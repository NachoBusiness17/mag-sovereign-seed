"""arxiv_harvest — the day's journals, recorded, massaged, mined against ourselves.

2026-09-05, operator: "an arxiv page with all the journals of the day... scroll
down every last one... record all the data into text files, massage it, mine it
against ourselves, then feed it to research — opportunities to make ourselves
truly stateless."

One pass, all stdlib:
  1. RECORD  — arXiv Atom API (export.arxiv.org, free, no key) per category,
     newest submissions -> corpus/arxiv/<date>/<id>.txt (title/authors/abstract).
  2. MASSAGE — digest.jsonl (normalized rows), deduped against prior days.
  3. MINE    — flash pass scores each title/abstract against the fleet's
     interest map (falsifiers, caching, orchestration/stigmergy, game-benchmarks/
     evals, provenance, training-data). Top hits become research-inbox drops.

Stateless by construction: everything lands as files; any seat, any era reads.
Mimosa-hardened: https-only literal host, size cap, DOCTYPE/ENTITY refusal
(billion-laughs class), no redirects.

Standalone:  python -m mag.arxiv_harvest [MAX_PER_CAT]
"""

from __future__ import annotations

import datetime
import io
import json
import re
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
ATOM = "https://export.arxiv.org/api/query"
CATEGORIES = ["cs.AI", "cs.LG", "cs.CL"]
# state/ is bind-mounted into the cage — corpus/ is host-only (unmounted),
# and a harvest the next recreate deletes is not stateless. (09-05 catch.)
OUT = ROOT / "state" / "arxiv"
_MAX_BYTES = 4_000_000
NS = {"a": "http://www.w3.org/2005/Atom"}

INTEREST_MAP = (
    "- agent verification, falsifiers, invariant checkers, eval harnesses (0.1% hole)\n"
    "- prompt/context caching, inference economics (0.0% hole)\n"
    "- multi-agent orchestration, stigmergy, stateless coordination, signed leases\n"
    "- game/virtual environments as benchmarks, open-world evaluation\n"
    "- provenance, audit trails, signed receipts for agent actions (3.6% — steal pass)\n"
    "- training data from agent traces, distillation of reasoning\n"
    "- LLM inference serving at high concurrency (the wall-of-agents)\n"
    "Score 0 (irrelevant), 1 (tangential), 2 (directly useful), 3 (moat-relevant)."
)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ARG002
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def _fetch_cat(cat: str, limit: int) -> list[dict[str, Any]]:
    url = (f"{ATOM}?search_query=cat:{cat}&sortBy=submittedDate"
           f"&sortOrder=descending&max_results={limit}")
    if not url.startswith("https://export.arxiv.org/"):
        raise ValueError("blocked: non-arxiv url")
    raw = None
    for _hop in range(2):  # one same-host redirect allowed (arxiv 301s canonical urls)
        try:
            with _OPENER.open(url, timeout=60) as r:
                raw = r.read(_MAX_BYTES + 1)
            break
        except urllib.request.HTTPError as e:
            if e.code in (301, 302, 303, 307) and _hop == 0:
                loc = e.headers.get("Location", "")
                if not loc.startswith("https://export.arxiv.org/"):
                    raise ValueError(f"blocked: redirect off-host: {loc[:80]}")
                url = loc
                continue
            raise
    if raw is None:
        raise ValueError("no response")
    if len(raw) > _MAX_BYTES:
        raise ValueError("blocked: response over 4MB cap")
    text = raw.decode("utf-8", errors="replace")
    low = text[:200000].lower()
    if "<!doctype" in low or "<!entity" in low:
        raise ValueError("blocked: DOCTYPE/ENTITY in response — XML entity expansion")
    root = ET.fromstring(text)
    out = []
    for e in root.findall("a:entry", NS):
        aid = (e.findtext("a:id", "", NS) or "").rsplit("/", 1)[-1]
        out.append({
            "id": aid,
            "cat": cat,
            "title": re.sub(r"\s+", " ", e.findtext("a:title", "", NS)).strip(),
            "authors": [a.findtext("a:name", "", NS) for a in e.findall("a:author", NS)],
            "published": (e.findtext("a:published", "", NS) or "")[:10],
            "abstract": re.sub(r"\s+", " ", e.findtext("a:summary", "", NS)).strip(),
        })
    return out


