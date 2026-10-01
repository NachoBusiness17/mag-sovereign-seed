# MCP DOCS MIRROR — INDEX

> **Provenance:** mirrored from github.com/modelcontextprotocol (the repo that builds modelcontextprotocol.io).
> **Mirror date:** 2026-09-04. **Spec revision mirrored:** 2026-07-28 (current release).
> **Doors used:** (1) api.github.com git-trees (recursive) — 950 blobs enumerated, local parse; (2) raw.githubusercontent.com literal per-file pulls — 38/38 HTTP 200, zero FAILs on fetched set; (3) three SDK repos' README.md via raw door.
> **License note:** spec + docs are MIT/CC (modelcontextprotocol repos); mirrored for internal fleet use only. Do not republish or feed to external parties; internal reference shelf per the wall-ledger law.

**Coverage:** 38 files, 1,349,598 bytes. Spec 2026-07-28: all 31 protocol pages + changelog + deprecated registry; schema.ts + schema.json + schema.mdx; python-sdk / typescript-sdk / servers READMEs; upstream README. The site modelcontextprotocol.io is built from this same repo — these bytes ARE the manuals.

**Fetch log:** `_raw/fetch_log.txt` (status code + literal URL + local path per file). Generator: `_raw/gen_fetch.py` (emits bash with literal URLs; no parameterized fetch at runtime).

