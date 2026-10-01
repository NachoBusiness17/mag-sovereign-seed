# Reading Guide – docs_register (STACK_V1.md)

**Entry file**: `docs/ref/STACK_V1.md`

### Three things to check
1. **Memory longevity claim** – The file states the signed memory “outlives every machine it runs on.” Verify by inspecting the verkle chain metadata (e.g., `memory/biography/verkle_chain.jsonl`) for a creation timestamp older than the latest container start time. If the timestamps overlap, the claim is overstated.
2. **Disposability of the body vs permanence of the record** – Confirm that container disposal is truly automated and that no persistent state lives outside the append‑only chain. Search for any `.bak` or persistent config files (`*.bak`, `configs/*.yaml`) that survive container teardown.
3. **Operator‑seat count** – The register says “One operator, several AI seats.” Cross‑reference `AGENTS.md` and `configs/lanes.yaml` to ensure the documented number of seats matches the actual registered seats (`mag.seat_registry`).

### The one trap
- **Over‑claim of “sovereign” invariance** – The text promises *nothing required runs* and *sovereignty is structural*. If any required service (e.g., `mag.watchdog` or `mag.docker-watchdog`) is manually started outside the chain, the claim is false. Verify that all required services are auto‑started by the orchestrator and not manually invoked.
