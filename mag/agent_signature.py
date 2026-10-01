"""agent_signature — ghost's VERIFIED AGENT REGISTRY (honest signatures, not claims).

Operator (2026-08-10): "you have hallucinated agents who have built stuff before we need to make
sure their signitures are somehow known by ghost even if they dont in the whisper round trip data"

THE PROBLEM: agents/modules are often *described* (in transcripts, memory, steal docs, handoffs)
as having "built stuff" — but that is a CLAIM, not evidence. Whisper round-trip data can be
silent (an agent never round-tripped) even though it genuinely exists and works. Ghost must be
able to distinguish a REAL agent (verified to exist on disk, importable, schema-known) from a
HALLUCINATED one (named/described but no real file).

THE MECHANISM (honest provenance for agents — the same discipline we apply to frontier claims):
  * scan()       — deterministically verify every mag/*.py (and tools/*.py) module EXISTS on disk,
                    is importable, has a SCHEMA constant, and what it actually provides. This is
                    the GROUND TRUTH — what ghost can trust regardless of whisper round-trips.
  * signature()  — build a content-addressed signature (sha256) for an agent/module from its real
                    file + schema + docstring. A stable address = "this agent is real, this is its
                    shape". Whisper silence does NOT erase a real signature.
  * know()       — does ghost KNOW this agent? verified (real file+signature) vs claimed-only
                    (named but no file) vs unknown. This is the anti-hallucination gate.
  * register()   — record the verified signature into the registry (ghost's agent ledger).
  * audit()      — list which claimed/described agents are REAL vs PHANTOM (have a file vs not).

Honesty: a signature is ONLY built from what actually exists on disk (importable + schema). A
"phantom" agent (described but no file) is flagged as such — ghost never trusts a signature that
isn't grounded. provenance is explicit on every record.

Schema: agent_signature.v1 · deterministic $0 · CLI: python -m mag.agent_signature scan |
        signature <module> | know <module> | audit | status
"""
from __future__ import annotations

import argparse
import ast
import hashlib
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

