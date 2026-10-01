# LING 3.0 FLASH — THE FREE WORKHORSE
## API reference, measured limits, fleet usage

*Compiled 2026-09-13 from tonight's mirror + probes + usage CSV. Everything measured; Unproven items flagged.*

---

## THE FIVE VARIANTS (all in the zoo, all Nous/universal_orbit)

| Model ID | Free? | Notes |
|---|---|---|
| `inclusionai/ling-3.0-flash-sante:free` | YES | **The workhorse.** This is what the mirror, probes, and all free-lane waves ride. |
| `inclusionai/ling-3.0-flash-fin:free` | YES | Second free row. Same family, different tuning. Probed clean in zoo census but not wave-tested yet. |
| `inclusionai/ling-3.0-flash` | NO | Paid tier. Probably higher rate limits. Unprobed. |
| `inclusionai/ling-3.0-flash-fin` | NO | Paid tier, "fin" tuning. Unprobed. |
| `inclusionai/ling-3.0-flash-vl` | NO | Vision-language variant. Unprobed. Could feed the eye if universal_orbit supports image inputs. |

## MEASURED WIDTH CEILING

| Width | OK | Errors | Wall | Median latency |
|---|---|---|---|---|
| 8 | 8/8 | 0 | 10.2s | 10.0s |
| 16 | 16/16 | 0 | 12.7s | 11.9s |
| 24 | 24/24 | 0 | 18.7s | 17.6s |
| 48 | 48/48 | 0 | 74.7s | 42.1s |

**Cruise: 24-wide. Burst: 48-wide. The wall above 48 is local spawn cost (hermes CLI boots), not the API.** 100+ needs a spawn-free organ (persistent hermes server, or direct universal_orbit calls skipping the CLI).

## THROUGHPUT (empirical, from usage CSV)

- **Sep 7:** 259 requests, 8.6M input tokens, 133K output — zero errors
- **Sep 8:** 254 requests, 10.5M input, 208K output — zero errors
- **Sep 13:** 87 requests (mirror share), 3.2M input, 57K output — zero errors
- **Lifetime:** thousands of requests, zero recorded 429s, rejections, or quota hits

**The free row has no observed daily cap.** 10M+ input tokens in a day, no throttling.

## LATENCY

| Width | Median | Max |
|---|---|---|
| 8 | 10.0s | 10.2s |
| 16 | 11.9s | 12.7s |
| 24 | 17.6s | 18.7s |
| 48 | 42.1s | 74.6s |

Latency scales with concurrency, not with queue position — gentle stretch, no clifffdge.

## ACCESS

```bash
# via hermes CLI (the seat's normal route)
hermes -z "your prompt" -m inclusionai/ling-3.0-flash-sante:free

# via fanout.py (the wave organ) — packs are data
# model: "inclusionai/ling-3.0-flash-sante:free"
# key_env: handled by hermes auth (no key needed for :free rows)
```

## QUIRKS

**None observed.** Unlike stepfun/solar-pro4 (400 on missing tags param), ling just
works. No special params, no auth friction, no content filtering surprises.

## RELIABILITY RECORD

- Thousands of requests across Sep 7-13
- Zero 429s, zero rejections, zero quota hits
- Zero content-refusal incidents
- The most reliable free lane in the zoo

## UNPROVEN (needs probing)

- **Context window limit** — empirically accepted 37K+ input per request; actual limit unmeasured
- **fin vs sante** — what's the difference? Different tuning? Different training data?
- **ling-3.0-flash-vl** — vision-language: can it read images through universal_orbit?
- **Paid tier rate limits** — does paying actually buy higher concurrency?
- **Daily cap** — 10M+ tokens in a day with no cap hit; the actual ceiling unknown

## COMPARISON TO OTHER FREE LANES

| Lane | Cost | Speed | Reliability | Quirks |
|---|---|---|---|---|
| **ling-3.0-flash-sante:free** | $0 | fast | zero issues | none |
| ling-3.0-flash-fin:free | $0 | fast | probed clean | untested in waves |
| longcat-2.0:free | $0 | fast | not wave-tested | unknown |
| laguna-s/xs:free | $0 | fast | not wave-tested | unknown |
| stepfun/step-3.7-flash:free | $0 | fast | clean but needs tags param | the only quirk in the free set |
| upstage/solar-pro4:free | $0 | fast | probed clean | gated listings |

**ling is the cleanest, fastest, most reliable free row in the zoo.** Zero quirks.
The default free-lane choice until a probe proves otherwise.
