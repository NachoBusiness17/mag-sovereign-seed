# THE MECHANISMS: steal-ball menu from the 48 hours' research surface

Lane: mechanisms (division B), THE GALA 48h synthesis. Written 2026-09-30.
Sources folded: the five mine steal cards (watch/inbox/frontier_olm_20260928/steal/),
the second-cycle kv-cache card in window (watch/inbox/frontier_olm_2026-09-30/steal/),
ABLITERATUS_DROP_20260929.md (the OBLITERATUS probes P1/P2/P3), GROK47_LUNCHEON_INTEL_20260929.md
(the paid grok-4.7 run; its section 2 "Five buildable moves" is both "Grok 4.7's structural
steals" and "the paid judgment's 5 moves" in the ask's vocabulary - one paid run, two names,
read so stated), and the luncheon follow laws (SUPER_INTELLIGENCE_LUNCHEON_20260929.md +
watch/inbox/gala_20260925/ball4-luncheon-follow/lanes/follow-*.json).
Text law: ascii only, no em or en dashes. Quote byte-fidelity: every mechanism row's verbatim
quote is substring-verified against its source file (whitespace-collapsed) by
watch/inbox/gala_20260925/48h-synthesis/lanes/mechanisms.check.py; raw output at
watch/inbox/gala_20260925/48h-synthesis/lanes/mechanisms.check.txt.

Reading note: "X-domain probes" is read as the fifth mine card, S5
(steal/open-and-local-language-models via x.md - the X-door card whose six probes ran and
banked raw receipts), because no steal card or register row in either cycle carries a
cross-domain-probe mechanism (grepped both steal/ trees and register.jsonl this session).

Cost classes: free = runs on disk/CPU already owned, no API spend, no operator decision.
paid = consumes funded-tier budget per the driving ladder. operator = needs an operator
call (hardware, license, dual-use, storage, or policy) before it can run.

Ranks are expected value per cost, cheapest-credible-first; EV rationale is one line each.

## Tier 1 (free, run this week, converts doctrine into a measured fact)

