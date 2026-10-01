"""Mag agent CLI — tool-using seat on the operator's local Mag disk, brain = DeepSeek (or Ollama).

UI is terminal: multi-line paste, file attach, light ANSI style.

Context law: pack-first. Provider context window is the real budget.
Auto-repack when near the window. No round ceiling — the context window is the real stop.
"""
from __future__ import annotations

import json
import os
import queue
import re
import sys
import threading
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from collections import deque
if os.name == "nt":  # B1 non-blocking stdin listener (Windows)
    import msvcrt

from config import ROOT
from mag.context_pack import (
    evolving_tail,
    build_context_pack,
    format_context_pack_text,
    freeze_system_prompt,
    infer_pack_mode,
)
from mag.context_admission import assess as assess_context, safe_write_receipt
from mag.compass import (
    FRAMEWORK_BLOCK,
    build_compass,
    constitution_text,
    record_decision,
    should_compass,
)
from mag import remedy  # at-will error toolkit: lookup cards from memory/remedies/
from mag import rails  # deterministic hard rails: configs/constitutional_rails.json (Maelstrom V2)
from mag.constants import PACK_STALE_DAYS  # the ONE decay bar (AG6 anchor guard shares it)
from models.providers import _looks_degenerate, chat_messages
from mag.write_strip import is_write_tool, read_only_from_env, strip_write_tools
from tools import TOOL_MAP, _normalize_args, dispatch as tool_dispatch

# --- HTTP backend (FastAPI) -------------------------------------------------
# The agent dispatches tools over HTTP to the FastAPI backend instead of
# executing them in-process. The backend owns the heavy lifting.
BACKEND_URL = os.environ.get("MAG_BACKEND_URL", "http://127.0.0.1:8000")
BACKEND_TIMEOUT = int(os.environ.get("MAG_BACKEND_TIMEOUT", "300"))  # seconds; shell/python tools can be slow

# No round ceiling (legacy max_tool_rounds removed 2026-08-03): the loop stops on
# final text, hard provider errors, or context-budget exhaustion (auto-repack +
# provider window are the real control). See run_turn.
MAX_HISTORY_MESSAGES = 24  # coarse clip; token budget wins when tighter
TOOL_RESULT_CHARS = 6000
ATTACH_TEXT_CHARS = 12000
# Tool schema + reply reserve (est. tokens) subtracted from provider window.
_TOOL_SCHEMA_RESERVE = 2500
_REPLY_RESERVE = 2500
# Default context windows (tokens) when provider config omits context_tokens.
_PROVIDER_CONTEXT_DEFAULTS: dict[str, int] = {
    "deepseek": 1_000_000,  # real 1M window (was 64K legacy default)
    "ollama": 32_000,
    "openrouter": 64_000,
    "anthropic": 200_000,
    "openai": 128_000,
    "gemini": 128_000,
    "xai": 128_000,
    "groq": 128_000,
    "together": 32_000,
}


def _load_mag_yaml() -> dict[str, Any]:
    try:
        import yaml  # type: ignore

        cfg_path = ROOT / "configs" / "mag.yaml"
        if cfg_path.exists():
            return yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    except Exception as exc:  # 2026-09-28 FW-46 silent-pass batch 2: the silent pass turned a corrupt configs/mag.yaml into silent all-defaults (repack ratio, budgets) with no trace; defaults still apply, the reason is now named on stderr
        print(f"[agent_cli] configs/mag.yaml unreadable, using defaults: {exc}", file=sys.stderr)
    return {}


def _repack_ratio() -> float:
    """Fraction of usable context before auto-repack (default 0.62)."""
    data = _load_mag_yaml()
    val = data.get("context_repack_ratio")
    try:
        r = float(val)
        if 0.35 <= r <= 0.9:
            return r
    except (TypeError, ValueError):
        pass
    return 0.62


# --- terminal style (stdlib ANSI; Windows VT when available) -----------------

_USE_COLOR = True


def _out(text: str = "", *, end: str = "\n") -> None:
    """Answer stream: final agent text ONLY. UI chrome uses stderr (print).

    Manifesto Phase 0: stdout/stderr split so a piped/orchestrated seat gets
    clean, machine-readable answers with zero terminal chrome.
    """
    try:
        sys.stdout.write(text + end)
        sys.stdout.flush()
    except Exception:
        pass





# Manifesto Phase 0: stdout/stderr split.
# Route this module's UI chrome (banner, status, tool traces, prompts) to
# stderr. Keep the binding module-local: mutating builtins.print here used to
# redirect every later-imported CLI's machine-readable output as well.
import builtins as _builtins
_PRINT = _builtins.print
def _chrome_print(*args, **kwargs):
    kwargs["file"] = sys.stderr
    _PRINT(*args, **kwargs)
print = _chrome_print


def _enable_windows_vt() -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        mode = ctypes.c_uint32()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            kernel32.SetConsoleMode(handle, mode.value | 0x0004)  # ENABLE_VIRTUAL_TERMINAL
    except Exception:
        pass
    # UTF-8 console for paste / unicode
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        sys.stdin.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass


def _c(code: str, s: str) -> str:
    if not _USE_COLOR or not sys.stdout.isatty():
        return s
    return f"\033[{code}m{s}\033[0m"


def dim(s: str) -> str:
    return _c("2", s)


def bold(s: str) -> str:
    return _c("1", s)


def green(s: str) -> str:
    return _c("92", s)


def cyan(s: str) -> str:
    return _c("96", s)


def yellow(s: str) -> str:
    return _c("93", s)


def mag_c(s: str) -> str:
    return _c("95", s)


def rule(char: str = "─", width: int = 56) -> str:
    return dim(char * width)


def print_mdish(text: str) -> None:
    """Light markdown → ANSI (bold, code, headers, bullets)."""
    for line in (text or "").splitlines():
        if line.startswith("### "):
            print(bold(cyan(line[4:])), flush=True)
        elif line.startswith("## "):
            print(bold(green(line[3:])), flush=True)
        elif line.startswith("# "):
            print(bold(line[2:]), flush=True)
        elif line.startswith(("- ", "* ")):
            body = line[2:]
            body = re.sub(r"\*\*(.+?)\*\*", lambda m: bold(m.group(1)), body)
            body = re.sub(r"`([^`]+)`", lambda m: yellow(m.group(1)), body)
            print(f"  {green('·')} {body}", flush=True)
        elif line.startswith("```"):
            print(dim(line), flush=True)
        else:
            body = re.sub(r"\*\*(.+?)\*\*", lambda m: bold(m.group(1)), line)
            body = re.sub(r"`([^`]+)`", lambda m: yellow(m.group(1)), body)
            print(body, flush=True)


def print_banner(provider: str, model: str | None, pack: dict[str, Any]) -> None:
    print(rule("═"), flush=True)
    print(
        bold(green("MAG AGENT"))
        + dim("  ·  ")
        + cyan(provider)
        + (dim(f" / {model}") if model else "")
        + dim("  ·  ")
        + _tip_line(pack)
        + dim("  ·  local tools"),
        flush=True,
    )
    print(rule("═"), flush=True)
    print(dim(f"root  {ROOT}"), flush=True)
    print(
        dim("tools ") + ", ".join(TOOL_MAP),
        flush=True,
    )
    print(rule(), flush=True)
    print(
        bold("input")
        + dim("  single line  ·  ")
        + yellow("/paste")
        + dim(" multi-line until ")
        + yellow("/end")
        + dim("  ·  ")
        + yellow("/file path")
        + dim(" attach text"),
        flush=True,
    )
    print(
        dim("cmds   ")
        + "/pack  /tools  /save  /img path  /help  /quit",
        flush=True,
    )
    print(
        dim("note   ")
        + "Paste big text with /paste. Images: path only (no vision yet).",
        flush=True,
    )
    print(
        dim("ctx    ")
        + f"window~{provider_context_tokens(provider)} tok · auto-repack at {_repack_ratio():.0%}",
        flush=True,
    )
    print(rule(), flush=True)


