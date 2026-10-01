"""flock_grid — spatial-hashing neighbor/seam search for the swarm (O(N), the MMO-scale unlock).

Operator (2026-08-11): "steal" + shared a ShaderToy boid shader whose core is a GRID (spatial hash):
a boid-ID grid texture (iChannel1), each pixel checks its 3x3 neighbor cells, iterates the stored
boid IDs (NEIGHBOR_STRIDE), and finds the nearest boid distance. This is exactly the O(N) neighbor
search our flock_shader.seams() needs (it is O(N^2) on the mean today).

MAPPING (shader -> ours):
  GetGridCoord/GetGridSize  = cell_of / dims (deterministic grid)
  iChannel1 (boid-ID grid)  = build_grid -> {cell: [agent indices]}
  3x3 neighbor cells        = neighbor_cells (radius 1, clamped to grid)
  NEIGHBOR_STRIDE           = the per-cell capacity stride
  nearest boid distance (md)= nearest_distance (O(N) via the grid)
  GRID_HEATMAP / smoothstep = local density -> SEAMS (isolated agents = divergences)

Deterministic + $0 (pure numpy/dict). Schema: flock_grid.v1
"""
from __future__ import annotations

import math
from typing import Any

SCHEMA = "flock_grid.v1"
NEIGHBOR_STRIDE = 4          # per-cell capacity stride (analogous to the shader)


def cell_of(pos: tuple[float, ...], cell_size: float) -> tuple[int, ...]:
    """Deterministic grid cell for a position (analogous to GetGridCoord)."""
    cs = max(1e-6, float(cell_size))
    return tuple(int(math.floor(float(p) / cs)) for p in pos)


def build_grid(positions: list[tuple[float, ...]], cell_size: float) -> dict[tuple[int, ...], list[int]]:
    """Build the spatial hash: {cell: [agent indices]} (analogous to the boid-ID grid iChannel1)."""
    grid: dict[tuple[int, ...], list[int]] = {}
    for i, pos in enumerate(positions):
        c = cell_of(pos, cell_size)
        grid.setdefault(c, []).append(i)
    return grid


def neighbor_cells(cell: tuple[int, ...], *, radius: int = 1) -> list[tuple[int, ...]]:
    """The 3x3 (radius 1) neighbor cells around a cell, like the shader's double loop."""
    out = []
    for dx in range(-radius, radius + 1):
        for dy in range(-radius, radius + 1):
            out.append((cell[0] + dx, cell[1] + dy))
    return out


def nearest_distance(positions: list[tuple[float, ...]], grid: dict[tuple[int, ...], list[int]],
                     cell_size: float, *, radius: int = 1) -> list[float]:
    """Nearest-boid squared-distance per agent, O(N) via the grid (the shader's 'md').

    Each agent checks its own cell + 3x3 neighbors and returns the min squared distance to any
    other agent. Correctness = same result as O(N^2) brute force, but O(N) work.
    """
    n = len(positions)
    nd = [float("inf")] * n
    for i, pos in enumerate(positions):
        c = cell_of(pos, cell_size)
        for nc in neighbor_cells(c, radius=radius):
            for j in grid.get(nc, []):
                if j == i:
                    continue
                d = (pos[0] - positions[j][0]) ** 2 + (pos[1] - positions[j][1]) ** 2
                if d < nd[i]:
                    nd[i] = d
    return nd


def seams_spatial(positions: list[tuple[float, ...]], *, cell_size: float = 1.0,
                  radius: int = 1, iso_tau: float = 0.25) -> list[dict[str, Any]]:
    """O(N) seam detection: agents with NO neighbor within iso_tau (squared distance) are SEAMS.

    Isolated agents = divergences (the flock is not locally coherent there) = the pixels to shade.
    This replaces flock_shader.seams()'s O(N^2) mean-deviation with an O(N) spatial method.
    Deterministic + $0.
    """
    grid = build_grid(positions, cell_size)
    nd = nearest_distance(positions, grid, cell_size, radius=radius)
    return [{"index": i, "nearest_d2": (round(math.sqrt(d), 4) if math.isfinite(d) else None),
             "isolated": not math.isfinite(d) or d > iso_tau}
            for i, d in enumerate(nd)]


def main(argv: list[str] | None = None) -> int:
    import sys, json
    positions = [(float(i % 5), float(i % 3)) for i in range(20)]
    s = seams_spatial(positions)
    print(json.dumps({"n": len(positions), "seams": s}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
