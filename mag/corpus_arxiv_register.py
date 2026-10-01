"""Verify the librarian's UNREGISTERED list — 933 citations with no map row.

`mag.librarian.py` reports 933 arXiv ids cited in watch/docs/mag cards but absent from
docs/ref/BIBLIOGRAPHY_MAP.md. That is a REGISTER gap by construction: the librarian never asks
whether the id exists, only whether the map mentions it. The operator's CITATION LAW ("a wrong
citation is worse than an honest gap") applies with full force here, because a hallucinated id
registered into the map would be worse than the gap it papered over.

So: resolve every id against the arXiv API and record what is real. arXiv returns 200 with a
`title` for a live id and 404 for a dead one -- a genuine verdict, unlike a bot-blocked 403.

The librarian's OWN audit found that a stored key is not a live lane, so I check the endpoint
with a control id first: if the control fails, the whole census is inconclusive and says so.

Writes memory/runs/corpus_gap_research/ARXIV_REGISTER.json + ARXIV_REGISTER.md
Read-only metadata, $0, no keys.
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
REPORT = ROOT / "watch" / "LIBRARIAN_REPORT.md"
OUT = ROOT / "memory" / "runs" / "corpus_gap_research"
UA = {"User-Agent": "local-sovereign-agent/1.0 (librarian register audit; metadata only)"}

ARXIV_LINE = re.compile(r"^-\s*(arxiv:(\d{4}\.\d{4,5})[^ ]*)\s*←\s*(.+)$")
CONTROL = "1706.03762"          # "Attention Is All You Need" -- certainly live, not from the report


def _fetch(url: str, tries: int = 2, timeout: int = 20) -> tuple[int, str]:
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status, r.read(200_000).decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            return e.code, ""
        except Exception:
            if i == tries - 1:
                return 0, ""
    return 0, ""


def _probe(aid: str) -> dict:
    status, body = _fetch(f"https://arxiv.org/abs/{aid}")
    title = ""
    if status == 200:
        m = re.search(r'<meta name="citation_title" content="([^"]*)"', body)
        title = m.group(1) if m else ""
    if title:
        return {"arxiv_id": aid, "status": status, "title": title, "exists": True,
                "via": "abs"}

    # FALLBACK. Measured 2026-09-29: 29 of 933 ids returned HTTP 406 from arxiv.org/abs. A 406
    # is "not acceptable" -- a content-negotiation refusal, NOT a dead paper. Re-querying those
    # through the export API resolves several (1806.10433 and 1906.09444 both came back with
    # real titles), so 406 is inconclusive on its own and must never be counted as DEAD.
    est, ebody = _fetch(f"http://export.arxiv.org/api/query?id_list={aid}")
    if est == 200:
        entries = re.findall(r"<entry>(.*?)</entry>", ebody, re.S)
        if entries:
            mt = re.search(r"<title>(.*?)</title>", entries[0], re.S)
            if mt:
                return {"arxiv_id": aid, "status": est, "title": mt.group(1).strip(),
                        "exists": True, "via": "export-api"}
    return {"arxiv_id": aid, "status": status, "title": "", "exists": False, "via": "abs"}


def main() -> int:
    if not REPORT.is_file():
        print("no librarian report; run `python -m mag.librarian` first", file=sys.stderr)
        return 2
    unreg: list[tuple[str, str]] = []
    section = ""
    for line in REPORT.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("## "):
            section = line[3:].split("(")[0].strip().upper()
            continue
        if not section.startswith("UNREGISTERED"):
            continue
        m = ARXIV_LINE.match(line.strip())
        if m:
            unreg.append((m.group(2), m.group(3).strip()))

    c_status, c_body = _fetch(f"https://arxiv.org/abs/{CONTROL}")
    control_ok = c_status == 200 and 'name="citation_title"' in c_body

    with ThreadPoolExecutor(max_workers=6) as pool:
        probed = list(pool.map(_probe, [a for a, _ in unreg]))

    # A second pass for whatever the abs page could not resolve, so the export fallback is not
    # competing with 933 other requests for the same rate limit.
    stuck = [p["arxiv_id"] for p in probed if not p.get("exists")]
    if stuck:
        with ThreadPoolExecutor(max_workers=2) as pool:
            retry = {r["arxiv_id"]: r for r in pool.map(_probe, stuck)}
        for p in probed:
            if not p.get("exists") and retry.get(p["arxiv_id"], {}).get("exists"):
                probed[probed.index(p)] = retry[p["arxiv_id"]]

    tally = Counter()
    rows = []
    for (aid, cited_in), res in zip(unreg, probed):
        if not control_ok:
            verdict = "INCONCLUSIVE"
        elif res["status"] == 200 and res["title"]:
            verdict = "REAL"
        elif res["status"] == 404:
            verdict = "DEAD"
        elif res["status"] == 0:
            verdict = "UNFETCHED"
        else:
            verdict = f"HTTP_{res['status']}"
        tally[verdict] += 1
        rows.append({"arxiv_id": aid, "cited_in": cited_in, "verdict": verdict,
                     "title": res["title"]})

    real = tally.get("REAL", 0)
    dead = tally.get("DEAD", 0)
    control = {"id": CONTROL, "status": c_status, "metadata_visible": control_ok,
               "reading": ("arXiv answers with real metadata for this client" if control_ok
                           else "arXiv is not answering with metadata; every verdict below is "
                                "INCONCLUSIVE and nothing is claimed about the citations")}
    v = {
        "schema": "arxiv_register.v1",
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "law": "a wrong citation is worse than an honest gap",
        "control": control,
        "unregistered_count": len(unreg), "tally": dict(tally),
        "real_rate_pct": round(100 * real / max(1, len(unreg)), 1) if control_ok else None,
        "note": ("The librarian reports ids that are absent from the MAP. That is a register "
                 "gap, not necessarily a truth problem -- these ids are used in real receipts. "
                 "This module separates the two: an id can be perfectly real and still "
                 "unregistered. Registering a DEAD id would be the harm, so the dead set is the "
                 "actionable half."),
        "results": rows,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "ARXIV_REGISTER.json").write_text(json.dumps(v, indent=2, ensure_ascii=False), encoding="utf-8")

    L = ["# ARXIV REGISTER — the librarian's 933 unregistered citations, resolved", "",
         f"*{v['unregistered_count']} ids cited in cards but absent from the map · {v['tally']}"
         + (f" · real {v['real_rate_pct']}%" if v["real_rate_pct"] is not None else "") + "*", "",
         f"> **{v['law']}**", "",
         "## Control", "",
         f"`{CONTROL}` → HTTP {c_status}, metadata visible: {control_ok}. **{control['reading']}**", ""]
    if control_ok:
        L += ["## What this means", "", v["note"], "",
              f"**{real} of {v['unregistered_count']} are real papers that simply never made it "
              f"into the map. {dead} are dead.** Registering the real ones is a genuine "
              "improvement to the bibliography; registering the dead ones would manufacture "
              "false citations, which the citation law forbids.", ""]
    else:
        L += ["No verdict is claimed. Re-run when the endpoint answers with metadata.", ""]
    if dead:
        L += ["## DEAD ids — do not register", "", "| id | cited in |", "|---|---|"]
        for r in [x for x in rows if x["verdict"] == "DEAD"][:40]:
            L.append(f"| `{r['arxiv_id']}` | {r['cited_in'][:70]} |")
        L.append("")
    (OUT / "ARXIV_REGISTER.md").write_text("\n".join(L), encoding="utf-8")
    print(json.dumps({k: v[k] for k in ("unregistered_count", "tally", "real_rate_pct")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
