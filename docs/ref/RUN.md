# RUN — one command, one surface

**Commitment:** `run-one-command-001`  
**Job:** The single documented way to bring up the functioning core, plus a categorized inventory of every `.cmd` launcher so we stop pretending 33 entry points are "the surface."

---

## The ONE command

```powershell
python main.py wake
```

`wake` is the canonical cold start. It does two things, no ceremony:

1. **Supervisor up** — `mag/process_supervisor.start_all()` starts the default loops:
   - `autorun` — governor/autorun consolidated loop (fill + drain + governor + cadence)
   - `ghost-daemon` — Ghost control plane (FastAPI :9000): sense + cycle + copilot + autonomous + SSE + REST
2. **START_BRIEF greeting** — `mag/state_brief.write()` renders `state/START_BRIEF.md` from live framework state: where we were, what's running, what landed, what's next — measured (bytes, freshness, verkle root, queue counts).

Result: the functioning core is up and the operator gets a measured brief. One command, one surface.

> **Why not the other 32?** They are specialized seats, container paths, or legacy aliases of the same supervisor. `wake` is the only one that brings up the *core* and *tells you what's running* in one shot. The rest are documented below so nothing is hidden — but none of them is the front door.

---

## The documented stop

```powershell
mag_kill.cmd
```

`mag_kill.cmd` runs `main.py power stop --json` — stops supervisor, dashboard, backend, workers, seat-guard. No respawn until you run `wake` again.

Alias: `stop_mag.cmd` (same `power stop`, non-JSON).

---

## Launcher inventory (33 `.cmd` files)

Grouped into four categories. **Core** = brings up the functioning core. **Specialized-seats** = one focused surface. **Container** = Docker path. **Legacy** = superseded by `wake`/`power`; kept for compatibility, not the surface.

### Core — bring up the functioning core

| Launcher | What it runs | Status |
|----------|--------------|--------|
| `main.py wake` | supervisor loops + START_BRIEF | **THE one command** |
| `mag_on.cmd` | `main.py power start --browser` (backend :8000 + dashboard :8765 + mirror :8743) | Core (full-stack turn-on) |
| `boot_mag.cmd` | `main.py power start --browser` (silent, Windows Startup/auto) | Core (auto-boot) |
| `mag.cmd` | main CLI wrapper (`main.py …`) | Core (CLI front door) |
| `mag_kill.cmd` | `main.py power stop --json` | **THE documented stop** |
| `stop_mag.cmd` | `main.py power stop` | Core (stop alias) |
| `start_dashboard.cmd` | `main.py dashboard --host 127.0.0.1 --port 8765` (restart loop) | Core (dashboard only) |
| `dashboard.cmd` | `ensure_services.cmd` + open :8765 | Core (dashboard only) |
| `launch_dashboard.cmd` | `ensure_services.cmd` + open :8765 | Core (dashboard only) |
| `switchboard_live.cmd` | dashboard + `main.py mag` + `main.py guard` + optional `seat-guard` | Core (switchboard stack) |
| `switchboard_status.cmd` | `main.py switchboard status` | Core (status check) |

### Specialized-seats — one focused surface

| Launcher | What it runs | Status |
|----------|--------------|--------|
| `launch_agent.cmd` | `main.py agent --provider deepseek` (interactive REPL) | Specialized-seat |
| `launch_agent_deepseek.cmd` | `main.py agent --provider deepseek` | Specialized-seat |
| `launch_agent_local.cmd` | `main.py agent --provider ollama` | Specialized-seat |
| `launch_agent_desk.cmd` | `ensure_services.cmd` + open Agent Desk tab | Specialized-seat |
| `launch_agent_machine.cmd` | `mag.cmd factory-machine run --note "<goal>"` | Specialized-seat |
| `launch_agent_queue.cmd` | queued goal via `launch_agent.cmd` + cursor bridge | Specialized-seat |
| `launch_run_sprint.cmd` | `mag.cmd factory-machine run --note "<goal>"` | Specialized-seat |
| `run_sprint.cmd` | `mag.cmd coding-session run` | Specialized-seat |
| `queue_deepseek.cmd` | `main.py orchestrator queue add … --provider deepseek` | Specialized-seat |
| `launch_voice.cmd` | `main.py cast` (voice) | Specialized-seat |
| `launch_sovereign_shell.cmd` | `ensure_services.cmd` + open :8765/shell | Specialized-seat |
| `launch_desktop.cmd` | `mag_on.cmd` + cursor seat boot | Specialized-seat |
| `desk_refresh.cmd` | restart lab + refresh local seat | Specialized-seat |
| `launch_dashboard_lan.cmd` | `main.py dashboard` on LAN | Specialized-seat |
| `phase1_verify.cmd` | `main.py multi-smoke` + `catch-up` + `nervous` + `orchestrator` | Specialized-seat (verification) |

### Container — Docker path

| Launcher | What it runs | Status |
|----------|--------------|--------|
| `launch_mag_container.cmd` | `docker compose up -d --build` + health wait + open :8765 | Container |
| `launch_sovereign_shell_container.cmd` | container + open :8765/shell | Container |
| `stop_mag_container.cmd` | `docker compose down` | Container (stop) |
| `launch_cursor_seat.cmd` | container + `main.py context-pack` + `main.py seats register` | Container |
| `setup-wsl.cmd` | WSL2 + Docker backend setup (admin) | Container (setup) |

### Legacy — superseded, kept for compatibility

| Launcher | What it runs | Why legacy |
|----------|--------------|------------|
| `start_everything.cmd` | `mag_launch.py` full stack | Superseded by `wake`/`power start` — same supervisor, older alias |
| `ensure_services.cmd` | `mag_launch.py` (backend + dashboard) | Superseded by `wake`; still called by many specialized-seat launchers as a pre-step |
| `start_tripartite.cmd` | `mag_launch.py` (Engine + Scribe + Dashboard) | Superseded by `wake`/`power` — the "tripartite" role split is now the consolidated supervisor |

> **No dead paths found.** Every launcher's `main.py` subcommand and referenced `.py`/`.ps1` file was cross-checked against `main.py` subparsers and `mag/gap_analysis.py` module gaps — all resolve. The three flagged **Legacy** are not broken; they are *superseded aliases* of the same supervisor that `wake`/`power` now drive. They are kept so nothing breaks, but they are not the surface.

---

## Decision table

| You want to… | Run |
|--------------|-----|
| Bring up the functioning core | `python main.py wake` |
| Full-stack turn-on + browser | `mag_on.cmd` |
| Stop everything | `mag_kill.cmd` |
| Open the dashboard only | `start_dashboard.cmd` |
| Run one interactive agent (deepseek) | `launch_agent.cmd` |
| Run a factory-machine sprint | `launch_run_sprint.cmd` |
| Run in Docker | `launch_mag_container.cmd` |
| Verify the stack is green | `phase1_verify.cmd` |

---

## Why this matters

33 launchers with no single clear entry = "no clear functioning system." `wake` collapses that to one command. The inventory above makes every launcher's purpose and status explicit — nothing is hidden, nothing is pretending to be the surface.
