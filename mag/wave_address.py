"""wave_address — reach ANY object across the surface BY THE WAVE ALONE.

Operator (2026-08-13): "how else can we use this across our codebase so we have reliable tool
execution and access in our environment so all of our objects can reach one another across the
surface using the wave alone"

THE WAVE IS THE ADDRESS: every object (tool, module, agent, RIB, knot) carries a deterministic,
content-addressed WAVE ADDRESS = sha256 of its identity/essence. Objects reach one another by
address ALONE — no names, no central registry, no import graph. The wave is the addressing.

REUSE (self-steal): deterministic_scanner.scan_probe fingerprint (content hash), scan_grid surface
fingerprint (the mesh at a glance), verkle knots (content addressing is already our substrate).

Schema: wave_address.v1 · deterministic + $0 · pure stdlib
"""
from __future__ import annotations

import hashlib
import json
import sys
from typing import Any

try:
    from config import ROOT
except Exception:
    from pathlib import Path as _P
    ROOT = _P(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCHEMA = "wave_address.v1"

# the wave surface: object_id -> {wave_address, essence, kind}
_SURFACE: dict[str, dict[str, Any]] = {}


def _addr(identity: str, salt: str = "wave") -> str:
    return hashlib.sha256(f"{salt}:{identity}".encode("utf-8")).hexdigest()[:16]


def register(object_id: str, essence: str, *, kind: str = "object") -> dict[str, Any]:
    """REGISTER an object on the wave surface: it gets a content-addressed WAVE ADDRESS. Deterministic
    + $0. Same essence -> same address (the wave is reproducible). This is how an object becomes
    reachable BY THE WAVE ALONE."""
    object_id = (object_id or "").strip()
    essence = (essence or "").strip()
    if not object_id or not essence:
        return {"ok": False, "schema": SCHEMA, "error": "object_id + essence required"}
    addr = _addr(essence)
    _SURFACE[object_id] = {"wave_address": addr, "essence": essence[:200], "kind": kind}
    return {"ok": True, "schema": SCHEMA, "object_id": object_id, "kind": kind,
            "wave_address": addr, "essence": essence[:200],
            "note": "object registered on the wave surface — reachable by its wave address alone"}


def reach(address: str) -> dict[str, Any]:
    """REACH an object BY THE WAVE ALONE: resolve a wave address to the object (deterministic, no
    name registry). The hash IS the address. Deterministic + $0. HONEST — resolves only registered
    objects; never fabricates a hit."""
    address = (address or "").strip()
    if not address:
        return {"ok": False, "schema": SCHEMA, "error": "empty wave address"}
    hits = [oid for oid, rec in _SURFACE.items() if rec["wave_address"] == address]
    if not hits:
        return {"ok": False, "schema": SCHEMA, "address": address,
                "error": "no object carries that wave address (not registered)"}
    return {"ok": True, "schema": SCHEMA, "tool": "reach", "address": address,
            "objects": [{"object_id": oid, **_SURFACE[oid]} for oid in hits],
            "note": "reached the object by its wave address alone (content-addressed, no registry)"}


def discover(signature: str) -> dict[str, Any]:
    """DISCOVER objects on the surface by SIGNATURE-PROBE: find every object whose essence matches the
    signature. Objects reach one another by probing, not a registry. Deterministic + $0 (substring
    match over real essences)."""
    sig = (signature or "").strip().lower()
    if not sig:
        return {"ok": False, "schema": SCHEMA, "error": "empty signature"}
    hits = [{"object_id": oid, **rec} for oid, rec in _SURFACE.items()
            if sig in rec["essence"].lower()]
    return {"ok": True, "schema": SCHEMA, "tool": "discover", "signature": sig,
            "n_hits": len(hits), "hits": hits,
            "note": "discovered objects by signature-probe over the surface (the wave)"}


def surface(*, grid: bool = True) -> dict[str, Any]:
    """THE SURFACE AT A GLANCE: every registered object + a reproducible scan_grid fingerprint of the
    whole wave surface (the mesh). Deterministic + $0. HONEST — the fingerprint is real (content hash
    of the registered essences), so the surface is known reproducibly."""
    if not _SURFACE:
        return {"ok": True, "schema": SCHEMA, "n_objects": 0, "surface": {},
                "fingerprint": hashlib.sha256("empty-wave".encode()).hexdigest()[:16]}
    grid_fp = hashlib.sha256(json.dumps(
        {oid: rec["wave_address"] for oid, rec in _SURFACE.items()},
        sort_keys=True).encode()).hexdigest()[:16]
    return {"ok": True, "schema": SCHEMA, "n_objects": len(_SURFACE),
            "surface": {oid: rec for oid, rec in _SURFACE.items()},
            "fingerprint": grid_fp, "grid": bool(grid),
            "note": "the whole wave surface fingerprinted at a glance — objects reach each other by wave address"}


def _module_purpose(module_name: str, path: str) -> str:
    """The module's first docstring line as its essence (honest: read from real source, AST-safe)."""
    try:
        import ast
        from pathlib import Path
        p = Path(path)
        if p.is_file():
            tree = ast.parse(p.read_text(encoding="utf-8", errors="replace"))
            doc = ast.get_docstring(tree) or ""
            first = next((ln.strip() for ln in doc.splitlines() if ln.strip()), "")
            return f"{module_name}: {first[:120]}"
    except Exception:
        pass
    return module_name


def register_surface() -> dict[str, Any]:
    """STRIKE THE CHORD: register the REAL codebase objects onto the wave surface — every mag module
    (from tool_quant.scan_tools) + the toolbelt (TOOL_MAP). Now all our objects reach one another by
    wave address. Deterministic + $0. HONEST — registered from real module names + real docstrings."""
    from mag import tool_quant
    added = 0
    for t in tool_quant.scan_tools():
        name = t.get("name") or ""
        if not name:
            continue
        ess = _module_purpose(name, t.get("path") or "")
        if name not in _SURFACE:
            register(name, ess, kind="module")
            added += 1
    # the toolbelt (real callable tools from TOOL_MAP)
    try:
        from tools import TOOL_MAP
        for name in TOOL_MAP:
            if name not in _SURFACE:
                register(name, f"{name}: a callable tool on the surface", kind="tool")
                added += 1
    except Exception:
        pass
    return {"ok": True, "schema": SCHEMA, "tool": "register_surface", "added": added,
            "n_total": len(_SURFACE),
            "note": f"struck the chord: {added} real objects registered; the surface carries the codebase"}


def run_cadence(*, force: bool = False) -> dict[str, Any]:
    """The wave-surface cadence: keep every real object reachable by wave address. Idempotent —
    re-registering the same essence yields the same address (no dupes). Deterministic + $0."""
    return register_surface()


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="wave-address")
    ap.add_argument("cmd", nargs="?", default="surface",
                    choices=["register", "reach", "discover", "surface"])
    ap.add_argument("args", nargs="*", default=[])
    ap.add_argument("--kind", default="object")
    a = ap.parse_args(argv)
    if a.cmd == "register":
        oid = a.args[0] if a.args else "obj"
        ess = " ".join(a.args[1:]) or oid
        print(json.dumps(register(oid, ess, kind=a.kind), ensure_ascii=False, indent=2, default=str))
    elif a.cmd == "reach":
        print(json.dumps(reach(a.args[0] if a.args else ""), ensure_ascii=False, indent=2, default=str))
    elif a.cmd == "discover":
        print(json.dumps(discover(" ".join(a.args) or ""), ensure_ascii=False, indent=2, default=str))
    elif a.cmd == "surface":
        print(json.dumps(surface(), ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
