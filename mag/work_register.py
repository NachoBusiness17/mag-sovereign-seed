"""work_register — the k8s-ADDRESSED recall surface: every piece done via the mem tools is folded
as a content-addressed verkle knot + a shared durable manifest (on the PVC), so ANY seat/fleet
recalls "everything done easily" instead of the operator having to keep telling us to use the tools.

Operator (2026-08-11): "this is something the k8's should be addressing" (re: remembering mem-tool
work easily, not handwaving). This makes recall INFRASTRUCTURE: the work register lives on the chain
(verkle knots) + a shared manifest (memory/runs/work_register/manifest.jsonl, on the mag-state PVC),
not an ephemeral session file.

Contract: work_register.v1 · deterministic · $0 · content-addressed (verkle) + durable (PVC manifest).
CLI: python -m mag.work_register record <kind> <label> [--path X] [--note N] | recall [--kind K] | backfill | status
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

SCHEMA = "work_register.v1"
MANIFEST = ROOT / "memory" / "runs" / "work_register" / "manifest.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _read_jsonl(path: Path, tail: int = 1000) -> list[dict[str, Any]]:
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


def record(kind: str, label: str, *, path: str = "", note: str = "",
            claim: dict | None = None) -> dict[str, Any]:
    """Fold one finished piece into the durable work register (verkle knot + shared manifest).

    claim (2026-08-25, the sharp edge): an optional tri-state claim
    {statement, status, basis, evidence} run through the vendored AOS integrity kernel
    BEFORE it lands — a claim that doesn't validate (e.g. Supported without Evidence)
    is degraded to Unproven, never over-claimed. Every fold CAN carry its status, and
    the ledger (logs/claims.jsonl) records what was claimed and on what basis.
    """
    kind = (kind or "work").strip().lower()
    label = (label or "").strip()
    if not label:
        return {"ok": False, "error": "label required"}
    row = {"ts": _now(), "schema": SCHEMA, "kind": kind, "label": label,
           "path": path, "note": note[:300]}
    # 0) the claim, if any — kernel-validated (never over-claims) + ledgered
    if claim and isinstance(claim, dict):
        try:
            from mag.integrity_kernel import tri_state
            c = tri_state(str(claim.get("statement") or label),
                          status=str(claim.get("status") or "Unproven"),
                          basis=tuple(claim.get("basis") or ("Assumption",)),
                          evidence=tuple(claim.get("evidence") or ()))
            row["claim"] = c
            _append_jsonl(Path(__file__).resolve().parents[1] / "logs" / "claims.jsonl",
                          {"ts": _now(), "kind": kind, "label": label, "claim": c})
        except Exception as e:
            row["claim_error"] = str(e)[:80]
    # 1) content-addressed verkle knot (the chain = durable, recallable by any seat)
    try:
        from mag.verkle_knot import append_verkle_knot
        knot = append_verkle_knot({"session_id": f"work:{kind}:{datetime.now(timezone.utc).strftime('%H%M%S%f')}",
                                   "theme": "doctrine",
                                   "summary": f"[work_register:{kind}] {label}{(' — ' + note[:120]) if note else ''}"})
        row["verkle"] = bool(knot.get("ok"))
    except Exception as e:
        row["verkle"] = False
        row["verkle_error"] = str(e)[:80]
    # 2) shared manifest (on the PVC -> k8s/fleet-readable, survives this PC/session)
    _append_jsonl(MANIFEST, row)
    return {"ok": True, "row": row}


def recall(*, kind: str | None = None) -> dict[str, Any]:
    """Query the register: everything done via mem tools, easily recallable."""
    rows = _read_jsonl(MANIFEST)
    if kind:
        rows = [r for r in rows if r.get("kind") == kind]
    by_kind: dict[str, int] = {}
    for r in _read_jsonl(MANIFEST):
        by_kind[r.get("kind", "work")] = by_kind.get(r.get("kind", "work"), 0) + 1
    return {"schema": SCHEMA, "ts": _now(), "n": len(rows), "by_kind": by_kind,
            "rows": [{"ts": r.get("ts"), "kind": r.get("kind"), "label": r.get("label"),
                      "path": r.get("path"), "note": r.get("note"), "verkle": r.get("verkle")}
                     for r in rows]}


def backfill() -> dict[str, Any]:
    """Fold tonight's mem-tool work into the register so the fleet recalls it NOW."""
    entries = [
        ("module", "grok_rightsize.call_grok_free fix", "mag/grok_rightsize.py", "fallback to two-key API"),
        ("module", "gpu_k8s", "mag/gpu_k8s.py", "GPU telemetry from k8s -> verkle"),
        ("module", "grok_frontier_loop", "mag/grok_frontier_loop.py", "budget-gated frontier steals"),
        ("module", "grok_hub", "mag/grok_hub.py", "centralized grok-4.5 grouping router"),
        ("module", "doctor_rightsize", "mag/doctor_rightsize.py", "distribute oversized code"),
        ("module", "mem_weave_distributor", "mag/mem_weave_distributor.py", "distribute everywhere"),
        ("module", "feedback", "mag/feedback.py", "our 👍/👎 -> training/ranking/verkle"),
        ("steal", "GROK_SURFACE_FAILOVER_STEAL", "memory/steal/", "grok fallback"),
        ("steal", "STEAL_EMBED_STEAL_PROTOCOL_STATELESS_PUPPET", "memory/steal/", "puppeteering"),
        ("steal", "STEAL_IMPROVE_GHOST_TRAIN_TESUJI", "memory/steal/", "feature roadmap"),
        ("steal", "DESIGN_GROK45_HUB_DEEPSEEK_SWARM", "memory/steal/", "hub->swarm"),
        ("steal", "STEAL_RIB_DEBUG_EVERY_PIECE", "memory/steal/", "verify vs RIB"),
        ("steal", "DEEP_RESEARCH_SYNTHESIS_CODE_IS_LAW", "memory/steal/", "lessig lattice"),
        ("steal", "DEEP_RESEARCH_INVARIANT_SHAPING_QUEUE", "memory/steal/", "invariant shaping"),
        ("directive", "!ghost=steal+debug", "memory/repo/operator-shorthand-map.md", "standing"),
        ("directive", "!training=debug vs RIB", "memory/repo/operator-shorthand-map.md", "standing"),
        ("directive", "going-to-bed=just-execute", "memory/routing.md", "standing"),
        ("directive", "steal-before-answering", "memory/routing.md", "trick lesson"),
        ("grant", "autonomous-invention-loop", "memory/repo/autonomous-invention-grant.md", "run+invent while away"),
    ]
    done = []
    for kind, label, path, note in entries:
        done.append(record(kind, label, path=path, note=note))
    return {"ok": True, "schema": SCHEMA, "backfilled": len(done)}


def status() -> dict[str, Any]:
    rows = _read_jsonl(MANIFEST)
    return {"schema": SCHEMA, "n": len(rows), "manifest": str(MANIFEST),
            "last": rows[-1] if rows else None}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="work-register",
                                 description="k8s-addressed recall: content-addressed record of mem-tool work.")
    sub = ap.add_subparsers(dest="cmd")
    p_rec = sub.add_parser("record")
    p_rec.add_argument("kind")
    p_rec.add_argument("label")
    p_rec.add_argument("--path", default="")
    p_rec.add_argument("--note", default="")
    p_rec = sub.add_parser("recall")
    p_rec.add_argument("--kind", default="")
    p_rec = sub.add_parser("backfill")
    p_rec = sub.add_parser("status")
    a = ap.parse_args(argv)
    if a.cmd == "record":
        print(json.dumps(record(a.kind, a.label, path=a.path, note=a.note), indent=2, default=str))
    elif a.cmd == "recall":
        print(json.dumps(recall(kind=a.kind or None), indent=2, default=str))
    elif a.cmd == "backfill":
        print(json.dumps(backfill(), indent=2, default=str))
    else:
        print(json.dumps(status(), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

__all__ = ["record", "recall", "backfill", "status", "main"]
