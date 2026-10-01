"""frontier_advisor — a DRAINABLE task handler: spend the scarce frontier allowance on a code-planning
/ frontier-research ask, steer the real frontier seat, and fold the answer. Runs HEADLESS via the
drainer (orchestrator.spawn_task recognizes the `[frontier-advice]` prefix), NOT by hand-run.

OPERATOR (2026-08-12): "so use it please. for code advice and instruction" + "you design tools you
need you don't ask for them."

THE DESIGN: I don't hand-run the frontier seat — I built a task type the ARCHITECTURE executes. When a
goal starts with `[frontier-advice]`, the drainer:
    1. RECOMMEND — frontier_council.recommend(ask) -> the right surface (chatgpt -> grok_web ->
       grok_x -> deepseek) by work type + remaining weekly allowance.
    2. SPEND     — frontier_council.spend(ask, surface) records the scarce allowance use (routing
       guard: data/maintenance never burns frontier).
    3. STEER     — drive the real seat (chatgpt_bot / grok_bot / browser_driver) with the ask and
       read the answer. Honest: if the seat is down, report it — never fabricate.
    4. FOLD      — write the answer + spend to memory/runs/frontier_advice/ so the wave keeps it.

Schema: frontier_advisor.v1 · deterministic $0 for routing; steer costs the surface's allowance.
Reuse: frontier_council, chatgpt_bot, grok_bot, browser_driver.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from typing import Any

try:
    from config import ROOT
except Exception:
    from pathlib import Path as _P
    ROOT = _P(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "frontier_advisor.v1"
REPORT_DIR = ROOT / "memory" / "runs" / "frontier_advice"

PREFIX = "[frontier-advice]"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _strip_prefix(goal: str) -> str:
    g = (goal or "").strip()
    if g.lower().startswith(PREFIX.lower()):
        g = g[len(PREFIX):].strip()
    return g


def _steer(surface: str, ask: str, *, max_wait_s: int = 180) -> dict[str, Any]:
    """Drive the real frontier seat for the ask and return its answer. Honest: never fabricates."""
    if surface == "chatgpt":
        from mag import chatgpt_bot
        return chatgpt_bot.steer(ask, surface="chatgpt", max_wait_s=max_wait_s)
    if surface in ("grok_web", "grok_x"):
        from mag import grok_bot
        bd_surface = "grok" if surface == "grok_web" else "x"
        return grok_bot.steer(ask, surface=bd_surface, max_wait_s=max_wait_s)
    # deepseek (free) — the free front-end
    from mag import browser_driver as bd
    r = bd.ask(ask, surface="deepseek", max_wait_s=max_wait_s)
    return {"ok": r.get("ok", False), "surface": "deepseek",
            "answer": r.get("answer", ""), "error": r.get("error")}


def execute_goal(goal: str, *, dry: bool = False) -> dict[str, Any]:
    """Run one frontier-advice task end-to-end: recommend -> spend -> steer -> fold."""
    ask = (_strip_prefix(goal)
           or "give concrete code planning / frontier research advice, brief and actionable, "
              "grounded in what we have.")
    try:
        from mag import frontier_council
        rec = frontier_council.recommend(ask)
        surface = rec.get("surface", "deepseek")
    except Exception as e:
        return {"ok": False, "schema": SCHEMA, "goal": goal[:160],
                "error": f"recommend failed: {str(e)[:120]}"}
    # record the scarce spend (routing guard inside spend refuses non-frontier on scarce surfaces)
    spend = {}
    try:
        from mag import frontier_council as fc
        spend = fc.spend(ask, surface)
    except Exception as e:
        spend = {"error": str(e)[:120]}
    if dry:
        return {"ok": True, "schema": SCHEMA, "dry": True, "surface": surface,
                "spend": spend, "ask": ask[:200],
                "note": "dry run — no steer; would steer the " + surface + " seat"}
    # STEER the real seat (may be down — report honestly, never fabricate)
    try:
        sr = _steer(surface, ask)
    except Exception as e:
        sr = {"ok": False, "error": f"steer failed: {str(e)[:160]}"}
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ts = _now()
    row = {"schema": SCHEMA, "ts": ts, "goal": ask[:400], "surface": surface,
           "recommend": rec, "spend": spend, "answer": sr.get("answer", ""),
           "ok": bool(sr.get("ok"))}
    report = REPORT_DIR / f"advice_{ts[:19].replace(':','').replace('-','').replace('T','_')}.json"
    report.write_text(json.dumps(row, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": bool(sr.get("ok")), "schema": SCHEMA, "surface": surface,
            "spend": spend, "answer": (sr.get("answer") or "")[:2000],
            "report": str(report.relative_to(ROOT)),
            "honest": "if the seat was down this reports it — the answer is never fabricated"}


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "contract": "execute_goal('[frontier-advice] <ask>') -> recommend (surface by work type "
                        "+ allowance) -> spend (routing guard) -> steer the real seat -> fold the "
                        "answer to memory/runs/frontier_advice/. Runs headless via the drainer; the "
                        "agent never hand-runs it.",
            "reuse": "frontier_council + chatgpt_bot + grok_bot + browser_driver",
            "cost": "routing $0; the steer consumes the surface's weekly allowance (scarce frontier "
                    "only for code planning / frontier research)"}


def route() -> dict[str, Any]:
    """EXTERNAL-STEAL (operator standing law): route the drainable-frontier-advice research through
    the ONE primitive (swarm_surface.route_novel). SELF-STEAL already folded: the [frontier-advice]
    handler mirrors orchestrator's [steward]/[token-chain] inline handlers; the council self-stole
    agent_state_router + model_pick + elevate. EXTERNAL: go find OTHER systems — budget-capped
    multi-frontier delegation, quota-managed LLM gateways, task-queue-executes-a-scarce-resource
    patterns — and adapt their mechanisms to our deterministic shape. Idempotent (dedupe by anchor)."""
    from mag import swarm_surface
    goal = ("RESEARCH-PACK frontier-advisor (STEAL both): the drainable [frontier-advice] task type "
            "— the drainer executes a scarce-frontier spend headless (recommend by work type -> "
            "record allowance -> steer the real seat -> fold the answer). SELF-STEAL (folded): "
            "mirrors orchestrator's [steward]/[token-chain] inline handlers; reuses frontier_council "
            "(agent_state_router model_shape + model_pick + elevate). EXTERNAL-STEAL: go find OTHER "
            "budget-capped multi-frontier delegation systems, quota-managed LLM gateways, and "
            "task-queue-executes-a-scarce-resource patterns, and adapt their mechanisms to our "
            "deterministic, architecture-native shape (contracts only, no wholesale copy). Produce a "
            "concrete design so the republic spends scarce frontier allowance at maximum velocity.")
    r = swarm_surface.route_novel(goal, surface="frontier-advisor",
                                  lens="drainable scarce-resource spend, budget-capped delegation",
                                  domain="research")
    return {"ok": r.get("ok"), "schema": SCHEMA, "route": r,
            "note": "the external-steal research is routed through the ONE primitive (idempotent)"}


if __name__ == "__main__":
    import argparse, json
    ap = argparse.ArgumentParser(prog="frontier-advisor")
    ap.add_argument("goal", nargs="*", default=[])
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    g = " ".join(a.goal) or "[frontier-advice] give concrete code planning advice"
    print(json.dumps(execute_goal(g, dry=a.dry), indent=2, default=str))
