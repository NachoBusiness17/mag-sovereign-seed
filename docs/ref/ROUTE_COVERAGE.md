# ROUTE COVERAGE — CLI surface vs REST surface

**Generated:** 2026-08-08
**Method:** regex scan of `main.py` (`sub.add_parser("X")`) for the CLI surface and
`dashboard/rest.py` (`("VERB", "/path", handler)`) for the REST surface. CLI→REST
matching is heuristic (token overlap); treat the **"no twin"** list as reliable and
the **"has twin"** list as confirmed only where the name/path matches directly or
was built deliberately.

**Why this matters:** the framework's truth layer is the filesystem/process/cadence
(law: files are truth). REST is a *control/view* surface — a uniform HTTP way to drive
and read the framework. Operations with **no REST twin** must be run via terminal/CLI,
which is the operator-friction we're eliminating. Closing gaps = thin REST wrappers
that call the existing module functions and return JSON (no logic duplication).

---

## The numbers
- **CLI commands:** 125
- **Unique REST paths:** ~249
- Coverage is **uneven**: REST is a partial twin, not a full mirror.

---

## No REST twin — the gap (must use CLI today)

### Core operational (highest value to close)
| CLI | Module | Notes |
|---|---|---|
| `run` | orchestrator | run a goal — **POST /api/v1/run** ✅ |
| `plan` | planner | planning gate |
| `ghost` | mag/ghost.py | sense / deploy / catalog / swarm — **GET/POST /api/v1/ghost** ✅ |
| `governor` | mag/governor.py | governor cycle |
| `fkb` | mag/failure_kb.py | stats / search / record — **/api/v1/failure** (report) + **?view=search** ✅ |
| `spec-gate` | mag/spec_gate.py | integrity gate — **GET/POST /api/v1/spec-gate** ✅ |
| `job-floor` | mag/job_floor.py | designation manager |
| `spider` | mag/spider.py | meta-supervisor |
| `pro-library` | mag/pro_library.py | aimbot |
| `resonance` | mag/resonance.py | corpus lens |
| `tesuji-shell` | mag/tesuji_shell.py | move capture |
| `trail` | mag/run_trail.py | run trails |
| `cast` | mag/desk_observer.py | agent-as-judge |
| `clippy` | mag/clippy.py | next-action |
| `conductor` | mag/conductor.py | multi-agent conductor |
| `guard` | mag/guard.py | failsafe loop |
| `steward` | mag/steward.py | steward cycle |
| `switchboard` | mag/switchboard.py | coordination |
| `loop-audit` | mag/loop_audit.py | loop health |
| `run-worth` | mag/run_worth.py | behavioral scoring |

### Housekeeping / one-off
`build-audit` · `caveman-audit` · `ponytail-audit` · `cost-sim` · `cross-version` ·
`env` · `field-steal` · `knot-evolution` · `ollama` · `release` · `roadmap-run` ·
`vast-train` · `workshop`

---

## Strong existing twins (already RESTful)
| CLI | REST |
|---|---|
| `janitor` | `/api/v1/janitor` (GET/POST) |
| `orphan` | `/api/v1/orphan` (GET/POST) |
| `ops-graph` | `/api/v1/graph/ops` |
| `live-feed` | `/api/v1/live-feed` |
| `drainer-stats` | `/api/v1/drainer/stats` |
| `vscode-feed` | `/api/v1/behavior/vscode` |
| `failure` (report) | `/api/v1/failure` (POST) + `?view=stats\|recurring\|search` |
| `run` | `/api/v1/run` (GET/POST) |
| `ghost` | `/api/v1/ghost` (GET/POST) |
| `spec-gate` | `/api/v1/spec-gate` (GET/POST) |
| `seats` | `/api/v1/seats` + register/heartbeat/unregister |
| `decide` | `/api/v1/decide` |
| `route` | `/api/v1/route` |
| `power` | `/api/v1/power` + stop/start |
| `factory-machine` | `/api/v1/factory-machine` |
| `improve` | `/api/v1/improve/cloud` + `/cycle` |
| `skill-ledger` | `/api/v1/skill-ledger` + record/labeled-row |
| `ideas` | `/api/v1/ideas` |
| `verkle-knots` | `/api/v1/verkle-knots/{id}` |
| `token-chain` | `/api/v1/token-chain` |
| `coordinate` | `/api/v1/coordinate` |
| `coding-session` | `/api/v1/coding-session` |
| `autopilot` | `/api/v1/autopilot` |
| `nervous` | `/api/v1/nervous` |
| `system-map` | `/api/v1/system-map` |
| `overseer` | `/api/v1/overseer/manifest\|events\|session` |
| `seats/steer` | `/api/v1/agents/{id}/steer` |

---

## Heuristic caveat (false positives to ignore)
Token-overlap matching flagged a few as "matched" that are NOT real twins:
- `compose-status` / `hermes-status` → unrelated agent steer-status route
- `state-snapshot` → agent state-snapshot route (different meaning)
- `verkle-audit` → `verkle-knots/{id}` (weak)
- `research-pack` → `context-pack` (weak)

These are in the **gap** list semantically; do not treat them as covered.

---

## Recommended priority to close gaps (highest pain first)
1. **`ghost`** — sense/catalog/deploy (module exists; thin twin)
2. **`fkb`** — search/stats/record (report endpoint added; add query/read-back)
3. **`run` / `plan`** — the two you'd most want to drive remotely
4. **`spec-gate` / `job-floor`** — integrity gates
5. **`spider` / `pro-library`** — self-improve + aimbot

**Pattern for each twin:** add a handler in `dashboard/rest.py` that imports the
existing module function and returns `200, result` (plus `_err` on bad input), and
register `GET`/`POST` routes in `ROUTES`. No new logic — reuse the module.

---

## Open items surfaced by this audit (restful doctor)
Reported via `/api/v1/failure` (kind=ops) as they recur:
- dashboard restart needed to load newly-added routes
- autorun loop restart needed to run new cadence jobs (janitor/orphan)
- window reload needed to show extension section views
- CLI-only core ops have no REST twin (this doc)
