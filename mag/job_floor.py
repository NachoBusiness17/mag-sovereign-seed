"""Job floor — DFHack-style designation manager (layered on the orchestrator).

DFHack turns vague goals into DESIGNATIONS (precise, queued work dwarves execute
mechanically) and manages the job lifecycle with stuck-job recovery. Same here:

  designated → claimed → executing → verifying → done | needs_escalate
                                          ↘ stuck (watchdog) → escalate

A job_floor job is a designation: it binds a frozen SPEC + base fingerprints
(spec_gate) + target files + a seat. The orchestrator queue still spawns the
actual sub-agents; the floor is the discipline layer that refuses vague work,
verifies against the world, and re-designates stuck jobs.

Usage:
  python main.py job-floor create --goal "..." --seat local --spec <path>
  python main.py job-floor claim <id> | verify <id> --ok|--fail <detail>
  python main.py job-floor status | list | stuck [--max-s 600]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT

FLOOR_DIR = ROOT / "memory" / "runs" / "job_floor"
JOBS_PATH = FLOOR_DIR / "jobs.json"

STATES = ("designated", "claimed", "executing", "verifying", "done", "needs_escalate", "stuck", "cancelled")
TERMINAL = {"done", "needs_escalate", "stuck", "cancelled"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load() -> dict[str, Any]:
    if not JOBS_PATH.is_file():
        return {"schema": "job_floor.v1", "jobs": {}}
    try:
        data = json.loads(JOBS_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {"schema": "job_floor.v1", "jobs": {}}
    except Exception:
        return {"schema": "job_floor.v1", "jobs": {}}


def _save(data: dict[str, Any]) -> None:
    JOBS_PATH.parent.mkdir(parents=True, exist_ok=True)
    JOBS_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def create_job(
    goal: str,
    *,
    seat: str = "local",
    spec_path: str | None = None,
    targets: list[str] | None = None,
    max_s: float = 600.0,
) -> dict[str, Any]:
    """Designate a job. If targets given, freeze their base fingerprints so the
    wrong-offset gate can refuse a blind apply later."""
    jid = f"job-{uuid.uuid4().hex[:12]}"
    bases: dict[str, Any] = {}
    if targets:
        from mag.spec_gate import freeze

        for t in targets:
            f = freeze(t, label=goal[:60])
            bases[str(Path(t).resolve())] = f.get("sha")
    rec = {
        "id": jid,
        "goal": goal[:500],
        "seat": seat,
        "spec_path": spec_path,
        "targets": [str(Path(t).resolve()) for t in (targets or [])],
        "bases": bases,
        "state": "designated",
        "created": _now(),
        "claimed_at": None,
        "finished_at": None,
        "max_s": max_s,
        "attempts": 0,
        "detail": "",
    }
    data = _load()
    data.setdefault("jobs", {})[jid] = rec
    _save(data)
    return rec


def _job(jid: str) -> dict[str, Any] | None:
    return (_load().get("jobs") or {}).get(jid)


def _update(jid: str, **fields: Any) -> dict[str, Any] | None:
    data = _load()
    job = (data.get("jobs") or {}).get(jid)
    if job is None:
        return None
    job.update(fields)
    _save(data)
    return job


def claim_job(jid: str) -> dict[str, Any]:
    """Claim a designated job for a seat → executing."""
    job = _job(jid)
    if not job:
        return {"ok": False, "error": "no such job"}
    if job["state"] not in ("designated", "claimed"):
        return {"ok": False, "error": f"cannot claim from state {job['state']}"}
    job = _update(jid, state="executing", claimed_at=_now(), attempts=int(job.get("attempts") or 0) + 1)
    return {"ok": True, "job": job}


def verify_job(jid: str, *, ok: bool, detail: str = "") -> dict[str, Any]:
    """Verification result: done on ok, else needs_escalate."""
    job = _job(jid)
    if not job:
        return {"ok": False, "error": "no such job"}
    if job["state"] not in ("executing", "verifying"):
        return {"ok": False, "error": f"cannot verify from state {job['state']}"}
    state = "done" if ok else "needs_escalate"
    job = _update(jid, state=state, finished_at=_now(), detail=detail[:300])
    # The exact-right-time hook: release any skill drops queued for this job's
    # completion so the agent picks them up at the next checkpoint (puppeteer
    # handoff). Lazy import to avoid a circular dep.
    if state == "done":
        try:
            from mag.skill_drop import release_due

            release_due(job_state="done", job_id=jid)
        except Exception:
            pass
    return {"ok": True, "job": job}


def stuck_jobs(*, max_s: float | None = None) -> list[dict[str, Any]]:
    """Watchdog: executing jobs past their budget → stuck (re-designate)."""
    now = time.time()
    out: list[dict[str, Any]] = []
    for j in (_load().get("jobs") or {}).values():
        if j.get("state") != "executing":
            continue
        started = j.get("claimed_at")
        jm = j.get("max_s")
        budget = float(jm if jm is not None else (max_s if max_s is not None else 600.0))
        if started:
            try:
                t0 = datetime.fromisoformat(str(started)).timestamp()
            except Exception:
                t0 = now
            if now - t0 > budget:
                _update(str(j["id"]), state="stuck", finished_at=_now(), detail=f"watchdog: >{budget}s executing")
                out.append(j)
    return out


def status() -> dict[str, Any]:
    from collections import Counter

    jobs = (_load().get("jobs") or {}).values()
    counts = Counter(str(j.get("state")) for j in jobs)
    return {
        "ok": True,
        "schema": "job_floor.v1",
        "total": len(jobs),
        "by_state": dict(counts),
        "path": str(JOBS_PATH),
    }


def list_jobs(*, limit: int = 40) -> list[dict[str, Any]]:
    jobs = sorted((_load().get("jobs") or {}).values(), key=lambda j: str(j.get("created")), reverse=True)
    return jobs[:limit]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="job-floor")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_c = sub.add_parser("create")
    p_c.add_argument("--goal", required=True)
    p_c.add_argument("--seat", default="local")
    p_c.add_argument("--spec", default="")
    p_c.add_argument("--target", action="append", default=[])
    p_c.add_argument("--max-s", type=float, default=600.0)
    p_claim = sub.add_parser("claim")
    p_claim.add_argument("id")
    p_v = sub.add_parser("verify")
    p_v.add_argument("id")
    p_v.add_argument("--ok", action="store_true")
    p_v.add_argument("--fail", action="store_true")
    p_v.add_argument("--detail", default="")
    p_s = sub.add_parser("stuck")
    p_s.add_argument("--max-s", type=float, default=600.0)
    sub.add_parser("status")
    sub.add_parser("list")
    args = ap.parse_args(argv)

    if args.cmd == "create":
        print(json.dumps(create_job(args.goal, seat=args.seat, spec_path=args.spec or None, targets=args.target, max_s=args.max_s), indent=2))
    elif args.cmd == "claim":
        print(json.dumps(claim_job(args.id), indent=2, default=str))
    elif args.cmd == "verify":
        if args.ok == args.fail:
            print("specify exactly one of --ok / --fail", file=sys.stderr)
            return 2
        print(json.dumps(verify_job(args.id, ok=args.ok, detail=args.detail), indent=2, default=str))
    elif args.cmd == "stuck":
        print(json.dumps(stuck_jobs(max_s=args.max_s), indent=2, default=str))
    elif args.cmd == "status":
        print(json.dumps(status(), indent=2))
    elif args.cmd == "list":
        print(json.dumps(list_jobs(), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
