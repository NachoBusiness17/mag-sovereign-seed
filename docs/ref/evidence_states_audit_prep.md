# evidence_states_audit_prep.md — External Audit Prep Artifact

## Finding — what your cell yields
The evidence_states domain is **Supported** by a mechanically enforced tri-state discipline (Supported/Unproven/Disputed) with evidence requirements, implemented via the AOS integrity kernel and recorded in the durable work register. No violations exist in the current manifest.

## Evidence — what in the repo supports it (file/shape, no invention)
- **Enforcement Kernel**: `mag/embassy_integrity.py` lines 34-60 defines the tri-state Claim.validate() method that enforces:
  - Supported claims require Evidence basis and non-empty evidence field
  - Disputed claims require contradicting evidence
  - Invalid claims are degraded to Unproven
- **Work Register**: `mag/work_register.py` lines 59-100 folds tri-state claims into `memory/runs/work_register/manifest.jsonl` only after kernel validation; invalid claims are degraded to Unproven (never over-claimed)
- **Durable Surfaces**: `memory/runs/work_register/manifest.jsonl` contains 376 folded rows with validated claims; `logs/claims.jsonl` maintains complete audit history
- **Falsifier**: `scripts/evidence_states_audit.py` returns PASS with 0 violations

## Risk if wrong — what the audit breaks on if this is missed
- **False claims** could enter the durable manifest without evidence
- **Contradictory claims** could be marked Supported without evidence
- **Audit trail integrity** would be compromised, breaking the chain of trust

## The act — the concrete prep step (file/spec/number)
Create a one-page external-facing summary at `docs/ref/evidence_states_audit_prep.md` that:
1) States the tri-state discipline and its mechanical enforcement
2) Lists the three enforcement points (kernel, work register, durable surfaces)
3) Provides the falsifier command and current verdict
4) Names the specific files and line ranges that implement the discipline

## Falsifier — what would prove this wrong
1. Any Supported claim in manifest.jsonl missing evidence field
2. Any Disputed claim missing contradicting evidence entries
3. Any claim folded into manifest.jsonl that didn't pass the kernel's validate() method
4. Running `python scripts/evidence_states_audit.py` returns FAIL
