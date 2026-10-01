"""prefix_prover — attribute cache misses: PREFIX DRIFT vs FRONTIER NOVELTY.

The gap (2026-08-25): honest_cache_meter measures the economics (hit ratio, $)
but cannot say WHY a lane missed. The recurring ~2,304-token divergence and the
glm-4.7-flash ledger artifact (ledger said 0.3%, A/B probe proved 99.6%) were
both PREFIX DRIFT wearing novelty's clothes — and drift is a builder bug, not
frontier spend. This module closes the attribution gap by joining two existing
stores ($0, deterministic, no LLM):

  invariant.check() per agent-state    -> prefix bytes stable vs pinned sha
  logs/provider_usage.jsonl per lane   -> hit/miss split (windowed)

THE LAW: a low-ratio lane is DRIFT if any feeding state's prefix bytes changed
(or were never pinned); NOVELTY only when every feeding prefix is byte-stable.
Never pay frontier prices for a builder bug.

Reuses: invariant (pin/check), cache_map row-split convention. Writes reports to
memory/runs/prefix_prover/<ts>/ — deliberately NOT folded as knots by default
(the verkle noise compaction exists for a reason).

CLI:
  python -m mag.prefix_prover freeze          # pin every known state's prefix
  python -m mag.prefix_prover audit           # attribution table, last 24h
  python -m mag.prefix_prover audit --hours 4
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

USAGE = ROOT / "logs" / "provider_usage.jsonl"
OUT_DIR = ROOT / "memory" / "runs" / "prefix_prover"
SCHEMA = "prefix_prover.v1"

LOW_RATIO = 0.90  # below this, a lane is "missing" and needs attribution
MIN_CALLS = 10    # below this, attribution is guesswork — say so instead


def _is_test_state(name: str) -> bool:
    """Test fixtures (invariant's own tests leave 'test-state' pins behind) must
    not poison the drift signal for real lanes."""
    n = (name or "").lower()
    return n.startswith("test") or "test" in n.split("-")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso_min(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M")


def known_states() -> list[str]:
    """Pinned states + the default state — the prefixes that feed the lanes."""
    states: list[str] = []
    try:
        from mag import invariant
        pins = (invariant._load_state().get("pins") or {})
        states.extend(sorted(pins.keys()))
        default = invariant.stable_prefix.__doc__  # noqa: F841 — import check
    except Exception:
        pass
    try:
        from mag.session_route import default_agent_state
        d = str(default_agent_state() or "coding-agent")
        if d not in states:
            states.append(d)
    except Exception:
        if "coding-agent" not in states:
            states.append("coding-agent")
    return states


def cmd_freeze() -> dict[str, Any]:
    from mag import invariant

    out = []
    for st in known_states():
        if st in (invariant._load_state().get("pins") or {}):
            chk = invariant.check(st)
            out.append({"state": st, "already_pinned": True, "stable": chk.get("stable")})
            continue
        r = invariant.freeze(st, label="prefix_prover baseline")
        out.append({"state": st, "frozen": bool(r.get("ok")), "sha": str(r.get("sha") or "")[:16]})
    return {"schema": SCHEMA, "ok": True, "action": "freeze", "states": out}


def _usage_rows(hours: int) -> list[dict]:
    if not USAGE.is_file():
        return []
    cutoff = _now() - timedelta(hours=hours)
    rows = []
    for line in USAGE.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        ts = str(r.get("ts") or "").replace("Z", "+00:00")
        try:
            t = datetime.fromisoformat(ts)
        except ValueError:
            continue
        if t >= cutoff and r.get("cache_hit_tokens") is not None and r.get("cache_miss_tokens") is not None:
            rows.append(r)
    return rows


def cmd_audit(hours: int) -> dict[str, Any]:
    from mag import invariant

    states = [s for s in known_states() if not _is_test_state(s)]
    state_report = []
    any_unstable = any_unpinned = False
    for st in states:
        c = invariant.check(st)
        if not c.get("ok"):
            any_unpinned = True
            state_report.append({"state": st, "pinned": False})
            continue
        stable = bool(c.get("stable"))
        any_unstable = any_unstable or (not stable)
        state_report.append({"state": st, "pinned": True, "stable": stable})

    lanes = defaultdict(lambda: [0, 0, 0])  # hit, miss, calls
    for r in _usage_rows(hours):
        key = f"{r.get('provider')}/{r.get('model')}"
        lanes[key][0] += int(r.get("cache_hit_tokens") or 0)
        lanes[key][1] += int(r.get("cache_miss_tokens") or 0)
        lanes[key][2] += 1

    lane_report = []
    for lane, (hit, miss, calls) in sorted(lanes.items(), key=lambda kv: -kv[1][1]):
        total = hit + miss
        ratio = round(hit / total, 4) if total else None
        if ratio is None or ratio >= LOW_RATIO:
            attribution = "healthy"
        elif calls < MIN_CALLS:
            attribution = "SMALL-SAMPLE: too few split calls to attribute honestly"
        elif any_unstable:
            attribution = "DRIFT: a feeding prefix changed bytes — fix the builder, not the budget"
        elif any_unpinned:
            attribution = "UNPINNED: freeze the invariant before attributing"
        else:
            attribution = "NOVELTY: prefixes byte-stable, misses are frontier spend"
        lane_report.append({"lane": lane, "calls": calls, "hit_ratio": ratio,
                            "miss_tokens": miss, "attribution": attribution})

    out = {
        "schema": SCHEMA,
        "ts": _now().isoformat().replace("+00:00", "Z"),
        "window_hours": hours,
        "states": state_report,
        "lanes": lane_report,
        "verdict": {
            "any_unstable": any_unstable,
            "any_unpinned": any_unpinned,
            "missing_lanes": sum(1 for l in lane_report if l["attribution"] not in ("healthy",)),
        },
    }
    d = OUT_DIR / _now().strftime("%Y%m%dT%H%M%SZ")
    d.mkdir(parents=True, exist_ok=True)
    (d / "audit.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    out["report"] = str(d / "audit.json")
    return out


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    ap = argparse.ArgumentParser(prog="prefix-prover", description="Attribute cache misses: drift vs novelty")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("freeze", help="pin every known state's prefix")
    p = sub.add_parser("audit", help="attribution over the usage window")
    p.add_argument("--hours", type=int, default=24)
    args = ap.parse_args(argv)
    out = cmd_freeze() if args.cmd == "freeze" else cmd_audit(args.hours)
    print(json.dumps(out, indent=2, ensure_ascii=False)[:5000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
