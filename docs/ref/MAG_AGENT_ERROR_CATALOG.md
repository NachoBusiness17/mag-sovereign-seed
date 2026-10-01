# Mag agent error catalog — common failures & fixes

**Commitment:** `mag-agent-error-catalog-001`  
**As-of:** 2026-08-05  
**Status:** Living doc — append when agents fail new ways  
**Parents:** `JONES_AGENT_FLEET_PACK.md` · `FRAMEWORK_LOAD.md` · FKB · `memory/remedies/`

**Job:** Pre-create remedies so coding agents on Mag tasks fail fast, recover fast, and emit training labels.

---

## How to use

| Who | Action |
|-----|--------|
| **Agent** | Scan §2 before starting; if error matches, apply fix — don't re-litigate |
| **Operator** | Add new rows when an agent repeats a mistake 3× |
| **FKB** | `python main.py fkb search "<error fragment>"` |
| **Training** | Tag `pattern_tags` in `training_events` from §2 code column |

---

## 1. Error taxonomy

| Code | Category | Training tag |
|------|----------|--------------|
| E01–E09 | Environment / boot | `env_wrong_python` |
| E10–E19 | Routing / seats | `seat_bleed` |
| E20–E29 | Scope / factory | `factory_scope_creep` |
| E30–E39 | Files / DNA law | `dna_violation` |
| E40–E49 | Tools / implementation | `tool_shape` |
| E50–E59 | Coordination / handoff | `chat_handoff` |
| E60–E69 | v3 research | `v3_premature` |
| E70–E79 | Mobile / voice | `voice_premature` |

---

## 2. Catalog (agent-facing)

### E01 — Wrong Python (`No module named 'langgraph'`)

| | |
|--|--|
| **Symptom** | `import` errors, missing `mag`, `langgraph`, wrong venv |
| **Cause** | Bare `python` on PATH → Hermes venv, not Mag `.venv` |
| **Fix** | `.venv/Scripts/python.exe main.py …` or `mag.cmd doctor` |
| **Prevent** | Run `mag.cmd doctor` first; never `pip install` into Hermes |
| **Tag** | `env_wrong_python` |

### E02 — Skipped framework load

| | |
|--|--|
| **Symptom** | Invented CLI flags, wrong architecture, "let me merge v3 first" |
| **Cause** | Agent didn't read `FRAMEWORK_LOAD.md` + role doc |
| **Fix** | STOP → load Tier 0 from `JONES_AGENT_FLEET_PACK.md` §3 |
| **Prevent** | Activation block requires load confirmation |
| **Tag** | `skipped_framework_load` |

### E03 — Cloud agent assumes gemma4 / Ollama up

| | |
|--|--|
| **Symptom** | Tests skip, `doctor` fails on model probes |
| **Cause** | Cloud VM has no home Ollama |
| **Fix** | Use `.venv/bin/python -m pytest` with mocks; don't claim local janitor works |
| **Prevent** | Task spec says `cloud_ok: true` or run on home PC |
| **Tag** | `cloud_no_ollama` |

### E04 — PowerShell vs bash path

| | |
|--|--|
| **Symptom** | `.\.venv\Scripts\python.exe` fails on Linux cloud |
| **Cause** | Copied Windows commands |
| **Fix** | `.venv/bin/python main.py …` on Linux |
| **Prevent** | Check `sys.platform` in runbooks |
| **Tag** | `env_wrong_python` |

### E05 — `mag.cmd` missing on Linux

| | |
|--|--|
| **Symptom** | `mag.cmd: command not found` |
| **Cause** | `mag.cmd` is Windows wrapper |
| **Fix** | `.venv/bin/python main.py <subcommand>` |
| **Tag** | `env_wrong_python` |

---

### E10 — Grok on scut work

| | |
|--|--|
| **Symptom** | Token burn on classify, typo fix, status check |
| **Cause** | Default to frontier |
| **Fix** | `route` → janitor; Grok only `[priority]` / plan phase |
| **Prevent** | `MAG_BUILD_PIPELINE` cost table |
| **Tag** | `seat_bleed` |

