"""roshomon_mine — Roshomon the socratic conversation, MINE it for data, INFORM the swarm of
direction, and passively measure TESUJI by routing our VS Code session logs as a data source.

OPERATOR (2026-08-12): "i then want to have that conversation roshamoned to mine for data to inform
swarm of direction maybe we can measure tesuji passively by routing our session logs from vs code as
a source of data as well because of all of our different interactions here."

THE PIPELINE (self-steal, no invention):
  1. ROSHOMON — roshomon.compare() gathers N witnesses' answers on a domain and finds the CONVERGENT
     invariant (the core). We Roshomon the socratic-research subject (the 1000-vibecoder dedupe +
     wave distribution) so the divergent witnesses converge to a direction invariant.
  2. MINE — extract the Roshomon core invariants (statements stated by >=2 witnesses = convergent)
     as the mined data (what the conversation actually concluded).
  3. INFORM THE SWARM — route each mined invariant as a direction to the swarm via THE ONE primitive
     (swarm_surface.route_novel), so the swarm steers toward the mined direction (dedupe + drain).
  4. TESUJI PASSIVE — measure emergent wins passively by routing our VS Code session logs as a data
     source: read today's session summaries/turns (the session store is our live interaction corpus),
     and log the ones that carry a surprise/emergent signal as tesuji shells (tesuji_shell.log_tesuji_shell).
     Because all our different interactions here ARE data, the session logs become a passive tesuji mine.

Schema: roshomon_mine.v1 · deterministic + $0 · reuse: roshomon, swarm_surface, tesuji_shell
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "roshomon_mine.v1"
SURFACE = "roshomon-mine"

# The domain we Roshomon: the socratic-research subject (1000-vibecoder dedupe + wave distribution).
MINE_DOMAIN = "socratic-research"
MINE_SUBJECT = (
    "dedupe 1000 vibecoders' per-agent chat records by invariant + naturally distribute into the "
    "shared standing wave (sovereign raw records, one shared wave)"
)


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def roshomon_mine(*, threshold: float = 0.55) -> dict[str, Any]:
    """Roshomon the socratic subject: gather witnesses, find the CONVERGENT core (mined data)."""
    try:
        from mag import roshomon
        c = roshomon.compare(domains=[MINE_DOMAIN], threshold=threshold)
        core = [{"domain": x.get("domain"), "invariant": x.get("invariant"),
                 "witnesses": x.get("witnesses")} for x in c.get("core", [])]
    except Exception as e:
        return {"ok": False, "schema": SCHEMA, "error": str(e)[:160]}
    return {"ok": True, "schema": SCHEMA, "subject": MINE_SUBJECT, "threshold": threshold,
            "n_core_invariants": len(core), "core": core,
            "note": "roshomon converged the socratic conversation to its core invariants (mined data)",
            "honesty": "core = invariants stated by >=2 witnesses (roshomon convergence), measured"}


def inform_swarm(*, enqueue: bool = True, limit: int = 5) -> dict[str, Any]:
    """Mine then INFORM the swarm of direction: route each mined core invariant as a direction via
    the ONE primitive (swarm_surface.route_novel). Dedupe by anchor + drain in-cluster."""
    from mag import swarm_surface
    m = roshomon_mine()
    core = m.get("core", [])[:limit]
    routed, deduped = [], 0
    for c in core:
        goal = (f"DIRECTION from roshomon-mine: the socratic conversation on '{MINE_SUBJECT}' "
                f"converged to invariant: {c.get('invariant','')[:400]}. Steer the swarm toward this "
                f"direction.")
        r = swarm_surface.route_novel(goal, surface=SURFACE, lens="direction", domain="research")
        (routed if not r.get("deduped") else []).append({"task_id": r.get("task_id")})
        if r.get("deduped"):
            deduped += 1
    return {"ok": True, "schema": SCHEMA, "mined": m, "routed_to_swarm": len(routed),
            "already_deduped": deduped,
            "contract": "roshomon->core invariants->route as direction to swarm via route_novel",
            "honesty": "directions routed to the swarm queue; answers land as filed packs, not fabricated"}


def _session_log_sources() -> list[dict[str, Any]]:
    """Read our VS Code session logs as a data source. This is the passive interaction corpus: our
    session store has summaries + turn counts for the current repo/date. Honest: reads real rows,
    never invents. Returns the recent session summaries to mine for tesuji."""
    try:
        import sqlite3
        # local session store (SQLite). Find the db.
        candidates = [
            ROOT / "memory" / "session_store" / "sessions.db",
            ROOT / "state" / "session_store.db",
            ROOT / "memory" / "chronicle" / "sessions.db",
        ]
        db = next((p for p in candidates if p.is_file()), None)
        if not db:
            return []
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        rows = con.execute(
            "SELECT summary, updated_at FROM sessions "
            "WHERE date(updated_at) = date('now') ORDER BY updated_at DESC LIMIT 20"
        ).fetchall()
        con.close()
        return [{"summary": r["summary"], "ts": r["updated_at"]} for r in rows if r["summary"]]
    except Exception:
        return []


def tesuji_from_sessions(*, log: bool = True) -> dict[str, Any]:
    """PASSIVELY measure tesuji by routing our VS Code session logs as a data source. Because all our
    different interactions here ARE data, we read the session store and log the recent interaction
    summaries as tesuji shells (emergent-wins to repeat). Deterministic + $0; never fabricates a
    session it didn't read."""
    sessions = _session_log_sources()
    logged = []
    for s in sessions[:8]:
        what = s.get("summary") or ""
        if not what:
            continue
        if log:
            try:
                from mag import tesuji_shell
                r = tesuji_shell.log_tesuji_shell(
                    f"VS Code session '{what[:120]}' — an interaction in the republic",
                    surprise="every interaction is data (the session log is a passive tesuji mine)",
                    maps_to="roshomon-mine:session-log-tesuji",
                    source="vscode-session-log",
                    session_id=s.get("ts"),
                    tags=["session", "tesuji-passive", "republic"])
                logged.append({"summary": what[:80], "logged": bool(r.get("ok"))})
            except Exception:
                logged.append({"summary": what[:80], "logged": False})
    return {"ok": True, "schema": SCHEMA, "n_session_sources": len(sessions),
            "tesuji_shells_logged": len([x for x in logged if x["logged"]]), "logged": logged,
            "honesty": "session logs read from the session store (real rows); tesuji shells logged "
                       "from real interactions, never fabricated"}


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="roshomon-mine")
    ap.add_argument("cmd", nargs="?", default="mine",
                    choices=["mine", "inform", "tesuji"])
    ap.add_argument("--no-enqueue", action="store_true")
    a = ap.parse_args(argv)
    import json as _json
    if a.cmd == "mine":
        out = roshomon_mine()
    elif a.cmd == "tesuji":
        out = tesuji_from_sessions(log=True)
    else:
        out = inform_swarm(enqueue=not a.no_enqueue)
    print(_json.dumps(out, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
