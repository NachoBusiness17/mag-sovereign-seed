# local_sovereign_agent — Mag Resource Harness

**For LLMs — load framework first:** [`docs/FRAMEWORK_LOAD.md`](docs/FRAMEWORK_LOAD.md) · [`LOAD.md`](LOAD.md)  
**Compass — vision, loop, v1–v10 arc:** [`docs/ref/MAG_MYCELIAL_REPUBLIC_COMPASS.md`](docs/ref/MAG_MYCELIAL_REPUBLIC_COMPASS.md)  
**Mycelial science — biology ↔ protocol:** [`docs/ref/MYCELIAL_SCIENCE_MAP.md`](docs/ref/MYCELIAL_SCIENCE_MAP.md)  
**Future walkthrough — v2→v10 + subsystems:** [`docs/ref/MAG_FUTURE_WALKTHROUGH.md`](docs/ref/MAG_FUTURE_WALKTHROUGH.md)  
**Vision — v2 completion + desk loop factory:** [`docs/ref/MAG_VISION_AUTOMATION.md`](docs/ref/MAG_VISION_AUTOMATION.md)  
**For everyone — full proposal:** [`docs/ref/MAG_PROJECT_PROPOSAL.md`](docs/ref/MAG_PROJECT_PROPOSAL.md)  
**For humans — dashboard how-to:** [`docs/HOW_TO_MAG_DASHBOARD.md`](docs/HOW_TO_MAG_DASHBOARD.md)  
**Run — one command, one surface:** [`docs/ref/RUN.md`](docs/ref/RUN.md) — `python main.py wake` brings up the core; `mag_kill.cmd` stops it

**Product home for the local orchestrator.** Local models do memory, briefs, and scutwork; **remote specialist seats are scarce** (priority + daily budget). This is **not** the strike demo-knot desk and not R0.

| Lane | Role |
|------|------|
| **L0** | Ollama — brief, ask biographer, todos, summarize |
| **L2** | Remote specialist — hard work only (`[priority]` / `[L2]`) |
| **L3** | Human — secrets / irreversible |

Strike desk (`sovereign-mirror-scaffold` :8743) is **optional analysis** of Mag data structures. Mag brand lives here on **:8765**.

## Three doors (layman)

| Door | Do | Example |
|------|-----|---------|
| **FIND** | Get your real material | X search, exports, `research-pack` |
| **FILE** | Save to disk (bead, trail) | SessionEnd, dig leaf, FILE block |
| **LOAD** | Brief any AI cheaply | `mag.cmd context-pack` |

See [`docs/FRAMEWORK_LOAD.md`](docs/FRAMEWORK_LOAD.md) for metaphors, load order, and use cases.

## Compass

North star for operators and agents — Mycelial Republic vision, forever agent loop, v1–v10 version arc, sovereignty law:

→ [`docs/ref/MAG_MYCELIAL_REPUBLIC_COMPASS.md`](docs/ref/MAG_MYCELIAL_REPUBLIC_COMPASS.md)

Machine arc: [`configs/version_roadmap.yaml`](configs/version_roadmap.yaml) · Version index: [`docs/ref/releases/VERSION_REGISTRY.md`](docs/ref/releases/VERSION_REGISTRY.md)

## Dashboard (Body · Pulse · Days · Chat)

```powershell
# fence-owner: operator - README quickstart card. FW-11 2026-09-28; receipt: watch/inbox/fifty_wide_20260917/FW11_fence_owners.md
python main.py lab
# → http://127.0.0.1:8765/
```

| Tab | Role |
|-----|------|
| **Office** | Been → now → next |
| **Days** | Workday list + 3D bead tree (subsessions, Verkle lattice) |
| **Body** | Inbound seats (Cursor, Chat), providers, governance |
| **Pulse** | Honest activity from filed sources |
| **Chat** | Agent + **guidance queue** (deferred steer at checkpoint) |

Restart dashboard after Python API changes. Hard-refresh static assets: **Ctrl+Shift+R**.

Publish checklist: [docs/GITHUB_PUBLISH.md](docs/GITHUB_PUBLISH.md)

## Requirements

- Python 3.12+
- Ollama with `gemma:2b` (router) and `gemma4:latest` (worker/critic)
- Optional later: `nomic-embed-text` for RAG

## Setup

```powershell
# fence-owner: operator - README quickstart card. FW-11 2026-09-28; receipt: watch/inbox/fifty_wide_20260917/FW11_fence_owners.md
cd $env:USERPROFILE\Documents\projects\local_sovereign_agent
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Run

```powershell
# fence-owner: operator - README goal-run card. FW-11 2026-09-28; receipt: watch/inbox/fifty_wide_20260917/FW11_fence_owners.md
# simple goal
python main.py run "List files under memory and read locus.md"

# shorthand
python main.py "List files under ."

python main.py status
```

## Escalation handoff

When status is `escalated`:

1. Open `queue/handoff/<id>.json` (and `.md`)
2. Execute the ask in the chosen specialist seat
3. Write `queue/results/<id>.json` with `{"handoff_id","ok","summary","deliverable"}`
4. `python main.py ingest <id>`

## Product home (integral — one process)

```powershell
# fence-owner: operator - README command card. FW-11 2026-09-28; receipt: watch/inbox/fifty_wide_20260917/FW11_fence_owners.md
cd $env:USERPROFILE\Documents\projects\local_sovereign_agent
.\.venv\Scripts\Activate.ps1

