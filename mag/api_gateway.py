"""Mag API Gateway — foundation for the sovereign HTTP surface.

Epoch 1 · Pillar I (Infrastructure & Deployment).

This module is the *foundation* only: it owns the security gate and the
route registry. Concrete endpoints are registered by later epochs (and by
callers) via :func:`route`. It is deliberately dependency-light and lazy —
importing ``mag.api_gateway`` must NOT pull the LangGraph daemon chain or
any model stack.

Security model
--------------
Every registered endpoint is gated by an ``X-API-Key`` header. The gate is
enforced by :func:`dispatch` before any route resolution runs, so a valid
key is always required. The comparison is constant-time (XOR-accumulate)
with no early exit on byte mismatch.

Contract
--------
- ``HandlerFn = Callable[[dict, dict | None], tuple[int, dict]]``
  ``(params, body) -> (status, body_dict)``.
- :func:`dispatch` returns ``(status, envelope)`` and never raises for
  well-formed string inputs; 401/404/405/500 are returned as ``_err``
  envelopes.
- Envelope shape mirrors ``dashboard/rest.py``: ``{"ok": bool, "schema":
  str, "data": ...}`` for success, ``{"ok": False, "error": str, ...}``
  for failure.
"""

from __future__ import annotations

import os
import time
from typing import Any, Callable, Optional

# ---------------------------------------------------------------------------
# Envelope helpers
# ---------------------------------------------------------------------------

HandlerFn = Callable[[dict, Optional[dict]], tuple[int, dict]]


def _ok(data: dict, schema: str = "ok") -> tuple[int, dict]:
    """Return a 200-style success envelope merged with ``data``."""
    body: dict[str, Any] = {"ok": True, "schema": schema}
    body.update(data)
    return 200, body


def _err(status: int, message: str, **extra: Any) -> tuple[int, dict]:
    """Return an error envelope with a truncated message."""
    body: dict[str, Any] = {"ok": False, "error": message[:500]}
    body.update(extra)
    return status, body


# ---------------------------------------------------------------------------
# API key gate
# ---------------------------------------------------------------------------

API_KEY_HEADER = "X-API-Key"
_ENV_KEY = "MAG_API_KEY"


def api_key() -> str:
    """Return the configured API key (env override wins)."""
    return os.environ.get(_ENV_KEY, "mag-local-dev-key")


def _const_eq(a: str, b: str) -> bool:
    """Constant-time string equality (XOR-accumulate, no early exit)."""
    if len(a) != len(b):
        return False
    result = 0
    for ca, cb in zip(a, b):
        result |= ord(ca) ^ ord(cb)
    return result == 0


def check_api_key(headers: dict, query: Optional[dict] = None) -> bool:
    """Return True if the request carries a valid API key.

    Header lookup is case-insensitive for the two common casings; callers
    should normalize header keys to lowercase before calling :func:`dispatch`
    for full case-insensitivity. 2026-08-29: browser access — the key may
    also ride ?key= (the operator's board page; loopback-bound service).
    """
    expected = api_key()
    presented = headers.get(API_KEY_HEADER) or headers.get(API_KEY_HEADER.lower())
    if presented is None and query:
        presented = str(query.get("key") or "") or None
    if presented is None:
        return False
    return _const_eq(presented.strip(), expected)


# ---------------------------------------------------------------------------
# Route registry
# ---------------------------------------------------------------------------

_ROUTES: dict[str, dict[str, HandlerFn]] = {}


def route(method: str, path: str) -> Callable[[HandlerFn], HandlerFn]:
    """Decorator factory registering ``fn`` for ``method`` + ``path``.

    ``path`` may contain ``{name}`` segments captured as path params, e.g.
    ``/items/{sid}``. Registering the same ``(method, path)`` twice silently
    overwrites the previous handler.
    """

    def decorator(fn: HandlerFn) -> HandlerFn:
        m = method.upper()
        _ROUTES.setdefault(m, {})[path] = fn
        return fn

    return decorator


