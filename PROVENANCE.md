# PROVENANCE — how this seed was built (2026-09-30)

Export prepared by the operator's ZCode seat (laptop side), read-only pulls from the
live estate over SSH. Nothing on the estate was modified to make this package.

## Source anchor

- Estate: `local_sovereign_agent` (live fleet copy, private machine)
- Verkle chain at export: tip root `00e374bd9b9b1b92b35fe70174cd69128ed9dd5145e20bca7de44a7978208a33`,
  8,692 leaves, tip ts `2026-09-30T23:47:34Z` (autonomous janitor knot)
- Newest seal at export: `2026-09-30T09-02-29` (referenced by name only; not shipped)

## Included

- `boot/` — AGENTS.md, CONSTITUTION.md, LOAD.md, RUNNING.md, OUTPUT_CONTRACT.md,
  TOOLS.md, THE_MACHINE.md, README_ESTATE.md, requirements.txt, docker-compose.yml,
  main.py, mag.cmd
- `docs/` — full documentation tree (manual, reference, publish checklist)
- `mag/` — the Python package (organs), bytecode-stripped
- `memory/` — MEMORY.md (live index + phantom ledger), briefs/latest.md (frozen
  self-brief with its honesty banner), doctrine/ (law ledger + scorecard)
- `story/` — 48h_synth/ (six synthesis chapters), RAINBOW_ROAD_RACTOR_20260929/
  (full ractor pack), RAINBOW_CLAIMS_AUDIT.md, GALA_20260925.md

## Excluded, and why

| Excluded | Reason |
|---|---|
| `.env` (and `.env.example`) | secrets by definition; never pulled |
| `memory/biography/` (verkle chain + knots) | estate publish law `docs/GITHUB_PUBLISH.md`: "never push"; the private self-record |
| `memory/seals/` | seal snapshots embed `configs/providers.yaml`, an OPERATOR-ONLY attestation file carrying account handles and a partial key prefix; whole directory cut after inspection |
| `corpus/` (8.6 GB) | mixed licensing incl. non-redistributable reference texts |
| `docs/report_v1/` | contains copyrighted third-party PDFs and arXiv transcriptions |
| `dashboard/`, `watch/` bulk, `state/`, `data/`, `queue/`, `server/`, `scripts/`, `tools/`, `tests/`, `training/`, `research/` | runtime state, bulk data, or private ops per publish law |
| `.git/` | history may carry retired secrets |
| `__pycache__/`, `.pyc/.pyo`, `.mimosa/` caches | estate t7 law: pyc-strip before public seed flip; runtime caches are not source |
| root scratch (game-wiki scrapes, one-off `_*.py`) | work artifacts, not seed material |

## Secrets audit (method and result)

1. Filename sweep on the source tree: only `.env` / `.env.example` matched secret
   filename shapes; neither was pulled.
2. Tier-1 pattern scan of the package (PEM blocks, sk-/ghp_/xox/AKIA/AIza and
   vendor prefixes): 7 files matched; all inspected; all were the fleet's own
   sanitizer regexes, docs about them, or a log line noting a PAT lives in the
   never-shipped `.env` (no values).
3. Tier-2 structural scan (python, regex for live key shapes incl. sk-or-, gsk_,
   csk_, hf_, xai-, tgp_, fw_, github_pat_, AKIA, AIza, xox, JWTs, telegram bot ids,
   `key = <24+ chars>`, `bearer <24+ chars>`): 14 hits, all inspected:
   placeholder examples (1), example tokens inside the public MCP spec mirror (4),
   internal tool session ids inside a `.mimosa` cache (6; that cache directory was
   then cut entirely), mnemonic fake keys in comments (3).
4. Post-cut rescan: 8 residual hits, every one a benign shape already listed above
   (placeholder, MCP-spec example token, or mnemonic comment key).
   Final result: **zero live secret values in this package.**

## Integrity

- `SEED_MANIFEST.sha256` lists SHA-256 for every file (generate/verify: see its header).
- Zip artifact: `mag_sovereign_seed_20260930.zip` (this folder minus the zip itself).

## Notes and flags

- `docs/ref/GAME_PLATFORM_BASECAMP.md` mentions that a GitHub PAT is parked in the
  estate `.env` (gitignored, not shipped). Kept: factual log, no value.
- `boot/README_ESTATE.md` carries the estate's own truncation-repair note verbatim.
- Mirrored third-party docs (`docs/ref/zai_docs_mirror/`, `docs/mirrors/mcp/`) belong
  to their publishers and are included as reference mirrors of public documentation.
