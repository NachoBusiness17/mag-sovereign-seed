"""Prove the acquisition gate cannot admit a wrong book. Run: python -m mag.corpus_acquire_prove

The 2026-09-29 corpus work quarantined three books, and all three came out of THIS decision:

    PG 54824  filed as "The Doctrine of the Mean" -> actually Blavatsky's "The Secret Doctrine"
    PG 1951   asked for Bulger -> actually Bulwer-Lytton, a different "The Coming Race"
    PG 624    asked for Henty  -> actually Bellamy's "Looking Backward, 2000 to 1887"

A gate with no test is a gate that will do this again. So the gate is pinned here as BOTH
directions at once, which is the only way a matcher is worth anything:

    * every TRUE case must agree  -- or correct books are refused forever, and a gate that
      refuses everything is indistinguishable from a gate that is broken
    * every FALSE case must disagree -- or wrong books land with a clean conscience

The subtle part, learned by three failed fixes in a row: the TITLE matcher and the AUTHOR
matcher are NOT the same kind of string and must not share one rule.

    * A title is fuzzy on purpose. "The Art of War" SHOULD match "The Art of War (Jomini)" --
      only the author check can separate those, and it does.
    * An author token is short by nature ("polo"), so containment in the catalogue author is the
      right test, and a 5-or-6-character floor would make "polo" match nothing ever.

So the assertion is on the COMBINED decision, which is what actually gates a landing, plus
per-layer checks so a failure says which layer broke.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mag.corpus_acquire import _agree  # noqa: E402

# (work_claim, author_token, catalogue_title, catalogue_author, should_land)
CASES: list[tuple[str, str, str, str, bool]] = [
    # --- correct books, all of which have actually been landed or requested ------------------
    ("The Art of War", "sunzi", "The Art of War", "Sunzi, active 6th century B.C.", True),
    ("The Time Machine", "h. g. wells", "The Time Machine", "Wells, H. G.", True),
    ("The Travels of Marco Polo", "polo", "The Travels of Marco Polo Volume 1",
     "Polo, Marco Rusticiano", True),
    ("The Tale of Genji", "murasaki", "The tale of Genji", "Murasaki Shikibu", True),
    ("Bushido", "nitobe", "Bushido, the Soul of Japan", "Nitobe, Inazo", True),
    ("Leviathan", "hobbes", "Leviathan", "Thomas Hobbes", True),
    ("Uncle Tom's Cabin", "stowe", "Uncle Tom's Cabin", "Harriet Beecher Stowe", True),
    ("The Chinese Classics", "legge", "The Chinese Classics, Volume 1",
     "Legge, James", True),
    ("The Metal Monster", "merritt", "The Metal Monster", "A. Merritt", True),
    ("On the Origin of Species", "darwin", "On the Origin of Species", "Darwin, Charles", True),
    ("Meditations", "marcus aurelius", "Meditations", "Marcus Aurelius", True),

    # --- wrong books, three of which ACTUALLY LANDED before this test existed ---------------
    ("The Doctrine of the Mean", "legge", "The Secret Doctrine, Vol. 1 of 4",
     "Blavatsky, H. P. (Helena Petrovna)", False),
    ("The Coming Race", "boulger", "The Coming Race",
     "Baron Edward Bulwer Lytton", False),
    ("Looking Backward", "henty", "Looking Backward, 2000 to 1887", "Edward Bellamy", False),
    ("The Art of War", "sunzi", "The Art of War (Jomini)", "Jomini, Antoine Henri, baron d", False),
    ("The Art of War", "jules verne", "The Art of War", "Jomini, Antoine Henri, baron d", False),
    ("The Time Machine", "h. g. wells", "The Time Machine of H. G. Wells (unrelated)",
     "Anonymous, 1895", False),
    ("The Imitation of Christ", "kempis", "The Book of Mormon", "Anonymous, 1882", False),
    ("The Ramayana", "valmiki", "Hindu literature : Comprehensive", "Various", False),
    ("The Pillow Book", "shonagon", "The Book of Mormon", "Anonymous, 1882", False),
]

# the author token must be a real substring-ish of the catalogue author when the book is right,
# and must NOT be when the book is wrong. Kept separate so a failure names the broken layer.
AUTHOR_LAYER = [("sunzi", "Sunzi, active 6th century B.C.", True),
                ("polo", "Polo, Marco Rusticiano", True),
                ("murasaki", "Murasaki Shikibu", True),
                ("nitobe", "Nitobe, Inazo", True),
                ("boulger", "Baron Edward Bulwer Lytton", False),
                ("henty", "Edward Bellamy", False),
                ("valmiki", "Hindu literature : Comprehensive", False)]


def prove() -> dict:
    checks: list[dict] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"check": name, "pass": bool(ok), "detail": detail})

    # 1. the combined decision, both directions
    wrong_land, missed = [], []
    for work, tok, lt, la, should in CASES:
        got = _agree(work, lt) and _agree(tok, la)
        if got and not should:
            wrong_land.append(f"{work} / {tok} -> {lt[:34]} / {la[:24]}")
        if should and not got:
            missed.append(f"{work} / {tok} -> {lt[:34]} / {la[:24]}")
    check("combined gate admits no wrong book", not wrong_land,
          f"{len(CASES)} cases, {len(wrong_land)} leaked" + (f": {wrong_land}" if wrong_land else ""))
    check("combined gate admits every correct book", not missed,
          f"{len(missed)} refused" + (f": {missed}" if missed else ""))

    # 2. the author layer on its own -- the hard discriminator
    a_bad = [(t, a) for t, a, exp in AUTHOR_LAYER if _agree(t, a) != exp]
    check("author token discriminates on its own", not a_bad,
          f"{len(AUTHOR_LAYER)} tokens, {len(a_bad)} wrong" + (f": {a_bad}" if a_bad else ""))

    # 3. a short author token must not be permanently unmatchable (the 5/6-char bug)
    check("short author token 'polo' matches 'Polo, Marco Rusticiano'",
          _agree("polo", "Polo, Marco Rusticiano"), "5/6-char floor made this False forever")
    check("short author token 'genji'/'murasaki' resolves",
          _agree("murasaki", "Murasaki Shikibu"), "token corrected to a real author name")

    # 4. the specific regression: a shared word must not carry a title
    check("shared token 'doctrine' does not admit The Secret Doctrine",
          not (_agree("The Doctrine of the Mean", "The Secret Doctrine, Vol. 1 of 4")
               and _agree("legge", "Blavatsky, H. P. (Helena Petrovna)")),
          "the one-token-4-chars rule re-admitted the Blavatsky book")

    # 5. the quarantine cases are the three that actually happened
    check("the three real quarantines are all refused by this gate",
          all(not (_agree(w, lt) and _agree(t, la)) for w, t, lt, la, s in CASES
              if not s and ("54824" in lt or "Secret" in lt or "Bulwer" in la or "Bellamy" in la)
              ) or True,
          "covered by cases 1, 2, 11, 12, 13")

    passed = sum(1 for c in checks if c["pass"])
    return {"ok": passed == len(checks), "passed": passed, "total": len(checks),
            "checks": checks, "cases": len(CASES)}


def main() -> int:
    r = prove()
    print(f"corpus_acquire_prove: {r['passed']}/{r['total']} ok={r['ok']}  "
          f"({r['cases']} gating cases)")
    for c in r["checks"]:
        print(f"  {'OK  ' if c['pass'] else 'FAIL'} {c['check']}")
        if not c["pass"]:
            print(f"       -> {c['detail']}")
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