def _massage(papers: list[dict], day: str) -> tuple[list[dict], int]:
    """Normalize + dedupe against prior digests. Returns (new, skipped)."""
    seen: set[str] = set()
    for f in OUT.glob("*/digest.jsonl"):
        for line in io.open(f, encoding="utf-8", errors="replace"):
            try:
                seen.add(json.loads(line).get("id", ""))
            except Exception:  # noqa: BLE001
                pass
    fresh = [p for p in papers if p["id"] and p["id"] not in seen]
    d = OUT / day
    d.mkdir(parents=True, exist_ok=True)
    with io.open(d / "digest.jsonl", "a", encoding="utf-8") as f:
        for p in fresh:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
            body = (f"# {p['title']}\n\narXiv:{p['id']} ({p['cat']}, {p['published']})\n"
                    f"Authors: {', '.join(a for a in p['authors'] if a)}\n\n"
                    f"{p['abstract']}\n")
            safe = re.sub(r"[^A-Za-z0-9._-]", "_", p["id"])
            io.open(d / f"{safe}.txt", "w", encoding="utf-8").write(body)
    return fresh, len(papers) - len(fresh)


def _mine(fresh: list[dict], limit_hits: int = 6) -> list[dict]:
    """Flash pass: score fresh titles against the interest map; keep hits >= 2."""
    if not fresh:
        return []
    listing = "\n".join(f"{p['id']} | {p['title']} | {p['abstract'][:180]}"
                        for p in fresh[:80])
    from mag.lane_runner import flash_call
    out = flash_call(
        "You score arXiv papers for a fleet that builds: agent verification/falsifiers, "
        "context caching, stigmergic multi-agent orchestration, game-environment "
        "benchmarks, provenance/audit, agent-trace training data, high-concurrency "
        "inference. Our interest map:\n" + INTEREST_MAP +
        "\n\nOutput ONLY a JSON array of papers scoring 2 or 3: "
        '[{"id": "...", "score": 2, "why": "one line"}]. Nothing else.',
        listing, max_tokens=800)
    i, j = out.find("["), out.rfind("]")
    if not (0 <= i < j):
        return []
    try:
        hits = [h for h in json.loads(out[i:j + 1]) if int(h.get("score", 0)) >= 2]
    except Exception:  # noqa: BLE001
        return []
    return hits[:limit_hits]


def harvest(max_per_cat: int = 100) -> dict[str, Any]:
    day = datetime.date.today().isoformat()
    papers: list[dict] = []
    for cat in CATEGORIES:
        try:
            papers += _fetch_cat(cat, max_per_cat)
        except Exception as e:  # noqa: BLE001 — one dead category never kills the harvest
            papers.append({"id": "", "cat": cat, "title": f"FETCH FAIL {e}",
                           "authors": [], "published": day, "abstract": ""})
    papers = [p for p in papers if p["id"]]
    fresh, skipped = _massage(papers, day)
    hits = _mine(fresh)
    inbox = ROOT / "queue" / "lanes" / "research" / "INBOX"
    inbox.mkdir(parents=True, exist_ok=True)
    if hits:
        body = "\n".join(f"- arXiv:{h['id']} (score {h.get('score')}) — {h.get('why', '')}"
                         for h in hits)
        (inbox / f"arxiv_{day.replace('-', '')}.md").write_text(
            f"**ARXIV HARVEST — {day}: {len(fresh)} new, top {len(hits)} mined against "
            f"our interest map** (UNPROVEN leads)\n\n{body}\n", encoding="utf-8")
    return {"day": day, "fetched": len(papers), "new": len(fresh), "skipped": skipped,
            "hits": len(hits), "hit_ids": [h.get("id") for h in hits]}


if __name__ == "__main__":
    import sys
    print(json.dumps(harvest(int(sys.argv[1]) if len(sys.argv) > 1 else 100)))
