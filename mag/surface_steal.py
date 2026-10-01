"""surface_steal — on every ask, surface lingering threads from our OWN corpus.

The operator's directive (2026-08-10): "every time i ask you a question you do a self steal
automatically — if there are lingering thoughts or directions from our corpus you can surface them."

Distinct from self_steal (which is the maintenance audit of under-utilized capabilities). THIS module
is the conversational behavior: before/alongside answering, consult the Republic's own memory for what
we ALREADY know and what's still LINGERING about the ask — so ghost never answers as a stranger, and
every reply is grounded + aware of adjacent threads. Deterministic, $0, no LLM.

  surface(question, limit)   -> related graph nodes + matching steal docs + lingering directions.
  lingering()                -> recent steal-doc titles (potential threads not yet folded).

Schema: surface_steal.v1 · deterministic · $0
CLI:  python -m mag.surface_steal "<question>"
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
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCHEMA = "surface_steal.v1"
STEAL_DIR = ROOT / "memory" / "steal"


def _words(text: str) -> set[str]:
    return set(w.lower() for w in re.findall(r"[A-Za-z0-9_]{4,}", text or ""))


def related_nodes(question: str, limit: int = 5) -> list[dict[str, Any]]:
    """The source-backed knowledge-graph nodes we already hold about this ask."""
    try:
        from mag.knowledge_graph import known
        k = known(question)
        return [
            {"label": n.get("label"), "kind": n.get("kind"),
             "body": (n.get("purpose") or n.get("summary") or "")[:140]}
            for n in (k.get("known") or [])[:limit]
        ]
    except Exception as e:
        return [{"error": str(e)[:120]}]


def steal_docs(question: str, limit: int = 4) -> list[dict[str, Any]]:
    """Match our memory/steal docs against the ask -> lingering directions already mined."""
    qw = _words(question)
    hits = []
    if STEAL_DIR.is_dir():
        for p in sorted(STEAL_DIR.glob("*.md")):
            try:
                head = p.read_text(encoding="utf-8", errors="replace")[:300].lower()
            except Exception:
                head = ""
            name = p.stem.lower()
            matched = sorted(qw & (set(re.findall(r"[a-z0-9_]{4,}", name)) | set(re.findall(r"[a-z0-9_]{4,}", head))))
            if matched:
                hits.append({"doc": p.stem, "matched": matched[:6]})
    return hits[:limit]


def lingering(limit: int = 6) -> list[str]:
    """The most recent steal docs — potential threads not yet fully folded."""
    if not STEAL_DIR.is_dir():
        return []
    docs = sorted(STEAL_DIR.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    return [p.stem for p in docs[:limit]]


def surface(question: str, limit: int = 5) -> dict[str, Any]:
    """The self-steal: what we already know + what's lingering about this ask."""
    result = {
        "ok": True, "schema": SCHEMA, "ask": question,
        "already_known": related_nodes(question, limit),
        "matched_steals": steal_docs(question, limit),
        "lingering_directions": lingering(limit),
    }
    # The surface is invoked conversationally and previously left no durable
    # receipt, which made self_steal report a live path as stale.  Record only
    # bounded metadata and a question fingerprint; never copy the ask into the
    # maintenance ledger.
    try:
        STEAL_DIR.mkdir(parents=True, exist_ok=True)
        receipt = {
            "schema": "surface_steal.receipt.v1",
            "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "ask_sha256": hashlib.sha256((question or "").encode("utf-8")).hexdigest()[:16],
            "limit": int(limit),
            "known_n": len(result["already_known"]),
            "matched_n": len(result["matched_steals"]),
            "lingering_n": len(result["lingering_directions"]),
        }
        with (STEAL_DIR / "surface_receipts.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(receipt, ensure_ascii=False) + "\n")
    except OSError:
        pass
    return result


def main(argv: list[str] | None = None) -> int:
    import argparse, json
    p = argparse.ArgumentParser(prog="surface_steal", description="surface lingering threads on any ask")
    p.add_argument("question", nargs="*", default=[""])
    p.add_argument("--limit", type=int, default=5)
    a = p.parse_args(argv)
    q = " ".join(a.question).strip() or "the republic, the epic, the ghost server"
    print(json.dumps(surface(q, a.limit), indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
