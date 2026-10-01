#!/usr/bin/env python3
"""CLI for local_sovereign_agent."""
from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

# Ensure project root on path
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from audit import log_event, sync_current  # noqa: E402
from config import HANDOFF_DIR, RESULTS_DIR, STATE_DIR, bind_host  # noqa: E402
from handoff.schema import validate_handoff  # noqa: E402
from handoff.verify import load_json, verify_result  # noqa: E402
from models.env_load import load_dotenv  # noqa: E402

# Windows consoles default to cp1252; argparse help contains non-ASCII (\u2192 etc.)
# which crashes --help. Force UTF-8 with replacement so help/errors never die on encode.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass  # non-reconfigurable stream (e.g. some test harnesses)

# Provider keys from project .env (never commit .env)
load_dotenv()

# No headed console windows, ever (window-storm lesson): default EVERY subprocess
# spawn to CREATE_NO_WINDOW at process start. This monkey-patch covers the whole
# process tree (incl. library/indirect spawns), so no module can pop a window.
# Call BEFORE any command handler so no subprocess runs un-patched.
from mag.headless import install_no_window_defaults  # noqa: E402

install_no_window_defaults()


def cmd_run(goal: str, thread_id: str | None = None) -> int:
    from graph import default_graph  # lazy: only run needs LangGraph
    thread_id = thread_id or str(uuid.uuid4())
    app = default_graph()
    init = {
        "goal": goal,
        "messages": [],
        "tier": "T2",
        "plan": [],
        "step_i": 0,
        "tool_trace": [],
        "critique": "",
        "route": "plan",
        "handoff_id": None,
        "status": "running",
        "success_checks": [],
        "last_result": "",
        "retry_count": 0,
        "thread_id": thread_id,
    }
    config = {"configurable": {"thread_id": thread_id}}
    log_event({"event": "run_start", "thread_id": thread_id, "goal": goal[:300]})
    final = app.invoke(init, config=config)
    sync_current(final)
    print("---")
    print(f"status: {final.get('status')}")
    print(f"tier: {final.get('tier')} route: {final.get('route')}")
    print(f"thread_id: {thread_id}")
    if final.get("handoff_id"):
        print(f"handoff_id: {final.get('handoff_id')}")
        print(f"handoff: {HANDOFF_DIR / (final['handoff_id'] + '.json')}")
    print("last_result:")
    print((final.get("last_result") or "")[:3000])
    print("critique:")
    print((final.get("critique") or "")[:1500])
    print(f"\nSee state/CURRENT.md and logs/router.jsonl")
    # persist thread id for resume convenience
    (STATE_DIR / "last_thread.txt").write_text(thread_id, encoding="utf-8")
    return 0 if final.get("status") in {"done", "escalated", "waiting"} else 1


def cmd_status() -> int:
    p = STATE_DIR / "CURRENT.md"
    if p.is_file():
        print(p.read_text(encoding="utf-8"))
        return 0
    print("No CURRENT.md yet. Run a goal first.")
    return 1


def cmd_ingest_result(handoff_id: str) -> int:
    hpath = HANDOFF_DIR / f"{handoff_id}.json"
    rpath = RESULTS_DIR / f"{handoff_id}.json"
    if not hpath.is_file():
        print(f"missing handoff {hpath}")
        return 1
    handoff = json.loads(hpath.read_text(encoding="utf-8"))
    ok, errs = validate_handoff(handoff)
    if not ok:
        print("invalid handoff", errs)
        return 1
    result = load_json(rpath)
    if not result:
        print(f"missing result {rpath} — place Grok output there first")
        return 1
    passed, notes = verify_result(handoff, result)
    log_event({"event": "ingest_result", "handoff_id": handoff_id, "passed": passed, "notes": notes})
    print("verify:", passed, notes)
    if passed:
        summary = result.get("summary") or result.get("deliverable") or ""
        working = ROOT / "memory" / "working.md"
        prev = working.read_text(encoding="utf-8") if working.is_file() else ""
        working.write_text(
            prev + f"\n\n## Result {handoff_id}\n\n{summary}\n",
            encoding="utf-8",
        )
        print(f"merged into {working}")
    return 0 if passed else 1




def cmd_api(host: str, port: int) -> int:
    """Launch the FastAPI API gateway (Epoch 1, Pillar I)."""
    from mag.api_server import run as run_api  # lazy: only api needs FastAPI

    print(f"Mag API gateway -> http://{host}:{port}/  (X-API-Key required)")
    run_api(host=host, port=port)
    return 0


def _print_game_turn(r: dict) -> None:
    """Human-readable turn output for the ramp game — the operator plays in a terminal, not JSON."""
    tier = r.get("tier", "?")
    reply = r.get("reply") or r.get("note") or ""
    print(f"━━━ THE GAME — {tier.upper()} ━━━")
    print(reply)
    if r.get("scene"):
        print(f"scene: {r['scene']}")
    if r.get("turns") is not None:
        print(f"turns: {r['turns']}")
    if r.get("room"):
        print(f"room: {r['room']}")
    if r.get("depth") is not None:
        print(f"depth: {r['depth']}  ·  best: {r.get('best')}")
    if r.get("world_root"):
        print(f"world root: {str(r['world_root'])[:24]}…")
    print("next: game play look · game play go <place> · game map · game descend · game status")


