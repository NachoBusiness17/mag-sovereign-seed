"""throughput_model — bare-metal, deterministic throughput + ETA model for the moonshot.

OPERATOR (2026-08-12): "if we put all resources to this and kept side tasks running on a small
swarm what throughput against a deterministic estimate against a wowhead/turtlewow codebase ingest
to manifestation of our own self-stolen system? how do we moon shot that" + "baremetal selfsteal".

SELF-STEAL (nothing invented — reuses our own measured + module machinery):
  * grounded bill numbers (2026-08-12): warm ~$0.0012/req, 98% cache, ~333-417 req/hr at $0.50 cap
    (swarm-capacity memory); free stack (GPU/ollama/k3s) rides free alongside.
  * time_estimate.estimate(goal,n,provider) -> work -> wall-clock ETA (the speed model).
  * cost_ledger.task_estimate  -> WORK (tokens).
  * swarm_rightsize.rightsize  -> concurrency N (the real speed control).
  * corpus_ingest dedup-by-invariant -> the ingest value (volume cheap, diversity is the self).

THE MODEL (deterministic + $0, honest: estimates are labeled, measured facts are not):
  capacity(provider, cap_usd_hr)        -> req/hr + swarm-batches/hr at a spend cap (measured base).
  split_resources(all_cap, side_cap)    -> ALL-in main moonshot vs small side swarm.
  ingest_estimate(n_total, dedup_ratio) -> unique invariants + deterministic file-walk ETA.
  manifest_estimate(n_tasks, n)         -> build tasks -> work -> ETA (time_estimate).
  moonshot_estimate(...)                -> the full WoW/Turtle ingest->manifestation estimate.

Schema: throughput_model.v1
"""
from __future__ import annotations

import sys
from typing import Any

try:
    from config import ROOT
