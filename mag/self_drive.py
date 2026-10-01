"""Self-driving ask — pick the model, redo the prompt, attach cached context on the fly,
inject learned principles, and spawn — automatically.

The operator wants a coding session that doesn't drift between flash/pro and doesn't lose the
plot: it should (1) pick the right model (tier_probe rule), (2) REDO the raw goal into a clean
spec, (3) assemble CACHED context on the fly (frozen prefix / handoff maze), (4) inject the
LEARNED principles (case law + remedies from the ledger/failure-KB), and (5) DRIVE it — all
autonomously. This is the ask-representation contract made real.

Composes the modules built/audited this session:
  model_pick  -> model_shape / is_handoff / context_plan
  router      -> depth / tier / seat
  context_pack -> fresh frozen prefix  |  session_maze -> handoff maze
  failure_kb  -> learned remedies / recurring patterns
  skill_ledger-> learned case law (decisions)
  orchestrator-> spawn the task

CLI:  python -m mag.self_drive "<goal>"            (print the full plan)
      python -m mag.self_drive --spawn "<goal>"    (print plan + actually spawn)
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

SCHEMA = "self_drive.v1"

_FLASH = "deepseek-v4-flash"
_PRO = "deepseek-v4-pro"


def redraft(goal: str, *, model_shape: str = "balanced") -> str:
    """Redo the raw operator goal into a clean, model-shaped spec (deterministic)."""
    goal = (goal or "").strip()
    if not goal:
        return ""
    verb = "REASON + PLAN (do not auto-run): " if model_shape == "reasoning" else "EXECUTE: "
    return (
        f"{verb}{goal}\n"
        "CONTRACT: state the concrete deliverable, the acceptance check (byte-verify / test), "
        "and the next action. Be concise. If this is a continuation, read the attached handoff "
        "maze and continue — do not re-derive what is frozen there."
    )


def cached_context(goal: str, *, is_handoff: bool = False) -> dict[str, Any]:
    """Assemble the cached context on the fly: fresh frozen prefix OR handoff maze."""
    out: dict[str, Any] = {"plan": "fresh_context_pack", "text": "", "sources": []}
    try:
        if is_handoff:
            from mag.session_maze import persist as maze_persist

            p = maze_persist()
            hp = p.get("handoff") or ""
            if hp:
                from pathlib import Path
                txt = Path(hp).read_text(encoding="utf-8", errors="replace")
                out["plan"] = "handoff_maze"
                out["text"] = txt[:4000]
                out["sources"] = ["state/HANDOFF.md"]
            return out
    except Exception as e:
        out["handoff_error"] = str(e)[:120]
    try:
        from mag.context_pack import build_context_pack, format_context_pack_text

        pack = build_context_pack()
        out["text"] = format_context_pack_text(pack)[:6000]
        out["sources"] = ["memory/briefs/latest.md", "context_pack"]
    except Exception as e:
        out["context_error"] = str(e)[:120]
    return out


def learned_principles(goal: str, *, limit: int = 3) -> dict[str, Any]:
    """Pull learned principles relevant to this goal: remedies/patterns + recent case law."""
    out: dict[str, Any] = {"remedies": [], "case_law": 0, "text": ""}
    try:
        from mag.failure_kb import surface_hits

        hits = surface_hits(goal=goal, limit=limit)
        out["remedies"] = [{"sig": h.get("sig"), "remedy": h.get("remedy")} for h in hits if h.get("sig")]
    except Exception:
        pass
    try:
        # recent case law from the skill ledger decisions file (deterministic read)
        from pathlib import Path
        d = Path(__file__).resolve().parent.parent / "memory" / "improve" / "skill_ledger.jsonl"
        rows = []
        if d.is_file():
            for line in d.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:]:
                if not line.strip():
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        out["case_law"] = len(rows)
        if rows:
            out["text"] = "\n".join(
                f"- {r.get('goal','')[:60]} -> {r.get('outcome') or 'decision'}"
                for r in rows if r.get("goal")
            )[:1200]
    except Exception:
        pass
    return out


def plan(goal: str, agent_state: str | None = None) -> dict[str, Any]:
    """The full self-driving plan (no spawn): agent state -> model + redraft + cached + learned.

    If a custom agent_state (research-agent / janitor-agent / coding-agent / default) is held,
    routing consumes it FIRST: the state's resource spec selects model / model_shape /
    thinking / effort / skills / memory_context / context_plan. For model_shape=auto states
    (coding-agent) the goal shape (model_pick) folds in to right-size the model.
    """
    from mag.agent_state_router import pick as state_pick

    spec: dict[str, Any] = {}
    state = (agent_state or "").strip()
    if state:
        spec = state_pick(state, goal)
        if not spec.get("ok"):
            return {"ok": False, "schema": SCHEMA, "goal": goal[:300], "agent_state": state,
                    "error": spec.get("error"), "known": spec.get("known")}
    from mag.model_pick import recommend_model

    if spec:
        shape = str(spec.get("model_shape") or "balanced")
        model = spec.get("model")
        is_handoff = bool(spec.get("is_handoff"))
        context_plan = spec.get("context_plan")
    else:
        rec = recommend_model(goal)
        shape = str(rec.get("model_shape") or "balanced")
        model = rec.get("model")
        is_handoff = bool(rec.get("is_handoff"))
        context_plan = rec.get("context_plan")
    ctx = cached_context(goal, is_handoff=is_handoff)
    learn = learned_principles(goal)
    # Apply half of the tesuji loop: fold measured provider economics into the plan.
    cost_evidence: dict[str, Any] = {}
    try:
        from mag.cost_learn import recent_cost_evidence
        cost_evidence = recent_cost_evidence(limit=5)
    except Exception:
        cost_evidence = {"source": "cost_learn", "providers": [], "n": 0}

    # Directive #4: consult ghost before long tasks (sanity check). Best-effort,
    # only for heavy/reasoning (long) tasks — never blocks the plan.
    ghost_sanity: dict[str, Any] | None = None
    if shape in ("heavy", "reasoning"):
        try:
            from mag.ghost_summon import summon as _gsummon
            g_ = _gsummon(goal, reason=False)
            stale = g_.get("stale_skip", {}).get("do_not_redesign") or []
            goal_l = goal.lower()
            ghost_sanity = {
                "ok": True,
                "schema": "ghost_sanity.v1",
                "stale_hits": [d for d in stale if any(tok and tok in goal_l for tok in d.lower().split())][:5],
                "coldest": [v.get("title") for v in g_.get("coldest_vertices", [])[:3]],
                "brief": (g_.get("brief") or "")[:1000],
            }
        except Exception as e:
            ghost_sanity = {"ok": False, "error": str(e)[:120]}

    return {
        "ok": True,
        "schema": SCHEMA,
        "goal": goal[:300],
        "agent_state": state or None,
        "model": model,
        "model_shape": shape,
        "thinking_level": spec.get("thinking_level"),
        "effort": spec.get("effort"),
        "skills": spec.get("skills") or [],
        "memory_context": spec.get("memory_context"),
        "is_handoff": is_handoff,
        "context_plan": context_plan,
        "context_sources": ctx.get("sources"),
        "context_chars": len(ctx.get("text") or ""),
        "learned": learn,
        "ghost_sanity": ghost_sanity,
        "cost_evidence": cost_evidence,
        "redrafted_prompt": redraft(goal, model_shape=shape),
        "context_excerpt": (ctx.get("text") or "")[:200],
    }


def drive(goal: str, *, spawn: bool = True, agent_state: str | None = None) -> dict[str, Any]:
    """Self-drive: build the plan (optionally state-aware), then spawn with the assembled context."""
    p = plan(goal, agent_state=agent_state)
    if not p.get("ok"):
        return p
    if not spawn:
        return p
    from mag.orchestrator import spawn_task

    full = "\n\n".join(
        [p["redrafted_prompt"]]
        + (["### CACHED CONTEXT (frozen prefix / maze)\n" + (p.get("context_excerpt") or "")] if p.get("context_excerpt") else [])
        + (["### LEARNED PRINCIPLES\n" + (p.get("learned") or {}).get("text", "")] if (p.get("learned") or {}).get("text") else [])
    )
    sp = spawn_task(full, provider="deepseek", model=p["model"], tag=f"self-drive-{p['model_shape']}")
    p["spawn"] = {"task_id": sp.get("task_id"), "ok": sp.get("ok"), "status": sp.get("status")}
    return p


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    ap = argparse.ArgumentParser(prog="self-drive", description="Self-driving ask: model + redraft + cached context + learned + spawn")
    ap.add_argument("--spawn", action="store_true", help="Actually spawn the task")
    ap.add_argument("--agent-state", default=None, help="Custom agent state: research-agent|janitor-agent|coding-agent|default")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("goal", nargs="*")
    args = ap.parse_args(argv)
    goal = " ".join(args.goal).strip()
    if not goal:
        print(json.dumps({"ok": False, "error": "no goal"}))
        return 0
    res = drive(goal, spawn=bool(args.spawn), agent_state=args.agent_state)
    print(json.dumps(res, indent=2, default=str)[:5000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
