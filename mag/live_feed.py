"""Live feed — tail the framework's trails as running terminal streams.

Watches the overseer, ghost, and drainer trail files live so the operator can see
verbose "what is happening" output in a running VS Code terminal tab (or plain
terminal). Follows appended JSONL lines and prints them as a readable stream.

Kinds:
  overseer  -> memory/runs/session_overseer_trail.jsonl  (+ desk_overseer_trail.jsonl)
  ghost     -> memory/runs/ghost/trail.jsonl             (+ results.jsonl)
  drainer   -> memory/runs/governor_autorun_trail.jsonl  (+ orchestrator_trail.jsonl)

CLI:
  python -m mag.live_feed overseer [--tail 20] [--lines 0]   # stream forever
  python -m mag.live_feed ghost   [--tail 20] [--lines 0]
  python -m mag.live_feed drainer [--tail 20] [--lines 0]
  # --lines N prints last N lines then exits; default 0 = follow forever.
  # --json prints raw JSONL rows instead of pretty text.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except ImportError:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

FEEDS: dict[str, list[Path]] = {
    "overseer": [
        ROOT / "memory" / "runs" / "session_overseer_trail.jsonl",
        ROOT / "memory" / "runs" / "desk_overseer_trail.jsonl",
    ],
    "ghost": [
        ROOT / "memory" / "runs" / "ghost" / "trail.jsonl",
        ROOT / "memory" / "runs" / "ghost" / "results.jsonl",
    ],
    "drainer": [
        ROOT / "memory" / "runs" / "governor_autorun_trail.jsonl",
        ROOT / "memory" / "runs" / "orchestrator_trail.jsonl",
    ],
}

_LABEL = {
    "overseer": "OVERSEER",
    "ghost": "GHOST",
    "drainer": "DRAINER",
}


def _line_reader(path: Path):
    """Yield new lines appended to a file (follow-on-write)."""
    if not path.exists():
        return
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        # seek to end for follow mode (caller truncates for --lines)
        fh.seek(0, 2)
        while True:
            line = fh.readline()
            if line:
                yield line
            else:
                time.sleep(0.4)


def _pretty(row: dict[str, Any]) -> str:
    """Render a trail row as a readable single line."""
    ts = str(row.get("ts") or row.get("timestamp") or row.get("created_at") or "")[:19]
    event = str(row.get("event") or row.get("type") or row.get("kind") or "row")
    goal = str(row.get("goal") or row.get("message") or row.get("detail") or "")
    if len(goal) > 140:
        goal = goal[:137] + "..."
    phase = str(row.get("phase") or "")
    action = str(row.get("action") or row.get("status") or "")
    bits = [f"[{event}]"]
    if phase:
        bits.append(f"phase={phase}")
    if action:
        bits.append(f"action={action}")
    if goal:
        bits.append(goal)
    return f"{ts}  {' '.join(bits)}"


def _emit(path: Path, pretty: bool, seen: dict[str, int]) -> None:
    """Print new rows from one feed file, tracking last byte offset per path."""
    if not path.exists():
        return
    key = str(path)
    offset = seen.get(key, 0)
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            fh.seek(offset)
            for line in fh:
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(row, dict):
                    continue
                if pretty:
                    print(_pretty(row))
                else:
                    print(line.rstrip())
                seen[key] = fh.tell()
    except OSError:
        pass


def watch(kind: str, *, tail: int = 20, lines: int = 0, json_out: bool = False) -> int:
    paths = FEEDS.get(kind)
    if not paths:
        print(f"unknown feed {kind!r}: {', '.join(FEEDS)}", file=sys.stderr)
        return 2
    label = _LABEL.get(kind, kind.upper())

    # Ensure each file exists so offsets are meaningful.
    for p in paths:
        p.parent.mkdir(parents=True, exist_ok=True)
        if not p.exists():
            p.touch()

    if lines and lines > 0:
        # Print last N lines across all files then exit.
        collected: list[str] = []
        for p in paths:
            try:
                data = p.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                data = []
            collected.extend(data[-max(0, lines):])
        for line in collected[-lines:]:
            print(line.rstrip() if json_out else _pretty_safe(line))
        return 0

    # Follow mode.
    seen: dict[str, int] = {}
    for p in paths:
        try:
            seen[str(p)] = p.stat().st_size
        except OSError:
            seen[str(p)] = 0

    print(f"[{label}] watching {len(paths)} trail file(s)... (Ctrl+C to stop)")
    print(f"[{label}] " + " · ".join(str(p.relative_to(ROOT)) for p in paths))
    try:
        while True:
            for p in paths:
                try:
                    _emit(p, not json_out, seen)
                except Exception:
                    pass
            time.sleep(1.0)
    except KeyboardInterrupt:
        print(f"\n[{label}] stopped.")
        return 0
    return 0


def _pretty_safe(line: str) -> str:
    try:
        row = json.loads(line)
        if isinstance(row, dict):
            return _pretty(row)
    except json.JSONDecodeError:
        pass
    return line.rstrip()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="live-feed", description="Tail overseer/ghost/drainer trails as a live terminal feed")
    ap.add_argument("kind", choices=sorted(FEEDS), help="overseer | ghost | drainer")
    ap.add_argument("--tail", type=int, default=20, help="(unused in follow) rows to seed context")
    ap.add_argument("--lines", type=int, default=0, help="print last N lines then exit (default 0 = follow forever)")
    ap.add_argument("--json", action="store_true", help="raw JSONL output")
    args = ap.parse_args(argv)
    return watch(args.kind, tail=args.tail, lines=args.lines, json_out=args.json)


if __name__ == "__main__":
    sys.exit(main())
