> **Deprecation banner:** cursor lane lapsed 2026-08-27 — current seats are Codex, Grok x2, DeepSeek. See `docs/ref/ZAI_API_EXPERT_REFERENCE.md` for current lanes.

# Cross-seat coordination

Mag routes work by **depth** so Grok, DeepSeek, and local janitors each do what they are good at — without burning tokens on the wrong seat.

**Single router:** `mag/router.py` → `route(goal)` · CLI `python main.py route "…"` · REST `POST /api/v1/route` · smoke `scripts/routing_smoke.py`

## Depth → seat map

| Depth | Seat | Launch | Use for |
|-------|------|--------|---------|
| `overview` | Grok TUI | Pack only | Big-picture maps, interlinking, ecosystem |
| `plan` | Grok TUI | Pack only | Architecture, tradeoffs, code planning |
| `heavy_code` | DeepSeek | Delegate / queue | Multi-step coding, refactors, tests |
| `simple_code` | Local (Ollama) | Dispatch | Small edits, one-file fixes |
| `scut` | Local | Dispatch | Status, bonds, brief, doctor |

## Shared visibility

All seats append to **`state/shared_activity.jsonl`**. Every context pack includes the last few rows so Codex, Grok x2, and DeepSeek agents see what the other current lanes are doing.

```powershell
# Read feed
curl -s http://127.0.0.1:8765/api/v1/coordination

# DeepSeek / Codex / Grok coordinate. Historical watch/cursor_bridge.py (Cursor lane lapsed 2026-08-27).
python main.py coordinate "implement lattice query API" --dry
python main.py coordinate "implement lattice query API" --background
```

Post heartbeat from any seat:

```powershell
curl -s -X POST http://127.0.0.1:8765/api/v1/coordination ^
  -H "Content-Type: application/json" ^
  -d "{\"seat\":\"deepseek\",\"depth\":\"heavy_code\",\"goal\":\"refactor seats.py\",\"status\":\"running\"}"
```

## CLI

```powershell
python main.py coordinate "big picture map of Mag and republic" --dry
python main.py coordinate "fix typo in README" 
python main.py coordinate "implement orchestrator heal loop" --background
python main.py coordinate "plan dashboard Body tab" --depth plan
```

## REST

```http
POST /api/v1/coordinate
{
  "goal": "implement canvas bridge tests",
  "seat": "deepseek",
  "depth": "heavy_code",
  "launch": true,
  "background": false
}
```

```http
GET /api/v1/coordination?limit=20
POST /api/v1/coordination  { "seat", "depth", "goal", "status" }
```

## Token rules (encoded in classifier)

1. **Never auto-run Grok** — overview/plan return a pack excerpt; operator pastes into TUI with `[priority]`.
2. **Heavy → DeepSeek** — tool loop or orchestrator queue (`--background`).
3. **Simple / scut → local** — Ollama janitor via `dispatch`.
4. **Context pack L0e** — coordination excerpt injected automatically.

## Dashboard

**Body** tab loads `/api/v1/coordination` — running seats + recent activity.

## Container

Works inside Docker — activity file lives on mounted `state/` volume.

See also: `memory/improve/SEATS.md`, `docs/ref/SOVEREIGN_STACK.md`. Historical `watch/cursor_bridge.py` (Cursor lane lapsed 2026-08-27).

## Peer handoffs (agent ↔ agent)

When a cloud, Codex, or Grok agent files work for home PC, use **peer handoff** so every seat sees it in `shared_activity.jsonl` and the handoff queue — not chat scroll.

```powershell
# Cloud agent files instructions for home PC
python main.py peer-handoff file ^
  --goal "Run dashboard v3 preview" ^
  --brief "Canvas tab, Shell compose, Trace rail" ^
  --from grok --track dashboard-v3 ^
  --command ".\scripts\env_switch.ps1 use dashboard-v3" ^
  --command ".\scripts\env_switch.ps1 run dashboard-v3" ^
  --pr https://github.com/NachoBusiness17/Mag/pull/18

# Home PC reads what the other agent said
python main.py peer-handoff list
python main.py peer-handoff latest
curl -s http://127.0.0.1:8765/api/v1/coordination
```

Home PC executes via env switcher: `docs/ref/ENV_SWITCHING.md`

Trail: `memory/handoff/peer_trail.jsonl` · Queue: `queue/handoff/peer-*.json`

## Tripartite boot (heart · mind · body)

When Mag boots multiple agents, each layer files coordination so every seat reads the same state:

| Layer | Role | Files |
|-------|------|-------|
| **Heart** | Local sovereign — disk, state, active env track | `memory/boot/tripartite_latest.md` |
| **Mind** | Routing — depth doctrine, peer handoffs, classify | `state/shared_activity.jsonl` |
| **Body** | Spawned agents — dashboard, scribe, drainer, Codex, Grok, DeepSeek | `mag_launch.py` slots |

```powershell
python main.py boot-coordination          # file heart/mind/body manifest
python mag_launch.py --once                 # supervisor boot + tripartite
python main.py boot --ensure                # sancho boot + tripartite
```

Every context-pack includes tripartite + peer handoffs + coordination feed — body agents see what mind routed and heart filed.

### Woven into orchestrator loops (not bolt-on)

Tripartite **pulses** ride existing subprocess edges — same trails as `task_lifecycle`:

```text
governor_autorun.fill_queue
  → enqueue_routed → weave_route (mind: depth + provider filed)

orchestrator.drain_once
  → spawn_task → weave_spawn (body: pid + goal)
  → _finalize → weave_terminal (body: done/failed/stalled)

mag_launch supervisor loop (~60s)
  → refresh_manifest_body (supervisor slots + orchestrator running tasks)

governor autorun_loop tick 0
  → maybe_boot_on_autorun_start (full manifest if stale)
  → autorun_once end → weave_autorun_tick (heart: fill/drain/governor)
```

Read live weave state: `memory/boot/tripartite_latest.json` · `GET /api/v1/coordination`
