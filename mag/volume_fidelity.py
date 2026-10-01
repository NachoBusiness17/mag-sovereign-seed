"""volume_fidelity — the HALLUCINATION GAUNTLET (batch 7, rb-gauntlet).

The commission: "is the volume a hallucination?" SHADOW WALK quantizes 9,305
behavioral parts into a GXxGZ voxel grid with a seeded carve (corridors descend
a BFS field to the doctrine core). The operator looks at it and SEES corridors,
biomes, gold invariants. This module is the machine that asks whether those
perceived structures correspond to real source structure or are projection
artifacts. It does NOT defend the game — it grades which of the discovered
structures deserve the word "invariant".

Four gauntlet tests, each a score 0-1 + verdict:

    1. NULL-MODEL CONTROL (the kill test) — K shuffled terrains (same
       column-height multiset, positions permuted), same deterministic carve
       procedure, same run seed. Three structure statistics (giant-component
       fraction of the corridor network, entropy of the carved-height
       distribution, carved/solid frontier length per carved cell) compared to
       the null ensemble as z-scores. z < 1.5 => the layout is statistically
       indistinguishable from noise: the landscape is DECORATION. Passing does
       not mean meaningful — it means non-random.
    2. NEIGHBOR FIDELITY — with a source-feature table (--parts json, or the
       game's own chunk manifest as parts-at-chunk-granularity), sample pairs:
       are volume-close pairs also source-close (Spearman rho between volume
       distance and |feature difference|)? Grounded against a label-shuffle
       null. Law density IS one of the three projection axes, so the manifest
       run is a real (coarse) fidelity test, not a proxy.
    3. INVARIANT STABILITY — re-run the carve under 3 reseeds (run #1..#3, the
       game's own fnv1a32(data_hash:runN) ladder). Jaccard overlap of carved
       corridor sets. If structure is seed-dependent, the "invariants" of the
       volume are artifacts of run #1.
    4. SEMANTIC PROBE (the honest one) — the gold invariants (BOOT_CHECK,
       THE CHAIN, THE ROOM): are their positions justified by the source
       (e.g. top law-density chunk) or operator-seeded convention? Names are
       reported as convention-marked regardless; only positions can be earned.

Exact port note: fnv1a32 + mulberry32 + the BFS leak field + carve() are
line-faithful transcriptions of dashboard/static/shadow_walk.html (lines 63-156).
Port proof: fnv1a32("aaad8ddf:1") == 0xba10a605 — the game's recorded run #1 seed.

CLI:
    python -m mag.volume_fidelity <volume.json>
    python -m mag.volume_fidelity <shadow_walk.html> --from-shadow-walk
    flags: --k 20  --pairs 200  --runs 3  --seed 20260906  --parts p.json  --feature NAME

Generic volume.json: {"GX":int,"GZ":int,"H":"<hex string or int list>",
"CORE":[x,z],"SLABW":[x...],"MAN":{"chunks":[{origin,biome,stats...}]}}.

Falsifiers (fold order #1):
    SEED-PORT  — fnv1a32(data_hash:1) must equal 0xba10a605 (recorded run #1).
    NULL-GATE  — a purely random terrain MUST score z<1.5 on STRUCTURE (run the
                 module on any permuted grid and the kill test must say so).
    RESEED     — the stability ladder recomputes from seeds, never from cache.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import re
from collections import Counter, deque
from pathlib import Path

RUN1_SEED_EXPECTED = 0xBA10A605  # recorded run #1 seed (game lore + receipt)
Z_GATE = 1.5                     # kill-test threshold from the commission


# ---------------------------------------------------------------- ported RNG/hash
def fnv1a32(s: str) -> int:
    """FNV-1a 32-bit over JS charCodes — line-faithful port of the game's hash."""
    h = 0x811C9DC5
    for ch in s:
        h ^= ord(ch)
        h = (h * 0x01000193) & 0xFFFFFFFF
    return h


