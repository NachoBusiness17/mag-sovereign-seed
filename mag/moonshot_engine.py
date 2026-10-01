"""moonshot_engine — operationalize the moonshot: turn the deterministic estimate (throughput_model)
into actually-QUEUED swarm work, and self-measure progress against it. Deterministic + stateless.

Operator (2026-08-12): "moonshot". Standing directive: execute the WoWHead/Turtle ingest ->
manifestation of our own self-stolen system through the swarm, ALL-in + small side swarm, with the
deterministic model (throughput_model.moonshot_estimate) as the plan and honest self-measurement.

SELF-STEAL (nothing invented — reuses our own machinery):
  * throughput_model.moonshot_estimate()  -> the deterministic plan (measured facts vs labeled est).
  * swarm_surface.route_novel(...)        -> THE ONE primitive: dedupe by anchor + enqueue to the
    SWARM research queue (swarm_worker.enqueue_task -> k8s worker drains in-cluster). We never
    enqueue ourselves — we weave the shared primitive, so the swarm coordinates the moonshot.
  * swarm_surface sent.jsonl ledger       -> the GROUNDED progress bytes (what actually landed).
  * idempotent dedupe (same goal -> same anchor) -> safe to run every cadence, $0.

THE MOONSHOT (operational, not just an estimate):
  plan()     -> the deterministic moonshot estimate (throughput_model) + honest labels.
  cold_launch(limit) -> route up to `limit` DISTINCT moonshot goals to the swarm (each distinct
                        goal -> distinct anchor -> no per-module enqueue, dedupe by anchor).
  progress() -> count moonshot goals that ACTUALLY landed in the sent.jsonl ledger -> real
                progress vs target, grounded in the same bytes route_novel writes (never invented).
  moonshot() -> full operational snapshot: plan + queued progress + honesty + self-measure.

Schema: moonshot_engine.v1 · deterministic + $0 · reuse: throughput_model, swarm_surface
"""
from __future__ import annotations

import json
import sys
from typing import Any

try:
    from config import ROOT
