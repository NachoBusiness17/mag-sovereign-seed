# WOW → OUR GAME — AzerothCore self-steal map (2026-09-15)

**Question it answers:** *this is a huge project — how can we map it to our game?*
**Answer in one line:** you do not map 10,409 files. You map the **six L0 slots**, and you
classify everything else as either **content** (data, with provenance) or **scale machinery we
refuse to build**. A huge engine maps onto six slots; the file count is not the shape.

| | |
|---|---|
| Territory | `C:\Users\foste\Documents\projects\azerothcore-wow` (sibling of the harness root) |
| Upstream | `https://github.com/azerothcore/azerothcore-wotlk.git` |
| **Rename gotcha** | the old `github.com/azerothcore/azerothcore-wow.git` **404s** — this is why the empty stub in the repo (created 2026-09-02) never fetched. Upstream renamed the repo to `azerothcore-wotlk`. |
| HEAD at clone | `f68a9759bdd11e773876c6bc12fd0c74866422c2` (2026-09-15, shallow, master) |
| On disk | 1,210 MB — `.git` 331 MB · `data/` 825 MB · `src/` 32 MB |
| Files | 10,409 tracked · 7,653 SQL (73 %) · 1,212 `.cpp` · 972 `.h` |
| C++ size | game 83,464 LOC · scripts 62,676 · common 24,600 · shared 12,718 · tools 9,525 · database 8,839 · apps 3,136 |
| License | **GPL-2.0** — we copy no code. Contracts only (fleet law), cited by path + symbol. |
| Machine artifact | `mag/wow_steal.py` (`wow_steal.v1`) — `map` / `verify` / `receipt` / `status` |
| Receipt | `memory/runs/hermes_jobs/wow_steal_20260916T002918Z.json` |
| Verification | **15/15 rows, 33/33 citations verified at bytes** · `map_digest ec40594529b7` |

None of the 15 rows is folklore: `verify` reads each cited file in the local clone and asserts
the symbol is present, recording its `sha256[:12]`. A row whose symbol is missing **fails**.
That is the whole point — the map is a hypothesis, the byte check is the receipt.

> **Correction, 2026-09-15 (byte check caught itself):** the first pass counted `DEFINE_HANDLER(`
> occurrences — 726 and 588 — which silently included the two `#define` macro lines. The real
> dispatch table is **725 client + 587 server = 1,312 entries** (`grep -c '/\*0x'` = 1,312), fixed
> here and in `mag/wow_steal.py`. Numbers from a report are not numbers from bytes.

---

## 1. The method (what makes this tractable)

1. **Size the territory first** (bytes, file census, LOC by subsystem). AzerothCore is
   73 % SQL and a third of the C++ is content scripts — the "huge project" is mostly *data*
   and *content*, not machinery.
2. **Map only against the contract you already have.** Our L0 universal contract has exactly
   six functions (`setup` / `turn` / `move` / `legal` / `evaluate` / `render`) + a seeded RNG
   protocol + a verifier vocabulary. Ask of each subsystem: **which of the six slots does this
   fill?** Anything that fills none is content or infrastructure.
3. **Give every row a stance**, or the map becomes a wish list:
   `steal` (take the contract) · `adapt` (take the shape, change the authority) ·
   `reject` (read it, name exactly why we refuse it) · `content` (belongs in L2/L3 as data).
4. **Cite path + symbol, not prose.** A claim you cannot byte-verify is not a claim.
5. **Read the enemy's design as the argument for yours.** The rejects here (global RNG, MySQL
   as authority, wall-clock ticks) are the clearest available arguments for our Hologram /
   verkle-chain / knot-index design. AzerothCore is the working counter-example.

## 2. The map — 15 rows

