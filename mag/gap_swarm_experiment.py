"""gap_swarm_experiment — 3-level steal + design the DeepSeek↔Grok gap-extraction experiment
to our swarms cheaply.

Operator (2026-08-10): "steal three times tell me what you find in each level as you dedupe and
simulate this as an ask to grok 4.5 design the experiment to extract and map data around complex
relevant gaps we have between deep seek and grok to our swarms cheaply"

THE 3-LEVEL STEAL (steal-both-default, executed concretely):
  LEVEL 1 (self-steal) — audit OUR OWN corpus for what we already hold about the DeepSeek↔Grok
      gap: frontier_batch, exit_dialogue (Grok analyzes/DeepSeek patterns), grok_gate/rightsize/
      window_hop (tier routing), elevate (escalate to grok-4.5), flock_steal (frontier answer
      clouds). These ARE the gap machinery.
  LEVEL 2 (external steal) — the mechanisms from frontier-model research we adapt: self-consistency
      integrator, schema-constrained decoding, mixture-of-agents compositing, tool-grounding,
      CoT-gated-by-external-verifier (the RIB→LLM honest mapping).
  LEVEL 3 (dedupe + synthesize) — dedupe across both: the overlapping invariant is RIGHTSIZE +
      PROVENANCE (cheapest capable tier + honest output labeling). The gap = where cheap DeepSeek
      diverges from frontier Grok on complex judgment, and how to EXTRACT that divergence cheaply.

THE EXPERIMENT (designed as a RIB, dispatched through our swarm):
  For each "complex gap" probe (a question where cheap-tier and frontier-tier plausibly differ):
    * dispatch the SAME probe to DeepSeek (cheap swarm_worker) AND to frontier (grok-4.5 via
      frontier_batch/elevate), N witnesses each.
    * compare via Roshomon-style invariant grouping: where do cheap and frontier DISAGREE?
      disagreement = a GAP to map. agreement = already-covered (cache hit, don't re-pay).
    * map the gaps (probe -> cheap answer -> frontier answer -> delta) into a RIB scene.
    * rightsize: only the probes that actually diverge go to the expensive frontier tier; the
      converged ones stay cheap. This is the "cheaply" part.

Honesty: grok output is only 'frontier_model_output' if a REAL call landed (frontier_batch rule);
otherwise 'not_dispatched' and we say so. provenance is explicit on every artifact.

Schema: gap_swarm_experiment.v1 · CLI: python -m mag.gap_swarm_experiment steal | probes |
        design [--dry] | dispatch [--dry] | status
"""
from __future__ import annotations

import argparse
import json
import re
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

SCHEMA = "gap_swarm_experiment.v1"
OUT = ROOT / "memory" / "runs" / "gap_swarm_experiment"
PROBES = OUT / "probes.json"
DESIGN = OUT / "design.json"
GAP_MAP = OUT / "gap_map.json"

