"""Governor - the autorun decision framework.

THE POINT (operator, 2026-08-03): the product is not a dataset, not a mirror,
not a chat app. It is a decision framework that AUTORUNS the agent - including
its coding - so the agent acts as the operator's proxy and builds the whole
thing. The X archive / seed mirror is ONE aspect: one household's soil.

This module is the framework, first working version:

    decide:  score candidate work from real sources (queue, agent_state, boot manifest)
    execute: run the task (code edits, docs, pytest) - no human in the loop
    verify:  prove it (exit codes, pytest, dry-run)
    record:  append cycle to memory/runs/governor_trail.jsonl
    loop:    --run N cycles; gates stop only on law/secrets/irreversible

Usage:
    python -m mag.governor --run 3          # autorun 3 cycles
    python -m mag.governor --dry 1          # decide + report, execute nothing
    python main.py governor --run 3         # same, wired into the CLI

Gates (G1 law / G2 secrets / G3 irreversible) are the ONLY reasons to pause
for the operator. Everything else autoruns.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# FIX (2026-08-24, "system devolved into spinning plates / real resources idle"): _run_seat()
# uses headless.PYTHON to spawn the agent seat but `headless` was NEVER imported — so every
# governor run_cycle() that found real todo work crashed with NameError: name 'headless' is not
# defined. The loop kept finding work, kept crashing, and never routed anything to the seats =
# the disconnected fuel line. This import restores the connection.
try:
    from mag import headless
except Exception:  # noqa: BLE001
    headless = None  # degrade: caller guards on headless being set

TRAIL = ROOT / "memory" / "runs" / "governor_trail.jsonl"
TRAIL.parent.mkdir(parents=True, exist_ok=True)

# items already completed idempotently this process run
_DONE: set[str] = set()

# G2: never touch these (L0 law - never read or echo .env secrets)
BANNED = ("secret", ".env", "password", "token", "api key", "credential")
# G3: irreversible / operator-only
OPERATOR_GATED = ("archive", "drop", "delete", "rm ", "irreversible", "publish")

# Provider reliability policy (deferred from working.md 2026-08-03 14:06
# incident: deepseek returned 3 empty responses -> seat guard-stop -> nothing
# done; anti-greenwash kept the todo open, but the next cycle would retry the
# SAME flaky provider). On a guard-stop, retry ONCE on a fallback provider —
# local ollama is T0-safe (nothing leaves the machine) and costs nothing.
# Override via env: QUEUE_PROVIDER / QUEUE_FALLBACK_PROVIDER.
PRIMARY_PROVIDER = os.environ.get("QUEUE_PROVIDER", "deepseek")
FALLBACK_PROVIDER = os.environ.get("QUEUE_FALLBACK_PROVIDER", "ollama")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _log(cycle: dict[str, Any]) -> None:
    with open(TRAIL, "a", encoding="utf-8") as f:
        f.write(json.dumps(cycle, ensure_ascii=False) + "\n")

# ---------------------------------------------------------------------------
# THE SPEC - the product statement the framework writes as its first artifact.
# ---------------------------------------------------------------------------
SPEC_DOC = """# Product vision - the autorun decision framework (2026-08-03)

**The point, stated once:** the product is not a dataset, not a mirror, not a chat app.
It is a **decision framework that autoruns the agent - including its coding** - so the
agent acts as your **proxy** and builds the whole thing itself.

**Who it is for:** people who want to own their digital footprint (nothing leaves the
machine; data tiers T0-T3 are law, not preference) and have an agent be their proxy -
OpenClaw-like, but for footprint owners instead of convenience renters.

**One line:** *A decision framework that autoruns your agent and its coding - your agent
is your proxy, your footprint stays yours.*

## Architecture (the loop, first version)
1. **Decide** - Governor scores candidate work from real sources: queue, agent_state next
   moves, dig leaves, boot manifest. value / (1 + cost); blocked skips.
