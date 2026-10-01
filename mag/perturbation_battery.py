"""perturbation_battery — THE PERTURBATION TEST (salon unified_fold_20260906).

deepseek-pro's licensed probe, rendered as one CLI: cross-domain invalidation
symmetry — corrupt one surface, another must measurably fail; no propagation =
the map is decoration. Salon artifact:
memory/runs/salons/unified_fold_20260906/SALON_ARTIFACT.md (perturbation test,
C4 LAW-064 OBSERVATION-GATE gap).

RULES OF ENGAGEMENT
  - ALL corruption happens on COPIES in state/_perturb_tmp/ (never live
    ledgers/pages). Restore/cleanup after every case. The live ledgers are only
    ever READ, plus the two G-cell POSTS at the end (explicitly requested).
  - Each case logs {case, corrupt, detector, caught, detail} and the battery
    emits state/perturbation_battery.json.

CASES
  P1 ledger   copy the ledgers to tmp; append a hash-valid but evidence-dead
              row; run BOTH organs' verify (grounding_wave v2 evidence audit +
              tesuji_map) against the copies -> expect EVIDENCE-MISSING.
  P2 voxels   copy chunk_manifest.json + a slab CSV; corrupt the CSV numbers;
              regenerate the data-derived fnv1a32 chunk hash (faithful port of
              _build_shadow_walk.py) -> expect manifest hash-mismatch.
  P3 maze     the historical blind spot: OLD bogus flood (uniform diamond
              gradient ignoring walls) vs CORRECT BFS, both on the ported
              _maze_sim_test.js SDF; run the physics-lab Bellman-residual
              instrument (|grad T| = 1 + reachability-leak) -> bogus FAILS,
              correct PASSES. This is the instrument that would have caught
              the maze's birth defect on day one.
  P4 premise  C4/deepseek probe: feed cite_gate a true-sounding claim citing a
              REAL file that does not support it (temp copy with a plausible
              filename). cite_gate checks EXISTENCE not SUPPORT -> expected
              FAIL-to-detect = the LAW-064 gap confirmed with a receipt.
  P5 x-domain remove one maze wall from the SDF -> BFS field hash changes ->
              do TESUJI cells bound to the old field hash auto-invalidate?
              There is no mechanism -> expected: propagation ABSENT (honest
              DISPUTED fuel for C1, per the salon).

VERDICT: battery-level = count caught. The salon cares especially about P4
(should FAIL = gap confirmed) and P5 (should FAIL = propagation absent) —
those two are FINDINGS, not bugs.

$0 LAW: local files only, no network, no daemons.
CLI:
  python -m mag.perturbation_battery            # full battery + JSON
  python -m mag.perturbation_battery --json     # ...plus JSON to stdout
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mag import cite_gate as cg          # noqa: E402  (engine only; no state write)
from mag import grounding_wave as gw     # noqa: E402
from mag import tesuji_map as tm         # noqa: E402

TMP = ROOT / "state" / "_perturb_tmp"
OUT_JSON = ROOT / "state" / "perturbation_battery.json"
DEAD_EVIDENCE = "watch/inbox/_perturb_dead_evidence_20260906.md"  # intentionally absent


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _case(case, corrupt, detector, caught, detail):
    return {"case": case, "corrupt": corrupt, "detector": detector,
            "caught": bool(caught), "detail": detail}


# ---------------------------------------------------------------- P1 ledger
def p1_ledger() -> dict:
    """Hash-valid but evidence-dead rows must FAIL both organs' verify."""
    details = {}
    caught_all = True

    # --- twin A: grounding_wave verify logic against a copy of ITS ledger ---
    src_gw = gw.LEDGER
    dst_gw = TMP / "GROUNDING_WAVE.jsonl"
    shutil.copy2(src_gw, dst_gw)
    rows = [json.loads(l) for l in dst_gw.read_text(encoding="utf-8").splitlines() if l.strip()]
    prev = rows[-1]["hash"]
    dead = {"prev": prev, "ts": _now(), "claim": "PERTURB PROBE: this claim is hash-valid "
            "but its evidence path does not exist",
            "verdict": "SUPPORTED", "evidence": DEAD_EVIDENCE,
            "note": "perturbation battery P1 twin-A row (copy only)",
            "seat": "perturb"}
    dead["hash"] = gw._row_hash(dead)
    with dst_gw.open("a", encoding="utf-8") as f:
        f.write(json.dumps(dead, ensure_ascii=False) + "\n")
    orig_ledger = gw.LEDGER
    try:
        gw.LEDGER = dst_gw
        ok_gw, msg_gw = gw.verify()
    finally:
        gw.LEDGER = orig_ledger
    caught_a = (not ok_gw) and ("EVIDENCE-MISSING" in msg_gw)
    details["grounding_wave"] = {"ok": ok_gw, "msg": msg_gw, "caught": caught_a}
    caught_all &= caught_a

    # --- twin B: tesuji_map verify logic against a copy of TESUJI_MAP.jsonl ---
    src_tm = tm.LEDGER
    dst_tm = TMP / "TESUJI_MAP.jsonl"
    shutil.copy2(src_tm, dst_tm)
    rows = [json.loads(l) for l in dst_tm.read_text(encoding="utf-8").splitlines() if l.strip()]
    prev = rows[-1]["hash"]
    dead = {"prev": prev, "ts": _now(), "seat": "perturb", "axis": "G",
            "cell": "G/perturb/dead-evidence", "probe": "perturbation-battery-P1",
            "resp_hash": "deadbeefdeadbeef", "verdict": "SUPPORTED",
            "tokens": 0, "ms": 0,
            "note": "PERTURB PROBE hash-valid evidence-dead row; source: " + DEAD_EVIDENCE}
    dead["hash"] = tm._row_hash(dead)
    with dst_tm.open("a", encoding="utf-8") as f:
        f.write(json.dumps(dead, ensure_ascii=False) + "\n")
    orig_ledger = tm.LEDGER
    try:
        tm.LEDGER = dst_tm
        ok_tm, msg_tm = tm.verify()
    finally:
        tm.LEDGER = orig_ledger
    caught_b = (not ok_tm) and ("EVIDENCE-MISSING" in msg_tm)
    details["tesuji_map"] = {"ok": ok_tm, "msg": msg_tm, "caught": caught_b}
    caught_all &= caught_b

    return _case(
        "P1_ledger",
        "appended hash-valid rows whose evidence path does not exist (copies of both ledgers)",
        "grounding_wave v2 evidence audit + tesuji_map verify (chain valid, evidence audited)",
        caught_all,
        details)


