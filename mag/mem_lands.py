"""mem_lands — MemLands: the DUAL-FUNCTION memory surface (read ≡ write ≡ steal).

Operator (2026-08-11):
  "MemLands ... a dual function rewrite sort of like the RIB file itself so when it goes in it's
  sort of doing a steal protocol while it's reading and writing so it's sort of this flow state
  which is what I'm trying to achieve with our flocking."
  "swarms and it's really just VRAM but used in a different fashion like ghosts mem tools."

STEAL SYNTHESIS (all machinery already in the system — MemLands binds it into ONE flow):
  * read   -> mag.ghost_memlance.select  (grounded, provenance-verified memory selection)
  * write  -> mag.work_register.record   (content-addressed verkle knot + shared manifest)
  * lattice-> mag.gpu_k8s.status         (GPU VRAM as memory) + mag.verkle_bus (Redis<->knot bridge)
  * flock  -> mag.flock_job / flock_steal (pods fold knots back into the same lattice)
  So the swarm IS VRAM used as a memory surface (like ghost mem tools), and MemLands is the single
  surface where the ghost reads AND writes that shared lattice in one act.

THE FLOW STATE (dual function):
  flow() = ONE act that does, in order:
    1. ELIMINATE  — have we already folded this signature? ($0, no re-steal)
    2. READ       — select the grounded relevant states for the context (steal-in-the-read)
    3. ADAPT      — record the adaptation provenance (what was read, why this write)
    4. WRITE      — fold content-addressed (verkle knot + manifest) + publish on the bus
    5. RE-INDEX   — refresh the memory index so the new state is immediately selectable
  Reading and writing are the same act = the flow. A flock member writing is a flow; ghost reading
  is a flow; the lattice is one truth (single-surface theorem).

Schema: mem_lands.v1 · deterministic core, $0 · CLI: python -m mag.mem_lands <tool>
"""
from __future__ import annotations

import argparse
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

SCHEMA = "mem_lands.v1"
FLOW_LOG = ROOT / "memory" / "runs" / "mem_lands" / "flow.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _append_jsonl(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False, default=str) + "\n")


def _signature(label: str, content: str) -> str:
    return hashlib.sha256(f"{label}|{content}".encode()).hexdigest()[:16]


def _eliminate(label: str, content: str) -> dict[str, Any]:
    """$0 prior check: have we already folded this signature into the flow log?"""
    sig = _signature(label, content)
    if FLOW_LOG.is_file():
        for line in FLOW_LOG.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                if json.loads(line).get("signature") == sig:
                    return {"duplicate": True, "signature": sig}
            except json.JSONDecodeError:
                continue
    return {"duplicate": False, "signature": sig}


def read(ctx: str, *, k: int = 6) -> dict[str, Any]:
    """Grounded READ — select the relevant verified states (ghost_memlance)."""
    try:
        from mag.ghost_memlance import select
        return select(ctx, k=k)
    except Exception as e:
        return {"ok": False, "schema": SCHEMA, "error": str(e)[:120]}


