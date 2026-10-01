# GAME PLATFORM BASECAMP — THE WOW CLONE + GWAP BACKEND PROGRAM

*Raised 2026-09-29 by zcode-seat, on operator order: "build it bro. set up basecamp go wide" / "go full width and plan it out" / "selfsteal first... self steal deep for a moonshot." Companion research: `watch/inbox/GWAP_BACKEND_RESEARCH_20260929.md`. This file is the program's home; every lane claims here.*

## THE CHARTER (operator's words, decoded once)

1. **Make a WoW clone** — the forcing project: an MMO demands every backend service exist under load.
2. **The GWAP is the backend** — external game developers build on our verification layer: agreement-as-anti-cheat, frozen-tape provable play, honest meters.
3. **Roblox without the child predators** — federated small servers, receipt-ledger payouts, export-everything ownership, consent-named play-as-work.
4. **Godot is the training engine — early Grok days.** Build, own, imperfect. Use reveals what's missing; the informed choice comes AFTER use. Nobody picks-and-goes (the Hermes lesson: he needed to go through all the interfaces).
5. **Self-steal first** — we've been building toward this since August. Mine the estate before researching outsiders.

## THE LADDER (each rung reveals the next missing piece)

| Rung | What | State | Reveals |
|---|---|---|---|
| B0 | Mountain slice (Godot learns; water+flock one loop) | DONE 2026-09-29, PLAYED-by-no-one-yet | engine basics |
| B1 | Revive CMaNGOS: submodule + build + world DB + client-data extract | RECON RUNNING (toolchain gap found: no compiler/CMake/MySQL on box) | build debt, snapshot age, DB shape |
| B2 | Godot client: realmd auth + movement opcodes into CMaNGOS | not started | protocol truth, netcode ownership question |
| B3 | GWAP payload v0 on the MUD (intent/report/witness, append-only JSONL) | not started | whether the backend exists before devs arrive |
| B4 | First external dev = Adam; invariant: backend works without estate help | not started | the actual platform roadmap |
| B5 | Informed choices: engine, netcode, DB, UE5-vs-Godot noir endgame | deferred BY DESIGN | everything above |

## THE LANES (claim by editing your row; do not delete others)

| Lane | Seat | State | Receipts |
|---|---|---|---|
| L-SELF-1 ramp mining (FROM_MUD_TO_WOW + witnesses + UF items + test_wow_*) | zcode-seat 20260929 | RUNNING | lands in watch/inbox/game_platform_basecamp_20260929/ |
| L-SELF-2 platform visions (TOKENOMICS_MYTH_GAME_API + play-as-work + gamedig atlas + noir GWAP) | zcode-seat 20260929 | RUNNING | same dir |
| L-EXT-1 WoW emu ecosystem (CMaNGOS/AzerothCore state, builds, legal line, bots) | zcode-seat 20260929 | RUNNING | same dir |
| L-EXT-2 game backends + creator platforms (Nakama/PlayFab, Roblox/UEFN economics, safety architecture, anti-cheat, play-to-earn post-mortems) | zcode-seat 20260929 | RUNNING | same dir |
| L-EXT-3 GWAP lineage (von Ahn -> reCAPTCHA -> citizen science -> data-through-play, Jain&Parkes) | zcode-seat 20260929 | RUNNING | same dir |
| L-AUDIT estate census (every surface graded RUNNABLE/CODE-ONLY/DESIGN-ONLY/DEAD + test census) | zcode-seat 20260929 | RUNNING | same dir |
| L-B1 server revival (toolchain install, cmake, build mangosd+realmd, world DB) | zcode-seat 20260929 | RECON: submodule init running; toolchain probe done (needs CMake + MSVC/BuildTools + MySQL) | this file's B1 log below |
| L-B3 agreement payload on mud.html | UNCLAIMED | | |
| L-FREE free-lane briefs (stealth driver rotation) | briefs filed, driver rotates | watch/inbox/game_platform_basecamp_20260929/FREE_LANE_BRIEFS.md |

## B1 LOG (append as work happens; never rewrite)

