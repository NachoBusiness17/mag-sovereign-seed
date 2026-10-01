# GSTD forest incorporation plan (2026-08-24)

Source: reference/gstdcoin/ (6 repos cloned 2026-08-05). Honesty gate: part real, part
aspirational — the real spine is REST hub + node self-report + poll-with-load-gate +
confidence-gated shared memory + quality-scored routing. The bridge MPC and /agents/* market
are fabricated (flagged in their own READMEs) — AVOID.

## What we ALREADY beat them on
- Shared state: our verkle chain > their Upstash KV. We win the ground-truth axis.
- The loop: our sense -> claim -> bank -> percolate already covers their task lifecycle.
- The ceiling: cadence_learn 90% CPU exists (the steal is WHERE the gate lives, see #3).

## Adopt, in value order (each maps to a concrete file)

### 1. Quality gate before anything enters the chain (collective.ts confidence>=0.8 + metacognition self-score)
- Their rule: only sync to shared memory when confidence >= 0.8; self-score floor 0.3 (withhold) /
  0.3-0.7 (down-weight) before submission. Corroboration bumps confidence +0.05.
- OUR MAP: the bank/percolate step (ox_percolate.sync + fuel_feed) must gate on a self-score
  floor, not on "did we produce it." A weak answer doesn't pollute the verkle/explore/invariants.
- FILE: mag/fuel_feed.py (add self-score to the folded result before marking done + percolating),
  mag/ox_percolate.py (skip percolating thin/empty artifacts — some already tagged noise).

### 2. Entropy-based lane routing (thermal-router.ts + specialization.ts)
- Their rule: route work to the node minimizing H = latencyVariance x failureRate x
  (1 - domainSpecialization); per-node-per-domain EMA scores (start 0.5 neutral).
- OUR MAP: fuel_feed._free_channel currently picks free lanes in FIXED order (nvidia first).
  Replace with entropy scoring over the lanes: pick the lane with min H (cheapest reliable).
- FILE: mag/fuel_feed.py (_free_channel -> entropy picker).

### 3. Gate at the POLL, not at execution (agent.ts resource headroom)
- Their rule: both pollers refuse work when loadavg/cores > maxCPU/100 — the node self-throttles
  SUPPLY, it doesn't over-subscribe and fail tasks.
- OUR MAP: work_loop.sense()/run_once() should check the CPU ceiling BEFORE claiming/drilling/
  feeding — if over the 90% ceiling, report "ceiling" and skip (we have cadence_learn.ceiling();
  move the gate to the poll).
- FILE: mag/work_loop.py (add ceiling gate at the top of run_once).

### 4. Chain-verified capabilities + software manifest (contracts AgentRegistry.tact)
- Their rule: node registers with nodeId=sha256(pubkey), genesisHash MUST match the current
  protocol manifest (old/wrong software rejected), capabilities as a uint32 bitmask.
- OUR MAP: anchor each seat/lane's declared capabilities + software version to the verkle chain
  (team_knot can carry it); reject seats whose manifest hash doesn't match — "who can do what"
  becomes a chain fact, not a self-report.
- FILE: mag/team_knot.py (extend reality with per-seat manifest hash) + fuel_feed channel checks.

### 5. Signed result proof (sovereign proof: sign task_id + result_json with the wallet key)
- Their rule: every submitted result is signed so the network can verify provenance.
- OUR MAP: our banked artifacts already carry source; fold a signature/hash of the result into
  the verkle anchor so the chain proves who banked what (already partially there via leaf hash).
- FILE: mag/work_loop.py _anchor (include result hash in the anchor summary).

## Honorable mentions (adopt when cheap)
- SQLite offline queue with drain-on-reconnect (offline-queue.ts) — any seat that drops.
- GitHub-file-as-bootstrap (p2p/peers.ts reads gstd-seed-peers.txt) — zero-infra peer discovery.
- Gossip-your-peer-table-back-on-heartbeat — cheapest mesh-widening trick.
- Balance-gated mode switch (sovereign_agent.py) — free-first/paid-lane logic (we have offpeak).

## NOT adopting (aspirational/fake)
- gstd-bridge MPC (fabricated), /agents/* market (404), propagation beacons (marketing).
- libp2p mesh (real but effectively empty bootstrap; the HTTP gossip mesh is the working one).

## Research tie-in (blockchain lessons)
- Ethereum median-time/monotonic: our verified_clock.
- XRP federated agreement: team_knot as last-closed-ledger (agreed reality).
- Solana PoH: verkle chain position = order/clock.
- TON sharding: lanes as shards, queue as async messages — the GSTD forest IS the TON lesson
  made real, and we own it.

## Order to wire
1. Quality gate (#1) — protect the chain now.
2. Ceiling gate at the poll (#3) — protect the machine now.
3. Entropy lane routing (#2) — make the lanes smarter.
4. Chain-verified manifest (#4) — make capabilities a chain fact.
