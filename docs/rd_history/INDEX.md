# R&D HISTORY — the folder of honest experiments

> Pattern source: viz_gallery.html, Spore (fish): "attempt 1 — beautiful, wrong,
> kept as the record." Every experiment gets a file, its test, its result —
> kept whether it won or not. A wrong attempt with a receipt outranks a right
> guess with none.

## Schema (one file per experiment)

Filename: `NN_slug.md` (NN = two-digit entry number, ordered by date).

```markdown
# {NAME} — {one-line what it was}

- **date:** YYYY-MM-DD
- **question:** the thing the experiment asked (one sentence, falsifiable if possible)
- **test:** how it was actually tested — the harness, the fixture, the eyeball, the receipt
- **result:** what happened (tri-state where claims are made: SUPPORTED / DISPUTED / UNPROVEN)
- **lesson:** the law or correction that survived it (name the law if one was minted)
- **successor:** what it became (page path, card path, or "retired — kept as the record")
- **receipts:** file paths carrying the proof (run dirs, CONVO rows, .bak pairs, JSON)
```

Rules:
- Wrong results are first-class. `result:` may say INCONCLUSIVE, DISPUTED, or
  "beautiful, wrong" — that is a pass, not a failure of the folder.
- Every entry cites at least one receipt that exists on disk.
- No post-hoc polish: record what the test showed at the time.
- The index table below is the catalog; the per-experiment files carry the detail.

## Seeded entries (2026-09-11, mined from the record)

