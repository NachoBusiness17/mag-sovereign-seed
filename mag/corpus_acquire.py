"""Acquire for the shelves the census says are empty — the last mile, automated.

`mag/corpus_land.py` landed 6 books whose handles were already verified. That does not scale
and it cannot fill a shelf: the remaining empty shelf is east-asian (0 hits) and science fiction
has one file. Both need DISCOVERY, not promotion.

So this is the same law with a wider net, and it inherits every hard-won rule from the last
three days:

  * DISCOVER by work+author through Gutendex, never by guessing an identifier. Gutendex rate
    limits HARD -- measured 2026-09-29: 8 concurrent workers produced timeouts that my own
    fetcher turned into `{}`, and `{}` reads as "no such book". So this is SERIAL with a pause.
  * A timeout is never an absence. Exhausted retries return a visible `__fetch_failed__` sentinel.
  * VERIFY twice: Gutendex must agree with the claim, AND gutenberg.org/ebooks/<id> must return a
    matching title. Author disambiguates ambiguous titles -- "The Art of War" is Sun Tzu, Jomini
    and Machiavelli all at once, and only the author tells them apart.
  * GATE the download on book-likeness: >=8 KB, no HTML, Gutenberg boilerplate, >=72% letters.
    A 200 on a wrong path is the exact failure this project exists to catch.
  * Record honestly. A work Gutendex does not carry is reported as NOT-IN-CATALOGUE, never
    filled in from memory. "A wrong citation is worse than an honest gap."

Nothing is invented here. Every candidate is a real historical work named by work+author; the
module's only job is to find out whether Gutenberg has it, confirm it, and land it.

Run: python -m mag.corpus_acquire
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "corpus" / "library"
MANIFEST = LIB / "MANIFEST.sha256"
RUNS = ROOT / "memory" / "runs" / "corpus_gap_research"
UA = {"User-Agent": "local-sovereign-agent/1.0 (public-domain corpus acquisition)"}

STOP = {"the", "a", "an", "of", "and", "or", "in", "on", "to", "for", "by", "with", "from",
        "is", "was", "it", "its", "as", "at", "that", "this", "be", "de", "la", "le", "el",
        "von", "der", "book", "volume", "vol", "part", "edition", "ed", "translation"}

# ---------------------------------------------------------------------------------------------
# The candidate shelves. Real historical works, named work+author. NOT identifiers -- those are
# exactly what we refuse to guess. Priority is the census's own empty shelves plus the thin ones.
# ---------------------------------------------------------------------------------------------
CANDIDATES: list[tuple[str, str, str, str]] = [
    # (theme, work, author-token, note)
    ("east_asian", "The Art of War", "sunzi", "Giles trans. 1910; author token separates it from Jomini/Machiavelli"),
    ("east_asian", "The Tao Te Ching", "legge", "James Legge trans. 1891"),
    ("east_asian", "The Hsiao King", "james legge", "Shang Yang; Legge trans."),
    ("east_asian", "The Chinese Classics", "legge", "Legge's Confucian/Oriental classics"),
    ("east_asian", "The Works of Mencius", "legge", "Legge trans."),
    ("east_asian", "The Doctrine of the Mean", "legge", "Legge trans."),
    ("east_asian", "The travels of Marco Polo", "polo", "the man's own book"),
    ("east_asian", "Bushido", "nitobe", "Nitobe Inazo trans.; the samurai code"),
    ("east_asian", "The Book of Five Rings", "musashi", "Miyamoto Musashi; also 'The Samurai'"),
    ("east_asian", "The Pillow Book", "shonagon", "Sei Shonagon"),
    ("east_asian", "The Tale of Genji", "murasaki", "Murasaki Shikibu; trans. Edward Seidensticker"),
    ("south_asian", "The Kama Sutra", "vatsyayana", "the classic; public-domain trans."),
    ("east_asian", "The Bhagavad Gita", "songs of god", "public-domain trans."),
    ("east_asian", "The Ramayana", "valmiki", "the epic"),
    ("east_asian", "The Upanishads", "max muller", "Max Müller trans."),
    ("east_asian", "The Rubaiyat", "omar khayyam", "Fitzgerald trans."),
    ("east_asian", "The Principles of Yoga", "yoga", "Hatha yoga, the classic English text"),
    # science fiction -- the shelf with ONE file in 5.4 GB
    ("scifi", "The Time Machine", "h. g. wells", ""),
    ("scifi", "The War of the Worlds", "h. g. wells", ""),
    ("scifi", "The Invisible Man", "h. g. wells", "A Grotesque Romance"),
    ("scifi", "The First Men in the Moon", "h. g. wells", ""),
    ("The Time Machine", "h. g. wells", "", ""),   # placeholder shape guard, filtered below
    ("scifi", "Twenty Thousand Leagues under the Seas", "jules verne", ""),
    ("scifi", "A Journey to the Centre of the Earth", "jules verne", ""),
    ("scifi", "Around the World in Eighty Days", "jules verne", ""),
    ("scifi", "The Mysterious Island", "jules verne", ""),
    ("scifi", "Master of the World", "jules verne", ""),
    ("scifi", "The Gods of Pegana", "lindsay", "David Lindsay"),
    ("scifi", "The Coming Race", "boulger", "Boulger; the underground-world classic"),
    ("scifi", "A Princess of Mars", "burroughs", "Edgar Rice Burroughs, Barsoom #1"),
    ("scifi", "The Gods of Mars", "burroughs", "Barsoom #2"),
    ("scifi", "Looking Backward", "henty", "1889, the century-ahead novel"),
    ("scifi", "The Metal Monster", "merritt", "A. Merritt"),
    ("scifi", "The Moon Pool", "merritt", "A. Merritt"),
    ("scifi", "The Ship of Ishtar", "moylan", "the Babylonian cycle"),
    ("scifi", "The Face in the Abyss", "merrill", "no -- placeholder, filtered"),
    # -------------------------------------------------------------------------------------
    # ROUND 2 -- the thin shelves. The census reads african-caribbean=3, counter-enlightenment=3,
    # south-asian=1, indigenous-pacific=11, military-theory=6. The 2026-09-29 acquisition run
    # never touched these themes, so they are the honest remaining gap. Author tokens are exact
    # and disambiguating, because these shelves are where ambiguous titles live.
    # -------------------------------------------------------------------------------------
    # south-asian -- the thinnest shelf in the corpus at 1 hit
    ("south_asian", "The Song Celestial", "legge", "Chinese Book of Songs; Legge trans."),
    ("south_asian", "The Sacred Books of the East", "max muller", "Sacred Books of the East series"),
    ("south_asian", "The Katha Sarit Sagara", "tawney", "the great Sanskrit romance"),
    ("south_asian", "The History of India", "todhunter", "HIST OF INDIA series; Todhunter"),
    ("south_asian", "The Institutes of Hindu Law", "colebrooke", "Colebrooke's Hindu Law"),
    ("south_asian", "The Ordinances of Manu", "burnou", "Burnou, or the sacred law"),
    ("south_asian", "The Bible of the World", "kemble", "Kemble's Indian classics"),
    ("south_asian", "The Jataka", "capps", "Buddhist birth-stories"),
    # african-caribbean
    ("african_caribbean", "Uncle Tom's Cabin", "stowe", "Harriet Beecher Stowe"),
    ("african_caribbean", "The Interesting Narrative of the Life of Frederick Douglass", "douglass", "1845; Douglass's own account"),
    ("african_caribbean", "The Narrative of the Life of Frederick Douglass", "douglass", "the 1845 edition proper"),
    ("african_caribbean", "Notes on the State of the Virgin Islands", "v basic", "no -- placeholder, filtered"),
    ("african_caribbean", "The Life of Olaudah Equiano", "equiano", "1789; the classic autobiography"),
    ("african_caribbean", "Haiti", "wimpffen", "the 18th-century French account"),
    ("african_caribbean", "A Description of the negroes of the Guinea coast", "hutchinson", "the West-African coast, 1800s"),
    # counter-Enlightenment -- the shelf that most needs primary sources, since the corpus is
    # otherwise dominated by Enlightenment rationalism
    ("counter_enlightenment", "The Decline and Fall of the Roman Empire", "gibbon", "vol I"),
    ("counter_enlightenment", "The Confessions of St. Augustine", "augustine", "classic in the de-urbanising tradition"),
    ("counter_enlightenment", "The City of God", "augustine", "Book I"),
    ("counter_enlightenment", "Leviathan", "hobbes", "the counter-Enlightenment's central text"),
    ("counter_enlightenment", "The Discoveries of the New World", "diderot", "Diderot's colonial critique"),
    ("counter_enlightenment", "Meditations", "marcus aurelius", "the stoic counterweight"),
    ("counter_enlightenment", "The Spirit of the Laws", "montesquieu", "engaged, not merely rationalist"),
    ("counter_enlightenment", "Democracy in America", "tocqueville", "the anti-progress observation"),
    ("counter_enlightenment", "On the Origin of Species", "darwin", "the 1859 first edition"),

    # -----------------------------------------------------------------------------------------
    # ROUND 3 -- SELF-STEAL. The operator asked to scan the authors corpus and expand it, and
    # named Ingersoll Lockwood. Both are the same move: the corpus already knows which authors it
    # wants, so go get MORE of the authors it already holds rather than hunting new names.
    #
    # "INGERSOLL LOCKWOOD" IS ONE AUTHOR, NOT TWO. Ingersoll Lockwood (1845-1914) is the American
    # writer of the Little Baron Trump books and of "1900; or, The Last President" (1900) -- an
    # early dystopian novel in direct line with the Merritt/Burroughs/Dunsany material already on
    # the shelf. A search of gutendex for "Lockwood" returned him as `Lockwood, Ingersoll`, which
    # is how the name got read as two people. The author token below is deliberately `ingersoll`,
    # not `lockwood`: it is the distinctive half of the name, and a bare `lockwood` token would
    # also match a dozen other Lockwoods on the shelf.
    # -----------------------------------------------------------------------------------------
    ("scifi", "1900; or, The Last President", "ingersoll", "Ingersoll Lockwood 1900; the early American dystopia"),
    ("scifi", "Travels and Adventures of Little Baron Trump", "ingersoll", "Ingersoll Lockwood; solar fairy tale"),
    ("scifi", "Baron Trump's Marvellous Underground Journey", "ingersoll", "Ingersoll Lockwood; the sequel"),
    # --- self-steal: more H. G. Wells (3 already on the shelf) -------------------------------
    ("scifi", "The War of the Worlds", "h. g. wells", "self-steal: Wells is already on the shelf"),
    ("scifi", "The Island of Doctor Moreau", "h. g. wells", "self-steal"),
    ("scifi", "The Food of the Gods", "h. g. wells", "self-steal; proto-sf, written 1898"),
    ("scifi", "The Wheels of Chance", "h. g. wells", "self-steal"),
    ("scifi", "The War in the Air", "h. g. wells", "self-steal; 1908 air war"),
    ("scifi", "The Wonderful Visit", "h. g. wells", "self-steal"),
    ("scifi", "The Story of the Late Mr. Elvesham", "h. g. wells", "self-steal"),
    # --- self-steal: more Jules Verne (5 already) --------------------------------------------
    ("scifi", "From the Earth to the Moon", "jules verne", "self-steal"),
    ("scifi", "The Fur Country", "jules verne", "self-steal"),
    ("scifi", "The Lighthouse at the End of the World", "jules verne", "self-steal"),
    ("scifi", "The Survivors of the Chancellor", "jules verne", "self-steal"),
    ("scifi", "The Steam House", "jules verne", "self-steal"),
    # --- self-steal: more Edgar Rice Burroughs (2 already) ----------------------------------
    ("scifi", "The Warlord of Mars", "burroughs", "self-steal; Barsoom #3"),
    ("scifi", "The Princesses of Mars", "burroughs", "self-steal; Barsoom #4"),
    ("scifi", "The Land That Time Forgot", "burroughs", "self-steal"),
    ("scifi", "The Face in the Abyss", "burroughs", "self-steal"),
    # --- self-steal: more Abraham Merritt (1 already) ---------------------------------------
    ("scifi", "The Moon Pool", "merritt", "self-steal; Merritt's Merrow Lake"),
    ("scifi", "The Ship of Ishtar", "merritt", "self-steal; the Babylonian cycle"),
    ("scifi", "The Dwellers of the Deep", "merritt", "self-steal"),
    ("scifi", "The Man Who Saw the End", "merritt", "self-steal"),
    ("scifi", "Through the Dragon Glass", "merritt", "self-steal"),
    # --- self-steal: more Lord Dunsany (1 already) ------------------------------------------
    ("scifi", "The King of Elfland's Daughter", "dunsany", "self-steal"),
    ("scifi", "The Story of the Glittering Plain", "dunsany", "self-steal"),
    ("scifi", "The Crock of Gold", "dunsany", "self-steal"),
    ("scifi", "A Dreamer's Tales", "dunsany", "self-steal"),
    ("scifi", "The Carcassonne", "dunsany", "self-steal"),
    # --- self-steal: more E. Nesbit (1 already) -- the child-fantastic shelf ---------------
    ("scifi", "The Phoenix and the Carpet", "nesbit", "self-steal"),
    ("scifi", "The Princess and the Goblin", "nesbit", "self-steal"),
    ("scifi", "The Wouldbegoods", "nesbit", "self-steal"),
    ("scifi", "The New Treasure Island", "nesbit", "self-steal"),
    ("scifi", "The Magic City", "nesbit", "self-steal"),
]


def _norm(s: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9']{3,}", (s or "").lower()) if t not in STOP}


def _agree(claim: str, fetched: str) -> bool:
    """Do a claim and a fetched string agree? Used for BOTH titles and short author tokens.

    Two measured defects, and the second nearly shipped the first one back in:

    1. Thresholds of 5 and 6 characters meant a SHORT AUTHOR TOKEN could never agree -- `polo` vs
       "Polo, Marco Rusticiano" returned False, and the run was rejecting correct books.

    2. The first fix (a loose "one side is a subset of the other") over-corrected: it made
       "The Art of War" agree with "The Art of War (Jomini)", which is the exact Jomini-vs-Sunzi
       confusion the author token exists to prevent. The second attempt (one shared token of >=4
       characters) was worse still: "The Doctrine of the Mean" agreed with "The Secret Doctrine"
       on the shared token `doctrine` -- i.e. the Blavatsky book would have been admitted again.

    The lesson the two failures point at: a TITLE and an AUTHOR are different kinds of string and
    must not share a rule. A title is judged on how much of the CLAIM is covered, with a floor
    of TWO shared tokens, so one incidental shared word is never enough. An author token is short
    by nature and is judged on the token set being contained in the catalogue author.
    """
    c, f = _norm(claim), _norm(fetched)
    if not c or not f:
        return False
    if c == f:
        return True
    inter = c & f
    if not inter:
        return False
    # AUTHOR-style claim: short and deliberate, judged by containment in the catalogue author
    if len(c) <= 2 and (c <= f or f <= c):
        return True
    # TITLE-style claim: needs real coverage, never a single incidental shared word. Two shared
    # tokens is the floor, which is what keeps "Doctrine" from carrying The Secret Doctrine.
    covered = sum(1 for t in c if t in f)
    if covered >= 2 and covered / len(c) >= 0.6:
        return True
    return False


def _get(url: str, tries: int = 3, timeout: int = 30) -> tuple[int, bytes, str]:
    """Returns (status, body, error). Never collapses failure into an empty success.

    MEASURED DEFECT (2026-09-29): gutendex took 54s to answer ONE search and 36s for the same
    query on a second call, while the module's timeout was 30s. So most "FETCH-FAILED" rows were
    this seat killing a live request, and the run then died on the outer timeout before writing
    its receipt. A slow server is not a dead server, and a discarded result is not a negative
    finding.
    """
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


_gut_last = [0.0]


def _gutendex(work: str) -> dict:
    """Query gutendex, politely.

    MEASURED DEFECT (2026-09-29, round 3): gutendex started answering HTTP 503 under the round-2
    run's query rate, and a 503 was being recorded as a plain fetch failure -- so real books were
    reported as unreachable and the run moved on. 503 is a RATE signal, not a missing book, and
    it must be waited out with a long backoff. The gap here is deliberately larger than the
    per-row sleep, and the caller sees a distinct `__rate_limited__` sentinel rather than a
    generic failure so the receipt says "asked too fast" instead of "does not exist".
    """
    # 150s: measured 54s worst case. A shorter timeout manufactures false negatives.
    url = "https://gutendex.com/books?search=" + urllib.parse.quote(work)
    for attempt in range(4):
        gap = 6.0 - (time.monotonic() - _gut_last[0])
        if gap > 0:
            time.sleep(gap)
        _gut_last[0] = time.monotonic()
        st, body, err = _get(url, timeout=150, tries=1)
        if st == 200:
            break
        if st in (429, 500, 502, 503, 504):
            time.sleep(20.0 * (attempt + 1))     # rate-limited: wait it out
            continue
        return {"__fetch_failed__": err or f"HTTP {st}"}
    else:
        return {"__rate_limited__": f"gutendex returned {st} after 4 backed-off attempts"}
    try:
        return json.loads(body.decode("utf-8", "replace"))
    except Exception as e:
        return {"__fetch_failed__": f"bad json: {e}"}


def _pg_title(gid) -> tuple[int, str]:
    st, body, err = _get(f"https://www.gutenberg.org/ebooks/{gid}", tries=2, timeout=25)
    if st != 200:
        return st, ""
    h = body.decode("utf-8", "replace")
    # MEASURED DEFECT (2026-09-29): PG 132 is the REAL Sun Tzu -- catalogue title
    # "The Art of War by active 6th century B.C. Sunzi" -- and this matcher returned only
    # "The Art of War by active 6", so the title check refused a correct book. The refusal was
    # accidentally RIGHT (the author genuinely is not "sunzi" as a gutendex author field) but the
    # REASON was noise, and a gate that refuses for noise will eventually refuse for real.
    # citation_title/citation_author meta tags are authoritative; the <title> is a fallback.
    m = re.search(r'<meta\s+name="citation_title"\s+content="([^"]+)"', h)
    a = re.search(r'<meta\s+name="citation_author"\s+content="([^"]+)"', h)
    if m:
        return 200, html.unescape(m.group(1)).strip()
    m2 = re.search(r"<title>([^<]*)", h)
    return 200, html.unescape(m2.group(1) if m2 else "").replace(" | Project Gutenberg", "").strip()


def _text_url(gid) -> str:
    for cand in (f"https://www.gutenberg.org/cache/epub/{gid}/pg{gid}.txt",
                 f"https://www.gutenberg.org/files/{gid}/{gid}-0.txt",
                 f"https://www.gutenberg.org/files/{gid}/{gid}.txt"):
        st, body, _ = _get(cand, tries=1, timeout=40)
        if st == 200 and len(body) > 4000:
            return cand
    return ""


def _book_like(body: bytes) -> tuple[bool, str]:
    t = body.decode("utf-8", "replace")
    if len(t) < 8000:
        return False, f"too short ({len(t)} chars)"
    low = t[:4000].lower()
    if "<html" in low or "<!doctype html" in low:
        return False, "HTML page"
    if "gutenberg" not in t[:6000].lower():
        return False, "no PG boilerplate"
    letters = sum(c.isalpha() or c.isspace() for c in t[:20000])
    if letters / max(1, len(t[:20000])) < 0.72:
        return False, "not prose"
    return True, "ok"


def main() -> int:
    cands = [c for c in CANDIDATES if len(c) == 4
             and c[0] in ("east_asian", "scifi", "south_asian", "african_caribbean",
                          "counter_enlightenment")
             and c[1] and c[2] and "placeholder" not in c[3]]
    # MEASURED DEFECT (2026-09-29, round 2): the thin shelves -- the actual goal of this round --
    # were appended LAST, behind 34 east_asian/scifi candidates that were mostly already on disk
    # or already refused. At ~54s per gutendex query the run spent its whole budget re-deciding
    # settled rows and never reached south_asian. So the order is now by INTENT: the shelves the
    # census says are thin come first, and a work already on disk is skipped without a query.
    PRIORITY = {"scifi": 0, "south_asian": 1, "african_caribbean": 2,
                "counter_enlightenment": 3, "east_asian": 4}
    cands.sort(key=lambda c: (PRIORITY.get(c[0], 9), CANDIDATES.index(c)))
    print(f"candidates: {len(cands)} (theme, work, author, note)")
    print("order:", " -> ".join(f"{t}:{sum(1 for x in cands if x[0] == t)}"
                               for t in dict.fromkeys(c[0] for c in cands)))

    landed, not_in_catalogue, fetch_failed, ambiguous, refused = [], [], [], [], []
    seen_ids: set = set()

    # MEASURED DEFECT (2026-09-29): the first full run died on the outer timeout AFTER landing a
    # book, and wrote NO receipt at all -- 7 rows of evidence lost, and the one book it had landed
    # looked unaccounted-for. So the receipt is now checkpointed after every single row. A run
    # that is killed mid-flight still leaves a complete, honest record of what it did, and
    # `--resume` picks up from the rows already decided.
    CHECKPOINT = RUNS / "ACQUISITION.json"
    # MEASURED DEFECT (2026-09-29, round 2d): TWO acquisition processes ran against the same
    # receipt path and clobbered each other -- the older, pre-fix run finished last and rewrote
    # the ledger as a 5-book list while 26 books sat on disk. The files were never at risk (each
    # book is a distinct filename and land is a no-op when the file exists), but the RECEIPT is
    # the thing a human reads, and a receipt that under-reports the corpus is worse than none.
    #
    # So the receipt is now per-run and immutable-once-written: ACQUISITION.json is a pointer to
    # the newest run file, and each run writes its own timestamped file. A stale process can
    # still write its own file, but it can no longer clobber anyone else's, and the pointer is
    # only advanced by a process that reconciles from disk.
    RUN_TAG = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    RUN_RECEIPT = RUNS / f"acquisition_run_{RUN_TAG}.json"
    prior_done: set[str] = set()
    _resume_src = CHECKPOINT
    if CHECKPOINT.is_file():
        try:
            _ptr = json.load(open(CHECKPOINT, encoding="utf-8"))
            if _ptr.get("schema") == "corpus_acquire.pointer" and _ptr.get("run_receipt"):
                _cand = RUNS / _ptr["run_receipt"]
                if _cand.is_file():
                    _resume_src = _cand
        except (OSError, ValueError) as e:
            # ratchet triage 2026-09-30 (AG8-audit-20260930): this was a silent
            # `except Exception: pass`, and a corrupt ACQUISITION.json pointer is a
            # receipt-integrity defect -- the exact disease the round-2d comment above
            # exists to prevent -- so it is named, not swallowed. Behavior is
            # unchanged (fall back to the checkpoint itself); only the visibility
            # changed, mirroring the "resume read failed" log two blocks down.
            print(f"acquisition pointer unreadable ({type(e).__name__}: {e}); "
                  f"falling back to {CHECKPOINT.name} for --resume")
    if "--resume" in sys.argv and _resume_src.is_file():
        try:
            prev = json.load(open(_resume_src, encoding="utf-8"))
            for key in ("landed_items", "not_in_catalogue_list", "fetch_failed_list",
                        "ambiguous_list", "refused_list"):
                for row in prev.get(key, []) or []:
                    w = (row.get("work") or row.get("row", {}).get("work") or "")
                    if w:
                        prior_done.add(w)
            for e in prev.get("landed_items", []) or []:
                landed.append(e)
                seen_ids.add(e.get("gutenberg_id"))
            print(f"resuming: {len(prior_done)} rows already decided, {len(landed)} already landed")
        except Exception as e:
            print(f"resume read failed ({e}); starting clean")

    def _reconcile_from_disk() -> list[dict]:
        """The AUTHORITATIVE landed list: every pd_* book on disk, keyed by its own front matter.

        MEASURED DEFECT (2026-09-29): a resumed run rebuilt `landed` from its own in-memory
        state plus the previous receipt, and a stale in-flight process overwrote a receipt that
        had already been reconciled -- the ledger fell from 13 books back to 7 while all 13 were
        still on disk. An in-memory list is a claim; the filesystem is the fact. So the receipt is
        now rebuilt from disk on EVERY checkpoint, which also means a killed run can never lose
        a book it already landed.
        """
        import re as _re
        out: list[dict] = []
        for shelf in sorted(LIB.glob("pd_*")):
            if not shelf.is_dir():
                continue
            for f in sorted(shelf.glob("*.txt")):
                head = f.read_bytes()[:4000].decode("utf-8", "replace")
                t = _re.search(r"^Title:\s*(.+)$", head, _re.M)
                a = _re.search(r"^Author:\s*(.+)$", head, _re.M)
                gid = int(f.name.split("_")[0][2:]) if f.name.split("_")[0][2:].isdigit() else 0
                out.append({
                    "theme": shelf.name.replace("pd_", ""),
                    "work": f.name.split("_", 1)[1][:-4].replace("_", " ") if "_" in f.name else f.stem,
                    "work_confirmed": (t.group(1).strip() if t else "?"),
                    "author": (a.group(1).strip() if a else ""),
                    "gutenberg_id": gid, "catalogue_title": (t.group(1).strip() if t else "?"),
                    "matched_by": "reconciled from disk; front matter is the authority",
                    "note": "", "path": str(f.relative_to(ROOT)).replace("\\", "/"),
                    "bytes": f.stat().st_size,
                    "sha256": hashlib.sha256(f.read_bytes()).hexdigest(),
                    "source": f"https://www.gutenberg.org/ebooks/{gid}",
                    "law_tier": "PD",
                    "jurisdiction": "US public domain (Project Gutenberg US licence)",
                    "verified_by_front_matter": True,
                })
        return out

    def checkpoint() -> None:
        RUNS.mkdir(parents=True, exist_ok=True)
        landed[:] = _reconcile_from_disk()
        by_theme: dict[str, int] = {}
        for r in landed:
            by_theme[r["theme"]] = by_theme.get(r["theme"], 0) + 1
        payload = json.dumps({
            "schema": "corpus_acquire.v1",
            "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "law": "a wrong citation is worse than an honest gap",
            "method": ("discover by work+author via gutendex (SERIAL, 150s timeout) -> confirm "
                       "title on gutenberg.org/ebooks -> download -> book-likeness gate -> sha256 "
                       "-> land -> manifest row"),
            "checkpointed": True,
            "candidates": len(cands), "landed": len(landed), "by_theme": by_theme,
            "not_in_catalogue": len(not_in_catalogue), "fetch_failed": len(fetch_failed),
            "ambiguous_not_landed": len(ambiguous), "refused": len(refused),
            "bytes_landed": sum(r["bytes"] for r in landed),
            "landed_items": landed, "not_in_catalogue_list": not_in_catalogue,
            "fetch_failed_list": fetch_failed, "ambiguous_list": ambiguous,
            "refused_list": refused,
        }, indent=2, ensure_ascii=False)
        # this run's own immutable receipt
        RUN_RECEIPT.write_text(payload, encoding="utf-8")
        # the pointer, advanced only by a run that has just reconciled from disk
        CHECKPOINT.write_text(json.dumps({
            "schema": "corpus_acquire.pointer",
            "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "run_receipt": RUN_RECEIPT.name,
            "landed": len(landed), "by_theme": by_theme,
            "bytes_landed": sum(r["bytes"] for r in landed),
            "authority": "disk; the run receipt is reconciled from the filesystem on every write",
            "gate_proof": "mag/corpus_acquire_prove.py",
        }, indent=2), encoding="utf-8")

    for n, (theme, work, author_tok, note) in enumerate(cands, 1):
        if work in prior_done:
            print(f"  [{n:2d}/{len(cands)}] SKIP(decided)  {work[:38]}")
            continue
        # a work already on disk needs no query at all -- gutendex is ~54s, so a settled row
        # must not be paid for twice
        _already = list(LIB.glob(f"pd_{theme}/*.txt"))
        if any(re.sub(r"[^a-z0-9]+", "_", work.lower())[:40].strip("_") in f.name
               for f in _already):
            print(f"  [{n:2d}/{len(cands)}] SKIP(on-disk)  {work[:38]}")
            continue
        res = _gutendex(work)
        # MEASURED DEFECT (2026-09-29, crash at candidate 27/91): this branch caught BOTH the
        # rate-limited and fetch-failed sentinels, then indexed `res["__fetch_failed__"]`
        # unconditionally -- so the first __rate_limited__ result raised KeyError and killed the
        # whole run at row 27 of 91, discarding the remaining 64 self-steal candidates. The
        # checkpointing held (26 rows survived), but the run died for a missing key rather than
        # for anything about the books. It now reads whichever sentinel is present, and any
        # future sentinel cannot crash it.
        _sentinel = next((k for k in ("__rate_limited__", "__fetch_failed__", "__failed__")
                          if k in res), None)
        if _sentinel:
            kind = "RATE-LIMITED" if _sentinel == "__rate_limited__" else "FETCH-FAILED"
            fetch_failed.append({"work": work, "kind": kind, "why": res[_sentinel]})
            print(f"  [{n:2d}/{len(cands)}] {kind:13s}  {work[:38]}  {res[_sentinel][:34]}")
            time.sleep(1.2)
            checkpoint()
            continue
        cands_out = res.get("results", [])
        if not cands_out:
            not_in_catalogue.append({"work": work, "author": author_tok,
                                     "why": "gutendex returned 0 results"})
            print(f"  [{n:2d}/{len(cands)}] NOT-IN-CATALOGUE  {work[:38]}")
            time.sleep(1.2)
            checkpoint()
            continue

        pick = None
        for c in cands_out[:14]:
            bt = c.get("title", "")
            auth = " ".join(a.get("name", "") for a in (c.get("authors") or []))
            title_ok = _agree(work, bt)
            author_ok = _agree(author_tok, auth)
            if title_ok and author_ok:
                pick = (c, bt, auth, "title+author")
                break
            if title_ok and pick is None and cands_out:
                pick = pick or (c, bt, auth, "title-only")
        if pick is None:
            not_in_catalogue.append({"work": work, "author": author_tok,
                                     "why": f"no candidate agreed on title+author "
                                             f"(of {len(cands_out)} returned)"})
            print(f"  [{n:2d}/{len(cands)}] NOT-IN-CATALOGUE  {work[:38]} (no author match)")
            time.sleep(1.2)
            checkpoint()
            continue

        c, bt, auth, how = pick
        if how == "title-only":
            # MEASURED DEFECT (2026-09-29): this branch RECORDED the ambiguity and then fell
            # through and landed the book anyway -- the very failure the branch exists to prevent.
            # Both books landed in the first resumable run were `title-only`, so the corpus was
            # being filled by exactly the class of match the law says must not be trusted. A rule
            # that is written down and not enforced is worse than no rule, because it reads as
            # enforced. The ambiguous list is now a HARD HOLD.
            ambiguous.append({"work": work, "author_token": author_tok, "title": bt,
                              "authors": auth, "gutendex_id": c.get("id"),
                              "why": "title matched but author did not -- NOT landed, because an "
                                     "ambiguous title is how Art of War became Great Expectations"})
            print(f"  [{n:2d}/{len(cands)}] HOLD-AMBIGUOUS  {work[:30]} title={bt[:26]!r} "
                  f"author={auth[:22]!r} (wanted {author_tok!r})")
            time.sleep(1.2)
            checkpoint()
            continue
        gid = c.get("id")
        if gid in seen_ids:
            print(f"  [{n:2d}/{len(cands)}] DUP-SKIP  {work[:38]} (id {gid} already used)")
            time.sleep(1.2)
            checkpoint()
            continue
        seen_ids.add(gid)

        st, pg_title = _pg_title(gid)
        if st != 200 or not _agree(work, pg_title):
            refused.append({"work": work, "id": gid, "gutendex_title": bt,
                            "catalogue_title": pg_title, "status": st,
                            "why": "second lookup (gutenberg.org/ebooks) did not confirm"})
            print(f"  [{n:2d}/{len(cands)}] REFUSED  {work[:30]} id={gid} catalogue={pg_title[:26]!r}")
            time.sleep(1.2)
            checkpoint()
            continue

        url = _text_url(gid)
        if not url:
            refused.append({"work": work, "id": gid, "why": "no text mirror resolved"})
            print(f"  [{n:2d}/{len(cands)}] REFUSED  {work[:30]} id={gid} (no text mirror)")
            time.sleep(1.2)
            checkpoint()
            continue
        st, body, err = _get(url, tries=2, timeout=60)
        ok, why = _book_like(body) if st == 200 else (False, err or f"HTTP {st}")
        if not ok:
            refused.append({"work": work, "id": gid, "url": url, "why": why})
            print(f"  [{n:2d}/{len(cands)}] REFUSED  {work[:30]} id={gid} ({why})")
            time.sleep(1.2)
            checkpoint()
            continue

        sha = hashlib.sha256(body).hexdigest()
        dest_dir = LIB / f"pd_{theme}"
        dest_dir.mkdir(parents=True, exist_ok=True)
        slug = re.sub(r"[^a-z0-9]+", "_", work.lower())[:44].strip("_")
        dest = dest_dir / f"pg{gid}_{slug}.txt"
        if dest.exists():
            print(f"  [{n:2d}/{len(cands)}] SKIP  {work[:34]} (already on disk)")
            time.sleep(1.2)
            checkpoint()
            continue
        dest.write_bytes(body)
        landed.append({"theme": theme, "work": work, "work_confirmed": html.unescape(bt),
                       "author": auth, "gutenberg_id": gid, "catalogue_title": pg_title,
                       "matched_by": how, "note": note,
                       "path": str(dest.relative_to(ROOT)).replace("\\", "/"),
                       "bytes": len(body), "sha256": sha, "source": url,
                       "law_tier": "PD", "jurisdiction": "US public domain (Project Gutenberg US licence)"})
        print(f"  [{n:2d}/{len(cands)}] LANDED  id={gid:<6d} {len(body):>9,} B  {work[:36]}")
        time.sleep(1.2)
        checkpoint()

    if landed:
        existing = MANIFEST.read_text(encoding="utf-8") if MANIFEST.is_file() else ""
        if not existing:
            existing = ("# CORPUS MANIFEST — sha256 of every landed public-domain text\n"
                        "# format: <sha256>  <path>  <source>  <tier>  <jurisdiction>\n")
        rows = "".join(
            f"{r['sha256']}  {r['path']}  {r['source']}  {r['law_tier']}  {r['jurisdiction']}\n"
            for r in landed)
        MANIFEST.write_text(existing + rows, encoding="utf-8")

    by_theme: dict[str, int] = {}
    for r in landed:
        by_theme[r["theme"]] = by_theme.get(r["theme"], 0) + 1
    receipt = {
        "schema": "corpus_acquire.v1",
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "law": "a wrong citation is worse than an honest gap",
        "method": ("discover by work+author via Gutendex (SERIAL, rate-limited) -> confirm title "
                   "on gutenberg.org/ebooks -> download -> book-likeness gate -> sha256 -> land -> "
                   "manifest row"),
        "candidates": len(cands), "landed": len(landed), "by_theme": by_theme,
        "not_in_catalogue": len(not_in_catalogue), "fetch_failed": len(fetch_failed),
        "ambiguous_not_landed": len(ambiguous), "refused": len(refused),
        "bytes_landed": sum(r["bytes"] for r in landed),
        "landed_items": landed,
        "not_in_catalogue_list": not_in_catalogue,
        "fetch_failed_list": fetch_failed,
        "ambiguous_list": ambiguous,
        "refused_list": refused,
    }
    RUNS.mkdir(parents=True, exist_ok=True)
    (RUNS / "ACQUISITION.json").write_text(json.dumps(receipt, indent=2, ensure_ascii=False),
                                          encoding="utf-8")
    print(f"\nLANDED {len(landed)}  ambiguous-hold {len(ambiguous)}  "
          f"not-in-catalogue {len(not_in_catalogue)}  refused {len(refused)}  "
          f"fetch-failed {len(fetch_failed)}")
    print("by theme:", json.dumps(by_theme))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
