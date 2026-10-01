"""codex_seat — the OpenAI Codex CLI as a BOUNDED seat (gpt-5.6-sol, priority tier, six-day window).

WHY THIS EXISTS (2026-08-24): the operator's ChatGPT/OpenAI account has a six-day priority window,
and Codex CLI (v0.149.1, ~/.codex authenticated, gpt-5.6-sol at xhigh) is the coding agent that
rides it. This is a BOUNDED one-shot wrapper over `codex exec` so the harness can drive it like any
other seat — prompt in, output + tokens out, honest failures — and the bill stays readable from
~/.codex/sessions (seat_hunter.codex_bill already reads them).

HONESTY / CONTRACT:
  * This is a SUBSCRIPTION seat with a DEADLINE (six days), not a $0-forever channel lane. Use it
    for real coding work only — the xhigh reasoning burns ~8k tokens even for "OK".
  * `codex exec` runs in a workspace-write sandbox with approval=never: it can write files in cwd.
    Point it at a real work dir, never at anything you cannot afford to have edited.
  * Tokens are reported from the exec output line ("tokens used"); cost is not estimated (Codex
    records no per-turn invoice — the bill reader surfaces raw tokens as the grounded fact).
  * If codex is missing or unauthenticated, report that — never fabricate an answer.

Schema: codex_seat.v1 · deterministic wrapper over the Codex CLI · reuse: seat_hunter.codex_bill
CLI: python -m mag.codex_seat status | run "<prompt>" [--cwd ...] [--reasoning auto]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:  # noqa: BLE001
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "codex_seat.v1"
CODEX_HOME = Path.home() / ".codex"
MODEL = "gpt-5.6-sol"


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _codex_cmd() -> list[str] | None:
    """Resolve the REAL codex entry. On Windows `codex` is a .ps1 shim that Python's subprocess
    cannot run directly — resolve the .cmd shim or the underlying node + codex.js instead."""
    import shutil
    for name in ("codex.cmd", "codex"):
        p = shutil.which(name)
        if p:
            return [p]
    for d in os.environ.get("PATH", "").split(os.pathsep):
        d = d.strip().strip('"')
        if not d:
            continue
        shim = Path(d) / "codex.ps1"
        if shim.is_file():
            node = Path(d) / "node.exe"
            entry = Path(d) / "node_modules" / "@openai" / "codex" / "bin" / "codex.js"
            if node.is_file() and entry.is_file():
                return [str(node), str(entry)]
    return None


def _installed() -> bool:
    return _codex_cmd() is not None


def _authed() -> bool:
    return (CODEX_HOME / "auth.json").is_file()


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA, "model": MODEL, "installed": _installed(),
            "authed": _authed(),
            "window": "operator: six-day priority tier — burn on real coding work only",
            "contract": "run(prompt) -> one-shot `codex exec` (workspace-write sandbox, "
                        "approval=never); returns output + tokens; honest if codex is "
                        "missing/unauth. Tokens = grounded fact; no invoice cost (Codex)",
            "cost": "subscription (six days) — token-hungry at xhigh (~8k tokens even for 'OK')"}


def _tokens_from_output(out: str) -> int | None:
    """Extract the 'tokens used' count defensively. BUG FIX 2026-08-24: a stray comma with no
    digits (e.g. 'tokens used ,') crashed int() and threw away a completed answer — the parse
    must never kill a real result."""
    m = re.search(r"tokens used\s*[\n:]?\s*([\d,]+)", out)
    if not m:
        return None
    s = m.group(1).replace(",", "")
    if not s.isdigit():
        return None
    return int(s)


def run(prompt: str, *, cwd: str | Path | None = None, timeout: int = 600,
        reasoning: str = "auto") -> dict[str, Any]:
    """One-shot `codex exec` with the prompt, in `cwd` (default: the project root). Bounded by
    timeout. Honest: reports failure if codex is missing/unauth, or the exec errors."""
    prompt = (prompt or "").strip()
    if not prompt:
        return {"ok": False, "schema": SCHEMA, "error": "empty prompt"}
    if not _installed():
        return {"ok": False, "schema": SCHEMA, "error": "codex CLI not found on PATH",
                "hint": "npm install -g @openai/codex && codex login"}
    if not _authed():
        return {"ok": False, "schema": SCHEMA, "error": "codex not authenticated",
                "hint": "run: codex login (browser auth with the OpenAI/ChatGPT account)"}
    workdir = str(cwd) if cwd else str(ROOT)
    base = _codex_cmd()
    if not base:
        return {"ok": False, "schema": SCHEMA, "error": "codex CLI not found on PATH",
                "hint": "npm install -g @openai/codex && codex login"}
    cmd = base + ["exec", "--skip-git-repo-check"]
    if reasoning and reasoning != "auto":
        cmd += ["--reasoning-effort", reasoning]
    cmd += [prompt]
    try:
        r = subprocess.run(cmd, cwd=workdir, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
        out = (r.stdout or "") + (r.stderr or "")
    except subprocess.TimeoutExpired:
        return {"ok": False, "schema": SCHEMA, "error": f"codex exec timed out ({timeout}s)",
                "model": MODEL, "ts": _now()}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "schema": SCHEMA, "error": f"{type(e).__name__}: {str(e)[:200]}"}
    ok = r.returncode == 0 and bool((r.stdout or "").strip())
    return {"ok": ok, "schema": SCHEMA, "model": MODEL, "returncode": r.returncode,
            "output": (r.stdout or "").strip()[-2000:],
            "stderr_tail": (r.stderr or "").strip()[-300:],
            "tokens": _tokens_from_output(out),
            "reasoning": reasoning, "cwd": workdir, "ts": _now()}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(prog="codex-seat")
    ap.add_argument("cmd", nargs="?", default="status", choices=["status", "run"])
    ap.add_argument("prompt", nargs="*", default=[])
    ap.add_argument("--cwd", default="")
    ap.add_argument("--reasoning", default="auto")
    a = ap.parse_args()
    if a.cmd == "run":
        print(json.dumps(run(" ".join(a.prompt), cwd=a.cwd or None, reasoning=a.reasoning),
                         indent=2, default=str))
    else:
        print(json.dumps(status(), indent=2, default=str))
