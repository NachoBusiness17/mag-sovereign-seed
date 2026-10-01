"""Frontier ghost — launch a grok terminal and navigate it to build packages for
cheap agent swarms.

THE TESUJI: a frontier ghost (a grok terminal session) BUILDS packages — compact
RenderMan RIB specs, frozen BUILD contracts, working artifacts — and a cheap agent
swarm EXPANDS + EXECUTES them. Compact at frontier, expand at cheap (RenderMan law).

This module is the frontier ghost's driver:
  1. `is_critical(task)`        — deterministic gate: is this coding task critical
                                    enough to warrant a live grok terminal?
  2. `scan_for_critical()`      — find a critical coding task in the queue/handoff
                                    that deserves the frontier ghost.
  3. `launch_terminal(...)`     — start the grok terminal (frontier ghost) on a goal.
  4. `navigate(...)`            — drive it: feed the ask, read output, steer follow-up
                                    turns until the package meets acceptance.
  5. `run_critical()`           — the orchestration entry: scan -> build RIB/context ->
                                    launch+navigate -> fold the package back to the swarm
                                    (handoff BUILD contract + verkle anchor + skill row).

Criticality is CODE-AS-LAW: a task is critical for the frontier ghost when it is a
build/implement ask (factory gate), OR a frontier-gap task shape, OR the frontier stack
is ready to batch-elevate, OR it is mission-tier. Never ask the LLM/operator which
model/seat — the deterministic gate decides. Schema: grok_terminal.v1
CLI:  python -m mag.grok_terminal scan
      python -m mag.grok_terminal run --task <id|goal> [--cwd DIR] [--rounds N]
      python -m mag.grok_terminal launch "<goal>" [--cwd DIR] [--rounds N]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import RESULTS_DIR, ROOT

SCHEMA = "grok_terminal.v1"
MAX_ROUNDS_DEFAULT = 4
RESULT_DIR = ROOT / "memory" / "runs" / "grok_terminal"
STATE = RESULT_DIR / "state.json"

# Deterministic criticality bar (code-as-law — no LLM vote).
CRITICAL_TIERS = {"mission", "research"}
CRITICAL_TAGS = ("build", "implement", "code", "construct", "refactor")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    out = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except (json.JSONDecodeError, TypeError):
            continue
    return out


def _grok_bin() -> str | None:
    try:
        from harness.grok_cli import find_grok
        return find_grok()
    except Exception:
        return None


def _policy() -> dict[str, Any]:
    """Read the grok-harness policy gate (code-as-law — the config decides, not the LLM)."""
    import os
    pol: dict[str, Any] = {}
    try:
        import yaml
        p = ROOT / "configs" / "mag.yaml"
        if p.is_file():
            pol = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except Exception:
        pass
    if os.environ.get("MAG_NO_HARNESS"):
        pol["use_grok_harness"] = False
    return pol


def _harness_allowed() -> bool:
    return bool(_policy().get("use_grok_harness"))


def is_critical(task: dict[str, Any] | None) -> bool:
    """Deterministic gate: should this coding task get the frontier ghost?

    Critical when the task is a build/implement ask (require_build / factory gate),
    is a frontier-gap task shape, or is mission/research tier tagged for building.
    """
    if not task:
        return False
    goal = str(task.get("goal") or task.get("query") or task.get("name") or "")
    tier = str(task.get("tier") or task.get("priority") or "").lower()
    tag = str(task.get("tag") or "").lower()

    if task.get("require_build") or task.get("factory_gate"):
        return True
    if any(k in goal.lower() for k in CRITICAL_TAGS):
        return True
    if tier in CRITICAL_TIERS and tag.startswith(("build", "code", "construct")):
        return True
    # frontier-gap task shape -> build package at frontier
    try:
        from mag.gap_map import analyze as gap_analyze
        shape = str(task.get("task_shape") or task.get("depth") or "")
        if shape and shape in (gap_analyze().get("frontier_gap_names") or []):
            return True
    except Exception:
        pass
    return False


def scan_for_critical(limit: int = 5) -> list[dict[str, Any]]:
    """Scan the orchestrator queue for a critical coding task that deserves the ghost."""
    found = []
    try:
        from mag.orchestrator import list_queue

        for item in list_queue(limit=80):
            if is_critical(item):
                found.append(item)
    except Exception:
        pass
    # Also look at handoff BUILD contracts (factory gate) — the classic package ask.
    try:
        hd = ROOT / "queue" / "handoff"
        if hd.is_dir():
            for p in sorted(hd.glob("BUILD-*.md"))[:limit]:
                found.append({
                    "id": p.stem,
                    "goal": f"execute build contract: {p.name}",
                    "source": "handoff",
                    "contract_path": str(p),
                    "require_build": True,
                    "tier": "mission",
                })
    except Exception:
        pass
    return found[:limit]


def _build_context(task: dict[str, Any]) -> str:
    """Compose the frontier ghost's input — RenderMan RIB + any frozen contract."""
    parts = []
    try:
        from mag.renderman_ask import compact_ask, render_rib
        rib = compact_ask(
            goal=task.get("goal") or "",
            inputs=[str(v) for v in task.get("inputs") or []],
            executor="grok-4.5",
            output_contract="write concrete files under cwd; end with SUMMARY/DELIVERABLE",
            acceptance="package built; no secrets exfiltrated",
        )
        parts.append("## RenderMan RIB (frozen spec)\n" + render_rib(rib))
    except Exception:
        pass
    cp = task.get("contract_path")
    if cp:
        try:
            parts.append("## Frozen BUILD contract\n" + Path(cp).read_text(encoding="utf-8", errors="replace")[:8000])
        except Exception:
            pass
    # Self-reference the research lens corpus: the frontier ghost builds on what the
    # cheap system already learned (compounding), not on a cold blank slate.
    try:
        from mag.research_lens import retrieve_prior
        pr = retrieve_prior(task.get("goal") or "", lens_id="default", limit=4)
        if pr.get("prior_refs"):
            parts.append("## PRIOR RESEARCH IN THIS LENS (build on it; don't redo settled answers)\n"
                         + pr.get("prior_block", "")[:6000])
    except Exception:
        pass
    return "\n\n".join(parts)


