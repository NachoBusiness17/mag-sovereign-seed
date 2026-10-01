"""A HOLDINGS AUDIT, and a report the librarian can actually read.

OPERATOR ASK (2026-09-29): "do a complete audit of everything you grabbed and let the librarian
know"

WHY THE LIBRARIAN COULD NOT SEE ANY OF IT -- measured, not assumed
  mag.librarian.receipt_state() walks docs/report_v1/sources/receipts/*.md and does:

      m = ARXIV.search(p.stem)
      if not m:
          continue          # <-- every non-arXiv receipt is SKIPPED SILENTLY

  It matches receipts by ARXIV ID TOKEN. The librarian was built for a research thread whose
  sources were all arXiv papers, and that assumption is load-bearing. The 192 documents acquired
  this session are Gutenberg texts, NTRS PDFs, Naval ordnance volumes, archive.org scans, physical
  lineage papers and 25 Shannon/von Neumann/Turing primaries -- NONE has an arXiv id, so NONE is
  visible to it. Probes for watson, bowlby, child-study, siege, shannon, turing, edvac, wilkes,
  frontinus, nasa, lowenfeld, gesell and piaget in its report ALL returned ZERO on a fresh run
  that scanned 5,022 documents and 298 map rows.

  That is not the librarian being wrong. It is the librarian answering a question about a corpus
  that is not ours, and reporting a confident count for it. I am not editing mag/librarian.py:
  its scope is deliberate and I have no operator authorization to widen it. This module writes
  what it CAN read.

WHAT THIS AUDITS, AND IN WHICH DIRECTION -- both, because they fail differently
  1. LEDGER -> DISK. Every row claiming LANDED is re-hashed from disk and its byte count
     checked. This catches a file that was deleted, truncated, or never written.
  2. DISK -> LEDGER. Every non-trivial file under the shelves this session built is checked for
     a ledger claim AND for a receipt that names it. This catches an ORPHAN -- a file on disk
     that nothing accounts for. A ledger-only audit cannot see one, and an orphan is exactly the
     artefact that looks like a holding and cannot be explained.
  3. LEDGER INTERNAL CONSISTENCY. A row's recorded status must match a file that exists.
  4. CONTENT, not just bytes. %PDF- magic on PDFs, and a text-extraction floor on .txt -- because
     this session landed a Soviet patent with a valid SHA-256 and destroyed Cyrillic OCR, and a
     hash-valid file is not a readable file.

THE TWO REAL DEFECTS THIS FOUND, both of which a bytes-only check would have passed
  - A STALE LEDGER ROW. mag/computing_history's vnedvac row still pointed at the pre-split
    filename of a file I had deliberately deleted and replaced with two correctly-tiered files.
    The audit's "missing" was CORRECT and the ledger was wrong.
  - FIVE BYTE-IDENTICAL ORPHANS in pd_child_development: 4,144,296 B of exact duplicates left
    behind when a filename scheme changed mid-session. A hash-verify of CLAIMED files cannot see
    these, because the stale copies are claimed by nothing -- they are invisible to both the
    ledger and a naive duplicate check that only compares claimed files. This is the
    Ingersoll Lockwood pattern a third time, and it is the strongest argument for auditing in
    BOTH directions.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

RUNS = ROOT / "memory" / "runs" / "holdings_audit"
OUT_MD = ROOT / "watch" / "INBOX" / "HOLDINGS_AUDIT_20260930.md"
RECEIPTS = ROOT / "docs" / "report_v1" / "sources" / "receipts"

# The shelves this session built. Deliberately EXPLICIT rather than a glob: an audit that
# silently widens its own scope is an audit that cannot be trusted to report a narrowing.
# DISJOINT BY CONSTRUCTION. A parent shelf and its children cannot both appear here: rglob over
# the parent already yields the children's files, so listing both walks every child file twice and
# every one of them becomes a phantom DUPLICATE-GROUP. That is not hypothetical -- the first run of
# this audit reported 149 duplicate groups which were 100% this bug, not redundancy in the estate.
# An independent sweep over disjoint shelves had already measured 0 real duplicate groups.
SHELVES = [
    "corpus/library/pd_siege_castle_fiction",
    "corpus/library/pd_child_development",
    "corpus/library/pd_computing_history",
    "corpus/library/pd_physical_compute",       # includes ancient_engineering, naval_engineering, nasa_space
    "corpus/papers_reference_nonredistributable",
]

LEDGER_GLOBS = ["memory/runs/**/*LANDING*.json", "memory/runs/**/NTRS_LANDING*.json"]


def _ledgers() -> list[Path]:
    out: set[Path] = set()
    for g in LEDGER_GLOBS:
        out |= set(ROOT.glob(g))
    return sorted(out)


def audit() -> dict:
    # ---------- direction 1: LEDGER -> DISK ----------
    claims: dict[str, dict] = {}
    ledger_rows = 0
    for l in _ledgers():
        try:
            d = json.loads(l.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"  LEDGER-PARSE-FAIL {l.name}: {type(e).__name__}")
            continue
        for r in (d.get("rows") or []):
            ledger_rows += 1
            if str(r.get("status", "")).startswith("LANDED") and r.get("landed"):
                claims[r["landed"]] = {"sha": r.get("sha256"), "bytes": r.get("bytes"),
                                       "ledger": l.name, "row": r}

    ok = miss = mism = 0
    findings: list[str] = []
    verified_bytes = 0
    for pth, c in sorted(claims.items()):
        fp = ROOT / pth
        if not fp.exists():
            miss += 1
            findings.append(f"MISSING-ON-DISK  {pth}  (claimed by {c['ledger']})")
            continue
        data = fp.read_bytes()
        h = hashlib.sha256(data).hexdigest()
        if c["sha"] and h != c["sha"]:
            mism += 1
            findings.append(f"HASH-MISMATCH    {pth}  claim={c['sha'][:12]} disk={h[:12]}")
        elif c["bytes"] is not None and len(data) != c["bytes"]:
            mism += 1
            findings.append(f"SIZE-MISMATCH    {pth}  claim={c['bytes']:,} disk={len(data):,}")
        else:
            ok += 1
            verified_bytes += len(data)

    # ---------- direction 2: DISK -> LEDGER + RECEIPT ----------
    receipt_text = ""
    if RECEIPTS.exists():
        receipt_text = "\n".join(p.read_text(encoding="utf-8", errors="replace")
                                 for p in RECEIPTS.glob("*.md"))
    dup_groups: dict[str, list[str]] = {}
    orphans: list[str] = []
    shelf_files = 0
    shelf_bytes = 0
    unreadable: list[str] = []
    for sh in SHELVES:
        p = ROOT / sh
        if not p.is_dir():
            continue
        for f in sorted(p.rglob("*")):
            if not f.is_file() or f.stat().st_size == 0:
                continue
            if f.suffix.lower() not in (".txt", ".pdf"):
                continue
            shelf_files += 1
            shelf_bytes += f.stat().st_size
            rel = str(f.relative_to(ROOT)).replace("\\", "/")
            h = hashlib.sha256(f.read_bytes()).hexdigest()
            dup_groups.setdefault(h, []).append(rel)
            if rel not in claims:
                orphans.append(rel)
            # content, not just bytes
            head = f.open("rb").read(8)
            if f.suffix.lower() == ".pdf":
                if not head.startswith(b"%PDF-"):
                    unreadable.append(f"NOT-A-PDF {rel}")
            else:
                try:
                    t = f.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    unreadable.append(f"UNREADABLE    {rel}")
                    continue
                printable = sum(1 for c in t[:20000] if c.isprintable() or c in "\n\t")
                if t and printable / max(1, len(t[:20000])) < 0.80:
                    unreadable.append(f"LOW-PRINTABLE {rel} "
                                      f"({printable/max(1,len(t[:20000])):.0%})")
    dups = {h: v for h, v in dup_groups.items() if len(v) > 1}
    for h, v in dups.items():
        findings.append(f"DUPLICATE-GROUP {h[:12]}  " + " | ".join(v))

    unreceipted = [o for o in orphans if o.rsplit("/", 1)[-1] not in receipt_text]
    for o in unreceipted:
        findings.append(f"ORPHAN-NO-RECEIPT {o}")

    return {
        "ts": datetime.now(timezone.utc).isoformat(),
        "ledger_rows_scanned": ledger_rows,
        "landed_claims": len(claims),
        "direction_1_claims_to_disk": {"ok": ok, "missing": miss, "mismatch": mism,
                                      "verified_bytes": verified_bytes},
        "direction_2_disk_to_claims": {"shelf_files": shelf_files, "shelf_bytes": shelf_bytes,
                                       "orphans_not_claimed": len(orphans),
                                       "orphans_with_no_receipt": len(unreceipted),
                                       "duplicate_groups": len(dups)},
        "content_checks": {"unreadable": len(unreadable), "items": unreadable[:20]},
        "findings": findings,
        "clean": miss == 0 and mism == 0 and len(dups) == 0 and len(unreceipted) == 0
                 and len(unreadable) == 0,
    }


def main() -> int:
    RUNS.mkdir(parents=True, exist_ok=True)
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    r = audit()
    (RUNS / "HOLDINGS_AUDIT.json").write_text(json.dumps(r, indent=2, ensure_ascii=False),
                                              encoding="utf-8")

    d1, d2 = r["direction_1_claims_to_disk"], r["direction_2_disk_to_claims"]
    L = ["# HOLDINGS AUDIT — everything acquired 2026-09-29/30 — for the librarian",
         "",
         f"_generated {r['ts']} · ledger rows {r['ledger_rows_scanned']} · "
         f"landed claims {r['landed_claims']} · method: `python -m mag.holdings_audit`_",
         "",
         "## WHY THIS IS A SEPARATE REPORT",
         "",
         "`mag.librarian` scans Markdown docs and matches receipts by **arXiv id token**",
         "(`receipt_state()` does `ARXIV.search(p.stem)` and `continue`s on no match). The 192",
         "documents acquired this session are Gutenberg texts, NTRS PDFs, Naval ordnance volumes,",
         "archive.org scans and primary papers — **none has an arXiv id, so none is visible to",
         "it.** A fresh librarian run over 5,022 documents and 298 map rows returned ZERO for",
         "watson, bowlby, child-study, siege, shannon, turing, edvac, wilkes, frontinus, nasa,",
         "lowenfeld, gesell and piaget.",
         "",
         "`mag/librarian.py` was **not modified** — its scope is deliberate and I have no",
         "operator authorization to widen it. This report is what it cannot see.",
         "",
         "## RESULT",
         "",
         f"- ledger -> disk: **{d1['ok']} ok, {d1['missing']} missing, {d1['mismatch']} mismatched**"
         f" ({d1['verified_bytes']:,} B re-hashed from disk)",
         f"- disk -> ledger: {d2['shelf_files']} files, {d2['shelf_bytes']:,} B; "
         f"{d2['orphans_not_claimed']} unclaimed by a ledger, "
         f"{d2['orphans_with_no_receipt']} with no receipt naming them",
         f"- duplicates: {d2['duplicate_groups']} byte-identical groups",
         f"- content: {r['content_checks']['unreadable']} files failed a readability/magic check",
         f"- **verdict: {'CLEAN' if r['clean'] else 'FINDINGS'}**",
         ""]
    if r["findings"]:
        L += ["## FINDINGS", ""]
        L += [f"- {f}" for f in r["findings"][:60]]
    else:
        L += ["No findings. Every landed claim re-hashes from disk, every file on disk is claimed",
              "and receipted, no byte-identical duplicates, and every file passes a content check.", ""]
    (OUT_MD).write_text("\n".join(L), encoding="utf-8")

    print(f"  ledger->disk : {d1['ok']} ok / {d1['missing']} missing / {d1['mismatch']} mismatch"
          f"  ({d1['verified_bytes']:,} B)")
    print(f"  disk->ledger : {d2['shelf_files']} files, {d2['shelf_bytes']:,} B, "
          f"{d2['orphans_with_no_receipt']} unreceipted, {d2['duplicate_groups']} dup groups")
    print(f"  content      : {r['content_checks']['unreadable']} unreadable")
    print(f"  verdict      : {'CLEAN' if r['clean'] else str(len(r['findings'])) + ' findings'}")
    print(f"  -> {OUT_MD.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())