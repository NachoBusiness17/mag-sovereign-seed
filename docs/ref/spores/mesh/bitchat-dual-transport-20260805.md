# FEATURE — Bitchat dual-transport MessageRouter

**Commitment:** `feat-bitchat-dual-transport-001`  
**Source:** `mine/raw/mesh_comm/permissionlesstech/bitchat` · WHITEPAPER.md  
**Org:** [github.com/permissionlesstech](https://github.com/permissionlesstech) — **3/3 public repos cloned**  
**Research:** field-steal 20260805T125129Z · research-pack 20260805T125145Z  
**Parent:** `docs/templates/FEATURE_COMPOSE.md`

## Org map (complete)

| Repo | Platform | Mag steal focus |
|------|----------|-----------------|
| [bitchat](https://github.com/permissionlesstech/bitchat) | iOS / macOS | Primary — `MessageRouter`, WHITEPAPER, Noise mesh sessions |
| [bitchat-android](https://github.com/permissionlesstech/bitchat-android) | Android | Cross-platform binary protocol; `UnifiedMeshService`; Wi-Fi Aware; Tor (Arti) |
| [georelays](https://github.com/permissionlesstech/georelays) | infra / Python | Nostr relay crawl + geolocation; BitChat kind-20000 compatibility filter |

**Product:** decentralized P2P messaging — BLE mesh offline + Nostr internet fallback. No accounts, no phone numbers, no central servers. Public domain (iOS) / GPL (Android).

**Operator note:** org has faced takedown pressure — verify builds from source (`docs/VERIFYING-A-BUILD.md` upstream).

## Identify

| Field | Value |
|-------|-------|
| name | dual_transport_router |
| foreign form | `MessageRouter` prefers BLE mesh → Nostr → courier store-and-forward |
| invariant | IF single-transport-only THEN partitioned/offline users lose coordination fidelity |

## Evaluate

| | |
|--|--|
| same | Mag already has LAN `:8765` + hub fallback (DeepSeek/GSTD) — same *shape* |
| differ | Bitchat is radio mesh; Mag is disk + switchboard — steal **routing policy**, not BLE stack |
| differ | Android adds Wi-Fi Aware + Tor — Mag may steal **multi-local-transport pick**, not Arti dep |
| differ | Georelays = hub topology research only — Nostr relays are not Mag DNA |
| capture risk | low if contracts only |
| local cost | $0 — conductor overlay research |

## Steal

**Contract:** Ordered fallback chain with explicit probe at each hop:

```text
live_local → mesh_transport (v5 opt-in) → hub_seat (GSTD/API) → defer + FILE
```

**Direct message routing (from README):**

1. Bluetooth first (Noise session, lowest latency)
2. Nostr fallback (recipient pubkey, BitChat private envelope — proprietary, not NIP-17/44/59)
3. Smart queuing when neither path available

**Android extras (bitchat-android):**

| Component | Mag analog (draft) |
|-----------|-------------------|
| `UnifiedMeshService` | conductor picks among local transports (LAN, BLE, Wi-Fi Aware) |
| TTL + dedup + fragmentation | switchboard loop_audit · steer_drop — no broadcast storms |
| `MeshForegroundService` | willing L3 enroll — operator opts device into relay, not Mag default |
| Tor (Arti) | T2 research seat — not default Mag path |

**Georelays (infra only):**

| Stage | Mag relevance |
|-------|---------------|
| Relay discovery BFS | hub seat health probe pattern (GSTD/API fallback) |
| kind-20000 filter | **reject** — BitChat-specific Nostr; not Mag interoperable |
| Geo lookup | research only — informs hub latency routing, not zeitgeist |

**Maps to:** `mag/conductor.py` phase + `configs/seat_playbook.yaml` transport_chain (draft).

## Enhance (Mag invariants)

- T0/T1 never on mesh without operator L3 enroll  
- pigeonhole `steer_drop` for directed traffic; no broadcast flood (Bitchat TTL/dedup → loop_audit pattern)  
- Artifact > transcript — courier = trail on disk, not chat scroll  
- Geohash location channels → **reject** for Mag ops (not a geo chat app)

## Compose

Reinforces: switchboard tier drops · GSTD as hub seat · ILAP routing matrix · Bridgefy transmission enum (mesh hop vs broadcast).

**Cancels failure mode:** “smart model picks transport by vibes” → conductor declares chain.

## Measure

- routing_smoke green for scut/local goals  
- eval-ilap-002 research_dive filed  
- overlap: **wire** — extend conductor, no new module  

## Promote

**Candidate:** playbook line + `training_patterns.yaml` `transport_fallback` (v4 draft).  
**Not auto-promote.**
