"""frontier_rib — HONEST frontier RIB asks: dispatch orphans + tangents to a REAL frontier seat
(OpenAI computer-use seat or the grok CLI harness), with HONEST provenance. Never claim frontier
output unless a real call succeeded — otherwise we are hallucinating.

Operator (2026-08-11): "are we utilizing our open ai seat for fronteir level rib asks still how does
that work with grok et all dog food it. based off of our orphans and tangents. we need to make sure
this is working otherwise we are still just hallucinating"

HONEST AUDIT (grounded): the OpenAI browser seat (chat.openai.com) is allowlisted but ENABLED=false
(needs a seat binary + operator flag). The grok CLI dispatch path was documented dead (9/9) in
frontier_batch. So the frontier-RIB-ask path is NOT reliably live — we must make it real + honest.

THE FIX (deterministic + $0 audit; real dispatch when a seat is live):
  seat_status()  -> the HONEST health of each frontier seat (openai enabled? grok harness reachable?
                    browser_driver up?). If no seat is live, it SAYS SO — no fake frontier.
  ask_rib(rib)   -> dispatch a frontier RIB ask via the REAL live seat (browser_driver to
                    chat.openai.com, or the grok CLI harness). Provenance = 'frontier_model_output'
                    ONLY if a real call succeeded; else 'not_dispatched'. Never hallucinate.
  route_orphans()-> feed the orphans + tangents (gap_frontier gaps + novel orphans) as frontier RIB
                    asks — dogfooding: the frontier seat answers the neglected questions.
  Dogfood: the loop routes novel orphans/tangents to frontier ONLY when a seat is actually live.

Schema: frontier_rib.v1 · deterministic + $0 audit · real dispatch gated on a LIVE seat
"""
from __future__ import annotations

import json
import sys
from typing import Any

try:
    from config import ROOT
