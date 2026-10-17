"""SEED STUB - audit
The estate runtime's audit module writes receipts to a tamper-evident chain.
This stub appends plain JSONL to audit_seed.jsonl next to the organs - the
honest version of the same idea. Replace it with your own receipt chain;
organs only need log_event().
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

LEDGER = Path(__file__).resolve().parent / "audit_seed.jsonl"


def log_event(kind, **fields):
    """Append one receipt row: kind, timestamp, whatever happened."""
    row = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "kind": kind, **fields}
    try:
        with open(LEDGER, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError:
        pass  # receipts must never crash the work
    return row
