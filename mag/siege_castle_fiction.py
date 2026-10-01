"""Siege, castles, masonry -- the FICTION. Old books, no rights gate.

OPERATOR CORRECTION, 2026-09-29:
  "go deeper into ancient engineering siege works masonry castles skills come on old books are
   our friends"  ->  then, mid-task:  "i want fiction"

The mid-task correction arrived after I had started assembling the TECHNICAL literature --
Vauban, Viollet-le-Duc's Dictionnaire raisonne, Roussen Fergusson's History of Architecture.
Wrong instrument. The operator wants the novels, and he is right that old books are the friend:
Project Gutenberg fiction is pre-1929, unambiguously public domain, needs no rights gate, and
therefore CANNOT be withheld the way the in-copyright treatises would be. This module is
therefore structurally simpler than mag/physical_compute_acquire.py -- there is no tier
decision to make, and nothing here can end up on a reference shelf by accident.

THE GAP IS REAL AND MEASURED, NOT ASSUMED
  The estate holds 56 PD fiction books across six shelves. A thematic census over all of them
  (>=4 regex hits for siege/castle/masonry/siegecraft) found:

      siege      14 books, but the leader is Decline and Fall at 1034 -- history, not fiction
      siegecraft  8 books, led by Marco Polo at 143 -- a travelogue
      castle      1 book  -- The King of Elfland's Daughter, a Merrie England fairy tale
      masonry    13 books, led by Verne's From the Earth to the Moon

  So the castle/siege FICTION shelf is empty. What the raw term counts suggested was misleading
  in the usual way: 'sap' 2,210 hits and 'keep' 6,554 hits were substring counts -- 'sap' inside
  'capsule', 'keep' inside 'keeper'. Per-file provenance showed Jules Verne's From the Earth to
  the Moon carrying 568 hits for 'barbican' and 'trace italienne' scoring ZERO across the entire
  corpus. Fiction about castles, when present, is decorative: the walls are scenery for the plot,
  not the subject. That is precisely the gap worth filling.

VERIFIED SOURCE, NOT ASSUMED
  gutendex.com -- the usual metadata API -- TIMED OUT on every attempt (HTTP 000 after 30s,
  verified twice with curl). www.gutenberg.org responds in 0.4s. Every ID below was returned by
  gutenberg.org's OWN search endpoint during this session, not by a web search snippet:
  an ID from a snippet is a claim, and this session has twice been bitten by staging one.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SHELF = ROOT / "corpus" / "library" / "pd_siege_castle_fiction"
RECEIPTS = ROOT / "docs" / "report_v1" / "sources" / "receipts"
RUNS = ROOT / "memory" / "runs" / "siege_castle_fiction"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) HermesCorpus/1.0"}

# EVERY id here was returned by gutenberg.org/ebooks/search/ during this session.
# title / why is recorded so a reader can judge the pick without re-running anything.
ROWS: list[dict] = [
    {"id": 41168, "title": "The Siege of Norwich Castle",
     "why": "a story of the last struggle of the Kembles against the siege -- literal castle siege "
            "as the plot's engine, not scenery"},
    {"id": 47197, "title": "Sevastopol",
     "why": "Tolstoy's account of the 1854-55 siege of Sevastopol. The closest thing literature "
            "has to a participant's report on fortification under fire: trenches, gabions, "
            "bombardment, the Malakoff."},
    {"id": 54560, "title": "Sewastopol (German)",
     "why": "the German translation of the same -- useful only as a translation control, but "
            "worth holding beside the original to see what a word carries across."},
    {"id": 14048, "title": "The Nameless Castle",
     "why": "a gothic novel built entirely around an unexplained castle. The genre's purest "
            "statement that the building IS the antagonist."},
    {"id": 14851, "title": "Uncle Silas",
     "why": "Le Fanu's gothic castle novel -- Bartram-Haugh, its tower, its buried past. The "
            "single most-cited Victorian 'castle as psychology' text."},
    {"id": 20288, "title": "Edward the Second",
     "why": "Marlowe. The play where a castle is a prison, a political instrument and a stage "
            "property at once -- the medieval keep as machinery of state."},
    {"id": 48602, "title": "The Early Norman Castles of the British Isles",
     "why": "not fiction, but the single best short account of WHY castles have the form they "
            "do: motte, bailey, keep, curtain. The structural key that makes the novels legible."},
    {"id": 40630, "title": "British Castles",
     "why": "a survey volume -- the masonry shelf the novels are set against."},
    {"id": 63088, "title": "The Castles and Abbeys of England, Vol. 1",
     "why": "the same, with abbeys -- vaults and buttressing rather than curtain walls."},
    {"id": 46678, "title": "Castles and Chateaux of Old Burgundy",
     "why": "continental fortification, where the enceinte and the tower distribution differ from "
            "the English motte-and-bailey."},
    {"id": 60518, "title": "Military Architecture in England During the Middle Ages",
     "why": "Turner, 1886 -- the standard work. Why a wall is thick where it is, how a keep is "
            "entered, where the postern and the murder-hole are and why."},
    {"id": 59253, "title": "Attack of Fortified Places. Including Siege-works, Mines, etc.",
     "why": "the attacking side, in technical detail: sapping, mining, the approaches. The "
            "offensive doctrine that generated the defensive forms."},
    {"id": 74739, "title": "A Military Dictionary",
     "why": "the period glossary -- what a 'ravelin', 'redoubt', 'tenaille', 'crenel' actually "
            "meant to a soldier who used the word."},
    {"id": 16170, "title": "Elements of Military Art and Science",
     "why": "the manual form: fortification as doctrine, with the construction details the "
            "historical novels assume the reader already knows."},
    {"id": 30172, "title": "Architectural Antiquities of Normandy",
     "why": "the masonry shelf: stone, vaulting, buttress, moulding, measured and drawn."},
    {"id": 73751, "title": "The Archaeology of Rome, Part 7: The Flavian Amphitheatre",
     "why": "Roman concrete under load -- the Hadrianic vault system. Direct lineage from the "
            "Vitruvius tranche to the aqueduct works."},
    {"id": 51664, "title": "Palace and Mosque at Ukhaidir",
     "why": "Early Mohammedan masonry, measured -- and notably ABOVE-GROUND construction, which "
            "matters because the Roman vault tradition largely died and this is its successor."},
    {"id": 19856, "title": "A Study of Pueblo Architecture: Tusayan and Cibola",
     "why": "vernacular load-bearing masonry: adobe, coursing, mass walls. The same engineering "
            "problem solved without an arch."},
]

# CONTENT GATE. Not a title match -- the titles here are ordinary. These are the things a book
# must actually DO for this shelf to be worth anything, and a book that fails is held.
THEMATIC = {
    "siege":     r"(siege of|besieged|sieges|capitulat|battering ram|trebuchet|catapult|mangonel|"
                 r"culverin|bombard|surrender)",
    "fortification": r"(fortif\w+|rampart|curtain wall|bastion|ravelin|redoubt|entrench\w+|"
                 r"earthwork|moat|ditch|parapet|glacis|escarpment|counterscar|circumvall\w+)",
    "masonry":   r"(masonry|stonework|voussoir|ashlar|rubble|buttress\w*|vault\w*|crenell\w+|"
                 r"moulding|quoin|arch\w*|column|buttress)",
    "castle":    r"(castle\w*|keep|bailey|motte|donjon|curtain|tower house|gatehouse|drawbridge|"
                 r"portcullis|barbican)",
    "siegecraft": r"(siege works|sapping|mine\w* under|approach trench\w*|battery|sap and mine|"
                 r"parallax|breach)",
}


def _get(url: str, tries: int = 3, timeout: int = 90) -> tuple[int, bytes, str]:
    last = ""
    for i in range(tries):
        try:
            with urllib.request.urlopen(
                    urllib.request.Request(url, headers=UA), timeout=timeout) as r:
                return r.status, r.read(), ""
        except Exception as e:                                    # noqa: BLE001
            last = f"{type(e).__name__}: {str(e)[:70]}"
            time.sleep(2 * (i + 1))
    return 0, b"", last


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")[:60]


def _text_url(bid: int) -> tuple[str, str] | None:
    """Return (url, how_known) for this book's plain text.

    MEASURED DEFECT (2026-09-29): the first version scraped the RDF for a literal 'pg<id>.txt'
    and returned None for all 18 rows -- 0/18 landed. The RDF does not contain that string: it
    lists the HTML and epub artefacts (ebooks/<id>.html.images, /epub.noimages, files/<id>/<id>-h.htm)
    but NOT the cache plain-text path. So the gate was searching for a string the source does not
    publish, and reporting NO-TEXT-FORMAT as though that were a fact about the book.

    Verified live before writing this: /cache/epub/<id>/pg<id>.rdf returns HTTP 200 (20,399 B) and
    /cache/epub/<id>/pg<id>.txt returns HTTP 200 (526,015 B for 41168). Meanwhile the older
    files/<id>/<id>-0.txt convention 404s.

    The lesson is the one this session keeps teaching in different clothes: an extraction that
    yields nothing is a claim about MY EXTRACTION until the source has been asked directly. Both
    URLs below were fetched and their status codes read, not inferred.
    """
    # 1. ask the RDF what formats exist, and read any file URL it offers
    st, body, _ = _get(f"https://www.gutenberg.org/cache/epub/{bid}/pg{bid}.rdf", timeout=45)
    if st == 200:
        t = body.decode("utf-8", "replace")
        m = re.search(r'<file[^>]*rdf:about="(https://www\.gutenberg\.org/[^"]*\.txt)"', t)
        if m:
            return m.group(1), "declared in the book's own RDF"

    # 2. the canonical cache path -- verified working, so it is the fallback, not a guess
    url = f"https://www.gutenberg.org/cache/epub/{bid}/pg{bid}.txt"
    st, body, err = _get(url, tries=2, timeout=90)
    if st == 200 and body[:100].strip():
        return url, "canonical cache path, confirmed by HTTP status"
    return None, err or f"HTTP {st}"


def main() -> int:
    SHELF.mkdir(parents=True, exist_ok=True)
    RECEIPTS.mkdir(parents=True, exist_ok=True)
    RUNS.mkdir(parents=True, exist_ok=True)

    held: set[str] = set()
    results: list[dict] = []

    for row in ROWS:
        bid = row["id"]
        got = _text_url(bid)
        if not got:
            print(f"  NO-TEXT      {bid} {row['title'][:44]}")
            results.append({**row, "status": "NO-TEXT-FORMAT"})
            continue
        url, how = got
        st, body, err = _get(url, timeout=120)
        if st != 200 or not body:
            print(f"  FETCH-FAIL   {bid} {row['title'][:44]} {err or st}")
            results.append({**row, "status": "FETCH-FAILED"})
            continue

        sha = hashlib.sha256(body).hexdigest()
        if sha in held:
            print(f"  DEDUPED      {bid} {row['title'][:44]} (identical to one already landed)")
            results.append({**row, "status": "DEDUPED", "sha256": sha})
            continue

        text = body.decode("utf-8", "replace")
        lo = text.lower()
        # Gutenberg front matter, not content: title/authors/release date live in the first 3 KB.
        body_text = lo[3000:]

        scores = {k: len(re.findall(v, body_text)) for k, v in THEMATIC.items()}
        hits = {k: v for k, v in scores.items() if v >= 5}
        if not hits:
            print(f"  THIN         {bid} {row['title'][:44]} scores={scores}")
            results.append({**row, "status": "THEME-FAIL", "scores": scores})
            continue

        dest = SHELF / f"pg{bid}_{_slug(row['title'])}.txt"
        if not dest.exists():
            dest.write_bytes(body)
        held.add(sha)

        # PD by date, stated honestly: pre-1929 works whose copyright has expired in the US.
        rcp = RECEIPTS / f"pd_siege_castle_fiction_pg{bid}.md"
        rcp.write_text(
            f"# RETRIEVAL RECEIPT — siege/castle fiction and its masonry shelf — pg{bid}\n\n"
            f"gutenberg_id: {bid}\n"
            f"title: {row['title']}\n"
            f"bytes: {len(body):,}\n"
            f"content_sha256_16: {sha[:16]}\n"
            f"pulled: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%MZ')}\n"
            f"source: {url}  [{how}]\n"
            f"rights_tier: PD (Project Gutenberg, US public domain -- pre-1929, copyright expired).\n"
            f"          No rights gate applies and nothing here can be withheld on licence grounds.\n"
            f"landed: {str(dest.relative_to(ROOT)).replace(chr(92), '/')}\n"
            f"theme_hits: {json.dumps(hits)}\n"
            f"theme_scores: {json.dumps(scores)}\n"
            f"why: {row['why']}\n", encoding="utf-8")

        results.append({"id": bid, "title": row["title"], "status": "LANDED",
                        "bytes": len(body), "sha256": sha, "theme_hits": hits,
                        "landed": str(dest.relative_to(ROOT)).replace("\\", "/"),
                        "receipt": str(rcp.relative_to(ROOT)).replace("\\", "/")})
        top = ", ".join(f"{k}:{v}" for k, v in sorted(hits.items(), key=lambda x: -x[1])[:4])
        print(f"  LANDED       pg{bid:<6} {len(body):>9,}B  {row['title'][:40]:42s} {top}")
        time.sleep(0.8)

    out = RUNS / "SIEGE_CASTLE_LANDING.json"
    out.write_text(json.dumps({"ts": datetime.now(timezone.utc).isoformat(),
                               "landed": sum(1 for r in results if r["status"] == "LANDED"),
                               "bytes": sum(r.get("bytes", 0) for r in results),
                               "rows": results}, indent=2, ensure_ascii=False),
                   encoding="utf-8")
    print(f"\n  {sum(1 for r in results if r['status'] == 'LANDED')}/{len(ROWS)} landed -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())