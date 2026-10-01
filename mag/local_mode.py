"""Runtime toggle for local-only provider mode.

This file provides a small file-backed runtime toggle so the dashboard can
enable/disable local-only mode without requiring process-level env changes.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from config import STATE_DIR

FLAG_PATH = STATE_DIR / "local_only.json"


def is_local_only() -> bool:
    import os

    env = str(os.environ.get("MAG_LOCAL_ONLY", "")).strip().lower()
    if env in ("1", "true", "yes"):
        return True
    # file-backed preference wins if present
    if not FLAG_PATH.is_file():
        return False
    try:
        data = json.loads(FLAG_PATH.read_text(encoding="utf-8"))
        return bool(data.get("local_only"))
    except Exception:
        return False


def set_local_only(value: bool) -> None:
    FLAG_PATH.parent.mkdir(parents=True, exist_ok=True)
    FLAG_PATH.write_text(json.dumps({"local_only": bool(value)}), encoding="utf-8")


def clear_local_only() -> None:
    try:
        if FLAG_PATH.is_file():
            FLAG_PATH.unlink()
    except Exception:
        pass