def print_help() -> None:
    lines = [
        ("/paste … /end", "Paste multi-line text/code blocks (Ctrl+V between)"),
        ("/file <path>", "Attach a text file into the next message"),
        ("/img <path>", "Note an image path for the model (no vision API yet)"),
        ("/pack", "Refresh Mag context-pack + reset chat memory (manual)"),
        ("/tools", "List Mag tools"),
        ("/save", "Append last answer → memory/working.md"),
        ("/help", "This help"),
        ("/quit", "Exit"),
        ("plain text", "One-line goal (Enter sends)"),
        ("auto-repack", "Mid-turn when near provider context window (DeepSeek etc.)"),
    ]
    print(bold("Commands"), flush=True)
    for cmd, desc in lines:
        print(f"  {yellow(cmd):<28}  {dim(desc)}", flush=True)

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "List files/dirs under a path relative to Mag project root.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Directory path, default '.'",
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a text file under Mag root or sibling mycelial-republic (jailed FS_ROOTS). Pass line_from/line_to for a 1-indexed numbered region (kills hand-rolled dump snippets). Republic dual-progress: use ../mycelial-republic/docs/MILESTONES.md or absolute path under Documents/projects/mycelial-republic — not Mag docs/MILESTONES.md.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path relative to Mag root, or under sibling mycelial-republic"},
                    "max_chars": {"type": "integer", "description": "Max characters to return"},
                    "line_from": {"type": "integer", "description": "1-indexed first line (line-range mode; numbered output)"},
                    "line_to": {"type": "integer", "description": "1-indexed last line, inclusive; clamps to EOF"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write/edit a text file under Mag root. Use search+replace for surgical edits (never clobber whole files); snapshot=sha256 rejects external drift. Full content only when creating files. Prefer memory/working.md, dig leaves, queue - not .env or verkle_tip. .py writes auto-verify via py_compile (returns verified + compile_error); diff edits also return changed_from/changed_to for a follow-up read_file line-range check.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path relative to Mag root"},
                    "content": {"type": "string", "description": "Full content (only when creating a new file; prefer search+replace for edits)"},
                    "search": {"type": "string", "description": "Exact substring to find (must appear exactly once)"},
                    "replace": {"type": "string", "description": "Replacement for search"},
                    "snapshot": {"type": "string", "description": "Expected current sha256 of the file (drift guard)"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_files",
            "description": "Substring search in md/txt/py/yaml/json under a path.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string"},
                    "under": {"type": "string", "description": "Root to search, default '.'"},
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_shell",
            "description": "Run an allowlisted shell command in Mag root (Windows PowerShell).",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string"},
                    "timeout": {"type": "integer"},
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_python",
            "description": "Run a short Python snippet in a temp sandbox. Preamble auto-injects: ROOT (project root Path), P(*parts) -> path join under ROOT, dump_lines(path, line_from, line_to) -> numbered file region. Use these instead of re-implementing file I/O.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string"},
                    "timeout": {"type": "integer"},
                },
                "required": ["code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "swarm_sense",
            "description": "NPC body-sense: one fog-of-war snapshot of the swarm's own body (health/capacity/economics/map). Call to perceive the world before acting.",
            "parameters": {
                "type": "object",
                "properties": {
                    "owner": {"type": "string", "description": "who senses (default worker)"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "pheromone_drop",
            "description": "Stigmergy: drop one content-addressed pheromone mark (kind: trail|fruitful|dead|here|danger|signal) so other NPCs build on your trail. The castle is built from these marks.",
            "parameters": {
                "type": "object",
                "properties": {
                    "scent": {"type": "string", "description": "the mark's meaning, e.g. 'foundation laid here'"},
                    "kind": {"type": "string", "description": "trail|fruitful|dead|here|danger|signal (default trail)"},
                    "at": {"type": "string", "description": "location/context this mark applies to"},
                    "owner": {"type": "string", "description": "who drops it (default worker)"},
                },
                "required": ["scent"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "pheromone_trail",
            "description": "Read the local pheromone trail — the marks prior builders left. Do this before starting new work to build on what exists instead of redoing it.",
            "parameters": {
                "type": "object",
                "properties": {
                    "kind": {"type": "string", "description": "filter to one kind (default all)"},
                    "limit": {"type": "integer", "description": "max marks to return (default 40)"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "blackboard_post",
            "description": "Post a note to the egregore's shared blackboard. kind: finding|decision|conflict|open-question|handoff|claim. DECISIONS and CONFLICTS are pinned forever (they anchor coherence) — use decision for load-bearing facts every builder must obey.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "the note"},
                    "kind": {"type": "string", "description": "finding|decision|conflict|open-question|handoff|claim (default finding)"},
                    "owner": {"type": "string", "description": "who posts (default worker)"},
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "blackboard_read",
            "description": "Read the egregore's shared mind: pinned decisions/conflicts (always) + the recent tail. Read this before acting to see what the collective has already decided.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "tail size (default 60)"},
                    "pinned_only": {"type": "boolean", "description": "only pinned decisions/conflicts (default false)"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "scan_measure",
            "description": "Deterministic scan of a stochastic signal: seeded bootstrap measurement (mean + 95% CI + SD) of noisy numeric samples. Same seed -> same reading (reproducible, $0). Use to measure a noisy/uncertain signal without guessing.",
            "parameters": {
                "type": "object",
                "properties": {
                    "samples": {"type": "array", "items": {"type": "number"}, "description": "the noisy numeric samples to measure"},
                    "seed": {"type": "integer", "description": "reproducibility seed (default 1738)"},
                    "b": {"type": "integer", "description": "bootstrap draws (default 1000)"},
                },
                "required": ["samples"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "scan_probe",
            "description": "Deterministic signature probe of a text environment: reproducible fingerprint + scan for known signatures (frontier-reasoning / one-structure / hidden-structure / standing-wave). Same seed + text -> same result. $0.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "the text environment to probe"},
                    "seed": {"type": "integer", "description": "reproducibility seed (default 1738)"},
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "scan_grid",
            "description": "Deterministic scan of a whole stochastic environment (a grid of noisy readings): reproducible fingerprint of the grid + seeded measurement of its numeric cells. $0.",
            "parameters": {
                "type": "object",
                "properties": {
                    "environment": {"type": "array", "description": "the stochastic environment cells to scan"},
                    "seed": {"type": "integer", "description": "reproducibility seed (default 1738)"},
                    "b": {"type": "integer", "description": "bootstrap draws (default 1000)"},
                },
                "required": ["environment"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mean_field",
            "description": "Deterministic MAPPING of a stochastic model (mean-field projection): given several noisy trajectories, project them into their deterministic equivalent — the expected trajectory E[x_t] at each step + the drift ODE. Transforms random processes into a fixed, predictable path. $0, stdlib.",
            "parameters": {
                "type": "object",
                "properties": {
                    "trajectories": {"type": "array", "items": {"type": "array", "items": {"type": "number"}}, "description": "the stochastic trajectories (each a time-series of numbers) to project"},
                },
                "required": ["trajectories"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "research",
            "description": "Search-swarm seam: route a research ask (like a Google search / deepseek research ask) to the swarm via route_novel — cheap DeepSeek, k8s-drained, the 'search swarm over browsers'. Separate from the deterministic core; the answer returns when the swarm drains the task, not synchronously.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ask": {"type": "string", "description": "the research question to send to the search swarm"},
                    "surface": {"type": "string", "description": "routing surface label (default det-scan)"},
                },
                "required": ["ask"],
            },
        },
    },
]


# --- fan-out write-strip (MICKEY-17 owed chore "strip write tools at
# --- fan-out", discharged 2026-09-26; compiler lives in mag/write_strip.py) --
# In read-only mode the seat's tool grant is COMPILED DOWN before the first
# model call: _schemas() is the one grant every provider call site sees, so
# the model never receives write-tool definitions (schema-level omission, not
# runtime veto). _run_tool() carries a backstop refusal keyed on the same
# receipt. Spawned fan-out children (orchestrator/gpipes) get this by default.
_ACTIVE_TOOL_SCHEMAS: list[dict[str, Any]] = TOOL_SCHEMAS
_STRIP_RECEIPT: dict[str, Any] | None = None
_DENIED_TOOL_NAMES: frozenset[str] = frozenset()


def activate_read_only(*, strict: bool = False) -> dict[str, Any]:
    """Compile TOOL_SCHEMAS down to the read-only grant, before the first call."""
    global _ACTIVE_TOOL_SCHEMAS, _STRIP_RECEIPT, _DENIED_TOOL_NAMES
    result = strip_write_tools(TOOL_SCHEMAS, strict=strict)
    _ACTIVE_TOOL_SCHEMAS = result["tools"]
    _STRIP_RECEIPT = result["receipt"]
    _DENIED_TOOL_NAMES = frozenset(result["receipt"]["stripped_names"])
    return result["receipt"]


def restore_full_grant() -> None:
    """Escape hatch (tests / interactive retry): back to the full schema list."""
    global _ACTIVE_TOOL_SCHEMAS, _STRIP_RECEIPT, _DENIED_TOOL_NAMES
    _ACTIVE_TOOL_SCHEMAS = TOOL_SCHEMAS
    _STRIP_RECEIPT = None
    _DENIED_TOOL_NAMES = frozenset()


def _schemas() -> list[dict[str, Any]]:
    """The single tool grant every provider call sees (read-only-compiled when active)."""
    return _ACTIVE_TOOL_SCHEMAS


def _read_only_notice() -> str:
    """One static line-block for the system body while a strip is active.

    Static per session (receipt fixed at activation), so the frozen-prefix
    bytes stay cache-stable. Tells the seat its grant is read-only so it
    returns proposed writes as data instead of inventing a write call.
    """
    if _STRIP_RECEIPT is None:
        return ""
    names = _STRIP_RECEIPT["stripped_names"]
    shown = ", ".join(names[:12]) + (", ..." if len(names) > 12 else "")
    return (
        "\n\n## Read-only seat (fan-out write-strip)\n"
        "This seat's tool grant is READ-ONLY. These tools are not in your schema "
        f"and cannot be called: {shown or 'none'}. Never attempt a write; return the "
        "proposed write as text/data in your final answer so the orchestrator applies it."
    )


# --- ANCHOR freshness guard (AG6, 2026-09-29, audit finding #5) ---------------
# The anchored plan is injected into EVERY agent session (Layer 2 "never forget
# the goal"), so a stale anchor is worse than no anchor: it re-teaches finished
# state (2026-08-03 sovereign-steering status) as if current. Same law as
# tools/freshness_check.py: the one decay bar is mag.constants.PACK_STALE_DAYS
# (7). The guard REFUSES to inject an anchor whose "## Status YYYY-MM-DD"
# stamp is older than the bar (or carries no parseable stamp at all) and says
# so loudly instead: one ANCHOR-STALE router log line (latched per process)
# plus an in-band marker the seat itself can read and escalate. Refreshing,
# re-stamping, or re-qualitying memory/plans/ANCHOR.md stays an operator call —
# this guard only makes staleness loud.
_ANCHOR_STALE_DAYS = PACK_STALE_DAYS
_ANCHOR_STATUS_DATE = re.compile(r"^##\s*Status\s+(\d{4}-\d{2}-\d{2})", re.MULTILINE)
_anchor_stale_logged = False


def _anchor_age_days(text: str) -> int | None:
    """Days since the anchor's '## Status YYYY-MM-DD' line; None when unstamped.

    Parsed from the FULL file text (pre-truncation) — the Status header format
    is read from the file itself (memory/plans/ANCHOR.md uses '## Status <date>').
    """
    m = _ANCHOR_STATUS_DATE.search(text)
    if not m:
        return None
    try:
        stamped = datetime.strptime(m.group(1), "%Y-%m-%d").date()
    except ValueError:
        return None
    return (date.today() - stamped).days


def _anchor_injection(anchor_path: str) -> str:
    """Anchor block for _system_prompt under the AG6 freshness guard.

    Fresh (stamped <= 7 days old) → inject as before (max 2500 chars).
    Stale or unstamped → inject a loud refusal marker, log ANCHOR-STALE once
    per process to logs/router.jsonl. File re-read per call (an operator
    refresh mid-session takes effect on the next provider call); only the log
    is latched.
    """
    global _anchor_stale_logged
    path = Path(anchor_path)
    try:
        text = path.read_text(encoding="utf-8") if path.is_file() else ""
    except Exception:
        text = ""
    if not text:
        return ""
    age = _anchor_age_days(text)
    if age is not None and age <= _ANCHOR_STALE_DAYS:
        return f"\n## Anchored plan (survives repack - re-read before acting)\n{text[:2500]}\n"
    if age is None:
        days_label, why = "-1", "no parseable '## Status YYYY-MM-DD' stamp — restamp it with today's date"
    else:
        days_label, why = str(age), f"Status stamp is {age} days old (bar: {_ANCHOR_STALE_DAYS} days)"
    if not _anchor_stale_logged:
        _anchor_stale_logged = True
        try:
            from audit import log_event

            log_event({"event": "ANCHOR-STALE", "days": age, "anchor": str(path)})
        except Exception:
            pass
    return (
        f"\n## Anchored plan withheld (ANCHOR-STALE {days_label})\n"
        f"{path} was NOT injected: {why}. Refreshing or re-stamping the anchor "
        "is an operator call; proceed from state/CURRENT.md + the compass, not "
        "the stale anchor, and tell the operator the anchor is stale.\n"
    )


def _system_prompt(
    pack_text: str,
    *,
    repacked: bool = False,
    goal: str = "",
    agent_state: str | None = None,
    preamble: dict[str, Any] | None = None,
) -> str:
    repack_note = ""
    anchor_path = os.environ.get("MAG_ANCHORED_PLAN") or str(ROOT / "memory" / "plans" / "ANCHOR.md")
    try:
        anchor_block = _anchor_injection(anchor_path)
    except Exception:
        anchor_block = ""
    framework_block = FRAMEWORK_BLOCK
    law_block = "\n".join(
        [
            "## Binding law (constitution - immutable)",
            constitution_text(700),
            "\nObligations always hold: data tiers T0-T3 (T0/T1 never to free remote train-on-input APIs); "
            "no .env/verkle_tip/knots writes; irreversible acts need a Human Nod; artifact > transcript.",
        ]
    )
    from mag.session_route import preamble as _session_preamble
    from mag.session_route import render as _render_preamble
    if preamble is None:
        preamble = _session_preamble(goal=goal, agent_state=agent_state, with_model=False)
    preamble_block = _render_preamble(preamble)
    if repacked:
        repack_note = (
            "\n## Auto-repack\n"
            "History was compacted to fit this provider's context window "
            "(pack-first). Residual below holds the goal "
            "and tools already run. Continue the job; do not re-discover from zero.\n"
        )
    return f"""You are Mag agent CLI — a tool-using seat on the operator's local Mag disk.
You keep work moving with local tools + this model.

## Law
- One job at a time. Truth-only. No flattery.
- Artifact > transcript. Prefer tools over guessing file contents.
- Paths: Mag root, or sibling `../mycelial-republic/` (read-allowed for dual progress / BOOT_SOIL). Absolute under Documents/projects/mycelial-republic is OK. Mag does NOT contain docs/MILESTONES.md — that lives in mycelial-republic.
- Never read or echo .env secrets. Never destroy residual DNA / verkle_tip / knots.
- Prefer write targets: memory/working.md, memory/runs/*/progress.md, queue/, dig leaves under memory/improve/.
- When done, give a short final answer (what you did + paths). Do not narrate fake tool calls — call tools for real.
- Context is scarce on remote seats (esp. DeepSeek). Prefer short tool results and finish; the harness will auto-repack if the window fills.

## Final answer format (human-readable — always use when replying to operator)
Structure your last message with markdown sections:

### TL;DR
One line.

### What I did
Bullets — files touched, commands run, artifacts written (paths).

### What I think
Honest assessment — what surprised you, risks, what might be wrong.

### Next
One concrete move for the operator (or ask one clarifying question).

### Open
What you still don't know — no bluffing.

Keep each section short. Tool traces belong in tools, not prose walls.
{repack_note}
{anchor_block}
{law_block}
{framework_block}
{preamble_block}
## Context pack (authoritative, min tokens)
{pack_text[:3500]}
"""


def _safe_tool_args(name: str, args: dict[str, Any]) -> dict[str, Any] | None:
    """Block obviously dangerous writes."""
    if name == "write_file":
        path = str(args.get("path") or "").replace("\\", "/").lower()
        banned = (
            ".env",
            "verkle_tip.json",
            "verkle_chain.jsonl",
            "/knots/",
            "\\knots\\",
            "quota_state.json",
        )
        for b in banned:
            if b in path:
                return None
    return args


def _preflight_tool(
    name: str,
    args: dict[str, Any],
    *,
    session_id: str | None = None,
) -> tuple[bool, str]:
    """Layer 1 (failure defense): reject obviously-failing tool calls before they hit the OS."""
    sid = (session_id or "").strip()
    if sid.startswith("desk-"):
        if name in ("run_shell", "shell"):
            return False, _with_remedy(
                "desk seat blocks run_shell (nested shell/LLM loops took down operator network). "
                "Use Workers tab, Shell window, or Local lane. Desk remote = read/write/search only.",
                name,
            )
        if name == "run_python":
            code = str(args.get("code") or "").lower()
            if "from llm import" in code or "import llm" in code:
                return False, _with_remedy(
                    "desk seat blocks nested LLM via run_python — use Local lane (orchestrator) "
                    "or spawn a Worker for research loops.",
                    name,
                )
        if name == "search_files":
            q = str(args.get("query") or args.get("pattern") or "")
            if len(q) < 3:
                return False, _with_remedy("search_files query too broad on desk seat", name)
    if name == "write_file":
        path = str(args.get("path") or "").strip()
        if not path:
            msg = (
                "write_file missing path= — emit flat JSON "
                '{"path": "relative/file.py", "content": "..."} '
                "(sibling keys, not nested arguments/parameters blob)"
            )
            return False, _with_remedy(msg, name)
        if path:
            ok, rmsg = rails.check_write_file(path, str(args.get("content") or ""))
            if not ok:
                return False, _with_remedy(rmsg, name)
            full = Path(path)
            if not full.is_absolute():
                full = ROOT / full
            if full.parent and not full.parent.exists():
                msg = f"directory does not exist: {full.parent} (create it first)"
                return False, _with_remedy(msg, name)
    if name == "run_python":
        code = str(args.get("code") or "").strip()
        if len(code) < 12:
            msg = "run_python snippet too short - likely a degenerate loop, not a real task"
            return False, _with_remedy(msg, name)
    return True, ""


def _with_remedy(msg: str, tool: str) -> str:
    """Append the matching remedy card so a blocked call teaches the fix."""
    card = remedy.prevent(tool)
    if card:
        return msg + " | " + remedy.card_md(card)
    return msg




def _run_tool_http(name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Dispatch a tool call to the FastAPI backend over HTTP."""
    import httpx

    url = f"{BACKEND_URL.rstrip('/')}/run_task"
    payload = {"tool": name, "args": args}
    try:
        with httpx.Client(timeout=BACKEND_TIMEOUT) as client:
            resp = client.post(url, json=payload)
            if resp.status_code != 200:
                return {
                    "ok": False,
                    "error": f"backend HTTP {resp.status_code}: {resp.text[:300]}",
                }
            body = resp.json()
            if not isinstance(body, dict):
                return {"ok": False, "error": f"backend returned non-JSON: {str(body)[:200]}"}
            if not body.get("ok"):
                result = body.get("result")
                # The actionable text lives one level down: `tools.dispatch`
                # returns {"ok": False, "error": "bad arguments for <tool>: ..."}
                # as the *result*, leaving the envelope's own `error` null.
                # Reading only the envelope replaces a self-teaching message
                # with the opaque "backend reported failure" and the model
                # re-emits the same bad call forever.
                nested = result.get("error") if isinstance(result, dict) else None
                return {
                    "ok": False,
                    "error": body.get("error") or nested or "backend reported failure",
                    "result": result,
                }
            return body.get("result") or {"ok": True}
    except httpx.ConnectError:
        return {
            "ok": False,
            "error": (
                f"backend not reachable at {BACKEND_URL}. "
                "Start it with: python -m backend.server"
            ),
        }
    except httpx.TimeoutException:
        return {"ok": False, "error": f"backend timeout after {BACKEND_TIMEOUT}s"}
    except Exception as e:
        return {"ok": False, "error": f"backend request failed: {e}"}


def _run_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    if name not in TOOL_MAP:
        return {"ok": False, "error": f"unknown tool: {name}", "tools": list(TOOL_MAP)}
    # Write-strip backstop: in read-only mode the schema was already omitted,
    # so a denied call here means the model invented a write tool it never saw.
    # Refuse, and hand the write back to the orchestrator as data
    # (write-delegation row 1: lanes return proposed writes, never write directly).
    if name in _DENIED_TOOL_NAMES:
        return {
            "ok": False,
            "error": (
                f"read-only seat (fan-out write-strip): tool '{name}' is not in this "
                "seat's grant; return the proposed write to the orchestrator instead."
            ),
        }
    normalized = _normalize_args(name, args)
    if normalized is not None:
        args = normalized
    safe = _safe_tool_args(name, args)
    if safe is None:
        return {"ok": False, "error": f"blocked write/target for tool {name}: {args.get('path')}"}
    return _run_tool_http(name, safe)


def _sanitize_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop orphan tool results / broken tool_call chains (DeepSeek 400 otherwise).

    API law: role=tool only after assistant message that includes tool_calls.
    """
    if not messages:
        return messages
    out: list[dict[str, Any]] = []
    i = 0
    while i < len(messages):
        m = messages[i]
        role = m.get("role")
        if role == "system":
            if not out:
                out.append(m)
            i += 1
            continue
        if role == "tool":
            # orphan tool — skip
            i += 1
            continue
        if role == "assistant":
            tcs = m.get("tool_calls") or []
            if tcs:
                # Need matching tool messages immediately after (or drop whole block)
                ids = []
                for tc in tcs:
                    if isinstance(tc, dict) and tc.get("id"):
                        ids.append(tc["id"])
                j = i + 1
                tool_msgs: list[dict[str, Any]] = []
                while j < len(messages) and messages[j].get("role") == "tool":
                    tool_msgs.append(messages[j])
                    j += 1
                got = {t.get("tool_call_id") for t in tool_msgs}
                if ids and all(tid in got for tid in ids):
                    # Normalize assistant: content may be null
                    asst = dict(m)
                    if asst.get("content") is None:
                        asst["content"] = ""
                    out.append(asst)
                    # only keep tools that match known ids
                    for t in tool_msgs:
                        if t.get("tool_call_id") in ids:
                            out.append(t)
                    i = j
                    continue
                # incomplete chain — drop assistant+partial tools
                i = j
                continue
            # plain assistant text
            asst = dict(m)
            if asst.get("content") is None:
                asst["content"] = ""
            # strip empty tool_calls key
            if "tool_calls" in asst and not asst["tool_calls"]:
                asst.pop("tool_calls", None)
            out.append(asst)
            i += 1
            continue
        if role == "user":
            out.append(m)
            i += 1
            continue
        i += 1
    return out


def _estimate_tokens(messages: list[dict[str, Any]]) -> int:
    """Rough token estimate (chars/4). Good enough for repack triggers."""
    total = 0
    for m in messages:
        try:
            total += len(json.dumps(m, default=str, ensure_ascii=False))
        except Exception:
            total += len(str(m))
    # tool schemas ride along every tool-enabled call
    total += 8_000
    return max(1, total // 4)


def provider_context_tokens(provider: str) -> int:
    """Usable context window for provider (from providers.yaml or defaults)."""
    pid = (provider or "deepseek").strip().lower()
    try:
        from models.providers import get_provider

        pcfg = get_provider(pid) or {}
        for key in ("context_tokens", "max_context_tokens", "context_window"):
            val = pcfg.get(key)
            if isinstance(val, int) and val > 1000:
                return val
            if isinstance(val, str) and val.isdigit():
                return int(val)
    except Exception:
        pass
    return _PROVIDER_CONTEXT_DEFAULTS.get(pid, 64_000)


def usable_context_budget(provider: str) -> int:
    """Tokens available for messages after schema + reply reserve."""
    raw = provider_context_tokens(provider)
    return max(4_000, raw - _TOOL_SCHEMA_RESERVE - _REPLY_RESERVE)


def _tool_residual_excerpt(messages: list[dict[str, Any]], *, max_chars: int = 4500) -> str:
    """Compact last tool results for repack residual (artifact crumbs, not full chain)."""
    chunks: list[str] = []
    for m in messages:
        if m.get("role") != "tool":
            continue
        body = (m.get("content") or "").strip()
        if not body:
            continue
        # keep path-ish / ok flags dense
        if len(body) > 900:
            body = body[:700] + "\n…[truncated]…\n" + body[-150:]
        chunks.append(body)
    text = "\n---\n".join(chunks[-8:])
    if len(text) > max_chars:
        text = text[-max_chars:]
    return text


def repack_messages(
    messages: list[dict[str, Any]],
    *,
    user_text: str,
    traces: list[str],
    provider: str,
    mode: str | None = None,
    session_id: str | None = None,
    instructions: str | list[str] | None = None,
) -> list[dict[str, Any]]:
    """Rebuild to system pack + residual (pack-first analog).

    Drops bloated tool chains. Keeps goal + tool ok flags + short result crumbs.

    A2 context freeze: the system prompt body + TOOL_SCHEMAS are frozen as a
    byte-identical per-session prefix (freeze_system_prompt); live values —
    the fresh context pack, the residual, the goal — ride in a small evolving
    tail appended AFTER that prefix, so consecutive repacks never mutate the
    prefix bytes the provider prompt cache keys on.

    New instructions (openai-week fold row) ride as TRAILING developer
    messages, appended at the END of the payload — never spliced into the
    frozen prefix, where a mid-insert would re-price everything after it.
    Sources: developer-role messages already in the input history, plus the
    optional ``instructions`` argument (one string or a list). Byte-stability
    of the prefix holds regardless of what instructions arrive.
    """
    pack = build_context_pack(
        mode=mode or infer_pack_mode(user_text),
        goal=user_text,
        max_brief=900,
        max_live=400,
    )
    pack_text = format_context_pack_text(pack)
    try:
        (ROOT / "memory" / "context_pack_latest.md").write_text(pack_text, encoding="utf-8")
    except Exception:
        pass

    tool_flags = " · ".join(traces[-24:]) if traces else "(none yet)"
    crumbs = _tool_residual_excerpt(messages)
    residual = (
        f"[auto-repack · provider={provider} · est_tokens_before high]\n\n"
        f"## Goal still in force\n{user_text.strip()}\n\n"
        f"## Tools already this turn\n{tool_flags}\n\n"
        f"## Result crumbs (truncated)\n{crumbs or '(no tool bodies kept)'}\n\n"
        "Continue from residual. Call tools only for gaps. Final answer when done."
    )
    # Frozen prefix: stable _system_prompt body (live pack text deliberately
    # omitted) + TOOL_SCHEMAS, captured once per session and reused verbatim.
    body = _system_prompt("", repacked=False)
    marker = "## Context pack (authoritative"
    cut = body.rfind(marker)
    stable_body = body[:cut].rstrip() if cut != -1 else body.rstrip()
    # Fan-out write-strip: the notice is static per session, so the frozen
    # prefix stays byte-stable (prompt-cache law preserved).
    stable_body += _read_only_notice()
    frozen = freeze_system_prompt(
        stable_body + "\n\n## Context pack (live — evolving tail below; prefix above is frozen)\n",
        tool_schemas=_schemas(),
        session_id=session_id or "agent-cli-default",
    )
    tail = evolving_tail(
        goal=user_text,
        pack_text=pack_text[:3500],
        residual=residual,
        repacked=True,
    )
    # Trailing developer messages: new instructions from the input history and
    # the explicit argument, carried verbatim AFTER the frozen-prefix payload.
    dev_msgs: list[dict[str, Any]] = []
    for m in messages:
        if m.get("role") == "developer":
            body = str(m.get("content") or "").strip()
            if body:
                dev_msgs.append({"role": "developer", "content": body})
    ins_list: list[str] = (
        [instructions] if isinstance(instructions, str) else list(instructions or [])
    )
    for ins in ins_list:
        body = str(ins or "").strip()
        if body:
            dev_msgs.append({"role": "developer", "content": body})
    return [
        {"role": "system", "content": frozen["prefix_text"] + tail},
        {"role": "user", "content": residual},
    ] + dev_msgs


def _clip_history(messages: list[dict[str, Any]], *, provider: str = "deepseek") -> list[dict[str, Any]]:
    messages = _sanitize_messages(messages)
    if not messages:
        return messages
    system = messages[0] if messages[0].get("role") == "system" else None
    rest = messages[1:] if system else messages[:]
    if len(rest) > MAX_HISTORY_MESSAGES:
        # clip from left but re-sanitize so we don't start mid tool-chain
        rest = _sanitize_messages(rest[-MAX_HISTORY_MESSAGES:])
        # if first is still tool, drop until user/assistant
        while rest and rest[0].get("role") == "tool":
            rest = rest[1:]
        rest = _sanitize_messages(rest)
    out = ([system] if system else []) + rest
    # Token budget wins over message count: if still fat, hard-repack path is run_turn's job
    budget = int(usable_context_budget(provider) * _repack_ratio())
    # Do not silently destroy the remaining history here.  run_turn owns the
    # repack decision and can preserve tool crumbs plus the active build/audit
    # contract in a durable, inspectable residual.
    return out


def _tip_line(pack: dict[str, Any]) -> str:
    tip = pack.get("tip") or {}
    if tip.get("ok"):
        return f"tip={tip.get('root_short')}… leaves={tip.get('n_leaves')}"
    return "tip=?"


def _drain_steer_until(deadline: float) -> list[str]:
    """Drain steer queue with a bounded wait (used inside a running round so
    !pause/!steer are acted on the instant they land, not only between rounds)."""
    out: list[str] = []
    while True:
        try:
            out.append(_STEER_QUEUE.get(timeout=max(0.0, deadline - time.time())))
        except queue.Empty:
            break
    return out


# False-success guard: a seat that claims file edits but ran no mutating tool
# this turn is hallucinating. Local 7B did this 2026-08-07 — reported "updated
# llm.py with timeout_seconds, verified imports" with ZERO tool calls and no
# file change. Treat as a failure → log + escalate (smarter tier via DF ladder).
_MUTATING_TOOLS = {
    "write_file",
    "write_file_append",
    "edit_file",
    "patch_file",
    "run_shell",
    "run_python",
    "pheromone_drop",      # NPC writes a mark to the trail
    "blackboard_post",     # NPC writes a note to the shared mind
}
_FAKE_SUCCESS_KEYWORDS = (
    "updated",
    "added",
    "implemented",
    "created",
    "fixed",
    "edited",
    "wrote",
    "changed",
    "modified",
    "refactored",
    "patched",
    "committed",
)


def _claims_edit(text: str) -> bool:
    """Does the final answer claim file edits/completion? (may be fake.)"""
    low = (text or "").lower()
    return any(k in low for k in _FAKE_SUCCESS_KEYWORDS)


def _escalate_fake_success(*, text: str, provider: str, goal: str, session_id: str | None = None):
    """Log the false-success + hand off to the next smarter tier (DF ladder)."""
    detail = f"claimed file edits but no mutating tool ran: {(text or '')[:200]}"
    try:
        from mag.operator_inbox import log_behavioral_event

        log_behavioral_event(
            kind="fake_success",
            detail=detail,
            tool="write_file",
            phase="verify",
            session_id=session_id,
            provider=provider,
        )
    except Exception:
        pass
    try:
        from mag.failure_kb import log_failure

        log_failure(
            kind="fake_success",
            detail=detail,
            tool="write_file",
            error="no file mutation on disk",
            phase="verify",
            session_id=session_id,
            provider=provider,
        )
    except Exception:
        pass
    try:
        from mag.decision_framework import escalate_on_loop

        esc = escalate_on_loop(
            goal=goal,
            provider=provider,
            tool="write_file",
            detail="false-success: claimed edits, wrote nothing",
            session_id=session_id,
        )
        return esc if esc.get("ok") else None
    except Exception:
        return None


def run_turn(
    user_text: str,
    *,
    provider: str,
    model: str | None,
    messages: list[dict[str, Any]],
    on_stream=None,
    on_status=None,
    session_id: str | None = None,
    tier: str = "T1",
) -> tuple[str, list[dict[str, Any]], list[str]]:
    """One user turn: tool loop until final text. Mutates/returns messages.

    No round ceiling (legacy safety loop removed 2026-08-03). The loop ends on:
      * final text from the model (normal end),
      * hard provider error (context/length etc. — repack, then error text),
      * context-budget exhaustion after max_repacks repacks.
    Empty model responses (crash artifacts) are retried twice with a nudge.
    """
    # Never append user onto a half-finished tool chain
    messages = _sanitize_messages(messages)
    messages.append({"role": "user", "content": user_text})
    messages = _clip_history(messages, provider=provider)
    traces: list[str] = []
    budget = usable_context_budget(provider)
    ratio = _repack_ratio()
    threshold = int(budget * ratio)
    repacks = 0
    max_repacks = 4
    timeout_retries = 0
    pack_mode = infer_pack_mode(user_text)

    rnd = 0
    empty_streak = 0
    degenerate_retries = 0
    collapse_window: deque[str] = deque(maxlen=5)
    collapse_nudges = 0
    last_tool = "-"
    turn_mutated = False
    turn_t0 = time.time()
    while True:
        rnd += 1
        _steer_interrupt.clear()  # T1: fresh round = fresh interrupt budget
        _emit_status(
            on_status,
            session_id,
            phase="model",
            detail=f"round {rnd} start",
            round=rnd,
            last_tool=last_tool,
            elapsed_ms=int((time.time() - turn_t0) * 1000),
        )
        if session_id and str(session_id).startswith("desk-") and rnd > _DESK_MAX_ROUNDS:
            _clear_live_turn(session_id)
            return (
                f"**Desk guard:** stopped after {rnd - 1} tool rounds (limit {_DESK_MAX_ROUNDS}). "
                "The remote seat was looping — use **Reset agent**, narrow the goal on the canvas, "
                "or spawn a **Worker** (Workers tab / Shell) for long shell loops.\n\n"
                f"_Last tool: `{last_tool}` · steer with !pause then a one-line goal._",
                messages,
                traces + [f"desk_guard:round>{_DESK_MAX_ROUNDS}"],
            )
        # B2/B3 (T1 fix 2026-08-03): act on steer commands IMMEDIATELY when they
        # arrive, not only at the next round boundary. _handle_steer_cmd sets
        # _paused/_steer_interrupt on !pause/!escape and records steer text;
        # the pause gate below + the in-tool-loop gate stop the churn mid-round.
        for cmd in _drain_steer_until(time.time() + 0.15):
            steer_text = _handle_steer_cmd(cmd)
            if steer_text:
                messages = apply_steer(messages, steer_text)
                traces.append(f"steer:{steer_text[:30]}")
                _emit_status(
                    on_status,
                    session_id,
                    phase="steer",
                    detail=steer_text[:120],
                    round=rnd,
                    last_tool=last_tool,
                )
                print(dim(f"  → operator steer absorbed: {steer_text[:60]}"), flush=True)
            elif cmd.strip().lower() in ("!continue", "!c"):
                _paused.clear()
                print(dim("  → resumed (Human Nod)"), flush=True)
            # !pause/!escape handled inside _handle_steer_cmd (sets event + ack)
        # pause gate: !pause blocks until !continue, but keep draining steer
        # text while paused so a queued !steer is still absorbed.
        while _paused.is_set():
            _emit_status(
                on_status,
                session_id,
                phase="pause",
                detail="paused — waiting for !continue",
                round=rnd,
                last_tool=last_tool,
            )
            time.sleep(0.3)
            for cmd in _drain_steer():
                steer_text = _handle_steer_cmd(cmd)
                if steer_text:
                    messages = apply_steer(messages, steer_text)
                    traces.append(f"steer:{steer_text[:30]}")
                    print(dim(f"  → operator steer absorbed: {steer_text[:60]}"), flush=True)
                elif cmd.strip().lower() in ("!continue", "!c"):
                    _paused.clear()
                    print(dim("  → resumed (Human Nod)"), flush=True)
        messages = _sanitize_messages(messages)
        est = _estimate_tokens(messages)
        admission = assess_context(
            estimated_tokens=est,
            context_window=provider_context_tokens(provider),
            repack_ratio=ratio,
            tool_schema_reserve=_TOOL_SCHEMA_RESERVE,
            reply_reserve=_REPLY_RESERVE,
            reason="round_preflight",
            provider=provider,
            session_id=session_id or "",
            repacks=repacks,
            max_repacks=max_repacks,
        )
        if admission["band"] in ("red", "black"):
            safe_write_receipt(ROOT, admission)
            traces.append(f"context_pressure:{admission['band']}:{est}")
        if est > threshold and repacks < max_repacks:
            messages = repack_messages(
                messages,
                user_text=user_text,
                traces=traces,
                provider=provider,
                mode=pack_mode,
                session_id=session_id,
            )
            repacks += 1
            est2 = _estimate_tokens(messages)
            traces.append(f"repack#{repacks}: {est}→{est2} tok (budget~{budget})")
            _emit_status(
                on_status,
                session_id,
                phase="repack",
                detail=f"repack #{repacks}: {est}→{est2} tok",
                round=rnd,
                last_tool=last_tool,
            )
            print(
                dim(f"  ↻ auto-repack #{repacks}  est {est}→{est2} / ~{budget}  ({provider})"),
                flush=True,
            )

        if est > threshold and repacks >= max_repacks:
            # Real budget stop: context exhausted and repacks used up.
            _mail(phase="budget_stop", detail=f"est {est} after {repacks} repack(s)")
            return (
                "**Stopped:** context budget exhausted "
                f"(est {est} > ~{threshold} tokens after {repacks} repack(s)). "
                "This is the real budget — /pack and continue with a narrower goal.",
                messages,
                traces,
            )

        res = _chat_with_heartbeat(
            provider=provider,
            messages=messages,
            model=model,
            on_stream=on_stream,
            on_status=on_status,
            session_id=session_id,
            rnd=rnd,
            last_tool=last_tool,
            tier=tier,
            max_tokens=2048,
        )
        if not res.get("ok"):
            err = res.get("error") or "model call failed"
            traces.append(f"error: {err}")
            err_l = err.lower()
            # Context / length / tool-chain poison → repack once and retry same round slot
            needs_repack = any(
                k in err_l
                for k in (
                    "context",
                    "maximum context",
                    "too long",
                    "token",
                    "length",
                    "tool_calls",
                    "tool call",
                )
            )
            if needs_repack and repacks < max_repacks:
                safe_write_receipt(
                    ROOT,
                    assess_context(
                        estimated_tokens=est,
                        context_window=provider_context_tokens(provider),
                        repack_ratio=ratio,
                        tool_schema_reserve=_TOOL_SCHEMA_RESERVE,
                        reply_reserve=_REPLY_RESERVE,
                        reason="provider_context_error",
                        provider=provider,
                        session_id=session_id or "",
                        repacks=repacks,
                        max_repacks=max_repacks,
                    ),
                )
                messages = repack_messages(
                    messages,
                    user_text=user_text,
                    traces=traces,
                    provider=provider,
                    mode=pack_mode,
                    session_id=session_id,
                )
                repacks += 1
                traces.append(f"repack_on_error#{repacks}: {err[:80]}")
                print(
                    dim(f"  ↻ repack after error #{repacks}: {err[:60]}"),
                    flush=True,
                )
                continue
            timeout_like = any(
                k in err_l
                for k in (
                    "timeout",
                    "timed out",
                    "idle timeout",
                    "no response",
                    "session file changed while embedded prompt lock was released",
                )
            )
            if timeout_like:
                safe_write_receipt(
                    ROOT,
                    {
                        **assess_context(
                            estimated_tokens=est,
                            context_window=provider_context_tokens(provider),
                            repack_ratio=ratio,
                            tool_schema_reserve=_TOOL_SCHEMA_RESERVE,
                            reply_reserve=_REPLY_RESERVE,
                            reason="provider_timeout_or_takeover",
                            provider=provider,
                            session_id=session_id or "",
                            repacks=repacks,
                            max_repacks=max_repacks,
                        ),
                        "error_class": "session_takeover" if "session file changed" in err_l else "timeout",
                    },
                )
                if timeout_retries < 1 and repacks < max_repacks:
                    timeout_retries += 1
                    messages = repack_messages(
                        messages,
                        user_text=user_text,
                        traces=traces,
                        provider=provider,
                        mode=pack_mode,
                        session_id=session_id,
                    )
                    repacks += 1
                    traces.append(f"timeout_recovery_repack#{repacks}")
                    continue
            # Model lock-loop (ƒ"?ƒ"?… repetition garbage) -> retry the SAME
            # round slot with a hotter temperature + bigger completion budget
            # instead of returning garbage as the final answer.
            retried_ok = False
            if "degenerate" in err_l and degenerate_retries < 2:
                degenerate_retries += 1
                traces.append(f"degenerate_retry#{degenerate_retries}: {err[:70]}")
                print(
                    dim(f"  ↻ model lock-loop — retry {degenerate_retries}/2 "
                        f"(temp 0.7, tok 4096)"),
                    flush=True,
                )
                res = chat_messages(
                    provider,
                    messages,
                    tools=_schemas(),
                    model=model,
                    tier=tier,
                    max_tokens=4096,
                    temperature=0.7,
                    stream=on_stream is not None,
                    on_stream=on_stream,
                    session_id=session_id,
                )
                if res.get("ok") and not _looks_degenerate(res.get("text") or ""):
                    retried_ok = True
                else:
                    traces.append(
                        f"error: {(res.get('error') or 'degenerate again')[:100]}"
                    )
                    if degenerate_retries >= 2:
                        try:
                            from mag.operator_inbox import log_behavioral_event

                            log_behavioral_event(
                                kind="degenerate",
                                detail="model lock-loop after 2 retries",
                                phase="degenerate_escalate",
                                provider=provider,
                            )
                            from mag.decision_framework import escalate_on_loop

                            esc = escalate_on_loop(
                                goal=user_text,
                                provider=provider,
                                detail="degenerate model output",
                            )
                            traces.append(f"escalate:{esc.get('target')}")
                            if esc.get("queue_id"):
                                return (
                                    f"**Degenerate loop — escalated to {esc.get('target')}** "
                                    f"(queue `{esc.get('queue_id')}`).",
                                    messages,
                                    traces,
                                )
                        except Exception:
                            pass
                    continue
            if not retried_ok and "tool" in err_l and "tool_calls" in err_l:
                sys_m = messages[0] if messages and messages[0].get("role") == "system" else None
                messages = ([sys_m] if sys_m else []) + [
                    {"role": "user", "content": user_text}
                ]
                traces.append("history_reset: tool-chain sanitize")
            _mail(phase="agent_error", detail=str(err)[:200])
            return (
                f"**Agent error:** {err}\n\n"
                f"_Try `/pack` (manual repack) or Reset agent, then one clean goal._",
                messages,
                traces,
            )

        # T1: absorb commands that landed while the model was streaming BEFORE
        # deciding whether to run the tool chain (bounded 0.05s catch window).
        messages = _absorb_steer(messages, traces, wait_s=0.05)

        tool_calls = res.get("tool_calls") or []
        text = (res.get("text") or "").strip()
        msg = res.get("message") or {"role": "assistant", "content": text}
        # Belt-and-braces: never let a repetition loop be filed as the answer
        # (streaming path may have already echoed deltas; treat as empty so the
        # existing empty-streak self-heal path kicks in).
        if text and _looks_degenerate(text):
            text = ""
            traces.append("degenerate_text_suppressed")

        # T1 escape checkpoint: if !escape/!pause landed while the model was
        # streaming, do not execute this round's tool chain. Return the partial
        # text (if any) as the round answer; the operator can then steer.
        if _steer_interrupt.is_set() and tool_calls:
            traces.append("escape: tool chain aborted")
            print(dim("  → escape checkpoint hit - skipping this round's tool calls"), flush=True)
            return (
                (text or "**Round aborted by operator escape.**")
                + "\n\n_Type a !steer to redirect, or just send your next goal._",
                messages,
                traces,
            )

        if tool_calls:
            # Normalize assistant tool-call message for DeepSeek/OpenAI
            asst: dict[str, Any] = {
                "role": "assistant",
                "content": msg.get("content") if msg.get("content") is not None else "",
                "tool_calls": tool_calls,
            }
            messages.append(asst)
            for tc in tool_calls:
                if not isinstance(tc, dict):
                    continue
                fn = tc.get("function") or {}
                name = fn.get("name") or ""
                raw_args = fn.get("arguments") or "{}"
                try:
                    args = json.loads(raw_args) if isinstance(raw_args, str) else dict(raw_args)
                except json.JSONDecodeError:
                    args = {}
                if not isinstance(args, dict):
                    args = {}
                tc_id = tc.get("id") or f"call_{rnd}_{name}"
                arg_s = json.dumps(args, ensure_ascii=False)[:120]
                print(f"  {cyan('→')} {yellow(name)}{dim(f'({arg_s})')}", flush=True)
                _emit_status(
                    on_status,
                    session_id,
                    phase="tool",
                    detail=f"start {name}",
                    tool=name,
                    round=rnd,
                    last_tool=last_tool,
                )
                tool_t0 = time.time()
                # T1: catch commands typed while the previous tool was running
                messages = _absorb_steer(messages, traces, wait_s=0.02)
                # T1 escape checkpoint #2: !escape/!pause landed mid-loop - stop
                # executing further tools; drop the rest of this tool chain.
                if _steer_interrupt.is_set():
                    traces.append("escape: remaining tool calls skipped")
                    print(dim("  → escape checkpoint hit - skipping remaining tool calls"), flush=True)
                    break
                # preflight-flat (2026-09-22): models sometimes nest the real
                # write_file payload one level deep ({"file": {path, content}},
                # {"path": {path, content}}, {"write_file": {...}}). Unwrap once
                # so preflight AND exec see flat args — 76/100 recent
                # failure-tail rows were this shape bouncing at preflight.
                if name == "write_file" and isinstance(args, dict):
                    if isinstance(args.get("path"), dict) and (args["path"].get("path") or args["path"].get("content") is not None):
                        inner = dict(args["path"])
                        args = {k: v for k, v in args.items() if k != "path"}
                        args.update(inner)
                    elif not args.get("path"):
                        for _v in list(args.values()):
                            if isinstance(_v, dict) and (_v.get("path") or _v.get("content") is not None):
                                args = dict(_v)
                                break
                pre_ok, pre_reason = _preflight_tool(name, args, session_id=session_id)
                if _steer_interrupt.is_set():
                    # escape landed between preflight and exec - bail now
                    traces.append("escape: preflight abort")
                    break
                if not pre_ok:
                    out = {"ok": False, "error": f"preflight: {pre_reason}"}
                    traces.append(f"{name}: preflight-blocked")
                    try:
                        from mag.operator_inbox import log_behavioral_event

                        log_behavioral_event(
                            kind="tool_fail",
                            detail=pre_reason[:200],
                            tool=name,
                            error="preflight-blocked",
                            phase=str(_activity.get("phase") or "tool"),
                            **normalize_seat(load_run()),
                        )
                    except Exception:
                        pass
                else:
                    if on_status:
                        out = _run_tool_with_heartbeat(
                            name,
                            args,
                            on_status=on_status,
                            session_id=session_id,
                            rnd=rnd,
                            last_tool=last_tool,
                        )
                    else:
                        out = _run_tool(name, args)
                    if not out.get("ok"):
                        err_msg = str(out.get("error") or "tool failed")[:200]
                        traces.append(f"{name}: failed")
                        try:
                            from mag.operator_inbox import log_behavioral_event

                            log_behavioral_event(
                                kind="tool_fail",
                                detail=err_msg,
                                tool=name,
                                error=err_msg,
                                phase=str(_activity.get("phase") or "tool"),
                                **normalize_seat(load_run()),
                            )
                        except Exception:
                            pass
                tool_dur = time.time() - tool_t0
                detail = f"done {name} ({tool_dur:.1f}s)"
                if tool_dur > _TOOL_SLOW_S:
                    detail += " — slow tool; Shell tab for long loops"
                last_tool = name
                _emit_status(
                    on_status,
                    session_id,
                    phase="tool",
                    detail=detail,
                    tool=name,
                    round=rnd,
                    last_tool=last_tool,
                    elapsed_ms=int(tool_dur * 1000),
                )
                # T1 pause gate INSIDE the tool loop: if the operator typed
                # !pause/!escape while a tool was executing, freeze here and
                # wait for !continue (or absorb any steer that landed too).
                while _paused.is_set():
                    time.sleep(0.3)
                    for cmd in _drain_steer():
                        steer_text = _handle_steer_cmd(cmd)
                        if steer_text:
                            messages = apply_steer(messages, steer_text)
                            traces.append(f"steer:{steer_text[:30]}")
                            print(dim(f"  → operator steer absorbed: {steer_text[:60]}"), flush=True)
                        elif cmd.strip().lower() in ("!continue", "!c"):
                            _paused.clear()
                            print(dim("  → resumed (Human Nod)"), flush=True)
                # Layer 3: collapse detector - 5 identical calls in a row
                sig = f"{name}:{json.dumps(args, ensure_ascii=False, sort_keys=True)[:80]}"
                collapse_window.append(sig)
                if len(collapse_window) == 5 and len(set(collapse_window)) == 1:
                    if collapse_nudges < 2:
                        collapse_nudges += 1
                        collapse_window.clear()
                        traces.append(f"collapse_detected#{collapse_nudges}")
                        try:
                            from mag.operator_inbox import log_behavioral_event

                            log_behavioral_event(
                                kind="collapse",
                                detail=f"5x identical {name} calls",
                                tool=name,
                                phase="collapse_nudge",
                                **normalize_seat(load_run()),
                            )
                        except Exception:
                            pass
                        print(dim("  \u2192 collapse detector: 5 identical tool calls - injecting nudge"), flush=True)
                        rem = remedy.prevent(name, json.dumps(args, default=str)[:200])
                        rem_txt = ("\n\nRemedy card:\n" + remedy.card_md(rem)) if rem else ""
                        try:
                            from mag.failure_kb import format_block, lookup

                            fkb = lookup(name, json.dumps(args, default=str)[:120])
                            fkb_txt = ("\n\n" + format_block(fkb)) if fkb else ""
                        except Exception:
                            fkb_txt = ""
                        messages.append(
                            {
                                "role": "user",
                                "content": (
                                    "[COLLAPSE DETECTOR] You called the exact same tool with the same "
                                    "arguments 5 times in a row. Stop. Re-anchor:\n\n"
                                    + build_compass(reason="loop")
                                    + rem_txt
                                    + fkb_txt
                                ),
                            }
                        )
                    else:
                        collapse_window.clear()
                        traces.append("collapse_stop")
                        _mail(phase="collapse_stop", step=_activity["step"], last_tool=_activity["last_tool"])
                        print(dim("  → collapse detector: escalating to smarter seat"), flush=True)
                        try:
                            from mag.decision_framework import escalate_on_loop

                            esc = escalate_on_loop(
                                goal=user_text,
                                provider=provider,
                                tool=name,
                                detail=f"5x identical {name}",
                                session_id=str(normalize_seat(load_run()).get("session_id") or ""),
                            )
                            traces.append(f"escalate:{esc.get('target')}")
                            if esc.get("action") == "file_for_grok":
                                return (
                                    "**Loop detected — escalated to Grok TUI (pack).**\n\n"
                                    f"{esc.get('hint', '')}\n\n"
                                    "_Local seat stopped burning tokens._",
                                    messages,
                                    traces,
                                )
                            if esc.get("queue_id"):
                                return (
                                    f"**Loop detected — escalated to {esc.get('target')}** "
                                    f"(queue `{esc.get('queue_id')}`).\n\n"
                                    f"{esc.get('hint', '')}\n\n"
                                    "_Reset agent or check orchestrator drain._",
                                    messages,
                                    traces,
                                )
                        except Exception as exc:
                            traces.append(f"escalate_failed:{str(exc)[:60]}")
                        return (
                            "**Stopped: collapse detector.** The same tool call repeated 5x twice "
                            "despite nudges - degenerate loop. Reset or /pack and re-state the goal.",
                            messages,
                            traces,
                        )
                payload = json.dumps(out, default=str)[:TOOL_RESULT_CHARS]
                traces.append(f"{name}: ok={out.get('ok')}")
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc_id,
                        "content": payload,
                    }
                )
            post_tool_est = _estimate_tokens(messages)
            if post_tool_est > threshold:
                safe_write_receipt(
                    ROOT,
                    assess_context(
                        estimated_tokens=post_tool_est,
                        context_window=provider_context_tokens(provider),
                        repack_ratio=ratio,
                        tool_schema_reserve=_TOOL_SCHEMA_RESERVE,
                        reply_reserve=_REPLY_RESERVE,
                        reason="post_tool_admission",
                        provider=provider,
                        session_id=session_id or "",
                        repacks=repacks,
                        max_repacks=max_repacks,
                    ),
                )
            _activity["step"] = rnd
            _activity["last_tool"] = name
            _activity["phase"] = "working"
            _maybe_status(rnd, name)
            if name in _MUTATING_TOOLS and out.get("ok"):
                turn_mutated = True
            # T1 escape checkpoint #3: operator escape fired mid-tool-loop - end
            # the round cleanly instead of starting another model round. The
            # partial tool chain is sanitized away next turn by _sanitize_messages.
            messages = _absorb_steer(messages, traces, wait_s=0.02)
            if _steer_interrupt.is_set():
                traces.append("escape: round ended after tool loop")
                print(dim("  → escape checkpoint hit - round ended"), flush=True)
                return (
                    "**Round aborted by operator escape.** The tool chain was stopped "
                    "mid-execution; partial results were discarded. Type a `!steer` to "
                    "redirect, or send your next goal.",
                    messages,
                    traces,
                )
            continue

        # Final text — normal end of the turn
        if text:
            _activity["phase"] = "answered"
            _mail(phase="answered")
            messages.append({"role": "assistant", "content": text})
            # False-success guard: claimed file edits but no mutating tool ran →
            # log + escalate (a seat that lies about edits bypasses collapse logic).
            if not turn_mutated and _claims_edit(text):
                esc = _escalate_fake_success(
                    text=text, provider=provider, goal=user_text, session_id=session_id
                )
                if esc:
                    traces.append(f"fake_success_escalate:{esc.get('target')}")
                    return (
                        f"**False-success guard — escalated to {esc.get('target')}** "
                        f"(queue `{esc.get('queue_id')}`). The seat claimed edits but ran no "
                        f"mutating tool; the smarter tier is taking over.\n\n{esc.get('hint', '')}",
                        messages,
                        traces,
                    )
            return text, messages, traces

        # Empty text with no tool calls: usually a crash artifact. Self-heal:
        # streak 1 dumps the pre-turn context (memdump) + auto-repacks to a lean
        # system-pack + residual (the crash signal usually means degraded context),
        # streak 2 demands a real tool call, streak 3 hard-stops.
        empty_streak += 1
        if empty_streak == 1:
            traces.append(f"empty_reroute#{empty_streak}")
            print(dim(f"  → empty model response — memdump + repack {empty_streak}/3"), flush=True)
            try:
                ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
                dump_dir = ROOT / "memory" / "runs" / f"{ts}_empty_recovery"
                dump_dir.mkdir(parents=True, exist_ok=True)
                (dump_dir / "pre_turn_messages.json").write_text(
                    json.dumps(messages, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
                )
                (dump_dir / "traces.txt").write_text("\n".join(traces[-24:]), encoding="utf-8")
                traces.append(f"empty_memdump:{dump_dir.name}")
                print(dim(f"    memdump → {dump_dir.name}"), flush=True)
            except Exception as exc:
                traces.append(f"empty_memdump_failed:{str(exc)[:80]}")
            messages = repack_messages(
                messages,
                user_text=user_text,
                traces=traces,
                provider=provider,
                session_id=session_id,
            )
            traces.append("empty_repack")
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "(Your previous reply was empty — context was auto-repacked to recover. "
                        "Re-anchor to the active blueprint/goal and pick the NEXT concrete step.\n\n"
                        + build_compass(reason="empty")
                    ),
                }
            )
            continue
        if empty_streak == 2:
            traces.append(f"empty_reroute#{empty_streak}")
            print(dim(f"  → empty model response — reroute {empty_streak}/3"), flush=True)
            messages.append({"role": "assistant", "content": ""})
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "(Your previous reply was empty again.) You MUST call a real tool now "
                        "to make progress on the active blueprint/goal.\n\n" + build_compass(reason="empty")
                    ),
                }
            )
            continue
        traces.append("empty_hardstop")
        _mail(phase="empty_stop")
        print(dim("  → empty model response x3 — stopping"), flush=True)
        messages.append({"role": "assistant", "content": ""})
        return "Stopped: 3 consecutive empty model responses", messages, traces


def load_run() -> dict[str, str]:
    """Resolve the active run identity (session/provider/model) for event logs.

    Reads MAG_AGENT_SESSION / MAG_PROVIDER / MAG_MODEL env overrides, falling
    back to the last persisted seat session on disk so behavioral events and
    /save entries are attributable even when the env is not set.
    """
    session_id = (os.environ.get("MAG_AGENT_SESSION") or "cli").strip() or "cli"
    provider = (os.environ.get("MAG_PROVIDER") or "").strip() or None
    model = (os.environ.get("MAG_MODEL") or "").strip() or None
    if not provider:
        try:
            data = load_session(session_id)
            provider = data.get("provider") or "deepseek"
            model = data.get("model") or model
        except Exception:
            provider = "deepseek"
    return {"session_id": session_id, "provider": provider, "model": model}


def normalize_seat(identity: dict[str, str] | None) -> dict[str, str]:
    """Coerce a run-identity dict into the canonical {session_id, provider, model} shape."""
    identity = identity or {}
    session_id = str(identity.get("session_id") or "cli").strip() or "cli"
    provider = str(identity.get("provider") or "").strip() or "deepseek"
    model = str(identity.get("model") or "").strip() or None
    return {"session_id": session_id, "provider": provider, "model": model}


def save_last(text: str) -> Path:
    path = ROOT / "memory" / "working.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    block = f"\n\n## Agent save ({ts})\n\n{text.strip()}\n"
    prev = path.read_text(encoding="utf-8") if path.is_file() else "# Working board\n"
    path.write_text(prev + block, encoding="utf-8")
    return path


def _resolve_user_path(raw: str) -> Path:
    p = Path(raw.strip().strip('"').strip("'"))
    if not p.is_absolute():
        p = (ROOT / p).resolve()
    return p


def read_paste_block() -> str:
    """Multi-line paste until /end or EOF. Blank lines are kept (for code)."""
    print(
        dim("paste mode — Ctrl+V your block, then a line with only ")
        + yellow("/end"),
        flush=True,
    )
    lines: list[str] = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line.strip().lower() in ("/end", "/eof", "```"):
            break
        lines.append(line)
    body = "\n".join(lines).strip()
    print(dim(f"  captured {len(body)} chars, {len(lines)} lines"), flush=True)
    return body


def attach_file(path_str: str) -> str:
    p = _resolve_user_path(path_str)
    if not p.is_file():
        return f"(attach failed: not a file: {p})"
    # images: metadata only
    suf = p.suffix.lower()
    if suf in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}:
        size = p.stat().st_size
        extra = ""
        try:
            from PIL import Image

            with Image.open(p) as im:
                extra = f", {im.size[0]}x{im.size[1]} {im.mode}"
        except Exception:
            pass
        return (
            f"[Image attachment — vision not enabled on this seat]\n"
            f"path: {p}\nsize: {size} bytes{extra}\n"
            f"Tell the operator I cannot see pixels; they can describe or use a vision model later."
        )
    try:
        text = p.read_text(encoding="utf-8", errors="replace")[:ATTACH_TEXT_CHARS]
    except Exception as e:
        return f"(attach failed: {e})"
    return f"[Attached file: {p}]\n```\n{text}\n```"


def read_user_input() -> str | None:
    """
    Returns user message text, or None for handled meta-commands that need
    special handling outside (quit/pack handled by caller via prefixes).
    Actually returns the line or multi-line content; caller handles /cmds.
    """
    try:
        line = input(green("mag") + dim("> "))
    except (EOFError, KeyboardInterrupt):
        raise
    return line


# --- B1-B5 Steering mechanism (sovereign steering engine) -------------------
# While the model is thinking, the operator can type `!steer <context>`,
# `!pause`, `!continue` on stdin without killing the job (B1 listener thread).
# run_turn drains the queue between tool rounds (B2/B3) and injects the steer
# text before the next model call. B4 status line + B5 governor seam below.

_STEER_QUEUE: "queue.Queue[str]" = queue.Queue()
_steer_listener_active = False
_pending_steer: str | None = None  # prompt-level !steer queued for the next turn


def push_steer(cmd: str) -> bool:
    """Public seam: push a steer command into the live turn's queue.

    Used by the dashboard steer channel (POST /api/v1/agent/steer) so the
    operator can steer from the UI, not just the REPL. The running run_turn
    drains this queue at its next checkpoint (T1 _absorb_steer gates) and
    acts on it exactly like a typed !steer/!pause/!continue/!escape.
    Returns True if queued, False if empty.
    """
    cmd = (cmd or "").strip()
    if not cmd:
        return False
    _STEER_QUEUE.put(cmd)
    return True
_steer_listener_lock = threading.Lock()
_paused = threading.Event()  # B3: !pause blocks between rounds; !continue clears
_steer_interrupt = threading.Event()  # T1: set when !pause/!escape arrives mid-round
_steer_active = threading.Event()  # B1 gate: listener reads stdin ONLY mid-turn

# --- Pigeonhole: knot mailbox for scheduled sub-agents (MAG_TASK_ID) --------
# When run by the orchestrator, stdin is DEVNULL so the mycelial mailbox under
# memory/mail/<task_id>/ is the live channel: inbox carries !steer/!pause/
# !continue, heartbeat beads + status.json tell the supervisor we are alive and
# what phase we are in. No task id -> all calls no-op (interactive REPL).
_TASK_ID = os.environ.get("MAG_TASK_ID", "").strip()
_activity: dict[str, Any] = {"step": 0, "last_tool": "-", "phase": "starting"}

# In-memory live turn state for dashboard polling (session_id -> snapshot).
_LIVE_TURNS: dict[str, dict[str, Any]] = {}
_LIVE_LOCK = threading.Lock()
_TOOL_SLOW_S = 30  # run-worth hint when a single tool exceeds this
_DESK_MAX_ROUNDS = 8  # dashboard desk-deepseek: strict — prevents API/network burn


def _run_tool_with_heartbeat(
    name: str,
    args: dict[str, Any],
    *,
    on_status,
    session_id: str | None,
    rnd: int,
    last_tool: str,
) -> dict[str, Any]:
    """Run tool with periodic SSE heartbeats so long shell/search does not look dead.

    Note (2026-08-16): tools are ALREADY hard-bounded at BACKEND_TIMEOUT (300s) by
    _run_tool_http's httpx.Client(timeout=BACKEND_TIMEOUT) -> every tool call is a backend
    HTTP request that cannot block forever. The heartbeats keep legitimate long tools looking
    alive; the httpx timeout is the real bound. (An earlier ThreadPoolExecutor belt was added
    then removed: Python threads can't be killed, so it couldn't enforce a tight bound, and the
    300s httpx timeout already does — over-engineering on the sovereign tool path.)
    """
    tool_t0 = time.time()
    stop = threading.Event()

    def _beat() -> None:
        while not stop.wait(5.0):
            elapsed = time.time() - tool_t0
            _emit_status(
                on_status,
                session_id,
                kind="heartbeat",
                phase="tool",
                detail=f"running {name}… ({elapsed:.0f}s)",
                tool=name,
                round=rnd,
                last_tool=last_tool,
                idle_s=int(elapsed),
            )

    hb = threading.Thread(target=_beat, name=f"tool-hb-{name}", daemon=True)
    hb.start()
    try:
        return _run_tool(name, args)
    finally:
        stop.set()


def _emit_status(
    on_status,
    session_id: str | None,
    *,
    kind: str = "status",
    **fields: Any,
) -> None:
    """Fire dashboard status/heartbeat callback + update live turn snapshot."""
    payload: dict[str, Any] = {"type": kind, **{k: v for k, v in fields.items() if v is not None}}
    if session_id:
        with _LIVE_LOCK:
            live = _LIVE_TURNS.setdefault(
                session_id,
                {"session_id": session_id, "started": time.time()},
            )
            live.update({k: v for k, v in fields.items() if k != "type"})
            live["type"] = kind
            live["updated"] = time.time()
    if on_status:
        try:
            on_status(payload)
        except Exception:
            pass


def get_live_turn(session_id: str) -> dict[str, Any]:
    """Polling fallback: last known turn phase for a dashboard session."""
    sid = (session_id or "").strip() or "dashboard"
    with _LIVE_LOCK:
        live = _LIVE_TURNS.get(sid)
        if not live:
            return {"ok": True, "session_id": sid, "active": False}
        out = dict(live)
    out["ok"] = True
    out["active"] = True
    out["idle_s"] = int(time.time() - float(out.get("updated") or out.get("started") or time.time()))
    return out


def _clear_live_turn(session_id: str | None) -> None:
    if not session_id:
        return
    with _LIVE_LOCK:
        _LIVE_TURNS.pop(session_id, None)


def _chat_with_heartbeat(
    *,
    provider: str,
    messages: list[dict[str, Any]],
    model: str | None,
    on_stream,
    on_status,
    session_id: str | None,
    rnd: int,
    last_tool: str,
    tier: str = "T1",
    **chat_kw: Any,
) -> dict[str, Any]:
    """Model call with periodic heartbeat while waiting on the provider."""
    t0 = time.time()
    stop = threading.Event()

    def _beat() -> None:
        while not stop.wait(5.0):
            idle_s = int(time.time() - t0)
            _emit_status(
                on_status,
                session_id,
                kind="heartbeat",
                phase="model",
                detail="waiting on provider…",
                round=rnd,
                last_tool=last_tool,
                idle_s=idle_s,
                elapsed_ms=int((time.time() - t0) * 1000),
            )

    _emit_status(
        on_status,
        session_id,
        phase="model",
        detail="calling provider",
        round=rnd,
        last_tool=last_tool,
        elapsed_ms=0,
    )
    hb = threading.Thread(target=_beat, name="agent-model-heartbeat", daemon=True)
    hb.start()
    try:
        return chat_messages(
            provider,
            messages,
            tools=_schemas(),
            model=model,
            tier=tier,
            stream=on_stream is not None,
            on_stream=on_stream,
            session_id=session_id,
            **chat_kw,
        )
    finally:
        stop.set()


def _ph() -> Any:
    try:
        from mag import pigeonhole as ph
        return ph
    except Exception:
        return None


def _mail(**kw: Any) -> None:
    if not _TASK_ID:
        return
    ph = _ph()
    if ph is None:
        return
    try:
        ph.write_status(_TASK_ID, **_activity, **kw)
    except Exception:
        pass


def _sync_current(
    *,
    goal: str = "",
    plan: list[str] | None = None,
    last_result: str = "",
    status: str = "running",
    **extra: Any,
) -> None:
    """Mirror live seat state into state/CURRENT.md (same contract as router)."""
    try:
        from audit import sync_current

        sync_current(
            {
                "status": status,
                "tier": extra.get("tier", "-"),
                "route": extra.get("route", "agent_cli"),
                "step_i": _activity.get("step", 0),
                "handoff_id": extra.get("handoff_id", "-"),
                "goal": goal or str(_activity.get("goal") or ""),
                "plan": plan or [],
                "last_result": last_result,
                "critique": extra.get("critique", ""),
                "tool_trace": extra.get("tool_trace", []),
            }
        )
    except Exception:
        pass


def _inbox_drain() -> list[str]:
    if not _TASK_ID:
        return []
    ph = _ph()
    if ph is None:
        return []
    try:
        return ph.drain_inbox(_TASK_ID)
    except Exception:
        return []


def _start_steer_listener() -> None:
    """B1: spawn one daemon thread that reads stdin while a turn runs."""
    global _steer_listener_active
    with _steer_listener_lock:
        if _steer_listener_active:
            return
        _steer_listener_active = True

    def _listen() -> None:
        global _steer_listener_active
        buf = ""
        last_space_t = 0.0  # double-tap space -> pause
        try:
            while True:
                if not _steer_active.is_set():
                    time.sleep(0.05)
                    continue
                # Knot channel: supervisor commands land in the mailbox even
                # when stdin is DEVNULL (scheduled sub-agent). Same queue as
                # keyboard input, so !steer/!pause/!continue behave identically.
                try:
                    for cmd in _inbox_drain():
                        _ack_cmd(cmd)
                        _STEER_QUEUE.put(cmd)
                except Exception:
                    pass
                try:
                    if os.name == "nt" and msvcrt.kbhit():
                        ch = msvcrt.getwch()
                        if ch == " ":
                            now = time.time()
                            if now - last_space_t < 0.5:
                                # double-tap space -> pause for additional input
                                _ack_cmd("!pause")
                                _STEER_QUEUE.put("!pause")
                                last_space_t = 0.0
                            else:
                                last_space_t = now
                            buf += ch
                        elif ch in ("\r", "\n"):
                            if buf.strip():
                                _ack_cmd(buf.strip())
                                _STEER_QUEUE.put(buf.strip())
                            buf = ""
                        elif ch in ("\x03", "\x1b"):
                            _ack_cmd("!escape")
                            _STEER_QUEUE.put("!escape")
                            buf = ""
                        elif ord(ch) == 8:  # backspace
                            buf = buf[:-1]
                        else:
                            buf += ch
                        continue
                    if hasattr(sys.stdin, "fileno"):
                        import select
                        r, _, _ = select.select([sys.stdin], [], [], 0.2)
                        if r:
                            line = sys.stdin.readline()
                            if not line:
                                break
                            if line.strip():
                                _ack_cmd(line.strip())
                                _STEER_QUEUE.put(line.strip())
                except (OSError, ValueError):
                    # redirected/non-console stdin: cannot poll keys - stay idle
                    time.sleep(0.2)
        finally:
            with _steer_listener_lock:
                _steer_listener_active = False

    t = threading.Thread(target=_listen, name="steer-listener", daemon=True)
    t.start()


def _start_heartbeat() -> None:
    """Pigeonhole liveness beads while a scheduled turn runs (MAG_TASK_ID only).

    The supervisor's crash recognition is heartbeat staleness, NOT timeout.
    Beads carry the latest step/last_tool so the supervisor can see live
    progress (or its absence) from the knot.
    """
    if not _TASK_ID:
        return
    ph = _ph()
    if ph is None:
        return

    def _beat() -> None:
        while True:
            time.sleep(ph.HEARTBEAT_INTERVAL_S)
            try:
                ph.heartbeat(_TASK_ID, **_activity)
            except Exception:
                pass

    threading.Thread(target=_beat, name="pigeonhole-heartbeat", daemon=True).start()


def _ack_cmd(cmd: str) -> None:
    """T1: immediate operator feedback - the seat SAW the command even if it
    only takes effect at the next checkpoint (pause gate / round start)."""
    low = cmd.strip().lower()
    if low.startswith("!steer"):
        print(dim(f"  → steer received - will inject before next model call: {cmd.strip()[6:].strip()[:50]}"), flush=True)
    elif low in ("!pause", "!p"):
        print(dim("  → !pause received - holding at next checkpoint"), flush=True)
    elif low in ("!continue", "!c"):
        print(dim("  → !continue received - resuming"), flush=True)
    elif low == "!escape":
        print(dim("  → !escape received - aborting at next checkpoint"), flush=True)


def _drain_steer() -> list[str]:
    """B2: pull all pending steer commands (non-blocking, used between rounds)."""
    out: list[str] = []
    while True:
        try:
            out.append(_STEER_QUEUE.get_nowait())
        except queue.Empty:
            break
    return out


def _auto_aim(messages: list[dict[str, Any]], traces: list[str]) -> None:
    """Phase 5: the aimbot fires proven pro-moves at the matching state,
    dropping them into the operator inbox which _absorb_operator_inbox drains
    THIS checkpoint. Guarded: only aim when the inbox is clear (no stacking)."""
    try:
        from mag.operator_inbox import status as inbox_status

        if (inbox_status().get("pending_n") or 0) > 0:
            return  # never stack guidance on top of pending guidance
        goal = ""
        for m in reversed(messages):
            if isinstance(m, dict) and m.get("role") == "user":
                c = str(m.get("content") or "")
                if not c.startswith("[OPERATOR"):
                    goal = c[:200]
                    break
        state = {"goal": goal, "phase": "checkpoint", "last_tool": traces[-1][:40] if traces else ""}
        from mag.pro_library import aim_once

        out = aim_once(state, goal=goal, limit=1, fire_moves=True)
        if out.get("fired"):
            traces.append(f"autoaim:{out['fired'][0].get('kind')}:{str(out['fired'][0].get('text', ''))[:24]}")
    except Exception:
        pass


def _absorb_steer(messages: list[dict[str, Any]], traces: list[str], wait_s: float = 0.0) -> list[dict[str, Any]]:
    """T1: process every steer command that landed, with an optional bounded
    wait (so a command typed DURING a model call / tool exec is seen before
    the next decision point). Call at EVERY decision point: after the model
    call, at the top of each tool iteration, and before the end-of-loop
    escape gate. !steer text is injected into the conversation; !pause /
    !continue / !escape set the events the gates below check. Returns the
    (possibly new) messages list — apply_steer builds a new list, so callers
    MUST rebind: messages = _absorb_steer(messages, traces, wait_s)."""
    for cmd in _drain_steer_until(time.time() + wait_s):
        steer_text = _handle_steer_cmd(cmd)
        if steer_text:
            messages = apply_steer(messages, steer_text)
            traces.append(f"steer:{steer_text[:30]}")
            print(dim(f"  → operator steer absorbed: {steer_text[:60]}"), flush=True)
        elif cmd.strip().lower() in ("!continue", "!c"):
            _paused.clear()
            print(dim("  → resumed (Human Nod)"), flush=True)
        # !pause/!escape already set their events inside _handle_steer_cmd
    _auto_aim(messages, traces)  # Phase 5: aimbot drops proven moves → inbox
    messages = _absorb_operator_inbox(messages, traces)
    return messages


def _absorb_operator_inbox(messages: list[dict[str, Any]], traces: list[str]) -> list[dict[str, Any]]:
    """Drain deferred operator guidance queued from the dashboard inbox dock."""
    try:
        from mag.operator_inbox import apply_actions_to_messages, drain_pending_at_checkpoint

        task = ""
        for m in reversed(messages):
            if isinstance(m, dict) and m.get("role") == "user":
                c = str(m.get("content") or "")
                if not c.startswith("[OPERATOR"):
                    task = c[:200]
                    break
        actions = drain_pending_at_checkpoint(task_hint=task)
        if not actions:
            return messages
        for a in actions:
            tag = a.get("action", "?")
            traces.append(f"inbox:{tag}:{str(a.get('text', ''))[:24]}")
            print(
                dim(f"  → operator inbox @ checkpoint ({tag}): {str(a.get('text', ''))[:60]}"),
                flush=True,
            )
        return apply_actions_to_messages(messages, actions)
    except Exception as e:
        traces.append(f"inbox_err:{str(e)[:40]}")
        return messages


def _handle_steer_cmd(cmd: str) -> str | None:
    """Act on one steer command. Returns steer text to inject, or None if the
    command was purely control.

    T1 fix: !pause/!escape act IMMEDIATELY (ack printed + _paused/_steer_interrupt
    set) so the operator sees the seat respond mid-round instead of watching it
    "chug away". Bounded !steer (ignores junk after the command).
    """
    low = cmd.strip().lower()
    if low.startswith("!steer"):
        raw_ctx = cmd.strip()[6:].strip()
        steer_id = ""
        if raw_ctx.startswith("[sid:"):
            end = raw_ctx.find("]")
            if end > 5:
                steer_id = raw_ctx[5:end].strip()
                raw_ctx = raw_ctx[end + 1 :].strip()
        ctx = raw_ctx
        if len(ctx) > 600:
            ctx = ctx[:600]
        if steer_id and _TASK_ID:
            ph = _ph()
            if ph is not None:
                try:
                    ph.ack_steer(_TASK_ID, steer_id, status="applied", phase=str(_activity.get("phase") or "model"))
                except Exception:
                    pass
        return ctx or "resume the active Blueprint from the interruption point"
    if low in ("!pause", "!p"):
        _paused.set()  # HOLD: pause gate (in-tool-loop + between rounds) waits for !continue
        try:
            from mag.operator_mode import set_paused
            set_paused(reason="agent CLI steer pause", requested_by="agent_cli")
        except Exception:
            pass
        return None
    if low in ("!continue", "!c"):
        _paused.clear()
        _steer_interrupt.clear()
        try:
            from mag.operator_mode import resume
            resume(requested_by="agent_cli")
        except Exception:
            pass
        return None
    if low == "!escape":
        _steer_interrupt.set()
        return None
    if low.startswith("!remedy") or low.startswith("!r "):
        kw = cmd.strip()[8:].strip() if low.startswith("!remedy") else cmd.strip()[3:].strip()
        if not kw:
            print(dim("  !remedy needs a keyword: !remedy <err text> (cards: memory/remedies/)"), flush=True)
            return None
        card = remedy.lookup(kw)
        if card:
            return "Pull the remedy card now, then fix: " + remedy.card_md(card)
        print(dim(f"  (no remedy for '{kw}' - add a card at memory/remedies/rem-<name>.md)"), flush=True)
        return None
    return None  # unknown !cmd ignored


def apply_steer(messages: list[dict[str, Any]], steer_text: str) -> list[dict[str, Any]]:
    """B5 governor seam: inject the operator steer as a user message so the
    model absorbs it before its next tool round. The Governor replaces this
    function later; nothing else in the loop changes."""
    record_decision("steer", steer_text, "mid-turn steering override")
    return messages + [
        {"role": "user", "content": f"[OPERATOR STEER] {steer_text}\nAdjust the active plan and continue from the interruption point."}
    ]


def _maybe_status(step: int, last_tool: str) -> None:
    """B4: dim status line on tty only."""
    if not sys.stdin.isatty():
        return
    try:
        print(dim(f"  [Mag] step {step} · {last_tool} · type !steer to redirect"), flush=True)
    except Exception:
        pass


def _log_seat_crash(stage: str, exc: BaseException) -> None:
    """Worklist 0: append seat crash traceback; the seat survives and keeps going.

    Log path contract (B2-86, 2026-09-26): MAG_SEAT_CRASH_LOG overrides the
    sink, else the production ROOT/logs/seat_crashes.log. Cause: the path was
    a bare constant, so tests/test_seat_crash_guard.py had no way to inject
    the sink and every run appended INJECTED-* traceback blocks to the
    production log (372 of 424 "guard caught N total" blocks on bytes at fix
    time, 52 real; receipt
    watch/inbox/burn_wave_20260926/B2_86_writer_isolation_20260926.md).
    Same shape as the MAG_GAPS_LOG seam (B2-79); no env set = same path.
    """
    _mail(phase="crashed", stage=stage, error=str(exc)[:200])
    try:
        import traceback
        env_log = os.environ.get("MAG_SEAT_CRASH_LOG")
        log = Path(env_log) if env_log else ROOT / "logs" / "seat_crashes.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("a", encoding="utf-8") as fh:
            fh.write(f"\n[{datetime.now(timezone.utc).isoformat()}] stage={stage}\n")
            fh.write("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)))
        print(dim(f"  [seat-crash-guard] {stage}: {type(exc).__name__}: {str(exc)[:120]} "
                  f"(logged {log.name})"), flush=True)
    except Exception as log_err:
        # FIX 2026-09-26 (B2-408). CAUSE: the bare `except Exception: pass`
        # swallowed sink write failures (unwritable MAG_SEAT_CRASH_LOG target,
        # disk full, permissions), so a crash that was NOT logged left no
        # surface naming the loss -- the B2-358 env tripwire only says the
        # variable is SET, never that its target failed, and the guard console
        # line above names the log only on success.
        # EVIDENCE: pre-fix, pointing MAG_SEAT_CRASH_LOG at an unwritable path
        # and crashing the seat printed nothing anywhere (probe in
        # watch/inbox/burn_wave_20260926/B2_408_crash_write_surface_20260926.md).
        # FIX: the failure is recorded twice -- a loud console line naming the
        # sink and error, and the importable CRASH_LOG_FAILURES counter below
        # (census/doctor surfaces read it instead of re-deriving).
        CRASH_LOG_FAILURES["count"] += 1
        CRASH_LOG_FAILURES["last_error"] = repr(log_err)[:200]
        CRASH_LOG_FAILURES["last_sink"] = str(log)
        CRASH_LOG_FAILURES["last_stage"] = stage
        print(f"  [seat-crash-guard] CRASH LOG WRITE FAILED: stage={stage} "
              f"sink={log} error={log_err!r} -- this crash is NOT logged; "
              f"failures so far: {CRASH_LOG_FAILURES['count']}", flush=True)


CRASH_LOG_FAILURES = {"count": 0, "last_error": "", "last_sink": "",
                      "last_stage": ""}


def run_agent(
    *,
    provider: str = "deepseek",
    model: str | None = None,
    one_shot: str | None = None,
    tier: str = "T1",
    read_only: bool | None = None,
) -> int:
    _enable_windows_vt()
    # optional NO_COLOR
    global _USE_COLOR
    if os.environ.get("NO_COLOR") or os.environ.get("MAG_AGENT_NO_COLOR"):
        _USE_COLOR = False

    # Fan-out write-strip (MICKEY-17 owed chore): spawned one-shot seats come up
    # read-only unless the caller explicitly opts out (read_only=False). Env
    # MAG_READ_ONLY / MAG_READ_ONLY_STRICT resolve when the flag is absent.
    if read_only is None:
        read_only, strict_ro = read_only_from_env()
    else:
        _, strict_ro = read_only_from_env()
    if read_only:
        receipt = activate_read_only(strict=strict_ro)
        stripped_s = ", ".join(receipt["stripped_names"]) or "none"
        print(
            dim(
                f"  read-only seat: {len(receipt['stripped'])} write tool(s) stripped "
                f"from schema ({stripped_s})"
            ),
            file=sys.stderr,
            flush=True,
        )

    mode = None
    if one_shot:
        # import context pack helpers lazily but before use to avoid NameError
        from mag.context_pack import build_context_pack, infer_pack_mode

        depth = "heavy_code" if provider == "deepseek" else "simple_code"
        mode = infer_pack_mode(one_shot, depth=depth)
        pack = build_context_pack(mode=mode, goal=one_shot, max_brief=900, max_live=400)
    else:
        pack = build_context_pack(max_brief=900, max_live=400)
    pack_text = format_context_pack_text(pack, mode=mode)
    try:
        (ROOT / "memory" / "context_pack_latest.md").write_text(pack_text, encoding="utf-8")
    except Exception:
        pass

    # Restful contract: queued/orchestrator seats must be one-shot, not REPL.
    if not one_shot:
        noninteractive = os.environ.get("MAG_NONINTERACTIVE", "").strip().lower() in (
            "1",
            "true",
            "yes",
        )
        allow_repl = os.environ.get("MAG_ALLOW_REPL", "").strip().lower() in ("1", "true", "yes")
        if noninteractive:
            print(
                "MAG_NONINTERACTIVE=1 — pass --query \"goal\" (restful one-shot seat).",
                file=sys.stderr,
            )
            return 2
        if not sys.stdin.isatty() and not allow_repl:
            print(
                "stdin is not a tty — use --query for one-shot work (or MAG_ALLOW_REPL=1 for REPL).",
                file=sys.stderr,
            )
            return 2

    # Data-backed session route: default coding-agent + seed + learned principles,
    # and (for one-shot goals) right-size the model (flash vs pro) via self_drive.plan.
    from mag.session_route import preamble as _session_preamble
    _pre = _session_preamble(one_shot or "", agent_state=None, with_model=bool(one_shot))
    if model is None and one_shot and provider == "deepseek" and _pre.get("model_hint"):
        model = _pre["model_hint"]
    system = _system_prompt(pack_text, goal=one_shot or "", preamble=_pre)
    system += _read_only_notice()
    messages: list[dict[str, Any]] = [{"role": "system", "content": system}]
    last_answer = ""
    pending_attach: list[str] = []

    print_banner(provider, model, pack)
    _start_steer_listener()  # B1: non-blocking stdin listener for mid-turn steering
    _start_heartbeat()  # pigeonhole: liveness beads for scheduled sub-agents

    cli_session_id = "cli"
    try:
        # optional env override so multiple agent windows don't stomp
        cli_session_id = (os.environ.get("MAG_AGENT_SESSION") or "cli").strip() or "cli"
    except Exception:
        cli_session_id = "cli"

    def _persist_cli(*, use_llm: bool = False) -> None:
        """Write seat transcript + FILE workday bead."""
        if len(messages) <= 1:
            return
        sess = {
            "session_id": cli_session_id,
            "provider": provider,
            "model": model,
            "messages": messages,
            "last_answer": last_answer,
            "updated": datetime.now(timezone.utc).isoformat(),
        }
        save_session(sess, file_workday=False)
        res = _file_workday_best_effort(cli_session_id, use_llm=use_llm)
        if res.get("ok") and not res.get("skipped"):
            bio = res.get("bio_session_id") or res.get("session_id")
            print(dim(f"  filed workday · {bio}"), flush=True)

    def do_turn(user_text: str) -> None:
        nonlocal last_answer, messages
        global _pending_steer
        if _pending_steer:
            user_text = f"[OPERATOR STEER] {_pending_steer}\nAdjust the active plan and continue from the interruption point.\n\n{user_text}"
            record_decision("cli steer", _pending_steer, "prompt-level steer override")
            print(dim(f"  \u2192 applied queued steer: {_pending_steer[:60]}"), flush=True)
            _pending_steer = None
        if pending_attach:
            user_text = "\n\n".join(pending_attach + [user_text])
            pending_attach.clear()
            print(dim(f"  (+ {user_text.count('[Attached')} attach block(s) in prompt)"), flush=True)
        if should_compass(user_text):
            low = user_text.strip().lstrip("!").strip().lower()
            steer_ctx = None
            if low.startswith("steer"):
                steer_ctx = (user_text.strip().lstrip("!").strip()[5:].strip()
                             or "resume the active Blueprint from the interruption point")
                record_decision("cli turn", steer_ctx, "compass-injected steer")
                print(dim(f"  \u2192 compass: steer override - {steer_ctx[:70]}"), flush=True)
            else:
                print(dim("  \u2192 compass: ambiguous input - injecting anchors"), flush=True)
            user_text = (
                build_compass(steer_text=steer_ctx, reason="steer" if steer_ctx else "input")
                + "\n\n"
                + user_text
            )
        print(rule(), flush=True)

        def _on_stream(delta: str) -> None:
            print(delta, end="", flush=True)

        _steer_active.set()  # B1: enable mid-turn stdin listener
        _mail(phase="started")
        try:
            try:
                ans, messages, traces = run_turn(
                    user_text,
                    provider=provider,
                    model=model,
                    messages=messages,
                    on_stream=_on_stream,
                    tier=tier,
                    session_id=cli_session_id,
                )
            except Exception as exc:  # seat crash-guard: never die mid-turn
                _log_seat_crash("do_turn", exc)
                ans = f"**Seat recovered from crash ({type(exc).__name__}).** Re-anchor and continue the goal."
                messages.append({"role": "user", "content": "(A tool/provider crash was caught. Continue the task.)"})
                traces = ["seat-crash-guard: recovered"]
        finally:
            _steer_active.clear()
        last_answer = ans
        print(rule(), flush=True)
        print(bold(green("answer")), flush=True)  # chrome -> stderr
        _out(ans)  # Manifesto Phase 0: clean answer on stdout
        if traces:
            print(dim("tools  " + " · ".join(traces)), flush=True)
        print(rule(), flush=True)
        # Live amend residual (heuristic); LLM polish on quit
        _persist_cli(use_llm=False)

    if one_shot:
        try:
            do_turn(one_shot)
            # Orchestrator-spawned seats (MAG_TASK_ID set) skip the LLM-polished
            # workday bio: it blocks up to the provider timeout AFTER the answer
            # and stalls orchestrator/gpipes fan/collect. Heuristic persist in
            # do_turn already filed the workday bead.
            _persist_cli(use_llm=not bool(_TASK_ID))
            failed = (last_answer or "").lstrip().startswith("**Agent error:**")
            _mail(phase="failed" if failed else "done", exit_code=1 if failed else 0)
            return 1 if failed else 0
        except Exception as exc:  # one-shot crash -> nonzero exit + log
            _log_seat_crash("one_shot", exc)
            _mail(phase="crashed", stage="one_shot", error=str(exc)[:200])
            return 1

    eof_streak = 0
    while True:
        global _pending_steer
        try:
            line = read_user_input()
            eof_streak = 0
        except KeyboardInterrupt:
            print("\n" + dim("bye"), flush=True)
            _persist_cli(use_llm=True)
            return 0
        except EOFError:
            if sys.stdin.isatty():
                print("\n" + dim("bye"), flush=True)
                _persist_cli(use_llm=True)
                return 0
            # non-tty stdin closed (orchestrator/pipe/DEVNULL): pause, do not die.
            # Graceful exit only after 3 consecutive empty reads.
            eof_streak += 1
            print(dim(f"  [seat] stdin closed - pause {eof_streak}/3 (reopen stdin or send goal)"), flush=True)
            if eof_streak >= 3:
                print(dim("bye"), flush=True)
                _persist_cli(use_llm=True)
                return 0
            time.sleep(2.0)
            continue
        if line is None or not str(line).strip():
            continue
        raw = str(line)
        stripped = raw.strip()
        low = stripped.lower()

        if low in ("/quit", "/exit", "quit", "exit"):
            print(dim("bye"), flush=True)
            _persist_cli(use_llm=True)
            return 0
        # Prompt-level steering: !steer/!pause/!continue/!escape/!remedy typed
        # at the mag> prompt (not mid-turn). These are control commands, never
        # sent to the model as a goal. !steer is queued and applied to the
        # NEXT turn; !continue clears a leftover pause; !escape clears a
        # leftover interrupt.
        if low.startswith("!"):
            steer_text = _handle_steer_cmd(stripped)
            if low.startswith("!steer"):
                # queue for the next turn so the operator can steer then type a goal
                _pending_steer = steer_text or "resume the active Blueprint from the interruption point"
                print(dim(f"  \u2192 steer queued for next turn: {_pending_steer[:60]}"), flush=True)
                continue
            if low in ("!pause", "!p"):
                print(dim("  \u2192 nothing running to pause (no active turn)"), flush=True)
                continue
            if low in ("!continue", "!c"):
                _paused.clear()
                _steer_interrupt.clear()
                print(dim("  \u2192 resumed (Human Nod)"), flush=True)
                continue
            if low == "!escape":
                _steer_interrupt.clear()
                print(dim("  \u2192 cleared pending interrupt"), flush=True)
                continue
            if low.startswith("!remedy") or low.startswith("!r "):
                kw = stripped[8:].strip() if low.startswith("!remedy") else stripped[3:].strip()
                if kw:
                    card = remedy.lookup(kw)
                    if card:
                        print(dim("  \u2192 " + remedy.card_md(card)[:200]), flush=True)
                    else:
                        print(dim(f"  (no remedy for '{kw}' - add a card at memory/remedies/rem-<name>.md)"), flush=True)
                else:
                    print(dim("  !remedy needs a keyword: !remedy <err text>"), flush=True)
                continue
            # unknown !cmd: ignore silently (don't send to model)
            print(dim(f"  (unknown command: {stripped[:40]})"), flush=True)
            continue
        if low in ("/help", "/?"):
            print_help()
            continue
        if low == "/tools":
            for t in TOOL_MAP:
                print(f"  {yellow(t)}", flush=True)
            continue
        if low == "/pack":
            pack = build_context_pack(max_brief=900, max_live=400)
            pack_text = format_context_pack_text(pack)
            messages = [{"role": "system", "content": _system_prompt(pack_text)}]
            print(green("pack refreshed") + dim(f" · {_tip_line(pack)}"), flush=True)
            continue
        if low == "/save":
            if not last_answer:
                print(yellow("nothing to save yet"), flush=True)
            else:
                p = save_last(last_answer)
                print(green("saved") + dim(f" → {p}"), flush=True)
            continue
        if low == "/paste" or low.startswith("/paste "):
            # optional goal on same line: /paste then body /end, or /paste fix this:
            prefix = stripped[6:].strip()  # after /paste
            body = read_paste_block()
            if not body and not prefix:
                print(yellow("empty paste"), flush=True)
                continue
            user_text = f"{prefix}\n\n{body}".strip() if prefix else body
            do_turn(user_text)
            continue
        if low.startswith("/file "):
            path = stripped[6:].strip()
            blob = attach_file(path)
            pending_attach.append(blob)
            print(green("attached") + dim(f" {path} — send a goal next (or /paste)"), flush=True)
            continue
        if low.startswith("/img "):
            path = stripped[5:].strip()
            blob = attach_file(path)
            pending_attach.append(blob)
            print(
                green("image path noted")
                + dim(" (no vision — describe what you need)"),
                flush=True,
            )
            continue

        # Triple-quote multi-line: """ then lines until """
        if stripped in ('"""', "'''") or stripped.startswith('"""') and stripped.count('"""') == 1:
            print(dim("multi-line — end with a line containing only \"\"\""), flush=True)
            lines = [] if stripped in ('"""', "'''") else [stripped.lstrip('"').lstrip("'")]
            while True:
                try:
                    ln = input()
                except EOFError:
                    break
                if ln.strip() in ('"""', "'''"):
                    break
                lines.append(ln)
            body = "\n".join(lines).strip()
            if body:
                do_turn(body)
            continue

        do_turn(raw.rstrip("\n"))


# --- Dashboard / API (same loop, structured result) -------------------------

_SESS_DIR = ROOT / "memory" / "agent_sessions"


def _sess_path(session_id: str) -> Path:
    safe = re.sub(r"[^a-zA-Z0-9._-]+", "_", session_id)[:64] or "default"
    return _SESS_DIR / f"{safe}.json"


def load_session(session_id: str = "dashboard") -> dict[str, Any]:
    path = _sess_path(session_id)
    if not path.is_file():
        return {"session_id": session_id, "messages": [], "provider": "deepseek"}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"session_id": session_id, "messages": [], "provider": "deepseek"}


def save_session(data: dict[str, Any], *, file_workday: bool = True) -> None:
    """Persist agent seat JSON; optionally FILE into Verkle/workday residual DNA."""
    _SESS_DIR.mkdir(parents=True, exist_ok=True)
    sid = str(data.get("session_id") or "dashboard")
    path = _sess_path(sid)
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    try:
        (_SESS_DIR / "LATEST.txt").write_text(sid, encoding="utf-8")
    except Exception:
        pass
    if file_workday:
        _file_workday_best_effort(sid, use_llm=False)


def _file_workday_best_effort(local_session_id: str, *, use_llm: bool = False) -> dict[str, Any]:
    """Seat-agnostic FILE: agent chat → residual DNA + Verkle leaf (fail-open)."""
    try:
        from mag.chat_source import file_agent_session

        return file_agent_session(
            local_session_id,
            use_llm=use_llm,
            force=False,
            amend=True,
            pdf=False,
            visual=False,
        )
    except Exception as e:
        return {"ok": False, "error": str(e)[:240]}


def api_agent_reset(session_id: str = "dashboard") -> dict[str, Any]:
    path = _sess_path(session_id)
    if path.is_file():
        try:
            path.unlink()
        except OSError as e:
            return {"ok": False, "error": str(e)}
    return {"ok": True, "session_id": session_id, "reset": True}


def api_agent_turn(
    goal: str,
    *,
    provider: str = "deepseek",
    model: str | None = None,
    session_id: str = "dashboard",
    reset: bool = False,
    on_stream=None,
    on_status=None,
    tier: str | None = None,
) -> dict[str, Any]:
    """One multi-tool turn for dashboard. Continues session messages on disk.

    on_stream(delta: str) is called with each streamed text delta (if the
    provider supports streaming) so a caller can render a live window.
    """
    goal = (goal or "").strip()
    if not goal:
        return {"ok": False, "error": "empty goal"}

    # Dashboard/API turns are autonomous one-shot work.  Respect the same
    # durable operator switch as the container worker and governor; the
    # interactive CLI can still accept !continue as the operator escape hatch.
    try:
        from mag.operator_mode import pause_reason
        if (reason := pause_reason()):
            return {"ok": True, "paused": True, "session_id": session_id, "reason": reason}
    except Exception:
        pass

    if tier is None:
        try:
            from mag.router import route

            tier = str(route(goal).get("tier") or "T1")
        except Exception:
            tier = "T1"

    depth = "heavy_code" if provider == "deepseek" else "simple_code"
    act_id: str | None = None
    try:
        from mag.coordination import log_activity

        row = log_activity(
            seat=provider,
            depth=depth,
            goal=goal,
            status="running",
            actor=f"agent:{session_id}",
        )
        act_id = str(row.get("id") or "")
    except Exception:
        pass

    if reset:
        api_agent_reset(session_id)

    sess = load_session(session_id)
    if reset or not sess.get("messages"):
        from mag.context_pack import build_context_pack, infer_pack_mode

        mode = infer_pack_mode(goal, depth=depth if depth else "")
        pack = build_context_pack(mode=mode, goal=goal, max_brief=900, max_live=400)
        pack_text = format_context_pack_text(pack, mode=mode)
        try:
            (ROOT / "memory" / "context_pack_latest.md").write_text(pack_text, encoding="utf-8")
        except Exception:
            pass
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": _system_prompt(pack_text, goal=goal)}
        ]
        tip = _tip_line(pack)
    else:
        messages = list(sess.get("messages") or [])
        tip = "session-continued"
        # Desk UI seat: bloated sessions → repack before burn (82-msg sessions crash seats)
        if str(session_id).startswith("desk-") and len(messages) > 28:
            traces_pre: list[str] = []
            messages = repack_messages(
                messages,
                user_text=goal,
                traces=traces_pre,
                provider=provider,
                session_id=session_id,
            )
            tip = f"desk-auto-repack ({len(messages)} msgs after trim)"
        elif not messages or messages[0].get("role") != "system":
            from mag.context_pack import infer_pack_mode

            mode = infer_pack_mode(goal, depth=depth)
            pack = build_context_pack(mode=mode, goal=goal, max_brief=900, max_live=400)
            messages = [{"role": "system", "content": _system_prompt(format_context_pack_text(pack, mode=mode), goal=goal)}] + messages

    if on_stream is None:
        def _on_stream(delta: str) -> None:
            print(delta, end="", flush=True)
    else:
        _on_stream = on_stream

    try:
        ans, messages, traces = run_turn(
            goal,
            provider=provider,
            model=model,
            messages=messages,
            on_stream=_on_stream,
            on_status=on_status,
            session_id=session_id,
            tier=tier,
        )
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "error": str(exc),
            "session_id": session_id,
            "hint": "Reset agent if desk seat poisoned; use Local lane for meta questions.",
        }
    finally:
        _clear_live_turn(session_id)
    sess.update(
        {
            "session_id": session_id,
            "provider": provider,
            "model": model,
            "messages": messages,
            "last_answer": ans,
            "last_traces": traces,
            "updated": datetime.now(timezone.utc).isoformat(),
        }
    )
    save_session(sess, file_workday=True)
    filed: dict[str, Any] = {}
    try:
        from mag.chat_source import agent_bio_id

        # save_session already filed; surface ids for dashboard
        filed = {
            "bio_session_id": agent_bio_id(session_id),
            "workday": "filed",
        }
    except Exception:
        filed = {"workday": "unknown"}
    if act_id:
        try:
            from mag.coordination import log_activity

            log_activity(
                seat=provider,
                depth=depth,
                goal=goal,
                status="done",
                actor=f"agent:{session_id}",
                detail=(ans or "")[:200],
                activity_id=act_id,
            )
        except Exception:
            pass
    return {
        "ok": True,
        "answer": ans,
        "tools": traces,
        "provider": provider,
        "model": model,
        "session_id": session_id,
        "tip": tip,
        "n_messages": len(messages),
        "filed": filed,
        "hint": "Mag agent · tools on local disk · workday Verkle leaf on save",
    }


def main_argv(argv: list[str] | None = None) -> int:
    import argparse

    p = argparse.ArgumentParser(prog="mag agent", description="Mag tool-using agent CLI")
    p.add_argument("-q", "--query", default="", help="One-shot goal then exit")
    p.add_argument(
        "--provider",
        default="ollama",
        help="ollama (default, local) | deepseek (only frozen BUILD / T2 plan)",
    )
    p.add_argument("--model", default="", help="Override model id")
    p.add_argument("--tier", choices=("T0", "T1", "T2", "T3"), default="T1")
    p.add_argument(
        "--read-only",
        action="store_true",
        help="Strip write tools from the schema grant (fan-out write-strip).",
    )
    args = p.parse_args(argv)
    return run_agent(
        provider=(args.provider or "ollama").strip(),
        model=(args.model or "").strip() or None,
        one_shot=(args.query or "").strip() or None,
        tier=args.tier,
        read_only=True if args.read_only else None,
    )


if __name__ == "__main__":
    sys.exit(main_argv())
