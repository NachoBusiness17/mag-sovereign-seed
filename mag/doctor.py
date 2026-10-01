"""Doctor Protocol — independent configuration sanity checker.

Runs BEFORE tasks are dispatched. Catches misconfigurations that would
waste money, leak data, or violate system invariants. Lives independently
in the test path — not coupled to the main loop.

WHAT IT WOULD HAVE CAUGHT TODAY:
  - Defaulting to grok-4-latest ($0.025) when grok-3-mini ($0.003) is available
  - Provider mismatch: using "grok" instead of "xai" in copilot inbox messages
  - Missing XAI_API_KEY when Grok tasks are queued
  - Cost cap violations before they happen

CHECKS:
  1. Provider sanity — are all referenced providers configured?
  2. Model sanity — are all referenced models available?
  3. Cost sanity — would any queued task exceed the daily cap?
  4. Inbox sanity — are there malformed messages?
  5. Env sanity — are required environment variables set? Also the B2-358
     env-redirect tripwire: MAG_SEAT_CRASH_LOG / MAG_GAPS_LOG are test
     isolation seams that silently move the production crash/gap logs when
     their export leaks into a plain shell; a redirect set outside a test
     run is a WARNING naming the target (mag/env_redirect.py).
  6. Verkle sanity — is the chain healthy?
  7. Scheduled task sanity — are tracked Windows tasks (MagImproveDaily) still
     registered and Ready? (t20: disabled/deleted tasks ran silently never)
  8. Provider endpoint health - route-correct liveness probes per configured
     provider (t86: the operator probed saelis "connection refused" and ollama
     "404" in a browser and could not tell dead from alive; there was no
     route-correct provider health surface. B2-04: remote lanes get the deep
     models+ping probe under MAG_PROBE_REMOTE=1, mapped onto the measured
     cerebras/nvidia/gemini/mistral/z_ai failure classes).
  9. Repo remote honesty (B2-127, 2026-09-26) — git remote -v classification,
     zero network bytes: a remote whose URL is a filesystem path on the repo's
     own volume is named same-disk, never "backup", so the Sep-16-stale
     local -> Mag-backup.git bare (same C: volume as the repo; B2-52 bridge
     card evidence :19) stops reading as off-machine protection. A same-disk
     target whose dir mtime is stale beyond 7d (the boot-freshness law's
     number) raises a WARNING naming the age and the same-disk limit.

PROVIDER ENDPOINT PROBE MATRIX (t86 spec, 2026-09-25):
  Every provider in configs/providers.yaml gets a probe matched to its kind
  and locality. Local = resolved base_url host is 127.0.0.1 / localhost / ::1.
  base_url_env overrides (e.g. OLLAMA_HOST, SAELIS_BASE_URL) are honored via
  models.providers.provider_base_url, the estate's own resolver.

  - Local openai_compat, provider ollama (id "ollama" or base on :11434):
      GET {base minus /v1}/api/tags
      200 + JSON body whose "models" is a list  -> ALIVE
      refused / timeout / other                 -> DOWN (detail carries the bytes)
  - Local openai_compat, other (e.g. saelis, mlx-cluster):
      1. TCP connect host:port   (refused = DOWN, the saelis case)
      2. GET {base}/models       (that path IS /v1/models when base carries /v1)
      2xx -> ALIVE; tcp ok but models probe failed -> DOWN, detail says which
      half failed (never blur a listening port with a dead one).
  - LOCALITY LAW (B2-107, 2026-09-26): a local-declared lane (id "ollama",
      resolved base on :11434, or free_local: true) whose base_url_env
      override resolves to a host this seat cannot even name (getaddrinfo
      fails, the trap case: OLLAMA_HOST=http://ollama:11434 read on the
      host, a docker-network name) classifies DOWN with probe
      "none(locality)" in the DEFAULT path, zero network bytes. The lane
      cannot serve a call from this seat, and the pre-law surfaces lied
      both ways: the default read REMOTE-UNVERIFIED ("no blind probing of
      paid endpoints", absurd for the free local eye) so the api_tags probe
      never fired, and MAG_PROBE_REMOTE=1 read a generic DOWN URLError
      ("GET /models failed URLError") that named no disease. The
      OLLAMA_HOST contract is HOST-REACHABLE WHERE THE CODE RUNS: host
      shells use the loopback default (config.ollama_base ->
      http://127.0.0.1:11434), compose services set
      http://host.docker.internal:11434[/v1] (docker-compose.yml since the
      2026-09-07 eye migration); "http://ollama:11434" only resolves inside
      a docker network and is exactly this trap on the host. A RESOLVABLE
      non-local ollama (LAN box, tunnel) stays REMOTE-UNVERIFIED /
      deep-probe as before: the law bites only on names this seat cannot
      resolve, never on reachable remotes. Docker-name translation (doctor
      silently rewriting "ollama" to host.docker.internal) is rejected
      fallback creep: the caller that runs the code would still fail.
  - RESOLVER BOUND (B2-489, 2026-09-26): the locality lookup itself is
      deadline-bounded. Windows DNS resolution is not covered by urllib
      timeouts (models.registry.ollama_tags runs its whole probe on a
      daemon thread for exactly this reason), so a resolver that
      blackholes a lookup would otherwise stall the check (and the whole
      examine() report) past every documented timeout: measured pre-bound,
      a 30s sleeper made check_provider_endpoints take 30.1s. _host_resolves
      therefore joins its lookup thread with a hard deadline
      (_RESOLVE_TIMEOUT_S = 2.0s, the check's own local-probe timeout); a
      lookup that does not answer in time reads unresolvable, same
      classification as a clean NXDOMAIN. The stranded thread dies with
      the process, the price the registry probe already pays. N
      local-declared lanes cost at most N deadlines, never N x 30s.
  - Remote (non-local base_url): NO network call by default. No blind probing
      of paid endpoints; classification is REMOTE-UNVERIFIED, config-only.
  - Remote DEEP probe (B2-04 extension, 2026-09-26), when explicitly opted
      into via MAG_PROBE_REMOTE=1: GET {base}/models, then ONE one-token chat
      ping (synthetic public prompt "Reply with the single word: pong.",
      max_tokens 1, temperature 0, browser UA per the Cloudflare-1010 law in
      models.providers, Bearer first key on file; key VALUES never appear in
      any detail string). A models-only 200 is NOT liveness: on 2026-09-26
      cerebras (chat 402), nvidia (410), gemini (401) and mistral (429 with
      x-ratelimit limits literally 0) all served /models 200 with zero usable
      inference (receipt watch/inbox/PROVIDER_HEALTH_20260926.md). The old
      t86 remote probe was exactly that trap: catalog-alive masquerading as
      lane-alive. Classification map, every class measured in B2-04:
        models 2xx + chat 2xx                -> ALIVE
        chat 402 payment required            -> QUOTA-DEAD (cerebras: catalog serves, no credit)
        chat 410 gone                        -> QUOTA-DEAD (nvidia: account functions purged)
        chat 401 unauthorized                -> AUTH-DEAD (gemini: credential cannot generate)
        chat 429 + x-ratelimit *limit* = 0   -> QUOTA-DEAD (mistral: nameplate, 0 req/min)
        chat 429 + body 1305/1302/overloaded -> DEGRADED (z_ai: alive, throttled, recovers)
        other chat non-2xx / models non-2xx  -> DOWN (code + body snippet in detail)
      ALARM classes: DOWN, QUOTA-DEAD, AUTH-DEAD feed issues (doctor red):
      dispatching to them wastes the call. DEGRADED does not alarm:
      models.providers.should_burst already treats 1305 as retry/burst at
      call time; degraded lanes surface under the result's "degraded" list.
      FENCES: opencode_only providers (z_ai, z_ai4) are never probed raw
      (coding-plan keys hang/1305 on /paas/v4, fence risk) -> FENCED, a
      declared state, not an alarm; kind != openai_compat lanes (e.g.
      anthropic_messages) get no OpenAI-shape ping -> REMOTE-UNVERIFIED
      naming the kind; remote lanes with no key or no resolvable
      model id on file stay REMOTE-UNVERIFIED (a catalog-only 200 would be
      exactly the B2-04 trap this probe exists to close). Burn law: the whole
      deep probe costs one 1-token completion per (base_url, model, key)
      triple; triples are deduped, never per-lane fan-out. Ping timeout floor
      15s: B2-04 measured 1-token z_ai pings at 2.5-4.5s (retries to ~10s),
      so the 2s local-probe default cannot serve a remote ping (live-verified
      2026-09-26: z_ai3 timed out at 2s while z_ai2 answered the same
      endpoint on the sibling key).
  - DORMANT: a provider carrying `dormant: true` is a declared state, not an
      alarm; it is not probed and never flags the doctor red.
  - Probes dedupe on (style, base_url): N providers sharing one endpoint cost
      one probe.

  GET /v1 is NEVER a valid liveness probe. /v1 is a POST-only route family
  (the chat completions live under /v1/chat/completions); a browser GET /v1
  returns 404 on a perfectly healthy ollama and 405-class errors elsewhere.
  The operator's 09-25 "ollama 404" was exactly this false alarm: the server
  answered, the route was wrong. Liveness is judged only by the routes above.

Schema: doctor.v1
Law: Doctor runs BEFORE dispatch. Failures block the pipeline.
"""

