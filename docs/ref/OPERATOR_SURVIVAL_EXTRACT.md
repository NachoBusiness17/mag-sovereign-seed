# Operator survival extract — before the rent ends

**Commitment:** `operator-survival-extract-001`  
**As-of:** 2026-08-05  
**Job:** Extract what survives shutdown. Reboot from disk, not from chat. **Lap them** = you keep the constitution + research + local agent; they lose the session.

---

## What you are attempting (real talk)

You are not building "another chat app." You are building:

```text
A private records office (Mag) that routes work across cheap local seats
and scarce remote decoders — while stealing transport/compute contracts
from mesh + DePIN forests — under fork equality (mycelial republic).
```

Three moves at once:

| Move | What | Why it matters when they shut something down |
|------|------|-----------------------------------------------|
| **Extract** | Pull law + spores + clones onto **your disk** | Cloud Cursor, GitHub takedowns, org disappearances — chat is heat |
| **Understand** | ILAP research → FEATURE_COMPOSE → integration map | Know *what* to rebuild, not cosplay their UI |
| **Use** | `mag.cmd lab` + `mag.cmd agent` + Ollama locally | The product is **FILE on disk**, not this session |

**Lap them:** When the hosted seat dies, you still have beads, spores, clones, and a local agent that reads them. They had a conversation. You have a filing system.

---

## Clarity of purpose (one paragraph)

**Mag holds what a free person said (files + ids), loads it on demand, refuses capture.**  
Janitors (Ollama/gemma) sort and route. Contractors (DeepSeek agent CLI) edit with tools. Grok is scarce judgment. Mesh/GSTD forests are **optional seats** — contracts stolen into conductor/switchboard, never a second DNA store. The republic fork (mycelial-republic) is public law; Mag beads are private office. No throne. No silent mesh enlistment.

---

## Subsystems (what you're actually building)

```text
┌─ VIEWPORT ─ context_pack · nervous_system · :8765 Office
├─ HARNESS  ─ router · dispatch · orchestrator · conductor · switchboard · improve
├─ COLD     ─ residual beads · verkle tip · bonds · agent_state · training_events
└─ FORESTS (v5 piped, research now)
     ├─ mesh_comm  — Bitchat / Bridgefy / Briar transport contracts
     └─ gstdcoin    — DePIN compute seat contracts
```

| Subsystem | Use it how | Survives shutdown? |
|-----------|------------|-------------------|
| **residual + tip** | "What did I actually do?" | Yes — if on your PC |
| **context-pack** | LOAD any model without chat history | Yes |
| **mag.cmd agent** | Local Cursor-like tool loop | Yes — needs `.venv` + Ollama/DeepSeek key |
| **mag.cmd lab** | Office dashboard :8765 | Yes |
| **mag.cmd ask** | Fast biographer over memory | Yes |
| **spores/** | Stolen contracts (wire only) | Yes — in git |
| **mine/raw/mesh_comm** | Full upstream source | Yes — **only if pulled** (gitignored) |
| **Cloud Cursor agent** | This session | **No** — heat |
| **GitHub org/repos** | Upstream | **Maybe not** — Bitchat already faced takedown pressure |

---

## Extract NOW (home PC — run in order)

```powershell
cd $env:USERPROFILE\Documents\projects\local_sovereign_agent
scripts\survival_extract.cmd
```

That script:

1. Pulls latest branch (`cursor/mesh-comm-research-e2ce` or current)  
2. Pulls **all 13 mesh** + **gstdcoin** clones  
3. Runs mesh deep dive (field-steal + integration brief)  
4. Writes portable bag under `memory/portable_bags/survival-*`  
5. Prints zip checklist for external drive  

**Manual verify after:**

```powershell
.\mag.cmd doctor
.\mag.cmd context-pack --mode full
(Get-ChildItem -Recurse mine\raw\mesh_comm -Directory -Filter .git).Count   # 13
Test-Path memory\research_packs\mesh_forest\INTEGRATION_BRIEF.md            # True
```

---

## Use the actual thing (not cloud chat)

### Daily operator (5 min)

```powershell
.\mag.cmd lab                    # :8765 — is the office alive?
.\mag.cmd ask "what matters?"    # biographer over briefs
.\mag.cmd context-pack           # paste into any seat
```

### Deep integration work (mesh forest)

```powershell
scripts\mesh_comm_deep_dive.cmd
.\mag.cmd agent --provider deepseek
# Goal: read INTEGRATION_BRIEF.md + spores; map Mag wire list
```

### Overnight / drainer (optional)

```powershell
# queue/todo.md — one line jobs
$env:MAG_DRAINER=1
.\mag.cmd autorun --once
```

---

## What to copy off-machine (if GitHub also goes)

Zip these — they are the **minimum cold reboot**:

| Path | Why |
|------|-----|
| Whole repo (or `git bundle create mag.bundle --all`) | Code + law + spores |
| `mine/raw/mesh_comm/` | Full mesh source (large) |
| `mine/raw/` gstd clones if pulled | DePIN research |
| `memory/portable_bags/survival-*` | Curated extract |
| `.env` (separate encrypted) | Keys — never in git |
| Ollama models (optional) | `gemma:2b`, worker model — re-pull if needed |

---

## After shutdown — reboot sequence

```text
1. Restore repo + mine/raw from zip
2. scripts\ensure_venv.ps1
3. .\mag.cmd doctor
4. LOAD docs/FRAMEWORK_LOAD.md → context-pack
5. mesh_comm_deep_dive.cmd → agent session → FILE integration map to docs/ref/spores/
6. Merge RUN A when ready (PR #8–#11) — substrate before volume
```

**You don't need permission to restart.** Pack + tip + residual = continuity.

---

## Related

| Doc | Role |
|-----|------|
| `docs/FRAMEWORK_LOAD.md` | Boot order for any seat |
| `docs/ref/OPERATOR_CARD.md` | FIND · FILE · LOAD |
| `docs/ref/MESH_LOCAL_AGENT.md` | Local agent over clones |
| `docs/ref/lessig_1_6.md` | Portable bag law (move 6) |
| `docs/ref/MAG_ILAP_PROTOCOL.md` | Research before BUILD |