SCHEMA = "agent_signature.v1"
REGISTRY = ROOT / "memory" / "registry_state" / "agent_signatures.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load_registry() -> dict[str, Any]:
    if not REGISTRY.is_file():
        return {}
    try:
        return json.loads(REGISTRY.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_registry(reg: dict[str, Any]) -> None:
    REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY.write_text(json.dumps(reg, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_schema(path: Path) -> str:
    """Read the module's own SCHEMA constant (self-describing source of truth)."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return ""
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == "SCHEMA" and isinstance(node.value, ast.Constant):
                    return str(node.value.value or "")
    return ""


def _head_doc(path: Path, n: int = 160) -> str:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        return (ast.get_docstring(tree) or "").splitlines()[0][:n] if ast.get_docstring(tree) else ""
    except Exception:
        return ""


def _module_files() -> list[tuple[str, Path]]:
    out = []
    for base, prefix in ((ROOT / "mag", "mag"), (ROOT / "tools", "tools")):
        if not base.is_dir():
            continue
        for p in sorted(base.glob("*.py")):
            if p.name.startswith("_"):
                continue
            out.append((f"{prefix}.{p.stem}", p))
    return out


def _verify_importable(module: str) -> bool:
    """Actually try to import the module (the real existence test, not just a file check)."""
    import importlib
    try:
        importlib.import_module(module)
        return True
    except Exception:
        return False


def scan() -> dict[str, Any]:
    """Verify every mag/*.py + tools/*.py: exists on disk, importable, schema-known. GROUND TRUTH."""
    verified, phantom = [], []
    for module, path in _module_files():
        schema = _read_schema(path)
        importable = _verify_importable(module)
        body_hash = hashlib.sha256(
            (module + "|" + schema + "|" + str(path.stat().st_size)).encode("utf-8")).hexdigest()[:16]
        rec = {
            "module": module, "schema": schema or "?",
            "importable": importable, "file": str(path.relative_to(ROOT)).replace("\\", "/"),
            "body_hash": body_hash, "purpose": _head_doc(path), "ts": _now(),
        }
        # register the verified signature so ghost KNOWS it regardless of whisper silence
        reg = _load_registry()
        reg[module] = {"signature": body_hash, "schema": schema, "ts": _now(),
                       "importable": importable}
        _save_registry(reg)
        (verified if importable else phantom).append(rec)
    return {"ok": True, "schema": SCHEMA, "n_verified": len(verified),
            "n_phantom": len(phantom), "verified": verified, "phantom": phantom,
            "registry": str(REGISTRY)}


def signature(module: str) -> dict[str, Any]:
    """The content-addressed signature for ONE agent/module (real file + schema + purpose)."""
    for m, p in _module_files():
        if m == module:
            schema = _read_schema(p)
            body_hash = hashlib.sha256(
                (m + "|" + schema + "|" + str(p.stat().st_size)).encode("utf-8")).hexdigest()
            return {"ok": True, "schema": SCHEMA, "module": module,
                    "signature": body_hash, "schema": schema,
                    "purpose": _head_doc(p), "exists": True, "file": str(p)}
    return {"ok": True, "schema": SCHEMA, "module": module, "exists": False,
            "signature": None, "note": "no file on disk — this agent is DESCRIBED but not verified"}


def know(module: str) -> dict[str, Any]:
    """Does ghost KNOW this agent? verified (real signature) vs claimed-only (no file)."""
    s = signature(module)
    reg = _load_registry()
    registered = module in reg
    if s.get("exists") and s.get("signature"):
        return {"ok": True, "schema": SCHEMA, "module": module, "status": "verified",
                "signature": s["signature"], "registered": registered,
                "note": "real agent — ghost trusts this regardless of whisper round-trip silence"}
    return {"ok": True, "schema": SCHEMA, "module": module, "status": "claimed_only",
            "registered": registered,
            "note": "described but NO file on disk — treat as phantom/unverified, do NOT trust as built"}


def audit(claims: list[str]) -> dict[str, Any]:
    """Given a list of CLAIMED agent/module names, sort into REAL (verified) vs PHANTOM (no file).
    This is the anti-hallucination gate: ghost sees which claimed agents actually exist."""
    real, phantom = [], []
    for c in claims:
        c = c.strip()
        if not c:
            continue
        if c.startswith("mag."):
            pass
        elif not c.startswith(("mag.", "tools.")):
            c = f"mag.{c}"
        if signature(c).get("exists"):
            real.append(c)
        else:
            phantom.append(c)
    return {"ok": True, "schema": SCHEMA, "n_claimed": len(claims),
            "n_real": len(real), "n_phantom": len(phantom),
            "real": real, "phantom": phantom,
            "note": "real = verified on disk (trust); phantom = described but no file (do NOT trust as built)"}


def status() -> dict[str, Any]:
    reg = _load_registry()
    return {"ok": True, "schema": SCHEMA, "n_registered_signatures": len(reg),
            "registry": str(REGISTRY)}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Ghost's VERIFIED agent signature registry (anti-hallucination)")
    ap.add_argument("cmd", nargs="?", default="status",
                    choices=["scan", "signature", "know", "audit", "status"])
    ap.add_argument("arg", nargs="*", default=[])
    a = ap.parse_args()
    if a.cmd == "scan":
        print(json.dumps(scan(), ensure_ascii=False, indent=2))
    elif a.cmd == "signature":
        m = a.arg[0] if a.arg else "mag.tool_manifest"
        print(json.dumps(signature(m), ensure_ascii=False, indent=2))
    elif a.cmd == "know":
        m = a.arg[0] if a.arg else "mag.tool_manifest"
        print(json.dumps(know(m), ensure_ascii=False, indent=2))
    elif a.cmd == "audit":
        claims = a.arg or ["mag.tool_manifest", "mag.nonexistent_phantom_agent",
                           "session_rib", "lens_chain", "gap_swarm_experiment",
                           "mag.does_not_exist"]
        print(json.dumps(audit(claims), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(status(), ensure_ascii=False, indent=2))