from __future__ import annotations

import hashlib
import json
import os
import socket
import subprocess
import threading
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except ImportError:
    ROOT = Path(__file__).resolve().parent.parent

from mag.env_redirect import env_redirect_warnings


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_jsonl(path: Path, tail: int = 50) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8", errors="replace").strip().splitlines()
    if tail and len(lines) > tail:
        lines = lines[-tail:]
    rows: list[dict[str, Any]] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


@dataclass
class DoctorReport:
    ok: bool
    checks: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    ts: str = field(default_factory=_now)


# ═══════════════════════════════════════════════════════════════════
# CHECKS
# ═══════════════════════════════════════════════════════════════════

def check_provider_sanity() -> dict[str, Any]:
    """Check that all referenced providers are configured with valid keys."""
    issues = []
    providers_ok = []

    # Check Grok
    xai_key = os.environ.get("XAI_API_KEY") or os.environ.get("GROK_API_KEY") or ""
    if xai_key:
        providers_ok.append("xai/grok")
    else:
        issues.append("XAI_API_KEY not set — Grok tasks will fail")

    # Check DeepSeek
    ds_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if ds_key:
        providers_ok.append("deepseek")
    else:
        issues.append("DEEPSEEK_API_KEY not set — DeepSeek tasks may fail (check models/providers.py fallback)")

    # Check Ollama
    try:
        import subprocess
        r = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=5,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) if sys.platform == "win32" else 0)
        if r.returncode == 0:
            providers_ok.append("ollama")
        else:
            issues.append("Ollama not responding — local models unavailable")
    except Exception:
        issues.append("Ollama not reachable — local models unavailable")

    return {
        "check": "provider_sanity",
        "ok": len(issues) == 0,
        "providers_ok": providers_ok,
        "issues": issues,
    }


# ═══════════════════════════════════════════════════════════════════
# PROVIDER ENDPOINT HEALTH (t86, 2026-09-25)
# ═══════════════════════════════════════════════════════════════════

_LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1", "0.0.0.0"}

# The browser UA is the Cloudflare-1010 law (models.providers.chat_provider,
# 2026-08-24): bare Python-urllib signatures get HTTP 403/1010 from groq's
# edge, so the deep probe must present the same UA real chat traffic does.
_BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

# B2-04 measured 1-token alive pings on remote lanes at 2.5-4.5s (z_ai worst
# retry ~10s; receipt watch/inbox/PROVIDER_HEALTH_20260926.md). The check's
# 2s default is a LOCAL-probe timeout (TCP connect, loopback HTTP); applying
# it to a remote ping misclassifies a slow-but-alive lane as DOWN (live
# verified 2026-09-26: z_ai3 timed out at 2s, z_ai2 answered the same
# endpoint). Floor, not override: an explicitly larger timeout still wins.
_REMOTE_PING_TIMEOUT_FLOOR = 15.0

# B2-489: hard deadline for one getaddrinfo in _host_resolves. Windows DNS
# resolution is not covered by urllib timeouts, so an unbounded lookup let a
# blackholing resolver stall check_provider_endpoints (measured 30.1s on a
# 30s sleeper, pre-bound red run 2026-09-26). Same number as the check's
# own local-probe timeout: a local-declared lane whose name takes longer
# than the local probe would get anyway reads unresolvable.
_RESOLVE_TIMEOUT_S = 2.0


def _host_resolves(host: str, timeout: float = _RESOLVE_TIMEOUT_S) -> bool:
    """B2-107 locality law seam: can this seat NAME the host at all?

    One getaddrinfo, zero network bytes (resolution is not a probe). The
    estate already met the unresolvable-docker-name disease on the native
    path (models.registry.ollama_tags runs its probe on a daemon thread so
    an absent container hostname cannot hold a caller hostage); the doctor
    surface never got the same honesty until B2-107. Any resolver failure
    reads unresolvable: a name this seat cannot look up is not a lane.
    Tests monkeypatch this seam; the live trap (OLLAMA_HOST=http://ollama:11434
    on the host) was reproduced on real DNS before the pins landed.

    B2-489 hard deadline: a lookup that never ANSWERS is a second disease
    the first seam still carried (a 30s blackhole sleeper measured 30.1s
    through check_provider_endpoints, red run 2026-09-26). Windows DNS
    resolution is not covered by urllib timeouts, so the lookup runs on a
    daemon thread joined with `timeout` seconds (default _RESOLVE_TIMEOUT_S)
    and a lookup that does not answer in time reads unresolvable, same as
    NXDOMAIN; the stranded thread dies with the process, the price the
    registry probe already pays. The socket-level pins patch
    socket.getaddrinfo (tests/test_doctor_provider_endpoints.py, B2-489).
    """
    box: dict[str, bool] = {}

    def _lookup() -> None:
        try:
            socket.getaddrinfo(host, None)
            box["ok"] = True
        except OSError:
            box["ok"] = False

    watcher = threading.Thread(
        target=_lookup, name="doctor-resolve-%s" % host, daemon=True
    )
    watcher.start()
    watcher.join(float(timeout))
    return box.get("ok", False)


def _parse_providers_yaml(path: Path) -> dict[str, Any]:
    """Parse a providers.yaml fixture with the estate's own load pattern
    (the mag/lanes.load_lanes shape: read text, strip comments, safe_load).
    Used for explicit paths (tests); the live default path goes through
    models.providers.load_providers, the same loader the estate uses."""
    try:
        import yaml  # type: ignore

        raw = Path(path).read_text(encoding="utf-8")
    except OSError:
        return {}
    lines = []
    for line in raw.splitlines():
        if "#" in line:
            in_q = False
            out = []
            for ch in line:
                if ch == '"':
                    in_q = not in_q
                if ch == "#" and not in_q:
                    break
                out.append(ch)
            line = "".join(out).rstrip()
        if line.strip():
            lines.append(line)
    try:
        data = yaml.safe_load("\n".join(lines)) or {}
    except Exception as e:
        return {}
    if not isinstance(data, dict):
        return {}
    provs = data.get("providers") or {}
    return provs if isinstance(provs, dict) else {}


