# FEATURE — Briar sync without central server

**Commitment:** `feat-briar-sync-noserver-001`  
**Source:** `mine/raw/mesh_comm/briar/briar` · briarproject.org / README  
**Parent:** `docs/templates/FEATURE_COMPOSE.md` · `memory_verkle_map.md`

## Identify

| Field | Value |
|-------|-------|
| name | sync_without_central_server |
| foreign form | P2P sync over Tor / BT / Wi-Fi; optional [mailbox](https://github.com/briar/briar-mailbox) when device offline |
| upstream | **GitLab primary:** [code.briarproject.org/briar/briar](https://code.briarproject.org/briar/briar) · GitHub mirror only |
| local clone | `mine/raw/mesh_comm/briar/briar` @ 1.5.19 (`b46d008`) |
| license | GPL-3.0 |
| invariant | IF central server required THEN capture + lights-out failure |

## Evaluate

| | |
|--|--|
| same | Mag beads + residual + sync-when-path-exists = zeitgeist already |
| differ | Briar is messaging product; Mag is office harness |
| overlap | **~90%** doctrine — document alignment, no new code |

**Transport chain (from README):**

```text
Internet up   → Tor sync (surveillance-resistant)
Internet down → Bluetooth or Wi-Fi direct sync
Offline peer  → optional Briar Mailbox (willing relay — separate repo)
```

**Mag steal:** ordered fallback shape matches ILAP `transport_chain` draft (local → mesh → hub → defer).

## Enhance

Mailbox = **L3 enroll** sidecar — not Mag DNA. See `MAG_v5_MESH_FOREST.md`.

## Compose

Confirms fourth forest house is **transport seat**, not second DNA store.

## Measure

**Verdict: document only** — add cross-link in `memory_verkle_map.md` (done via spore catalog).

## Promote

No code. ILAP overlap row: defer Briar implement.
