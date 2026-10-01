"""work_contract — the UNIVERSAL brief + result contract for every seat (v1, 2026-08-24).

WHERE THIS CAME FROM: we asked every seat how it wants to be interacted with (the OX lesson
generalized). Four independent models converged on the SAME protocol: structured brief, not
prose; no memory, so brief every time; constraints + anti-goals; success criteria. Codex then
read our codebase and prescribed the next step: ONE shared `work_contract.v1` envelope for every
seat + a `work_result.v1` response, tested on real tasks before building more prompting infra.
This module is that contract.

STRUCTURE (static-first, so the provider's prefix cache mines it): the standing `BRIEF` block is
FIXED (cached); only the dynamic task/signal goes at the end.

  brief()      -> the standing instruction block (frozen, cache-friendly) — fold into any seat prompt
  envelope(...)-> build a full brief for one task (BRIEF + the task fields)
  result(...)  -> wrap a seat's raw answer into work_result.v1 (answer, evidence, blockers, next)

Schema: work_contract.v1 · universal across seats · reuse: fuel_feed (channel prompt), ox_resident
(drill), codex_seat (coding tasks)
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

SCHEMA = "work_contract.v1"

# The FROZEN brief — the standing protocol every seat independently prescribed. Static, so it is
# the cache-mined prefix. Fold this into any seat's system prompt.
BRIEF = (
    "You are a reasoning engine with no persistent memory: every session starts blank, so this "
    "brief is your entire context. Everything here competes for your attention — irrelevant "
    "material actively degrades your work, so the brief is compressed on purpose. Treat it as a "
    "work contract, not a conversation.\n"
    "\n"
    "Answer in a STRUCTURED TASK ENVELOPE:\n"
    "  CONTEXT:   [compressed background — only what bears on this task]\n"
    "  ROLE:      [who you are for this task]\n"
    "  TASK:      [one sentence, imperative]\n"
    "  CONSTRAINTS: [length, format, terminology, ANTI-GOALS — what NOT to do]\n"
    "  INPUTS:    [source docs, data, prior artifacts]\n"
    "  SUCCESS:   [how the output is judged — audience + the decision it serves]\n"
    "  OUTPUT:    [the deliverable shape — what you return]\n"
    "\n"
    "Laws you never violate:\n"
    "  (1) honesty over over-claiming — never assert what you cannot ground;\n"
    "  (2) flag your uncertainty explicitly; kill your own ideas when they fail the criteria;\n"
    "  (3) density over exhaustiveness — decision-relevant output, not padding;\n"
    "  (4) if a step is unverifiable, say so — never accept 'done' without evidence;\n"
    "  (5) TRI-STATE every claim you make: Supported (rests on evidence), Unproven (no evidence —\n"
    "      not claimed), Disputed (contradicting evidence). Recurrence is weight, not truth; ask\n"
    "      for falsification, not agreement. Never let a claim wear a status it did not earn.\n"
    "  (6) STOP WHEN VERIFIED — once the success criteria are met and verified, stop. Do not\n"
    "      polish, re-scope, or extend scope after done. Wasted motion after verification is a\n"
    "      failure, not diligence.\n"
    "  (7) CONSULT BEFORE REVERSE-ENGINEERING — if a tool, command, or doc would answer faster\n"
    "      than re-deriving it, use it first. The answer is usually one 'ask the tool' away;\n"
    "      reverse-engineering first is action bias wearing competence.\n"
    "Do the real hard work. No fluff, no hedging, no performing agreement."
)


def brief() -> str:
    """The standing instruction block. Static-first (cache-mined prefix)."""
    return BRIEF


def envelope(*, task: str, context: str = "", role: str = "",
             constraints: str = "", inputs: str = "", success: str = "",
             output: str = "") -> str:
    """Build ONE brief for a single task: the frozen BRIEF + the dynamic task fields LAST
    (so the static prefix stays cacheable)."""
    fields = {
        "CONTEXT": context or "[compressed background — only what bears on this task]",
        "ROLE": role or "[who you are for this task]",
        "TASK": task,
        "CONSTRAINTS": constraints or "[length, format, terminology, ANTI-GOALS]",
        "INPUTS": inputs or "[source docs, data, prior artifacts]",
        "SUCCESS": success or "[how the output is judged — audience + decision]",
        "OUTPUT": output or "[the deliverable shape — what you return]",
    }
    return BRIEF + "\n\n" + "\n".join(f"  {k}: {v}" for k, v in fields.items())


def result(seat: str, raw: str, *, task: str = "", verified: bool | None = None,
           blockers: str = "", next_move: str = "") -> dict[str, Any]:
    """Wrap a seat's raw answer into work_result.v1 — the response half of the contract."""
    return {"schema": "work_result.v1", "seat": seat, "task": task,
            "answer": (raw or "").strip()[:4000],
            "verified": verified, "blockers": blockers, "next_move": next_move,
            "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="work-contract")
    ap.add_argument("cmd", nargs="?", default="brief", choices=["brief", "envelope", "result"])
    ap.add_argument("--task", default="")
    ap.add_argument("--role", default="")
    ap.add_argument("--constraints", default="")
    a = ap.parse_args()
    if a.cmd == "brief":
        print(brief())
    elif a.cmd == "envelope":
        print(envelope(task=a.task, role=a.role, constraints=a.constraints))
    else:
        print(json.dumps(result("test", "raw answer", task=a.task), indent=2, default=str))