### E11 — DeepSeek re-plans architecture

| | |
|--|--|
| **Symptom** | BUILD spec ignored; new design in build phase |
| **Cause** | Unfrozen spec or chat handoff |
| **Fix** | Reject build; return to plan seat; freeze BUILD spec |
| **Prevent** | `Status: frozen` gate |
| **Tag** | `factory_scope_creep` |

### E12 — Cursor audit adds features

| | |
|--|--|
| **Symptom** | Audit PR grows scope |
| **Cause** | Audit session not constrained |
| **Fix** | Audit pack: diff + spec only; verdict pass/fix/reject |
| **Tag** | `factory_scope_creep` |

### E13 — Hermes as default agent

| | |
|--|--|
| **Symptom** | Slow/broken tool loops |
| **Cause** | Ignored `SEATS.md` — Hermes parked |
| **Fix** | `agent --provider deepseek` or janitor |
| **Tag** | `seat_bleed` |

### E14 — Missing `[priority]` for Grok

| | |
|--|--|
| **Symptom** | Grok budget refused / route defers |
| **Cause** | `lanes.yaml` `require_priority: true` |
| **Fix** | Add `[priority]` to goal or use DeepSeek for code |
| **Tag** | `seat_bleed` |

---

### E20 — Build without frozen handoff

| | |
|--|--|
| **Symptom** | DeepSeek invents scope |
| **Cause** | No `queue/handoff/BUILD-*.md` with `Status: frozen` |
| **Fix** | Operator freeze; copy from `docs/ref/BUILD-TEMPLATE.md` |
| **Tag** | `factory_no_freeze` |

### E21 — Files forbidden touched

| | |
|--|--|
| **Symptom** | Spec violation; audit reject |
| **Cause** | Agent refactored "while here" |
| **Fix** | `git checkout` forbidden paths; rebuild |
| **Tag** | `factory_scope_creep` |

### E22 — Skipped routing_smoke / pytest

| | |
|--|--|
| **Symptom** | PR fails CI; audit reject |
| **Cause** | BUILD spec commands not run |
| **Fix** | Run commands from spec; FILE exit codes |
| **Tag** | `factory_skip_verify` |

### E23 — Pilot N+1 before audit pass

| | |
|--|--|
| **Symptom** | Compounding debt |
| **Cause** | Skipped `MAG_FACTORY_PILOT` gate |
| **Fix** | Complete audit JSON; verdict `pass` first |
| **Tag** | `factory_skip_verify` |

---

### E30 — Chat as handoff

| | |
|--|--|
| **Symptom** | Next seat re-reads entire history |
| **Cause** | No FILE block; no BUILD spec / pack |
| **Fix** | `context-pack` + one goal; FILE to trail |
| **Prevent** | Elias rope law — `COORDINATION_ELIAS_ROPE.md` |
| **Tag** | `chat_handoff` |

### E31 — Second DNA store

| | |
|--|--|
| **Symptom** | New "memory" DB, agent chat DB, vector throne |
| **Cause** | Over-engineering |
| **Fix** | Use residual + trail + `training/events.jsonl` edges |
| **Tag** | `dna_violation` |

### E32 — T0/T1 sent remote

| | |
|--|--|
| **Symptom** | Tier law breach |
| **Cause** | Full briefs/secrets in API pack |
| **Fix** | `context-pack` only; redact on export |
| **Tag** | `dna_violation` |

### E33 — Auto-promote / auto-merge

| | |
|--|--|
| **Symptom** | Config changed without human |
| **Cause** | Agent assumed autonomy |
| **Fix** | `promote --apply` L3 only; PR merge L3 |
| **Tag** | `dna_violation` |

### E34 — Claiming out of alpha

| | |
|--|--|
| **Symptom** | "Production ready" docs |
| **Cause** | Marketing drift |
| **Fix** | Read `MAG_PROJECT_PROPOSAL.md` §4 honesty |
| **Tag** | `metric_theater` |

---

### E40 — `write_file` wrong shape

