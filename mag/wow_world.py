"""wow_world -- the bones-world skeleton: rooms as legality tables on the bones gate.

Blueprint M0 (watch/inbox/WOW_CLONE_BETA_BLUEPRINT_20260916.md): the beta of "our WoW clone"
is NOT a private server and never will be. It is our own world on our own bones: every room is
a legality table, every door is a legality row, and every verb -- movement included --
dispatches through the SAME Dispatch gate mag/wow_bones.py runs. A room is a status
("ROOM:<id>"); a door is a row; a locked door is a STATUS_NEVER row; a missing door is no row
at all. Refusal stays typed in the gate's own vocabulary (UNKNOWN_OPCODE / UNKNOWN_STATUS /
STATUS_NEVER / STATUS_UNHANDLED / STATUS_MISMATCH) and handler_ran False is the gate's own
word, never ours.

The session is BonesSession extended, not replaced: same kernels (Instance for the encounter
law, Stream for the RNG law), same lifecycle (AUTHED -> LOGGEDIN on the first successful verb;
promotion draws nothing), same turn limit, same guarded DONE. What the world adds:
  * a `room` pointer and a `route` ledger,
  * a `go <direction>` verb whose legality IS the room's exit table,
  * movement that costs no draws and never loads an encounter,
  * encounters that load only where the room's table lists them, and only the Instance
    kernel's guarded DONE (world_boss refuses it forever) can complete them.

WHY ROW NAMES CARRY THEIR ROOM (`VERB@ROOM:<id>`): the gate keys rows by name alone; without
the room suffix a GO_NORTH row would silently overwrite across rooms -- one room's door
becoming every room's law, which is the one shape of silence this harness does not ship.

WHAT THIS IS NOT: not a client, not a server, not network play, not a character database, and
no C++, MySQL, or content from the clone (AzerothCore is GPL-2.0; we read the laws, we write
our own world).

RUN:
  python -m mag.wow_world start   --seed S [--world-boss]
  python -m mag.wow_world turn    --session <id> --verb go --arg north
  python -m mag.wow_world turn    --session <id> --verb look
  python -m mag.wow_world status  --session <id>
  python -m mag.wow_world verbs   --session <id>
  python -m mag.wow_world map     --session <id>
  python -m mag.wow_world receipt --session <id>

Schema: wow_world.v1 . deterministic + $0 . session + receipt files are the only writes
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

from mag.wow_bones import Dispatch, load_fixture  # noqa: E402
from mag.wow_bones_session import (AUTHED, BOSS_ID, DRAW_TARGET, LOGGEDIN,  # noqa: E402
                                   BonesSession, canonical)

WORLD_SCHEMA = "wow_world.v1"
SESSION_SCHEMA = "wow_world_session.v1"
RECEIPT_SCHEMA = "wow_session.v1"        # world receipts keep the bones receipt contract
OUT_DIR = ROOT / "memory" / "runs" / "wow_world"
SESSIONS_DIR = OUT_DIR / "sessions"
RECEIPTS_DIR = OUT_DIR / "receipts"

TO_BE_DECIDED = "TO_BE_DECIDED"
IN_PROGRESS = "IN_PROGRESS"

# The seed world: 5 rooms, one encounter (boss 0 in the vault), one locked door.
DEFAULT_WORLD: dict[str, Any] = {
    "schema": WORLD_SCHEMA,
    "id": "atrium-ring",
    "start": "atrium",
    "boss": 0,
    "rooms": [
        {"id": "atrium", "name": "The Atrium", "verbs_allowed": ["look"],
         "exits": {"north": "torch_hall", "east": "archive"}, "encounters": []},
        {"id": "torch_hall", "name": "The Torch Hall", "verbs_allowed": ["look"],
         "exits": {"south": "atrium", "east": "vault",
                   "west": {"room": "ash_gallery", "locked": True}},
         "encounters": []},
        {"id": "archive", "name": "The Archive", "verbs_allowed": ["look"],
         "exits": {"west": "atrium", "north": "vault"}, "encounters": []},
        {"id": "vault", "name": "The Vault", "verbs_allowed": ["look", "pry"],
         "exits": {"south": "torch_hall", "west": "archive"}, "encounters": [0]},
        {"id": "ash_gallery", "name": "The Ash Gallery", "verbs_allowed": ["look"],
         "exits": {"east": "torch_hall"}, "encounters": []},
    ],
}


def world_digest(world: dict[str, Any]) -> str:
    """12-hex binding of the exact legality table a session was played against."""
    return hashlib.sha256(canonical(world).encode("utf-8")).hexdigest()[:12]


def world_session_id(seed: str, world_boss: bool, world: dict[str, Any]) -> str:
    material = f"{SESSION_SCHEMA}:{world['id']}:{seed}:{int(bool(world_boss))}"
    return "wworld-" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:12]


def _handler_name(verb: str) -> str:
    return "WorldSession::Handle" + verb.title().replace("_", "")


def _write_json(path: Path, body: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical(body), encoding="utf-8")
    return path


def room_fixture(world: dict[str, Any]) -> dict[str, Any]:
    """Compile the world into a Dispatch-shaped fixture view.

    A room is a status, a door is a legality row; the gate class is reused verbatim over this
    table -- no gating logic lives here. Locked exits compile to STATUS_NEVER rows (the gate's
    first-class lock); open exits to rows whose status is the room they stand in.
    """
    statuses = {f"ROOM:{room['id']}": i for i, room in enumerate(world["rooms"])}
    rows: list[dict[str, Any]] = []
    for room in world["rooms"]:
        status = f"ROOM:{room['id']}"
        for verb in room["verbs_allowed"]:
            v = verb.strip().upper()
            rows.append({"opcode": "0x0", "name": f"{v}@{status}", "status": status,
                         "processing": "INPLACE", "handler": _handler_name(v)})
        for direction, target in room["exits"].items():
            d = direction.strip().upper()
            locked = isinstance(target, dict) and bool(target.get("locked"))
            rows.append({"opcode": "0x0", "name": f"GO_{d}@{status}",
                         "status": "STATUS_NEVER" if locked else status,
                         "processing": "INPLACE",
                         "handler": "WorldSession::HandleGo" + d.title()})
    return {"tables": {"client_opcodes": rows}, "enums": {"session_status": statuses}}


def _exit_target(room: dict[str, Any], direction: str) -> str:
    """Resolve a door row back to its destination room id (the gate proved the door exists)."""
    raw = room["exits"].get(direction, room["exits"].get(direction.lower()))
    if raw is None:
        # the gate DISPATCHED this door, so the table must resolve it; if it cannot, the
        # world table is corrupt -- fail loud, never silently stand still
        raise KeyError(f"exit row dispatched but unresolved: {direction} in {room['id']}")
    return raw["room"] if isinstance(raw, dict) else raw


class WorldSession(BonesSession):
    """BonesSession with a room pointer: same gate law, same kernels, same guarded DONE."""

    def __init__(self, fixture: dict[str, Any], seed: str,
                 world: dict[str, Any] | None = None, *, world_boss: bool = False):
        super().__init__(fixture, seed, world_boss=world_boss)
        self.world = world if world is not None else DEFAULT_WORLD
        self.room_gate = Dispatch(room_fixture(self.world))
        self.room = self.world["start"]
        self.route: list[str] = [self.room]
        self.session_id = world_session_id(self.seed, self.world_boss, self.world)

    # -- addressing (addressing is not legality: the gate decides) ----------------------

    def _room_status(self) -> str:
        return f"ROOM:{self.room}"

    def _row_name(self, verb_name: str) -> str:
        return f"{verb_name}@{self._room_status()}"

    def _current_room(self) -> dict[str, Any]:
        for room in self.world["rooms"]:
            if room["id"] == self.room:
                return room
        raise KeyError(f"room pointer off-table: {self.room}")

    # -- the game -----------------------------------------------------------------------

    def turn(self, verb: str, arg: str | None = None) -> dict[str, Any]:
        self.turn_count += 1
        verb_clean = verb.strip()
        is_move = verb_clean.lower() == "go" and arg is not None
        verb_name = ("GO_" + arg.strip().upper()) if is_move else verb_clean.upper()
        # THE GATE DECIDES. Composing the row name only addresses a legality row.
        gate = self.room_gate.dispatch(self._row_name(verb_name), self._room_status())
        entry: dict[str, Any] = {"n": self.turn_count, "verb": verb, "arg": arg,
                                 "room": self.room, "ok": bool(gate["ok"]),
                                 "reason": gate["reason"],
                                 "handler_ran": bool(gate["handler_ran"])}
        if gate["ok"]:
            entry["handler"] = gate["handler"]
            promoted = False
            if self.session_status == AUTHED:
                self.session_status = LOGGEDIN      # auth -> logged in; promotion draws nothing
                promoted = True                     # (the bones lifecycle law, verbatim)
            if is_move:
                dest = _exit_target(self._current_room(), arg.strip().upper())
                self.room = dest
                self.route.append(dest)
                entry["to"] = dest
                # movement draws nothing and never loads an encounter
            elif promoted:
                pass                                # the auth verb is consumed by promotion
            elif BOSS_ID in (self._current_room()["encounters"] or []) and \
                    self.instance.state[BOSS_ID] == self.instance.enums[TO_BE_DECIDED]:
                # a load, not a transition: the kernel commits and returns False (their contract)
                self.instance.set_boss_state(BOSS_ID, IN_PROGRESS)
            else:
                self.stream.next()
                self.draws += 1
                if self.instance.state[BOSS_ID] == self.instance.enums[IN_PROGRESS] and \
                        self.draws % DRAW_TARGET == 0:
                    # guarded terminal: refused forever under --world-boss (the kernel's own law)
                    self.instance.set_boss_state(BOSS_ID, "DONE",
                                                 world_boss_alive=self.world_boss)
        self.moves.append(entry)
        return entry

    # -- the receipt (wow_session.v1, extended with the world binding) -------------------

    def receipt(self) -> dict[str, Any]:
        body = {
            "schema": RECEIPT_SCHEMA,
            "session_id": self.session_id,
            "seed": self.seed,
            "world": self.world["id"],
            "world_sha256_12": world_digest(self.world),
            "world_boss_alive": self.world_boss,
            "room": self.room,
            "route": list(self.route),
            "bones_digest": (self.fixture.get("bones_digest") or "")[:12],
            "session_status": self.session_status,
            "encounter_state": self.encounter_name(),
            "draw_index": self.stream.index,
            "moves": self.moves,
            "verdict": self.verdict(),
        }
        body["sha256"] = hashlib.sha256(canonical(body).encode("utf-8")).hexdigest()
        return body

    # -- persistence (session + receipt files are the only writes) -----------------------

    def save(self) -> Path:
        state = {
            "schema": SESSION_SCHEMA,
            "session_id": self.session_id,
            "seed": self.seed,
            "world_boss_alive": self.world_boss,
            "world_id": self.world["id"],
            "world_sha256_12": world_digest(self.world),
            "room": self.room,
            "route": list(self.route),
            "session_status": self.session_status,
            "boss0": self.instance.state[BOSS_ID],
            "draws": self.draws,
            "turn_count": self.turn_count,
            "stream_log": list(self.stream.log),
            "moves": list(self.moves),
        }
        return _write_json(SESSIONS_DIR / f"{self.session_id}.json", state)

    @classmethod
    def load(cls, session_id: str,
             fixture: dict[str, Any] | None = None) -> "WorldSession | None":
        """Resume from the ledger. A changed world is not the world the session was played in."""
        path = SESSIONS_DIR / f"{session_id}.json"
        if not path.is_file():
            return None
        fixture = fixture if fixture is not None else load_fixture()
        if fixture is None:
            return None
        state = json.loads(path.read_text(encoding="utf-8"))
        if state.get("world_sha256_12") != world_digest(DEFAULT_WORLD):
            return None                             # typed refusal to resume a foreign world
        ses = cls(fixture, state["seed"], world_boss=state["world_boss_alive"])
        ses.session_status = state["session_status"]
        ses.room = state["room"]
        ses.route = state["route"]
        ses.instance.state[BOSS_ID] = state["boss0"]
        ses.draws = state["draws"]
        ses.turn_count = state["turn_count"]
        ses.stream.log = state["stream_log"]
        ses.stream.index = max((d["index"] for d in state["stream_log"]), default=-1) + 1
        ses.moves = state["moves"]
        return ses

    def write_receipt(self) -> Path:
        return _write_json(RECEIPTS_DIR / f"{self.session_id}.json", self.receipt())

    # -- surfaces ------------------------------------------------------------------------

    def legal_verbs(self) -> list[str]:
        """Rows legal right here, right now: this room's status, minus the STATUS_NEVER locks."""
        here = self._room_status()
        return sorted(name.split("@", 1)[0] for name, row in self.room_gate.rows.items()
                      if row["status"] == here)


