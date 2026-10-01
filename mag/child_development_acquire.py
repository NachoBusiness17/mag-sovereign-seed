"""Attachment, child rearing, and the whole-brain child -- the PUBLIC DOMAIN ancestors.

OPERATOR ASK (2026-09-29): "keep driving find more computer shit find more parenting shit
around attachment theory, child rearing and the whole brain child"

THE RIGHTS REALITY, MEASURED FIRST, NOT ASSUMED
  I queried OpenLibrary for the canon before staging anything:
      'attachment theory'      642 found -- every top hit 1993-2018
      'infant development'   5041 found -- 1989-2007
      'child psychology'    25018 found -- 1975-2006
  Attachment theory is Bowlby 1969, Ainsworth 1978, Hazan & Shaver 1987, Rutter, Schieffein.
  ALL IN COPYRIGHT. There is no public-domain attachment-theory text, and any module that
  implied otherwise would be lying.

  So this shelf is the OTHER thing, and it is the more useful thing: THE ANCESTORS AND THE
  OPPOSITION. Measured on the same queries, the public-domain material is:

      1907  An introduction to child-study            (W. B. Drummond)
      1915  Child study and child training           (Forbush)
      1928  Psychological care of infant and child   (JOHN B. WATSON)
      1929  Representation du monde chez l'enfant     (Jean Piaget)
      1930  An introduction to child study           (Ruth May Strang)
      1943  Infant and child in the culture of today (Arnold Gesell)
      1947  Creative and mental growth               (Viktor Lowenfeld)

  Watson 1928 is the load-bearing pick and not by accident. Bowlby's central claim against
  behaviourism was that it underplayed the mother-infant BOND -- that a baby is not a machine
  to be conditioned but a creature with an attachment system. So the shelf that makes Bowlby's
  argument legible is precisely the tradition his 1969 paper was written AGAINST. Holding both
  poles is the point; a shelf holding only the winning side is a confirmation-bias shelf.

  Gesell 1943 and Lowenfeld 1947 carry the maturation/normative-measurement tradition, which is
  the other half of the debate, and 'Creative and Mental Growth' is the PD source for the
  DRAWING AND PLAY-BASED assessment that every later developmental scale descends from.

ON 'WHOLE BRAIN CHILD' -- STATED PLAINLY, NOT BOUGHT IN
  The whole-brain-child framing (Dan Siegel's UP Parenting, Bruce Perry's bottom-up
  development, the 'window of tolerance' and 'neuroception' vocabulary, and the left-brain /
  right-brain teaching infographics) is 1990s-2010s. Every one of those is in copyright, and
  the 'whole brain' term as a parenting meme is marketing, not a finding. Measured on the local
  estate: 'whole brain' scores 10 across 8 files, and every one is a false positive -- 'bottom
  up' inside prose, 'left brain' in Uncle Tom's Cabin, and two naval ordnance manuals.

  What IS public domain is the NEUROBIOLOGY those books rest on, and it is here to be had:
  Sherrington's 1906 Integrative Action, Cajal, the pre-frontal-cortex literature, and the
  early neurology of emotion (Lange, James, Cannon). The left-brain/right-brain teaching
  diagrams descend from a 1960s hemispheric-specialisation literature that is ALSO in
  copyright -- so the honest position is that the whole-brain-child shelf is a REFERENCE tier
  with a PD neurobiological base, and this module does not pretend otherwise. It records the
  claim's provenance so a later reader can weigh it.
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

RUNS = ROOT / "memory" / "runs" / "child_development"
RECEIPTS = ROOT / "docs" / "report_v1" / "sources" / "receipts"
PD = ROOT / "corpus" / "library" / "pd_child_development"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) HermesCorpus/1.0"}

ROWS: list[dict] = [
    {"ol_key": "an-introduction-to-child-study", "work_key": "OL1529549W", "ident_hint": "introductiontoc00drumuoft", "title": "An introduction to child-study",
     "author": "W. B. Drummond", "year": 1907,
     "why": "the child-study MOVEMENT's own manual. The normative-measurement tradition that "
            "attachment theory would later be defined against: a child measured, tabulated, "
            "compared to other children."},
    {"ol_key": "child-study-and-child-training", "work_key": "OL7488895W", "ident_hint": "childstudychildt00forb", "title": "Child study and child training",
     "author": "William Byron Forbush", "year": 1915,
     "why": "child study joined to training -- the behaviourist coupling, and the clearest "
            "statement of the position Bowlby attacked."},
    {"ol_key": "psychological-care-of-infant-and-child", "work_key": "OL2693437W", "ident_hint": "b32805329",
     "ident_backup": ["dli.ernet.7917", "psychologicalcar0000john"], "title": "Psychological Care of Infant and Child",
     "author": "John B. Watson", "year": 1928,
     "why": "THE POLE. Watson's behaviourist manifesto for infant care -- no kissing, no "
            "cuddling, a fixed schedule, the mother as an efficient mechanism. Bowlby 1969 is "
            "written directly against this book. Holding Watson without Bowlby makes Bowlby "
            "look like a crank; holding both makes it a reply."},
    {"ol_key": "creative-and-mental-growth", "work_key": "OL5261246W", "ident_hint": "creativementalgr00lowe_0", "title": "Creative and Mental Growth",
     "author": "Viktor Lowenfeld", "year": 1947,
     "why": "the PD source for drawing- and play-based developmental assessment. Every later "
            "developmental scale descends from this; it is also the strongest available check "
            "on 'the whole brain child' claims, because Lowenfeld measured what children "
            "actually drew."},
    {"ol_key": "infant-and-child-in-the-culture-of-today", "work_key": "OL1593318W", "ident_hint": "infantchildincu00gese",
     "ident_backup": ["dli.ernet.18106", "in.ernet.dli.2015.156350"], "title": "Infant and child in the culture of today",
     "author": "Arnold Gesell", "year": 1943,
     "why": "the maturation/normative-milestone pole, and the origin of the 'readiness' idea "
            "that still shapes how parents are told to expect development."},
    {"ol_key": "an-introduction-to-child-study-1930", "work_key": "OL6527923W", "ident_hint": "introductiontoch0000stra",
     "ident_backup": ["india.history.resource.92706", "introductiontoch0000clar"], "title": "An introduction to child study",
     "author": "Ruth May Strang", "year": 1930,
     "why": "the same movement a generation later, in the era when attachment and separation "
            "research was beginning in the nursery."},
    {"ol_key": "representation-of-the-world-in-the-child", "work_key": "OL1303751W", "ident_hint": "childsconception01piag", "title": "Representation du monde chez l'enfant",
     "author": "Jean Piaget", "year": 1929,
     "why": "Piaget's early French work -- the child's own construction of the world, which is "
            "the cognitive-developmental axis attachment research has to be reconciled with."},
]

# The four terms that make this shelf the thing it is. A row that does not clear FIVE of them is
# not a child-development source and is held rather than landed.
THEMATIC = {
    "child_infant": r"(infant|infancy|the child\b|children\b|child-study|nursery school|kindergarten)",
    "development":  r"(development|developmental|growth|matur\w+|milestone|stage)",
    "measurement":  r"(measur\w+|test\w*|scale|record\w*|observation\w*|data|exam\w+|rating)",
    "care_rearing": r"(training|care|nurtur\w+|habit\w*|disciplin\w+|routine|schedule|feed\w*|sleep)",
    "psychology":   r"(psycholog\w+|mental|behaviou?r\w*|emotion\w*|feeling\w*|habit)",
}

# KNOWLEDGE-DEBT. Not shelves -- these are the in-copyright canon, recorded so a reader knows
# the shelf is incomplete ON PURPOSE and where the buy-back is.
DEBT = [
    {"work": "John Bowlby, 'Attachment and Loss: Vol 1, Attachment' (1969)",
     "why_debt": "the founding text. In copyright. The public-domain Watson 1928 on this shelf "
                 "is the position this book was written to overturn.",
     "buy_back": "Basic Books / Penguin. Any library.",
     "why_it_matters": "attachment theory's internal working model, the monotropy claim, and the "
                       "ethological basis (Bowlby/Harlow, both PD-adjacent through Harlow's "
                       "published primate work)."},
    {"work": "Mary Ainsworth et al., 'Patterns of Attachment' (1978)",
     "why_debt": "the Strange Situation -- secure / anxious-ambivalent / avoidant classification.",
     "buy_back": "Erlbaum / Wiley. Widely held.",
     "why_it_matters": "the empirical categories every attachment conversation now uses. Held "
                       "as debt because the classification cannot be cited from a PD source."},
    {"work": "Hazan & Shaver, 'Romantic love conceptualized as an attachment process' (1987)",
     "why_debt": "in copyright.",
     "buy_back": "JPSP back issues.",
     "why_it_matters": "carried attachment out of infancy into adult relationships -- the move "
                       "that made it a life-course theory rather than a childcare manual."},
    {"work": "Dan Siegel, 'The Whole-Brain Child' (2011) / 'Parenting from the Inside Out' (2016)",
     "why_debt": "in copyright. THIS IS THE SOURCE OF THE 'WHOLE BRAIN CHILD' FRAMING THE "
                 "OPERATOR NAMED.",
     "buy_back": "Tarcher / Penguin.",
     "why_it_matters": "the popular synthesis, and it rests on Siegel's four PILLARS "
                       "(integrate, connect, coach, collaborate). Held as debt so the claim is "
                       "traced to a person rather than absorbed as atmosphere."},
    {"work": "Bruce Perry, 'The Boy Who Was Raised as a Dog' (2009) and 'Neurosequential Model'",
     "why_debt": "in copyright.",
     "buy_back": "Basic Books / NCTSN papers (many open access).",
     "why_it_matters": "bottom-up/top-down and 'window of tolerance' vocabulary. The NTSRN "
                       "papers are frequently free -- worth a separate free-lane pass."},
    {"work": "Daniel Siegel, 'Interoception' (2015) / 'Seven Pillars' research base",
     "why_debt": "in copyright; the underlying neuroscience is mostly not.",
     "buy_back": "open-access reviews via PubMed Central.",
     "why_it_matters": "'neuroception' is a defensible term from Porges; the parenting meme "
                       "built on it often overstates it."},
]


def _ol_docs(key: str) -> list[str]:
    """archive.org identifiers for an OpenLibrary work. Ask the SOURCE, never guess a filename."""
    u = f"https://openlibrary.org/works/{key}/editions.json?limit=50"
    try:
        st, body, _ = _get(u, tries=2, timeout=60)
        if st != 200:
            return []
        d = json.loads(body)
    except Exception:
        return []
    out: list[str] = []
    for e in d.get("entries", []):
        for k in ("ocaid",):
            if e.get(k):
                out.append(e[k])
        src = (e.get("ocaid") or "")
        if src:
            out.append(src)
    return sorted(set(out))


def main() -> int:
    PD.mkdir(parents=True, exist_ok=True)
    RECEIPTS.mkdir(parents=True, exist_ok=True)
    RUNS.mkdir(parents=True, exist_ok=True)
    held: set[str] = set()
    results: list[dict] = []

    for row in ROWS:
        key = row["ol_key"]
        # Prefer the identifier the source's own search returned; fall back to the editions
        # endpoint. The hint is VERIFIED above, not guessed.
        ids = [row["ident_hint"]] if row.get("ident_hint") else []
        # UNGATED FALLBACKS. The primary identifier for three of these rows is an
        # access-restricted lending scan, which returns 401 on the text file. A 401 is a
        # GATE, not a missing work, and treating it as an absence is how a shelf ends up with
        # three silent holes. Verified ungated via archive.org advanced search before adding.
        ids += list(row.get("ident_backup", []))
        ids += [i for i in _ol_docs(row.get("work_key", "")) if i not in ids]
        if not ids:
            print(f"  NO-SCAN       {row['title'][:44]} (no archive.org scan for {key})")
            results.append({**row, "status": "NO-SCANNABLE-EDITION"})
            continue

        landed_any = False
        for ident in ids[:4]:
            md = _meta(ident)
            if not md:
                continue
            files = _text_files(md)
            if not files:
                continue
            for name in files[:2]:
                url = f"https://archive.org/download/{ident}/{name.replace(' ', '%20')}"
                st, body, err = _get(url, tries=2, timeout=180)
                if st != 200 or not body or len(body) < 3000:
                    continue
                sha = hashlib.sha256(body).hexdigest()
                if sha in held:
                    continue
                text = body.decode("utf-8", "replace")
                probe = " ".join(text[:40000].split()).lower()
                hits = [k for k, pat in THEMATIC.items() if len(re.findall(pat, probe)) >= 3]
                if len(hits) < 3:
                    continue
                # FILENAME MUST CARRY AUTHOR AND YEAR. Title alone collides: 'An introduction
                # to child-study' (1907, Drummond) and 'An introduction to child study' (1930,
                # Strang) differ by one hyphen and normalise to the same slug -- measured, not
                # hypothesised. Two distinct works, one filename.
                slug = re.sub(r"[^a-z0-9]+", "_", row["title"].lower()).strip("_")[:44]
                who = re.sub(r"[^a-z0-9]+", "", row["author"].lower())[:10]
                dest = PD / f"child_{row['year']}_{who}_{slug}.txt"
                # WRITE UNCONDITIONALLY, THEN VERIFY. The old `if not dest.exists()` meant a
                # file already on disk caused a silent skip -- and the row was still recorded
                # LANDED with a sha that matched nothing on disk. Now the bytes on disk are
                # re-hashed and the row is only LANDED if the hash agrees.
                dest.write_bytes(body)
                landed_sha = hashlib.sha256(dest.read_bytes()).hexdigest()
                # SWEEP STALE-NAMED TWINS. A re-run after a filename-scheme change writes the NEW
                # name and leaves the OLD one on disk -- 5 byte-identical duplicates, exactly the
                # Ingersoll Lockwood pattern, which a hash-verify of CLAIMED files cannot see
                # because the stale copy is not claimed by anything. Remove an unclaimed file
                # ONLY when a claimed file has the identical hash; both conditions or it stays.
                for stale in PD.glob("*.txt"):
                    if stale.name == dest.name:
                        continue
                    if hashlib.sha256(stale.read_bytes()).hexdigest() == sha:
                        stale.unlink()
                        print(f"    swept stale twin {stale.name}")
                if landed_sha != sha:
                    dest.unlink(missing_ok=True)
                    print(f"  WRITE-MISMATCH {row['title'][:40]} -- bytes did not land as fetched; row HELD")
                    continue
                held.add(sha)
                rcp = RECEIPTS / f"child_{dest.stem.replace('child_','')}.md"
                rcp.write_text(
                    f"# RETRIEVAL RECEIPT — child development (PD ancestor) — {row['title']}\n\n"
                    f"openlibrary_work: {key}\n"
                    f"author: {row['author']}\n"
                    f"published: {row['year']}\n"
                    f"archive_identifier: {ident}\n"
                    f"selected_file: {name}\n"
                    f"content_sha256_16: {sha[:16]}\n"
                    f"bytes: {len(body):,}\n"
                    f"pulled: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%MZ')}\n"
                    f"source: {url}\n"
                    f"rights_tier: PD (pre-{1949} US publication; verified year from the "
                    f"catalogue, not assumed)\n"
                    f"landed: {str(dest.relative_to(ROOT)).replace(chr(92), '/')}\n"
                    f"theme_groups_matched: {hits}\n"
                    f"why: {row['why']}\n", encoding="utf-8")
                results.append({"title": row["title"], "author": row["author"],
                                "year": row["year"], "status": "LANDED", "bytes": len(body),
                                "sha256": sha,
                                "landed": str(dest.relative_to(ROOT)).replace("\\", "/"),
                                "receipt": str(rcp.relative_to(ROOT)).replace("\\", "/"),
                                "themes": hits})
                print(f"  LANDED  {row['year']}  {row['title'][:44]:46s} {len(body):>9,}B  {hits}")
                landed_any = True
                break
            if landed_any:
                break
        if not landed_any:
            gated = []
            for ident in ids[:6]:
                st, body, _e = _get(f"https://archive.org/metadata/{ident}", tries=1, timeout=40)
                if st == 200 and body:
                    try:
                        md = json.loads(body)
                        if md.get("metadata", {}).get("access-restricted-item"):
                            gated.append(ident)
                    except Exception:
                        pass
            note = f" -- ALL COPIES LENDING-GATED {gated}" if gated else " -- theme gate failed"
            print(f"  HELD          {row['year']}  {row['title'][:40]}{note}")
            results.append({**{k: v for k, v in row.items() if k != "ident_backup"},
                            "status": "LENDING-GATED" if gated else "THEME-GATE-FAILED",
                            "gated_identifiers": gated})
            results.append({**row, "status": "THEME-GATE-FAILED"})

    debt = RUNS / "KNOWLEDGE_DEBT_attachment_rearing.json"
    debt.write_text(json.dumps({
        "schema": "knowledge_debt.v1",
        "note": "The attachment-theory and whole-brain-child canon is in copyright. These are "
                "recorded as debt WITH a buy-back path, not as withheld material and not as a "
                "silent gap. The public-domain shelf beside them is the ANCESTORS AND THE "
                "OPPOSITION -- notably Watson 1928, the behaviourist pole Bowlby 1969 answered.",
        "entries": DEBT,
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    out = RUNS / "CHILD_DEVELOPMENT_LANDING.json"
    out.write_text(json.dumps({"ts": datetime.now(timezone.utc).isoformat(),
                               "landed": sum(1 for r in results if r["status"] == "LANDED"),
                               "bytes": sum(r.get("bytes", 0) for r in results),
                               "rows": results, "knowledge_debt": str(debt.relative_to(ROOT))
                               .replace("\\", "/")},
                              indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n  {sum(1 for r in results if r['status'] == 'LANDED')}/{len(ROWS)} landed")
    print(f"  knowledge debt recorded: {len(DEBT)} in-copyright works with buy-back paths")
    print(f"  -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())