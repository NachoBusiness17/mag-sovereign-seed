"""Self-drive cadence job — agent-state-aware ask planning, live in the autorun loop.

Runs on the governor cadence (MAG_SELF_DRIVE_EVERY). It picks the next pending intent from the
idea graph / orphan timer and replans it through self_drive (custom agent state -> model / context /
learned principles) so routing provably serves a held custom state. Spawns ONLY when a genuinely
fresh goal resolves and there is room in the queue — no spawn storm. Deterministic, fail-open.

Wired into: mag.governor_autorun autorun loop cadence.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TRAIL = ROOT / "memory" / "runs" / "self_drive_cadence.jsonl"
LAST_RUN = ROOT / "memory" / "runs" / "self_drive_cadence_last.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_last() -> dict[str, Any]:
    if not LAST_RUN.is_file():
        return {}
    try:
        return json.loads(LAST_RUN.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def _save_last(obj: dict[str, Any]) -> None:
    LAST_RUN.parent.mkdir(parents=True, exist_ok=True)
    LAST_RUN.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def _trail(entry: dict[str, Any]) -> None:
    TRAIL.parent.mkdir(parents=True, exist_ok=True)
    with TRAIL.open("a", encoding="utf-8") as f:
        f.write(json.dumps({**entry, "ts": _now()}, ensure_ascii=False, default=str) + "\n")


def _next_intent() -> str | None:
    """Deterministic pick of the next pending intent (fail-open to None)."""
    candidates: list[str] = []
    try:
        # Orphan timer intents (undone-yet-intended work) — the richest deterministic source.
        p = ROOT / "memory" / "ideas" / "orphans.jsonl"
        if p.is_file():
            for line in p.read_text(encoding="utf-8", errors="replace").splitlines()[-8:]:
                if not line.strip():
                    continue
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if r.get("status") == "open" and r.get("intent"):
                    candidates.append(str(r["intent"]))
    except Exception:
        pass
    # Fallback: idea graph open_loop leaves (already-raised, not-yet-consumed topics).
    if not candidates:
        try:
            from mag.idea_graph import list_nodes
            nodes = list_nodes(status="open") or list_nodes() or []
            for n in nodes[:6]:
                if n.get("title"):
                    candidates.append(str(n["title"]))
        except Exception:
            try:
                p = ROOT / "memory" / "idea_graph.jsonl"
                if p.is_file():
                    for line in p.read_text(encoding="utf-8", errors="replace").splitlines()[-6:]:
                        if not line.strip():
                            continue
                        try:
                            r = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if r.get("title") or r.get("content"):
                            candidates.append(str(r.get("title") or r.get("content"))[:300])
            except Exception:
                pass
    last = _load_last().get("last_intent", "")
    for c in candidates:
        if c != last:
            return c
    return candidates[-1] if candidates else None


def _queue_room(limit: int = 12) -> bool:
    try:
        from mag.orchestrator import queue_status
        st = queue_status()
        n = int(st.get("total") or 0)
        return n < limit
    except Exception:
        return False


def run(*, spawn: bool = False, agent_state: str | None = None) -> dict[str, Any]:
    """One self-drive cadence tick. Picks the next intent, replans through self_drive."""
    out: dict[str, Any] = {
        "ok": True, "planned": 0, "spawned": 0,
        "state": agent_state, "model": None, "intent": None, "error": None,
    }
    intent = _next_intent()
    if not intent:
        _trail({**out, "reason": "no_intent"})
        return out
    out["intent"] = intent[:200]
    try:
        from mag.self_drive import plan, drive

        p = plan(intent, agent_state=agent_state)
        if not p.get("ok"):
            out["error"] = p.get("error")
            _trail(out)
            return out
        out["planned"] = 1
        out["state"] = p.get("agent_state") or agent_state
        out["model"] = p.get("model")
        if spawn:
            if _queue_room():
                d = drive(intent, spawn=True, agent_state=agent_state)
                if d.get("ok") and d.get("spawn", {}).get("task_id"):
                    out["spawned"] = 1
                    out["task_id"] = d["spawn"]["task_id"]
                _save_last({"last_intent": intent, "planned_at": _now()})
            else:
                _save_last({"last_intent": intent, "planned_at": _now(), "spawn_skipped": "queue_full"})
        _trail(out)
    except Exception as e:
        out["error"] = str(e)[:200]
        _trail(out)
    return out


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(prog="self-drive-cadence")
    ap.add_argument("--spawn", action="store_true", help="spawn the re-planned task (queue room permitting)")
    ap.add_argument("--agent-state", default=None)
    args = ap.parse_args()
    print(json.dumps(run(spawn=args.spawn, agent_state=args.agent_state), indent=2, default=str))
