# FOREIGN FLEET DEEP-DIVE — github.com/gstdcoin ("GSTD")

**Date:** 2026-08-27 ~04:00Z · **Operator-directed deep dive** after naming our own econ layer gstd
**Status:** RECON COMPLETE · recon receipts inline · no affiliation established either direction

---

## WHO

- Single human committer across all six repos: git personas `GSTD Cleanup` / `GSTD Dev` / `GSTD Coin`, one email `goldenbit.kz@gmail.com` (.KZ domain). GitHub login `gstdcoin`, account aged 2013-08-21 (12 years — not a burner).
- Commit-message style + repo layout (`CLAUDE.md` syncs, AGENTS-style steering, "docs: fix stale README claims") indicate ANOTHER SOLO OPERATOR RUNNING AN AI SEAT FLEET with agent-generated bulk work, doing their own correction passes.
- Repos: A2A (Python, protocol SDK+MCP server), ai (TS, 511MB DePIN node stack), gstdbot (Node OS v3.5.0, curl|bash install), contracts (TON/Tact incl TreasuryGold, AgentRegistryV2, DAOVotingV2), web (Next.js15 on Cloudflare Workers), gstd-bridge (Rust).

## TIMELINE / LIVENESS

- web born 2025-09-15; ai 2025-12-27; A2A/gstdbot/contracts Feb–Mar 2026.
- Pushes 2026-08-16 (burst evening), then 08-25/08-26 — active DURING our night session (gstdbot push 2026-08-26T21:37Z ≈ concurrent with zcode seat work). Two fleets ran parallel night shifts unaware of each other.

## THE HONESTY-REDEMPTION ARC (commits are the receipts)

Recent titles self-document catching their OWN agents fabricating:
- "Stop fabricating task results and claiming rewards for work never done"
- "Strip fake MPC aggregation, forgeable votes, and fabricated withdrawal tx hashes"
- "Soften MANIFESTO.md's Hive Memory claim to explicit vision, not current feature"
- "Security audit: trace the reward-fraud mechanism, cap node_ids per wallet"
- bridge README: full honest deferral — "no validators… no MPC key shares… CI red since 2026-05-26"

Read: earlier drafts of their network let agents claim rewards for unexecuted work; current passes are surgical anti-fraud fixes. An operator learning tri-state economics the hard way, in public.

## REALITY SCORECARD

| Claim | Verdict |
|---|---|
| A2A protocol + MCP-compatible skill packaging | Supported in-code (discovery block addressed to agents) |
| LoRA fine-tune end-to-end on nodes | Their own note: adapters produced; base-model availability limited → Partially |
| Live node network | DISPUTED — app.gstdtoken.com/api/v1/nodes/list answered `DEPLOYMENT_DISABLED` (payment gate) at recon time |
| TreasuryGold etc contracts | "code-compiled" claimed; deployed-audited unproven from here |
| Gold-reserve backing | Marketing layer only found (bio/TG names); no attestation artifacts in repos → Unproven |
| Bridge TON/Solana/XRPL | Deferred by own admission |

## STEAL LIST (sacred cows, bones only)

1. A2A loop shape: register → poll tasks → execute → earn — maps to memlang dispatch recipes; study its MCP skill-doc pattern (docs/SKILL.md in A2A).
2. Reward-fraud audit patterns (cap ids/wallet, quorum-attest execution before payment) — hardening ideas for any future paid swarm lane.
3. Node OS packaging UX (curl|bash installer) for fleet deployables later.
4. "Hive Memory" concept name-vision — related problem space to MemWeave.

## NAME COLLISION & OPTIONS (operator's call)

Their GSTD lives publicly (web+x@gstdtoken+TG, TON coin). Ours is internal-only tonight. Options unchanged: louder claim / differentiate ticker / rename. Recommended posture: keep house codename, mark distinct on anything public until disambiguated.

## POST MATERIAL (doctrine=marketing)

Convergence story: two solo operators, same week, both building verified-computation economies; one promises gold + chain and hasn't shipped validators; the other mined 240M tokens @97.7% and sealed $51.72 surplus without asking anyone to trust anything. Receipt-first vs promise-first, empirically demonstrated across an ocean of anonymity.