| | |
|--|--|
| **Symptom** | `unexpected keyword`, empty `{}`, nested `arguments` |
| **Cause** | Model tool-call format |
| **Fix** | See `memory/remedies/rem-write-file-shape.md` |
| **Tag** | `tool_shape` |

### E41 — Invented CLI flags

| | |
|--|--|
| **Symptom** | `main.py` argparse error |
| **Cause** | Agent hallucinated subcommand |
| **Fix** | `python main.py --help` or grep `main.py` |
| **Tag** | `tool_shape` |

### E42 — Empty DeepSeek replies (×3)

| | |
|--|--|
| **Symptom** | Orchestrator loop, no diff |
| **Cause** | Keys, WAF, rate limit |
| **Fix** | FKB guard; `--import` for web export; switch task |
| **Tag** | `empty_reply` |

### E43 — Test imports wrong ROOT

| | |
|--|--|
| **Symptom** | `ModuleNotFoundError: mag` in pytest |
| **Cause** | Missing `sys.path` or wrong cwd |
| **Fix** | Copy pattern from `tests/test_v3_modules.py` |
| **Tag** | `tool_shape` |

---

### E50 — Second orchestrator

| | |
|--|--|
| **Symptom** | Parallel spawn systems, agent-to-agent chat |
| **Cause** | Framework cosplay |
| **Fix** | One router, one orchestrator; pigeonhole steer |
| **Tag** | `chat_handoff` |

### E51 — Full repo in context

| | |
|--|--|
| **Symptom** | Token bleed, slow, wrong focus |
| **Cause** | Ignored pack-first |
| **Fix** | `context-pack` max; BUILD spec file scope |
| **Tag** | `chat_handoff` |

### E52 — No FILE at session end

| | |
|--|--|
| **Symptom** | Next agent lacks case law |
| **Cause** | Chat died without trail |
| **Fix** | FILE block → `memory/runs/` or handoff |
| **Tag** | `chat_handoff` |

---

### E60 — v3 before v2 gate

| | |
|--|--|
| **Symptom** | spider/resonance wired before router merge |
| **Cause** | Skipped merge order |
| **Fix** | `HANDOFF_MAG_AGENT_TODOS.md` §1 — #8→#11 first |
| **Tag** | `v3_premature` |

### E61 — Athena / Steiniger persona product

| | |
|--|--|
| **Symptom** | Identity theater in code/docs |
| **Cause** | slashreboot cosplay |
| **Fix** | Steal static/dynamic ops only — not EUT persona |
| **Tag** | `metric_theater` |

### E62 — Training on chat logs

| | |
|--|--|
| **Symptom** | Mirror dataset as conductor labels |
| **Cause** | Wrong training signal |
| **Fix** | `MAG_TRAINING_DATA_SPEC.md` — orchestration outcomes only |
| **Tag** | `dna_violation` |

---

### E70 — Mobile voice before voice/turn API

| | |
|--|--|
| **Symptom** | Expo app with no backend |
| **Cause** | Skipped phase 0 |
| **Fix** | `MAG_MOBILE_VOICE_SPEC.md` phases; PWA first |
| **Tag** | `voice_premature` |

### E71 — Public :8765 expose

| | |
|--|--|
| **Symptom** | Security incident |
| **Cause** | Port forward without auth |
| **Fix** | Tailscale + device tokens |
| **Tag** | `dna_violation` |

---

## 3. Pre-flight checklist (every agent turn)

```text
[ ] mag.cmd doctor OR .venv/*/python main.py doctor
[ ] Loaded role doc from JONES_AGENT_FLEET_PACK §4
[ ] context-pack pasted (not full chat)
[ ] ONE job / ONE BUILD spec / ONE epic
[ ] Seat correct for phase (plan/build/audit)
[ ] Files in scope listed — max 10
[ ] Commands to run identified
[ ] FILE block ready for session end
```

---

## 4. When to append a new error

1. Agent repeated mistake ≥3× (FKB threshold)  
2. Add row with code E80+  
3. Draft remedy in `memory/remedies/`  
4. `grove-build` when grove ships  
5. Tag in `configs/training_patterns.yaml` when exists  

---

*End error catalog — Jones fleet agents load this with the attach pack.*
