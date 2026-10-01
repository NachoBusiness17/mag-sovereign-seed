"""TOPIC INDEX — the card catalog the corpus never had.

Archaeology finding G5-1 (watch/RESEARCH_ARCHAEOLOGY_20260905.md): 640 cards
organized by TIME and SEAT, never TOPIC — no organ can answer "what do we know
about X" without reading everything. This is that organ.

Usage:
    python -m mag.topic_index build              # rebuild md + json mirrors
    python -m mag.topic_index query autoglm      # what do we know about X

Outputs:
    watch/TOPIC_INDEX.md                human spine + catalog
    dashboard/static/topic_index.json   machine mirror (served at /static/)

Stdlib only. ASCII output (Windows console). Deterministic: filename slug +
H1 vocabulary (the spine) + dominant BODY terms (term frequency, stopword-
filtered, >=3 occurrences, top 8 per card), merged into one inverted index.
Spine terms keep priority in per-card ordering.
"""
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCAN_ROOTS = [
    ROOT / "watch",
    ROOT / "queue" / "handoff",   # flat ghost-era stratum only (no seat dirs)
    ROOT / "memory",              # flat cards only (479 run dirs NOT walked)
]
OUT_MD = ROOT / "watch" / "TOPIC_INDEX.md"
OUT_JSON = ROOT / "dashboard" / "static" / "topic_index.json"

STOPWORDS = {
    "intake", "card", "watch", "self", "steal", "salon", "receipt", "receipts",
    "session", "night", "note", "notes", "filed", "sealed", "verkle", "knot",
    "memo", "memorandum", "draft", "index", "build", "built", "review",
    "deep", "research", "roadmap", "window", "windows", "shift", "digest",
    "with", "that", "this", "from", "have", "what", "when", "were", "they",
    "2026", "2025", "handoff", "memory", "queue", "docs", "ref", "static",
    "master", "order", "status", "state", "close", "closes", "sweep", "part",
    "lite", "seat", "seats", "gpt", "astra", "round",
}

# Body-term extraction guards: cap the body text scanned per card (~40KB) and
# require >=3 occurrences so the full build stays well under the ~60s budget
# for 696 files (body tokenization adds <1s at this corpus size).
BODY_SCAN_CHARS = 40960
BODY_MIN_COUNT = 3
BODY_TOP = 8
SPINE_TOP = 14

DATE_RE = re.compile(r"(20\d{2})(\d{2})(\d{2})")
SCORE_RE = re.compile(r"\b(\d{1,2})/25\b")
STATES = {
    "DISPUTED": re.compile(r"\bDISPUTED\b"),
    "UNPROVEN": re.compile(r"\bUnproven\b", re.I),
    "WINDOWED": re.compile(r"\bWINDOWED\b"),
    "BUILD NOW": re.compile(r"BUILD NOW"),
    "OWED": re.compile(r"\bOWED\b", re.I),
    "FOLDED": re.compile(r"\bFOLDED\b|\bTOMBSTONED\b|\bROUTED\b"),
}


def _scan_files():
    for root in SCAN_ROOTS:
        if not root.is_dir():
            continue
        for p in sorted(root.glob("*.md")):
            yield p


def _parse(p: Path) -> dict | None:
    try:
        text = p.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None
    if not text.strip():
        return None
    m = DATE_RE.search(p.name)
    date = f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else ""
    sc = SCORE_RE.search(text[:6000])
    states = [s for s, rx in STATES.items() if rx.search(text[:6000])]
    h1 = next((l.lstrip("# ").strip() for l in text.splitlines()
               if l.startswith("# ")), "")
    spine_tokens = Counter(
        t for t in re.split(r"[^a-z0-9]+", (p.stem + " " + h1).lower())
        if len(t) >= 4 and t not in STOPWORDS and not t.isdigit()
    )
    # dominant BODY terms: frequency over the card body (capped scan), same
    # filters as the spine, kept only at >=3 occurrences, top ~8 per card
    body_tokens = Counter(
        t for t in re.split(r"[^a-z0-9]+", text[:BODY_SCAN_CHARS].lower())
        if len(t) >= 4 and t not in STOPWORDS and not t.isdigit()
    )
    spine = [t for t, _ in spine_tokens.most_common(SPINE_TOP)]
    return {
        "file": str(p.relative_to(ROOT)).replace("\\", "/"),
        "title": h1[:90] or p.stem,
        "date": date,
        "score": int(sc.group(1)) if sc else None,
        "states": states,
        "spine": spine,
        "body_tokens": body_tokens,
    }


