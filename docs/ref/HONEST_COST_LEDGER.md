# HONEST COST LEDGER — what actually costs what (2026-08-28)

Opened by the operator: "$0.28 for 6M tokens — what are we doing here? We need to
start having an honest conversation about what actually costs what."
Source data: DeepSeek usage CSVs 2026-08-28 (cost + amount), tonight's kill/boot
receipts. Every number below is read from data unless marked [est] or [unproven].

## THE HEADLINE: the 28 cents is the system working, not broken
- DeepSeek today: **$0.28 total** — 705 requests, 6.04M tokens, 24h continuous.
- **91% of input tokens were cache hits** (e.g. hour-00: 275K hit vs 23K miss).
  Cache discipline is why 6M tokens cost a quarter, not ~$1.40 (miss-rate 4x).
- Steady ~30 req/hr all day = the swarm watch cadence (heartbeat + drains).
- Run-rate: **~$8.50/month** buys an always-on flash-lane witness. This is the
  cheapest organ the fleet runs. The honest question is not "why 28 cents" but
  "is the watch buying anything" — that's a value audit (row 2 below), separate
  from cost.

## UNIT ECONOMICS BY LANE (per unit of work)
| Lane | Cost | What one unit buys |
|---|---|---|
| DeepSeek v4-flash (Swarm key) | ~$0.0004/req, ~$0.05/M tok effective | grind: drains, digests, watch, forensics. 91% cache hit at ~30 req/hr |
| DeepSeek v4-pro | $0.001-0.002/req [3 pings today, $0.003 total] | rare judgment escalations — used 3x today, correctly tiny |
| z.ai 4.7-flash / 4.5-flash | $0 (free lanes, cached, by-model pinned) | bulk drains + driver coordination; caps are quota not dollars |
| Groq | $0 within 100 calls/100K tok per day | overflow free lane only |
| Coding plans (Max + Lite) | flat monthly; the scarce unit is QUOTA | judgment beats ONLY (Lite = this seat since 08-28, control mechanism) |
| Vast cheap blade | $0.09-0.15/hr, 4h lifetime cap -> ~$0.40-0.60/blade | burst muscle: GPU play, Saelis, parallel drains; ~1-in-N dark lottery |
| Local desk GPU | $0 — and unwired (RX 5600 XT runs CPU-only ollama) | nothing yet; ROCm experiment pending |
| Rocinante (Oct 27) | capital, then ~$0 marginal | the fix that makes local the default grind lane |

## WHAT WE ACTUALLY BURNED ON WASTE (tonight's honest kill list)
- Dark 3090 "sancho-diag": billed $0.160/hr while unreachable [~19h dark, ~$3
  est] — killed 08-28 night. THE leak. The meter watched nothing.
- Watch/companion heartbeat dead >24h (bargain loop, no scheduler entry) —
  found by codex forensics; restart one-liner staged, not yet fired.
- Codex spawned host-side duplicates (ghost :9000 + mirror dashboard) outside
  Docker — both KILLED 08-28 night; container stack owns 9000/8000/8765
  (verified: docker backend holds all three). 4 stdio mcp_server processes on
  host are per-seat spawns, benign, not port duplicates.
- A4000 blade 49072033: bought $0.092/hr, went proxy-dark, destroyed in 2.3
  min. Total exposure $0.0035. Fail-fast cost of doing business, absorbed by
  the organ — that 2-minute kill is what keeps the lottery from bleeding.

## THE HONEST CONVERSATION, STATED
1. Grind is essentially free: deepseek flash ~$9/mo + z.ai/groq free lanes
   carry everything dumb. Never pay premium for it.
2. Judgment is the only expensive thing: flat-plan quota. Lite seat exists
   precisely to cap this. One beat/day until Sep 1 reset.
3. Muscle is rented by the hour and fails often: vast blades at ~$0.10/hr,
   dark-lottery absorbed by blade_buyer (proof: tonight's 2.3-min kill).
4. Waste wears one costume again: unwatched meters and duplicate organs.
   Covenant floor + blade_buyer + the lattice are the enforcement — organs
   died because nobody restarted them. The watch needs a watch (the heartbeat
   restart is still the one open fix).
5. Rocinante ends the rental question for the grind; until then vast blades
   are the honest price of GPU burst.


## VAST TRUE COST — invoice #170099260803260902 (filed 2026-09-02, operator-supplied CSV)
- Invoice total through Sep 1: **$15.86** (GPU $9.78 / storage $3.91 / download $2.17).
- **STATUS.md CORRECTION**: node 49572280 (“LIVE, ~$0.90/day bleeding”) actually lived
  ~14 GPU-minutes, total **$0.039**. The kill order targeted a corpse; fail-fast worked,
  the paperwork didn't. Account now: 0 instances, $0 accruing (verified live 09-02).
- **CORRECTED (same night):** my first read over-claimed. Storage-hours ~= GPU-hours on
  nearly every row — this is CONCURRENT disk proration (big disks, short lives), not
  post-death bleeding. destroy_instance does remove volumes; the original law
  (market_watch.py, OPERATOR ORDER 2026-08-27: $0.10/GB/mo on STOPPED instances,
  stop-vs-destroy math on every alert) was never violated — nothing was left stopped.
  The real lever: DISK SIZE at buy time (pick_template) — storage proration rode at
  ~40% of GPU cost on short leases. blade ledger should show storage as a line item.

## CORRECTION CHAIN (2026-09-02 night) — the learned-and-lost class, third instance
1. 08-27: operator orders storage-fee awareness -> market_watch.py built with stop-vs-destroy math.
2. The live buying path (blade_buyer) never applied it at execution time (no storage line item in the blade ledger).
3. 09-02: seat re-discovers the fee from an invoice, mis-names the mechanism (teardown gap), credits no one.
4. Operator: "self steal — i had that in vast but it was ignored." Both errors true: the shelf WAS ignored by the live path, AND the seat ignored the shelf.
LAW RESTATED: recorded corrections apply at execution time; and a rediscovery must cite its ancestor before it claims novelty.
