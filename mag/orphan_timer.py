"""Orphan timer for idea generation — capture undone-yet-intended work so it's never lost.

Problem: the operator raises intent in one window (e.g. "restart dashboard to load a
route", "apply the janitor", "reload window"), then works in OTHER windows and forgets.
The ghost should recognize that intent as "undone yet intended" and keep it alive.

This module tracks OPEN intents and, after a threshold, promotes stale ones into the
idea graph as `open_loop` nodes (and the queue, optionally) so they survive across
windows and can be auto-delegated by the drainer. It is the "orphan timer for idea
generation".

Store: memory/ideas/orphans.jsonl        (schema: orphan.v1)
  {id, intent, source, first_seen, last_touch, status: open|promoted|resolved,
   promoted_at, idea_node_id}

API:
  note_intent(intent, source="operator", id=None)  -> record an open intent (dedup by id/intent)
  touch_intent(id)                                  -> reset the timer (being worked)
  resolve_intent(id)                                -> close when done
  run(threshold_s=...)                              -> promote stale open -> idea graph open_loop
  list_open()                                       -> open orphans

CLI:
  python -m mag.orphan_timer note "restart dashboard" --source system
  python -m mag.orphan_timer run --threshold 3600
  python -m mag.orphan_timer list
  python -m mag.orphan_timer resolve <id>

REST:
  POST /api/v1/orphan  {action: note|touch|resolve|run, intent, id, source, threshold}
  GET  /api/v1/orphan  -> {open: [...], promoted_total}
"""
from __future__ import annotations

import json
import sys
import time
import uuid
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

ORPHANS_PATH = ROOT / "memory" / "ideas" / "orphans.jsonl"
DEFAULT_THRESHOLD_S = 3600  # 1h


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _now_epoch() -> float:
    return time.time()


def _read() -> list[dict[str, Any]]:
    if not ORPHANS_PATH.is_file():
        return []
    out: list[dict[str, Any]] = []
    for line in ORPHANS_PATH.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            o = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(o, dict):
            out.append(o)
    return out


def _write(rows: list[dict[str, Any]]) -> None:
    ORPHANS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = ORPHANS_PATH.with_suffix(".tmp")
    body = "\n".join(json.dumps(r, ensure_ascii=False, default=str) for r in rows)
    if body:
        body += "\n"
    tmp.write_text(body, encoding="utf-8")
    tmp.replace(ORPHANS_PATH)


def note_intent(intent: str, *, source: str = "operator", id: str | None = None) -> dict[str, Any]:
    intent = (intent or "").strip()
    if not intent:
        return {"ok": False, "error": "empty intent"}
    rows = _read()
    # Dedup by explicit id or normalized intent text.
    norm = intent.lower()
    for o in rows:
        if o.get("status") == "open" and (
            (id and o.get("id") == id)
            or (o.get("intent", "").lower() == norm)
        ):
            o["last_touch"] = _now()
            _write(rows)
            return {"ok": True, "id": o["id"], "status": "already_open", "intent": intent}
    oid = id or f"orphan_{uuid.uuid4().hex[:10]}"
    row = {
        "schema": "orphan.v1",
        "id": oid,
        "intent": intent[:400],
        "source": source,
        "first_seen": _now(),
        "last_touch": _now(),
        "first_seen_epoch": _now_epoch(),
        "status": "open",
        "promoted_at": None,
        "idea_node_id": None,
    }
    rows.append(row)
    _write(rows)
    return {"ok": True, "id": oid, "status": "open", "intent": intent}


def touch_intent(id: str) -> dict[str, Any]:
    rows = _read()
    for o in rows:
        if o.get("id") == id:
            o["last_touch"] = _now()
            _write(rows)
            return {"ok": True, "id": id, "status": o.get("status")}
    return {"ok": False, "error": f"not found: {id}"}


def resolve_intent(id: str) -> dict[str, Any]:
    rows = _read()
    for o in rows:
        if o.get("id") == id:
            o["status"] = "resolved"
            o["resolved_at"] = _now()
            _write(rows)
            return {"ok": True, "id": id, "status": "resolved"}
    return {"ok": False, "error": f"not found: {id}"}


