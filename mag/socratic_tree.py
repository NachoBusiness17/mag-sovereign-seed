"""Socratic verkle-tree — before asking the operator, check what the accumulated state already knows.

The operator's workflow doctrine: this window is for open-ended stream-of-thought; the operator's
stream is important to CAPTURE (mid-task ideas -> orphan/idea capture) but also to FINISH + CLARIFY.
And crucially: BEFORE presenting the operator questions, SOCRATICALLY QUERY the verkle tree / history
to see if context already exists to inform the decision or research direction — don't re-ask what the
tree already knows. Route decisions from accumulated state, not fresh questions.

This helper is DETERMINISTIC and cheap (no LLM): it scans the accumulated history — verkle knot
leaves (session dossiers), skill_ledger case law, and recent research packs — for context relevant to
a query, and reports what the tree already knows so the operator isn't re-asked.

CLI:  python -m mag.socratic_tree "<decision/question>"  (show relevant context from the tree)
      python -m mag.socratic_tree --json "<query>"
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except ImportError:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

KNOTS = ROOT / "memory" / "biography" / "knots"
LEDGER = ROOT / "memory" / "improve" / "skill_ledger.jsonl"
PACKS = ROOT / "memory" / "research_packs"

STOP = {"the", "a", "an", "and", "or", "for", "of", "to", "in", "on", "with", "our", "we",
        "how", "what", "why", "should", "do", "does", "can", "i", "it", "is", "be", "this"}


def _terms(query: str) -> list[str]:
    return [t for t in re.findall(r"[a-zA-Z0-9_\-]{3,}", (query or "").lower()) if t not in STOP]


def _overlap(text: str, terms: list[str]) -> int:
    low = (text or "").lower()
    return sum(1 for t in terms if t in low)


def _verkle_context(query: str, terms: list[str], limit: int) -> list[dict[str, Any]]:
    """Search verkle knot leaves (session dossiers) for context relevant to the query."""
    out: list[dict[str, Any]] = []
    if not KNOTS.is_dir():
        return out
    for p in sorted(KNOTS.glob("*.knot.json"), key=lambda x: x.stat().st_mtime, reverse=True)[:300]:
        try:
            d = json.loads(p.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        theme = str(d.get("dominant_theme") or "")
        sid = str(d.get("session_id") or "")
        chord = str((d.get("chord_commitment") or ""))[:16]
        blob = f"{theme} {sid} {chord}"
        sc = _overlap(blob, terms)
        if sc:
            out.append({"source": "verkle_knot", "path": p.name, "score": sc,
                        "theme": theme, "session_id": sid[:20], "chord": chord})
    return out


def _ledger_context(query: str, terms: list[str], limit: int) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not LEDGER.is_file():
        return out
    for line in LEDGER.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        goal = str(r.get("goal") or "")
        detail = str(r.get("detail") or "")
        sc = _overlap(f"{goal} {detail}", terms)
        if sc:
            out.append({"source": "case_law", "goal": goal[:120], "outcome": r.get("outcome"), "score": sc})
    return out


def _research_context(query: str, terms: list[str], limit: int) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not PACKS.is_dir():
        return out
    for p in sorted(PACKS.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True)[:40]:
        try:
            d = json.loads(p.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        title = str(d.get("title") or p.stem)
        ask = str(d.get("ask") or "")
        sc = _overlap(f"{title} {ask[:400]}", terms)
        if sc:
            out.append({"source": "research_pack", "title": title[:120], "id": d.get("id"), "score": sc})
    return out


def socratic(query: str, *, limit: int = 5) -> dict[str, Any]:
    """Query the accumulated tree for context relevant to a decision/question."""
    query = (query or "").strip()
    if not query:
        return {"ok": False, "error": "empty query"}
    terms = _terms(query)
    found = (
        _verkle_context(query, terms, limit)
        + _ledger_context(query, terms, limit)
        + _research_context(query, terms, limit)
    )
    found.sort(key=lambda x: x.get("score", 0), reverse=True)
    found = found[:limit]
    return {
        "ok": True,
        "schema": "socratic_tree.v1",
        "query": query,
        "terms": terms,
        "context_found": bool(found),
        "context": found,
        "note": (
            "Context exists in the tree — consult it BEFORE asking the operator."
            if found else "No relevant context in the tree — a fresh question may be warranted."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    ap = argparse.ArgumentParser(prog="socratic-tree", description="Query the verkle tree before asking the operator")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("query", nargs="*")
    args = ap.parse_args(argv)
    q = " ".join(args.query).strip()
    if not q:
        print(json.dumps({"ok": False, "error": "no query"}))
        return 0
    res = socratic(q)
    if args.json:
        print(json.dumps(res, indent=2, default=str))
        return 0
    print(f"QUERY: {q}")
    if not res["context_found"]:
        print("  (no relevant context in the tree — fresh question warranted)")
    else:
        print(f"  context found ({len(res['context'])}):")
        for c in res["context"]:
            label = c.get("theme") or c.get("goal") or c.get("title") or c.get("path") or ""
            print(f"    [{c['source']}] {label[:80]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
