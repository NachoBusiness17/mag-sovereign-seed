"""Events key schema gate: the writer-key vocabulary of the shared events log.

Spec owner for the gate wired into mag.shared_surface.validate (B2-342,
2026-09-26). The B2-329 dump purity law made the writer-key vocabulary
load-bearing (a strict downstream consumer of the `events` dump rejects any
key outside it), but no spec owned the vocabulary. The spec is now
configs/events_key_schema.json: every key any writer ever appended, each
with first-seen line, seq (decimal string per the B2-40 scheme), ts and
owning writer, censused at a recorded log sha256. The registry is a CLOSED
VOCABULARY, not a required-fields spec: any registered key may be omitted
on any line. The gate:

- An event key NOT in the registry is an ERROR, one per distinct key, naming
  the key, occurrence count, first line, seq and owning writer: register it
  by name (with first-seen evidence and a carries note) or fix the writer.
  The fold's warning channel names the same keys (WARN + exit 2).
- The underscore prefix is reserved for fold-internal fields (B2-329 dump
  purity); underscore keys are exempt from the scan and must never be
  written to the log.
- A missing or unreadable registry is an ERROR (the spec must exist).
- Census counts and first-seen lines are point-in-time facts at the recorded
  sha256; appends never invalidate an entry, only NEW keys do.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
EVENTS_KEY_SCHEMA = ROOT / "configs" / "events_key_schema.json"


def reject_json_constant(name: str) -> Any:
    # JS JSON.parse rejects NaN/Infinity; bare json.loads accepts them. Reject
    # so this scanner matches the fold's tolerant-reader semantics exactly.
    raise ValueError(f"non-JSON constant: {name}")


def load_event_key_registry(path: Path = EVENTS_KEY_SCHEMA) -> set[str]:
    """Return the closed vocabulary of writer keys from configs/events_key_schema.json.

    Only the key NAMES are load for the gate; first-seen evidence fields are
    documentation. Raises on a missing, unreadable or shape-invalid registry
    (the spec must exist).
    """
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    entries = value.get("keys")
    if not isinstance(entries, list) or not entries:
        raise ValueError(f"registry carries no keys list: {path}")
    known: set[str] = set()
    for entry in entries:
        if isinstance(entry, dict) and isinstance(entry.get("key"), str) and entry["key"]:
            known.add(entry["key"])
    if not known:
        raise ValueError(f"registry keys list carries no key names: {path}")
    return known


def scan_event_keys(events_log: Path, known: set[str]) -> dict[str, Any]:
    """Census every event key outside the registry vocabulary.

    Scans the parseable lines of the events log (same strict json.loads with
    NaN/Infinity rejected as mag.shared_surface.scan_events_log; malformed
    lines are that gate's job). Underscore-prefixed keys are exempt: the
    prefix is reserved for fold-internal fields (B2-329 dump purity),
    written by NO writer. Returns {"lines": <parseable lines scanned>,
    "unknown": [per-distinct-key records with count, first line, first seq,
    first writer]}.
    """
    lines = 0
    unknown: dict[str, dict[str, Any]] = {}
    if not events_log.is_file():
        return {"lines": 0, "unknown": []}
    with events_log.open("rb") as handle:
        for lineno, raw in enumerate(handle, 1):
            content = raw.rstrip(b"\r\n")
            if not content.strip():
                continue
            try:
                ev = json.loads(content, parse_constant=reject_json_constant)
            except (json.JSONDecodeError, ValueError, UnicodeDecodeError):
                continue
            if not isinstance(ev, dict):
                continue  # a JSON scalar line carries no event keys
            lines += 1
            for key in ev.keys():
                if key.startswith("_") or key in known:
                    continue
                rec = unknown.get(key)
                if rec is None:
                    unknown[key] = {
                        "key": key,
                        "count": 1,
                        "first_line": lineno,
                        "first_seq": ev.get("seq"),
                        "first_writer": ev.get("writer"),
                    }
                else:
                    rec["count"] += 1
    return {"lines": lines, "unknown": sorted(unknown.values(), key=lambda r: r["key"])}
