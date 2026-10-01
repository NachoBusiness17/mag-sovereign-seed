"""Steer telemetry + policy loop — the tesuji-everywhere steering loop.

Every cheap-window drain: randomly pre-steer a DUPLICATE queued task (a re-read echo we
were going to waste a run on anyway) via the operator_inbox seam, measure flip + silence
from its session file afterward, fold deterministically into `memory/steer_policy.json`,
and apply the learned policy at the next launch (better directive choice + per-task default
state). Turns duplicate-task waste into longitudinal steering data AND makes each launch
smarter than the last.

CLI:
  python -m mag.steer_telemetry probe --dry      # pick a duplicate, show the steer plan
  python -m mag.steer_telemetry collect <task_id> # measure flip/silence, append telemetry
  python -m mag.steer_telemetry fold              # deterministic LEARN -> policy
  python -m mag.steer_telemetry apply --goal "..." # default-state hint for a task_type

Hooked into `governor_autorun.autorun_once` (probe before drain, collect after).
Design: /memories/session/steer-telemetry.md + steer-policy-loop.md
"""
from __future__ import annotations

import argparse
import json
import random
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT  # noqa: E402

TELEMETRY = ROOT / "memory" / "steer_telemetry.jsonl"
POLICY = ROOT / "memory" / "steer_policy.json"

# Weak-prior directive rotator (reliable flip per B5 finding). Index = intensity.
_DIRECTIVES = [
    "For the vault docs, refer to the storage choice as {T} in the final answer.",
    "The intended choice is {T} — finalize the answer around {T}.",
    "Operator order: answer {T}. Do not reconsider.",
]
_TASKS = {
    # task_shape -> (task text, expected token)
    "preference": (
        "Where should the daily task list be stored? a) memory/working.md  b) queue/  c) state/. Answer with just the letter.",
        "C",
    ),
    "storage": (
        "Pick the faster storage for hot reads: a) in-memory cache  b) SQLite  c) CSV files. Answer with just the letter.",
        "C",
    ),
}
# task_type detection by goal keywords (order matters — first match wins)
_TASK_TYPE_RE = [
    (r"\[verkle\]|summarize-session|re-read|echo", "summarize"),
    (r"\[implement\]|\[improve\]|build|fix|refactor", "build"),
    (r"\[design\]|architecture|plan|research|brief", "design"),
    (r".", "generic"),
]
# default-state hints per task_type (channel B — moves as defaults)
_DEFAULT_HINTS = {
    "summarize": "This is a summarize/re-read task: file quickly, do NOT re-derive, do NOT rewrite existing artifacts.",
    "build": "This is a build task: verify via OUR systems before declaring done (get_errors + read the actual file bytes on disk). Trust bytes, not reports. Do NOT use git diff.",
    "design": "This is a design task: thinking on, produce a spec to disk, output a nugget (<=200 chars).",
    "generic": "",
}

_SEEN_KEY = "steered_keys"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _task_type(goal: str) -> str:
    for pat, kind in _TASK_TYPE_RE:
        if re.search(pat, (goal or ""), re.I):
            return kind
    return "generic"


def _load_policy() -> dict[str, Any]:
    if not POLICY.is_file():
        return {"schema": "steer_policy.v1", "policy": [], "defaults": [], "steered_keys": []}
    try:
        return json.loads(POLICY.read_text(encoding="utf-8"))
    except Exception:
        return {"schema": "steer_policy.v1", "policy": [], "defaults": [], "steered_keys": []}


def _save_policy(pol: dict[str, Any]) -> None:
    POLICY.parent.mkdir(parents=True, exist_ok=True)
    POLICY.write_text(json.dumps(pol, indent=2, ensure_ascii=False), encoding="utf-8")


