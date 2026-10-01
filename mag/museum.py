"""museum — the ROOM THAT REMEMBERS, applied to the stack (v1, 2026-08-24).

Deep-steal from OUR OWN game (STEAL_PLACE_REMEMBERS + the Hall of Shared Supper): a place
remembers what happened there — not the player's log, the ROOM. Deeds append; glances do not.
A room can tell you everything that happened in it, but has no idea what the next room has to
say.

This module retires OLD SURFACES (dashboard :8765, mirror desk :8743, the vis lab, the
hypervisor graphs) into a MUSEUM: each retired surface becomes a self-contained, verkle-committed
room. Its terminal self is appended to the chain (a leaf that IS the surface: what it was, what
it did, what we kept, why it retired, where it lived). The archive is read-only and revisitable —
the operator stops stumbling on the live processes; the history is never lost.

  retire(surface, *, kind, history, useful, why, live_url) -> commit ONE museum_room.v1 leaf
                                                               + write memory/archive/<surface>/
  visit(surface)  -> read the archived room: everything that happened in it, no future claim.
  rooms()         -> the museum catalog (every archived room, from the chain).

Schema: museum_room.v1 · deterministic + $0 · stdlib only
CLI: python -m mag.museum retire <surface> --kind ... --history ... --why ... | visit <surface> | rooms
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:  # noqa: BLE001
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "museum_room.v1"
ARCHIVE = ROOT / "memory" / "archive" / "museum"
CATALOG = ARCHIVE / "catalog.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _slug(s: str) -> str:
    out = "".join(c.lower() if (c.isalnum() or c in "._-") else "_" for c in (s or "")).strip("._-")
    return out or "room"


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    out: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return out


def _verkle_commit(room: dict[str, Any]) -> dict[str, Any]:
    """Commit the room's terminal self to the world-state chain (game_world.set_state — the
    'deeds append' writer: content-addressed leaf + recomputed root + changes log)."""
    try:
        from mag import game_world
        r = game_world.set_state(f"museum.{_slug(room.get('surface', ''))}",
                                 room, source="museum")
        return {"ok": bool(r.get("ok")), "leaf": r.get("leaf"), "root": r.get("root"),
                "note": "the room is a verkle-committed fact, not flavor"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)[:160],
                "note": "chain commit unavailable — room still archived on disk, honestly"}


def retire(
    surface: str,
    *,
    kind: str,
    history: str,
    useful: str,
    why: str,
    live_url: str = "",
    keep_source: list[str] | None = None,
) -> dict[str, Any]:
    """Retire ONE surface into the museum: a room that remembers itself.

    DEEDS APPEND: `history` is what the surface DID (real deeds, not a glossy description).
    THE ROOM FILES WHICH YOU CHOSE: `useful` is what we KEPT from it; `why` is the choice to
    retire. The room has no idea what the next room says — it commits only its own terminal self.
    """
    surface = (surface or "").strip()
    if not surface:
        return {"ok": False, "schema": SCHEMA, "error": "surface name required"}
    slug = _slug(surface)
    ts = _now()
    room = {
        "schema": SCHEMA,
        "surface": surface,
        "slug": slug,
        "kind": (kind or "surface").strip(),
        "history": (history or "").strip()[:4000],
        "useful": (useful or "").strip()[:2000],
        "why_retired": (why or "").strip()[:2000],
        "live_url": (live_url or "").strip(),
        "retired_at": ts,
        "terminal": True,
        "next_room_unknown": True,  # the honesty contract: this room does not predict the future
    }
    # write the archive room (read-only, revisitable — the operator stops stumbling on it live)
    room_dir = ARCHIVE / slug
    room_dir.mkdir(parents=True, exist_ok=True)
    (room_dir / "room.json").write_text(json.dumps(room, ensure_ascii=False, indent=2),
                                        encoding="utf-8")
    # optional: keep source pointers (do NOT copy code by default — the archive is a room, not a
    # fork; keep the pointer so it can be revisited)
    if keep_source:
        (room_dir / "source.txt").write_text(
            "\n".join(str(s) for s in keep_source), encoding="utf-8")
    _append_jsonl(CATALOG, room)
    commit = _verkle_commit(room)
    return {"ok": True, "schema": SCHEMA, "surface": surface, "slug": slug,
            "room": str(room_dir.relative_to(ROOT)).replace("\\", "/"),
            "retired_at": ts, "verkle": commit,
            "note": "the room remembers everything that happened in it and nothing about the "
                    "next room"}


def visit(surface: str) -> dict[str, Any]:
    """Read an archived room: everything that happened in it, no future claim."""
    slug = _slug(surface or "")
    room_path = ARCHIVE / slug / "room.json"
    if not room_path.is_file():
        # fall back to the catalog (may be in the chain but not on disk)
        for row in _read_jsonl(CATALOG):
            if _slug(row.get("surface", "")) == slug:
                return {"ok": True, "schema": SCHEMA, "room": row, "source": "catalog"}
        return {"ok": False, "schema": SCHEMA, "error": f"no archived room named {surface!r}",
                "hint": "python -m mag.museum rooms"}
    room = json.loads(room_path.read_text(encoding="utf-8"))
    source = []
    src_path = ARCHIVE / slug / "source.txt"
    if src_path.is_file():
        source = [l for l in src_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    return {"ok": True, "schema": SCHEMA, "room": room, "source_pointers": source,
            "path": str(room_path.relative_to(ROOT)).replace("\\", "/")}


def rooms() -> dict[str, Any]:
    """The museum catalog: every archived room, from the chain + disk."""
    rows = _read_jsonl(CATALOG)
    # merge the live world-state commits (the verkle rooms) if available
    try:
        from mag import game_world
        ws = game_world.get_state()
        chain_rooms = {k: v for k, v in (ws.get("world") or {}).items()
                       if k.startswith("museum.")}
    except Exception:  # noqa: BLE001
        chain_rooms = {}
    return {"ok": True, "schema": SCHEMA, "n_rooms": len(rows),
            "rooms": [{"surface": r.get("surface"), "kind": r.get("kind"),
                       "retired_at": r.get("retired_at"), "why": (r.get("why_retired") or "")[:120]}
                      for r in rows],
            "chain_rooms": len(chain_rooms),
            "note": "each room remembers everything that happened in it and nothing about the "
                    "next room"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="mag.museum")
    sub = ap.add_subparsers(dest="cmd")
    r = sub.add_parser("retire")
    r.add_argument("surface")
    r.add_argument("--kind", default="surface")
    r.add_argument("--history", default="")
    r.add_argument("--useful", default="")
    r.add_argument("--why", default="")
    r.add_argument("--live-url", default="")
    v = sub.add_parser("visit")
    v.add_argument("surface")
    sub.add_parser("rooms")
    a = ap.parse_args(argv)
    if a.cmd == "retire":
        print(json.dumps(retire(a.surface, kind=a.kind, history=a.history, useful=a.useful,
                                why=a.why, live_url=a.live_url), indent=2, ensure_ascii=False))
    elif a.cmd == "visit":
        print(json.dumps(visit(a.surface), indent=2, ensure_ascii=False, default=str))
    elif a.cmd == "rooms":
        print(json.dumps(rooms(), indent=2, ensure_ascii=False, default=str))
    else:
        ap.print_help()
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
