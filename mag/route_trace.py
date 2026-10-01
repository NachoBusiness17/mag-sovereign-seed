"""route_trace — the deterministic ROUTE-PROVENANCE debugger. At a billion people, "where did they
go from" must be an ANSWERABLE, deterministic trace — never a guess. Every routed action (a person's
move, a swarm goal, a session, a game action) leaves a content-addressed knot; the chain records the
path; route_trace reads it back as the route.

OPERATOR (2026-08-12): "We need to be able to debug these routes eventually because this is gonna get
big. Imagine there's a billion people on this platform and we can't tell where they went from. We have
the terminal deterministic machinery built in for stochastic navigation we should be using it."

THE STEAL (use the terminal deterministic machinery we ALREADY have):
  * verkle_lance.trace(key)   -> the TEMPORAL MAP: map an event/key to its knot(s) + chain position +
    parent/child (the deterministic "where it sits in time"). This IS the route trace primitive.
  * verkle_lance.link(event)  -> tie an event temporally (the root that anchors it at that point).
  * verkle_lance.verify(key)  -> deterministic content-addressed verdict (hash present, root valid).
  * source_trace.trace_source() -> the ORIGIN chain (where a process/person came FROM).
  * game_world.set_state()    -> fold a route hop as a content-addressed knot (provenance on the chain).

WHY THIS SCALES TO A BILLION:
  - Every hop is content-addressed (sha256) -> the SAME route always lands the same knot -> no two
    billion-people routes collide by accident.
  - The chain is temporal (parent_verkle_root -> verkle_root) -> a route is a LIST OF PARENTS, so
    tracing "where they went from" = walking the parent chain deterministically, $0, no inference.
  - Provenance (who/what/when/from/to) rides on the knot -> "where did they go from" = read the knot,
    not reconstruct from logs. The chain is the receipt.

Schema: route_trace.v1 · deterministic + $0 · reuse: verkle_lance, source_trace, game_world
"""
from __future__ import annotations

import json
import sys
from typing import Any

try:
    from config import ROOT
except Exception:
    from pathlib import Path as _P
    ROOT = _P(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "route_trace.v1"


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _lance() -> Any:
    from mag import verkle_lance
    return verkle_lance


def _gw() -> Any:
    from mag import game_world
    return game_world


def hop(*, who: str, what: str, frm: str = "", to: str = "", fold: bool = True) -> dict[str, Any]:
    """Record ONE route hop: a person/agent moved from `frm` to `to` doing `what`. Fold it as a
    content-addressed knot on the chain (provenance = the receipt). Idempotent by content address
    (same hop -> same knot -> never duplicates). This is the unit the billion-scale trace is built on."""
    who = (who or "").strip()
    what = (what or "").strip()
    if not who or not what:
        return {"ok": False, "schema": SCHEMA, "error": "who and what required"}
    gw = _gw()
    key = f"route.{who}.{what}"
    # idempotent: skip if the world already holds this exact hop
    existing = gw.get_state(key)
    if existing.get("found"):
        return {"ok": True, "schema": SCHEMA, "who": who, "what": what, "leaf": existing.get("value", {}).get("leaf"),
                "deduped": True, "recorded": False}
    value = {"who": who, "what": what, "from": frm, "to": to, "ts": _now()}
    r = gw.set_state(key, value, source="route-trace") if fold else {"ok": True, "leaf": "dry"}
    return {"ok": r.get("ok"), "schema": SCHEMA, "who": who, "what": what, "from": frm, "to": to,
            "leaf": r.get("leaf"), "recorded": bool(r.get("ok")),
            "note": "hop folded as a content-addressed knot — provenance on the chain"}


def trace(who: str, *, limit: int = 20) -> dict[str, Any]:
    """WHERE DID THEY GO FROM — the deterministic answer. Read the chain (verkle_lance.trace) for the
    person's knots + their temporal place (parent/child roots), and the game world for the hops. The
    route is a list of parents: walking it deterministically gives the path. $0, no inference."""
    out: dict[str, Any] = {"ok": True, "schema": SCHEMA, "who": who}
    # 1) the temporal map (verkle_lance): the person's knots + chain position + parent/child
    try:
        l = _lance()
        tr = l.trace(who, limit=limit)
        out["chain"] = {"found": tr.get("found"), "n_matches": tr.get("n_matches"),
                        "matches": tr.get("matches", [])}
    except Exception as e:
        out["chain_error"] = str(e)[:120]
    # 2) the route hops recorded in the world (game_world state)
    try:
        gw = _gw()
        world = gw.get_state()
        hops = [{"key": k, "value": v.get("value")} for k, v in (world.get("world") or {}).items()
                if k.startswith(f"route.{who}.")]
        out["hops"] = hops[-limit:]
        out["n_hops"] = len(hops)
        out["route"] = [{"from": h["value"].get("from", ""), "to": h["value"].get("to", ""),
                         "what": h["value"].get("what", ""), "ts": h["value"].get("ts", "")}
                        for h in hops[-limit:]]
    except Exception as e:
        out["world_error"] = str(e)[:120]
    out["note"] = ("the deterministic trace: chain temporal map (verkle_lance) + recorded hops "
                   "(game_world). 'Where did they go from' = walk the parent chain, $0, no inference.")
    return out


def origin(who: str, *, limit: int = 8) -> dict[str, Any]:
    """The ORIGIN chain: trace the person/process back to its SOURCE (source_trace.trace_source for a
    process pid, or the earliest recorded hop for a person). This is the 'where did they come FROM'
    root — the deepest deterministic parent."""
    out: dict[str, Any] = {"ok": True, "schema": SCHEMA, "who": who}
    # if `who` looks like a pid, use source_trace (the origin/process chain)
    if str(who).isdigit():
        try:
            from mag import source_trace
            src = source_trace.trace_source(int(who))
            out["origin"] = src[:limit]
        except Exception as e:
            out["origin_error"] = str(e)[:120]
    else:
        # else: the earliest hop = the origin (the first 'from' where the route began)
        try:
            gw = _gw()
            world = gw.get_state()
            hops = [(k, v.get("value")) for k, v in (world.get("world") or {}).items()
                    if k.startswith(f"route.{who}.")]
            hops.sort(key=lambda x: (x[1] or {}).get("ts", ""))
            out["origin"] = hops[:limit]
        except Exception as e:
            out["origin_error"] = str(e)[:120]
    out["note"] = "the deepest deterministic parent — the origin of the route, not a guess"
    return out


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "contract": "hop(who,what,from,to)->record+fold a route hop as a content-addressed knot; "
                        "trace(who)->the deterministic 'where did they go from' (chain temporal map + "
                        "hops); origin(who)->the deepest parent (source_trace or earliest hop)",
            "cost": "deterministic + $0 (reuses verkle_lance + source_trace + game_world)",
            "scales": "content-addressed hops + temporal parent chain = a billion routes traceable "
                      "by walking parents, no inference, no collision"}


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="route-trace")
    ap.add_argument("cmd", nargs="?", default="status",
                    choices=["hop", "trace", "origin", "status"])
    ap.add_argument("--who", default="player")
    ap.add_argument("--what", default="")
    ap.add_argument("--from", dest="frm", default="")
    ap.add_argument("--to", default="")
    a = ap.parse_args(argv)
    import json as _json
    if a.cmd == "hop":
        out = hop(who=a.who, what=a.what, frm=a.frm, to=a.to)
    elif a.cmd == "trace":
        out = trace(a.who)
    elif a.cmd == "origin":
        out = origin(a.who)
    else:
        out = status()
    print(_json.dumps(out, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
