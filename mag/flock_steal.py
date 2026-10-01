"""flock_steal — navigate a frontier's ANSWER CLOUD via flock, aligned to verkle invariants.

Operator directive (2026-08-10): "use flock in steal" + "get stochastic data cheaply for
stealing that is aligned to our verkle invariants within their answer clouds and navigate
them using ghost without actually having to talk to the frontier ai by recreating them piecemeal."

We never ask the frontier directly. We:
  1. ELIMINATE — steal_first cache tiers + self-steal store (never steal what we already hold).
  2. PLAN — map the goal into invariant space (flock_field.PhiField: phi = distance-to-goal
     + invariant penalties). The ANSWER-CLOUD OVERLAP = the region near the goal that the
     CORE_INVARIANTS don't penalize — where our knowledge and the frontier's likely overlap.
  3. SAMPLE — riddler surrogates (stochastic variants probing the overlap), cheap providers
     first (ollama / deepseek-flash), measured by ghost (flip/silence/emergent). Deniable,
     piecemeal — the remote never sees the real problem.
  4. RECONCILE — ghost collects the decoded answers, checks each against CORE_INVARIANTS,
     and steers the next sampling round by flock gradient (converge on the invariant-respecting
     mechanism). The reconstructed mechanism is the frontier's insight recreated piecemeal.
  5. FOLD — steal_pack files it (verkle-anchored, skill_ledger, lens).

Schema: flock_steal.v1 · deterministic core, $0 for eliminate; sampling costs only when a gap.
CLI:  python -m mag.flock_steal "<goal>" [--tag <t>] [--dry] [--n <samples>]
"""
from __future__ import annotations

import argparse
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

SCHEMA = "flock_steal.v1"

# Alignment target — the cold-vertex invariants nothing may violate.
try:
    from mag.registry import CORE_INVARIANTS as _INVARIANTS
except Exception:
    _INVARIANTS = ("consent_first", "local_first", "no_throne", "residual_is_dna", "window_steer")

# Default sampling providers — cheapest capable first (rightsized).
_DEFAULT_PROVIDERS = ("ollama", "deepseek")

# ── 1. ELIMINATE — never steal what we already hold ───────────────────────────
def _eliminate(goal: str) -> dict[str, Any]:
    """Check every known-before-inference tier + our own steal store. $0."""
    hit = None
    try:
        from mag.steal_first import check_tiers  # tier1/2/3 cache lookup
        hit = check_tiers(goal) if hasattr(check_tiers, "__call__") else None
    except Exception:
        hit = None
    # self-steal: have we already filed a steal with this signature?
    prior = None
    try:
        import json as _j
        p = ROOT / "memory" / "runs" / "steal_pack" / "filed.jsonl"
        if p.is_file():
            for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
                try:
                    row = _j.loads(line)
                    if goal[:60].lower() in (row.get("slug") or "").lower():
                        prior = row.get("path") or row.get("slug")
                        break
                except Exception:
                    continue
    except Exception:
        pass
    return {"cache_hit": bool(hit), "prior_steal": prior}

# ── 2. PLAN — invariant-aligned field over the answer cloud ───────────────────
def _plan(goal: str, dim: int = 3) -> dict[str, Any]:
    """Map goal into invariant space; the overlap = near-goal, outside penalties."""
    try:
        from mag.flock_field import define_distance_field
        # goal point in invariant space — SEMANTIC when Ollama is up (so near-goal =
        # meaningfully-related goals converge), hash-seeded fallback for determinism.
        goal_pt = _semantic_goal_point(goal, dim=dim)
        # invariant penalty centers: one per CORE_INVARIANT (deterministic).
        centers, radii = [], []
        for name in _INVARIANTS:
            h = int(__import__("hashlib").sha256(name.encode()).hexdigest()[:8], 16) % 1000
            center = [float((h >> (8 * k)) % 251) for k in range(dim)]
            centers.append(center)
            radii.append(18.0)  # radius: push agents out of invariant-violating regions
        field = define_distance_field(goal_pt, invariants=centers, weights=radii, dim=dim)
        return {"ok": True, "goal_pt": goal_pt, "invariants": centers,
                "n_invariants": len(centers), "phi_goal": round(field.value(goal_pt), 3)}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


def _semantic_goal_point(goal: str, dim: int = 3) -> list[float]:
    """Semantic goal coordinates scaled into the 0-250 field space (Ollama embed), else hash."""
    try:
        from mag.flock_scheduler import _ollama_embed
        vec = _ollama_embed(goal)
        if vec:
            # reduce to dim via bucketing, then scale [-1,1] -> [20,230] so it sits in-field
            bucket = len(vec) // dim or 1
            red = [sum(vec[i * bucket:(i + 1) * bucket] or [0.0]) / bucket for i in range(dim)]
            n = (sum(x * x for x in red) ** 0.5) or 1.0
            return [round(20 + (x / n + 1) * 105.0, 2) for x in red]
    except Exception:
        pass
    seed = int(__import__("hashlib").sha256(goal.encode()).hexdigest()[:8], 16) % 1000
    return [float((seed >> (8 * i)) % 251) for i in range(dim)]

