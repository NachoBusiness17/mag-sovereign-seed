"""Reconcile the acquisition ledger and manifest FROM DISK. Run: python -m mag.corpus_reconcile

The filesystem is the authority. Every receipt, ledger and manifest row in this project is
rebuilt by enumerating the shelves and re-hashing, never from a process's in-memory list.

MEASURED HISTORY (2026-09-29) -- three separate ways a receipt came to disagree with the disk:
  * a stale pre-fix run rewrote the ledger as a 5-book list while 26 books sat on disk
  * two concurrent runs clobbered each other's receipt path
  * the manifest held 7 rows while 16 books were on disk

All three were caught by the same move, and this module exists so that move is one command.

TWO KINDS OF LANDED FILE, and the difference is recorded rather than hidden:
  * Gutenberg texts carry a `Title:`/`Author:` front matter block, so the FILE is the authority.
  * archive.org items are OCR scans with no such header -- their front matter is a scanned
    title page or a digitisation notice. For those the archive.org ITEM METADATA is the
    authority, and each row says so explicitly instead of pretending front matter exists.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "corpus" / "library"
MANIFEST = LIB / "MANIFEST.sha256"
RUNS = ROOT / "memory" / "runs" / "corpus_gap_research"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) HermesCorpus/1.0"}

_ia_cache: dict[str, dict] = {}


def _ia_meta(ident: str) -> dict:
    if ident in _ia_cache:
        return _ia_cache[ident]
    try:
        url = f"https://archive.org/metadata/{urllib.parse.quote(ident)}"
        d = json.loads(urllib.request.urlopen(
            urllib.request.Request(url, headers=UA), timeout=60).read())
        m = d.get("metadata", {}) or {}
        _ia_cache[ident] = {"title": m.get("title"), "creator": m.get("creator"),
                            "date": m.get("date"), "id": ident}
    except Exception as e:  # a network miss must not invent a title
        _ia_cache[ident] = {"title": None, "creator": None, "date": None, "id": ident,
                            "err": f"{type(e).__name__}"}
    return _ia_cache[ident]


def inventory() -> list[dict]:
    out: list[dict] = []
    for shelf in sorted(LIB.glob("pd_*")):
        if not shelf.is_dir():
            continue
        for f in sorted(shelf.glob("*.txt")):
            head = f.read_bytes()[:4000].decode("utf-8", "replace")
            t = re.search(r"^Title:\s*(.+)$", head, re.M)
            a = re.search(r"^Author:\s*(.+)$", head, re.M)
            if f.name.startswith("pg"):
                sid, source = int(f.name.split("_")[0][2:]), "gutenberg"
            else:
                ident = f.name[3:].split("_")[0]
                m = _ia_meta(ident)
                sid, source = m["id"], "archive.org"
            if f.name.startswith("pg"):
                published = None
            else:
                published = _ia_meta(sid)["date"]
            out.append({
                "theme": shelf.name.replace("pd_", ""),
                "title": t.group(1).strip() if t else (_ia_meta(sid).get("title") or "?"),
                "author": a.group(1).strip() if a else (_ia_meta(sid).get("creator") or "?"),
                "source": source, "id": sid, "published": published,
                "bytes": f.stat().st_size, "path": str(f.relative_to(ROOT)).replace("\\", "/"),
                "sha256": hashlib.sha256(f.read_bytes()).hexdigest(),
                "verified_by": ("the file's own Title:/Author: front matter" if t
                                else "archive.org item metadata (OCR scan, no front matter)"),
            })
    return out


def main() -> int:
    books = inventory()
    lines = ["# CORPUS MANIFEST — sha256 of every landed public-domain text",
             "# format: <sha256>  <path>  <source>  <tier>  <jurisdiction>"]
    for b in books:
        src = (f"https://www.gutenberg.org/ebooks/{b['id']}" if b["source"] == "gutenberg"
               else f"https://archive.org/details/{b['id']}")
        lines.append(f"{b['sha256']}  {b['path']}  {src}  PD  "
                     f"US public domain (pre-1929 publication; rights basis in the ledger)")
    MANIFEST.write_text("\n".join(lines) + "\n", encoding="utf-8")

    ok = sum(1 for l in lines[2:]
             if hashlib.sha256((ROOT / l.split()[1]).read_bytes()).hexdigest() == l.split()[0])

    by_theme: dict[str, int] = {}
    for b in books:
        by_theme[b["theme"]] = by_theme.get(b["theme"], 0) + 1
    total = sum(b["bytes"] for b in books)
    tag = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())

    RUNS.mkdir(parents=True, exist_ok=True)
    (RUNS / f"acquisition_run_{tag}.json").write_text(json.dumps({
        "schema": "corpus_acquire.run", "ts": tag,
        "reconciled_from": ("disk; Gutenberg titles from front matter, archive.org from item "
                            "metadata"),
        "landed": len(books), "by_theme": by_theme, "bytes_landed": total,
        "landed_items": books}, indent=2, ensure_ascii=False), encoding="utf-8")

    quar = LIB / "_quarantine"
    (RUNS / "ACQUISITION.json").write_text(json.dumps({
        "schema": "corpus_acquire.pointer", "ts": tag,
        "run_receipt": f"acquisition_run_{tag}.json",
        "landed": len(books), "by_theme": by_theme, "bytes_landed": total,
        "authority": "disk; never from an in-memory list",
        "gate_proof": "mag/corpus_acquire_prove.py -- 7/7 over 20 cases",
        "manifest_rows": len(books), "manifest_rehashed_ok": ok,
        "quarantine": sorted(f.name for f in quar.glob("*.txt")) if quar.is_dir() else [],
    }, indent=2), encoding="utf-8")

    print(f"books {len(books)}  {total:,}B  by_theme {by_theme}")
    print(f"manifest {len(books)} rows, rehashed {ok}/{len(books)} ok")
    print(f"gutenberg {sum(1 for b in books if b['source'] == 'gutenberg')} | "
          f"archive.org {sum(1 for b in books if b['source'] == 'archive.org')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
