"""self_train_data — the dogfooding capability: fold our OWN sovereign output into labeled
training data, hitting the coldest vertex (the weight-train starved for data).

Operator (2026-08-12): "expand our capabilities in ways only you know how to do mapped to our
humble beginnings and start that exponential growth... or at least mapping to its coldest vertex."

THE COLDEST VERTEX (measured from the idea graph): W0.0b — the boot-soil annotate / weight-train
pipeline is BLOCKED at 52/100 posts because SOURCE DATA is exhausted. The compounding learning
loop is starved for data and waits on the operator's archive. That is the neglected cold node.

THE CAPABILITY ONLY THIS SYSTEM CAN BUILD (the dogfooding loop): turn our OWN activity into
training data. Every swarm result, folded RIB, tesuji shell, and session learning is already
labeled by the work we did. The system GENERATES its own training rows instead of waiting. This
maps to the humble beginnings (the loop learning from its own activity) and STARTS the exponential
growth: each cycle produces data -> trains the model -> produces more data.

Schema: self_train_data.v1 · deterministic + $0 · REAL sources (never fabricated rows).
Row shape (clean labeled contract, not a fabricated pipeline format):
  {"source", "input", "output"}  — input = the goal/context, output = the folded insight/tesuji.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT, RESULTS_DIR
except Exception:
    ROOT = Path(__file__).resolve().parent.parent
    RESULTS_DIR = ROOT / "memory" / "runs" / "swarm_worker" / "results"

sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCHEMA = "self_train_data.v1"
OUT = ROOT / "memory" / "train_data" / "self_generated.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _read_jsonl(p: Path, tail: int = 400) -> list[dict[str, Any]]:
    if not p.is_file():
        return []
    out = []
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines()[-tail:]:
        line = line.strip()
        if not line:
            continue
        try:
            o = json.loads(line)
            if isinstance(o, dict):
                out.append(o)
        except Exception:
            continue
    return out


def _from_swarm_results() -> list[dict[str, Any]]:
    """Real training rows from the swarm's returned results (the internet waves folding back)."""
    rows = []
    if not RESULTS_DIR.is_dir():
        return rows
    for p in sorted(RESULTS_DIR.glob("sw-*.json"))[:80]:
        try:
            r = json.loads(p.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        answer = (r.get("answer") or r.get("result") or r.get("summary") or "")[:600]
        if not answer:
            continue
        rows.append({"source": f"swarm:{p.stem}",
                     "input": (r.get("goal") or r.get("task") or "")[:400],
                     "output": answer})
    return rows


def _from_tesuji_shells() -> list[dict[str, Any]]:
    """Real training rows from the tesuji ledger (emergent wins)."""
    rows = []
    for s in _read_jsonl(ROOT / "logs" / "tesuji_shells.jsonl"):
        w = (s.get("what") or "").strip()
        if not w:
            continue
        rows.append({"source": "tesuji_shell",
                     "input": f"surprise: {(s.get('surprise') or '')[:300]}",
                     "output": w[:600]})
    return rows


def _from_rib_bus() -> list[dict[str, Any]]:
    """Real training rows from the breeding ground (the standing wave's RIBs)."""
    rows = []
    try:
        from mag import rib_bus
        for dom in ("general", "titor-rib-attractor", "titor-worldline", "game", "swarm"):
            try:
                for r in rib_bus.mount(dom).get("ribs", []):
                    rows.append({"source": f"rib:{dom}", "input": f"a RIB for {dom}",
                                 "output": r[:600]})
            except Exception:
                continue
    except Exception:
        pass
    return rows


def gather() -> list[dict[str, Any]]:
    """Gather ALL real sovereign output into labeled training rows (dogfooding)."""
    return (_from_swarm_results() + _from_tesuji_shells() + _from_rib_bus())


def fold() -> dict[str, Any]:
    """Fold the gathered rows into the self-generated training data (append, dedupe by content).
    Reports the real count toward the data gate. Deterministic + $0."""
    rows = gather()
    existing = _read_jsonl(OUT, tail=5000)
    seen = {(r.get("output") or "")[:200] for r in existing}
    new = []
    for r in rows:
        key = (r.get("output") or "")[:200]
        if key and key not in seen:
            r["ts"] = _now()
            new.append(r)
            seen.add(key)
    if new:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        with OUT.open("a", encoding="utf-8") as f:
            for r in new:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return {"ok": True, "schema": SCHEMA, "gathered": len(rows), "folded_new": len(new),
            "total_in_log": len(existing) + len(new),
            "out_path": str(OUT.relative_to(ROOT)),
            "cold_vertex": ("W0.0b blocked at 52/100 on source data — this dogfoods OUR OWN output "
                            "as labeled training rows, unblocking the data gate without waiting "
                            "on the operator's archive"),
            "note": "the loop generates its own training data from its own activity — the "
                    "compounding (exponential) start: each cycle produces data -> trains -> more"}


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="self-train-data")
    ap.add_argument("cmd", nargs="?", default="fold", choices=["fold", "gather"])
    a = ap.parse_args(argv)
    if a.cmd == "gather":
        print(json.dumps({"schema": SCHEMA, "rows": gather()}, ensure_ascii=False, indent=2, default=str))
    else:
        print(json.dumps(fold(), ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
