#!/usr/bin/env python3
"""cascade_research.py — the Perplexity steal: cascade-rank research
cheap-to-expensive with HARD STOPPING FLOORS (R4, research seam, 2026-09-11).

One question, three escalation tiers, each gated by a coverage floor:

  TIER 1  $0        local surfaces: invariant sheet, bibliography map, cards
  TIER 2  pennies   the deepseek research seam (mag MCP `research` tool)
  TIER 3  GO-gated  frontier subagent — operator GO or it does not fire

STOPPING FLOOR: a tier that lands >= MIN_INDEPENDENT independent sources
(hits in >=2 DISTINCT files) STOPS the cascade — never spend a dearer tier
on a question the cheaper tier already answered. This is the Perplexity
insight made fleet-law: rank by cost, stop at the first floor that holds.

Audit pattern inherited from mag/librarian.py: deterministic, stdlib-only,
one pass, tri-state claims, report on disk. The script NEVER holds keys and
NEVER leaves the box:
  - tier 2 is ingested from a JSON receipt the desk writes after firing the
    research seam (--tier2-json), so the cascade stays reproducible;
  - tier 3 only emits a dispatch payload when --go is passed (the card names
    the gate: operator GO — launch law amendment 5).

Usage:
  python mag/cascade_research.py "question"
  python mag/cascade_research.py "question" --tier2-json receipt.json
  python mag/cascade_research.py "question" --go        # tier-3 dispatch only
Exit 0 = a tier met the floor (cascade stopped); 1 = floor never met.
"""
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAP_PATH = ROOT / "docs" / "ref" / "BIBLIOGRAPHY_MAP.md"
SHEET_GLOBS = ["watch/**/*sheet*.md", "watch/**/*invariant*.md"]
CARD_WALKS = ["watch", "docs", "configs"]
SELF_GUARD = {"cascade_research.md", "r4_cascade.md", "librarian_report.md"}

MIN_INDEPENDENT = 2        # the coverage floor: >=2 independent sources
MIN_KEYWORDS_PER_HIT = 2   # a file must hit >=2 distinct question terms
STOPWORD = set("""a an and are as at be by does do for from has how in is it
its of on or that the this to was what when where which who why will with
change changes""".split())

# ---------------------------------------------------------------------------
# tier 1 — the $0 pass over local surfaces


def keywords(question):
    toks = [t for t in re.split(r"[^a-z0-9]+", question.lower()) if t]
    core = [t for t in toks if t not in STOPWORD and len(t) >= 3]
    # dedupe, keep order; singular/plural fold (sheet/cards vs sheet/card)
    folded, seen = [], set()
    for t in core:
        k = t[:-1] if t.endswith("s") and t[:-1] not in STOPWORD else t
        if k not in seen:
            seen.add(k)
            folded.append(k)
    return folded


def _score_text(text, kws):
    """(distinct_kw_hits, score, best_line) for one document."""
    low = text.lower()
    hits = [k for k in kws if k in low]
    if len(hits) < MIN_KEYWORDS_PER_HIT:
        return None
    score = sum(low.count(k) for k in hits)
    best, best_n = "", -1
    for line in text.splitlines():
        n = sum(line.lower().count(k) for k in hits)
        if n > best_n and line.strip():
            best, best_n = line.strip(), n
    return len(hits), score, best[:220]


def tier1(question):
    """Scan sheet + map + cards. Returns (hits, surfaces) — hits sorted best
    first; a hit = {file, surface, kws, score, line}. Deterministic order.

    Rarest-term anchoring keeps the floor honest: common words ("fleet",
    "state") match everything, so a file only counts if it contains the
    corpus-rarest keyword (df-minimal, df>0) AND >=MIN_KEYWORDS_PER_HIT
    distinct terms. Without this the floor always passes and never gates."""
    kws = keywords(question)
    candidates = []  # (path, surface)
    for g in SHEET_GLOBS:
        candidates += [(p, "invariant-sheet") for p in ROOT.glob(g)]
    if MAP_PATH.exists():
        candidates.append((MAP_PATH, "bibliography-map"))
    for d in CARD_WALKS:
        base = ROOT / d
        if base.exists():
            candidates += [(p, "card") for p in base.rglob("*.md")]
    seen, texts = set(), []
    for p, surface in sorted(candidates, key=lambda c: str(c[0])):
        if p.name.lower() in SELF_GUARD or str(p) in seen:
            continue
        seen.add(str(p))
        try:
            texts.append((p, surface, p.read_text(encoding="utf-8", errors="replace").lower()))
        except OSError:
            continue
    # document frequency per keyword -> anchor = rarest keyword with df>0
    df = {k: sum(1 for _, _, t in texts if k in t) for k in kws}
    anchors = [k for k in sorted(kws, key=lambda k: (df[k], k)) if df[k] > 0]
    anchor = anchors[0] if anchors else None
    hits = []
    for p, surface, low in texts:
        present = [k for k in kws if k in low]
        if anchor is None or anchor not in present:
            continue
        if len(present) < MIN_KEYWORDS_PER_HIT:
            continue
        s = _score_text(p.read_text(encoding="utf-8", errors="replace"), kws)
        hits.append({"file": str(p.relative_to(ROOT)), "surface": surface,
                     "kws": s[0], "score": s[1], "line": s[2],
                     "anchor": anchor})
    hits.sort(key=lambda h: (-h["kws"], -h["score"], h["file"]))
    surfaces = {h["surface"] for h in hits}
    return hits, surfaces


