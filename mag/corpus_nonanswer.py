"""Detect NON-ANSWERS that the fan-out counted as answers.

`retry` reports `answered: 57/57`, but "answered" only means a row came back non-empty. B08 is
the proof that those are not the same thing: `or-nemotron` returned 135 words of deliberation --
"Not sure. ... I recall that ... Maybe I should include ... Perhaps" -- and the reasoning-strip
removed the scaffold, leaving a clean-looking 135-word paragraph that contains no work, no
author, no year and no source.

That row moves the headline completeness figure without moving knowledge one bit, and it is the
most dangerous kind of defect in this pack: it is invisible in every count I reported.

This module scores each answer for ANSWER-SHAPED content rather than NON-EMPTY content:
  * does it name a work / author / year / source at all?
  * how much of it is hedging rather than assertion?
  * how much of it is first-person deliberation?

A row can be non-empty, un-hedged, and still be a non-answer. So all three are scored, and the
verdict is the conjunction, not any single signal.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "memory" / "runs" / "corpus_gap_research" / "raw.jsonl"
OUT = ROOT / "memory" / "runs" / "corpus_gap_research"

# a citation-shaped token: an author name, a year, a source name, or an id
YEAR = re.compile(r"\b(1[5-9]\d{2}|20[0-2]\d)\b")
SOURCE = re.compile(r"\b(?:gutenberg|archive\.org|standard ebooks|wikisource|open library|"
                    r"hathitrust|loc\.gov|doi\.org|arxiv|pg\s*#?\d)\b", re.IGNORECASE)
IDLIKE = re.compile(r"\b(?:10\.\d{4,9}/|PG\s*#?\s*\d{3,6}|isbn[:\s])", re.IGNORECASE)
ITALIC = re.compile(r"\*[^*\n]{4,80}\*")          # a titled work
HEDGE = re.compile(r"\b(?:not sure|maybe|perhaps|i recall|i think|unclear|"
                   r"i believe|possibly|seems|might be|actually,)\b", re.IGNORECASE)
DELIB = re.compile(r"\b(?:i should|i don't know|i'm not|let me|as an ai|"
                   r"i apologize|hope this|would need to|isn't aware)\b", re.IGNORECASE)


def score(ans: str) -> dict:
    a = ans or ""
    words = a.split()
    n = len(words) or 1
    works = len(ITALIC.findall(a))
    years = len(set(YEAR.findall(a)))
    srcs = len(set(SOURCE.findall(a)))
    ids = len(set(IDLIKE.findall(a)))
    hedge = len(HEDGE.findall(a))
    delib = len(DELIB.findall(a))
    # citation density: does the answer actually point at things?
    density = (works + min(years, 5) + min(srcs, 3) + min(ids, 3)) / max(1, n / 100)
    # deliberation share
    noise = (hedge + delib * 2) / n

    # CORRECTION (measured, 2026-09-29): the first version scored G07 a NON_ANSWER. Reading it,
    # G07 is a TRUNCATION -- the lane listed a real GDC Vault postmortem (Dark Souls II, Yui
    # Tanimura, gdcvault.com/play/1024532) and the token cap cut it mid-word at "Blood". That is
    # a budget defect, not an empty one, and calling it a non-answer is the same class of error
    # as the one this module hunts: mislabelling a defect to move a number.
    truncated = bool(a) and not a.rstrip().endswith((".", ")", "\"", "'", "]", "。", "）"))

    if works == 0 and ids == 0 and srcs == 0 and not truncated:
        verdict = "NON_ANSWER"          # points at nothing at all
    elif truncated and works == 0 and ids == 0 and srcs == 0:
        verdict = "TRUNCATED"           # real content cut off by the token cap
    elif density < 0.5 and noise > 0.02:
        verdict = "THIN"                # names something, barely
    elif noise > 0.05:
        verdict = "HEDGED"              # real content, unreliable delivery
    else:
        verdict = "ANSWER"
    return {"words": len(words), "italic_titles": works, "years": years,
            "sources": srcs, "ids": ids, "hedges": hedge, "deliberation": delib,
            "truncated_at_cap": truncated,
            "citation_density_per_100w": round(density, 2),
            "noise_share": round(noise, 4), "verdict": verdict}


def best_rows() -> dict[str, dict]:
    best: dict[str, dict] = {}
    if not RAW.is_file():
        return best
    for ln in RAW.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            r = json.loads(ln)
        except Exception:
            continue
        if not r.get("ok") or not r.get("qid"):
            continue
        if r["qid"] not in best or (r.get("chars") or 0) > (best[r["qid"]].get("chars") or 0):
            best[r["qid"]] = r
    return best


def main() -> int:
    best = best_rows()
    rows = []
    for qid, r in sorted(best.items()):
        s = score(r.get("answer") or "")
        s.update({"qid": qid, "lane": r.get("lane"), "question": r.get("question")})
        rows.append(s)

    tally = Counter(r["verdict"] for r in rows)
    by_lane: dict[str, Counter] = {}
    for r in rows:
        by_lane.setdefault(r["lane"] or "?", Counter())[r["verdict"]] += 1

    out = {
        "schema": "corpus_nonanswer.v1",
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "law": "a returned row is not an answer; an answer points at something checkable",
        "note": ("retry's `answered` counter only means the row came back non-empty. This "
                 "module re-scores the SAME rows for answer-shaped content. The gap between the "
                 "two numbers is the honest completeness figure."),
        "answered_per_retry": len(rows),
        "verdicts": dict(tally),
        "real_answers": tally.get("ANSWER", 0),
        "completeness_pct": round(100 * tally.get("ANSWER", 0) / max(1, len(rows)), 1),
        "by_lane": {k: dict(v) for k, v in sorted(by_lane.items())},
        "non_answers": [r for r in rows if r["verdict"] == "NON_ANSWER"],
    }
    (OUT / "nonanswer.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    L = ["# NON-ANSWERS — rows the fan-out counted as answers that name nothing", "",
         f"*repack says **57/57 answered**. Re-scored for answer-shaped content: "
         f"**{out['real_answers']} real answers ({out['completeness_pct']}%)**, "
         f"{tally.get('THIN', 0)} thin, {tally.get('HEDGED', 0)} hedged, "
         f"**{tally.get('NON_ANSWER', 0)} non-answers** · {out['ts']}*", "",
         f"> **{out['law']}**", "",
         "| verdict | n |", "|---|---:|"]
    for k, v in tally.most_common():
        L.append(f"| {k} | {v} |")
    L += ["", "## Non-answers — the rows that moved the headline without moving knowledge", "",
          "| qid | lane | words | titles | sources | question |", "|---|---|---:|---:|---:|---|"]
    for r in out["non_answers"]:
        L.append(f"| {r['qid']} | `{r['lane']}` | {r['words']} | {r['italic_titles']} | "
                 f"{r['sources']} | {str(r.get('question') or '')[:52]} |")
    L += ["", "## By lane", "", "| lane | verdicts |", "|---|---|"]
    for ln, c in out["by_lane"].items():
        L.append(f"| `{ln}` | {', '.join(f'{k}={v}' for k, v in sorted(c.items()))} |")
    L += ["", "## Why this matters", "",
          "Every completeness number I reported before this module counts a 135-word paragraph of",
          "\"Not sure ... Maybe ... Perhaps\" exactly like a 372-word list of 20 cited works. Both",
          "are non-empty rows on the tape. B08 (Indigenous and Pacific shelf) is the clean",
          "example: the lane deliberated, the stripper cut the scaffold, and what remained reads",
          "like an answer in a diff and in a word count.",
          "",
          "**The honest completeness figure is the ANSWER count, not the answered count.**",
          "The shelf gap is wider than 57/57 suggested, and it is widest exactly where the",
          "corpus is emptiest."]
    (OUT / "NONANSWER.md").write_text("\n".join(L), encoding="utf-8")
    print(json.dumps({"answered_per_retry": len(rows), "verdicts": dict(tally),
                      "completeness_pct": out["completeness_pct"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
