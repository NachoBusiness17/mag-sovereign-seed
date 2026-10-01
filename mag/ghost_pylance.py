"""ghost_pylance — steal Pylance as GHOST MEMTOOLS (deterministic code-intelligence memtools).

Operator (2026-08-10): "how could we steal pylance as ghost memtools."

STEAL ANALYSIS:
  * EXTERNAL — Pylance/Pyright is a fact-grounded, deterministic code-intelligence engine
    (diagnostics, references, definitions, symbols, value-provenance tracing, import audit).
    Its VALUE to the ghost is GROUNDING: the ghost reasons over stochastic memory, but it can
    VERIFY and CORRECT that work against a deterministic ground-truth analysis of our own code.
    We steal the *capabilities* (the analysis model), not any prompt DNA.
  * SELF — the framework already does AST analysis (code_map) and py_compile verification. We
    reuse that floor and lift it into a ghost-facing memtool surface.
  * ENGINE — real pylance/pyright is NOT installed in the venv, so we implement the DETERMINISTIC
    FLOOR in-process with the stdlib `ast` (tier C, $0). If a real `pyright`/`pylance` binary is
    later reachable, these become a thin bridge to it; the contract stays the same.

MEMTOOLS (the ghost's code-intelligence organs):
  diagnose(module)      - AST diagnostics: syntax errors, undefined names, unused imports.
  symbols(module)       - document symbol map (defs/classes/assigns with lines).
  references(symbol)    - cross-file usages across the workspace (like Pylance references).
  trace_value(m,sym)    - value PROVENANCE via AST (how a symbol got its value; like traceValue).
  imports()             - dependency audit of our own codebase (resolved vs not).
  self_check()          - syntax-check ALL our modules (the "N/N modules syntax-clean" bead).

Schema: ghost_pylance.v1 · deterministic $0 · CLI: python -m mag.ghost_pylance <tool>
"""
from __future__ import annotations

import ast
import builtins
import importlib.util
import json
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

SCHEMA = "ghost_pylance.v1"
SCAN_DIRS = ["mag", "tools", "scripts", "harness", "router", "backend"]
_BUILTINS = set(dir(builtins))


def _module_path(module_rel: str) -> Path:
    p = ROOT / module_rel
    if not p.suffix:
        p = p.with_suffix(".py")
    return p


def _modules() -> list[Path]:
    seen: set[Path] = set()
    out = []
    for d in SCAN_DIRS:
        base = ROOT / d
        if not base.is_dir():
            continue
        for py in sorted(base.glob("*.py")):
            if py.name.startswith("_") or py.name.startswith("test_"):
                continue
            if py in seen:
                continue
            seen.add(py)
            out.append(py)
    return out


