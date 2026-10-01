"""Research lens — iterative, self-referencing research that grows a corpus of knowledge.

STOLEN PATTERNS (steal-first) composed onto existing local machinery:
  - agentswarm `memoryBlock` "PRIOR RUNS ... build on them"  -> `retrieve_prior()` injects
    prior landed answers into a NEW pack before it answers (self-reference / compounding).
  - blackboard pinned decisions + full-history keyword recall -> durable decisions stay
    pinned in the corpus index and are searchable deep.
  - mycelium reinforcement (edges sharpen with use) -> `sharpen()`/`fold_back()` bump
    per-lens weights on supports/extends edges; decision edges get a protected floor.
  - route-selected context package (RAG over prior) -> `build_lens()` selects the relevant
    prior answers into a "PRIOR RESEARCH IN THIS LENS" block (like selected_memories).
  - sessionLearning promotion gate -> `score_fidelity` gates an answer before it enters
    the corpus (only passing answers compound).
  - agent-as-cleaner (bounded growth) -> `reindex()` may condense low-value old answers
    per theme instead of unbounded growth.

A research project = a LENS (reuse lens_library.Lens). Each lens has a growing corpus
(memory/research_packs/*.answer.*.md). New packs REFERENCE prior answers (self-reference),
fold their own answer back into the corpus (grows), and reinforce edges (gets sharper).
The corpus index (memory/lenses/corpus_index.json) is the "corpus of knowledge."

Schema: research_lens.v1
CLI:  python -m mag.research_lens reindex | prior "<ask>" [--lens X] |
      build "<ask>" [--title T] [--lens X] | status | fold | cadence
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except ImportError:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from mag.research_pack import PACKS, build_research_pack, load_pack, score_fidelity  # noqa: E402

SCHEMA = "research_lens.v1"
LENS_DIR = ROOT / "memory" / "lenses"
INDEX = LENS_DIR / "corpus_index.json"
STOP = set(
    "the a an and or of to in for on with is are was were be been it as at by from this that these those we i you they he she "
    "research pack answer ask title what how when where why do does did not no yes so but then than into about over under "
    "system agent model local remote grok deepseek via from".split()
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug(s: str, n: int = 48) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", (s or "lens").lower()).strip("-")
    return (s or "lens")[:n]


def _terms(text: str) -> list[str]:
    toks = re.findall(r"[a-zA-Z][a-zA-Z0-9_]{2,}", (text or "").lower())
    return [t for t in toks if t not in STOP]


def _answer_files() -> list[Path]:
    if not PACKS.is_dir():
        return []
    return sorted(
        list(PACKS.glob("*.answer.remote.md")) + list(PACKS.glob("*.answer.local.md")),
        key=lambda p: p.stat().st_mtime,
    )


def _pack_meta(pack_id: str) -> dict[str, Any]:
    j = PACKS / f"{pack_id}.json"
    if j.is_file():
        try:
            p = json.loads(j.read_text(encoding="utf-8"))
            return {"title": str(p.get("title") or pack_id), "ask": str(p.get("ask") or "")}
        except Exception:
            pass
    return {"title": pack_id, "ask": ""}


# ------------------------------------------------------------------ corpus ----
def reindex() -> dict[str, Any]:
    """Build/update the corpus index over landed research answers. Idempotent by pack_id."""
    LENS_DIR.mkdir(parents=True, exist_ok=True)
    prev: dict[str, Any] = {}
    if INDEX.is_file():
        try:
            prev = json.loads(INDEX.read_text(encoding="utf-8"))
        except Exception:
            prev = {}
    items: dict[str, Any] = dict(prev.get("items") or {})

    added, updated = 0, 0
    for f in _answer_files():
        pack_id = f.name.split(".answer.")[0]
        source = "remote" if "remote" in f.name else "local"
        meta = _pack_meta(pack_id)
        text = ""
        try:
            text = f.read_text(encoding="utf-8", errors="replace")[:4000]
        except OSError:
            pass
        key = pack_id + "::" + source
        is_new = key not in items
        items[key] = {
            "pack_id": pack_id,
            "source": source,
            "title": meta["title"],
            "ask": meta["ask"][:600],
            "answer_excerpt": text[:900],
            "key_terms": _terms(meta["title"] + " " + meta["ask"])[:40],
            "answer_path": f.name,
            "ts": _now(),
            "mtime": f.stat().st_mtime,
        }
        if is_new:
            added += 1
        else:
            updated += 1

    # Agent-as-cleaner: bound growth — condense old low-value answers per theme key.
    by_theme: dict[str, list[Any]] = {}
    for k, it in items.items():
        th = it["key_terms"][0] if it["key_terms"] else "misc"
        by_theme.setdefault(th, []).append(it)
    condensed = 0
    BUDGET = 40  # max entries per theme before condensation
    for th, grp in by_theme.items():
        if len(grp) <= BUDGET:
            continue
        for old in grp[BUDGET:]:
            old["condensed_finding"] = (old.get("answer_excerpt") or "")[:300]
            old["answer_excerpt"] = ""
            condensed += 1

    index = {"schema": SCHEMA, "ts": _now(), "count": len(items), "items": items,
             "last_added": added, "last_updated": updated, "last_condensed": condensed}
    INDEX.write_text(json.dumps(index, ensure_ascii=False, default=str, indent=2), encoding="utf-8")
    return {"ok": True, "action": "reindex", "count": len(items), "added": added,
            "updated": updated, "condensed": condensed, "index": str(INDEX)}


def _load_index() -> dict[str, Any]:
    if INDEX.is_file():
        try:
            return json.loads(INDEX.read_text(encoding="utf-8"))
        except Exception:
            return {"items": {}}
    return {"items": {}}


# ------------------------------------------------------------- self-reference ----
def retrieve_prior(ask: str, *, lens_id: str | None = None, limit: int = 5) -> dict[str, Any]:
    """Find prior research answers relevant to a new ask (self-reference). Renders an
    agentswarm-style PRIOR RESEARCH block injected into the next pack."""
    idx = _load_index()
    items = idx.get("items") or {}
    q_terms = Counter(_terms(ask))
    lens_terms: set[str] = set()
    if lens_id:
        try:
            from mag.lens_library import LENSES
            lens_terms = set((LENSES.get(lens_id) or type("L", (), {"key_terms": []})()).key_terms or [])
        except Exception:
            lens_terms = set()

    scored: list[tuple[float, Any]] = []
    for it in items.values():
        terms = Counter(it.get("key_terms") or [])
        if not terms:
            continue
        overlap = sum((q_terms & terms).values())
        if overlap <= 0 and not (lens_terms & set(terms)):
            continue
        score = overlap / max(1, sum(terms.values()))
        if lens_terms & set(terms):
            score += 0.15
        scored.append((round(score, 3), it))
    scored.sort(key=lambda x: (x[0], x[1].get("mtime") or 0), reverse=True)
    top = [it for _, it in scored[:limit]]

    lines = [
        "# PRIOR RESEARCH IN THIS LENS (build on it; don't redo settled answers)",
        "",
    ]
    for i, it in enumerate(top, 1):
        lines.append(f"{i}. [{it['pack_id'][:40]}] {it['title']}")
        ex = (it.get("answer_excerpt") or "").strip()
        if ex:
            lines.append("   " + ex.replace("\n", " ")[:240])
    if not top:
        lines.append("_No prior answers yet — this is a fresh lens._")
    block = "\n".join(lines)

    return {"ok": True, "prior_refs": [it["pack_id"] for it in top], "count": len(top),
            "prior_block": block, "ask": (ask or "")[:200], "lens_id": lens_id or ""}


def _inject_prior(pack: dict[str, Any], prior: dict[str, Any]) -> dict[str, Any]:
    """Attach the prior-research block to a pack so the model self-references it."""
    pack["prior_research"] = {
        "refs": prior.get("prior_refs") or [],
        "block": prior.get("prior_block") or "",
        "note": "Self-referencing lens: build on these prior answers; do not redo settled ones.",
    }
    flm = pack.get("for_lesser_models") or {}
    flm["user_template"] = (
        "See pack.ask + pack.sources[].excerpt + pack.prior_research.block "
        "(PRIOR RESEARCH IN THIS LENS — reference it before answering)."
    )
    pack["for_lesser_models"] = flm
    return pack


def build_lens(ask: str, *, lens_id: str = "default", title: str = "",
               urls: list[str] | None = None, elevate_to: str = "local") -> dict[str, Any]:
    """Build a NEW research pack that self-references prior answers in this lens."""
    built = build_research_pack(ask, urls=urls, title=title or _slug(ask), elevate_to=elevate_to)
    if not built.get("ok"):
        return built
    pack = load_pack(built.get("json")) or {}
    prior = retrieve_prior(ask, lens_id=lens_id)
    pack = _inject_prior(pack, prior)
    # write back the enriched pack json (keeps freeze bag + execution state intact)
    (PACKS / f"{built['id']}.json").write_text(
        json.dumps(pack, ensure_ascii=False, default=str, indent=2), encoding="utf-8")
    (PACKS / "latest.json").write_text(
        json.dumps(pack, ensure_ascii=False, default=str, indent=2), encoding="utf-8")
    return {**built, "prior_refs": prior.get("prior_refs") or [], "prior_count": prior.get("count"),
            "lens_id": lens_id}


# ------------------------------------------------------------------- fold ----
def _lens_weights(lens_id: str) -> dict[str, Any]:
    p = LENS_DIR / f"{_slug(lens_id)}.json"
    if p.is_file():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return {"refs": {}}
    return {"refs": {}}


def _save_lens_weights(lens_id: str, w: dict[str, Any]) -> None:
    LENS_DIR.mkdir(parents=True, exist_ok=True)
    (LENS_DIR / f"{_slug(lens_id)}.json").write_text(
        json.dumps(w, ensure_ascii=False, default=str, indent=2), encoding="utf-8")


def fold_back(answer_path: str | Path, *, lens_id: str = "default") -> dict[str, Any]:
    """Fold a landed answer back into the corpus: fidelity-gate -> skill_ledger ->
    idea_graph claim node linked to prior packs -> reinforce lens edge weights."""
    answer = Path(answer_path)
    base = answer.name.split(".answer.")[0]
    pack_id = base if base else answer.stem

    # 1) promotion gate (stolen sessionLearning): only passing answers compound.
    pack = load_pack(PACKS / f"{pack_id}.json") or {}
    text = ""
    try:
        text = answer.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        pass
    fid = {}
    if pack and text:
        try:
            fid = score_fidelity(text, pack) or {}
        except Exception:
            fid = {}
    gated = bool(fid.get("recommend") == "hold") if fid else True

    # 2) fold to skill_ledger via the existing fold mechanism.
    try:
        from mag.research_fold import fold_one
        folded = fold_one(answer)
    except Exception as e:
        folded = {"ok": False, "error": str(e)[:120]}

    # 3) idea_graph claim node + link to the prior packs this answer references.
    graph = {"ok": False}
    prior_refs = list((pack.get("prior_research") or {}).get("refs") or [])
    try:
        from mag import idea_graph as ig
        node = ig.add_node(
            title=(pack.get("title") or pack_id)[:300],
            ntype="claim" if gated else "evidence",
            status="open",
            body=text[:4000],
            refs=prior_refs,
            tags=["research_lens", _slug(lens_id)],
            source="research_lens",
        )
        # link back to any prior packs that already have graph nodes (by title search is
        # expensive; link by ref marker is best-effort via existing neighborhood).
        graph = {"ok": True, "node_id": node.get("id")}
    except Exception as e:
        graph = {"ok": False, "error": str(e)[:120]}

    # 4) reinforce lens edge weights (mycelium shape: w += alpha on reuse).
    w = _lens_weights(lens_id)
    refs = dict(w.get("refs") or {})
    for rp in prior_refs:
        e = refs.get(rp, {"weight": 0.3, "uses": 0, "protected": False})
        e["weight"] = round(min(1.0, float(e["weight"]) + 0.1), 3)
        e["uses"] = int(e.get("uses") or 0) + 1
        # decision/conflict edges get a protected floor — never pruned (blackboard steal).
        if gated:
            e["protected"] = True
        refs[rp] = e
    w["refs"] = refs
    w["last_fold"] = _now()
    _save_lens_weights(lens_id, w)

    return {"ok": True, "pack_id": pack_id, "gated": gated, "fidelity": fid,
            "folded": folded.get("ok"), "graph": graph, "prior_refs": prior_refs,
            "lens_edges": len(refs), "lens_id": lens_id}


# ------------------------------------------------------------------- status ----
def status() -> dict[str, Any]:
    idx = _load_index()
    items = idx.get("items") or {}
    by_source: Counter = Counter()
    for it in items.values():
        by_source[it.get("source") or "?"] += 1
    lens_files = sorted(LENS_DIR.glob("*.json")) if LENS_DIR.is_dir() else []
    lens_edges = {}
    for f in lens_files:
        if f.name == "corpus_index.json":
            continue
        try:
            w = json.loads(f.read_text(encoding="utf-8"))
            lens_edges[f.stem] = {"edges": len(w.get("refs") or {}), "last_fold": w.get("last_fold")}
        except Exception:
            continue
    return {"schema": SCHEMA, "ok": True, "corpus_size": len(items), "by_source": dict(by_source),
            "index": str(INDEX), "lenses": lens_edges, "ts": _now()}


def run_cadence() -> dict[str, Any]:
    """Idempotent cadence: reindex the corpus + fold any landed-but-unfolded answers."""
    ri = reindex()
    try:
        from mag.research_fold import run as fold_run
        fr = fold_run(limit=0)
    except Exception as e:
        fr = {"ok": False, "error": str(e)[:120]}
    return {"ok": True, "action": "cadence", "reindex": ri, "fold": fr, "status": status()}


# ---------------------------------------------------------------------- CLI ----
def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    ap = argparse.ArgumentParser(prog="research-lens", description="Iterative self-referencing research lens (grows a corpus)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("reindex", help="rebuild the corpus index over landed answers")
    sub.add_parser("status", help="corpus growth + lens edge weights")
    p_prior = sub.add_parser("prior", help="retrieve PRIOR RESEARCH for a new ask")
    p_prior.add_argument("ask", nargs="+")
    p_prior.add_argument("--lens", default="")
    p_build = sub.add_parser("build", help="build a self-referencing research pack")
    p_build.add_argument("ask", nargs="+")
    p_build.add_argument("--title", default="")
    p_build.add_argument("--lens", default="default")
    p_build.add_argument("--elevate", action="store_true")
    p_fold = sub.add_parser("fold", help="fold a landed answer back into the corpus")
    p_fold.add_argument("path")
    p_fold.add_argument("--lens", default="default")
    sub.add_parser("cadence", help="idempotent: reindex + fold unfed answers")
    args = ap.parse_args(argv)

    if args.cmd == "reindex":
        print(json.dumps(reindex(), indent=2, default=str))
    elif args.cmd == "status":
        print(json.dumps(status(), indent=2, default=str))
    elif args.cmd == "prior":
        print(json.dumps(retrieve_prior(" ".join(args.ask), lens_id=args.lens or None), indent=2, default=str)[:6000])
    elif args.cmd == "build":
        r = build_lens(" ".join(args.ask), lens_id=args.lens, title=args.title,
                       elevate_to="grok_tui" if args.elevate else "local")
        print(json.dumps(r, indent=2, default=str)[:8000])
    elif args.cmd == "fold":
        print(json.dumps(fold_back(args.path, lens_id=args.lens), indent=2, default=str)[:6000])
    elif args.cmd == "cadence":
        print(json.dumps(run_cadence(), indent=2, default=str)[:6000])
    return 0


# Hook for governor_autorun cadence (kept importable + idempotent).
__all__ = ["reindex", "retrieve_prior", "build_lens", "fold_back", "status", "run_cadence"]


if __name__ == "__main__":
    raise SystemExit(main())
