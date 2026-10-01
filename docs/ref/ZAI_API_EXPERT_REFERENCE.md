# Z.ai API Expert Reference — the fleet's provider, mastered (2026-08-26)

> The Operator ordered expertise. This is the compiled reference from the full docs.
> Every lane, every price, every error, every parameter — at the bytes.

## 1. MODEL CATALOG (both endpoints: standard + coding plan)

| Model | Context | Vision | Thinking | Input $/M | Cached $/M | Output $/M | Free? |
|---|---|---|---|---|---|---|---|
| **glm-4.7-flash** | 200K | no | optional | **FREE** | **FREE** | **FREE** | YES |
| **glm-4.5-flash** | 128K | no | optional | **FREE** | **FREE** | **FREE** | YES |
| glm-4.6v-flash | 128K | **yes** | optional | **FREE** | **FREE** | **FREE** | YES |
| **glm-5.3-flash** | **1M** | **YES** | **always** | $0.075* | $0.015* | $0.25* | no (promo) |
| glm-5.3 | **1M** | no | **always** | $1.40 | $0.26 | $4.40 | no |
| glm-5.2 | 1M | no | auto | $1.40 | $0.26 | $4.40 | no |
| glm-5.1 | 1M | no | auto | $1.40 | $0.26 | $4.40 | no |
| glm-5 | 1M | no | auto | $1.00 | $0.20 | $3.20 | no |
| glm-5-turbo | 1M | no | auto | $1.20 | $0.24 | $4.00 | no |
| glm-4.7 | 200K | no | optional | $0.60 | $0.11 | $2.20 | no |
| glm-4.6 | 200K | no | optional | $0.60 | $0.11 | $2.20 | no |
| glm-4.5 | 128K | no | optional | $0.60 | $0.11 | $2.20 | no |
| glm-4.5-air | 128K | no | optional | $0.20 | $0.03 | $1.10 | no |
| glm-4.6v | 128K | **yes** | optional | $0.30 | $0.05 | $0.90 | no |
| glm-5v-turbo | 1M | **yes** | auto | $1.20 | $0.24 | $4.00 | no |

*5.3-flash has 50% promo pricing (ends Sep 9, 2026); list: $0.15/$0.03/$0.50

## 2. THE FLEET'S CODING PLAN CREDITS

| Plan | 5h credits | Weekly credits | $/mo |
|---|---|---|---|
| Lite | 2,000 | 10,000 | $18 |
| Pro | 12,000 | 60,000 | ~$60 |
| Max | 28,000 | 140,000 | ~$120 |

Credit formula: `(input_tok × in_mult + cached_tok × cache_mult + output_tok × out_mult) / 10,000`

| Model | Input mult | Cached mult | Output mult |
|---|---|---|---|
| GLM-5.3 | 6.9 | 1.7 | 24 |
| GLM-5.3-Flash | 2.3 | 0.56 | 8 |
| Web Search MCP | — | — | 1.2/call |

**Off-peak: 50% credits.** Peak = weekdays 14:00-18:00 UTC+8. All day weekends = off-peak.

**Weekly token capacity at 95% cache (Max plan):**
- GLM-5.3: 676M - 1.35B tokens/week
- GLM-5.3-Flash: **2.0B - 4.1B tokens/week**

## 3. THE CACHE (implicit, automatic)

- No API parameters for cache control
- Response field: `usage.prompt_tokens_details.cached_tokens`
- Cache hits: ~50% of standard input price
- Cache: implicit based on content similarity (not byte-exact, but identical = highest hit)
- Best practices: stable system prompts, long docs in system message, append-don't-rewrite history
- TTL: undocumented ("reasonable time limits")
- **FLEET FINDING**: 4.7-flash (thinking off) caches at 99%. 5.3-flash (thinking always on) did NOT cache on our test. Hypothesis: thinking generates variable reasoning tokens that break similarity matching.
- **OVERTURNED 08-29 (EXP-A, mag/_exp_a_cache_retrigger.py): 5.3-flash DOES cache — 99.52% hit (7040/7074) on a byte-stable ~7K prefix with thinking on; novel-prefix same-size controls: 0%.** The 08-26 miss was prefix instability, not thinking. Cache mining doctrine extends to the judgment lane: frozen prefix + append-only turns + max_tokens>=1536.

## 4. PARAMETERS THAT MATTER

