"""mag/integrity_kernel — the AOS tri-state integrity kernel, vendored (2026-08-25).

PROVENANCE: this file is a verbatim vendored copy of the reviewed toolkit that ships in
`embassy-aos/mag/embassy_integrity.py` (the 22-passing-test suite AOS reviewed under
Pattern A), itself kept self-contained in `embassy-sandbox/sandbox/integrity.py`. It is
stdlib-only, deterministic, network-free, and secret-free. Vendored here (self-steal,
operator 2026-08-25: "we need this sharp edge in everything") so EVERY mag fold —
work_register, queue_gate, any body's result — can run its claims through the SAME
kernel the partner already audited, instead of each module re-inventing a weaker version.

It provides:
    * tri-state claims (Supported / Unproven / Disputed + Evidence / Inference / Assumption)
    * verkle witness (tamper-evident provenance = evidence, not authority)
    * false-success guard (anti "Self-Report-Instead-Of-Run")
    * OPSEC gates G1-G8 (the AOS non-negotiable stop conditions)
    * symmetric scrutiny (ARK Gate 6 analog)
    * first-runtime inbox E2E with promote: false

THE SHARP EDGE: a claim can only be Supported on Evidence; Disputed requires the
contradicting evidence; everything else is Unproven (not claimed). Nothing is auto-truthed.
"""
from __future__ import annotations

import hashlib
import re
import time
from dataclasses import dataclass, field
from typing import Iterable, Optional

# ---------------------------------------------------------------------
# 1. TRI-STATE CLAIMS - the AOS integrity kernel
#    (Supported / Unproven / Disputed + Evidence / Inference / Assumption)
# ---------------------------------------------------------------------

CLAIM_STATUS = ("Supported", "Unproven", "Disputed")
BASIS_KINDS = ("Evidence", "Inference", "Assumption")


@dataclass(frozen=True)
class Claim:
    """A single integrity-kernel claim.

    A Supported claim must rest on at least one piece of *Evidence*. A claim
    whose basis is only Inference/Assumption cannot be Supported. This mirrors
    ARK Article II (Evidence Supremacy) and the AOS tri-state claims.
    """

    statement: str
    status: str = "Unproven"
    basis: tuple[str, ...] = ("Assumption",)
    evidence: tuple[str, ...] = ()

    def validate(self) -> tuple[bool, str]:
        if self.status not in CLAIM_STATUS:
            return False, f"invalid status: {self.status}"
        for b in self.basis:
            if b not in BASIS_KINDS:
                return False, f"invalid basis kind: {b}"
        if self.status == "Supported" and not any(b == "Evidence" for b in self.basis):
            return False, "Supported requires at least one Evidence basis"
        if self.status == "Supported" and not self.evidence:
            return False, "Supported requires attached evidence"
        if self.status == "Disputed" and not self.evidence:
            return False, "Disputed requires the contradicting evidence"
        return True, "ok"


def integrity_kernel(claims: Iterable[Claim]) -> dict:
    """Run every claim through the integrity kernel; nothing is auto-truthed."""
    passed = []
    failed = []
    for c in claims:
        ok, why = c.validate()
        (passed if ok else failed).append({"statement": c.statement, "why": why})
    return {
        "passed": len(passed),
        "failed": len(failed),
        "auto_truth": False,  # software never auto-truthes
        "human_final_call": True,  # the kernel is not the authority
        "details": passed + failed,
    }


def tri_state(statement: str, status: str = "Unproven",
              basis: tuple[str, ...] = ("Assumption",),
              evidence: tuple[str, ...] = ()) -> dict:
    """Convenience: build a claim dict the way mag modules fold results.
    NEVER over-claims: a bad status/basis degrades to Unproven/Assumption
    (the same fail-safe the queue gate uses). Returns the kernel-validated dict.
    """
    c = Claim(statement, status, tuple(basis), tuple(evidence))
    ok, why = c.validate()
    if not ok:
        # degrade: never let an invalid claim carry a Supported/Disputed status
        c = Claim(statement, "Unproven", ("Assumption",), ())
    return {
        "statement": c.statement,
        "status": c.status,
        "basis": list(c.basis),
        "evidence": list(c.evidence),
        "valid": True,
    }


