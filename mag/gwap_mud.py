"""gwap_mud -- MUD scene adapter for the GWAP agreement engine (v1, rung B3).

The connector that lets mud.html sessions feed the agreement engine WITHOUT
touching mud.html itself (v0 receipt debt 6): the game already beats presence
heartbeats at the relay (dashboard/mud_relay.py), so this module reads the two
shapes that exist TODAY and turns each into the claim-triple struct
{author, claims} that mag/gwap_payload.py already scores.

EVENT SHAPE (one mud.html-style scene event, what the game loop knows):
  {"player": {"id": str, "x": number, "y": number},
   "action": "move" | "attack" | "kill",
   "target": str (required for attack/kill, ignored for move)}
  Verbs: move -> "moved" + tile object, attack -> "attacked" + target id,
  kill -> "killed" + target id. Positions quantize to integer tiles (Python
  round, half-even) so the same world state always produces the same triple
  bytes. Unknown actions fail closed (MUD_EVENT): the adapter never invents
  verbs.

REPLAY SHAPE (one relay presence line, a POST /mud/seen body or a /mud/ws
text frame): {id, name, x, y, hp, max_hp, state} exactly as
dashboard/mud_relay.py _register_seen normalizes it (state is the mud.html
G.state: title/play/dead/victory; the spectator view /mud/state may add an
"age" key, which is tolerated and dropped). A single line is only a
snapshot: claims come from DELTAS against the same player's previous
snapshot -- tile movement (moved), hp drop (lost hp, qualifier carries the
amount), death and victory state transitions, emitted in that fixed order.
Presence is authority-free BY DESIGN (relay docstring): an hp drop names the
loser, never the attacker, so replay claims never say "attacked"; attacker
attribution needs richer frames and stays inside the semantic-layer debt
(v0 receipt debt 5). First sighting of a player yields no claim: there is
nothing to diff against.

Both struct builders return {author, claims} ready for build_payload(); the
demo (python -m mag.gwap_mud) runs one full round end to end: events ->
intent, replay -> report, build_payload, sign, ledger append, chain verify.

LAWS: no RNG, no clock reads, no network. from_replay_line is pure: the
caller threads the returned snapshot in as the next prev. Dicts over
dataclasses. canonical() stays the only serialization, owned by gwap_payload.
"""

from __future__ import annotations

import json
from typing import Any, Iterable

from mag.gwap_payload import GwapError

EVENT_VERBS = {"move": "moved", "attack": "attacked", "kill": "killed"}
PRESENCE_KEYS = ("id", "name", "x", "y", "hp", "max_hp", "state")


