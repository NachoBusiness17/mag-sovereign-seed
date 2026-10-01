"""gwap_to_gps -- fail-closed bridge: gwap session ledgers feed the gps capability ledger.

Mickey17 Wave 1 (game-platform basecamp, 2026-09-29). The wave ledger return 3
(watch/inbox/MICKEY17_WAVE_LEDGER_20260929.md) named three schema disagreements
between mag/gwap_payload.py (the GWAP agreement mint) and tools/gps_mcp/ledger.py
(the router's capability truth); this adapter is the one metabolism that closes
them:

  verdicts, 4-valued vs binary -- VERIFIED_AGREE feeds verdict=1 (pass),
      DISPUTE feeds verdict=0 (fail); CHALLENGE and BLOCKED are SKIPS: counted
      in the feed report, never sent to record_verdict, so a judge-owed or
      tabooed round can neither inflate nor deflate a pass_rate. The gps side
      stays binary by design; the nuance lives here, in the report.
  evidence hash, receipt_sha256 vs row_sha256 -- the evidence is row_sha256.
      meter_credit.receipt_sha256 is a build-time receipt over the payload body;
      it does not identify a ledger position (identical payloads in two sessions
      share it, and a signature already commits to it). row_sha256 binds
      seq + ts_utc + payload + prev_sha256, so an auditor holding the evidence
      hash can re-walk the chain (gwap_payload.verify_chain_file) and point at
      the exact row that earned the verdict.
  key mapping, (model_id, task_shape) vs scene/participants, uninvented --
      THE INVENTION, documented: task_shape is a caller argument defaulting to
      "gwap-agreement-v1" (one shape per verdict source; the default names this
      module's semantics). model_id resolves by explicit precedence, refusing
      at every miss:
        1. scene_to_model {scene_id: model_id} -- scene granularity wins; the
           scene is the unit the payload itself is keyed by.
        2. participant_to_model {anon_id: model_id}, consulted for the intent
           author (the robber): the robber's intent is the work product under
           verification, cop and witness are the instruments, so the robber is
           the model under test when mapping by participant.
      There is NO identity fallback (scene_id as model_id, first participant,
      ...) on purpose: a guessed routing key quietly seeds some OTHER model's
      capability row with this verdict, and routing dollars follow it. A miss
      raises UNMAPPED_* / NO_KEY_MAP before any db write.

FAIL-CLOSED LAWS: verify_chain_file runs over the WHOLE file before anything
is fed (a broken chain leaves the gps ledger untouched, no partial feed of a
tampered history); the feed itself is two-pass -- every row is validated and
key-mapped into a plan BEFORE the first record_verdict call, so any refusal
(broken chain, missing file, foreign schema, unknown verdict, unmapped key)
leaves the gps ledger untouched; rows are read from the file bytes after
verification, never from cache.

Run (demo):  python -m mag.gwap_to_gps
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mag.gwap_payload import (
    BLOCKED,
    CHALLENGE,
    DISPUTE,
    VERDICTS,
    VERIFIED_AGREE,
    SCHEMA,
    anon_id,
    build_payload,
    verify_chain_file,
)
from tools.gps_mcp.ledger import CapabilityLedger

DEFAULT_TASK_SHAPE = "gwap-agreement-v1"

SKIP_VERDICTS = (CHALLENGE, BLOCKED)
VERDICT_TO_BIN: dict[str, int] = {VERIFIED_AGREE: 1, DISPUTE: 0}

_ZERO_HASH = "0" * 64


class GwapToGpsError(Exception):
    """Reason-coded refusal (house pattern: .reason carries the machine code)."""

    def __init__(self, reason: str, message: str = "") -> None:
        self.reason = reason
        super().__init__(message or reason)


def _require(condition: bool, reason: str, message: str) -> None:
    if not condition:
        raise GwapToGpsError(reason, message)


def _read_verified_rows(path: Path) -> list[dict[str, Any]]:
    """Fail-closed file walk: verify the whole chain first, then parse bytes."""
    _require(path.is_file(), "MISSING_SESSION", f"session ledger not found: {path}")
    ok, bad = verify_chain_file(path)
    _require(
        ok,
        "BROKEN_CHAIN",
        f"{path.name} fails verification at row {bad}; refusing to feed",
    )
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _model_id_for(
    payload: dict[str, Any],
    scene_to_model: dict[str, str] | None,
    participant_to_model: dict[str, str] | None,
) -> str:
    """Resolve the gps model_id for one payload. See module docstring for the
    documented precedence; every miss refuses rather than guesses."""
    if scene_to_model is not None:
        scene_id = payload.get("scene_id")
        _require(
            isinstance(scene_id, str) and scene_id in scene_to_model,
            "UNMAPPED_SCENE",
            f"scene_id {scene_id!r} missing from scene_to_model",
        )
        return scene_to_model[scene_id]
    if participant_to_model is not None:
        author = (payload.get("intent_struct") or {}).get("author")
        _require(
            isinstance(author, str) and author in participant_to_model,
            "UNMAPPED_PARTICIPANT",
            f"intent author {author!r} missing from participant_to_model",
        )
        return participant_to_model[author]
    raise GwapToGpsError(
        "NO_KEY_MAP",
        "supply scene_to_model or participant_to_model; model_id is never guessed",
    )


def feed_session(
    session_path: Path | str,
    gps: CapabilityLedger | Path | str,
    *,
    task_shape: str = DEFAULT_TASK_SHAPE,
    scene_to_model: dict[str, str] | None = None,
    participant_to_model: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Walk one gwap session ledger file and feed the gps capability ledger.

    Every VERIFIED_AGREE row becomes one record_verdict(verdict=1), every
    DISPUTE row one record_verdict(verdict=0), both with evidence_hash =
    the row's row_sha256. CHALLENGE and BLOCKED rows are counted in the
    returned report and never scored. Returns the report dict:

        rows_seen fed skipped by_verdict chain_tip task_shape
        evidence_hashes model_ids

    The report is the skips' only home: gps is binary by design, so the
    4-valued nuance is reported here instead of being squeezed into a
    pass/fail it does not fit.
    """
    _require(
        isinstance(task_shape, str) and bool(task_shape.strip()),
        "BAD_TASK_SHAPE",
        "task_shape must be a non-empty string",
    )
    path = Path(session_path)
    owns_ledger = not isinstance(gps, CapabilityLedger)
    ledger = gps if isinstance(gps, CapabilityLedger) else CapabilityLedger(gps)
    rows = _read_verified_rows(path)

    report: dict[str, Any] = {
        "session_path": str(path),
        "task_shape": task_shape,
        "rows_seen": len(rows),
        "fed": 0,
        "skipped": 0,
        "by_verdict": {v: 0 for v in VERDICTS},
        "chain_tip": rows[-1]["row_sha256"] if rows else _ZERO_HASH,
        "evidence_hashes": [],
        "model_ids": set(),
    }

    # Pass 1: validate and key-map EVERY row into a plan before the first db
    # write, so a refusal on row N cannot leave rows 1..N-1 already scored.
    # The chain law gives tampered files this atomicity for free; the plan
    # extends it to schema, verdict, and key-map refusals.
    plan: list[tuple[str, int, str]] = []  # (model_id, 1|0, row_sha256)
    for row in rows:
        payload = row.get("payload")
        _require(
            isinstance(payload, dict) and payload.get("schema") == SCHEMA,
            "BAD_PAYLOAD",
            f"row {row.get('seq')} does not carry a {SCHEMA} payload",
        )
        verdict = payload.get("verdict")
        _require(
            verdict in VERDICTS,
            "UNKNOWN_VERDICT",
            f"row {row.get('seq')} verdict {verdict!r} is not one of {VERDICTS}",
        )
        report["by_verdict"][verdict] += 1
        if verdict in SKIP_VERDICTS:
            report["skipped"] += 1
            continue
        model_id = _model_id_for(payload, scene_to_model, participant_to_model)
        plan.append((model_id, VERDICT_TO_BIN[verdict], row["row_sha256"]))

    # Pass 2: execute the plan; nothing below can refuse anymore.
    try:
        for model_id, bin_verdict, row_sha in plan:
            ledger.record_verdict(
                model_id=model_id,
                task_shape=task_shape,
                verdict=bool(bin_verdict),
                evidence_hash=row_sha,
            )
            report["fed"] += 1
            report["evidence_hashes"].append(row_sha)
            report["model_ids"].add(model_id)
    finally:
        if owns_ledger:
            ledger.close()
    report["model_ids"] = sorted(report["model_ids"])
    return report


