# Mag v5 — XRPL integration (Mag tools & frameworks)

**Commitment:** `mag-v5-xrpl-001`  
**As-of:** 2026-08-05  
**Status:** **Piped for v5** — read-only tools first; payments L3 human  
**Parents:** `MAG_v5_PIPE.md` · `GSTDCOIN_REPOS_INDEX.md` · `DNA.md` · `CONSTITUTION.md`

**Job:** XRPL ledger literacy and optional payment rails **through Mag agent tools, ingest, and tiers** — not by trusting undeployed gstd-bridge prod.

---

## 0. One line

**Mag reads XRPL honestly via our tools; spends only after L3 human seal — bridge theater stays catalogued, not routed.**

---

## 1. Why XRPL in v5 (and not v3)

| Source | Status | Mag use |
|--------|--------|---------|
| **gstd-bridge** (`mine/raw/gstdcoin/gstd-bridge`) | **Not deployed** — README documents gaps | Spore catalog + protocol reference only |
| **XRPL public network** | Live | Read-only queries via JSON-RPC / WebSocket |
| **Mag constitution** | L3 on irreversible | Payments = human gate, never autorun |

GSTD's cross-chain story includes XRPL (`chains/xrpl.rs`, `wss://xrplcluster.com`). We **learn** from their bridge design; we **wire** through Mag frameworks when ready.

---

## 2. Mag-native integration (not fork bridge)

```text
Agent / Chat intent
    ↓
route.v2 → tier check (T2 public ledger ok · T3 spend)
    ↓
mag/xrpl_tools.py  (or MCP tool seat)
    ↓
XRPL JSON-RPC / WebSocket (public cluster)
    ↓
FILE → ingest row + training event + optional residual leaf
```

**Do not** run gstd-bridge validator node as v5 default — MPC/threshold gaps documented upstream.

---

## 3. v5 phases

### Phase X0 — Spore + read-only (v4)

- [ ] Spore leaves from `gstd-bridge` XRPL module (`src/chains/xrpl.rs`)  
- [ ] Ingest row: XRPL docs, cluster endpoints, trust line concepts  
- [ ] `docs/ref/XRPL_ROUTE_MAP.md` — what Mag may call vs defer  
- [ ] No secrets in repo

### Phase X1 — Query tools (v5)

- [ ] `mag/xrpl_client.py` — thin wrapper: account_info, ledger, tx history (public)  
- [ ] Agent tool: `xrpl_account_lookup`, `xrpl_tx_lookup`  
- [ ] Tier: **T2** public data only in tool results  
- [ ] Tests with mocked RPC (no mainnet keys in CI)

### Phase X2 — Mag MCP / switchboard seat (v5)

- [ ] Optional MCP tool provider `mag-xrpl-tools` (stdio)  
- [ ] Switchboard peer: `xrpl-read` (local bind)  
- [ ] Context-pack chip: "XRPL: read-only seat"  
- [ ] Cost ledger: RPC call counts (no spend)

### Phase X3 — Payment templates (v5+, L3 only)

- [ ] **Human-signed** payment intent file (`memory/xrpl/intents/{id}.json`)  
- [ ] Tool: `xrpl_prepare_payment` → draft only, never auto-submit  
- [ ] L3 CLI: `main.py xrpl-submit --intent id` after operator confirm  
- [ ] Wallet seed in vault only (`XRPL_SEED` / hardware — never git)  
- [ ] Training event on every submit: `pattern: xrpl_payment`

### Phase X4 — GSTD bridge alignment (when upstream ships)

- [ ] Re-probe gstd-bridge deployment status  
- [ ] Update route map — enable only if upstream gaps closed  
- [ ] Mag route: TON/XRPL via GSTD **or** direct XRPL — seat_score picks

---

## 4. Framework hooks (use what we have)

| Mag framework | XRPL use |
|---------------|----------|
| **Ingest registry** | Tag XRPL docs, endpoint URLs, spores |
| **Idea graph** | `entity` nodes for accounts, `claim` for bridge status |
| **Tiers T0–T3** | Read T2; spend T3 |
| **Agent CLI tools** | Query + prepare payment draft |
| **Switchboard** | Optional `xrpl-read` peer |
| **Steward** | `steward-xrpl-digest` — weekly public network sanity |
| **Promote gate** | Enable payment tools in `configs/lanes.yaml` |
| **Training export** | Redacted `xrpl_query` episodes (no addresses if operator flags) |

---

## 5. Config sketch (v5 — not committed until implement)

```yaml
# configs/xrpl.yaml (v5)
enabled: false          # promote to true
mode: read_only         # read_only | payment_l3
rpc_url: https://s1.ripple.com:51234
ws_url: wss://xrplcluster.com
network: mainnet        # or testnet for dev
tier_max_read: T2
tier_payment: T3
require_intent_file: true
```

Env (vault only): `XRPL_SEED`, optional `XRPL_ACCOUNT`

---

## 6. Routing doctrine

| Action | Tier | Auto? |
|--------|------|-------|
| Ledger / account read | T2 | Yes (agent tool) |
| TX history (public) | T2 | Yes |
| Prepare payment draft | T3 prep | Draft only |
| Sign + submit TX | T3 | **Never** — human CLI |
| Trust gstd-bridge withdraw | — | **Defer** until upstream deployed |

---

## 7. v3/v4 prerequisites

| Prereq | Why |
|--------|-----|
| Agent tool loop stable (CHAT-6) | XRPL is a tool seat |
| Tier refuse tested | No accidental mainnet spend |
| Spore catalog (v4) | Bridge honesty filed before wire |
| Cost ledger | Audit trail for any paid RPC provider |

---

## 8. Links

- `reference/gstdcoin/gstd-bridge/src/chains/xrpl.rs` — upstream watcher reference  
- `reference/gstdcoin/gstd-bridge/README.md` — deployment honesty  
- `docs/ref/MAG_v5_GSTD_FOREST.md` — TON/GSTD track (separate from direct XRPL)  
- `docs/ref/GSTDCOIN_REPOS_INDEX.md` — gstd-bridge deferred note

---

*v5-XRPL: our frameworks, our tiers, our promote gate — learn from GSTD bridge, don't inherit their undeployed risk.*