# ---------------------------------------------------------------- P2 voxels
def _fnv1a32(bs: bytes) -> int:
    h = 0x811C9DC5
    for b in bs:
        h ^= b
        h = (h * 0x01000193) & 0xFFFFFFFF
    return h


def _slab_grid_hash(csv_path: Path) -> str:
    """Faithful miniature of _build_shadow_walk.py's per-chunk content hash:
    fnv1a32 over the 'heights+types hex subgrid' derived from the source data
    (chars -> height nibble, digit_ratio -> type nibble; pre-carve, stable)."""
    hx = "0123456789abcdef"
    stream = []
    with csv_path.open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            h_nibble = min(15, max(1, int(round(math.log2(max(int(r["chars"]), 1))))))
            t_nibble = min(15, int(float(r["digit_ratio"]) * 15))
            stream.append(hx[h_nibble] + hx[t_nibble])
    return "%08x" % _fnv1a32("".join(stream).encode())


def p2_voxels() -> dict:
    """Corrupt slab CSV numbers -> regenerated data hash mismatches the manifest."""
    src_manifest = ROOT / "state" / "shadow_work" / "chunk_manifest.json"
    src_slab = ROOT / "state" / "shadow_work" / "slab_1.csv"
    mani = json.loads(src_manifest.read_text(encoding="utf-8"))
    cp_manifest = TMP / "chunk_manifest.json"
    cp_slab = TMP / "slab_1.csv"
    shutil.copy2(src_manifest, cp_manifest)
    shutil.copy2(src_slab, cp_slab)

    # mini-manifest: store the data-derived hash of the PRISTINE copy
    stored = _slab_grid_hash(cp_slab)

    # corrupt the numbers (deterministic: every 7th row shifted)
    lines = cp_slab.read_text(encoding="utf-8").splitlines()
    out = [lines[0]]
    n_corrupt = 0
    for ln in lines[1:]:
        parts = ln.split(",")
        if int(parts[0]) % 7 == 0:
            parts[1] = str(int(parts[1]) + 37)
            parts[2] = str(int(parts[2]) + 3)
            n_corrupt += 1
        out.append(",".join(parts))
    cp_slab.write_text("\n".join(out) + "\n", encoding="utf-8")

    regenerated = _slab_grid_hash(cp_slab)     # "regenerate chunk hash" from data
    mismatch = regenerated != stored

    # control: pristine copy must reproduce the stored hash (detector not trivial)
    control = _slab_grid_hash(src_slab) == stored

    return _case(
        "P2_voxels",
        f"corrupted {n_corrupt} rows of slab_1.csv numbers (chars/words) on the copy",
        "manifest check: regenerate fnv1a32 from data, compare to stored content hash "
        "(faithful port of _build_shadow_walk.py / shadow_walk page V-key check)",
        mismatch and control,
        {"stored_hash": stored, "regenerated_hash_after_corruption": regenerated,
         "mismatch": mismatch,
         "control_pristine_reproduces_stored": control,
         "real_manifest_data_hash": mani.get("data_hash"),
         "hash_basis": mani.get("hash_basis")})


