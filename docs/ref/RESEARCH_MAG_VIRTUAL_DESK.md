# Research proposal — Mag Virtual Desk (autonomous second workstation)

**Commitment:** `research-mag-virtual-desk-001`  
**As-of:** 2026-08-05  
**Audience:** External research agent (Grok, DeepSeek dig, `improve --deep`, human scout)  
**Return to:** Cursor/Mag implementer with filled **§8 deliverable template**  
**Parents:** `HANDOFF_MAG_AGENT_TODOS.md` · `MAG_v2_PLAN.md` · `AGENTIC_LANDSCAPE_2026.md` · `CONTAINER.md`

---

## 0. Activation (paste this to the research agent)

```text
JOB: Deep research for Mag Resource Harness — "virtual desk" pattern.

Read docs/ref/RESEARCH_MAG_VIRTUAL_DESK.md in full (or this paste).

GOAL: Find how production agent systems achieve:
  (A) isolated workstation — Mag works without operator keyboard/display,
  (B) observable output — operator checks a card/brief, not a chat scroll,
  (C) crash containment — one task dies, supervisor survives,
  (D) optional GUI hands — headless browser/desktop inside cage only.

CONSTRAINTS (non-negotiable):
  - Local-first, footprint owner (T0–T3 tiers, residual on disk)
  - One router, one orchestrator — no second DNA store
  - Container cage default (Docker mag-sovereign), not host roam
  - Windows home PC primary; Linux container secondary
  - Steal contracts, not framework cosplay

DELIVER: Complete §8 template. Cite URLs + dates. Flag vaporware.
PRIORITY: P0 questions first. Max 15 pages equivalent.
```

---

## 1. Operator intent (why this research exists)

Nacho wants Mag to feel like it has **its own virtual desktop and keyboard** — plugging away on queued work while the operator codes, browses, or walks away. Not babysitting a chat window.

**Metaphor today (already built, partial):**

| Operator desk | Mag desk |
|---------------|----------|
| Cursor IDE, human keyboard | `queue/todo.md`, governor fill, orchestrator queue |
| `MAG_OPERATOR_ACTIVE=1` | `MAG_DRAINER=1`, autorun loop |
| Edits in repo | Residual: briefs, trail, FKB, verkle leaves |
| Win+Ctrl+D optional second desktop | Docker `mag-sovereign` + orchestrator spawn |

**Gap:** No formal **workstation profile** (headless display, browser cage, VNC/noVNC ritual, Windows virtual-desktop ops doc). No industry steal list specific to "second desk" UX.

This research closes that gap so an implementer can ship **v2.1 Mag Workstation** without re-litigating architecture.

---

## 2. Mag context (minimal — do not re-research v2 plan)

### Stack (frozen assumptions)

```text
LAYMAN   Office :8765 — FIND/FILE/LOAD, autorun card (backend exists)
LATTICE  route.v2 → seats → orchestrator spawn → governor_autorun
FREEDOM  container cage · G1–G4 gates · residual + trail on disk
```

### Existing modules (research should map TO these, not replace)

| Module | Role |
|--------|------|
| `mag/orchestrator.py` | Spawn/kill/reap isolated `main.py agent` children; queue drain |
| `mag/governor_autorun.py` | Intelligent fill → route → execute; respects `MAG_OPERATOR_ACTIVE` |
| `mag/failure_kb.py` | Fail → remedy scoring |
| `watch/cursor_bridge.py` | IDE ↔ REST bridge when operator codes |
| `mag/research_pack.py` | URL → local pack pattern (reference for deliverable shape) |
| `docs/CONTAINER.md` | Docker boundary, cap_drop, localhost ports |

### Operator modes

| Mode | Env | Behavior |
|------|-----|----------|
| Coding | `MAG_OPERATOR_ACTIVE=1` | Autorun paused; Cursor owns edits |
| AFK | `MAG_DRAINER=1`, operator inactive | Fill queue, drain, verkle gaps |
| Manual | `MAG_DRAINER=0` | Operator drives `run` / `ask` / `brief` |

### Gates (never propose bypass)

- **G1** constitution / tiers / residual
- **G2** secrets never echoed
- **G3** irreversible = L3 human only
- **G4** operator active pauses autorun

---

## 3. Research questions (priority order)

### P0 — Must answer (blocks v2.1 spec)

**Q1. Isolation model**  
How do production systems separate **operator input** from **agent input** without a literal second human?  
Look for: job queues, mailboxes, session files, sandbox stdin=DEVNULL, "computer use" APIs that don't hook host keyboard.

**Q2. Supervision pattern**  
What is the industry-standard **parent survives / child dies** shape?  
Map to Mag orchestrator: timeout, heartbeat, stall detection, retry policy, parallel workers.

