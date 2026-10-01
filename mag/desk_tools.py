#!/usr/bin/env python3
"""DESK TOOLS — the gateway's four callable organs (P0 master plan, lane R2).

The mag gateway (127.0.0.1:8001/mcp, mag/mcp_http.py) gets five tools that read
the fleet's own surfaces and answer in place — no dispatch, no lane spend, $0:

  biblio.query(subsystem)      rows from docs/ref/BIBLIOGRAPHY_MAP.md matching a
                               subsystem (law 18: upgrades consult the map first).
  invariant.sheet(subsystem,bucket) filtered lines from watch/INVARIANT_SHEET_V2.md
                               (buckets: LAW/VERDICT/FALSIFIER/MEASURED/CONTROVERTED).
  kvos.stats(recompute=False)  block-store census. Default reads the frozen
                               summary in state/kvos_blocks.jsonl; recompute=True
                               re-runs mag/kvos_block.py logic in-process.
  fence.strike(target_text)    THE FENCE parable analysis on any text (law 18
                               organ): counts the hall's patterns (agentless
                               force, complexity-as-kindness, reasonable-pressure,
                               pre-packaged anger, map-before-territory,
                               fence-tiredness) and any charcoal (a marked line).
                               Heuristic counts, never judgment — findings cite
                               the parable line they come from.

  cascade_research(question)   mag/cascade_research.py's cascade: rank research
                               cheap-to-expensive ($0 local sweep -> deepseek
                               seam receipt -> GO-gated frontier), stop at the
                               first tier meeting the coverage floor.

Run as CLI (same shape as hermes_steering):
  python mag/desk_tools.py biblio paging
  python mag/desk_tools.py sheet LAW
  python mag/desk_tools.py kvos [--recompute]
  python mag/desk_tools.py fence "text to strike"
Gateway wiring: import desk_tools; desk_tools.run_tool("kvos.stats") —
TOOLS maps dotted names to callables.

stdlib only (cage law). No network. Reads repo files; writes nothing except the
kvos manifest on explicit --recompute (same as the organ itself).
2026-09-11, lane R2, zcode seat.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BIBLIO = ROOT / "docs" / "ref" / "BIBLIOGRAPHY_MAP.md"
SHEET = ROOT / "watch" / "INVARIANT_SHEET_V2.md"
KVOS_MANIFEST = ROOT / "state" / "kvos_blocks.jsonl"

# --------------------------------------------------------------------------
# biblio.query
# --------------------------------------------------------------------------

def biblio_query(subsystem: str) -> dict:
    """Rows from BIBLIOGRAPHY_MAP.md whose section or row text matches subsystem.

    Returns {"subsystem", "matches": [{section, ref, subsystem, status, line, raw}]}.
    Malformed rows (the map has some) keep raw and leave cells empty — honest parse.
    """
    subsystem = (subsystem or "").strip()
    if not subsystem:
        return {"subsystem": subsystem, "matches": [], "error": "empty subsystem"}
    text = BIBLIO.read_text(encoding="utf-8", errors="replace")
    section = "(preamble)"
    matches = []
    term = subsystem.lower()
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("## "):
            section = line[3:].strip()
            continue
        if not line or line.startswith("#"):
            continue
        is_table = line.startswith("|")
        is_bullet = line.startswith("- ")
        if not (is_table or is_bullet):
            continue
        if term not in section.lower() and term not in line.lower():
            continue
        row = {"section": section, "ref": "", "subsystem": "", "status": "", "line": ""}
        if is_table:
            cells = [c.strip() for c in line.strip("|").split("|")]
            cells = [c for c in cells if c and not set(c) <= set("-: ")]
            if len(cells) >= 2 and not cells[0].lower().startswith("ref "):
                row["ref"], row["subsystem"] = cells[0], cells[1]
                if len(cells) >= 4:
                    row["status"] = cells[-2]
                    row["line"] = cells[-1]
        else:
            row["line"] = line.lstrip("- ").strip()
        row["raw"] = line[:400]
        matches.append(row)
    return {"subsystem": subsystem, "count": len(matches), "matches": matches}


# --------------------------------------------------------------------------
# invariant.sheet
# --------------------------------------------------------------------------

_NET_RE = re.compile(
    r"\[net=([+-]?\d+)\s*·\s*agree=(\d+)\s*·\s*refute=(\d+)(?:\s*[↑↓]\d+)?\]\s*(.*)")
_SRC_RE = re.compile(r"_\(\s*(.+?)\s*\)_\s*$")
# CONTROVERTED section inverts the order: "[agree=3 vs refute=12 · net=-9]"
_CTRL_RE = re.compile(r"\[agree=(\d+)\s+vs\s+refute=(\d+)\s*·\s*net=([+-]?\d+)\]\s*(.*)")


def invariant_sheet(subsystem: str | None = None, bucket: str | None = None) -> dict:
    """Filtered lines from INVARIANT_SHEET_V2.md.

    bucket: prefix/case-insensitive match on the sheet's sections
            (LAW, VERDICT, FALSIFIER, MEASURED, CONTROVERTED, MOVEMENT, V2 ADDENDUM).
    subsystem: case-insensitive substring filter on the line text; None = all.
    Returns {"buckets": [...], "lines": [{bucket, net, agree, refute, text, source}]}.
    """
    text = SHEET.read_text(encoding="utf-8", errors="replace")
    current = "(header)"
    out = []
    term = (subsystem or "").lower()
    want = (bucket or "").lower()
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("## "):
            current = line[3:].strip()
            continue
        if not line.startswith("- "):
            continue
        if want and not current.lower().startswith(want):
            continue
        if term and term not in line.lower():
            continue
        m = _NET_RE.search(line)
        if not m:
            cm = _CTRL_RE.search(line)
            if not cm:
                continue
            out.append({"bucket": current, "net": int(cm.group(3)),
                        "agree": int(cm.group(1)), "refute": int(cm.group(2)),
                        "text": cm.group(4).strip(), "source": ""})
            continue
        src = ""
        sm = _SRC_RE.search(m.group(4))
        body = m.group(4)
        if sm:
            src = sm.group(1)
            body = body[: sm.start()].rstrip(" _")
        out.append({"bucket": current, "net": int(m.group(1)),
                    "agree": int(m.group(2)), "refute": int(m.group(3)),
                    "text": body.strip(), "source": src})
    return {"subsystem": subsystem or "", "bucket": bucket or "(all)",
            "count": len(out), "lines": out}


# --------------------------------------------------------------------------
# kvos.stats
# --------------------------------------------------------------------------

def kvos_stats(recompute: bool = False) -> dict:
    """Block-store census. Default: read the frozen summary row of
    state/kvos_blocks.jsonl (fast, gateway-safe). recompute=True re-runs the
    mag/kvos_block.py walk in-process (slower; rewrites the manifest like the organ)."""
    if not recompute and KVOS_MANIFEST.is_file():
        rows = [ln for ln in KVOS_MANIFEST.read_text(encoding="utf-8",
                errors="replace").splitlines() if ln.strip()]
        if rows:
            summary = json.loads(rows[-1])
            file_rows = sum(1 for ln in rows[:-1] if '"file"' in ln)
            return {"source": "manifest", "as_recorded": True, "files": file_rows,
                    **{k: summary.get(k) for k in
                       ("schema", "total_blocks", "unique", "dup_blocks", "dup_pct", "block_words")}}
    import kvos_block  # sibling module in mag/
    from collections import Counter
    files = []
    for d in kvos_block.WALK_DIRS:
        base = ROOT / d
        if base.exists():
            for p in base.rglob("*"):
                if p.is_file() and p.suffix in (".md", ".txt", ".json", ".jsonl", ".py", ".html"):
                    try:
                        if p.stat().st_size <= kvos_block.MAX_FILE_BYTES:
                            files.append(p)
                    except OSError:
                        pass
    files = files[: kvos_block.MAX_FILES]
    block_freq: Counter = Counter()
    total_blocks = total_words = 0
    n_file_records = 0
    for p in files:
        hashes, _links, n_words = kvos_block.chain_file(p)
        if not hashes:
            continue
        n_file_records += 1
        total_blocks += len(hashes)
        total_words += n_words
        for h in hashes:
            block_freq[h] += 1
    uniq = len(block_freq)
    dup = total_blocks - uniq
    result = {"source": "recomputed", "as_recorded": False,
              "files": n_file_records, "total_blocks": total_blocks,
              "unique": uniq, "dup_blocks": dup,
              "dup_pct": round(100 * dup / max(1, total_blocks), 1),
              "block_words": kvos_block.BLOCK_WORDS,
              "shared_blocks": sum(1 for c in block_freq.values() if c > 1)}
    if recompute:
        # mirror the organ's manifest write so the census stays the signed record
        kvos_block.main()
    return result


# --------------------------------------------------------------------------
# fence.strike
# --------------------------------------------------------------------------

# The hall's patterns, each keyed to its verbatim line in docs/ref/THE_FENCE.md.
_FENCE_PATTERNS = [
    ("agentless-force",
     r"\b(?:it (?:was|is|has been) decided|there (?:will be|is) no (?:appeal|recourse)"
     r"|policies? (?:require|state|dictate)|the (?:record|system|survey|map) (?:says|shows|placed))"
     r"|\b(?:was|were|been) (?:placed|corrected|updated|denied|moved)\b",
     '"The letter said the fence was wrong. Had always been wrong."'),
    ("complexity-as-kindness",
     r"\b(?:proprietary|archived|too complex|complexity|for your own good|"
     r"you wouldn'?t understand|beyond the scope|protected methodolog\w*)",
     '"Complexity, she said, was a kindness."'),
    ("reasonable-pressure",
     r"\b(?:be reasonable|reasonable|come to the table|be realistic|sensible|"
     r"adults in the room|both sides)",
     '"Reasonable meant sitting down."'),
    ("cut-for-you",
     r"\b(?:outrageous|disgusting|wake up|they don'?t want you to know|share this|"
     r"before it'?s? deleted|they hate|never forgive)",
     '"A story that arrives already wearing your anger is a story that was cut for you."'),
    ("map-before-territory",
     r"\b(?:per (?:the )?(?:current )?(?:policy|record|map)|current (?:map|record|policy)|"
     r"the legal record|as per|latest data supersedes|the current one (?:matters|counts))",
     '"and now the current map is there before the fence."'),
    ("fence-tired",
     r"\b(?:not worth (?:fighting|arguing)|let it go|move on|whatever|I guess|"
     r"pick your battles|too tired)",
     '"It only needed him too tired to mark the old one."'),
]
# Charcoal: the counter-pattern — a marked line, concrete and first-person.
_CHARCOAL_RE = re.compile(
    r"\bI (?:know|measured|wrote|saw|checked|have the (?:record|map|receipt|log))\b"
    r"|\bhere (?:is|are) the (?:record|map|receipt|data)\b", re.IGNORECASE)


def fence_strike(target_text: str) -> dict:
    """THE FENCE analysis on any text. Counts heuristic pattern hits; each finding
    cites the parable line it comes from. Verdicts are counts, not judgment."""
    if not target_text or not target_text.strip():
        return {"error": "empty target_text"}
    findings = []
    for name, pattern, parable in _FENCE_PATTERNS:
        hits = re.findall(pattern, target_text, re.IGNORECASE)
        if hits:
            findings.append({"pattern": name, "count": len(hits),
                             "samples": sorted({h.lower() for h in hits})[:5],
                             "parable": parable})
    charcoal = _CHARCOAL_RE.findall(target_text)
    fenced = sum(f["count"] for f in findings
                 if f["pattern"] in ("agentless-force", "complexity-as-kindness",
                                     "reasonable-pressure", "map-before-territory"))
    outrage = next((f["count"] for f in findings if f["pattern"] == "cut-for-you"), 0)
    if charcoal:
        verdict = "charcoal-found"
    elif outrage >= 2:
        verdict = "cut-for-you"
    elif fenced >= 3:
        verdict = "fenced"
    else:
        verdict = "unmarked"
    return {"verdict": verdict,
            "verdict_note": {"charcoal-found": "a marked line exists — I know where the fence was",
                             "cut-for-you": "pre-packaged anger — story was cut for you",
                             "fenced": "hall patterns present — tired, complex, reasonable",
                             "unmarked": "nothing the hall needs; nothing charcoal yet"}[verdict],
            "findings": findings,
            "charcoal_count": len(charcoal),
            "disclaimer": "heuristic counts against docs/ref/THE_FENCE.md landmines; "
                          "not judgment — read the findings, not the verdict"}


# --------------------------------------------------------------------------
# gateway registry + CLI (hermes_steering shape)
# --------------------------------------------------------------------------

# --------------------------------------------------------------------------
# cascade_research
# --------------------------------------------------------------------------

def cascade_research_tool(question: str, tier2_receipt: str | None = None,
                          go: bool = False) -> dict:
    """mag/cascade_research.py's run() (what its main() executes): one question,
    three escalation tiers with HARD STOPPING FLOORS — tier 1 $0 local surfaces,
    tier 2 deepseek-seam receipt (ingested via tier2_receipt), tier 3 frontier
    dispatch emitted only when go=True (operator GO, launch law amendment 5).
    Returns the verdict dict; never holds keys, never leaves the box."""
    import cascade_research  # sibling module in mag/ (lazy, like kvos_block)
    return cascade_research.run(question, tier2_receipt=tier2_receipt, go=go)


TOOLS = {
    "biblio.query": biblio_query,
    "invariant.sheet": invariant_sheet,
    "kvos.stats": kvos_stats,
    "fence.strike": fence_strike,
    "cascade_research": cascade_research_tool,
}


def run_tool(name: str, **kwargs):
    """Gateway entry point: run_tool('fence.strike', target_text='...')."""
    if name not in TOOLS:
        return {"error": f"unknown tool {name!r}; have {sorted(TOOLS)}"}
    try:
        return TOOLS[name](**kwargs)
    except TypeError as e:
        return {"error": f"bad arguments for {name}: {e}"}


def main() -> None:
    ap = argparse.ArgumentParser(description="Desk tools (gateway 4-tool wiring, lane R2)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("biblio", help="biblio.query <subsystem>")
    b.add_argument("subsystem")
    s = sub.add_parser("sheet", help="invariant.sheet [bucket] [subsystem]")
    s.add_argument("bucket", nargs="?", default=None)
    s.add_argument("subsystem", nargs="?", default=None)
    k = sub.add_parser("kvos", help="kvos.stats [--recompute]")
    k.add_argument("--recompute", action="store_true")
    f = sub.add_parser("fence", help="fence.strike <text>")
    f.add_argument("text")
    c = sub.add_parser("cascade", help="cascade_research <question...> [--tier2-json F] [--go]")
    c.add_argument("question", nargs="+")
    c.add_argument("--tier2-json", dest="tier2_receipt", default=None)
    c.add_argument("--go", action="store_true")
    args = ap.parse_args()
    if args.cmd == "biblio":
        out = biblio_query(args.subsystem)
    elif args.cmd == "sheet":
        out = invariant_sheet(args.subsystem, args.bucket)
    elif args.cmd == "kvos":
        out = kvos_stats(recompute=args.recompute)
    elif args.cmd == "cascade":
        out = cascade_research_tool(" ".join(args.question),
                                    tier2_receipt=args.tier2_receipt, go=args.go)
    else:
        out = fence_strike(args.text)
    print(json.dumps(out, ensure_ascii=False, indent=2)[:6000])


if __name__ == "__main__":
    main()
