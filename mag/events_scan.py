"""Events-log malformed-line scanner (B2-399 split, 2026-09-26).

Self-contained block moved out of mag/shared_surface.py per the B2-248
module-split precedent (the ratchet's file-too-long law): the file sat at
exactly the 400-line cap after the B2-342/B2-358 landings and the B2-360
lock landing kept adding to sibling modules, so the scanner moves here and
mag.shared_surface re-exports the name (its validate wiring and the tests
address it through that module, same re-export pattern as mag/events_key_schema.py
from B2-342).

Spec unchanged byte-for-byte from the shared_surface.py version this moved:
a line is malformed when it is non-blank (trailing CRLF stripped; both LF
and CRLF terminators occur in the real log) and fails strict json.loads with
NaN/Infinity rejected, mirroring JSON.parse in the fold
(scripts/index_fold_host.mjs readEvents, which warns and skips these).
Records carry content sha256, not just line numbers: the baseline registry
keys on bytes so appends can never shift a match.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from mag.events_key_schema import reject_json_constant


def scan_events_log(events_log: Path) -> list[dict[str, Any]]:
    """Return one record per malformed line of the append-only events log."""
    malformed: list[dict[str, Any]] = []
    if not events_log.is_file():
        return malformed
    with events_log.open("rb") as handle:
        for lineno, raw in enumerate(handle, 1):
            content = raw.rstrip(b"\r\n")
            if not content.strip():
                continue  # the fold skips blank lines the same way
            try:
                json.loads(content, parse_constant=reject_json_constant)
            except (json.JSONDecodeError, ValueError, UnicodeDecodeError):
                malformed.append({
                    "line": lineno,
                    "sha256": hashlib.sha256(content).hexdigest(),
                    "excerpt": content[:120].decode("utf-8", "replace"),
                })
    return malformed
