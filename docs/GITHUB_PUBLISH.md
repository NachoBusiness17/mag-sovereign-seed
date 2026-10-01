# Publishing Mag to GitHub

## What ships in the repo

- Python package (`mag/`, `main.py`, `dashboard/`, `tests/`)
- Config **templates** (`configs/*.yaml`) — keys via env vars only
- Dashboard static assets (Body / Pulse / Days v2 / guidance queue)
- Launch scripts (`launch_*.cmd`, `start_everything.cmd`)
- Seed memory templates (see `memory/README.md`)

## What stays local (never push)

- `.env` and any file containing API keys
- `memory/biography/`, `agent_sessions/`, `attention.md`, decisions log
- `logs/`, `state/`, `queue/todo.md`
- `.cursor/`, portable bags, interaction logs

## First-time publish

```powershell
cd $env:USERPROFILE\Documents\projects\local_sovereign_agent
copy .env.example .env
# fill keys in .env — never commit

python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

python main.py doctor
python -m pytest tests/ -q --ignore=tests/test_supervision_soak.py
```

## Remote (example)

```powershell
git remote add origin https://github.com/NachoBusiness17/Mag.git
git push -u origin master
```

Use `main` instead of `master` if that is your default branch on GitHub.

## After clone (new machine) — container-first (recommended)

Mag runs in Docker so agent tools never roam your full desktop. See **`docs/CONTAINER.md`**.

```powershell
git clone https://github.com/NachoBusiness17/Mag.git local_sovereign_agent
cd local_sovereign_agent
copy .env.example .env
powershell -ExecutionPolicy Bypass -File scripts\install.ps1 -WithOllama -Shortcuts
# → http://127.0.0.1:8765/
```

Manual equivalent:

```powershell
docker compose up -d --build
docker compose --profile ollama up -d --build   # optional local LLM
```

CLI inside the cage: `scripts\mag_exec.ps1 doctor`

## After clone — dev-only (no container)

For disposable dev machines only — spawns agent tools on the host:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py lab
# → http://127.0.0.1:8765/
```

Hard-refresh the dashboard after upgrades: **Ctrl+Shift+R**.

## Isolated test environment

Mirrors a fresh clone without touching your live `memory/`:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/bootstrap_test_env.ps1
powershell -ExecutionPolicy Bypass -File scripts/bootstrap_test_env.ps1 -Launch
# test dashboard → http://127.0.0.1:8770/  (8770 avoids clashing with prod :8765)
```

Manual worktree (same commit, separate folder):

```powershell
git worktree add ..\mag_test_env -b env-test HEAD
cd ..\mag_test_env
copy .env.example .env
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py doctor
python -m pytest tests/ -q --ignore=tests/test_supervision_soak.py
python main.py lab --port 8770
```