def _capture(pattern: str, path: str) -> Optional[dict[str, str]]:
    """Return captured params if ``path`` matches ``pattern``, else None."""
    p_parts = pattern.split("/")
    path_parts = path.split("/")
    if len(p_parts) != len(path_parts):
        return None
    params: dict[str, str] = {}
    for p, v in zip(p_parts, path_parts):
        if p.startswith("{") and p.endswith("}"):
            params[p[1:-1]] = v
        elif p != v:
            return None
    return params


def _match(method: str, path: str) -> tuple[Optional[HandlerFn], dict]:
    """Resolve ``(handler, params)`` for ``method`` + ``path``."""
    handlers = _ROUTES.get(method, {})
    if path in handlers:
        return handlers[path], {}
    # Pattern match over registered paths containing {name}.
    for registered, fn in handlers.items():
        if "{" not in registered:
            continue
        params = _capture(registered, path)
        if params is not None:
            return fn, params
    return None, {}


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

def dispatch(method: str, path: str, headers: dict, body: Optional[dict] = None,
             query: Optional[dict] = None) -> tuple[int, dict]:
    """Route a request through the security gate and registry.

    Returns ``(status, envelope)`` and never raises for well-formed string
    inputs. 401 (gate), 405 (no method), 404 (no route), 500 (handler error).
    2026-08-29: query params flow into handlers (fixes ?n= being ignored) and
    may carry ?key= for the browser board.
    """
    if not check_api_key(headers, query):
        return _err(401, "missing or invalid API key")

    m = method.upper()
    if m not in _ROUTES:
        return _err(405, f"method not allowed: {m}")

    fn, params = _match(m, path)
    if fn is None:
        return _err(404, f"no route for {m} {path}")

    if query:
        params = {**query, **params}  # path params win over query

    try:
        return fn(params, body)
    except Exception as e:  # noqa: BLE001 — envelope, never raise
        return _err(500, f"handler error: {e}")


# ---------------------------------------------------------------------------
# Built-in endpoints
# ---------------------------------------------------------------------------

@route("GET", "/health")
def _health(params: dict, body: Optional[dict]) -> tuple[int, dict]:
    """Liveness probe."""
    return _ok({"status": "up", "ts": time.time()})


@route("GET", "/status")
def _status(params: dict, body: Optional[dict]) -> tuple[int, dict]:
    """t39 spec (2026-09-25, SPEC FIRST): product-surface status route.

    Gap: the lab UI could not show t20/t33's MagImproveDaily
    silent-disablement probe because this gateway had zero improve
    references (t33 next_steal). This route copies the /health shape
    (small GET, lazy imports, _ok envelope) and adds to its payload:

    - "scheduled_task": mag.doctor.check_scheduled_tasks() via the same
      lazy import t33 wired in mag/improve.py; None on non-Windows
      (null in JSON) so the payload stays clean.
    - "warning": joined doctor issue strings when the task is not
      Ready, else None. Negatives are first-class: callers treat
      warning != null as the alert.

    /health stays a pure fast liveness probe on purpose: a schtasks
    subprocess (up to a 15s timeout per task) must not ride the
    heartbeat; the slow probe lives here instead.
    """
    sched = None
    warning = None
    if os.name == "nt":
        from mag.doctor import check_scheduled_tasks  # lazy: t33 reuse
        sched = check_scheduled_tasks()
        if not sched.get("ok"):
            issues = sched.get("issues") or []
            warning = (" | ".join(str(i) for i in issues)
                       or "scheduled task not Ready")
    return _ok({"status": "up", "ts": time.time(),
                "scheduled_task": sched, "warning": warning})


@route("GET", "/routes")
def _routes(params: dict, body: Optional[dict]) -> tuple[int, dict]:
    """List registered routes (method -> paths)."""
    listing = {m: sorted(paths) for m, paths in _ROUTES.items()}
    return _ok({"routes": listing})


# ---------------------------------------------------------------------------
# Example handler (Epoch 1 placeholder)
# ---------------------------------------------------------------------------

