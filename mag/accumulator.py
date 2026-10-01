"""NNUE-style accumulator v0 for a coding agent — patch, don't re-encode.

Falsifier-first (docs/ref/NNUE_ACCUMULATOR_DESIGN_20260904.md, Surface 3):
measurement precedes any real training. The falsifier is stale-facts-per-100-turns
vs a full-log baseline, replayed from room.jsonl traces. THIS FILE IS THE
MEASUREMENT RIG'S DATA STRUCTURE, not a trained model.

What is here:
- Typed sparse feature store keyed (entity, relation, slot), FROZEN starter
  schema for a coding agent (schema rot = noise; freeze before anything else).
- Accumulator: running vector A (d=64, plain ints/floats, stdlib-only). Feature
  rows are deterministic pseudo-random projections of a seeded hash of the
  feature key — W1 is reproducible without a table file.
- Two-axis scoring per active feature: rank = recency x certainty. Facts are
  looked up top-k by that rank (a stale-but-receipted fact can beat a fresh
  but uncertain one).
- Tiny head stub: score(A) -> {"value", "quiescent"} — UNTRAINED placeholder.
  Calibration comes later per the brief's training recipe (supervise on
  trajectory outcomes, temperature-scale, Fishtest A/B vs prompt-only).

Not here yet: decay firing on real rows, certainty fed by real receipts,
seat wiring. Build order per the design note: falsifier measurement first.
"""

import hashlib
import math
from typing import Dict, List, Tuple

# ---------------------------------------------------------------------------
# FROZEN starter schema (v1) — coding agent world features.
# Do not edit casually: feature IDs hash over the key strings; schema rot
# silently changes every row in W1.
# ---------------------------------------------------------------------------
SCHEMA_VERSION = 1
FEATURE_SCHEMA: Dict[str, Tuple[str, str, str]] = {
    "file_open": ("file", "open", "path"),
    "file_modified": ("file", "modified", "path"),
    "test_last_result": ("test", "last_result", "suite"),
    "git_status": ("git", "status", "branch"),
    "tool_last_io": ("tool", "last_io", "tool_name"),
    "constraint_user": ("constraint", "user", "id"),
    "task_current": ("task", "current", "id"),
    "task_blocked": ("task", "blocked", "id"),
}

# recency/certainty defaults per the design note's calibration axis
CERTAINTY_DEFAULT = 0.2   # Unproven floor
CERTAINTY_SUPPORTED = 0.8  # receipted / measured
RECENCY_INITIAL = 1.0

_DIM = 64


def feature_key(schema_id: str, slot_value: str) -> Tuple[str, str, str]:
    ent, rel, _slot = FEATURE_SCHEMA[schema_id]
    return (ent, rel, slot_value)


def _row_from_hash(key: Tuple[str, str, str]) -> List[float]:
    """Deterministic pseudo-random W1 row from a seeded hash of the key.
    Reproducible without a table file: same key -> same row, forever."""
    h = hashlib.blake2b(
        ("|".join(key) + f"|v{SCHEMA_VERSION}").encode(), digest_size=64
    ).digest()
    ints = int.from_bytes(h, "big")
    row = []
    for i in range(_DIM):
        # mulberry32-style 32-bit extraction, deterministic
        chunk = (ints >> (i * 8)) & 0xFF
        row.append((chunk / 255.0) * 2.0 - 1.0)  # uniform-ish in [-1, 1]
    return row


