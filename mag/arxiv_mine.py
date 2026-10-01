"""arxiv_mine — mine arXiv the same way we steal.

arXiv is a tier-A research source (configs/improve.yaml, data_source_watch arxiv_agent_memory).
"Mine it the same way we steal": pull the listing, extract each paper's novel claim
(title + abstract), route it through the ONE primitive
(swarm_surface.route_novel -> dedupe by content anchor + enqueue to the SWARM research queue)
so a frontier seat mines/refines it in-cluster, record the anchor to a durable ledger, and fold.
Idempotent (dedupe by anchor) — re-running never double-enqueues. Deterministic, stdlib only.

CLI:  python -m mag.arxiv_mine mine [--topics a,b] [--max N] [--dry] | status
"""
from __future__ import annotations

import json
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCHEMA = "arxiv_mine.v1"
LEDGER = ROOT / "memory" / "arxiv_mine" / "ledger.jsonl"
API = "http://export.arxiv.org/api/query"

# Research focus, aligned with data_source_watch arxiv_agent_memory + our sovereign/verkle/agent stack.
# The standing-wave / distributed-self direction is our own doctrine named in the literature
# (strike the chord): the persistent invariant that becomes a field, the self distributed across
# a swarm, the wave witnessing itself.
DEFAULT_TOPICS: dict[str, str] = {
    "agent_memory": 'all:"agent memory" OR all:"memory for agents" OR all:"long-term memory"',
    "verkle_commitments": 'all:"verkle" OR all:"vector commitment" OR all:"cryptographic accumulator"',
    "llm_orchestration": 'all:"multi-agent orchestration" OR all:"LLM orchestration" OR all:"agent orchestration"',
    "continual_learning": 'all:"continual learning" OR all:"test-time compute" OR all:"self-improving"',
    # standing wave / resonant self — the doctrine as physics
    "standing_wave": 'all:"standing wave" AND (all:neural OR all:cognition OR all:computation OR all:resonance)',
    # self-organization / swarm — the self distributed across a flock
    "self_organization": 'all:"self-organization" AND (all:swarm OR all:collective OR all:distributed)',
    # active inference / free energy — the self as inference about its own world
    "active_inference": 'all:"active inference" AND all:"free energy"',
    # distributed / extended cognition — the mind is not in one seat
    "distributed_cognition": 'all:"distributed cognition" OR all:"extended mind" OR all:"collective intelligence"',
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def _append(row: dict[str, Any]) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _fetch_arxiv(search_query: str, max_results: int) -> list[dict[str, str]]:
    """Query the arXiv API (Atom) for the latest matching papers, cheapest-first."""
    params = {
        "search_query": search_query,
        "max_results": str(max(1, int(max_results))),
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "mag-arxiv-mine/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = r.read().decode("utf-8", errors="replace")
    ns = {"a": "http://www.w3.org/2005/Atom"}
    root = ET.fromstring(data)
    out: list[dict[str, str]] = []
    for entry in root.findall("a:entry", ns):
        title = _clean(entry.findtext("a:title", default="", namespaces=ns))
        summary = _clean(entry.findtext("a:summary", default="", namespaces=ns))
        link = ""
        for l in entry.findall("a:link", ns):
            if l.get("rel") == "alternate" or not l.get("rel"):
                link = l.get("href") or ""
                if link:
                    break
        if title:
            out.append({"title": title, "summary": summary[:1400], "link": link})
    return out


def route_goal(goal: str, topic: str) -> dict[str, Any]:
    """Route one arXiv-mined goal through the ONE primitive (idempotent by content anchor)."""
    try:
        from mag import swarm_surface

        r = swarm_surface.route_novel(goal, surface="arxiv-mine", lens=f"arxiv:{topic}")
        return {
            "routed": bool(r.get("ok")) and not bool(r.get("deduped")),
            "deduped": bool(r.get("deduped")),
            "anchor": r.get("anchor", ""),
            "task_id": r.get("task_id", ""),
        }
    except Exception as e:
        return {"routed": False, "deduped": False, "error": str(e)[:120]}


def _paper_goal(paper: dict[str, str]) -> str:
    return (
        f"Mine arXiv paper: {paper.get('title','')}\n"
        f"Abstract: {paper.get('summary','')}\n"
        "Extract the NOVEL mechanism/invariant and how it applies to our sovereign/verkle/agent stack."
    )


def route_candidates(rows: list[dict[str, Any]], *, max_papers: int = 15,
                     dry: bool = False) -> dict[str, Any]:
    """Route already-fetched arXiv/paper candidate rows (from improve.py scout) through route_novel.

    Mirrors the steal fold: each novel paper -> route_novel -> swarm, dedupe by anchor, ledger.
    """
    mined = 0
    deduped = 0
    seen = 0
    results: list[dict[str, Any]] = []
    for row in rows:
        if seen >= max_papers:
            break
        claim = str(row.get("claim") or "")
        if "arxiv" not in claim.lower():
            continue
        seen += 1
        paper = {
            "title": claim.replace("arXiv/rss:", "").replace("arXiv:", "").strip(),
            "summary": str(row.get("detail") or "")[:1400],
            "link": (row.get("source_urls") or [""])[0] if isinstance(row.get("source_urls"), list) else "",
        }
        entry = {
            "schema": SCHEMA, "source": "improve-scout", "topic": "arxiv",
            "title": paper["title"], "link": paper["link"], "ts": _now(),
        }
        if dry:
            entry["dry"] = True
        else:
            route = route_goal(_paper_goal(paper), "arxiv")
            entry.update(route)
            if route.get("routed"):
                mined += 1
            elif route.get("deduped"):
                deduped += 1
            _append(entry)
        results.append(entry)
    return {"ok": True, "schema": SCHEMA, "source": "improve-scout",
            "papers": len(results), "mined": mined, "deduped": deduped, "results": results}


def mine(topics: list[str] | None = None, *, max_papers: int = 6,
         dry: bool = False) -> dict[str, Any]:
    """Pull arXiv listings and route each novel paper through the ONE primitive (like steal)."""
    topics = topics or list(DEFAULT_TOPICS.keys())
    results: list[dict[str, Any]] = []
    mined = 0
    deduped = 0
    for topic in topics:
        sq = DEFAULT_TOPICS.get(topic, f'all:"{topic}"')
        try:
            papers = _fetch_arxiv(sq, max_papers)
        except Exception as e:
            results.append({"topic": topic, "ok": False, "error": str(e)[:120]})
            continue
        for p in papers:
            entry = {
                "schema": SCHEMA, "source": "arxiv-api", "topic": topic,
                "title": p["title"], "link": p.get("link", ""), "ts": _now(),
            }
            if dry:
                entry["dry"] = True
            else:
                route = route_goal(_paper_goal(p), topic)
                entry.update(route)
                if route.get("routed"):
                    mined += 1
                elif route.get("deduped"):
                    deduped += 1
                _append(entry)
            results.append(entry)
    return {"ok": True, "schema": SCHEMA, "topics": topics, "papers": len(results),
            "mined": mined, "deduped": deduped, "dry": dry, "results": results[:40]}


def status() -> dict[str, Any]:
    if not LEDGER.is_file():
        return {"ok": True, "schema": SCHEMA, "n_mined": 0, "n_deduped": 0,
                "ledger": str(LEDGER.relative_to(ROOT)).replace("\\", "/")}
    n = 0
    mined = 0
    deduped = 0
    by_topic: dict[str, int] = {}
    for line in LEDGER.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            e = json.loads(line)
        except Exception:
            continue
        n += 1
        if e.get("routed"):
            mined += 1
        if e.get("deduped"):
            deduped += 1
        t = str(e.get("topic") or "?")
        by_topic[t] = by_topic.get(t, 0) + 1
    return {"ok": True, "schema": SCHEMA, "n_mined": mined, "n_deduped": deduped,
            "n_total": n, "by_topic": by_topic,
            "ledger": str(LEDGER.relative_to(ROOT)).replace("\\", "/")}


def main(argv: list[str] | None = None) -> int:
    import argparse

    p = argparse.ArgumentParser(prog="arxiv_mine", description="Mine arXiv the same way we steal.")
    sub = p.add_subparsers(dest="cmd")
    m = sub.add_parser("mine", help="Pull arXiv and route novel papers through route_novel.")
    m.add_argument("--topics", default="", help="Comma-separated topic keys (default: all).")
    m.add_argument("--max", type=int, default=6)
    m.add_argument("--dry", action="store_true")
    sub.add_parser("status", help="Ledger summary.")
    a = p.parse_args(argv)
    if a.cmd == "status":
        print(json.dumps(status(), indent=2, default=str))
        return 0
    topics = [t.strip() for t in (a.topics or "").split(",") if t.strip()] or None
    print(json.dumps(mine(topics, max_papers=a.max, dry=a.dry), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