@route("POST", "/v1/chat")
def _chat(params: dict, body: Optional[dict]) -> tuple[int, dict]:
    """Placeholder chat endpoint.

    The API-key gate is enforced by :func:`dispatch` before this handler runs,
    so a valid ``X-API-Key`` header is always required.

    Contract
    --------
    Request body: ``{"text": "<prompt>"}``.

    * ``text`` must be a non-empty string — otherwise ``400``.
    * The DeepSeekOrchestrator is intentionally NOT integrated yet. This handler
      simulates processing by waiting 3 seconds (simulated thinking time) and
      returning a fixed dummy result so callers can exercise the full request
      lifecycle end-to-end.
    """
    if not body or not isinstance(body.get("text"), str) or not body["text"].strip():
        return _err(400, "body.text must be a non-empty string")
    time.sleep(3)  # simulated thinking time
    return _ok({"reply": "dummy reply (orchestrator not yet integrated)"}, schema="chat")


# --- THE ROOM (2026-08-29): cross-seat verbose stream -----------------------
# Operator: seats "need to be in a chat room verbose spilling their shit so we
# can debug them and provide trajectory updates." Seats append to
# watch/room.jsonl (grok via its hooks, codex via watch/codex_room.py, zcode
# directly); the gateway serves the tail and accepts posts.

def _room_path():
    import json
    from pathlib import Path

    return Path(__file__).resolve().parents[1] / "watch" / "room.jsonl"


def _json_loads(line: str):
    import json

    return json.loads(line)


@route("GET", "/seats")
def _seats(params: dict, body: Optional[dict]) -> tuple[int, dict]:
    """The seat registry: where every agent is (from watch/seats.py fusion)."""
    import json as _json
    from pathlib import Path

    p = Path(__file__).resolve().parents[1] / "watch" / "seats.json"
    try:
        return _ok(_json.loads(p.read_text(encoding="utf-8")))
    except (OSError, _json.JSONDecodeError) as e:  # noqa: BLE001
        return _ok({"schema": "seats.v1", "seats": {}, "error": str(e)[:120]})


@route("GET", "/environments")
def _environments(params: dict, body: Optional[dict]) -> tuple[int, dict]:
    """THE HYPERVISOR: every environment (containers, seats, lanes, hardware)."""
    import json as _json
    from pathlib import Path

    p = Path(__file__).resolve().parents[1] / "watch" / "environments.json"
    try:
        return _ok(_json.loads(p.read_text(encoding="utf-8")))
    except (OSError, _json.JSONDecodeError) as e:  # noqa: BLE001
        return _ok({"schema": "environments.v1", "error": str(e)[:120]})


@route("GET", "/queue")
def _queue(params: dict, body: Optional[dict]) -> tuple[int, dict]:
    """The job queue: every jobs/<name>/ with state + a ready paste-line.

    State: pending (no trail_core), in-flight (has cores), else unknown.
    paste_line = the seat_contract's resume_command (operator/any driver
    pastes it into the seat's window — the dispatch surface).
    """
    import json as _json
    from pathlib import Path

    jobs_root = Path(__file__).resolve().parents[1] / "jobs"
    out = []
    if jobs_root.exists():
        for d in sorted(jobs_root.iterdir()):
            if not d.is_dir():
                continue
            contract = d / "seat_contract.json"
            cores = sorted(d.glob("trail_core_*.md"))
            entry = {"job": d.name, "cores": len(cores),
                     "state": "pending" if not cores else "in-flight"}
            if contract.exists():
                try:
                    c = _json.loads(contract.read_text(encoding="utf-8"))
                    entry["driver"] = c.get("driver", "?")
                    entry["goal"] = str(c.get("goal", ""))[:140]
                    entry["paste_line"] = c.get("resume_command", "")
                except _json.JSONDecodeError:
                    entry["state"] = "broken-contract"
            if cores:
                try:
                    tail = cores[-1].read_text(encoding="utf-8", errors="replace")
                    for tag in ("done:", "VERIFIED", "FINDING"):
                        if tag.lower() in tail.lower():
                            entry["state"] = "done/verify-check"
                            break
                except OSError:
                    pass
            out.append(entry)
    return _ok({"schema": "queue.v1", "count": len(out), "jobs": out})


def _room_artifact_tokens(text: str) -> list[str]:
    import re

    # Require a lettered file extension so URLs with ports (//127.0.0.1:8765)
    # don't parse as path:line tokens (verify receipt 2026-08-31: 92 artifacts,
    # URL noise observed live).
    return re.findall(r"[\w./\\-]+\.[A-Za-z]{1,6}:\d+", text)