def mulberry32(seed: int):
    """mulberry32 — line-faithful port of the game's rng() (signed-imul via masks)."""
    state = seed & 0xFFFFFFFF

    def nxt() -> float:
        nonlocal state
        state = (state + 0x6D2B79F5) & 0xFFFFFFFF
        t = state ^ (state >> 15)
        t = (t * ((1 | state) & 0xFFFFFFFF)) & 0xFFFFFFFF
        t = (((t + ((t ^ (t >> 7)) * ((61 | t) & 0xFFFFFFFF)) & 0xFFFFFFFF)
              & 0xFFFFFFFF) ^ t) & 0xFFFFFFFF
        return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 4294967296

    return nxt


# ---------------------------------------------------------------- game algorithm
def solve_field(gx: int, gz: int, h0: list, core: list) -> list:
    """BFS leak field from the core: cost 1 on solid, 4 through void (SPFA)."""
    field = [32000] * (gx * gz)
    start = core[1] * gx + core[0]
    field[start] = 0
    q = deque([start])
    nb = ((1, 0), (-1, 0), (0, 1), (0, -1))
    while q:
        i = q.popleft()
        d = field[i]
        x, y = i % gx, i // gx
        for dx, dy in nb:
            nx, ny = x + dx, y + dy
            if not (0 <= nx < gx and 0 <= ny < gz):
                continue
            j = ny * gx + nx
            if h0[j] <= 0:
                if field[j] > d + 4:
                    field[j] = d + 4
                    q.append(j)
                continue
            if field[j] <= d + 1:
                continue
            field[j] = d + 1
            q.append(j)
    return field