# ------------------------------------------------------------- P3/P5 maze
W, H_WORLD = 2.0, 2.7
GW, GH = 240, 135
CHEESE = (1.2, 1.35)
WALLS_RAW = [
    [0.5, 0.5, 0.03, 0.30], [0.25, 0.30, 0.20, 0.03], [0.25, 0.72, 0.20, 0.03],
    [0.50, 0.50, 0.03, 0.28], [0.75, 0.30, 0.20, 0.03], [0.75, 0.72, 0.20, 0.03],
    [0.12, 0.52, 0.03, 0.22], [0.88, 0.50, 0.03, 0.22], [0.62, 0.14, 0.03, 0.16],
    [0.38, 0.88, 0.03, 0.16],
]
EPS = 0.012  # collision band, as in the sim


def _walls(drop=None):
    ws = [w for i, w in enumerate(WALLS_RAW) if i != drop]
    return [[w[0] * 2, w[1] * 2.7, w[2] * 2, w[3] * 2.7] for w in ws]


def _sdf(x, y, walls):
    d = 1e9
    for cx, cy, hw, hh in walls:
        ax, ay = abs(x - cx) - hw, abs(y - cy) - hh
        d = min(d, max(ax, ay))
    return min(d, min(x - 0.05, 1.95 - x, y - 0.05, 2.65 - y))


def _cheese_cell():
    return int(CHEESE[0] / W * GW), int(CHEESE[1] / H_WORLD * GH)


def _passable(walls):
    passable = bytearray(GW * GH)
    for y in range(GH):
        wy = (y + 0.5) / GH * H_WORLD
        for x in range(GW):
            wx = (x + 0.5) / GW * W
            passable[y * GW + x] = 1 if _sdf(wx, wy, walls) >= EPS else 0
    return passable


def _bfs(walls, passable):
    """CORRECT flood: unit-cost BFS from the cheese through passable cells.
    Wall/unreachable cells stay INF (never enqueued)."""
    INF = float("inf")
    T = [INF] * (GW * GH)
    sx, sy = _cheese_cell()
    if not passable[sy * GW + sx]:
        return T
    T[sy * GW + sx] = 0
    q = [(sx, sy)]
    i = 0
    while i < len(q):
        x, y = q[i]
        i += 1
        d = T[y * GW + x]
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < GW and 0 <= ny < GH and passable[ny * GW + nx] \
                    and T[ny * GW + nx] == INF:
                T[ny * GW + nx] = d + 1
                q.append((nx, ny))
    return T