def build() -> dict:
    cards = [c for c in (_parse(p) for p in _scan_files()) if c]
    # v3: document-frequency reweighting. Raw top-8 TF lets generic corpus
    # words (operator, lane, ...) crowd out distinctive mid-rank terms
    # (autoglm ranked 11th of 62 in its best file). weight = count * log(N/df)
    # promotes terms that are frequent HERE but rare across the corpus.
    n = len(cards)
    df: Counter = Counter()
    for c in cards:
        df.update(c["body_tokens"].keys())
    for c in cards:
        ranked = sorted(
            (t for t, cnt in c["body_tokens"].items() if cnt >= BODY_MIN_COUNT),
            key=lambda t: (-(c["body_tokens"][t] * math.log(n / df[t])), t),
        )
        seen = set(c["spine"])
        c["topics"] = c["spine"] + [t for t in ranked if t not in seen][:BODY_TOP]
        del c["body_tokens"]  # never serialized into the mirrors

    index: dict[str, list[int]] = defaultdict(list)
    for i, c in enumerate(cards):
        for t in c["topics"]:
            index[t].append(i)

    topics = sorted(index.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    stats = {
        "built": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        "cards": len(cards),
        "topics": len(topics),
        "dated": sum(1 for c in cards if c["date"]),
        "scored": sum(1 for c in cards if c["score"] is not None),
    }

    lines = [
        "# TOPIC INDEX — the card catalog (rebuilt nightly by mag/topic_index.py)",
        "",
        f"Built {stats['built']} · {stats['cards']} cards · "
        f"{stats['topics']} topics · {stats['dated']} dated · {stats['scored']} scored. "
        "Query mode: `python -m mag.topic_index query <term>`. Machine mirror: "
        "/static/topic_index.json. Finding G5-1: organized by time+seat never topic — "
        "this file is the fix. Ten-minute test: search this page, read the listed cards.",
        "",
    ]
    for term, idxs in topics[:80]:
        lines.append(f"## {term} ({len(idxs)})")
        for i in idxs[:20]:
            c = cards[i]
            bits = [c["date"] or "----", c["title"]]
            if c["score"] is not None:
                bits.append(f"{c['score']}/25")
            if c["states"]:
                bits.append(",".join(c["states"]))
            lines.append(f"- {bits[0]} [{c['file']}] {bits[1]}"
                         + (f" — {bits[2]}" if len(bits) > 2 else "")
                         + (f" · {bits[3]}" if len(bits) > 3 else ""))
        if len(idxs) > 20:
            lines.append(f"- …+{len(idxs) - 20} more (see json)")
        lines.append("")

    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    OUT_JSON.write_text(json.dumps({
        "stats": stats,
        "topics": {t: [cards[i] for i in idxs] for t, idxs in topics},
    }, ensure_ascii=True), encoding="utf-8")
    return stats


def query(terms: list[str]) -> int:
    if not OUT_JSON.is_file():
        build()
    data = json.loads(OUT_JSON.read_text(encoding="utf-8"))
    hits = 0
    for t in terms:
        shown = False
        for size in (t, t.rstrip("s")):
            if size in data["topics"]:
                rows = data["topics"][size]
                print(f"{size}: {len(rows)} cards (spine)")
                for c in rows[:12]:
                    st = ",".join(c["states"]) or "-"
                    sc = f"{c['score']}/25" if c["score"] is not None else "-"
                    print(f"  {c['date'] or '----'} {sc:>6} {st:<24} {c['file']}")
                hits += 1
                shown = True
                break
        # full-text recall fallback: the spine is filename+H1; bodies answer too
        ft = _fulltext(t)
        if ft:
            print(f"{t}: {len(ft)} files mention it in the BODY"
                  + ("" if shown else " (spine: no hits)"))
            for f in ft[:12]:
                print(f"  {f}")
            hits += 1
        elif not shown:
            print(f"{t}: no hits")
    return hits


def _fulltext(term: str) -> list[str]:
    out = []
    rx = re.compile(re.escape(term), re.I)
    for p in _scan_files():
        try:
            if rx.search(p.read_text(encoding="utf-8", errors="ignore")):
                out.append(str(p.relative_to(ROOT)).replace("\\", "/"))
        except OSError:
            pass
    return out


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "build":
        s = build()
        print(f"topic_index: {s['cards']} cards, {s['topics']} topics -> "
              f"{OUT_MD.relative_to(ROOT)}")
    elif len(sys.argv) >= 3 and sys.argv[1] == "query":
        n = query([t.lower() for t in sys.argv[2:]])
        sys.exit(0 if n else 1)
    else:
        print(__doc__)
        sys.exit(2)
