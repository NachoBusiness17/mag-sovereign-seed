# BURST DOCTRINE — what to burst, where, and how (2026-09-03, measured + receipted)

Every number below is either live-measured tonight (`watch/PROBE_BURST_20260903.log`),
vendor-receipted (ZAI_API_EXPERT_REFERENCE.md), or marked Unproven. No vibes.

## THE LANES (what each is FOR)

| Lane / model | Concurrency | Latency p50 | Cost profile | USE FOR |
|---|---|---|---|---|
| **glm-5.3-flash** (API credits) | **50** (measured 50/50, p50 1.7s) | 1.1s solo → 1.7s @50 | $0.000075/kTok in, $0.00025 out | THE burst lane: intake cards, wing sweeps, ractor legions, panel seats, any fan-out |
| **glm-4-32b-0414-128k** | 15 | **0.8s** (fastest measured) | $0.0001/kTok | High-volume short work: classification, extraction, triage pings, heartbeat checks |
| **glm-5.3** (API credits) | 15 | 1.1s | $0.0014/kTok in | Judgment: conductor specs, folds, arbitration — when flash isn't enough |
| **glm-4.5-flash** (free) | 2 | 0.9s short / **11.8s @9Ktok** | FREE | Tiny short-context free jobs ONLY (see 8K law) |
| **glm-4.7-flash** (free) | **1** (measured: 2nd call = 1302) | 0.8s | FREE | Strictly single-flight: the cache-mining standing wave, thinking-off (measured 200 tonight) |
| **Plan door / ZCode** (5.3-flash OAuth) | plan-side Unproven (Lite ≥50 empirical) | ~1s class | ZERO credits 23:00–09:00 SGT campaign; off-peak 50% otherwise | Judgment seats, coding work, the panel — schedule heavy plan work in-window |

## THE BURST LAWS (all measured tonight unless noted)

1. **Flash bursts big and cheap.** 50 simultaneous = 50/50 success, median latency +0.6s vs solo. When in doubt, burst on 5.3-flash.
2. **4.7-flash never parallelizes.** Two calls = one 1302 (measured). Single-flight only; it exists for frozen-prefix cache mining, nothing else.
3. **The 8K tax:** free-trial flash past ~8K context runs ~10x slower (measured 11.8s vs 1.2s). Long-context free work is a contradiction — move it to 5.3-flash (1M ctx, 50-wide, near-free at promo rates).
4. **32B is the latency king on a budget** — 0.8s, 15-wide, cheapest paid kTok. Default for anything that fits "many small decisions".
5. **Terse outputs are money.** Output tokens cost 3.3x input (API cash) to 3.5x (plan credits). max_tokens discipline is a budget line, not a style choice.
6. **Night window compounds:** 23:00–09:00 SGT = plan-door flash at zero credits (billing-row receipted 09-04) AND API off-peak 50% outside weekday peak. The overnight run is the cheap run — schedule bursts inside it.
7. **Cache: frozen prefix + append-only turns = 99.5% hit** (receipted 08-29, re-confirmed 09-04 at metered ~50K tok/credit plan-side). 4.7-flash thinking-off still disableable (measured 200 tonight) — the standing-wave miner lives.
8. **1302 means "you hit your model's row"** — backoff, or move the workload to a wider row (this table). It is information, not an insult.
9. **Plan-door concurrency: Unproven** — Lite measured ≥50 in-flight empirically (09-04 billing); Pro/Max expected ≥ Lite. The dashboard cell remains unread.

## ROUTING TABLE (burst patterns by job shape)

| Job | Pattern |
|---|---|
| Intake card batch (dozen links) | 5.3-flash ×(10–30) background spawns; scale to 50 for raw sweeps |
| Ractor legions / bay scale-up | 5.3-flash replicas to 50 on API lane; tranche past 50 needs the form |
| Wing mining (free) | 4.5-flash short-context ×2 max, OR pay pennies on 32B ×15 — 32B is faster per call |
| Standing-wave cache mining | 4.7-flash single-flight frozen prefix (free) — never two in-flight |
| Long-context reading | 5.3-flash ONLY (1M ctx; free flash dies at 8K) |
| Judgment / folds / conductor | 5.3 (API) or plan-door 5.3-flash effort=low in night window |
| Heartbeats / liveness pings | 32B ×15 — fastest, cheapest, widest little lane |

## CORRECTIONS FILED WITH THIS DOCTRINE
- Addendum 2 row "GLM-5.3: 5" was a transcription error — operator paste says **15**. Corrected here; the addendum above stands corrected by reference.
- 4.7-flash forced-thinking claim (operator paste) DISPUTED by live test: `thinking {"type":"disabled"}` returned 200 tonight. §4 row lives; cache-mining doctrine intact.

## KEY-LABEL CORRECTION (economist audit, 09-03 late)
The probe log labels the 50/50 ladder "Pro credit key" — but the harness fell back to
ZAI_API_KEY when the Pro-named var was absent, so the run's key attribution is ambiguous.
What is MEASURED: the credited key in .env carried 50/50 in-flight on 5.3-flash at p50 1.7s
(the Lite package separately shows ≥50 in billing evidence). Cite the numbers, not the
plan name. Also: probe run 1 died on a harness bug (0/0 rows = "not measured"); all
doctrine numbers stand on run 2 only. — per ECONOMIST_SCALE_AUDIT_20260903.md

## LAW 13 (probed 09-04, watch/INTAKE_GLM53_HIGH_CONCURRENCY_20260904.md addendum):
**The 50-row is enforced PER KEY.** Waves of 60/70/80 concurrent returned exactly 50 successes + instant 1302s, zero 429s, flat latency. Provider capacity is fine; the wall is key-side policy. CONSEQUENCE: bay scale-up past 50-wide = MORE KEYS (horizontal), never concurrency tricks. The third-party c=512 claim was self-hosted TP=4, not the vendor API — consistent, not applicable. Probe: scripts/conc_probe_past50.mjs (~$0.02, 260 requests).
