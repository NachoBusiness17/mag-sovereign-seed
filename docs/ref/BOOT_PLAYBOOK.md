# BOOT PLAYBOOK — wedge-proof brain-box boots (2026-08-28)

Four-witness deep-steal (operator: "how did RenderMan do it"): dossiers in
`state/vast/research/` — BOOT_WEDGE_VAST (vast-specific), BOOT_WEDGE_GENERAL
(tooling + warm pool), DISTCOM_PLAYBOOK (Slurm/K8s/Ray/BOINC),
RENDER_FARM_PLAYBOOK (Tractor/Deadline/OpenCue). This file is the synthesis:
what is LIVE, what is STAGE-2, and the doctrine.

## Doctrine (the one-liner)

Render farms stage the expensive thing ONCE and retry the cheap thing
FOREVER. The unit of loss is a frame, never the scene. We had it inverted:
every box re-pulled the 120GB scene, so every wedge cost the whole pull.

## LIVE (landed 2026-08-28)

| Rail | Instrument | Receipt it answers |
|---|---|---|
| Stall-proof downloader | `box_contract.sh` v2.2: aria2c 8-conn or curl `--speed-limit 102400 --speed-time 60 --retry 20 --retry-all-errors -C -`; per-shard HEAD size verify; one retry then exit | 331MB/90min silent curl (machine 139376) |
| Off-box watcher, kill in minutes | `boot_watcher.py`: du/phase probes every 45s via ssh6; rails = ssh-dark ×3, flat-after-growth ×4, never-grew ×8, 45-min cap; auto-destroy + blacklist + `wedge_ledger.jsonl` | same, plus "watch verbosely like the deepseek pool" |
| Closed seeker loop | `seeker.py`: proxy-gate pass ≠ success — every catch spawns boot_watcher; MISSION COMPLETE only on verified healthy boot; wedge-kill resumes hunt | gate-passed-then-wedged box billed 90 min |
| Ask-time host health | seeker prefers inet_down ≥500 Mb/s + disk_bw ≥1000 MB/s, logs net/disk fields per ask into the TARGET line | 20 Mbps host masquerading as a stall |
| Dark-host memory | proxy-dark and dead-pull machines permanently blocked (`blocked_machines.json`) | 122589 asked 7×, all dark |

## STAGE-2 (queued, needs one healthy host first)

1. **Pull once — volume**: on a reachable whitelist host: `vastai create volume`
   (200GB), rent GPU with `--link-volume --mount-path /root/brain/models`,
   contract skips download when all 4 shards hash-verify. Volume ≈ $0.50–0.80/day;
   `clone volume` to a new host BEFORE losing the old one (locality is real —
   volumes are per-datacenter, not region-portable).
2. **Shard atoms on durable storage** (render-farm bone): killed pull must leave
   3/4 shards valid somewhere durable; next box RESUMES shard 3, not shard 1.
   Follows automatically from the volume; before that, S3/B2 park of a verified
   pull set is the origin-portable version (~$3 ingress cap per vast witness).
3. **Stop-not-destroy after READY**: stop (don't destroy) keeps the disk;
   idempotent onstart no-ops when shards hash-verify. `scheduling` >5 min on
   start → GPUs stolen → destroy and fall back. Old law stands: stopped >24h
   with no next-use plan = destroy.
4. **Lemon throttle** (render-farm refinement): blacklist entries become
   strike-counts with expiry windows (max_fails_allowed / triesDifferentClient),
   not forever-dark integers — a 3am network flake shouldn't ban a host at noon.
5. **Kill-before-rebook**: when asks go parallel someday, destroy confirmation
   must precede the next contract (OpenCue kill_running_frame_before_release) —
   single-flight today makes this safe; parallelize only after this lands.

## Source receipts

- 11 wedged boxes ≈ $3.40 tuition + machine 139376 ($0.55, 331MB/260GB @ 90 min)
- `wedge_ledger.jsonl` = every future kill with machine, reason, bytes, minutes
- Dossiers: `state/vast/research/BOOT_WEDGE_{VAST,GENERAL}.md`,
  `DISTCOM_PLAYBOOK.md`, `RENDER_FARM_PLAYBOOK.md`
