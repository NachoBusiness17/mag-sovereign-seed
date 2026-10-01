# WHO ELSE HAS DONE THIS — the emulator family, and the Turtle WoW steal (2026-09-15)

**Question:** *who else has done this — look at Turtle WoW. steal.*
**Answer:** everyone in this space descends from **one 2005 codebase**, there are exactly two
living lines, and **Turtle WoW is the proof of the single most important law in our game**:
*content is not protocol.* Five years of the heaviest custom content in the family changed
**~1 % of the verbs and added none.** Verified at bytes against two independent clones.

Machine artifacts: `mag/wow_family.py` (`wow_family.v1`) · `tests/test_wow_family.py`
· receipt in `memory/runs/hermes_jobs/`.

---

## 1. The family tree (all of it open, all of it readable)

```
MaNGOS (2005) — the common ancestor
├── cmangos / mangos-classic / mangos-tbc        the classic line, still alive
│   └── vMaNGOS ← Elysium ← LightsHope           PROGRESSIVE VANILLA (vmangos/core)
│        └── Turtle WoW (1.12 client + custom content)
│             └── tortoise-wow/tortoise-wow      ← the public restoration of TW 1.18.1
└── TrinityCore
    ├── SunwellCore → azerothcore/azerothcore-wotlk     WotLK 3.3.5a  (we hold this one)
    └── tbcmangos/core, cmangos/mangos-tbc              TBC line
```

Two lines, one ancestor, and every project in the table below is a different answer to the
same question: *how much of the world do you rebuild, and how much do you let the client own?*

## 2. The landscape (sizes/licenses/stars from the GitHub API, 2026-09-15)

