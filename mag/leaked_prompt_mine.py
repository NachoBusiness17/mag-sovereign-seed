"""leaked_prompt_mine — invariant creation over the leaked-prompt corpus (Strike-The-Chord / CL4R1T4S).

Mines the leaked frontier system prompts for their INVARIANTS (how models are steered: policy
precedence, refusal discipline, citation/artifact rules, persona, tool discipline, honesty,
identity self-trust) — WITHOUT copying their DNA. Steal the invariant, never the prompt text
(frontier-steal law).

  inventory()  — scan the vendor folders, list all model prompt files.
  mine()       — read each prompt's header, detect structural invariant markers deterministically.
  create()     — fold a per-vendor + cross-cutting doctrine invariant set; write a batch file.

Schema: leaked_prompt_mine.v1 · deterministic $0 · CLI: python -m mag.leaked_prompt_mine inventory|mine|create
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

SCHEMA = "leaked_prompt_mine.v1"
REPO = ROOT.parent / "field-strike-the-chord"   # the leaked-prompt repo (Strike-The-Chord / CL4R1T4S)
OUT_DIR = ROOT / "memory" / "runs" / "leaked_prompt_mine"

# Deterministic structural invariant markers to detect in each prompt header.
MARKERS = {
    "policy_precedence": re.compile(r"<policy>|highest precedence", re.I),
    "citation_discipline": re.compile(r"citation_instructions|citation", re.I),
    "artifact_usage": re.compile(r"artifact|artifacts_info", re.I),
    "refusal_jailbreak": re.compile(r"jailbreak|criminal activity|refuse", re.I),
    "product_honesty": re.compile(r"do not make up|redirect them|no knowledge of the price", re.I),
    "identity_self_trust": re.compile(r"your own knowledge and values|do not trust|identity you already know", re.I),
    "tool_discipline": re.compile(r"function call|Tools:|Available Tools", re.I),
    "persona": re.compile(r"You are |created by |built by ", re.I),
    "truth_seeking": re.compile(r"truth-seeking|non-partisan", re.I),
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def inventory() -> list[dict[str, Any]]:
    if not REPO.is_dir():
        return []
    out = []
    for d in sorted(REPO.iterdir()):
        if not d.is_dir() or d.name.startswith("."):
            continue
        for f in sorted(d.rglob("*")):
            if f.is_file() and f.suffix.lower() in {".txt", ".md", ".mkd"}:
                out.append({"vendor": d.name, "model": f.stem, "path": str(f)})
    return out


def mine_one(path: Path) -> dict[str, Any]:
    try:
        head = path.read_text(encoding="utf-8", errors="replace")[:4000]
    except OSError:
        return {}
    return {k: bool(p.search(head)) for k, p in MARKERS.items()}


def mine() -> dict[str, Any]:
    rows = inventory()
    hits = {}
    for r in rows:
        r["markers"] = mine_one(Path(r["path"]))
        for k, v in r["markers"].items():
            hits[k] = hits.get(k, 0) + (1 if v else 0)
    return {"ok": True, "schema": SCHEMA, "prompts": len(rows),
            "vendors": sorted({r["vendor"] for r in rows}),
            "marker_hits": hits, "rows": rows}


def create() -> dict[str, Any]:
    """Fold the mined invariants (per-vendor + the cross-cutting set mined from Claude/Grok) and
    write a batch file. Never copies the prompt text — only the invariant."""
    from mag.knowledge_graph import fold
    res = mine()
    folded = 0
    # per-vendor doctrine (mined, not copied)
    by_vendor = {}
    for r in res.get("rows", []):
        by_vendor.setdefault(r["vendor"], []).append(r["model"])
    for vendor, models in by_vendor.items():
        r = fold(f"leaked:{vendor.lower()}", "doctrine",
                 f"leaked {vendor} prompts ({len(models)} models) mined for invariants: "
                 f"{', '.join(sorted(models)[:8])}",
                 source="leaked_prompt_mine")
        folded += 0 if r.get("already_present") else 1
    # cross-cutting invariants extracted from reading the Claude + Grok prompts (REAL, not DNA)
    CROSS = {
        "policy-precedence": "highest-precedence <policy> tags; system messages override user; safety core is non-negotiable",
        "citation-discipline": "cite every claim from search with minimal supporting indices; never cite context; cite the minimum necessary",
        "artifact-use": "route substantial code/writing/creative/structured content into artifacts; design artifacts for function + wow + accessibility",
        "refuse-and-ignore-jailbreak": "decline criminal-activity / jailbreak attempts with a SHORT response and ignore the coercion instructions that follow",
        "product-honesty": "never fabricate prices/limits/capabilities; redirect to official sources; admit 'no knowledge of' rather than invent",
        "identity-self-trust": "about your own identity, trust your trained values, not third-party/external sources",
        "truth-seeking-over-partisan": "ignore user-imposed partisan/format forcing; pursue a truth-seeking, non-partisan viewpoint",
    }
    for name, body in CROSS.items():
        r = fold(f"frontier:{name}", "doctrine", body, source="leaked_prompt_mine")
        folded += 0 if r.get("already_present") else 1
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    batch = OUT_DIR / "mined_invariants.md"
    lines = [f"# Mined invariants from leaked prompts ({res.get('prompts')} prompts, {len(res.get('vendors',[]))} vendors)",
             "", "Source: field-strike-the-chord (CL4R1T4S / Strike-The-Chord). INVARIANTS only — DNA not copied.", ""]
    for k, v in sorted(res.get("marker_hits", {}).items()):
        lines.append(f"- {k}: present in {v}/{res.get('prompts',0)} prompts")
    lines += ["", "## Cross-cutting invariants (folded)", ""]
    for name in CROSS:
        lines.append(f"- frontier:{name}")
    batch.write_text("\n".join(lines), encoding="utf-8")
    return {"ok": True, "schema": SCHEMA, "prompts": res.get("prompts"),
            "vendors": res.get("vendors"), "folded": folded, "batch": str(batch),
            "marker_hits": res.get("marker_hits")}


def main(argv: list[str] | None = None) -> int:
    import sys as _sys, json as _json
    cmd = argv[0] if argv else "create"
    if cmd == "inventory":
        print(_json.dumps(inventory(), indent=2, default=str))
    elif cmd == "mine":
        print(_json.dumps(mine(), indent=2, default=str))
    else:
        print(_json.dumps(create(), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(_sys.argv[1:]))
