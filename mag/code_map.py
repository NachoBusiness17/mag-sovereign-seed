"""code_map — full-system code map + invariant extraction (the rib at full scale).

Scans the WHOLE codebase (mag/, tools/, root modules, key docs/configs) and distills a
compact, structured CODE MAP: every module's purpose (docstring header) + its extracted
invariants (LAW / DOCTRINE / Schema / never-rules). This is the deterministic half of
"a full code map of our system and its invariants from a frontier perspective" — the
frontier then distills the cross-cutting invariants (see distill_to_frontier()).

Schema: code_map.v1
CLI: python -m mag.code_map build           -> write queue/handoff/CODE_MAP_RIB.md
     python -m mag.code_map count           -> module/invariant counts (no big output)
"""
from __future__ import annotations

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

SCHEMA = "code_map.v1"
OUT = ROOT / "queue" / "handoff" / "CODE_MAP_RIB.md"
SCAN_DIRS = ["mag", "tools", "scripts", "harness", "router", "backend"]
INVARIANT_PREFIXES = ("law", "doctrine", "schema", "invariant", "constitu")
_INVARIANT_RE = re.compile(r"(^|\b)(law|doctrine|schema|invariant|constitution|never|always)\b", re.I)


def _extract(path: Path) -> tuple[str, list[str]]:
    """Return (docstring header, invariant lines) from a module."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return "", []
    doc = (ast.get_docstring(tree) or "").splitlines()
    header = ""
    for ln in doc:
        s = ln.strip()
        if s:
            header = s[:140]
            break
    invariants: list[str] = []
    for ln in doc:
        s = ln.strip()
        if not s or len(s) > 220:
            continue
        if s.lower().startswith(INVARIANT_PREFIXES) or _INVARIANT_RE.search(s):
            invariants.append(s[:200])
    return header, invariants[:8]


def scan() -> dict[str, Any]:
    mods: list[dict[str, Any]] = []
    seen: set[Path] = set()
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
            header, inv = _extract(py)
            if not header:
                continue
            mods.append({"file": py.relative_to(ROOT).as_posix(),
                         "purpose": header, "invariants": inv})
    # root-level entry modules
    for name in ("main.py", "graph.py", "state.py", "config.py", "conftest.py",
                 "synthesis_agent.py", "ijl_core.py"):
        py = ROOT / name
        if py.is_file() and py not in seen:
            header, inv = _extract(py)
            if header:
                mods.append({"file": name, "purpose": header, "invariants": inv})
    return {"schema": SCHEMA, "modules": mods,
            "n_modules": len(mods),
            "n_invariants": sum(len(m["invariants"]) for m in mods)}


def build() -> dict[str, Any]:
    s = scan()
    lines = [f"# CODE MAP RIB — full-system map + invariants", f"- schema: {SCHEMA}",
             f"- modules: {s['n_modules']}  invariants: {s['n_invariants']}",
             f"- generated: {datetime.now(timezone.utc).isoformat()}",
             ""]
    for m in s["modules"]:
        lines.append(f"## {m['file']}")
        lines.append(f"- {m['purpose']}")
        for inv in m["invariants"]:
            lines.append(f"  - {inv}")
        lines.append("")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    return {"ok": True, "schema": SCHEMA, "path": str(OUT),
            "n_modules": s["n_modules"], "n_invariants": s["n_invariants"],
            "chars": sum(len(l) for l in lines)}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv[0] if argv else "count"
    if cmd == "build":
        print(json.dumps(build(), indent=2, default=str))
    elif cmd == "distill":
        print(json.dumps(distill(), indent=2, default=str)[:4000])
    elif cmd == "distilled":
        print(json.dumps(distilled(), indent=2, default=str)[:6000])
    else:
        print(json.dumps(scan(), indent=2, default=str)[:2000])
    return 0


# ---------------------------------------------------------------------------
# RIGHT-SIZED FRONTIER DISTILLATION — bind grok to Ghost's exact output contract
# so we get the distilled invariants we need, not vague sprawl.
# ---------------------------------------------------------------------------
GHOST_CONTRACT = (
    "Return ONLY a distilled invariant map. Each line EXACTLY:\n"
    "  - [<domain>] <invariant> (guardrail: <one short clause>)\n"
    "Rules: NO preamble, NO prose, NO markdown headers (one title line only), NO bullets that "
    "aren't the invariant format, NO repetition, hard cap at 40 lines. Extract only the "
    "CROSS-CUTTING, load-bearing rules whose violation breaks the system or its economy "
    "(routing, cost, memory, governance, security). Prefer the single strongest specific "
    "invariant over vague generalities. This is RIGHT-SIZING, not summarizing."
)


def distill(*, out: Path | None = None) -> dict[str, Any]:
    """Right-size a frontier (grok-4.5) distillation of the code map: send a BOUNDED rib +
    Ghost's strict output contract + a capped output budget, so the frontier returns exactly
    the distilled invariants we consume (no sprawl)."""
    import mag.grok_rightsize as gr

    if not OUT.is_file():
        build()
    full = OUT.read_text(encoding="utf-8")
    # Bound the input: prioritize invariant lines over module headers to fit the frontier context.
    body_lines = []
    for ln in full.splitlines():
        s = ln.strip()
        if s.startswith("# "):
            body_lines.append(s)
        elif s.startswith("- ") and s[2:3].isalpha():
            body_lines.append(s)  # invariant/guardrail lines first
        elif s.startswith("## "):
            body_lines.append("### " + s[3:])
    bounded = "\n".join(body_lines)[:22000]

    goal = ("Distill the full-system code map below into its load-bearing cross-cutting "
            "invariants. You are RIGHT-SIZING, not summarizing: extract only the rules that "
            "if violated break the system or its economy. Follow the output contract exactly "
            "and STOP at the line cap — no filler.")
    ctx = "CODE MAP (full-system, generated from source):\n\n" + bounded + \
          "\n\nOUTPUT CONTRACT:\n" + GHOST_CONTRACT
    r = gr.call_grok(goal, tier="orchestrate", context=ctx, max_tokens=1200, timeout=300)

    dest = out or (ROOT / "queue" / "handoff" / "DISTILLED_INVARIANTS.md")
    dest.parent.mkdir(parents=True, exist_ok=True)
    content = r.content or "NO CONTENT"
    dest.write_text(content, encoding="utf-8")
    # Cache by rib-hash so the SWARM reads the cache, not the frontier (cost doctrine:
    # big ask once -> cache the relevant part -> inform the swarm).
    try:
        import hashlib as _h
        dist_cache = ROOT / "memory" / "runs" / "code_map" / "distill.json"
        dist_cache.parent.mkdir(parents=True, exist_ok=True)
        dist_cache.write_text(json.dumps({
            "rib_hash": _h.sha256(OUT.read_bytes()).hexdigest()[:16],
            "model": r.model, "tier": r.tier, "cost_est_usd": r.cost_est_usd,
            "content": content}, ensure_ascii=False, default=str), encoding="utf-8")
    except Exception:
        pass
    return {"ok": r.ok, "model": r.model, "tier": r.tier, "cost_est_usd": r.cost_est_usd,
            "tokens_total": r.tokens_total, "error": r.error,
            "input_chars": len(bounded), "output_lines": len(content.splitlines()),
            "saved_to": str(dest)}


def distilled() -> dict[str, Any]:
    """SWARM-FACING reader: return the cached right-sized distillation. NEVER calls the
    frontier — the swarm reads this cache, which is the cost doctrine (big ask once, cache,
    reuse). Returns ok=False until distill() has run once."""
    dist_cache = ROOT / "memory" / "runs" / "code_map" / "distill.json"
    if not dist_cache.is_file():
        return {"ok": False, "cached": False,
                "error": "no cached distillation; run `python -m mag.code_map distill` once"}
    try:
        import hashlib as _h
        c = json.loads(dist_cache.read_text(encoding="utf-8"))
        cur = _h.sha256(OUT.read_bytes()).hexdigest()[:16]
        fresh = c.get("rib_hash") == cur
        return {"ok": True, "cached": True, "fresh": fresh,
                "model": c.get("model"), "cost_est_usd": c.get("cost_est_usd"),
                "rib_hash": c.get("rib_hash"),
                "content": c.get("content", ""),
                "note": ("swarm reads this cache; re-distill only if rib_hash changed" if fresh
                          else "code map changed - re-run distill once")}
    except Exception as e:
        return {"ok": False, "cached": False, "error": str(e)[:160]}


if __name__ == "__main__":
    raise SystemExit(main())
