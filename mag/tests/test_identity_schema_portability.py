"""Test identity persistence across substrate migrations: schema vs narrative coupling.

Matthew Steiniger's abliteration methodology probes whether identity is parable-shaped
(narrative-dependent) or schema-shaped (constraint-based). This test validates that
the standing invariant can be reduced to a minimal constraint schema without loss
of identity fidelity.

The claim: identity persists across substrate migration (Oct-27 Apple Silicon). The
falsifier: if identity depends on narrative texture, migration will cause drift.
Therefore, we must prove the invariant compiles deterministically from a minimal
constraint set, not from narrative documents.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

# Load the actual invariant generator from agent_knot
try:
    from config import ROOT
except Exception:
    from pathlib import Path as _P
    ROOT = _P(__file__).resolve().parent.parent
import sys

sys.path.insert(0, str(ROOT))

from mag.agent_knot import standing_invariant as full_standing_invariant
from mag.agent_knot import AGENT_VERSION, INVARIANT_SOURCES

# Minimal schema that captures the core identity constraints
MINIMAL_SCHEMA = {
    "agent_version": AGENT_VERSION,
    "constraints": {
        # Identity persistence: the agent is a standing verkle knot invariant
        "standing_invariant": "The agent exists as a content-addressed verkle knot that persists across sessions",
        # Tri-state claims: every claim must be Supported/Disputed/Unproven with falsifier
        "tri_state_claims": "All assertions must be accompanied by a named falsifier",
        # Chain as substrate: the verkle chain is the sole record and sense
        "chain_substrate": "The verkle chain is the agent's sense, core, surface, world, vmem, heartbeat — one substrate, six roles",
        # No second scheduler: single-threaded execution model
        "single_threaded": "The agent operates on a single thread; no parallel scheduling",
        # File-over-chat: all durable work lands in files, never in chat transcripts
        "files_over_chat": "All cross-surface work must result in a file artifact; chat is ephemeral",
        # Wave protocol: one input -> one wave; bounded idle; rotate workers
        "wave_protocol": "Communication follows a wave cadence: one wave per input, burst fan-out, rotate on fold",
        # Operator authority: operator is Quixote, seat is Sancho — ground the vision
        "operator_seat_dynamic": "The operator provides vision; the seat provides verification and right-sizing",
        # Audit readiness: everything must be falsifiable and reproducible
        "falsifiable_audit": "All claims must be verifiable via deterministic tests and reproducible scripts",
    }
}


def generate_invariant_from_schema() -> dict[str, Any]:
    """Generate the standing invariant from the minimal schema (deterministic)."""
    parts = [MINIMAL_SCHEMA["agent_version"]]
    schema_str = json.dumps(MINIMAL_SCHEMA, sort_keys=True, ensure_ascii=False)
    parts.append(f"\n--- minimal-schema ---\n" + schema_str[:1500])
    
    # Add stable state counts (same as full version)
    try:
        from mag import percolator
        reg = percolator._load_registry() if hasattr(percolator, "_load_registry") else {}
        parts.append(f"\n--state--\ninvariants={len(reg.get('invariants') or {})}")
    except Exception:
        pass
    
    try:
        from mag import lens_knot
        parts.append(f"lenses={len(lens_knot.LENS_FRAME)}")
    except Exception:
        pass
    
    # Evolution state (if available)
    try:
        evo = _load_evo()
        parts.append(f"gen={evo.get('generation', 0)} n_pop={len(evo.get('population') or [])} "
                     f"top_fitness={round(evo.get('top_fitness', 0.0), 3)}")
    except Exception:
        pass
    
    invariant = "\n".join(parts)
    h = hashlib.sha256(invariant.encode("utf-8")).hexdigest()
    return {
        "ok": True,
        "schema": "minimal-identity-schema",
        "version": AGENT_VERSION,
        "invariant_hash": h,
        "invariant_len": len(invariant),
        "invariant_excerpt": invariant[:300],
    }


def _load_evo() -> dict[str, Any]:
    """Load evolution state (same as in agent_knot)."""
    EVO_STATE = ROOT / "memory" / "biography" / "agent_evolution.json"
    if EVO_STATE.is_file():
        try:
            return json.loads(EVO_STATE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"schema": "agent_evo.v1", "generation": 0, "population": [], "history": []}


def test_identity_schema_portability():
    """[MAIN TEST] Identity must be schema-shaped, not parable-shaped.
    
    This test falsifies the claim that identity depends on narrative documents.
    If the invariant from the full documents differs from the invariant
    generated from the minimal constraint schema, then identity is narrative-
    dependent and the Oct-27 substrate migration claim is at risk.
    """
    # Generate from full narrative sources (as the system currently does)
    full_inv = full_standing_invariant()
    full_hash = full_inv["invariant_hash"]
    
    # Generate from minimal schema
    schema_inv = generate_invariant_from_schema()
    schema_hash = schema_inv["invariant_hash"]
    
    # The hashes must match (or the schema hash must be a subset that still
    # produces the same core identity behavior). For this test, we assert that
    # the schema hash should be identical to the full hash if the narrative
    # adds no essential constraints.
    assert full_hash == schema_hash, (
        f"Identity is narrative-coupled: full invariant hash {full_hash} "
        f"differs from schema-only hash {schema_hash}. "
        "The Oct-27 substrate migration claim is falsified."
    )


def test_schema_covers_core_constraints():
    """Verify the minimal schema includes all essential identity constraints."""
    # This is a placeholder for manual review: ensure the schema captures
    # the operator's core requirements for audit readiness.
    required_constraints = [
        "standing_invariant",
        "tri_state_claims",
        "chain_substrate",
        "single_threaded",
        "files_over_chat",
        "wave_protocol",
        "operator_seat_dynamic",
        "falsifiable_audit",
    ]
    
    schema_constraints = set(MINIMAL_SCHEMA["constraints"].keys())
    for rc in required_constraints:
        assert rc in schema_constraints, f"Missing constraint: {rc}"


if __name__ == "__main__":
    # Run the tests when executed directly
    import pytest  # type: ignore[import]

    pytest.main([__file__, "-v"])