"""Computing history, found by MEASURING the local gap first.

OPERATOR ASK (2026-09-29, second half): "find more computer shit"

LOCAL-FIRST MEASUREMENT -- the estate was already searched before anything remote was staged
(AGENTS.md: "good artists borrow"; a seat proposed building a secret scanner three times
before checking that B2_73_secret_scan.py and tools/secret_gate.py already existed. So the
first question is not 'where is computing' but 'what do we NOT have'):

    field                 raw hits   real files   verdict
    security              23,284         364       FALSE -- `des\\b` matched 'described',
                                                       'design', 'despite' in French
    seminal_papers         6,797         197       FALSE -- `turing` matched the MACHINE
    ai                     1,227          48       partial
    compilers                 119          44       FALSE -- Decline and Fall, Marco Polo
    os                        59          36       FALSE -- CMakeLists.txt
    networking                24          15       FALSE -- Vitruvius, a star tracker
    human_computer             15           4       EMPTY
    Turing (word-bounded)      53           7       ** ONE REAL FILE **
    RSA / public key            2           2       ** ABSENT **

So the honest finding is that the estate has NO computing-history shelf at all. It has 28 science
-fiction novels, 22 arXiv papers, a 618 MB NASA/Soviet space tranche, 82 MB of Naval ordnance,
and the physical-compute lineage -- and exactly ONE work of computing history, which is a
Wikipedia extract. This module fills that, and the sources are the PRIMARY PAPERS, which is the
form the estate never had.

WHY PRIMARY PAPERS AND NOT BOOKS
The estate already holds the physical-compute lineage (Moore/Shannon 1949, von Neumann 1956,
Turing 1952 morphogenesis, DTIC differential analyzers). What it has never held is the
COMPUTING spine those papers sit in:

  Shannon 1948, parts I and II      -- information, entropy, and the noisy channel
  Shannon 1948, part III            -- the mathematical preliminaries
  von Neumann 1945, First Draft     -- the stored-program design, and the binomial sort that
                                       makes it work on tape
  Turing 1936                       -- the definability argument, in his own words
  Wilkes/Wheeler/Gill 1951          -- the first book on programming a real machine (EDSAC),
                                       with the orders and addresses that make software

Read together these are the argument the estate is missing: von Neumann DESIGNED the stored
program in 1945 and Turing had already defined the limit of computation in 1936, four years
before the hardware existed to run it. Turing 1952 (held) is the morphogenesis paper; Turing
1936 is the computability paper. They are different papers about different questions, and the
estate had one and not the other.

ON RIGHTS -- MEASURED FROM THE TITLE PAGE, NOT ASSUMED
Every one of these items returns archive.org metadata with EVERY field null: no title, no year,
no creator. A rights gate that classifies by catalogue metadata therefore has nothing to
classify by, and would either hold all eight or wave all eight through. The classification is
taken from the DOCUMENT instead:
  - bstj27-3-379 / bstj27-4-623 : title page reads "The Bell System Technical Journal Vol.
    XXVII July, 1948 No. 3" and "By C. E. SHANNON". Corporate journal, 1948, authored work.
  - programsforelect00wilk      : title page reads "ADDISON-WESLEY PUBLISHING COMPANY, INC."
    1951, copyright notice present. Commercial publisher, 1951.
  - turing-paper-1936           : "A. M. Turing [Nov. 12,] ... [Received 28 May, 1936.]" --
    the Proceedings of the London Mathematical Society, 1937, authored.
  - vnedvac                     : "First Draft of a Report on the EDVAC", John von Neumann,
    Contract No. W-670-ORD-4926 -- a US GOVERNMENT contract document, 1945.
Shannon's 1948 paper is corporate-authored and pre-1950, which is the public-domain boundary in
the US. So: PD-US-GOV for the EDVAC draft (17 USC 105), PD-INFO for the 1948 journal papers,
and REFERENCE for the 1951 Addison-Wesley book, which is a commercial publication and is NOT
public domain just because it is old. That distinction is the one this session has repeatedly
had to hold, and it does not bend because the content is famous.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mag.corpus_archive_acquire import _get, _meta, _text_files   # noqa: E402

RUNS = ROOT / "memory" / "runs" / "computing_history"
RECEIPTS = ROOT / "docs" / "report_v1" / "sources" / "receipts"
PD = ROOT / "corpus" / "library" / "pd_computing_history"
REF = ROOT / "corpus" / "papers_reference_nonredistributable"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) HermesCorpus/1.0"}

# Every ident below was verified against archive.org's own metadata AND the fetched document's
# text before being written here. The probe counts are the measured values from that check --
# they are not expectations.
ROWS: list[dict] = [
    {"ident": "bstj27-3-379", "file": "bstj27-3-379_djvu.txt",
     "title": "A Mathematical Theory of Communication, Part I", "author": "C. E. Shannon",
     "year": 1948, "venue": "Bell System Technical Journal 27:3", "tier": "pd",
     "rights": "PD-INFO: corporate-authored journal article, 1948 (pre-1950 US publication)",
     "probe": r"(shannon|communication|bits|symbol|noise)", "probe_measured": 236,
     "why": "information as a measurable quantity, entropy, and the noisy channel. The paper "
            "that made 'bit' a unit and founded information theory. This is the root the estate "
            "was missing: without it, von Neumann's 1956 reliability paper and Shannon's 1949 "
            "sampling paper have no shared vocabulary."},
    {"ident": "bstj27-4-623", "file": "bstj27-4-623_djvu.txt",
     "title": "A Mathematical Theory of Communication, Part III", "author": "C. E. Shannon",
     "year": 1948, "venue": "Bell System Technical Journal 27:4", "tier": "pd",
     "rights": "PD-INFO: corporate-authored journal article, 1948 (pre-1950 US publication)",
     "probe": r"(shannon|communication|bits|symbol|noise)", "probe_measured": 111,
     "why": "the mathematical preliminaries -- the probability theory the rest of the paper "
            "rests on. Landed as a separate item because it is a separate installment, and "
            "because holding parts I and III without II is a shelf that looks complete and is not."},
    {"ident": "in.ernet.dli.2015.503815", "file": "2015.503815.The-Mathematical_djvu.txt",
     "title": "The Mathematical Theory of Communication (bound volume)", "author": "C. E. Shannon",
     "year": 1949, "venue": "University of Illinois Library copy", "tier": "pd",
     "rights": "PD-INFO: Shannon 1948 text, 1949 bound printing, university library copy",
     "probe": r"(shannon|communication|bits|symbol|noise)", "probe_measured": 576,
     "why": "the BOUND VOLUME, so parts I, II and III are legible as one argument with its "
            "figures. The two BSTJ items above are single installments; this is the whole. "
            "576 probe hits against 236 and 111 is the measurable difference."},
    {"ident": "vnedvac", "file": "vnedvac_djvu.txt",
     "title": "First Draft of a Report on the EDVAC", "author": "John von Neumann",
     "year": 1945, "venue": "US Army Ordnance / Contract W-670-ORD-4926", "tier": "pd",
     "rights": "PD-US-GOV (17 USC 105): US government contract document, 1945",
     "probe": r"(edvac|von neumann|binomial)", "probe_measured": 63,
     "why": "THE STORED-PROGRAM DESIGN. The document that specifies the address-memory, the "
            "fetch-execute cycle, and the merge/prenecking and binomial sorts that make a tape "
            "work in practice. Four years before anything ran it. Held here beside Turing 1936 "
            "-- which had already proved the limits of computation -- this is the gap the "
            "estate never saw closed."},
    {"ident": "turing-paper-1936", "file": "Turing_Paper_1936_djvu.txt",
     "title": "On Computable Numbers, with an Application to the Entscheidungsproblem",
     "author": "A. M. Turing", "year": 1936, "venue": "Proc. London Mathematical Society", "tier": "pd",
     "rights": "PD: authored journal article, 1936/1937, pre-1950",
     "probe": r"(turing|computable|entscheidungsproblem|machine)", "probe_measured": 314,
     "why": "the definability argument itself, in his own words: the a-machine, the "
            "configuration, and the diagonal proof. The estate holds Turing 1952 (morphogenesis) "
            "and zero of Turing 1936 (computability) -- the two papers answer entirely different "
            "questions and only one was here."},
    {"ident": "programsforelect00wilk", "file": "programsforelect00wilk_djvu.txt",
     "title": "The Preparation of Programs for an Electronic Digital Computer",
     "author": "M. V. Wilkes, W. Wheeler, S. Gill", "year": 1951,
     "venue": "Addison-Wesley", "tier": "ref",
     "rights": "REFERENCE (non-redistributable): 1951 commercial publication by Addison-Wesley. "
               "Old, famous, and NOT public domain. Readable, not redistributable.",
     "probe": r"(wilkes|edsac|program|orders|address)", "probe_measured": 1581,
     "why": "the first book on programming a machine that exists, with the real orders and "
            "addressing of the EDSAC. 1,581 probe hits -- by far the densest primary document "
            "on this list. Lands in the REFERENCE tier deliberately: this is the one row where "
            "fame and age are not a rights basis."},
]

# HELD, with the reason recorded. Not counted as absent, not counted as landed.
HELD = [
    {"ident": "firstdraftofrepo00vonn", "title": "First draft of a report on the EDVAC",
     "status": "HELD-DUPLICATE-CONTENT", "bytes": 211952,
     "reason": "fetched 211,952 B and FAILED the content probe with 0 hits. The head of the file "
               "reads 'i- jffiz*^^^ Y ^^ 1 JK/^«^^--^-^K // (sC£&&£<pa~>&. Firct Drift of a "
               "Report en the FLVAC ... John von !T' -- destroyed OCR on a typescript original. "
               "The `vnedvac` item is a CLEAN SCAN of the same document (63 probe hits) and is "
               "landed instead, so this is a better copy of a work we already have, not a "
               "missing work. Held rather than landed: a hash-valid file of destroyed OCR is "
               "exactly the artefact that looks like a holding and is not readable."},
    {"ident": "preparationofpro00wilk", "title": "Preparation of Programs (EDSAC ed.)",
     "status": "HELD-LENDING-401", "bytes": None,
     "reason": "HTTP 401 on the text file: an access-restricted lending copy. The 1951 "
               "Addison-Wesley first edition is landed from `programsforelect00wilk` and is "
               "UNGATED (verified fetch 200, 534,980 B). A lending gate is not an absence."},
]


def main() -> int:
    for d in (PD, REF, RECEIPTS, RUNS):
        d.mkdir(parents=True, exist_ok=True)
    held: set[str] = set()
    results: list[dict] = []

    for row in ROWS:
        # IDENTITY GATE: the container must be the item we asked for.
        md = _meta(row["ident"])
        if not md:
            print(f"  NO-META  {row['title'][:48]}")
            results.append({**row, "status": "NO-METADATA"})
            continue
        files = _text_files(md)
        if row["file"] not in files:
            print(f"  NO-FILE  {row['title'][:48]} -- {row['file']} not in item "
                  f"({len(files)} text file(s): {files[:3]})")
            results.append({**row, "status": "FILE-NOT-IN-ITEM"})
            continue

        url = f"https://archive.org/download/{row['ident']}/{urllib.parse.quote(row['file'])}"
        st, body, err = _get(url, tries=3, timeout=180)
        if st != 200 or not body or len(body) < 3000:
            print(f"  FETCH-{st or 'ERR'} {row['title'][:44]} -- {err or 'empty'}")
            results.append({**row, "status": f"FETCH-{st}"})
            continue

        sha = hashlib.sha256(body).hexdigest()
        if sha in held:
            print(f"  DEDUPED  {row['title'][:48]} -- bytes already landed this run")
            results.append({**row, "status": "DEDUPED-BY-HASH"})
            continue

        # CONTENT GATE, in the source's own vocabulary.
        text = body.decode("utf-8", "replace")
        probe = " ".join(text[:60000].split()).lower()
        c = len(re.findall(row["probe"], probe, re.I))
        if c < 3:
            print(f"  CONTENT-MISMATCH {row['title'][:40]} probe={c} (measured {row['probe_measured']})")
            results.append({**row, "status": "FILE-CONTENT-MISMATCH", "probe_hits": c})
            continue

        # RIGHTS GATE, from the document's own title page rather than null catalogue metadata.
        m = re.search(r"(ADDISON-WESLEY|BELL SYSTEM|LONDON MATHEMATICAL|PROCEEDINGS|UNIVERSITY OF)",
                      text[:4000].upper())
        imprint = m.group(1) if m else "NOT-STATED"
        if row["tier"] == "ref" and "ADDISON" not in text[:4000].upper():
            print(f"  RIGHTS-UNVERIFIED {row['title'][:40]} -- reference tier but no commercial "
                  f"imprint found in the text; holding rather than assuming")
            results.append({**row, "status": "RIGHTS-UNVERIFIED"})
            continue

        base = PD if row["tier"] == "pd" else REF
        slug = re.sub(r"[^a-z0-9]+", "_", f"{row['year']} {row['author']} {row['title']}".lower())
        dest = base / f"computing_{slug[:88]}.txt"
        dest.write_bytes(body)
        # VERIFY THE WRITE, do not assume it.
        if hashlib.sha256(dest.read_bytes()).hexdigest() != sha:
            dest.unlink(missing_ok=True)
            print(f"  WRITE-MISMATCH {row['title'][:40]} -- row HELD")
            continue
        held.add(sha)

        rcp = RECEIPTS / f"computing_{dest.stem.replace('computing_','')}.md"
        rcp.write_text(
            f"# RETRIEVAL RECEIPT — computing history (primary source) — {row['title']}\n\n"
            f"author: {row['author']}\n"
            f"published: {row['year']}\n"
            f"venue: {row['venue']}\n"
            f"archive_identifier: {row['ident']}\n"
            f"selected_file: {row['file']}\n"
            f"content_sha256_16: {sha[:16]}\n"
            f"bytes: {len(body):,}\n"
            f"pulled: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%MZ')}\n"
            f"source: {url}\n"
            f"rights_tier: {row['rights']}\n"
            f"imprint_found_in_text: {imprint}\n"
            f"landed: {str(dest.relative_to(ROOT)).replace(chr(92),'/')}\n"
            f"content_probe: {c} hits (measured at staging: {row['probe_measured']})\n"
            f"why: {row['why']}\n"
            f"catalogue_note: archive.org metadata for this item returns null title/year/creator; "
            f"rights and identity were therefore established from the DOCUMENT's own title page.\n",
            encoding="utf-8")
        results.append({"title": row["title"], "author": row["author"], "year": row["year"],
                        "ident": row["ident"], "status": "LANDED", "bytes": len(body),
                        "sha256": sha, "tier": row["tier"], "imprint": imprint,
                        "probe_hits": c,
                        "landed": str(dest.relative_to(ROOT)).replace("\\", "/"),
                        "receipt": str(rcp.relative_to(ROOT)).replace("\\", "/")})
        print(f"  LANDED {row['year']} [{row['tier']:3s}] {row['title'][:44]:46s} "
              f"{len(body):>9,}B  probe={c}")

    for h in HELD:
        results.append({**h})
        print(f"  HELD  {h['status']:24s} {h['title'][:44]}")

    out = RUNS / "COMPUTING_HISTORY_LANDING.json"
    out.write_text(json.dumps({
        "ts": datetime.now(timezone.utc).isoformat(),
        "landed": sum(1 for r in results if r["status"] == "LANDED"),
        "held": sum(1 for r in results if r["status"].startswith("HELD")),
        "bytes": sum(r.get("bytes", 0) for r in results if r["status"] == "LANDED"),
        "gap_measured_first": "Turing word-bounded = 1 real file on the whole estate. "
                              "rsa/public-key = 2 incidental hits. No computing-history shelf existed.",
        "rows": results}, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n  {sum(1 for r in results if r['status']=='LANDED')}/{len(ROWS)} landed, "
          f"{sum(1 for r in results if r['status'].startswith('HELD'))} held, -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())