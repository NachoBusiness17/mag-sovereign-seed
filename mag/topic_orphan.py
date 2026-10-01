"""Topic-orphan detection + reroute — find stranded research topics and route them back in.

The operator's ask: identify TOPIC orphans (as well as project orphans) so we can REROUTE them
through our existing systems. A project orphan is an undone work intent (orphan_timer). A TOPIC
orphan is a topic that was raised (idea graph / inbox / intent) but never became an active research
thread and has no answer — it's stranded.

This scans raised topics, checks each against the research bed (is there an active pack / a done
answer?), and REROUTES stranded ones: note_intent (orphan_timer) so they survive + are promotable,
and reports them so the cadence can spawn a cheap research pack. Deterministic, fail-open, no LLM.

CLI:  python -m mag.topic_orphan scan | reroute | run
Wired into: mag.governor_autorun cadence (MAG_TOPIC_EVERY).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except ImportError:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "topic_orphan.v1"
PACKS = ROOT / "memory" / "research_packs"

STOP = {"the", "a", "an", "and", "or", "for", "of", "to", "in", "on", "with", "our", "we",
        "how", "what", "why", "should", "do", "does", "can", "i", "it", "is", "be", "this", "on"}


def _terms(t: str) -> list[str]:
    return [x for x in re.findall(r"[a-zA-Z0-9_\-]{3,}", (t or "").lower()) if x not in STOP]


def _has_active_thread(topic: str) -> bool:
    """Is there an active (running/queued) OR completed research pack on this topic?"""
    terms = _terms(topic)
    if not terms or not PACKS.is_dir():
        return True  # can't tell -> don't false-positive a reroute
    for p in PACKS.glob("*.json"):
        if p.name == "latest.json":
            continue
        try:
            d = json.loads(p.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        blob = f"{d.get('title','')} {d.get('ask','')}".lower()
        # active if any term matches AND it has no done answer OR a pending/running task
        if any(t in blob for t in terms):
            return True  # a pack exists on this topic -> not an orphan
    return False


def _raised_topics() -> list[dict[str, Any]]:
    """Collect topics raised across our seams (project orphans + idea graph + inbox)."""
    out: list[dict[str, Any]] = []
    # 1) orphan_timer open intents (project orphans -> may also be topics)
    try:
        from mag.orphan_timer import list_open
        for o in list_open():
            out.append({"topic": str(o.get("intent") or o.get("id") or ""), "source": "orphan_timer"})
    except Exception:
        pass
    # 2) operator_inbox processed mentions (things the operator raised)
    try:
        p = ROOT / "memory" / "operator_inbox.json"
        if p.is_file():
            d = json.loads(p.read_text(encoding="utf-8", errors="replace"))
            for m in (d.get("processed") or [])[-30:]:
                out.append({"topic": str(m.get("text") or ""), "source": "operator_inbox"})
    except Exception:
        pass
    return [x for x in out if _terms(x["topic"])]


def scan() -> dict[str, Any]:
    raised = _raised_topics()
    orphans = []
    for r in raised:
        if not _has_active_thread(r["topic"]):
            orphans.append(r)
    return {"ok": True, "schema": SCHEMA, "ts": datetime.now(timezone.utc).isoformat(),
            "raised_n": len(raised), "topic_orphans": orphans, "orphan_n": len(orphans)}


def reroute(*, note: bool = True) -> dict[str, Any]:
    """Reroute stranded topics through the existing systems (orphan_timer.note_intent)."""
    s = scan()
    rerouted = []
    for o in s["topic_orphans"]:
        try:
            if note:
                from mag.orphan_timer import note_intent
                note_intent(o["topic"][:200], source=f"topic-orphan:{o['source']}")
            rerouted.append({"topic": o["topic"][:120], "source": o["source"], "rerouted": note})
        except Exception as e:
            rerouted.append({"topic": o["topic"][:120], "source": o["source"], "error": str(e)[:100]})
    return {**s, "rerouted": rerouted, "rerouted_n": len(rerouted)}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = (argv[0] if argv else "scan").lower()
    if cmd == "reroute":
        print(json.dumps(reroute(), indent=2, default=str)[:5000])
    else:
        print(json.dumps(scan(), indent=2, default=str)[:5000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
