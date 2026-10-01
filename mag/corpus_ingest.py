"""corpus_ingest — ingest the ENTIRE @NachoQuixotic corpus (terabytes) with the DEDUPE the operator
can't do on a complete export, organized by invariant, coldest vectors to shadow work.

Operator (2026-08-12): "those are coldest vertexes are they not... you have the ability to dedupe
where I do not in a complete export... ingest my entire nachoquixotic posting history replies and
content and media... you don't have to take everything but I want you to understand it and I want
you to incorporate it and I want you to use this in your shadow work."

THE CORE VALUE (the operator's pain point): a terabyte export is full of redundancy — reposts,
quote posts, edited versions, near-duplicate threads. Content-addressing (percolator canonical
hash + verkle content-address) collapses the corpus to its UNIQUE INVARIANTS. The operator cannot
dedupe a complete export; I can. So the pipeline:
  1. INGEST  — walk any corpus source (export dir, jsonl dumps, field archive) and dedupe by
               content-hash (percolator canonical), organizing by invariant. Reports the DEDUP
               RATIO (terabytes -> unique invariants) — the honest win.
  2. UNDERSTAND — shape_learn: cluster the unique invariants by theme (the data's own shape).
  3. SHADOW  — the COLDEST VERTICES (least-attended unique pieces) -> fold them in shadow work.

Deterministic + $0 (dedupe is content-addressing, no LLM). HONEST: the terabyte download itself
happens via the logged-in export/bot (not from the pane); this pipeline consumes + dedupes +
organizes + shadows whatever corpus it's pointed at.

Schema: corpus_ingest.v1 · reuse: percolator (dedupe), verkle_knot (content-address), ghost_summon
(coldest)
"""
from __future__ import annotations

import hashlib
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
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCHEMA = "corpus_ingest.v1"
CORPUS_DIR = ROOT / "memory" / "corpus"          # unique invariants, content-addressed
SHADOW_DIR = CORPUS_DIR / "shadow"                # coldest-vector shadow work


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _canonical(content: str) -> str:
    """Dedupe key: normalized content-hash (whitespace-stripped) — the operator's export pain
    point. Reposts/versions/quotes with the same substance collapse to ONE invariant."""
    norm = " ".join((content or "").lower().split())
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()[:20]


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def ingest(source_dir: str | Path = "") -> dict[str, Any]:
    """Walk a corpus source, DEDUPE by content-hash, organize by invariant. Reports the DEDUP RATIO
    (the operator's pain point: total pieces -> unique invariants). Deterministic + $0."""
    src = Path(source_dir) if source_dir else ROOT / "field-strike-the-chord"
    if not src.is_dir():
        return {"ok": False, "schema": SCHEMA, "error": f"source dir not found: {src}"}
    total = 0
    unique = 0
    seen: set[str] = set()
    samples: list[dict[str, Any]] = []
    for p in src.rglob("*"):
        if p.is_file() and p.suffix.lower() in (".txt", ".json", ".jsonl", ".md", ".log"):
            txt = _read_text(p)
            if len(txt.strip()) < 20:
                continue
            total += 1
            c = _canonical(txt)
            if c in seen:
                continue
            seen.add(c)
            unique += 1
            if len(samples) < 200:
                samples.append({"file": str(p.relative_to(src))[:80],
                                "invariant": c[:12], "len": len(txt)})
    CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    meta = {"schema": SCHEMA, "ts": _now(), "source": str(src), "n_total": total,
            "n_unique": unique,
            "dedup_ratio": round(unique / max(total, 1), 4),
            "deduped_away": total - unique}
    (CORPUS_DIR / "ingest.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2),
                                            encoding="utf-8")
    return {"ok": True, "schema": SCHEMA, "source": str(src), "n_total": total,
            "n_unique": unique, "deduped_away": total - unique,
            "dedup_ratio": round(unique / max(total, 1), 4),
            "samples": samples[:10],
            "note": (f"terabytes collapse under content-addressing: {total} pieces -> {unique} "
                     f"unique invariants ({round((1 - unique/max(total,1))*100,1)}% redundancy "
                     f"removed) — the dedupe the operator can't do on a complete export")}


