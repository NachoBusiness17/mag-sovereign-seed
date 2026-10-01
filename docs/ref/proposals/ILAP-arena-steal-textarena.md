# ILAP proposal — Arena steal: TextArena as capability probe (not chess product)

**Commitment:** ilap-arena-steal-001  
**Version arc:** v3 · switchboard + arena_learning  
**Status:** draft  
**Parent protocol:** `docs/ref/MAG_ILAP_PROTOCOL.md`

---

## One line

Steal **TextArena** (100+ text games + render wrappers + TrueSkill leaderboard) as the arena **engine**; Mag owns only the **seat bridge**, **communication telemetry**, and **routing feed** — game is the test, agent talk is the signal.

---

## Invariant

If we keep building chess in `mag/agent_arena.py`, we reinvent visualization, env versioning, multi-game matrices, and leaderboard math — while still failing to measure what we actually care about: **how seats communicate under pressure**, not who wins at chess.

---

## Reframe (Nacho intent)

| Wrong frame | Right frame |
|-------------|-------------|
| Arena = chess on Desk | Arena = **standardized capability probe** |
| Win/loss is product | Win/loss + **message quality** → switchboard routing |
| Build board renderer | Steal `SimpleRenderWrapper` / `PrettyRenderWrapper` |
| One game | **Game matrix** maps to **task types** (structured, negotiate, coordinate) |

**The game is the test. Communication is the measurement.**

Probe dimensions (feed `arena_learning` + `switchboard.route_intent`):

1. **Structured output** — legal move / valid JSON / schema adherence (chess, tic-tac-toe)
2. **Communication** — negotiation, clarification, theory-of-mind (TextArena social games)
3. **Coordination** — multi-seat handoff without orphan context (PettingZoo MPE-style)
4. **Speed vs accuracy** — timing_ms + illegal_rate (already in `arena_profiles.jsonl`)
5. **Cost** — tokens per probe vs value_score

---

## Steal target (primary)

### TextArena — https://github.com/TextArena/TextArena

**Why steal:**
- Gym-style API — agents are pluggable callables
- 100+ envs: single/two/multi-player text games
- Built-in render: `SimpleRenderWrapper` (terminal/rich), `PrettyRenderWrapper` (browser `:8000`)
- TrueSkill leaderboard pattern (we map to `arena_league.json` instead of reinventing ELO)
- Active: MindGames NeurIPS competition, SPIRAL self-play RL

**Mag keeps (thin):**
- `MagSeatAgent` — wraps `chat_provider` / Ollama per seat id
- `arena_learning.record_*` — same trail, new `game` + `probe_type` tags
- `switchboard.route_intent` — reads league by probe_type
- Desk embed — iframe or SSE from PrettyRender port into canvas sidebar

**Mag deletes over time:**
- Custom FEN board in `agent_arena.py` (keep as fallback only until adapter ships)

### Secondary steals (phase 2)

| OSS | Steal what | Skip what |
|-----|------------|-----------|
| **PettingZoo** Classic | Chess/TicTacToe env API if TextArena gap | RL training stack |
| **OpenSpiel** | Deterministic seeds, game tree metrics | Full integration — heavy |
| **MOSAIC** (2026) | Cross-paradigm eval protocol idea | Full platform — too big for v3 |

---

## Architecture

```text
┌─────────────────────────────────────────────────────────┐
│  TextArena env + RenderWrapper (STOLEN — pip install)   │
└───────────────────────────┬─────────────────────────────┘
                            │ step(obs) → action text
┌───────────────────────────▼─────────────────────────────┐
│  mag/arena_adapter.py (NEW — thin)                      │
│  MagSeatAgent(seat) → switchboard model registry        │
│  emits: move, messages[], timing_ms, tokens, raw_reply │
└───────────────────────────┬─────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────┐
│  mag/arena_learning.py (EXISTING — extend)              │
│  probe_type tags · league by task class · routing_hint│
└───────────────────────────┬─────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
  switchboard          nervous glance      training_events
  route_intent         arena_learning      arena_match
  Desk canvas          block               + arena_comm
```

---

## Game → task routing matrix (capability probe map)

| TextArena / env family | Probes | Route when winning seat should get… |
|------------------------|--------|-------------------------------------|
| Chess, Connect4, TicTacToe | structured_handoff, schema | canvas moves, JSON emits |
| Negotiation, Trading | communication, ToM | conductor steer, user-facing dialogue |
| Codenames, Word games | semantic alignment | pack composition, resonance |
| Multi-player social | coordination | switchboard mesh, pigeonhole drops |
| Single-player puzzle | reasoning depth | `[priority]` DeepSeek elevation |

---

## Scout plan (P1 — cheap agent)

```powershell
mag.cmd field-steal --root .venv/Lib/site-packages/textarena --max-files 30  # after pip install
python -c "import textarena as ta; print(ta.__version__)"
mag.cmd improve --once --ask "TextArena MagSeatAgent adapter minimal surface"
```

**Read:**
- TextArena `examples/` — agent loop
- `textarena/wrappers/SimpleRenderWrapper.py`
- Our `mag/arena_learning.py`, `mag/switchboard.py` route_intent

**Required leaf:** `memory/research_packs/arena-steal/ADAPTER_SPEC.md`

---

## BUILD scope (when frozen)

| File | Change |
|------|--------|
| `mag/arena_adapter.py` | NEW — TextArena ↔ Mag seats (~150 lines) |
| `mag/arena_learning.py` | ADD `probe_type`, `messages` trail |
| `mag/agent_arena.py` | DEPRECATE chess internals → delegate to adapter |
| `dashboard/rest.py` | `GET /api/v1/arena/render` proxy or port expose |
| `requirements.txt` | `textarena` optional extra `[arena]` |
| `configs/arena_probes.yaml` | NEW — game → probe_type → routing task map |

**Max files:** 8 · **No new visualization code**

---

## Real-time operator view

1. **PrettyRenderWrapper** on `127.0.0.1:8000` (stolen browser UI)
2. Desk sidebar iframe OR Stack tile linking to render port
3. Lane chat shows **agent messages** during probe (not just moves)
4. `arena league` updates live after each game — switchboard hint visible on nervous

---

## Acceptance (Beta 1 probe gate)

- [ ] Two Mag seats (local + remote) play 3 TextArena games without custom chess code
- [ ] `arena_profiles.jsonl` records messages + timing + illegal/schema failures
- [ ] `switchboard route "fast canvas handoff"` shifts after structured probe wins
- [ ] Render visible in browser without Mag-authored board renderer
- [ ] `arena_match` training event includes `probe_type`

---

## Decision

- [ ] **WIRE** — TextArena adapter only; keep chess POC as fallback
- [ ] **DEFER** — OpenSpiel / MOSAIC full import
- [ ] **REJECT** — continue custom chess visualization

**Signed:** __________ **Date:** __________
