"""live_report — ONE human-readable live view of the autonomous loop.

The operator said: "I still have no idea how to see anything you're doing." This is the fix:
a single always-fresh markdown (state/LIVE_REPORT.md) that consolidates the autonomous loop's
state — what's running, what's queued, what it recently generated, what's next — so the human
has exactly ONE place to look. Deterministic, $0, no LLM; files-as-truth (all state is under
memory/ and state/).

Schema: live_report.v1
CLI: python -m mag.live_report          (render to state/LIVE_REPORT.md)
     python -m mag.live_report --print  (stdout, don't write)
Wired: regenerate on governor cadence + on wake so it is never stale.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCHEMA = "live_report.v1"
OUT = ROOT / "state" / "LIVE_REPORT.md"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _recent_answers(n: int = 5) -> list[str]:
    """Most recent landed research answers (the data the cloud loop generated)."""
    out: list[str] = []
    root = ROOT / "memory" / "research_packs"
    if root.is_dir():
        files = sorted(root.glob("*.answer.*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
        for f in files[:n]:
            out.append(f"{f.name}  ({f.stat().st_size} B)")
    return out


def render() -> str:
    lines: list[str] = []
    lines.append("# LIVE REPORT — what the autonomous loop is doing right now")
    lines.append(f"\n_Generated {_now()} · schema {SCHEMA} · $0 · files-as-truth_\n")

    # Control harness (ghost's aggregate view)
    control: dict[str, Any] = {}
    try:
        from mag.ghost_control import control as ctl
        control = ctl()
    except Exception as e:
        control = {"control_error": str(e)[:120]}

    lines.append("## 1 · What ghost sees")
    try:
        from mag.operator_mode import read as read_operator_mode
        op = read_operator_mode()
        mode = op.get("effective_mode", op.get("mode"))
        detail = str(op.get("reason") or "")[:180]
        lines.append(f"- **Operator mode:** {str(mode).upper()} · {detail}")
    except Exception as e:
        lines.append(f"- **Operator mode:** unavailable ({str(e)[:100]})")
    rec = control.get("recurring") or {}
    if rec:
        lines.append(f"- **Recurring cadence:** {json.dumps(rec, default=str)[:300]}")
    pressing = control.get("pressing")
    if pressing:
        lines.append(f"- **Pressing matter:** {str(pressing)[:200]}")
    scrum = control.get("scrum") or {}
    if scrum:
        lines.append(f"- **Scrum by status:** {json.dumps(scrum.get('by_status'), default=str)}")
    tok = control.get("tokens_saved_vs_projected")
    if tok:
        lines.append(f"- **Tokens saved vs projected:** {json.dumps(tok, default=str)[:200]}")
    plat = control.get("platform_state")
    if plat:
        lines.append(f"- **Platform procs running:** {plat.get('running')}")

    # Process supervision (what's actually running)
    try:
        sp = ROOT / "memory" / "supervisor" / "state.json"
        if sp.is_file():
            st = json.loads(sp.read_text(encoding="utf-8"))
            running = [k for k, v in st.items() if v.get("status") == "running"]
            lines.append(f"\n## 2 · Supervised loops running: {running or 'none'}")
    except Exception:
        pass

    # Read-only lifecycle preflight: this observes the single-controller law
    # without starting, stopping, or probing a provider.
    try:
        from mag.live_ops_readiness import snapshot as readiness_snapshot
        readiness = readiness_snapshot()
        lines.append(
            f"\n## 2a · Lifecycle readiness: {readiness.get('lifecycle')} "
            f"· receipts={'ready' if readiness.get('ready_for_operator_action') else 'missing'}"
        )
        for warning in readiness.get("warnings") or []:
            lines.append(f"- **Warning:** {warning}")
    except Exception as e:
        lines.append(f"\n## 2a · Lifecycle readiness: unavailable ({str(e)[:80]})")

    # Queue
    try:
        from mag.orchestrator import queue_status
        qs = queue_status() or {}
        counts = qs.get("counts") or {}
        lines.append(f"\n## 3 · Queue: total={qs.get('total')}  {json.dumps(counts, default=str)}")
    except Exception as e:
        lines.append(f"\n## 3 · Queue: (unavailable {str(e)[:60]})")

    # Recently generated data (the cloud loop's output)
    lines.append("\n## 4 · Recently landed answers (cloud loop output)")
    answers = _recent_answers()
    if answers:
        for a in answers:
            lines.append(f"- {a}")
    else:
        lines.append("- none yet")

    lines.append("\n## 5 · What remains (see state/WHAT_REMAINS.md)")
    lines.append("- `state/WHAT_REMAINS.md` — consolidated what-remains (scrum + open items)")
    lines.append("- `state/START_BRIEF.md` — the wake greeting / state")

    lines.append("\n---\n_Open the Control Room dashboard at http://127.0.0.1:8765 for the interactive view._")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    text = render()
    if argv and argv[0] == "--print":
        print(text)
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size} B)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
