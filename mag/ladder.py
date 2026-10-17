"""ladder — the AUTOMATED baby-step loop (2026-08-25).

Operator: "we can do our babysteps automated... you have enough training to put it
on a curve." The utilization ladder walks itself: SENSE each body's utilization,
CURVE (learn from real outcomes — bodies that succeed get more work, failures get
less, and the ramp rises as success accumulates), WALK (dispatch real tasks to the
under-utilized bodies via seat_dispatch), FOLD, LEARN.

Self-steal (nothing new invented):
  * seat_dispatch   — task any body headlessly (flash/heavy tiers, mailbox seats)
  * offerings       — BODIES + route(intent) (the bodies map)
  * percolator      — the EXPLORE QUEUE is the endless pool of REAL novel work
  * lane_cadence    — the learn-from-outcomes pattern (this is the curve's shape)
  * work_register   — every result folds with a tri-state claim

The curve (memory/runs/ladder_curve.json): per body — tasks_done, ok_count,
last_ok, weight, ramp_level. weight = success-rate × recency (newer outcomes count
more). walk_cycle picks the bodies with the LOWEST weight first (the most
under-utilized get walked first — the whole point), and ramp_level grows the task
as a body proves itself (babysteps -> bigger steps).

CLI: python -m mag.ladder sense|curve|walk [--batch N]|status
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(r"c:\Users\ESTATE_USER\Documents\projects\local_sovereign_agent")
sys.path.insert(0, str(ROOT))

SCHEMA = "ladder.v1"
CURVE_FILE = ROOT / "memory" / "runs" / "ladder_curve.json"
DAILY_CAP = 8  # max dispatches per day per ladder run (bounded, rightsized)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _load_curve() -> dict[str, Any]:
    if CURVE_FILE.is_file():
        try:
            return json.loads(CURVE_FILE.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            pass
    return {"bodies": {}, "ts": _now()}


def _save_curve(c: dict[str, Any]) -> None:
    CURVE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CURVE_FILE.write_text(json.dumps(c, ensure_ascii=False, indent=2), encoding="utf-8")


def _weight(b: dict[str, Any]) -> float:
    """The curve: success-rate × recency. Newer outcomes count more. Fresh bodies get
    walked FIRST (lowest weight) — under-utilization is the whole point."""
    ok = int(b.get("ok_count") or 0)
    done = int(b.get("tasks_done") or 0)
    rate = ok / done if done else 0.0
    last = b.get("last_ts") or ""
    recency = 1.0
    try:
        from datetime import datetime
        t = datetime.fromisoformat(last.replace("Z", "+00:00"))
        age_h = (datetime.now(timezone.utc) - t).total_seconds() / 3600
        recency = max(0.1, 1.0 - age_h / 24.0)  # 24h decay
    except Exception:  # noqa: BLE001
        recency = 0.1
    return round(rate * recency, 4)


def sense() -> dict[str, Any]:
    """Each body's utilization state: installed, tasks_done, last outcome, weight."""
    from mag import offerings
    s = offerings.status()
    curve = _load_curve()
    rows = {}
    for bid, body in s.get("bodies", {}).items():
        b = curve.get("bodies", {}).get(bid, {})
        rows[bid] = {
            "installed": body.get("installed"),
            "name": body.get("name", bid),
            "surfaces": body.get("surfaces", [])[:4],
            "tasks_done": int(b.get("tasks_done") or 0),
            "ok_count": int(b.get("ok_count") or 0),
            "last_ok": bool(b.get("last_ok")) if b.get("last_ok") is not None else None,
            "last_ts": b.get("last_ts"),
            "weight": _weight(b),
            "ramp_level": int(b.get("ramp_level") or 0),
        }
    return {"ok": True, "schema": SCHEMA, "kind": "sense", "n": len(rows), "bodies": rows}


