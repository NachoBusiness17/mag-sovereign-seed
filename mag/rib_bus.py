"""rib_bus — route the RIB/steer INSTRUCTION LAYER through the verkle bus + memory.

Operator (2026-08-11): "route almost everything through it [the bus] ... all of our rib files are
basically instructions for flocks on how to act intelligently from frontier models down to these
dumb workers ... wire everything through memories so we can speed this up and align more succinctly
with our own stuff."

THE GAP IT CLOSES: today `frontier_steer.inject()` prepends a STATIC hardcoded `_STEER` list to each
task slice, and `rib_renderer.dispatch()` enqueues RIBs without bus/memory anchoring. The verkle bus
(now anchored by GPU/VRAM telemetry via gpu_k8s) is NOT in that path. So the frontier instruction
layer doesn't fold to memory, isn't published, and workers don't auto-load it from our doctrine.

THE WIRING: make the instruction layer FIRST-CLASS on the bus.
  publish_rib()  — fold a frontier RIB/steer invariant as a verkle knot (durable, content-addressed,
                   replayable, tied to the VRAM-anchored bus) + publish to mag:rib (real-time sync) +
                   append to the per-domain memory store (the source of truth, aligned with our doctrine).
  mount()        — auto-load a domain's bus-grown RIB instruction set from memory (deterministic, $0).
  inject_for()   — a drop-in for frontier_steer.inject(): prepend base frontier steer + the domain's
                   mounted RIBs to a worker task slice, so the cheap worker auto-carries the frontier
                   instruction layer aligned with our own memory.

Memory is the source of truth (memory/rib_bus/<domain>.json); the verkle knot + bus publish are the
durable/realtime projection. Deterministic + $0 (fold/publish/mount are all local, no LLM).

Schema: rib_bus.v1
"""
from __future__ import annotations

import hashlib
import json
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

SCHEMA = "rib_bus.v1"
RIB_DIR = ROOT / "memory" / "rib_bus"
CH_RIB = "mag:rib"

BASE_SOURCE = "frontier_steer (mined invariants)"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _domain_file(domain: str) -> Path:
    d = (domain or "general").strip().lower().replace(" ", "-")[:60] or "general"
    return RIB_DIR / f"{d}.json"


def _rib_key(domain: str, invariant: str) -> str:
    return hashlib.sha256(f"{domain}\x1f{invariant}".encode("utf-8")).hexdigest()[:16]


