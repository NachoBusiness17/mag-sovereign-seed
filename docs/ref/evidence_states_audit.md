# evidence_states_audit.md — Evidence States Discipline Audit

## 1. The Tri-State Law

**Every claim in the repository MUST carry a status (Supported/Unproven/Disputed) with basis and evidence.** This is not a guideline—it is mechanically enforced by the integrity kernel and work register.

### The Discipline
- **Supported claims**: Require at least one "Evidence" basis and attached evidence files/paths
- **Disputed claims**: Require contradicting evidence (cannot be based only on Inference/Assumption)  
- **Unproven claims**: Default status for claims without sufficient evidence or with only Inference/Assumption basis
- **Validation**: Claims are validated BEFORE being folded into the durable manifest

## 2. Enforcement Points

### A. Integrity Kernel (`mag/embassy_integrity.py`)
- **Lines 7-60**: Defines the tri-state claim model with Evidence/Inference/Assumption basis
- **Lines 48-60**: `Claim.validate()` method enforces the discipline:
  - Supported claims must have Evidence basis and evidence field
  - Disputed claims must have evidence field (contradicting evidence)
  - Invalid claims are rejected with specific error messages

### B. Work Register (`mag/work_register.py`)
- **Lines 59-100**: `record()` function folds tri-state claims into durable manifest
- **Lines 76-87**: Claims are validated via integrity kernel BEFORE folding
- **Lines 66-67**: Invalid claims are degraded to Unproven (never over-claimed)
- **Lines 84-85**: All claims are logged to `logs/claims.jsonl` for audit trail

### C. Durable Evidence Surfaces
- **`memory/runs/work_register/manifest.jsonl`**: Records every folded claim with validated status, basis, and evidence
- **`logs/claims.jsonl`**: Timestamped log of all claims with validation outcomes

## 3. Audit Checklist

### Critical Checks
- [ ] Scan `memory/runs/work_register/manifest.jsonl` for Supported claims missing evidence field
- [ ] Verify Disputed claims have contradicting evidence entries
- [ ] Confirm kernel validation happens before folding in `work_register.record()`
- [ ] Check that no claim bypasses the integrity kernel

### Sample Patterns to Verify
```json
// Valid Supported claim
{
  "status": "Supported",
  "basis": ["Evidence"],
  "evidence": ["path/to/evidence/file.txt"]
}

// Valid Disputed claim  
{
  "status": "Disputed", 
  "basis": ["Evidence"],
  "evidence": ["contradicting evidence path"]
}

// Invalid (would be degraded to Unproven)
{
  "status": "Supported",
  "basis": ["Inference"],  // Invalid for Supported
  "evidence": []           // Missing evidence
}
```

## 4. Falsifier Script

Run `python scripts/evidence_states_audit.py` to programmatically verify compliance:

```bash
cd local_sovereign_agent
python scripts/evidence_states_audit.py
```

The script will:
- Parse `memory/runs/work_register/manifest.jsonl`
- Validate each claim against the integrity kernel rules
- Report any violations with specific file/line references
- Return PASS/FAIL verdict

## 5. What Would Prove This Wrong

The evidence_states discipline is FALSE if any of these conditions exist:

1. **Supported claim without evidence**: Any claim in manifest.jsonl with status=Supported but no evidence field
2. **Disputed claim without contradicting evidence**: Any Disputed claim missing evidence entries  
3. **Kernel bypass**: A claim folded into manifest.jsonl that doesn't pass the kernel's validate() method
4. **Script failure**: Running `python scripts/evidence_states_audit.py` returns FAIL

## 6. Audit Trail

All enforcement and validation is tamper-evident:
- Verkle knots provide cryptographic provenance for each fold
- Claims.jsonl maintains complete audit history
- Integrity kernel validation is deterministic and repeatable

---
**Audit Date**: 2026-09-12  
**Domain**: evidence_states  
**Status**: Supported (mechanically enforced)  
**Falsifier**: scripts/evidence_states_audit.py