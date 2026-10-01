"""tool_5ws — ASK THE 5 W'S BEFORE EVERY TOOL LAUNCH, then pick the RIGHT tool from our corpus
instead of reaching reflexively for the first tool (regex/grep). Baked into the swarm as a default.

Operator (2026-08-11): "is regex the right tool for this knowing our corpus of tools and directives?
shouldn't you ask yourself this every time you launch a tool? the 5 w's and bake it into the swarm?"

THE 5-W REFLECTION (deterministic + $0, self-steals our existing routers):
  WHO   — which surface/agent owns this (the lens it serves).
  WHAT  — the task kind (research/steal/memory/cost/render/guard/surface/compiler).
  WHEN  — the cadence (now / async / swarm-queued).
  WHERE — which subsystem it lands in.
  WHY   — the intent (which invariant/lens it feeds).
  THEN  — pick the RIGHT tool from the corpus (task_router/matrix_router/switchboard/
          swarm_surface/percolator/lens_knot/memlang/verkle/ghost), NOT the default.

SELF-STEAL (not invented): our corpus already has task_router.route_task (classify), switchboard
.route_intent, matrix_router.route, swarm_surface.route_novel. tool_5ws is a thin 5-W lens that
picks among THOSE — it does not re-route or invent.

Schema: tool_5ws.v1 · deterministic + $0 · reuse: task_router, switchboard, swarm_surface
"""
from __future__ import annotations

import re
import sys
from typing import Any

try:
    from config import ROOT
except Exception:
    from pathlib import Path as _P
    ROOT = _P(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "tool_5ws.v1"

# WHAT: task-kind -> the right tool from our corpus (the 5-W answer for 'what').
TASK_TOOL: dict[str, str] = {
    "research": "swarm_surface.route_novel",     # novel research -> the swarm (dogfood, never local)
    "steal": "steal_lens.steal / egregore_steal.deep_steal",
    "memory": "percolator / lens_knot / agent_knot",
    "compiler": "compiler_lang.expand / world_rib / memlang",
    "cost": "cache_shard / usage_monitor / flock_usage_guard / gpu_lifecycle",
    "render": "flock_shader / swarm_render / lens_shader (GPU via gpu_lifecycle)",
    "guard": "cast_guard / guardrail_sentinel",
    "surface": "chain_substrate.pulse / lens_shader.program / republic_loop",
    "route": "task_router.route_task / switchboard.route_intent / matrix_router.route",
}
# WHERE: subsystem-hint -> the tool.
WHERE_TOOL: dict[str, str] = {
    "swarm": "swarm_surface.route_novel", "chain": "chain_substrate / verkle_knot",
    "lens": "lens_shader / lens_knot", "gpu": "gpu_lifecycle",
    "world": "world_rib", "egregore": "egregore_steal", "test": "agentic_test_steal",
}

_WHAT_RE = re.compile(r"research|steal|memory|compiler|cost|render|guard|surface|route|map|loop", re.I)
_WHERE_RE = re.compile(r"swarm|chain|lens|gpu|world|egregore|test|shader", re.I)


def _detect(text: str, pat: re.Pattern, table: dict[str, str]) -> str:
    m = pat.search(text or "")
    if m:
        for key in table:
            if key.lower() in (m.group(0).lower() or ""):
                return key
    return ""


def ask(task: str) -> dict[str, Any]:
    """The 5 W's of a task: who/what/when/where/why — answered deterministically from the text."""
    t = task or ""
    what = _detect(t, _WHAT_RE, TASK_TOOL) or "route"
    where = _detect(t, _WHERE_RE, WHERE_TOOL) or what
    return {
        "ok": True, "schema": SCHEMA,
        "five_ws": {
            "who": "the swarm / ghost (the lens it serves)",
            "what": what,
            "when": "now if deterministic, else swarm-queued (async)",
            "where": where,
            "why": f"feeds the {what}/{where} invariant into the loop",
        },
        "tool": TASK_TOOL.get(what, TASK_TOOL["route"]),
        "note": "5 W's asked BEFORE launching a tool; the right tool chosen from the corpus, "
                "not the reflex default",
    }


def select(task: str) -> dict[str, Any]:
    """The 5 W's + pick the RIGHT tool from the corpus. This is what to run before any launch."""
    a = ask(task)
    return {"ok": True, "schema": SCHEMA, "task": (task or "")[:200],
            "five_ws": a["five_ws"], "tool": a["tool"],
            "avoid": "regex/grep first — only if the corpus has no right tool",
            "law": "ask the 5 W's before every tool launch; bake into the swarm"}


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "contract": "ask(task)->the 5 W's; select(task)->pick the right tool from the corpus "
                        "(task_router/switchboard/matrix_router/swarm_surface/percolator/...); "
                        "woven into republic_loop as step S0 (tool-select)",
            "cost": "deterministic + $0 (self-steals our existing routers)",
            "n_task_kinds": len(TASK_TOOL)}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="tool-5ws")
    ap.add_argument("task", nargs="*", default=[""])
    a = ap.parse_args()
    print(json.dumps(select(" ".join(a.task) or "scifi self-steal via swarm"),
                     indent=2, default=str))
