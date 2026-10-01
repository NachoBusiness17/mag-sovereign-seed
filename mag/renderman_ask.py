"""RenderMan-style ask contract + elevation protocol.

"Smart author writes the RIB; the dumb renderer executes." For OUR planned asks:
  - COMPACT locally into a frozen RenderMan spec (the RIB) — goal, research vectors,
    available inputs, executor, output contract, acceptance, quantize target.
  - EXPAND in the LLM — the compact RIB expands into a full prompt, minimizing token bloat
    while carrying the exact research vectors to the frontier model.
  - ELEVATE — when a task needs frontier reasoning, explicitly ask GROK what the executor
    (cheap model, e.g. deepseek-v4-flash) needs to complete it, even passively, so we get the
    exact spec without paying a "stupidity tax" on how to talk to the frontier model.

The ghost and router should know this protocol (see sense_surfaces / routing) so elevation is
always RenderMan-structured, never an ad-hoc novel ask.

Deterministic compact/expand ($0); elevation calls grok (costs). Schema: renderman_ask.v1
CLI:  python -m mag.renderman_ask compact "<goal>" [--vectors a --vectors b] [--rib-out file]
      python -m mag.renderman_ask expand --rib <file>
      python -m mag.renderman_ask elevate "<goal>" [--executor deepseek-v4-flash]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

SCHEMA = "renderman_ask.v1"

RIB_FIELDS = ("goal", "vectors", "inputs", "executor", "output_contract", "acceptance", "quantize_target")


def _specs_dir() -> Path:
    try:
        from config import ROOT
        d = ROOT / "memory" / "runs" / "renderman_specs"
    except Exception:
        d = Path("memory/runs/renderman_specs")
    d.mkdir(parents=True, exist_ok=True)
    return d


def _load_cached_spec(rib_hash: str) -> dict[str, Any] | None:
    p = _specs_dir() / f"{rib_hash}.json"
    if p.is_file():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def _save_cached_spec(rib_hash: str, spec: dict[str, Any]) -> None:
    try:
        (_specs_dir() / f"{rib_hash}.json").write_text(
            json.dumps(spec, ensure_ascii=False, default=str), encoding="utf-8")
    except Exception:
        pass


def _verkle_anchor(rib_hash: str, spec: dict[str, Any]) -> dict[str, Any]:
    """Best-effort: anchor the grok executor-spec into the shared verkle lattice."""
    try:
        from mag.verkle_knot import append_verkle_knot
        dossier = {
            "session_id": f"renderman-{rib_hash}",
            "theme": "renderman_ask",
            "summary": f"RenderMan elevation spec for task {rib_hash}: " + str(spec.get("executor_spec") or "")[:500],
        }
        return append_verkle_knot(dossier) or {"ok": True}
    except Exception:
        return {"ok": False, "error": "verkle unavailable"}


def compact_ask(*, goal: str, vectors: list[str] | None = None, inputs: list[str] | None = None,
                executor: str = "deepseek-v4-flash", output_contract: str = "",
                acceptance: str = "", quantize_target: str = "") -> dict[str, Any]:
    """Build a compact frozen RenderMan spec (the RIB) for a planned ask."""
    rib = {
        "schema": SCHEMA,
        "goal": (goal or "").strip()[:400],
        "vectors": [str(v).strip()[:200] for v in (vectors or []) if str(v).strip()][:8],
        "inputs": [str(i).strip()[:200] for i in (inputs or []) if str(i).strip()][:12],
        "executor": executor,
        "output_contract": (output_contract or "")[:300],
        "acceptance": (acceptance or "")[:300],
        "quantize_target": (quantize_target or "")[:200],
        "rib_hash": "",
    }
    core = {k: rib[k] for k in RIB_FIELDS}
    rib["rib_hash"] = hashlib.sha256(json.dumps(core, ensure_ascii=False, default=str).encode()).hexdigest()[:16]
    return rib


def render_rib(rib: dict[str, Any]) -> str:
    """Compact one-line form for cache/storage (rib_hash proves immutability)."""
    return json.dumps(rib, ensure_ascii=False, separators=(",", ":"))


def expand_ask(rib: dict[str, Any]) -> str:
    """Expand a compact RIB into a full prompt for the LLM (the dumb renderer executes)."""
    lines = [f"GOAL: {rib['goal']}"]
    if rib.get("vectors"):
        lines.append("RESEARCH VECTORS TO CONVEY:\n- " + "\n- ".join(rib["vectors"]))
    if rib.get("inputs"):
        lines.append("AVAILABLE INPUTS:\n- " + "\n- ".join(rib["inputs"]))
    if rib.get("output_contract"):
        lines.append("OUTPUT CONTRACT: " + rib["output_contract"])
    if rib.get("acceptance"):
        lines.append("ACCEPTANCE: " + rib["acceptance"])
    if rib.get("quantize_target"):
        lines.append("QUANTIZE RESULT INTO: " + rib["quantize_target"])
    if rib.get("executor_spec_from_grok"):
        lines.append("EXECUTOR SPEC (from grok elevation):\n" + str(rib["executor_spec_from_grok"]))
    return "\n".join(lines)


def ask_grok_for_executor_spec(goal: str, *, executor: str = "deepseek-v4-flash",
                               context: str = "", tier: str | None = None) -> dict[str, Any]:
    """ELEVATION PROTOCOL: ask grok what the executor needs to complete this task (even passively).

    Returns {ok, executor_spec, model, cost}. Guarded — if grok is unreachable, returns
    ok=False so the rib can still be built without elevation guidance.
    """
    question = (
        f"Given this task, specify the EXACT compact inputs/spec the executor ({executor}) needs "
        f"to complete it successfully: what data, what steps, what output shape, what acceptance "
        f"check. Be terse and exact — no filler. TASK: {goal}"
    )
    try:
        from mag.grok_rightsize import call_grok
        res = call_grok(question, tier=tier, context=context)
        if not getattr(res, "ok", False):
            return {"ok": False, "error": getattr(res, "error", "grok call failed")}
        return {"ok": True, "executor_spec": (res.content or "")[:1200], "model": getattr(res, "model", ""),
                "cost": getattr(res, "cost_est_usd", 0.0)}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


def elevate_ask(*, goal: str, vectors: list[str] | None = None, inputs: list[str] | None = None,
                executor: str = "deepseek-v4-flash", output_contract: str = "", acceptance: str = "",
                quantize_target: str = "", do_grok: bool = True) -> dict[str, Any]:
    """Build the RenderMan rib, optionally asking grok what the executor needs (elevation).

    The grok executor-spec is CACHED by rib_hash and verkle-anchored, so identical tasks
    REUSE it instead of re-asking the frontier (even passively). do_grok=True asks grok only
    on cache miss; if grok is unreachable, the rib still builds (guarded).
    """
    rib = compact_ask(goal=goal, vectors=vectors, inputs=inputs, executor=executor,
                      output_contract=output_contract, acceptance=acceptance,
                      quantize_target=quantize_target)
    h = rib["rib_hash"]
    elevation: dict[str, Any] = {"ok": False, "skipped": not do_grok}
    cached = _load_cached_spec(h)
    if cached:
        elevation = {"ok": True, "cached": True, "executor_spec": cached.get("executor_spec", ""),
                     "model": cached.get("model", ""), "rib_hash": h}
        rib["executor_spec_from_grok"] = elevation["executor_spec"]
        rib["grok_model"] = elevation.get("model", "")
    elif do_grok:
        elevation = ask_grok_for_executor_spec(goal, executor=executor)
        if elevation.get("ok"):
            rib["executor_spec_from_grok"] = elevation["executor_spec"]
            rib["grok_model"] = elevation.get("model", "")
            _save_cached_spec(h, {"executor_spec": elevation["executor_spec"],
                                  "model": elevation.get("model", ""), "rib_hash": h})
            elevation["verkle"] = _verkle_anchor(h, rib)
    return {"rib": rib, "elevation": elevation, "expanded": expand_ask(rib)}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    ap = argparse.ArgumentParser(prog="renderman-ask", description="RenderMan-style ask contract + elevation")
    sub = ap.add_subparsers(dest="cmd")
    pc = sub.add_parser("compact", help="compact a goal into a RenderMan RIB")
    pc.add_argument("goal", nargs="+")
    pc.add_argument("--vectors", action="append", default=[])
    pc.add_argument("--rib-out", default="")
    pe = sub.add_parser("expand", help="expand a RIB file into a full prompt")
    pe.add_argument("--rib", required=True)
    pe.add_argument("--executor", default="deepseek-v4-flash")
    pv = sub.add_parser("elevate", help="build RIB + ask grok what the executor needs")
    pv.add_argument("goal", nargs="+")
    pv.add_argument("--executor", default="deepseek-v4-flash")
    pv.add_argument("--no-grok", action="store_true")
    args = ap.parse_args(argv)
    if args.cmd == "compact":
        rib = compact_ask(goal=" ".join(args.goal), vectors=args.vectors)
        if args.rib_out:
            open(args.rib_out, "w", encoding="utf-8").write(render_rib(rib))
            print(json.dumps({"ok": True, "rib_out": args.rib_out, "rib": rib}, default=str)[:3000])
        else:
            print(render_rib(rib))
    elif args.cmd == "expand":
        rib = json.loads(open(args.rib, encoding="utf-8").read())
        print(expand_ask(rib))
    elif args.cmd == "elevate":
        r = elevate_ask(goal=" ".join(args.goal), executor=args.executor, do_grok=not args.no_grok)
        print(json.dumps(r, default=str)[:6000])
    else:
        ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
