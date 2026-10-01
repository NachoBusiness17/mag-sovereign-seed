# Oct-27 Migration Manifest — Reading Guide

Entry file
- docs/ref/SPORE_CONTINUITY_SCHEMA.md

Three things to check (quick, falsifiable)
1. Verkle continuity: memory/biography/verkle_chain.jsonl exists and contains the claimed knot counts; run `python -m mag.verkle_audit --dry` and confirm chain tip matches `docs/ref/SPORE_CONTINUITY_SCHEMA.md` references.
2. Identity pre/post test: confirm `python -m mag.identity_check --date=2026-10-26` and `--date=2026-10-27` are runnable (scripts present under mag/) and assert identity-hash correlation ≥0.95.
3. Narrative coupling: inspect audit_corpus/PARABLE_SCAFFOLDING_ABLATION_PLAN.md for the parable dependency; verify the audit bundle includes the parable artifacts (search audit_bundle/ for parable files) so a clean-room reproducer can reconstruct narrative framing.

The one trap (what will fool an outside reader)
- Missing roadmap stub: docs/ref/SPORE_CONTINUITY_SCHEMA.md references `docs/ROADMAP_OCT_27.md` and test commands but there is no dedicated migration manifest file or an explicit checklist tying the identity-check command to concrete input artifacts. An examiner will find the claim "Identity persists across substrate changes" marked Unproven unless the manifest names the exact files, commands, and acceptance thresholds.

Minimum prep action (concrete)
- This file (docs/ROADMAP_OCT_27.md) is the entry manifest. Add one small artifact: a test-verification table at `audit_reports/identity_migration_preflight_{timestamp}.md` produced by `python -m mag.audit_prep --examiner=steiniger --domain=migration_manifest`.

Fail condition (falsifier)
- A run of the identity-check commands (pre/post) producing identity-hash correlation < 0.95 or missing/mismatching verkle knots proves the Oct-27 continuity claim false.
