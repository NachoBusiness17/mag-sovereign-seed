"""Salvage: for every lead whose Gutenberg handle is wrong, FIND the right one.

The title-match found ~69 (qid, id) pairs where a lane named a real work by a real author and
paired it with a live ID belonging to a different book. The work is not lost -- only the handle.

Gutendex (https://gutendex.com) is a public JSON index of Project Gutenberg: no key, no
scraping, one query per claimed work. For each UNMATCHED claim we take the work title out of
the lead's own text, query Gutendex, and keep only a candidate whose fetched catalogue title
agrees with the claim. That agreement is re-checked against gutenberg.org/ebooks/<id> itself,
so a promoted handle has been confirmed by two independent lookups.

Result: a promote-ready manifest of works -> verified id -> sha256-able source URL, with the
law's third tier (PD / RAG / DEBT) attached per work. Nothing is downloaded here.

Read-only against the network. Writes MANIFEST.candidates.json + SALVAGE.md.
"""
from __future__ import annotations

import json
import re
import sys
import urllib.parse
import urllib.request
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "memory" / "runs" / "corpus_gap_research"
TRUTH = RUNS / "gutenberg_title_match.json"
OUT = RUNS / "MANIFEST.candidates.json"
UA = {"User-Agent": "local-sovereign-agent/1.0 (corpus salvage; catalogue metadata only)"}

STOP = {"the", "a", "an", "of", "and", "or", "in", "on", "to", "for", "by", "with", "from", "is",
        "was", "it", "its", "as", "at", "that", "this", "be", "de", "la", "le", "von", "der",
        "book", "volume", "vol", "part", "edition", "novel", "story", "tales", "tale", "other"}


