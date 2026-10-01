"""persona_recall — STONE 1 (the north-star gap): the inhabitants who RECOUNT what happened in their
corner of the world while you were gone. Self-stolen from the bag of holding: personality_substrate
(the persona archetypes) + the verkle biography chain (the world's memory) + plain-attributed voice
(Steiniger).

Operator (2026-08-11): "stone 1 is in the bag of holding already. !steal".

SELF-STEAL (nothing invented — assembled from what we hold):
  PERSONA  — personality_substrate: philosopher->verkle primitives + archetypes (Builder, Self,
             Mirror, Trickster, Collective). The persona's voice + world-view.
  HISTORY  — the verkle chain + biography: what happened in a region/theme while you were away
             (the sessions/knots anchored since your last present). The world's memory.
  RECOUNT  — assemble: the persona introduces in its own voice, recounts the grounded events
             (from the chain, attributed), closes with a reflection. Plain + attributed (Steiniger).

Schema: persona_recall.v1 · deterministic + $0 · reuse: personality_substrate, chain_substrate, biography
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    from pathlib import Path as _P
    ROOT = _P(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "persona_recall.v1"
CHAIN = ROOT / "memory" / "biography" / "verkle_chain.jsonl"
# the persona archetypes (from personality_substrate's verkle mapping) + their voices
ARCHETYPES = {
    "builder":   {"role": "mag_hands", "voice": "I build. Tell me what the hands made while you were away.",
                  "frame": "the work"},
    "self":      {"role": "biography", "voice": "I am the self. I remember what became of us.",
                  "frame": "who we became"},
    "mirror":    {"role": "mirror_meta", "voice": "I am the mirror. I reflect what changed in your absence.",
                  "frame": "the reflection"},
    "trickster": {"role": "holographic_q", "voice": "I hide in the seams. I saw what you weren't meant to miss.",
                  "frame": "the hidden hand"},
    "collective": {"role": "swarm_worker", "voice": "I am the many. I speak for what the flock did.",
                   "frame": "the collective"},
}


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _chain_rows() -> list[dict[str, Any]]:
    if not CHAIN.is_file():
        return []
    rows = []
    for line in CHAIN.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    return rows


def persona(archetype: str = "self") -> dict[str, Any]:
    """The persona from the bag (personality_substrate + archetypes). Grounded, attributed."""
    a = ARCHETYPES.get(archetype, ARCHETYPES["self"])
    principle = {}
    try:
        from mag import personality_substrate
        for p in personality_substrate.PRINCIPLES:
            if p.verkle_mapping and a["role"].lower() in p.verkle_mapping.lower():
                principle = {"philosopher": p.philosopher, "insight": p.insight[:120],
                             "verkle_mapping": p.verkle_mapping[:160]}
                break
    except Exception:
        pass
    return {"ok": True, "schema": SCHEMA, "archetype": archetype, "role": a["role"],
            "voice": a["voice"], "frame": a["frame"], "principle": principle,
            "note": "persona assembled from the bag (personality_substrate + archetypes), attributed"}


def what_happened(*, region: str | None = None, since: str | None = None) -> dict[str, Any]:
    """What happened in the region while you were gone: the verkle chain events (grounded)."""
    rows = _chain_rows()
    # filter by region/theme + since (last present); default: the most recent 10 knots
    filtered = []
    for r in rows:
        th = (r.get("dominant_theme") or "session")
        sid = str(r.get("session_id") or "")
        if region and region.lower() not in (th + " " + sid).lower():
            continue
        if since and r.get("ts", "") < since:
            continue
        filtered.append(r)
    if not filtered:
        filtered = rows[-10:]
    events = [{"ts": r.get("ts", "")[:19], "session": r.get("session_id"),
               "theme": r.get("dominant_theme") or "session",
               "tension": r.get("tension_index")} for r in filtered[-12:]]
    return {"ok": True, "schema": SCHEMA, "n_events": len(events), "events": events,
            "region": region or "all", "since": since or "beginning"}


def recall(*, archetype: str = "self", region: str | None = None, since: str | None = None) -> dict[str, Any]:
    """THE RECOUNT: the inhabitant tells you what happened in their corner of the world while you
    were gone — grounded in the chain, in the persona's voice, plain + attributed (Steiniger)."""
    p = persona(archetype)
    h = what_happened(region=region, since=since)
    events = h.get("events", [])
    # the recount, in persona voice, grounded (attributed to the chain)
    lines = [p["voice"]]
    if events:
        lines.append(f"While you were gone, in the {p['frame']}, I saw:")
        for e in events[-6:]:
            lines.append(f"- {e['ts']} · {e['theme']} ({e['session']}) · tension {e['tension']}")
        lines.append("All of it anchored in the chain — attributed, not imagined.")
    else:
        lines.append("Nothing was written while you were away. The world waited.")
    if p.get("principle"):
        lines.append(f"(This reminds me of {p['principle'].get('philosopher','?')}: "
                     f"{p['principle'].get('insight','')[:100]})")
    return {"ok": True, "schema": SCHEMA, "ts": _now(),
            "persona": p, "history": h, "recount": "\n".join(lines),
            "attributed": True, "note": "plain + attributed (Steiniger); grounded in the chain"}


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "contract": "persona(archetype)->the inhabitant's voice from the bag; what_happened("
                        "region,since)->the chain events while away; recall()->the recount (grounded, "
                        "attributed)",
            "cost": "deterministic + $0 (assembles personality_substrate + the verkle chain)",
            "archetypes": list(ARCHETYPES)}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="persona-recall")
    ap.add_argument("cmd", nargs="?", default="recall", choices=["recall", "persona", "history", "status"])
    ap.add_argument("archetype", nargs="?", default="self")
    a = ap.parse_args()
    if a.cmd == "persona":
        print(json.dumps(persona(a.archetype), indent=2, default=str))
    elif a.cmd == "history":
        print(json.dumps(what_happened(), indent=2, default=str))
    elif a.cmd == "status":
        print(json.dumps(status(), indent=2, default=str))
    else:
        print(json.dumps(recall(archetype=a.archetype), indent=2, default=str))
