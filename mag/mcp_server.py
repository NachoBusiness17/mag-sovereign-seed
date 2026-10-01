"""mcp_server — serve the mag TOOL_MAP over the Model Context Protocol (stdio).

Operator ask (design doc Next #5, 2026-08-25): "serving our tool catalog as MCP
so the bodies consume each other." This is that server. Any MCP-capable body
(zcode, cursor, claude, codex, opencode) spawns it and gets the mag tool
registry NATIVELY — no bridge code, no prompt glue, no seat-specific adapters.

WHY STDIO JSON-RPC BY HAND: the venv has no `mcp`/`fastmcp` package and this
system's law is stdlib-only. MCP is JSON-RPC 2.0 over stdio with a fixed
handshake (initialize → notifications/initialized → tools/list, tools/call) —
small enough to implement exactly, and every byte is inspectable.

SECURITY POSTURE: the tool registry ALREADY runs inside this repo's backend
(the /run_task dispatch lives in backend/server.py, which imports TOOL_MAP
and its dispatch directly; dashboard/rest.py imports no TOOL_MAP -- B2-506
correction 2026-09-26, this doc previously said the dashboard dispatched it).
Spawning this server grants
nothing the local process doesn't already have; it is transport, not authority.
It does NOT expose file paths outside what filesystem.py itself allows.

PIN GATE (2026-09-29, wave5-repair mcp-pin-wire): tools/mcp_pin.py
check_drift() is wired at every connect surface -- serve() gates the profile
surface once at boot and every tools/list through handle() is gated; the
gateway adapter (mag/mcp_http.py) and the dashboard /mcp route pass the same
ledger. First connect pins the surface; a drifted description/schema is
WITHHELD from the served list and alarmed on stderr (fail loud); repin() is
the only way a changed surface returns. Ledger: MAG_MCP_PIN_LEDGER env
override, default state/mcp_pins.jsonl; MAG_MCP_PIN_GATE=off|0|false is the
operator disarm hatch. Direct handle() callers pass pin_ledger=None (gate
off) unless they opt in. Receipt:
watch/inbox/wave5_repair/mcp-pin-wire.md. Closes the dormant-gate gap banked
in watch/inbox/burn_reset_20260927/flash50/mcp-security.md (gap 1) and
flash50/w4-41.md (class-W wiring truth).

Schema: mcp_tool_map.v1 · stdio transport · reuse: tools.TOOL_MAP (single source)
BRIDGE (R1, 2026-09-29): the estate verbs (water tick, dirac scan/rank, dry
chain verify, OUT_DIR-pinned compile, driver status) are registered as static
tools.TOOL_MAP entries wrapping mag/estate_bridge.py and served through the
"bridge" profile; design + per-tool rulings:
watch/inbox/burn_reset_20260927/flash50/mcp-bridge.md (repair, bank, driver
control words and keys are NEVER exposed).
CLI:  python -m mag.mcp_server            (speak MCP on stdio — for clients)
      python -m mag.mcp_server --list     (human list of exposed tools)
      python -m mag.mcp_server --quantize archivist  (stable compact cartridge)
      python -m mag.mcp_server --quantize all --out watch/inbox/MCP_CARTRIDGES.json
      python -m mag.mcp_server --profile builder    (serve a bounded profile)
"""
from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import os
import sys
from pathlib import Path
from typing import Any

SCHEMA = "mcp_tool_map.v1"
PROTOCOL_VERSION = "2025-06-18"
SERVER_INFO = {"name": "mag-tool-map", "version": "1.0.0"}

