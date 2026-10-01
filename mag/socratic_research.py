"""socratic_research — a 5-turn Socratic deep-research ask on a subject, structured by OUR OWN
lensing (lens_shader) + the 5 W's (tool_5ws), routed to the swarm for direction.

OPERATOR (2026-08-12): "socratic deep research asks 5 turns on this subject for direction" +
"self steal lensing and 5 ws". So this is not a naive Q&A — it frames the subject through our own
lensing (which lens is hot) + the 5 W's (who/what/when/where/why), then drives 5 Socratic turns each
routed to the swarm (swarm_surface.route_novel, dedupe + drain in-cluster) for direction.

SUBJECT (the standing question): how 1000 vibecoders' per-agent chat records (like ours) get
deduped (by invariant, content-anchored) and naturally distributed into everyone's shared standing
wave in the republic — sovereign per-operator records, one shared wave.

SELF-STEAL (reuse, not invent):
  * tool_5ws.ask()        -> frame the subject by WHO/WHAT/WHEN/WHERE/WHY (the 5-W frame).
  * lens_shader.program() -> which lens is hot on this subject (the steer / seam to research).
  * swarm_surface.route_novel() -> route each Socratic turn's direction question to the SWARM
    (dedupe by anchor + drain in-cluster). The swarm answers; we never run it locally.
  * content-anchored turn ids -> idempotent (a turn already routed doesn't re-route).

Schema: socratic_research.v1 · deterministic + $0 · reuse: tool_5ws, lens_shader, swarm_surface
"""
from __future__ import annotations

import json
import sys
from typing import Any

try:
    from config import ROOT
except Exception:
    from pathlib import Path as _P
    ROOT = _P(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "socratic_research.v1"
SURFACE = "socratic-research"

SUBJECT = (
    "How do 1000 vibecoders' per-agent chat records (like ours — gpt/cursor/grokbot/grok-desktop "
    "with versions) get DEDUPED (by invariant, content-anchored, not by raw chat) and NATURALLY "
    "DISTRIBUTED into everyone's shared standing wave in the republic — keeping each operator's raw "
    "record sovereign (never capture) while the reusable invariant warms the one wave everyone mounts?"
)

# The 5 Socratic turns. Each is a sharp direction question on the subject, ordered from the frame
# (what are we solving) to the mechanism (how dedupe + distribute) to the test (how do we know it
# works at 1000). Each routes to the swarm as a distinct anchor (dedupe + drain).
SOCRATIC_TURNS: list[str] = [
    "SOCRATIC TURN 1 (frame): What is the single hardest part of deduping 1000 vibecoders' per-agent "
    "records into shared invariants — is it the dedupe (same rule, 1000 spellings) or the sovereign "
    "boundary (what must NEVER leave a person's raw record)? Name the crux and the minimal first "
    "mechanism to break it.",
    "SOCRATIC TURN 2 (dedupe): Given each record is 'how the model spoke to ME', what is the right "
    "content anchor for dedupe so the SAME reusable invariant from 1000 people collapses to ONE knot "
    "while preserving per-person provenance (who contributed, never the raw words)? Design the "
    "dedupe-at-invariant contract.",
    "SOCRATIC TURN 3 (distribution): How does a folded invariant NATURALLY reach everyone's standing "
    "wave with no central hub and no broadcast — is the warm shared prefix (everyone mounts the same "
    "chain) sufficient, or is there a stigmergy/attractor mechanism that pulls each person's wave "
    "toward the shared one? Design the no-hub distribution.",
    "SOCRATIC TURN 4 (sovereignty + value): What makes a 1000-vibecoder republic WORTH it — how do we "
    "ensure the shared wave stays honest (grounded invariants, verifiable provenance, never-capture) "
    "as scale grows, and what is the highest-value thing to share first (what does one operator gain "
    "from 999 others' verified lessons)?",
    "SOCRATIC TURN 5 (test + direction): What is the minimal PROOF that this works at 1000 — a "
    "measure that dedupe collapsed the redundancy AND distribution actually warmed every wave? Give "
    "the concrete test + the next build step for direction.",
]


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def frame() -> dict[str, Any]:
    """Self-steal the 5 W's + lensing to frame the subject (what's hot, what's the steer)."""
    out: dict[str, Any] = {"ok": True, "schema": SCHEMA, "subject": SUBJECT}
    try:
        from mag import tool_5ws
        out["five_ws"] = tool_5ws.ask(SUBJECT)
    except Exception as e:
        out["five_ws_error"] = str(e)[:120]
    try:
        from mag import lens_shader
        prog = lens_shader.program()
        out["lens_frame"] = {"active_lens": prog.get("active_lens"),
                             "seams": prog.get("seams", [])[:5]}
    except Exception as e:
        out["lens_error"] = str(e)[:120]
    out["note"] = "subject framed through our own lensing + 5 W's (self-steal, deterministic + $0)"
    return out


def ask(*, enqueue: bool = True, limit: int = len(SOCRATIC_TURNS)) -> dict[str, Any]:
    """Run the 5-turn Socratic ask: route each turn's direction question to the swarm (dedupe by
    anchor + drain in-cluster). Deterministic + $0; the swarm answers for direction."""
    from mag import swarm_surface
    f = frame()
    routed, deduped = [], 0
    for t in SOCRATIC_TURNS[:limit]:
        r = swarm_surface.route_novel(t, surface=SURFACE, lens="socratic", domain="research")
        (routed if not r.get("deduped") else []).append({"turn": t[:80], "task_id": r.get("task_id")})
        if r.get("deduped"):
            deduped += 1
    return {"ok": True, "schema": SCHEMA, "subject": SUBJECT,
            "n_turns": len(SOCRATIC_TURNS[:limit]),
            "routed_to_swarm": len(routed), "already_deduped": deduped,
            "frame": f, "turns": SOCRATIC_TURNS[:limit],
            "contract": "frame (5-W + lensing) -> 5 Socratic turns -> swarm_surface.route_novel "
                        "(dedupe by anchor + drain in-cluster); the swarm returns direction; $0",
            "honesty": "turns routed to the swarm queue; answers land as filed research packs, "
                       "never fabricated here"}


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA, "subject": SUBJECT, "n_turns": len(SOCRATIC_TURNS),
            "surface": SURFACE,
            "note": "the 5-turn Socratic deep-research ask on the 1000-vibecoder dedupe + wave "
                    "distribution, framed by our lensing + 5 W's, routed to the swarm for direction"}


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="socratic-research")
    ap.add_argument("cmd", nargs="?", default="ask", choices=["frame", "ask", "status"])
    ap.add_argument("--no-enqueue", action="store_true")
    a = ap.parse_args(argv)
    import json as _json
    if a.cmd == "frame":
        out = frame()
    elif a.cmd == "status":
        out = status()
    else:
        out = ask(enqueue=not a.no_enqueue)
    print(_json.dumps(out, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
