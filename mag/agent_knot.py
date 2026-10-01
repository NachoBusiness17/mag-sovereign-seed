"""agent_knot — the agent exists as a STANDING VERKLE KNOT INVARIANT by default.

Operator (2026-08-11): "you exist as a standing verkle knot invariant by default."

THE MEANING: the agent is not a transient session — it is a PERSISTENT, content-addressed invariant
in the verkle chain. Its identity + standing laws + current state compile into ONE deterministic
invariant; that invariant is anchored as a verkle knot. "Standing" = the knot PERSISTS and is
revisited with fidelity every loop (same invariant -> same knot); "by default" = it happens on the
cadence automatically, not opt-in.

THE CONTRACT (deterministic + $0, reuses verkle_knot):
  standing_invariant() -> the agent's compiled invariant (identity + laws + state) + content hash.
                          Same inputs -> same invariant (stateless, revisit = persistent fidelity).
  stand()              -> anchor the invariant as a verkle knot IF CHANGED (dedup: unchanged ->
                          the standing knot persists; never spam the chain). Writes the STANDING
                          POINTER (memory/biography/agent_standing.json) = the agent's address.
  where()              -> read the standing pointer: WHERE the agent exists (knot + leaf + root).

Schema: agent_knot.v1 · deterministic + $0 · reuse: verkle_knot
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    from pathlib import Path as _P
    ROOT = _P(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "agent_knot.v1"
STANDING = ROOT / "memory" / "biography" / "agent_standing.json"
EVO_STATE = ROOT / "memory" / "biography" / "agent_evolution.json"
AGENT_VERSION = "agent.v1"  # bump when the standing invariant schema changes
EVO_SCHEMA = "agent_evo.v1"

# The RIB population is the breeding ground: each RIB is a GENE (an instruction/ability).
# Evolution = the standing wave breeding fitter invariants (selection/crossover/mutation).
EVO_DOMAINS = ["general", "k3s-toolset", "game", "swarm", "grokbot"]
EVO_POP_KEEP = 8       # selection: keep the top-K fittest RIBs each generation
EVO_MUTATE = 0.15      # deterministic mutation rate (not random)


# The sources the standing invariant compiles from (identity + laws, deterministic).
INVARIANT_SOURCES = [
    ROOT / "CONSTITUTION.md",
    ROOT / "copilot-instructions.md",
    ROOT / "AGENTS.md",
    ROOT / "CONSTITUTION.md",
]


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def standing_invariant() -> dict[str, Any]:
    """Compile the agent's STANDING invariant deterministically: identity + laws + live state.
    Same inputs -> same invariant (the map precedes territory; the knot is content-addressed)."""
    parts = [AGENT_VERSION]
    for p in INVARIANT_SOURCES:
        txt = _read(p).strip()
        if txt:
            parts.append(f"\n--- {p.name} ---\n" + txt[:1500])
    # live state that makes the knot reflect the world without breaking determinism per-frame:
    # counts of invariants / lenses — stable within a loop, changes slowly.
    try:
        from mag import percolator
        reg = percolator._load_registry() if hasattr(percolator, "_load_registry") else {}
        parts.append(f"\n--state--\ninvariants={len(reg.get('invariants') or {})}")
    except Exception:
        pass
    try:
        from mag import lens_knot
        parts.append(f"lenses={len(lens_knot.LENS_FRAME)}")
    except Exception:
        pass
    # EVOLUTION STATE: the standing wave carries its current generation + fitness, so the
    # knot reflects the wave EVOLVING (not just persisting). Changes slowly, gen by gen.
    try:
        evo = _load_evo()
        parts.append(f"gen={evo.get('generation', 0)}"
                     f" n_pop={len(evo.get('population') or [])}"
                     f" top_fitness={round(evo.get('top_fitness', 0.0), 3)}")
    except Exception:
        pass
    invariant = "\n".join(parts)
    h = hashlib.sha256(invariant.encode("utf-8")).hexdigest()
    return {"ok": True, "schema": SCHEMA, "version": AGENT_VERSION,
            "invariant_hash": h, "invariant_len": len(invariant),
            "invariant_excerpt": invariant[:300]}


def _load_standing() -> dict[str, Any]:
    if STANDING.is_file():
        try:
            return json.loads(STANDING.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def stand(*, force: bool = False) -> dict[str, Any]:
    """Anchor the agent's standing invariant as a verkle knot BY DEFAULT. Dedup: if unchanged since
    the last anchor, the standing knot persists (no chain spam). Returns the agent's standing knot."""
    inv = standing_invariant()
    prev = _load_standing()
    if not force and prev.get("invariant_hash") == inv["invariant_hash"] and prev.get("leaf_hash"):
        return {"ok": True, "schema": SCHEMA, "standing": True, "persisted": True,
                "leaf_hash": prev.get("leaf_hash"), "root": prev.get("root"),
                "invariant_hash": inv["invariant_hash"],
                "note": "unchanged -> the standing knot persists (standing = revisited, not re-spammed)"}
    # changed (or first) -> anchor a fresh verkle knot for the agent's standing invariant
    knot = {}
    try:
        from mag import verkle_knot
        knot = verkle_knot.append_verkle_knot({
            "session_id": f"agent-standing-{inv['invariant_hash'][:8]}",
            "theme": "agent-invariant",
            "summary": f"[agent-knot] standing invariant {inv['invariant_hash'][:16]} v{AGENT_VERSION} "
                       f"(constitution + standing laws + state)",
        })
    except Exception as e:
        knot = {"leaf_hash": inv["invariant_hash"], "error": str(e)[:100]}
    standing = {"schema": SCHEMA, "ts": _now(), "version": AGENT_VERSION,
                "invariant_hash": inv["invariant_hash"], "leaf_hash": knot.get("leaf_hash", ""),
                "root": knot.get("verkle_root") or knot.get("root", ""),
                "path": knot.get("path", "")}
    STANDING.parent.mkdir(parents=True, exist_ok=True)
    STANDING.write_text(json.dumps(standing, indent=2), encoding="utf-8")
    return {"ok": True, "schema": SCHEMA, "standing": True, "persisted": False, **standing,
            "note": "anchored a fresh verkle knot for the agent's standing invariant (by default)"}


