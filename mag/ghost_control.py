"""ghost_control — the HUMAN-FACING control harness. Ghost is the central piece.

The whole point: ghost is the nervous system that makes every other piece VISIBLE and
USEFUL. This is the single surface the human sees — ghost's live view of the machine,
aggregated from the moving parts we built:

  scrum backlog/sprint  · press digest (pressing matter) · loop_breaker state
  token savings counter · skills available               · oh_fuck emergency status
  ghost.run_recurring    (the automatic cadence output)

One REST endpoint -> the Control Room / dashboard -> the human steers the machine through
ghost, not through scattered terminals. Deterministic, $0, no LLM.

Schema: ghost_control.v1
CLI:  python -m mag.ghost_control
REST: GET /api/v1/ghost/control
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

SCHEMA = "ghost_control.v1"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def control() -> dict[str, Any]:
    """Ghost's live view of the whole machine — the human-facing control harness."""
    out: dict[str, Any] = {"schema": SCHEMA, "ts": _now(), "ok": True, "source": "ghost"}

    # recurring cadence output (what ghost ran automatically)
    try:
        from mag.ghost import run_recurring
        out["recurring"] = run_recurring()
    except Exception as e:
        out["recurring_error"] = str(e)[:120]

    # scrum board + next sprint item
    try:
        from mag.scrum import backlog, sprint
        b = backlog()
        sp = sprint()
        out["scrum"] = {"by_status": b.get("by_status"),
                        "next": (sp.get("item") or {}).get("id"),
                        "next_title": (sp.get("item") or {}).get("title")}
    except Exception as e:
        out["scrum_error"] = str(e)[:120]

    # press digest (pressing matter)
    try:
        from mag.press_digest import digest
        d = digest()
        out["pressing"] = d.get("pressing")
    except Exception as e:
        out["press_error"] = str(e)[:120]

    # loop_breaker state (is anything crash-looping?)
    try:
        from mag.loop_breaker import detect
        out["loop_state"] = detect().get("verdict")
    except Exception as e:
        out["loop_error"] = str(e)[:120]

    # token savings counter
    try:
        from mag.ghost_grok_dashboard import saved_vs_projected
        out["tokens_saved_vs_projected"] = saved_vs_projected()
    except Exception as e:
        out["tokens_error"] = str(e)[:120]

    # skills available (one-window surface)
    try:
        from mag.skill_pipeline import SKILLS
        out["skills"] = sorted(SKILLS.keys())
    except Exception as e:
        out["skills_error"] = str(e)[:120]

    # oh_fuck emergency status (is the system safe?)
    try:
        from mag.platform_kill import scan as pk_scan
        out["platform_state"] = {"running": pk_scan().get("procs", 0),
                                 "note": "0 = quiet/safe"}
    except Exception as e:
        out["platform_error"] = str(e)[:120]

    # VISIBILITY: what ghost ran automatically (so the human can SEE it's alive).
    out["activity"] = _recent_activity()
    return out


def _recent_activity() -> dict[str, Any]:
    """Recent autonomous activity + freshness — 'you may know you're running, I do not' fix."""
    import time as _t
    act: dict[str, Any] = {}
    trail = ROOT / "memory" / "runs" / "ghost_trail.jsonl"
    if trail.is_file():
        age = round(_t.time() - trail.stat().st_mtime)
        act["ghost_last_seen_s"] = age
        act["ghost_alive"] = age < 3600
    gov = ROOT / "memory" / "runs" / "governor_autorun_trail.jsonl"
    if gov.is_file():
        act["governor_last_tick_s"] = round(_t.time() - gov.stat().st_mtime)
    press = ROOT / "memory" / "press" / "latest.json"
    if press.is_file():
        try:
            d = json.loads(press.read_text(encoding="utf-8"))
            act["press_last"] = d.get("ts", "")[:19]
        except Exception:
            pass
    # cadence job freshness from recent trails
    for name, rel in (("rightsize", "runs/rightsize_all"), ("scrum", "scrum/backlog.json"),
                      ("queue", "runs/orchestrator_trail.jsonl")):
        p = ROOT / "memory" / rel
        if p.exists():
            act[f"{name}_age_s"] = round(_t.time() - p.stat().st_mtime)
    return act


def main(argv: list[str] | None = None) -> int:
    print(json.dumps(control(), indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