# ---------------------------------------------------------------------
# 2. VERKLE WITNESS - tamper-evident provenance (evidence, not authority)
# ---------------------------------------------------------------------

def _sha256(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


@dataclass
class VerkleWitness:
    """Append-only, content-addressed chain of events.

    Each node links to the previous via hash. Changing any node breaks the
    chain link, so tampering is provable. This is a *local cryptographic
    witness*: it proves what happened, it does not claim jurisdiction over
    what should be believed (that stays with the human + integrity kernel).
    """

    chain: list = field(default_factory=list)

    def append(self, event: str, ts: Optional[str] = None) -> dict:
        ts = ts or f"{int(time.time()*1000)}"
        prev = self.chain[-1]["node_hash"] if self.chain else "genesis"
        payload = f"{len(self.chain)}|{ts}|{event}"
        payload_hash = _sha256(payload)
        node_hash = _sha256(f"{prev}|{payload_hash}")
        node = {
            "index": len(self.chain),
            "ts": ts,
            "event": event,
            "payload_hash": payload_hash,
            "prev_hash": prev,
            "node_hash": node_hash,
        }
        self.chain.append(node)
        return node

    def verify(self) -> bool:
        for i, node in enumerate(self.chain):
            expected_prev = self.chain[i - 1]["node_hash"] if i > 0 else "genesis"
            if node["prev_hash"] != expected_prev:
                return False
            payload = f"{node['index']}|{node['ts']}|{node['event']}"
            if _sha256(payload) != node["payload_hash"]:
                return False
            if _sha256(f"{node['prev_hash']}|{node['payload_hash']}") != node["node_hash"]:
                return False
        return True


# ---------------------------------------------------------------------
# 3. FALSE-SUCCESS GUARD - anti "Self-Report-Instead-Of-Run"
# ---------------------------------------------------------------------

@dataclass
class Executor:
    effects: list = field(default_factory=list)

    def run(self, effect: str) -> str:
        """Actually perform the effect (append to a real log) and return it."""
        self.effects.append(effect)
        return effect

    def claim_only(self, effect: str) -> str:
        """Claim the effect happened WITHOUT performing it (the failure mode)."""
        return effect


def verify_execution(executor: Executor, effect: str) -> bool:
    """True iff the effect actually landed in the executor's log."""
    return effect in executor.effects


# ---------------------------------------------------------------------
# 4. OPSEC GATES G1-G8 - the AOS non-negotiable stop conditions
# ---------------------------------------------------------------------

_MUNI = re.compile(r"\b(Springfield|Riverton|Lakewood|Millbrook)\b", re.I)
_PII = re.compile(
    r"\b(?:[\w.+-]+@[\w-]+\.[a-z]{2,}|\d{3}[-.)]\d{3}[-.]\d{4})\b", re.I
)
_SECRET = re.compile(r"\b(api[_-]?key|bearer|token|secret|password|oauth)\b", re.I)
_G5_DUMP = re.compile(r"\b(raw.?vault|case.?dump|densif|unscrubbed)\b", re.I)
_G6_TRUTH = re.compile(r"\b(this is legally true|medical fact|definitely proves)\b", re.I)
_G7_HOST = re.compile(r"\b(?:rm -rf /|kill \d{1,5}|format c:|del /f)", re.I)
_G8_SHIP = re.compile(r"\b(git push|npm publish|deploy to prod)\b", re.I)
_SKILL_CHROME = re.compile(
    r"\b(nacho(?:quixotic| business)?|strike the chord)\b|"
    r"built by (?:nacho|the operator)|personal (?:brand|skill) of",
    re.I,
)

GATES: dict = {
    "G1": (_MUNI, "municipality / hometown names as product samples"),
    "G2": (_PII, "real PII (emails, phones, ids)"),
    "G3": (_SECRET, "secrets, tokens, cookies, .env, OAuth material"),
    "G4": (_SKILL_CHROME, "operator skill brands as product chrome"),
    "G5": (_G5_DUMP, "unscrubbed vault / case / densify dumps"),
    "G6": (_G6_TRUTH, "automated truth / legal-medical advice claims"),
    "G7": (_G7_HOST, "free-roam host FS or kill reserved services"),
    "G8": (_G8_SHIP, "ship to public git/live without OPSEC + human"),
}


def scan_opspec(text: str) -> dict:
    """Scan a piece of output against G1-G8. Returns per-gate pass/fail."""
    result = {}
    for gate, (pattern, desc) in GATES.items():
        hits = list(pattern.findall(text))
        result[gate] = {
            "pass": not hits,
            "hits": [h[0] if isinstance(h, tuple) else h for h in hits],
            "desc": desc,
        }
    return result


def opspec_clear(text: str) -> bool:
    """True only if every gate passes (zero OPSEC violations)."""
    return all(g["pass"] for g in scan_opspec(text).values())


# ---------------------------------------------------------------------
# 5. SYMMETRY AUDIT - ARK Gate 6 analog (symmetric scrutiny)
# ---------------------------------------------------------------------

@dataclass(frozen=True)
class Scrutiny:
    actor: str
    sources: int
    hours: float


SYMMETRY_SOURCE_DELTA = 2.0  # >2.0x source delta triggers
SYMMETRY_HOUR_DELTA = 0.40  # >40% analysis-hour delta triggers


def symmetry_audit(a: Scrutiny, b: Scrutiny, justification: str = "") -> dict:
    """Compare scrutiny depth across two comparable actors (ARK Gate 6)."""
    source_ratio = max(a.sources, b.sources) / max(1, min(a.sources, b.sources))
    hours_delta = abs(a.hours - b.hours) / max(1, max(a.hours, b.hours))
    asymmetric = (source_ratio > SYMMETRY_SOURCE_DELTA) or (
        hours_delta > SYMMETRY_HOUR_DELTA
    )
    justified = bool(justification)
    return {
        "actors": (a.actor, b.actor),
        "source_ratio": round(source_ratio, 2),
        "hours_delta": round(hours_delta, 2),
        "asymmetric": asymmetric,
        "justified": justified,
        "flag": "Asymmetric Scrutiny" if (asymmetric and not justified) else "ok",
        "justification_logged": justification,
    }


# ---------------------------------------------------------------------
# 6. FIRST-RUNTIME INBOX E2E - binding sequence step 5 (promote: false)
# ---------------------------------------------------------------------

@dataclass
class Inbox:
    tasks: list = field(default_factory=list)

    def enqueue(self, task: dict) -> None:
        self.tasks.append(task)


@dataclass
class Outbox:
    results: list = field(default_factory=list)


def run_inbox_e2e(inbox: Inbox, outbox: Outbox, promote: bool = False) -> dict:
    """Process every inbox task; write results to outbox.

    When promote=False, results are *delivered but never promoted* - they
    cannot ship to any public/partner surface. This is the first-runtime
    contract from the AOS binding sequence (step 5).
    """
    report = {"processed": 0, "promoted": 0, "blocked": []}
    for task in inbox.tasks:
        result = {
            "task_id": task.get("id"),
            "status": "done",
            "payload": task.get("payload"),
        }
        outbox.results.append(result)
        report["processed"] += 1
        if promote and task.get("allow_promote"):
            report["promoted"] += 1
        else:
            report["blocked"].append(task.get("id"))
    report["promoted_ok"] = report["promoted"] == 0
    return report
