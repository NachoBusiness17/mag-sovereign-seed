"""mine_diamonds — surface the highest-signal items already in our weave.

Deterministic, $0 "simply looking": the content-addressed verkle chain + research packs +
skill_ledger + one_sizer are a DEDUPED record of everything novel we've done (duplicates are
already collapsed by _leaf_hash). So the diamonds are hiding among them — this scans and ranks
them by DISCRIMINATING signal (recency + cross-lens convergence + cost-savings + win-rate) so we
can see the gems we didn't know we had, then feed them back via steal_pack/pro_library.

Signal model (v2) — each gem scores on 4 independent rails, weighted so the ranking actually
separates the rough from the diamond (this is the "extract training signal" step of the
self-training pipeline: record decisions -> surface proven gems -> fold to case law):
  base         0.35 — raw magnitude (leaves / runs / rows)
  convergence  0.30 — how many DISTINCT lenses (chain / packs / ledger / sizer) corroborate it
  recency      0.20 — how fresh it is (newer steals/research = fresher signal)
  savings      0.15 — cost-savings evidence (a folded frontier steal that cost pennies is a gem)

A gem that is big AND corroborated across lenses AND recent AND cost-saving outranks a gem that
is merely "present" — that's the discriminator v1 was missing.

Schema: mine_diamonds.v2
CLI: python -m mag.mine_diamonds [--top 10] [--digest]
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
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

SCHEMA = "mine_diamonds.v2"
CHAIN = ROOT / "memory" / "biography" / "verkle_chain.jsonl"
PACKS = ROOT / "memory" / "research_packs"
LEDGER = ROOT / "memory" / "improve" / "skill_ledger.jsonl"
SIZER = ROOT / "memory" / "learn" / "sizing.jsonl"
HANDOFF = ROOT / "queue" / "handoff"

# Rails: weights must sum to 1.0
_W = {"base": 0.35, "convergence": 0.30, "recency": 0.20, "savings": 0.15}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except Exception:
        return 0.0


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    out = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except (json.JSONDecodeError, TypeError):
            continue
    return out


# ---------------------------------------------------------------------------
# lens readers — each returns gems with a "base" + keyword list for convergence
# ---------------------------------------------------------------------------
def _verkle_gems() -> list[dict[str, Any]]:
    rows = _read_jsonl(CHAIN)
    n = max(1, len(rows))
    themes = Counter(str(r.get("theme") or r.get("dominant_theme") or "untagged") for r in rows)
    gems = []
    for t, c in themes.most_common(8):
        keywords = {w for w in t.replace("_", " ").split() if len(w) > 2}
        gems.append({"kind": "chain_theme", "name": t, "leaves": c,
                     "base": min(1.0, c / 20.0), "keywords": keywords,
                     "recency": _mtime(CHAIN), "savings": 0.0,
                     "note": f"{c}/{n} leaves ({c/n:.0%} of chain)"})
    return gems


def _pack_gems() -> list[dict[str, Any]]:
    if not PACKS.is_dir():
        return []
    gems = []
    for p in sorted(PACKS.glob("*.answer.*.md")):
        text = p.read_text(encoding="utf-8", errors="replace")
        title = ""
        for ln in text.splitlines():
            if ln.startswith("# "):
                title = ln[2:].strip()[:80]
                break
        slug = p.stem.replace(".answer.remote", "").replace(".answer.local", "")
        keywords = {w for w in slug.replace("_", " ").replace("-", " ").split() if len(w) > 3}
        keywords |= {w for w in title.replace("_", " ").split() if len(w) > 4}
        remote = ".remote." in p.name
        gems.append({"kind": "research_pack", "name": title or p.stem, "file": p.name,
                     "slug": slug, "chars": len(text), "base": 1.0,
                     "keywords": keywords, "recency": _mtime(p),
                     "savings": 0.6 if remote else 0.2,
                     "note": "folded steal/roadmap (case law)" + (" · frontier" if remote else " · local")})
    return gems


def _ledger_gems() -> list[dict[str, Any]]:
    rows = _read_jsonl(LEDGER)
    by_shape: dict[str, list[bool]] = defaultdict(list)
    for r in rows:
        shape = str(r.get("task_shape") or r.get("shape") or "?")
        ok = str(r.get("outcome") or "ok") in ("ok", "done", "success")
        by_shape[shape].append(ok)
    gems = []
    for shape, oks in by_shape.items():
        ok_rate = sum(oks) / len(oks) if oks else 0
        # only "proven moves" (validated + repeated) are ledger diamonds
        if len(oks) >= 3 and ok_rate >= 0.7:
            keywords = {w for w in shape.replace("_", " ").split() if len(w) > 2}
            gems.append({"kind": "ledger_win", "name": f"task_shape={shape}",
                         "runs": len(oks), "win_rate": round(ok_rate, 2),
                         "base": round(ok_rate, 2), "keywords": keywords,
                         "recency": _mtime(LEDGER), "savings": 0.3,
                         "note": f"{len(oks)} runs, {ok_rate:.0%} ok — a proven move"})
    return gems


def _sizer_gems() -> list[dict[str, Any]]:
    rows = _read_jsonl(SIZER)
    if not rows:
        return []
    domains = Counter(str(r.get("domain") or "general") for r in rows)
    gems = []
    for d, c in domains.most_common(5):
        keywords = {w for w in d.replace("_", " ").split() if len(w) > 2}
        gems.append({"kind": "sizer_domain", "name": f"domain={d}", "rows": c,
                     "base": min(1.0, c / 10.0), "keywords": keywords,
                     "recency": _mtime(SIZER), "savings": 0.2,
                     "note": f"{c} sizing rows"})
    return gems


# ---------------------------------------------------------------------------
# convergence + ranking
# ---------------------------------------------------------------------------
def _lens_indexes(gems: list[dict[str, Any]]) -> list[set[str]]:
    """One keyword set per lens, so a gem can count how many lenses corroborate it."""
    per_lens: dict[str, set[str]] = defaultdict(set)
    for g in gems:
        per_lens[g["kind"]].update(g.get("keywords") or set())
    seen: set[str] = set()
    idx: list[set[str]] = []
    for g in gems:
        k = g["kind"]
        if k not in seen:
            seen.add(k)
            idx.append(per_lens[k])
    return idx


def _convergence(gem: dict[str, Any], lenses: list[set[str]]) -> int:
    kw = gem.get("keywords") or set()
    if not kw:
        return 1
    return max(1, sum(1 for lens in lenses if kw & lens))


def _rank(gems: list[dict[str, Any]]) -> list[dict[str, Any]]:
    lenses = _lens_indexes(gems)
    newest = max((g["recency"] for g in gems), default=0.0)
    oldest = min((g["recency"] for g in gems), default=0.0)
    span = max(1e-9, newest - oldest)
    for g in gems:
        conv = _convergence(g, lenses) / len(lenses)
        rec = 0.0 if span == 0 else (g["recency"] - oldest) / span
        g["convergence"] = round(min(1.0, conv), 2)
        g["recency_score"] = round(min(1.0, rec), 2)
        g["savings"] = round(float(g.get("savings", 0.0)), 2)
        g["signal"] = round(
            _W["base"] * float(g["base"])
            + _W["convergence"] * float(g["convergence"])
            + _W["recency"] * float(g["recency_score"])
            + _W["savings"] * float(g["savings"]),
            3,
        )
    gems.sort(key=lambda g: -float(g["signal"]))
    return gems


def diamonds(top: int = 10) -> dict[str, Any]:
    gems = _verkle_gems() + _pack_gems() + _ledger_gems() + _sizer_gems()
    gems = _rank(gems)
    return {"ok": True, "schema": SCHEMA, "ts": _now(), "scanned": {
                "chain_leaves": len(_read_jsonl(CHAIN)),
                "research_packs": len(list(PACKS.glob("*.answer.*.md"))) if PACKS.is_dir() else 0,
                "ledger_rows": len(_read_jsonl(LEDGER)),
                "sizer_rows": len(_read_jsonl(SIZER)),
            },
            "top_diamonds": gems[:top]}


def digest(top: int = 8) -> dict[str, Any]:
    """Write the top diamonds as a handoff doc that steal_pack auto-files to case law."""
    r = diamonds(top)
    lines = ["# Mine Diamonds — top gems surfaced by simply looking",
             "", f"- schema: {SCHEMA}", f"- ts: {r['ts']}", f"- scanned: {json.dumps(r['scanned'])}", ""]
    for g in r["top_diamonds"]:
        lines.append(f"## {g['kind']}: {g['name']}  (signal={g['signal']})")
        lines.append(f"- convergence={g.get('convergence')} recency={g.get('recency_score')} "
                     f"savings={g.get('savings')}")
        lines.append(f"- {g.get('note', '')}")
        lines.append("")
    HANDOFF.mkdir(parents=True, exist_ok=True)
    out = HANDOFF / "STEAL_MINE_DIAMONDS.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    return {"ok": True, "digest": str(out), "n": len(r["top_diamonds"]),
            "top": [{k: g[k] for k in ("kind", "name", "signal")} for g in r["top_diamonds"]]}


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="mine-diamonds")
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--digest", action="store_true", help="also write STEAL_MINE_DIAMONDS.md for steal_pack")
    args = ap.parse_args(argv)
    r = diamonds(args.top)
    if args.digest:
        r["digest"] = digest(args.top)
    print(json.dumps(r, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
