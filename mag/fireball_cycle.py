#!/usr/bin/env python3
"""Fireball cycle — convert one mapped gap into a receipt, then remap."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "memory" / "runs" / "fireball_cycle"
LATEST = OUT_DIR / "latest.json"
RECEIPTS = OUT_DIR / "receipts.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def run(goal: str = "dogfood the mapped organs") -> dict[str, Any]:
    from . import atlas, basecamp, elder

    elder_result = elder.audit()
    atlas_result = atlas.build("operational")
    camp_result = basecamp.status(goal)
    result = {
        "ok": bool(elder_result.get("ok") and atlas_result.get("ok") and camp_result.get("ok")),
        "schema": "fireball_cycle.v1",
        "ts": _now(),
        "goal": goal,
        "steps": {
            "elder": {"ok": bool(elder_result.get("ok")), "gaps": len(elder_result.get("gaps", []))},
            "atlas": {"ok": bool(atlas_result.get("ok")), "summary": atlas_result.get("summary", {})},
            "basecamp": {"ok": bool(camp_result.get("ok")), "ghosts": camp_result.get("ghosts", [])},
        },
        "law": "fireball changes phase and creates a tool; it does not delete mass",
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    LATEST.write_text(json.dumps(result, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    with RECEIPTS.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"schema": "fireball_cycle.receipt.v1", "ts": result["ts"],
                            "ok": result["ok"], "goal": goal,
                            "ghosts": result["steps"]["basecamp"]["ghosts"]},
                           ensure_ascii=False, sort_keys=True) + "\n")
    return result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="mag.fireball_cycle")
    ap.add_argument("goal", nargs="*", default=["dogfood the mapped organs"])
    args = ap.parse_args(argv)
    result = run(" ".join(args.goal))
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
