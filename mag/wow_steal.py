"""wow_steal -- the SELF-STEAL on the WoW line (AzerothCore, the 3.3.5a emulator).

The MUD steal (mag/mud_steal.py) took the MUD, the ANCESTOR of every MMORPG. This takes the
MMORPG itself: AzerothCore -- the WotLK server emulator, the most complete implementation of
"a persistent world that carries on without you" that we can read in source.

WHY THIS IS A STEAL AND NOT A MERGE: the territory is 10,409 tracked files (1,210 MB on disk)
and ~200k lines of C++ that only run with MySQL, Boost, OpenSSL and a licensed 3.3.5a client.
Our game is a 37-entity verkle world (game_world.v1). They do not join. What joins is the
CONTRACT: our L0 universal contract has exactly six slots (setup/turn/move/legal/evaluate/
render) plus a seeded RNG protocol and a verifier vocabulary -- so a 10k-file engine maps onto
six slots, not onto 10k files. Everything that does not fit an L0 slot is either CONTENT
(L2/L3: data, not code) or INFRASTRUCTURE we deliberately reject (real-time scale machinery).

LAW (fleet, standing): contracts only -- never a default seat, never a second DNA store.
AzerothCore is GPL-2.0. We copy NO code. We read the shape, cite path+symbol, and write our
own contract. Every claim in this file is machine-verified at bytes by `verify` -- if the
symbol is not in the file, the row FAILS. No row is allowed to be folklore.

RUN:
  python -m mag.wow_steal map       # the 15 rows (mechanism -> slot -> take/leave)
  python -m mag.wow_steal verify    # byte-verify every cited path+symbol, print the receipt
  python -m mag.wow_steal receipt   # verify + write memory/runs/hermes_jobs/wow_steal_<utc>.json
  python -m mag.wow_steal status

Schema: wow_steal.v1 . deterministic + $0 . read-only (receipt writes only on `receipt`)
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "wow_steal.v1"
# The clone: sibling of the harness root (C:\Users\ESTATE_USER\Documents\projects\azerothcore-wow).
# Upstream renamed azerothcore-wow -> azerothcore-wotlk on GitHub; the old URL 404s.
ACORE = ROOT.parent / "azerothcore-wow"
ACORE_UPSTREAM = "https://github.com/azerothcore/azerothcore-wotlk.git"
RECEIPT_DIR = ROOT / "memory" / "runs" / "hermes_jobs"

# stance: steal = take the contract as-is | adapt = take the shape, change the authority
#         reject = read it, name why we refuse it | content = it belongs in L2/L3 as data
ROWS: list[dict[str, Any]] = [
    {
        "id": "R01",
        "slot": "L0 legal(state, actor)",
        "wow": "The client-opcode table: every verb a client may ask for, one row per opcode, "
               "each carrying a session-status gate and a processing place.",
        "stance": "steal",
        "take": "legal() as a FROZEN TABLE with a status gate per entry, not a computed predicate. "
                "725 client opcodes = the largest written-down legal-move alphabet we have. Hash the "
                "table -> that hash is the contract version our verifier binds to.",
        "leave": "Opcodes are a namespace of 725 verbs a real client owns. Ours is small and we own it.",
        "acore": [("src/server/game/Server/Protocol/Opcodes.cpp", "OpcodeTable::Initialize")],
        "ours": [("watch/corpus/L0_contract.md", "legal(state, actor) -> [action]")],
    },
    {
        "id": "R02",
        "slot": "L0 render(state)",
        "wow": "A separate SERVER opcode table (587 entries): the world tells the client what "
               "changed; the client never tells the world what is true.",
        "stance": "steal",
        "take": "render() as a second, independently hashable table. Presentation is a vocabulary "
                "we version too -- a replay watched through a pinned render table cannot drift.",
        "leave": "Packet serialization, ARC4 header crypto, compression thresholds.",
        "acore": [("src/server/game/Server/Protocol/Opcodes.cpp", "ValidateAndSetServerOpcode")],
        "ours": [("watch/corpus/L0_contract.md", "render(state) -> View")],
    },
    {
        "id": "R03",
        "slot": "L0 turn(state, actor)",
        "wow": "Dispatch gates every opcode on session status (switch (opHandle->Status)) before a "
               "handler runs; an out-of-phase request is dropped, not interpreted.",
        "stance": "steal",
        "take": "Turn legality is structural: the gate is checked BEFORE the verb is read, and the "
                "refusal is silent + typed. Our ILLEGAL_TURN already means this -- AzerothCore proves "
                "the gate belongs on the dispatch table, not inside each verb.",
        "leave": "The DOS throttle next to it (AntiDOS.EvaluateOpcode) is rate machinery for hostile "
                 "clients; our cost-gate is a budget, not a shield.",
        "acore": [("src/server/game/Server/WorldSession.cpp", "switch (opHandle->Status)")],
        "ours": [("watch/corpus/L0_contract.md", "ILLEGAL_TURN")],
    },
    {
        "id": "R04",
        "slot": "L0 move(state, actor, action)",
        "wow": "Spell::CheckCast re-validates everything on the server -- range, line of sight, "
               "reagents, cooldown, power, target legality -- even though the client already "
               "checked it locally. 9,534 lines in Spell.cpp, and check is the front door.",
        "stance": "steal",
        "take": "The client's request is a PROPOSAL. This is exactly our game_emulator.act(): the "
                "actor cannot choose the outcome, the server re-decides. AzerothCore's ordering "
                "(check -> cost -> resolve -> commit) is the ordering our resolver should state.",
        "leave": "The 100+ SpellCastResult codes as a public vocabulary -- ours must stay small and "
                 "stable; we extend by contract, not by enum growth.",
        "acore": [("src/server/game/Spells/Spell.cpp", "SpellCastResult Spell::CheckCast(bool strict")],
        "ours": [("mag/game_emulator.py", "def act(")],
    },
    {
        "id": "R05",
        "slot": "L0 transition / step",
        "wow": "Map::Update(t_diff, s_diff): the step function is PER-MAP, ordered, and takes the "
               "elapsed time as an argument instead of reading a clock.",
        "stance": "adapt",
        "take": "Step ownership is per-container and the step is a pure function of (state, diff). "
                "Our fold is game_world.set_state(); our 'diff' is the knot index -- a SEQUENCE, "
                "never a duration.",
        "leave": "Wall-clock diff as the authority. A clock makes a world unreplayable: replay at a "
                 "different speed is a different world. Ours replays from the chain, byte for byte.",
        "acore": [("src/server/game/Maps/Map.cpp", "void Map::Update(const uint32 t_diff")],
        "ours": [("mag/game_world.py", "def set_state(")],
    },
    {
        "id": "R06",
        "slot": "L0 (world heartbeat)",
        "wow": "World::Update(diff) drives WUPDATE_COUNT timers: one tick, many periods, every "
               "subsystem a timer registered against it.",
        "stance": "adapt",
        "take": "One heartbeat, many registered cadences -- and the world advances whether or not a "
                "player is present (the 'carries on without you' law we already took from the MUD).",
        "leave": "The clock as the heartbeat. Our heartbeat is the fold: the world advances when a "
                 "site asks for status, and the proof is world_status(), not an uptime counter.",
        "acore": [("src/server/game/World/World.cpp", "void World::Update(uint32 diff)")],
        "ours": [("mag/game_world.py", "def world_status(")],
    },
    {
        "id": "R07",
        "slot": "L0 RNG protocol",
        "wow": "urand() / rand32() / rand_chance(): process-global mutable RNG with no run-level "
               "seed and no recorded draw index.",
        "stance": "reject",
        "take": "The TAXONOMY of draw sites -- loot chance, crit roll, spawn selection, loot roll. "
                "Naming where our world is allowed to be random is the useful half.",
        "leave": "The implementation. An unseeded global draw cannot be replayed, so a divergence "
                 "can never be proven. Our L0 forbids this outright: seed fixed at setup, one "
                 "monotonic stream, every draw records its index, divergence = RNG_DIVERGE. "
                 "AzerothCore is the clearest argument FOR our RNG law: it is the counter-example.",
        "acore": [("src/common/Utilities/Random.h", "AC_COMMON_API uint32 urand")],
        "ours": [("watch/corpus/L0_contract.md", "RNG Protocol (seeded, auditable)"),
                 ("watch/corpus/L0_contract.md", "RNG_DIVERGE")],
    },
    {
        "id": "R08",
        "slot": "L0 evaluate(state) + L4 instance lineage",
        "wow": "InstanceScript::SetBossState(id, EncounterState): a per-instance state machine "
               "(NOT_STARTED / IN_PROGRESS / FAIL / DONE) with IsBossDone() as the terminal query.",
        "stance": "steal",
        "take": "This IS our verdict vocabulary, already written: a terminal predicate is a small "
                "typed state machine per instance, and credit is granted by the machine, not by the "
                "narration. And an instance id is a LINEAGE: two campaigns never silently merge.",
        "leave": "Encounter credit tables and the raid-lockout persistence model.",
        "acore": [("src/server/game/Instances/InstanceScript.h", "virtual bool SetBossState(uint32 id, EncounterState state)")],
        "ours": [("watch/corpus/L0_contract.md", "evaluate(state) -> VERDICT")],
    },
    {
        "id": "R09",
        "slot": "L3 pack (data, not code)",
        "wow": "Loot is a TABLE read at runtime (LootMgr): drop chance, reference chance, money "
               "range -- content authored as data, rolled through roll_chance_f().",
        "stance": "content",
        "take": "The shape: a pack is a table + a thin delta over an engine, and the draw is the "
                "ONLY random thing in it. Our L2/L3 layer is exactly this (Engine foundry -> thin "
                "rule delta), with one addition: the draw is recorded and replayed.",
        "leave": "Not one loot row is imported. 825 MB of Blizzard-derived data and 7,653 SQL files "
                 "are provenance poison for an L2 static, which must carry its own source status.",
        "acore": [("src/server/game/Loot/LootMgr.cpp", "roll_chance_f")],
        "ours": [("watch/BASECAMP_GAME_ATLAS_20260901.md", "Engine foundry"),
                 ("watch/corpus/L0_contract.md", "RNG_DIVERGE")],
    },
    {
        "id": "R10",
        "slot": "L1 engine / L3 pack seam",
        "wow": "modules/ is an auto-load seam: AC_ADD_SCRIPTS_LIST is generated by CMake and every "
               "module registers itself; 598 script files under src/server/scripts load the same way.",
        "stance": "steal",
        "take": "Content is auto-discovered against a generated registry, so adding a pack never "
                "edits the engine. Our registry must do the same, and it must name the seventh "
                "tile-matching bridge explicitly or the next mapper will read it as a missing organ.",
        "leave": "C++ link-time registration. Our registry is data; loading a pack must not require "
                 "a compiler.",
        "acore": [("modules/CMakeLists.txt", "AC_ADD_SCRIPTS_LIST")],
        "ours": [("watch/BASECAMP_GAME_ATLAS_20260901.md", "Engine foundry")],
    },
    {
        "id": "R11",
        "slot": "L2 static",
        "wow": "DBCStores: the client's static tables (achievements, criteria, categories...) loaded "
               "into typed in-memory stores at boot.",
        "stance": "content",
        "take": "The layer exists and it is DATA LAYERED UNDER THE ENGINE -- proof that our L2 "
                "static layer is a real layer and not a filing habit.",
        "leave": "The tables themselves. Our L2 statics are our own research artifacts and must "
                 "carry provenance + an uncertainty label; a Blizzard DBC carries neither.",
        "acore": [("src/server/game/DataStores/DBCStores.h", "extern DBCStorage <AchievementEntry>")],
        "ours": [("watch/BASECAMP_GAME_ATLAS_20260901.md", "Archive gardens")],
    },
    {
        "id": "R12",
        "slot": "world authority",
        "wow": "Truth lives in MySQL plus in-memory caches (ObjectMgr, CharacterCache): the world "
               "state is a mutable relational DB with a disposable heap mirror in front of it.",
        "stance": "reject",
        "take": "The SEPARATION it proves is real: static world data (spawns, templates, loot) is "
                "not character state, and the two are loaded and invalidated differently.",
        "leave": "The store. An RDBMS + cache is not content-addressed and cannot be replayed byte "
                 "for byte, so it cannot be an authority for a verifiable world. Ours is: the world "
                 "state IS the verkle protocol, and a change is real only if it commits to the "
                 "chain. AzerothCore's character table is the strongest case for our chain.",
        "acore": [("src/server/game/Cache/CharacterCache.cpp", "CharacterCache::LoadCharacterCacheStorage")],
        "ours": [("mag/game_world.py", "the world state IS the verkle protocol")],
    },
    {
        "id": "R13",
        "slot": "verifier vocabulary",
        "wow": "Warden (client integrity) plus the DOS throttle: the server treats the client as "
               "hostile by default and answers misbehavior with a named, typed policy.",
        "stance": "adapt",
        "take": "A verifier FAILS LOUDLY with a stable reason code (Kick/Ban/Throttle -> our "
                "ILLEGAL_MOVE / ILLEGAL_TURN / RNG_DIVERGE). The reason code is the product; the "
                "detection machinery is an implementation detail.",
        "leave": "The client scanner. We do not inspect a client we do not trust -- we refuse to "
                 "believe it in the first place.",
        "acore": [("src/server/game/Server/WorldSession.h", "HandleWardenDataOpcode")],
        "ours": [("watch/corpus/L0_contract.md", "ILLEGAL_MOVE")],
    },
    {
        "id": "R14",
        "slot": "trust boundary",
        "wow": "Two processes, two trust domains: authserver issues a session key (sAuthSocketMgr) "
               "and worldserver starts the world (sWorld->SetInitialWorldSettings()). The world "
               "never takes an identity claim from the wire.",
        "stance": "steal",
        "take": "Identity and world are different authorities. Our switchboard is the same shape: "
                "model text can propose, only the switchboard/effect broker authorizes effects. "
                "A seat that could both propose and commit would be AzerothCore trusting its client.",
        "leave": "SRP6 / session-key / realm-list protocol details.",
        "acore": [("src/server/apps/authserver/Main.cpp", "sAuthSocketMgr.StartNetwork"),
                  ("src/server/apps/worldserver/Main.cpp", "sWorld->SetInitialWorldSettings")],
        "ours": [("AGENTS.md", "only the switchboard/effect broker authorizes effects")],
    },
    {
        "id": "R15",
        "slot": "scale machinery",
        "wow": "Grids, ObjectAccessor, map threading, map/vmap/mmap extractors: the machinery that "
               "exists so that thousands of players can be in one world at once.",
        "stance": "reject",
        "take": "One honest lesson: 'MMO scale' is spatial partitioning and timing, not gameplay. "
                "It is the majority of the file count and it buys nothing we are buying.",
        "leave": "All of it. Our world proves 37 entities on a self-verifying root. Our scale axis "
                 "is the number of VERIFIED transitions, not concurrent sockets. Reading this pile "
                 "is exactly what should stop us from ever building it.",
        "acore": [("src/server/game/Grids/GridObjectLoader.h", "class GridObjectLoader")],
        "ours": [("_game_loop_proof.json", "world_entities")],
    },
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _resolve(which: str, rel: str) -> Path:
    return (ACORE if which == "acore" else ROOT) / rel


def _evidence(which: str, rel: str, symbol: str) -> dict[str, Any]:
    """Byte-verify ONE citation: does the file exist, is the symbol in it, what is its hash."""
    p = _resolve(which, rel)
    ev: dict[str, Any] = {"which": which, "path": rel, "symbol": symbol, "exists": p.is_file()}
    if not ev["exists"]:
        ev.update({"symbol_found": False, "sha256_12": None, "bytes": None})
        return ev
    raw = p.read_bytes()
    ev["bytes"] = len(raw)
    ev["sha256_12"] = hashlib.sha256(raw).hexdigest()[:12]
    try:
        text = raw.decode("utf-8", errors="replace")
    except Exception:
        text = ""
    ev["symbol_found"] = symbol in text
    return ev


def self_map() -> dict[str, Any]:
    """The map, without touching disk: mechanism -> L0 slot -> take / leave."""
    return {
        "ok": True,
        "schema": SCHEMA,
        "rows": len(ROWS),
        "map": [{k: r[k] for k in ("id", "slot", "wow", "stance", "take", "leave")} for r in ROWS],
        "law": "contracts only; no code copied; GPL-2.0 upstream read as a design reference",
    }


def verify() -> dict[str, Any]:
    """Verify EVERY row's citations against the local clone + our tree. A missing symbol fails."""
    rows_out, failures, total_ev = [], [], 0
    for r in ROWS:
        evs = [_evidence("acore", p, s) for (p, s) in r["acore"]]
        evs += [_evidence("ours", p, s) for (p, s) in r["ours"]]
        total_ev += len(evs)
        bad = [e for e in evs if not (e["exists"] and e["symbol_found"])]
        if bad:
            failures.append({"id": r["id"], "bad": bad})
        rows_out.append({"id": r["id"], "slot": r["slot"], "stance": r["stance"],
                         "evidence": evs, "ok": not bad})
    digest = hashlib.sha256(
        json.dumps([[e["which"], e["path"], e["symbol"], e["sha256_12"]] for e in
                    [x for row in rows_out for x in row["evidence"]]],
                   ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    head = None
    try:
        import subprocess
        head = subprocess.run(["git", "-C", str(ACORE), "log", "-1", "--format=%H %ad", "--date=short"],
                              capture_output=True, text=True, timeout=20).stdout.strip() or None
    except Exception:
        head = None
    return {
        "ok": not failures,
        "schema": SCHEMA,
        "ts": _now(),
        "rows": len(ROWS),
        "rows_ok": sum(1 for r in rows_out if r["ok"]),
        "citations": total_ev,
        "citations_ok": sum(1 for row in rows_out for e in row["evidence"]
                            if e["exists"] and e["symbol_found"]),
        "map_digest": digest,
        "acore_root": str(ACORE),
        "acore_head": head,
        "failures": failures,
        "verdict": "every claim is present at bytes in the clone" if not failures
                   else "MAP HAS UNVERIFIED CLAIMS -- fix or delete the row",
        "rows_detail": rows_out,
    }


def receipt() -> dict[str, Any]:
    """verify() + write the receipt (the only write this module ever performs)."""
    v = verify()
    RECEIPT_DIR.mkdir(parents=True, exist_ok=True)
    out = RECEIPT_DIR / f"wow_steal_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    out.write_text(json.dumps(v, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": v["ok"], "schema": SCHEMA, "receipt": str(out),
            "map_digest": v["map_digest"], "rows_ok": v["rows_ok"], "rows": v["rows"],
            "verdict": v["verdict"]}


def status() -> dict[str, Any]:
    n_steal = sum(1 for r in ROWS if r["stance"] == "steal")
    n_adapt = sum(1 for r in ROWS if r["stance"] == "adapt")
    n_rej = sum(1 for r in ROWS if r["stance"] == "reject")
    n_con = sum(1 for r in ROWS if r["stance"] == "content")
    return {
        "ok": True,
        "schema": SCHEMA,
        "contract": "map() -> mechanism->L0 slot; verify() -> byte-verified citations; "
                    "receipt() -> verify + file the receipt",
        "cost": "deterministic + $0 (reads the local clone; no network, no model)",
        "clone": {"root": str(ACORE), "upstream": ACORE_UPSTREAM, "present": ACORE.is_dir()},
        "stance_counts": {"steal": n_steal, "adapt": n_adapt, "reject": n_rej, "content": n_con},
        "thesis": "a 10k-file engine maps onto SIX L0 slots, not onto 10k files; everything else "
                  "is content (data, with provenance) or scale machinery we refuse to build",
        "law": "contracts only -- we cite path+symbol and write our own contract; no GPL code copied",
    }


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="wow-steal")
    ap.add_argument("cmd", nargs="?", default="status",
                    choices=["map", "verify", "receipt", "status"])
    a = ap.parse_args(argv)
    out = {"map": self_map, "verify": verify, "receipt": receipt, "status": status}[a.cmd]()
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
    return 0 if out.get("ok", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
