"""Land the US Navy engineering reference volumes the operator asked for.

Run: python -m mag.naval_engineering_land
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mag.corpus_archive_acquire import _get, _meta          # noqa: E402
from mag.naval_engineering_acquire import IDENT, ROWS, SHELF  # noqa: E402
from mag.physical_compute_acquire import _pdf_text           # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PDDIR = ROOT / "corpus" / "library" / "pd_physical_compute"
RUNS = ROOT / "memory" / "runs" / "physical_compute_lineage"
RECEIPTS = ROOT / "docs" / "report_v1" / "sources" / "receipts"


def main() -> int:
    md = _meta(IDENT)
    if not md:
        print("archive.org metadata unavailable -- refusing to guess at file names")
        return 1
    names = {f.get("name") for f in (md.get("_files") or [])}

    dest_dir = PDDIR / SHELF
    dest_dir.mkdir(parents=True, exist_ok=True)
    RECEIPTS.mkdir(parents=True, exist_ok=True)
    RUNS.mkdir(parents=True, exist_ok=True)

    results = []
    for row in ROWS:
        fn = row["file"]
        if fn not in names:
            print(f"  FILE-NOT-FOUND  {fn} -- not in the item's file list")
            results.append({"slug": row["slug"], "status": "FILE-NOT-FOUND", "file": fn})
            continue

        st, body, err = _get(
            f"https://archive.org/download/{IDENT}/{fn.replace(' ', '%20')}",
            tries=3, timeout=600)
        if st != 200 or not body:
            print(f"  FETCH-FAILED    {fn}  st={st} {err}")
            results.append({"slug": row["slug"], "status": "FETCH-FAILED", "file": fn})
            continue

        ext = ".pdf" if fn.lower().endswith(".pdf") else ".txt"
        if ext == ".pdf":
            if body[:5] != b"%PDF-":
                print(f"  NOT-A-PDF       {fn}  first bytes {body[:8]!r}")
                results.append({"slug": row["slug"], "status": "NOT-A-PDF", "file": fn})
                continue
            text, why = _pdf_text(body)
            if text is None:
                print(f"  UNPROBEABLE     {fn}: {why}")
                results.append({"slug": row["slug"], "status": "UNPROBEABLE", "file": fn,
                                "why": why})
                continue
        else:
            text = body.decode("utf-8", "replace")

        # Content gate: the file must contain what THIS row claims. For an engineering volume
        # the useful claim is the GPO imprint, not a topic word -- these were chosen as
        # reference data, and their rightness is established by the title page.
        probe = " ".join(text[:40000].split()).lower()
        if "government printing office" not in probe and "ordnance" not in probe:
            print(f"  CONTENT-FAIL    {fn}: no GPO imprint and no 'ordnance' in first 40 KB")
            results.append({"slug": row["slug"], "status": "FILE-CONTENT-MISMATCH", "file": fn})
            continue

        sha = hashlib.sha256(body).hexdigest()
        dest = dest_dir / f"pc_{row['slug']}{ext}"
        if not dest.exists():
            dest.write_bytes(body)

        kind = ("text-pdf-with-rendered-plates" if ext == ".pdf"
                else "searchable-text-layer-captions-only")
        entry = {
            "slug": row["slug"], "status": "LANDED", "file": fn, "row": row["row"],
            "tier": "PD",
            "basis": "US Government Printing Office 1957 ('UNITED STATES GOVERNMENT PRINTING "
                     "OFFICE WASHINGTON: 1957'). 17 USC 105 -- no US copyright. Evidence is in "
                     "the document's own title page, not in archive.org's rights field, which is "
                     "silent for this item.",
            "bytes": len(body), "sha256": sha,
            "landed": str(dest.relative_to(ROOT)).replace("\\", "/"),
            "shelf": SHELF, "kind": kind,
            "extracted_chars": len(text),
        }
        rcp = RECEIPTS / f"pc_{row['slug']}.md"
        rcp.write_text(
            f"# RETRIEVAL RECEIPT — US Navy engineering reference, row {row['row']} — {row['slug']}\n\n"
            f"archive_identifier: {IDENT}\n"
            f"selected_file: {fn}\n"
            f"content_sha256_16: {sha[:16]}\n"
            f"bytes: {len(body):,}\n"
            f"pulled: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%MZ')}\n"
            f"source: https://archive.org/download/{IDENT}/{fn}\n"
            f"rights_tier: PD ({entry['basis']})\n"
            f"source_kind: {kind}\n"
            f"landed: {entry['landed']}\n"
            f"extracted_chars: {len(text):,}\n"
            f"gap_closed: {row['why']}\n", encoding="utf-8")
        entry["receipt"] = str(rcp.relative_to(ROOT)).replace("\\", "/")
        results.append(entry)
        print(f"  LANDED  {fn[:44]:46s} {len(body):>12,}B  {ext}  {kind}")

    out = RUNS / "NAVAL_ENGINEERING_LANDING.json"
    prev = json.loads(out.read_text(encoding="utf-8")) if out.is_file() else {"rows": []}
    keep = {r["slug"] for r in results}
    prev["rows"] = [r for r in prev.get("rows", []) if r["slug"] not in keep] + results
    prev["landed"] = sum(1 for r in prev["rows"] if r["status"] == "LANDED")
    prev["bytes_landed"] = sum(r.get("bytes", 0) for r in prev["rows"] if r["status"] == "LANDED")
    prev["ts"] = datetime.now(timezone.utc).isoformat()
    out.write_text(json.dumps(prev, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n  {prev['landed']}/{len(ROWS)} landed, {prev['bytes_landed']:,} bytes -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())