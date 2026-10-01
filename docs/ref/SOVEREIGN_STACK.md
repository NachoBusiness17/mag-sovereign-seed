# Sovereign stack — three parallel tracks

Mag's north star: **own the boundary, own the chrome, own the brain** — rent decoders only at the edges.

```
Boundary (Mag disk) → Execution (agent_cli, :8000, orchestrator) → Decoder (swappable)
UI: Cursor (cockpit) | :8765 Shell (owned) | Grok (scarce judgment)
```

## Track A — UI (Sovereign Shell)

| Piece | Location |
|-------|----------|
| Monaco editor + file tree | `dashboard/static/sovereign_shell.html`, `shell.js`, `shell.css` |
| Safe workspace I/O | `mag/workspace_api.py` |
| REST | `GET/POST /api/v1/workspace/*` |
| Launch | `launch_sovereign_shell.cmd` → http://127.0.0.1:8765/shell |

Cursor-grade editing under Mag ROOT. CDN Monaco today; offline bundle is a later sovereign step.

## Track B — Integration (Cursor ↔ Mag)

| Piece | Location |
|-------|----------|
| REST bridge | `watch/cursor_bridge.py` |
| Hooks → Verkle | `watch/cursor_hook.py`, `.cursor/hooks.json` |
| Seat rule | `.cursor/rules/mag-cursor-seat.mdc` |

**Bridge commands**

```cmd
python watch/cursor_bridge.py pack
python watch/cursor_bridge.py ask "goal"
python watch/cursor_bridge.py delegate "tool-heavy goal"
python watch/cursor_bridge.py queue "background goal"
python watch/cursor_bridge.py autopilot [--drain]
python watch/cursor_bridge.py health
```

Cursor owns multi-file IDE work; Mag owns tool loops, memory, orchestrator queue.

## Inter-agent REST contract

**Bus:** Mag dashboard at `http://127.0.0.1:8765` (`dashboard/rest.py`).  
**Client:** `watch/cursor_bridge.py` — Cursor's HTTP client; do not paste task blocks into chat.

| Caller | Callee | REST | Bridge |
|--------|--------|------|--------|
| Cursor | Mag (context) | `GET /api/v1/context-pack` | `pack` |
| Cursor | Mag (health) | `GET /api/v1/health` | `health` |
| Cursor | Mag (tool loop) | `POST /api/v1/agent` | `ask`, `delegate` |
| Cursor | Mag (router) | `POST /api/v1/dispatch` | `task --mode dispatch` |
| Cursor | Mag (queue) | `POST /api/v1/orchestrator/queue` | `queue`, `task --mode queue` |
| Cursor | Mag (autopilot) | `POST /api/v1/autopilot` | `autopilot`, `task --mode autopilot` |
| Cursor | Mag (unified) | `POST /api/v1/seat/task` | `task --mode …` |
| Dashboard UI | same | same paths | — |
| Router / seats | Mag | `POST /api/v1/dispatch` | — |

**Unified task body** (`POST /api/v1/seat/task`):

```json
{
  "goal": "Implement seat-identity Option A in mag/seats.py",
  "seat": "cursor",
  "mode": "delegate",
  "provider": "deepseek",
  "session_id": "cursor"
}
```

Modes: `delegate` / `agent` → tool loop; `queue` → orchestrator; `autopilot` → improve+governor (goal optional); `dispatch` → classify seat + run.

**Example — task Mag from Cursor (seat-identity work):**

```cmd
python watch/cursor_bridge.py task "Implement seat-identity Option A per memory/improve/..." --mode delegate --seat cursor
```

```cmd
curl -s -X POST http://127.0.0.1:8765/api/v1/seat/task ^
  -H "Content-Type: application/json" ^
  -d "{\"goal\":\"Implement seat-identity Option A\",\"seat\":\"cursor\",\"mode\":\"queue\"}"
```

**Still copy-paste / CLI (not on REST bus yet):**

- Grok TUI judgment — pack via `GET /api/v1/context-pack`, then paste into TUI
- `python main.py …` one-offs (doctor, multi-smoke) — use dashboard buttons or REST aliases where they exist
- Sub-agent spawn/monitor — `POST /api/v1/agents` (REST exists; bridge wrapper not added — use curl or extend bridge)

**Env:** `MAG_URL` (default `http://127.0.0.1:8765`), `MAG_BRIDGE_TIMEOUT` (default 120s).

## Track C — Brain (autopilot + seed-mirror)

| Piece | Location |
|-------|----------|
| Autopilot pass | `mag/autopilot.py` |
| CLI | `python main.py autopilot [--drain] [--no-queue] [--no-governor]` |
| REST | `POST /api/v1/autopilot` |
| Log | `logs/autopilot_latest.json` |
| Drainer tick | `MAG_AUTOPILOT_EVERY` env on orchestrator drain loop |

Flow: seed-mirror readiness → top improve candidates → orchestrator enqueue → optional drain → governor cycle.

**Seed-mirror blocked until** W0.0 X archive in `../mycelial-republic/data/raw/`.

## Ports

| Service | Port |
|---------|------|
| Mag dashboard | :8765 |
| Mag backend | :8000 |
| Mirror desk | :8743 |
| Ollama | :11434 |

## Operator launch

```
stop_mag.cmd
start_everything.cmd
launch_cursor_seat.cmd   OR   launch_sovereign_shell.cmd
```

Hard refresh :8765 after static JS changes (Ctrl+Shift+R).
