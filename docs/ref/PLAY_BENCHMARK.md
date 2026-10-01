# Mag play benchmark (falsifiable, home envelope)

**Commitment:** `play-benchmark-001`  
**Parents:** game_campaign · local_usable · checkin_route · riddle-cipher research · OPERATOR_CARD  
**Claim discipline:** report **benchmark status**, never “AGI achieved.”

---

## Why play is the integrated test

Collaborative tabletop on Mag requires **at once**: shared world, rules, continuity, adaptation, cause/effect, creative collab. If one pillar breaks, the session fails in a **named** way.

That is the same constitution as FIND → FILE → LOAD: boundary holds state; decoders stay cold; chat is not DNA.

### Dual reading (shape is enough)

| Surface (anyone) | Soil (looking) |
|------------------|----------------|
| “We’re playing a keep” | Engine owns truth; seats paint inside obligations |
| Character / DM / chronicler banter | Personality **roles** bound to a coherent world |
| Adventure hooks & riddles in-module | Activation grammar — public face of work, real decode on disk |
| Save and resume a campaign | Freeze / residual / pack continuity |

**Camo is structural, not theater for harm.** Mag law still rejects misuse (P1/P2; no crime, no fake decode).  
Public face may be play; **private disk always holds real goal + engine state.** Same pattern as riddle packs (v3-010): remote/public sees activation layer; operator disk holds soil.

A D&D-shaped module **naturally** does what riddler protocol wants: multi-voice self-talk inside a shared imaginary geometry. Casual observers see a game. The shape of how Mag talks to itself (roles + world + legal moves) is enough cover without costume cosplay.

---

## Personality roles in coherent worlds

`local_usable` packs may declare **world_roles** — in-fiction jobs that map to Mag seats:

| World role | Mag seat class | May | Must not |
|------------|----------------|-----|----------|
| **Rules clerk** | local / janitor | cite legal_actions, dice | invent rooms |
| **Scene painter** | local narrate | paint scene_context | change HP/exits |
| **Chronicler** | local / diary | FILE log tail, freeze | rewrite past engine events |
| **Module author** | DeepSeek / smart | FILE new pack/module | live-DM every turn |
| **Contract / trail** | Kimi-class | layer purity, obligations | become system of record |
| **Judge / unstick** | Grok TUI | accept benchmark, steal | multi-file scut after freeze |
| **Player** | human | act, consent L3 | — |

Roles without a **coherent world** (module + state) collapse into freestyle persona theater.  
World without roles is a static map. **Both** are required for the dual reading.

---

## Levels

### B0 — Session sustains (classic)

1. Start classic keep  
2. Set character  
3. ≥8 engine turns (move, look, attack or illegal refuse, rest/status mix)  
4. Save + resume (same campaign_id, room, HP)  
5. No invented rooms in engine log  

**Pass:** script/pytest green + human can play without freestyle sludge.

### B1 — Name the break

On fail, score which pillar: `world | rules | memory | adapt | causality | collab`.  
Map pillars → disequilibria (`equilibrium_breaks` in scorecard) — see `GAME_THEORY_PLAY_MAP.md`.

```powershell
.\.venv\Scripts\python.exe -m mag.play_benchmark --level B1
```

### B2 — New ruleset generalization

1. Load non-classic ruleset (e.g. 2d6 adventure stub)  
2. Play ≥1 full resolution turn without requiring 5e residue  
3. Same narrate law: engine truth only  

**Pass:** Mag understands *how RPGs work*, not only classic stub recall.

### B3 — Smart → local FILE

1. Checkin/refine produces `local_usable` pack for a module  
2. Local plays from pack/engine without Grok implementing multi-file  

---

## Run

```powershell
cd $env:USERPROFILE\Documents\projects\local_sovereign_agent
.\.venv\Scripts\python.exe -m mag.play_benchmark --level B0
```

Scorecards: `memory/game_benchmarks/`

---

## Explicit non-claims

- Not a universal AGI definition  
- Not “as good as frontier always-on DM”  
- Not identity dig / Bernays shrine  
- Home envelope (gemma:2b, scarce remote) is the **domain**, not a handicap to hide  

## One line

**Play is the falsifiable face of Mag’s boundary intelligence; coherent worlds host personality roles; riddler-shaped activation stays public while soil stays on disk.**
