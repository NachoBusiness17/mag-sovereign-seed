# BUILD spec — Factory audit JSON scaffold

**Commitment:** build-factory-audit-json-001  
**Status:** draft  
**Branch:** cursor/factory-audit-json-e2ce  
**Pipeline:** `docs/ref/MAG_BUILD_PIPELINE.md`  
**Pilot:** #1 of 3 factory pipeline pilots (see `docs/ref/MAG_FACTORY_PILOT.md`)

**Workflow:** Copy to `queue/handoff/BUILD-factory-audit-json.md` and set `Status: frozen` before build.

## One line

Add a minimal build-audit JSON writer + schema so Cursor audit phase FILEs structured verdicts to disk.

## Acceptance

- [ ] `memory/runs/build_audit/` directory documented in `memory/runs/README.md`
- [ ] `mag/factory_audit.py` writes `{slug, verdict, spec_path, diff_stat, commands, timestamp}` JSON
- [ ] `python main.py factory-audit --slug {slug} --verdict pass|fix|reject` CLI exists
- [ ] `tests/test_factory_audit.py` covers write + load round-trip
- [ ] `scripts/routing_smoke.py` still passes
- [ ] No changes outside §Files in scope

## Files in scope (max 10)

| Path | Change |
|------|--------|
| `mag/factory_audit.py` | add |
| `main.py` | add `factory-audit` subcommand |
| `tests/test_factory_audit.py` | add |
| `memory/runs/README.md` | modify — document build_audit/ |
| `memory/runs/build_audit/.gitkeep` | add |

## Files forbidden

- `mag/governor_autorun.py` (no autorun wiring in pilot 1)
- `configs/lanes.yaml`
- `docs/ref/MAG_v4_THEORY.md` (theory only — no code coupling)

## Commands that must pass

```powershell
.venv/Scripts/python.exe scripts/routing_smoke.py
.venv/Scripts/python.exe -m pytest tests/test_factory_audit.py -q
.venv/Scripts/python.exe main.py factory-audit --slug factory-audit-json --verdict pass --dry
```

## Tier / secrets law

- **Tier touch:** T2 only
- **Secrets:** none
- **G3 irreversible:** none

## Rollback

```powershell
git checkout main -- mag/factory_audit.py main.py tests/test_factory_audit.py memory/runs/README.md
```

## Anti-goals

- Do not wire factory-audit into autorun or orchestrator yet (pilot 2)
- Do not add Grove poem generation (v3)
- Do not refactor ponytail-audit — only add parallel build-audit path

## Grok session

- **Date:** 2026-08-05
- **Plan seat:** Grok + Cursor (this spec)

## Build seat notes (DeepSeek fills after build)

- **Commands run:**
- **Paths changed:**
- **Open risks:**

## Audit verdict (Cursor fills after audit)

- **Verdict:** pending
- **Audit JSON:** `memory/runs/build_audit/factory-audit-json.json`
- **Date:**
