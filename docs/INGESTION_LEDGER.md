# MAG ingestion ledger

**Status:** active architectural inventory  
**As of:** 2026-08-06  
**Rule:** Source names are canonical. A file or CLI entry point is not proof of reliable runtime behavior.

## Status vocabulary

- **Implemented:** concrete code and a callable entry point exist.
- **Partially implemented:** meaningful code exists, but an acceptance gate is open.
- **Referenced:** doctrine or plans describe it; implementation has not been established.
- **Stubbed:** an interface or placeholder exists without the promised behavior.
- **Unlocated:** named by doctrine, but no source implementation has been traced.

## Concept ledger

| Name | Purpose | Source files | Runtime | Doctrine | Related systems | Confidence | Open questions | Implementation status | Future work |
|---|---|---|---|---|---|---|---|---|---|
| Residual DNA | Canonical durable record of a completed session | `docs/DNA.md`, `mag/registry.py`, `mag/biography.py`, `mag/session_card.py` | Session close writes residual/card/registry artifacts | Memory survives models and processes | Verkle, context pack, bonds | High | Are all crash paths backfilled? | Implemented | Verify crash recovery and portable restore |
| Verkle | Continuity, provenance, and portable witness chain | `docs/DNA.md`, `mag/verkle_knot.py`, `mag/verkle_audit.py`, `memory/verkle_tip.json` | Session leaves advance the session-only tip; audit detects gaps | One cold vertex; history honesty | Residual, trails, packs | High | Which relationships are cryptographic versus operational metaphor? | Implemented, runtime audit partial | Document exact guarantees and restore drill |
| Run trail | Warm execution history for open and closed work | `mag/run_trail.py`, `docs/ref/run_trail_lattice.md` | Records actions and closes into related-run edges | Chat is heat; FILE is durable | Bonds, context pack, factory | High | Are all worker exits terminally recorded? | Implemented | Test interrupted-worker closure |
| Bonds | Reintroduce relevant unfinished work into later sessions | `mag/bonds.py`, `memory/bonds_active.md` | Closed runs contribute next-session edges | Learning persists across sessions | Trails, packs | Medium-high | How are stale bonds retired? | Implemented | Audit ranking and retirement behavior |
| Context pack | Minimum-token briefing for a stateless seat | `mag/context_pack.py`, `memory/context_pack_latest.md` | Builds clipped local file context for handoff | Pack-first; never send full chat | Router, tiers, remote seats | High | Are pack contents themselves correctly redacted for every mode? | Implemented; remote tier gate passed | Audit redaction quality independently |
| Router / dispatch | Select the cheapest safe seat for work | `mag/router.py`, `mag/dispatch.py`, `configs/lanes.yaml` | Classifies depth and routes with seat constraints | Local first; frontier scarce | Context pack, FKB, orchestrator | High | Is there still a competing legacy route path? | Implemented, reconciliation pending | Run routing smoke and retire ambiguity |
| Orchestrator | Queue, spawn, supervise, and reap bounded work | `mag/orchestrator.py`, `mag/governor_autorun.py` | Manages tasks and worker lifecycle | One orchestrator; no agent-chat throne | Router, pigeonhole, trails | High | Does every task produce a terminal artifact? | Partially implemented | Prove handoff-result-ingest round trip |
| Failure KB | Convert failures into reusable remedies | `mag/failure_kb.py` | Records failure/remedy evidence for later routing | Expensive mistakes should become capability | Router, improve, audit | Medium-high | Are remedies automatically evaluated before reuse? | Implemented, merge history unresolved | Verify gate and remedy selection |
| Improve loop | Scout, evaluate, and propose behavioral changes | `mag/improve.py`, `configs/improve.yaml`, `memory/improve/` | Produces candidates; human promotion applies changes | No silent self-modification | FKB, training events, promote | High | Which candidate classes can affect routing? | Implemented | Audit promotion boundaries |
| Skills | Reusable verified behavioral transformations | `mag/skill_seat.py`, `docs/templates/MODEL_TESUJI.md`, `configs/local_playbooks.yaml` | Selects playbooks and runs skill gates | A skill is more than a prompt | Improve, audit, local models | Medium | Which skills include retirement and promotion criteria? | Partially implemented | Complete skill contract audit |
| Desk | Visible calibration surface for Local/DeepSeek handoffs | `mag/agent_desk.py`, `mag/desk_dialogue.py`, `mag/desk_conductor.py`, `dashboard/static/index.html` | Canvas-backed turns and conductor steps | Prove slow-to-fast before fast-to-fast | Local adapter, DeepSeek, trust ladder | High | Can Tier 1 pass three consecutive runs? | Partially implemented; Trust Tier 0 | Repair baseline and repeat trust probes |
| DeepSeek seat | Cheap long-context coding and problem escalation | `models/providers.py`, `mag/agent_cli.py`, `mag/desk_conductor.py` | Remote provider can perform bounded turns and tool work | Cheap builder; raise deltas rather than re-plan | Factory, Desk, context pack | High | Has one full frozen-spec run been recorded? | Partially implemented | Complete and gate a real DeepSeek build |
| Local intelligence | Always-on cheap observation, compression, and scut | `llm.py`, `mag/desk_local_adapter.py`, `configs/lanes.yaml` | Ollama models serve local Desk and janitor work | Local first; private data stays local | Desk, router, packs | High | Can real Ollama hand off exact bounded intent reliably after the process is proven? | Process simulation passes 3× 12/12; hardware lane remains unverified | Diagnose Ollama/model/hardware separately, then reach Desk Trust Tier 1 |
| Factory | Plan, freeze, build, audit, and file a coding episode | `docs/ref/MAG_BUILD_PIPELINE.md`, `mag/factory_machine.py`, `mag/coding_session_runner.py` | Runs sprint machinery and produces reports/retrospectives | Static spec; stateless builder; deterministic inspector | DeepSeek, Cursor, build audit | High | Was pilot 1 truly frozen before build? | Partially implemented | Run pilots 2 and 3 without chat re-explanation |
| Build audit | Structured terminal evidence for a factory build | `mag/build_audit.py`, `tests/test_build_audit.py`, `memory/factory/build_audit-factory-audit-json.json` | Writes `build_audit.v1` and training event | Verification must outlive model claims | Factory, release gates | High | Artifact contains no recorded commands; is that sufficient evidence? | Implemented; pilot artifact passed | Strengthen evidence requirements |
| Freeze gate | Refuse build work without a frozen BUILD specification | `configs/releases.yaml`, `docs/ref/MAG_NEXT_CODING_RUN.md` | No proven enforcement located yet | No implementation from conversational intent alone | Factory, conductor, orchestrator | High | Where should the single enforcement boundary live? | Referenced / partially scaffolded | Factory pilot 2 |
| Training events | Unified behavioral episode labels | `mag/training_events.py`, `memory/training/events.jsonl` | Emits lifecycle, skill, release, and factory events | Expensive work must become reusable learning | Factory, improve, future distillation | High | Are events complete and evaluation-ready? | Implemented, quality unverified | Validate joins, redaction, and label coverage |
| Distillation | Convert verified episodes into improved local capability | `configs/training_patterns.yaml`, training references | No complete verified promotion-to-weights cycle established | Models temporary; learning permanent | Training events, local models, promote | Medium | What is the first accepted local capability delta? | Partially implemented / referenced | Define eval-first distillation gate |
| Office dashboard | Owner-facing viewport over MAG | `dashboard/`, `docs/HOW_TO_MAG_DASHBOARD.md` | Serves port 8765 with many operational surfaces | Viewport must not become DNA | Residual, Desk, Stack, Ideas, Days | High | Which actions work in current runtime? | Partially implemented; usability broken | Runtime-control inventory and core-four consolidation |
| Desktop entry | Human doorway into MAG | `scripts/install_desktop_shortcuts.ps1`, launcher `.cmd` files | One main `MAG` shortcut now opens Desk; legacy tools retained in `MAG Tools` | One understandable door, replaceable workers behind it | Office, native services, Docker | High | Should Office or Desk be the canonical landing surface? | Partially refined | Build one explicit launcher/control center |
| Sovereign Mirror | Human continuity/presentation layer named by doctrine | `docs/ref/MIRROR_PRESENTED.md`, mirror launcher references | Optional mirror service is started by power command when configured | User remains owner; presentation is not DNA | Office, residual | Medium | Exact current runtime boundary and necessity? | Partially implemented | Trace independently before product claims |
| Governor | Enforce gates, pauses, tiers, and autorun policy | `mag/governance.py`, `mag/governor_autorun.py` | Applies operator-active and policy checks | Human L3 on irreversible action | Autorun, router, tier law | High | Are all remote and destructive paths governed? | Partially implemented | Build policy coverage matrix |
| Conductor | Phase and seat guidance for coordinated work | `mag/conductor.py`, `mag/desk_conductor.py` | Heuristic conductor and separate Desk conductor both exist | Coordination without a second throne | Router, Desk, factory | High | Are two conductors clearly bounded and named? | Partially implemented | Clarify contracts; evaluate before training |
| Spider | Detect stalls and propose bounded intervention | `mag/spider.py` | Research CLI and switchboard hooks exist | Observe before intervention | Orchestrator, FKB, switchboard | Medium-high | Has intervention improved outcomes in measured runs? | Research implementation | Eval before proactive use |
| Resonance | Surface relevant prior material and patterns | `mag/resonance.py` | Research CLI exists | Past soil should inform current work | Verkle, context pack, Grove | Medium | Precision and token-cost evidence? | Research implementation | Build retrieval evaluation |
| Grove | Human-readable skill/history layer | `mag/grove.py`, v3 backlog | Research CLI exists | System should teach, not only execute | Training events, factory, resonance | Medium | Is it useful memory or decorative theater? | Research implementation | Validate against learning outcomes |

## Open questions

Ranked by architectural importance:

1. What exact evidence supersedes the historical RUN A PR-merge requirement on the current branch?
2. Can T0/T1 refusal be demonstrated across every remote entry point, not only the primary router?
3. Can Local produce exact handoff intent three times consecutively without echo, drift, or truncation?
4. Where is the single authoritative freeze-gate enforcement boundary?
5. What deterministic evidence must a `build_audit.v1` contain before it can justify promotion?
6. What is the first measurable example of a frontier lesson becoming improved local capability?
7. Which dashboard and desktop actions are owner features versus internal laboratory instruments?
8. How are obsolete bonds, skills, remedies, and roadmap items retired without erasing provenance?

## Maintenance rule

Update this ledger when runtime evidence changes a classification. Do not promote an item merely because a file, button, or plan exists.
