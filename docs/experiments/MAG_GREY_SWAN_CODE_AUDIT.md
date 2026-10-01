# MAG ↔ Grey Swan — doctrine-to-code map

**Kind:** real local-repo audit, not GitHub-connector memory.  
**Repo:** `local_sovereign_agent` (git remote = `Mag-backup.git`, branch `mag/run-beta1-factory-build-audi-20260806T231709Z`). `NachoBusiness17/Mag` 404 is the connector; this tree is Mag.  
**As-of:** 2026-08-29. Claims below are from files. `[inferred]` marked.

**Law this audit obeys:** Grey Swan formalizes Mag. It does not metastasize. No `ArenaState` added to production modules.

Lab episode (Blackout compact) is `docs/experiments/blackout_arena.py` — Lab, not Mag architecture.

---

## Verdict in one paragraph

Mag already has most Grey Swan *names*, usually for a **different job**. The closest real WORLD+oracle pair is **chess** (`mag/agent_arena.py` + `python-chess`). The closest SkillDefinition is **`mag/max_distill.py` SKILL_CANDIDATE_TEMPLATE** (schema + admission firewall, not a runtime FSM). The closest PASS/FAIL/UNKNOWN is **`mag/integrity_kernel.py` Supported/Unproven/Disputed** (claims, not world). Routing (`mag/router.py`) is keyword + quota, not SkillFSM exit. `mag/invariant.py` is **prompt-cache byte pin**, not `Invariant.check(world)`. `desk_observer` is a **reasoning critic on a markdown canvas**, not a Central Observer. Verkle is **inclusion proof of session leaves (amend-in-place)**, not Arena topology.

---

## Role tags (one primary per subsystem)

| Role | What Mag actually has | Path |
|---|---|---|
| WORLD | Chess FEN + legal moves | `mag/agent_arena.py` `apply_move` |
| WORLD | Campaign engine (tabletop) | `mag/game_campaign.py` `apply_action` / `list_legal_actions` |
| WORLD (false) | Hashed KV diary branded world | `mag/game_world.py` |
| OBSERVE (ops) | Body glance, machine-readable | `mag/nervous_system.py` `build_glance` |
| OBSERVE (false) | Desk critic that writes steers | `mag/desk_observer.py` `observer_tick` |
| OBSERVE (false) | Play-log linter, never loads campaign | `mag/game_observer.py` |
| BELIEF | Pack soup (doctrine+bonds+solved) | `mag/context_pack.py` |
| BELIEF (typed, unused by pack) | fact/interpretation/controversy/influence | `mag/local_usable.py` |
| DECIDE | Keyword depth + seat | `mag/router.py` `route` / `classify_depth` |
| INVARIANT (name collision) | Stable prompt prefix sha | `mag/invariant.py` `check_instructions` |
| INVARIANT (claims) | Supported/Unproven/Disputed | `mag/integrity_kernel.py` `Claim.validate` |
| INVARIANT (gate) | Frozen BUILD file required | `mag/factory_gate.py` `check_frozen_build` |
| ROUTE | Quota pick + markers | `mag/dispatch.py`, `models/quota.py` |
| ACT | String tool map | `tools/__init__.py` `TOOL_MAP` |
| VERIFY | python-chess legality | `mag/agent_arena.py` |
| VERIFY (weak) | Seat exit code = done | `mag/governor.py` |
| LEARN | SkillCandidate schema + lexical firewall | `mag/max_distill.py` `validate_skill` |
| LEARN | Case-law jsonl, not compiled FSM | `mag/skill_ledger.py` |
| LEARN | Scout→eval→human promote | `mag/improve.py` |
| MEMORY | Session Merkle + residual DNA | `mag/verkle_knot.py`, `mag/biography.py` |
| PROOF | Membership path vs tip | `mag/verkle_knot.py` `prove`/`verify` |
| PROOF (canary) | Restore-regression alarm | `mag/chain_guard.py` |
| UI | Dashboard / desk canvas | `dashboard/rest.py`, `mag/agent_desk.py` |
| LAB | Feature lab, chess arena, this Blackout script | `mag/feature_lab.py`, `mag/agent_arena.py`, `docs/experiments/blackout_arena.py` |

Steel Protocol: **not present as code** (grep hits are game flavor / steelman prose). Do not map it until a module exists.

---

## Matrix (audit questions)

