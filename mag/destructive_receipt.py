"""destructive_receipt — LAW-065 third leg: receipted destructive actions (2026-09-07).

The invariants-shrink forensics (watch/inbox/INVARIANTS_SHRINK_FORENSICS_20260906.md)
proved the loss class: an out-of-band wipe in a quiet window — no receipt, no log, no
named hand, "UNPROVEN (the actor)". The auto-heal + seal-check in mag/percolator.py make
the registry forget nothing; THIS instrument makes destructive acts RECEIPTED. Third leg
of LAW-065: before a file is overwritten/replaced/deleted, a receipt row lands in the
append-only ledger naming who, why, and what the target's bytes were.

Ledger: research/destructive_receipts.jsonl (append-only jsonl), one row per act:
  {ts, action, target, actor, reason, sha256_before}
  target       ROOT-relative posix path (absolute when outside ROOT)
  sha256_before hash of the target's bytes BEFORE the act (null when absent)

check(target): for writers about to replace a file. No receipt on record for the target
-> appends a warn line to state/destructive_receipts.log and returns False; receipt on
record -> True. WARN-ONLY in this build: making receipts REQUIRED before replace is
operator law to grant, not this instrument's call (gatekeep build order 2026-09-07:
land the instrument + one demo call site).

Demo call site: mag/percolator.py _save_registry receipts each atomic registry save.

CLI ($0, stdlib only, no network, no daemons):
  python -m mag.destructive_receipt record --target <path> --actor <seat> --reason "..."
  python -m mag.destructive_receipt check  --target <path>
  python -m mag.destructive_receipt list [--tail N]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

LEDGER = ROOT / "research" / "destructive_receipts.jsonl"
WARN_LOG = ROOT / "state" / "destructive_receipts.log"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def norm_target(target: str | Path) -> str:
    """ROOT-relative posix path when inside the repo; resolved absolute otherwise."""
    p = Path(target)
    try:
        return p.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return p.resolve().as_posix()


def sha256_before(target: str | Path) -> str | None:
    """Hash of the target's bytes BEFORE the destructive act; None when absent."""
    p = Path(target)
    if not p.is_file():
        return None
    h = hashlib.sha256()
    with p.open("rb") as f:
        for blk in iter(lambda: f.read(65536), b""):
            h.update(blk)
    return h.hexdigest()


def _append(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def record(target: str | Path, actor: str, reason: str, action: str = "replace") -> dict:
    """Append a receipt row for an intended destructive act. Returns the row."""
    row = {"ts": _now(), "action": action, "target": norm_target(target),
           "actor": actor, "reason": reason, "sha256_before": sha256_before(target)}
    _append(LEDGER, row)
    return row


def receipts_for(target: str | Path) -> list:
    """All receipt rows on record for a target (exact normalized-path match)."""
    t = norm_target(target)
    out: list = []
    if not LEDGER.is_file():
        return out
    for ln in LEDGER.read_text(encoding="utf-8", errors="replace").splitlines():
        if not ln.strip():
            continue
        try:
            r = json.loads(ln)
        except json.JSONDecodeError:
            continue
        if isinstance(r, dict) and r.get("target") == t:
            out.append(r)
    return out


def check(target: str | Path, actor: str = "") -> bool:
    """WARN-IF-NO-RECEIPT: call BEFORE any file replace. True when a receipt exists;
    otherwise a warn line lands in state/destructive_receipts.log and False returns.
    Never blocks in this build — enforcement is a later, operator-gated law."""
    if receipts_for(target):
        return True
    _append(WARN_LOG, {"ts": _now(), "warn": "NO-RECEIPT",
                       "target": norm_target(target), "actor": actor})
    return False


def list_receipts(tail: int = 50) -> list:
    if not LEDGER.is_file():
        return []
    rows = []
    for ln in LEDGER.read_text(encoding="utf-8", errors="replace").splitlines():
        if not ln.strip():
            continue
        try:
            rows.append(json.loads(ln))
        except json.JSONDecodeError:
            continue
    return rows[-tail:]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="mag.destructive_receipt", description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    rec = sub.add_parser("record", help="append a receipt row for a destructive act")
    rec.add_argument("--target", required=True)
    rec.add_argument("--actor", required=True, help="seat/hand performing the act")
    rec.add_argument("--reason", required=True)
    rec.add_argument("--action", default="replace",
                     choices=["replace", "delete", "truncate", "move"])
    chk = sub.add_parser("check", help="warn-if-no-receipt for a target")
    chk.add_argument("--target", required=True)
    chk.add_argument("--actor", default="")
    lst = sub.add_parser("list", help="show recent receipt rows")
    lst.add_argument("--tail", type=int, default=50)
    args = ap.parse_args(argv)

    if args.cmd == "record":
        row = record(args.target, args.actor, args.reason, action=args.action)
        print(json.dumps(row, ensure_ascii=False))
        print(f"receipt -> {LEDGER.relative_to(ROOT).as_posix()}")
        return 0
    if args.cmd == "check":
        ok = check(args.target, actor=args.actor)
        print(("RECEIPTED" if ok else "NO-RECEIPT (warn logged to "
              f"{WARN_LOG.relative_to(ROOT).as_posix()})") + f" :: {norm_target(args.target)}")
        return 0 if ok else 1
    rows = list_receipts(args.tail)
    for r in rows:
        print(json.dumps(r, ensure_ascii=False))
    print(f"{len(rows)} row(s) shown; ledger {LEDGER.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    sys.exit(main())