def launch_terminal(*, goal: str, cwd: Path | None = None, context: str = "",
                    rounds: int = MAX_ROUNDS_DEFAULT, yolo: bool | None = None) -> dict[str, Any]:
    """Launch the grok terminal (frontier ghost) and navigate it to build the package."""
    from harness.grok_cli import escalate_via_harness, harness_available

    pol = _policy()
    if not _harness_allowed():
        return {"ok": False, "error": "grok harness disabled (set use_grok_harness: true in configs/mag.yaml)",
                "action": "blocked_policy"}
    if not harness_available():
        return {"ok": False, "error": "grok terminal unavailable (grok CLI/harness not installed)",
                "action": "blocked"}
    if yolo is None:
        yolo = bool(pol.get("harness_yolo"))
    cwd = cwd or ROOT
    rounds = max(1, int(rounds or MAX_ROUNDS_DEFAULT))
    steering = context or ""
    prior = ""
    log = []

    for r in range(1, rounds + 1):
        prompt = goal if r == 1 else (
            "Continue/refine the package from your previous work to meet acceptance.\n\n"
            "## Previous deliverable (your own)\n" + prior[-12000:] + "\n\n## Goal\n" + goal
        )
        res = escalate_via_harness(
            goal=prompt, context=steering, cwd=cwd, max_turns=12,
            yolo=yolo, handoff_id=f"grokterm-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-r{r}",
        )
        res["round"] = r
        res["goal"] = goal
        log.append(res)
        if not res.get("ok"):
            break
        prior = str(res.get("deliverable") or "")
        summary = str(res.get("summary") or "")
        # A concrete SUMMARY + DELIVERABLE means the package was built — accept.
        if summary.strip() or _looks_delivered(prior):
            break

    result = {
        "schema": SCHEMA,
        "ok": any(x.get("ok") for x in log),
        "action": "launched_navigated" if log else "no_rounds",
        "goal": goal,
        "rounds_run": len(log),
        "rounds": rounds,
        "cwd": str(cwd),
        "log": log,
        "final_summary": (log[-1].get("summary") if log else ""),
        "final_deliverable": (log[-1].get("deliverable") if log else "")[:2000],
        "ts": _now(),
    }
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULT_DIR / f"ghost-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, default=str, indent=2)[:300000], encoding="utf-8")
    result["result_path"] = str(out_path)
    return result


def _looks_delivered(text: str) -> bool:
    t = text.upper()
    return "DELIVERABLE:" in t or "## SUMMARY" in t or "wrote " in t.lower()


