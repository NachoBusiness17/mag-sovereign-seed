# SURFACES — the fleet's complete observability registry (2026-08-26)

One registry of every surface the operator touches or the fleet runs. The rule this
replaces: N scattered dashboards → publish the few load-bearing surfaces, aggregate
the rest into one view. Status sources are LEDGERS (already recording), not new probes.

## A. Control surfaces (the ones worth a window)
| Surface | Endpoint | Auth | Status source |
|---|---|---|---|
| **OpenClaw Control UI** (fleet gateway) | http://127.0.0.1:18789 | token (URL fragment; Mag OpenClaw.lnk) | gateway ws + logs |
| **Mag dashboard** (legacy SPA) | http://127.0.0.1:8765 | open (loopback) | dashboard/rest.py — prune to the pages that matter |
| **AutoClaw app ×2** (credit lanes) | desktop, elevated | app account (zai_auto bound) | %APPDATA%/AutoClaw/auth.json mtime + gateway log |
| **VS Code copilot seat** (retiring) | desktop window | BYOK deepseek | chat panel; sessions in workspaceStorage |

## B. Compute lanes (where work runs) — FINAL DOCTRINE (operator, 2026-08-26)
| Role | Lanes | Law |
|---|---|---|
| **Swarm/cache-mining** | z_ai, z_ai4 (paid API keys) | cache economics; frozen prefix mandatory |
| **Coding seats in tandem** | z_ai2 (Pro) + z_ai3 (Lite) | cold-writer/warm-reader pair; seat work + swarm carry |
| **EXPERIMENT LANE** | deepseek | bulk trials at 97% cached prefix — MAX_DISTILL arms, A/B tests, anything needing thousands of cheap calls (the vast.ai of tokens) |
| **GPU experiments** | vast.ai | training/eval when Studios aren't here |
| **Free rotation** | groq (dual-key), ox, nvidia, openrouter x2, cerebras, ollama | fuel_feed channel
| Lane | Key | Role | Ledger |
|---|---|---|---|
| z_ai | ZAI_API_KEY (paid API) | swarm, cache economics | logs/provider_usage.jsonl |
| z_ai4 | ZAI_API_KEY_2 (paid API) | swarm, cache economics | same |
| z_ai2 | ZAI_API_KEY_Pro (coding plan) | swarm carrier default + Pro seat | same — cold-writer |
| z_ai3 | ZAI_API_KEY_Lite (coding plan) | swarm + future lite seat | same — warm-reader |
| groq (dual-key rotation) | GROQ_API_KEY + _2 | free fast lane | same |
| deepseek | DEEPSEEK_API_KEY | copilot BYOK + cheap chewing | same (97% cached lifetime) |
| ox / nvidia / openrouter×2 / cerebras | env | free channel rotation | fuel_feed lane_profile.jsonl |
| ollama (11 models) + saelis-31b staged | local | free local | :11434 |
| ZCode Max seat | harness | THIS seat | rollout transcripts + memory |

## C. State surfaces (what's true)
| Truth | Where | Check |
|---|---|---|
| The signed line | memory/biography/verkle_chain.jsonl | tip root; chain_guard canary |
| Instruction layer | invariant.check_instructions() | epoch-pinned sha |
| Seat mesh | queue/handoff/*/CONVO.md | last turns |
| Cache health | memory/runs/cache_watch.jsonl | probe + ledger floor |
| Lane cadence | memory/runs/fuel_feed/lane_profile.jsonl | per-lane ok-rates |
| Container host | docker_watchdog.log + docker ps | watchdog timestamps |

## D. The modern equivalent (Cloudflare One) — the plan
1. **cloudflared tunnel** in front of A only (Control UI + pruned dashboard): no ports
   published, Access auth, phone-reachable. The one piece needing the operator's CF login.
2. **One aggregated view** (new single page, or a Worker): pulls C's ledgers + B's usage
   into one glance — chain tip, lane hits/misses last hour, seat heartbeats, containers,
   watchdog events. No new recording, only reading what already records.
3. **Retire the clutter**: the legacy dashboard pages that duplicate the aggregate view
   get removed, not maintained. Publish > build.

## D-bis. REMOTE LAYER (operator directive 2026-08-26: "there's a fuckload here")
| Surface | Role | Status |
|---|---|---|
| **Hugging Face** | free stateless storage — Spaces/Datasets/Hub; `mag/hf_space.py` already designed 5 use-cases (research publication, cold vectors, tesuji bench, verkle verification, mycelial coordination); local hub cache warm (saelis-31b + whisper + gpt2) | MAPPED — code exists, HF dir live, deployment unbuilt |
| **Notion seat** | knowledge surface for the operator | API key present; INBOX active (ext-26d39414f1 = died mesh-join task, re-queueable); seat functional |
| **z.ai frontends** (chat/GLM/Smith?) | additional UI surfaces on the accounts we hold | UNMAPPED |
| **Jupyter (kernel)** | interactive compute surface — the notebooks already in-tree (7 first-party) become live fleet organs | PARTIAL (files exist, not wired) |
| **Mermaid** | diagram-as-code grammar — zero .mmd today, diagrams are hand-HTML; mermaid gives git-diffable architecture docs | UNBUILT |
| **Sci-fi corpus** (Desktop preprints + Diamond Age) | the doctrine's own source material — mine it like the sessions | UNMINED |
| **Instruction sets from the chain** | standing waves/BRIEF built FROM verkle knots, deployable to any remote surface | pattern proven locally (spore/standing waves); remote deployment unbuilt |
Doctrine: route fleet state through free remote surfaces — same steal as Cloudflare One. Map before building.

## E. Memory hooks
This file is the registry; the zcode standing wave points here; future sessions read
SURFACES.md before building anything new — if a proposed tool duplicates a row above,
it duplicates, it doesn't get built.
