"""wow_player -- player files as append-only ledgers (blueprint M2).

The law: a character is a LEDGER, not a database row. Login is resume-from-ledger:
the traits dict on disk is only a materialized view; load() replays the hash-chained
ledger rows through pure reducers and refuses the file when the view disagrees
(VIEW_MISMATCH). The anti-MySQL law made structural.

THE FILE (schema wow_player.v1, one JSON per player under memory/runs/wow_player):
  schema + player_id ("ply-" + sha256 of the name, salt = the schema string itself,
  secret-free) + name + traits {room, stamina_max, inventory} + ledger rows
  [{n, event, data, prev, hash}]. Every mutation appends EXACTLY one row; rows are
  never edited or removed. Grants survive spends in the ledger; only the replayed
  view drops the spent item.

DETERMINISM: no timestamps, no clocks, no randomness -- created_ts is deliberately
omitted so the same moves always produce the same bytes. canonical() is the only
serialization this module speaks: saving, row hashing, and byte-identity all use it.

RUN:
  python -m mag.wow_player create --name NAME [--room R] [--stamina N]
  python -m mag.wow_player apply   --player ply-... --event EVENT [--data JSON]
  python -m mag.wow_player show    --player ply-...
  python -m mag.wow_player verify  --player ply-...

Deterministic + $0 + stdlib only. The player file is the only write.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SCHEMA = "wow_player.v1"
STORE = ROOT / "memory" / "runs" / "wow_player"

_ZERO_HASH = "0" * 64
_FILE_KEYS = {"schema", "player_id", "name", "traits", "ledger"}
_ROW_KEYS = {"n", "event", "data", "prev", "hash"}
_EVENTS = {"create", "move", "stamina", "grant_item", "spend_item"}


def canonical(obj: Any) -> str:
    """The only serialization this module speaks -- byte-stable by construction."""
    return json.dumps(
        obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def player_id_for(name: str) -> str:
    """Derived, deterministic, secret-free: the salt is the schema string itself."""
    return "ply-" + hashlib.sha256(
        f"{SCHEMA}:{name}".encode("utf-8")
    ).hexdigest()[:12]


class PlayerLedgerError(Exception):
    def __init__(self, reason: str, message: str = "") -> None:
        self.reason = reason
        super().__init__(message or reason)


def _row_hash(row: dict[str, Any]) -> str:
    payload = {key: row[key] for key in ("n", "event", "data", "prev")}
    return hashlib.sha256(canonical(payload).encode("utf-8")).hexdigest()


def _new_row(
    n: int, event: str, data: dict[str, Any], prev: str
) -> dict[str, Any]:
    row = {"n": n, "event": event, "data": deepcopy(data), "prev": prev}
    row["hash"] = _row_hash(row)
    return row


def _require_data(condition: bool) -> None:
    if not condition:
        raise PlayerLedgerError("INVALID_DATA", "Invalid event data")


def _reduce(
    event: str, data: dict[str, Any], view: dict[str, Any] | None
) -> dict[str, Any]:
    """Pure reducer: (event, data, view) -> new view. Never mutates the input view."""
    if not isinstance(event, str) or event not in _EVENTS:
        raise PlayerLedgerError("UNKNOWN_EVENT", f"Unknown event: {event!r}")
    _require_data(isinstance(data, dict))

    if event == "create":
        if view is not None:
            raise PlayerLedgerError("BAD_N", "Create is permitted only at genesis")
        _require_data(
            set(data) == {"room", "stamina_max"}
            and isinstance(data["room"], str)
            and type(data["stamina_max"]) is int
        )
        return {
            "room": data["room"],
            "stamina_max": data["stamina_max"],
            "inventory": [],
        }

    if view is None:
        raise PlayerLedgerError("BAD_N", "The first event must be create")

    result = deepcopy(view)
    if event == "move":
        _require_data(set(data) == {"to"} and isinstance(data["to"], str))
        result["room"] = data["to"]
    elif event == "stamina":
        _require_data(set(data) == {"delta"} and type(data["delta"]) is int)
        result["stamina_max"] += data["delta"]
    elif event == "grant_item":
        _require_data(set(data) == {"item"} and isinstance(data["item"], dict))
        result["inventory"].append(deepcopy(data["item"]))
    elif event == "spend_item":
        # The spend SHADOWS a grant; the ledger keeps both rows forever. Only the
        # replayed view drops the earliest unspent grant carrying that item_id.
        _require_data(
            set(data) == {"item_id"} and isinstance(data["item_id"], str)
        )
        for index, item in enumerate(result["inventory"]):
            if item.get("item_id") == data["item_id"]:
                del result["inventory"][index]
                break
    return result


def _replay(ledger: list[dict[str, Any]]) -> dict[str, Any]:
    view = None
    for row in ledger:
        view = _reduce(row["event"], row["data"], view)
    if view is None:
        raise PlayerLedgerError("BAD_N", "A ledger must contain genesis")
    return view


def verify_file(d: Any) -> tuple[bool, str]:
    """Typed referee. Checks in order: BAD_SCHEMA, BAD_ID, BAD_N, BROKEN_CHAIN,
    TAMPERED, VIEW_MISMATCH. OK only when all pass."""
    if (
        not isinstance(d, dict)
        or d.get("schema") != SCHEMA
        or set(d) != _FILE_KEYS
        or not isinstance(d["name"], str)
        or not isinstance(d["ledger"], list)
    ):
        return False, "BAD_SCHEMA"

    ledger = d["ledger"]
    for row in ledger:
        if (
            not isinstance(row, dict)
            or set(row) != _ROW_KEYS
            or not isinstance(row["event"], str)
            or not isinstance(row["data"], dict)
        ):
            return False, "BAD_SCHEMA"

    expected_id = player_id_for(d["name"])
    if d["player_id"] != expected_id:
        return False, "BAD_ID"

    if not ledger:
        return False, "BAD_N"
    for expected_n, row in enumerate(ledger, 1):
        if type(row["n"]) is not int or row["n"] != expected_n:
            return False, "BAD_N"

    previous_hash = _ZERO_HASH
    for row in ledger:
        if row["prev"] != previous_hash:
            return False, "BROKEN_CHAIN"
        previous_hash = row["hash"]

    for row in ledger:
        if row["hash"] != _row_hash(row):
            return False, "TAMPERED"

    try:
        replayed = _replay(ledger)
        if canonical(replayed) != canonical(d["traits"]):
            return False, "VIEW_MISMATCH"
    except (
        PlayerLedgerError,
        TypeError,
        ValueError,
        UnicodeError,
        RecursionError,
    ):
        return False, "VIEW_MISMATCH"

    return True, "OK"


def _path_for(player_id: str) -> Path:
    if not isinstance(player_id, str) or re.fullmatch(
        r"ply-[0-9a-f]{12}", player_id
    ) is None:
        raise PlayerLedgerError("BAD_ID", "Invalid player identifier")
    return STORE / f"{player_id}.json"


def _read_document(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise PlayerLedgerError("BAD_SCHEMA", "Invalid JSON player file") from exc


def _json_data(data: dict[str, Any]) -> dict[str, Any]:
    """Detach input and ensure its persisted representation is replayable."""
    try:
        return json.loads(canonical(data))
    except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
        raise PlayerLedgerError("INVALID_DATA", "Event data must be JSON") from exc


class PlayerFile:
    def __init__(self, document: dict[str, Any]) -> None:
        ok, reason = verify_file(document)
        if not ok:
            raise PlayerLedgerError(reason, "Invalid player ledger")
        self._document = deepcopy(document)
        self._document["traits"] = _replay(self._document["ledger"])

    @property
    def player_id(self) -> str:
        return self._document["player_id"]

    @property
    def name(self) -> str:
        return self._document["name"]

    @property
    def traits(self) -> dict[str, Any]:
        return deepcopy(self._document["traits"])

    @property
    def ledger(self) -> list[dict[str, Any]]:
        return deepcopy(self._document["ledger"])

    @classmethod
    def create(
        cls, name: str, room: str = "atrium", stamina_max: int = 10
    ) -> PlayerFile:
        """Genesis row n=1. A second create for the same name is REFUSED -- the
        character already exists as its ledger; resume with load()."""
        _require_data(isinstance(name, str))
        data = {"room": room, "stamina_max": stamina_max}
        traits = _reduce("create", data, None)
        player_id = player_id_for(name)

        path = _path_for(player_id)
        document = {
            "schema": SCHEMA,
            "player_id": player_id,
            "name": name,
            "traits": traits,
            "ledger": [_new_row(1, "create", data, _ZERO_HASH)],
        }
        player = cls(document)
        content = player.canonical_state().encode("utf-8")
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with path.open("xb") as stream:
                stream.write(content)
        except FileExistsError as exc:
            raise PlayerLedgerError(
                "ALREADY_EXISTS", "Player already exists; resume with load"
            ) from exc
        return player

    def apply(self, event: str, **data: Any) -> dict[str, Any]:
        """Every mutation appends EXACTLY one row, then saves."""
        if not isinstance(event, str) or event not in _EVENTS:
            raise PlayerLedgerError("UNKNOWN_EVENT", f"Unknown event: {event!r}")

        # Validate before JSON normalization so booleans cannot become integers
        # and non-dict receipts cannot become acceptable via serialization.
        _reduce(event, data, self._document["traits"])
        detached_data = _json_data(data)
        document = self.to_file()
        ledger = document["ledger"]
        row = _new_row(len(ledger) + 1, event, detached_data, ledger[-1]["hash"])
        ledger.append(row)
        document["traits"] = _replay(ledger)

        candidate = type(self)(document)
        candidate.save()
        self._document = candidate._document
        return deepcopy(row)

    def to_file(self) -> dict[str, Any]:
        return deepcopy(self._document)

    def canonical_state(self) -> str:
        """The byte-identity surface: the M2 falsifier compares these strings."""
        return canonical(self.to_file())

    def save(self) -> Path:
        document = self.to_file()
        ok, reason = verify_file(document)
        if not ok:
            raise PlayerLedgerError(reason, "Refusing to save an invalid ledger")

        path = _path_for(self.player_id)
        content = canonical(document).encode("utf-8")
        path.parent.mkdir(parents=True, exist_ok=True)

        # A stale instance must not truncate or replace an already-written chain:
        # history is append-only at the FILE level too.
        try:
            existing = _read_document(path)
        except FileNotFoundError:
            existing = None
        else:
            ok, reason = verify_file(existing)
            if not ok:
                raise PlayerLedgerError(reason, "Existing player file is invalid")
            old_ledger = existing["ledger"]
            if (
                existing["player_id"] != self.player_id
                or existing["name"] != self.name
                or len(old_ledger) > len(document["ledger"])
                or canonical(old_ledger)
                != canonical(document["ledger"][: len(old_ledger)])
            ):
                raise PlayerLedgerError(
                    "LEDGER_CONFLICT", "Saving would replace ledger history"
                )

        path.write_bytes(content)
        return path

    @classmethod
    def load(cls, player_id: str) -> PlayerFile | None:
        """Login = resume-from-ledger. Never trusts the stored view: the ledger
        is replayed and compared. Returns None only when the file is absent."""
        path = _path_for(player_id)
        try:
            document = _read_document(path)
        except FileNotFoundError:
            return None

        ok, reason = verify_file(document)
        if not ok:
            raise PlayerLedgerError(reason, "Invalid player file")
        if document["player_id"] != player_id:
            raise PlayerLedgerError("BAD_ID", "File identity differs from its name")
        return cls(document)


def _emit(obj: Any) -> None:
    print(canonical(obj))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    create_parser = commands.add_parser("create")
    create_parser.add_argument("--name", required=True)
    create_parser.add_argument("--room", default="atrium")
    create_parser.add_argument("--stamina", type=int, default=10)

    apply_parser = commands.add_parser("apply")
    apply_parser.add_argument("--player", required=True)
    apply_parser.add_argument("--event", required=True)
    apply_parser.add_argument("--data", default="{}")

    show_parser = commands.add_parser("show")
    show_parser.add_argument("--player", required=True)

    verify_parser = commands.add_parser("verify")
    verify_parser.add_argument("--player", required=True)

    args = parser.parse_args(argv)
    try:
        if args.command == "create":
            player = PlayerFile.create(args.name, args.room, args.stamina)
            _emit(player.to_file())
            return 0

        if args.command == "verify":
            try:
                document = _read_document(_path_for(args.player))
            except FileNotFoundError:
                _emit({"ok": False, "reason": "NOT_FOUND"})
                return 1
            ok, reason = verify_file(document)
            if ok and document["player_id"] != args.player:
                ok, reason = False, "BAD_ID"
            _emit({"ok": ok, "reason": reason})
            return 0 if ok else 1

        player = PlayerFile.load(args.player)
        if player is None:
            raise PlayerLedgerError("NOT_FOUND", "Player file does not exist")

        if args.command == "apply":
            try:
                data = json.loads(args.data)
            except (ValueError, RecursionError) as exc:
                raise PlayerLedgerError("INVALID_DATA", "Invalid event JSON") from exc
            _require_data(isinstance(data, dict))
            if "event" in data:
                raise PlayerLedgerError("INVALID_DATA", "Event is not a data field")
            player.apply(args.event, **data)

        _emit(player.to_file())
        return 0
    except PlayerLedgerError as exc:
        _emit({"ok": False, "reason": exc.reason})
        return 1
    except OSError:
        _emit({"ok": False, "reason": "IO_ERROR"})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