def _fold_back(result: dict[str, Any], task: dict[str, Any]) -> dict[str, Any]:
    """Fold the frontier ghost's package back to the cheap swarm: handoff contract +
    verkle anchor + skill_ledger row."""
    folded = {"handoff": False, "verkle": False, "skill": False}
    try:
        hd = ROOT / "queue" / "handoff"
        hd.mkdir(parents=True, exist_ok=True)
        stem = "GHOST-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        body = (
            f"# BUILD {stem}\n\n- Source: frontier ghost (grok terminal) on critical task\n"
            f"- Goal: {(task.get('goal') or '')[:300]}\n- Status: package built; cheap swarm executes.\n\n"
            f"## Package / deliverable\n{result.get('final_deliverable') or '(see result_path)'}\n"
            f"Result: {result.get('result_path')}\n"
        )
        (hd / f"{stem}.md").write_text(body, encoding="utf-8")
        folded["handoff"] = True
    except Exception:
        pass
    try:
        from mag.verkle_knot import append_verkle_knot
        append_verkle_knot({
            "session_id": f"grokterm-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}",
            "theme": "grok_terminal",
            "summary": f"Frontier ghost built package: " + (task.get("goal") or "")[:300],
        })
        folded["verkle"] = True
    except Exception:
        pass
    try:
        from mag.skill_ledger import record
        record("grok_terminal_package", input_data={"goal": task.get("goal") or ""},
               action={"seat": "grok-terminal", "rounds": result.get("rounds_run")},
               outcome={"ok": result.get("ok")}, source="grok_terminal")
        folded["skill"] = True
    except Exception:
        pass
    return folded


def run_critical(*, task: dict[str, Any] | None = None, cwd: Path | None = None,
                 rounds: int = MAX_ROUNDS_DEFAULT, yolo: bool = False) -> dict[str, Any]:
    """Scan -> pick a critical coding task -> launch+navigate frontier ghost -> fold back."""
    t = task or (scan_for_critical(limit=1)[0] if scan_for_critical(limit=1) else None)
    if not t:
        return {"ok": False, "action": "no_critical_task", "reason": "nothing critical to build"}
    if not is_critical(t):
        return {"ok": False, "action": "not_critical", "reason": "task below criticality bar"}
    context = _build_context(t)
    res = launch_terminal(goal=t.get("goal") or "", cwd=cwd, context=context,
                          rounds=rounds, yolo=yolo)
    res["task"] = {k: t.get(k) for k in ("id", "goal", "tier", "tag", "task_shape", "depth") if k in t}
    res["fold"] = _fold_back(res, t) if res.get("ok") else {"skipped": True}
    return res


def run_cadence() -> dict[str, Any]:
    """Idempotent-ish cadence: only run the frontier ghost when there's a NEW critical
    task not already handed to the ghost (tracked by goal hash in state)."""
    prev = set()
    if STATE.is_file():
        try:
            prev = set((json.loads(STATE.read_text(encoding="utf-8")) or {}).get("done") or [])
        except Exception:
            prev = set()
    tasks = scan_for_critical(limit=5)
    picked = None
    for t in tasks:
        key = str(t.get("goal") or t.get("id") or "")[:80]
        if key and key not in prev:
            picked = t
            break
    if picked is None:
        return {"ok": True, "action": "skip", "reason": "no_new_critical_task"}
    res = run_critical(task=picked)
    key = str(picked.get("goal") or picked.get("id") or "")[:80]
    if res.get("ok") and key:
        prev.add(key)
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps({"done": sorted(prev), "ts": _now()}, indent=2), encoding="utf-8")
    return res


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    ap = argparse.ArgumentParser(prog="grok-terminal", description="Frontier ghost: launch a grok terminal to build packages for cheap swarms")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("scan", help="list critical coding tasks that deserve the frontier ghost")
    p_run = sub.add_parser("run", help="run the frontier ghost on a critical task")
    p_run.add_argument("--task", default="", help="task id or goal; empty = auto-pick first critical")
    p_run.add_argument("--cwd", default="", help="working dir for the ghost")
    p_run.add_argument("--rounds", type=int, default=MAX_ROUNDS_DEFAULT, help="max navigate rounds")
    p_run.add_argument("--yolo", action="store_true", help="always-approve shell in the ghost")
    sub.add_parser("cadence", help="idempotent cadence: run only on NEW critical tasks")
    args = ap.parse_args(argv)

    if args.cmd == "scan":
        print(json.dumps({"schema": SCHEMA, "critical": scan_for_critical()}, indent=2, default=str)[:8000])
    elif args.cmd == "run":
        task = None
        if args.task:
            task = {"id": args.task, "goal": args.task, "require_build": True, "tier": "mission"}
        print(json.dumps(run_critical(task=task, cwd=Path(args.cwd) if args.cwd else None,
                                      rounds=args.rounds, yolo=args.yolo), indent=2, default=str)[:12000])
    elif args.cmd == "cadence":
        print(json.dumps(run_cadence(), indent=2, default=str)[:12000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