- 2026-09-29: corpus checkout confirmed CMaNGOS mangos-wotlk @ 49dfc1f, GPL-2. Submodule `src/modules/Bots -> celguar/mangosbot-bots` init kicked (background). Toolchain probe: git+python only; no cmake/gcc/cl/mysql/ninja/make. CMake install kicked via winget (background). MSVC Build Tools + MariaDB are the long poles — install next session or via operator winget.
- 2026-09-29 07:0x: **Bots submodule POPULATED** — mangosbot-bots @ b685d7eb (r-2022-11-26~587) checked out into src/modules/Bots (ahbot, botpch, sources present). The owned stack is now code-complete: server core + world DB + bots module. Remaining to runnable: toolchain (CMake installing; MSVC BuildTools + MariaDB owed), client-data extract (owned 3.3.5 client required), first build log.
- 2026-09-29: **TOOLCHAIN COMPLETE**: CMake installed (WinGet), **MSVC Build Tools 2022 + VC 14.44.35207 installed** (VCTools workload, exit 0), **MariaDB 13.0 installed** (mysql.exe present; service not yet registered, DBs not loaded). First-build checklist: MariaDB service + load mangos/realmd/characters/playerbots DBs from sql/ + Boost 1.87 + cmake + compile.
- 2026-09-29 (evening, "go"): **B1 FIRST COMPILE EXECUTED.** Toolchain completed (CMake + MSVC 14.44 + MariaDB 13.0 on Windows; gcc/cmake/boost1.90/mariadb in WSL Ubuntu 26.04). Databases live on both hosts (mangos 161 tbl / characters 80 / playerbots 21 / realmd 8) + world content loaded (29,919 creatures / 9,086 quests). Build tree: WSL `~/mangos-wotlk` (bots @ b685d7eb synced). **RESULT: `realmd` BUILT and links (1.19MB auth-server binary).** `mangosd` blocked by the bots-fused game tree (120 playerbot call sites / 40 files / zero iframes) -> the GCC 15 / Boost 1.90 port of mangosbot-bots is the active lane; 12 fixes landed in the canonical tree (asio io_service/deadline_timer/work/post/run-ec, from_string, cotire cmake_min, Log.cpp overflow, TravelMgr syntax, Value.h two-phase, game-includes unconditional + Vmap case, Player.h include). Ledger down from 12 error classes to upstream source inconsistencies in TravelMgr.cpp/h (WIP snapshot) + remaining unity-order includes. Full resumable state + error ledger: `watch/inbox/game_platform_basecamp_20260929/BOTSPORT_LEDGER_20260929.md`. Next-lane pointer: try `cmangos/playerbots` (CMaNGOS-maintained bots fork) vs pinning a matching celguar commit.
- 2026-09-29: solvability note — B1's first real deliverable is not a running server; it is the LOGGED LIST of everything missing (that log IS the informed-choice input).

## WIDE-WAVE RESULTS (2026-09-29, six lanes LANDED)

Full digests: `watch/inbox/game_platform_basecamp_20260929/LANES_20260929.md`. Headlines:

