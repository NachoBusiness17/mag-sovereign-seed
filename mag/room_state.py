#!/usr/bin/env python3
"""room_state.py v2 — seed the salon lightmap ("the room that remembers").

Reads the trajectory stream tail (memory/trajectory/steps.jsonl, trajectory_step.v1)
and emits dashboard/static/room_state.json: the fleet's real anatomy as organ walls,
which walls the seat's attention actually touched recently (lit + hit counts), which
walls are invariant candidates, and — NEW in v2 — each wall's Ponytail economy state:
pixels earn by fire-rate.

  JOINED   >=3 fires/24h, twice running (two consecutive trailing 24h windows).
  ghost    candidate overlay: fires recently but not yet promoted.
  PRUNE    0 fires/72h -> prune note (goes DARK-SIDE, geometry kept, glow stripped).

Every wall also carries its algebra-primitive glyph (fleet_symbols.html), a
content_hash (no hash -> no draw), last_fire_ts, hit_count_200 and a 20-bucket
fire histogram over the last 200 steps — the map shows the STREAM, never a snapshot.
The render ships hash-anchored: chain_tip_at_paint (verkle chain tip at write).

$0 · stdlib only · one-shot, no daemon. Night shift runs:
    python mag/room_state.py [--window 200]
Before each write the previous state is archived to room_state.prev.json so the
cross-version invariant diff is real, not declared.
"""
import argparse
import hashlib
import json
import os
import shutil
import time
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STEPS = os.path.join(ROOT, "memory", "trajectory", "steps.jsonl")
CHAIN = os.path.join(ROOT, "memory", "biography", "verkle_chain.jsonl")
OUT = os.path.join(ROOT, "dashboard", "static", "room_state.json")
PREV = os.path.join(ROOT, "dashboard", "static", "room_state.prev.json")

SCHEMA = "room_state.v2"
JOIN_WINDOW_H = 24      # Ponytail: >=3 fires per trailing 24h window...
JOIN_MIN_FIRES = 3      # ...twice running, before a wall joins the live layer
PRUNE_HOURS = 72        # 0 fires/72h -> prune note
HIST_BUCKETS = 20       # per-wall fire histogram across the last `window` steps
PERSIST_MIN_HOURS = 24  # invariance needs a real time gap between versions —
                        # persistence across minutes is geometry, not evidence

# The room's real anatomy. x/y/w/h place each organ on the 560x560 lightmap canvas.
# tokens = substrings matched against trajectory step commands (attention probe).
# glyph  = the wall's algebra primitive (sym-* in dashboard/static/fleet_symbols.html):
#          chain=STORE, lanes=GATE, guards=DISSIPATE, room/organs/watch=INTEGRATE,
#          boot_check=GROUND, board=EMIT, sensors=DIFFERENTIATE, memory=STORE.
# invariant=True seeds the canonical three: chain never moved since Aug, the room
# beats hourly, boot_check gates every window (operator brief, 09-06).
WALLS = [
    {"id": "chain",      "label": "verkle chain · skeleton",   "kind": "skeleton",
     "x": 70,  "y": 80,  "w": 26,  "h": 260, "invariant": True,  "glyph": "store",
     "tokens": ["verkle_chain", "verkle_knot"]},
    {"id": "memory",     "label": "memory/biography",          "kind": "memory",
     "x": 150, "y": 56,  "w": 130, "h": 34,  "invariant": False, "glyph": "store",
     "tokens": ["biography", "MEMORY.md"]},
    {"id": "watch",      "label": "watch · ledger cards",      "kind": "ledger",
     "x": 150, "y": 150, "w": 110, "h": 24,  "invariant": False, "glyph": "integrate",
     "tokens": ["watch/"]},
    {"id": "immune",     "label": "guards · refeed_guard",     "kind": "immune",
     "x": 420, "y": 60,  "w": 96,  "h": 26,  "invariant": False, "glyph": "dissipate",
     "tokens": ["refeed_guard", "watchdog", "grounding_wave"]},
    {"id": "lanes",      "label": "lanes · auth_tracks",       "kind": "circulation",
     "x": 400, "y": 170, "w": 124, "h": 24,  "invariant": False, "glyph": "gate",
     "tokens": ["auth_tracks", "fuel_feed"]},
    {"id": "room",       "label": "the room · CONVO.md",       "kind": "room",
     "x": 250, "y": 250, "w": 92,  "h": 26,  "invariant": True,  "glyph": "integrate",
     "tokens": ["CONVO.md", "room.jsonl", "queue/handoff"]},
    {"id": "board",      "label": "the board · room.html",     "kind": "board",
     "x": 440, "y": 280, "w": 84,  "h": 26,  "invariant": False, "glyph": "emit",
     "tokens": ["room.html", "board.js", "live.html"]},
    {"id": "organs",     "label": "mag/* organs",              "kind": "organs",
     "x": 330, "y": 390, "w": 140, "h": 30,  "invariant": False, "glyph": "integrate",
     "tokens": ["mag/", "overseer"]},
    {"id": "boot_check", "label": "boot_check · gate",         "kind": "gate",
     "x": 60,  "y": 420, "w": 112, "h": 26,  "invariant": True,  "glyph": "ground",
     "tokens": ["boot_check", "boot.py"]},
    {"id": "sensors",    "label": "sensors · trajectory",      "kind": "nervous",
     "x": 180, "y": 480, "w": 160, "h": 22,  "invariant": False, "glyph": "differentiate",
     "tokens": ["steps.jsonl", "read_receipts", "trajectory"]},
]


