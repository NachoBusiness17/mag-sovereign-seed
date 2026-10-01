"""lattice_distance — Legendre three-square invariant for lattice/voxel spaces.

On the 3D integer lattice Z^3, the distance between two points is
sqrt(dx^2 + dy^2 + dz^2), so every on-grid squared distance is a sum of
three squares.  Legendre's three-square theorem: a non-negative integer n
is a sum of three squares iff n is NOT of the form 4^a * (8b + 7).

Consequence (falsifier-class): on-grid distances can ONLY ever measure
sqrt of numbers outside that family.  sqrt(7), sqrt(15), sqrt(23),
sqrt(28), sqrt(31), sqrt(39)... NEVER appear between lattice points.
If a claimed on-grid pair measures sqrt(7), the grid is broken or the
space is not Z^3.

Provenance: intake card watch/INTAKE_LEGENDRE_LATTICE_20260904.md (15/25
BUILD WINDOWED; tweet math hand-verified before filing: 7 = 4^0(8*0+7)
excluded, 14 = 1+4+9 lives).  Zero dependencies.  Consumers: maze_arena
gate law, mesh-baker GLB voxel sanity, dungeon "impossible distances" room.

Note the boundary honestly: two integer lattice points can never produce
an excluded squared distance (dx^2+dy^2+dz^2 is ITSELF a three-square
decomposition).  The validator earns its keep on PARSED data — GLB floats,
scaled/quantized grids — where the "on-grid" claim is the thing under test.
"""
from __future__ import annotations

import itertools
import math
from typing import Iterable, Sequence

__all__ = ["is_three_square", "excluded_form", "lattice_distance_ok", "validate_voxel_coords"]

_INT_TOL = 1e-9


def _as_int(n) -> int | None:
    """Coerce to int if n is an integer value (int or near-integral float)."""
    if isinstance(n, bool):
        return None
    if isinstance(n, int):
        return n
    if isinstance(n, float) and math.isfinite(n):
        r = round(n)
        if abs(n - r) <= _INT_TOL:
            return int(r)
    return None


def is_three_square(n) -> bool:
    """True iff n is a sum of three squares (of integers >= 0).

    By Legendre's three-square theorem: True iff n is NOT of the form
    4^a * (8b + 7) with a, b >= 0.  Negative n -> False.  n = 0 -> True
    (0 = 0 + 0 + 0).  Integral floats (7.0) are accepted; anything else
    that is not an integer value -> False (a non-integer can never be a
    sum of integer squares).
    """
    k = _as_int(n)
    if k is None or k < 0:
        return False
    if k == 0:
        return True
    while k % 4 == 0:
        k //= 4
    return k % 8 != 7


def excluded_form(n) -> tuple[int, int] | None:
    """If n is of the form 4^a * (8b + 7), return (a, b); else None."""
    k = _as_int(n)
    if k is None or k <= 0:
        return None
    a = 0
    while k % 4 == 0:
        k //= 4
        a += 1
    if k % 8 == 7:
        return (a, (k - 7) // 8)
    return None


def lattice_distance_ok(d2) -> bool:
    """True iff d2 (a squared distance) is a representable lattice distance.

    d2 must be a non-negative integer value and NOT of the excluded
    4^a*(8b+7) family.  Non-integer or negative d2 -> False: such a
    distance can never occur between two points of Z^3 either.
    """
    k = _as_int(d2)
    if k is None or k < 0:
        return False
    return is_three_square(k)


def validate_voxel_coords(coords: Iterable[Sequence[float]]) -> dict:
    """Check point pairs of a claimed voxel grid against the Z^3 invariant.

    Given an iterable of 3-tuples (integers, or parsed floats claiming to
    sit on the integer grid), returns::

        {"ok": bool, "violations": [...], "pairs_checked": int}

    Each violation is a point pair whose squared distance is an integer in
    the excluded 4^a*(8b+7) family — e.g. a measured sqrt(7) between
    supposedly on-grid voxels, which proves the space is NOT the true Z^3
    lattice.  Violation rows carry the pair, d2, and the (a, b) form so a
    UI can name the curse: {"a": p0, "b": p1, "d2": 7, "form": [0, 0]}.
    Points with the wrong arity are skipped as malformed input.
    """
    pts: list[tuple[float, ...]] = []
    for p in coords:
        try:
            q = tuple(float(c) for c in p)
        except (TypeError, ValueError):
            continue
        if len(q) == 3 and all(math.isfinite(c) for c in q):
            pts.append(q)

    violations: list[dict] = []
    checked = 0
    for (i, p), (j, q) in itertools.combinations(enumerate(pts), 2):
        d2 = sum((a - b) ** 2 for a, b in zip(p, q))
        checked += 1
        form = excluded_form(d2)
        if form is not None:
            violations.append({
                "a": tuple(int(c) if c.is_integer() else c for c in p),
                "b": tuple(int(c) if c.is_integer() else c for c in q),
                "d2": int(round(d2)),
                "form": [form[0], form[1]],
            })
    return {"ok": not violations, "violations": violations, "pairs_checked": checked}
