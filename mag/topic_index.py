"""TOPIC INDEX v4 — the card catalog the corpus never had.

Archaeology finding G5-1 (watch/RESEARCH_ARCHAEOLOGY_20260905.md): ~640 cards
organized by TIME and SEAT, never TOPIC — no organ can answer "what do we know
about X" without reading everything. This is that organ.

v4 (concurrency probe group 2, 2026-09-05) supersedes the v3 TF-IDF draft
(preserved as mag/topic_index_v3_tf_draft.py, mirrors watch/TOPIC_INDEX.md +
dashboard/static/topic_index.json left in place): bones stolen (query mode,
states extraction, fulltext recall), reinterpretation named — fixed KEYWORD
BUCKETS instead of free-form TF terms, so every topic has a stable, speakable
name; recursive stream of every *.md under --dir (v3 globbed top level only,
missing inbox/ scout/ hermes_wings/ ...); files >2MB skipped; deterministic
output (identical json run-to-run except generated_at).

Usage:
    python -m mag.topic_index build [--dir watch]
    python -m mag.topic_index query <term> [term...]

Outputs (new files only, never edits existing cards):
    <dir>/topic_index.json          machine: {generated_at, cards:[...]}
    <dir>/TOPIC_INDEX_20260905.md   human: per-topic lists, newest first,
                                    count + median score, + no-topic bucket

Stdlib only, streaming (line-by-line, O(1) memory per card), ASCII-safe output.
"""
import argparse
import datetime
import json
import os
import re
import statistics
import sys
from collections import Counter

MAX_FILE_BYTES = 2 * 1024 * 1024   # skip files > 2MB
HEAD_CHARS = 6000                  # content prefix used for topic matching + states
JSON_OUT = "topic_index.json"
MD_OUT = "TOPIC_INDEX_20260905.md"

DATE_RE = re.compile(r"(20\d{2})(\d{2})(\d{2})")
SCORE_RE = re.compile(r"\b(\d{1,2})/25\b")
HEADING_RE = re.compile(r"^#{1,6}\s+(.*\S)\s*$")
STATES = {
    "DISPUTED": re.compile(r"\bDISPUTED\b"),
    "UNPROVEN": re.compile(r"\bUnproven\b", re.I),
    "WINDOWED": re.compile(r"\bWINDOWED\b"),
    "BUILD NOW": re.compile(r"BUILD NOW"),
    "OWED": re.compile(r"\bOWED\b", re.I),
    "FOLDED": re.compile(r"\bFOLDED\b|\bTOMBSTONED\b|\bROUTED\b"),
}

# topic name -> keywords. Matched against relpath + title + content head,
# normalized (lowercased, -/_ folded to space) with word boundaries, so
# "vision" never matches "revision". Multi-label: one card, many topics.
TOPIC_BUCKETS = [
    ("x-harvest", ["x harvest", "xbatch", "x canon", "x deck", "harvest",
                   "canon reply", "deck"]),
    ("astra", ["astra"]),
    ("concurrency", ["concurrency", "conc probe", "conc test", "8 wide",
                     "five wide", "parallel worker", "swarm worker"]),
    ("auth-lite", ["auth", "lite", "free lane", "quota", "refill", "fuel feed",
                   "rib chat", "groq", "coding plan", "parked"]),
    ("vision", ["vision", "multimodal", "eyes receipt", "vlm", "screenshot",
                "image pipeline", "dumb agent with eyes"]),
    ("shadow-fields", ["shadow field", "shadowfields", "shadertoy", "lightmap",
                       "tornado xsk3rr"]),
    ("beacon", ["beacon"]),
    ("gstd", ["gstd"]),
    ("salon", ["salon"]),
    ("verkle-chain", ["verkle", "knot", "opentimestamps", "hash chain",
                      "chain v1", "chain v2", "seal"]),
    ("refguard-refeed", ["refguard", "refeed", "re feed", "rearm", "re arm",
                         "watchdog", "guard"]),
    ("intake", ["intake"]),
    ("self-steal", ["self steal", "selfsteal"]),
    ("dnd-game", ["dnd", "d&d", "game", "maze", "riddle", "dungeon", "kaliset",
                  "threebody", "nnue", "arena"]),
    ("overseer", ["overseer"]),
    ("grounding", ["grounding", "ground wave", "ground ledger"]),
    ("trajectory", ["trajectory"]),
    ("android", ["android", "autoglm", "emulator", "apk"]),
    ("mcp", ["mcp"]),
    ("docker-fleet", ["docker", "container", "cage", "night shift", "warden"]),
    ("economics", ["tokenomic", "economics", "spend", "budget", "penny",
                   "cost per"]),
    ("max-distill", ["max distill", "distill"]),
    ("corpus-canon", ["corpus", "canon", "training material", "oral history",
                      "library"]),
]