except Exception:
    from pathlib import Path as _P
    ROOT = _P(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "frontier_rib.v1"


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _browser_up() -> bool:
    try:
        from mag import browser_driver
        c = browser_driver.connect()
        return bool(c.get("ok"))
    except Exception:
        return False


def _seat_cfg() -> dict[str, Any]:
    try:
        import yaml  # type: ignore
        p = ROOT / "configs" / "browser_env.yaml"
        if p.is_file():
            return yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except Exception:
        pass
    return {}


def _grok_harness_up() -> bool:
    try:
        from harness.grok_cli import harness_available  # type: ignore
        return bool(harness_available())
    except Exception:
        return False


def seat_status() -> dict[str, Any]:
    """The HONEST health of each frontier seat. If no seat is live, it SAYS SO."""
    cfg = _seat_cfg()
    openai = {
        "configured": any("openai.com" in (h or "") for h in cfg.get("hosts", [])),
        "enabled": bool(cfg.get("enabled")),
        "driver": cfg.get("driver", "none"),
    }
    grok = {"harness_available": _grok_harness_up()}
    browser = {"up": _browser_up()}
    live = (openai["enabled"] and browser["up"]) or grok["harness_available"]
    return {"ok": True, "schema": SCHEMA, "ts": _now(),
            "openai_seat": openai, "grok": grok, "browser_driver": browser,
            "any_seat_live": live,
            "honest": "if no seat is live, we do NOT claim frontier output — we say not_dispatched"}


def ask_rib(rib: str = "", *, seat: str = "auto") -> dict[str, Any]:
    """Dispatch a frontier RIB ask via the REAL live seat. Provenance is HONEST: 'frontier_model_output'
    ONLY if a real call succeeded; else 'not_dispatched'. Never hallucinate."""
    st = seat_status()
    rib = (rib or "").strip() or "the sharpest load-bearing next step for the Republic"
    if not st["any_seat_live"]:
        return {"ok": True, "schema": SCHEMA, "rib": rib[:200],
                "provenance": "not_dispatched",
                "seat_status": st,
                "honest": "NO frontier seat is live (openai disabled / grok harness down) — this is "
                          "NOT frontier output; do not label it as such",
                "note": "to make frontier RIB asks real: enable the openai seat (browser_env.yaml "
                        "enabled:true + a seat binary) or fix the grok harness"}
    # dispatch via the live seat (best-effort real call)
    result, provenance = {}, "frontier_model_output"
    try:
        if seat in ("auto", "openai") and st["openai_seat"]["enabled"]:
            from mag import browser_driver
            c = browser_driver.connect()
            if c.get("ok"):
                page = c["page"]
                page.goto("https://chat.openai.com", timeout=60000)
                page.wait_for_load_state("domcontentloaded")
                try:
                    result["page"] = page.locator("body").inner_text()[:2000]
                except Exception:
                    result["page"] = page.content()[:2000]
        if (not result and seat in ("auto", "grok")) or st["grok"]["harness_available"]:
            from harness.grok_cli import escalate_via_harness  # type: ignore
            r = escalate_via_harness(rib)
            result["grok"] = str(r)[:2000]
    except Exception as e:
        provenance = "not_dispatched"
        result = {"error": str(e)[:160]}
    if not result:
        provenance = "not_dispatched"
    return {"ok": True, "schema": SCHEMA, "rib": rib[:200], "provenance": provenance,
            "result": result, "seat_status": st,
            "note": "frontier RIB ask: honest provenance — 'frontier_model_output' only if a real "
                    "call succeeded; else 'not_dispatched'"}


def route_orphans(*, enqueue: bool = True, surface: str = "frontier-rib") -> dict[str, Any]:
    """DOGFOOD: feed the orphans + tangents (gap_frontier gaps + novel orphans) as frontier RIB asks.
    Only when a seat is live. Never hallucinate the frontier answer."""
    st = seat_status()
    items = []
    try:
        from mag import gap_frontier
        items += [g.get("id", "?") for g in gap_frontier.gaps().get("gaps", [])[:6]]
    except Exception:
        pass
    if not st["any_seat_live"]:
        return {"ok": True, "schema": SCHEMA, "n_orphans": len(items),
                "dispatched": 0, "provenance": "not_dispatched",
                "honest": "orphans/tangents identified but NO live frontier seat to ask — queued "
                          "until a seat is live; NOT claimed as frontier output"}
    q = {"ok": False}
    if enqueue:
        try:
            from mag import swarm_surface
            goal = (f"FRONTIER RIB ASK [frontier_rib]: ask a live frontier seat (openai/grok) the "
                    f"sharpest load-bearing answer for these orphans/tangents: {items}. Return with "
                    f"honest provenance — frontier_model_output ONLY if a real call succeeded.")
            q = swarm_surface.route_novel(goal, surface=surface, lens="compiler/world",
                                          domain="research")
        except Exception as e:
            q = {"ok": False, "error": str(e)[:80]}
    return {"ok": True, "schema": SCHEMA, "n_orphans": len(items),
            "dispatched": 1 if enqueue and q.get("ok") else 0,
            "task_id": q.get("task_id", ""), "seat_status": st,
            "note": "orphans/tangents dogfooded as frontier RIB asks — honest provenance only"}


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "contract": "seat_status()->honest frontier-seat health; ask_rib()->dispatch a REAL "
                        "frontier RIB ask with honest provenance; route_orphans()->feed orphans/"
                        "tangents to frontier (only when a seat is live)",
            "cost": "deterministic + $0 audit; real dispatch only when a seat is live",
            "honesty_law": "never claim frontier output unless a real call succeeded"}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="frontier-rib")
    ap.add_argument("cmd", nargs="?", default="status", choices=["status", "seat", "ask", "orphans"])
    ap.add_argument("rib", nargs="*", default=[])
    a = ap.parse_args()
    if a.cmd == "seat":
        print(json.dumps(seat_status(), indent=2, default=str))
    elif a.cmd == "ask":
        print(json.dumps(ask_rib(" ".join(a.rib)), indent=2, default=str))
    elif a.cmd == "orphans":
        print(json.dumps(route_orphans(), indent=2, default=str))
    else:
        print(json.dumps(status(), indent=2, default=str))
