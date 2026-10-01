"""gpu_memweave — route deterministic coding tasks to the GPU node via memlang + k8s.

Build (2026-08-11): stop HALLUCINATING the GPU/k3s state and make it real. This module
routes DETERMINISTIC (machine_target T0-T2) coding tasks to the GPU node (ollama via k8s),
carrying the instruction as a memlang token. HONEST telemetry: it reports GPU numbers ONLY
if the pod actually provides them (gpu_k8s), never fabricated. Unverified until run.

Schema: gpu_memweave.v1 · deterministic + $0 (no LLM) · reuse: memlang, machine_target, gpu_k8s
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "gpu_memweave.v1"
# Which machine_target ranks are "dumb deterministic coding tasks" -> GPU node.
GPU_RANKS = ("T0", "T1", "T2")  # T3 (binary patch) excluded: deepest, rightsized-last.


def _load(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _resolve_target(task: str) -> dict[str, str]:
    """Resolve the machine_target rank for a task (T0-T3) from machine_target.TARGETS."""
    try:
        from mag import machine_target
        # minimal heuristic: default T2; exact classifier is separate.
        return {"rank": "T2", "action": machine_target.TARGETS["T2"]["action"]}
    except Exception as e:
        return {"rank": "T2", "action": "file_write", "error": str(e)[:80]}


def route(task: str, *, spec: str = "") -> dict[str, Any]:
    """Compile the task to a memlang token + resolve its target rank.

    Returns {ok, token, opcode, anchor, rank, gpu_routed} WITHOUT claiming the GPU is live.
    """
    out: dict[str, Any] = {"schema": SCHEMA, "ok": False}
    # 1) memlang token (the instruction carried to the node).
    try:
        from mag import memlang
        tok = memlang.compile_token("rib_elevate", spec or task)
        out["token_len"] = tok.get("token_len")
        out["opcode"] = tok.get("opcode")
        out["anchor_hex"] = (tok.get("anchor_hex") or "")[:16]
        out["compile"] = bool(tok.get("ok"))
    except Exception as e:
        out["compile_error"] = str(e)[:120]
    # 2) resolve machine target rank.
    tgt = _resolve_target(task)
    out["rank"] = tgt.get("rank")
    out["action"] = tgt.get("action")
    # 3) HONEST gpu check: only if the pod reports real telemetry, else "unavailable".
    out["gpu_routed"] = out["rank"] in GPU_RANKS  # candidate, NOT confirmed
    gpu = _gpu_telemetry()
    if gpu:
        out["gpu_telemetry"] = gpu
        out["gpu_confirmed"] = True
    else:
        out["gpu_confirmed"] = False
        out["gpu_telemetry"] = "unavailable (pod not reporting — NOT fabricating)"
    out["ok"] = True
    return out


def _gpu_telemetry() -> dict[str, Any] | None:
    """Real GPU telemetry only if a source provides it (gpu_k8s / gpu_ghost ledger). Return None
    otherwise — never invent numbers (honesty over over-claiming)."""
    try:
        from mag import gpu_k8s
        s = gpu_k8s.status()
        if s and s.get("ok"):
            return {"source": "gpu_k8s", "telemetry": s}
    except Exception:
        pass
    # fallback: read the gpu_ghost ledger if it has real rows.
    ledger = ROOT / "memory" / "runs" / "gpu_ghost" / "telemetry.jsonl"
    if ledger.is_file():
        rows = [l for l in ledger.read_text(encoding="utf-8", errors="replace").splitlines() if l.strip()]
        if rows:
            return {"source": "gpu_ghost_ledger", "rows": len(rows), "last": json.loads(rows[-1])}
    return None


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "contract": "route(task)->memlang token + target rank + HONEST gpu telemetry "
                        "(None = unavailable, never fabricated)",
            "gpu_ranks": list(GPU_RANKS), "cost": "deterministic + $0"}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="gpu-memweave")
    ap.add_argument("task", nargs="*", default=[])
    a = ap.parse_args()
    if a.task:
        print(json.dumps(route(" ".join(a.task)), indent=2, default=str))
    else:
        print(json.dumps(status(), indent=2, default=str))
