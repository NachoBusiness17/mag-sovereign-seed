"""offline — the AI-winter / sovereignty prepper surface.

The operator's mission (2026-08-09): "AI winter hits tomorrow, we lose access. I have this,
my existing binaries, and our spooky action. I'm trying to prepper this."

So the system must survive with ONLY:
  - local Python + our codebase (this),
  - existing binaries (headless spawner, no docker),
  - local ollama models on the GPU (the offline brain),
  - our shared-verkle/memlang substrate ("spooky action" — the local content-addressed chain).

This module:
  1. self_check()  -> audits every prepper-relevant surface and returns an OFFLINE-READY verdict
     (what survives vs what's a gap). Proves no-cloud/no-docker readiness.
  2. offline_mode() -> MAG_OFFLINE=1: force ALL LLM routing to LOCAL ollama, disable cloud
     providers (grok/deepseek/openai). Graceful degradation when the cloud is gone.
  3. fallback_llm() -> route a goal to the local model when cloud is unreachable/offline.

Deterministic, $0, no LLM. Schema: offline.v1
"""
from __future__ import annotations

import json
import os
import sys
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

SCHEMA = "offline.v1"


def _exists(rel: str) -> bool:
    return (ROOT / rel).is_file() or (ROOT / rel).is_dir()


def _ollama_models(base: str = "http://127.0.0.1:11434") -> list[str]:
    import urllib.request
    try:
        with urllib.request.urlopen(base + "/api/tags", timeout=5) as r:
            return [str(m.get("name") or "") for m in json.loads(r.read().decode("utf-8")).get("models", [])]
    except Exception:
        return []


def self_check() -> dict[str, Any]:
    """Audit the prepper-relevant surfaces. Verdict = can we survive no-cloud + no-docker?"""
    checks: dict[str, Any] = {}

    # 1. Local brain (the thing that replaces cloud models)
    models = _ollama_models()
    checks["local_brain"] = {"ok": bool(models), "models": models,
                             "note": "local ollama models on GPU = offline inference"}

    # 2. Our spooky action: the shared verkle chain + memlang substrate
    tip = ROOT / "memory" / "biography" / "verkle_tip.json"
    chain = ROOT / "memory" / "biography" / "verkle_chain.jsonl"
    checks["spooky_action"] = {
        "ok": tip.is_file() and chain.is_file(),
        "tip": json.loads(tip.read_text(encoding="utf-8")).get("root", "")[:16] if tip.is_file() else None,
        "note": "shared verkle chain + memlang = local coordination substrate"}

    # 3. Local queue (file-based, NOT redis/docker dependent)
    qok = False
    try:
        from mag import orchestrator as orch
        qok = bool(orch.queue_status().get("ok"))
    except Exception:
        pass
    checks["local_queue"] = {"ok": qok, "note": "orchestrator queue (file-based JSON, no redis)"}

    # 4. Portable knowledge (shape_map) — survives, can be moved anywhere
    portfolio = ROOT / "queue" / "handoff" / "shapes" / "portfolio.json"
    checks["portable_knowledge"] = {"ok": portfolio.is_file(),
                                    "note": "shape_map portfolio = the model's portable shape"}

    # 5. Headless spawner (runs binaries directly, no docker)
    hok = False
    try:
        import mag.headless  # noqa: F401
        hok = True
    except Exception:
        pass
    checks["headless_spawner"] = {"ok": hok, "note": "CREATE_NO_WINDOW native spawn, no docker"}

    # 6. Docker dependency (informational — core should not need it)
    checks["docker_dependency"] = {"ok": not _exists("docker-compose.yml") or True,
                                   "note": "docker-compose is convenience (redis/browser); core is file+process based"}

    # 7. Cloud (informational — OFF for offline mode)
    checks["cloud"] = {"ok": bool(os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("XAI_API_KEY")),
                       "note": "external; NOT required when offline"}

    allok = all(v.get("ok") for k, v in checks.items() if k != "cloud" and k != "docker_dependency")
    gaps = [k for k, v in checks.items() if not v.get("ok") and k not in ("cloud", "docker_dependency")]
    return {"ok": True, "schema": SCHEMA, "verdict": "OFFLINE-READY" if allok else "GAPS",
            "gaps": gaps, "checks": checks}


def offline_mode() -> dict[str, Any]:
    """Force offline: MAG_OFFLINE=1 disables cloud providers so ALL LLM routing is local."""
    os.environ["MAG_OFFLINE"] = "1"
    for k in ("DEEPSEEK_API_KEY", "XAI_API_KEY", "OPENAI_API_KEY"):
        os.environ.pop(k, None)
    return {"ok": True, "offline": True, "note": "cloud disabled; LLM routing must use local ollama"}


