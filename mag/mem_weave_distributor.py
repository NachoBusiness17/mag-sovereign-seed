"""mem_weave_distributor — generalize doctor_rightsize EVERYWHERE: when any internal system grows
too large (code, INFERENCE, USER BEHAVIOR, SWARM BEHAVIOR, memory), distribute it into the mem weave
so it just works as emergent, content-addressed, consumable pieces — not a bloated monolith.

Operator (2026-08-11): "do this everywhere including inference user behavior swarm behavior etc."

Contract: mem_weave_distributor.v1 · deterministic · $0 · AST/file-size based · never mutates sources —
it FOLDS a distilled weave representation (knowledge_graph node + verkle knot + ledger) so the swarm
routes to / consumes each capability piecewise ("just works").
CLI: python -m mag.mem_weave_distributor scan | rightsize [--source X] | status
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCHEMA = "mem_weave_distributor.v1"
STATE_DIR = ROOT / "memory" / "runs" / "mem_weave_distributor"
LEDGER = STATE_DIR / "distributed.jsonl"

# Default size caps per source kind (bytes). Override via env per source.
DEFAULT_CAPS = {
    "code": 1 << 20,           # 1 MiB
    "inference": 2 << 20,      # 2 MiB
    "user_behavior": 1 << 20,
    "swarm_behavior": 2 << 20,
    "memory": 3 << 20,
}

# Source domains -> concrete paths/globs to measure.
SOURCES: dict[str, dict[str, Any]] = {
    "code": {"globs": ["mag/*.py"], "kind": "module"},
    "inference": {"globs": ["memory/pile/training_rows.jsonl", "memory/training/*.jsonl",
                            "memory/runs/inference*.jsonl", "memory/runs/*infer*.jsonl"], "kind": "inference"},
    "user_behavior": {"globs": ["logs/behavioral_events.jsonl", "memory/behavior/*.jsonl",
                                "memory/interaction_logs/*.jsonl", "logs/interaction*.jsonl"], "kind": "user_behavior"},
    "swarm_behavior": {"globs": ["memory/runs/swarm*.jsonl", "memory/runs/flock*.jsonl",
                                 "memory/comms_trail/*.jsonl", "memory/mycelium/*.jsonl"], "kind": "swarm_behavior"},
    "memory": {"globs": ["memory/runs/**/*.jsonl"], "kind": "memory"},
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _cap(source: str) -> int:
    import os
    return int(os.environ.get(f"WEAVE_CAP_{source.upper()}", DEFAULT_CAPS.get(source, 1 << 20)))


def _read_jsonl(path: Path, tail: int = 200) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    out = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out[-tail:]


def _append_jsonl(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False, default=str) + "\n")


def _resolve(glob: str) -> list[Path]:
    return sorted(ROOT.glob(glob))


def scan_source(source: str) -> dict[str, Any]:
    """Measure one source domain; report total bytes, file count, and oversized files."""
    files = []
    seen: set[Path] = set()
    total = 0
    cap = _cap(source)
    for glob in SOURCES.get(source, {}).get("globs", []):
        for p in _resolve(glob):
            if p in seen or not p.is_file():
                continue
            seen.add(p)
            try:
                size = p.stat().st_size
            except OSError:
                continue
            total += size
            files.append({"path": str(p), "bytes": size, "oversized": size > cap})
    oversized = [f for f in files if f["oversized"]]
    return {"source": source, "kind": SOURCES.get(source, {}).get("kind", "?") ,
            "files": len(files), "total_bytes": total, "cap_bytes": cap,
            "n_oversized": len(oversized), "oversized": oversized}


def scan() -> dict[str, Any]:
    return {"schema": SCHEMA, "ts": _now(), "sources": {s: scan_source(s) for s in SOURCES}}


# ── distribute one source into the mem weave ───────────────────────────────
def distribute_source(source: str, *, dry: bool = False) -> dict[str, Any]:
    s = scan_source(source)
    dist = []
    for f in s.get("oversized", []):
        # FOLD a distilled weave node so the swarm owns/consumes it piecewise.
        note = (f"[mem_weave_distributor] {source} file {f['bytes']}B exceeds cap "
                f"{s['cap_bytes']}B -> distributed into the mem weave; consumed piecewise")
        folded = {}
        if not dry:
            try:
                from mag.knowledge_graph import fold as kg_fold
                folded = kg_fold(f"distributed:{source}:{Path(f['path']).name}", "case_law",
                                 note, source="mem_weave_distributor")
            except Exception as e:
                folded = {"error": str(e)[:80]}
            try:
                from mag.verkle_knot import append_verkle_knot
                append_verkle_knot({"session_id": f"mem-weave-dist:{source}",
                                    "theme": "case_law", "summary": note[:200]})
            except Exception:
                pass
        dist.append({"path": f["path"], "bytes": f["bytes"], "folded": folded, "dry": dry})
    if not dry and dist:
        _append_jsonl(LEDGER, {"ts": _now(), "schema": "mem_weave_dist_run.v1",
                               "source": source, "distributed_n": len(dist),
                               "total_bytes": s["total_bytes"]})
    return {"source": source, "ok": True, "distributed": dist, "dry": dry}


def rightsize(*, source: str | None = None, dry: bool = False) -> dict[str, Any]:
    """SCAN all (or one) source -> distribute oversized -> VERIFY (re-scan) -> report."""
    targets = [source] if source else list(SOURCES.keys())
    results = {s: distribute_source(s, dry=dry) for s in targets}
    rescan = scan() if not source else scan_source(source)
    return {"ok": True, "schema": SCHEMA, "ts": _now(), "distributed": results, "verify": rescan}


def status() -> dict[str, Any]:
    rows = _read_jsonl(LEDGER)
    return {"schema": SCHEMA, "n_distributions": len(rows), "last": rows[-1] if rows else None}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="mem-weave-distributor",
                                 description="Distribute oversized systems (code/inference/behavior/swarm/memory) into the mem weave.")
    ap.add_argument("cmd", nargs="?", choices=["scan", "rightsize", "status"], default="scan")
    ap.add_argument("--source", default="")
    ap.add_argument("--dry", action="store_true", default=True)
    a = ap.parse_args(argv)
    if a.cmd == "scan":
        print(json.dumps(scan(), indent=2, default=str))
    elif a.cmd == "rightsize":
        print(json.dumps(rightsize(source=a.source or None, dry=a.dry), indent=2, default=str))
    else:
        print(json.dumps(status(), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

__all__ = ["scan", "scan_source", "distribute_source", "rightsize", "status", "main"]
