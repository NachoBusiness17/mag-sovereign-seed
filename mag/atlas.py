#!/usr/bin/env python3
"""Atlas — the generated map of verified Mag organs.

Atlas is not a second registry. It compiles the receipts-first organ map and
its declared topology into a durable artifact. Unknown stays unknown; a
module name alone never advances a status.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "memory" / "runs" / "atlas"
ATLAS = OUT_DIR / "atlas.json"
RECEIPTS = OUT_DIR / "receipts.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _receipt(row: dict[str, Any]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with RECEIPTS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def build(scope: str = "operational") -> dict[str, Any]:
    """Compile the current organ map and topology without model/network calls."""
    from .organ_map import map_organs, operational_graph

    inventory = map_organs()
    graph = operational_graph()
    result = {
        "ok": True,
        "schema": "atlas.v1",
        "ts": _now(),
        "scope": scope,
        "summary": inventory.get("summary", {}),
        "organs": inventory.get("organs", []),
        "graph": graph,
        "law": "map precedes territory; evidence advances claims",
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ATLAS.write_text(json.dumps(result, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    _receipt({"schema": "atlas.receipt.v1", "ts": result["ts"], "ok": True,
              "scope": scope, "path": str(ATLAS.relative_to(ROOT)).replace("\\", "/"),
              "summary": result["summary"]})
    return result


def status() -> dict[str, Any]:
    if not ATLAS.is_file():
        return {"ok": False, "schema": "atlas.v1", "error": "atlas not built"}
    try:
        return json.loads(ATLAS.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "schema": "atlas.v1", "error": str(exc)[:200]}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="mag.atlas")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--scope", default="operational")
    sub.add_parser("status")
    args = ap.parse_args(argv)
    result = build(args.scope) if args.cmd == "build" else status()
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
