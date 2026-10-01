# Bleeding-edge agent repos — steal map + research direction

**Commitment:** `agent-bleeding-edge-repos-001`  
**As-of:** 2026-08-05  
**Parents:** user research brief (7 directions) · `AGENT_PLATFORM_REPOS_INDEX.md` · `MESH_COMM_REPOS_INDEX.md` · `AGENTIC_LANDSCAPE_2026.md` · `MAG_STEAL_AUTOPILOT.md`  
**Local clones:** `mine/raw/agent_bleeding_edge/` (gitignored — refresh below)  
**Manifest:** `configs/agent_bleeding_edge_repos.yaml`  

**Job:** Verify *bleeding-edge lore* against **public GitHub / HF / papers**, then map stealable contracts into Mag. Sibling forest to platform camp (IDE/workspace) and mesh_comm (BLE/Nostr transport).

**Mag law:** contracts only — never second orchestrator, never chat-as-DNA, never SaaS memory throne, never auto weight pull (`max_auto_pull_gb: 0`).

---

## 0. Honesty filter (read first)

| Claim class | How Mag treats it |
|-------------|-------------------|
| Public repo + docs (Letta, Mem0, exo, OpenHands replay, A2A, AgentOps) | **Primary quarry** — clone, field-steal, map |
| Tiny / name-colliding OSS (AgentLens ×2, agent-replay @ low stars) | **Contract quarry if local-first**; don't invent popularity |
| Spec tools misnamed as agent products (**WitGen**) | **False friend** — WitGen = zkEVM Lean *circuit witness IR* (`Verified-zkEVM/clean`), **not** agent run witnesses |
| Discord / leak lore (OS schedulers, FAANG FUSE agent-fs, “quiet agent” brands) | **Direction only** — no clone until artifact |
| Crypto agent bazaars (Solana/Stellar USDC markets) | **Watch** — steal discovery/skill.md grammar; reject payment throne |
| Formal provers (Lean4 / Coq / TLA+) | **P3 witness path** — Mag uses pytest/`post_run_eval` first |

Sibling forests:

- Coding platform / IDE client → `AGENT_PLATFORM_REPOS_INDEX.md`
- Offline mesh transport → `MESH_COMM_REPOS_INDEX.md`
- Blackboard / cascade → `STEAL_PROTOCOL_REPOS_INDEX.md`

---

## 1. Brief → verified map (7 directions)

| # | Brief direction | Verified public artifacts | Mag stance |
|---|-----------------|---------------------------|------------|
| **1** | Agent OS — exo/p2p mDNS; OS schedulers; Plan9/9P/FUSE agent-fs | **exo-explore/exo** (Apache-2.0). Plan9port / libfuse exist but **not** agent-fs products. OS-scheduler leaks: **direction only**. | exo → MESH_COMM / GSTD research. Agent-fs → residual + FILE bus **direction**; **do not build FUSE now**. |
| **2** | Spec-driven + agent witnesses — Lean/Coq, TLA+, “WitGen” | Lean4, Coq, TLA+ real. **WitGen ≠ agent witness** (zk circuit IR). OpenProver / DAP papers exist (Lean agents). | Witness = `post_run_eval` / pytest **first**; Lean later **P3**. |
| **3** | Time-travel / replay / AgentLens / agent blame | OpenHands trajectory replay + **OpenHands/trajectory-visualizer**. **clay-good/agent-replay** (local SQLite). AgentLens name collision: `agentlens-hq/agentlens` + `tranhoangtu-it/agentlens` (both tiny). Sweep = JetBrains coding assistant. | Steal trail JSONL + scrubber; Mag residual already partial. |
| **4** | Agent economies / specialist markets — Bazaar, Fixie, AgentOps | **AgentOps-AI/agentops** real. Fixie = SaaS SDK (`fixie-ai/fixie-sdk`), not marketplace. Bazaar = several crypto demos (watch). **a2aproject/A2A** = LF agent interop protocol. | Specialist seats via `route.v2` + tiny local models; reject payment/mesh throne. |
| **5** | Quiet agent paradigm | **Paradigm, not a repo.** Closest code cousins: Sweep PR-shaped loops; AgentOps cost gates; Mag L3 + autorun pause + promote. | Map to L3 gate + batch questions + PR-not-stream. |
| **6** | Self-managing context — Mem0, Letta/MemGPT, hierarchical memory | **mem0ai/mem0**, **letta-ai/letta** (MemGPT rename). Zep examples. **jina-ai/late-chunking**. | Steal hierarchy contracts → FKB + residual; reject SaaS memory throne. |
| **7** | Agent teaching / org memory / apprenticeship | No single dominant OSS “apprenticeship” repo. Closest: Letta self-edit memory + Mag improve promote + FKB. Discord Letta/Mem0: **watch**. | Org memory = FKB + improve; teaching = promote gates + residual tips. |

