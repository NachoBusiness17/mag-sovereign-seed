"""vscode_seat — turn a VS Code chat into a CONTROLLED executor seat for the Republic.

The operator asks how our software "manipulates" VS chat to do exactly what we want. The honest
mechanism: you don't hack the editor — you CONTROL it through its input, the same way we steer the
stateless DeepSeek agents. VS Code chat is a SEAT (bound by VS Code rules, sandboxed browser, no
secrets). So the Republic writes a precise, steering-loaded, architecture-routed TASK SPEC and the
chat executes it exactly.

  task_spec(task, ...)  — build the controlled task spec (steering + directives + acceptance +
                         report-back contract).
  generate(task, ...)   — write the spec to a file, return the ONE-LINE opener for a new chat.
  opener(path)          — the line to paste into a new VS Code chat.

Schema: vscode_seat.v1 · deterministic $0
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

SCHEMA = "vscode_seat.v1"
TASK_DIR = ROOT / "memory" / "runs" / "vscode_tasks"

# Architecture directives every Republic executor seat must obey (from the routing doctrine).
_DIRECTIVES = [
    "Route through the architecture (mag modules, REST, queue) — NEVER ad-hoc terminal for framework ops.",
    "Use file edits + Pylance/runCodeSnippet for deterministic work. No approval pings after 'go'.",
    "SELF-STEAL + EXTERNAL-STEAL on any non-trivial build (check our modules + other systems, adapt).",
    "Dogfood: probe the real system; surface failures honestly. Honest provenance — never call synthesis 'frontier'.",
    "Steal the INVARIANT, never the DNA. Report back by writing the result to the contract path + folding.",
]


def task_spec(*, task: str, skill: str = "default", steer: bool = True,
              acceptance: list[str] | None = None, id: str | None = None) -> dict[str, Any]:
    """Build a controlled VS Code chat task spec (what to do, how to do it, when done, report back)."""
    tid = id or datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    steer_lines = []
    if steer:
        try:
            from mag.frontier_steer import preamble
            steer_lines = preamble()
        except Exception:
            steer_lines = []
    acc = acceptance or ["The task's stated goal is met, verified by a real probe (not asserted).",
                         "Result written to the report-back path + folded into the knowledge graph."]
    spec = {
        "schema": SCHEMA, "id": tid, "task": task, "skill": skill,
        "steering": steer_lines,
        "directives": _DIRECTIVES,
        "routing": _grounded_routing(task),
        "acceptance": acc,
        "report_back": str(TASK_DIR / tid / "report.md"),
        "note": "Execute EXACTLY this. Write report.md, fold the invariant, then stop.",
    }
    return spec


def _grounded_routing(task: str) -> dict[str, Any]:
    """The provenance-grounded routing decision for this seat task: the deterministic lens fed to
    deepseek. Frontier ONLY when a real seat is live AND verkle frontier provenance exists — never
    route/label a DeepSeek result as frontier (provenance_router)."""
    try:
        from mag import provenance_router
        return provenance_router.route(task)
    except Exception as e:
        return {"tier": "flash", "provider": "deepseek", "provenance": "deepseek",
                "error": str(e)[:120]}


def generate(*, task: str, skill: str = "default", steer: bool = True,
             acceptance: list[str] | None = None, id: str | None = None) -> dict[str, Any]:
    """Write the task spec to disk and return the ONE-LINE opener for a new VS Code chat."""
    spec = task_spec(task=task, skill=skill, steer=steer, acceptance=acceptance, id=id)
    d = TASK_DIR / spec["id"]
    d.mkdir(parents=True, exist_ok=True)
    path = d / "task.md"
    lines = [f"# VS Code seat task — {spec['id']}", "",
             f"## TASK\n{spec['task']}", "",
             "## STEERING (follow these)",
             *[f"- {s}" for s in spec["steering"]], "",
             "## ARCHITECTURE DIRECTIVES",
             *[f"- {s}" for s in spec["directives"]], "",
             "## ACCEPTANCE (done only when these hold)",
             *[f"- {a}" for a in spec["acceptance"]], "",
             "## REPORT BACK",
             f"Write `{spec['report_back']}` with what you did + any invariant folded, then STOP.", ""]
    path.write_text("\n".join(lines), encoding="utf-8")
    opener = (f"Read `{path}` and execute it exactly as the Republic's controlled seat — "
              f"you know the standing directives. Go.")
    return {"ok": True, "schema": SCHEMA, "id": spec["id"], "task_path": str(path),
            "report_back": spec["report_back"], "opener": opener}


def self_fix_swarm(*, errors: list[str] | None = None, id: str | None = None) -> dict[str, Any]:
    """Repurpose vscode_seat.generate() ON THE FLY into a SELF-FIXING SWARM seat.

    Operator (2026-08-11): "we can repurpose it on the fly can't we" + "self fixing swarm".
    YES — generate() is already parameterized, so a new controlled seat task + opener is produced
    per call. This helper repurposes it for the fixing agent: the seat runs the self-heal loop
    (error_healer SEE->MEM->PATCH->FOLD), fixes real errors via file edits + get_errors
    verification (RIB-debug law), folds the invariant, and reports back by file so ghost can watch.

    Deterministic + $0 (no LLM here — this just assembles the spec + opener; the seat executes).
    Returns the same shape as generate(): {ok, id, task_path, report_back, opener}.
    """
    focus = errors or ["the errors surfaced by mag.error_healer.scan() and mag.dogfood_audit"]
    task = (
        "Act as the SELF-FIXING SWARM seat. Use module functions only (NO ad-hoc terminal / "
        "python -m spawns for routing). Steps: "
        "1) import mag.error_healer and call scan() then heal(force=False) — the SEE -> MEM -> "
        "PATCH -> FOLD mid-steer pass for every surfaced error; "
        "2) for any error that needs a real code fix, do it via file edits + get_errors "
        "(RIB-debug: verify against its spec, never claim 'done' unverified); "
        "3) fold each fixed invariant via mag.steal_pack; "
        "4) write report.md to the report_back path and STOP. Errors to focus on: " +
        "; ".join(focus)
    )
    acceptance = [
        "Every surfaced error was scanned and either healed (MEM->PATCH->FOLD) or honestly flagged "
        "as unfixable.",
        "Each real fix was verified with get_errors (trust bytes, not reports).",
        "Report written to the report_back path + invariant folded.",
    ]
    return generate(task=task, skill="self-fixing-swarm", acceptance=acceptance,
                    id=id or datetime.now(timezone.utc).strftime("self-fix-%Y%m%d-%H%M%S"))


def main(argv: list[str] | None = None) -> int:
    import sys as _sys, json as _json
    task = " ".join(argv) if argv else "Build X"
    r = generate(task=task)
    print(_json.dumps(r, indent=2, default=str))
    return 0


def cadence_generate() -> dict[str, Any]:
    """Auto-generate a ready VS Code seat task from the current PENDING backlog (cheap, $0).
    Wired into afk_cadence so the Republic always has a fresh controlled task + opener for the
    next chat — the human just pastes the opener. Bounded: only if there's pending work and no
    fresh spec was generated recently."""
    try:
        st = json.loads((ROOT / "memory" / "handoff_state.json").read_text(encoding="utf-8"))
        pending = [p for p in st.get("pending", []) if p.strip()]
    except Exception:
        pending = []
    if not pending:
        return {"ok": True, "schema": SCHEMA, "generated": False, "reason": "no pending work"}
    # bounded: skip if a fresh spec exists from the last 6 hours
    fresh = [d for d in TASK_DIR.iterdir() if d.is_dir()] if TASK_DIR.is_dir() else []
    if fresh:
        try:
            newest = max((d for d in fresh if (d / "task.md").exists()),
                         key=lambda d: d.stat().st_mtime)
            from datetime import datetime, timezone
            age_s = (datetime.now(timezone.utc).timestamp() - newest.stat().st_mtime)
            if age_s < 6 * 3600:
                opener = (f"Read `{newest / 'task.md'}` and execute it exactly as the Republic's "
                          f"controlled seat — you know the standing directives. Go.")
                return {"ok": True, "schema": SCHEMA, "generated": False, "reason": "fresh spec exists",
                        "task_path": str(newest / "task.md"), "opener": opener}
        except Exception:
            pass
    task = pending[0]
    r = generate(task=task, id=datetime.now(timezone.utc).strftime("vsc-%Y%m%d-%H%M%S"))
    return {"ok": True, "schema": SCHEMA, "generated": True, "task_path": r["task_path"],
            "opener": r["opener"]}


if __name__ == "__main__":
    raise SystemExit(main())
