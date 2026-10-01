"""Grok mirror — mirror the "Grok instruction-production" pattern through our pipeline.

GOLD MINE (stolen from a shared X Grok conversation): Grok turns a VISION prompt + a
"make this a frontier research plan for dumber models to execute" follow-up into a
decomposable, executable instruction package. That is our RenderMan tesuji observed in
the wild: frontier compacts, cheap executes. This module MIRRORS that exact
instruction-production pattern through our own pipeline:

  1. `capture_plan(vision)`     — send the vision + the mirror prompt to grok (frontier)
                                 → a structured research plan (mission, ≤8-step decomposition
                                 constraints, parallel tracks, kernel, cadence, risk, first prompt).
  2. `interpret(plan)`          — OUR code interpretation: deterministically map each plan
                                 section/track/step to our existing machinery (research_pack,
                                 cheap_swarm, frontier_ghost, research_lens, agent_state,
                                 verkle, skill_ledger). No LLM — bytes, not vibes.
  3. `questions(plan)`          — SOCRATIC elevation (RenderMan): ask grok what the executor
                                 needs to complete it, so we get the exact spec.
  4. `research_project(vision)` — build a self-referencing research pack (research_lens) from
                                 the findings and dispatch it to the cheap swarm.
  5. `distill_skill(...)`       — distill the prompt pattern + pipeline into a reusable SKILL.
  6. `run_mirror(vision)`       — orchestrate the whole mirror autonomously + write a report.

The GHOST helps and actively observes: `set_active_coding_window(on)` flips a flag
(state/active_coding_window.json) that ghost.sense_surfaces() reads, so ghost knows an
active coding window is running this mirror.

Schema: grok_mirror.v1
CLI:  python -m mag.grok_mirror "vision" [--no-grok] [--research] [--skill] [--window-on]
      python -m mag.grok_mirror window on|off|status
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except ImportError:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCHEMA = "grok_mirror.v1"
OUT_DIR = ROOT / "memory" / "runs" / "grok_mirror"
WINDOW_FLAG = ROOT / "state" / "active_coding_window.json"

# The stolen instruction-production prompt pattern: vision -> decomposable plan for
# dumber models to execute. This is the exact shape Grok produced (mission, constraints,
# tracks, kernel, cadence, risk, first prompt).
MIRROR_PROMPT = (
    "You are given a vision. Produce a full frontier research plan for dumber models to "
    "execute — structured EXACTLY like this (executable end-to-end by mid-tier models, "
    "only public data + commodity hardware + open tooling; no frontier-model exclusivity):\n"
    "0) MISSION STATEMENT (one sentence).\n"
    "1) DESIGN CONSTRAINTS for dumber-model execution: every work package decomposable into "
    "<=8 sequential agent steps; inputs limited to open sources (arXiv, HF datasets, GitHub, "
    "public data); outputs must be code/configs/literature matrices/protocols/CAD; evaluation "
    "automatic (unit tests, physics checks, open benchmarks); no proprietary APIs.\n"
    "2) FOUR PARALLEL RESEARCH TRACKS (A-D), each with 5 numbered work packages and a "
    "quantified success metric per track.\n"
    "3) CROSS-TRACK INTEGRATION LAYER (the kernel): unified accounting, an interoperability "
    "score every artifact carries, monthly re-ranking.\n"
    "4) EXECUTION CADENCE for dumber models (week/month phase timeline with a success gate).\n"
    "5) RISK & FAILURE HANDLING (built-in): capability overhang, hallucination, resource "
    "starvation, coordination failure.\n"
    "6) IMMEDIATE FIRST PROMPT (copy-paste for any open model).\n"
    "Be concrete, decomposed, and machine-executable. THE VISION:\n\n"
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug(s: str, n: int = 48) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", (s or "mirror").lower()).strip("-")
    return (s or "mirror")[:n]


# ---------------------------------------------------------------- window flag ----
def set_active_coding_window(on: bool) -> dict[str, Any]:
    """Flip the active-coding-window flag the ghost observes."""
    WINDOW_FLAG.parent.mkdir(parents=True, exist_ok=True)
    WINDOW_FLAG.write_text(json.dumps(
        {"active": bool(on), "ts": _now(), "schema": "active_coding_window.v1"}, indent=2),
        encoding="utf-8")
    return {"ok": True, "active": bool(on), "flag": str(WINDOW_FLAG)}


def active_coding_window() -> dict[str, Any]:
    if WINDOW_FLAG.is_file():
        try:
            d = json.loads(WINDOW_FLAG.read_text(encoding="utf-8"))
            return {"ok": True, "active": bool(d.get("active")), "ts": d.get("ts"), "flag": str(WINDOW_FLAG)}
        except Exception:
            pass
    return {"ok": True, "active": False, "flag": str(WINDOW_FLAG)}


# ----------------------------------------------------------------- capture ----
def capture_plan(vision: str, *, grok: bool = True) -> dict[str, Any]:
    """Send the vision + mirror prompt to grok (frontier) -> structured research plan."""
    prompt = MIRROR_PROMPT + (vision or "")[:4000]
    if not grok:
        return {"ok": False, "action": "dry", "prompt_chars": len(prompt), "plan": ""}
    try:
        # Elevation -> the working team API (XAI_API_KEY = funded team 715bf1ab), NOT the
        # free CLI harness. grok_free is for default/non-elevated work; a mirror is an
        # elevated grok query and should hit the funded grok-4.
        from mag.grok_rightsize import call_grok
        res = call_grok(prompt, max_tokens=4096, tier="orchestrate")
        return {
            "ok": bool(res.ok),
            "model": res.model, "tier": res.tier,
            "plan": (res.content or ""),
            "tokens_prompt": res.tokens_prompt, "tokens_completion": res.tokens_completion,
            "cost_est_usd": res.cost_est_usd, "latency_ms": res.latency_ms,
            "key_env": res.key_env, "error": res.error, "prompt_chars": len(prompt),
        }
    except Exception as e:
        return {"ok": False, "error": str(e)[:200], "plan": ""}


# ---------------------------------------------------------------- interpret ----
def interpret(plan_text: str) -> dict[str, Any]:
    """OUR code interpretation: map each plan section/track to our machinery. Deterministic."""
    t = plan_text or ""
    low = t.lower()

    def has(*words: str) -> bool:
        return any(w in low for w in words)

    mapping: list[dict[str, Any]] = []

    def sec(label: str, module: str, why: str) -> None:
        mapping.append({"section": label, "our_module": module, "why": why})

    if has("mission"):
        sec("Mission", "state_brief", "freeze the one-sentence mission as the goal contract")
    if has("design constraints", "decomposable", "<=8", "8 sequential"):
        sec("Design constraints", "research_pack + cheap_swarm", "decompose into <=8-step packages; cheap swarm expands+executes")
    if has("track a", "energy"):
        sec("Track A", "research_pack", "spawn as a cheap research pack")
    if has("track b", "manufactur", "matter"):
        sec("Track B", "cheap_swarm", "dispatch build package to cheap tier")
    if has("track c", "cognitive", "knowledge", "agent scaffolding"):
        sec("Track C", "research_lens + agent_state", "self-referencing corpus + state-routed agents")
    if has("track d", "biolog", "health"):
        sec("Track D", "research_pack + integrity_kernel", "safety-gated protocol pack")
    if has("integration", "kernel", "sovereignty kernel", "re-ranking"):
        sec("Integration/kernel", "ghost + verkle_knot", "ghost senses all surfaces; verkle anchors the ledger")
    if has("cadence", "week 0", "month"):
        sec("Execution cadence", "governor_autorun", "map phases to cadence ticks")
    if has("risk", "failure", "hallucination", "overhang"):
        sec("Risk handling", "failure_kb + spec_gate", "gate + learn from failures")
    if has("first prompt", "copy-paste", "begin."):
        sec("Immediate first prompt", "frontier_help + renderman_ask", "percolate as a frontier ask / elevate")

    tracks = re.findall(r"Track\s+([A-D])", t)
    return {"ok": True, "sections_mapped": len(mapping), "mapping": mapping,
            "tracks_detected": sorted(set(tracks)), "plan_chars": len(t)}


# ---------------------------------------------------------------- questions ----
def questions(plan_text: str, *, grok: bool = True) -> dict[str, Any]:
    """Socratic elevation (RenderMan): ask grok what the executor needs to complete it."""
    ask = ("Given this research plan, specify the EXACT compact inputs/spec the executor "
           "(deepseek-v4-flash) needs to complete step 1 of each track: what data, what "
           "output shape, what acceptance check. Be terse. PLAN:\n" + (plan_text or "")[:4000])
    if not grok:
        return {"ok": False, "action": "dry"}
    try:
        from mag.renderman_ask import ask_grok_for_executor_spec
        return ask_grok_for_executor_spec(ask, executor="deepseek-v4-flash")
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


# ------------------------------------------------------------- research proj ----
def research_project(vision: str, plan_text: str, *, lens_id: str = "default") -> dict[str, Any]:
    """Build a self-referencing research pack from the mirror findings + dispatch to cheap."""
    try:
        from mag.research_lens import build_lens
        ask = (
            "Validate and operationalize this grok-mirrored research plan: extract the "
            "highest-leverage next steps our cheap swarm should execute, mapped to our "
            "existing machinery. Reference prior research; do not redo settled answers.\n\n"
            "VISION: " + vision[:1200] + "\n\nPLAN EXCERPT:\n" + (plan_text or "")[:4000]
        )
        return build_lens(ask, lens_id=lens_id, title="grok-mirror-" + _slug(vision))
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


# ------------------------------------------------------------------- skill ----
SKILL_TEMPLATE = """# Grok Instruction-Production Mirror

