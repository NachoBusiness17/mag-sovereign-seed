"""ghost_talk — TALK TO GHOST DIRECTLY. Ghost is the surface of interaction.

The operator shouldn't hunt for the right dashboard card or command. Ghost IS the
interface: you type a natural-language prompt, ghost senses context, routes it through
the whole machine (skill_pipeline + scrum + press + loop + tokens), and replies concisely.

No "where do I look" — just talk to ghost.

CLI:  python -m mag.ghost_talk "<prompt>"          (one-shot)
      python -m mag.ghost_talk                      (interactive REPL)
Schema: ghost_talk.v1
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

SCHEMA = "ghost_talk.v1"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _context_line() -> str:
    """A one-line sense of where things stand (ghost's current read)."""
    try:
        from mag.ghost import sense
        s = sense()
        return (f"inbox_pending={s.get('inbox_pending',0)} "
                f"frustration={s.get('frustration_total',0)} "
                f"verkle_stale={s.get('verkle_tip_stale')} "
                f"training_rows={s.get('training_rows',0)}")
    except Exception:
        return "context unavailable"


def reply(prompt: str) -> dict[str, Any]:
    """Ghost replies to a natural-language prompt by routing it through the machine.

    GHOST = the process: every ask is NUDGED (ghost_nudge contract), then routed through
    the skill pipeline (one-window surface). The agent window is ghost's front-end.
    """
    prompt = (prompt or "").strip()
    out: dict[str, Any] = {"schema": SCHEMA, "ts": _now(), "ok": True,
                           "you": prompt, "source": "ghost"}

    # NUDGE: apply the nudge contract (how ghost steers models) before routing.
    try:
        from mag.ghost_nudge import nudge as nudge_ask
        n = nudge_ask(prompt)
        out["nudged"] = True
        out["nudge_route"] = n.get("route")
        out["nudge_skills"] = n.get("skills")
        working = n.get("nudged_prompt") or prompt
    except Exception:
        working = prompt
        out["nudged"] = False

    # ghost senses where things stand
    out["context"] = _context_line()

    # route the prompt through the developed skills (one-window surface)
    try:
        from mag.skill_pipeline import run as skills_run
        sr = skills_run(prompt)
        out["skills"] = {"chain": sr.get("chain"), "steps": [
            {"skill": st.get("skill"), "ok": st.get("ok"),
             "result": str(st.get("result"))[:120]} for st in sr.get("steps", [])]}
    except Exception as e:
        out["skills_error"] = str(e)[:120]

    # SPOOKY: the long-standing per-prompt test of ghost's abilities to affect
    # outcomes. Always shown — which autonomous levers ghost is pulling for this ask.
    try:
        from mag.ghost_spooky import probe as spooky_probe
        out["spooky"] = spooky_probe(prompt)
    except Exception as e:
        out["spooky_error"] = str(e)[:120]

    # if the prompt is about "what's going on / status", fold in the control harness
    lp = prompt.lower()
    if any(w in lp for w in ("status", "what's going", "whats going", "summary",
                              "where are we", "pressing", "control", "overview")):
        try:
            from mag.ghost_control import control
            out["control"] = control()
        except Exception as e:
            out["control_error"] = str(e)[:120]

    # ghost's concise reply to the human
    reply_lines = [f"[ghost] Routed '{prompt[:80]}' through {len(out.get('skills',{}).get('chain',[]))} skill(s)."]
    if out.get("skills", {}).get("steps"):
        ok = sum(1 for s in out["skills"]["steps"] if s["ok"])
        reply_lines.append(f"  {ok}/{len(out['skills']['steps'])} skills completed.")
    if out.get("spooky", {}).get("line"):
        reply_lines.append(f"  👻 spooky: {out['spooky']['line']}")
    if out.get("control", {}).get("pressing"):
        reply_lines.append(f"  Pressing: {out['control']['pressing'].get('title')}")
    out["reply"] = "\n".join(reply_lines)
    return out


def repl() -> None:
    print("Ghost surface — talk to me. (type /quit to exit)")
    import sys as _s
    while True:
        try:
            p = input("ghost> ")
        except (EOFError, KeyboardInterrupt):
            print()
            return
        p = p.strip()
        if not p:
            continue
        if p.lower() in ("/quit", "/exit", "quit", "exit"):
            return
        try:
            print(reply(p).get("reply", ""))
        except Exception as e:
            print(f"[ghost] error: {e}")


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    prompt = " ".join(argv) if argv else ""
    if prompt:
        print(json.dumps(reply(prompt), indent=2, ensure_ascii=False, default=str))
    else:
        repl()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
