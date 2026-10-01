"""Session-maze handoff — the memory-framework test for deep-model drop-in.

The operator runs on a LOW tier (e.g. deepseek-v4-flash) and wants to hand the
run to a DEEPER model (e.g. deepseek-v4-pro) WITHOUT re-pasting the whole
conversation (which re-pays the context tax: new tokens, breaks the frozen
prefix, costs more, risks corrupting the run).

This module assembles a COMPACT, byte-stable "maze + instructions" bundle from
the framework's own state (CURRENT.md, active research pack, module, ledger
counts, supervisor status) — the map that IS the territory. The deeper model
reads the maze file and continues, instead of being re-taught the whole thread.

  - assemble()   -> read live state -> render maze (deterministic, no LLM)
  - persist()    -> write memory/graph/session_maze.json + state/HANDOFF.md
  - deep_handoff() -> assemble + spawn the goal on the deeper provider/model
                     (spawn_task(provider=deepseek, model=deepseek-v4-pro))

The test: does a fresh deeper model, given ONLY the maze, continue the run at
equivalent quality without the re-teach? (Same shape as the frozen-prefix /
context-tax doctrine.)

CLI:  main.py deep-handoff --goal "<continue this>" [--model deepseek-v4-pro]
REST: POST /api/v1/handoff/deep  {goal, model}
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

MAZE_PATH = ROOT / "memory" / "graph" / "session_maze.json"
HANDOFF_PATH = ROOT / "state" / "HANDOFF.md"

DEFAULT_DEEP_MODEL = "deepseek-v4-pro"
DEFAULT_DEEP_PROVIDER = "deepseek"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_first(path: Path, maxlen: int = 0) -> str:
    try:
        t = path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return ""
    return t[:maxlen] if maxlen else t


def _read_current() -> dict[str, Any]:
    """Authoritative task contract from state/CURRENT.md."""
    out: dict[str, Any] = {"present": False}
    p = ROOT / "state" / "CURRENT.md"
    if not p.is_file():
        return out
    out["present"] = True
    out["raw"] = _read_first(p, 4000)
    return out


def _latest_research_pack() -> str:
    d = ROOT / "memory" / "research_packs"
    if not d.is_dir():
        return ""
    md = sorted(d.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    return md[0].name if md else ""


def _active_module() -> str:
    for cand in ("campaigns/quiet_forge/module.json",):
        p = ROOT / cand
        if p.is_file():
            return cand
    return ""


def _ledger_counts() -> dict[str, int]:
    out = {}
    try:
        from mag.skill_ledger import progress

        pr = progress()
        out["decisions"] = pr.get("decisions") if isinstance(pr, dict) else None
    except Exception:
        pass
    return out


def assemble() -> dict[str, Any]:
    """Render the session maze: the map that IS the territory for the next model."""
    current = _read_current()
    maze: dict[str, Any] = {
        "schema": "session_maze.v1",
        "ts": _now(),
        "instructions": {
            "read": "You are a deeper-tier model continuing a sovereign-agent run. "
                    "Read ONLY this maze + the referenced files. Do NOT re-derive "
                    "what is already frozen here. Continue the stated goal.",
            "maze": "the accumulated state (frozen)",
            "tail": "the goal line + current step (thin, evolves)",
        },
        "current": current,
        "active_module": _active_module(),
        "latest_research_pack": _latest_research_pack(),
        "ledger": _ledger_counts(),
        "supervisor": {},
    }
    try:
        from mag.process_supervisor import status as ps_status

        st = ps_status()
        maze["supervisor"] = {"running": st.get("running"), "loops": st.get("loops")}
    except Exception:
        pass
    return maze


def _render_text(maze: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# HANDOFF — Session Maze (map is the territory)")
    lines.append("")
    lines.append("Read this maze + referenced files. Continue the goal without re-teaching.")
    lines.append("")
    lines.append(f"- Maze schema: {maze.get('schema')}")
    lines.append(f"- Assembled: {maze.get('ts')}")
    lines.append("")
    lines.append("## Current contract")
    cur = maze.get("current", {})
    if cur.get("present"):
        lines.append(cur.get("raw", ""))
    else:
        lines.append("(no state/CURRENT.md — see goal below)")
    lines.append("")
    if maze.get("active_module"):
        lines.append(f"## Active module\n{maze['active_module']}")
        lines.append("")
    if maze.get("latest_research_pack"):
        lines.append(f"## Latest research pack\nmemory/research_packs/{maze['latest_research_pack']}")
        lines.append("")
    led = maze.get("ledger", {})
    if led:
        lines.append(f"## Ledger: {json.dumps(led)}")
        lines.append("")
    sup = maze.get("supervisor", {})
    if sup.get("running"):
        lines.append(f"## Supervisor running: {sup.get('running')}")
        lines.append("")
    return "\n".join(lines)


def persist() -> dict[str, Any]:
    maze = assemble()
    MAZE_PATH.parent.mkdir(parents=True, exist_ok=True)
    MAZE_PATH.write_text(json.dumps(maze, indent=2, ensure_ascii=False), encoding="utf-8")
    HANDOFF_PATH.parent.mkdir(parents=True, exist_ok=True)
    HANDOFF_PATH.write_text(_render_text(maze), encoding="utf-8")
    return {"ok": True, "maze": str(MAZE_PATH), "handoff": str(HANDOFF_PATH), "ts": maze["ts"]}


def deep_handoff(
    goal: str,
    *,
    model: str = DEFAULT_DEEP_MODEL,
    provider: str = DEFAULT_DEEP_PROVIDER,
    timeout: int = 900,
) -> dict[str, Any]:
    """Assemble the maze, then spawn the run on the deeper model.

    The deeper model reads state/HANDOFF.md (the frozen maze) instead of a
    re-pasted conversation — the memory-framework test.
    """
    goal = (goal or "").strip()
    if not goal:
        return {"ok": False, "error": "goal required"}
    persisted = persist()
    dispatch_goal = (
        f"Deep-tier handoff (memory-framework test). Read state/HANDOFF.md — the "
        f"frozen session maze (map is the territory) — and continue this goal "
        f"without re-teaching: {goal}"
    )
    from mag.orchestrator import spawn_task

    spawn = spawn_task(dispatch_goal, provider=provider, model=model, timeout=timeout,
                       tag=f"deep-handoff-{model}")
    return {
        "ok": bool(spawn.get("ok")),
        "model": model,
        "provider": provider,
        "maze": str(MAZE_PATH),
        "handoff": str(HANDOFF_PATH),
        "spawn": spawn,
    }


# Byte-stable escalation preamble — the CACHE-HIT surface. Keep this IDENTICAL across calls so
# DeepSeek's prefix cache hits (~$0.0036/M hit vs ~$0.435/M miss, per cache_map). Only the thin
# volatile question (the user tail) varies. Same doctrine as game_dm_llm.LORE / invariant.py.
_ESCALATION_PREAMBLE = (
    "You are a senior debugging partner for a sovereign-agent architecture. "
    "You are given the frozen session maze (the accumulated, byte-stable state) plus ONE thin "
    "question. Read the maze for context, then answer ONLY the question. Be specific and grounded; "
    "cite suspect lines; prefer the fix that respects a headless, rightsized, never-wedge system. "
    "The maze is the map; the question is the delta."
)


def escalate_cached(
    question: str,
    *,
    model: str = DEFAULT_DEEP_MODEL,
    provider: str = DEFAULT_DEEP_PROVIDER,
    tier: str = "T2",
    max_tokens: int = 1600,
) -> dict[str, Any]:
    """CACHE-AWARE direct escalation to a deeper model (2026-08-16, operator's cost question).

    The problem it solves: an ad-hoc `chat_provider(model=deepseek-v4-pro)` with a fresh brief each
    time pays a FULL CACHE-MISS on every call (~$0.435/M). This rides the BYTE-STABLE maze prefix
    (cache-HIT ~$0.0036/M) + a THIN question tail, so repeated escalations hit the cache.

    Structure (the doctrine: separate stable prefix from volatile tail):
      system = the fixed _ESCALATION_PREAMBLE (byte-stable -> cache-hit surface)
      user   = the maze text (byte-stable, from persist()) + "\nQUESTION:\n" + question (thin tail)
    Only the question bytes change between calls, so the leading prefix stays cached.

    Direct call (not the queue) — usable even when the swarm drain is down/broken. Deterministic
    coordinator; the deeper model is the real cost.
    """
    question = (question or "").strip()
    if not question:
        return {"ok": False, "error": "question required"}
    # byte-stable maze text (persist() renders state/HANDOFF.md deterministically)
    try:
        p = persist()
        hp = p.get("handoff") or ""
        from pathlib import Path
        maze_text = Path(hp).read_text(encoding="utf-8", errors="replace") if hp and Path(hp).is_file() else ""
    except Exception as e:
        maze_text = ""
        p = {"error": str(e)[:120]}
    user = f"{maze_text}\n\nQUESTION:\n{question}" if maze_text else question
    try:
        from models.providers import chat_provider
        r = chat_provider(provider, _ESCALATION_PREAMBLE, user, model=model, tier=tier,
                          max_tokens=max_tokens)
        return {
            "ok": bool(r.get("ok")),
            "model": model,
            "provider": provider,
            "text": r.get("text") or r.get("content") or "",
            "error": r.get("error"),
            "usage": r.get("usage"),
            "maze": p,
            "cache_aware": True,
            "note": "byte-stable maze prefix (cache-hit) + thin question tail; not a fresh miss",
        }
    except Exception as e:
        return {"ok": False, "error": str(e)[:200], "maze": p}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = (argv[0] if argv else "status").lower()
    if cmd in ("assemble", "persist"):
        print(json.dumps(persist(), indent=2, ensure_ascii=False))
        return 0
    if cmd in ("deep", "handoff"):
        goal = argv[1] if len(argv) > 1 else ""
        model = argv[2] if len(argv) > 2 else DEFAULT_DEEP_MODEL
        print(json.dumps(deep_handoff(goal, model=model), indent=2, ensure_ascii=False, default=str))
    if cmd in ("escalate", "escalate-cached"):
        question = argv[1] if len(argv) > 1 else ""
        model = argv[2] if len(argv) > 2 else DEFAULT_DEEP_MODEL
        print(json.dumps(escalate_cached(question, model=model), indent=2, ensure_ascii=False, default=str))
        return 0
    print(json.dumps(assemble(), indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
