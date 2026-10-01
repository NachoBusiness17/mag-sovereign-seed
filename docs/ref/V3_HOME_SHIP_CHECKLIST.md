# v3 home PC ship checklist

**When:** After v2 PRs **#8 → #9 → #10 → #11** merge, then pull PR **#13**.  
**Goal:** Desktop feels restful; improve feeds behavioral + nervous + spider; one kill switch.

---

## 1. One-time setup (30 min)

| Step | Command | Pass |
|------|---------|------|
| venv | `powershell -ExecutionPolicy Bypass -File scripts\ensure_venv.ps1` | `.venv\Scripts\python.exe` exists |
| shortcuts | `powershell -ExecutionPolicy Bypass -File scripts\install_desktop_shortcuts.ps1` | Desktop: Mag ON, Mag KILL, Mag Desktop |
| Cursor hooks | `scripts\install_cursor_hooks.cmd` | Copies `configs/cursor/` → `.cursor/` |
| v2 merge | Merge #8→#11 on home PC, pull `main`, merge PR #13 | `git log -1 --oneline` shows v3 modules |

---

## 2. Smoke (run once)

```cmd
scripts\v3_home_smoke.cmd
scripts\v3_deepseek_run.cmd
```

See **`docs/ref/V3_DEEPSEEK_RUN.md`** for DeepSeek build drain setup.

Or step by step:

```cmd
mag.cmd power start
mag.cmd doctor
mag.cmd power status
mag.cmd seats register --seat cursor --goal "smoke"
mag.cmd switchboard peers --live
mag.cmd improve-loop cycle --drain
mag.cmd nervous --json
mag.cmd spider --once
mag.cmd power stop
```

**Pass:** doctor OK · power stop leaves 0 mag pids · improve-loop returns `"ok": true`.

---

## 3. Daily habit

| Start | Work | Improve | Exit |
|-------|------|---------|------|
| `Mag ON` or `launch_desktop.cmd` | Cursor + `@memory/cursor_preamble_latest.md` | `cursor_bridge improve --claim "…" --enqueue` | `Mag KILL` |

**Never** for improve/background: raw `launch_agent.cmd` (REPL). Use `launch_agent_queue.cmd "goal"`.

---

## 4. Cloud agent (Cursor Cloud / background agent)

File outcomes to disk — chat is not the handoff:

```text
python watch/cursor_bridge.py improve --claim "one concrete fix" --enqueue
# or REST:
POST /api/v1/improve/cloud  { "claim": "…", "enqueue": true }
POST /api/v1/improve/cycle  { "drain": true }
```

That feeds: `logs/behavioral_events.jsonl` · `memory/training/events.jsonl` · nervous glance · spider tick · orchestrator queue.

---

## 5. Product gates (v3 shipped when)

- [ ] `v3_home_smoke.cmd` passes on home PC  
- [ ] Cursor sessionStart registers `ext-*` peer in `switchboard peers --live`  
- [ ] One improve cycle queues + drains without stdin hang  
- [ ] `mag_kill.cmd` → ports 8000/8765 free, no respawn  
- [ ] Body tab Power card shows UP/DOWN honestly  

---

## 6. If something fails

| Symptom | Fix |
|---------|-----|
| Orchestrator blind to Cursor | `cursor_bridge register` or reinstall hooks |
| Improve hangs | Use `--mode queue`, not REPL |
| Python whack-a-mole | `mag_kill.cmd` (not closing windows one-by-one) |
| Guard restarts after kill | `state/mag_power.off` should exist after kill; `power start` clears it |
| Hermes on PATH | Always `mag.cmd` or `.venv\Scripts\python.exe` |

See `docs/ref/MAG_V3_DISPATCH_PLAN.md` for dispatch waves.
