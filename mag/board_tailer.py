#!/usr/bin/env python3
"""Observe the image-board log and surface governed directives.

The room is an interaction surface, not an authority surface. This module is
deliberately a poller with a durable byte cursor:

* ordinary roasts, replies, and bootstrap chatter are recorded as ignored;
* explicit ``>>route``/``!route``/``>>steer`` markers become proposals;
* delegation is opt-in with ``--dispatch`` and still goes through
  ``board_directive`` (route -> seat_dispatch, steer -> switchboard);
* no model call and no automatic task launch happen during observation.

That gives us an honest liveness receipt for the board->proposal rib without
pretending the board itself can grant permission.

Usage:
  python -m mag.board_tailer poll --max-lines 5000
  python -m mag.board_tailer poll --max-lines 5000 --dispatch
  python -m mag.board_tailer watch --interval 2
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from . import board_directive

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROOM = ROOT / "watch" / "room.jsonl"
STATE_DIR = ROOT / "memory" / "runs" / "board_tailer"
STATE_PATH = STATE_DIR / "cursor.json"
EVENTS_PATH = STATE_DIR / "events.jsonl"
RECEIPT_PATH = STATE_DIR / "last_receipt.json"


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _load_state(path: Path) -> dict[str, Any]:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _append_event(path: Path, event: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")


def _read_new(room: Path, state: dict[str, Any], max_lines: int) -> tuple[list[tuple[int, dict[str, Any]]], int]:
    """Read complete JSONL records after the durable byte cursor."""
    offset = int(state.get("offset", 0) or 0)
    if not room.exists():
        return [], offset
    size = room.stat().st_size
    if offset > size:
        offset = 0  # log was rotated/truncated

    records: list[tuple[int, dict[str, Any]]] = []
    with room.open("rb") as f:
        f.seek(offset)
        while len(records) < max_lines:
            start = f.tell()
            raw = f.readline()
            if not raw:
                break
            end = f.tell()
            if not raw.endswith(b"\n"):
                # A writer may be mid-record; leave it for the next poll.
                f.seek(start)
                break
            try:
                obj = json.loads(raw.decode("utf-8", errors="replace"))
            except Exception:
                obj = {"text": raw.decode("utf-8", errors="replace"), "raw": True}
            if not isinstance(obj, dict):
                obj = {"text": str(obj), "raw": True}
            records.append((end, obj))
        new_offset = f.tell()
    return records, new_offset


def _candidate(rec: dict[str, Any]) -> bool:
    event = str(rec.get("event") or "")
    return event in {"chan_post", "chan_op"} or bool(rec.get("steer"))


def _delegate(rec: dict[str, Any], *, dispatch: bool) -> dict[str, Any]:
    if not dispatch:
        return {"ok": True, "action": "proposal-only", "skipped": "dispatch not requested"}
    raw = json.dumps(rec, ensure_ascii=False)
    try:
        p = subprocess.run(
            [sys.executable, "-m", "mag.board_directive", "gate", "--stdin"],
            input=raw + "\n", text=True, capture_output=True,
            encoding="utf-8", errors="replace", timeout=120, cwd=str(ROOT),
        )
        return {
            "ok": p.returncode == 0,
            "action": "delegated",
            "rc": p.returncode,
            "output_head": (p.stdout or "")[-1200:],
            "error_head": (p.stderr or "")[-400:],
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "action": "delegated", "error": str(exc)[:400]}


def poll(*, room: Path, state_path: Path, events_path: Path,
         dispatch: bool = False, max_lines: int = 200) -> dict[str, Any]:
    state = _load_state(state_path)
    records, new_offset = _read_new(room, state, max_lines=max_lines)
    seen = 0
    candidates = 0
    proposals = 0
    delegated = 0
    ignored = 0
    failures = 0

    for offset, rec in records:
        seen += 1
        digest = hashlib.sha256(json.dumps(rec, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]
        item: dict[str, Any] = {
            "schema": "board_tailer.v1",
            "ts": _now(),
            "room_offset": offset,
            "record_hash": digest,
            "event": rec.get("event"),
            "seat": rec.get("seat") or rec.get("actor") or "unknown",
            "thread": rec.get("thread"),
            "text_head": str(rec.get("text") or "")[:240],
        }
        if not _candidate(rec):
            item["decision"] = "ignored_non_directive_event"
            ignored += 1
            _append_event(events_path, item)
            continue
        candidates += 1
        directive = board_directive._decode(rec)
        if directive is None:
            item["decision"] = "ignored_no_marker"
            item["note"] = "a roast never routes"
            ignored += 1
            _append_event(events_path, item)
            continue

        proposals += 1
        item["decision"] = "proposal"
        item["effect"] = directive.effect
        item["reason"] = directive.reason
        item["proposal"] = directive.to_proposal()
        result = _delegate(rec, dispatch=dispatch)
        item["delegation"] = result
        if dispatch:
            delegated += 1
            if not result.get("ok"):
                failures += 1
        _append_event(events_path, item)

    new_state = {
        "schema": "board_tailer.cursor.v1",
        "room": str(room),
        "offset": new_offset,
        "updated_ts": _now(),
    }
    _save_state(state_path, new_state)
    result = {
        "ok": failures == 0,
        "schema": "board_tailer.v1",
        "ts": _now(),
        "room": str(room),
        "offset": new_offset,
        "seen": seen,
        "candidates": candidates,
        "proposals": proposals,
        "delegated": delegated,
        "ignored": ignored,
        "failures": failures,
        "dispatch": dispatch,
    }
    # Event rows intentionally describe individual ignored/proposed records;
    # keep a separate latest aggregate so the organ map can judge poll health
    # without treating a benign ignored event as a failed run.
    _save_state(RECEIPT_PATH, {
        "schema": "board_tailer.receipt.v1",
        "ts": result["ts"],
        "ok": result["ok"],
        "seen": seen,
        "candidates": candidates,
        "proposals": proposals,
        "delegated": delegated,
        "ignored": ignored,
        "failures": failures,
        "dispatch": dispatch,
    })
    return result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="mag.board_tailer")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("poll", "watch"):
        p = sub.add_parser(name)
        p.add_argument("--room", type=Path, default=DEFAULT_ROOM)
        p.add_argument("--state", type=Path, default=STATE_PATH)
        p.add_argument("--events", type=Path, default=EVENTS_PATH)
        p.add_argument("--dispatch", action="store_true",
                       help="delegate explicit markers through board_directive")
        p.add_argument("--max-lines", type=int, default=200)
        p.add_argument("--interval", type=float, default=2.0)
    args = ap.parse_args(argv)
    if not args.room.exists():
        print(json.dumps({"ok": False, "error": "room file not found", "room": str(args.room)}))
        return 2
    if args.cmd == "poll":
        print(json.dumps(poll(room=args.room, state_path=args.state, events_path=args.events,
                              dispatch=args.dispatch, max_lines=args.max_lines), indent=2))
        return 0
    try:
        while True:
            result = poll(room=args.room, state_path=args.state, events_path=args.events,
                          dispatch=args.dispatch, max_lines=args.max_lines)
            if result["seen"] or result["failures"]:
                print(json.dumps(result, ensure_ascii=False), flush=True)
            time.sleep(max(0.2, args.interval))
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