# -- demo ---------------------------------------------------------------------------


def _demo() -> None:
    import tempfile

    robber = anon_id("gwap-to-gps-robber-20260929")
    cop = anon_id("gwap-to-gps-cop-20260929")
    parts = [
        {"anon_id": robber, "role": "robber"},
        {"anon_id": cop, "role": "cop"},
    ]
    tape = {"sha256": "0" * 64, "engine_version": "gwap-to-gps-demo"}
    ts = "2026-09-29T12:00:00Z"
    kw = dict(participants=parts, consent=True, created_utc=ts, replay_tape_ref=tape)
    agree = build_payload(
        scene_id="scene-demo-agree",
        intent_struct={"author": robber, "claims": [
            {"subject": "a", "verb": "did", "object": "x"},
            {"subject": "b", "verb": "did", "object": "y"},
        ]},
        report_struct={"author": cop, "claims": [
            {"subject": "b", "verb": "did", "object": "y"},
            {"subject": "a", "verb": "did", "object": "x"},
        ]},
        **kw,
    )
    dispute = build_payload(
        scene_id="scene-demo-dispute",
        intent_struct={"author": robber, "claims": [
            {"subject": "a", "verb": "did", "object": "x"},
        ]},
        report_struct={"author": cop, "claims": [
            {"subject": "z", "verb": "saw", "object": "nothing"},
        ]},
        **kw,
    )

    with tempfile.TemporaryDirectory() as tmp:
        from mag.gwap_payload import SessionLedger

        session = SessionLedger("gwap-to-gps-demo-20260929", store=Path(tmp))
        session.append(agree, ts_utc=ts)
        session.append(dispute, ts_utc=ts)
        report = feed_session(
            session.path,
            Path(tmp) / "gps-demo.db",
            participant_to_model={robber: "demo-model"},
        )
        print("feed report:", json.dumps(report, indent=2, sort_keys=True))
        check = CapabilityLedger(Path(tmp) / "gps-demo.db")
        try:
            row = check.report_capability("demo-model", DEFAULT_TASK_SHAPE)
        finally:
            check.close()
        print("capability row:", row)


if __name__ == "__main__":
    _demo()
