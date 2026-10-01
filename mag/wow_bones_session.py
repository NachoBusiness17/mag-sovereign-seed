"""wow_bones_session -- the referee: a session runner on the bones kernels.

The directive (watch/inbox/HERMES_DIRECTIVE_BONES_REFEREE_20260916.md) names ONE artifact:
a session that runs the dispatch ordering law, the encounter law, and the RNG law end to
end, so a human can play a bones-legal game and get a byte-stable, replayable receipt.
Hermes' handoff went unpicked (verified 2026-09-16); the Sep-20 proof needed it to exist,
so the zcode seat built it to the same contract -- the falsifiers below are the directive's
own, binding this code the way they would have bound Hermes'.

THE GAME (stated laws, small on purpose):
  * A session begins in STATUS_AUTHED (the slice the legality tables trust).
  * A turn is one verb name dispatched through Dispatch.dispatch() -- the gate runs BEFORE
    the verb; refusals are typed (UNKNOWN_OPCODE / UNKNOWN_STATUS / STATUS_NEVER /
    STATUS_UNHANDLED / STATUS_MISMATCH) and never silent.
  * The first successful AUTHED verb promotes the session to STATUS_LOGGEDIN (the real
    WorldSession lifecycle: auth, then logged in). Promotion draws nothing.
  * The first successful LOGGEDIN verb writes boss 0 from TO_BE_DECIDED to IN_PROGRESS
    (a load, not a transition -- Instance returns False per the AzerothCore contract).
  * Every successful LOGGEDIN verb after that draws the seeded Stream. On every DRAW_TARGET
    (3) draws the runner attempts boss 0 -> DONE, honoring the world-boss guard: with
    --world-boss the attempt is refused forever and the session can never COMPLETE.
  * TURN_LIMIT (8) turns without DONE ends the session EXHAUSTED. DONE ends it COMPLETE.
    Anything else is OPEN.

WHAT THIS IS NOT: not a client, not a server, not network play, not a character database.
The adapter may format; only the kernels decide.

RUN:
  python -m mag.wow_bones_session start --seed S [--world-boss]
  python -m mag.wow_bones_session verbs --session <id> [--limit N]
  python -m mag.wow_bones_session turn  --session <id> --verb <VERB>
  python -m mag.wow_bones_session status --session <id>
  python -m mag.wow_bones_session receipt --session <id>
  python -m mag.wow_bones session ...          # same commands, forwarded

Schema: wow_session.v1 . deterministic + $0 . session + receipt files are the only writes
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

from mag.wow_bones import FX_PRESENT, Dispatch, Instance, Stream, load_fixture  # noqa: E402

SCHEMA = "wow_session.v1"
SESSION_SCHEMA = "wow_bones_session.v1"
OUT_DIR = ROOT / "memory" / "runs" / "wow_bones"
SESSIONS_DIR = OUT_DIR / "sessions"
RECEIPTS_DIR = OUT_DIR / "receipts"

AUTHED = "STATUS_AUTHED"
LOGGEDIN = "STATUS_LOGGEDIN"
DRAW_TARGET = 3      # draws before the runner attempts boss DONE
TURN_LIMIT = 8       # turns without DONE end the session EXHAUSTED
BOSS_ID = 0          # the demo encounter is boss 0


def canonical(obj: Any) -> str:
    """The only serialization this module speaks -- byte-stable by construction."""
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def session_id_for(seed: str, world_boss: bool) -> str:
    material = f"{SESSION_SCHEMA}:{seed}:{int(world_boss)}"
    return "bones-" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:12]


class BonesSession:
    """Three kernels, one referee. Every turn is gate-first; every draw records its index."""

    def __init__(self, fixture: dict[str, Any], seed: str, *, world_boss: bool = False):
        self.fixture = fixture
        self.seed = str(seed)
        self.world_boss = bool(world_boss)
        self.session_id = session_id_for(self.seed, self.world_boss)
        self.dispatch = Dispatch(fixture)
        self.instance = Instance(fixture)
        self.stream = Stream(self.seed)
        self.session_status = AUTHED
        self.turn_count = 0
        self.draws = 0
        self.moves: list[dict[str, Any]] = []

    # -- state helpers ------------------------------------------------------------------

    def encounter_name(self) -> str:
        return self.instance.name(self.instance.state[BOSS_ID])

    def verdict(self) -> str:
        if self.instance.is_done(BOSS_ID):
            return "COMPLETE"
        if self.turn_count >= TURN_LIMIT:
            return "EXHAUSTED"
        return "OPEN"

    # -- the game -----------------------------------------------------------------------

    def turn(self, verb: str) -> dict[str, Any]:
        self.turn_count += 1
        gate = self.dispatch.dispatch(verb, self.session_status)
        entry: dict[str, Any] = {"n": self.turn_count, "verb": verb,
                                 "ok": bool(gate["ok"]), "reason": gate["reason"]}
        if gate["ok"]:
            entry["handler"] = gate["handler"]
            if self.session_status == AUTHED:
                self.session_status = LOGGEDIN      # auth -> logged in; no draw
            elif self.instance.state[BOSS_ID] == self.instance.enums["TO_BE_DECIDED"]:
                # a load, not a transition: the kernel commits the state and returns False
                self.instance.set_boss_state(BOSS_ID, "IN_PROGRESS")
            else:
                self.stream.next()
                self.draws += 1
                if self.draws % DRAW_TARGET == 0:
                    # guarded terminal: refused forever under --world-boss
                    self.instance.set_boss_state(BOSS_ID, "DONE",
                                                 world_boss_alive=self.world_boss)
        self.moves.append(entry)
        return entry

    # -- the receipt (wow_session.v1) ---------------------------------------------------

    def receipt(self) -> dict[str, Any]:
        body = {
            "schema": SCHEMA,
            "session_id": self.session_id,
            "seed": self.seed,
            "world_boss_alive": self.world_boss,
            "bones_digest": (self.fixture.get("bones_digest") or "")[:12],
            "session_status": self.session_status,
            "encounter_state": self.encounter_name(),
            "draw_index": self.stream.index,
            "moves": self.moves,
            "verdict": self.verdict(),
        }
        body["sha256"] = hashlib.sha256(canonical(body).encode("utf-8")).hexdigest()
        return body

    # -- persistence (session + receipt files are the only writes) ----------------------

    def save(self) -> Path:
        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        state = {
            "schema": SESSION_SCHEMA,
            "session_id": self.session_id,
            "seed": self.seed,
            "world_boss_alive": self.world_boss,
            "session_status": self.session_status,
            "boss0": self.instance.state[BOSS_ID],
            "draws": self.draws,
            "turn_count": self.turn_count,
            "stream_log": self.stream.log,
            "moves": self.moves,
        }
        path = SESSIONS_DIR / f"{self.session_id}.json"
        path.write_text(canonical(state), encoding="utf-8")
        return path

    @classmethod
    def load(cls, session_id: str) -> "BonesSession | None":
        path = SESSIONS_DIR / f"{session_id}.json"
        if not path.is_file():
            return None
        state = json.loads(path.read_text(encoding="utf-8"))
        fixture = load_fixture()
        if fixture is None:
            return None
        ses = cls(fixture, state["seed"], world_boss=state["world_boss_alive"])
        ses.session_status = state["session_status"]
        ses.instance.state[BOSS_ID] = state["boss0"]
        ses.draws = state["draws"]
        ses.turn_count = state["turn_count"]
        ses.stream.log = state["stream_log"]
        ses.stream.index = max((d["index"] for d in state["stream_log"]), default=-1) + 1
        ses.moves = state["moves"]
        return ses

    def write_receipt(self) -> Path:
        RECEIPTS_DIR.mkdir(parents=True, exist_ok=True)
        path = RECEIPTS_DIR / f"{self.session_id}.json"
        path.write_text(canonical(self.receipt()), encoding="utf-8")
        return path


def _fixture_or_none() -> dict[str, Any] | None:
    fx = load_fixture()
    if fx is None and FX_PRESENT():
        fx = load_fixture()
    return fx


def _emit(obj: Any) -> None:
    print(canonical(obj))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="wow-bones-session")
    ap.add_argument("cmd", choices=["start", "turn", "status", "receipt", "verbs"])
    ap.add_argument("--seed")
    ap.add_argument("--world-boss", action="store_true")
    ap.add_argument("--session")
    ap.add_argument("--verb")
    ap.add_argument("--limit", type=int, default=12)
    a = ap.parse_args(argv)

    if a.cmd == "start":
        fx = _fixture_or_none()
        if fx is None:
            _emit({"ok": False, "reason": "NO_FIXTURE",
                   "hint": "python -m mag.wow_bones extract"})
            return 1
        ses = BonesSession(fx, a.seed or "0", world_boss=a.world_boss)
        ses.save()
        _emit({"ok": True, "schema": SESSION_SCHEMA, "session_id": ses.session_id,
               "seed": ses.seed, "world_boss_alive": ses.world_boss,
               "session_status": ses.session_status,
               "encounter_state": ses.encounter_name(), "draw_index": 0,
               "verdict": ses.verdict()})
        return 0

    if not a.session:
        _emit({"ok": False, "reason": "NO_SESSION", "hint": "--session <id>"})
        return 1
    ses = BonesSession.load(a.session)
    if ses is None:
        _emit({"ok": False, "reason": "UNKNOWN_SESSION", "session": a.session})
        return 1

    if a.cmd == "turn":
        if not a.verb:
            _emit({"ok": False, "reason": "NO_VERB", "hint": "--verb <OPCODE_NAME>"})
            return 1
        entry = ses.turn(a.verb)
        ses.save()
        _emit({"ok": True, "turn": entry, "session_status": ses.session_status,
               "encounter_state": ses.encounter_name(),
               "draw_index": ses.stream.index, "verdict": ses.verdict()})
        return 0
    if a.cmd == "status":
        _emit({"ok": True, "session_id": ses.session_id, "seed": ses.seed,
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
        legal = [v for v in ses.dispatch.verbs()
                 if ses.dispatch.rows[v]["status"] == ses.session_status]
        _emit({"ok": True, "session_status": ses.session_status,
               "legal_verbs": legal[: max(0, a.limit)], "total": len(legal)})
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
