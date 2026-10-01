# BUILD — v3 DeepSeek code run (Wave 0 → Wave 1 bridge)

**Status:** frozen  
**Slug:** `v3-deepseek-run`  
**Branch:** `cursor/v3-deepseek-run-e2ce`  
**Parent:** `docs/ref/MAG_V3_DISPATCH_PLAN.md` · `docs/ref/V3_DEEPSEEK_RUN.md`

---

## Goal

One operator command queues and drains a **DeepSeek build goal** through the v3 harness (orchestrator → agent tools → training events → improve-loop → spider), after v2 lattice is on disk.

## Scope

| In | Out |
|----|-----|
| `scripts/v3_deepseek_run.cmd` + `.sh` | Factory pilot `build_audit.py` |
| Orchestrator `task_lifecycle` training hooks | Pack modes (Wave 1 BUILD) |
| REST `GET /api/v1/grove` | Layman layout JSON |
| Spider → switchboard `steer_drop` | Auto-promote |

## Preconditions

1. Merge PR **#8 → #11** on home PC (v2 lattice)
2. Merge or pull PR **#13** (v3 modules)
3. `.env` with `DEEPSEEK_API_KEY`
4. `scripts/v3_home_smoke.cmd` passes

## Acceptance

```text
scripts/v3_deepseek_run.cmd "[build] your goal"
→ doctor OK · drain returns task_id · training-events shows task_lifecycle
→ improve-loop cycle ok · spider tick ok
```

## Verify

```powershell
mag.cmd doctor
python main.py training-events --stats
python main.py orchestrator queue status
curl http://127.0.0.1:8765/api/v1/grove?limit=5
```

## Seat assignment

| Phase | Seat |
|-------|------|
| Merge v2 | Human + Cursor |
| This BUILD wiring | Cloud agent / Cursor |
| Queued goals | DeepSeek `agent --provider deepseek` |
| Audit | Cursor ponytail-audit |

---

*Frozen 2026-08-05 — operator L3*
