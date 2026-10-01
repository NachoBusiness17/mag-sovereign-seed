"""perplexity_research — deep web research with citations, folded into the corpus.

Perplexity Sonar API: real-time web search + cited sources — the "deep research
elevation and steal" engine. Unlike Grok (closed reasoning), Sonar returns live,
cited findings we can steal mechanisms from (RenderMan / particle physics / Houdini /
ShaderToy / geometric calculus -> flocking + AI interaction).

Requires PERPLEXITY_API_KEY (operator-provided secret — never route through the model).

REMAPPING (REMAP_PATH): Perplexity retires Sonar Chat Completions on 2026-09-27
(perplexity-lab lane, MICKEY17_V2 burn 09-24). The legacy chat route
(route="chat") refuses on/after that date; the post-sunset route is ONE FLAG
AWAY, and it is READY, NOT LIVE (the module is dormant: no key in .env as of
2026-09-25):

  route="search"  POST {SEARCH_URL} — Search API request shape, grounded in
                  docs.perplexity.ai (getting-started + docs/search/quickstart,
                  fetched 2026-09-25). Body: {query: str, max_results: 1-20
                  (default 10), max_tokens (total page-content cap),
                  search_type: "fast" ($1/1k requests; standard $5/1k)}.
                  Response: {id, results: [{title, url, snippet, date,
                  last_updated}], server_time} — normalized here into the same
                  content/citations leaf shape the chat route emitted.
  route="agent"   NAMED remap path, deliberately NOT implemented: the Agent API
                  request shape was not pinned from official docs as of
                  2026-09-25, so this module refuses it rather than inventing
                  one. Pin it before wiring it.

Flag sources: research(..., route="search") | env SONAR_ROUTE=search | CLI
--route search [--fast]. Default stays route="chat": pre-sunset it still posts
the chat shape unchanged; post-sunset it returns remap instructions instead of
calling the dead endpoint.

Transport guard (Mimosa 2026-09-25): every request goes through _OPENER, whose
redirect handler re-validates each hop against an https + exact-host allowlist,
so no caller-controlled or redirected URL can reach urllib.

Schema: perplexity_research.v1
CLI: python -m mag.perplexity_research "<query>" [--model sonar|sonar-pro|sonar-deep-research]
     python -m mag.perplexity_research "<query>" --route search [--fast]
     python -m mag.perplexity_research status
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCHEMA = "perplexity_research.v1"
API_URL = "https://api.perplexity.ai/chat/completions"  # legacy Sonar chat, retired 2026-09-27
SEARCH_URL = "https://api.perplexity.ai/search"  # Search API remap target (REMAP_PATH)
SONAR_CHAT_SUNSET = "2026-09-27"
REMAP_PATH = "search"  # canonical post-sunset route
DEFAULT_ROUTE = "chat"  # dormant legacy route stays default: ready, not live
ROUTE_ENV = "SONAR_ROUTE"  # env override, e.g. SONAR_ROUTE=search
ROUTES: dict[str, str | None] = {"chat": API_URL, "search": SEARCH_URL, "agent": None}
LEAF_DIR = ROOT / "memory" / "runs" / "perplexity"

# SSRF pin: only these exact hosts, https only, redirects re-validated per hop.
ALLOWED_HOSTS = frozenset({"api.perplexity.ai"})

_KEY_ENVS = ("PERPLEXITY_API_KEY", "PPLX_API_KEY")
SYSTEM = (
    "You are a deep research engine. Given a query, return the load-bearing, cited "
    "mechanisms and insights. Prefer concrete, stealable mechanisms over vague overviews. "
    "Always cite sources inline. Be dense and structured."
)


def key() -> str:
    for e in _KEY_ENVS:
        v = os.environ.get(e)
        if v:
            return v
    return ""


def _today() -> str:
    """UTC date, ISO. Tests monkeypatch this to time-travel around the sunset."""
    return datetime.now(timezone.utc).date().isoformat()


def resolve_route(route: str | None = None) -> str:
    """Resolve the effective route: explicit arg > ROUTE_ENV > DEFAULT_ROUTE."""
    r = (route or os.environ.get(ROUTE_ENV) or DEFAULT_ROUTE)
    r = str(r).strip().lower()
    if r not in ROUTES:
        raise ValueError(f"unknown route {r!r}; known routes: {sorted(ROUTES)}")
    return r


def status() -> dict[str, Any]:
    try:
        resolved = resolve_route()
    except ValueError as e:
        resolved = f"INVALID: {e}"
    return {"ok": bool(key()), "has_key": bool(key()),
            "envs": list(_KEY_ENVS), "api_url": API_URL,
            "default_route": DEFAULT_ROUTE, "remap_path": REMAP_PATH,
            "resolved_route": resolved, "route_env": ROUTE_ENV,
            "routes": dict(ROUTES), "sonar_chat_sunset": SONAR_CHAT_SUNSET,
            "note": "set PERPLEXITY_API_KEY to enable deep research"}


def endpoint_blocked(url: str) -> str | None:
    """SSRF guard: reason-string if `url` may not be fetched, else None."""
    try:
        u = urllib.parse.urlsplit(url)
    except ValueError:
        return f"unparseable endpoint URL {url!r}"
    if u.scheme != "https":
        return f"endpoint scheme must be https, got {u.scheme!r}"
    if u.hostname not in ALLOWED_HOSTS:
        return f"endpoint host {u.hostname!r} not in allowlist {sorted(ALLOWED_HOSTS)}"
    return None


class _PinnedRedirect(urllib.request.HTTPRedirectHandler):
    """Refuse redirects that leave the pinned endpoint allowlist."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        blocked = endpoint_blocked(newurl)
        if blocked:
            raise urllib.error.HTTPError(
                newurl, code, f"redirect blocked: {blocked}", headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_OPENER = urllib.request.build_opener(_PinnedRedirect())


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _write_leaf(leaf: dict[str, Any]) -> Path:
    LEAF_DIR.mkdir(parents=True, exist_ok=True)
    p = LEAF_DIR / f"leaf-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.json"
    p.write_text(json.dumps(leaf, ensure_ascii=False, default=str, indent=2),
                 encoding="utf-8")
    return p


def _research_chat(query: str, *, model: str, max_tokens: int,
                   timeout: float) -> dict[str, Any]:
    """Legacy Sonar chat-completions route (default; refuses on/after sunset)."""
    blocked = endpoint_blocked(API_URL)
    if blocked:
        return {"ok": False, "schema": SCHEMA, "route": "chat", "model": model,
                "error": blocked}
    body = {
        "model": model,
        "messages": [{"role": "system", "content": SYSTEM},
                     {"role": "user", "content": (query or "").strip()}],
        "max_tokens": max_tokens,
    }
    req = urllib.request.Request(
        API_URL, data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {key()}"}, method="POST")
    try:
        with _OPENER.open(req, timeout=timeout) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {"ok": False, "schema": SCHEMA, "route": "chat", "model": model,
                "error": f"HTTP {e.code}: {e.read()[:200]}"}
    except Exception as e:
        return {"ok": False, "schema": SCHEMA, "route": "chat", "model": model,
                "error": str(e)[:200]}

    content = (raw.get("choices") or [{}])[0].get("message", {}).get("content", "")
    citations = raw.get("citations") or []
    usage = raw.get("usage") or {}
    leaf = {"schema": SCHEMA, "route": "chat", "ts": _ts(), "query": query[:400],
            "model": model, "content": content, "citations": citations[:20],
            "usage": usage}
    _write_leaf(leaf)
    # (best-effort fold into the corpus is handled by the caller / cadence loop)
    return {"ok": True, "schema": SCHEMA, "route": "chat", "model": model,
            "content": content, "n_citations": len(citations), "citations": citations,
            "usage": usage, "saved_to": str(LEAF_DIR)}


def _search_body(query: str, *, max_results: int, max_tokens: int,
                 fast: bool) -> dict[str, Any]:
    """Search API request body (docs.perplexity.ai/docs/search/quickstart, 09-25)."""
    body: dict[str, Any] = {"query": (query or "").strip()}
    n = int(max_results) if max_results is not None else 10
    body["max_results"] = max(1, min(n, 20))  # documented range 1-20
    if max_tokens:
        body["max_tokens"] = int(max_tokens)  # total page-content cap (Search API param)
    if fast:
        body["search_type"] = "fast"  # $1/1k fast tier vs $5/1k standard
    return body


def _research_search(query: str, *, max_results: int, max_tokens: int,
                     timeout: float, fast: bool) -> dict[str, Any]:
    """Post-sunset Search API route (REMAP_PATH): raw ranked results, normalized."""
    blocked = endpoint_blocked(SEARCH_URL)
    if blocked:
        return {"ok": False, "schema": SCHEMA, "route": "search", "error": blocked}
    body = _search_body(query, max_results=max_results, max_tokens=max_tokens,
                        fast=fast)
    req = urllib.request.Request(
        SEARCH_URL, data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {key()}"}, method="POST")
    try:
        with _OPENER.open(req, timeout=timeout) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {"ok": False, "schema": SCHEMA, "route": "search",
                "error": f"HTTP {e.code}: {e.read()[:200]}"}
    except Exception as e:
        return {"ok": False, "schema": SCHEMA, "route": "search", "error": str(e)[:200]}

    results = raw.get("results") or []
    citations = [r.get("url", "") for r in results if r.get("url")]
    parts = []
    for i, r in enumerate(results, 1):
        head = f"[{i}] {r.get('title') or '(untitled)'} {r.get('url') or ''}".rstrip()
        snip = (r.get("snippet") or "").strip()
        parts.append(f"{head}\n{snip}" if snip else head)
    content = "\n\n".join(parts)
    usage = raw.get("usage") or {}
    leaf = {"schema": SCHEMA, "route": "search", "ts": _ts(), "query": query[:400],
            "content": content, "citations": citations[:20],
            "n_results": len(results), "usage": usage}
    _write_leaf(leaf)
    return {"ok": True, "schema": SCHEMA, "route": "search", "content": content,
            "n_citations": len(citations), "citations": citations,
            "usage": usage, "saved_to": str(LEAF_DIR)}


def research(query: str, *, model: str = "sonar", max_tokens: int = 2000,
             timeout: float = 120.0, route: str | None = None,
             max_results: int = 10, fast: bool = False) -> dict[str, Any]:
    """Run one Perplexity research call on `route`. Returns content + citations.

    route=None resolves to $SONAR_ROUTE or DEFAULT_ROUTE ("chat"). The chat
    route refuses on/after SONAR_CHAT_SUNSET and names the remap path; the
    "search" route posts the Search API shape; "agent" is an honest stub.
    """
    try:
        route = resolve_route(route)
    except ValueError as e:
        return {"ok": False, "schema": SCHEMA, "route": route, "error": str(e)}
    if route == "agent":
        return {"ok": False, "schema": SCHEMA, "route": "agent",
                "error": ("route 'agent' is a named remap path but its request "
                          "shape is not pinned from official docs (checked "
                          f"2026-09-25); use route='{REMAP_PATH}'")}
    if route == "chat" and _today() >= SONAR_CHAT_SUNSET:
        return {"ok": False, "schema": SCHEMA, "route": "chat", "model": model,
                "error": (f"sonar chat-completions retired {SONAR_CHAT_SUNSET}; "
                          f"REMAPPING: set route='{REMAP_PATH}' (env {ROUTE_ENV}="
                          f"{REMAP_PATH} or CLI --route {REMAP_PATH}) to post the "
                          f"Search API shape at {SEARCH_URL}")}
    if not key():
        return {"ok": False, "route": route, "schema": SCHEMA,
                "error": "PERPLEXITY_API_KEY not set (operator must provide it)"}
    if route == "search":
        return _research_search(query, max_results=max_results,
                                max_tokens=max_tokens, timeout=timeout, fast=fast)
    return _research_chat(query, model=model, max_tokens=max_tokens, timeout=timeout)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "status":
        print(json.dumps(status(), indent=2, default=str))
        return 0
    model = "sonar"
    if "--model" in argv:
        i = argv.index("--model")
        model = argv[i + 1]
        del argv[i:i + 2]
    route = None
    if "--route" in argv:
        i = argv.index("--route")
        route = argv[i + 1]
        del argv[i:i + 2]
    fast = False
    if "--fast" in argv:
        fast = True
        argv.remove("--fast")
    q = " ".join(argv).strip()
    if not q:
        print(json.dumps(status(), indent=2, default=str))
        return 0
    r = research(q, model=model, route=route, fast=fast)
    print(json.dumps({"ok": r.get("ok"), "route": r.get("route"),
                      "model": r.get("model"), "n_citations": r.get("n_citations"),
                      "error": r.get("error")}, indent=2))
    if r.get("ok"):
        print("===== CONTENT =====")
        print(r["content"])
        print("===== CITATIONS =====")
        for i, c in enumerate(r.get("citations", []), 1):
            print(f"[{i}] {c}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
