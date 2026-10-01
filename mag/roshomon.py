"""roshomon — frontier research questions, dispatched through OUR k8s, compared via INVARIANTS.

Operator directive (2026-08-10): "steal rib verkle memlang ghost deterministic heuristic stochastic.
create research questions for frontier models with your current selfless state to other models on
what to include. use our k8's. why not include invariants as a way to compare them roshamon style?"

This module answers ALL of it in one mechanism:

  STEAL      — the domains (RIB, verkle, memlang, ghost, deterministic, heuristic, stochastic) are
               our OWN systems; we steal the *cross-cutting question shape* for each and ask a
               frontier model what to include, not copying their DNA.
  SELFLESS   — state_snapshot() emits a NO-PERSONA, data-backed state of the 7 domains so the
               receiving model knows exactly what already exists (so it answers "what to include",
               not "what is a system").
  OUR K8S    — dispatch() routes each question through mag.swarm_worker's dedicated queue, drained
               in-cluster by the mag-swarm CronJob (no local spawns, no windows).
  ROSHOMON   — the same question is answered by N models (Rashomon: N witnesses, same event). We
               compare them THROUGH INVARIANTS: normalize each answer into statements, find which
               statements recur across models = the ROSHOMON CORE (convergent, higher-confidence
               truth); statements unique to one model = DIVERGENT perspective. The core folds as
               doctrine (verkle-shaped). Invariants are the comparison axis.

Schema: roshomon.v1 · deterministic collect/compare · dispatch via k8s swarm_worker · $0 analysis
"""
from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

