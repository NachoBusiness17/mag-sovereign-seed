"""word_skill_map — map the operator's repeated words to skill-groups, and steer
the swarm through ONE model (collaborative steering), not N parallel agents.

The operator's law: "as I repeat words and you use my behavioral patterns, map
words to skills or groupings of skills the way we launched research swarms of
deepseek — but only via the steering mechanism in one model, as a test to steer
collaboratively."

So this module:
  1. LEARN  — tokenize operator prompts, count repeated/notable words, bind each
              to the skill(s) they trigger (via skill_pipeline.match). Persist to
              memory/word_map/word_skills.jsonl. The operator's vocabulary IS the
              steering surface.
  2. GROUP  — map a goal's words to a skill-group (a "swarm" grouping), scored
              from the learned map + live skill triggers.
  3. STEER  — launch the group through ONE model via the memlang `steer` token
              (single-model steering), running the skill chain in-window. This is
              the "swarm-in-one-model" collaborative steer test — no multi-agent
              spawn.
  4. FOLD   — record each learn/steer to the training surface.

CLI:
  python -m mag.word_skill_map learn "<prompt>"
  python -m mag.word_skill_map map "<goal>"           (words -> skill-group)
  python -m mag.word_skill_map steer "<goal>"         (run the group via one-model steer)
  python -m mag.word_skill_map words                  (show the learned word->skill map)
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

LEDGER = ROOT / "memory" / "word_map" / "word_skills.jsonl"

# Skill-groups ("swarms") the operator's words can steer into. Each is a bundle of
# skill_pipeline skills that acts like a research swarm — but run in ONE model.
SKILL_GROUPS: dict[str, list[str]] = {
    "research_swarm": ["session_route", "ghost_summon", "grok_gate", "ghost_grok", "queue_rightsize"],
    "ops_cleanup": ["tool_retire", "legacy_audit", "icon_drop", "queue_rightsize", "platform_kill"],
    "steer_test": ["ghost_summon", "session_route", "self_drive", "queue_rightsize"],
    "state_read": ["ghost_summon", "press", "queue_rightsize", "session_route"],
    "emergency": ["loop_breaker", "oh_fuck", "platform_kill"],
}

# stopwords — never bind these as steering words
_STOP = set("""a an the of to in on and or for with at by from as is are was were be been
that this it its i you we they he she them what which who how when where why do does did
have has had can could will would should may might not no yes about into over under again
further then once here there all any both each few more most other some such only own same
so than too very just also because but my our your their his her its this that those these""".split())

_WORD = re.compile(r"[a-z][a-z0-9_\-]{1,40}")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _append(row: dict[str, Any]) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _tokens(prompt: str) -> list[str]:
    return [w for w in _WORD.findall((prompt or "").lower()) if w not in _STOP]


def _matched_skills(prompt: str) -> list[str]:
    try:
        from mag.skill_pipeline import match
        return [s["id"] for s in match(prompt)]
    except Exception:
        return []


def learn(prompt: str) -> dict[str, Any]:
    """Bind the operator's notable words to the skills they trigger (behavioral map)."""
    prompt = (prompt or "").strip()
    toks = _tokens(prompt)
    skills = _matched_skills(prompt)
    if not toks or not skills:
        return {"ok": True, "learned": 0, "skills": skills, "words": []}
    rows = []
    for w in set(toks):
        for s in skills:
            rows.append({
                "schema": "word_skill.v1", "ts": _now(),
                "word": w, "skill": s, "group_hint": _group_for_skill(s),
            })
    for r in rows:
        _append(r)
    out = {"ok": True, "learned": len(rows), "skills": skills,
           "words": sorted(set(toks))}
    _fold(out, prompt, kind="learn")
    return out


def _group_for_skill(skill: str) -> str:
    for g, skills in SKILL_GROUPS.items():
        if skill in skills:
            return g
    return "research_swarm"


