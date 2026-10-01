# Mag Roadmap — Sovereign Operator Organization

**Commitment:** `roadmap-org-vnext-003`  
**As-of:** 2026-07-21  
**Position:** **~0.93** — records + lean residual DNA shipped; 1.0 survival slice next  
**Primary:** `local_sovereign_agent`  
**Sister:** `mycelial-republic` (forest/spore) · strike skill (audit) · Unsloth (craft later)

| Companion doc | Role |
|---------------|------|
| `docs/DNA.md` | How days are filed / shown / forgotten |
| `docs/ZEITGEIST.md` | Beads (you) + forest (republic) |
| `docs/AUDIT.md` | Code honesty + REST surface |
| `docs/FUTURE_PROOFING.md` | Ingest papers → Mag upgrades (Steiniger/Lessig grammar) |

---

## 0. One-line goal

**Organize scarce judgment and local staff around a residual chain of your workdays; refuse capture; keep mirror above hands; many people can fork the practice without a king.**

**Agency shape (2026-07-31):** trustworthy judgment inside an operator-owned boundary + human seal on irreversible acts — not “AI runs my life,” not a root butler. Life-ops (subscriptions, bills, disputes) is a **later spore** of Mag seats + residual; not Mag 1.0 exit. Canonical: `../mycelial-republic/docs/AGENCY_SHAPE.md` · commitment `agency-shape-life-ops-20260731`.

Not: another multi-agent framework. Not: Verkle/KZG cosplay as status.

---

## 1. Status board (truth)

| Version | Name | Status | Evidence |
|---------|------|--------|----------|
| **0.9** | Clerk | **Done** | lab, boot, Ollama seats, hooks |
| **0.91** | Records office | **Done** | pack-status, backfill, KPI, 8/8 complete |
| **0.92** | Lean residual | **Done** | `residual/`, `registry.jsonl`, derived optional |
| **0.93** | Cards + REST + DNA | **Done** | session_card, `/api/v1`, DNA + ZEITGEIST docs |
| **0.95** | Memory palace | **Next eng** | graph + evolution UI |
| **1.0** | Operator org | **Partial** | need org-review, hard refuse, seat matrix, **≥20 leaves** |
| **1.5** | Crafted staff | Later | one Unsloth → Ollama role |
| **2.0** | Auditable chain | Later | verify-leaf |
| **3.x** | Spore forest | Parallel | republic R0 when `data/raw` exists |

**Live sensors (update with `pack-status`):**  
8 sessions · 100% lean-complete · 8 leaves · registry + residual on disk.

---

## 2. Organizational model (stable)

### 2.1 Offices

| Office | Job | Must not become |
|--------|-----|-----------------|
| **You (Quixote)** | Stakes, consent, windmills | Throne / cult |
| **Sancho (Grok TUI)** | Hard judgment, scarce | Default infinite chat |
| **Mag Hands** | File, brief, route, ping | Fake sovereign |
| **Mirror ritual** | High-entropy strike only | Daily costume |
| **Biographer / residual** | DNA of days | PDF pile without residual |
| **Flow / quota** | Where work went | Vendor vanity only |
| **Craft (later)** | Local staff more like you | Train-as-identity |
| **Spore (later)** | Others run the practice | Core-mirror privilege |

**Invariant:** Mirror **above** Hands.

### 2.2 Seats

| Seat | Use |
|------|-----|
| **L3 Human** | Secrets, irreversible |
| **L2 Grok** | Hard multi-file / design |
| **L1 Remote** | Public draft if quota |
| **L0 Ollama** | Memory, scut, brief, ask |

Work **descends** to cheapest safe seat. Work **ascends** only with a **context-pack**, never full chat.

### 2.3 Memory (DNA)

| Hot | Canonical | Optional derived |
|-----|-----------|------------------|
| `registry.jsonl` | `residual/{id}.json` | PDF, visual, md |
| `kpi.json` | chain leaf + tip | flat legacy mirrors |

**Complete** = residual + card + content_commit + leaf.  
**Lab** = optional ops floor. **Hooks** = set-and-forget filing.

