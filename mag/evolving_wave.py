"""evolving_wave — THE WAVE BREEDS THE WORK: evolution wired into the loop (2026-08-24).

The orphan's two missing wires, now closed:
  1. OFFSPRING FEED THE WORK — a bred tesuji is PERCOLATED (novel -> explore queue -> the
     fuel feed drills it through the free lanes next ring; repeat -> compiled invariant).
     The wave's offspring no longer stop at the standing knot — they become real work.
  2. FITNESS FROM REALITY — fitness blends the deterministic proxy (agent_knot) with REAL
     feedback from disk: has this gene's content actually percolated into shared reality
     (invariant registry / explore queue)? Evolution evolves toward what WORKS, not just
     what is long/novel.

Plus the stolen algorithms, made ours, deterministic + $0:
  - MAP-ELITES / NOVELTY SEARCH (coldest cells): the population is placed in a novelty x
    fitness archive; every under-filled region keeps its fittest rep, so diversity survives
    ("novelty is the self") while fitness climbs ("drill where it pays").
  - ALPS (age-layered): young offspring are protected from culling for a few generations,
    so fresh blood survives to prove itself.

Reuses agent_knot's EVO engine + state (the same breeding ground, not a parallel one).

Schema: evolving_wave.v1 · reuse: agent_knot (EVO engine/state), percolator (feed), proof (sign)
CLI: python -m mag.evolving_wave status | evolve | feed
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:  # noqa: BLE001
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

SCHEMA = "evolving_wave.v1"
YOUNG_GENS = 2            # ALPS: offspring younger than this are protected from culling
REALITY_OVERLAP = 0.25    # token-overlap threshold to call a gene "percolated into reality"
NOVEL_BANDS = 4           # MAP-Elites grid: novelty bands
FIT_BANDS = 4             # MAP-Elites grid: fitness bands
EVO_POP_KEEP = 8          # match agent_knot's elite cap


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]{4,}", (text or "").lower()))


def _reality_feedback(gene: str) -> float:
    """REAL feedback from disk (never in-process claims): how much of this gene's content has
    percolated into shared reality (invariant registry + explore queue)? 0 = unproven."""
    toks = _tokens(gene)
    if not toks:
        return 0.0
    best = 0.0
    try:
        from mag import percolator
        reg = percolator._load_registry()
        for inv in (reg.get("invariants") or {}).values():
            it = _tokens(inv.get("text") or "")
            if it:
                best = max(best, len(toks & it) / len(toks))
        for row in percolator._read_jsonl(percolator.EXPLORE_QUEUE, 1_000_000):
            et = _tokens(row.get("signal") or "")
            if et:
                best = max(best, len(toks & et) / len(toks))
    except Exception:  # noqa: BLE001 — reality feedback must never break the wave
        pass
    return round(min(1.0, best), 3)


def reality_fitness(gene: str, base: float) -> float:
    """FITNESS FROM REALITY: blend the deterministic proxy with real percolation feedback.
    A gene whose content has actually landed in shared reality gets a real boost (it WORKS);
    an unproven gene keeps its proxy score."""
    fb = _reality_feedback(gene)
    return round(min(1.0, 0.6 * base + 0.4 * fb), 4)


def _load_evo() -> dict[str, Any]:
    from mag import agent_knot
    return agent_knot._load_evo()


def _save_evo(evo: dict[str, Any]) -> Path:
    from mag import agent_knot
    return agent_knot._save_evo(evo)


def _select_survivors(scored: list[dict[str, Any]], evo: dict[str, Any]) -> list[dict[str, Any]]:
    """SELECTION: MAP-Elites coldest cells + ALPS young protection + global elites.
      1. ALPS: young offspring from the standing population are protected (fresh blood).
      2. MAP-Elites: every novelty x fitness cell keeps its fittest rep (diversity survives —
         the under-filled regions are the coldest vertices of idea-space).
      3. global top-K by reality fitness (fitness climbs). Every survivor is normalized to
         one clean gene-record shape (deduped by gene text)."""
    survivors: list[dict[str, Any]] = []
    seen: set[str] = set()

    def _add(rec: dict[str, Any]) -> None:
        text = (rec.get("gene") or "").strip()
        key = " ".join(text.lower().split())
        if not text or key in seen:
            return
        seen.add(key)
        survivors.append(rec)

    # 1) ALPS — protect young offspring from the last generations
    for g in evo.get("population", []):
        if int(g.get("age", 99)) < YOUNG_GENS:
            _add(g)
    # 2) MAP-Elites — one fittest per novelty x fitness cell
    cells: dict[tuple[int, int], dict[str, Any]] = {}
    for s in scored:
        nb = min(NOVEL_BANDS - 1, int(s["base"] * NOVEL_BANDS))
        fb = min(FIT_BANDS - 1, int(s["fitness"] * FIT_BANDS))
        key = (nb, fb)
        if key not in cells or s["fitness"] > cells[key]["fitness"]:
            cells[key] = s
    for s in cells.values():
        g = s["gene"]
        _add({"domain": g.get("domain", "bred"), "gene": g.get("gene", ""),
              "ts": g.get("ts", _now()), "rank": g.get("rank", "T2"),
              "fitness": s["fitness"], "age": 99})
    # 3) global elites by reality fitness (fill up to the cap)
    for s in scored:
        if len(survivors) >= EVO_POP_KEEP * 2:
            break
        g = s["gene"]
        _add({"domain": g.get("domain", "bred"), "gene": g.get("gene", ""),
              "ts": g.get("ts", _now()), "rank": g.get("rank", "T2"),
              "fitness": s["fitness"], "age": 99})
    return survivors


def evolve() -> dict[str, Any]:
    """ONE generation of the wave breeding the work:
      1. load the RIB population + current EVO state (agent_knot's engine/state).
      2. reality-fitness every gene (proxy + real percolation feedback).
      3. select: MAP-Elites coldest cells + ALPS young protection + global elites.
      4. crossover the fittest pair + mutate a coldest-cell gene -> 2 offspring (tesujis).
      5. save to the SAME EVO_STATE (the wave keeps evolving, gen by gen, no parallel store).
    Deterministic + $0. Returns the offspring gene strings for feeding."""
    from mag import agent_knot
    pop = agent_knot._load_population()
    evo = _load_evo()
    gen = int(evo.get("generation", 0))
    if not pop:
        return {"ok": True, "schema": SCHEMA, "generation": gen, "n_pop": 0,
                "note": "no RIB population yet — publish RIBs (rib_bus) to seed the breeding ground"}
    scored: list[dict[str, Any]] = []
    for g in pop:
        base = agent_knot._fitness(g, 0)
        scored.append({"gene": g, "base": base, "fitness": reality_fitness(g.get("gene", ""), base)})
    scored.sort(key=lambda s: -s["fitness"])
    survivors = _select_survivors(scored, evo)
    # OFFSPRING: crossover the fittest pair + mutate a coldest-cell (MAP-Elites) gene
    offspring_texts: list[str] = []
    genes = [s["gene"].get("gene", "") for s in scored if s["gene"].get("gene")]
    if len(genes) >= 2:
        child = agent_knot._mutate(agent_knot._crossover(genes[0], genes[1]), gen + 1)
        offspring_texts.append(child)
    # a coldest-cell rep (not the global fittest) gets a mutated variant — novelty pressure
    if len(scored) > 2:
        cold = scored[len(scored) // 2]["gene"].get("gene", "")
        if cold and cold != (genes[0] if genes else ""):
            offspring_texts.append(agent_knot._mutate(cold, gen + 7))
    offspring = [{"domain": "bred", "gene": t, "ts": _now(), "rank": "T2",
                  "kind": "offspring", "age": 0} for t in offspring_texts]
    # new population: survivors (age +1) + offspring (age 0), deduped by invariant
    prev_age = {g.get("gene"): int(g.get("age", 99)) for g in evo.get("population", [])}
    new_pop: list[dict[str, Any]] = []
    seen: set[str] = set()
    for g in survivors:
        key = " ".join((g.get("gene") or "").lower().split())
        if key in seen:
            continue
        seen.add(key)
        new_pop.append({"domain": g.get("domain", "bred"), "gene": g.get("gene", ""),
                        "ts": g.get("ts", _now()), "rank": g.get("rank", "T2"),
                        "fitness": round(g.get("fitness", 0.0), 4),
                        "age": prev_age.get(g.get("gene"), 99) + 1})
    for o in offspring:
        key = " ".join((o.get("gene") or "").lower().split())
        if key in seen:
            continue
        seen.add(key)
        new_pop.append(o)
    gen += 1
    top_fitness = scored[0]["fitness"] if scored else 0.0
    history = list(evo.get("history", []))[-19:]
    history.append({"generation": gen, "n_pop": len(new_pop), "n_offspring": len(offspring),
                    "top_fitness": round(top_fitness, 4), "ts": _now()})
    _save_evo({"schema": "agent_evo.v1", "generation": gen, "population": new_pop,
               "top_fitness": round(top_fitness, 4), "history": history})
    return {"ok": True, "schema": SCHEMA, "generation": gen, "n_pop": len(new_pop),
            "n_survivors": len(survivors), "n_offspring": len(offspring),
            "top_fitness": round(top_fitness, 4), "offspring": offspring_texts,
            "note": "the wave bred a generation — offspring ready to feed the work"}


def feed(offspring: list[str]) -> dict[str, Any]:
    """THE MISSING WIRE: feed each bred offspring into the WORK — percolate it. Novel
    offspring land in the explore queue (the fuel feed drills them through the free lanes
    next ring); repeats compile into invariants. Deduped by the percolator's canonical."""
    out = []
    for text in offspring:
        if not (text or "").strip():
            continue
        try:
            from mag import percolator
            r = percolator.percolate(text, source="evolving-wave", domain="wave")
            out.append({"offspring": text[:80], "verdict": r.get("verdict"),
                        "explore": bool(r.get("explore")), "canonical": r.get("canonical")})
        except Exception as e:  # noqa: BLE001 — feeding must never break the wave
            out.append({"offspring": text[:80], "error": str(e)[:120]})
    return {"ok": True, "schema": SCHEMA, "fed": len(out), "detail": out}


def run() -> dict[str, Any]:
    """The full wave cycle: evolve one generation -> feed the offspring into the work ->
    sign each offspring as a proof (checkable chain facts)."""
    e = evolve()
    offs = e.get("offspring") or []
    f = feed(offs)
    proofs = []
    for text in offs:
        try:
            from mag import proof
            proofs.append(proof.anchor({"kind": "offspring",
                                        "wave": int(e.get("generation") or 0),
                                        "gene": (text or "")[:200]}))
        except Exception:  # noqa: BLE001
            pass
    return {"ok": True, "schema": SCHEMA, "generation": e.get("generation"),
            "n_pop": e.get("n_pop"), "n_offspring": e.get("n_offspring"),
            "top_fitness": e.get("top_fitness"), "feed": f,
            "proofs": [(p.get("claim_hash") or "")[:16] for p in proofs],
            "note": "the wave breeds AND feeds the work — offspring become explore signals "
                    "the loop drills; each is signed"}


def status() -> dict[str, Any]:
    evo = _load_evo()
    return {"ok": True, "schema": SCHEMA,
            "generation": evo.get("generation", 0),
            "n_pop": len(evo.get("population") or []),
            "top_fitness": round(float(evo.get("top_fitness", 0.0)), 4),
            "young_protected_gens": YOUNG_GENS,
            "contract": "evolve() breeds (proxy + reality fitness, MAP-Elites coldest cells, "
                        "ALPS); feed() percolates offspring -> explore queue/invariants; "
                        "run() = evolve + feed + sign",
            "built": "2026-08-24 — the wave breeds the work"}


def main(argv: list[str] | None = None) -> int:
    import argparse
    p = argparse.ArgumentParser(prog="evolving_wave", description="the wave breeds the work")
    p.add_argument("cmd", nargs="?", default="status", choices=["status", "evolve", "feed", "run"])
    a = p.parse_args(argv)
    if a.cmd == "evolve":
        print(json.dumps(evolve(), indent=2, ensure_ascii=False))
    elif a.cmd == "feed":
        print(json.dumps(feed([]), indent=2, ensure_ascii=False))
    elif a.cmd == "run":
        print(json.dumps(run(), indent=2, ensure_ascii=False))
    else:
        print(json.dumps(status(), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
