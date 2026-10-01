# V4 BUILD PLAN — generational audit fusion (2026-08-28)

Sources: four audits — AUDIT_grok_correctness.md (30KB, 10 named regressions
R1-R10), AUDIT_zai_economics.md (10 regressions + compute_event.v1 schema),
AUDIT_codex_interface.md (ergonomics), AUDIT_deepseek_merge.md (7 regressions)
— plus SYSTEM_BRIEF_V4 reviews. Grok's frame correction governs this plan:
**the Mag modules and the Vast modules are complementary organ systems, not
generations.** The Vast tree procures and boots; the Mag tree governs, routes,
keeps the ledger. V4 = one animal.

## Verdict table (fused)

| Module | Verdict | Notes |
|---|---|---|
| mag/compute_reconcile.py | KEEP + EXTEND | 4/4 auditors: owner of measure→reconcile→cadence. Must learn vast instances. |
| mag/fuel_feed.py | KEEP | Work feed. Blades without it are space heaters. Best per-lane telemetry in the fleet. |
| models/quota.py | KEEP | The only real cost ledger either generation has. Port its pattern to vast spend. |
| mag/desk_model_probe.py | MERGE | A/B probe → sizer validation + tok/s-at-READY measurement. |
| mag/free_tier.py, cheap_swarm.py | MERGE | Intent-routing + daily-cap patterns; static notes and hardcoded paths retire. |
| state/vast/boot_watcher.py | KEEP | Net-new, best operator rail. Fixed live tonight (grok path/predicate bugs). |
| state/vast/blade_buyer.py | KEEP/MERGE | Caps are law. Fix credit() comment/code drift; emit compute_event rows. |
| state/vast/sizer.py | MERGE | Pure planner today; gains live profiling + persisted decision reports. |
| state/vast/seeker.py | SPLIT (see dissents) | Codex: RETIRE into config-driven controller. Elder/zai: KEEP (dream-host tier is a real feature). Resolution: config-driven hunt config, dream-host kept as a config entry. |
| state/vast/box_contract.sh | KEEP | Stall-proof + phased READY handshake. |

## Build order (regression-ordered; regressions are the queue)

**V4.0 — the governor learns the fleet (blocks all scaling):**
1. Extend `compute_reconcile.measure()`: show_instances(), wedge/success
   ledger, credit, fuel_feed backlog, local GPU posture (R1/R3/R8; elder+grok).
2. Implement `reconcile()` BUY/RESIZE/REAP as the ONLY mutator; hunters become
   proposers behind its lock (grok R-races; elder ruling).
3. SPEND ledger: quota.py pattern — every create/destroy/kill/probe appends
   `compute_event.v1` rows with cost_usd + balance_before/after; covenant
   enforced as Σ-per-window (zai #1).
4. Pytest gates for the organs (grok R10: a print-loop selftest is not a gate).

**V4.1 — proof of value:**
5. tok/s probe at READY (desk_model_probe shape) → effective-$/useful-hour
   per host (zai/grok/codex convergence).
6. Sizer auto-profiles live boxes (nvidia-smi/free/df over ssh) — typed
   profiles retire (zai #7).
7. Entropy routing: hard→brain, easy→blades (elder #5); unused READY = failed
   reconcile → fuel_feed must have a queue item before a buy fires (elder #2).
8. Local-loop posture: desk GPU idle → bring-up-local beats renting (elder #7).

**V4.2 — the operator surface:**
9. One answer-first status/verdict surface (codex): "what is misallocated and
   what should change" — persisted JSON verdict `rightsized|misallocated` with
   named actions, rendered phone-first.
10. Lemon throttle (strike counts + expiry) replacing forever-blacklists.

## The $5 experiment (unchanged, now governed)

Runs ONLY after V4.0 lands — the governor, not raw hunters, runs it. Same
pre-registered thresholds as V4_SPEC.md: one blade, 45 min real fleet
prompts, prove = continuous serve + tok/s ≥ home baseline + $/1k < API price;
kill = any manual repair. Documented honestly either way.

## Dissents preserved

- Codex RETIREs seeker; elder/zai KEEP it — resolved as config-driven hunt
  with the dream-host as config (verify the resolution survives contact).
- Elder: 331MB wedge was an aria2c pool failure → pre-download checksum
  handshake. [Unproven]
- Grok: desk sleep is the dominant spend leak. Test: kill the hunter with a
  box up; reconcile must still reap. [Unproven]
- Zai: attention-per-healthy-boot-hour is the ROI metric. [no receipt yet]