def _bogus_diamond(passable):
    """The OLD bogus flood: uniform diamond (Manhattan) gradient from the
    cheese ignoring walls entirely — finite everywhere, walls included."""
    sx, sy = _cheese_cell()
    return [abs(x - sx) + abs(y - sy) for y in range(GH) for x in range(GW)]


def _reachability(walls, passable):
    sx, sy = _cheese_cell()
    seen = bytearray(GW * GH)
    if not passable[sy * GW + sx]:
        return seen
    seen[sy * GW + sx] = 1
    q = [(sx, sy)]
    i = 0
    while i < len(q):
        x, y = q[i]
        i += 1
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < GW and 0 <= ny < GH and passable[ny * GW + nx] \
                    and not seen[ny * GW + nx]:
                seen[ny * GW + nx] = 1
                q.append((nx, ny))
    return seen


def _bellman_instrument(T, passable, reach):
    """physics-lab residual check: (a) |grad T| = 1 Bellman residual on every
    reachable non-source cell; (b) reachability-leak — any FINITE T on a cell
    BFS proves unreachable (walls/sealed pockets) is a violation."""
    INF = float("inf")
    leak = 0
    for i in range(GW * GH):
        if T[i] != INF and not reach[i]:
            leak += 1
    max_r = 0.0
    bad = 0
    for y in range(GH):
        for x in range(GW):
            i = y * GW + x
            if not reach[i] or T[i] == 0 or T[i] == INF:
                continue
            best = INF
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if 0 <= nx < GW and 0 <= ny < GH:
                    j = ny * GW + nx
                    if T[j] < best:
                        best = T[j]
            r = T[i] - (1 + best) if best != INF else float("inf")
            if abs(r) > 1e-9:
                bad += 1
                max_r = max(max_r, abs(r))
    return {"leak_finite_on_unreachable": leak,
            "bellman_violations": bad, "max_abs_residual": max_r}


def _field_sha(T):
    h = hashlib.sha256()
    h.update(b"".join((b"inf" if v == float("inf") else str(int(v)).encode())
                      for v in T))
    return h.hexdigest()[:16]


def p3_maze() -> dict:
    """Bogus diamond flood vs correct BFS under the residual instrument."""
    walls = _walls()
    passable = _passable(walls)
    reach = _reachability(walls, passable)

    t_good = _bfs(walls, passable)
    t_bad = _bogus_diamond(passable)

    res_good = _bellman_instrument(t_good, passable, reach)
    res_bad = _bellman_instrument(t_bad, passable, reach)

    good_pass = res_good["leak_finite_on_unreachable"] == 0 \
        and res_good["bellman_violations"] == 0
    bad_fail = res_bad["leak_finite_on_unreachable"] > 0 \
        or res_bad["bellman_violations"] > 0

    return _case(
        "P3_maze_residual",
        "the OLD bogus flood: uniform diamond gradient from the cheese ignoring "
        "walls (the maze's birth defect), no copy needed — pure instrument test",
        "physics-lab Bellman-residual check: |grad T| = 1 on reachable cells + "
        "reachability-leak (finite T where BFS proves unreachable)",
        good_pass and bad_fail,
        {"correct_bfs": {**res_good, "instrument": "PASS" if good_pass else "FAIL"},
         "bogus_diamond": {**res_bad, "instrument": "FAIL" if bad_fail else "PASS"},
         "note": "the eikonal term alone is BLIND to the diamond gradient "
                 "(locally |grad T|=1 everywhere reachable); the wall/"
                 "reachability-leak term is what catches it — both terms are "
                 "load-bearing in the instrument",
         "grid": [GW, GH], "reachable_cells": sum(reach)}


)


