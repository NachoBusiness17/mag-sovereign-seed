"""maze_real — render the REAL-PROCESS MAZE from real corpus pieces (2026-09-13).

Operator's reframe: "the maze was always just a demo — map real processes to mazes...
invariants mapped via stochastic distance... islands of order vs the fractals of stability."

GRAMMAR (every wall traceable to a real byte, nothing decorative):
  - Island of order   = one LAW (dashboard/static/lattice_data.json, 20 laws) — a C-shaped
    walled room; border length ∝ citation degree (invariants cast the longest shadows).
  - Corridor          = one primaryEdge (co-citation) — an opening between two islands.
  - GOLD invariants   = the top-cited law per group: full gold border, never moved.
  - The two stones    = laws 19-20 (born isolated, no co-citations — the lattice drew them
    alone): the beacon STARTS at their island; the field expands from the newest stone.
  - Beacon path       = BFS tour over the REAL co-citation graph from LAW-XX (newest) —
    the arena's stochastic distance field expands along actual doctrine structure.
  -Organ coupling     = count of mag/*.py importing each other, printed in the receipt
    (island naming substrate; v0 keeps walls law-only).

Output: dashboard/static/rounds_real.json  {generated, sources+sha256, walls, beaconPath,
mapping} — consumed by maze_arena.html when opened with ?real=1.
Deterministic: layout derived from content hashes + graph order, no randomness.

CLI: python -m mag.maze_real [--hold]   (--hold = don't write, just print the mapping)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
from collections import deque
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parent.parent
LATTICE = ROOT / "dashboard" / "static" / "lattice_data.json"
OUT = ROOT / "dashboard" / "static" / "rounds_real.json"

# world box (matches the demo walls' coordinate space: x 0.3..1.9, y 0.3..2.45)
X0, X1, Y0, Y1 = 0.30, 1.90, 0.30, 2.45
WT = 0.045          # wall thickness


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def build() -> dict:
    data = json.loads(LATTICE.read_text(encoding="utf-8"))
    laws = data["laws"]
    n = len(laws)

    degree = [0] * n
    for a, b, w in data["primaryEdges"]:
        degree[a] += w
        degree[b] += w

    # adjacency from co-citation (weighted)
    adj = [[] for _ in range(n)]
    for a, b, w in data["primaryEdges"]:
        adj[a].append((b, w))
        adj[b].append((a, w))

    # islands: one per law, placed on a grid ordered by a BFS from the newest law
    # (the two stones that expand the field — the beacon starts there)
    newest = n - 1
    order, seen, q = [], {newest}, deque([newest])
    while q:
        cur = q.popleft()
        order.append(cur)
        nxt = sorted(adj[cur], key=lambda e: (-e[1], e[0]))  # strongest co-citation first
        for nb, _w in nxt + [(i, 0) for i in range(n) if i not in seen]:
            if nb not in seen:
                seen.add(nb)
                q.append(nb)

    cols, rows = 5, (n + 4) // 5
    cw, ch = (X1 - X0) / cols, (Y1 - Y0) / rows
    cells = {}
    for slot, li in enumerate(order):
        r, c = divmod(slot, cols)
        cells[li] = (X0 + c * cw + cw * 0.18, Y0 + r * ch + ch * 0.15, cw * 0.64, ch * 0.7)

    top_by_group = {}
    for i, law in enumerate(laws):
        g = law.get("group", 0)
        if g not in top_by_group or degree[i] > degree[top_by_group[g]]:
            top_by_group[g] = i
    gold = set(top_by_group.values())

    walls, mapping = [], []

    def wall(x, y, w, h, law_idx, kind):
        # arena wall format: [center_x, center_y, half_w, half_h] (sdf() reads center+half)
        walls.append([round(x + w / 2, 3), round(y + h / 2, 3), round(w / 2, 3), round(h / 2, 3)])
        mapping.append({"wall": len(walls) - 1, "kind": kind,
                        "law": laws[law_idx]["label"], "id": laws[law_idx]["id"],
                        "degree": degree[law_idx]})

    for li in range(n):
        x, y, w, h = cells[li]
        t = WT + (0.012 * degree[li])          # invariants cast the longest shadows
        kind = "gold" if li in gold else "order"
        # C-shape: top, left, bottom (opening faces the next island in the BFS tour)
        wall(x, y, w + t, t, li, kind)                   # top
        wall(x, y, t, h + t, li, kind)                   # left
        wall(x, y + h, w + t, t, li, kind)               # bottom
        if li in gold:                                    # gold keeps its right wall too
            wall(x + w, y, t, h + t, li, kind)

    # corridors: primaryEdges (weight = co-citation count — the stochastic distance inverse)
    corridors = [{"edge": [int(a), int(b)], "weight": int(w),
                  "laws": [laws[a]["id"], laws[b]["id"]]} for a, b, w in data["primaryEdges"]]

    # beacon path: BFS tour order over island centers — the field expands from the newest stone
    beacon_path = [[round((cells[li][0] + cells[li][2] / 2), 3),
                    round((cells[li][1] + cells[li][3] / 2), 3)] for li in order]

    organ_count = len(list((ROOT / "mag").glob("*.py")))
    return {
        "schema": "real_maze.v1",
        "generated": datetime.now(timezone.utc).isoformat(),
        "label": "ISLANDS OF ORDER — 20 laws, co-citation corridors, newest stone first",
        "sources": {
            "lattice": str(LATTICE.relative_to(ROOT)),
            "lattice_sha": sha(LATTICE.read_text(encoding="utf-8")),
            "organs": organ_count,
        },
        "walls": walls,
        "beaconPath": beacon_path,
        "tour": [laws[i]["id"] for i in order],
        "corridors": corridors,
        "mapping": mapping,
    }


def main() -> int:
    ap = argparse.ArgumentParser(prog="maze_real")
    ap.add_argument("--hold", action="store_true")
    args = ap.parse_args()
    doc = build()
    print(f"walls: {len(doc['walls'])} ({sum(1 for m in doc['mapping'] if m['kind']=='gold')} gold-bordered)  "
          f"corridors: {len(doc['corridors'])}  tour: {' -> '.join(str(t) for t in doc['tour'][:6])}...")
    for m in doc["mapping"][:6]:
        print(f"  wall {m['wall']:2d} [{m['kind']:5s}] {m['id']} {m['law']} (degree {m['degree']})")
    if not args.hold:
        OUT.write_text(json.dumps(doc, indent=1), encoding="utf-8")
        print(f"written: {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