# These are capability projections, not permission sets.  A spawned server can
# expose fewer tools to a model body to save context and reduce accidental
# surface area; the existing guards/switchboard/effect broker still decide
# whether a call may execute.
ROLE_TOOLSETS: dict[str, tuple[str, ...]] = {
    "archivist": (
        "list_dir", "read_file", "search_files", "blackboard_read",
        "pheromone_trail", "scan_measure", "scan_probe", "scan_grid",
        "mean_field", "whisper_decode",
        "corpus_search", "corpus_get", "corpus_tail", "corpus_stats",
        "research_search", "research_sources", "research_stats",
    ),
    "scout": (
        "list_dir", "read_file", "search_files", "swarm_sense",
        "pheromone_trail", "scan_measure", "scan_probe", "scan_grid",
        "mean_field", "research",
        "corpus_search", "corpus_get", "corpus_tail", "corpus_stats",
        "research_search", "research_sources", "research_stats",
    ),
    "builder": (
        "list_dir", "read_file", "search_files", "write_file", "apply_patch",
        "run_python", "run_shell", "blackboard_read",
    ),
    "adversary": (
        "read_file", "search_files", "blackboard_read", "pheromone_trail",
        "scan_measure", "scan_probe", "scan_grid", "mean_field", "swarm_sense",
    ),
    "governor": (
        "list_dir", "read_file", "search_files", "blackboard_read", "pheromone_trail",
    ),
    "historian": (
        "list_dir", "read_file", "search_files", "blackboard_read", "pheromone_trail",
        "whisper_decode",
        "corpus_search", "corpus_get", "corpus_tail", "corpus_stats",
        "research_search", "research_sources", "research_stats",
    ),
    "salon": (
        "list_dir", "read_file", "search_files", "blackboard_read", "pheromone_trail",
        "research", "vision",
    ),
    "steward": (
        "list_dir", "read_file", "search_files", "blackboard_read", "pheromone_trail",
        "research",
    ),
    "book": (
        "list_dir", "read_file", "search_files", "blackboard_read", "vision",
        "whisper_decode",
    ),
    # estate bridge R1 (2026-09-29, mcp-bridge.md 4.2.1): exactly the estate
    # verbs, nothing else. A profile is a projection, not a permission set;
    # authority stays with the guards/switchboard. Per-tool rulings:
    # chain verify is DRY ONLY (repair never exposed), thought compile is
    # OUT_DIR-pinned, driver status is read-only (control words + keys never
    # cross). Watch: watch/inbox/burn_reset_20260927/flash50/mcp-bridge.md.
    "bridge": (
        "estate_water_graph_tick", "estate_dirac_scan", "estate_dirac_rank",
        "estate_chain_verify", "estate_thought_compile", "estate_driver_status",
    ),
    "full": (),
}

ROLE_DESCRIPTIONS = {
    "archivist": "bounded inventory and lossless evidence retrieval",
    "scout": "low-cost exploration and candidate discovery",
    "builder": "contract-bound implementation and local verification",
    "adversary": "read-only challenge, measurement, and stop-signal generation",
    "governor": "policy inspection without direct effect execution",
    "historian": "continuity, archive, and provenance work",
    "salon": "canon-bound analysis and proposal synthesis",
    "steward": "resource, route, and reservoir analysis",
    "book": "Primer/ractor design review over canonical pointers",
    "bridge": "estate compute bridge: deterministic water physics, read-only "
              "Dirac census, dry chain verify, OUT_DIR-pinned compile, driver "
              "status; no repair, no bank, no keys",
    "full": "backward-compatible complete local tool projection",
}

_READ_TOOLS = {
    "list_dir", "read_file", "search_files", "blackboard_read", "pheromone_trail",
    "scan_measure", "scan_probe", "scan_grid", "mean_field", "swarm_sense",
    "whisper_decode",
    # corpus — the estate catalog surface, read-only, byte-true (2026-09-18)
    "corpus_search", "corpus_get", "corpus_tail", "corpus_stats",
    # research — the fleet's research corpus surface, read-only (2026-09-18)
    "research_search", "research_sources", "research_stats",
    # estate bridge R1 (2026-09-29): tick is deterministic compute, dirac
    # scan/rank read-only census, chain verify is DRY ONLY, driver status is a
    # read (mcp-bridge.md 3.7 effect-class table)
    "estate_water_graph_tick", "estate_dirac_scan", "estate_dirac_rank",
    "estate_chain_verify", "estate_driver_status",
}
_MUTATING_TOOLS = {"write_file", "apply_patch", "run_shell", "run_python",
                   "pheromone_drop", "blackboard_post",
                   # estate bridge R1 (2026-09-29): compile writes, but the
                   # allowlist is one OUT_DIR (mcp-bridge.md 3.5: mutating,
                   # canned-authority tier, not operator-tier)
                   "estate_thought_compile"}
_MODEL_OR_EXTERNAL_TOOLS = {"research", "vision", "voice_turn"}