---

## 2. Steal map (contract → Mag deliverable)

| # | Contract | Best sources | Mag slot | Priority | Status |
|---|----------|--------------|----------|----------|--------|
| B1 | **Local inference / P2P mesh OS** | exo | GSTD / MESH_COMM research — not Mag DNA | **P2** | watch/research |
| B2 | **Executable witnesses** | Mag pytest first; Lean/TLA later | `post_run_eval` / heavy_code gate | **P0** | partial (A6/P2) |
| B3 | **Trajectory replay + agent blame** | OH traj viz; agent-replay; Phoenix | residual JSONL scrubber; autorun trail UI | **P0** | open |
| B4 | **Specialist seat economics / A2A** | AgentOps; A2A; mcp-agent | `route.v2` budgets + optional A2A card research | **P1** | open |
| B5 | **Quiet agent (batch / PR-not-stream)** | Sweep patterns; Mag L3 | autorun pause + promote + batch questions | **P0** | partial |
| B6 | **Hierarchical / self-managing memory** | Letta; Mem0; late-chunking; Zep | FKB + residual + tip cores | **P0** | open |
| B7 | **Org memory / apprenticeship** | Letta self-edit; Mag improve | improve promote + FKB bonds | **P1** | partial |

**Explicit non-steals**

- Second orchestrator (CrewAI / AutoGen / LangGraph as DNA)
- Chat-as-DNA or agent-to-agent chat coordination (use pack + trail / Elias rope)
- SaaS memory throne (Mem0 Cloud / hosted Zep / Fixie cloud)
- FUSE / Plan9 agent filesystem product this quarter
- Crypto payment bazaars as Mag identity
- Auto HF weight pulls (`max_auto_pull_gb: 0`)
- Invented “WitGen agent witness” product (false friend)

---

## 3. Repos — clone forest (Wave 1)

Shallow clones via pull script. Formal provers + crypto bazaars + tiny AgentLens forks are **Wave 2 / watch**.

