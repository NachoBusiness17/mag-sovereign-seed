"""water_graph — the flow-graph engine: routing as physics, not a hardcoded pair.

Operator order 2026-09-27 ("use the physics instead of fighting them" +
"Next"): the water_computer module hardcodes VALVE_AT = {two valves on one
line} — nothing to route WITH. This engine generalizes the family's real
laws (mag/hydro_xor_sim.py: one-way check valves, mark-per-tick, siphon
crests; mag/water_computer.py: gravity tick, honest OUT) onto an arbitrary
graph:

  - Nodes: tanks/junctions with integer elevation + volume; `cold` nodes
    condense steam; `waste` HOLDS spilled/overflow volume as a boilable
    basin (V5 economy law 2026-09-29: deletion is theft — see the
    STARVATION LAW note under tick()).
  - Pipes: one-way (check-valve law, no backflow by construction), integer
    capacity, optional siphon with a crest volume (primes at crest, runs
    until the intake breaks — hydro_xor_sim's semantics, integerized).
  - Junctions: `plain` accumulates; `xor` delivers only when EXACTLY one
    inlet delivered this tick (both inlets -> overflow to waste — the
    hydraulic XOR); `sill` delivers only when total inflow >= a threshold
    (the hydraulic AND); `any` is OR.
  - Steam: `boil(node, n)` lifts volume to steam; each tick steam condenses
    at the highest `cold` node as rain (rises regardless of pipes — a
    second routing medium; falls back to its origin node when no cold node
    exists).
  - Fracture (AC2, 2026-09-30, watch/inbox/last_mile_20260930/AD1_FRACTURE.md;
    reach retuned B1 2026-09-30, B1_FRACTURE_REACH.md): a pipe running FULL
    BORE (flow == cap) accumulates `stress += flow` — cumulative throughput
    in VOLUME units — in `_move` AND at gated-inlet PROBE time (B1 seam fix:
    gated inlets load too, else the default Mountain's main artery can never
    burst); at `200 + name_hash(name) % 201` (= [200, 400] volume, the
    operator's sustained-full-bore design window) it FRACTURES — closed
    forever (`open()` refuses it; the valve verb cannot reopen a burst) —
    and that tick's flow sprays to the lowest-elevation node other than dst
    (first-min in insertion order). Conserved, never deleted, zero RNG.
  - Int domain (R8, 2026-09-30, watch/inbox/last_mile_20260930/
    R8_INT_DOMAIN.md): Python ints are unbounded, GDScript ints are 64-bit;
    the depth product `volume * DEPTH_SCALE` (mag/hydrology.py HydroNode and
    water_graph.gd HydroNode.depth, the render layer's to_dict included)
    crosses 2^63 silently in the Godot twin on mega-volume boards while
    Python computes it exactly. POLICY: the volume domain is BOUNDED at
    VOLUME_SAT — derived so `volume * DEPTH_SCALE` and
    `elev * HEAD_SCALE + depth` both stay inside signed int64 for any
    in-domain board — and EVERY increment flows through one saturating
    receiver that CLAMPS at the ceiling and NAMES the absorbed amount
    ("Node X SATURATES: ..."). Saturation is policy-declared deletion with
    a sensor, never a silent wrap. Ingestion (add_node) clamps into the
    domain (construction has no event stream yet); elevation clamps at
    ELEV_SAT. hydrology.py needs no change: its formulas are int64-safe by
    construction once the domain holds at every increment site here.

Deterministic: insertion-ordered pipes, integer volumes, no floats, no RNG.
$0, stdlib. water_computer delegates its gravity tick here when a campaign
seeds a graph spec; legacy 3-tank mode is untouched (its tests are the
regression suite for the old path).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# --------------------------------------------------- int domain (R8) ----
# R8 INT DOMAIN LAW (2026-09-30, receipt watch/inbox/last_mile_20260930/
# R8_INT_DOMAIN.md). Python ints are unbounded; GDScript ints are 64-bit.
# The deepest integer product in the estate is depth = volume * DEPTH_SCALE;
# past INT64_MAX // DEPTH_SCALE the Godot twin wraps silently while Python
# computes exactly — a cross-engine divergence with no crash and no sensor.
# The law bounds the volume domain so NO derived product can cross 2^63 in
# EITHER language: volume <= VOLUME_SAT keeps volume*DEPTH_SCALE in int64
# even at cross_section 1, and elev <= ELEV_SAT keeps the hydrology head
# (elev*HEAD_SCALE + depth) in int64 with room to spare. Both scales mirror
# mag/hydrology.py (pinned equal by tests/test_water_graph_int_domain.py).
INT64_MAX = (1 << 63) - 1        # 9,223,372,036,854,775,807
DEPTH_SCALE = 1000               # milli-depth per volume unit (hydrology mirror)
HEAD_SCALE = 256                 # Q8 head units per elevation unit (mirror)
ELEV_SAT = 1 << 20               # elevation domain ceiling (1,048,576 units)
VOLUME_SAT = (INT64_MAX - ELEV_SAT * HEAD_SCALE) // DEPTH_SCALE
# -> 9,223,372,036,586,340 (~9.223e15); the literal is pinned by test.


def name_hash(s: str) -> int:
    """djb2 32-bit string hash — the fracture threshold's entropy source.
    Python's builtin hash() is salted per process (PYTHONHASHSEED), so it
    could never be deterministic across runs NOR agree with the Godot
    mirror; this loop is byte-identical to water_graph.gd's name_hash().
    Still zero RNG: same name -> same threshold, always, everywhere."""
    h = 5381
    for ch in s:
        h = ((h * 33) + ord(ch)) & 0xFFFFFFFF
    return h


def fracture_threshold(pipe_name: str) -> int:
    """Volume a pipe survives at full bore: 200 + hash(name) % 201 ->
    [200, 400] VOLUME units (B1 2026-09-30, B1_FRACTURE_REACH.md): stress is
    cumulative throughput, so the threshold is denominated in volume — a
    cap-1 pipe bursts after 200-400 ticks of sustained full bore (the
    operator's window), a cap-k pipe after threshold/k. The old band
    120 + hash%240 had no design anchor (AJ4 finding 2: unreachable)."""
    return 200 + name_hash(pipe_name) % 201


@dataclass
class Node:
    name: str
    elev: int = 0
    kind: str = "plain"          # plain | xor | sill | cold | waste
    sill: int = 0                # for kind == "sill"
    volume: int = 0
    steam: int = 0


@dataclass
class Pipe:
    name: str
    src: str
    dst: str
    cap: int = 1                 # max units per tick
    siphon: bool = False
    crest: int = 2               # volume at src needed to prime (siphon only)
    primed: bool = False
    open: bool = True
    stress: int = 0              # AC2: cumulative full-bore load
    fractured: bool = False      # AC2: burst — closed forever


@dataclass
class WaterGraph:
    nodes: dict[str, Node] = field(default_factory=dict)
    pipes: dict[str, Pipe] = field(default_factory=dict)
    tick_count: int = 0

    def add_node(self, name: str, elev: int = 0, kind: str = "plain",
                 sill: int = 0, volume: int = 0) -> Node:
        # R8 INT DOMAIN LAW: ingestion clamps into the declared domain so
        # `volume <= VOLUME_SAT` holds before the first tick (and with it,
        # volume*DEPTH_SCALE can never wrap the 64-bit GDScript twin).
        # Construction-time saturation is silent BY DESIGN — there is no
        # event stream yet; the runtime sensor fires in _receive().
        n = Node(name=name, elev=max(-ELEV_SAT, min(ELEV_SAT, elev)),
                 kind=kind, sill=sill, volume=min(volume, VOLUME_SAT))
        self.nodes[name] = n
        return n

    def add_pipe(self, name: str, src: str, dst: str, cap: int = 1,
                 siphon: bool = False, crest: int = 2, open_: bool = True,
                 primed: bool = False, stress: int = 0,
                 fractured: bool = False) -> Pipe:
        for node in (src, dst):
            if node not in self.nodes:
                raise KeyError(f"unknown node {node!r}")
        p = Pipe(name=name, src=src, dst=dst, cap=cap, siphon=siphon,
                 crest=crest, open=open_, primed=primed, stress=stress,
                 fractured=fractured)
        self.pipes[name] = p
        return p

    def open(self, pipe_name: str) -> None:
        # AC2 (2026-09-30): a FRACTURED pipe is closed for good — the valve
        # verb routes through here (server/world.py _apply, dataset
        # engine_apply) and must NOT be able to reopen a burst pipe.
        if self.pipes[pipe_name].fractured:
            return
        self.pipes[pipe_name].open = True

    def close(self, pipe_name: str) -> None:
        self.pipes[pipe_name].open = False

    # ------------------------------------------------------------- steam ----
    def boil(self, node_name: str, units: int = 1) -> int:
        """Lift volume to steam at a node (heat is a routing medium: steam
        ignores pipes and condenses at the highest cold node)."""
        n = self.nodes[node_name]
        units = min(units, n.volume)
        n.volume -= units
        # R8: steam shares the volume domain (it condenses back into
        # volume); unbounded steam accumulation would overflow the GDScript
        # twin's int64 long before Python's unbounded ints noticed.
        n.steam = min(VOLUME_SAT, n.steam + units)
        return units

    # -------------------------------------------------- int domain (R8) ----
    def _receive(self, node: Node, gain: int, events: list[str]) -> None:
        """R8 INT DOMAIN LAW receiver: every volume increment lands here (or
        at the add_node/boil ingest clamps) so `volume <= VOLUME_SAT` holds
        on every tick and volume * DEPTH_SCALE can never cross 2^63 in
        EITHER engine. A gain that would cross the ceiling CLAMPS and NAMES
        the absorbed amount — policy-declared deletion with a sensor (the
        same honesty as FRACTURES/STARVED), never a silent wrap. In-domain
        arithmetic is overflow-safe by construction: both operands stay
        <= VOLUME_SAT, so the sum and the absorbed amount fit int64 in the
        GDScript twin."""
        if gain <= 0:
            return
        room = VOLUME_SAT - node.volume
        if gain <= room:
            node.volume += gain
            return
        node.volume = VOLUME_SAT
        events.append(f"Node {node.name} SATURATES: {gain - room} absorbed "
                      f"at the volume ceiling {VOLUME_SAT} "
                      f"(int64 depth domain, R8).")

    def _condense_steam(self) -> list[str]:
        events: list[str] = []
        colds = [n for n in self.nodes.values() if n.kind == "cold"]
        if colds:
            target = max(colds, key=lambda n: n.elev)
            for n in self.nodes.values():
                if n.steam:
                    self._receive(target, n.steam, events)
                    events.append(f"Steam condenses at {target.name} (+{n.steam}).")
                    n.steam = 0
        return events

    # --------------------------------------------------------------- tick ----
    def tick(self) -> list[str]:
        """One physics tick. Deterministic three-phase structure:
        (1) condense steam; (2) plain pipes + pipes INTO gated junctions
        (the inflow LEAVES the source at probe time — reserved, so sibling
        pipes from the same source cannot re-spend it — but does not LAND
        at the junction until the gate verdict); (3) evaluate junction gates
        (XOR/sill) from committed inflow counts, commit or overflow, then
        run gated junctions' outflow pipes under their gate. Gated-junction
        outflow MUST wait for the gate — the first cut let the outflow pipe
        drain the junction in the same pass its inflows arrived (the XOR
        delivered on both-inlet ticks; caught by tests, 2026-09-27)."""
        self.tick_count += 1
        events: list[str] = list(self._condense_steam())

        gated_kinds = ("xor", "sill")
        deferred_in: dict[str, list[tuple[str, Pipe, int]]] = {}
        gated_out: list[Pipe] = []
        delivered: dict[str, list[str]] = {}

        for p in self.pipes.values():
            if p.fractured or not p.open:
                continue
            src = self.nodes[p.src]
            dst = self.nodes[p.dst]
            if src.kind in gated_kinds:
                gated_out.append(p)
                continue
            if dst.kind in gated_kinds:
                flow = self._available(p, src, events)
                if flow:
                    # B1 SEAM FIX (2026-09-30, B1_FRACTURE_REACH.md): full-
                    # bore flow INTO a gated junction stresses the pipe AT
                    # PROBE TIME — the water left the source through the
                    # pipe section = wear. The AC2 cut loaded pipes only in
                    # _move, so the default Mountain's main artery (p_spring
                    # -> xor gate1) could NEVER burst (evidence: tests/
                    # test_water_graph.py B1 seam tests). On burst the flow
                    # sprays (conserved); the gate never sees the inlet.
                    if self._fracture(p, src, dst, flow, events):
                        continue
                    # NEG-VOLUME LAW (2026-09-29, LW5 deferred-inflow
                    # double-count): the deferred flow is RESERVED here, at
                    # probe time — else a sibling pipe from the SAME source
                    # re-spends it and the gate phase double-decrements src
                    # (pinned repros + 1000 seeded graphs, test_water_graph.py LW5 block).
                    src.volume -= flow
                    deferred_in.setdefault(dst.name, []).append((p.name, p, flow))
                continue
            self._move(p, src, dst, delivered, events)

        # junction gates: commit or overflow from the ACTUAL inflow count.
        # STARVATION LAW (2026-09-28, operator: "this whole starve-out thing
        # is bullshit and our water computer spec should have picked it up"):
        # a gated junction that receives inflow below its gate and then dumps
        # that water to waste is SILENT STARVATION — the network eats water
        # in the middle while looking like a gate. Two changes:
        #   (1) under-gate inflow is HELD (not spilled this tick) so a later
        #       tick can still reach the gate — a real sill pools water;
        #   (2) any HELD volume that overflows a LATER tick (new shape
        #       changed the verdict) emits a STARVED line naming the node,
        #       the held amount, and the gate — the sensor the spec lacked.
        gate: dict[str, int] = {}
        for name, node in self.nodes.items():
            if node.kind not in gated_kinds:
                continue
            ins = deferred_in.get(name, [])
            allow = (len(ins) == 1) if node.kind == "xor" else (
                len(ins) >= max(1, node.sill))
            gate[name] = 1 if allow else 0
            if allow:
                for pname, p, flow in ins:
                    self._receive(node, flow, events)  # R8; src decremented at probe (LW5)
                    delivered.setdefault(name, []).append(pname)
                    events.append(f"{pname}: {flow} {p.src}->{name}.")
                if node.kind == "xor":
                    events.append(f"Junction {name} passes ({ins[0][0]} sole inlet).")
                else:
                    events.append(f"Junction {name} sill reached ({len(ins)} inlets).")
            else:
                held_now = sum(flow for _, _, flow in ins)
                # hold the new inflow; pool with anything already held
                for pname, p, flow in ins:
                    self._receive(node, flow, events)  # R8; src decremented at probe (LW5)
                why = (f"{len(ins)} inlets" if node.kind == "xor"
                       else f"{len(ins)} < sill {node.sill}")
                if held_now > 0:
                    events.append(f"Junction {name} holds {held_now} below gate "
                                  f"({why}); pooling.")
                if node.volume > 0 and held_now == 0:
                    # gate failed again with NO new inflow: previously-pooled
                    # water is now dead weight. Spill it and NAME the starve.
                    # V5 ECONOMY LAW (2026-09-29, Z14 flaw: the STARVED spill
                    # zeroed volume with no destination while its event string
                    # claimed "spilled to waste" — slow starters permanently
                    # lost half the 8-unit economy). Fix: the spill ROUTES to
                    # the first waste node in insertion order, and waste HOLDS
                    # it as a boilable basin (boil from waste -> steam ignores
                    # pipes -> condenses at the highest cold node = recovery).
                    # Evidence: tests/test_water_graph_starvation.py V5 tests
                    # (waste holds, boil-from-waste recovers, conservation).
                    # No waste node in the graph: HOLD at the junction (never
                    # delete); the event names the hold so the sensor stays
                    # honest and the water stays boilable where it sits.
                    spill = node.volume
                    basin = next((n for n in self.nodes.values()
                                  if n.kind == "waste"), None)
                    if basin is not None:
                        self._receive(basin, spill, events)  # R8
                        node.volume = 0
                        events.append(f"Junction {name} STARVED: {spill} pooled units "
                                      f"spilled to waste at {basin.name} ({why}; no inflow "
                                      f"reached the gate; boil {basin.name} to recover them).")
                    else:
                        events.append(f"Junction {name} STARVED: {spill} pooled units "
                                      f"held at the junction ({why}; no inflow reached "
                                      f"the gate; no waste node to receive them).")

        # gated outflow under the gate
        for p in gated_out:
            if not gate.get(p.src):
                continue
            src = self.nodes[p.src]
            dst = self.nodes[p.dst]
            self._move(p, src, dst, delivered, events)

        return events

    def _available(self, p: Pipe, src: Node, events: list[str]) -> int:
        """Flow a pipe into a gated junction would carry this tick (no commit)."""
        if src.volume <= 0:
            return 0
        dst = self.nodes[p.dst]
        head_ok = src.elev > dst.elev
        if p.siphon:
            if not p.primed:
                if src.volume >= p.crest and head_ok:
                    p.primed = True
                    events.append(f"Siphon {p.name} primes at crest ({p.crest}).")
                else:
                    return 0
            return min(p.cap, src.volume)
        if not head_ok:
            return 0
        return min(p.cap, src.volume)

    def _fracture(self, p: Pipe, src: Node, dst: Node, flow: int,
                  events: list[str]) -> bool:
        """AC2 pipe-fracture law (2026-09-30), B1 reach retune (2026-09-30).
        Full-bore flow (flow == cap) loads the pipe: stress += flow,
        cumulative VOLUME across ticks (a cap-k pipe wears k units per
        full-bore tick). When stress EXCEEDS 200 + hash(name) % 201 (= [200,
        400] volume — 200-400 ticks of sustained full bore on the all-cap-1
        default Mountain) the pipe bursts — closed forever — and THIS tick's
        flow sprays to the lowest-elevation node other than dst (first-min
        in insertion order; min() keeps the first tie) instead of
        delivering. Returns True when the burst happened (caller returns;
        volumes are already conserved: src -= flow, spray += flow)."""
        if flow != p.cap:
            return False
        p.stress += flow
        if p.stress <= fracture_threshold(p.name):
            return False
        p.fractured = True
        p.open = False
        src.volume -= flow
        spray = min((n for n in self.nodes.values() if n.name != dst.name),
                    key=lambda n: n.elev)
        self._receive(spray, flow, events)  # R8: even a burst's spray saturates
        events.append(f"Pipe {p.name} FRACTURES (stress {p.stress}): "
                      f"spray to {spray.name}.")
        return True

    def _move(self, p: Pipe, src: Node, dst: Node,
              delivered: dict[str, list[str]], events: list[str]) -> None:
        if src.volume <= 0:
            if p.siphon and p.primed:
                p.primed = False
                events.append(f"Siphon {p.name} breaks (intake dry).")
            return
        head_ok = src.elev > dst.elev
        if p.siphon:
            if not p.primed:
                if src.volume >= p.crest and head_ok:
                    p.primed = True
                    events.append(f"Siphon {p.name} primes at crest ({p.crest}).")
                else:
                    return
            flow = min(p.cap, src.volume)
        else:
            if not head_ok:
                return  # check valve: gravity-only, never uphill
            flow = min(p.cap, src.volume)
        if self._fracture(p, src, dst, flow, events):
            return  # AC2: burst — this tick's flow sprayed, not delivered
        src.volume -= flow
        if dst.kind == "waste":
            # V5 ECONOMY LAW (2026-09-29): waste HOLDS what it receives —
            # the old early-return skipped the accumulation, so every unit
            # piped to waste was deleted from the economy. Held waste is
            # boilable (steam ignores pipes, condenses at the cold crown),
            # so the drain is a basin, not a void.
            self._receive(dst, flow, events)  # R8
            events.append(f"{p.name}: {flow} to waste at {dst.name}.")
            return
        self._receive(dst, flow, events)  # R8
        delivered.setdefault(dst.name, []).append(p.name)
        events.append(f"{p.name}: {flow} {p.src}->{p.dst}.")

    # -------------------------------------------------------------- state ----
    def volume(self, node_name: str) -> int:
        return self.nodes[node_name].volume

    def to_spec(self) -> dict[str, Any]:
        return {
            "schema": "water_graph.v1",
            "tick": self.tick_count,
            "nodes": {n: {"elev": v.elev, "kind": v.kind, "volume": v.volume,
                          "steam": v.steam}
                      for n, v in self.nodes.items()},
            "pipes": {p: {"src": v.src, "dst": v.dst, "cap": v.cap,
                          "siphon": v.siphon, "crest": v.crest,
                          "primed": v.primed, "open": v.open,
                          "stress": v.stress, "fractured": v.fractured}
                      for p, v in self.pipes.items()},
        }


def from_spec(spec: dict[str, Any]) -> WaterGraph:
    g = WaterGraph()
    for name, n in spec.get("nodes", {}).items():
        g.add_node(name, elev=int(n.get("elev", 0)),
                   kind=str(n.get("kind", "plain")),
                   sill=int(n.get("sill", 0)),
                   volume=int(n.get("volume", 0)))
    for name, p in spec.get("pipes", {}).items():
        # LW5 (2026-09-29): pass `primed` through — to_spec emitted it but
        # from_spec dropped it, so every spec roundtrip (estate_water_graph_
        # tick included) silently reverted a primed siphon to unprimed.
        # Evidence fixed-on: test_spec_roundtrip_preserves_siphon_primed_state.
        # AC2 (2026-09-30): `stress`/`fractured` ride the same law — a burst
        # pipe must survive the estate roundtrip closed, not resurrect open.
        g.add_pipe(name, src=p["src"], dst=p["dst"], cap=int(p.get("cap", 1)),
                   siphon=bool(p.get("siphon", False)),
                   crest=int(p.get("crest", 2)), open_=bool(p.get("open", True)),
                   primed=bool(p.get("primed", False)),
                   stress=int(p.get("stress", 0)),
                   fractured=bool(p.get("fractured", False)))
    g.tick_count = int(spec.get("tick", 0))
    return g
