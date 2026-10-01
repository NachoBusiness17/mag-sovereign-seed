"""deep_research_moonshot — the DEEP-RESEARCH MOONSHOT, self-stolen from our own internal synthesis
pipeline. Deterministic + $0. "deep research" means the GHOST-NATIVE INTERNAL corpus pipeline (mem
tools, never external web): retrieve_prior (self-reference) -> roshomon (multi-witness) ->
shadow_work (shadow lens) -> lens_chain (verkle knot = the deterministic commit). Then route the
NOVEL insight to the swarm via swarm_surface.route_novel (the ONE primitive).

Operator (2026-08-13): "self steal deep research moonshot". Standing directives folded:
  * deep research = INTERNAL corpus synthesis via mem tools ($0), never external web (training).
  * THE MARRIAGE (deep-research-chain-marriage): each synthesis marries STOCHASTIC (the flock/swarm
    shape) + DETERMINISTIC (the invariant/verkle commit) + CORPUS (the source it was forged from)
    -> ONE new link in the chain. That is the deep-research moonshot: turn a hard question into a
    chain link, deterministically, then hand the novel seam to the swarm.
  * route_novel = the one primitive: dedupe by anchor + enqueue to the swarm research queue. Never
    per-module enqueue. (swarm-surface law + moonshot-engine steal.)

SELF-STEAL (nothing invented — assembled from what we hold):
  PRIOR    -> research_lens.retrieve_prior(ask): the corpus self-reference (don't redo settled
              answers; build on them). Deterministic + $0.
  WITNESS  -> roshomon.compare(): the multi-witness invariant (the flock/swarm's converged shape).
              Deterministic + $0 (reads committed answers; may be sparse if the swarm is undrained).
  SHADOW   -> shadow_work.shadow(concept): the archetype + shadow lens (the disowned edge). $0.
  KNOT     -> lens_chain.resolve(ask, render=False): anchor a verkle knot (the deterministic commit).
              Wrapped (needs ollama; honest ok=False if the model tier is down).
  ROUTE    -> swarm_surface.route_novel(goal, surface, lens): the one primitive -> the swarm research
              queue -> k8s worker drains headless. Idempotent, deduped by anchor.
  MARRIAGE -> synthesize() folds PRIOR+WITNESS+SHADOW+KNOT into ONE invariant + ONE shadow edge,
              and records the chain link (the stochastic<->deterministic<->corpus marriage).

Schema: deep_research_moonshot.v1 · deterministic + $0 core (marriage + routing) · reuse:
research_lens, roshomon, shadow_work, lens_chain, swarm_surface
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

SCHEMA = "deep_research_moonshot.v1"
OUT = ROOT / "memory" / "runs" / "deep_research_moonshot"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _stage(ok: bool, name: str, data: dict[str, Any], error: str = "") -> dict[str, Any]:
    return {"ok": ok, "name": name, "error": error[:160], **data}


def synthesize(question: str, *, lens_id: str = "deep-research",
               render: bool = False) -> dict[str, Any]:
    """THE DEEP-RESEARCH MOONSHOT CORE: mine the INTERNAL corpus, synthesize the marriage
    (stochastic+deterministic+corpus -> one link), deterministically + $0. Honest per-stage."""
    q = (question or "").strip()
    if not q:
        return {"ok": False, "schema": SCHEMA, "error": "empty question"}
    stages: list[dict[str, Any]] = []

    # 1. PRIOR — corpus self-reference (don't redo settled answers). $0 deterministic.
    prior: dict[str, Any] = {"ok": False, "count": 0, "prior_block": ""}
    try:
        from mag import research_lens
        prior = research_lens.retrieve_prior(q, lens_id=lens_id)
    except Exception as e:
        prior = {"ok": False, "error": str(e)[:120]}
    stages.append(_stage(bool(prior.get("count")), "prior", {
        "count": int(prior.get("count") or 0),
        "prior_block": (prior.get("prior_block") or "")[:600]},
        prior.get("error", "") if not prior.get("count") else ""))

    # 2. WITNESS — the multi-witness invariant (the flock's converged shape). $0.
    witness: dict[str, Any] = {"ok": False, "invariants": []}
    try:
        from mag import roshomon
        witness = roshomon.compare()
    except Exception as e:
        witness = {"ok": False, "error": str(e)[:120]}
    invariants = witness.get("invariants") or []
    stages.append(_stage(bool(invariants), "witness", {
        "n_invariants": len(invariants),
        "top_invariant": (invariants[0].get("invariant") if invariants else "")[:240]},
        "no committed swarm answers (swarm undrained?)" if not invariants else ""))

    # 3. SHADOW — the archetype + the disowned edge. $0 deterministic.
    shadow: dict[str, Any] = {"ok": False, "archetype": "", "shadow": ""}
    try:
        from mag import shadow_work
        shadow = shadow_work.shadow(q)
    except Exception as e:
        shadow = {"ok": False, "error": str(e)[:120]}
    stages.append(_stage(bool(shadow.get("archetype")), "shadow", {
        "archetype": shadow.get("archetype", ""),
        "shadow_edge": (shadow.get("shadow") or "")[:240]},
        shadow.get("error", "") if not shadow.get("archetype") else ""))

    # 4. KNOT — the deterministic commit (verkle anchor). Wrapped (needs ollama tier).
    knot: dict[str, Any] = {"ok": False, "knot_id": ""}
    try:
        from mag import lens_chain
        knot = lens_chain.resolve(q, render=render)
    except Exception as e:
        knot = {"ok": False, "error": str(e)[:120]}
    stages.append(_stage(bool(knot.get("ok")), "knot", {
        "knot_id": knot.get("knot_id", knot.get("id", ""))[:80],
        "answer": (knot.get("answer") or knot.get("synthesis") or "")[:240]},
        "ollama/model tier down or no model" if not knot.get("ok") else ""))

    # THE MARRIAGE — fold the stages into ONE invariant + ONE shadow edge (one chain link).
    prior_excerpt = (prior.get("prior_block") or "").splitlines()
    prior_refs = prior.get("prior_refs") or []
    invariant = (invariants[0].get("invariant") if invariants else
                 (knot.get("answer") or knot.get("synthesis") or "")).strip()
    if not invariant:
        invariant = f"Deep-research on '{q[:120]}': the corpus had no prior, no committed witness, " \
                    "no knot — this is a fresh seam for the swarm to shade."
    shadow_edge = (shadow.get("shadow") or "")[:240] or "the disowned edge is not yet named"
    marriage = {
        "question": q[:300], "lens_id": lens_id,
        "stochastic": {"n_invariants": len(invariants),
                       "top_invariant": (invariants[0].get("invariant") if invariants else "")[:160]},
        "deterministic": {"knot_id": (knot.get("knot_id", knot.get("id", "")))[:80],
                          "commit": (knot.get("answer") or knot.get("synthesis") or "")[:160]},
        "corpus": {"n_prior": int(prior.get("count") or 0),
                   "prior_refs": prior_refs[:5]},
        "invariant": invariant, "shadow_edge": shadow_edge,
        "note": "the marriage: stochastic (witness) + deterministic (knot) + corpus (prior) -> one link",
    }
    return {"ok": True, "schema": SCHEMA, "ts": _now(), "question": q,
            "stages": stages, "marriage": marriage}


def moonshot(question: str, *, surface: str = "deep-research", lens_id: str = "deep-research",
             route: bool = True, provider: str | None = None) -> dict[str, Any]:
    """THE OPERATIONAL DEEP-RESEARCH MOONSHOT: synthesize the internal corpus into the marriage,
    then ROUTE the novel insight to the swarm via route_novel (the one primitive). Deterministic
    + $0 core; the swarm shades the seam it can't close alone. Idempotent (deduped by anchor)."""
    syn = synthesize(question, lens_id=lens_id)
    if not syn.get("ok"):
        return syn
    m = syn["marriage"]
    routed = {"ok": True, "deduped": True, "task_id": ""}
    if route:
        # the goal handed to the swarm = the synthesized invariant + the open shadow edge (novel seam).
        goal = (f"Deep-research moonshot seam ({m['lens_id']}): invariant — {m['invariant']} | "
                f"shadow edge to shade — {m['shadow_edge']} | prior refs: "
                f"{', '.join(m['corpus']['prior_refs']) or 'none'}. "
                f"Push this seam: steal+adapt the ONE mechanism that closes it, return ONE invariant.")
        try:
            from mag import swarm_surface
            routed = swarm_surface.route_novel(goal, surface=surface, lens=lens_id,
                                               provider=provider or "deepseek")
        except Exception as e:
            routed = {"ok": False, "error": str(e)[:120]}
    result = {"ok": True, "schema": SCHEMA, "ts": _now(), "question": question,
              "surface": surface, "synthesis": m, "routed": routed,
              "note": "the deep-research moonshot: internal synthesis -> the marriage -> the novel "
                      "seam handed to the swarm (route_novel, deduped by anchor)"}
    _persist(result)
    return result