def _real_task(bid: str, ramp: int) -> str:
    """Pull a REAL task from the percolator explore queue (endless novel work), scaled by
    the body's ramp level (babysteps -> bigger steps). Falls back to a useful audit ask."""
    from mag import percolator
    try:
        if percolator.EXPLORE_QUEUE.is_file():
            rows = [json.loads(l) for l in
                    percolator.EXPLORE_QUEUE.read_text(encoding="utf-8", errors="replace").splitlines()
                    if l.strip()]
            open_rows = [r for r in rows if r.get("status") == "open"]
            if open_rows:
                r = open_rows[-1]  # the most recent novel signal
                sig = str(r.get("signal") or "")[:400]
                return (f"EXPLORE + FOLD a novel percolator signal (ramp {ramp}): {sig} — "
                        f"classify it, then fold it into an invariant via mag.percolator.percolate "
                        f"(repeat -> invariant, novel -> explore). Report the verdict in one line.")
    except Exception:  # noqa: BLE001
        pass
    return (f"AUDIT BEAT (ramp {ramp}): read logs/provider_usage.jsonl and report the single most "
            f"actionable inefficiency you find, in one sentence.")


def walk_cycle(*, batch: int = 2, dry: bool = False) -> dict[str, Any]:
    """WALK the ladder: dispatch a real task to the most under-utilized bodies (by curve),
    fold the results, update the curve. Bounded by batch + the concurrency gate."""
    from mag import seat_dispatch as sd

    s = sense()
    curve = _load_curve()
    bodies = s["bodies"]
    # most under-utilized first (lowest weight, fewest tasks)
    ranked = sorted(bodies.items(), key=lambda kv: (kv[1]["weight"], kv[1]["tasks_done"]))
    # only bodies we can actually dispatch headless (or mailbox — but walk only headless)
    walkable = [bid for bid, _ in ranked if bid in sd.HEADLESS]
    picked = walkable[:batch]

    ran = []
    for bid in picked:
        b = curve.setdefault("bodies", {}).setdefault(bid, {})
        ramp = int(b.get("ramp_level") or 0)
        goal = _real_task(bid, ramp)
        b["tasks_done"] = int(b.get("tasks_done") or 0) + 1  # tentatively
        if dry:
            ran.append({"seat": bid, "task": goal[:80], "dry": True})
            continue
        r = sd.task(goal, seat=bid, tag="ladder")
        ok = r.get("status") == "done"
        b["tasks_done"] = int(b.get("tasks_done") or 0)
        b["ok_count"] = int(b.get("ok_count") or 0) + (1 if ok else 0)
        b["last_ok"] = ok
        b["last_ts"] = _now()
        b["ramp_level"] = int(b.get("ramp_level") or 0) + (1 if ok else -1)
        if b["ramp_level"] < 0:
            b["ramp_level"] = 0
        ran.append({"seat": bid, "task_id": r.get("task_id"), "status": r.get("status"),
                    "detail": str(r.get("detail") or "")[:80]})

    curve["ts"] = _now()
    _save_curve(curve)
    return {"ok": True, "schema": SCHEMA, "kind": "walk", "picked": picked,
            "ran": ran, "curve": {k: {"tasks_done": v.get("tasks_done"), "ok_count": v.get("ok_count"),
                                      "ramp_level": v.get("ramp_level"), "weight": _weight(v)}
                                  for k, v in curve.get("bodies", {}).items()}}


def status() -> dict[str, Any]:
    c = _load_curve()
    return {"ok": True, "schema": SCHEMA, "kind": "status",
            "curve_file": str(CURVE_FILE.relative_to(ROOT)),
            "bodies": {k: {"tasks_done": v.get("tasks_done"), "ok_count": v.get("ok_count"),
                           "ramp_level": v.get("ramp_level"), "weight": _weight(v)}
                       for k, v in c.get("bodies", {}).items()},
            "ts": c.get("ts")}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="ladder", description="automated baby-step loop")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("sense")
    sub.add_parser("curve")
    p_w = sub.add_parser("walk")
    p_w.add_argument("--batch", type=int, default=2)
    p_w.add_argument("--dry", action="store_true")
    sub.add_parser("status")
    a = ap.parse_args(argv)
    if a.cmd == "sense":
        out = sense()
    elif a.cmd == "curve":
        out = status()
    elif a.cmd == "walk":
        out = walk_cycle(batch=a.batch, dry=a.dry)
    else:
        out = status()
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