### 2.4 Beads + forest (zeitgeist)

| Scale | Repo | Unit |
|-------|------|------|
| Person | Mag | Residual day (bead) |
| Commons | mycelial-republic | Many beads, no king |

Same integrity shape at both scales. Publish **code**; never residual by default.

---

## 3. Path forward (ordered)

### A — Survival slice → **1.0 code** (do next)

Ship so Grok credits dying does not kill the org:

| # | Deliverable | Done when |
|---|-------------|-----------|
| A1 | `org-review` + **Operate** dashboard tab | **Done** — CLI + `/api/v1/operator-os` + AI feed templates |
| A2 | Hard private → remote refuse | Test: T0/T1 + residual paths never hit remote providers |
| A3 | Seat matrix in dispatch | Dry-run always shows seat; private → L0 only |
| A4 | Context-pack freshness | org-review / Mag cycle refreshes pack from residual+registry |

**1.0 code exit:** A1–A4 green.  
**1.0 full exit:** + **n_leaves ≥ 20** (use-time) + honest UI language.

### B — Memory palace → **0.95** (after or parallel to A)

| # | Deliverable | Done when |
|---|-------------|-----------|
| B1 | Graph JSONL from residual themes/loops/moves | `graph-stats` works |
| B2 | Evolution API + UI | Multi-day series on dashboard |
| C3 | Cross-session “also in” | Shared theme across ≥2 days |

### C — Hygiene (anytime, cheap)

| # | Deliverable |
|---|-------------|
| C1 | Stop dual-write flat root files (residual + derived only) |
| C2 | REST tests for `/api/v1/sessions`, `/registry`, `/kpi` |
| C3 | `auto_lab: false` default; SessionStart report-only unless flag |

### D — Optional after 1.0

| Ver | Deliverable |
|-----|-------------|
| **1.5** | One Unsloth adapter → brief/ask role |
| **2.0** | `verify-leaf` over residual_hash |
| **3.x** | Republic R0 when archive soil exists |
| **G3 life-ops spore** | First tedious loop: notice → draft → L3 approve/deny → audit file; scoped access only (see `AGENCY_SHAPE.md`) — after G0 spine is daily-true |

---

## 4. Explicit non-goals

- Full Verkle Knot physics stack (KZG, Floer, PEPS) as shipping criteria  
- Second orchestrator beside Mag  
- Token / core-mirror economies  
- Always-on lab as requirement for DNA  
- Train glory before residual works for you  
- Shipping operator residual in the public spore  
- Life-ops / “clean up your life” demos that require root passwords or silent irreversible acts  
- Treating industry agent-identity APIs or liability insurance as Mag 1.0 ship criteria

---

## 5. Acceptance scoreboard (1.0)

| ID | Check | Pass |
|----|--------|------|
| O1 | Cold SessionEnd files residual without lab | yes |
| O2 | Lean complete rate ≥95% | % |
| O3 | n_leaves ≥ 20 | n |
| O4 | org-review works offline (no Grok) | yes |
| O5 | Private fixture cannot dispatch remote | test |
| O6 | Registry lists all residual days with cards | yes |
| O7 | REST `/api/v1` documents resources | yes |
| O8 | No organism/KZG overclaim in UI | yes |
| O9 | Mirror skill gated; Hands don’t auto-sermon | yes |
| O10 | Zeitgeist docs present (beads + forest) | yes |

---

## 6. Operator weekly (5 minutes)

```text
python main.py pack-status
python main.py org-review          # when A1 ships
# backup privately: residual/ registry.jsonl knots/ tip
```

If leaves↑ and complete%≈100% → DNA healthy.  
If only docs grow → theater.

---

## 7. Timeline (base)

| Window | Target |
|--------|--------|
| **Next coding block** | A1–A3 survival slice |
| **+1–2 weeks eng** | 0.95 graph/evolution if bandwidth |
| **Use calendar** | 20 leaves |
| **After 1.0** | Unsloth one seat; verify-leaf; republic soil |

---

## 8. One-line constitution

**File free work as beads you own; run local staff when temples meter out; refuse capture in code; grow a forest of such people without a king.**