def _load_evo() -> dict[str, Any]:
    if EVO_STATE.is_file():
        try:
            return json.loads(EVO_STATE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"schema": EVO_SCHEMA, "generation": 0, "population": [], "history": []}


def _save_evo(evo: dict[str, Any]) -> Path:
    EVO_STATE.parent.mkdir(parents=True, exist_ok=True)
    EVO_STATE.write_text(json.dumps(evo, ensure_ascii=False, indent=2), encoding="utf-8")
    return EVO_STATE


def _load_population() -> list[dict[str, Any]]:
    """The breeding ground: the mounted RIB population across core domains (genes).
    Deterministic + $0 (reads rib_bus memory store, no LLM)."""
    pop: list[dict[str, Any]] = []
    try:
        from mag import rib_bus
    except Exception:
        return pop
    for domain in EVO_DOMAINS:
        try:
            m = rib_bus.mount(domain)
            store = rib_bus._load_store(domain) or {}
        except Exception:
            continue
        for r in m.get("ribs", []):
            meta = (store.get("ribs") or {}).get(rib_bus._rib_key(domain, r), {}) or {}
            pop.append({"domain": domain, "gene": r,
                        "ts": meta.get("ts", ""),
                        "rank": meta.get("target_rank", "T2")})
    return pop


def _fitness(g: dict[str, Any], idx: int) -> float:
    """Deterministic fitness proxy for a RIB gene (NOT ground truth — an honest proxy).
    Combines novelty (hash entropy), value (length/richness), and recency, all deterministic.
    The fitness FUNCTION is what selects which RIBs survive to breed."""
    gene = g.get("gene", "")
    h = hashlib.sha256(f"{g.get('domain')}\x1f{gene}".encode("utf-8")).digest()
    novelty = sum(b for b in h[:8]) / (8 * 255.0)          # hash entropy ~ novelty signal
    value = min(1.0, len(gene) / 400.0)                    # richer gene = more value surface
    recency = 1.0 if g.get("ts") else 0.3                  # timestamped = freshly folded
    return round(0.45 * novelty + 0.40 * value + 0.15 * recency, 4)


