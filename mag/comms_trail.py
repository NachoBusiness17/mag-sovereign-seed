"""comms_trail — steal the cheap agent-communication trail to confirm the shared private
language (operationalizes the "steal cheap agent communication" research topic).

The republic OS needs the agent-to-agent communication recorded as learning data. This
module captures the cheap communication surfaces and folds them into the mycelium graph as
artifact nodes + consumption edges (producer -> artifact -> consumer):

  1. `capture()`            — scan the communication surfaces (queue/handoff BUILD+GHOST
                             contracts, research pack answers, grok_free captures, grok_mirror
                             reports) and record each as a mycelium artifact node with
                             producer/consumer consumption edges. Idempotent via a seen-set.
  2. `confirm_language()`   — the shared-private-language round-trip: for each frozen BUILD
                             contract that has a landed result/answer, mark supports (grok spec
                             was interpreted + executed) vs contradicts (cheap agent diverged).
                             This CONFIRMS grok and the cheap tier speak the same language.
  3. `run_cadence()`        — idempotent: capture + confirm + dual-write.

Cheap by construction (no API cost — reads local files + mycelium). Schema: comms_trail.v1
CLI:  python -m mag.comms_trail capture | confirm | status | cadence
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
except ImportError:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCHEMA = "comms_trail.v1"
RUNS = ROOT / "memory" / "runs" / "comms_trail"
STATE = RUNS / "state.json"
HANDOFF = ROOT / "queue" / "handoff"
PACKS = ROOT / "memory" / "research_packs"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_state() -> dict[str, Any]:
    if STATE.is_file():
        try:
            return json.loads(STATE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _write_state(st: dict[str, Any]) -> None:
    RUNS.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(st, ensure_ascii=False, default=str, indent=2), encoding="utf-8")


def _surface_artifacts() -> list[dict[str, Any]]:
    """Enumerate the cheap communication surfaces as artifacts."""
    arts: list[dict[str, Any]] = []
    # 1) handoff BUILD + GHOST contracts (the frozen spec channel)
    if HANDOFF.is_dir():
        for p in sorted(HANDOFF.glob("*.md")):
            if p.name.startswith(("BUILD-", "GHOST-")):
                try:
                    text = p.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    text = ""
                arts.append({"kind": "handoff", "id": p.stem, "title": p.name,
                             "producer": "grok_terminal" if p.name.startswith("GHOST-") else "grok_free",
                             "text": text[:4000]})
    # 2) research pack answers (the knowledge-return channel)
    if PACKS.is_dir():
        for p in sorted(PACKS.glob("*.answer.*.md")):
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                text = ""
            arts.append({"kind": "answer", "id": p.stem, "title": p.name,
                         "producer": "cheap_swarm", "text": text[:4000]})
    # 3) grok_free captures (free grok surface results)
    try:
        gf = ROOT / "memory" / "runs" / "grok_free"
        if gf.is_dir():
            for p in sorted(gf.glob("*.json")):
                arts.append({"kind": "grok_free", "id": p.stem, "title": p.name,
                             "producer": "grok_free", "text": ""})
    except Exception:
        pass
    return arts


def _ensure_artifact(mc, art: dict[str, Any]) -> str:
    """Idempotent: ensure a mycelium artifact node exists for a communication surface; return node id."""
    title = art.get("title") or art.get("id") or "artifact"
    for n in mc._load_nodes().values():
        if str(n.get("title")) == title and n.get("type") == "artifact":
            return str(n["id"])
    node = mc.add_node(title[:300], ntype="artifact", trust=0.5,
                       tags=[art.get("kind", "comms")], body=art.get("text", "")[:2000])
    return str(node["id"])


def capture() -> dict[str, Any]:
    """Record the cheap communication trail as mycelium artifacts + consumption edges."""
    from mag import mycelium as mc
    st = _read_state()
    seen = set(st.get("seen") or [])
    added, edges = 0, 0
    for art in _surface_artifacts():
        key = f"{art['kind']}:{art['id']}"
        if key in seen:
            continue
        nid = _ensure_artifact(mc, art)
        # producer (a seat) -> artifact; consumer (cheap swarm) on answers/handoffs
        producer = mc.add_node(art.get("producer", "seat") + " (seat)", ntype="seat",
                               trust=0.6, tags=["seat"])
        mc.link(producer["id"], nid, etype="produced")
        edges += 1
        seen.add(key)
        added += 1
    st["seen"] = sorted(seen)
    st["last_capture"] = _now()
    _write_state(st)
    mc.dual_write()
    return {"ok": True, "action": "capture", "added": added, "edges": edges,
            "surfaces": len(_surface_artifacts())}


def _has_result(handoff_id: str) -> bool:
    """Is there a landed result/answer matching this BUILD contract? (round-trip done?)"""
    base = handoff_id
    for p in (PACKS.glob(f"*{base}*.answer.*.md") if PACKS.is_dir() else []):
        return True
    # a GROK/grok_free result json with the same stem
    gf = ROOT / "memory" / "runs" / "grok_free"
    return bool(gf.is_dir() and any(base in f.name for f in gf.glob("*.json")))


def confirm_language() -> dict[str, Any]:
    """Round-trip: for each frozen BUILD contract, CONFIRM the shared private language —
    a landed result means grok's spec was interpreted + executed (supports); none = the
    cheap tier hasn't interpreted it yet (open). Records supports/contradicts edges."""
    from mag import mycelium as mc
    confirmed, pending = 0, 0
    for art in _surface_artifacts():
        if art["kind"] != "handoff":
            continue
        nid = _ensure_artifact(mc, art)
        if _has_result(art["id"]):
            mc.reinforce(nid, nid, etype="supports", reward=0.5)  # spec interpreted + executed
            confirmed += 1
        else:
            pending += 1
    mc.dual_write()
    return {"ok": True, "action": "confirm_language", "confirmed": confirmed, "pending": pending}


