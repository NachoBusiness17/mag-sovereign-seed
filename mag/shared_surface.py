"""Validate and expose the cross-client Mag shared surface.

This module is deliberately read-only in its inspect/status/validate verbs: it
does not move files or grant effects; it gives host, container, WSL, editor,
and CLI workers one deterministic way to find the durable inbox and detect
drift in its discovery pointers. The one exception is the rebuild verb
(WO-10, 2026-09-29), the standing INDEX fold repair: it heals the surface
strictly through the fold's own writer verbs (see mag/surface_rebuild.py,
its implementation module per the file-too-long law).

CLI::
    python -m mag.shared_surface path
    python -m mag.shared_surface status
    python -m mag.shared_surface validate
    python -m mag.shared_surface rebuild [--dry]

Living-file law (B2-156, 2026-09-26; spec watch/inbox/LIVING_HASH_LAW_20260926.md):
a SEALED living item (living:true + size:N) seals only its first N bytes.
validate hashes that sealed prefix: append-only growth past the seal is counted
(living_files.ok) and never an error, while mutation or truncation of the sealed
prefix is a hard error. An OPEN living item (living:true + seal:"open") is an
edit-shaped board with no byte seal: counted in living_files.open, never an
error. A living item with neither is a WARNING and counts in
living_files.unverified (steady state is empty; it is migration residue).

Events-log hygiene (B2-42, 2026-09-26): validate also scans
watch/inbox/index_events.jsonl, the append-only log that INDEX.json is folded
from (scripts/index_fold_host.mjs). The fold's reader is tolerant: it warns and
skips lines that fail JSON.parse, so a writer that starts appending garbage
would otherwise never fail a gate. Spec here:

- A line is malformed when it is non-blank (after stripping trailing CRLF) and
  fails strict json.loads with NaN/Infinity rejected, matching the fold's
  JSON.parse semantics.
- Lines whose content sha256 is registered in
  configs/events_malformed_baseline.json are grandfathered debt: the no-erase
  law keeps them in the log verbatim, so they stay warnings-free and folded
  over. Registration is keyed on content bytes, not line numbers, because the
  log is append-only and legacy lines keep their positions anyway.
- Any malformed line NOT in the registry is an ERROR: a NEW malformed line
  fails validate (exit 1). Fix the writer and register debt by name if a new
  one must land.
- A missing or unreadable baseline is an ERROR (the debt registry must exist);
  a missing events log is a WARNING (container surfaces may not mount the
  repo); a registered line that no longer exists in the log is a WARNING so
  fixed or pruned debt can be reclaimed from the registry.

Events key schema (B2-342, 2026-09-26): the B2-329 dump purity law made the
writer-key vocabulary load-bearing (a strict downstream consumer of the
`events` dump rejects any key outside it), but no spec owned the vocabulary.
The spec is now configs/events_key_schema.json: every key any writer ever
appended, each with first-seen line, seq (decimal string per the B2-40
scheme), ts and owning writer, censused at a recorded log sha256. The
gate implementation lives in mag/events_key_schema.py (re-exported here,
where inspect_surface wires it). The
registry is a CLOSED VOCABULARY, not a required-fields spec: any registered
key may be omitted on any line. The gate:

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

Env-redirect tripwire (B2-358, 2026-09-26): validate also warns when
MAG_SEAT_CRASH_LOG or MAG_GAPS_LOG is set outside a test run. These are the
test isolation seams (mag.agent_cli._log_seat_crash,
mag.temperature_stack._gaps_log) whose writers report ok either way, so a
shell export leaked past its test run silently redirects the production crash
or gap log. The warning names the variable and the redirect target and never
fails validate (a warning, not an error); the operator response is in
mag/env_redirect.py and receipt
watch/inbox/burn_wave_20260926/B2_358_env_tripwire_20260926.md.

LINKS event split (B2-168): LINKS.jsonl link-rows-only past its B2-28
marker; gate spec + debt registry live in mag/links_split_gate.py.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from mag.env_redirect import env_redirect_warnings
# B2-342 events key schema gate: implementation lives in its own module (the
# ratchet's file-too-long law); names are re-exported here because
# mag.shared_surface.validate is the wiring surface and tests address them
# through this module.
from mag.events_key_schema import (  # noqa: F401  (re-export)
    EVENTS_KEY_SCHEMA,
    load_event_key_registry,
    reject_json_constant as _reject_constant,
    scan_event_keys,
)
from mag.links_split_gate import (  # noqa: F401  (B2-168 re-export; spec in mag/links_split_gate.py)
    LINKS_KIND_BASELINE,
    LINKS_LEDGER,
    links_split_check,
    scan_links_kind_rows,
)
from mag.links_sha_ratchet import (  # noqa: F401  (B2-173 re-export; spec in mag/links_sha_ratchet.py)
    LINKS_SHA_BASELINE,
    links_sha_ratchet_check,
    scan_same_sha_unflagged,
)
# WO-10 (2026-09-29) rebuild verb: implementation lives in mag/surface_rebuild.py
# (the file-too-long law module-split pattern); re-exported here because
# mag.shared_surface is the wiring surface and the CLI below dispatches it.
from mag.surface_rebuild import rebuild_surface  # noqa: F401


ROOT = Path(__file__).resolve().parents[1]
WATCH = ROOT / "watch"
INBOX = WATCH / "inbox"
INDEX = INBOX / "INDEX.json"
CONTRACT = INBOX / "SHARED_SURFACE_CONTRACT.json"
WARM_PACK = WATCH / "WARM_PACK.json"
EVENTS_LOG = INBOX / "index_events.jsonl"
MALFORMED_BASELINE = ROOT / "configs" / "events_malformed_baseline.json"
CONTROL_FILES = {"INDEX.json", "INDEX.md", "SHARED_SURFACE_CONTRACT.json"}

# B2-297 (2026-09-26) living-downgrade watchlist: the three paths the
# LIVING_HASH_LAW_20260926.md names as living-by-design. A plain `add`
# re-register legally drops the living flag (last-register-wins, law
# section 5), so one stale whole-file refresh silently reverts any of
# these to a whole-file seal that hard-fails on the next append. validate
# warns (never errors) when one of them folds to an item without
# item.living, so the downgrade is named at the next validate instead of
# surfacing as an append failure later.
KNOWN_LIVING_PATHS = (
    "LINKS.jsonl",
    "burn_wave_20260926/QUEUE.md",
    "phone_relay_log.jsonl",
)

# B2-399 (2026-09-26): scan_events_log moved to mag/events_scan.py per the
# B2-248 module-split precedent (file-too-long law); the file sat at exactly
# the 400-line cap after the B2-342/B2-358 landings. Re-exported here because
# mag.shared_surface.validate is the wiring surface and tests address the
# scanner through this module (same re-export pattern as mag/events_key_schema.py).
from mag.events_scan import scan_events_log  # noqa: E402  (B2-399 re-export)


def _load(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def inspect_surface() -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    index: dict[str, Any] = {}
    contract: dict[str, Any] = {}
    warm: dict[str, Any] = {}
    # B2-156 living-file law counters (see the items loop below).
    living_ok = 0
    living_open = 0
    living_unverified = 0

    if not INBOX.is_dir():
        errors.append(f"missing inbox: {INBOX}")
    if not INDEX.is_file():
        errors.append(f"missing index: {INDEX}")
    else:
        try:
            index = _load(INDEX)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"invalid INDEX.json: {exc}")
    if not CONTRACT.is_file():
        errors.append(f"missing contract: {CONTRACT}")
    else:
        try:
            contract = _load(CONTRACT)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"invalid SHARED_SURFACE_CONTRACT.json: {exc}")
    if WARM_PACK.is_file():
        try:
            warm = _load(WARM_PACK)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"invalid WARM_PACK.json: {exc}")
    else:
        warnings.append(f"warm pack not found: {WARM_PACK}")

    # Events-log hygiene (B2-42 2026-09-26): the fold's tolerant reader skips
    # malformed lines forever, so validate is the gate that fails on NEW ones.
    # Legacy debt is grandfathered by content sha256 (no-erase law: the lines
    # stay in the log; see configs/events_malformed_baseline.json).
    malformed = scan_events_log(EVENTS_LOG)
    if not EVENTS_LOG.is_file():
        warnings.append(f"events log not found: {EVENTS_LOG}")
    grandfathered: dict[str, dict[str, Any]] = {}
    if MALFORMED_BASELINE.is_file():
        try:
            baseline = _load(MALFORMED_BASELINE)
            for entry in baseline.get("grandfathered", []):
                if isinstance(entry, dict) and entry.get("sha256"):
                    grandfathered[str(entry["sha256"]).lower()] = entry
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"invalid malformed-line baseline: {exc}")
    else:
        errors.append(f"missing malformed-line baseline: {MALFORMED_BASELINE}")
    seen_malformed: set[str] = set()
    for rec in malformed:
        seen_malformed.add(rec["sha256"])
        if rec["sha256"] in grandfathered:
            continue
        errors.append(
            f"NEW malformed line in index_events.jsonl (line {rec['line']}, "
            f"sha256 {rec['sha256'][:12]}): register it in "
            f"configs/events_malformed_baseline.json or fix the writer; "
            f"excerpt: {rec['excerpt'][:80]}"
        )
    for gsha, gentry in grandfathered.items():
        if gsha not in seen_malformed:
            warnings.append(
                f"grandfathered malformed line no longer in the log "
                f"(fixed or pruned? reclaim the registry entry): sha256 "
                f"{gsha[:12]} (was line {gentry.get('line')})"
            )

    # Events key schema (B2-342 2026-09-26): the writer-key vocabulary is
    # owned by configs/events_key_schema.json (the B2-329 dump purity law
    # made it load-bearing). A key outside the closed vocabulary is an ERROR
    # naming the key and its first-seen evidence; the fold warning channel
    # names the same keys. Missing registry is an ERROR; a missing log is
    # already a WARNING above (nothing to scan then).
    known_keys: set[str] | None = None
    if EVENTS_KEY_SCHEMA.is_file():
        try:
            known_keys = load_event_key_registry(EVENTS_KEY_SCHEMA)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"invalid events key schema registry: {exc}")
    else:
        errors.append(f"missing events key schema registry: {EVENTS_KEY_SCHEMA}")
    key_scan: dict[str, Any] = {"lines": 0, "unknown": []}
    if known_keys is not None and EVENTS_LOG.is_file():
        try:
            key_scan = scan_event_keys(EVENTS_LOG, known_keys)
        except OSError as exc:
            errors.append(f"unreadable events log for key scan: {exc}")
    for rec in key_scan["unknown"]:
        errors.append(
            f"NEW event key in index_events.jsonl: {rec['key']!r} x{rec['count']} "
            f"(first line {rec['first_line']}, seq {rec['first_seq']!r}, "
            f"writer {rec['first_writer']!r}): register it in "
            f"configs/events_key_schema.json with first-seen evidence or fix "
            f"the writer"
        )

    # B2-168 LINKS event split; spec: mag/links_split_gate.py docstring.
    links_split_check(LINKS_LEDGER, LINKS_KIND_BASELINE, errors, warnings)

    # B2-173 same-sha duplicate ratchet; spec: mag/links_sha_ratchet.py docstring.
    links_sha_ratchet_check(LINKS_LEDGER, LINKS_SHA_BASELINE, errors, warnings)

    indexed = {Path(str(item.get("path", ""))).name for item in index.get("items", [])
               if isinstance(item, dict)}
    files = sorted(path.name for path in INBOX.iterdir() if path.is_file()) if INBOX.is_dir() else []
    unindexed = [name for name in files if name not in indexed and name not in CONTROL_FILES]
    if unindexed:
        warnings.append("unindexed inbox files: " + ", ".join(unindexed))

    expected_root = "/board/inbox"
    if index.get("root") != expected_root:
        errors.append(f"INDEX root is {index.get('root')!r}, expected {expected_root!r}")
    if contract.get("canonical", {}).get("container") != expected_root:
        errors.append("contract container path does not match /board/inbox")
    warm_pointer = warm.get("discovery", {}).get("shared_inbox")
    if warm_pointer and warm_pointer.get("path") != "/board/inbox/INDEX.json":
        errors.append("WARM_PACK shared inbox pointer is incorrect")
    elif not warm_pointer:
        warnings.append("WARM_PACK has no shared inbox discovery pointer")

    indexed_items: list[dict[str, Any]] = []
    for item in index.get("items", []):
        if not isinstance(item, dict):
            errors.append("INDEX contains a non-object item")
            continue
        raw = str(item.get("path", "")).replace("\\", "/")
        for pref in ("/board/inbox/", "/app/inbox/", "inbox/"):
            if raw.startswith(pref):
                raw = raw[len(pref):]
                break
        rel = raw  # resolve real subpaths (matthews_zenodo_17811909/x, journal_mark_202609/x)
        target = INBOX / rel
        record = {"path": item.get("path"), "exists": target.is_file()}
        if not target.is_file():
            errors.append(f"indexed item missing: {item.get('path')}")
        recorded_hash = str(item.get("sha256") or "").upper()
        if recorded_hash and target.is_file():
            actual_hash = _sha256(target)
            record["sha256_match"] = actual_hash == recorded_hash
            if item.get("living"):
                # Living-file law (B2-156 2026-09-26, spec:
                # watch/inbox/LIVING_HASH_LAW_20260926.md). Sealed living:
                # (sha256, size) over the item's first `size` bytes; append-only
                # growth past the seal is the designed state of a ledger, so a
                # prefix match is counted, never an error, while a mutated or
                # truncated sealed prefix is a hard error. Open living
                # (seal:"open"): edit-shaped board, no byte seal, counted only.
                # Neither shape fails on growth.
                if item.get("seal") == "open":
                    living_open += 1
                    record["living_open"] = True
                else:
                    size = item.get("size")
                    if isinstance(size, int) and size > 0:
                        with target.open("rb") as handle:
                            prefix = handle.read(size)
                        prefix_ok = (
                            len(prefix) == size
                            and hashlib.sha256(prefix).hexdigest().upper() == recorded_hash
                        )
                        record["living_prefix_match"] = prefix_ok
                        if prefix_ok:
                            living_ok += 1
                        else:
                            errors.append(f"living prefix mismatch: {item.get('path')}")
                    else:
                        record["living_unverified"] = True
                        living_unverified += 1
                        warnings.append(
                            f"living item without size seal (re-register with "
                            f"add --living to seal a prefix): {item.get('path')}"
                        )
            elif actual_hash != recorded_hash:
                errors.append(f"hash mismatch: {item.get('path')}")
        indexed_items.append(record)

    # Env-redirect tripwire (B2-358 2026-09-26): MAG_SEAT_CRASH_LOG and
    # MAG_GAPS_LOG are test isolation seams (mag.agent_cli._log_seat_crash,
    # mag.temperature_stack._gaps_log) that silently move the production
    # crash/gap logs when their export leaks into a plain shell. validate
    # warns (never errors) while either is set, naming the redirect target.
    warnings.extend(env_redirect_warnings())

    # Living-downgrade detector (B2-297): a known living path whose current
    # INDEX item carries no living flag means a plain re-register dropped
    # the flag (last-register-wins, LIVING_HASH_LAW section 5); the file
    # will hard-fail its next append under a whole-file seal.
    living_downgraded = 0
    living_by_rel = {}
    for item in index.get("items", []):
        if isinstance(item, dict):
            raw = str(item.get("path", "")).replace("\\", "/")
            for pref in ("/board/inbox/", "/app/inbox/", "inbox/"):
                if raw.startswith(pref):
                    raw = raw[len(pref):]
                    break
            living_by_rel[raw.lstrip("/")] = bool(item.get("living"))
    for rel in KNOWN_LIVING_PATHS:
        if rel in living_by_rel and not living_by_rel[rel]:
            living_downgraded += 1
            warnings.append(
                f"living downgrade: {rel} is a known living file but its "
                f"registration carries no living flag (a plain re-register "
                f"dropped it, LIVING_HASH_LAW section 5 last-register-wins); "
                f"re-register with add --living or --living-open before the "
                f"next append hard-fails"
            )

    return {
        "schema": "shared_surface.status.v1",
        "ok": not errors,
        "root": str(ROOT),
        "paths": {
            "host": str(INBOX),
            "container": "/board/inbox",
            "wsl": "/mnt/c/Users/ESTATE_USER/Documents/projects/local_sovereign_agent/watch/inbox",
            "index": "/board/inbox/INDEX.json",
            "contract": "/board/inbox/SHARED_SURFACE_CONTRACT.json"
        },
        "files": files,
        "indexed_items": indexed_items,
        "unindexed_items": unindexed,
        "events_log_malformed": {
            "total": len(malformed),
            "grandfathered": len(malformed) - sum(
                1 for r in malformed if r["sha256"] not in grandfathered),
            "new": sum(1 for r in malformed if r["sha256"] not in grandfathered),
        },
        "events_log_keys": {
            "lines_scanned": key_scan["lines"],
            "unknown_keys": len(key_scan["unknown"]),
        },
        "living_files": {
            "ok": living_ok,
            "open": living_open,
            "unverified": living_unverified,
            "downgraded": living_downgraded,
        },
        "errors": errors,
        "warnings": warnings
    }


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m mag.shared_surface")
    parser.add_argument(
        "command",
        choices=("path", "status", "validate", "rebuild"),
        nargs="?",
        default="status",
    )
    parser.add_argument("--dry", action="store_true", help="rebuild: census only, no heals")
    args = parser.parse_args()
    if args.command == "path":
        print(json.dumps({
            "schema": "shared_surface.path.v1",
            "host": str(INBOX),
            "container": "/board/inbox",
            "wsl": "/mnt/c/Users/ESTATE_USER/Documents/projects/local_sovereign_agent/watch/inbox",
            "read_first": "/board/inbox/INDEX.json"
        }, indent=2))
        return 0
    if args.command == "rebuild":
        # WO-10 standing repair: fold rebuild + register heals via the fold's
        # own verbs; exit 1 only when the post-run census still has deltas.
        result = rebuild_surface(dry_run=bool(args.dry))
        print(json.dumps(result, indent=2))
        return 0 if result.get("ok") else 1
    result = inspect_surface()
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] or args.command == "status" else 1


if __name__ == "__main__":
    raise SystemExit(main())
