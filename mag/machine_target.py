"""machine_target — RIB lowers to MACHINE/BINARY edits by default (the final target language).

Operator (2026-08-11): "steal linux and binary level machine edits and make it the default language
that rib translates to if it isn't already deep research steal. our mmos :D"

The thesis (from the deep-research steal): RIB (our instruction layer) should translate down to the
MACHINE/BINARY level as its DEFAULT target — the way a compiler lowers a high-level language to
machine code. If the agent can emit machine-level edits, it OWNS THE WHOLE STACK (agent as OS), and
our MMO swarm ultimately executes as machine processes (k8s pods = binary executables).

THE DEFAULT LOWERING (rank -> machine action, RIGHTSIZED):
  T0 deterministic $0 (AST/file/hash)  -> already local machine (no external action)
  T1 process                            -> fork/execve/mmap (run a binary; the k8s pod)
  T2 source/config edit                 -> file write (bytes on disk; our normal edits)
  T3 binary patch (byte-level)          -> ELF/section/relocation edit — the DEEPEST, RIGHTSIZED
                                           ONLY when source/config cannot reach the state
Every RIB invariant carries a target rank; the swarm lowers to the CHEAPEST machine action that
reaches the goal. Deterministic + $0 (a pure mapping spec; no actual binary patching without a real
assembler/patch tool, honestly scoped).

Schema: machine_target.v1
"""
from __future__ import annotations

from typing import Any

SCHEMA = "machine_target.v1"

# rank -> (machine action, description, when-to-use)
TARGETS: dict[str, dict[str, str]] = {
    "T0": {"action": "local", "desc": "deterministic $0 already-resolved (AST/file/hash)",
           "use": "the goal is reachable with our local deterministic tools"},
    "T1": {"action": "execve/mmap", "desc": "run a binary / read process state",
           "use": "the goal needs a running process (the k8s pod executes it)"},
    "T2": {"action": "file_write", "desc": "source/config edit (bytes on disk)",
           "use": "the goal is a source/config change (our normal edits)"},
    "T3": {"action": "binary_patch", "desc": "ELF/section/relocation byte edit (deepest)",
           "use": "RIGHTSIZED: only when source/config cannot reach the state"},
}

DEFAULT_TARGET = "machine"


def target(rank: str) -> dict[str, str]:
    """The machine action for a RIB target rank (T0-T3). Deterministic + $0."""
    t = TARGETS.get(str(rank).upper(), TARGETS["T2"])
    return {"rank": str(rank).upper(), "machine_action": t["action"],
            "desc": t["desc"], "when": t["use"]}


def lowers_to(invariant: str, rank: str = "T2") -> dict[str, Any]:
    """The concrete machine-level edit a RIB invariant lowers to (by default target rank)."""
    t = target(rank)
    return {"ok": True, "schema": SCHEMA, "invariant": invariant[:200],
            "target_language": DEFAULT_TARGET, "rank": t["rank"],
            "machine_action": t["machine_action"], "desc": t["desc"],
            "rightsize": ("cheapest machine action that reaches the goal; "
                          "binary_patch (T3) only when source/config can't")}


def default_target() -> dict[str, Any]:
    """Confirm the DEFAULT language RIB translates to = machine/binary (T0-T3 rank ladder)."""
    return {"ok": True, "schema": SCHEMA, "default_target": DEFAULT_TARGET,
            "why": "agent-as-OS: RIB lowers to machine/binary edits, owning the whole stack",
            "ranks": {k: v["action"] for k, v in TARGETS.items()}}


def main(argv: list[str] | None = None) -> int:
    import json, sys
    print(json.dumps(default_target(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