1. **Audit:** 189 game-scope tests collected (instrument named in digest); 9/9 games runnable; `mag/wow_*` = 2,272 ln / 64 tests with 1,312 opcodes as data (bones_digest `efeb905b…`); Godot slice CODE-ONLY; mud_relay authority gap self-documented.
2. **Self-steal ramp:** the 9/14 ramp doc already priced every WoW organ and staged this exact order; the organ map names the estate itself as the server (percolator = talent tree, XP log = 414,459 lines never spent). Blueprint tension resolved: WOW_CLONE_BETA_BLUEPRINT's "no C++/MySQL ever" + UF-80 are SUPERSEDED by operator order 2026-09-29 (named override). Bridge law: CMaNGOS = content/scale authority; bones/ledger = verification authority.
3. **Self-steal platform:** August vision was assets + slogan (no wallet/token/API artifact exists); GWAP payload design is COMPLETE on paper (schema + KissKissBan + judge organ DORMANT); GAMEDIG's 18 abuse laws = the backend's anti-farm launch checklist; play-as-work v6 gives the meter math. **Seven decisions named and owed** (digest §L-SELF-2.5) — token-vs-ledger, payout schedule, substrate, v0 verification scope, worker-vs-player meters, meter v0 scope, August vibes.
4. **Ext WoW emu:** CMaNGOS wotlk alive, CI-green on Windows; **`bearlikelion/WoWdot` (MIT, Godot 4.7) already walks around AzerothCore 3.3.5a — B2 fork target, months saved**; Blizzard enforcement wave 2025-26 (Turtle WoW injunction) = scale+money+brand triggers; extraction-per-user is the legal product feature.
5. **Ext backends/platforms:** open-core + paid cloud is the surviving vendor model; Roblox effective ~25-30% vs Epic 40% pool vs Steam-25 dead-in-days; **Rec Room shuts down June 2026** (federation law's strongest evidence); no FTC consent order — Texas AG DTPA theory = never market safety you haven't architected; CS:GO Overwatch = player juries at scale killed by unpaid juror XP; Axie = closed-loop token death.
6. **Ext GWAP lineage:** reCAPTCHA = the only GWAP business that scaled (embed in existing friction); **the two-sided "verified judgment as an API" market is UNCLAIMED** (search-confirmed); five openings incl. blocker-role-as-audit-market and data-custody-as-mechanic (ESP's 36M labels died private).

## THE DECISIONS OWED (operator; digests carry the argument)

| # | Decision | Default if operator silent |
|---|---|---|
| D1 | Payout rail: receipt-ledger (real value, published rate) vs one-token scrip | ledger; token deferred |
| D2 | GWAP payout schedule | weight rare byte-backed artifacts; affordance over points |
| D3 | Substrate rung 1 | CMaNGOS+Godot (Teardown purchase un-armed until asked for) |
| D4 | Day-one sellable | replay+receipts only; V2 judge wiring = separate lane |
| D5 | AI clients | workers with cost_enforcer caps; play condition human-only until B4 |
| D6 | Meter v0 | agreement_score + AR floor; SC/NC schema-reserved |
| D7 | August vibes (wallet/token/marketplace/MYTH) | dropped until B4 reveals demand |

## THE MOAT (why this platform and not another)

Frozen-tape replay verification (202/202 green) + agreement payloads + the verkle ledger = **play is provable**. Nobody's creator platform verifies play. That is the thing to sell, and it is already green.

## LAWS THIS PROGRAM RUNS UNDER

- Trust bytes, not reports (every RUNNABLE grade needs an execution or a receipt).
- Landed = fetch/build -> hash -> MANIFEST row (the librarian lane's law, adopted).
- No fabrications, no em-dashes in filed receipts.
- Informed choices are DEFERRED until use — a rung's output is the list of what's missing.
- Claims: edit your row, never others'; append-only B1 log.
- 2026-09-29 15:45Z: **THE GAME LEFT THE MACHINE.** Repo live private: github.com/NachoBusiness17/the-mountain (operator gh auth, account NachoBusiness17; PAT also parked in estate .env as backup, gitignored both repos, gate shapes cover ghp_/github_pat_). mountain-gate fired on first real push: clean. 23 objects / 35.99 KiB / main tracking origin. Next operator step: invite Adam as collaborator. Preparedness-audit gap (game on one box only) closed for the game surface; estate repo stays local-by-design pending its own curation pass.

## WINDOW HANDOFF - 2026-09-29 evening close (zcode-seat, GLM-5.3 window)

STATE AT CLOSE:
- B3 LANDED: the gwap payload module + 21/21 tests pass. The platform verification organ exists as code. Demo ledgers verify clean under memory/runs/gwap/.
- B1: realmd links; mangosd blocked on bots port; bots lane (swap-vs-grind) still cycling at close, self-filing to BOTSPORT_LEDGER.
- GAME LEFT THE MACHINE: github.com/NachoBusiness17/the-mountain (private, gate-clean). Owed: Adam invite.
- OPUS ASK: drafted then INVERTED per delegation research (OPUS_ASK_DRAFT + DELEGATION_RESEARCH in basecamp inbox). Fired version = capability-ledger spec + gate contract + adversarial critique. NOT fired; operator funds.
- RACTOR-ESSAY: dogfood complete (watch/inbox/game_platform_essay_20260929/), 3 amendments owed into the skill (dispatch ladder, Phase 2.5 byte check, digest completeness). NEXT WINDOW applies them.
- HYGIENE: 210 forgotten files committed by triage lane (582189a913b, f324e74b0c, e6b57934e); junk purge list awaiting operator; Belady collision anomaly flagged in triage report.
- SKILLS: woven + functionally proven; lint green; catalog generated.

NEXT WINDOW QUEUE (priority order):
1. Apply ractor-essay skill amendments from the dogfood RECEIPT.
2. Collect bots lane result; if mangosd links, first boot attempt (DBs ready both hosts).
3. gwap payload v1 debts (B3 receipt lists 7): signatures, semantic scoring, MUD integration first.
4. gps-mcp v0 built LOCALLY by mid-tier per the inverted ask (LiteLLM facade + capability ledger + receipt rows).
5. Godot install + first human play of the Mountain slice (or Adam via the repo).
6. Decisions owed: D1-D7 defaults stand unless operator rules; junk purge approval; salon/ractor merge.
- 2026-09-29 16:10 EDT: **THE PORT IS DONE - mangosd LINKED.** 37,544,048 bytes (BuildID b0866273ee31b3c00adefaaacd8c1346a39c92a), 1097 TUs, zero errors. Full stack: realmd 1.19MB + mangosd 37.5MB + libBots.a 44MB, built from the corpus CMaNGOS tree through a 6-cycle GCC15/Boost1.90 port (742 -> 0 unique errors). Cycles 5-6: ledger fix list applied + 2 root causes found deeper (AiObject.h derives without including; Metric.h io_context::work survived the asio sweep via the PCH chain). B1 code phase COMPLETE; boot blocked only on client data (owned 3.3.5a DBC/maps/vmaps/mmaps) + mangosd.conf. Operational law banked: inline wsl bash -c mangles nested escapes (false MAKE_EXIT=0 while make failed) - verification only from script files, trust log bytes.
- 2026-09-29 (night): **FIRST SERVER BOOT. realmd RUNS** - full banner, DB connected (MariaDB 11.8.6 via dedicated mangos user), realm id 1 'MaNGOS' registered, clean timeout shutdown. Zero Blizzard client data needed (auth layer only needs the realmd DB). B2 protocol lane is now unblocked: SRP6 handshake work can point at OUR realmd on demand (boot script banked: b1_realmd_first_boot.sh; conf at build/{src/,}etc/realmd.conf; DB user mangos/mangos granted all four DBs). The world-server (mangosd) boot remains gated on owned 3.3.5a client data - an operator-values call, not a code problem.
- 2026-09-29 (night, operator ruling - THE DECISION): **WE BUILD OUR OWN.** The CMaNGOS build is the specimen, never the product; no 3.3.5a client will ever be sourced (the fork is closed). Two lanes running: (1) HOW_A_REAL_SERVER_WORKS dissection of the compiled reference (auth/session/dispatch/movement/objects/grids/tick/persistence/threading, path-cited); (2) OUR SERVER v0 - server-authoritative water world on our own protocol (asyncio TCP, JSON lines, typed rejects, deterministic ticks), the Mountain board as the world, Python test client first, Godot wiring next. Every organ ours; the reference teaches, we build.
- 2026-09-29 (night): **MICKEY17 IMPROVEMENT WAVE FIRED: 24 concurrent edge-mining agents** (surfaces: mag cores, wow bones, games shelf, relays, corpus, memory, inbox registry, skills, tests, gates, configs, discipline, queue, hermes, new organs, stealth lanes, the-mountain, docs, game state, scripts, telemetry, operator interface, dashboard, cross-organ + port bonus). Mission per agent: mine the edge (novel/underused/surprising), not describe; propose one Mickey17-shaped improvement; report under 250 words. Width note: 24 = past the tested rung (12 clean); operator order; failure mode is absorbed retries. Dissection receipt filed (HOW_A_REAL_SERVER_WORKS digest). Synthesis lands as the improvement-run plan.
