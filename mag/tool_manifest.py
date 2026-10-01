"""tool_manifest — FULL ACCESS to every tool the ghost system exposes, self-updating.

Operator (2026-08-10): "i want to have full access to your tools and understanding of them
i want them to all populate directly in vs code". The schema_registry MANIFEST is hand-maintained
and only lists ~10 modules; this module AUTO-DISCOVERS every mag/*.py (and tools/*.py) module and
extracts, from each module's OWN source (no hand-typing):
    SCHEMA            the self-describing version constant
    purpose           the first docstring line (or __doc__ head)
    CLI               whether it has argparse + its `python -m mag.X ...` line
    REST              which /api/v1/... routes it contributes (from dashboard REST if declared)
    state_file        where it writes state (heuristic: ROOT / "memory" globs)

It emits a single source-of-truth artifact:
    memory/tool_manifest.json   machine-readable (served to the dashboard / REST / VS Code)
    TOOLS.md                    human-readable, written to the workspace root (populates in VS Code)

The manifest is the DISCOVERY surface: ghost, the dashboard, and the operator all read the SAME
file. Nothing is handwaved — every row is read from the module's own code.

Schema: tool_manifest.v1 · deterministic · $0 (pure AST/token scan, no LLM)
CLI:    python -m mag.tool_manifest scan | json | md | status
"""
from __future__ import annotations

import argparse
import ast
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

SCHEMA = "tool_manifest.v1"
MAG_DIR = ROOT / "mag"
TOOLS_DIR = ROOT / "tools"
JSON_OUT = ROOT / "memory" / "tool_manifest.json"
MD_OUT = ROOT / "TOOLS.md"