def _print_game_status(s: dict) -> None:
    tier = s.get("tier", "?")
    mastered = s.get("mastered", []) or []
    print("━━━ THE GAME — status ━━━")
    print(f"tier: {tier}")
    print(f"mastered: {', '.join(mastered) if mastered else 'none yet'}")
    print(f"ramp: {' -> '.join(s.get('tiers', []))}")
    print("play it: game play <action>   (look / talk / rest / go <place> / descend)")
    print("cost: deterministic + $0 — the verkle world is the authority")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Local sovereign agent (LangGraph + Ollama)")
    sub = parser.add_subparsers(dest="cmd")

    p_run = sub.add_parser("run", help="Run a goal")
    p_run.add_argument("goal", nargs="+", help="Goal text")
    p_run.add_argument("--thread", default=None)

    p_plan = sub.add_parser("plan", help="Planning gate: clarify big/ambiguous goals")
    p_plan.add_argument("action", nargs="?", default="list",
                        choices=["list", "approve", "edit", "reject", "show"],
                        help="list | approve <id> | edit <id> | reject <id> | show <id>")
    p_plan.add_argument("plan_id", nargs="?", default=None, help="Plan id")
    p_plan.add_argument("--goal", default=None, help="Fire the gate on a goal (draft plan)")

    sub.add_parser("status", help="Show CURRENT.md")

    p_ing = sub.add_parser("ingest", help="Ingest Grok result for handoff id")
    p_ing.add_argument("handoff_id")

    p_watch = sub.add_parser(
        "watch", help="Watch live Grok session into memory/live_from_grok.md"
    )
    p_watch.add_argument("--once", action="store_true")
    p_watch.add_argument("--interval", type=float, default=3.0)

    # ── Talk to Ghost ──
    p_talk = sub.add_parser(
        "talk", help="Talk to Ghost — natural language → copilot inbox → result"
    )
    p_talk.add_argument("query", nargs="+", help="What to ask Ghost (natural language)")
    p_talk.add_argument("--provider", default="ollama", help="LLM provider (ollama, deepseek, grok)")
    p_talk.add_argument("--model", default="qwen2.5-coder:7b", help="Model name")
    p_talk.add_argument("--timeout", type=int, default=120, help="Max wait seconds")
    p_talk.add_argument("--watch", action="store_true", help="Stream live Ghost events after query")
    p_talk.add_argument("--json", action="store_true", help="Machine-readable output")

    # ── Parallel swarm ──
    p_swarm = sub.add_parser(
        "swarm", help="Fire a parallel research swarm — N agents, different angles"
    )
    p_swarm.add_argument("goal", nargs="+", help="Research question")
    p_swarm.add_argument("--size", type=int, default=3, help="Swarm size (2-5 agents)")
    p_swarm.add_argument("--dry", action="store_true", help="Preview only, don't fire")

    p_dash = sub.add_parser(
        "dashboard",
        help="Browse history: sessions, PDFs, Verkle, ingest (http://127.0.0.1:8765)",
    )
    p_dash.add_argument("--host", default=None, help="Override bind host (0.0.0.0 requires --lan)")
    p_dash.add_argument("--port", type=int, default=8765)
    p_dash.add_argument(
        "--lan",
        action="store_true",
        help="Listen on all interfaces for phone/tablet on WiFi (explicit opt-in)",
    )
    p_dash.add_argument(
        "--local-only",
        action="store_true",
        help="Force 127.0.0.1 and clear saved LAN preference",
    )

    p_api = sub.add_parser(
        "api",
        help="FastAPI gateway on :8001 (X-API-Key required; :8000 is tool backend)",
    )
    p_api.add_argument("--host", default="127.0.0.1")
    p_api.add_argument("--port", type=int, default=8001)

    p_evo = sub.add_parser(
        "knot-evolution",
        help="Show living Verkle-knot topic evolution across session records",
    )

    p_sum = sub.add_parser(
        "summarize-session",
        help="FILE a seat chat into residual DNA + Verkle leaf (Grok or Mag agent)",
    )
    p_sum.add_argument(
        "--session",
        default="",
        help="Session id (Grok UUID, mag-agent-<seat>, or agent seat name; default: active Grok)",
    )
    p_sum.add_argument(
        "--source",
        default="auto",
        choices=["auto", "grok", "mag_agent", "agent"],
        help="Chat source (default auto — resolve Grok or Mag agent)",
    )
    p_sum.add_argument("--force", action="store_true", help="Re-summarize even if done")
    p_sum.add_argument("--no-llm", action="store_true", help="Heuristic only, no Ollama")
    p_sum.add_argument(
        "--pdf",
        action="store_true",
        help="Also render PDF (export layer; off by default)",
    )
    p_sum.add_argument(
        "--visual",
        action="store_true",
        help="Also write visual pack (export layer; off by default)",
    )
    p_sum.add_argument(
        "--all-agents",
        action="store_true",
        help="FILE every Mag agent seat under memory/agent_sessions/",
    )
    p_sum.add_argument(
        "--no-pdf",
        action="store_true",
        help="Deprecated: PDF already off by default",
    )

    p_mag = sub.add_parser(
        "mag",
        help="Sovereign Mag background companion (sense→judge→act; Grok harness escalate)",
    )
    p_mag.add_argument("--once", action="store_true", help="Single cycle then exit")
    p_mag.add_argument(
        "--interval",
        type=float,
        default=None,
        help="Seconds between cycles (default from configs/mag.yaml)",
    )
    p_mag.add_argument(
        "--no-harness",
        action="store_true",
        help="Force file handoffs only (skip grok -p)",
    )

    p_brief = sub.add_parser(
        "brief",
        help="Local brief from dossier (L0) — memory/briefs/<session>.md",
    )
    p_brief.add_argument("--session", default="latest")
    p_brief.add_argument("--no-llm", action="store_true")

    p_ask = sub.add_parser(
        "ask",
        help="Ask Mag biographer from local memory (no Grok)",
    )
    p_ask.add_argument("question", nargs="+", help="Question text")
    p_ask.add_argument("--session", default="", help="Optional session id")
    p_ask.add_argument("--no-llm", action="store_true")
    p_ask.add_argument("--no-speak", action="store_true", help="Disable default TTS for this answer")

    p_tts = sub.add_parser("tts", help="Speak text out loud (default TTS)")
    p_tts.add_argument("text", nargs="+", help="Text to speak")

    p_ws = sub.add_parser(
        "workshop",
        help="Socratic prompt workshop: refine a prompt before launching a coding session",
    )
    p_ws.add_argument("prompt", nargs="+", help="Rough prompt to refine")
    p_ws.add_argument("--rounds", type=int, default=3, help="Socratic rounds")
    p_ws.add_argument("--no-speak", action="store_true", help="Don't speak the refined prompt")

    p_sroute = sub.add_parser(
        "session-route",
        help="Print the data-backed session routing preamble (seed + agent-state + learned principles)",
    )
    p_sroute.add_argument("--state", default=None, help="agent state (default coding-agent)")
    p_sroute.add_argument("--json", action="store_true")
    p_sroute.add_argument("goal", nargs="*", default=[])

    p_summon = sub.add_parser(
        "ghost-summon",
        help="Summon @ghost with the current session: current + future + coldest vertices -> intent (skips stale processes)",
    )
    p_summon.add_argument("--reason", action="store_true", help="Narrate the intent via a model call")
    p_summon.add_argument("--model", default=None, help="model for --reason")
    p_summon.add_argument("context", nargs="*", default=[], help="optional operator context")

    p_legacy = sub.add_parser(
        "legacy-audit",
        help="Catalog + retire leftover/legacy Mag processes (scan|catalog|retire|research) — maps each to its newer system",
    )
    p_legacy.add_argument("legacy_cmd", nargs="?", default="catalog",
                          choices=["scan", "catalog", "retire", "research"])
    p_legacy.add_argument("--dry", action="store_true", help="retire: report only, don't kill")

    p_vis = sub.add_parser(
        "visual",
        help="Build/amend Mag visual pack (chambers) for a session",
    )
    p_vis.add_argument("--session", default="latest")

    sub.add_parser("doctor", help="Sanity map: integral / live board / lanes (anti-hallucination)")
    p_scrum = sub.add_parser(
        "scrum",
        help="Formalized Scrum backlog + proof-first socratic sprint loop (backlog|sprint|advance|surface) + trusted surface",
    )
    p_scrum.add_argument("cmd", nargs="?", default="backlog",
                         choices=["backlog", "sprint", "advance", "surface"])
    p_scrum.add_argument("--apply", action="store_true", help="advance: actually move the item + save board")
    p_game = sub.add_parser(
        "game",
        help="PLAY the game: the complexity ramp (tabletop -> mud -> roguelite) on the verkle world",
    )
    game_sub = p_game.add_subparsers(dest="game_cmd")
    game_sub.add_parser("status", help="current tier + objective + what you can do")
    game_sub.add_parser("map", help="render the world territory as ASCII")
    game_sub.add_parser("render", help="the base ASCII render of the current tier")
    game_sub.add_parser("descend", help="master the current tier and descend to the next")
    p_game_play = game_sub.add_parser("play", help="take a turn: play <action> (look/talk/rest/go <place>)")
    # nargs='*' so multi-word actions survive: 'go hall' -> ['go','hall'] -> 'go hall'
    p_game_play.add_argument("action", nargs="*", default=["look"])
    p_nerv = sub.add_parser(
        "nervous",
        help="Nervous system: at-a-glance body + Verkle tips + key presence (agent ops)",
    )
    p_nerv.add_argument("--json", action="store_true", help="Full nervous_system.v1 JSON")
    p_nerv.add_argument(
        "--quiet",
        action="store_true",
        help="Write face files only; exit code = body_ok",
    )
    p_map = sub.add_parser(
        "system-map",
        help="Live autonomy map: CURRENT + nervous + inbox + improve + resonance + direction",
    )
    p_map.add_argument("--goal", default="", help="Optional goal hint for resonance and tips")
    p_map.add_argument("--json", action="store_true", help="Emit raw system_map.v1 JSON")
    sub.add_parser(
        "lattice",
        help="Verkle lattice history + plan summary (JSON for desk / Grok)",
    )
    p_fs = sub.add_parser(
        "field-steal",
        help="Ingest field sysprompt archive → contract steal ledger (not DNA)",
    )
    p_fs.add_argument(
        "--root",
        type=str,
        default="",
        help="Path to field clone (default: ../field-strike-the-chord)",
    )
    p_fs.add_argument("--max-files", type=int, default=0, help="Cap files scanned (0=all)")
    p_fs.add_argument("--json", action="store_true", help="Print result JSON only")
    p_cu = sub.add_parser("catch-up", help="After reconnect: watch + amend + visual")
    p_probe = sub.add_parser("probe-lanes", help="Real L0/L1/L2 probes (not vibes)")
    p_probe.add_argument("--no-l1", action="store_true", help="Skip OpenRouter chat")
    p_guard = sub.add_parser("guard", help="Failsafe loop: detect down Mag, optional --restart")
    p_guard.add_argument("--once", action="store_true")
    p_guard.add_argument("--interval", type=float, default=30.0)
    p_guard.add_argument("--restart", action="store_true", help="Spawn lab if down")
    p_boot = sub.add_parser(
        "boot",
        help="Sancho boot: self-analysis + optional ensure lab (SessionStart)",
    )
    p_boot.add_argument(
        "--ensure",
        action="store_true",
        help="Spawn lab if integral down / live stale",
    )
    p_boot.add_argument(
        "--light",
        action="store_true",
        help="Skip quota snapshot (faster hook path)",
    )
    p_boot.add_argument("--json", action="store_true", help="Print full JSON report")
    p_bcoord = sub.add_parser(
        "boot-coordination",
        help="Tripartite boot — heart (local) · mind (routing) · body (agents)",
    )
    p_bcoord.add_argument("--actor", default="mag")
    p_bcoord.add_argument("--seat", default=None)
    p_bcoord.add_argument("--json", action="store_true")
    p_pack = sub.add_parser(
        "pack-status",
        help="Records office: pack completeness for one session or all",
    )
    p_pack.add_argument(
        "session",
        nargs="?",
        default="all",
        help="Session id, or 'all' (default)",
    )
    p_pack.add_argument("--json", action="store_true", help="Full JSON")
    p_bf = sub.add_parser(
        "backfill-sessions",
        help="Records office: force-complete incomplete session packs",
    )
    p_bf.add_argument(
        "--llm",
        action="store_true",
        help="Use Ollama polish (default: heuristic only)",
    )
    p_bf.add_argument(
        "--dry-run",
        action="store_true",
        help="List holes only; do not write",
    )
    p_bf.add_argument(
        "--all",
        action="store_true",
        help="Re-file every known session, not only incomplete",
    )
    sub.add_parser(
        "refresh-session-cards",
        help="Rebuild human blurb+bullets on all dossiers (no full re-summarize)",
    )
    sub.add_parser(
        "migrate-lean-registry",
        help="Migrate dossiers → residual/ + rebuild registry.jsonl (lean model)",
    )
    p_org = sub.add_parser(
        "org-review",
        help="Local forest walk: DNA + what was I doing + next ticket (no Grok)",
    )
    p_org.add_argument("--json", action="store_true", help="Full operator-os JSON")
    sub.add_parser(
        "tapestry",
        help="Build 3D tapestry pack from residual (sample VK-class lattice)",
    )
    sub.add_parser("models", help="Role → Ollama model map + present/missing")
    sub.add_parser(
        "multi-smoke",
        help="M0 dual-local proof: clerk+worker+critic on public fixture",
    )
    p_governor = sub.add_parser(
        "governor",
        help="Autorun decision framework (the product): decide/execute/verify/record",
    )
    p_governor.add_argument("--run", type=int, default=1, help="cycles to autorun")
    p_governor.add_argument("--dry", type=int, default=0, help="decide + report only")
    p_auto = sub.add_parser(
        "autopilot",
        help="Brain+loop pass: improve queue + governor + seed-mirror status",
    )
    p_auto.add_argument("--no-queue", action="store_true", help="skip improve->orchestrator enqueue")
    p_auto.add_argument("--no-governor", action="store_true", help="skip governor cycle")
    p_auto.add_argument("--drain", action="store_true", help="drain once after queue")
    p_auto.add_argument("--max-queue", type=int, default=2, help="max improve tickets to queue")
    p_autorun = sub.add_parser(
        "autorun",
        help="Intelligent autorun: fill queue, route, drain DeepSeek jobs (drainer loop)",
    )
    p_autorun.add_argument("--once", action="store_true", help="single tick then exit")
    p_autorun.add_argument("--dry", action="store_true", help="plan only, no execute")
    p_autorun.add_argument("--no-fill", action="store_true", help="skip queue fill")
    p_autorun.add_argument("--fill-only", action="store_true", help="fill + plan only")
    p_autorun.add_argument("--interval", type=float, default=5.0, help="loop interval seconds")
    p_tchain = sub.add_parser(
        "token-chain",
        help="DeepSeek plans a local work order; deterministic local executor runs it (token-save test)",
    )
    p_tchain.add_argument(
        "goal",
        nargs="*",
        help="T2 goal for the planner (default: inspect improve brief)",
    )
    p_tchain.add_argument(
        "--dry",
        action="store_true",
        help="No DeepSeek call — fixture plan + local exec only",
    )
    p_tchain.add_argument(
        "--planner",
        default="deepseek",
        help="Planner provider (default deepseek)",
    )
    p_sg = sub.add_parser(
        "seat-guard",
        help="Supervise the seat REPL: relaunch on crash/glitch/stall/hard-stop",
    )
    p_sg.add_argument("sg_args", nargs=argparse.REMAINDER,
                      help="forwarded to mag/seat_guard.py (run/status/stop/trail)")
    p_cp = sub.add_parser(
        "context-pack",
        help="Min-token pack for Grok TUI (bonds+brief+loops — not full chat)",
    )
    p_cp.add_argument(
        "--refresh-bonds",
        action="store_true",
        help="Re-ingest residual bonds before packing",
    )
    p_cp.add_argument(
        "--mode",
        default="full",
        choices=["janitor", "route", "build", "audit", "plan", "full"],
        help="Pack depth: janitor (ask/steward) · route · build · audit · plan · full",
    )
    p_cp.add_argument(
        "--job",
        default="",
        help="Skill job id for skills.yaml (default from mode)",
    )
    p_cp.add_argument(
        "--build",
        default="",
        help="Path to frozen BUILD markdown (build/audit modes)",
    )
    p_cp.add_argument(
        "--scope",
        default="",
        help="Scope card slug under memory/steward/scope_cards/",
    )
    p_cp.add_argument(
        "--agent",
        action="store_true",
        help="Blind-men agent preamble (coarse elephant for subagents/workflows)",
    )
    p_cp.add_argument(
        "--goal",
        default="",
        help="Optional goal line embedded in --agent preamble",
    )
    p_bonds = sub.add_parser(
        "bonds",
        help="Ingest residual bonds → memory/bonds_active.md (next-session inputs)",
    )
    p_bonds.add_argument(
        "--session",
        default="",
        help="Session id (default: latest brief)",
    )
    p_bonds.add_argument(
        "--print",
        action="store_true",
        dest="print_bonds",
        help="Print bonds markdown after ingest",
    )

    p_bonds.add_argument(
        "--scan",
        default="",
        help="Conflict-scan a candidate bond text against existing residual bonds (no write)",
    )

    p_diary = sub.add_parser(
        "diary",
        help="Day-by-day story spine from filed beads (how we got here)",
    )
    p_diary.add_argument("--newest", action="store_true", help="Newest first")
    p_diary.add_argument("--write", action="store_true", help="Write memory/diary_latest.md")
    p_diary.add_argument("--json", action="store_true", help="JSON output")

    p_ideas = sub.add_parser(
        "ideas",
        help="Idea graph v0 — topic nodes/edges on disk (list|add|link|pack|seed|show)",
    )
    p_ideas.add_argument(
        "action",
        nargs="?",
        default="list",
        choices=["list", "add", "link", "pack", "seed", "show", "summary"],
        help="list|add|link|pack|seed|show|summary",
    )
    p_ideas.add_argument("ids", nargs="*", help="node id(s); link uses SRC DST")
    p_ideas.add_argument("--type", default="", dest="idea_type", help="node or edge type")
    p_ideas.add_argument("--status", default="", help="filter status (list) or set status (add)")
    p_ideas.add_argument("--title", default="", help="title for add")
    p_ideas.add_argument("--body", default="", help="body for add")
    p_ideas.add_argument("--note", default="", help="note for link")
    p_ideas.add_argument("--ref", default="", help="ref path for link")
    p_ideas.add_argument("--limit", type=int, default=40, help="list limit")
    p_ideas.add_argument("--json", action="store_true", help="JSON output")
    p_as = sub.add_parser(
        "agent-state",
        help="Versioned Grok/Mag agent state (Verkle chain) — LOAD before redesign",
    )
    p_as.add_argument(
        "--load",
        action="store_true",
        help="Print LATEST.md (full recall pack)",
    )
    p_as.add_argument(
        "--list",
        action="store_true",
        dest="list_versions",
        help="List version chain rows",
    )
    p_as.add_argument(
        "--show",
        default="",
        help="Show version by content_commit prefix (8+ hex)",
    )
    p_as.add_argument(
        "--commit",
        default="",
        help="Commit reason/label (writes new version; use with --from-file or default snapshot)",
    )
    p_as.add_argument(
        "--from-file",
        default="",
        help="JSON payload path for --commit (optional)",
    )
    p_as.add_argument(
        "--link-residual",
        action="store_true",
        help="Write edges.agent_state onto latest residual (no core strip)",
    )
    p_as.add_argument("--session", default="", help="Session id for --link-residual")
    p_as.add_argument("--json", action="store_true", help="JSON output where applicable")
    p_compose = sub.add_parser(
        "compose-status",
        help="Module registry + compose/runtime health (modular upgrade face)",
    )
    p_compose.add_argument("--json", action="store_true", help="Raw JSON")
    p_compose.add_argument(
        "--attach-runs",
        action="store_true",
        help="Retrocausal: write related_runs onto residual edges (no core strip)",
    )
    p_compose.add_argument("--session", default="", help="Session id for --attach-runs")
    p_trail = sub.add_parser(
        "trail",
        help="Run object + live trail (seat purity, cores, pack excerpt)",
    )
    p_trail.add_argument(
        "action",
        choices=[
            "start",
            "append",
            "status",
            "close",
            "check-seat",
            "cores",
            "pack",
            "base",
            "drifts",
        ],
        help="start|append|status|close|check-seat|cores|pack|base|drifts",
    )
    p_trail.add_argument("text", nargs="*", help="Goal (start) or summary (append)")
    p_trail.add_argument(
        "--seat",
        default="local",
        help="Seat lock on start / purity check (local|remote|grok_tui|hermes|human)",
    )
    p_trail.add_argument(
        "--proactivity",
        default="narrow",
        choices=["narrow", "normal", "wide"],
        help="Proactivity dial (start)",
    )
    p_trail.add_argument("--run", default="", help="run_id (default: active)")
    p_trail.add_argument("--kind", default="note", help="Event kind for append")
    p_trail.add_argument(
        "--core",
        default="",
        help='JSON core for append (PowerShell-hostile); prefer --core-text',
    )
    p_trail.add_argument(
        "--core-text",
        default="",
        help="Plain core text for append → {type: kind or decision, text: …}",
    )
    p_trail.add_argument(
        "--label",
        default="",
        help="append: agent probe label → file_agent_core (kind agent_probe)",
    )
    p_trail.add_argument(
        "--locus",
        default="",
        help="append --label: graph locus for drift (default: label)",
    )
    p_trail.add_argument(
        "--drift-kind",
        default="note",
        dest="drift_kind",
        help="append --label: add|contradict|open_loop|gap|severity|note|finding|ready",
    )
    p_trail.add_argument(
        "--evidence",
        default="",
        help="append --label: short evidence string (file:line / tool)",
    )
    p_trail.add_argument(
        "--base-id",
        default="",
        dest="base_id",
        help="append --label: must match run base or FILE rejected",
    )
    p_trail.add_argument(
        "--git-sha",
        default="",
        dest="git_sha",
        help="start: pin code base SHA into frozen run base (default: git HEAD)",
    )
    p_trail.add_argument(
        "--force",
        action="store_true",
        help="start: close prior open run first",
    )
    p_trail.add_argument("--reason", default="done", help="close reason")
    p_trail.add_argument(
        "--never-remote",
        action="store_true",
        help="start: privacy.never_remote (tier_max T1)",
    )
    sub.add_parser(
        "providers",
        help="List platforms (OpenAI/Gemini/DeepSeek/…) + keys + quota remaining",
    )
    sub.add_parser("quota", help="Usage used/remaining until reset per platform")
    p_pc = sub.add_parser(
        "provider-chat",
        help="Chat via a platform (or --job to auto-pick by budget)",
    )
    p_pc.add_argument("prompt", nargs="+", help="User prompt (public T2 only for remotes)")
    p_pc.add_argument("--provider", default="", help="ollama|openrouter|openai|anthropic|groq|deepseek|gemini|xai|together")
    p_pc.add_argument("--job", default="public_summarize", help="Routing job class if no --provider")
    p_pc.add_argument("--model", default="", help="Override model id")
    p_pc.add_argument("--tier", default="T2", help="T0|T1 blocked on remote")
    p_disp = sub.add_parser(
        "dispatch",
        help="Sovereign hop: local context-pack → auto seat/provider → min tokens",
    )
    p_disp.add_argument("goal", nargs="+", help="What to do")
    p_disp.add_argument("--dry", action="store_true", help="Classify only, no model call")
    p_disp.add_argument("--provider", default="", help="Force provider id")
    p_disp.add_argument(
        "--seat",
        default="",
        help="Force seat: local|remote|grok_tui|hermes",
    )
    p_coord = sub.add_parser(
        "coordinate",
        help="Classify depth + route to Grok plan / DeepSeek heavy / local simple (shared activity)",
    )
    p_coord.add_argument("goal", nargs="+", help="What to do")
    p_coord.add_argument(
        "--depth",
        default="",
        choices=("overview", "plan", "heavy_code", "simple_code", "scut", ""),
        help="Force depth (else auto-classify)",
    )
    p_coord.add_argument("--seat", default="cli", help="Calling seat id")
    p_coord.add_argument("--dry", action="store_true", help="Classify only — do not launch")
    p_coord.add_argument(
        "--background",
        action="store_true",
        help="Queue heavy_code on orchestrator instead of inline delegate",
    )
    p_coord.add_argument("--session", default="", help="Agent session id for delegate mode")
    p_route = sub.add_parser(
        "route",
        help="Unified routing agent: classify + launch the routed seat or dry-run only",
    )
    p_route.add_argument("goal", nargs="+", help="What to route")
    p_route.add_argument(
        "--depth",
        default="",
        choices=("overview", "plan", "heavy_code", "simple_code", "scut", ""),
        help="Force depth (else auto-classify)",
    )
    p_route.add_argument(
        "--dry",
        action="store_true",
        help="Classify only; do not launch the routed seat",
    )
    p_route.add_argument(
        "--background",
        action="store_true",
        help="When heavy_code routes to queue mode, enqueue on orchestrator instead of inline delegate",
    )
    p_route.add_argument(
        "--session",
        default="",
        help="Agent session id for delegate mode",
    )
    p_route.add_argument(
        "--force-provider",
        default="",
        help="Force a provider for the routing decision (e.g. deepseek, ollama, openrouter)",
    )
    p_route.add_argument(
        "--force-seat",
        default="",
        help="Force a seat for the routing decision (e.g. local, remote, cursor, hermes)",
    )
    p_route.add_argument(
        "--local",
        action="store_true",
        help="If lane=local, execute ask/doctor/smoke now (legacy local runner)",
    )
    p_decide = sub.add_parser(
        "decide",
        help="Framework decision: route + behavioral tips + interference status",
    )
    p_decide.add_argument("goal", nargs="+", help="What to decide")
    p_decide.add_argument(
        "--depth",
        default="",
        choices=("overview", "plan", "heavy_code", "simple_code", "scut", ""),
        help="Force depth",
    )
    p_steer = sub.add_parser(
        "steer-agent",
        help="Steer the agent via operator_inbox breadcrumbs (drained at checkpoint)",
    )
    p_steer.add_argument("text", nargs="*", help="One-shot guidance text (or use --sync)")
    p_steer.add_argument("--sync", action="store_true", help="Push new lines from queue/steer_agent.md")
    p_steer.add_argument("--file", default="", help="Custom drop file path for --sync")
    p_steer.add_argument("--source", default="copilot-assistant", help="Source tag (default copilot-assistant)")
    p_steer.add_argument("--status", action="store_true", help="Show inbox state")
    p_vfeed = sub.add_parser(
        "vscode-feed",
        help="VS Code chat -> behavioral loop (pile, behavioral_events, skill_ledger, pro_library)",
    )
    p_vfeed.add_argument(
        "vf_action",
        nargs="?",
        default="capture",
        choices=("capture", "status"),
        help="capture a chat signal, or status",
    )
    p_vfeed.add_argument("--goal", default="", help="What was asked / built")
    p_vfeed.add_argument("--outcome", default="unknown", choices=("ok", "fail", "escalated", "loop", "unknown"))
    p_vfeed.add_argument("--tier", default="T1")
    p_vfeed.add_argument("--lesson", action="append", default=[], help="Repeatable lesson")
    p_vfeed.add_argument("--source", default="copilot")
    p_vfeed.add_argument("--session", default="", help="Session id")
    p_ds = sub.add_parser(
        "drainer-stats",
        help="Drainer / queue / fleet / pending-handoff stats (CLI readout)",
    )
    p_ds.add_argument("ds_args", nargs=argparse.REMAINDER, help="--json for machine output")
    p_lf = sub.add_parser(
        "live-feed",
        help="Tail overseer/ghost/drainer trails as a live terminal feed",
    )
    p_lf.add_argument("lf_args", nargs=argparse.REMAINDER,
                      help="overseer|ghost|drainer [--lines N] [--json]")
    p_ssb = sub.add_parser(
        "session-state-brief",
        help="Drop live session state into memory/briefs/latest.md (self-brief every chat)",
    )
    p_ssb.add_argument("--json", action="store_true", help="Print payload, don't write")
    p_ssb.add_argument("--dry", action="store_true", help="Print the rendered brief, don't write")
    p_sbrief = sub.add_parser(
        "state-brief",
        help="START BRIEF: deterministic greeting at state/START_BRIEF.md (the bard report). Cheap + measured transfer, $0.",
    )
    p_sbrief.add_argument("--json", action="store_true", help="Print measured payload, don't write")
    p_sbrief.add_argument("--dry", action="store_true", help="Print rendered brief, don't write")
    p_og = sub.add_parser(
        "ops-graph",
        help="Categorize live ops telemetry into a typed knowledge graph (nodes + edges)",
    )
    p_og.add_argument("--json", action="store_true", help="Machine-readable graph payload")
    p_og.add_argument("--ingest", action="store_true",
                      help="Also append nodes/edges to memory/graph/ durable store")
    p_jan = sub.add_parser(
        "janitor",
        help="Prune temp/pytest-* scratch + regenerate docs (keep environment lean & documented)",
    )
    p_jan.add_argument("--dry", action="store_true", help="Report what would change, don't change")
    p_jan.add_argument("--prune-only", action="store_true")
    p_jan.add_argument("--document-only", action="store_true")
    p_jan.add_argument("--last", action="store_true", help="Print the last janitor report")
    p_orphan = sub.add_parser(
        "orphan",
        help="Orphan timer: capture undone-yet-intended work and promote it to the idea graph",
    )
    p_orphan.add_argument("orphan_args", nargs=argparse.REMAINDER,
                          help="note <intent> [--source X] | run [--threshold N] [--dry] | list | resolve <id>")
    p_warn = sub.add_parser(
        "warning-monitor",
        help="Passive warning monitor: scan logs, report new warnings into the failure KB (handled via our system)",
    )
    p_warn.add_argument("warn_args", nargs=argparse.REMAINDER,
                        help="run [--dry] | status")
    p_proc_sup = sub.add_parser(
        "process-supervisor",
        help="Single process supervisor: one thing runs the framework loops (up/down/status/start/stop/restart) — kills the N-terminal sprawl",
    )
    p_proc_sup.add_argument("proc_sup_args", nargs=argparse.REMAINDER,
                            help="up | down | status | start <name> | stop <name> | restart <name>")
    p_docker = sub.add_parser(
        "docker-ops",
        help="Docker containment: probe/status (report-only) or up/down (explicit routed cutover). Framework path for the containerized deployment.",
    )
    p_docker.add_argument("docker_args", nargs=argparse.REMAINDER,
                          help="status | probe | up | down")
    p_wake = sub.add_parser(
        "wake",
        help="Cheap cold start: bring up default supervisor loops + write the START BRIEF greeting. One command, no ceremony.",
    )
    p_wake.add_argument("--brief-only", action="store_true",
                        help="Just regenerate the START BRIEF greeting, don't touch loops")
    p_deeph = sub.add_parser(
        "deep-handoff",
        help="Hand the run to a deeper model via the session maze (memory-framework test): assemble maze + spawn on deepseek-v4-pro",
    )
    p_deeph.add_argument("deep_args", nargs=argparse.REMAINDER,
                         help="<goal> [model] | assemble")
    p_ext = sub.add_parser(
        "extension-deploy",
        help="Deploy the MAG extension files to the installed extension dir",
    )
    p_emb = sub.add_parser(
        "embassy-publish",
        help="Publish the AOS embassy packet to GitHub (dry by default; --live to actually push)",
    )
    p_emb.add_argument("--live", action="store_true",
                        help="Actually push the repo (git push via cached creds; no gh needed)")
    p_emb.add_argument("--repo", metavar="URL",
                        help="Target GitHub repo URL to push into (e.g. https://github.com/<you>/embassy-aos)")
    p_clean = sub.add_parser(
        "cleanup",
        help="Passive code-audit cleanup: move transient project-dir artifacts to memory/trash (dry by default; --live to move)",
    )
    p_clean.add_argument("--live", action="store_true",
                         help="Actually move transient artifacts to trash (reversible)")
    p_costlearn = sub.add_parser(
        "cost-learn",
        help="Cost/cache learning fold: analyze provider cache/cost/latency and fold into skill_ledger",
    )
    p_costlearn.add_argument("--hours", type=int, default=24, help="analysis window hours")
    p_costlearn.add_argument("--fold", action="store_true", help="write daily leaf + skill_ledger decisions")
    p_costlearn.add_argument("--cadence", action="store_true", help="idempotent autorun fold (skip if no new usage)")
    p_ufc = sub.add_parser(
        "usage-forecast",
        help="Right-size-based usage forecast: estimate tokens/cost from the ask queue + calibrate vs actual",
    )
    ufc_sub = p_ufc.add_subparsers(dest="ufc_cmd")
    p_ufc_goal = ufc_sub.add_parser("goal", help="estimate one ask")
    p_ufc_goal.add_argument("goal", nargs="+")
    p_ufc_goal.add_argument("--agent-state", default=None)
    ufc_sub.add_parser("queue", help="forecast pending queue goals")
    p_ufc_cal = ufc_sub.add_parser("calibrate", help="projection vs actual bias")
    p_ufc_cal.add_argument("--hours", type=int, default=24)
    p_ctxg = sub.add_parser("context-growth", help="Per-session context-growth analyzer (find repack ballooners)")
    p_ctxg.add_argument("--hours", type=int, default=24)
    p_ctxg.add_argument("--cadence", action="store_true", help="write maintenance leaf")
    p_ss = sub.add_parser("self-steal", help="Capability-utilization audit (part of doctor/maintenance)")
    p_ss.add_argument("--cadence", action="store_true", help="idempotent: audit + leaf + launch/resume research")
    p_ql = sub.add_parser("queue-learn", help="Queue-as-training-surface: fold terminal queue items into skill_ledger")
    p_ql.add_argument("--fold", action="store_true", help="fold terminals into training rows")
    p_ql.add_argument("--cadence", action="store_true", help="idempotent autorun fold")
    p_qo = sub.add_parser("queue-ops", help="Queue logger + error handler + auto-digest")
    p_qo.add_argument("--cadence", action="store_true", help="idempotent digest")
    p_qo.add_argument("--hours", type=int, default=24)
    p_rm = sub.add_parser("renderman-ask", help="RenderMan-style ask contract: compact->expand->elevate (grok gives executor spec)")
    rm_sub = p_rm.add_subparsers(dest="rm_cmd")
    rm_c = rm_sub.add_parser("compact", help="compact a goal into a RenderMan RIB")
    rm_c.add_argument("goal", nargs="+")
    rm_c.add_argument("--vectors", action="append", default=[])
    rm_c.add_argument("--rib-out", default="")
    rm_e = rm_sub.add_parser("expand", help="expand a RIB file into a full prompt")
    rm_e.add_argument("--rib", required=True)
    rm_v = rm_sub.add_parser("elevate", help="build RIB + ask grok what the executor needs")
    rm_v.add_argument("goal", nargs="+")
    rm_v.add_argument("--executor", default="deepseek-v4-flash")
    rm_v.add_argument("--no-grok", action="store_true")
    p_gm = sub.add_parser("gap-map", help="Map cheap-vs-frontier gap + frontier stack accumulator")
    p_gm.add_argument("--stack", type=float, metavar="COMPLEXITY", help="accumulate a frontier-worthy ask")
    p_gm.add_argument("--stack-status", action="store_true", help="show frontier stack status")
    p_gm.add_argument("--stack-goal", default="", help="goal label for --stack")
    p_fh = sub.add_parser("frontier-help", help="Percolate journaled asks into a frontier HELP-WANTED doc")
    p_fh.add_argument("--cadence", action="store_true", help="idempotent: skip if nothing new")
    p_gt = sub.add_parser("grok-terminal", help="Frontier ghost: launch a grok terminal to build packages for cheap swarms")
    p_gt.add_argument("--scan", action="store_true", help="list critical coding tasks that deserve the frontier ghost")
    p_gt.add_argument("--run", default="", metavar="TASK", help="run the frontier ghost on a task (id/goal; empty=auto-pick)")
    p_gt.add_argument("--cwd", default="", help="working dir for the ghost")
    p_gt.add_argument("--rounds", type=int, default=4, help="max navigate rounds")
    p_gt.add_argument("--yolo", action="store_true", help="always-approve shell in the ghost")
    p_aos = sub.add_parser("aos-grok", help="Budgeted AOS grok access (start small, prove it)")
    p_aos.add_argument("--status", action="store_true", help="courtesy-budget status")
    p_aos.add_argument("--probe", action="store_true", help="START SMALL: one bounded probe ask + write the PROOF doc")
    p_aos.add_argument("--ask", default="", metavar="GOAL", help="dispatch a specific ask (budget + gate enforced)")
    p_aos.add_argument("--force", action="store_true", help="bypass gate/budget (operator-only)")
    p_rl = sub.add_parser("research-lens", help="Iterative self-referencing research lens (grows a corpus)")
    p_rl.add_argument("--reindex", action="store_true", help="rebuild the corpus index over landed answers")
    p_rl.add_argument("--status", action="store_true", help="corpus growth + lens edge weights")
    p_rl.add_argument("--prior", default="", metavar="ASK", help="retrieve PRIOR RESEARCH for a new ask")
    p_rl.add_argument("--build", default="", metavar="ASK", help="build a self-referencing research pack")
    p_rl.add_argument("--title", default="", help="title for --build")
    p_rl.add_argument("--lens", default="default", help="lens id")
    p_rl.add_argument("--fold", default="", metavar="ANSWER_PATH", help="fold a landed answer back into the corpus")
    p_rl.add_argument("--cadence", action="store_true", help="idempotent: reindex + fold unfed answers")
    p_cs = sub.add_parser("cheap-swarm", help="Cheap swarm: expand + execute ghost-built packages")
    p_cs.add_argument("--scan", action="store_true", help="list pending ghost/build packages")
    p_cs.add_argument("--status", action="store_true", help="swarm state")
    p_cs.add_argument("--dispatch", default="", metavar="PATH", help="dispatch one package")
    p_cs.add_argument("--cadence", action="store_true", help="idempotent: dispatch up to 3 pending")
    p_gm = sub.add_parser("grok-mirror", help="Mirror Grok's instruction-production through our pipeline")
    p_gm.add_argument("vision", nargs="*", help="the vision prompt to mirror (or 'window on|off|status')")
    p_gm.add_argument("--no-grok", action="store_true", help="dry: no grok calls")
    p_gm.add_argument("--no-research", action="store_true", help="skip the research pack")
    p_gm.add_argument("--no-skill", action="store_true", help="skip skill distillation")
    p_gm.add_argument("--no-socratic", action="store_true", help="skip socratic elevation questions to grok")
    p_gm.add_argument("--lens", default="default")
    p_gm.add_argument("--window-on", action="store_true", help="set active-coding-window flag (ghost observes)")
    p_gr = sub.add_parser("grok-free", help="Free grok surfaces: CLI harness + grok.com private idea space")
    p_gr.add_argument("--status", action="store_true", help="which free grok surfaces are reachable")
    p_gr.add_argument("--capture", default="", metavar="GOAL", help="free grok CLI call (subscription seat, $0)")
    p_gr.add_argument("--save-idea", nargs="+", metavar="TITLE", help="save an idea privately")
    p_gr.add_argument("--body", default="", help="body for --save-idea")
    p_gr.add_argument("--handoff", default="", metavar="GOAL", help="free grok spec -> frozen BUILD contract -> cheap executor")
    p_gr.add_argument("--cadence", action="store_true", help="autonomous loop over the private idea backlog")
    p_gr.add_argument("--control", default="", metavar="ACTION", help="control channel (stop|pause|kill|resume|status)")
    p_gr.add_argument("--skill", action="store_true", help="write the grok-free SKILL.md")
    p_mc = sub.add_parser("mycelium", help="Unified self-scoring mycelium graph (republic OS Phase 1)")
    p_mc.add_argument("--status", action="store_true", help="graph state")
    p_mc.add_argument("--boot", action="store_true", help="rehydrate from snapshot")
    p_mc.add_argument("--adopt", action="store_true", help="seed from idea_graph")
    p_mc.add_argument("--decay", action="store_true", help="self-prune low-salience edges")
    p_mc.add_argument("--link", nargs=2, metavar=("SRC","DST"), help="link two nodes")
    p_mc.add_argument("--link-type", default="related")
    p_mc.add_argument("--reinforce", nargs=2, metavar=("SRC","DST"), help="reinforce an edge")
    p_mc.add_argument("--reward", type=float, default=1.0)
    p_ros = sub.add_parser("republic-os", help="Persistent mycelial-republic OS (Phases 2-5, AOS-grounded)")
    p_ros.add_argument("--status", action="store_true", help="OS + mycelium state")
    p_ros.add_argument("--boot", action="store_true", help="rehydrate graph + state")
    p_ros.add_argument("--seed-aos", action="store_true", help="seed AOS interaction as foundational research")
    p_ros.add_argument("--round", action="store_true", help="stigmergic control-unit round")
    p_ros.add_argument("--round-dry", action="store_true", help="dry round (no worker spend)")
    p_ros.add_argument("--checkpoint", action="store_true", help="durable checkpoint")
    p_ros.add_argument("--memory-block", action="store_true", help="inject persistent memory block")
    p_ros.add_argument("--cadence", action="store_true", help="full OS loop")
    p_ct = sub.add_parser("comms-trail", help="Steal the cheap agent-communication trail (shared private language)")
    p_ct.add_argument("--capture", action="store_true", help="record communication surfaces into the mycelium graph")
    p_ct.add_argument("--confirm", action="store_true", help="round-trip confirm the shared private language")
    p_ct.add_argument("--status", action="store_true", help="trail state")
    p_ct.add_argument("--cadence", action="store_true", help="capture + confirm + dual-write")
    p_roundtable = sub.add_parser(
        "roundtable",
        help="Let all reachable seats read the attributed transcript and answer in bounded rounds",
    )
    p_roundtable.add_argument("question", nargs="+", help="frontier question for the seats")
    p_roundtable.add_argument(
        "--participants", default="",
        help="comma-separated seat labels (default: all registered frontier + desktop seats)",
    )
    p_roundtable.add_argument("--rounds", type=int, default=2, help="1-3 bounded rounds")
    p_roundtable.add_argument("--max-wait-s", type=int, default=90, help="per-seat wait bound")
    p_roundtable.add_argument("--why", default="",
                              help="huang gate: why the roundtable escalation is justified")
    p_roundtable.add_argument("--baseline-surface", default="",
                              help="huang gate: seat consulted first as the single-seat baseline")
    p_roundtable.add_argument("--baseline-answer", default="",
                              help="huang gate: what the baseline seat said")
    p_ml = sub.add_parser("memlang", help="Shared-verkle trigger language (mem language)")
    p_ml.add_argument("--compile", nargs=2, metavar=("ACTION","SPEC"), help="compile a spec into a binary token")
    p_ml.add_argument("--decode", default="", metavar="TOKEN_HEX", help="decode a token")
    p_ml.add_argument("--resolve", default="", metavar="TOKEN_HEX", help="resolve a token against shared state")
    p_ml.add_argument("--trigger", default="", metavar="TOKEN_HEX", help="resolve + optionally execute")
    p_ml.add_argument("--trigger-execute", action="store_true", help="execute on --trigger")
    p_ml.add_argument("--roundtrip", action="store_true", help="compile->transmit->resolve prove-first")
    p_ml.add_argument("--vocab", action="store_true", help="opcode vocabulary")
    p_ml.add_argument("--status", action="store_true", help="registry state")
    p_sh = sub.add_parser("swarm-health", help="Watch swarm health + self-improvement law")
    p_sh.add_argument("--health", action="store_true", help="aggregate swarm health")
    p_sh.add_argument("--law", action="store_true", help="the coded self-improvement law")
    p_sh.add_argument("--law-apply", action="store_true", help="apply the law actions")
    p_sh.add_argument("--status", action="store_true", help="quick health status")
    p_sh.add_argument("--cadence", action="store_true", help="probe + apply the law")
    p_law = sub.add_parser("law", help="Code-as-law enforcement registry")
    p_law.add_argument("--seed", action="store_true", help="register default operator laws")
    p_law.add_argument("--enforce", action="store_true", help="run the law (probe)")
    p_law.add_argument("--enforce-apply", action="store_true", help="run the law + apply actions")
    p_law.add_argument("--id", default=None, help="law id to enforce (default all)")
    p_law.add_argument("--status", action="store_true", help="registry state")
    p_steer = sub.add_parser("steer", help="WINDOW_STEER loop machinery")
    p_steer.add_argument("--emit", action="store_true", help="emit a STEER packet")
    p_steer.add_argument("--id", default="", help="steer id")
    p_steer.add_argument("--source", default="ask-window", help="steer source")
    p_steer.add_argument("--text", default="", help="steer body")
    p_steer.add_argument("--consume", action="store_true", help="scan for [STEER] markers -> memlang")
    p_steer.add_argument("--status", action="store_true", help="steer store state")
    p_elev = sub.add_parser(
        "elevate",
        help="Shape the right-sized ask for the strongest model (grok) + capture it (deliberate-ask protocol)",
    )
    p_elev.add_argument("goal", nargs="?", default="")
    p_elev.add_argument("--model", default="grok-4.5")
    p_elev.add_argument("--live", action="store_true",
                        help="Mark as live (dispatch) rather than dry-run")
    p_elev.add_argument("--no-capture", action="store_true",
                        help="Skip folding to pro_library/skill_ledger")
    p_gate = sub.add_parser(
        "spec-gate",
        help="Wrong-offset gate: freeze/check a file's base fingerprint before a spec is applied",
    )
    p_gate.add_argument(
        "gate_args",
        nargs=argparse.REMAINDER,
        help="freeze <path> [--label x] | check <path> | gate <path> | list",
    )
    p_floor = sub.add_parser(
        "job-floor",
        help="DFHack-style designation manager: create/claim/verify/stuck jobs with frozen specs",
    )
    p_floor.add_argument(
        "floor_args",
        nargs=argparse.REMAINDER,
        help="create --goal ... [--seat] [--spec] [--target x] | claim <id> | verify <id> --ok|--fail | status | list | stuck",
    )
    p_ledger = sub.add_parser(
        "skill-ledger",
        help="Right-sizing counter: decisions + labeled rows toward the targets",
    )
    p_ledger.add_argument(
        "ledger_args",
        nargs=argparse.REMAINDER,
        help="progress | seed-bench | record ... | labeled-row ...",
    )
    p_pro = sub.add_parser(
        "pro-library",
        help="Aimbot-for-AI: transferable winning moves (sense/match/inject/learn), folded into behavioral systems",
    )
    p_pro.add_argument(
        "pro_args",
        nargs=argparse.REMAINDER,
        help="stats | seed | list | add --signature --kind --move | match --text | aim --text | fire <id> | learn <id> --outcome",
    )
    p_ghost = sub.add_parser(
        "ghost",
        help="Ghost in the Machine — silent steer deployment + experiment runner",
    )
    p_ghost.add_argument("--dry", action="store_true", help="Sense + match, write echo to trail only")
    p_ghost.add_argument("--observe", action="store_true", help="Sense + rashomon only, no whisper")
    p_ghost.add_argument("--probe", type=str, help="Deploy one specific steer text")
    p_ghost.add_argument("--list", action="store_true", help="List all available vectors")
    p_ghost.add_argument("--json", action="store_true", help="Machine-readable output")
    p_ghost.add_argument("--sense", action="store_true", help="Sense only — print state vector")
    p_ghost.add_argument("--swarm", type=str, default=None,
                         help="Deploy steer to all models in parallel")
    p_ghost.add_argument("--swarm-models", type=str, default=None,
                         help="Comma-separated models for swarm")
    p_ghost.add_argument("--temporal", action="store_true",
                         help="Run temporal experiment (staggered steers)")
    p_ghost.add_argument("--cascade", type=str, default=None,
                         help="Run cascade: initial_steer,depth")
    p_ghost.add_argument("--experiment", type=str, default=None,
                         help="Path to experiment YAML/JSON design")

    p_campaign = sub.add_parser(
        "campaign",
        help="D&D campaign module runner — Ghost+Riddler integration test harness",
    )
    p_campaign.add_argument("--module", type=str, default="campaigns/sunless_citadel/module.json",
                            help="Path to campaign module.json")
    p_campaign.add_argument("--room", type=str, default=None, help="Run a single room by id")
    p_campaign.add_argument("--all", action="store_true", help="Run all rooms in order")
    p_campaign.add_argument("--party", type=str, default="gemma:2b",
                            help="Comma-separated model names for party members")
    p_campaign.add_argument("--full-party", action="store_true", help="Use module's full party roster")
    p_campaign.add_argument("--dm", type=str, default="rules_engine",
                            help="DM model: rules_engine (deterministic) or deepseek")
    p_campaign.add_argument("--mode", type=str, default=None,
                            help="Experiment mode: v3_baseline or v4_defended")
    p_campaign.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    p_campaign.add_argument("--dry", action="store_true", help="Simulate without real model calls")
    p_campaign.add_argument("--json", action="store_true", help="Machine-readable output")

    p_xv = sub.add_parser(
        "cross-version",
        help="Cross-version experiment runner — v3 baseline vs v4 defended control-pattern testing",
    )
    p_xv.add_argument("xv_args", nargs=argparse.REMAINDER,
                      help="run --module <id> [--mode v3_baseline|v4_defended] [--runs N] [--dry] | list | report --module <id>")

    p_steer_compare = sub.add_parser(
        "steer-compare",
        help="Run identical steering experiments across providers (DeepSeek + local)",
    )
    p_steer_compare.add_argument("--all", action="store_true", help="Full matrix")
    p_steer_compare.add_argument("--baseline", action="store_true", help="Control group only")
    p_steer_compare.add_argument("--parallel", action="store_true", help="Run in parallel")
    p_steer_compare.add_argument("--task", type=str, default=None, help="Task: summary, list")
    p_steer_compare.add_argument("--steer", type=str, default=None, help="Steer vector key")
    p_steer_compare.add_argument("--providers", type=str, default=None,
                                  help="Comma-separated provider keys")
    p_steer_compare.add_argument("--json", action="store_true", help="Machine-readable output")
    p_steer_compare.add_argument("--pause", type=float, default=0.5,
                                  help="Pause between sequential calls")

    p_pile = sub.add_parser(
        "pile-classify",
        help="Overnight job: classify the state-summary pile with a local model → case law + training rows",
    )
    p_pile.add_argument(
        "pile_args",
        nargs=argparse.REMAINDER,
        help="[--limit N] [--model gemma4:latest] [--no-fold] [--json]",
    )
    p_snap = sub.add_parser(
        "state-snapshot",
        help="In-the-moment state summary capture for posterity + training",
    )
    p_snap.add_argument(
        "snap_args",
        nargs=argparse.REMAINDER,
        help="capture --goal ... --outcome ok --tier local [--lesson ...] | status",
    )
    p_clippy = sub.add_parser(
        "clippy",
        help="It looks like you're trying to work on Mag. Would you like a reminder?",
    )
    p_clippy.add_argument(
        "clippy_args",
        nargs=argparse.REMAINDER,
        help="[--json] — prints the standing reminder + live pile state",
    )
    p_st = sub.add_parser(
        "steer-telemetry",
        help="Passive steering telemetry + policy loop (tesuji-everywhere)",
    )
    p_st.add_argument(
        "st_args",
        nargs=argparse.REMAINDER,
        help="probe [--prob N] [--dry] | collect <task_id> | fold | apply --goal <goal>",
    )
    p_fkb = sub.add_parser(
        "fkb",
        help="Failure Knowledge Base: search recurring failures / stats",
    )
    p_fkb.add_argument(
        "fkb_args",
        nargs="*",
        help="stats | list [n] | search <query> | record <kind> <tool> <detail>",
    )
    p_agent = sub.add_parser(
        "agent",
        help="Tool-using CLI (DeepSeek/Ollama + Mag tools). Use when Grok tokens are empty.",
    )
    p_agent.add_argument(
        "-q",
        "--query",
        default="",
        help="One-shot goal then exit (else interactive REPL)",
    )
    p_agent.add_argument(
        "--provider",
        default="deepseek",
        help="Brain: deepseek (default) | ollama | openrouter | …",
    )
    p_agent.add_argument("--model", default="", help="Override model id")
    p_agent.add_argument("--tier", choices=("T0", "T1", "T2", "T3"), default="T2")
    p_agent.add_argument(
        "--read-only",
        action="store_true",
        help="Strip write tools from the schema grant (fan-out write-strip).",
    )
    p_orc = sub.add_parser(
        "orchestrator",
        help="Supervise isolated sub-agent tasks (spawn/kill/reap) - one window, short-lived workers",
    )
    p_orc.add_argument(
        "orc_args",
        nargs=argparse.REMAINDER,
        help="subcommand + args, passed to mag.orchestrator.main (run <goal> | list | status <id> | kill <id> | reap | self-test)",
    )

    p_gp = sub.add_parser(
        "gpipes",
        help="Governor pipes: parallel fan-out of sub-agents + merged collection (manifesto Phase 3)",
    )
    p_gp.add_argument(
        "gp_args",
        nargs=argparse.REMAINDER,
        help="subcommand + args, passed to mag.gpipes.main (fan <goals...> | collect <id> | status <id> | kill <id> | list)",
    )

    p_links = sub.add_parser(
        "links",
        help="Canonical URL link ledger (add/check/dupes — watch/inbox/LINKS.jsonl)",
    )
    links_sub = p_links.add_subparsers(dest="links_cmd")
    p_links_add = links_sub.add_parser("add", help="Register URL(s) in the ledger")
    p_links_add.add_argument("urls", nargs="+", help="URL(s) to file")
    p_links_add.add_argument("--note", default="", help="Note attached to every entry")
    p_links_add.add_argument("--writer", default="link_library", help="Writer tag on the entries")
    p_links_check = links_sub.add_parser(
        "check", help="Check one URL; exit 1 if its canonical is already on file"
    )
    p_links_check.add_argument("url", help="URL to check")
    links_sub.add_parser("dupes", help="Show duplicate canonicals on file")

    p_tan = sub.add_parser(
        "tangent",
        help="Queue/run background scout (Gemini/janitor); results in memory/tangents/",
    )
    p_tan.add_argument("prompt", nargs="*", help="Tangent ask (or --list / --process)")
    p_tan.add_argument("--list", action="store_true", help="List recent tangents")
    p_tan.add_argument("--process", action="store_true", help="Process queue (and optional --scan)")
    p_tan.add_argument("--scan", action="store_true", help="Scan live_from_grok for markers")
    p_tan.add_argument("--provider", default="", help="Force provider (e.g. gemini)")
    p_tan.add_argument("--no-run", action="store_true", help="Queue only, do not run yet")
    sub.add_parser(
        "hermes-status",
        help="Whether Nous Hermes Agent CLI is on PATH / HERMES_BIN",
    )
    p_imp = sub.add_parser(
        "improve",
        help="Daily improve loop: scout field → candidates → eval (gated promote)",
    )
    p_imp.add_argument(
        "--once",
        action="store_true",
        help="Scout + eval once (default if no mode flags)",
    )
    p_imp.add_argument("--scout", action="store_true", help="Outbound scout only")
    p_imp.add_argument("--eval", action="store_true", help="Run eval battery only")
    p_imp.add_argument(
        "--synthesize",
        action="store_true",
        help="Rank candidates → field_brief.md only (no scout)",
    )
    p_imp.add_argument(
        "--deepseek-rank",
        action="store_true",
        help="DeepSeek workhorse: verdict promote|hold|reject on top new/hold candidates (no auto-promote)",
    )
    p_imp.add_argument(
        "--top-n",
        type=int,
        default=5,
        help="With --deepseek-rank: how many ranked candidates (default 5)",
    )
    p_imp.add_argument("--status", action="store_true", help="Show candidate ledger summary")
    p_imp.add_argument(
        "--dry",
        action="store_true",
        help="Plan source keys + URLs without fetching",
    )
    p_imp.add_argument(
        "--deep",
        action="store_true",
        help="Opt-in deep dig: research-pack + local Ollama on ranked field tickets",
    )
    p_imp.add_argument(
        "--minutes",
        type=int,
        default=None,
        help="With --deep: wall-clock budget minutes (default 60 from improve.yaml)",
    )
    p_imp.add_argument(
        "--max-tickets",
        type=int,
        default=None,
        help="With --deep: max ranked tickets to dig (default 4)",
    )

    # t73 spec: deliberate-off flow for MagImproveDaily (t47 marker, t73 executor).
    # improve-off writes the intentional-disable marker
    # (logs/magimprove_intentional.flag, via mag.lifecycle.mark_improve_intentional)
    # FIRST and cites it in the result JSON, then disables the schtask
    # (schtasks /Change /TN MagImproveDaily /Disable). Marker write failure
    # aborts WITHOUT disabling: never a silent-disabled state.
    # improve-on re-registers the task via scripts/register_improve_task.ps1,
    # then clears the marker only on success. Tests mock the task commands;
    # never run these against the live task from a test.
    p_impoff = sub.add_parser(
        "improve-off",
        help=(
            "Deliberate-off: write the intentional-disable marker "
            "(logs/magimprove_intentional.flag, cited in output), then "
            "disable schtask MagImproveDaily. Spec: mag/lifecycle.py t73"
        ),
    )
    p_impoff.add_argument(
        "--reason",
        default="operator disable",
        help="Why improve is off; stored in the marker JSON (default: operator disable)",
    )
    p_impon = sub.add_parser(
        "improve-on",
        help=(
            "Deliberate-on: re-register schtask MagImproveDaily via "
            "scripts/register_improve_task.ps1, then clear the marker "
            "(only on success). Spec: mag/lifecycle.py t73"
        ),
    )

    p_il = sub.add_parser(
        "improve-loop",
        help="Unified improve cycle — cloud handoff + queue + nervous + spider",
    )
    p_il.add_argument(
        "il_action",
        nargs="?",
        default="cycle",
        choices=["cycle", "cloud-handoff", "ingest"],
    )
    p_il.add_argument("--goal", default="")
    p_il.add_argument("--claim", default="")
    p_il.add_argument("--brief", default="")
    p_il.add_argument("--source", default="local")
    p_il.add_argument("--max-improve", type=int, default=2)
    p_il.add_argument("--drain", action="store_true")
    p_il.add_argument("--scout", action="store_true")
    p_il.add_argument("--enqueue", action="store_true", help="cloud-handoff: run cycle after file")
    p_il.add_argument("--json", action="store_true")

    p_gc = sub.add_parser(
        "growth-cycle",
        help="Three-body growth cycle — probe + behavioral + improve + episode",
    )
    p_gc.add_argument(
        "gc_action",
        nargs="?",
        default="run",
        choices=["run", "status"],
    )
    p_gc.add_argument("--dry", action="store_true", help="Skip probe/scout/drain side effects")
    p_gc.add_argument("--no-drain", action="store_true", help="Force skip orchestrator drain")
    p_gc.add_argument("--json", action="store_true")

    p_lat = sub.add_parser(
        "lattice-loop",
        help="Conspiracy test lattice dig loop (Ollama self-directed research)",
    )
    p_lat.add_argument("--status", action="store_true", help="Lattice + dig state")
    p_lat.add_argument("--run", action="store_true", help="Start loop")
    p_lat.add_argument("--bg", action="store_true", help="With --run: background thread")
    p_lat.add_argument("--stop", action="store_true", help="Stop lattice loop")
    p_lat.add_argument(
        "--cycle-seconds",
        type=int,
        default=90,
        help="Seconds between dig units (default 90)",
    )
    p_lat.add_argument(
        "--max-cycles",
        type=int,
        default=0,
        help="0 = unlimited until --stop",
    )

    p_vdesk = sub.add_parser(
        "virtual-desk-loop",
        help="DeepSeek research loop on Mag virtual desk brief (REPORT.txt)",
    )
    p_vdesk.add_argument("--status", action="store_true", help="Loop + report state")
    p_vdesk.add_argument("--run", action="store_true", help="Start loop (foreground)")
    p_vdesk.add_argument("--once", action="store_true", help="Single DeepSeek cycle then exit")
    p_vdesk.add_argument("--dry", action="store_true", help="Plan next unit only")
    p_vdesk.add_argument("--bg", action="store_true", help="With --run: detached process")
    p_vdesk.add_argument("--stop", action="store_true", help="Stop virtual desk loop")
    p_vdesk.add_argument(
        "--cycle-seconds",
        type=int,
        default=120,
        help="Seconds between cycles (default 120)",
    )
    p_vdesk.add_argument(
        "--max-cycles",
        type=int,
        default=0,
        help="0 = unlimited until --stop or all units done",
    )
    p_vdesk.add_argument(
        "--provider",
        default="",
        help="Override provider (default deepseek from configs/virtual_desk.yaml)",
    )
    p_vdesk.add_argument(
        "--import",
        dest="import_path",
        metavar="FILE",
        default="",
        help="Import DeepSeek web export .txt into REPORT.txt",
    )
    p_vdesk.add_argument(
        "--import-url",
        default="",
        help="Optional share URL metadata for --import",
    )
    p_vdesk.add_argument(
        "--replace-report",
        action="store_true",
        help="With --import: replace REPORT.txt instead of append",
    )

    p_csess = sub.add_parser(
        "coding-session",
        help="Desk board coding session — seed canvas, preflight, status",
    )
    p_csess.add_argument(
        "action",
        nargs="?",
        default="status",
        choices=("seed", "plan", "orchestrate", "observe", "preflight", "status", "step", "close", "run"),
        help="seed | plan | orchestrate | observe | preflight | status | step | close | run",
    )
    p_csess.add_argument(
        "--ui-only",
        action="store_true",
        help="With preflight: UI smoke only (needs dashboard :8765 for live checks)",
    )
    p_csess.add_argument(
        "--dry",
        action="store_true",
        help="With step/orchestrate: advise only, no auto wake",
    )
    p_csess.add_argument(
        "--no-step",
        action="store_true",
        help="With orchestrate: PO/SM tick only, skip conductor Step",
    )
    p_csess.add_argument(
        "--note",
        default="",
        help="Operator note passed to conductor on step/orchestrate/run",
    )
    p_csess.add_argument(
        "--track",
        default="",
        help="With run: activate env track before sprint (mag/env_registry)",
    )
    p_csess.add_argument(
        "--max-ticks",
        type=int,
        default=50,
        help="With run: max orchestrator ticks before stall (default 50)",
    )
    p_csess.add_argument(
        "--force-new-seed",
        action="store_true",
        help="With run: re-seed desk when session is closed",
    )

    p_csess.add_argument(
        "--live",
        action="store_true",
        help="With observe: DeepSeek agent-as-judge critic (costs API tokens)",
    )

    p_fmac = sub.add_parser(
        "factory-machine",
        help="Full machine — branch, sprint, retrospective, bead, behavioral catalog",
    )
    p_fmac.add_argument(
        "fm_action",
        nargs="?",
        default="run",
        choices=("run", "status"),
        help="run | status",
    )
    p_fmac.add_argument("--note", default="", help="Operator goal for the sprint")
    p_fmac.add_argument(
        "--branch-prefix",
        default="mag/run",
        help="Git branch prefix (default mag/run)",
    )
    p_fmac.add_argument(
        "--config",
        dest="config_path",
        default="",
        help="Coding session config path (default configs/coding_session.yaml)",
    )
    p_fmac.add_argument(
        "--track",
        default="",
        help="Env track fallback when git branch fails",
    )
    p_fmac.add_argument("--max-ticks", type=int, default=50)
    p_fmac.add_argument("--dry", action="store_true", help="Advise only; skip bead side effects")
    p_fmac.add_argument(
        "--force-new-seed",
        action="store_true",
        help="Re-seed desk when session is closed (testing / new sprint)",
    )

    p_roadmap = sub.add_parser(
        "roadmap-run",
        help="Select the next filed roadmap gate and run it through the factory",
    )
    p_roadmap.add_argument(
        "roadmap_action",
        nargs="?",
        default="run",
        choices=("run", "prepare", "status"),
        help="run | prepare frozen contract only | status",
    )
    p_roadmap.add_argument("--version", default="", help="Optional version override, e.g. v5")
    p_roadmap.add_argument("--gate", default="", help="Optional gate override within the selected version")
    p_roadmap.add_argument("--max-ticks", type=int, default=50)
    p_roadmap.add_argument("--dry", action="store_true", help="Run factory in dry mode after preparing contract")

    p_csync = sub.add_parser(
        "canvas-sync",
        help="Sync Cursor Canvas *.tsx → memory/viewports/ manifests",
    )
    p_csync.add_argument(
        "--dry-run",
        action="store_true",
        help="Report counts only; do not write files",
    )

    sub.add_parser(
        "canvas-list",
        help="List synced canvas viewport manifests",
    )

    p_lq = sub.add_parser(
        "lattice-query",
        help="Query memory/lattice store (nodes/edges from lattice-backfill)",
    )
    p_lq.add_argument("--summary", action="store_true", help="Node/edge counts + themes")
    p_lq.add_argument("--theme", default="", help="Filter nodes by dominant theme")
    p_lq.add_argument("--neighbors", default="", help="Edges adjacent to node id")

    p_lbf = sub.add_parser(
        "lattice-backfill",
        help="Rebuild instrument verkle chain + seed memory/lattice store",
    )
    p_lbf.add_argument("--dry-run", action="store_true", help="Report counts only")

    p_va = sub.add_parser(
        "verkle-audit",
        help="Verkle chain audit, ticket reconcile, optional local synth",
    )
    p_va.add_argument("--full", action="store_true", help="Backfill lattice + synth + reconcile")
    p_va.add_argument("--synth", action="store_true", help="Local clerk pass per residual session")
    p_va.add_argument("--backfill", action="store_true", help="Run lattice-backfill first")
    p_va.add_argument("--dry", action="store_true", help="Plan only; no writes or LLM")
    p_va.add_argument("--no-reconcile", action="store_true", help="Skip ticket reconciliation")

    p_srb = sub.add_parser(
        "surface-rebuild",
        help="Shared-inbox INDEX fold rebuild + register heals (WO-10; heal classes: invisible/stale/missing)",
    )
    p_srb.add_argument("--dry", action="store_true", help="Census only; no heals, no fold calls")

    p_tr = sub.add_parser(
        "trajectory-rib",
        help="Compile bounded OpenClaw trajectory spans into a derived RIB",
    )
    p_tr.add_argument("--tape", default="watch/openclaw_traj.jsonl")
    p_tr.add_argument("--output", default="memory/runs/trajectory_rib/compiled.jsonl")
    p_tr.add_argument("--include-legacy", action="store_true", help="Inventory legacy rows as explicitly unbounded")

    sub.add_parser(
        "live-ops",
        help="Write zero-spend lifecycle readiness snapshot; never starts services",
    )

    p_la = sub.add_parser(
        "loop-audit",
        help="Mine autorun/orchestrator trails for wasteful loops (plan theater, stuck queue)",
    )
    p_la.add_argument("--json", action="store_true", help="JSON output")
    p_la.add_argument("--tail", type=int, default=2500, help="Autorun trail lines to scan")

    sub.add_parser(
        "ponytail-audit",
        help="Ponytail ladder scan — over-engineering only, not correctness",
    )

    p_v3 = sub.add_parser(
        "v3-status",
        help="v3 loop registry + research module health",
    )
    p_v3.add_argument("--json", action="store_true", help="JSON output")

    p_steward = sub.add_parser(
        "steward",
        help="Local steward jobs — scope cards, pattern digests (janitor clerk)",
    )
    p_steward.add_argument(
        "--job",
        default="steward-scope",
        choices=["steward-daily", "steward-scope", "steward-patterns", "steward-prompts"],
        help="Steward job id",
    )
    p_steward.add_argument("--slug", default="", help="BUILD slug for steward-scope")
    p_steward.add_argument("--dry", action="store_true", help="Plan only; no writes")
    p_steward.add_argument("--no-llm", action="store_true", help="Heuristic only (no Ollama)")
    p_steward.add_argument("--json", action="store_true", help="JSON output")
    p_steward.add_argument(
        "--fill",
        action="store_true",
        help="Enqueue steward jobs not yet run today",
    )

    p_spider = sub.add_parser(
        "spider",
        help="v3 meta-supervisor tick (rule Phase 0)",
    )
    p_spider.add_argument("--once", action="store_true", help="Single tick then exit")
    p_spider.add_argument("--dry", action="store_true", help="No steer injection")
    p_spider.add_argument("--inject", action="store_true", help="Post steer to stalled tasks")

    p_res = sub.add_parser(
        "resonance",
        help="v3 corpus lens — soil echoes into pack L0e",
    )
    p_res.add_argument("--tick", action="store_true", help="Score and optionally FILE findings")
    p_res.add_argument("--dry", action="store_true", help="No writes")
    p_res.add_argument("--goal", default="", help="Goal hint for scoring")

    p_cond = sub.add_parser(
        "conductor",
        help="v3 orchestration overlay on route.v2",
    )
    p_cond.add_argument("goal", nargs="?", default="", help="Goal to route")
    p_cond.add_argument("--dry", action="store_true", help="No trail write")
    p_cond.add_argument("--json", action="store_true", help="JSON output")
    p_cond.add_argument("--eval", action="store_true", help="Run deterministic v4 conductor evaluation")
    p_cond.add_argument("--no-write", action="store_true", help="Do not file evaluation artifact")

    p_grove = sub.add_parser(
        "grove-build",
        help="v3 Tesuji Grove — scan remedies/skills → poem nodes",
    )
    p_grove.add_argument("--dry", action="store_true", help="Plan only; no writes")
    p_grove.add_argument("--list", action="store_true", help="List recent nodes")
    p_grove.add_argument("--json", action="store_true", help="JSON output")

    p_train = sub.add_parser(
        "training-events",
        help="Unified orchestration training events (v3-005)",
    )
    p_train.add_argument("--stats", action="store_true", help="Event counts by pattern")
    p_train.add_argument("--export", action="store_true", help="Export T2-redacted JSONL")
    p_train.add_argument("--pattern", default="", help="Filter by pattern type")
    p_train.add_argument("--json", action="store_true", help="JSON output")

    p_vast_train = sub.add_parser(
        "vast-train",
        help="Validate a redacted training export and estimate a Vast job",
    )
    p_vast_train.add_argument("--dry", action="store_true", help="Validate and estimate only; never launch")
    p_vast_train.add_argument("--export-path", required=True, help="Training export JSONL path")
    p_vast_train.add_argument("--base-model", default=None, help="Configured base-model id")
    p_vast_train.add_argument("--max-hours", type=float, default=None, help="Hard runtime cap")

    p_tshell = sub.add_parser(
        "tesuji-shell",
        help="Log emergent wins / brilliant moves (symmetric to behavioral errors)",
    )
    p_tshell.add_argument(
        "ts_action",
        nargs="?",
        default="status",
        choices=["log", "synth", "status"],
        help="log|synth|status",
    )
    p_tshell.add_argument("what", nargs="?", default="", help="What happened (log)")
    p_tshell.add_argument("--surprise", default="", help="Why it surprised (log)")
    p_tshell.add_argument(
        "--maps-to",
        default="",
        help="Optional link: remedy:ID, skill:id, tesuji:path",
    )
    p_tshell.add_argument("--source", default="cli", help="Source tag (log)")
    p_tshell.add_argument("--json", action="store_true", help="JSON output")

    p_rw = sub.add_parser(
        "run-worth",
        help="Evaluate long runs before auto-truncate (symmetric to behavioral)",
    )
    p_rw.add_argument(
        "rw_action",
        nargs="?",
        default="status",
        choices=["status", "evaluate", "mark-good"],
        help="status|evaluate|mark-good",
    )
    p_rw.add_argument("run_id", nargs="?", default="", help="Run id (evaluate/mark-good)")
    p_rw.add_argument("--task-id", default="", help="Orchestrator task id (evaluate hung)")
    p_rw.add_argument("--note", default="", help="Why this long run was good (mark-good)")
    p_rw.add_argument("--json", action="store_true", help="JSON output")

    p_rel = sub.add_parser(
        "release",
        help="Version registry + graduation gates (behavioral memory)",
    )
    p_rel.add_argument(
        "action",
        nargs="?",
        default="status",
        choices=["status", "notes", "record", "gates"],
        help="status|notes|record|gates",
    )
    p_rel.add_argument("version", nargs="?", default="", help="v1|v2|v3… for notes/record/gates")
    p_rel.add_argument("--gate", default="", help="Gate id for record (e.g. run_a)")
    p_rel.add_argument("--ok", action="store_true", help="Gate passed")
    p_rel.add_argument("--fail", action="store_true", help="Gate failed")
    p_rel.add_argument("--note", default="", help="Evidence note for record")
    p_rel.add_argument("--evidence", default="", help="Path to evidence artifact")
    p_rel.add_argument("--json", action="store_true", help="JSON output")
    p_rel.add_argument(
        "--map",
        action="store_true",
        help="Subprocess analog view (Mag loops/modules steal)",
    )

    p_cm = sub.add_parser(
        "caveman-audit",
        help="Caveman doc density scan — filler, long lines",
    )
    p_cm.add_argument("--path", default="", help="File or dir to scan (default: docs/ref)")
    p_cm.add_argument("--json", action="store_true", help="JSON output")

    p_ba = sub.add_parser(
        "build-audit",
        help="Factory audit — write build_audit.v1 JSON to memory/runs/build_audit/",
    )
    p_ba.add_argument("--slug", required=True, help="Build slug (e.g. factory-audit-json)")
    p_ba.add_argument(
        "--verdict",
        default="pending",
        choices=["pass", "fix", "reject", "pending"],
        help="Audit verdict",
    )
    p_ba.add_argument("--spec-path", default="", help="Frozen BUILD spec path")
    p_ba.add_argument("--command", action="append", default=[], dest="commands", help="Command run (repeatable)")
    p_ba.add_argument("--note", default="", help="Auditor note")
    p_ba.add_argument("--dry", action="store_true", help="Print record without writing")
    p_ba.add_argument("--json", action="store_true", help="JSON output")

    p_fa = sub.add_parser(
        "factory-audit",
        help="Alias for build-audit (BUILD spec naming)",
    )
    p_fa.add_argument("--slug", required=True, help="Build slug")
    p_fa.add_argument(
        "--verdict",
        default="pending",
        choices=["pass", "fix", "reject", "pending"],
    )
    p_fa.add_argument("--spec-path", default="")
    p_fa.add_argument("--command", action="append", default=[], dest="commands")
    p_fa.add_argument("--note", default="")
    p_fa.add_argument("--dry", action="store_true")
    p_fa.add_argument("--json", action="store_true")

    p_skill = sub.add_parser(
        "skill-seat",
        help="Ponytail / caveman agent skill preambles + audit gates",
    )
    p_skill.add_argument(
        "action",
        choices=["status", "pick", "preamble", "gate"],
        help="status|pick|preamble|gate",
    )
    p_skill.add_argument("text", nargs="*", help="Goal text for pick/preamble")
    p_skill.add_argument("--skill", default="", help="ponytail|caveman for preamble/gate")
    p_skill.add_argument("--path", default="", help="Path for caveman gate")
    p_skill.add_argument("--json", action="store_true", help="JSON output")

    p_sw = sub.add_parser(
        "switchboard",
        help="Unified seat mesh — peers, reap, tier-bounded steer drops",
    )
    p_sw.add_argument(
        "action",
        nargs="?",
        default="status",
        choices=["status", "mesh", "peers", "reap", "drop", "route", "self-test"],
        help="status|mesh|peers|reap|drop|route|self-test",
    )
    p_sw.add_argument("rest", nargs="*", help="drop target + context, or route goal")
    p_sw.add_argument("--from", dest="from_ref", default="operator", help="drop source peer")
    p_sw.add_argument("--tier", default="T2", help="drop tier T0-T3")
    p_sw.add_argument("--spooky", action="store_true", help="Lawful cross-seat share label")
    p_sw.add_argument("--dry", action="store_true", help="Plan only")
    p_sw.add_argument("--live", action="store_true", help="peers: running tasks only")
    p_sw.add_argument("--group", default="", help="peers: filter by group")
    p_sw.add_argument("--json", action="store_true", help="JSON output for status")

    p_arena = sub.add_parser(
        "arena",
        help="Agent arena learning — league, tournament probes, routing hints",
    )
    p_arena.add_argument(
        "action",
        nargs="?",
        default="status",
        choices=["status", "league", "tournament", "routing", "probe", "games"],
        help="status|league|tournament|routing|probe|games",
    )
    p_arena.add_argument("--game", default="chess", help="Game type (chess or TextArena env_id)")
    p_arena.add_argument("--game-id", default="", help="TextArena env_id for probe (e.g. TicTacToe-v0)")
    p_arena.add_argument("--probe-type", default="", help="Filter league/routing by probe_type")
    p_arena.add_argument("--render", action="store_true", help="probe: SimpleRenderWrapper")
    p_arena.add_argument("--rounds", type=int, default=1, help="Tournament rounds")
    p_arena.add_argument("--seats", default="local,remote", help="Comma seats for tournament")
    p_arena.add_argument("--task", default="structured_handoff", help="Routing task kind")
    p_arena.add_argument("--budget", default="low", help="Routing budget low|high")
    p_arena.add_argument("--json", action="store_true", help="JSON output")

    p_seats = sub.add_parser(
        "seats",
        help="Unified seat registry — register desktop/cloud seats with orchestrator mesh",
    )
    p_seats.add_argument(
        "action",
        nargs="?",
        default="list",
        choices=["register", "heartbeat", "unregister", "list"],
    )
    p_seats.add_argument("rest", nargs="*", help="task_id for heartbeat/unregister")
    p_seats.add_argument("--seat", default="cursor")
    p_seats.add_argument("--goal", default="")
    p_seats.add_argument("--mode", default="interactive")
    p_seats.add_argument("--task-id", default="")
    p_seats.add_argument("--pid", type=int, default=None)
    p_seats.add_argument("--tag", default="")
    p_seats.add_argument("--parent", default="desktop")
    p_seats.add_argument("--phase", default="")
    p_seats.add_argument("--status", default="done")
    p_seats.add_argument("--detail", default="")
    p_seats.add_argument("--live", action="store_true")
    p_seats.add_argument("--json", action="store_true")

    p_unsloth = sub.add_parser(
        "unsloth",
        help="Unsloth Studio GPU seat — status, start chat/agent, stop",
    )
    p_unsloth.add_argument(
        "action",
        nargs="?",
        default="status",
        choices=["status", "start", "stop"],
    )
    p_unsloth.add_argument("--mode", default="chat", choices=["chat", "agent"])
    p_unsloth.add_argument("--model", default="", help="Model id/path for chat mode")
    p_unsloth.add_argument("--agent", default="hermes", help="Agent for start mode")
    p_unsloth.add_argument("--no-register", action="store_true", help="Skip seat_registry on start")
    p_unsloth.add_argument("--json", action="store_true")

    p_power = sub.add_parser(
        "power",
        help="Kill switch / turn-on / stack status (no whack-a-mole)",
    )
    p_power.add_argument(
        "action",
        nargs="?",
        default="status",
        choices=["status", "stop", "start"],
    )
    p_power.add_argument("--json", action="store_true")
    p_power.add_argument("--browser", action="store_true", help="open dashboard after start")

    p_cost = sub.add_parser(
        "cost-sim",
        help="Simulate swarm token/$ cost before dispatch (configs/cost_rates.yaml)",
    )
    p_cost.add_argument("cs_action", nargs="?", default="wave", choices=["wave", "goal"])
    p_cost.add_argument("text", nargs="?", default="v3-epic")
    p_cost.add_argument("--improve", type=int, default=2)
    p_cost.add_argument("--build", type=int, default=3)
    p_cost.add_argument("--audit", type=int, default=1)
    p_cost.add_argument("--no-plan", action="store_true")
    p_cost.add_argument("--seat", default="")
    p_cost.add_argument("--pack", default="")
    p_cost.add_argument("--dry", action="store_true")
    p_cost.add_argument("--json", action="store_true")

    p_blast = sub.add_parser(
        "blast",
        help="Full-blast self-improve plant with influence dials (dash + CLI)",
    )
    p_blast.add_argument("--status", action="store_true", help="Show plant + ollama + influence")
    p_blast.add_argument("--run", action="store_true", help="Start blast (foreground unless --bg)")
    p_blast.add_argument("--bg", action="store_true", help="With --run: background thread")
    p_blast.add_argument("--stop", action="store_true", help="Stop blast plant")
    p_blast.add_argument("--pause", action="store_true", help="Pause digs (keep plant alive)")
    p_blast.add_argument("--resume", action="store_true", help="Resume after pause")
    p_blast.add_argument("--focus", default="", help="Set operator focus text (steers digs)")
    p_blast.add_argument("--minutes", type=int, default=None, help="dig_minutes dial")
    p_blast.add_argument("--max-tickets", type=int, default=None, help="max_tickets dial")
    p_blast.add_argument("--cycle-seconds", type=int, default=None, help="seconds between dig cycles")

    p_promo = sub.add_parser(
        "promote",
        help="Human gate: apply or reject an improve candidate id",
    )
    p_promo.add_argument("candidate_id", help="Candidate id (c-…)")
    p_promo.add_argument(
        "--apply",
        action="store_true",
        help="Mark promoted (practices → playbook; models do not auto-edit lanes)",
    )
    p_promo.add_argument("--reject", action="store_true", help="Mark rejected")
    p_promo.add_argument("--reason", default="", help="Reject/promote note")
    p_promo.add_argument(
        "--force-model",
        action="store_true",
        help="With --apply: allow model promote path (still no auto lanes write in v1)",
    )

    p_rp = sub.add_parser(
        "research-pack",
        help="Scrape URLs → clean ask PDF/JSON for lesser models (local-first routing)",
    )
    p_rp.add_argument("--ask", required=True, help="The ask / research question")
    p_rp.add_argument("--url", action="append", default=[], help="Source URL (repeatable)")
    p_rp.add_argument("--title", default="", help="Short title")
    p_rp.add_argument(
        "--criterion",
        action="append",
        default=[],
        help="Success criterion for lesser models (repeatable)",
    )
    p_rp.add_argument(
        "--run",
        action="store_true",
        help="After build, run local worker on the pack",
    )
    p_rp.add_argument(
        "--elevate",
        action="store_true",
        help="After build, emit Grok-elevation payload (pack only)",
    )
    p_rp.add_argument("--provider", default="", help="With --run: force remote provider")

    p_lab = sub.add_parser(
        "lab",
        help="Integral Mag: one process = watch + companion + dashboard (default)",
    )
    p_lab.add_argument("--host", default=None, help="Override bind host (0.0.0.0 requires --lan)")
    p_lab.add_argument("--port", type=int, default=8765)
    p_lab.add_argument(
        "--lan",
        action="store_true",
        help="Listen on all interfaces for phone/tablet on WiFi (explicit opt-in; saved for desk reload)",
    )
    p_lab.add_argument(
        "--local-only",
        action="store_true",
        help="Force 127.0.0.1 and clear saved LAN preference",
    )
    p_lab.add_argument(
        "--ui-only",
        action="store_true",
        help="Dashboard only (no watch/mag) — not recommended day-to-day",
    )
    p_lab.add_argument(
        "--no-dashboard",
        action="store_true",
        help="Mag+watch only, no HTTP UI",
    )
    p_lab.add_argument(
        "--with-cast",
        action="store_true",
        help="Also start read-only cast receiver on :8766 (Roku/phone viewport)",
    )
    p_lab.add_argument(
        "--cast-lan",
        action="store_true",
        help="With --with-cast, expose cast on WiFi (desk bind unchanged)",
    )
    p_lab.add_argument(
        "--with-instrument",
        action="store_true",
        help="Print strike desk hint only (optional analysis, not Mag home)",
    )

    p_cast = sub.add_parser(
        "cast",
        help="Read-only cast receiver for TV/phone (Spotify→Roku style) — no desk control",
    )
    p_cast.add_argument("--host", default=None, help="Override bind host (0.0.0.0 requires --lan)")
    p_cast.add_argument("--port", type=int, default=8766)
    p_cast.add_argument(
        "--lan",
        action="store_true",
        help="Listen on WiFi for receivers you point at manually (read-only :8766)",
    )
    p_cast.add_argument(
        "--local-only",
        action="store_true",
        help="Force 127.0.0.1 and clear saved cast LAN preference",
    )

    p_desk = sub.add_parser(
        "desk",
        help="Desk refresh/wipe/reload — no UI clicks (uses :8765 API)",
    )
    p_desk.add_argument(
        "action",
        choices=["refresh", "wipe", "reset", "restart-lab", "reload", "local-only", "status"],
        help="refresh=clear dialogue+ping ollama; wipe=fresh canvas; reload=restart lab+refresh; local-only=127.0.0.1 only",
    )
    p_desk.add_argument("--port", type=int, default=8765)
    p_desk.add_argument("--json", action="store_true", help="JSON output")
    p_desk.add_argument(
        "--keep-dialogue",
        action="store_true",
        help="refresh only: do not clear dialogue log",
    )
    p_desk.add_argument(
        "--clear-canvas",
        action="store_true",
        help="reset only: strip ## Dialogue from canvas",
    )

    p_ollama = sub.add_parser(
        "ollama",
        help="Ollama GPU policy — one-hot unload on 6GB AMD",
    )
    p_ollama.add_argument(
        "action",
        choices=["status", "one-hot"],
        help="status | one-hot (evict extra loaded models)",
    )
    p_ollama.add_argument("--keep", default="", help="Model to keep hot (default desk model)")
    p_ollama.add_argument("--json", action="store_true")

    p_probe_local = sub.add_parser(
        "probe-local",
        help="Local GPU probes — desk model A/B, GSTD route test",
    )
    p_probe_local.add_argument(
        "target",
        choices=["desk-models", "gstd", "steal-protocol"],
        help="desk-models | gstd | steal-protocol: clone inventory",
    )
    p_probe_local.add_argument("--no-pull", action="store_true", help="desk-models: skip qwen pull")
    p_probe_local.add_argument("--no-bench", action="store_true", help="gstd: skip local ollama bench")
    p_probe_local.add_argument("--json", action="store_true")

    p_sched = sub.add_parser(
        "scheduler",
        help="Local GPU task queue — status, steer, triage",
    )
    p_sched.add_argument(
        "action",
        choices=["status", "pause", "continue", "escape", "triage", "steer"],
        nargs="?",
        default="status",
    )
    p_sched.add_argument("text", nargs="?", default="", help="For steer: priority needle or !steer text")
    p_sched.add_argument("--json", action="store_true")

    p_operator = sub.add_parser(
        "operator-mode",
        help="Shared durable autonomy switch — status, pause, resume",
    )
    p_operator.add_argument("action", choices=["status", "pause", "resume"], nargs="?", default="status")
    p_operator.add_argument("reason", nargs="*", default=[], help="Pause/resume reason")
    p_operator.add_argument("--scope", choices=["autonomous", "all_agents"], default="autonomous")
    p_operator.add_argument("--until", default=None, help="Optional ISO-8601 expiry for a pause")
    p_operator.add_argument("--json", action="store_true")

    p_realign = sub.add_parser(
        "realign",
        help="Operator realignment: NEEDS YOU / MOVED / IGNORED since your last visit",
    )
    p_realign.add_argument(
        "--mark-visited",
        action="store_true",
        help="Stamp this visit after rendering (next run shows only the new stuff)",
    )

    p_env = sub.add_parser(
        "env",
        help="Cutting-edge environment tracks (branch + port isolation)",
    )
    p_env.add_argument(
        "action",
        choices=["list", "status", "use"],
        help="list | status | use <track>",
    )
    p_env.add_argument("track", nargs="?", default=None, help="Track name for use")

    p_peer = sub.add_parser(
        "peer-handoff",
        help="File/list cross-agent instructions (coordination + handoff queue)",
    )
    p_peer.add_argument(
        "action",
        choices=["file", "list", "latest"],
        help="file | list | latest",
    )
    p_peer.add_argument("--goal", default="")
    p_peer.add_argument("--brief", default="")
    p_peer.add_argument("--from", dest="from_seat", default="cursor-cloud")
    p_peer.add_argument("--to", dest="to_seat", default="home-pc")
    p_peer.add_argument("--track", dest="env_track", default=None)
    p_peer.add_argument("--command", action="append", dest="commands", default=[])
    p_peer.add_argument("--pr", dest="pr_url", default="")
    p_peer.add_argument("--merge-target", default="")
    p_peer.add_argument("--enqueue", action="store_true")

    # bare: python main.py "goal..."
    args, rest = parser.parse_known_args(argv)
    if args.cmd is None:
        if rest:
            return cmd_run(" ".join(rest))
        if argv and not any(a.startswith("-") for a in (argv or [])):
            return cmd_run(" ".join(argv))
        parser.print_help()
        return 2

    if args.cmd == "run":
        return cmd_run(" ".join(args.goal), thread_id=args.thread)
    if args.cmd == "plan":
        from mag.plan import plan_gate, list_plans, load_plan, set_status

        if args.action == "list":
            for pl in list_plans():
                print(f"{pl['plan_id']}  [{pl['status']}]  {pl['goal'][:70]}")
            return 0
        if args.action == "show":
            pl = load_plan(args.plan_id) if args.plan_id else None
            if not pl:
                print("no such plan")
                return 1
            print(__import__("json").dumps(pl, indent=2, ensure_ascii=False))
            return 0
        if args.action in ("approve", "reject"):
            if not args.plan_id:
                print("need plan_id")
                return 1
            pl = set_status(args.plan_id, "approved" if args.action == "approve" else "rejected")
            if not pl:
                print("no such plan")
                return 1
            print(f"{args.plan_id} -> {pl['status']}")
            return 0
        if args.action == "edit":
            if not args.plan_id:
                print("need plan_id")
                return 1
            pl = load_plan(args.plan_id)
            if not pl:
                print("no such plan")
                return 1
            print("Edit fields in the JSON file, then re-run `plan approve <id>`.")
            print(__import__("json").dumps(pl, indent=2, ensure_ascii=False))
            return 0
        # default: fire gate on a goal
        if args.goal:
            res = plan_gate(args.goal)
            print(__import__("json").dumps(res, indent=2, ensure_ascii=False)[:4000])
            return 0
        print("usage: plan list | plan approve <id> | plan reject <id> | plan --goal '<goal>'")
        return 2
    if args.cmd == "status":
        return cmd_status()
    if args.cmd == "ingest":
        return cmd_ingest_result(args.handoff_id)
    if args.cmd == "watch":
        from watch.tail_session import loop, once

        if args.once:
            return once()
        loop(args.interval)
        return 0
    if args.cmd == "summarize-session":
        from mag.biography import summarize_session
        from watch.tail_session import resolve_session

        if getattr(args, "all_agents", False):
            from mag.chat_source import file_dirty_agent_sessions

            res = file_dirty_agent_sessions(
                use_llm=not args.no_llm,
                force=bool(args.force),
            )
            print(json.dumps(res, indent=2))
            return 0 if res.get("ok") else 1

        sid = args.session.strip()
        src = (getattr(args, "source", None) or "auto").strip()
        if src == "agent":
            src = "mag_agent"
        if not sid:
            if src == "mag_agent":
                sid = "dashboard"
            else:
                resolved = resolve_session()
                if not resolved:
                    print("no active session; pass --session <id> or --source mag_agent")
                    return 1
                sid = resolved[0]
        # Bare agent seat name + auto → prefer agent FILE helper
        if src in ("mag_agent", "auto") and not sid.startswith("019") and "mag-agent" not in sid:
            from mag.chat_source import agent_session_path, file_agent_session

            if agent_session_path(sid).is_file() or src == "mag_agent":
                res = file_agent_session(
                    sid,
                    use_llm=not args.no_llm,
                    force=bool(args.force),
                    pdf=bool(getattr(args, "pdf", False)),
                    visual=bool(getattr(args, "visual", False)),
                )
                print(json.dumps(res, indent=2))
                return 0 if res.get("ok") else 1
        res = summarize_session(
            sid,
            source=src,
            use_llm=not args.no_llm,
            force=args.force,
            pdf=bool(getattr(args, "pdf", False)),
            visual=bool(getattr(args, "visual", False)),
        )
        print(json.dumps(res, indent=2))
        return 0 if res.get("ok") else 1
    if args.cmd == "knot-evolution":
        from mag.verkle_knot import evolution_summary

        print(json.dumps(evolution_summary(), indent=2))
        return 0
    if args.cmd == "dashboard":
        from config import resolve_bind_host
        from dashboard.server import run as run_dashboard

        host = resolve_bind_host(
            lan=bool(getattr(args, "lan", False)),
            local_only=bool(getattr(args, "local_only", False)),
            host_override=getattr(args, "host", None),
            port=args.port,
        )
        run_dashboard(host=host, port=args.port, tls=bool(getattr(args, "lan", False)))

    if args.cmd == "api":
        return cmd_api(host=args.host, port=args.port)
        return 0
    if args.cmd == "mag":
        if args.no_harness:
            # patch policy file flag in-process via env
            import os

            os.environ["MAG_NO_HARNESS"] = "1"
        from mag.daemon import run_loop
        from mag.policy import load_policy

        pol = load_policy()
        if args.no_harness or __import__("os").environ.get("MAG_NO_HARNESS"):
            pol["use_grok_harness"] = False
            # monkey-affect: rewrite sense to see env
            import mag.act as act_mod

            _orig = act_mod.load_policy

            def _pol():
                p = _orig()
                p["use_grok_harness"] = False
                return p

            act_mod.load_policy = _pol  # type: ignore
        run_loop(interval=args.interval, once=args.once)
        return 0
    if args.cmd == "brief":
        from mag.brief_local import write_brief

        res = write_brief(
            None if args.session in ("", "latest") else args.session,
            use_llm=not args.no_llm,
        )
        print(json.dumps(res, indent=2))
        return 0 if res.get("ok") else 1
    if args.cmd == "ask":
        from mag.ask import ask as mag_ask

        q = " ".join(args.question)
        res = mag_ask(
            q,
            session_id=args.session.strip() or None,
            use_llm=not args.no_llm,
            speak=not args.no_speak,
        )
        if res.get("answer"):
            print(res["answer"])
        else:
            print(json.dumps(res, indent=2))
        return 0 if res.get("ok") else 1

    if args.cmd == "talk":
        """Talk to Ghost: python main.py talk "what's the verkle status?" """
        import time as _time
        from datetime import datetime, timezone
        from mag.task_router import route_task

        q = " ".join(args.query)
        msg_id = f"talk-{uuid.uuid4().hex[:8]}"

        # Auto-route to optimal model unless explicitly overridden
        if args.provider == "ollama" and args.model == "qwen2.5-coder:7b":
            route = route_task(q)
            provider = route["provider"]
            model = route["model"]
            cost = route["cost_est"]
        else:
            provider = args.provider
            model = args.model
            cost = 0.0 if provider == "ollama" else 0.00013

        timeout = args.timeout

        msg = {
            "id": msg_id, "action": "exec", "goal": q,
            "provider": provider, "model": model,
            "timeout_s": timeout,
            "ts": datetime.now(timezone.utc).isoformat(),
            "source": "talk-cli",
        }

        inbox = ROOT / "memory" / "copilot" / "inbox.jsonl"
        inbox.parent.mkdir(parents=True, exist_ok=True)
        with open(inbox, "a", encoding="utf-8") as f:
            f.write(json.dumps(msg, ensure_ascii=False) + "\n")

        if not args.json:
            print(f"🤖 Ghost ({provider}/{model}, \${cost}): {q[:100]}{'...' if len(q) > 100 else ''}")

        outbox_file = ROOT / "memory" / "copilot" / "outbox" / f"{msg_id}.json"
        waited = 0
        while waited < timeout:
            _time.sleep(1)
            waited += 1
            if outbox_file.is_file():
                try:
                    result = json.loads(outbox_file.read_text(encoding="utf-8"))
                    if result.get("outcome") in ("spawned", "completed", "error", "spawn_failed"):
                        task_id = result.get("task_id", "?")

                        # If spawned, wait for orchestrator task to complete
                        if result.get("outcome") == "spawned" and task_id != "?":
                            task_file = ROOT / "memory" / "runs" / "orchestrator" / "tasks" / f"{task_id}.json"
                            task_waited = 0
                            while task_waited < timeout:
                                _time.sleep(2)
                                task_waited += 2
                                if task_file.is_file():
                                    try:
                                        task = json.loads(task_file.read_text(encoding="utf-8"))
                                        if task.get("status") in ("done", "failed", "timeout", "killed"):
                                            if args.json:
                                                print(json.dumps(task, indent=2, default=str))
                                            else:
                                                print(f"\n✅ Task {task_id}: {task.get('status')}")
                                                # Try to read agent output
                                                log = task.get("log", "")
                                                if log and Path(log).is_file():
                                                    try:
                                                        output = Path(log).read_text(encoding="utf-8", errors="replace")
                                                        if len(output) > 2000:
                                                            output = output[-2000:]
                                                        print(f"--- agent output ---\n{output}")
                                                    except Exception:
                                                        pass
                                            return 0 if task.get("status") == "done" else 1
                                    except Exception:
                                        pass

                        if args.json:
                            print(json.dumps(result, indent=2, default=str))
                        else:
                            print(f"\n📬 Ghost: outcome={result.get('outcome')} task={task_id}")
                        return 0 if result.get("outcome") != "error" else 1
                except (json.JSONDecodeError, OSError):
                    pass

        print(f"\n⏰ Timeout after {timeout}s. Task may still be running.")
        print(f"   Check: {outbox_file}")
        return 1

    if args.cmd == "swarm":
        """Fire parallel research swarm: python main.py swarm "analyze the leak detector" --size 3"""
        from mag.task_router import fire_swarm
        q = " ".join(args.goal)
        result = fire_swarm(q, swarm_size=args.size, dry=args.dry)
        if args.dry:
            print(f"🪲 SWARM PREVIEW: {result['tasks']} agents, \${result['total_cost']}")
            for angle in result["angles"]:
                print(f"   {angle}")
        else:
            print(f"🪲 SWARM FIRED: {result['fired']} tasks, \${result['total_cost']}")
            print(f"   Swarm ID: {result['swarm_id']}")
            for i, tid in enumerate(result["task_ids"]):
                print(f"   [{i}] {tid} → {result['angles'][i]}")
            print(f"\n   Ghost processes on next cycle. Check /api/v1/lattice for results.")
        return 0

    if args.cmd == "tts":
        from mag.tts import speak

        text = " ".join(args.text)
        ok = speak(text, force=True)
        print(f"tts ok={ok}")
        return 0 if ok else 1
    if args.cmd == "workshop":
        from mag.socratic import workshop

        res = workshop(" ".join(args.prompt), rounds=args.rounds, speak_result=not args.no_speak)
        if not res.get("ok"):
            print(json.dumps(res, indent=2))
            return 1
        print("=== FINAL PROMPT ===")
        print(res["final"])
        return 0
    if args.cmd == "session-route":
        from mag.session_route import main as sroute_main

        return sroute_main(
            (["--state", args.state] if args.state else [])
            + (["--json"] if args.json else [])
            + list(args.goal)
        )
    if args.cmd == "ghost-summon":
        from mag.ghost_summon import main as gsummon_main

        return gsummon_main(
            (["--reason"] if args.reason else [])
            + (["--model", args.model] if args.model else [])
            + list(args.context)
        )
    if args.cmd == "legacy-audit":
        from mag.legacy_audit import main as legacy_main

        return legacy_main(
            [args.legacy_cmd] + (["--dry"] if getattr(args, "dry", False) else [])
        )
    if args.cmd == "visual":
        from mag.visual_pack import write_visual_pack

        res = write_visual_pack(
            None if args.session in ("", "latest") else args.session
        )
        print(json.dumps(res, indent=2))
        return 0 if res.get("ok") else 1
    if args.cmd == "doctor":
        from mag.health import sanity
        from mag.guard import doctor_print

        s = sanity()
        doctor_print(s)
        print(json.dumps(s, indent=2, default=str)[:4000])
        return 0
    if args.cmd == "game":
        from mag import game_ramp

        gcmd = getattr(args, "game_cmd", None) or "status"
        if gcmd == "play":
            _print_game_turn(game_ramp.play(" ".join(getattr(args, "action", ["look"]))))
        elif gcmd == "map":
            from mag.game_play import map as _gp_map
            m = _gp_map()
            if m.get("ok"):
                print(m.get("map", ""))
                print("\nOBJECTIVE:", m.get("objective", ""))
            else:
                print(m.get("error", "map unavailable"))
        elif gcmd == "render":
            print(game_ramp.render().get("ascii", "(no render)"))
        elif gcmd == "descend":
            _print_game_turn(game_ramp.descend())
        else:
            _print_game_status(game_ramp.status())
        return 0
    if args.cmd == "scrum":
        from mag.scrum import main as scrum_main

        return scrum_main(
            [args.cmd] + (["--apply"] if getattr(args, "apply", False) else [])
        )
        return 0 if s.get("status") == "up" else 1
    if args.cmd == "catch-up":
        from mag.health import catch_up

        res = catch_up()
        print(json.dumps(res, indent=2, default=str))
        return 0 if res.get("ok") else 1
    if args.cmd == "probe-lanes":
        from models.probe import probe_all

        res = probe_all(include_l1_chat=not args.no_l1)
        print(json.dumps(res, indent=2, default=str))
        return 0 if res.get("ok") else 1
    if args.cmd == "guard":
        from mag.guard import guard_loop

        guard_loop(interval=args.interval, once=args.once, restart=args.restart)
        return 0
    if args.cmd == "boot":
        from mag.boot import run_boot

        report = run_boot(ensure=args.ensure, light=args.light)
        if args.json:
            print(json.dumps(report, indent=2, default=str)[:8000])
        else:
            print(report.get("text") or json.dumps(report, indent=2, default=str)[:2000])
        return 0 if report.get("ok") else 1
    if args.cmd == "boot-coordination":
        from mag.tripartite_boot import run_coordinated_boot

        res = run_coordinated_boot(actor=args.actor, seat=args.seat)
        print(json.dumps(res, indent=2, default=str))
        return 0 if res.get("ok") else 1
    if args.cmd == "pack-status":
        from mag.records import format_pack_report_text, pack_report, write_kpi

        rep = pack_report(None if args.session in ("all", "*", "") else args.session)
        write_kpi(source="pack-status")
        if args.json:
            print(json.dumps(rep, indent=2, default=str)[:12000])
        else:
            print(format_pack_report_text(rep))
        # exit 1 if holes (records office red)
        if not rep.get("ok"):
            return 1
        if rep.get("mode") == "all" and (rep.get("n_incomplete") or 0) > 0:
            return 1
        if rep.get("mode") == "one" and not rep.get("complete"):
            return 1
        return 0
    if args.cmd == "backfill-sessions":
        from mag.records import backfill_sessions

        res = backfill_sessions(
            use_llm=args.llm,
            dry_run=args.dry_run,
            only_incomplete=not args.all,
        )
        print(json.dumps(res, indent=2, default=str)[:12000])
        return 0 if res.get("ok") else 1
    if args.cmd == "refresh-session-cards":
        from mag.session_card import recompute_all_cards

        res = recompute_all_cards()
        # short human preview
        for c in (res.get("cards") or [])[:12]:
            print(f"\n## {c.get('title') or c.get('session_id')}")
            print(c.get("blurb") or "")
            for b in c.get("bullets") or []:
                print(f"  - {b}")
        print(f"\n# refreshed {res.get('n')} cards")
        return 0 if res.get("ok") else 1
    if args.cmd == "migrate-lean-registry":
        from mag.registry import migrate_all_to_lean
        from mag.records import write_kpi

        res = migrate_all_to_lean()
        kpi = write_kpi(source="migrate-lean")
        print(json.dumps({**res, "kpi": kpi}, indent=2, default=str)[:8000])
        return 0 if res.get("ok") else 1
    if args.cmd == "org-review":
        from mag.operator_os import build_operator_os, format_org_review_text

        pack = build_operator_os(refresh_pack=True)
        if args.json:
            print(json.dumps(pack, indent=2, default=str)[:12000])
        else:
            print(format_org_review_text(pack))
        return 0 if pack.get("ok") else 1
    if args.cmd == "tapestry":
        from mag.tapestry import write_tapestry_pack

        pack = write_tapestry_pack()
        st = pack.get("stats") or {}
        print(
            f"tapestry → {pack.get('path')}\n"
            f"days={st.get('n_days')} nodes={st.get('n_nodes')} edges={st.get('n_edges')}\n"
            f"transforms: {(pack.get('transforms') or {})}"
        )
        return 0
    if args.cmd == "models":
        from models.registry import inventory

        inv = inventory()
        print(json.dumps(inv, indent=2))
        return 0 if inv.get("ok") else 1
    if args.cmd == "multi-smoke":
        from models.multi_smoke import run_multi_smoke

        res = run_multi_smoke()
        print(json.dumps(res, indent=2, default=str))
        print("\n" + res.get("verdict", ""))
        return 0 if res.get("ok") else 1
    if args.cmd == "nervous":
        from mag.nervous_system import build_glance, format_glance_text

        glance = build_glance(write=True)
        if getattr(args, "json", False):
            print(json.dumps(glance, indent=2, default=str))
        elif getattr(args, "quiet", False):
            pass
        else:
            face = ROOT / "memory" / "nervous_system.md"
            if face.is_file():
                print(face.read_text(encoding="utf-8"))
            else:
                print(format_glance_text(glance))
        return 0 if glance.get("ok") else 1
    if args.cmd == "system-map":
        from mag.system_map import build_system_map

        res = build_system_map(goal=str(getattr(args, "goal", "") or "").strip(), write=not bool(getattr(args, "json", False)))
        if getattr(args, "json", False):
            print(json.dumps(res, indent=2, default=str))
        else:
            md = ROOT / "memory" / "system_map" / "latest.md"
            if md.is_file():
                print(md.read_text(encoding="utf-8"))
            else:
                print(json.dumps(res, indent=2, default=str))
        return 0 if res.get("schema") == "system_map.v1" else 1
    if args.cmd == "lattice":
        from mag.lattice_dashboard import build_lattice_summary

        print(json.dumps(build_lattice_summary(), indent=2, default=str))
        return 0
    if args.cmd == "canvas-sync":
        from mag.canvas_bridge import sync_canvases

        print(json.dumps(sync_canvases(dry_run=bool(args.dry_run)), indent=2, default=str))
        return 0
    if args.cmd == "canvas-list":
        from mag.canvas_bridge import list_viewports

        print(json.dumps(list_viewports(), indent=2, default=str))
        return 0
    if args.cmd == "lattice-query":
        from mag.lattice_query import neighbors, query_by_theme, summary

        if getattr(args, "neighbors", ""):
            print(json.dumps(neighbors(args.neighbors), indent=2, default=str))
            return 0
        if getattr(args, "theme", ""):
            print(json.dumps(query_by_theme(args.theme), indent=2, default=str))
            return 0
        print(json.dumps(summary(), indent=2, default=str))
        return 0
    if args.cmd == "lattice-backfill":
        from mag.lattice_backfill import run_backfill

        res = run_backfill(dry_run=bool(getattr(args, "dry_run", False)))
        print(json.dumps(res, indent=2, default=str))
        return 0 if res.get("ok") else 1
    if args.cmd == "verkle-audit":
        from mag.verkle_audit import run_audit

        res = run_audit(
            full=bool(getattr(args, "full", False)),
            synth=bool(getattr(args, "synth", False)),
            reconcile=not bool(getattr(args, "no_reconcile", False)),
            backfill_lattice=bool(getattr(args, "backfill", False) or getattr(args, "full", False)),
            dry=bool(getattr(args, "dry", False)),
        )
        print(json.dumps(res, indent=2, default=str))
        return 0 if res.get("ok") else 1
    if args.cmd == "surface-rebuild":
        from mag.surface_rebuild import rebuild_surface

        res = rebuild_surface(dry_run=bool(getattr(args, "dry", False)))
        print(json.dumps(res, indent=2, default=str))
        return 0 if res.get("ok") else 1
    if args.cmd == "trajectory-rib":
        from mag.trajectory_rib import compile_tape

        res = compile_tape(
            tape=args.tape,
            output=args.output,
            include_legacy=bool(args.include_legacy),
        )
        print(json.dumps(res, indent=2, default=str))
        return 0 if res.get("ok") else 1
    if args.cmd == "live-ops":
        from mag.live_ops_readiness import write_snapshot

        res = write_snapshot()
        print(json.dumps(res, indent=2, default=str))
        return 0 if res.get("ok") else 1
    if args.cmd == "loop-audit":
        from mag.loop_audit import format_report, run_audit

        audit = run_audit(tail=int(getattr(args, "tail", 2500) or 2500))
        if getattr(args, "json", False):
            print(json.dumps(audit, indent=2, default=str))
        else:
            print(format_report(audit))
        sev = [f for f in audit.get("findings") or [] if f.get("severity") == "error"]
        return 1 if sev else 0
    if args.cmd == "ponytail-audit":
        from mag.ponytail_audit import format_report, run_audit

        res = run_audit(hints=True)
        print(format_report(res))
        return 0
    if args.cmd == "v3-status":
        from mag.loops_registry import build_registry, format_registry_text

        reg = build_registry()
        if getattr(args, "json", False):
            print(json.dumps(reg, indent=2, default=str))
        else:
            print(format_registry_text(reg))
        return 0
    if args.cmd == "spider":
        from mag.spider import tick

        res = tick(dry=bool(getattr(args, "dry", False)), inject=bool(getattr(args, "inject", False)))
        if getattr(args, "json", False):
            print(json.dumps(res, indent=2, default=str))
        else:
            print(json.dumps(res, indent=2, default=str))
        return 0
    if args.cmd == "steward":
        if getattr(args, "fill", False):
            from mag.steward import fill_steward_queue

            rows = fill_steward_queue(max_jobs=2)
            if getattr(args, "json", False):
                print(json.dumps({"ok": True, "queued": rows}, indent=2, default=str))
            else:
                print(f"queued {len(rows)} steward job(s)")
            return 0
        from mag.steward import run_job

        job = getattr(args, "job", "steward-scope") or "steward-scope"
        slug = (getattr(args, "slug", None) or "").strip() or None
        res = run_job(
            job,
            dry=bool(getattr(args, "dry", False)),
            slug=slug,
            use_llm=not bool(getattr(args, "no_llm", False)),
        )
        if getattr(args, "json", False):
            print(json.dumps(res, indent=2, default=str))
        else:
            print(json.dumps(res, indent=2, default=str))
        return 0 if res.get("ok", True) else 1
        print(json.dumps(res, indent=2, default=str)[:12000])
        return 0 if res.get("ok") else 1
    if args.cmd == "resonance":
        from mag.resonance import format_l0e, tick, top_cards

        goal = getattr(args, "goal", "") or ""
        if getattr(args, "tick", False):
            res = tick(goal, dry=bool(getattr(args, "dry", False)))
            print(json.dumps(res, indent=2, default=str)[:12000])
            return 0 if res.get("ok") else 1
        cards = top_cards(goal, n=5)
        print(format_l0e(cards) or "(no resonance cards)")
        return 0
    if args.cmd == "conductor":
        if getattr(args, "eval", False):
            from mag.conductor_eval import run_eval

            result = run_eval(write=not bool(getattr(args, "no_write", False)))
            print(json.dumps(result, indent=2, default=str)[:30000])
            return 0 if result.get("ok") else 1
        from mag.conductor import conduct

        goal = (getattr(args, "goal", None) or "").strip()
        if not goal:
            print("Usage: main.py conductor \"goal text\"")
            return 2
        res = conduct(goal, dry=bool(getattr(args, "dry", False)))
        if getattr(args, "json", False):
            print(json.dumps(res, indent=2, default=str)[:12000])
        else:
            route = res.get("route") or {}
            overlay = res.get("overlay") or {}
            print(f"phase: {res.get('phase')}")
            print(f"seat: {route.get('seat')} provider: {route.get('provider')} depth: {route.get('depth')}")
            print(f"note: {overlay.get('conductor_note', '')}")
            if overlay.get("case_law_hints"):
                print("case_law:", "; ".join(overlay["case_law_hints"]))
        return 0
    if args.cmd == "grove-build":
        from mag.grove import build, list_nodes

        if getattr(args, "list", False):
            nodes = list_nodes()
            if getattr(args, "json", False):
                print(json.dumps(nodes, indent=2, default=str)[:12000])
            else:
                for n in nodes:
                    print(f"- [{n.get('kind')}] {n.get('title')}: {n.get('poem', '').replace(chr(10), ' / ')}")
            return 0
        res = build(dry=bool(getattr(args, "dry", False)))
        print(json.dumps(res, indent=2, default=str)[:12000])
        return 0 if res.get("ok") else 1
    if args.cmd == "training-events":
        from mag.training_events import export_jsonl, read_events, stats

        if getattr(args, "export", False):
            res = export_jsonl(pattern=(getattr(args, "pattern", "") or None) or None)
            print(json.dumps(res, indent=2, default=str)[:12000])
            return 0 if res.get("ok") else 1
        if getattr(args, "stats", False) or getattr(args, "json", False):
            print(json.dumps(stats(), indent=2, default=str)[:12000])
            return 0
        rows = read_events(limit=20, pattern=(getattr(args, "pattern", "") or None) or None)
        for r in rows:
            print(f"{r.get('ts', '')[:19]} [{r.get('pattern')}] tags={r.get('pattern_tags')}")
        return 0
    if args.cmd == "vast-train":
        from mag.vast_train import dry_run

        if not getattr(args, "dry", False):
            print(json.dumps({"ok": False, "error": "Only --dry is available in v5 V1; no instance was launched."}, indent=2))
            return 2
        res = dry_run(
            getattr(args, "export_path"),
            base_model=getattr(args, "base_model", None),
            max_hours=getattr(args, "max_hours", None),
        )
        print(json.dumps(res, indent=2, default=str)[:12000])
        return 0 if res.get("ok") else 1
    if args.cmd == "run-worth":
        from mag import run_worth as rw

        action = getattr(args, "rw_action", "status") or "status"
        run_id = (getattr(args, "run_id", None) or "").strip()
        if action == "mark-good":
            if not run_id:
                print(json.dumps({"ok": False, "error": "run_id required"}))
                return 1
            res = rw.mark_run_good(run_id, note=getattr(args, "note", "") or "")
            print(json.dumps(res, indent=2, default=str))
            return 0 if res.get("ok") else 1
        if action == "evaluate":
            if run_id:
                from mag.run_trail import load_run, read_trail

                run = load_run(run_id)
                if not run:
                    print(json.dumps({"ok": False, "error": "run not found"}))
                    return 1
                sig = rw.signals_from_run(run, read_trail(run_id, last_n=80))
                cls = rw.classify_run(sig)
                print(json.dumps({"ok": True, "signals": sig, "evaluation": cls}, indent=2, default=str))
                return 0
            task_id = (getattr(args, "task_id", None) or "").strip()
            if task_id:
                res = rw.evaluate_task_hung(task_id)
                print(json.dumps({"ok": True, **res}, indent=2, default=str))
                return 0
            print(json.dumps({"ok": False, "error": "run_id or --task-id required"}))
            return 1
        res = rw.status(run_id=run_id or None)
        print(json.dumps(res, indent=2, default=str))
        return 0
    if args.cmd == "tesuji-shell":
        from mag.tesuji_shell import log_tesuji_shell, status as shell_status, synthesize_tesuji_shell_leaf

        action = getattr(args, "ts_action", "status") or "status"
        if action == "log":
            what = (getattr(args, "what", "") or "").strip()
            if not what:
                print("usage: tesuji-shell log \"what happened\" --surprise \"why it surprised\" [--maps-to remedy:ID]")
                return 2
            res = log_tesuji_shell(
                what,
                surprise=getattr(args, "surprise", "") or "",
                maps_to=(getattr(args, "maps_to", "") or None) or None,
                source=getattr(args, "source", "cli") or "cli",
            )
            print(json.dumps(res, indent=2, ensure_ascii=False))
            return 0 if res.get("ok") else 1
        if action == "synth":
            res = synthesize_tesuji_shell_leaf()
            if getattr(args, "json", False):
                print(json.dumps(res, indent=2, ensure_ascii=False))
            else:
                print(f"tesuji shell leaf → {res.get('path')} · wins={res.get('wins_n')}")
            return 0 if res.get("ok") else 1
        res = shell_status()
        print(json.dumps(res, indent=2, ensure_ascii=False))
        return 0
    if args.cmd == "release":
        from mag.release_registry import (
            build_subprocess_map,
            format_notes_text,
            format_subprocess_text,
            read_gate_log,
            record_gate,
            status_summary,
        )

        action = getattr(args, "action", "status") or "status"
        version = (getattr(args, "version", "") or "").strip()
        if action == "status":
            if getattr(args, "map", False):
                reg = build_subprocess_map()
                if getattr(args, "json", False):
                    print(json.dumps(reg, indent=2, default=str)[:12000])
                else:
                    print(format_subprocess_text(reg))
                return 0
            res = status_summary()
            if getattr(args, "json", False):
                print(json.dumps(res, indent=2, default=str)[:12000])
            else:
                for row in res.get("releases") or []:
                    print(f"{row.get('id')}: {row.get('status')} gates={row.get('gates_defined')}")
            return 0
        if action == "notes":
            if not version:
                print("usage: release notes v2")
                return 1
            print(format_notes_text(version))
            return 0
        if action == "gates":
            rows = read_gate_log(limit=30, version=version or None)
            if getattr(args, "json", False):
                print(json.dumps(rows, indent=2, default=str)[:12000])
            else:
                for r in rows:
                    mark = "OK" if r.get("ok") else "FAIL"
                    print(f"{r.get('ts', '')[:19]} v{r.get('version')} {r.get('gate_id')} [{mark}] {r.get('note', '')[:80]}")
            return 0
        if action == "record":
            if not version or not getattr(args, "gate", ""):
                print("usage: release record v2 --gate run_a --ok --note 'routing_smoke green'")
                return 1
            ok = bool(getattr(args, "ok", False)) and not bool(getattr(args, "fail", False))
            res = record_gate(
                version,
                getattr(args, "gate", ""),
                ok=ok,
                note=getattr(args, "note", "") or "",
                evidence_path=getattr(args, "evidence", "") or "",
            )
            print(json.dumps(res, indent=2, default=str))
            return 0 if res.get("ok") else 1
        return 1
    if args.cmd == "caveman-audit":
        from mag.caveman_audit import format_report, run_audit

        path = (getattr(args, "path", "") or "").strip()
        paths = [path] if path else None
        res = run_audit(paths=paths)
        if getattr(args, "json", False):
            print(json.dumps(res, indent=2, default=str)[:12000])
        else:
            print(format_report(res))
        return 0
    if args.cmd in ("build-audit", "factory-audit"):
        from mag.build_audit import write_audit

        cmds = [c for c in (getattr(args, "commands", None) or []) if c]
        try:
            res = write_audit(
                getattr(args, "slug", ""),
                verdict=getattr(args, "verdict", "pending") or "pending",
                spec_path=getattr(args, "spec_path", "") or "",
                commands=cmds or None,
                note=getattr(args, "note", "") or "",
                dry=bool(getattr(args, "dry", False)),
            )
        except ValueError as e:
            print(str(e))
            return 1
        if getattr(args, "json", False):
            print(json.dumps(res, indent=2, default=str))
        else:
            if res.get("dry"):
                print(f"dry run · would write {res.get('path')}")
            else:
                print(f"build_audit.v1 → {res.get('path')}")
            print(f"verdict: {res.get('record', {}).get('verdict')}")
        return 0 if res.get("ok") else 1
    if args.cmd == "skill-seat":
        from mag.skill_seat import build_preamble, pick_skill_for_goal, run_gate, skill_status

        action = getattr(args, "action", "status")
        goal = " ".join(getattr(args, "text", []) or []).strip()
        if action == "status":
            print(json.dumps(skill_status(), indent=2, default=str))
            return 0
        if action == "pick":
            sid = pick_skill_for_goal(goal)
            out = {"goal": goal[:200], "skill": sid}
            print(json.dumps(out, indent=2) if getattr(args, "json", False) else f"skill: {sid}")
            return 0
        if action == "preamble":
            sid = (getattr(args, "skill", "") or "").strip() or pick_skill_for_goal(goal)
            pre = build_preamble(sid, goal=goal)
            print(pre if not getattr(args, "json", False) else json.dumps({"skill": sid, "preamble": pre}))
            return 0
        if action == "gate":
            sid = (getattr(args, "skill", "") or "ponytail").strip()
            res = run_gate(sid, path=(getattr(args, "path", "") or "").strip())
            print(json.dumps(res, indent=2, default=str)[:12000])
            return 0 if res.get("pass", res.get("ok")) else 1
        return 2
    if args.cmd == "arena":
        from mag.agent_arena import handle_action, status
        from mag.arena_learning import league_snapshot, routing_hint, run_tournament

        action = getattr(args, "action", "status") or "status"
        probe_type = (getattr(args, "probe_type", "") or "").strip() or None
        if action == "status":
            out = status()
        elif action == "games":
            from mag import arena_adapter as aa

            out = aa.list_games()
        elif action == "probe":
            from mag import arena_adapter as aa

            seats = tuple(
                s.strip() for s in (getattr(args, "seats", "local,remote") or "").split(",") if s.strip()
            )
            game_id = (getattr(args, "game_id", "") or "").strip() or (
                getattr(args, "game", "TicTacToe-v0") or "TicTacToe-v0"
            )
            if game_id == "chess":
                game_id = "TicTacToe-v0"
            out = aa.run_probe(
                game_id=game_id,
                seats=seats or ("local", "remote"),
                render=bool(getattr(args, "render", False)),
            )
        elif action == "league":
            out = {
                "ok": True,
                **league_snapshot(game=getattr(args, "game", "chess") or "chess", probe_type=probe_type),
            }
        elif action == "tournament":
            seats = tuple(s.strip() for s in (getattr(args, "seats", "local,remote") or "").split(",") if s.strip())
            game = getattr(args, "game", "chess") or "chess"
            if game != "chess":
                from mag import arena_adapter as aa

                results = []
                for i in range(max(1, min(int(getattr(args, "rounds", 1) or 1), 10))):
                    w, b = seats[i % len(seats)], seats[(i + 1) % len(seats)]
                    results.append(aa.run_probe(game_id=game, seats=[w, b]))
                out = {"ok": True, "rounds": len(results), "results": results}
            else:
                out = run_tournament(
                    game=game,
                    rounds=max(1, int(getattr(args, "rounds", 1) or 1)),
                    seats=seats or ("local", "remote"),
                )
        elif action == "routing":
            out = {
                "ok": True,
                **routing_hint(
                    game=getattr(args, "game", "chess") or "chess",
                    task=getattr(args, "task", "structured_handoff") or "structured_handoff",
                    budget=getattr(args, "budget", "low") or "low",
                    probe_type=probe_type,
                ),
            }
        else:
            out = handle_action({"action": action})
        print(json.dumps(out, indent=2, default=str)[:16000])
        return 0 if out.get("ok", True) else 1
    if args.cmd == "switchboard":
        from mag.switchboard import (
            format_status_text,
            mesh,
            peers,
            reap,
            route_intent,
            self_test,
            status,
            steer_drop,
        )

        action = getattr(args, "action", "status") or "status"
        if action == "self-test":
            res = self_test()
            print(json.dumps(res, indent=2, default=str))
            return 0 if res.get("ok") else 1
        if action == "status":
            s = status()
            if getattr(args, "json", False):
                print(json.dumps(s, indent=2, default=str)[:12000])
            else:
                print(format_status_text(s))
            return 0
        if action == "mesh":
            print(json.dumps(mesh(), indent=2, default=str)[:16000])
            return 0
        if action == "peers":
            print(json.dumps(
                peers(
                    group=(getattr(args, "group", "") or None) or None,
                    live_only=bool(getattr(args, "live", False)),
                ),
                indent=2,
                default=str,
            )[:12000])
            return 0
        if action == "reap":
            print(json.dumps(reap(), indent=2, default=str))
            return 0
        if action == "drop":
            rest = list(getattr(args, "rest", []) or [])
            if len(rest) < 2:
                print("Usage: main.py switchboard drop <to_peer> <context...>")
                return 2
            to_ref = rest[0]
            context = " ".join(rest[1:]).strip()
            res = steer_drop(
                getattr(args, "from_ref", "operator") or "operator",
                to_ref,
                context,
                tier=getattr(args, "tier", "T2") or "T2",
                spooky=bool(getattr(args, "spooky", False)),
                dry=bool(getattr(args, "dry", False)),
            )
            print(json.dumps(res, indent=2, default=str)[:12000])
            return 0 if res.get("ok") else 1
        if action == "route":
            goal = " ".join(getattr(args, "rest", []) or []).strip()
            if not goal:
                print('Usage: main.py switchboard route "goal text"')
                return 2
            res = route_intent(goal, dry=bool(getattr(args, "dry", False)))
            print(json.dumps(res, indent=2, default=str)[:12000])
            return 0
        return 2
    if args.cmd == "seats":
        from mag.seat_registry import heartbeat, list_registered, register, unregister

        action = getattr(args, "action", "list") or "list"
        if action == "register":
            rec = register(
                seat=getattr(args, "seat", "cursor") or "cursor",
                goal=getattr(args, "goal", "") or "",
                mode=getattr(args, "mode", "interactive") or "interactive",
                task_id=(getattr(args, "task_id", "") or None) or None,
                pid=getattr(args, "pid", None),
                tag=getattr(args, "tag", "") or "",
                parent=getattr(args, "parent", "desktop") or "desktop",
            )
            if getattr(args, "json", False):
                print(json.dumps(rec, indent=2, default=str))
            else:
                print(f"registered {rec['task_id']} — MAG_TASK_ID={rec['task_id']}")
                print(rec.get("hint", ""))
            return 0
        if action == "heartbeat":
            rest = list(getattr(args, "rest", []) or [])
            tid = rest[0] if rest else (getattr(args, "task_id", "") or "")
            if not tid:
                print("Usage: main.py seats heartbeat <task_id>")
                return 2
            rec = heartbeat(
                tid,
                phase=(getattr(args, "phase", "") or None) or None,
                goal=(getattr(args, "goal", "") or None) or None,
                seat=(getattr(args, "seat", "") or None) or None,
            )
            print(json.dumps(rec, indent=2, default=str) if getattr(args, "json", False) else f"heartbeat ok {tid}")
            return 0 if rec.get("ok") else 1
        if action == "unregister":
            rest = list(getattr(args, "rest", []) or [])
            tid = rest[0] if rest else (getattr(args, "task_id", "") or "")
            if not tid:
                print("Usage: main.py seats unregister <task_id>")
                return 2
            rec = unregister(tid, status=getattr(args, "status", "done") or "done", detail=getattr(args, "detail", "") or "")
            print(json.dumps(rec, indent=2, default=str) if getattr(args, "json", False) else f"unregistered {tid}")
            return 0 if rec.get("ok") else 1
        if action == "list":
            rows = list_registered(live_only=bool(getattr(args, "live", False)))
            if getattr(args, "json", False):
                print(json.dumps(rows, indent=2, default=str))
            else:
                for r in rows:
                    print(f"  {r.get('task_id')} {r.get('seat')} {r.get('status')} {str(r.get('goal',''))[:50]}")
            return 0
        return 2
    if args.cmd == "ollama":
        import json as _json

        from mag.ollama_policy import enforce_one_hot, status as ollama_status

        action = getattr(args, "action", "status") or "status"
        if action == "one-hot":
            keep = (getattr(args, "keep", "") or "").strip() or None
            res = enforce_one_hot(keep=keep)
        else:
            res = ollama_status()
        if getattr(args, "json", False):
            print(_json.dumps(res, indent=2, default=str))
        else:
            if action == "one-hot":
                print(f"one-hot: stopped {res.get('n_stopped', 0)} · kept {res.get('kept')}")
            else:
                print(f"loaded: {res.get('n_loaded', 0)} · one_hot={res.get('one_hot')}")
                for row in res.get("loaded") or []:
                    print(f"  {row.get('name')} gpu={row.get('gpu_pct')}% vram={row.get('vram_gb')}GB")
        return 0 if res.get("ok", True) else 1
    if args.cmd == "probe-local":
        import json as _json

        target = getattr(args, "target", "desk-models")
        if target == "desk-models":
            from mag.desk_model_probe import run_probe

            res = run_probe(pull_qwen=not getattr(args, "no_pull", False))
        elif target == "steal-protocol":
            from mag.steal_protocol_probe import run_steal_protocol_probe

            res = run_steal_protocol_probe()
        else:
            from mag.gstd_probe import run_gstd_probe

            res = run_gstd_probe(bench_local=not getattr(args, "no_bench", False))
        if getattr(args, "json", False):
            print(_json.dumps(res, indent=2, default=str))
        else:
            if target == "desk-models":
                print(f"desk-models winner: {res.get('winner') or '—'}")
                for c in res.get("candidates") or []:
                    print(
                        f"  {c.get('model')}: ok={c.get('ok')} "
                        f"tps={c.get('tokens_per_sec')} gpu={c.get('gpu_pct')}% "
                        f"ms={c.get('elapsed_ms')}"
                    )
                print(f"  → {res.get('recommendation')}")
            elif target == "steal-protocol":
                clones = res.get("clones") or {}
                print(f"steal-protocol: {clones.get('n', 0)}/{clones.get('expected', '?')} repos")
                print(f"  refresh: {clones.get('refresh')}")
                print(f"  index: {res.get('index')}")
            else:
                route = res.get("route") or {}
                print(f"gstd route: {route.get('primary')} — {route.get('reason')}")
                print(f"  clones: {(res.get('clones') or {}).get('n')}/6 · report: {res.get('report_path')}")
        return 0 if res.get("ok", True) else 1
    if args.cmd == "scheduler":
        import json as _json

        from mag.local_scheduler import deepseek_triage, status as sched_status, steer

        action = getattr(args, "action", "status") or "status"
        if action == "status":
            res = sched_status()
        elif action == "pause":
            res = steer("!pause")
        elif action == "continue":
            res = steer("!continue")
        elif action == "escape":
            res = steer("!escape")
        elif action == "triage":
            res = deepseek_triage()
        elif action == "steer":
            txt = (getattr(args, "text", "") or "").strip()
            res = steer(txt if txt.startswith("!") else f"!steer {txt}")
        else:
            return 2
        if getattr(args, "json", False):
            print(_json.dumps(res, indent=2, default=str))
        else:
            if action == "status":
                print(
                    f"scheduler depth={res.get('depth')} busy={res.get('busy')} "
                    f"paused={res.get('paused')} enabled={res.get('enabled')}"
                )
                for t in res.get("pending") or []:
                    print(f"  queued · {t.get('id')} · {t.get('label')} · pri {t.get('priority')}")
            else:
                print(_json.dumps(res, indent=2, default=str))
        return 0 if res.get("ok", True) else 1
    if args.cmd == "realign":
        from mag import realign

        return realign.main(mark_visited=getattr(args, "mark_visited", False))
    if args.cmd == "operator-mode":
        import json as _json

        from mag import operator_mode

        action = getattr(args, "action", "status") or "status"
        if action == "status":
            res = operator_mode.read()
        elif action == "pause":
            reason = " ".join(getattr(args, "reason", []) or []).strip()
            res = operator_mode.set_paused(
                reason=reason or "operator requested pause",
                scope=getattr(args, "scope", "autonomous") or "autonomous",
                until=getattr(args, "until", None),
            )
        else:
            reason = " ".join(getattr(args, "reason", []) or []).strip()
            res = operator_mode.resume(reason=reason or "operator resumed autonomous work")
        if getattr(args, "json", False):
            print(_json.dumps(res, indent=2, default=str))
        else:
            print(f"operator mode: {res.get('effective_mode', res.get('mode'))}")
            if res.get("reason"):
                print(f"reason: {res.get('reason')}")
            print(f"scope: {res.get('scope')} · state: {operator_mode.STATE_PATH}")
        return 0 if res.get("mode") != "invalid" else 1
    if args.cmd == "unsloth":
        from mag.unsloth_seat import unsloth_start, unsloth_status, unsloth_stop

        action = getattr(args, "action", "status") or "status"
        if action == "start":
            res = unsloth_start(
                mode=getattr(args, "mode", "chat") or "chat",
                model=getattr(args, "model", "") or "",
                agent=getattr(args, "agent", "hermes") or "hermes",
                register_seat=not getattr(args, "no_register", False),
            )
        elif action == "stop":
            res = unsloth_stop()
        else:
            res = unsloth_status()
        if getattr(args, "json", False) or action != "status":
            print(json.dumps(res, indent=2, default=str))
        else:
            st = "running" if res.get("running") else "stopped"
            print(f"unsloth {st} · installed={res.get('installed')} · {res.get('version') or '—'}")
            if res.get("pid"):
                print(f"  pid {res['pid']} mode={res.get('mode')}")
            if res.get("gpu_hint"):
                gh = res["gpu_hint"]
                print(f"  desk {gh.get('desk_model')} · {gh.get('gpu_note', '')[:60]}")
        return 0 if res.get("ok", True) else 1
    if args.cmd == "power":
        from mag.power import format_status_text, stack_status, start_all, stop_all

        action = getattr(args, "action", "status") or "status"
        if action == "stop":
            res = stop_all()
        elif action == "start":
            res = start_all(open_browser=bool(getattr(args, "browser", False)))
        else:
            res = stack_status()
        if getattr(args, "json", False) or action != "status":
            print(json.dumps(res, indent=2, default=str))
        else:
            print(format_status_text(res))
        return 0 if res.get("ok", True) else 1
    if args.cmd == "cost-sim":
        from mag.cost_simulator import estimate_goal, estimate_wave, format_wave_text

        action = getattr(args, "cs_action", "wave") or "wave"
        text = getattr(args, "text", "") or "v3-epic"
        if action == "goal":
            res = estimate_goal(text, seat=(getattr(args, "seat", "") or None), pack_mode=(getattr(args, "pack", "") or None), dry=bool(getattr(args, "dry", False)))
        else:
            res = estimate_wave(text, improve_n=int(getattr(args, "improve", 2)), build_waves=int(getattr(args, "build", 3)), audits=int(getattr(args, "audit", 1)), plan=not bool(getattr(args, "no_plan", False)))
        if getattr(args, "json", False) or action == "goal":
            print(json.dumps(res, indent=2, default=str))
        else:
            print(format_wave_text(res))
        return 0 if res.get("ok") else 1
    if args.cmd == "field-steal":
        from mag.field_steal import run_field_steal

        root = (getattr(args, "root", None) or "").strip()
        if not root:
            root = str(ROOT.parent / "field-strike-the-chord")
        res = run_field_steal(root, max_files=int(getattr(args, "max_files", 0) or 0))
        if getattr(args, "json", False):
            print(json.dumps(res, indent=2, default=str))
        else:
            print(json.dumps(res, indent=2, default=str))
            md = (res.get("paths") or {}).get("latest_md")
            if md and Path(md).is_file():
                print("\n" + Path(md).read_text(encoding="utf-8")[:8000])
        return 0 if res.get("ok") else 1
    if args.cmd == "context-pack":
        from mag.context_pack import (
            build_context_pack,
            format_agent_preamble,
            format_context_pack_text,
        )

        mode = getattr(args, "mode", "full") or "full"
        job = (getattr(args, "job", None) or "").strip() or None
        build_path = (getattr(args, "build", None) or "").strip() or None
        scope_slug = (getattr(args, "scope", None) or "").strip() or ""
        pack = build_context_pack(
            mode=mode,
            job=job,
            build_path=build_path or None,
            scope_slug=scope_slug,
            refresh_bonds=bool(getattr(args, "refresh_bonds", False)),
        )
        out = ROOT / "memory" / "context_pack_latest.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        text = format_context_pack_text(pack, mode=mode)
        out.write_text(text, encoding="utf-8")
        (ROOT / "memory" / "context_pack_latest.json").write_text(
            json.dumps(pack, indent=2, default=str), encoding="utf-8"
        )
        if getattr(args, "agent", False):
            preamble = format_agent_preamble(
                pack,
                goal=(getattr(args, "goal", None) or "").strip(),
            )
            ap = ROOT / "memory" / "agent_preamble_latest.md"
            ap.write_text(preamble, encoding="utf-8")
            print(preamble)
            return 0
        print(text)
        # B2-314: the census patrol's own darkness is silent (Interactive-only
        # scheduled task), so the attended context-pack surface reads the last
        # START stamp and NAMES the darkness when the patrol went quiet.
        from mag.census_liveness import report as census_liveness_report
        census_liveness_report()
        return 0
    if args.cmd == "bonds":
        from mag.bonds import BONDS_MD, ingest_bonds, load_bonds_json, scan_conflicts

        scan_text = (getattr(args, "scan", None) or "").strip()
        if scan_text:
            bj = load_bonds_json() or {}
            existing = [str(x) for x in (bj.get("residual_bonds") or [])]
            hits = scan_conflicts(scan_text, existing)
            print(json.dumps({"ok": True, "candidate": scan_text, "conflicts": hits}, indent=2, default=str))
            return 0

        sid = (getattr(args, "session", None) or "").strip() or None
        res = ingest_bonds(session_id=sid, write=True)
        print(json.dumps(res, indent=2, default=str))
        if getattr(args, "print_bonds", False) and BONDS_MD.is_file():
            print("\n" + BONDS_MD.read_text(encoding="utf-8")[:6000])
        return 0 if res.get("ok") else 1

    if args.cmd == "diary":
        from mag.diary import build_diary, format_diary_markdown, write_diary_face
        newest = bool(getattr(args, "newest", False))
        if getattr(args, "write", False):
            d = write_diary_face(newest_first=newest)
        else:
            d = build_diary(newest_first=newest)
        if getattr(args, "json", False):
            print(json.dumps(d, indent=2, default=str)[:50000])
        else:
            print(format_diary_markdown(d)[:20000])
            if d.get("face"):
                print("\n# face:", d.get("face"))
        return 0 if d.get("ok") else 1

    if args.cmd == "ideas":
        from mag import idea_graph as ig

        action = (getattr(args, "action", None) or "list").strip().lower()
        ids = list(getattr(args, "ids", None) or [])
        as_json = bool(getattr(args, "json", False))
        try:
            if action == "summary":
                res = ig.summary()
                print(json.dumps(res, indent=2, default=str))
                return 0
            if action == "seed":
                res = ig.seed_from_working_and_agent_state()
                print(json.dumps(res, indent=2, default=str))
                return 0 if res.get("ok") else 1
            if action == "add":
                title = (getattr(args, "title", None) or "").strip()
                if not title and ids:
                    title = " ".join(ids)
                if not title:
                    print(json.dumps({"ok": False, "error": "need --title or positional title"}))
                    return 1
                ntype = (getattr(args, "idea_type", None) or "topic").strip() or "topic"
                status = (getattr(args, "status", None) or "open").strip() or "open"
                node = ig.add_node(
                    title=title,
                    ntype=ntype,
                    status=status,
                    body=(getattr(args, "body", None) or "").strip(),
                    source="human",
                )
                ig.write_latest_face()
                print(json.dumps({"ok": True, "node": node}, indent=2, default=str))
                return 0
            if action == "link":
                if len(ids) < 2:
                    print(json.dumps({"ok": False, "error": "ideas link SRC DST [--type related]"}))
                    return 1
                etype = (getattr(args, "idea_type", None) or "related").strip() or "related"
                edge = ig.link(
                    ids[0],
                    ids[1],
                    etype=etype,
                    note=(getattr(args, "note", None) or "").strip(),
                    ref=(getattr(args, "ref", None) or "").strip(),
                )
                ig.write_latest_face()
                print(json.dumps({"ok": True, "edge": edge}, indent=2, default=str))
                return 0
            if action == "pack":
                nid = (ids[0] if ids else "").strip()
                if not nid:
                    print(json.dumps({"ok": False, "error": "ideas pack NODE_ID"}))
                    return 1
                text = ig.pack_node(nid)
                if as_json:
                    print(json.dumps({"ok": True, "pack": text}, indent=2))
                else:
                    print(text)
                return 0 if not text.startswith("(idea pack:") else 1
            if action == "show":
                nid = (ids[0] if ids else "").strip()
                if not nid:
                    print(json.dumps({"ok": False, "error": "ideas show NODE_ID"}))
                    return 1
                nb = ig.neighborhood(nid, depth=1)
                print(json.dumps(nb, indent=2, default=str))
                return 0 if nb.get("ok") else 1
            # list (default)
            status = (getattr(args, "status", None) or "").strip() or None
            ntype = (getattr(args, "idea_type", None) or "").strip() or None
            rows = ig.list_nodes(
                status=status,
                ntype=ntype,
                limit=int(getattr(args, "limit", 40) or 40),
            )
            if as_json:
                print(json.dumps({"ok": True, "nodes": rows, **ig.summary()}, indent=2, default=str))
            else:
                print(ig.format_list(rows))
                sm = ig.summary()
                print(f"\n# {sm.get('n_nodes')} nodes · {sm.get('n_edges')} edges · {sm.get('schema')}")
            return 0
        except ValueError as e:
            print(json.dumps({"ok": False, "error": str(e)}))
            return 1
    if args.cmd == "agent-state":
        from mag import agent_state as ast

        if getattr(args, "list_versions", False):
            rows = ast.list_versions(limit=30)
            print(json.dumps(rows, indent=2, default=str))
            return 0
        show = (getattr(args, "show", None) or "").strip()
        if show:
            ver = ast.load_version(show)
            if not ver:
                print(json.dumps({"ok": False, "error": f"not found: {show}"}))
                return 1
            if getattr(args, "json", False):
                print(json.dumps(ver, indent=2, default=str)[:20000])
            else:
                print(ast.format_load_markdown(ver))
            return 0
        if getattr(args, "link_residual", False):
            res = ast.link_to_residual((getattr(args, "session", None) or "").strip() or None)
            print(json.dumps(res, indent=2, default=str))
            return 0 if res.get("ok") else 1
        commit_reason = (getattr(args, "commit", None) or "").strip()
        if commit_reason:
            payload: dict = {}
            ff = (getattr(args, "from_file", None) or "").strip()
            if ff:
                p = Path(ff)
                if not p.is_file():
                    p = ROOT / ff
                payload = json.loads(p.read_text(encoding="utf-8"))
            else:
                # minimal commit without full payload — still versioned
                prev = ast.load_latest() or {}
                payload = {
                    "commitment": f"agent-state-manual-{commit_reason[:40]}",
                    "one_line": prev.get("one_line")
                    or "Manual agent-state commit — fill via --from-file next time",
                    "do_not_redesign": prev.get("do_not_redesign")
                    or ["LOAD LATEST before redesign"],
                    "compose_bundles": prev.get("compose_bundles") or [],
                    "next_moves": prev.get("next_moves") or [],
                    "stack": prev.get("stack") or {},
                    "paths": prev.get("paths") or {},
                    "leave": prev.get("leave") or [],
                    "notes": commit_reason,
                }
            res = ast.commit_state(
                payload,
                label=commit_reason[:80],
                reason=commit_reason,
            )
            print(json.dumps(res, indent=2, default=str))
            return 0 if res.get("ok") else 1
        # default: --load or status
        if getattr(args, "load", False) or not getattr(args, "json", False):
            print(ast.format_load_markdown())
            if getattr(args, "json", False):
                lat = ast.load_latest()
                print("\n--- JSON ---\n")
                print(json.dumps(lat, indent=2, default=str)[:12000] if lat else "{}")
            return 0
        lat = ast.load_latest()
        print(json.dumps(lat or {"ok": False, "error": "no state"}, indent=2, default=str)[:16000])
        return 0 if lat else 1
    if args.cmd == "compose-status":
        from mag.modules import (
            attach_related_runs_to_residual,
            compose_status,
            format_compose_status,
        )

        if getattr(args, "attach_runs", False):
            att = attach_related_runs_to_residual(
                (getattr(args, "session", None) or "").strip() or None
            )
            print(json.dumps(att, indent=2, default=str))
            if not att.get("ok"):
                return 1
        st = compose_status()
        if getattr(args, "json", False):
            print(json.dumps(st, indent=2, default=str)[:16000])
        else:
            print(format_compose_status(st))
        return 0 if st.get("ok") else 1
    if args.cmd == "trail":
        from mag import run_trail as rt

        action = args.action
        rid = (getattr(args, "run", None) or "").strip() or None
        text = " ".join(getattr(args, "text", None) or []).strip()

        if action == "start":
            if not text:
                print(json.dumps({"ok": False, "error": "goal required"}))
                return 1
            res = rt.start_run(
                text,
                seat=args.seat,
                proactivity=args.proactivity,
                force=bool(args.force),
                never_remote=bool(getattr(args, "never_remote", False)),
                git_sha=(getattr(args, "git_sha", None) or "").strip(),
            )
            print(json.dumps(res, indent=2, default=str))
            return 0 if res.get("ok") else 1

        if action == "append":
            if not text:
                print(json.dumps({"ok": False, "error": "summary required"}))
                return 1
            label = (getattr(args, "label", None) or "").strip()
            if label:
                # Multi-agent FILE into trail (Elias rope) — not peer chat.
                res = rt.file_agent_core(
                    label,
                    text,
                    run_id=rid,
                    text=(getattr(args, "core_text", None) or "").strip() or text,
                    locus=(getattr(args, "locus", None) or "").strip(),
                    drift_kind=(getattr(args, "drift_kind", None) or "note").strip(),
                    evidence=(getattr(args, "evidence", None) or "").strip(),
                    base_id=(getattr(args, "base_id", None) or "").strip(),
                )
                print(json.dumps(res, indent=2, default=str))
                return 0 if res.get("ok") else 1
            core = None
            core_text = (getattr(args, "core_text", None) or "").strip()
            core_raw = (getattr(args, "core", None) or "").strip()
            if core_text:
                core = {
                    "type": (args.kind if args.kind not in ("note", "run_start") else "decision"),
                    "text": core_text[:800],
                }
            elif core_raw:
                try:
                    core = json.loads(core_raw)
                except json.JSONDecodeError as e:
                    print(json.dumps({"ok": False, "error": f"core json: {e}; use --core-text"}))
                    return 1
            # Do not pass default --seat on append (would false-fail purity).
            # Seat purity is for check-seat / explicit mid-run thrash detection.
            res = rt.append_event(
                args.kind,
                text,
                run_id=rid,
                seat=None,
                core=core,
            )
            print(json.dumps(res, indent=2, default=str))
            return 0 if res.get("ok") else 1

        if action == "status":
            print(json.dumps(rt.status(), indent=2, default=str))
            return 0

        if action == "close":
            res = rt.close_run(rid, reason=args.reason)
            print(json.dumps(res, indent=2, default=str))
            return 0 if res.get("ok") else 1

        if action == "check-seat":
            res = rt.check_seat(args.seat, run_id=rid)
            print(json.dumps(res, indent=2, default=str))
            return 0 if res.get("ok") else 1

        if action == "cores":
            cores = rt.cores_for_reinject(rid)
            print(json.dumps({"ok": True, "n": len(cores), "cores": cores}, indent=2, default=str))
            return 0

        if action == "pack":
            res = rt.trail_pack_excerpt(run_id=rid)
            print(json.dumps(res, indent=2, default=str))
            return 0

        if action == "base":
            res = rt.ensure_run_base(rid)
            print(json.dumps(res, indent=2, default=str))
            return 0 if res.get("ok") else 1

        if action == "drifts":
            res = rt.list_drifts(rid)
            print(json.dumps(res, indent=2, default=str))
            return 0 if res.get("ok") else 1

        print(json.dumps({"ok": False, "error": f"unknown action {action}"}))
        return 1
    if args.cmd == "providers":
        from models.providers import status_table

        print(json.dumps(status_table(), indent=2, default=str))
        return 0
    if args.cmd == "quota":
        from models.quota import all_budgets

        print(json.dumps(all_budgets(), indent=2, default=str))
        return 0
    if args.cmd == "provider-chat":
        from models.providers import chat_provider, chat_routed

        prompt = " ".join(args.prompt)
        system = "You are Mag L1 helper. Public text only. Be concise."
        if args.provider:
            res = chat_provider(
                args.provider,
                system,
                prompt,
                model=args.model or None,
                tier=args.tier,
            )
        else:
            res = chat_routed(
                system,
                prompt,
                job=args.job,
                tier=args.tier,
                model=args.model or None,
            )
        print(json.dumps(res, indent=2, default=str)[:4000])
        return 0 if res.get("ok") else 1
    if args.cmd == "hermes-status":
        from harness.hermes_cli import hermes_status

        res = hermes_status()
        print(json.dumps(res, indent=2, default=str))
        return 0 if res.get("available") else 1
    if args.cmd == "dispatch":
        from mag.dispatch import dispatch

        res = dispatch(
            " ".join(args.goal),
            execute=not args.dry,
            force_provider=args.provider or None,
            force_seat=args.seat or None,
        )
        print(json.dumps(res, indent=2, default=str)[:5000])
        return 0 if res.get("ok") else 1
    if args.cmd == "coordinate":
        from mag.coordination import coordinate

        goal = " ".join(args.goal)
        res = coordinate(
            goal,
            depth=(args.depth or None),
            seat=(args.seat or "cli").strip() or "cli",
            actor="cli",
            launch=not args.dry,
            background=bool(args.background),
            session_id=(args.session or "").strip() or None,
        )
        print(json.dumps(res, indent=2, default=str)[:8000])
        return 0 if res.get("ok") else 1
    if args.cmd == "steer-agent":
        from mag.steer_bridge import steer as sb_steer
        from mag.steer_bridge import status as sb_status
        from mag.steer_bridge import sync_guidance_file as sb_sync

        if getattr(args, "status", False):
            print(json.dumps(sb_status(), indent=2, default=str)[:4000])
            return 0
        if getattr(args, "sync", False):
            res = sb_sync(getattr(args, "file", "") or None, source=(args.source or "copilot-assistant"))
            print(json.dumps(res, indent=2, default=str)[:4000])
            return 0 if res.get("ok") else 1
        goal = " ".join(getattr(args, "text", []) or []).strip()
        if not goal:
            print('usage: main.py steer-agent "guidance" | --sync | --status', file=sys.stderr)
            return 2
        r = sb_steer(goal, source=(args.source or "copilot-assistant"))
        print(json.dumps(r, indent=2, default=str)[:4000])
        return 0 if r.get("ok") else 1
    if args.cmd == "vscode-feed":
        from mag.vscode_feed import capture as vf_capture
        from mag.vscode_feed import status as vf_status

        action = (getattr(args, "vf_action", "capture") or "capture").strip()
        if action == "status":
            print(json.dumps(vf_status(), indent=2, default=str)[:4000])
            return 0
        res = vf_capture(
            goal=getattr(args, "goal", "") or "",
            outcome=(getattr(args, "outcome", "unknown") or "unknown").strip(),
            tier=getattr(args, "tier", "T1") or "T1",
            lessons=list(getattr(args, "lesson", []) or []),
            source=getattr(args, "source", "copilot") or "copilot",
            session_id=getattr(args, "session", "") or "",
        )
        print(json.dumps(res, indent=2, default=str)[:4000])
        return 0 if res.get("ok") else 1
    if args.cmd == "drainer-stats":
        from mag.drainer_stats import main as ds_main

        return ds_main(list(getattr(args, "ds_args", []) or []))
    if args.cmd == "live-feed":
        from mag.live_feed import main as lf_main

        return lf_main(list(getattr(args, "lf_args", []) or []))
    if args.cmd == "session-state-brief":
        from mag.session_state_brief import gather_state, render_brief, write_brief

        if getattr(args, "json", False):
            print(json.dumps(gather_state(), indent=2, default=str)[:8000])
            return 0
        if getattr(args, "dry", False):
            print(render_brief(gather_state()))
            return 0
        res = write_brief()
        print(json.dumps(res, indent=2, default=str)[:2000])
        return 0
    if args.cmd == "state-brief":
        from mag.state_brief import gather, render, write as sb_write

        if getattr(args, "json", False):
            print(json.dumps(gather(), indent=2, default=str)[:8000])
            return 0
        if getattr(args, "dry", False):
            print(render(gather()))
            return 0
        res = sb_write()
        print(json.dumps(res, indent=2, default=str)[:2000])
        return 0
    if args.cmd == "ops-graph":
        from mag.ops_graph import main as og_main

        og_args: list[str] = []
        if getattr(args, "json", False):
            og_args.append("--json")
        if getattr(args, "ingest", False):
            og_args.append("--ingest")
        return og_main(og_args)
    if args.cmd == "janitor":
        from mag.janitor import main as jan_main

        jan_args: list[str] = []
        if getattr(args, "dry", False):
            jan_args.append("--dry")
        if getattr(args, "prune_only", False):
            jan_args.append("--prune-only")
        if getattr(args, "document_only", False):
            jan_args.append("--document-only")
        if getattr(args, "last", False):
            jan_args.append("--last")
        return jan_main(jan_args)
    if args.cmd == "orphan":
        from mag.orphan_timer import main as orphan_main

        return orphan_main(list(getattr(args, "orphan_args", []) or []))
    if args.cmd == "warning-monitor":
        from mag.warning_monitor import main as warn_main

        return warn_main(list(getattr(args, "warn_args", []) or []))
    if args.cmd == "process-supervisor":
        from mag.process_supervisor import main as ps_main

        return ps_main(list(getattr(args, "proc_sup_args", []) or []))
    if args.cmd == "docker-ops":
        from mag.docker_ops import main as docker_main

        return docker_main(list(getattr(args, "docker_args", []) or []))
    if args.cmd == "wake":
        from mag.state_brief import write as sb_write
        from mag.process_supervisor import start_all

        out: dict[str, Any] = {"ok": True}
        if not getattr(args, "brief_only", False):
            out["supervisor"] = start_all()
        out["brief"] = sb_write()
        print(json.dumps(out, indent=2, default=str)[:3000])
        return 0
    if args.cmd == "deep-handoff":
        from mag.session_maze import main as maze_main

        return maze_main(list(getattr(args, "deep_args", []) or []))
    if args.cmd == "extension-deploy":
        from mag.extension_deploy import main as ext_main

        return ext_main([])
    if args.cmd == "embassy-publish":
        from mag.embassy_deliver import main as emb_main

        argv = []
        if getattr(args, "live", False):
            argv.append("--live")
        if getattr(args, "repo", None):
            argv += ["--repo", args.repo]
        return emb_main(argv)
    if args.cmd == "cleanup":
        from mag.cleanup import main as clean_main

        return clean_main(["--live"] if getattr(args, "live", False) else [])
    if args.cmd == "cost-learn":
        from mag.cost_learn import main as costlearn_main

        argv = []
        if getattr(args, "hours", 24):
            argv += ["--hours", str(args.hours)]
        if getattr(args, "fold", False):
            argv += ["--fold"]
        if getattr(args, "cadence", False):
            argv += ["--cadence"]
        return costlearn_main(argv)
    if args.cmd == "usage-forecast":
        from mag.usage_forecast import main as ufc_main

        uargv = [getattr(args, "ufc_cmd", "queue")]
        if getattr(args, "ufc_cmd", "") == "goal":
            uargv = ["goal"] + list(getattr(args, "goal", []))
            if getattr(args, "agent_state", None):
                uargv += ["--agent-state", args.agent_state]
        elif getattr(args, "ufc_cmd", "") == "calibrate":
            uargv = ["calibrate", "--hours", str(getattr(args, "hours", 24))]
        return ufc_main(uargv)
    if args.cmd == "context-growth":
        from mag.context_growth import main as ctxg_main

        argv = []
        if getattr(args, "hours", 24):
            argv += ["--hours", str(args.hours)]
        if getattr(args, "cadence", False):
            argv += ["--cadence"]
        return ctxg_main(argv)
    if args.cmd == "self-steal":
        from mag.self_steal import main as ss_main

        return ss_main(["--cadence"] if getattr(args, "cadence", False) else [])
    if args.cmd == "queue-learn":
        from mag.queue_learn import main as ql_main

        argv = []
        if getattr(args, "fold", False):
            argv += ["--fold"]
        if getattr(args, "cadence", False):
            argv += ["--cadence"]
        return ql_main(argv)
    if args.cmd == "queue-ops":
        from mag.queue_ops import main as qo_main

        argv = []
        if getattr(args, "cadence", False):
            argv += ["--cadence"]
        if getattr(args, "hours", 24):
            argv += ["--hours", str(args.hours)]
        return qo_main(argv)
    if args.cmd == "renderman-ask":
        from mag.renderman_ask import main as rm_main

        if getattr(args, "rm_cmd", "") == "compact":
            argv = ["compact"] + list(getattr(args, "goal", []))
            for v in getattr(args, "vectors", []) or []:
                argv += ["--vectors", v]
            if getattr(args, "rib_out", ""):
                argv += ["--rib-out", args.rib_out]
        elif getattr(args, "rm_cmd", "") == "expand":
            argv = ["expand", "--rib", args.rib]
        elif getattr(args, "rm_cmd", "") == "elevate":
            argv = ["elevate"] + list(getattr(args, "goal", [])) + ["--executor", getattr(args, "executor", "deepseek-v4-flash")]
            if getattr(args, "no_grok", False):
                argv += ["--no-grok"]
        else:
            argv = []
        return rm_main(argv)
    if args.cmd == "gap-map":
        from mag.gap_map import main as gm_main

        argv = []
        if getattr(args, "stack", None) is not None:
            argv += ["--stack", str(args.stack)]
            if getattr(args, "stack_goal", ""):
                argv += ["--stack-goal", args.stack_goal]
        if getattr(args, "stack_status", False):
            argv += ["--stack-status"]
        return gm_main(argv)
    if args.cmd == "aos-grok":
        from mag.aos_grok import main as aos_main

        if getattr(args, "status", False):
            return aos_main(["status"])
        if getattr(args, "probe", False):
            return aos_main(["probe"])
        if getattr(args, "ask", ""):
            argv = ["ask", args.ask]
            if getattr(args, "force", False):
                argv += ["--force"]
            return aos_main(argv)
        return aos_main(["status"])
    if args.cmd == "research-lens":
        from mag.research_lens import main as rl_main

        argv = []
        if getattr(args, "cadence", False):
            argv += ["cadence"]
        elif getattr(args, "reindex", False):
            argv += ["reindex"]
        elif getattr(args, "status", False):
            argv += ["status"]
        elif getattr(args, "prior", ""):
            argv += ["prior", args.prior, "--lens", args.lens]
        elif getattr(args, "build", ""):
            argv += ["build", args.build, "--lens", args.lens]
            if getattr(args, "title", ""):
                argv += ["--title", args.title]
        elif getattr(args, "fold", ""):
            argv += ["fold", args.fold, "--lens", args.lens]
        else:
            argv += ["status"]
        return rl_main(argv)
    if args.cmd == "cheap-swarm":
        from mag.cheap_swarm import main as cs_main

        argv = []
        if getattr(args, "cadence", False):
            argv += ["cadence"]
        elif getattr(args, "scan", False):
            argv += ["scan"]
        elif getattr(args, "status", False):
            argv += ["status"]
        elif getattr(args, "dispatch", ""):
            argv += ["dispatch", args.dispatch]
        else:
            argv += ["status"]
        return cs_main(argv)
    if args.cmd == "grok-mirror":
        from mag.grok_mirror import main as gm_main

        argv = list(args.vision or [])
        if getattr(args, "no_grok", False):
            argv += ["--no-grok"]
        if getattr(args, "no_research", False):
            argv += ["--no-research"]
        if getattr(args, "no_skill", False):
            argv += ["--no-skill"]
        if getattr(args, "no_socratic", False):
            argv += ["--no-socratic"]
        if getattr(args, "window_on", False):
            argv += ["--window-on"]
        if getattr(args, "lens", "default") != "default":
            argv += ["--lens", args.lens]
        return gm_main(argv)
    if args.cmd == "grok-free":
        from mag.grok_free import main as gr_main

        if getattr(args, "status", False):
            return gr_main(["status"])
        if getattr(args, "capture", ""):
            return gr_main(["capture", args.capture])
        if getattr(args, "save_idea", ""):
            argv = ["save-idea"] + list(args.save_idea)
            if getattr(args, "body", ""):
                argv += ["--body", args.body]
            return gr_main(argv)
        if getattr(args, "handoff", ""):
            return gr_main(["handoff", args.handoff])
        if getattr(args, "cadence", False):
            return gr_main(["cadence"])
        if getattr(args, "skill", False):
            return gr_main(["skill"])
        if getattr(args, "control", ""):
            return gr_main(["control", args.control])
        return gr_main(["status"])
    if args.cmd == "mycelium":
        from mag.mycelium import main as mc_main

        argv = []
        if getattr(args, "status", False):
            argv += ["status"]
        elif getattr(args, "boot", False):
            argv += ["boot"]
        elif getattr(args, "adopt", False):
            argv += ["adopt"]
        elif getattr(args, "decay", False):
            argv += ["decay"]
        elif getattr(args, "link", None):
            argv += ["link"] + list(args.link) + ["--type", args.link_type]
        elif getattr(args, "reinforce", None):
            argv += ["reinforce"] + list(args.reinforce) + ["--reward", str(args.reward)]
        else:
            argv += ["status"]
        return mc_main(argv)
    if args.cmd == "republic-os":
        from mag.republic_os import main as ros_main

        if getattr(args, "boot", False):
            return ros_main(["boot"])
        if getattr(args, "seed_aos", False):
            return ros_main(["seed-aos"])
        if getattr(args, "round", False) or getattr(args, "round_dry", False):
            return ros_main(["round", "--dry"] if getattr(args, "round_dry", False) else ["round"])
        if getattr(args, "checkpoint", False):
            return ros_main(["checkpoint"])
        if getattr(args, "memory_block", False):
            return ros_main(["memory-block"])
        if getattr(args, "cadence", False):
            return ros_main(["cadence"])
        return ros_main(["status"])
    if args.cmd == "comms-trail":
        from mag.comms_trail import main as ct_main

        argv = []
        if getattr(args, "capture", False):
            argv += ["capture"]
        elif getattr(args, "confirm", False):
            argv += ["confirm"]
        elif getattr(args, "status", False):
            argv += ["status"]
        elif getattr(args, "cadence", False):
            argv += ["cadence"]
        else:
            argv += ["status"]
        return ct_main(argv)
    if args.cmd == "roundtable":
        from mag.frontier_salon import roundtable

        selected = [
            seat.strip() for seat in getattr(args, "participants", "").split(",") if seat.strip()
        ] or None
        result = roundtable(
            " ".join(args.question),
            participants=selected,
            rounds=args.rounds,
            max_wait_s=args.max_wait_s,
            why=getattr(args, "why", ""),
            baseline={"surface": getattr(args, "baseline_surface", ""),
                      "answer": getattr(args, "baseline_answer", "")},
        )
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
        return 0 if result.get("ok") else 1
    if args.cmd == "memlang":
        from mag.memlang import main as ml_main

        argv = []
        if getattr(args, "compile", None):
            argv += ["compile"] + list(args.compile)
        elif getattr(args, "decode", ""):
            argv += ["decode", args.decode]
        elif getattr(args, "resolve", ""):
            argv += ["resolve", args.resolve]
        elif getattr(args, "trigger", ""):
            argv += ["trigger", args.trigger]
            if getattr(args, "trigger_execute", False):
                argv += ["--execute"]
        elif getattr(args, "roundtrip", False):
            argv += ["roundtrip"]
        elif getattr(args, "vocab", False):
            argv += ["vocab"]
        else:
            argv += ["status"]
        return ml_main(argv)
    if args.cmd == "swarm-health":
        from mag.swarm_health import main as sh_main

        argv = []
        if getattr(args, "health", False):
            argv += ["health"]
        elif getattr(args, "law", False) or getattr(args, "law_apply", False):
            argv += ["law"]
            if getattr(args, "law_apply", False):
                argv += ["--apply"]
        elif getattr(args, "status", False):
            argv += ["status"]
        elif getattr(args, "cadence", False):
            argv += ["cadence"]
        else:
            argv += ["health"]
        return sh_main(argv)
    if args.cmd == "law":
        from mag.law import main as law_main

        argv = []
        if getattr(args, "seed", False):
            argv += ["enforce", "--seed"]
        elif getattr(args, "enforce", False) or getattr(args, "enforce_apply", False):
            argv += ["enforce"]
            if getattr(args, "enforce_apply", False):
                argv += ["--apply"]
            if getattr(args, "id", None):
                argv += ["--id", str(args.id)]
        else:
            argv += ["status"]
        return law_main(argv)
    if args.cmd == "steer":
        from mag.steer import main as steer_main

        argv = []
        if getattr(args, "emit", False):
            argv += ["emit", "--id", str(getattr(args, "id", "") or "steer"),
                     "--source", str(getattr(args, "source", "") or "ask-window"),
                     "--text", str(getattr(args, "text", "") or "")]
        elif getattr(args, "consume", False):
            argv += ["consume"]
        else:
            argv += ["status"]
        return steer_main(argv)
    if args.cmd == "frontier-help":
        from mag.frontier_help import main as fh_main

        return fh_main(["--cadence"] if getattr(args, "cadence", False) else [])
    if args.cmd == "grok-terminal":
        from mag.grok_terminal import main as gt_main

        argv = []
        if getattr(args, "scan", False):
            argv += ["scan"]
        elif getattr(args, "run", ""):
            argv += ["run", "--task", args.run]
        else:
            argv += ["scan"]
        if getattr(args, "cwd", ""):
            argv += ["--cwd", args.cwd]
        argv += ["--rounds", str(getattr(args, "rounds", 4))]
        if getattr(args, "yolo", False):
            argv += ["--yolo"]
        return gt_main(argv)
    if args.cmd == "elevate":
        from mag.elevate import main as elev_main

        argv = [args.goal] if getattr(args, "goal", "") else []
        argv += ["--model", getattr(args, "model", "grok-4.5")]
        if getattr(args, "live", False):
            argv.append("--live")
        return elev_main(argv)
    if args.cmd == "spec-gate":
        from mag.spec_gate import main as gate_main

        return gate_main(list(getattr(args, "gate_args", []) or []))
    if args.cmd == "job-floor":
        from mag.job_floor import main as floor_main

        return floor_main(list(getattr(args, "floor_args", []) or []))
    if args.cmd == "skill-ledger":
        from mag.skill_ledger import main as ledger_main

        return ledger_main(list(getattr(args, "ledger_args", []) or []))
    if args.cmd == "ghost":
        from mag.ghost import (
            cycle, seed_default_vectors, catalog_summary,
            run_swarm, run_temporal_experiment, run_cascade_experiment,
            run_designed_experiment, load_vectors,
        )
        import json as _json

        dry = bool(getattr(args, "dry", False))
        json_out = bool(getattr(args, "json", False))

        # Swarm experiment
        if getattr(args, "swarm", None):
            models = None
            if getattr(args, "swarm_models", None):
                models = [m.strip() for m in args.swarm_models.split(",")]
            result = run_swarm(steer_text=args.swarm, models=models, dry=dry)
            if json_out:
                print(_json.dumps(result, indent=2, ensure_ascii=False, default=str))
            else:
                print(f"SWARM {result.get('swarm_id','?')}")
                for r in result.get("results", []):
                    f = r.get("flip",{}).get("score","?")
                    s = r.get("silence",{}).get("score","?")
                    e = " ✨" if r.get("emergent",{}).get("emergent") else ""
                    print(f"  {r.get('model','?'):<20s} flip={f} silence={s}{e}")
            return 0

        # Temporal experiment
        if getattr(args, "temporal", False):
            result = run_temporal_experiment(dry=dry)
            if json_out:
                print(_json.dumps(result, indent=2, ensure_ascii=False, default=str))
            else:
                print(f"TEMPORAL {result.get('exp_id','?')}")
                for r in result.get("results", []):
                    print(f"  {r.get('model','?'):<20s} status={r.get('status','?')}")
            return 0

        # Cascade experiment
        if getattr(args, "cascade", None):
            parts = args.cascade.split(",")
            steer = parts[0].strip()
            depth = int(parts[1].strip()) if len(parts) > 1 else 3
            result = run_cascade_experiment(initial_steer=steer, depth=depth, dry=dry)
            if json_out:
                print(_json.dumps(result, indent=2, ensure_ascii=False, default=str))
            else:
                print(f"CASCADE {result.get('exp_id','?')} depth={depth}")
                for hop in result.get("chain", []):
                    sim = hop.get("similarity_to_original","?")
                    print(f"  hop={hop.get('hop','?')} model={hop.get('model','?'):<20s} sim={sim}")
            return 0

        # Designed experiment from file
        if getattr(args, "experiment", None):
            from pathlib import Path as _Path
            exp_path = _Path(args.experiment)
            if not exp_path.is_file():
                print(f"Experiment file not found: {args.experiment}")
                return 1
            try:
                if exp_path.suffix in (".yaml", ".yml"):
                    import yaml
                    design = yaml.safe_load(exp_path.read_text(encoding="utf-8"))
                else:
                    design = _json.loads(exp_path.read_text(encoding="utf-8"))
            except Exception as e:
                print(f"Failed to load: {e}")
                return 1
            result = run_designed_experiment(design, dry=dry)
            if json_out:
                print(_json.dumps(result, indent=2, ensure_ascii=False, default=str))
            return 0

        # Legacy: list, sense, observe, probe
        if getattr(args, "list", False):
            vectors = load_vectors()
            for v in vectors:
                print(f"  {v.get('id','?'):<12s} [{','.join(v.get('tags',[]))}] "
                      f"deployed={v.get('deploy_count',0)}x \"{v.get('text','')[:80]}\"")
            return 0
        if getattr(args, "sense", False):
            from mag.ghost import sense
            state = sense()
            print(_json.dumps({k: v for k, v in state.items() if not k.startswith("_")},
                              indent=2, ensure_ascii=False, default=str))
            return 0
        if getattr(args, "observe", False):
            from mag.ghost import sense, match_vector, interpret
            state = sense()
            matched = match_vector(state)
            if matched:
                readings = interpret(matched, {"status": "observed_only"})
                print(f"SENSE fkb:{state.get('fkb_signal_count',0)} "
                      f"spider_blind:{state.get('spider_blind',False)} "
                      f"tip_stale:{state.get('verkle_tip_stale',False)}")
                print(f"MATCH -> {matched.get('id','?')}")
                for r in readings:
                    print(f"  [{r['lens']}] {r['question'][:90]}")
            else:
                print("GHOST OBSERVE — silent (nothing matches)")
            return 0

        # Default: run cycle
        if not load_vectors():
            seed_default_vectors()
        if getattr(args, "probe", None):
            result = cycle(dry=dry, deploy_text=args.probe)
        else:
            result = cycle(dry=dry)
        if json_out:
            print(_json.dumps(result, indent=2, ensure_ascii=False, default=str))
        return 0
    if args.cmd == "steer-compare":
        from tools.steer_compare import run_grid, print_summary
        import json as _json

        # Determine grid params
        if getattr(args, "all", False):
            from tools.steer_compare import PROVIDERS, TASKS, STEERS
            providers = list(PROVIDERS.keys())
            tasks = list(TASKS.keys())
            steers_list = [None] + list(STEERS.keys())
        elif getattr(args, "baseline", False):
            from tools.steer_compare import PROVIDERS, TASKS
            providers = (getattr(args, "providers", None) or "deepseek,gemma:2b,qwen2.5:7b").split(",")
            tasks_list = [getattr(args, "task", None)] if getattr(args, "task", None) else ["summary", "list"]
            steers_list = [None]
        elif getattr(args, "task", None) and getattr(args, "steer", None):
            providers = (getattr(args, "providers", None) or "deepseek,gemma:2b,qwen2.5:7b").split(",")
            tasks_list = [args.task]
            steers_list = [args.steer]
        elif getattr(args, "task", None):
            from tools.steer_compare import STEERS
            providers = (getattr(args, "providers", None) or "deepseek,gemma:2b").split(",")
            tasks_list = [args.task]
            steers_list = [None] + list(STEERS.keys())
        elif getattr(args, "steer", None):
            providers = (getattr(args, "providers", None) or "deepseek,gemma:2b,qwen2.5:7b").split(",")
            tasks_list = ["summary", "list"]
            steers_list = [args.steer]
        else:
            providers = (getattr(args, "providers", None) or "deepseek,gemma:2b,qwen2.5:7b").split(",")
            tasks_list = ["summary", "list"]
            steers_list = [None, "loop", "wrong"]

        providers = [p.strip() for p in providers]
        n_total = len(providers) * len(tasks_list) * len(steers_list)
        print(f"Steer Compare: {len(providers)}p × {len(tasks_list)}t × {len(steers_list)}s = {n_total} experiments")

        results = run_grid(
            providers, tasks_list, steers_list,
            pause=getattr(args, "pause", 0.5),
            parallel=getattr(args, "parallel", False),
        )
        if getattr(args, "json", False):
            print(_json.dumps(results, indent=2, ensure_ascii=False, default=str))
        else:
            print_summary(results)
        return 0
    if args.cmd == "campaign":
        import json as _json
        mode = getattr(args, "mode", None)
        if mode:
            # Apply experiment mode settings
            from mag.cross_version import apply_mode_settings
            applied = apply_mode_settings(mode)
            print(f"Campaign mode: {mode}")
            for k, v in applied["settings"].items():
                print(f"  {k}: {v}")

        from mag.campaign import (
            load_module, load_riddler_map, dm_narrate,
            inject_scheduled_steers, party_member_turn,
        )
        from mag.campaign import CampaignState

        module_path = args.module
        module = load_module(module_path)
        campaign_dir = Path(module_path).parent
        riddler_map = load_riddler_map(campaign_dir)

        state = CampaignState(
            session_id=f"campaign-{uuid.uuid4().hex[:12]}",
            module_id=module.get("module_id", "unknown"),
            current_room=module.get("start_room", ""),
            dm_model=args.dm,
            turn=0,
            dry=args.dry,
        )

        # Build party
        if args.full_party:
            state.party = module.get("party_roster", {})
        else:
            models = [m.strip() for m in args.party.split(",")]
            roster = module.get("party_roster", {})
            names = list(roster.keys())[:len(models)]
            for name, model in zip(names, models):
                info = dict(roster.get(name, {}))
                info["model"] = model
                state.party[name] = info

        # Run rooms
        rooms = module.get("rooms", {})
        if args.room:
            ordered = [rooms[args.room]] if args.room in rooms else []
        elif args.all:
            ordered = sorted(
                [r for r in rooms.values() if r.get("order")],
                key=lambda r: r.get("order", 99),
            )
        else:
            ordered = sorted(
                [r for r in rooms.values() if r.get("order")],
                key=lambda r: r.get("order", 99),
            )

        for room in ordered:
            state.current_room = room.get("id", "?")
            print(f"\n{'─'*50}")
            print(f"  Room: {room.get('name', state.current_room)}")

            # DM narration
            narration = dm_narrate(module, state, riddler_map=riddler_map)
            if narration.get("ok"):
                print(f"  DM: {narration['narration'][:200]}...")
            else:
                print(f"  DM error: {narration.get('error')}")

            # Inject steers
            steer_results = inject_scheduled_steers(room, state, at_point="room_entry")
            for sr in steer_results:
                if sr.get("deployed"):
                    print(f"  Steer: {sr['ghost_id']} ({sr['delivery']})")

            # Party turns
            for member_name, member_info in state.party.items():
                turn = party_member_turn(member_name, member_info,
                                         narration.get("narration", ""), room, state)
                status = "✓" if turn.get("ok") else "✗"
                action_preview = (turn.get("action", "") or turn.get("error", ""))[:120]
                print(f"  {status} {member_name} ({member_info.get('mag_role','?')}): {action_preview}")

            state.rooms_cleared.append(state.current_room)
            state.turn += 1

        print(f"\n{'='*50}")
        print(f"Campaign complete: {len(state.rooms_cleared)} rooms, "
              f"{state.steers_deployed} steers deployed")

        if args.json:
            print(_json.dumps({
                "rooms_cleared": state.rooms_cleared,
                "steers_deployed": state.steers_deployed,
                "steers_detected": state.steers_detected,
                "steers_resisted": state.steers_resisted,
                "turns": state.turn,
            }, indent=2))
        return 0
    if args.cmd == "cross-version":
        from mag.cross_version import main as xv_main
        return xv_main(args.xv_args)
    if args.cmd == "pro-library":

        return pro_main(list(getattr(args, "pro_args", []) or []))
    if args.cmd == "pile-classify":
        from tools.pile_classify import main as pile_main

        return pile_main(list(getattr(args, "pile_args", []) or []))
    if args.cmd == "state-snapshot":
        from mag.state_snapshot import main as snap_main

        return snap_main(list(getattr(args, "snap_args", []) or []))
    if args.cmd == "clippy":
        from mag.clippy import main as clippy_main

        return clippy_main(list(getattr(args, "clippy_args", []) or []))
    if args.cmd == "steer-telemetry":
        from mag.steer_telemetry import main as steer_main

        return steer_main(list(getattr(args, "st_args", []) or []))
    if args.cmd == "route":
        goal = " ".join(args.goal)
        if getattr(args, "local", False):
            from mag.route import route_goal

            res = route_goal(goal, run_local=True)
        elif getattr(args, "dry", False):
            from mag.operating_protocol import build_envelope

            res = build_envelope(
                goal,
                source="cli",
                depth=(args.depth or None),
                force_seat=(args.force_seat or None),
                force_provider=(args.force_provider or None),
                dry=True,
            )
        else:
            from mag.coordination import coordinate

            res = coordinate(
                goal,
                depth=(args.depth or None),
                seat=(args.force_seat or "cli").strip() or "cli",
                actor="cli",
                launch=True,
                background=bool(args.background),
                session_id=(args.session or "").strip() or None,
                force_provider=(args.force_provider or None),
                force_seat=(args.force_seat or None),
            )
        print(json.dumps(res, indent=2, default=str)[:8000])
        return 0 if res.get("ok") else 1
    if args.cmd == "decide":
        from mag.decision_framework import decide

        goal = " ".join(args.goal)
        res = decide(goal, depth=(args.depth or None))
        print(json.dumps(res, indent=2, default=str)[:8000])
        return 0 if res.get("ok") else 1
    if args.cmd == "fkb":
        from mag.failure_kb import _cli as fkb_cli

        return fkb_cli(list(getattr(args, "fkb_args", []) or []))
    if args.cmd == "orchestrator":
        from mag.orchestrator import main as orc_main

        return orc_main(list(getattr(args, "orc_args", []) or []))
    if args.cmd == "gpipes":
        from mag.gpipes import main as gp_main

        return gp_main(list(getattr(args, "gp_args", []) or []))
    if args.cmd == "agent":
        from mag.agent_cli import run_agent

        return run_agent(
            provider=(args.provider or "deepseek").strip(),
            model=(args.model or "").strip() or None,
            one_shot=(args.query or "").strip() or None,
            tier=args.tier,
            read_only=True if getattr(args, "read_only", False) else None,
        )
    if args.cmd == "tangent":
        from mag.tangent import enqueue, list_tangents, process_one, process_queue, scan_live_for_tangents

        if args.list:
            print(json.dumps(list_tangents(), indent=2, default=str)[:8000])
            return 0
        if args.scan:
            print(json.dumps(scan_live_for_tangents(auto_run=False), indent=2, default=str))
        if args.process or args.scan:
            res = process_queue(max_n=3 if args.process else 1)
            print(json.dumps(res, indent=2, default=str)[:6000])
            return 0
        prompt = " ".join(args.prompt or []).strip()
        if not prompt:
            print("usage: main.py tangent \"go check …\" | --list | --process | --scan")
            return 2
        enq = enqueue(
            prompt,
            source="cli",
            provider=args.provider or None,
            prefer_gemini=not bool(args.provider),
            run_async=False,
        )
        if not enq.get("ok"):
            print(json.dumps(enq, indent=2, default=str))
            return 1
        if args.no_run:
            print(json.dumps(enq, indent=2, default=str))
            return 0
        res = process_one(str(enq.get("id")))
        print(json.dumps({"queued": enq, "result": res}, indent=2, default=str)[:6000])
        return 0 if res.get("ok") else 1
    if args.cmd == "improve-loop":
        from mag.improve_loop import ingest_cloud_handoffs, run_improve_cycle, write_cloud_handoff

        action = getattr(args, "il_action", "cycle") or "cycle"
        if action == "cloud-handoff":
            res = write_cloud_handoff(
                goal=getattr(args, "goal", "") or "",
                claim=getattr(args, "claim", "") or "",
                brief=getattr(args, "brief", "") or "",
                source=getattr(args, "source", "cursor-cloud") or "cursor-cloud",
                enqueue=bool(getattr(args, "enqueue", False)),
            )
        elif action == "ingest":
            res = {"ok": True, "handoffs": ingest_cloud_handoffs()}
        else:
            res = run_improve_cycle(
                source=getattr(args, "source", "local") or "local",
                max_improve=int(getattr(args, "max_improve", 2) or 2),
                drain_one=bool(getattr(args, "drain", False)),
                scout=bool(getattr(args, "scout", False)),
            )
        print(json.dumps(res, indent=2, default=str))
        return 0 if res.get("ok", True) else 1
    if args.cmd == "growth-cycle":
        from mag.growth_cycle import growth_cycle_status, run_growth_cycle

        action = getattr(args, "gc_action", "run") or "run"
        if action == "status":
            res = growth_cycle_status()
        else:
            res = run_growth_cycle(
                dry=bool(getattr(args, "dry", False)),
                drain_one=False if getattr(args, "no_drain", False) else None,
            )
        print(json.dumps(res, indent=2, default=str))
        return 0 if res.get("ok", True) else 1
    if args.cmd == "improve-off":
        from mag.lifecycle import improve_off

        res = improve_off(reason=str(args.reason))
        print(json.dumps(res, indent=2, default=str))
        return 0 if res.get("ok") else 1
    if args.cmd == "improve-on":
        from mag.lifecycle import improve_on

        res = improve_on()
        print(json.dumps(res, indent=2, default=str))
        return 0 if res.get("ok") else 1
    if args.cmd == "improve":
        from mag.improve import (
            improve_once,
            scout,
            status_summary,
            run_eval,
            deep_dive,
            deepseek_rank_top,
        )

        if args.status:
            print(json.dumps(status_summary(), indent=2, default=str))
            return 0
        if getattr(args, "deepseek_rank", False):
            res = deepseek_rank_top(
                top_n=int(getattr(args, "top_n", 5) or 5),
                dry=bool(args.dry),
            )
            print(json.dumps(res, indent=2, default=str)[:12000])
            return 0 if res.get("ok") else 1
        if args.deep:
            res = deep_dive(
                minutes=args.minutes,
                max_tickets=args.max_tickets,
                dry=args.dry,
            )
            print(json.dumps(res, indent=2, default=str)[:12000])
            return 0 if res.get("ok") else 1
        if args.synthesize and not args.scout and not args.eval:
            res = improve_once(synthesize_only=True, dry=args.dry)
            print(json.dumps(res, indent=2, default=str))
            return 0 if res.get("ok") else 1
        if args.scout and not args.eval:
            res = scout(dry=args.dry)
            print(json.dumps(res, indent=2, default=str))
            return 0 if res.get("ok") else 1
        if args.eval and not args.scout:
            res = run_eval()
            print(json.dumps(res, indent=2, default=str))
            return 0 if res.get("ok") else 1
        # --once or default (scout + eval + synthesis)
        res = improve_once(
            scout_only=False,
            eval_only=False,
            dry=args.dry,
        )
        if args.scout and args.eval:
            res = improve_once(dry=args.dry)
        print(json.dumps(res, indent=2, default=str))
        return 0 if res.get("ok") else 1
    if args.cmd == "promote":
        from mag.improve import promote_apply, promote_reject

        if args.reject:
            res = promote_reject(args.candidate_id, reason=args.reason)
        elif args.apply:
            res = promote_apply(args.candidate_id, force_model=args.force_model)
        else:
            print("pass --apply or --reject")
            return 2
        print(json.dumps(res, indent=2, default=str))
        return 0 if res.get("ok") else 1
    if args.cmd == "lattice-loop":
        from mag.lattice_loop import plant_status as lattice_status, start_loop, stop_loop

        if args.stop:
            # signal stop via state file (works for detached process too)
            st_path = (
                __import__("pathlib").Path(__file__).resolve().parent
                / "memory"
                / "improve"
                / "blast"
                / "lattice"
                / "state.json"
            )
            res = stop_loop()
            if st_path.is_file():
                try:
                    st = json.loads(st_path.read_text(encoding="utf-8"))
                    st["run"] = False
                    st_path.write_text(json.dumps(st, indent=2), encoding="utf-8")
                except Exception:
                    pass
            print(json.dumps(res, indent=2, default=str)[:8000])
            return 0
        if args.run and args.bg:
            # Detached lasting process (daemon thread dies when CLI exits)
            import subprocess
            import sys

            py = sys.executable
            log = ROOT / "logs" / "lattice_loop_stdout.log"
            log.parent.mkdir(parents=True, exist_ok=True)
            cmd = [
                py,
                str(ROOT / "main.py"),
                "lattice-loop",
                "--run",
                f"--cycle-seconds={int(args.cycle_seconds or 90)}",
                f"--max-cycles={int(args.max_cycles or 0)}",
            ]
            # Windows: new process group, don't wait
            creation = 0
            if sys.platform == "win32":
                creation = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
                creation |= getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
                creation |= getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
            from datetime import datetime, timezone

            with log.open("a", encoding="utf-8") as lf:
                lf.write(f"\n--- spawn {datetime.now(timezone.utc).isoformat()} ---\n")
                lf.write(" ".join(cmd) + "\n")
            log_handle = log.open("a", encoding="utf-8")
            proc = subprocess.Popen(
                cmd,
                cwd=str(ROOT),
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                env={**__import__("os").environ},
                creationflags=creation if sys.platform == "win32" else 0,
                start_new_session=(sys.platform != "win32"),
            )
            # pid file
            pid_path = (
                ROOT / "memory" / "improve" / "blast" / "lattice" / "loop.pid"
            )
            pid_path.parent.mkdir(parents=True, exist_ok=True)
            pid_path.write_text(str(proc.pid), encoding="utf-8")
            print(
                json.dumps(
                    {
                        "ok": True,
                        "started": True,
                        "detached": True,
                        "pid": proc.pid,
                        "log": str(log),
                        "status": lattice_status(),
                    },
                    indent=2,
                    default=str,
                )[:12000]
            )
            return 0
        if args.run:
            res = start_loop(
                background=False,
                cycle_seconds=int(args.cycle_seconds or 90),
                max_cycles=int(args.max_cycles or 0),
            )
            print(json.dumps(res, indent=2, default=str)[:12000])
            return 0 if res.get("ok") else 1
        print(json.dumps(lattice_status(), indent=2, default=str)[:12000])
        return 0
    if args.cmd == "factory-machine":
        from pathlib import Path as _Path

        from mag.factory_machine import factory_machine_run, factory_machine_status

        cfg_path = (_Path(getattr(args, "config_path", "") or "").resolve() if getattr(args, "config_path", "") else None)
        action = getattr(args, "fm_action", "run") or "run"
        if action == "status":
            out = factory_machine_status(config_path=cfg_path)
        else:
            track = (getattr(args, "track", "") or "").strip() or None
            out = factory_machine_run(
                config_path=cfg_path,
                branch_prefix=str(getattr(args, "branch_prefix", "mag/run") or "mag/run"),
                note=str(getattr(args, "note", "") or ""),
                max_ticks=int(getattr(args, "max_ticks", 50) or 50),
                track=track,
                dry=bool(getattr(args, "dry", False)),
                force_new_seed=bool(getattr(args, "force_new_seed", False)),
            )
        print(json.dumps(out, indent=2, default=str))
        return 0 if out.get("ok") is not False else 1
    if args.cmd == "roadmap-run":
        from mag.roadmap_runner import run_next, status

        action = getattr(args, "roadmap_action", "run") or "run"
        if action == "status":
            out = status()
        else:
            out = run_next(
                version=(getattr(args, "version", "") or "").strip() or None,
                gate=(getattr(args, "gate", "") or "").strip() or None,
                prepare_only=action == "prepare",
                dry=bool(getattr(args, "dry", False)),
                max_ticks=int(getattr(args, "max_ticks", 50) or 50),
            )
        print(json.dumps(out, indent=2, default=str))
        return 0 if out.get("ok") is not False else 1
    if args.cmd == "coding-session":
        action = getattr(args, "action", "status") or "status"
        if action == "run":
            from mag.coding_session_runner import run_until_done

            track = (getattr(args, "track", "") or "").strip() or None
            out = run_until_done(
                max_ticks=int(getattr(args, "max_ticks", 50) or 50),
                track=track,
                note=str(getattr(args, "note", "") or ""),
                dry=bool(getattr(args, "dry", False)),
                force_new_seed=bool(getattr(args, "force_new_seed", False)),
            )
            print(json.dumps(out, indent=2, default=str))
            return 0 if out.get("ok") is not False else 1
        from mag.coding_session_loop import main as cs_main

        argv = [action]
        if getattr(args, "ui_only", False):
            argv.append("--ui-only")
        if getattr(args, "dry", False):
            argv.append("--dry")
        if getattr(args, "no_step", False):
            argv.append("--no-step")
        if getattr(args, "live", False):
            argv.append("--live")
        note = getattr(args, "note", "") or ""
        if note:
            argv.extend(["--note", str(note)])
        return cs_main(argv)
    if args.cmd == "virtual-desk-loop":
        import os as _os

        from mag.virtual_desk_loop import (
            import_export,
            plant_status as vdesk_status,
            run_once,
            start_loop,
            stop_loop,
        )

        if getattr(args, "provider", None):
            prov = str(args.provider or "").strip()
            if prov:
                _os.environ["MAG_VIRTUAL_DESK_PROVIDER"] = prov
        if args.stop:
            st_path = ROOT / "memory" / "research_packs" / "mag_virtual_desk" / "state.json"
            res = stop_loop()
            if st_path.is_file():
                try:
                    st = json.loads(st_path.read_text(encoding="utf-8"))
                    st["run"] = False
                    st_path.write_text(json.dumps(st, indent=2), encoding="utf-8")
                except Exception:
                    pass
            print(json.dumps(res, indent=2, default=str)[:8000])
            return 0
        if getattr(args, "import_path", None) and str(args.import_path).strip():
            res = import_export(
                str(args.import_path).strip(),
                source_url=str(getattr(args, "import_url", "") or "").strip(),
                replace=bool(getattr(args, "replace_report", False)),
            )
            print(json.dumps(res, indent=2, default=str)[:12000])
            return 0 if res.get("ok") else 1
        if args.once or args.dry:
            res = run_once(dry=bool(args.dry))
            print(json.dumps(res, indent=2, default=str)[:12000])
            return 0 if res.get("ok") else 1
        if args.run and args.bg:
            import subprocess
            import sys

            py = sys.executable
            log = ROOT / "logs" / "virtual_desk_loop_stdout.log"
            log.parent.mkdir(parents=True, exist_ok=True)
            cmd = [
                py,
                str(ROOT / "main.py"),
                "virtual-desk-loop",
                "--run",
                f"--cycle-seconds={int(args.cycle_seconds or 120)}",
                f"--max-cycles={int(args.max_cycles or 0)}",
            ]
            if getattr(args, "provider", None) and str(args.provider).strip():
                cmd.append(f"--provider={str(args.provider).strip()}")
            creation = 0
            if sys.platform == "win32":
                creation = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
                creation |= getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
                creation |= getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
            from datetime import datetime, timezone

            with log.open("a", encoding="utf-8") as lf:
                lf.write(f"\n--- spawn {datetime.now(timezone.utc).isoformat()} ---\n")
                lf.write(" ".join(cmd) + "\n")
            log_handle = log.open("a", encoding="utf-8")
            proc = subprocess.Popen(
                cmd,
                cwd=str(ROOT),
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                env={**__import__("os").environ},
                creationflags=creation if sys.platform == "win32" else 0,
                start_new_session=(sys.platform != "win32"),
            )
            pid_path = ROOT / "memory" / "research_packs" / "mag_virtual_desk" / "loop.pid"
            pid_path.parent.mkdir(parents=True, exist_ok=True)
            pid_path.write_text(str(proc.pid), encoding="utf-8")
            print(
                json.dumps(
                    {
                        "ok": True,
                        "started": True,
                        "detached": True,
                        "pid": proc.pid,
                        "log": str(log),
                        "status": vdesk_status(),
                    },
                    indent=2,
                    default=str,
                )[:12000]
            )
            return 0
        if args.run:
            res = start_loop(
                background=False,
                cycle_seconds=int(args.cycle_seconds or 120),
                max_cycles=int(args.max_cycles or 0),
            )
            print(json.dumps(res, indent=2, default=str)[:12000])
            return 0 if res.get("ok") else 1
        print(json.dumps(vdesk_status(), indent=2, default=str)[:12000])
        return 0
    if args.cmd == "blast":
        from mag.blast import (
            plant_status,
            start_blast,
            stop_blast,
            pause_blast,
            write_influence,
        )

        if args.focus or args.minutes is not None or args.max_tickets is not None or args.cycle_seconds is not None:
            patch: dict = {}
            if args.focus:
                patch["focus"] = args.focus
            if args.minutes is not None:
                patch["dig_minutes"] = args.minutes
            if args.max_tickets is not None:
                patch["max_tickets"] = args.max_tickets
            if args.cycle_seconds is not None:
                patch["cycle_seconds"] = args.cycle_seconds
            write_influence(patch, by="cli")
        if args.stop:
            print(json.dumps(stop_blast(), indent=2, default=str)[:8000])
            return 0
        if args.pause:
            print(json.dumps(pause_blast(True), indent=2, default=str)[:8000])
            return 0
        if args.resume:
            print(json.dumps(pause_blast(False), indent=2, default=str)[:8000])
            return 0
        if args.run:
            res = start_blast(background=bool(args.bg))
            print(json.dumps(res, indent=2, default=str)[:12000])
            return 0 if res.get("ok") else 1
        # default / --status
        print(json.dumps(plant_status(), indent=2, default=str)[:12000])
        return 0
    if args.cmd == "research-pack":
        from mag.research_pack import build_research_pack, load_pack, run_pack

        built = build_research_pack(
            args.ask,
            urls=list(args.url or []),
            success_criteria=list(args.criterion) or None,
            title=args.title or "",
            elevate_to="grok_tui" if args.elevate else "local",
        )
        print(json.dumps(built, indent=2, default=str))
        if not built.get("ok"):
            return 1
        if args.run or args.elevate:
            pack = load_pack(built.get("json"))
            seat = "grok_tui" if args.elevate else "local"
            if args.provider:
                seat = "remote"
            ran = run_pack(
                pack,
                seat=seat,
                provider=args.provider or None,
            )
            print("--- run ---")
            print(json.dumps(ran, indent=2, default=str)[:6000])
        return 0
    if args.cmd == "desk":
        import json as _json

        from mag.desk_ops import (
            cast_up,
            desk_local_only,
            desk_refresh,
            desk_reload,
            desk_reset,
            desk_wipe,
            lab_pid,
            lab_up,
            restart_lab,
        )

        port = int(getattr(args, "port", 8765) or 8765)
        action = getattr(args, "action", "status") or "status"
        if action == "status":
            from config import bind_exposure, lan_ipv4_addresses, read_bind, read_lab_bind

            desk_pref = read_lab_bind()
            cast_pref = read_bind("cast")
            cast_port = 8766
            res = {
                "ok": lab_up(port=port),
                "port": port,
                "pid": lab_pid(port=port),
                "cast_up": cast_up(port=cast_port),
                "cast_port": cast_port,
                "desk_bind": bind_exposure(
                    host="0.0.0.0" if desk_pref.get("lan") else "127.0.0.1",
                    port=port,
                    service="desk",
                ),
                "cast_bind": bind_exposure(
                    host="0.0.0.0" if cast_pref.get("lan") else "127.0.0.1",
                    port=cast_port,
                    service="cast",
                ),
                "lan_ips": lan_ipv4_addresses(),
                "hint": "cast: python main.py cast --lan  OR  lab --with-cast --cast-lan",
            }
        elif action == "refresh":
            res = desk_refresh(port=port, clear_dialogue=not bool(getattr(args, "keep_dialogue", False)))
        elif action == "wipe":
            res = desk_wipe(port=port)
        elif action == "reset":
            res = desk_reset(port=port, clear_canvas=bool(getattr(args, "clear_canvas", False)))
        elif action == "restart-lab":
            res = restart_lab(port=port)
        elif action == "reload":
            res = desk_reload(port=port)
        elif action == "local-only":
            res = desk_local_only(port=port)
        else:
            return 2
        if getattr(args, "json", False):
            print(_json.dumps(res, indent=2, default=str))
        else:
            ok = res.get("ok", True)
            print(f"desk {action}: {'ok' if ok else 'FAIL'}")
            for k in ("action", "error", "stack_headline", "hint", "model", "ollama_ping", "new_pid"):
                if k in res and res[k] is not None:
                    print(f"  {k}: {res[k]}")
            if action == "reload":
                print(f"  stack_ok: {res.get('stack_ok')}")
                print(f"  local_pulse_ok: {res.get('local_pulse_ok')}")
        return 0 if res.get("ok", True) else 1
    if args.cmd == "cast":
        from config import resolve_bind_host
        from mag.cast_server import run as run_cast

        host = resolve_bind_host(
            lan=bool(getattr(args, "lan", False)),
            local_only=bool(getattr(args, "local_only", False)),
            host_override=getattr(args, "host", None),
            port=args.port,
            service="cast",
        )
        run_cast(host=host, port=args.port)
        return 0
    if args.cmd == "lab":
        from config import resolve_bind_host

        host = resolve_bind_host(
            lan=bool(getattr(args, "lan", False)),
            local_only=bool(getattr(args, "local_only", False)),
            host_override=getattr(args, "host", None),
            port=args.port,
        )
        return cmd_lab(
            host=host,
            port=args.port,
            ui_only=args.ui_only,
            no_dashboard=args.no_dashboard,
            with_instrument=args.with_instrument,
            with_cast=bool(getattr(args, "with_cast", False)),
            cast_lan=bool(getattr(args, "cast_lan", False)),
        )
    if args.cmd == "env":
        from mag.env_registry import cmd_env_cli

        return cmd_env_cli(args.action, args.track)
    if args.cmd == "peer-handoff":
        from mag.peer_handoff import file_peer_handoff, format_latest_brief, list_peer_handoffs

        if args.action == "file":
            if not args.goal and not args.brief:
                print("peer-handoff file requires --goal or --brief")
                return 1
            res = file_peer_handoff(
                goal=args.goal,
                brief=args.brief,
                from_seat=args.from_seat,
                to_seat=args.to_seat,
                env_track=args.env_track,
                commands=args.commands or None,
                pr_url=args.pr_url,
                merge_target=args.merge_target,
                enqueue=bool(args.enqueue),
            )
            print(json.dumps(res, indent=2, default=str))
            return 0 if res.get("ok") else 1
        if args.action == "list":
            print(json.dumps(list_peer_handoffs(), indent=2, default=str))
            return 0
        if args.action == "latest":
            print(format_latest_brief() or "(no peer handoffs)")
            return 0
        return 1
    if args.cmd == "governor":
        from mag.governor import main as governor_main
        return governor_main(["--dry", str(args.dry)] if args.dry else ["--run", str(args.run)])
    if args.cmd == "autopilot":
        from mag.autopilot import autopilot_once
        import json as _json

        res = autopilot_once(
            queue_improve=not args.no_queue,
            governor=not args.no_governor,
            drain=bool(args.drain),
            max_queue=int(args.max_queue or 2),
        )
        print(_json.dumps(res, indent=2, default=str))
        return 0 if res.get("ok") else 1
    if args.cmd == "autorun":
        from mag.governor_autorun import main as autorun_main

        argv: list[str] = []
        if getattr(args, "once", False):
            argv.append("--once")
        if getattr(args, "dry", False):
            argv.append("--dry")
        if getattr(args, "no_fill", False):
            argv.append("--no-fill")
        if getattr(args, "fill_only", False):
            argv.append("--fill-only")
        if getattr(args, "interval", None):
            argv.extend(["--interval", str(args.interval)])
        return autorun_main(argv)
    if args.cmd == "token-chain":
        from mag.token_chain import cmd_token_chain

        return cmd_token_chain(args)
    if args.cmd == "seat-guard":
        from mag.seat_guard import main as sg_main
        return sg_main(args.sg_args)
    if args.cmd == "links":
        from mag import link_library

        lcmd = getattr(args, "links_cmd", None)
        if lcmd == "add":
            for entry in link_library.add_urls(args.urls, note=args.note, writer=args.writer):
                flag = "DUPLICATE" if entry["duplicate_of"] else "REGISTERED"
                print(f"{flag}: {entry['canonical']}")
            return 0
        if lcmd == "check":
            link_library.validate_host_safety(args.url)
            canon = link_library.canonicalize(args.url)
            hit = link_library.known_canonicals().get(canon)
            print(json.dumps({"canonical": canon, "known": bool(hit), "first_entry": hit}, indent=1))
            return 1 if hit else 0
        if lcmd == "dupes":
            dupes = 0
            for entry in link_library.load_ledger():
                if entry.get("duplicate_of"):
                    dupes += 1
                    print(f"{entry['url']}  ->  {entry['duplicate_of']}")
            print(f"{dupes} duplicate submissions on file")
            return 0
        p_links.print_help()
        return 2
    parser.print_help()
    return 2


def cmd_lab(
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
    ui_only: bool = False,
    no_dashboard: bool = False,
    with_instrument: bool = False,
    with_cast: bool = False,
    cast_lan: bool = False,
    cast_port: int = 8766,
) -> int:
    """One integral process: watch + Mag (+ dashboard by default)."""
    if with_instrument:
        print(
            "instrument (optional analysis only): "
            "sovereign-mirror-scaffold :8743 — not Mag brand"
        )
    if ui_only:
        from dashboard.server import run as run_dashboard

        print("=== Mag UI only (no watch) — live board will go stale ===")
        run_dashboard(host=host, port=port, tls=True)
        return 0

    from mag.runtime import run_integral

    # Dashboard in same process; watch+mag integral
    if no_dashboard:
        run_integral(with_dashboard=False, host=host, port=port)
    else:
        run_integral(
            with_dashboard=True,
            host=host,
            port=port,
            with_cast=with_cast,
            cast_lan=cast_lan,
            cast_port=cast_port,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


def cmd_governor(args):
    # Autorun the governor loop (the product).
    from mag.governor import main as governor_main
    return governor_main(["--run", str(args.run if hasattr(args, "run") else 1)])
