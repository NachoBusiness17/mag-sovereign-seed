#!/usr/bin/env python3
"""PATHS-ON-MAP emitter — trajectory walker paths over the tesuji field.

Reads the LAST 500 trajectory_step.v1 rows from memory/trajectory/steps.jsonl,
groups them by session_id (each session = one walker), greps each step's
command for organ tokens, maps each token onto the field's corridors
(A1-A6 + G ground + R record), and emits dashboard/static/trajectory_paths.json
as per-session PATH ARRAYS for the field page to draw as colored threads.

Card: watch/inbox/PATHS_ON_MAP_20260907.md
Spec: watch/SELF_STEAL_MODEL_CARTOGRAPHY_20260906.md (PATHS-ON-MAP)
Law:  trajectories are walker PATHS over the field; the envelope is the path log.
"""
import collections
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STEPS = ROOT / "memory" / "trajectory" / "steps.jsonl"
OUT = ROOT / "dashboard" / "static" / "trajectory_paths.json"
TAIL = 500
MAX_POINTS = 64  # cap per-walker path length; walkers are compressed, not lost

# organ token -> corridor. First match wins per step; dedup within a step.
ORGAN_AXIS = [
    ("tesuji", "A1"), ("probe", "A1"), ("distill", "A1"),
    ("shadow", "A2"), ("refusal", "A2"), ("injection", "A2"),
    ("maze", "A3"), ("arena", "A3"), ("arrakis", "A3"), ("swarm", "A3"), ("slot", "A3"),
    ("lightmap", "A4"), ("refeed", "A4"), ("feed", "A4"), ("rib", "A4"), ("cache", "A4"),
    ("percolator", "A5"), ("canon", "A5"), ("topic", "A5"), ("overseer", "A5"),
    ("vision", "A5"), ("cite", "A5"),
    ("gguf", "A6"), ("quant", "A6"), ("rocinante", "A6"), ("studio", "A6"),
    ("wave", "G"), ("ground", "G"),
    ("chain", "R"), ("salon", "R"), ("riddler", "R"), ("x_interceptor", "R"),
]

PALETTE = [
    "#7cf5ff", "#e8c96a", "#ff9d6b", "#9dff6b", "#6b9dff", "#ff6bd4",
    "#6bffd4", "#ffd46b", "#c96bff", "#6bff9d", "#ff6b6b", "#6bc4ff",
    "#e0e06b", "#b6ff6b", "#ff8ac2",
]


def touches(cmd):
    """Return the (axis, organ) touches found in one step command."""
    low = (cmd or "").lower()
    hits = []
    seen = set()
    for organ, axis in ORGAN_AXIS:
        if organ in low and organ not in seen:
            seen.add(organ)
            hits.append((axis, organ))
    return hits


def main():
    lines = STEPS.read_text(encoding="utf-8").splitlines() if STEPS.exists() else []
    rows = []
    for line in lines[-TAIL:]:
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    by_session = collections.OrderedDict()
    for r in rows:
        sid = r.get("session_id") or "(anon)"
        ts = r.get("ts") or ""
        for axis, organ in touches(r.get("command")):
            by_session.setdefault(sid, []).append(
                {"axis": axis, "cell": axis + "/" + organ, "ts": ts, "organ": organ}
            )

    # walkers sorted by last touch, newest first
    sessions = []
    for sid, pts in by_session.items():
        pts.sort(key=lambda p: p["ts"])
        # collapse consecutive same-corridor touches into one point (keep first
        # organ as the cell, last ts as the exit time) — the walk, not the noise
        path = []
        for p in pts:
            if path and path[-1]["axis"] == p["axis"]:
                path[-1]["ts"] = p["ts"]
                continue
            path.append({"axis": p["axis"], "cell": p["cell"], "ts": p["ts"]})
        path = path[-MAX_POINTS:]  # keep the freshest leg of long walks
        sessions.append({
            "id": sid,
            "steps": len(pts),
            "first_ts": pts[0]["ts"],
            "last_ts": pts[-1]["ts"],
            "path": path,
        })
    sessions.sort(key=lambda s: s["last_ts"], reverse=True)
    for i, s in enumerate(sessions):
        s["color"] = PALETTE[i % len(PALETTE)]

    out = {
        "schema_version": "trajectory_paths.v1",
        "ts": max((s["last_ts"] for s in sessions), default=""),
        "source": "trajectory_step.v1",
        "window": TAIL,
        "total_points": sum(len(s["path"]) for s in sessions),
        "sessions": sessions,
    }
    OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("PATHS: %d walkers, %d path points, %d raw touches -> %s"
          % (len(sessions), out["total_points"], sum(len(v) for v in by_session.values()), OUT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