| Param | Type | Default | Notes |
|---|---|---|---|
| thinking.type | str | "enabled" | 5.3 and 5.3-flash: ONLY "enabled". 4.7-flash: can disable |
| reasoning_effort | str | "max" | 5.3/5.3-flash: max/high/low. Only works when thinking enabled |
| temperature | float | model dep | Low=factual, high=creative. Don't pair with top_p |
| top_p | float | model dep | 0.8-0.95 recommended. Don't pair with temperature |
| max_tokens | int | model dep | 5.3: default 65536, max 131072 |
| stream | bool | false | SSE streaming |
| tool_stream | bool | false | Stream tool calls in fragments (requires stream=true) |

> RECEIPTED 09-04: thinking/effort semantics per model, native + Coding-Plan effort remap
> tables, the 5.3 no-disable 1210 (docs + lived scar), reasoning_content shape, campaign
> scoping, queued $0 pings — §10 at the bottom. Cache/tool basics: ADDENDUM 09-03 below.

## 5. ERROR CODES (fleet-critical)

| Code | Meaning | Fleet response |
|---|---|---|
| **1302** | Rate limit (concurrency) | Backoff + retry (transient) |
| **1305** | Service overloaded | Exponential backoff (transient) |
| **1308** | Usage limit hit, resets at {time} | Wait for window |
| **1310** | Weekly/monthly exhausted | Wait for period reset |
| **1316/1317** | 5h/7d limit, no balance | Wait or top up |
| **1318-1321** | 5h/7d limit + spend cap | Wait or raise cap |
| 1309 | Coding plan expired | Renew |
| 1311 | Plan lacks this model | Upgrade |
| 1313 | Fair Usage Policy violation | Submit request to restore |
| 1113 | Insufficient balance | Recharge |
| 1210 | Invalid parameter (e.g. thinking disabled on 5.3) | Fix the param |
| 1261 | Prompt too long | Truncate |
| 1301 | Unsafe content detected | Rephrase |

### 5.1 CLIENT BACKOFF + REASONING FLOOR LAW (spec'd 2026-09-26, lane B2-62; measured by B2-04 same day)

MEASURED (live, `watch/inbox/burn_wave_20260926/B2_04_probe_results2.json`):
429 body `{"error":{"code":"1305","message":"The service may be temporarily overloaded, please try again later"}}`
hit ~1 in 3 calls at 6s spacing on the Pro lane; one Lite 429 was STILL 1305 after the
probe's single 15s wait; adaptive stretch is needed, not one fixed wait. Separately,
glm-4.7-flash at model-default thinking ate the WHOLE 600-token budget on 2 of 7 burns
(usage completion=600, content empty).

LAWS for the z.ai lane client (`models/providers.py`, chat_provider + chat_messages):

1. **OVERLOAD BACKOFF**; on HTTP 429 whose body names the overload family (1305 /
   1302 / "overloaded"), a provider flagged `retry_overload: true` (z_ai2, z_ai3; the
   funded fleet lanes) retries the SAME request after 15s, then 30s (base 15 = the
   measured recovery wait, x2 stretch per attempt, 2 attempts max) before failing.
   Bounded: worst case +45s. Every failed attempt is recorded, so fuel_feed /
   lane_cadence keep learning. After exhaustion the existing should_burst ->
   burst_mill(paid) path is unchanged and stays the LAST resort (free-first law,
   providers.yaml prefer_order). Providers without the flag never sleep (mistral
   limit-0, groq quota 429s behave exactly as before). A caller holding the
   concurrency gate keeps its slot during backoff: provider-wide overload is exactly
   when the single 4.7-flash slot must serialize instead of letting a herd re-collide.
2. **REASONING FLOOR**; the receipted minimum budget for thinking-on work is
   max_tokens >= 1536 (EXP-A 08-29 cache doctrine, §3 OVERTURNED note). When the
   caller did NOT decide thinking (thinking=None) AND max_tokens < 1536 AND the model
   can disable thinking (4.7-flash / 4.5-flash family; NOT glm-5.3 / glm-5.3-flash , 
   forced thinking, 1210 scar §10.1), the client disables thinking for that call and
   reports `reasoning_floor_applied: true`. Explicit thinking=True + a crumb budget
   keeps the honest empty_reasoning failure (caller override). The client NEVER
   raises a caller's budget (08-29 law, providers.py:258: callers opt down; never up
   from crumbs).

Falsifier: rerun B2_04_probe2.py's zai section; if 15s+30s no longer recovers a
1305 within 2 retries the constants are mis-tuned; if glm-4.7-flash at
max_tokens >= 1536 still returns content-empty, the floor value is wrong.

