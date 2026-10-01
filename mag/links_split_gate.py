"""LINKS.jsonl event-split gate (B2-168, 2026-09-26).

The B2-28 schema split (2026-09-26) made watch/inbox/LINKS.jsonl
link-rows-only going forward: scout, seat and endpoint-news EVENT rows
(the id/kind/detail shape those writers used to append by hand) belong in
watch/inbox/EVENTS.jsonl with schema "event.v1" (parse path
mag.link_library.load_events). The 51 legacy event rows stay in
LINKS.jsonl (append-only law) below the migration-marker row (schema
"migration-marker.v1", writer "b2-28-schema-split"), so "NEW" is defined
line-wise: any row AFTER that marker carrying a "kind" field is judged
against configs/links_kind_baseline.json (content-sha keyed, the B2-42
grandfather pattern); an unregistered one is an ERROR naming the line and
pointing at EVENTS.jsonl. Post-marker rows that landed before the gate are
registered debt there, mirrored into EVENTS.jsonl with origin provenance,
never erased.

This module exists because mag/shared_surface.py sits over the ratchet's
400-line bar (the same reason mag/events_key_schema.py does); the validate
wiring re-exports these names so tests and callers address the gate through
mag.shared_surface.

Receipt: watch/inbox/burn_wave_20260926/B2_168_event_split_gate_20260926.md.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

MARKER_SCHEMA = "migration-marker.v1"
MARKER_WRITER = "b2-28-schema-split"

ROOT = Path(__file__).resolve().parents[1]
LINKS_LEDGER = ROOT / "watch" / "inbox" / "LINKS.jsonl"
LINKS_KIND_BASELINE = ROOT / "configs" / "links_kind_baseline.json"


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def links_split_check(links_ledger: Path, baseline_path: Path,
                      errors: list[str], warnings: list[str]) -> None:
    """Validate-door check for the LINKS event split; extends the lists.

    Errors: a missing baseline registry (the debt register must exist) and
    any post-marker kind row whose content sha256 is not registered in it.
    Warnings: a missing marker row (the split cannot be enforced without
    its anchor) and a missing LINKS.jsonl (container surfaces may not mount
    the repo). Registered rows are grandfathered debt: they stay in
    LINKS.jsonl (no-erase), mirrored into EVENTS.jsonl with origin
    provenance.
    """
    grandfathered: set[str] = set()
    if baseline_path.is_file():
        try:
            baseline = _load_json(baseline_path)
            for entry in baseline.get("grandfathered", []):
                if isinstance(entry, dict) and entry.get("sha256"):
                    grandfathered.add(str(entry["sha256"]).lower())
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"invalid links kind baseline: {exc}")
    else:
        errors.append(f"missing links kind baseline: {baseline_path}")
    if not links_ledger.is_file():
        warnings.append(f"links ledger not found: {links_ledger}")
        return
    if not links_split_marker_line(links_ledger):
        warnings.append(
            "links schema-split marker missing in LINKS.jsonl: the B2-28 "
            "split cannot be enforced without its anchor row"
        )
    for rec in scan_links_kind_rows(links_ledger):
        if rec["sha256"].lower() in grandfathered:
            continue
        errors.append(
            f"NEW event-kind row in LINKS.jsonl (line {rec['line']}, id "
            f"{rec['id']!r}, kind {rec['kind']!r}, writer {rec['writer']!r}): "
            f"LINKS.jsonl is link rows only past the B2-28 marker; file "
            f"events in watch/inbox/EVENTS.jsonl (schema event.v1) via "
            f"mag.link_library.load_events"
        )


def links_split_marker_line(links_ledger: Path) -> int:
    """Line number of the B2-28 migration-marker row, 0 when absent (B2-168)."""
    if not links_ledger.is_file():
        return 0
    with links_ledger.open("rb") as handle:
        for lineno, raw in enumerate(handle, 1):
            content = raw.rstrip(b"\r\n")
            if not content.strip():
                continue
            try:
                row = json.loads(content)
            except (json.JSONDecodeError, ValueError):
                continue
            if (isinstance(row, dict)
                    and row.get("schema") == MARKER_SCHEMA
                    and row.get("writer") == MARKER_WRITER):
                return lineno
    return 0


def scan_links_kind_rows(links_ledger: Path) -> list[dict[str, Any]]:
    """Return one record per NEW event-kind row in LINKS.jsonl (B2-168).

    Rows ABOVE the B2-28 migration marker are grandfathered (append-only
    law); any row BELOW it carrying a "kind" field is NEW and returned as
    one record ({line, id, kind, writer, sha256}) for the validate gate to
    judge against configs/links_kind_baseline.json. Unparseable lines are
    skipped: the events-log hygiene gate (B2-42) owns malformed-line debt,
    and this check owns schema cohabitation only.
    """
    found: list[dict[str, Any]] = []
    marker_line = links_split_marker_line(links_ledger)
    if not marker_line:
        return found
    with links_ledger.open("rb") as handle:
        for lineno, raw in enumerate(handle, 1):
            if lineno <= marker_line:
                continue
            content = raw.rstrip(b"\r\n")
            if not content.strip():
                continue
            try:
                row = json.loads(content)
            except (json.JSONDecodeError, ValueError):
                continue
            if isinstance(row, dict) and "kind" in row:
                found.append({
                    "line": lineno,
                    "id": row.get("id"),
                    "kind": row.get("kind"),
                    "writer": row.get("writer"),
                    "sha256": hashlib.sha256(content).hexdigest(),
                })
    return found
