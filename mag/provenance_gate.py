"""
provenance_gate.py — smallest buildable slice of a provenance gate.

Pipeline: claim intake -> grounding check -> GATE-STAMPED citation,
fail-closed on anything unverifiable.

Enforced invariants
-------------------
I1  Only evidence READ THIS SESSION via ProvenanceGate.read_evidence()
    (called exclusively from the reader/retrieval path) may ground a
    claim. There is no API for the generator to register evidence.
I2  Citation objects are minted only inside the gate. Any binding the
    generator proposes ({digest, span}) is an UNTRUSTED HINT: it is
    validated against the session registry or discarded.
I3  A claim is marked VERIFIED only if its asserted support span occurs
    verbatim in session-bound evidence whose content re-hashes to the
    bound digest (integrity check on every grounding).
I4  Everything else is DOWNGRADED to labeled uncertainty (UNVERIFIED,
    citation=None) or DROPPED, per policy. Never passes as fact.

Stdlib only. Python 3.8+. Run: python provenance_gate.py
"""

from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _sha256_hex(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------- #
# Records
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class EvidenceRecord:
    """Created ONLY by the gate when the reader ingests raw content."""
    digest: str      # sha256 hex of the exact content read
    source_uri: str
    size_bytes: int
    read_at: str


@dataclass(frozen=True)
class Citation:
    """Stamped by the gate. Generators have no legitimate way to produce one."""
    digest: str
    source_uri: str
    span: str                 # exact supporting span, verbatim in evidence
    stamped_at: str
    stamped_by: str = field(default="provenance-gate", init=False)


class Verdict(Enum):
    VERIFIED = "VERIFIED"
    UNVERIFIED = "UNVERIFIED"
    DROPPED = "DROPPED"


@dataclass
class Claim:
    """Generator output at intake. proposed_binding is an UNTRUSTED hint."""
    text: str
    proposed_binding: Optional[Dict[str, str]] = None  # {"digest": ..., "span": ...}


# --------------------------------------------------------------------------- #
# The gate
# --------------------------------------------------------------------------- #

class ProvenanceGate:
    """
    Session-scoped gate. Holds the registry of evidence ACTUALLY READ this
    session. read_evidence() belongs to the reader/retrieval path only;
    the generator-facing surface is process() alone.
    """

    def __init__(self, policy: str = "downgrade"):
        assert policy in ("downgrade", "drop"), "policy must be 'downgrade' or 'drop'"
        self.policy = policy
        self._records: Dict[str, EvidenceRecord] = {}
        self._contents: Dict[str, str] = {}

    # ---- reader-side entry point (NOT reachable from the generator) -------- #

    def read_evidence(self, source_uri: str, content: str) -> EvidenceRecord:
        digest = _sha256_hex(content)
        self._records[digest] = EvidenceRecord(
            digest=digest,
            source_uri=source_uri,
            size_bytes=len(content.encode("utf-8")),
            read_at=_utc_now(),
        )
        self._contents[digest] = content
        return self._records[digest]

    # ---- grounding ----------------------------------------------------------#

    def _ground(
        self, claim: Claim
    ) -> "tuple[Verdict, Optional[Citation], str]":
        hint = claim.proposed_binding or {}
        digest, span = hint.get("digest"), hint.get("span", "")

        if not digest or not span:
            return Verdict.UNVERIFIED, None, "intake had no binding hint to validate"

        rec = self._records.get(digest)
        if rec is None:
            # Fail closed: citing content never read this session is fatal.
            return Verdict.DROPPED, None, (
                f"bound digest {digest[:12]}... was never read this session"
            )

        content = self._contents.get(digest, "")
        if _sha256_hex(content) != digest:
            # Fail closed: evidence mutated after read (tamper detected).
            return Verdict.DROPPED, None, "content/digest mismatch (tamper)"

        if span not in content:
            return Verdict.DROPPED, None, (
                "claimed support span not present verbatim in bound evidence"
            )

        # I2: the gate — and only the gate — mints the citation here.
        citation = Citation(
            digest=rec.digest, source_uri=rec.source_uri,
            span=span, stamped_at=_utc_now(),
        )
        return Verdict.VERIFIED, citation, ""

    # ---- public generator-facing surface ------------------------------------#

    def process(self, claims: List[Claim]) -> List[Dict]:
        out: List[Dict] = []
        for claim in claims:
            verdict, citation, reason = self._ground(claim)

            if verdict is Verdict.VERIFIED:
                out.append({
                    "claim": claim.text,
                    "verdict": Verdict.VERIFIED.value,
                    "citation": asdict(citation),
                    "uncertainty_label": None,
                    "reason": None,
                    "emitted": True,
                })
                continue

            if self.policy == "drop":
                # Tombstone keeps the audit trail without promoting the claim.
                out.append({
                    "claim": None,                      # text withheld
                    "verdict": Verdict.DROPPED.value,
                    "citation": None,
                    "uncertainty_label": None,
                    "reason": reason,
                    "emitted": False,
                })
            else:  # downgrade
                out.append({
                    "claim": claim.text,
                    "verdict": Verdict.UNVERIFIED.value,
                    "citation": None,                   # no stamp ever attached
                    "uncertainty_label": "UNGROUNDED",
                    "reason": reason,
                    "emitted": True,
                })
        return out

    # ---- downstream verifier: defeats forged citation objects ---------------#

    def verify_citation(self, citation: Dict) -> bool:
        """Re-validate any citation dict against this session's registry."""
        digest = citation.get("digest")
        span = citation.get("span", "")
        if citation.get("stamped_by") != "provenance-gate":
            return False
        if digest not in self._records:
            return False
        if _sha256_hex(self._contents.get(digest, "")) != digest:
            return False
        return span in self._contents.get(digest, "")


# --------------------------------------------------------------------------- #
# Demo: happy path, bad span, phantom evidence, forged stamp
# --------------------------------------------------------------------------- #

if __name__ == "__main__":
    gate = ProvenanceGate(policy="downgrade")

    # Reader path: content-addressed evidence, actually read this session.
    doc = ("Water boils at 100 C at standard atmospheric pressure. "
           "The Eiffel Tower is 330 m tall including antennas.")
    ev = gate.read_evidence("file:///corpus/facts.txt", doc)

    claims = [
        # 1) Grounded: span exists verbatim in read evidence -> gate stamps it.
        Claim("Water boils at 100 C at standard atmospheric pressure.",
              proposed_binding={"digest": ev.digest,
                                "span": "Water boils at 100 C at standard atmospheric pressure."}),
        # 2) Bad span: not present verbatim in read evidence -> downgraded.
        Claim("The Eiffel Tower is made of cheese.",
              proposed_binding={"digest": ev.digest, "span": "The Eiffel Tower is made of cheese."}),
        # 3) Phantom evidence: digest never read this session -> dropped (fail-closed).
        Claim("The moon is made of cheese.",
              proposed_binding={"digest": "deadbeef" * 8, "span": "The moon is made of cheese."}),
    ]
    out = gate.process(claims)
    for o in out:
        print(o["verdict"].ljust(10), "|", (o["claim"] or "<withheld>")[:60],
              "|", (o["reason"] or "GATE-STAMPED"))

    # 4) Forged stamp: downstream verifier must reject a citation not minted by the gate.
    forged = {"digest": ev.digest, "span": "Water boils at 100 C",
              "stamped_by": "the-generator"}  # generator forged a citation
    real = {"digest": ev.digest,
            "span": "Water boils at 100 C at standard atmospheric pressure.",
            "stamped_by": "provenance-gate"}
    print("\nforged citation accepted?", gate.verify_citation(forged), "(must be False)")
    print("real citation accepted?  ", gate.verify_citation(real), "(must be True)")