"""Byte-check the Internet Archive identifiers the pack cites -- the axis never verified.

The B09 (science history), B11 (medicine) and several G-theme answers cite archive.org item
identifiers rather than Project Gutenberg numbers. Those were never put through a check, and
`corpus_lead_verify` only recognises Gutenberg/DOI/arXiv/URL grammars, so this whole citation
axis has been sitting unverified while the pack reads as well-sourced.

archive.org is better behaved than doi.org for this: `archive.org/metadata/<id>` is a public
JSON endpoint that answers 200 with real metadata or 404 when the item is absent, and it
carries the item's own title. So this is the same law applied to a second registry:

    a lead is promoted by title-match, never by status-match

Writes: memory/runs/corpus_gap_research/archive_check.json + ARCHIVE_CHECK.md
Read-only metadata fetches; no book bodies, no fulltext, $0, no keys.
"""
from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "memory" / "runs" / "corpus_gap_research" / "CORPUS_GAP_RESEARCH.md"
OUT = ROOT / "memory" / "runs" / "corpus_gap_research"
UA = {"User-Agent": "local-sovereign-agent/1.0 (corpus lead verification; item metadata only)"}

STOP = {"the", "a", "an", "of", "and", "or", "in", "on", "to", "for", "by", "with", "from", "is",
        "was", "it", "its", "as", "at", "that", "this", "be", "history", "volume", "vol"}

# an archive.org item id: lowercase alnum + dashes, 8+ chars, usually ending in a year-suffix
ARCHIVE_ID = re.compile(r"`([a-z0-9][a-z0-9\-_]{7,40})`")
ARCHIVE_URL = re.compile(r"archive\.org/(?:details|download|stream)/([A-Za-z0-9\-_.]{6,60})")
# the words we must NOT treat as ids
NOT_ID = {"gutenberg.org", "example.com", "doi.org", "wikipedia.org"}


