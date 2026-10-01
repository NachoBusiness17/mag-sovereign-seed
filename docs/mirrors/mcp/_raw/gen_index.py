"""Generate docs/mirrors/mcp/INDEX.md from the local mirror tree.

Local files only. Purposes are hand-written one-liners keyed by path.
"""
import os
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

RAW = "https://raw.githubusercontent.com/modelcontextprotocol/modelcontextprotocol/main/"
V = "2026-07-28"

PURPOSE = {
    "spec/2026-07-28/index.mdx": "Spec front page: what MCP is, hosts/clients/servers, MUST/SHOULD BCP-14 terms, extensions (Tasks, Skills-over-MCP, MCP Apps), the security warning block",
    "spec/2026-07-28/architecture/index.mdx": "Client-host-server architecture: host owns consent/security/LLM integration, client is 1:1 with a server, servers never see the whole conversation",
    "spec/2026-07-28/basic/index.mdx": "Base protocol: JSON-RPC 2.0 message types, per-request _meta (version+clientInfo+capabilities), resultType envelope, MRTR input_required results",
    "spec/2026-07-28/basic/versioning.mdx": "No handshake: every request carries its version; UnsupportedProtocolVersionError drives per-request negotiation; modern vs legacy eras",
    "spec/2026-07-28/basic/patterns/index.mdx": "The three message patterns: request/response, multi round-trip requests (MRTR), subscribe/notify",
    "spec/2026-07-28/basic/patterns/mrtr.mdx": "MRTR: server-to-client requests (sampling/elicitation/roots) ride results as input requests; replaces server-initiated requests — breaking change",
    "spec/2026-07-28/basic/patterns/cancellation.mdx": "notifications/cancelled: best-effort, in-flight only, receiver discretion",
    "spec/2026-07-28/basic/patterns/progress.mdx": "notifications/progress with progressToken: rate guidance and races vs final response",
    "spec/2026-07-28/basic/patterns/subscriptions.mdx": "subscriptions/listen: long-lived change notifications delivered on a request's response stream (list changes, resource updates)",
    "spec/2026-07-28/basic/transports/index.mdx": "Transport = binding: framing + delivery only; protocol semantics identical on every binding; custom transports defined",
    "spec/2026-07-28/basic/transports/stdio.mdx": "stdio binding: newline-delimited JSON-RPC over a client-launched subprocess's stdin/stdout; stderr free-for logging; backward-compat probe rules",
    "spec/2026-07-28/basic/transports/streamable-http.mdx": "Streamable HTTP: every message its own POST to one MCP endpoint; reply = JSON or request-scoped SSE; GET stream and sessions REMOVED in 2026-07-28; Origin validation",
    "spec/2026-07-28/basic/authorization/index.mdx": "OAuth 2.1 framework for HTTP transports: server discovery, client registration, RFC 8707 resource parameter, token audience binding",
    "spec/2026-07-28/basic/authorization/authorization-server-discovery.mdx": "How a client finds the authorization server (protected resource metadata, WWW-Authenticate)",
    "spec/2026-07-28/basic/authorization/client-registration.mdx": "Dynamic + pre-registered client registration flows against the authorization server",
    "spec/2026-07-28/basic/authorization/security-considerations.mdx": "MUST-level OAuth security: token audience validation, no token passthrough, theft/leak mitigations, confused-deputy defenses",
    "spec/2026-07-28/server/index.mdx": "Server features index: resources (application-driven), prompts (user-controlled), tools (model-controlled) + utilities",
    "spec/2026-07-28/server/tools.mdx": "Tools: model-controlled function invocation; tools/list + tools/call; JSON Schema input; output schemas; human-in-the-loop SHOULD; tool annotations (hints, readOnly/destructive)",
    "spec/2026-07-28/server/resources.mdx": "Resources: URI-identified context data, application-driven inclusion; listChanged + subscribe capability flags; resource templates",
    "spec/2026-07-28/server/prompts.mdx": "Prompts: user-controlled templates (slash commands); prompts/list + prompts/get with arguments",
    "spec/2026-07-28/server/discover.mdx": "server/discover: one call returning supported versions, capabilities, identity, instructions — the stdio backward-compat probe; servers MUST implement",
    "spec/2026-07-28/server/utilities/caching.mdx": "Caching utility: ttlMs + cacheScope on discoverable results",
    "spec/2026-07-28/server/utilities/completion.mdx": "Argument autocompletion for prompt/resource template arguments",
    "spec/2026-07-28/server/utilities/logging.mdx": "RFC-5424-level logging notifications to clients",
    "spec/2026-07-28/server/utilities/pagination.mdx": "Opaque-cursor pagination across all list operations",
    "spec/2026-07-28/client/elicitation.mdx": "Elicitation: server asks the user for input via the client; form mode (JSON Schema) vs URL mode (sensitive data MUST go URL mode, never through the client)",
    "spec/2026-07-28/client/sampling.mdx": "Sampling: server requests LLM completions via the client — DEPRECATED as of 2026-07-28 (SEP-2577); migrate to direct LLM provider APIs",
    "spec/2026-07-28/client/roots.mdx": "Roots: client-declared filesystem/URI scopes servers should operate within",
    "spec/2026-07-28/schema.mdx": "Auto-generated schema reference page for 2026-07-28 (the big one: every type, request, notification)",
    "spec/2026-07-28/changelog.mdx": "2026-07-28 revision changes: stateless _meta era, MRTR, sessions removed, sampling deprecated",
    "spec/2026-07-28/deprecated.mdx": "Deprecated-features registry and lifecycle (sampling and friends; 12-month minimum retention)",
    "schema/schema.ts": "Authoritative TypeScript schema for 2026-07-28 — the spec is DEFINED here first",
    "schema/schema.json": "JSON Schema generated from schema.ts — machine-readable protocol contract",
    "schema/schema.mdx": "Schema doc page source (2026-07-28)",
    "sdks/python-sdk/README.md": "MCP Python SDK v2 (MIT): FastMCP-style servers, client sessions, transport support",
    "sdks/typescript-sdk/README.md": "MCP TypeScript SDK v2 (@modelcontextprotocol/server|client), implements the 2026-07-28 spec",
    "sdks/servers/README.md": "Reference servers repo — now points to the MCP Registry as the canonical browse surface; repo is deprecated for listings",
    "README.upstream.md": "Upstream repo README: spec + schema (TypeScript-first, JSON Schema generated) + docs",
}

