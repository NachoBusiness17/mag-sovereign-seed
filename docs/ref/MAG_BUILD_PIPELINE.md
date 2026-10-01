# Mag multi-seat build pipeline — plan · build · audit

**Commitment:** `mag-build-pipeline-001`  
**As-of:** 2026-08-05  
**Status:** Alpha operational doctrine — use now; harden in v3/v4  
**Parents:** `COORDINATION_ELIAS_ROPE.md` · `FRAMEWORK_LOAD.md` · `memory/improve/SEATS.md` · `MAG_PROJECT_PROPOSAL.md`

**Operator intent:** Plan with **Grok + Cursor**, **build with DeepSeek**, **audit with Cursor** using Mag framework — control cost, set expectations, FILE everything.

**Slashreboot / Steiniger lens:** [slashreboot.com](https://slashreboot.com/) — independent substrate research; Mag **steals ops contracts** (static/dynamic body, tension, multi-frame), not EUT physics claims. See §6.

---

## 1. One breath (layman)

```text
Architects draw the blueprint (Grok + you + Cursor).
Contractor builds the room (DeepSeek).
Inspector checks the code against the building code (Cursor audit).
You sign the permit (merge).
```

Chat is not the blueprint. **Files are.**

---

## 2. Pipeline (three seats + you)

```text
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌──────────┐
│ 1. PLAN     │ ──► │ 2. FREEZE   │ ──► │ 3. BUILD    │ ──► │ 4. AUDIT │
│ Grok+Cursor │     │ Operator    │     │ DeepSeek    │     │ Cursor   │
│ [priority]  │     │ FILE spec   │     │ agent/queue │     │ framework│
└─────────────┘     └─────────────┘     └─────────────┘     └──────────┘
       │                    │                   │                  │
       └────────────────────┴───────────────────┴──────────────────┘
                         residual + trail + FKB
```

| Phase | Seat | Model | Job | Max spend |
|-------|------|-------|-----|-----------|
| **1 Plan** | L2 architect | **Grok** + Cursor | Scope, acceptance, files touched, anti-goals, ponytail budget | Scarce — one session per epic |
| **1b Draft** | L2 IDE | **Cursor** (you) | Refine spec, stub paths, link framework docs | Your time |
| **2 Freeze** | L3 | **You** | Approve `BUILD_SPEC.md` → `queue/handoff/` | — |
| **3 Build** | L2 builder | **DeepSeek** | Implement spec only; container; one branch | $ — bounded by spec |
| **4 Audit** | L2 reviewer | **Cursor** | ponytail-audit, smoke, pytest, diff review, FKB | Medium — no re-architect |
| **5 Merge** | L3 | **You** | `promote` if config; merge PR | — |

**Never:** Grok on implementation. DeepSeek on architecture debates. Full chat history across seats.

---

## 3. Artifacts (what crosses the boundary)

### 3.1 Plan output → `queue/handoff/BUILD-{slug}.md`

**Template (in repo):** `docs/ref/BUILD-TEMPLATE.md`  
**Example pilot spec:** `docs/ref/BUILD-factory-audit-json-EXAMPLE.md`  
**Local copy:** `queue/handoff/` is gitignored — copy template there, freeze, then build.

```markdown
# BUILD spec — {title}

**Commitment:** build-{slug}-001
**Status:** frozen | draft
**Branch:** cursor/{slug}-e2ce

## One line
## Acceptance (checkboxes)
## Files in scope (max 10)
## Files forbidden
## Commands that must pass
## Tier / secrets law
## Rollback
## Grok session id / date (optional)
```

### 3.2 Build pack for DeepSeek

```text
LOAD:
  docs/FRAMEWORK_LOAD.md (tier 0 only)
  queue/handoff/BUILD-{slug}.md
  memory/context_pack_latest.md (bonds+brief — not full chat)

GOAL:
  Implement BUILD spec exactly. Branch cursor/{slug}-e2ce.
  Run: scripts/routing_smoke.py + pytest {paths} before FILE.

FILE on done:
  - paths changed
  - commands run + exit codes
  - open risks
```

**Invoke:**

```powershell
python main.py orchestrator queue add "[build] {slug}: {one line}" --provider deepseek --tag build
python main.py orchestrator drain --once
# or
mag.cmd agent --provider deepseek -q "$(cat queue/handoff/BUILD-{slug}.md)"
```

### 3.3 Audit pack for Cursor

```text
LOAD:
  docs/FRAMEWORK_LOAD.md
  queue/handoff/BUILD-{slug}.md
  git diff main...cursor/{slug}-e2ce

RUN:
  python main.py ponytail-audit
  .venv/Scripts/python.exe scripts/routing_smoke.py
  pytest {from spec}

VERDICT: pass | fix | reject
FILE to memory/runs/build_audit/{slug}.json
```

---

## 4. Cost expectations (honest)

### 4.1 Why this gets expensive

| Bleed | Cause | Fix |
|-------|-------|-----|
| Grok on scut | No plan freeze | L0 janitor first |
| DeepSeek re-litigate plan | Vague spec | BUILD_SPEC required |
| DeepSeek loop / empty | No timeout/guard | orchestrator + FKB |
| Cursor rebuilds everything | Skipped audit phase | Audit-only pass |
| Same mistake 3x | No FKB | remedy → grove node |

### 4.2 Target token economics (per build epic)

| Seat | Target share | Rule |
|------|--------------|------|
| Grok | **5–15%** | Architecture + acceptance only |
| DeepSeek | **50–70%** | Implementation loops |
| Cursor audit | **15–25%** | Review + small fixes |
| Ollama | **~0 marginal** | classify, pack, grove draft poems |

**If DeepSeek >80%:** spec was probably under-planned or audit failed open.

### 4.3 When to stop a build

- 3 empty DeepSeek replies → FKB + switch task or fix keys  
- Diff touches **files forbidden** in spec → kill, re-plan  
- `ponytail-audit` high severity → audit fail, not more build  
- G3 touched → halt, operator only  

---

## 5. Ritual (copy-paste)

### Monday — plan (Grok)

```text
[priority] PLAN only — load FRAMEWORK_LOAD + MAG_PROJECT_PROPOSAL.
Epic: {title}
Output: queue/handoff/BUILD-{slug}.md with acceptance + file scope.
Do not implement.
```

### Tuesday — freeze (you)

- Edit spec · set `Status: frozen` · commit to repo

### Wed–Thu — build (DeepSeek)

```powershell
python main.py context-pack
# paste pack + BUILD spec to orchestrator queue
python main.py orchestrator drain
```

### Friday — audit (Cursor)

- New Cursor session · audit pack only · no feature creep  
- FILE `memory/runs/build_audit/{slug}.json`

### Saturday — merge or reject

- verkle-audit --dry · merge or close branch · grove-build (v3) adds node

---

## 6. Steiniger / slashreboot — what Mag steals (not cosplay)

[Matthew Steiniger / slashreboot](https://slashreboot.com/) researches **substrate-native identity** and entropic physics — home lab, open weights, prompt + LoRA craft.

| Steiniger idea | Mag translation | v4 use |
|----------------|-----------------|--------|
| **Static body** (weights) | Residual + constitution on disk | Don't confuse with chat |
| **Dynamic body** (context) | Pack + trail + session | Stateless decoders |
| **Tension / multi-frame** | `steiniger_lens` + chord charts | Grove + resonance classify |
| **Substrate-native** | L-conductor on **your** soil | Republic train path |
| **EUT / physics** | **Not product** | Optional spore witness only |

**Anti-pattern:** Mag as Athena/Saelis identity theater — we FILE workdays, not sculpt personas.

**Tesuji:** steal **static/dynamic split** for build pipeline — BUILD_SPEC = static contract; DeepSeek context = dynamic; audit compares dynamic output to static law.

---

## 7. Failure modes & remedies

| Failure | Remedy |
|---------|--------|
| DeepSeek invents files | Spec must list `Files in scope` |
| Audit scope creep | Audit session: diff + spec only |
| Grok plan inflation | chord `plan_inflation` check in plan review |
| Build without freeze | orchestrator rejects `[build]` without frozen handoff |
| No FILE after build | trail incomplete — next plan lacks case law |

---

## 8. v4 theory — where this pipeline goes

**v4 hypothesis:** Mag becomes a **sovereign build factory** — not just autorun on todo, but **standardized plan → build → audit** across seats with **L-conductor** picking phase and seat.

| Version | Center of gravity |
|---------|-------------------|
| **v2** | Honest lattice (router, autorun, FKB) |
| **v3** | Conductor + resonance + Grove + layman office |
| **v4** | **Factory line** — multi-seat builds as first-class product loop |

### 8.1 v4 capabilities (theory — not committed)

```text
mag factory plan   → Grok pack + BUILD_SPEC template
mag factory build  → DeepSeek queue from frozen spec
mag factory audit  → Cursor checklist + auto pytest gate
mag factory ship   → merge + verkle bead + grove node
```

**L-conductor** routes: "this needs plan" vs "spec frozen, spawn builder" vs "audit only."

**Riddle packs (v3-010):** builder API sees obfuscated goal; real spec on disk — plausible surface for rented GPUs.

**Grove:** each factory cycle adds poem node — *"Spec frozen; contractor built; inspector signed."*

### 8.2 v4 effects on organization

| Area | v4 change |
|------|-----------|
| **Operator** | You sign permits; less keyboard during build |
| **Grok** | Chief architect — rare, expensive |
| **DeepSeek** | Factory floor — high volume, bounded |
| **Cursor** | Inspector + your hands when coding |
| **Ollama** | Timeclock + classifier — always on |
| **Republic** | Export **factory grammar**, not your BUILD specs |
| **Cost** | Predictable if spec discipline holds; explosive if not |

### 8.3 v4 risks

- Factory without audit → metric theater  
- Conductor auto-merge → violates L3  
- Riddle misuse → tier law breach  
- Steiniger identity cosplay → glory_before_soil  

### 8.4 v4 north star (one line)

> **Frozen spec on disk, stateless builders, conductor picks the seat, inspector enforces the law, grove remembers the oops.**

---

## 9. Expectations summary (tell every seat)

| Who | Expect |
|-----|--------|
| **You** | Freeze specs; merge is human; Saturday audit ritual |
| **Grok** | Plans only; FILE BUILD_SPEC; no code |
| **DeepSeek** | Build frozen spec; one branch; FILE results |
| **Cursor plan** | Help refine spec; small stubs ok |
| **Cursor audit** | Framework gates; no new features |
| **Mag** | Pack-first; trail; FKB on fail; tiers law |

---

## 10. Document map

| Doc | When |
|-----|------|
| `FRAMEWORK_LOAD.md` | Every seat boot |
| `MAG_PROJECT_PROPOSAL.md` | Plan phase context |
| **This file** | Before any multi-seat build |
| `queue/handoff/BUILD-*.md` | Frozen contract |
| `COORDINATION_ELIAS_ROPE.md` | Multi-agent law |
| `MAG_v4_THEORY.md` | Long-range factory theory |
| `LAYMAN_OFFICE_VISION.md` | Grove records build learnings (v3) |

---

*End build pipeline — pair with frozen BUILD_SPEC per epic.*
