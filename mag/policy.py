"""Load mag.yaml policy."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from config import CONFIGS_DIR, ROOT


def _strip_comment(val: str) -> str:
    # strip unquoted # comments
    if "#" not in val:
        return val.strip()
    in_q = False
    out = []
    for ch in val:
        if ch in "\"'":
            in_q = not in_q
        if ch == "#" and not in_q:
            break
        out.append(ch)
    return "".join(out).strip()


def load_policy() -> dict[str, Any]:
    path = CONFIGS_DIR / "mag.yaml"
    defaults: dict[str, Any] = {
        "interval_seconds": 120,
        "max_attention_per_day": 8,
        "max_assigned_per_cycle": 1,
        "use_grok_harness": True,
        "harness_yolo": False,
        "harness_max_turns": 12,
        "harness_output": "plain",
        "watch_before_cycle": True,
        "todo_path": "queue/todo.md",
        "attention_path": "memory/attention.md",
        "journal_path": "memory/mag_journal.md",
        "log_path": "logs/mag.jsonl",
        "assigned_markers": ["[mag]", "[assign]"],
        "attention": {
            "open_loops_from_working": True,
            "unread_handoff": True,
            "live_session_stale_minutes": 45,
            "always_note_if_todo_stale_hours": 24,
        },
    }
    if not path.is_file():
        return dict(defaults)

    out = dict(defaults)
    for line in path.read_text(encoding="utf-8").splitlines():
        raw = line.split("#", 1)[0].rstrip() if not line.strip().startswith("#") else ""
        if not raw.strip() or raw.strip().startswith("#"):
            # handle inline comments carefully
            if "#" in line and ":" in line.split("#")[0]:
                raw = line.split("#")[0]
            else:
                continue
        if ":" not in raw:
            continue
        # skip nested-only indent keys for attention (keep defaults)
        if raw.startswith("  ") or raw.startswith("\t"):
            continue
        key, _, val = raw.partition(":")
        key = key.strip()
        val = _strip_comment(val)
        if not val:
            continue
        if val.lower() in {"true", "false"}:
            out[key] = val.lower() == "true"
        elif val.isdigit():
            out[key] = int(val)
        elif val.startswith("[") and val.endswith("]"):
            inner = val[1:-1]
            out[key] = [x.strip().strip("\"'") for x in inner.split(",") if x.strip()]
        else:
            out[key] = val.strip("\"'")
    return out


def resolve(rel: str) -> Path:
    p = Path(rel)
    return p if p.is_absolute() else ROOT / p
