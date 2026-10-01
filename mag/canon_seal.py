"""canon_seal — Phase-0 sha256 seal for corpus/canon (X-harvest doctrine gate).

The doctrine (watch/X_HARVEST_DOCTRINE_20260905.md) and the 09-05 workers both
named the same gate: nothing gets harvested INTO the canon, and no cite-gate
batch runs over it, until the banked corpus is sealed — a sha256 MANIFEST that
makes "banked + sealed" a checkable claim instead of prose.

Manifest format is `sha256sum -c` compatible: "<hex>  <relpath>" per line.

LAW CITATION: files not processes; append-side manifest, never rewrites source
bytes. Backup-first is structural: verify() compares, never deletes.

CLI:
  python -m mag.canon_seal seal   [--root corpus/canon]   # mint/refresh MANIFEST.sha256
  python -m mag.canon_seal verify [--root corpus/canon]   # recompute + report
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CANON = ROOT / "corpus" / "canon"


def _hash_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _files(canon: Path) -> list[Path]:
    return sorted(p for p in canon.rglob("*") if p.is_file() and p.name != "MANIFEST.sha256")


def seal(canon: Path) -> str:
    canon.mkdir(parents=True, exist_ok=True)
    lines = []
    for p in _files(canon):
        lines.append(f"{_hash_file(p)}  {p.relative_to(canon).as_posix()}")
    out = canon / "MANIFEST.sha256"
    out.write_text(
        f"# Phase-0 seal {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')} "
        f"— {len(lines)} files, sha256sum -c compatible\n" + "\n".join(lines) + "\n",
        encoding="utf-8")
    return f"SEALED {len(lines)} files -> {out.name}"


def verify(canon: Path) -> tuple[bool, str]:
    manifest = canon / "MANIFEST.sha256"
    if not manifest.is_file():
        return False, "NO MANIFEST — canon is unsealed"
    recorded: dict[str, str] = {}
    for ln in manifest.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if ln and not ln.startswith("#"):
            h, _, rel = ln.partition("  ")
            recorded[rel] = h
    actual = {p.relative_to(canon).as_posix(): p for p in _files(canon)}
    missing = sorted(set(recorded) - set(actual))
    added = sorted(set(actual) - set(recorded))
    changed = [rel for rel, p in actual.items() if rel in recorded
               and _hash_file(p) != recorded[rel]]
    ok = not missing and not changed
    msg = (f"{len(recorded)} sealed, {len(added)} new(unsealed), "
           f"{len(missing)} missing, {len(changed)} changed")
    if missing:
        msg += " | missing: " + ", ".join(missing[:5])
    if changed:
        msg += " | CHANGED: " + ", ".join(changed[:5])
    if added:
        msg += " | new: " + ", ".join(added[:5])
    return ok, msg


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["seal", "verify"])
    ap.add_argument("--root", default=str(DEFAULT_CANON))
    args = ap.parse_args()
    canon = Path(args.root)
    if args.cmd == "seal":
        print(seal(canon))
    else:
        ok, msg = verify(canon)
        print(("PASS " if ok else "FAIL ") + msg)
        sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
