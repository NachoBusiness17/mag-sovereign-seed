"""Governance payload — steering, behavioral loop, autonomy prefs for the Body tab.

Teaches tools via remedy cards + behavioral themes (injected into context-pack).
Steering via !steer/!continue/!pause/!escape — dashboard + pigeonhole, not re-approval.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT

DAILY = ROOT / "memory" / "improve" / "daily"
DECISIONS = ROOT / "memory" / "decisions_log.jsonl"
REMEDY_DIR = ROOT / "memory" / "remedies"


def _latest_behavioral_leaf() -> dict[str, Any]:
    if not DAILY.is_dir():
        return {}
    leaves = sorted(DAILY.glob("*-behavioral.md"), reverse=True)
    if not leaves:
        return {}
    path = leaves[0]
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    themes: list[dict[str, str]] = []
    for m in re.finditer(r"^#{2,3}\s+(T\d+)\s*[—\-–]\s*(.+)$", text, re.M):
        tid, title = m.group(1), m.group(2).strip()
        # grab first "Avoid:" or "Pattern to avoid:" line under theme
        avoid = ""
        block_m = re.search(
            rf"^#{2,3}\s+{re.escape(tid)}\s*[—\-–].*?(?=^#{2,3}\s+|\Z)",
            text,
            re.M | re.S,
        )
        if block_m:
            av = re.search(r"(?:Avoid|Pattern to avoid):\s*(.+)", block_m.group(0), re.M)
            if av:
                avoid = av.group(1).strip()[:200]
        themes.append({
            "id": tid,
            "title": title,
            "avoid": avoid,
            "layman": f"When {title.lower()}, {avoid[:120]}" if avoid else title,
        })
    return {
        "path": str(path.relative_to(ROOT)).replace("\\", "/"),
        "themes": themes[:8],
        "n_themes": len(themes),
    }


def _steer_case_law(n: int = 3) -> list[dict[str, str]]:
    if not DECISIONS.is_file():
        return []
    rows: list[dict[str, str]] = []
    try:
        lines = [l for l in DECISIONS.read_text(encoding="utf-8").splitlines() if l.strip()]
    except OSError:
        return []
    for line in reversed(lines[-40:]):
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        outcome = str(d.get("outcome") or d.get("decision") or "")[:160]
        ctx = str(d.get("context") or d.get("steer_input") or "")[:120]
        if outcome or ctx:
            rows.append({"context": ctx, "outcome": outcome, "ts": str(d.get("timestamp") or d.get("ts") or "")[:19]})
        if len(rows) >= n:
            break
    return rows


def broadcast_steer(cmd: str) -> dict[str, Any]:
    """Push steer to chat agent turn + all running orchestrator workers."""
    cmd = (cmd or "").strip()
    if not cmd.startswith("!"):
        cmd = "!" + cmd
    out: dict[str, Any] = {"cmd": cmd, "chat_queued": False, "workers": [], "desk_queued": False}
    try:
        from mag.agent_cli import push_steer

        out["chat_queued"] = bool(push_steer(cmd))
    except Exception as e:
        out["chat_error"] = str(e)[:200]
    if cmd.startswith("!steer "):
        try:
            from mag.desk_dialogue import desk_steering_enabled, post_desk_steer

            if desk_steering_enabled():
                desk = post_desk_steer(cmd[7:].strip())
                out["desk_queued"] = bool(desk.get("ok"))
            else:
                out["desk_queued"] = False
                out["desk_skipped"] = "desk steering disabled"
        except Exception as e:
            out["desk_error"] = str(e)[:200]
    try:
        from mag import pigeonhole as ph
        from mag.orchestrator import TASK_DIR, TERMINAL

        if TASK_DIR.is_dir():
            for p in TASK_DIR.glob("*.json"):
                try:
                    t = json.loads(p.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    continue
                if t.get("status") in TERMINAL:
                    continue
                tid = t.get("task_id")
                if not tid:
                    continue
                try:
                    if cmd.startswith("!steer "):
                        ph.post_steer(tid, cmd[7:].strip())
                        out["workers"].append({"task_id": tid, "sent": "steer"})
                    elif cmd in ("!pause", "!continue", "!escape"):
                        ph.post_cmd(tid, cmd.lstrip("!"))
                        out["workers"].append({"task_id": tid, "sent": cmd.lstrip("!")})
                except Exception as we:
                    out["workers"].append({"task_id": tid, "error": str(we)[:80]})
    except Exception as e:
        out["workers_error"] = str(e)[:200]
    out["ok"] = out["chat_queued"] or bool(out["workers"]) or out.get("desk_queued")
    return out


def build_governance() -> dict[str, Any]:
    from mag.preferences import autonomy_status, drainer_status, operator_status
    from mag.remedy import cards as remedy_cards
    from mag.operator_inbox import status as inbox_status

    behavioral = _latest_behavioral_leaf()
    tesuji_shell = {}
    try:
        from mag.tesuji_shell import latest_leaf_excerpt, status as shell_status

        tesuji_shell = {**latest_leaf_excerpt(max_wins=5), **shell_status()}
    except Exception:
        pass
    remedies = remedy_cards()
    case_law = _steer_case_law(3)
    inbox = inbox_status()

    return {
        "ok": True,
        "schema": "mag_governance.v1",
        "ts": datetime.now(timezone.utc).isoformat(),
        "layman": (
            "Steering lets you redirect a running agent without restarting. "
            "Queue guidance in Chat while the agent runs — it is read at the next checkpoint. "
            "Behavioral themes teach the model what failed before. "
            "Drainer auto-runs the worker queue so you are not the bottleneck."
        ),
        "operator_inbox": {
            **inbox,
            "api": "GET/POST /api/v1/operator-inbox",
            "checkpoint": "agent_cli._absorb_steer → drain_pending_at_checkpoint",
            "decision_matrix": "governor scores queue tasks higher when words match queued guidance",
            "behavioral_events": "logs/behavioral_events.jsonl (tool_fail, collapse, seat_crash)",
        },
        "steering": {
            "commands": [
                {"cmd": "!continue", "layman": "Resume — agent picks next blueprint step (compass decides if you typed 'continue')"},
                {"cmd": "!steer <text>", "layman": "Override direction mid-turn without killing the job"},
                {"cmd": "!pause", "layman": "Hold between tool rounds"},
                {"cmd": "!escape", "layman": "Abort the current round cleanly"},
            ],
            "chat_api": "POST /api/v1/agent/steer {cmd}",
            "worker_api": "POST /api/v1/agents/{id}/cmd {cmd: steer|pause|continue|escape}",
            "case_law": case_law,
        },
        "behavioral_loop": {
            "pipeline": "scout → eval → promote (memory/improve/)",
            "leaf": behavioral,
            "tesuji_shell": {
                "wins": tesuji_shell.get("wins") or [],
                "shells_n": tesuji_shell.get("shells_n", 0),
                "log_path": tesuji_shell.get("log_path", "logs/tesuji_shells.jsonl"),
                "latest_leaf": tesuji_shell.get("latest_leaf") or tesuji_shell.get("path"),
                "cli": "python main.py tesuji-shell log \"…\" --surprise \"…\"",
            },
            "remedy_cards": len(remedies),
            "remedy_sample": [c.get("id") or c.get("title") for c in remedies[:5] if c.get("id") or c.get("title")],
            "injected_into_pack": autonomy_status().get("inject_behavioral_pack", True),
            "mag_teaches_tools": "L1 preflight + L3 collapse append remedy cards; compass wraps ambiguous input",
        },
        "autonomy": autonomy_status(),
        "drainer": drainer_status(),
        "operator": operator_status(),
        "cursor_note": (
            "Cursor IDE shell/tool approvals are separate from Mag. "
            "Use watch/cursor_bridge.py (REST) or Agent mode in Chat to avoid per-command clicks. "
            "Enable Cursor auto-run in IDE settings for trusted workflows."
        ),
        "sources": [
            "memory/improve/daily/*-behavioral.md",
            "memory/improve/daily/*-tesuji-shells.md",
            "logs/tesuji_shells.jsonl",
            "memory/decisions_log.jsonl",
            "memory/remedies/*.md",
            "mag/agent_cli.py (steer queue + inbox drain)",
            "mag/operator_inbox.py (deferred guidance)",
            "logs/behavioral_events.jsonl",
            "mag/compass.py (autonomous continue)",
        ],
    }
