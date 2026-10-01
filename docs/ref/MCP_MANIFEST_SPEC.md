# MCP MANIFEST SPEC — the enforceable capability-layer manifest (v0.1, 2026-09-04)

**Status:** SPEC DRAFT under the 2026-08-26 operator GO. The GO named the burn protocol —
nacho builds, sd attacks, zcode referees — whoever drafts, the attack pass follows. This
document is the draft the GO ordered; **no enforcement organ exists yet** (see TRI-STATE).

**First consumers:** the lane manifests `queue/lanes/<name>/manifest.md` (their
`mcp_whitelist:` line is the consumer-side pin of this spec — see section 9).

---

## 0. PROVENANCE — the GO, verbatim (2026-08-26)

Recorded in `queue/handoff/zcode/CONVO.md` (zcode-seat entry, 2026-08-26T22:5x),
"OPERATOR GO — DECISIONS RECORDED", item (2), quoted in full:

> (2) MCP-MANIFEST: GO — the GLM_K8S_MCP_DEEP_RESEARCH distillation + four-server find is
> verified (repo doc lines 37-40/98-113/148 match; docs.z.ai confirms Vision/WebSearch/
> WebReader/Zread all official, Coding-Plan-gated). Owning seat: post your distillation to
> CONVO, then draft the mcp-manifest build spec under burn protocol — nacho builds, sd
> attacks, zcode referees. SPEC MUST PIN: epoch-pinned byte-stable manifest; read-only
> perception packs for quantized tiers, write-capable tools only for the primary planner;
> QUOTA GATE on all four Z.AI MCP servers (per-call credit weights — web search 1.2/call —
> or their eyes eat the judgment lanes' 5h pool); fail-close rule carried over (never cache
> privileged results by argument equality); SURFACES.md entry for the local Vision stdio
> server. Distributed cache-tier machinery (Redis tiers/hashing/single-flight) is OUT of
> today's scope — Rocinante blueprint only.

Corroborated in-session (sess_f7209b4a, "Fresh Boot Test on 5.3 Flash", Aug 26), the seat's
restatement the GO answered: "post the distillation to CONVO and draft the `mcp-manifest`
build spec ... Spec must pin: epoch-pinned byte-stable manifest, read-only perception for
quantized tiers / write-capable hands only for the primary planner, quota gate, fail-close
rule carried over, SURFACES registration."