def _defined_names(tree: ast.AST) -> set[str]:
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    names.add(t.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, ast.Import):
            for a in node.names:
                names.add((a.asname or a.name).split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            for a in node.names:
                names.add(a.asname or a.name)
        elif isinstance(node, ast.arg):
            names.add(node.arg)
    return names


def _used_names(tree: ast.AST) -> set[str]:
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            names.add(node.id)
    return names


def _annotation_names(tree: ast.AST) -> set[str]:
    """Name-references that appear INSIDE type annotations (steal: Pylance resolves these).

    Type hints (returns, arg annotations, AnnAssign annotations, TypeAlias) reference names like
    `Any`, `Path`, `Callable` that our AST floor can't always prove are imported/builtin. Pylance
    resolves them; to kill the false positives, we treat annotation-only references as KNOWN
    (a real typo inside a type hint is a different, rarer bug). This is the import/annotation-aware
    refinement surfaced by dogfooding verify_edit on clean files.
    """
    names: set[str] = set()
    def _collect(n: ast.AST | None) -> None:
        for node in ast.walk(n) if n is not None else []:
            if isinstance(node, ast.Name):
                names.add(node.id)
    for node in ast.walk(tree):
        if isinstance(node, ast.AnnAssign) and node.annotation:
            _collect(node.annotation)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.returns:
            _collect(node.returns)
        if isinstance(node, ast.arg) and node.annotation:
            _collect(node.annotation)
    return names


def _import_names(tree: ast.AST) -> list[str]:
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                out.append(a.asname or a.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            for a in node.names:
                out.append(a.asname or a.name)
    return out


def diagnose(module_rel: str) -> dict[str, Any]:
    """AST diagnostics for one module: syntax errors, undefined names, unused imports."""
    p = _module_path(module_rel)
    if not p.is_file():
        return {"ok": False, "schema": SCHEMA, "error": f"no module {module_rel}"}
    src = p.read_text(encoding="utf-8", errors="replace")
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        return {"ok": True, "schema": SCHEMA, "module": module_rel, "syntax_ok": False,
                "syntax_error": {"line": e.lineno, "msg": str(e.msg)}}
    defined = _defined_names(tree)
    used = _used_names(tree)
    # annotation-aware: don't flag type-hint references (import-aware steal from Pylance)
    undefined = sorted((used - defined - _BUILTINS) - _annotation_names(tree))
    imported = _import_names(tree)
    used_text = src
    unused_imports = [i for i in imported if used_text.count(i) <= 1]
    return {"ok": True, "schema": SCHEMA, "module": module_rel, "syntax_ok": True,
            "n_undefined_candidates": len(undefined), "undefined": undefined[:30],
            "unused_imports": unused_imports[:20], "defined_count": len(defined)}


def verify_edit(file_rel: str) -> dict[str, Any]:
    """Verify a just-edited file with OUR AST tool (the get_errors replacement, diff-free).

    Operator (2026-08-11): "why are you defaulting to pylance and not your own tool usage so we can
    refine them?" — this is the deterministic $0 surface for checking that an edit landed and is
    sound: syntax_ok + no undefined names + no unused imports, one clean verdict. Use THIS (or
    ghost_pylance.diagnose) instead of the external Pylance get_errors surface.
    """
    d = diagnose(file_rel)
    if not d.get("ok"):
        return d
    verdict = ("CLEAN" if (d.get("syntax_ok") and not d.get("undefined")
                           and not d.get("unused_imports"))
               else "NEEDS_ATTENTION")
    return {"ok": True, "schema": SCHEMA, "module": file_rel, "verdict": verdict,
            **{k: d.get(k) for k in ("syntax_ok", "syntax_error", "n_undefined_candidates",
                                     "undefined", "unused_imports", "defined_count")},
            "note": "verified via ghost_pylance (our AST memtool), not external Pylance; no git diff"}


def symbols(module_rel: str) -> dict[str, Any]:
    """Document symbol map: defs/classes/assigns with line numbers."""
    p = _module_path(module_rel)
    if not p.is_file():
        return {"ok": False, "error": f"no module {module_rel}"}
    try:
        tree = ast.parse(p.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError as e:
        return {"ok": True, "schema": SCHEMA, "module": module_rel, "syntax_ok": False,
                "error": f"line {e.lineno}: {e.msg}"}
    syms = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            syms.append({"kind": "function", "name": node.name, "line": node.lineno})
        elif isinstance(node, ast.ClassDef):
            syms.append({"kind": "class", "name": node.name, "line": node.lineno})
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    syms.append({"kind": "var", "name": t.id, "line": node.lineno})
    return {"ok": True, "schema": SCHEMA, "module": module_rel, "n_symbols": len(syms),
            "symbols": sorted(syms, key=lambda s: s["line"])}


def references(symbol: str, *, limit: int = 40) -> dict[str, Any]:
    """Cross-file usages of a symbol across the workspace (like Pylance references)."""
    hits = []
    for p in _modules():
        try:
            tree = ast.parse(p.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id == symbol:
                hits.append({"file": p.relative_to(ROOT).as_posix(), "line": node.lineno,
                             "ctx": type(node.ctx).__name__.replace("Load", "").replace("Store", "").replace("Del", "del") or "load"})
            elif isinstance(node, ast.Attribute) and node.attr == symbol:
                hits.append({"file": p.relative_to(ROOT).as_posix(), "line": node.lineno, "ctx": "attr"})
    hits = hits[:limit]
    return {"ok": True, "schema": SCHEMA, "symbol": symbol, "n_references": len(hits),
            "references": hits}


def trace_value(module_rel: str, symbol: str) -> dict[str, Any]:
    """Value PROVENANCE via AST: every assignment to `symbol` and its RHS source (like
    traceValue). Deterministic — how a memory/code value got set, for the ghost to audit."""
    p = _module_path(module_rel)
    if not p.is_file():
        return {"ok": False, "error": f"no module {module_rel}"}
    src = p.read_text(encoding="utf-8", errors="replace")
    src_lines = src.splitlines()
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        return {"ok": True, "schema": SCHEMA, "module": module_rel, "syntax_ok": False,
                "error": f"line {e.lineno}: {e.msg}"}
    chain = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == symbol:
                    chain.append({"line": node.lineno, "kind": "assign",
                                  "rhs": ast.get_source_segment(src, node.value) or ""})
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == symbol:
            chain.append({"line": node.lineno, "kind": "annotated",
                          "rhs": ast.get_source_segment(src, node.value) if node.value else None})
        elif isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name) and node.target.id == symbol:
            chain.append({"line": node.lineno, "kind": "augassign",
                          "rhs": ast.get_source_segment(src, node.value) or ""})
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == symbol:
            chain.append({"line": node.lineno, "kind": "definition",
                          "rhs": (src_lines[node.lineno - 1] if node.lineno <= len(src_lines) else "")[:120]})
    return {"ok": True, "schema": SCHEMA, "module": module_rel, "symbol": symbol,
            "provenance": chain}


def imports(*, resolve: bool = True) -> dict[str, Any]:
    """Dependency audit of our own codebase: every top-level import + whether it RESOLVES
    (like pylanceImports). resolve=True uses importlib to check importability."""
    rows = []
    unresolved = []
    for p in _modules():
        try:
            tree = ast.parse(p.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            mod = None
            if isinstance(node, ast.Import):
                mod = node.names[0].name.split(".")[0]
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                mod = (node.module or "").split(".")[0]
            if not mod:
                continue
            rows.append({"file": p.relative_to(ROOT).as_posix(), "import": mod})
    if resolve:
        seen = set()
        for r in rows:
            m = r["import"]
            if m in seen:
                continue
            seen.add(m)
            ok = importlib.util.find_spec(m) is not None
            r["resolved"] = ok
            if not ok:
                unresolved.append({"import": m, "first_seen": r["file"]})
    return {"ok": True, "schema": SCHEMA, "n_imports": len(rows),
            "n_unique": len({r["import"] for r in rows}),
            "unresolved": unresolved[:30], "rows": rows}


def self_check() -> dict[str, Any]:
    """Syntax-check ALL our modules; count clean vs broken (the 'N/N modules clean' bead)."""
    clean, broken = 0, []
    for p in _modules():
        try:
            ast.parse(p.read_text(encoding="utf-8", errors="replace"))
            clean += 1
        except SyntaxError as e:
            broken.append({"file": p.relative_to(ROOT).as_posix(), "line": e.lineno, "msg": str(e.msg)})
    total = clean + len(broken)
    return {"ok": True, "schema": SCHEMA, "modules_checked": total, "syntax_clean": clean,
            "syntax_broken": len(broken), "broken": broken}


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="ghost-pylance")
    ap.add_argument("cmd", nargs="?", default="self_check",
                    choices=["diagnose", "symbols", "references", "trace_value", "imports", "self_check"])
    ap.add_argument("--module", default="")
    ap.add_argument("--symbol", default="")
    args = ap.parse_args(argv)
    if args.cmd == "diagnose":
        print(json.dumps(diagnose(args.module), indent=2))
    elif args.cmd == "symbols":
        print(json.dumps(symbols(args.module), indent=2))
    elif args.cmd == "references":
        print(json.dumps(references(args.symbol), indent=2))
    elif args.cmd == "trace_value":
        print(json.dumps(trace_value(args.module, args.symbol), indent=2))
    elif args.cmd == "imports":
        print(json.dumps(imports(), indent=2, default=str))
    else:
        print(json.dumps(self_check(), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