| # | L0 slot | AzerothCore mechanism | Stance | We take | We leave |
|---|---|---|---|---|---|
| R01 | `legal(state, actor)` | client-opcode table, `OpcodeTable::Initialize`, **725** client opcodes | steal | legal moves as a **frozen table** with a per-entry status gate; hash the table = contract version | the 725-name namespace; a real client owns it, ours is ours |
| R02 | `render(state)` | **587** server opcodes, `ValidateAndSetServerOpcode` | steal | render as a **second hashable table** — replay through a pinned render table cannot drift | packet serialization, ARC4, compression |
| R03 | `turn(state, actor)` | `switch (opHandle->Status)` — gate the verb *before* reading it | steal | turn legality lives on the **dispatch table**, refusal is silent + typed → our `ILLEGAL_TURN` | the DoS throttle (a budget is not a shield) |
| R04 | `move(state, actor, action)` | `Spell::CheckCast` — server re-validates range/LOS/reagents/cooldown/power (9,534 LOC in `Spell.cpp`) | steal | the client's request is a **proposal**; order = check → cost → resolve → commit (= `game_emulator.act`) | the 100+ `SpellCastResult` codes as public vocabulary |
| R05 | transition / step | `Map::Update(t_diff, s_diff)` — per-map step, elapsed time as an *argument* | adapt | step ownership is per-container; `(state, diff) → state` = `game_world.set_state` | wall-clock diff as authority — a clock makes replay impossible; our diff is the **knot index** |
| R06 | (heartbeat) | `World::Update(diff)` + `WUPDATE` timers: one heartbeat, many cadences | adapt | one heartbeat / many registered periods; world advances with no player present | uptime as proof; our proof is `world_status()`, not a clock |
| R07 | RNG protocol | `urand()` / `rand32()` / `rand_chance()` — process-global, unseeded, unrecorded | **reject** | the **taxonomy** of draw sites (loot / crit / spawn / roll) | the implementation. Unreplayable ⇒ divergence can never be proven. Our law: seed at `setup`, one monotonic stream, record the index, divergence = `RNG_DIVERGE` |
| R08 | `evaluate(state)` + L4 lineage | `InstanceScript::SetBossState(id, EncounterState)` — NOT_STARTED / IN_PROGRESS / FAIL / DONE + `IsBossDone()` | steal | this **is** our verdict vocabulary, and instance id = **lineage** (two campaigns never silently merge) | encounter credit tables, raid lockouts |
| R09 | L3 pack (data) | loot = runtime **table** (`LootMgr`, `roll_chance_f`) | content | packs are tables + a thin delta over an engine; the draw is the only random thing and it is **recorded** | not one loot row; 825 MB of Blizzard-derived data is provenance poison for an L2 static |
| R10 | L1↔L3 seam | `modules/` auto-load via `AC_ADD_SCRIPTS_LIST`; 598 scripts in `src/server/scripts` | steal | content auto-discovered against a generated registry — **adding a pack never edits the engine**; name the seventh (tile) bridge explicitly | C++ link-time registration; our registry is data, no compiler required |
| R11 | L2 static | `DBCStores` — typed static tables loaded at boot | content | proof the L2 layer is real and sits **under** the engine | the tables; our statics carry their own provenance + uncertainty, a DBC carries neither |
| R12 | world authority | truth in MySQL + in-memory caches (`ObjectMgr`, `CharacterCache`) | **reject** | the real separation: static world data ≠ character state, loaded/invalidated differently | the store. RDBMS + cache is not content-addressed ⇒ cannot be an authority. Ours: **the world state IS the verkle protocol**; a change is real only if it commits |
| R13 | verifier vocabulary | Warden + `AntiDOS` policy: client is hostile by default, answer is a typed policy | adapt | a verifier **fails loudly with a stable reason code** (`ILLEGAL_MOVE` / `ILLEGAL_TURN` / `RNG_DIVERGE`) | the client scanner — we don't inspect a client we refuse to believe |
| R14 | trust boundary | `authserver` (session key) ≠ `worldserver` (`SetInitialWorldSettings`); the world never takes an identity claim from the wire | steal | identity and world are **different authorities** = our switchboard: model text proposes, only the switchboard/effect broker authorizes effects | SRP6 / session-key / realm-list protocol |
| R15 | scale machinery | Grids, `ObjectAccessor`, map threading, map/vmap/mmap extractors | **reject** | one honest lesson: "MMO scale" is spatial partitioning + timing, not gameplay — it is most of the file count and buys nothing we buy | all of it. Our world proves **37 entities on a self-verifying root**; our scale axis is verified transitions, not sockets |

**Stance ledger:** 7 steal · 3 adapt · 3 reject · 2 content.

## 3. The five things actually worth taking

1. **The gate belongs on the dispatch table, not in the verb** (R03) — status is checked before
   the request is interpreted; refusals are typed and silent.
2. **Legal moves are a frozen, hashable table** (R01/R02) — **725 client / 587 server** verbs is
   the largest written-down legal-move alphabet we can study. Freeze ours the same way and the
   contract gets a version hash our verifier can bind to.
3. **Every request is a proposal, re-validated server-side** (R04) — the enforcement ordering
   (check → cost → resolve → commit) is what `game_emulator.act` should state explicitly.
4. **Terminal predicates are small typed state machines** (R08) — `EncounterState` maps 1:1 onto
   our verdict vocabulary + L4 instance lineage.
5. **Engine and content are separate registries** (R10/R11) — 598 auto-loaded scripts and a DBC
   layer are the working proof that packs are data and never touch the engine.

## 4. The three things we looked at and refused

