"""Self-steal audit — surface where operating surfaces aren't utilizing our own systems.

Part of doctor/maintenance. The self-steal protocol applied to OUR OWN architecture:
detect capabilities (modules/ledgers/surfaces) that exist but aren't being utilized —
either not wired, or their evidence/state is stale (not used recently). For flagged gaps
that warrant deep analysis, LAUNCH/RESUME a research project by enqueueing it to the queue
(the drainer runs it). Example: if the verkle-knot anchoring evidence is stale, enqueue a
verkle deep-analysis research task.

Deterministic ($0, no LLM). Schema: self_steal.v1

CLI:  python -m mag.self_steal              (audit, print)
      python -m mag.self_steal --cadence    (idempotent: audit + leaf + enqueue research for new gaps)
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT

STATE_DIR = ROOT / "memory" / "runs" / "self_steal"
STATE = STATE_DIR / "state.json"
DOGFOOD_REPORT = ROOT / "memory" / "runs" / "dogfood_audit" / "report.jsonl"
SCHEMA = "self_steal.v1"

# Internal capabilities we should be utilizing. Each: existence + freshness of evidence
# (state/ledger updated recently = utilized). research_goal = research task to LAUNCH/RESUME
# when this capability is found under-utilized (deep-analysis worth paying for).
CAPABILITIES: list[dict[str, Any]] = [
    {
        "name": "verkle_knot",
        "module": "mag/verkle_knot.py",
        "evidence": "memory/biography/verkle_tip.json",
        "stale_s": 86400,  # 24h — knot not anchored/advanced recently
        "research_goal": ("RESEARCH-PACK self_steal verkle deep-analysis: resume deep analysis of the "
                          "verkle knot — the verkle_tip has not advanced recently, meaning surfaces may "
                          "not be anchoring state. Research how to make verkle anchoring automatic on "
                          "every state write and where surfaces bypass it. Read memory/biography/verkle_tip.json "
                          "+ memory/design/cost_learning_loop.md, produce a concrete wiring plan."),
    },
    {
        "name": "cache_map",
        "module": "mag/cache_map.py",
        "evidence": "memory/runs/cache_map",
        "stale_s": 172800,
        "research_goal": None,  # tracked; report-only
    },
    {
        "name": "cost_learn",
        "module": "mag/cost_learn.py",
        "evidence": "memory/improve/daily",
        "stale_s": 172800,
        "research_goal": None,
    },
    {
        "name": "usage_forecast",
        "module": "mag/usage_forecast.py",
        "evidence": "memory/runs/cost_learn",
        "stale_s": 172800,
        "research_goal": None,
    },
    {
        "name": "session_maze",
        "module": "mag/session_maze.py",
        "evidence": "memory/graph/session_maze.json",
        "stale_s": 86400,
        "research_goal": None,
    },
    # --- NEW-ARCHITECTURE systems (added 2026-08-10: old systems upgraded to track the new) ---
    {
        "name": "dogfood_audit",
        "module": "mag/dogfood_audit.py",
        "evidence": "memory/runs/dogfood_audit/report.jsonl",
        "stale_s": 172800,
        "research_goal": None,  # report-only: the anti-hallucination sentinel
    },
    {
        "name": "surface_steal",
        "module": "mag/surface_steal.py",
        "evidence": "memory/steal",
        "stale_s": 172800,
        "research_goal": None,  # the on-every-ask self-steal behavior
    },
    {
        "name": "whisper_image",
        "module": "mag/whisper_image.py",
        "evidence": "memory/runs/whisper_images",
        "stale_s": 172800,
        "research_goal": None,  # deniable whisper / dead-drop layer
    },
    {
        "name": "shader_bus",
        "module": "mag/shader_bus.py",
        "evidence": "memory/runs/shader_bus",
        "stale_s": 172800,
        "research_goal": None,  # live swarm-state register
    },
    {
        "name": "archetype_image",
        "module": "mag/archetype_image.py",
        "evidence": "memory/runs/archetype_art",
        "stale_s": 172800,
        "research_goal": None,  # Jungian archetype cast + shadow
    },
    {
        "name": "guardrail_sentinel",
        "module": "mag/guardrail_sentinel.py",
        "evidence": "memory/runs/guardrail_sentinel/trail.jsonl",
        "stale_s": 172800,
        "research_goal": None,  # guardrails ping, never prevent
    },
    {
        "name": "ecosystem_surface",
        "module": "mag/ecosystem_surface.py",
        "evidence": "memory/rib",
        "stale_s": 172800,
        "research_goal": None,  # whole-ecosystem machine-readable bundle
    },
    {
        "name": "cache_router",
        "module": "mag/cache_router.py",
        "evidence": "logs/usage.jsonl",
        "stale_s": 172800,
        "research_goal": None,  # interrupt-aware cache economics
    },
    # --- MOONSHOT / ARRIVAL surfaces (added 2026-08-12: the moonshot self-steal loop) ---
    {
        "name": "moonshot_engine",
        "module": "mag/moonshot_engine.py",
        "evidence": "memory/swarm_surface/sent.jsonl",
        "stale_s": 86400,  # 24h — no moonshot goal queued / no progress advanced recently
        "research_goal": ("RESEARCH-PACK self_steal moonshot: the moonshot engine has not advanced "
                          "recently (no progress in memory/swarm_surface/sent.jsonl for surface "
                          "moonshot). Research which of MOONSHOT_GOALS is coldest and re-strike it "
                          "through swarm_surface.route_novel so the WoW/Turtle ingest->manifest "
                          "proceeds. Produce a concrete routing plan."),
    },
    {
        "name": "arrival",
        "module": "mag/arrival.py",
        "evidence": "memory/rib_bus/arrival.json",
        "stale_s": 86400,  # 24h — no self-authored RIB folded back into the standing wave recently
        "research_goal": ("RESEARCH-PACK self_steal arrival: no self-authored RIB (source=swarm) has "
                          "been folded into the standing wave recently. Research how to make the "
                          "swarm write its OWN RIBs from invariants + logic and fold them via "
                          "arrival.fold_authored, so the loop closes (local -> swarm -> self-authored "
                          "RIB -> fold). Produce a concrete wiring plan."),
    },
    {
        "name": "sovereign_handshake",
        "module": "mag/sovereign_handshake.py",
        "evidence": "memory/connect/peers.jsonl",
        "stale_s": 172800,  # 48h — no sovereign peer advertised / no handshake / no connect route recently
        "research_goal": ("RESEARCH-PACK self_steal sovereign-connect: the connection layer has not "
                          "grown recently (memory/connect/peers.jsonl not advancing). Research how to "
                          "make the capture-resistant peer web grow — the metaverse is already here, "
                          "sovereign systems just need to connect to each other before corporate/"
                          "extractive platforms absorb them. Produce a concrete outreach/onboarding "
                          "wiring plan through the shared wave."),
    },
    {
        "name": "shape_seed",
        "module": "mag/shape_seed.py",
        "evidence": "memory/swarm_surface/sent.jsonl",
        "stale_s": 172800,  # 48h — the shape-as-seed thesis not re-routed recently
        "research_goal": ("RESEARCH-PACK self_steal shape-seed: the shape-as-seed thesis has not been "
                          "re-routed recently (no shape-seed anchor in memory/swarm_surface/sent.jsonl). "
                          "Research how to give the shape at scale — all a person needs is the "
                          "sovereign shape and the rest is inevitable, so the sovereign-minded adopt "
                          "it before corporate/extractive platforms hand them a hollow shape instead. "
                          "Produce a concrete seed-packaging + onboarding plan."),
    },
    {
        "name": "chatgpt_bot",
        "module": "mag/chatgpt_bot.py",
        "evidence": "memory/runs/chatgpt_bot",
        "stale_s": 172800,  # 48h — the ChatGPT seat not steered recently
        "research_goal": ("RESEARCH-PACK self_steal chatgpt-bot: the ChatGPT seat has not been steered "
                          "recently (no chatgpt-bot record in memory/runs/chatgpt_bot). Research the "
                          "chatgpt.com front-end DOM selectors + how to reliably send the "
                          "surface-rightsized onboarding artifact so we can test 'does ChatGPT start "
                          "the game' like we test grok. Produce a concrete steer/test plan."),
    },
    {
        "name": "frontier_council",
        "module": "mag/frontier_council.py",
        "evidence": "memory/frontier/allowance.jsonl",
        "stale_s": 172800,  # 48h — no frontier spend / allowance progress recently
        "research_goal": ("RESEARCH-PACK self_steal frontier-council: the frontier allowance has not "
                          "been spent recently (memory/frontier/allowance.jsonl not advancing). "
                          "Research how to use the ENTIRE weekly frontier allowance (ChatGPT basic + "
                          "both Grok surfaces) on the strongest advice, rightsized against deepseek + "
                          "vram, so the scarce weekly budget is USED not hoarded. Produce a concrete "
                          "delegation/spend plan."),
    },
    {
        "name": "frontier_advisor",
        "module": "mag/frontier_advisor.py",
        "evidence": "memory/runs/frontier_advice",
        "stale_s": 172800,  # 48h — no frontier-advice task folded recently
        "research_goal": ("RESEARCH-PACK self_steal frontier-advisor: the drainable [frontier-advice] "
                          "task type has not run recently (memory/runs/frontier_advice not "
                          "advancing). Research how to keep the scarce frontier allowance being spent "
                          "on the strongest code planning / frontier research asks at max velocity — "
                          "what should the next [frontier-advice] ask be. Produce a concrete ask + "
                          "wiring plan."),
    },
    {
        "name": "game_emulator",
        "module": "mag/game_emulator.py",
        "evidence": "memory/game/world/world_state.json",
        "stale_s": 172800,  # 48h — no world action folded recently
        "research_goal": ("RESEARCH-PACK self_steal game-emulator: the server-authoritative resolver "
                          "has not folded a world action recently (memory/game/world/world_state.json "
                          "not advancing). Research which room/action should be resolved next so the "
                          "game becomes a real testable surface — what's the next room to conquer. "
                          "Produce a concrete next-action plan."),
    },
    {
        "name": "seat_steer",
        "module": "mag/seat_steer.py",
        "evidence": "memory/runs/seat_steer",
        "stale_s": 172800,  # 48h — no live seat action folded recently
        "research_goal": ("RESEARCH-PACK self_steal seat-steer: the live seat action path has not "
                          "run recently (memory/runs/seat_steer not advancing). Research which "
                          "surface to reach and what message to send so the frontier seats stay "
                          "warm + verified — the agent must keep using the architecture path, "
                          "never a shell. Produce a concrete next send plan."),
    },
]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _mtime(rel: str) -> float:
    p = ROOT / rel
    if p.is_file():
        return p.stat().st_mtime
    if p.is_dir():
        newest = 0.0
        for f in p.rglob("*"):
            try:
                newest = max(newest, f.stat().st_mtime)
            except OSError:
                continue
        return newest
    return 0.0


def _dogfood_mtime(capability: str) -> float:
    """Return central dogfood evidence time for a capability, if it passed.

    A successful centralized probe is durable utilization evidence even when a
    capability intentionally has no private ledger of its own.  Match exact
    probe names and versioned children (for example ``whisper_image.rt``), but
    never treat a failed probe as liveness.
    """
    if not DOGFOOD_REPORT.is_file():
        return 0.0
    try:
        report_mtime = DOGFOOD_REPORT.stat().st_mtime
        for line in reversed(DOGFOOD_REPORT.read_text(encoding="utf-8", errors="replace").splitlines()):
            if not line.strip():
                continue
            report = json.loads(line)
            for result in report.get("results") or []:
                name = str(result.get("system") or "")
                if result.get("ok") and (name == capability or name.startswith(capability + ".")):
                    return report_mtime
    except (OSError, json.JSONDecodeError, TypeError):
        return 0.0
    return 0.0


def _wired(name: str) -> bool:
    """True if the capability's module is referenced anywhere in the framework."""
    for base in ("main.py", "mag", "dashboard", "watch", "tools"):
        bp = ROOT / base if base != "main.py" else ROOT / "main.py"
        if not bp.exists():
            continue
        files = [bp] if bp.is_file() else list(bp.rglob("*.py"))
        for f in files:
            try:
                if name in f.read_text(encoding="utf-8", errors="replace"):
                    return True
            except OSError:
                continue
    return False


