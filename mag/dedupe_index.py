"""Content-hash dedupe index — the gate that stops re-downloading what we already hold.

WHY THIS EXISTS
  This session caught the seat downloading material the estate already owned, twice:
    - three Ingersoll Lockwood books, 1,069,068 B, re-fetched while already sitting in
      corpus/library/ingersoll_lockwood/ — invisible to a scan that only looked for pd_* dirs;
    - and the operator had to point out that the entire watch/ tree had never been searched.

  Both failures share a cause: dedupe was done on FILENAMES, which is wrong in two directions at
  once. It misses a real book filed under an unexpected directory name, and it manufactures false
  duplicates when unrelated files reduce to the same normalized title (an earlier attempt
  collapsed every front-matter-less file onto one empty key and reported a false group).

  So: sha256 the BYTES. Two files are the same document only if they are byte-identical.
  Title matching is kept as a separate, advisory signal and never as a merge decision.

MEASURED (2026-09-29, first run over this estate)
    files indexed        68,981
    unique hashes        62,890
    duplicate groups      2,308
    title keys              512

  Caveat worth stating rather than hiding: most of those 2,308 groups are NOT books. One group is
  a single 9-byte file replicated 825 times under corpus/oral_history/seat_pools/grok_sessions/.
  Real-book duplication is a far smaller number. The index reports both, because a count that
  mixes "the same book twice" with "the same empty marker 825 times" is not a number anyone can
  act on.

USAGE
    python -m mag.dedupe_index            # build/refresh and print the summary
    python -m mag.dedupe_index --probe F  # is F already held? (by hash, then by title)
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "memory" / "runs" / "physical_compute_lineage"
INDEX = RUNS / "DEDUPE_INDEX.json"

# Bytes that are obviously not documents. Indexed separately so the summary cannot imply that
# 2,308 groups means 2,308 duplicated books.
TRIVIAL_MAX = 64

TITLE_STOP = {"the", "a", "an", "of", "and", "to", "in", "on", "for", "with",
              "from", "by", "at", "as", "its", "it", "was", "were", "been"}


def _norm_title(path: Path) -> str | None:
    """First content-bearing line, normalized. Advisory only — never used to merge."""
    try:
        head = path.read_text(encoding="utf-8", errors="replace")[:4000]
    except Exception:
        return None
    for line in head.splitlines()[:40]:
        words = [w for w in re.sub(r"[^a-z0-9 ]", " ", line.lower()).split()
                 if w not in TITLE_STOP and len(w) > 2]
        if len(words) >= 4:
            return " ".join(words[:8])
    return None


def build() -> dict:
    by_hash: dict[str, list[str]] = collections.defaultdict(list)
    titles: dict[str, list[str]] = collections.defaultdict(list)
    doc_dupes: dict[str, list[str]] = {}
    indexed = trivial = 0

    for p in (ROOT / "corpus").rglob("*"):
        if not p.is_file():
            continue
        try:
            size = p.stat().st_size
        except OSError:
            continue
        if size == 0:
            continue
        rel = str(p.relative_to(ROOT)).replace("\\", "/")

        if size <= TRIVIAL_MAX:
            trivial += 1
            continue
        try:
            digest = hashlib.sha256(p.read_bytes()).hexdigest()
        except Exception:
            continue
        indexed += 1
        by_hash[digest].append(rel)
        if len(by_hash[digest]) > 1:
            doc_dupes[digest] = by_hash[digest]

        if p.suffix.lower() in {".txt", ".md"}:
            t = _norm_title(p)
            if t:
                titles[t].append(rel)

    out = {
        "schema": "corpus_dedupe_index.v2",
        "files_indexed": indexed,
        "skipped_trivial_le_64b": trivial,
        "unique_hashes": len(by_hash),
        "document_duplicate_groups": len(doc_dupes),
        "title_keys": len(titles),
        "note": ("Group counts are separated by size because a count that mixes 'the same book "
                 "twice' with 'the same 9-byte marker 825 times' is not actionable. Title keys "
                 "are ADVISORY: they suggest a candidate, they never authorise a merge."),
    }
    RUNS.mkdir(parents=True, exist_ok=True)
    INDEX.write_text(json.dumps(out, indent=2), encoding="utf-8")
    (RUNS / "DEDUPE_GROUPS.json").write_text(
        json.dumps({"by_hash": doc_dupes, "by_title": {k: v for k, v in titles.items()
                                                       if len(v) > 1}}, indent=2),
        encoding="utf-8")
    return out


def load() -> dict:
    if INDEX.is_file():
        return json.loads(INDEX.read_text(encoding="utf-8"))
    return build()


def probe(path: Path) -> tuple[bool, str]:
    """Is this file already held, byte-for-byte? Returns (is_duplicate, explanation).

    MEASURED DEFECT (2026-09-29, this session): the first implementation compared `p == path`
    to skip the file under test. That is a PATH identity check, and it does not work here --
    every caller passes a path built independently (e.g. a glob result), so the same file
    arrives as two different Path objects that are equal only after resolution, and on Windows
    the separators and drive casing differ freely. The gate therefore reported
    "DUPLICATE of <the file itself>" on a file that existed exactly once on disk.

    Verified before the fix: probing the just-landed Frontinus returned a match, and a manual
    sweep for that hash across corpus/ found ZERO other byte-identical copies. The gate was
    reporting a file as its own duplicate -- a false positive on the exact class of input it
    exists to judge, which is worse than no gate at all because it would make a seat delete
    perfectly good material as a "duplicate".

    The fix compares resolved paths, and -- because that is still a path comparison -- the
    hash is only compared against files that are genuinely a different object on disk.
    """
    path = path.resolve()
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    size = path.stat().st_size
    for p in (ROOT / "corpus").rglob("*"):
        if not p.is_file():
            continue
        try:
            if p.resolve() == path:
                continue
            if p.stat().st_size != size:
                continue
            if hashlib.sha256(p.read_bytes()).hexdigest() == digest:
                return True, str(p.relative_to(ROOT)).replace("\\", "/")
        except Exception:
            continue
    return False, ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", type=Path)
    ap.add_argument("--rebuild", action="store_true")
    a = ap.parse_args()

    if a.probe:
        dup, where = probe(a.probe)
        print("DUPLICATE of " + where if dup else "NOT already held")
        return 0 if dup else 1

    print(json.dumps(build() if a.rebuild else load(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())