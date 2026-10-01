"""Rebuild trustworthy bounds metadata for the OpenClaw trajectory tape.

This is a read-only scanner over a JSONL tape.  It never rewrites the tape;
it records physical line count, full-file hash, and how many records carry a
valid ``trajectory_span.v1`` metadata envelope.  The output is intentionally
small so ``read_archive`` can reject stale or unbounded dereferences.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _display_path(path: Path) -> str:
    try:
        rel = path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)
    if rel == "watch/openclaw_traj.jsonl":
        return "/board/openclaw_traj.jsonl"
    return rel


def build_bounds(tape: str | Path, output: str | Path | None = None) -> dict:
    path = Path(tape)
    if not path.is_absolute():
        path = ROOT / path
    data = path.read_bytes() if path.is_file() else b""
    lines = data.splitlines(keepends=True)
    bounded = 0
    ranges: list[tuple[int, int]] = []
    malformed = 0
    for index, raw in enumerate(lines, start=1):
        try:
            row = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            malformed += 1
            continue
        metadata = row.get("metadata") if isinstance(row, dict) else None
        if not isinstance(metadata, dict) or metadata.get("schema") != "trajectory_span.v1":
            continue
        line_range = metadata.get("lineRange")
        byte_range = metadata.get("byteRange")
        body_hash = metadata.get("bodySha256")
        if (
            isinstance(line_range, list) and len(line_range) == 2
            and line_range == [index, index]
            and isinstance(byte_range, list) and len(byte_range) == 2
            and all(isinstance(v, int) and v >= 0 for v in byte_range)
            and byte_range[1] > byte_range[0]
            and isinstance(body_hash, str) and len(body_hash) == 64
        ):
            bounded += 1
            ranges.append((line_range[0], line_range[1]))

    contiguous = ranges == [(i, i) for i in range(1, len(ranges) + 1)]
    result = {
        "schema": "tape_bounds.v1",
        "tape": _display_path(path),
        "lines": len(lines),
        "bounded": bounded,
        "legacyUnbounded": max(0, len(lines) - bounded),
        "malformed": malformed,
        "writer": "deploy/openclaw/hooks/mag-file/handler.js",
        "prefixAnchored": bool(bounded and contiguous and bounded == len(lines)),
        "tapeSha": "sha256:" + hashlib.sha256(data).hexdigest(),
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    if output is not None:
        target = Path(output)
        if not target.is_absolute():
            target = ROOT / target
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mag.trajectory_bounds")
    parser.add_argument("--tape", default="watch/openclaw_traj.jsonl")
    parser.add_argument("--output", default="watch/openclaw_traj.jsonl.bounds.meta.json")
    args = parser.parse_args(argv)
    print(json.dumps(build_bounds(args.tape, args.output), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