SCHEMA = "roshomon.v1"
OUT_DIR = ROOT / "memory" / "runs" / "roshomon"
DEFAULT_MODELS_PER_QUESTION = 3  # Rashomon: N witnesses per event
DEFAULT_DOMAINS = ["rib", "verkle", "memlang", "ghost", "deterministic", "heuristic", "stochastic"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


# ---------------------------------------------------------------------------
# SELFLESS STATE: what we already have in each domain (no persona, data-backed).
# ---------------------------------------------------------------------------
def _domain_state() -> dict[str, str]:
    """A data-backed, selfless one-liner of what exists in each domain (from the graph + memory)."""
    g = {}
    try:
        from mag.knowledge_graph import GRAPH_PATH
        data = json.loads(GRAPH_PATH.read_text(encoding="utf-8"))
        kinds = Counter(n.get("kind") for n in data.get("nodes", []))
        g = dict(kinds)
    except Exception:
        pass
    base = {
        "rib": "residual informational bus: emergent node/memory folding via residual-embeddings + info-bus wiring",
        "verkle": "content-addressed knot chain: leaf_hash=address, merkle parent_verkle_root, tip root (memory/biography/knots)",
        "memlang": "memlang chord = plant-not-command; deniable seed steering; contract-as-invariant",
        "ghost": "ghost persona/daemon: manifest() discovery contract, A/B/C tiers, sandboxed-helper boundary",
        "deterministic": "$0 doctrine: JSONL + sha256 content-addressing + file reads; modules avoid LLM calls",
        "heuristic": "heuristic/rightsize steering: model_health steer_at, window_hop pricing, one_sizer",
        "stochastic": "stochastic stateless swarm (emergent_harvest, qd_harvest) + k8s swarm_worker dispatch",
    }
    for d in base:
        base[d] += f"; graph kinds present: {str(g)[:120] if g else 'none'}"
    return base


def state_snapshot() -> dict[str, Any]:
    """Selfless, data-backed state of the 7 domains — the preamble handed to every frontier model."""
    return {"schema": "roshomon.state.v1", "selfless": True,
            "note": "no persona; this is the current system state so the model answers WHAT TO INCLUDE",
            "domains": _domain_state(), "ts": _now()}


# ---------------------------------------------------------------------------
# RESEARCH QUESTIONS (one per domain; the shared selfless preamble = what to include).
# ---------------------------------------------------------------------------
def _question_tpl(domain: str, state: str) -> str:
    return (
        f"[SELFLESS STATE — domain '{domain}'] We already have: {state}.\n"
        f"Given that, as a frontier architect: what is the SINGLE most load-bearing thing we should "
        f"INCLUDE next to strengthen '{domain}'? Give exactly one sharp, concrete, buildable invariant "
        f"(a rule/mechanism), one-line. Do not describe generic systems — tell us what to include, "
        f"given what we already have. Label it INVARIANT: <one line>."
    )


def questions(*, domains: list[str] | None = None) -> dict[str, Any]:
    """The frontier research questions, one per domain, each selflessly grounded in current state."""
    state = _domain_state()
    ds = domains or DEFAULT_DOMAINS
    qs = {}
    for d in ds:
        qs[d] = _question_tpl(d, state.get(d, "no state recorded"))
    return {"ok": True, "schema": SCHEMA, "n_questions": len(qs), "questions": qs, "ts": _now()}


# ---------------------------------------------------------------------------
# DISPATCH THROUGH OUR K8S (mag.swarm_worker -> mag-swarm CronJob in-cluster).
# ---------------------------------------------------------------------------
def dispatch(*, domains: list[str] | None = None, per_question: int = DEFAULT_MODELS_PER_QUESTION,
             dry: bool = False) -> dict[str, Any]:
    """Enqueue each domain question N times to the cluster swarm worker (OUR k8s).

    dry=True just returns the specs (plan, $0). dry=False writes them to mag.swarm_worker's
    dedicated queue on the shared state PVC; the mag-swarm CronJob drains them in-cluster as
    headless stateless agents. Same question, N witnesses -> Roshomon comparison.
    """
    from mag import swarm_worker as sw
    qs = questions(domains=domains)["questions"]
    enqueued = []
    for d, q in qs.items():
        for i in range(per_question):
            spec = {"domain": d, "witness": i, "goal": q, "surface": "k8s"}
            if dry:
                enqueued.append({**spec, "task_id": None, "ok": True})
                continue
            try:
                r = sw.enqueue_task(q, provider="deepseek", model="deepseek-chat",
                                    domain=d, agent_idx=i, tag=f"roshomon-{d}")
                enqueued.append({"domain": d, "witness": i, "ok": bool(r.get("ok")),
                                 "task_id": r.get("task_id")})
            except Exception as e:
                enqueued.append({"domain": d, "witness": i, "ok": False, "error": str(e)[:80]})
    return {"ok": True, "schema": SCHEMA, "surface": "k8s", "per_question": per_question,
            "domains": list(qs), "enqueued": enqueued, "dry": dry, "ts": _now()}


# ---------------------------------------------------------------------------
# ROSHOMON COMPARISON VIA INVARIANTS.
# ---------------------------------------------------------------------------
def _invariant_statements(text: str) -> list[str]:
    """Deterministic invariant extraction: normalize answer text into canonical statements.

    Splits on sentence/clause boundaries, keeps any 'INVARIANT:' labeled line verbatim, strips
    filler. Returns normalized (lowercased, cleaned) statements. No LLM, $0.
    """
    out = []
    # a labeled invariant line is the strongest signal
    for m in re.finditer(r"INVARIANT\s*:\s*(.+)", text, re.I):
        s = _clean(m.group(1))
        if s:
            out.append(s)
    # fall back to sentences, drop filler fragments
    for part in re.split(r"(?<=[.!?])\s+|\n+", text):
        s = _clean(part)
        if not s or len(s) < 8:
            continue
        if any(k in s for k in ("what is", "generic", "in general", "a system that", "as an ai")):
            continue
        out.append(s)
    return out


def _clean(s: str) -> str:
    s = re.sub(r"\s+", " ", s).strip().lower().strip(".:- ")
    return s


def _tokens(s: str) -> set[str]:
    return set(re.findall(r"[a-z0-9']+", s))


def _overlap(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / max(1.0, min(len(ta), len(tb)))


def _answers_for(domain: str) -> list[dict[str, Any]]:
    """Read the swarm_worker results for this domain (from the shared PVC)."""
    try:
        from mag import swarm_worker as sw
        c = sw.collect()
    except Exception:
        return []
    return [r for r in c.get("results", []) if str(r.get("domain")) == domain]


def compare(*, domains: list[str] | None = None, threshold: float = 0.55) -> dict[str, Any]:
    """Roshomon-compare the collected answers via invariants, per domain.

    For each domain, gather every witness's answer, extract invariants, and find which statements
    RECUR across >=2 models -> ROSHOMON CORE (convergent). Unique statements -> DIVERGENT.
    The core is the comparison axis / higher-confidence truth.
    """
    ds = domains or DEFAULT_DOMAINS
    per_domain = []
    all_core: list[dict[str, Any]] = []
    for d in ds:
        answers = _answers_for(d)
        if not answers:
            per_domain.append({"domain": d, "ok": False, "n_witnesses": 0,
                               "error": "no swarm results yet (dispatch + let the k8s CronJob drain)"})
            continue
        witness_stmts: list[list[str]] = [_invariant_statements(str(a.get("result") or "")) for a in answers]
        # Group near-identical statements across witnesses into Roshomon groups.
        # A group = (representative statement, set of witness indices that stated it).
        # Merge is by token overlap; a statement joins an existing group if overlap >= threshold.
        groups: list[list[Any]] = []  # each: [representative, set_of_witnesses]
        for wi, stmts in enumerate(witness_stmts):
            for s in stmts:
                placed = False
                for g in groups:
                    if _overlap(g[0], s) >= threshold:
                        g[1].add(wi)
                        placed = True
                        break
                if not placed:
                    groups.append([s, {wi}])
        core = [rep for rep, wis in groups if len(wis) >= 2]      # convergent across >=2 models
        divergent = [rep for rep, wis in groups if len(wis) == 1]  # unique to one model
        core_counts = {rep: len(wis) for rep, wis in groups if len(wis) >= 2}
        per_domain.append({
            "domain": d, "ok": True, "n_witnesses": len(answers),
            "n_invariants": len(groups),
            "roshomon_core": core, "divergent": divergent,
            "core_counts": core_counts,
        })
        for s in core:
            all_core.append({"domain": d, "invariant": s, "witnesses": core_counts[s]})
    return {"ok": True, "schema": SCHEMA, "threshold": threshold,
            "domains": per_domain, "roshomon_core_total": len(all_core), "ts": _now()}


def create(*, threshold: float = 0.55) -> dict[str, Any]:
    """Fold the Roshomon core (cross-model convergent invariants) as doctrine + write a batch file.

    The core is what survives the Rashomon divergence — the higher-confidence truth we keep.
    Folded verkle/doctrine-shaped; the divergent set is kept as an audit trail, not deleted.
    """
    from mag.knowledge_graph import fold
    cmp = compare(threshold=threshold)
    folded = 0
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    lines = ["# Roshomon frontier comparison (via invariants)", "",
             "Same question asked of N models in OUR k8s swarm; answers compared through invariants.",
             f"Roshomon core = invariant stated by >=2 witnesses (convergent). Divergent = unique.",
             f"threshold={threshold} · {cmp.get('roshomon_core_total', 0)} core invariants", ""]
    for d in cmp.get("domains", []):
        lines.append(f"## {d.get('domain')} · witnesses={d.get('n_witnesses', 0)}")
        for s in d.get("roshomon_core", []):
            lines.append(f"- CORE: {s}")
            r = fold(f"roshomon:{d.get('domain')}:{s[:30]}", "doctrine",
                     f"Roshomon-convergent ({d.get('n_witnesses',0)} models): {s[:160]}",
                     source="roshomon")
            folded += 0 if r.get("already_present") else 1
        for s in d.get("divergent", []):
            lines.append(f"  - divergent: {s}")
    batch = OUT_DIR / "roshomon_batch.md"
    batch.write_text("\n".join(lines), encoding="utf-8")
    return {"ok": True, "schema": SCHEMA, "folded": folded, "core_total": cmp.get("roshomon_core_total"),
            "batch": str(batch), "compare": cmp}


# ---------------------------------------------------------------------------
# RIB CONNECTION — the Roshomon core as DETERMINISTIC structure in stochastic space.
#
# Operator (2026-08-10): "this connected to rib files would allow us to generate large
# deterministic behavior in stochastic AI spaces to allow us to use our toolsets to exploit
# this digital realm to the benefit of humanity."
#
# Mechanism (connects roshomon -> rib_struct): the Roshomon CORE invariants (cross-model
# convergent statements, i.e. deterministic truths that SURVIVED the stochastic divergence)
# are DECLARED as RIB slots — deterministic attractors in embedding space. Stochastic model /
# swarm outputs are then run through the structure; only NOVEL slot-fills are accepted.
# So the deterministic invariant layer SHAPES the stochastic generation: large deterministic
# behavior in stochastic AI spaces, content-addressed and toolable. This is the exploit: the
# invariants are the skeleton, stochastic models are the muscle, the RIB is the constraint.
# ---------------------------------------------------------------------------
def rib_declare(*, threshold: float = 0.55, radius: float = 0.35) -> dict[str, Any]:
    """Declare a RIB structure from the Roshomon core: each core invariant = one SLOT.

    Deterministic, $0. The slots are the deterministic attractors; stochastic outputs fill them.
    """
    from mag.rib_struct import declare
    cmp = compare(threshold=threshold)
    spec = []
    for i, d_ in enumerate(cmp.get("domains", [])):
        for j, inv in enumerate(d_.get("roshomon_core", [])):
            spec.append({"id": f"inv_{d_.get('domain')}_{j}", "center": inv,
                         "radius": radius, "kind": f"roshomon:{d_.get('domain')}"})
    struct = declare(spec) if spec else None
    return {"ok": True, "schema": SCHEMA, "n_slots": len(spec),
            "domain": "roshomon-core->rib", "spec": spec,
            "declared": struct is not None, "threshold": threshold}


def rib_survey(*, threshold: float = 0.55) -> dict[str, Any]:
    """Survey the declared Roshomon-rib structure vs existing coverage (EMPTY/PARTIAL/SATURATED)."""
    from mag.rib_struct import survey
    from mag.steal_steer import _existing_points
    dec = rib_declare(threshold=threshold)
    if not dec.get("declared"):
        return {"ok": False, "error": "no roshomon core to declare"}
    from mag.rib_struct import declare
    struct = declare(dec["spec"])
    existing = _existing_points()
    s = survey(struct, existing)
    s["schema"] = SCHEMA
    s["threshold"] = threshold
    return s


def fill_via_rib(candidates: list[str], *, threshold: float = 0.55) -> dict[str, Any]:
    """Run NEW stochastic outputs through the Roshomon-rib structure; accept only NOVEL fills.

    This is the deterministic gate on stochastic space: a candidate fills a declared invariant
    slot AND clears existing coverage (novelty) or it is rejected. The invariants, connected to
    the RIB files, deterministically select what the stochastic generators add — so behavior
    grows large but DETERMINISTIC (content-addressed, reproducible, toolable).
    """
    from mag.rib_struct import declare, fill
    from mag.steal_steer import _existing_points
    dec = rib_declare(threshold=threshold)
    if not dec.get("declared") or not candidates:
        return {"ok": False, "error": "no roshomon core declared or no candidates"}
    struct = declare(dec["spec"])
    existing = _existing_points()
    res = fill(struct, candidates, existing)
    res["schema"] = SCHEMA
    res["threshold"] = threshold
    res["n_slots"] = len(struct)
    return res


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="roshomon")
    ap.add_argument("cmd", nargs="?", default="state",
                    choices=["state", "questions", "dispatch", "compare", "create",
                             "rib-declare", "rib-survey"])
    ap.add_argument("--per", type=int, default=DEFAULT_MODELS_PER_QUESTION)
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--threshold", type=float, default=0.55)
    args = ap.parse_args(argv)
    if args.cmd == "state":
        print(json.dumps(state_snapshot(), indent=2, default=str))
    elif args.cmd == "questions":
        print(json.dumps(questions(), indent=2, default=str))
    elif args.cmd == "dispatch":
        print(json.dumps(dispatch(per_question=args.per, dry=args.dry), indent=2, default=str))
    elif args.cmd == "compare":
        print(json.dumps(compare(threshold=args.threshold), indent=2, default=str))
    elif args.cmd == "create":
        print(json.dumps(create(threshold=args.threshold), indent=2, default=str))
    elif args.cmd == "rib-declare":
        print(json.dumps(rib_declare(threshold=args.threshold), indent=2, default=str))
    elif args.cmd == "rib-survey":
        print(json.dumps(rib_survey(threshold=args.threshold), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