def list_open() -> list[dict[str, Any]]:
    return [o for o in _read() if o.get("status") == "open"]


def run(*, threshold_s: int = DEFAULT_THRESHOLD_S, dry: bool = False) -> dict[str, Any]:
    """Promote stale open intents into the idea graph as open_loop nodes."""
    now = _now_epoch()
    rows = _read()
    promoted: list[dict[str, Any]] = []
    changed = False
    for o in rows:
        if o.get("status") != "open":
            continue
        first = o.get("first_seen_epoch") or now
        age = now - float(first)
        if age < threshold_s:
            continue
        if dry:
            promoted.append({"id": o["id"], "intent": o["intent"][:80], "age_s": int(age)})
            continue
        node_id = None
        try:
            from mag.idea_graph import add_node, link
            n = add_node(
                title=f"[orphan] {o['intent'][:200]}",
                ntype="open_loop",
                status="open",
                body=f"Undone-yet-intended (source={o.get('source')}, opened {o.get('first_seen')}). "
                     f"Left open past {threshold_s}s. Orphan id: {o.get('id')}.",
                tags=["orphan", o.get("source", "operator")],
                source="ghost-orphan",
            )
            node_id = n.get("id")
            try:
                link("n_spine_workspace", node_id, etype="related", note="orphan intent")
            except Exception:
                pass
        except Exception:
            node_id = None
        o["status"] = "promoted"
        o["promoted_at"] = _now()
        o["idea_node_id"] = node_id
        promoted.append({
            "id": o["id"], "intent": o["intent"][:80], "age_s": int(age),
            "idea_node_id": node_id,
        })
        # Feed the doctor: catalogue the orphan as a learnable observation so it
        # surfaces in recurring_patterns if the same intent keeps going undone.
        if not dry:
            try:
                from mag.failure_kb import log_failure
                log_failure(
                    kind="orphan",
                    detail=f"Undone-yet-intended: {o['intent'][:240]}",
                    tool="orphan_timer",
                    phase="cadence",
                )
            except Exception:
                pass
        changed = True
    if changed:
        _write(rows)
    return {
        "ok": True,
        "schema": "orphan_run.v1",
        "ts": _now(),
        "threshold_s": threshold_s,
        "dry": dry,
        "promoted": promoted,
        "n_promoted": len(promoted),
        "open_remaining": sum(1 for o in rows if o.get("status") == "open"),
    }


# ====================================================================
# CLI
# ====================================================================
def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="orphan_timer", description="orphan timer for idea generation")
    sub = ap.add_subparsers(dest="cmd")

    p_note = sub.add_parser("note", help="Record an open intent")
    p_note.add_argument("intent", nargs="+")
    p_note.add_argument("--source", default="operator")

    p_run = sub.add_parser("run", help="Promote stale open intents -> idea graph")
    p_run.add_argument("--threshold", type=int, default=DEFAULT_THRESHOLD_S)
    p_run.add_argument("--dry", action="store_true")

    p_list = sub.add_parser("list", help="List open orphans")
    p_resolve = sub.add_parser("resolve", help="Resolve an orphan")
    p_resolve.add_argument("id")

    args = ap.parse_args(argv)

    if args.cmd == "note":
        r = note_intent(" ".join(args.intent), source=args.source)
        print(json.dumps(r, indent=2, ensure_ascii=False, default=str))
        return 0
    if args.cmd == "run":
        r = run(threshold_s=args.threshold, dry=args.dry)
        print(json.dumps(r, indent=2, ensure_ascii=False, default=str))
        return 0
    if args.cmd == "list":
        rows = list_open()
        print(f"{len(rows)} open orphans")
        for o in rows:
            print(f"  {o.get('id')}  [{o.get('source')}]  {o.get('intent')[:80]}")
        return 0
    if args.cmd == "resolve":
        r = resolve_intent(args.id)
        print(json.dumps(r, indent=2, ensure_ascii=False, default=str))
        return 0
    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
