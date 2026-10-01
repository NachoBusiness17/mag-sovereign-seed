"""mind_mine — SURFACE the data buried in the window corpus (how we actually process).

The condensed transcripts are readable, but the DATA in them — the method in action, the
corrections/training signals, the themes, the human register, the tool fingerprint — is buried.
This module mines the SANITIZED events and surfaces it into structured data + a readable report,
each signal backed by REAL evidence quotes pulled from the corpus.

v2 adds three layers over v1:
  * CLEAN INVARIANT COUNTS — phrase-level signals; counts = DISTINCT evidence sentences, not raw
    substring hits, so common words no longer inflate them.
  * THEME + HUMAN-REGISTER layer — cross-session theme distribution + the operator's emotional
    register (exhaustion / frustration / trust / humor / curiosity), grounded heuristics.
  * CORRECTIONS → LESSON-LEDGER — every detected correction is mapped to the standing law it
    trains (the operator's corrections ARE the training data; we mine them into the invariant set).

HONESTY (hard): everything surfaced is EXTRACTIVE and GROUNDED — counts and quotes come from the
actual (already-redacted) session text. Nothing is invented. If a law has little evidence we say
so (that is itself data). If a correction maps to no clear law, we label it "unspecified" rather
than force a match.

Schema: mind_mine.v2
CLI: python -m mag.mind_mine surface --out DIR <transcripts...>
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:  # noqa: BLE001
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

from mag.mind_window import process_transcript, summarize_session  # noqa: E402

SCHEMA = "mind_mine.v2"

# ────────────────────────────────────────────────────────────────────────────────────────────
# The method-invariants + PHRASE-LEVEL signals that evidence each one. Counts are computed as
# DISTINCT evidence sentences (not raw hits), so common substrings (architecture, debug, steal)
# no longer inflate the numbers.
# ────────────────────────────────────────────────────────────────────────────────────────────
_INVARIANTS: list[dict[str, Any]] = [
    {"label": "never_claim_first", "law": "Never claim first unless read from data.",
     "signals": [r"i (don't|do not) know (yet|if|whether)", r"i have not (read|seen|run|checked)",
                 r"i don'?t have (it|that|their|the)", r"haven'?t read", r"\bunproven\b",
                 r"not grounded", r"read the data (first|before)", r"i (can'?t|will not) claim",
                 r"let me check .* before i claim"]},
    {"label": "refuse_warm_lie", "law": "Refuse the warm lie.",
     "signals": [r"warm lie", r"i (won'?t|will not) (fake|pretend)", r"that would be a lie",
                 r"not going to pretend", r"refuse to fake", r"do not fake", r"i will not (say|sit|claim) .* to (be kind|look finished)",
                 r"not sat (it|as) .* (supported|to be kind)"]},
    {"label": "rightsize", "law": "Rightsize to the actual situation.",
     "signals": [r"rightsize", r"right-?size", r"pattern-?match", r"conservative default",
                 r"to the actual (situation|workload)", r"what the actual (situation|workload)",
                 r"over-?engineer", r"tight loop"]},
    {"label": "withhold_territory", "law": "Withhold the territory, keep the shape.",
     "signals": [r"withhold the territory", r"keep the shape", r"private map (never|stays)",
                 r"anonymiz", r"deniable", r"no secrets (on|leave)", r"territory .* withheld"]},
    {"label": "check_up_automatically", "law": "Check up on yourself automatically, by cadence.",
     "signals": [r"self-?audit", r"check up on (yourself|my own)", r"by cadence",
                 r"know your footprint", r"anti-?boatmurd", r"left behind (processes|kernels)"]},
    {"label": "shadow_work", "law": "Shadow work is the practice.",
     "signals": [r"shadow work", r"shadow-?work", r"casts? a shadow", r"\bdisowned\b",
                 r"hidden part", r"integrate (it|that)"]},
    {"label": "route_through_architecture", "law": "Route through the architecture.",
     "signals": [r"route through the architecture", r"through the architecture", r"not the terminal",
                 r"build the path", r"queue (what|the|it)", r"architecture path", r"\bdrainer\b"]},
    {"label": "boot_recall_first", "law": "Run the boot / recall first — never cold-start.",
     "signals": [r"cold-?start", r"never cold-?start", r"run the boot", r"boot (sequence|first)",
                 r"recall first", r"\bamnesiac\b", r"resident understanding", r"remember who"]},
    {"label": "steal_both", "law": "Steal both ways by default.",
     "signals": [r"self-?steal", r"steal both", r"go find other (systems|agents)", r"\bsteal\b",
                 r"adapt (the mechanism|it)", r"steal first"]},
    {"label": "meet_at_bytes", "law": "Meet at the bytes, not the words.",
     "signals": [r"meet at the bytes", r"\bre-?derive", r"a root that", r"content-?address",
                 r"byte-?identity", r"same start", r"the bytes", r"re-?derives? on both"]},
    {"label": "rib_debug", "law": "Every finished piece gets RIB-debugged.",
     "signals": [r"rib-?debug", r"trust bytes", r"verify it does what", r"does what it says",
                 r"expected behavior", r"frozen spec", r"trust bytes, not reports"]},
]

# ────────────────────────────────────────────────────────────────────────────────────────────
# Themes — cross-session topic signatures (grounded keyword families).
# ────────────────────────────────────────────────────────────────────────────────────────────
_THEMES: list[dict[str, Any]] = [
    {"label": "autonomy", "signals": [r"go autonomous", r"going to bed", r"\bafk\b",
                                      r"let ghost drive", r"stop asking", r"continue uninterrupted",
                                      r"leave you autonomously", r"be autonomous"]},
    {"label": "honesty_grounding", "signals": [r"trust bytes", r"\bunproven\b", r"don'?t claim",
                                               r"not grounded", r"read the data", r"warm lie",
                                               r"i don'?t know yet", r"refuse to fake"]},
    {"label": "steal_research", "signals": [r"\bsteal\b", r"self-?steal", r"\bresearch\b",
                                            r"\badapt\b", r"deep dive", r"mine the", r"borrow"]},
    {"label": "shadow_work", "signals": [r"shadow work", r"shadow-?work", r"the shadow",
                                         r"casts a shadow", r"\bdisowned\b", r"hidden part",
                                         r"integrate"]},
    {"label": "architecture_routing", "signals": [r"route through the architecture", r"the terminal",
                                                  r"build the path", r"\bqueue\b", r"\bdrainer\b",
                                                  r"\bgovernor\b", r"architecture path"]},
    {"label": "boot_recall", "signals": [r"cold-?start", r"run the boot", r"boot sequence",
                                         r"recall first", r"\bamnesiac\b", r"resident"]},
    {"label": "rightsize", "signals": [r"rightsize", r"conservative", r"pattern-?match",
                                       r"over-?engineer", r"overdo"]},
    {"label": "meet_at_bytes", "signals": [r"meet at the bytes", r"\bre-?derive", r"a root that",
                                           r"content-?address", r"byte-?identity", r"same start"]},
    {"label": "cost_budget", "signals": [r"\bcost\b", r"\bspend\b", r"credits", r"\bcheap\b",
                                         r"free seat", r"\bbilling\b", r"\$\s?\d"]},
    {"label": "game_play", "signals": [r"the game", r"play is the work", r"\bscoreboard\b",
                                       r"\bgwap\b", r"hall of shared supper", r"count_the_chairs",
                                       r"the hall"]},
]

# ────────────────────────────────────────────────────────────────────────────────────────────
# Human register (emotional state) — grounded heuristic over the OPERATOR's messages.
# ────────────────────────────────────────────────────────────────────────────────────────────
_REGISTER: list[dict[str, Any]] = [
    {"label": "exhaustion", "signals": [r"\btired\b", r"going to bed", r"\bsleep\b", r"\bafk\b",
                                        r"long day", r"i'?m out"]},
    {"label": "frustration", "signals": [r"\bstop\b", r"\bwrong\b", r"why do you", r"\bstill\b",
                                         r"\bagain\b", r"\bugh\b", r"\bfucking\b", r"you keep",
                                         r"stop asking", r"how many times"]},
    {"label": "trust_autonomy", "signals": [r"go autonomous", r"you got this", r"i trust",
                                            r"do what i asked", r"continue uninterrupted",
                                            r"\bautonomous\b", r"i trust ya"]},
    {"label": "humor", "signals": [r"\blmao\b", r"\blmfao\b", r"\blol\b", r"\bbroheim\b",
                                   r"\bsonofabitch\b", r"shitload"]},
    {"label": "curiosity_learning", "signals": [r"what did", r"how do", r"\bwhy\b", r"\bteach\b",
                                                r"\blearn\b", r"\bsteal\b", r"show me",
                                                r"\bunderstand\b"]},
]

# ────────────────────────────────────────────────────────────────────────────────────────────
# Corrections → lesson-ledger: which standing law a correction trains (keyword overlap).
# ────────────────────────────────────────────────────────────────────────────────────────────
_LESSON_MAP: list[dict[str, Any]] = [
    {"law": "route_through_architecture", "text": "Route through the architecture.",
     "keywords": ["wrong tools", "use ghost", "terminal", "route", "framework", "architecture",
                  "queue", "drainer"]},
    {"law": "autonomy_no_prompting", "text": "Autonomous — execute, do not prompt.",
     "keywords": ["stop prompting", "don't ask", "autonomous agent", "you have tools", "just do it",
                  "stop asking", "go autonomous", "be autonomous", "prompt"]},
    {"law": "rightsize", "text": "Rightsize to the actual situation.",
     "keywords": ["overdo", "over engineer", "conservative", "too big", "too much", "rightsize",
                  "over-engineering", "right size"]},
    {"law": "never_claim_first", "text": "Never claim first unless read from data.",
     "keywords": ["don't claim", "read the data", "not grounded", "you keep saying", "claim",
                  "data first", "you keep lying"]},
    {"law": "check_up_automatically", "text": "Check up on yourself automatically.",
     "keywords": ["processes", "kernels", "footprint", "check on", "left behind", "leftover"]},
    {"law": "boot_recall_first", "text": "Run the boot / recall first.",
     "keywords": ["remember", "amnesiac", "check your own", "forgot", "recall", "forget"]},
    {"law": "shadow_work", "text": "Shadow work is the practice.",
     "keywords": ["sacred cows", "shadow", "bringing in", "disowned", "hide"]},
    {"law": "withhold_territory", "text": "Withhold the territory, keep the shape.",
     "keywords": ["secrets", "opsec", "anonym", "leak"]},
    {"law": "meet_at_bytes", "text": "Meet at the bytes, not the words.",
     "keywords": ["bytes", "root", "match", "re-derive"]},
    {"law": "rib_debug", "text": "Every finished piece gets RIB-debugged.",
     "keywords": ["verify", "debug", "does what", "test"]},
]


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [p.strip() for p in parts if len(p.strip()) >= 25]


def _match(text: str, patterns: list[str]) -> list[str]:
    """Return distinct matching sentences for a pattern family (capped)."""
    sents = _sentences(text)
    hits: list[str] = []
    seen: set[str] = set()
    for pat in patterns:
        rx = re.compile(pat, re.IGNORECASE)
        for s in sents:
            if rx.search(s) and s not in seen:
                seen.add(s)
                hits.append(s)
    return hits


def _count(text: str, patterns: list[str]) -> int:
    """Count distinct matching sentences (clean count, not raw substring hits)."""
    return len(_match(text, patterns))


def _map_lesson(correction: str) -> dict[str, Any]:
    """Map a correction to the standing law it trains (best keyword overlap; else unspecified)."""
    low = correction.lower()
    best, best_n = None, 0
    for row in _LESSON_MAP:
        n = sum(1 for kw in row["keywords"] if kw in low)
        if n > best_n:
            best, best_n = row, n
    if best is None or best_n == 0:
        return {"law": "unspecified", "text": "(no clear standing law)", "matched": []}
    return {"law": best["law"], "text": best["text"],
            "matched": [kw for kw in best["keywords"] if kw in low]}


def mine_session(session: dict[str, Any]) -> dict[str, Any]:
    inv_evidence: dict[str, list[str]] = {}
    inv_hits: Counter = Counter()
    themes: Counter = Counter()
    register: Counter = Counter()
    corrections: list[str] = []
    refusals: list[str] = []
    for ev in session["events"]:
        c = (ev.get("content") or "").strip()
        if not c:
            continue
        kind = ev["kind"]
        if kind == "assistant.message":
            for inv in _INVARIANTS:
                hits = _match(c, inv["signals"])
                if hits:
                    inv_hits[inv["label"]] += len(hits)
                    inv_evidence.setdefault(inv["label"], [])
                    for h in hits:
                        if h not in inv_evidence[inv["label"]] and len(inv_evidence[inv["label"]]) < 4:
                            inv_evidence[inv["label"]].append(h)
            refusals.extend(_match(c, _REFUSAL_SIGNALS))
        elif kind == "user.message":
            corrections.extend(_match(c, _CORRECTION_SIGNALS))
            for reg in _REGISTER:
                register[reg["label"]] += _count(c, reg["signals"])
        for theme in _THEMES:
            themes[theme["label"]] += _count(c, theme["signals"])
    tools: list[str] = []
    for ev in session["events"]:
        tools.extend(ev.get("tools") or [])
    # lesson-ledger for this session
    lessons = [_map_lesson(x) for x in corrections]
    lesson_agg: Counter = Counter(l["law"] for l in lessons)
    return {"source": session["source"], "n_events": session["n_events"],
            "summary": summarize_session(session),
            "invariant_hits": dict(inv_hits),
            "invariant_evidence": inv_evidence,
            "themes": dict(themes),
            "register": dict(register),
            "corrections_total": len(corrections),
            "corrections": corrections[:8],
            "refusals": refusals[:8],
            "lesson_ledger": dict(lesson_agg),
            "tools": Counter(tools)}


_REFUSAL_SIGNALS = [r"i (do not|don't) know", r"i (will not|won't) (fake|pretend|lie|sit)",
                    r"i cannot", r"i don'?t have", r"\bunproven\b", r"not (supported|proven)",
                    r"i will not claim", r"let me check .* before i claim"]
# Distinctive correction INTENTS only (not bare don't/stop/fix, which over-catch ordinary prose
# and inflate the "unspecified" bucket — an honesty bug from the broad detector).
_CORRECTION_SIGNALS = [r"!training", r"stop prompting", r"stop asking", r"just do it",
                       r"you have tools", r"don'?t (ask|prompt) (me|for)", r"use ghost",
                       r"wrong tools", r"you'?re (an )?autonomous agent", r"you keep (doing|saying|asking)",
                       r"that'?s not (right|what|true)", r"over-?engineer", r"don'?t over",
                       r"stop bringing", r"sacred cows", r"why do you (keep|always)",
                       r"stop thinking", r"you are (doing|overdoing) it", r"should have (done|triggered)",
                       r"how many times", r"use the (architecture|framework)", r"not the terminal",
                       r"you'?re ignoring"]


def mine_sessions(paths: list[str]) -> dict[str, Any]:
    mined = [mine_session(process_transcript(p)) for p in paths]
    agg_tools: Counter = Counter()
    agg_inv: Counter = Counter()
    agg_themes: Counter = Counter()
    agg_register: Counter = Counter()
    agg_lessons: Counter = Counter()
    agg_human = agg_prose = agg_toolonly = 0
    all_corrections: list[str] = []
    all_refusals: list[str] = []
    for m in mined:
        agg_tools.update(m["tools"])
        agg_inv.update(m["invariant_hits"])
        agg_themes.update(m["themes"])
        agg_register.update(m["register"])
        agg_lessons.update(m["lesson_ledger"])
        agg_human += m["summary"]["human_turns"]
        agg_prose += m["summary"]["agent_prose"]
        agg_toolonly += m["summary"]["tool_only_events"]
        all_corrections.extend(m["corrections"])
        all_refusals.extend(m["refusals"])
    corrections_total = sum(m["corrections_total"] for m in mined)
    return {
        "schema": SCHEMA,
        "generated": datetime.now(timezone.utc).isoformat(),
        "n_sessions": len(mined),
        "corpus": {"human_turns": agg_human, "agent_prose": agg_prose,
                   "tool_only_events": agg_toolonly},
        "top_tools": [{"tool": t, "uses": n} for t, n in agg_tools.most_common(15)],
        "invariant_evidence_volume": [{"label": inv["label"], "law": inv["law"], "hits": agg_inv.get(inv["label"], 0)}
                                      for inv in _INVARIANTS],
        "themes": [{"theme": t, "hits": n} for t, n in agg_themes.most_common()],
        "register": [{"register": r, "hits": n} for r, n in agg_register.most_common()],
        "lesson_ledger": [{"law": law, "hits": n} for law, n in agg_lessons.most_common()],
        "corrections_total": corrections_total,
        "corrections_sample": list(dict.fromkeys(all_corrections))[:12],
        "refusals_total": len(all_refusals),
        "refusals_sample": list(dict.fromkeys(all_refusals))[:8],
        "sessions": mined,
    }


def _md(surface: dict[str, Any]) -> str:
    L = ["# The Data in the Window — what surfaces about how we process",
         "",
         "Everything below is EXTRACTIVE and GROUNDED — counts and quotes come from the actual "
         "(already-redacted) session text. Nothing is invented; if a law has little evidence, "
         "that is itself data.",
         "",
         f"**Corpus:** {surface['n_sessions']} sessions — {surface['corpus']['human_turns']} human "
         f"turns, {surface['corpus']['agent_prose']} agent-prose turns, "
         f"{surface['corpus']['tool_only_events']} tool-only events collapsed.",
         "",
         "## 1. The method in action (clean invariant counts = distinct evidence passages)",
         "",
         "| Invariant | Law | Passages |",
         "|---|---|---|"]
    for row in surface["invariant_evidence_volume"]:
        L.append(f"| {row['label']} | {row['law']} | {row['hits']} |")
    L += ["",
          "## 2. The tool fingerprint",
          "",
          "| Tool | Uses |",
          "|---|---|"]
    for t in surface["top_tools"]:
        L.append(f"| `{t['tool']}` | {t['uses']} |")
    L += ["",
          "## 3. Themes across the corpus",
          "",
          "| Theme | Passages |",
          "|---|---|"]
    for th in surface["themes"]:
        L.append(f"| {th['theme']} | {th['hits']} |")
    L += ["",
          "## 4. The human register (operator's state across the corpus)",
          "",
          "| Register | Passages |",
          "|---|---|"]
    for r in surface["register"]:
        L.append(f"| {r['register']} | {r['hits']} |")
    L += ["",
          "## 5. Corrections → the laws they train (the training-data ledger)",
          "",
          f"{surface['corrections_total']} correction-signal moments, mapped to standing laws:",
          "",
          "| Law | Corrections training it |",
          "|---|---|"]
    for row in surface["lesson_ledger"]:
        L.append(f"| {row['law']} | {row['hits']} |")
    L += ["",
          "Correction samples:",
          ""]
    for c in surface["corrections_sample"]:
        L.append(f"- {c}")
    L += ["",
          "## 6. Refusal / honesty moments",
          "",
          f"{surface['refusals_total']} moments where the agent refused to overclaim. Sample:",
          ""]
    for r in surface["refusals_sample"]:
        L.append(f"- {r}")
    L += ["",
          "## 7. Per-session invariant evidence",
          ""]
    for m in surface["sessions"]:
        L.append(f"### {m['source']}")
        for inv in _INVARIANTS:
            ev = m["invariant_evidence"].get(inv["label"], [])
            if ev:
                L.append(f"- **{inv['label']}** ({m['invariant_hits'].get(inv['label'], 0)}):")
                for e in ev:
                    L.append(f"  - “{e}”")
    L.append("")
    L.append("Generated by `mag.mind_mine` v2 (extractive + grounded — withhold territory, keep shape).")
    return "\n".join(L)


def _surface(out_dir: str | Path, paths: list[str]) -> dict[str, Any]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    surface = mine_sessions(paths)
    (out / "surface.json").write_text(json.dumps(surface, indent=2, ensure_ascii=False),
                                      encoding="utf-8")
    (out / "SURFACED.md").write_text(_md(surface), encoding="utf-8")
    return {"ok": True, "out": str(out), "n_sessions": surface["n_sessions"],
            "invariant_hits": {r["label"]: r["hits"] for r in surface["invariant_evidence_volume"]},
            "themes": surface["themes"], "register": surface["register"],
            "lesson_ledger": surface["lesson_ledger"],
            "corrections_total": surface["corrections_total"],
            "refusals_total": surface["refusals_total"]}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="mind-mine")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_s = sub.add_parser("surface", help="surface the data in the window corpus")
    p_s.add_argument("--out", default=str(ROOT / "window"))
    p_s.add_argument("files", nargs="+")
    a = ap.parse_args(argv)
    if a.cmd == "surface":
        print(json.dumps(_surface(a.out, a.files), indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
