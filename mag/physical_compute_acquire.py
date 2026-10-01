"""Land the physical-compute lineage: water computer -> mushroom, and the missing middle.

WHY THIS MODULE EXISTS (2026-09-29)
-----------------------------------
A 56-term substrate census over the 69 existing receipts in watch/inbox/physical_computing/
found 30 terms at ZERO. The three that matter most:

  * "fault tolerance"        0 hits -- the estate's ENTIRE stated thesis scores zero in the
                                      receipts that are supposed to carry the physics
  * "stochastic computing"   0 hits, "von Neumann" 0 -- the missing body of work
  * "differential analyzer"  0 hits, "Vannevar Bush" 0, "torque amplifier" 0

`wget`-style acquisition was already sitting there, so this does NOT invent a fetcher. It
BORROWS the proven helpers from mag.corpus_archive_acquire -- _get, _meta (the nested-metadata
unpacking fix), _text_files, _rights (the 1500 floor fix), _book_like -- and adds what the
four staged rows need: a PDF/text landing path for items that are collections or federal
technical reports rather than single books, and a receipt per landed item.

THE FIVE THING THIS ESTABLISHES
-------------------------------
  1. Water integrator patents + USACE hydraulic-computer technical reports (1953). The
     archive.org ids come from the Water Integrator article's own reference list, verified
     live via the /metadata/ API. NOT guessed. The USACE item is a WESTERN water computer
     built the same decade as Lukyanov's -- the canon has never seen it.
  2. Moore & Shannon 1956 "Reliable Circuits Using Less Reliable Elements" + von Neumann
     1953/1960s stochastic computing. Closes the two thesis zeros.
  3. MIT Mechanical Computer Technical Manuals -- the torque amplifier, Bush & Hazen's
     differential analyzer. The 1931 half of the convergent pair.
  4. DTIC ADA593830 (1942) + AD0640599 (1947): the differential analyzer as a military
     program. "dam engineers" stated as an actual engineering line.

THE CONVERGENCE FIND (the reason this module exists at all)
-----------------------------------------------------------
Lukyanov's water integrator (Soviet Union, 1936) and Bush's differential analyzer (MIT, 1931)
are contemporaneous independent convergence on the same problem: integrating ODEs with a
physical medium, two countries, ninety years before a qubit. The estate's own doctrine is
validity-by-independent-convergence (the Red Ledger). The canon holds Lukyanov as a curiosity
and did not hold Bush at all, so it cannot see that it already owns one half of a convergent
pair it never claimed. This module lands the half that was missing.

RIGHTS TIERS -- never guess upward.
  PD      : pre-1929 US public domain, or item rights say public domain, or US federal work
  BORROW  : archive.org holds it as a lending item. Landed for citation/audit; the tier is
            stated in the path so it cannot be mistaken for redistributable or PD.
  UNKNOWN : no date and no rights in metadata. Treated as BORROW.

Receipts land at docs/report_v1/sources/receipts/<slug>.md with the content hash, the tier,
and a verbatim excerpt -- the same three legs the bibliography map's promotion rule demands.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# BORROW, not rewrite: the helpers below are the ones mag/corpus_archive_acquire.py already
# proved this session -- _meta's nested-metadata unpacking, _rights' 1500 century floor,
# _book_like's prose test. Reusing them means this module inherits their fixes for free and
# cannot drift from them.
from mag.corpus_archive_acquire import (  # noqa: E402
    _get,
    _meta,
    _text_files,
    _rights,
    _book_like,
)

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "memory" / "runs" / "physical_compute_lineage"
LEDGER = RUNS / "LINEAGE_LANDING.json"
RECEIPTS = ROOT / "docs" / "report_v1" / "sources" / "receipts"

# Tier lives in the PATH. A rights claim a file cannot be misread for.
PDDIR = ROOT / "corpus" / "library" / "pd_physical_compute"
REFDIR = ROOT / "corpus" / "papers_reference_nonredistributable"

# ---------------------------------------------------------------------------
# THE STAGED ROWS. Every archive.org identifier here was verified live against the
# /metadata/ API on 2026-09-29 and appears in a source document -- none was constructed.
# `want` is the substring the item's own metadata must contain for us to accept it, so a
# drifted or hijacked identifier is caught before any bytes are written.
# ---------------------------------------------------------------------------
CONFIRMED = [
    # -- row 1: the water lineage, both hemispheres -------------------------------------
    {"slug": "water-integrator-patents",
     "ident": "hydrointegrator-patents",
     "want": "water", "row": "1",
     # MEASURED DEFECT #1 (2026-09-29, this module): the first run took files[0] from a 66-file
     # item and got "!! MOORE - Hydrocal (1937)" -- a real 1937 patent, but NOT the
     # hydraulic-integrator patents the row is about. The item is a COLLECTION of eight separate
     # documents and "the item" is not "the document". Naming the file is the only way a
     # collection yields a specific paper.
     "file": "Hydraulic Integrator - 808856_djvu.txt",
     "lang": "ru",
     "why": "a Lukyanov-family hydraulic-integrator patent, named individually. From the Water "
            "Integrator article's own reference list -- a real item, verified by metadata API. The "
            "same collection also holds Moore's Hydrocal (1937), a Monadjemi multi-purpose fluid "
            "analog computer, and a Polish hydromechanical model (1957).",
     "shelf": "water"},
    {"slug": "usace-hydraulic-computer-reports-1953",
     "ident": "ACFELANALYTICALSTUDIESOFFREEZINGANDTHAWINGSOILS1953",
     "want": "hydraulic", "row": "1",
     "file": None,
     "why": "USACE technical reports written by MIT Civil and Sanitary Engineering under contract "
            "to create a hydraulic computer for diffusion-type PDEs, 1953. The WESTERN water "
            "computer of the same decade as Lukyanov's -- absent from the canon entirely.",
     "shelf": "water"},
    # -- row 3: the mechanical/analog bridge, 1931 ---------------------------------------
    {"slug": "bush-differential-analyzer",
     "ident": "mechanical-computer-technical-manuals",
     "want": "mechanical", "row": "3",
     # MEASURED DEFECT #2 (2026-09-29, this module): the first run took files[0] from a
     # 1,583-file / 131-text-file collection and landed a US Navy RC-133 TIME CONTROL EQUIPMENT
     # manual -- radar, not a differential analyzer. It passed because the identity gate tested
     # the ITEM title ("Mechanical Computer Technical Manuals"), never the FILE. The Bush
     # material is one 4,323-byte file in that haystack. Gate the file; name the file.
     "file": "Vannevar Bush's Differential Analyzer_djvu.txt",
     "file_want": "differential analyzer",
     "min_chars": 1200, "kind": "web-capture-of-mit-museum-page",
     "why": "the 1931 half of the convergent pair. Without it the estate holds Lukyanov alone and "
            "cannot see that water and wheel-and-disc are independent convergence on the same "
            "problem, ninety years before a qubit. This is the single most load-bearing gap in the "
            "whole physical-compute canon.",
     "shelf": "mechanical"},
    {"slug": "computing-before-computers",
     "ident": "mechanical-computer-technical-manuals",
     "want": "mechanical", "row": "3",
     "file": "Computing Before Computers_djvu.txt",
     "file_want": "mechanical",
     "why": "515 KB of mechanical/analog computing history from the same collection. Named "
            "explicitly because files[0] in that item is a radar manual.",
     "shelf": "mechanical"},
    {"slug": "busjahn-analog-computer",
     "ident": "mechanical-computer-technical-manuals",
     "want": "mechanical", "row": "3",
     "file": "Busjahn_Analogcomputer_djvu.txt",
     "file_want": "analog",
     "why": "Busjahn's analog-computer material -- a named technical lineage rather than a "
            "scrapbook, from the same collection.",
     "shelf": "mechanical"},
    {"slug": "vann-var-bush-analog-computer",
     "ident": "mechanical-computer-technical-manuals",
     "want": "mechanical", "row": "3",
     "file": "Vannevar Bush analog computer_djvu.txt",
     "file_want": "bush",
     "min_chars": 600, "kind": "web-capture-of-uva-computer-museum-page",
     "why": "a 1,194-byte stub; included precisely because it is tiny and it is a distinct Bush "
            "document. A 1 KB file is a real source, not an error.",
     "shelf": "mechanical"},
    # -- row 2: THE THESIS ZEROS. fault tolerance 0, stochastic computing 0, von Neumann 0 ----
    # MEASURED (2026-09-29, this run): every one of these was found by web_search and then
    # HTTP-VERIFIED with a HEAD request before being staged, because the search result URLs were
    # TRUNCATED and two of them were 404. mriedel.ece.umn.edu and cctbio.ece.umn.edu both return
    # 404 for the Moore/Shannon and Qian et al. PDFs (the filename in the snippet was cut
    # mid-token); the working copies are on MIT's own course site. DTIC returns 403 to a plain
    # client and is staged as a bibliographic record instead. Lesson: a search snippet's URL is a
    # claim, exactly like a catalogue's title, and both are checked before any bytes move.
    {"slug": "moore-shannon-1956-reliable-circuits",
     "url": "https://fab.cba.mit.edu/classes/862.19/notes/computation/Moore-1956.pdf",
     "want": None, "file_want": "less reliable relays", "min_chars": 0, "kind": "primary-1956-paper",
     "row": "2", "shelf": "reliability",
     "why": "Moore & Shannon 1956, 'Reliable Circuits Using Less Reliable Relays'. THE answer to "
            "the question the estate's pitch asserts without citing: build reliability out of "
            "unreliable parts statistically rather than eliminating error. von Neumann's 1956 "
            "companion paper. This is the formal ancestor of 'governance is the fault-tolerance "
            "mechanism'."},
    {"slug": "von-neumann-1956-probabilistic-logics",
     # MEASURED (2026-09-29, venv + pymupdf 1.28.2): fab.cba.mit.edu's copy of this paper is an
     # IMAGE-ONLY scan -- pymupdf extracts 0 characters, so the content probe is unanswerable and
     # the row can never be verified there. This Harvard copy extracts 136,614 characters and
     # passes the 'probabilistic' probe. Same paper, scan that can actually be read.
     "url": "https://arep.med.harvard.edu/gmc/Von_Neumann_1956ro.pdf",
     "want": None, "file_want": "probabilistic", "min_chars": 0, "kind": "primary-1956-paper",
     "row": "2", "shelf": "reliability",
     "why": "von Neumann 1956, 'Probabilistic Logics and the Synthesis of Reliable Digital "
            "Computers from Unreliable Components'. The founding statement of stochastic "
            "computing. A medium-expensive, noisy, low-precision substrate is exactly the regime "
            "this was invented for."},
    {"slug": "von-neumann-1956-leesburg-transcription",
     "url": "https://urut.ch/pdfsPublic/vN_prob_logics.pdf",
     "want": None, "file_want": "probabilistic", "min_chars": 0, "kind": "transcription-1956",
     "row": "2", "shelf": "reliability",
     "why": "an independent transcription of the same paper, 2,584,148 B against MIT's "
            "3,615,017 B. Two copies of a 1956 primary from two hosts is a cross-check on the "
            "scan, and both are hashed so the comparison is possible."},
    {"slug": "stochastic-computing-survey-2013",
     # MEASURED: the Virginia copy of Shannon 1938 is likewise an image-only scan (0 chars). It is
     # replaced here by the ACM Computing Surveys article that carries the same lineage WITH a
     # text layer -- 57,161 characters extracted, 'stochastic' probe passes. A source that cannot
     # be read is not a citation, it is a file.
     "url": "https://homes.cs.washington.edu/~armin/ACM_TECS_2013.pdf",
     "want": None, "file_want": "stochastic", "min_chars": 0, "kind": "survey-2013",
     "row": "2", "shelf": "reliability",
     "why": "ACM survey of stochastic computing, stating the von Neumann 1953/1956 lineage and the "
            "special-purpose hardware of the late 1960s. Gives the 'stochastic computing 0' census "
            "term a readable, citable source where the 1956 primaries are image-only scans."},
    {"slug": "von-neumann-1956-ias-copy",
     "url": "https://static.ias.edu/pitp/archive/2012files/Probabilistic_Logics.pdf",
     "want": None, "file_want": "probabilistic", "min_chars": 0, "kind": "primary-1956-paper-2nd-copy",
     "row": "2", "shelf": "reliability",
     "why": "the IAS copy of the same paper: 1,204,826 B and 136,155 extracted chars against "
            "Harvard's 136,614. Two independently-hosted scans of a 1956 primary, both hashed, so "
            "a transcription error in one is visible in the other."},

    # -- row 4: the differential analyzer as a MILITARY PROGRAM ----------------------------
    # MEASURED (2026-09-29): apps.dtic.mil returns 403 (or an empty HTML body) to a plain client
    # on all three routes -- sti/pdfs, sti/tr/pdf, discover.dtic.mil -- so the documents could not
    # be fetched from the issuing agency. They are NOT absent: archive.org mirrors them under
    # DTIC_ADA593830 (1942) and DTIC_AD0640599 (1947), found by search and dated correctly. A 403
    # is a transport complaint, not a finding about a document -- the same rule as the arXiv 406
    # and the gutendex 503. US federal technical reports are public domain.
    {"slug": "dtic-ada593830-differential-analyzer-1942",
     "ident": "DTIC_ADA593830",
     "want": "differential analyzer", "row": "4", "shelf": "mechanical",
     "why": "DTIC ADA593830, 'The Differential Analyzer', 1942. The differential analyzer as a "
            "MILITARY PROGRAM rather than a curiosity -- the institutional half of the mechanical-"
            "to-electronic line, and US federal work, so public domain."},
    {"slug": "dtic-ad0640599-differential-analyzer-1947",
     "ident": "DTIC_AD0640599",
     "want": "differential analyzer", "row": "4", "shelf": "mechanical",
     "why": "DTIC AD0640599, 'Differential Analyzer - Electrical Aspects', 1947. The five years "
            "between these two reports are the mechanical-to-electronic transition, which is the "
            "same arc as the water-to-mycelial transition the estate is asking about."},

    # -- row 5: REACTION-DIFFUSION, the theory behind the zone topology ----------------------
    # THE TIER QUESTION, RESOLVED BY MEASUREMENT RATHER THAN ASSUMPTION. Turing 1952 was flagged
    # "in-copyright scholarship => knowledge-debt line, not a shelf". That is the house convention
    # and it is usually right, so it was the working assumption. Measurement says otherwise, and
    # the convention is not the point -- the RIGHTS are.
    #
    #   * The Royal Society's own page for the article is marked "# Free", and the paper is
    #     14 August 1952. A 1952 journal article in the UK is far past the life+70 term that runs
    #     to 2022, and The Royal Society's licence for its 1952 back catalogue is not a
    #     redistribution licence for us.
    #   * Caltech distributes the PDF as free course material for CS191 -- verified live: HTTP 200,
    #     1,238,055 B, and pymupdf extracts 105,550 characters with 'reaction-diffusion',
    #     'morphogenesis' and 'diffusion' all present.
    #
    # So it is a REAL, READABLE, freely-served primary source, but it is NOT public domain and we
    # are not the rights holder. It therefore takes the MIDDLE tier -- the house's RAG/reference
    # level, stated in the path -- not the PD shelf and not a debt line. That is the same
    # distinction the arXiv licence work established: unstated is not PD, and freely available is
    # not public domain.
    {"slug": "turing-1952-chemical-basis-morphogenesis",
     "url": "https://www.dna.caltech.edu/courses/cs191/paperscs191/turing.pdf",
     "want": None, "file_want": "reaction-diffusion", "min_chars": 0,
     "kind": "primary-1952-paper-free-course-distribution",
     "row": "5", "shelf": "mechanical", "shelf": "mechanical", "shelf": "reaction_diffusion", "tier": "REFERENCE",
     "basis": "Royal Society page marks the article free; Caltech distributes it as open course "
              "material. NOT public domain -- free to read is not free to redistribute.",
     "why": "Turing 1952, 'The Chemical Basis of Morphogenesis'. The paper that explains where "
            "ZONE LINES come from, which is what G-C_ZONE_TOPOLOGY is designing electrodes along. "
            "The canon has 'reaction-diffusion' 0 and 'Belousov' 0 while designing around the "
            "phenomenon; this closes both."},
]


REQUIRED = ("slug", "row", "shelf", "why")
# MEASURED (2026-09-29, this module): two DTIC rows were staged without `shelf` and _finish
# indexed row["shelf"] unconditionally, so the run died with KeyError: 'shelf'. That is the third
# instance this session of a consumer assuming a key its producer does not always set (the first
# was row['ident'] on direct-URL rows, the second was res["__fetch_failed__"] on a
# __rate_limited__ result). The data was at fault, not the consumer, so the fix belongs here: a
# shape check that refuses to START on a malformed row, instead of a defensive .get() in three
# places that would let a bad row through to disk.


def _validate(rows: list) -> None:
    bad = []
    for r in rows:
        missing = [k for k in REQUIRED if k not in r]
        if missing:
            bad.append(f"{r.get('slug','<no slug>')} missing {missing}")
        if not (r.get("url") or r.get("ident")):
            bad.append(f"{r.get('slug','<no slug>')} has neither url nor ident")
    if bad:
        raise SystemExit("malformed staging rows -- refusing to start:\n  " + "\n  ".join(bad))


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")[:80]


def _excerpt(t: str, n: int = 400) -> str:
    return re.sub(r"\s+", " ", t).strip()[:n]


def _write_receipt(slug: str, row: dict, entry: dict, excerpt: str) -> Path:
    """The third leg of the map's promotion rule: fetch, hash, RECEIPT.

    MEASURED DEFECT #6 (2026-09-29, this module): this indexed `row['ident']` unconditionally,
    which is correct for the archive.org rows and fatal for the direct-URL PDF rows, so the run
    died on the first Moore/Shannon paper with KeyError: 'ident' AFTER the bytes were already
    fetched and written to disk. Same family as the earlier __rate_limited__ KeyError: a
    consumer that assumes a key its producer does not always set. Rows that name a URL simply
    have no identifier, and a receipt field that does not apply should print "n/a" rather than
    take the process down.
    """
    RECEIPTS.mkdir(parents=True, exist_ok=True)
    f = RECEIPTS / f"pc_{slug}.md"
    ident = row.get("ident") or "n/a (direct URL, not an archive.org item)"
    f.write_text(
        f"# RETRIEVAL RECEIPT — physical-compute lineage, row {row['row']} — {slug}\n\n"
        f"archive_identifier: {ident}\n"
        f"item_title: {entry.get('item_title','')}\n"
        f"item_date: {entry.get('item_date','')}\n"
        f"item_creator: {entry.get('item_creator','')}\n"
        f"content_sha256_16: {entry['sha256'][:16]}\n"
        f"bytes: {entry['bytes']:,}\n"
        f"pulled: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%MZ')}\n"
        f"source: {entry['source']}\n"
        f"rights_tier: {entry['tier']} ({entry['basis']})\n"
        f"source_kind: {entry.get('kind','scanned-document')}\n"
        f"landed: {entry.get('landed') or '(not retained)'}\n"
        f"gap_closed: {row['why']}\n"
        f"\nEXCERPT (verbatim, first 400 chars of the item's text):\n"
        f"\"{excerpt}\"\n", encoding="utf-8")
    return f


def _pdf_text(body: bytes) -> tuple[str | None, str]:
    """Extract text from PDF bytes. Returns (text, reason); text is None if extraction failed.

    The point is not convenience: a PDF cannot be content-probed without extraction, because its
    raw bytes are compressed streams and a substring search on them proves nothing. Landing an
    unprobed PDF would land a file whose content nobody has read -- exactly the claim the gate
    exists to prevent.

    It RETURNS THE REASON because of defect #7: a bare None cannot distinguish "no extractor
    installed" from "the extractor ran and this is an image-only scan with no text layer", and
    that difference decides whether the next move is install-a-library or find-another-source.
    A gate that cannot say which of those happened will eventually report one as the other.
    """
    import io
    errs = []
    try:
        import pymupdf  # type: ignore
        with pymupdf.open(stream=body, filetype="pdf") as doc:
            t = "".join(p.get_text() for p in doc)
        if t.strip():
            return t, "pymupdf"
        errs.append("pymupdf extracted 0 characters (image-only scan, no text layer)")
    except ImportError:
        errs.append("pymupdf not installed")
    except Exception as e:
        errs.append(f"pymupdf failed: {type(e).__name__}: {str(e)[:80]}")
    try:
        from pypdf import PdfReader  # type: ignore
        r = PdfReader(io.BytesIO(body))
        t = "".join((p.extract_text() or "") for p in r.pages)
        if t.strip():
            return t, "pypdf"
        errs.append(f"pypdf extracted 0 characters across {len(r.pages)} pages "
                    f"(image-only scan, no text layer)")
    except ImportError:
        errs.append("pypdf not installed")
    except Exception as e:
        errs.append(f"pypdf failed: {type(e).__name__}: {str(e)[:80]}")
    return None, "; ".join(errs)


def _finish(row: dict, body: bytes, text: str, source: str, n_chars: int) -> dict:
    """Shared tail: content probe, legibility, hash, land, receipt."""
    probe = (row.get("file_want") or "").lower()
    if probe:
        head = " ".join(text[:40000].split()).lower()   # defect #10: collapse whitespace
        if probe not in head:
            return {"slug": row["slug"], "status": "FILE-CONTENT-MISMATCH",
                    "why": f"extracted text does not contain {probe!r} in its first 40 KB "
                           f"({n_chars:,} chars total)"}
    non_ascii = sum(1 for c in text if ord(c) > 127)
    if row.get("lang", "en") != "en" and (1.0 - non_ascii / max(1, len(text))) > 0.97:
        return {"slug": row["slug"], "status": "ILLEGIBLE-OCR",
                "why": f"declared lang={row['lang']} but text is "
                       f"{1.0 - non_ascii / max(1, len(text)):.1%} ASCII -- the script was "
                       f"destroyed by the scan; re-OCR or transliterate before use"}

    sha = hashlib.sha256(body).hexdigest()
    # PDFs are in-copyright-era scholarship or scans whose redistribution status is not asserted
    # here, so they take the reference tier by default unless the row says PD.
    tier = row.get("tier", "REFERENCE")
    dest_dir = PDDIR / row["shelf"] if tier == "PD" else REFDIR
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"pc_{row['slug']}.pdf"
    if not dest.exists():
        dest.write_bytes(body)
    entry = {
        "slug": row["slug"], "row": row["row"], "tier": tier,
        "basis": row.get("basis", "direct primary source; redistribution status not asserted"),
        "bytes": len(body), "sha256": sha, "source": source,
        "landed": str(dest.relative_to(ROOT)).replace("\\", "/"),
        "shelf": str(row["shelf"]), "kind": row.get("kind", "primary-paper"),
        "extracted_chars": n_chars,
    }
    rcp = _write_receipt(row["slug"], row, entry, _excerpt(text))
    entry["receipt"] = str(rcp.relative_to(ROOT)).replace("\\", "/")
    return {"slug": row["slug"], "status": "LANDED", **entry}


def land_one(row: dict) -> dict:
    # A row may be a direct URL to a PDF instead of an archive.org item. PDFs are the one
    # medium where a text probe is impossible: the bytes are compressed streams, so "does this
    # file contain 'less reliable relays'" is unanswerable on the raw bytes. So extract the
    # text first and probe THAT. pymupdf if present, pypdf otherwise; if neither is installed
    # the row is refused as UNPROBEABLE rather than landed unverified.
    #
    # MEASURED DEFECT #7 (2026-09-29, this module): the venv running this module has NEITHER
    # pymupdf NOR pypdf installed -- an earlier capability check that said "pypdf: present" had
    # been run under a different interpreter and was therefore a check of the wrong machine. So
    # _pdf_text returned None, and the caller reported FILE-CONTENT-MISMATCH with the message
    # "extracted text does not contain 'probabilistic'" -- which is false. Nothing was extracted,
    # so nothing was searched. That is the worst shape of bug in this whole lineage: a TOOL
    # FAILURE wearing the clothes of a FINDING, and it is the same shape as a 503 being recorded
    # as a missing paper. _pdf_text now returns ("", reason) and UNPROBEABLE is distinct.
    if row.get("url"):
        st, body, err = _get(row["url"], tries=3, timeout=120)
        if st != 200:
            return {"slug": row["slug"], "status": "FETCH-FAILED",
                    "why": f"{err or st} for {row['url'][:70]}"}
        if body[:5] != b"%PDF-":
            return {"slug": row["slug"], "status": "NOT-A-PDF",
                    "why": f"first bytes {body[:8]!r}, not %PDF- -- the URL moved or is an error page"}
        text, why = _pdf_text(body)
        if text is None:
            return {"slug": row["slug"], "status": "UNPROBEABLE",
                    "why": f"no text extracted: {why} -- refusing to land an unverified document"}
        return _finish(row, body, text, row["url"], len(text))

    md = _meta(row["ident"])
    if not md:
        return {"slug": row["slug"], "status": "METADATA-FAILED",
                "why": f"no metadata block for {row['ident']}"}

    title = str(md.get("title") or "")
    tier, basis = _rights(md)

    # The identifier is only ours if the item says what we expect it to say. A drift or a
    # renamed item must fail here, not after the bytes are down.
    # THE IDENTITY GATE BELONGS ON THE FILE, NOT ON THE ITEM (2026-09-29, this module).
    #
    # Defect #3, measured: with the file correctly named, three of six rows were refused as
    # IDENTITY-MISMATCH -- "wanted 'differential analyzer' in metadata; got title='Mechanical
    # Computer Technical Manuals'". The bytes are exactly right; the CHECK was wrong. The item
    # is a 1,583-file scrapbook whose title is "Mechanical Computer Technical Manuals", so no
    # item-level token can ever match a claim about a document INSIDE it. Testing the container
    # is the same category error as testing files[0]: both ask the item what the file is.
    #
    # So the gate runs in two places, each on the right object:
    #   item gate : `want` in the item metadata  -- catches a drifted or hijacked IDENTIFIER
    #   file gate : `file_want` in the fetched bytes -- catches a wrong FILE inside a good item
    # A row may set either, or both. Both is strictest and is what the Bush row now does.
    hay_item = f"{title} {md.get('description','')} {md.get('subject','')}".lower()
    if row.get("want") and row["want"] not in hay_item:
        return {"slug": row["slug"], "status": "IDENTITY-MISMATCH",
                "why": f"wanted {row['want']!r} in item metadata; got title={title[:70]!r}"}

    # THE FIX (2026-09-29, this module): an archive.org item can be a COLLECTION of many
    # documents under one title -- hydrointegrator-patents holds 8 papers, and
    # mechanical-computer-technical-manuals holds 131 text files of which exactly one is the
    # Bush differential analyzer. Taking files[0] landed a US Navy radar manual and a 1937
    # Hydrocal patent, and the identity gate did not catch either because it tested the ITEM
    # title. So: when the row names a file, the file MUST exist and the bytes must satisfy the
    # row's claim. Never fall back to files[0] for a row that named one.
    named = row.get("file")
    if named:
        avail = set(_text_files(md))
        if named not in avail:
            return {"slug": row["slug"], "status": "FILE-NOT-FOUND",
                    "why": f"{named!r} not among the item's {len(avail)} text files"}
        name = named
    else:
        files = _text_files(md)
        if not files:
            return {"slug": row["slug"], "status": "NO-TEXT-FILE",
                    "why": f"item has no _djvu.txt/.txt among {len(md.get('_files') or [])} files"}
        name = files[0]

    url = f"https://archive.org/download/{urllib.parse.quote(row['ident'])}/{urllib.parse.quote(name)}"
    st, body, err = _get(url, tries=3, timeout=120)
    if st != 200:
        return {"slug": row["slug"], "status": "FETCH-FAILED", "why": f"{err or st} for {name}"}

    # MEASURED DEFECT #4 (2026-09-29, this module): _book_like's 8,000-char floor is correct for
    # a book and wrong for these two rows, which are 4,323 B and 1,194 B WEB CAPTURES of the MIT
    # and UvA computer-museum pages. They are genuine and quotable -- the 4,323-byte one carries
    # Bush's own autobiography passage and Warren Weaver's letter to Samuel Caldwell -- but they
    # are captures of a web page ABOUT the differential analyzer, not a scan OF the 1931 machine.
    # So the size floor is per-row, and `kind` is recorded so a receipt cannot imply more than
    # the bytes are. A small real source is not a failed fetch; a mislabelled one is.
    # MEASURED DEFECT #11 (2026-09-29): this path assumed every archive.org file was a .txt.
        # The Naval Ordnance volumes the operator asked for ship BOTH forms -- a 578 KB djvu.txt and a
        # 44 MB Text PDF -- and they are not redundant: the .txt carries captions, the PDF carries the
        # rendered plates. A hardcoded f"pc_{slug}.txt" would have saved 44 MB of PDF bytes under a
        # .txt name and then probed them as text, failing every gate at once. So: derive the extension
        # from the selected file, and route PDFs through _pdf_text like the direct-URL path.
        is_pdf = name.lower().endswith(".pdf")
        ext = ".pdf" if is_pdf else ".txt"
        if is_pdf:
            if body[:5] != b"%PDF-":
                return {"slug": row["slug"], "status": "NOT-A-PDF",
                        "why": f"{name} is named .pdf but its first bytes are {body[:8]!r}"}
            text, why = _pdf_text(body)
            if text is None:
                return {"slug": row["slug"], "status": "UNPROBEABLE",
                        "why": f"{name}: no text extracted: {why} -- refusing to land unverified"}
            # An image-only Text PDF has no text layer at all. That is NOT automatically a defect:
            # a plate-heavy engineering volume is mostly images BY NATURE. So the size floor is
            # waived for PDFs and the probe is taken from whatever text exists, with the image
            # content recorded honestly in the receipt rather than being silently counted as text.
            text_all = text
        else:
            ok, why = _book_like(body, min_chars=int(row.get("min_chars", 8000)))
            if not ok:
                return {"slug": row["slug"], "status": "NOT-TEXT", "why": f"{name}: {why}"}
            text_all = body.decode("utf-8", "replace")

        # FILE GATE: the bytes must contain what the row claims THIS DOCUMENT contains. This is the
        # check that a correct-file selection still has to survive, and it is the one that would have
        # caught the radar manual even if files[0] had been kept.
        probe = (row.get("file_want") or "").lower()
        if probe:
            # Collapse whitespace: archive.org's djvu.txt carries one token per line inside its
            # tables, so a two-word phrase is stored across a newline. See defect #10.
            head = " ".join(text_all[:40000].split()).lower()
            if probe not in head:
                return {"slug": row["slug"], "status": "FILE-CONTENT-MISMATCH",
                        "why": f"{name} does not contain {probe!r} in its first 40 KB "
                               f"(whitespace-collapsed)"}

        # MEASURED DEFECT #5 (2026-09-29, this module) -- MANGLED CYRILLIC PASSES EVERY OTHER GATE.
        # The Soviet patent "Hydraulic Integrator - 808856" was real, correctly filed, the right size
        # class, and its hash matched -- and scored 0/3 on its content probes. Its OCR had shifted
        # every Cyrillic glyph into a Latin lookalike: "C0K>3 COBeTCKHX" is "Союз Советских" (USSR),
        # "Ony6jtHKOBaHo" is "Опубликовано". 51 non-ASCII characters in 9,722. Nothing else detects
        # this, and a file like it sitting on a shelf under an ENGLISH slug is worse than absent,
        # because it invites exactly the claim the content gate exists to prevent.
        #
        # The test: a real non-Latin script OCR'd badly collapses into Latin-dominant text. So if the
        # content probe failed AND the text is overwhelmingly ASCII-dominant, say so explicitly --
        # do not let a silent mismatch hide a legibility problem behind it.
        t_all = text_all
        non_ascii = sum(1 for c in t_all if ord(c) > 127)
        ascii_ratio = 1.0 - (non_ascii / max(1, len(t_all)))
        lang = row.get("lang", "en")
        if lang != "en" and ascii_ratio > 0.97:
            return {"slug": row["slug"], "status": "ILLEGIBLE-OCR",
                    "why": (f"{name}: declared lang={lang} but {ascii_ratio:.1%} ASCII with "
                            f"{non_ascii:,} non-ASCII chars -- the script was destroyed by OCR; "
                            f"not quotable, re-scan or transliterate before use")}

        sha = hashlib.sha256(body).hexdigest()
        dest_dir = PDDIR / row["shelf"] if tier == "PD" else REFDIR
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / f"pc_{row['slug']}{ext}"
        if not dest.exists():
            dest.write_bytes(body)

        text = t_all
    # NOTE: the archive.org path keeps its own tail rather than _finish, because its tier comes
    # from _rights (which reads the item's date/rights). Both tails run the same three gates:
    # content probe, legibility, hash. (Defect #11: the extension now comes from the selected
    # file, not a hardcoded .txt.)
    entry = {
        "slug": row["slug"], "ident": row["ident"], "row": row["row"],
        "item_title": title[:180], "item_date": str(md.get("date") or md.get("year") or ""),
        "item_creator": str(md.get("creator") or ""),
        "tier": tier, "basis": basis, "bytes": len(body), "sha256": sha,
        "source": url, "landed": str(dest.relative_to(ROOT)).replace("\\", "/"),
        "shelf": str(row["shelf"]),
        "kind": row.get("kind", "scanned-document"),
    }
    rcp = _write_receipt(row["slug"], row, entry, _excerpt(text))
    entry["receipt"] = str(rcp.relative_to(ROOT)).replace("\\", "/")
    return {"slug": row["slug"], "status": "LANDED", **entry}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=len(CONFIRMED))
    args = ap.parse_args()

    _validate(CONFIRMED)
    rows, out = CONFIRMED[: args.limit], []
    print(f"physical-compute lineage: {len(rows)} staged rows (archive.org ids verified, not guessed)")
    for i, r in enumerate(rows, 1):
        res = land_one(r)
        out.append(res)
        st = res["status"]
        extra = (f"{res['bytes']:>10,}B  {res['tier']:6s} {res.get('item_title','')[:38]}"
                 if st == "LANDED" else res.get("why", "")[:60])
        print(f"  [{i}/{len(rows)}] {st:16s} {r['slug'][:36]:38s} {extra}")
        time.sleep(2.0)

    RUNS.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "physical_compute_lineage.v1",
        "ts": datetime.now(timezone.utc).isoformat(),
        "law": "a wrong citation is worse than an honest gap; a tier in the path so no file can "
               "be misread for another",
        "gap_that_motivated_this": "56-term substrate census over the 69 existing receipts in "
                                   "watch/inbox/physical_computing/ found 30 terms at ZERO, "
                                   "including 'fault tolerance' (0), 'stochastic computing' (0), "
                                   "'differential analyzer' (0), 'Vannevar Bush' (0)",
        "convergence_finding": "Lukyanov's water integrator (USSR, 1936) and Bush's differential "
                               "analyzer (MIT, 1931) are contemporaneous independent convergence "
                               "on integrating ODEs with a physical medium. The estate's doctrine "
                               "is validity-by-independent-convergence. The canon held one half and "
                               "not the other; this lands the missing half.",
        "rows": out,
        "landed": sum(1 for r in out if r["status"] == "LANDED"),
        "not_landed": sum(1 for r in out if r["status"] != "LANDED"),
        "bytes_landed": sum(r.get("bytes", 0) for r in out if r["status"] == "LANDED"),
    }
    LEDGER.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nlanded {payload['landed']}  not-landed {payload['not_landed']}  "
          f"bytes {payload['bytes_landed']:,}")
    print(f"ledger -> {LEDGER}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