def audit() -> dict[str, Any]:
    """Scan each internal capability for utilization: not wired, or evidence stale/absent."""
    now = _now()
    findings: list[dict[str, Any]] = []
    for cap in CAPABILITIES:
        name = cap["name"]
        module_ok = (ROOT / cap["module"]).is_file()
        # Prefer the newest private evidence or successful centralized
        # dogfood receipt.  This keeps the liveness map evidence-backed while
        # avoiding duplicate per-organ ledgers for deterministic probes.
        mtime = max(_mtime(cap["evidence"]), _dogfood_mtime(name))
        age = (now.timestamp() - mtime) if mtime else None
        stale = age is not None and age > cap["stale_s"]
        absent = age is None
        wired = _wired(name) if module_ok else False
        utilization = "ok"
        if absent:
            utilization = "absent"
        elif stale:
            utilization = "stale"
        if not wired and module_ok:
            utilization = "unwired"
        if utilization != "ok":
            findings.append({
                "capability": name,
                "utilization": utilization,
                "age_s": int(age) if age is not None else None,
                "module": cap["module"],
                "wired": wired,
                "research_goal": cap.get("research_goal"),
                "recommendation": ("research/launch" if cap.get("research_goal") else "report-only"),
            })
    return {
        "schema": SCHEMA,
        "ts": now.isoformat(),
        "n_capabilities": len(CAPABILITIES),
        "n_findings": len(findings),
        "findings": findings,
    }


