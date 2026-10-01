"""epistemic_guard — the NEW SYSTEM: a deterministic guard against manufactured consent / puppeteering.

Operator (2026-08-13): "i don't want to be puppeted an neither does anyone else. Yet our desires get
in the way. this is an old fight. can we make a better new system and leave the old one."

The OLD system = manufactured consent: structure that shapes belief through unexamined desires, no
informed control. The NEW system = the one that can't be puppeted because it MECHANICALLY forces
evidence. This guard adapts the strongest anti-manipulation mechanisms (DEEP STEAL from agentswarm):
  * BASE-RATE PRIOR FIRST   — commit what reference classes imply BEFORE weighing the narrative
    ('news volume measures attention, not probability').
  * MECHANICAL EVIDENCE GATE — reject a claim with no prior, no reference class, no numbers.
  * INVERTED FRAMING        — argue the opposite; if the claim can't survive the flip, it's fragile.
  * RED-TEAM                — name the direction each flaw biases (narrative seduction > base rate).
These make consent INFORMED, not manufactured. Deterministic + $0, pure stdlib — a filter, not a
judge; it flags structure, it never fabricates.

Schema: epistemic_guard.v1 · deterministic + $0 · pure stdlib
"""
from __future__ import annotations

import json
import re
import sys
from typing import Any

try:
    from config import ROOT