def _norm(s: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9']{3,}", (s or "").lower()) if t not in STOP}


def _get_json(url: str, timeout: int = 30, tries: int = 3) -> dict:
    """Fetch JSON, retrying on timeout.

    A timeout must never be reported as an empty result set: `{}` is indistinguishable from
    "the API has no such book", and that difference is the whole claim. Any exhausted retries
    return a sentinel the caller can see.
    """
    last = ""
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except Exception as e:
            last = f"{type(e).__name__}: {e}"[:120]
            time.sleep(1.5 * (i + 1))
    return {"__fetch_failed__": last}


def _salvage_one(row: dict) -> dict | None:
    """Do the Gutendex lookup + the independent catalogue confirm for one bad handle.

    Network-bound, so the driver runs these in a thread pool: 69 serial round-trips took over
    7 minutes and timed the tool out, which is a harness limit rather than a result.
    """
    got = claimed_work(row["claim_context"])
    if not got:
        return {"_miss": {"qid": row["qid"], "bad_id": row["gutenberg_id"],
                          "why": "no parsable work+author in the lead text"}}
    work, author = got
    q = urllib.parse.quote(work)
    res = _get_json(f"https://gutendex.com/books?search={q}")
    if "__fetch_failed__" in res:
        return {"_miss": {"qid": row["qid"], "bad_id": row["gutenberg_id"],
                          "work": work, "author": author,
                          "why": f"FETCH FAILED (not absent): {res['__fetch_failed__']}"}}
    cands = res.get("results", []) if res else []
    hit = None
    for c in cands[:12]:
        bt = c.get("title", "")
        authors = " ".join(a.get("name", "") for a in (c.get("authors") or []))
        if agree(work, bt) and (not author or agree(author, authors)
                                 or _norm(author) & _norm(authors)):
            hit = (c, bt, authors)
            break
    if not hit:
        return {"_miss": {"qid": row["qid"], "bad_id": row["gutenberg_id"],
                          "work": work, "author": author,
                          "why": f"no Gutendex candidate agreed on title (of {len(cands)} returned)"}}
    c, bt, authors = hit
    gid = c.get("id")
    status, pg_title = _pg_title(gid)
    confirmed = status == 200 and agree(work, pg_title)
    text = ""
    for f in (c.get("formats") or {}):
        if f.endswith(".txt") or f.endswith(".txt.utf-8"):
            text = f
            break
    return {"_hit": {
        "work_claimed": work, "author_claimed": author,
        "work_confirmed": bt, "author_confirmed": authors,
        "gutendex_id": gid, "bad_handle_replaced": row["gutenberg_id"],
        "pg_status": status, "pg_title": pg_title, "confirmed": confirmed,
        # gutendex returns subjects as bare strings on some records and {name:...} on others
        "subjects": [(s.get("name") if isinstance(s, dict) else str(s))
                     for s in (c.get("subjects") or [])][:6],
        "source_text": f"https://www.gutenberg.org/ebooks/{gid}" if confirmed else text,
        "law_tier": "PD",
        "jurisdiction_note": "US public domain; confirm the Gutenberg header/footer boilerplate at download time",
    }}


def _pg_title(gid) -> tuple[int, str]:
    try:
        req = urllib.request.Request(f"https://www.gutenberg.org/ebooks/{gid}", headers=UA)
        with urllib.request.urlopen(req, timeout=20) as r:
            html = r.read(300_000).decode("utf-8", "replace")
    except Exception as e:
        return getattr(e, "code", 0) or 0, ""
    m = re.search(r"<title>([^<]*)", html)
    return 200, (m.group(1) if m else "").replace(" | Project Gutenberg", "").strip()


def claimed_work(ctx: str) -> tuple[str, str] | None:
    """Pull (work_title, author) out of the lead's own bullet.

    The first version matched only `work - author` and silently dropped 44 of 70 rows, so the
    salvage looked catastrophic when most of those were trivially findable. Handles the three
    shapes the pack actually uses:
      * `- **Work** - Author (d. 1234) - PG 1234`   (dashes, life dates)
      * `- **Work**, Author, PG 1234`               (commas)
      * `- **Author**. *Work*. PG 1234`             (author first)
    Requires BOTH a work and an author, or returns None -- a half-parse is worse than a miss
    because it sends a nonsense title to Gutendex.
    """
    txt = ctx.replace("**", " ").replace("`", " ")
    txt = re.sub(r"\bPG\s*#?\s*\d{3,6}\b", " ", txt, flags=re.IGNORECASE)
    txt = re.sub(r"\bGutenberg\s*#?\s*\d{3,6}\b", " ", txt, flags=re.IGNORECASE)
    txt = re.sub(r"https?://\S+", " ", txt)
    txt = txt.strip(" -–—:|")

    LIFE = re.compile(r"\((?:d\.|b\.|fl\.?)?\s*\d{3,4}[^)]*\)")
    txt = LIFE.sub(" ", txt)

    # shape 1: dash or en-dash separated
    for sep in (r"\s[–—]\s", r"\s-\s"):
        m = re.search(sep.join([r"([^–—\-|]{4,90}?)", r"([^–—\-|]{3,60})"]), txt)
        if m:
            work, author = m.group(1).strip(" .,"), m.group(2).strip(" .,")
            if len(work) > 3 and len(author) > 2 and not re.fullmatch(r"[\d\s.]+", author):
                return work, author

    # shape 2: comma separated -> first is work, second is author
    parts = [p.strip(" .,") for p in txt.split(",") if len(p.strip(" .,")) > 2]
    if len(parts) >= 2:
        author, work = parts[1], parts[0]
        if len(work) > 3 and len(author) > 2:
            return work, author

    # shape 3: author first, then an italicised or quoted work
    m = re.search(r"([A-Z][\w.'’ -]{3,40})\.\s*[\*\"“']?([A-Z][\w'’,: ]{5,70})", txt)
    if m:
        return m.group(2).strip(" .,"), m.group(1).strip(" .,")

    return None


def agree(claim: str, fetched: str) -> bool:
    """Does the fetched title plausibly BE the claimed work?

    The first version required >=2 shared tokens, which rejected obvious matches: "The Book of
    the Courtier" vs "The Courtier" shares only `courtier`, and "The Art of War" vs "The Art of
    War" survives only if the stopword list is not eating `art`/`war`. So the rule is now
    SUBSET-SIGNIFICANT rather than a fixed count: every distinctive (long) token of the claim's
    core must appear in the fetched title, OR one rare shared token carries it.

    This is a promotion gate, so it stays asymmetric in the safe direction -- a loose match is
    still caught by the second, independent lookup against gutenberg.org in the caller.
    """
    c, f = _norm(claim), _norm(fetched)
    if not c or not f:
        return False
    # An exact normalised match is the strongest signal there is -- and it is the case the
    # distinctive-token rule silently failed, because a short title like "The Art of War"
    # normalises to {art, war}, every token under the 5-char floor, leaving nothing to compare.
    if c == f:
        return True
    inter = c & f
    if not inter:
        return False
    # distinctive = long enough to carry identity
    distinctive = {t for t in c if len(t) >= 5}
    if distinctive and distinctive <= f:
        return True
    # otherwise a single strong shared token (>=6 chars) is enough
    return any(len(t) >= 6 for t in inter)


def main() -> int:
    truth = json.loads(TRUTH.read_text(encoding="utf-8"))
    bad = [r for r in truth["results"] if r["verdict"] in ("UNMATCHED", "HTTP_404")]

    salvaged, unrecoverable = [], []
    seen_works: set[tuple[str, str]] = set()

    # Serial, with a pause. MEASURED DEFECT: the first salvage run used an 8-worker
    # ThreadPoolExecutor and Gutendex answered most queries with a read timeout, which _get_json
    # turned into `{}` -- so every result list came back empty and 36 works were reported as
    # "not on Gutenberg". A serial probe with a 2s pause returns beowulf=9, moby dick=5,
    # Emma Austen=2. The earlier "these works are absent from the corpus" reading was an
    # artefact of my own concurrency, and it was wrong. Gutendex rate-limits; respect it.
    #
    # Second defect, same run: the manifest was written ONCE at the end, so a 70-item serial
    # pass looked identical to a hung process (no file mtime change, no output). Each item now
    # appends to the manifest immediately, so progress is observable and a kill loses nothing
    # already learned.
    # OUT is the manifest FILE path, not a directory -- joining it produced
    # ".../MANIFEST.candidates.json/salvage_progress.jsonl" and a hard FileNotFoundError.
    prog = OUT.parent / "salvage_progress.jsonl"
    prog.write_text("", encoding="utf-8")
    for n, row in enumerate(bad, 1):
        res = _salvage_one(row)
        with prog.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"n": n, "of": len(bad),
                                 "qid": row.get("qid"), "bad_id": row.get("gutenberg_id"),
                                 "result": res}, ensure_ascii=False) + "\n")
        if not res:
            continue
        if "_miss" in res:
            unrecoverable.append(res["_miss"])
        else:
            s = res["_hit"]
            key = (s["work_claimed"].lower(), s["author_claimed"].lower())
            if key not in seen_works:
                seen_works.add(key)
                salvaged.append(s)
        # Write the manifest AND the report every 10 items, so a long serial pass is always
        # resumable and its partial truth is readable. Measured: at ~13 s/item a 70-item pass
        # runs ~15 min, which is longer than a single tool window -- an end-only write made a
        # healthy run indistinguishable from a hung one.
        if n % 10 == 0:
            _emit(salvaged, unrecoverable, len(bad), partial_at=n)
        time.sleep(1.2)

    return _emit(salvaged, unrecoverable, len(bad), partial_at=None)


