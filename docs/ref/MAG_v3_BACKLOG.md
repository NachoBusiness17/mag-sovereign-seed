# Mag v3 — Feature backlog & utility ledger

**Commitment:** `mag-v3-backlog-001`  
**As-of:** 2026-08-05  
**Status:** Alpha research — living list, not a promise schedule  
**Parents:** `MAG_v3_RESEARCH_PLAN.md` · `DNA.md` · `CONSTITUTION.md` · `strike_origin.md`

**Job:** Capture v3 possibilities as they appear. Score usefulness vs core purpose. Plan without pretending we're out of alpha.

---

## 0. Core purpose (alignment lens)

Every backlog item is scored against these — not negotiable:

| # | Purpose | Test |
|---|---------|------|
| P1 | **Footprint sovereignty** | Operator owns residual; T0/T1 never remote train-on-input |
| P2 | **Honest files** | Truth on disk; trail > chat; no greenwash |
| P3 | **Fork equality** | Second person can run without your beads or a throne |
| P4 | **Seat economics** | L0 janitor first; frontier scarce; tokens priced |
| P5 | **Human gate on irreversible** | G3 / L3 seal; promote for config changes |
| P6 | **Emergent, not predicted** | Constitution + loops; end state unknown (founding frame) |

**Reject if:** second DNA store · auto weight train in lattice · deception of non-consenting third parties · hiding illegal acts · single cloud oracle dependency without local fork.

---

## 1. How to add an item

Copy this block. ID = `v3-NNN`.

```markdown
### v3-NNN — Title

**One line:**
**Usefulness (1–5):**  **Alignment (1–5):**  **Alpha blocker:** yes|no
**Tier touch:** T0|T1|T2|T3
**Depends:** v2 gate | other v3-IDs
**Loop:** improve | autorun | FKB | resonance | spider | conductor | spore | new

**Intent:**
**Mechanism (sketch):**
**Utility — who benefits, when:**
**Misuse / drift risk:**
**Honest defer reason:**
**Status:** idea | research | spec | blocked | rejected
```

---

## 2. Backlog (newest first)

### v3-013 — Mobile voice client (Android + iOS, Grok-style)

**One line:** Thin handset apps — push-to-talk voice → Mag home router → janitor-first answers for pennies vs voice subscriptions.

**Usefulness:** 5  **Alignment:** 5  **Alpha blocker:** yes

