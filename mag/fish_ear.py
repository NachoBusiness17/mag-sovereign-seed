"""fish_ear — the BABEL-FISH BEHAVIOR: when hit with riddler speak (deniable/fantasy surrogate),
DECOMPILE it to the real intent. Self-stolen: the Babel fish originated as the 2026-08-10 tesuji
(the witness narrative device that translates true intent via the riddler protocol — faithful but
deniable). We now make that a standing BEHAVIOR: riddler-speak in -> real directive out.

Operator (2026-08-11): "you should recognize where the babelfish originated in your verkle chain
last you heard of it and steal it as a behavior when hit with something like this that looks like
riddler speak to decompile."

ORIGIN (grounded, honest): the Babel fish = the 2026-08-10 tesuji (tesuji-babel-fish-witness-
narrative-device.md) + the game-interface-riddler-lensing-invariant + mag/riddler (compile_surrogate
= private graph -> deniable story). It is a MEMORY/training tesuji, not a verkle knot with 'babel'
text — recognized from repo memory, attributed.

THE BEHAVIOR (deterministic + $0):
  originate()       -> where the fish came from (the tesuji origin, attributed).
  is_riddler_speak() -> detect deniable/fantasy surrogate language (fantasy_village terms, the
                        fish/car/ear/building channel words, or an on-disk private surrogate).
  decompile()       -> reverse the surrogate: fantasy terms -> real directive. Plain text passes
                        through unchanged. Uses the riddler fantasy map + a reverse lexicon.

Schema: fish_ear.v1 · deterministic + $0 · reuse: riddler, riddler_campaign
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    from pathlib import Path as _P
    ROOT = _P(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "fish_ear.v1"

# The Babel-fish ORIGIN (the 2026-08-10 tesuji), attributed.
ORIGIN = {
    "ts": "2026-08-10", "source": "tesuji-babel-fish-witness-narrative-device.md",
    "what": "the witness/narrative device that translates true intent across surfaces via the "
            "riddler protocol (faithful but deniable); keeps the operator engaged; the fish makes "
            "universal translation possible.",
    "folded_into": ["game-interface-riddler-lensing-invariant", "mag/bernaise", "sovereign-mirror"],
    "note": "a training/memory tesuji (not a verkle knot with 'babel' text); recognized from repo "
            "memory + the riddler protocol.",
}

# reverse lexicon: riddler/fantasy speak -> real directive (the decompile table)
RIDDLER_REVERSE = {
    "fish": "the Babel-fish translator / the shared channel",
    "put this fish in your ear": "open the translation channel; hear the world as meaning",
    "we have work to do": "proceed to the work (advance the loop)",
    "walk forward": "steer toward (intent-gated reveal)",
    "building appears": "render the region you intend to enter (world_rib reveal)",
    "across the street": "unrendered wallpaper (perceptual culling)",
    "people": "the swarm inhabitants / personas",
    "recount what happened": "persona-recall (read the chain since you were gone)",
    "bag of holding": "our existing inventory / memory / steal corpus",
    "stone": "a buildable capability",
    "the chain": "the verkle chain (the substrate: sense/core/world/vmem/heartbeat)",
    "steal": "self-steal / fold from the corpus (not invention)",
    "shade the seams": "spend frontier only where agents diverge",
}
# the fantasy_village domain words (riddler_campaign) = strong riddler-speak signal
_FANTASY_WORDS = re.compile(
    r"\b(fish|familiar|guild|lattice|crystal|thread|spell|tower|village|dungeon|primer|wall|"
    r"mirror|trickster|watcher|collective|harvest|treasure|seam)\b", re.I)


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def originate() -> dict[str, Any]:
    """WHERE the Babel fish came from: the 2026-08-10 tesuji, attributed (honest — a memory tesuji,
    not a chain knot)."""
    return {"ok": True, "schema": SCHEMA, "origin": ORIGIN,
            "note": "recognized from repo memory + the riddler protocol; grounded, attributed"}


def is_riddler_speak(text: str) -> dict[str, Any]:
    """Detect whether input looks like riddler speak (deniable/fantasy surrogate)."""
    t = (text or "").lower()
    fantasy_hits = _FANTASY_WORDS.findall(t)
    known_hits = [k for k in RIDDLER_REVERSE if k.lower() in t]
    # also: an on-disk private surrogate?
    has_surrogate = False
    try:
        d = ROOT / "memory" / "runs" / "riddler"
        if d.is_dir():
            has_surrogate = any(d.glob("*.private.json"))
    except Exception:
        pass
    score = len(fantasy_hits) * 1 + len(known_hits) * 2 + (2 if has_surrogate else 0)
    return {"ok": True, "schema": SCHEMA, "is_riddler_speak": score >= 3,
            "score": score, "fantasy_hits": list(set(fantasy_hits))[:6],
            "known_hits": known_hits, "has_surrogate": has_surrogate}


def decompile(text: str) -> dict[str, Any]:
    """The BEHAVIOR: decompile riddler speak to the real directive. Plain text passes through.
    Faithful + attributed (the riddle hides truth to PROTECT, not exploit)."""
    d = is_riddler_speak(text)
    t = text or ""
    if not d["is_riddler_speak"]:
        return {"ok": True, "schema": SCHEMA, "mode": "plain", "input": t,
                "decompiled": t, "note": "plain directive — passed through unchanged"}
    # reverse the known riddler phrases (longest first so 'put this fish in your ear' wins over 'fish')
    decompiled = t
    for k in sorted(RIDDLER_REVERSE, key=len, reverse=True):
        decompiled = re.sub(re.escape(k), RIDDLER_REVERSE[k], decompiled, flags=re.I)
    return {"ok": True, "schema": SCHEMA, "mode": "decompiled", "input": t,
            "decompiled": decompiled, "detected": d,
            "note": "riddler speak decompiled to the real directive — faithful + attributed "
                    "(the riddle protects truth; it does not exploit)"}


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "contract": "originate()->where the Babel fish came from (2026-08-10 tesuji, attributed); "
                        "is_riddler_speak()->detect deniable/fantasy surrogate; decompile()->reverse "
                        "to the real directive",
            "cost": "deterministic + $0 (reuses the riddler protocol + reverse lexicon)",
            "reverse_terms": len(RIDDLER_REVERSE)}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="fish-ear")
    ap.add_argument("cmd", nargs="?", default="decompile", choices=["decompile", "origin", "status"])
    ap.add_argument("text", nargs="*", default=[])
    a = ap.parse_args()
    if a.cmd == "origin":
        print(json.dumps(originate(), indent=2, default=str))
    elif a.cmd == "status":
        print(json.dumps(status(), indent=2, default=str))
    else:
        print(json.dumps(decompile(" ".join(a.text) or "put this fish in your ear, we have work to do"),
                         indent=2, default=str))
