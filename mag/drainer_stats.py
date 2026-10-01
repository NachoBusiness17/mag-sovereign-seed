"""Drainer stats — clean CLI readout of the dispatch pipeline.

One command that answers "what's the drainer doing right now?" in a terminal /
VS Code window. Pulls live state from the framework's own modules (no LLM):
drainer status, queue counts, live tasks, fleet totals, pending handoffs.

Schema: drainer_stats.v1

CLI:
  python -m mag.drainer_stats            # table readout (default)
  python -m mag.drainer_stats --json     # machine-readable

REST (dashboard/rest.py):
  GET /api/v1/drainer/stats              -> this payload as JSON

VS Code: magMap.drainerStats command opens a terminal tab running
  `python -m mag.drainer_stats`
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except ImportError:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

# Windows console default codec (cp1252) can't encode box/emoji chars — force UTF-8.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def drainer_stats() -> dict[str, Any]:
    out: dict[str, Any] = {"ok": True, "schema": "drainer_stats.v1", "ts": _now()}

    # --- drainer ---
    try:
        from mag.preferences import drainer_status, operator_status

        d = drainer_status()
        out["drainer"] = {
            "enabled": bool(d.get("enabled")),
            "autorun_allowed": bool(d.get("autorun_allowed")),
            "operator_active": bool(d.get("operator_active")),
            "env_locked": bool(d.get("env_locked")),
            "hint": d.get("hint"),
        }
        out["operator"] = operator_status()
    except Exception as e:
        out["drainer_error"] = str(e)[:200]

    # --- queue ---
    try:
        from mag.orchestrator import list_queue, queue_status

        qs = queue_status()
        out["queue"] = {"total": qs.get("total"), "counts": qs.get("counts"), "running_task_id": qs.get("running_task_id")}
        q = list_queue(limit=80)
        out["queue_items"] = [
            {
                "queue_id": i.get("queue_id"),
                "goal": (i.get("goal") or "")[:90],
                "status": i.get("status"),
                "provider": i.get("provider"),
                "tag": i.get("tag"),
            }
            for i in q
            if i.get("status") not in ("done", "failed", "killed", "timeout", "died")
        ]
    except Exception as e:
        out["queue_error"] = str(e)[:200]

    # --- fleet (live + terminal totals) ---
    try:
        from mag.orchestrator import list_tasks, TERMINAL

        tasks = list_tasks(limit=200) or []
        statuses: dict[str, int] = {}
        live = []
        for t in tasks:
            st = t.get("status") or "?"
            statuses[st] = statuses.get(st, 0) + 1
            if st not in TERMINAL:
                live.append({
                    "task_id": t.get("task_id"),
                    "goal": (t.get("goal") or "")[:80],
                    "status": st,
                    "provider": t.get("provider"),
                    "detail": (t.get("detail") or "")[:60],
                })
        out["fleet"] = {
            "total": len(tasks),
            "statuses": statuses,
            "live_n": len(live),
            "live": live[:12],
        }
    except Exception as e:
        out["fleet_error"] = str(e)[:200]

    # --- pending handoffs ---
    try:
        from mag.peer_handoff import list_peer_handoffs

        ph = list_peer_handoffs(limit=12)
        pending = [h for h in ph if h.get("status") == "filed"]
        out["pending_handoffs"] = [
            {
                "handoff_id": h.get("handoff_id"),
                "from": h.get("from_seat"),
                "to": h.get("to_seat"),
                "goal": (h.get("goal") or "")[:80],
            }
            for h in pending
        ]
        out["pending_handoffs_n"] = len(pending)
    except Exception as e:
        out["handoff_error"] = str(e)[:200]

    return out


def render_table(s: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("")
    lines.append("  ⚙️  MAG DRAINER STATS" + " " + "·" + " " + s.get("ts", "")[:19])
    lines.append("  " + "─" * 66)
    d = s.get("drainer") or {}
    lines.append(f"  drainer      : {'ON' if d.get('enabled') else 'OFF'}  (autorun={'allowed' if d.get('autorun_allowed') else 'paused'})")
    lines.append(f"  operator     : {'ACTIVE (pauses drainer)' if d.get('operator_active') else 'idle'}")
    if d.get("hint"):
        lines.append(f"  hint         : {d.get('hint')}")

    q = s.get("queue") or {}
    lines.append("")
    lines.append("  QUEUE")
    counts = q.get("counts") or {}
    if counts:
        lines.append("  " + "  ".join(f"{k}={v}" for k, v in counts.items()))
    else:
        lines.append("  (empty)")
    q_items = s.get("queue_items") or []
    for item in q_items[:10]:
        lines.append(f"    · [{item.get('status','?')}] {item.get('goal')}")
    if len(q_items) > 10:
        lines.append(f"    … +{len(q_items)-10} more")

    f = s.get("fleet") or {}
    lines.append("")
    lines.append("  FLEET")
    lines.append(f"  total={f.get('total',0)}  live={f.get('live_n',0)}  " + " ".join(f"{k}={v}" for k, v in (f.get('statuses') or {}).items()))
    for t in (f.get("live") or [])[:8]:
        lines.append(f"    ▶ [{t.get('status','?')}] {t.get('goal')}  ({t.get('provider')})")
    if not (f.get("live")):
        lines.append("    (no live tasks)")

    lines.append("")
    lines.append(f"  PENDING HANDOFFS: {s.get('pending_handoffs_n', 0)}")
    for h in (s.get("pending_handoffs") or [])[:8]:
        lines.append(f"    · {h.get('from')} → {h.get('to')}: {h.get('goal')}")
    lines.append("")
    lines.append("  " + "─" * 66)
    lines.append("  tip: `python -m mag.drainer_stats --json` for machine output")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="drainer-stats", description="Drainer / queue / fleet stats")
    ap.add_argument("--json", action="store_true", help="Machine-readable JSON output")
    args = ap.parse_args(argv)
    s = drainer_stats()
    if args.json:
        print(json.dumps(s, indent=2, default=str))
    else:
        print(render_table(s))
    return 0 if s.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
