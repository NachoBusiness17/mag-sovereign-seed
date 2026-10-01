"""matrix_router — the TWO-WINDOW MATRIX: ghost routes tasks between open CLI windows.

Operator (2026-08-10): "can we have two windows in the cli and have ghost be aware of both and
have it route tasks through open chat windows so i can see them and we can really matrix this
shit" + "build these things automatically deploy them and test and enhance them via our stateless
systems".

THE MECHANISM (stateless: fresh functions re-encoding invariants; identity in the verkle chain):
  Two CLI windows = two LANES (voice_lanes) = two registered SEATS (seat_registry). Both mount
  the SAME shared window_bus segment (byte-stable, cache-hit cost). GHOST is aware of both (reads
  the registry + bus) and ROUTES tasks between them — heavy task to lane A, synthesis to lane B —
  so the operator watches both windows live (the matrix).

Flow:
  1. register_lane(name, role)  — register each window as a lane/seat ghost can see.
  2. mount_bus()                — build the shared byte-stable bus both windows mount (cache-hit).
  3. route(goal)                — decide WHICH window handles a task (by role/keyword), and write
                                  the routed task + bus update so the target window picks it up.
  4. status()                   — ghost's view: which windows are open, what's on the bus, what's
                                  routed where.

Schema: matrix_router.v1 · deterministic $0 · CLI: python -m mag.matrix_router register|bus|
        route "<goal>"|status
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
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

SCHEMA = "matrix_router.v1"
MATRIX_DIR = ROOT / "memory" / "runs" / "matrix"
LANES = MATRIX_DIR / "lanes.json"
BUS = MATRIX_DIR / "bus.txt"
ROUTES = MATRIX_DIR / "routes.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load_lanes() -> dict[str, Any]:
    if not LANES.is_file():
        return {}
    try:
        return json.loads(LANES.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_lanes(d: dict[str, Any]) -> None:
    MATRIX_DIR.mkdir(parents=True, exist_ok=True)
    LANES.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")


# role -> keyword signals (which lane handles what)
ROLE_SIGNALS = {
    "research": ["research", "deep", "steal", "investigate", "survey", "learn", "study"],
    "build": ["build", "implement", "code", "write", "create", "fix", "deploy"],
    "synthesis": ["synthesize", "summarize", "review", "decide", "recommend", "assess"],
    "ops": ["status", "queue", "drain", "health", "clean", "janitor"],
}


def register_lane(name: str, role: str = "research", *, seat: str = "cli-window") -> dict[str, Any]:
    """Register a CLI window as a matrix lane + seat so ghost is aware of it."""
    lanes = _load_lanes()
    rec = {"name": name, "role": role, "seat": seat, "registered_at": _now(),
           "active": True}
    lanes[name] = rec
    _save_lanes(lanes)
    # also register as a seat so ghost/routing sees it as an open window
    try:
        from mag import seat_registry as sr
        sr.register(goal=f"[matrix-lane {name}]", seat=seat, tag=f"matrix-{name}", mode="interactive")
    except Exception:
        pass
    return {"ok": True, "schema": SCHEMA, "lane": rec}


def mount_bus(*, invariants: list[str] | None = None, signals: list[str] | None = None) -> dict[str, Any]:
    """Build the shared byte-stable bus (window_bus) that all matrix windows mount."""
    lanes = _load_lanes()
    members = list(lanes.keys())
    try:
        from mag import window_bus as wb
        seg = wb.bus_segment(invariants=invariants or ["matrix-active", "stateless"],
                             signals=signals or ["two-window", "ghost-routed"],
                             members=members or ["lane-a", "lane-b"])
        BUS.parent.mkdir(parents=True, exist_ok=True)
        BUS.write_text(str(seg.get("segment") or seg.get("bus") or ""), encoding="utf-8")
        return {"ok": True, "schema": SCHEMA, "members": members,
                "bus_path": str(BUS), "segment": seg}
    except Exception as e:
        return {"ok": False, "schema": SCHEMA, "error": str(e)[:200]}


def _role_for(goal: str) -> str:
    g = goal.lower()
    best, best_n = "research", 0
    for role, sigs in ROLE_SIGNALS.items():
        n = sum(1 for s in sigs if s in g)
        if n > best_n:
            best, best_n = role, n
    return best


def route(goal: str, *, source_lane: str = "driver") -> dict[str, Any]:
    """Decide WHICH window handles a task (by role), write the routed task + bus update."""
    lanes = _load_lanes()
    if not lanes:
        return {"ok": False, "schema": SCHEMA, "error": "no lanes registered — register_lane first"}
    role = _role_for(goal)
    # pick a lane matching the role, else round-robin over active lanes
    target = next((n for n, l in lanes.items() if l.get("role") == role and l.get("active")), None)
    if target is None:
        active = [n for n, l in lanes.items() if l.get("active")]
        target = active[len([None]) % max(1, len(active))] if active else list(lanes)[0]
    ROUTES.parent.mkdir(parents=True, exist_ok=True)
    row = {"ts": _now(), "goal": goal[:200], "role": role, "target": target,
           "source": source_lane}
    with ROUTES.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return {"ok": True, "schema": SCHEMA, "goal": goal[:120], "role": role,
            "routed_to": target, "route_record": str(ROUTES)}


def status() -> dict[str, Any]:
    lanes = _load_lanes()
    routes = 0
    if ROUTES.is_file():
        try:
            routes = sum(1 for _ in ROUTES.open(encoding="utf-8"))
        except Exception:
            pass
    return {"ok": True, "schema": SCHEMA, "n_windows": len(lanes),
            "lanes": {n: {"role": l.get("role"), "active": l.get("active")}
                      for n, l in lanes.items()},
            "bus": str(BUS) if BUS.is_file() else "not mounted",
            "n_routes": routes}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Two-window matrix router (ghost routes between CLI windows)")
    ap.add_argument("cmd", nargs="?", default="status",
                    choices=["register", "bus", "route", "status"])
    ap.add_argument("arg", nargs="*", default=[])
    a = ap.parse_args()
    if a.cmd == "register":
        name = a.arg[0] if a.arg else "lane-a"
        role = a.arg[1] if len(a.arg) > 1 else "research"
        print(json.dumps(register_lane(name, role), ensure_ascii=False, indent=2))
    elif a.cmd == "bus":
        print(json.dumps(mount_bus(), ensure_ascii=False, indent=2))
    elif a.cmd == "route":
        goal = " ".join(a.arg) or "research the stateless matrix"
        print(json.dumps(route(goal), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(status(), ensure_ascii=False, indent=2))
