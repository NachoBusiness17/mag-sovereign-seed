"""steal_pack — file STEAL outputs into the swarm research-pack pipeline.

Every external-steal / deep-research / distillation we produce (queue/handoff/STEAL_*,
DEEP_RESEARCH_*, DISTILLED_*) currently sits as a one-off markdown file. This capability
FILES each into the research-pack pipeline (memory/research_packs/*.answer.remote.md) so it:
  1. auto-folds to skill_ledger as case law (research_fold.fold_one),
  2. becomes a lens reading (research_lens corpus) for cross-domain convergence,
  3. is verkle-anchored (shared chain), and
  4. is self-referenced by future research packs (retrieve_prior).

Deterministic ($0, no LLM) — it just routes the already-produced steal bytes into the
learning loop. Schema: steal_pack.v1

CLI:  python -m mag.steal_pack <file> [--tag steal]     file one steal into a research pack
      python -m mag.steal_pack --all                    file every queue/handoff steal/roadmap/distill
      python -m mag.steal_pack status                   show what's already filed vs pending
"""
from __future__ import annotations

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

SCHEMA = "steal_pack.v1"
PACKS = ROOT / "memory" / "research_packs"
HANDOFF = ROOT / "queue" / "handoff"
STOLEN_LOG = ROOT / "memory" / "runs" / "steal_pack" / "filed.jsonl"
LENS_LOG = ROOT / "memory" / "steal_lens" / "records.jsonl"  # inherent lens record per steal

# Handoff files that are steal/research/distill outputs worth filing.
_PATTERNS = ("STEAL_", "DEEP_RESEARCH_", "DISTILLED_", "SKILLS_ROADMAP", "CODE_MAP_DISTILLED")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _log_filed(slug: str, path: str, fold_ok: bool) -> None:
    STOLEN_LOG.parent.mkdir(parents=True, exist_ok=True)
    with STOLEN_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": _now(), "slug": slug, "path": path,
                            "fold_ok": bool(fold_ok)}, ensure_ascii=False) + "\n")


def _filed_slugs() -> set[str]:
    if not STOLEN_LOG.is_file():
        return set()
    slugs = set()
    for line in STOLEN_LOG.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            slugs.add(str(json.loads(line).get("slug") or ""))
        except Exception:
            continue
    return slugs


def _lens_record(slug: str, text: str) -> dict[str, Any]:
    """The INHERENT lens pass on a steal: novelty + keyword_lens + invariant shard + gpu route.
    Deterministic, $0. Appends one lensed steal record (5 W's + lens + shard + resource)."""
    rec: dict[str, Any] = {"ts": _now(), "schema": "steal_lens.v1", "slug": slug}
    try:
        from mag import novelty_lens
        nv = novelty_lens.novelty(text)
        rec["novelty"] = nv["novelty"]; rec["verdict"] = nv["verdict"]
    except Exception as e:
        rec["novelty_error"] = str(e)[:100]
    try:
        from mag import novelty_lens
        kl = novelty_lens.keyword_lens(slug)
        rec["lens"] = kl.get("lens"); rec["kind"] = kl.get("kind")
        rec["similar_systems"] = kl.get("similar_systems", [])
    except Exception as e:
        rec["lens_error"] = str(e)[:100]
    try:
        from mag import cache_shard
        rec["shard_id"] = cache_shard.shard_key(text).get("shard_id")
    except Exception as e:
        rec["shard_error"] = str(e)[:100]
    try:
        from mag import gpu_lifecycle
        g = gpu_lifecycle.route(work="steal")
        rec["gpu"] = {"target": g.get("target"), "free": g.get("free_for_render")}
    except Exception as e:
        rec["gpu_error"] = str(e)[:100]
    try:
        LENS_LOG.parent.mkdir(parents=True, exist_ok=True)
        with LENS_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
    except Exception:
        pass
    return rec


def file_steal(src: Path, *, tag: str = "steal", remote: bool = True, force: bool = False,
               lens: bool = True) -> dict[str, Any]:
    """File one steal/research output into the research-pack pipeline and fold it to case law.
    Inherently runs the lens pass (novelty + lens + shard + gpu) unless lens=False."""
    src = Path(src)
    if not src.is_file():
        return {"ok": False, "error": f"not a file: {src}"}
    slug = src.stem.lower().replace(" ", "-")[:80] or "steal"
    PACKS.mkdir(parents=True, exist_ok=True)
    ans = PACKS / f"{slug}.answer.{'remote' if remote else 'local'}.md"
    if ans.is_file() and not force:
        return {"ok": False, "error": f"already filed: {ans.name}", "already": True}
    content = src.read_text(encoding="utf-8", errors="replace").strip()
    lens_rec = _lens_record(slug, content) if lens else {}
    header = (f"# {src.stem}\n- source: steal_pack ({tag})\n- filed: {_now()}\n"
              f"- original: {src.name}\n\n")
    ans.write_text(header + content, encoding="utf-8")
    fold_ok = False
    try:
        from mag.research_fold import fold_one
        fold_ok = bool(fold_one(ans).get("ok", True))
    except Exception as e:
        fold_ok = False
    # verkle-anchor the steal so it's on the shared chain + self-referenced later
    verkle = {}
    try:
        from mag.verkle_knot import append_verkle_knot
        verkle = append_verkle_knot({"session_id": f"steal_pack-{slug}",
                                     "theme": "steal", "summary": f"[steal:{tag}] {src.stem}"}) or {}
    except Exception:
        pass
    _log_filed(slug, str(ans), fold_ok)
    return {"ok": True, "slug": slug, "answer_path": str(ans),
            "fold_ok": fold_ok, "verkle": bool(verkle), "tag": tag,
            "lens": lens_rec}


def file_all(*, tag: str = "steal") -> dict[str, Any]:
    """File every matching queue/handoff steal/roadmap/distill not yet filed."""
    filed, skipped, errors = [], [], []
    for p in sorted(HANDOFF.glob("*.md")) if HANDOFF.is_dir() else []:
        if not p.name.startswith(_PATTERNS):
            continue
        if p.stem in _filed_slugs():
            skipped.append(p.name)
            continue
        r = file_steal(p, tag=tag)
        (filed if r.get("ok") else errors).append({"file": p.name, **{k: r.get(k) for k in ("fold_ok", "error") if k in r}})
    return {"ok": True, "filed": filed, "skipped": skipped, "errors": errors}


def status() -> dict[str, Any]:
    pending = sorted(p.name for p in (HANDOFF.glob("*.md") if HANDOFF.is_dir() else [])
                     if p.name.startswith(_PATTERNS) and p.stem not in _filed_slugs())
    filed = sorted(_filed_slugs())
    return {"schema": SCHEMA, "packs_dir": str(PACKS), "filed": len(filed),
            "pending": pending, "filed_slugs": filed}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] == "status":
        print(json.dumps(status(), indent=2, default=str))
        return 0
    if argv[0] == "--all":
        print(json.dumps(file_all(), indent=2, default=str))
        return 0
    tag = "steal"
    if "--tag" in argv:
        i = argv.index("--tag")
        tag = argv[i + 1]
        del argv[i:i + 2]
    print(json.dumps(file_steal(argv[0], tag=tag), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
