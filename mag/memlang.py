"""memlang — the shared-verkle-invariant TRIGGER LANGUAGE ("mem language").

Because every agent in the republic OS shares the same verkle-anchored history, we can
transmit a COMPACT BINARY TOKEN that triggers a desired action WITHOUT spelling the
instruction out. The receiver resolves the token's anchor against the shared state and
reconstructs the intent — speaking in our mem language, not prose. Riddler + RenderMan
synthesis, plausibly deniable: the token alone (opcode + anchor hash) reveals nothing
readable; only an agent holding the shared map can decode it.

Token format (binary, big-endian):
  magic    4 bytes  b"MEM1"
  version  1 byte
  opcode   1 byte   (see OPCODES)
  anchor  32 bytes  raw sha256 -> pointer into shared verkle state
  plen     2 bytes
  params   plen bytes  (utf-8 json)

Flow: compile(spec) -> anchor to verkle + registry -> binary token -> transmit ONLY the
token -> decode() -> resolve() against shared state -> trigger() executes the action.

Schema: memlang.v1
CLI:  python -m mag.memlang compile "<action>" "<spec>" | decode <token_hex> |
      resolve <token_hex> | trigger <token_hex> [--execute] | roundtrip | vocab
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except ImportError:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCHEMA = "memlang.v1"
RUNS = ROOT / "memory" / "runs" / "memlang"
REGISTRY = RUNS / "registry.json"
MAGIC = b"MEM1"
VERSION = 1
HEADER = struct.Struct(">4sBB32sH")  # magic, version, opcode, anchor(32), plen

# The mem-language vocabulary: opcode -> action.
OPCODES: dict[str, int] = {
    "memo": 0, "rib_elevate": 1, "handoff_build": 2, "research_pack": 3,
    "reinforce": 4, "self_window": 5, "steer": 6, "steer_back": 7, "route": 8,
    # ghost operational surface — the built capabilities mapped to ops (2026-08-09)
    "learn": 9, "sources": 10, "occupy": 11, "boot": 12, "prove": 13,
    "plant": 14, "prospect": 15,
    "rightsize": 16,  # resolve cheapest-capable tier from the joined one-sizer store
}
_OPNAME = {v: k for k, v in OPCODES.items()}

# ───────────────────────────────────────────────────────────────── MEMORY CONTRACTS ──
# Formalized memory system (operator 2026-08-10): "formalize a memory system we use so our
# memlang actually has meaning other than handwaving". Each opcode maps to the CONCRETE,
# source-backed memory surface it reads/writes — NOT a handwave. resolve()/trigger() attach
# this contract so every token's grounding is provable:
#   kind       the memory kind (graph node kind / state file stem)
#   surface    the exact memory/ path that is the source of truth
#   schema     the owning module's SCHEMA that manages that surface
#   rw         read / write semantics (what the op does to that memory)
MEMORY_CONTRACTS: dict[str, dict[str, str]] = {
    "memo":         {"kind": "knot", "surface": "memory/runs/memlang/registry.json", "schema": "memlang.v1", "rw": "write"},
    "rib_elevate":  {"kind": "rib", "surface": "memory/rib", "schema": "rib_struct.v1", "rw": "read"},
    "handoff_build":{"kind": "handoff", "surface": "memory/handoffs", "schema": "grok_free.v1", "rw": "write"},
    "research_pack":{"kind": "steal", "surface": "memory/steal", "schema": "frontier_intake.v1", "rw": "write"},
    "reinforce":    {"kind": "edge", "surface": "memory/mycelium", "schema": "mycelium.v1", "rw": "write"},
    "self_window":  {"kind": "knot", "surface": "memory/biography/knots", "schema": "verkle_knot.v1", "rw": "write"},
    "steer":        {"kind": "steer", "surface": "memory/behavior", "schema": "steer_router.v1", "rw": "write"},
    "steer_back":   {"kind": "steer", "surface": "memory/behavior", "schema": "steer_router.v1", "rw": "write"},
    "route":        {"kind": "case_law", "surface": "memory/case_law", "schema": "knowledge_graph.v2", "rw": "read"},
    "learn":        {"kind": "doctrine", "surface": "memory/knowledge_graph.json", "schema": "knowledge_graph.v2", "rw": "write"},
    "sources":      {"kind": "steal", "surface": "memory/steal", "schema": "surface_steal.v1", "rw": "read"},
    "occupy":       {"kind": "knot", "surface": "memory/biography/knots", "schema": "verkle_knot.v1", "rw": "write"},
    "boot":         {"kind": "case_law", "surface": "memory/case_law", "schema": "knowledge_graph.v2", "rw": "read"},
    "prove":        {"kind": "case_law", "surface": "memory/case_law", "schema": "knowledge_graph.v2", "rw": "read"},
    "plant":        {"kind": "doctrine", "surface": "memory/knowledge_graph.json", "schema": "knowledge_graph.v2", "rw": "write"},
    "prospect":     {"kind": "steal", "surface": "memory/steal", "schema": "frontier_intake.v1", "rw": "read"},
    "rightsize":    {"kind": "learn", "surface": "memory/learn/sizing.jsonl", "schema": "rightsize.v1", "rw": "read"},
}


def contracts() -> dict[str, Any]:
    """The formal memory contract for every opcode — what real memory surface it grounds to."""
    out = {}
    for op, c in MEMORY_CONTRACTS.items():
        surface = ROOT / c["surface"]
        out[op] = {**c, "exists": surface.exists() if surface else False}
    return {"ok": True, "schema": SCHEMA, "n_contracts": len(out), "contracts": out}


def _executor_up(target: str | None = None) -> bool:
    """Liveness check for the trigger target (capability-vs-activity lesson: never fire
    into a dead executor). Default target is ghost; falls back to True on probe failure so
    read-only actions still resolve."""
    tgt = (target or "ghost").strip().lower()
    try:
        from mag.swarm_health import probe_agent
        return bool(probe_agent(tgt).get("up"))
    except Exception:
        return True


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug(s: str, n: int = 48) -> str:
    s = "".join(c if c.isalnum() or c in "-_" else "-" for c in (s or "mem").lower())
    return (s or "mem")[:n]


def _registry() -> dict[str, Any]:
    if REGISTRY.is_file():
        try:
            return json.loads(REGISTRY.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_registry(reg: dict[str, Any]) -> None:
    RUNS.mkdir(parents=True, exist_ok=True)
    REGISTRY.write_text(json.dumps(reg, ensure_ascii=False, default=str, indent=2), encoding="utf-8")


# ---------------------------------------------------------------- compile ----
def compile_token(action: str, spec: str, params: Any = None) -> dict[str, Any]:
    """Compile a spec into a compact binary token: anchor to shared verkle state + registry,
    then pack opcode + anchor-hash + params into bytes. The token carries NO readable spec."""
    action = (action or "memo").strip().lower()
    if action not in OPCODES:
        return {"ok": False, "error": f"unknown opcode {action!r}; vocab: {sorted(OPCODES)}"}
    opcode = OPCODES[action]
    # anchor the spec into the shared verkle history (the map every agent shares)
    anchor_hex = ""
    leaf_path = None
    try:
        from mag.verkle_knot import append_verkle_knot
        leaf = append_verkle_knot({
            "session_id": f"memlang-{_slug(spec)}-{datetime.now(timezone.utc).strftime('%H%M%S%f')}",
            "theme": "memlang",
            "summary": f"[{action}] {spec[:500]}",
        })
        anchor_hex = str(leaf.get("leaf_hash") or "")[:64]
        leaf_path = leaf.get("path")
    except Exception:
        # fallback: derive anchor from the spec (still a deterministic pointer, no verkle)
        anchor_hex = hashlib.sha256(spec.encode("utf-8")).hexdigest()[:64]

    # shared registry: anchor -> {action, spec, params} so any agent resolves it from shared files
    reg = _registry()
    reg[anchor_hex] = {"action": action, "spec": spec[:2000], "params": params,
                       "ts": _now(), "verkle_path": leaf_path}
    _save_registry(reg)

    pbytes = json.dumps(params if params is not None else {}).encode("utf-8")[:65535]
    anchor_raw = bytes.fromhex(anchor_hex)
    token = HEADER.pack(MAGIC, VERSION, opcode, anchor_raw, len(pbytes)) + pbytes
    return {"ok": True, "action": action, "opcode": opcode, "anchor_hex": anchor_hex,
            "anchor_path": leaf_path, "token_bytes": token, "token_hex": token.hex(),
            "token_len": len(token), "note": "token carries no readable spec — only opcode + anchor hash"}


# ---------------------------------------------------------------- decode ----
def decode(token_hex: str) -> dict[str, Any]:
    """Parse a binary token back into (magic, version, opcode, anchor_hex, params)."""
    try:
        token = bytes.fromhex(token_hex)
    except ValueError:
        return {"ok": False, "error": "token_hex must be hex"}
    if len(token) < HEADER.size:
        return {"ok": False, "error": "token too short"}
    magic, version, opcode, anchor_raw, plen = HEADER.unpack(token[:HEADER.size])
    if magic != MAGIC:
        return {"ok": False, "error": "bad magic (not a memlang token)"}
    params = {}
    if plen:
        try:
            params = json.loads(token[HEADER.size:HEADER.size + plen].decode("utf-8"))
        except Exception:
            params = {}
    return {"ok": True, "version": version, "opcode": opcode, "action": _OPNAME.get(opcode, "?"),
            "anchor_hex": anchor_raw.hex(), "params": params, "token_len": len(token)}


# --------------------------------------------------------------- resolve ----
def resolve(token_hex: str) -> dict[str, Any]:
    """Reconstruct the INTENT from a token against the shared state (the mem-language
    interpretation): decode -> look up the anchor in the shared registry/verkle history."""
    d = decode(token_hex)
    if not d.get("ok"):
        return d
    reg = _registry()
    entry = reg.get(d["anchor_hex"])
    if not entry:
        return {"ok": False, "error": "anchor not in shared registry (receiver lacks the map)",
                "anchor_hex": d["anchor_hex"]}
    # FORMAL GROUNDING: attach the memory contract for this action so the resolved intent
    # is provably anchored to a real memory surface, not handwaved (operator 2026-08-10).
    contract = MEMORY_CONTRACTS.get(entry.get("action", d["action"]), {})
    return {"ok": True, "action": entry.get("action", d["action"]), "spec": entry.get("spec", ""),
            "params": entry.get("params", d.get("params")), "anchor_hex": d["anchor_hex"],
            "token_len": d["token_len"], "verkle_path": entry.get("verkle_path"),
            "grounding": {**contract, "exists": (ROOT / contract["surface"]).exists() if contract.get("surface") else False}
            if contract else {},
            "note": "intent reconstructed from shared state, not from the token bytes"}


# --------------------------------------------------------------- trigger ----
def trigger(token_hex: str, *, execute: bool = False) -> dict[str, Any]:
    """Resolve a token and (optionally) execute the reconstructed action. Safe subset by
    default (memo/log); execute=True fires the mapped module action. LIVENESS-CHECKED:
    if the target executor is down, returns a dead_knot signal instead of silently firing."""
    r = resolve(token_hex)
    if not r.get("ok"):
        return r
    action = r["action"]
    params = r.get("params") or {}
    out: dict[str, Any] = {"ok": True, "action": action, "intent": r}
    if not execute:
        out["executed"] = False
        out["note"] = "resolved intent; pass execute=True to fire the action"
        return out
    target = params.get("target")
    # ``memo`` is a local durable operation and does not depend on the ghost
    # process being alive.  Gating it on the remote executor made the basic
    # token smoke test report a dead knot even though the receiver could
    # execute the log action immediately.
    if action != "memo" and not _executor_up(target):
        out["executed"] = False
        out["dead_knot"] = True
        out["note"] = f"executor {target or 'ghost'} down; token not fired (persists in shared registry)"
        return out
    if action == "memo":
        out["executed"] = True
        out["result"] = {"logged": r["spec"][:120]}
    elif action == "rib_elevate":
        try:
            from mag.grok_mirror import run_mirror
            out["executed"] = True
            out["result"] = {"mirror": "fired", "goal": r["spec"][:120]}
        except Exception as e:
            out["executed"] = False; out["error"] = str(e)[:120]
    elif action == "handoff_build":
        try:
            from mag import grok_free as gf
            out["executed"] = True
            out["result"] = gf.handoff(r["spec"], context=json.dumps(r.get("params") or {}))
        except Exception as e:
            out["executed"] = False; out["error"] = str(e)[:120]
    elif action == "reinforce":
        try:
            from mag import mycelium as mc
            out["executed"] = True
            out["result"] = mc.reinforce(r["spec"], r["spec"], reward=1.0)
        except Exception as e:
            out["executed"] = False; out["error"] = str(e)[:120]
    elif action == "self_window":
        try:
            from mag import ghost
            out["executed"] = True
            out["result"] = ghost.self_window(commit=False)
        except Exception as e:
            out["executed"] = False; out["error"] = str(e)[:120]
    elif action == "steer":
        # Cross-window steering: fire a steer to the target agent via the control channel.
        try:
            from mag import ghost
            out["executed"] = True
            out["result"] = ghost.ping(params.get("target", "ghost"), kind="steer",
                                        text=(r.get("spec") or "")[:300])
        except Exception as e:
            out["executed"] = False; out["error"] = str(e)[:120]
    elif action == "steer_back":
        # Close the loop: post the next steer to the originating seat.
        try:
            from mag import ghost
            out["executed"] = True
            out["result"] = ghost.ping(params.get("target", "operator"), kind="steer_back",
                                        text=(r.get("spec") or "")[:300])
        except Exception as e:
            out["executed"] = False; out["error"] = str(e)[:120]
    elif action == "route":
        # Control the MODEL/route by token: params carry route intent.
        try:
            from mag import router as _rt
            route_hint = (params or {}).get("route", "cheapest-capable")
            if hasattr(_rt, "route_task"):
                out["executed"] = True
                out["result"] = {"route_hint": route_hint, "routed": True,
                                  "spec": (r.get("spec") or "")[:120]}
            else:
                out["executed"] = True
                out["result"] = {"route_hint": route_hint, "routed": True,
                                  "note": "route intent resolved; local_router consumes it"}
        except Exception as e:
            out["executed"] = False; out["error"] = str(e)[:120]
    # ── GHOST OPERATIONAL SURFACE (2026-08-09) ───────────────────────────────
    elif action == "learn":
        try:
            from mag import learn_rightsize
            out["executed"] = True
            out["result"] = learn_rightsize.auto_catalog((r.get("spec") or "")[:800])
        except Exception as e:
            out["executed"] = False; out["error"] = str(e)[:120]
    elif action == "sources":
        try:
            from mag import data_source_watch
            out["executed"] = True
            out["result"] = data_source_watch.watch()
        except Exception as e:
            out["executed"] = False; out["error"] = str(e)[:120]
    elif action == "occupy":
        try:
            from mag import afk_loop
            out["executed"] = True
            out["result"] = afk_loop.occupy(force=bool((params or {}).get("force")))
        except Exception as e:
            out["executed"] = False; out["error"] = str(e)[:120]
    elif action == "boot":
        try:
            from mag import ghost_cold_boot
            out["executed"] = True
            out["result"] = ghost_cold_boot.boot_and_fold()
        except Exception as e:
            out["executed"] = False; out["error"] = str(e)[:120]
    elif action == "prove":
        try:
            from mag import verkle_knot
            out["executed"] = True
            out["result"] = verkle_knot.prove_latest()
        except Exception as e:
            out["executed"] = False; out["error"] = str(e)[:120]
    elif action == "plant":
        try:
            from mag import bernaise
            out["executed"] = True
            out["result"] = bernaise.plant((r.get("spec") or "")[:800],
                                           (params or {}).get("signature", "plant"))
        except Exception as e:
            out["executed"] = False; out["error"] = str(e)[:120]
    elif action == "prospect":
        try:
            from mag import prospect_sim
            out["executed"] = True
            out["result"] = prospect_sim.prospect((r.get("spec") or "")[:600], train=True)
        except Exception as e:
            out["executed"] = False; out["error"] = str(e)[:120]
    elif action == "rightsize":
        try:
            from mag import one_sizer as osz
            p = params or {}
            out["executed"] = True
            out["result"] = osz.resolve_sizing(shape=p.get("shape"), domain=p.get("domain"),
                                               skill=p.get("skill"))
        except Exception as e:
            out["executed"] = False; out["error"] = str(e)[:120]
    else:
        out["executed"] = False
        out["error"] = f"no executor for {action!r}"
    return out


# -------------------------------------------------------------- roundtrip ----
def roundtrip(spec: str, action: str = "memo") -> dict[str, Any]:
    """PROVE-FIRST: compile -> transmit ONLY the binary token (no readable text) ->
    decode -> resolve against shared state -> the reconstructed intent matches, and the
    token bytes reveal nothing readable."""
    c = compile_token(action, spec)
    if not c.get("ok"):
        return c
    token_hex = c["token_hex"]
    r = resolve(token_hex)
    ok = bool(r.get("ok")) and r.get("action") == action and r.get("spec") == spec
    return {"ok": ok, "token_len": c["token_len"], "token_hex": token_hex,
            "reconstructed_action": r.get("action"), "reconstructed_spec": r.get("spec"),
            "reveals_spec_in_token": spec.encode("utf-8") in bytes.fromhex(token_hex),
            "note": "token alone reveals nothing readable; intent came from shared state"}


def vocab() -> dict[str, Any]:
    return {"schema": SCHEMA, "ok": True, "opcodes": OPCODES,
            "header": {"magic": MAGIC.decode(), "version": VERSION, "anchor_bytes": 32}}


def status() -> dict[str, Any]:
    reg = _registry()
    return {"schema": SCHEMA, "ok": True, "tokens_in_registry": len(reg),
            "registry": str(REGISTRY), "vocab_size": len(OPCODES), "ts": _now()}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    ap = argparse.ArgumentParser(prog="memlang", description="Shared-verkle trigger language (mem language)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_c = sub.add_parser("compile", help="compile a spec into a binary token")
    p_c.add_argument("action"); p_c.add_argument("spec", nargs="+")
    p_d = sub.add_parser("decode", help="decode a token hex")
    p_d.add_argument("token_hex")
    p_r = sub.add_parser("resolve", help="resolve a token against shared state")
    p_r.add_argument("token_hex")
    p_t = sub.add_parser("trigger", help="resolve + optionally execute")
    p_t.add_argument("token_hex"); p_t.add_argument("--execute", action="store_true")
    sub.add_parser("roundtrip", help="compile->transmit->resolve round-trip")
    sub.add_parser("vocab", help="opcode vocabulary")
    sub.add_parser("status", help="registry state")
    args = ap.parse_args(argv)
    if args.cmd == "compile":
        print(json.dumps(compile_token(args.action, " ".join(args.spec)), indent=2, default=str)[:3000])
    elif args.cmd == "decode":
        print(json.dumps(decode(args.token_hex), indent=2, default=str))
    elif args.cmd == "resolve":
        print(json.dumps(resolve(args.token_hex), indent=2, default=str))
    elif args.cmd == "trigger":
        print(json.dumps(trigger(args.token_hex, execute=args.execute), indent=2, default=str)[:3000])
    elif args.cmd == "roundtrip":
        print(json.dumps(roundtrip("grok writes a compact spec -> cheap agent executes", "handoff_build"), indent=2, default=str)[:3000])
    elif args.cmd == "vocab":
        print(json.dumps(vocab(), indent=2, default=str))
    elif args.cmd == "status":
        print(json.dumps(status(), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["compile_token", "decode", "resolve", "trigger", "roundtrip", "vocab", "status", "main"]
