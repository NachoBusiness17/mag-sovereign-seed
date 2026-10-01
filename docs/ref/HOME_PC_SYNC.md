# Home PC sync — Windows (operator Nacho)

**Commitment:** `home-pc-sync-001`  
**Job:** Pull branch work + refresh research clones. **Never assume cwd.**

**Behavioral lessons (2026-08-05):**
- Pasting `git` / `./scripts/*.sh` from cloud without `cd` → fails in `C:\Users\foste`
- PowerShell: **`mag.cmd` alone fails** — use **`.\mag.cmd`** or **`.\mag.ps1`** from repo root (Command_Precedence)

## Rule for agents

1. **Do not** give bare `mag.cmd` in PowerShell — always **`.\mag.cmd`** or **`.\mag.ps1`**.  
2. **Do** use `scripts\home_sync.cmd` (batch handles paths) or verify repo root.  
3. **Do** use `.cmd` scripts on Windows, `.sh` on Linux/cloud.  
4. **Default repo (Nacho):** `%USERPROFILE%\Documents\projects\local_sovereign_agent`
5. **Switch tracks** (research / operational / queue-lanes / baseline): `docs/ref/ENV_SWITCHING.md` · `scripts\env_switch.ps1 list`

---

## One command (from anywhere — script finds repo)

```powershell
# Set once if repo is not default path:
# $env:MAG_ROOT = "D:\path\to\local_sovereign_agent"

powershell -ExecutionPolicy Bypass -File "$env:USERPROFILE\Documents\projects\local_sovereign_agent\scripts\home_sync.cmd"
```

Or after `cd` to repo:

```powershell
cd $env:USERPROFILE\Documents\projects\local_sovereign_agent
scripts\home_sync.cmd
scripts\home_sync.cmd cursor\mesh-comm-research-e2ce
```

---

## What home_sync.cmd does

1. Resolve repo root (`MAG_ROOT` or walk up for `mag.cmd`)  
2. `git fetch origin`  
3. `git checkout` + `git pull` target branch (default: current tracking branch)  
4. `scripts\pull_mesh_comm_repos.cmd`  
5. `scripts\pull_gstdcoin_repos.cmd`  
6. `.\mag.cmd doctor` (or `.\mag.ps1 doctor`)  
7. `.\mag.cmd context-pack --mode janitor`  

Optional — full mesh integration pass for local agent:

```powershell
scripts\mesh_comm_deep_dive.cmd
.\mag.cmd agent --provider deepseek
```

See `docs/ref/MESH_LOCAL_AGENT.md`.

---

## Manual (only if script fails)

```powershell
cd $env:USERPROFILE\Documents\projects\local_sovereign_agent   # adjust if needed
git fetch origin
git checkout cursor/mesh-comm-research-e2ce
git pull origin cursor/mesh-comm-research-e2ce
scripts\pull_mesh_comm_repos.cmd
scripts\pull_gstdcoin_repos.cmd
.\mag.cmd doctor
.\mag.cmd context-pack --mode janitor
```

**Find repo if unknown:**

```powershell
Get-ChildItem -Path $env:USERPROFILE -Recurse -Filter "mag.cmd" -ErrorAction SilentlyContinue | Select-Object -First 3 DirectoryName
```

---

## Active branch (our work)

| Branch | PR | Contains |
|--------|-----|----------|
| `cursor/mesh-comm-research-e2ce` | #17 | ILAP + mesh forest + scout spores (fullest) |
| `cursor/v3-deepseek-run-e2ce` | #15 | v3 wiring + ILAP (subset of mesh branch) |

Prefer **mesh-comm-research** for latest research stack.

---

## Cloud agent

Cloud workspace is already at repo root — use `./scripts/mesh_comm_ilap_run.sh` and `.venv/bin/python`, not `mag.cmd` unless on Windows.