class Accumulator:
    def __init__(self, dim: int = _DIM):
        self.dim = dim
        self.A: List[float] = [0.0] * dim
        self.active: Dict[Tuple[str, str, str], List[float]] = {}

    # -- core NNUE ops ------------------------------------------------------
    def add(self, key: Tuple[str, str, str]) -> None:
        if key in self.active:
            raise ValueError(f"feature already active: {key}")
        row = _row_from_hash(key)
        self.active[key] = row
        for i, r in enumerate(row):
            self.A[i] += r

    def remove(self, key: Tuple[str, str, str]) -> None:
        row = self.active.pop(key)  # KeyError if absent — honest failure
        for i, r in enumerate(row):
            self.A[i] -= r

    def update(self, key: Tuple[str, str, str]) -> None:
        """remove + add with same key: refresh recency, A unchanged."""
        self.remove(key)
        self.add(key)

    def patch(self, delta_spec: List[Tuple[str, str, str, str]]) -> None:
        """delta_spec: list of (op, schema_id, slot_value, op_key) where
        op in {"add","remove"}; op_key disambiguates multiple adds of the same
        schema id by embedding the disambiguator into the slot string."""
        for op, schema_id, slot_value, op_key in delta_spec:
            if op_key:
                slot_value = f"{slot_value}#{op_key}"
            key = feature_key(schema_id, slot_value)
            if op == "add":
                self.add(key)
            elif op == "remove":
                self.remove(key)
            else:
                raise ValueError(f"bad op: {op}")

    # -- verification -------------------------------------------------------
    def rebuild_from_scratch(self) -> None:
        self.A = [0.0] * self.dim
        for key, row in self.active.items():
            for i, r in enumerate(row):
                self.A[i] += r

    def feature_set_hash(self) -> str:
        h = hashlib.blake2b(digest_size=16)
        for key in sorted(self.active):
            h.update(("|".join(key) + ";").encode())
        return h.hexdigest()

    def assert_consistent(self) -> bool:
        """Rebuild and check A matches incrementally-maintained A."""
        saved = list(self.A)
        self.rebuild_from_scratch()
        ok = all(abs(a - b) < 1e-9 for a, b in zip(saved, self.A))
        return ok

    # -- two-axis scoring ---------------------------------------------------
    def _scores(self) -> Dict[Tuple[str, str, str], float]:
        return {
            k: RECENCY_INITIAL * self.certainty.get(k, CERTAINTY_DEFAULT)
            for k in self.active
        }

    def top_k_facts(self, k: int = 3) -> List[Tuple[Tuple[str, str, str], float]]:
        s = self._scores()
        return sorted(s.items(), key=lambda kv: (-kv[1], kv[0]))[:k]


class Session(Accumulator):
    """Accumulator + per-feature (recency, certainty) two-axis metadata."""

    def __init__(self, dim: int = _DIM):
        super().__init__(dim)
        self.recency: Dict[Tuple[str, str, str], float] = {}
        self.certainty: Dict[Tuple[str, str, str], float] = {}

    def add(self, key, certainty: float = CERTAINTY_DEFAULT) -> None:
        super().add(key)
        self.recency[key] = RECENCY_INITIAL
        self.certainty[key] = certainty

    def remove(self, key) -> None:
        super().remove(key)
        self.recency.pop(key, None)
        self.certainty.pop(key, None)

    def set_certainty(self, key, certainty: float) -> None:
        self.certainty[key] = certainty


# ---------------------------------------------------------------------------
# Tiny head stub — UNTRAINED. Deterministic projection only.
# Calibration (temperature scaling, Fishtest A/B) comes later per the brief.
# ---------------------------------------------------------------------------
class HeadStub:
    def __init__(self, dim: int = _DIM, seed: int = 7):
        self.w: List[float] = [
            (math.sin(seed * 0.7 + i * 0.13)) for i in range(dim)
        ]

    def score(self, A: List[float]) -> Dict[str, object]:
        v = sum(a * b for a, b in zip(A, self.w)) / len(A)
        # quiescence proxy: small |value| -> quiet; clearly a placeholder
        return {"value": v, "quiescent": abs(v) < 0.1}


# ---------------------------------------------------------------------------
# Self-test: simulate a coding-agent session, assert invariants.
# ---------------------------------------------------------------------------
def _close(a: List[float], b: List[float], eps: float = 1e-9) -> bool:
    return len(a) == len(b) and all(abs(x - y) < eps for x, y in zip(a, b))


