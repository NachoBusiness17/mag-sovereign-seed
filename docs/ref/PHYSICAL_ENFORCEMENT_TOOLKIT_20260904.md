# PHYSICAL ENFORCEMENT TOOLKIT — structural-law primitives, stolen from the field (2026-09-04)

Companion to watch/ARCHITECTURE_IS_LAW_20260904.md. Source: physical-computing research
pass (14 searches, 2024-26 state verified, sources in the research log). Each entry:
mechanism → violation made impossible → fleet lesson.

## THE TEN PRIMITIVES

1. **Content-addressed storage** (git/Nix/IPFS): the name IS the commitment — readers
   recompute the hash, substitution fails at read time with no auditor. *Fleet:* extend
   claim-CAS physics to inbox messages + receipts — a card citing sha256(content)
   cannot be answered against different content.
2. **Append-only + published checkpoints** (Certificate Transparency's real trick):
   each entry commits to all prior; a signed root is republished to WITNESSES on a
   second medium. *Fleet:* one checkpoint/day (root hash + row count) to git commit or
   the operator's X — one line makes local rewriting publicly falsifiable for free.
   Counter-lesson: QLDB died July 2025 — buy patterns, not products.
3. **Monotonic epoch counters** (TPM 2.0's shape, portable to files): increment-only
   counters gate authority — a scheduler whose claim doesn't cite the current epoch is
   a zombie STRUCTURALLY, on its face. *Fleet:* one append-only epoch file gates all
   scheduler claims. Kills the tick-class forever.
4. **Ratchet protocols** (Signal): every message derives from the last; old keys
   deleted — compromise has a half-life. *Fleet:* inbox claims consumed on read
   (rename = replay physically impossible); seat creds derived from the last chain
   knot — a token leaked Tuesday can't sign Thursday's rows.
5. **Stigmergy** (medium as coordinator): no agent messages another; markers in a
   shared medium, TTL decay, no coordinator process to kill. *Fleet:* the file IS the
   lock (atomic create/rename = O_EXCL physics); pheromone TTL handles staleness;
   one-scheduler = stigmergy with one writable trail.
6. **Landauer / no-silent-deletion**: erasure costs energy and leaves entropy —
   deletion must be an expensive, VISIBLE act. *Fleet:* never rm a chain row — a
   delete IS a tombstone-append citing what and why. The one physics-grade rule a
   files fleet can honor completely.
7. **Capability systems** (seL4/HACMS: red teams owned the camera, could NOT cross the
   cap boundary): authority = possession of unforgeable references, no ambient
   authority. *Fleet:* MCP whitelists are capability-LITE; full caps = path-as-capability
   (unguessable secret-bearing dir names ≈ unforgeable), every tool path walked from a
   held cap; revocation = cap deletion.
8. **Fail-physical records** (S3 Object Lock COMPLIANCE mode — not even root can
   shorten retention; canarytokens — reading the bait leaks the attacker; dead-man
   switches — silence is the trigger; git reflog). *Fleet:* canary files in inboxes;
   a dead-man heartbeat row the watchdog must advance (staleness becomes structural);
   trails never GC'd, only tombstoned. NOTE: Thinkst now ships an MCP-server
   canarytoken — the industry just arrived at our threat model.
9. **Time as physics** (RFC 3161 / OpenTimestamps-batch-to-bitcoin): the deep past is
   scarce — you cannot forge a 2010 commitment in 2026 without redoing global hashrate.
   *Fleet:* THE CHEAPEST UPGRADE IN THE REPORT — anchor one hash/day (the day's chain
   root) via OpenTimestamps. Free, one batched tx. "The operator said GO on Sep 3"
   becomes checkable against physics.
10. **Self-evident violation** (checks cheaper than attacks): Merkle proofs O(log n),
    random spot-checks escalate only on mismatch (risk-limiting audits; Filecoin
    WindowPoSt: daily random challenges, missed windows = penalties). *Fleet:* a nightly
    free-lane verifier samples k random chain rows, recomputes knots + CAS tokens,
    spot-checks inbox claims vs artifacts — one-builds-one-verifies, made mechanical.
    Lying requires perfect fabrication against every future sample; checking costs pennies.

## THE COMMON SHAPE
Make the honest path the path of least resistance and the dishonest path require
continuous, visible work. Four load-bearing primitives across every deployment:
(a) published checkpoints to a second medium; (b) monotonic epoch counters gating
authority; (c) delete-as-append; (d) random spot-check verification.

## COST-RANKED ADOPTION ORDER (files fleet)
1. Daily OpenTimestamps anchor — free, one tx. **BUILD FIRST.**
2. Nightly verifier spot-check loop — free lane.
3. Epoch-counter file gating scheduler claims — file physics; zombies die structurally.
4. Path-as-capability inboxes — unguessable dirs.
5. Tombstone-only deletion + never-GC trails.
6. Canary files in inboxes.
7. Compliance-locked backup tier — the only one that costs money.

*Full sourced report in the research gopher's log; this is the persistent card. Feeds
Builder's inbox as the structural-law build queue.*