**Steal:** the pattern from a shared X Grok conversation — Grok turns a VISION prompt +
"make this a frontier research plan for dumber models to execute" into a decomposable,
executable instruction package. This is the RenderMan tesuji observed in the wild:
frontier compacts, cheap executes.

## The prompt pattern (steal this shape)
```
Given this vision, produce a full frontier research plan for dumber models to execute:
0) one-sentence MISSION
1) DESIGN CONSTRAINTS for dumber-model execution (every work package <=8 sequential
   agent steps; open inputs only; outputs code/configs/protocols/CAD; automatic eval;
   no proprietary APIs)
2) FOUR PARALLEL TRACKS (A-D), 5 numbered work packages each + quantified success metric
3) CROSS-TRACK INTEGRATION KERNEL (unified accounting, interoperability score, re-ranking)
4) EXECUTION CADENCE (week/month phases + success gate)
5) BUILT-IN RISK & FAILURE HANDLING (overhang, hallucination, starvation, coordination)
6) IMMEDIATE FIRST PROMPT (copy-paste for any open model)
```

## Why it works (the law it encodes)
- **Compact at frontier, expand at cheap** — grok freezes the spec (the RIB); dumber
  models execute it. Never make the cheap tier invent the plan.
- **Decompose to <=8 agent steps** — a mid-tier model can only hold so much; bite-sized
  packages are machine-executable.
