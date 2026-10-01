#!/usr/bin/env python3
"""Basecamp — the small climb controller around the evidence map."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "memory" / "runs" / "basecamp"
STATUS_FILE = OUT_DIR / "status.json"
RECEIPTS = OUT_DIR / "receipts.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def status(goal: str = "map the climb") -> dict[str, Any]:
    from .atlas import build

    atlas = build("operational")
    summary = atlas.get("summary", {})
    organs = atlas.get("organs", [])
    ghosts = [r.get("id") for r in organs if r.get("status") == "GHOST"]
    gaps = [
        {"id": r.get("id"), "codes": list(r.get("gap_codes") or [])}
        for r in organs if r.get("gap_codes")
    ]
    structural = [
        row for row in gaps
        if any(code in {"source_missing", "callable_missing", "caller_missing", "caller_undeclared", "state_missing"}
               for code in row["codes"])
    ]
    climb = structural[0] if structural else (gaps[0] if gaps else None)
    next_steps = [
        "keep verified organs bounded by receipts",
        "close the first remaining orphan rib or proof gap",
        "rerun the map after each climb step",
    ]
    if ghosts:
        next_steps[1] = f"close ghost: {ghosts[0]}"
    elif climb:
        next_steps[1] = f"close gap: {climb['id']} ({', '.join(climb['codes'])})"
    result = {
        "ok": True,
        "schema": "basecamp.v1",
        "ts": _now(),
        "goal": goal,
        "summary": summary,
        "ghosts": ghosts,
        "gaps": gaps,
        "next_steps": next_steps,
        "method": "one bounded climb step, receipt, remap",
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    STATUS_FILE.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    with RECEIPTS.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"schema": "basecamp.receipt.v1", "ts": result["ts"],
                            "ok": True, "goal": goal, "ghost_count": len(ghosts)},
                           ensure_ascii=False, sort_keys=True) + "\n")
    return result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="mag.basecamp")
    ap.add_argument("goal", nargs="*", default=["map the climb"])
    args = ap.parse_args(argv)
    print(json.dumps(status(" ".join(args.goal)), indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
