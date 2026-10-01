# INSIGHTS — what MCP actually IS, and what it does NOT give us (Ponytail fold, 2026-09-04)

Read from the mirrored bytes: spec revision **2026-07-28** (current release;
`schema/2026-07-28/schema.ts` is the authoritative definition — the spec says
so). This is the read-the-manual paydirt for the fleet's senses-aisle problem
(watch/SOCRATIC_MCP_BRIEF_20260904.md, INTAKE_MCP_AWESOME_20260904.md).

## 1. What MCP IS

**One sentence:** an open protocol, built on JSON-RPC 2.0, that standardizes
how an LLM application (the HOST) connects to capability providers (SERVERS)
through per-server connectors (CLIENTS, 1:1 with servers).

**Architecture (spec/architecture).** Host = container + coordinator: creates
clients, controls permissions and lifecycle, enforces consent and security
policy, owns the LLM and the context aggregation. Client = one server's
connector: routes messages bidirectionally, maintains the security boundary
between servers. Server = focused capability provider: exposes primitives,
requests user input only through the host. **Design law #3 in the spec:
servers should not be able to read the whole conversation, nor see into other
servers.** That is the spec-level justification for the fleet's lane-whitelist
pattern (per-lane MCP subsets in the room's own architecture fold).

**Transports (spec/transports).** Exactly two standard bindings:
- **stdio** — client launches the server as a subprocess; newline-delimited
  JSON-RPC over stdin/stdout; stderr free for logs; nothing else may touch
  stdout. This is how our loopback-only fleet runs nearly everything.
- **Streamable HTTP** — every message is its own POST to ONE MCP endpoint;
  reply is a JSON object or a request-scoped SSE stream. In 2026-07-28 the
  GET stream and protocol-level sessions were REMOVED (stateless era); servers
  MUST validate `Origin` (DNS-rebinding defense).
- Custom transports are explicitly allowed; the framing rules are portable.

**The primitives (the capabilities matrix):**

| Primitive | Direction | Who controls it | Core operations |
|---|---|---|---|
| Tools | server → model | MODEL-controlled (auto-invoked) | tools/list, tools/call; JSON-Schema inputs; annotations (readOnly/destructive hints) |
| Resources | server → host/app | APPLICATION-driven | resources/list, read, templates; subscribe via subscriptions/listen |
| Prompts | server → user | USER-controlled (slash commands) | prompts/list, prompts/get with args |
| Elicitation | server → user via client | server asks, user answers | form mode (JSON Schema) vs URL mode (sensitive data) |
| Roots | client → server | client declares scope | roots/list — filesystem/URI scopes |
| Sampling | server → client's LLM | host mediates | sampling/createMessage — **DEPRECATED 2026-07-28 (SEP-2577)** |

**The 2026-07-28 sea change (read this before adopting anything new):** the
"modern" era is STATELESS. No initialize handshake — every request carries its
protocol version + client info + capabilities in `_meta` fields; the server
accepts or rejects each request independently
(`UnsupportedProtocolVersionError`); `server/discover` returns versions +
capabilities + identity in one call and doubles as the stdio legacy probe.
Server-to-client requests (sampling, elicitation, roots) now ride INSIDE
results as `input_required` via **MRTR** — the old server-initiated request
pattern is gone (breaking change). Extensions (Tasks, MCP Apps,
Skills-over-MCP) are opt-in and negotiated per request. Practical consequence:
**SDK v2s exist because the protocol changed shape**; the fleet's 9 live
servers mostly speak the LEGACY handshake era, and a modern client must be
dual-era (stdio: send server/discover first, fall back to initialize).

## 2. Security considerations IN THE SPEC (not folklore — MUST-level text)

- **Human in the loop**: for tools and (legacy) sampling, applications SHOULD
  provide UI showing what the model can invoke, indicators on invocation, and
  confirmation prompts. The protocol puts consent in the HOST, by design.
- **OAuth 2.1 for HTTP transports**, with RFC 8707 resource indicators:
  clients MUST send `resource`; servers MUST validate token audience; **token
  passthrough is explicitly forbidden** (confused-deputy defense); short-lived
  tokens, refresh rotation for public clients.
- **Elicitation**: servers MUST NOT request secrets (passwords, API keys,
  tokens, payment credentials) via form mode — such interactions MUST use URL
  mode, keeping the secret out of the MCP client entirely. (Fleet parallel:
  secrets-never-echoed.)
- **Streamable HTTP**: Origin validation mandatory (DNS rebinding); local
  servers should bind appropriately; authorization is separate from transport.
- **Sampling deprecation is itself a security decision**: routing server LLM
  calls through the host was a consent chokepoint the ecosystem is dropping in
  favor of servers using provider APIs directly — meaning the HOST's oversight
  shrinks and OUR per-lane whitelists matter more, not less.

## 3. What the spec does NOT solve — why our aisle-triage problem exists

1. **Discovery ≠ trust.** The protocol defines how to talk to a server, not
   whether to. There is no ranking, no security certification, no provenance
   in-band. The MCP Registry (registry.modelcontextprotocol.io) is a separate
   service and a LIST, not a verdict. 3,838 servers in the catalogs, zero
   specification-level signal for "safe to adopt." **The fleet's adoption
   organ (server → Mimosa security pass → SKILL.md pairing → room receipt →
   liveness falsifier) is therefore NOT a nice-to-have; the spec has no
   substitute for it.** Aisle triage is ours to build, exactly as the salon
   concluded.
2. **No identity/attestation layer.** Nothing in-band proves a server is who
   it claims to be across updates; supply-chain warnings in the spec's own
   security pages are advisory, not mechanical.
3. **No orchestration.** Cross-server composition, shared context, and
   sequencing are HOST duties, deliberately unspecified. The room, not MCP,
   is our conductor.
4. **No quality contract.** Capability negotiation says WHAT a server can do,
   nothing about how well; annotations are self-declared hints. Liveness and
   fidelity checks (our falsifier pattern) remain external.
5. **Version churn is real.** 2026-07-28 deprecates sampling and deletes
   sessions; mirrors and adoption decisions rot on a spec-revision clock.
   Mirror date stamps are load-bearing.

## 4. What the fleet gets FOR FREE from the spec

- **The aisle vocabulary**: 59 community categories map cleanly onto the six
  primitives — "search server" = tools; "memory server" = resources; "prompt
  library" = prompts. Triage by primitive first, category second.
- **Capability negotiation = a free liveness probe**: `server/discover` (or a
  legacy `initialize`) is the falsifier for "this server is alive and offers
  what its card claims" — write it as the adoption organ's check step.
- **stdio as the default posture fits the loopback law**: subprocess servers
  never open a port; Streamable HTTP only where a cloud BaaS demands it.
- **The consent boundary has a spec address**: host-side approval before
  tools/call maps 1:1 onto the room's gate pattern (KEYS/spend/operator GO).

**Bottom line:** MCP gives the fleet WIRE FORMATS and a CONSENT ARCHITECTURE;
it gives zero TRUST and zero DISCOVERY. Everything the operator called the
aisle problem lives in the gap — and the gap is buildable with organs we
already run (Mimosa, skills, room receipts, falsifiers).
