"""Core agent commands: run, status, ingest, watch, dashboard, knot-evolution, summarize-session."""
from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from audit import log_event, sync_current  # noqa: E402
from config import HANDOFF_DIR, RESULTS_DIR, STATE_DIR  # noqa: E402
from graph import default_graph  # noqa: E402
from handoff.schema import validate_handoff  # noqa: E402
from handoff.verify import load_json, verify_result  # noqa: E402


def cmd_run(goal: str, thread_id: str | None = None) -> int:
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
    log_event({"event": "ingest_result", "handoff_id": handoff_id, "passed": passed})
    print(json.dumps({"ok": passed, "notes": notes}, indent=2))
    return 0 if passed else 1


def add_parser(sub) -> None:
    p_run = sub.add_parser("run", help="Run a goal")
    p_run.add_argument("goal", nargs="+", help="Goal text")
    p_run.add_argument("--thread", default=None)

    sub.add_parser("status", help="Show CURRENT.md")

    p_ing = sub.add_parser("ingest", help="Ingest Grok result for handoff id")
    p_ing.add_argument("handoff_id")

    p_watch = sub.add_parser(
        "watch", help="Watch live Grok session into memory/live_from_grok.md"
    )
    p_watch.add_argument("--once", action="store_true")
    p_watch.add_argument("--interval", type=float, default=3.0)

    p_dash = sub.add_parser(
        "dashboard",
        help="Browse history: sessions, PDFs, Verkle, ingest (http://127.0.0.1:8765)",
    )
    p_dash.add_argument("--host", default="127.0.0.1")
    p_dash.add_argument("--port", type=int, default=8765)

    sub.add_parser(
        "knot-evolution",
        help="Show living Verkle-knot topic evolution across session records",
    )

    p_sum = sub.add_parser(
        "summarize-session",
        help="Write Mag biography summary for a Grok session (default: active)",
    )
    p_sum.add_argument("--session", default="", help="Session id (default: active pointer)")
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
        "--no-pdf",
        action="store_true",
        help="Deprecated: PDF already off by default",
    )


def dispatch(args) -> int:
    if args.cmd == "run":
        return cmd_run(" ".join(args.goal), thread_id=args.thread)
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

        sid = args.session.strip()
        if not sid:
            resolved = resolve_session()
            if not resolved:
                print("no active session; pass --session <id>")
                return 1
            sid = resolved[0]
        res = summarize_session(
            sid,
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
        from dashboard.server import run as run_dashboard

        run_dashboard(host=args.host, port=args.port)
        return 0
    return 2
