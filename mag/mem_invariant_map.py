"""mem_invariant_map — map OUR invariants through a LOCAL model (mem pointers) for smarter behavior.

Composes the pieces the operator already built (no new machinery, $0, deterministic-ish):

  invariant_lattice (lattice/mycelial view) + knowledge_graph  ->  memlang pointers (32B verkle anchor)
  -> mem_ollama.render_* (LOCAL qwen coder seat = the "slow Diogenes", blunt + grounded)
  -> self_loop zeitgeist (the mapped reading) -> verkle fold + tesuji capture.

RIGHTSIZED FOR THE LOW-VRAM UNIT (2026-08-11): the surface picks the SMALLEST capable local model
unless GPU headroom is CONFIRMED. On a shitty VRAM card we maximize usefulness AND longevity of the
whole unit: tiny model by default, mid coder seat only when gpu_lifecycle says the GPU is actually
free_for_render with headroom. Never OOMs, never spins, degrades to CPU-safe tiny model when the
sampler is blind (source:none). "Fast frontier + slow Diogenes": the local slow reading is the
grounded/ blunt pass; the frontier path stays optional + gated (never auto).

Schema: mem_invariant_map.v1 · deterministic + $0 (local) · guarded everywhere
CLI:  python -m mag.mem_invariant_map status | models | pick | map "<goal>"
"""
from __future__ import annotations

import json
import subprocess
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

SCHEMA = "mem_invariant_map.v1"

# Local seats installed on this unit (name -> (size_gb, tier)). TIER: tiny/mid/big.
# Grounded 2026-08-11 from `ollama list` on the operator's machine.
LOCAL_MODELS = {
    "gemma:2b": (1.7, "tiny"),
    "qwen2.5:3b-instruct": (1.9, "tiny"),
    "qwen-desk:latest": (1.9, "tiny"),
    "qwen2.5vl:3b": (3.2, "mid"),
    "qwen2.5-coder:7b": (4.7, "mid"),     # the "slow as fuck coder seat"
    "gemma4:latest": (9.6, "big"),
    "gemma4-hermes:latest": (9.6, "big"),
    "qwen2.5:32b": (19.0, "big"),         # too big for the low-VRAM unit by default
}

# Default pick per confirmed GPU headroom (maximize usefulness + unit longevity).
TINY_DEFAULT = "qwen2.5:3b-instruct"     # CPU-safe / tight VRAM: small + capable
CODER_SEAT = "qwen2.5-coder:7b"          # the complex-work coder seat (only when GPU headroom confirmed)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _installed() -> list[str]:
    """Live list of ollama models actually pulled (guards on the real unit, not the table)."""
    try:
        r = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=15)
        names = [l.split()[0] for l in r.stdout.splitlines()[1:] if l.strip() and l.split()]
        return names
    except Exception:
        return []


def _gpu_ok() -> tuple[bool, dict[str, Any]]:
    """Is the GPU CONFIRMED free with headroom? Returns (ok, telemetry). Blind sampler => not ok."""
    try:
        from mag.gpu_lifecycle import resources as gr
        g = gr()
        tel = g.get("resources") or {}
        if tel.get("source") in (None, "none"):
            return False, {"free_for_render": False, "source": "none",
                           "note": "GPU sampler blind on this host -> treat as busy (CPU-safe)"}
        free = bool(g.get("free_for_render")) and (tel.get("vram_used_pct", 100) < 80)
        return free, {"free_for_render": free, "vram_used_pct": tel.get("vram_used_pct"),
                      "util_pct": tel.get("util_pct"), "source": tel.get("source")}
    except Exception as e:
        return False, {"error": str(e)[:120]}


def available() -> dict[str, Any]:
    """Available local seats (installed), tier-tagged — the honest surface, not the hardcoded table."""
    inst = _installed()
    rows = []
    for name in inst:
        size, tier = LOCAL_MODELS.get(name, (None, "unknown"))
        rows.append({"model": name, "size_gb": size, "tier": tier})
    return {"ok": True, "schema": SCHEMA, "installed": rows, "count": len(rows)}


def pick_model() -> dict[str, Any]:
    """RIGHT-SIZE the model: tiny by default; coder seat only when GPU headroom is CONFIRMED."""
    inst = set(_installed())
    gpu_ok, tel = _gpu_ok()
    # candidates that are actually installed, small-first (tiny -> mid)
    tiny = [m for m in (TINY_DEFAULT, "gemma:2b", "qwen-desk:latest") if m in inst]
    mid = [m for m in (CODER_SEAT, "qwen2.5vl:3b") if m in inst]
    if gpu_ok and mid:
        model = mid[0]
        tier = "mid (coder seat, complex frontier-style work)"
    else:
        model = tiny[0] if tiny else (inst & set(LOCAL_MODELS.keys()) or {"?"}).pop()
        tier = "tiny (CPU-safe / tight VRAM — longevity of the unit)"
    return {"ok": True, "schema": SCHEMA, "model": model, "tier": tier,
            "gpu_headroom_confirmed": gpu_ok, "gpu": tel,
            "reason": "GPU headroom confirmed -> coder seat" if gpu_ok
                      else "GPU blind/busy -> tiny CPU-safe model (maximize unit life)"}