## 6. FLEET LANE MAPPING

| Fleet lane | API model | Cost | Role |
|---|---|---|---|
| z_ai (ZAI_API_KEY) | glm-4.7-flash | FREE | Standing wave / bulk mining |
| z_ai2 (Pro key) | glm-4.7-flash + glm-5.3-flash | free + credits | Swarm + frontier vision |
| z_ai3 (Lite key) | glm-4.7-flash + glm-5.3-flash | free + credits | Swarm + frontier vision |
| z_ai4 (ZAI_API_KEY_2) | glm-4.7-flash | FREE | Second free swarm lane |
| ZCode (Lite plan since 08-28) | glm-5.3-flash (this seat) | credits (3x quota) | Judgment/conductor — lite plan = control mechanism |

## 7. KEY ARCHITECTURAL FACTS

1. **5.3-flash is multimodal; 5.3-full is text-only.** The cheap model SEES.
2. **5.3-flash gets 3× the coding plan quota** of 5.3-full (lower multipliers).
3. **5.3 and 5.3-flash: thinking cannot be disabled.** Only 4.7-flash and below can turn it off.
4. **The free models (4.7-flash, 4.5-flash, 4.6v-flash) are free at ALL tiers** — no credits consumed.
5. **Off-peak (weekends all day, weekdays off-peak hours) = 50% credits.**
6. **Cached input is 50% of standard input price** — the standing wave halves the cost even on paid models.
7. **Model routing:** requests for 5.2/5.1 → 5.3; 5-turbo/4.7 → 5.3-flash. The API silently upgrades.
8. **5.3-flash was tested as "ox-alpha"** on OpenCode and OpenRouter — most popular model of the week.
9. **Native MCP servers included:** Vision, Web Search, Web Reader, Zread — free with all plans.
10. **Context window on all current models: 1M tokens** (except 4.7-flash at 200K, 4.5 at 128K).

## 9. GLM-5.3-FLASH ANNOUNCEMENT STEAL (2026-08-28, from the vendor blog)

Confirmed by the announcement text (operator pasted raw; fetchers were JS-walled):

1. **Weights are PUBLIC on HuggingFace.** Local runners: SGLang, vLLM, TokenSpeed.
   → ROCINANTE CALL (Oct 27): 320B total / 18B active MoE at 4.4x smaller KV cache
   than GLM-5.3 — the seat brain becomes self-hostable, and the NG-AISRP
   interpretability hook (log internals of a model we OWN) becomes executable on
   a frontier-class brain.
