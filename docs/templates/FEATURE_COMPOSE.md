# Feature compose — identify · evaluate · steal · enhance · compose

**Commitment:** `feature-compose-001`  
**Job:** Turn foreign systems (models, harnesses, products, papers) into **upgrades of Mag’s composed mind** — greater than sum of borrowed parts.  
**Not:** feature checklist cosplay · API accumulation · “and also run their model.”

**Parents:** `memory/improve/GOAL.md` · `docs/DNA.md` · `docs/templates/MODEL_TESUJI.md`  
**Outputs:**
- Feature leaf: `memory/improve/evals/features/{source}-{slug}-{date}.md`
- Or model leaf: `memory/improve/evals/models/…` (same logic, model-shaped card)
- Promoted practices → `playbook.md` only when operator will run them

---

## The capability (what “we want to be able to” means)

| Verb | Meaning here |
|------|----------------|
| **Identify** | Name a **key feature** as a *contract* or *mechanism*, not a brand or bench score |
| **Evaluate** | Same / differ / data honesty / local cost / capture risk |
| **Steal** | Port the **contract** into Mag files/code — without their weights, UI, or throne |
| **Honest origin** | Same day: fill **`STEAL_TESUJI.md`** (like / love / grateful / inside us) — no anonymous ports |
| **Enhance** | Adapt to *our* constraints: local-first, residual DNA, scarce Grok, L3 human |
| **Compose** | Wire steals so they **reinforce each other** — one system, not a junk drawer |

**Greater than sum** only if steals **share substrate** (trail, seats, pack, residual) and **cancel each other’s failure modes**.

---

## Key feature (definition)

A **key feature** is something that, if removed, the foreign system’s long-horizon behavior **collapses or degrades sharply**.

Examples that count:

- Must preserve thinking history across tools  
- One seat per trajectory  
- Cache/prefix economics  
- Quant-aware deploy path  
- Bounded tool surface  

Examples that do **not** count:

- “2.8T parameters”  
- “#3 on leaderboard”  
- “has a chat app”  
- “supports plugins” without a binding contract  

**Test:** Can you state it as an invariant?  
`IF X is violated THEN quality/safety/fidelity fails.`

---

## Pipeline (fixed order)

```
source → identify features → evaluate each → take/leave
              ↓
         steal (port contract)
              ↓
         enhance (fit Mag invariants)
              ↓
         compose (wire + cancel failure modes)
              ↓
         measure (harness-honest eval)
              ↓
         promote practice or reject
```

Never reverse: do not compose first and invent justifications later.

---

## 1. Identify

For each candidate feature:

| Field | Fill |
|-------|------|
| name | short invariant name |
| foreign form | how *they* implement it |
| failure if absent | what breaks |
| evidence | card / paper / footnote / observed behavior |

Max **5** features per source per leaf. Rank by load-bearing weight, not marketing.

---

## 2. Evaluate (per feature)

| Axis | Question |
|------|----------|
| **Same** | Do we already have a weaker form? |
| **Differ** | What’s actually new? |
| **Data** | What evidence backs it? unknown is allowed |
| **Simplify?** | Does stealing *reduce* moving parts or tokens? |
| **Enhance?** | Does it raise fidelity / long-horizon / sovereignty? |
| **Capture?** | Does it pull identity into their seat/API? |
| **local_feasible** | L0 / pack-only remote / cluster-only / never |

**Verdict per feature:** `steal` · `hold` · `leave`

---

## 3. Steal (port, don’t clone)

Steal means a **Mag-native binding**:

| Steal lands in | Example |
|----------------|---------|
| DNA / residual schema | mid-run trail fields |
| Harness / seats | seat purity rule |
| Pack / remote | pack-first only |
| Prompt / HABIT | proactivity dial text |
| Improve / eval | harness footnotes |
| Code path | reject mid-run seat swap |

**Anti-steal:** adding their provider as default · downloading weights · renaming Mag after them.

---

## 4. Enhance (our constraints are the forge)

Every steal must pass through Mag’s forge:

| Constraint | Enhancement rule |
|------------|------------------|
| Local-first | Prefer L0/files; remote is knife |
| Residual cold vertex | Steals strengthen DNA, don’t create second memory throne |
| Token economy | Steals reduce naive Grok dump, not inflate it |
| Bounded agency | Steals *limit* freestyle, not train freestyle |
| Human L3 | Steals preserve promote/stop gates |
| Portable practice | Steals are files you can move house with |

If a steal only works as “rent their agent,” it failed enhance → **leave**.

---

## 5. Compose (greater than sum)

Composition is intentional **interference** of steals:

| Pattern | Meaning |
|---------|---------|
| **Shared substrate** | Two steals write the same trail / residual / pack |
| **Failure cancel** | A’s bug blocked by B’s dial (e.g. long-horizon + proactivity cap) |
| **Amplify** | Trail + seat purity + pack-first → one continuous mind without freestyle capture |
| **Reject stack** | Features that fight Mag invariants never co-promote |

**Greater-than-sum checklist (all true):**

1. ≥2 steals share one substrate  
2. At least one pair cancels a failure mode  
3. No new throne (no second system of record)  
4. Something measurable improved (or a honest fixture now exists)  
5. Token path did not get worse for scut  

If only one isolated practice lands, you have a **patch**, not a composition. Patches are fine — name them honestly.

---

## Compose ledger (lightweight)

When promoting a multi-steal bundle, one line in playbook or leaf:

```text
compose: trail_integrity + seat_purity + proactivity_dial
substrate: residual-warm / run object
cancels: freestyle mid-run amnesia
measure: run fixture F-…
```

---

## Relation to model tesuji

| This doc | Model tesuji |
|----------|----------------|
| Any source (model, harness, paper, product) | HF/model-shaped card |
| Feature-level unit | Model-level unit that *contains* features |
| Compose step explicit | Take list; compose implied |

**Use model tesuji** when the source is a model card.  
**Use this doc** when combining steals across sources or when the unit is a single key feature.

K3 example of compose (already identified):

```text
trail integrity + seat purity + proactivity dial + pack-first
  → continuous long work without freestyle capture or chat amnesia
  > sum of “add memory” + “add agent” + “add cache” as separate toys
```

---

## Skeleton (feature leaf)

```markdown
# {source} / {feature-or-bundle} — feature compose

**Commitment:** `fc-{slug}-001`  
**Date:**  
**Source:**  
**Baseline:** Mag composed mind  

## Identify (≤5)
| name | foreign form | fails if absent | evidence |

## Evaluate
| name | same | differ | simplify | enhance | capture | feasible | verdict |

## Steal map
| name | Mag landing | form (file/rule/code) |

## Enhance notes
- forge constraints applied…

## Compose
- substrate:
- cancels:
- amplify:
- greater-than-sum? yes/no + why

## Leave
-

## Measure
| fixture / smoke | proves |

## One line
…
```

---

## Standing rules

1. **Identify contracts, not brands.**  
2. **Evaluate before steal.** Unknown data stays unknown.  
3. **Steal into Mag; enhance under Mag law.**  
4. **Compose only when steals share substrate or cancel failures.**  
5. **Measure harness-honestly** — multi-smoke alone is not composition proof.  
6. **Never auto-apply model seats** from a compose leaf.

---

## One line

**We grow by forging foreign load-bearing contracts into one residual-first mind — not by stacking products.**
