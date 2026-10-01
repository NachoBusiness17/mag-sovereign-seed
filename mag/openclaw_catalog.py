"""OpenClaw-facing catalog of Mag organs.

Compile so Sancho can LOAD `/mag/memory/runs/openclaw_catalog/latest.json`
instead of inventing a second Mag. Host Mag venv runs the commands.

    .\\.venv\\Scripts\\python.exe -m mag.openclaw_catalog compile
"""
from __future__ import annotations

import ast
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT


def _rel_posix(path) -> str:
    """Repo-relative posix path, absolute when outside ROOT.

    Cause (ball3 follow-up sweep 2026-09-29): display/receipt derivations
    raised ValueError whenever the path lived outside the repo (the suite
    runs use an out-of-repo pytest basetemp). Same fix as the driver-meter
    lane's _rel_posix in tools/stealth_driver.py.
    """
    try:
        return Path(path).relative_to(ROOT).as_posix()
    except ValueError:
        return Path(path).as_posix()



SCHEMA = "openclaw_catalog.v1"
FABRIC_SCHEMA = "tool_fabric.v1"
OUT = ROOT / "memory" / "runs" / "openclaw_catalog" / "latest.json"
FABRIC = ROOT / "memory" / "runs" / "openclaw_catalog" / "fabric.json"
MAG = ROOT / "mag"

CROWN_MODULES = {
    "memlance": "ghost_memlance.py",
    "verkle-lance": "verkle_lance.py",
    "pylance": "ghost_pylance.py",
    "steer": "grok_steer.py",
    "dnd": "game_campaign.py",
    "chess": "agent_arena.py",
    "lab": "lab_episode.py",
    "mermaid": "surface_render.py",
    "render-world": "game_world_render.py",
    "render-console": "console_render.py",
    "cast": "cast_server.py",
    "salon": "lane_salon.py",
    "patches": "openclaw_patches.py",
    "corpus": "seat_corpus.py",
    "fuel": "fuel_feed.py",
    "governor": "governor.py",
}

# Crown jewels the operator named — always listed, even if scan misses them.
CROWN: list[dict[str, str]] = [
    {"id": "memlance", "cmd": "python -m mag.ghost_memlance select --goal GOAL",
     "origin": "ghost_pylance shape on MEMORY bytes (2026-08-11). Select grounded states, never synthesize.",
     "family": "lance"},
    {"id": "verkle-lance", "cmd": "python -m mag.verkle_lance self_check",
     "origin": "same lance on the knot chain. Temporal map = parent_root → tip.",
     "family": "lance"},
    {"id": "pylance", "cmd": "python -m mag.ghost_pylance diagnose --module mag.X",
     "origin": "GHOSTLANCE: AST over our code, $0, anti-hallucination.",
     "family": "lance"},
    {"id": "steer", "cmd": "python -m mag.grok_steer",
     "origin": "DFHack overlay: sit over a live seat, cache-hit maze prefix, steer don't patch-loop.",
     "family": "steer"},
    {"id": "dnd", "cmd": "python -c \"from mag.game_campaign import handle_game; print(handle_game)\"",
     "note": "Campaign engine owns truth; LLM narrates after. Dashboard h_game / Talk game.",
     "origin": "game_campaign.v1 + game_entry stone-2 walk-in.",
     "family": "game"},
    {"id": "chess", "cmd": "python -m mag.agent_arena",
     "origin": "Seat-vs-seat; python-chess is the oracle.",
     "family": "game"},
    {"id": "lab", "cmd": "python -m mag.lab_episode run --n 40",
     "origin": "Grey Swan stolen as Lab, not a raid.",
     "family": "lab"},
    {"id": "mermaid", "cmd": "python -m mag.surface_render",
     "origin": "Inline hypervisor: mermaid + bare-metal SVG, no Kroki required. GET /api/v1/fleet/hypervisor",
     "family": "render"},
    {"id": "render-world", "cmd": "python -m mag.game_world_render",
     "origin": "Region glyph render.",
     "family": "render"},
    {"id": "render-console", "cmd": "python -m mag.console_render",
     "origin": "Artifact console.",
     "family": "render"},
    {"id": "cast", "cmd": "python -m mag.cast_server",
     "origin": "Cast page renderer.",
     "family": "render"},
    {"id": "salon", "cmd": "python -m mag.lane_salon salon Q --thread hypervisor --monitor deepseek",
     "origin": "Verbose one board; monitor files fixes. Last night = blades thread.",
     "family": "salon"},
    {"id": "patches", "cmd": "python -m mag.openclaw_patches apply",
     "origin": "OpenClaw /patches → Mag write jail.",
     "family": "hypervisor"},
    {"id": "corpus", "cmd": "python -m mag.seat_corpus show groq",
     "origin": "What to send each lane.",
     "family": "hypervisor"},
    {"id": "fuel", "cmd": "python -m mag.fuel_feed status",
     "origin": "Free-lane mill.",
     "family": "mill"},
    {"id": "governor", "cmd": "python -m mag.governor --dry 1",
     "origin": "Autorun decide/execute. ONE supervisor with mag-worker.",
     "family": "mill"},
]


