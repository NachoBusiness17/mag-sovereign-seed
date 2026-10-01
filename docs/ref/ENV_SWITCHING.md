# Environment switching — cutting-edge tracks

Named **tracks** map to git branches and isolated lab ports so you can run research, operational home desk, queue-lane experiments, and baseline without clashing.

| Track | Branch | Port | Root |
|-------|--------|------|------|
| `operational` | `unify-mag-home` | 8765 | `mag_test_env` worktree |
| `research` | `cursor/mesh-comm-research-e2ce` | 8766 | main repo |
| `queue-lanes` | `cursor/queue-lanes-behavioral-logging` | 8767 | main repo |
| `baseline` | `master` | 8770 | main repo (or `mag_env_baseline` if multi-worktree) |
| `dashboard-v3` | `cursor/dashboard-v3-base-e2ce` | 8765 | `mag_env_dashboard_v3` worktree — PR #18 preview |

Registry: `configs/env_tracks.yaml` · Active marker: `.mag_active_env`

## Commands (PowerShell, from repo root)

```powershell
.\scripts\env_switch.ps1 list
.\scripts\env_switch.ps1 use research
.\scripts\env_switch.ps1 status
.\scripts\env_switch.ps1 sync operational
.\scripts\env_switch.ps1 run research
```

Or via batch: `scripts\env_switch.cmd list`

Python: `python main.py env list|status|use research`

## Multi-worktree mode

Set `$env:MAG_MULTI_WORKTREE = "1"` to create `mag_env_{track}` worktrees on demand instead of switching the main repo branch. Existing `mag_test_env` (operational) is unchanged.

See also: `docs/ref/HOME_PC_SYNC.md` for one-shot home PC pull.
