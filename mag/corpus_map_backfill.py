"""Build the librarian's register backfill: verified real citations, ready to merge into the map.

`mag.librarian.py` reports 933 arXiv ids cited in cards but absent from BIBLIOGRAPHY_MAP.md, and
reports 220 rows that are RETRIEVAL-PLAN (source named, primary not pulled+hashed). Two very
different problems, and this addresses the first:

    907 of the 933 are CONFIRMED REAL (arXiv title fetched, control passed).

So the map is behind the desk on genuine literature, not on hallucination. The citation law
("a wrong citation is worse than an honest gap") is satisfied by construction here: this module
only emits rows whose title was fetched from arXiv, so every line it produces is verifiable.

It does NOT touch BIBLIOGRAPHY_MAP.md. It writes a reviewable, sorted, deduplicated candidate
block plus a machine-readable JSON, and merging is the operator's call -- a map that silently
grew 900 rows on a seat's say-so would be exactly the unbidden write the standing law forbids.

Critically it also never marks a row PULLED: only 9 of 275 map rows are PULLED+HASHED today, and
conflating "the citation is real" with "we hold the paper" is the exact confusion the librarian's
PULLED / RETRIEVAL-PLAN vocabulary exists to prevent. Every row here lands as a PLAN, with a
fetched title as evidence.

Writes: memory/runs/corpus_gap_research/MAP_BACKFILL.md + MAP_BACKFILL.json
"""
from __future__ import annotations

import html
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REG = ROOT / "memory" / "runs" / "corpus_gap_research" / "ARXIV_REGISTER.json"
OUT = ROOT / "memory" / "runs" / "corpus_gap_research"
MAP = ROOT / "docs" / "ref" / "BIBLIOGRAPHY_MAP.md"


def _theme(cited_in: str) -> str:
    """Bucket a citation by where it was used -- that is the only curation signal available."""
    p = cited_in.lower()
    if "moonshot" in p or "physics" in p:
        return "physics"
    if "physical_computing" in p or "cube" in p:
        return "physical-computing"
    if "burn_reset" in p or "selffeed" in p:
        return "self-feed"
    if "corpus" in p or "papers" in p:
        return "corpus"
    return "general"


def main() -> int:
    if not REG.is_file():
        print("run `python -m mag.corpus_arxiv_register` first", flush=True)
        return 2
    reg = json.loads(REG.read_text(encoding="utf-8"))
    real = [r for r in reg["results"] if r["verdict"] == "REAL"]
    unresolved = [r for r in reg["results"] if r["verdict"] != "REAL"]

    by_theme: dict[str, list[dict]] = defaultdict(list)
    for r in real:
        by_theme[_theme(r["cited_in"])].append(r)

    # already in the map? dedupe against the map text so we never propose a duplicate row
    map_text = MAP.read_text(encoding="utf-8", errors="replace") if MAP.exists() else ""
    already = {m for m in re.findall(r"\b(\d{4}\.\d{4,5})\b", map_text)}
    fresh = [r for r in real if r["arxiv_id"] not in already]
    dupes = [r for r in real if r["arxiv_id"] in already]

    v = {
        "schema": "map_backfill.v1",
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "law": "a wrong citation is worse than an honest gap",
        "source": "mag.corpus_arxiv_register (title fetched from arxiv.org, control passed)",
        "unregistered_total": reg["unregistered_count"],
        "confirmed_real": len(real),
        "already_in_map": len(dupes),
        "fresh_for_map": len(fresh),
        "unresolved_not_claimed": len(unresolved),
        "themes": {k: len(v_) for k, v_ in sorted(by_theme.items())},
        "map_untouched": True,
        "every_row_is_a_plan": True,
        "promotion_rule": ("fetch the PDF, sha256 it, drop a receipt under "
                           "docs/report_v1/sources/receipts/<arxiv-id>.md, and only then does a "
                           "row move from RETRIEVAL-PLAN to PULLED+PULLED+HASHED"),
        "rows": fresh,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "MAP_BACKFILL.json").write_text(json.dumps(v, indent=2, ensure_ascii=False), encoding="utf-8")

    L = [f"# MAP BACKFILL — {len(fresh):,} verified real citations the map is missing", "",
         f"*{v['confirmed_real']} of {v['unregistered_total']} unregistered ids confirmed real · "
         f"{v['already_in_map']} already present in the map · **{v['fresh_for_map']} genuinely "
         f"new** · {v['unresolved_not_claimed']} unresolved and NOT claimed · {v['ts']}*", "",
         f"> **{v['law']}**", "",
         "Every row below carries a title fetched from arxiv.org, so every row is verifiable. "
         "**`docs/ref/BIBLIOGRAPHY_MAP.md` was NOT modified** — merging 900 rows is the "
         "operator's call, not this seat's.", "",
         "## Every row here is a RETRIEVAL-PLAN, not a PULLED source", "",
         f"{v['promotion_rule']}. Only **9 of 275** map rows are PULLED+HASHED today, and "
         "\"the citation is real\" is not the same claim as \"we hold the paper\".", "",
         "## Themes", "", "| bucket | fresh rows |", "|---|---:|"]
    for k, n in sorted(v["themes"].items(), key=lambda kv: -kv[1]):
        L.append(f"| {k} | {n} |")
    L += ["", f"## The rows ({len(fresh):,})", "",
          "| arXiv id | fetched title | first cited in |", "|---|---|---|"]
    for r in sorted(fresh, key=lambda x: x["arxiv_id"]):
        # arXiv serves HTML-escaped titles; `Don't` arrives as `Don&#39;t`. Unescape so the
        # backfill is copy-pasteable, and collapse the whitespace newlines introduce.
        t = re.sub(r"\s+", " ", html.unescape(r["title"])).strip()
        L.append(f"| {r['arxiv_id']} | {t[:78]} | {r['cited_in'][:44]} |")
    L += ["", "## Unresolved — not claimed either way", "",
          f"{v['unresolved_not_claimed']} ids returned HTTP 406 from arxiv.org/abs and could not "
          "be resolved through the export API either. 406 is content negotiation, not a dead "
          "paper, so these are **inconclusive** and are excluded from the backfill rather than "
          "guessed at.", ""]
    (OUT / "MAP_BACKFILL.md").write_text("\n".join(L), encoding="utf-8")
    print(json.dumps({k: v[k] for k in ("confirmed_real", "already_in_map", "fresh_for_map",
                                       "unresolved_not_claimed")}, indent=2))
    print("themes:", json.dumps(v["themes"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
