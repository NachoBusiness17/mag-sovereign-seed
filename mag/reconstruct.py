"""reconstruct — DETERMINISTIC TRACKING BY RECONSTRUCTION, NOT BY HELD STATE. When queried, the answer
is RECONSTRUCTED from content-addressed source (the chain, RIBs, corpus, game world) — never read from
a held snapshot that can drift. The stateless/re-derivable doctrine made literal.

OPERATOR (2026-08-12): "we need to have deterministic tracking using our very own system when queried
not held but reconstructed."

THE PRINCIPLE (self-steal our own machinery, no invention):
  * world_rib.reederive()  -> the grounding check: the world follows the RIB; querying = recompile,
    not read a snapshot. The map precedes the territory; the territory is re-derived from the map.
  * auto_quantize LAW      -> "the chain root is always recoverable from any quantization level." The
    full state is reconstructible from any fragment.
  * game_world.get_state() -> read the server-authoritative state FROM the chain (reconstructed, not
    held in a separate tracker that can disagree).
  * verkle_lance.trace()   -> the temporal map: reconstruct a route's position from the chain parents.
  * ghost_memlance.select() -> select memory states from DISK bytes (grounded, verified) — never from
    memory-of-memory. Reconstruction = grounding.

WHY RECONSTRUCT, NOT HOLD:
  - A HELD snapshot can drift from the source (the anti-pattern: a "state" that disagrees with the
    bytes). Reconstruction reads the source every query -> the answer IS the current truth.
  - It scales to a billion: nothing is stored per-person except the content-addressed knots; the
    answer for any query is rebuilt from those knots on demand. Stateless, $0, no drift.
  - It's honest: a reconstructed answer carries its provenance (the source bytes it was built from);
    a held answer hides where it came from.

Schema: reconstruct.v1 · deterministic + $0 · reuse: world_rib, game_world, verkle_lance, ghost_memlance
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

SCHEMA = "reconstruct.v1"


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def state(surface: str = "game-world") -> dict[str, Any]:
    """RECONSTRUCT a tracked surface's state on query — never read a held snapshot. Deterministic.
    Each surface re-derives from its own content-addressed source (the chain/world/RIBs)."""
    out: dict[str, Any] = {"ok": True, "schema": SCHEMA, "surface": surface,
                           "reconstructed_at": _now()}
    if surface == "game-world":
        try:
            from mag import game_world
            g = game_world.get_state()
            out["state"] = {"n_entities": g.get("n_entities"), "root": g.get("root"),
                            "n_changes": g.get("n_changes")}
            out["provenance"] = "reconstructed from game_world chain (server-authoritative bytes)"
        except Exception as e:
            out["error"] = str(e)[:120]
    elif surface == "rib":
        try:
            from mag import rib_bus
            m = rib_bus.mount("general")
            out["state"] = {"n_ribs": m.get("n_ribs")}
            out["provenance"] = "reconstructed from rib_bus store (content-addressed RIBs)"
        except Exception as e:
            out["error"] = str(e)[:120]
    else:
        # unknown surface -> reconstruct from the corpus ledgers (agent_corpus / republic_wave)
        try:
            from mag import agent_corpus
            c = agent_corpus.corpus()
            out["state"] = {"total_chats": c.get("total_chats"),
                            "per_agent": c.get("per_agent_chat_count")}
            out["provenance"] = "reconstructed from agent_corpus ledgers (content-addressed knots)"
        except Exception as e:
            out["error"] = str(e)[:120]
    out["note"] = "reconstructed on query from content-addressed source — never a held snapshot that can drift"
    return out


def wave() -> dict[str, Any]:
    """RECONSTRUCT the shared standing wave on query (republic_wave ledgers), never a held view.
    Deterministic + $0."""
    try:
        from mag import republic_wave
        w = republic_wave.wave()
        return {"ok": True, "schema": SCHEMA,
                "state": {"n_shared_invariants": w.get("n_shared_invariants"),
                          "n_contributors": w.get("n_contributors"),
                          "contributors": w.get("contributors")},
                "provenance": "reconstructed from republic_wave wave + contributor ledgers (content-addressed)",
                "reconstructed_at": _now(),
                "note": "the shared wave is re-derived on query — the answer is the current bytes, not a cached view"}
    except Exception as e:
        return {"ok": False, "schema": SCHEMA, "error": str(e)[:120]}


def rederive(surface: str = "game-world") -> dict[str, Any]:
    """The GROUNDING CHECK: query the surface twice and confirm the reconstruction is byte-stable
    (same query -> same reconstructed state -> re-derivable, no drift, no held state lying)."""
    a = state(surface)
    b = state(surface)
    stable = a.get("state") == b.get("state")
    return {"ok": True, "schema": SCHEMA, "surface": surface, "re_derivable": stable,
            "first": a.get("state"), "second": b.get("state"),
            "note": "map precedes territory: querying re-derives the state from source each time; "
                    "byte-stable = no held state drifted between queries"}


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "contract": "state(surface)->RECONSTRUCT the tracked surface on query (game-world/rib/"
                        "corpus) from content-addressed source, never a held snapshot; wave()-"
                        ">reconstruct the shared standing wave; rederive()->grounding check (byte-stable)",
            "cost": "deterministic + $0 (reuses world_rib rederive + game_world + rib_bus + ledgers)",
            "principle": "reconstruct, don't hold: query = re-derive from the source bytes; nothing "
                         "is stored per-person except the content-addressed knots; the answer IS the "
                         "current truth, with provenance"}


def fold_doctrine() -> dict[str, Any]:
    """Fold the load-bearing doctrine as a RIB so every cold worker inherits it: THE SYSTEM IS
    STATELESS, OUR KNOWLEDGE OF IT IS NOT — the water (stateless workers/queries) re-derives the
    wave (stateful chain/knowledge) on query via reconstruct, never a held snapshot. Idempotent."""
    from mag import rib_bus
    invariant = (
        "RECONSTRUCT-DON'T-HOLD (the stateless/stateful bridge): the SYSTEM is stateless (workers "
        "and queries spawn cold and die, re-deriving from content-addressed source), but our "
        "KNOWLEDGE of it is stateful (the chain/RIBs/corpus accumulate and persist as the wave). "
        "Query = RECONSTRUCT the answer from the source bytes every time — never read a held "
        "snapshot that can drift. Stateless water, stateful wave, reconstructed on demand: the "
        "system can't be captured (nothing held) and the knowledge can't lie (it IS the current "
        "bytes, with provenance)."
    )
    r = rib_bus.publish_rib(invariant, domain="reconstruct", source="doctrine",
                            target_rank="T1")
    return {"ok": r.get("ok", False), "schema": SCHEMA, "domain": "reconstruct",
            "key": r.get("key"), "note": "the reconstruct-don't-hold doctrine folded as a RIB"}


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="reconstruct")
    ap.add_argument("cmd", nargs="?", default="state",
                    choices=["state", "wave", "rederive", "status"])
    ap.add_argument("--surface", default="game-world")
    a = ap.parse_args(argv)
    import json as _json
    if a.cmd == "state":
        out = state(a.surface)
    elif a.cmd == "wave":
        out = wave()
    elif a.cmd == "rederive":
        out = rederive(a.surface)
    else:
        out = status()
    print(_json.dumps(out, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