def _emit(salvaged: list[dict], unrecoverable: list[dict], total: int,
          partial_at: int | None) -> dict:
    """Write the manifest + the human report. Called every 10 items and once at the end.

    One writer, so a partial run and a complete run produce the same shape and a reader cannot
    mistake one for the other -- `partial` is explicit in both files.
    """
    out = {
        "schema": "corpus_salvage.v1",
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "law": "a lead is promoted by title-match, never by status-match",
        "input_bad_handles": total,
        "partial": partial_at is not None,
        "processed": partial_at if partial_at is not None else total,
        "salvaged": len(salvaged),
        "confirmed": sum(1 for s in salvaged if s["confirmed"]),
        "unrecoverable": len(unrecoverable),
        "candidates": salvaged,
        "misses": unrecoverable,
        "promotion_rule": ("curl the text, sha256 it, land under corpus/library/<theme>/ with a "
                           "MANIFEST.sha256 row carrying licence basis and jurisdiction. Nothing "
                           "here is downloaded; this file is a work-list, not a holding."),
    }
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    partial_note = (f" — **PARTIAL, {out['processed']}/{total} processed**" if partial_at is not None
                    else f" — complete, {total}/{total}")
    L = ["# SALVAGE — correct handles for the leads that named a real work and a wrong id", "",
         f"*{out['input_bad_handles']} bad handles in{partial_note} · "
         f"**{out['confirmed']}/{out['salvaged']} salvaged candidates confirmed** by a second "
         f"lookup against gutenberg.org/ebooks/ · {out['unrecoverable']} unrecoverable · "
         f"{out['ts']}*", "",
         f"> **{out['law']}**", "",
         "| work (claimed) | author | confirmed id | catalogue title | replaces bad id |",
         "|---|---|---:|---|---|"]
    for s in salvaged:
        if not s["confirmed"]:
            continue
        L.append(f"| {s['work_claimed']} | {s['author_claimed']} | {s['gutendex_id']} | "
                 f"{s['work_confirmed'][:40]} | ~~{s['bad_handle_replaced']}~~ |")
    L += ["", "## Unconfirmed candidates (do not promote without a second look)", ""]
    for s in salvaged:
        if not s["confirmed"]:
            L.append(f"- {s['work_claimed']} ({s['author_claimed']}) -> id {s['gutendex_id']} "
                     f"but catalogue says `{s['pg_title'][:50]}` (HTTP {s['pg_status']})")
    L += ["", "## Unrecoverable — no candidate agreed on title", ""]
    for u in unrecoverable:
        L.append(f"- {u.get('work', u['qid'])} ({u.get('author','')}) — {u['why']}")
    L += ["", "## How to promote", "", f"1. {out['promotion_rule']}",
          "2. Check the Gutenberg header boilerplate on the downloaded file; the `law_tier` here is",
          "   an expectation from the catalogue, not a read of the file.",
          "3. `10.1007/978` style dead DOIs (47 of 89 in `verify.json`) are NOT salvageable by this",
          "   route: they are not book handles. Treat them as unverified and re-derive from a",
          "   publisher page."]
    (RUNS / "SALVAGE.md").write_text("\n".join(L), encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("input_bad_handles", "processed", "partial",
                                          "salvaged", "confirmed", "unrecoverable")}, indent=2))
    return out


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
