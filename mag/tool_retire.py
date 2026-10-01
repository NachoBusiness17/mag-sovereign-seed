"""Tool Retire — delete old tools after use, and LEARN from each retirement.

The operator's rule: "delete old tools after we use them, and make that a learning
loop." When a tool (module / script / .cmd launcher / scratch) has served its
purpose and is now superseded, we RETIRE it — move it to trash (reversible) and
FOLD the retirement into the learning system so ghost knows what replaced what.

This is different from mag.cleanup (which sweeps transient scratch on a cadence):
tool_retire is the explicit "this tool is done, delete it, learn from it" path.

Learning loop (Law #6, self-improving):
  * skill_ledger.record_decision  -> case law: what got retired, what replaced it
  * training_events.emit(lifecycle_gap) -> training surface (tool retirement)

CLI:
  python -m mag.tool_retire retire NAME --reason ... --replaced-by ...
  python -m mag.tool_retire audit        # list known-obsolete tools
  python -m mag.tool_retire list         # recent retirements
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except ImportError:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

TRASH = ROOT / "memory" / "trash" / "tools"
LEDGER = ROOT / "memory" / "tools" / "retired.jsonl"

# Known-obsolete tools: (glob, reason, replaced_by). Kept as a living list so the
# learning loop accumulates what has been superseded.
_OBSOLETE: list[tuple[str, str, str]] = [
    ("_tmp_*.py", "one-off scratch probe", "scoped module / skill_pipeline"),
    ("launch_agent_local.cmd", "local ollama seat superseded", "launch_agent_machine.cmd / container"),
    ("launch_agent_deepseek.cmd", "direct deepseek seat superseded", "queue path via orchestrator"),
    ("launch_desk.cmd", "legacy desk boot", "launch_agent_desk.cmd"),
    ("deliver/", "obsolete staging", "Desktop/Mag/Output (embassy_deliver)"),
    ("codex_*", "codex scratch", "tool_retire/cleanup"),
    ("pytest-of-*", "pytest scratch", "cleanup cadence"),
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _append_ledger(row: dict[str, Any]) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _fold_learning(row: dict[str, Any]) -> None:
    """Fold the retirement into the learning loop (case law + training surface)."""
    try:
        from mag import skill_ledger, training_events
        skill_ledger.record_decision(
            goal="tool_retire",
            task_shape="tool_lifecycle",
            provider="local",
            model="tool_retire",
            reasoning_level="none",
            seat="",
            outcome="ok",
            detail=f"retired {row.get('name')} -> {row.get('replaced_by') or 'none'}",
            source="tool_retire",
        )
        training_events.emit(
            "lifecycle_gap",
            input_data={"name": row.get("name")},
            action={"kind": "tool_retire", "reason": row.get("reason", "")[:200]},
            outcome={"replaced_by": row.get("replaced_by") or ""},
            pattern_tags=["tool_retire", "delete_after_use", "learning_loop"],
            tier_max="T1",
            exportable=False,
        )
    except Exception:
        pass


def _resolve(name: str) -> list[Path]:
    """Resolve a tool name (filename or glob) under ROOT into concrete paths."""
    matches: list[Path] = []
    p = ROOT / name
    if p.exists():
        matches.append(p)
        return matches
    # try globs
    for pat in (name, f"**/{name}", f"**/*{name}*"):
        try:
            matches.extend(ROOT.glob(pat))
        except Exception:
            continue
    # dedupe
    return list(dict.fromkeys(matches))


def retire(name: str, *, reason: str = "", replaced_by: str = "", dry: bool = True) -> dict[str, Any]:
    """Retire a tool: move to trash + fold the lesson into the learning loop."""
    targets = _resolve(name)
    if not targets:
        return {"ok": False, "schema": "tool_retire.v1", "error": f"no such tool: {name}"}

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = TRASH / ts
    moved = []
    for t in targets:
        rel = str(t.relative_to(ROOT)).replace("\\", "/").replace("/", "__")
        if not dry:
            dest.mkdir(parents=True, exist_ok=True)
            shutil.move(str(t), str(dest / rel))
        moved.append({"path": str(t.relative_to(ROOT)).replace("\\", "/")})

    row = {
        "schema": "tool_retire.v1",
        "ts": _now(),
        "name": name,
        "reason": reason,
        "replaced_by": replaced_by,
        "moved": moved,
        "dry": dry,
        "trash": str(dest),
    }
    _append_ledger(row)
    if not dry:
        _fold_learning(row)
    else:
        row["note"] = "dry run — nothing moved, nothing folded"
    return row


def audit() -> dict[str, Any]:
    """List known-obsolete tools that could be retired (dry)."""
    found = []
    for pat, reason, replaced in _OBSOLETE:
        for t in _resolve(pat):
            if t.exists():
                found.append({
                    "pattern": pat, "path": str(t.relative_to(ROOT)).replace("\\", "/"),
                    "reason": reason, "replaced_by": replaced,
                })
    return {"schema": "tool_retire.audit.v1", "n": len(found), "items": found}


def list_retired(limit: int = 20) -> list[dict[str, Any]]:
    if not LEDGER.is_file():
        return []
    rows = []
    for line in LEDGER.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows[-limit:]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="mag.tool_retire")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_retire = sub.add_parser("retire")
    p_retire.add_argument("name")
    p_retire.add_argument("--reason", default="")
    p_retire.add_argument("--replaced-by", default="")
    p_retire.add_argument("--live", action="store_true", help="actually move to trash + fold learning")
    p_retire.set_defaults(fn=lambda a: print(json.dumps(
        retire(a.name, reason=a.reason, replaced_by=a.replaced_by, dry=not a.live),
        indent=2, ensure_ascii=False)))

    p_audit = sub.add_parser("audit")
    p_audit.set_defaults(fn=lambda a: print(json.dumps(audit(), indent=2, ensure_ascii=False)))

    p_list = sub.add_parser("list")
    p_list.set_defaults(fn=lambda a: print(json.dumps(list_retired(), indent=2, ensure_ascii=False)))

    args = ap.parse_args(argv)
    args.fn(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
