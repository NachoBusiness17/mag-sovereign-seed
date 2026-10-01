"""Sovereign Mag background loop."""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from audit import log_event
from config import ROOT
from mag.act import act
from mag.judge import judge
from mag.policy import load_policy, resolve
from mag.sense import sense


def _mag_log(pol: dict, event: dict[str, Any]) -> None:
    path = resolve(pol.get("log_path") or "logs/mag.jsonl")
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"ts": datetime.now(timezone.utc).isoformat(), **event}
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, default=str) + "\n")
    log_event({"mag": True, **event})


def _maybe_summarize_ended_sessions() -> None:
    """On session switch: amend previous session record (same files, no duplicates).

    Also lightly amend *current* open session when chat grew (periodic living doc).
    """
    try:
        from mag.biography import summarize_session
        from watch.tail_session import resolve_session
    except Exception:
        return

    pointer = ROOT / "watch" / "last_seen_session.txt"
    prev = pointer.read_text(encoding="utf-8").strip() if pointer.is_file() else ""
    resolved = resolve_session()
    current = resolved[0] if resolved else ""
    if prev and prev != current:
        try:
            res = summarize_session(prev, use_llm=True, force=False, amend=True)
            _mag_log(load_policy(), {"phase": "session_end_summary_fallback", **res})
        except Exception as e:
            _mag_log(load_policy(), {"phase": "session_end_summary_fallback", "error": str(e)})
    # Living amend of active session (skips if chat unchanged)
    if current:
        try:
            res = summarize_session(current, use_llm=False, force=False, amend=True, pdf=False)
            if not res.get("skipped"):
                _mag_log(load_policy(), {"phase": "session_live_amend", **{k: res.get(k) for k in ("ok", "amended", "lines", "source")}})
        except Exception as e:
            _mag_log(load_policy(), {"phase": "session_live_amend", "error": str(e)})
        pointer.parent.mkdir(parents=True, exist_ok=True)
        pointer.write_text(current, encoding="utf-8")

    # Mag agent seats → same Verkle/workday path (seat-agnostic FILE)
    try:
        from mag.chat_source import file_dirty_agent_sessions

        agent_res = file_dirty_agent_sessions(use_llm=False, force=False)
        if agent_res.get("n"):
            _mag_log(
                load_policy(),
                {
                    "phase": "agent_workday_amend",
                    "n": agent_res.get("n"),
                    "results": (agent_res.get("results") or [])[:8],
                },
            )
    except Exception as e:
        _mag_log(load_policy(), {"phase": "agent_workday_amend", "error": str(e)})


def run_cycle() -> dict[str, Any]:
    pol = load_policy()
    if pol.get("watch_before_cycle"):
        try:
            from watch.tail_session import once as watch_once

            watch_once()
        except Exception as e:
            _mag_log(pol, {"phase": "watch", "error": str(e)})

    _maybe_summarize_ended_sessions()

    snapshot = sense()
    decision = judge(snapshot)
    # enforce attention daily cap before act
    if decision.get("action") == "attention":
        if _attention_over_cap(pol):
            decision = {
                "action": "idle",
                "reason": "attention daily cap reached",
                "goal": "",
                "attention_text": "",
            }

    result = act(decision, snapshot)
    # Tangents are opt-in only (CLI / dashboard Tangent / POST /api/v1/tangent).
    # Not wired into the lab cycle — proof-of-concept for later deliberate use.
    out = {
        "decision": decision,
        "result": {k: v for k, v in result.items() if k != "deliverable"},
        "assigned_n": len(snapshot.get("assigned") or []),
    }
    _mag_log(pol, {"phase": "cycle", **out})
    _write_status(decision, result)
    return out


def run_loop(interval: float | None = None, once: bool = False) -> None:
    pol = load_policy()
    sec = float(interval if interval is not None else pol.get("interval_seconds") or 120)
    print(f"Sovereign Mag running (interval={sec}s). Ctrl+C to stop.")
    print(f"  todo: {resolve(pol['todo_path'])}")
    print(f"  attention: {resolve(pol['attention_path'])}")
    print(f"  harness: use={pol.get('use_grok_harness')}")
    # Prefer integral watch thread so a separate `main.py watch` is not required
    if pol.get("integral_watch", True) and not once:
        try:
            from mag.runtime import start_watch_thread, write_heartbeat

            w = float(pol.get("watch_interval_seconds") or 5)
            start_watch_thread(w)
            write_heartbeat(status="mag_loop", mag_interval=sec, watch_interval=w)
            print(f"  integral watch thread every {w}s (do not also run main.py watch)")
        except Exception as e:
            print(f"  watch thread failed: {e} — cycle still calls watch_once")
    try:
        while True:
            print(f"\n--- mag cycle {datetime.now().isoformat(timespec='seconds')} ---")
            out = run_cycle()
            d = out.get("decision") or {}
            print(f"action={d.get('action')} reason={d.get('reason')}")
            r = out.get("result") or {}
            if r.get("path"):
                print(f"wrote {r['path']}")
            try:
                from mag.runtime import write_heartbeat

                write_heartbeat(
                    status="running",
                    last_action=d.get("action"),
                    last_reason=(d.get("reason") or "")[:200],
                )
            except Exception as _hb:
                # LOOP-DEATH GUARD (2026-09-25, t19 except-pass sweep): a heartbeat
                # writer that swallows its own death leaves the daemon looking alive
                # while every freshness consumer reads a stale beat. Non-fatal for the
                # cycle, but visible. (pattern: mag/ghost.py cost-enforcer guard)
                print(f"[daemon] HEARTBEAT LOOP DEATH GUARD: write_heartbeat exited: {_hb}", flush=True)
            if r.get("handoff_id"):
                print(f"handoff/harness id={r.get('handoff_id')} via={r.get('via')}")
            if r.get("graph_status"):
                print(f"graph_status={r.get('graph_status')}")
            if once:
                break
            time.sleep(sec)
    except KeyboardInterrupt:
        print("\nMag stopped.")


def _attention_over_cap(pol: dict) -> bool:
    count_path = ROOT / "watch" / "attention_count_day.txt"
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    max_a = int(pol.get("max_attention_per_day") or 8)
    if not count_path.is_file():
        return False
    try:
        d, c = count_path.read_text(encoding="utf-8").strip().split()
        return d == day and int(c) >= max_a
    except ValueError:
        return False


def _write_status(decision: dict, result: dict) -> None:
    path = ROOT / "state" / "MAG.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""# Mag status

- **updated:** {datetime.now(timezone.utc).isoformat()}
- **action:** {decision.get('action')}
- **reason:** {decision.get('reason')}
- **goal:** {decision.get('goal')}
- **result_ok:** {result.get('ok')}
- **detail:** {json.dumps({k: result.get(k) for k in ('action','graph_status','via','handoff_id','path','suppressed') if k in result}, default=str)}

See `memory/attention.md`, `memory/mag_journal.md`, `logs/mag.jsonl`.
""",
        encoding="utf-8",
    )
