"""Falsifier harness for the registry auto-heal fix (mag/percolator.py, 2026-09-06).

Closes the RECURRING registry-wipe amnesia class (watch/inbox/INVARIANTS_SHRINK_FORENSICS_20260906.md)
plus the GAP-2 partial-loss falsifier (memory/runs/salons/astra_gap_v2_20260906/ANSWER.md:
"removing one sealed generation leaves a silently healthy load" — the >50% count gate cannot
detect partial loss; the trigger is now a per-generation ID diff against the newest seal,
watch/inbox/SEAL_CHECK_20260906.md).
Runs against a TEMP copy of the registry + seals — the live invariants.json is never touched.

Cases:
  (a)  registry missing  -> load auto-heals from newest seal -> generations restored
  (b)  registry shrunken (<50% of seal gens) -> heals (seal ∪ live merged, shared counts
       MAX-merged — Z15 2026-09-29: SUM triple-counted on repeated heals; MAX is idempotent)
  (c)  healthy load (live ⊇ seal IDs) -> no heal triggered (no surprise overwrites)
  (d)  ONE sealed generation removed from an otherwise-healthy live copy (>50% by count,
       so the OLD code missed it) -> the missing generation is RESTORED (gap-2 falsifier)

Usage: python -m mag.percolator_heal_test   (exit 0 = all pass)
Schema: percolator.v1 · deterministic + $0 · deps: stdlib only
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mag import percolator  # noqa: E402

FAILURES: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  [{detail}]" if detail and not cond else ""))
    if not cond:
        FAILURES.append(name)


def make_world(tmp: Path, seal_gens: dict, live_raw: str | None) -> tuple[Path, Path]:
    """Temp seal snapshot + optional live registry file; patch module paths onto it."""
    seals = tmp / "memory" / "seals" / "2026-09-06T01-40-13" / "memory" / "percolator"
    seals.mkdir(parents=True)
    (seals / "invariants.json").write_text(
        json.dumps({"invariants": seal_gens, "false_positives": 2}, ensure_ascii=False), encoding="utf-8")
    reg = tmp / "memory" / "percolator"
    reg.mkdir(parents=True, exist_ok=True)
    if live_raw is not None:
        (reg / "invariants.json").write_text(live_raw, encoding="utf-8")
    percolator.SEALS_DIR = tmp / "memory" / "seals"
    percolator.INVARIANT_REGISTRY = reg / "invariants.json"
    return reg, seals / "invariants.json"


def seal_gens6() -> dict:
    return {f"S{i}": {"text": f"gen {i}", "count": i * 10, "first_seen": "2026-09-05T01:00:00Z",
                      "last_seen": "2026-09-06T01:40:13Z", "domain": "test"} for i in range(1, 7)}


def main() -> int:
    base = Path(tempfile.mkdtemp(prefix="percolator_heal_test_"))
    print(f"harness root: {base}")

    # ── (a) registry MISSING -> auto-heal from newest seal ────────────────────
    print("(a) registry missing -> heal from seal")
    reg_dir, _ = make_world(base / "a", seal_gens6(), None)
    got = percolator._load_registry()
    check("a1 gens restored from seal", len(got["invariants"]) == 6, str(len(got["invariants"])))
    check("a2 seal counts intact", got["invariants"]["S3"]["count"] == 30)
    check("a3 heal logged (never silent)",
          (reg_dir / "heal.log").is_file()
          and "auto-healed 6 generations from" in (reg_dir / "heal.log").read_text(encoding="utf-8"))
    check("a4 load did not write the live file", not percolator.INVARIANT_REGISTRY.exists())

    # ── (a2) registry EMPTY (0 bytes, the wipe signature) -> heal ─────────────
    print("(a2) registry empty -> heal from seal")
    reg_dir, _ = make_world(base / "a2", seal_gens6(), "")
    got = percolator._load_registry()
    check("a2.1 empty file heals", len(got["invariants"]) == 6)
    check("a2.2 heal logged", "auto-healed 6" in (reg_dir / "heal.log").read_text(encoding="utf-8"))

    # ── (b) registry SHRUNKEN (<50% of seal) -> heal, seal ∪ live merged ──────
    print("(b) registry shrunken -> heal + merge")
    live = {"invariants": {
        "S1": {"text": "gen 1", "count": 3, "first_seen": "2026-09-06T08:49:55Z", "last_seen": "2026-09-06T17:00:00Z", "domain": "test"},
        "X1": {"text": "fresh post-wipe gen", "count": 7, "first_seen": "2026-09-06T08:49:55Z", "last_seen": "2026-09-06T17:00:00Z", "domain": "test"},
    }, "false_positives": 5}
    reg_dir, _ = make_world(base / "b", seal_gens6(), json.dumps(live, ensure_ascii=False))
    before = percolator.INVARIANT_REGISTRY.read_bytes()
    got = percolator._load_registry()
    check("b1 heal triggered (2*2 < 6)", len(got["invariants"]) == 7, str(sorted(got["invariants"])))
    # Z15 (2026-09-29): shared counts merge by MAX(10,3)=10, not SUM(13) — SUM re-added the
    # sealed count on every heal event (the heal.log repeats), MAX is idempotent under
    # repeated heals. Falsified live: heal.log 2026-09-06..09-26 shows 4 heals off one seal.
    check("b2 shared count MAX-merged max(10,3)", got["invariants"]["S1"]["count"] == 10)
    check("b3 live-only gen kept", got["invariants"]["X1"]["count"] == 7)
    check("b4 seal gens intact", got["invariants"]["S6"]["count"] == 60)
    check("b5 false_positives maxed", got["false_positives"] == 5)
    check("b6 heal logged", "auto-healed 7" in (reg_dir / "heal.log").read_text(encoding="utf-8"))
    check("b7 load did not overwrite live file",
          percolator.INVARIANT_REGISTRY.read_bytes() == before)

    # ── (c) HEALTHY load (live ⊇ seal IDs) -> NO heal ─────────────────────────
    # Fixture note: the pre-gap-2 (c) fixture held 4/6 seal gens — "healthy" only under the
    # 50% shortcut, i.e. exactly the partial-loss state gap-2 says MUST heal (now case d).
    # Healthy under the ID diff = live contains every sealed generation ID.
    print("(c) healthy load (live superset of seal IDs) -> no heal, no surprise overwrite")
    healthy_gens = {k: dict(v, count=v["count"] + 5, last_seen="2026-09-07T00:00:00Z")
                    for k, v in seal_gens6().items()}
    healthy_gens["X1"] = {"text": "live-only gen, post-seal accrual", "count": 9,
                          "first_seen": "2026-09-06T08:49:55Z",
                          "last_seen": "2026-09-07T00:00:00Z", "domain": "test"}
    healthy = {"invariants": healthy_gens, "false_positives": 9}
    reg_dir, _ = make_world(base / "c", seal_gens6(), json.dumps(healthy, ensure_ascii=False))
    before = percolator.INVARIANT_REGISTRY.read_bytes()
    got = percolator._load_registry()
    check("c1 no heal: exact live content returned",
          got["invariants"] == healthy["invariants"] and got["false_positives"] == 9)
    check("c2 no heal log written", not (reg_dir / "heal.log").exists())
    check("c3 live file byte-identical", percolator.INVARIANT_REGISTRY.read_bytes() == before)

    # ── (d) GAP-2: ONE sealed generation removed from an otherwise-healthy copy ─
    # live = the seal content minus S6 -> 5/6 = 83% by count: the OLD 50%-only gate PASSED
    # this file and silently kept the loss. The ID diff must restore S6.
    print("(d) gap-2: one sealed gen removed (>50% healthy) -> restored by ID diff")
    partial_gens = {k: dict(v) for k, v in seal_gens6().items() if k != "S6"}
    live = {"invariants": partial_gens, "false_positives": 3}
    reg_dir, _ = make_world(base / "d", seal_gens6(), json.dumps(live, ensure_ascii=False))
    before = percolator.INVARIANT_REGISTRY.read_bytes()
    check("d0 old 50% gate would have passed (5*2 >= 6)", len(partial_gens) * 2 >= 6)
    got = percolator._load_registry()
    check("d1 missing generation RESTORED (6/6)", len(got["invariants"]) == 6,
          str(sorted(got["invariants"])))
    check("d2 restored gen intact from seal", got["invariants"]["S6"]["count"] == 60)
    check("d3 survivors kept, shared counts MAX-merged (Z15 2026-09-29: max(10,10)=10, not 10+10)",
          got["invariants"]["S1"]["count"] == 10 and got["invariants"]["S5"]["count"] == 50
          and set(got["invariants"]) == set(seal_gens6()))
    check("d4 heal logged (never silent)",
          "auto-healed 6" in (reg_dir / "heal.log").read_text(encoding="utf-8"))
    check("d5 load did not overwrite live file",
          percolator.INVARIANT_REGISTRY.read_bytes() == before)

    # ── atomic save (the writer half of the fix) ───────────────────────────────
    print("save: atomic temp+os.replace")
    percolator._save_registry(seal_gens6())
    saved = json.loads(percolator.INVARIANT_REGISTRY.read_text(encoding="utf-8"))
    check("s1 saved file valid + complete", len(saved) == 6)
    leftovers = [p.name for p in percolator.INVARIANT_REGISTRY.parent.glob("*.tmp")]
    check("s2 no .tmp leftovers", not leftovers, str(leftovers))

    shutil.rmtree(base, ignore_errors=True)
    print(f"\n{'ALL PASS' if not FAILURES else 'FAILED: ' + ', '.join(FAILURES)}")
    return 0 if not FAILURES else 1


if __name__ == "__main__":
    sys.exit(main())