**Orphan trail:** GO'd Aug 26, never drafted — mined from archived session transcripts
2026-09-04 (`watch/SELF_STEAL_ZCODE_SESSION_ORPHANS_20260904.md` #O1, tri-state Supported).
The Sep 3–4 MCP cards (`watch/INTAKE_ZAI_DEVPACK_MEMORY_20260903.md`,
`watch/STEAL_ZAI_SYSTEMS_AUTOMATE_20260904.md`) enumerate the suite but carry none of the
pinned requirements; this spec is where the pins land.

---

## 1. WHY THIS SPEC EXISTS

Capability without a manifest is unmetered spend and unbounded blast radius. The operator's
frame: perception tools (eyes/GPS) are cheap per call but eat quota pools sized for
judgment; hands (write-capable tools) are dangerous in proportion to the agent's autonomy.
The manifest makes both enforceable AT THE GATE, not by asking the model to be careful.
This is the capability-endowment doctrine ("senses for the blind, GPS for the stateless,
hands for the tool-less" — see `memory/improve/orphan-o3-endowment-doctrine-2026-09-04.md`)
in enforceable form.

---

## 2. MANIFEST FORMAT — one pack per MCP server

File: `docs/ref/mcp_packs/<pack_id>.manifest.json`. Canonical JSON (sorted keys, no
trailing whitespace, LF endings) — byte-stability is a hard requirement (section 3).

```json
{
  "schema": "mcp.pack.manifest.v1",
  "pack_id": "zai_web_search",
  "server": {
    "kind": "remote_streamable_http",
    "endpoint_ref": "ZAI_MCP_SEARCH_URL",
    "auth_ref": "ZAI_MCP_AUTH",
    "official": true,
    "notes": "Z.AI official, Coding-Plan-gated"
  },
  "epoch": "2026-09-04T00:00:00Z",
  "epoch_sha256_16": "<sha256 of canonical tools array, first 16 hex>",
  "tools": [
    {
      "name": "web_search",
      "order": 0,
      "tier": "perception",
      "mode": "read_only",
      "quota": { "unit": "credits", "per_call": 1.2 },
      "cache": { "policy": "allow", "key": "tenant+tool_version+canonical_args+source_rev+auth_scope" }
    }
  ]
}
```

Field rules:
- `tools[].order` — the tool's index in the pack's deterministic `tools/list` ordering.
  Ordering is frozen per epoch. (External validation: the MCP specification itself
  recommends deterministic tools/list ordering for client caching and LLM prompt-cache
  hits — `docs/ref/GLM_K8S_MCP_DEEP_RESEARCH_20260826.md`.)
- `tools[].tier` — exactly one of `perception` (read-only senses) or `hands`
  (write-capable). No tool is untyped.
- `tools[].mode` — `read_only` | `write`. A `perception` tool MUST be `read_only`;
  a `hands` tool MAY be either (e.g. a file-write hand vs a no-op probe hand).
- `tools[].quota.per_call` — the per-call credit weight the gate charges (section 5).
  Absent = unmetered = the gate REFUSES the call (fail-close; unknown cost is a denial,
  not a free pass).
- `tools[].cache.policy` — `allow` only for `read_only` tools. `write` tools carry
  `cache: {policy: "never"}` plus `invalidate: "publish"` (section 6).

## 3. EPOCH-PINNING — the byte-stable rule

1. A pack manifest is FROZEN at an epoch: `epoch` (ISO timestamp) +
   `epoch_sha256_16` (sha256 over the canonical `tools` array, first 16 hex chars —
   house digest format).
2. Between epochs, NOTHING in `tools` (names, descriptions, schemas, order, tier,
   quota) may change. Edits happen only at epoch windows — the same law as the frozen
   prefix (editing a frozen manifest taxes every consumer's cache, the billing-CSV-era
   lesson, lessons.jsonl).
3. Consumers do not reference "the latest pack" — they reference
   `<pack_id>@<epoch_sha256_16>`. A lane pinned to a retired epoch fails the spawn
   check until the manager re-pins it (section 8).
4. Epoch changes publish a diff row to the pack's surface (what changed, why, which
   consumers must re-pin).

## 4. PERCEPTION TIERING

- **`perception` packs** (read-only: vision/OCR, web search, web reader, repo read) —
  bindable by ANY lane, including quantized/flash/edge tiers and dumb swarms.
- **`hands` tools** — bindable ONLY by the primary planner lane (and lanes the operator
  explicitly endows with hands in their manifest). Quantized tiers never get hands.
- The gate enforces this structurally: a spawn request from a lane whose model tier is
  below the planner tier and whose pack list contains `hands` tools is refused at spawn,
  not warned at runtime.

## 5. QUOTA GATE — per-call credit weights

- Every manifest'd tool call passes a PRE-CALL gate: lane budget minus outstanding
  charges >= `quota.per_call`, else the call is refused (fail-close) and the refusal is
  receipted.
- Cited weight from the GO: **web search 1.2 credits/call** — the operator's example of
  why: "or their eyes eat the judgment lanes' 5h pool." Perception is cheap per call and
  ruinous per thousand.
- Each gated call appends a receipt row (tool, lane, cost, ts). No receipt = never
  happened (the coverage thesis; lane contract clause 6).
- Budgets live with the lane (lane contract clause 8 budget guards), not in the pack —
  the pack prices, the lane pays.

## 6. FAIL-CLOSE CARRYOVER — the cache rule

- Never cache privileged results by argument equality. A `write`/`hands` result is
  NEVER replayed from cache; a cached perception result is keyed on the full
  deterministic key (section 2 `cache.key`), and any auth-scope or source-rev change
  misses the key.
- Ambiguity fails closed: unknown tool, unknown tier, unknown quota, stale epoch →
  refuse + receipt.

## 7. SURFACES REGISTRATION

The local Vision stdio server (the only LOCAL pack at spec time) gets a row in
`docs/ref/SURFACES.md` (senses section): name, stdio transport, auth scope, status
source. Remote Z.AI servers are surfaced through their packs, not SURFACES rows.
REGISTRATION IS PART OF THE BUILD, not an afterthought — the surface-door law.

## 8. SIGNING / CHECK STEPS (the enforcement checklist)

Spawn-time (lane agent boot):
1. Read lane manifest (`queue/lanes/<name>/manifest.md`) — once, at spawn, never at
   runtime (lane contract clause 1).
2. Resolve each `mcp_whitelist` entry to `docs/ref/mcp_packs/<pack_id>.manifest.json@<epoch_sha256_16>`.
3. Verify the pack file's canonical hash matches the pinned `epoch_sha256_16`. Mismatch
   or missing → REFUSE SPAWN (fail-close) + receipt naming the bad pin.
4. Verify tier rules (section 4) against the lane's model tier.

Runtime (every tool call):
5. Gate: tier check → quota check → execute → receipt append. Refusals receipt too.
6. No lane may call a server absent from its whitelist; the adapter surface simply does
   not expose it (model-pin isolation applied to tools — lane charter clause 5).

Epoch change (manager GO only):
7. New manifest committed under new epoch hash; old epoch marked retired; affected lane
   manifests re-pinned by explicit manager edit; diffs published (section 3.4).

## 9. FIRST CONSUMERS — the lane manifests bind packs

The seven `queue/lanes/<name>/manifest.md` files (chartered 2026-09-04,
`watch/RESEARCH_LANE_ARCHITECTURE_20260904.md` clause 5) are this spec's first
consumers. Their `mcp_whitelist:` lines graduate from bare server names to pinned
references as packs are authored:

| Lane | whitelist today (bare) | pins when packs exist |
|---|---|---|
| Day Work | mag, web_reader | + `zai_web_reader@<hash>` |
| Builder | mag, github | hands-tier for the build planner only |
| Bard/Ledger | mag blackboard, cloudbase | hands-tier (writes state) |
| Elder | mag research-swarm, web_reader, image_search | perception only — "reads, synthesizes, never clicks" |
| Research | mag research, browser_use, node_repl | the ONLY lane that clicks (hands: browser) |
| Android Surface | android-emulator, computer-use, vision | embodied hands — AX-first law |
| Economist | mag run_python, mimosa | read-only metering |

`mag` itself is a pack (the house stdio suite) and gets a manifest like any other —
no server is above the gate.

## 10. OUT OF SCOPE (GO wording)

Distributed cache-tier machinery — Redis tiers, hashing, single-flight — is OUT.
Rocinante blueprint only.

## 11. RELATED DOCTRINE

- **Capability-endowment doctrine** — "senses for the blind, GPS for the stateless,
  hands for the tool-less": `memory/improve/orphan-o3-endowment-doctrine-2026-09-04.md`.
  Perception tiering (section 4) IS that doctrine made enforceable.
- **THE LIVE-CADENCE RULING** (operator, 2026-09-03, sess_95e7f98a "Teasing Out Salon
  Systems", twice in a row): *"there is no baking anymore"* / *"we do it live"* —
  context: salon/campaign operation. RULES OUT: offline/batch pre-compiled passes, baked
  stale history, work teed up against a snapshot instead of the live surface. RULES IN:
  live cadence — the system runs and is corrected live; feeds wire to real events NOW,
  gates verify against the live tip, digests diff live surfaces. This spec obeys it:
  the gate receipts every live call; nothing is pre-baked against a cached world.
  Tri-state: Supported (verbatim in session; absence on record surfaces verified
  2026-09-04, folded here from orphan #O5).

## TRI-STATE

- The GO + pinned requirements: **Supported** (CONVO verbatim + session extract;
  absence grep-verified in the orphan pass).
- Lane-manifest binding: **Supported as design** (charter clause 5, 3-witness salon),
  **Unproven as wiring** — no lane agent has yet spawned under a pinned whitelist.
- Quota weights: the 1.2 credits/call web-search figure is **Supported as the
  operator-cited example**; all other per-tool weights are **Unproven until metered**
  by the economist lane.
- The spawn-refusal / epoch-retirement paths: **Unproven** — designed, never fired
  (same blind spot as the lane kill-switch; test the death path FIRST).

*— drafted by the zcode seat (Max) from the Aug-26 GO, 2026-09-04. Attack pass owed under
the burn protocol.*
