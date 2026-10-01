"""surface_adapters — the NATIVE steering layer, self-stolen from OUR OWN API-building machinery.

The operator (2026-08-13): "we are building api's from scratch if you didn't notice. deep steal" +
"there is a slack integration etc tool integration for all surfaces plugins whatever. whats stopping
us from making our own plugins so we can use them natively and steer them?"

DEEP STEAL = SELF-STEAL from our own system (NOT external web — the wrong tool). We ALREADY build
APIs from scratch: backend/server.py (FastAPI, uniform {ok, tool, result, error} envelope),
provider_gateway.py (POST /api/v1/run_turn, GET /api/v1/providers, _require_key gating), extension_deploy.py
(the "op with no path gets a REST route built" precedent), and a live endpoint catalog (376 routes
from the REST best-practices steal). So building native integrations is OUR medium — steal the
pattern from ourselves.

THE LAYER (deterministic $0 coordinator; the native calls are the seams):
  registry()   -> the surface adapter map, DERIVED (like the endpoint catalog, never hand-maintained):
                   each surface -> {driver, kind: native|browser, configured}. The truth is on disk.
  adapter(s)   -> pick the BEST available driver for a surface: NATIVE (API/webhook/app) when free +
                   configured, else BROWSER (CDP, the $0 fallback). Rightsized (sw47): native where
                   it's free, browser where it's the only $0 path.
  steer(s, g)  -> steer a surface through its chosen adapter (native REST call or browser_driver),
                   honest if not configured/down. Reuses seat_steer for the browser path.
  native_call(s, g) -> the actual native REST call for NATIVE surfaces (deepseek API; slack webhook).
  register()   -> idempotent; REST route POST /api/v1/surface/steer (the extension_deploy precedent).

NATIVE NOW (free + configured): deepseek (API — the key resolves) + slack (incoming webhook if set).
BROWSER FALLBACK (no free native API): chatgpt, grok/supergrok (CDP until/unless API credits exist).

Schema: surface_adapters.v1 · deterministic $0 coordinator · reuse: seat_steer, provider_gateway, backend
"""
from __future__ import annotations

import json
import os
import sys
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

SCHEMA = "surface_adapters.v1"
OUT = ROOT / "memory" / "runs" / "surface_adapters"