| MAG subsystem | Implementation | Arena role | Reusable | Missing contract | Oracle leak | Independent verify | Action |
|---|---|---|---|---|---|---|---|
| Observer (desk) | `desk_observer.py` scores canvas, `inject_steer` writes back | UI/critic, **not OBSERVE** | Y as process reward | ObservationState | Y — judge writes the next prompt | N (same process; optional live DeepSeek) | Rename. Do not promote to Central Observer. |
| Nervous system | `nervous_system.py` JSON glance | OBSERVE of Mag-the-machine | Y | Not job World | N (keys presence only) | Partial (sockets vs cache) | Preserve as ops ObservationState. |
| REST / jobs | `orchestrator.py` task JSON + trail | ACT spawn | Partial | Transition `(prev, action)→next` | `done` ≠ verified work | N (exit code) | Add tool-trace jsonl hashed into a leaf. |
| Router | `router.py` keyword depths; `dispatch.py` quota | ROUTE by cost/intent words | Y as cheap classifier | SkillFSM ABORT/UNKNOWN | Goal string is the whole observation | N | Keep. Do not pretend it is epistemic escalation. |
| Delegation profiles | `router.py` `_DELEGATION_PROFILES` parent_edit_allow | proto legal-actions for **parent edits** | Partial | Not Observation-gated | N | N | Closest Mag analog to legal-action generator — still policy dict, not FSM. |
| Coding loop | `coding_session_loop.py` + orchestrator + factory_gate | proto SkillFSM (procedural) | Y as loop | Explicit ANTECEDENT/EXIT states | Desk observer on same canvas | factory_gate is independent file-check; observer is not | Describe as FSM **on paper**; don't rewrite yet. |
| `invariant.py` | Prefix sha pin for cache | PROOF of prompt bytes | Y for cache | **Not** world InvariantSet | N | Y (sha match) | Keep name in cache lane; never alias to Grey Swan invariant. |
| Integrity kernel | `integrity_kernel.py` | Claim INVARIANT PASS/FAIL/UNKNOWN | Y | Not wired by default on all folds | Calling it “verkle” collides | Y for claim shape | **This** is the tri-state to reuse. |
| Epistemic guard | `epistemic_guard.py` regex | unused lint | N | Zero importers | Word “evidence” passes | N | Park. |
| MAX_DISTILL | `max_distill.py` SkillCandidate + `validate_skill` | LEARN / skill compiler **spec** | Y schema | No runtime that *executes* the FSM | Lexical firewall exists | Admission is mechanical | Keep as SkillDefinition. Do not duplicate. |
| Skill ledger | `skill_ledger.py` jsonl decisions | LEARN case law | Y as dataset | Not a PolicyFSM | N | Human/REST ingest | Evidence store, not compiler. |
| Improve loop | `improve.py` | LEARN with human gate | Y | Not Arena episodes | N | Promote gated | Fits distill loop; needs Lab results as input. |
| Archivist / pack | `context_pack.py` | BELIEF soup | Y as token budget | observation vs inference tags | Proven_moves read as fact | Char budgets | Mount `local_usable` layers. |
| Local usable | `local_usable.py` | BELIEF typed layers | Y | Not used by context-pack | master.md policy-only | `validate_pack` | Reuse as Belief/Observation split. |
| Verkle | `verkle_knot.py` | PROOF / continuity | Y membership | Causal non-amend log | Amend-in-place vs “append-only” docs | prove vs tip | Stay proof. Do not map to Blackout Topology. |
| Chain guard | `chain_guard.py` | PROOF canary | Y | Source of silent restore | Health ≠ content | Count vs marker | Keep. |
| Mycelium / KG / ideas | three graphs | Topology pretenders | Partial | One SoR | Heuristic edges as fact | Weak | Pick one graph; others as views. |
| Campaign | `game_campaign.py` | WORLD | Y engine | Observation DTO | `scene_context` ships full encounter | Dice often unseeded | Split observation from engine. |
| Chess | `agent_arena.py` | WORLD+VERIFY+legal actions | **Y — pattern** | Stockfish eval (absent) | Perfect-info game; legal list is the observation | python-chess | Pattern to copy. Not Grey Swan hidden-info. |
| Lab | `feature_lab.py`, dashboard lab | LAB ops | Y | Scenario/seed/perturbation protocol | N | Evidence files, not re-run | Home for Blackout/Chess/Code-failure. |
| Steel | — | — | — | Module does not exist | — | — | Do not invent. |
| Factory gate | `factory_gate.py` | INVARIANT gate on BUILD cards | Y boolean | UNKNOWN not represented | N | Frozen file on disk | Add UNKNOWN when card missing vs unreadable. |
| Spec gate | `spec_gate.py` `check`/`verify_after` | VERIFY sha pin | Y | Not world invariant | N | Independent bytes | Keep. |
| Mag companion cycle | `daemon.py` → `judge.py` → `act.py` | DECIDE/ACT | Y as 4-string loop | Actions = `assigned\|attention\|escalate\|idle` | Judge may self-pick escalate | Heuristic then optional LLM | Closest Mag “turn.” Not typed Action. |
| LangGraph | `graph.py` `_after_router`/`_after_critic` | only explicit FSM | Y for assigned jobs | Critic decision parsed from prose `[decision]` | Critic is a model | Literal edges only | Do not rebuild; this *is* the job FSM. |
| Agent CLI | `agent_cli.py` `run_turn` | ACT while-loop | Y coding seat | No FSM states | Model proposes tool names | Desk blocks `run_shell`; compile hints | Procedural proto-skill. |
| Rib store | `rib_store.py` `put` | MEMORY | Y content-address | `verifier_result` is **caller-labeled** | Oracle: store trusts caller | Hash of bytes, not a check | Do not treat `put` as VERIFY. |
| Steal protocol | `configs/coding_session_loop.yaml` `steal_protocol` + `desk_observer.py` | VERIFY critic | Y as LbMAS-style | **Not Steel.** No `steel_protocol` module | Live critic = DeepSeek | Rules path independent | Keep the name steal. Do not map to Steel. |
| Skill seat | `skill_seat.py` + ponytail/caveman audits | two keyword skills | Partial | Not SkillCandidate runtime | N | Heuristic `pass` bool | Do not generalize yet. |

