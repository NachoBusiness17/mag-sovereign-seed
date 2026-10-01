"""Cheap swarm — the EXPAND + EXECUTE half of the frontier-ghost tesuji.

RenderMan law: compact at the frontier, expand at the cheap. The frontier ghost
(mag/grok_terminal) BUILDS packages (`queue/handoff/GHOST-*.md`, or frozen
`BUILD-*.md` contracts); the CHEAP SWARM is what EXPANDS + EXECUTES them on the cheap
tier (deepseek-v4-flash / local) and folds the result back.

This module:
  1. `scan()`            — find ghost-built / frozen build packages not yet dispatched.
  2. `dispatch(pkg)`     — enqueue ONE package to the cheap tier (tag=cheap-swarm), so
                           the drainer's cheap model expands + implements the package.
  3. `run_cadence()`     — idempotent: scan + dispatch up to a daily cap, track dispatched.
  4. `status()`          — swarm state: pending, dispatched, done today, cost guard.

Cheap by construction (deepseek-v4-flash / local) + a daily cap so it can't runaway.
Schema: cheap_swarm.v1
CLI:  python -m mag.cheap_swarm scan | dispatch <pkg> | status | cadence
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
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

SCHEMA = "cheap_swarm.v1"
HANDOFF_DIR = ROOT / "queue" / "handoff"
STATE_DIR = ROOT / "memory" / "runs" / "cheap_swarm"
DISPATCHED = STATE_DIR / "dispatched.jsonl"
DEFAULT_MAX_PER_DAY = 6  # cheap but bounded — no runaway
# FREE-FIRST (2026-08-24): the cheap swarm runs on the free NVIDIA build lane — same
# flash model family (deepseek-ai/deepseek-v4-flash-0731), verified 3.4s, $0 build credits.
DEFAULT_MODEL = "deepseek-ai/deepseek-v4-flash-0731"
DEFAULT_PROVIDER = "nvidia"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _today() -> str:
    return date.today().isoformat()


def _packages() -> list[dict[str, Any]]:
    """Ghost-built + frozen BUILD packages on disk (GHOST-*.md and BUILD-*.md)."""
    out: list[dict[str, Any]] = []
    if not HANDOFF_DIR.is_dir():
        return out
    for p in sorted(HANDOFF_DIR.glob("*.md")):
        name = p.name
        if not (name.startswith("GHOST-") or name.startswith("BUILD-")):
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        out.append({
            "path": str(p),
            "name": name,
            "stem": p.stem,
            "kind": "ghost" if name.startswith("GHOST-") else "build",
            "goal": f"Execute build package {name}: expand the frozen spec and implement it under the repo.",
            "text_preview": text[:1200],
        })
    return out


def _dispatched_ids() -> set[str]:
    if not DISPATCHED.is_file():
        return set()
    out: set[str] = set()
    for line in DISPATCHED.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            out.add(str(json.loads(line).get("stem") or ""))
        except json.JSONDecodeError:
            continue
    return {x for x in out if x}


def _mark_dispatched(pkg: dict[str, Any], *, queue_id: str, ok: bool) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with DISPATCHED.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": _now(), "stem": pkg["stem"], "name": pkg["name"],
                            "kind": pkg["kind"], "queue_id": queue_id, "ok": ok}) + "\n")


def _count_today() -> int:
    rows = []
    if DISPATCHED.is_file():
        for line in DISPATCHED.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return sum(1 for r in rows if (r.get("ts") or "")[:10] == _today() and r.get("ok"))


def scan() -> dict[str, Any]:
    """List packages not yet dispatched to the swarm."""
    all_pkgs = _packages()
    done = _dispatched_ids()
    pending = [p for p in all_pkgs if p["stem"] not in done]
    return {"ok": True, "action": "scan", "schema": SCHEMA,
            "total": len(all_pkgs), "dispatched": len(done),
            "pending": len(pending), "packages": pending,
            "max_per_day": DEFAULT_MAX_PER_DAY, "used_today": _count_today()}


def dispatch(pkg: dict[str, Any], *, max_per_day: int = DEFAULT_MAX_PER_DAY) -> dict[str, Any]:
    """Dispatch ONE package to the cheap swarm. Idempotent per package stem."""
    stem = pkg.get("stem") or pkg.get("name") or ""
    if stem in _dispatched_ids():
        return {"ok": False, "action": "already_dispatched", "stem": stem}
    if _count_today() >= max_per_day:
        return {"ok": False, "action": "daily_cap", "max_per_day": max_per_day,
                "used_today": _count_today()}
    goal = pkg.get("goal") or ""

    # Avoid duplicate goal already queued/running.
    try:
        from mag.governor_autorun import queue_has_goal
        if queue_has_goal(goal):
            _mark_dispatched(pkg, queue_id="dup", ok=False)
            return {"ok": False, "action": "already_queued", "stem": stem}
    except Exception:
        pass

    try:
        from mag.orchestrator import enqueue
        q = enqueue(goal, provider=DEFAULT_PROVIDER, model=DEFAULT_MODEL,
                    tag="cheap-swarm", tier="research")
    except Exception as e:
        return {"ok": False, "action": "enqueue_error", "stem": stem, "error": str(e)[:200]}

    qid = str(q.get("queue_id") or "")
    ok = bool(q.get("ok")) and bool(qid)
    _mark_dispatched(pkg, queue_id=qid, ok=ok)
    return {"ok": ok, "action": "dispatched" if ok else "enqueue_failed",
            "stem": stem, "queue_id": qid, "goal": goal[:120], "detail": q}


def run_cadence(*, max_per_day: int = DEFAULT_MAX_PER_DAY, max_new: int = 3) -> dict[str, Any]:
    """Idempotent cadence: dispatch up to max_new pending packages to the cheap swarm.

    PEAK-PRICE GUARD (2026-08-24): DeepSeek peak (weekday BJ 09-12/14-18) is 2x off-peak.
    During peak, NEW dispatches defer to the next off-peak window (mag.offpeak) so heavy
    rounds run at half price. MAG_ALLOW_PEAK=1 (or defer_peak=False) forces on.
    """
    try:
        from mag.offpeak import defer_if_peak
        d = defer_if_peak()
        if d.get("defer"):
            return {"ok": True, "action": "deferred_peak", "schema": SCHEMA,
                    "multiplier": 2.0, "next_offpeak_utc": d.get("next_offpeak_utc"),
                    "note": "peak pricing — new dispatches deferred to off-peak (MAG_ALLOW_PEAK=1 overrides)",
                    "scan": scan()}
    except Exception:  # noqa: BLE001 — pricing guard must never break the cadence
        pass
    s = scan()
    dispatched, skipped = [], []
    for pkg in s.get("packages", [])[:max_new]:
        r = dispatch(pkg, max_per_day=max_per_day)
        (dispatched if r.get("ok") else skipped).append(
            {"stem": pkg["stem"], "action": r.get("action"), "queue_id": r.get("queue_id")})
    return {"ok": True, "action": "cadence", "schema": SCHEMA, "scan": s,
            "dispatched": dispatched, "skipped": skipped}


def status() -> dict[str, Any]:
    s = scan()
    return {"schema": SCHEMA, "ok": True, "handoff_dir": str(HANDOFF_DIR),
            "total_packages": s["total"], "dispatched": s["dispatched"],
            "pending": s["pending"], "used_today": s["used_today"],
            "max_per_day": DEFAULT_MAX_PER_DAY, "model": DEFAULT_MODEL, "ts": _now()}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    ap = argparse.ArgumentParser(prog="cheap-swarm", description="Cheap swarm: expand + execute ghost-built packages")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("scan", help="list pending ghost/build packages")
    p_d = sub.add_parser("dispatch", help="dispatch one package")
    p_d.add_argument("path")
    sub.add_parser("status", help="swarm state")
    sub.add_parser("cadence", help="idempotent: dispatch up to 3 pending")
    args = ap.parse_args(argv)
    if args.cmd == "scan":
        print(json.dumps(scan(), indent=2, default=str)[:8000])
    elif args.cmd == "dispatch":
        pkg = {"path": args.path, "name": Path(args.path).name, "stem": Path(args.path).stem,
               "kind": "build", "goal": f"Execute build package {Path(args.path).name}: expand the frozen spec and implement it."}
        print(json.dumps(dispatch(pkg), indent=2, default=str)[:8000])
    elif args.cmd == "status":
        print(json.dumps(status(), indent=2, default=str)[:6000])
    elif args.cmd == "cadence":
        print(json.dumps(run_cadence(), indent=2, default=str)[:8000])
    return 0


__all__ = ["scan", "dispatch", "run_cadence", "status"]


if __name__ == "__main__":
    raise SystemExit(main())
