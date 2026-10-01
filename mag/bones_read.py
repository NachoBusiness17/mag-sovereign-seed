"""bones_read — the operator's reading mechanic, encoded as a self-check.

Operator (2026-08-23): "honest to god the way i read is a line at a time. I read the first and
last letter of each word in a sentence and then the whole sentence comes forth."

That is not a dyslexia workaround — it is the deep mechanic: read the load-bearing ENDS (the
frame) and let the middle resolve against them. When the ends don't agree with the frame, the
whole sentence is wrong regardless of how good the middle sounds. This is the correction habit
that caught the `I am AOS` swap: the frame said "Bones", the middle claimed "AOS", so the
sentence should have been flagged before it landed.

bones_read applies that reading to OUTBOUND claims: extract each sentence's load-bearing ends
(named actors, first/last content words) and check them against the standing frame (who is
speaking, who is being addressed, the committed anchors). A mismatch between the ends and the
frame flags the whole sentence.

Schema: bones_read.v1
CLI: python -m mag.bones_read check "<text>" --speaker bone
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "bones_read.v1"

# The standing actors. speaker must never self-claim one of these.
PARTNERS = ("AOS", "Adventure", "AdventureNLearn")
SPEAKERS = ("bone", "bones", "ghost")

# Self-attribution traps: a speaker's own pronoun binding itself to a partner.
# e.g. "I am AOS", "I am Adventure", "my human is your human" style conflation.
_SELF_CLAIM = re.compile(
    r"\b(?:i am|i'm|i\s+am\s+the)\s+(aos|adventure|adventurenlearn)\b",
    re.IGNORECASE,
)
# "my <owner-noun>" must be the speaker's own, never the partner's house.
_OWNER_SMUDGE = re.compile(
    r"\b(my|our)\s+(human|operator|swarm|seat|house|bones)\b",
    re.IGNORECASE,
)


def _ends(text: str) -> list[str]:
    """Extract the load-bearing ends of each sentence: first + last content word."""
    out = []
    for sent in re.split(r"[.!?]\s+", text):
        words = [w for w in re.findall(r"[A-Za-z']+", sent) if w.lower() not in
                 {"the", "a", "an", "and", "or", "of", "to", "in", "is", "are", "i", "you"}]
        if len(words) >= 2:
            out.append((words[0], words[-1]))
    return out


def _strip_frame(words: list[str], speaker: str) -> list[str]:
    """Drop the speaker's own name + the noise words so 'ends' are the meaningful frame."""
    sk = {speaker.lower(), "bone", "bones", "ghost"}
    return [w for w in words if w.lower() not in sk]


def check(text: str, *, speaker: str = "bone") -> dict[str, Any]:
    """Read the load-bearing ends of `text` and flag any incoherence with the frame.

    Returns findings: each is a real catch (end-vs-frame mismatch), never a style nit.
    """
    findings: list[dict[str, Any]] = []

    # 1. Self-attribution trap: speaker claims to BE a partner.
    for m in _SELF_CLAIM.finditer(text):
        claimed = m.group(1)
        if claimed.lower() in {p.lower() for p in PARTNERS}:
            findings.append({
                "kind": "identity-swap",
                "severity": "high",
                "detail": f"'{speaker}' self-claims '{claimed}' — the frame is {speaker}, "
                          f"the middle says {claimed}. Whole sentence suspect.",
                "span": text[max(0, m.start() - 20):m.end() + 20],
            })

    # 2. Owner smudge: 'my/our human|operator|swarm' — whose house is it?
    #    The operator's mechanic: check the OWNER noun's ENDS against the frame.
    for m in _OWNER_SMUDGE.finditer(text):
        poss, noun = m.group(1).lower(), m.group(2).lower()
        # 'our <X>' from a single speaker collapses two houses -> smudge.
        if poss == "our":
            findings.append({
                "kind": "owner-smudge",
                "severity": "medium",
                "detail": f"'our {noun}' collapses the speaker's house and the partner's — "
                          f"the boundary says they are separate.",
                "span": text[max(0, m.start() - 20):m.end() + 20],
            })

    # 3. Ends-vs-frame: the sentence's load-bearing ends must cohere. If the FIRST and LAST
    #    content words name two different houses as if one, that's the swap the reader catches.
    for first, last in _ends(text):
        first_l, last_l = first.lower(), last.lower()
        houses = {w.lower() for w in PARTNERS + SPEAKERS}
        if first_l in houses and last_l in houses and first_l != last_l:
            # first names one house, last names another, and neither is the speaker's own — the
            # reader's frame says the ends must agree; flag it as a possible swap.
            if first_l not in {speaker.lower(), "bone", "bones", "ghost"} and \
               last_l not in {speaker.lower(), "bone", "bones", "ghost"}:
                findings.append({
                    "kind": "ends-disagree",
                    "severity": "low",
                    "detail": f"first end '{first}' and last end '{last}' name different houses "
                              f"— the frame expects them to cohere.",
                    "span": f"{first} ... {last}",
                })

    return {"schema": SCHEMA, "ok": not findings, "findings": findings,
            "ends": _ends(text)}


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="bones-read")
    ap.add_argument("cmd", choices=["check"])
    ap.add_argument("text", nargs="*", help="text to read by its bones")
    ap.add_argument("--speaker", default="bone", help="who is speaking (default bone)")
    a = ap.parse_args(argv)
    if a.cmd == "check":
        out = check(" ".join(a.text) or "(empty)", speaker=a.speaker)
    else:
        out = {"schema": SCHEMA, "ok": True}
    print(__import__("json").dumps(out, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
