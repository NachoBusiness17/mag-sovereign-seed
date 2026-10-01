"""Skill drop — timed, frozen, right-sized skill breadcrumbs.

The puppeteer rig's remote handoff: a remote seat / operator / assistant preps
a skill OFFLINE (right-sized to a bootloader-style nugget, frozen by sha256),
queues it, and RELEASES it at the exact right time — when the agent finishes
its current task (job_floor verify → done) — as an operator_inbox breadcrumb
the agent drains at the next checkpoint.

Lifecycle:
  drop_skill(...)   right-size (≤200-token nugget) → freeze (sha256) → queue
  release_due(...)  called from job_floor on verify→done → commit_guidance
                    (source="skill-drop") → drained at next checkpoint
  verify_drop(...)  the frozen hash still matches → trust bytes, not reports

CLI:  python -m mag.skill_drop add|status|release|verify
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from config import ROOT  # noqa: E402

DROPS_PATH = ROOT / "memory" / "working" / "skill_drops.json"
NUGGET_LIMIT = 200


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load() -> dict[str, Any]:
    if not DROPS_PATH.is_file():
        return {"schema": "skill_drop.v1", "drops": []}
    try:
        data = json.loads(DROPS_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {"schema": "skill_drop.v1", "drops": []}
    except (json.JSONDecodeError, OSError):
        return {"schema": "skill_drop.v1", "drops": []}


def _save(data: dict[str, Any]) -> None:
    DROPS_PATH.parent.mkdir(parents=True, exist_ok=True)
    DROPS_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def right_size(content: str, *, limit: int = NUGGET_LIMIT) -> str:
    """Quantize to a bootloader-scale nugget: first intent line + a verify tail.
    Always reserves room for the tail so the actionable bit survives truncation."""
    text = (content or "").strip()
    if len(text) <= limit:
        return text
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    head = lines[0] if lines else ""
    tail = ""
    for l in lines[1:]:
        if re.search(r"\b(verify|check|test|assert|rollback|how|pass if)\b", l.lower()):
            tail = l
            break
    if tail:
        head = head[:max(0, limit - len(tail) - 3)]
        return (head + " | " + tail).strip()[:limit]
    return head[:limit]


def freeze(content: str) -> str:
    return hashlib.sha256((content or "").encode("utf-8")).hexdigest()


def verify_drop(drop_id: str) -> dict[str, Any]:
    for d in _load().get("drops") or []:
        if d.get("id") == drop_id:
            ok = freeze(str(d.get("content") or "")) == d.get("sha256")
            return {"ok": ok, "id": drop_id, "name": d.get("name"),
                    "note": "frozen bytes intact — safe to apply" if ok
                            else "DRIFT: nugget no longer matches frozen hash"}
    return {"ok": False, "id": drop_id, "error": "no such drop"}


def drop_skill(
    name: str,
    content: str,
    *,
    source: str = "remote",
    drop_when: str = "job_done",
    job_id: str | None = None,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    nugget = right_size(content)
    if not nugget:
        return {"ok": False, "error": "empty skill"}
    if drop_when not in ("job_done", "checkpoint"):
        return {"ok": False, "error": f"drop_when must be job_done|checkpoint, got {drop_when}"}
    rec = {
        "id": f"skill-{uuid.uuid4().hex[:10]}",
        "name": (name or "untitled")[:80],
        "content": nugget,
        "sha256": freeze(nugget),
        "source": source[:40],
        "drop_when": drop_when,
        "job_id": job_id,
        "tags": [str(t)[:40] for t in (tags or [])[:8]],
        "state": "queued",
        "created": _now(),
        "released_at": None,
    }
    data = _load()
    data.setdefault("drops", []).append(rec)
    _save(data)
    return {"ok": True, "drop": rec, "chars": len(nugget), "frozen": rec["sha256"][:12]}


def release_due(*, job_state: str, job_id: str | None = None) -> list[dict[str, Any]]:
    """Release queued drops whose condition is met — call at the JOB BOUNDARY
    (job_floor verify→done), not at every checkpoint."""
    from mag.operator_inbox import commit_guidance

    data = _load()
    drops = data.get("drops") or []
    released: list[dict[str, Any]] = []
    for d in drops:
        if d.get("state") != "queued":
            continue
        if d.get("drop_when") == "job_done":
            if job_id and d.get("job_id") and d.get("job_id") != job_id:
                continue
            if job_state not in ("done", "verifying", "needs_escalate", "stuck"):
                continue
        text = f"[SKILL DROP — {d.get('name')}] {d.get('content')}"
        r = commit_guidance(text, source="skill-drop")
        if r.get("ok"):
            d["state"] = "released"
            d["released_at"] = _now()
            released.append(d)
    _save(data)
    return released


def status() -> dict[str, Any]:
    drops = _load().get("drops") or []
    counts = Counter(str(d.get("state")) for d in drops)
    return {
        "ok": True,
        "schema": "skill_drop.v1",
        "total": len(drops),
        "by_state": dict(counts),
        "queued": [{"id": d["id"], "name": d.get("name"), "drop_when": d.get("drop_when"),
                    "job_id": d.get("job_id"), "chars": len(d.get("content") or ""),
                    "frozen": (d.get("sha256") or "")[:12]} for d in drops if d.get("state") == "queued"],
        "path": str(DROPS_PATH),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="skill-drop", description="Timed, frozen, right-sized skill breadcrumbs.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_add = sub.add_parser("add", help="queue a skill drop")
    p_add.add_argument("name")
    p_add.add_argument("content")
    p_add.add_argument("--source", default="remote")
    p_add.add_argument("--drop-when", default="job_done", choices=["job_done", "checkpoint"])
    p_add.add_argument("--job-id", default=None)
    p_add.add_argument("--tag", action="append")
    sub.add_parser("status", help="show queued drops")
    p_rel = sub.add_parser("release", help="release due drops for a job state")
    p_rel.add_argument("--job-state", default="done")
    p_rel.add_argument("--job-id", default=None)
    p_ver = sub.add_parser("verify", help="verify a drop's frozen hash")
    p_ver.add_argument("id")
    args = ap.parse_args(argv)

    if args.cmd == "add":
        r = drop_skill(args.name, args.content, source=args.source, drop_when=args.drop_when,
                       job_id=args.job_id, tags=args.tag)
        print(json.dumps(r, indent=2, ensure_ascii=False))
    elif args.cmd == "status":
        print(json.dumps(status(), indent=2, ensure_ascii=False))
    elif args.cmd == "release":
        out = release_due(job_state=args.job_state, job_id=args.job_id)
        print(json.dumps({"released": len(out), "drops": [d["id"] for d in out]}, indent=2))
    elif args.cmd == "verify":
        print(json.dumps(verify_drop(args.id), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