**Q3. Observable autonomy**  
How do systems show "what the agent did overnight" without chat history?  
Dashboards, run cards, structured artifacts, morning briefs, OpenTelemetry-style traces readable by layman.

**Q4. Container + GUI**  
Minimal pattern for **headless browser or desktop inside Docker only** (not host Chrome):  
xvfb, Playwright in container, noVNC, CDP over localhost, seccomp/cap_drop compatibility.

**Q5. Windows operator ritual**  
Practical **two-desk UX on Windows 11**: Virtual Desktops, which windows go where, Task Scheduler for `MagAutorun`, firewall/localhost binding. No Linux-only hand-waving.

### P1 — Strongly desired (shapes implementation)

**Q6. Computer use / desktop automation**  
Anthropic computer use, OpenAI Operator/CUA, Google Mariner, OpenClaw, Bytebot, etc. — what is **load-bearing** vs demo? Cost, reliability, cage requirements.

**Q7. Evaluator in a cage**  
Planner/generator/evaluator loops where evaluator uses Playwright MCP **inside sandbox** — cite Anthropic harness blog, OpenAI eval patterns.

**Q8. Parallel desk economics**  
When to spawn N orchestrator children vs one long agent — token cost, context bleed, failure blast radius.

**Q9. Pause / steer / continue**  
Live operator intervention without killing worker: mailbox, RPC, file-based knot (Mag has pigeonhole — find 3 analogues).

**Q10. Security anti-patterns**  
Docker socket mount, host `/` bind, "agent uses your real Chrome profile", RDP into host — flag each with severity.

### P2 — Nice to have (future)

**Q11.** macOS parallel (Secondary Spaces) — one paragraph if easy.  
**Q12.** k8s Job vs long-running Deployment for agent workers — when Mag outgrows compose.  
**Q13.** Voice/phone as async input channel (OpenClaw-style) — footprint-owner fit?

---

## 4. Where to look (seed list — expand)

### Frameworks & SDKs

| Source | Hunt for |
|--------|----------|
| OpenAI Agents SDK | Sandboxes, sessions, parallel subagents, computer use |
| Anthropic | Long-running harness, computer use, tool sandbox |
| Google ADK | Code execution environment, session persistence |
| LangGraph / LangSmith | Human-in-the-loop interrupt, checkpointing |
| Microsoft AutoGen / Magentic | Multi-agent isolation |
| CrewAI / Swarm | Anti-patterns (second orchestrator) — what NOT to copy |

### Products (agent workstations)

| Product | Question |
|---------|----------|
| OpenClaw | Local daemon + channels; how isolation works |
| Cursor background agent | What it can/can't touch; cloud vs local |
| Devin / Cognition | Workstation VM model |
| GitHub Copilot Workspace | Artifact handoff vs chat |
| E2B, Daytona, Modal Sandboxes | API-spawned micro-VMs for agents |
| Browserbase, Steel, Anchor | Headless browser as a service vs self-host |
| Windows Sandbox / WSL2 | Footprint-owner cage on Windows host |

### Infra patterns

- Docker + `xvfb-run` + Playwright official image
- noVNC + fluxbox minimal desktop in container
- gVisor / Firecracker / Kata — overkill audit for Mag scale
- systemd user services vs Task Scheduler for drainer
- `MAG_OPERATOR_ACTIVE` analogues in other products

### Academic / engineering posts

- Anthropic "building effective agents" + 2025–2026 harness posts
- OpenAI swarm → agents SDK migration notes
- Berkeley / BAIR agent safety sandbox surveys (2025+)

---

## 5. Evaluation rubric (score each finding 1–5)

| Criterion | 1 (ignore) | 5 (steal) |
|-----------|------------|-----------|
| **Cage fit** | Requires host root / full desktop | Runs in container or micro-VM |
| **Residual fit** | State only in cloud session | Artifacts on disk, replayable |
| **Operator load** | Must watch stream | Card/brief sufficient |
| **Merge cost** | New orchestrator framework | Wires into orchestrator/autorun |
| **Windows viable** | Linux-only | Works on Win11 + Docker Desktop |
| **Tier law** | Sends T3 data to cloud by default | Local-first default, escalate explicit |

**Steal threshold:** average ≥ 3.5 AND cage fit ≥ 4.

---

## 6. Anti-goals (research agent must NOT recommend)