2. **Execute** - run the task: code edits, docs, pytest. No human in the loop.
3. **Verify** - prove it: exit codes, tests, dry-run correctness.
4. **Record** - append the cycle to the trail; the trail IS the audit.
5. **Loop** - repeat until no unblocked work or an operator gate fires.

**Gates (the only reasons to pause):**
- G1 law (constitution, data tiers, residual DNA) - never violate, never route around
- G2 secrets (.env, tokens, credentials) - never read, never echo
- G3 irreversible (archive drops, deletes, publishes) - operator only

Everything else autoruns. That is the product.

## Where the seed mirror sits
The X archive / mirror_train rows are ONE aspect: one household's soil - the demo that
proves the loop on real data. They are not the product, and they never block the framework
from running. When the loop finds no unblocked work, it says so and waits - it does not
fabricate.
"""

# ---------------------------------------------------------------------------
# Candidate sources
# ---------------------------------------------------------------------------
def queue_candidates() -> list[dict[str, Any]]:
    """Unchecked [mag] lines in queue/todo.md. Operator-gated lines are skipped."""
    todo = ROOT / "queue" / "todo.md"
    out: list[dict[str, Any]] = []
    if not todo.exists():
        return out
    for line in todo.read_text(encoding="utf-8").splitlines():
        m = re.match(r"- \[ \] \[(\w+)\] (.+)", line.strip())
        if not m:
            continue
        who, text = m.group(1), m.group(2)
        low = text.lower()
        if any(b in low for b in BANNED) or any(g in low for g in OPERATOR_GATED):
            continue
        out.append({
            "id": f"queue:{len(out)}", "title": text,
            "value": 3 if who == "mag" else 1,
            "blocked": False, "who": who,
            "exec": exec_queue_task,  # dispatch to the coding seat (the live link)
        })
    return out


def agent_state_candidates() -> list[dict[str, Any]]:
    """Open (not deferred) next moves from agent_state LATEST.md."""
    p = ROOT / "memory" / "agent_state" / "LATEST.md"
    out: list[dict[str, Any]] = []
    if not p.exists():
        return out
    for line in p.read_text(encoding="utf-8").splitlines():
        m = re.match(r"\d+\.\s*\[(open|deferred)\]\s*(\w+):\s*(.+)", line.strip())
        if not m:
            continue
        out.append({
            "id": f"state:{m.group(2)}", "title": m.group(3),
            "value": 2, "blocked": m.group(1) == "deferred",
            "who": "mag", "exec": None,
        })
    return out

def boot_manifest() -> list[dict[str, Any]]:
    """First cycles: the framework building itself. One-time, idempotent."""
    return [
        {
            "id": "boot:spec",
            "title": "write docs/ref/PRODUCT_VISION_AUTORUN.md (doc)",
            "value": 2, "blocked": False, "who": "mag",
            "exec": exec_spec_doc,
        },
        {
            "id": "boot:cli",
            "title": "wire governor into main.py CLI (code)",
            "value": 3, "blocked": False, "who": "mag",
            "exec": exec_cli_wiring,
        },
        {
            "id": "boot:selftest",
            "title": "governor self-test: import + dry-run + CLI help (code)",
            "value": 3, "blocked": False, "who": "mag",
            "exec": exec_selftest,
        },
    ]


def all_candidates() -> list[dict[str, Any]]:
    return queue_candidates() + agent_state_candidates() + boot_manifest()


_inbox_hints: list[str] = []


def _refresh_inbox_hints() -> list[str]:
    global _inbox_hints
    try:
        from mag.operator_inbox import pending_hints

        _inbox_hints = pending_hints()
    except Exception:
        _inbox_hints = []
    return _inbox_hints


def score(c: dict[str, Any]) -> float:
    cost = 1.0 + (2.0 if c.get("exec") is None else 0.0)
    s = c["value"] / cost
    try:
        from mag.autorun_common import fkb_score_adjustment

        s += fkb_score_adjustment(str(c.get("title") or ""))
    except Exception:
        pass
    if _inbox_hints:
        title = str(c.get("title") or "").lower()
        for hint in _inbox_hints:
            for word in re.findall(r"[a-z0-9]{4,}", hint.lower()):
                if word in title:
                    s += 0.75
                    break
    return s

# ---------------------------------------------------------------------------
# Executors
# ---------------------------------------------------------------------------
def exec_spec_doc(c: dict[str, Any]) -> tuple[bool, str]:
    target = ROOT / "docs" / "ref" / "PRODUCT_VISION_AUTORUN.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        return True, f"exists already: {target}"
    target.write_text(SPEC_DOC, encoding="utf-8")
    return True, f"wrote {target}"


def exec_cli_wiring(c: dict[str, Any]) -> tuple[bool, str]:
    main = ROOT / "main.py"
    if not main.exists():
        return False, f"missing {main}"
    src = main.read_text(encoding="utf-8")
    if 'add_parser("governor"' in src or 'add_parser("governor",' in src \
            or 'add_parser(\n        "governor"' in src:
        return True, "already wired"
    add = '''

def cmd_governor(args):
    # Autorun the governor loop (the product).
    from mag.governor import main as governor_main
    return governor_main(["--run", str(args.run if hasattr(args, "run") else 1)])
'''
    with open(main, "a", encoding="utf-8") as f:
        f.write(add)
    return True, "appended cmd_governor to main.py (verify wiring by hand next)"

def _run_seat(text: str, provider: str) -> tuple[int, str, str]:
    """One seat dispatch: main.py agent -q <text> --provider <provider>."""
    import subprocess
    import sys as _sys

    try:
        from mag.autorun_common import refresh_context_for_goal

        refresh_context_for_goal(text)
    except Exception:
        pass

    cmd = [headless.PYTHON, str(ROOT / "main.py"), "agent", "-q", text,
           "--provider", provider]
    try:
        import os as _os
        # SELF-STEAL (2026-08-24, operator "self steal you're being retarded"): the
        # dogfood_audit "unknown provider deepseek" fix already exists — headless._spawn_env()
        # injects PYTHONPATH = project root + venv site-packages so the spawned child resolves
        # mag/config/yaml. We were spawning on the bare base interpreter with no deps. Pass the
        # fixed env (exactly what dogfood_audit regression-guards).
        _env = headless._spawn_env() if headless else None
        _flags = (getattr(subprocess, "CREATE_NO_WINDOW", 0) if _os.name == "nt" else 0)
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=1200,
                           creationflags=_flags, env=_env)
    except subprocess.TimeoutExpired:
        return -1, "seat timeout (1200s)", ""
    out = (r.stdout or "") + (r.stderr or "")
    tail = (r.stdout or "")[-300:].strip()
    return r.returncode, out, tail


def exec_queue_task(c: dict[str, Any]) -> tuple[bool, str]:
    """Dispatch a [mag] queue task to the coding seat (one-shot agent).

    THE missing link for "coding sessions happen naturally": the operator
    sensed real work in queue/todo.md but had exec=None (report-only). This
    executor hands the task text to the seat (main.py agent -q ...) and marks
    the todo line done ONLY on a clean finish: seat exit 0 AND no "Stopped:"
    guard phrase in output (anti-greenwash, proven live 2026-08-03).

    Provider policy (2026-08-03): primary = API provider (deepseek). If the
    seat guard-stops ("Stopped: 3 consecutive empty model responses" /
    "Stopped: context budget exhausted") — a provider-reliability signal, NOT
    a task failure — retry ONCE on FALLBACK_PROVIDER (local ollama, T0-safe)
    before giving up. Guard-stop on both -> todo stays unchecked, governor
    retries next cycle. Nonzero seat exits (seat-internal bugs) do NOT fall
    back — a provider change cannot fix a tool/serialization bug.
    """
    text = c["title"]
    if c.get("who") != "mag":
        return False, "not assigned to mag - skipping"
    rc, out, tail = _run_seat(text, PRIMARY_PROVIDER)
    if "Stopped:" in out:
        # Anti-greenwash (proven live 2026-08-03 14:06): the seat exits 0 even
        # on guard-stops with NO work done. Only a clean finish -- exit 0 AND
        # no "Stopped:" guard phrase -- may mark done.
        rc2, out2, tail2 = _run_seat(text, FALLBACK_PROVIDER)
        if rc2 == 0 and "Stopped:" not in out2:
            _mark_queue_done(text)
            return True, "fallback %s exit=0: %s" % (FALLBACK_PROVIDER, tail2)
        return False, ("seat guard-stop on %s AND %s (NOT marked done): %s"
                       % (PRIMARY_PROVIDER, FALLBACK_PROVIDER, tail2 or tail))
    if rc == 0:
        _mark_queue_done(text)
        return True, "seat exit=0: " + tail
    return False, "seat exit=%d: %s" % (rc, tail)


def _mark_queue_done(title: str) -> None:
    """Flip the matching unchecked [mag] line in queue/todo.md to [x]."""
    todo = ROOT / "queue" / "todo.md"
    if not todo.exists():
        return
    lines = todo.read_text(encoding="utf-8").splitlines()
    for i, ln in enumerate(lines):
        if ln.startswith("- [ ] [") and title in ln:
            lines[i] = ln.replace("- [ ]", "- [x]", 1)
            break
    todo.write_text("\n".join(lines), encoding="utf-8")


def exec_selftest(c: dict[str, Any]) -> tuple[bool, str]:
    """Idempotent: import governor, run a dry cycle, prove CLI help exists."""
    import mag.governor as g
    cands = g.all_candidates()
    ranked = sorted(cands, key=g.score, reverse=True)
    msg = f"candidates={len(cands)} top={ranked[0]['id'] if ranked else 'none'}"
    return True, "selftest ok: " + msg


# ---------------------------------------------------------------------------
# Cycle loop
# ---------------------------------------------------------------------------
def run_cycle(dry: bool = False) -> dict[str, Any]:
    start = _now()
    hints = _refresh_inbox_hints()
    cands = [c for c in all_candidates()
             if not c.get("blocked") and c["id"] not in _DONE]
    ranked = sorted(cands, key=score, reverse=True)
    if not ranked:
        out = {"ts": start, "action": "no_unblocked_work", "detail": ""}
        if hints:
            out["operator_inbox"] = hints[:3]
        return out
    pick = ranked[0]
    if dry or pick.get("exec") is None:
        ok, detail = False, "dry (no executor)"
    else:
        ok, detail = pick["exec"](pick)
        if ok and detail.startswith(("already", "exists", "wrote", "selftest ok")):
            _DONE.add(pick["id"])
    cycle = {
        "ts": start, "action": pick["id"], "title": pick["title"],
        "dry": dry or pick.get("exec") is None,
        "ok": ok, "detail": detail,
    }
    if hints:
        cycle["operator_inbox"] = hints[:3]
        try:
            from mag.compass import record_decision

            record_decision(
                "governor cycle",
                " | ".join(hints)[:200],
                f"picked {pick['id']} with inbox hint boost",
            )
        except Exception:
            pass
    _log(cycle)
    return cycle

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="governor", description="autorun decision framework")
    ap.add_argument("--run", type=int, default=1, help="number of cycles to autorun")
    ap.add_argument("--dry", type=int, default=0, help="decide + report, execute nothing")
    args = ap.parse_args(argv)
    n = args.dry if args.dry else args.run
    for _ in range(n):
        cyc = run_cycle(dry=bool(args.dry))
        print(f"[{cyc['ts']}] {cyc['action']} ok={cyc['ok']} :: {cyc['detail']}")
        if not cyc["ok"] and not cyc["dry"]:
            break
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
