"""game_saga — the BOATMURDERED running gag, made literal (the world's memory of named absurdity).

Boatmurdered law (RIB 9): specific, named, escalating misfortunes + recurring characters + a world
that recounts what happened while you were gone. This module persists a campaign's SAGA (named
events/characters) in the server-authoritative world (game_world verkle), and recalls it so the
creative DM weaves the running gag into every turn. You forget; the world remembers; the gag lands.

Schema: game_saga.v1 · reuse: mag.game_world (the authority), mag.game_dm_llm (the narrator)
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from typing import Any

try:
    from config import ROOT
except Exception:
    from pathlib import Path as _P
    ROOT = _P(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SCHEMA = "game_saga.v1"
MAX_ENTRIES = 12  # keep the saga tight; the best bits, not a log


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _world() -> Any:
    from mag import game_world
    return game_world


def _key(campaign_id: str) -> str:
    return f"game.saga.{campaign_id}"


def recall(campaign_id: str) -> dict[str, Any]:
    """The saga so far — 'what happened while you were gone.' Named, recurring, escalating."""
    gw = _world()
    try:
        r = gw.get_state(_key(campaign_id))
        entries = (r.get("value") or []) if isinstance(r, dict) else []
    except Exception:
        entries = []
    if not entries:
        return {"ok": True, "schema": SCHEMA, "campaign_id": campaign_id, "saga": [],
                "text": "The world is quiet. Nothing has happened here yet — or nothing remembers it."}
    text = "\n".join(f"- {e.get('name', '?')}: {e.get('event', '')}" for e in entries)
    return {"ok": True, "schema": SCHEMA, "campaign_id": campaign_id, "saga": entries,
            "text": text, "note": "the saga the world recounts while you were gone (Boatmurdered)"}


def add(campaign_id: str, name: str, event: str) -> dict[str, Any]:
    """Record a named saga beat (a recurring character / specific absurdity). Keeps the best bits."""
    gw = _world()
    try:
        r = gw.get_state(_key(campaign_id))
        entries = list((r.get("value") or []) if isinstance(r, dict) else [])
    except Exception:
        entries = []
    entries.append({"name": str(name)[:40], "event": str(event)[:200], "ts": _now()})
    # collapse repeats of the SAME name into a running-gag escalation (the elephant returns, angrier)
    counts: dict[str, int] = {}
    kept: list[dict[str, Any]] = []
    for e in entries:
        counts[e["name"]] = counts.get(e["name"], 0) + 1
    # keep most recent; if a name recurs >1, mark it a running gag
    for e in entries[-MAX_ENTRIES:]:
        e2 = dict(e)
        if counts.get(e["name"], 0) > 1:
            e2["running_gag"] = True
            e2["count"] = counts[e["name"]]
        kept.append(e2)
    try:
        gw.set_state(_key(campaign_id), kept, source="game_saga")
    except Exception:
        pass
    return {"ok": True, "schema": SCHEMA, "campaign_id": campaign_id, "name": name,
            "running_gag": counts.get(name, 0) > 1, "entries": len(kept)}


def running_gags(campaign_id: str) -> list[dict[str, Any]]:
    """The named things that keep coming back (the elephant, the barkeep, Calcifer)."""
    r = recall(campaign_id)
    return [e for e in (r.get("saga") or []) if e.get("running_gag")]


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "note": "the world's memory of named absurdity (Boatmurdered running gag); "
                    "add(name,event) records, recall() recounts, running_gags() lists the recurring"}


if __name__ == "__main__":
    import argparse
    import json

    ap = argparse.ArgumentParser(prog="game-saga")
    ap.add_argument("cmd", choices=["recall", "add", "gags"], default="recall", nargs="?")
    ap.add_argument("--campaign", default="demo")
    ap.add_argument("--name", default="")
    ap.add_argument("--event", default="")
    a = ap.parse_args()
    if a.cmd == "add":
        out = add(a.campaign, a.name or "the elephant", a.event or "trampled the tavern again")
    elif a.cmd == "gags":
        out = {"ok": True, "gags": running_gags(a.campaign)}
    else:
        out = recall(a.campaign)
    print(json.dumps(out, indent=2, default=str))
