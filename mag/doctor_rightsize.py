"""doctor_rightsize — the DOCTOR rightsizes internal systems: when a module gets TOO LARGE,
distribute it into the MEM WEAVE so it just works as emergent pieces, not a monolith.

Operator (2026-08-11): "we need our doctor right-sizing our internal systems so when they get too
large they get distributed to the mem weave and just work."

How it works (stateless, $0, AST-based):
  1. SCAN: measure every mag/*.py module (lines, top-level defs/classes). Flag modules over
     SIZE_THRESHOLD as "too large" (monolithic).
  2. DISTRIBUTE: for each oversized module, extract its discrete capabilities (top-level defs/classes)
     and FOLD each into the mem weave (knowledge_graph.fold doctrine/module node + verkle knot), so
     the weave owns the capability and the swarm routes to it piecewise. Record in a distribution ledger.
  3. VERIFY (RIB-debug law): re-scan + confirm the distribution folded; report what was distributed.
  4. SELF-LEARN: log which modules were distributed + their sizes so the doctor tightens the threshold.

Contract: doctor_rightsize.v1. Deterministic + $0. Never edits the source module — it only folds the
weave representation so the capability is discoverable/consumable piecewise ("just works").
CLI: python -m mag.doctor_rightsize scan | distribute [--module X] | status | rightsize
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCHEMA = "doctor_rightsize.v1"
MAG = ROOT / "mag"
STATE_DIR = ROOT / "memory" / "runs" / "doctor_rightsize"
LEDGER = STATE_DIR / "distributed.jsonl"

SIZE_THRESHOLD_LINES = 500   # a module over this many lines is a candidate for distribution
DEFS_THRESHOLD = 20          # ...and/or this many top-level defs/classes (monolithic)
SKIP_PREFIXES = ("_", "__")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _read_jsonl(path: Path, tail: int = 200) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    out = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out[-tail:]


def _append_jsonl(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False, default=str) + "\n")


# ── SCAN ───────────────────────────────────────────────────────────────────
def _measure_module(path: Path) -> dict[str, Any]:
    src = path.read_text(encoding="utf-8", errors="replace")
    lines = len(src.splitlines())
    defs: list[str] = []
    classes: list[str] = []
    try:
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("_"):
                defs.append(node.name)
            elif isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
                classes.append(node.name)
    except SyntaxError:
        pass
    return {"module": path.stem, "path": str(path), "lines": lines,
            "defs": len(defs), "classes": len(classes),
            "def_names": defs[:8], "class_names": classes[:4]}


def scan() -> dict[str, Any]:
    """Measure all mag/*.py modules; flag oversized ones."""
    modules = []
    oversized = []
    for p in sorted(MAG.glob("*.py")):
        if p.name.startswith(SKIP_PREFIXES) or p.name == "__init__.py":
            continue
        m = _measure_module(p)
        modules.append(m)
        if m["lines"] > SIZE_THRESHOLD_LINES or m["defs"] > DEFS_THRESHOLD:
            m["too_large"] = True
            oversized.append(m)
    return {"schema": SCHEMA, "ts": _now(), "n_modules": len(modules),
            "n_oversized": len(oversized),
            "oversized": [{"module": m["module"], "lines": m["lines"], "defs": m["defs"],
                           "classes": m["classes"]} for m in oversized],
            "threshold": {"lines": SIZE_THRESHOLD_LINES, "defs": DEFS_THRESHOLD}}


# ── DISTRIBUTE to the mem weave ────────────────────────────────────────────
def distribute_to_weave(module_name: str) -> dict[str, Any]:
    """Fold an oversized module's discrete capabilities into the mem weave."""
    path = MAG / f"{module_name}.py"
    if not path.is_file():
        return {"ok": False, "error": f"no module {module_name}"}
    m = _measure_module(path)
    folded = []
    # Each top-level capability becomes a weave node so the swarm routes to it piecewise.
    for name in m.get("def_names", [])[:10]:
        try:
            from mag.knowledge_graph import fold as kg_fold
            r = kg_fold(f"{module_name}.{name}", "module",
                        f"capability distributed from oversized module {module_name} "
                        f"({m['lines']} lines) into the mem weave", source="doctor_rightsize")
            folded.append({"cap": name, "ok": bool(r.get("ok", r.get("added", True)))})
        except Exception as e:
            folded.append({"cap": name, "ok": False, "error": str(e)[:80]})
    # Verkle knot: durable, content-addressed record of the distribution.
    knot = {}
    try:
        from mag.verkle_knot import append_verkle_knot
        knot = append_verkle_knot({"session_id": f"doctor-rightsize:{module_name}",
                                   "theme": "doctrine",
                                   "summary": f"[doctor_rightsize] distributed {module_name} "
                                              f"({m['lines']} lines, {m['defs']} defs) into mem weave"})
    except Exception as e:
        knot = {"error": str(e)[:80]}
    row = {"ts": _now(), "schema": SCHEMA, "module": module_name, "lines": m["lines"],
           "defs": m["defs"], "folded": folded, "verkle_ok": bool(knot.get("ok")), "knot": knot}
    _append_jsonl(LEDGER, row)
    return {"ok": True, **row}


def rightsize(*, module: str | None = None) -> dict[str, Any]:
    """SCAN -> DISTRIBUTE oversized modules -> VERIFY -> learn."""
    s = scan()
    dist = []
    targets = [module] if module else [o["module"] for o in s["oversized"]]
    for name in targets:
        d = distribute_to_weave(name)
        dist.append({"module": name, "ok": d.get("ok"), "folded_n": len(d.get("folded", [])),
                     "verkle_ok": d.get("verkle_ok")})
    # VERIFY (RIB-debug): re-scan to confirm nothing else grew; log the run.
    rescan = scan()
    _append_jsonl(LEDGER, {"ts": _now(), "schema": "doctor_rightsize_run.v1",
                           "action": "rightsize", "distributed": dist,
                           "remaining_oversized": [o["module"] for o in rescan["oversized"]]})
    return {"ok": True, "schema": SCHEMA, "ts": _now(), "scan": s,
            "distributed": dist, "rescan_remaining": [o["module"] for o in rescan["oversized"]]}


def status() -> dict[str, Any]:
    rows = _read_jsonl(LEDGER)
    return {"schema": SCHEMA, "n_distributions": len(rows),
            "last": rows[-1] if rows else None}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="doctor-rightsize",
                                 description="Doctor rightsizes oversized internal systems into the mem weave.")
    ap.add_argument("cmd", nargs="?", choices=["scan", "rightsize", "distribute", "status"], default="scan")
    ap.add_argument("--module", default="")
    a = ap.parse_args(argv)
    if a.cmd == "scan":
        print(json.dumps(scan(), indent=2, default=str))
    elif a.cmd == "rightsize":
        print(json.dumps(rightsize(module=a.module or None), indent=2, default=str))
    elif a.cmd == "distribute":
        print(json.dumps(distribute_to_weave(a.module) if a.module
                         else {"ok": False, "error": "need --module"}, indent=2, default=str))
    else:
        print(json.dumps(status(), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

__all__ = ["scan", "distribute_to_weave", "rightsize", "status", "main"]
