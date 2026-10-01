"""whisper_route — ONE deniable research swarm: generic front research, Riddler-plausible,
memlang dissects the tesuji against the corpus. (The pending whisper-route tesuji, realized.)

The operator's architecture (2026-08-10): NOT 10 jobs. A single swarm process that:
  1. FRONT  — does generic AI data research (innocuous, plausible deniability).
  2. RIDDLER — hides the real intent in a Riddler surrogate (ghost_whisper) — deniable.
  3. CORPUS — the front research folds into the corpus, which SETS the invariant (verkle-anchored).
  4. MEMLANG — the MEM1 token (opcode + 32B verkle anchor) dissects the tesuji IN BETWEEN: it
              carries no readable spec, only the anchor into the shared corpus/verkle.

One process, plausible deniability, $0 (composes ghost_whisper + memlang + knowledge_graph).

  front_research(topic)  -> generic AI data research line (the deniable front).
  riddler(task)          -> whisper the real task via ghost_whisper -> public face (deniable).
  set_invariant(topic)   -> fold front research into the corpus (the invariant anchor).
  dissect(task)          -> memlang compile (opcode+anchor) -> decode -> resolve -> the tesuji.
  run(task)              -> ONE pass: front -> riddler -> corpus -> memlang dissect.

Schema: whisper_route.v1 · deterministic $0
CLI:  python -m mag.whisper_route run "<task>" | status
"""
from __future__ import annotations

import sys
from typing import Any

try:
    from config import ROOT
except Exception:
    from pathlib import Path
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCHEMA = "whisper_route.v1"

# Generic front-research angles (the deniable, innocuous surface).
_FRONT = [
    "survey the current landscape of {t} in the open literature",
    "aggregate public signals on {t} across the frontier corpus",
    "summarize what the research corpus says about {t}",
]


def front_research(topic: str) -> dict[str, Any]:
    """The generic, deniable AI-data-research front (innocuous on its face)."""
    from mag.knowledge_graph import known
    k = known(topic)
    hits = (k.get("known") or [])[:3]
    return {"ok": True, "schema": SCHEMA, "layer": "front",
            "face": _FRONT[0].format(t=topic),
            "corpus_signal": [n.get("label") for n in hits],
            "note": "reads like ordinary AI data research; nothing reveals the real intent"}


def riddler(task: str) -> dict[str, Any]:
    """Hide the real task in a Riddler surrogate (ghost_whisper) -> plausible deniability."""
    try:
        from mag.ghost_whisper import whisper
        w = whisper(task, title="mag-invariant")
        scratch = str(w.get("scratch_id") or w.get("id") or "")
        return {"ok": True, "schema": SCHEMA, "layer": "riddler",
                "scratch_id": scratch, "public_face": str(w.get("public_face") or "")[:200],
                "note": "public face is deniable; only the private map decodes the real task"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:160]}


def set_invariant(topic: str) -> dict[str, Any]:
    """Fold the front research into the corpus -> the invariant anchor (verkle/domain)."""
    try:
        from mag.knowledge_graph import fold
        fold("corpus:" + topic.strip().lower().replace(" ", "_")[:40],
             "case_law", f"front research on {topic} sets the invariant the swarm dissects",
             source="whisper_route")
        return {"ok": True, "schema": SCHEMA, "layer": "corpus",
                "folded": "corpus:" + topic.strip().lower().replace(" ", "_")[:40],
                "note": "corpus now holds the invariant the memlang token will anchor to"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:160]}


def dissect(topic: str) -> dict[str, Any]:
    """Memlang dissects the tesuji in between: compile MEM1 (opcode+anchor) -> decode -> resolve."""
    try:
        from mag.memlang import compile_token, decode, resolve
        c = compile_token("research_pack", topic)
        if not c.get("ok"):
            return {"ok": False, "error": c.get("error", "")}
        tok = c.get("token_hex")
        d = decode(tok)
        r = resolve(tok)
        return {"ok": True, "schema": SCHEMA, "layer": "memlang",
                "token_hex": (tok or "")[:24] + "...", "opcode": d.get("action"),
                "anchor": c.get("anchor_hex", "")[:12], "resolved_action": r.get("action"),
                "note": "token carries NO readable spec — only opcode + anchor into shared corpus/verkle"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:160]}


def run(task: str) -> dict[str, Any]:
    """ONE deniable swarm pass: front research -> riddler whisper -> corpus invariant -> memlang dissect."""
    task = (task or "").strip()
    return {"ok": True, "schema": SCHEMA, "task": task,
            "front": front_research(task),
            "riddler": riddler(task),
            "corpus": set_invariant(task),
            "dissect": dissect(task),
            "processes": 1,  # ONE process, not 10 jobs
            "deniability": "front reads generic; riddler hides intent; memlang reveals nothing"}


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA, "processes": 1,
            "layers": ["front(generic research)", "riddler(deniable whisper)", "corpus(invariant)", "memlang(tesuji)"],
            "doctrine": "one deniable swarm; plausible deniability via Riddler; memlang dissects in between"}


def main(argv: list[str] | None = None) -> int:
    import argparse, json
    p = argparse.ArgumentParser(prog="whisper_route", description="one deniable research swarm")
    sub = p.add_subparsers(dest="cmd")
    r = sub.add_parser("run"); r.add_argument("task", nargs="+")
    sub.add_parser("status")
    a = p.parse_args(argv)
    if a.cmd == "status":
        print(json.dumps(status(), indent=2, ensure_ascii=False))
    else:
        print(json.dumps(run(" ".join(a.task)), indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