def _first_doc(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")[:1200]
    except OSError:
        return ""
    if '"""' not in text:
        return ""
    a = text.find('"""')
    b = text.find('"""', a + 3)
    if b < 0:
        return ""
    block = text[a + 3:b].strip().splitlines()
    return " ".join(x.strip() for x in block[:3])[:240]


def _subtools(path: Path) -> list[str]:
    """Argparse choices + public def names (the loved subtools)."""
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    found: list[str] = []
    for m in re.finditer(r'choices\s*=\s*\[([^\]]+)\]', raw):
        for tok in re.findall(r'["\']([a-zA-Z][\w-]{1,40})["\']', m.group(1)):
            if tok not in found:
                found.append(tok)
    try:
        tree = ast.parse(raw)
    except SyntaxError:
        return found[:24]
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
            if node.name not in found:
                found.append(node.name)
    return found[:24]


def _imports(path: Path) -> list[str]:
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    mods = re.findall(r"(?:from|import)\s+mag\.([a-zA-Z_][a-zA-Z0-9_]*)", raw)
    out: list[str] = []
    for m in mods:
        if m not in out:
            out.append(m)
    return out[:16]


def scan_clis() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for p in sorted(MAG.glob("*.py")):
        if p.name.startswith("_"):
            continue
        try:
            raw = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if 'if __name__ == "__main__"' not in raw:
            continue
        rows.append({
            "id": p.stem,
            "cmd": f"python -m mag.{p.stem}",
            "origin": _first_doc(p),
            "family": "scanned",
        })
    return rows


def compile_fabric() -> dict[str, Any]:
    """Crown jewels + subtools + import ribs. The copy of tools we love — Mag's own topology."""
    from tools import TOOL_MAP

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, str]] = []
    for c in CROWN:
        fn = CROWN_MODULES.get(c["id"])
        path = MAG / fn if fn else None
        subs = _subtools(path) if path and path.is_file() else []
        imps = _imports(path) if path and path.is_file() else []
        nodes.append({**c, "module": fn or "", "subtools": subs, "imports_mag": imps})
        for other in imps:
            edges.append({"from": c["id"], "to": other, "kind": "import-rib"})
    nodes.append({
        "id": "agent-tools",
        "family": "agent",
        "cmd": "tools.TOOL_MAP via mag.agent_cli",
        "origin": "Coding-seat toolbelt: fs + shell + swarm sense.",
        "subtools": sorted(TOOL_MAP.keys()),
        "imports_mag": [],
    })
    mermaid = ["graph LR"]
    for e in edges[:80]:
        mermaid.append(f"  {e['from']}-->{e['to']}")
    fabric = {
        "ok": True,
        "schema": FABRIC_SCHEMA,
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "law": "Fabric is Mag's own topology copy. Adapt contracts; do not clone foreign thrones.",
        "nodes": nodes,
        "edges": edges,
        "mermaid": "\n".join(mermaid),
        "n_nodes": len(nodes),
        "n_edges": len(edges),
    }
    FABRIC.parent.mkdir(parents=True, exist_ok=True)
    FABRIC.write_text(json.dumps(fabric, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    fabric["path"] = _rel_posix(FABRIC)
    return fabric


def compile_catalog() -> dict[str, Any]:
    scanned = scan_clis()
    seen = {c["id"] for c in CROWN}
    extra = [r for r in scanned if r["id"] not in seen]
    fabric = compile_fabric()
    out = {
        "ok": True,
        "schema": SCHEMA,
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "law": "OpenClaw LOADs this catalog. Host Mag venv RUNS cmds. /mag is read-only.",
        "host": r".\.venv\Scripts\python.exe -m mag.<id>",
        "crown": CROWN,
        "fabric_path": fabric.get("path"),
        "fabric_n_nodes": fabric.get("n_nodes"),
        "fabric_n_edges": fabric.get("n_edges"),
        "scanned_cli_n": len(scanned),
        "scanned_extra_n": len(extra),
        "scanned_extra": extra,
        "dashboard": {
            "body": "http://127.0.0.1:8765/",
            "fleet_mermaid": "http://127.0.0.1:8765/  GET /api/v1/fleet/hypervisor",
            "game": "dashboard h_game / h_table_view",
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    out["path"] = _rel_posix(OUT)
    return out


def main(argv: list[str] | None = None) -> int:
    import sys
    args = list(argv if argv is not None else sys.argv[1:])
    cmd = args[0] if args else "compile"
    if cmd != "compile":
        print("usage: python -m mag.openclaw_catalog compile")
        return 2
    print(json.dumps(compile_catalog(), indent=2, default=str)[:8000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
