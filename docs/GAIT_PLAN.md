# GAIT PLAN — scale in stages, learn every fall (2026-08-24)

The operator's law, learned the hard way: slow trickle -> proof of concept -> standing ->
tentative steps -> walk -> fall -> learn -> jog -> fall -> learn -> run. **Only then, after we
know what we are doing.** Scaling before knowing = the overnight burn (spin, bank nothing).

## The two commitments (the middle where we met)
1. **The operator's gait** — no stage is skipped; every fall is curriculum, not failure.
2. **Concrete stages** — each stage has a measurable definition of done, a metric, a
   fall-catcher, and a gate. We advance on data, not enthusiasm.

## The fall-catchers (already built — this is what the structure is FOR)
- **Quality gate** (GSTD steal #1): nothing weak enters the chain/percolator — bank only what
  clears a self-score floor. Falls don't pollute.
- **Ceiling at the poll** (GSTD steal #3): refuse work over the 90% CPU ceiling BEFORE claiming.
  Falls don't saturate the machine.
- **Lane rotation** (today's fix): no single lane carries everything. Falls don't saturate one lane.
- **The percolator**: every fall files a noise/lesson, not a loss. Falls become learning.
- **The verkle chain + verified clock**: reality and time are grounded bytes, not claims.

## STAGES

### Stage 1 — SLOW TRICKLE (current)
One signal, one lane, one result. Learn each lane's PERSONALITY: latency, rate limits,
failure modes, cache behavior. Do this across ALL lanes (rotating), a trickle at a time.
- **Definition of done**: a per-lane reliability profile ledger exists (per lane: calls,
  success, avg latency, failure modes, rate-limit behavior) from REAL trickle calls.
- **Metric**: lane profile coverage — every lane in the channel has >= N observed calls.
- **Fall-catcher**: one ask at a time; a lane failing just logs its profile entry.
- **Gate to Stage 2**: every lane in the channel has a real profile row (success/fail/latency).

### Stage 2 — PROOF OF CONCEPT
One real question, END TO END, through the full pipe: rotating lanes -> bank -> quality-gate ->
percolate -> one invariant on the chain. Proven once, measured.
- **Definition of done**: one real signal becomes one real, verkle-anchored invariant via the
  full pipe, with the quality gate actually exercised (a weak answer was rejected).
- **Metric**: full-pipe success (signal -> invariant) + gate rejections logged.
- **Fall-catcher**: the quality gate rejects weak output; the percolator files the lesson.
- **Gate to Stage 3**: the proof-of-concept invariant is on the chain, verifiable.

### Stage 3 — STANDING
The loop runs bounded, all lanes rotating, ceiling held, quality-gated, WITHOUT babysitting.
- **Definition of done**: survives a defined window (e.g., 6h) unattended; banks per tick;
  no lane saturated; no chain pollution (gate holds).
- **Metric**: uptime-without-intervention + banked-per-tick + per-lane share.
- **Fall-catcher**: ceiling-at-poll + quality gate + rotation — falls are cheap and logged.
- **Gate to Stage 4**: survived the window, banked consistently, gate rejections normal.

### Stage 4 — TENTATIVE STEPS -> WALK
Scale batch up as the lane profiles prove out; all real work sources feed (explore queue,
scrum backlog, cold vertices); no saturation.
- **Definition of done**: the loop walks across the ecosystem — every work source drained at a
  sustainable rate, all lanes carrying a share, machine usable.
- **Metric**: throughput per source, per-lane share, CPU under ceiling, cost profile.
- **Fall-catcher**: per-lane failure isolates; rotation heals; quality gate protects the chain.
- **Gate to Stage 5**: walking data exists (throughput + lane shares + cost) for a full cycle.

### Stage 5 — JOG -> RUN
Only after the walking data shows we know what we're doing: scale to the full ecosystem —
all seats, all lanes, the GSTD plug-in, the swarm across windows/machines.
- **Definition of done**: the ecosystem runs at meaningful scale, self-healing, cheap, banked.
- **Metric**: the full set — banked results, cost, uptime, lane health, chain integrity.
- **Fall-catcher**: everything from earlier stages, now load-bearing.
- **Gate**: none — this is the destination. But the gait never stops; falls keep teaching.

## Standing
- We are AT Stage 1. Do not advance on enthusiasm — advance on the stage's metric.
- The operator steers each gait; I make the stages concrete and the falls cheap.
- Every fall is recorded (ledger/percolator) — the falls are the curriculum.
