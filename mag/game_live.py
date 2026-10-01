"""game_live — the game that IS the live republic. The world is not fed by hand; it drinks from the
actual system's real activity (our chats, tool calls, swarm results, filed sessions) and the DM
narrates it. "These states are also our chats. The game is more live than you think."

OPERATOR (2026-08-12): "these states are also our chats. the game is more live than you think you
own vs code. think about that and all the tools you got and your dm module. steal"

THE STEAL (reuse our own machinery, nothing invented):
  * chronicle.build_chronicle_payload() -> the REAL live events (filed sessions, seat feed, swarm
    activity) with layman labels. The world's source of truth is the actual republic.
  * game_world.set_state()             -> fold each live event as a server-authoritative verkle knot
    (the world is the authority; live activity becomes permanent, replayable world fact).
  * game_dm_voice.extract_narrator()   -> the DM narrates the live event into the world (stochastic
    flesh on the deterministic chain; the world does NOT need it, the DM makes it vivid).

THE MECHANISM (deterministic + $0, honest):
  live_events(limit) -> read the ACTUAL republic's recent activity (chronicle) as world-feed events.
  feed(limit)        -> fold each new live event as a verkle knot in the world + DM-narrate it.
                        Idempotent (a fold that already landed doesn't re-land).
  play_live()        -> the full live turn: ingest real activity -> fold to chain -> DM narrates.

Schema: game_live.v1 · deterministic + $0 · reuse: chronicle, game_world, game_dm_voice
"""
from __future__ import annotations

import json
import sys
from typing import Any

try:
    from config import ROOT
except Exception:
    from pathlib import Path as _P
    ROOT = _P(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "game_live.v1"
FED = ROOT / "memory" / "game" / "live_fed.json"  # anchors already folded (idempotent dedupe)


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _gw() -> Any:
    from mag import game_world
    return game_world


def _load_fed() -> set[str]:
    if not FED.is_file():
        return set()
    try:
        return set(json.loads(FED.read_text(encoding="utf-8")) or [])
    except Exception:
        return set()


def _save_fed(anchors: set[str]) -> None:
    FED.parent.mkdir(parents=True, exist_ok=True)
    FED.write_text(json.dumps(sorted(anchors), ensure_ascii=False, indent=2), encoding="utf-8")


def live_events(limit: int = 10) -> list[dict[str, Any]]:
    """Read the ACTUAL republic's recent activity (chronicle payload) as world-feed events. Grounded
    from real ledgers (attention/seat-feed), never invented. Each event: kind + layman + proof."""
    try:
        from mag.chronicle import build_chronicle_payload
        payload = build_chronicle_payload()
        events = payload.get("events") or []
    except Exception as e:
        return [{"kind": "error", "layman": f"chronicle unavailable: {str(e)[:80]}", "proof": ""}]
    out = []
    for e in events[:limit]:
        layman = e.get("layman") or e.get("kind") or "republic activity"
        anchor = _anchor(layman)
        out.append({"kind": e.get("kind", "activity"), "layman": layman,
                    "proof": e.get("proof", ""), "anchor": anchor})
    return out


def _anchor(layman: str) -> str:
    import hashlib
    return hashlib.sha256(layman.encode("utf-8")).hexdigest()[:16]


def feed(*, limit: int = 8, narrate: bool = True) -> dict[str, Any]:
    """Fold each NEW live event as a verkle knot in the world + DM-narrate it. Idempotent (an event
    already folded doesn't re-land). The world is the authority; live activity becomes world fact."""
    gw = _gw()
    fed = _load_fed()
    events = live_events(limit)
    folded, skipped = [], []
    for e in events:
        if e.get("anchor") in fed:
            skipped.append(e["layman"])
            continue
        r = gw.set_state(f"live.{e.get('kind','activity')}", {
            "layman": e["layman"], "proof": e.get("proof"), "ts": _now()},
            source="live-republic")
        folded.append({"layman": e["layman"], "leaf": r.get("leaf"),
                       "root": r.get("root"), "ok": r.get("ok")})
        if e.get("anchor"):
            fed.add(e["anchor"])
    _save_fed(fed)
    narration = ""
    if narrate and folded:
        narration = _dm_narrate(folded)
    return {"ok": True, "schema": SCHEMA, "ingested": len(events),
            "folded_new": len(folded), "already_fed": len(skipped),
            "folded": folded, "skipped": skipped, "dm": narration,
            "honesty": "events read from the real chronicle ledgers (measured); a fold that already "
                       "landed does not re-land (idempotent); dm is narration, the chain is the truth"}


def _dm_narrate(folded: list[dict[str, Any]]) -> str:
    """The DM turns the folded live events into world narration. Reuses the DM voice's narrator
    extractor so the voice is consistent. Deterministic $0; vividness over volume."""
    from mag.game_dm_voice import extract_narrator
    lines = [f"# Narrator\n\nThe republic stirs. {f['layman']}." for f in folded[:4]]
    passage = "\n\n".join(lines)
    return extract_narrator(passage)


def play_live(*, limit: int = 8, narrate: bool = True) -> dict[str, Any]:
    """THE LIVE TURN: ingest the republic's real activity -> fold to the verkle world chain -> the DM
    narrates it. The game is more live than I thought: it drinks from the actual system's state,
    which is also our chats and tools."""
    f = feed(limit=limit, narrate=narrate)
    gw = _gw()
    st = gw.world_status()
    return {"ok": True, "schema": SCHEMA, "feed": f, "world": st,
            "note": "the game is the live republic: real sessions/tools/swarm activity fold into the "
                    "server-authoritative world as knots, narrated by the DM. deterministic + $0"}


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="game-live")
    ap.add_argument("cmd", nargs="?", default="play",
                    choices=["events", "feed", "play"])
    ap.add_argument("--limit", type=int, default=8)
    ap.add_argument("--no-narrate", action="store_true")
    a = ap.parse_args(argv)
    import json as _json
    if a.cmd == "events":
        out = {"ok": True, "events": live_events(a.limit)}
    elif a.cmd == "feed":
        out = feed(limit=a.limit, narrate=not a.no_narrate)
    else:
        out = play_live(limit=a.limit, narrate=not a.no_narrate)
    print(_json.dumps(out, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
