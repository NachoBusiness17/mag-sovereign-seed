"""autonomous_research — run the RIB-driven cold-edge research loop HEADLESS.

The operator (2026-08-12): "how do we not crash vs code can you do all of this headless and just
go" — the loop must run DETACHED from VS Code, in a separate headless process (CREATE_NO_WINDOW),
never in the chat execution.

THE DESIGN (architecture-native, headless):
  VS Code only ENQUEUES. The heavy work runs in the k8s swarm worker (in-cluster, headless) or a
  detached local process via mag.headless. Neither touches VS Code, neither pops a window.
  1. plan() — enqueue each cold-edge research goal via swarm_worker.enqueue_task (stateless,
     content-addressed queue; k8s worker drains headless next pass). Deterministic, $0.
  2. The worker runs the RIB-driven research (own fetch surface: research_pack._fetch_url) and
     returns a result file.
  3. fold() — read completed swarm results and fold the steals to repo memory + rib_bus.

Routing law: fetch uses OUR OWN surface (research_pack._fetch_url), never the generic fetch tool.
No-window law: every spawn uses mag.headless (CREATE_NO_WINDOW). Guarded — never breaks the cadence.

Schema: autonomous_research.v1 · deterministic + $0 · reuse: swarm_worker, research_pack, rib_bus.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCHEMA = "autonomous_research.v1"

# The cold edges still open for research (the frontier). n_planning_mode = built (plan.py);
# n_3254150770 + n_1dabc36677 = researched this session. Remaining loop targets:
COLD_EDGES = [
    {
        "edge": "n_49740ba140",
        "title": "grok free compounding",
        "goal": "RIB-driven research: does consumer/free-tier AI compounding (persistent agents "
                "earning capability over time) exist as a real pattern? Find the ONE mechanism "
                "worth stealing and the ONE invariant it implies for our free-tier front line.",
    },
    {
        "edge": "n_717f3ba254",
        "title": "free project bones / idea graph",
        "goal": "RIB-driven research: open_loop idea nodes / backlog-as-living-structure / "
                "idea-graph agent patterns. Find the ONE mechanism worth stealing for our "
                "open_loop idea graph and the ONE invariant.",
    },
]

# RIB doctrine that drives the research behavior (injected into each task).
_DOCTRINE = (
    "Hold the invariants: aim at the coldest vertex (neglected core = future-proof frontier); "
    "steal-and-adapt (contracts only, no wholesale copy); one knot at a time; the nod is mine. "
    "Return ONE steal + ONE invariant. Fetch via our own surface only."
)

# OVERNIGHT SWARM batch — RIB-driven goals across the cold edges + the open frontier. Each is
# routed via swarm_surface.route_novel (dedupe by anchor + enqueue to the swarm research queue ->
# k8s worker drains HEADLESS in-cluster all night). Intent-rightsized: research -> swarm/4/cheap,
# frontier -> coldest seam premium.
_OVERNIGHT_GOALS = [
    # ── cold edges (research intent -> swarm/4/cheap) ─────────────────────
    {"goal": "RIB-driven research: subagent-router — the ONE subagent-routing mechanism worth "
             "stealing across Claude Code/Cursor/agentswarm/OpenAI, mapped to our router.py+dispatch.",
     "intent": "research"},
    {"goal": "RIB-driven research: relational/episodic agent memory — the ONE mechanism worth "
             "stealing (Mem0/Letta/SubtleMemory) mapped to our verkle chain + memlance.",
     "intent": "research"},
    {"goal": "RIB-driven research: free-tier AI compounding — the ONE mechanism by which "
             "persistent agents earn capability over time, mapped to our free-tier front line.",
     "intent": "research"},
    {"goal": "RIB-driven research: open_loop idea-graph / backlog-as-living-structure — the ONE "
             "mechanism worth stealing for our idea graph, mapped to our open_loop nodes.",
     "intent": "research"},
    {"goal": "RIB-driven research: clarify-before-dispatch / intent-gating — the ONE gating "
             "mechanism worth stealing, mapped to our existing mag/plan.py planning gate.",
     "intent": "research"},
    # ── frontier synthesis (frontier intent -> coldest seam, premium) ────
    {"goal": "DEEP SYNTHESIS moonshot: the coldest vertex that, if connected, re-weights the "
             "entire sovereign-agent architecture — name it and the knot to place.",
     "intent": "frontier"},
    {"goal": "DEEP SYNTHESIS moonshot: cross-modal invariant (time-lens x space-lens) as a general "
             "method — formalize 'the coldest point is the withheld connection' as a reusable law.",
     "intent": "frontier"},
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def plan(*, enqueue: bool = True, domain: str = "research") -> dict[str, Any]:
    """Enqueue each open cold-edge research goal to the swarm queue (headless drain in-cluster).

    This is the 'just go' entry: VS Code enqueues, the k8s worker runs headless, results return
    to be folded. Deterministic, $0. enqueue=False = dry plan.
    """
    from mag import swarm_worker

    out = []
    for item in COLD_EDGES:
        goal = item["goal"] + "\n" + _DOCTRINE
        if enqueue:
            r = swarm_worker.enqueue_task(goal, provider="deepseek", domain=domain,
                                          tag=f"cold_edge:{item['edge']}")
            out.append({"edge": item["edge"], "title": item["title"],
                        "task_id": r.get("task_id"), "ok": r.get("ok"),
                        "queue": r.get("queue")})
        else:
            out.append({"edge": item["edge"], "title": item["title"],
                        "ok": True, "dry": True, "goal_len": len(goal)})
    return {"ok": True, "schema": SCHEMA, "enqueue": enqueue, "enqueued": out}


def status() -> dict[str, Any]:
    """Read the swarm queue for our cold-edge tasks (queued/running/done) — the return channel."""
    from mag import swarm_worker
    tasks = []
    qdir = Path(getattr(swarm_worker, "QUEUE_DIR", ""))
    if qdir.is_dir():
        for p in sorted(qdir.glob("sw-*.json")):
            try:
                t = json.loads(p.read_text(encoding="utf-8"))
                if t.get("tag", "").startswith("cold_edge:"):
                    tasks.append({"task_id": t.get("task_id"), "edge": t.get("tag"),
                                  "status": t.get("status"), "detail": (t.get("detail") or "")[:200]})
            except Exception:
                continue
    return {"ok": True, "schema": SCHEMA, "n_tasks": len(tasks), "tasks": tasks}


def spawn_overnight(*, enqueue: bool = True, domain: str = "research") -> dict[str, Any]:
    """Spawn the OVERNIGHT SWARM: route the RIB-driven goal batch through swarm_surface.route_novel.

    route_novel = THE one primitive (dedupe by content anchor + enqueue to the swarm research queue
    -> k8s worker drains HEADLESS in-cluster). Idempotent, so the cadence can call this every pass
    without duplicating. Intent-rightsized via intent_rightsize (research -> swarm/4/cheap, frontier
    -> coldest seam). enqueue=False = dry plan.

    This is the 'make it worthwhile' entry: VS Code enqueues a batch, the cloud swarm drains it all
    night headless, and results return to be folded.
    """
    from mag import swarm_surface
    from mag import intent_rightsize
    from mag import steer_swarm

    out = []
    for item in _OVERNIGHT_GOALS:
        # each goal becomes a SELF-TESTING ask: mounted doctrine + acceptance RIB (complex behavior
        # test inside the ask, via steer_swarm.testable_ask)
        ta = steer_swarm.testable_ask(item["goal"], domain=domain)
        goal = ta["ask"]
        sz = intent_rightsize.rightsize(goal, intent=item["intent"])
        if enqueue:
            r = swarm_surface.route_novel(goal, surface="autonomous_research",
                                          lens=item["intent"], domain=domain)
            out.append({"intent": item["intent"], "ok": r.get("ok"),
                        "deduped": r.get("deduped"), "anchor": r.get("anchor", "")[:12],
                        "task_id": r.get("task_id", ""),
                        "rightsized": sz.get("profile") or sz.get("intent")})
        else:
            out.append({"intent": item["intent"], "ok": True, "deduped": False, "dry": True,
                        "goal_len": len(goal),
                        "rightsized": sz.get("profile") or sz.get("intent")})
    n_new = sum(1 for o in out if not o.get("deduped"))
    return {"ok": True, "schema": SCHEMA, "enqueue": enqueue,
            "n_goals": len(out), "n_new": n_new, "swarm": out}


# WOW-CLONE INSTRUCTION SWARM — free build instructions for our self-hosted WoW-style emulator
# clone on k8s (the castle-in-the-sky foundation). Each goal routed via swarm_surface.route_novel.
_WOW_DOCTRINE = (
    "RIB doctrine: aim at the coldest vertex; steal-and-adapt (contracts only, no wholesale copy); "
    "one knot at a time; the nod is mine. Goal: FREE code instructions to build OUR self-hosted "
    "WoW-style emulator clone on k8s. Return concrete build instructions + the ONE steal."
)
_WOW_GOALS = [
    "WoW MMO emulator stack: MaNGOS/TrinityCore/CMaNGOS architecture, client-server split, DB "
    "schema (world/characters/realmd), self-host setup steps, free license.",
    "Open-source WoW server code instructions: stand up a private server-authoritative world from "
    "source, build steps, config, tools. Map to our k8s swarm as the emulator.",
    "Emulator on k8s: run the server-authoritative world on a k8s swarm (state PVC, stateless "
    "workers re-render, replayable opcodes). Map to our verkle chain as the protocol.",
    "RIB-as-mod system: how WoW addons (FrameXML, hooks, saved variables) map to our RIB "
    "instruction layer and rib_bus.mount. Get the mod system code instructions.",
    "Free + legal: how to build a WoW-style clone legally from open-source (not proprietary "
    "assets) - the ONE licensing/legal constraint that gates building our clone for free.",
]


def wow_clone_swarm(*, enqueue: bool = True, domain: str = "wow") -> dict[str, Any]:
    """Launch the WoW-clone instruction swarm: route each goal through route_novel (dedupe +
    enqueue to the swarm research queue -> k8s worker drains headless in another ghost seat).
    Idempotent via anchor dedupe. Returns the launched task list."""
    from mag import swarm_surface
    from mag import steer_swarm

    out = []
    for i, g in enumerate(_WOW_GOALS):
        # each WoW goal is a self-testing ask: instruction set + acceptance RIB (behavior test)
        ta = steer_swarm.testable_ask(g + "\n" + _WOW_DOCTRINE, domain=domain)
        if enqueue:
            r = swarm_surface.route_novel(ta["ask"], surface="wow-clone-swarm", lens="research",
                                          domain=domain)
            out.append({"i": i, "ok": r.get("ok"), "deduped": r.get("deduped"),
                        "task_id": r.get("task_id", ""), "anchor": (r.get("anchor") or "")[:12]})
        else:
            out.append({"i": i, "ok": True, "deduped": False, "dry": True,
                        "goal_len": len(ta["ask"])})
    return {"ok": True, "schema": SCHEMA, "enqueue": enqueue,
            "n": len(out), "n_new": sum(1 for o in out if not o.get("deduped")), "tasks": out}


# GAME-WORK SWARM — idle free seats put to work on the game (2026-08-24, operator: "find other
# cool shit we could be doing with our free seats that are just sitting idle. playing our game to
# see if it sucks, researching roguelites, combing through our extensive existing game fiction and
# research libraries"). Three irons: (1) PLAYTEST the Hall and say if it sucks, (2) roguelite
# research mapped to the clone spine, (3) self-steal sweep of our own design + fiction libraries.
_GAME_DOCTRINE = (
    "RIB doctrine: aim at the coldest vertex; steal-and-adapt (contracts only, no wholesale copy); "
    "one knot at a time; the nod is mine. CONTEXT: our game = the Hall of Shared Supper (one-room "
    "slice, empty chairs, verkle-committed) + the clone/Mickey 17 spine (clone dies, reprinted with "
    "memory; memory/steal/DESIGN_CLONE_REPRINT_MICKEY17_20260824.md) + the guild hidden network + "
    "the nemesis-as-gadfly + the Deadzone roguelite steal "
    "(memory/steal/STEAL_DEADZONE_ROGUE_20260824.md). Return ONE concrete steal + ONE invariant, "
    "mapped to what we already own (verkle world, game_mud, game_campaign storyteller, game_observer)."
)
_GAME_GOALS = [
    "PLAYTEST the Hall of Shared Supper (mag/game_mud.py room + mag/hall_shared_supper.py): sit "
    "ONE play session as a fresh player. Walk in, see the room, count the chairs, make the "
    "end-of-sitting choice. Then critique HONESTLY: does it suck? Is the first-run-no-math true? "
    "Does the choice moment land? What would make a stranger come back? Return ONE honest verdict "
    "+ ONE concrete improvement.",
    "RIB-driven research: Hades (Supergiant) — the ONE meta-progression / commitment-hook "
    "mechanism worth stealing: death as memory, NPCs who remember your deaths, relationships and "
    "story advancing THROUGH death. Map it to our clone/Mickey 17 reprint spine (clone dies, "
    "reprinted with memory, return-stronger, world remembers). What does Hades do in shape that we "
    "should copy, and what do we refuse?",
    "RIB-driven research: the ONE 'tough to get into / hard to commit to' onboarding fix worth "
    "stealing across Rogue Legacy (lineage/descendants), Returnal (death-loop story), Children of "
    "Morta (family meta-progression), Caves of Qud (emergent simulation). Map to our Hall + clone "
    "spine: first run no math, safe to commit because the self persists.",
    "RIB-driven research: Dwarf Fortress + RimWorld story-generator mechanics (storyteller "
    "algorithm picking events from live state, Legends mode browsable history, 'losing is fun' "
    "death economy) — the ONE mechanism worth stealing for our game_campaign storyteller + the "
    "clone death economy. Map to what we already own (game_campaign storyteller/threat_budget, "
    "game_observer, verkle world history).",
    "SELF-STEAL SWEEP of our own design library: read memory/steal/* + "
    "handoff/STEAL_GAME_FEATURES_20260819.md + memory/steal/DESIGN_CLONE_REPRINT_MICKEY17_20260824.md "
    "+ memory/steal/STEAL_DEADZONE_ROGUE_20260824.md + the Hall audit. Surface the TOP unused "
    "mechanic not yet wired into the Hall, and name ONE concrete next feature + why it fits the "
    "clone/reprint/guild/nemesis spine.",
    "SELF-STEAL SWEEP of our game fiction + narrative corpus: read memory/narrative_corpus/ + "
    "adventure_one_shot outputs + hero_journey + the museum rooms (memory/archive/museum/). Find "
    "the ONE existing piece of fiction that should become a room or character in the Hall. Name "
    "it, where it goes, why it fits the clone/reprint/guild spine.",
]


def game_swarm(*, enqueue: bool = True, domain: str = "game") -> dict[str, Any]:
    """Launch the GAME-WORK SWARM: route each goal through route_novel (dedupe + enqueue to the
    swarm research queue -> k8s worker drains headless on the free path). Idempotent via anchor
    dedupe. The irons: playtest the Hall, roguelite research, self-steal sweep of our libraries."""
    from mag import swarm_surface
    from mag import steer_swarm

    out = []
    for i, g in enumerate(_GAME_GOALS):
        ta = steer_swarm.testable_ask(g + "\n" + _GAME_DOCTRINE, domain=domain)
        if enqueue:
            r = swarm_surface.route_novel(ta["ask"], surface="game-swarm", lens="research",
                                          domain=domain)
            out.append({"i": i, "ok": r.get("ok"), "deduped": r.get("deduped"),
                        "task_id": r.get("task_id", ""), "anchor": (r.get("anchor") or "")[:12]})
        else:
            out.append({"i": i, "ok": True, "deduped": False, "dry": True,
                        "goal_len": len(ta["ask"])})
    return {"ok": True, "schema": SCHEMA, "enqueue": enqueue,
            "n": len(out), "n_new": sum(1 for o in out if not o.get("deduped")), "tasks": out}


def fold_k8s_to_k3s(*, domain: str = "k3s-toolset", publish: bool = True) -> dict[str, Any]:
    """AUTO-FOLD completed k8s swarm results into a k3s-mounted RIB domain, so the k3s toolset
    starts/updates itself.

    k8s (DeepSeek swarm) produces results -> the worker writes them to the shared state PVC
    (swarm_worker RESULTS_DIR). This reads the COMPLETED results and publishes each as a RIB on
    the given domain via rib_bus.publish_rib. The k3s local workers auto-mount that domain
    (rib_bus.mount + inject_for) — "starting their toolset" = the k3s workers inherit the folded
    instruction set. This is the offload that makes k8s concentrate on cold-seam work only.

    Guarded: never breaks the cadence. Honest: if no completed results yet, reports that (never
    fabricates). Deterministic + $0.
    """
    from mag import rib_bus
    from mag import swarm_worker

    # read the shared state PVC (results dir the in-cluster worker writes)
    rdir = Path(getattr(swarm_worker, "RESULTS_DIR", ""))
    if not rdir.is_dir():
        return {"ok": True, "schema": SCHEMA, "domain": domain, "n_folded": 0,
                "note": "no swarm results dir yet — k8s hasn't returned completed work"}
    folded = []
    for p in sorted(rdir.glob("*.json")):
        try:
            rec = json.loads(p.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        # extract the meaningful text (goal/result/answer/summary — defensive)
        goal = str(rec.get("goal") or rec.get("task_id") or p.stem)[:200]
        body = (str(rec.get("result") or rec.get("answer") or rec.get("summary")
                    or rec.get("detail") or rec.get("output") or "")).strip()
        if not body:
            continue
        if publish:
            try:
                r = rib_bus.publish_rib(f"[k8s->k3s folded] goal: {goal}\nRESULT: {body[:600]}",
                                        domain=domain, source="fold_k8s_to_k3s (auto, 2026-08-12)",
                                        target_rank="T2")
                folded.append({"file": p.name, "rib": r.get("ok"), "key": r.get("key", "")[:12]})
            except Exception as e:
                folded.append({"file": p.name, "rib": False, "error": str(e)[:100]})
        else:
            folded.append({"file": p.name, "rib": "dry", "len": len(body)})

    # also scan the QUEUE_DIR for sw-* specs marked done (backstop for results written inline)
    qdir = Path(getattr(swarm_worker, "QUEUE_DIR", ""))
    if qdir.is_dir():
        for p in sorted(qdir.glob("sw-*.json")):
            try:
                rec = json.loads(p.read_text(encoding="utf-8", errors="replace"))
            except Exception:
                continue
            if str(rec.get("status", "")) in ("done", "completed", "success"):
                body = str(rec.get("result") or "").strip()
                if not body:
                    continue
                if publish:
                    try:
                        r = rib_bus.publish_rib(
                            f"[k8s->k3s folded] goal: {str(rec.get('goal'))[:200]}\nRESULT: {body[:600]}",
                            domain=domain, source="fold_k8s_to_k3s (auto)", target_rank="T2")
                        folded.append({"file": p.name, "rib": r.get("ok"), "key": r.get("key", "")[:12]})
                    except Exception:
                        pass

    # the k3s toolset is started when the domain is mounted
    mounted = rib_bus.mount(domain)
    return {"ok": True, "schema": SCHEMA, "domain": domain, "n_folded": len(folded),
            "folded": folded, "k3s_mounted_ribs": mounted.get("n_ribs", 0),
            "note": "completed k8s results auto-folded as RIBs; k3s mounts this domain to start "
                    "their toolset"}


def lens_research_asks(*, corpus: str | None = None, fold: bool = True,
                       domain: str = "foundation") -> dict[str, Any]:
    """LENS the research corpus to understand OUR OWN systems + the foundations to build.

    Not steal-and-fold blindly: run the recent research through the cross-lens synthesis
    (apply_all_lenses) so the convergences/divergences/tesuji/merged-insight reveal what OUR
    architecture implies about the foundations we need. Maps the merged insight to a concrete
    "foundation to build" recommendation. Folded as a RIB on the foundation domain.

    Guarded (never breaks cadence). Deterministic + $0 (apply_all_lenses is deterministic;
    the deep synthesis honestly flags when it needs model inference — the stochastic seat's job).
    """
    from mag import lens_library

    # gather the research corpus: the research packs + recent steal files (real bytes)
    text_chunks: list[str] = []
    if corpus:
        text_chunks.append(corpus)
    rp = ROOT / "memory" / "research_packs"
    if rp.is_dir():
        for p in sorted(rp.glob("*.md"))[-6:]:
            try:
                text_chunks.append(p.read_text(encoding="utf-8", errors="replace")[:1500])
            except Exception:
                pass
    steal = ROOT / "memory" / "steal"
    if steal.is_dir():
        for p in sorted(steal.glob("*.md"))[-6:]:
            try:
                text_chunks.append(p.read_text(encoding="utf-8", errors="replace")[:1500])
            except Exception:
                pass
    data = "\n\n---\n\n".join(text_chunks)[:6000]
    syn = lens_library.apply_all_lenses(data, "research asks -> our systems + foundations")
    merged = getattr(syn, "merged_insight", "") or ""

    # foundation recommendation: the merged insight names what to build next
    foundation = _foundation_from(merged, getattr(syn, "tesuji", []))

    folded = {}
    if fold and merged and merged != ("No strong patterns detected. Apply lenses with model "
                                      "inference for deeper analysis."):
        try:
            from mag import rib_bus
            folded = rib_bus.publish_rib(
                f"[lensed research -> foundation] merged: {merged[:500]} "
                f"| FOUNDATION TO BUILD: {foundation[:300]}",
                domain=domain, source="lens_research_asks (2026-08-12)", target_rank="T2")
        except Exception as e:
            folded = {"ok": False, "error": str(e)[:120]}

    return {"ok": True, "schema": SCHEMA, "domain": domain,
            "lenses": getattr(syn, "lenses_applied", []),
            "convergences": len(getattr(syn, "convergences", [])),
            "divergences": len(getattr(syn, "divergences", [])),
            "tesuji": len(getattr(syn, "tesuji", [])),
            "merged_insight": merged, "foundation_to_build": foundation,
            "folded": folded,
            "note": "research asks lensed -> our-system understanding + foundation to build"}


def _foundation_from(merged: str, tesuji: list[Any]) -> str:
    """Deterministic: turn the merged insight into a 'foundation to build' recommendation."""
    if not merged or merged == "No strong patterns detected. Apply lenses with model inference " \
            "for deeper analysis.":
        return "Deep synthesis needs the stochastic seat — feed the lensed corpus to the frontier " \
               "at the coldest seam to name the foundation."
    t = (merged + " " + " ".join(str(x) for x in tesuji)).lower()
    if "memory" in t or "chain" in t:
        return "Foundation: harden the verkle/memory substrate (the chain is the foundation every " \
               "lens converges on)."
    if "rout" in t or "dispatch" in t or "gate" in t:
        return "Foundation: the intent-gate + dispatch substrate (routing is the convergent seam)."
    if "swarm" in t or "k8s" in t or "emulator" in t:
        return "Foundation: the k8s/emulator substrate (the swarm is the foundation being built)."
    return "Foundation: fold the lensed merged insight as doctrine; name the coldest seam to build."


def process_lensed_data(*, enqueue: bool = True, domain: str = "research") -> dict[str, Any]:
    """Use the SWARMS to process the lensed research DATA (not just steal-and-fold).

    Operator (2026-08-12): "we should also be using our swarms to process this data later when we
    can do it for free the focus is on data." The lensed corpus is the DATA; the deterministic lens
    honestly can't do the deep synthesis, so we route it through the SWARM (DeepSeek) which
    processes it into folded knowledge. Free processing (free tiers / free frontends / grok seat)
    is prioritized WHEN AVAILABLE; the DeepSeek swarm is the cheap paid fallback.

    Route via route_novel (dedupe by anchor + enqueue to the swarm research queue -> k8s worker
    drains headless). Idempotent. Deterministic + $0 to enqueue.
    """
    from mag import swarm_surface

    # the DATA: the lensed research corpus (research packs + recent steals), real bytes
    chunks: list[str] = []
    rp = ROOT / "memory" / "research_packs"
    if rp.is_dir():
        for p in sorted(rp.glob("*.md"))[-6:]:
            try:
                chunks.append(p.read_text(encoding="utf-8", errors="replace")[:1500])
            except Exception:
                pass
    steal = ROOT / "memory" / "steal"
    if steal.is_dir():
        for p in sorted(steal.glob("*.md"))[-6:]:
            try:
                chunks.append(p.read_text(encoding="utf-8", errors="replace")[:1500])
            except Exception:
                pass
    data = "\n\n---\n\n".join(chunks)[:5000]

    goal = ("PROCESS THIS LENSED RESEARCH DATA into folded foundation knowledge: "
            "cross-lens synthesize the corpus, name the convergences + divergences + the ONE "
            "tesuji, and the foundation to build for our sovereign-agent systems. Return ONE "
            "merged invariant + ONE foundation. Focus on the DATA.\n\nDATA:\n" + data)

    if not enqueue:
        return {"ok": True, "schema": SCHEMA, "enqueue": False, "data_chars": len(data), "dry": True}

    r = swarm_surface.route_novel(goal, surface="process-lensed-data", lens="research",
                                  domain=domain)
    return {"ok": bool(r.get("ok")), "schema": SCHEMA, "deduped": r.get("deduped"),
            "task_id": r.get("task_id", ""), "anchor": (r.get("anchor") or "")[:12],
            "data_chars": len(data),
            "note": "lensed research data enqueued to the swarm for deep processing; free "
                    "processing prioritized when available (focus is the data)"}


def route_local(goal: str, *, intent: str | None = None) -> dict[str, Any]:
    """Route a task to the LOCAL stack per intent_rightsize — the fix for "why use DeepSeek when we
    have everything right here" (operator 2026-08-12).

    Our own doctrine: build -> k3s (deterministic, $0), inference -> gpu (free local), research ->
    swarm (DeepSeek). The game-coding task is BUILD + INFERENCE, so it belongs on the LOCAL stack
    (k3s + GPU), NOT the paid DeepSeek research swarm. DeepSeek is for research seams only.

    Deterministic + $0 (pure routing decision; the local runners execute it).
    """
    from mag import intent_rightsize

    g = (goal or "").strip() or "the game build task"
    intent = (intent or "").strip() or intent_rightsize._detect_intent(g)
    prof = intent_rightsize.INTENT.get(intent, intent_rightsize.INTENT["research"])
    local = prof["surface"] in ("cpu", "k3s", "gpu")      # local/free vs paid swarm/frontier
    return {"ok": True, "schema": SCHEMA, "goal": g[:160], "intent": intent,
            "surface": prof["surface"], "n_agents": prof["n_agents"],
            "cost_tier": prof["cost_tier"], "local": local,
            "why": prof["why"],
            "note": ("LOCAL stack (k3s/gpu/cpu, $0) — the game is a build/inference, use our free "
                     "resources" if local else
                     "research/frontier — the paid swarm is the right surface for this seam"),
            "recommendation": ("route the game build to k3s + local GPU inference; keep DeepSeek "
                               "for research seams only" if local else
                               "this is research — the DeepSeek swarm is correct here")}


# DEEP RESEARCH PROJECT — the WoW-clone game build (the operator's "important task").
# Operator (2026-08-12): "!deep research project" — a focused deep-research project, routed through
# the swarm, on how to build our self-hosted emulator clone START TO FINISH for zero.
DEEP_GAME_ROUNDS = [
    "DEEP RESEARCH round 1: the full architecture to build our self-hosted WoW-style emulator "
    "clone from source (MaNGOS/TrinityCore/CMaNGOS) — client-server split, world/characters/realmd "
    "DB schema, build steps, self-host setup. Return the concrete start-to-finish build plan.",
    "DEEP RESEARCH round 2: run the emulator server-authoritative on our k8s swarm (state PVC, "
    "stateless workers re-render, replayable opcodes -> verkle protocol). The exact k8s manifests + "
    "how the swarm becomes the game server.",
    "DEEP RESEARCH round 3: the RIB-as-mod system — how WoW addons (FrameXML, hooks, saved "
    "variables) map to our RIB instruction layer and rib_bus.mount. The mod system code instructions.",
    "DEEP RESEARCH round 4: build the game for ZERO — the cheapest path (local GPU/ollama for "
    "inference, k3s for build, free tiers) + the ONE legal/licensing constraint that gates the free "
    "clone. The zero-cost build plan.",
]


def deep_research_project(*, enqueue: bool = True, domain: str = "deep-research",
                          provider: str = "deepseek") -> dict[str, Any]:
    """Launch the DEEP RESEARCH PROJECT on the game build, routed through the swarm.

    Enqueues the deep-research rounds (start-to-finish game build, emulator-on-k8s, RIB-as-mod,
    zero-cost build) to the swarm worker queue via route_novel (dedupe + enqueue, k8s drains
    headless). Deterministic + $0 to enqueue. Honest: reports deduped vs new."""
    from mag import swarm_surface

    out = []
    for i, q in enumerate(DEEP_GAME_ROUNDS):
        if enqueue:
            r = swarm_surface.route_novel(q, surface="deep-research-project", lens="deep-research",
                                          domain=domain, provider=provider)
            out.append({"round": i + 1, "ok": r.get("ok"), "deduped": r.get("deduped"),
                        "task_id": r.get("task_id", ""), "anchor": (r.get("anchor") or "")[:12]})
        else:
            out.append({"round": i + 1, "ok": True, "deduped": False, "dry": True})
    return {"ok": True, "schema": SCHEMA, "project": "game-build deep research", "enqueue": enqueue,
            "n_rounds": len(out),
            "n_new": sum(1 for o in out if not o.get("deduped")), "rounds": out,
            "note": "deep research project on the game build routed through the swarm (k8s drains "
                    "headless); rounds fold -> insight for the next ask"}


def main(argv: list[str] | None = None) -> int:
    argv = list(argv) if argv else list(sys.argv[1:])
    dry = "--dry" in argv
    wow = "--wow" in argv
    process = "--process" in argv
    deep = "--deep" in argv
    game = "--game" in argv
    if deep:
        print(json.dumps(deep_research_project(enqueue=not dry), ensure_ascii=False, indent=2,
                         default=str))
    elif game:
        print(json.dumps(game_swarm(enqueue=not dry), ensure_ascii=False, indent=2, default=str))
    elif wow:
        print(json.dumps(wow_clone_swarm(enqueue=not dry), ensure_ascii=False, indent=2, default=str))
    elif process:
        print(json.dumps(process_lensed_data(enqueue=not dry), ensure_ascii=False, indent=2,
                         default=str))
    elif dry:
        print(json.dumps(spawn_overnight(enqueue=False), ensure_ascii=False, indent=2, default=str))
    else:
        print(json.dumps(spawn_overnight(enqueue=True), ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
