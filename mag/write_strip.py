"""write_strip — the fan-out write-strip compiler (MICKEY-17 owed chore, 2026-09-26).

Compiles a subagent's tool-schema grant DOWN to the read-only subset at
fan-out time, so a spawned lane never sees tool definitions it cannot use.
Schema-level omission, not runtime veto — the LLM never sees the write tool
at all (arXiv:2603.05344v3 via MICKEY-17 v2 lane `write-delegation#0`;
single-writer doctrine via lane `orchestrator-war-stories#0`, Cognition's
April 2026 reversal: extra agents contribute intelligence while writes stay
single-threaded).

Scope (the brief's boundary): this module and its three call-site patches are
RUNNER-SIDE only — the estate's own fan-out layer:
    mag/orchestrator.py spawn_task()  ->  appends --read-only to the child cmd
    main.py "agent" subcommand        ->  forwards the flag
    mag/agent_cli.py run_agent()      ->  activates the strip before turn 1
The equivalent ZCode-HARNESS change (the agent() facade natively restricting
subagent tool schemas at spawn) is NOT built here — it stays spec-only in
watch/inbox/WRITE_STRIP_FANOUT_20260926.md, per the chore's own wording.

Classification is BY NAME (schema-level, before any model call):
  write     — unambiguous mutating tools: estate write_file, the harness
              family (Write/Edit/MultiEdit/NotebookEdit/apply_patch/
              str_replace_editor), file delete/move, and the estate's
              shared-state writers (pheromone_drop, blackboard_post — Law 6:
              shared-state writes are single-seat). Always stripped.
  dual_use  — tools that CAN write as a side effect but are also the lanes'
              read/fetch path (run_shell, bash, run_python). Kept by default;
              stripped under strict=True (typed survey seats).
  read      — everything else. Kept. Unknown names default to read so a lane
              never loses a capability silently; the receipt lists every kept
              name so the orchestrator can audit the grant.
"""
from __future__ import annotations

import os
from typing import Any

# The flag/env contract shared by orchestrator -> main.py -> agent_cli.
READ_ONLY_ARG = "--read-only"
ENV_READ_ONLY = "MAG_READ_ONLY"
ENV_READ_ONLY_STRICT = "MAG_READ_ONLY_STRICT"

# Names compared normalized: lowercased, underscores/hyphens removed.
WRITE_TOOL_NAMES = frozenset(
    {
        # estate seat
        "writefile",
        # harness/ZCode family (also seen in OpenAI/Anthropic-style schemas)
        "write",
        "edit",
        "multiedit",
        "notebookedit",
        "applypatch",
        "strreplaceeditor",
        # file lifecycle mutators seen across harnesses
        "createfile",
        "deletefile",
        "removefile",
        "movefile",
        "renamefile",
        # estate shared-state writers (Law 6: single-seat shared writes)
        "pheromonedrop",
        "blackboardpost",
    }
)

DUAL_USE_TOOL_NAMES = frozenset(
    {
        "runshell",
        "bash",
        "runpython",
        "pythonrepl",
    }
)

KIND_WRITE = "write"
KIND_DUAL_USE = "dual_use"
KIND_READ = "read"


def normalize_tool_name(name: str) -> str:
    """Lowercase and drop separators so 'Write'/'write_file'/'write-file' match."""
    return str(name or "").strip().lower().replace("_", "").replace("-", "")


def classify_tool(name: str) -> str:
    n = normalize_tool_name(name)
    if n in WRITE_TOOL_NAMES:
        return KIND_WRITE
    if n in DUAL_USE_TOOL_NAMES:
        return KIND_DUAL_USE
    return KIND_READ


def is_write_tool(name: str) -> bool:
    return classify_tool(name) == KIND_WRITE


def is_dual_use_tool(name: str) -> bool:
    return classify_tool(name) == KIND_DUAL_USE


def _tool_name(schema: Any) -> str | None:
    """Extract the tool name from the schema formats in use.

    Handles: OpenAI function format {"type":"function","function":{"name":..}},
    flat format {"name":..} (also the Anthropic shape), and None-safe junk.
    """
    if not isinstance(schema, dict):
        return None
    fn = schema.get("function")
    if isinstance(fn, dict) and fn.get("name"):
        return str(fn["name"])
    if schema.get("name"):
        return str(schema["name"])
    return None


def strip_write_tools(tools: list[dict[str, Any]], *, strict: bool = False) -> dict[str, Any]:
    """Compile a tool-schema grant to its read-only subset.

    Returns {"tools": kept_schemas, "receipt": {...}}. The input list and its
    dicts are never mutated; kept entries are the SAME dict objects (so callers
    that hash/compare schemas still work), only the container is new.
    """
    kept: list[dict[str, Any]] = []
    stripped: list[dict[str, str]] = []
    kept_names: list[str] = []
    unnamed = 0
    for schema in tools or []:
        name = _tool_name(schema)
        if name is None:
            # A schema without a name cannot be classified: keep it and say so
            # in the receipt rather than silently dropping a capability.
            kept.append(schema)
            kept_names.append("(unnamed)")
            unnamed += 1
            continue
        kind = classify_tool(name)
        if kind == KIND_WRITE or (strict and kind == KIND_DUAL_USE):
            stripped.append({"name": name, "kind": kind})
        else:
            kept.append(schema)
            kept_names.append(name)
    receipt = {
        "schema": "write_strip.v1",
        "strict": bool(strict),
        "total": len(tools or []),
        "kept": kept_names,
        "unnamed_kept": unnamed,
        "stripped": stripped,
        "stripped_names": [s["name"] for s in stripped],
    }
    return {"tools": kept, "receipt": receipt}


def read_only_from_env(env: dict[str, str] | None = None) -> tuple[bool, bool]:
    """Resolve (read_only, strict) from the environment (truthy 1/true/yes)."""
    e = env if env is not None else os.environ

    def _truthy(key: str) -> bool:
        return str(e.get(key, "")).strip().lower() in ("1", "true", "yes")

    return _truthy(ENV_READ_ONLY), _truthy(ENV_READ_ONLY_STRICT)