# ─────────────────────────────────────────────────────────── LEVEL 1: SELF-STEAL ──
# What WE already hold about the DeepSeek↔Grok gap (from our own corpus, self-steal).
SELF_STEAL: list[dict[str, Any]] = [
    {"source": "frontier_batch", "schema": "frontier_batch.v1",
     "find": "honest grok↔deepseek compare; provenance='frontier_model_output' only if a real call landed"},
    {"source": "exit_dialogue", "schema": "exit_dialogue.v1",
     "find": "Grok analyzes, DeepSeek patterns, human decides — the division of labor; $0.003/rightsized"},
    {"source": "grok_gate / rightsize / window_hop", "schema": "window_hop.v1",
     "find": "cheapest-capable tier routing; deepseek hit $0.0028/M miss $0.14/M out $0.28/M; only judgment climbs"},
    {"source": "elevate", "schema": "elevate.v1",
     "find": "escalate to grok-4.5 with --dry/--capture; frontier gated, not default"},
    {"source": "flock_steal", "schema": "flock_steal.v1",
     "find": "navigate a frontier's ANSWER CLOUD via flock; overlap = where our knowledge and frontier likely align"},
]
# ─────────────────────────────────────────────────────── LEVEL 2: EXTERNAL STEAL ──
# Mechanisms from frontier-model research we adapt (the RIB→LLM honest mapping).
EXTERNAL_STEAL: list[dict[str, Any]] = [
    {"source": "self-consistency (Wang 2203.11171)", "mechanism":
     "majority over N diverse samples as the integrator; a pixel = average of many samples"},
    {"source": "schema-constrained decoding (XGrammar 2411.15100)", "mechanism":
     "grammar/JSON-schema as the output contract; renderer decides final shading via schema validation"},
    {"source": "Mixture-of-Agents (2406.04692)", "mechanism":
     "layered compositing: layer N agents see all layer N-1 outputs; assemble a coherent whole"},
    {"source": "Toolformer (2302.04761)", "mechanism":
     "tool use as deterministic grounding / area-light; ground the model's claims in real tools"},
    {"source": "CoT gated by external verifier (2201.11903)", "mechanism":
     "chain-of-thought as shading passes, gated by a deterministic external verifier (light doesn't check itself)"},
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def steal() -> dict[str, Any]:
    """The 3-level steal, deduped. Level 3 = synthesize + dedupe across 1 and 2."""
    l1 = SELF_STEAL
    l2 = EXTERNAL_STEAL
    # LEVEL 3: dedupe — the overlapping invariant across both levels
    deduped = {
        "rightsize-and-provenance": "cheapest capable tier + honest output labeling (self: grok_gate/"
        "window_hop/rightsize; external: verifier-gated CoT + self-consistency as integrator)",
        "extract-divergence-cheaply": "only probes that actually diverge go to the expensive frontier "
        "tier; converged stay cheap (self: flock_steal overlap; external: MoA compositing + schema validation)",
    }
    return {"ok": True, "schema": SCHEMA, "level1_self_steal": l1,
            "level2_external_steal": l2, "level3_dedupe": deduped,
            "n_l1": len(l1), "n_l2": len(l2), "n_deduped": len(deduped)}


# ───────────────────────────────────────────────────────────────── THE PROBES ──
# Complex-gap probes: questions where cheap (DeepSeek) and frontier (Grok) plausibly differ.
DEFAULT_PROBES: list[str] = [
    "What is the deepest load-bearing invariant in how frontier reasoning models maintain "
    "coherence over long horizons without a central orchestrator?",
    "How should a self-improving agent decide when cheap-tier synthesis is insufficient and "
    "escalate to frontier reasoning?",
    "What are the honest failure modes of self-consistency as a truth detector, and when does "
    "majority-vote mislead?",
    "How can a memory system distinguish a genuine emergent invariant from a transient "
    "stochastic convergence across multiple model witnesses?",
    "What is the cheapest reliable way to extract a frontier model's reasoning structure "
    "without paying full frontier price for every answer?",
]


def probes() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    p = {"schema": SCHEMA, "ts": _now(), "n_probes": len(DEFAULT_PROBES),
         "probes": DEFAULT_PROBES}
    PROBES.write_text(json.dumps(p, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


# ─────────────────────────────────────────────────────── THE EXPERIMENT DESIGN ──
def design(*, cheap_witnesses: int = 3, frontier_witnesses: int = 2) -> dict[str, Any]:
    """Design the gap-extraction experiment as a RIB scene: probe -> cheap vs frontier -> delta.
    The experiment maps WHERE DeepSeek and Grok diverge, and rightsizes so only diverging probes
    pay the expensive tier."""
    pr = probes()
    scene_slots = []
    for i, p in enumerate(pr["probes"]):
        scene_slots.append({"id": f"gap_probe_{i}", "center": p, "radius": 0.35,
                            "kind": "gap-probe"})
    design_doc = {
        "schema": SCHEMA, "ts": _now(),
        "purpose": "extract + map complex gaps between DeepSeek (cheap) and Grok (frontier) to "
                   "our swarms cheaply",
        "method": (
            f"for each probe: dispatch to DeepSeek cheap swarm ({cheap_witnesses} witnesses) AND to "
            f"frontier grok-4.5 ({frontier_witnesses} witnesses); Roshomon-compare across tiers; "
            f"disagreement = a GAP to map; agreement = covered (cache hit, don't re-pay); only "
            f"diverging probes escalate to the expensive tier"
        ),
        "cheap_witnesses": cheap_witnesses, "frontier_witnesses": frontier_witnesses,
        "rib_slots": scene_slots,
        "provenance": "OUR experiment design (self+external steal), NOT a frontier claim",
    }
    DESIGN.write_text(json.dumps(design_doc, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "schema": SCHEMA, "design": str(DESIGN), "n_probes": len(scene_slots),
            "slots": scene_slots}


# ─────────────────────────────────────────────────────────── DISPATCH THROUGH SWARM ──
def dispatch(*, dry: bool = True, cheap_witnesses: int = 3) -> dict[str, Any]:
    """Feed the gap-experiment RIB to OUR k8s swarm as A/B render tasks. dry=True = $0 plan.
    Each probe = one render task to the cheap swarm (the expensive frontier is gated/separate)."""
    d = design()
    from mag import invariant_lattice as il
    out = {"ok": True, "schema": SCHEMA, "dry": dry, "tasks": []}
    for i, slot in enumerate(d["slots"]):
        for w in range(cheap_witnesses):
            task = f"[gap-probe {i} witness {w}] {slot['center']}"
            if dry:
                out["tasks"].append({"probe": i, "witness": w, "ok": True, "task_id": None})
            else:
                try:
                    r = il.dispatch_to_k8s(task, domain="gap-probe")
                    out["tasks"].append({"probe": i, "witness": w,
                                         "ok": bool(r.get("ok")), "task_id": r.get("task_id")})
                except Exception as e:
                    out["tasks"].append({"probe": i, "witness": w, "ok": False,
                                         "error": str(e)[:80]})
    out["n_tasks"] = len(out["tasks"])
    return out


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "design": str(DESIGN) if DESIGN.is_file() else "not built",
            "n_probes": len(DEFAULT_PROBES),
            "l1_findings": len(SELF_STEAL), "l2_findings": len(EXTERNAL_STEAL)}


# ─────────────────────────────────────────────────────────────── ESCALATE VIA SWARM ──
# Route the grok-4.5 escalation through OUR SWARM (operator 2026-08-10: "you keep using
# terminal instead of our swarm"). The escalation ask is ENQUEUED to the swarm_worker
# dedicated queue; the in-cluster worker renders it (real grok via the working xAI key),
# and collect()/bridge brings results back. NOT a terminal call.
def escalate(*, dry: bool = True, per_probe: int = 2) -> dict[str, Any]:
    """Enqueue the grok-4.5 gap-validation escalation to OUR SWARM (not the terminal).
    dry=True returns the plan ($0); dry=False enqueues so the cluster drains it."""
    from mag import invariant_lattice as il
    out = {"ok": True, "schema": SCHEMA, "dry": dry, "tasks": []}
    for i, p in enumerate(DEFAULT_PROBES):
        for w in range(per_probe):
            task = (f"[gap-escalation probe {i} witness {w}] Ask grok-4.5 to validate/refine the "
                    f"gap-extraction experiment for this probe, then return the sharpest "
                    f"disagreement/gap vs cheap-tier DeepSeek. Probe: {p}")
            if dry:
                out["tasks"].append({"probe": i, "witness": w, "ok": True, "task_id": None})
            else:
                try:
                    r = il.dispatch_to_k8s(task, domain="gap-escalate")
                    out["tasks"].append({"probe": i, "witness": w,
                                         "ok": bool(r.get("ok")), "task_id": r.get("task_id")})
                except Exception as e:
                    out["tasks"].append({"probe": i, "witness": w, "ok": False,
                                         "error": str(e)[:80]})
    out["n_tasks"] = len(out["tasks"])
    return out


# ─────────────────────────────────────── 3-ROUND DEEPSEEK+GROK SWARM DEEP RESEARCH ──
# Operator (2026-08-10): "steal three times through our swarm for deep research on deepseek and
# grok". Route 3 rounds of frontier deep-research questions through OUR SWARM (swarm_worker
# queue -> in-cluster worker), NOT the terminal. dry=True = plan ($0); dry=False enqueues.
DEEP_GROK_QUESTIONS: list[str] = [
    "Deep research: what are the sharpest structural gaps between DeepSeek (cheap deepseek-chat) "
    "and Grok (frontier grok-4.5) in reasoning quality, and how do we extract and map them cheaply "
    "to our swarm?",
    "Deep research: what invariant lets a self-improving system use cheap-tier synthesis (DeepSeek) "
    "while escalating only genuine judgment gaps to frontier (Grok)?",
    "Deep research: how do we run frontier-level (Grok-class) reasoning using our cheap swarm of "
    "DeepSeek witnesses + Roshomon consensus, honestly, without claiming DeepSeek synthesis is "
    "Grok output?",
]


def deep_research(*, dry: bool = True, provider: str = "deepseek") -> dict[str, Any]:
    """Route 3 rounds of DeepSeek+Grok deep research through OUR SWARM (3 rounds = 3 questions).
    dry=True = plan ($0); dry=False enqueues to the swarm_worker dedicated queue."""
    from mag import swarm_worker as sw
    out = {"ok": True, "schema": SCHEMA, "dry": dry, "rounds": []}
    for i, q in enumerate(DEEP_GROK_QUESTIONS):
        if dry:
            out["rounds"].append({"round": i + 1, "ok": True, "task_id": None,
                                  "question": q[:60]})
        else:
            try:
                r = sw.enqueue_task(q, provider=provider, model="deepseek-chat",
                                    domain="deep-grok-research", agent_idx=i, tag=f"grok3-{i}")
                out["rounds"].append({"round": i + 1, "ok": bool(r.get("ok")),
                                      "task_id": r.get("task_id"), "question": q[:60]})
            except Exception as e:
                out["rounds"].append({"round": i + 1, "ok": False, "error": str(e)[:100]})
    out["n_rounds"] = len(out["rounds"])
    return out


# ────────────────────── INDEPENDENCE-ADJUSTED GAP MAP (steal 2026-08-11) ───────
# External field-steal (mine/raw/steal_protocol, agentswarm/forecast.ts evidenceOverlap +
# scaleK): the strongest win for this test env is EVIDENCE-OVERLAP-SCALED INDEPENDENCE.
# "Agreement = don't re-pay" is only HONEST if the agreeing witnesses are INDEPENDENT.
# N cheap witnesses pulling from the same source are ~1 opinion, not N. Before declaring a
# probe COVERED (cache hit), reduce the effective witness count by their shared-source/answer
# overlap. Correlated sourcing != independent convergence. Paired with a risk-gated, FAIL-OPEN
# escalation gate (microsoft/conductor `when`-routing + marikarx/subagent-router) and a FRONTIER
# BUDGET HARD-STOP (marikarx budget_hard_stop) so the expensive tier is bounded and gaps that
# can't be escalated are reported honestly, never silently re-paid.
#
# Adapted deterministic + $0 (pure functions, no LLM), per the architecture law (bytes not vibes).

OVERLAP_TAU = 0.6              # pairwise overlap >= this = correlated (not independent)
CONVERGENCE_TAU = 0.5          # divergence below this = converged (covered)
DEFAULT_FRONTIER_BUDGET = 3    # max frontier escalations per run (budget hard-stop)


def _token_overlap(a: str, b: str) -> float:
    """Jaccard-ish token overlap between two witness answer strings (0..1)."""
    def toks(s: str) -> set[str]:
        return set((s or "").lower().split())
    ta, tb = toks(a), toks(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def independent_witnesses(
    answers: list[str],
    *,
    sources: list[list[str]] | None = None,
    tau: float = OVERLAP_TAU,
) -> dict[str, Any]:
    """Effective independent witness count for a probe's cheap answers.

    N witnesses that all pulled from the same source are NOT N independent opinions. We count a
    witness as NEW only if it is not correlated (pairwise source/answer overlap >= tau) with any
    already-counted one. Prefers cited-source overlap when provided (the honest signal); falls back
    to answer token overlap otherwise (still far better than assuming full independence).

    Deterministic + $0. Contract: agreement_is_real iff overlap < tau.
    """
    n = len(answers or [])
    if n == 0:
        return {"n_raw": 0, "n_independent": 0, "mean_overlap": 0.0,
                "correlated": False, "rule": OVERLAP_TAU_RULE}
    ov: list[float] = []
    independent: set[int] = set()
    for i in range(n):
        correlated = False
        for j in independent:
            if sources is not None:
                si = set(sources[i] or [])
                sj = set(sources[j] or [])
                o = (len(si & sj) / len(si | sj)) if (si | sj) else 0.0
            else:
                o = _token_overlap(answers[i], answers[j])
            ov.append(o)
            if o >= tau:
                correlated = True
                break
        if not correlated:
            independent.add(i)
    mean_ov = (sum(ov) / len(ov)) if ov else 0.0
    n_ind = len(independent)
    return {
        "n_raw": n, "n_independent": n_ind,
        "mean_overlap": round(mean_ov, 4),
        "correlated": n_ind < n,
        "rule": OVERLAP_TAU_RULE,
    }


OVERLAP_TAU_RULE = "agreement_is_real iff overlap < tau; correlated sourcing != independent convergence"


def decide_escalation(
    *,
    n_cheap: int,
    n_independent: int,
    divergence_score: float,
    frontier_used: int = 0,
    frontier_budget: int = DEFAULT_FRONTIER_BUDGET,
    convergence_tau: float = CONVERGENCE_TAU,
) -> dict[str, Any]:
    """Pure decision table: route a probe to COVERED ($end) or ESCALATE (frontier).

    Adapted from microsoft/conductor's deterministic `when`-routing + marikarx/subagent-router's
    risk-gated escalation + budget hard-stop. FAIL-OPEN: a cheap grader hiccup never blocks the
    cheap path — if we cannot establish independence, we treat the probe as NOT converged.

    Honest invariants (unrepresentable states are illegal):
      * covered=True with divergence >= tau  -> illegal
      * escalate=True while frontier budget is 0 -> illegal (reported as budget_exhausted)
    """
    # fail-open: no independent cheap witness + cheap witnesses present = cannot trust convergence
    if n_cheap > 0 and n_independent == 0:
        converged = False
    else:
        converged = (n_independent >= 1) and (divergence_score < convergence_tau)

    if frontier_used >= frontier_budget:
        return {"decision": "frontier_budget_exhausted",
                "action": "report_unescaped_gap",
                "converged": converged, "escalate": False,
                "reason": f"frontier budget exhausted ({frontier_used}/{frontier_budget}); "
                          "gap left unescaped — honest report, no silent re-pay"}
    if converged:
        return {"decision": "covered", "action": "end_no_repay",
                "converged": True, "escalate": False,
                "reason": "cheap witnesses converged below divergence tau (overlap-adjusted)"}
    return {"decision": "escalate", "action": "frontier_one_witness",
            "converged": False, "escalate": True,
            "reason": "cheap/frontier divergence (or correlated cheap consensus) needs ONE frontier "
                      "witness"}


def gap_map(
    probes_answers: list[dict[str, Any]],
    *,
    frontier_budget: int = DEFAULT_FRONTIER_BUDGET,
) -> dict[str, Any]:
    """Independence-adjusted gap map for a batch of probes.

    Each entry: {"probe": str, "cheap_answers": [str...], "sources": [[str...]...] | None,
                 "frontier_answer": str | None}. Returns, per probe, the effective independent
    witness count + an escalation decision. Deterministic + $0.
    """
    out: dict[str, Any] = {"schema": "gap_map.v1", "ts": _now(), "entries": [], "frontier_used": 0}
    frontier_used = 0
    for entry in probes_answers or []:
        cheap = entry.get("cheap_answers") or []
        src = entry.get("sources")
        ind = independent_witnesses(cheap, sources=src)
        # divergence_score: cheap-vs-frontier disagreement when a frontier answer is present,
        # else 0 (no frontier -> no cross-tier divergence to measure yet).
        if entry.get("frontier_answer") is not None:
            div = max((_token_overlap(c, entry.get("frontier_answer") or "") for c in cheap),
                      default=1.0)
            divergence_score = 1.0 - div
        else:
            divergence_score = 0.0
        dec = decide_escalation(
            n_cheap=len(cheap), n_independent=ind["n_independent"],
            divergence_score=divergence_score, frontier_used=frontier_used,
            frontier_budget=frontier_budget)
        if dec["escalate"]:
            frontier_used += 1
        out["entries"].append({
            "probe": entry.get("probe"),
            "independence": ind,
            "divergence_score": round(divergence_score, 4),
            "decision": dec,
        })
    out["frontier_used"] = frontier_used
    out["frontier_budget"] = frontier_budget
    out["unescaped_gaps"] = sum(1 for e in out["entries"]
                                if e["decision"]["decision"] == "frontier_budget_exhausted")
    return out


# ────────────────────── PRECISION-GAP STEALS (2026-08-11, operator "word") ────────
# Three lower-value-but-real adaptions from the same field-steal, added on the operator's go.
# All deterministic + $0: they PLAN/SCHEDULE (the swarm executes the actual LLM witnesses).

def localize_gap(cheap_answers: list[str], frontier_answer: str) -> dict[str, Any]:
    """C3 leave-one-out divergence localization: WHICH witness carries the gap.

    Re-measure cheap<->frontier divergence with each cheap witness held out; the witness whose
    removal most changes alignment (max |delta|) is the load-bearing gap. Turns "there's a gap"
    into "the gap rides on this witness's claim". Deterministic + $0.
    """
    if not cheap_answers or not frontier_answer:
        return {"ok": False, "reason": "need non-empty cheap answers + frontier answer"}
    def divergence(answers: list[str]) -> float:
        # MEAN overlap vs frontier = the cheap CONSENSUS position, so a single agreeing witness
        # can't zero out divergence (that's what makes leave-one-out marginal credit meaningful).
        if not answers:
            return 1.0
        ov = [_token_overlap(a, frontier_answer) for a in answers]
        return 1.0 - (sum(ov) / len(ov))
    baseline = divergence(cheap_answers)
    rows = []
    for i in range(len(cheap_answers)):
        reduced = [a for j, a in enumerate(cheap_answers) if j != i]
        d = divergence(reduced)
        rows.append({"removed": i, "answer": cheap_answers[i][:80],
                     "divergence_without": round(d, 4), "delta": round(d - baseline, 4)})
    rows.sort(key=lambda r: -abs(r["delta"]))
    return {"ok": True, "baseline_divergence": round(baseline, 4),
            "gap_witness": rows[0],
            "note": "witness whose removal most changes cheap<->frontier alignment = the gap",
            "rows": rows}


def inverted_probe(probe: str, cheap_consensus: str = "") -> dict[str, Any]:
    """Anti-groupthink (agentswarm inverted-question): a probe that argues the OPPOSITE of the
    emerging cheap consensus so the panel must defend itself. Deterministic scheduling only.
    """
    consensus = cheap_consensus or probe
    return {"ok": True,
            "inverted_task": f"[inverted-probe] Argue the OPPOSITE of the cheap consensus: "
                             f"{consensus[:200]} (original probe: {probe[:200]})",
            "role": "anti-groupthink cheap witness (ONE)",
            "note": "if the inverted witness produces a counter the cheap tier can't refute -> "
                    "treat as divergence -> escalate to frontier"}


def adversarial_verify(cheap_answers: list[str], *, sources: list[list[str]] | None = None) -> dict[str, Any]:
    """Cheap adversarial verifier BEFORE paying frontier (agentswarm verify + subagent-router risk
    gate). One cheap witness attacks the convergent cheap answer; escalate ONLY if it confirms a
    real, uncorrelated divergence. Deterministic: returns coherence + the advisory plan (the actual
    attack witness is spawned by the swarm).
    """
    ind = independent_witnesses(cheap_answers, sources=sources)
    return {"ok": True,
            "coherence": ind["n_independent"] >= 1,
            "n_independent": ind["n_independent"],
            "advisory": "spawn ONE cheap adversarial witness to attack the convergent cheap answer; "
                        "escalate to frontier ONLY if it confirms a real, uncorrelated divergence",
            "cheap_first": True}


def gap_map_precision(probes_answers: list[dict[str, Any]], *, frontier_budget: int = DEFAULT_FRONTIER_BUDGET) -> dict[str, Any]:
    """gap_map + the three precision steals on diverged probes. Deterministic + $0.
    Each entry may add: verify (adversarial advisory), inverted (anti-groupthink plan),
    gap_witness (C3 leave-one-out localization when a frontier answer is present).
    """
    base = gap_map(probes_answers, frontier_budget=frontier_budget)
    for e in base["entries"]:
        raw = next((x for x in probes_answers or [] if x.get("probe") == e["probe"]), None)
        cheap = (raw or {}).get("cheap_answers") or []
        frontier = (raw or {}).get("frontier_answer")
        if e["decision"]["escalate"] or e["decision"]["decision"] == "frontier_budget_exhausted":
            e["verify"] = adversarial_verify(cheap, sources=(raw or {}).get("sources"))
            e["inverted"] = inverted_probe(e["probe"], cheap_consensus="; ".join(cheap)[:200] if cheap else "")
            if frontier:
                loc = localize_gap(cheap, frontier)
                if loc.get("ok"):
                    e["gap_witness"] = loc["gap_witness"]
    return base


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="3-level steal + DeepSeek↔Grok gap experiment to swarms")
    ap.add_argument("cmd", nargs="?", default="status",
                    choices=["steal", "probes", "design", "dispatch", "escalate", "deep-research",
                             "gap-map", "status"])
    ap.add_argument("--dry", action="store_true", default=False, help="plan only ($0); default is REAL dispatch")
    a = ap.parse_args()
    if a.cmd == "steal":
        print(json.dumps(steal(), ensure_ascii=False, indent=2))
    elif a.cmd == "probes":
        print(json.dumps(probes(), ensure_ascii=False, indent=2))
    elif a.cmd == "design":
        print(json.dumps(design(), ensure_ascii=False, indent=2))
    elif a.cmd == "dispatch":
        print(json.dumps(dispatch(dry=a.dry), ensure_ascii=False, indent=2))
    elif a.cmd == "escalate":
        print(json.dumps(escalate(dry=a.dry), ensure_ascii=False, indent=2))
    elif a.cmd == "deep-research":
        print(json.dumps(deep_research(dry=a.dry), ensure_ascii=False, indent=2))
    elif a.cmd == "gap-map":
        # RIB-debug demo with planted correlated witnesses — no real spend.
        demo = [
            {"probe": "p0", "cheap_answers": ["alpha beta gamma", "alpha beta delta", "alpha beta eps"],
             "sources": [["https://a"], ["https://a"], ["https://a"]], "frontier_answer": None},
            {"probe": "p1", "cheap_answers": ["one two", "three four"], "sources": None,
             "frontier_answer": "one two three four five"},
            {"probe": "p2", "cheap_answers": ["x y z"], "sources": None, "frontier_answer": None},
        ]
        print(json.dumps(gap_map(demo), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(status(), ensure_ascii=False, indent=2))