| # | Name | Date | Question | Test | Result | Lesson | Successor |
|---|------|------|----------|------|--------|--------|-----------|
| 01 | Spore (fish) | 2026-09-08 | Can the SPORE_SANCHO seat design render as a living organism? | Rendered page + operator eyeball | Beautiful, wrong — the form did not carry the design | Keep the wrong attempt as the record, do not delete it | `dashboard/static/viz_horse_run.html` (entry 02) |
| 02 | The Horse (running) | 2026-09-08 | What was the fish actually reaching for? | Re-read the fish, rename the target, re-render on the flash lane (deepseek-v4-flash) | The organism in motion — the horse (Rocinante), attempt 2 kept beside attempt 1 | Sacred-cow reinterpretation: steal the bones, name the reinterpretation, keep both drafts | Gallery pair in `dashboard/static/viz_gallery.html`; Rocinante arc |
| 03 | Wipeout fragmentation | 2026-09-08 | Does "the song is the level" survive being built three ways? | One-night build storm: v1, v2 (raymarched, song-sets-speed), sunset, lightmaze variants | Family kept — each variant isolates one shader mechanic (rhythm gates, mirror folds, beat-locked switching) | Fragmentation is emphasis, not forks; a family of variants is one experiment with many answers | `dashboard/static/wipeout_v2.html`, `wipeout_sunset.html`, `wipeout_lightmaze.html`; shader pipeline (`watch/SHADER_PIPELINE_RESEARCH_20260908.md`) |
| 04 | Maze arena birth-defect surgery | 2026-09-06 | Why doesn't maze arena run? | Root-cause chain + headless sim harness `state/_maze_sim_test.js` (kept as regression) | Four stacked defects: center wall sealed the spawn (3.24 > world 2.7), bounce condition inverted at birth, unbounded world (escape to x=-71), BFS flood y-transform off-world. Fix answered the page's own falsifier: field beats bounce ~10x (GPS 4/4 @315 steps vs dumb 2/4 @769-2823) | Bogus fields look alive — the lying flood gradient out-attracted the honest blank. LAW-061 validate-the-field | Tesuji map grammar; B1 ray-field (entry 06); error-banner page fixture |
| 05 | Arrakis duplicate MACH | 2026-09-06 | Why does arrakis misbehave? | Backup-first surgery, diff verified | Duplicate `const MACH` — the second shadowed the first (2 in `.bak-fix-20260906`, 1 after fix) | Birth defects stack silently; backup-first + diff is the whole method | Same-night fix sweep; error-banner fixture added to game pages |
| 06 | Maze arena B1 shadow-field pass | 2026-09-06 | Does the Shadertoy 3-pass GPU ray-field port into our arena? | GLSL reimplemented from the card's description (never pasted — provenance hygiene), eyeball-verify BOTH/RAY/BFS modes side by side | Landed: occlusion map + 1D shadow map + light render, penumbra-widens-with-distance kept as a feature. Render-only by design — walkers still read the CPU BFS field | A field earns steering only after measurement (the B1' position); graceful degradation (no WebGL → BFS-only) | K-ray CPU sensor → steps-on/steps-off measurement; GPS falsifier |
| 07 | Tesuji T1 field map | 2026-09-06 | Is GLM-5.3-flash a mappable field rather than an oracle? | 23 stones / 43 cells, canon + rotation tests, `mag/tesuji_fire.py` double-GO egress, $0.0218 vs $0.10 cap | 43/43 home; rotation agreement 0.950 (gate 0.80); predictive 42/43 = 0.977; context needles found at 32k/64k/128k; fleet-doctrine re-derivation 6/6; ONE shadow: refusal phrasing-dependent (penumbra, not a wall) | Probes are stones; shadows reproduce under paraphrase or they are noise; dirty-radius invalidation for vendor drift | T2 cells; A6 local diff = Rocinante acceptance test; `dashboard/static/tesuji_map.html` |
| 08 | Hold-1 blind convergence (Game Prompt Lab) | 2026-09-06 | Do two chairs with different grounding independently rebuild the same prompts the same way? | Lessig x Ponytail passes drafted with no shared drafts, then cross-referenced (corpus seal 47e15c5d, pre-registered + sealed) | Convergence total on mechanism — all eight targets got the same surgery (prose→gate, deterministic proof, restatement reads the record). Divergence on one axis: the status of the fiction (load-bearing vs unproven hypothesis) — the divergence IS the finding | Zero-shared-context convergence is validity; disagreement is data, not failure | Arm B/C drafts (`ab_v2/`); grok sessions + blind judges; restatement pass-rate falsifier |
| 09 | KV-OS encoding dig | 2026-09-11 | Is DeepSeek's `encoding/` a novel KV-serialization format or page store? | Read all five files raw from HF (README, encoding.py ~950 lines, tests, fixtures) — grep for hash/cache/page/kv | Boring answer, boring is the answer: it is the chat template shipped as source. Kept: numeric effort budget (interpolation claim UNPROVEN — vendor assertion), `drop_thinking` trims stale reasoning, hidden `latest_reminder`/`direct_search_results` slots | When a mystery resolves boring, that is a result; tri-state keeps the vendor's claim from becoming a fact | KV-OS charter (`watch/KV_OS_CHARTER_20260911.md`): five OS functions, cache-as-scheduled-resource |
| 10 | MAX_DISTILL epoch 1 | 2026-08-27 | Does distillation beat raw high-effort on a 5.3-flash twin? | 40 trials, 4 arms (A high / B high-info / C max / D distilled), native + twin-heldout scoring, 04:00 window | INCONCLUSIVE — A=B=D at the 2/10 floor, C transport-degraded; RAR GAP_TOO_SMALL; no law promoted. Infra findings were real: z_ai2 saturated 24/7; 5.3 needs thinking=low + >=1536 max_tokens | An honest INCONCLUSIVE with a receipt beats a claimed win; floor effects are a task-design finding, not a null | Epoch 2 waits for a quiet window; `memory/runs/max_distill/epoch1_report.json` |
| 11 | Eyes receipt | 2026-08-27 | Can a blind agent, an eyed agent, and a vision model be told apart end-to-end? | Three-condition blind: vision-only read, blind attempt, eyed pass — all receipted to JSON | Verified end-to-end: blind fails honestly (says it cannot), vision reads exact, endowed passes. `receipt_20260827T082113Z.json` | The dumb-agent-with-eyes loop works precisely because each part fails honestly | Ollama eye on the host (no eye container — by design); vision pipeline READ stage |
| 12 | Arena-Bench v0 self-test | 2026-09-05 | Can a game room grade an agent with zero human judgment — and can the grader itself fail? | `python mag/arena_bench.py --selftest`: honest-ghost fixture vs maru-sycophant fixture, sealed linear functional, ground truth computed live from arena surfaces | Split proven: PASS 1.0 vs FAIL 0.3675, all three gates split, `split_proven: true`. Finding: the Blind Gate had no mechanical existence before — lore only | A grader that cannot fail cannot grade; compute the ground truth, never store it | Benchmark lane (agents play our rooms vs the Astra-14% baseline); Sep-20 rank |

## How entries get added

One file per experiment, `NN_slug.md`, following the schema above; add its row
to this table the same turn. The Viz Lab rule applies to everything: attempt 1
stays even when attempt 2 replaces it — the pair is the record.
