"""corpus_expand — expand the research corpus for FREE into our growing library.

The operator's intent: "expand the research corpus for free to expand our own growing
library — we have plenty of bandwidth and space for high-quality source material."

So ghost harvests high-quality sources (free tiers, arXiv, portals, the field corpus,
steal repos) and ingests them into the corpus — growing the library at $0, bounded by
bandwidth/space which we have plenty of. Everything auto-catalogs (learn_rightsize).

  sources()  — the high-quality free sources worth pulling.
  harvest(source) — pull source material for free (local corpus / free-tier portal).
  ingest(text, source) — auto-catalog into the corpus (dedup + fold).
  expand()   — the pass: pull free sources -> ingest -> grow the library, bounded.

CLI:  python -m mag.corpus_expand sources|harvest <source>|expand
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# high-quality free sources worth pulling into the library
_SOURCES = {
    "field_corpus": {
        "local": ROOT.parent / "field-strike-the-chord",
        "why": "the vendor-prompt corpus (our training origin + field-steal source)",
        "free": True,
    },
    "steal_protocol": {
        "local": ROOT / "mine" / "raw" / "steal_protocol",
        "why": "deep-research orchestration repos (conductor, moa, leeroo...)",
        "free": True,
    },
    "sovereign_mirror": {
        "local": ROOT.parent / "worktrees" / "sovereign-mirror-scaffold",
        "why": "the verkle commitment prior art we stole from",
        "free": True,
    },
    "mycelial_republic": {
        "local": ROOT.parent / "mycelial-republic",
        "why": "the training soil / LoRA data partner",
        "free": True,
    },
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sources() -> dict[str, Any]:
    rows = []
    for sid, s in _SOURCES.items():
        local = s.get("local")
        present = bool(local and local.is_dir())
        rows.append({"id": sid, "why": s["why"], "free": s["free"],
                     "present": present, "path": str(local) if local else ""})
    return {"schema": "corpus_expand.sources.v1", "ts": _now(), "n": len(rows), "sources": rows}


def harvest(source: str | None = None) -> dict[str, Any]:
    """Pull a high-quality source's material (free, local corpus) into text chunks."""
    sid = source or "field_corpus"
    s = _SOURCES.get(sid)
    if not s:
        return {"ok": False, "error": f"unknown source {sid}", "known": list(_SOURCES)}
    local = s.get("local")
    if not local or not local.is_dir():
        return {"ok": False, "source": sid, "error": "source not present locally"}
    # path parts that are junk, not high-quality source material — skip them so
    # the free library stays clean (operator: "high-quality source material").
    _JUNK_PARTS = {
        ".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache",
        ".mypy_cache", ".ruff_cache", ".tox", ".hg", ".svn", "dist", "build",
        ".idea", ".vscode", "site-packages", ".next", ".turbo",
    }
    # harvest readable text files as corpus material (free, local)
    chunks = []
    for pat in ("**/*.md", "**/*.txt"):
        for f in list(local.glob(pat)):
            parts = set(f.parts)
            if parts & _JUNK_PARTS:
                continue
            if f.stat().st_size > 2_000_000:
                continue  # skip huge binaries; we have space but keep it sane
            try:
                chunks.append({"file": str(f), "text": f.read_text(encoding="utf-8", errors="replace")[:2000]})
            except Exception:
                continue
    return {"ok": True, "source": sid, "harvested_files": len(chunks),
            "material_kb": sum(len(c["text"]) // 1024 for c in chunks),
            "chunks": chunks[:5]}


def ingest(text: str, source: str) -> dict[str, Any]:
    """Auto-catalog source material into the corpus (dedup + fold)."""
    try:
        from mag.learn_rightsize import auto_catalog
        return auto_catalog(text)
    except Exception as e:
        return {"ok": False, "error": str(e)[:120]}


def expand(*, source: str | None = None) -> dict[str, Any]:
    """The pass: harvest free high-quality sources -> ingest -> grow the library."""
    h = harvest(source)
    if not h.get("ok"):
        return {"schema": "corpus_expand.expand.v1", "ts": _now(), "ok": False,
                "error": h.get("error"), "source": h.get("source")}
    ingested = 0
    examples = []
    for c in h.get("chunks", [])[:10]:
        r = ingest(c.get("text", ""), h.get("source", "corpus"))
        if r.get("cataloged"):
            ingested += 1
            examples.append({"file": c.get("file"), "category": r.get("row", {}).get("category")})
    return {"schema": "corpus_expand.expand.v1", "ts": _now(), "ok": True,
            "source": h.get("source"), "harvested_files": h.get("harvested_files"),
            "ingested": ingested, "examples": examples[:5],
            "note": "free high-quality source material pulled + auto-cataloged into the library"}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv[0] if argv else "sources"
    rest = " ".join(argv[1:]) if len(argv) > 1 else ""
    if cmd == "sources":
        print(json.dumps(sources(), indent=2, ensure_ascii=False))
    elif cmd == "harvest":
        print(json.dumps(harvest(rest or None), indent=2, ensure_ascii=False, default=str))
    elif cmd == "expand":
        print(json.dumps(expand(source=rest or None), indent=2, ensure_ascii=False, default=str))
    else:
        print(json.dumps(sources(), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
