# HOW TO RUN THE BRAIN BOX — playbook for the fresh window (2026-08-27 night)

Mission: self-hosted GLM-5.3-Flash on ONE rented 3090-class box. Everything below
is paid for in tuition (~$3.40, eleven boxes). DO NOT re-derive — execute.

## THE LAWS (each bought with receipts)
1. **Image = `ollama/ollama:latest` ONLY.** Foreign images (pytorch/vllm/nvidia)
   never register with vast's ssh proxy → permanently dark. 3-for-3 proven.
2. **Reachability gate via `ssh6.vast.ai` proxy ONLY.** Direct IP always times
   out, reachable or not. Gate: `ssh -p <port> root@ssh6.vast.ai` within 5 min
   of running. Dark = destroy, next candidate. ~$0.03 per sample.
3. **Heavy onstart blocks sshd until done** — don't expect ssh mid-contract;
   contract must self-report (status.json → mapped port 8001).
4. **Deal card** (operator-approved): 3090, cpu_ram ≥128GB, host disk ≥300GB,
   rel ≥0.97, ≤$0.35/hr. Machine 138174 (California, 188GB RAM, 2.9Gbps) =
   the dream; it re-lists periodically — grab on sight.
5. **Blocklist:** machines 147517, 31186, 39565, 20092 (+ state/vast/blocked_machines.json).
   147517/31186 = wedge hosts (accept contracts, never boot); 20092 = port-dark.
6. **Budget:** credit ~$45 (console.vast.ai `/users/current/` field `credit` —
   NOT `balance`). Refuse launch under $5.
7. **Quant: UD-IQ3_XXS (120GB, 4 shards)** fits a 129GB-RAM+24GB-VRAM box
   (153GB total). Q4_K_XL (186GB) needs ≥200GB total — multi-GPU/big-RAM hosts
   were network-dark from this desk; single-box IQ3 is the proven path.
8. **Serve law:** right-size context (4096; ollama's 32K default = 33GB alloc =
   CPU offload = 12 tok/s disaster) and ONE resident model variant.
9. Thinking tax is cross-provider: /no_think or budget max_tokens ≥1536.

## THE TOOLING (all exists, all verified)
- `state/vast/box_contract.sh` — boot contract v2.1 (verified shard names
  UD-IQ3_XXS 4 shards, prebuilt llama.cpp, phase heartbeat, self-health).
  NOTE: verify asset exists at contract start; filenames were checked 08-27.
- `state/vast/seeker.py` — RUNNING detached: hunts the deal card every 3 min,
  asks + gates + destroys-dark automatically, writes state/vast/brain_v2_endpoint.txt
  and reachable_machines.json whitelist on success. Check `state/vast/seeker.log`.
- `state/vast/launch_vast.py` — probe/instances/destroy (launch = SDK instead).
- `scripts/council_runner.py` — council instrument, dry-verified.
- `scripts/steering_suite.py` — EXP-02 harness, selftest PASS, live smoke PASS
  (first datum: doctrine prefix +0.33 over baseline, n=1).
- `state/vast/corpus_packs/` + `corpus_questions.json` — EXP-01 ammo (grok-1).
- `docs/ref/VAST_API_EXPERT_REFERENCE.md` — API laws (two generations, credit
  not balance, gpu_ram in MB, storage billed while STOPPED).

## EXECUTION SEQUENCE (fresh window)
1. Boot read: memory MEMORY.md + this file + CONVO.md last 5 rows. That's the
   whole state; do not read this session's history.
2. Check `state/vast/seeker.log` — if a box is acquired, skip to 5.
3. If seeker is still hunting: let it. Meanwhile run `--summary` on
   `state/vast/burst_results.jsonl` + verify hands box tunnel still green.
4. If no box by ~2h: widen deal card to $0.45 or try machine 122589/other
   SK/PL hosts again — reachability may be time-of-day dependent. Each probe ~$0.03.
5. On box: contract self-runs (onstart). Watch `http://IP:8001/status.json`
   (phase heartbeat) + `:8000/health`. When health OK →
   `BRAIN_STATUS.txt` receipt → tunnel `ssh -L 18000:localhost:8000` →
   steering full battery + council session (`scripts/council_runner.py`,
   questions in `state/vast/brain_questions.md`, model registry via env).

## FALLBACK LADDER (if the brain fights back)
a. Same contract, UD-Q2_K_XL folder (109GB — check HF tree for real shard names
   via the API before hardcoding: /api/models/unsloth/GLM-5.3-Flash-GGUF/tree/main/<quant>).
b. Keep brain in RAM only (no disk concern) — box disk 260GB assumed.
c. Hosted 5.3 via membership = always available judgment; the box is upside.

## WHAT NOT TO DO
- No multi-GPU hosts yet (all tested dark — retry after feed verdict data).
- No new orchestrators/buyers — ONE seeker instance max (budget-projection law).
- No premium-seat debugging of dark boxes — they're a lottery, sample and move.