def _emit(obj: Any) -> None:
    print(canonical(obj))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="wow-world")
    ap.add_argument("cmd",
                    choices=["start", "turn", "status", "receipt", "verbs", "map"])
    ap.add_argument("--seed")
    ap.add_argument("--world-boss", action="store_true")
    ap.add_argument("--session")
    ap.add_argument("--verb")
    ap.add_argument("--arg")
    a = ap.parse_args(argv)

    if a.cmd == "start":
        fx = load_fixture()
        if fx is None:
            _emit({"ok": False, "reason": "NO_FIXTURE",
                   "hint": "python -m mag.wow_bones extract"})
            return 1
        ses = WorldSession(fx, a.seed or "0", world_boss=a.world_boss)
        ses.save()
        _emit({"ok": True, "schema": SESSION_SCHEMA, "session_id": ses.session_id,
               "seed": ses.seed, "world": ses.world["id"], "room": ses.room,
               "session_status": ses.session_status,
               "encounter_state": ses.encounter_name(), "draw_index": 0,
               "verdict": ses.verdict()})
        return 0

    if not a.session:
        _emit({"ok": False, "reason": "NO_SESSION", "hint": "--session <id>"})
        return 1
    ses = WorldSession.load(a.session)
    if ses is None:
        _emit({"ok": False, "reason": "UNKNOWN_SESSION", "session": a.session})
        return 1

    if a.cmd == "turn":
        if not a.verb:
            _emit({"ok": False, "reason": "NO_VERB", "hint": "--verb go|look [--arg north]"})
            return 1
        entry = ses.turn(a.verb, a.arg)
        ses.save()
        _emit({"ok": True, "turn": entry, "room": ses.room, "route": ses.route,
               "session_status": ses.session_status,
               "encounter_state": ses.encounter_name(),
               "draw_index": ses.stream.index, "verdict": ses.verdict()})
        return 0
    if a.cmd == "status":
        _emit({"ok": True, "session_id": ses.session_id, "seed": ses.seed,
               "world": ses.world["id"], "room": ses.room, "route": ses.route,
               "session_status": ses.session_status,
               "encounter_state": ses.encounter_name(),
               "draw_index": ses.stream.index, "turn_count": ses.turn_count,
               "verdict": ses.verdict()})
        return 0
    if a.cmd == "receipt":
        path = ses.write_receipt()
        _emit(ses.receipt())
        print(path, file=sys.stderr)
        return 0
    if a.cmd == "verbs":
        _emit({"ok": True, "room": ses.room, "legal_verbs": ses.legal_verbs()})
        return 0
    if a.cmd == "map":
        room = ses._current_room()
        _emit({"ok": True, "room": ses.room, "name": room["name"],
               "exits": {d: (t["room"] if isinstance(t, dict) else t)
                         for d, t in room["exits"].items()},
               "encounters": room["encounters"]})
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