- **Automatic evaluation** — unit tests / physics checks / open benchmarks, not vibes.
- **Built-in risk** — capability overhang, hallucination, starvation, coordination handled
  up front so cheap models don't derail.

## Our pipeline (mag/grok_mirror.py)
`capture_plan(vision)` → `interpret(plan)` (map sections to our modules) → `questions(plan)`
(socratic elevation) → `research_project(vision)` (research_lens build + cheap_swarm) →
`distill_skill()`. Ghost observes via the active-coding-window flag
(state/active_coding_window.json).

## Do this next time
When a vision/ambition lands, mirror it: capture the grok plan, interpret against our
modules, ask grok what the executor needs, spin a research pack, fold it back into the
lens corpus. Do NOT hand-build the plan from scratch — let the frontier produce it, then
we decompose + execute with cheap models.
"""


def distill_skill(*, vision: str = "", plan_text: str = "") -> dict[str, Any]:
    """Write the distilled SKILL + register a pro_library move."""
    skill_dir = ROOT / "memory" / "skills"
    skill_dir.mkdir(parents=True, exist_ok=True)
    path = skill_dir / "grok-instruction-production-mirror.md"
    path.write_text(SKILL_TEMPLATE, encoding="utf-8")
    rec = {"pro_library": None}
    try:
        from mag.pro_library import add_move
        rec["pro_library"] = add_move(
            signature="grok,mirror,instruction,plan,dumber-model,render,rib,frontier,cheap",
            kind="steer",
            move=(
                "When a vision lands, MIRROR it: send vision + 'make this a frontier "
                "research plan for dumber models' to grok (compact at frontier), then "
                "interpret against our modules, ask grok what the executor needs, spin a "
                "research pack, fold back into the lens corpus. Never hand-build the plan. "
                f"Origin vision: {(vision or '')[:120]}"
            ),
        )
    except Exception as e:
        rec["pro_library"] = {"ok": False, "error": str(e)[:120]}
    return {"ok": True, "skill": str(path), "registered": rec}


# ------------------------------------------------------------------- mirror ----
def run_mirror(vision: str, *, grok: bool = True, research: bool = True,
               skill: bool = True, socratic: bool = True, lens_id: str = "default") -> dict[str, Any]:
    """Autonomous full mirror: capture -> interpret -> (socratic) questions -> research ->
    skill -> report. Ghost observes via the active-coding-window flag."""
    set_active_coding_window(True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {"schema": SCHEMA, "ts": _now(), "vision": (vision or "")[:200],
                              "grok": grok, "socratic": socratic}

    cap = capture_plan(vision, grok=grok)
    report["capture"] = cap
    plan_text = cap.get("plan") or ""
    # HONESTY (operator 2026-08-10): 'grok' is only the REQUEST flag. Whether real grok output
    # was captured lives in grok_captured (true only when the call succeeded AND returned text).
    # No artifact may imply frontier output that did not actually arrive.
    report["grok_captured"] = bool(cap.get("ok") and (plan_text or "").strip())
    if report["grok_captured"] is False:
        report["provenance_note"] = "grok was requested but returned no real output; this is OUR synthesis, not frontier output"

    report["interpret"] = interpret(plan_text)

    if socratic:
        report["questions"] = questions(plan_text, grok=grok)

    if research:
        report["research_project"] = research_project(vision, plan_text, lens_id=lens_id)

    if skill:
        report["skill"] = distill_skill(vision=vision, plan_text=plan_text)

    # write the report (the mirror artifact)
    rid = "mirror-" + _slug(vision)
    out_path = OUT_DIR / f"{rid}.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, default=str, indent=2), encoding="utf-8")
    report["report_path"] = str(out_path)

    # ghost-observable: keep the flag on while we're actively coding.
    return report


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    ap = argparse.ArgumentParser(prog="grok-mirror", description="Mirror Grok's instruction-production through our pipeline")
    ap.add_argument("vision", nargs="*", help="the vision prompt to mirror (or 'window' subcommand)")
    ap.add_argument("--no-grok", action="store_true", help="dry: capture/interpret/questions without grok calls")
    ap.add_argument("--no-research", action="store_true", help="skip the research pack")
    ap.add_argument("--no-skill", action="store_true", help="skip skill distillation")
    ap.add_argument("--no-socratic", action="store_true", help="skip socratic elevation questions to grok")
    ap.add_argument("--lens", default="default")
    ap.add_argument("--window-on", action="store_true", help="set active-coding-window flag (ghost observes)")
    args = ap.parse_args(argv)

    if args.window_on:
        print(json.dumps(set_active_coding_window(True), indent=2))
        return 0
    if args.vision and args.vision[0] == "window":
        sub = args.vision[1] if len(args.vision) > 1 else "status"
        if sub in ("on", "true", "1"):
            print(json.dumps(set_active_coding_window(True), indent=2))
        elif sub in ("off", "false", "0"):
            print(json.dumps(set_active_coding_window(False), indent=2))
        else:
            print(json.dumps(active_coding_window(), indent=2))
        return 0
    if not args.vision:
        print("usage: python -m mag.grok_mirror '<vision>' [--no-grok] [--window-on]")
        return 1
    vision = " ".join(args.vision)
    r = run_mirror(vision, grok=not args.no_grok, research=not args.no_research,
                   skill=not args.no_skill, socratic=not args.no_socratic, lens_id=args.lens)
    print(json.dumps(r, indent=2, default=str)[:12000])
    return 0


__all__ = ["capture_plan", "interpret", "questions", "research_project", "distill_skill",
           "run_mirror", "set_active_coding_window", "active_coding_window", "main"]


if __name__ == "__main__":
    raise SystemExit(main())
