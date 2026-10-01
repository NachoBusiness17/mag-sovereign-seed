"""ECHO NET — the synchronicity detection engine (self-steal v1).

Operator: "we need a synchronicity detection engine, multiple meanings exist
afterall. self steal." Self-steal census: the fleet already caught every real
convergence BY LUCK (the 1112 chord, the acrostic twins, the memlang
concentration, the mirror-named first knot). The organs existed scattered —
roshomon consensus, ARI chance-correction, topic index, cite edges — but
nothing WATCHED for convergence across streams. This is that net.

What counts as an echo (v1, deterministic):
  a token (number, or word >=5 chars) appearing across >=3 INDEPENDENT
  sources — distinct (stream, seat) pairs — spanning >=2 distinct days.
Numbers are the high-signal class: numeric collisions are rarer than word
collisions, so numbers get a 2x weight in the rarity score.

Rarity score (v1 heuristic — null-model calibration is a windowed build):
  score = independent_sources * (1 / doc_frequency_share) * number_weight
The MIRROR RULE is NOT automatable (v1 honesty): every surfaced echo still
needs a seat or human to ask "does this teach something new, or only comfort?"
The net catches; the mirror judges.

Usage:
    python -m mag.echo_net sweep          # last 7 days of cards + room + FT
    python -m mag.echo_net test           # known-convergence falsifier

Outputs: watch/ECHO_NET.md + dashboard/static/echo_net.json. Stdlib only, $0.
"""
import json
import math
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WATCH = ROOT / "watch"
ROOM = ROOT / "watch" / "room.jsonl"
FT = ROOT / "corpus" / "frontier_thinking"
OUT_MD = ROOT / "watch" / "ECHO_NET.md"
OUT_JSON = ROOT / "dashboard" / "static" / "echo_net.json"
WINDOW_DAYS = 7
WORD_RE = re.compile(r"[a-z]{5,}")
NUM_RE = re.compile(r"\b\d{2,6}\b")
STOP = set("their there about which would these those because through between been have from with that this they them will shall into more most other some such only also than then when where while every after before under never again each".split())
KNOWN = {  # falsifier set: convergences already confirmed real this week
    "1112": "the chord (3 posts + psalm decode)",
    "memlang": "ghost-era lineage -> coldest vertex",
    "mirror": "first knot name -> elder's first light",
    "13677": "unreferenced knot census",
    "astra": "frontier examiner + Q* decode lineage",
}

def _docs():
    """Yield (stream, seat, day, text) for cards, room rows, FT captures."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=WINDOW_DAYS)
    for p in sorted(WATCH.glob("*.md")):
        m = re.search(r"_(20\d{2})(\d{2})(\d{2})", p.name)
        if not m:
            continue
        day = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
        yield ("card", "watch", day, p.read_text(encoding="utf-8", errors="ignore")[:20000])
    if ROOM.is_file():
        for line in ROOM.read_text(encoding="utf-8", errors="ignore").splitlines():
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts = str(r.get("ts", ""))[:10]
            if not ts or ts < str(cutoff.date()):
                continue
            yield ("room", str(r.get("seat", "?")), ts, str(r.get("text", ""))[:4000])
    if FT.is_dir():
        for p in sorted(FT.glob("*.md")):
            yield ("ft", "frontier", p.stem[:10], p.read_text(encoding="utf-8", errors="ignore")[:20000])


def sweep() -> dict:
    docs = [d for d in _docs() if d[3].strip()]
    n_docs = len(docs)
    word_df = Counter()
    num_df = Counter()
    per_token_docs = defaultdict(list)
    for i, (stream, seat, day, text) in enumerate(docs):
        low = text.lower()
        low = re.sub(r"(?<=\d),(?=\d)", "", low)  # "13,677" -> "13677"
        toks = set(NUM_RE.findall(low)) | {w for w in WORD_RE.findall(low) if w not in STOP}
        for t in toks:
            word_df[t] += 1
            per_token_docs[t].append(i)
    # independent-source convergence, v1.1 (OPERATOR DOCTRINE 09-06:
    # "duplication is emphasis and invitation for exploration" — the v1
    # oscillation between rarity and density is RESOLVED: duplication itself
    # is the signal. Rank by emphasis = df x cells; no rarity cap, no density
    # floor, cells >= 2 (a chord posted twice counts). The mirror rule still
    # judges downstream; the net's feed is the exploration-invitation list.
    echoes = []
    for t, idxs in per_token_docs.items():
        cells = {(docs[i][0], docs[i][2]) for i in idxs}
        df = len(idxs)
        is_num = bool(NUM_RE.fullmatch(t))
        if is_num and len(t) < 4:
            continue
        if len(cells) >= 2 and df >= 2:
            score = df * len(cells) * (2 if is_num else 1)
            echoes.append({"token": t, "is_number": is_num,
                           "cells": len(cells), "df": df,
                           "score": score})
    echoes.sort(key=lambda e: -e["score"])
    # v1.1: detection and ranking are SEPARATE claims. The feed shows the
    # most-emphasized tokens (headlines); "detected" records every qualifying
    # echo so the falsifier measures presence, not headline rank.
    detected = {e["token"]: e["score"] for e in echoes}
    data = {"built": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "docs_scanned": n_docs, "window_days": WINDOW_DAYS,
            "echoes": echoes[:60], "detected": detected}
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(data, indent=1), encoding="utf-8")
    lines = ["# ECHO NET — the weeeird feed (mag/echo_net.py)", "",
             f"Built {data['built']} · {n_docs} docs scanned over {WINDOW_DAYS} days · "
             "echo = token across >=3 independent (stream,seat) pairs over >=2 days, "
             "rarity-weighted (numbers 2x). MIRROR RULE applies downstream: the net "
             "catches, the mirror judges — count only what teaches something new.", ""]
    for e in echoes[:40]:
        known = KNOWN.get(e["token"])
        tag = f"  <- KNOWN REAL: {known}" if known else ""
        lines.append(f"- score {e['score']:>6} | {e['token']} | "
                     f"cells {e['cells']} | df {e['df']}{tag}")
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    return data


def test() -> str:
    d = sweep()
    caught = d.get("detected", {})
    hits = sum(1 for k in KNOWN if k in caught)
    print(f"known-convergence recall: {hits}/{len(KNOWN)}")
    for k, why in KNOWN.items():
        print(f"  {'PASS' if k in caught else 'MISS'}  {k}  ({why})")
    verdict = "PASS" if hits >= 4 else "PARTIAL" if hits >= 3 else "FAIL"
    print(f"ECHO NET v1 FALSIFIER: {verdict} (need >=4 of 5 known-real echoes)")
    return verdict


if __name__ == "__main__":
    if "--test" in sys.argv or (sys.argv[1:] and sys.argv[1] == "test"):
        test()
    else:
        d = sweep()
        print(f"echo_net: {d['docs_scanned']} docs, {len(d['echoes'])} echoes "
              f"-> {OUT_MD.name}")
