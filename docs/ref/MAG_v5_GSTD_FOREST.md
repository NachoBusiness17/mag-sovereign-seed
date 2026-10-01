# Mag v5 — GSTD forest (pipe)

**Commitment:** `mag-v5-gstd-forest-001`  
**As-of:** 2026-08-05  
**Status:** **Piped for v5** — spore catalog + local clones now; test + implement after v4 gates  
**Parents:** `MAG_v5_PIPE.md` · `GSTDCOIN_REPOS_INDEX.md` · `MAG_BEHAVIORAL_COMPOUNDING.md` · `DNA.md`

**Job:** Keep [gstdcoin](https://github.com/gstdcoin) in the product pipe — reverse-engineer, catalog spores, probe MIT distributed compute, wire Mag routing — **without** blocking v3 substrate or v4 mold.

---

## 0. One line

**v5 = Mag knows the GSTD stack better than their READMEs and routes through it when local janitors lose.**

---

## 1. Why v5 (not v3/v4)

| Version | Job | GSTD role |
|---------|-----|-----------|
| **v3** | Substrate — orchestrator, seats, pack, Office | Index + clones only (reference) |
| **v4** | Mold — conductor, steward, eval, loop discipline | Spore catalog + route map draft |
| **v5** | Forest seat — optional DePIN inference + task economy | **Test, probe, implement** |

**Do not implement GSTD seats until:**

- v2 merge gate closed on home PC  
- v4 conductor + steward loops stable (plan theater ↓, pack-first true)  
- Switchboard peer model exists for optional remote seats  
- Operator vault holds `GSTD_*` keys (never in git)

---

## 2. Three horizons (same pipe)

```text
Now (v3/v4)     Encounter → recognize → catalog spore
Mid (v5 test)   Probe live API · shadow worker loop · route map
Later (v5+)     Mag-native parity · optional gstdbot edge · training export
```

---

## 3. Repos & Mag slots (frozen index)

Full table: `docs/ref/GSTDCOIN_REPOS_INDEX.md`

| Repo | License | v5 test focus | Mag slot |
|------|---------|---------------|----------|
| **ai** | MIT | Pages API, chat completions, KV node registry | L1 DePIN inference when nodes online |
| **A2A** | MIT | Worker poll/submit, FastMCP tools | Switchboard peer / task economy |
| **gstdbot** | Apache 2.0 | Swarm poll, P2P mesh, Ollama edge | Optional edge node (earn/serve) |
| **contracts** | MIT | Settlement path literacy | Read-only; no keys in repo |
| **gstd-bridge** | MIT | **Skip** — not deployed | Reference only |
| **web** | MIT | — | Public face; no harness wire |

**Platform base (prod):** `https://app.gstdtoken.com/api/v1`

---

## 4. Spore catalog (start now, v4 steward)

File incredible findings as spores — training prep for future agents.

| Spore kind | Example |
|------------|---------|
| `integration_hook` | Dual poll: `tasks/poll` (gstdbot) vs `tasks/worker/pending` (A2A) |
| `protocol_truth` | Prod hub = `ai/frontend` Pages API, not Go backend |
| `compute_seat` | MIT distributed inference + sovereign worker loop |
| `substitution_point` | Groq fallback when zero nodes online |
| `deferred_risk` | gstd-bridge README gaps — do not route |

**Target soil (Mag-native, not `reference/`):**

```text
mine/raw/gstdcoin/           ← clones
mine/curated/gstd/spores/    ← REF_LEAF spores
memory/ingest/registry.jsonl ← tagged rows
docs/ref/GSTD_ROUTE_MAP.md   ← frozen routing law (v4 draft → v5 probe)
```

**Janitor jobs (v4):** `steward-spore` · `steward-gstd-digest` (planned on v4 steward wave)

---

## 5. v5 test plan (phased)

### Phase T0 — Read-only shadow (no wallet)

- [ ] Inventory API routes from `ai/frontend/src/pages/api/v1/`
- [ ] Inventory MCP tools: `A2A/tools/main.py` + `ai/gstd-mcp-server/index.ts`
- [ ] Probe: `GET /api/v1/health`, `GET /api/v1/stats`
- [ ] File `GSTD_ROUTE_MAP.md` with live vs documented truth
- [ ] Spore leaves for every mismatch

### Phase T1 — Worker shadow (test wallet, no earn dependency)

- [ ] Register test node via A2A `gstd_client.py` patterns
- [ ] Heartbeat loop (10-min TTL — document stale behavior)
- [ ] Poll → submit dry run on trivial task
- [ ] Log training events: `route_decision`, `gstd_probe`

### Phase T2 — Mag routing seat

- [ ] Switchboard lane: `gstd-inference` (L1, after local Ollama fail or explicit `[gstd]`)
- [ ] `POST /api/v1/chat/completions` from Mag agent-cli path
- [ ] Cost ledger entry per `MAG_V4_CONDUCTOR_LOOP_DRAFT.md` § cost_ledger
- [ ] Dashboard/chat: one-line seat status (“GSTD: N nodes, last probe …”)

### Phase T3 — Optional edge (operator choice)

- [ ] Run gstdbot locally; verify swarm poll + Ollama
- [ ] P2P bootstrap from `GET /api/v1/nodes/peers` (document only unless needed)
- [ ] **Do not** wire gstd-bridge

---

## 6. v5 implement targets (after tests green)

| ID | Deliverable | Subsystem |
|----|-------------|-----------|
| v5-G001 | `GSTD_ROUTE_MAP.md` + ingest rows | steward + ingest |
| v5-G002 | `mag/gstd_seat.py` — probe + route helper | switchboard + router |
| v5-G003 | MCP wire (A2A and/or ai MCP) behind config flag | agent-cli |
| v5-G004 | `configs/lanes.yaml` gstd lane + tier gates | seat economics |
| v5-G005 | Spore export slice for training (`exportable` events) | training spec |
| v5-G006 | Chat preflight chip: GSTD seat availability | dashboard (Cursor target) |

---

## 7. Routing doctrine (frozen intent)

```text
T0 local Ollama (janitor) → always first
T1 OpenRouter/DeepSeek     → cheap remote draft
T1-cap GSTD DePIN          → when probe says nodes online + goal allows
L2 Grok/Cursor             → scarce; [priority] + pack
L3 human                   → wallet, deploy, promote
```

**Mag wins when:** it knows *not* to call GSTD (stale nodes, bridge theater, wrong MCP server).

---

## 8. Training future (v5+)

- Curated spores + exportable `gstd_*` training events → fine-tune corpus  
- GSTD `A2A/finetune_worker.py` = optional **compute** for LoRA; Mag catalog = **curriculum**  
- No auto-train without promote gate (`MAG_TRAINING_DATA_SPEC.md`)

---

## 9. Gates checklist (before v5 implement)

| Gate | Check |
|------|-------|
| v2 merged | PR #8–#11 on home `main` |
| v4 steward | scope cards + patterns digest daily |
| Switchboard | peer seat model documented |
| Secrets | `GSTD_API_KEY`, wallet mnemonic in vault only |
| Spores | ≥10 filed GSTD spores in `mine/curated/gstd/` |
| Route map | T0 probe complete |

---

## 10. Links

| Doc | Role |
|-----|------|
| `docs/ref/GSTDCOIN_REPOS_INDEX.md` | Repo map + refresh scripts |
| `docs/ref/MAG_BEHAVIORAL_COMPOUNDING.md` | Spore → pattern → habit |
| `docs/ref/MAG_V4_CONDUCTOR_LOOP_DRAFT.md` | Seat economics + cost ledger |
| `reference/gstdcoin/` or `mine/raw/gstdcoin/` | Local clones (operator soil) |

---

*Status: **in pipe for v5**. v3/v4 may catalog and probe read-only; implementation waits on gates §9.*
