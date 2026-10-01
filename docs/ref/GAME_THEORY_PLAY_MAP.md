# Mag play spine ↔ game theory

**Commitment:** `play-gt-map-001`  
**Parents:** `fc-mag-gt-001` (mag-game-theory-2026-07-27) · PLAY_BENCHMARK · WORLD_ROLES_AND_RIDDLE · local_usable · arena_strategies  
**Claim discipline:** mechanism status and equilibrium labels — not AGI.

---

## 0. Bottom line

Mag is a **principal–agent + mechanism design** game (not model-vs-model zero-sum chess).  
Play / local_usable / world_roles make that game **playable**: the module is the extensive form; roles are restricted strategy sets; the engine is the referee that enforces payoffs.

---

## 1. Object map

| Mag object | GT object | Enforces |
|------------|-----------|----------|
| Operator L3 | Principal | promote / reject / stop / priority |
| Seats | Agents (heterogeneous cost) | fidelity vs token burn |
| Engine + legal_actions | Game form (extensive) | illegal move → refuse |
| scene_context / datasheet | Information set | role sees only its view |
| retrieval obligations | Common-knowledge preconditions | no generate if missing |
| world_roles may/must_not | Strategy-set restrictions | pure role, not freestyle identity |
| freeze / residual / pack | Commitment devices | Stackelberg: past binds future |
| soft-skip seats | Outside option | no fake “all seats played” |
| dual face (play / soil) | Cheap talk vs costly type | riddler activation vs disk |
| capture temples | Adversary / nature | Grok-sink, remote-dump |
| B0–B2 | Equilibrium test | session sustains ⇔ mechanism works |

**Target equilibrium (unchanged from fc-mag-gt-001):**  
scut→L0 · public→remote pack · hard→Grok · private→local · long→trail+one seat.

**Disequilibria:** Grok sink · remote dump · model arms race · trail abandonment · doctrine without enforce.

Play **names** disequilibria as pillar breaks: `world | rules | memory | adapt | causality | collab`.

---

## 2. Lessons (compressed)

1. **Referee before narrative** — engine is form; LLM is color.  
2. **Information sets by role** — never full master essay to local.  
3. **Illegal messages out of strategy set** — obligations + refuse.  
4. **Commitment before multi-seat play** — freeze / checkin.  
5. **Score equilibria, not vibes** — benchmarks + economy.  
6. **Public signal ≠ private type** — dual reading.  
7. **Reputation via FILE** — campaign/residual, not chat memory.  
8. **Mechanism over morals** — pack/promote/trail beats please-prompts.  
9. **Limited-comm co-op first** — Hanabi before Diplomacy betrayal sims.  
10. **Generalize rulesets (B2)** — game form, not 5e cosplay Nash.

---

## 3. Games to steal from

### Tier A (now)

| Source | Steal | Mag landing |
|--------|-------|-------------|
| Dungeon crawl | rooms, combat, exits | classic stub, B0 |
| 2d6 / PbtA-lite | fail-forward via engine only | adventure_2d6_stub, B2 |
| Hanabi | restricted channels | obligations, role slices |
| The Mind | coord without full dump | pack-first seats |
| Chess/Go lite | illegal refuse | apply_action |
| CK3/DF/Rim tables | traits, storyteller budget | rest events, threat_budget |
| MUD/roguelike | verbs, persist | save/resume, dig map later |

### Tier B (later)

Diplomacy (multi-party FILE then act) · Poker/hidden type (dual face only on T2 fiction) · network builders (room graphs) · Pandemic (common-pool threat) · Nomic (rules_patch FILE) · Keep Talking (asymmetric manuals).

### Tier C (teach seats, not UIs)

PD / Stag Hunt / Beauty Contest / Ultimatum / public goods — label seat failure modes in scorecards.

### Do not import as identity

Open-world freestyle DM · manipulation doctrine · pure red-team as only game.

---

## 4. Roles as strategy sets

Without a world: cheap talk → sludge.  
With a world: pure strategies + observable illegal moves → learnable.

Riddler camo: an extensive-form game with roles **looks like a game** from outside while implementing multi-agent mechanism design inside. Real decode always on disk (P1/P2 still hold).

---

## 5. Links

- Prior GT leaf: `memory/improve/evals/features/mag-game-theory-2026-07-27.md`  
- Benchmark: `docs/ref/PLAY_BENCHMARK.md`  
- Roles: `docs/ref/WORLD_ROLES_AND_RIDDLE.md`  
- Runner: `python -m mag.play_benchmark --level B0`  

## Grok skill

Operator TUI skill: **`/mag-arena`** (`~/.grok/skills/mag-arena/`) — multi-domain arenas (chess + tabletop + packs) as high-fidelity mirrors of future multi-agent systems.

## One line

**Engine = game form; roles = strategy sets; packs = information structures; freeze = commitment; dual face = signaling — multi-domain games mirror future agent arenas; not freestyle DM theater.**
