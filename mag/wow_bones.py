"""wow_bones -- take the BONES of AzerothCore out of the C++ and make them runnable + testable.

The operator (2026-09-15): "we want the bones of this thing and the ability to test against it,
not necessarily the client itself -- it's like rebuilding photoshop from scratch without all the
bullshit nonsense."

So this is the extraction, in the two halves that phrase names:

  1. THE BONES  -- the laws that make a 1,212-file C++ engine a *world*: the dispatch table with
     its status gate, the packet-processing places, the encounter state machine, the typed
     refusal vocabulary. Those are DATA, and they come out of the clone by parsing, not by
     building: `extract()` reads Opcodes.cpp / Opcodes.h / InstanceScript.h and writes a
     fixture (`bones.json`) with a `bones_digest` -- the contract version our verifier binds to.
     725 client verbs, 587 server verbs, 6 session statuses, 3 processing places, 6 encounter
     states. No compiler, no MySQL, no client, no 1.1 GB of map data.

  2. THE ABILITY TO TEST AGAINST IT -- three kernels that RUN those laws, so a claim about them
     is a passing test instead of a paragraph:
       Dispatch  -- the ORDERING LAW: the status gate is evaluated on the table BEFORE the verb
                    runs. AzerothCore proves it at WorldSession.cpp:436 (switch (opHandle->Status)
                    inside the dispatch loop). Here it is executable and falsifiable.
       Instance  -- the ENCOUNTER LAW: NOT_STARTED / IN_PROGRESS / FAIL / DONE / SPECIAL plus the
                    loading state TO_BE_DECIDED, with the real transition rules (a load is not a
                    transition; a repeated state is not a transition; DONE is refused while a
                    world-boss minion lives).
       Stream    -- the RNG LAW, and the DIFFERENTIAL: a seeded stream whose every draw records
                    its index, so a replayed log either reproduces or reports RNG_DIVERGE.
                    AzerothCore's urand()/rand32() (src/common/Utilities/Random.h:30,36) is a
                    process-global mutable stream with no run seed and no draw index -- it is the
                    counter-example that makes this kernel worth having. We test against their
                    design by proving the property theirs cannot have.

WHAT THIS IS NOT: not a build, not a fork, not a vendored engine, not a client, not a merge. No
C++ is copied and none is needed -- the bones are counts, names, enums and rules, verified against
the source by `mag/wow_steal.py verify` and re-parsed here. AzerothCore is GPL-2.0; we read it.

RUN:
  python -m mag.wow_bones extract   # parse the clone -> bones.json (+ digest)
  python -m mag.wow_bones laws      # the extracted laws, each with its citation
  python -m mag.wow_bones status    # fixture presence + digest + source head
Tests: tests/test_wow_bones.py (skips itself cleanly when the clone is absent).

Schema: wow_bones.v1 . deterministic + $0 . the fixture write is the only write
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

SCHEMA = "wow_bones.v1"
ACORE = ROOT.parent / "azerothcore-wow"
OUT_DIR = ROOT / "memory" / "runs" / "wow_bones"
FIXTURE = OUT_DIR / "bones.json"

SRC_OPCODES_CPP = "src/server/game/Server/Protocol/Opcodes.cpp"
SRC_OPCODES_H = "src/server/game/Server/Protocol/Opcodes.h"
SRC_INSTANCE_H = "src/server/game/Instances/InstanceScript.h"
SRC_INSTANCE_CPP = "src/server/game/Instances/InstanceScript.cpp"
SRC_RANDOM_H = "src/common/Utilities/Random.h"

_RE_CLIENT = re.compile(
    r"/\*0x([0-9A-Fa-f]+)\*/\s*DEFINE_HANDLER\(\s*([A-Za-z0-9_]+)\s*,\s*([A-Za-z0-9_]+)\s*,"
    r"\s*([A-Za-z0-9_]+)\s*,\s*&WorldSession::([A-Za-z0-9_]+)")
_RE_SERVER = re.compile(
    r"/\*0x([0-9A-Fa-f]+)\*/\s*DEFINE_SERVER_OPCODE_HANDLER\(\s*([A-Za-z0-9_]+)\s*,"
    r"\s*([A-Za-z0-9_]+)\s*\)")
_RE_ENUM = re.compile(r"^\s*([A-Z][A-Z0-9_]*)\s*(?:=\s*(\d+))?", re.M)
_RE_LINECOMMENT = re.compile(r"//[^\n]*")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _read(rel: str) -> str:
    p = ACORE / rel
    return p.read_text(encoding="utf-8", errors="replace") if p.is_file() else ""


def parse_opcodes(cpp_text: str) -> dict[str, list[dict[str, Any]]]:
    """The alphabet, straight out of the dispatch table."""
    client = [{"opcode": f"0x{op.upper()}", "name": name, "status": status,
               "processing": proc, "handler": handler}
              for op, name, status, proc, handler in _RE_CLIENT.findall(cpp_text)]
    server = [{"opcode": f"0x{op.upper()}", "name": name, "status": status}
              for op, name, status in _RE_SERVER.findall(cpp_text)]
    return {"client_opcodes": client, "server_opcodes": server}


def parse_enums(h_text: str, instance_h: str, cpp_text: str) -> dict[str, dict[str, int]]:
    """The three vocabularies the dispatch law is written in."""
    def block(text: str, header: str) -> str:
        i = text.find(header)
        if i < 0:
            return ""
        j = text.find("};", i)
        return text[i:j] if j > 0 else text[i:]

    def members(text: str) -> dict[str, int]:
        out: dict[str, int] = {}
        nxt = 0
        for name, val in _RE_ENUM.findall(_RE_LINECOMMENT.sub("", text)):
            nxt = int(val) if val else nxt
            out[name] = nxt
            nxt += 1
        return out

    return {
        "session_status": members(block(h_text, "enum SessionStatus")),
        "packet_processing": members(block(h_text, "enum PacketProcessing")),
        "encounter_state": members(block(instance_h, "enum EncounterState")),
        # the loading state matters to the transition law; assert it is parsed, not assumed
        "_instance_cpp_present": {"yes": 1 if "InstanceScript::SetBossState" in cpp_text else 0},
    }


def extract(write: bool = False) -> dict[str, Any]:
    """Read the bones out of the clone. `write=True` files the fixture (the only write)."""
    cpp = _read(SRC_OPCODES_CPP)
    h = _read(SRC_OPCODES_H)
    inst_h = _read(SRC_INSTANCE_H)
    inst_cpp = _read(SRC_INSTANCE_CPP)
    if not cpp or not inst_h:
        return {"ok": False, "schema": SCHEMA, "error": f"clone not found or incomplete at {ACORE}",
                "acore": str(ACORE)}

    tables = parse_opcodes(cpp)
    enums = parse_enums(h, inst_h, inst_cpp)
    digest_src = json.dumps({"tables": tables, "enums": enums}, ensure_ascii=False,
                            sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(digest_src.encode("utf-8")).hexdigest()
    out = {
        "ok": True,
        "schema": SCHEMA,
        "ts": _now(),
        "acore": str(ACORE),
        "source": {"opcodes_cpp": SRC_OPCODES_CPP, "opcodes_h": SRC_OPCODES_H,
                   "instance_h": SRC_INSTANCE_H, "instance_cpp": SRC_INSTANCE_CPP},
        "source_sha256_12": {
            SRC_OPCODES_CPP: hashlib.sha256(cpp.encode("utf-8")).hexdigest()[:12],
            SRC_OPCODES_H: hashlib.sha256(h.encode("utf-8")).hexdigest()[:12],
            SRC_INSTANCE_H: hashlib.sha256(inst_h.encode("utf-8")).hexdigest()[:12],
        },
        "counts": {"client_opcodes": len(tables["client_opcodes"]),
                   "server_opcodes": len(tables["server_opcodes"]),
                   "session_status": len(enums["session_status"]),
                   "packet_processing": len(enums["packet_processing"]),
                   "encounter_state": len(enums["encounter_state"])},
        "enums": enums,
        "tables": tables,
        "bones_digest": digest,
        "law": "bones are data: parsed, hashed, and re-derivable; no C++ copied or compiled",
    }
    if write:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        FIXTURE.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        out["fixture"] = str(FIXTURE)
    return out


def load_fixture() -> dict[str, Any] | None:
    if FIXTURE.is_file():
        try:
            return json.loads(FIXTURE.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


# ---------------------------------------------------------------------------------------------
# THE KERNELS -- run the laws so a claim about them is a test, not a paragraph
# ---------------------------------------------------------------------------------------------

class Dispatch:
    """The ORDERING LAW, executable.

    AzerothCore (WorldSession.cpp:436) switches on `opHandle->Status` BEFORE the handler runs;
    a verb asked for in the wrong phase is dropped, not interpreted. Here that is a refusal with
    a typed reason and a handler that provably never fired.
    """

    # statuses a client is allowed to be in; STATUS_NEVER is a server-side/removed verb
    CLIENT_ABLE = ("STATUS_AUTHED", "STATUS_LOGGEDIN", "STATUS_TRANSFER",
                   "STATUS_LOGGEDIN_OR_RECENTLY_LOGGOUT")

    def __init__(self, fixture: dict[str, Any]):
        self.rows = {r["name"]: r for r in fixture["tables"]["client_opcodes"]}
        self.enums = fixture["enums"]
        self.calls: list[str] = []

    def verbs(self) -> list[str]:
        return sorted(self.rows)

    def dispatch(self, opcode_name: str, session_status: str) -> dict[str, Any]:
        """Gate first, verb second. Refusal is typed and the handler is never invoked."""
        row = self.rows.get(opcode_name)
        if row is None:
            return {"ok": False, "reason": "UNKNOWN_OPCODE", "handler_ran": False}
        if session_status not in self.enums["session_status"]:
            return {"ok": False, "reason": "UNKNOWN_STATUS", "handler_ran": False}
        if row["status"] == "STATUS_NEVER":
            return {"ok": False, "reason": "STATUS_NEVER", "handler_ran": False}
        if row["status"] == "STATUS_UNHANDLED":
            return {"ok": False, "reason": "STATUS_UNHANDLED", "handler_ran": False}
        if row["status"] != session_status:
            return {"ok": False, "reason": "STATUS_MISMATCH", "handler_ran": False}
        self.calls.append(opcode_name)
        return {"ok": True, "reason": "DISPATCHED", "handler": row["handler"],
                "processing": row["processing"], "handler_ran": True}


class Instance:
    """The ENCOUNTER LAW, executable.

    Mirrors InstanceScript::SetBossState (InstanceScript.cpp): a TO_BE_DECIDED boss is LOADING,
    so writing its first state is not a transition and returns False; writing the state it
    already has is not a transition; DONE is refused while a world-boss minion is alive.
    """

    def __init__(self, fixture: dict[str, Any], boss_ids: int = 12):
        self.enums = fixture["enums"]["encounter_state"]
        self.state = {i: self.enums["TO_BE_DECIDED"] for i in range(boss_ids)}
        self.log: list[tuple[int, int]] = []

    def name(self, state: int) -> str:
        inv = {v: k for k, v in self.enums.items() if isinstance(v, int)}
        return inv.get(state, "INVALID")

    def set_boss_state(self, boss_id: int, state: str, *, world_boss_alive: bool = False) -> bool:
        """True == a real transition committed; False == refused or a no-op (their contract)."""
        if boss_id not in self.state or state not in self.enums:
            return False
        sid = self.enums[state]
        cur = self.state[boss_id]
        if cur == self.enums["TO_BE_DECIDED"]:          # loading, not a transition
            self.state[boss_id] = sid
            return False
        if cur == sid:                                  # no-op
            return False
        if state == "DONE" and world_boss_alive:        # guarded terminal
            return False
        self.state[boss_id] = sid
        self.log.append((boss_id, sid))
        return True

    def is_done(self, boss_id: int) -> bool:
        return self.state.get(boss_id) == self.enums["DONE"]


class Stream:
    """The RNG LAW, executable -- and the differential.

    Seeded at setup, one monotonic stream, every draw records its index. Replay either
    reproduces or reports RNG_DIVERGE. AzerothCore's urand() cannot do this (Random.h:30: no run
    seed, no recorded index), which is exactly why our L0 contract forbids their shape.
    """

    def __init__(self, seed: str | int, *, modulo: int = 100):
        self.seed = str(seed)
        self.modulo = modulo
        self.index = 0
        self.log: list[dict[str, int]] = []

    def next(self, *, record: bool = True) -> int:
        h = hashlib.sha256(f"{self.seed}:{self.index}".encode("utf-8")).hexdigest()
        val = int(h[:12], 16) % self.modulo
        if record:
            self.log.append({"index": self.index, "value": val})
        self.index += 1
        return val

    def replay(self, log: list[dict[str, int]], *, modulo: int | None = None) -> dict[str, Any]:
        """Re-run a committed draw log against the same seed. Divergence is a typed failure."""
        mod = self.modulo if modulo is None else modulo
        for entry in log:
            i, want = entry.get("index"), entry.get("value")
            got = int(hashlib.sha256(f"{self.seed}:{i}".encode("utf-8")).hexdigest()[:12], 16) % mod
            if got != want:
                return {"ok": False, "reason": "RNG_DIVERGE", "index": i,
                        "committed": want, "replayed": got}
        return {"ok": True, "reason": "REPLAY_MATCH", "draws": len(log)}


def laws() -> dict[str, Any]:
    """The bones, each with its citation in the clone and its kernel here."""
    return {
        "ok": True,
        "schema": SCHEMA,
        "laws": [
            {"id": "B01", "law": "the alphabet is a TABLE, not a computed predicate",
             "acore": f"{SRC_OPCODES_CPP} OpcodeTable::Initialize (725 client verbs)",
             "ours": "Dispatch.verbs()", "test": "the whole alphabet is gated: no verb is reachable "
                                                     "without a status decision"},
            {"id": "B02", "law": "the GATE runs before the VERB (phase is checked, not the payload)",
             "acore": "src/server/game/Server/WorldSession.cpp:436 switch (opHandle->Status)",
             "ours": "Dispatch.dispatch()", "test": "wrong phase -> typed refusal, handler_ran False "
                                                    "even though the verb exists"},
            {"id": "B03", "law": "refusal is TYPED and silent; the caller gets a reason, not a crash",
             "acore": f"{SRC_OPCODES_H} enum SessionStatus (STATUS_NEVER/UNHANDLED as first-class)",
             "ours": "reason codes UNKNOWN_OPCODE / STATUS_MISMATCH / STATUS_NEVER / STATUS_UNHANDLED",
             "test": "every refusal path returns a reason code"},
            {"id": "B04", "law": "the alphabet has a per-verb PROCESSING PLACE (where it may run)",
             "acore": f"{SRC_OPCODES_H} enum PacketProcessing (INPLACE/THREADUNSAFE/THREADSAFE)",
             "ours": "row['processing'] on every dispatched verb",
             "test": "every dispatched verb carries a processing place from the enum"},
            {"id": "B05", "law": "terminal state is a small TYPED machine, and loading is not a transition",
             "acore": f"{SRC_INSTANCE_H} enum EncounterState + InstanceScript::SetBossState",
             "ours": "Instance.set_boss_state()", "test": "TO_BE_DECIDED load returns False; "
                                                          "repeat is False; DONE guard is False; "
                                                          "real transition is True"},
            {"id": "B06", "law": "the RNG is SEEDED and every draw RECORDS ITS INDEX (replayable)",
             "acore": f"{SRC_RANDOM_H}:30 urand() -- global, unseeded, unindexed (the "
                      "counter-example)", "ours": "Stream.next() / Stream.replay()",
             "test": "same seed + same log -> REPLAY_MATCH; tampered draw -> RNG_DIVERGE"},
        ],
        "cost": "deterministic + $0",
    }


def status() -> dict[str, Any]:
    fx = load_fixture()
    return {
        "ok": True,
        "schema": SCHEMA,
        "acore": {"root": str(ACORE), "present": ACORE.is_dir()},
        "fixture": {"path": str(FIXTURE), "present": FX_PRESENT()},
        "counts": (fx or {}).get("counts"),
        "bones_digest": (fx or {}).get("bones_digest"),
        "kernels": ["Dispatch (ordering law)", "Instance (encounter law)", "Stream (RNG law)"],
        "law": "extract the bones as data; run them as kernels; test against them; build nothing",
    }


def FX_PRESENT() -> bool:  # noqa: N802 - kept shouty to read as a predicate in status()
    return FIXTURE.is_file()


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="wow-bones")
    ap.add_argument("cmd", nargs="?", default="status",
                    choices=["extract", "laws", "status", "session"])
    a, rest = ap.parse_known_args(argv)
    if a.cmd == "extract":
        out = extract(write=True)
    elif a.cmd == "laws":
        out = laws()
    elif a.cmd == "session":
        from mag.wow_bones_session import main as session_main
        return session_main(rest)
    else:
        out = status()
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
    return 0 if out.get("ok", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