except Exception:
    from pathlib import Path as _P
    ROOT = _P(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "throughput_model.v1"

# GROUNDED constants (from the 2026-08-12 bill / swarm-capacity memory) — measured, not invented.
WARM_COST_PER_REQ_USD = 0.0012   # deepseek-v4-flash warm prefix, real bill (H2: 0.00120)
WARM_CACHE_HIT = 0.98            # measured cache-hit ratio
FALLBACK_TPS = 30.0              # time_estimate fallback (no measured latency yet)
DRAIN_CADENCE_S = 120.0          # worker poll interval (additive)

# Conservative, LABELED estimate of the ingest target (WoWHead/Turtle WoW scale).
# Re-verify against the real export when ingested; never presented as measured.
WOW_RECORDS = 1_000_000          # WoWHead DB records (items/spells/quests/NPCs) — labeled estimate
WOW_CODE_LOC = 2_000_000         # Turtle WoW (TrinityCore) server LOC — labeled estimate
WOW_DEDUP_RATIO = 0.75           # labeled estimate of redundancy removed by content-hash dedupe


def capacity(*, provider: str = "deepseek", cap_usd_hr: float = 0.50,
             free_stack: bool = True) -> dict[str, Any]:
    """req/hr + swarm-batches/hr at a spend cap, grounded on the real warm-prefix cost/req.
    The FREE stack (GPU/ollama/k3s) rides alongside at $0, so it multiplies real throughput."""
    req_per_hr = cap_usd_hr / WARM_COST_PER_REQ_USD if WARM_COST_PER_REQ_USD else 0.0
    batch8 = req_per_hr / 8.0       # 8-worker swarm-batches/hr
    batch20 = req_per_hr / 20.0     # 20-req batch/hr
    return {"ok": True, "schema": SCHEMA, "provider": provider, "cap_usd_hr": cap_usd_hr,
            "req_per_hr": round(req_per_hr), "swarm_batches_8w_hr": round(batch8, 1),
            "swarm_batches_20r_hr": round(batch20, 1),
            "free_stack": "GPU/ollama/k3s ride free alongside (multiplier)" if free_stack else "none",
            "base": f"grounded: ${WARM_COST_PER_REQ_USD:.4f}/req warm, {WARM_CACHE_HIT*100:.0f}% cache-hit"}


def split_resources(*, all_cap_usd_hr: float = 0.50, side_cap_usd_hr: float = 0.05) -> dict[str, Any]:
    """Split ALL-in main moonshot vs a SMALL side swarm. Grounded from capacity()."""
    main = capacity(cap_usd_hr=all_cap_usd_hr)
    side = capacity(cap_usd_hr=side_cap_usd_hr)
    return {"ok": True, "schema": SCHEMA,
            "main": {"cap_usd_hr": all_cap_usd_hr, "req_hr": main["req_per_hr"],
                     "batches_8w_hr": main["swarm_batches_8w_hr"]},
            "side": {"cap_usd_hr": side_cap_usd_hr, "req_hr": side["req_per_hr"],
                     "batches_8w_hr": side["swarm_batches_8w_hr"]},
            "note": "side swarm keeps loops alive (render/steer/cold-start) while main moonshots"}


def ingest_estimate(*, n_total: int = WOW_RECORDS, dedup_ratio: float = WOW_DEDUP_RATIO,
                    bytes_per_record: int = 2048) -> dict[str, Any]:
    """Deterministic ingest: content-hash dedupe collapses n_total -> unique invariants. The dedupe
    is the value (volume cheap, diversity is the self). File-walk ETA is deterministic + $0."""
    n_unique = int(n_total * (1 - dedup_ratio))
    total_bytes = n_total * bytes_per_record
    # deterministic, $0: hashing ~ a few hundred MB/s; conservative labeled rate
    ingest_s = total_bytes / 100e6  # 100 MB/s content-hash — labeled conservative
    return {"ok": True, "schema": SCHEMA, "n_total": n_total, "dedup_ratio": dedup_ratio,
            "n_unique": n_unique, "redundancy_removed": n_total - n_unique,
            "total_bytes": total_bytes, "ingest_eta_s": round(ingest_s, 1),
            "note": f"{n_total:,} records -> {n_unique:,} unique invariants ({dedup_ratio*100:.0f}% "
                    f"redundancy removed by content-hash) — deterministic, $0"}


def manifest_estimate(*, n_tasks: int = 50, n: int = 8, tokens_per_task: int = 6000,
                      provider: str = "deepseek") -> dict[str, Any]:
    """Manifestation: build tasks -> work -> wall-clock ETA (self-steal time_estimate's model).
    ETA = (n_tasks*tokens_per_task / n) / tps + drain_cadence. Honest about measured-vs-fallback."""
    try:
        from mag import time_estimate
        est = time_estimate.estimate("manifest", n=n, provider=provider)
        tps = est.get("tokens_per_sec") or FALLBACK_TPS
        measured = bool(est.get("speed_measured"))
    except Exception:
        tps = FALLBACK_TPS
        measured = False
    total_tokens = n_tasks * tokens_per_task
    eta_s = (total_tokens / max(n, 1)) / tps + DRAIN_CADENCE_S
    return {"ok": True, "schema": SCHEMA, "n_tasks": n_tasks, "n_parallel": n,
            "tokens_per_task": tokens_per_task, "total_tokens": total_tokens,
            "tokens_per_sec": round(tps, 1), "speed_measured": measured,
            "eta_s": round(eta_s), "eta_min": round(eta_s / 60, 1),
            "note": ("measured latency" if measured else
                     "NO measured latency for provider — using fallback tps; rough estimate, not precise")}


def moonshot_estimate(*, all_cap_usd_hr: float = 0.50, side_cap_usd_hr: float = 0.05,
                      n_ingest: int = WOW_RECORDS, n_manifest: int = 50,
                      n_parallel: int = 8) -> dict[str, Any]:
    """THE MOONSHOT ESTIMATE: Turtle WoW/WoWHead ingest -> manifestation of our own self-stolen
    system, ALL-in + small side swarm. Deterministic; measured facts vs labeled estimates clearly
    separated."""
    cap = capacity(cap_usd_hr=all_cap_usd_hr)
    split = split_resources(all_cap_usd_hr=all_cap_usd_hr, side_cap_usd_hr=side_cap_usd_hr)
    ingest = ingest_estimate(n_total=n_ingest)
    manifest = manifest_estimate(n_tasks=n_manifest, n=n_parallel)
    return {"ok": True, "schema": SCHEMA,
            "throughput": cap,
            "split": split,
            "ingest": ingest,
            "manifest": manifest,
            "moonshot": "ingest WoWHead/Turtle -> dedupe to unique invariants -> manifest as RIBs/"
                        "world/game through the swarm, ALL-in, with a small side swarm keeping loops alive",
            "honesty": "measured = warm cost/req + cache-hit + capacity; labeled estimates = WoW "
                       "scale + dedup ratio + tps fallback. Re-verify against the real export."}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="throughput-model")
    ap.add_argument("cmd", nargs="?", default="moonshot",
                    choices=["capacity", "split", "ingest", "manifest", "moonshot"])
    a = ap.parse_args()
    import json
    if a.cmd == "capacity":
        print(json.dumps(capacity(), ensure_ascii=False, indent=2, default=str))
    elif a.cmd == "split":
        print(json.dumps(split_resources(), ensure_ascii=False, indent=2, default=str))
    elif a.cmd == "ingest":
        print(json.dumps(ingest_estimate(), ensure_ascii=False, indent=2, default=str))
    elif a.cmd == "manifest":
        print(json.dumps(manifest_estimate(), ensure_ascii=False, indent=2, default=str))
    else:
        print(json.dumps(moonshot_estimate(), ensure_ascii=False, indent=2, default=str))
