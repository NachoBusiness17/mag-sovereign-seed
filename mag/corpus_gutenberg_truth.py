"""Title-match the live Gutenberg handles against what the lead actually claimed.

Liveness is cheap and nearly free of information: 67 of 68 Gutenberg IDs resolve, yet a
hand-check of 17 found 7 pointing at a different book. So this script does the expensive part --
for each (id, claim) pair it fetches the real catalogue title and asks a plain question:

    does the fetched title belong to the work the answer named?

Scoring is deliberately conservative and mechanical. A claim passes only on a real token
overlap with the fetched title; anything else is UNMATCHED, which is NOT an accusation of
lying -- it is a refusal to promote. Several causes are enumerated in the output so the
distinction stays visible:

  MATCHED    - token overlap confirms the handle belongs to the claimed work
  UNMATCHED  - the handle is live but the fetched title does not support the claim
  NO_CLAIM   - the answer cited a bare number with no work named near it (unusable as a lead)
  UNFETCHED  - the catalogue page could not be read this run

Read-only. Fetches catalogue metadata, not book bodies.
"""
from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "memory" / "runs" / "corpus_gap_research" / "CORPUS_GAP_RESEARCH.md"
OUT = ROOT / "memory" / "runs" / "corpus_gap_research"
UA = {"User-Agent": "local-sovereign-agent/1.0 (corpus lead verification; catalogue metadata only)"}

STOP = {
    "the", "a", "an", "of", "and", "or", "in", "on", "to", "for", "by", "with", "from", "is",
    "was", "it", "its", "as", "at", "that", "this", "be", "de", "la", "le", "el", "von", "der",
    "book", "volume", "vol", "part", "edition", "ed", "novel", "story", "tales", "tale",
    "and", "mr", "mrs", "dr", "sir", "lord", "lady", "his", "her", "their", "other", "short",
}


def _norm(s: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9']{3,}", (s or "").lower()) if t not in STOP}


def _title(gid: str) -> tuple[int, str]:
    try:
        req = urllib.request.Request(f"https://www.gutenberg.org/ebooks/{gid}", headers=UA)
        with urllib.request.urlopen(req, timeout=20) as r:
            html = r.read(300_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception:
        return 0, ""
    m = re.search(r"<title>([^<]*)", html)
    return 200, (m.group(1) if m else "").replace(" | Project Gutenberg", "").strip()


def _nearest_claim(qid: str) -> list[str]:
    """The text surrounding each bare Gutenberg id inside one answer."""
    if not PACK.is_file():
        return []
    lines = PACK.read_text(encoding="utf-8", errors="replace").splitlines()
    out, cur = [], None
    for ln in lines:
        m = re.match(r"^### ([A-Z]\d{2}) — ", ln)
        if m:
            cur = m.group(1)
        if cur != qid:
            continue
        for mm in re.finditer(r"\b(?:gutenberg|pg)\s*#?\s*(\d{3,6})\b", ln, re.IGNORECASE):
            lo = max(0, mm.start() - 150)
            hi = min(len(ln), mm.end() + 150)
            out.append(ln[lo:hi])
    return out


def main() -> int:
    # claimed work text, keyed (qid -> gutenberg id) from the pack
    pairs: dict[tuple[str, str], str] = {}
    if PACK.is_file():
        cur = None
        for ln in PACK.read_text(encoding="utf-8", errors="replace").splitlines():
            m = re.match(r"^### ([A-Z]\d{2}) — (.+)$", ln)
            if m:
                cur = m.group(1)
                continue
            if cur is None:
                continue
            for mm in re.finditer(r"\b(?:gutenberg|pg)\s*#?\s*(\d{3,6})\b", ln, re.IGNORECASE):
                lo, hi = max(0, mm.start() - 200), min(len(ln), mm.end() + 120)
                pairs.setdefault((cur, mm.group(1)), ln[lo:hi])

    results = []
    for (qid, gid), claim in sorted(pairs.items()):
        status, title = _title(gid)
        c_tokens, t_tokens = _norm(claim), _norm(title)
        if status != 200:
            verdict = "UNFETCHED" if status == 0 else f"HTTP_{status}"
        elif not c_tokens:
            verdict = "NO_CLAIM"
        else:
            inter = c_tokens & t_tokens
            # a work's distinctive token must survive: 1 shared non-stopword is weak evidence,
            # so require >=2 OR a long shared token (>=7 chars) to call it matched.
            strong = {t for t in inter if len(t) >= 7}
            verdict = "MATCHED" if (len(inter) >= 2 or strong) else "UNMATCHED"
        results.append({"qid": qid, "gutenberg_id": gid, "status": status,
                        "fetched_title": title, "verdict": verdict,
                        "overlap": sorted((_norm(claim) & _norm(title)))[:8],
                        "claim_context": claim.strip()[:200]})

    tally = Counter(r["verdict"] for r in results)
    scored = tally["MATCHED"] + tally["UNMATCHED"]
    v = {
        "schema": "gutenberg_title_match.v1",
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "law": "a lead is promoted by title-match, never by status-match",
        "pairs": len(results), "tally": dict(tally),
        "promotable_rate": (round(100 * tally["MATCHED"] / scored, 1) if scored else None),
        "note": ("UNMATCHED is a refusal to promote, not a claim of fabrication: the token test "
                 "is mechanical and will fail on paraphrases and on titles the answer described "
                 "rather than named. The hand-check in docs/ref/LEAD_VERIFICATION_20260928.md is "
                 "the adjudicated sample: 10/17 confirmed, 7 wrong, all 7 still HTTP 200."),
        "results": results,
    }
    (OUT / "gutenberg_title_match.json").write_text(json.dumps(v, indent=2, ensure_ascii=False), encoding="utf-8")

    L = ["# GUTENBERG TITLE-MATCH — live handles vs the work each answer named", "",
         f"*{v['pairs']} (qid, id) pairs · {v['tally']} · "
         f"promotable {v['promotable_rate']}% of scorable · {v['ts']}*", "",
         f"> **{v['law']}**", "",
         "| verdict | n |", "|---|---:|"]
    for k, n in tally.most_common():
        L.append(f"| {k} | {n} |")
    L += ["", "## UNMATCHED — live handle, claim not supported by the fetched title", "",
          "| id | fetched title | claimed context (trimmed) |", "|---|---|---|"]
    for r in [x for x in results if x["verdict"] == "UNMATCHED"][:40]:
        t = r["claim_context"].replace("|", "/").replace("\n", " ")
        L.append(f"| {r['gutenberg_id']} | {r['fetched_title'][:44]} | {t[:110]} |")
    L += ["", "## MATCHED — promotable once hashed and landed", "",
          "| id | fetched title | qid |", "|---|---|---|"]
    for r in [x for x in results if x["verdict"] == "MATCHED"][:60]:
        L.append(f"| {r['gutenberg_id']} | {r['fetched_title'][:54]} | {r['qid']} |")
    L += ["", "## Reading the numbers honestly", "", v["note"]]
    (OUT / "GUTENBERG_TITLE_MATCH.md").write_text("\n".join(L), encoding="utf-8")
    print(json.dumps({"pairs": v["pairs"], "tally": v["tally"],
                      "promotable_rate": v["promotable_rate"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
