"""doctrine_statute — deepseek's 90-day rule, made organ (2026-09-08).

STATUTE: a doctrine card that no other file references for N days is demoted to
historical context — it stops binding the seats until a human or a witnessed
post promotes it back. Right-sized for a fleet that is weeks old: the default
horizon is 90 days (deepseek's proposal, salon-audit 20260908), but `report`
runs at ANY age so the tripwire is visible long before it can fire.

This organ NEVER deletes or moves anything. It reads, counts, and names.
Demotion lists land in state/statute/ for a human (or the audit) to act on.

LAW CITATION: files not processes; read-only sweep; no scheduled runs — you
call it, it reports, it exits.

CLI:
  python -m mag.doctrine_statute report [--days 90] [--shelf watch]
  python -m mag.doctrine_statute demote [--days 90]   # writes the demotion list file
"""
from __future__ import annotations

import argparse
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "state" / "statute"
SCAN_SUFFIX = (".py", ".md", ".html", ".js", ".yaml", ".yml", ".json", ".css", ".txt")
MAX_SCAN_BYTES = 512 * 1024


def _cards(shelf: str) -> list[Path]:
    base = ROOT / shelf
    if not base.is_dir():
        return []
    return sorted(p for p in base.rglob("*.md") if p.is_file())


def _reference_corpus(shelves: list[str]) -> tuple[str, set[str]]:
    """All text content EXCEPT the cards under judgment + those files' own names."""
    chunks: list[str] = []
    card_paths: set[str] = set()
    for shelf in shelves:
        for p in (ROOT / shelf).rglob("*") if (ROOT / shelf).is_dir() else []:
            if not p.is_file() or p.stat().st_size > MAX_SCAN_BYTES:
                continue
            rel = p.relative_to(ROOT).as_posix()
            if p.suffix == ".md" and shelf == "watch":
                card_paths.add(rel)  # cards don't count as their own witnesses...
                continue
            if p.suffix in SCAN_SUFFIX:
                try:
                    chunks.append(p.read_text(encoding="utf-8", errors="replace"))
                except Exception:  # noqa: BLE001
                    pass
    # ...but they DO count as referenced when another card names them, so scan
    # card text too — minus each card's own self-mention handled per-card below.
    for rel in card_paths:
        try:
            chunks.append((ROOT / rel).read_text(encoding="utf-8", errors="replace"))
        except Exception:  # noqa: BLE001
            pass
    return "\n".join(chunks), card_paths


def statute(shelves: list[str], days: int, write: bool) -> dict:
    now = time.time()
    mega, card_paths = _reference_corpus(shelves)
    orphans, live = [], []
    for shelf in shelves:
        for p in _cards(shelf):
            rel = p.relative_to(ROOT).as_posix()
            if rel in ("watch/inbox/SALON_AUDIT_FOLD_20260908.md",):
                continue
            age_days = (now - p.stat().st_mtime) / 86400
            base = p.name
            text = p.read_text(encoding="utf-8", errors="replace")
            # referenced = named by some OTHER file (self-mentions don't count)
            others = mega.replace(text, "", 1) if text in mega else mega
            refs = base in others or rel in others
            row = {"path": rel, "age_days": round(age_days, 1), "referenced": refs}
            (orphans if not refs else live).append(row)
    due = [o for o in orphans if o["age_days"] >= days]
    report = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "horizon_days": days,
        "shelves": shelves,
        "cards_scanned": len(orphans) + len(live),
        "referenced": len(live),
        "unreferenced": len(orphans),
        "demotion_due": len(due),
        "oldest_unreferenced_days": max((o["age_days"] for o in orphans), default=0),
        "demotion_list": sorted(due, key=lambda o: -o["age_days"]),
    }
    if write:
        OUT.mkdir(parents=True, exist_ok=True)
        f = OUT / f"demotion_list_{datetime.now(timezone.utc):%Y%m%d}.json"
        f.write_text(json.dumps(report, indent=1), encoding="utf-8")
        report["written"] = str(f.relative_to(ROOT))
    return report


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["report", "demote"])
    ap.add_argument("--days", type=int, default=90)
    ap.add_argument("--shelf", action="append", default=None,
                    help="repeatable; default: watch + watch/inbox")
    a = ap.parse_args()
    shelves = a.shelf or ["watch"]
    rep = statute(shelves, a.days, write=(a.cmd == "demote"))
    print(f"STATUTE horizon={rep['horizon_days']}d | cards={rep['cards_scanned']} "
          f"| referenced={rep['referenced']} | unreferenced={rep['unreferenced']} "
          f"| demotion_due={rep['demotion_due']} "
          f"| oldest_unreferenced={rep['oldest_unreferenced_days']}d")
    if rep["demotion_due"]:
        for row in rep["demotion_list"][:20]:
            print(f"  DEMOTE {row['path']} ({row['age_days']}d unreferenced)")
    if rep.get("written"):
        print("written:", rep["written"])


if __name__ == "__main__":
    main()
