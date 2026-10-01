# Agent platform repos — steal map + research direction

**Commitment:** `agent-platform-repos-001`  
**As-of:** 2026-08-05  
**Parents:** `AGENTIC_LANDSCAPE_2026.md` · `MAG_STEAL_AUTOPILOT.md` · `STEAL_PROTOCOL_REPOS_INDEX.md` · trench brief (IDE camps / worktrees / ACP)  
**Local clones:** `mine/raw/agent_platform/` (gitignored — refresh below)  
**Manifest:** `configs/agent_platform_repos.yaml`  

**Job:** Map *real GitHub repos* (not Discord lore) to **stealable Mag contracts**. Camp thesis: agent platform wins; IDE is a client.

**Mag law:** contracts only — never second orchestrator, never chat-as-DNA, never auto-merge.

---

## 0. Honesty filter (read first)

| Claim class | How Mag treats it |
|-------------|-------------------|
| Public repo + docs (OpenHands headless, SWE-agent ACI, jj workspaces) | **Primary quarry** — clone, field-steal, map |
| Archived forks (Void, Aide) | **Reference archaeology** — optional clone; don’t bet product on them |
| HN/Discord “leaks” (Cursor Zero, FAANG FUSE agent FS, Amazon mesh) | **Direction only** — no clone target until a public artifact exists |
| Brand cosplay (CrewAI theater, second LangGraph) | **Reject** as DNA; steal status enums / tool schemas only |

Sibling forests:

- Blackboard / cascade → `STEAL_PROTOCOL_REPOS_INDEX.md`
- Bleeding-edge (memory / replay / quiet / A2A / exo) → `AGENT_BLEEDING_EDGE_REPOS_INDEX.md`
- Offline mesh transport → `MESH_COMM_REPOS_INDEX.md`

This index is **coding-agent platform + workspace + tool bus**.

---

## 1. Thesis → Mag slots

```text
foreign coding agent
  → isolate workspace (worktree / jj workspace / container)
  → tool loop + test gate
  → structured trail (JSONL / residual)
  → human approve *goal* (intent), not every hunk
  → Mag router remains sole dispatch brain
```

| Camp | Win condition | Mag stance |
|------|---------------|------------|
| **IDE camp** (Void, PearAI, Melty, Aide) | Agents as editor features | Steal **chrome contracts** (chat=commit, intent review). Do not fork VS Code. |
| **Platform camp** (OpenHands, SWE-agent, Aider, custom mesh) | Editor is one client | **Home camp.** Mag Office + `agent_cli` + orchestrator. |
| **Terminal / ambient** (Warp lore, Ghostty hooks) | Multiplexer as orchestrator | Watch; Mag already owns CLI host. Steal layout grammar later. |

---

## 2. Steal map (contract → Mag deliverable)

| # | Contract | Best GitHub sources | Mag slot | Priority | Status |
|---|----------|---------------------|----------|----------|--------|
| P1 | **Headless agent + machine events** | OpenHands `--headless --json`; OpenCode CI; OpenHarness | `agent_cli` JSON trail; autorun card event stream | **P0** | open |
| P2 | **Test-gated report-back** | Aider; mini-swe-agent; SWE-agent | `post_run_eval` / pytest after `heavy_code` | **P0** | partial (A6) |
| P3 | **Workspace per seat** | agent-worktree; worktree-pilot; agetor; jj | orchestrator spawn → worktree bind + prune | **P1** | open |
| P4 | **Chat / turn = VCS unit** | Melty (message→commit); Aider auto-commit | desk session → knot leaf / trail core, not chat scroll | **P1** | partial |
| P5 | **Intent / goal approval UI** | OpenCode plan seat; Agetor MCP approvals; Melty | Desk trust ladder: approve goal before promote | **P1** | partial |
| P6 | **ACI / tool surface discipline** | mini-swe-agent bash-only; SWE-agent ACI; MCP SDK | REST + optional `mag/mcp_bridge.py` | **P2** | open (A5) |
| P7 | **Model router / seat economics** | LiteLLM proxy patterns | `route.v2` + provider.yaml — not LiteLLM as brain | **P2** | partial |
| P8 | **CI/CD-shaped ops dashboard** | Agetor; Cline Kanban; RunMaestro; OpenHands Canvas | `agents.html` + autorun status enum | **P1** | partial |
| P9 | **Stacked / change-based VCS** | jj; Sapling stacked diffs | research only until git worktree prune ships | **P3** | watch |
| P10 | **IDE as thin client** | Continue; Cline; OpenCode; Pear submodule | Cursor/VS Code = window; Mag = state server | **P2** | open |

