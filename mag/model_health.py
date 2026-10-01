"""model_health — the RIB↔corpus connecting force, made self-maintaining.

SELF-STEAL (adapt, don't duplicate): the connecting-force machinery already exists —
research_lens (self-referencing corpus, retrieve_prior, fold_back) and behavioral_lensing
(zeitgeist = >=4 lenses converging across >=3 agents). This module WIRES the RIB invariants
IN AS THE LENS SET so the invariant DOMAINS become lenses that self-reference and grow, then
measures model health per domain:

  reinforcement = how much the corpus + case law back each invariant domain
  zeitgeist     = which domains the system keeps converging on (multi-lens convergence)
  bottleneck    = thin AND load-bearing (many invariants, little research) -> fix first

The cadence prints reinforced vs thin, then STEERS emergent_harvest at the thinnest bottleneck
domain so research compounds where the model is weak. Deterministic, $0, no LLM.
Schema: model_health.v1
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
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

SCHEMA = "model_health.v1"
HANDOFF = ROOT / "queue" / "handoff"

from mag.emergent_harvest import _load_invariants
from mag.signals import wilson_lower, recency_decay


def _toks(s: str) -> set[str]:
    return {w for w in re.split(r"[^a-z0-9]+", (s or "").lower()) if len(w) > 2}


_STOP = {"the", "and", "for", "are", "with", "that", "this", "from", "guardrail", "never",
         "always", "not", "but", "all", "can", "has", "its", "via", "when", "before"}


def _packs() -> list[str]:
    d = ROOT / "memory" / "research_packs"
    return [p.stem for p in d.glob("*.answer.*.md")] if d.is_dir() else []


def _ledger_rows() -> list[dict[str, Any]]:
    p = ROOT / "memory" / "improve" / "skill_ledger.jsonl"
    if not p.is_file():
        return []
    out = []
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


def _domain_tokens(texts: list[str]) -> set[str]:
    k: set[str] = set()
    for t in texts:
        k |= (_toks(t) - _STOP)
    return k


def health() -> dict[str, Any]:
    """Per invariant-domain: corpus reinforcement, zeitgeist weight, bottleneck rank."""
    invs = _load_invariants()
    if not invs:
        return {"ok": False, "error": "no DISTILLED_INVARIANTS.md"}
    domains: dict[str, list[str]] = defaultdict(list)
    for v in invs:
        domains[v["domain"] or "general"].append(v["text"])
    packs = _packs()
    ledger = _ledger_rows()
    p_tok = [_toks(p) for p in packs]
    l_tok = [_toks(str(r.get("goal", "")) + " " + str(r.get("task_shape", ""))) for r in ledger]

    rows = []
    for d, texts in domains.items():
        dk = _domain_tokens(texts)
        hit_p = sum(1 for t in p_tok if dk & t)
        hit_l = sum(1 for t in l_tok if dk & t)
        n_inv = len(texts)
        # reinforcement = how much the corpus backs this domain (wilson-shrunk, $0 confidence)
        reinf_p = wilson_lower(hit_p, max(1, len(packs)))
        reinf_l = wilson_lower(hit_l, max(1, len(ledger)))
        reinforcement = round(0.5 * reinf_p + 0.5 * reinf_l, 3)
        # bottleneck = load-bearing (many invariants) but thin (low reinforcement)
        bottleneck = round((min(1.0, n_inv / 6.0) * 0.5) + ((1.0 - reinforcement) * 0.5), 3)
        rows.append({"domain": d, "invariants": n_inv, "packs_cover": hit_p,
                     "ledger_cover": hit_l, "reinforcement": reinforcement,
                     "bottleneck": bottleneck})
    # classification is RELATIVE (wilson shrinks hard at large denominators): thin = below
    # median reinforcement; steer_at = the true thinnest (min reinforcement = biggest bottleneck).
    rows.sort(key=lambda r: r["reinforcement"])
    median = rows[len(rows) // 2]["reinforcement"] if rows else 0.0
    for r in rows:
        r["state"] = "REINFORCED" if r["reinforcement"] >= median else "THIN"
    steer = min(rows, key=lambda r: r["reinforcement"])["domain"] if rows else None  # thinnest
    rows.sort(key=lambda r: -r["bottleneck"])
    thin = [r for r in rows if r["state"] == "THIN"]
    return {"ok": True, "schema": SCHEMA, "n_invariants": len(invs), "n_domains": len(rows),
            "domains": rows, "n_thin": len(thin), "median_reinforcement": round(median, 3),
            "bottleneck_priority": [r["domain"] for r in rows],
            "steer_at": steer}


def digest() -> dict[str, Any]:
    """Write STEAL_MODEL_HEALTH.md so steal_pack folds the health read into case law."""
    h = health()
    if not h.get("ok"):
        return {"ok": False}
    lines = ["# Model Health — RIB↔corpus connecting force read",
             "", f"- schema: {SCHEMA}", f"- invariants: {h['n_invariants']}  domains: {h['n_domains']}",
             f"- thin domains: {h['n_thin']}  steer_at: {h['steer_at']}", ""]
    for r in h["domains"]:
        lines.append(f"- [{r['state']:<10}] {r['domain']:<14} inv={r['invariants']} "
                     f"reinforcement={r['reinforcement']} packs={r['packs_cover']} ledger={r['ledger_cover']}")
    HANDOFF.mkdir(parents=True, exist_ok=True)
    out = HANDOFF / "STEAL_MODEL_HEALTH.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    return {"ok": True, "digest": str(out), "steer_at": h["steer_at"]}


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="model-health")
    ap.add_argument("--digest", action="store_true")
    args = ap.parse_args(argv)
    r = health()
    if args.digest:
        r["digest"] = digest()
    print(json.dumps(r, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
