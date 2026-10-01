# Steal protocol repos — local reference index

**Purpose:** Multi-agent orchestrator / blackboard / cascade research clones for desk steal protocol.  
**Local clones:** `mine/raw/steal_protocol/` (gitignored — refresh below)  
**Manifest:** `configs/steal_protocol_repos.yaml`  
**Mag law:** contracts only — never default seat, never second DNA store.

**Sibling forest (coding agents / worktrees / MCP):** `docs/ref/AGENT_PLATFORM_REPOS_INDEX.md`

---

## Repos (11)

| id | Path | Steal focus |
|----|------|-------------|
| **agentswarm** | `robzilla1738/agentswarm` | Conductor + verifier + blackboard |
| **bmas** | `arvarik/bmas` | LbMAS control unit + rounds |
| **flock** | `whiteducksoftware/flock` | Typed blackboard orchestrator |
| **blackboard-core** | `hemantsingh443/blackboard-core` | Supervisor picks next worker |
| **ollama-agent-harness** | `Bradliebs/ollama-agent-harness` | Local lead + sub-agents |
| **subagent-router** | `marikarx/subagent-router` | DeepSeek/Ollama routing + budgets |
| **leeroo-orchestrator** | `Leeroo-AI/leeroo_orchestrator` | Expert model picker |
| **c3** | `EIT-EAST-Lab/C3` | Transcript credit assignment |
| **moa** | `togethercomputer/moa` | Layered proposer/aggregator |
| **ms-conductor** | `microsoft/conductor` | YAML workflow + Ollama |
| **agent-blackboard** | `claudioed/agent-blackboard` | MCP blackboard coordinator |

---

## Refresh clones

Windows:

```cmd
scripts\pull_steal_protocol_repos.cmd
```

Unix:

```bash
./scripts/pull_steal_protocol_repos.sh
```

**GitHub stars (optional — your account follows upstream):**

```cmd
set MAG_GH_STAR=1
scripts\pull_steal_protocol_repos.cmd
```

Requires `gh auth login`. Stars are separate from clone — Mag does not auto-star unless you set `MAG_GH_STAR=1`.

---

## Inventory probe

```cmd
.venv\Scripts\python.exe main.py probe-local steal-protocol
```

---

## Why this is not automatic

| GSTD / mesh | Steal protocol (before this index) |
|-------------|-------------------------------------|
| Curated yaml + pull script | Was chat-only — no manifest |
| Wired in `home_sync.cmd` | Not wired |
| `improve.yaml` rotation | Not in rotation |
| `gstd_probe` inventory | No probe |

**Mag never auto-clones on orchestrate/Step** — operator or `home_sync` runs pull scripts deliberately (gitignored soil, disk, license review).

---

## Field-steal example

```cmd
.venv\Scripts\python.exe main.py field-steal --root mine/raw/steal_protocol/robzilla1738/agentswarm --max-files 40
```
