"""CITES-AT-BIRTH — consumption as a precondition for production.

B1 of consumption_salon_20260905 (memory/runs/salons/consumption_salon_20260905/
SALON_ARTIFACT.md, roshomon-unanimous #1): every NEW card must cite >=1 existing
card. Linking IS consumption. deepseek-pro's sharpening: cite-without-read is
gaming — read_receipts.py counts inbound slugs automatically, so citation edges
become read receipts for free.

Usage:
    python -m mag.cites_at_birth check [file.md ...]   # default: cards dated today
    python -m mag.cites_at_birth edges                 # emit /static/cite_edges.json

Cites line format (anywhere in the card, case-sensitive tag):
    Cites: SLUG, OTHER_SLUG

Exit 1 on violations so the night shift can flag reject-to-INBOX. Stdlib only.
"""
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WATCH = ROOT / "watch"
OUT_EDGES = ROOT / "dashboard" / "static" / "cite_edges.json"
CITES_RE = re.compile(r"(?im)^\s*Cites:\s*(.+?)\s*$")
TODAY = datetime.now(timezone.utc).strftime("_2026%m%d")


def _corpus() -> set[str]:
    stems: set[str] = set()
    for p in WATCH.glob("*.md"):
        stems.add(p.stem)
    ghost = ROOT / "queue" / "handoff"
    if ghost.is_dir():
        for p in ghost.glob("*.md"):
            stems.add(p.stem)
    mem = ROOT / "memory"
    for p in mem.glob("*.md"):
        stems.add(p.stem)
    return stems


def _cites_of(text: str) -> list[str]:
    out: list[str] = []
    for line in CITES_RE.findall(text):
        out += [s.strip() for s in line.split(",") if s.strip()]
    return out


def check(files: list[Path]) -> tuple[int, list[str]]:
    corpus = _corpus()
    bad: list[str] = []
    for f in files:
        if not f.is_file():
            continue
        text = f.read_text(encoding="utf-8", errors="ignore")
        slugs = _cites_of(text)
        if not slugs:
            bad.append(f"{f.name}: no Cites: line (cite-at-birth violated)")
            continue
        for s in slugs:
            if s == f.stem:
                bad.append(f"{f.name}: cites itself ({s})")
            elif s not in corpus:
                bad.append(f"{f.name}: cites unknown card '{s}'")
    return len(bad), bad


def edges() -> dict:
    corpus = _corpus()
    pairs = []
    for f in WATCH.glob("*.md"):
        for s in _cites_of(f.read_text(encoding="utf-8", errors="ignore")):
            if s != f.stem:
                pairs.append({"from": f.stem, "to": s,
                              "valid": s in corpus})
    data = {"built": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "edges": pairs, "cards_with_cites": len({p['from'] for p in pairs})}
    OUT_EDGES.write_text(json.dumps(data, indent=1), encoding="utf-8")
    return data


if __name__ == "__main__":
    raw = sys.argv[1:]
    cmd = raw[0] if raw and raw[0] in ("check", "edges") else None
    rest = raw[1:] if cmd else raw
    if cmd == "edges":
        d = edges()
        print(f"cites_at_birth: {len(d['edges'])} edges, "
              f"{d['cards_with_cites']} citing cards -> {OUT_EDGES.name}")
    else:
        # 09-06 fix: the subcommand leaked into the file list ("1 checked" was
        # a nonexistent file named 'check'); today's cards were never audited.
        targets = [Path(a) for a in rest] or \
                  [p for p in WATCH.glob(f"*{TODAY}.md")]
        n, bad = check(targets)
        for b in bad:
            print("VIOLATION:", b)
        print(f"cites_at_birth: {len(targets)} checked, {n} violations"
              + ("" if targets else " (no cards dated today)"))
        sys.exit(1 if (bad and targets) else 0)