# DEFAULT: watch + Mag companion + dashboard (do not also run watch separately)
python main.py lab
# → http://127.0.0.1:8765/

# Sancho boot (self-analysis; --ensure spawns lab if down)
python main.py boot
python main.py boot --ensure
# → memory/boot_report.md  +  watch/boot_latest.json
# SessionStart hook: watch/sancho_boot_hook.py (ensure=True)

# Records office — lean residual + hot registry
python main.py pack-status              # complete = residual+card+commit+leaf
python main.py migrate-lean-registry    # dossiers → residual/ + registry.jsonl
python main.py backfill-sessions        # fill incomplete (heuristic)
python main.py refresh-session-cards    # blurb+bullets only
# layout: residual/{sid}.json  registry.jsonl  derived/  knots/ + tip
# → memory/biography/kpi.json

# REST API (lab / dashboard on :8765)
# GET  http://127.0.0.1:8765/api/v1
# GET  /api/v1/health  /api/v1/registry  /api/v1/sessions  /api/v1/kpi
# GET  /api/v1/sessions/{id}/residual
# POST /api/v1/catch-up  /api/v1/ask  /api/v1/brief
# Audit: docs/AUDIT.md
# DNA: docs/DNA.md  ·  Zeitgeist: docs/ZEITGEIST.md  ·  Roadmap: docs/ORG_ROADMAP.md
# Operate tab (dashboard home): forest walk + AI feed templates + DNA
# CLI:  python main.py org-review
# API:  GET /api/v1/operator-os
```

### If you kill Mag

| What freezes | What does not |
|--------------|----------------|
| `memory/live_from_grok.md` (eyes) | The specialist chat itself (TUI keeps writing history) |
| Companion cycles (todos, escalate) | Existing dossier files on disk |
| Heartbeat → Board shows **DOWN** | Hooks may still fire SessionEnd if the seat loads them |

**Recovery:** `python main.py lab` again. Same session id **amends** the same `.md` / `.dossier.json` / `.pdf` / Verkle leaf — no duplicate session docs.

Do **not** run `main.py watch` + `main.py mag` + dashboard as three processes. Watch is baked into `lab` / `mag`.

Heartbeat: `watch/heartbeat.json`

### Local multi-model (M0 dual-local)

**Clerk** `gemma:2b` (route/judge) · **Worker** `gemma4:latest` (brief/ask/critic). Sequential load — not parallel 3×8B.

```powershell
# fence-owner: operator - README models card. FW-11 2026-09-28; receipt: watch/inbox/fifty_wide_20260917/FW11_fence_owners.md
python main.py models          # role → model + present?
python main.py multi-smoke     # MUST pass: two model ids in logs/multi_smoke_latest.json
python main.py doctor
```

Board → **Orchestrate** → **Run multi-smoke**. If smoke fails, multi-model is cosplay — fix Ollama before features.

### Research pack (scrape → clean PDF → route)

Local-first info routing: freeze the **ask + fidelity bar + sources**, run lesser models on that pack, elevate to a specialist only when needed.

```powershell
# fence-owner: operator - README research-pack card. FW-11 2026-09-28; receipt: watch/inbox/fifty_wide_20260917/FW11_fence_owners.md
python main.py research-pack `
  --ask "Summarize claims about Z from these pages; flag uncertainty." `
  --url "https://example.com/one" `
  --url "https://example.com/two" `
  --criterion "Cite URLs for every claim" `
  --criterion "Use format: answer / evidence / gaps / next move" `
  --run

# Produce pack for a specialist (you open PDF/prompt; no full chat dump)
python main.py research-pack --ask "…" --url "…" --elevate
```

Outputs: `memory/research_packs/latest.pdf` · `latest.json` · `latest.prompt.txt`

### Sovereign dispatch (auto model + local context)

```powershell
# fence-owner: operator - README dispatch card. FW-11 2026-09-28; receipt: watch/inbox/fifty_wide_20260917/FW11_fence_owners.md
python main.py dispatch "what was I doing?"
python main.py dispatch "draft a public summary of X"   # picks remote if key+budget
python main.py dispatch "refactor the auth module" --dry  # → specialist seat
python main.py hermes-status
python main.py dispatch "via hermes draft a public outline" --dry  # → hermes seat
```

Keeps **history local**, sends **context-pack + goal** only, chooses provider by job + remaining quota.

### Multi-platform (Claude / OpenAI / Gemini / DeepSeek / Llama / …)

Config: `configs/providers.yaml` (models + **your** quota limits + reset period).  
Keys live in **`.env`** (gitignored). Mag loads them on every `main.py` start.

```powershell
# fence-owner: operator - README scaffold card. FW-11 2026-09-28; receipt: watch/inbox/fifty_wide_20260917/FW11_fence_owners.md
# seed XAI from scaffold if present
python scripts/sync_env_from_scaffold.py
# paste other keys into .env
notepad .env
# or
.\scripts\edit_env.ps1

python main.py providers   # see configured: true/false
python main.py quota
```

(Truncation note: this file ended mid-sentence on the bare word "Also" after
its 2026-08-09 edit (de7bb85fe), a defect proven 2026-09-28 in
watch/inbox/burn_reset_20260927/flash50/s2-17.md; the lost tail is not
recoverable from git history, so the dangling word is removed and this closing
sentence marks the truncation, added 2026-09-29 by the gala wave5-repair
old-files lane.)