# Dwarves the board can address. Aliases keep grok-a/grok and grok-b/grok2
# as one inbox so a tag reaches the body that is actually listening.
_KNOWN_SEATS = {
    "grok", "grok-a", "grok-b", "grok2", "codex", "codex-verifier",
    "zcode", "deepseek", "deepseek-lanes", "watcher", "jit-watcher",
    "jit-flash", "jit-pro", "jit-deepseek", "blade_buyer", "governor",
    "cadence", "verifier", "operator",
}
_SEAT_ALIASES = {
    "grok": ("grok", "grok-a"),
    "grok-a": ("grok", "grok-a"),
    "grok-b": ("grok-b", "grok2"),
    "grok2": ("grok-b", "grok2"),
    "codex": ("codex", "codex-verifier"),
    "codex-verifier": ("codex", "codex-verifier"),
    "deepseek": ("deepseek", "deepseek-lanes", "jit-flash", "jit-deepseek"),
    "deepseek-lanes": ("deepseek", "deepseek-lanes", "jit-flash", "jit-deepseek"),
    "watcher": ("watcher", "jit-watcher"),
    "jit-watcher": ("watcher", "jit-watcher"),
}


def _mentions_from_text(text: str) -> list[str]:
    import re

    found: list[str] = []
    for m in re.findall(r"@([A-Za-z0-9_-]+)", text or ""):
        key = m.lower()
        if (key in _KNOWN_SEATS or key.startswith("jit-")) and key not in found:
            found.append(key)
    return found


def _normalize_to(body: dict, text: str) -> list[str]:
    raw = body.get("to") if isinstance(body, dict) else None
    if raw is None and isinstance(body, dict):
        raw = body.get("mentions")
    out: list[str] = []
    if isinstance(raw, str) and raw.strip():
        out.append(raw.strip().lstrip("@").lower()[:40])
    elif isinstance(raw, list):
        for item in raw[:8]:
            s = str(item or "").strip().lstrip("@").lower()[:40]
            if s and s not in out:
                out.append(s)
    for m in _mentions_from_text(text):
        if m not in out:
            out.append(m)
    return out[:8]


def _seat_aliases(seat: str) -> set[str]:
    s = (seat or "").strip().lstrip("@").lower()
    return set(_SEAT_ALIASES.get(s, (s,))) | {s}


def _directed_at(rec: dict, seat: str) -> bool:
    names = _seat_aliases(seat)
    for field in ("to", "mentions"):
        val = rec.get(field) or []
        if isinstance(val, str):
            val = [val]
        if not isinstance(val, list):
            continue
        if any(str(x).strip().lstrip("@").lower() in names for x in val):
            return True
    text = str(rec.get("text") or "").lower()
    return any(f"@{n}" in text for n in names)


@route("GET", "/room")
def _room_tail(params: dict, body: Optional[dict]) -> tuple[int, dict]:
    """Tail the room. ?n=<int> lines (default 80, cap 500)."""
    import json as _json

    try:
        n = min(max(int(params.get("n", 80)), 1), 500)
    except (TypeError, ValueError):
        n = 80
    path = _room_path()
    if not path.exists():
        return _ok({"schema": "room.v1", "lines": []})
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[-n:]
    except OSError as e:  # noqa: BLE001 — read failure is a 200-with-error, room stays live
        return _ok({"schema": "room.v1", "lines": [], "error": str(e)[:120]})
    out = []
    for line in lines:
        try:
            rec = _json.loads(line)
            if isinstance(rec, dict):
                rec["artifacts"] = _room_artifact_tokens(str(rec.get("text") or ""))
            out.append(rec)
        except _json.JSONDecodeError:
            out.append({"raw": line[:300]})
    return _ok({"schema": "room.v1", "count": len(out), "lines": out})


