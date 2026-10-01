"""river -- Watershed rung 4: erosion and sediment on the integer substrate.

WC's river-bend steal (watch/inbox/water_engineering_20260930/WF_SYNTHESIS.md,
"WC companion" section): sael.net/river-bend runs the Ikeda-Parker-Sawai
bend-migration model -- near-bank velocity from curvature, bank erosion by
excess shear, point-bar deposition, oxbow cutoffs, scroll bars that
revegetate. The estate version keeps the two integers and drops the floats,
landing on rung 2's field (mag/field_flow.py: integer sheet flow over a
height grid, Q8 heads, dirty-block activation -- all inherited):

  - SILT: a second integer per cell (elev + volume + silt). Conservation
    law: silt is never created or destroyed, only moved -- erosion
    requires the cell to HOLD loose material, so an initial silt mantle
    bounds total carving (the mountain armors when the regolith is gone).
  - EROSION (the sill law, water_graph's gate carried onto a field): each
    tick, a cell whose water throughput (inflow + outflow this tick)
    EXCEEDS sill_flow moves 1 silt + 1 elev-unit to its
    strictly-lowest-head neighbor. The cell carves (-1 elev, -1 silt);
    the neighbor receives (+1 silt; the elev-unit lands, see the
    collision rule below).
  - DEPOSITION: passive -- a cell with flow at or below the sill never
    sends, so silt and elev arriving there stay and the bed rises (the
    point bar). Waste cells (rung 2's outlets) never erode: they are the
    sea; everything arriving piles up -- the delta.
  - MEANDER: transfers shift elevations by whole units, moved cells
    re-enter the dirty set, and the next water pass re-solves heads over
    the shifted bed -- the flow path wanders, bends migrate, and
    abandoned channels stay carved. The mountain remembers.

COLLISION RULE (the corner WC's sketch left open): what happens when a
transfer would land on a cell that is itself eroding this tick? Landing
the elev-unit there is a no-op conveyor (the -1 own carve and +1 deposit
cancel; only the channel head could ever incise, and it stalls the
moment it digs one slope-step below its outlet -- verified by hand on a
1x12 slope). A first cut cascaded the unit down lowest-neighbor chains
to the first quiet bed; that failed spectacularly (test evidence,
2026-09-30): every eroder's unit rode to the one sea cell, the delta
towered +11 elev/tick, drainage clogged, the backed-up pool made the
chains ride UPSTREAM, and the whole load dumped back onto the armored
spring pit (net +50 elev at the spring). Final resolution, split by
load type: the SILT is bed load -- it always lands on the direct lowest
neighbor and walks one cell per tick, even through eroding cells (they
re-send it next tick; silt stays conserved exactly). The ELEV-unit is
the suspended carve -- it settles only where the water is slow (a
non-eroding bed or the sea); over an actively eroding thalweg it stays
in the water column and washes out of the reach with the water (meter:
washed_out). The thalweg incises along its whole length; the bars and
the delta grow where the water is slow; the mountain loses elev only to
carving, exactly as a real watershed does.

Determinism law intact: integers only, no floats, no RNG (terrain noise
is a pure integer hash), iteration orders fixed (insertion-ordered dicts,
the NEIGHBOR_OFFSETS tuple, row-major commits). Same inputs, byte-identical
run. $0, stdlib. The water phase mirrors FieldFlow.tick exactly -- pinned
by test_river.py's parity test (no silt -> identical volumes, elevations
and dirty set); the override exists only because the sediment law needs
per-cell throughput, which the parent tick does not report.
"""
from __future__ import annotations

from typing import Any

from mag.field_flow import (
    DEFAULT_CONDUCTANCE,
    DEFAULT_CROSS_SECTION,
    FieldFlow,
    NEIGHBOR_OFFSETS,
)

DEFAULT_SILL_FLOW = 6   # throughput (in+out units/tick) above which a cell erodes