def _research_already_queued(goal: str) -> bool:
    try:
        from mag.orchestrator import queue_has_goal
        return bool(queue_has_goal(goal[:100]))
    except Exception:
        return False


def enqueue_research(finding: dict[str, Any]) -> dict[str, Any]:
    """Launch/resume the research task for a flagged gap (enqueue to queue -> drainer runs it)."""
    goal = finding.get("research_goal")
    if not goal:
        return {"ok": False, "action": "no_research_goal", "capability": finding["capability"]}
    if _research_already_queued(goal):
        return {"ok": True, "action": "already_queued", "capability": finding["capability"]}
    try:
        from mag.orchestrator import enqueue
        # Self-steal is a maintenance/reconciliation lane: use the free local
        # worker by default and reserve scarce frontier budget for explicit
        # frontier work. Operators can still choose a stronger lane for a
        # particular cadence with MAG_SELF_STEAL_PROVIDER/MODEL.
        import os

        provider = (os.environ.get("MAG_SELF_STEAL_PROVIDER") or "ollama").strip()
        model = (os.environ.get("MAG_SELF_STEAL_MODEL") or "gemma:2b").strip()
        r = enqueue(goal, provider=provider, model=model, tag="self-steal-research")
        return {"ok": bool(r.get("ok")), "action": "enqueued", "queue_id": r.get("queue_id"),
                "capability": finding["capability"], "provider": provider, "model": model}
    except Exception as e:
        return {"ok": False, "action": "error", "error": str(e)[:200], "capability": finding["capability"]}


