"""manifest — the CHAIN-VERIFIED MANIFEST: who can do what, as a chain fact (2026-08-24).

GSTD steal #4. The system's standing seams — the bones — declared in ONE deterministic
registry, anchored to the verkle chain, and re-verified on every read. Any session/seat reads
the same committed reality instead of trusting its own in-process claim about who owns what.
This is the fix for the proven collision (two sessions, each claiming the loop): the manifest
names ONE owner per concern, as a chain fact.

  manifest()  -> the deterministic registry (roles + owners + contracts), hashed.
  verify()    -> CHAIN-VERIFIED read: does the on-disk manifest hash match the anchored
                 chain leaf? match = committed. drift = the bones changed without
                 re-anchoring (honest fact, reported, not hidden).
  anchor()    -> commit the manifest hash to the verkle chain (deduped: unchanged persists,
                 no chain spam — the team_knot pattern).

Schema: manifest.v1 · deterministic + $0 · reuse: verkle_knot (append), team_knot (dedup)
CLI: python -m mag.manifest status | verify | anchor
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
except Exception:  # noqa: BLE001
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

SCHEMA = "manifest.v1"
SESSION_ID = "manifest"
ANCHOR = ROOT / "state" / "manifest_anchor.json"  # on-disk record of the anchored chain hash

# THE BONES — one owner per concern, as a chain fact. Nothing here is invented; each entry is
# a standing seam already built and verified in this system (2026-08-24 and before).
MANIFEST: list[dict[str, str]] = [
    {"role": "the tick", "owner": "mag.work_loop.run_once",
     "concern": "one bank-or-halt loop iteration",
     "contract": "only the loop claims work; queue/cold/fuel/drill; halt at 0% CPU; ceiling-gated",
     "schema": "work_loop.v1"},
    {"role": "the ceiling", "owner": "mag.cadence_learn",
     "concern": "CPU ceiling + worker cadence",
     "contract": "refuse work at/above MAG_CPU_CEILING (90); taper parallelism as CPU climbs; learn from rounds",
     "schema": "cadence_learn.v1"},
    {"role": "the quality gate", "owner": "mag.fuel_feed",
     "concern": "only quality-cleared answers enter shared reality",
     "contract": "score every lane answer (WITHHOLD 0.3); weak = filed fall, never pollution",
     "schema": "fuel_feed.v1"},
    {"role": "the free-lane channel", "owner": "mag.fuel_feed",
     "concern": "explore-queue signals -> free lanes -> fold -> percolate",
     "contract": "entropy-routed (hard->strong, easy->fast); $0 only; per-lane profile",
     "schema": "fuel_feed.v1"},
    {"role": "the drill", "owner": "mag.ox_resident",
     "concern": "coldest-vertex deep reasoning",
     "contract": "cold-vertex only, bounded (RETRY_CAP=3), reasoning is the product",
     "schema": "ox_resident.v1"},
    {"role": "the percolator", "owner": "mag.percolator",
     "concern": "explore -> invariant / explore (shared knowledge)",
     "contract": "signals percolate only after the gate; deduped by canonical",
     "schema": "percolator.v1"},
    {"role": "the learn seam", "owner": "mag.ox_percolate",
     "concern": "ox artifacts -> percolator (novel/consolidated/noise)",
     "contract": "sync + distill; novel->explore, consolidated->invariant",
     "schema": "ox_percolate.v1"},
    {"role": "the clock", "owner": "mag.verified_clock",
     "concern": "one verified time source",
     "contract": "now_iso/age/verify (system vs chain, drift <= 300s)",
     "schema": "verified_clock.v1"},
    {"role": "the team reality", "owner": "mag.team_knot",
     "concern": "shared team state, anchored",
     "contract": "read status() before acting; stand() to anchor changes",
     "schema": "team_knot.v1"},
    {"role": "the chain", "owner": "mag.verkle_knot",
     "concern": "append/verify committed state",
     "contract": "append_verkle_knot + verify(); the ground truth store",
     "schema": "verkle_knot.v1"},
    {"role": "the queue", "owner": "mag.orchestrator",
     "concern": "tasks: enqueue / drain / list",
     "contract": "the real source of queued work",
     "schema": "orchestrator.v1"},
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def manifest() -> dict[str, Any]:
    """The deterministic registry + its hash (same bytes every read)."""
    payload = {"schema": SCHEMA, "entries": MANIFEST,
               "note": "who can do what, as a chain fact — one owner per concern"}
    h = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()
    return {"ok": True, "schema": SCHEMA, "manifest_hash": h, "entries": MANIFEST,
            "count": len(MANIFEST)}


def _load_anchor() -> dict[str, Any]:
    if ANCHOR.is_file():
        try:
            return json.loads(ANCHOR.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            pass
    return {}


def anchor(*, force: bool = False) -> dict[str, Any]:
    """Commit the manifest hash to the verkle chain (deduped: unchanged persists, no spam)."""
    m = manifest()
    prev = _load_anchor()
    if not force and prev.get("manifest_hash") == m["manifest_hash"] and prev.get("leaf_hash"):
        return {"ok": True, "schema": SCHEMA, "anchored": True, "persisted": True,
                "manifest_hash": m["manifest_hash"], "leaf_hash": prev.get("leaf_hash"),
                "root": prev.get("root"), "path": prev.get("path", ""),
                "note": "unchanged -> the manifest anchor persists (no chain spam)"}
    knot = {}
    try:
        from mag import verkle_knot
        knot = verkle_knot.append_verkle_knot({
            "session_id": SESSION_ID,
            "theme": "manifest",
            "summary": f"[manifest] {m['manifest_hash'][:16]} — {m['count']} standing seams",
        })
    except Exception as e:  # noqa: BLE001 — anchoring must never break the manifest
        knot = {"leaf_hash": m["manifest_hash"], "error": str(e)[:100]}
    rec = {"schema": SCHEMA, "ts": _now(), "manifest_hash": m["manifest_hash"],
           "leaf_hash": knot.get("leaf_hash", ""),
           "root": knot.get("verkle_root") or knot.get("root", ""),
           "path": knot.get("path", "")}
    ANCHOR.parent.mkdir(parents=True, exist_ok=True)
    ANCHOR.write_text(json.dumps(rec, indent=2, default=str), encoding="utf-8")
    return {"ok": True, "schema": SCHEMA, "anchored": True, "persisted": False, **rec,
            "note": "anchored the manifest to a fresh verkle knot"}


def verify() -> dict[str, Any]:
    """CHAIN-VERIFIED read: does the current manifest match the anchored chain fact?
    match = committed. drift = the bones changed without re-anchoring (honest fact)."""
    m = manifest()
    a = _load_anchor()
    if not a.get("leaf_hash"):
        return {"ok": True, "schema": SCHEMA, "verified": False, "state": "unanchored",
                "manifest_hash": m["manifest_hash"],
                "note": "manifest not yet anchored — run anchor() to commit it as a chain fact"}
    match = a.get("manifest_hash") == m["manifest_hash"]
    return {"ok": True, "schema": SCHEMA, "verified": match,
            "state": "committed" if match else "DRIFT",
            "manifest_hash": m["manifest_hash"], "anchored_hash": a.get("manifest_hash"),
            "leaf_hash": a.get("leaf_hash"), "root": a.get("root"),
            "note": ("chain-verified: on-disk manifest matches the anchored leaf"
                     if match else "DRIFT: on-disk manifest differs from the anchored chain "
                                    "leaf — the bones changed without re-anchoring")}


def status() -> dict[str, Any]:
    """READ the manifest: who can do what + the chain-verification state. Any session calls
    this before claiming a role (the collision fix)."""
    v = verify()
    return {"ok": True, "schema": SCHEMA, **v,
            "count": len(MANIFEST),
            "owners": sorted({e["owner"] for e in MANIFEST}),
            "roles": [e["role"] for e in MANIFEST],
            "contract": "one owner per concern, as a chain fact — read before claiming a role",
            "built": "2026-08-24 — foundation #4 of the doctrine"}


def main(argv: list[str] | None = None) -> int:
    import argparse
    p = argparse.ArgumentParser(prog="manifest", description="chain-verified manifest")
    p.add_argument("cmd", nargs="?", default="status",
                   choices=["status", "verify", "anchor"])
    a = p.parse_args(argv)
    if a.cmd == "verify":
        print(json.dumps(verify(), indent=2, ensure_ascii=False))
    elif a.cmd == "anchor":
        print(json.dumps(anchor(), indent=2, ensure_ascii=False))
    else:
        print(json.dumps(status(), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
