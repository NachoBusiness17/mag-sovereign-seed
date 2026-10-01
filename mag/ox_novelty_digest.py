"""ox_novelty_digest — dedupe the novel? candidate pool down to DISTINCT mechanisms.

The 318 "novel?" tags overcount because each novel core generates 64 scope/context variants that
mostly re-derive the SAME mechanism. This script clusters those variants (by shingle overlap
within a core) and emits ONE representative per distinct mechanism, so we can read the real core
instead of 318 near-copies.

Output: handoff/OX_NOVELTY_DIGEST.md
Each entry: core | distinct-mechanism id | variant count | scope | representative content opening.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

try:
    from config import ROOT
except Exception:  # noqa: BLE001
    ROOT = Path(__file__).resolve().parent.parent

OUT_DIR = ROOT / "handoff"
INDEX = OUT_DIR / "OX_NOVELTY_INDEX.jsonl"
DIGEST = OUT_DIR / "OX_NOVELTY_DIGEST.md"


def _shingles(text: str, k: int = 8) -> set[str]:
    toks = re.findall(r"[a-z0-9]+", text.lower())
    return {" ".join(toks[i:i + k]) for i in range(max(0, len(toks) - k + 1))}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _content(name: str) -> str:
    try:
        p = OUT_DIR / f"OX_MEGA3_{name}.json"
        d = json.loads(p.read_text(encoding="utf-8", errors="replace"))
        return d.get("content") or d.get("reasoning") or ""
    except Exception:  # noqa: BLE001
        return ""


def build() -> dict:
    rows = [json.loads(l) for l in INDEX.read_text(encoding="utf-8", errors="replace").splitlines()
            if l.strip() and json.loads(l).get("tag") == "novel?"]
    # A "distinct mechanism" is one (core x scope): the 8 contexts are surface-variants of the same
    # kind of work. Pick the MOST substantial (longest content) variant as the representative.
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in rows:
        groups[(r["core"], r["scope"])].append(r)

    out: list[dict] = []
    for (core, scope), items in groups.items():
        rep = max(items, key=lambda x: x["content_len"])
        opening = _content(rep["name"]).strip().replace("\n", " ")[:340]
        out.append({"core": core, "scope": scope, "variants": len(items),
                    "names": [x["name"] for x in items], "opening": opening})

    out.sort(key=lambda x: (-x["variants"], x["core"]))
    lines = ["# OX NOVELTY DIGEST — distinct mechanisms in the 318-pool (core x scope)", "",
             f"Novel? pool: {len(rows)} variants -> {len(out)} distinct (core x scope) mechanisms",
             "", "## Distinct mechanisms", ""]
    for c in out:
        lines.append(f"### {c['core']} | {c['scope']}  [{c['variants']} variants]  names={c['names']}")
        lines.append(f"**opening:** {c['opening']}...")
        lines.append("")
    DIGEST.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"pool": len(rows), "distinct_mechanisms": len(out), "digest": str(DIGEST)}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    res = build()
    if a.json:
        print(json.dumps(res, indent=2, ensure_ascii=False))
    else:
        for k, v in res.items():
            print(f"{k}: {v}")
