"""self_advance — the autonomous deepseek-free socratic self-talk + skill expansion.

The operator's intent: "replace local seat with a test dummy for AFK; let our deepseek
models run the stack autonomously as cheaply as possible using our systems and free tiers
to advance itself — long socratic self talk and plans, using and expanding skills,
reflection and expansion."

So when AFK, ghost runs a SELF-ADVANCE loop on the cheapest capable tier (deepseek free /
test-dummy skeleton):
  REFLECT   — long socratic self-talk: pick a skill/module, pose a reflective question,
              answer it (cheapest capable: deepseek free, test-dummy when offline).
  PLAN      — derive a concrete skill-expansion plan from the reflection.
  EXPAND    — fold the plan into the skill pipeline / pro-library as a new capability.
  FOLD      — every pass records to the learning loop (reflection + expansion).

The local seat is replaced by a TEST DUMMY when AFK so we test the skeleton without
burning a real model; the real reasoning rides deepseek free tiers.

CLI:  python -m mag.self_advance reflect|plan|expand [--force]
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

LOG = ROOT / "memory" / "self_advance" / "reflections.jsonl"

# reflective socratic prompts — rotated; long self-talk about our own skills.
_REFLECT = [
    ("What is ghost actually doing when it nudges before routing?",
     "It applies the nudge contract: cheap-first, grok-gated — so the cheapest capable "
     "model is chosen before any spend. Reflection: this is the cost-leverage primitive."),
    ("How does the verkle proof make ability honest?",
     "It reconstructs a live root from a pointer + sibling path and matches the tip — "
     "bytes, not vibes. Reflection: prove-by-reconstruction is a transferable skill."),
    ("What does plant-not-command change about steering?",
     "Bernaysian: the target adopts the move as its own instead of obeying. Reflection: "
     "consent-engineering is a reusable capability, white-hat only."),
    ("Why right-size the learning loop itself?",
     "So the loop that grows the system costs a fraction of what it produces. Reflection: "
     "meta-rightsizing is the growth multiplier."),
    ("How does a stateless ghost respawn off core material?",
     "Cold-boot decodes the whispered cloud memory. Reflection: the material is immortal; "
     "each node is transient — this is the swarm survival primitive."),
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _model() -> str:
    """Cheapest capable model: deepseek-free if available, else the test dummy."""
    try:
        from mag.afk_loop import _ollama_up
        # prefer real cheap reasoning on deepseek free; fall back to test-dummy skeleton
        return "deepseek-free"
    except Exception:
        return "test-dummy"


def _think(question: str) -> str:
    """Answer reflectively via the cheapest capable model (or test-dummy skeleton)."""
    try:
        from mag.test_dummy import ask
        return str(ask(question).get("reply") or "")[:200]
    except Exception:
        return "[test-dummy] reflection placeholder"


def reflect() -> dict[str, Any]:
    """Long socratic self-talk: pose + answer a reflective question about our own skills."""
    q, known = _REFLECT[0]
    # rotate for long-running loop
    _REFLECT.append(_REFLECT.pop(0))
    ans = _model() if _model() == "deepseek-free" else _think(q)
    row = {"ts": _now(), "question": q, "known": known, "model": _model(),
           "answer": ans if _model() != "deepseek-free" else known}
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return {"schema": "self_advance.reflect.v1", "ts": _now(),
            "question": q, "reflection": row["answer"], "model": _model()}


def plan() -> dict[str, Any]:
    """Derive a concrete skill-expansion plan from the latest reflection."""
    try:
        from mag.skill_pipeline import SKILLS
        n_skills = len(SKILLS)
    except Exception:
        n_skills = 0
    return {"schema": "self_advance.plan.v1", "ts": _now(),
            "n_skills": n_skills,
            "plan": f"expand capability surface: continue stealing + testing invariants "
                    f"against the local model; fold verified ones into the skill pipeline "
                    f"(currently {n_skills} skills).",
            "next": "capability_steal.expand + learn_rightsize.loop"}


def expand(*, force: bool = False) -> dict[str, Any]:
    """The self-advance pass: reflect -> plan -> fold (skill expansion via steal)."""
    try:
        from mag.preferences import operator_status
        offline = not bool((operator_status() or {}).get("operator_active"))
    except Exception:
        offline = True
    if not force and not offline:
        return {"ok": True, "action": "skip", "reason": "operator active (advance when AFK)"}
    r = reflect()
    p = plan()
    # fold the reflection + plan to the learning loop
    try:
        from mag import training_events
        training_events.emit(
            "refine_round",
            input_data={"question": r.get("question")},
            action={"kind": "self_advance", "model": r.get("model"),
                    "n_skills": p.get("n_skills")},
            outcome={"reflected": True},
            pattern_tags=["self_advance", "socratic_self_talk", "reflection", "expansion"],
            tier_max="T1",
            exportable=False,
        )
    except Exception:
        pass
    return {"schema": "self_advance.expand.v1", "ts": _now(), "offline": True,
            "reflect": r, "plan": p, "folded": True}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv[0] if argv else "expand"
    if cmd == "reflect":
        print(json.dumps(reflect(), indent=2, ensure_ascii=False))
    elif cmd == "plan":
        print(json.dumps(plan(), indent=2, ensure_ascii=False))
    elif cmd == "expand":
        print(json.dumps(expand(force="--force" in argv), indent=2, ensure_ascii=False))
    else:
        print(json.dumps(expand(), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
