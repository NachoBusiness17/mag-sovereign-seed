"""connectivity_sizer — size our built tools by CONNECTIVITY (bare-metal linter).

OPERATOR (2026-08-12): "knowing how and why they are connected helps us understand how to best
size our built tools for different jobs to make it even more bare metal."

DOCTRINE: the size of a tool should match its connectivity, not its ambition.
  * shared-primitive (many depend on it) -> build ONCE, lean, reuse everywhere (the ONE primitive).
  * leaf (touches only itself)            -> pure stdlib, no deps (bare-metal).
  * frontier-boundary (touches a remote)  -> thin + dry-gated (the expensive part stays scarce).
  * distributor (feeds the swarm)         -> tiny seed + cheap worker.

SELF-STEAL: code_map (full AST system map), one_sizer (rightsize), rightsize_all, attention_ranker
(dependency centrality).
EXTERNAL-STEAL (radon / Martin): cyclomatic complexity, maintainability index, and dependency
metrics (fan-in Ca, fan-out Ce, instability I = Ce/(Ce+Ca)) — the canonical "size by connectivity".

WHAT IT DOES (deterministic, pure stdlib, $0): scan every mag/*.py via AST, compute each tool's
connectivity (fan-in/fan-out + external deps + complexity + lloc), classify it into the connectivity
class its JOB implies, and flag OVER-BUILT (heavy deps/complexity for a leaf) vs UNDER-BUILT
(high-connectivity surface reinvented per-module). Operator is the final judge.

Schema: connectivity_sizer.v1 · deterministic + $0 · pure stdlib
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "connectivity_sizer.v1"
MAG_DIR = ROOT / "mag"

# Known shared primitives (the ONE-primitive surfaces) — reuse, don't reinvent.
SHARED_PRIMITIVES = {"swarm_surface", "swarm_worker", "route_novel", "rib_action", "bernaise",
                     "attractor_tools", "model_pick", "one_sizer", "code_map", "memlang",
                     "frontier_gravity", "frontier_pennies"}
# Frontier-boundary surfaces — tools that touch a remote mind should be thin + dry-gated.
FRONTIER_SURFACES = {"chatgpt_bot", "grok_bot", "grok_rightsize", "browser_driver", "frontier_advisor",
                     "frontier_council", "riddler_tap", "grok_mirror", "grok_hub"}
# Distributor surfaces — tools that broadcast to the cheap swarm.
DISTRIBUTOR_SURFACES = {"swarm_worker", "swarm_surface", "autonomous_research", "frontier_pennies",
                        "arxiv_mine", "cheap_swarm", "flock_job"}


def _decision_points(tree: ast.AST) -> int:
    """Minimal cyclomatic-complexity proxy: count decision points (stdlib, deterministic)."""
    n = 1
    for node in ast.walk(tree):
        if isinstance(node, (ast.If, ast.For, ast.While, ast.ExceptHandler, ast.Assert)):
            n += 1
        elif isinstance(node, ast.BoolOp):
            n += len(node.values) - 1
        elif isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            n += 1
    return n


def _lloc(src: str) -> int:
    """Logical lines of code (stdlib): count non-blank, non-comment source lines."""
    try:
        tree = ast.parse(src)
    except Exception:
        return max(1, len([l for l in src.splitlines() if l.strip() and not l.strip().startswith("#")]))
    return len([n for n in ast.walk(tree) if isinstance(n, ast.stmt)])


def scan() -> dict[str, Any]:
    """AST-scan every mag/*.py: connectivity (fan-in/fan-out), external deps, complexity, lloc."""
    mods: dict[str, dict[str, Any]] = {}
    if not MAG_DIR.is_dir():
        return {"ok": False, "schema": SCHEMA, "error": "mag dir missing"}
    # pass 1: read each module's imports + complexity
    files: dict[str, tuple[str, set[str], set[str]]] = {}
    for p in sorted(MAG_DIR.glob("*.py")):
        if p.name.startswith("_"):
            continue
        mod = p.stem
        src = p.read_text(encoding="utf-8", errors="replace")
        try:
            tree = ast.parse(src)
        except SyntaxError:
            tree = None
        internal, external = set(), set()
        for node in ast.walk(tree) if tree else []:
            if isinstance(node, ast.Import):
                for a in node.names:
                    top = (a.name or "").split(".")[0]
                    (internal if top == "mag" or (MAG_DIR / f"{top}.py").is_file() else external).add(top)
            elif isinstance(node, ast.ImportFrom) and node.module:
                top = (node.module or "").split(".")[0]
                if top == "mag" or (MAG_DIR / f"{top}.py").is_file() or top == "mag" and node.level == 0:
                    if node.level == 0:
                        internal.add(top)
                elif node.level == 0:
                    external.add(top)
        files[mod] = (src, internal - {"mag"}, external)
    # pass 2: compute fan-in from all internal edges
    fan_in: dict[str, int] = {m: 0 for m in files}
    edges = []
    for m, (_, internal, _) in files.items():
        for dep in internal:
            if dep in fan_in:
                fan_in[dep] += 1
                edges.append((m, dep))
    for mod, (src, internal, external) in files.items():
        fan_out = len(internal & set(files))
        fan_inv = fan_in[mod]
        tot = fan_inv + fan_out
        instability = (fan_out / tot) if tot else 1.0
        try:
            tree = ast.parse(src)
        except SyntaxError:
            tree = None
        mods[mod] = {
            "fan_in": fan_inv, "fan_out": fan_out,
            "instability": round(instability, 3),
            "external_deps": sorted(external), "n_external_deps": len(external),
            "complexity": _decision_points(tree) if tree else 0,
            "lloc": _lloc(src),
            "edges": sorted(e for (a, b) in edges if a == mod),
        }
    return {"ok": True, "schema": SCHEMA, "n_modules": len(mods), "modules": mods}


def classify() -> dict[str, Any]:
    """Size each tool by connectivity: class + verdict (over-built / right-sized / under-built)."""
    s = scan()
    mods = s.get("modules") or {}
    rows = []
    for mod, m in mods.items():
        fan_in, fan_out = m["fan_in"], m["fan_out"]
        deps = m["n_external_deps"]
        cx = m["complexity"]
        conn = fan_in + fan_out
        # connectivity class implied by the job
        if mod in SHARED_PRIMITIVES:
            cls_ = "shared-primitive"
        elif mod in DISTRIBUTOR_SURFACES:
            cls_ = "distributor"
        elif mod in FRONTIER_SURFACES:
            cls_ = "frontier-boundary"
        elif conn >= 3:
            cls_ = "connector"
        else:
            cls_ = "leaf"
        # verdict
        if cls_ == "leaf" and (deps > 0 or cx > 20):
            verdict = "over-built"
            note = f"leaf but {deps} external dep(s)/complexity {cx} — shrink to stdlib/lean"
        elif cls_ == "shared-primitive" and deps > 0:
            verdict = "over-built"
            note = "shared primitive with external deps — must stay bare-metal + one"
        elif fan_in >= 4 and mod not in SHARED_PRIMITIVES and cls_ != "frontier-boundary":
            verdict = "under-built"
            note = f"{fan_in} dependents but not a shared primitive — consolidate/reuse the ONE primitive"
        elif fan_out >= 6 and cls_ == "leaf":
            verdict = "under-built"
            note = f"leaf but fans out to {fan_out} modules — likely should be a connector/shared"
        else:
            verdict = "right-sized"
            note = "sized to its connectivity"
        rows.append({"module": mod, "class": cls_, "verdict": verdict, "note": note,
                     "fan_in": fan_in, "fan_out": fan_out, "instability": m["instability"],
                     "external_deps": m["n_external_deps"], "complexity": cx, "lloc": m["lloc"]})
    rows.sort(key=lambda r: r["verdict"])
    return {"ok": True, "schema": SCHEMA, "n_modules": len(rows),
            "rows": rows,
            "over_built": [r["module"] for r in rows if r["verdict"] == "over-built"],
            "under_built": [r["module"] for r in rows if r["verdict"] == "under-built"],
            "right_sized": [r["module"] for r in rows if r["verdict"] == "right-sized"]}


def status() -> dict[str, Any]:
    c = classify()
    return {"ok": True, "schema": SCHEMA,
            "contract": "scan() = AST connectivity (fan-in/fan-out, external deps, complexity, "
                        "lloc); classify() = size each tool by connectivity (shared-primitive / "
                        "leaf / frontier-boundary / distributor) + verdict (over-built / "
                        "right-sized / under-built). Bare-metal: leaf = stdlib, shared = ONE + "
                        "lean, frontier = thin + dry-gated, distributor = seed.",
            "reuse": "code_map (map) + one_sizer/rightsize_all (sizing) + radon/Martin (metrics)",
            "n_modules": c.get("n_modules"),
            "over_built": len(c.get("over_built") or []),
            "under_built": len(c.get("under_built") or []),
            "right_sized": len(c.get("right_sized") or [])}


def main(argv: list[str] | None = None) -> int:
    import argparse

    p = argparse.ArgumentParser(prog="connectivity_sizer")
    sub = p.add_subparsers(dest="cmd")
    sub.add_parser("scan")
    sub.add_parser("classify")
    sub.add_parser("status")
    a = p.parse_args(argv)
    if a.cmd == "scan":
        print(json.dumps(scan(), indent=2, default=str))
    elif a.cmd == "classify":
        print(json.dumps(classify(), indent=2, default=str))
    else:
        print(json.dumps(status(), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
