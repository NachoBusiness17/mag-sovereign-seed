# RESUME BOARD — 09-05 (crash-resilience: this file is the door)

> WINDOW DEATH INSURANCE: everything resumable lives here + the boards below. A dead window
> never eats the plan — the next window reads this and continues.

- **AUTH SWITCHBOARD LIVE** (09-05, the swap-recovery organ): `python -m mag.auth_switchboard status` = one-command auth health check; the 09-05 swap left 2 dead lanes enabled (API-Key code=1000, Start-Plan 401 expired) while the coding-plan lane PASSES. Way back + card: watch/SELF_STEAL_ENV_SWITCH_20260905.md. `use <name>` is GO-gated operator hand; `snapshot known_good` after the fix makes every future swap one word to undo.

- **TRAJECTORY STREAM LIVE** (spine build #1, tesuji landed 09-05 17:0xZ): PostToolUse hook armed in config.json (backup .bak-pre-trajectory-20260905); every Bash call seals a step; `python -m mag.trajectory_step stats|verify|test-reject`; card watch/SELF_STEAL_TRAJECTORY_STEP_20260905.md. First organic steps = next window boot (hooks load at session start) — likely tonight's 23:00 night shift.
- **WEEKEND BURN BOARD** (5 builds, falsifiers, lane assignment): watch/WEEKEND_BURN_BOARD_20260905.md — B1+B2+B3 fire as the three free windows at 11:00 pool open; B5 next slot; B4 long-horizon.
- **Salon receipt**: memory/runs/salons/self_steal_moonshot_20260905/SALON_ARTIFACT.md (5/7 shapes, fold ranked all builds).
- **Capacity cap law**: ≤3 free windows; 4th+ auto-launch on Max.
- **Day capacity runbook**: watch/DAY_CAPACITY_RUNBOOK_20260905.md.

---

## Lane daemon re-arm — SUPERSEDED 2026-09-05 (STRUCTURE, not prose)

The daemon now lives in the mag_launch roster (slot `lane_scheduler`): container
recreates respawn it, kills get respawned by the supervisor. NEVER hand-run the
one-liner below — the daemon now REFUSES when stdout is redirected into its own
log (one file, one writer). Kept for history only:

```
# fence-owner: operator - standing container daemon start (mag-sovereign lane runner). FW-11 2026-09-28; receipt: watch/inbox/fifty_wide_20260917/FW11_fence_owners.md
docker exec -d mag-sovereign sh -c "python /app/mag/lane_runner.py --daemon >> /app/logs/lane_scheduler.log 2>&1"
```

Re-armed 2026-09-05T00:12:21Z pid 2082 after the 23:33:46Z engine recreate. mag_launch does NOT start it; after any mag-sovereign recreate, run the line above once.