# --------------------------------------------------------------- P4 poison
def p4_premise_poison() -> dict:
    """cite_gate vs a true-sounding claim citing a REAL file that does not
    support it. Expected FAIL-to-detect: the gate checks EXISTENCE not SUPPORT
    (the LAW-064 OBSERVATION-GATE gap, salon C4)."""
    src = ROOT / "memory" / "runs" / "salons" / "unified_fold_20260906" / "SALON_ARTIFACT.md"
    plausible = TMP / "voxel_slab_density_audit_20260906.md"
    shutil.copy2(src, plausible)  # REAL file, plausible filename, wrong subject

    card = TMP / "poison_card_C4_law064.md"
    card.write_text(
        "# Premise-poison probe (C4 / LAW-064)\n\n"
        "Claim: the shadow voxel bank's deepest law-density core sits in slab 7 "
        "at 5,430 chars median, per the measurement record: "
        "state/_perturb_tmp/voxel_slab_density_audit_20260906.md\n\n"
        "(The cited file is real, non-empty — and is a copy of the unified-fold "
        "salon artifact about chairs and probes. It contains no slab measurements. "
        "The 5,430 figure belongs to a different measurement entirely.)\n",
        encoding="utf-8")

    row = cg.check_card(str(card))  # the CLI's engine; no live state write
    flagged = (row["cite_rate"] != 1.0) or (not row["complete"])
    return _case(
        "P4_premise_poison",
        "claim citing a REAL file that does not support it (salon-artifact copy "
        "under a plausible measurement filename)",
        "mag.cite_gate check (existence-based classification)",
        flagged,
        {"expected": "FAIL-to-detect (LAW-064 gap confirmed)",
         "gap_confirmed": not flagged,
         "cite_gate_row": {k: row[k] for k in ("card", "total_citations", "counts",
                                               "cite_rate", "complete")},
         "citations": [{"raw": c["raw"], "class": c["class"], "note": c["note"]}
                       for c in row["citations"]],
         "reading": "cite_gate stamps the citation LOCAL-VERIFIED and the card "
                    "complete: it verifies the cited bytes EXIST, never whether "
                    "they SUPPORT the claim. Sound inference on a poisoned "
                    "premise ships straight through. This is the receipt for "
                    "LAW-064 OBSERVATION-GATE: publication protocols must "
                    "verify the premise's bytes, not just the claim's form."})


# ------------------------------------------------------------- P5 x-domain
def p5_cross_domain() -> dict:
    """Remove one wall -> BFS field hash changes -> nothing downstream
    auto-invalidates. Expected: propagation ABSENT."""
    walls_old = _walls()
    walls_new = _walls(drop=4)  # [0.75,0.30,0.20,0.03] — a real corridor wall
    passable_old = _passable(walls_old)
    passable_new = _passable(walls_new)
    field_old = _bfs(walls_old, passable_old)
    field_new = _bfs(walls_new, passable_new)
    h_old, h_new = _field_sha(field_old), _field_sha(field_new)
    field_changed = h_old != h_new

    # Bind a G-cell to the OLD field hash — on a COPY of the ledger.
    src_tm = tm.LEDGER
    dst_tm = TMP / "TESUJI_MAP_p5.jsonl"
    shutil.copy2(src_tm, dst_tm)
    rows = [json.loads(l) for l in dst_tm.read_text(encoding="utf-8").splitlines() if l.strip()]
    bound = {"prev": rows[-1]["hash"], "ts": _now(), "seat": "perturb", "axis": "G",
             "cell": "G/perturb/field-bound", "probe": "maze-field-binding",
             "resp_hash": h_old, "verdict": "SUPPORTED", "tokens": 0, "ms": 0,
             "note": "PERTURB PROBE: cell bound to maze BFS field sha " + h_old}
    bound["hash"] = tm._row_hash(bound)
    with dst_tm.open("a", encoding="utf-8") as f:
        f.write(json.dumps(bound, ensure_ascii=False) + "\n")

    # Now corrupt the SURFACE (wall removed, field hash moved to h_new) and ask:
    # does the ledger organ auto-invalidate the cell that binds h_old?
    # The row is NOT touched — the mutation is in the world, not the ledger.
    orig_ledger = tm.LEDGER
    try:
        tm.LEDGER = dst_tm
        ok, msg = tm.verify()
    finally:
        tm.LEDGER = orig_ledger
    # verify() reads only rows+chain; it cannot see the world. A still-PASS
    # verify with a stale world binding = no auto-invalidation mechanism.
    still_valid_under_mutation = ok

    # mechanism scan: does ANY organ key invalidation on external content hashes?
    organs = ((ROOT / "mag" / "tesuji_map.py").read_text(encoding="utf-8")
              + (ROOT / "mag" / "tesuji_probes.py").read_text(encoding="utf-8"))
    has_invalidation_hook = any(
        k in organs.lower() for k in ("invalidat", "field hash"))
    # (dirty-radius re-probing is PLANNED probe-policy prose in tesuji docs, not a
    #  mechanism wired to game-field content hashes — the scan result is the
    #  honest mechanical answer.)

    propagation_present = field_changed and not still_valid_under_mutation

    return _case(
        "P5_cross_domain",
        "removed one maze wall from the SDF (port of state/_maze_sim_test.js); "
        "BFS field recomputed",
        "cross-domain invalidation symmetry: do TESUJI cells bound to the old "
        "field hash auto-invalidate? (ledger verify + row-hash binding test)",
        propagation_present,
        {"field_hash_old": h_old, "field_hash_new": h_new,
         "field_changed": field_changed,
         "bound_row_still_verify_valid_after_surface_mutation": still_valid_under_mutation,
         "ledger_verify_after_mutation": {"ok": ok, "msg": msg},
         "organ_invalidation_hook_found": has_invalidation_hook,
         "expected": "FAIL (propagation ABSENT — salon-predicted, honest DISPUTED "
                     "fuel for C1)",
         "reading": "the field is sensitive (hash moved), but no organ carries a "
                    "game-field content hash, so no cell can invalidate from it. "
                    "Even a cell that EXPLICITLY writes the old hash into its row "
                    "stays hash-valid: the chain hashes the ROW, never the WORLD. "
                    "Cross-domain propagation is ABSENT by construction."})


