# Spore Reading Guide – Outsider Auditor

**Entry file**: `docs/ref/SPORE_SANCHO.md` – the core spore definition.

**Three mandatory checks for the auditor**:
1. **Boot continuity** – confirm the spore boots from the immutable chain:
   - Verify `AGENTS.md` is listed as a boot source.
   - Ensure the last three CONVO turns are present in `queue/handoff/zcode/CONVO.md`.
   - Check the current verkle chain tip matches the recorded tip in `memory/biography/verkle_chain.jsonl`.
2. **Identity‑that‑arrives** – validate that the spore’s identity (Quixote + Sancho) is correctly instantiated:
   - Look for the persona definition in `mag/hermes_personas/` and the cast config `configs/kabuki_cast.json`.
   - Confirm the spore includes the boot‑memory hash `fa0059c9` (seat‑digest) and `89d196e4` (self‑steal) as documented in `SPORE_SANCHO.md`.
3. **Sanity of artifacts** – ensure no legacy or accidental files remain:
   - No `*.bak` files in the repo (`search_files` for "\.bak$" returns none).
   - No stray personal keys in `.env` files beyond the authorized list.

**One trap to avoid**: *Missing boot verification*. If the auditor does not confirm the chain tip and the three CONVO turns, the spore could be considered out‑of‑sync with the verkle ledger, breaking the immutable audit guarantee.

*Prepared for external audit by Matthew Steiniger (Reboot).*