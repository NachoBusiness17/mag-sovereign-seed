"""SectionStream — Python port of roblox/src/shared/SectionStream.luau.

The GnomeCode ep.1 streamed-sections pattern (Doors: the world materializes
ahead of the walker instead of all at boot). A stream holds sections, each a
one-shot build closure plus a center; ``poll(positions)`` builds every unbuilt
section whose center sits within ``radius`` of any position, at most
``budget`` builds per poll so a neighborhood manifests across frames instead
of spiking one.

``ordered=True`` builds STRICTLY in insertion order: a section never builds
before its predecessors even when its own radius trips first. Maze builds
whose closures draw from one shared seeded-RNG stream must use this mode —
insertion order then equals rng draw order, so a streamed world is identical
to the eager one, only later in time (the Luau's Ossuary floors ride one
SeedRng(20261031); per-floor draw counts unchanged, every corridor, sentinel,
lever and brazier lands where it always did).

Determinism contract (why this port exists): the module draws NO randomness
of its own — there is nothing here to seed, so the estate's no-RNG law is
satisfied by construction. The determinism this module sells is rng-ORDER
preservation: one shared seeded generator feeding closures that ``ordered``
mode invokes strictly in insertion order reproduces the eager build exactly.
tests/test_section_stream.py proves it with the fleet's own xorshift32 shape
(roblox/src/shared/SeedRng.luau).

Luau -> Python mapping (each line of the 103-line source maps 1:1):
Vector3 -> any 3-number sequence (tuple); ``(pos - sec.center).Magnitude``
-> :func:`math.dist`; ``budget or math.huge`` -> ``budget if budget is not
None else math.inf``; ``table.insert`` -> ``list.append``; the
``predecessorsDone`` identity walk keeps the Luau's ``other == sec`` table
identity compare as ``is``.

Port receipt: watch/inbox/hydrology/Z4_SECTIONSTREAM.md (Y1's top port).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Iterable, Sequence, Tuple

__all__ = ["Section", "SectionStream", "Vec3"]

Vec3 = Tuple[float, float, float]


@dataclass
class Section:
    """One unbuilt (or built) piece of the world: a center plus a one-shot
    build closure. ``done`` flips exactly when ``build`` has run once."""

    center: Vec3
    build: Callable[[], object]
    done: bool = field(default=False)


def _predecessors_done(sections: Sequence[Section], sec: Section) -> bool:
    """ordered-mode gate: a section may build only once every
    earlier-registered section has built (insertion order = rng draw order
    for seeded builds). Mirrors predecessorsDone() in the Luau, identity
    compare included."""
    for other in sections:
        if other is sec:
            return True  # walked insertion order up to sec: everything before is done
        if not other.done:
            return False
    return True


class SectionStream:
    """Streamed world materialization — poll it with walker positions.

    :param radius: build any unbuilt section whose center is within this
        distance of any polled position (boundary inclusive, like the
        Luau's ``<=``).
    :param budget: max builds per poll (``math.inf`` when None, mirroring
        ``budget or math.huge``); the budget is per poll, never total.
    :param ordered: build strictly in insertion order — the rng-order
        preservation mode for closures sharing one seeded generator.
    """

    def __init__(
        self,
        radius: float,
        budget: float | None = None,
        ordered: bool = False,
    ) -> None:
        self._radius = radius
        self._budget = math.inf if budget is None else budget
        self._ordered = ordered is True
        self._sections: list[Section] = []

    def add(self, center: Vec3, build: Callable[[], object]) -> None:
        """Register a section; builds happen only via :meth:`poll`."""
        self._sections.append(Section(center=center, build=build))

    def poll(self, positions: Iterable[Vec3]) -> int:
        """Build due sections (insertion order, budget-capped), return how
        many built this poll. A section builds at most once, on the first
        position found within radius — exactly the Luau loop, breaks and
        all. (Positions are snapshotted first: the Luau re-iterates its
        table per section, a live Python iterator would exhaust after the
        first section.)"""
        positions = list(positions)  # re-iterable, like the Luau table
        sections = self._sections
        budget = self._budget
        radius = self._radius
        built = 0
        for sec in sections:
            if built >= budget:
                break
            if not sec.done and (not self._ordered or _predecessors_done(sections, sec)):
                for pos in positions:
                    if math.dist(pos, sec.center) <= radius:
                        sec.done = True
                        sec.build()
                        built += 1
                        break
        return built

    def pending(self) -> int:
        """Count of sections not yet built."""
        return sum(1 for sec in self._sections if not sec.done)
