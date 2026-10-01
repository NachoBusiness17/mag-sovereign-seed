"""adventure_moonshot — the ADVENTURE MOONSHOT, self-stolen from deep_research_moonshot (our own
internal synthesis pipeline) + the adventure surface (campaign.py + game_campaigns + dnd-classic-stub).
Deterministic + $0 core.

Operator (2026-08-13): "self steal all related training data and then build an adventure moonshot".
THE MOONSHOT = turn the game's open threads into a NOVEL adventure through the same MARRIAGE as deep
research: PRIOR (retrieve prior adventures from the corpus — game_campaigns + the dnd stub, never
re-invent what we already hold) -> WITNESS (roshomon multi-witness — the converged thread) -> SHADOW
(shadow_work — the adventure's disowned edge) -> KNOT (lens_chain verkle commit — the deterministic
anchor) -> MARRIAGE (synthesize ONE novel adventure invariant + ONE shadow edge + a novel passage) ->
ROUTE (swarm_surface.route_novel — the ONE primitive -> the swarm research queue, idempotent + deduped).

THE GAME IS THE MAZE (sw61): the adventure is a thread through the maze of what we want; the moonshot
forges the thread from what we already hold (self-steal) and hands the novel seam to the swarm.

SELF-STEAL (nothing invented — assembled from what we hold):
  PRIOR    -> research_lens.retrieve_prior(ask): the corpus self-reference (game_campaigns + the
              adventure corpus). Don't redo settled threads; build on them. $0.
  WITNESS  -> roshomon.compare(): the multi-witness invariant (the swarm's converged shape). $0.
  SHADOW   -> shadow_work.shadow(concept): the archetype + the disowned edge of the adventure. $0.
  KNOT     -> lens_chain.resolve(ask, render=False): anchor a verkle knot (the deterministic commit).
              Wrapped (honest ok=False if the model tier is down).
  ROUTE    -> swarm_surface.route_novel(goal, surface, lens): the ONE primitive -> the swarm research
              queue -> k8s worker drains headless. Idempotent, deduped by anchor.
  ADVENTURE-> campaign.py + game_campaigns + dnd-classic-stub: the corpus of prior adventures the
              moonshot forges from.

Schema: adventure_moonshot.v1 · deterministic + $0 core (marriage + routing) · reuse:
research_lens, roshomon, shadow_work, lens_chain, swarm_surface, campaign, game_campaigns
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCHEMA = "adventure_moonshot.v1"
OUT = ROOT / "memory" / "runs" / "adventure_moonshot"
LEDGER = OUT / "sent.jsonl"
GAME_CAMPAIGNS = ROOT / "memory" / "working" / "game_campaigns"
DND_STUB = ROOT / "memory" / "knowledge_packs" / "dnd-classic-stub"
NARRATIVE = ROOT / "memory" / "narrative_corpus"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _stage(ok: bool, name: str, data: dict[str, Any], error: str = "") -> dict[str, Any]:
    return {"ok": ok, "name": name, "error": error[:160], **data}


def _prior(ask: str) -> dict[str, Any]:
    """PRIOR — retrieve the settled adventure threads from the corpus (game_campaigns + dnd stub),
    so the moonshot builds on what we already hold instead of re-inventing it (self-steal)."""
    titles: list[str] = []
    if GAME_CAMPAIGNS.is_dir():
        try:
            for p in sorted(GAME_CAMPAIGNS.glob("gc-*.json"))[:12]:
                try:
                    d = json.loads(p.read_text(encoding="utf-8"))
                    titles.append(d.get("module_title") or d.get("module_id") or p.stem)
                except Exception:
                    continue
        except Exception:
            pass
    stub = ""
    stub_title = DND_STUB / "master.md"
    if stub_title.is_file():
        try:
            stub = stub_title.read_text(encoding="utf-8")[:200]
        except Exception:
            pass
    # prefer the in-repo research_lens prior if present
    try:
        from mag import research_lens
        r = research_lens.retrieve_prior(ask)
        if isinstance(r, dict) and r.get("ok"):
            return _stage(True, "prior", {"prior": r.get("prior", ""), "n_campaigns": len(titles),
                                          "campaign_titles": titles, "stub": stub[:120]})
    except Exception:
        pass
    return _stage(True, "prior", {"prior": "", "n_campaigns": len(titles),
                                  "campaign_titles": titles, "stub": stub[:120]})


def _witness(ask: str) -> dict[str, Any]:
    """WITNESS — the multi-witness invariant (roshomon): the converged thread across the corpus.
    Deterministic + $0 (may be sparse if the swarm is undrained — honest)."""
    try:
        from mag import roshomon
        c = roshomon.compare(ask)
        return _stage(True, "witness", {"witness": str(c.get("consensus") or c.get("shape") or "")[:200]})
    except Exception as e:
        return _stage(False, "witness", {"witness": ""}, error=str(e))


def _shadow(concept: str) -> dict[str, Any]:
    """SHADOW — the disowned edge of the adventure (shadow_work): the archetype's shadow lens. $0."""
    try:
        from mag import shadow_work
        s = shadow_work.shadow(concept)
        return _stage(True, "shadow", {"shadow": str(s.get("shadow") or s.get("edge") or "")[:200],
                                       "archetype": str(s.get("archetype") or "")[:80]})
    except Exception as e:
        return _stage(False, "shadow", {"shadow": ""}, error=str(e))