def det_noise(y: int, x: int, span: int) -> int:
    """Deterministic integer terrain noise in [-span, +span]: a pure
    multiplicative hash of the coordinates. The no-RNG determinism law --
    same board on every platform, no seed, no clock."""
    if span <= 0:
        return 0
    h = (y * 2654435761) ^ (x * 3266489917)
    h ^= h >> 13
    h = (h * 1274126177) & 0xFFFFFFFF
    h ^= h >> 16
    return (h % (2 * span + 1)) - span


class River(FieldFlow):
    """FieldFlow (rung 2 sheet flow) + silt + the sill erosion law (rung 4)."""

    def __init__(self, elev: list[list[int]],
                 volumes: list[list[int]] | None = None,
                 waste: Any = (),
                 silt: list[list[int]] | None = None,
                 cross_section: int = DEFAULT_CROSS_SECTION,
                 conductance: int = DEFAULT_CONDUCTANCE,
                 sill_flow: int = DEFAULT_SILL_FLOW) -> None:
        super().__init__(elev, volumes, waste, cross_section, conductance)
        if sill_flow < 0:
            raise ValueError(f"sill_flow must be >= 0, got {sill_flow}")
        self.sill_flow = int(sill_flow)
        if silt is None:
            self.silt = [[0] * self.w for _ in range(self.h)]
        else:
            if len(silt) != self.h or any(len(r) != self.w for r in silt):
                raise ValueError("silt grid shape must match the elev grid")
            if any(v < 0 for row in silt for v in row):
                raise ValueError("silt must be >= 0")
            self.silt = [[int(v) for v in row] for row in silt]
        # meters: per-cell throughput (the shear meter), rock units moved
        self.last_flow: list[list[int]] = [[0] * self.w for _ in range(self.h)]
        self.last_eroded = 0
        self.total_eroded = 0
        self.total_deposited = 0
        self.washed_out = 0
        # insertion-ordered wet cells from the water pass (sediment scan order)
        self._flow_order: list[tuple[int, int]] = []

    # ------------------------------------------------------------ water ----
    def tick(self, full: bool = False) -> tuple[int, int]:
        """One water tick (FieldFlow's Jacobi sheet-flow law, instrumented
        to report per-cell throughput) followed by the sediment tick.
        Returns (cells_processed, volume_moved) -- the parent signature."""
        cells = ([(y, x) for y in range(self.h) for x in range(self.w)]
                 if full else list(self.dirty))
        out: dict[tuple[int, int], int] = {}
        inc: dict[tuple[int, int], int] = {}
        touched: dict[tuple[int, int], None] = {}
        flow_out: dict[tuple[int, int], int] = {}
        flow_in: dict[tuple[int, int], int] = {}
        drained_delta = 0
        moved = 0

        for y, x in cells:
            v = self.vol[y][x]
            if v <= 0:
                continue
            if (y, x) in self.waste:
                out[(y, x)] = out.get((y, x), 0) + v
                flow_out[(y, x)] = flow_out.get((y, x), 0) + v
                touched[(y, x)] = None
                drained_delta += v
                moved += v
                continue
            h_src = self._head(y, x, v)
            wants: list[tuple[int, int, int]] = []
            total_want = 0
            for ny, nx in self._neighbors(y, x):
                d = h_src - self._head(ny, nx, self.vol[ny][nx])
                if d <= 0:
                    continue
                raw = (d * self.conductance) >> 8
                if raw > 0:
                    wants.append((ny, nx, raw))
                    total_want += raw
            if not wants:
                continue
            if total_want > v:
                wants = [(ny, nx, raw * v // total_want) for ny, nx, raw in wants]
            out_sum = 0
            for ny, nx, f in wants:
                if f <= 0:
                    continue
                out_sum += f
                touched[(y, x)] = None
                flow_in[(ny, nx)] = flow_in.get((ny, nx), 0) + f
                if (ny, nx) in self.waste:
                    drained_delta += f
                else:
                    inc[(ny, nx)] = inc.get((ny, nx), 0) + f
                    touched[(ny, nx)] = None
                moved += f
            if out_sum > 0:
                out[(y, x)] = out.get((y, x), 0) + out_sum
                flow_out[(y, x)] = flow_out.get((y, x), 0) + out_sum

        for (y, x), f in out.items():
            self.vol[y][x] -= f
        for (y, x), f in inc.items():
            self.vol[y][x] += f
        self.drained += drained_delta

        # the shear meter: throughput = inflow + outflow, this tick, per cell
        for row in self.last_flow:
            for x in range(self.w):
                row[x] = 0
        for (y, x), f in flow_out.items():
            self.last_flow[y][x] += f
        for (y, x), f in flow_in.items():
            self.last_flow[y][x] += f
        self._flow_order = list(touched)

        # dirty rebuild -- the parent law, verbatim
        nxt: dict[tuple[int, int], None] = {}
        for y, x in touched:
            for cy, cx in [(y, x)] + [(y + dy, x + dx) for dy, dx in NEIGHBOR_OFFSETS]:
                if 0 <= cy < self.h and 0 <= cx < self.w:
                    nxt.setdefault((cy, cx), None)
        self.dirty = nxt

        self.tick_count += 1
        self.last_processed = len(cells)
        self.total_processed += len(cells)
        self.last_moved = moved
        self.total_moved += moved

        # the bed shifts under the water: moved cells re-enter the dirty
        # set (via _mark_dirty below), so the NEXT water pass re-solves
        # heads over carved channels and raised bars -- the meander law.
        self._sediment_tick()
        return len(cells), moved

    # --------------------------------------------------------- sediment ----
    def _lowest(self, y: int, x: int,
                snap: dict[tuple[int, int], int]) -> tuple[int, int] | None:
        """Strictly-lowest-head neighbor under snapshot heads (first found
        in NEIGHBOR_OFFSETS order wins ties -- the determinism device).
        Sediment never moves uphill or across an equal head."""
        best: tuple[int, int] | None = None
        best_h = snap[(y, x)]
        for ny, nx in self._neighbors(y, x):
            if snap[(ny, nx)] < best_h:
                best_h = snap[(ny, nx)]
                best = (ny, nx)
        return best

    def _sediment_tick(self) -> int:
        """The erosion pass. One Jacobi sweep: every decision reads the
        post-water, pre-sediment snapshot (heads, silt, flows), then all
        transfers commit together -- no transfer can change another's
        target mid-tick, and mutual transfers are impossible (strictly
        lower heads cannot point both ways). Returns transfers committed.

        Per transfer: -1 elev -1 silt at the source (the carve); +1 silt
        at its lowest neighbor (the bed load, one cell per tick, always);
        the +1 elev-unit lands only if that neighbor is NOT eroding this
        tick (quiet bed or sea) -- otherwise it stays suspended and washes
        out with the water (the collision rule, module docstring)."""
        snap: dict[tuple[int, int], int] = {}
        for y in range(self.h):
            for x in range(self.w):
                snap[(y, x)] = self._head(y, x, self.vol[y][x])
        eroders: dict[tuple[int, int], None] = {}
        targets: dict[tuple[int, int], tuple[int, int]] = {}
        for cell in self._flow_order:
            y, x = cell
            if cell in self.waste:
                continue
            if self.last_flow[y][x] <= self.sill_flow:
                continue        # at/below the sill: deposition only
            if self.silt[y][x] < 1:
                continue        # armored bedrock: nothing loose to move
            dst = self._lowest(y, x, snap)
            if dst is None:
                continue        # pit: no strictly lower neighbor to carry to
            eroders[cell] = None
            targets[cell] = dst
        landings: dict[tuple[int, int], int] = {}
        washed = 0
        for dst in targets.values():
            if dst in eroders:
                washed += 1     # suspended over an eroding bed: leaves the reach
            else:
                landings[dst] = landings.get(dst, 0) + 1
        for (sy, sx), (dy, dx) in targets.items():
            self.elev[sy][sx] -= 1
            self.silt[sy][sx] -= 1
            self.silt[dy][dx] += 1
        for (ly, lx), n in landings.items():
            self.elev[ly][lx] += n
        self.last_eroded = len(targets)
        self.total_eroded += len(targets)
        self.total_deposited += sum(landings.values())
        self.washed_out += washed
        for cell in eroders:
            self._mark_dirty(cell[0], cell[1])
        for (ly, lx) in landings:
            self._mark_dirty(ly, lx)
        return len(targets)

    # ------------------------------------------------------------ public ----
    def add_silt(self, y: int, x: int, amount: int) -> None:
        """Place loose material on a cell (no dirty mark: silt is invisible
        to water; only its movement through erosion shifts heads)."""
        if not (0 <= y < self.h and 0 <= x < self.w):
            raise ValueError(f"add_silt ({y}, {x}) outside the grid")
        if amount < 1:
            raise ValueError(f"amount must be >= 1, got {amount}")
        self.silt[y][x] += amount

    def total_silt(self) -> int:
        return sum(sum(row) for row in self.silt)

    def total_elev(self) -> int:
        return sum(sum(row) for row in self.elev)

    def delta_silt(self) -> int:
        """Silt parked at waste cells -- the delta meter."""
        return sum(self.silt[y][x] for y, x in self.waste)

    def wet_path(self) -> list[list[int]]:
        """Row-major [y, x] of cells holding water -- the JSON trace."""
        return [[y, x] for y in range(self.h) for x in range(self.w)
                if self.vol[y][x] > 0]

    def render(self, baseline: list[list[int]] | None = None) -> str:
        """ASCII trace: '~' wet; vs the baseline (the uncarved board):
        '1'-'9' carve depth, '^' a raised bar, '.' untouched."""
        rows = []
        for y in range(self.h):
            line = []
            for x in range(self.w):
                if self.vol[y][x] > 0:
                    line.append("~")
                elif baseline is not None:
                    d = baseline[y][x] - self.elev[y][x]
                    line.append(str(min(d, 9)) if d > 0 else ("^" if d < 0 else "."))
                else:
                    line.append(".")
            rows.append("".join(line))
        return "\n".join(rows)

    # -------------------------------------------------------------- state ----
    def to_spec(self) -> dict[str, Any]:
        return {
            "schema": "river.v1",
            "shape": [self.h, self.w],
            "tick": self.tick_count,
            "sill_flow": self.sill_flow,
            "cross_section": self.cross_section,
            "conductance": self.conductance,
            "elev": [list(r) for r in self.elev],
            "vol": [list(r) for r in self.vol],
            "silt": [list(r) for r in self.silt],
            "waste": sorted([y, x] for y, x in self.waste),
            "meters": {
                "total_eroded": self.total_eroded,
                "total_deposited": self.total_deposited,
                "washed_out": self.washed_out,
                "drained": self.drained,
                "total_moved": self.total_moved,
            },
        }


def from_spec(spec: dict[str, Any]) -> River:
    """river.v1 spec -> River (meters other than tick are run history and
    restart at zero -- state fields are the contract)."""
    g = River(spec["elev"], volumes=spec.get("vol"),
              waste={(int(y), int(x)) for y, x in spec.get("waste", [])},
              silt=spec.get("silt"),
              cross_section=int(spec.get("cross_section", DEFAULT_CROSS_SECTION)),
              conductance=int(spec.get("conductance", DEFAULT_CONDUCTANCE)),
              sill_flow=int(spec.get("sill_flow", DEFAULT_SILL_FLOW)))
    g.tick_count = int(spec.get("tick", 0))
    return g
