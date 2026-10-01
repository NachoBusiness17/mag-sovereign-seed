# NNUE SIDECAR BRIEF — Hybrid Search + Learned Eval (canonical, 2026-09-04)

Received verbatim from the operator (follow-up briefing; provenance: the
DeepSeek-thread research line). This is the CANONICAL design source; the
seat-drafted design note (docs/ref/NNUE_ACCUMULATOR_DESIGN_20260904.md) is
the fleet-adapted companion. Both artifacts below in full.

## Part A — architecture sheet (portrait + landscape table)

Three columns: Stockfish NNUE + αβ, LC0 + MCTS, a 7B decoder agent.

Rows that matter for design: state representation, learned object, net shape,
eval latency, incremental state, search, nodes/sec order of magnitude, pruning,
transposition, training, where human knowledge lives, worst-case demand on
eval, quiet/tactical split, failure mode, what to steal.

The binding constraint: alpha-beta needs a calm leaf; MCTS can average a noisy
one; a raw 7B has no bound unless you add a rejector.

### One-sentence architectures
- Stockfish: legal-move generator → ordered Negamax with fail-hard bounds →
  NNUE leaf score (CPU, incremental) → TT / heuristics decide cutoffs.
- LC0: legal-move generator → PUCT/MCTS → deep residual policy+value (GPU,
  full forward pass per node, batched) → visit counts pick the move.
- 7B agent: tokenizer → decoder-only transformer (full or cached KV forward
  pass) → sample or argmax → optional tools / RAG / CoT / MCTS-over-text. No
  native game tree. World state lives in tokens.

### What each system optimizes
Stockfish: Elo per millisecond on CPU → tiny eval, deep exact-ish tree. LC0:
Elo per GPU-second → fat eval, shallow selective tree. 7B agent: next-token
logprob on pretraining, then planning bolted on afterwards. That last fact is
why agents feel less "Stockfish" than "a strong leaf eval with almost no
search."

### Where human knowledge lives
It never disappears. It moves. Stockfish: rules, feature geometry
(HalfKAv2_hm, threats, pairs), search heuristics, tablebases, Fishtest. LC0:
rules, input planes, MCTS constants, self-play curriculum. 7B agent: tokenizer,
data mix, RLHF rubric, tool schemas, system prompt, retrieval corpus. "From
scratch" always means "from the rules and the harness," not from a void.

### Worst-case behavior — the constraint that picks the search
Alpha-beta needs a leaf score that is rarely insane. One wild evaluation
poisons a cutoff and can flip the root. MCTS averages damage across visits.
Token-level sampling has no bound at all: a single bad token is committed
unless an outer loop rejects it. Wrapping a 7B in naive tree search without a
calibrated value head reproduces LC0's early years, not Stockfish's reliability.

### Compressed notes
- Stockfish NNUE 2026 master: HalfKAv2_hm, L1~1024 with 8 layer-stacks / 8
  PSQT buckets, L2=32, L3=32, sparse affine input, clipped/squared-clipped
  ReLU, dual nets for quiet vs decided. HCE removed in 16.1 (Feb 2024).
  Search still hand-engineered.
- LC0: resnet/attention, policy+value(+MLH/WDL) heads, batched GPU eval;
  1e4–1e5 nps enthusiast hardware vs Stockfish 1e6–1e8 on CPU.
- 7B class: ~32 layers, d~4096, GQA, 4k–128k context; KV cache is the only
  incremental state; tools and memory are text, not tensors patched by delta.

## Part B — design note: NNUE-style accumulator for agents

The problem: an agent between sibling thoughts changes a few facts (tool
result, file, constraint, clock) but rebuilds a prompt and re-runs attention
over thousands of tokens. That is LC0's calling convention — full encode every
node — forced onto a Stockfish-shaped job (many cheap what-ifs). NNUE's bet:
keep a running first-layer activation and patch it when the world patches.
Steal that split.

### 1. World features (sparse, typed, delta-friendly)
Do NOT feed raw tokens into the accumulator. Feature store keyed like HalfKA:
(entity, relation, slot). Examples: open files, buffers, cursor, git status,
last test result; tool schemas bound this turn; last N tool I/O hashes; user
constraints in force (deadline, tone, must-not); task graph (current node,
blocked, evidence pointers); episodic facts with stable IDs. Each active
feature is a row in embedding table W1. Sparsity target: tens to few hundred
active out of 1e5–1e6 — the 0.1% regime NNUE was built for.

