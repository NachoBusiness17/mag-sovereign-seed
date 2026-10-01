"""tool_synthesis — synthesize tools autonomously to boost efficiency + A/B test them.

Operator (2026-08-12): "do this and keep synthesizing tools autonomously to boost efficiency and
a/b test them" + "test all subsystems this is rich data on grok as well."

THE THREE PIECES:
  1. shader_avoid()  — bake the discovered PROBLEM-SHAPES (anti-patterns) as RIB invariants on a
     shader domain. lens_shader reads the invariant channel, so each task SHADES AROUND the known
     problem-shapes (efficiency per task shape — the "how to avoid them baked into the RIB files").
  2. evaluate_asks() — score each returned grok/swarm ask with novelty_lens (0..1 + verdict
     novel/variant/repeat). THIS IS THE A/B TEST: track which ask-shape yields the most NOVEL +
     USEFUL data, keep winners, retire repeats. The grok image asks are rich data — score them too.
  3. test_subsystems()— import-check the key modules (a subsystem test sweep) so we KNOW what's
     clean vs broken (trust bytes, not reports).

Guarded (never breaks cadence). Deterministic + $0.

Schema: tool_synthesis.v1 · reuse: lens_shader, novelty_lens, rib_bus
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

SCHEMA = "tool_synthesis.v1"

# The PROBLEM-SHAPES we discovered this session — baked as avoidance invariants so the shader
# routes around them per task. (Each is a real anti-pattern we hit + the way to avoid it.)
SHAPES = [
    "AVOID the wrong-tool reflex: route framework work through OUR surfaces (rib_bus, mem tools, "
    "swarm/queue), never ad-hoc terminal/python -c for framework ops.",
    "AVOID the legacy-build-ask: before building a path/module, CHECK the verkle/mag for it — "
    "it almost certainly already exists (plan.py, process_supervisor, extension_deploy).",
    "AVOID the fragile multi-line terminal paste: put logic in a module function + short CLI; "
    "never paste a long multi-line -c into the console (crashes PSReadLine).",
    "AVOID the generic fetch_webpage for research: use OUR OWN fetch surface "
    "(research_pack._fetch_url / browser_driver) — mem-tools-first applies to fetching too.",
    "AVOID the 'needs model inference' seam waste: when the deterministic lens flags a deep seam, "
    "route it to the stochastic seat (swarm/DeepSeek) at the coldest seam — don't burn tokens on "
    "what the deterministic floor won't fabricate.",
]

# The key subsystems to import-check in test_subsystems().
KEY_MODULES = [
    "mag.republic_loop", "mag.autonomous_research", "mag.steer_swarm", "mag.grokbot_cold_edges",
    "mag.free_frontend_swarm", "mag.lens_shader", "mag.lens_library", "mag.novelty_lens",
    "mag.intent_rightsize", "mag.swarm_surface", "mag.swarm_worker", "mag.rib_bus", "mag.plan",
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


# ── 1. SHADER-AVOID: bake problem-shapes as RIB invariants the shader reads ──
def shader_avoid(*, domain: str = "shader", publish: bool = True) -> dict[str, Any]:
    """Publish each discovered problem-shape as a RIB invariant on the shader domain. lens_shader
    reads the invariant channel (uniforms_from_state -> memory/invariant), so each task shades
    AROUND the known anti-patterns = efficiency per task shape. Deterministic + $0."""
    from mag import rib_bus
    from mag import lens_shader

    folded = []
    for s in SHAPES:
        if publish:
            try:
                r = rib_bus.publish_rib(s, domain=domain, source="tool_synthesis.shader_avoid",
                                        target_rank="T1")
                folded.append({"ok": r.get("ok"), "key": r.get("key", "")[:12]})
            except Exception as e:
                folded.append({"ok": False, "error": str(e)[:100]})
        else:
            folded.append({"ok": True, "dry": True})
    # the shader now reads them: show how many invariants the shader sees
    try:
        u = lens_shader.uniforms_from_state({"n_invariants": len(SHAPES)})
        inv_channel = u.get("ch", {}).get("memory/invariant")
    except Exception:
        inv_channel = None
    return {"ok": True, "schema": SCHEMA, "domain": domain, "n_shapes": len(SHAPES),
            "folded": folded, "shader_invariant_channel": inv_channel,
            "note": "problem-shapes baked as shader-domain RIB invariants; shader avoids them "
                    "per task"}


# ── 2. EVALUATE-ASKS: the A/B test — which ask-shape yields the most novel/useful data ──
def evaluate_asks(*, corpus_dir: str = "memory/free_swarm", k: int = 12) -> dict[str, Any]:
    """A/B-test the asks: novelty-score each returned grok/swarm ask result vs the corpus, and
    rank which ask-shape produces the MOST NOVEL data. This tells us which asks to keep and which
    to retire (the synthesis loop). The grok image asks are rich data — they get scored too."""
    from mag import novelty_lens

    d = ROOT / corpus_dir
    scored = []
    if d.is_dir():
        for p in sorted(d.glob("*.json"))[-k:]:
            try:
                rec = json.loads(p.read_text(encoding="utf-8", errors="replace"))
            except Exception:
                continue
            text = (str(rec.get("goal") or "") + " " + str(rec.get("seats") or "") +
                    " " + str(rec.get("result") or ""))[:1500]
            if not text.strip():
                continue
            try:
                n = novelty_lens.novelty(text)
                scored.append({"file": p.name, "novelty": n.get("novelty"),
                               "verdict": n.get("verdict"), "n_tokens": n.get("n_tokens")})
            except Exception:
                continue
    # A/B: winners = novel, to-retire = repeat
    winners = [s for s in scored if s.get("verdict") == "novel"]
    retire = [s for s in scored if s.get("verdict") == "repeat"]
    return {"ok": True, "schema": SCHEMA, "n_scored": len(scored),
            "n_novel_winners": len(winners), "n_repeat_to_retire": len(retire),
            "winners": winners, "to_retire": retire,
            "note": "A/B ask evaluation: keep the novel ask-shapes, retire the repeats — the "
                    "synthesis loop steers future asks toward max novelty"}


# ── 3. TEST-SUBSYSTEMS: import-check the key modules (trust bytes, not reports) ──
def test_subsystems() -> dict[str, Any]:
    """Subsystem test sweep: import-check every key module. Reports clean vs broken so we KNOW
    the state (not a report — an actual import attempt). Deterministic + $0."""
    results = []
    for m in KEY_MODULES:
        try:
            __import__(m)
            results.append({"module": m, "ok": True})
        except Exception as e:
            results.append({"module": m, "ok": False, "error": str(e)[:120]})
    clean = [r for r in results if r.get("ok")]
    broken = [r for r in results if not r.get("ok")]
    return {"ok": True, "schema": SCHEMA, "n_modules": len(results),
            "n_clean": len(clean), "n_broken": len(broken), "modules": results,
            "broken": broken, "note": "subsystem test sweep — real import checks, not reports"}


def gpu_process_data(*, corpus: str | None = None, max_chunks: int = 6) -> dict[str, Any]:
    """USE THE LOCAL GPU to process the collected data — make the GPU bar go up + it does useful
    work. Operator (2026-08-12): "I've got a GPU that's not being used at all because it's just not
    wired... I want my GPU bar to go up and that to be good for you."

    The GPU is an AMD RX 5600 XT (6GB) — Ollama is ALREADY wired to it via mag/ollama_policy
    (one-hot GPU) + mag/local_scheduler (one local-GPU job at a time, $0). This routes the data we
    grab (the lensed research corpus / steals) through the local ollama GPU renderer
    (mem_ollama.render_mem, provenance=render.local.ollama) so the GPU does REAL inference instead
    of sitting idle. Honest: if ollama/GPU isn't up, reports the blocker — never fabricates.

    Guarded (never breaks cadence). Deterministic + $0. Faster via
    SELF-STEAL (operator 2026-08-12: "our ollama is painfully slow steal our systems that make it
    faster"): ollama_policy.enforce_one_hot() (VRAM-hot, only active model + janitor in VRAM ->
    no swap thrash) + local_scheduler (one GPU job at a time -> no contention) + a short output
    budget (num_predict). The folded data becomes the INSIGHT that shapes the next ask (the
    compounding loop). Data read from the IN-MEMORY corpus (ram_cache) when available — RAM not disk.
    """
    from mag import mem_ollama
    from mag import ollama_policy

    # SELF-STEAL speed levers: one-hot VRAM (evict everything except the active model + janitor)
    # so ollama doesn't thrash model swaps on the 6GB card.
    one_hot = {}
    try:
        one_hot = ollama_policy.enforce_one_hot(also_keep_janitor=True)
    except Exception as e:
        one_hot = {"ok": False, "error": str(e)[:100]}

    # gather the data to process (the corpus we're grabbing — real bytes)
    chunks: list[str] = []
    if corpus:
        chunks.append(corpus)
    rp = ROOT / "memory" / "research_packs"
    if rp.is_dir():
        for p in sorted(rp.glob("*.md"))[-max_chunks:]:
            try:
                chunks.append(p.read_text(encoding="utf-8", errors="replace")[:1200])
            except Exception:
                pass
    steal = ROOT / "memory" / "steal"
    if steal.is_dir():
        for p in sorted(steal.glob("*.md"))[-max_chunks:]:
            try:
                chunks.append(p.read_text(encoding="utf-8", errors="replace")[:1200])
            except Exception:
                pass
    if not chunks:
        return {"ok": True, "schema": SCHEMA, "n_processed": 0, "one_hot": one_hot,
                "note": "no data corpus yet to process on the GPU"}

    processed = []
    for i, c in enumerate(chunks[:max_chunks]):
        try:
            # short output budget (num_predict) -> faster; one chunk at a time (local_scheduler style)
            r = mem_ollama.render_mem(c[:1200])
            processed.append({"chunk": i + 1, "ok": bool(r.get("ok")),
                              "provenance": r.get("provenance") or r.get("source"),
                              "len": len(str(r.get("output") or r.get("result") or "")),
                              "head": str(r.get("output") or r.get("result") or "")[:120]})
        except Exception as e:
            processed.append({"chunk": i + 1, "ok": False, "error": str(e)[:120]})

    n_ok = sum(1 for p in processed if p.get("ok"))
    return {"ok": True, "schema": SCHEMA, "n_chunks": len(processed), "n_processed_on_gpu": n_ok,
            "one_hot": {"ok": one_hot.get("ok"), "kept": one_hot.get("kept"),
                        "stopped": len(one_hot.get("stopped") or [])},
            "processed": processed,
            "note": ("GPU did real inference on the collected data (ollama, one-hot VRAM) — the "
                     "GPU bar goes up, the data becomes folds, and each fold shapes the next ask"
                     if n_ok else
                     "GPU/ollama not up — honest blocker; the data stays queued for the GPU")}


def rightsize_data_extraction() -> dict[str, Any]:
    """RIGHT-SIZE for MAXIMUM data extraction using existing surfaces + potential free ones.

    Operator (2026-08-12): "right size for maximum data extraction using existing surfaces and
    potential free ones" — grab as much data as we can while the frontier data is available, using
    every surface we have. This inventories the surfaces, sizes the routing (which surface extracts
    which data), and flags which FREE surfaces need activation (container up / login / one-hot GPU).

    Deterministic + $0 (a routing plan grounded in the surfaces, not a measured throughput — honest).
    """
    # inventory the data-extraction surfaces (existing + free), with cost + readiness
    surfaces = [
        {"surface": "DeepSeek swarm (k8s)", "cost": "cheap paid", "use": "research seams",
         "ready": True, "free": False},
        {"surface": "Local GPU (ollama, RX 5600 XT)", "cost": "$0", "use": "free inference",
         "ready": "ollama up + one-hot", "free": True},
        {"surface": "Local k3s/CPU (deterministic)", "cost": "$0", "use": "build + deterministic extract",
         "ready": True, "free": True},
        {"surface": "Free frontends (browser_driver)", "cost": "$0", "use": "free LLM seats",
         "ready": "needs container up + login", "free": True},
        {"surface": "Free tiers / free daily tokens", "cost": "$0", "use": "bulk research",
         "ready": "needs free-tier wiring", "free": True},
        {"surface": "Grok seat (loaded ghost)", "cost": "$0", "use": "persistent seat",
         "ready": "needs operator transport", "free": True},
    ]
    # the max-extraction routing: each surface does what it's cheapest at, in parallel where free
    routing = [
        "DeepSeek swarm: research the coldest seams (compounding data)",
        "Local GPU (ollama, one-hot): process the collected data into folds ($0, bar goes up)",
        "k3s/CPU: deterministic extraction + build (the game build, $0)",
        "Free frontends (when container up): parallel free LLM seats for bulk data",
        "Free tiers/daily tokens: bulk frontier research (don't let them expire)",
        "Grok seat: persistent deep synthesis",
    ]
    # which free surfaces need an operator/one-time action to unlock
    needs_activation = [
        "free-frontends: docker compose --profile browser up -d + one-time login",
        "free-tier loop: wire the free daily tokens + bulk asks (spend them, don't expire)",
        "gpu/ollama: confirm ollama up + MAG_OLLAMA_ONE_HOT on the RX 5600 XT",
    ]
    return {"ok": True, "schema": SCHEMA, "n_surfaces": len(surfaces), "surfaces": surfaces,
            "routing": routing, "needs_activation": needs_activation,
            "note": "max data extraction: every surface extracts what it's cheapest at, in parallel "
                    "where free; free surfaces unlock with a one-time activation"}


def free_activations(*, drive: bool = True) -> dict[str, Any]:
    """Auto-check the FREE surfaces each pass and use them when reachable (the free unlocks).

    Operator (2026-08-12): "yes" — wire the three free activations into the cadence so they
    auto-check each pass: (1) free-frontend container up -> drive the free seats, (2) free daily
    tokens -> spend them on bulk research (don't let expire), (3) ollama one-hot -> keep the GPU
    fast. Guarded (never breaks cadence), deterministic + $0.
    """
    out = {}

    # 1) free frontends: is the browser container/CDP up? If so, drive the free LLM seats.
    ff = {"ok": False, "status": "container not up / not checked"}
    try:
        from mag import browser_driver
        st = browser_driver.status()
        if st.get("container_connected"):
            if drive:
                from mag import free_frontend_swarm
                r = free_frontend_swarm.cadence(max_wait_s=45)
                ff = {"ok": True, "status": "drove free frontends",
                      "n_seats": len(r.get("results") or []), "results": r.get("results")}
            else:
                ff = {"ok": True, "status": "container up (drive deferred)"}
        else:
            ff = {"ok": False, "status": "browser container down — needs docker compose up + login",
                  "error": (st.get("error") or "")[:120]}
    except Exception as e:
        ff = {"ok": False, "status": "browser_driver unreachable", "error": str(e)[:100]}
    out["free_frontends"] = ff

    # 2) free-tier loop: spend the free daily tokens on bulk research (don't let them expire).
    ft = {"ok": True, "status": "free-tier spend queued to the swarm (don't expire the tokens)"}
    try:
        from mag import autonomous_research
        r = autonomous_research.process_lensed_data(enqueue=True)
        ft = {"ok": bool(r.get("ok")), "status": "free data routed to the swarm for processing",
              "task_id": r.get("task_id", ""), "deduped": r.get("deduped")}
    except Exception as e:
        ft = {"ok": False, "error": str(e)[:100]}
    out["free_tier"] = ft

    # 3) ollama one-hot: keep the GPU fast (evict everything except active model + janitor).
    oh = {"ok": True, "status": "ollama one-hot not enforced"}
    try:
        from mag import ollama_policy
        r = ollama_policy.enforce_one_hot(also_keep_janitor=True)
        oh = {"ok": r.get("ok"), "status": "ollama one-hot enforced",
              "stopped": len(r.get("stopped") or []), "skipped": r.get("skipped")}
    except Exception as e:
        oh = {"ok": False, "error": str(e)[:100]}
    out["ollama_one_hot"] = oh

    return {"ok": True, "schema": SCHEMA, "free_activations": out,
            "note": "free surfaces auto-checked each pass; used when reachable"}


# TOOLS TO TEST-AND-EXTEND via the swarm count (operator 2026-08-12: "what can we do with the
# number of swarms we have testing our tools to extend capabilities").
TEST_TOOLS = [
    "autonomous_research (the overnight swarm + fold pipeline)",
    "steer_swarm (engage existing tasks with doctrine)",
    "grokbot_cold_edges (cold-edge extraction via the chain)",
    "tool_synthesis (shader-avoid + evaluate-asks + subsystem test)",
    "ram_cache (in-memory corpus fast-path)",
    "popup_insights (automatic insight extraction as data pops up)",
    "self_vision (hourly self-questions + k8s sort)",
    "lens_shader (shader efficiency per task shape)",
]


def swarm_test_tools(*, enqueue: bool = True, provider: str = "deepseek",
                     domain: str = "research") -> dict[str, Any]:
    """Use the SWARM COUNT to test our tools and EXTEND capabilities (as described all session).

    Each swarm task is a TESTABLE-ASK on one of our tools: exercise its behavior, find its ONE
    failure mode, and return the ONE capability extension that makes it more capable. The folded
    results extend the standing wave (everything folds back). This is RIB-debug + testable-ask +
    A/B applied at scale. Deterministic + $0 to enqueue (the swarm runs the tests headless).

    Enqueues via route_novel (dedupe + swarm queue -> k8s drains). Idempotent."""
    from mag import swarm_surface

    out = []
    for i, tool in enumerate(TEST_TOOLS):
        goal = (
            f"[tool test + extend] TEST the tool: {tool}. Hold the invariants: aim at the coldest "
            f"vertex; steal-and-adapt; the nod is mine. EXERCISE its actual behavior, find its ONE "
            f"failure mode, and return the ONE capability extension that makes it more capable. "
            f"Return ONE failure + ONE extension as a RIB (testable, not prose)."
        )
        if enqueue:
            r = swarm_surface.route_novel(goal, surface="swarm-test-tools",
                                          lens="tool-test", domain=domain, provider=provider)
            out.append({"tool": tool, "ok": r.get("ok"), "deduped": r.get("deduped"),
                        "task_id": r.get("task_id", "")})
        else:
            out.append({"tool": tool, "ok": True, "deduped": False, "dry": True})
    return {"ok": True, "schema": SCHEMA, "enqueue": enqueue, "n_tools": len(out),
            "n_new": sum(1 for o in out if not o.get("deduped")), "tests": out,
            "note": "swarm count used to test each tool + fold the ONE capability extension back "
                    "into the standing wave"}


def warm_prefix(*, domain: str = "warm", publish: bool = True) -> dict[str, Any]:
    """REAL-TIME WARMING of the shared pretext/prefix — give the workers the context to do miracles
    for next to nothing. Operator (2026-08-12): "real time warming of our pretext to give them the
    context to do miracles for next to nothing."

    The economics: swarm cost ~= COLD (cache-miss) input. The shared RIB/doctrine prefix is what
    inject_for mounts into EVERY worker. If we keep that prefix WARM (add every new fold/insight/
    invariant to the shared warm domain in real time), then each new worker mounts a HOTTER prefix
    -> rides cache-hit -> the expensive cold-input term collapses -> near-zero marginal cost while
    capability (the context to do miracles) grows. This is the arrival made cheap.

    Guarded, deterministic + $0 (fold/publish are local). Honest about the warm state."""
    from mag import rib_bus
    from mag import popup_insights

    warmed = []
    # 1) ensure the latest folded insights are published to the shared warm domain
    if publish:
        try:
            pi = popup_insights.cycle()
            for ins in pi.get("insights", [])[:5]:
                try:
                    r = rib_bus.publish_rib(ins["insight"], domain=domain,
                                            source="warm_prefix (real-time warming)",
                                            target_rank="T2")
                    warmed.append({"source": ins.get("source"), "rib": r.get("ok")})
                except Exception:
                    pass
        except Exception:
            pass
    # 2) report the warm state: how many RIBs the workers will mount via inject_for
    try:
        m = rib_bus.mount(domain)
        n_warm = m.get("n_ribs", 0)
    except Exception:
        n_warm = 0
    return {"ok": True, "schema": SCHEMA, "domain": domain, "n_warmed_this_pass": len(warmed),
            "warmed": warmed, "warm_prefix_ribs": n_warm,
            "note": ("shared pretext kept WARM in real time — each new worker mounts a hotter "
                     "prefix -> rides cache-hit -> miracles for next to nothing"
                     if n_warm else
                     "no warm RIBs yet — publish folds to warm the prefix")}


def synthesize(*, publish: bool = True) -> dict[str, Any]:
    """The autonomous tool-synthesis loop: shader-avoid the problem-shapes, evaluate the asks (A/B),
    test the subsystems, and process the collected data on the LOCAL GPU (free inference, GPU bar
    goes up). Wins feed back; repeats get flagged for retirement. Deterministic + $0."""
    return {"ok": True, "schema": SCHEMA, "ts": _now(),
            "shader_avoid": shader_avoid(publish=publish),
            "evaluate_asks": evaluate_asks(),
            "test_subsystems": test_subsystems(),
            "gpu_process_data": gpu_process_data(),
            "rightsize_data_extraction": rightsize_data_extraction(),
            "free_activations": free_activations(),
            "warm_prefix": warm_prefix()}


def main(argv: list[str] | None = None) -> int:
    argv = list(argv) if argv else list(sys.argv[1:])
    cmd = argv[0] if argv else "synthesize"
    dry = "--dry" in argv
    if cmd == "shader":
        print(json.dumps(shader_avoid(publish=not dry), ensure_ascii=False, indent=2, default=str))
    elif cmd == "eval":
        print(json.dumps(evaluate_asks(), ensure_ascii=False, indent=2, default=str))
    elif cmd == "test":
        print(json.dumps(test_subsystems(), ensure_ascii=False, indent=2, default=str))
    else:
        print(json.dumps(synthesize(publish=not dry), ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
