"""frontier_council — spend the ENTIRE weekly frontier allowance on the strongest advice, and make
the frontier work WITH deepseek + vram toward our goals.

OPERATOR (2026-08-12): "how can we get frontier advice from chat gpt? i have a basic license and i
want it to work together with you and deepseek and my vram most effectively towards our goals but
use the entire weekly allowance same with both grok desktop chat surfaces."

THE DOCTRINE, made literal (rightsize-everywhere + cost-baseline):
  Frontier surfaces are a FINITE, VALUABLE allowance — a scarce resource. They exist for FRONTIER
  ADVICE (the strongest judgment/strategy/synthesis), not for cheap deterministic work. GROUND TRUTH
  (operator 2026-08-12):
    * SUPERGROK (both grok desktop chat surfaces: grok.x.ai + x.com) is a LIMITED RESOURCE — NOT our
      local VRAM model. It runs the frontier models grok-4.5 / grok-5.6 / sol / extra-high, and the
      operator has TWO accounts (nacho + sd) — a shared, scarce weekly allowance across both.
    * chat.deepseek.com is FREE (unlimited front-end) — not scarce, not a paid API.
    * ChatGPT basic is a scarce weekly allowance.
    * VRAM is our local $0 render/cache/inference.
  So:
    1. ROUTE BY WORK TYPE (operator 2026-08-12, explicit):
         * DEEPSEEK (free, HIGH QUALITY front-end) -> DATA + MAINTENANCE + tactical volume.
         * GROK/GPT (scarce frontier allowance)     -> CODE PLANNING + FRONTIER RESEARCH + strategy.
         * VRAM (local)                             -> render / cache / inference.
       Never spend scarce frontier on what the free deepseek tier does at high quality.
    2. SPEND THE WHOLE ALLOWANCE — a scarce resource that runs out weekly is wasted if left unspent;
       we track each surface's used/cap (and supergrok's 2 accounts) and keep delegating the
       strongest asks until the weekly budget is USED, not hoarded, not exceeded.
    3. VELOCITY-FIRST — we have limited time. The council routes FAST: classify the work type, pick
       the right surface immediately, and build. Max velocity = right tool per job, zero dithering.
    4. COUNCIL — ChatGPT + supergrok (2 accounts) + DeepSeek (free) + VRAM (local) work together:
       grok/gpt plan the code + research the frontier, deepseek does the free data/maintenance
       volume, VRAM renders/caches locally, and I (the agent) route and fold the answers back into
       the wave.

HONESTY: we do NOT know the exact weekly cap of ChatGPT basic or supergrok (operator/provider-side
and changes). So the cap is OPERATOR-SETTABLE (memory/frontier/caps.json, defaults below); we track
what we actually spend (memory/frontier/allowance.jsonl) and report used/remaining so the operator
can aim to use the full allowance without ever exceeding it.

Schema: frontier_council.v1 · deterministic + $0 · reuse: elevate, browser_driver, cost_learn
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from typing import Any

try:
    from config import ROOT
except Exception:
    from pathlib import Path as _P
    ROOT = _P(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "frontier_council.v1"
FRONTIER_DIR = ROOT / "memory" / "frontier"
ALLOWANCE = FRONTIER_DIR / "allowance.jsonl"   # every frontier spend, append-only
CAPS = FRONTIER_DIR / "caps.json"              # operator-settable weekly caps

# The council: every surface, its role, and its weekly allowance model.
#  cap = weekly allowance in "ask units" (0 = not scarce: free/unlimited/local). Honest defaults —
#  operator sets real caps in memory/frontier/caps.json.
# GROUND TRUTH (operator 2026-08-12): supergrok (both grok surfaces) is a LIMITED resource with 2
# accounts (nacho + sd), running grok-4.5/5.6/sol/extra-high; chat.deepseek is FREE.
SURFACES: dict[str, dict[str, Any]] = {
    "chatgpt": {
        "role": "frontier advice (basic license)",
        "driver": "browser_driver chatgpt (chatgpt.com front-end)",
        "cap": 40,        # operator-settable — basic ChatGPT weekly ask budget
        "scarce": True,
        "model_shape": "reasoning",  # self-steal: agent_state_router vocabulary
        "models": ["chatgpt-basic"],
        "accounts": ["nacho"],
    },
    "grok_web": {
        "role": "frontier advice — SUPERGROK (grok desktop, grok.x.ai)",
        "driver": "browser_driver grok (grok.x.ai front-end)",
        "cap": 20,        # operator-settable — supergrok is a LIMITED resource
        "scarce": True,   # CORRECTED: supergrok is scarce, NOT our local, NOT free
        "model_shape": "reasoning",
        "models": ["grok-4.5", "grok-5.6", "sol", "extra-high"],
        "accounts": ["nacho", "sd"],  # 2 accounts share the supergrok allowance
    },
    "grok_x": {
        "role": "frontier advice — SUPERGROK (grok inside X, x.com)",
        "driver": "browser_driver x (x.com front-end)",
        "cap": 20,
        "scarce": True,   # same limited supergrok resource
        "model_shape": "reasoning",
        "models": ["grok-4.5", "grok-5.6", "sol", "extra-high"],
        "accounts": ["nacho", "sd"],
    },
    "deepseek": {
        "role": "volume / tactical work (FREE front-end)",
        "driver": "chat.deepseek.com front-end (free, unlimited)",
        "cap": 0,         # FREE — not scarce
        "scarce": False,
        "model_shape": "cheap",  # self-steal: janitor/maintenance shape in agent_state_router
        "models": ["deepseek-v4-flash"],
        "accounts": ["nacho"],
    },
    "vram": {
        "role": "local rendering / caching / inference (VRAM, $0 local)",
        "driver": "local GPU / ram_cache / vram_memory",
        "cap": 0,
        "scarce": False,
        "model_shape": "local",
        "models": ["local"],
        "accounts": ["nacho"],
    },
}


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load_caps() -> dict[str, int]:
    """Load operator-settable weekly caps; merge over defaults. Never crashes on missing file."""
    caps = {k: v["cap"] for k, v in SURFACES.items()}
    if CAPS.is_file():
        try:
            caps.update({k: int(v) for k, v in json.loads(CAPS.read_text(encoding="utf-8")).items()})
        except Exception:
            pass
    return caps


def _spend_ledger() -> dict[str, int]:
    """Count spends in the current ISO week, not the all-time ledger.

    The ledger is intentionally append-only, but allowance consumption is a
    weekly window.  Counting every historical row made a healthy reset look
    permanently exhausted and silently routed frontier work to the cheap tier.
    """
    counts: dict[str, int] = {}
    now = datetime.now(timezone.utc)
    week_start = (now - timedelta(days=now.weekday())).date()
    if ALLOWANCE.is_file():
        for line in ALLOWANCE.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
                s = row.get("surface", "")
                stamp = str(row.get("ts") or "")
                try:
                    row_date = datetime.fromisoformat(stamp.replace("Z", "+00:00")).date()
                except (ValueError, TypeError):
                    row_date = now.date()
                if s and row_date >= week_start:
                    counts[s] = counts.get(s, 0) + 1
            except Exception:
                continue
    return counts


def allowance() -> dict[str, Any]:
    """Report the weekly allowance state per surface: used / cap / remaining, and whether the scarce
    frontier budget is being USED (not hoarded, not exceeded). Honest: caps are operator-settable."""
    caps = _load_caps()
    used = _spend_ledger()
    rows = []
    for name, meta in SURFACES.items():
        cap = caps.get(name, meta["cap"])
        u = used.get(name, 0)
        rows.append({"surface": name, "role": meta["role"], "used": u, "cap": cap,
                     "remaining": (cap - u) if cap else None,  # None = not scarce
                     "scarce": meta["scarce"]})
    # scarce = finite weekly budget; total remaining across scarce surfaces
    scarce_remaining = sum(r["remaining"] for r in rows if r["scarce"] and r["remaining"] is not None)
    return {"ok": True, "schema": SCHEMA, "surfaces": rows,
            "scarce_remaining_total": scarce_remaining,
            "doctrine": "a scarce weekly allowance is wasted if left unspent — spend the whole "
                        "budget on the STRONGEST asks (frontier advice), never hoard, never exceed",
            "note": "caps are operator-settable in memory/frontier/caps.json (defaults are honest "
                    "estimates, not provider truth)"}


# WORK-TYPE ROUTING LAW (operator 2026-08-12, explicit): grok/gpt (scarce frontier) is for CODE
# PLANNING + FRONTIER RESEARCH; deepseek (free, high quality) is for DATA + MAINTENANCE. Route by
# work type, velocity-first. These keyword sets are the classifier.
FRONTIER_KINDS = (
    "code", "plan", "architect", "design", "frontier", "research", "strategy", "recommend",
    "synthesize", "evaluate", "assess", "roadmap", "new", "build", "blueprint", "tactics",
)
DEEPSEEK_KINDS = (
    "data", "maintenance", "process", "refactor", "cleanup", "ingest", "corpus", "migrate",
    "dedupe", "batch", "monitor", "log", "backfill", "maintain", "tactical", "volume",
)


def route_type(goal: str) -> dict[str, Any]:
    """Classify a goal's WORK TYPE: frontier (code planning / frontier research / strategy) vs
    deepseek (data / maintenance / tactical volume) vs local. This is the operator's explicit
    routing law, applied velocity-first."""
    g = (goal or "").lower()
    fw = [k for k in FRONTIER_KINDS if k in g]
    ds = [k for k in DEEPSEEK_KINDS if k in g]
    # frontier wins on ties: code planning / frontier research is the scarce high-value spend
    if fw and len(fw) >= len(ds):
        return {"ok": True, "schema": SCHEMA, "type": "frontier",
                "why": f"code planning / frontier research signals: {fw[:4]}", "kinds": fw}
    if ds:
        return {"ok": True, "schema": SCHEMA, "type": "deepseek",
                "why": f"data / maintenance signals: {ds[:4]}", "kinds": ds}
    # no strong signal: fall back to the elevate judgment signal
    try:
        from mag import elevate
        if elevate.should_elevate(goal):
            return {"ok": True, "schema": SCHEMA, "type": "frontier",
                    "why": "elevate-worthy (judgment/strategy)", "kinds": []}
    except Exception:
        pass
    return {"ok": True, "schema": SCHEMA, "type": "deepseek",
            "why": "default to the free high-quality tier — keep scarce frontier for code/research",
            "kinds": []}


def rightsize(goal: str) -> dict[str, Any]:
    """DECIDE which surface a goal goes to, BY WORK TYPE (operator law): code planning / frontier
    research -> the scarce frontier (grok/gpt); data / maintenance / tactical volume -> free
    deepseek; local render/cache -> vram. Velocity-first: classify fast, route immediately. This is
    the rightsize-everywhere law applied to the council."""
    t = route_type(goal)
    if t["type"] == "frontier":
        return {"ok": True, "schema": SCHEMA, "goal": goal[:160], "tier": "frontier",
                "surface": "council", "work_type": "code-planning / frontier-research",
                "why": t["why"], "else": "deepseek"}
    return {"ok": True, "schema": SCHEMA, "goal": goal[:160], "tier": "deepseek",
            "surface": "deepseek", "work_type": "data / maintenance / tactical",
            "why": t["why"], "note": "deepseek front-end is free + high quality for data/maintenance"}


def spend(goal: str, surface: str) -> dict[str, Any]:
    """RECORD a frontier spend against a scarce surface's weekly allowance (append-only ledger).
    ROUTING GUARD (operator law): we only spend scarce frontier allowance on code planning / frontier
    research work types — never on data/maintenance that the free deepseek tier does at high
    quality. Returns used/cap so the operator can see the budget being USED toward the full weekly
    allowance."""
    s = SURFACES.get(surface)
    if not s:
        return {"ok": False, "schema": SCHEMA, "error": f"unknown surface {surface}"}
    if s["scarce"]:
        t = route_type(goal or "")
        if t["type"] != "frontier":
            return {"ok": False, "schema": SCHEMA, "surface": surface,
                    "error": "routing guard: data/maintenance doesn't consume scarce frontier "
                             "allowance — use the free high-quality deepseek tier"}  # noqa: E501
    FRONTIER_DIR.mkdir(parents=True, exist_ok=True)
    with ALLOWANCE.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"schema": SCHEMA, "surface": surface, "goal": (goal or "")[:200],
                            "ts": _now()}, ensure_ascii=False) + "\n")
    caps = _load_caps()
    used = _spend_ledger()
    u = used.get(surface, 0)
    cap = caps.get(surface, s["cap"])
    return {"ok": True, "schema": SCHEMA, "surface": surface, "used": u,
            "cap": cap, "remaining": (cap - u) if cap else None,
            "note": "spend recorded; scarce allowance is budgeted to be USED (not hoarded) — aim "
                    "for the full weekly allowance on the strongest asks"}


def _resolve_model(goal: str, surface: str) -> dict[str, Any]:
    """Self-steal (agent_state_router + model_pick): fold the model_shape + actual model for the
    chosen surface. For deepseek (auto-ish tier) reuse model_pick.recommend_model to pick flash vs
    pro; for frontier surfaces the model is the supergrok/ChatGPT set the operator holds."""
    meta = SURFACES.get(surface, {})
    shape = meta.get("model_shape", "balanced")  # the council's shape for this surface (self-steal)
    model = None
    if surface == "deepseek":
        try:
            from mag import model_pick
            rec = model_pick.recommend_model(goal)
            model = rec.get("model")  # refine the specific model (flash/pro) — not the shape
        except Exception as e:
            model = "deepseek-v4-flash"
    else:
        model = (meta.get("models") or [None])[0]
    return {"surface": surface, "model_shape": shape, "model": model}


def recommend(goal: str) -> dict[str, Any]:
    """The self-stolen full recommendation (agent_state_router + model_pick + the council routing
    law): classify the work type, pick the surface (scarce frontier only for code planning / frontier
    research), and resolve the model_shape + actual model. Velocity-first: one call, a ready plan."""
    r = rightsize(goal)
    used = _spend_ledger()
    caps = _load_caps()
    surface = r["surface"]
    if r["tier"] == "frontier":
        # The X surface remains visible in the council census, but the
        # executable delegate path is limited to the two surfaces with a
        # proven browser driver.  Do not claim a route to an unproven surface.
        order = ["chatgpt", "grok_web"]
        surface = None
        for s in order:
            cap = caps.get(s, SURFACES[s]["cap"]) or 0
            if (cap - used.get(s, 0)) > 0:
                surface = s
                break
        if surface is None:
            surface = "deepseek"
    res = _resolve_model(goal, surface)
    return {"ok": True, "schema": SCHEMA, "goal": goal[:160], "work_type": r["work_type"],
            "tier": r["tier"], "surface": surface, "model_shape": res["model_shape"],
            "model": res["model"], "why": r["why"],
            "note": "self-stolen from agent_state_router + model_pick: the work type -> surface -> "
                    "model_shape -> model chain, under the operator's routing law"}


def delegate(goal: str) -> dict[str, Any]:
    """Route a goal through the council to the best surface, given its strength + remaining
    allowance, and shape the ask (reuse elevate). The frontier and cheap surfaces work TOGETHER:
    frontier -> strongest advice; deepseek -> volume; vram -> local render/cache; the agent folds
    the answers back into the wave. Returns the plan (surface + shaped ask + model_shape)."""
    rec = recommend(goal)
    ask = ""
    try:
        from mag import elevate
        ask = elevate.shape_ask(goal)["ask"]
    except Exception:
        ask = goal
    return {"ok": True, "schema": SCHEMA, "goal": goal[:160], "tier": rec["tier"],
            "surface": rec["surface"], "model_shape": rec["model_shape"],
            "model": rec["model"], "shaped_ask": ask,
            "council": "ChatGPT + supergrok (2 accounts: nacho+sd, grok-4.5/5.6/sol/extra-high) give "
                       "frontier advice; deepseek is free (unlimited); vram renders/caches locally; "
                       "the agent routes + folds. Together, toward our goals, using the full weekly "
                       "frontier allowance."}


def council() -> dict[str, Any]:
    """The council view: every surface, its role, its driver, and how they coordinate toward goals."""
    a = allowance()
    members = []
    for row in a["surfaces"]:
        meta = SURFACES[row["surface"]]
        members.append({"surface": row["surface"], "role": row["role"],
                        "driver": meta["driver"], "used": row["used"], "cap": row["cap"]})
    return {"ok": True, "schema": SCHEMA, "council": members,
            "coordination": "frontier (chatgpt + both grok) -> strongest advice on scarce allowance; "
                            "deepseek -> volume/tactical; vram -> local render/cache; agent -> route "
                            "+ fold. Use the ENTIRE weekly frontier allowance on the strongest asks.",
            "scarce_remaining_total": a["scarce_remaining_total"]}


def route() -> dict[str, Any]:
    """Route the research through the ONE primitive (swarm_surface.route_novel): how to get frontier
    advice from a basic ChatGPT license + both Grok surfaces and spend the ENTIRE weekly allowance
    while working together with deepseek + vram. The swarm researches the allowance-spend strategy so
    the republic learns to use scarce frontier budget optimally. Idempotent (dedupe by anchor)."""
    from mag import swarm_surface
    goal = ("RESEARCH-PACK frontier-council (STEAL both): how to get frontier advice from a BASIC "
            "ChatGPT license + both Grok desktop chat surfaces (grok.x.ai + x.com) and spend the "
            "ENTIRE weekly allowance while working together with deepseek + vram toward goals. "
            "SELF-STEAL (already folded): agent_state_router model_shape vocabulary (reasoning/cheap/"
            "auto/balanced) + model_pick for the deepseek tier + elevate for the ask shape. The "
            "doctrine: route BY WORK TYPE — grok/gpt (scarce) for code planning + frontier research, "
            "deepseek (free, high quality) for data/maintenance, vram (local) for render/cache; a "
            "scarce weekly allowance is wasted if left unspent, so track used/cap and delegate the "
            "strongest asks until the whole weekly budget is USED, never hoarded, never exceeded. "
            "EXTERNAL-STEAL: go find OTHER multi-provider routing / budget-capped delegation systems "
            "(router agents, cost-aware model routing, quota-managed LLM gateways) and adapt their "
            "mechanisms to our deterministic shape. Produce a concrete plan.")
    r = swarm_surface.route_novel(goal, surface="frontier-council",
                                  lens="scarce weekly allowance spend, frontier delegation, rightsize",
                                  domain="research")
    return {"ok": r.get("ok"), "schema": SCHEMA, "route": r,
            "note": "the frontier-allowance strategy research is routed through the ONE primitive"}

def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "contract": "allowance()->weekly used/cap/remaining per surface; rightsize(goal)->which "
                        "tier (frontier vs cheap); spend(goal,surface)->record a scarce spend (rightsized "
                        "guard); delegate(goal)->route to the best surface + shape the ask; council()-"
                        ">the coordinated team; route()->send research to the swarm",
            "cost": "deterministic + $0 (reuses elevate + browser_driver)",
            "doctrine": "use the ENTIRE weekly frontier allowance on the strongest asks; frontier + "
                        "deepseek + vram work together toward our goals"}


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="frontier-council")
    ap.add_argument("cmd", nargs="?", default="status",
                    choices=["allowance", "rightsize", "spend", "delegate", "council", "route", "status"])
    ap.add_argument("goal", nargs="*", default=[])
    ap.add_argument("--surface", default="chatgpt")
    a = ap.parse_args(argv)
    import json as _json
    g = " ".join(a.goal)
    out: dict[str, Any]
    if a.cmd == "allowance":
        out = allowance()
    elif a.cmd == "rightsize":
        out = rightsize(g or "review the strategic direction")
    elif a.cmd == "spend":
        out = spend(g or "advice on the roadmap", a.surface)
    elif a.cmd == "delegate":
        out = delegate(g or "synthesize our strategic direction for the week")
    elif a.cmd == "council":
        out = council()
    elif a.cmd == "route":
        out = route()
    else:
        out = status()
    print(_json.dumps(out, indent=2, default=str))
    return 0


if __name__ == "__main__":
    main()
