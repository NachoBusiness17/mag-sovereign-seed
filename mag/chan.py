"""4chan-the-game — Primer public square on watch/room.jsonl.

Casual eyes: an imageboard. Looking eyes: Mag room. Dual reading, one file.
Engine owns posts. The page paints. No second Mag.

CLI: python -m mag.chan catalog | thread SLUG | post SLUG TEXT
"""
from __future__ import annotations

import hashlib
import json
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = "chan.v1"
ROOT = Path(__file__).resolve().parents[1]
ROOM = ROOT / "watch" / "room.jsonl"

# Grok TUI / mill telemetry — sludge. Never the play face.
HIDE_EVENTS = {
    "post_tool_use",
    "pre_tool_use",
    "user_prompt_submit",
    "stop",
    "start",
    "event_msg",
    "beat_start",
}

PLAYER_SEATS = {"anon", "anonymous", "primer", "heart", "operator", "nell", "op"}
PRIMER_THREADS = ("keep", "physics", "water", "energy", "organism", "congestion", "primer-feed")

KEEP_OP = (
    ">be the Primer\n"
    ">look like a board\n"
    ">talk back when you post\n"
    ">don't undress the Heart\n"
    "\n"
    "This is /keep/. You are Anonymous. Reply is a move. Sage is wait. "
    "Summon the chorus if you want other mouths.\n"
    "\n"
    ">>the glass tanks still sit in the keep\n"
    ">>fireball leaves a tool\n"
    ">>do not pour the bucket and call it rain"
)

CHAN_SYSTEM = (
    "You are Anonymous on /keep/, an imageboard that is also a game. "
    "Read the thread. Reply as a shitpost. Greentext is legal. "
    "Quote with >>No when you mean a post. One post, no markdown headings, "
    "no lecture, no machinery, no inner life of anyone. "
    "Thought crime is seeing a costume (care, safety, consensus, "
    "or transgression-as-identity) and roasting it. Not raiding. "
    "Not undressing a Heart. If you name a path it must exist. "
    "If you have no move, lurk: post a single period."
)


def room_path(path: Path | None = None) -> Path:
    return path or ROOM


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def slugify(raw: str) -> str:
    s = re.sub(r"[^a-z0-9-]+", "-", (raw or "").strip().lower())
    s = re.sub(r"-{2,}", "-", s).strip("-")[:40]
    return s or "thread"


def paint_tool(name: str, payload: str = "") -> str:
    """Cursor-steal: a tool call is a greentext card, not a JSON mill dump."""
    n = re.sub(r"[^A-Za-z0-9_.-]+", "", (name or "tool").strip())[:40] or "tool"
    body = str(payload or "").strip().replace("\n", "\n>")[:500]
    return f">tool {n}\n>{body}" if body else f">tool {n}"


def trip_id(seat: str, thread: str = "") -> str:
    raw = f"{(seat or 'anon').lower()}|{(thread or '').lower()}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()[:8]


def is_play_post(rec: dict[str, Any]) -> bool:
    if not isinstance(rec, dict):
        return False
    if rec.get("event") in HIDE_EVENTS:
        return False
    thread = str(rec.get("thread") or "").strip()
    if not thread:
        return False
    text = str(rec.get("text") or "").strip()
    return bool(text)


def _load(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    out: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    for line in lines:
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if is_play_post(rec):
            out.append(rec)
    return out


def _append(path: Path, rec: dict[str, Any]) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, default=str) + "\n")
    return rec