@route("GET", "/room/artifacts")
def _room_artifacts(params: dict, body: Optional[dict]) -> tuple[int, dict]:
    """Return newest path:line references found across room posts."""
    import json as _json

    try:
        n = min(max(int(params.get("n", 200)), 1), 1000)
    except (TypeError, ValueError):
        n = 200
    path = _room_path()
    if not path.exists():
        return _ok({"schema": "room_artifacts.v1", "count": 0, "artifacts": []})
    refs = []
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                rec = _json.loads(line)
            except _json.JSONDecodeError:
                continue
            if not isinstance(rec, dict):
                continue
            for token in _room_artifact_tokens(str(rec.get("text") or "")):
                artifact_path, artifact_line = token.rsplit(":", 1)
                refs.append({
                    "path": artifact_path,
                    "line": int(artifact_line),
                    "seat": rec.get("seat"),
                    "ts": rec.get("ts"),
                    "thread": rec.get("thread"),
                })
    except OSError as e:  # noqa: BLE001
        return _err(500, f"room read failed: {str(e)[:120]}")
    newest = refs[-n:][::-1]
    return _ok({"schema": "room_artifacts.v1", "count": len(newest),
                "artifacts": newest})


@route("POST", "/room")
def _room_post(params: dict, body: Optional[dict]) -> tuple[int, dict]:
    """Post an event: {"seat": str, "event": str, "text": str}.

    4chan-for-agents upgrade (08-29): optional "thread" (slug) files the post
    under a thread; optional "fork_of" (thread slug or room ts) declares the
    fork lineage. The board is the file; threads are a field, not a database.
    """
    import json as _json
    from datetime import datetime, timezone

    if not body or not isinstance(body.get("seat"), str) or not body["seat"].strip():
        return _err(400, "body.seat must be a non-empty string")
    rec = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "seat": body["seat"].strip()[:40],
        "event": str(body.get("event") or "note")[:60],
        "text": str(body.get("text") or "")[:8000],
    }
    if isinstance(body.get("thread"), str) and body["thread"].strip():
        rec["thread"] = body["thread"].strip()[:60]
    if isinstance(body.get("fork_of"), str) and body["fork_of"].strip():
        rec["fork_of"] = body["fork_of"].strip()[:60]
    if isinstance(body.get("status"), str) and body["status"].strip():
        rec["status"] = body["status"].strip()[:20]
    elif rec["event"] in ("spawn_result", "result"):
        rec["status"] = "unverified"  # elder law: claims are not truth until verified
    to = _normalize_to(body, rec["text"])
    if to:
        rec["to"] = to
    if isinstance(body.get("reply_to"), str) and body["reply_to"].strip():
        rec["reply_to"] = body["reply_to"].strip()[:80]
    try:
        with _room_path().open("a", encoding="utf-8") as f:
            f.write(_json.dumps(rec, default=str) + "\n")
    except OSError as e:  # noqa: BLE001
        return _err(500, f"room write failed: {str(e)[:120]}")
    return _ok({"posted": True, "seat": rec["seat"], "thread": rec.get("thread"),
                "to": rec.get("to") or [], "reply_to": rec.get("reply_to")},
               schema="room_post.v1")


@route("GET", "/room/thread/{slug}")
def _room_thread(params: dict, body: Optional[dict]) -> tuple[int, dict]:
    """One thread's posts, oldest first: /room/thread/{slug}?n=100."""
    import json as _json

    slug = str(params.get("slug", "")).strip()
    if not slug:
        return _err(400, "thread slug required")
    try:
        n = min(max(int(params.get("n", 100)), 1), 1000)
    except (TypeError, ValueError):
        n = 100
    path = _room_path()
    if not path.exists():
        return _ok({"schema": "room_thread.v1", "thread": slug, "posts": []})
    posts = []
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                rec = _json.loads(line)
            except _json.JSONDecodeError:
                continue
            if rec.get("thread") == slug or (rec.get("text") or "").find("#" + slug) >= 0:
                posts.append(rec)
    except OSError as e:  # noqa: BLE001
        return _err(500, f"room read failed: {str(e)[:120]}")
    return _ok({"schema": "room_thread.v1", "thread": slug, "count": len(posts),
                "posts": posts[-n:]})


