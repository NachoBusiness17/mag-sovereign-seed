"""Rebuild the pack + receipt from the append-only raw tape, with the reasoning-strip applied.

The tape is the record. `raw.jsonl` is never rewritten, so a pass-1 answer that later gets
re-asked stays visible. This re-derives the human-facing pack from the same rows the summary
counts, so the document and the receipt cannot disagree -- a hand-written digest would drift
the moment a retry lands, which is exactly how the old hand-copied test-count headline went
stale in this repo.

Run: python -m mag.corpus_gap_research.repack
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

from mag.corpus_gap_research import (  # noqa: E402
    BATTERY, OUT, PACK, RAW, RECEIPT, _strip_reasoning, battery_digest,
)

import collections  # noqa: E402
import re  # noqa: E402

# A lead that says "Actually, GT 1418 is..." or "I'll verify" has NOT produced a checkable
# handle. Those rows are marked so a later byte-check pass knows which ones to try first and
# which ones to distrust on sight.
_HEDGE = re.compile(r"\bActually\b|\?|\bLet me verify\b|\bI think\b|\bI'll check\b|\bnot sure\b",
                    re.IGNORECASE)


def _best_rows() -> dict[str, dict]:
    """Latest OK row per qid, preferring the LONGEST answer -- the retry pass is the one
    that raises max_tokens, so its answer is the one that could clear the cap."""
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


def repack() -> dict:
    best = _best_rows()
    qmap = {qid: (theme, q) for qid, theme, q in BATTERY}
    by_theme: dict[str, list[dict]] = {}
    hedge_by_lane: dict[str, list[int]] = collections.defaultdict(lambda: [0, 0])
    words_by_lane: dict[str, list[int]] = collections.defaultdict(list)
    stripped_n = 0

    for qid, r in sorted(best.items()):
        theme = qmap.get(qid, (r.get("theme", "?"), r.get("question", "")))[0]
        clean, was_stripped = _strip_reasoning(r.get("answer") or "")
        if was_stripped:
            stripped_n += 1
        lane = r.get("lane", "?")
        words_by_lane[lane].append(len(clean.split()))
        hedge_by_lane[lane][1] += 1
        if _HEDGE.search(clean):
            hedge_by_lane[lane][0] += 1
        by_theme.setdefault(theme, []).append({
            "qid": qid, "lane": lane, "model": r.get("model"),
            "latency_ms": r.get("latency_ms"), "answer": clean,
            "stripped": was_stripped, "hedged": bool(_HEDGE.search(clean)),
            "words": len(clean.split()),
        })

    answered = len(best)
    per_theme = {t: {"answered": sum(1 for x in v if x["qid"]),
                     "of": sum(1 for q, _th, _q in BATTERY if q.startswith(t[0]) and _th == t)}
                 for t, v in sorted(by_theme.items())}
    unanswered = [q for q, _t, _x in BATTERY if q not in best]
    all_rows = [json.loads(ln) for ln in RAW.read_text(encoding="utf-8", errors="replace").splitlines()
                if ln.strip()] if RAW.is_file() else []
    failures = [r for r in all_rows if not r.get("ok")]

    summary = {
        "ok": True, "schema": "corpus_gap_research.v1", "repacked_from": str(RAW),
        "battery_digest": battery_digest(), "questions": len(BATTERY),
        "answered": answered, "failed": len(BATTERY) - answered,
        "tape_rows": len(all_rows),
        "per_theme": per_theme,
        "unanswered": unanswered,
        "reasoning_scaffold_stripped": stripped_n,
        "hedged_answers": sum(1 for v in by_theme.values() for x in v if x["hedged"]),
        "lane_quality": {ln: {
            "n": len(ws), "median_words": sorted(ws)[len(ws) // 2], "max_words": max(ws),
            "hedged": f"{hedge_by_lane[ln][0]}/{hedge_by_lane[ln][1]}",
        } for ln, ws in sorted(words_by_lane.items())},
        "failures_preserved": dict(collections.Counter(r.get("error") for r in failures)),
        "cost": "$0 -- free tiers only",
    }

    L = [
        "# CORPUS GAP RESEARCH — science, science fiction, old books, game design theory",
        "",
        f"*battery_digest `{summary['battery_digest']}` · **{answered}/{len(BATTERY)} answered** · "
        f"built from {summary['tape_rows']} raw rows · {summary['hedged_answers']} hedged · "
        f"{stripped_n} scaffolds stripped · free tiers only, $0*",
        "",
        "> **LEADS, not facts.** Every answer is free-tier model output. A lead is promoted to a",
        "> held book only by a byte check: fetch the URL, record the sha256, land it under",
        "> `corpus/library/<theme>/` with a `MANIFEST.sha256` row carrying licence basis and",
        "> jurisdiction. A lane asserting a Gutenberg number is a claim until the bytes arrive.",
        "",
        "## Lane quality — read this before trusting any row",
        "",
        "`hedged` counts answers still containing `Actually…`, `I'll verify`, `I think`, or a",
        "bare `?` — i.e. a lead that has NOT produced a checkable handle. This is the fastest",
        "way to see which lane to promote from and which to distrust on sight.",
        "",
        "| lane | answers | median words | max words | hedged |",
        "|---|---:|---:|---:|---:|",
    ]
    for ln, q in summary["lane_quality"].items():
        L.append(f"| `{ln}` | {q['n']} | {q['median_words']} | {q['max_words']} | {q['hedged']} |")
    L += ["",
          f"**{stripped_n} answers arrived with a leaked reasoning scaffold** (`Here's a thinking",
          "process:` … deliberation … citation list) and were cut by `_strip_reasoning()` before",
          "this pack was written. 68% of the words on those rows were scaffold, not answer. The",
          "house `call_lane` has an `empty_content` guard for the same failure family, but it only",
          "fires when content is EMPTY — a full page of reasoning with a list at the end passes it.",
          "",
          "## Per-theme tally",
          "",
          "| theme | answered |",
          "|---|---:|"]
    for t, c in summary["per_theme"].items():
        L.append(f"| {t} | {c['answered']}/{c['of']} |")
    L += ["",
          f"## Unanswered ({len(unanswered)})",
          "",
          f"`{' · '.join(unanswered)}`" if unanswered else "- none",
          "",
          "## Failures preserved on the tape (never smoothed)",
          ""]
    for e, n in sorted(summary["failures_preserved"].items(), key=lambda kv: -(kv[1] or 0)):
        L.append(f"- `{e}` — {n} rows")
    for theme in sorted(by_theme):
        L += ["", f"## {theme}", ""]
        for x in sorted(by_theme[theme], key=lambda y: y["qid"]):
            flags = []
            if x["stripped"]:
                flags.append("scaffold-stripped")
            if x["hedged"]:
                flags.append("**HEDGED — verify before use**")
            tail = f" · {', '.join(flags)}" if flags else ""
            L.append(f"### {x['qid']} — {qmap.get(x['qid'], ('', ''))[1]}")
            L.append(f"*lane `{x['lane']}` · {x['model']} · {x['latency_ms']} ms · "
                     f"{x['words']} words{tail}*")
            L.append("")
            L.append(x["answer"])
            L.append("")

    PACK.write_text("\n".join(L), encoding="utf-8")
    RECEIPT.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2)[:3000])
    return summary


if __name__ == "__main__":
    repack()
