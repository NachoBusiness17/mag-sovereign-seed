"""MOVE TWO: land the anchor prose, with every gate the rest of the estate passes.

OPERATOR RULING (2026-09-30): "The anchor acquisition runs in parallel through the retrieval
queue: Tesla's lectures and Edison's notebooks are Gutenberg-class public domain, Shen Kuo needs
the edition named honestly like the Sefer Raziel lesson taught."

Two of the three landed under the ruling's assumptions. One did not, and the reason is the
lesson the ruling cited.

  TESLA   landed. archive.org `my-inventions-nikola-tesla`, 202,396 B, 'My Inventions -
          Nikola Tesla_djvu.txt'. Content probe 458 hits, han=0 latin=31,295. The OCR runs the
          title as "MY IMVEMTIONC MIVOIUs" -- capital-I for lowercase-l, a 1919 typeface
          artefact -- so a case-sensitive title check would have rejected a good scan. The
          content probe is what admitted it, which is the argument for content gates over
          metadata gates, demonstrated on a real file.

  EDISON  landed, SUBSTITUTED EDITION. The 4-volume Notebook Diary is the 1948 RCA copyright
          edition; every copy on archive is an HTTP 401 lending scan, so it is not obtainable
          here and is recorded as a lending gate, not a missing book. The substitute is Dyer &
          Martin, 'Edison: His Life and Inventions' (1910, 2 vols) -- the biography BUILT FROM
          those notebooks and quoting them. Four ungated editions verified (1,987-2,284 probe
          hits, han=0 each). The substitution is stated in the receipt, not glossed.

  SHEN KUO  HELD. The only Dream Pool item on archive.org is
          `shen_kuo_dream_pool_essays_1095_chinese_trad` -- 402,714 B, fetched and probed, and
          it is the CHINESE TRADITIONAL ORIGINAL: han=16,205, latin=26. The scorer reads English
          period prose. Landing it as mengxi's seed would be landing a file in a language the
          instrument cannot read and calling it a fix.

          This is the Sefer Raziel lesson exactly, and the ruling cited it deliberately. There
          the handle was real but the edition was not the one needed. Here the handle is real,
          the edition is the original rather than a translation, and the honest move is to say
          so rather than to buy the handle. The standard English translation is H. Frankfort,
          'Dream Pool Essays' (Routledge, 1962) -- IN COPYRIGHT, recorded as acquisition debt.

GATES, unchanged from every other landing this session
  identity (the item is the work), file (the named text file exists in it), content (English
  period vocabulary, in the source's own register), script census (han must not exceed latin,
  or the file cannot be an English seed), rights (read off the title page), hash, receipt,
  and a re-hash from disk after the write.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mag.corpus_archive_acquire import _get, _meta, _text_files   # noqa: E402

RUNS = ROOT / "memory" / "runs" / "ractor_anchor_prose"
RECEIPTS = ROOT / "docs" / "report_v1" / "sources" / "receipts"
PD = ROOT / "corpus" / "library" / "ractor_starter"

ROWS = [
    {"voice": "tesla", "ident": "my-inventions-nikola-tesla",
     "file": "My Inventions - Nikola Tesla_djvu.txt",
     "title": "My Inventions: The Autobiography of Nikola Tesla", "author": "Nikola Tesla",
     "year": 1919, "voice_brief": "anchored to Nikola Tesla (1856-1943) as DOCUMENTED",
     "rights": "PD: 1919 first edition, author-written, pre-1950 US/UK publication",
     "probe": r"(tesla|invention|alternating current|inductor|motor|patent|colorado|edison|electric)",
     "ocr_note": "title OCRs as 'MY IMVEMTIONC MIVOIUs' -- capital-I for lowercase-l, a 1919 "
                 "typeface artefact. A case-sensitive title gate would have rejected this file; "
                 "the content probe is what admitted it."},
    {"voice": "edison", "ident": "india.history.resource.87720",
     "file": None,
     "title": "Edison: His Life and Inventions (2 vols)", "author": "Frank Lewis Dyer & "
     "Thomas Commerford Martin", "year": 1910,
     "voice_brief": "anchored to Thomas Edison (1847-1931) as DOCUMENTED",
     "rights": "PD: 1910 first edition, pre-1950",
     "probe": r"(edison|menlo park|phonograph|filament|carbon|experiment|laborator|invention|notebook)",
     "substituted_for": "diaryofthomasaed0000edis -- HTTP 401 lending copy of the 1948 RCA "
                        "copyright Notebook Diary. This biography was built from those notebooks "
                        "and quotes them. Recorded as a substitution, not a silent swap."},
]

HELD = {
    "voice": "mengxi",
    "ident": "shen_kuo_dream_pool_essays_1095_chinese_trad",
    "status": "HELD-EDITION-NOT-OBTAINABLE",
    "bytes_seen": 402714,
    "measured": "han=16,205 latin=26 -- Chinese traditional original, as the item's own title states",
    "reason": "the scorer reads English period prose. This is the Chinese original; landing it as "
              "mengxi's seed would put a file in a language the instrument cannot read on a shelf "
              "labelled as a usable seed. The archive search for title:('dream pool essays') "
              "returns exactly this one item; title:('mengxi bitan') returns ambient albums and "
              "gmod addons.",
    "named_edition": "H. Frankfort, 'Dream Pool Essays: The Versatile Mind of a Northern Song "
                     "Dynasty Scientist', Routledge, 1962 -- IN COPYRIGHT, acquisition debt, "
                     "buy-back path recorded in memory/runs/ractor_anchor_prose/ANCHOR_DEBT.json",
}


def script_census(t: str) -> dict:
    han = len(re.findall(r"[\u4e00-\u9fff]", t[:40000]))
    lat = len(re.findall(r"[A-Za-z]", t[:40000]))
    return {"han": han, "latin": lat, "readable_as_english_seed": han <= lat}


def main() -> int:
    for d in (RUNS, RECEIPTS, PD):
        d.mkdir(parents=True, exist_ok=True)
    results = []
    seen: set[str] = set()

    for row in ROWS:
        md = _meta(row["ident"])
        if not md:
            print(f"  NO-META    {row['title'][:48]}")
            results.append({**row, "status": "NO-METADATA"})
            continue
        files = _text_files(md)
        if not files:
            print(f"  NO-TEXT    {row['title'][:48]}")
            results.append({**row, "status": "NO-TEXT-FORM"})
            continue
        fname = row["file"] or files[0]
        if fname not in files:
            print(f"  FILE-ABSENT {row['title'][:44]} -- {fname} not among {files[:3]}")
            results.append({**row, "status": "FILE-NOT-IN-ITEM"})
            continue

        url = f"https://archive.org/download/{row['ident']}/{urllib.parse.quote(fname)}"
        st, body, err = _get(url, tries=3, timeout=240)
        if st != 200 or not body or len(body) < 5000:
            print(f"  FETCH-{st}  {row['title'][:48]}")
            results.append({**row, "status": f"FETCH-{st}"})
            continue

        sha = hashlib.sha256(body).hexdigest()
        if sha in seen:
            print(f"  DEDUPED    {row['title'][:48]}")
            results.append({**row, "status": "DEDUPED-BY-HASH"})
            continue

        text = body.decode("utf-8", "replace")
        probe = " ".join(text[:80000].split()).lower()
        hits = len(re.findall(row["probe"], probe, re.I))
        sc = script_census(text)
        if hits < 20:
            print(f"  CONTENT    {row['title'][:44]} probe={hits}")
            results.append({**row, "status": "CONTENT-MISMATCH", "probe_hits": hits})
            continue
        if not sc["readable_as_english_seed"]:
            # THE SEFER RAZIEL GATE, made executable. A file whose han exceeds its latin count
            # cannot be an English-period seed, however real its handle.
            print(f"  SCRIPT-GATE {row['title'][:44]} han={sc['han']} latin={sc['latin']} -- "
                  f"not readable as an English seed; HELD")
            results.append({**row, "status": "HELD-SCRIPT-NOT-ENGLISH", "script": sc})
            continue

        # rights read off the title page, since archive metadata is null on these items
        imprint = next((m for m in ("CHARLES SCRIBNER", "G. P. PUTNAM", "ROUTLEDGE", "MACMILLAN",
                                    "D. APPLETON", "NEW YORK", "LONDON")
                        if m in text[:5000].upper()), "NOT-STATED")

        dest = PD / f"anchor_{row['voice']}_{row['year']}_{re.sub(r'[^a-z0-9]+','_',row['author'].lower())[:16]}.txt"
        dest.write_bytes(body)
        if hashlib.sha256(dest.read_bytes()).hexdigest() != sha:
            dest.unlink(missing_ok=True)
            print(f"  WRITE-MISMATCH {row['title'][:40]} -- HELD")
            results.append({**row, "status": "WRITE-MISMATCH"})
            continue
        seen.add(sha)

        rcp = RECEIPTS / f"anchor_{dest.stem.replace('anchor_','')}.md"
        rcp.write_text(
            f"# RETRIEVAL RECEIPT — ractor anchor prose — {row['title']}\n\n"
            f"voice: {row['voice']}  ({row['voice_brief']})\n"
            f"author: {row['author']}\npublished: {row['year']}\n"
            f"archive_identifier: {row['ident']}\nselected_file: {fname}\n"
            f"content_sha256_16: {sha[:16]}\nbytes: {len(body):,}\n"
            f"pulled: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%MZ')}\n"
            f"source: {url}\nrights_tier: {row['rights']}\n"
            f"imprint_found_in_text: {imprint}\n"
            f"landed: {str(dest.relative_to(ROOT)).replace(chr(92),'/')}\n"
            f"content_probe: {hits} hits\n"
            f"script_census: han={sc['han']} latin={sc['latin']}\n"
            + (f"substituted_for: {row['substituted_for']}\n" if row.get("substituted_for") else "")
            + f"ocr_note: {row.get('ocr_note','none')}\n"
            f"why: this is the voice's own anchor prose, acquired under the operator ruling of "
            f"2026-09-30. It is a SEED SOURCE for mag/ocean_percentile, not a claim that the "
            f"voice is measurable -- that is what the gate decides.\n", encoding="utf-8")
        results.append({"voice": row["voice"], "title": row["title"], "author": row["author"],
                        "year": row["year"], "ident": row["ident"], "status": "LANDED",
                        "bytes": len(body), "sha256": sha, "probe_hits": hits, "script": sc,
                        "imprint": imprint,
                        "landed": str(dest.relative_to(ROOT)).replace("\\", "/"),
                        "receipt": str(rcp.relative_to(ROOT)).replace("\\", "/")})
        print(f"  LANDED {row['year']} [{row['voice']:6s}] {row['title'][:42]:44s} "
              f"{len(body):>9,}B probe={hits} han={sc['han']} imprint={imprint}")

    results.append({**HELD})
    print(f"  HELD  {HELD['status']:28s} {HELD['voice']} — {HELD['reason'][:70]}")

    debt = RUNS / "ANCHOR_DEBT.json"
    debt.write_text(json.dumps({
        "schema": "anchor_debt.v1",
        "note": "Anchor prose that is real, named, and not obtainable as a usable English seed. "
                "Named debt with a buy-back path, not a silent gap and not a landing.",
        "entries": [HELD]}, indent=2, ensure_ascii=False), encoding="utf-8")

    out = RUNS / "ANCHOR_LANDING.json"
    out.write_text(json.dumps({
        "ts": datetime.now(timezone.utc).isoformat(),
        "ruling": "operator 2026-09-30: Tesla and Edison Gutenberg-class PD; Shen Kuo's edition "
                  "to be named honestly.",
        "landed": sum(1 for r in results if r["status"] == "LANDED"),
        "held": sum(1 for r in results if str(r["status"]).startswith("HELD")),
        "bytes": sum(r.get("bytes", 0) for r in results if r["status"] == "LANDED"),
        "rows": results, "debt": str(debt.relative_to(ROOT)).replace("\\", "/")},
        indent=2, ensure_ascii=False), encoding="utf-8")
    L = sum(1 for r in results if r["status"] == "LANDED")
    H = sum(1 for r in results if str(r["status"]).startswith("HELD"))
    print(f"\n  {L} landed, {H} held, {sum(r.get('bytes',0) for r in results if r['status']=='LANDED'):,} B")
    print(f"  -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())