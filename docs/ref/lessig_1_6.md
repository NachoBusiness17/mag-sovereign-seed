# Lessig 1-6 enforcement — 2026-07-27

**Commitment:** `lessig-1-6-portable-bag-001`  
**Chord:** `chord-mag-prices-enforced-not-mapped-001`

Lessig modalities applied to disentangled moves 1-6.

## Law (rules that bind without asking)

| Move | Law |
|------|-----|
| 1 Trail real goals | Open run for multi-step work; close with progress.md |
| 2 Noise cut | Bare `Model signal:` auto-rejected at scout; bulk clean done |
| 3 Seat purity | Dispatch refuses wrong seat while run open |
| 4 Process vs case | Process=playbook; case=residual; mid-goal=trail |
| 5 Grok scarce | Scut/status/improve = Mag; Grok only [priority]+pack |
| 6 Portable bag | residual+tip+pins+configs only; see memory/portable_bags/ |

## Norms (what we do when no one watches)

- No "just this remote" mid-run.
- No promote of model seats without tesuji leaf + human.
- No new analysis leaf before a dirty product hour / real trail.
- Pin and bag are move-house kits, not trophies.

## Markets (prices)

- Tokens price intelligence (quota, pack-first).
- Attention is the scarce good; Grok is expensive.
- Open weights / harness fashion is not payment for DNA.

## Architecture (code that makes the above hard to violate)

- `mag/dispatch.py` seat gate
- `mag/improve.py` bare Model signal status=rejected
- `mag/run_trail.py` progress.md + seat lock
- `mag/run_trail.py` **base freeze + drift FILE** (`base_id` on agent_probe; mismatch rejected)
- `mag/context_pack.py` `--agent` preamble surfaces `base_id`
- `memory/portable_bags/` cold bag copy
- `max_auto_pull_gb: 0`

### Base + drift (stateless seats, 2026-08-01)

| Law | Architecture |
|-----|----------------|
| Multi-agent work opens a run | `trail start` freezes `run.base` |
| Seats do not invent shared state | pack `--agent` + trail cores only |
| Drift cites the base graph | `file_agent_core` / append `agent_probe` stamp + match `base_id` |
| Fold / time-travel compare | `trail drifts` clusters by locus under one base_id |

## Bag location

See `memory/portable_bags/LATEST.txt`
