# ILAP proposal — v3 entry research

**Commitment:** ilap-v3-entry-001  
**Version arc:** v2 → v3 build gate  
**Status:** draft  
**Parent protocol:** `docs/ref/MAG_ILAP_PROTOCOL.md`

---

## One line

Before v3 volume coding: research harness/memory/agent trends (arxiv, Reddit, OpenClaw, X witness), steal contracts into Verkle-mapped slots, prove routing matrix green — then factory BUILD.

---

## Invariant

If we skip research and merge PRs blindly, we rebuild switchboard/conductor/improve overlaps and burn frontier seats on patterns already filed in `MAG_STEAL_AUTOPILOT.md` and `memory_verkle_map.md`.

---

## Concepts to research (P1)

| # | Concept | Sources | Mag slot hypothesis | Steal or skip? |
|---|---------|---------|---------------------|----------------|
| 1 | Harness memory ≠ chat scroll | OpenClaw docs, HF agent_memory, Anthropic harness essay | residual + pack + promote gate | steal → improve |
| 2 | Plan→build→audit factory | Anthropic agents, Factory missions | factory pilot + conductor phase | wire existing |
| 3 | PBX mesh / steer drops | Telecom steal, Cursor swarm economics | switchboard (shipped v3) | wire — already coded |
| 4 | DePIN edge inference | GSTD ai/frontend ARCHITECTURE | v5 gstd-inference seat | defer to v5 ILAP |
| 5 | Public activation / riddles | X witness spine, v3-010 backlog | spore + T2 surface | research only — no crypto yet |
| 6 | Mesh offline coordination | Briar/Bitchat/Bridgefy clones | switchboard + deferred G4 | research — `pull_mesh_comm_repos.sh` |

---

## Scout plan (P1)

```powershell
mag.cmd improve --once
mag.cmd research-pack --ask "OpenClaw memory promote vs Mag residual" --url "https://docs.openclaw.ai/cli/memory"
mag.cmd research-pack --ask "Anthropic harness long-running agents contract" --url "https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents"
python main.py resonance --tick --goal "v3-entry"
```

---

## Routing matrix (P2)

| # | Frozen goal | Expected seat | Expected phase | Expected pack_mode | Actual | Match? |
|---|-------------|---------------|----------------|-------------------|--------|--------|
| 1 | `doctor health status` | local | execute | janitor | | |
| 2 | `[build] factory audit json` | deepseek | build | build | | |
| 3 | `big picture v3 ecosystem` | grok_tui | plan | plan | | |
| 4 | `[steward] steward-prompts` | local | execute | janitor | | |
| 5 | `switchboard mesh status` | local | execute | route | | |

---

## Overlap results

| Scout finding | Existing module | Overlap % | Decision |
|---------------|-----------------|-----------|----------|
| OpenClaw MEMORY.md promote | improve promote gate | ~80% | wire — document in memory_verkle_map |
| Anthropic progress.txt handoff | trail cores / working.md | ~60% | wire — factory FILE checklist |
| Switchboard PBX | mag/switchboard.py | ~95% | wire only — no new module |
| GSTD DePIN | v5 pipe docs | 0% code | defer v5 ILAP |

---

## Verkle braid (this ILAP)

| Subsystem | Write |
|-----------|-------|
| improve | scout candidates from rotation |
| research_pack | OpenClaw + Anthropic REPORTs |
| training_events | `research_dive`, `ilap_cycle` on close |
| releases | gate `factory_pilot` after ILAP pass |
| verkle | `--dry` before `release record v3` |

---

## Outcome decision (P3)

- [x] **WIRE** for items 1–3 in overlap table  
- [ ] **BUILD** only factory-audit-json after matrix green  
- [ ] **DEFER** GSTD + riddle packs to dedicated ILAP proposals  

**Next BUILD:** `factory-audit-json` per `MAG_FACTORY_PILOT.md` — not v3 module volume.