def carve(gx: int, gz: int, h0: list, field: list, core: list, slabw, seed: int):
    """Line-faithful port of the game's carve(): 14 field-descending corridors,
    slab doors, 3 forced dead-end spurs, ridge raises, organ monoliths.
    Returns (carveH, corridor_set, organs)."""
    carve_h = list(h0)
    organs = []
    rng = mulberry32(seed)
    crossed = set()
    cand = [i for i in range(gx * gz)
            if h0[i] > 0 and field[i] < 31000 and field[i] > 6]
    cand.sort(key=lambda i: field[i])  # stable, like ES2019 Array.sort
    picks = []
    pool = cand[:220]
    while len(picks) < 14 and pool:
        k = int(rng() * len(pool))
        i = pool.pop(k)
        ok = True
        for p in picks:
            dx = (p % gx) - (i % gx)
            dy = (p // gx) - (i // gx)
            if dx * dx + dy * dy < 100:
                ok = False
                break
        if ok:
            picks.append(i)
    corridor = set()
    for s in picks:
        i = s
        guard = 4000
        core_idx = core[1] * gx + core[0]
        path = []
        while i != core_idx and guard > 0:
            guard -= 1
            path.append(i)
            x, y = i % gx, i // gx
            best, bd = -1, field[i]
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if not dx and not dy:
                        continue
                    nx, ny = x + dx, y + dy
                    if not (0 <= nx < gx and 0 <= ny < gz):
                        continue
                    j = ny * gx + nx
                    if h0[j] > 0 and field[j] < bd:
                        bd = field[j]
                        best = j
            if best < 0:
                organs.append(i)
                break
            i = best
        for j in path:
            carve_h[j] = 1
            corridor.add(j)
            x = j % gx
            if x in slabw:
                crossed.add(x)
                for dz in (-1, 0, 1):
                    jj = ((j // gx) + dz) * gx + x
                    if 0 <= jj < gx * gz and h0[jj] > 0:
                        carve_h[jj] = 1
                        corridor.add(jj)
    for _ in range(3):  # forced dead-end spurs
        i = cand[int(rng() * len(cand))]
        x, y = i % gx, i // gx
        d = ((1, 0), (-1, 0), (0, 1), (0, -1))[int(rng() * 4)]
        for _s in range(6 + int(rng() * 6)):
            x += d[0]
            y += d[1]
            if x < 1 or y < 1 or x >= gx - 1 or y >= gz - 1 or h0[y * gx + x] <= 0:
                break
            carve_h[y * gx + x] = 1
            corridor.add(y * gx + x)
        organs.append(y * gx + x)
        i2 = y * gx + x  # JS reads/writes raw linear indices: wrap or undefined no-op
        if 0 <= i2 < gx * gz and carve_h[i2] < 2:
            carve_h[i2] = 1
    for x in slabw:  # raise slab ridges where no corridor crossed
        for y in range(gz):
            i = y * gx + x
            if h0[i] > 0 and x not in crossed and carve_h[i] > 1:
                carve_h[i] = min(13, carve_h[i] + 1)
    for i in organs:  # organs become monoliths (out-of-range organ = JS undefined)
        if 0 <= i < gx * gz and h0[i] > 0:
            carve_h[i] = min(15, carve_h[i] + 3)
    return carve_h, corridor, organs


# ---------------------------------------------------------------- statistics
def _shannon_bits(values) -> float:
    n = len(values)
    if not n:
        return 0.0
    ent = 0.0
    for c in Counter(values).values():
        p = c / n
        ent -= p * math.log2(p)
    return ent


def structure_stats(carve_h: list, corridor: set, gx: int, gz: int) -> dict:
    """The three structure statistics compared against the null ensemble."""
    n_carved = len(corridor)
    # giant component of the corridor network, 4-connected
    seen, best_cc = set(), 0
    for start in corridor:
        if start in seen:
            continue
        size, q = 0, deque([start])
        seen.add(start)
        while q:
            i = q.popleft()
            size += 1
            x, y = i % gx, i // gx
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if 0 <= nx < gx and 0 <= ny < gz:
                    j = ny * gx + nx
                    if j in corridor and j not in seen:
                        seen.add(j)
                        q.append(j)
        best_cc = max(best_cc, size)
    gc_frac = best_cc / max(1, n_carved)
    # entropy of the carved-height distribution over solid terrain
    solid = [v for v in carve_h if v > 0]
    ent = _shannon_bits(solid)
    # frontier: carved(==1) / solid(>1) adjacency, unordered pairs counted once
    frontier = 0
    for i in corridor:
        x, y = i % gx, i // gx
        for dx, dy in ((1, 0), (0, 1)):  # right + down neighbor only = unordered
            nx, ny = x + dx, y + dy
            if 0 <= nx < gx and 0 <= ny < gz:
                j = ny * gx + nx
                if carve_h[j] > 1:
                    frontier += 1
    return {"carved_n": n_carved, "gc_frac": gc_frac, "entropy": ent,
            "frontier_per_carved": frontier / max(1, n_carved)}


def _zscore(actual: float, nulls: list) -> float:
    if len(nulls) < 2:
        return 0.0
    m = sum(nulls) / len(nulls)
    var = sum((v - m) ** 2 for v in nulls) / (len(nulls) - 1)
    sd = math.sqrt(var)
    if sd == 0:
        return 0.0 if actual == m else float("inf")
    return (actual - m) / sd


def _ranks(vals):
    order = sorted(range(len(vals)), key=lambda i: vals[i])
    ranks = [0.0] * len(vals)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and vals[order[j + 1]] == vals[order[i]]:
            j += 1
        avg = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def spearman(a, b) -> float:
    if len(a) < 3:
        return 0.0
    ra, rb = _ranks(a), _ranks(b)
    ma, mb = sum(ra) / len(ra), sum(rb) / len(rb)
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    da = math.sqrt(sum((x - ma) ** 2 for x in ra))
    db = math.sqrt(sum((y - mb) ** 2 for y in rb))
    if da == 0 or db == 0:
        return 0.0
    return num / (da * db)


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


# ---------------------------------------------------------------- loaders
def _heights(spec, n: int) -> list:
    if isinstance(spec, list):
        return [int(v) for v in spec]
    return [int(ch, 16) for ch in spec[:n]]


def load_volume(path: str, from_shadow_walk: bool) -> dict:
    text = Path(path).read_text(encoding="utf-8")
    if from_shadow_walk:
        m = re.search(r"const WALK=(\{.*?\});", text, re.S)
        if not m:
            raise SystemExit("no `const WALK={...};` found in the html")
        w = json.loads(m.group(1))
        gx, gz = w["GX"], w["GZ"]
        vol = {
            "gx": gx, "gz": gz, "h0": _heights(w["H"], gx * gz),
            "core": w["CORE"], "slabw": set(w["SLABW"]), "hash": w["HASH"],
            "chunks": w.get("MAN", {}).get("chunks", []),
            # anchors read from placeObjects(): BOOT_CHECK=SPAWN_B, THE CHAIN=CORE,
            # THE ROOM=SPAWN_W (weights annex)
            "anchors": [
                {"name": "BOOT_CHECK", "x": w["SPAWN_B"][0], "z": w["SPAWN_B"][2]},
                {"name": "THE CHAIN", "x": w["CORE"][0] + 0.5, "z": w["CORE"][1] + 0.5},
                {"name": "THE ROOM", "x": w["SPAWN_W"][0], "z": w["SPAWN_W"][2]},
            ],
        }
        if len(vol["h0"]) < gx * gz:
            raise SystemExit("H shorter than GX*GZ")
        return vol
    w = json.loads(text)
    gx, gz = int(w["GX"]), int(w["GZ"])
    return {"gx": gx, "gz": gz, "h0": _heights(w["H"], gx * gz),
            "core": w.get("CORE"), "slabw": set(w.get("SLABW", [])),
            "hash": w.get("HASH", ""), "chunks": w.get("MAN", {}).get("chunks", []),
            "anchors": w.get("anchors", [])}


# ---------------------------------------------------------------- gauntlet tests
def test_null_model(vol: dict, k: int, base_seed: int, run_seed: int) -> dict:
    gx, gz, h0, core, slabw = vol["gx"], vol["gz"], vol["h0"], vol["core"], vol["slabw"]
    field = solve_field(gx, gz, h0, core)
    ch, corr, _ = carve(gx, gz, h0, field, core, slabw, run_seed)
    real = structure_stats(ch, corr, gx, gz)
    keys = ("gc_frac", "entropy", "frontier_per_carved")
    nulls = {k2: [] for k2 in keys}
    for c in range(k):
        perm = list(h0)
        random.Random(base_seed + c).shuffle(perm)
        f2 = solve_field(gx, gz, perm, core)
        ch2, corr2, _ = carve(gx, gz, perm, f2, core, slabw, run_seed)
        st = structure_stats(ch2, corr2, gx, gz)
        for k2 in keys:
            nulls[k2].append(st[k2])
    zmap = {k2: _zscore(real[k2], nulls[k2]) for k2 in keys}
    zmap = {k2: (0.0 if z == float("inf") else z) for k2, z in zmap.items()}
    z_struct = sum(zmap.values()) / len(zmap)
    above = z_struct >= Z_GATE
    return {"real": real, "z": zmap, "z_struct": z_struct, "above": above,
            "null_means": {k2: sum(v) / len(v) for k2, v in nulls.items()},
            "verdict": ("z=%.2f above null — the layout is not noise" % z_struct
                        if above else
                        "z=%.2f — decoration until proven otherwise" % z_struct)}


def test_neighbor_fidelity(vol: dict, pairs: int, seed: int, parts=None,
                           feature: str = "") -> dict:
    """Volume-close pairs should also be source-close. Feature table: explicit
    --parts json {id:{x,z,features:{...}}} or the chunk manifest (mean_law)."""
    rows = []
    if parts:
        feat_keys = None
        for pid, p in parts.items():
            feats = p.get("features", {})
            if not feats:
                continue
            if feat_keys is None:
                feat_keys = sorted(feats) if not feature else [feature]
            rows.append((float(p["x"]), float(p["z"]),
                         float(feats[feat_keys[0]])))
    else:
        for c in vol["chunks"]:
            st = c.get("stats", {})
            if st.get("points", 0) > 0 and "mean_law" in st:
                rows.append((c["origin"][0] + 8, c["origin"][1] + 8,
                             float(st["mean_law"])))
    if len(rows) < 8:
        return {"skipped": "no source-feature table with enough rows"}
    rng = random.Random(seed)
    n = len(rows)
    idx = [(i, j) for i in range(n) for j in range(i + 1, n)]
    rng.shuffle(idx)
    idx = idx[:pairs]
    vd = [math.hypot(rows[i][0] - rows[j][0], rows[i][1] - rows[j][1])
          for i, j in idx]
    sd = [abs(rows[i][2] - rows[j][2]) for i, j in idx]
    rho = spearman(vd, sd)
    nulls = []
    for c in range(20):
        vals = [r[2] for r in rows]
        random.Random(seed + 1000 + c).shuffle(vals)
        sd2 = [abs(vals[i] - vals[j]) for i, j in idx]
        nulls.append(spearman(vd, sd2))
    z = _zscore(rho, nulls)
    earned = rho > 0 and z >= Z_GATE
    return {"rho": rho, "z": z, "n_rows": n, "n_pairs": len(idx),
            "feature": "mean_law (manifest)" if not parts else (feature or "first feature"),
            "verdict": ("rho=%.2f (z=%.2f vs label-shuffle) — law gradient is "
                        "spatially carried" % (rho, z) if earned else
                        "rho=%.2f (z=%.2f) — neighborhood law structure NOT carried"
                        % (rho, z))}


def test_stability(vol: dict, runs: int, run_seed_fn) -> dict:
    gx, gz, h0, core, slabw = vol["gx"], vol["gz"], vol["h0"], vol["core"], vol["slabw"]
    sets = []
    for r in range(1, runs + 1):
        f = solve_field(gx, gz, h0, core)  # field is seed-independent
        _, corr, _ = carve(gx, gz, h0, f, core, slabw, run_seed_fn(r))
        sets.append(corr)
    jac = []
    for a in range(runs):
        for b in range(a + 1, runs):
            u = sets[a] | sets[b]
            jac.append(len(sets[a] & sets[b]) / len(u) if u else 1.0)
    j = sum(jac) / len(jac) if jac else 1.0
    if j >= 0.75:
        v = "J=%.2f across reseeds — invariants survive run #1" % j
    elif j >= 0.4:
        v = "J=%.2f — partially seed-bound, treat 'invariants' as soft" % j
    else:
        v = "J=%.2f — artifacts of run #1, not invariants" % j
    return {"jaccard": j, "pairs": jac, "runs": runs, "verdict": v}


def test_semantic(vol: dict) -> dict:
    """Gold invariants: positions source-justified or operator-seeded convention?
    Names are ALWAYS convention-marked; only positions can be earned."""
    chunks = vol["chunks"]
    if not chunks or not vol.get("anchors"):
        return {"skipped": "no manifest/anchors in this volume"}
    law_rows = sorted(
        [(c["stats"]["mean_law"], c["id"]) for c in chunks
         if c.get("stats", {}).get("points", 0) > 0], reverse=True)
    rank_by_id = {cid: r + 1 for r, (_m, cid) in enumerate(law_rows)}
    out = []
    earned_n = 0
    for a in vol["anchors"]:
        hit = None
        for c in chunks:
            ox, oz = c["origin"]
            if ox <= a["x"] < ox + 16 and oz <= a["z"] < oz + 16:
                hit = c
                break
        if not hit:
            out.append({"name": a["name"], "position": "unjustified (off-manifest)"})
            continue
        st = hit.get("stats", {})
        rank = rank_by_id.get(hit["id"])
        if rank is not None and rank <= 3:
            pos = "earned — rank %d/%d chunk by law density" % (rank, len(law_rows))
            earned_n += 1
        elif st.get("points", 0) == 0 and st.get("tensors", 0) > 0:
            pos = "earned-position — weights/tensor annex (0 behavioral points, %d tensors); meaning still convention" % st["tensors"]
            earned_n += 1
        else:
            pos = "convention — ordinary chunk (rank %s), placement is design not data" % rank
        out.append({"name": a["name"], "chunk": hit["id"], "position": pos})
    return {"anchors": out, "earned_n": earned_n, "n_anchors": len(out),
            "verdict": ("semantic=<earned> — %d/%d anchor positions source-justified; "
                        "names remain operator convention" % (earned_n, len(out))
                        if earned_n == len(out) else
                        "semantic=<convention-marked> — %d/%d anchor positions "
                        "source-justified; names are operator convention"
                        % (earned_n, len(out)))}


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(prog="mag.volume_fidelity",
                                 description="HALLUCINATION GAUNTLET — is the volume a hallucination?")
    ap.add_argument("source", help="volume.json or shadow_walk html")
    ap.add_argument("--from-shadow-walk", action="store_true",
                    help="parse the WALK arrays out of the game html")
    ap.add_argument("--k", type=int, default=20, help="null controls")
    ap.add_argument("--pairs", type=int, default=200, help="neighbor pairs sampled")
    ap.add_argument("--runs", type=int, default=3, help="reseed ladder length")
    ap.add_argument("--seed", type=int, default=20260906, help="control RNG base seed")
    ap.add_argument("--parts", default="", help="optional parts json {id:{x,z,features{}}}")
    ap.add_argument("--feature", default="", help="feature key for --parts")
    args = ap.parse_args()

    vol = load_volume(args.source, args.from_shadow_walk)
    solid = sum(1 for v in vol["h0"] if v > 0)
    print("GAUNTLET vs %s — grid %dx%d, %d solid columns, core %s, data_hash %s"
          % (Path(args.source).name, vol["gx"], vol["gz"], solid,
             vol["core"], vol["hash"] or "n/a"))
    if vol["hash"]:
        s1 = fnv1a32(vol["hash"] + ":1")
        tag = "PASS" if s1 == RUN1_SEED_EXPECTED else "FAIL (%08x)" % s1
        print("seed-port falsifier: fnv1a32(%s:1)=%08x vs recorded ba10a605 — %s"
              % (vol["hash"], s1, tag))

    run_seed = lambda r: fnv1a32(vol["hash"] + ":" + str(r)) if vol["hash"] else r

    results = {}
    n1 = test_null_model(vol, args.k, args.seed, run_seed(1))
    results["structure"] = n1
    print("TEST 1 NULL-MODEL CONTROL (K=%d shuffled terrains, same carve, run#1 seed)"
          % args.k)
    print("  real: carved=%d gc_frac=%.3f entropy=%.3f frontier/carved=%.3f"
          % (n1["real"]["carved_n"], n1["real"]["gc_frac"],
             n1["real"]["entropy"], n1["real"]["frontier_per_carved"]))
    print("  null: gc_frac=%.3f entropy=%.3f frontier/carved=%.3f"
          % (n1["null_means"]["gc_frac"], n1["null_means"]["entropy"],
             n1["null_means"]["frontier_per_carved"]))
    print("  z: gc=%+.2f entropy=%+.2f frontier=%+.2f"
          % (n1["z"]["gc_frac"], n1["z"]["entropy"], n1["z"]["frontier_per_carved"]))
    print("  STRUCTURE: " + n1["verdict"])

    parts = None
    if args.parts:
        raw = json.loads(Path(args.parts).read_text(encoding="utf-8"))
        parts = raw.get("parts", raw)
    n2 = test_neighbor_fidelity(vol, args.pairs, args.seed, parts, args.feature)
    results["neighbors"] = n2
    print("TEST 2 NEIGHBOR FIDELITY (%d pairs)" % args.pairs)
    print("  NEIGHBORS: " + n2.get("verdict", n2.get("skipped", "skipped")))

    n3 = test_stability(vol, args.runs, run_seed)
    results["stability"] = n3
    print("TEST 3 INVARIANT STABILITY (%d reseeds)" % args.runs)
    print("  per-pair J: %s" % ", ".join("%.3f" % j for j in n3["pairs"]))
    print("  STABILITY: " + n3["verdict"])

    n4 = test_semantic(vol)
    results["semantic"] = n4
    print("TEST 4 SEMANTIC PROBE (gold invariants)")
    for a in n4.get("anchors", []):
        print("  %-10s @ %s — %s" % (a["name"], a.get("chunk", "?"), a["position"]))
    print("  SEMANTIC: " + n4.get("verdict", n4.get("skipped", "skipped")))

    def _state(n, kind):
        if n.get("skipped"):
            return "SKIPPED"
        if kind == "neighbors":
            return "CARRIED" if n["rho"] > 0 and n["z"] >= Z_GATE else "NOT-CARRIED"
        return "EARNED" if n.get("earned_n") == n.get("n_anchors") else "CONVENTION-MARKED"

    print("GAUNTLET VERDICT: structure %s | neighbors %s | stability J=%.2f | semantic %s"
          % ("NOT-NOISE" if n1["above"] else "DECORATION?",
             _state(n2, "neighbors"), n3["jaccard"], _state(n4, "semantic")))


if __name__ == "__main__":
    main()
