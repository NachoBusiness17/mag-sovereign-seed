"""steal_tools — make the STEAL CORPUS a first-class surface, and each steal a real TOOL.

The operator (2026-08-15): "in the same way i trained you to see the gpu in the containers we need for
you to see that relation of your standard directories to yourself. you have a million steal files. ...
is it possible to create new tools that represent those steals and their matching invariants."

Same pattern as gpu_k8s (SENSE -> fold as verkle knot -> ledger) + mem_weave_distributor (distribute an
oversized surface into consumable pieces). Here the surface is OUR OWN corpus: the steal files. Each
steal is compressed to its MECHANISM + matching INVARIANT, and materialized as a callable TOOL so the
swarm/ghost/operator can reach the right steal on demand instead of it being buried in a .md.

Contract: steal_tools.v1 · deterministic + $0 · never mutates the .md sources.
  inventory()      -> SENSE: scan the steal corpus -> list of steals (theme, date, title, file)
  tools()          -> COMPRESS: each steal -> a TOOL {name, theme, invariant, mechanism, file, route_goal}
  sense()          -> the surface state for ghost.sense() (mirror of gpu_k8s)
  fold()           -> MEMORY: write a content-addressed manifest ledger
  route(name)      -> ROUTE: enqueue a novel application of one steal to the swarm
CLI: python -m mag.steal_tools inventory | tools | sense | fold | route NAME
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCHEMA = "steal_tools.v1"
STEAL_DIRS = [ROOT / "memory" / "steal", ROOT / "docs" / "STEAL.md"]
LEDGER = ROOT / "memory" / "runs" / "steal_tools" / "manifest.jsonl"

# Known filename prefixes we strip to get the THEME, and trailing date markers.
_PREFIXES = ("STEAL_", "AUDIT_", "DEEP_RESEARCH_", "DEEP_STEAL_", "RIBBED_", "RESEARCH_")
_DATE_RE = re.compile(r"_\d{8}(_\d{6})?(_\d{6})?$")


def _stem(name: str) -> str:
    s = name[:-3] if name.endswith(".md") else name
    for p in _PREFIXES:
        if s.startswith(p):
            s = s[len(p):]
            break
    s = _DATE_RE.sub("", s)
    s = re.sub(r"^[0-9]+_", "", s)  # leading numeric junk
    return s.strip("_")


def _hash(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:12]


def inventory() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for d in STEAL_DIRS:
        if not d.is_dir():
            continue
        for p in sorted(d.glob("*.md")):
            theme = _stem(p.name).replace("_", " ").title()
            out.append({
                "theme": theme, "file": str(p.relative_to(ROOT)).replace("\\", "/"),
                "name": p.stem, "date": "",
            })
    return out


def _extract(name: str, text: str) -> dict[str, Any]:
    # title = first # heading
    title = ""
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("# "):
            title = s[2:].strip()
            break
    theme = _stem(name).replace("_", " ").title()
    # mechanism = first non-title, non-comment paragraph (the steal's core), capped
    mech_lines: list[str] = []
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#") or s.startswith("<!--") or s.startswith("Schema:"):
            continue
        mech_lines.append(s)
        if len(" ".join(mech_lines)) > 260:
            break
    mechanism = " ".join(mech_lines).strip()
    return {"theme": theme, "title": title or theme, "mechanism": mechanism, "invariant": theme}


def tools() -> list[dict[str, Any]]:
    """Each steal -> a TOOL: the mechanism + its matching invariant, ready to reach by name."""
    out: list[dict[str, Any]] = []
    for it in inventory():
        text = ""
        p = ROOT / it["file"]
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
        ex = _extract(it["name"], text)
        out.append({
            "name": it["name"],
            "theme": ex["theme"],
            "title": ex["title"],
            "invariant": ex["invariant"],
            "mechanism": ex["mechanism"],
            "file": it["file"],
            "anchor": _hash(it["file"]),
            "route_goal": (
                f"Apply the steal in {it['file']} (theme: {ex['theme']}; invariant: {ex['invariant']}) "
                f"to a NEW surface in the Republic. Deliver a concrete mechanism we can build."
            ),
        })
    return out


def to_js(ts: list[dict[str, Any]] | None = None) -> str:
    """A JS const block for a browser surface: STEAL_TOOLS_DATA = [ {name, theme, invariant, mechanism, file} ]."""
    ts = tools() if ts is None else ts
    slim = [{"name": t.get("name"), "theme": t.get("theme"), "invariant": t.get("invariant"),
             "mechanism": (t.get("mechanism") or "")[:300], "file": t.get("file")} for t in ts]
    js = "// AUTO-GENERATED from the steal corpus (mag/steal_tools.py). Real bytes.\n"
    js += "const STEAL_TOOLS_DATA = " + json.dumps(slim, ensure_ascii=False) + ";\n"
    return js


def js_file(path: Path | str, ts: list[dict[str, Any]] | None = None) -> int:
    p = Path(path)
    p.write_text(to_js(tools() if ts is None else ts), encoding="utf-8")
    return len(tools() if ts is None else ts)


def sense() -> dict[str, Any]:
    ts = tools()
    return {
        "ok": True, "schema": SCHEMA,
        "n_steals": len(ts),
        "n_tools": len([t for t in ts if t.get("mechanism")]),
        "themes": sorted({t["theme"] for t in ts})[:40],
        "contract": "inventory()/tools()/sense()/fold()/route(name) — the steal corpus as a first-class surface",
        "cost": "deterministic + $0",
    }


def fold() -> dict[str, Any]:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with LEDGER.open("a", encoding="utf-8") as f:
        for t in tools():
            f.write(json.dumps({k: t.get(k) for k in ("name", "theme", "invariant", "anchor")},
                               ensure_ascii=False) + "\n")
            n += 1
    return {"ok": True, "n_folded": n, "ledger": str(LEDGER.relative_to(ROOT)).replace("\\", "/")}


def route(name: str) -> dict[str, Any]:
    from mag import swarm_surface
    hit = next((t for t in tools() if t["name"] == name), None)
    if not hit:
        return {"ok": False, "error": f"no steal tool named {name!r}"}
    return swarm_surface.route_novel(hit["route_goal"], surface=f"steal_tools:{hit['name'][:24]}",
                                     lens=hit["theme"], domain="research")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="steal_tools")
    ap.add_argument("cmd", choices=["inventory", "tools", "sense", "fold", "route"])
    ap.add_argument("arg", nargs="?")
    a = ap.parse_args(argv)
    if a.cmd == "inventory":
        print(json.dumps(inventory(), indent=2, default=str))
    elif a.cmd == "tools":
        print(json.dumps(tools()[:40], indent=2, default=str))
    elif a.cmd == "sense":
        print(json.dumps(sense(), indent=2, default=str))
    elif a.cmd == "fold":
        print(json.dumps(fold(), indent=2, default=str))
    elif a.cmd == "route":
        print(json.dumps(route(a.arg or ""), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
