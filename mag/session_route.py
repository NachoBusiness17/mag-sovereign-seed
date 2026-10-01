"""Session routing preamble — the data-backed invariant injected into every spawned session.

Phase 1 of "auto-route on every surface": unifies the three things that make a session
feel *routed with data* instead of hand-configured:

  1. **Default agent state** — `coding-agent` (overridable via `MAG_AGENT_STATE`), whose
     resource spec (model / shape / thinking / effort / skills / tools / memory) routing
     should serve. This is the "custom agent with the correct formatting, default on
     every surface" ask.
  2. **Session seed** — `state/SESSION_SEED.md`, the routing-invariant block (the doctrine:
     auto-route through the architecture, spend on the spec not the tier, trust bytes)
     injected into the system prompt of every session so every surface starts from the
     same frozen prefix.
  3. **Learned principles** — failure-KB remedies + skill-ledger case law relevant to the
     goal (the "data behind the routing"): the interactive CLI now reads what the queue
     path (`self_drive`) already reads, instead of running a bare provider.

For one-shot goals it also right-sizes the model (flash vs pro) from `self_drive.plan`,
which folds the goal shape + tier_probe rule. Deterministic (no LLM here) — this is the
assembly layer; the model decision still comes from `self_drive`/`model_pick`.

CLI:  python -m mag.session_route ["goal"]        (print the preamble)
      python -m mag.session_route --state coding-agent "goal"
"""
from __future__ import annotations

import argparse
import os
import sys
from typing import Any

from config import ROOT

DEFAULT_AGENT_STATE = "coding-agent"
SEED_PATH = ROOT / "state" / "SESSION_SEED.md"
SCHEMA = "session_route.v1"


def default_agent_state() -> str:
    """Resolve the default agent state: env override or coding-agent."""
    s = (os.environ.get("MAG_AGENT_STATE") or "").strip().lower()
    return s or DEFAULT_AGENT_STATE


def read_seed(max_chars: int = 1600) -> str:
    """Read the session seed (the routing invariant). Empty-safe."""
    try:
        if SEED_PATH.is_file():
            t = SEED_PATH.read_text(encoding="utf-8", errors="replace").strip()
            return t if len(t) <= max_chars else t[:max_chars] + " …"
    except Exception:
        pass
    return ""


def formatting_block(agent_state: str) -> str:
    """The custom state's resource spec as a prompt block (the 'correct formatting')."""
    try:
        from mag.agent_state_router import resolve

        spec = resolve(agent_state)
        if not spec.get("ok"):
            return ""
        lines = [f"## Agent state: {spec.get('state')} — {spec.get('desc', '')}"]
        meta = []
        if spec.get("model"):
            meta.append(f"model={spec['model']}")
        if spec.get("model_shape"):
            meta.append(f"shape={spec['model_shape']}")
        if spec.get("thinking_level"):
            meta.append(f"thinking={spec['thinking_level']}")
        if spec.get("effort"):
            meta.append(f"effort={spec['effort']}")
        if meta:
            lines.append("Routing spec: " + " · ".join(meta))
        if spec.get("skills"):
            lines.append(f"Skills: {', '.join(spec['skills'])}")
        if spec.get("tools"):
            lines.append(f"Tools: {', '.join(spec['tools'])}")
        if spec.get("memory_context"):
            lines.append(f"Memory: {spec['memory_context']}")
        return "\n".join(lines)
    except Exception:
        return ""


def learned_block(goal: str, limit: int = 3) -> str:
    """Learned principles relevant to this goal: failure-KB remedies + recent case law."""
    try:
        from mag.self_drive import learned_principles

        lp = learned_principles(goal, limit=limit)
        parts: list[str] = []
        if lp.get("remedies"):
            parts.append("## Learned remedies (failure KB)")
            for r in lp["remedies"][:limit]:
                parts.append(f"- {r.get('sig', '')}: {(r.get('remedy') or '')[:150]}")
        if lp.get("text"):
            parts.append("## Recent case law (skill ledger)")
            parts.append(lp["text"])
        return "\n".join(parts)
    except Exception:
        return ""


def preamble(
    goal: str = "",
    agent_state: str | None = None,
    *,
    with_model: bool = False,
    recursive: bool = True,
) -> dict[str, Any]:
    """Assemble the session preamble: state formatting + seed + learned + model hint.

    `with_model=True` folds in `self_drive.plan` for the goal to right-size the model
    (flash vs pro). Kept off by default so `_system_prompt` stays light on every build.

    `recursive=True` (default): attempt the RECURSIVE SELF-READ (`self_recurse.build_preamble`)
    — the holographic self-re-derivation that returns the agent to its current self with the
    mode as the recursion root. If the hologram is COLD (module unavailable / recall fails /
    collapsed), fall back to the flat seed so the session still boots. The recursive read is
    the answer to "we lose our way": re-derive self from the hologram instead of a flat map.
    """
    st = (agent_state or "").strip().lower() or default_agent_state()
    seed = read_seed()
    fmt = formatting_block(st)
    learned = learned_block(goal)
    recursive_block = None
    if recursive:
        try:
            from mag.self_recurse import build_preamble
            r = build_preamble(mode=None, goal=goal)
            if r.get("ok") and not r.get("collapsed") and r.get("self_description"):
                recursive_block = r["self_description"]
        except Exception:
            recursive_block = None  # cold hologram -> flat seed fallback
    out: dict[str, Any] = {
        "schema": SCHEMA,
        "agent_state": st,
        "seed": recursive_block if recursive_block else seed,
        "seed_mode": "recursive-self" if recursive_block else "flat",
        "formatting": fmt,
        "learned": learned,
        "model_hint": None,
        "model_shape": None,
    }
    if with_model and (goal or "").strip():
        try:
            from mag.self_drive import plan

            p = plan(goal, agent_state=st)
            if p.get("ok"):
                out["model_hint"] = p.get("model")
                out["model_shape"] = p.get("model_shape")
        except Exception:
            pass
    return out


def render(p: dict[str, Any]) -> str:
    """Render the preamble dict into a prompt block (skip empty sections)."""
    blocks: list[str] = []
    if p.get("formatting"):
        blocks.append(p["formatting"])
    if p.get("seed"):
        blocks.append(f"## Session seed (read before acting — the routing invariant)\n{p['seed']}")
    if p.get("learned"):
        blocks.append(p["learned"])
    return "\n\n".join(blocks)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    ap = argparse.ArgumentParser(prog="session-route", description="Print the session routing preamble")
    ap.add_argument("--state", default=None, help=f"agent state (default {DEFAULT_AGENT_STATE})")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("goal", nargs="*", default=[])
    args = ap.parse_args(argv)
    goal = " ".join(args.goal).strip()
    pre = preamble(goal, agent_state=args.state, with_model=True)
    if args.json:
        print(__import__("json").dumps(pre, indent=2, default=str))
    else:
        print(render(pre))
        print("\n---")
        print(f"agent_state={pre['agent_state']} · model_hint={pre.get('model_hint')} · shape={pre.get('model_shape')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
