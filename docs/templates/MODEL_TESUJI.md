# Model tesuji eval (`model_tesuji.v1`)

**Commitment:** `model-tesuji-001`  
**Job:** Read a Hugging Face (or peer) model card **as data**, extract **same / differ / take / leave**, keep only **tesuji** that *simplify and enhance* Mag.  
**Not:** model shopping, auto-pull seats, leaderboard cosplay, “add API because hype.”

**Parents:** `memory/improve/GOAL.md` · `configs/improve.yaml` · `docs/templates/REF_LEAF.md` · **`docs/templates/FEATURE_COMPOSE.md`** (identify→steal→enhance→compose)  
**Output:** `memory/improve/evals/models/{slug}-{YYYY-MM-DD}.md`  
**Gate:** practices may promote; model seats never auto-apply (`max_auto_pull_gb: 0`).  
**After Take:** if ≥2 steals share substrate or cancel failures, fill **Compose** per FEATURE_COMPOSE (greater than sum).

---

## When to run

| Trigger | Action |
|---------|--------|
| Scout surfaces a **named** model (not page chrome) | Open HF card + tech blog; start a leaf |
| Weekly improve review | Finish ≤1 open leaf or reject as noise |
| Operator names a model | Full leaf before any seat talk |

Skip if claim is bare `Model signal: X` with no card read.

---

## Process (order fixed)

### 0. Identity (card face)

| Field | Value |
|-------|-------|
| slug | org/name |
| HF / source URL | |
| release / weight date | |
| license | |
| total params · activated | |
| context | |
| modalities | |
| local_feasible | true / false / cluster-only |
| our baseline compare | e.g. Mag L0 gemma · L2 Grok · remote Claude |

### 1. Data behind it (what we can actually cite)

Fill only from **card, tech report, paper, license, eval footnotes**. Mark unknowns.

| Layer | Evidence | Status |
|-------|----------|--------|
| Pretrain corpus / mix | | known / partial / unknown |
| SFT / agent trajectory data | | |
| RL / preference | | |
| Quantization / training tricks | | |
| Eval harness coupling | which agent harness, effort, fallbacks | |
| Open weights vs open data | | |
| Commercial / geo constraints | | |

**Honesty rule:** If pretrain mix is marketing-only, write **unknown** — do not invent.

### 2. Same as our world

3–7 bullets. Mechanisms that already match Mag / mirror doctrine (even if scale differs).

### 3. Differs

3–7 bullets. Architecture, contract, product, political/economic move. Concrete.

### 4. Tesuji candidates

A **tesuji** here = a small structural move that **reduces moving parts or token waste** while **raising fidelity or long-horizon coherence**.

For each candidate:

| Id | Move (one line) | Simplifies what? | Enhances what? | Cost / risk | Verdict |
|----|-----------------|------------------|----------------|-------------|---------|
| T1 | | | | | take / hold / leave |

**Reject** anything that only adds seats, providers, or size.

### 5. Take (promote-shaped)

Bullets that can become **practices** in `playbook.md` or harness constraints. Must be runnable without the model.

### 6. Leave behind

Explicit reject list so future scouts don’t re-litigate.

### 7. Mag map

| Take item | Lands in | Done when |
|-----------|----------|-----------|
| | e.g. HABIT / residual / dispatch / AGENTS | |

### 8. One line

Single verdict. Prefer: *steal contract X; ignore weights.*

---

## Scoring (for human / brief, not auto-pull)

| Signal | + / − |
|--------|-------|
| Open card with real architecture table | + |
| Footnotes admit harness coupling | + |
| Local-run path ≤ our VRAM budget | + |
| Bare name drop / trending dump | − |
| Only API rent with no transferable contract | − |
| Requires mid-session multi-model thrash | − |

---

## Copy skeleton

```markdown
# {org}/{name} — model tesuji

**Commitment:** `mt-{slug}-001`  
**Date:** YYYY-MM-DD  
**Sources:** HF card · blog · report  
**Baseline:** Mag L0 / L2 / remote knives  
**local_feasible:** …

## 0. Identity
(table)

## 1. Data behind it
(table)

## 2. Same
-

## 3. Differs
-

## 4. Tesuji
(table)

## 5. Take
-

## 6. Leave
-

## 7. Mag map
(table)

## 8. One line
…
```

---

## Relation to improve loop

```
scout (HF signal)
  → if named model + worth time: write evals/models/*.md
  → extract Take as kind=practice candidates (or promote by hand)
  → Leave stays in leaf so reject is cheap next time
  → never auto_apply_model_seats
```

Scout noise stays noise. **The leaf is the product.**

---

## Cross-domain leaves

Not every tesuji is a HuggingFace model card. **Orientation / plain-speech** and other cross-domain contracts use the same skeleton (Identity → Same → Differs → Tesuji → Take → Leave → Mag map → One line) but fill Identity from audience and domain, not params and license.

| Kind | Example | Grove (`memory/improve/…`) | Git-tracked (`docs/ref/tesuji/`) |
|------|---------|----------------------------|----------------------------------|
| orientation / plain-speech | Amish barn-raising Mag explainer | `evals/models/zeitgeist-amish-plain-2026-08-05.md` | [zeitgeist-amish-plain-2026-08-05.md](../ref/tesuji/zeitgeist-amish-plain-2026-08-05.md) |

**Rule:** mirror durable cross-domain tesuji to `docs/ref/tesuji/`; grove copy stays gitignored. See `docs/ref/MAG_STEAL_AUTOPILOT.md` for zeitgeist filter + cross-domain contract theft.
