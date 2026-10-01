# BUILD spec — {title}

**Commitment:** build-{slug}-001  
**Status:** draft | frozen  
**Branch:** cursor/{slug}-e2ce  
**Pipeline:** `docs/ref/MAG_BUILD_PIPELINE.md`

**Workflow:** Copy this template to `queue/handoff/BUILD-{slug}.md` (local, gitignored). Set `Status: frozen` before DeepSeek build.

## One line

{What ships in one sentence — no architecture essay.}

## Acceptance

- [ ] {measurable outcome 1}
- [ ] {measurable outcome 2}
- [ ] Commands in §Commands pass with exit 0
- [ ] Diff stays inside §Files in scope
- [ ] No §Files forbidden touched
- [ ] FILE block written to trail / audit JSON

## Files in scope (max 10)

| Path | Change |
|------|--------|
| `path/to/file.py` | {add | modify | delete} |

## Files forbidden

- `configs/secrets*`
- `memory/briefs/*` (unless spec says otherwise)
- {anything else out of bounds}

## Commands that must pass

```powershell
.venv/Scripts/python.exe scripts/routing_smoke.py
.venv/Scripts/python.exe -m pytest tests/test_{module}.py -q
```

## Tier / secrets law

- **Tier touch:** T2 only (no T0/T1 in remote pack)
- **Secrets:** none
- **G3 irreversible:** {none | list what needs L3}

## Rollback

{How to revert if audit fails — usually `git checkout main -- {paths}` or close branch.}

## Anti-goals

- {What DeepSeek must NOT do — e.g. refactor unrelated modules, add deps, re-plan architecture}

## Grok session

- **Date:** {YYYY-MM-DD}
- **Session id:** {optional}
- **Plan seat:** Grok + Cursor

## Build seat notes (DeepSeek fills after build)

- **Commands run:**
- **Paths changed:**
- **Open risks:**

## Audit verdict (Cursor fills after audit)

- **Verdict:** pass | fix | reject
- **Audit JSON:** `memory/runs/build_audit/{slug}.json`
- **Date:**