_TOPIC_RES = [
    (name, [re.compile(r"(?<![a-z0-9])" + re.escape(k) + r"(?![a-z0-9])")
            for k in kws])
    for name, kws in TOPIC_BUCKETS
]


def _norm(text):
    return re.sub(r"[-_]+", " ", text.lower())


def _topics_for(relpath, title, head):
    hay = _norm(relpath + "\n" + title + "\n" + head)
    return [name for name, res in _TOPIC_RES
            if any(r.search(hay) for r in res)]


def _extract_card(full_path, relpath):
    """Stream one card: title (first heading), max rubric score, filename
    date, tri-state/disposition flags, topic tags."""
    title = None
    best_score = None
    date = None
    states = []
    head_parts = []
    head_len = 0
    base = os.path.basename(relpath)
    with open(full_path, "r", encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            if title is None:
                m = HEADING_RE.match(raw)
                if m:
                    title = m.group(1).strip()
            m = SCORE_RE.search(raw)
            if m:
                v = int(m.group(1))
                if best_score is None or v > best_score:
                    best_score = v
            if not states:
                states = [s for s, rx in STATES.items() if rx.search(raw)]
            if date is None:
                dm = DATE_RE.search(base)
                if dm:
                    d = dm.group(0)
                    date = f"{d[0:4]}-{d[4:6]}-{d[6:8]}"
            if head_len < HEAD_CHARS:
                head_parts.append(raw)
                head_len += len(raw)
    if title is None:
        title = os.path.splitext(base)[0]
    topics = _topics_for(relpath, title, "".join(head_parts)[:HEAD_CHARS])
    return {
        "path": relpath.replace("\\", "/"),
        "title": title,
        "date": date,
        "score": best_score,
        "states": states,
        "topics": topics,
    }


def _iter_cards(watch_dir, skip_abs):
    """Recursive stream of *.md under watch_dir (hidden dirs skipped)."""
    skipped_big = 0
    for root, dirs, files in os.walk(watch_dir):
        dirs[:] = sorted(d for d in dirs if not d.startswith("."))
        for fname in sorted(files):
            if not fname.lower().endswith(".md"):
                continue
            full = os.path.join(root, fname)
            if os.path.abspath(full) in skip_abs:
                continue
            try:
                if os.path.getsize(full) > MAX_FILE_BYTES:
                    skipped_big += 1
                    continue
            except OSError:
                continue
            rel = os.path.relpath(full, os.path.dirname(watch_dir))
            yield _extract_card(full, rel), skipped_big
    yield None, skipped_big


def build(watch_dir="watch"):
    watch_dir = os.path.abspath(watch_dir)
    parent = os.path.dirname(watch_dir)
    json_path = os.path.join(watch_dir, JSON_OUT)
    md_path = os.path.join(watch_dir, MD_OUT)
    skip_abs = {os.path.abspath(json_path), os.path.abspath(md_path)}

    cards = []
    gen = _iter_cards(watch_dir, skip_abs)
    skipped_big = 0
    while True:
        card, skipped = next(gen)
        if card is None:
            skipped_big = skipped
            break
        cards.append(card)

    generated_at = datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")
    index = {
        "generated_at": generated_at,
        "dir": watch_dir.replace("\\", "/"),
        "cards_indexed": len(cards),
        "skipped_over_2mb": skipped_big,
        "cards": cards,
    }
    with open(json_path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(index, fh, indent=1, ensure_ascii=False)
        fh.write("\n")
    _write_human(md_path, index)
    return index, json_path, md_path


def _card_sort_key(c):
    return (c["date"] or "0000-00-00", c["path"])


def _fmt_card(c):
    score = ("%2d/25" % c["score"]) if c["score"] is not None else "  --  "
    date = c["date"] or "----------"
    title = c["title"]
    if len(title) > 88:
        title = title[:85] + "..."
    st = (" [" + ",".join(c["states"]) + "]") if c["states"] else ""
    return "- %s  %s  `%s` — %s%s" % (date, score, c["path"], title, st)


def _write_human(md_path, index):
    per_topic = {}
    no_topic = []
    for c in index["cards"]:
        if c["topics"]:
            for t in c["topics"]:
                per_topic.setdefault(t, []).append(c)
        else:
            no_topic.append(c)

    rows = []
    for name in sorted(per_topic, key=lambda n: (-len(per_topic[n]), n)):
        lst = sorted(per_topic[name], key=_card_sort_key, reverse=True)
        scores = [c["score"] for c in lst if c["score"] is not None]
        med = statistics.median(scores) if scores else None
        rows.append((name, len(lst), med, lst[0]["date"] or "undated", lst))

    lines = [
        "# TOPIC INDEX — the unlock (20260905)",
        "",
        "Built by `python -m mag.topic_index build` (streaming, deterministic; "
        "v4 named-bucket indexer, supersedes the v3 TF draft — bones kept: "
        "query mode, states, fulltext recall). Corpus: **%d** cards under "
        "`%s` (+%d skipped >2MB). Generated %s. Multi-label: a card may sit "
        "in several topics. Score = max `n/25` rubric hit in the card."
        % (index["cards_indexed"], index["dir"],
           index["skipped_over_2mb"], index["generated_at"]),
        "",
        "## Summary (topic | cards | median score | newest)",
        "",
        "| topic | cards | median | newest |",
        "|---|---|---|---|",
    ]
    for name, n, med, newest, _ in rows:
        lines.append("| %s | %d | %s | %s |"
                     % (name, n, ("%g" % med) if med is not None else "-", newest))
    lines.append("| (no topic) | %d | - | - |" % len(no_topic))
    lines.append("")

    for name, n, med, newest, lst in rows:
        med_s = ("%g/25" % med) if med is not None else "no scores"
        lines.append("## %s — %d cards · median %s · newest %s"
                     % (name, n, med_s, newest))
        lines.append("")
        lines.extend(_fmt_card(c) for c in lst)
        lines.append("")

    no_topic.sort(key=_card_sort_key, reverse=True)
    lines.append("## no-topic — %d cards (nothing vanishes)" % len(no_topic))
    lines.append("")
    if no_topic:
        lines.extend(_fmt_card(c) for c in no_topic)
        lines.append("")

    with open(md_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines))


def _fulltext(term, watch_dir):
    """v3 bone: body-text recall fallback for query mode."""
    out = []
    rx = re.compile(re.escape(term), re.I)
    skip_abs = set()
    for root, dirs, files in os.walk(os.path.abspath(watch_dir)):
        dirs[:] = sorted(d for d in dirs if not d.startswith("."))
        for fname in files:
            if not fname.lower().endswith(".md"):
                continue
            full = os.path.join(root, fname)
            if full in skip_abs:
                continue
            try:
                if os.path.getsize(full) > MAX_FILE_BYTES:
                    continue
                with open(full, "r", encoding="utf-8", errors="replace") as fh:
                    if rx.search(fh.read()):
                        out.append(os.path.relpath(full, os.path.dirname(
                            os.path.abspath(watch_dir))).replace("\\", "/"))
            except OSError:
                pass
    return out


def query(terms, watch_dir="watch"):
    json_path = os.path.join(os.path.abspath(watch_dir), JSON_OUT)
    if not os.path.isfile(json_path):
        build(watch_dir)
    with open(json_path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    hits = 0
    for t in terms:
        t = t.lower()
        shown = False
        for name in (t, t.rstrip("s")):
            rows = [c for c in data["cards"] if name in c["topics"]]
            if rows:
                print("%s: %d cards (bucket)" % (name, len(rows)))
                for c in sorted(rows, key=_card_sort_key, reverse=True)[:12]:
                    st = ",".join(c["states"]) or "-"
                    sc = ("%d/25" % c["score"]) if c["score"] is not None else "-"
                    print("  %s %6s %-24s %s"
                          % (c["date"] or "----", sc, st, c["path"]))
                hits += 1
                shown = True
                break
        ft = _fulltext(t, watch_dir)
        if ft:
            print("%s: %d files mention it in the BODY%s"
                  % (t, len(ft), "" if shown else " (bucket: no hits)"))
            for f in ft[:12]:
                print("  " + f)
            hits += 1
        elif not shown:
            print("%s: no hits" % t)
    return hits


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="mag.topic_index",
        description="Topic index over watch/ cards (G5-1 unlock)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    bp = sub.add_parser("build", help="build the topic index")
    bp.add_argument("--dir", default="watch",
                    help="dir to index (default: watch)")
    qp = sub.add_parser("query", help="query the index (bucket + fulltext)")
    qp.add_argument("terms", nargs="+")
    qp.add_argument("--dir", default="watch")
    args = ap.parse_args(argv)

    if args.cmd == "build":
        idx, json_path, md_path = build(args.dir)
        per_topic = Counter()
        no_topic = 0
        for c in idx["cards"]:
            if c["topics"]:
                per_topic.update(c["topics"])
            else:
                no_topic += 1
        print("cards indexed: %d (skipped >2MB: %d)"
              % (idx["cards_indexed"], idx["skipped_over_2mb"]))
        print("topics: %d, no-topic cards: %d" % (len(per_topic), no_topic))
        for name, n in sorted(per_topic.items(), key=lambda kv: (-kv[1], kv[0])):
            print("  %-18s %d" % (name, n))
        print("wrote: " + json_path)
        print("wrote: " + md_path)
        return 0
    if args.cmd == "query":
        return 0 if query(args.terms, args.dir) else 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