def point_invariants(limit: int = 8) -> list[dict[str, Any]]:
    """Pull our invariants and compile each to a memlang pointer (32B verkle anchor)."""
    ptrs: list[dict[str, Any]] = []
    invariants: list[str] = []
    try:
        from mag import invariant_lattice
        lat = invariant_lattice.lattice_view()
        # invariant texts live in the lattice/mycelial nodes; collect labels/doctrine generically
        for k in ("lattice", "mycelial", "invariants", "nodes"):
            v = lat.get(k)
            if isinstance(v, list):
                for node in v[:limit]:
                    if isinstance(node, dict):
                        t = node.get("invariant") or node.get("label") or node.get("doctrine") or node.get("text")
                        if isinstance(t, str) and t.strip():
                            invariants.append(t.strip())
    except Exception:
        pass
    # fallback: knowledge_graph "known" surface
    if not invariants:
        try:
            from mag import knowledge_graph as kg
            known = kg.known("sovereign invariant")
            for n in (known.get("known") or [])[:limit]:
                lbl = n.get("label") if isinstance(n, dict) else str(n)
                if lbl:
                    invariants.append(str(lbl))
        except Exception:
            pass
    # compile each to a memlang token pointer (deniable, compact) — guarded per token
    for inv in invariants[:limit]:
        tok = None
        try:
            from mag import memlang
            if hasattr(memlang, "compile_token"):
                tok = memlang.compile_token("steer", inv)
            else:
                tok = memlang.compile("steer", inv)
        except Exception:
            tok = None
        ptrs.append({"invariant": inv[:160], "pointer": (tok or {}).get("token_hex") or
                     (tok if isinstance(tok, str) else None)})
    return ptrs


def map_(goal: str = "") -> dict[str, Any]:
    """MAP invariants through the local coder seat ("slow Diogenes") -> a grounded reading.

    "Fast frontier + slow Diogenes": the local slow model is the blunt/grounded pass over our
    mem pointers. Right-sized to the low-VRAM unit. Guards on model availability + GPU headroom.
    """
    out: dict[str, Any] = {"ok": True, "schema": SCHEMA, "ts": _now(), "goal": (goal or "")[:120]}
    # 1) right-size the model for this unit
    pick = pick_model()
    out["pick"] = {k: pick.get(k) for k in ("model", "tier", "gpu_headroom_confirmed", "reason")}
    model = pick.get("model")
    # 2) map invariants -> mem pointers
    ptrs = point_invariants()
    out["pointers"] = [{"invariant": p["invariant"], "pointer": bool(p["pointer"])} for p in ptrs]
    # 3) render through the local seat (slow Diogenes — blunt, grounded, terse)
    try:
        from mag import mem_ollama
        prompt = (goal or "Read our invariant set and give the blunt, grounded zeitgeist: "
                        "what is the strongest move we should make next? Be Diogenes — terse, honest, "
                        "no flattery. Base it only on the invariants.")
        r = mem_ollama.render_mem(prompt, model=model, timeout=180)
        out["reading"] = (r.get("text") or r.get("content") or str(r))[:1200]
        out["model_used"] = r.get("model") or model
        out["ok"] = bool(r.get("ok", True))
    except Exception as e:
        out["reading_error"] = f"{type(e).__name__}: {e}"
        out["reading"] = ""
    # 4) fold to verkle + record the reading as a steer-able signal (guarded)
    try:
        from mag import verkle_knot
        kn = verkle_knot.append_verkle_knot({
            "session_id": "mem_invariant_map",
            "scalar_knot": {"duration_minutes": 0.1, "tension_index": "1",
                            "residual_weight": 1.0,
                            "theme_vector": {"dominant": "mem_invariant_map",
                                             "basis": ["invariant", "local", "zeitgeist", "memlang"],
                                             "raw": [1, 0, 0, 0], "normalized": [1, 0, 0, 0]}},
            "content_commit": {"hex": (out.get("reading") or "empty")[:64]},
            "rib": {"domain": "mem-invariant-map", "invariant": (out.get("reading") or "")[:400],
                    "source": "local-coder-seat"},
        })
        out["verkle"] = bool(kn.get("ok"))
    except Exception:
        out["verkle"] = False
    return out


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "contract": "available()->installed seats; pick_model()->rightsized model for the low-VRAM "
                        "unit; point_invariants()->invariants as memlang pointers; map_(goal)->local "
                        "reading ('fast frontier + slow Diogenes') folded to verkle",
            "cost": "deterministic + $0 (local)", "models": available()}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="mem-invariant-map")
    ap.add_argument("cmd", nargs="?", default="status",
                    choices=["status", "models", "pick", "map"])
    ap.add_argument("goal", nargs="*", default=[])
    a = ap.parse_args()
    if a.cmd == "models":
        print(json.dumps(available(), indent=2, default=str))
    elif a.cmd == "pick":
        print(json.dumps(pick_model(), indent=2, default=str))
    elif a.cmd == "map":
        print(json.dumps(map_(" ".join(a.goal)), indent=2, ensure_ascii=False, default=str))
    else:
        print(json.dumps(status(), indent=2, ensure_ascii=False, default=str))