# ---------------------------------------------------------------------------
# tier 2 — the pennies pass, ingested from a research-seam receipt


def tier2(receipt_path, kws):
    """Load a seam receipt: {ask, answer, sources:[{title,url}], cost_usd}.
    Independence = distinct source URLs; the answer must itself hit >=2
    question keywords to count as an answer (not a polite shrug)."""
    r = json.loads(Path(receipt_path).read_text(encoding="utf-8"))
    answer = r.get("answer", "")
    distinct_kws = len({k for k in kws if k in answer.lower()})
    sources = []
    for s in r.get("sources", []):
        url = s.get("url", "")
        if url and url not in {x["url"] for x in sources}:
            sources.append({"title": s.get("title", url), "url": url})
    return {"answer": answer, "sources": sources,
            "kw_hits": distinct_kws, "cost_usd": r.get("cost_usd", 0.0)}


# ---------------------------------------------------------------------------
# the cascade


def run(question, tier2_receipt=None, go=False):
    kws = keywords(question)
    trace = []
    verdict = {"question": question, "kws": kws, "tiers": trace}

    # TIER 1 — $0
    hits, surfaces = tier1(question)
    independent = len({h["file"] for h in hits})
    t1 = {"tier": 1, "cost": "$0", "hits": hits[:8], "independent": independent,
          "surfaces": sorted(surfaces)}
    if independent >= MIN_INDEPENDENT:
        t1["verdict"] = "STOP — floor met (%d independent local sources)" % independent
        trace.append(t1)
        verdict.update({"stopped_at": 1, "answer": None, "status": "ANSWERED-TIER-1"})
        return verdict
    t1["verdict"] = "ESCALATE — only %d independent local source(s)" % independent
    trace.append(t1)

    # TIER 2 — pennies (deepseek seam receipt)
    if tier2_receipt:
        t2r = tier2(tier2_receipt, kws)
        independent2 = independent + len(t2r["sources"])  # cross-tier union
        answered = t2r["kw_hits"] >= MIN_KEYWORDS_PER_HIT
        t2 = {"tier": 2, "cost": "~$%.4f (deepseek pennies)" % t2r["cost_usd"],
              "sources": t2r["sources"], "kw_hits": t2r["kw_hits"],
              "independent": independent2}
        if answered and independent2 >= MIN_INDEPENDENT:
            t2["verdict"] = "STOP — floor met (%d independent sources union)" % independent2
            trace.append(t2)
            verdict.update({"stopped_at": 2, "answer": t2r["answer"],
                            "status": "ANSWERED-TIER-2"})
            return verdict
        t2["verdict"] = ("ESCALATE — seam %s, union %d independent"
                         % ("answered but thin" if answered else "no answer",
                            independent2))
        trace.append(t2)
    else:
        trace.append({"tier": 2, "cost": "pennies", "verdict":
                      "ESCALATE — seam not fired yet (desk fires mcp research; "
                      "re-ingest with --tier2-json)"})

    # TIER 3 — GO-gated frontier
    if go:
        t3 = {"tier": 3, "cost": "frontier $",
              "verdict": "GO present — dispatch payload EMITTED, desk executes",
              "dispatch": {"ask": question, "budget": "operator-approved",
                           "gate": "operator GO (launch law amendment 5)"}}
        verdict.update({"stopped_at": None, "status": "TIER-3-DISPATCHED",
                        "answer": None})
    else:
        t3 = {"tier": 3, "cost": "frontier $",
              "verdict": "BLOCKED — operator GO required; gate named, not paid"}
        verdict.update({"stopped_at": None, "status": "GATED-TIER-3",
                        "answer": None})
    trace.append(t3)
    return verdict


def render(v):
    out = ["# CASCADE RESEARCH — R4 test result", "",
           f"_question: {v['question']}_",
           f"_keywords: {', '.join(v['kws'])} · floor: >={MIN_INDEPENDENT} "
           f"independent sources · {time.strftime('%Y-%m-%dT%H:%MZ', time.gmtime())}_", ""]
    for t in v["tiers"]:
        out.append(f"## TIER {t['tier']} ({t['cost']}) — {t['verdict']}")
        for h in t.get("hits", []):
            out.append(f"- [{h['surface']}] {h['file']} — {h['line']}")
        for s in t.get("sources", []):
            out.append(f"- [seam] {s['title']} — {s['url']}")
        if "dispatch" in t:
            out.append(f"- dispatch ask: {t['dispatch']['ask']}")
        out.append("")
    out.append(f"## VERDICT: {v['status']}")
    if v.get("answer"):
        out.append("")
        out.append(v["answer"])
    return "\n".join(out)


def main(argv):
    args = [a for a in argv[1:] if not a.startswith("--")]
    receipt = next((argv[i + 1] for i, a in enumerate(argv) if a == "--tier2-json"), None)
    go = "--go" in argv
    if not args:
        print(__doc__)
        return 2
    v = run(" ".join(args), tier2_receipt=receipt, go=go)
    print(render(v))
    out = ROOT / "watch" / "inbox" / "mickey" / "R4_cascade.json"
    out.write_text(json.dumps(v, indent=2), encoding="utf-8")
    print(f"\ncascade json -> {out.relative_to(ROOT)}")
    return 0 if v["stopped_at"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
