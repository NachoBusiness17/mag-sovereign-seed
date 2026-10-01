"""bare_numpy — OUR OWN minimal numerical core (bare-metal, self-stolen, zero deps).

OPERATOR (2026-08-12): "can we make our own numpy?" — YES, right-sized. We don't clone numpy (a
C BLAS/LAPACK library); we build the MINIMAL numerical core covering the ops WE actually use, so
the moonshot/render path is fully OURS — no external binary required. Same doctrine as the render
stack: bare-metal first, optional adapter (numpy) if present.

THE CORE (pure Python, deterministic + $0, zero deps):
  BArray        — a minimal 1D/2D numeric array backed by Python lists.
  zeros/ones/from_list — array construction (deterministic).
  elementwise   — add/sub/mul/div (vectorized, list-based).
  mean/min/max  — reductions.
  normalize     — unit-vector / range-0..1 (for fields/embeddings).
  dot           — matrix-vector product (for fields).
  apply         — element-wise function (for the flock/world gradient).
  OPTIONAL: if numpy is present, heavy ops can dispatch to it (adapter, never a requirement).

Schema: bare_numpy.v1
"""
from __future__ import annotations

import math
import operator
from typing import Any, Callable, Iterable, Sequence

SCHEMA = "bare_numpy.v1"


class BArray:
    """A minimal 2D numeric array (list of lists). Deterministic, $0, zero deps."""

    __slots__ = ("rows", "cols", "data")

    def __init__(self, data: Sequence[Sequence[float]] | Sequence[float]):
        if data and isinstance(data[0], (list, tuple)):
            self.data = [list(map(float, r)) for r in data]
            self.rows = len(self.data)
            self.cols = len(self.data[0]) if self.data else 0
        else:
            self.data = [list(map(float, data))]  # 1 row (1D treated as 1xN)
            self.rows = 1
            self.cols = len(self.data[0]) if self.data else 0

    def shape(self) -> tuple[int, int]:
        return (self.rows, self.cols)

    def get(self, r: int, c: int) -> float:
        return self.data[r][c]

    def flat(self) -> list[float]:
        return [v for row in self.data for v in row]

    def to_list(self) -> list[list[float]]:
        return [list(r) for r in self.data]

    def _elem(self, other: Any, op: Callable[[float, float], float]) -> "BArray":
        if isinstance(other, BArray):
            if (self.rows, self.cols) != (other.rows, other.cols):
                raise ValueError("shape mismatch")
            data = [[op(a, b) for a, b in zip(ra, rb)]
                    for ra, rb in zip(self.data, other.data)]
        else:
            s = float(other)
            data = [[op(v, s) for v in r] for r in self.data]
        return BArray(data)

    def __add__(self, other: Any) -> "BArray":
        return self._elem(other, operator.add)

    def __sub__(self, other: Any) -> "BArray":
        return self._elem(other, operator.sub)

    def __mul__(self, other: Any) -> "BArray":
        return self._elem(other, operator.mul)

    def __truediv__(self, other: Any) -> "BArray":
        return self._elem(other, operator.truediv)

    def __eq__(self, other: Any) -> bool:  # type: ignore[override]
        if not isinstance(other, BArray):
            return False
        return self.to_list() == other.to_list()

    def __repr__(self) -> str:
        return f"BArray(rows={self.rows}, cols={self.cols})"


# ── construction ─────────────────────────────────────────────────────────────
def zeros(rows: int, cols: int = 1) -> BArray:
    return BArray([[0.0] * cols for _ in range(rows)])


def ones(rows: int, cols: int = 1) -> BArray:
    return BArray([[1.0] * cols for _ in range(rows)])


def from_list(data: Sequence[Sequence[float]] | Sequence[float]) -> BArray:
    return BArray(data)


# ── reductions (deterministic, $0) ───────────────────────────────────────────
def mean(a: BArray) -> float:
    f = a.flat()
    return sum(f) / len(f) if f else 0.0


def amin(a: BArray) -> float:
    return min(a.flat())


def amax(a: BArray) -> float:
    return max(a.flat())


def normalize(a: BArray) -> BArray:
    """Range-normalize to 0..1 per element-row (for fields/embeddings). Deterministic."""
    out = []
    for r in a.data:
        lo, hi = min(r), max(r)
        rng = (hi - lo) or 1.0
        out.append([(v - lo) / rng for v in r])
    return BArray(out)


def dot(a: BArray, v: Sequence[float]) -> list[float]:
    """Matrix-vector product: a (RxC) x v (C) -> length R. For fields/gradients."""
    vv = list(map(float, v))
    if a.cols != len(vv):
        raise ValueError("dot: inner dims mismatch")
    return [sum(x * y for x, y in zip(row, vv)) for row in a.data]


def apply(a: BArray, fn: Callable[[float], float]) -> BArray:
    """Element-wise function (the flock/world gradient operator)."""
    return BArray([[fn(v) for v in r] for r in a.data])


def magnitude(a: BArray) -> float:
    return math.sqrt(sum(v * v for v in a.flat()))


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "contract": "minimal bare-metal numeric core (BArray + zeros/ones/from_list + "
                        "elementwise + mean/min/max + normalize + dot + apply). Pure Python, "
                        "$0, zero deps; numpy optional adapter.",
            "ops": ["BArray", "zeros", "ones", "from_list", "mean", "amin", "amax",
                    "normalize", "dot", "apply", "magnitude"]}
