"""Regression gate for the lead-verification and salvage logic.

Every case here is a real row from the 2026-09-28 pack or a real Gutenberg catalogue title.
The point is that BOTH failure directions are pinned:
  * a true match must be promoted   (a gate that rejects everything is not a gate)
  * a wrong handle must be refused  (a gate that accepts everything is worse than none)

Measured defect this file exists to prevent: `agree()` scored "The Art of War" against itself
as False, because the title normalises to {art, war} and every token fell under the 5-char
distinctive floor. A one-line fix plus this file keeps it fixed.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mag.corpus_salvage import agree, claimed_work  # noqa: E402

# (claim, fetched_title, expected) -- real catalogue titles pulled from gutenberg.org
AGREE_CASES = [
    ("The Book of the Courtier", "The Courtier", True),
    ("The Art of War", "The Art of War", True),                     # the regression above
    ("The Decameron", "The Decameron", True),
    ("The Consolation of Philosophy", "The Consolation of Philosophy", True),
    ("The Life of Benvenuto Cellini", "The Autobiography of Benvenuto Cellini", True),
    ("The Art of War", "Great Expectations", False),                # real wrong handle
    ("The Book of the Courtier", "Unconscious Comedians", False),   # real wrong handle
    ("The Travels of Sir John Mandeville", "Grass of Parnassus", False),
    ("Essays", "Romeo and Juliet", False),
    ("The Book of the City of Ladies", "Night and Day", False),
]

# (claim_context, expected (work, author) or None) -- real bullet shapes from the pack
PARSE_CASES = [
    ("- **The Book of the Courtier** – Baldassare Castiglione (d. 1529) – 1242",
     ("The Book of the Courtier", "Baldassare Castiglione")),
    ("- **The Art of War** – Niccolò Machiavelli (d. 1527) – 1400",
     ("The Art of War", "Niccolò Machiavelli")),
    ("- **The Consolation of Philosophy** – Boethius – 11436",
     ("The Consolation of Philosophy", "Boethius")),
]


def prove() -> dict:
    fails = []
    for claim, fetched, expected in AGREE_CASES:
        got = agree(claim, fetched)
        if got != expected:
            fails.append({"fn": "agree", "claim": claim, "fetched": fetched,
                          "expected": expected, "got": got})
    for ctx, expected in PARSE_CASES:
        got = claimed_work(ctx)
        if got != expected:
            fails.append({"fn": "claimed_work", "ctx": ctx, "expected": expected, "got": got})
    total = len(AGREE_CASES) + len(PARSE_CASES)
    return {
        "ok": not fails, "passed": total - len(fails), "total": total,
        "failed": fails,
        "law": "a lead is promoted by title-match, never by status-match",
    }


if __name__ == "__main__":
    import json
    r = prove()
    print(json.dumps(r, indent=2, ensure_ascii=False))
    raise SystemExit(0 if r["ok"] else 1)
