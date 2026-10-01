# Mag container boundary

**Default install:** Mag runs in Docker — not as host-native subprocesses spawned from desktop shortcuts.

That is the safety fix for the connundrum: an agent stack with `run_shell`, `run_python`, and an orchestrator drainer must not roam your full desktop filesystem. The container is the cage; the host only exposes **localhost ports** and **explicit mounts**.

## What stays where

| Layer | Location | Can touch |
|-------|----------|-----------|
| **Container** | `mag-sovereign` image | `/app` + mounted dirs only |
| **Host mounts** | `memory/`, `watch/`, `logs/`, `state/`, `queue/` | Operator soil — your filed work |
| **Host IDE** | Cursor | Reads/writes `watch/` hooks; calls `http://127.0.0.1:8765` |
| **Secrets** | `.env` on host | Injected into container; never baked into image |

Not mounted: your home directory, SSH keys, unrelated projects, Docker socket.

## Quick start (Windows)

```powershell
git clone https://github.com/NachoBusiness17/Mag.git local_sovereign_agent
cd local_sovereign_agent
copy .env.example .env
# fill API keys

powershell -ExecutionPolicy Bypass -File scripts\install.ps1 -WithOllama -Shortcuts
```

Or manually:

```powershell
docker compose up -d --build
# optional LLM sidecar:
docker compose --profile ollama up -d --build
```

Open http://127.0.0.1:8765/

## Daily use

| Action | Command |
|--------|---------|
| Start | `launch_mag_container.cmd` or desktop **Mag Office** |
| Shell editor | `launch_sovereign_shell_container.cmd` |
| Cursor seat | `launch_cursor_seat.cmd` |
| CLI inside cage | `scripts\mag_exec.ps1 doctor` |
| Stop | `stop_mag_container.cmd` |
| Logs | `docker compose logs -f mag` |

## Fresh install / empty data

Same as bare-metal: Office shows **PROVISIONAL**, Mirror tour runs, Days/Ideas/Body are empty but honest. First `/api/v1/home` may seed `memory/bonds_active.md` inside the mount.

Run smoke inside the cage:

```powershell
scripts\mag_exec.ps1 multi-smoke
```

## Why not host `mag_launch`?

`ensure_services.cmd` / old desktop shortcuts spawned **detached Python on the host**. The backend tool service can run shell and Python against whatever is under `ROOT`. One bad tool loop or drainer misfire reaches your real machine.

Container mode:

- `cap_drop: ALL`, `no-new-privileges`
- `MAG_DRAINER=0` by default (opt-in only)
- `MAG_NO_MIRROR=1` unless you mount a mirror scaffold
- Ports bound to `127.0.0.1` only — not LAN-wide

## Dev override (advanced)

For integral watch+mag in one process without Docker:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py lab
```

Use only on a machine you treat as disposable dev soil — not the recommended operator path.

## Ollama

**Profile `ollama`** runs a sidecar; Mag sees it at `http://ollama:11434`.

Pull models inside the sidecar:

```powershell
docker compose exec ollama ollama pull gemma:2b
docker compose exec ollama ollama pull gemma4:latest
```

Or point `OLLAMA_HOST` at host Desktop Ollama if you prefer.

## Cursor bridge

`watch/cursor_bridge.py` on the host still works — it hits `http://127.0.0.1:8765` (port-forwarded from the container). Hooks write to `watch/cursor_feed.jsonl` on the host; the container reads the same file via mount.

```cmd
python watch/cursor_bridge.py health
python watch/cursor_bridge.py task "…" --mode delegate --seat cursor
```

## Cursor Canvas viewports

Set canvas source dirs (host paths with `*.canvas.tsx`), then sync:

```powershell
$env:CANVAS_SOURCES = "$env:USERPROFILE\.cursor\projects\<your-workspace>\canvases"
python main.py canvas-sync
# Dashboard → Canvas tab, or POST /api/v1/viewports/sync
```

Manifests land in `memory/viewports/` (gitignored runtime; `.gitkeep` only in repo).

## Mycelial Republic (sibling project)

Mag is the **private office**; [Mycelial Republic](../mycelial-republic) is the **public fork** — constitution, practice data, honest self-tests.

Fresh clone: **no personal beads** (correct). Framework seeds ship in `memory/`; Story tab and Office **launch pad** explain the two houses.

```powershell
cd ..
git clone <mycelial-republic-url> mycelial-republic
```

Set `MAG_REPUBLIC_ROOT` if not a sibling folder. See `memory/boot/REPUBLIC_LAUNCH.md`.

## Troubleshooting

```powershell
docker compose ps
docker compose logs mag
docker compose exec mag python main.py doctor
```

Rebuild after code changes:

```powershell
docker compose up -d --build
```

## Cross-seat coordination

Shared activity lives on the mounted `state/` volume (`state/shared_activity.jsonl`). DeepSeek agents and Cursor poll the same feed:

```powershell
curl -s http://127.0.0.1:8765/api/v1/coordination
python watch/cursor_bridge.py activity
python main.py coordinate "implement feature X" --background
```

See **[COORDINATION.md](COORDINATION.md)** for depth routing (local / Grok / DeepSeek) and token rules.