def _norm(s: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9']{3,}", (s or "").lower()) if t not in STOP}


def agree(claim: str, fetched: str) -> bool:
    c, f = _norm(claim), _norm(fetched)
    if not c or not f:
        return False
    if c == f:
        return True
    inter = c & f
    if not inter:
        return False
    distinctive = {t for t in c if len(t) >= 5}
    if distinctive and distinctive <= f:
        return True
    return any(len(t) >= 6 for t in inter)


def _meta(item: str) -> tuple[int, str, str, bool]:
    """(status, title, creator, is_dark) from the public metadata endpoint.

    MEASURED DEFECT: archive.org answers HTTP 200 with an EMPTY `metadata` object for items it
    marks `is_dark`. A dark item is a real, existing record that the archive is withholding
    catalogue data from, not a missing one. The first version scored every dark item as
    UNMATCHED because title and creator came back empty -- which would have reported 73 wrong
    identifiers when most were dark-but-real. `is_dark` is now reported separately and never
    counted as a mismatch.
    """
    try:
        req = urllib.request.Request(f"https://archive.org/metadata/{item}", headers=UA)
        with urllib.request.urlopen(req, timeout=25) as r:
            d = json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        return e.code, "", "", False
    except Exception:
        return 0, "", "", False
    md = d.get("metadata") or {}
    title = md.get("title") or ""
    creator = md.get("creator") or ""
    if isinstance(creator, list):
        creator = " ".join(map(str, creator))
    return 200, str(title), str(creator), bool(d.get("is_dark"))


def extract() -> list[dict]:
    if not PACK.is_file():
        return []
    rows, qid = [], None
    for line in PACK.read_text(encoding="utf-8", errors="replace").splitlines():
        m = re.match(r"^### ([A-Z]\d{2}) — (.+)$", line)
        if m:
            qid, question = m.group(1), m.group(2)
            continue
        if qid is None:
            continue
        ids = set(ARCHIVE_URL.findall(line))
        for tok in ARCHIVE_ID.findall(line):
            if any(bad in tok for bad in NOT_ID):
                continue
            # item ids in this pack look like `wordword00surn` or `titleofwork00auth`
            if re.search(r"\d{2}([a-z]{4,})$", tok) or re.search(r"\d{4}[a-z]{2}$", tok):
                ids.add(tok)
        for i in ids:
            rows.append({"qid": qid, "question": question, "id": i, "line": line.strip()[:200]})
    seen: dict[str, set] = {}
    for r in rows:
        seen.setdefault(r["id"], set()).add(r["qid"])
    return [{"id": i, "qids": sorted(q), "n_answers": len(q)} for i, q in sorted(seen.items())]


def _claim_for(item: str) -> str:
    """The WORK title the answer named next to this identifier.

    The first version took the first italic span on the citing line, which on a B09-style bullet
    (`**Whewell, W.** *History of the Inductive Sciences* (1857). Internet Archive ID: ...`) is
    often the AUTHOR in the pack's markdown, not the work -- so it compared "Mach, E." against a
    catalogue title and called it a mismatch. Now: prefer an explicit `Author, *Work*` shape,
    then the first italic span, then fall back to the catalogue title (NO_CLAIM).
    """
    if not PACK.is_file():
        return ""
    for line in PACK.read_text(encoding="utf-8", errors="replace").splitlines():
        if item not in line:
            continue
        # **Author, I.** *Work*  -> take the italic span that is not the author blob
        italics = re.findall(r"(?<!\*)\*([^*\n]{4,90})\*(?!\*)", line)
        if italics:
            # an italic span that looks like a name (Surname, X.) is an author, not a work
            for it in italics:
                if not re.match(r"^[A-Z][a-z]+,?\s+[A-Z]?\.?$", it.strip()):
                    return it.strip()
            return italics[-1].strip()
        m = re.search(r"([A-Z][A-Za-z'\-]+(?:\s+[A-Z][A-Za-z'\-]+)*),\s*\d{4}", line)
        if m:
            return m.group(1)
    return ""


def check_one(it: dict) -> dict:
    status, title, creator, dark = _meta(it["id"])
    claim = _claim_for(it["id"])
    if status != 200:
        verdict = "UNFETCHED" if status == 0 else f"HTTP_{status}"
    elif dark or not title:
        # real record, catalogue withheld. Not a mismatch, and not evidence either way.
        verdict = "DARK" if dark else "NO_METADATA"
    elif not claim:
        verdict = "NO_CLAIM"
    else:
        verdict = "MATCHED" if agree(claim, title) or agree(claim, creator) else "UNMATCHED"
    return {**it, "status": status, "fetched_title": title, "fetched_creator": creator,
            "is_dark": dark, "claim": claim, "verdict": verdict}


def main() -> int:
    items = extract()
    with ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(check_one, items))

    # CONTROL. Before reporting any archive.org absence, prove the endpoint will even answer
    # for an item that is certainly real. Measured 2026-09-29: `adventuresofsherl00doyle` (Doyle,
    # certain to exist) and `analysissensatio00mach` BOTH return HTTP 200 with an EMPTY metadata
    # object from this client, so archive.org is withholding catalogue data here rather than
    # reporting absence. Without this control the first run scored 68 of 79 identifiers as
    # "no metadata" -- i.e. as fabricated -- which the control shows is an artefact.
    CONTROL = "adventuresofsherl00doyle"          # certainly real, deliberately not in the pack
    c_status, c_title, _, c_dark = _meta(CONTROL)
    control_ok = bool(c_title)
    control = {
        "item": CONTROL, "status": c_status, "title": c_title, "is_dark": c_dark,
        "metadata_visible": control_ok,
        "reading": ("the endpoint answers with real metadata for this client" if control_ok else
                    "the endpoint WITHHOLDS metadata for this client; empty metadata therefore "
                    "carries NO information about whether an identifier exists"),
    }

    tally = Counter(r["verdict"] for r in rows)
    scorable = tally["MATCHED"] + tally["UNMATCHED"]
    absent = tally.get("NO_METADATA", 0)
    v = {
        "schema": "archive_check.v1",
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "law": "a lead is promoted by title-match, never by status-match",
        "registry": "https://archive.org/metadata/<item>",
        "control": control,
        "items_claimed": len(rows), "tally": dict(tally),
        "promotable_rate": (round(100 * tally["MATCHED"] / scorable, 1) if scorable else None),
        "absent_verdict_valid": control_ok,
        "inconclusive": absent if not control_ok else 0,
        "note": ("UNMATCHED is a refusal to promote, not an accusation. The claim is the work "
                 "title the answer named beside the identifier. Critically: if control."
                 "metadata_visible is false, every NO_METADATA row is INCONCLUSIVE -- this client "
                 "is being served an empty metadata envelope, so an empty reply proves nothing "
                 "about the identifier. Those rows need a different client (browser UA, or the "
                 "item page itself) before any of them is called absent."),
        "results": rows,
    }
    (OUT / "archive_check.json").write_text(json.dumps(v, indent=2, ensure_ascii=False), encoding="utf-8")

    L = ["# ARCHIVE.ORG CHECK — the citation axis that was never verified", "",
         f"*{v['items_claimed']} archive.org identifiers cited by the pack · {v['tally']} · "
         f"promotable {v['promotable_rate']}% of scorable · {v['ts']}*", "",
         f"> **{v['law']}**", "",
         "## CONTROL — read this before reading any count", "",
         f"Control item `{control['item']}` (certainly real, deliberately not in the pack): "
         f"HTTP {control['status']}, metadata title = "
         f"`{control['title'] or '(empty)'}`.", "",
         f"**{control['reading']}**", ""]
    if not control_ok:
        L += [f"So the {v['inconclusive']} `NO_METADATA` rows below are **inconclusive, not "
              "absent**. The first run of this module reported them as missing identifiers, which "
              "the control shows was an artefact of the client, not a property of the leads. "
              "They are not counted against the pack.", ""]
    L += ["| verdict | n |", "|---|---:|"]
    for k, n in tally.most_common():
        L.append(f"| {k} | {n} |")
    L += ["", "## The axis, item by item", "",
          "| item | verdict | real title | real creator | claimed | qid |", "|---|---|---|---|---|---|"]
    for r in sorted(rows, key=lambda x: (x["verdict"], x["id"])):
        L.append(f"| `{r['id'][:34]}` | {r['verdict']} | {r['fetched_title'][:40]} | "
                 f"{r['fetched_creator'][:22]} | {r['claim'][:28]} | {','.join(r['qids'])} |")
    L += ["", "## Reading it honestly", "", v["note"]]
    (OUT / "ARCHIVE_CHECK.md").write_text("\n".join(L), encoding="utf-8")
    print(json.dumps({"items_claimed": v["items_claimed"], "tally": v["tally"],
                      "promotable_rate": v["promotable_rate"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
