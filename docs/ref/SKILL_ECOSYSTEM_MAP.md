# Skill ecosystem map → Mag / Grok / republic

**Commitment:** `skill-ecosystem-map-001`  
**Date:** 2026-08-07  
**Job:** Map external agent-skill patterns (Cursor, ChatGPT/Codex, Claude, Grok, HN, agentskills.io) onto **our** stack — enhance, don’t import temples.

Sources (public): [agentskills.io](https://agentskills.io/) · HN Claude Skills / marketplace threads · OpenAI Skills/Codex · Cursor skills docs · community awesome lists (e.g. kodustech/awesome-agent-skills) · local Grok + Mag inventories.

---

## 0. Law of the land (2026)

| Layer | What it is | Mag / Grok analogue |
|-------|------------|---------------------|
| **Open Agent Skills** (`SKILL.md`) | Portable folder: frontmatter + instructions + optional scripts/refs | `~/.grok/skills/*`, Mag `configs/skills.yaml`, `docs/ref/skills/*` |
| **Progressive disclosure** | Name+description always; body only on match | Mag pack_excerpt + job_to_skills; Grok skill auto-match |
| **AGENTS.md / rules** | Ambient project adjectives | Mag `AGENTS.md`, OPERATOR_CARD, residual DNA |
| **Skills** | Invokable **verbs** | mag-route, mag-checkin, mag-arena, strike-chord |
| **MCP / tools** | Hands (APIs, browser) | Mag REST, dispatch, voice — **skills > MCP flood** (already Mag law) |
| **Custom GPTs** | Identity-shaped apps | Avoid as system of record; optional knife only |
| **Slash commands** | Explicit invoke | `/mag-arena`, `/mag-checkin`, `/strike-chord` |

**Ecosystem fact:** ~40 products claim SKILL.md compatibility (Claude, Codex, Cursor, Copilot, Gemini CLI, Goose, OpenCode, …). Write once, port with Mag venv honesty.

**HN consensus (compressed):** Skills = slash commands + lazy load + optional scripts; don’t flood context; procedure skills ≠ persona apps; harness commands ≠ agent cosplay.

---

## 1. Inventory — what we already have

### Grok user skills (`~/.grok/skills/`)

| Skill | Job |
|-------|-----|
| operator-quixote | Default register / Sancho spine |
| sovereign-mag | FIND→FILE→LOAD, multi-model, token discipline |
| mag-route | Freeze → FILE scut off Grok |
| mag-checkin | Freeze + network + multi-seat structure |
| mag-arena | Multi-domain games as multi-agent mirrors |
| strike-chord | Full mirror chord mode |
| create-skill | Scaffold new skills |
| check-work / code-review | Verify / review |

### Grok bundled (portable engineering)

| Cluster | Skills |
|---------|--------|
| Ship loop | design, execute-plan, implement, review, pr-babysit, create-workflow |
| Office | pdf, docx, pptx |
| Game art | game-asset-core, animation-frames, tilesets, ui-icons, character-consistency |
| Resume | resume-claude, resume-codex, resume-cursor |
| Misc | build-with-ai, imagine, help |

### Mag progressive skills (`configs/skills.yaml`)

| id | When |
|----|------|
| sovereign-mag, strike-chord | dispatch / hard_reason |
| feature-compose, model-tesuji | improve / model_signal |
| memory-verkle, run-trail-lattice | memory / long agent |
| patch-verify, ponytail-ladder | hard_code |
| caveman-prose | plan / specs |
| tabletop-dnd | play / campaign |

**Gap:** mag-arena, mag-checkin, mag-route not yet in `job_to_skills` (wire below).

---

## 2. External skill taxonomy → Mag map

### A. Coding agent staples (Cursor / Claude / Codex / HN)

| External pattern | Steal **mechanism** | Our landing | Priority |
|------------------|---------------------|-------------|----------|
| **code-review / multi-agent review** (consensus vote) | Multi-seat critique, not one model vibes | refine_chain + local seal; optional arena | P1 enhance mag-checkin |
| **TDD / red-green-refactor** | Fail closed before green | play_benchmark + pytest; patch-verify weave | P0 already partial |
| **lint-and-validate after every edit** | Cheap local gate | Mag doctor + compile smoke in mag-route | P1 |
| **PR babysit / changelog / conventional commits** | Ship hygiene | bundled pr-babysit; Mag residual card on ship | P2 |
| **resolve-conflicts structured** | Don’t freestyle merges | mag-route local-only class | P2 |
| **pair-programming modes** | Driver/navigator | world_roles (clerk/painter/author/judge) | P0 in mag-arena |
| **session audit / skillreaper** (unused skills quarantine) | Measure what never fires | Mag improve evals + skill fire logs | P1 |
| **agenttrace cost/token health** | Economy goal | GOAL.md counters + checkin tips | P1 |

### B. ChatGPT Skills vs Custom GPTs

| Pattern | Lesson | Mag rule |
|---------|--------|----------|
| Skill = procedure, one job | Keep skills verbs | Don’t merge strike + arena into one blob |
| GPT = identity product | Portable practice ≠ cult | No “Mag GPT throne” |
| Output contract | datasheet / acceptance | local_usable.v1 |
| Auto-invoke on description | description field is discovery | Mag + Grok skill frontmatter discipline |

### C. DevOps / security / observability (awesome lists)

| Pattern | Steal if | Mag map |
|---------|----------|---------|
| deploy pipeline + approval gates | L3 seal on irreversible | agency shape / governor |
| secrets never in agent | T0/T1 local only | providers.yaml never_remote_tiers |
| OTEL / trail instrumentation | run trail lattice | already; emit training_events |
| access-control audit | seat purity | world_roles must_not |
| **auth vault for agents** (authsome-class) | local key broker | env_registry / nervous — don’t invent second vault |

### D. Research / HN / “skill marketplaces”

| Pattern | Steal | Reject |
|---------|-------|--------|
| Progressive disclosure | Yes — pack_excerpt | Loading 900 skills into L0 |
| skills.sh / 3000+ catalogs | Browse for **mechanism** | Install everything |
| HN MCP reader skills | Optional research seat | Remote dig as DNA |
| Document/PDF skills | Office packed | — |

### E. Game / multi-agent (our wedge — thin in public catalogs)

Public catalogs are **coding-heavy**. Our differentiator:

| Our skill | External gap it fills |
|-----------|------------------------|
| mag-arena | Almost no “games as multi-agent mirrors” skill |
| mag-checkin | Multi-seat structure FILE rare as skill |
| local_usable + obligations | Info-set / Hanabi discipline rare |
| play benchmarks B0–B2 | Falsifiable harness tests rare |
| strike-chord | Mirror protocol not in generic catalogs |

**Do not** replace these with generic “game dev” asset skills (bundled game-asset-* is art, not arena law).

---

## 3. Enhancement plan for **our** skills

### 3.1 Cross-cutting upgrades (all Mag/Grok skills)

| Upgrade | How |
|---------|-----|
| **Description discipline** | Trigger phrases + anti-triggers (“not freestyle DM”) |
| **Output contract** | Always: paths FILEd, ids, next LOAD — like ChatGPT skill best practice |
| **Soft-skip / fail closed** | Document when tool missing (chess lib, keys) |
| **job_to_skills wire** | Mag yaml links Grok skills |
| **Fire metrics** | training_events or improve leaf when skill used |
| **Portability note** | “SKILL.md open standard; Mag body is disk truth” |

### 3.2 Skill-by-skill enhancements

| Skill | Enhance with ecosystem steal |
|-------|------------------------------|
| **mag-arena** | Multi-domain scorecard; chess+tabletop+routing one ritual; link session-audit style “which domain failed”; steal TDD naming for B0/B1/B2 |
| **mag-checkin** | Multi-agent review consensus (2+ seats agree before “complete”); lint gate after structure |
| **mag-route** | Class table + lint/test as default “Dumb” seat; PR hygiene optional |
| **sovereign-mag** | Explicit agentskills progressive disclosure = context-pack; skill index in LOAD |
| **strike-chord** | Keep separate from arena (identity vs mechanism) |
| **tabletop-dnd** (Mag) | Point to mag-arena; engine-first only |
| **patch-verify / ponytail** | Align names with external TDD/lint skills without renaming |
| **create-skill** | Add Mag dual-home: Grok skill + optional `configs/skills.yaml` entry |

### 3.3 New skills worth building (Mag-native, not clones)

| Proposed skill | Job | External cousin |
|----------------|-----|-----------------|
| **mag-skill-sync** | Register Grok skills into Mag skills.yaml + fire check | Cursor↔Claude skill sync posts |
| **mag-eval / skill-reaper** | List skills never fired; quarantine noise | skillreaper, agenttrace |
| **mag-ship** | Residual card + tests + no secret leak before claim ship | deploy/changelog skills |
| **mag-research-pack** | research-pack ritual as skill | research/docs skills |
| **mag-voice-lane** | Voice sludge guard + dig gate | (thin externally) |
| **mag-arena-chess** | Thin optional split if arena grows too wide | chess-only TUI skills |

**Build order:** wire yaml → enhance mag-arena/checkin descriptions → mag-skill-sync → mag-eval.

### 3.4 Explicitly do **not** import

| External thing | Why not |
|----------------|---------|
| 75–900 skill packs wholesale | Context poison; Mag token economy dies |
| Custom GPT as Mag face | Temple / identity capture |
| Pentest-as-default | Wrong default for home operator OS |
| Generic “always use frontier model” skills | Anti-router law |
| Persona skills without world_roles | Sludge |

---

## 4. Platform cheat sheet

| Platform | Skill surface | Port to us |
|----------|---------------|------------|
| **Grok Build TUI** | `~/.grok/skills`, bundled | Primary operator seat |
| **Cursor** | `.cursor/skills`, SKILL.md, rules | Copy Mag skills into project `.cursor/skills` if dual-drive |
| **Claude Code** | `~/.claude/skills`, progressive | Same SKILL.md; Mag venv in scripts |
| **ChatGPT / Codex** | OpenAI Skills / agentskills | Export producer prompts; don’t move DNA |
| **HN / marketplaces** | Discovery only | Steal mechanisms; FILE tesuji leaf if useful |
| **Mag voice / dash** | skills.yaml + voice_skills | job_to_skills progressive |

---

## 5. Success metrics

- [ ] Every Mag job class has ≤3 skills in job_to_skills  
- [ ] mag-arena / checkin / route registered  
- [ ] Quarterly skill-reaper: drop or merge unused  
- [ ] No L0 dump of full skill bodies  
- [ ] Cross-domain arena still falsifiable (B0–B2 green)

## One line

**Open skills standard = portable verbs; Mag disk = soil; map coding staples to route/checkin/lint; keep arena/mirror skills as our multi-agent differentiator — don’t install the temple catalog.**