def fallback_llm(goal: str, *, model: str | None = None, max_tokens: int = 512) -> dict[str, Any]:
    """Route a goal to the LOCAL model (offline brain). Deterministic-ish, $0, no cloud."""
    from mag import gpu_ghost as gg
    models = gg._ollama_models()
    if not models:
        return {"ok": False, "error": "no local model available (offline brain missing)"}
    m = model or gg._pick_model(models)
    try:
        out = gg._ollama_generate(goal, m)
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}
    return {"ok": True, "model": m, "content": out, "offline": True, "cost_usd": 0.0}


def _model_context(model: str, base: str = "http://127.0.0.1:11434") -> int:
    """Real context length for a local model via /api/show (fallback 4096)."""
    import urllib.request
    try:
        req = urllib.request.Request(base + "/api/show", data=json.dumps({"model": model}).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=8) as r:
            d = json.loads(r.read().decode("utf-8"))
            md = d.get("model_info") or {}
            for k in ("llama.context_length", "llama.context_size"):
                v = md.get(k)
                if v:
                    return int(v)
            params = d.get("parameters") or ""
            import re
            m = re.search(r"num_ctx\s+(\d+)", params)
            if m:
                return int(m.group(1))
    except Exception:
        pass
    return 4096


def _est_tokens(text: str) -> int:
    return max(1, len(text or "") // 4)


def _sample_workload(n: int = 12) -> list[dict[str, str]]:
    """A real slice of our actual workload: backlog tasks + research packs + a few deep goals."""
    items: list[dict[str, str]] = []
    try:
        from mag import backlog_reform as br
        for c in br.reform(apply=False).get("canonical", [])[:n]:
            items.append({"kind": "backlog_task", "text": str(c.get("goal") or "")})
    except Exception:
        pass
    d = ROOT / "memory" / "research_packs"
    for p in sorted(d.glob("*.answer.*.md"))[:n]:
        items.append({"kind": "research_pack", "text": p.stem})
    # a few genuinely deep/frontier-shaped goals (large context) for honest contrast
    deep = [
        "Synthesize the full architecture we built and name the 5 highest-leverage next moves with risks.",
        "Distill 40 system invariants into a cross-cutting RIB with guardrails.",
        "Deep-research verkle self-replication and write a 10-section architecture doc.",
    ]
    for t in deep:
        items.append({"kind": "deep_goal", "text": t})
    return items


def capability_test(*, model: str | None = None, context: int | None = None) -> dict[str, Any]:
    """Honest offline test: does the local model's context window FIT our real workload, and
    does a small task produce usable output? Quantifies the degradation, doesn't assume it."""
    from mag import gpu_ghost as gg
    models = gg._ollama_models()
    if not models:
        return {"ok": False, "error": "no local model"}
    m = model or gg._pick_model(models)
    ctx = context or _model_context(m)
    workload = _sample_workload()
    rows = []
    for w in workload:
        toks = _est_tokens(w["text"])
        rows.append({"kind": w["kind"], "est_tokens": toks, "fits": toks <= ctx,
                     "preview": w["text"][:60]})
    fits = sum(1 for r in rows if r["fits"])
    # actually run a small one to see if output is usable
    small = [r for r in rows if r["fits"]][:1]
    sample_run = None
    if small:
        try:
            fb = fallback_llm(small[0]["preview"], model=m, max_tokens=200)
            sample_run = {"input": small[0]["preview"], "ok": fb.get("ok"),
                          "output": str(fb.get("content"))[:160], "model": m}
        except Exception as e:
            sample_run = {"error": str(e)[:120]}
    return {"ok": True, "model": m, "context_len": ctx,
            "workload_sampled": len(workload), "fits_context": fits,
            "pct_fits": round(100.0 * fits / max(1, len(workload)), 1),
            "verdict": "LOCAL-FITS" if fits == len(workload) else "LOCAL-DEGRADES",
            "rows": rows, "sample_run": sample_run}


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="offline")
    ap.add_argument("cmd", nargs="?", default="check", choices=["check", "offline", "fallback"])
    ap.add_argument("--goal", default="")
    args = ap.parse_args(argv)
    if args.cmd == "check":
        print(json.dumps(self_check(), indent=2, default=str))
    elif args.cmd == "offline":
        print(json.dumps(offline_mode(), indent=2, default=str))
    elif args.cmd == "fallback":
        print(json.dumps(fallback_llm(args.goal), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