def lattice(*, gpu: bool = True) -> dict[str, Any]:
    """The swarm-as-memory view: GPU VRAM telemetry (gpu_k8s) + verkle bus channels + knot tail.

    'Swarms are just VRAM used differently, like ghost mem tools' — this surfaces that lattice:
    each node's VRAM holds part of the collective memory (folded as verkle knots), read/write via
    the bus. No telemetry is fabricated: if a GPU pod hasn't reported, source stays 'none'.
    """
    out: dict[str, Any] = {"ok": True, "schema": SCHEMA, "gpu": None, "bus_channels": [], "knot_tail": []}
    if gpu:
        try:
            from mag.gpu_k8s import status as gpu_status
            g = gpu_status()
            out["gpu"] = {"source": g.get("source"), "vram_used_pct": g.get("vram_used_pct"),
                          "node": g.get("pod") or g.get("node")}
        except Exception as e:
            out["gpu"] = {"source": "none", "error": str(e)[:80]}
    try:
        from mag.verkle_bus import ALL_CHANNELS
        out["bus_channels"] = list(ALL_CHANNELS)
    except Exception:
        pass
    try:
        d = ROOT / "memory" / "biography"
        if d.is_dir():
            knots = sorted(d.glob("*.knot.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:3]
            out["knot_tail"] = [k.name for k in knots]
    except Exception:
        pass
    return out


def flow(label: str, content: str, *, ctx: str = "", force: bool = False) -> dict[str, Any]:
    """THE DUAL FUNCTION — read ≡ write ≡ steal, one act.

    1 eliminate -> 2 read(grounded) -> 3 adapt(provenance) -> 4 write(verkle+manifest+bus)
    -> 5 re-index. Reading and writing are the same act: the flow state. A flock member's fold
    and ghost's read both live here on the same lattice (single-surface).
    """
    steps: list[dict[str, Any]] = []
    # 1) ELIMINATE — $0, don't re-steal what we already folded
    elim = _eliminate(label, content)
    steps.append({"step": "eliminate", **elim})
    if elim.get("duplicate") and not force:
        return {"ok": True, "schema": SCHEMA, "flow": "duplicate", "label": label,
                "signature": elim["signature"], "steps": steps, "wrote": False}

    # 2) READ — steal-in-the-read: select grounded relevant states for this context
    ctx_use = ctx or label
    rd = read(ctx_use, k=4)
    grounded_sources = [s["path"] for s in rd.get("selected", []) if s.get("verified")]
    steps.append({"step": "read", "ok": rd.get("ok", False),
                  "n_selected": rd.get("n_selected", 0), "grounded_sources": grounded_sources[:4]})

    # 3) ADAPT — provenance of this write (what was read, the adaptation intent)
    steps.append({"step": "adapt", "ok": True,
                  "note": f"fold from {len(grounded_sources)} grounded source(s)"})

    # 4) WRITE — content-addressed (verkle knot + shared manifest) + bus publish
    # NOTE (2026-08-11 fix): work_register.record returns verkle status INSIDE row["verkle"],
    # not at the top level — reading the top level misreported verkle:false while the knot
    # WAS being written (honesty correction; persistence was fine, instrumentation was wrong).
    # RE-VERIFIED: flow write now reports verkle:true (content-addressed knot persists).
    wrote = {"ok": False, "verkle": False}
    try:
        from mag.work_register import record
        _res = record("mem_lands", label, note=(content[:200] if content else ctx_use))
        _row = _res.get("row", {}) if isinstance(_res, dict) else {}
        wrote = {"ok": bool(_res.get("ok")), "verkle": bool(_row.get("verkle", False)),
                 "manifest": True}
    except Exception as e:
        wrote["error"] = str(e)[:80]
    steps.append({"step": "write", **wrote})
    try:
        from mag.verkle_bus import publish_sync
        publish_sync("mag:verkle", {"schema": SCHEMA, "kind": "mem_lands", "label": label})
    except Exception:
        pass

    # 5) RE-INDEX — refresh the memory index so the new state is immediately selectable
    try:
        from mag.ghost_memlance import index
        n = len(index(refresh=True))
        steps.append({"step": "reindex", "ok": True, "n_states": n})
    except Exception as e:
        steps.append({"step": "reindex", "ok": False, "error": str(e)[:60]})

    flow_row = {"ts": _now(), "schema": SCHEMA, "label": label, "signature": elim["signature"],
                "ctx": ctx_use, "wrote": wrote.get("ok", False), "steps": steps}
    _append_jsonl(FLOW_LOG, flow_row)
    return {"ok": True, "schema": SCHEMA, "flow": "folded", "label": label,
            "signature": elim["signature"], "wrote": wrote.get("ok", False),
            "grounded_sources": grounded_sources[:4], "steps": steps}


def self_check() -> dict[str, Any]:
    """Consistency over the flow log + lattice wiring (what's reachable)."""
    n = 0
    if FLOW_LOG.is_file():
        n = sum(1 for l in FLOW_LOG.read_text(encoding="utf-8", errors="replace").splitlines() if l.strip())
    lat = lattice()
    return {"ok": True, "schema": SCHEMA, "n_flows": n,
            "gpu_source": (lat.get("gpu") or {}).get("source"),
            "bus_channels": len(lat.get("bus_channels") or []),
            "knot_tail": len(lat.get("knot_tail") or [])}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="mem-lands")
    ap.add_argument("cmd", nargs="?", default="self_check",
                    choices=["read", "flow", "lattice", "self_check"])
    ap.add_argument("--ctx", default="")
    ap.add_argument("--label", default="")
    ap.add_argument("--content", default="")
    ap.add_argument("--k", type=int, default=6)
    args = ap.parse_args(argv)
    if args.cmd == "read":
        print(json.dumps(read(args.ctx, k=args.k), indent=2, default=str))
    elif args.cmd == "flow":
        print(json.dumps(flow(args.label, args.content, ctx=args.ctx), indent=2, default=str))
    elif args.cmd == "lattice":
        print(json.dumps(lattice(), indent=2, default=str))
    else:
        print(json.dumps(self_check(), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