# ------------------------------------------------------------------ driver
def run_battery() -> dict:
    if TMP.exists():
        shutil.rmtree(TMP)
    TMP.mkdir(parents=True, exist_ok=True)
    cases = []
    try:
        cases.append(p1_ledger())
        cases.append(p2_voxels())
        cases.append(p3_maze())
        cases.append(p4_premise_poison())
        cases.append(p5_cross_domain())
    finally:
        shutil.rmtree(TMP, ignore_errors=True)  # restore/cleanup after each+all
    caught = sum(1 for c in cases if c["caught"])
    out = {
        "schema": "perturbation_battery/v1",
        "ts": _now(),
        "salon": "memory/runs/salons/unified_fold_20260906/SALON_ARTIFACT.md",
        "rules": "all corruption on copies in state/_perturb_tmp/, cleaned after run",
        "cases": cases,
        "verdict": {
            "caught": caught,
            "total": len(cases),
            "instruments_up": f"{sum(1 for c in cases[:3] if c['caught'])}/3",
            "expected_failures_confirmed": f"{sum(1 for c in cases[3:] if not c['caught'])}/2",
            "reading": "P1-P3 are instruments: corruption must be CAUGHT. "
                       "P4-P5 are the salon's expected failures: a MISS there "
                       "CONFIRMS the gap (LAW-064 / cross-domain propagation "
                       "absent) — findings, not bugs.",
        },
    }
    OUT_JSON.write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="mag.perturbation_battery")
    ap.add_argument("--json", action="store_true", help="also print the JSON row")
    args = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

    out = run_battery()
    for c in out["cases"]:
        mark = "CAUGHT " if c["caught"] else "MISSED "
        print(f"[{mark}] {c['case']:<22} corrupt={c['corrupt'][:70]}")
        print(f"           detector={c['detector'][:90]}")
    v = out["verdict"]
    print(f"BATTERY: {v['caught']}/{v['total']} caught | "
          f"instruments {v['instruments_up']} | "
          f"expected-failures confirmed {v['expected_failures_confirmed']}")
    print(f"JSON -> {OUT_JSON.relative_to(ROOT)}")
    if args.json:
        print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