def _tool_meta(name: str) -> dict[str, str]:
    """Return compact, honest metadata for a capability projection.

    This metadata describes the surface; it never grants the capability.  The
    values intentionally use UNKNOWN where a call-specific meter is required.
    """
    if name in _MUTATING_TOOLS:
        return {
            "effect_class": "mutating_or_executing",
            "risk": "guarded",
            "authority": "switchboard_and_effect_broker",
            "cost_kind": "local_compute_or_unknown",
            "exhaustion": "deny_or_defer",
        }
    if name in _MODEL_OR_EXTERNAL_TOOLS:
        return {
            "effect_class": "model_or_external",
            "risk": "provider_dependent",
            "authority": "broker_or_explicit_refusal",
            "cost_kind": "unknown_until_metered",
            "exhaustion": "reroute_or_stop",
        }
    if name in _READ_TOOLS:
        return {
            "effect_class": "read_or_deterministic_compute",
            "risk": "low_or_local",
            "authority": "read_guard",
            "cost_kind": "deterministic_local",
            "exhaustion": "retry_or_defer",
        }
    return {
        "effect_class": "unknown",
        "risk": "unknown",
        "authority": "explicit_policy_required",
        "cost_kind": "unknown",
        "exhaustion": "operator_gate",
    }


def _load_tool_map() -> dict[str, Any]:
    from tools import TOOL_MAP

    return TOOL_MAP


def _load_tool_functions() -> dict[str, Any]:
    """Load real callables for signatures; TOOL_MAP remains the call registry.

    TOOL_MAP deliberately uses ``**kw`` lambdas for normalization.  Introspecting
    those lambdas produced a fake required ``kw`` argument in the first MCP
    dogfood pass.  The underlying function map is the correct signature source.
    """
    from tools import TOOL_MAP, _FN

    functions = dict(_FN)
    if "vision" not in functions:
        from mag import vision

        functions["vision"] = vision.describe
    for name, fn in TOOL_MAP.items():
        functions.setdefault(name, fn)
    return functions


def _profile_names(profile: str) -> list[str]:
    if profile not in ROLE_TOOLSETS:
        raise ValueError(f"unknown MCP profile: {profile}")
    names = sorted(_load_tool_map())
    selected = ROLE_TOOLSETS[profile]
    if not selected:  # full profile
        return names
    return [name for name in selected if name in names]


def _param_schema(fn: Any) -> dict[str, Any]:
    """Best-effort JSON Schema from the signature (stdlib-only, no registry upkeep).

    The registry stays compiled-from-code: signature drift updates the schema.
    """
    props: dict[str, Any] = {}
    required: list[str] = []
    try:
        sig = inspect.signature(fn)
        real = getattr(fn, "__wrapped__", fn)
        sig = inspect.signature(real)
    except (TypeError, ValueError):
        return {"type": "object", "properties": props}
    for name, p in sig.parameters.items():
        if name in ("self", "kwargs", "args"):
            continue
        t = "string"
        default = p.default if p.default is not inspect.Parameter.empty else None
        annotation = p.annotation
        if isinstance(default, bool) or annotation in (bool, "bool"):
            t = "boolean"
        elif isinstance(default, int) or annotation in (int, "int"):
            t = "integer"
        elif isinstance(default, float) or annotation in (float, "float"):
            t = "number"
        entry: dict[str, Any] = {"type": t}
        if default is not None and not isinstance(default, (bool, int, float)):
            entry["default"] = default
        props[name] = entry
        if p.default is inspect.Parameter.empty:
            required.append(name)
    return {"type": "object", "properties": props, "required": required}


def _input_schema(name: str, fn: Any) -> dict[str, Any]:
    """Input schema for one tool.

    The estate bridge tools carry EXPLICIT hand-written schemas (enum for
    scope, min/max bounds for ticks/sizes that a signature guess cannot
    express, mag/estate_bridge.py BRIDGE_INPUT_SCHEMAS); everything else
    stays signature-derived. Keying the explicit table on the estate_ prefix
    keeps every existing tool's schema byte-identical, so no existing pin in
    the mcp_pin ledger drifts when bridge R1 lands.
    """
    if name.startswith("estate_"):
        from mag.estate_bridge import BRIDGE_INPUT_SCHEMAS

        schema = BRIDGE_INPUT_SCHEMAS.get(name)
        if schema is not None:
            return schema
    return _param_schema(fn)


def tools_manifest(profile: str = "full") -> list[dict[str, Any]]:
    """Return a compact, profile-scoped manifest from live callable signatures."""
    functions = _load_tool_functions()
    out = []
    for name in _profile_names(profile):
        fn = functions[name]
        doc = (inspect.getdoc(getattr(fn, "__wrapped__", fn)) or "").strip().splitlines()
        out.append({
            "name": name,
            "description": (doc[0] if doc else f"mag tool: {name}")[:240],
            "inputSchema": _input_schema(name, fn),
            "_meta": {"mag": {"profile": profile, "quantized": True, **_tool_meta(name)}},
        })
    return out


