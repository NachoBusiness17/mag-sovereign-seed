#!/usr/bin/env python3
"""Lossless, bounded archive dereference for the RIB.

Spans are one-based inclusive JSONL line ranges:

    python -m mag.read_archive "/board/openclaw_traj.jsonl:1-3"

The command is read-only. It returns the exact selected lines plus a SHA-256
digest. When trajectory metadata is present, it also checks the writer's
body hash and reports whether the bound is verified. Legacy lines remain
readable but are explicitly marked unbounded/unverified.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SPAN_RE = re.compile(r"^(?P<path>.+):(?P<start>\d+)-(?P<end>\d+)$")


def _resolve(raw: str) -> Path:
    candidate = Path(raw)
    if raw.startswith("/board/"):
        candidate = ROOT / "watch" / raw.removeprefix("/board/")
    elif raw.startswith("/mag/"):
        candidate = ROOT / raw.removeprefix("/mag/")
    elif not candidate.is_absolute():
        candidate = ROOT / candidate
    resolved = candidate.resolve()
    allowed = [ROOT.resolve()]
    board = Path("/board")
    if board.exists():
        allowed.append(board.resolve())
    if not any(os.path.commonpath([str(resolved), str(base)]) == str(base) for base in allowed):
        raise ValueError("archive path is outside the readable project/board roots")
    return resolved


def parse_span(span: str) -> tuple[Path, int, int]:
    match = SPAN_RE.match(span.strip())
    if not match:
        raise ValueError("span must be <path>:<start>-<end>, with one-based inclusive lines")
    start, end = int(match.group("start")), int(match.group("end"))
    if start < 1 or end < start:
        raise ValueError("invalid line range")
    return _resolve(match.group("path")), start, end


def _body_hash(record: dict[str, Any]) -> str:
    base = {k: v for k, v in record.items() if k != "metadata"}
    body = (json.dumps(base, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    return hashlib.sha256(body).hexdigest()


def deref(path: Path, start: int, end: int) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    selected: list[bytes] = []
    total = 0
    with path.open("rb") as f:
        for number, raw in enumerate(f, start=1):
            total = number
            if start <= number <= end:
                selected.append(raw)
            if number > end:
                break
    raw_bytes = b"".join(selected)
    lines: list[Any] = []
    metadata: list[dict[str, Any]] = []
    for raw in selected:
        text = raw.decode("utf-8", errors="replace").rstrip("\r\n")
        try:
            record = json.loads(text)
        except json.JSONDecodeError:
            record = None
        lines.append(record if record is not None else text)
        if isinstance(record, dict) and isinstance(record.get("metadata"), dict):
            meta = dict(record["metadata"])
            expected = meta.get("bodySha256")
            meta["bodyHashVerified"] = bool(expected and expected == _body_hash(record))
            metadata.append(meta)
    return {
        "ok": True,
        "schema": "read_archive.v1",
        "path": str(path),
        "span": f"{path}:{start}-{min(end, total)}",
        "requested": [start, end],
        "returned": len(selected),
        "total_lines_seen": total,
        "sha256": hashlib.sha256(raw_bytes).hexdigest(),
        "bounded": len(metadata) == len(selected) and bool(selected),
        "metadata": metadata,
        "lines": lines,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="mag.read_archive")
    ap.add_argument("span", help="<path>:<start>-<end>")
    ap.add_argument("--raw", action="store_true", help="print exact selected bytes instead of JSON")
    args = ap.parse_args(argv)
    try:
        path, start, end = parse_span(args.span)
        result = deref(path, start, end)
    except (OSError, ValueError) as exc:
        print(json.dumps({"ok": False, "schema": "read_archive.v1", "error": str(exc)}))
        return 2
    if args.raw:
        for item in result["lines"]:
            if isinstance(item, str):
                print(item)
            else:
                print(json.dumps(item, ensure_ascii=False, separators=(",", ":")))
    else:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
