"""ram_cache — use available SYSTEM RAM as an in-memory corpus fast-path.

Operator (2026-08-12): "I've got available resources on my SSD and memory... would using more memory
help?" + "use it" (then going to bed = JUST EXECUTE). The data-processing (lensing, novelty scoring,
swarm-data processing) reads the corpus from DISK every pass. With available RAM we hold the corpus
+ derived embeddings in MEMORY (module-level cache) so repeated passes skip disk I/O.

This is the memory-lattice idea applied to system RAM: the corpus lives hot in RAM; the lensing /
novelty scoring / processing read from it, not the disk. Guarded + deterministic + $0. Never breaks
the cadence (worst case = falls back to disk).

Schema: ram_cache.v1
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "ram_cache.v1"
MAX_CORPUS_CHARS = 2_000_000          # cap the in-memory corpus (RAM is bounded, don't OOM)

# module-level cache: loaded once, served from RAM on repeated passes
_CACHE: dict[str, Any] = {"loaded": False, "documents": [], "text": "", "counts": {},
                          "_fingerprint": 0.0}   # newest corpus-dir mtime at last load

# the corpus dirs the cache watches for staleness (auto-refresh when disk is newer)
_CORPUS_DIRS = ("memory/research_packs", "memory/steal", "memory/rib")


def _fingerprint() -> float:
    """Newest mtime across the watched corpus dirs. Cheap (one scandir per dir, no full re-read).
    Used to auto-invalidate the cache: if disk is newer than the last load, the cache is stale."""
    best = 0.0
    for rel in _CORPUS_DIRS:
        d = ROOT / rel
        if not d.is_dir():
            continue
        try:
            for e in d.iterdir():
                if e.name.endswith(".md") and e.is_file():
                    try:
                        best = max(best, e.stat().st_mtime)
                    except Exception:
                        continue
        except Exception:
            continue
    return best


def _read_md_dir(d: Path, n: int = 200) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    if not d.is_dir():
        return out
    for p in sorted(d.glob("*.md"))[-n:]:
        try:
            txt = p.read_text(encoding="utf-8", errors="replace")
            out.append({"path": str(p.relative_to(ROOT)), "text": txt[:1200],
                        "title": txt.splitlines()[0][:120] if txt.splitlines() else p.stem})
        except Exception:
            continue
    return out


def load_corpus(*, refresh: bool = False) -> dict[str, Any]:
    """Load the corpus (research packs + steals + chain tail) into MEMORY once, cached. Returns the
    cache state. Deterministic + $0. The in-memory fast-path for lensing/novelty/processing."""
    if _CACHE["loaded"] and not refresh:
        # auto-invalidate: if the corpus dirs changed on disk since the last load, the cache is
        # stale -> reload so lensing/novelty/processing never read a frozen snapshot. Cheap check.
        if _fingerprint() <= _CACHE["_fingerprint"]:
            return {"ok": True, "schema": SCHEMA, "cached": True, **_CACHE["counts"]}
        refresh = True

    docs: list[dict[str, str]] = []
    docs += _read_md_dir(ROOT / "memory" / "research_packs", 200)
    docs += _read_md_dir(ROOT / "memory" / "steal", 200)
    docs += _read_md_dir(ROOT / "memory" / "rib", 100)

    text_parts: list[str] = []
    total = 0
    for d in docs:
        total += len(d["text"])
        if total > MAX_CORPUS_CHARS:
            break
        text_parts.append(d["text"])

    _CACHE.update({"loaded": True, "documents": docs,
                   "text": "\n\n".join(text_parts),
                   "counts": {"n_documents": len(docs), "n_chars": total},
                   "_fingerprint": _fingerprint()})
    return {"ok": True, "schema": SCHEMA, "cached": False, **_CACHE["counts"]}


def corpus() -> dict[str, Any]:
    """The in-memory corpus (loaded on first call, served from RAM after)."""
    load_corpus()
    return {"ok": True, "schema": SCHEMA, "documents": _CACHE["documents"],
            "text": _CACHE["text"], "counts": _CACHE["counts"]}


def corpus_text(max_chars: int | None = None) -> str:
    """The in-memory corpus as text (RAM-served; no disk I/O on repeated passes)."""
    load_corpus()
    t = _CACHE["text"]
    return t[:max_chars] if max_chars else t


def status() -> dict[str, Any]:
    load_corpus()
    return {"ok": True, "schema": SCHEMA, "cached_in_ram": _CACHE["loaded"],
            "counts": _CACHE["counts"],
            "note": "corpus held in RAM — lensing/novelty/processing read from memory, not disk"}


def main(argv: list[str] | None = None) -> int:
    import json as _json
    print(_json.dumps(status(), ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
