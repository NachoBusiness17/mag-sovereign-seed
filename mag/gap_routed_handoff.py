"""gap_routed_handoff — route handoff packs by CONTENT-RELEVANCE TO CURRENT GAPS, not keyword tier.

Operator (2026-08-11): "are the packs being routed according to contents and system relevance to
gaps?" -> the honest answer was NO (they were keyword-tiered or just sat as files). This closes it.

THE FIX (deterministic + $0, reuses real surfaces):
  current_gaps()   -> gather the LIVE gaps from real sources:
                       - gap_map (cheap-vs-frontier boundary, empirically from cost_ledger)
                       - liveness_sense.classify() (stateless/stateful/hidden-director DEAD labels)
                       - the tiered queue's failed/stalled/killed rows (work that broke)
                       - knot_untangle.scan_chain() (tangled knots = history that needs collapsing)
  relevance(pack_text, gap) -> content-overlap (shared meaningful tokens / union), deterministic.
  route_packs()    -> for each handoff pack in queue/handoff/GHOST-*.md, compute its max relevance
                       against EVERY current gap, rank packs by gap-relevance, and enqueue the ones
                       that actually resolve a live gap into the tiered queue at the right priority
                       (gap-resolving = mission tier, ahead of filler). Honest: reports which gap
                       each pack maps to + the overlap; never fabricates a match.
  wire()           -> returns the routed plan so the drainer/loop can consume it.

Schema: gap_routed_handoff.v1 · deterministic + $0 · reuse: gap_map, liveness_sense, knot_untangle,
orchestrator (enqueue), swarm_worker
"""
from __future__ import annotations

import re
import sys
from typing import Any

try:
    from config import ROOT