def load_steps():
    """The whole tape (read-only): parsed steps with ts + command, order preserved."""
    if not os.path.exists(STEPS):
        return []
    out = []
    with open(STEPS, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                s = json.loads(line)
            except Exception:
                continue
            out.append(s)
    return out


def parse_ts(t):
    return datetime.fromisoformat(t)


def wall_fires(steps):
    """Fire events per wall across the WHOLE tape: {wall_id: [iso ts, ...]}."""
    ev = {w["id"]: [] for w in WALLS}
    for s in steps:
        cmd = s.get("command", "") or ""
        ts = s.get("ts")
        if not ts:
            continue
        for w in WALLS:
            if any(t in cmd for t in w["tokens"]):
                ev[w["id"]].append(ts)
    return ev


def attention(tail):
    """Hit counts per wall id across the last `window` trajectory steps."""
    hits = {w["id"]: 0 for w in WALLS}
    for s in tail:
        cmd = s.get("command", "") or ""
        for w in WALLS:
            if any(t in cmd for t in w["tokens"]):
                hits[w["id"]] += 1
    return hits


def histogram(wid, tail):
    """Fires per HIST_BUCKETS bucket across the tail steps (the 200-step stream)."""
    hist = [0] * HIST_BUCKETS
    n = max(1, len(tail))
    for i, s in enumerate(tail):
        cmd = s.get("command", "") or ""
        w = next((w for w in WALLS if w["id"] == wid), None)
        if w and any(t in cmd for t in w["tokens"]):
            b = min(HIST_BUCKETS - 1, i * HIST_BUCKETS // n)
            hist[b] += 1
    return hist


def economy(ev, now, first_ts):
    """Ponytail gate: JOINED / ghost / prune from the wall's own fire-rate.

    Returns (state, joins_at, prune_note). joins_at = the earliest ts at which
    this wall could honestly flip JOINED: for candidates in good standing that is
    max(now, first tape ts + window) — before then the prior window cannot hold
    any tape, so a JOIN verdict would be hallucinated.
    """
    w24 = [t for t in ev if parse_ts(t) > now - timedelta(hours=JOIN_WINDOW_H)]
    wprev = [t for t in ev
             if now - timedelta(hours=2 * JOIN_WINDOW_H) < parse_ts(t)
             <= now - timedelta(hours=JOIN_WINDOW_H)]
    w72 = [t for t in ev if parse_ts(t) > now - timedelta(hours=PRUNE_HOURS)]
    if len(w24) >= JOIN_MIN_FIRES and len(wprev) >= JOIN_MIN_FIRES:
        return "joined", now.strftime("%Y-%m-%dT%H:%M:%SZ"), None
    if not w72:
        note = ("0 fires in %dh — PRUNE NOTE: goes dark-side, geometry kept, "
                "glow stripped" % PRUNE_HOURS)
        return "prune", None, note
    joins_at = None
    if len(w24) >= JOIN_MIN_FIRES and first_ts is not None:
        earliest = first_ts + timedelta(hours=JOIN_WINDOW_H)
        if earliest > now:
            joins_at = earliest.strftime("%Y-%m-%dT%H:%M:%SZ")
    return "ghost", joins_at, None


def chain_tip():
    """Last knot of the verkle chain — the hash anchor the render paints as-of."""
    if not os.path.exists(CHAIN):
        return None
    try:
        with open(CHAIN, encoding="utf-8", errors="replace") as f:
            last = ""
            for last in f:
                if last.strip():
                    pass
        k = json.loads(last)
        return {"index": k.get("index"),
                "tip": (k.get("verkle_root") or "")[:12]}
    except Exception:
        return None


def persisted_invariants(prev):
    """Walls whose label+position survive from the previous version — counted
    only when that version is at least PERSIST_MIN_HOURS old (a diff across
    minutes proves the geometry is static, not that the wall is load-bearing)."""
    if not os.path.exists(PREV):
        return set()
    try:
        doc = json.load(open(PREV, encoding="utf-8"))
        old_gen = parse_ts(doc["generated"])
        old = {w.get("id"): w for w in doc.get("walls", [])}
    except Exception:
        return set()
    if datetime.now(timezone.utc) - old_gen < timedelta(hours=PERSIST_MIN_HOURS):
        return set()
    keep = set()
    for w in WALLS:
        p = old.get(w["id"])
        if p and (p.get("label"), p.get("x"), p.get("y"), p.get("w"), p.get("h")) == \
                 (w["label"], w["x"], w["y"], w["w"], w["h"]):
            keep.add(w["id"])
    return keep


def content_hash(w):
    """Stable hash of the wall's definition — no hash, no draw (Ponytail invariant)."""
    blob = json.dumps({k: w[k] for k in ("id", "label", "x", "y", "w", "h",
                                         "kind", "glyph", "tokens")},
                      sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--window", type=int, default=200)
    args = ap.parse_args()

    steps = load_steps()
    steps.sort(key=lambda s: s.get("ts") or "")
    tail = steps[-args.window:]
    hits = attention(tail)
    fires = wall_fires(steps)
    keep = persisted_invariants(None)

    now = None
    if steps:
        now = parse_ts(steps[-1]["ts"])
    else:
        now = datetime.now(timezone.utc)
    first_ts = parse_ts(steps[0]["ts"]) if steps else None
    gen = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    walls = []
    for w in WALLS:
        ev = sorted(fires[w["id"]])
        state, joins_at, prune_note = economy(ev, now, first_ts)
        walls.append({k: w[k] for k in ("id", "label", "x", "y", "w", "h", "kind",
                                        "invariant", "glyph")}
                     | {"lit": hits[w["id"]] > 0, "hits": hits[w["id"]],
                        "invariant": bool(w["invariant"] or w["id"] in keep),
                        "content_hash": content_hash(w),
                        "last_fire_ts": ev[-1] if ev else None,
                        "hit_count_200": hits[w["id"]],
                        "hist": histogram(w["id"], tail),
                        "economy": state,
                        "joins_at": joins_at,
                        "prune_note": prune_note})

    if os.path.exists(OUT):
        shutil.copyfile(OUT, PREV)  # archive for the next version's diff

    tip = chain_tip()
    counts = {"joined": sum(1 for w in walls if w["economy"] == "joined"),
              "ghost": sum(1 for w in walls if w["economy"] == "ghost"),
              "prune": sum(1 for w in walls if w["economy"] == "prune")}
    state = {
        "schema": SCHEMA,
        "generated": gen,
        "source": "memory/trajectory/steps.jsonl (trajectory_step.v1), last %d steps" % len(tail),
        "window": len(tail),
        "lit": [w["id"] for w in walls if w["lit"]],
        "economy": counts,
        "chain_tip_at_paint": tip,
        "economy_rules": {
            "joined": ">=3 fires/24h, twice running (two consecutive trailing %dh windows)" % JOIN_WINDOW_H,
            "ghost": "candidate overlay — fires recently, not yet promoted",
            "prune": "0 fires/%dh -> prune note (dark-side, geometry kept)" % PRUNE_HOURS,
            "invariant": "no hash -> no draw; every wall carries content_hash + chain_tip_at_paint",
        },
        "walls": walls,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=1)
    inv = sum(1 for w in walls if w["invariant"])
    print("room_state.json written (v2): %d organ walls, %d lit, %d invariant candidates "
          "(window=%d) | economy: %d JOINED, %d ghost, %d prune | tip=%s@%s"
          % (len(walls), len(state["lit"]), inv, len(tail),
             counts["joined"], counts["ghost"], counts["prune"],
             (tip or {}).get("tip"), (tip or {}).get("index")))


if __name__ == "__main__":
    main()
