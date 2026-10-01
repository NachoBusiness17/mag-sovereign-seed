"""test_dummy — a deterministic placeholder MODEL for AFK pipeline testing.

Replaces the local seat (ollama as brain) with a TEST DUMMY when AFK: a cheap,
deterministic stub that exercises the pipeline end-to-end WITHOUT needing a real
model. It "thinks" by pattern — returns a stable, traceable response so we can
verify the autonomous loop runs, then let the REAL advancement happen on deepseek
free tiers.

  ask(prompt)   — deterministic reply (pattern-based, no network, no model).
  capacity()    — the dummy's simulated capability probe.
  is_dummy()    — True; lets the loop know it's testing the skeleton, not a brain.

CLI: python -m mag.test_dummy ask "<prompt>" | capacity
"""
from __future__ import annotations

import json
import re
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

SCHEMA = "test_dummy.v1"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def is_dummy() -> bool:
    return True


def ask(prompt: str) -> dict[str, Any]:
    """Deterministic dummy reply — exercises the loop, carries no real reasoning."""
    prompt = (prompt or "").strip()
    words = re.findall(r"[a-z0-9_\-]{3,}", prompt.lower())
    themes = sorted(set(words))[:6]
    return {
        "schema": SCHEMA, "ts": _now(), "ok": True,
        "dummy": True,
        "echo": prompt[:120],
        "themes": themes,
        "reply": (
            "[test-dummy] received '" + prompt[:60] + "'. "
            "Pattern themes: " + (", ".join(themes) or "none") + ". "
            "Pipeline exercised; no real model consumed."
        ),
        "note": "test dummy — replace with deepseek free tier for real autonomous advance",
    }


def capacity() -> dict[str, Any]:
    return {"schema": SCHEMA, "ok": True, "dummy": True,
            "capability": "deterministic test stub (no real model)",
            "cost": 0.0, "network": False, "model": "test-dummy"}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "capacity":
        print(json.dumps(capacity(), indent=2, ensure_ascii=False))
        return 0
    prompt = " ".join(argv) if argv else ""
    print(json.dumps(ask(prompt), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