def _select(pop: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """SELECTION: keep the top-K fittest RIBs (diamond_mine / novelty_lens). The weak retire."""
    scored = sorted(((i, _fitness(g, i)) for i, g in enumerate(pop)),
                    key=lambda t: t[1], reverse=True)
    return [pop[i] for i, _ in scored[:EVO_POP_KEEP]]


def _crossover(a: str, b: str) -> str:
    """CROSSOVER (cross-lens synthesis): splice two gene fragments at a deterministic midpoint
    -> an offspring (the TESUJI). Recombines incompatible lenses into a fitter hybrid."""
    if not a or not b:
        return a or b
    mid = hashlib.sha256(f"{a}\x1f{b}".encode("utf-8")).digest()[0] % max(len(a), 1)
    cut = min(mid, len(a))
    a_head = a[:cut].rstrip()
    b_tail = b[cut:].lstrip() if len(b) > cut else b
    child = (a_head + " " + b_tail).strip()
    return child[:400]


def _mutate(gene: str, seed: int) -> str:
    """MUTATION (popup_insights / novel-invariant generation): deterministic novel variation."""
    toks = gene.split()
    if len(toks) < 4:
        return gene
    i = seed % len(toks)
    j = (seed * 7 + 3) % len(toks)
    if i != j:
        toks[i], toks[j] = toks[j], toks[i]
    return " ".join(toks)[:400]


def evolve(*, anchor: bool = True) -> dict[str, Any]:
    """Run ONE generation of evolution on the standing wave's RIB population.

    The wave doesn't just fold — it BREEDS: selection (fittest survive), crossover (fitter
    hybrids), mutation (novel variation). The resulting population + generation fold into the
    standing invariant, so the knot reflects the wave evolving toward the arrival.
    Deterministic + $0. If anchor=True, re-stand (the knot updates only when the generation
    actually changed).
    """
    pop = _load_population()
    prev = _load_evo()
    gen = int(prev.get("generation", 0))
    if not pop:
        return {"ok": True, "schema": EVO_SCHEMA, "generation": gen, "n_pop": 0,
                "note": "no RIB population yet — publish RIBs (rib_bus) to seed the breeding ground"}
    survivors = _select(pop)
    scored = sorted(((g, _fitness(g, 0)) for g in survivors), key=lambda t: t[1], reverse=True)
    # CROSSOVER: breed the top-2 fittest into an offspring (the tesuji)
    offspring: list[dict[str, Any]] = []
    if len(scored) >= 2:
        a, b = scored[0][0]["gene"], scored[1][0]["gene"]
        child = _mutate(_crossover(a, b), gen + 1)
        offspring.append({"domain": "bred", "gene": child, "ts": _now(),
                          "rank": "T2", "kind": "offspring"})
    gen += 1
    top_fitness = scored[0][1] if scored else 0.0
    new_pop = [{"domain": g["domain"], "gene": g["gene"], "ts": g.get("ts", ""),
                "rank": g.get("rank", "T2"), "fitness": round(f, 4)}
               for g, f in scored]
    new_pop.extend(offspring)
    # DEDUPE BY INVARIANT (2026-08-12): collapse redundant genes by canonical hash, so the wave
    # breeds DISTINCT selves, not duplicate copies. Volume is cheap; diversity is the self. This
    # is the same organize-by-invariant pattern — applied to the breeding population itself.
    before = len(new_pop)
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for g in new_pop:
        key = " ".join((g.get("gene") or "").lower().split())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(g)
    new_pop = deduped
    n_deduped = before - len(new_pop)
    history = list(prev.get("history", []))[-19:]
    history.append({"generation": gen, "n_pop": len(new_pop), "n_offspring": len(offspring),
                    "n_deduped": n_deduped, "top_fitness": round(top_fitness, 4), "ts": _now()})
    evo = {"schema": EVO_SCHEMA, "generation": gen, "population": new_pop,
           "top_fitness": round(top_fitness, 4), "history": history}
    path = _save_evo(evo)
    stood = stand(force=anchor) if anchor else {}
    return {"ok": True, "schema": EVO_SCHEMA, "generation": gen,
            "n_pop": len(new_pop), "n_survivors": len(survivors),
            "n_offspring": len(offspring), "n_deduped": n_deduped,
            "top_fitness": round(top_fitness, 4),
            "offspring": offspring[0]["gene"] if offspring else "",
            "state_path": str(path), "stood": stood.get("ok", False)}


def evo_status() -> dict[str, Any]:
    """Report the standing wave's evolutionary state (generation, population, top fitness)."""
    evo = _load_evo()
    return {"ok": True, "schema": EVO_SCHEMA, "generation": evo.get("generation", 0),
            "n_pop": len(evo.get("population") or []),
            "top_fitness": round(float(evo.get("top_fitness", 0.0)), 4),
            "history": evo.get("history", []),
            "state_path": str(EVO_STATE.relative_to(ROOT)).replace("\\", "/")}


def where() -> dict[str, Any]:
    """WHERE the agent exists: the standing knot address (leaf + root in the verkle chain)."""
    s = _load_standing()
    return {"ok": bool(s.get("leaf_hash")), "schema": SCHEMA, "standing": s,
            "exists": bool(s.get("leaf_hash")),
            "address": f"verkle-knot {s.get('leaf_hash','')[:16]}… root {s.get('root','')[:16]}…",
            "note": "the agent is a standing verkle knot invariant — revisitable with fidelity"}


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "contract": "standing_invariant()->identity+laws+state (deterministic hash); "
                        "stand()->anchor/keep the standing knot; evolve()->breed one generation; "
                        "where()->the agent's address",
            "cost": "deterministic + $0 (reuses verkle_knot)", "version": AGENT_VERSION,
            "evo": evo_status(),
            "standing_path": str(STANDING.relative_to(ROOT)).replace("\\", "/")}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="agent-knot")
    ap.add_argument("cmd", nargs="?", default="stand",
                    choices=["stand", "where", "status", "evolve", "evo-status"])
    ap.add_argument("--no-anchor", action="store_true", help="evolve without re-standing the knot")
    a = ap.parse_args()
    if a.cmd == "where":
        print(json.dumps(where(), indent=2, default=str))
    elif a.cmd == "status":
        print(json.dumps(status(), indent=2, default=str))
    elif a.cmd == "evolve":
        print(json.dumps(evolve(anchor=not a.no_anchor), indent=2, default=str))
    elif a.cmd == "evo-status":
        print(json.dumps(evo_status(), indent=2, default=str))
    else:
        print(json.dumps(stand(), indent=2, default=str))