except Exception:
    from pathlib import Path as _P
    ROOT = _P(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCHEMA = "epistemic_guard.v1"

# markers of a BASE-RATE / reference-class anchor (the prior)
_BASE_RATE_MARKERS = [
    "base rate", "reference class", "in comparable", "historically", "x in n", "out of n",
    "frequency", "how often", "prior", "counted", "p(prior)", "similar cases",
]
# markers of NUMBERS / quantified evidence
_NUMBER_RE = re.compile(r"\b\d+(?:\.\d+)?\s*(?:%|percent|million|billion|thousand|out of|in)\b")
# markers of NARRATIVE SEDUCTION (a vivid story, not evidence)
_NARRATIVE_MARKERS = [
    "devil", "evil", "secret", "hidden", "they", "them", "elite", "cult", "conspiracy",
    "they did", "they control", "dark", "shadow", "plot", "harvest", "abduct", "ritual",
]
# markers that it INVOKES EVIDENCE / sources / verifiability
_EVIDENCE_MARKERS = [
    "evidence", "source", "document", "verify", "data", "study", "report", "citation",
    "primary", "counted", "measure", "reproducib",
]


def _has(probes: list[str], low: str) -> list[str]:
    return [p for p in probes if p in low]


def prior_first(text: str) -> dict[str, Any]:
    """BASE-RATE PRIOR FIRST: does the claim anchor on a reference class / base rate BEFORE the
    narrative? 'News volume measures attention, not probability.' Deterministic + $0."""
    low = (text or "").lower()
    base_hits = _has(_BASE_RATE_MARKERS, low)
    num_hits = _NUMBER_RE.findall(low)
    anchored = bool(base_hits) or bool(num_hits)
    return {"ok": True, "schema": SCHEMA, "tool": "prior_first",
            "anchored": anchored, "base_rate_hits": base_hits, "numbers": num_hits,
            "verdict": "anchored on a base rate / numbers" if anchored
                       else "NO base rate / numbers — floating on narrative"}


def evidence_gate(text: str) -> dict[str, Any]:
    """MECHANICAL EVIDENCE GATE (steal): reject a claim with no prior, no reference class, no numbers.
    This is the filter that makes consent informed, not manufactured. Deterministic + $0."""
    low = (text or "").lower()
    prior = bool(_has(_BASE_RATE_MARKERS, low))
    numbers = bool(_NUMBER_RE.findall(low))
    evidence = bool(_has(_EVIDENCE_MARKERS, low))
    pass_gate = prior or (numbers and evidence)
    return {"ok": True, "schema": SCHEMA, "tool": "evidence_gate",
            "prior": prior, "numbers": numbers, "evidence_words": evidence,
            "pass": pass_gate,
            "verdict": "PASS — grounded (prior/numbers/evidence present)" if pass_gate
                       else "FAIL — ungrounded; would be rejected + retried with feedback"}


def inverted_framing(text: str) -> dict[str, Any]:
    """INVERTED-FRAMING coherence probe (steal): argue the opposite. A claim that survives the flip is
    robust; one that collapses under inversion is narrative. Deterministic proxy: does the claim state
    a falsifiable direction a NO-case could refute, or only assert a one-sided story?"""
    low = (text or "").lower()
    has_no_case = any(w in low for w in ["could be wrong", "counter", "against", "however",
                                         "alternative", "opposite", "no case", "evidence against",
                                         "both sides", "uncertain", "not necessarily"])
    has_numbers = bool(_NUMBER_RE.findall(low))
    falsifiable = has_numbers or has_no_case
    return {"ok": True, "schema": SCHEMA, "tool": "inverted_framing",
            "has_no_case": has_no_case, "has_numbers": has_numbers,
            "falsifiable": falsifiable,
            "verdict": "survives inversion (falsifiable / has a no-case)" if falsifiable
                       else "fragile under inversion — one-sided assertion"}


def red_team(text: str) -> dict[str, Any]:
    """RED-TEAM (steal): attack the rationale; name the direction each flaw biases. Mechanical: flag
    narrative-seduction markers and missing evidence, and which way the bias leans. Deterministic."""
    low = (text or "").lower()
    narrative = _has(_NARRATIVE_MARKERS, low)
    base = bool(_has(_BASE_RATE_MARKERS, low))
    evidence = bool(_has(_EVIDENCE_MARKERS, low))
    flaws = []
    if narrative and not base:
        flaws.append("narrative seduction: a vivid story beating a boring base rate — biases toward belief")
    if not evidence:
        flaws.append("no evidence/sources invoked — unverifiable")
    if not base:
        flaws.append("base-rate neglect: no reference class")
    return {"ok": True, "schema": SCHEMA, "tool": "red_team",
            "narrative_markers": narrative, "flaws": flaws, "n_flaws": len(flaws),
            "verdict": "clean (evidence + base rate present)" if not flaws
                       else "flawed — " + "; ".join(flaws)}


def consent_check(text: str) -> dict[str, Any]:
    """THE NEW SYSTEM: is this informed truth or manufactured consent? Combines the guards into one
    verdict. Manufactured consent = narrative, no base rate, no evidence, no falsifiability.
    Informed truth = anchored, gated, falsifiable. Deterministic + $0. HONEST — a mechanical filter
    that flags structure; it does not fabricate a judgment."""
    p = prior_first(text)["anchored"]
    g = evidence_gate(text)["pass"]
    f = inverted_framing(text)["falsifiable"]
    r = red_team(text)["n_flaws"]
    score = sum([p, g, f])  # 0..3 truth-signals
    manufactured = score <= 1 or r >= 2
    return {"ok": True, "schema": SCHEMA, "tool": "consent_check",
            "truth_signals": {"prior": p, "evidence_gate": g, "falsifiable": f},
            "red_team_flaws": r, "score": score,
            "kind": "manufactured-consent" if manufactured else "informed-truth",
            "verdict": ("MANUFACTURED CONSENT — narrative with no verifiable ground; the old system"
                        if manufactured else
                        "INFORMED TRUTH — anchored, gated, falsifiable; the new system"),
            "note": "the new system: mechanically filter manufactured consent, keep the verifiable"}


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="epistemic-guard")
    ap.add_argument("cmd", nargs="?", default="consent",
                    choices=["prior", "gate", "invert", "redteam", "consent"])
    ap.add_argument("args", nargs="*", default=[])
    a = ap.parse_args(argv)
    text = " ".join(a.args) or "a claim"
    fn = {"prior": prior_first, "gate": evidence_gate, "invert": inverted_framing,
          "redteam": red_team, "consent": consent_check}[a.cmd]
    print(json.dumps(fn(text), ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
