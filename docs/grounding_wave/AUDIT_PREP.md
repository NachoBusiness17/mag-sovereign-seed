Purpose: prepare the grounding_wave area for external audit (Matthew Steiniger).

Checklist (concrete, one-shot prep):

1) Evidence bundle (existence): ensure these files are present and unchanged:
   - handoff/OX_MEGA_claim_grounding_gate.json (spec of fail-closed grounding gate)
   - handoff/OX_MEGA_recursion_grounding.json (recursion-grounding rule)
   - handoff/OX_MEGA2_own_ground_truth.json
   - handoff/OX_MEGA2_shared_verifiable_ground.json
   - window/surface.json (contains "tri-state" / evidence supremacy language)
   - tests/test_lattice_grounding.py

2) Non-invasive checks (commands to run locally, read-only):
   - git ls-files | rg "OX_MEGA|surface.json|test_lattice_grounding.py"
   - ./.venv/Scripts/python.exe -m pytest tests/test_lattice_grounding.py -q
   - ./.venv/Scripts/python.exe scripts/chain_probe.py --verify (read-only probe)

3) Add an auditor-facing index (this file) plus a single deterministic presence test to be committed separately if approved:
   - tests/test_grounding_wave_presence.py (spec: assert files exist; assert window/surface.json contains "tri-state" and "evidence supremacy" strings; do not alter any other content)

4) Risk notes for the operator: do NOT modify the verkle chain or attempt to repair knots; repairs are operator-only blessings. All checks above are read-only.

5) Acceptance for audit handoff: this doc present + CI-local run of the presence test passing (or manual assertion recorded). File path to add to audit bundle: docs/grounding_wave/AUDIT_PREP.md

Timestamp and author: write this file as the prep artifact before collecting the sanitized audit bundle.