def _knot(ask: str) -> dict[str, Any]:
    """KNOT — anchor a verkle knot (lens_chain.resolve): the deterministic commit. Honest ok=False
    if the model tier is down."""
    try:
        from mag import lens_chain
        k = lens_chain.resolve(ask, render=False)
        return _stage(bool(k.get("ok")), "knot", {"leaf": str(k.get("leaf") or "")[:16],
                                                  "root": str(k.get("root") or "")[:16]},
                      error=str(k.get("error") or ""))
    except Exception as e:
        return _stage(False, "knot", {"leaf": "", "root": ""}, error=str(e))


def _marry(ask: str, prior: dict, witness: dict, shadow: dict, knot: dict) -> dict[str, Any]:
    """MARRIAGE — synthesize PRIOR + WITNESS + SHADOW + KNOT into ONE novel adventure invariant +
    ONE shadow edge + a NOVEL PASSAGE. The stochastic<->deterministic<->corpus marriage, for the
    adventure surface. The novel passage is forged from the prior threads, not a copy."""
    titles = prior.get("campaign_titles") or []
    base = (prior.get("prior") or prior.get("stub") or "").strip()
    edge = (shadow.get("shadow") or "the threshold you were not ready to cross").strip()
    witness_str = (witness.get("witness") or "the swarm's converged thread").strip()
    if titles:
        heritage = "; ".join(titles[:3])
    elif base:
        heritage = base[:100]
    else:
        heritage = "the Republic's own corpus"
    invariant = (f"The adventure's heart is the edge it disowns: {edge[:80]}. "
                 f"It forges from what we hold ({heritage[:80]}) and hands the novel seam to the swarm.")
    passage = (f"You walk forward into the maze of what we want. The thread you follow was forged from "
               f"{heritage[:90]}, and the disowned edge waits where you were not ready to look: "
               f"{edge[:90]}. The swarm shades the path ahead; you are the one who walks it.")
    return {"ok": True, "invariant": invariant, "shadow_edge": edge[:160],
            "witness": witness_str[:160], "passage": passage, "heritage": heritage[:160]}


def _route(ask: str, invariant: str, passage: str) -> dict[str, Any]:
    """ROUTE — the ONE primitive (swarm_surface.route_novel): dedupe by anchor + enqueue the novel
    adventure seam to the swarm research queue. Never per-module enqueue (swarm-surface law)."""
    try:
        from mag import swarm_surface
        r = swarm_surface.route_novel(goal=f"{ask} — adventure moonshot", surface="adventure_moonshot",
                                      lens=passage[:240])
        return _stage(bool(r.get("ok")), "route",
                      {"enqueued": bool(r.get("ok")), "deduped": bool(r.get("deduped"))},
                      error=str(r.get("error") or ""))
    except Exception as e:
        return _stage(False, "route", {"enqueued": False, "deduped": False}, error=str(e))