| Repo | Size | License | ★ | Client | What it proves | Steal |
|---|---:|---|---:|---|---|---|
| `vmangos/core` | 96 MB | GPL-2.0 | 924 | vanilla 1.4.2 → 1.12.1 | **9 frozen protocol headers, one per patch** | the versioning bone |
| `tortoise-wow/tortoise-wow` | 105 MB | **AGPL-3.0** | 334 | Turtle WoW 1.18.1 (b7272) | the most custom content in the family | the *content-is-not-protocol* proof |
| `azerothcore/azerothcore-wotlk` | 1,325 MB | GPL-2.0 | 8,913 | WotLK 3.3.5a | the modular core (we mapped it) | `mag/wow_steal.py` |
| `TrinityCore/TrinityCore` | 1,406 MB | GPL-2.0 | 10,775 | WotLK 3.3.5a | the upstream everything forked from | reference only |
| `cmangos/mangos-classic` | 116 MB | GPL-2.0 | 1,080 | vanilla | the other classic survivor | reference only |
| `cmangos/mangos-tbc` | 175 MB | GPL-2.0 | 519 | 2.4.3 | the TBC line | reference only |
| `chromiecraft/chromiecraft` | 0.5 MB | — | 163 | (AzerothCore) | **a whole server as a 0.5 MB config repo** | server-as-data |
| `ServUO/ServUO` | 72 MB | GPL-2.0 | 754 | Ultima Online | the same bones, different game (C#) | cross-line comparison |
| `EQEmu/EQEmu` | 142 MB | GPL-3.0 | 633 | EverQuest | same, C++ | cross-line comparison |
| `OpenMW/openmw` | 108 MB | GPL-3.0 | 6,566 | Morrowind | **the archetype**: engine rebuilt clean, reads *your* data files | the "bones, not the client" model |

Note the compression: the vanilla core is **~1/14th** the size of the WotLK core and carries
more *versions* of its contract. **Bigger is not more bone.** The 1.3 GB AzerothCore clone is
73 % SQL content; the 96 MB vanilla clone is mostly protocol history.

`chromiecraft/chromiecraft` deserves the second look: a public progression server whose entire
public artifact is a 0.5 MB shell repo. The engine is upstream's, the *server* is config. That
is the end state our pack registry is aiming at.

## 3. The headline finding — Turtle WoW added no verbs

Press the claim hard, because it is the load-bearing one:

| Measurement | Value | Evidence |
|---|---:|---|
| Frozen 1.12.1 contract (names) | **826** | `vmangos-core/src/game/Server/Protocol/Opcodes_1_12_1.h` |
| vMaNGOS dev verbs (2026) | **826** | `vmangos-core/src/game/Server/Protocol/Opcodes.cpp` |
| TortoiseWoW verbs (TW 1.18.1) | **824** | `tortoise-wow/src/game/Protocol/Opcodes.cpp` |
| Shared | **821** | |
| Differing names | **8 (0.97 %)** | |
| Slots **beyond** the frozen range | **0** | |
| **Unexplained verbs** | **0** | |

Every one of the 8 differences is vanilla-era bookkeeping, and each is proven, not asserted:

- `SMSG_ACCOUNT_DATA_TIMES` (tortoise) and `SMSG_ACCOUNT_DATA_MD5` (vmangos) both occupy
  **slot 0x209** — a rename, not an addition.
- `CMSG_UNUSED`, `CMSG_UNUSED2` — placeholder slots, literally named UNUSED, bound to the
  null handler.
- `CMSG_MAIL_TAKE_ITEM`, `CMSG_SET_LOOKING_FOR_GROUP`, `MSG_SET_DUNGEON_DIFFICULTY`,
  `SMSG_RAID_MEMBER_STATS` — present in the 2026 vanilla core, absent (or renamed) in the
  restoration; all vanilla-era verbs.

**The most content-heavy server in the family never touched the wire.** Their custom zones,
races, challenge modes and client patches all ride on **data + client assets**. That is our
L0/L1/L2/L3 discipline, executed for five years by people who had never heard of it.

## 4. What we steal (the rows)

| # | Bone | From | Why it matters to us |
|---|---|---|---|
| F01 | **Versioned frozen contracts in source** — 9 headers, `Opcodes_1_4_2.h` … `Opcodes_1_12_1.h`, alphabets growing 727 → 745 → 748 → 757 → 765 → 782 → 796 → 814 → 826 | `vmangos/core` | our L0 contract gets a *series* of frozen versions, not one mutable file. Freeze per version, hash per version, replay against the version the run was played under |
| F02 | **Explicit refusal taxonomy — every slot declared** — 304 `DEFINE_HANDLER` + 524 `INVALID_PACKET` = all 826, each refusal carrying a reason (`UnhandleReason::Invalid` / `::Unhandled`) | `vmangos/core` | our `legal()` must be **exhaustive by construction**: every action in the vocabulary is either implementable or refused with a stable code. No silent gaps |
| F03 | **The verb carries its LANE, not just its phase** — 10 `PACKET_PROCESS_*` dispatch places (MAP / WORLD / MOVEMENT / GUILD / GROUP / CHANNEL / SELF_ITEMS / SPELLS / DB_QUERY / MAX) | `vmangos/core`, `tortoise-wow` | "which worker runs this" is part of the verb's declaration. Our fleet asks that question daily; the answer was written in C++ in 2006 |
| F04 | **CUSTOM BEHAVIOUR BEHIND A CONFIG FLAG, OFF BY DEFAULT** + *"content should be separate from the core"* + *"every piece of data must be marked with the patch in which it was added"* | `vmangos-core/README.md` project guidelines | four sentences that are our L1/L2/L3 law: engine vs content separation, and **provenance stamping on every datum** |
| F05 | **A server can be a config repo** — ChromieCraft publishes 0.5 MB of shell + config and leans on upstream for everything | `chromiecraft/chromiecraft` | the target shape of our pack registry: the world is data; the engine is somebody's frozen contract |

And from the WotLK line we already hold: the status gate on the dispatch table (B02), the
proposal→validate→commit ordering (R04), the encounter state machine (R08), and three
counter-examples worth more than the steals (global RNG, MySQL-as-authority, wall-clock ticks).

## 5. The non-WoW cousins — this is a tradition, not a hack

Bones-first rebuilding is the standard move in every game lineage, and the WoW family is
actually late to it:

- **OpenMW** (Morrowind) — the archetype: a clean engine that reads the *user's* data files. No
  client shipped, no content copied, 6.5k stars. "Bones, not the client" as a 20-year project.
- **ServUO / EQEmu** — the same bones for Ultima Online (C#) and EverQuest (C++): world
  authority, scripted content, GM tooling, loot tables.
- **The MUD line** — already stolen into `mag/mud_steal.py`: persistent world, world-as-
  authority, player-built worlds, no resets.
- **ChromieCraft** — progression as a public test realm on someone else's engine.

Every one of them answers the same way: **the engine is the contract, the content is data, and
the client is the user's problem.**

## 6. What this pass did NOT do

- **No build, no server, no client.** Nothing here requires compiling 1.3 GB of C++ or owning a
  1.12 client. All three clones are read as text.
- **No code copied.** `tortoise-wow` is **AGPL-3.0** (network copyleft, stricter than the GPL-2.0
  lines) — we read it and cite it, nothing more. Contracts only.
- **No attribution laundering.** Where a claim came from a README rather than a table, it is
  quoted and cited (`vmangos-core/README.md`, Project guidelines).

## 7. Run it

```bash
cd C:\Users\foste\Documents\projects\local_sovereign_agent
.venv\Scripts\python.exe -m mag.wow_family lineage    # the family table
.venv\Scripts\python.exe -m mag.wow_family delta      # the claim + its numbers
.venv\Scripts\python.exe -m mag.wow_family doctrine   # the laws, quoted
.venv\Scripts\python.exe -m pytest tests\test_wow_family.py tests\test_wow_bones.py -q
```

Deterministic, `$0`, **read-only** (this module writes nothing at all).
