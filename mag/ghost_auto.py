"""ghost_auto — the automatic loop: tesuji capture + sizing learning + bounded swarm dispatch.

The operator's directive (2026-08-10): "you should do this automatically in the future all of it."
The manual flow (capture tesuji shell, teach one_sizer the sizing, launch the stateless DeepSeek swarm
to mine under-mined data) becomes a CADENCE that runs without asking. Deterministic, $0, bounded
(no runaway — mirror cheap_swarm's daily cap).

  run_cadence(force)  -> auto: 1) synthesize the tesuji daily leaf  2) record the knot_mining sizing
                          3) bounded stateless dispatch for under-mined domains (untagged knot corpus).
  status()            -> recent state.

Schema: ghost_auto.v1 · deterministic · $0
CLI:  python -m mag.ghost_auto [--force]  (cadence)  |  status
"""
from __future__ import annotations

import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCHEMA = "ghost_auto.v1"
STATE_DIR = ROOT / "memory" / "runs" / "ghost_auto"
STATE = STATE_DIR / "state.json"
KNOTS = ROOT / "memory" / "biography" / "knots"
DAILY_CAP_DISPATCH = 1      # bounded: at most 1 stateless dispatch per day (no runaway)
UNTAGGED_THRESHOLD = 200    # dispatch only when the untagged shadow corpus is large


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _today() -> str:
    return date.today().isoformat()


def _load_state() -> dict[str, Any]:
    if STATE.is_file():
        try:
            d = json.loads(STATE.read_text(encoding="utf-8"))
            if isinstance(d, dict):
                return d
        except Exception:
            pass
    return {"dispatches_today": 0, "last_dispatch_day": None, "runs": 0}


def _save_state(s: dict[str, Any]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(s, indent=2), encoding="utf-8")


def _untagged_count() -> int:
    """The shadow corpus: knots whose filename theme is 'untagged' (never classified)."""
    n = 0
    if KNOTS.is_dir():
        for p in KNOTS.glob("*.knot.json"):
            if "_untagged_" in p.name:
                n += 1
    return n


def _synthesize_tesuji_leaf() -> dict[str, Any]:
    try:
        from mag.tesuji_shell import synthesize_tesuji_shell_leaf
        return synthesize_tesuji_shell_leaf()
    except Exception as e:
        return {"ok": False, "error": str(e)[:120]}


def _record_sizing() -> dict[str, Any]:
    try:
        from mag.one_sizer import record_sizing
        return record_sizing(skill="knot_mining", domain="data_mining", shape="data",
                             effective_tier="flash", model="deepseek-v4-flash", ok=True)
    except Exception as e:
        return {"ok": False, "error": str(e)[:120]}


def _dispatch_stateless(domain: str) -> dict[str, Any]:
    try:
        from mag.stateless_research import launch
        return launch(domain=domain, enqueue=True)
    except Exception as e:
        return {"ok": False, "error": str(e)[:120]}


def _record_swarm_behavior(dispatched: list[dict[str, Any]]) -> dict[str, Any]:
    """Frank-Church style: save a behavior profile for every agent the swarm dispatched, and feed
    one_sizer so rightsizing learns from real outcomes. Cheap $0, runs by default in the cadence."""
    from mag.agent_behavior import record
    n = 0
    for d in dispatched:
        if not (d and d.get("ok")):
            continue
        for a in (d.get("agents") or []):
            try:
                record(agent_id=f"stateless-{a.get('agent')}-{str(a.get('task_id') or '')[:8]}",
                       domain="data_mining", shape="data", tier="flash",
                       model="deepseek-chat", ok=bool(a.get("ok")),
                       source="ghost_auto.stateless_dispatch")
                n += 1
            except Exception:
                continue
    return {"ok": True, "recorded": n}


def run_cadence(*, force: bool = False) -> dict[str, Any]:
    """Automatic: tesuji leaf + sizing learning + bounded stateless dispatch for under-mined data."""
    s = _load_state()
    s["runs"] = s.get("runs", 0) + 1
    today = _today()

    # reset daily dispatch cap at midnight
    if s.get("last_dispatch_day") != today:
        s["dispatches_today"] = 0
        s["last_dispatch_day"] = today

    # 1) always synthesize the tesuji daily leaf (emergent wins -> repeat)
    leaf = _synthesize_tesuji_leaf()

    # 2) always record the sizing observation (teach one_sizer -> cheaper next time)
    sizing = _record_sizing()

    # 3) bounded dispatch: mine the untagged shadow corpus if it's large AND under cap
    untagged = _untagged_count()
    dispatched = []
    if untagged >= UNTAGGED_THRESHOLD and s["dispatches_today"] < DAILY_CAP_DISPATCH:
        r = _dispatch_stateless(
            "verkle knot mining: classify the untagged corpus from session content, "
            "name each dominant theme, fold provenance back to source transcripts")
        dispatched.append({"ok": r.get("ok"), "agents": (r.get("launched") or []) if r.get("ok") else [],
                           "error": r.get("error", "")})
        if r.get("ok"):
            s["dispatches_today"] += 1
    else:
        dispatched.append({"ok": False, "reason": "under threshold or daily cap reached",
                           "untagged": untagged})

    behavior = _record_swarm_behavior(dispatched)
    _save_state(s)
    return {
        "ok": True, "schema": SCHEMA, "ts": _now(),
        "untagged_corpus": untagged,
        "dispatches_today": s["dispatches_today"], "cap": DAILY_CAP_DISPATCH,
        "tesuji_leaf": leaf.get("ok"), "sizing_learned": sizing.get("ok"),
        "behavior_recorded": behavior.get("recorded", 0),
        "dispatched": dispatched,
    }


def status() -> dict[str, Any]:
    s = _load_state()
    return {"ok": True, "schema": SCHEMA, "runs": s.get("runs", 0),
            "dispatches_today": s.get("dispatches_today", 0), "cap": DAILY_CAP_DISPATCH,
            "untagged_now": _untagged_count()}


def main(argv: list[str] | None = None) -> int:
    import argparse
    p = argparse.ArgumentParser(prog="ghost_auto", description="automatic loop: tesuji + sizing + dispatch")
    p.add_argument("--force", action="store_true", help="run cadence even if state says recent")
    p.add_argument("--status", action="store_true", help="print status")
    a = p.parse_args(argv)
    res = status() if a.status else run_cadence(force=a.force)
    print(json.dumps(res, indent=2, default=str)[:5000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