| id | Upstream | License (check) | Steal focus | Mag slot |
|----|----------|-----------------|-------------|----------|
| **exo** | [exo-explore/exo](https://github.com/exo-explore/exo) | Apache-2.0 | P2P/mDNS local cluster | B1 |
| **letta** | [letta-ai/letta](https://github.com/letta-ai/letta) | Apache-2.0 | hierarchical + self-editing memory | B6, B7 |
| **mem0** | [mem0ai/mem0](https://github.com/mem0ai/mem0) | Apache-2.0 | memory CRUD / scopes | B6, B7 |
| **oh-traj-viz** | [OpenHands/trajectory-visualizer](https://github.com/OpenHands/trajectory-visualizer) | check | trajectory timeline UI | B3 |
| **agent-replay** | [clay-good/agent-replay](https://github.com/clay-good/agent-replay) | MIT | local SQLite replay/fork | B3, B5 |
| **agentops** | [AgentOps-AI/agentops](https://github.com/AgentOps-AI/agentops) | MIT | cost/session spans | B4 |
| **phoenix** | [arize-ai/phoenix](https://github.com/arize-ai/phoenix) | check | local OTel / eval UI | B3, B4 |
| **a2a** | [a2aproject/A2A](https://github.com/a2aproject/A2A) | Apache-2.0 | Agent Card + task lifecycle | B4 |
| **mcp-agent** | [lastmile-ai/mcp-agent](https://github.com/lastmile-ai/mcp-agent) | Apache-2.0 | MCP workflow compositions | B4 |
| **late-chunking** | [jina-ai/late-chunking](https://github.com/jina-ai/late-chunking) | Apache-2.0 | late chunking eval | B6 |
| **zep** | [getzep/zep](https://github.com/getzep/zep) | Apache-2.0 | long-term memory examples | B6 |
| **sweep** | [sweepai/sweep](https://github.com/sweepai/sweep) | check | issue→PR quiet loop | B3, B5 |

### Wave 2 / watch-only (do not default-clone)

| id | Upstream | Why deferred |
|----|----------|--------------|
| **agentlens** | agentlens-hq/agentlens | Real MIT CLI; tiny stars — steal diagnose grammar on demand |
| **agentlens-observe** | tranhoangtu-it/agentlens | Name collision; self-hosted obs |
| **agent-bazaar-*** | Allen-Saji / Agent-Bazaar orgs | Crypto markets; discovery grammar only |
| **fixie-sdk** | fixie-ai/fixie-sdk | SaaS platform SDK, not specialist bazaar |
| **lean4 / tlaplus / coq** | leanprover, tlaplus, coq | Formal witness P3 — huge |
| **plan9port / libfuse** | 9fans, libfuse | 9P/FUSE direction — no Mag FUSE now |
| **continue / pearai** | already in agent_platform | IDE client camp |
| **WitGen** | Verified-zkEVM/clean witgen IR | **Not** agent witnesses |

---

## 4. Research weeks (after pull)

### Week E — Memory contracts (B6, B7) — **this week priority**

```text
1. Letta  — core vs archival memory; self-edit APIs → Mag residual layers
2. Mem0   — add/search/update scopes → FKB bond shapes (reject cloud)
3. late-chunking — retrieval chunking ideas for tip cores
```

### Week F — Replay / quiet / blame (B3, B5)

```text
1. OpenHands trajectory-visualizer + existing OpenHands clone (platform forest)
2. agent-replay — SQLite trace schema vs Mag JSONL residual
3. Sweep — PR-not-stream / batch-report UX cousins
4. Mag Desk — batch questions + promote (already partial L3)
```

### Week G — Economies + A2A (B4)

```text
1. AgentOps / Phoenix — cost + span grammar for seat budgets
2. A2A Agent Card — compare to Mag pack (interop research only)
3. mcp-agent — workflow patterns over existing MCP bridge plan (A5)
```

### Week H — Mesh OS + witnesses (B1, B2)

```text
1. exo — mDNS/P2P inference mesh → document beside MESH_COMM (not Mag DNA)
2. Witness path — harden post_run_eval/pytest; defer Lean
3. Agent-fs lore — FILE bus + residual paths only; no FUSE
```

---

## 5. HF specialist coding models (&lt;3B) — watch list only

**Policy:** list + seat-route research. **No auto download** (`improve.yaml` `max_auto_pull_gb: 0`).

Verified via HF Hub API (downloads/likes as-of 2026-08-05; re-check before pull):

| Model id | ~size | Notes |
|----------|-------|-------|
| [Qwen/Qwen2.5-Coder-0.5B-Instruct](https://huggingface.co/Qwen/Qwen2.5-Coder-0.5B-Instruct) | 0.5B | Tiny specialist coder |
| [Qwen/Qwen2.5-Coder-1.5B-Instruct](https://huggingface.co/Qwen/Qwen2.5-Coder-1.5B-Instruct) | 1.5B | Strong small coder (+ GGUF sibling) |
| [deepseek-ai/deepseek-coder-1.3b-base](https://huggingface.co/deepseek-ai/deepseek-coder-1.3b-base) | 1.3B | Classic small coder base |
| [bigcode/starcoder2-3b](https://huggingface.co/bigcode/starcoder2-3b) | 3B | Cap edge — fill-in / code completion |
| [stabilityai/stable-code-3b](https://huggingface.co/stabilityai/stable-code-3b) | 3B | Cap edge |
| [ibm-granite/granite-3b-code-instruct-2k](https://huggingface.co/ibm-granite/granite-3b-code-instruct-2k) | 3B | Cap edge instruct |
| [HuggingFaceTB/SmolLM2-1.7B-Instruct](https://huggingface.co/HuggingFaceTB/SmolLM2-1.7B-Instruct) | 1.7B | General small; not code-specialist but seat-cheap |

Operator pull is manual (Ollama / HF CLI) when a Mag seat is budgeted — never improve-scout auto-pull.

---

## 6. Search queries (GitHub + scout)

| Intent | Query seeds |
|--------|-------------|
| Memory layers | `MemGPT Letta`, `mem0 memory layer`, `hierarchical agent memory` |
| Replay / blame | `agent trajectory replay`, `agent-replay sqlite`, `OpenHands trajectory` |
| A2A / MCP agents | `a2aproject A2A`, `mcp-agent lastmile`, `agent card protocol` |
| Local mesh OS | `exo-explore exo`, `mdns llm cluster` |
| Late chunking | `jina late chunking`, `chunked pooling` |
| Avoid as artifacts | `WitGen agent witness`, `FAANG FUSE agent fs`, `OS scheduler agent leak` |

Improve kind hint: `agentic_contract` (memory / replay / quiet).

---

## 7. Mag relevance matrix

| Foreign pattern | Steal | Reject |
|-----------------|-------|--------|
| Letta hierarchical memory | Layer names + self-edit API shape | Letta as Mag brain / cloud |
| Mem0 memory CRUD | Scope keys → FKB bonds | Mem0 Cloud throne |
| OpenHands traj viz | Scrubber UX over Mag JSONL | Their orchestrator |
| agent-replay SQLite | Local fork/replay CI gate | Second trail store as DNA |
| AgentOps / Phoenix | Cost + span enums | Cloud ops as identity |
| A2A Agent Card | Interop research vs Mag pack | Chat-between-agents DNA |
| exo mesh | GSTD/MESH_COMM notes | Mag default seat mesh |
| Quiet paradigm | Batch Q + PR promote | Brand cosplay product |
| Lean / TLA | Future witness P3 | Blocking Mag on formal tools |
| WitGen (zk) | Ignore for agents | Pretending it is Mag witness |

---

## 8. Named watch list (brief)

| Watch | Status |
|-------|--------|
| Letta / Mem0 Discord | Direction / community patterns — no clone |
| continuedev / pearAI | Already in **agent_platform** Wave1 (Continue + pearai-submodule); pearai-app deferred |
| HF &lt;3B specialist coding | Listed in §5 — manual seat only |
| MCP agent-to-agent | **a2aproject/A2A** + **mcp-agent** cloned; Mag stays pack+trail for coordination |
| jina.ai late chunking | **jina-ai/late-chunking** cloned |

---

## 9. Refresh clones

Windows:

```cmd
scripts\pull_agent_bleeding_edge_repos.cmd
```

Unix:

```bash
./scripts/pull_agent_bleeding_edge_repos.sh
```

Optional Wave 2:

```cmd
set MAG_BLEEDING_EDGE_WAVE2=1
scripts\pull_agent_bleeding_edge_repos.cmd
```

**Mag never auto-clones on orchestrate/Step** — operator runs pull deliberately.

**Windows note:** `arize-ai/phoenix` has cassette filenames that exceed default MAX_PATH. Pull script / operator should `git -C … config core.longpaths true` before checkout (or enable OS long paths). Research steals do not need those test cassettes.

Inventory:

```cmd
dir mine\raw\agent_bleeding_edge
```

---

## 10. Linkage

| Doc | Role |
|-----|------|
| `AGENT_PLATFORM_REPOS_INDEX.md` | Coding-agent platform camp (P1–P10) |
| `MESH_COMM_REPOS_INDEX.md` | BLE/Nostr transport — exo pairs here |
| `AGENTIC_LANDSCAPE_2026.md` | A1–A12 + brief pointers |
| `HANDOFF_MAG_AGENT_TODOS.md` | Operational B3/B5/B6 rows |
| `configs/improve.yaml` | `agent_bleeding_edge_repos` local source |

Update this index when a B-row ships — flip Status and note the Mag path.

---

*End bleeding-edge repos — commitment `agent-bleeding-edge-repos-001`*
