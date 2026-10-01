"""field_flow -- Watershed rung 2: dirty-block sheet flow over a height grid.

Z5 of the hydrology lane (Y2's top steal: Dwarf Fortress' dirty-block
activation). Rung 1 (mag/hydrology.py) graded the head on the verdict
engine's PIPES; this module drops the pipes and lets water sheet across a
2D integer height grid -- the exact surface tools/dem_to_board emits
(water_graph.v1 board, nodes g{y}x{x}, elev 0-255):

  - Field: integer elevations + integer volumes per cell. Head law shared
    with hydrology: head = elev*256 + depth, depth = volume*1000 //
    cross_section (Q8 head, milli-depth) -- filling a cell RAISES its
    head, so backwater and pools that fill come free.
  - Flow: each tick a cell considers its 8 Moore neighbors and pours to
    every strictly-lower head, flow_i = (dHead_i * conductance) >> 8
    (Q8 fixed point, same constant family as rung 1), scaled down
    proportionally when the wants exceed the cell's volume. Nothing ever
    flows uphill; a dHead below 256//conductance rounds to zero (the
    integer surface-tension floor -- a 1-unit droplet stays put).

DIRTY-BLOCK LAW (the steal): a tick processes only ACTIVE cells -- those
whose volume moved last tick (in or out) plus their neighbors. Quiescent
water costs zero: a settled board ticks in O(1). The wetted meter is
last_processed (cells examined per tick); total_processed accumulates it.

Exactness (why the shortcut cannot drift from a full scan): a cell is
dropped from the dirty set only when it AND all 8 neighbors were
untouched by gross movement, so its next outflow provably recomputes to
the same zero it just produced -- while any cell with pending flow keeps
its recipients dirty, and their neighbor rule pulls the sender back in.
Both ends of every active edge stay dirty; test_field_flow proves state
equality against tick(full=True) step by step.

Determinism law: integers only, no floats, no RNG, no clocks. The dirty
set is an insertion-ordered dict, neighbor offsets are a fixed tuple,
commits ride dict insertion order -- same inputs, byte-identical run,
every platform. $0, stdlib.
"""
from __future__ import annotations

from typing import Any

HEAD_SCALE = 256              # Q8: one elevation unit = 256 head units
DEPTH_SCALE = 1000            # depth = volume * 1000 // cross_section
DEFAULT_CROSS_SECTION = 1000
DEFAULT_CONDUCTANCE = 8       # flow = dHead * conductance >> 8

# Fixed Moore-neighborhood order: the determinism device for both flow
# computation and dirty-set growth.
NEIGHBOR_OFFSETS: tuple[tuple[int, int], ...] = (
    (-1, -1), (-1, 0), (-1, 1),
    (0, -1), (0, 1),
    (1, -1), (1, 0), (1, 1),
)


