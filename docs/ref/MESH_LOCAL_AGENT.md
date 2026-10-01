# Mesh forest — local agent deep dive (operator)

**Commitment:** `mesh-local-agent-001`  
**Job:** Pull all mesh clones onto disk, then run a **local tool-using agent** (like cloud Cursor) over them to reason about integration — contracts only, not app cosplay.

---

## Are the repos on my PC?

**Not from `git pull` alone.** Upstream trees live under `mine/raw/mesh_comm/` and that path is **gitignored** (`.gitignore` → `mine/raw/**`).

| State | What you have |
|-------|----------------|
| Only cloned Mag repo | Manifest + spores + pull scripts — **no** Bitchat/Bridgefy/Briar source |
| Ran `scripts\pull_mesh_comm_repos.cmd` | **13 local clones** (permissionlesstech 3 · Bridgefy 6 · Briar 4) |
| Ran `scripts\home_sync.cmd` | Branch + both mesh + gstdcoin pulls + doctor |

**Verify on Windows:**

```powershell
cd $env:USERPROFILE\Documents\projects\local_sovereign_agent
(Get-ChildItem -Recurse mine\raw\mesh_comm -Directory -Filter .git).Count
# expect 13
```

If count is 0 or low → run `scripts\home_sync.cmd` or `scripts\pull_mesh_comm_repos.cmd`.

---

## What Mag already ran (cloud scout)

`scripts/mesh_comm_ilap_run.sh` is a **shallow scout** — 3 repos, docs-heavy `field-steal`, one whitepaper pack, spores filed under `docs/ref/spores/mesh/`.

That is **not** a full architecture pass over all 13 codebases.

---

## Deep dive — all repos, local agent

### One command (recommended)

**Windows:**

```powershell
cd $env:USERPROFILE\Documents\projects\local_sovereign_agent
scripts\mesh_comm_deep_dive.cmd
```

**Linux / cloud:**

```bash
./scripts/mesh_comm_deep_dive.sh
```

This:

1. Pulls / refreshes all 13 clones  
2. `field-steal` on each repo (docs + architecture markdown)  
3. Writes `memory/research_packs/mesh_forest/INTEGRATION_BRIEF.md` (paths, spores, starter goals)  
4. Prints the next agent command  

### Chat interface for agents (local Cursor-like)

Mag has a **tool-using REPL** — reads files under repo root (including `mine/raw/mesh_comm/`), lists dirs, writes dig leaves:

```powershell
.\mag.cmd agent --provider deepseek
# or local-only:
.\mag.cmd agent --provider ollama
```

**Starter goal** (paste after deep dive):

```text
Read memory/research_packs/mesh_forest/INTEGRATION_BRIEF.md and docs/ref/spores/mesh/.
For each org (permissionlesstech, bridgefy, briar): summarize transport architecture,
how messages route, and what contracts Mag should steal into conductor/switchboard/pigeonhole.
Output a FEATURE_COMPOSE-style integration map — wire only, no SDK merge, willing L3 enroll.
Use read_file on mine/raw/mesh_comm/* source (MessageRouter, MeshService, sync layers).
```

**One-shot:**

```powershell
.\mag.cmd agent --provider deepseek -q "Compare Bitchat MessageRouter vs Bridgefy transmission modes vs Briar sync-without-server; Mag integration contracts only"
```

**Other local seats:**

| Command | Role |
|---------|------|
| `.\mag.cmd ask "…"` | Biographer over memory/briefs — fast, no file tools |
| `.\mag.cmd lab` | Office UI `:8765` — health, history, janitor context |
| `.\mag.cmd research-pack --ask "…" --url "…" --run` | Scrape URL + local Ollama answer (whitepapers) |
| `.\mag.cmd improve --deep` | Ranked practice tickets — not mesh-specific |

---

## ILAP framing (research before BUILD)

```text
P0  ILAP proposal     docs/ref/proposals/ILAP-mesh-steal-001.md
P1  deep dive         scripts/mesh_comm_deep_dive.cmd
P1  agent session     mag.cmd agent (integration map on disk)
P2  aim               python scripts/routing_smoke.py
P3  eval              wire / defer — no Bridgefy AAR in Mag core
```

**Law:** steal **contracts** (routing, TTL, willing relay, transmission enum) — never ship foreign UI or silent background mesh.

---

## Related

| Doc | Role |
|-----|------|
| `MESH_COMM_REPOS_INDEX.md` | 13 targets + org maps |
| `MAG_v5_MESH_FOREST.md` | v5 pipe vision |
| `MAG_ILAP_PROTOCOL.md` | Research-before-BUILD ritual |
| `HOME_PC_SYNC.md` | Windows sync from cloud branches |