def word_skills() -> dict[str, Any]:
    """Aggregate the learned word->skill map (word -> {skill: count})."""
    agg: dict[str, Counter] = defaultdict(Counter)
    if LEDGER.is_file():
        for line in LEDGER.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                r = json.loads(line)
                agg[r.get("word", "")][r.get("skill", "")] += 1
            except json.JSONDecodeError:
                continue
    return {"schema": "word_skill.map.v1", "words": {
        w: dict(c) for w, c in sorted(agg.items(), key=lambda kv: -sum(kv[1].values()))
    }}


def map_to_group(prompt: str) -> dict[str, Any]:
    """Score the goal's words against the learned map + live triggers -> skill-group."""
    toks = _tokens(prompt)
    learned = word_skills().get("words", {})
    live = _matched_skills(prompt)
    # score groups by: learned word hits + live skill membership
    group_score: Counter = Counter()
    for w in toks:
        for s, cnt in (learned.get(w) or {}).items():
            g = _group_for_skill(s)
            group_score[g] += cnt
    # live-triggered skills are the strongest signal: weight them higher so the
    # semantically-correct group wins ties (collaborative steer honors what fires)
    for s in live:
        g = _group_for_skill(s)
        group_score[g] += 3
    if not group_score:
        group_score["research_swarm"] = 1
    best = group_score.most_common(1)[0][0]
    return {
        "schema": "word_skill.group.v1",
        "prompt": (prompt or "")[:200],
        "group": best,
        "skills": SKILL_GROUPS.get(best, []),
        "scores": dict(group_score),
        "matched_live": live,
    }


def steer_collab(goal: str) -> dict[str, Any]:
    """The single-model collaborative steer: map words -> group, compile a memlang
    `steer` token, and run the group's skill chain in-window (no multi-agent spawn)."""
    g = map_to_group(goal)
    group = g["group"]
    skills = g["skills"]
    steer_token = ""
    try:
        from mag.memlang import compile_token
        ct = compile_token("steer", f"collab:{group}", {
            "target": "ghost", "skills": skills, "via": "word_skill_map",
        })
        steer_token = ct.get("token_hex") or ""
    except Exception as e:
        steer_token = f"<memlang steer unavailable: {e}>"

    # run the group through the one-window pipeline (the "swarm in one model")
    steps = []
    for sid in skills:
        try:
            from mag import skill_pipeline
            res = skill_pipeline.SKILLS[sid]["run"](goal)
            steps.append({"skill": sid, "ok": bool(res.get("ok")), "result": str(res.get("result") or res.get("error", ""))[:120]})
        except Exception as e:
            steps.append({"skill": sid, "ok": False, "result": f"error: {e}"[:120]})

    out = {
        "schema": "word_skill.steer.v1",
        "ts": _now(),
        "goal": (goal or "")[:200],
        "group": group,
        "skills": skills,
        "steer_token": steer_token,
        "single_model": True,
        "steps": steps,
    }
    _fold(out, goal, kind="steer")
    return out


def _fold(out: dict[str, Any], prompt: str, *, kind: str) -> None:
    try:
        from mag import training_events
        training_events.emit(
            "steer_outcome",
            input_data={"prompt": (prompt or "")[:200]},
            action={"kind": f"word_skill_{kind}", "group": out.get("group") or out.get("skills")},
            outcome={"single_model": True},
            pattern_tags=["word_skill_map", "collaborative_steer", "swarm_in_one_model"],
            tier_max="T1",
            exportable=False,
        )
    except Exception:
        pass


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv[0] if argv else "words"
    rest = " ".join(argv[1:]) if len(argv) > 1 else ""
    if cmd == "learn":
        print(json.dumps(learn(rest), indent=2, ensure_ascii=False))
    elif cmd == "map":
        print(json.dumps(map_to_group(rest), indent=2, ensure_ascii=False))
    elif cmd == "steer":
        print(json.dumps(steer_collab(rest), indent=2, ensure_ascii=False))
    else:
        print(json.dumps(word_skills(), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