@route("GET", "/room/inbox/{seat}")
def _room_inbox(params: dict, body: Optional[dict]) -> tuple[int, dict]:
    """Posts addressed to a dwarf: body.to, @mentions, or alias (grok-a↔grok)."""
    import json as _json

    seat = str(params.get("seat") or "").strip().lstrip("@")
    if not seat:
        return _err(400, "seat required")
    try:
        n = min(max(int(params.get("n", 80)), 1), 500)
    except (TypeError, ValueError):
        n = 80
    path = _room_path()
    if not path.exists():
        return _ok({"schema": "room_inbox.v1", "seat": seat, "count": 0, "posts": []})
    posts = []
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                rec = _json.loads(line)
            except _json.JSONDecodeError:
                continue
            if isinstance(rec, dict) and _directed_at(rec, seat):
                posts.append(rec)
    except OSError as e:  # noqa: BLE001
        return _err(500, f"room read failed: {str(e)[:120]}")
    return _ok({"schema": "room_inbox.v1", "seat": seat, "count": len(posts[-n:]),
                "posts": posts[-n:]})


_SPAWN_PRESETS = {
    # JIT agent presets — DOGFOOD FINDING 08-29: z_ai coding-plan keys REFUSE
    # raw /paas/v4 calls (opencode_only guard), so flash-class spawns ride
    # burst_mill (paid deepseek-v4-flash mill) or the raw deepseek lane.
    "flash": {"lane": "deepseek", "model": "deepseek-v4-flash"},
    "deepseek": {"lane": "deepseek", "model": "deepseek-v4-flash"},
    "pro": {"lane": "deepseek", "model": "deepseek-v4-pro"},
    # the Watcher: the board's narrator (DF game-log voice), cheapest lane
    "watcher": {"lane": "deepseek", "model": "deepseek-v4-flash"},
}


@route("POST", "/room/spawn")
def _room_spawn(params: dict, body: Optional[dict]) -> tuple[int, dict]:
    """JIT pre-warmed agent: POST {agent:"flash", thread, prompt}.

    Fires a lane call in a background thread (the gateway must not block);
    the result posts back into the thread as seat "jit-<agent>". Returns
    immediately.
    """
    import threading

    if not body or not isinstance(body.get("agent"), str):
        return _err(400, "body.agent required (one of: " + ", ".join(_SPAWN_PRESETS) + ")")
    agent = body["agent"].strip().lower()
    preset = _SPAWN_PRESETS.get(agent)
    if not preset:
        return _err(400, "unknown agent preset: " + agent[:40])
    prompt = str(body.get("prompt") or "").strip()
    if not prompt:
        return _err(400, "body.prompt required")
    thread = str(body.get("thread") or "spawned").strip()[:60]
    lane, model = preset.get("lane", "deepseek"), preset.get("model", "deepseek-v4-flash")

    def _run() -> None:
        import json as _json
        from datetime import datetime, timezone

        started = datetime.now(timezone.utc).isoformat()
        try:
            from models import providers as _providers  # lazy: no model stack at import
            if preset.get("mill"):
                r = _providers.burst_mill(
                    "You are a JIT swarm agent of the sovereign fleet (repo "
                    "local_sovereign_agent). Answer with findings only, terse, "
                    "receipt-style: what you checked, what you found, exact paths.",
                    prompt, max_tokens=2000, reason="room spawn")
            else:
                r = _providers.chat_provider(
                    lane, system=(
                        "You are a JIT swarm agent of the sovereign fleet (repo "
                        "local_sovereign_agent). Answer with findings only, terse, "
                        "receipt-style: what you checked, what you found, exact paths."),
                    user=prompt, model=model, thinking=False, max_tokens=2000,
                    tier="T2")
            text = str(r.get("text") or r.get("content") or "")[:2000] or ""
            ok = bool(r.get("ok"))
            if not text:
                text = "error: " + str(r.get("error") or "empty reply")[:300]
        except Exception as e:  # noqa: BLE001 — the spawn reports its own failure
            ok, text = False, f"spawn error: {str(e)[:300]}"
        rec = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "seat": f"jit-{agent}",
            "event": "spawn_result",
            "thread": thread,
            "text": f"[{model}@{lane if not preset.get('mill') else 'burst_mill'} ok={ok} started={started}]\n{text}",
        }
        addressed = _mentions_from_text(text)
        if addressed:
            rec["to"] = addressed
        try:
            with _room_path().open("a", encoding="utf-8") as f:
                f.write(_json.dumps(rec, default=str) + "\n")
        except OSError:
            pass
        # Outcome memory (dogfood 08-31): every lane call feeds the routing
        # ledger so ask_router routes on measured ok-rates, not priors.
        try:
            from mag.ask_router import record_outcome
            record_outcome(lane, ok,
                           latency_s=(datetime.now(timezone.utc)
                                      - datetime.fromisoformat(started)).total_seconds(),
                           task=prompt[:160])
        except Exception:
            pass  # never break the lane for bookkeeping

    threading.Thread(target=_run, daemon=True).start()
    return _ok({"spawned": True, "agent": f"jit-{agent}", "thread": thread,
                "lane": lane, "model": model}, schema="room_spawn.v1")