- **Global mutable RNG** (R07) — the counter-example that justifies our whole RNG protocol.
- **MySQL + caches as world authority** (R12) — the counter-example that justifies the verkle chain.
- **Wall-clock ticks as time authority** (R05) — the counter-example that justifies knot-index replay.

These are worth more than the steals. They are the strongest available arguments for the design
we already committed to, written by 15 years of production code.

## 5. What this map is NOT

- **Not a build.** Building AzerothCore = MySQL 8.4, Boost, OpenSSL, CMake/vcpkg, ~1 h+ compile,
  plus a licensed 3.3.5a client (~15 GB) for maps/DBCs. `docker-compose.yml` carries 7 services.
  Nothing in this map requires it; we read source only.
- **Not a merge, not a fork, not a vendor.** GPL-2.0 + contracts-only law. No code is copied.
- **Not registered** in `configs/steal_protocol_repos.yaml` (that forest is agent-orchestrator
  repos, `steal_contracts_only`, dest `mine/raw/steal_protocol/`). This is a game-line steal;
  registering it there is an operator call, not a default.

## 6. Open joins (honest, unfinished)

- The **L4 instance schema** is still described, not built — R08 gives it a vocabulary, not a file.
- Our **legal-move table** does not exist yet as a frozen, hashed artifact. That is R01/R02's
  actual work item, and it is the cheapest real win on this page.
- The **seven engine families** still have the tile-matching bridge unnamed (R10), so it will
  read as a missing organ to the next mapper.

## 7. The bones — extracted as data, run as laws, tested

The map says *what to take*. `mag/wow_bones.py` (`wow_bones.v1`) takes it: it parses the real
dispatch table and enums straight out of the clone into a fixture with a contract digest, then
runs them as three kernels so the claims above are falsifiable.

| | |
|---|---|
| Fixture | `memory/runs/wow_bones/bones.json` (229,534 B) |
| `bones_digest` | `efeb905b4d178d1ad9a5e20fc8ee409d568b84c8c08527a7c96f538e354739a6` |
| Extracted | **725** client verbs · **587** server verbs · **6** session statuses · **3** processing places · **6** encounter states |
| Kernels | `Dispatch` (ordering law B02) · `Instance` (encounter law B05) · `Stream` (RNG law B06) |
| Tests | `tests/test_wow_bones.py` — **12 passed**; subset `pytest -k "game or wow or steal"` = **106 passed, 1 skipped** |
| Receipt | `memory/runs/hermes_jobs/wow_bones_20260916T010936Z.json` |

The kernels exist to make the theft *checkable*, not to describe it:

- **`Dispatch`** — the ordering law. `dispatch(verb, phase)` evaluates the gate on the table
  first, so a verb that exists is refused with a typed reason and `handler_ran: False`.
  `test_gate_runs_before_the_verb` asserts the handler provably never fired. All 725 verbs are
  gated; the partition is total (433 dispatchable / 292 `STATUS_NEVER`) and unpinned-in-tests it
  would drift silently.
- **`Instance`** — the encounter law, taken from `InstanceScript::SetBossState` including the two
  rules that make it interesting: a `TO_BE_DECIDED` load **is not a transition** (returns false),
  and `DONE` is refused while a world-boss minion lives.
- **`Stream`** — the RNG law and the differential. Same seed + same log → `REPLAY_MATCH`; a
  tampered draw → `RNG_DIVERGE` at the exact index. This is the property AzerothCore's
  `urand()` cannot have, and the reason our L0 contract exists.

Source-of-truth hashes recorded in the fixture: `Opcodes.cpp fdddf2806193`,
`Opcodes.h 9109ea4d2abd`, `InstanceScript.h f63278dff6a4` — clone HEAD `f68a975`.

One failure earned its keep during construction: the on-disk fixture's digest stopped matching a
fresh extraction the moment the enum parser was fixed, and the test caught it instead of us.

## 8. Run it

```bash
cd C:\Users\foste\Documents\projects\local_sovereign_agent
.venv\Scripts\python.exe -m mag.wow_steal map       # the 15 rows
.venv\Scripts\python.exe -m mag.wow_steal verify    # byte-verify every citation
.venv\Scripts\python.exe -m mag.wow_steal receipt   # verify + file the receipt
.venv\Scripts\python.exe -m mag.wow_bones extract   # parse the clone -> bones.json + digest
.venv\Scripts\python.exe -m mag.wow_bones laws      # the 6 extracted laws, each cited
.venv\Scripts\python.exe -m pytest tests\test_wow_bones.py -q
```

Contract-only, deterministic, `$0`, read-only apart from the two receipts/fixture writes.
