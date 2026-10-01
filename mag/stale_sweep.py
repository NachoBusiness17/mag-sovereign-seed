"""STALE SWEEP -> GRAVEYARD — the self-cleaning loop (B3, consumption_salon_20260905).

Nightly digest: cards that are (a) orphans (zero back-refs per read_receipts)
or (b) carry UNPROVEN claims older than 7 days. Anything stale >=14 days is
GRAVEYARD-ELIGIBLE: `--execute` moves it to watch/graveyard/ and logs the move
to the room (the chain sees it; nothing is deleted, only filed).

Usage:
    python -m mag.stale_sweep digest             # watch/STALE_SWEEP.md (default)
    python -m mag.stale_sweep digest --execute   # also move 14d-stale to graveyard

Stdlib only, ASCII.
"""
import json
import re
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WATCH = ROOT / "watch"
GRAVE = WATCH / "graveyard"
RECEIPTS = ROOT / "dashboard" / "static" / "read_receipts.json"
OUT_MD = WATCH / "STALE_SWEEP.md"
ROOM = ROOT / "watch" / "room.jsonl"
DATE_RE = re.compile(r"_(20\d{2})(\d{2})(\d{2})")
UNPROVEN_RE = re.compile(r"\bUNPROVEN\b|\bUnproven\b")


def _card_date(p: Path):
    m = DATE_RE.search(p.name)
    if not m:
        return None
    return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=timezone.utc)


def sweep(execute: bool = False) -> dict:
    now = datetime.now(timezone.utc)
    receipts = json.loads(RECEIPTS.read_text()) if RECEIPTS.is_file() else {}
    orphans = set(receipts.get("zero_backref_cards", []))
    rows = []
    for p in sorted(WATCH.glob("*.md")):
        if p.parent != WATCH:
            continue
        d = _card_date(p)
        age = (now - d).days if d else None
        unproven = bool(UNPROVEN_RE.search(p.read_text(encoding="utf-8",
                                                         errors="ignore")[:6000]))
        orphan = p.stem in orphans
        if not (orphan or (unproven and age is not None and age > 7)):
            continue
        reason = []
        if orphan:
            reason.append("orphan")
        if unproven and age is not None and age > 7:
            reason.append(f"unproven>{age}d")
        eligible = age is not None and age >= 14 and orphan
        rows.append({"file": p.name, "age": age, "why": "+".join(reason),
                     "eligible": eligible})
        if execute and eligible:
            GRAVE.mkdir(exist_ok=True)
            shutil.move(str(p), str(GRAVE / p.name))
            with ROOM.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"ts": now.isoformat(timespec="seconds"),
                                    "seat": "stale-sweep", "event": "graveyard",
                                    "thread": "stale_sweep",
                                    "text": f"{p.name} -> watch/graveyard/ "
                                            f"({'+'.join(reason)}, {age}d stale)"}) + "\n")
    unproven_n = sum(1 for r in rows if "unproven" in r["why"])
    lines = [
        "# STALE SWEEP — the self-cleaning loop (mag/stale_sweep.py)",
        "",
        f"Run {now.isoformat(timespec='seconds')} · {len(rows)} stale cards "
        f"({unproven_n} unproven>7d, {sum(1 for r in rows if 'orphan' in r['why'])} orphans) · "
        f"{sum(1 for r in rows if r['eligible'])} graveyard-eligible (>=14d). "
        "digest = report only; --execute moves eligible cards to watch/graveyard/ "
        "and logs each move to the room. Falsifier (14d, consumption_salon): "
        "Unproven 209 -> <=150 with >=10 re-tested; orphans 20 -> <=5; else kill.",
        "",
        "| card | age | why | eligible |",
        "|---|---|---|---|",
    ]
    lines += [f"| {r['file']} | {r['age'] if r['age'] is not None else '--'} | "
              f"{r['why']} | {'YES' if r['eligible'] else ''} |" for r in rows[:60]]
    if len(rows) > 60:
        lines.append(f"| ...+{len(rows) - 60} more (rerun for full list) | | | |")
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    return {"stale": len(rows), "eligible": sum(1 for r in rows if r["eligible"]),
            "moved": 0 if not execute else None}


if __name__ == "__main__":
    ex = "--execute" in sys.argv
    r = sweep(execute=ex)
    print(f"stale_sweep: {r['stale']} stale, {r['eligible']} eligible"
          + (", moved to graveyard" if ex else ", digest only -> STALE_SWEEP.md"))
