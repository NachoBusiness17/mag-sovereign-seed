"""Queue ops — structured logger + error handler + auto-digest for the queue/drainer.

Complements the tier-based separate queues (orchestrator). Gives the ghost/drainer:
  1. LOGGER:  structured JSONL of queue lifecycle events (logs/queue_events.jsonl).
  2. ERROR HANDLER: catches drain/spawn errors, logs them, and feeds failure_kb so they
     become case law / recurring patterns (not just a raw line).
  3. AUTO-DIGEST: periodic summary of per-tier queue state + errors + failure patterns,
     written as a maintenance leaf the ghost/dashboard can read.

Deterministic ($0, no LLM). Schema: queue_ops.v1

CLI:  python -m mag.queue_ops digest [--hours N]
      python -m mag.queue_ops --cadence    (idempotent digest)
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from config import ROOT

EVENTS = ROOT / "logs" / "queue_events.jsonl"
DIGEST_DIR = ROOT / "memory" / "runs" / "queue_digest"
STATE = ROOT / "memory" / "runs" / "queue_ops" / "state.json"
SCHEMA = "queue_ops.v1"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    out = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except (json.JSONDecodeError, TypeError):
            continue
    return out


# ---- 1. LOGGER -------------------------------------------------------------
def log_event(event: str, queue_id: str = "", *, task_id: str = "", **fields: Any) -> None:
    """Append a structured queue lifecycle event."""
    EVENTS.parent.mkdir(parents=True, exist_ok=True)
    row = {"schema": "queue_event.v1", "ts": _now(), "event": event,
           "queue_id": queue_id, "task_id": task_id, **fields}
    with EVENTS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


# ---- 2. ERROR HANDLER ------------------------------------------------------
def handle_error(error: str, *, queue_id: str = "", task_id: str = "",
                 phase: str = "drain", goal: str = "", provider: str = "",
                 model: str = "") -> None:
    """Log a queue/drain error and feed it to failure_kb (becomes case law)."""
    err = (error or "unknown error")[:300]
    log_event("error", queue_id, task_id=task_id, phase=phase, error=err,
              goal=goal[:120], provider=provider, model=model)
    try:
        from mag.failure_kb import log_failure
        log_failure(
            kind="queue_error",
            detail=f"{phase}: {err}",
            error=err,
            phase=phase,
            provider=provider or None,
            model=model or None,
        )
    except Exception:
        pass


# ---- 3. AUTO-DIGEST --------------------------------------------------------
def _tier_counts() -> dict[str, int]:
    try:
        from mag.orchestrator import list_queue
        q = list_queue(limit=100)
        c = Counter()
        for x in q:
            if x.get("status") in ("queued", "running"):
                c[x.get("tier") or "mission"] += 1
        return dict(c)
    except Exception:
        return {}


def digest(*, hours: int = 24, events: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Summarize queue health over a window: per-tier state, errors, failure patterns."""
    evs = events if events is not None else _read_jsonl(EVENTS)
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    win = [e for e in evs if str(e.get("ts") or "") >= cutoff]

    by_event: Counter = Counter(e.get("event") for e in win)
    errors = [e for e in win if e.get("event") == "error"]
    err_sigs: Counter = Counter((e.get("phase") or "?") + ":" + (e.get("error") or "")[:60] for e in errors)

    # failure patterns from failure_kb
    fkb_patterns = []
    try:
        from mag.failure_kb import query as fkb_query
        r = fkb_query(kind="queue_error", limit=5) if callable(fkb_query) else {}
        fkb_patterns = (r or {}).get("recurring") or []
    except Exception:
        pass

    tiers = _tier_counts()
    return {
        "schema": SCHEMA,
        "ts": _now(),
        "window_hours": hours,
        "events_in_window": len(win),
        "by_event": dict(by_event),
        "error_count": len(errors),
        "error_sigs": [{"sig": k, "n": v} for k, v in err_sigs.most_common(6)],
        "queue_by_tier": tiers,
        "failure_kb_patterns": fkb_patterns[:5],
        "drainer": "ghost-operated single drainer, tier-priority order",
    }


def render_md(d: dict[str, Any]) -> str:
    lines = [
        f"# Queue Digest ({d['ts'][:10]})",
        "",
        f"- Window: last {d['window_hours']}h · events: {d['events_in_window']} · errors: {d['error_count']}",
        f"- Drainer: {d['drainer']}",
        "",
        "## Events", "",
    ]
    for k, v in d["by_event"].items():
        lines.append(f"- {k}: {v}")
    lines += ["", "## Queue by tier", ""]
    for tier, n in sorted(d["queue_by_tier"].items()):
        lines.append(f"- {tier}: {n}")
    lines += ["", "## Top error signatures", ""]
    for s in d["error_sigs"]:
        lines.append(f"- [{s['n']}x] {s['sig']}")
    if not d["error_sigs"]:
        lines.append("- none in window")
    return "\n".join(lines)


def run_cadence(*, hours: int = 24) -> dict[str, Any]:
    """Idempotent digest: write a leaf; skip if no new events since last digest."""
    events = _read_jsonl(EVENTS)
    last = ""
    if STATE.is_file():
        try:
            last = (json.loads(STATE.read_text(encoding="utf-8")) or {}).get("last_ts") or ""
        except Exception:
            last = ""
    if events and str(events[-1].get("ts") or "") <= last:
        return {"ok": True, "action": "skip", "reason": "no_new_events"}
    d = digest(hours=hours, events=events)
    DIGEST_DIR.mkdir(parents=True, exist_ok=True)
    leaf = DIGEST_DIR / f"queue_digest_{d['ts'][:10]}.md"
    leaf.write_text(render_md(d), encoding="utf-8")
    if events:
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps({"last_ts": events[-1].get("ts"), "digested_at": _now()}, indent=2),
                         encoding="utf-8")
    return {"ok": True, "action": "wrote", "leaf": str(leaf), "digest": d}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    ap = argparse.ArgumentParser(prog="queue-ops", description="Queue logger + error handler + auto-digest")
    ap.add_argument("--cadence", action="store_true", help="idempotent digest")
    ap.add_argument("--hours", type=int, default=24)
    args = ap.parse_args(argv)
    res = run_cadence(hours=args.hours) if args.cadence else digest(hours=args.hours)
    print(json.dumps(res, indent=2, default=str)[:6000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
