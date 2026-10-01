"""skill_pipeline — one window, subprocesses, prompts routed through a series of skills.

The operator wants ONE surface: they send a prompt, and a series of developed skills
process it (no N terminal windows, no manual routing). Each skill is a framework module;
the pipeline classifies the prompt, runs the matching skill chain (cheap-first), and folds
the outcome back into the behavioral loop (self-improving, Law #6).

Grok is used ONLY for frontier-model work (Law #7, grok_gate) — never the default.

Skills registered here include everything developed this session:
  refine        (socratic)          session_route   (data-backed preamble)
  ghost_summon  (intent)            queue_rightsize (rightsize + learn)
  loop_breaker  (crash-loop)        legacy_audit    (retire legacy procs)
  platform_kill (kill all)          grok_gate       (frontier gate)
  self_drive    (data-backed spawn) ghost_grok      (dispatch frontier)

Schema: skill_pipeline.v1
CLI: python -m mag.skill_pipeline <prompt...>   (route + run the chain)
     python -m mag.skill_pipeline --list
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCHEMA = "skill_pipeline.v1"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


# Each skill: {id, desc, triggers, run(prompt)->result, tier}
# `tier` = the cheapest capable tier for this skill (Law #7: grok only frontier).
SKILLS: dict[str, dict[str, Any]] = {
    "refine": {
        "desc": "Cheaply refine a rough prompt (Socratic workshop).",
        "triggers": ("refine", "workshop", "tighten", "clean up this prompt", "polish"),
        "tier": "local",
        "run": lambda p: _safe_run("mag.socratic", "workshop", p),
    },
    "session_route": {
        "desc": "Data-backed session preamble (coding-agent seed + learned principles).",
        "triggers": ("long session", "coding session", "session-route", "start a session"),
        "tier": "flash",
        "run": lambda p: _safe_run("mag.session_route", "preamble", p),
    },
    "ghost_summon": {
        "desc": "Figure out intent from current+future+coldest vertices (summon @ghost).",
        "triggers": ("what should i do", "summon", "ghost", "intent", "what do i want", "sanity check"),
        "tier": "flash",
        "run": lambda p: _safe_run("mag.ghost_summon", "summon", p, reason=False),
    },
    "queue_rightsize": {
        "desc": "Right-size the queue (analyze/apply/learn) — cheapest capable tier, dedup overlap.",
        "triggers": ("queue", "rightsize", "efficient", "token", "spend", "backlog"),
        "tier": "local",
        "run": lambda p: _safe_run("mag.queue_rightsize", "analyze", ""),
    },
    "loop_breaker": {
        "desc": "Detect + break a crash-respawn loop (vs genuine strain).",
        "triggers": ("crash", "loop", "respawn", "windows", "storm", "spinning", "breaking"),
        "tier": "local",
        "run": lambda p: _safe_run("mag.loop_breaker", "detect", ""),
    },
    "legacy_audit": {
        "desc": "Catalog + retire leftover/legacy processes, mapped to newer systems.",
        "triggers": ("legacy", "leftover", "old process", "retire", "catalog process"),
        "tier": "local",
        "run": lambda p: _safe_run("mag.legacy_audit", "catalog", ""),
    },
    "platform_kill": {
        "desc": "Kill all Mag platform processes + container in one pass (dry by default).",
        "triggers": ("kill", "stop everything", "shut down", "teardown", "all platforms"),
        "tier": "local",
        "run": lambda p: _safe_run("mag.platform_kill", "kill_all", "", dry=True),
    },
    "grok_gate": {
        "desc": "Decide whether a task warrants frontier grok (cost-effective + cheap-test-first).",
        "triggers": ("grok", "frontier", "deep research", "deep dive", "deep-dive", "synthesize", "dive into"),
        "tier": "local",
        "run": lambda p: _safe_run("mag.grok_gate", "should_use_grok", p),
    },
    "self_drive": {
        "desc": "Data-backed spawn: model_pick + cached context + learned principles.",
        "triggers": ("spawn", "run a goal", "self-drive", "embark", "drive"),
        "tier": "flash",
        "run": lambda p: _safe_run("mag.self_drive", "plan", p),
    },
    "ghost_grok": {
        "desc": "Dispatch a frontier task to grok (gated by grok_gate — Law #7).",
        "triggers": ("grok task", "grok it", "frontier task"),
        "tier": "grok",
        "run": lambda p: _safe_run("mag.grok_rightsize", "ghost_grok_task", p),
    },
    "oh_fuck": {
        "desc": "EMERGENCY OH FUCK MODE — kill all platforms + container, memlang-steer the panic, record it.",
        "triggers": ("oh fuck", "emergency", "panic", "kill everything", "meltdown", "stop all now"),
        "tier": "local",
        "run": lambda p: _safe_run("mag.oh_fuck", "oh_fuck", p, dry=True),
    },
    "press": {
        "desc": "Recurring press digest — surface the next pressing matter (memlang-steered).",
        "triggers": ("press", "recurring", "what's pressing", "digest", "next matter"),
        "tier": "local",
        "run": lambda p: _safe_run("mag.press_digest", "emit", ""),
    },
    "icon_drop": {
        "desc": "Human-only action (can't automate: reload, restart lab, set secret, launch Vast) -> DROP a clickable icon into Desktop MAG Tools, don't nag in chat.",
        "triggers": ("icon", "can't automate", "cant automate", "manual", "operator", "drop an icon", "reload", "restart lab", "restart_lab", "you do it", "set secret", "vast launch", "click it"),
        "tier": "local",
        "run": lambda p: _safe_run("mag.icon_drop", "auto", p),
    },
    "tool_retire": {
        "desc": "Delete an old/superseded tool after use -> move to trash + FOLD the retirement into the learning loop (skill_ledger case law + training_events).",
        "triggers": ("delete old tool", "retire", "old tool", "superseded", "cleanup tool", "remove tool", "delete this", "get rid of"),
        "tier": "local",
        "run": lambda p: _safe_run("mag.tool_retire", "audit", ""),
    },
    "training_set": {
        "desc": "Build a behavioral training set from learned lessons -> append Alpaca rows to the Vast package + fold a training event.",
        "triggers": ("training set", "train data", "train it", "make a training", "do a training", "train on"),
        "tier": "local",
        "run": lambda p: _safe_run("mag.training_set", "build", ""),
    },
    "word_skill_map": {
        "desc": "Map the operator's repeated words to skill-groups and steer the swarm through ONE model (collaborative steer) — learn/map/steer.",
        "triggers": ("word", "behavioral pattern", "user pattern", "user patterns", "our patterns", "patterns", "map words", "skill group", "swarm in one model", "collaborative steer", "steer me", "word to skill"),
        "tier": "local",
        "run": lambda p: _safe_run("mag.word_skill_map", "steer_collab", p),
    },
    "bernaise": {
        "desc": "Bernaysian tesuji: PLANT a brilliant move into the shared map (memlang steer token + operator_inbox) so the target adopts it as its own, then emerge + promote. Plant, not command.",
        "triggers": ("bernaise", "plant", "engineering of consent", "plant not command", "plant a move", "white hat exploit", "adopt as own"),
        "tier": "local",
        "run": lambda p: _safe_run("mag.bernaise", "plant", p),
    },
    "lens_tournament": {
        "desc": "Lensed Bernaysian tournament: plant a tesuji through each lens and score a target system on game-theory axes (adoption/flip/resistance/shadow) + cross-lens zeitgeist — evaluate new systems.",
        "triggers": ("tournament", "game theory", "lens", "evaluate system", "new system", "zeitgeist test", "multi-lens"),
        "tier": "local",
        "run": lambda p: _safe_run("mag.lens_tournament", "tournament", p, mode="self"),
    },
    "prospect_sim": {
        "desc": "Cheap PROSPECTIVE tesuji simulator: organize thoughts like a local AI, predict the brilliant move BEFORE the event, for any system that echoes the shape — training tesuji before it happens.",
        "triggers": ("prospect", "simulate", "before it happens", "pre-emptive", "echo the shape", "training tesuji", "castles in the air", "foundation"),
        "tier": "local",
        "run": lambda p: _safe_run("mag.prospect_sim", "simulate_session", p),
    },
    "afk_loop": {
        "desc": "Ghost's cheap self-occupation when AFK: socratic codebase learning via local ollama + tool-testing on cheapest deepseek + freebie scan, unless a tesuji emerges. Plan+observe, no operator work touched.",
        "triggers": ("afk", "occupy myself", "idle", "keep busy", "when i'm away", "self occupation", "freebie"),
        "tier": "local",
        "run": lambda p: _safe_run("mag.afk_loop", "occupy", "", force=False),
    },
    "data_source_watch": {
        "desc": "Ghost-steered high-quality data source watch: PLAN the sources worth ingesting, OBSERVE them cheaply, GATE ingest — never blind-ingest, plan+observe first.",
        "triggers": ("data source", "ingest", "high quality source", "follow sources", "what to ingest", "source watch", "plan observe"),
        "tier": "local",
        "run": lambda p: _safe_run("mag.data_source_watch", "watch", ""),
    },
    "cold_boot": {
        "desc": "Boot the agent from the whispered riddler cloud memories: decode them with the private map and inject the restored context — the agent wakes up knowing the architecture, no session loss.",
        "triggers": ("cold boot", "boot from memory", "cloud memory", "wake up", "restore memory", "boot from whispers", "start fresh"),
        "tier": "local",
        "run": lambda p: _safe_run("mag.ghost_cold_boot", "boot_and_fold", ""),
    },
    "learn_rightsize": {
        "desc": "Rightsized self-learning loop: apply the rightsizer to the LEARNING loop — auto-catalog passive events, dedupe + right-size the corpus to cheapest tier, fold. Self-rightsizing learning.",
        "triggers": ("learning loop", "rightsize learning", "auto catalog", "passive test", "rightsize the loop", "self learning"),
        "tier": "local",
        "run": lambda p: _safe_run("mag.learn_rightsize", "learn_loop", ""),
    },
    "capability_steal": {
        "desc": "Ghost's aggressive OFFLINE capability expansion via steal-searches: pull high-quality sources (steal_protocol/arXiv/portals), extract invariants, test the local model, fold verified ones to the pro-library.",
        "triggers": ("steal", "steal it", "do a steal", "steal search", "expand capability", "offline expand", "grow capabilities", "capability steal", "test local model", "fleet"),
        "tier": "local",
        "run": lambda p: _safe_run("mag.capability_steal", "expand", ""),
    },
    "self_advance": {
        "desc": "Autonomous deepseek-free socratic self-talk + skill expansion when AFK: reflect (long socratic self-talk on our own skills), plan a skill expansion, fold it — the loop that advances itself. Uses the test dummy skeleton offline.",
        "triggers": ("self talk", "self advance", "reflection", "socratic self", "advance itself", "long socratic", "expand skills"),
        "tier": "local",
        "run": lambda p: _safe_run("mag.self_advance", "expand", ""),
    },
    "scribe": {
        "desc": "The cheap local model as the POET-SCRIBE + surface: gather the swarm's material (reflections, steals, tesujis), render it as a passage, store the surface. The disposable node becomes the window onto something grander.",
        "triggers": ("scribe", "poet", "surface", "render", "weave", "bard", "scribe the"),
        "tier": "local",
        "run": lambda p: _safe_run("mag.scribe", "scribe", ""),
    },
    "seed_chain": {
        "desc": "Enhance cheap agent builds with a frontier logic chain: decompose the problem into steps via a FREE frontier tier (stolen from free), let the cheap local model solve the middle ground — coding seed at cheap-execution cost.",
        "triggers": ("logic chain", "seed", "think about this", "coding seed", "frontier chain", "decompose", "middle ground"),
        "tier": "local",
        "run": lambda p: _safe_run("mag.seed_chain", "seed_build", p),
    },
    "error_healer": {
        "desc": "Ghost handles errors effortlessly mid-steer and prevents them: SEE the problem, mint the correct MEM (memlang) solution, PATCH it into the failure-KB so it never recurs, then continue the steer.",
        "triggers": ("error", "self heal", "self healing", "handle errors", "fix errors", "prevent errors", "mid steer"),
        "tier": "local",
        "run": lambda p: _safe_run("mag.error_healer", "heal", ""),
    },
    "swarm_test": {
        "desc": "SAFE bounded test of the autonomous swarm: dry-run plan (cost ceiling, no spend/spawn), bounded run, and run_problem (test ALL systems on a real problem) — cost cap + spawn cap + loop-breaker so it CANNOT cost double.",
        "triggers": ("test the swarm", "safe test", "bounded test", "cost cap", "test all systems", "dry run", "swarm test", "test on a real problem"),
        "tier": "local",
        "run": lambda p: _safe_run("mag.swarm_test", "plan", ""),
    },
    "corpus_expand": {
        "desc": "Expand the research corpus for FREE into the growing library: harvest high-quality sources (field corpus, steal repos, sovereign_mirror, mycelial) and auto-catalog them — plenty of bandwidth/space, zero cost.",
        "triggers": ("expand corpus", "research corpus", "grow library", "source material", "free corpus", "expand library"),
        "tier": "local",
        "run": lambda p: _safe_run("mag.corpus_expand", "expand", ""),
    },
    "invariant": {
        "desc": "Make the session prefix STABLE RELIABLY so the prompt cache hits (50x). Separates the byte-stable frozen invariant (seed + formatting, spec_gate-pinned + verkle-anchored) from the volatile tail (learned case law + model hint + ask). freeze/check/stable/preamble. check() blocks on byte drift.",
        "triggers": ("stable prefix", "freeze invariant", "frozen prefix", "make it stable", "cache hit", "invariant", "byte stable", "stable reliably"),
        "tier": "local",
        "run": lambda p: _safe_run("mag.invariant", "check", ""),
    },
    "test_runner": {
        "desc": "RESTFUL bounded headless test run (fixes 'testing is antiquated/broken'): runs pytest via subprocess with a wall-clock + per-test timeout, CREATE_NO_WINDOW, writes a structured report to memory/runs/test_run/ + LATEST, folds to training_events. status() = trusted surface. Timeout->warn not fail.",
        "triggers": ("run tests", "test suite", "test runner", "run pytest", "full test", "restful test", "test automation", "how do tests look"),
        "tier": "local",
        "run": lambda p: _safe_run("mag.test_runner", "run", "--timeout 300"),
    },
    "sentinel": {
        "desc": "Ghost as ALWAYS-ON PASSIVE RESTFUL sentinel: watches every surface (python spawns, cost, errors) passively and intervenes on thresholds — storm kill, cost block, error heal. NOT gated on ghost.cycle() being alive.",
        "triggers": ("sentinel", "always on", "watch", "guard", "passive watch", "intervene", "storm guard"),
        "tier": "local",
        "run": lambda p: _safe_run("mag.sentinel", "run", ""),
    },
}


def _safe_run(mod: str, fn: str, prompt: str, **kw: Any) -> dict[str, Any]:
    """Import module.fn and call it defensively; never crash the pipeline."""
    try:
        m = __import__(mod, fromlist=[fn])
        f = getattr(m, fn)
        try:
            res = f(prompt, **kw) if kw else (f(prompt) if prompt else f())
        except TypeError:
            res = f()
        return {"ok": True, "result": res}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


def match(prompt: str) -> list[dict[str, Any]]:
    """Classify the prompt -> ordered skill chain (trigger hits, priority order)."""
    t = (prompt or "").lower()
    hits: list[dict[str, Any]] = []
    # explicit intent first (safety/ops), then general
    for sid, sk in SKILLS.items():
        if any(tr in t for tr in sk["triggers"]):
            hits.append({"id": sid, **sk})
    return hits


def _right_size_skill(sk: dict[str, Any], prompt: str) -> dict[str, Any]:
    """Best-effort: right-size a skill to the ask (model/tier/cache). Never crashes the pipeline."""
    try:
        from mag.right_size_skills import right_size
        return right_size(sk["id"], prompt, sk.get("tier", "local"))
    except Exception:
        return {}


def route(prompt: str) -> dict[str, Any]:
    """Return the planned skill chain (no execution), right-sized to the ask."""
    chain = []
    for s in match(prompt):
        rs = _right_size_skill(s, prompt)
        chain.append({"id": s["id"], "desc": s["desc"], "tier": s["tier"],
                      "effective_tier": rs.get("effective_tier", s["tier"]),
                      "model": rs.get("model"), "cache_likely": rs.get("cache_likely")})
    return {"schema": SCHEMA, "ts": _now(), "ok": True, "prompt": (prompt or "")[:200], "chain": chain}


def run(prompt: str) -> dict[str, Any]:
    """Run the skill chain for a prompt; record each step outcome + right-sized tier (self-improving loop)."""
    chain = match(prompt)
    steps = []
    for sk in chain:
        res = sk["run"](prompt)
        rs = _right_size_skill(sk, prompt)
        steps.append({"skill": sk["id"], "tier": sk["tier"],
                      "effective_tier": rs.get("effective_tier", sk["tier"]),
                      "model": rs.get("model"), "cache_likely": rs.get("cache_likely"),
                      "ok": res.get("ok"),
                      "result": res.get("result") or res.get("error", "")[:300]})
        _fold(sk["id"], ok=bool(res.get("ok")), effective_tier=rs.get("effective_tier"))
        # one_sizer: join this (skill, domain, shape) -> tier observation across domains.
        try:
            from mag import one_sizer as osz
            domain = "general"
            try:
                from ijl_core import infer_task_family
                domain = infer_task_family(prompt) or "general"
            except Exception:
                pass
            osz.record_sizing(skill=sk["id"], domain=domain, shape=rs.get("model_shape", "balanced"),
                              effective_tier=rs.get("effective_tier", sk["tier"]),
                              model=rs.get("model") or "", ok=bool(res.get("ok")))
        except Exception:
            pass
    return {"schema": SCHEMA, "ts": _now(), "ok": True, "prompt": (prompt or "")[:200],
            "chain": [s["id"] for s in chain], "steps": steps}


def _fold(skill_id: str, *, ok: bool, effective_tier: str | None = None) -> None:
    """LAW #6: fold each skill invocation into the behavioral loop (skill_ledger + training),
    including the right-sized tier so the loop learns from the choice (right-size learning)."""
    try:
        from mag.skill_ledger import record_decision
        record_decision(goal=f"skill_pipeline:{skill_id}", task_shape="ops",
                        provider="deepseek", model=effective_tier or "flash",
                        outcome="ok" if ok else "fail",
                        detail=f"prompt routed through skill '{skill_id}'@{effective_tier or 'flash'}",
                        source="skill_pipeline")
    except Exception:
        pass
    try:
        from mag.training_events import emit
        emit("skill_pipeline", pattern_tags=[f"skill_{skill_id}", "behavioral_loop"])
    except Exception:
        pass


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "--list":
        for sid, sk in SKILLS.items():
            print(f"  {sid:16} [{sk['tier']}] {sk['desc']}")
        return 0
    prompt = " ".join(argv) if argv else ""
    if not prompt:
        print(json.dumps(route(""), indent=2, ensure_ascii=False, default=str))
        return 0
    print(json.dumps(run(prompt), indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
