"""mag/steer_receipt_wire.py

LAW: one append-only tape.
Reads NEW lines from watch/steer_bus_receipts.jsonl (byte-offset tracked in
watch/steer_receipt_wire.state, resume-safe), and for each new row emits an
event into the existing hash-chained stream at state/vast/event_stream.py:
emit(organ=steer_bus, kind=steer.ack, body=row, actor=churn).
Stdlib only. Fail loud.
"""

import argparse
import importlib.util
import json
import sys
from pathlib import Path

RECEIPTS = Path("watch/steer_bus_receipts.jsonl")  # the file steer_bus.py actually writes
OFFSET_STATE = Path("watch/steer_receipt_wire.state")
EVENT_STREAM = Path("state/vast/event_stream.py")

ORGAN = "steer_bus"
KIND = "steer.ack"
ACTOR = "churn"


def _load_event_stream():
    if not EVENT_STREAM.is_file():
        raise FileNotFoundError(f"event stream not found: {EVENT_STREAM}")
    spec = importlib.util.spec_from_file_location("vast_event_stream", EVENT_STREAM)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load spec from {EVENT_STREAM}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _read_offset():
    if not OFFSET_STATE.is_file():
        return 0
    return int(OFFSET_STATE.read_text(encoding="utf-8").strip() or "0")


def _write_offset(offset):
    OFFSET_STATE.parent.mkdir(parents=True, exist_ok=True)
    OFFSET_STATE.write_text(str(offset), encoding="utf-8")


def _iter_new_rows(offset):
    if not RECEIPTS.is_file():
        return [], offset
    data = RECEIPTS.read_bytes()
    if len(data) < offset:
        raise RuntimeError("receipt tape truncated; refusing to resume")
    chunk = data[offset:].decode("utf-8")
    rows = []
    for line in chunk.splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows, len(data)


def run_once():
    stream = _load_event_stream()
    if not hasattr(stream, "emit"):
        raise AttributeError("event_stream module lacks emit()")
    offset = _read_offset()
    rows, new_offset = _iter_new_rows(offset)
    for row in rows:
        stream.emit(organ=ORGAN, kind=KIND, body=row, actor=ACTOR)
    _write_offset(new_offset)
    return len(rows)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="steer_receipt_wire")
    parser.add_argument("--once", action="store_true", help="emit once and exit")
    args = parser.parse_args(argv)
    count = run_once()
    print(f"{count} events emitted")


if __name__ == "__main__":
    main()
