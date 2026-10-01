"""Three-track autopilot: improve -> queue, governor cycle, seed-mirror status."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT


def _seed_mirror_status() -> dict[str, Any]:
    """Brain track: republic soil readiness (no training without operator drop)."""
    republic = ROOT.parent / "mycelial-republic"
    raw_dir = republic / "data" / "raw"
    train_jsonl = republic / "data" / "train" / "train.jsonl"
    annotated = republic / "data" / "annotated" / "mirror_train.jsonl"
    archives = list(raw_dir.glob("*.zip")) if raw_dir.is_dir() else []
    return {
        "republic_root": str(republic) if republic.is_dir() else None,
        "w0_archive": len(archives) > 0,
        "archive_files": [a.name for a in archives[:5]],
        "annotated_rows": (
            sum(1 for _ in annotated.open(encoding="utf-8", errors="replace"))
            if annotated.is_file()
            else 0
        ),
        "train_jsonl_rows": (
            sum(1 for _ in train_jsonl.open(encoding="utf-8", errors="replace"))
            if train_jsonl.is_file()
            else 0
        ),
        "blocked": len(archives) == 0,
        "hint": (
            "Drop X archive in mycelial-republic/data/raw/ then run train/prepare.py"
            if len(archives) == 0
            else "Archive present — run prepare + qlora"
        ),
    }


def _top_improve_candidates(limit: int = 3) -> list[dict[str, Any]]:
    from mag.improve import read_candidates

    rows = read_candidates(limit=200)
    feasible = [
        r for r in rows
        if r.get("feasible") is not False and float(r.get("score") or 0) >= 10
    ]
    feasible.sort(key=lambda r: float(r.get("score") or 0), reverse=True)
    return feasible[:limit]


def autopilot_once(
    *,
    queue_improve: bool = True,
    governor: bool = True,
    drain: bool = False,
    max_queue: int = 2,
) -> dict[str, Any]:
    """Run one parallel-friendly autopilot pass (brain + loop tracks)."""
    out: dict[str, Any] = {
        "schema": "autopilot.v1",
        "ts": datetime.now(timezone.utc).isoformat(),
        "steps": [],
    }

    out["seed_mirror"] = _seed_mirror_status()
    out["steps"].append({"seed_mirror": out["seed_mirror"].get("hint")})

    queued: list[dict[str, Any]] = []
    if queue_improve:
        try:
            from mag.governor_autorun import enqueue_routed

            for cand in _top_improve_candidates(max_queue):
                claim = str(cand.get("claim") or cand.get("id") or "")[:300]
                if not claim:
                    continue
                goal = f"[improve] {claim}"
                rec = enqueue_routed(goal, tag=f"improve-{cand.get('id', '')[:12]}")
                if rec.get("ok") is not False or rec.get("queue_id"):
                    queued.append(rec)
            out["queued"] = queued
            out["steps"].append({"queue_improve": f"queued {len(queued)}"})
        except Exception as e:
            out["steps"].append({"queue_improve": f"error: {e}"})

    if drain and queued:
        try:
            from mag.orchestrator import drain_once

            d = drain_once()
            out["drain"] = d
            out["steps"].append({"drain": d.get("action")})
        except Exception as e:
            out["steps"].append({"drain": f"error: {e}"})

    if governor:
        try:
            from mag.governor import run_cycle

            cyc = run_cycle(dry=False)
            out["governor"] = cyc
            out["steps"].append({"governor": f"{cyc.get('action')} ok={cyc.get('ok')}"})
        except Exception as e:
            out["steps"].append({"governor": f"error: {e}"})

    out["ok"] = True
    log = ROOT / "logs" / "autopilot_latest.json"
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    return out
