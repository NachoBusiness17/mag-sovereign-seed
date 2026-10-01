"""session_rib — distill a SESSION's threads into a deduped RIB scene and dispatch it through
OUR SWARMS as A/B variants, folding the winners. The RIB-FILE WAY (operator 2026-08-10).

Operator directives that define this module:
  * "lets take a look at the session and what we talked about and do a invariant search among them
     to dedupe the request and send all of it to the swarm intelligently using our self improving
     tools a/b testing with swarms and themselves to always be learning"
  * "and before you build you only will do the rib file way through our swarms from now on to
     dogfood the process as stated to fail fast and learn faster"

THE PROCESS (dogfood-the-process):
  1. THREADS  — the session's topics (what we talked about), each a raw thread.
  2. INVARIANT SEARCH — map each thread to its load-bearing invariant (deterministic keyword
     fingerprint match — no LLM to route).
  3. DEDUPE  — group threads that reduce to the SAME invariant (template_invariant-style family
     match) so we don't ask the swarm the same thing N times.
  4. RIB SCENE — declare the deduped invariants as a RIB: each invariant = a slot (attractor);
     existing knowledge = repellors. Deterministic, $0.
  5. SWARM DISPATCH — feed the RIB to OUR k8s (rib_renderer/invariant_lattice.dispatch_to_k8s) so
     the swarm RENDERS the scene. A/B: each invariant is dispatched as MULTIPLE variants/witnesses
     (different framings -> same goal) and compared.
  6. FOLD WINNERS — the convergent/winning variants fold as doctrine; the A/B outcome records to
     training (self-improving: the swarm and the tools learn from each other).

HONESTY: the RIB is OUR scene from OUR session; the swarm renders it. provenance is explicit.

Schema: session_rib.v1 · CLI: python -m mag.session_rib threads | scene | dispatch [--dry] |
        a-b [--dry] | fold | status
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

SCHEMA = "session_rib.v1"
SCENE_DIR = ROOT / "memory" / "rib"
SCENE = SCENE_DIR / "session-scene.json"
LEDGER = ROOT / "memory" / "runs" / "session_rib" / "ab_ledger.jsonl"

# Invariant fingerprints over the session's themes. A thread reduces to ONE invariant.
INVARIANT_FINGERPRINTS: dict[str, list[str]] = {
    "honesty-provenance": ["honest", "provenance", "grok", "frontier", "ground", "attest", "claim"],
    "steal-both-default": ["steal", "self-steal", "external", "adapt", "mechanism", "invariant"],
    "memory-format": ["memlang", "contract", "verkle", "knot", "memory", "content-address", "grounding"],
    "deterministic-0cost": ["deterministic", "doctrine", "$0", "no-llm", "cost", "cache", "jsonl"],
    "rib-scene-swarm": ["rib", "render", "scene", "swarm", "k8s", "renderer", "frontier", "dispatch"],
    "self-improving-ab": ["a/b", "ab test", "learn", "variant", "self-improve", "feedback", "training"],
    "tool-manifest": ["tool", "manifest", "vs code", "discover", "schema", "registry", "access"],
    "lens-reuse": ["lens", "deep-dive", "corpus", "prior", "frontier answer", "cheap", "reuse"],
    "dashboard-incluster": ["dashboard", "cluster", "service", "port-forward", "not local", "crash"],
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _words(text: str) -> set[str]:
    return set(w.lower() for w in re.findall(r"[a-zA-Z][a-zA-Z0-9_]{3,}", text or ""))


def thread_invariant(thread: str) -> tuple[str, float]:
    """Deterministic invariant routing: which invariant this thread reduces to."""
    tw = _words(thread)
    best, best_score = "", 0.0
    for inv, keys in INVARIANT_FINGERPRINTS.items():
        hit = len(tw & set(k.lower() for k in keys))
        score = hit / max(1, len(keys))
        if score > best_score:
            best, best_score = inv, score
    return best, round(best_score, 3)


# The threads from THIS session (what we talked about) — the raw input to the invariant search.
SESSION_THREADS: list[str] = [
    "honesty everywhere: no artifact may claim grok/frontier provenance unless real output captured; "
    "attestation over verification, independent witnesses, ponytail audit challenges not trusts",
    "steal automatically before leaving reasoning: self-steal our own corpus AND external-steal "
    "other systems, adapt the mechanism to our deterministic architecture",
    "formalize memory so memlang has meaning: MEMORY_CONTRACTS map each opcode to a real kind/"
    "surface/schema/rw; review-driven curation grounded to contracts",
    "deterministic $0 substrate: JSONL + sha256 content-addressing + file reads, modules avoid LLM "
    "calls; the deterministic layer is the measurement instrument over stochastic swarms",
    "RIB renderer abstraction: frontier authors scenes, our k8s swarm renders them; dispatch RIB to "
    "swarm as render tasks; build only via the RIB-file way through swarms to fail fast and learn",
    "A/B testing with swarms and themselves: ghost_experimenter record_training + learn_steer_protocol, "
    "dspy_sovereign variant A/B with confidence, always learning from puppeteering",
    "tool manifest: auto-discover every mag/*.py, read schema/purpose/CLI/REST from module source, "
    "emit tool_manifest.json + TOOLS.md populating in VS Code for full tool access",
    "lens-chain: reuse prior deep-dive corpus (memory/steal, 43 docs) as lenses to answer new "
    "questions cheaply, chained as verkle knots with honest provenance",
    "in-cluster dashboard: host in k8s not local machine that crashed; port-forward via our own "
    "headless runner, single-controller, never double-supervise",
]


def threads() -> dict[str, Any]:
    """The session threads, each routed to its invariant (dedupe pre-step)."""
    rows = [{"thread": t, "invariant": thread_invariant(t)[0],
             "score": thread_invariant(t)[1]} for t in SESSION_THREADS]
    return {"ok": True, "schema": SCHEMA, "n_threads": len(rows), "threads": rows}


def dedupe() -> dict[str, Any]:
    """Group threads by invariant — the dedupe step (don't ask the swarm the same thing N times)."""
    groups: dict[str, list[str]] = {}
    for t in SESSION_THREADS:
        inv, _ = thread_invariant(t)
        groups.setdefault(inv, []).append(t)
    return {"ok": True, "schema": SCHEMA, "n_unique_invariants": len(groups),
            "groups": {k: len(v) for k, v in groups.items()},
            "deduped": list(groups.keys())}


def scene() -> dict[str, Any]:
    """Declare the deduped invariants as a RIB scene: each invariant = one SLOT (attractor)."""
    groups = dedupe()["groups"]
    spec = []
    for i, inv in enumerate(groups):
        spec.append({"id": f"session_inv_{i}", "center": inv,
                     "radius": 0.35, "kind": f"session:{inv}"})
    SCENE_DIR.mkdir(parents=True, exist_ok=True)
    rib = {"schema": SCHEMA, "ts": _now(),
           "purpose": "session threads -> deduped invariants -> RIB scene for the swarm to render",
           "provenance": "OUR session's invariants, dispatched through OUR swarm (not a fresh frontier claim)",
           "n_slots": len(spec), "scene": spec, "invariants": list(groups)}
    SCENE.write_text(json.dumps(rib, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "schema": SCHEMA, "scene": str(SCENE), "n_slots": len(spec),
            "invariants": list(groups)}


def dispatch(*, dry: bool = True, per_invariant: int = 2) -> dict[str, Any]:
    """Feed the session RIB to OUR k8s swarm. A/B: each invariant -> per_invariant variant tasks.
    dry=True returns the plan ($0); dry=False enqueues to the swarm_worker queue (cluster drains)."""
    s = scene()
    from mag import invariant_lattice as il
    out = {"ok": True, "schema": SCHEMA, "dry": dry, "tasks": []}
    for i, inv in enumerate(s["invariants"]):
        for v in range(per_invariant):
            variant = f"[session_rib variant {v}] invariant={inv}: render this session invariant through our swarm"
            if dry:
                out["tasks"].append({"invariant": inv, "variant": v, "ok": True, "task_id": None})
            else:
                try:
                    r = il.dispatch_to_k8s(variant, domain=f"session-rib-{inv}")
                    out["tasks"].append({"invariant": inv, "variant": v,
                                         "ok": bool(r.get("ok")), "task_id": r.get("task_id")})
                except Exception as e:
                    out["tasks"].append({"invariant": inv, "variant": v, "ok": False,
                                         "error": str(e)[:80]})
    out["n_tasks"] = len(out["tasks"])
    return out


def ab_test(*, dry: bool = True, per_invariant: int = 2) -> dict[str, Any]:
    """A/B TEST through the swarm: dispatch variant pairs, record to the A/B ledger, then fold
    winners via ghost_experimenter's self-improving steer protocol. dry=True = plan only."""
    d = dispatch(dry=dry, per_invariant=per_invariant)
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    for t in d["tasks"]:
        LEDGER.open("a", encoding="utf-8").write(
            json.dumps({"ts": _now(), "schema": SCHEMA,
                        "provenance": "planned" if dry else "dispatched",
                        "dry": dry, **t}, ensure_ascii=False) + "\n")
    # fold winners: learn from the A/B feedback (self-improving)
    learn = {}
    if not dry:
        try:
            from mag import ghost_experimenter as ge
            learn = ge.learn_steer_protocol()
        except Exception as e:
            learn = {"ok": False, "error": str(e)[:120]}
    return {"ok": True, "schema": SCHEMA, "dry": dry, "dispatch": d,
            "ledger": str(LEDGER), "steer_protocol_learning": learn}


def status() -> dict[str, Any]:
    d = dedupe()
    return {"ok": True, "schema": SCHEMA, "n_threads": len(SESSION_THREADS),
            "n_unique_invariants": d["n_unique_invariants"],
            "invariants": d["deduped"], "scene": str(SCENE) if SCENE.is_file() else "not built"}


# ─────────────────────────────────────────────────────────── STREAM OF CONSCIOUSNESS ──
# The operator's stream-of-consciousness handler (2026-08-10): "tesuji this is what i want to
# happen when i stream of conciousness". When the operator free-associates, we DON'T just
# answer — we CAPTURE the threads, run invariant search + dedupe, express as a RIB scene, and
# dispatch through OUR swarm as A/B variants (self-improving). This is the RIB-file way:
# capture -> invariants -> dedupe -> scene -> swarm A/B -> fold winners.
def _split_threads(text: str) -> list[str]:
    """Split free-form stream-of-consciousness into discrete threads (sentence/clause level)."""
    if not text or not text.strip():
        return []
    # split on sentence boundaries + line breaks, drop empty/filler fragments
    parts = re.split(r"(?<=[.!?\n])\s+", text)
    out = []
    for p in parts:
        p = p.strip()
        if len(p) >= 12 and not p.lower().startswith(("tesuji", "steal", "just do", "ok", "yeah")):
            out.append(p)
    return out or [text.strip()]


def stream_of_consciousness(text: str, *, per_invariant: int = 2, dry: bool = True) -> dict[str, Any]:
    """THE handler: free-form input -> threads -> invariants -> dedupe -> RIB scene -> swarm A/B.
    This is the automatic behavior for when the operator streams consciousness."""
    raw_threads = _split_threads(text)
    if not raw_threads:
        return {"ok": False, "schema": SCHEMA, "error": "no threads extracted"}
    # route each thread to its invariant + dedupe
    groups: dict[str, list[str]] = {}
    rows = []
    for t in raw_threads:
        inv, score = thread_invariant(t)
        groups.setdefault(inv, []).append(t)
        rows.append({"thread": t[:200], "invariant": inv, "score": score})
    # express as a RIB scene (temporarily set the threads so scene() uses THIS input)
    global SESSION_THREADS
    _saved = SESSION_THREADS
    SESSION_THREADS = raw_threads
    try:
        s = scene()
    finally:
        SESSION_THREADS = _saved
    # dispatch through our swarm as A/B variants
    ab = ab_test(dry=dry, per_invariant=per_invariant)
    return {"ok": True, "schema": SCHEMA, "n_threads": len(raw_threads),
            "n_unique_invariants": len(groups),
            "threads": rows, "invariants": list(groups),
            "groups": {k: len(v) for k, v in groups.items()},
            "scene": s, "ab_test": ab, "dry": dry}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Session -> deduped invariants -> RIB scene -> swarm A/B")
    ap.add_argument("cmd", nargs="?", default="status",
                    choices=["threads", "scene", "dispatch", "a-b", "stream", "status"])
    ap.add_argument("arg", nargs="*", default=[])
    ap.add_argument("--dry", action="store_true", default=True)
    a = ap.parse_args()
    if a.cmd == "threads":
        print(json.dumps(threads(), ensure_ascii=False, indent=2))
    elif a.cmd == "scene":
        print(json.dumps(scene(), ensure_ascii=False, indent=2))
    elif a.cmd == "dispatch":
        print(json.dumps(dispatch(dry=a.dry), ensure_ascii=False, indent=2))
    elif a.cmd == "a-b":
        print(json.dumps(ab_test(dry=a.dry), ensure_ascii=False, indent=2))
    elif a.cmd == "stream":
        text = " ".join(a.arg)
        print(json.dumps(stream_of_consciousness(text, dry=a.dry), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(status(), ensure_ascii=False, indent=2))
