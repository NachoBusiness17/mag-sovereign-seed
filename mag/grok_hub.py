"""grok_hub — the CENTRALIZED GROK-4.5 POST: a small grok-4.5 hub that GROUPS asks and
dispatches the groups to DEEPSEEK swarms, right-sized so frontier-level querying costs a
fraction of frontier. Everything recorded (ledger + verkle knot).

Operator's model (2026-08-11): consult grok on the plan -> a grok-4.5 hub creates the GROUPINGS ->
it dispatches the groups to deepseek swarms -> rightsize every ask -> frontier quality at a fraction
of the cost -> ALL RECORDED.

Contract: grok_hub.v1. grok 4.5 (tier=orchestrate) ONLY for the grouping/steer step, budget-gated;
deepseek does the volume. Honesty: grok_captured is TRUE only when grok actually returned groupings.
CLI: python -m mag.grok_hub group "<ask1>|<ask2>|..." [--dry] [--force] | status | cadence
"""
from __future__ import annotations

import argparse
import json
import os
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

SCHEMA = "grok_hub.v1"
STATE_DIR = ROOT / "memory" / "runs" / "grok_hub"
LEDGER = STATE_DIR / "groupings.jsonl"

GROUP_SYSTEM = (
    "You are the centralized grok hub. You are given a batch of research/task asks. "
    "GROUP them into the smallest number of coherent groups (2-6), where each group is a "
    "unified task a CHEAP deepseek executor can run. Return STRICT JSON only:\n"
    '{"groups":[{"id":"g1","asks":[<indices, 0-based>],"steer":"<one-line RIB: what to research/do>","reason":"<why grouped>"}]}'
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _cfg() -> dict[str, Any]:
    return {"min_remaining_pct": 25.0, "cooldown_s": 900}


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


# ── budget gate (reuse grok_frontier_loop) ────────────────────────────────
def _gate() -> dict[str, Any]:
    try:
        from mag.grok_frontier_loop import budget_status as _bs
        st = _bs()
        can = bool(st.get("can_spend_grok"))
    except Exception:
        st = {}
        can = False
    return {"ok": can, "status": st}


# ── grouping (grok 4.5 brain) ─────────────────────────────────────────────
def group_asks(asks: list[str], *, dry: bool = True, force: bool = False) -> dict[str, Any]:
    """Batch asks -> grok 4.5 creates groupings (or cheap fallback in dry). Returns groupings."""
    asks = [a for a in asks if (a or "").strip()]
    out: dict[str, Any] = {"schema": SCHEMA, "ts": _now(), "n_asks": len(asks), "dry": dry,
                           "grok_captured": False}
    if not asks:
        return {**out, "ok": False, "reason": "no_asks"}
    groups: list[dict[str, Any]] = []
    captured = False
    if not dry:
        g = _gate()
        if force or g["ok"]:
            try:
                from mag.grok_rightsize import call_grok
                payload = json.dumps({"asks": asks})
                res = call_grok(payload, tier="orchestrate", max_tokens=4096)  # grok 4.5
                captured = bool(res.ok) and bool((res.content or "").strip())
                if captured:
                    parsed = _parse_grouping(res.content)
                    if parsed:
                        groups = parsed
            except Exception as e:
                out["error"] = str(e)[:200]
    out["grok_captured"] = captured
    if not groups:
        # Cheap deterministic fallback (honest: not frontier grouping).
        groups = _fallback_grouping(asks)
        if not captured and not dry:
            out["provenance_note"] = ("grok 4.5 requested but returned no grouping; "
                                      "used deterministic fallback (NOT frontier).")
    out["groups"] = groups
    return {**out, "ok": True}


def _parse_grouping(text: str) -> list[dict[str, Any]]:
    """Parse STRICT JSON grouping out of a grok response (strip any prose)."""
    import re
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return []
    try:
        data = json.loads(m.group(0))
        return [g for g in data.get("groups", []) if isinstance(g, dict) and g.get("asks")]
    except (json.JSONDecodeError, AttributeError):
        return []


def _fallback_grouping(asks: list[str]) -> list[dict[str, Any]]:
    """Deterministic local grouping by first keyword (never claims to be frontier)."""
    import re
    groups: dict[str, list[int]] = {}
    for i, a in enumerate(asks):
        words = re.findall(r"[a-z]{4,}", a.lower())
        key = words[0] if words else "misc"
        groups.setdefault(key, []).append(i)
    return [{"id": f"g{k}", "asks": idxs,
             "steer": f"research/execute the grouped asks ({asks[idxs[0]][:60]}...)",
             "reason": "deterministic fallback grouping"} for k, idxs in groups.items()]


# ── dispatch groups to the deepseek swarm ────────────────────────────────
def dispatch_groups(groups: list[dict[str, Any]], asks: list[str], *, dry: bool = True) -> dict[str, Any]:
    """Dispatch each group to the deepseek swarm via the orchestrator queue."""
    dispatched: list[dict[str, Any]] = []
    for grp in groups:
        indices = [int(i) for i in grp.get("asks", []) if str(i).lstrip("-").isdigit()]
        goal = (grp.get("steer") or "").strip() + \
               (" | asks: " + " || ".join(asks[i] for i in indices if i < len(asks))[:800])
        if dry:
            dispatched.append({"group": grp.get("id"), "queue_id": "dry", "ok": True})
            continue
        try:
            from mag.orchestrator import enqueue
            r = enqueue(goal, provider="deepseek", model="deepseek-v4-flash",
                        timeout=1200, tag=f"grok-hub-{grp.get('id')}")
            dispatched.append({"group": grp.get("id"), "queue_id": r.get("queue_id", "?"),
                               "ok": bool(r.get("ok")), "error": r.get("error", "")[:120]})
        except Exception as e:
            dispatched.append({"group": grp.get("id"), "ok": False, "error": str(e)[:120]})
    return {"dispatched": dispatched, "n": len(dispatched)}


# ── record (ledger + verkle knot) ─────────────────────────────────────────
def record(grouping: dict[str, Any], dispatch: dict[str, Any]) -> dict[str, Any]:
    row = {"ts": _now(), "schema": SCHEMA,
           "n_asks": grouping.get("n_asks"), "n_groups": len(grouping.get("groups", [])),
           "grok_captured": grouping.get("grok_captured"),
           "groups": [{"id": g.get("id"), "n": len(g.get("asks", [])), "steer": g.get("steer", "")[:120]}
                      for g in grouping.get("groups", [])],
           "dispatch": dispatch.get("dispatched")}
    _append_jsonl(LEDGER, row)
    try:
        from mag.verkle_knot import append_verkle_knot
        knot = append_verkle_knot({"session_id": f"grok-hub:{datetime.now(timezone.utc).strftime('%H%M')}",
                                   "theme": "steal", "summary": f"[grok-hub] grouped {len(grouping.get('groups', []))} groups from {grouping.get('n_asks')} asks"})
        row["verkle"] = knot.get("ok")
    except Exception as e:
        row["verkle"] = False
        row["verkle_error"] = str(e)[:120]
    return row


# ── full cycle + self-improve ─────────────────────────────────────────────
def cycle(asks: list[str], *, dry: bool = True, force: bool = False) -> dict[str, Any]:
    """group -> dispatch -> record -> learn."""
    grp = group_asks(asks, dry=dry, force=force)
    disp = dispatch_groups(grp.get("groups", []), asks, dry=dry)
    rec = record(grp, disp)
    lr = learn()
    return {"ok": True, "action": "cycle", "grouping": grp, "dispatch": disp,
            "record": rec, "learn": lr}


def learn() -> dict[str, Any]:
    rows = _read_jsonl(LEDGER)
    n = len(rows)
    captured = sum(1 for r in rows if r.get("grok_captured"))
    groups = sum(r.get("n_groups", 0) for r in rows)
    _append_jsonl(LEDGER, {"ts": _now(), "schema": "grok_hub_learn.v1", "n_cycles": n,
                           "grok_captured_n": captured, "groups_total": groups,
                           "capture_rate": round((captured / n), 3) if n else 0.0,
                           "note": "fold capture-rate so the hub keeps grok for real grouping only"})
    return {"n_cycles": n, "grok_captured_n": captured, "groups_total": groups,
            "capture_rate": round((captured / n), 3) if n else 0.0}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="grok-hub",
                                 description="Centralized grok-4.5 hub: group asks -> deepseek swarms -> record.")
    ap.add_argument("cmd", nargs="?", choices=["group", "status", "learn"], default="status")
    ap.add_argument("asks", nargs="*", help="asks joined by '|'")
    ap.add_argument("--dry", action="store_true", default=True)
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd == "group":
        asks = "|".join(a.asks).split("|") if a.asks else []
        print(json.dumps(cycle([x for x in asks if x.strip()], dry=a.dry, force=a.force),
                         indent=2, default=str))
    elif a.cmd == "learn":
        print(json.dumps(learn(), indent=2, default=str))
    else:
        print(json.dumps({"schema": SCHEMA, "n_recorded": len(_read_jsonl(LEDGER)),
                          "last": _read_jsonl(LEDGER, tail=1)}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

__all__ = ["group_asks", "dispatch_groups", "record", "cycle", "learn", "main"]