class FieldFlow:
    """Integer sheet-flow over a height grid with dirty-block activation."""

    def __init__(self, elev: list[list[int]],
                 volumes: list[list[int]] | None = None,
                 waste: Any = (),
                 cross_section: int = DEFAULT_CROSS_SECTION,
                 conductance: int = DEFAULT_CONDUCTANCE) -> None:
        if not elev or not elev[0]:
            raise ValueError("elev grid must be non-empty")
        self.h = len(elev)
        self.w = len(elev[0])
        self.elev: list[list[int]] = []
        for row in elev:
            if len(row) != self.w:
                raise ValueError(
                    f"elev grid must be rectangular, row len {len(row)} != {self.w}")
            self.elev.append([int(v) for v in row])
        if volumes is None:
            self.vol = [[0] * self.w for _ in range(self.h)]
        else:
            if len(volumes) != self.h or any(len(r) != self.w for r in volumes):
                raise ValueError("volumes shape must match elev grid")
            self.vol = [[int(v) for v in row] for row in volumes]
            if any(v < 0 for row in self.vol for v in row):
                raise ValueError("volumes must be >= 0")
        if cross_section < 1:
            raise ValueError(f"cross_section must be >= 1, got {cross_section}")
        if conductance < 1:
            raise ValueError(f"conductance must be >= 1, got {conductance}")
        self.cross_section = cross_section
        self.conductance = conductance
        self.waste: set[tuple[int, int]] = set(waste)
        for y, x in self.waste:
            if not (0 <= y < self.h and 0 <= x < self.w):
                raise ValueError(f"waste cell ({y}, {x}) outside the grid")
        # meters: per-tick and cumulative cell examinations (the wetted
        # meter) plus volume moved and volume drained off-system.
        self.tick_count = 0
        self.last_processed = 0
        self.total_processed = 0
        self.last_moved = 0
        self.total_moved = 0
        self.drained = 0
        # Dirty set: insertion-ordered (dict as ordered set). Seeded with
        # every cell holding water plus neighbors -- the add-water law
        # applied to initial conditions.
        self.dirty: dict[tuple[int, int], None] = {}
        for y in range(self.h):
            for x in range(self.w):
                if self.vol[y][x] > 0:
                    self._mark_dirty(y, x)

    # ------------------------------------------------------------ helpers ----
    def _head(self, y: int, x: int, v: int) -> int:
        """Head of a cell holding volume v (caller passes the snapshot
        value; never self.vol directly, so mid-tick commits cannot leak
        into the flow computation)."""
        return self.elev[y][x] * HEAD_SCALE + v * DEPTH_SCALE // self.cross_section

    def _mark_dirty(self, y: int, x: int) -> None:
        """Cell + its in-bounds neighbors enter the dirty set (insertion
        order = argument order then NEIGHBOR_OFFSETS order)."""
        self.dirty.setdefault((y, x), None)
        for dy, dx in NEIGHBOR_OFFSETS:
            ny, nx = y + dy, x + dx
            if 0 <= ny < self.h and 0 <= nx < self.w:
                self.dirty.setdefault((ny, nx), None)

    def _neighbors(self, y: int, x: int):
        for dy, dx in NEIGHBOR_OFFSETS:
            ny, nx = y + dy, x + dx
            if 0 <= ny < self.h and 0 <= nx < self.w:
                yield ny, nx

    # ------------------------------------------------------------ public ----
    def add_water(self, y: int, x: int, amount: int) -> None:
        """Pour `amount` units on a cell; the cell and neighbors go dirty
        (the volume changed -- the dirty-block law's entry condition)."""
        if not (0 <= y < self.h and 0 <= x < self.w):
            raise ValueError(f"add_water ({y}, {x}) outside the grid")
        if amount < 1:
            raise ValueError(f"amount must be >= 1, got {amount}")
        self.vol[y][x] += amount
        self._mark_dirty(y, x)

    def tick(self, full: bool = False) -> tuple[int, int]:
        """One Jacobi tick: all flows are computed from the START-of-tick
        volumes (self.vol is read-only until commit), so results never
        depend on iteration order. Returns (cells_processed, volume_moved).

        full=True is the reference path: every cell row-major, the scan a
        naive sheet-flow would pay. The dirty path provably lands the same
        state (module docstring exactness argument) at cost |dirty|."""
        cells = ([(y, x) for y in range(self.h) for x in range(self.w)]
                 if full else list(self.dirty))
        out: dict[tuple[int, int], int] = {}
        inc: dict[tuple[int, int], int] = {}
        touched: dict[tuple[int, int], None] = {}
        drained_delta = 0
        moved = 0

        for y, x in cells:
            v = self.vol[y][x]
            if v <= 0:
                continue
            if (y, x) in self.waste:
                # The outlet: water standing on (or arriving at) a waste
                # cell leaves the tile. Standing volume drains here;
                # arrivals are diverted below and never land.
                out[(y, x)] = out.get((y, x), 0) + v
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
                if (ny, nx) in self.waste:
                    drained_delta += f
                else:
                    inc[(ny, nx)] = inc.get((ny, nx), 0) + f
                    touched[(ny, nx)] = None
                moved += f
            if out_sum > 0:
                out[(y, x)] = out.get((y, x), 0) + out_sum

        # commit (order: drains/outs then ins; a conveyor cell rides both
        # and can never go negative because out was capped at its
        # start-of-tick volume).
        for (y, x), f in out.items():
            self.vol[y][x] -= f
        for (y, x), f in inc.items():
            self.vol[y][x] += f
        self.drained += drained_delta

        # Dirty-block law: next tick's active set = cells with gross
        # movement (in OR out -- a conveyor cell with balanced in/out is
        # still flowing) plus their neighbors. Insertion order = first
        # touch, then fixed neighbor order.
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
        return len(cells), moved

    def run(self, max_ticks: int, stop_on_settle: bool = True) -> int:
        """Tick up to max_ticks; stops early when the board is quiescent
        (empty dirty set). Returns ticks executed."""
        ran = 0
        for _ in range(max_ticks):
            if stop_on_settle and not self.dirty:
                break
            self.tick()
            ran += 1
        return ran

    def settled(self) -> bool:
        """True when no cell is active -- the wetted meter reads zero."""
        return not self.dirty

    def total_volume(self) -> int:
        return sum(sum(row) for row in self.vol)

    def wet_cells(self) -> int:
        return sum(1 for row in self.vol for v in row if v > 0)

    def snapshot(self) -> list[list[int]]:
        return [list(row) for row in self.vol]

    # ------------------------------------------------------------ loader ----
    @classmethod
    def from_board(cls, spec: dict[str, Any]) -> "FieldFlow":
        """Load a dem_to_board output (water_graph.v1 with a dem_board
        header, nodes g{y}x{x}) as a FieldFlow. Elevations and volumes
        come from the nodes; kind == "waste" cells are the outlets."""
        nodes = spec.get("nodes")
        if not isinstance(nodes, dict) or not nodes:
            raise ValueError("board spec has no nodes")
        hdr = spec.get("dem_board") or {}
        shape = hdr.get("shape")
        if shape:
            h, w = int(shape[0]), int(shape[1])
        else:
            coords = [_parse_gname(name) for name in nodes]
            h = w = max(max(y, x) for y, x in coords) + 1
        elev = [[0] * w for _ in range(h)]
        vol = [[0] * w for _ in range(h)]
        waste: set[tuple[int, int]] = set()
        for name, node in nodes.items():
            y, x = _parse_gname(name)
            if not (0 <= y < h and 0 <= x < w):
                raise ValueError(f"node {name} outside shape {(h, w)}")
            if elev[y][x] or vol[y][x]:
                raise ValueError(f"duplicate node for ({y}, {x})")
            elev[y][x] = int(node.get("elev", 0))
            vol[y][x] = int(node.get("volume", 0))
            if str(node.get("kind", "plain")) == "waste":
                waste.add((y, x))
        return cls(elev, volumes=vol, waste=waste)


def _parse_gname(name: str) -> tuple[int, int]:
    """'g{y}x{x}' -> (y, x); raises ValueError on any other grammar (the
    water_graph board contract is row-major g-names, nothing else)."""
    try:
        idx = name.index("x", 1)
        y, x = int(name[1:idx]), int(name[idx + 1:])
    except (ValueError, IndexError) as exc:
        raise ValueError(f"bad board node name {name!r} (want g{{y}}x{{x}})") from exc
    if y < 0 or x < 0:
        raise ValueError(f"bad board node name {name!r} (negative index)")
    return y, x