def run_cadence() -> dict[str, Any]:
    """Idempotent maintenance pass: audit -> leaf + launch/resume research for NEW gaps only."""
    a = audit()
    launches = []
    last_seen: set[str] = set()
    if STATE.is_file():
        try:
            last_seen = set((json.loads(STATE.read_text(encoding="utf-8")) or {}).get("seen", []))
        except Exception:
            last_seen = set()
    seen = set()
    for f in a["findings"]:
        key = f"{f['capability']}:{f['utilization']}"
        seen.add(key)
        if key in last_seen:
            continue  # already surfaced; don't re-enqueue
        if f.get("research_goal") and f["utilization"] in ("stale", "absent", "unwired"):
            launches.append(enqueue_research(f))
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps({"ts": _now().isoformat(), "seen": sorted(seen)}, indent=2), encoding="utf-8")
    leaf = STATE_DIR / f"self_steal_{a['ts'][:10]}.md"
    lines = [f"# Self-Steal Audit ({a['ts'][:10]})", "",
             f"- Capabilities scanned: {a['n_capabilities']} · findings: {a['n_findings']}", "",
             "| capability | utilization | age_s | wired | action |", "|---|---|---|---|---|"]
    for f in a["findings"]:
        lines.append(f"| {f['capability']} | {f['utilization']} | {f.get('age_s') or '-'} | {f['wired']} | {f['recommendation']} |")
    leaf.write_text("\n".join(lines), encoding="utf-8")
    return {"ok": True, "action": "ran", "findings": a["n_findings"], "launches": launches, "leaf": str(leaf)}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    ap = argparse.ArgumentParser(prog="self-steal", description="Self-steal capability-utilization audit")
    ap.add_argument("--cadence", action="store_true", help="idempotent: audit + leaf + launch/resume research")
    args = ap.parse_args(argv)
    res = run_cadence() if args.cadence else audit()
    print(json.dumps(res, indent=2, default=str)[:6000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