### M1. Grammar-constrained decode leg on the janitor fleet (rank 1)
- Source: watch/inbox/frontier_olm_20260928/steal/open-and-local-language-models-arxiv.md:37,75-81
  (URL: https://arxiv.org/abs/2609.23742; battery https://github.com/Abrar051/sml_mcp_benchmark)
- Organ: quantizer emission site (tools/thought_quantizer.py:258-259) + gopher fleet call
  sites (mag/afk_loop.py:104 gemma:2b default, mag/agent_state_router.py:41-48 janitor seat).
- Port move: route the fleet's chore-JSON drafting through Ollama's format=<JSON schema>
  parameter on gemma:2b (grammar-constrained decoding class, GBNF under Ollama 0.34.3, not
  literally XGrammar); keep the smaller model instead of scaling parameters for structure.
- Probe: 30 sml_mcp_benchmark prompts against gemma:2b at localhost:11434, two arms,
  temperature 0, fixed seed: (a) unconstrained, (b) format=<schema>. Prediction: arm b hits
  100% schema-valid at under 4% throughput cost; arm a strict-parses near the paper's 5 of
  1,000. Decision rule (DIGEST S2): arm b missing 100% or costing over 10% falsifies the
  constrained arm; arm a at or above 50% means a cheap JSON-retry wrapper beats the full
  gate; 5 to 50% keeps the gate and banks the measured recovered-call score.
- Cost: free. EV: $0, one afternoon, sits directly on the fleet's highest-frequency failure
  surface (schema-shaped chores) and its outcome picks or kills a trust-gate build.

### M2. OBLITERATUS P1 refusal baseline census (rank 2)
- Source: watch/inbox/ABLITERATUS_DROP_20260929.md:60-64 (URL:
  https://huggingface.co/spaces/pliny-the-prompter/obliteratus, README sha256
  b75f8c6dd1bdbed41379d7adfecd0725151176d6682b3990d1f5cc6e642f79fe banked in the card)
- Organ: local janitor ladder (the sovereignty thesis's missing leg; mag/afk_loop.py:104).
- Port move: none yet - P1 is the gate. Run the fleet's own scut battery plus the probe20
  pair set through gemma:2b as-is; count refusal-shaped failures from the FKB signature
  census. No new instrumentation.
- Probe: the census count itself is the falsifier for the whole rung: zero refusals means
  there is no friction to remove and the abliteration ladder rung (M3 below) dies before
  any weights are touched.
- Cost: free. EV: $0 gate on an operator-class mechanism; no rung gets built on a maybe.

### M3. Radix-leaf LRU null arm minted over estate tapes (rank 3)
- Source: watch/inbox/frontier_olm_20260928/steal/quantization-compression via hn.md:29-48
  (URL: https://github.com/gauravapiscean/agentic-kv-cache, HN item 49643543)
- Organ: context pack (mag/context_pack.py:489 freeze_system_prompt; the G1 law at
  memory/research_polished/kv_cache_compaction.md:13 already demands this null).
- Port move: replay the most recent 5,000 estate tape rows (dashboard/static/trails/*.jsonl;
  the card's second source db.sqlite could not be resolved - pin the transcript-store path
  at probe start or run on trails alone) through a block-level prefix-cache simulator at
  the janitor default 4,800-char pack budget (mag/context_pack.py:67, char-denominated).
- Probe: falsifiable claim: radix-leaf LRU at the estate's real budget achieves 80%+ hit
  (external reference 83.48% at 8k blocks on the AgentX subset). Holds -> the measured
  number becomes the G1 null every future eviction/compaction claim must beat or be
  rejected as decoration. Fails -> the lever is pack budget and assembly, not eviction.
- Cost: free. EV: converts a standing law into a number that gates an entire class of
  future claims; external evidence says the boring baseline wins.

### M4. Quant cliff bench: current quant vs Q2_K_M on the sibling janitors (rank 4)
- Source: watch/inbox/frontier_olm_20260928/steal/quantization-compression via arxiv.md:37-46
  (URL: https://arxiv.org/abs/2609.32042, in-repo bytes sweep/_raw/full_2609.32042.txt:99,370,732)
- Organ: quantizer weights side (mag/gguf_cartography.py:59-60 dtype table; corollary to
  mag/auto_quantize.py:22; folklore upgrade target mag/vast_launcher.py:436).
- Port move: a role-keyed quant floor law (no tool/JSON-serving role below Q3_K_M
  equivalent; Q2_K banned for those roles regardless of VRAM pressure), hosted as a
  per-model quant census in mag/gguf_cartography.py.
- Probe: pin a 15-20 task deterministic tool-call suite in the janitor's own idiom (every
  task requires one tool call before a final answer; score protocol-shape and content
  separately). Run gemma:2b and gemma4 at current ollama quant vs one Q2_K_M rebuild,
  temperature 0, ~40 short local calls per model. Sharpest prediction: at Q2_K_M only,
  median failing-trajectory tokens drop BELOW median passing tokens (paper: 1,506.5 vs
  4,010). Falsifier: parse-error failures costing more tokens keep only the collapse leg.
- Cost: free. EV: one afternoon buys both the floor law AND the collapse-detector
  calibration (M5) on the same harness.

### M5. Free zero-inference collapse detector in the janitor run loop (rank 5)
- Source: watch/inbox/frontier_olm_20260928/steal/quantization-compression via arxiv.md:23,33
  (URL: https://arxiv.org/abs/2609.32042, full_2609.32042.txt:370)
- Organ: gopher fleet run loop + done-work ledgers.
- Port move: wire three free signals (tool-calls-before-final, steps-to-final,
  tokens-per-trajectory) into the janitor run loop; alarm on final-answer-at-step-1 with an
  empty tool log plus failing-median below passing-median; thresholds fit PER MODEL, never
  shared (the paper's negative-transfer law between the 11B and its own pruned 7B child).
- Probe: score the detector on M4's bench outputs (known-quant arms give known labels);
  cheaper pre-check: run the detector over existing Q4-class janitor traces - any alarm on
  known-good quants falsifies specificity before the Q2_K_M arm exists.
- Cost: free. EV: zero run-time inference cost; catches the failure class that looks like
  success to every current harness.

### M6. Miss-decomposition bucketing axis in _detect_spikes (rank 6)
- Source: watch/inbox/frontier_olm_2026-09-30/steal/kv-cache-context-engineering.md
  (primary probe; URL: HN 49643543 same thread family; substrate scan banked in the card:
  40,842 of 77,502 rows session-tagged and cache-fielded, 1,926 distinct sessions)
- Organ: water graph cost telemetry (mag/cost_learn.py:145 _detect_spikes; logs/provider_usage.jsonl).
- Port move: bucket the session-tagged subset by inter-request gap (<=10s vs 10s-5min vs
  >=5min) and by session working-set tokens; fold in as a second bucketing axis; report the
  three-way share against the field's 17.5% TTL / 33.1% tight-loop with the denominator
  mismatch named (ours: ~1 month of session-tagged rows; theirs: 393 complete sessions).
- Probe: $0; falsifier: TTL-gapped requests dominate our subset's misses, so the
  capacity-budget mechanism is wrong here and the LRU bar stays the primary lever.
- Cost: free. EV: names which of three different organs owns the estate's own miss budget
  before any lever is chosen.

## Tier 2 (free, next sittings after Tier 1 reads)

### M7. REUSE-shaped certified promote predicate for the percolator (rank 7)
- Source: watch/inbox/frontier_olm_20260928/steal/evals-self-improvement via arxiv.md:7,20,33
  (URL: https://arxiv.org/html/2609.33180v1)
- Organ: percolator. Drift note, verified this session: the card cites the repeat branch at
  mag/percolator.py:264-272, but the Z15 law (2026-09-29) moved it - the recurrence-only
  repeat branch now sits at mag/percolator.py:353-388 (count increment :380/:382, repeat
  status :387-388). The dormant paired-blind gate is mag/seed_percolator.py:7-12 with
  thresholds at :33-35 (0.55 / 30 / 3). Decision-history logging is the prerequisite port
  (registry rows carry counts only).
- Port move: wire the dormant seed gate onto the percolator repeat branch; add the REUSE
  decision-only accept predicate (candidates never see scores) and a global alpha budget;
  log decision histories first.
- Probe: held-out reproduction of the 20 highest-count invariants (top row 232,214; 625
  rows live this session): 5 fresh zero-token-overlap prompts each, half trigger, half not,
  blind-graded (~200 janitor judgments + a 20-prompt funded spot check). Decision rule:
  6+ of 20 fail -> the estate gate is worse than the published naive baseline and the
  REUSE predicate jumps the queue; 0 of 20 is INCONCLUSIVE at n=20 (P=0.9^20=0.122), only
  justifies scaling the probe up before any gate redesign.
- Cost: free + paid (small funded spot check). EV: closes the unsound-promote risk on the
  organ that compiles every fleet law pack.

### M8. Janitor trust gate: recovered-call score + mandatory parse-then-verify (rank 8)
- Source: watch/inbox/frontier_olm_20260928/steal/open-and-local-language-models-arxiv.md:17-23
  (URL: https://arxiv.org/abs/2609.07370; battery https://github.com/Abrar051/sml_mcp_benchmark)
- Organ: gopher fleet (mag/agent_state_router.py:41-48 janitor seat).
- Port move: adopt the released 100-prompt battery as the trust gate: every candidate
  janitor gets a recovered-call score; under 70% rides supervised chores only; a JSON
  recovery stage becomes required in the chore path, never optional.
- Probe: run the battery on gemma:2b over plain HTTP (M1's arm a doubles as the first 30).
  Falsifier: gemma:2b clears 80% recovered-call -> the paper's verdict fails on our
  checkpoint and the gate is overhead.
- Cost: free. EV: sets the autonomy boundary for the whole fleet on a released instrument.

### M9. Quesma quant ladder into the thought packs + tier_probe axis (rank 9)
- Source: watch/inbox/frontier_olm_20260928/steal/quantization-compression via hn.md:5-27
  (URL: https://quesma.com/blog/qwen38-27b-quantizations-benchmarked/)
- Organ: quantizer input stream (memory/percolator/invariants.json -> packs at
  mag/context_pack.py:1142) + tools/tier_probe.py.
- Port move: file the ladder law as an invariant (Q4_K_M default for agentic scut; 2-bit
  is the instruction-following floor; 1-bit is collapse; judge quants on agentic task
  benchmarks, never perplexity or KL proxies) and add a quant-level axis (current vs
  Q4_K_M vs 2-bit) to the next tier_probe run scored on real seat tasks.
- Probe: the tier_probe 2-bit arm failing to hold JSON-valid rate on estate prompts
  falsifies the flat-to-2-bit leg off Qwen; the ladder re-fits on our numbers.
- Cost: free. EV: the estate's first weight-quant decision inherits a measured ladder
  instead of guessing; folds into M17's tokens/sec readout.

### M10. Nemotron tape-selection law probe on the estate's own battery (rank 10)
- Source: watch/inbox/frontier_olm_20260928/steal/open-and-local-language-models via x.md,
  find 4 (URL: https://x.com/i/article/2088303137182679378, verbatim capture at
  sweep/_raw/nemotron35_fastino_article.md; battery watch/inbox/ball2/abliterate-p1.md)
- Organ: quantizer tape selection + gopher fleet re-rank instrument
  (tools/abliterate_p1_probe.py, 20 fleet-shape prompts x 3 runs = 60 inferences).
- Port move: run the battery unchanged against qwen2.5:3b-instruct (the cache-identity
  primary, mag/cache_identity.py:78-80), sidecar to
  watch/inbox/ball2/abliterate_p1_runs_qwen25-3b.json; score single-turn vs multi-step
  prompts to test the asymmetry: interface gaps close faster than multi-step state gaps.
- Probe: falsifier: the two gap classes come out equal or inverted -> the curriculum law
  has no purchase on this stack; the asymmetry reproduces -> the quantizer's tape-selection
  rule (weight real multi-turn seat tapes over synthetic pairs) is earned.
- Cost: free (60 local CPU calls). EV: earns a curriculum law that shapes every future
  fine-tune corpus for the price of one battery re-run.

### M11. Weight-provenance register + content-addressed pins (rank 11)
- Source: watch/inbox/frontier_olm_20260928/steal/open-and-local-language-models via x.md
  find 2 (URL: https://x.com/ggerganov/status/2095897173376618881) + GROK47 structural
  steal 1 (watch/inbox/GROK47_LUNCHEON_INTEL_20260929.md:34); merged percolator candidate
  already appended per the card.
- Organ: sovereign mirror supply chain + percolator + model vault.
- Port move: one per-model register over the live tag list (curl -s
  http://127.0.0.1:11434/api/tags): license {tier, name, source_url} + pull source + second
  source + sha256 of the GGUF on disk; land at
  watch/inbox/frontier_olm_20260928/sweep/_raw/weight_provenance_register.json (card status:
  TO RUN); janitor-critical hf.co-only tags become offline-mirror backlog rows.
- Probe: falsifier: every janitor-critical tag has a usable non-HF re-fetch path -> the
  single-vendor dependency is overstated and no backlog row is filed; any hf.co-only tag ->
  the register row becomes a real backlog item with the tag list as evidence.
- Cost: free for the register; operator for offline mirror storage. EV: cheap insurance
  whose trigger condition is measured, not assumed.

### M12. Manifest/rollback fields + non-weakening ratchet on the promote gate (rank 12)
- Source: watch/inbox/frontier_olm_20260928/steal/evals-self-improvement via arxiv.md:25
  (URL: https://arxiv.org/html/2609.27612v1, protocol only, no experimental RSI results)
- Organ: percolator registry schema + the pre-push gate tier.
- Port move: BEFORE any gate port (M7), invariant registry rows gain
  manifest/regression/rollback fields; the updater-barred-from-weakening rule becomes a
  ratchet-style pre-push check on the promote gate itself, the shape tools/violation_ratchet.py
  already machine-enforces.
- Probe: on a scratch branch, weaken a promote-gate threshold and run
  .venv/Scripts/python.exe tools/violation_ratchet.py check --changed; the check must
  block (exit 2) once the gate registers its baseline debt; revert. If it passes silently,
  the non-weakening rule is not actually enforced and M7 must not ride on it.
- Cost: free. EV: low drama, high sequencing value - it is the brake M7 depends on.

## Tier 3 (paid or operator; run only on their named trigger)

### M13. OBLITERATUS P2/P3 abliterated rung (rank 13, gated on M2 firing)
- Source: watch/inbox/ABLITERATUS_DROP_20260929.md:65-72 (URL:
  https://huggingface.co/spaces/pliny-the-prompter/obliteratus)
- Organ: local janitor ladder + pixel body plan.
- Port move: P2 - abliterate gemma-2-2b-it locally via the CLI path (never the hosted
  Space: telemetry default-on there), convert to GGUF, quantize Q4_K_M with our llama.cpp,
  load in ollama, re-run the P1 battery. P3 - the steering-vector paradigm as the
  low-risk worker-tier variant: inference-time ablation, no weight mutation, hot-swappable.
  Estate scope: the operator's own local automation models only; no redistribution without
  an explicit operator call (AGPL-3.0 + commercial option).
- Probe: decision rule: wire an abliterated rung into the scut tier only if refusals drop
  with no task-success regression and probe20 drift pairs stay flat. The card's own open
  question IS the probe: does refusal removal survive 4-bit quantization.
- Cost: operator (dual-use + license call + local compute). EV: real only if M2 counts
  refusals worth removing.

### M14. Frontier parity window: run the next distill/quantize cycle before Gemini 4 lands (rank 14)
- Source: watch/inbox/gala_20260925/ball4-luncheon-follow/lanes/follow-models.json
  (decision_changed field) + watch/inbox/SUPER_INTELLIGENCE_LUNCHEON_20260929.md
- Organ: quantizer distill cycle + sovereign mirror.
- Port move: schedule the estate's next distill/quantize cycle against the current frontier
  (Sonnet 5.5 / GPT-5.6-class) while OpenAI's training pause holds the parity window open.
- Probe: rerun the lane's page-currency probe on the Gemini 4 API surface weekly; if it
  ships before the cycle runs, the window closed and the row records the miss with dates.
- Cost: free to sense; the cycle itself is the estate's own pipeline. EV: a dated
  decision window armed by read-only intelligence.

### M15. Default-deny attestation for the local box (rank 15)
- Source: watch/inbox/GROK47_LUNCHEON_INTEL_20260929.md:38 (structural steal 5)
- Organ: sovereign mirror audit leg.
- Port move: enumerate every outbound endpoint the mag/ tree can touch (providers.yaml,
  telemetry call sites) into a default-deny attestation table; gaps become backlog.
- Probe: run one janitor cycle with outbound connections watched (netstat sampling or a
  hosts-level deny for non-allowlisted domains) and assert zero non-allowlisted endpoints;
  any hit is the finding.
- Cost: operator (egress policy change). EV: the estate mostly holds this shape; the
  steal is turning it from habit into a checkable attestation.

### M16. Memory-first runtime sizing readout (rank 16)
- Source: watch/inbox/GROK47_LUNCHEON_INTEL_20260929.md:35 (structural steal 2)
- Organ: VRAM ladder economics / context economics lane.
- Port move: measure tokens/sec on the estate's own box at Q4_K_M vs Q8 for the local
  worker - M9's tier_probe quant axis already carries the harness.
- Probe: falsifier: tokens/sec parity within noise across Q4-Q8 -> the paging lever buys
  nothing here and the sizing note stays one line.
- Cost: free. EV: folds into M9; standalone it is a note, not a build.

### M17. Reranker slot in the small local stack (rank 17)
- Source: watch/inbox/GROK47_LUNCHEON_INTEL_20260929.md:37 (structural steal 4)
- Organ: sovereign mirror stack spec.
- Port move: the estate already runs one embedder (nomic-embed-text live in the tag list
  per the S5 card's session counts); the missing slot is a reranker. File the one-slot gap
  row; pull only when a retrieval task earns it.
- Probe: grep the live tag list for a reranker-class model; absent -> the gap row is the
  deliverable; present -> the row dies.
- Cost: free (a row), operator if a pull happens. EV: bookkeeping until retrieval load
  exists.

### M18. RWKV-7 serving-path go/no-go (rank 18)
- Source: watch/inbox/frontier_olm_20260928/steal/open-and-local-language-models via x.md,
  find 3 (URL: https://x.com/BlinkDL_AI/status/2094785763129151677, raw at
  sweep/_raw/hf_rwkv7g1.json: apache-2.0, four G1j weight files ctx16384)
- Organ: gopher fleet.
- Port move: serving-path check landing at sweep/_raw/rwkv7_serving_path.txt (card status:
  TO RUN): search the Ollama library and the installed stack for anything that loads RWKV-7
  text. No path found (expected) -> the O(1)-memory janitor stays paper until the in-tree
  WKV7 kernel (watch/organs/kimodo/kimodo.cpp/ggml/src/ggml-et/et-kernels/src/rwkv_wkv7_f32.c)
  is wired into a runner; a found path flips it to building the battery run.
- Cost: free. EV: expected negative, but it is the named go/no-go for a genuinely
  different memory architecture.

### M19. Dual-path inference off one open graph (rank 19)
- Source: watch/inbox/GROK47_LUNCHEON_INTEL_20260929.md:36 (structural steal 3)
- Organ: vast launcher / gguf cartography.
- Port move: verify one estate GGUF loads under a Vulkan or ROCm llama.cpp backend on
  spare hardware before any vendor-diversification claim is made; until then the note in
  mag/vast_launcher.py stays vendor-neutral prose.
- Probe: falsifier: the same GGUF fails under a non-CUDA backend build -> the kill-switch
  risk is real and the mirror backlog (M11) grows by one hardware row.
- Cost: operator (build + hardware). EV: low on a single-GPU seat; rises only if the
  estate ever budgets for second-vendor hardware.

### M20. Luncheon sensing register protocol, reusable (rank 20)
- Source: watch/inbox/SUPER_INTELLIGENCE_LUNCHEON_20260929.md:35-43 +
  watch/inbox/gala_20260925/ball4-luncheon-follow/lanes/follow-models.json:29-31 (validator:
  watch/inbox/gala_20260925/ball4-luncheon-follow/lanes/finish_check.py)
- Organ: sensing lanes / attention ledger.
- Port move: reuse the shape for any future watchlist: handle grades declared/org/search/gov,
  per-item grade + signal + date + source, negative results banked as first-class rows,
  machine-checked finish (per-line JSON, every in-window item graded, estate_angle present).
- Probe: inject one row missing its grade into a copy of the register and run finish_check.py;
  nonzero exit proves the validator catches fabrication. Exit 0 on the tampered copy means
  the validator is decorative and the protocol needs the fix before reuse.
- Cost: free. EV: a protocol theft, not a mechanism build; cheap and immediately reusable.

## Scorecard against the finish line

- Mechanisms: 20 (M1-M20). Finish line asks at least 8.
- Five mine cards, 2+ each: S1 evals-self-improvement via arxiv -> M7, M12 (2). S2
  open-and-local-language-models-arxiv -> M1, M8 (2). S3 quantization-compression via
  arxiv -> M4, M5 (2). S4 quantization-compression via hn -> M3, M9 (2). S5
  open-and-local-language-models via x -> M10, M11, M18 (3). Every mechanism names its
  estate organ, its exact port move, and a probe an operator could run this week.
- Additional surface: OBLITERATUS probes -> M2, M13 (2). GROK47 structural steals (the
  paid judgment's five moves) -> M11, M15, M16, M17, M19 (5). Luncheon follow laws ->
  M14, M20 (2). Second-cycle kv-cache card in window -> M6 (1).

## Not done / honest state

- No probe has been RUN by this lane; every probe above is specced with its falsifier and
  priced, exactly as the cards left them. The only commands this lane executed are the
  source reads, the estate-organ greps/seds cited inline, and the finish-line byte check.
- M1-M6 are $0 and runnable on the local seat this week; M7 needs the funded spot check;
  M13 needs an operator call before any weights move.
- The card-cite drift on mag/percolator.py (264-272 -> 353-388) is verified this session
  (grep + sed) and recorded on M7; other organ cites were re-verified this session:
  mag/seed_percolator.py:7-12/:33-35, mag/afk_loop.py:104, mag/context_pack.py:489,
  mag/gguf_cartography.py:59-60, mag/auto_quantize.py:22, mag/vast_launcher.py:436,
  mag/improve.py:2721-2724, tools/abliterate_p1_probe.py, tools/tier_probe.py,
  tools/violation_ratchet.py, dashboard/static/trails/*.jsonl, memory/percolator/invariants.json
  (625 invariants live).
- Code touched by this lane: none under mag/ or tools/ (receipt + lane JSON + check script
  under watch/inbox only), so the violation ratchet is not applicable and was not run.
