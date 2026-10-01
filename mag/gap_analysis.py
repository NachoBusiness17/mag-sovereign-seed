"""Gap analysis — where we're NOT using our systems, or just pretending to.

The operator's ask: "we still need some sort of gap analysis to see where we're not using
our systems or we're just pretending." This is the 'code is law / amend the code or admit
the gap' doctrine made mechanical. A system that is DEFINED but not USED, or USED but not
ENFORCED, is decorative — an engraving that isn't a rule.

Three kinds of gap (deterministic, cheap, no LLM):
  1. CADENCE GAPS — a passive cadence job is DEFINED (MAG_*_EVERY) but its trail is STALE
     (the loop isn't actually running it) -> we're pretending the passive system runs.
  2. MODULE GAPS — a mag/*.py module is DEFINED but never imported/called anywhere -> a
     dead module (built but not wired).
  3. PRETENDING = DEFINED + NOT-ENFORCED — machinery that exists but nothing enforces it
     (e.g. a spec_gate that's never gate()-called, a research_fold never run).

CLI:  python -m mag.gap_analysis
Wired into: mag.governor_autorun cadence (MAG_GAP_EVERY) so it runs passively.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except ImportError:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "gap_analysis.v1"

# The passive cadence jobs and the trail file each is expected to keep fresh.
CADENCE_TRAILS: dict[str, str] = {
    "warn":      "memory/runs/warning_monitor_trail.jsonl",
    "orphan":    "memory/runs/orphan_trail.jsonl",
    "fold":      "memory/runs/research_fold/folded.jsonl",
    "map":       "memory/graph/framework_map.json",
    "autorun":   "memory/runs/governor_autorun_trail.jsonl",
}


def _now() -> float:
    return datetime.now(timezone.utc).timestamp()


def _stale(rel: str, max_age_s: int) -> tuple[bool, int]:
    p = ROOT / rel
    if not p.is_file():
        return True, -1
    try:
        age = int(_now() - p.stat().st_mtime)
        return age > max_age_s, age
    except OSError:
        return True, -1


def _cadence_gaps() -> list[dict[str, Any]]:
    out = []
    for job, trail in CADENCE_TRAILS.items():
        stale, age = _stale(trail, max_age_s=3600)  # >1h old = not running
        if stale:
            out.append({"job": job, "trail": trail, "stale": True, "age_s": age,
                        "gap": "cadence job defined but not running (trail stale)"})
    return out


def _module_gaps() -> list[dict[str, Any]]:
    """mag/*.py modules that are never imported/called anywhere (dead modules)."""
    mag_dir = ROOT / "mag"
    if not mag_dir.is_dir():
        return []
    defined = {p.stem for p in mag_dir.glob("*.py") if p.stem != "__init__"}
    # search usage across the repo (main.py, tools/, watch/, dashboard/, tests/)
    used: set[str] = set()
    for base in ("main.py", "dashboard", "tools", "watch", "tests", "mag"):
        base_path = ROOT / base if base != "main.py" else ROOT / "main.py"
        if not base_path.exists():
            continue
        files = [base_path] if base_path.is_file() else list(base_path.rglob("*.py"))
        for f in files:
            try:
                txt = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for m in re.findall(r"\bmag\.(\w+)", txt):
                used.add(m)
            for m in re.findall(r"from mag import\s+([\w,\s]+)", txt):
                used.update(x.strip() for x in m.split(","))
    dead = sorted(defined - used)
    return [{"module": m, "gap": "defined but never imported/called (dead module)"} for m in dead]


def _enforcement_gaps() -> list[dict[str, Any]]:
    """Machinery that exists but nothing enforces it — the 'pretending' list."""
    gaps: list[dict[str, Any]] = []
    # research_fold: has it ever run? (folded registry exists?)
    if not (ROOT / "memory" / "runs" / "research_fold" / "folded.jsonl").is_file():
        gaps.append({"mechanism": "research_fold", "gap": "built but fold registry never written (never ran)"})
    # socratic_tree / self_drive / model_pick: are they referenced anywhere yet (wired)?
    for mod in ("socratic_tree", "self_drive", "model_pick", "work_tiers"):
        if not (ROOT / "mag" / f"{mod}.py").is_file():
            continue
        referenced = False
        for base in ("main.py", "dashboard", "tools", "watch", "mag"):
            base_path = ROOT / base if base != "main.py" else ROOT / "main.py"
            if not base_path.exists():
                continue
            files = [base_path] if base_path.is_file() else list(base_path.rglob("*.py"))
            for f in files:
                try:
                    if mod in f.read_text(encoding="utf-8", errors="replace"):
                        referenced = True
                        break
                except OSError:
                    continue
            if referenced:
                break
        if not referenced:
            gaps.append({"mechanism": mod, "gap": "built this session but NOT wired into main.py/cadence yet"})
    return gaps


def gap_analysis() -> dict[str, Any]:
    cadence = _cadence_gaps()
    modules = _module_gaps()
    enforcing = _enforcement_gaps()
    return {
        "ok": True,
        "schema": SCHEMA,
        "ts": datetime.now(timezone.utc).isoformat(),
        "cadence_gaps": cadence,
        "module_gaps": modules,
        "enforcement_gaps": enforcing,
        "n_gaps": len(cadence) + len(modules) + len(enforcing),
        "note": (
            "These are places we are 'just pretending' — defined but not running/used/enforced. "
            "Fix by wiring (cadence) or admitting the gap. Code is law."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    print(json.dumps(gap_analysis(), indent=2, default=str)[:6000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