2. **Vision-in-the-loop is vendor design intent, not a bolt-on:** natively
   integrated so the model "decides when to observe and use visual feedback to
   guide subsequent actions" — self-visual judgment, test-time improvement, GUI
   judgment "grounded in real user flows." Vendor's own words: "Many failures
   only surface through rendering, interaction, or playtesting" (game dev named
   explicitly) and "Code lets the model build and change the world. Vision lets
   it enter the world people see and use." → This IS the fleet's
   play-is-epistemology doctrine in vendor voice; dumb-agent-with-eyes and the
   game harness ride a model BUILT to look. ZCode Browser Use + Computer Use are
   the named unlock surfaces (this seat's eyes are first-class).
3. **Architecture:** 320B total / 18B active (vs GLM-4.5's 355B/32B), 45 layers
   (vs 92), hybrid sparse + linear attention, Manifold-Constrained
   Hyper-Connections, IndexPool at 1M context. Attention compute 3x smaller and
   KV cache 4.4x smaller vs GLM-5.3. (That KV is serving cache, not our prompt
   cache — the §3 fleet finding is unaffected.)
4. **Served at scale on Chinese AI chips** (SGLang-based engine, W8A8, EPD
   disaggregation) — supply-line fact for the atlas. The serving stack was
   partly built by a GLM-5.3-powered infra agent — the model helped optimize
   the system serving the model (governor feedback loop, vendor edition).
5. **Benchmarks vs our lanes:** openly benchmarked against DeepSeek-V4-Flash
   (our drain-lane rival): base-vs-base splits (MMLU 88.1 vs 88.5, BBH 86.6 vs
   84.9, LiveCodeBench 37.6 vs 29.9). Coding/agentic approaching Claude Opus
   4.8; Pareto frontier at $0.045/task on AA Index v4.1.1. A price war between
   our two grind lanes — in our favor.
6. **Doctrine deltas:** (a) 1M context + flash cost = the session-mining lane
   upgrade — 630K sessions fit RAW (BOOT_4_7 shorthand existed because 4.7
   overflowed); (b) 3x coding-plan quota confirmed → post-Sep-1 rationing math
   may relax (operator's call, law 9 rightsize); (c) anon-tested as "ox-alpha"
   on OpenCode/OpenRouter before release — vendors run anonymous-lane recon too.

## 8. THE ECONOMICS (verified at our usage)

Today's fleet run: 30.5M tokens, 97% cached, cost $0.21 (would be $4.27 uncached).
At Max plan (140K credits/week) with 95% cache on 5.3-flash: ~2-4 BILLION tokens/week.
The wave + the plan + the off-peak = compute that approaches free at scale.

---

## ADDENDUM 2026-09-03 — CODING PLAN CREDITS + THE CONCURRENCY ABSENCE (docs sweep, 7 pages)

Sources fetched fresh: 4 capability pages (stream-tool, function-calling, cache,
struct-output) + devpack/overview + devpack/tool/claude + 2 404 probes (rate-limit,
usages-policy paths). 

### CONCURRENCY: RECEIPTED 09-04 (operator paste of the rate-limits page; supersedes "NOT PUBLISHED" — the page exists now or lives under a path we 404-probed).
**Scope header, verbatim: "The model concurrency on this page is only applicable to API users with balance consumption. GLM Coding users please refer to the package benefits."** So this table governs our credit-pool lanes (z_ai*); the PLAN door has its own (still = package-benefits/dashboard read). Higher limits: application form.

Concurrency limits (in-flight requests, API balance users) — fleet-load-bearing rows:
- **GLM-5.3-Flash: 50** ← the legions engine; ractor-legions ceiling on the API lane is now RECEIPTED
- GLM-4-Plus: 20 · GLM-4-32B-0414-128K: 15 (confirms the old sizing chart exactly)
- GLM-5.1: 10 · GLM-5.2: 10 · GLM-4.5: 10 · GLM-4.5V: 10 · GLM-4.6V: 10
- GLM-5.3: 5 · GLM-4.5-Air: 5 · GLM-4.5-AirX: 5 · AutoGLM-Phone-Multilingual: 5 · Web-Reader: 5 · Search-Prime(-Claude): 5
- GLM-4.6: 3 · GLM-4.6V-FlashX: 3 · GLM-4.7-FlashX: 3
- GLM-4.7: 2 · GLM-5: 2 · GLM-4.5-Flash: 2 · GLM-OCR: 2
- **GLM-4.7-Flash: 1** ← the scar explained: our old cache-mining lane was concurrency-1 by design — every saturation flap this season was the vendor's ceiling, not our error
- GLM-5-Turbo: 1 · GLM-5V-Turbo: 1 · GLM-4.6V-Flash: 1 · GLM-Image: 1 · CogVideoX-3: 1
- Video models (ViduQ1/Vidu2 family): 5 each

Routing consequences: (a) swarm/legion sizing on the API lane should key on 5.3-flash @50 — a 50-replica bay is vendor-legal with balance; (b) never build a concurrent workload on 4.7-flash (1) — single-flight only; (c) 1302 rate-limit errors map to these ceilings — backoff scales with the model's row.

### THE PUBLISHED QUOTA SHAPE (coding plan)
- 5-hour rolling credits + weekly credits: Lite 2,000/10,000 · Pro 12,000/60,000 · Max 28,000/140,000. 5h quota refreshes dynamically 5h after consumption; weekly resets every 7 days.
- Credit formula: (input×mult + cached×mult + output×mult)/10,000. GLM-5.3: in 6.9 / cached 1.7 / out 24. Flash: 2.3/0.56/8. MCP calls ×1.2 each. → OUTPUT COSTS 3.5x INPUT: terse-output doctrine is credit-optimal.
- Off-peak 50% credit rate (peak = Mon-Fri 14:00-18:00 SGT).
- CAMPAIGN: daily 23:00-09:00 UNLIMITED GLM-5.3-Flash via ZCode + doubled quota on other agents. NOTE: our locked campaign window 15:00-01:00Z IS 23:00-09:00 SGT — the window was vendor-aligned all along. Night Flash muscle is literally unlimited in-window.
- Token allowance (Pro, 95% cache hit): 290-580M tok/week GLM-5.3; Flash ~5x that.

### CACHE (vendor-confirmed fleet doctrine)
Implicit auto-caching, all GLM-5.x/4.x. API-side hits ~50% discount; coding-plan credits: cached multiplier 1.7 vs input 6.9 = ~75% off. TTL: "reasonable time limits", unpublished — resident-prefix cadence should assume decay; re-prime before long gaps (prime-then-flock holds).

### TOOL/STRUCT (organs)
Tool streaming: stream=True + tool_stream=True, glm-5 family only. tool_choice: auto only. JSON mode: response_format json_object, glm-5/4.7/4.6/4.5. [1m] model suffix = 1M context. Claude door env: ANTHROPIC_BASE_URL=https://api.z.ai/api/anthropic, CLAUDE_CODE_AUTO_COMPACT_WINDOW=1000000, verified CC 2.0.14+.

---

## 10. RECEIPTED FROM VENDOR DOCS 09-04 — THINKING/EFFORT SEMANTICS + CAMPAIGN SCOPING (8-page fold)

Sources: devpack/latest-model · guides/capabilities/thinking-mode (+ operator paste of live
page) · capabilities/{stream-tool, function-calling, cache, struct-output} ·
devpack/notice/event-glm-5.3-flash · llms.txt index. Complements the 09-03 addendum above
(cache/tool basics already folded there) — this section is what that sweep did NOT catch.

### 10.1 Thinking semantics per model
- **FORCED (cannot disable): GLM-5.3 + GLM-5.3-FLASH.** Verbatim: "GLM-5.3 and
  GLM-5.3-FLASH use forced thinking and cannot be disabled."
  **LIVED SCAR AGREES, and predates the docs**: 2026-08-26T02:38Z, z_ai lane, glm-5.3 →
  `HTTP 400 code 1210 "This model always engages in thinking and cannot be disabled;
  please use low, high, or max"` (memory/runs/alpha_zai/comparison.jsonl). The vendor's
  own error text receipts the 3-value effort set from production telemetry.
- Auto-decide (disable allowed): 5.2/5.1/5/4.6/4.5.
- **4.7/4.5V FORCED: UNPROVEN, CONFLICT ON FILE.** Operator paste says 4.7/4.5V are
  forced-enabled; the fetched render does not confirm it; lived production (§3 fleet
  finding, mag/fuel_feed.py 08-24 comment) runs 4.7-flash thinking-OFF for cache mining.
  Kill condition queued: §10.7 ping 1.
- **DOOR NUANCE (load-bearing):** native PAAS endpoint: `thinking.type="disabled"` on
  5.3 = 1210 ERROR. Coding-Plan door (/api/anthropic): disabled/false/none/off does NOT
  error — silently remaps to low ("still performs lightweight thinking"). Priority:
  "Explicit Effort > thinking toggle > default max"; default effort = max.

### 10.2 reasoning_effort tables
Native API:
| Model | Allowed values | Other values |
|---|---|---|
| 5.3 / 5.3-flash | **max, high, low ONLY** | ERROR (1210 family) |
| 5.2 | max, xhigh, high, medium, low, minimal, none | none/minimal = stops thinking; low/medium→high; xhigh→max |

Coding-Plan remap (what the plan door sends upstream when we steer it):
| Model | Mapping |
|---|---|
| 5.3 / 5.3-flash | none/minimal/low→low · medium/high→high · xhigh/max→max |
| 5.2 | none/minimal→stop · low/medium→high · xhigh→max |

latest-model page adds: light/ultra also accepted (light→low, ultra→max); unknown effort
string → max + logged hint. **MAX_DISTILL receipt**: "5.3 needs thinking=low" is now
vendor-receipted — low IS the model's floor, not a workaround.

### 10.3 reasoning_content shape
- Message: assistant msg carries `reasoning_content` beside content/tool_calls.
  Streaming: `delta.reasoning_content` chunks (hasattr-guard), same for stream-tool deltas.
- Preserved thinking: ON by default on the Coding-Plan endpoint, OFF on standard API.
  Opt-in via `clear_thinking:false` requires returning prior reasoning_content
  UNMODIFIED — "All consecutive reasoning_content blocks must exactly match the original
  sequence"; reordering/editing degrades performance + cache hit.

### 10.4 Stream-tool deltas
Tool-call args arrive as fragments keyed by `index`; assemble incrementally:
`final_tool_calls[index].function.arguments += frag` (arguments are a JSON STRING).
Docs self-contradiction: page says "limited to glm-5" while its own sample uses glm-5.3 —
treat the limit as untested. [1m] suffix + CLAUDE_CODE_AUTO_COMPACT_WINDOW=1000000 for 1M
on the Claude door (see addendum).

### 10.5 Structured output — honest limits
**NO json_schema parameter. NO strict mode. NO message.parsed.** Only
`response_format {"type":"json_object"}` + schema embedded in the system prompt +
`json.loads(content)` + own validation. Fleet output contracts CANNOT go native on z.ai —
keep prompt-schema discipline. (Docs-page absence ≠ proven API absence; probe queued §10.7.)

### 10.6 EVENT SCOPING — glm-5.3-flash nocturnal campaign (LIVE; sharpens addendum)
Vendor notice, exact scope: **Sep 3–20, 2026, DAILY 23:00–09:00 UTC+8 (15:00–01:00 UTC),
weekends included, automatic, all paid plans.** "Via ZCode: Zero quota consumption";
other supported agents: quota DOUBLED. **Applies ONLY to glm-5.3-flash** — 5.3-full bills
standard. Open items: notice's "ZCode" = this seat's CLI is name-collision-risk UNPROVEN
(prove via plan dashboard zero-burn in-window); stacking with off-peak 50% credits
unspecified.
**CORROBORATION 09-05** (@louszbd "Lou", z.ai GLM product account, quoting Zixuan Li,
api.fxtwitter receipt): "increased GLM-5.3-Flash usage for ALL CODING PLAN users" —
"all coding plan users" strengthens Lite-key coverage (probe prediction: Lite row $0/0cr);
feedback agents NAMED BY VENDOR: "Hermes and OpenClaw" = our openclaw lane is officially
the supported class; "applies automatically" re-affirmed. Card:
watch/INTAKE_LOUSZBD_FLASH_QUOTA_20260905.md.

### 10.7 QUEUED PINGS ($0-ordered; next seat executes cold)
1. **glm-4.7-flash + `thinking {"type":"disabled"}` + max_tokens=16** on ZAI_API_KEY —
   FREE model, $0. 200 → 4.7 still disableable, cache-mining doctrine intact, paste wrong.
   1210 → §4 row is DEAD, free-lane doctrine must rebuild on reasoning-bearing completions.
2. glm-5.3-flash native + `reasoning_effort:"medium"` → expect effort-error naming
   max/high/low (completes the 1210 receipt for the effort axis).
3. Plan dashboard read inside tonight's 23:00–09:00 SGT window → proves zero-quota
   campaign + settles the "ZCode" identity question.

### ADDENDUM 2 — CONCURRENCY TABLE FOUND (operator supplied the page my probes 404'd, 09-03)
Source: z.ai rate-limits page (pasted verbatim by operator; "API usage is limited by concurrency — in-flight requests").

FLEET-MEANING ROWS (concurrent in-flight):
- GLM-5.3-Flash: **50** — the free-lane king; intake/driver burst caps were conservative vs this.
- GLM-5.3: 15 · GLM-4-32B-0414-128K: 15 (B-lane engine confirmed at 15) · GLM-4-Plus: 20
- GLM-5.1/5.2: 10 · GLM-4.5V/4.6V: 10 · Web-Reader: 5 · Search-Prime(+Claude): 5
- GLM-4.7-Flash: **1** ← explains the historic "4.7 pool congested provider-wide"; 4.7: 2, 4.7-FlashX: 3
- GLM-4.5-Flash: 2 · 4.5-Air/AirX: 5 · GLM-5: 2 · 5-Turbo: 1 · GLM-Image/CogVideoX-3: 1
- THROTTLE LAW: >8K context on GLM-4-Flash (free trial) throttles to 1% of standard concurrency — long-context free-lane work dies silently; keep free-trial Flash calls short-context.
TRI-STATE: table = Supported (operator paste, primary source). Application to CODING-PLAN sessions (OAuth/anthropic door) = Unproven — table is titled for API usage; plan side may be credit-window-only. Router implications: 4.7-Flash lanes are 1-wide (retire/deprioritize), 5.3-Flash at 50 justifies bigger burst caps on API-credit lanes; fuel_feed FREE_LANES repoint = routed-plan item, not hot-patched.

## PRICING & BILLING RECEIPTS (09-04, operator billing table paste — 2026-09-03 rows)

Two keys, two economies:
- **3254...c7fd = API-with-balance key (cash pricing, "Postpaid"):**
  - glm-5.3: INPUT $0.0014/kTok · OUTPUT $0.0044/kTok
  - glm-5.3-flash: INPUT $0.000075/kTok · OUTPUT $0.00025/kTok (18.7x / 17.6x cheaper than 5.3-full)
  - glm-4.5-air: INPUT $0.0002/kTok · OUTPUT $0.0011/kTok · CACHE $0.00003/kTok
  - glm-4-32b-0414-128k: NORMAL $0.0001/kTok (night B-engine burned 1.31M tok = $0.13)
- **4f8a...6464 = GLM Coding Lite V3 - Yearly PACKAGE key (all rows $0 cash, credits consumed against package):**
  - 5.3-flash night bay traffic: 573,842 INPUT + 130,511 OUTPUT + **12,353,152 CACHE** tok, 75 calls → 44.21 + 34.98 + 231.75 credits
  - 5.3: 422,248 IN + 6,043 OUT + 2,509,696 CACHE → 97.60 + 4.86 + 142.93 credits
  - web-reader plugin: $0.01/time → 1.2 credits/call

**CACHE ECONOMICS (receipted):** cache reads are $0/kToken cash but METER PACKAGE CREDITS —
12,353,152 cached tokens = 231.745 credits ≈ **53.3K cached tokens per credit** (5.3-flash
Lite). The resident-worker/cache-farming doctrine is confirmed and now has a metered rate:
a cache-heavy night bay spends package credits, not cash, at ~19 credits per million cached
tokens. Watch the weekly/5h Lite windows (2,000/10,000) against this rate.

**CAMPAIGN-WINDOW TENSION (tri-state):** the 5.3-flash Lite rows SHOW credits consumed
(44.21+34.98+231.75) on 09-03 — if the "23:00-09:00 zero-quota via ZCode" campaign applied
to these calls, the rows would presumably show 0. Either the bay traffic ran outside the
window, or the campaign doesn't zero the package-credit meter. Resolves only with an
in-window vs out-window row comparison — still Unproven, dashboard read stands.

**KEY INVENTORY CORRECTION:** ZAI_API_KEY_Lite (4f8a...6464) is NOT a raw balance key —
it IS a GLM Coding Lite Yearly package key. The empirical 50/50 concurrency pass (09-04)
therefore measured the LITE PACKAGE's concurrency: Lite carries >=50 in-flight on
5.3-flash. Plan-door row for LITE: RECEIPTED empirically. Pro's package concurrency:
still unread.

### PRO/MAX PACKAGE RECEIPTS (09-04, operator billing table — key e18f...617f, "GLM Coding Max V3 - Quarterly")

**THE ZERO-QUOTA CAMPAIGN ROW IS RECEIPTED:** glm-5.3-flash NORMAL — **32,262,464 tokens,
162 calls, $0.00, Credits Consumed 0.000000, no package attached** (09-03 row). The
"23:00-09:00 SGT zero-quota via ZCode" night window is REAL and meter-zero. "ZCode" as
this CLI is now Supported-by-billing-shape (a 32M-token row escaping both cash AND package
credits has no other explanation on file).

**CREDIT RATES (tokens per credit, measured from Pro rows):**
- 5.3-flash INPUT: 31,324,562 / 2,544.50 = **~12,312 tok/credit**
- 5.3-flash CACHE: 424,643,328 / 8,428.51 = **~50,381 tok/credit**
- 5.3-flash OUTPUT: 1,354,539 / 377.20 = **~3,591 tok/credit**
- 5.3 INPUT: ~3,767 tok/credit · 5.3 CACHE: ~14,748 tok/credit

**SWARM BUDGET MATH (Max package = 28,000 credits/5h + 140,000/week):**
- input-shaped work: 140K cr x 12,312 ≈ **1.72B input tokens/week**
- output-shaped work: 140K cr x 3,591 ≈ **503M output tokens/week**
- cache-shaped work: 140K cr x 50,381 ≈ **7.05B cached tokens/week**
- At ~500 tok/wing-request that is order **~480K wing-requests/day** on the Pro lane alone
  (before the Lite package, before the night zero-quota window, before free lanes).
- Observed spend: the bay's real 09-03 traffic (~600M tokens across cache+input) consumed
  ~17K credits — the swarm is ALREADY running inside the package with headroom.

**CONCURRENCY on Pro:** 1,081 flash calls on 09-03 through the package; the Lite package
measured >=50 in-flight empirically. Pro's per-window concurrency: expect >= Lite
(one more dashboard cell, non-blocking).

### CONCURRENCY APPENDIX — FULL TABLE (09-04, operator verbatim paste of rate-limits page; completes the fleet-rows-only receipt above)

Header caveat, verbatim: "The model concurrency on this page is only applicable to API users
with balance consumption. GLM Coding users please refer to the package benefits."
→ Our Lite/Pro PACKAGE keys do NOT ride this table; their limits = package benefits
  (Lite empirically >=50 in-flight on 5.3-flash, measured 09-04). This table governs
  balance-consumption API keys only.

Full model rows (concurrency):
GLM-4.6=3, GLM-4.6V-FlashX=3, GLM-4.7=2, GLM-Image=1, GLM-5-Turbo=1, GLM-5V-Turbo=1,
GLM-5.1=10, GLM-5.2=10, GLM-5.3=5, GLM-5.3-Flash=50, GLM-4.5=10, GLM-4.6V=10,
GLM-4.7-Flash=1, GLM-4.7-FlashX=3, GLM-OCR=2, GLM-5=2, GLM-4-Plus=20, GLM-4.5V=10,
GLM-4.6V-Flash=1, AutoGLM-Phone-Multilingual=5, GLM-4.5-Air=5, GLM-4.5-AirX=5,
GLM-4.5-Flash=2, GLM-4-32B-0414-128K=15, Web-Reader=5, Search-Prime=5,
Search-Prime-Claude=5, CogView-4-250304=5, GLM-ASR-2512=5, ViduQ1-text/Image/Start-End=5,
Vidu2-Image/Start-End/Reference=5, CogVideoX-3=1. Higher limits: application form.

NEW-LANE CANDIDATES this table reveals (never probed, all on keys we hold):
- GLM-OCR (2): OCR lane for the intake — untried.
- Search-Prime / Search-Prime-Claude (5): vendor web-search API — candidate behind the
  invariant-hunt queries; billing rows show the operator already pays $0.01/search on the
  Max package (search-prime-claude 28 calls receipted).
- Web-Reader (5): vendor reader — the intake fetcher's fallback of last resort.
- GLM-4.7-FlashX (3) vs GLM-4.7-Flash (1): a 3x-concurrency sibling of the cache-mining lane.
- GLM-ASR-2512 (5) / Vidu2 family (5): audio/video lanes — **ASR LIVE 09-07** (probed:
  POST /api/paas/v4/audio/transcriptions, model=glm-asr-2512, multipart file — HTTP 200,
  transcribed a 30s LCD Soundsystem clip on first fire; "Daft Punk" → "that punk", honest
  near-miss). Vidu2 video lanes still someday-docket. THE TORTOISE HAS EARS
  (watch/THE_TORTOISE_20260907.md).
SELF-STEAL CORRECTION FILED 09-04: the dashboard-read request was redundant — both answers
(concurrency here, zero-burn in the billing rows) were already in hand. Shelf-before-ask.

**FILING NOTE 09-04 (late):** the operator's second delivery of this table was filed as a
self-steal miss. Re-filed under the correct law: DUPLICATION IS EMPHASIS. Two independent
deliveries of the same table = double-attested numbers, not a redundant paste. Amendment 4,
watch/INTAKE_RUBRIC_20260903.md.

## PROVIDER VERDICT LINES (fold 2026-09-06 from MORNING_HOT_TRIAGE_20260901 + SELF_STEAL_MEMORY_20260901, board actions)
- Together AI Sept H100 cut: VALID (official @togethercompute post, primary-sourced) but does NOT move fleet $/compute math — vast.ai big-RAM at $0.54-1.00/hr stays ~4-7x cheaper; Together = convenience/premium, not cost-floor.
- GLM-5.3 "agentic SOTA": INFLATED as a blanket claim — PARTIALLY VALID, self-reported. Leads CyberGym only; trails closed models on most core agentic/coding benchmarks. Quote with the caveat.
- DeepSeek MEASURED: 91-98 percent cache-hit; MID-MONTH REPRICE ~Aug 16 (flash 2.4-4.7x, dual peak/off); cache saved ~$1,870; Together batch ~19x cheaper for bulk.
- z.ai existing subs GRANDFATHERED (existing-subscription pricing survives plan changes) — economics row that lived in one card only.
- VAULT_VENTURE keep-alive ~$40-50/mo; RUNG 0.5 = underused PC vault node + FreeToken; hardware check BEFORE drive spend.
- Cites: MORNING_HOT_TRIAGE_20260901, SELF_STEAL_MEMORY_20260901