**Explicit non-steals**

- Second orchestrator beside Mag (`route.v2` stays sole brain)
- Agent-to-agent chat as coordination (use pack + trail / Elias rope)
- Full VS Code fork product (Void/Aide/Pear app trees)
- EnIGMA CTF offense stack (steal **interactive tool sessions** shape only)
- Redis/NATS “ACP” unless FILE residual proven insufficient
- Unattended merge / always-approve on host (OpenHands headless = container only)

---

## 3. Repos — clone forest (Wave 1)

Shallow clones via pull script. Large VS Code forks are **Wave 2 / on-demand**.

| id | Upstream | License (check) | Steal focus | Mag slot |
|----|----------|-----------------|-------------|----------|
| **openhands** | [OpenHands/OpenHands](https://github.com/OpenHands/OpenHands) | MIT | Agent Canvas, Agent Server, headless JSONL, automations | P1, P8 |
| **swe-agent** | [SWE-agent/SWE-agent](https://github.com/SWE-agent/SWE-agent) | MIT | ACI, issue→patch→test loop | P2, P6 |
| **aider** | [Aider-AI/aider](https://github.com/Aider-AI/aider) | Apache-2.0 | repomap, lint/test gate, git commit per turn | P2, P4 |
| **jj** | [jj-vcs/jj](https://github.com/jj-vcs/jj) | Apache-2.0 | `jj workspace` multi-checkout; change-based model | P3, P9 |
| **litellm** | [BerriAI/litellm](https://github.com/BerriAI/litellm) | Apache-2.0 | proxy/router, budgets, fallbacks | P7 |
| **mcp-python** | [modelcontextprotocol/python-sdk](https://github.com/modelcontextprotocol/python-sdk) | MIT | tool schema / server patterns | P6 |
| **continue** | [continuedev/continue](https://github.com/continuedev/continue) | Apache-2.0 | IDE→agent client contracts | P10 |
| **melty** | [meltylabs/melty](https://github.com/meltylabs/melty) | check upstream | chat message = git commit | P4, P5 |
| **pearai-sub** | [trypear/pearai-submodule](https://github.com/trypear/pearai-submodule) | check upstream | Continue-fork AI surface (not full app) | P10 |

### Wave 1b — worktree ops / terminal / kanban (added 2026-08-05)

| id | Upstream | License (check) | Steal focus | Mag slot |
|----|----------|-----------------|-------------|----------|
| **mini-swe-agent** | [SWE-agent/mini-swe-agent](https://github.com/SWE-agent/mini-swe-agent) | MIT | ~100-line bash agent; supersedes SWE-agent for default | P2, P6 |
| **opencode** | [anomalyco/opencode](https://github.com/anomalyco/opencode) | MIT | plan vs build seats; subagents; headless CI | P1, P5, P10 |
| **agent-worktree** | [nekocode/agent-worktree](https://github.com/nekocode/agent-worktree) | check | `wt run` create→agent→merge/prune | P3 |
| **worktree-pilot** | [WorktreePilot/worktree-pilot](https://github.com/WorktreePilot/worktree-pilot) | check | ports, logs, safe cleanup per task | P3, P8 |
| **agetor** | [alamops/agetor](https://github.com/alamops/agetor) | check | kanban control plane + MCP approvals | P3, P5, P8 |
| **cline** | [cline/cline](https://github.com/cline/cline) | Apache-2.0 | plan-and-act IDE agent | P5, P10 |
| **cline-kanban** | [cline/kanban](https://github.com/cline/kanban) | check | card=worktree ops UI; auto-commit chains | P3, P8 |
| **openharness** | [mifunedev/openharness](https://github.com/mifunedev/openharness) | check | Docker sandbox + worktrees + cron factory | P1, P3 |
| **runmaestro** | [RunMaestro/Maestro](https://github.com/RunMaestro/Maestro) | check | multi-agent fleet dashboard + worktrees | P3, P8 |

### Wave 1c — SDK harness references (never second orchestrator)

| id | Upstream | License (check) | Steal focus | Mag slot |
|----|----------|-----------------|-------------|----------|
| **google-adk** | [google/adk-python](https://github.com/google/adk-python) | Apache-2.0 | session/status enum, workflow runtime, Task API, A2A | P1, P5 |
| **openai-agents** | [openai/openai-agents-python](https://github.com/openai/openai-agents-python) | MIT | sessions, guardrails, handoffs, tracing | P1, P5, P6 |

### Wave 2 — field-steal on demand (`MAG_AGENT_PLATFORM_WAVE2=1`)

| id | Upstream | Why deferred | Steal if needed |
|----|----------|--------------|-----------------|
| **void** | [voideditor/void](https://github.com/voideditor/void) | Archived; full VS Code fork (huge) | Provider wiring, agent-mode chrome, packaging GA |
| **aide** | [codestoryai/aide](https://github.com/codestoryai/aide) | Archived | LSP-aware proactive agent UX |
| **sidecar** | [codestoryai/sidecar](https://github.com/codestoryai/sidecar) | Companion to Aide | Agentic edit loop / SWE-bench harness bits |
| **pearai-app** | [trypear/pearai-app](https://github.com/trypear/pearai-app) | Full VS Code fork | Prefer submodule only |
| **sapling** | [facebook/sapling](https://github.com/facebook/sapling) | Large; niche ops | Stacked-diff grammar for agent tasks |
| **openhands-sdk** | [OpenHands/software-agent-sdk](https://github.com/OpenHands/software-agent-sdk) | Overlaps main OpenHands tree | Agent Server internals if Canvas too heavy |
| **opentree** | [axelgar/opentree](https://github.com/axelgar/opentree) | tmux-specific | tmux + worktree dashboard grammar |
| **emd-maestro** | [emdgroup/maestro](https://github.com/emdgroup/maestro) | overlaps RunMaestro name | ACP kanban Tauri — compare only |
| **kankanban** | [Knwar/kankanban](https://github.com/Knwar/kankanban) | Claude-Code-specific | MCP board tools + per-card worktrees |

---

## 4. Research direction (what to read in each clone)

Order of attack after `pull_agent_platform_repos`:

### Week A — Platform spine (P1, P2, P8)

```text
1. OpenHands       — headless + --json event schema; Agent Server
2. mini-swe-agent  — bash-only loop (prefer over full SWE-agent)
3. Aider           — lint/test after edit; commit as trail unit
4. Agetor / Cline Kanban — ops dashboard shape (card → worktree → review)
```

**Field-steal targets:**

```cmd
.venv\Scripts\python.exe main.py field-steal --root mine/raw/agent_platform/OpenHands/OpenHands --max-files 40
.venv\Scripts\python.exe main.py field-steal --root mine/raw/agent_platform/SWE-agent/mini-swe-agent --max-files 30
.venv\Scripts\python.exe main.py field-steal --root mine/raw/agent_platform/Aider-AI/aider --max-files 35
.venv\Scripts\python.exe main.py field-steal --root mine/raw/agent_platform/alamops/agetor --max-files 35
.venv\Scripts\python.exe main.py field-steal --root mine/raw/agent_platform/cline/kanban --max-files 30
```

**Compose into Mag:** JSONL event types for autorun card; `post_run_eval` hook; never import their orchestrator.

### Week B — Workspace isolation (P3, P9)

```text
1. agent-worktree — wt run headless lifecycle (create → agent → merge/prune)
2. worktree-pilot — ports + logs + cleanup
3. jj docs: workspace add / forget / update-stale
4. Defer Sapling until git worktree prune is boring and reliable
```

**Acceptance sketch:** one orchestrator task gets a disposable worktree; failed task deletes tree; residual records path + outcome.

### Week C — Tool bus + IDE client (P6, P7, P10)

```text
1. MCP python-sdk — thin wrapper over existing Mag REST (A5)
2. LiteLLM — fallback/budget *ideas* only → provider.yaml
3. Continue / Pear submodule — how IDE clients talk to a state server
```

### Week D — Intent UX archaeology (P4, P5)

```text
1. Melty — message→commit state machine (CHARLIE_README / services)
2. Void / Aide (on-demand) — agent mode chrome; LSP proactive loop
3. Mag Desk — approve *goal*, then show diff; promote stays human
```

---

## 5. Search queries (GitHub + scout)

Use when refreshing beyond the manifest (Monday `github` / Friday harness rotation):

| Intent | Query seeds |
|--------|-------------|
| Headless coding agents | `headless agent JSONL`, `org:OpenHands`, `mini-swe-agent`, `opencode headless` |
| Worktree / parallel seats | `git worktree agent`, `jj workspace`, `wt run`, `agent-worktree`, `WorktreeCreate` |
| Kanban control planes | `agetor`, `cline/kanban`, `maestro worktree`, `kankanban` |
| Test-gated agents | `aider test`, `mini-swe-agent`, `agent only commit if tests pass` |
| MCP bridges | `modelcontextprotocol`, `mcp server coding agent`, `agetor mcp` |
| Ops dashboards | `agent canvas`, `RunMaestro`, `openharness cron`, `diff queue` |
| Avoid | `cursor zero leak`, `agent mesh FAANG` (no artifact); CrewAI as DNA |

Improve kind hint when scout hits a pattern: `agentic_contract` (see landscape §6).

---

## 6. Mag relevance matrix

| Foreign pattern | Steal | Reject |
|-----------------|-------|--------|
| OpenHands headless + JSON events | Event schema + CI-shaped status | Their cloud / always-approve on host |
| OpenHands Agent Server | Multi-seat host behind one API | Replacing Mag router |
| SWE-agent ACI | Constrained tool vocabulary | EnIGMA as product direction |
| Aider lint/test + git | Evaluator seat + trail commits | Aider as default seat |
| Melty chat=commit | Turn → knot / trail unit | Editor fork |
| jj workspaces | Parallel FS views | Forcing operators onto jj |
| LiteLLM | Budget/fallback tables | Proxy as DNA |
| MCP SDK | Mag-as-MCP state server | MCP as identity |
| Continue / Pear sub | Thin IDE client | Second memory store |
| Void / Aide archives | UX archaeology | Shipping a VS Code fork |

---

## 7. Refresh clones

Windows:

```cmd
scripts\pull_agent_platform_repos.cmd
```

Unix:

```bash
./scripts/pull_agent_platform_repos.sh
```

Optional stars (your account):

```cmd
set MAG_GH_STAR=1
scripts\pull_agent_platform_repos.cmd
```

**Mag never auto-clones on orchestrate/Step** — operator or `home_sync` runs pull deliberately.

Inventory probe (after wiring): extend `probe-local` → `agent-platform` (same shape as steal-protocol). Until then:

```cmd
dir mine\raw\agent_platform
```

---

## 8. Linkage

| Doc | Role |
|-----|------|
| `AGENTIC_LANDSCAPE_2026.md` | SDK / harness steal list A1–A12 |
| `AGENT_BLEEDING_EDGE_REPOS_INDEX.md` | Memory / replay / quiet / A2A (B1–B7) |
| `STEAL_PROTOCOL_REPOS_INDEX.md` | Blackboard / cascade forest |
| `MAG_STEAL_AUTOPILOT.md` | Zeitgeist filter + rob list |
| `HANDOFF_MAG_AGENT_TODOS.md` | Operational queue — add P1–P3 when scheduled |
| `configs/improve.yaml` | `agent_platform_repos` local source |

Update this index when a P-row ships — flip Status and note the Mag path.

---

*End agent-platform repos — commitment `agent-platform-repos-001`*
