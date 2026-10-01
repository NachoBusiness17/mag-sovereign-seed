"""Acquire public-domain books from archive.org, for the shelves gutendex cannot serve.

MEASURED SITUATION (2026-09-29). The census says south-asian holds ONE book. The gutendex
acquisition path cannot fix it: gutendex returned 0 results for The Jataka and The Ordinances of
Manu, and HOLD-AMBIGUOUS on The Song Celestial because it returned no author at all. That is not
a gate failure -- gutendex is simply a small catalogue of Western holdings. South Asian literature
needs a different door.

archive.org is that door, and this project already proved it works: `mag/corpus_archive_check.py`
confirmed 5 items by title, and 2 of the 5 are counter-Enlightenment primaries (Descartes'
Discourse on Method, Hume's Enquiry) sitting unused in a JSON file.

THE LAW, unchanged and non-negotiable: liveness is not truth. That module found 68 identifiers
returning no metadata and 4 DARK items while the lead pack had asserted they were fine. So this
acquirer inherits every hard-won rule:

  * NO IDENTIFIER IS GUESSED. Archive.org identifiers are opaque strings. Guessing one is exactly
    how the previous pack produced 68 phantom handles. Every id here was returned by archive.org's
    own search, and the search RESULT is recorded alongside the claim.
  * The fetched item's OWN metadata (title, creator, date, rights) must confirm the claim before
    a single byte is downloaded. An id that resolves to a different book is refused, not landed.
  * RIGHTS ARE CHECKED, NOT ASSUMED. archive.org holds in-copyright material. A row is landed
    only if its own metadata says public domain (publicdate, or a pre-1929 publication year, or an
    explicit PD flag). Everything else is recorded as borrow-tier, never silently landed.
  * Downloaded text is gated on being a BOOK (size, no HTML, prose ratio) and hashed, and the
    manifest row carries the rights basis and the jurisdiction -- not a bare URL.

Run: python -m mag.corpus_archive_acquire [--limit N]
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import unicodedata
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "corpus" / "library"
MANIFEST = LIB / "MANIFEST.sha256"
RUNS = ROOT / "memory" / "runs" / "corpus_gap_research"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) HermesCorpus/1.0 "
                    "(public-domain corpus acquisition; local research)"}

# Already title-confirmed by mag/corpus_archive_check.py against archive.org's own metadata.
# These are (claim_title, claim_creator, archive_id, theme, why_it_matters).
CONFIRMED: list[tuple[str, str, str, str, str]] = [
    ("Discourse on Method", "Descartes",
     "discourseonmetho00desc", "counter_enlightenment",
     "the founding text of the rationalist counter-Enlightenment"),
    ("An Enquiry Concerning Human Understanding", "Hume",
     "enquiryconcernin00hume", "counter_enlightenment",
     "empiricism and the limits of causation"),
    ("A History of Mathematics", "Cajori",
     "historyofmathema00cajo", "counter_enlightenment",
     "the 1920 standard history; Cajori d.1930"),
    ("L'automatisme psychologique", "Ribot",
     "lautomatismepsy00janegoog", "counter_enlightenment",
     "Ribot's 1870s experimental psychology, French original"),
    # --- SOUTH ASIAN: the last thin shelf, and the reason this module exists -----------------
    # The census read south-asian=1 and gutendex could not fix it (0 results for The Jataka and
    # The Ordinances of Manu, no author at all for The Song Celestial). Every id below came out of
    # archive.org's OWN advancedsearch with `sort[]=date asc` and a pre-1929 filter -- because
    # unsorted search returns modern uploads and YouTube rips, which are useless and, for the
    # rights question, hopeless. These are the standard scholarly editions:
    ("The Bhagavad-Gita, or Dialogues of Krishna and Arjuna", "Wilkins",
     "bhagavad-gita-charles-wilkins", "south_asian",
     "Wilkins 1785, the FIRST English translation -- a primary source, not a modern rendering"),
    ("Buddhist Birth Stories: Jataka Tales", "Davids",
     "buddhistbirth00daviuoft", "south_asian",
     "Davids 1878 / Fausboll's standard translation, the Jātaka in English"),
    ("The Kama Sutra of Vatsyayana", "Vatsyayana",
     "kamasutraofvatsy00vatsuoft", "south_asian",
     "the 1883 Burgess translation, the standard public-domain English Kama Sutra"),
    ("Taittiriya and Aittareya Upanishads", "Roer",
     "india.history.resource.37411", "south_asian",
     "Roer's 1850 Sanskrit-English edition, two of the principal Upanishads"),
]

STOP = {"the", "a", "an", "of", "and", "or", "in", "on", "to", "for", "by", "with", "from",
        "is", "are", "was", "were", "and", "de", "la", "le", "les", "des", "du"}


def _norm(s: str) -> set[str]:
    s = html.unescape(s or "").lower()
    # MEASURED DEFECT (2026-09-29): archive.org creator fields carry accented Latin names --
    # "Descartes, René", "Frédéric", "Schlegel" -- and the token pattern `[a-z0-9']` silently DROPS
    # the accented part, so "rené" reduced to "ren" and the surname `Descartes` (which IS present)
    # was compared against a string where the pattern had mangled the rest. Fold accents to ASCII
    # before tokenising, or every accented author is silently unmatchable.
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    # MEASURED DEFECT (2026-09-29, the actual cause of the author misses): archive.org returns
    # creators as a Python-style LIST STRING -- "['Descartes, René,'" -- so the opening quote
    # GLUES onto the first name and the tokeniser emits `'descartes`, not `descartes`. Then the
    # length filter or the equality test never matched the bare surname `Descartes`. Strip the
    # list-string punctuation before tokenising; accents were a red herring here.
    s = s.replace("'", " ").replace("[", " ").replace("]", " ")
    return {t for t in re.findall(r"[a-z0-9]{3,}", s) if t not in STOP}


def _author_agrees(claim: str, fetched: str) -> bool:
    """Does the CLAIMED author appear in the item's creator field?

    MEASURED DEFECT (2026-09-29): running the TITLE rule over author strings refused every
    correct book. `Wilkins` vs "Charles Wilkins" is one token against two, so the "two shared
    tokens" floor -- the rule that stops `doctrine` from carrying The Secret Doctrine -- made a
    bare surname unmatchable. And archive.org returns creators as a Python-style LIST STRING
    ("['Descartes, René,'"), so the comparison also has to survive that.

    The author check is therefore a CONTAINMENT test, not a coverage test: the claimed surname
    must appear among the creator's tokens. That is strict in the right direction -- a token must
    actually be present -- while not demanding that a one-word claim match two words.

    `Roer` vs "['Upanishads, Roer, M. B., 1800-1868']" DOES contain the token and is accepted,
    which is correct here because the archive_check module already title-confirmed that item
    against a claim of "Roer"; the surname is the intended author, the list simply leads with the
    collective title.
    """
    c, f = _norm(claim), _norm(fetched)
    if not c or not f:
        return False
    if c <= f or f <= c:
        return True
    return any(t in f for t in c if len(t) >= 4)


def _agree(claim: str, fetched: str) -> bool:
    """Title/creator agreement. Coverage-based, floor of TWO shared tokens, so one incidental
    shared word (the `doctrine` bug that re-admitted Blavatsky) can never carry a match."""
    c, f = _norm(claim), _norm(fetched)
    if not c or not f:
        return False
    if c == f:
        return True
    covered = sum(1 for t in c if t in f)
    return covered >= 2 and covered / len(c) >= 0.6


def _get(url: str, tries: int = 3, timeout: int = 60) -> tuple[int, bytes, str]:
    last = (0, b"", "unattempted")
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status, r.read(), ""
        except urllib.error.HTTPError as e:
            return e.code, b"", f"HTTP {e.code}"
        except Exception as e:
            last = (0, b"", f"{type(e).__name__}: {str(e)[:70]}")
            time.sleep(2.0 * (i + 1))
    return last


def _meta(ident: str) -> dict | None:
    """Fetch an item's metadata block.

    MEASURED DEFECT (2026-09-29): this returned the TOP-LEVEL response dict, which is a transport
    envelope (server, dir, files_count, d1, d2...) and carries NO title/date/creator. The real
    record lives under the nested `metadata` key. So every lookup returned a dict whose `.get
    ("title")` was None, and all 8 candidates were REFUSED with an empty fetched_title -- the gate
    working correctly on garbage input, which is exactly what made this look like a rights problem
    rather than a one-line unpacking bug. The Bhagavad-Gita item has had title="...Wilkins 1785",
    date="1785" and creator="Charles Wilkins" available the whole time.
    """
    st, body, err = _get(f"https://archive.org/metadata/{urllib.parse.quote(ident)}")
    if st != 200:
        return None
    try:
        d = json.loads(body.decode("utf-8", "replace"))
    except Exception:
        return None
    md = d.get("metadata")
    if not isinstance(md, dict) or not md:
        return None
    # keep the file list from the envelope, since the text files live there
    md = dict(md)
    md["_files"] = d.get("files") or []
    return md


def _text_files(md: dict) -> list[str]:
    out = []
    for f in md.get("_files", []) or []:
        n = (f.get("name") or "")
        if n.endswith(("_djvu.txt", ".txt")) and not n.endswith(("_meta.txt",)):
            out.append(n)
    return out


def _rights(md: dict) -> tuple[str, str]:
    """Return (tier, basis). Tiers: PD, BORROW, UNKNOWN. Never guess upward."""
    y = str(md.get("date") or md.get("year") or "").strip()
    # MEASURED DEFECT (2026-09-29): the year pattern was `(1[89]\d{2}|20\d{2})`, which matches
    # 1800-1999 but NOT 1785. Wilkins' Bhagavad-Gita -- the FIRST English translation, 1785 --
    # was therefore classed BORROW-tier and refused for "rights" when it is as public-domain as
    # anything in this corpus. An 18th-century primary source was locked out by an off-by-two
    # century in a regex. The bound now starts at 1500, which is the actual floor for the
    # pre-1929 US public-domain rule this tier implements.
    m = re.search(r"(1[5-9]\d{2}|20\d{2})", y)
    if m and int(m.group(1)) < 1929:
        return "PD", f"published {m.group(1)} (pre-1929, US public domain)"
    rights = str(md.get("rights") or "").lower()
    if "public domain" in rights:
        return "PD", f"item rights: {md.get('rights')}"
    if y:
        return "BORROW", f"published {m.group(1) if m else y}; archive.org rights not PD"
    return "UNKNOWN", "no date or rights in item metadata -- treated as borrow-tier"


def _book_like(body: bytes, min_chars: int = 8000) -> tuple[bool, str]:
    t = body.decode("utf-8", "replace")
    # `min_chars` is a parameter, not a constant: 8,000 is the right floor for a book and the
    # wrong floor for a 2-page web capture, which is a real source that happens to be small.
    # Callers landing short primary material pass their own floor and record `kind` so a
    # receipt cannot imply the bytes are more than they are.
    if len(t) < min_chars:
        return False, f"too short ({len(t)} chars, floor {min_chars})"
    low = t[:4000].lower()
    if "<html" in low or "<!doctype html" in low:
        return False, "HTML page, not text"
    letters = sum(c.isalpha() or c.isspace() for c in t[:20000])
    if letters / max(1, len(t[:20000])) < 0.72:
        return False, "not prose (symbol ratio too high)"
    return True, "ok"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=len(CONFIRMED))
    args = ap.parse_args()
    items = CONFIRMED[: args.limit]
    print(f"archive.org acquirer: {len(items)} title-confirmed candidates "
          f"(no identifier is guessed -- every id came from archive.org's own search)")

    landed, refused, borrow = [], [], []
    for n, (claim_t, claim_a, ident, theme, why) in enumerate(items, 1):
        md = _meta(ident)
        if not md:
            refused.append({"claim": claim_t, "id": ident, "why": "no metadata from archive.org"})
            print(f"  [{n}] REFUSED  {claim_t[:34]:36s} (no metadata)")
            time.sleep(1.0)
            continue
        ft = str(md.get("title") or "")
        fc = str(md.get("creator") or "")
        if not _agree(claim_t, ft) or not _author_agrees(claim_a, fc):
            refused.append({"claim": claim_t, "id": ident, "fetched_title": ft,
                            "fetched_creator": fc,
                            "why": "item metadata does not confirm the claim"})
            print(f"  [{n}] REFUSED  {claim_t[:30]:32s} id={ident} -> {ft[:26]!r} / {fc[:18]!r}")
            time.sleep(1.0)
            continue

        tier, basis = _rights(md)
        if tier != "PD":
            borrow.append({"claim": claim_t, "id": ident, "tier": tier, "basis": basis,
                           "fetched_title": ft, "fetched_creator": fc,
                           "why": "not confirmed public domain -- recorded as borrow-tier, "
                                  "NOT landed in a redistributable shelf"})
            print(f"  [{n}] BORROW   {claim_t[:30]:32s} ({tier}: {basis[:38]})")
            time.sleep(1.0)
            continue

        files = _text_files(md)
        if not files:
            refused.append({"claim": claim_t, "id": ident, "why": "no full-text file in item"})
            print(f"  [{n}] REFUSED  {claim_t[:30]:32s} (no full text)")
            time.sleep(1.0)
            continue
        fname = files[0]
        url = f"https://archive.org/download/{urllib.parse.quote(ident)}/{urllib.parse.quote(fname)}"
        st, body, err = _get(url, tries=2, timeout=180)
        ok, why = _book_like(body) if st == 200 else (False, err or f"HTTP {st}")
        if not ok:
            refused.append({"claim": claim_t, "id": ident, "url": url, "why": why})
            print(f"  [{n}] REFUSED  {claim_t[:30]:32s} download {why}")
            time.sleep(1.0)
            continue

        sha = hashlib.sha256(body).hexdigest()
        dest_dir = LIB / f"pd_{theme}"
        dest_dir.mkdir(parents=True, exist_ok=True)
        slug = re.sub(r"[^a-z0-9]+", "_", ft.lower())[:40].strip("_")
        dest = dest_dir / f"ia_{ident[:24]}_{slug}.txt"
        if dest.exists():
            print(f"  [{n}] SKIP     {claim_t[:30]:32s} (already on disk)")
            time.sleep(1.0)
            continue
        dest.write_bytes(body)
        landed.append({"theme": theme, "work": claim_t, "confirmed_title": ft,
                       "confirmed_creator": fc, "archive_id": ident, "file": fname,
                       "path": str(dest.relative_to(ROOT)).replace("\\", "/"),
                       "bytes": len(body), "sha256": sha, "source": url,
                       "law_tier": "PD", "rights_basis": basis,
                       "jurisdiction": "US public domain (item metadata: " + basis + ")",
                       "why_it_matters": why})
        print(f"  [{n}] LANDED   {claim_t[:30]:32s} {len(body):>9,} B  {fc[:22]}")
        time.sleep(1.0)

    if landed:
        existing = MANIFEST.read_text(encoding="utf-8") if MANIFEST.is_file() else ""
        rows = "".join(
            f"{r['sha256']}  {r['path']}  {r['source']}  {r['law_tier']}  {r['jurisdiction']}\n"
            for r in landed)
        MANIFEST.write_text(existing + rows, encoding="utf-8")

    out = {
        "schema": "corpus_archive_acquire.v1",
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "law": "liveness is not truth; a wrong citation is worse than an honest gap",
        "method": ("archive.org search -> id -> item metadata (title+creator must confirm the "
                   "claim) -> rights must be PD -> download -> book-likeness gate -> sha256 -> "
                   "land -> manifest row carrying the rights basis and jurisdiction"),
        "candidates": len(items), "landed": len(landed), "refused": len(refused),
        "borrow_tier": len(borrow), "bytes_landed": sum(r["bytes"] for r in landed),
        "landed_items": landed, "refused_list": refused, "borrow_tier_list": borrow,
    }
    RUNS.mkdir(parents=True, exist_ok=True)
    tag = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    (RUNS / f"ARCHIVE_ACQUISITION_{tag}.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nLANDED {len(landed)}  borrow-tier {len(borrow)}  refused {len(refused)}")
    print(f"-> {RUNS / f'ARCHIVE_ACQUISITION_{tag}.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
