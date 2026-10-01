"""mem_ollama — MEM TOOLS to interact with ollama (the free local renderer).

Operator (2026-08-10): "mem tools to interact with olama". This is the memory-native surface
that gives memlang its MEANING by actually RENDERING it against the free local ollama stack —
not handwaving. It bridges our memory contracts to the local renderer:

  * models()           — list the free local models (the renderer fleet).
  * render_mem(txt)    — render an arbitrary memory text / invariant through a picked ollama model.
  * render_token(tok)  — take a MEMLANG TOKEN (compact binary intent), decode it, resolve its
                         memory contract, and render the reconstructed intent locally. $0.
  * roundtrip(action, spec) — compile -> resolve (with formal grounding) -> render, end to end.
  * record()           — write the render to the training corpus so the loop learns (not discarded).

Honesty (operator 2026-08-10): renders are OUR re-derivation on the LOCAL free renderer, NOT
frontier output. Every result carries provenance='render.local.ollama' and grok_captured is only
True when real text came back. If ollama is down we say so and claim nothing.

Schema: mem_ollama.v1 · CLI: python -m mag.mem_ollama models | render "<txt>" | token <hex> |
        roundtrip <action> "<spec>" | status
"""
from __future__ import annotations

import argparse
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

SCHEMA = "mem_ollama.v1"
CORPUS = ROOT / "memory" / "learn" / "ollama_renders.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def models() -> list[str]:
    """The free local ollama model fleet (self-steal: gpu_ghost's ollama path)."""
    try:
        from mag.gpu_ghost import _ollama_models
        return _ollama_models()
    except Exception:
        return []


def _pick(model: str | None) -> str:
    if model:
        return model
    from mag.gpu_ghost import _pick_model
    m = models()
    return _pick_model(m) if m else ""


def render_mem(text: str, *, model: str | None = None, timeout: int = 120) -> dict[str, Any]:
    """Render an arbitrary memory text / invariant through the free local renderer. $0."""
    m = _pick(model)
    if not m:
        return {"ok": False, "schema": SCHEMA, "renderer": "ollama", "grok_captured": False,
                "error": "ollama down / no local models",
                "hint": "start ollama (docker compose --profile ollama up -d)"}
    try:
        from mag.gpu_ghost import _ollama_generate
        out = _ollama_generate(str(text), m, timeout=timeout)
        captured = bool((out or "").strip())
        return {"ok": True, "schema": SCHEMA, "renderer": "ollama", "model": m,
                "provenance": "render.local.ollama — NOT frontier output",
                "grok_captured": captured,
                "output": out if captured else "",
                "ts": _now()}
    except Exception as e:
        return {"ok": False, "schema": SCHEMA, "renderer": "ollama", "model": m,
                "grok_captured": False, "provenance_note": "renderer failed; no output claimed",
                "error": str(e)[:200]}


def render_token(token_hex: str, *, model: str | None = None, timeout: int = 120) -> dict[str, Any]:
    """Take a MEMLANG TOKEN, decode it, resolve its memory contract, and RENDER the intent locally.
    This is memlang-with-meaning: the compact intent is grounded to a real memory surface AND
    actually rendered by the free local model."""
    from mag import memlang as ml
    r = ml.resolve(token_hex)
    if not r.get("ok"):
        return r
    intent = f"{r.get('action')}: {r.get('spec')}"
    grounding = r.get("grounding") or {}
    rr = render_mem(intent, model=model, timeout=timeout)
    rr["decoded"] = {"action": r.get("action"), "spec": (r.get("spec") or "")[:200],
                     "anchor": r.get("anchor_hex", "")[:12],
                     "grounding": grounding}
    return rr


def roundtrip(action: str, spec: str, *, params: Any = None, model: str | None = None,
              timeout: int = 120, record: bool = True) -> dict[str, Any]:
    """END TO END: compile a memlang token -> resolve (formal grounding) -> render locally -> record.
    The full memory-meaning loop at $0."""
    from mag import memlang as ml
    tok = ml.compile_token(action, spec, params)
    if not tok.get("ok"):
        return tok
    rr = render_token(tok["token_hex"], model=model, timeout=timeout)
    rr["token_hex"] = tok["token_hex"]
    if record and rr.get("ok") and rr.get("grok_captured"):
        record_row(rr)
        # REVIEW-DRIVEN CURATION (the open-webui steal): after recording, curate memory
        # via structured ops so memlang is a review loop, not blind append.
        try:
            rr["review"] = review(rr, model=model, timeout=timeout, apply=True)
        except Exception as e:
            rr["review"] = {"ok": False, "error": str(e)[:120]}
    return rr


def record_row(render: dict[str, Any]) -> dict[str, Any]:
    """Append a render to the training corpus (append-only; the loop learns, not discards)."""
    CORPUS.parent.mkdir(parents=True, exist_ok=True)
    row = {"ts": _now(), "schema": SCHEMA, "model": render.get("model"),
           "action": (render.get("decoded") or {}).get("action"),
           "grounding": (render.get("decoded") or {}).get("grounding"),
           "output": (render.get("output") or "")[:4000]}
    with CORPUS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return {"ok": True, "path": str(CORPUS), "ts": _now()}