### 2. Accumulator
A ∈ R^d (d=1024 or 2048, int8/int16 at inference). Feature add i: A += W1[i].
Remove j: A -= W1[j]. Update: remove-then-add. Persist A across tokens, tool
calls, search nodes. Rebuild from scratch only on hash mismatch, context
compaction, or task-root change (Stockfish's lazy refresh analog).

### 3. Small head (affordable to rerun)
Two-three tiny layers on A + dense side-channels (current utterance embedding,
time budget). Outputs = what search needs:
- Value: P(success | state) — calibrated. The leaf eval.
- Policy prior: distribution over next ACT TYPES (reply, tool X, search, ask,
  stop), not the whole vocab.
- Uncertainty/quiescence flag: quiet (answer) vs tactical (expand tools).

### 4. Discrete wrapper (thinner than alpha-beta)
1. Generate K candidate acts from the policy prior.
2. Apply each act's feature delta speculatively, patch A, run the head = leaf.
3. High uncertainty or tool act → expand one ply (call or simulate).
4. Bound: refuse acts below a value floor (fail-low); prefer stable winners
   across depths (iterative deepening).
The 7B stays the tongue: it renders the chosen act into tokens. It is no
longer the only world model.

### Why KV-cache is not an accumulator
KV stores attention keys/values for past tokens — incremental in SEQUENCE
LENGTH, not in WORLD FACTS. Adding a message appends KV; replacing a fact
needs stale-text or history-rewrite. Feature-table accumulators treat facts
as addressed rows. Tape vs position eval.

### Training recipe (Stockfish-shaped, not AlphaZero-cosplay)
1. Supervise value head on real trajectory outcomes (task success, user edit
   distance, test pass, time-to-done). Distill a stronger teacher into the
   small head, the way NNUE distills deep searches.
2. Train W1 so deltas are well-conditioned: one fact flip moves A by a
   bounded amount. Contrastive loss on (state, state-with-one-fact-toggled).
3. Calibrate value (temperature scaling / isotonic on held-out harness).
   Uncalibrated values cannot drive cutoffs.
4. Fishtest analog: A/B accumulator+head vs prompt-only 7B on a frozen suite.
   Ship only Elo-like wins (success rate at fixed latency).

### Minimal viable implementation
Feature extractor: LLM or rules emit add/remove feature IDs after every user
message and tool result. Table W1: 256k rows × 1024, int8. Head: 1024 → 256 →
64 → {value, 16 act-logits, uncertainty}. Loop: 7B proposes 4 sketches; sidecar
scores in microseconds; 7B renders the winner. If the sidecar does not beat
"just prompt the 7B with a longer scratchpad" at equal wall time, STOP.

### Failure modes
- Feature ontology rot: unstable IDs ("file:foo" vs "/abs/foo") = noise.
  Freeze a schema.
- Hidden state in prose: facts that never become features make A a lie.
  Extraction recall IS the eval quality.
- Uncalibrated value: classic alpha-beta poison. Prefer MCTS-like averaging
  until calibration proven.
- Refresh too rare: A drifts. Hash the feature set; rebuild on mismatch.

### What this is not
Not a water computer, not a liquid net, not a pretraining replacement. It is a
leaf-eval calling convention. The 7B stays renderer + commonsense prior. The
accumulator is the position. The discrete loop is the search. The Stockfish
split, named so it can be built.

## Part C — landscape table (compressed)

| Dimension | Stockfish (NNUE+αβ) | LC0 (resnet+MCTS) | 7B decoder agent |
|---|---|---|---|
| Job | move under clock | move under clock | tokens/tool calls under latency+policy |
| State | bitboards + feature indices | spatial planes | tokens + KV; tools/files as text |
| Learned object | scalar eval (+PSQT) | policy+value (+aux) | next-token distribution |
| Net | shallow MLP, quantized int | deep resnet/attention | ~7B, ~32 layers |
| Device | CPU+SIMD, no GPU at play | GPU, batched nodes | GPU/NPU, batch tokens |
| Eval latency | sub-µs after accumulator hit | ms/node unbatched | ms–tens of ms/token |
| Incremental state | YES: add/remove rows | NO: full forward | PARTIAL: KV grows, facts unaddressed |
| Search | negamax, αβ, ID, LMR, null-move, qsearch, Lazy SMP | PUCT/MCTS, Dirichlet | usually none; CoT/beam/tool-loop |
| Nodes/sec | 1e6–1e8 CPU | 1e4–1e5 GPU | 1e1–1e2 acts/s |
| Pruning | can't-beat-alpha; qsearch | low prior/visit | ~none unless outer critic |
| Transposition | clustered TT bounds+move | MCTS tree | context window; maybe vector DB |
| Training | supervised deep-search labels + WDL; SPSA; Fishtest | self-play RL from rules | pretrain+SFT+preference/RL |
| Human knowledge | rules, features, heuristics, tablebases, Fishtest | rules, planes, constants, curriculum | data mix, prompts, tools, rubrics, retrieval |
| Worst-case demand | severe: wild leaf poisons cutoffs | milder: visits average | none unless rejector added — then severe |
| Quiet/tactical | qsearch; dual NNUE | value+visits | absent; models ramble instead of quiescing |
| Failure mode | horizon + bad order; eval drift | shallow tactics; batch starvation | hallucinated state; stale context; no cutoff |
| What to steal | accumulator + calibrated cheap head + IDs | batched eval + prior-weighted explore | tongue / commonsense renderer |

Read across a row when designing an agent loop. LC0's net on Stockfish's
search = latency explosion. Stockfish's search on an uncalibrated 7B probe =
cutoffs lie. Part B exists to make the 7B column's incremental-state cell look
more like Stockfish's.

Sources: Nasu 2018 (NNUE shogi); SF12 2020 port; HCE removed 16.1 2024;
SFNNv8-v15 master 2025-26; AlphaZero Science 2018; Shannon 1950; Lukyanov
1936 as analog foil, not load-bearing physics; 2024-26 analog/PNN/iontronic
papers as hardware rhyme, not shipping plan. Working document; nps and 7B
shapes are family-typical order-of-magnitude.
