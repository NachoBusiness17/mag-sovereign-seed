"""Byte-check EVERY identifier the 57 answers assert — the promotion gate, run over the whole pack.

The 17-ID sample measured a 41% false rate. That sample was hand-picked, so it is not evidence
about the other 40 answers. This extracts every checkable handle the pack asserts (Gutenberg
IDs, DOIs, arXiv ids, archive.org identifiers, bare URLs) and checks each one by TITLE or
resolving it, never by status code.

Free, no keys, no downloads of copyrighted bodies: for Gutenberg we read the catalogue page
title; for a URL we record whether it resolves. A row becomes a FACT only when the fetched
text says the thing the lead claims.

Writes: memory/runs/corpus_gap_research/VERIFY.md + verify.json (append-only, re-runnable).
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
RAW = ROOT / "memory" / "runs" / "corpus_gap_research" / "raw.jsonl"
OUT = ROOT / "memory" / "runs" / "corpus_gap_research"
UA = {"User-Agent": "local-sovereign-agent/1.0 (corpus lead verification; no scraping of bodies)"}

# --- identifier grammars, deliberately tight so we do not harvest noise -------------------
GUTENBERG = re.compile(r"\b(?:gutenberg|pg)\s*#?\s*(\d{3,6})\b", re.IGNORECASE)
GUTENBERG_URL = re.compile(r"gutenberg\.org/(?:ebooks|files|cache/epub)/(\d{3,6})", re.IGNORECASE)
ARXIV = re.compile(r"\barxiv[:\s/]+(\d{4}\.\d{4,5})(?:v\d+)?\b", re.IGNORECASE)
DOI = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Za-z0-9]+\b")
URL = re.compile(r"https?://[^\s\)\]\}\>,;'\"`]+")


def _fetch(url: str, timeout: int = 20) -> tuple[int, str]:
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(400_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception:
        return 0, ""


def _gutenberg_title(gid: str) -> tuple[int, str]:
    status, html = _fetch(f"https://www.gutenberg.org/ebooks/{gid}")
    m = re.search(r"<title>([^<]*)", html)
    title = (m.group(1) if m else "").replace(" | Project Gutenberg", "").strip()
    return status, title


def extract() -> list[dict]:
    """Every asserted handle, with the qid and the sentence that asserted it."""
    rows: list[dict] = []
    if not PACK.is_file():
        return rows
    text = PACK.read_text(encoding="utf-8", errors="replace")
    qid = None
    for line in text.splitlines():
        m = re.match(r"^### ([A-Z]\d{2}) — (.+)$", line)
        if m:
            qid, question = m.group(1), m.group(2)
            continue
        if qid is None:
            continue
        ids = set()
        for g in GUTENBERG.findall(line) + GUTENBERG_URL.findall(line):
            ids.add(("gutenberg", g))
        for a in ARXIV.findall(line):
            ids.add(("arxiv", a))
        for d in DOI.findall(line):
            ids.add(("doi", d.rstrip(".")))
        for u in URL.findall(line):
            ids.add(("url", u.rstrip(".,);")))
        for kind, ident in sorted(ids):
            rows.append({"qid": qid, "question": question, "kind": kind, "id": ident,
                         "asserted_in": line.strip()[:240]})
    # de-dup on (kind,id) but keep every qid that asserted it
    seen: dict[tuple, set] = {}
    for r in rows:
        seen.setdefault((r["kind"], r["id"]), set()).add(r["qid"])
    out = []
    for (kind, ident), qids in sorted(seen.items()):
        out.append({"kind": kind, "id": ident, "qids": sorted(qids), "n_answers": len(qids)})
    return out


def verify(items: list[dict]) -> dict:
    checked = []
    for it in items:
        rec = dict(it)
        if it["kind"] == "gutenberg":
            status, title = _gutenberg_title(it["id"])
            rec.update(status=status, resolved_title=title,
                       verdict="resolves" if status == 200 else f"HTTP {status}")
        elif it["kind"] == "arxiv":
            status, body = _fetch(f"https://arxiv.org/abs/{it['id']}")
            m = re.search(r'<meta name="citation_title" content="([^"]*)"', body)
            rec.update(status=status, resolved_title=(m.group(1) if m else ""),
                       verdict="resolves" if status == 200 else f"HTTP {status}")
        elif it["kind"] == "doi":
            status, _ = _fetch(f"https://doi.org/{it['id']}", timeout=25)
            rec.update(status=status, resolved_title="", verdict="resolves" if status in (200, 302) else f"HTTP {status}")
        else:
            status, _ = _fetch(it["id"], timeout=15)
            rec.update(status=status, resolved_title="",
                       verdict="resolves" if status in (200, 301, 302) else f"HTTP {status}")
        checked.append(rec)
    return {
        "schema": "corpus_lead_verify.v1",
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "law": "a lead is promoted by title-match, never by status-match",
        "pack": str(PACK.relative_to(ROOT)).replace("\\", "/"),
        "handles_claimed": len(checked),
        "by_kind": dict(Counter(c["kind"] for c in checked)),
        "resolves": sum(1 for c in checked if c["verdict"] == "resolves"),
        "dead": sum(1 for c in checked if c["verdict"] != "resolves"),
        "checks": checked,
    }


def report(v: dict) -> str:
    L = [
        "# LEAD VERIFY — every identifier the 57 answers assert, byte-checked",
        "",
        f"*{v['handles_claimed']} handles · {v['resolves']} resolve · {v['dead']} dead · "
        f"by kind: {v['by_kind']} · generated {v['ts']}*",
        "",
        f"> **{v['law']}**",
        "",
        "| kind | id | resolves | status | real title (Gutenberg/arXiv) | asserted by |",
        "|---|---|---|---|---|---|",
    ]
    for c in sorted(v["checks"], key=lambda x: (x["kind"], str(x["id"]))):
        ok = "yes" if c["verdict"] == "resolves" else "**NO**"
        L.append(f"| {c['kind']} | `{c['id']}` | {ok} | {c['verdict']} | "
                 f"{c.get('resolved_title','')[:52] or '—'} | {','.join(c['qids'])} |")
    L += ["", "## What this does NOT prove", "",
          "A 200 on a Gutenberg ID does not make the lead right. The 17-ID hand-check found 7",
          "wrong IDs that ALL returned 200 — the author and title were right, the handle invented.",
          "So the table above is a *liveness* census, not a *truth* census. Truth requires a",
          "human/LLM comparison of `resolved_title` against what the lead claimed, per row.",
          "Verified wrong-handle evidence: `docs/ref/LEAD_VERIFICATION_20260928.md`."]
    return "\n".join(L)


if __name__ == "__main__":
    items = extract()
    v = verify(items)
    (OUT / "verify.json").write_text(json.dumps(v, indent=2, ensure_ascii=False), encoding="utf-8")
    (OUT / "VERIFY.md").write_text(report(v), encoding="utf-8")
    print(json.dumps({k: v[k] for k in ("handles_claimed", "by_kind", "resolves", "dead")}, indent=2))
    print("->", (OUT / "VERIFY.md").relative_to(ROOT))
