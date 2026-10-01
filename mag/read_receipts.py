"""READ RECEIPTS — the consumption meter (who actually reads the corpus?).

Operator catch 09-05 ("are they using them?") + consumption audit receipt:
the machine eats what it just cooks, never goes back for leftovers — 40 of 58
surfaces near-zero hits, ghost era unread, 209 Unproven = write-only research.
The usage meter made burn visible; this makes READING visible.

Usage:
    python -m mag.read_receipts sweep

Outputs:
    watch/READ_RECEIPTS.md                the unread-bloat surface
    dashboard/static/read_receipts.json   machine mirror

Measures two sides:
  WRITER side  — back-refs per card (which watch/*.md cards get referenced by
                 other cards, room.jsonl, CONVO.md, memory/*.md).
  READER side  — page hits from logs/dashboard_sv.log (current log window;
                 the log has no timestamps and restarts truncate it).

Stdlib only. ASCII output.
"""
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOGS = [ROOT / "logs" / "dashboard_sv.log",
        ROOT / "logs" / "dashboard_restart.out.log"]
CARD_DIR = ROOT / "watch"
REF_CORPUS = [CARD_DIR,
              ROOT / "watch" / "room.jsonl",
              ROOT / "queue" / "handoff" / "zcode" / "CONVO.md"]
OUT_MD = ROOT / "watch" / "READ_RECEIPTS.md"
OUT_JSON = ROOT / "dashboard" / "static" / "read_receipts.json"
GET_RE = re.compile(r'GET (/static/[A-Za-z0-9_.-]+\.html|/)\s')


def _surface_hits() -> Counter:
    hits: Counter = Counter()
    for log in LOGS:
        if not log.is_file():
            continue
        for line in log.read_text(encoding="utf-8", errors="ignore").splitlines():
            m = GET_RE.search(line)
            if m:
                hits[m.group(1)] += 1
    return hits


def _backrefs() -> tuple[dict[str, int], int]:
    cards = sorted(CARD_DIR.glob("*.md"))
    corpus = ""
    for p in REF_CORPUS:
        if p.is_file():
            corpus += p.read_text(encoding="utf-8", errors="ignore")
        elif p.is_dir():
            for q in p.glob("*.md"):
                corpus += q.read_text(encoding="utf-8", errors="ignore")
    counts = {}
    for c in cards:
        slug = c.stem
        others = corpus.count(slug)
        own = c.read_text(encoding="utf-8", errors="ignore").count(slug)
        counts[slug] = max(0, others - own)
    return counts, len(cards)


def sweep() -> dict:
    hits = _surface_hits()
    backrefs, n_cards = _backrefs()
    all_html = sorted(p.name for p in (ROOT / "dashboard" / "static").glob("*.html"))
    zero_pages = [h for h in ("/static/" + h for h in all_html) if hits.get(h, 0) == 0]
    zero_cards = sorted(k for k, v in backrefs.items() if v == 0)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    data = {
        "built": now,
        "window": "current dashboard log (no timestamps; restarts truncate)",
        "surface_hits": dict(hits.most_common()),
        "zero_hit_pages": zero_pages,
        "cards": n_cards,
        "cards_zero_backrefs": len(zero_cards),
        "backrefs": dict(sorted(backrefs.items(), key=lambda kv: -kv[1])),
        "zero_backref_cards": zero_cards,
    }
    OUT_JSON.write_text(json.dumps(data, ensure_ascii=True, indent=1), encoding="utf-8")

    lines = [
        "# READ RECEIPTS — the consumption meter (mag/read_receipts.py)",
        "",
        f"Built {now}. Window: {data['window']}. Question (operator 09-05): "
        "'are they using them?' Verdict then: the machine eats what it just cooks, "
        "never goes back for leftovers. This page is how that gets caught early.",
        "",
        f"## Surfaces (hits, top 15 of {len(all_html)} pages)",
        "",
    ]
    for page, n in hits.most_common(15):
        lines.append(f"- {n:>5}  {page}")
    lines += ["", f"## ZERO-hit pages ({len(zero_pages)})", ""]
    lines += [f"- {p}" for p in zero_pages[:30]]
    if len(zero_pages) > 30:
        lines.append(f"- …+{len(zero_pages) - 30} more (see json)")
    top_cards = sorted(backrefs.items(), key=lambda kv: -kv[1])[:15]
    lines += ["", f"## Card back-refs (top 15 of {n_cards})", ""]
    lines += [f"- {v:>4}  {k}" for k, v in top_cards if v > 0]
    lines += ["", f"## Cards with ZERO back-refs ({len(zero_cards)})", ""]
    lines += [f"- {k}" for k in zero_cards[:20]]
    if len(zero_cards) > 20:
        lines.append(f"- …+{len(zero_cards) - 20} more (see json)")
    lines += ["", "Zero back-refs is not shame — new cards start at zero. The signal "
              "is CARDS THAT STAY AT ZERO: written, never read, never disproven. "
              "Feed them to the topic index or disposition them.", ""]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    return data


if __name__ == "__main__":
    d = sweep()
    print(f"read_receipts: {len(d['surface_hits'])} pages hit, "
          f"{len(d['zero_hit_pages'])} zero-hit, {d['cards']} cards, "
          f"{d['cards_zero_backrefs']} zero-backref -> {OUT_MD.relative_to(ROOT)}")
