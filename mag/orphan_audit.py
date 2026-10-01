"""Find artifacts that claim work without a trustworthy completion boundary.

This scanner is intentionally conservative and read-only by default. It does
not delete, move, apply, or mark anything complete. ``--write`` writes the
report to the shared ``watch`` surface so every client can inspect the same
snapshot.

CLI::
    python -m mag.orphan_audit
    python -m mag.orphan_audit --write
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PATCH_QUEUE = ROOT / "queue" / "handoff" / "openclaw" / "PATCHES"
JOBS = ROOT / "jobs"
OCTANT = ROOT / "watch" / "octant_20260831"
TASKS = ROOT / "memory" / "runs" / "orchestrator" / "tasks"
MAIL = ROOT / "memory" / "mail"
REPORT = ROOT / "watch" / "ORPHAN_AUDIT.json"
PROTECTED_EXTERNAL_SEATS = {"autoclaw", "zcode", "notion"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _json(path: Path) -> tuple[Any | None, str | None]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except Exception as exc:  # noqa: BLE001
        return None, str(exc)


def _patches() -> dict[str, Any]:
    pending = sorted(PATCH_QUEUE.glob("*.json")) if PATCH_QUEUE.is_dir() else []
    applied = sorted((PATCH_QUEUE / "applied").glob("*.json")) if (PATCH_QUEUE / "applied").is_dir() else []
    rejected = sorted((PATCH_QUEUE / "rejected").glob("*.json")) if (PATCH_QUEUE / "rejected").is_dir() else []
    rows: list[dict[str, Any]] = []
    targets: dict[str, list[str]] = {}
    for path in pending:
        payload, error = _json(path)
        row: dict[str, Any] = {"file": path.name}
        if error:
            row.update({"status": "invalid_json", "error": error})
        elif not isinstance(payload, dict):
            row.update({"status": "invalid_payload", "error": "not an object"})
        else:
            target = str(payload.get("path") or "").replace("\\", "/")
            row["path"] = target
            if target:
                targets.setdefault(target, []).append(path.name)
            target_path = ROOT / target if target and not Path(target).is_absolute() else None
            if not target:
                row.update({"status": "invalid_payload", "error": "missing path"})
            elif payload.get("search") is not None:
                found = False
                search = str(payload["search"]).replace("\r\n", "\n")
                if target_path and target_path.is_file():
                    try:
                        found = search in target_path.read_text(encoding="utf-8")
                    except OSError:
                        pass
                row.update({"status": "ready" if found else "search_not_found",
                            "target_exists": bool(target_path and target_path.is_file()),
                            "search_match": found,
                            "line_ending_normalized": payload["search"] != search})
            elif payload.get("content") is not None:
                row.update({"status": "ready", "target_exists": bool(target_path and target_path.is_file())})
            else:
                row.update({"status": "invalid_payload", "error": "no search or content"})
        rows.append(row)
    duplicates = {target: names for target, names in targets.items() if len(names) > 1}
    return {"pending_n": len(pending), "applied_archive_n": len(applied),
            "rejected_archive_n": len(rejected), "pending": rows,
            "duplicate_targets": duplicates}


def _jobs() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    if not JOBS.is_dir():
        return {"job_n": 0, "rows": []}
    for directory in sorted(p for p in JOBS.iterdir() if p.is_dir()):
        contract = directory / "seat_contract.json"
        trails = sorted(directory.glob("trail_core_*.md"))
        row: dict[str, Any] = {"job_id": directory.name, "contract": contract.is_file(),
                               "trail_n": len(trails), "latest_trail": trails[-1].name if trails else None}
        if not contract.is_file():
            row.update({"status": "missing_contract"})
        else:
            value, error = _json(contract)
            if error or not isinstance(value, dict):
                row.update({"status": "invalid_contract", "error": error or "not an object"})
            elif not trails:
                row.update({"status": "no_trail"})
            else:
                try:
                    latest_text = trails[-1].read_text(encoding="utf-8")
                except OSError:
                    latest_text = ""
                row.update({"status": "not_started" if "NOT_STARTED" in latest_text else "contract_and_trail"})
        rows.append(row)
    return {"job_n": len(rows), "rows": rows,
            "attention": [row for row in rows if row["status"] in
                          {"missing_contract", "invalid_contract", "no_trail", "not_started"}]}


def _octant() -> dict[str, Any]:
    rows_dir = OCTANT / "rows"
    actual = sorted(path.name for path in rows_dir.glob("*.row.md")) if rows_dir.is_dir() else []
    declared: set[str] = set()
    for source in OCTANT.glob("*.md"):
        try:
            text = source.read_text(encoding="utf-8")
        except OSError:
            continue
        declared.update(re.findall(r"(?:/|\\)rows(?:/|\\)([A-Za-z0-9_.-]+\.row\.md)", text))
    missing = sorted(name for name in declared if name not in actual)
    unlanded = []
    for name in actual:
        try:
            text = (rows_dir / name).read_text(encoding="utf-8")
        except OSError:
            continue
        if "status**: UNLANDED" in text or "status: UNLANDED" in text:
            unlanded.append(name)
    return {"actual_rows": actual, "declared_rows": sorted(declared),
            "declared_but_missing": missing,
            "unlanded_rows": sorted(unlanded),
            "status": "pointer_drift" if missing else "aligned"}


def _task_ledger() -> dict[str, Any]:
    counts: Counter[str] = Counter()
    active: list[dict[str, Any]] = []
    protected: list[dict[str, Any]] = []
    if TASKS.is_dir():
        for path in TASKS.glob("*.json"):
            value, error = _json(path)
            if error or not isinstance(value, dict):
                counts["invalid"] += 1
                continue
            status = str(value.get("status") or "unknown")
            counts[status] += 1
            if status in {"running", "stalled"}:
                row = {"file": path.name, "task_id": value.get("task_id"),
                       "status": status, "created_at": value.get("created_at"),
                       "seat": value.get("seat"), "pid": value.get("pid"),
                       "goal": value.get("goal"), "detail": value.get("detail")}
                if (status == "running" and not value.get("pid")
                        and str(value.get("seat") or "").lower() in PROTECTED_EXTERNAL_SEATS):
                    row["classification"] = "protected_external_no_auto_reap"
                    protected.append(row)
                else:
                    active.append(row)
    return {"counts": dict(sorted(counts.items())), "active": active, "protected": protected}


def _mail_ledger() -> dict[str, Any]:
    counts: Counter[str] = Counter()
    if MAIL.is_dir():
        for path in MAIL.glob("*/status.json"):
            value, error = _json(path)
            if error or not isinstance(value, dict):
                counts["invalid"] += 1
            else:
                counts[str(value.get("phase") or value.get("status") or "unknown")] += 1
    return {"counts": dict(sorted(counts.items()))}


def build_report() -> dict[str, Any]:
    patches = _patches()
    jobs = _jobs()
    octant = _octant()
    tasks = _task_ledger()
    mail = _mail_ledger()
    attention = {
        "patches": [row for row in patches["pending"] if row["status"] != "ready"],
        "jobs": jobs["attention"],
        "octant_declared_but_missing": octant["declared_but_missing"],
        "octant_unlanded_rows": octant["unlanded_rows"],
        "active_task_records": tasks["active"],
    }
    return {"schema": "orphan_audit.v1", "generated_at": _now(), "root": str(ROOT),
            "read_only": True, "patches": patches, "jobs": jobs, "octant": octant,
            "orchestrator": tasks, "mail": mail, "attention": attention}


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m mag.orphan_audit")
    parser.add_argument("--write", action="store_true", help="write the report to watch/ORPHAN_AUDIT.json")
    args = parser.parse_args()
    report = build_report()
    if args.write:
        report["read_only"] = False
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        report["written_to"] = str(REPORT)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
