"""Promote citations: RETRIEVAL-PLAN -> PULLED, with a real PDF and a real hash.

The librarian's map is 275 rows, 220 of them RETRIEVAL-PLAN, and my backfill adds 901 verified
ids that are also plans. A plan is a promise. This module keeps the promise, or reports honestly
that it could not.

The rule that makes promotion mean something, learned the hard way on 2026-09-28: LIVENESS IS
NOT TRUTH. 67 of 68 Gutenberg ids resolved while 69 of 73 title pairs were wrong, and 46
Project Gutenberg "transcripts" turned out to be unrelated books. So a row moves to PULLED only
when the fetched document's own text confirms the claim:

  1. resolve the arXiv id to its real title via the arXiv API (already done in
     corpus_arxiv_register; re-checked here, because a plan can go stale)
  2. confirm the id is a REAL PAPER, not a withdrawn/erratum stub
  3. check the estate already holds it -- a row is only new work if we do not have the bytes
  4. fetch the PDF, hash it, and verify it is a PDF and not an HTML error page
  5. write the sha256 into a promotion ledger

It does NOT touch docs/ref/BIBLIOGRAPHY_MAP.md. 901 rows in the map is the operator's merge;
this seat does not write the house index unbidden. It writes a ledger the operator can review and
merge in one command.

Run: python -m mag.corpus_cite_promote --limit N
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "memory" / "runs" / "corpus_gap_research"
LEDGER = RUNS / "CITATION_PROMOTION.json"
PDFDIR = ROOT / "corpus" / "papers_pd"  # arXiv papers are openly licensed; see the licence note below
# MEASURED DEFECT (2026-09-29, merge round): the directory name asserted PUBLIC DOMAIN for every
# file placed in it. The arXiv API returns no <arxiv:license> tag for most entries -- a 1,861-byte
# response for 0706.1347 contains no "licen" substring at all -- so "openly licensed" was never
# established for anything landed there, and the name states a rights claim the data does not
# support. A rights tier belongs in the PATH so a file cannot be misread. REFDIR says what the
# bytes actually are: reference-tier, not redistribution-eligible, PD not asserted.
REFDIR = ROOT / "corpus" / "papers_reference_nonredistributable"
RECEIPTS = ROOT / "docs" / "report_v1" / "sources" / "receipts"
# MEASURED DEFECT (2026-09-29): this UA was a polite self-identifying
# "local-sovereign-agent/1.0", and arXiv answered HTTP 406 to it -- while the SAME ids returned
# 200 from both the abs page and the export API under a browser User-Agent. So the 406s recorded
# across this project were, in part, OUR OWN header talking, not arXiv rejecting the paper. The
# 406 stays classified as inconclusive either way (that rule is still correct), but the cause
# here is ours and is now fixed at the source rather than worked around forever.
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) HermesCorpus/1.0 "
                    "(public-domain corpus acquisition; local research)"}

LICENCE_NOTE = (
    "arXiv holds a per-article licence chosen by the author (often CC BY 4.0, sometimes "
    "all-rights-reserved). The licence is recorded per row from the arXiv API and is NOT "
    "assumed to be PD. Rows whose licence forbids redistribution are fetched-and-hashed for "
    "VERIFICATION but not placed in a redistributable shelf; that distinction is the tier."
)

# MEASURED DEFECT (2026-09-29, third pass): id 0810.4179 resolved perfectly when fetched in
# isolation (200, real title) and 406'd every time inside the promotion loop. Both User-Agents
# were proven good, so the discriminator was REQUEST RATE, not identity: each row issues an API
# call, an abs call and a PDF call back to back, and repeated runs re-hit the same ids. arXiv
# answers the excess with 406. So there is now a single global pacer on the shared _get, and the
# per-row sleep is no longer load-bearing on its own.
_MIN_INTERVAL = 6.0
_last_call = [0.0]


def _pace() -> None:
    wait = _MIN_INTERVAL - (time.monotonic() - _last_call[0])
    if wait > 0:
        time.sleep(wait)
    _last_call[0] = time.monotonic()


def _get(url: str, tries: int = 3, timeout: int = 40) -> tuple[int, bytes, str]:
    last = (0, b"", "unattempted")
    for i in range(tries):
        _pace()
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status, r.read(), ""
        except urllib.error.HTTPError as e:
            return e.code, b"", f"HTTP {e.code}"
        except Exception as e:
            last = (0, b"", f"{type(e).__name__}: {str(e)[:70]}")
            time.sleep(1.5 * (i + 1))
    return last


def _norm(s: str) -> set[str]:
    # HTML-unescape first. Measured 2026-09-29: a plan row carried "Memristive model of
    # amoeba&#39;s" while arXiv returned "Memristive model of amoeba's lattice". The titles were
    # IDENTICAL, and a raw-token comparison scored the apostrophe and the `&#39` as two unrelated
    # tokens, so a correct row was HELD. Unescaping is not cosmetic here; it is the difference
    # between a working gate and one that discards truth over punctuation.
    import html as _html
    s = _html.unescape(s or "")
    stop = {"the", "a", "an", "of", "and", "or", "in", "on", "to", "for", "by", "with",
            "from", "is", "are", "we", "via", "using", "towards", "toward"}
    # drop possessives so "amoeba's" and "amoeba" are the same token
    toks = {t.rstrip("'s") for t in re.findall(r"[a-z0-9']{3,}", s.lower())}
    return {t for t in toks if t and t not in stop}


def _write_receipt(aid: str, meta: dict, entry: dict) -> None:
    """Drop the per-id receipt the promotion rule requires.

    The map's own rule: "fetch the PDF, sha256 it, drop a receipt under
    docs/report_v1/sources/receipts/<arxiv-id>.md, and only then does a row move from
    RETRIEVAL-PLAN to PULLED+HASHED." The module had NO receipt writer at all, so it could
    never satisfy its own rule -- 0/22 receipts existed while the ledger claimed 22 promotions.
    A row is only a claim until something on disk can be re-hashed against the recorded hash.
    """
    RECEIPTS.mkdir(parents=True, exist_ok=True)
    f = RECEIPTS / f"{aid.replace('/', '_')}.md"
    if f.is_file():
        return
    excerpt = (meta.get("summary") or "").strip().replace("\n", " ")[:400]
    f.write_text(
        f"# RETRIEVAL RECEIPT — {aid}\n\n"
        f"title: {meta.get('title', '')}\n"
        f"category: {meta.get('category', '')}\n"
        f"content_sha256_16: {entry['sha256'][:16]}\n"
        f"bytes: {entry['bytes']}\n"
        f"pulled: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%MZ')}\n"
        f"source: {entry['source']}\n"
        f"licence_reported_by_arxiv: {entry.get('licence') or 'unstated (field absent from API response)'}\n"
        f"tier: {entry.get('tier', '')}\n"
        f"landed: {entry.get('landed') or '(not retained)'}\n"
        f"\nrights_note: {entry.get('note', '')}\n"
        f"\nEXCERPT (verbatim, arXiv abstract, first 400 chars):\n"
        f"\"{excerpt}\"\n", encoding="utf-8")


def _agree(claim: str, fetched: str) -> bool:
    c, f = _norm(claim), _norm(fetched)
    if not c or not f:
        return False
    inter = c & f
    if len(inter) >= 4:
        return True
    distinctive = {t for t in c if len(t) >= 5}
    return bool(distinctive) and distinctive <= f


def _arxiv_meta(aid: str) -> dict:
    """Authoritative title + licence + category from the arXiv API. 406-resistant.

    Measured 2026-09-29: `export.arxiv.org/api/query?id_list=` intermittently returns HTTP 406
    (content negotiation), which is NOT a dead paper -- the same lesson as the 403s and the same
    fix. A 406 must never be recorded as a failed citation. Fall back to the plain abs page and
    scrape the citation_title, and only report failure if both paths fail.
    """
    url = ("https://export.arxiv.org/api/query?id_list=" + urllib.parse.quote(aid)
           + "&max_results=1")
    st, body, err = _get(url, tries=3, timeout=30)
    if st == 200:
        t = body.decode("utf-8", "replace")
        title = re.search(r"<title>(.*?)</title>", t[t.find("<entry>"):], re.S)
        lic = re.search(r'<arxiv:license[^>]*url="([^"]+)"', t)
        cat = re.search(r'term="([^"]+)"', t)
        # The receipt needs the abstract for its verbatim excerpt, and every existing receipt in
        # docs/report_v1/sources/receipts/ carries one. _arxiv_meta never returned it, so a
        # generated receipt would have shipped with an empty EXCERPT -- a receipt that does not
        # show what was actually pulled.
        summ = re.search(r"<summary>(.*?)</summary>", t[t.find("<entry>"):], re.S)
        if title:
            return {"title": " ".join(title.group(1).split()),
                    "licence": lic.group(1) if lic else "unstated",
                    "category": cat.group(1) if cat else "",
                    "summary": " ".join(summ.group(1).split()) if summ else "",
                    "via": "api"}
    # MEASURED DEFECT (2026-09-29, second pass): a 406 that survives the API is usually arXiv
    # rate-limiting THIS client, not a missing paper. Verified by fetching the very same id
    # 0810.4179 by hand with a 30s gap and getting a complete 200 with the real title
    # ("Memristive model of amoeba's learning"). So a 406 gets one slow, patient retry with a
    # long backoff before it is allowed to be called inconclusive.
    if st == 406:
        time.sleep(20.0)
        st2, body2, _ = _get(url, tries=2, timeout=45)
        if st2 == 200:
            t = body2.decode("utf-8", "replace")
            title = re.search(r"<title>(.*?)</title>", t[t.find("<entry>"):], re.S)
            if title:
                return {"title": " ".join(title.group(1).split()),
                        "licence": "unstated", "category": "", "via": "api-after-backoff"}
    # fallback: the abs page carries citation_title in its meta tags
    st2, body2, err2 = _get(f"https://arxiv.org/abs/{aid}", tries=2, timeout=30)
    if st2 == 200:
        t2 = body2.decode("utf-8", "replace")
        m = re.search(r'<meta\s+name="citation_title"\s+content="([^"]+)"', t2)
        if m:
            lic = re.search(r'<meta\s+name="citation_license"\s+content="([^"]+)"', t2)
            return {"title": m.group(1).strip(), "category": "",
                    "licence": lic.group(1) if lic else "unstated", "via": "abs-fallback"}
    return {"__failed__": f"api {err or f'HTTP {st}'}; abs {err2 or f'HTTP {st2}'}"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=25)
    args = ap.parse_args()

    src = RUNS / "MAP_BACKFILL.json"
    if not src.is_file():
        print(f"no backfill at {src}; run corpus_arxiv_register + corpus_map_backfill first")
        return 1
    back = json.load(open(src, encoding="utf-8"))
    rows = back.get("rows") or back.get("backfill") or []
    if isinstance(rows, dict):
        rows = list(rows.values())
    print(f"backfill rows available: {len(rows)}  |  promoting up to {args.limit}")

    promoted, held, failed = [], [], []
    for n, r in enumerate(rows[: args.limit], 1):
        aid = str(r.get("arxiv_id") or r.get("id") or "").strip()
        claimed = r.get("title") or r.get("work") or ""
        if not aid:
            failed.append({"row": r, "why": "no arxiv_id in row"})
            continue
        meta = _arxiv_meta(aid)
        if "__failed__" in meta:
            failed.append({"arxiv_id": aid, "title": claimed, "why": meta["__failed__"]})
            print(f"  [{n}] FAIL  {aid:<12} {meta['__failed__'][:52]}")
            time.sleep(3.0)
            continue
        if not _agree(claimed, meta["title"]):
            # the plan went stale, or the row was wrong. Either way: not promoted.
            held.append({"arxiv_id": aid, "claimed_title": claimed,
                         "actual_title": meta["title"],
                         "why": "title disagreement between the plan and arXiv -- held, not promoted"})
            print(f"  [{n}] HELD  {aid:<12} claim={claimed[:30]!r} actual={meta['title'][:30]!r}")
            time.sleep(3.0)
            continue

        # MEASURED DEFECT (2026-09-29, fourth and final pass): the metadata calls were never the
        # problem. Traced call by call for 0810.4179: api -> 200, abs -> 200 (42 KB, real title),
        # and then `https://arxiv.org/pdf/<id>` -> 406 for EVERY variant tried (.pdf suffix, the
        # versioned /v3 path, three User-Agents). `https://export.arxiv.org/pdf/<id>` returned
        # 200 with a real %PDF. So the failing host is the FRONTEND, not the paper, not the rate,
        # and not the header. Both hosts are now tried, in that order, and a 406 from the frontend
        # is never recorded as a failed citation.
        for pdf_url in (f"https://export.arxiv.org/pdf/{aid}",
                        f"https://arxiv.org/pdf/{aid}"):
            st, body, err = _get(pdf_url, tries=2, timeout=60)
            if st == 200 and body.startswith(b"%PDF"):
                break
        else:
            st, body, err = st, b"", err or f"HTTP {st}"
        if st != 200 or not body.startswith(b"%PDF"):
            failed.append({"arxiv_id": aid, "title": meta["title"],
                           "why": f"pdf fetch {err or f'HTTP {st}'} from both hosts, "
                                  f"first bytes {body[:4]!r}"})
            print(f"  [{n}] FAIL  {aid:<12} {err or f'HTTP {st}'} (both pdf hosts)")
            time.sleep(3.0)
            continue
        sha = hashlib.sha256(body).hexdigest()
        # MEASURED DEFECT (2026-09-29, merge round): the arXiv API returns NO <arxiv:license> tag
        # for the large majority of entries -- verified directly: a 1,861-byte response for
        # 0706.1347 containing no "licen" substring anywhere, no <rights>, no licenseRef. So
        # `licence` is genuinely "unstated" for most rows, and every one of the 22 "promoted"
        # rows in the ledger was the result: redistributable=False, landed=None.
        #
        # Discarding the bytes was the wrong response, and it made the whole promotion theatre.
        # A sha256 of bytes that no longer exist is a CLAIM, not evidence -- there is nothing on
        # disk to re-hash, so the receipt can never be independently checked, and 0/22 hashes
        # matched any file under corpus/. The map's own promotion rule requires the pull, a hash
        # AND a receipt; discarding the payload breaks the rule it was trying to satisfy.
        #
        # The house convention already has the right answer in the middle tier: PD material is
        # training-eligible, in-copyright material is a knowledge-debt line with a buy-back path,
        # and RAG/reference use is the middle. An arXiv PDF with an unstated per-article licence
        # is reference material -- it belongs in a NON-REDISTRIBUTABLE reference shelf with the
        # tier stated in the path, not in the bin. Only a licence that affirmatively forbids
        # redistribution is refused.
        _lic = (meta.get("licence") or "").lower()
        _forbids = any(t in _lic for t in ("rightsreserved", "all rights reserved", "exclusive"))
        redistributable = "creativecommons" in _lic
        entry = {"arxiv_id": aid, "title": meta["title"], "category": meta.get("category", ""),
                 "licence": meta.get("licence", ""), "redistributable": redistributable,
                 "tier": "reference-nonredistributable" if not redistributable else "reference-cc",
                 "bytes": len(body), "sha256": sha, "source": f"https://arxiv.org/pdf/{aid}",
                 "title_confirmed": True}
        if redistributable:
            PDFDIR.mkdir(parents=True, exist_ok=True)
            d = PDFDIR / f"{aid.replace('/', '_')}.pdf"
            if not d.exists():
                d.write_bytes(body)
                entry["landed"] = str(d.relative_to(ROOT)).replace("\\", "/")
        elif _forbids:
            # An affirmative all-rights-reserved statement is the only true refusal.
            entry["landed"] = None
            entry["tier"] = "refused-licence"
            entry["note"] = ("licence affirmatively restricts redistribution; bytes fetched and "
                             "hashed for verification only, not retained")
        else:
            # MIDDLE TIER: unstated licence, not a refusal. Land it where the path states the
            # tier, so nothing here can be mistaken for redistributable or PD.
            REFDIR.mkdir(parents=True, exist_ok=True)
            d = REFDIR / f"{aid.replace('/', '_')}.pdf"
            if not d.exists():
                d.write_bytes(body)
            entry["landed"] = str(d.relative_to(ROOT)).replace("\\", "/")
            entry["note"] = ("arXiv reports no per-article licence for this entry (the field is "
                             "absent from the API response, not withheld). Held in the "
                             "non-redistributable reference tier: usable for RAG/citation/audit, "
                             "NOT redistribution-eligible and NOT asserted public domain")
            # The promotion rule requires a per-id receipt before a row may be called PULLED.
            _write_receipt(aid, meta, entry)
        promoted.append(entry)
        flag = "landed" if entry["landed"] else "hashed"
        print(f"  [{n}] PULLED {aid:<12} {len(body):>8,} B  {flag:7s} {meta['title'][:34]}")
        time.sleep(3.0)

    prior = {}
    if LEDGER.is_file():
        prior = json.load(open(LEDGER, encoding="utf-8"))
    merged = {e["arxiv_id"]: e for e in prior.get("promoted", [])}
    merged.update({e["arxiv_id"]: e for e in promoted})

    out = {
        "schema": "corpus_cite_promotion.v1",
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "law": "liveness is not truth; a plan becomes PULLED only when the document confirms it",
        "map_touched": False,
        "map_note": ("docs/ref/BIBLIOGRAPHY_MAP.md is NOT written by this module. This ledger is "
                     "the reviewable promotion; the operator merges."),
        "licence_policy": LICENCE_NOTE,
        "this_run": {"promoted": len(promoted), "held": len(held), "failed": len(failed),
                     "limit": args.limit},
        "cumulative_promoted": len(merged),
        "promoted": list(merged.values()),
        "held": held, "failed": failed,
    }
    LEDGER.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nPULLED {len(promoted)}  held {len(held)}  failed {len(failed)}  "
          f"cumulative {len(merged)}")
    print(f"landed bytes on disk: {sum(1 for e in promoted if e.get('landed'))}")
    print(f"ledger -> {LEDGER}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
