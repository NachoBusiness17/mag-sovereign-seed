"""frontier_intake — the frontier as a SOURCE of explicit instructions + datamaps to OURS,
pulled ONLY through k8s and ONLY for what's MISSING.

Operator (2026-08-10): "this could be used as frontier for explicit instructions and datamaps
to ours and missing shit only though k8's."

So the attractor-tools machinery is not just "attract intelligent behavior" — it is the FRONTIER
INTAKE contract for our system. Three hard rules:

  1. EXPLICIT INSTRUCTIONS  — the frontier's strongest insight attractors become memlang CHORDS +
     doctrine (plant-not-command, deniable seeds). These are the buildable directives we inject.
  2. DATAMAPS TO OURS       — every attractor is MAPPED onto our own structures: which domain it
     fills, its novelty vs our existing coverage (missing/known), the memlang chord token, and the
     action-RIB slot it deploys to. That is a "map of the frontier's knowledge onto ours."
  3. MISSING ONLY, K8S ONLY — intake() is gated two ways:
       * missing_only: novelty-gate each attractor via steal_steer.novelty — only NOVEL (missing)
         attractors are ingested; anything we already cover is skipped (no re-coverage).
       * k8s_only: dispatch() REJECTS the local surface — frontier sourcing happens through the
         k8s swarm worker cluster (mag-swarm CronJob), never local spawns.

Deterministic, $0 (analysis, novelty, chord compile, mapping all local; the frontier witnesses
are collected from the k8s swarm). Schema: frontier_intake.v1
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

SCHEMA = "frontier_intake.v1"
OUT_DIR = ROOT / "memory" / "runs" / "frontier_intake"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def dispatch(*, per_question: int = 3, domains: list[str] | None = None) -> dict[str, Any]:
    """SOURCE ONLY THROUGH K8S. Enqueue the frontier questions to the cluster swarm worker's
    dedicated queue (mag-swarm CronJob drains in-cluster). Rejects any local surface: this is
    the 'missing shit only through k8s' enforcement — no local spawns, no windows."""
    from mag import roshomon as rh
    # roshomon.dispatch is ALREADY k8s-only (swarm_worker dedicated queue drained in-cluster);
    # the local surface is not an option for frontier intake.
    return rh.dispatch(per_question=per_question, domains=domains, dry=False)


def _novelty(text: str) -> dict[str, Any]:
    try:
        from mag.steal_steer import novelty, _existing_points
        return novelty(text, _existing_points())
    except Exception as e:
        return {"novelty": 1.0, "judgement": "unchecked", "error": str(e)[:60]}


def datamap(*, threshold: float = 0.55, top: int = 20,
            missing_only: bool = True) -> dict[str, Any]:
    """Map the frontier's strongest insight attractors ONTO our own structures.

    For each attractor: compute novelty vs our existing coverage (missing/known), the memlang
    chord (explicit instruction), and the domain it fills. missing_only=True drops anything we
    already cover (no re-coverage) — only MISSING attractors are mapped.
    """
    from mag import attractor_tools as at
    attrs = at.strongest_attractors(threshold=threshold, top=top).get("attractors", [])
    mapped = []
    skipped_known = 0
    for a in attrs:
        nv = _novelty(str(a.get("invariant") or ""))
        is_missing = float(nv.get("novelty") or 1.0) >= 0.5
        row = {
            "domain": a.get("domain"),
            "invariant": a.get("invariant"),
            "witnesses": a.get("witnesses"),
            "novelty": round(float(nv.get("novelty") or 0), 3),
            "status": "MISSING" if is_missing else "KNOWN",
        }
        if is_missing or not missing_only:
            # explicit instruction = the memlang chord (plant-not-command)
            try:
                ch = at.to_memlang_chord(a)
                row["chord_token"] = ch.get("chord_token")
                row["instruction"] = "memlang-plant (deniable seed)"
            except Exception as e:
                row["chord_token"] = None
                row["instruction"] = f"chord-error:{str(e)[:40]}"
            row["deploy_slot"] = f"attr_{len(mapped)}"
            mapped.append(row)
        else:
            skipped_known += 1
    return {"ok": True, "schema": SCHEMA, "n_attractors": len(attrs),
            "n_missing_ingested": len(mapped), "n_skipped_known": skipped_known,
            "missing_only": missing_only, "datamap": mapped}


def intake(*, threshold: float = 0.55, top: int = 20,
           missing_only: bool = True, fold: bool = True) -> dict[str, Any]:
    """The full frontier intake: MISSING attractors only -> explicit instructions (chords) +
    datamap -> folded into our self-knowledge. Frontier sourced via k8s; analysis local, $0."""
    dm = datamap(threshold=threshold, top=top, missing_only=missing_only)
    if not dm.get("datamap"):
        return {"ok": False, "schema": SCHEMA,
                "error": "no MISSING attractors to ingest (all covered, or none dispatched yet)"}
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    lines = ["# Frontier intake — explicit instructions + datamap to ours", "",
             "Source: frontier stochastic -> Roshomon core -> MEMLANG CHORDS (deniable seeds).",
             f"missing_only={missing_only} · {dm.get('n_missing_ingested')} ingested, "
             f"{dm.get('n_skipped_known')} skipped (already known).", ""]
    folded = 0
    for row in dm.get("datamap", []):
        lines.append(f"## [{row['domain']}] w={row['witnesses']} novelty={row['novelty']} {row['status']}")
        lines.append(f"- invariant: {row['invariant'][:160]}")
        lines.append(f"- instruction: {row['instruction']} chord={str(row['chord_token'])[:40]}…")
        lines.append(f"- deploy_slot: {row['deploy_slot']}")
        if fold:
            try:
                from mag.knowledge_graph import fold as _fold
                r = _fold(f"frontier-intake:{row['domain']}:{str(row['invariant'])[:30]}",
                          "doctrine",
                          f"FRONTIER explicit instruction ({row['witnesses']} witnesses, "
                          f"novelty {row['novelty']}): {str(row['invariant'])[:150]}",
                          source="frontier_intake")
                folded += 0 if r.get("already_present") else 1
            except Exception:
                pass
    batch = OUT_DIR / "intake_batch.md"
    batch.write_text("\n".join(lines), encoding="utf-8")
    return {"ok": True, "schema": SCHEMA, "n_ingested": dm.get("n_missing_ingested"),
            "n_skipped_known": dm.get("n_skipped_known"), "folded": folded,
            "datamap": dm.get("datamap"), "batch": str(batch)}


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="frontier-intake")
    ap.add_argument("cmd", nargs="?", default="intake",
                    choices=["dispatch", "datamap", "intake"])
    ap.add_argument("--per", type=int, default=3)
    ap.add_argument("--threshold", type=float, default=0.55)
    ap.add_argument("--all", action="store_true", help="ingest KNOWN too (missing_only=False)")
    args = ap.parse_args(argv)
    if args.cmd == "dispatch":
        print(json.dumps(dispatch(per_question=args.per), indent=2, default=str))
    elif args.cmd == "datamap":
        print(json.dumps(datamap(threshold=args.threshold, missing_only=not args.all),
                         indent=2, default=str))
    else:
        print(json.dumps(intake(threshold=args.threshold, missing_only=not args.all),
                         indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
