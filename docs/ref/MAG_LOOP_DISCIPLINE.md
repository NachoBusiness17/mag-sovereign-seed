# Mag — Loop discipline (learn from 100+ step runs)

**As-of:** 2026-08-05  
**CLI:** `python main.py loop-audit`  
**Parents:** `MAG_BEHAVIORAL_COMPOUNDING.md` · `verkle_audit` · `governor_autorun`  
**v4 planning:** `docs/ref/MAG_V4_CONDUCTOR_LOOP_DRAFT.md` · `configs/training_patterns.yaml` (draft)

---

## What “100+ Mag steps” usually means

It is rarely one brilliant agent grinding through 100 tool calls. In practice it is three stacked wastes:

| Pattern | What you see | Root cause |
|---------|--------------|------------|
| **Plan theater** | Autorun trail grows 1000+ rows; same goals re-planned every 5s | Drainer ticks while queue stuck / operator pause; full route logged each tick |
| **Verkle fan-out** | Many `[verkle] summarize-session …` queue rows | One orphan residual → one scut job; detail string varies → dedupe miss |
| **Agent churn** | One session, dozens of non-identical tool calls | No round ceiling (by design); collapse detector only stops *identical* 5× repeats |

**Meta-lesson (already in behavioral compounding):** file episodes, dedupe goals, batch cold-path work, one outcome per leaf.

---

## What Verkle steps teach us

Verkle is **cold filing**, not hot coding. When it shows up as 100+ “steps”:

1. **Integrity gaps are batch jobs** — `backfill-sessions --all` beats N summarize-session spawns.
2. **Gaps ≠ immediate queue** — info-severity (n_leaves metric) should not enqueue; warn/error only (already in `fill_queue`).
3. **Session-scoped goals** — normalize to `[verkle] summarize-session {sid}` so dedupe works across wording changes.
4. **Loops audited in chord** — `chord_lens.detect_loops` flags *plan inflation*, *metric theater*, *scope creep* in transcript text; use that at session end, not as autorun fuel.

---

## Revised approach (operator + harness)

### Operator habits

```text
python main.py loop-audit              # before blaming the model
python main.py loop-audit --json       # for dashboard / improve scout
mag_kill.cmd                           # stop plan theater when debugging
cursor_bridge task "…" --mode queue    # one goal, one leaf — not REPL wandering
```

Clear stale `[test]` queue rows left from smoke tests. They dominate replan counts.

### Harness rules (shipped / tightening)

| Rule | Mechanism |
|------|-----------|
| Same goal once in queue | `orchestrator.enqueue` normalized dedupe |
| Verkle goals stable | `verkle_gap_goal()` in fill + fingerprint |
| No fat plan in trail | `_trail_autorun_once()` — fp + counts, not full routes |
| Plan log only on change | `plan_pending()` fingerprint gate |
| Spider surfaces theater | `plan_theater` / `idle_autorun` signals |
| Agent identical-loop stop | collapse detector → escalate (`decision_framework`) |
| Hot repeat block | FKB ≥8 → `fkb_block_for_goal` |

### Still manual (v4)

- **Outcome gate:** did the leaf land on disk? (knot, test pass, PR) — not “agent said done.”
- **Phase gate:** plan depth → Grok TUI, not another queued scut (`route_task` refuses overview/plan).
- **Batch verkle:** weekly `verkle-audit --full`, not continuous gap drip.

---

## When 100 tool rounds is legitimate

Heavy refactor with varied reads/edits can exceed 50 rounds without being a “loop.” Signals of *dumb* loops:

- Same tool + same args repeatedly (collapse detector)
- Autorun replanning without drain starts (`loop-audit` plan_theater)
- Verkle scut jobs that never produce knots
- Improve `[improve]` cycles that restate the same claim

Escalate or stop; do not let context window be the only brake.

---

## Run worth gate (v1)

**Before** auto-truncating at `max_tool_calls` or killing a stalled sub-agent, Mag evaluates **worth** — symmetric to behavioral errors and tesuji shells.

| Verdict | Meaning | Action |
|---------|---------|--------|
| **valuable** | varied tools, artifacts, velocity | extend `max_tool_calls_defer` |
| **uncertain** | not enough signal yet | defer truncate (do not assume bad) |
| **worthless** | low score + identical loops | block at hard limit |
| **hung** | no heartbeat/step delta, zero artifacts | kill early (orchestrator stall) |

```powershell
python main.py run-worth status
python main.py run-worth evaluate RUN_ID
python main.py run-worth mark-good RUN_ID --note "100-step DeepSeek run was good"
```

Config: `configs/improve.yaml` → `run_worth` (thresholds, hung_timeout_s, defer cap).  
Logs: `logs/run_worth.jsonl`, operator overrides → `logs/run_worth_overrides.jsonl`.

---

## Related commands

```text
python main.py verkle-audit --dry
python main.py autorun --once --dry
python main.py spider --once
python main.py fkb lookup "<tool>"
python main.py v3-status --json
```
