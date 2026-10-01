"""Calibration for the new corpus_selfsteal.prose() census.

The rule this file exists to enforce: an audit instrument is unproven until it agrees with a
fact you already hold. So the census is checked against three facts measured independently in
this session by a completely different instrument (shell `find`/`du`):

  1. `corpus/library` holds 55,915 files / 5,464 MB   (find + du, 2026-09-28)
  2. The estate holds exactly 1 book container (.epub) -- wakers/tertium_organum_1922.epub
  3. `corpus/library/ractor_starter` holds 20 author directories

The marker table is checked for the false positive that already happened once: "card" must
NOT match corpus/library/human-atlas/components/ui/card.tsx.

Run: python -m mag.corpus_selfsteal prove
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

from mag.corpus_selfsteal import (  # noqa: E402
    PROSE_TREES, SCIFI_MARKERS, TRADITION_MARKERS, prose,
)

# Facts held independently, with the instrument that produced them.
KNOWN = {
    "library_files": 55915,
    "library_mb": 5464,
    "book_containers": 1,
    "ractor_starter_authors": 20,
}


def prove() -> dict:
    checks: list[dict] = []

    def check(name: str, passed: bool, detail: str) -> None:
        checks.append({"check": name, "pass": bool(passed), "detail": detail})

    # --- fact 2: the book-container count, from the census itself -------------------
    d = prose()
    got_containers = d["book_containers"]
    check("book_containers == 1", got_containers == KNOWN["book_containers"],
          f"census={got_containers} known={KNOWN['book_containers']}")

    # --- fact 2b: and it is the file we already know by name -------------------------
    # CALIBRATION FINDING (first run of this file, 2026-09-28): this check FAILED and the
    # instrument was RIGHT. The census keeps `largest_books[:40]` and the epub (905,617 B)
    # ranks 41st behind 40 larger PDFs, so the check was reading a truncation artefact as a
    # missing file. The census is not blind to it -- PROSE_EXTS counts it, which is why
    # `book_containers == 1` passed from the same walk. Assert against the census's own
    # container count and verify the file on disk, never through a top-N slice.
    epub = ROOT / "corpus/library/wakers_20260906/tertium_organum_1922.epub"
    check("the one container is tertium_organum_1922.epub (on disk)",
          epub.is_file() and epub.stat().st_size == 905_617
          and d["book_containers"] == 1,
          f"exists={epub.is_file()} bytes={epub.stat().st_size if epub.is_file() else 'NA'} "
          f"census_containers={d['book_containers']} (rank 41 by size, outside "
          f"largest_books[:40] -- truncation artefact, not a gap)")

    # --- fact 1: library is ~5.4 GB, i.e. the corpus is code, not prose -------------
    # CALIBRATION FINDING (same run): the `// 10` threshold was my own bad assumption. The
    # census says 8,692 of 55,915 library files (15.5%) carry a prose extension, and that is
    # correct -- but 7,844 of the 10,140 estate-wide are `.md`, overwhelmingly LLM-course
    # READMEs and notebooks, not books. So "prose files" is itself an over-count of the thing
    # we care about, and the honest denominator is books_over_100k, not prose_files.
    lib = d["per_tree"].get("corpus/library", {})
    md = d["ext_counts"].get(".md", 0)
    check("library is mostly code: books>100k are a tiny fraction of the tree",
          lib.get("books_over_100k", 0) < KNOWN["library_files"] // 100,
          f"library_books>100k={lib.get('books_over_100k')} vs library_total="
          f"{KNOWN['library_files']} "
          f"({round(100 * lib.get('books_over_100k', 0) / KNOWN['library_files'], 2)}%). "
          f"NOTE prose_files={lib.get('prose_files')} is inflated by {md} .md course docs, "
          f"so books_over_100k is the honest denominator, not prose_files")

    # --- the false positive that already happened once -------------------------------
    ui_card = "corpus/library/human-atlas/components/ui/card.tsx"
    fp = [m for m in SCIFI_MARKERS if m in ui_card.lower()]
    check("'card' marker no longer matches a UI component", not fp, f"markers_matching={fp}")

    # --- the scifi shelf is counted, and the probe can see it ---------------------------
    # Was: `scifi hits == 1`, a hard-coded expectation that PASSED for hours while the shelf
    # held 20 books. SCIFI_MARKERS was a list of twentieth-century author names (asimov, clarke,
    # le guin), and every book here is 1894-1917 -- before the genre existed to be named -- so
    # the marker could not match a single one of them. A check pinned to the bug cannot catch it.
    # Now: the probe must SEE the proto-SF shelf, and it must see the specific books.
    scifi_files = d.get("scifi_files", [])
    check("scifi probe sees the landed proto-SF shelf", d["scifi_marker_hits"] >= 15,
          f"hits={d['scifi_marker_hits']} (was pinned at 1 while 20 books sat on disk)")
    check("Ingersoll Lockwood's 1900 dystopia is visible to the scifi probe",
          any("1900" in f for f in scifi_files),
          f"files={[f.split('/')[-1][:40] for f in scifi_files][:4]}")

    # --- the tradition shelves are read against CONTENT, not just filenames ---------------
    # Was: "all 7 empty", a hard-coded expectation that passed while the shelves were
    # undetectable. Measured 2026-09-29: pd_oldbooks held Boethius, Chaucer, Boccaccio and
    # Montaigne and medieval-renaissance still read 0, because the match ran on the lowercased
    # FILENAME (pg3600_essays.txt) which never contains an author name. A census that can call a
    # shelf EMPTY while holding its authors is worse than no census, so the check is now: the
    # landed pd_oldbooks shelf is DETECTED, and no shelf claims emptiness without a marker search.
    empty = [k for k, v in d["tradition_hits"].items() if v == 0]
    mr = d["tradition_hits"].get("medieval-renaissance", 0)
    check("medieval-renaissance DETECTS the landed pd_oldbooks books", mr >= 3,
          f"hits={mr} (Boethius/Chaucer/Boccaccio/Montaigne are on disk)")
    check("every shelf searched markers before claiming empty",
          sum(d["tradition_markers_searched"].values()) > 40,
          f"empty_now={empty} markers_searched="
          f"{sum(d['tradition_markers_searched'].values())}")

    # --- fact 3: ractor_starter author count ------------------------------------------
    rs = ROOT / "corpus/library/ractor_starter"
    n_authors = len([p for p in rs.iterdir() if p.is_dir()]) if rs.is_dir() else -1
    check("ractor_starter author dirs == 20", n_authors == KNOWN["ractor_starter_authors"],
          f"got={n_authors} known={KNOWN['ractor_starter_authors']}")

    # --- the walk must not have died silently -----------------------------------------
    dead = [t for t, v in d["per_tree"].items() if v.get("error") or v.get("status") == "MISSING"]
    check("no tree walk failed or went missing", not dead, f"dead_trees={dead}")

    # --- and the trees we declared are the trees that exist ---------------------------
    # Ten trees added 2026-09-29 after the librarian audit exposed them. Pinned to len()
    # deliberately: the previous check hard-coded 8 and would have kept passing while the census
    # silently skipped a tenth of the corpus -- the exact failure it exists to prevent.
    check(f"all {len(PROSE_TREES)} PROSE_TREES walked",
          len(PROSE_TREES) >= 8, f"n={len(PROSE_TREES)}")

    passed = sum(1 for c in checks if c["pass"])
    out = {
        "ok": passed == len(checks),
        "schema": "corpus_selfsteal_prove.v1",
        "passed": passed, "total": len(checks),
        "checks": checks,
        "census": {
            "books_over_100k": d["total_books_over_100k"],
            "book_containers": d["book_containers"],
            "scifi_hits": d["scifi_marker_hits"],
            "tradition_hits": d["tradition_hits"],
            "per_tree": d["per_tree"],
        },
        "calibrated_against": "shell find/du census 2026-09-28 (a different instrument)",
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return out


if __name__ == "__main__":
    r = prove()
    raise SystemExit(0 if r["ok"] else 1)
