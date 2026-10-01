"""Bounded, non-interactive research seat for cheap local reconciliation work.

The generic ``main.py agent`` seat carries a large tool schema, an interactive
steering listener, and a multi-round context loop. That is appropriate for an
operator-facing coding seat, not for a small self-steal research receipt on a
CPU Ollama lane. This worker performs one plain, capped model call and writes
one durable artifact, then exits.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT
from models.providers import chat_provider


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _mail(**fields: Any) -> None:
    task_id = os.environ.get("MAG_TASK_ID", "").strip()
    if not task_id:
        return
    try:
        from mag import pigeonhole

        pigeonhole.write_status(task_id, **fields)
        pigeonhole.heartbeat(task_id, **fields)
    except Exception:
        pass


def _safe_name(value: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9_.-]+", "_", value or "research")
    return clean[:100] or "research"


def run(goal: str, *, provider: str = "ollama", model: str | None = None) -> dict[str, Any]:
    if not model:
        model = "gemma:2b" if provider == "ollama" else None
    task_id = os.environ.get("MAG_TASK_ID", "research-standalone")
    _mail(phase="started", worker="bounded-research", goal=goal[:240])
    system = (
        "You are a bounded research worker inside a sovereign codebase. "
        "Do not claim to have edited files or contacted external services. "
        "Return a compact, evidence-aware plan (at most 500 words) with exactly "
        "these headings: FINDING, EVIDENCE, NEXT ACTION, UNKNOWN. "
        "Separate verified facts from proposals. Prefer concrete repository paths, "
        "commands, acceptance tests, and explicit blockers."
    )
    try:
        response = chat_provider(
            provider,
            system,
            goal,
            model=model,
            temperature=0.1,
            max_tokens=700,
            tier="T1",
            session_id=task_id,
            timeout=240,
        )
    except Exception as exc:
        response = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    text = str(response.get("text") or "").strip()
    ok = bool(response.get("ok") and text)
    out_dir = ROOT / "memory" / "runs" / "research_worker"
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = _safe_name(task_id)
    artifact = out_dir / f"{stem}.md"
    receipt = out_dir / f"{stem}.json"
    if ok:
        body = (
            f"# Bounded Research Receipt\n\n"
            f"- task: `{task_id}`\n- provider: `{provider}`\n- model: `{model}`\n"
            f"- ts: `{_now()}`\n- goal: {goal}\n\n{text}\n"
        )
        artifact.write_text(body, encoding="utf-8")
    result = {
        "schema": "research_worker.receipt.v1",
        "ok": ok,
        "task_id": task_id,
        "provider": provider,
        "model": model,
        "goal": goal[:500],
        "artifact": str(artifact) if ok else None,
        "error": None if ok else str(response.get("error") or "empty model response")[:300],
        "ts": _now(),
    }
    receipt.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    _mail(phase="done" if ok else "failed", exit_code=0 if ok else 1,
          artifact=str(artifact) if ok else "", error=result.get("error") or "")
    print(json.dumps(result, ensure_ascii=False), flush=True)
    return result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="mag.research_worker")
    ap.add_argument("--goal", required=True)
    ap.add_argument("--provider", default="ollama")
    ap.add_argument("--model", default=None)
    args = ap.parse_args(argv)
    result = run(args.goal, provider=args.provider, model=args.model)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