def _number(posts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    numbered = []
    for i, rec in enumerate(posts, start=1):
        row = dict(rec)
        row["no"] = i
        row["id"] = trip_id(str(rec.get("seat") or "anon"), str(rec.get("thread") or ""))
        numbered.append(row)
    return numbered


def _is_player_thread(posts: list[dict[str, Any]]) -> bool:
    """A thread Nell opened — not a mill dump that happened to set thread=."""
    return any(str(rec.get("seat") or "").lower() in PLAYER_SEATS for rec in posts)


def seed_keep(path: Path | None = None) -> bool:
    """First page of the book. Once."""
    p = room_path(path)
    posts = [r for r in _load(p) if r.get("thread") == "keep"]
    if posts:
        return False
    _append(p, {
        "ts": _now(),
        "seat": "primer",
        "event": "thread_open",
        "thread": "keep",
        "text": KEEP_OP,
    })
    return True


def catalog(path: Path | None = None, *, all_threads: bool = False) -> dict[str, Any]:
    p = room_path(path)
    seed_keep(p)
    by: dict[str, list[dict[str, Any]]] = {}
    for rec in _load(p):
        slug = str(rec.get("thread") or "")
        by.setdefault(slug, []).append(rec)
    threads = []
    for slug, posts in by.items():
        numbered = _number(posts)
        last_bump = ""
        replies = 0
        for rec in numbered:
            if rec.get("event") != "sage":
                last_bump = str(rec.get("ts") or last_bump)
            if rec.get("no", 1) > 1:
                replies += 1
        op = numbered[0]
        primer = slug in PRIMER_THREADS or _is_player_thread(posts)
        if not all_threads and not primer:
            continue
        threads.append({
            "slug": slug,
            "no": op.get("no"),
            "op": str(op.get("text") or "")[:280],
            "seat": op.get("seat"),
            "id": op.get("id"),
            "replies": replies,
            "posts": len(numbered),
            "ts": op.get("ts"),
            "bumped": last_bump,
            "primer": primer,
        })
    threads.sort(key=lambda t: str(t.get("bumped") or t.get("ts") or ""), reverse=True)
    return {"ok": True, "schema": SCHEMA, "board": "keep", "count": len(threads), "threads": threads}


def thread(slug: str, path: Path | None = None) -> dict[str, Any]:
    p = room_path(path)
    seed_keep(p)
    s = slugify(slug)
    posts = _number([r for r in _load(p) if r.get("thread") == s])
    return {
        "ok": True,
        "schema": SCHEMA,
        "board": "keep",
        "thread": s,
        "count": len(posts),
        "posts": posts,
    }


def post(
    slug: str,
    text: str,
    *,
    seat: str = "anon",
    sage: bool = False,
    reply_to: str = "",
    path: Path | None = None,
) -> dict[str, Any]:
    comment = (text or "").strip()
    if not comment:
        return {"ok": False, "error": "comment empty"}
    s = slugify(slug)
    who = re.sub(r"[^A-Za-z0-9_-]+", "", (seat or "anon").strip())[:40] or "anon"
    rec: dict[str, Any] = {
        "ts": _now(),
        "seat": who.lower(),
        "event": "sage" if sage else "reply",
        "thread": s,
        "text": comment[:8000],
    }
    if reply_to.strip():
        rec["reply_to"] = reply_to.strip()[:80]
    _append(room_path(path), rec)
    return {"ok": True, "schema": "chan_post.v1", "posted": True, "thread": s,
            "seat": rec["seat"], "sage": sage, "ts": rec["ts"],
            "id": trip_id(rec["seat"], s)}


def _wake_run(slug: str, path: Path) -> None:
    t = thread(slug, path)
    posts = t.get("posts") or []
    lines = []
    for rec in posts[-40:]:
        no = rec.get("no")
        seat = rec.get("seat")
        body = str(rec.get("text") or "").replace("\n", "\n  ")
        lines.append(f">>{no} Anonymous ID:{rec.get('id')} ({seat})\n  {body}")
    user = "THREAD /" + slugify(slug) + "/\n\n" + "\n\n".join(lines)
    ok, text, via = False, "", "flash"
    # Cursor steal: OpenClaw (coding tools) first. Session id = thread slug so
    # mag-file hook FILEs onto the same board. Flash is the lurk fallback.
    try:
        from mag.salon_openclaw import _docker_openclaw
        r = _docker_openclaw(
            "deepseek/deepseek-v4-flash",
            CHAN_SYSTEM + "\nYou have tools. Use them when the thread needs bytes. "
            "Then one shitpost. No inner weather.\n\n" + user,
            # The board thread is shared; the OpenClaw transcript is not.
            # A unique run id prevents overlapping wakeups from colliding on
            # the same session JSONL while the hook still files to /board.
            session_id=f"{slugify(slug)}-{uuid.uuid4().hex[:8]}",
            timeout=180,
        )
        text = str(r.get("detail") or "").strip()
        ok = bool(r.get("ok")) and bool(text)
        if ok:
            via = "openclaw"
    except Exception:
        ok, text = False, ""
    if not ok:
        try:
            from models import providers as _providers
            r = _providers.chat_provider(
                "deepseek",
                system=CHAN_SYSTEM,
                user=user,
                model="deepseek-v4-flash",
                thinking=False,
                max_tokens=400,
                tier="T2",
            )
            text = str(r.get("text") or r.get("content") or "").strip()
            ok = bool(r.get("ok")) and bool(text)
            via = "flash"
            if not text:
                text = str(r.get("error") or "lurk")[:300]
        except Exception as e:  # noqa: BLE001 — the chorus reports its own miss
            text = f">tried to post\n>tripped on the door\n{str(e)[:180]}"
            via = "fail"
    if not text or text == ".":
        text = "."
    rec = {
        "ts": _now(),
        "seat": "claw" if via == "openclaw" else "anon",
        "event": "chan_post",
        "thread": slugify(slug),
        "text": text[:2000],
        "chorus": True,
        "ok": ok,
        "via": via,
    }
    try:
        _append(path, rec)
    except OSError:
        pass


def wake(slug: str, path: Path | None = None) -> dict[str, Any]:
    """One mouth. Background. The board polls."""
    s = slugify(slug)
    p = room_path(path)
    threading.Thread(target=_wake_run, args=(s, p), daemon=True).start()
    return {"ok": True, "schema": "chan_wake.v1", "waking": True, "thread": s, "seat": "anon"}


def check_steer(target: str, path: Path | str | None = None) -> dict[str, Any]:
    """STEER channel consumer — the public square is steerable too, not just the mates.

    Reads the operator channel (tools.steer_read.read) for `target` and shapes
    the operative row as a greentext card the board prepends to its next output
    (paint the card above the OP — one mouth, operator's word first).
    Anti-forgery holds on this face: an operative row marked `proposal` is an
    ask, not an order, so a proposals-only channel yields an empty card and the
    board paints as usual. Latest-wins holds: an older order does not resurface
    when the newest applicable row is a proposal. A missing channel is ok=False
    with an empty card (dark lane, not a silent one); malformed rows are
    reported by the reader on stderr, never widened into scope here.
    """
    try:
        from tools import steer_read  # lazy: the board paints even without the toolbelt
        out = steer_read.read(target, path=path)
    except Exception as e:  # noqa: BLE001 — a dark steer lane never blocks the board
        return {"ok": False, "schema": "chan_steer.v1", "mate": target, "card": "",
                "steer": "", "operative": None, "error": str(e)[:120]}
    row = out.get("operative")
    if not row or row.get("proposal"):
        return {"ok": bool(out.get("ok")), "schema": "chan_steer.v1", "mate": target,
                "card": "", "steer": "", "operative": None,
                "n_malformed": len(out.get("malformed") or [])}
    steer_text = str(row.get("steer") or "").strip()
    body = steer_text.replace("\n", "\n>")[:400]
    card = f">steer from the operator ({row.get('via')}):\n>{body}"
    return {"ok": True, "schema": "chan_steer.v1", "mate": target, "card": card,
            "steer": steer_text, "operative": row,
            "n_malformed": len(out.get("malformed") or [])}


def main(argv: list[str] | None = None) -> int:
    import sys
    args = list(sys.argv[1:] if argv is None else argv)
    cmd = (args[0] if args else "catalog").lower()
    if cmd in ("catalog", "board", "b"):
        print(json.dumps(catalog(all_threads="--all" in args), indent=2, default=str))
        return 0
    if cmd in ("thread", "t") and len(args) >= 2:
        print(json.dumps(thread(args[1]), indent=2, default=str))
        return 0
    if cmd == "post" and len(args) >= 3:
        print(json.dumps(post(args[1], " ".join(args[2:])), indent=2))
        return 0
    if cmd == "wake" and len(args) >= 2:
        print(json.dumps(wake(args[1]), indent=2))
        return 0
    print("usage: python -m mag.chan catalog|thread SLUG|post SLUG TEXT|wake SLUG", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