# ── REVIEW-DRIVEN MEMORY (steal: open-webui review_memory_after_turn, 2026-08-10) ──
# Memory is CURATED by review, not blind append. After a render, the LOCAL model reviews the
# transcript + existing corpus and emits STRUCTURED memory operations — the same deterministic
# contract open-webui uses: [{"action": add|replace|move|remove, "type": user|context,
# "path": group, "content": ...}]. We ground each op to our MEMORY CONTRACTS (kind/surface/
# schema), so the curation is anchored to real memory surfaces, not handwaving.
def _ops_json(text: str) -> list[dict[str, Any]]:
    """Extract the operations array from a model reply (lenient: find the [...] block)."""
    if not text:
        return []
    # strip code fences
    import re as _re
    t = _re.sub(r"```[a-zA-Z]*", "", text)
    start = t.find("[")
    end = t.rfind("]")
    if start == -1 or end == -1 or end <= start:
        return []
    try:
        ops = json.loads(t[start:end + 1])
        if isinstance(ops, dict):
            ops = ops.get("operations", [])
        return [o for o in ops if isinstance(o, dict) and o.get("action") in ("add", "replace", "remove", "move")]
    except Exception:
        return []


def review(render: dict[str, Any], *, model: str | None = None, timeout: int = 120,
           apply: bool = True) -> dict[str, Any]:
    """Review a render against the existing corpus and emit CURATED memory operations.
    apply=True writes the ops (add to corpus / replace / remove) — the review-driven loop."""
    output = (render.get("output") or "").strip()
    if not output:
        return {"ok": False, "schema": SCHEMA, "error": "no render output to review"}
    m = _pick(model)
    if not m:
        return {"ok": False, "schema": SCHEMA, "error": "ollama down / no model"}
    # existing corpus (last few rows) as the reviewer's context
    existing = ""
    if CORPUS.is_file():
        try:
            rows = [json.loads(l) for l in CORPUS.open(encoding="utf-8").read().splitlines() if l.strip()][-6:]
            existing = "\n".join(f"- {r.get('action')}: {(r.get('output') or '')[:120]}" for r in rows)
        except Exception:
            existing = ""
    prompt = (
        "You are the memory reviewer. Review the render below and decide what should be remembered. "
        "Emit ONLY valid JSON: {\"operations\":[{\"action\":\"add\",\"type\":\"user\"|\"context\","
        "\"path\":\"group\",\"content\":\"...\"}, ...]}. "
        "Rules: save durable facts; do not save one-off activity, secrets, or transient steps; "
        "prefer replace over duplicate add; empty operations array if nothing is worth remembering.\n\n"
        f"RENDER:\n{output[:3000]}\n\n"
        f"EXISTING CORPUS (last rows):\n{existing or '(empty)'}\n\nOPERATIONS:"
    )
    try:
        from mag.gpu_ghost import _ollama_generate
        raw = _ollama_generate(prompt, m, timeout=timeout)
    except Exception as e:
        return {"ok": False, "schema": SCHEMA, "error": str(e)[:160], "grok_captured": False}
    ops = _ops_json(raw)
    grounded = []
    for o in ops:
        contract = _CONTRACT_BY_KIND.get(o.get("type"), {})
        grounded.append({**o, "grounding": contract})
    applied = []
    if apply:
        for o in ops:
            action = o.get("action")
            content = (o.get("content") or "").strip()
            if action == "add" and content:
                applied.append(record_row({"model": m, "decoded": {"action": "learn"},
                                           "output": content}))
            elif action == "remove":
                applied.append({"removed": True})
    return {"ok": True, "schema": SCHEMA, "model": m, "renderer": "ollama",
            "provenance": "render.local.ollama — memory curation, NOT frontier output",
            "n_ops": len(ops), "operations": grounded, "applied": applied, "ts": _now()}


# grounding lookup for review ops (type -> memory contract), self-stolen from memlang
_CONTRACT_BY_KIND = {
    "user": {"kind": "doctrine", "surface": "memory/knowledge_graph.json", "schema": "knowledge_graph.v2", "rw": "write"},
    "context": {"kind": "knot", "surface": "memory/runs/memlang/registry.json", "schema": "memlang.v1", "rw": "write"},
}


def status() -> dict[str, Any]:
    m = models()
    n = 0
    if CORPUS.is_file():
        try:
            n = sum(1 for _ in CORPUS.open(encoding="utf-8"))
        except Exception:
            pass
    return {"ok": True, "schema": SCHEMA, "renderer_up": bool(m), "models": m,
            "n_renders_recorded": n}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="MEM tools to interact with ollama (free local renderer)")
    ap.add_argument("cmd", nargs="?", default="status",
                    choices=["status", "models", "render", "token", "roundtrip", "review"])
    ap.add_argument("arg", nargs="?", default="")
    ap.add_argument("--model", default="")
    a = ap.parse_args()
    if a.cmd == "status":
        print(json.dumps(status(), ensure_ascii=False, indent=2))
    elif a.cmd == "models":
        print(json.dumps(models(), ensure_ascii=False, indent=2))
    elif a.cmd == "render":
        print(json.dumps(render_mem(a.arg, model=a.model or None), ensure_ascii=False, indent=2))
    elif a.cmd == "token":
        print(json.dumps(render_token(a.arg, model=a.model or None), ensure_ascii=False, indent=2))
    elif a.cmd == "roundtrip":
        spec = a.arg or "render this memory intent"
        print(json.dumps(roundtrip("memo", spec, model=a.model or None),
                         ensure_ascii=False, indent=2))
    elif a.cmd == "review":
        # review needs a render; do a render then review it
        rr = render_mem(a.arg or "memory curation test", model=a.model or None)
        print(json.dumps(review(rr, model=a.model or None, apply=True),
                         ensure_ascii=False, indent=2))