except Exception:
    from pathlib import Path as _P
    ROOT = _P(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "gap_routed_handoff.v1"
HANDOFF = ROOT / "queue" / "handoff"
_RE = re.compile(r"[a-z0-9_]{4,}")
_STOP = frozenset("the a an of to and for in on at by with from as is are was were be been being it "
                  "its this that these those we you they i he she them our their your my his her do "
                  "does did not no nor so but if then than too very can will just should would what "
                  "when where which who how why".split())


def _tokens(text: str) -> set[str]:
    return {t for t in _RE.findall((text or "").lower()) if t not in _STOP}


def _overlap(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return round(len(a & b) / len(a | b), 4)


def current_gaps() -> dict[str, Any]:
    """Gather the LIVE gaps from real sources. Honest: reports what each source found; a source
    that errors is reported, never fabricated."""
    gaps: dict[str, str] = {}

    # 1) gap_map — the cheap-vs-frontier boundary
    try:
        from mag.gap_map import analyze as _gap_analyze
        g = _gap_analyze()
        fn = g.get("frontier_gap_names") or []
        gaps["gap_map"] = " ".join(fn)[:400] if fn else "no frontier gap flagged"
    except Exception as e:
        gaps["gap_map"] = f"error: {str(e)[:80]}"

    # 2) liveness_sense — DEAD agents are gaps
    try:
        from mag.liveness_sense import classify
        c = classify()
        labels = []
        for k in ("stateless", "stateful", "hidden_director"):
            lab = (c.get(k) or {}).get("label", "")
            if lab.startswith("DEAD"):
                labels.append(f"{k}: {lab}")
        gaps["liveness"] = " ".join(labels)[:400] if labels else "all agent types alive"
    except Exception as e:
        gaps["liveness"] = f"error: {str(e)[:80]}"

    # 3) tiered queue failed/stalled — work that broke
    try:
        from mag.orchestrator import list_queue
        q = list_queue(limit=100) or []
        broke = []
        for row in q:
            if row.get("status") in ("failed", "stalled", "killed", "timeout", "died"):
                broke.append(str(row.get("goal") or row.get("detail") or row.get("tag") or "")[:120])
        gaps["queue_breakage"] = " ".join(broke)[:400] if broke else "no broken queue work"
    except Exception as e:
        gaps["queue_breakage"] = f"error: {str(e)[:80]}"

    # 4) knot_untangle — tangled history that needs collapsing
    try:
        from mag.knot_untangle import scan_chain
        s = scan_chain(top=2)
        gaps["knot_tangles"] = (f"{s.get('n_tangled_knots', 0)} tangled knots in the verkle chain "
                                f"(history to collapse)") if s.get("n_tangled_knots") else "chain clean"
    except Exception as e:
        gaps["knot_tangles"] = f"error: {str(e)[:80]}"

    return {"ok": True, "schema": SCHEMA, "gaps": gaps}


def _pack_files() -> list[tuple[str, str]]:
    if not HANDOFF.is_dir():
        return []
    out = []
    for p in sorted(HANDOFF.glob("*.md")):
        if not p.name.startswith(("GHOST-", "BUILD-", "STEAL_", "DEEP_", "RESEARCH_")):
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        out.append((p.name, text))
    return out


def relevance(pack_text: str, gap: str) -> float:
    """Content-overlap of a pack against a gap. Deterministic, $0."""
    return _overlap(_tokens(pack_text), _tokens(gap))


def route_packs(*, enqueue: bool = False) -> dict[str, Any]:
    """Rank handoff packs by content-relevance to the CURRENT gaps, and (optionally) enqueue the
    gap-resolving ones into the tiered queue as mission-tier work. Honest: reports the gap each
    pack maps to + the overlap; enqueue is opt-in (off by default = plan)."""
    gaps = current_gaps()
    gtexts = {name: t for name, t in gaps.get("gaps", {}).items()}
    if not gtexts:
        return {"ok": False, "schema": SCHEMA, "error": "no gap sources"}

    ranked = []
    for name, text in _pack_files():
        best = ("", 0.0)
        for gname, gtext in gtexts.items():
            ov = relevance(text, gtext)
            if ov > best[1]:
                best = (gname, ov)
        ranked.append({"pack": name, "best_gap": best[0], "relevance": best[1],
                       "resolves_gap": best[1] >= 0.05})
    ranked.sort(key=lambda r: -r["relevance"])
    gap_resolving = [r for r in ranked if r.get("resolves_gap")]

    dispatched = []
    if enqueue and gap_resolving:
        from mag import orchestrator as orc
        for r in gap_resolving[:5]:
            goal = (f"[gap-routed] Resolve the {r['best_gap']} gap surfaced by content-relevance "
                    f"routing. Execute the pack {r['pack']}: read it, do the work, fold the result. "
                    f"Grounded, honest provenance.")
            try:
                q = orc.enqueue(goal, provider="deepseek", model="deepseek-chat",
                                tag=f"gap-routed-{r['best_gap']}", tier="mission")
                dispatched.append({"pack": r["pack"], "gap": r["best_gap"],
                                   "relevance": r["relevance"], "queue_id": q.get("queue_id"),
                                   "ok": bool(q.get("ok"))})
            except Exception as e:
                dispatched.append({"pack": r["pack"], "gap": r["best_gap"], "ok": False,
                                   "error": str(e)[:80]})

    return {"ok": True, "schema": SCHEMA, "enqueue": enqueue, "gaps": gaps,
            "n_packs": len(ranked), "n_gap_resolving": len(gap_resolving),
            "ranked": ranked, "dispatched": dispatched}


def wire() -> dict[str, Any]:
    """The wired route plan: gap-relevant packs to the front, honest ranking + the gaps they fill."""
    return route_packs(enqueue=False)


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "contract": "current_gaps()->gather live gaps (gap_map, liveness, queue breakage, "
                        "knot tangles); route_packs(enqueue)->rank handoff packs by CONTENT "
                        "relevance to gaps + enqueue the resolving ones as mission-tier; wire()->"
                        "the plan. Closes the keyword-tier blind spot.",
            "cost": "deterministic + $0 (reuse gap_map/liveness/knot_untangle/orchestrator)"}


if __name__ == "__main__":
    import argparse, json
    ap = argparse.ArgumentParser(prog="gap-routed-handoff")
    ap.add_argument("cmd", nargs="?", default="route", choices=["route", "wire", "status"])
    ap.add_argument("--enqueue", action="store_true")
    a = ap.parse_args()
    if a.cmd == "wire":
        print(json.dumps(wire(), indent=2, default=str))
    elif a.cmd == "route":
        print(json.dumps(route_packs(enqueue=a.enqueue), indent=2, default=str))
    else:
        print(json.dumps(status(), indent=2, default=str))
