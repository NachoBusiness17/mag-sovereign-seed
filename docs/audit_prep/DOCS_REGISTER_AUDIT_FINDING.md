## Finding — what your cell yields

STACK_V1.md over-claims provenance tracking. It claims "research lineage is tracked in a bibliography map" and "full-fidelity internals stay in local files by law," but the actual register is a de-riddled narrative with no structured bibliography, no paper-to-subsystem mappings, and no centralized provenance ledger.

## Evidence — what in the repo supports it (file/shape, no invention)

- `docs/ref/STACK_V1.md` §10 claims: "Research lineage is tracked in a bibliography map (papers to subsystems, with status)"
- Repository audit shows no bibliography map exists, no papers-to-subsystems registry exists, and no provenance tracking system
- Mentions of "provenance" in docs are scattered dashboard references, not research lineage tracking
- Charged register dogfood experiments exist but are domain-specific (medieval_guild), not general research provenance
- No bibliography files, citation indexes, or research lineage manifests found in the repo structure

## Risk if wrong — what the audit breaks on if this is missed

The examiner will identify the provenance gap as a fundamental integrity violation. The claim of "research lineage tracking" is falsifiable and false, undermining the document's credibility as a complete self-description. This reveals a pattern of over-claiming documentation completeness.

## The act — the concrete prep step (file/spec/number)

Create `docs/ref/BIBLIOGRAPHY_MAP.md` - a structured research lineage registry with three columns: (1) Paper/Source, (2) Subsystem Implementation, (3) Status (Adopted/Rejected/In Progress). Populate with existing research traces found in memory/ and docs/ to make the provenance claim real.

## Falsifier — what would prove this wrong

A single existing bibliography map file or research lineage registry that tracks paper-to-subsystem mappings with status, published before this audit prep finding.