except Exception:
    from pathlib import Path as _P
    ROOT = _P(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "moonshot_engine.v1"
SURFACE = "moonshot"
LEDGER = ROOT / "memory" / "swarm_surface" / "sent.jsonl"

# DISTINCT, deterministic moonshot goals — each is a distinct build target, so each maps to a
# distinct content anchor and dedupes independently. These OPERATIONALIZE the estimate: they are
# the actual units of work the swarm drains to manifest the self-stolen system from the WoW/Turtle
# corpus. Ordered from ingest -> invariants -> manifestation.
MOONSHOT_GOALS: list[str] = [
    "Ingest WoWHead/Turtle WoW corpus -> content-hash dedupe to unique invariants (volume cheap, "
    "diversity is the self): map item/spell/quest/NPC records into our invariant lattice.",
    "Extract the deterministic invariant spine from the WoW/Turtle corpus and fold it into our "
    "invariant lattice so the game world and our system share the same re-derivable rules.",
    "Manifest the self-stolen system as RIBs from the deduped corpus: publish the world/quest/"
    "item invariant set as interpretable RIBs on rib_bus so the world renders from the chain.",
    "Manifest the WoW/Turtle world as a verkle knot chain: content-address the world-state so the "
    "game is a re-derivable, stateless knot set (game is constructed, not coded).",
    "Build the game-as-subtle-work surface: route the manifested world through swarm_surface so "
    "the stochastic swarm individuates the deterministic world (deterministic spine + stochastic "
    "flesh) on the shared queue.",
    "Moonshot self-measure: wire progress back into throughput_model so the deterministic estimate "
    "is corrected by REAL queued progress each cadence (honesty: measured > labeled).",
    "EXTERNAL STEAL (moonshot): research how open-source MMO/emulator server codebases (MaNGOS/"
    "TrinityCore lineage) structure server-authoritative world state, event buses, and modding/"
    "addon hooks; steal+adapt the strongest mechanism into our verkle-anchored game world so the "
    "Republic's game is grounded in proven patterns (contract only, no wholesale copy).",
    "LIVE GAME FEED (moonshot): wire the game world to drink from the ACTUAL republic's state "
    "(our chats, tool calls, swarm results, filed sessions) as committed verkle knots narrated by "
    "the DM, so the game IS the live hologram of the system rather than a manual turn surface.",
]


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _ledger_entries(surface: str | None = None) -> list[dict[str, Any]]:
    """Grounded progress bytes: read the ACTUAL sent.jsonl ledger route_novel writes. Never invent
    progress — if it isn't in the ledger it didn't land."""
    if not LEDGER.is_file():
        return []
    out: list[dict[str, Any]] = []
    for line in LEDGER.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            e = json.loads(line)
        except Exception:
            continue
        if surface is None or e.get("surface") == surface:
            out.append(e)
    return out


def _outcome(task_id: str) -> str:
    """Grounded outcome for one ledger task_id: live queue-spec status, else a filed result,
    else 'vanished' (no verifiable trace anywhere).

    FIX RECEIPT (LM10, 2026-09-29): cause — the sent.jsonl ledger is an ENQUEUE ledger, so
    progress() counted rows whose work had evaporated: anchors 9fd392d3a126d4c1 /
    021b129e9844ab6f (task sw-12205a0a9c / sw-9309fab2e0, enqueued 2026-08-12) have no spec
    in the live queue, none in queue_backup_20260827_preRepoint, and no results/<id>.json —
    yet progress() reported pct_of_target 25->100% as if the work stood. Evidence fixed:
    progress() now joins ledger task_ids against queue spec + results bytes and reports the
    census, so 'vanished' rows are visible instead of silently credited."""
    if not task_id:
        return "no-task-id"
    try:
        from mag import swarm_worker
    except Exception:
        return "unknown-no-worker"
    spec = swarm_worker.QUEUE_DIR / f"{task_id}.json"
    if spec.is_file():
        try:
            return str(json.loads(spec.read_text(encoding="utf-8")).get("status", "unknown"))
        except Exception:
            return "unreadable-spec"
    if (getattr(swarm_worker, "RESULTS_DIR", None) is not None
            and (swarm_worker.RESULTS_DIR / f"{task_id}.json").is_file()):
        return "result-filed"
    return "vanished"


def plan() -> dict[str, Any]:
    """The deterministic moonshot estimate (throughput_model). Grounded: measured facts vs labeled
    estimates clearly separated, never over-claimed."""
    try:
        from mag import throughput_model
        est = throughput_model.moonshot_estimate()
        return {"ok": True, "schema": SCHEMA, "plan": est}
    except Exception as e:
        return {"ok": False, "schema": SCHEMA, "error": str(e)[:120]}


def cold_launch(*, limit: int = len(MOONSHOT_GOALS)) -> dict[str, Any]:
    """Route up to `limit` DISTINCT moonshot goals to the swarm via THE ONE primitive
    (swarm_surface.route_novel). Each distinct goal -> distinct anchor -> dedupe by anchor, so this
    is idempotent: repeated runs enqueue nothing already sent. $0 (reuses the swarm queue)."""
    from mag import swarm_surface
    goals = MOONSHOT_GOALS[:limit]
    results = []
    for g in goals:
        r = swarm_surface.route_novel(g, surface=SURFACE, lens="moonshot", domain="research")
        results.append({"goal": g[:60], "anchor": r.get("anchor", ""),
                        "deduped": r.get("deduped", False), "ok": r.get("ok", False)})
    n_sent = sum(1 for r in results if not r["deduped"])
    return {"ok": True, "schema": SCHEMA, "target": len(goals),
            "newly_queued": n_sent, "already_deduped": len(goals) - n_sent,
            "results": results, "contract": "route_novel(surface=moonshot) -> swarm queue; "
            "idempotent by content anchor; swarm drains in-cluster"}


def progress() -> dict[str, Any]:
    """Real, grounded progress: count moonshot goals that ACTUALLY landed in the sent.jsonl ledger
    (the same bytes route_novel writes). Measured, never invented. Deterministic + $0."""
    entries = _ledger_entries(SURFACE)
    anchors = sorted({e.get("anchor", "") for e in entries if e.get("anchor")})
    target = len(MOONSHOT_GOALS)
    # LM10 2026-09-29: outcome join — the ledger proves ENQUEUE, not DONE; census the bytes
    # (queue spec status + results/<id>.json) so vanished rows are seen, never credited.
    outcomes: dict[str, int] = {}
    for e in entries:
        o = _outcome(e.get("task_id", ""))
        outcomes[o] = outcomes.get(o, 0) + 1
    verified_done = outcomes.get("done", 0) + outcomes.get("result-filed", 0)
    return {"ok": True, "schema": SCHEMA, "target": target,
            "queued_unique": len(anchors), "ledger_rows": len(entries),
            "pct_of_target": round(100.0 * len(anchors) / target, 1) if target else 0.0,
            "verified_done": verified_done,
            "outcomes": dict(sorted(outcomes.items(), key=lambda kv: -kv[1])),
            "note": "grounded in sent.jsonl ledger (measured); 0 means nothing landed yet; "
                    "pct_of_target counts ENQUEUED goals — verified_done joins the outcome "
                    "bytes, and 'vanished' rows (purged spec + no result) are visible",
            "anchors": anchors}


def moonshot() -> dict[str, Any]:
    """Full operational snapshot: the deterministic plan + real queued progress + honesty. This is
    the report the loop surfaces each cadence — plan is labeled, progress is measured."""
    p = plan()
    prog = progress()
    # self-measure: correct the labeled estimate by REAL queued progress when available
    measured_ready = prog["queued_unique"] > 0
    return {"ok": True, "schema": SCHEMA,
            "surface": SURFACE,
            "plan": p.get("plan"),
            "progress": prog,
            "self_measure": ("progress measured from sent.jsonl ledger; correct the estimate by "
                             "real queued work each cadence (honesty: measured > labeled)"
                             if measured_ready else
                             "no moonshot goals queued yet — run cold_launch() to start, or let "
                             "the cadence route them"),
            "honesty": "plan = labeled estimate (throughput_model); progress = measured ledger "
                       "bytes; never claim queued work that isn't in the ledger",
            "cost": "deterministic + $0 (reuses swarm_surface.route_novel + ledger)"}


def moonshot_self_steal(*, limit: int = len(MOONSHOT_GOALS), fold_back: bool = True) -> dict[str, Any]:
    """THE MOONSHOT SELF-STEAL LOOP (2026-08-12, operator: "moonshot self steal loop").

    Composes the self-steal cadence (sense -> sort -> re-strike -> fold, applied EVERYWHERE per the
    self-steal-cadence memory) onto the moonshot + arrival surfaces:
      1. SENSE    — moonshot_engine.moonshot() (plan + progress, measured) + self_steal.audit()
                    (moonshot/arrival now registered, so the loop sees if they're cold).
      2. RE-STRIKE — cold_launch(limit) routes the DISTINCT moonshot goals to the swarm via THE ONE
                    primitive (swarm_surface.route_novel), idempotent by content anchor. Each beat
                    re-strikes whatever goals aren't yet queued.
      3. FOLD     — arrival.fold_authored(limit) reads the swarm's authored packs and folds them back
                    as SELF-AUTHORED RIBs (source=swarm) into the standing wave, warming the prefix
                    every other worker mounts.

    Deterministic + $0 (reuses swarm_surface.route_novel + rib_bus.publish_rib + self_steal.audit;
    dogfoods the swarm). This is the Arrival made cheap: local -> swarm -> swarm writes its own RIBs
    -> fold -> warm the wave -> the whole fleet gets smarter with every beat."""
    from mag import swarm_surface, self_steal, arrival

    # 1) SENSE — the moonshot plan + measured progress + whether the surfaces are cold
    p = moonshot()
    audit = {}
    try:
        audit = self_steal.audit()
        audit["moonshot_findings"] = [
            f for f in audit.get("findings", [])
            if f.get("capability") in ("moonshot_engine", "arrival")
        ]
    except Exception as e:
        audit["error"] = str(e)[:120]

    # 2) RE-STRIKE — route the distinct moonshot goals to the swarm (idempotent by anchor)
    launch = cold_launch(limit=limit)

    # 3) FOLD — fold the swarm's authored packs back as self-authored RIBs into the standing wave
    fold = arrival.fold_authored(limit=8) if fold_back else {"ok": True, "folded": [],
                                                             "n_folded": 0}

    return {"ok": True, "schema": SCHEMA, "surface": SURFACE,
            "sense": {"plan": p.get("plan"), "progress": p.get("progress"),
                      "audit_findings": audit.get("n_findings"),
                      "moonshot_cold": [f for f in audit.get("moonshot_findings", [])
                                        if f.get("utilization") != "ok"]},
            "re_strike": launch,
            "fold": {"ok": fold.get("ok"), "n_folded": fold.get("n_folded", 0),
                     "folded": [f for f in fold.get("folded", []) if f.get("ok")]},
            "contract": "sense (plan+progress+audit) -> re-strike (cold_launch via "
                        "swarm_surface.route_novel, idempotent) -> fold (arrival.fold_authored -> "
                        "self-authored RIBs into the standing wave); $0, dogfoods the swarm",
            "honesty": "progress + folds measured from the shared ledgers (sent.jsonl, rib_bus "
                       "store); never claim queued or folded work that isn't in the bytes"}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="moonshot-engine")
    ap.add_argument("cmd", nargs="?", default="moonshot",
                    choices=["plan", "cold-launch", "progress", "moonshot"])
    ap.add_argument("--limit", type=int, default=len(MOONSHOT_GOALS))
    a = ap.parse_args()
    if a.cmd == "plan":
        out = plan()
    elif a.cmd == "cold-launch":
        out = cold_launch(limit=a.limit)
    elif a.cmd == "progress":
        out = progress()
    else:
        out = moonshot()
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