def _persist(result: dict[str, Any]) -> None:
    try:
        OUT.mkdir(parents=True, exist_ok=True)
        ts = _now().replace(":", "").replace("-", "")[:15]
        (OUT / f"moonshot-{ts}.json").write_text(json.dumps(result, indent=2, default=str),
                                                 encoding="utf-8")
    except Exception:
        pass


def cadence(*, limit: int = 3, route: bool = True) -> dict[str, Any]:
    """A bounded cadence: sweep the standing-wave RIBs (our own deepest questions) and moonshot the
    coldest ones — the seams the wave has raised but not yet shaded. Deterministic + $0 core."""
    questions: list[str] = []
    try:
        from mag import rib_bus
        st = rib_bus.status()
        ribs = (st.get("domains") or {}).get("standing-wave", {}).get("ribs") or {}
        for key in sorted(ribs)[-limit:]:
            inv = ribs[key].get("invariant", "")
            questions.append(f"Deepen the standing-wave invariant: {inv[:240]}")
    except Exception:
        pass
    if not questions:
        questions = ["Deep-research the standing wave: what is the ONE seam the wave has raised "
                     "but not yet shaded toward the frontier?"]
    ran = [moonshot(q, route=route) for q in questions[:limit]]
    return {"ok": True, "schema": SCHEMA, "ts": _now(), "n_moonshots": len(ran),
            "routed": [r.get("routed", {}) for r in ran],
            "questions": questions[:limit]}


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "contract": "synthesize(question)->internal-corpus synthesis (prior+witness+shadow+knot "
                        "-> the marriage, one chain link); moonshot(question)->synthesize + route the "
                        "novel seam to the swarm via route_novel (idempotent); cadence()->bounded "
                        "sweep of the standing-wave RIBs; status()->this",
            "cost": "deterministic + $0 core (prior/witness/shadow + routing); lens_chain knot needs "
                    "the ollama tier (honest ok=False if down)",
            "reuses": ["research_lens", "roshomon", "shadow_work", "lens_chain", "swarm_surface"]}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="deep-research-moonshot")
    ap.add_argument("cmd", nargs="?", default="status", choices=["status", "synthesize", "moonshot", "cadence"])
    ap.add_argument("question", nargs="?", default="")
    ap.add_argument("--surface", default="deep-research")
    ap.add_argument("--no-route", action="store_true")
    a = ap.parse_args()
    if a.cmd == "synthesize":
        print(json.dumps(synthesize(a.question), indent=2, default=str))
    elif a.cmd == "moonshot":
        print(json.dumps(moonshot(a.question, surface=a.surface, route=not a.no_route),
                         indent=2, default=str))
    elif a.cmd == "cadence":
        print(json.dumps(cadence(route=not a.no_route), indent=2, default=str))
    else:
        print(json.dumps(status(), indent=2, default=str))