# ── per-domain memory store (source of truth) ────────────────────────────────
def _load_store(domain: str) -> dict[str, Any]:
    f = _domain_file(domain)
    if not f.is_file():
        return {"domain": domain, "ribs": {}, "updated": None}
    try:
        return json.loads(f.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {"domain": domain, "ribs": {}, "updated": None}


def _save_store(store: dict[str, Any]) -> Path:
    f = _domain_file(store["domain"])
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")
    return f


# ── fold to verkle (durable, content-addressed, tied to the VRAM-anchored bus) ──
def _fold_verkle(domain: str, invariant: str, source: str, n_total: int,
                 *, first_ts: str | None = None) -> dict[str, Any]:
    try:
        from mag.verkle_knot import append_verkle_knot

        # AH19 (audit finding #10, 2026-09-30): the fold minute is PINNED to the
        # rib's first-seen ts. Before the pin, every republish stamped now()
        # into time.created_at/updated_at — the dossier hash changed on every
        # call, so the dedupe gate never fired and each publish of an UNCHANGED
        # invariant paid a full-chain amend (v1) / an append (v2). With the pin,
        # an unchanged (invariant, store-size) pair yields a byte-identical
        # dossier → identical leaf_hash → dedupe skip. Evidence: the live chain
        # showed 2,821/8,626 rows as amend rewrites, many from this fold.
        if first_ts and len(first_ts) >= 16:
            minute = first_ts[:16]  # ISO 8601 → "YYYY-MM-DDTHH:MM"
        else:
            minute = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M")
        dossier = {
            "session_id": f"rib_bus_{domain}",  # no colon — colon is invalid in Windows filenames
            "time": {
                "created_at": {"iso_minute": minute, "unix_minute": None, "date": None},
                "updated_at": {"iso_minute": minute, "unix_minute": None, "date": None},
            },
            "scalar_knot": {
                "duration_minutes": 0.1,
                "tension_index": str(n_total)[:8],
                "residual_weight": 1.0,
                "theme_vector": {
                    "dominant": f"rib_{domain}",
                    "basis": ["rib", "instruction", "frontier", "sovereign"],
                    "raw": [n_total, 0.0, 0.0, 0.0],
                    "normalized": [1.0, 0.0, 0.0, 0.0],
                },
            },
            "content_commit": {"hex": _rib_key(domain, invariant)},
            "rib": {"domain": domain, "invariant": invariant[:400], "source": source},
        }
        return append_verkle_knot(dossier)
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


def _publish(domain: str, invariant: str, source: str) -> bool:
    try:
        from mag import verkle_bus

        return bool(verkle_bus.publish_sync(
            CH_RIB, {"type": "rib", "domain": domain,
                     "source": source, "invariant": invariant[:400]}))
    except Exception:
        return False


# ── public API ────────────────────────────────────────────────────────────────
def publish_rib(invariant: str, *, domain: str = "general", source: str = "frontier",
                target_rank: str = "T2", fold: bool = True, publish: bool = True) -> dict[str, Any]:
    """Fold + publish + store ONE frontier RIB/steer instruction for a domain.

    Dedupes by content hash. Returns the store state. Deterministic + $0.

    AH19 (chain_mode=v2): the fold's session_id stays ``rib_bus_{domain}`` —
    one pointer bucket per domain — and every publish appends ONE leaf whose
    chain ``session_seq`` IS the version (one leaf per (domain, version); the
    version pointer is the domain's session pointer). Republishing an
    UNCHANGED invariant dedupes to a skip (fold minute pinned to first-seen
    ts, see _fold_verkle). Spec: watch/inbox/last_mile_20260930/AH19_AMEND_PERF.md
    """
    invariant = (invariant or "").strip()
    if not invariant:
        return {"ok": False, "error": "empty invariant"}
    store = _load_store(domain)
    k = _rib_key(domain, invariant)
    # AH19: preserve the rib's FIRST-SEEN ts — the fold minute pins to it so a
    # republish of unchanged content is a dedupe skip, not a new chain write.
    existing = store["ribs"].get(k) or {}
    first_ts = str(existing.get("first_ts") or existing.get("ts") or "") or _now()
    # default target language = MACHINE (agent-as-OS): every RIB carries a target rank it lowers to
    store["ribs"][k] = {"invariant": invariant, "source": source, "ts": _now(),
                        "first_ts": first_ts,
                        "target_rank": str(target_rank or "T2").upper()}
    store["updated"] = _now()
    path = _save_store(store)
    knot = (_fold_verkle(domain, invariant, source, len(store["ribs"]), first_ts=first_ts)
            if fold else {})
    pub = _publish(domain, invariant, source) if publish else False
    return {
        "ok": True, "schema": SCHEMA, "domain": domain,
        "key": k, "n_total": len(store["ribs"]),
        "target_rank": str(target_rank or "T2").upper(),
        "added": "new" if len(store["ribs"]) == 1 else "updated",
        "store_path": str(path), "verkle": knot,
        "chain_mode": knot.get("chain_mode"),
        # AH19 version pointer: the (domain, version) leaf this publish resolves
        # to — skipped folds report the version already committed at the pointer.
        "version": knot.get("session_seq"),
        "published": pub,
    }


def mount(domain: str = "general") -> dict[str, Any]:
    """Auto-load the bus-grown RIB instruction set for a domain from memory. Deterministic + $0."""
    store = _load_store(domain)
    ribs = [r["invariant"] for r in store["ribs"].values()] if store.get("ribs") else []
    return {"ok": True, "schema": SCHEMA, "domain": domain, "n_ribs": len(ribs),
            "ribs": ribs, "updated": store.get("updated")}


def inject_for(slice_text: str, domain: str = "general") -> str:
    """UNIFIED injection (SELF-STEAL 2026-08-12): delegate to steer_engine.compile_steer so the
    canonical steer block (frontier invariants + operator directives + domain RIBs + grokbot
    seat directives) rides on EVERY task through this ONE drop-in. Because steer_swarm,
    knot_untangle, territory_solver and stateless_research all route through inject_for, one edit
    here propagates the unified steering to every worker/seat. Falls back gracefully if
    steer_engine is unavailable (never breaks a worker task)."""
    try:
        from mag import steer_engine
        c = steer_engine.compile_steer(domain)
        lines = [f"- {s}" for s in c["steer"]] or ["(no steer mounted)"]
    except Exception:
        # fallback to the prior behavior (frontier + mounted domain RIBs) — never break a task
        from mag.frontier_steer import preamble
        base = preamble()
        m = mount(domain)
        mounted = m.get("ribs", [])
        seen = set(base)
        extra = [r for r in mounted if r not in seen and not (seen.add(r) or False)]
        lines = [f"- {s}" for s in base] + [f"- [rib:{domain}] {s}" for s in extra]
    head = "\n".join(lines) if lines else "(no steer mounted)"
    return (f"STEER (steer_engine compiled — follow these):\n{head}\n\nTASK: {slice_text}")


def machine_lower(domain: str = "general") -> dict[str, Any]:
    """Resolve the mounted RIBs for a domain to their MACHINE actions (the default RIB target).

    Each RIB's target_rank -> the concrete machine/binary edit the swarm should perform (T0 local,
    T1 execve/mmap, T2 file_write, T3 binary_patch). Deterministic + $0.
    """
    m = mount(domain)
    ribs = m.get("ribs", [])
    store = _load_store(domain)
    lowered = []
    for r in ribs:
        rank = (store.get("ribs", {}).get(_rib_key(domain, r), {}) or {}).get("target_rank", "T2")
        from mag import machine_target as mt
        l = mt.lowers_to(r, rank)
        lowered.append({"invariant": r, "rank": rank, "machine_action": l["machine_action"]})
    return {"ok": True, "schema": SCHEMA, "domain": domain, "target_language": "machine",
            "n_ribs": len(lowered), "lowered": lowered}


def status() -> dict[str, Any]:
    """Report what's on the RIB bus per domain (memory-backed source of truth)."""
    out: dict[str, Any] = {"ok": True, "schema": SCHEMA, "domains": {}}
    if RIB_DIR.is_dir():
        for f in sorted(RIB_DIR.glob("*.json")):
            try:
                store = json.loads(f.read_text(encoding="utf-8", errors="replace"))
                d = store.get("domain") or f.stem
                out["domains"][d] = {"n_ribs": len(store.get("ribs") or {}),
                                     "updated": store.get("updated")}
            except Exception:
                continue
    out["n_domains"] = len(out["domains"])
    return out


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="rib-bus")
    sub = ap.add_subparsers(dest="cmd")
    p = sub.add_parser("publish")
    p.add_argument("invariant")
    p.add_argument("--domain", default="general")
    p.add_argument("--source", default="frontier")
    sub.add_parser("mount").add_argument("--domain", default="general")
    sub.add_parser("status")
    a = ap.parse_args(argv)
    if a.cmd == "publish":
        print(json.dumps(publish_rib(a.invariant, domain=a.domain, source=a.source),
                         ensure_ascii=False, indent=2, default=str))
    elif a.cmd == "mount":
        print(json.dumps(mount(a.domain), ensure_ascii=False, indent=2, default=str))
    else:
        print(json.dumps(status(), ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
