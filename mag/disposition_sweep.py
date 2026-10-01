"""disposition_sweep — close the four-verb orphan count honestly.

W1 finding (ORPHAN_LEDGER_20260906 ITEM 2): hundreds of watch/ cards carry no
disposition row, so the four-verb count inflates. This sweep classifies every
undisposed card deterministically and MERGES rows into watch/DISPOSITIONS.json
(read-modify-write, never replaces — the invariants-registry shrink lesson).

Classes (the verb + why):
  SUBSTRATE   — receipts/ledgers/census/audits: the card IS the record, exempt by class
  TRANSDUCE   — salons/briefs/folds: content flowed into laws, organs, boards
  KEEP-OPEN   — charters/standing programs/boards: living instruments, not orphans
  DISPOSE     — drafts/stubs/tmp: dead drafts, retired
  OPEN-WIRE   — build card whose named artifact is missing: the real remaining work
  WIRED       — build card whose named artifact exists on disk

Every auto row is suffixed "(auto-classified.v1)" so a human pass can audit the
classifier itself. Existing rows are never touched.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WATCH = ROOT / "watch"
DISPO = WATCH / "DISPOSITIONS.json"
MARK = " (auto-classified.v1)"

SUBSTRATE = re.compile(r"RECEIPT|LEDGER|HAUL|DIGEST|AUDIT|CENSUS|DAY_CLOSE|DAY_LEDGER|HEALTH|SNAPSHOT|MANIFEST|RUN_LOG|RELAUNCH|PROOF_OF_LIFE|BASELINE|REGISTRY_2026|ATLAS\.md$", re.I)
TRANSDUCE = re.compile(r"SALON|FOLD|DOSSIER|BRIEF|PACK|PANEL|SOCRATIC|DIALECTIC|SELF_STEAL|STEAL_|_STEAL|ARCHIVE_|PARABLE|TRIAGE|INTAKE_|ANSWER", re.I)
KEEP = re.compile(r"CHARTER|STANDING|PROGRAM|BOARD|ROADMAP|RUNBOOK|CONSTITUTION|COVENANT|DOCTRINE", re.I)
DEAD = re.compile(r"DRAFT|STUB|_TMP|TMP_|_OLD|DELETE|WIP\b", re.I)
ARTIFACT = re.compile(r"([A-Za-z0-9_]+\.(?:html|py|js))|/static/([A-Za-z0-9_./-]+)")


def classify(path: Path) -> str:
    name = path.name
    try:
        body = path.read_text(encoding="utf-8", errors="ignore")[:12000]
    except OSError:
        return "SUBSTRATE - unreadable, treated as record" + MARK
    if SUBSTRATE.search(name):
        return "SUBSTRATE - receipt/ledger class, is the record" + MARK
    if DEAD.search(name):
        return "DISPOSE - draft/stub class" + MARK
    if KEEP.search(name):
        return "KEEP-OPEN - charter/standing class, living instrument" + MARK
    if TRANSDUCE.search(name):
        return "TRANSDUCE - salon/brief class, folded into laws+organs" + MARK
    m = ARTIFACT.findall(body)
    targets = [a or b for a, b in m if (a or b)]
    for t in targets[:5]:
        cand = ROOT / t if not t.startswith("static") else ROOT / "dashboard" / t
        cand2 = ROOT / "dashboard" / "static" / Path(t).name
        if cand.is_file() or cand2.is_file():
            return f"WIRED - artifact {Path(t).name} exists on disk" + MARK
        return f"OPEN-WIRE - names {Path(t).name}, artifact not found on disk" + MARK
    return "TRANSDUCE - analysis card, folded into the room" + MARK


def main() -> int:
    data = json.loads(DISPO.read_text(encoding="utf-8")) if DISPO.is_file() else {
        "schema": "dispositions.v1", "updated": "", "cards": {}
    }
    cards = data.setdefault("cards", {})
    window = sorted(WATCH.glob("*202609*.md"))
    added = {"SUBSTRATE": 0, "TRANSDUCE": 0, "KEEP-OPEN": 0, "DISPOSE": 0, "OPEN-WIRE": 0, "WIRED": 0}
    for p in window:
        if p.name in cards:
            continue
        verdict = classify(p)
        cards[p.name] = verdict
        for k in added:
            if verdict.startswith(k):
                added[k] += 1
                break
    data["updated"] = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    data["last_sweep"] = "mag/disposition_sweep.py auto-classified.v1"
    DISPO.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"cards in Sep window: {len(window)} | total dispositioned: {len(cards)}")
    print(json.dumps(added, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
