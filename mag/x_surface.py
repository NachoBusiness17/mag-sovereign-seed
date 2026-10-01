"""x_surface — X (Twitter) as a free data + drafting surface, gated by an OPERATOR REVIEW QUEUE.

Operator (2026-08-10): "give you access to your x account so you can post and browse x for free
data to steal using our system at full blast yet lowest cost ... read only and queue responses and
original posts so i can see what you wrote so i can make sure its not fucked."

DESIGN (safe by construction):
  * READ-ONLY HARVEST (autonomous): browse X via the ghost container browser and harvest text into
    the corpus (corpus_expand.ingest) — free data for self-improvement, $0 frontier spend.
  * DRAFT QUEUE (operator-gated): the system DRAFTS replies + original posts into a REVIEW QUEUE.
    NOTHING posts without the operator approving. `approve(id)` is the only publish path (requires
    the operator to have logged into X in the ghost browser).
  * The queue is the control surface: every draft is visible for review before it could ever go live.

SCHEMA: x_surface.v1 · CLI: python -m mag.x_surface harvest "<query>" | draft "<text>" [--kind reply|post] | queue | approve <id>
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

SCHEMA = "x_surface.v1"
DRAFTS = ROOT / "memory" / "runs" / "x_surface" / "drafts.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_drafts() -> list[dict[str, Any]]:
    if DRAFTS.is_file():
        try:
            return json.loads(DRAFTS.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def _save_drafts(drafts: list[dict[str, Any]]) -> None:
    DRAFTS.parent.mkdir(parents=True, exist_ok=True)
    DRAFTS.write_text(json.dumps(drafts, ensure_ascii=False, indent=2), encoding="utf-8")


def harvest(query: str) -> dict[str, Any]:
    """READ-ONLY harvest: browse X via the ghost container browser, extract text, ingest to corpus.

    This is the free-data steal — X trends/threads become corpus material for self-improvement at
    $0 frontier cost. Requires the ghost browser up + operator logged into X in it."""
    from mag import browser_driver as bd
    r = bd.ask(query, surface="x", max_wait_s=90)
    if not r.get("ok"):
        return {"ok": False, "schema": SCHEMA, "error": r.get("error"),
                "hint": "X must be logged in inside the ghost browser + browser container up"}
    text = str(r.get("answer") or "")
    ingested = 0
    try:
        from mag import corpus_expand as ce
        ing = ce.ingest(text, "x_surface_harvest")
        ingested = 1 if ing.get("ok") else 0
    except Exception:
        pass
    return {"ok": True, "schema": SCHEMA, "mode": "read_only", "query": query[:80],
            "harvested_chars": len(text), "ingested": ingested}


def draft(text: str, *, kind: str = "reply") -> dict[str, Any]:
    """DRAFT a reply or original post into the REVIEW QUEUE (operator-gated — NOT posted)."""
    if not (text or "").strip():
        return {"ok": False, "schema": SCHEMA, "error": "empty draft"}
    kind = kind if kind in ("reply", "post") else "reply"
    drafts = _load_drafts()
    d = {"id": "x-" + uuid.uuid4().hex[:8], "kind": kind, "text": text.strip(),
         "status": "pending_review", "created_at": _now()}
    drafts.append(d)
    _save_drafts(drafts)
    return {"ok": True, "schema": SCHEMA, "mode": "queued_for_review",
            "draft": d, "n_pending": sum(1 for x in drafts if x.get("status") == "pending_review"),
            "note": "queued — operator reviews before anything could go live"}


def queue() -> dict[str, Any]:
    """The REVIEW QUEUE: every draft awaiting the operator's eyes."""
    drafts = _load_drafts()
    pending = [d for d in drafts if d.get("status") == "pending_review"]
    return {"ok": True, "schema": SCHEMA, "n_pending": len(pending), "drafts": pending}


def approve(draft_id: str) -> dict[str, Any]:
    """The ONLY publish path: operator approves a queued draft, then it posts (needs X login).

    This is gated — the operator explicitly approves; the system does not auto-post."""
    drafts = _load_drafts()
    for d in drafts:
        if d.get("id") == draft_id and d.get("status") == "pending_review":
            d["status"] = "approved"
            _save_drafts(drafts)
            # actual posting is browser-driven (needs X login) — mark ready, not auto-fired
            return {"ok": True, "schema": SCHEMA, "approved": d["id"],
                    "note": "approved — post now requires a browser-publish step (X login present)"}
    return {"ok": False, "schema": SCHEMA, "error": f"no pending draft {draft_id}"}


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="x-surface")
    ap.add_argument("cmd", nargs="?", default="queue", choices=["harvest", "draft", "queue", "approve"])
    ap.add_argument("arg", nargs="*", default=[])
    ap.add_argument("--kind", default="reply")
    args = ap.parse_args(argv)
    body = " ".join(args.arg)
    if args.cmd == "harvest":
        print(json.dumps(harvest(body), indent=2))
    elif args.cmd == "draft":
        print(json.dumps(draft(body, kind=args.kind), indent=2))
    elif args.cmd == "approve":
        print(json.dumps(approve(body), indent=2))
    else:
        print(json.dumps(queue(), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
