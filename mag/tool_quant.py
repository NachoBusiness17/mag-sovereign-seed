"""tool_quant — QUANT versions of all our tools: each tool's compact self-similar essence that
carries the whole (Shufflebrain), joined deterministic+stochastic, turtles all the way down.

OPERATOR (2026-08-12): "stochastic deterministic turtle joining. we want these quant versions of
all our tools." SELF-STEAL (reuses our own machinery):
  shape_map.shape_for  -> the QUANT: a tool's content-addressed Merkle-root spec (carries the whole)
  auto_quantize        -> adaptive-resolution quant (Quantum points; anomalies never quantized)
  swarm_surface        -> the STOCHASTIC join: route the tool's quant to the swarm for refinement

THE PATTERN (per tool):
  QUANT   = shape_for(tool, its elements) -> {name, root, n, leaf_hashes} — the deterministic essence
  JOIN    = deterministic quant + stochastic swarm refinement (route_novel) — the turtle join
  TURTLE  = each quant is itself self-similar (the root carries the whole) — turtles all the way down

Schema: tool_quant.v1 · deterministic + $0 (quant); join routes to the swarm (stochastic side)
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "tool_quant.v1"
MAG_DIR = ROOT / "mag"
LEDGER = ROOT / "memory" / "tool_quant" / "quant_ledger.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def scan_tools() -> list[dict[str, Any]]:
    """The tools: every mag/*.py module (our tool surface). Deterministic + $0."""
    out = []
    if not MAG_DIR.is_dir():
        return out
    for p in sorted(MAG_DIR.glob("*.py")):
        if p.name.startswith("_") or p.name == "__init__.py":
            continue
        out.append({"name": p.stem, "path": str(p)})
    return out


def quant_tool(name: str, path: str) -> dict[str, Any]:
    """The QUANT version of one tool: its content-addressed Merkle-root spec (carries the whole)."""
    try:
        from mag import shape_map
        p = Path(path)
        text = p.read_text(encoding="utf-8", errors="replace") if p.is_file() else name
        # elements = the tool's top-level function/class definitions (its structural essence)
        import re
        defs = re.findall(r"^(?:def|class)\s+\w+", text, re.M)
        elements = defs or [name]
        spec = shape_map.shape_for(name, elements, text_fn=lambda d: str(d))
        return {"ok": True, "schema": SCHEMA, "tool": name,
                "quant": {"root": spec.get("root"), "n": spec.get("n"),
                          "leaf_hashes": spec.get("leaf_hashes"),
                          "coords": spec.get("coords")},
                "essence": "Merkle-root spec — the tool's whole carried in a compact root"}
    except Exception as e:
        return {"ok": False, "tool": name, "error": str(e)[:120]}


def quant_all() -> dict[str, Any]:
    """QUANT versions of ALL our tools -> a persistent ledger. Deterministic + $0."""
    tools = scan_tools()
    quants = [quant_tool(t["name"], t["path"]) for t in tools]
    ok = [q for q in quants if q.get("ok")]
    ledger = {"schema": SCHEMA, "ts": _now(), "n_tools": len(tools), "n_quant": len(ok),
              "quants": ok}
    try:
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        LEDGER.write_text(json.dumps(ledger, ensure_ascii=False, indent=2, default=str),
                          encoding="utf-8")
    except OSError:
        pass
    return {"ok": True, "schema": SCHEMA, "n_tools": len(tools), "n_quant": len(ok),
            "quants": ok, "ledger": str(LEDGER.relative_to(ROOT)).replace("\\", "/")}


def turtle_join(*, tool: str = "", enqueue: bool = True) -> dict[str, Any]:
    """STOCHASTIC + DETERMINISTIC turtle join: the deterministic quant (root) joins with the
    STOCHASTIC swarm (route_novel) for refinement — the wave's stochastic flesh on the deterministic
    bones. Turtles all the way down: each quant is a knot carrying the whole."""
    from mag import swarm_surface
    tools = [t for t in scan_tools() if not tool or t["name"] == tool]
    routed = []
    for t in tools[:10]:
        q = quant_tool(t["name"], t["path"])
        if not q.get("ok"):
            continue
        goal = (f"STOCHASTIC refinement of the deterministic quant of tool '{t['name']}': "
                f"root={q['quant']['root']}. Return the improvement (the stochastic flesh on the "
                f"deterministic bones).")
        r = swarm_surface.route_novel(goal, surface=f"tool-quant:{t['name'][:24]}",
                                      lens="quant/refine", domain="quant") if enqueue else {"ok": True, "dry": True}
        routed.append({"tool": t["name"], "root": q["quant"]["root"][:16],
                       "routed": r.get("ok"), "task_id": r.get("task_id", ""), "deduped": r.get("deduped")})
    return {"ok": True, "schema": SCHEMA, "n_routed": len(routed), "join": "deterministic quant + stochastic swarm",
            "turtle": "each quant is self-similar — the root carries the whole, turtles all the way down",
            "routed": routed}


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "contract": "quant_tool/quant_all -> the QUANT (Merkle-root spec) of each tool; "
                        "turtle_join -> deterministic quant + stochastic swarm refinement; "
                        "turtles all the way down",
            "cost": "deterministic + $0 (quant); join routes to the swarm",
            "ledger": str(LEDGER.relative_to(ROOT)).replace("\\", "/")}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="tool-quant")
    ap.add_argument("cmd", nargs="?", default="all", choices=["all", "join", "status"])
    ap.add_argument("--tool", default="")
    a = ap.parse_args()
    if a.cmd == "join":
        print(json.dumps(turtle_join(tool=a.tool, enqueue=True), ensure_ascii=False, indent=2, default=str))
    elif a.cmd == "status":
        print(json.dumps(status(), ensure_ascii=False, indent=2, default=str))
    else:
        print(json.dumps(quant_all(), ensure_ascii=False, indent=2, default=str))