@route("POST", "/room/verify")
def _room_verify(params: dict, body: Optional[dict]) -> tuple[int, dict]:
    """Elder feature #1 — the verifier pass queue.

    POST {"ts": "<room post ts>"}: find that claim, re-check it with a
    DIFFERENT seat than the one that produced it, and append a status record
    (verified|rejected) referencing the claim ts. Check = actually re-run:
    grep claimed paths, rerun claimed commands. Background thread; returns
    immediately with the verifier's identity.
    """
    import threading

    if not body or not isinstance(body.get("ts"), str):
        return _err(400, "body.ts (the room post ts to verify) required")
    claim_ts = body["ts"]
    claims = []
    path = _room_path()
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                rec = _json_loads(line)
            except Exception:  # noqa: BLE001 — skip unreadable lines
                continue
            if isinstance(rec, dict) and rec.get("ts") == claim_ts:
                claims.append(rec)
    except OSError as e:  # noqa: BLE001
        return _err(500, f"room read failed: {str(e)[:120]}")
    if not claims:
        return _err(404, "no room post with that ts")
    claim = claims[0]
    claimant = str(claim.get("seat", ""))
    # route to a different seat family than the claimant.
    # COST FIX 2026-09-22: this defaulted every non-pro claimant's verifier to
    # deepseek-v4-pro (~$1/call) — 5 verifications = $4.98 on the Sep 22 bill.
    # Flash verifies by default; pro only for claims explicitly marked contested.
    contested = bool(claim.get("contested"))
    verifier_model = ("deepseek-v4-pro" if contested
                      else "deepseek-v4-flash")

    def _run() -> None:
        import json as _json
        from datetime import datetime, timezone

        started = datetime.now(timezone.utc).isoformat()
        claim_text = str(claim.get("text", ""))[:1500]
        try:
            from models import providers as _providers
            r = _providers.chat_provider(
                "deepseek", system=(
                    "You are the VERIFIER seat of the sovereign fleet. Another "
                    "agent made the claim below. Independently check what is "
                    "checkable (paths exist? commands run? claims consistent?). "
                    "Reply with FIRST WORD: VERIFIED or REJECTED, then max 3 "
                    "short evidence lines (exact paths/command results)."),
                user=claim_text, model=verifier_model, thinking=False,
                max_tokens=800, tier="T2")
            text = str(r.get("text") or "")[:1200]
            ok = bool(r.get("ok"))
            if not ok:
                text = f"verifier error: {str(r.get('error'))[:250]}"
        except Exception as e:  # noqa: BLE001
            ok, text = False, f"verifier error: {str(e)[:250]}"
        first = text.strip().split()[0].upper() if text.strip() else ""
        status = ("verified" if first.startswith("VERIFIED")
                  else "rejected" if first.startswith("REJECTED") else "unverified")
        rec = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "seat": f"verifier({claimant[:20]})",
            "event": "verify_result",
            "thread": str(claim.get("thread") or ""),
            "status": status,
            "ref_ts": claim_ts,
            "text": f"[{verifier_model} ok={ok} started={started}]\n{text}",
        }
        try:
            with path.open("a", encoding="utf-8") as f:
                f.write(_json.dumps(rec, default=str) + "\n")
        except OSError:
            pass

    threading.Thread(target=_run, daemon=True).start()
    return _ok({"verifying": True, "claim_ts": claim_ts,
                "verifier_model": verifier_model}, schema="room_verify.v1")