**Tier touch:** T2 transcripts over tunnel; T0/T1 stay home  
**Depends:** v2 gate (#8 router) · Tailscale/tunnel ops · `POST /api/v1/voice/turn`  
**Loop:** conductor + voice_trail + training_events

**Intent:** Replicate Grok/ChatGPT voice **UX** without their subscription economics — phone is mic + speaker; Mag lattice is brain.  
**Spec:** `docs/ref/MAG_MOBILE_VOICE_SPEC.md`  
**Status:** spec

---

### v3-012 — Tesuji Grove (poem skill tree)

**One line:** Browse Mag learnings as a poem-style skill tree — skills, tesuji, remedies, curious errors classified — each node links to real files.

**Usefulness:** 5  **Alignment:** 5  **Alpha blocker:** yes

**Tier touch:** T2 poems may cite public tesuji; T0/T1 sources stay path-only on expand  
**Depends:** v2 gate · FKB · improve evals · grove-build CLI  
**Loop:** improve + FKB + grove

**Intent:** Museum of competence behind the office — not RPG XP.  
**Spec:** `docs/ref/LAYMAN_OFFICE_VISION.md` §4  
**Status:** research (CLI: `main.py grove-build`)

---

### v3-011 — Layman customizable dashboard

**One line:** Plain-office mode + widget layout on disk + themes — your cork board, not fixed expert UI.

**Usefulness:** 5  **Alignment:** 5  **Alpha blocker:** no (partial: plain copy in v2)

**Depends:** dashboard REST · `state/mag_preferences.json`  
**Loop:** operator prefs

**Intent:** Grandma sees "Mag OK / last night / next." Expert panels behind one toggle.  
**Spec:** `docs/ref/LAYMAN_OFFICE_VISION.md` §2–§3  
**Status:** idea

---

### v3-010 — Riddle packs / spore-routed jobs (plausible surface, real soil)

**One line:** Router picks model + API + data tier; ships an encrypted/obfuscated job pack whose public face is a riddle; operator disk holds decode + real goal for later reinterpretation.

**Usefulness (1–5):** 4  **Alignment (1–5):** 3 (high if bounded)  **Alpha blocker:** yes (needs honest router v2 + tier law)

**Tier touch:** T2 public riddle surface · T0/T1 real goal on disk only  
**Depends:** v2 gate (#8 router) · v3-007 conductor · Phase 4 spore spine  
**Loop:** spore + conductor + route.v2

**Intent:**  
Remote seat sees **activation grammar** (riddle, witness, public pack) — not full operator soil. Real issue (code, research, dispute draft) runs inside cage or decodes locally. Later: riddle reinterpreted as case law / spore witness without exposing private residual.

**Mechanism (sketch):**

```text
route.v2(goal)
  -> classify tier + seat + API
  -> spore_pack.build(real_goal, tier_max=T2)
       public_layer: riddle + success_criteria (re-readable later)
       private_layer: encrypted blob / local-only path (operator key)
  -> dispatch to frontier API with public_layer only
  -> residual files decode map + outcome (not ciphertext on X)
```

Aligns with `MAG_v2_PLAN` Phase 4: *"Riddles on X = activation keys, not ciphertext storage."*  
Extends conversation spec: `route --export spore`, obfuscated remote viewport.

**Utility — who benefits, when:**  
Footprint owner sending work through rented APIs without dumping biography. Public witness layer for strike/spore grammar. Reinterpretation = feature (story fidelity), not bug.

**Misuse / drift risk:**  
Plausible deniability used to evade law or harm others → **reject** (violates P1/P2). Becomes theater if riddle has no real decode on disk → chord `metric_theater`. Must not bypass G2 secrets or G3 irreversible.

**Honest defer reason:**  
Needs v2 router truth, container cage, and spore honesty guard (UI never claims story hash = disk tip). Crypto spec + key custody = L3 design.

**Status:** idea → research

---

### v3-009 — L-conductor (trained orchestration expert)

**One line:** Local trained model expert at routing, steering, delegating frontier seats — not mirror, not worker.

**Usefulness:** 5  **Alignment:** 5  **Alpha blocker:** yes

**Tier touch:** T0/T1 train labels local · T2 delegate payloads  
**Depends:** v2 gate · decisions_log case law · v3-004 spider  
**Loop:** conductor

**Intent:** Conductor reads trails; learns orchestration economics; frontier models stay specialists.

**Status:** research (CLI: `main.py conductor`) — see `MAG_v3_RESEARCH_PLAN.md` §0.1

---

### v3-008 — Resonance / corpus lens (auto "find shit like this")

**One line:** Crosswalk soil + frontier + conversation; inject top echoes into context-pack without promote gate.

**Usefulness:** 5  **Alignment:** 5  **Alpha blocker:** yes

**Tier touch:** T2 excerpts in pack · T0/T1 never exported  
**Depends:** v2 context-pack · chord_lens · improve scout  
**Loop:** resonance

**Status:** research (CLI: `main.py resonance`)

---

### v3-007 — Spider (meta-supervisor on agent web)

**One line:** Proactive steer/pause/kill across orchestrator children + chat + autorun.

**Usefulness:** 4  **Alignment:** 5  **Alpha blocker:** yes

**Depends:** v2 orchestrator · pigeonhole · FKB  
**Loop:** spider

**Status:** research (CLI: `main.py spider`)

---

### v3-006 — Virtual desk / Mag Workstation

**One line:** Second desk ops + optional headless GUI cage; Mag plugs away while operator codes.

**Usefulness:** 4  **Alignment:** 4  **Alpha blocker:** no (partial v2.1 ops)

**Depends:** container · autorun · `RESEARCH_MAG_VIRTUAL_DESK.txt`  
**Loop:** autorun + research

**Status:** research (virtual-desk-loop on branch #12)

---

### v3-005 — Bead export + conductor eval set

**One line:** JSONL export for training labels; 10-prompt orchestration benchmark — not mirror eval.

**Usefulness:** 4  **Alignment:** 5  **Alpha blocker:** yes

**Depends:** residual volume · republic repo  
**Loop:** conductor + improve

**Status:** idea

---

### v3-004 — Nested self-improve registry

**One line:** One manifest listing all loops, trails, and promote gates so alpha doesn't sprawl silently.

**Usefulness:** 3  **Alignment:** 5  **Alpha blocker:** no

**Depends:** none  
**Loop:** meta (documents improve, autorun, FKB, verkle, v3 loops)

**Status:** spec (`mag/loops_registry.py` · `main.py v3-status`)

---

### v3-003 — Life-ops spore (agency shape)

**One line:** Notice → draft → L3 seal for bills/disputes/subscriptions — boundary-owned, not root butler.

**Usefulness:** 4  **Alignment:** 4  **Alpha blocker:** yes

**Depends:** G0 spine daily-true · `AGENCY_SHAPE.md`  
**Loop:** spore + L3 gate

**Status:** idea (ORG_ROADMAP G3 — later spore)

---

### v3-002 — Browser evaluator in cage

**One line:** Playwright MCP inside container only; evaluator loop for autorun verify.

**Usefulness:** 3  **Alignment:** 5  **Alpha blocker:** yes

**Depends:** container workstation profile  
**Loop:** autorun + FKB

**Status:** idea (AGENTIC_LANDSCAPE A7 gap)

---

### v3-001 — Cross-operator forest discovery

**One line:** Republic-level discovery without central throne or residual export.

**Usefulness:** 2  **Alignment:** 3  **Alpha blocker:** yes

**Depends:** Phase 5 fork · forest  
**Loop:** spore forest

**Status:** idea (defer)

---

## 3. Utility matrix (quick sort)

| ID | Title | Use | Align | Ship when |
|----|-------|-----|-------|-----------|
| v3-013 | Mobile voice | 5 | 5 | voice/turn API + Expo pilot |
| v3-012 | Tesuji Grove | 5 | 5 | After grove-build |
| v3-011 | Layman dashboard | 5 | 5 | Plain copy now; layout v3 |
| v3-009 | L-conductor | 5 | 5 | After v2 + case law volume |
| v3-008 | Resonance | 5 | 5 | After index + pack wire |
| v3-010 | Riddle packs | 4 | 3* | After router + spore honesty guard |
| v3-007 | Spider | 4 | 5 | After orchestrator stable |
| v3-006 | Virtual desk | 4 | 4 | Ops doc now; GUI later |
| v3-005 | Bead export | 4 | 5 | Before any conductor train |
| v3-003 | Life-ops | 4 | 4 | After daily spine true |
| v3-004 | Loop registry | 3 | 5 | Anytime |
| v3-002 | Browser eval | 3 | 5 | Workstation profile |
| v3-001 | Forest discovery | 2 | 3 | Phase 5+ |

\*Alignment 3 until crypto + misuse guardrails spec'd; becomes 5 with bounded spore law.

---

## 4. Planning rhythm (alpha-appropriate)

| When | Do |
|------|-----|
| Any session | Append backlog item if idea has a one-line + loop tag |
| Weekly | Re-score usefulness/alignment; move status |
| After v2 gate | Pick **one** v3 research thread; no parallel implementation |
| Saturday verkle | Note which backlog items `verkle_gaps` would close |

**Not:** roadmap dates · pretending v3 blocks v2 · building without trail.

---

## 5. Founding frame (why this list exists)

We cannot predict which v3 items compound like case law. We **can** file possibilities honestly, score them against constitution, and let loops + conductor research decide — same as founders with amendable law, not a finished nation design doc.

---

*Append items at section 2. Link from HANDOFF when an item graduates to spec.*

---

## 6. v5 pipe (deferred — do not implement on v3/v4)

| ID | Title | Doc | Status |
|----|-------|-----|--------|
| **v5-GSTD** | GSTD forest — MIT DePIN seat + spore catalog + route map | `docs/ref/MAG_v5_GSTD_FOREST.md` | **piped** — catalog/probe in v4; test/implement v5 |
| **v5-VAST** | Vast.ai training pipeline — rent GPU, LoRA from export, promote weights | `docs/ref/MAG_v5_VAST_TRAINING.md` | **piped** — infer today; train orchestration v5 |
| **v5-XRPL** | XRPL read tools + L3 payment rails via Mag frameworks | `docs/ref/MAG_v5_XRPL.md` | **piped** — spores v4; tools v5 |

Umbrella: `docs/ref/MAG_v5_PIPE.md` · one-pagers 09–12

One-pager: `docs/ref/onepagers/09-gstd-v5-pipe.md`
