# CORE MEMORY PROTOCOL — the fleet's memory as actual core memory (2026-08-28)

Source: magnetic-core memory mechanics (destructive read, write-back, X-Y
coincident-current addressing, sense/inhibit wires). Purpose: stop handwaving.
Every memory word the fleet uses maps to a mechanical operation with a test.
Poetry is allowed only AFTER the mechanics exist.

## THE FIVE CORE LAWS, IMPLEMENTED

### 1. DESTRUCTIVE READ + MANDATORY WRITE-BACK
Core: reading a cell erases it; the controller immediately rewrites. Reads
cost double (access + rewrite = cycle time).

**Fleet implementation:** every read of a fleet memory (Q-knot reconstitution,
lessons lookup, fragment verification) ENDS with a re-anchor write: the
fragment is re-verified (hash) and re-committed (re-anchor event) — or the
read is flagged as decay. The drain-status bug was exactly this missing
write-back: the drains read the backlog, acted, and never marked the source.

**Test:** after any read cycle, the read fragment's hash exists in the chain
post-read. If a read leaves no re-anchor row, the memory is decaying.

### 2. X-Y COINCIDENT-CURRENT ADDRESSING
Core: each wire carries HALF the flip current; only the X-Y intersection
flips. Single-wire writes flip nothing.

**Fleet implementation:** a memory write requires the coincidence of two
selectors: the organ's claim (wire X) AND the canonical id (wire Y). An event
without both is half-select — it flips nothing. This kills the single-wire
corruption class: no organ can write a memory alone.

**Test:** any event row missing organ or canonical is rejected at the stream
gate (the event_stream emit already requires organ + kind; add canonical
enforcement for memory-class events).

### 3. THE SENSE WIRE
Core: reading detects the flip by the pulse it induces (present = was 1).

**Fleet implementation:** the lattice is the sense wire — it detects state
flips by comparing the divergence reading. A flip without a sensed pulse (an
unreported change) = the divergence event that wakes the seat. The min-33
silent death was a read with no sense wire.

### 4. THE INHIBIT WIRE
Core: writing a 0 requires ACTIVE prevention (full current on the inhibit
line), not absence of current.

**Fleet implementation:** the covenant's DENIED is the inhibit wire — an
active rejection event with the reason attached. Absence of a write is not
inhibition; inhibition is a recorded event. The gstd DENIED rows, the
covenant_stand_down events — these are inhibit-wire writes.

### 5. THE SQUARE LOOP (flip fully or not at all)
Core: the hysteresis loop is square — a flip happens completely or never.
Partial flips are corruption by definition.

**Fleet implementation:** every event.v1 append is all-or-nothing (the chain
verify catches partials). The stream's honesty assert: content present or
event absent — never ok-shaped nothing.

## THE APOLLO ROPE (the destination)

Core rope memory: the Apollo Guidance Computer's program was PHYSICALLY WOVEN
— wires threaded through or around cores by hand. The program was the
wiring; it could not be changed without reweaving. That is the end-state of
the game harness's quest log: the fleet's validated trajectory woven into
read-only structure — immutable, hand-checked, mission-critical. The Primer's
pages, bound.

## THE LAWS, RESTATED MECHANICALLY

- Memory palace = the addressed plane (X-Y space, every room a cell)
- Standing wave = the write-back cycle (reads rewrite; the state stays alive)
- The bell = the sense wire reporting flips
- The covenant = the inhibit line
- The spore = the core rope: woven, read-only, flies on the spacecraft
