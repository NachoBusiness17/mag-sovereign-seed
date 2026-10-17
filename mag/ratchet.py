"""ratchet.py ? DFHack-inspired enablement dials & delete-when-X retirement receipts.

Implements queue/todo.md line 254 (DF/DFHack fix taxonomy fold):
  1. Four formal enablement dials per registered debt/fix:
     - ALWAYS_ON   ("always-on"): structural safety law; cannot be toggled off.
     - DEFAULT_ON  ("default-on"): active by default; opt-out via env/config.
     - OPT_IN      ("opt-in"): inert by default; opt-in via env/config.
     - MANUAL_ONLY ("manual-only"): operator CLI only; refuses daemon/unattended runs.
  2. Every registered ratchet entry MUST declare a non-empty `delete_when` condition
     (Law 8: falsifier / retirement condition at birth, or registration is refused).
  3. `retire_debt()` verifies that the retirement evidence exists on disk, hashes its
     bytes (Law 2), and appends an immutable retirement receipt to
     `state/ratchet_retirements.jsonl`.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
RETIREMENTS_LEDGER = ROOT / "state" / "ratchet_retirements.jsonl"

VALID_DIALS = ("always-on", "default-on", "opt-in", "manual-only")


@dataclass(frozen=True)
class RatchetSpec:
    debt_id: str
    dial: str
    delete_when: str
    owner_organ: str
    summary: str


def _env_key(prefix: str, debt_id: str) -> str:
    clean = "".join(ch if ch.isalnum() else "_" for ch in debt_id.upper()).strip("_")
    return f"{prefix}_{clean}"


class RatchetRegistry:
    def __init__(self, ledger_path: Optional[Path] = None) -> None:
        self._specs: Dict[str, RatchetSpec] = {}
        self.ledger_path = Path(ledger_path) if ledger_path else RETIREMENTS_LEDGER

    def register(self, spec: RatchetSpec) -> RatchetSpec:
        if spec.dial not in VALID_DIALS:
            raise ValueError(f"invalid dial {spec.dial!r}; expected one of {VALID_DIALS}")
        if not spec.delete_when or not spec.delete_when.strip():
            raise ValueError(f"debt {spec.debt_id!r} missing delete_when retirement condition (Law 8)")
        self._specs[spec.debt_id] = spec
        return spec

    def get(self, debt_id: str) -> RatchetSpec:
        if debt_id not in self._specs:
            raise KeyError(f"unregistered ratchet debt: {debt_id!r}")
        return self._specs[debt_id]

    def is_enabled(
        self,
        debt_id: str,
        *,
        overrides: Optional[Dict[str, bool]] = None,
        unattended: bool = False,
    ) -> bool:
        spec = self.get(debt_id)
        if spec.dial == "always-on":
            return True
        if spec.dial == "manual-only":
            if unattended:
                return False
            if overrides and debt_id in overrides:
                return bool(overrides[debt_id])
            return os.environ.get(_env_key("MAG_RATCHET_MANUAL", debt_id), "").strip() in ("1", "true", "yes")
        if overrides and debt_id in overrides:
            return bool(overrides[debt_id])
        if spec.dial == "default-on":
            off = os.environ.get(_env_key("MAG_RATCHET_OFF", debt_id), "").strip().lower()
            return off not in ("1", "true", "yes")
        if spec.dial == "opt-in":
            on = os.environ.get(_env_key("MAG_RATCHET_ON", debt_id), "").strip().lower()
            return on in ("1", "true", "yes")
        return False

    def retire(self, debt_id: str, *, verified_by: str, evidence_path: Path | str, note: str = "") -> dict:
        spec = self.get(debt_id)
        ev = Path(evidence_path)
        if not ev.is_file():
            raise FileNotFoundError(f"retirement evidence missing on disk: {ev}")
        digest = hashlib.sha256(ev.read_bytes()).hexdigest()
        receipt = {
            "schema": "mag_ratchet_retirement.v1",
            "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "debt_id": spec.debt_id,
            "dial": spec.dial,
            "owner_organ": spec.owner_organ,
            "delete_when": spec.delete_when,
            "verified_by": verified_by,
            "evidence_path": str(ev),
            "evidence_sha256": digest,
            "note": note,
        }
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        with self.ledger_path.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(receipt, sort_keys=True) + "\n")
        return receipt

    def list_specs(self) -> List[dict]:
        return [asdict(s) for s in self._specs.values()]


DEFAULT_REGISTRY = RatchetRegistry()

for _item in (
    RatchetSpec(
        debt_id="B2-294-seal-line-8mb",
        dial="always-on",
        delete_when="index_events.jsonl migrates fully to bintree_v2 content-addressed store",
        owner_organ="tools/md_record_seal.py",
        summary="Hash real bytes up to 8 MB in both register_sha256 and seal_line so autoseal never shadows register",
    ),
    RatchetSpec(
        debt_id="INVARIANT-20261017-03-free-lane-width",
        dial="always-on",
        delete_when="OpenRouter/free providers replace burst-concurrency 429s with token-bucket headers",
        owner_organ="tools/full_scan.py",
        summary="Cap free-lane dispatch concurrency to width <= 3 with >= 5.0s inter-call pacing",
    ),
    RatchetSpec(
        debt_id="GHOST-1-fkb-circuit-breaker",
        dial="default-on",
        delete_when="Linux container autonomous_janitor retired or unified with host Windows janitor",
        owner_organ="mag/ghost.py",
        summary="Suppress win32-only fkb: quests in Linux container and trip 3-fail circuit breaker over auto_trail",
    ),
    RatchetSpec(
        debt_id="CHAIN-V2-shadow-hook",
        dial="opt-in",
        delete_when="7-day v2 binary-tree shadow completes with 0 unexplained mismatches and v1 writer retires",
        owner_organ="mag/verkle_knot.py",
        summary="Mirror v1 verkle_knot appends into memory/biography_v2 binary tree when chain_v2_shadow is enabled",
    ),
    RatchetSpec(
        debt_id="CHAIN-V2-checkpoint-signing",
        dial="manual-only",
        delete_when="Automated HSM/seal-key daemon replaces operator-gated Ed25519 checkpoint signing",
        owner_organ="mag/bintree_v2.py",
        summary="Sign v2 binary-tree checkpoints with pinned Ed25519 seal key de5fc05e962c43ab",
    ),
):
    DEFAULT_REGISTRY.register(_item)
