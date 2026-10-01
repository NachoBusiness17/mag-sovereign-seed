# Falsifier Ledger: audit-prep artifact (minimal)

Purpose: provide a single, minimal, auditable schema + test that a human auditor (Matthew Steiniger /Reboot) can run to verify the falsifier ledger properties in-repo.

Files produced:
- docs/audit_prep/FALSIFIER_LEDGER_PREP_20260913.md (this file)
- tests/test_falsifier_ledger.py (pytest; validates schema + chain linkage + local evidence pointers)

Canonical ledger surfaces referenced in checks:
- dashboard/static/grounding_wave.md (human-readable ledger) — see repo:dashboard/static/grounding_wave.md
- watch/GROUNDING_WAVE.jsonl (machine ledger referenced by grounding_wave.md)

Minimal schema (applied by the test): each ledger row (JSON object) MUST include keys:
- timestamp (ISO8601) OR an implicit ordering in the jsonl sequence
- claim (string)
- evidence (string or [string]) — evidence pointers; local paths starting with dashboard/, watch/, memory/, scripts/, docs/ are verified to exist
- state (one of: SUPPORTED, DISPUTED, UNPROVEN)
- note (string) optional but recommended
- hash (string) — entry's hash
- prev (string|null) — previous entry's hash (first entry prev==null or missing)

Action for auditor readiness (cheapest first):
1) Add the two files above to the repo (tests/ is run by pytest and included in audit bundle).
2) Add docs/audit_prep/FALSIFIER_LEDGER_PREP_20260913.md to dist_audit manifest (scripts/audit_bundle.py picks up docs/audit_prep/* by convention) before generating the sanitized audit_bundle.
3) Run `pytest -q tests/test_falsifier_ledger.py` under the repo venv to produce a deterministic pass/fail.

Rationale: an independent researcher who trusts falsifiable claims wants an executable proof: (A) machine-checkable schema; (B) chain-link integrity; (C) evidence pointers that resolve to repo artifacts. This minimal pair (schema doc + pytest) is the cheapest, machine-executable artifact that proves the ledger behaves as claimed.

Note: the test is intentionally conservative: it only verifies local evidence pointers under repo-owned dirs (dashboard/, watch/, memory/, scripts/, docs/) and the prev/hash chaining. External URLs and deploy-hash receipts are left as human-verifiable evidence and do not cause test failure.