1. Second orchestrator or chat-native DNA store beside residual  
2. Host-native drainer with `run_shell` on full `C:\` (pre-container model)  
3. "Just use cloud agent 24/7" — seat transition ending cloud dependence  
4. Grok/Claude as default overnight drain — token law: Ollama scut, DeepSeek heavy, Grok scarce  
5. VNC exposed on LAN — localhost or SSH tunnel only  
6. Framework rewrite (LangGraph-only Mag, etc.)

---

## 7. Hypotheses to validate or falsify

| ID | Hypothesis | If true → action |
|----|------------|------------------|
| H1 | Win Virtual Desktop + container is enough for v2.1 without xvfb | Ship ops doc only |
| H2 | Playwright-in-container covers 90% of "GUI hands" | `MAG_WORKSTATION=playwright` profile |
| H3 | noVNC adds security surface without operator value | Skip VNC; logs + screenshots only |
| H4 | E2B-style micro-VM is overkill until parallel >5 workers | Defer |
| H5 | Pigeonhole steer ≈ industry "interrupt" pattern | Document as Mag's knot channel |
| H6 | Morning brief + autorun card = sufficient observability | Defer fancy trace UI |

---

## 8. Deliverable template (research agent fills this)

```markdown
# Mag Virtual Desk — Research Report

**Researcher:** <name/seat>
**Date:** <ISO date>
**Commitment:** research-mag-virtual-desk-001-r1

## Executive summary (≤10 bullets)

-

## P0 answers

### Q1 Isolation model
**Answer:**
**Best references:** (url, date)
**Mag mapping:** <module or new file>
**Steal score:** /5

### Q2 Supervision pattern
(repeat)

### Q3 Observable autonomy
(repeat)

### Q4 Container + GUI
(repeat)

### Q5 Windows operator ritual
(repeat)

## P1 answers (Q6–Q10)
<condensed>

## Steal list (ranked)

| Rank | Pattern | Source | Mag implementation sketch | Score |
|------|---------|--------|---------------------------|-------|
| 1 | | | | |

## Reject list (explicit no)

| Pattern | Why rejected |
|---------|--------------|

## Hypothesis results

| ID | Verdict (confirmed/falsified/unclear) | Evidence |
|----|---------------------------------------|----------|

## v2.1 implementation proposal (for implementer)

### Phase A — ops only (no code)
-

### Phase B — minimal code
| File | Change |
|------|--------|

### Phase C — defer
-

## Open questions for Nacho
-

## Bibliography
<urls with access dates>
```

---

## 9. Search queries (copy-paste starters)

```text
"agent sandbox" docker playwright headless 2025 2026
OpenAI agents SDK sandbox parallel subagents
Anthropic computer use sandbox architecture
"long running" agent harness planner evaluator artifact
E2B devbox agent isolation vs docker compose
OpenClaw local agent daemon architecture
Windows 11 virtual desktop automation workflow
noVNC docker security localhost only
xvfb playwright docker official image
agent orchestrator parent child process timeout heartbeat
"operator inactive" agent autonomous queue drain
Modal sandbox serverless agent 2025
browser automation agent container cap_drop
```

---

## 10. How findings return to Mag (workflow)

```text
1. Research agent fills §8 → save as memory/research_packs/mag_virtual_desk/REPORT.md
   OR paste into Grok → export markdown.

2. Operator: mag.cmd research-pack --ask "virtual desk" --url <best primary source>
   (optional enrichment)

3. Feed REPORT.md + this proposal to implementer (Cursor local):
   "Implement Phase A/B from RESEARCH_MAG_VIRTUAL_DESK report r1"

4. Implementer runs ponytail-audit + routing_smoke before merge.

5. Update HANDOFF §10 + MAG_v2_PLAN Phase 3.9 when spec lands.
```

---

## 11. Success criteria (research is "done" when)

- [ ] All P0 questions have answers with ≥2 independent sources each  
- [ ] Steal list has ≥5 items scored with rubric  
- [ ] Reject list has ≥3 items (protects implementer from hype)  
- [ ] v2.1 proposal has Phase A (ops) separable from Phase B (code)  
- [ ] Windows ritual is step-by-step, not conceptual  
- [ ] Container+GUI section names exact image/base (e.g. `mcr.microsoft.com/playwright`)  
- [ ] No recommendation violates G1–G4 or anti-goals §6  

---

## 12. One paragraph for the research agent's system prompt

You are researching **autonomous agent workstations** for a local-first harness called Mag. The operator wants a **second virtual desk**: Mag drains a queue in a Docker cage while the human uses Cursor on another desktop. Your job is not to redesign Mag — it is to find **production-proven patterns** for isolation, supervision, observability, and optional headless GUI — then map them onto existing modules (`orchestrator`, `governor_autorun`, `container`, `cursor_bridge`). Prefer primary sources (SDK docs, engineering blogs, GitHub READMEs) from 2024–2026. Be skeptical of demos. Fill the §8 template completely. Separate **what ships in v2.1** from **what to defer**.

---

*End proposal — hand to research seat; return filled §8 to implementer.*
