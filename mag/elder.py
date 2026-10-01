#!/usr/bin/env python3
"""Elder — deterministic audit seat for the generated organ map.

The elder reports and ranks evidence gaps; it does not become a second
conductor and never grants permissions. Its output is an audit receipt, not a
command.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "memory" / "runs" / "elder"
REPORT = OUT_DIR / "audit.json"
RECEIPTS = OUT_DIR / "receipts.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def audit() -> dict[str, Any]:
    from .organ_map import map_organs

    inventory = map_organs()
    organs = inventory.get("organs", [])
    def next_action(row: dict[str, Any]) -> str:
        codes = list(row.get("gap_codes") or [])
        if "source_missing" in codes:
            return "add source or mark the organ retired"
        if "callable_missing" in codes:
            return "repair callable import"
        if "caller_missing" in codes or "caller_undeclared" in codes:
            return "connect a named caller and leave a receipt"
        if "state_missing" in codes:
            return "create or correct the declared state path"
        if "proof_failed" in codes:
            return "repair deterministic proof"
        if "receipt_missing" in codes or "receipt_not_successful" in codes:
            return "produce a successful receipt or classify the failure"
        if "receipt_stale" in codes:
            return "run one bounded live dogfood step"
        return "observe live"

    gaps = [
        {
            "id": row.get("id"),
            "status": row.get("status"),
            "codes": list(row.get("gap_codes") or []),
            "next": next_action(row),
            "callable_error": row.get("callable_error", ""),
        }
        for row in organs
        if row.get("gap_codes")
    ]
    # Structural gaps are climbable ribs; stale receipts are useful follow-up
    # work but should not hide an organ that has no caller at all.
    gaps.sort(key=lambda row: (
        not any(code in {"source_missing", "callable_missing", "caller_missing", "caller_undeclared", "state_missing"}
                for code in row["codes"]),
        row["id"] or "",
    ))
    result = {
        "ok": True,
        "schema": "elder.audit.v1",
        "ts": _now(),
        "organ_summary": inventory.get("summary", {}),
        "gaps": gaps,
        "gap_count": len(gaps),
        "law": "contradictions resolve by evidence and hierarchy, not vote",
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(result, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    with RECEIPTS.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"schema": "elder.receipt.v1", "ts": result["ts"],
                            "ok": True, "gap_count": len(gaps),
                            "path": str(REPORT.relative_to(ROOT)).replace("\\", "/")},
                           ensure_ascii=False, sort_keys=True) + "\n")
    return result


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(prog="mag.elder").parse_args(argv)
    print(json.dumps(audit(), indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