def pin_ledger_path() -> Path | None:
    """Ledger for the connect-time pin gate, or None when the gate is disarmed.

    MAG_MCP_PIN_LEDGER overrides the ledger path (default state/mcp_pins.jsonl,
    tools/mcp_pin.py DEFAULT_LEDGER).  MAG_MCP_PIN_GATE=off|0|false disarms the
    gate entirely: an operator escape hatch, not the default posture.
    """
    if os.environ.get("MAG_MCP_PIN_GATE", "").strip().lower() in ("0", "off", "false"):
        return None
    override = os.environ.get("MAG_MCP_PIN_LEDGER", "").strip()
    if override:
        return Path(override)
    from tools.mcp_pin import DEFAULT_LEDGER  # lazy: module import stays stdlib-only

    return DEFAULT_LEDGER


def pin_gate_filter(
    manifest: list[dict[str, Any]], ledger_path: str | Path | None
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Connect-time rug-pull gate: run tools/mcp_pin.py check_drift, fail loud.

    NEW and PINNED tools pass unchanged.  A DRIFTED tool (description and/or
    inputSchema hash differs from its pin) is WITHHELD from the served list --
    the mutated description never reaches a model -- and alarmed on stderr;
    tools/mcp_pin.py --repin <tools_list.json> --reason "reviewed" is the only
    way a changed surface returns (the pin doctrine at tools/mcp_pin.py:140-145:
    the alarm blocks, repin is the only way past).  ledger_path=None is a
    passthrough so an operator can disarm without a code edit.
    """
    if ledger_path is None:
        return manifest, {"alarm": False, "enabled": False, "counts": {"drift": 0}, "verdicts": []}
    from tools.mcp_pin import check_drift  # lazy: module import stays stdlib-only

    report = check_drift(manifest, ledger_path=Path(ledger_path))
    if report["alarm"]:
        for alarm in report["alarms"]:
            sys.stderr.write(
                "[mcp_pin] DRIFT ALARM: tool %r %s changed since pin (first_seen %s); "
                "WITHHELD from served surface. Accept after review: "
                'python -m mag.mcp_server --list > tools_list.json && '
                'python tools/mcp_pin.py --repin tools_list.json --reason "reviewed"\n'
                % (alarm["tool_name"], " and ".join(alarm["kind"]), alarm["first_seen"])
            )
        sys.stderr.flush()
    verdict_by_name = {v["tool_name"]: v["verdict"] for v in report["verdicts"]}
    served = [t for t in manifest if verdict_by_name.get(str(t.get("name") or "")) in ("NEW", "PINNED")]
    return served, report


def quantized_manifest(profile: str = "full") -> dict[str, Any]:
    """Build a timestamp-free, content-addressed capability cartridge.

    The cartridge is a projection for model context.  Its digest makes the
    exact tool surface cacheable and auditable; it is not an authority grant.
    """
    tools = tools_manifest(profile)
    body = {
        "schema": "mcp_quantized_manifest.v1",
        "profile": profile,
        "purpose": ROLE_DESCRIPTIONS[profile],
        "authority": "projection_only; execution remains guarded by Mag",
        "source": "tools.TOOL_MAP + tools._FN signatures",
        "tool_count": len(tools),
        "tools": tools,
    }
    canonical = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    body["manifest_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return body


def quantized_cartridges() -> dict[str, Any]:
    """Build every persona cartridge once for shared cache/manifest filing."""
    profiles = {profile: quantized_manifest(profile) for profile in sorted(ROLE_TOOLSETS)}
    body = {
        "schema": "mcp_quantized_cartridges.v1",
        "purpose": "share stable, bounded tool projections between model bodies",
        "authority": "projection_only; execution remains guarded by Mag",
        "profiles": profiles,
    }
    canonical = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    body["cartridges_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return body


def write_quantized_cartridges(path: str | Path, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Atomically file a generated cartridge for other model bodies to read.

    This writes a projection only. It does not register tools, grant effects,
    or alter the live tool registry. The temporary sibling plus ``os.replace``
    prevents a reader from observing a half-written shared cartridge.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    value = payload if payload is not None else quantized_cartridges()
    encoded = json.dumps(value, indent=2, ensure_ascii=False) + "\n"
    temporary = target.with_name(f".{target.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(encoded, encoding="utf-8")
        os.replace(temporary, target)
    finally:
        try:
            temporary.unlink()
        except OSError:
            pass
    return {
        "ok": True,
        "path": str(target),
        "schema": value.get("schema"),
        "cartridges_sha256": value.get("cartridges_sha256"),
        "profile_count": len(value.get("profiles") or {}),
    }


def call_tool(name: str, arguments: dict[str, Any] | None,
              allowed_tools: set[str] | None = None) -> dict[str, Any]:
    """Dispatch through the SAME registry + arg-normalizer the backend uses."""
    from tools import TOOL_MAP, _normalize_args

    if allowed_tools is not None and name not in allowed_tools:
        return {"content": [{"type": "text", "text": json.dumps(
            {"ok": False, "error": f"tool not in active MCP profile: {name}"})}],
                "isError": True}
    args = _normalize_args(name, arguments)
    if args is None:
        return {"content": [{"type": "text", "text": json.dumps(
            {"ok": False, "error": f"unknown tool: {name}"})}], "isError": True}
    try:
        result = TOOL_MAP[name](**args)
    except Exception as e:  # noqa: BLE001 — tool boundary, report don't crash
        return {"content": [{"type": "text", "text": json.dumps(
            {"ok": False, "error": f"{type(e).__name__}: {e}"})}], "isError": True}
    if not isinstance(result, (str, bytes)):
        result = json.dumps(result, ensure_ascii=False, default=str)
    return {"content": [{"type": "text", "text": str(result)}]}


# ────────────────────────────── MCP stdio protocol ──────────────────────────

def _rpc(id_: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": id_, "result": result}


def _err(id_: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": id_, "error": {"code": code, "message": message}}


def handle(
    msg: dict[str, Any],
    profile: str = "full",
    pin_ledger: str | Path | None = None,
) -> dict[str, Any] | None:
    """Serve one JSON-RPC message.

    pin_ledger: when given, every tools/list response is gated through
    pin_gate_filter() against the mcp_pin ledger (drifted tools withheld,
    stderr alarm).  serve() and the HTTP adapters pass the resolved ledger so
    real connects are always gated; direct callers default to None (gate off).
    """
    method = msg.get("method")
    id_ = msg.get("id")
    if method == "initialize":
        return _rpc(id_, {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": SERVER_INFO,
        })
    if method == "notifications/initialized":
        return None  # notification — no response
    if method == "ping":
        return _rpc(id_, {})
    if method == "tools/list":
        manifest: list[dict[str, Any]] = tools_manifest(profile)
        if pin_ledger is not None:
            manifest, _gate = pin_gate_filter(manifest, pin_ledger)
        return _rpc(id_, {"tools": manifest})
    if method == "tools/call":
        p = msg.get("params") or {}
        return _rpc(id_, call_tool(str(p.get("name") or ""), p.get("arguments"),
                                   set(_profile_names(profile))))
    if id_ is not None:
        return _err(id_, -32601, f"method not found: {method}")
    return None


def serve(profile: str = "full") -> int:
    ledger = pin_ledger_path()
    if ledger is not None:
        # Boot gate: alarm at connect even if the client never asks tools/list.
        # The tools/list branch gates again per response (serve passes the
        # ledger through), so a drifted surface can never be served.
        boot, gate = pin_gate_filter(tools_manifest(profile), ledger)
        if gate["alarm"]:
            sys.stderr.write(
                "[mcp_pin] serving %d of %d %s tools; drifted tools withheld until repin\n"
                % (len(boot), gate["counts"]["observed"], profile)
            )
            sys.stderr.flush()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            resp = _err(None, -32700, "parse error")
        else:
            resp = handle(msg, profile, ledger)
        if resp is not None:
            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    ap = argparse.ArgumentParser(prog="mcp-server", description="Serve mag TOOL_MAP over MCP stdio")
    ap.add_argument("--list", action="store_true", help="print the tool manifest and exit")
    ap.add_argument("--profile", choices=sorted(ROLE_TOOLSETS), default="full",
                    help="restrict the exposed projection to one persona profile")
    ap.add_argument("--quantize", choices=["all", *sorted(ROLE_TOOLSETS)], metavar="PROFILE",
                    help="print a stable persona-scoped cartridge, or all profiles")
    ap.add_argument("--out", metavar="PATH",
                    help="atomically file a quantized cartridge (requires --quantize)")
    args = ap.parse_args(argv)
    if args.out and not args.quantize:
        ap.error("--out requires --quantize")
    if args.quantize:
        result = quantized_cartridges() if args.quantize == "all" else quantized_manifest(args.quantize)
        if args.out:
            print(json.dumps(write_quantized_cartridges(args.out, result), ensure_ascii=False))
        else:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    if args.list:
        print(json.dumps(tools_manifest(args.profile), indent=2, ensure_ascii=False))
        return 0
    return serve(args.profile)


if __name__ == "__main__":
    raise SystemExit(main())