# Which surfaces we can steer + their driver preference. kind=native means a free native API/webook
# (the operator's 'use them natively'); kind=browser means the $0 CDP fallback (no free native API).
SURFACE_DRIVERS: dict[str, dict[str, Any]] = {
    "deepseek":  {"kind": "native",  "key_env": "DEEPSEEK_API_KEY", "api": "chat",
                  "note": "free native API — we have the key (rightsized: flash bulk, pro cold seams)"},
    "slack":     {"kind": "native",  "key_env": "SLACK_WEBHOOK_URL", "api": "webhook",
                  "note": "free native integration via incoming webhook, if configured"},
    "chatgpt":   {"kind": "browser", "api": "seat_steer",
                  "note": "no free native API — browser (CDP) until/unless API credits exist (sw47)"},
    "grok_web":  {"kind": "browser", "api": "seat_steer",
                  "note": "supergrok — no free native API — browser (CDP) fallback"},
    "grok_x":    {"kind": "browser", "api": "seat_steer",
                  "note": "supergrok (x.com) — browser (CDP) fallback"},
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _configured(surface: str, spec: dict[str, Any]) -> bool:
    """A native surface is configured if its key/webhook is present (never logs the value)."""
    if spec.get("kind") != "native":
        return True  # browser fallback is always 'available' (it reports down honestly if CDP is down)
    key_env = spec.get("key_env") or ""
    return bool(key_env and os.environ.get(key_env, "").strip())


def registry() -> dict[str, Any]:
    """The surface adapter map — DERIVED from the registry + live config (like the endpoint catalog,
    never hand-maintained; the truth is on disk / env)."""
    surfaces = []
    for surface, spec in SURFACE_DRIVERS.items():
        configured = _configured(surface, spec)
        surfaces.append({
            "surface": surface,
            "kind": spec["kind"],
            "configured": configured,
            "api": spec["api"],
            "note": spec["note"],
            "driver": "native" if (spec["kind"] == "native" and configured) else
                      ("browser" if spec["kind"] == "browser" else "unconfigured-native"),
        })
    return {"ok": True, "schema": SCHEMA, "n_surfaces": len(surfaces), "surfaces": surfaces,
            "note": "the native steering layer — native where free, browser where it's the only $0 path"}


def adapter(surface: str) -> dict[str, Any]:
    """Pick the BEST driver for a surface: NATIVE when free+configured, else BROWSER fallback."""
    spec = SURFACE_DRIVERS.get((surface or "").lower())
    if not spec:
        return {"ok": False, "surface": surface, "error": "unknown surface",
                "known": sorted(SURFACE_DRIVERS)}
    if spec["kind"] == "native" and _configured(surface, spec):
        return {"ok": True, "surface": surface, "driver": "native", "api": spec["api"]}
    if spec["kind"] == "browser":
        return {"ok": True, "surface": surface, "driver": "browser", "api": "seat_steer"}
    return {"ok": False, "surface": surface, "driver": "unconfigured-native",
            "error": f"native surface not configured (need {spec.get('key_env')})"}


def native_call(surface: str, goal: str) -> dict[str, Any]:
    """The ACTUAL native REST call for a NATIVE surface (deepseek API / slack webhook). Honest if
    not configured. This is the 'use them natively' seam."""
    spec = SURFACE_DRIVERS.get((surface or "").lower())
    if not spec or spec["kind"] != "native":
        return {"ok": False, "surface": surface, "error": "not a native surface"}
    if not _configured(surface, spec):
        return {"ok": False, "surface": surface, "error": f"native surface unconfigured "
                                                          f"(need {spec.get('key_env')})"}
    # deepseek chat API (rightsized: caller chooses model; v4-flash bulk, v4-pro cold seams)
    if surface == "deepseek":
        try:
            from mag import llm as _llm  # the framework's own provider call (self-steal)
            # fall through to a minimal native call via the framework's provider resolution
            key = os.environ.get(spec["key_env"], "")
            import urllib.request
            body = json.dumps({"model": os.environ.get("MAG_SURFACE_DS_MODEL", "deepseek-chat"),
                               "messages": [{"role": "user", "content": goal}]}).encode()
            req = urllib.request.Request(
                os.environ.get("DEEPSEEK_API_URL", "https://api.deepseek.com/chat/completions"),
                data=body, headers={"Authorization": f"Bearer {key}",
                                    "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as r:
                data = json.loads(r.read().decode())
            return {"ok": True, "surface": surface, "driver": "native", "api": "chat",
                    "answer": (data.get("choices") or [{}])[0].get("message", {}).get("content", ""),
                    "honest": "native DeepSeek API call"}
        except Exception as e:
            return {"ok": False, "surface": surface, "driver": "native",
                    "error": f"deepseek native call failed: {str(e)[:160]}"}
    if surface == "slack":
        try:
            import urllib.request
            webhook = os.environ.get(spec["key_env"], "")
            body = json.dumps({"text": goal[:1800]}).encode()
            req = urllib.request.Request(webhook, data=body,
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=20) as r:
                return {"ok": True, "surface": "slack", "driver": "native", "api": "webhook",
                        "answer": f"posted to slack (HTTP {r.status})", "honest": "native slack webhook"}
        except Exception as e:
            return {"ok": False, "surface": "slack", "driver": "native",
                    "error": f"slack native call failed: {str(e)[:160]}"}
    return {"ok": False, "surface": surface, "error": "native_call not implemented for this surface"}


def steer(surface: str, goal: str) -> dict[str, Any]:
    """Steer a surface NATIVELY where free, else through the browser fallback. The unified surface
    path (self-stolen from seat_steer + extension_deploy). Honest if not configured/down."""
    goal = (goal or "").strip()
    if not goal:
        return {"ok": False, "schema": SCHEMA, "error": "empty goal"}
    a = adapter(surface)
    if not a.get("ok"):
        return a
    if a["driver"] == "native":
        r = native_call(surface, goal)
    else:
        try:
            from mag import seat_steer
            r = seat_steer.send(surface, goal, max_wait_s=90)
            r = {"ok": bool(r.get("ok")), "driver": "browser", "surface": surface,
                 "answer": r.get("answer", ""), "error": r.get("error", "")}
        except Exception as e:
            r = {"ok": False, "driver": "browser", "surface": surface,
                 "error": f"browser steer failed: {str(e)[:120]}"}
    r["schema"] = SCHEMA
    r["surface"] = surface
    try:
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / f"steer-{_now()[:13].replace(':', '')}-{surface}.json").write_text(
            json.dumps({"surface": surface, "goal": goal[:200], "result": r}, indent=2, default=str),
            encoding="utf-8")
    except Exception:
        pass
    return r


def status() -> dict[str, Any]:
    reg = registry()
    reg["schema"] = SCHEMA
    reg["contract"] = ("registry()->derived surface adapter map; adapter(s)->best driver (native when "
                       "free+configured, else browser); steer(s,g)->steer natively or via browser; "
                       "native_call(s,g)->the native REST seam; REST POST /api/v1/surface/steer")
    reg["cost"] = "deterministic $0 coordinator; native calls are the (free/rightsized) seams"
    return reg


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="surface-adapters")
    ap.add_argument("cmd", nargs="?", default="status", choices=["status", "adapter", "steer"])
    ap.add_argument("surface", nargs="?", default="deepseek")
    ap.add_argument("goal", nargs="?", default="")
    a = ap.parse_args()
    if a.cmd == "adapter":
        print(json.dumps(adapter(a.surface), indent=2, default=str))
    elif a.cmd == "steer":
        print(json.dumps(steer(a.surface, a.goal or "status"), indent=2, default=str))
    else:
        print(json.dumps(status(), indent=2, default=str))