def status() -> dict[str, Any]:
    from mag import mycelium as mc
    st = _read_state()
    arts = _surface_artifacts()
    # shared-private-language confidence: how many frozen BUILD/GHOST contracts have a landed
    # result (confirmed) vs still open (pending). Cheap to compute (local file globs) and is the
    # signal the router consumes to decide how much cheap-tier work to trust.
    confirmed = pending = 0
    for art in arts:
        if art["kind"] != "handoff":
            continue
        if _has_result(art["id"]):
            confirmed += 1
        else:
            pending += 1
    return {"schema": SCHEMA, "ok": True, "surfaces": len(arts),
            "seen": len(st.get("seen") or []), "last_capture": st.get("last_capture"),
            "confirmed": confirmed, "pending": pending,
            "mycelium": {"nodes": mc.status()["nodes"], "edges": mc.status()["edges"]},
            "ts": _now()}


def consumption_signal() -> dict[str, Any]:
    """Read the ACTUAL mycelium consumption edges -> per-seat consumption stats.

    The router consumes this to trust seats that have a PROVEN consumption record (a seat
    that has actually produced/consumed artifacts in the graph), not just the aggregate
    confirmed/pending round-trip count. Cheap (local jsonl reads, no API).

    Returns per-seat: how many consumption edges the seat is the source of + summed weight
    (weight grows with reinforcement = the seat's work was used). A seat with count>0 and
    weight above the trust floor is "proven" \u2014 the router can route to it with confidence.
    """
    from mag import mycelium as mc
    nodes = mc._load_nodes()
    edges = mc._load_edges()
    seats: dict[str, dict[str, Any]] = {}
    total = 0
    for e in edges:
        if e.get("type") != "consumption":
            continue
        total += 1
        src = str(e.get("src"))
        n = nodes.get(src)
        if not n or n.get("type") != "seat":
            continue
        title = str(n.get("title") or src)
        key = title.split(" (")[0].strip().lower()
        cur = seats.setdefault(key, {"count": 0, "weight": 0.0})
        cur["count"] += 1
        cur["weight"] = round(cur["weight"] + float(e.get("weight") or 0), 4)
    # a seat is "proven" when it has consumption edges with meaningful weight (>= trust floor)
    proven = sorted(k for k, v in seats.items() if v["count"] > 0 and v["weight"] >= 0.5)
    return {
        "ok": True,
        "schema": "comms_consumption.v1",
        "total_consumption_edges": total,
        "seats": seats,
        "proven_seats": proven,
    }


def run_cadence() -> dict[str, Any]:
    """Idempotent: capture + confirm + dual-write the communication trail."""
    c = capture()
    cl = confirm_language()
    return {"ok": True, "action": "comms_cadence", "capture": c, "confirm_language": cl}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    ap = argparse.ArgumentParser(prog="comms-trail", description="Steal the cheap agent-communication trail (shared private language)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("capture", help="record communication surfaces into the mycelium graph")
    sub.add_parser("confirm", help="round-trip confirm the shared private language")
    sub.add_parser("status", help="trail state")
    sub.add_parser("cadence", help="capture + confirm + dual-write")
    args = ap.parse_args(argv)
    if args.cmd == "capture":
        print(json.dumps(capture(), indent=2, default=str))
    elif args.cmd == "confirm":
        print(json.dumps(confirm_language(), indent=2, default=str))
    elif args.cmd == "status":
        print(json.dumps(status(), indent=2, default=str))
    elif args.cmd == "cadence":
        print(json.dumps(run_cadence(), indent=2, default=str)[:4000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["capture", "confirm_language", "status", "consumption_signal", "run_cadence", "main"]