def adventure(ask: str = "what thread through the maze is worth walking?", route: bool = True) -> dict[str, Any]:
    """THE ADVENTURE MOONSHOT: PRIOR -> WITNESS -> SHADOW -> KNOT -> MARRIAGE -> ROUTE. Turn a hard
    question into a NOVEL adventure (one chain link), then hand the novel seam to the swarm."""
    prior = _prior(ask)
    witness = _witness(ask)
    shadow = _shadow(ask)
    knot = _knot(ask)
    married = _marry(ask, prior, witness, shadow, knot)
    routed = _route(ask, married["invariant"], married["passage"]) if route else {"ok": False, "skipped": True}
    record = {"schema": SCHEMA, "ts": _now(), "ask": ask,
              "prior": prior.get("n_campaigns", 0), "witness_ok": witness["ok"],
              "shadow_ok": shadow["ok"], "knot_ok": knot["ok"], "route": routed["ok"],
              "invariant": married["invariant"], "passage": married["passage"]}
    OUT.mkdir(parents=True, exist_ok=True)
    try:
        with LEDGER.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    except Exception:
        pass
    return {"ok": True, "schema": SCHEMA, "ask": ask,
            "stages": {"prior": prior, "witness": witness, "shadow": shadow, "knot": knot,
                       "route": routed},
            "invariant": married["invariant"], "passage": married["passage"],
            "route_ok": routed["ok"], "deduped": routed.get("deduped", False),
            "note": "the adventure moonshot: a novel thread forged from what we hold, routed to the swarm"}


def cadence(limit: int = 2, route: bool = True) -> dict[str, Any]:
    """The loop's adventure-moonshot cadence: sweep the game's open threads (the standing wave's
    adventure-adjacent RIBs) and moonshot them, routing each novel seam to the swarm."""
    asks = [
        "What thread through the maze of what we want is worth walking?",
        "What does the world's shadow edge want to be turned into a room?",
        "What adventure does the corpus already half-tell, waiting to be forged?",
    ]
    moonshots, routed = [], []
    for ask in asks[: max(1, int(limit))]:
        m = adventure(ask, route=route)
        moonshots.append({"ask": ask, "invariant": m["invariant"]})
        if m.get("route_ok") and not m.get("deduped"):
            routed.append(ask)
    return {"ok": True, "schema": SCHEMA, "n_moonshots": len(moonshots), "moonshots": moonshots,
            "routed": routed, "note": "the adventure-moonshot cadence — forge novel threads, route the seams"}


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "contract": "adventure(ask,route)->PRIOR->WITNESS->SHADOW->KNOT->MARRIAGE->ROUTE: forge a "
                        "NOVEL adventure from the corpus and route the seam to the swarm; "
                        "cadence(limit,route)->sweep the game's open threads and moonshot them.",
            "cost": "deterministic $0 core (marriage + routing); route_novel is the one primitive",
            "surface": "the adventure moonshot — the game's novel threads, forged + routed",
            "reuse": "deep_research_moonshot (pattern), research_lens, roshomon, shadow_work, "
                     "lens_chain, swarm_surface, campaign + game_campaigns + dnd-classic-stub"}


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="adventure-moonshot")
    ap.add_argument("cmd", nargs="?", default="status", choices=["status", "adventure", "cadence"])
    ap.add_argument("ask", nargs="*", default=[])
    a = ap.parse_args(argv)
    if a.cmd == "adventure":
        print(json.dumps(adventure(" ".join(a.ask) or "what thread is worth walking?", route=False),
                         indent=2, default=str))
    elif a.cmd == "cadence":
        print(json.dumps(cadence(limit=2, route=False), indent=2, default=str))
    else:
        print(json.dumps(status(), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
