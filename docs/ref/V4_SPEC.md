# V4 SPEC — self-healing procurement-and-serve (fused 2026-08-28)

Four-family council, one canonical brief (SYSTEM_BRIEF_V4.md): grok (systems),
codex (product), deepseek (governor), zai (economics). Full reviews:
memory/runs/v4_council/. Codex's V4 one-liner, adopted as the thesis:
**"a self-healing procurement-and-serve system that turns market noise into a
small number of durable, inspectable decisions."**

## Architecture (converged by all four families)

ONE loop, three-to-four organs, two owners.

- **Governor + sole mutator**: `mag/compute_reconcile.py` — every 5 min +
  on-demand. measure() reads: show_instances(), wedge/success ledger, credit,
  fuel_feed pending work. reconcile() owns exactly three actions:
  BUY / RESIZE / REAP. No other process mutates instances (grok: tonight's
  hunters had check-then-act races and an unlocked blocklist).
- **Organs (thin, propose-only)**: sizer = PLAN · seeker + blade_buyer =
  ACQUIRE (behind the governor's lock, one in-flight ask, budget fail-closed)
  · boot_watcher = HEALTH · fuel_feed = WORK (an unused READY box is a failed
  reconcile) · **SPEND ledger = first-class organ** (zai): every instance
  start/cost/reap appends a row; the covenant is a ledger query, not a hope.
- **Owners**: Operator owns covenant constants ($5 cap, credit floor) as
  config; seats own work routing. The Operator reads receipts, never pokes
  organs. The receipt is phone-first (codex): numbers, one decision, one
  next action.

## Readiness law (converged: codex + grok + elder)

READY means one thing: a **deterministic smoke inference through the
operator's real path returned and was hash-persisted**. Phase names are
hints, never success. Model sha256 verified against the registry at the same
moment (elder). The watcher's old substring match ("health-wait") would have
false-READIED — fixed live before it cost money.

## The measurement schema (union, deduped — every boot/blade logs all)

| metric | kill/threshold |
|---|---|
| ask_to_running_s | >300s destroy; feeds per-machine boot_success_rate |
| time_to_ready + pull MB/s | brain >70min kill; builds the host-speed table |
| disk_delta_kb per probe | never-grew ×8 / flat ×4 → kill (live) |
| t_first_token_s | brain 70min / blade 15min → kill |
| tok_s on a FIXED real prompt | ≤ home qwen-desk baseline → do not scale |
| cost_per_1k_tokens incl. failed attempts | brain ≤$0.01, blade ≤$0.02 → else kill tier |
| $/healthy-serving-hour (all spend ÷ healthy uptime) | brain >$0.50, blade >$0.20 → kill tier |
| utilization fraction | <10% over 30min → reap (idle-burn, zai) |
| model_sha256_match | false → destroy + blacklist |
| smoke_success_rate | <100% on the accepted path → rejection |

## Blacklist → lemon throttle (converged: elder + codex + grok)

Two tiers: soft (retry after 6h) and hard (3 distinct failures / 24h).
Reachability whitelist is written ONLY at verified READY. Hosts acquire a
reliability score that decays on dark events. Effective-$/useful-hour (desk
probe pattern) feeds back so slow-not-dark hosts stop being re-bought.

## THE $5 EXPERIMENT (pre-registered — thresholds locked before spend)

Sequencing adopted from grok: **blade first** (the brain test runs only after
HEALTH has written at least one success ledger row).

1. blade_buyer rents ONE box ≤$0.12/hr (covenant: MAX_BLADES=1, floor $39).
2. contract v2.2 boots qwen3:8b; watcher rails on; smoke gate before READY.
3. Drive **45 min of real fleet prompts** (fuel_feed item or the steering
   prompt set — dog food, never /health).
4. Auto-reap at 4h. Compute $/1M tokens, tok/s, operator touches.

**Proves** (scale authorized): continuous serve for the window, stable tok/s
≥ home qwen-desk baseline, known $/1k below the quota.py API price, zero
manual repair.
**Kills** (thesis documented, budget pivots): proxy-dark again (two $0.05
3060s already died), erratic or sub-baseline throughput, or any manual repair
beyond expected contract steps.

## Preserved dissents (testable claims, not averaged)

- **Elder**: the 331MB wedge was an aria2c connection-pool failure, not speed
  — real fix is a pre-download checksum handshake from the registry.
  [inference from scar, Unproven]
- **Grok**: desk sleep / hunter death is the dominant remaining spend leak —
  a healthy box bills with nobody watching. Test: leave a box up, kill the
  hunter, verify reconcile still reaps. [Unproven]
- **Codex**: phone-first daily receipt is the ONLY operator surface; a second
  control center would become a place to chase status. [policy]
- **Zai**: attention-per-healthy-boot-hour is V4's true ROI metric — operator
  attention, not silicon, is the binding constraint. [no receipt logs it yet]

## Status

Stage-1 rails live tonight: contract v2.2, boot_watcher (paths + exact-READY
+ success ledger — grok's path-wrong bug fixed before first real run),
seeker closed loop + covenant floor, blade buyer caps, sizer + registry,
health-filtered asks. Next build: compute_reconcile as governor over the
organs, SPEND ledger wiring, the $5 experiment run for real.

## V4 ADDENDUM (2026-08-28, operator rulings)

1. **ELDER OWNS THE DIRECTION**: the elder prevents-and-presents the castles
   in the sky; the seats build the foundations under them. Concretely: the
   elder judges lineage-audit output, owns V4 design arbitration, and its
   anchored consults gate new subsystem designs (self-steal consult = the
   precedent). Seats propose; the elder disposes on design; the governor
   disposes on state.
2. **HUNTER POPULATION (genetic)**: duplication between hunters is not always
   a bug to dedupe — it can be breeding stock. V4.x: N hunter configs (deal
   cards, gates, quants) compete concurrently within budget caps; fitness =
   booted-and-served tok/s per dollar from the ledger; reconcile selects and
   breeds; losers die by their own rails. Dedupe applies to MUTATORS only —
   exploration wants a population.