def _pid(value: Any, field: str, reason: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise GwapError(reason, f"{field} must be a non-empty string")
    return value.strip()


def _num(value: Any, field: str, reason: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise GwapError(reason, f"{field} must be a number")
    return float(value)


def _tile(value: Any, field: str, reason: str) -> int:
    return int(round(_num(value, field, reason)))


def _tile_object(x: Any, y: Any, reason: str) -> str:
    return f"tile {_tile(x, 'x', reason)} {_tile(y, 'y', reason)}"


# -- mud.html-style events ------------------------------------------------------------


def claim_from_event(event: Any) -> dict[str, str]:
    """One scene event -> one claim triple. The mapping is closed and
    deterministic: {move, attack, kill} in, {moved, attacked, killed} out."""
    if not isinstance(event, dict):
        raise GwapError("MUD_EVENT", "event must be a dict")
    action = event.get("action")
    if action not in EVENT_VERBS:
        raise GwapError(
            "MUD_EVENT",
            f"action must be one of {sorted(EVENT_VERBS)}, got {action!r}",
        )
    player = event.get("player")
    if not isinstance(player, dict):
        raise GwapError("MUD_EVENT", "event.player must be a dict")
    subject = _pid(player.get("id"), "player.id", "MUD_EVENT")
    if action == "move":
        return {
            "subject": subject,
            "verb": "moved",
            "object": _tile_object(player.get("x"), player.get("y"), "MUD_EVENT"),
            "qualifier": "",
        }
    target = _pid(event.get("target"), "target", "MUD_EVENT")
    return {
        "subject": subject,
        "verb": EVENT_VERBS[action],
        "object": target,
        "qualifier": "",
    }


def struct_from_events(author: Any, events: Iterable[Any]) -> dict[str, Any]:
    """Events -> {author, claims} ready for build_payload(intent_struct=...)."""
    if not isinstance(author, str) or not author.strip():
        raise GwapError("MUD_EVENT", "author must be a non-empty string")
    return {
        "author": author.strip(),
        "claims": [claim_from_event(e) for e in events],
    }


# -- relay replay lines ----------------------------------------------------------------


def _presence(row: Any) -> dict[str, Any]:
    """Validate + normalize one presence snapshot to exactly PRESENCE_KEYS
    (floats for the numerics). Accepts a dict or a JSON string line. Extra
    keys (the /mud/state spectator 'age') are tolerated and dropped."""
    if isinstance(row, str):
        try:
            row = json.loads(row)
        except ValueError:
            raise GwapError("MUD_REPLAY", "line is not valid JSON") from None
    if not isinstance(row, dict) or not set(row) >= set(PRESENCE_KEYS):
        raise GwapError(
            "MUD_REPLAY",
            "presence must carry at least "
            "{id, name, x, y, hp, max_hp, state}",
        )
    return {
        "id": _pid(row["id"], "id", "MUD_REPLAY"),
        "name": row["name"] if isinstance(row["name"], str) else "",
        "x": _num(row["x"], "x", "MUD_REPLAY"),
        "y": _num(row["y"], "y", "MUD_REPLAY"),
        "hp": _num(row["hp"], "hp", "MUD_REPLAY"),
        "max_hp": _num(row["max_hp"], "max_hp", "MUD_REPLAY"),
        "state": _pid(row["state"], "state", "MUD_REPLAY"),
    }


def from_replay_line(
    line: Any, prev: dict[str, Any] | None = None
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    """Parse one relay presence line -> (snapshot, claims).

    snapshot is the normalized presence dict: feed it back in as prev on the
    same player's next line. With prev=None (first sighting) there is no
    delta, so the line yields no claims. Claims, in fixed order: moved (tile
    change), lost hp (drop > 0, qualifier 'down N'), died (state transition
    to dead), won (state transition to victory). prev must belong to the same
    player id; otherwise MUD_REPLAY."""
    snap = _presence(line)
    claims: list[dict[str, str]] = []
    if prev is not None:
        prev = _presence(prev)
        if prev["id"] != snap["id"]:
            raise GwapError(
                "MUD_REPLAY", "prev snapshot is for a different player id"
            )
        tile = _tile_object(snap["x"], snap["y"], "MUD_REPLAY")
        if tile != _tile_object(prev["x"], prev["y"], "MUD_REPLAY"):
            claims.append(
                {"subject": snap["id"], "verb": "moved",
                 "object": tile, "qualifier": ""}
            )
        drop = round(prev["hp"] - snap["hp"], 1)
        if drop > 0:
            claims.append(
                {"subject": snap["id"], "verb": "lost", "object": "hp",
                 "qualifier": f"down {drop:g}"}
            )
        if snap["state"] == "dead" and prev["state"] != "dead":
            claims.append(
                {"subject": snap["id"], "verb": "died",
                 "object": tile, "qualifier": ""}
            )
        if snap["state"] == "victory" and prev["state"] != "victory":
            claims.append(
                {"subject": snap["id"], "verb": "won",
                 "object": tile, "qualifier": ""}
            )
    return snap, claims


def struct_from_replay(author: Any, lines: Iterable[Any]) -> dict[str, Any]:
    """Replay lines -> {author, claims} ready for build_payload(report_struct=...).
    Threads each player's last snapshot across the walk (mixed players in one
    stream are fine: prev tracking is per id); first sightings yield nothing."""
    if not isinstance(author, str) or not author.strip():
        raise GwapError("MUD_REPLAY", "author must be a non-empty string")
    claims: list[dict[str, str]] = []
    last: dict[str, dict[str, Any]] = {}
    for line in lines:
        peek = _presence(line)
        snap, fresh = from_replay_line(peek, last.get(peek["id"]))
        last[snap["id"]] = snap
        claims.extend(fresh)
    return {"author": author.strip(), "claims": claims}


# -- demo -------------------------------------------------------------------------------


def _demo() -> None:
    import hashlib

    from mag.gwap_payload import (
        HAS_CRYPTO,
        SessionLedger,
        anon_id,
        author_keypair,
        build_payload,
        sign_payload,
        utc_now_iso,
        verify_signature,
    )

    ts = utc_now_iso()
    robber = anon_id("mud-demo-robber-20260929")
    cop = anon_id("mud-demo-cop-20260929")

    # What the game loop knows: bearer-7 moves, strikes a brute, moves again.
    events = [
        {"player": {"id": "bearer-7", "x": 12.4, "y": 8.6},
         "action": "move"},
        {"player": {"id": "bearer-7", "x": 12.4, "y": 8.6},
         "action": "attack", "target": "mob-brute-3"},
        {"player": {"id": "bearer-7", "x": 13.2, "y": 8.6},
         "action": "move"},
    ]
    # What the relay saw: presence snapshots of the same run. The attack is
    # invisible to presence-only frames, so the cop corroborates 2 of 3.
    lines = [
        {"id": "bearer-7", "name": "Bearer Seven", "x": 0.5, "y": 0.5,
         "hp": 100, "max_hp": 100, "state": "play"},
        {"id": "bearer-7", "name": "Bearer Seven", "x": 12.4, "y": 8.6,
         "hp": 100, "max_hp": 100, "state": "play"},
        {"id": "bearer-7", "name": "Bearer Seven", "x": 13.2, "y": 8.6,
         "hp": 93.5, "max_hp": 100, "state": "play"},
    ]
    intent_struct = struct_from_events(robber, events)
    report_struct = struct_from_replay(cop, lines)
    payload = build_payload(
        scene_id="mud-arena-042",
        intent_struct=intent_struct,
        report_struct=report_struct,
        participants=[
            {"anon_id": robber, "role": "robber"},
            {"anon_id": cop, "role": "cop"},
        ],
        consent=True,
        created_utc=ts,
        replay_tape_ref={
            "sha256": hashlib.sha256(
                b"mud replay tape: gwap_mud demo 2026-09-29"
            ).hexdigest(),
            "engine_version": "mud-presence-v0",
        },
    )
    if HAS_CRYPTO:
        priv_hex, _pub_hex = author_keypair("mud-demo-robber-key-20260929")
        payload = sign_payload(payload, robber, priv_hex)

    ledger = SessionLedger("mud-demo-20260929")
    row = ledger.append(payload, ts_utc=ts)
    ok, bad = ledger.verify_chain()
    print("[mud -> gwap connector] session=mud-demo-20260929")
    print(f"  intent claims : "
          f"{[c['verb'] + ' ' + c['object'] for c in intent_struct['claims']]}")
    print(f"  report claims : "
          f"{[c['verb'] + ' ' + c['object'] for c in report_struct['claims']]}")
    print(f"  agreement     : {payload['agreement_score']}")
    print(f"  verdict       : {payload['verdict']}")
    print(f"  signature     : {verify_signature(payload)}")
    print(f"  ledger row    : seq={row['seq']} verify ok={ok} bad={bad}")
    print(f"  file          : {ledger.path}")
    print("note: the attack claim (attacked mob-brute-3) scores only when a")
    print("future relay frame carries attacker attribution; presence-only")
    print("frames cannot name the striker (semantic layer stays debt 5).")


if __name__ == "__main__":
    _demo()
