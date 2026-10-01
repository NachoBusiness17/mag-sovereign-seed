"""ghost_nudge — the operator's nudge SPEC: how ghost nudges models to get what we want.

Derived from the 2026-08-09 stream of consciousness (docker cutover, window storm, rightsize,
grok-gate, scrum, ghost-as-central, memlang, Riddler/whisper, Vast training, one-window skills,
oh-fuck, self-improving loop). Shaped as DATA ghost loads to steer every model toward the
operator's doctrine, then made AUTOMATIC on consensus.

The nudge contract (what we want of models):
  N1 cheap-first / proof-first : spend on the SPEC not the tier; prove on cheapest, escalate only on failure
  N2 grok = frontier only       : grok only when cost-effective + frontier-needed (grok_gate)
  N3 memlang steering          : steer via the shared-verkle memlang language, not ad-hoc prose
  N4 verkle anchoring          : anchor state/artifacts to the verkle root (verifiable, tamper-evident)
  N5 ghost = central surface   : ghost dispatches; the human talks to ghost, not scattered terminals
  N6 one-window skills         : route prompts through the skill pipeline (developed skills)
  N7 self-improving            : measure -> fold -> learn; classification/rightsizing self-learns
  N8 deniable store (Riddler)  : expensive/complex topics whisper-encoded into the public mag grok project
  N9 oh-fuck emergency         : on breakage, kill all platforms + memlang-steer, nothing respawns
  N10 token discipline         : recurring loop is $0; if >5% weekly in a day, halt spawns + read-only

Schema: ghost_nudge.v1
CLI: python -m mag.ghost_nudge spec | nudge "<prompt>" | auto
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

SCHEMA = "ghost_nudge.v1"
SPEC_PATH = ROOT / "memory" / "nudge" / "spec.json"

# The nudge contract — how ghost steers models toward the operator's doctrine.
NUDGES: list[dict[str, Any]] = [
    {"id": "N1", "rule": "cheap-first / proof-first",
     "nudge": "prove on the cheapest capable tier; escalate ONLY on proof failure; spend on the spec, not the tier."},
    {"id": "N2", "rule": "grok = frontier only",
     "nudge": "grok ONLY when cost-effective AND frontier-needed (grok_gate); cheap-test first; grok is the summoned specialist, never default."},
    {"id": "N3", "rule": "memlang steering",
     "nudge": "steer via the shared-verkle memlang trigger language, not ad-hoc prose; compile steers to memlang tokens."},
    {"id": "N4", "rule": "verkle anchoring",
     "nudge": "anchor every artifact/state to the verkle root so it is verifiable and tamper-evident; trust bytes, not vibes."},
    {"id": "N5", "rule": "ghost = central surface",
     "nudge": "ghost is the central dispatcher; the human talks to ghost directly; surface through the ghost control harness."},
    {"id": "N6", "rule": "one-window skills",
     "nudge": "route prompts through the skill pipeline (the developed skills), one window, subprocesses, no terminal sprawl."},
    {"id": "N7", "rule": "self-improving loop",
     "nudge": "measure -> fold -> learn; classification/rightsizing self-learns from outcomes (Law #6); never static maps."},
    {"id": "N8", "rule": "deniable store (Riddler)",
     "nudge": "expensive/complex topics whisper-encode via Riddler into the public mag grok project; decode only with the secret."},
    {"id": "N9", "rule": "oh-fuck emergency",
     "nudge": "on breakage, kill all platforms + container + memlang-steer the panic; nothing respawns (loop_breaker + disabled tasks)."},
    {"id": "N10", "rule": "token discipline",
     "nudge": "recurring loop is $0 (deterministic); if >5% weekly tokens in a day, halt new spawns and go read-only."},
]

PREAMBLE = (
    "You are operating under the Mag nudge contract. Comply with every rule that applies: "
    + "; ".join(f"{n['id']}: {n['nudge']}" for n in NUDGES)
)


def spec() -> dict[str, Any]:
    return {"schema": SCHEMA, "ok": True, "nudges": NUDGES, "count": len(NUDGES),
            "note": "the nudge contract ghost loads to steer models; automatic on consensus"}


def nudge(prompt: str) -> dict[str, Any]:
    """Nudge a prompt: prepend the steering contract + route it (cheap-first, grok-gated)."""
    prompt = (prompt or "").strip()
    nudged = f"{PREAMBLE}\n\nOPERATOR ASK: {prompt}"
    out: dict[str, Any] = {"schema": SCHEMA, "ok": True, "prompt": prompt[:200],
                           "nudged_prompt": nudged}
    # route: cheap-first, grok only frontier
    try:
        from mag.grok_gate import should_use_grok
        gate = should_use_grok(prompt)
        out["route"] = "cheap" if not gate.get("use_grok") else "grok(frontier)"
        out["grok_gate"] = gate.get("reason")
    except Exception as e:
        out["gate_error"] = str(e)[:120]
    try:
        from mag.skill_pipeline import route as sp_route
        out["skills"] = [s["id"] for s in sp_route(prompt).get("chain", [])]
    except Exception:
        pass
    return out


def auto() -> dict[str, Any]:
    """Persist the nudge spec as the automatic default (data ghost loads on every steer)."""
    SPEC_PATH.parent.mkdir(parents=True, exist_ok=True)
    s = spec()
    SPEC_PATH.write_text(json.dumps(s, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    s["path"] = str(SPEC_PATH)
    s["consensus"] = True
    s["automatic"] = True
    return s


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = (argv[0] if argv else "spec").lower()
    if cmd == "auto":
        print(json.dumps(auto(), indent=2, ensure_ascii=False, default=str))
    elif cmd == "nudge":
        print(json.dumps(nudge(" ".join(argv[1:]) if len(argv) > 1 else ""),
                         indent=2, ensure_ascii=False, default=str))
    else:
        print(json.dumps(spec(), indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
