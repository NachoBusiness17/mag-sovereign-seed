"""Framework map — authoritative, functional grouping of the whole framework.

The VS Code "Framework Map" pane is fed by this module, not by a local scanner
in the extension. This is the framework's own rule system owning the map:

  - Scans the real command surface (main.py subcommands, mag/ + tools/ modules,
    .cmd launchers, dashboard REST routes, providers.yaml) from code.
  - Regroups every entry BY FUNCTION (Steer / Decide / State / Learn / Run /
    Ops / Agents / Launch / Routes / Providers) with a curated one-line help,
    a longer description, and an example showing how it's used.
  - render() always recomputes a LIVE snapshot so the map never goes stale.
  - persist() appends a durable copy to memory/graph/framework_map.json.

Wired in (the automation):
  REST   GET /api/v1/framework/map -> render()  (dashboard/rest.py)
  Loop   registered in mag/loops_registry.py
  Cadence MAG_MAP_EVERY ticks in mag/governor_autorun.py -> refresh+persist

CLI:
  python -m mag.framework_map               # render as a small table
  python -m mag.framework_map --json        # machine-readable payload
  python -m mag.framework_map --ingest      # render + append durable copy
  python -m mag.framework_map --compile     # validate seams -> memory/runs/framework_map/report.md
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except ImportError:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCHEMA = "framework_map.v1"
GRAPH_DIR = ROOT / "memory" / "graph"
MAP_PATH = GRAPH_DIR / "framework_map.json"
REPORT_DIR = ROOT / "memory" / "runs" / "framework_map"
REPORT_PATH = REPORT_DIR / "report.md"

# ---------------------------------------------------------------------------
# Functional groups — the map is regrouped BY FUNCTION, not by file kind.
# ---------------------------------------------------------------------------
GROUPS: list[dict[str, str]] = [
    {"id": "steer",    "icon": "🎛️", "label": "Steer",    "blurb": "Shape the running agent — ghost, inbox, skills, aimbot"},
    {"id": "decide",   "icon": "🧭", "label": "Decide",   "blurb": "Routing, tiers & escalation — the router's judgment"},
    {"id": "state",    "icon": "🗃️", "label": "State",    "blurb": "Persistent memory — piles, verkle, ledger, case law"},
    {"id": "learn",    "icon": "📈", "label": "Learn",    "blurb": "Self-improvement — fold outcomes into better defaults"},
    {"id": "run",      "icon": "⚙️", "label": "Run",      "blurb": "Pipeline & execution — queue, jobs, spec-gated work"},
    {"id": "ops",      "icon": "🩺", "label": "Ops",      "blurb": "Health & observability — watch, diagnose, graph"},
    {"id": "agents",   "icon": "🤝", "label": "Agents",   "blurb": "Multi-agent orchestration — desks, seats, arenas"},
    {"id": "launcher", "icon": "🚀", "label": "Launch",   "blurb": "One-click .cmd launchers"},
    {"id": "route",    "icon": "🔌", "label": "Routes",   "blurb": "Dashboard REST endpoints"},
    {"id": "provider", "icon": "🧠", "label": "Providers", "blurb": "Model providers in providers.yaml"},
]

# Curated metadata keyed by "<kind>:<name>". Falls back to assign_group() +
# scanned help for anything not listed here.
CURATED: dict[str, dict[str, str]] = {
    # ── STEER ────────────────────────────────────────────────────────────
    "mag:ghost": {
        "group": "steer",
        "help": "Silent situational steer — sense state, deploy test vectors",
        "desc": "Senses the agent's situation (CURRENT.md, briefs, agent_state, VS Code context), matches context, and deploys contextual test vectors through operator_inbox. Gated: suppresses auto-deploy during unattended autonomy runs or when the operator is active.",
        "example": "python -m mag.ghost --sense\npython -m mag.ghost --deploy \"Check FKB before retrying\"",
    },
    "mag:steer_bridge": {
        "group": "steer",
        "help": "Push guidance into the running agent via operator_inbox",
        "desc": "Commits a guidance message to operator_inbox; the agent drains it at its next checkpoint (_absorb_operator_inbox). Idempotent drop-file push with --sync for reliable delivery.",
        "example": "python main.py steer-agent \"Prefer the spec over the tier\" --sync",
    },
    "mag:operator_inbox": {
        "group": "steer",
        "help": "Operator breadcrumbs the agent absorbs at checkpoints",
        "desc": "The interference channel: operator notes/steers queued here get absorbed by the running agent every checkpoint. The seam ghost and steer_bridge both inject through.",
        "example": "python -m mag.operator_inbox commit_guidance --text \"<steer>\"",
    },
    "mag:pro_library": {
        "group": "steer",
        "help": "Aimbot — transferable winning moves injected like a scope",
        "desc": "SENSE (state) → MATCH (signature overlap) → INJECT (steer/skill/spec/tip via operator_inbox) → LEARN (outcome). Seeded with discovered wins; fires proven moves automatically.",
        "example": "python main.py pro-library\npython main.py pro-library --list",
    },
    "mag:tesuji_shell": {
        "group": "steer",
        "help": "Capture a winning move as reusable case law",
        "desc": "Records a proven move so pro_library can aim it later. The tesuji is the loop: measure → fold → apply.",
        "example": "python -m mag.tesuji_shell capture --move \"<signature>:<inject>\"",
    },
    "mag:skill_drop": {
        "group": "steer",
        "help": "Drop a skill into the running agent's context",
        "desc": "Injects a skill/spec via the operator_inbox seam so the next checkpoint inherits it.",
        "example": "python -m mag.skill_drop --skill research_sprint",
    },
    "mag:intention_brief": {
        "group": "steer",
        "help": "Write the intent the next run should absorb",
        "desc": "Composes an intention brief the agent consumes on start — the 'frozen spec' that makes a cheap tier render well.",
        "example": "python -m mag.intention_brief --goal \"<goal>\"",
    },
    "mag:clippy": {
        "group": "steer",
        "help": "Propose the next action from folded choices",
        "desc": "Suggestions that fold recorded choices back into better proposals.",
        "example": "python -m mag.clippy",
    },
    "mag:compass": {
        "group": "steer",
        "help": "Constitutional compass — route a question against the law",
        "desc": "Binds to Mycelial Republic constitution; checks a goal against T0–T3 tiers and fork equality.",
        "example": "python -m mag.compass \"<question>\"",
    },
    "tools:pupeteer_gauntlet": {
        "group": "steer",
        "help": "Prove steering works — run local models through tests they're too dumb for",
        "desc": "Control vs puppeteer arms, all real model calls. Probes: memory-edit flip, spec_gate drift block, job_floor walking, aimbot fire, silent steer. Report → memory/runs/pupeteer/.",
        "example": "python tools/pupeteer_gauntlet.py --live",
    },
    "tools:steer_compare": {
        "group": "steer",
        "help": "A/B two steer vectors against the same state",
        "desc": "Measures which steer changes the outcome, per steer_telemetry policy.",
        "example": "python tools/steer_compare.py --a \"<v1>\" --b \"<v2>\"",
    },
    # ── DECIDE ───────────────────────────────────────────────────────────
    "mag:decision_framework": {
        "group": "decide",
        "help": "Compass + case law + behavioral leaves → surface_tips() / decide()",
        "desc": "The framework decision channel. Combines compass, skill_ledger case law, and behavioral leaves to surface tips and make decisions. Owns the loop-escalation ladder (ollama → deepseek → overmind → grok).",
        "example": "python -m mag.decision_framework decide --goal \"<goal>\"",
    },
    "mag:router": {
        "group": "decide",
        "help": "Heuristic tier/route + model soft decisions → final route+seat",
        "desc": "The router channel. Decides provider/tier and seat. router/supervisor.py is the heuristic gate that produces the final route.",
        "example": "python -m mag.router --goal \"<goal>\"",
    },
    "mag:supervisor": {
        "group": "decide",
        "help": "Router supervisor — authoritative route+seat decision",
        "desc": "Heuristic routing gate (router/supervisor.py) that picks provider, tier, and seat.",
        "example": "python -m mag.supervisor --goal \"<goal>\"",
    },
    "mag:fork_router": {
        "group": "decide",
        "help": "Route questions to the right fork",
        "desc": "Decides which fork/strategy handles a question.",
        "example": "python -m mag.fork_router --goal \"<goal>\"",
    },
    "mag:routing_concert": {
        "group": "decide",
        "help": "Concert routing — multiple signals into one route",
        "desc": "Coordinates several routing signals into a single route decision.",
        "example": "python -m mag.routing_concert",
    },
    "mag:rails": {
        "group": "decide",
        "help": "Hard rails — guard which routes/seats are allowed",
        "desc": "Enforces routing constraints so the agent stays on allowed tracks.",
        "example": "python -m mag.rails",
    },
    "tools:tier_probe": {
        "group": "decide",
        "help": "Right-size the tier empirically — A/B, objective scoring",
        "desc": "Tests routing assumptions: 2 task shapes × 4 tiers, real model calls, objective scoring (no LLM judge), real prices. Adopted the 'test the assumption' ledger.",
        "example": "python tools/tier_probe.py --design --exec",
    },
    "mag:temperature_stack": {
        "group": "decide",
        "help": "Temperature by task shape",
        "desc": "Sets sampling temperature per task kind for stable output.",
        "example": "python -m mag.temperature_stack --kind research",
    },
    "mag:refine_chain": {
        "group": "decide",
        "help": "Refine an answer through successive cheap passes",
        "desc": "Chains cheap refinements instead of one expensive ask.",
        "example": "python -m mag.refine_chain --goal \"<goal>\"",
    },
    # ── STATE ────────────────────────────────────────────────────────────
    "mag:state_snapshot": {
        "group": "state",
        "help": "In-the-moment state classification → state_summaries.jsonl",
        "desc": "capture_summary(goal, outcome, tier, kind, lessons) appends a structured, deduped row to the pile — the training + posterity feed.",
        "example": "python -m mag.state_snapshot capture --goal \"<goal>\" --outcome ok",
    },
    "mag:verkle_audit": {
        "group": "state",
        "help": "Audit the verkle state tree, fix drift",
        "desc": "Runs a full audit and repairs the verkle tree (freeze/check/gate a file's sha256 base before a spec applies).",
        "example": "python -m mag.verkle_audit --full\npython -m mag.verkle_audit --fix",
    },
    "mag:verkle_knot": {
        "group": "state",
        "help": "Fold a leaf into the verkle knowledge knot",
        "desc": "Writes a reasoning leaf into the tree so cheap models inherit strong output.",
        "example": "python -m mag.verkle_knot --leaf \"<nugget>\"",
    },
    "mag:context_pack": {
        "group": "state",
        "help": "Compose the frozen context pack for a model",
        "desc": "Builds the byte-identical prefix (system + bootloader + manifest + TIP + decision-DAG) so any tier reads the same state at cache-hit price.",
        "example": "python -m mag.context_pack --goal \"<goal>\"",
    },
    "mag:memory_events": {
        "group": "state",
        "help": "Log memory events (read/write/fold)",
        "desc": "Tracks what entered/exited memory for auditing and resonance.",
        "example": "python -m mag.memory_events",
    },
    "mag:training_events": {
        "group": "state",
        "help": "Emit labeled training rows",
        "desc": "Feeds the training pipeline with real decisions.",
        "example": "python -m mag.training_events",
    },
    "mag:failure_kb": {
        "group": "state",
        "help": "Failure knowledge base — signatures + remedies",
        "desc": "Stores failure signatures and maps them to remedies (FKB). The anti-cheat pattern detector.",
        "example": "python -m mag.failure_kb --match \"<signature>\"",
    },
    "mag:run_trail": {
        "group": "state",
        "help": "Trail of runs — what happened, when, with what cost",
        "desc": "Durable run history; the L1 self-improvement layer.",
        "example": "python -m mag.run_trail --recent",
    },
    "mag:run_worth": {
        "group": "state",
        "help": "Score whether a run was worth it",
        "desc": "Behavioral scoring of a run's value → feeds skill_ledger.",
        "example": "python -m mag.run_worth --run <id>",
    },
    "mag:skill_ledger": {
        "group": "state",
        "help": "Case law ledger — record decisions + labeled rows",
        "desc": "The right-sizing counter: record_decision (case-law pairs) + record_labeled_row (training rows) + progress(). Targets 1000 decisions / 5000 labeled rows.",
        "example": "python main.py skill-ledger --progress",
    },
    "mag:idea_graph": {
        "group": "state",
        "help": "Map ideas into a knowledge graph",
        "desc": "Builds an idea graph from packs and training rows; under-coverage drives next research topics.",
        "example": "python -m mag.idea_graph --rebuild",
    },
    "mag:resonance": {
        "group": "state",
        "help": "Corpus lens — echo what's relevant to the goal",
        "desc": "Cross-walks the current goal against historical behavior to surface resonance.",
        "example": "python -m mag.resonance --goal \"<goal>\"",
    },
    "tools:pile_classify": {
        "group": "state",
        "help": "Long overnight job — drain the pile, classify with a local model",
        "desc": "Drains state_summaries, classifies each with a LOCAL model (default gemma4), folds into skill_ledger + training_rows. Idempotent by id. Built for scheduler/downtime.",
        "example": "python tools/pile_classify.py --limit 50",
    },
    "tools:classify_corpus": {
        "group": "state",
        "help": "Auto-producer — bulk classify the corpus into labeled rows",
        "desc": "Local bulk classify (gemma4) + deepseek-v4-flash sample audit → labeled training rows.",
        "example": "python tools/classify_corpus.py",
    },
    # ── LEARN ────────────────────────────────────────────────────────────
    "mag:improve_loop": {
        "group": "learn",
        "help": "Behavioral compounding — L1→L4 self-improvement loop",
        "desc": "L1 files trails, L2 scores training_events/FKB into candidates, L3 steps into RUN sheets/factory config, L4 talks via Grove poems and office cards.",
        "example": "python -m mag.improve_loop",
    },
    "mag:behavioral_synth": {
        "group": "learn",
        "help": "Synthesize behavioral themes into a daily leaf",
        "desc": "Turns behavioral events into a daily synthesized leaf.",
        "example": "python -m mag.behavioral_synth --day today",
    },
    "mag:behavior_catch": {
        "group": "learn",
        "help": "Catch behavior events for scoring",
        "desc": "Logs behavioral events (pro_fire/pro_learn, fake_success) that feed scoring.",
        "example": "python -m mag.behavior_catch --event <event>",
    },
    "mag:grove": {
        "group": "learn",
        "help": "Talk back — Grove poems / office cards",
        "desc": "The L4 'talk' layer that narrates what the loop learned.",
        "example": "python -m mag.grove --poem",
    },
    "mag:remedy": {
        "group": "learn",
        "help": "Apply the remedy for a known failure signature",
        "desc": "Maps an FKB signature to the fix and applies it.",
        "example": "python -m mag.remedy --signature <sig>",
    },
    "mag:attention_ranker": {
        "group": "learn",
        "help": "Rank what deserves attention next",
        "desc": "Prioritizes candidates from scoring for the next step.",
        "example": "python -m mag.attention_ranker",
    },
    "mag:token_economy": {
        "group": "learn",
        "help": "Track token spend across tiers",
        "desc": "Measures token/cost so the cheap-window doctrine is enforced with data.",
        "example": "python -m mag.token_economy --report",
    },
    "mag:cost_ledger": {
        "group": "learn",
        "help": "Ledger of cost per run/provider",
        "desc": "Records real cost so tier decisions are price-aware.",
        "example": "python -m mag.cost_ledger --recent",
    },
    "mag:research_director": {
        "group": "learn",
        "help": "Direct research — pick topics from under-coverage",
        "desc": "Selects the next research topic from idea-graph gaps.",
        "example": "python -m mag.research_director --next",
    },
    "tools:topic_research": {
        "group": "learn",
        "help": "Research a topic → packs → idea graph + training rows",
        "desc": "Drives a research topic through pack classification into the idea graph.",
        "example": "python tools/topic_research.py --topic \"<topic>\"",
    },
    # ── RUN ──────────────────────────────────────────────────────────────
    "mag:orchestrator": {
        "group": "run",
        "help": "Core orchestrator — queue, drain, reconcile",
        "desc": "The drainer: pulls from the FIFO queue, runs agents, reaps stale/completed pids, reconciles the queue. The heart of the sovereign loop.",
        "example": "python -m mag.orchestrator drain-once",
    },
    "mag:job_floor": {
        "group": "run",
        "help": "Designation manager on top of the orchestrator",
        "desc": "States designated→claimed→executing→verifying→done|needs_escalate|stuck. Watchdog: stuck_jobs(max_s). The sandbox/containment layer.",
        "example": "python main.py job-floor --status",
    },
    "mag:spec_gate": {
        "group": "run",
        "help": "Wrong-offset gate — freeze/check/gate a file before applying a spec",
        "desc": "Blocks blind apply on drift. 'Trust bytes, not reports.' The authoritative server that never trusts the client.",
        "example": "python main.py spec-gate --file <path> --spec <spec>",
    },
    "tools:spec_execute": {
        "group": "run",
        "help": "Frozen state → penny spec → local executes inside the spec",
        "desc": "The 'spend on the spec, not the tier' pipeline: deepseek-v4-flash (thinking off) writes a penny spec, local executes inside it.",
        "example": "python tools/spec_execute.py --goal \"<goal>\"",
    },
    "tools:local_bench": {
        "group": "run",
        "help": "Benchmark harness — task shapes × local models",
        "desc": "Measures verifiable ok + fake_success across task shapes. Proved tool_plan was a broken verifier. Results → memory/runs/local_bench/.",
        "example": "python tools/local_bench.py --shapes 9",
    },
    "tools:code_execution": {
        "group": "run",
        "help": "Sandboxed code execution",
        "desc": "Executes code in a contained environment (job_floor containment).",
        "example": "python tools/code_execution.py --check <file>",
    },
    "mag:factory_gate": {
        "group": "run",
        "help": "Factory phase gate",
        "desc": "Gates whether a factory phase may run.",
        "example": "python -m mag.factory_gate --phase <n>",
    },
    "mag:factory_machine": {
        "group": "run",
        "help": "Factory machine — run a factory phase",
        "desc": "Executes a factory (v3 substrate) phase.",
        "example": "python -m mag.factory_machine --phase <n>",
    },
    "mag:tripartite_boot": {
        "group": "run",
        "help": "Boot the tripartite loop",
        "desc": "Starts the sovereign tripartite (route/queue/drain) loop.",
        "example": "python -m mag.tripartite_boot",
    },
    "mag:operating_protocol": {
        "group": "run",
        "help": "Operating protocol — how the loop should behave",
        "desc": "The rules the loop follows; the constitution at runtime.",
        "example": "python -m mag.operating_protocol",
    },
    # ── OPS ──────────────────────────────────────────────────────────────
    "mag:nervous_system": {
        "group": "ops",
        "help": "At-a-glance health — keys, ports, containment, gates",
        "desc": "Probes keys (.env), ports (providers), containment (Docker), gate status (T0–T3). Feeds context_pack L0a, dashboard body, governance alerts. Trust glance + doctor JSON.",
        "example": "python main.py nervous --json",
    },
    "mag:ops_graph": {
        "group": "ops",
        "help": "Categorize + visualize live telemetry as a knowledge graph",
        "desc": "collect() live ops telemetry → categorize() into typed nodes/edges → render() live SVG radial. REST: GET /api/v1/graph/ops.",
        "example": "python main.py ops-graph --ingest",
    },
    "mag:drainer_stats": {
        "group": "ops",
        "help": "Drainer status + queue stats",
        "desc": "Reports drainer/queue/operator/fleet health. REST: GET /api/v1/drainer/stats.",
        "example": "python -m mag.drainer_stats",
    },
    "mag:health": {
        "group": "ops",
        "help": "Health check endpoint",
        "desc": "Liveness/health of the framework.",
        "example": "python -m mag.health",
    },
    "mag:live_feed": {
        "group": "ops",
        "help": "Tail a live trail (overseer / ghost / drainer)",
        "desc": "Streams a live feed of a subsystem's trail to the terminal.",
        "example": "python -m mag.live_feed ghost",
    },
    "mag:governor": {
        "group": "ops",
        "help": "Governor — the autorun heartbeat",
        "desc": "Supervises the autorun loop cadence.",
        "example": "python -m mag.governor --status",
    },
    "mag:governor_autorun": {
        "group": "ops",
        "help": "Autorun loop — fills the queue when unattended",
        "desc": "Fills the queue automatically (skips 'done') so the system works without being asked.",
        "example": "python -m mag.governor_autorun --once",
    },
    "mag:janitor": {
        "group": "ops",
        "help": "Janitor — clean stale state / verkle / temp",
        "desc": "Housekeeping: verkle audit + fix, temp cleanup.",
        "example": "python -m mag.janitor --all",
    },
    "mag:system_map": {
        "group": "ops",
        "help": "Map of the whole system",
        "desc": "Renders the framework system map.",
        "example": "python -m mag.system_map",
    },
    "mag:spider": {
        "group": "ops",
        "help": "Watchdog — orchestrator stalls + FKB patterns",
        "desc": "Watches for stalls and failure patterns, writes spider_trail.jsonl.",
        "example": "python -m mag.spider --once",
    },
    # ── AGENTS ───────────────────────────────────────────────────────────
    "mag:agent_cli": {
        "group": "agents",
        "help": "The coding agent — the running worker",
        "desc": "Runs the agent loop: absorbs operator inbox at checkpoints, mutating tools, false-success guard, escalates on loop.",
        "example": "python main.py agent --provider deepseek --query \"<goal>\"",
    },
    "mag:agent_desk": {
        "group": "agents",
        "help": "Desk — an agent workspace/seat",
        "desc": "Runs an agent in a desk with its own context.",
        "example": "python -m mag.agent_desk --seat <name>",
    },
    "mag:coding_session_orchestrator": {
        "group": "agents",
        "help": "Orchestrate a coding session",
        "desc": "Coordinates the coding session lifecycle (steal_protocol integrated).",
        "example": "python -m mag.coding_session_orchestrator",
    },
    "mag:coding_session_runner": {
        "group": "agents",
        "help": "Run a coding session",
        "desc": "Executes a coding session against a goal.",
        "example": "python -m mag.coding_session_runner --goal \"<goal>\"",
    },
    "mag:conductor": {
        "group": "agents",
        "help": "Conductor — direct the multi-agent ensemble",
        "desc": "v4 MOLD conductor orchestrates desks/agents.",
        "example": "python -m mag.conductor",
    },
    "mag:steward": {
        "group": "agents",
        "help": "Steward — manage seats",
        "desc": "Tends the seats/fleet.",
        "example": "python -m mag.steward --status",
    },
    "mag:seat_registry": {
        "group": "agents",
        "help": "Register seats",
        "desc": "Tracks available seats/providers.",
        "example": "python -m mag.seat_registry --list",
    },
    "mag:peer_handoff": {
        "group": "agents",
        "help": "Hand a task off between agents",
        "desc": "Queues a handoff request another agent executes.",
        "example": "python -m mag.peer_handoff --to <agent> --ask \"<ask>\"",
    },
    "mag:handoff_inbox": {
        "group": "agents",
        "help": "Handoff inbox — incoming asks",
        "desc": "Lists/picks handoff requests.",
        "example": "python -m mag.handoff_inbox --list",
    },
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _py(root: Path) -> str:
    p = root / ".venv" / "Scripts" / "python.exe"
    return f'& "{p}"' if p.is_file() else "python"


def assign_group(name: str) -> str:
    """Keyword-based fallback classifier for anything not curated above."""
    n = str(name).lower()
    if re.search(r"(ghost|steer|inbox|skill_drop|tesuji|pro_library|clippy|socratic|intention_brief|compass|gauntlet)", n):
        return "steer"
    if re.search(r"(decision|router|supervisor|fork_router|routing_concert|tier_probe|temperature|refine|rails|ollama_policy|dispatch|fork)", n):
        return "decide"
    if re.search(r"(state_snapshot|verkle|context_pack|memory_events|training_events|failure_kb|run_trail|run_worth|skill_ledger|idea_|resonance|records|diary|biography|dossier|session_card|pile|ledger|knot)", n):
        return "state"
    if re.search(r"(improve|behavioral|behavior_|grove|story|remedy|attention_ranker|token_economy|cost_ledger|research|classify|topic)", n):
        return "learn"
    if re.search(r"(nervous|ops_graph|drainer|health|live_feed|governor|janitor|system_map|audit|spider|autorun|doctor|status)", n):
        return "ops"
    if re.search(r"(orchestrator|job_floor|spec_|local_bench|code_exec|factory|tripartite|boot|runtime|launch_pad|lifecycle|operating_protocol)", n):
        return "run"
    if re.search(r"(agent|desk|session|conductor|steward|seat|arena|autopilot|campaign|game_|handoff|coordination|voice_)", n):
        return "agents"
    return "ops"


def _doc_head(txt: str) -> str:
    m = re.search(r'"""(.*?)(?:\n\s*""")', txt, re.S)
    if not m:
        return ""
    head = m.group(1).split("\n")[0].strip()
    head = re.split(r" — |\.", head, 1)[0]
    return head[:120]


def _read_text(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


# ---------------------------------------------------------------------------
# Scanners — mirror the surfaces the extension used to scan locally.
# ---------------------------------------------------------------------------
def _scan_subcommands(root: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    txt = _read_text(root / "main.py")
    seen: set[str] = set()
    for m in re.finditer(r'add_parser\(\s*"([a-z0-9_-]+)"\s*(?:,\s*help\s*=\s*"([^"]*)")?', txt):
        name, help_text = m.group(1), (m.group(2) or "")
        if name in seen:
            continue
        seen.add(name)
        out.append({"id": f"cli:{name}", "kind": "cli", "name": name, "help": help_text,
                    "run": f"{_py(root)} main.py {name}", "file": "main.py", "line": None})
    return out


def _scan_modules(root: Path, subdir: str) -> list[dict[str, Any]]:
    d = root / subdir
    out: list[dict[str, Any]] = []
    if not d.is_dir():
        return out
    for f in sorted(d.glob("*.py")):
        if f.name == "__init__.py":
            continue
        head = _doc_head(_read_text(f))
        run = f"{_py(root)} {subdir}/{f.name}" if subdir == "tools" else None
        out.append({"id": f"{subdir}:{f.stem}", "kind": subdir, "name": f.stem, "help": head,
                    "run": run, "file": f"{subdir}/{f.name}", "line": None})
    return out


def _scan_launchers(root: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for f in sorted(root.glob("*.cmd")):
        txt = _read_text(f)
        m = re.search(r"REM\s+(.*)", txt)
        out.append({"id": f"launcher:{f.name}", "kind": "launcher", "name": f.stem, "help": (m.group(1).strip() if m else ""),
                    "run": f'"{f}"', "file": f.name, "line": None})
    return out


def _scan_routes(root: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    txt = _read_text(root / "dashboard" / "rest.py")
    seen: set[str] = set()
    for m in re.finditer(r'\(\s*"(GET|POST|PUT|DELETE)",\s*"([^"]+)"', txt):
        method, path = m.group(1), m.group(2)
        key = f"{method} {path}"
        if key in seen:
            continue
        seen.add(key)
        out.append({"id": f"route:{method}:{path}", "kind": "route", "name": path, "help": f"{method} — dashboard REST endpoint",
                    "run": f"curl -s http://127.0.0.1:8765{path}", "file": "dashboard/rest.py", "line": None})
    return out


def _scan_providers(root: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    lines = _read_text(root / "configs" / "providers.yaml").split("\n")
    in_providers = False
    for i, ln in enumerate(lines):
        if re.match(r"^providers:\s*$", ln):
            in_providers = True
            continue
        if not in_providers:
            continue
        m = re.match(r"^  ([a-z0-9_]+):\s*$", ln)
        if m:
            nm = re.search(r"name:\s*(.*)", lines[i + 1] if i + 1 < len(lines) else "")
            out.append({"id": f"provider:{m.group(1)}", "kind": "provider", "name": m.group(1),
                        "help": (nm.group(1).strip() if nm else ""), "run": None,
                        "file": "configs/providers.yaml", "line": i + 1})
    return out


def _enrich(it: dict[str, Any]) -> dict[str, Any]:
    curated = CURATED.get(f"{it['kind']}:{it['name']}")
    it["group"] = (curated or {}).get("group") or assign_group(it["name"])
    if curated and curated.get("help"):
        it["help"] = curated["help"]
    it["desc"] = (curated or {}).get("desc") or it["help"]
    it["example"] = (curated or {}).get("example") or (it.get("run") or "")
    return it


def collect() -> list[dict[str, Any]]:
    return [
        *_scan_subcommands(ROOT),
        *_scan_modules(ROOT, "mag"),
        *_scan_modules(ROOT, "tools"),
        *_scan_launchers(ROOT),
        *_scan_routes(ROOT),
        *_scan_providers(ROOT),
    ]


def render() -> dict[str, Any]:
    """Live snapshot — recomputed from code, never stale."""
    return {
        "schema": SCHEMA,
        "root": str(ROOT),
        "ts": _now(),
        "groups": GROUPS,
        "items": [_enrich(it) for it in collect()],
    }


def persist() -> dict[str, Any]:
    payload = render()
    MAP_PATH.parent.mkdir(parents=True, exist_ok=True)
    MAP_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    payload["persisted_to"] = str(MAP_PATH)
    return payload


def refresh(who: str = "autorun:governor") -> dict[str, Any]:
    """Cadence entry point: render + persist + compile report. Safe to call from
    the autorun loop. The report is the 'compiler' the operator checks in
    another window / dashboard tab — so nobody has to be in the loop."""
    try:
        res = persist()
        res["report"] = compile_report(who=who)
        return res
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)[:300], "ts": _now()}


def _has(path: Path, needle: str) -> bool:
    return needle in _read_text(path)


REPORTS_PATH = REPORT_DIR / "reports.jsonl"


def _append_report(rec: dict[str, Any]) -> None:
    try:
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with REPORTS_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except OSError:
        pass


def list_reports(tail: int = 20) -> list[dict[str, Any]]:
    """Most recent run-session reports, newest first (for the dashboard tab)."""
    if not REPORTS_PATH.is_file():
        return []
    out: list[dict[str, Any]] = []
    for line in REPORTS_PATH.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            o = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(o, dict):
            out.append(o)
    out.sort(key=lambda r: str(r.get("ts", "")), reverse=True)
    return out[:tail]


def _read_jsonl(path: Path, tail: int = 0) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    if tail:
        lines = lines[-tail:]
    out: list[dict[str, Any]] = []
    for ln in lines:
        ln = ln.strip()
        if not ln:
            continue
        try:
            o = json.loads(ln)
        except json.JSONDecodeError:
            continue
        if isinstance(o, dict):
            out.append(o)
    return out


def collect_telemetry(tail_ledger: int = 200) -> dict[str, Any]:
    """Deterministic telemetry snapshot from the framework's OWN ledgers/trails.

    No LLM. Read-only. Feeds the run-session report with:
      agents involved, token spend, frameworks/providers, total estimated cost,
      total estimated savings, experiments run, items involved.
    """
    t: dict[str, Any] = {
        "agents": [],
        "frameworks": [],
        "token_spend": {},
        "total_est_cost_usd": 0.0,
        "total_est_savings_usd": 0.0,
        "savings_tokens": 0,
        "experiments": [],
        "items": [],
    }

    # ── cost ledger: agents + frameworks + token spend + estimated cost ──
    try:
        rows = _read_jsonl(ROOT / "memory" / "training" / "cost_ledger.jsonl", tail=tail_ledger)
        per_provider: dict[str, dict[str, Any]] = {}
        tok_in = tok_out = 0
        total_usd = 0.0
        for r in rows:
            act = r.get("actual") or {}
            plat = r.get("platform") or {}
            prov = str(plat.get("provider") or "?")
            model = str(plat.get("model") or "")
            tok_in += int(act.get("prompt_tokens") or 0)
            tok_out += int(act.get("completion_tokens") or 0)
            usd = float(act.get("usd_est") or 0)
            total_usd += usd
            d = per_provider.setdefault(prov, {"tokens": 0, "usd": 0.0, "models": set()})
            d["tokens"] += int(act.get("prompt_tokens") or 0) + int(act.get("completion_tokens") or 0)
            d["usd"] += usd
            if model:
                d["models"].add(model)
        t["frameworks"] = [
            {"provider": k, "tokens": v["tokens"], "usd": round(v["usd"], 6), "models": sorted(v["models"])}
            for k, v in per_provider.items()
        ]
        t["agents"] = sorted(per_provider.keys())
        t["token_spend"] = {"prompt_tokens": tok_in, "completion_tokens": tok_out, "total_tokens": tok_in + tok_out}
        t["total_est_cost_usd"] = round(total_usd, 6)
    except Exception as e:  # noqa: BLE001
        t["cost_error"] = str(e)[:120]

    # ── token economy: estimated savings (local vs counterfactual dump) ──
    try:
        from mag.token_economy import economy_snapshot

        snap = economy_snapshot()
        tot = snap.get("totals") or {}
        life = snap.get("lifetime") or {}
        t["savings_tokens"] = int(tot.get("tokens_saved") or 0)
        t["total_est_savings_usd"] = round(
            int(tot.get("tokens_saved") or 0) / 1_000_000 * 2.0, 4
        )  # ~$2/M nominal counterfactual; honest estimate, labeled below
        t["savings_lifetime_tokens"] = int(life.get("tokens_saved") or 0)
        t["economy_turns"] = int(tot.get("turns") or 0)
    except Exception as e:  # noqa: BLE001
        t["savings_error"] = str(e)[:120]

    # ── experiments run + items involved (from memory/runs experiment dirs) ──
    try:
        runs_dir = ROOT / "memory" / "runs"
        if runs_dir.is_dir():
            for sub in sorted(runs_dir.iterdir()):
                if not sub.is_dir():
                    continue
                files = [f.name for f in sorted(sub.iterdir()) if f.is_file()]
                if not files:
                    continue
                t["experiments"].append({"name": sub.name, "runs": len(files), "files": files[:6]})
                for f in files[:3]:
                    t["items"].append(f"{sub.name}/{f}")
        t["experiments"].sort(key=lambda x: x["name"])
        # cap for the report
        t["experiments"] = t["experiments"][:24]
        t["items"] = t["items"][:32]
    except Exception as e:  # noqa: BLE001
        t["experiments_error"] = str(e)[:120]

    return t


def compile_report(who: str = "framework_map", intent: str = "", why: str = "") -> dict[str, Any]:
    """Deterministic 'compiler' — validates every seam and emits a structured
    per-run-session report (who/what/when/where/why/intent/topics + summary).

    Writes:
      memory/runs/framework_map/report.md       (human-readable, open in another window)
      memory/runs/framework_map/reports.jsonl   (append-only index for the dashboard tab)
    No LLM; read-only checks.
    """
    checks: list[dict[str, str]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    try:
        payload = render()
        items = payload.get("items") or []
    except Exception as e:  # noqa: BLE001
        payload, items = {}, []
        check("module renders", False, f"render() raised: {str(e)[:120]}")

    check("module renders", len(items) > 0, f"{len(items)} entries")

    groups = payload.get("groups") or []
    counts: dict[str, int] = {}
    for it in items:
        counts[it["group"]] = counts.get(it["group"], 0) + 1
    check("functional groups", len(groups) >= 8,
          ", ".join(f"{g['label']}={counts.get(g['id'], 0)}" for g in groups))

    check("REST route handler", _has(ROOT / "dashboard" / "rest.py", "def h_framework_map"), "dashboard/rest.py")
    check("REST route registered", _has(ROOT / "dashboard" / "rest.py", '"/api/v1/framework/map"'), "dashboard/rest.py")
    check("REST reports route", _has(ROOT / "dashboard" / "rest.py", '"/api/v1/framework/reports"'), "dashboard/rest.py")

    check("cadence env", _has(ROOT / "mag" / "governor_autorun.py", "MAG_MAP_EVERY"), "mag/governor_autorun.py")
    check("cadence job", _has(ROOT / "mag" / "governor_autorun.py", "from mag.framework_map import refresh"), "mag/governor_autorun.py")

    check("loop registered", _has(ROOT / "mag" / "loops_registry.py", '"id": "framework_map"'), "mag/loops_registry.py")

    check("ext polls REST", _has(ROOT / "vscode-mag-map" / "extension.js", "/api/v1/framework/map"), "vscode-mag-map/extension.js")
    check("ext auto-refresh", _has(ROOT / "vscode-mag-map" / "extension.js", "refreshSeconds"), "vscode-mag-map/extension.js")

    ok_all = all(c["ok"] for c in checks)

    # ── telemetry: agents / tokens / frameworks / cost / savings / experiments ──
    telemetry = collect_telemetry()

    # ── structured per-run-session fields ──
    ts = _now()
    rec_id = "fm-" + ts.replace(":", "").replace("-", "").replace("+00:00", "Z").split(".")[0]
    topics = ["framework-map", "verdict:" + ("ready" if ok_all else "attention")] + [g["label"].lower() for g in groups]
    where = f"memory/graph/framework_map.json · {REPORT_PATH.name} · mag/framework_map.py"
    what = f"Regenerated the functional framework map: {len(items)} entries across {len([g for g in groups if counts.get(g['id'])])} groups."
    summary = what + (" All seams verified." if ok_all else " Some seams need attention — see checks.")

    rec: dict[str, Any] = {
        "id": rec_id,
        "ts": ts,
        "who": who,
        "what": what,
        "where": where,
        "why": why or "kept fresh by the MAG_MAP_EVERY cadence; served to the Framework Map pane and dashboard.",
        "intent": intent or "Keep the functional grouping, descriptions and examples current without a manual rescan.",
        "topics": topics,
        "summary": summary,
        "verdict": "ready" if ok_all else "attention",
        "ok": ok_all,
        "entries": len(items),
        "counts": counts,
        "checks": checks,
        "telemetry": telemetry,
        "path": str(REPORT_PATH),
    }

    # ── telemetry lines for the human report ──
    tl = ["## Telemetry", ""]
    tl.append(f"- **agents involved**: {', '.join(telemetry['agents']) or '—'}")
    tl.append(f"- **token spend**: {telemetry['token_spend'].get('total_tokens', 0)} tokens "
              f"({telemetry['token_spend'].get('prompt_tokens', 0)} in / {telemetry['token_spend'].get('completion_tokens', 0)} out)")
    fws = "; ".join(f"{f['provider']} (${f['usd']}, {f['tokens']} tok)" for f in telemetry["frameworks"]) or "—"
    tl.append(f"- **frameworks**: {fws}")
    tl.append(f"- **total estimated cost**: ${telemetry['total_est_cost_usd']}")
    tl.append(f"- **total estimated savings**: {telemetry['savings_tokens']} tokens "
              f"(≈${telemetry['total_est_savings_usd']} @~$2/M counterfactual; {telemetry.get('savings_lifetime_tokens', 0)} lifetime)")
    tl.append(f"- **experiments run**: {len(telemetry['experiments'])} — "
              f"{', '.join(e['name'] for e in telemetry['experiments'][:12]) or '—'}")
    tl.append(f"- **items involved**: {len(telemetry['items'])} — "
              f"{', '.join(telemetry['items'][:8]) or '—'}")
    tl.append("")

    lines = [
        f"# Framework Map — compiler report · {rec_id}", "",
        f"- generated: {ts}",
        f"- who: {who}",
        f"- what: {what}",
        f"- where: {where}",
        f"- why: {rec['why']}",
        f"- intent: {rec['intent']}",
        f"- topics: {', '.join(topics)}",
        f"- entries: {len(items)}",
        f"- verdict: {'✅ READY' if ok_all else '⚠️  NEEDS ATTENTION'}",
        "",
        "## Seam checks", "",
    ]
    lines += [f"- {'✅' if c['ok'] else '❌'} **{c['name']}** — {c['detail']}" for c in checks]
    lines += ["", "## By function", ""]
    lines += [f"- {g['icon']} **{g['label']}**: {counts.get(g['id'], 0)} — {g['blurb']}" for g in groups]
    lines += ["", *tl]
    report_text = "\n".join(lines)

    try:
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(report_text, encoding="utf-8")
    except OSError as e:  # noqa: BLE001
        report_text += f"\n\n(write failed: {e})"

    rec["detail"] = report_text
    _append_report(rec)
    return rec


def _table(payload: dict[str, Any]) -> list[str]:
    lines = [f"# Framework Map — {payload.get('ts', '')}  ({len(payload.get('items') or [])} entries)"]
    for g in payload.get("groups") or []:
        items = [i for i in payload.get("items") or [] if i.get("group") == g["id"]]
        if not items:
            continue
        lines.append(f"\n## {g['icon']} {g['label']} — {g['blurb']}")
        for it in items:
            lines.append(f"- {it['name']}: {it['help']}")
    return lines


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="framework_map", description="Authoritative functional grouping of the framework.")
    ap.add_argument("--json", action="store_true", help="print machine-readable payload")
    ap.add_argument("--ingest", action="store_true", help="render + persist durable copy")
    ap.add_argument("--compile", action="store_true", help="validate all seams + write a run-session report")
    ap.add_argument("--who", default="operator", help="who initiated the run session (for the report)")
    args = ap.parse_args(argv)
    if args.compile:
        rep = compile_report(who=args.who)
        print(f"[framework_map] compile ok={rep['ok']} -> {rep['path']} (id {rep['id']})")
        return 0
    if args.ingest:
        payload = persist()
        print(f"[framework_map] {payload.get('persisted_to', '?')} ({len(payload.get('items') or [])} entries)")
        return 0
    payload = render()
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    print("\n".join(_table(payload)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
