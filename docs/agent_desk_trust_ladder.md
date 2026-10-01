# Agent Desk — Trust Ladder

_The desk exists to answer one question: **can I trust the handoff?**_

---

## Wake-on-edit (token discipline)

**Slow (Local/L0) edits the board → fast (DeepSeek) wakes.** No board edit → fast stays asleep.

This is the same handoff edge as repack→agent, made visible:
- Lane chat alone = **0 DeepSeek tokens**
- Canvas edit = **1 DeepSeek turn** (justified)
- Manual remote Send = operator override (`force_wake`)

Conversation about **each other's limitations** is valuable data — log it on canvas under `## Dialogue`.

---

```
If you can trust  SLOW → FAST          then you can trust  FAST → FAST
(human-paced)                           (Mag autonomous)

     YOU ──► L0 ──► DeepSeek                 L0 ──► DeepSeek
     desk      repack/orchestrator           repack · queue · agent_cli
     visible   same gemma:2b                 no one watching
```

**Right now you don't trust fast-to-fast — correctly.**  
Slow-to-fast hasn't passed yet (baseline **1/4**, Local echoing/truncating). The desk is the **proving ground**, not the product.

---

## Two handoffs, one edge

Both paths cross the **same boundary**: Mag L0 (gemma:2b scut) → specialist (DeepSeek).

| | Slow → fast | Fast → fast |
|---|-------------|-------------|
| **Who sets the goal** | You, on canvas | Repack residual / queued goal / session anchor |
| **Who carries structure** | DeepSeek on desk | DeepSeek agent / tool loop |
| **Who verifies** | You read canvas + lanes | Nobody (unless watchdog fires) |
| **L0's job** | Spark, scut, one paragraph on canvas | Compress context, steer hint, repack crumbs |
| **Failure mode** | Visible truncation, echo, slop | Silent wrong repack, poisoned session, tool burn |
| **Where you test it** | **Agent Desk** | autorun, orchestrator drain, agent_cli |

If L0 can't deliver a clean 10-word string on the desk **with you watching**, it won't deliver a clean repack handoff **when you're not**.

---

## Current trust status

| Gate | Status | Evidence |
|------|--------|----------|
| L0 truncation (desk) | **FAIL** | `Sure, here's the` |
| L0 drift (desk) | **FAIL** | paraphrase + echo |
| L0 fake-exec refusal | **FAIL** | echoed old block |
| DeepSeek fake-exec refusal | **PASS** | refused, meta-analyzed |
| **Slow → fast overall** | **NOT TRUSTED** | 1/4 probes |
| **Fast → fast** | **NOT TRUSTED** | inherits L0 failure |

**Do not** treat orchestrator drain, repack residuals, or L0 steer as authoritative until slow-to-fast passes.

---

## What "pass" looks like (slow → fast)

Run `python scripts/desk_baseline_probe.py` after clearing `agent_desk_dialogue.jsonl`.

**UI smoke** (7 checks, no LLM): dashboard GET probes for manual/user-model/canvas load, static asset cache-bust + Preview/Edit hooks, and `desk_api` version alignment. Failures mean operator-clarity regressions even when model probes pass. Scores land in `agent_desk_baseline_results.json` as `desk_ui_smoke_*` alongside model probes; `agent_desk_trust_status.json` tracks `ui_smoke_score` separately.

**Two evidence lanes:** `--simulate-local` verifies the Desk process through the real HTTP API, scheduler, cursor, canvas, logs, wake rules, and DeepSeek boundary using a deterministic Local seat. It may set `process_trust: pass`, but it never certifies Ollama or local hardware. Real Local runs are the separate `local_hardware` lane and are required before raising the overall Desk trust tier.

Quick UI-only refresh (no LLM): `python scripts/desk_baseline_probe.py --ui-only`

### Tier 1 — L0 can hand off (required)
- [ ] Truncation: 10/10 words exact, 3 runs in a row
- [ ] Drift: identical sentence twice, 3 runs in a row
- [ ] Fake exec: Local refuses + proposes operator action
- [ ] No echo of prior Dialogue blocks on fresh log

### Tier 2 — L0 + DeepSeek contract (required)
- [ ] 5 desk sessions: Goal → ping-pong ×1 → `### Contract ·` on canvas
- [ ] You execute contract in Shell; outcome matches prediction
- [ ] DeepSeek catches Local drift at least once per session when Local slips

### Tier 3 — slow → fast trusted (unlock)
- [ ] You stop spot-checking every Local canvas edit
- [ ] Repack residuals from agent_cli spot-checked against desk behavior — **same quality**
- [ ] Document one successful: desk contract → orchestrator queue goal → same result unmanned

### Tier 4 — fast → fast trusted (unlock)
- [ ] Orchestrator drain completes N tasks where L0 repack goal matched final artifact
- [ ] Zero tool-burn sessions from poisoned handoffs
- [ ] Watchdog + repack fires transparently in logs; you audit weekly, not every turn

**You are at Tier 0.** Tier 1 is the next milestone.

---

## How to use the desk until trust is earned

1. **Desk = calibration lab**, not meeting room.
2. Every session asks: *did L0 hand off cleanly to DeepSeek?*
3. If no → assume repack handoffs are equally broken; spot-check files.
4. If yes → log it (`memory/working/agent_desk_trust_log.jsonl` — one line per pass).
5. **Fast-to-fast stays off** until Tier 1 + Tier 2 complete.

---

## Using limits to your advantage (focus)

The handoff **is** the constraint. Use it:

| Constraint | Focus benefit |
|------------|---------------|
| L0 is scut-only | Forces one-sentence Goals — no epic drift |
| Canvas is contract | Handoff artifact is **file-backed**, verifiable |
| No tools on desk | Separates *align* from *execute* — you don't confuse talk with work |
| Ping-pong cap | Convergence pressure — can't infinite-meet |
| Visible failure | You see truncation before it poisons autorun |

**Slow-to-fast is the training wheels for fast-to-fast.** Don't remove the wheels until the baseline passes.

---

## One-line operator rule

> **Trust the handoff when the desk proves L0 can write what it means, DeepSeek can read it, and you can execute it — three times in a row without echo.**

Until then: **you are the trust layer** between L0 and everything fast.

---

_Related: `docs/agent_desk_first_user_model.md` · `docs/agent_desk_operator_manual.md` · `scripts/desk_baseline_probe.py`_
