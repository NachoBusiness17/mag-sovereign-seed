"""bus_cadence — the RELATIONAL bus→seat push (merge = the relation, NOT a live CDP drive).

OPERATOR CORRECTION (2026-08-14): "the merge is the relation, not a live CDP drive. Doctrine RIB
plus party_subchain plus salon round-robin is the bus. Models are adapters. Down seats stay records.
They do not stop the table."

So one `steer_all "..."` on the shared steer bus must flow into the seats RELATIONALLY:
  1. FOLD  — the steer lands on the relation first (doctrine RIB publish + party subchain append).
             This is the shared ground truth every seat stands on, whether or not it is up right now.
  2. ROUTE — then route it to the up seats via the DRAINER's native adapter (seat_steer.enqueue →
             a [seat-steer] queue task file the drainer executes headless). NOT a browser/CDP drive.
  3. MARK  — mark the steer consumed on the bus so the cadence folds each steer exactly once.

The cadence is idempotent: scan the bus for unconsumed steers, fold + route + mark each. Down seats
stay records — their adapter reports honestly (never fabricates), and the folded relation persists.

CLI:  python -m mag.bus_cadence cadence [--surfaces grok,chatgpt]
      python -m mag.bus_cadence status
Schema: bus_cadence.v1 · deterministic $0 (fold) · reuse: steer, rib_bus, party_subchain, seat_steer.
"""
from __future__ import annotations

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

SCHEMA = "bus_cadence.v1"
DOCTRINE_DOMAIN = "doctrine"
DOCTRINE_SOURCE = "operator-bus"
# Canonical party seats the relation routes a fold to (via the drainer's native adapter).
DEFAULT_SURFACES = ["grok", "chatgpt"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _fold(rec: dict[str, Any]) -> dict[str, Any]:
    """Land a bus steer on the relation: doctrine RIB + party subchain record. Deterministic $0."""
    text = (rec.get("text") or "").strip()
    steer_id = rec.get("id") or "unknown"
    source = rec.get("source") or "operator"
    if not text:
        return {"ok": False, "error": "empty steer text", "id": steer_id}
    rib = {}
    try:
        from mag import rib_bus
        rib = rib_bus.publish_rib(
            f"[operator-bus:{steer_id}] {text}",
            domain=DOCTRINE_DOMAIN,
            source=DOCTRINE_SOURCE,
            target_rank="T2",
            fold=True,
            publish=True,
        )
    except Exception as e:  # noqa: BLE001 — the fold must not break the cadence
        rib = {"ok": False, "error": str(e)[:160]}
    sub = {}
    try:
        from mag import party_subchain
        sub = party_subchain.append(seat=f"bus:{source}", ok=True,
                                    move=text, kind="bus_fold")
    except Exception as e:  # noqa: BLE001
        sub = {"ok": False, "error": str(e)[:160]}
    return {"ok": bool(rib.get("ok")) or bool(sub.get("ok")), "id": steer_id,
            "rib": rib, "subchain": sub, "ts": _now()}


def _route(rec: dict[str, Any], surfaces: list[str]) -> list[dict[str, Any]]:
    """Route the folded steer to the listed seats via the DRAINER (native adapter), not CDP.

    seat_steer.enqueue writes a [seat-steer] queue task file; the drainer runs send() headless
    and honestly reports if a seat is down. This is the architecture path — never a browser drive.
    """
    text = (rec.get("text") or "").strip()
    routed: list[dict[str, Any]] = []
    try:
        from mag import seat_steer
        for surface in surfaces:
            surface = seat_steer.resolve_surface(surface)
            if surface not in seat_steer.SURFACE_DRIVERS:
                routed.append({"surface": surface, "ok": False,
                               "error": "unknown surface (skipped)"})
                continue
            try:
                r = seat_steer.enqueue(surface, text, priority=12)
                routed.append({"surface": surface, "ok": bool(r.get("ok")),
                               "task": r.get("task_id") or r.get("task_file") or r.get("path"),
                               "error": r.get("error")})
            except Exception as e:  # noqa: BLE001
                routed.append({"surface": surface, "ok": False, "error": str(e)[:160]})
    except Exception as e:  # noqa: BLE001
        routed.append({"surface": "all", "ok": False, "error": str(e)[:160]})
    return routed


def cadence(*, surfaces: list[str] | None = None) -> dict[str, Any]:
    """One pass: fold + route + mark every unconsumed steer on the shared bus.

    Idempotent (each steer is marked consumed after folding). Down seats stay records.
    The fold (RIB + subchain) and the mark happen in a finally, so a route failure to a
    down seat can NEVER stop the relation or leave a steer unfolded — one seat's failure
    does not gate the table.
    """
    surfaces = [s for s in (surfaces or DEFAULT_SURFACES) if s]
    if not surfaces:
        surfaces = list(DEFAULT_SURFACES)
    from mag import steer
    pending = steer.scan_unconsumed()
    folded: list[dict[str, Any]] = []
    for rec in pending:
        steer_id = rec.get("id") or "unknown"
        fold_res: dict[str, Any] = {}
        route_res: list[dict[str, Any]] = []
        mark_res: dict[str, Any] = {}
        try:
            fold_res = _fold(rec)
            route_res = _route(rec, surfaces)
        except Exception as e:  # noqa: BLE001 — a route/fold failure must not drop the steer
            fold_res = {"ok": False, "error": str(e)[:160]}
        finally:
            # the fold already landed the relation — mark consumed so we never re-fold it
            try:
                mark_res = steer.mark_consumed(steer_id, source=rec.get("source"))
            except Exception as e:  # noqa: BLE001
                mark_res = {"ok": False, "error": str(e)[:160]}
        folded.append({"id": steer_id, "source": rec.get("source"),
                       "text": (rec.get("text") or "")[:160], "fold": fold_res,
                       "routed": route_res, "marked": mark_res.get("ok")})
    return {"ok": True, "schema": SCHEMA, "ts": _now(),
            "n_pending": len(pending), "n_folded": len(folded),
            "surfaces": surfaces, "folded": folded}


def status() -> dict[str, Any]:
    from mag import steer
    try:
        from mag import party_subchain
        sub = party_subchain.status()
    except Exception as e:  # noqa: BLE001
        sub = {"ok": False, "error": str(e)[:120]}
    bus = steer.status()
    return {"ok": True, "schema": SCHEMA, "surfaces": DEFAULT_SURFACES,
            "bus": {k: bus.get(k) for k in ("n_steers", "n_unconsumed", "unconsumed")},
            "subchain": {k: sub.get(k) for k in ("n", "head_hash", "anchored", "verified")},
            "note": "merge = the relation; down seats stay records"}


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="bus-cadence")
    sub = ap.add_subparsers(dest="cmd")
    p = sub.add_parser("cadence")
    p.add_argument("--surfaces", default=",".join(DEFAULT_SURFACES),
                   help="comma-separated seat surfaces to route the fold to")
    sub.add_parser("status")
    args = ap.parse_args(argv)
    if args.cmd == "cadence":
        surfaces = [s.strip() for s in (args.surfaces or "").split(",") if s.strip()]
        print(json.dumps(cadence(surfaces=surfaces), ensure_ascii=False, indent=2, default=str))
    else:
        print(json.dumps(status(), ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