**Known gaps (honest FAIL lines):**
- FAIL (not mirrored): docs/extensions/* (Tasks, Apps, Skills-over-MCP) — NOT mirrored this pass; separate subtree, next extension pass
- FAIL (not mirrored): seps/* (43 SEP documents incl. SEP-2322 MRTR, SEP-2577 sampling-deprecation) — NOT mirrored; cited by spec pages
- FAIL (not mirrored): docs/community/* (security best practices beyond spec, working groups incl. skills-over-mcp) — NOT mirrored this pass
- FAIL (not mirrored): blog/* (104 files), earlier spec revisions 2024-11-05 / 2025-03-26 / 2025-11-25 / 2026-07-28 drafts under docs/docs/ — NOT mirrored (one current revision is the working set)

---

## (root)

- `README.upstream.md` — Upstream repo README: spec + schema (TypeScript-first, JSON Schema generated) + docs (876 bytes) [source](https://raw.githubusercontent.com/modelcontextprotocol/modelcontextprotocol/main/README.md)

## spec/2026-07-28/ — the specification

- `spec/2026-07-28/architecture/index.mdx` — Client-host-server architecture: host owns consent/security/LLM integration, client is 1:1 with a server, servers never see the whole conversation (6,195 bytes) [source](https://raw.githubusercontent.com/modelcontextprotocol/modelcontextprotocol/main/docs/specification/2026-07-28/architecture/index.mdx)
- `spec/2026-07-28/basic/authorization/authorization-server-discovery.mdx` — How a client finds the authorization server (protected resource metadata, WWW-Authenticate) (7,969 bytes) [source](https://raw.githubusercontent.com/modelcontextprotocol/modelcontextprotocol/main/docs/specification/2026-07-28/basic/authorization/authorization-server-discovery.mdx)
- `spec/2026-07-28/basic/authorization/client-registration.mdx` — Dynamic + pre-registered client registration flows against the authorization server (10,016 bytes) [source](https://raw.githubusercontent.com/modelcontextprotocol/modelcontextprotocol/main/docs/specification/2026-07-28/basic/authorization/client-registration.mdx)
- `spec/2026-07-28/basic/authorization/index.mdx` — OAuth 2.1 framework for HTTP transports: server discovery, client registration, RFC 8707 resource parameter, token audience binding (25,683 bytes) [source](https://raw.githubusercontent.com/modelcontextprotocol/modelcontextprotocol/main/docs/specification/2026-07-28/basic/authorization/index.mdx)
- `spec/2026-07-28/basic/authorization/security-considerations.mdx` — MUST-level OAuth security: token audience validation, no token passthrough, theft/leak mitigations, confused-deputy defenses (9,954 bytes) [source](https://raw.githubusercontent.com/modelcontextprotocol/modelcontextprotocol/main/docs/specification/2026-07-28/basic/authorization/security-considerations.mdx)
- `spec/2026-07-28/basic/index.mdx` — Base protocol: JSON-RPC 2.0 message types, per-request _meta (version+clientInfo+capabilities), resultType envelope, MRTR input_required results (25,149 bytes) [source](https://raw.githubusercontent.com/modelcontextprotocol/modelcontextprotocol/main/docs/specification/2026-07-28/basic/index.mdx)
- `spec/2026-07-28/basic/patterns/cancellation.mdx` — notifications/cancelled: best-effort, in-flight only, receiver discretion (4,428 bytes) [source](https://raw.githubusercontent.com/modelcontextprotocol/modelcontextprotocol/main/docs/specification/2026-07-28/basic/patterns/cancellation.mdx)
- `spec/2026-07-28/basic/patterns/index.mdx` — The three message patterns: request/response, multi round-trip requests (MRTR), subscribe/notify (2,957 bytes) [source](https://raw.githubusercontent.com/modelcontextprotocol/modelcontextprotocol/main/docs/specification/2026-07-28/basic/patterns/index.mdx)
- `spec/2026-07-28/basic/patterns/mrtr.mdx` — MRTR: server-to-client requests (sampling/elicitation/roots) ride results as input requests; replaces server-initiated requests — breaking change (13,386 bytes) [source](https://raw.githubusercontent.com/modelcontextprotocol/modelcontextprotocol/main/docs/specification/2026-07-28/basic/patterns/mrtr.mdx)
- `spec/2026-07-28/basic/patterns/progress.mdx` — notifications/progress with progressToken: rate guidance and races vs final response (2,495 bytes) [source](https://raw.githubusercontent.com/modelcontextprotocol/modelcontextprotocol/main/docs/specification/2026-07-28/basic/patterns/progress.mdx)
- `spec/2026-07-28/basic/patterns/subscriptions.mdx` — subscriptions/listen: long-lived change notifications delivered on a request's response stream (list changes, resource updates) (6,101 bytes) [source](https://raw.githubusercontent.com/modelcontextprotocol/modelcontextprotocol/main/docs/specification/2026-07-28/basic/patterns/subscriptions.mdx)
- `spec/2026-07-28/basic/transports/index.mdx` — Transport = binding: framing + delivery only; protocol semantics identical on every binding; custom transports defined (4,059 bytes) [source](https://raw.githubusercontent.com/modelcontextprotocol/modelcontextprotocol/main/docs/specification/2026-07-28/basic/transports/index.mdx)
- `spec/2026-07-28/basic/transports/stdio.mdx` — stdio binding: newline-delimited JSON-RPC over a client-launched subprocess's stdin/stdout; stderr free-for logging; backward-compat probe rules (7,172 bytes) [source](https://raw.githubusercontent.com/modelcontextprotocol/modelcontextprotocol/main/docs/specification/2026-07-28/basic/transports/stdio.mdx)
- `spec/2026-07-28/basic/transports/streamable-http.mdx` — Streamable HTTP: every message its own POST to one MCP endpoint; reply = JSON or request-scoped SSE; GET stream and sessions REMOVED in 2026-07-28; Origin validation (31,155 bytes) [source](https://raw.githubusercontent.com/modelcontextprotocol/modelcontextprotocol/main/docs/specification/2026-07-28/basic/transports/streamable-http.mdx)
- `spec/2026-07-28/basic/versioning.mdx` — No handshake: every request carries its version; UnsupportedProtocolVersionError drives per-request negotiation; modern vs legacy eras (11,293 bytes) [source](https://raw.githubusercontent.com/modelcontextprotocol/modelcontextprotocol/main/docs/specification/2026-07-28/basic/versioning.mdx)
- `spec/2026-07-28/changelog.mdx` — 2026-07-28 revision changes: stateless _meta era, MRTR, sessions removed, sampling deprecated (11,719 bytes) [source](https://raw.githubusercontent.com/modelcontextprotocol/modelcontextprotocol/main/docs/specification/2026-07-28/changelog.mdx)
- `spec/2026-07-28/client/elicitation.mdx` — Elicitation: server asks the user for input via the client; form mode (JSON Schema) vs URL mode (sensitive data MUST go URL mode, never through the client) (28,212 bytes) [source](https://raw.githubusercontent.com/modelcontextprotocol/modelcontextprotocol/main/docs/specification/2026-07-28/client/elicitation.mdx)
- `spec/2026-07-28/client/roots.mdx` — Roots: client-declared filesystem/URI scopes servers should operate within (4,471 bytes) [source](https://raw.githubusercontent.com/modelcontextprotocol/modelcontextprotocol/main/docs/specification/2026-07-28/client/roots.mdx)
- `spec/2026-07-28/client/sampling.mdx` — Sampling: server requests LLM completions via the client — DEPRECATED as of 2026-07-28 (SEP-2577); migrate to direct LLM provider APIs (21,815 bytes) [source](https://raw.githubusercontent.com/modelcontextprotocol/modelcontextprotocol/main/docs/specification/2026-07-28/client/sampling.mdx)
- `spec/2026-07-28/deprecated.mdx` — Deprecated-features registry and lifecycle (sampling and friends; 12-month minimum retention) (5,031 bytes) [source](https://raw.githubusercontent.com/modelcontextprotocol/modelcontextprotocol/main/docs/specification/2026-07-28/deprecated.mdx)
- `spec/2026-07-28/index.mdx` — Spec front page: what MCP is, hosts/clients/servers, MUST/SHOULD BCP-14 terms, extensions (Tasks, Skills-over-MCP, MCP Apps), the security warning block (5,694 bytes) [source](https://raw.githubusercontent.com/modelcontextprotocol/modelcontextprotocol/main/docs/specification/2026-07-28/index.mdx)
- `spec/2026-07-28/schema.mdx` — Auto-generated schema reference page for 2026-07-28 (the big one: every type, request, notification) (726,080 bytes) [source](https://raw.githubusercontent.com/modelcontextprotocol/modelcontextprotocol/main/docs/specification/2026-07-28/schema.mdx)
- `spec/2026-07-28/server/discover.mdx` — server/discover: one call returning supported versions, capabilities, identity, instructions — the stdio backward-compat probe; servers MUST implement (3,636 bytes) [source](https://raw.githubusercontent.com/modelcontextprotocol/modelcontextprotocol/main/docs/specification/2026-07-28/server/discover.mdx)
- `spec/2026-07-28/server/index.mdx` — Server features index: resources (application-driven), prompts (user-controlled), tools (model-controlled) + utilities (1,593 bytes) [source](https://raw.githubusercontent.com/modelcontextprotocol/modelcontextprotocol/main/docs/specification/2026-07-28/server/index.mdx)
- `spec/2026-07-28/server/prompts.mdx` — Prompts: user-controlled templates (slash commands); prompts/list + prompts/get with arguments (9,490 bytes) [source](https://raw.githubusercontent.com/modelcontextprotocol/modelcontextprotocol/main/docs/specification/2026-07-28/server/prompts.mdx)
- `spec/2026-07-28/server/resources.mdx` — Resources: URI-identified context data, application-driven inclusion; listChanged + subscribe capability flags; resource templates (12,958 bytes) [source](https://raw.githubusercontent.com/modelcontextprotocol/modelcontextprotocol/main/docs/specification/2026-07-28/server/resources.mdx)
- `spec/2026-07-28/server/tools.mdx` — Tools: model-controlled function invocation; tools/list + tools/call; JSON Schema input; output schemas; human-in-the-loop SHOULD; tool annotations (hints, readOnly/destructive) (23,788 bytes) [source](https://raw.githubusercontent.com/modelcontextprotocol/modelcontextprotocol/main/docs/specification/2026-07-28/server/tools.mdx)
- `spec/2026-07-28/server/utilities/caching.mdx` — Caching utility: ttlMs + cacheScope on discoverable results (8,996 bytes) [source](https://raw.githubusercontent.com/modelcontextprotocol/modelcontextprotocol/main/docs/specification/2026-07-28/server/utilities/caching.mdx)
- `spec/2026-07-28/server/utilities/completion.mdx` — Argument autocompletion for prompt/resource template arguments (5,350 bytes) [source](https://raw.githubusercontent.com/modelcontextprotocol/modelcontextprotocol/main/docs/specification/2026-07-28/server/utilities/completion.mdx)
- `spec/2026-07-28/server/utilities/logging.mdx` — RFC-5424-level logging notifications to clients (4,476 bytes) [source](https://raw.githubusercontent.com/modelcontextprotocol/modelcontextprotocol/main/docs/specification/2026-07-28/server/utilities/logging.mdx)
- `spec/2026-07-28/server/utilities/pagination.mdx` — Opaque-cursor pagination across all list operations (2,994 bytes) [source](https://raw.githubusercontent.com/modelcontextprotocol/modelcontextprotocol/main/docs/specification/2026-07-28/server/utilities/pagination.mdx)

## schema/ — the protocol contract

- `schema/schema.json` — JSON Schema generated from schema.ts — machine-readable protocol contract (181,474 bytes) [source](https://raw.githubusercontent.com/modelcontextprotocol/modelcontextprotocol/main/schema/2026-07-28/schema.json)
- `schema/schema.mdx` — Schema doc page source (2026-07-28) (1,771 bytes) [source](https://raw.githubusercontent.com/modelcontextprotocol/modelcontextprotocol/main/schema/2026-07-28/schema.mdx)
- `schema/schema.ts` — Authoritative TypeScript schema for 2026-07-28 — the spec is DEFINED here first (98,426 bytes) [source](https://raw.githubusercontent.com/modelcontextprotocol/modelcontextprotocol/main/schema/2026-07-28/schema.ts)

## sdks/python-sdk/

- `sdks/python-sdk/README.md` — MCP Python SDK v2 (MIT): FastMCP-style servers, client sessions, transport support (5,724 bytes) [source](https://raw.githubusercontent.com/modelcontextprotocol/python-sdk/main/README.md)

## sdks/typescript-sdk/

- `sdks/typescript-sdk/README.md` — MCP TypeScript SDK v2 (@modelcontextprotocol/server|client), implements the 2026-07-28 spec (8,305 bytes) [source](https://raw.githubusercontent.com/modelcontextprotocol/typescript-sdk/main/README.md)

## sdks/servers/

- `sdks/servers/README.md` — Reference servers repo — now points to the MCP Registry as the canonical browse surface; repo is deprecated for listings (8,707 bytes) [source](https://raw.githubusercontent.com/modelcontextprotocol/servers/main/README.md)
