"""grok_gate — the grok cost-gate (Law #7): use grok ONLY when cost-effective AND frontier needed.

Rules (operator doctrine):
  * NEVER default to grok.
  * Test the process on the cheap tier (ollama / deepseek-v4-flash) FIRST.
  * Only escalate to grok when BOTH hold:
      (a) the task genuinely needs frontier results (hard reasoning / architecture / novel
          synthesis / repeated cheap failure), AND
      (b) it is cost-effective — the cheap tier was tested and failed or is insufficient.
  * Grok is the SUMMONED specialist (operating_protocol), not the default runtime.

Schema: grok_gate.v1
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCHEMA = "grok_gate.v1"

# Signals that a task genuinely needs frontier reasoning (not cheap-shaped).
FRONTIER_SIGNALS = (
    "architecture", "design protocol", "novel synthesis", "frontier", "grok",
    "synthesize", "orchestrate", "research pack", "deep research",
    "unified", "quantized", "thesis", "prove", "constitution", "protocol design",
)
# Signals that a task is cheap-shaped (exec / janitor / classify) — NEVER grok.
CHEAP_SIGNALS = (
    "janitor", "classify", "summarize", "rename", "tag", "cleanup", "prune",
    "verkle", "backfill", "steward", "maintenance", "label", "parse", "extract",
    "fkb signal", "run_pytest",
)


def _needs_frontier(goal: str) -> bool:
    g = (goal or "").lower()
    if any(s in g for s in CHEAP_SIGNALS) and not any(s in g for s in FRONTIER_SIGNALS):
        return False
    return any(s in g for s in FRONTIER_SIGNALS)


def should_use_grok(
    goal: str,
    *,
    cheap_result_ok: bool | None = None,
    frontier_required: bool | None = None,
) -> dict[str, Any]:
    """Decide whether to escalate to grok. cheap_result_ok=True => NO (cheap worked)."""
    g = (goal or "").strip()
    if cheap_result_ok is True:
        return {"ok": False, "schema": SCHEMA, "use_grok": False,
                "reason": "cheap tier already succeeded — grok not cost-effective"}
    frontier = frontier_required if frontier_required is not None else _needs_frontier(g)
    if not frontier:
        return {"ok": True, "schema": SCHEMA, "use_grok": False,
                "reason": "task is cheap-shaped — no frontier needed", "frontier": False}
    # frontier needed AND (cheap failed/untested) => cost-effective to escalate
    cheap_state = "failed/insufficient" if cheap_result_ok is False else "untested"
    return {"ok": True, "schema": SCHEMA, "use_grok": True,
            "reason": f"frontier needed ({cheap_state}) — escalate to grok",
            "frontier": True, "cheap_state": cheap_state}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    goal = " ".join(argv) if argv else ""
    print(json.dumps(should_use_grok(goal), indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
