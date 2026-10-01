# One-pager: External engine handoff

**Use:** Paste §1 + attach §2 files + one ask.

---

## 1. Paste block (every time)

```markdown
# Mag handoff

**Target:** Mag v4 — substrate on PR #13; spec leads implementation.
**Law:** L1 file → L2 score → L3 promote. Auto-handle = reflexes with trails.
**Four gates:** pattern · eval · join keys · auto|draft|human

**Non-goals:** Auto-promote router/skills · chat-as-memory · raw T0 export · Cursor billing hijack

**Ask:** [ONE specific deliverable]
**Deliverable shape:** [schema | eval JSON | RUN row | mermaid — pick ONE]

**Constraints:**
- Extend mag_training_event.v1 — do not fork schemas
- Mag conductor = mag/conductor.py on THIS repo (not MS Conductor)
- Person memory = L3 promote; engine facts = draft OK
```

---

## 2. File load order

| # | Path |
|---|------|
| 1 | `docs/ref/onepagers/01-v4-north-star.md` (+ topic one-pager) |
| 2 | `docs/ref/MAG_V4_CONDUCTOR_LOOP_DRAFT.md` OR `MAG_LOCAL_STEWARD.md` |
| 3 | `configs/training_patterns.yaml` |
| 4 | `docs/ref/MAG_TRAINING_DATA_SPEC.md` §5–7 |
| 5 | One snapshot: `python main.py loop-audit --json` |

**Do not attach:** full autorun trail, chat history, raw residuals.

---

## 3. Seat routing

| Engine | Feed | Ask for |
|--------|------|---------|
| Grok `[priority]` | north star + full v4 draft | architecture, tradeoffs, RUN sequencing |
| DeepSeek | patterns yaml + one RUN row | schema, code, tests |
| Cursor agent | one RUN row + branch `cursor/v3-swarm-vision-e2ce` | minimal diff |
| Ollama steward | steward one-pager + verkle tip | catalog/digest templates |

---

## 4. Example asks

- Design `task_estimate.v1` fields on `route.v2`  
- Write 10 eval cases as JSON for loop discipline  
- RUN row: pack mode + job-aware skills (files listed)  
- Actor memory JSON schema + amend log only  

---

## 5. One line

> Process before incident · utilize before build · promote before law.