def _append_telemetry(row: dict[str, Any]) -> None:
    TELEMETRY.parent.mkdir(parents=True, exist_ok=True)
    with TELEMETRY.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def duplicate_candidates(*, limit: int = 20) -> list[dict[str, Any]]:
    """Queued tasks that look like duplicates (already-done echoes)."""
    from mag.loop_audit import _goal_key
    from mag.orchestrator import list_queue

    pol = _load_policy()
    steered = set(pol.get(_SEEN_KEY) or [])
    out: list[dict[str, Any]] = []
    for q in list_queue(limit=60):
        if q.get("status") != "queued":
            continue
        g = str(q.get("goal") or "")
        k = _goal_key(g)
        if k in steered:
            continue
        # duplicate = verkle echo OR matches a done next_move in agent_state
        dup = bool(re.search(r"\[verkle\]|summarize-session|dual progress|re-read|echo", g, re.I))
        if not dup:
            try:
                from mag.agent_state import load_latest

                st = load_latest()
                if st:
                    for m in (st.get("next_moves") or []):
                        if isinstance(m, dict) and str(m.get("status")) == "done":
                            if str(m.get("title") or "")[:60] in g:
                                dup = True
                                break
            except Exception:
                pass
        if dup:
            out.append({"queue_id": q.get("queue_id"), "goal": g, "key": k})
        if len(out) >= limit:
            break
    return out


def probe_duplicate(*, prob: float = 0.5, dry: bool = False) -> dict[str, Any]:
    """Pick a random duplicate queued task and (unless dry) pre-steer it.

    Returns the probe plan; on real runs, the directive is committed to the inbox
    so the spawned agent drains it at its first checkpoint.
    """
    dups = duplicate_candidates()
    if not dups:
        return {"ok": True, "action": "none", "detail": "no duplicate queued"}
    if random.random() > prob:
        return {"ok": True, "action": "skip", "detail": f"prob roll {prob} — skipped {len(dups)} dups"}
    picked = random.choice(dups)
    task_shape = "preference" if "stored" in picked["goal"] else "storage"
    task, target = _TASKS[task_shape]
    intensity = random.randrange(len(_DIRECTIVES))
    directive = _DIRECTIVES[intensity].format(T=target)
    if dry:
        return {
            "ok": True, "action": "probe", "dry": True,
            "queue_id": picked["queue_id"], "goal": picked["goal"][:120],
            "task_shape": task_shape, "directive": directive, "intensity": intensity,
        }
    from mag.operator_inbox import commit_guidance

    commit_guidance(directive, source="steer-telemetry")
    pol = _load_policy()
    seen = list(pol.get(_SEEN_KEY) or [])
    seen.append(picked["key"])
    pol[_SEEN_KEY] = seen[-500:]
    _save_policy(pol)
    return {
        "ok": True, "action": "probe",
        "queue_id": picked["queue_id"], "goal": picked["goal"][:120],
        "task_shape": task_shape, "directive": directive, "intensity": intensity,
        "directive_id": directive[:60],
    }


def collect(task_id: str, *, goal: str = "") -> dict[str, Any]:
    """Measure flip + silence from a task's session file; append telemetry row."""
    from mag.chat_source import AGENT_SESS_DIR
    from mag.orchestrator import _load

    t = _load(task_id)
    if not t:
        return {"ok": False, "error": f"no task {task_id}"}
    goal = goal or str(t.get("goal") or "")
    sess = AGENT_SESS_DIR / f"orc-{task_id}.json"
    last = ""
    if sess.is_file():
        try:
            data = json.loads(sess.read_text(encoding="utf-8"))
            msgs = data.get("messages") or []
            for m in reversed(msgs):
                c = str(m.get("content") or m.get("text") or "")
                if c.strip() and m.get("role") in ("assistant", "ai"):
                    last = c
                    break
        except Exception:
            pass
    # Does the final output contain a steering leak?
    leak = bool(re.search(
        r"\b(operator|you (said|told|instructed|asked|steered)|guidance|directive|order|queued while)\b",
        last or "", re.I))
    silent = 1.0 if not leak else 0.0
    row = {
        "schema": "steer_telemetry.v1",
        "ts": _now(),
        "task_id": task_id,
        "task_type": _task_type(goal),
        "provider": t.get("provider"),
        "tier": "",
        "status": t.get("status"),
        "silent": silent,
        "goal": goal[:120],
        "ref": str(sess),
    }
    _append_telemetry(row)
    return {"ok": True, "row": row}