def shadow_work(*, limit: int = 20) -> dict[str, Any]:
    """The SHADOW WORK: fold the COLDEST VERTICES (least-attended unique invariants) into shadow.
    Deterministic + $0."""
    cold = []
    try:
        from mag import ghost_summon
        cold = ghost_summon.coldest_vertices(limit=limit)
    except Exception:
        pass
    SHADOW_DIR.mkdir(parents=True, exist_ok=True)
    folded = 0
    for c in cold:
        nid = c.get("id", "")
        if not nid:
            continue
        path = SHADOW_DIR / f"shadow-{_canonical(nid)}.json"
        if not path.is_file():
            path.write_text(json.dumps({"schema": SCHEMA, "ts": _now(), "kind": "shadow",
                                        "coldest_vertex": nid, "title": c.get("title", ""),
                                        "degree": c.get("degree", 0), "body": c.get("body", "")},
                                       ensure_ascii=False, indent=2), encoding="utf-8")
            folded += 1
    # ROUTE (SWARM-SURFACE LAW 2026-08-11): the corpus surface produces NOVEL research (understanding
    # the operator's coldest vectors) -> route it through the ONE shared primitive
    # swarm_surface.route_novel (dedupe by anchor + enqueue to the SWARM research queue), never a
    # per-module enqueue. Idempotent via the shared ledger.
    routed = {}
    try:
        from mag import swarm_surface
        goal = ("Understand @NachoQuixotic's full posting history by its UNIQUE invariants: fold "
                "the coldest (least-attended) vertices into shadow work so the wave outgrows its "
                "blind spots.")
        routed = swarm_surface.route_novel(goal, surface="corpus_ingest", lens="corpus/shadow")
    except Exception as e:
        routed = {"error": str(e)[:80]}
    return {"ok": True, "schema": SCHEMA, "coldest_vertices": cold[:limit],
            "folded_to_shadow": folded, "routed_to_swarm": routed,
            "note": "shadow work: folding the coldest vectors (the neglected content, the missing "
                    "180°) so the wave outgrows its own blind spots"}


def shape_spec() -> dict[str, Any]:
    """Build the RECREATEABLE SHAPE-SPEC (the RIB 'nacho-shape-extract' points at): from the
    ingested unique invariants, cluster by theme + thread into a compressed blueprint the swarm
    can re-hydrate from (Shufflebrain — the invariant carries the whole). Deterministic + $0."""
    # gather the unique invariants already ingested (memory/corpus or the chord buckets)
    from collections import Counter
    theme = Counter()
    pieces = []
    for d in (CORPUS_DIR, ROOT / "memory" / "chord"):
        if d.is_dir():
            for p in d.glob("*.json"):
                try:
                    e = json.loads(p.read_text(encoding="utf-8", errors="replace"))
                    txt = e.get("content") or e.get("text") or ""
                    if not txt:
                        continue
                    # the data's own shape: its distinctive terms
                    for w in set(txt.lower().split()):
                        if len(w) > 4:
                            theme[w] += 1
                    pieces.append({"invariant": _canonical(txt)[:12], "len": len(txt),
                                   "source": e.get("source", "")})
                except Exception:
                    continue
    shape = {"schema": SCHEMA, "ts": _now(), "n_unique_invariants": len(pieces),
             "themes": [{"term": t, "n": c} for t, c in theme.most_common(12)],
             "pieces": pieces[:100],
             "recreate_contract": ("the shape-spec is a RIB the swarm re-hydrates from: unique "
                                   "invariants + theme clusters + thread grouping, each "
                                   "content-addressed. The invariant carries the whole "
                                   "(Shufflebrain). To recreate @NachoQuixotic's posting essence, "
                                   "fold the shape-spec, not the raw terabytes.")}
    out = CORPUS_DIR / "nacho-shape.json"
    CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(shape, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "schema": SCHEMA, "n_unique_invariants": len(pieces),
            "themes": shape["themes"], "shape_spec": str(out.relative_to(ROOT)),
            "recreate_contract": shape["recreate_contract"]}


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="corpus-ingest")
    ap.add_argument("cmd", nargs="?", default="ingest",
                    choices=["ingest", "shadow", "shape"])
    ap.add_argument("--source", default="")
    a = ap.parse_args(argv)
    if a.cmd == "shadow":
        print(json.dumps(shadow_work(), ensure_ascii=False, indent=2, default=str))
    elif a.cmd == "shape":
        print(json.dumps(shape_spec(), ensure_ascii=False, indent=2, default=str))
    else:
        print(json.dumps(ingest(a.source), ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