def _run_self_test() -> int:
    fails = 0

    def check(name: str, ok: bool) -> None:
        nonlocal fails
        print(("PASS" if ok else "FAIL") + "  " + name)
        if not ok:
            fails += 1

    s = Session()

    # 1. add 10 features
    feat_keys = [
        feature_key("file_open", "mag/accumulator.py"),
        feature_key("file_open", "docs/ref/NNUE_SIDECAR_BRIEF_20260904.md"),
        feature_key("file_modified", "mag/accumulator.py"),
        feature_key("test_last_result", "mag"),
        feature_key("git_status", "main"),
        feature_key("tool_last_io", "bash"),
        feature_key("constraint_user", "no_chinese_in_replies"),
        feature_key("task_current", "accumulator_v0"),
        feature_key("task_blocked", "calibration_leg"),
        feature_key("file_open", "room.jsonl"),
    ]
    before_10 = list(s.A)
    for k in feat_keys:
        s.add(k)
    check("10 adds moved A", not _close(s.A, before_10))
    check("consistency after 10 adds", s.assert_consistent())

    snapshot_after_10 = list(s.A)

    # 2. patch 3 deltas: file modified, test failed then passed (update)
    s.update(feature_key("file_modified", "mag/accumulator.py"))
    s.update(feature_key("test_last_result", "mag"))
    s.add(feature_key("file_modified", "room.jsonl"))
    check("consistency after patches", s.assert_consistent())
    check("A changed after patches", not _close(s.A, snapshot_after_10))
    check("11 active features (2 in-place updates + 1 add)", len(s.active) == 11)

    # 3. remove 2, then re-add 1: A must return to the pre-remove state
    snapshot_pre_remove = list(s.A)
    k1 = feature_key("tool_last_io", "bash")
    k2 = feature_key("file_open", "room.jsonl")
    s.remove(k1)
    s.remove(k2)
    check("9 active after removals", len(s.active) == 9)
    check("A changed after removals", not _close(s.A, snapshot_pre_remove))
    s.add(k1)
    s.add(k2)  # THE key accumulator invariant: remove-then-re-add restores A
    check("remove-then-re-add returns to prior A", _close(s.A, snapshot_pre_remove))

    # 4. hash mismatch detection after silent mutation
    h_good = s.feature_set_hash()
    s.active[feature_key("git_status", "main")][3] += 1.0  # silent corruption
    h_bad = s.feature_set_hash()
    check(
        "hash unchanged by value mutation (set-hash catches set drift only)",
        h_good == h_bad,
    )
    s.remove(feature_key("git_status", "main"))  # set drift
    check("hash detects set drift", s.feature_set_hash() != h_bad)
    s.add(feature_key("git_status", "main"))
    check("hash restored after re-add", s.feature_set_hash() == h_good)

    # 5. top-k fact lookup ordering: certainty ranks stale-vs-fresh correctly
    s2 = Session()
    fresh_low = feature_key("task_current", "accumulator_v0")  # cert 0.2
    stale_high = feature_key("test_last_result", "mag")  # receipted
    s2.add(fresh_low)  # default certainty 0.2
    s2.add(stale_high, certainty=CERTAINTY_SUPPORTED)
    top = s2.top_k_facts(k=2)
    check(
        "top-k orders by recency x certainty",
        top[0][0] == stale_high and top[1][0] == fresh_low,
    )

    head = HeadStub()
    out = head.score(s2.A)
    check(
        "head stub returns typed score",
        isinstance(out["value"], float) and isinstance(out["quiescent"], bool),
    )

    print(("ALL PASS" if fails == 0 else f"{fails} FAILURES"))
    return fails


if __name__ == "__main__":
    raise SystemExit(1 if _run_self_test() else 0)