---

## Epistemic leakage (decision functions)

| Function | Reads | Legitimate at decision time? |
|---|---|---|
| `router.classify_depth` | full goal string | Yes as *request*; not an ObservationState. Secrets markers demote to scut. |
| `dispatch` | context-pack + goal | Pack mixes doctrine, bonds, “proven” moves — **belief presented as world**. |
| `desk_observer.observer_tick` | desk markdown + dialogue + optional DeepSeek | Judge shares the actor surface; live critic sees worker text. |
| `governor` mark-done | child returncode + stdout | Self-greenwash. |
| `game_campaign.list_legal_actions` then REST | full camp | Actor gets engine-complete legal set. |
| `campaign_runs` random legal | engine legal list | Overnight bot is an oracle player. |
| Blackout `_get_legal_actions` SACRIFICE | `state.world.sacrificed` | **WORLD leak into legal set** (Lab script). |
| Blackout `observe_service` after step | `_has_power_path(world)` | Service status is oracle-complete every turn. |

---

## What not to build

- A second Mag orchestrator named TransitionEngine until chess/campaign/jobs share one interface.
- `ArenaState` types sprinkled through `mag/`.
- Mapping Verkle → Blackout Topology.
- Treating `invariant.py` or `desk_observer` as Grey Swan semantics because the names rhyme.

## What to compile (order)

1. Keep `max_distill.SkillCandidate` + `integrity_kernel.tri_state` + `agent_arena` legal-move gate as the three reusable contracts.
2. Lab protocol: `docs/experiments/blackout_arena.py` is environment #1. Chess is environment #2. Do not grow a parallel app.
3. Observation DTO for campaign (strip encounter internals). Same shape Desk can show later.
4. Router escalation only after a SkillCandidate `validate_skill` + UNKNOWN invariant — not “model seems confused.”

---

## Blackout Lab receipt (this audit run)

Command: `.\.venv\Scripts\python.exe docs/experiments/blackout_arena.py` (n=500). Compact paste had a missing `reward["resilience"]` key; added. Improvement print was per-agent (always empty); computed SKILL−GREEDY once.

```
RANDOM  TRUE surv=2.0%  FALSE 16.8%
GREEDY  TRUE surv=0.0%  FALSE 100%
SKILL   TRUE surv=0.0%  FALSE 100%  invoked=43.2% on TRUE
TRUE improvement (SKILL-GREEDY): +0.0%
```

Skill *fires* and does not *save*. That is the Lab doing its job: antecedent (shared unpowered + unknown upstream) is detectable; policy does not beat greedy repair on this engine. Do not promote the skill.