# Paths mirrored but not locally re-fetched in this pass get honest FAIL lines here.
FAILS = [
    "docs/extensions/* (Tasks, Apps, Skills-over-MCP) — NOT mirrored this pass; separate subtree, next extension pass",
    "seps/* (43 SEP documents incl. SEP-2322 MRTR, SEP-2577 sampling-deprecation) — NOT mirrored; cited by spec pages",
    "docs/community/* (security best practices beyond spec, working groups incl. skills-over-mcp) — NOT mirrored this pass",
    "blog/* (104 files), earlier spec revisions 2024-11-05 / 2025-03-26 / 2025-11-25 / 2026-07-28 drafts under docs/docs/ — NOT mirrored (one current revision is the working set)",
]

rows = []
for root, ds, fs in os.walk("."):
    if "_raw" in root or "INDEX.md" in fs and root != ".":
        pass
    if "_raw" in root:
        continue
    for f in fs:
        p = os.path.join(root, f)
        rel = os.path.relpath(p, ".").replace(os.sep, "/")
        if rel == "INDEX.md":
            continue
        rows.append((rel, os.path.getsize(p)))
rows.sort()

groups = {}
for rel, size in rows:
    if rel.startswith("spec/"):
        key = "spec/" + rel.split("/")[1]
    elif rel.startswith(("sdks/", "schema/")):
        key = rel.split("/")[0] + ("/" + rel.split("/")[1] if rel.startswith("sdks/") else "")
    else:
        key = "(root)"
    groups.setdefault(key, []).append((rel, size))

def src(rel):
    if rel.startswith("spec/"):
        return RAW + "docs/specification/" + rel[len("spec/"):]
    if rel.startswith("schema/"):
        return RAW + "schema/" + V + "/" + rel.split("/")[-1]
    if rel.startswith("sdks/"):
        repo = rel.split("/")[1]
        return "https://raw.githubusercontent.com/modelcontextprotocol/" + repo + "/main/README.md"
    if rel == "README.upstream.md":
        return RAW + "README.md"
    return "?"

out = io.StringIO()
w = out.write
w("# MCP DOCS MIRROR — INDEX\n\n")
w("> **Provenance:** mirrored from github.com/modelcontextprotocol (the repo that builds modelcontextprotocol.io).\n")
w("> **Mirror date:** 2026-09-04. **Spec revision mirrored:** %s (current release).\n" % V)
w("> **Doors used:** (1) api.github.com git-trees (recursive) — 950 blobs enumerated, local parse; "
  "(2) raw.githubusercontent.com literal per-file pulls — 38/38 HTTP 200, zero FAILs on fetched set; "
  "(3) three SDK repos' README.md via raw door.\n")
w("> **License note:** spec + docs are MIT/CC (modelcontextprotocol repos); mirrored for internal fleet use only. "
  "Do not republish or feed to external parties; internal reference shelf per the wall-ledger law.\n\n")
tot = sum(s for _, s in rows)
w("**Coverage:** %d files, %s bytes. Spec %s: all 31 protocol pages + changelog + deprecated registry; "
  "schema.ts + schema.json + schema.mdx; python-sdk / typescript-sdk / servers READMEs; upstream README. "
  "The site modelcontextprotocol.io is built from this same repo — these bytes ARE the manuals.\n\n"
  % (len(rows), f"{tot:,}", V))
w("**Fetch log:** `_raw/fetch_log.txt` (status code + literal URL + local path per file). "
  "Generator: `_raw/gen_fetch.py` (emits bash with literal URLs; no parameterized fetch at runtime).\n\n")
w("**Known gaps (honest FAIL lines):**\n")
for f in FAILS:
    w("- FAIL (not mirrored): %s\n" % f)
w("\n---\n")

order = ["(root)", "spec/" + V, "schema", "sdks/python-sdk", "sdks/typescript-sdk", "sdks/servers"]
titles = {
    "(root)": "(root)",
    "spec/" + V: "spec/%s/ — the specification" % V,
    "schema": "schema/ — the protocol contract",
    "sdks/python-sdk": "sdks/python-sdk/",
    "sdks/typescript-sdk": "sdks/typescript-sdk/",
    "sdks/servers": "sdks/servers/",
}
for key in order:
    items = groups.get(key, [])
    if not items:
        continue
    w("\n## %s\n\n" % titles[key])
    for rel, size in items:
        purpose = PURPOSE.get(rel, "(unindexed — read and amend)")
        w("- `%s` — %s (%s bytes) [source](%s)\n" % (rel, purpose, f"{size:,}", src(rel)))

open("INDEX.md", "w", encoding="utf-8", newline="\n").write(out.getvalue())
print("INDEX.md written:", len(rows), "files,", tot, "bytes")