# Directory globs the module reads state from — used to guess state_file per module.
STATE_HINTS = ["memory", "logs", "state", "configs", "deploy"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _head_doc(module_doc: str | None, n: int = 200) -> str:
    """First meaningful line of a module docstring -> the 'purpose'.""" 
    if not module_doc:
        return ""
    lines = [ln.strip() for ln in module_doc.splitlines() if ln.strip()]
    return (lines[0] if lines else "")[:n]


def _scan_module(path: Path) -> dict[str, Any]:
    """AST-scan ONE module for its self-describing surface (no import, no side effects)."""
    name = path.stem
    try:
        src = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {"name": name, "module": f"mag.{name}", "schema": "", "purpose": "UNREADABLE", "ok": False}
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return {"name": name, "module": f"mag.{name}", "schema": "", "purpose": "SYNTAX-ERR", "ok": False}

    module_doc = ast.get_docstring(tree) or ""
    schema = ""
    has_argparse = False
    has_http = False
    routes: list[str] = []
    for node in tree.body:
        # SCHEMA = "..."
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == "SCHEMA" and isinstance(node.value, ast.Constant):
                    schema = str(node.value.value or "")
        # argparse usage (CLI)
        if isinstance(node, ast.ImportFrom):
            for a in node.names:
                if a.name == "argparse":
                    has_argparse = True
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name == "argparse":
                    has_argparse = True
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            pass
    # REST routes: scan the whole source for /api/v1/... path strings
    routes = sorted(set(re.findall(r'"/api/v1/[^"]+"', src)))
    has_http = bool(routes) or ("http.server" in src or "BaseHTTPRequestHandler" in src)

    cli = ""
    if has_argparse or ("if __name__ == '__main__'" in src and "__main__" in src):
        cli = f"python -m mag.{name}" if path.parent == MAG_DIR else f"python -m tools.{name}"

    # state_file guess: look for ROOT / "memory" writes declared near the top
    state_file = ""
    m = re.search(r'([A-Z_]+)\s*=\s*(ROOT|Path\(__file__\)[^)]*)\s*/\s*"((?:memory|logs|state|configs)/[^"]+)"', src)
    if m:
        state_file = m.group(3)

    return {
        "name": name,
        "module": f"mag.{name}" if path.parent == MAG_DIR else f"tools.{name}",
        "schema": schema or "?",
        "purpose": _head_doc(module_doc),
        "cli": cli,
        "has_http": has_http,
        "routes": routes,
        "state_file": state_file,
        "file": str(path.relative_to(ROOT)).replace("\\", "/"),
        "ok": True,
    }


def scan() -> dict[str, Any]:
    """Discover every mag/*.py + tools/*.py module into the tool manifest."""
    mods: list[dict[str, Any]] = []
    seen: set[str] = set()
    for base, prefix in ((MAG_DIR, "mag"), (TOOLS_DIR, "tools")):
        if not base.is_dir():
            continue
        for p in sorted(base.glob("*.py")):
            if p.name.startswith("_"):
                continue
            if p.stem in seen:
                continue
            seen.add(p.stem)
            row = _scan_module(p)
            row["module"] = f"{prefix}.{p.stem}"
            mods.append(row)
    mods.sort(key=lambda m: m["name"])
    manifest = {
        "schema": SCHEMA,
        "ts": _now(),
        "n_tools": len(mods),
        "tools": mods,
    }
    JSON_OUT.parent.mkdir(parents=True, exist_ok=True)
    JSON_OUT.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def to_markdown(manifest: dict[str, Any] | None = None) -> str:
    """Render the manifest as a human TOOLS.md for the workspace root (populates in VS Code)."""
    man = manifest or (json.loads(JSON_OUT.read_text(encoding="utf-8")) if JSON_OUT.is_file() else scan())
    L: list[str] = []
    L.append("# Tool Manifest — full access to every ghost tool")
    L.append("")
    L.append(f"Auto-generated by `mag.tool_manifest` (schema {SCHEMA}) at {man.get('ts', '')}. "
             f"**{man.get('n_tools', 0)} tools**. Source of truth: `memory/tool_manifest.json`.")
    L.append("")
    L.append("| tool | schema | purpose |")
    L.append("|------|--------|---------|")
    for t in man.get("tools", []):
        purpose = (t.get("purpose") or "").replace("|", "/")
        L.append(f"| `{t.get('name')}` | `{t.get('schema')}` | {purpose} |")
    L.append("")
    L.append("## Detail")
    L.append("")
    for t in man.get("tools", []):
        L.append(f"### `{t.get('module')}` — `{t.get('schema')}`")
        L.append("")
        L.append(f"- **purpose**: {t.get('purpose') or '—'}")
        L.append(f"- **cli**: `{t.get('cli') or '—'}`")
        L.append(f"- **state**: `{t.get('state_file') or '—'}`")
        L.append(f"- **routes**: {', '.join(t.get('routes')) or '—'}")
        L.append("")
    return "\n".join(L)


def write_md(manifest: dict[str, Any] | None = None) -> dict[str, Any]:
    """Write TOOLS.md to the workspace root."""
    md = to_markdown(manifest)
    MD_OUT.write_text(md, encoding="utf-8")
    return {"ok": True, "path": str(MD_OUT), "bytes": len(md.encode("utf-8")), "ts": _now()}


def status() -> dict[str, Any]:
    man = scan()
    return {"ok": True, "schema": SCHEMA, "n_tools": man["n_tools"],
            "json": str(JSON_OUT), "md": str(MD_OUT), "ts": man["ts"]}


def run_scan() -> dict[str, Any]:
    """Full scan + write both artifacts (used by cadence / dashboard / CLI)."""
    man = scan()
    w = write_md(man)
    return {**status(), "md": w, "manifests": man["n_tools"]}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Discover + emit the tool manifest")
    ap.add_argument("cmd", nargs="?", default="scan", choices=["scan", "json", "md", "status"])
    a = ap.parse_args()
    if a.cmd == "scan":
        print(json.dumps(scan(), ensure_ascii=False, indent=2))
    elif a.cmd == "json":
        print(JSON_OUT.read_text(encoding="utf-8"))
    elif a.cmd == "md":
        print(write_md())
    else:
        print(json.dumps(status(), ensure_ascii=False, indent=2))
