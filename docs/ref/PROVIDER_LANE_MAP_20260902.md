# PROVIDER LANE MAP (2026-09-02, evening)
*Operator: "we have mistral, openai, and god knows how many new api things — we need a map and to go do all of it."
Ground truth: repo .env key names + states (values never echoed), deploy/openclaw/openclaw.container.json,
hermes config.yaml. This file is the single lane source of truth; update it when a wire changes.*

## A. THE KEY SHELF (what we hold)

| Key | State | Provider | Best role | Tier | Wired into |
|---|---|---|---|---|---|
| ZAI_API_KEY | SET | z.ai | free gophers (4.7-flash) | FREE | cage `zai` provider; web MCPs |
| ZAI_API_KEY_2 | SET | z.ai | free gophers lane 2 | FREE | cage `zai-2` (coding endpoint) |
| ZAI_API_KEY_3 | SET | z.ai | free gophers lane 3 | FREE | **UNWIRED** — spare |
| ZAI_API_KEY_Pro | SET | z.ai | 5.3-flash judgment (JUDGE-only) | Max-plan credits | cage `zai-pro`; hermes candidate |
| ZAI_API_KEY_Lite | SET | z.ai | Lite seat control lane | Lite-plan credits | cage `zai-lite`; ZCode seat |
| DEEPSEEK_API_KEY | SET | deepseek | grind lane (v4-flash, 91% cache) | pennies | cage primary (all entries) |
| ANTHROPIC_API_KEY (1) | SET | claude | FUNDED judgment/bulk lane — workspace-linked, header anthropic-workspace-id in .env | paid | **WIRED+VERIFIED 09-03: PONG haiku-4-5** |
| ANTHROPIC_API_KEY_2 | SET | claude | UNFUNDED free front surface — light calls only | free | verified, bench |
| OPENAI_API_KEY | SET(len164) | openai | embeddings/vision occasionally | paid | hermes .env (to be repurposed) |
| OPENROUTER_API_KEY / _2 | SET | openrouter | last-resort auto-fallback | paid | cage fallback chains |
| GROQ_API_KEY / _2 | SET | groq | overflow free lane (100 calls/day cap) | FREE (capped) | **UNWIRED** |
| MISTRAL_API_KEY | SET | mistral | **HOST-SIDE ONLY — consent gate open** | paid | UNWIRED (deliberate) |
| COHERE_API_KEY_FREE/_PAID | SET | cohere | command-a (paid one wired in cage) | mixed | cage `cohere` |
| CEREBAS_API_KEY | SET | cerebras | fast small-model bursts | paid | **UNWIRED** |
| NVIDIABuild-Autogen-46 | SET | nvidia | deepseek-v4-flash mirror | paid | cage `nvidia` (worker fallback) |
| ALIBABA-MODEL-STUDIO | SET | alibaba | qwen lane | paid | **UNWIRED** |
| TOGETHER_API_KEY | SET | together | open-model buffet | paid | **UNWIRED** |
| XAI_API_KEY | SET | x.ai | grok lane (retirement note in hermes) | paid | **UNWIRED** |
| CURSOR_API_KEY | SET | cursor | not a lane — product key | n/a | UNWIRED |
| VASTAI_API_KEY | SET | vast.ai | GPU blades (buyer stood down) | $/hr | blade_buyer |
| NOTION_API_KEY | SET | notion | mirror target (pull-only shelf) | free | **UNWIRED — queued** |
| GEMINI/GOOGLE_API_KEY | EMPTY | google | Gemini 3.8 Flash lane ($0.75/M) | — | **needs real key** |
| GROK_API_KEY / _2 | EMPTY | x.ai api | — | — | dead |
| X_* (5 keys) | SET | twitter | ractor surface (publication only) | n/a | ghost/x tooling |

## B. THE CAGE (openclaw) — routing truth

Providers configured: deepseek, zai (KEY, free 4.7/5.3-flash/5.3), zai-pro, zai-lite,
glm53-api, zai-2 (KEY_2, coding endpoint, 4.7/4.5-flash), cohere, nvidia, ollama.
**Found gap (this is why "glm steering is not happening"):** `main` and `worker`
entries route deepseek primary → openrouter/auto fallback. **Zero GLM in the chain** —
the free lanes were never wired into the routing, only the `zcode` entry had one.
Fix applied 2026-09-02 evening: GLM free lanes wired into every fallback chain (see board receipt).

## C. HERMES — routing truth

config.yaml: provider custom → **local ollama** (gemma4-hermes, 65K ctx) — the slow-lane trap.
Fix queued: repoint base_url → https://api.z.ai/api/paas/v4, model → glm-4.7-flash,
key ← ZAI_API_KEY_Lite. Identity import: fleet SOUL block + verb-genomes skill.

## D. THE LANE DOCTRINE (who carries what)

1. **Grind** → deepseek v4-flash (cage primary), 91% cache, ~$9/mo whole-fleet.
2. **Gopher overflow** → GLM free lanes (zai KEY + KEY_2 + KEY_3 spare), never paid.
3. **Judgment** → 5.3-flash on plan credits (zai-pro/zai-lite), JUDGE-only, cached conductor.
3b. **KEY LAW (operator correction 2026-09-02, word on record):** programmatic/API work
    uses the z.ai API keys (KEY/KEY_2/KEY_3) — they carry the large credit pool and are NOT
    quota-limited. Pro/Lite keys are interactive coding-plan seats with QUOTA WINDOWS —
    hands-off for API calls, scripts, and gopher lanes. The conductor calls ZAI_API_KEY.
4. **Bulk-cron cache mining** → Claude (2 keys) — VERIFY first, then night windows.
5. **Burst muscle** → vast blades (buyer stood down; floor honored).
6. **Wired-but-idle bench**: groq (daily cap), cerebras, together, alibaba, xai, cohere-free —
   map only; wire on task need, one at a time, each with a receipt.
7. **Consent gates**: mistral (host-side until explicit consent), openai (paid — avoid),
   cursor (not a lane), notion (mirror, pull-only).
8. **Empty/dead**: gemini (needs real key — the one NEW lane worth buying), grok api.

## E. IDENTITY IMPORT STATUS

| Surface | AGENTS/doctrine | Skills | Steer protocol |
|---|---|---|---|
| cage workspace | exists (5.4KB) + lanes section appended 09-02 | shelf: chan, fireball-cycle, operator-corrections + **verb-genomes added 09-02** | via steer_bus → receipts |
| hermes | SOUL.md fleet block appended 09-02 | ships its own + **verb-genomes copied 09-02** | queue-file driven (overnight_churn) |
| zcode (this seat) | full | full | steer_bus author side |
