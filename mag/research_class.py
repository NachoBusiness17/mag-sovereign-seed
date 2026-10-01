"""research_class — classify ALL research (frontier + every level) through ONE lens at fold time,
chain it back to the origin, then gap-fill the most efficient tools from our own ecosystem.

Operator (2026-08-11): "we need to classify frontier level research and all level research after
it's been deduped and looked for novelty ... as we're folding we need to classify it so that it is
all readable via the same lens ... we need one that goes back to the very beginning ... use our
vertical pointer structure and our mirrored tools within our own ecosystem to create the most
efficient tools that we can using our knowledge base to gap items."

WHAT THIS IS (deterministic + $0, module functions only, no LLM):
  1. classify(text, source)  — ONE lens: tier x kind x domain x grounding. Applied at fold time.
  2. fold_classified(text, ...) — percolate (dedup + novelty) THEN classify, append a uniform row to
     memory/research_class/registry.jsonl with a VERTICAL POINTER back to its origin (prev_id chain
     to the very beginning — the first seeded invariant), so the whole body is readable via the same
     lens AND traceable to origin.
  3. lens_read()            — read every classified research row through the SAME lens (uniform view).
  4. gaps(k)                — coverage by (domain, kind): return the least-covered = GAP ITEMS, and
     propose the most efficient tool build from OUR OWN mirrored tools + knowledge base to fill them.
  5. tool_plan(gap)         — given a gap, name the existing mag.* mirrored tools + a minimal build
     that closes it (contract-only, from our knowledge base).

Schema: research_class.v1 · deterministic + $0 · reuse: percolator (dedup/novelty), ghost_memlance
(grounding), rib_bus (origin fold).
"""
from __future__ import annotations

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
    from pathlib import Path as _P
    ROOT = _P(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "research_class.v1"
REGISTRY = ROOT / "memory" / "research_class" / "registry.jsonl"
ORIGIN_INVARIANT = "the map precedes the territory; the RIB precedes the flock"  # the very beginning

# ── THE ONE LENS: tier × kind × domain × grounding ─────────────────────────────
TIERS = ("frontier", "operational", "steal", "doctrine")
KINDS = ("invariant", "mechanism", "gap", "tool", "steal", "synthesis", "fact")
DOMAINS = ("swarm", "memory", "security", "voice", "wearable", "agent-os", "economics",
           "render", "compiler", "world", "inference", "general")

_TIER_HINT = {"frontier": ("frontier", "deep-research", "grok", "openai", "codex", "groq"),
              "steal": ("steal", "bench-", "eval-"),
              "doctrine": ("doctrine", "invariant", "constitution", "law", "rib"),
              "operational": ("operational", "run", "loop", "fix", "build", "module")}
_KIND_HINT = {"invariant": ("invariant", "doctrine", "precedes", "law", "principle"),
              "mechanism": ("mechanism", "pipeline", "loop", "flywheel", "render", "compiler"),
              "gap": ("gap", "missing", "uncovered", "gap item", "absent"),
              "tool": ("tool", "module", "script", "surface", "route", "endpoint"),
              "steal": ("steal", "borrowed", "adapted", "stolen"),
              "synthesis": ("synthesis", "deep-research", "research", "synthesize", "analysis"),
              "fact": ("fact", "measured", "billed", "verified", "real data", "trust bytes")}
_DOMAIN_HINT = {"swarm": ("swarm", "flock", "k8s", "agent", "consensus"),
                "memory": ("memory", "verkle", "invariant", "biography", "stateless"),
                "security": ("security", "token", "guard", "probe", "auth", "deniable", "leak"),
                "voice": ("voice", "stt", "whisper", "speech", "earbud", "mic"),
                "wearable": ("wearable", "vr", "ar", "headset", "glasses", "hud", "baymax"),
                "agent-os": ("agent-as-os", "agent os", "tool surface", "machine target", "os"),
                "economics": ("cost", "budget", "rightsize", "token", "spend", "$0"),
                "render": ("render", "shader", "flock_anim", "path", "visual", "image"),
                "compiler": ("compiler", "compile", "lower", "machine", "binary", "rib"),
                "world": ("world", "environment", "doom", "vrm", "3d", "2d", "mesh", "gen"),
                "inference": ("inference", "stochastic", "sampling", "probabilistic", "infer")}

_GROUNDED = ("verified", "grounded", "measured", "billed", "rib", "trust bytes", "rib-debug", "shipped")
_UNGROUNDED = ("unverified", "derived", "estimated", "plan only", "assumption")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _match(text: str, hints) -> list[str]:
    low = (text or "").lower()
    return [h for h in hints if h in low]


def classify(text: str, *, source: str = "") -> dict[str, Any]:
    """ONE lens classification (deterministic keyword). tier × kind × domain × grounding."""
    blob = f"{text} {source}".lower()
    tier = next((t for t, hs in _TIER_HINT.items() if _match(blob, hs)), "operational")
    kind = next((k for k, hs in _KIND_HINT.items() if _match(blob, hs)), "synthesis")
    domain = next((d for d, hs in _DOMAIN_HINT.items() if _match(blob, hs)), "general")
    if any(m in blob for m in _UNGROUNDED):
        grounding = "unverified"
    elif any(m in blob for m in _GROUNDED):
        grounding = "verified"
    else:
        grounding = "unknown"
    return {"tier": tier, "kind": kind, "domain": domain, "grounding": grounding}


def fold_classified(text: str, *, source: str = "", domain: str = "general") -> dict[str, Any]:
    """Percolate (dedup+novelty) THEN classify, and append a uniform, origin-chained row.

    The vertical pointer: each row stores origin (the canonical chain root) + prev_id, so the whole
    body is readable via the same lens AND traceable back to the very beginning (ORIGIN_INVARIANT).
    Deterministic + $0.
    """
    from mag import percolator as pc
    p = pc.percolate(text, source=source or "research_class", domain=domain)
    verdict = p.get("verdict", "no_signal")
    signal = p.get("signal") or (text[:400] if verdict != "no_signal" else "")
    if not signal:
        return {"ok": True, "schema": SCHEMA, "verdict": "no_signal", "classified": None,
                "note": "no signal after percolate (noise already filed)"}
    lens = classify(signal, source=source)
    rows = lens_read(_full=True)
    prev_id = rows[-1]["id"] if rows else None
    origin = hashlib.sha256(ORIGIN_INVARIANT.encode("utf-8")).hexdigest()[:16]
    row = {"id": hashlib.sha256(f"{verdict}:{signal}".encode("utf-8")).hexdigest()[:16],
           "ts": _now(), "source": source, "verdict": verdict,
           "canonical": p.get("canonical"), "signal": signal[:400],
           "lens": lens, "origin": origin, "prev_id": prev_id,
           "depth": (rows[-1]["depth"] + 1) if rows else 1}
    REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    with REGISTRY.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return {"ok": True, "schema": SCHEMA, "verdict": verdict, "classified": row,
            "origin_root": origin}


def lens_read(*, domain: str | None = None, kind: str | None = None, tier: str | None = None,
              _full: bool = False, tail: int = 2000) -> list[dict[str, Any]]:
    """Read ALL classified research through the same lens (uniform rows). Deterministic."""
    out: list[dict[str, Any]] = []
    if not REGISTRY.is_file():
        return out
    for line in REGISTRY.read_text(encoding="utf-8", errors="replace").splitlines()[-tail:]:
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        l = r.get("lens") or {}
        if domain and l.get("domain") != domain:
            continue
        if kind and l.get("kind") != kind:
            continue
        if tier and l.get("tier") != tier:
            continue
        if _full:
            out.append(r)
        else:
            out.append({"id": r["id"], "ts": r["ts"], "verdict": r.get("verdict"),
                        "signal": r.get("signal"), "lens": l, "origin": r.get("origin"),
                        "prev_id": r.get("prev_id"), "depth": r.get("depth")})
    return out


def coverage() -> dict[str, Any]:
    """Coverage by (domain, kind) — where are we thin? Deterministic."""
    rows = lens_read(_full=True)
    by_dk: dict[str, int] = {}
    by_domain: dict[str, int] = {}
    by_kind: dict[str, int] = {}
    for r in rows:
        l = r.get("lens") or {}
        d, k = l.get("domain", "general"), l.get("kind", "synthesis")
        by_dk[f"{d}:{k}"] = by_dk.get(f"{d}:{k}", 0) + 1
        by_domain[d] = by_domain.get(d, 0) + 1
        by_kind[k] = by_kind.get(k, 0) + 1
    return {"n": len(rows), "by_domain": by_domain, "by_kind": by_kind, "by_domain_kind": by_dk,
            "origin_root": hashlib.sha256(ORIGIN_INVARIANT.encode("utf-8")).hexdigest()[:16]}


def gaps(k: int = 6) -> dict[str, Any]:
    """GAP ITEMS: the least-covered (domain, kind) cells + the knowledge-base footprint.
    Proposes filling them with the most efficient tools from our own mirrored ecosystem."""
    cov = coverage()
    cells = cov["by_domain_kind"]
    # all possible domain:kind cells
    all_cells = [(d, k2) for d in DOMAINS for k2 in KINDS]
    zero = [(f"{d}:{k2}", 0) for d, k2 in all_cells if f"{d}:{k2}" not in cells]
    scored = sorted([(c, cells.get(c, 0)) for c in set(list(cells) + [z[0] for z in zero])],
                    key=lambda x: x[1])[:k]
    gap_list = []
    for cell, count in scored:
        gap_list.append({"cell": cell, "count": count, "plan": tool_plan(cell)})
    return {"ok": True, "schema": SCHEMA, "n_classified": cov["n"], "gaps": gap_list,
            "origin_root": cov["origin_root"]}


# ── mirrored tool map: our own ecosystem's tools (knowledge base) ──────────────
_MIRROR = {
    "swarm": ["mag/flock_shader.py", "mag/memweave.py", "mag/flock_grid.py", "mag/swarm_render.py"],
    "memory": ["mag/verkle_knot.py", "mag/percolator.py", "mag/ghost_memlance.py", "mag/rib_bus.py"],
    "security": ["mag/cast_guard.py", "mag/remote_control.py", "mag/ghost_leak_detector.py"],
    "voice": ["mag/voice_stt.py", "mag/voice_trigger.py", "mag/cast_server.py"],
    "wearable": ["mag/wearable_swarm.py", "dashboard/static/wearable.html"],
    "agent-os": ["mag/machine_target.py", "mag/rib_bus.py", "mag/browser_driver.py"],
    "economics": ["mag/cost_learn.py", "mag/model_pick.py", "mag/grok_rightsize.py"],
    "render": ["mag/swarm_render.py", "mag/flock_anim.py", "mag/shader_bus.py"],
    "compiler": ["mag/machine_target.py", "mag/rib_bus.py"],
    "world": ["mag/flock_anim.py", "mag/swarm_render.py", "mag/flock_shader.py"],
    "inference": ["mag/bernaise.py", "mag/behavioral_analytics.py", "mag/tesuji_surface.py"],
    "general": [],
}
_MIRROR_BY_KIND = {"gap": "mag/problem_knot.py", "tool": "mag/steal_pack.py",
                   "synthesis": "mag/fact_bus.py", "invariant": "mag/rib_bus.py",
                   "mechanism": "mag/agent_os_loop.py"}


def tool_plan(cell: str) -> dict[str, Any]:
    """The most efficient tool build for a gap cell, from OUR OWN mirrored tools. $0."""
    d, _, k2 = cell.partition(":")
    tools = list(_MIRROR.get(d, []))
    if k2 in _MIRROR_BY_KIND:
        tools.append(_MIRROR_BY_KIND[k2])
    tools = list(dict.fromkeys([t for t in tools if t]))
    return {"cell": cell, "mirrored_tools": tools,
            "build": f"compose/adapt the mirrored {len(tools)} tool(s) to cover {cell}; "
                     "fold the result via research_class.fold_classified + percolator so it is "
                     "readable through the same lens and chained to origin."}


def status() -> dict[str, Any]:
    cov = coverage()
    return {"ok": True, "schema": SCHEMA, "n_classified": cov["n"],
            "lens": {"tiers": list(TIERS), "kinds": list(KINDS), "domains": list(DOMAINS)},
            "origin_root": cov["origin_root"],
            "registry": str(REGISTRY.relative_to(ROOT)).replace("\\", "/"),
            "cost": "deterministic + $0"}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="research-class")
    ap.add_argument("cmd", nargs="?", default="status",
                    choices=["status", "coverage", "gaps", "lens", "fold"])
    ap.add_argument("--text", default="", help="fold: research text to classify")
    ap.add_argument("--source", default="")
    a = ap.parse_args()
    if a.cmd == "status":
        print(json.dumps(status(), indent=2, default=str))
    elif a.cmd == "coverage":
        print(json.dumps(coverage(), indent=2, default=str))
    elif a.cmd == "gaps":
        print(json.dumps(gaps(), indent=2, default=str))
    elif a.cmd == "lens":
        print(json.dumps(lens_read(), indent=2, default=str))
    else:
        print(json.dumps(fold_classified(a.text, source=a.source), indent=2, default=str))
