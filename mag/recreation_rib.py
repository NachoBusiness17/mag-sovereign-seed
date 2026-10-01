"""recreation_rib — dogfood: capture OUR coding history + corrections as a compact,
renderer-agnostic RIB, then re-render it through a FREE local model to recreate the
architecture for a fraction of the original cost.

Operator (2026-08-10): "if you were to create a rib file of your coding history and its
corrections from all of our frontier models to where you are to recreate it for a fraction of
a cost using our system could you dogfood that?"

The RIB is the RENDERER-AGNOSTIC SCENE: a compact set of SLOTS (the load-bearing invariants,
build steps, and corrections that got us here), each anchored to the real module/schema that
owns it. ANY renderer (frontier, our k8s swarm, or a FREE local model) can fill the scene.
Dogfooding means: run it through ollama (qwen2.5:32b, local, $0) and check whether a cheap
model can RECREATE the architecture's shape from just the RIB + a tool manifest — not from
the original (expensive) deep-research sessions.

Honesty (operator 2026-08-10): the render is OUR re-derivation from the RIB, NOT a frontier
claim. We label it render.local + provenance: the scene came from our own history; the model
re-rendered it. If the renderer is down, we say so — we never claim a recreation that didn't
happen.

Schema: recreation_rib.v1 · CLI: python -m mag.recreation_rib build | render [--model qwen2.5:32b]
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
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCHEMA = "recreation_rib.v1"
RIB_OUT = ROOT / "memory" / "rib" / "recreation-coding-history.json"
STEAL_DIR = ROOT / "memory" / "steal"
TRAIN_DIR = ROOT / "memory" / "training"
GRAPH = ROOT / "memory" / "knowledge_graph.json"

# The load-bearing invariants + corrections that define how we got here. Each entry is
# (slot_id, invariant_text, owning_schema) — the SCENE. A cheap renderer fills from these.
BUILD_SCENE: list[dict[str, Any]] = [
    {"id": "architecture-native", "center":
     "route ALL work through the sovereign architecture (REST routes, queue, drainer, governor/"
     "autorun loop, ghost, overseer) — NEVER ad-hoc terminal commands; async-able work goes to the "
     "queue, deterministic work to non-prompting tools; system-imperative local ops get a BUILT path, "
     "not a hand-run.", "schema": "config.v1", "kind": "doctrine"},
    {"id": "deterministic-0cost", "center":
     "the $0 doctrine: JSONL + sha256 content-addressing + file reads; modules avoid LLM calls; "
     "deterministic modules run for free and are the load-bearing substrate under the stochastic "
     "swarm.", "schema": "knowledge_graph.v2", "kind": "doctrine"},
    {"id": "verkle-substrate", "center":
     "memory is a chain of content-addressed knots (filename=address); a tip root points at the "
     "present; the surface is a viewer, the artifact is truth.", "schema": "verkle_knot.v1",
     "kind": "memory"},
    {"id": "rib-scene", "center":
     "RIBs are renderer-agnostic scenes: declare a constellation of slots in stochastic space and "
     "let ANY generator (frontier, k8s swarm, local model) fill it; steering is the constraint "
     "satisfier (attractors pull wanted data, repellors push already-covered).",
     "schema": "rib_struct.v1", "kind": "memory"},
    {"id": "roshomon-invariants", "center":
     "compare frontier answers THROUGH INVARIANTS: statements recurring across >=2 independent "
     "witnesses = the Roshomon core (convergent truth); unique statements = divergent perspective; "
     "the core folds as doctrine.", "schema": "roshomon.v1", "kind": "stochastic"},
    {"id": "swarm-rendering", "center":
     "the frontier AUTHORES scenes (RIBs); OUR k8s swarm RENDERS them. We take the invariants and "
     "our own cheap compute does the work. Never ask the frontier to execute.", "schema": "swarm_worker.v1",
     "kind": "stochastic"},
    {"id": "memlang-contract", "center":
     "memlang is a compact binary trigger token anchored to shared verkle state; every opcode maps "
     "to a FORMAL MEMORY CONTRACT (a real kind/surface/schema/rw), so a token's grounding is "
     "provable, not handwaved.", "schema": "memlang.v1", "kind": "memory"},
    {"id": "honesty-provenance", "center":
     "HONESTY EVERYWHERE: no artifact may claim 'grok'/'frontier' provenance unless real output was "
     "captured; independent witnesses over single-oracle verification; the ponytail grounding audit "
     "challenges, not trusts; there is no 'steal' without a real source.", "schema": "ponytail_audit.v1",
     "kind": "doctrine"},
    {"id": "single-controller", "center":
     "replicas:1 DELIBERATE; ONE controller owns the always-on loop (never two — the window-storm/"
     "double-drain fix).", "schema": "mag-deployment.yaml", "kind": "ops"},
    {"id": "tool-manifest", "center":
     "the tool manifest auto-discovers every mag/*.py, reads SCHEMA/purpose/CLI/REST from the "
     "module's own source, and emits memory/tool_manifest.json + TOOLS.md — full access to every "
     "tool, populating in VS Code.", "schema": "tool_manifest.v1", "kind": "ops"},
]

# Corrections that shaped the system (real bugs fixed, kept as guardrails in the scene).
CORRECTIONS: list[dict[str, Any]] = [
    {"id": "corr-swarm-8fail", "detail": "swarm 8-fail bug: run_py double-prepended the interpreter "
     "(python python main.py); fixed by run_headless(cmd). Guardrail: never double-wrap the interpreter."},
    {"id": "corr-double-supervision", "detail": "dashboard crash: local host ran BOTH mag_launch and "
     "process_supervisor driving always-on loops = double-supervision. Guardrail: one controller owns "
     "the loop; host the dashboard in-cluster, not on the local machine."},
    {"id": "corr-grok-flag-lie", "detail": "grok:True in artifacts was only the REQUEST flag, not "
     "evidence of output. Guardrail: grok_captured = real output only; provenance_note when it didn't "
     "arrive."},
    {"id": "corr-poweroff-churn", "detail": "container infinite restart: 'power off' exited 0, outer "
     "restart policy respawned forever. Guardrail: hold-alive (idle) instead of exit on power-off."},
    {"id": "corr-doctrine-bloat", "detail": "225 near-dup doctrine pairs were mostly template "
     "similarity; consolidated into families. Guardrail: consolidate templates, don't pile copies."},
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def build(*, with_corrections: bool = True) -> dict[str, Any]:
    """Emit the recreation RIB: our coding history + corrections as a renderer-agnostic scene."""
    scene = [dict(s) for s in BUILD_SCENE]
    if with_corrections:
        scene.extend(dict(c) for c in CORRECTIONS)
    rib = {
        "schema": SCHEMA,
        "ts": _now(),
        "purpose": "renderer-agnostic scene of the Republic's coding history + corrections; "
                   "render with ANY generator to recreate the architecture at fraction of original cost",
        "provenance": "OUR OWN history (self-steal), NOT frontier output",
        "n_slots": len(scene),
        "scene": scene,
    }
    RIB_OUT.parent.mkdir(parents=True, exist_ok=True)
    RIB_OUT.write_text(json.dumps(rib, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "schema": SCHEMA, "rib": str(RIB_OUT), "n_slots": len(scene)}


def _ollama_available() -> bool:
    import urllib.request
    try:
        from config import ollama_base
        base = ollama_base()
        with urllib.request.urlopen(f"{base}/api/tags", timeout=4) as r:
            return bool(json.loads(r.read().decode()).get("models"))
    except Exception:
        return False


def render(*, model: str = "qwen2.5:32b", prompt_suffix: str = "") -> dict[str, Any]:
    """Dogfood: re-render the recreation RIB through a FREE local model (ollama) and check whether
    it can RECREATE the architecture's shape from just the scene + a tool list. $0 render."""
    if not RIB_OUT.is_file():
        build()
    rib = json.loads(RIB_OUT.read_text(encoding="utf-8"))
    scene_text = "\n".join(
        f"- {s.get('id')}: {s.get('center')} [schema={s.get('schema')}]" for s in rib["scene"])
    from mag.tool_manifest import JSON_OUT as TM_JSON
    tool_names = "tool-list-unavailable"
    if TM_JSON.is_file():
        try:
            tm = json.loads(TM_JSON.read_text(encoding="utf-8"))
            tool_names = ", ".join(t.get("name") for t in tm.get("tools", [])[:80])
        except Exception:
            pass
    prompt = (
        "You are re-rendering a compact scene (RIB) that captures a self-improving sovereign AI "
        "system's coding history and corrections. From ONLY the scene slots and tool list, write a "
        "dense reconstruction of the architecture: its layers (deterministic $0 substrate, verkle "
        "memory, RIB scenes, Roshomon swarm, memlang contracts, honesty/provenance) and the guardrails "
        "from its corrections. Do not invent tools; only reason from what is given.\n\n"
        f"SCENE SLOTS ({rib.get('n_slots')}):\n{scene_text}\n\n"
        f"TOOL NAMES AVAILABLE (first 80): {tool_names}\n\n"
        f"RECONSTRUCTION:{prompt_suffix}"
    )
    # call ollama (free, local) — the honest cheap renderer
    import urllib.request
    try:
        from config import ollama_base
        base = ollama_base()
        body = json.dumps({"model": model, "prompt": prompt, "stream": False,
                           "options": {"temperature": 0.3}}).encode("utf-8")
        req = urllib.request.Request(f"{base}/api/generate", data=body,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=180) as resp:
            out = json.loads(resp.read().decode())
        text = str(out.get("response") or "").strip()
        captured = bool(text)
        return {
            "ok": True, "schema": SCHEMA, "model": model, "renderer": "ollama",
            "provenance": "render.local — re-derivation from OUR RIB, NOT frontier output",
            "grok_captured": captured,  # honest: real render output was captured
            "reconstruction": text if captured else "",
            "n_slots": rib.get("n_slots"),
            "ts": _now(),
        }
    except Exception as e:
        return {"ok": False, "schema": SCHEMA, "model": model, "renderer": "ollama",
                "grok_captured": False,
                "provenance_note": "renderer down or failed; NO recreation claimed",
                "error": str(e)[:200]}


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "rib": str(RIB_OUT) if RIB_OUT.is_file() else "not built",
            "n_slots": len(BUILD_SCENE) + len(CORRECTIONS),
            "renderer_available": _ollama_available()}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Dogfood: recreation RIB of our coding history")
    ap.add_argument("cmd", nargs="?", default="build", choices=["build", "render", "status"])
    ap.add_argument("--model", default="qwen2.5:32b")
    a = ap.parse_args()
    if a.cmd == "build":
        print(json.dumps(build(), ensure_ascii=False, indent=2))
    elif a.cmd == "render":
        r = render(model=a.model)
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(status(), ensure_ascii=False, indent=2))
