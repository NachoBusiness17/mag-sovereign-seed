"""LINKS.jsonl same-sha duplicate ratchet (B2-173, 2026-09-26).

B2-06 triaged the silent duplicate clusters and flagged them through the
ledger's own append path (flag rows carrying duplicate_of; the historical
dupe rows themselves keep duplicate_of "" because the ledger is
append-only). B2-26 then backfilled a real canonical_sha256 onto every
then-331 link row, which makes sha equality a trustworthy duplicate signal.
This gate spends that signal: any link row whose canonical_sha256 equals an
EARLIER row's canonical_sha256 while its own duplicate_of is empty is
judged. Rows registered in configs/links_sha_ratchet_baseline.json
(content-sha256 keyed, the B2-42/B2-168 grandfather pattern; editing a
registered line drops its cover and the row is re-judged on its merits) are
debt kept in place by the append-only law: 6 rows at gate birth, LINKS.jsonl
lines 100, 184, 186, 255, 258, 265, each already covered by a B2-06 flag row
(lines 306-310) or the kept-with-reason mis-merge correction (line 311). An
unregistered one is an ERROR naming the line, seq, canonical and first-filing
line, pointing at the add door (python -m mag.link_library add) that stamps
duplicate_of at submission; hand appends bypass that door, which is exactly
how every silent dupe on file landed.

Erratum carried at gate birth (bytes over reports): B2-26's receipt
(Evidence last bullet) and the B2-173 queue brief call LINKS.jsonl:265 "an
unflagged silent dupe B2-06 did not flag". The ledger bytes disagree:
LINKS.jsonl:308 (seq 1790422303925615, writer dupe-triage-20260926) is a
B2-06 flag row whose note names re-filing seq 1789736600516927, which IS
line 265. Line 265's own duplicate_of stays empty per the append-only law;
the flag lives on the L308 row per the B2-06 convention. No new flag row was
filed: it would duplicate L308 and trip this very gate.

Scope boundary, named so it cannot rot silently: rows whose
canonical_sha256 is absent or not 64-hex are not subjects of this gate. The
post-B2-26 "op":"register" rows (LINKS.jsonl:336-348 at gate birth) carry no
canonical_sha256 field at all, and lines 340 and 345 among them are an
unflagged same-canonical pair (docs.z.ai/guides/overview/pricing, two
writers) this gate therefore cannot see; that is a schema-cohabitation debt,
briefed separately in the burn queue by this lane. The image-drop class
(B2-172) hashes FILE BYTES into canonical_sha256 rather than the canonical
string; a same-bytes re-drop would trip this gate, and that is desired: the
class belongs in IMAGE_DROPS.jsonl going forward.

This module exists because mag/shared_surface.py sits over the ratchet's
400-line bar (the same reason mag/links_split_gate.py does); the validate
wiring re-exports these names so tests and callers address the gate through
mag.shared_surface.

Receipt: watch/inbox/burn_wave_20260926/B2_173_l265_flag_20260926.md.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LINKS_SHA_BASELINE = ROOT / "configs" / "links_sha_ratchet_baseline.json"

_HEX64 = re.compile(r"^[0-9a-fA-F]{64}$")


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def scan_same_sha_unflagged(links_ledger: Path) -> list[dict[str, Any]]:
    """One record per same-canonical_sha256 row lacking duplicate_of (B2-173).

    File-order scan; the first occurrence of a canonical_sha256 is the first
    filing (append-only monotonic ledger, the B2-122 first-filing-wins law)
    and is never a violation. A later row is returned as a record when its
    canonical_sha256 is 64-hex, was already seen, and its own duplicate_of is
    empty; the record carries line, first_line, seq, canonical, the shared
    canonical_sha256, and line_sha256 (sha256 of the raw line bytes, the
    baseline grandfather key). Unparseable lines are skipped: the events-log
    hygiene gate (B2-42) owns malformed-line debt, this check owns duplicate
    filings only. Rows without a 64-hex sha are skipped per the module scope
    boundary.
    """
    found: list[dict[str, Any]] = []
    seen: dict[str, int] = {}
    with links_ledger.open("rb") as handle:
        for lineno, raw in enumerate(handle, 1):
            content = raw.rstrip(b"\r\n")
            if not content.strip():
                continue
            try:
                row = json.loads(content)
            except (json.JSONDecodeError, ValueError):
                continue
            if not isinstance(row, dict):
                continue
            sha = str(row.get("canonical_sha256") or "")
            if not _HEX64.match(sha):
                continue
            sha = sha.upper()
            first_line = seen.get(sha)
            if first_line is None:
                seen[sha] = lineno
                continue
            if row.get("duplicate_of"):
                continue
            found.append({
                "line": lineno,
                "first_line": first_line,
                "seq": row.get("seq"),
                "canonical": row.get("canonical"),
                "canonical_sha256": sha,
                "line_sha256": hashlib.sha256(content).hexdigest(),
            })
    return found


def links_sha_ratchet_check(links_ledger: Path, baseline_path: Path,
                            errors: list[str], warnings: list[str]) -> None:
    """Validate-door check for the same-sha ratchet; extends the lists.

    Errors: a missing baseline registry (the debt register must exist, the
    B2-168 shape) and any unregistered same-canonical_sha256 row lacking
    duplicate_of. No warning cases of its own: a missing ledger is already
    the split gate's warning, and this scan has nothing to say about an
    absent file.
    """
    grandfathered: set[str] = set()
    if baseline_path.is_file():
        try:
            baseline = _load_json(baseline_path)
            for entry in baseline.get("grandfathered", []):
                if isinstance(entry, dict) and entry.get("sha256"):
                    grandfathered.add(str(entry["sha256"]).lower())
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"invalid links sha ratchet baseline: {exc}")
    else:
        errors.append(f"missing links sha ratchet baseline: {baseline_path}")
    if not links_ledger.is_file():
        return
    for rec in scan_same_sha_unflagged(links_ledger):
        if rec["line_sha256"] in grandfathered:
            continue
        errors.append(
            f"NEW same-canonical_sha256 row in LINKS.jsonl lacking "
            f"duplicate_of (line {rec['line']}, seq {rec['seq']!r}, canonical "
            f"{rec['canonical']!r}, sha {rec['canonical_sha256']}, first "
            f"filed line {rec['first_line']}): stamp duplicate_of at "
            f"submission via the add door (python -m mag.link_library add) "
            f"or register the row in "
            f"configs/links_sha_ratchet_baseline.json with evidence"
        )