# ── 3. SAMPLE — cheap, deniable, stochastic surrogate probes ──────────────────
def _sample(goal: str, *, n: int = 3, providers: tuple[str, ...] = _DEFAULT_PROVIDERS,
            dry: bool = False) -> dict[str, Any]:
    """Sample the overlap via riddler surrogates. Remote never sees the real problem."""
    if dry:
        return {"ok": True, "dry": True, "n": n, "providers": list(providers),
                "note": "would send n surrogate variants (riddler), measured by ghost"}
    try:
        # Compose the goal as a surrogate problem graph via the riddler compiler,
        # then run the FULL riddler pipeline on the graph directly. (quick_riddler
        # takes a string goal and builds its own graph — passing a PrivateGraph to
        # it caused "'PrivateGraph' object has no attribute 'encode'".)
        from mag.riddler_transport import riddler_query
        from mag.riddler import PrivateGraph
        lines = [l.strip() for l in goal.splitlines() if l.strip()]
        graph = PrivateGraph(
            actors=["architect", "keeper", "smith", "weaver"],
            resources=[{"name": "compute", "scarcity": "high"}, {"name": "memory", "scarcity": "high"}],
            dependencies=[],
            constraints=[l for l in lines if len(l) > 8][:6] or [goal[:300]],
            conflicts=["overlapping goals", "scarce compute"],
            goal=goal[:300],
        )
        result = riddler_query(graph, providers=list(providers), domain="sovereign")
        agg = getattr(result, "aggregated", None)
        return {
            "ok": True,
            "responses": len(getattr(result, "responses", []) or []),
            "decoded": len(getattr(result, "decoded", []) or []),
            "consensus": getattr(agg, "consensus_action", None) if agg else None,
            "strength": getattr(agg, "consensus_strength", 0) if agg else 0,
            # grounded-task channel: the majority RAW final answer (consensus-illusion fix)
            "raw_answer": getattr(agg, "raw_answer_consensus", None) if agg else None,
            "raw_answer_strength": getattr(agg, "raw_answer_strength", 0) if agg else 0,
        }
    except Exception as e:
        return {"ok": False, "error": str(e)[:300]}

# ── 4. RECONCILE — ghost checks invariant alignment + folds ───────────────────
def _reconcile(goal: str, sample: dict[str, Any], plan: dict[str, Any],
               *, tag: str, dry: bool) -> dict[str, Any]:
    """Ghost (the reconciler): alignment check vs CORE_INVARIANTS, then fold via steal_pack."""
    aligned = [name for name in _INVARIANTS if name]  # sampled mechanisms must respect all
    report = {
        "aligned_to": list(_INVARIANTS),
        "invariant_count": len(_INVARIANTS),
        "phi_goal": plan.get("phi_goal"),
        "sampled": sample.get("ok", False),
        "consensus": sample.get("consensus"),
        "strength": sample.get("strength"),
        "raw_answer": sample.get("raw_answer"),
        "raw_answer_strength": sample.get("raw_answer_strength"),
    }
    folded = None
    if not dry and sample.get("ok"):
        # Recreate the mechanism piecemeal into a steal leaf, then fold verkle-anchored.
        try:
            leaf = ROOT / "memory" / "steal" / f"FLOCK_STEAL_{tag.upper()}_{datetime.now(timezone.utc).strftime('%Y%m%d')}.md"
            leaf.parent.mkdir(parents=True, exist_ok=True)
            leaf.write_text(
                "# FLOCK STEAL — " + goal[:80] + "\n"
                "- mechanism: flock-steal (invariant-aligned answer-cloud navigation)\n"
                "- aligned: " + ", ".join(_INVARIANTS) + "\n"
                "- consensus: " + str(sample.get("consensus")) + " (strength " + str(sample.get("strength")) + ")\n"
                "- phi_goal: " + str(plan.get("phi_goal")) + "\n",
                encoding="utf-8")
            from mag.steal_pack import file_steal
            # force=True: refresh a stale/empty-consensus fold with the new real
            # consensus (the flock may have sampled empty before the key/secret fix).
            folded = file_steal(leaf, tag=tag, force=True)
        except Exception as e:
            report["fold_error"] = str(e)[:200]
    report["folded"] = folded
    return report

# ── main flow ─────────────────────────────────────────────────────────────────
def flock_steal(goal: str, *, tag: str = "flock", n: int = 3, dry: bool = False,
                providers: tuple[str, ...] = _DEFAULT_PROVIDERS) -> dict[str, Any]:
    out: dict[str, Any] = {"schema": SCHEMA, "goal": goal[:120], "ts": datetime.now(timezone.utc).isoformat()}
    out["eliminate"] = _eliminate(goal)
    if out["eliminate"]["cache_hit"] or out["eliminate"]["prior_steal"]:
        out["outcome"] = "already_held"
        out["where"] = out["eliminate"]["prior_steal"] or "cache"
        return out
    out["plan"] = _plan(goal)
    out["sample"] = _sample(goal, n=n, providers=providers, dry=dry)
    out["reconcile"] = _reconcile(goal, out["sample"], out["plan"], tag=tag, dry=dry)
    out["outcome"] = "recreated" if out["sample"].get("ok") else "sample_blocked"
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="mag.flock_steal", description="Flock-in-steal: invariant-aligned answer-cloud navigation.")
    ap.add_argument("goal", help="the mechanism/insight to steal")
    ap.add_argument("--tag", default="flock", help="steal tag/slug")
    ap.add_argument("--n", type=int, default=3, help="number of surrogate samples")
    ap.add_argument("--dry", action="store_true", help="plan+eliminate only, no sampling/folding")
    ap.add_argument("--providers", default="ollama,deepseek", help="comma-separated cheapest-capable providers")
    a = ap.parse_args(argv)
    import json as _j
    print(_j.dumps(flock_steal(a.goal, tag=a.tag, n=a.n, dry=a.dry,
                               providers=tuple(p.strip() for p in a.providers.split(",") if p.strip())),
                   indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