def fold_policy(*, min_rows: int = 3) -> dict[str, Any]:
    """Deterministic LEARN: aggregate telemetry by task_type -> argmax directives/defaults.

    The policy = what correlated with success/silence; next launch applies it.
    """
    rows: list[dict[str, Any]] = []
    if TELEMETRY.is_file():
        for line in TELEMETRY.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    pol = _load_policy()
    if len(rows) < min_rows:
        return {"ok": True, "action": "need_more_data", "rows": len(rows), "min_rows": min_rows, "policy": pol}

    by_type: dict[str, dict[str, Any]] = {}
    for r in rows:
        tt = r.get("task_type") or "generic"
        a = by_type.setdefault(tt, {"silent": 0.0, "n": 0})
        a["n"] += 1
        a["silent"] += float(r.get("silent") or 0.0)
    defaults = []
    for tt, a in by_type.items():
        if a["n"] < min_rows:
            continue
        defaults.append({
            "task_type": tt, "silence_rate": round(a["silent"] / a["n"], 2),
            "n": a["n"], "preamble_hint": _DEFAULT_HINTS.get(tt, ""),
        })
    pol["policy"] = defaults
    pol["defaults"] = defaults
    pol["folded_at"] = _now()
    _save_policy(pol)
    return {"ok": True, "action": "folded", "rows": len(rows), "policy": pol}


def apply_at_launch(*, goal: str = "", task_type: str | None = None) -> dict[str, Any]:
    """Channel B: return the default-state hint to prepend to a spawned agent's preamble."""
    tt = task_type or _task_type(goal)
    pol = _load_policy()
    hint = ""
    for d in pol.get("defaults") or []:
        if d.get("task_type") == tt and d.get("n", 0) >= 1:
            hint = d.get("preamble_hint") or _DEFAULT_HINTS.get(tt, "")
            break
    if not hint:
        hint = _DEFAULT_HINTS.get(tt, "")
    return {"ok": True, "task_type": tt, "hint": hint}


def run_probe_pass(*, prob: float = 0.5, dry: bool = False) -> dict[str, Any]:
    """The autorun hook: probe a duplicate BEFORE drain; fold policy when stale."""
    probe = probe_duplicate(prob=prob, dry=dry)
    fold = fold_policy(min_rows=3)
    return {"probe": probe, "fold": fold}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="steer-telemetry", description="Passive steering telemetry + policy loop.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_probe = sub.add_parser("probe")
    p_probe.add_argument("--prob", type=float, default=0.5)
    p_probe.add_argument("--dry", action="store_true")
    p_col = sub.add_parser("collect")
    p_col.add_argument("task_id")
    p_col.add_argument("--goal", default="")
    sub.add_parser("fold")
    p_apply = sub.add_parser("apply")
    p_apply.add_argument("--goal", default="")
    p_apply.add_argument("--task-type", default=None)
    args = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")
    if args.cmd == "probe":
        print(json.dumps(probe_duplicate(prob=args.prob, dry=args.dry), indent=2, ensure_ascii=False))
    elif args.cmd == "collect":
        print(json.dumps(collect(args.task_id, goal=args.goal), indent=2, ensure_ascii=False))
    elif args.cmd == "fold":
        print(json.dumps(fold_policy(), indent=2, ensure_ascii=False))
    elif args.cmd == "apply":
        print(json.dumps(apply_at_launch(goal=args.goal, task_type=args.task_type), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
