"""hydrology -- The Watershed: graded head over the verdict engine.

WF_SYNTHESIS.md (2026-09-30) called water_graph "a logic circuit in a
wetsuit": head is a boolean (`src.elev > dst.elev`), flow is min(cap,
volume) -- verdict physics, not fluid physics. This module is rung 1 of
the synthesis ladder: keep water_graph as the verdict layer (gates,
siphons, steam, tick structure all inherited untouched) and replace only
the boolean head with a fixed-point gradient:

  - Node geometry: each node carries an integer `cross_section`; depth
    = volume * 1000 // cross_section (milli-depth units, so small tanks
    still grade with integer math).
  - Head: head = elev * 256 + depth -- elevation in Q8 (HEAD_SCALE =
    256 head units per elevation unit), depth added in the same integer
    space. Filling a pool RAISES its head: backwater, equalization, and
    pools that visibly fill come out of this one change.
  - Flow: proportional to (head_src - head_dst) in Q8 fixed-point:
    flow = (dHead * conductance) >> 8, capped by pipe capacity and
    available volume. Bigger drop = bigger flow; equal heads = nothing
    moves; nothing ever flows uphill (the check-valve law survives).

Determinism law intact: integers only, no floats, no RNG, no clocks.
$0, stdlib, and water_graph.py itself is untouched (its tests are the
regression suite for the boolean path). AF2 (2026-09-30, AD1's flag):
the AC2 pipe-fracture law rides the inherited `_fracture` hook from
this module's `_move` — full-bore graded flow stresses the pipe under
the same djb2 threshold, and a burst fires identically to the boolean
engine for the same pipe name (one law, two head laws).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from mag.water_graph import Node, Pipe, WaterGraph

HEAD_SCALE = 256        # Q8: one elevation unit = 256 head units
DEPTH_SCALE = 1000      # depth = volume * 1000 // cross_section
DEFAULT_CROSS_SECTION = 1000


@dataclass
class HydroNode(Node):
    """A node with shape: cross_section converts volume into depth."""
    cross_section: int = DEFAULT_CROSS_SECTION

    @property
    def depth(self) -> int:
        return self.volume * DEPTH_SCALE // self.cross_section

    @property
    def head(self) -> int:
        return self.elev * HEAD_SCALE + self.depth


@dataclass
class HydrologyGraph(WaterGraph):
    """WaterGraph with graded heads. Only the node type, add_node, the
    head law (_available/_move), and the spec change; tick structure,
    junction gates, siphons, steam, and starvation law are inherited."""
    conductance: int = 8   # Q8: flow = dHead * conductance >> 8

    def add_node(self, name: str, elev: int = 0, kind: str = "plain",
                 sill: int = 0, volume: int = 0,
                 cross_section: int = DEFAULT_CROSS_SECTION) -> HydroNode:
        if cross_section < 1:
            raise ValueError(f"cross_section must be >= 1, got {cross_section}")
        n = HydroNode(name=name, elev=elev, kind=kind, sill=sill,
                      volume=volume, cross_section=cross_section)
        self.nodes[name] = n
        return n

    # ------------------------------------------------------ head law ----
    def _pipe_flow(self, p: Pipe, src: HydroNode, dst: HydroNode,
                   events: list[str]) -> int:
        """Flow a pipe would carry this tick (no volume commit). The
        rung-1 change: dHead over node cross-sections in Q8, replacing
        the boolean `src.elev > dst.elev` verdict. Siphons keep their
        own law (prime at crest under positive head, then full bore)."""
        if src.volume <= 0:
            return 0
        d_head = src.head - dst.head
        if p.siphon:
            if not p.primed:
                if src.volume >= p.crest and d_head > 0:
                    p.primed = True
                    events.append(f"Siphon {p.name} primes at crest ({p.crest}).")
                else:
                    return 0
            return min(p.cap, src.volume)
        if d_head <= 0:
            return 0  # check valve: gravity-only, never uphill
        return min(p.cap, src.volume, (d_head * self.conductance) >> 8)

    def _available(self, p: Pipe, src: Node, events: list[str]) -> int:
        """Override: graded flow into gated junctions (no commit)."""
        if src.volume <= 0:
            return 0
        return self._pipe_flow(p, src, self.nodes[p.dst], events)

    def _move(self, p: Pipe, src: Node, dst: Node,
              delivered: dict[str, list[str]], events: list[str]) -> None:
        """Override: commit the graded flow (same event grammar as the
        boolean engine, so downstream reporters do not branch)."""
        if src.volume <= 0:
            if p.siphon and p.primed:
                p.primed = False
                events.append(f"Siphon {p.name} breaks (intake dry).")
            return
        flow = self._pipe_flow(p, src, dst, events)
        if flow <= 0:
            return
        # AF2 (2026-09-30, AD1's flag): this override re-implemented the
        # commit without the base engine's AC2 fracture hook, so a graded
        # pipe could run full bore forever. Fixed by calling the ONE law
        # where the boolean engine calls it (inherited `_fracture`, same
        # djb2 threshold, same spray, same event grammar) — not a second
        # copy. Evidence fixed-on: tests/test_hydrology.py AF2 block (the
        # graded and boolean engines burst byte-identically for the same
        # pipe name).
        if self._fracture(p, src, dst, flow, events):
            return  # burst: this tick's flow sprayed, not delivered
        src.volume -= flow
        if dst.kind == "waste":
            events.append(f"{p.name}: {flow} to waste at {dst.name}.")
            return
        dst.volume += flow
        delivered.setdefault(dst.name, []).append(p.name)
        events.append(f"{p.name}: {flow} {p.src}->{p.dst}.")

    # -------------------------------------------------------------- state ----
    def depth(self, node_name: str) -> int:
        return self.nodes[node_name].depth

    def head(self, node_name: str) -> int:
        return self.nodes[node_name].head

    def to_spec(self) -> dict[str, Any]:
        spec = super().to_spec()
        spec["schema"] = "hydrology.v1"
        spec["conductance"] = self.conductance
        for name, node in self.nodes.items():
            spec["nodes"][name]["cross_section"] = node.cross_section
        return spec


def from_spec(spec: dict[str, Any]) -> HydrologyGraph:
    """hydrology.v1 spec -> graph (cross_section-aware; water_graph.v1
    specs load with the default cross-section)."""
    g = HydrologyGraph(conductance=int(spec.get("conductance", 8)))
    for name, n in spec.get("nodes", {}).items():
        g.add_node(name, elev=int(n.get("elev", 0)),
                   kind=str(n.get("kind", "plain")),
                   sill=int(n.get("sill", 0)),
                   volume=int(n.get("volume", 0)),
                   cross_section=int(n.get("cross_section",
                                           DEFAULT_CROSS_SECTION)))
    for name, p in spec.get("pipes", {}).items():
        # AF2 (2026-09-30): carry `stress`/`fractured` (the AC2 roundtrip
        # law — a burst hydrology pipe must survive the estate roundtrip
        # closed, not resurrect open; to_spec emits them via the base) and
        # `primed` (LW5, same one-line family: the base from_spec fix never
        # reached this override). Evidence fixed-on:
        # tests/test_hydrology.py AF2 roundtrip test.
        g.add_pipe(name, src=p["src"], dst=p["dst"], cap=int(p.get("cap", 1)),
                   siphon=bool(p.get("siphon", False)),
                   crest=int(p.get("crest", 2)), open_=bool(p.get("open", True)),
                   primed=bool(p.get("primed", False)),
                   stress=int(p.get("stress", 0)),
                   fractured=bool(p.get("fractured", False)))
    g.tick_count = int(spec.get("tick", 0))
    return g