def _probe_ollama_tags(base: str, timeout: float) -> dict[str, str]:
    """Native /api/tags liveness (registry law: never construct /v1/api/tags)."""
    root = base[:-3].rstrip("/") if base.lower().endswith("/v1") else base.rstrip("/")
    url = root + "/api/tags"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            code = int(getattr(r, "status", 200) or 200)
            body = r.read(65536)
    except urllib.error.HTTPError as e:
        return {"status": "DOWN", "detail": "GET /api/tags HTTP %s %s" % (e.code, url)}
    except Exception as e:
        return {"status": "DOWN",
                "detail": ("GET /api/tags failed %s: %s" % (type(e).__name__, e))[:200]}
    try:
        data = json.loads(body.decode("utf-8", errors="replace"))
    except Exception as e:
        return {"status": "DOWN",
                "detail": ("GET /api/tags %s but body unparsed: %s" % (code, type(e).__name__))[:200]}
    models = data.get("models") if isinstance(data, dict) else None
    if code == 200 and isinstance(models, list):
        return {"status": "ALIVE", "detail": "GET /api/tags 200, %d models tagged" % len(models)}
    return {"status": "DOWN", "detail": "GET /api/tags HTTP %s but 'models' is not a list" % code}


def _probe_tcp_then_models(base: str, timeout: float) -> dict[str, str]:
    """Local non-ollama probe: TCP connect, then route-correct GET {base}/models.

    Refused TCP is the unambiguous dead signal (the operator's saelis case).
    A listening port whose /models fails is still DOWN for routing, but the
    detail says which half failed so a listener is never reported as refused.
    """
    parts = urllib.parse.urlsplit(base)
    host = parts.hostname or "127.0.0.1"
    port = parts.port or (443 if parts.scheme == "https" else 80)
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
        sock.close()
    except OSError as e:
        # A refusal (WinError 10061) and a timeout (firewall drop) are both
        # DOWN, but the detail names which one happened: never blur the bytes.
        why = "refused" if isinstance(e, ConnectionRefusedError) else type(e).__name__
        return {"status": "DOWN",
                "detail": ("tcp %s:%s %s: %s" % (host, port, why, e))[:200]}
    url = base.rstrip("/") + "/models"
    req = urllib.request.Request(url, headers={"User-Agent": "mag-doctor-t86"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            code = int(getattr(r, "status", 200) or 200)
    except urllib.error.HTTPError as e:
        return {"status": "DOWN", "detail": "tcp %s:%s ok but GET /models HTTP %s" % (host, port, e.code)}
    except Exception as e:
        return {"status": "DOWN",
                "detail": ("tcp %s:%s ok but GET /models failed %s" % (host, port, type(e).__name__))[:200]}
    if 200 <= code < 300:
        return {"status": "ALIVE", "detail": "tcp %s:%s ok + GET /models %s" % (host, port, code)}
    return {"status": "DOWN", "detail": "tcp %s:%s ok but GET /models HTTP %s" % (host, port, code)}


def _classify_chat_failure(code: int, raw: str, hdrs: dict[str, str]) -> dict[str, str]:
    """Map a chat-ping failure onto the B2-04 measured classes.

    Every branch names the lane whose live response defined it
    (watch/inbox/PROVIDER_HEALTH_20260926.md); the body snippet rides in the
    detail so the classification is never a bare number.
    """
    snippet = " ".join((raw or "").split())[:140]
    if code == 402:
        return {"status": "QUOTA-DEAD",
                "detail": ("models ok but chat 402 payment required: catalog serves, zero usable "
                           "credit (B2-04 cerebras class); body: '%s'" % snippet)}
    if code == 410:
        return {"status": "QUOTA-DEAD",
                "detail": ("models ok but chat 410 gone: account functions purged (B2-04 nvidia "
                           "class); body: '%s'" % snippet)}
    if code == 401:
        return {"status": "AUTH-DEAD",
                "detail": ("models ok but chat 401: credential reads the catalog and cannot "
                           "generate (B2-04 gemini class); body: '%s'" % snippet)}
    if code == 403:
        # B2-457 (2026-09-26): a 403 tier_not_allowed is a PER-KEY TIER FACT,
        # not an outage. Defining byte (B2-105 live 2026-09-26,
        # B2_105_verify_results.json): mistral-large-latest answers
        # 403 {"message":"This model is not available in your subscription
        # tier","type":"tier_not_allowed","code":"1910"} - the key lists the
        # catalog, cannot call the model, and waiting never fixes it. Without
        # this arm the shape fell to the generic DOWN catch-all, so a dormant
        # fence removal or a stale default re-add would alarm as an outage.
        return {"status": "AUTH-DEAD",
                "detail": ("models ok but chat 403 tier not allowed: key reads the catalog, "
                           "cannot call the model, waiting never fixes it (B2-105 mistral-large "
                           "tier_not_allowed class); body: '%s'" % snippet)}
    if code == 429:
        # LIMIT headers only: 'x-ratelimit-remaining-*' / 'reset' / 'used' also
        # contain the substring 'limit' and must never read as a zero quota.
        zero_limit = any(
            k.startswith("x-ratelimit") and "limit" in k
            and not any(w in k for w in ("remaining", "reset", "used"))
            and v == "0"
            for k, v in hdrs.items()
        )
        if zero_limit:
            return {"status": "QUOTA-DEAD",
                    "detail": ("models ok but chat 429 with a zero rate-limit header (limit = 0 "
                               "req): nameplate lane (B2-04 mistral class); body: '%s'" % snippet)}
        low = (raw or "").lower()
        if "overloaded" in low or "1305" in raw or "1302" in raw:
            return {"status": "DEGRADED",
                    "detail": ("models ok but chat 429 overload/backoff (B2-04 z_ai 1305 class: "
                               "alive, throttled, recovers after a wait); body: '%s'" % snippet)}
        return {"status": "DEGRADED",
                "detail": ("models ok but chat 429 rate-limited (class unmeasured, treated as "
                           "throttled not dead); body: '%s'" % snippet)}
    return {"status": "DOWN",
            "detail": "models ok but chat HTTP %s (deep probe); body: '%s'" % (code, snippet)}


def _probe_gemini_native_deep(base: str, timeout: float, model: str, key: str) -> dict[str, str]:
    """B2-194 deep probe for kind gemini_native: ONE one-token generateContent ping.

    The vertex native endpoint has no /models analog on the express path, so
    the ping IS the probe (the openai_compat two-step exists because a
    models-only 200 is not liveness; here every byte is inference). Cost: one
    1-token completion per call. The key is never logged.
    """
    payload = {
        "contents": [{"role": "user", "parts": [{"text": "Reply with the single word: pong."}]}],
        "generationConfig": {"temperature": 0, "maxOutputTokens": 1},
    }
    body = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json", "x-goog-api-key": key,
               "User-Agent": _BROWSER_UA}
    req = urllib.request.Request(
        base.rstrip("/") + "/publishers/google/models/%s:generateContent" % model,
        data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            code = int(getattr(r, "status", 200) or 200)
            raw = r.read(65536).decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        try:
            raw = e.read(65536).decode("utf-8", errors="replace")
        except Exception:
            raw = ""
        low = raw.lower()
        if e.code == 403 and ("has not been used" in low or "is disabled" in low or "permission_denied" in low):
            return {"status": "AUTH-DEAD",
                    "detail": ("generateContent 403 API disabled/unprovisioned for the key's "
                               "project: enable aiplatform per the B2-63 GO card, then rerun "
                               "B2_63_vertex_probe.py")}
        if e.code in (401, 403):
            return {"status": "AUTH-DEAD", "detail": "generateContent HTTP %s (deep probe)" % e.code}
        if e.code == 429:
            return {"status": "QUOTA-DEAD", "detail": "generateContent HTTP 429 (deep probe)"}
        return {"status": "DOWN", "detail": "generateContent HTTP %s (deep probe)" % e.code}
    except Exception as e:
        return {"status": "DOWN",
                "detail": ("POST generateContent failed %s (deep probe)" % type(e).__name__)[:220]}
    if not 200 <= code < 300:
        return {"status": "DOWN", "detail": "generateContent HTTP %s (deep probe)" % code}
    try:
        data = json.loads(raw)
    except Exception:
        return {"status": "DOWN", "detail": "generateContent 200 with unparseable body (deep probe)"}
    cands = data.get("candidates") or []
    parts = ((cands[0].get("content") or {}).get("parts") or []) if cands else []
    text = "".join(str(p.get("text") or "") for p in parts if isinstance(p, dict))
    if cands:
        return {"status": "ALIVE",
                "detail": "generateContent 200, candidates[0].content served (%d chars ping)" % len(text)}
    # B2-04 shape: a 200 with no candidates and a length stop is the budget
    # shape, lane live, caller's maxOutputTokens too small.
    return {"status": "DEGRADED",
            "detail": "generateContent 200 with no candidates (empty/length-stop shape, B2-04 class)"}


def _probe_remote_deep(base: str, timeout: float, model: str, key: str) -> dict[str, str]:
    """B2-04 deep remote probe (MAG_PROBE_REMOTE=1): GET {base}/models, then
    ONE one-token chat ping.

    A models-only 200 is NOT liveness: on 2026-09-26 cerebras (chat 402),
    nvidia (410), gemini (401) and mistral (429, x-ratelimit limits literally
    0) all served /models 200 while no inference was possible (receipt
    watch/inbox/PROVIDER_HEALTH_20260926.md). The ping is synthetic and
    public ("Reply with the single word: pong.", max_tokens 1), carries the
    browser UA per the Cloudflare-1010 law in models.providers, and never
    logs the key. Cost: one 1-token completion per call.
    """
    headers = {"User-Agent": _BROWSER_UA, "Authorization": "Bearer " + key}
    req = urllib.request.Request(base.rstrip("/") + "/models", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            code = int(getattr(r, "status", 200) or 200)
    except urllib.error.HTTPError as e:
        return {"status": "DOWN", "detail": "GET /models HTTP %s (deep probe)" % e.code}
    except Exception as e:
        return {"status": "DOWN",
                "detail": ("GET /models failed %s (deep probe)" % type(e).__name__)[:220]}
    if not 200 <= code < 300:
        return {"status": "DOWN", "detail": "GET /models HTTP %s (deep probe)" % code}

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "Reply with the single word: pong."}],
        "max_tokens": 1,
        "temperature": 0,
    }
    body = json.dumps(payload).encode("utf-8")
    chat_headers = dict(headers)
    chat_headers["Content-Type"] = "application/json"
    req = urllib.request.Request(base.rstrip("/") + "/chat/completions", data=body,
                                 headers=chat_headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            code = int(getattr(r, "status", 200) or 200)
            raw = r.read(65536).decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        try:
            raw = e.read(65536).decode("utf-8", errors="replace")
        except Exception:
            raw = ""
        hdrs = {k.lower(): str(v).strip() for k, v in (e.headers or {}).items()}
        return _classify_chat_failure(int(e.code), raw, hdrs)
    except Exception as e:
        return {"status": "DOWN",
                "detail": ("POST /chat/completions failed %s (deep probe)" % type(e).__name__)[:220]}
    # 2xx on the ping: the endpoint served inference. An empty content with a
    # length stop is the reasoning-budget shape B2-04 measured on z_ai
    # (thinking ate the whole budget): lane live, caller's budget too small,
    # NOT a dead lane.
    try:
        data = json.loads(raw)
        choice = (data.get("choices") or [{}])[0]
        msg = choice.get("message") or {}
        content = str(msg.get("content") or "")
        finish = str(choice.get("finish_reason") or "")
    except Exception:
        content, finish = "", ""
    if content.strip():
        return {"status": "ALIVE",
                "detail": "models 200 + chat ping 200, content '%s'" % content.strip()[:24]}
    if finish == "length":
        return {"status": "ALIVE",
                "detail": ("models 200 + chat ping 200 but empty content (finish=length: reasoning "
                           "ate the 1-token ping budget; lane live, B2-04 z_ai budget shape)")}
    return {"status": "ALIVE",
            "detail": "models 200 + chat ping 200 (response body had no parsable content)"}


def check_provider_endpoints(
    config_path: Path | None = None,
    timeout: float = 2.0,
    probe_remote: bool | None = None,
) -> dict[str, Any]:
    """Route-correct provider health surface (t86, 2026-09-25; B2-04, 2026-09-26).

    SPEC: module docstring, PROVIDER ENDPOINT PROBE MATRIX. Every provider in
    configs/providers.yaml is classified ALIVE / DORMANT / DOWN /
    REMOTE-UNVERIFIED / QUOTA-DEAD / AUTH-DEAD / DEGRADED / FENCED by a probe
    matched to its kind and locality:

      ollama-shaped local   GET {base minus /v1}/api/tags   (200 + models list)
      other local           TCP connect, then GET {base}/models
      local-declared (id ollama / :11434 / free_local) on a NON-LOCAL host
                            that this seat cannot resolve (inside the B2-489
                            _RESOLVE_TIMEOUT_S deadline): DOWN, probe
                            "none(locality)", default path, zero bytes
                            (B2-107 locality law; module docstring)
      remote                NO call by default (REMOTE-UNVERIFIED, config-only);
                            MAG_PROBE_REMOTE=1 opts into the B2-04 DEEP probe:
                            GET {base}/models + ONE 1-token chat ping, mapped
                            onto the measured classes (QUOTA-DEAD 402/410/
                            zero-limit-429, AUTH-DEAD 401, DEGRADED 1305 429)
      dormant: true         DORMANT, declared state, never probed, never alarms
      opencode_only         FENCED when remote-probing: coding-plan keys are
                            harness-only, raw probes are the fence-risk law

    GET /v1 is never used or trusted: it is a POST-only route, the operator's
    own false alarm (healthy ollama answers a browser GET /v1 with 404).
    Local probes dedupe on (style, base_url); the deep probe dedupes on
    (style, base_url, model, key fingerprint). base_url_env overrides are
    honored via models.providers.provider_base_url, the estate's own resolver.
    Loads the config through models.providers.load_providers (the same loader
    the estate uses) or an explicit fixture path parsed with the estate
    pattern.

    DOWN, QUOTA-DEAD and AUTH-DEAD are the alarm classes; they feed examine()
    issues so the doctor surfaces lanes that cannot serve a call instead of
    leaving the operator guessing. DEGRADED never alarms (should_burst owns
    the 1305 retry at call time); FENCED and DORMANT are declared states.
    """
    from models.providers import provider_base_url, provider_default_model, provider_keys

    load_err = ""
    providers: dict[str, Any] = {}
    if config_path is None:
        try:
            from models.providers import load_providers

            providers = dict(load_providers().get("providers") or {})
        except Exception as e:
            load_err = ("providers.yaml load failed: %s: %s" % (type(e).__name__, e))[:200]
    else:
        providers = _parse_providers_yaml(Path(config_path))
    if load_err:
        # Negatives are first-class: an unrunnable health check says so.
        return {"check": "provider_endpoints", "ok": False, "statuses": {},
                "providers": [],
                "issues": ["PROVIDER ENDPOINT CHECK UNRUNNABLE: " + load_err],
                "unverified": [], "probes_run": 0}
    if probe_remote is None:
        probe_remote = os.environ.get("MAG_PROBE_REMOTE") == "1"

    rows: list[dict[str, Any]] = []
    cache: dict[tuple[str, str], dict[str, str]] = {}
    probes_run = 0
    for pid in sorted(providers):
        pcfg = providers.get(pid)
        if not isinstance(pcfg, dict):
            continue
        dormant = bool(pcfg.get("dormant"))
        kind = str(pcfg.get("kind") or "openai_compat")
        try:
            base = provider_base_url(pcfg)
        except Exception as e:
            base = ""
        row: dict[str, Any] = {"provider": pid, "kind": kind, "base_url": base,
                               "dormant": dormant, "status": "?", "probe": "none", "detail": ""}
        if dormant:
            row.update(status="DORMANT", probe="none(dormant)",
                       detail="explicit dormant marker: declared state, not probed, not an alarm")
            rows.append(row)
            continue
        if not base:
            row.update(status="DOWN", probe="none",
                       detail="no base_url configured and base_url_env unset")
            rows.append(row)
            continue
        host = (urllib.parse.urlsplit(base).hostname or "").lower()
        local = host in _LOCAL_HOSTS
        if not local:
            # B2-107 locality law: a local-declared lane (the yaml's own
            # locality declaration: id ollama, :11434, or free_local: true)
            # on a host this seat cannot resolve is a misconfigured
            # base_url_env, not a remote lane. DOWN here, zero bytes, in
            # the default path; the pre-law surfaces lied both ways
            # (REMOTE-UNVERIFIED hid the trap, MAG_PROBE_REMOTE=1 read a
            # generic DOWN URLError naming no disease). A RESOLVABLE
            # non-local ollama stays a genuine remote lane below.
            declared_local = (
                pid == "ollama"
                or base.rstrip("/").removesuffix("/v1").removesuffix("/V1").endswith(":11434")
                or bool(pcfg.get("free_local"))
            )
            if declared_local and not _host_resolves(host):
                row.update(status="DOWN", probe="none(locality)",
                           detail=("host '%s' does not resolve from this seat: locality trap "
                                   "(docker-network name on the host?); the lane is "
                                   "local-declared so base_url_env must be host-reachable "
                                   "where the code runs (host shell: http://127.0.0.1:11434, "
                                   "compose: http://host.docker.internal:11434/v1)" % host)[:220])
                rows.append(row)
                continue
        if not local and not probe_remote:
            row.update(status="REMOTE-UNVERIFIED", probe="none(config-only)",
                       detail=("remote lane: no blind probing of paid endpoints, config-only; "
                               "MAG_PROBE_REMOTE=1 runs the B2-04 deep models+ping probe"))
            rows.append(row)
            continue
        if local and (pid == "ollama" or base.rstrip("/").endswith(":11434")):
            style = "api_tags"
        elif local:
            style = "tcp+models"
        else:
            style = "remote_models+chat"
        if style == "remote_models+chat":
            # B2-04 fences and dedupe: a models-only GET would be the exact
            # trap the deep probe exists to close, so fences are judged
            # BEFORE any byte leaves the machine.
            if pcfg.get("opencode_only"):
                row.update(status="FENCED", probe="none(fenced)",
                           detail=("opencode_only per providers.yaml law: coding-plan key refused on "
                                   "raw /paas/v4 (hangs/1305, fence risk); not probed, not an alarm"))
                rows.append(row)
                continue
            if kind == "gemini_native":
                # B2-194 (2026-09-26): the express key's native protocol gets
                # its own deep probe; a one-token generateContent ping is the
                # only honest liveness test for this kind (a models-style GET
                # would be the B2-04 catalog-alive trap again).
                gkeys = provider_keys(pcfg or {})
                gmodel = provider_default_model(pcfg or {}) or ((pcfg.get("models") or [None])[0])
                if not gkeys or not gmodel:
                    which = "API key" if not gkeys else "default_model/models entry"
                    row.update(status="REMOTE-UNVERIFIED",
                               probe="none(no-key)" if not gkeys else "none(no-model)",
                               detail=("gemini_native deep probe needs a key AND a model id; %s "
                                       "missing on file" % which))
                    rows.append(row)
                    continue
                if not probe_remote:
                    row.update(status="REMOTE-UNVERIFIED", probe="none(config-only)",
                               detail=("gemini_native lane: no blind probing of paid endpoints, "
                                       "config-only; MAG_PROBE_REMOTE=1 runs the one-token "
                                       "generateContent ping (B2-194)"))
                    rows.append(row)
                    continue
                gfp = hashlib.sha256(gkeys[0].encode("utf-8")).hexdigest()[:12]
                gck = ("gemini_native", base, str(gmodel), gfp)
                if gck in cache:
                    probe = dict(cache[gck])
                else:
                    probes_run += 1
                    probe = _probe_gemini_native_deep(
                        base, max(timeout, _REMOTE_PING_TIMEOUT_FLOOR), str(gmodel), gkeys[0])
                    cache[gck] = dict(probe)
                row.update(status=probe["status"], probe="gemini_native_ping",
                           detail=probe["detail"])
                rows.append(row)
                continue
            if kind != "openai_compat":
                row.update(status="REMOTE-UNVERIFIED", probe="none(kind)",
                           detail=("deep probe is an openai-compat chat ping; kind '%s' speaks another "
                                   "protocol and would false-alarm on a route mismatch" % kind))
                rows.append(row)
                continue
            keys = provider_keys(pcfg or {})
            model = provider_default_model(pcfg or {}) or ((pcfg.get("models") or [None])[0])
            if not keys or not model:
                which = "API key" if not keys else "default_model/models entry"
                row.update(status="REMOTE-UNVERIFIED",
                           probe="none(no-key)" if not keys else "none(no-model)",
                           detail=("deep probe needs a key AND a model id; %s missing on file; a "
                                   "catalog-only 200 would be the B2-04 trap (catalog alive, "
                                   "inference dead)" % which))
                rows.append(row)
                continue
            # Fingerprint, not value: dedupes z_ai2/z_ai3-style lane pairs and
            # nous/nous_api key chains without ever storing or printing a key.
            fp = hashlib.sha256(keys[0].encode("utf-8")).hexdigest()[:12]
            ckey = (style, base, str(model), fp)
            if ckey in cache:
                probe = dict(cache[ckey])
            else:
                probes_run += 1
                probe = _probe_remote_deep(base, max(timeout, _REMOTE_PING_TIMEOUT_FLOOR),
                                           str(model), keys[0])
                cache[ckey] = dict(probe)
        else:
            key = (style, base)
            if key in cache:
                probe = dict(cache[key])
            else:
                probes_run += 1
                if style == "api_tags":
                    probe = _probe_ollama_tags(base, timeout)
                else:
                    probe = _probe_tcp_then_models(base, timeout)
                cache[key] = dict(probe)
        row.update(status=probe["status"], probe=style, detail=probe["detail"])
        rows.append(row)

    statuses = {r["provider"]: r["status"] for r in rows}
    alarm_classes = ("DOWN", "QUOTA-DEAD", "AUTH-DEAD")
    dead = [r for r in rows if r["status"] in alarm_classes]
    unverified = [r["provider"] for r in rows if r["status"] == "REMOTE-UNVERIFIED"]
    degraded = [r["provider"] for r in rows if r["status"] == "DEGRADED"]
    fenced = [r["provider"] for r in rows if r["status"] == "FENCED"]
    prefix = {"DOWN": "PROVIDER ENDPOINT DOWN",
              "QUOTA-DEAD": "PROVIDER QUOTA DEAD",
              "AUTH-DEAD": "PROVIDER AUTH DEAD"}
    issues = [
        "%s: '%s' %s (%s)" % (prefix[r["status"]], r["provider"], r["base_url"], r["detail"])
        for r in dead
    ]
    return {
        "check": "provider_endpoints",
        "ok": not dead,
        "statuses": statuses,
        "providers": rows,
        "issues": issues,
        "unverified": unverified,
        "degraded": degraded,
        "fenced": fenced,
        "probes_run": probes_run,
    }


def check_model_sanity() -> dict[str, Any]:
    """Check that models referenced in the task router match available models."""
    from mag.task_router import MODELS

    issues = []
    model_status = {}

    for name, cfg in MODELS.items():
        provider = cfg["provider"]
        cost = cfg["cost"]

        if provider == "grok" and not (os.environ.get("XAI_API_KEY") or ""):
            issues.append(f"Model '{name}' requires Grok provider but XAI_API_KEY is not set")
            model_status[name] = "unavailable"
        elif provider == "deepseek" and not os.environ.get("DEEPSEEK_API_KEY", ""):
            model_status[name] = "unverified"
        elif provider == "ollama":
            model_status[name] = "local"
        else:
            model_status[name] = "ok"

    # Check for the specific error we made today: grok-4-latest vs grok-3-mini
    from mag.task_router import route_task, classify_task
    test_goal = "analyze the system architecture"
    route = route_task(test_goal)
    if route["model"] == "grok-4-latest" and route["task_type"] != "orchestrate":
        issues.append(
            f"TASK ROUTER WARNING: '{test_goal}' routes to {route['model']} "
            f"(${route['cost_est']}) but task type is '{route['task_type']}'. "
            f"Consider grok-3-mini ($0.003) for non-orchestrate tasks."
        )

    return {
        "check": "model_sanity",
        "ok": len(issues) == 0,
        "model_status": model_status,
        "issues": issues,
    }


def check_inbox_sanity() -> dict[str, Any]:
    """Check for malformed or dangerous messages in the copilot inbox."""
    inbox = ROOT / "memory" / "copilot" / "inbox.jsonl"
    if not inbox.is_file():
        return {"check": "inbox_sanity", "ok": True, "issues": [], "note": "No inbox file"}

    messages = _read_jsonl(inbox, tail=20)
    issues = []
    unprocessed = []

    for msg in messages:
        if msg.get("_processed"):
            continue
        unprocessed.append(msg)

        provider = msg.get("provider", "")
        model = msg.get("model", "")
        goal = msg.get("goal", "")

        # Check 1: provider must be registered
        valid_providers = {"ollama", "deepseek", "xai", "grok", "openai", "anthropic"}
        if provider not in valid_providers:
            issues.append(
                f"UNPROCESSED MESSAGE '{msg.get('id', '?')[:20]}': "
                f"unknown provider '{provider}'. Valid: {valid_providers}"
            )

        # Check 2: Grok-4-latest should only be used for orchestrate tasks
        if model == "grok-4-latest" and provider in ("grok", "xai"):
            from mag.task_router import classify_task
            task_type = classify_task(goal)
            if task_type != "orchestrate":
                issues.append(
                    f"UNPROCESSED MESSAGE '{msg.get('id', '?')[:20]}': "
                    f"using grok-4-latest (${0.025}) for '{task_type}' task. "
                    f"Consider grok-3-mini (${0.003})."
                )

        # Check 3: cost estimate
        cost_est = 0.0
        if model == "grok-4-latest":
            cost_est = 0.025
        elif model in ("grok-3-mini",):
            cost_est = 0.003
        elif provider == "deepseek":
            cost_est = 0.00013

        if cost_est > 0.01:
            issues.append(
                f"UNPROCESSED MESSAGE '{msg.get('id', '?')[:20]}': "
                f"estimated cost ${cost_est} — verify this task justifies the spend."
            )

    return {
        "check": "inbox_sanity",
        "ok": len(issues) == 0,
        "unprocessed_count": len(unprocessed),
        "issues": issues,
    }


def check_env_sanity() -> dict[str, Any]:
    """Check that required environment variables are set."""
    required = {
        "XAI_API_KEY": "Grok API access (set to XAI_MAG_KEY value from .env)",
        "DEEPSEEK_API_KEY": "DeepSeek API access",
    }
    optional = {
        "HF_TOKEN": "Hugging Face Spaces deployment",
        "HF_USERNAME": "Hugging Face username for Spaces",
        "REDIS_HOST": "Redis event bus host",
        "X_ACCESS_TOKEN": "X/Twitter API access",
        "X_USER_ID": "X/Twitter user ID",
    }

    issues = []
    for var, desc in required.items():
        if not os.environ.get(var):
            issues.append(f"MISSING: {var} — {desc}")

    warnings_list = []
    for var, desc in optional.items():
        if not os.environ.get(var):
            warnings_list.append(f"OPTIONAL: {var} not set — {desc}")

    # B2-358 env-redirect tripwire (2026-09-26): MAG_SEAT_CRASH_LOG and
    # MAG_GAPS_LOG are test isolation seams (mag.agent_cli._log_seat_crash,
    # mag.temperature_stack._gaps_log) whose writers report ok either way, so
    # an export leaked into a plain shell silently redirects the production
    # crash/gap logs. Warning only, never a hard env failure: dispatch is not
    # blocked on it, but every line names the variable and the redirect target.
    redirect_warnings = env_redirect_warnings()

    return {
        "check": "env_sanity",
        "ok": len(issues) == 0,
        "missing_required": issues,
        "missing_optional": warnings_list,
        "redirect_warnings": redirect_warnings,
    }


def check_chain_discipline() -> dict[str, Any]:
    """Check that modules use chain_query instead of reading the chain file directly.

    This would have caught the grep-over-chain pattern the assistant defaulted to.
    Every module that asks 'what do we know?' must go through chain_query.
    Direct reads of # CHAIN_QUERY_MIGRATION_NEEDED: replace with chain.tail() or chain.by_type() are a discipline violation.
    """
    issues = []
    mag_dir = ROOT / "mag"
    if not mag_dir.is_dir():
        return {"check": "chain_discipline", "ok": True, "issues": [], "note": "mag/ directory not found"}

    direct_read_patterns = [
        "# CHAIN_QUERY_MIGRATION_NEEDED: replace with chain.tail() or chain.by_type()",
        'memory/biography/verkle_chain',
    ]

    for py_file in sorted(mag_dir.glob("*.py")):
        if py_file.name == "chain_query.py":
            continue

        try:
            content = py_file.read_text(encoding="utf-8", errors="replace")
            for pattern in direct_read_patterns:
                if pattern in content:
                    imports_chain_query = "chain_query" in content or "from mag.chain_query" in content
                    if imports_chain_query:
                        continue
                    issues.append(
                        f"CHAIN DISCIPLINE: {py_file.name} reads # CHAIN_QUERY_MIGRATION_NEEDED: replace with chain.tail() or chain.by_type() directly "
                        f"instead of using chain_query. Import 'from mag.chain_query import chain' "
                        f"and use chain.tail(), chain.by_theme(), etc."
                    )
        except OSError:
            continue

    state_querying_modules = [
        "ghost.py", "doctor.py", "cost_enforcer.py", "steal_first.py",
        "task_router.py", "exit_dialogue.py", "signal_flare.py",
        "bard.py", "renderman.py", "depin.py", "holographic_q.py",
        "state_quantizer.py", "ghost_leak_detector.py", "behavioral_analytics.py",
    ]

    missing_import = []
    for module_name in state_querying_modules:
        module_path = mag_dir / module_name
        if module_path.is_file():
            try:
                content = module_path.read_text(encoding="utf-8", errors="replace")
                if "chain_query" not in content and "from mag.chain_query" not in content:
                    if module_name != "chain_query.py":
                        missing_import.append(
                            f"CHAIN DISCIPLINE: {module_name} does not import chain_query. "
                            f"It should use chain.tail(), chain.by_theme(), etc. for state queries."
                        )
            except OSError:
                continue

    issues.extend(missing_import)

    return {
        "check": "chain_discipline",
        "ok": len(issues) == 0,
        "issues": issues,
        "modules_checked": len(list(mag_dir.glob("*.py"))),
        "discipline_violations": len([i for i in issues if "directly" in i]),
        "missing_imports": len(missing_import),
    }


def check_memlance_discipline() -> dict[str, Any]:
    """Check that modules use ghost_memlance's CANONICAL surface (select/index), not guessed keys.

    2026-08-11 operator: "this is the same bug ... fix it automatically moving forward." The
    recurring bug = calling ghost_memlance then guessing its return key (e.g. .get("states"),
    .get("entries")) instead of reading the REAL shape. select() returns {selected: [...]},
    index() returns a LIST. This guard flags the guess-internals pattern automatically.
    """
    issues = []
    mag_dir = ROOT / "mag"
    if not mag_dir.is_dir():
        return {"check": "memlance_discipline", "ok": True, "issues": [],
                "note": "mag/ directory not found"}
    # guessed keys that are NOT what ghost_memlance returns (select->selected, index->list)
    guessed = ['.get("states")', '.get("entries")', '.get("results")', '.get("rows")']
    for py_file in sorted(mag_dir.glob("*.py")):
        if py_file.name == "ghost_memlance.py":
            continue
        try:
            content = py_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        # only modules that actually touch memlance
        if "ghost_memlance" not in content and "memlance" not in content:
            continue
        # does it use the canonical surface?
        uses_canonical = (".select(" in content) or (".index(" in content)
        if uses_canonical:
            continue
        # it references memlance but reads a guessed key / doesn't call select or index
        for g in guessed:
            if g in content:
                issues.append(
                    f"MEMLANCE DISCIPLINE: {py_file.name} reads a guessed key {g} on a memlance "
                    f"result instead of the canonical surface. Use ghost_memlance.select(goal,k)"
                    f" (returns {{selected:[...]}}) or index() (returns a list). Read the real "
                    f"shape from the code, never guess."
                )
                break
    return {"check": "memlance_discipline", "ok": len(issues) == 0,
            "issues": issues, "modules_checked": len(list(mag_dir.glob("*.py"))),
            "discipline_violations": len(issues)}


# ═══════════════════════════════════════════════════════════════════
# SCHEDULED TASK SANITY (t20, 2026-09-25)
# ═══════════════════════════════════════════════════════════════════

SCHEDULED_TASKS = ("MagImproveDaily",)


def _parse_schtask_list(stdout: str) -> str:
    """Extract the Status value from `schtasks /Query /FO LIST` output.

    A LIST block carries one `Status:` line. No Status line -> "?".
    """
    for line in (stdout or "").splitlines():
        if line.strip().lower().startswith("status:"):
            return line.split(":", 1)[1].strip() or "?"
    return "?"


def _scheduled_task_status(name: str) -> str:
    """Query a scheduled task's Status field (read-only, no elevation needed).

    Returns the schtasks Status string ('Ready' | 'Disabled' | 'Running' | ...),
    'MISSING' when the task is not registered, or '?' when the query fails or
    the platform is not Windows. Shape mirrors mag/amd_window_guard._task_status.
    """
    import subprocess
    import sys
    if os.name != "nt":
        return "?"
    try:
        r = subprocess.run(
            ["schtasks", "/Query", "/TN", name, "/FO", "LIST"],
            capture_output=True, text=True, timeout=15,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
            if sys.platform == "win32" else 0,
        )
    except Exception:
        return "?"
    if r.returncode != 0:
        return "MISSING"
    return _parse_schtask_list(r.stdout)


def check_scheduled_tasks(
    task_names: tuple[str, ...] = SCHEDULED_TASKS,
    _status_fn: Any = None,
    _platform: str | None = None,
    _intentional_fn: Any = None,
) -> dict[str, Any]:
    """Silent-disablement probe for Windows scheduled tasks.

    A task that got disabled or deleted keeps its job silently undone forever;
    until t20 (2026-09-25) no doctor check surfaced that. Flags any tracked
    task whose Status is not Ready. 'Running' also passes because it implies
    the task is registered and enabled; flagging it would false-alarm mid-run.
    MISSING (unregistered) is flagged as loudly as Disabled.

    t47 spec (2026-09-25): intentional-vs-silent disablement. A Disabled task
    is NOT flagged when lifecycle's intentional-disable marker exists
    (logs/magimprove_intentional.flag, written by
    mag.lifecycle.mark_improve_intentional per the lifecycle.py t47 spec):
    the disable was declared deliberate, so it is a state, not an alarm.
    The marker payload lands in the result under "intentional" so callers can
    see why it stayed quiet. MISSING still alarms even with the marker:
    the prescribed remediation is disable, not delete.

    t82 spec (2026-09-25): the Disabled remediation prescribes the t73
    executor `python main.py improve-on` first (re-register + marker clear
    on success); raw `schtasks /Change /TN <task> /ENABLE` is the elevated
    fallback only, since a blind /ENABLE skips marker clearing and the next
    doctor run misreads the re-enable as intentional.
    """
    if _status_fn is None:
        _status_fn = _scheduled_task_status
    if _intentional_fn is None:
        from mag.lifecycle import improve_intentional as _intentional_fn  # lazy: t47
    platform = _platform if _platform is not None else os.name
    if platform != "nt":
        return {"check": "scheduled_tasks", "ok": True, "statuses": {},
                "issues": [],
                "note": "skipped: schtasks is Windows-only (platform=%s)" % platform}
    statuses = {t: _status_fn(t) for t in task_names}
    issues = []
    intentional: dict[str, Any] = {}
    for t, s in statuses.items():
        sl = s.strip().lower()
        if sl in ("ready", "running"):
            continue
        if sl == "disabled":
            marker = _intentional_fn() or {}
            if marker:
                intentional[t] = marker
                continue  # t47: declared deliberate, a state not an alarm
            # t82 receipt: this prescription previously named only raw
            # `schtasks /Change /TN <task> /ENABLE`, which skips t73's marker
            # clearing (a blind /ENABLE leaves logs/magimprove_intentional.flag
            # stale, so the next doctor run misreads the re-enable as
            # intentional). Aligned per t81's next_steal to prescribe
            # `python main.py improve-on` (t73 executor: re-register via
            # scripts/register_improve_task.ps1, marker cleared ONLY on
            # success) first, raw /ENABLE as elevated fallback.
            issues.append(
                "SCHEDULED TASK DISABLED: '%s' is Disabled, its job silently stopped. "
                "Re-enable: python main.py improve-on (clears the intentional "
                "marker on success). Elevated fallback: schtasks /Change /TN %s /ENABLE"
                % (t, t))
        elif sl == "missing":
            issues.append(
                "SCHEDULED TASK MISSING: '%s' is not registered in Task Scheduler "
                "(deleted or never created), its job now runs silently never. "
                "Recreate: scripts/register_improve_task.ps1" % t)
        elif sl == "?":
            issues.append(
                "SCHEDULED TASK UNQUERYABLE: status of '%s' could not be determined "
                "(schtasks failed or output unparsed), treat as suspect and verify "
                "with: schtasks /Query /TN %s /FO LIST" % (t, t))
        else:
            issues.append(
                "SCHEDULED TASK NOT READY: '%s' status is '%s' (expected Ready), "
                "its job may silently not run" % (t, s))
    return {"check": "scheduled_tasks", "ok": len(issues) == 0,
            "statuses": statuses, "issues": issues, "intentional": intentional}


# ═══════════════════════════════════════════════════════════════════
# FULL EXAMINATION
# ═══════════════════════════════════════════════════════════════════

def check_tracked_secrets() -> dict[str, Any]:
    """Live-value secret scan over ALL tracked content (P0 law, 2026-09-30).

    The 16-day steps.jsonl leak (7 live keys committed since 09-14, receipt
    watch/inbox/last_mile_20260930/AG1_SECRETS_CONTAINMENT.md) happened because
    every gate checked key SHAPES, never live VALUES. This check is the
    doctor's missing arm: every live .env value is searched against every
    tracked file at HEAD. Any hit is an ERROR naming file + env name only —
    values are never printed. Non-secret names (hosts/URIs/client-ids/model
    names, the audit's own classification) are excluded, same law as
    tools/precommit_secret_check.py. Fail-closed: unparseable .env or git
    failure is a cannot-verify ERROR, never a silent pass.
    """
    import subprocess
    import sys

    from mag.trajectory_step import redactions  # one law with the hook + gate

    non_secret_suffixes = ("_HOST", "_URI", "_URL", "_MODEL", "_ClientID")
    non_secret_names = {"OLLAMA_HOST", "X_ClientID", "X_REDIRECT_URI", "AOS_AGENT_MODEL"}
    env_file = ROOT / ".env"
    try:
        pairs = [(n, v) for n, v in redactions(env_file)
                 if n not in non_secret_names and not n.endswith(non_secret_suffixes)]
    except Exception as exc:
        return {"check": "tracked_secrets", "ok": False,
                "issues": [f"tracked_secrets: cannot parse {env_file.name}: {exc}"],
                "missing_optional": []}
    if not pairs:
        return {"check": "tracked_secrets", "ok": False,
                "issues": [f"tracked_secrets: no live values parsed from {env_file.name} — cannot verify (fail-closed)"],
                "missing_optional": []}
    issues: list[str] = []
    for name, value in pairs:
        if len(value) < 8:
            continue
        try:
            proc = subprocess.run(
                ["git", "grep", "-l", "--fixed-strings", value, "HEAD", "--"],
                cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8",
                errors="replace", creationflags=0x08000000 if sys.platform == "win32" else 0,
            )
        except Exception as exc:
            issues.append(f"tracked_secrets: git grep failed for {name}: {exc}")
            continue
        if proc.returncode == 0 and proc.stdout.strip():
            for path in sorted(set(proc.stdout.splitlines())):
                issues.append(f"tracked_secrets: LIVE VALUE of {name} present in tracked file {path} at HEAD — untrack/redact/rotate")
    return {"check": "tracked_secrets", "ok": not issues, "issues": issues, "missing_optional": []}


def check_self_steal() -> dict[str, Any]:
    """Self-steal capability-utilization check: surfaces where our own systems aren't being used.

    Surfaces under-utilized internal capabilities (stale/absent/unwired) so doctor/maintenance
    can see where the architecture isn't leveraging its own machinery (e.g. verkle anchoring).
    """
    try:
        from mag.self_steal import audit
        a = audit()
    except Exception as e:
        return {"check": "self_steal", "ok": False, "issues": [f"self_steal audit error: {e}"], "missing_optional": []}
    issues = []
    for f in a.get("findings", []):
        issues.append(f"self_steal: capability '{f['capability']}' utilization={f['utilization']} "
                      f"age_s={f['age_s']} wired={f['wired']} -> {f['recommendation']}")
    return {"check": "self_steal", "ok": len(issues) == 0, "issues": issues, "missing_optional": []}


def check_system_tracking() -> dict[str, Any]:
    """GAP-ANALYSIS HEALTH CHECK: verify every system is present, wired, and tracking data.

    Each system must (a) import, (b) have its store on disk, and (c) hold tracked data
    (non-empty registry/ledger/graph). Ensures nothing we built is a silent empty shell.
    """
    def _rows(p: Path) -> int:
        if not p.is_file():
            return 0
        try:
            return sum(1 for ln in p.read_text(encoding="utf-8", errors="replace").splitlines() if ln.strip())
        except Exception:
            return 0

    def _js(p: Path) -> int:
        if not p.is_file():
            return 0
        try:
            import json as _j
            d = _j.loads(p.read_text(encoding="utf-8"))
            return 1 if isinstance(d, dict) and d else 0
        except Exception:
            return 0

    # (name, module, store_path, expected-kind, min_rows)
    systems = [
        ("mycelium", "mag.mycelium", ROOT / "memory/mycelium/graph_snapshot.json", "json", 1),
        ("republic_os", "mag.republic_os", ROOT / "memory/runs/republic_os/state.json", "json", 1),
        ("comms_trail", "mag.comms_trail", ROOT / "memory/runs/comms_trail/state.json", "json", 1),
        ("memlang", "mag.memlang", ROOT / "memory/runs/memlang/registry.json", "json", 1),
        ("research_lens", "mag.research_lens", ROOT / "memory/lenses/corpus_index.json", "json", 1),
        ("grok_free", "mag.grok_free", ROOT / "memory/runs/grok_free/usage.jsonl", "lines", 1),
        ("cheap_swarm", "mag.cheap_swarm", ROOT / "memory/runs/cheap_swarm/dispatched.jsonl", "lines", 1),
        ("frontier_help", "mag.frontier_help", ROOT / "memory/frontier/HELP_WANTED.md", "lines", 1),
        ("aos_grok", "mag.aos_grok", ROOT / "memory/embassy/AOS/grok_usage.jsonl", "lines", 1),
        ("grok_mirror", "mag.grok_mirror", ROOT / "memory/runs/grok_mirror", "dir_files", 1),
        ("gap_map", "mag.gap_map", ROOT / "memory/runs/gap_map/stack.json", "json", 0),
        ("cost_learn", "mag.cost_learn", ROOT / "memory/training/cost_ledger.jsonl", "lines", 1),
    ]
    issues = []
    tracked = []
    for name, module, store, kind, min_rows in systems:
        ok_module, ok_store, ok_data = False, False, False
        try:
            __import__(module)
            ok_module = True
        except Exception:
            pass
        ok_store = store.exists()
        if kind == "dir_files":
            ok_store = store.is_dir()
            ok_data = len(list(store.glob("*.json"))) >= min_rows if ok_store else False
        elif ok_store:
            n = _rows(store) if kind == "lines" else _js(store)
            ok_data = n >= min_rows
        status = "ok" if (ok_module and ok_store and ok_data) else "gap"
        if status != "ok":
            issues.append(f"tracking gap: {name} module={ok_module} store={ok_store} data={ok_data} ({store})")
        else:
            tracked.append(name)
    # ghost self-window must exist (agent_state authored by ghost-self)
    try:
        from mag.agent_state import load_latest
        lat = load_latest() or {}
        if lat.get("label") == "ghost-self":
            tracked.append("ghost_self_window")
        else:
            issues.append("ghost self-window not authored (agent_state LATEST != ghost-self)")
    except Exception as e:
        issues.append(f"ghost self-window check error: {e}")
    return {"check": "system_tracking", "ok": len(issues) == 0, "issues": issues,
            "tracked": tracked, "systems_checked": len(systems) + 1, "missing_optional": []}


def examine() -> DoctorReport:
    """Run all doctor checks. Returns a full report."""
    checks = [
        check_provider_sanity(),
        check_provider_endpoints(),
        check_model_sanity(),
        check_inbox_sanity(),
        check_env_sanity(),
        check_chain_discipline(),
        check_memlance_discipline(),
        check_scheduled_tasks(),
        check_tracked_secrets(),
    ]
    try:
        checks.append(check_self_steal())
    except Exception:
        pass
    try:
        checks.append(check_system_tracking())
    except Exception:
        pass

    errors = []
    warnings = []
    for c in checks:
        if not c["ok"]:
            for issue in c.get("issues", []):
                if "WARNING" in issue or "OPTIONAL" in issue:
                    warnings.append(issue)
                else:
                    errors.append(issue)
        if c.get("missing_optional"):
            warnings.extend(c["missing_optional"])
        # B2-358: the env-redirect tripwire rides report.warnings the same way.
        if c.get("redirect_warnings"):
            warnings.extend(c["redirect_warnings"])

    return DoctorReport(
        ok=len(errors) == 0,
        checks=checks,
        errors=errors,
        warnings=warnings,
    )


def doctor_status() -> dict[str, Any]:
    """Quick status check for the doctor protocol."""
    report = examine()
    return {
        "schema": "doctor.v1",
        "ts": _now(),
        "ok": report.ok,
        "errors": len(report.errors),
        "warnings": len(report.warnings),
        "checks_run": len(report.checks),
        "details": {c["check"]: {"ok": c["ok"], "issues": len(c.get("issues", []))} for c in report.checks},
    }
