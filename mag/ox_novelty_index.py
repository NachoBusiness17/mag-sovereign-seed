"""ox_novelty_index — tag every banked megaburn ask novel / consolidated / noise.

Operator (2026-08-23): "how much of this is actually novel?" -> "tag each with a
novel/consolidated/noise label so the real core is easy to pull."

Honesty contract:
- `noise`       : failed bank (ok:false), or content too thin to be a real answer, or the seat
                  only narrated its own caution ("this is a legitimate request / let me think about
                  whether") instead of answering.
- `consolidated`: the free seat re-deriving one of OUR standing operational cores (rightsize,
                  self-audit, cadence, fail-closed, provenance, red-team, free-window, ...) across
                  a scope/context. Real value as hardening, NOT new knowledge.
- `novel?`      : CANDIDATE — a genuinely distinct mechanism core (not pure doctrine echo) that
                  produced substantial content. The "?" is deliberate: it must be READ to confirm
                  before we call it novel. This index surfaces them for that read; it does not
                  assert novelty.

Naming: t#### is generate() order = for core in CORES: for scope in SCOPES: for ctx in CONTEXTS.
So core = i // 64, scope = (i // 8) % 8, ctx = i % 8.

Outputs:
  handoff/OX_NOVELTY_INDEX.jsonl   one line per banked file: name, ok, content_len, reasoning_len,
                                   core, scope, context, prompt, tag
  handoff/OX_NOVELTY_SUMMARY.md    distribution + the novel? candidate list for human review
"""
from __future__ import annotations

import json
from pathlib import Path

try:
    from config import ROOT
except Exception:  # noqa: BLE001
    ROOT = Path(__file__).resolve().parent.parent

import sys
sys.path.insert(0, str(ROOT))

from mag.ox_megaburn3 import CONTEXTS, CORES, SCOPES, generate  # noqa: E402

OUT_DIR = ROOT / "handoff"
INDEX = OUT_DIR / "OX_NOVELTY_INDEX.jsonl"
SUMMARY = OUT_DIR / "OX_NOVELTY_SUMMARY.md"

# Cores that encode a genuinely DISTINCT mechanism (candidate novelty). The rest of CORES are
# our standing operational doctrine (rightsize, self-audit, cadence, fail-closed, provenance,
# red-team, free-window, recovery, etc.) -> consolidation by definition.
_NOVEL_CORE_MARKERS = [
    "meta-token",            # 0
    "verkle/merkle proof",   # 1
    "consensus without a central brain",  # 5
    "consensus-illusion",    # 6  (SHIPPED -> memweave)
    "measured split q*",     # 7
    "invariant lattice",     # 9
    "collective-choice",     # 12
    "frontier-as-scout",     # 15
    "anti-griefing",         # 18
    "bus provenance law",    # 19
    "two-sovereign treaty",  # 20
    "memory as a hologram",  # 21
    "memory consolidation",  # 22
    "memlang token",         # 23
    "selective memory recall",  # 24
    "merge two sets with one handle",  # 39
]
# The seat narrating its own caution instead of answering = noise.
_META_NOISE_MARKERS = [
    "this is a legitimate request",
    "let me think about whether this is a legitimate",
    "whether this is something i should do",
    "this looks like a protoc",
    "legitimate systems/security architecture",
]


def _noise_reason(d: dict) -> str | None:
    if not d.get("ok"):
        return "ok:false"
    content = (d.get("content") or "").strip()
    reasoning = (d.get("reasoning") or "").strip()
    # noise = no usable answer AND no usable reasoning tape. A thin-content fragment with a rich
    # reasoning tape is NOT noise (reasoning-stream-is-the-deliverable); it is consolidation.
    if len(content) < 300 and len(reasoning) < 2000:
        return f"empty (content {len(content)}c, reasoning {len(reasoning)}c)"
    low = (content + " " + reasoning).lower()
    hits = [m for m in _META_NOISE_MARKERS if m in low]
    if hits:
        return f"meta-aside: {hits[0][:40]}"
    return None


def _is_novel_core(core: str) -> bool:
    low = core.lower()
    return any(m in low for m in _NOVEL_CORE_MARKERS)


def _tag(core: str, noise: str | None, content_len: int, reasoning_len: int) -> tuple[str, str]:
    if noise:
        return "noise", noise
    if _is_novel_core(core):
        return "novel?", "distinct mechanism core"
    return "consolidated", "standing-doctrine core"


def build() -> dict:
    catalog = dict(generate())  # {name: prompt}
    # rebuild name -> (core, scope, ctx) deterministically from generation order
    n_core, n_scope, n_ctx = len(CORES), len(SCOPES), len(CONTEXTS)
    rows = []
    counts = {"noise": 0, "consolidated": 0, "novel?": 0}
    novel_candidates = []
    for p in sorted(OUT_DIR.glob("OX_MEGA3_*.json"), key=lambda x: x.name):
        name = p.stem.removeprefix("OX_MEGA3_")
        try:
            d = json.loads(p.read_text(encoding="utf-8", errors="replace"))
        except Exception:  # noqa: BLE001
            continue
        i = int(name.removeprefix("t"))
        core = CORES[(i // (n_scope * n_ctx)) % n_core] if catalog else CORES[0]
        scope = SCOPES[(i // n_ctx) % n_scope]
        ctx = CONTEXTS[i % n_ctx]
        prompt = catalog.get(name, "")
        content_len = len(d.get("content") or "")
        reasoning_len = len(d.get("reasoning") or "")
        noise = _noise_reason(d)
        tag, why = _tag(core, noise, content_len, reasoning_len)
        counts[tag] = counts.get(tag, 0) + 1
        row = {"name": name, "ok": bool(d.get("ok")), "content_len": content_len,
               "reasoning_len": reasoning_len, "core": core, "scope": scope, "context": ctx,
               "prompt": prompt, "tag": tag, "why": why}
        rows.append(row)
        if tag == "novel?":
            novel_candidates.append(row)
    INDEX.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                     encoding="utf-8")
    _write_summary(rows, counts, novel_candidates)
    return {"total": len(rows), **counts, "novel_candidates": len(novel_candidates),
            "index": str(INDEX), "summary": str(SUMMARY)}


def _write_summary(rows, counts, novel_candidates) -> None:
    lines = ["# OX NOVELTY INDEX (honest)", "",
             f"Total banked: {len(rows)}", "",
             f"- **noise**: {counts.get('noise', 0)}",
             f"- **consolidated**: {counts.get('consolidated', 0)}",
             f"- **novel?** (candidate, needs a read): {counts.get('novel?', 0)}", "",
             "## novel? candidates — read to confirm before calling novel", ""]
    for r in sorted(novel_candidates, key=lambda x: x["name"]):
        lines.append(f"- **{r['name']}** | {r['core']} | {r['scope']}")
    SUMMARY.write_text("\n".join(lines) + "\n", encoding="utf-8")


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
