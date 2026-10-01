"""Create a file-backed, history-aware Vast blade launch plan.

This module plans only.  It never talks to Vast, starts a process, or enables
the buyer.  Boot expectations are derived exclusively from boot_watch.log.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[1]
VAST = ROOT / "state" / "vast"
TEMPLATES = VAST / "blade_templates.json"
COVENANT = VAST / "covenant.json"
BOOT_LOG = VAST / "boot_watch.log"
PLANS = VAST / "launch_plans"

_STAMP = re.compile(r"\[(?:boot[^]]*?)?(\d{2}:\d{2}:\d{2})\]")
_PHASE = re.compile(r"phase:\s*[^-]+->\s*(\w+)", re.I)
_TEMPLATE = re.compile(r"(?:template(?:_name)?\s*[:=]\s*[\"']?)([A-Za-z0-9_.-]+)", re.I)


def _clock(line: str) -> float | None:
    match = _STAMP.search(line)
    if not match:
        return None
    h, m, s = (int(x) for x in match.group(1).split(":"))
    return h * 3600 + m * 60 + s


def boot_history(template: str, path: Path | None = None) -> list[float]:
    """Return completed pull-to-READY minutes for *template*.

    Unlabelled records are retained for the registry default: the existing
    watcher log predates template labels and is the default qwen3 boot trail.
    Labeled records are matched exactly.
    """
    path = path or BOOT_LOG
    if not path.exists():
        return []
    sessions: list[dict[str, object]] = []
    current: dict[str, object] | None = None
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    for line in lines:
        if "watching instance" in line.lower():
            current = {"template": None, "pull": None, "ready": None}
            tm = _TEMPLATE.search(line)
            if tm:
                current["template"] = tm.group(1)
            sessions.append(current)
        if current is None:
            continue
        tm = _TEMPLATE.search(line)
        if tm:
            current["template"] = tm.group(1)
        stamp = _clock(line)
        phase = _PHASE.search(line)
        if stamp is not None and phase:
            value = phase.group(1).lower()
            if value == "pull":
                current["pull"] = stamp
            elif value == "ready":
                current["ready"] = stamp
    default_name = _default_template()
    minutes: list[float] = []
    for row in sessions:
        label = row["template"]
        if label and label != template:
            continue
        if not label and template != default_name:
            continue
        pull, ready = row["pull"], row["ready"]
        if isinstance(pull, (int, float)) and isinstance(ready, (int, float)):
            elapsed = float(ready) - float(pull)
            if elapsed < 0:
                elapsed += 24 * 3600
            minutes.append(elapsed / 60.0)
    return minutes


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _default_template() -> str:
    try:
        return str(_load(TEMPLATES).get("default") or "")
    except (OSError, json.JSONDecodeError):
        return "qwen3-8b-ollama"


def make_plan(template_name: str, work_description: str) -> dict:
    registry = _load(TEMPLATES)
    template = next((x for x in registry.get("templates", [])
                     if x.get("name") == template_name), None)
    if not template:
        raise ValueError(f"unknown template: {template_name}")
    if not isinstance(template.get("dph"), (int, float)):
        raise ValueError(f"template has no numeric dph: {template_name}")
    covenant = _load(COVENANT)
    ttl_h = float(covenant["blade_lifetime_h"])
    history = boot_history(template_name)
    expected = float(median(history)) if len(history) >= 3 else None
    note = f"median of {len(history)} boot histories" if expected is not None else "no history yet"
    dph = float(template["dph"])
    return {
        "schema": "launch_plan.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "template": template_name,
        "work_description": work_description,
        "dph": dph,
        "expected_boot_min": expected,
        "expected_boot_note": note,
        "ttl_h": ttl_h,
        "est_cost": dph * ttl_h,
    }


def write_plan(template_name: str, work_description: str) -> Path:
    plan = make_plan(template_name, work_description)
    PLANS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = PLANS / f"{stamp}_{template_name}.json"
    path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 2 or not args[1].strip():
        print("usage: python -m mag.blade_plan <template-name> <work-description>", file=sys.stderr)
        return 2
    try:
        path = write_plan(args[0], args[1])
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"launch plan refused: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"plan": str(path.relative_to(ROOT)), "template": args[0]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
