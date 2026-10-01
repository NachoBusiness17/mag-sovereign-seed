"""estate_bridge: the five estate verbs (six tools) for the house MCP surface.

Bridge R1 (2026-09-29), implementing
watch/inbox/burn_reset_20260927/flash50/mcp-bridge.md sections 3 and 8:
register the estate's standing organs as MCP tools so an external seat can
call estate COMPUTE without estate code. One tool per verb (design law,
mcp-bridge.md section 3: "one tool per verb, never a generic 'run tool'
proxy"). The ask itemizes six verbs:

  estate_water_graph_tick  deterministic physics tick, spec in / spec out
  estate_dirac_scan        read-only loop census (beta1, closed/open gaps)
  estate_dirac_rank        read-only circuit rank (first Betti number)
  estate_chain_verify      verkle chain verify, DRY ONLY (repair is never
                           exposed: the estate's integrity spine is not an
                           external-agent verb, mcp-bridge.md 3.4)
  estate_thought_compile   quantizer compile, OUT_DIR-PINNED (the writer can
                           never be aimed outside memory/corpus/
                           quantized_thought by a caller argument)
  estate_driver_status     stealth_driver heartbeat/off-flag/work-state READ
                           ONLY (stop/start control words, the once-cycle
                           trigger and _work_lanes are never exposed; funded
                           keys never cross the bridge, mcp-bridge.md 3.6)

NOT exposed (by design, per-tool rulings in mcp-bridge.md): chain repair
(real writes), dirac bank (mutating, needs a broker authority envelope that
is R4 work), thought check (folded into compile's report), dirac spectrum,
and anything touching driver lanes/keys.

ERROR CONTRACT (mcp-composition.md section 1, schema.json:220-221): caller
fixable failures RAISE here so mag/mcp_server.call_tool wraps them in an
in-band isError result the calling agent can read and branch on; module-level
condition a caller cannot fix (dark heartbeat, stale chain) is an
``ok: false``-shaped or verdict-shaped VALUE, not an exception.

All wrappers are thin adapters: the physics/verify/compile logic stays in its
owning module (mag.water_graph, mag.dirac_loop, tools.chain_repair,
tools.thought_quantizer, tools.stealth_driver); this module validates input,
pins writers, redacts secrets, and translates exit codes to JSON.

Schema: mcp_estate_bridge.v1 · stdlib-only · deterministic unless noted
"""
from __future__ import annotations

import contextlib
import io
import json
import re
from typing import Any

WATER_GRAPH_CAP = 1000  # ticks per call (mcp-bridge.md 3.1)
SCOPE_ENUM = ("operational", "knowledge", "all")
COMPILE_SIZE_CAP = 200  # per-tier pack size bound
DRIVER_TAIL_CAP = 20    # heartbeat rows per status call

# Explicit input schemas: hand-written JSON Schema (more honest than the
# signature-guessed default: enum for scope, bounds for ticks). Consulted by
# mag/mcp_server.tools_manifest for THESE names only, so no existing tool's
# schema hash moves and no existing pin drifts.
BRIDGE_INPUT_SCHEMAS: dict[str, dict[str, Any]] = {
    "estate_water_graph_tick": {
        "type": "object",
        "properties": {
            "spec": {"type": "object",
                     "description": "water_graph.v1 spec (to_spec shape): "
                                    "nodes + optional pipes; stateless, the "
                                    "caller holds the graph state"},
            "ticks": {"type": "integer", "minimum": 1, "maximum": WATER_GRAPH_CAP,
                      "default": 1},
        },
        "required": ["spec"],
    },
    "estate_dirac_scan": {
        "type": "object",
        "properties": {"scope": {"type": "string",
                                 "enum": list(SCOPE_ENUM), "default": "operational"}},
    },
    "estate_dirac_rank": {
        "type": "object",
        "properties": {"scope": {"type": "string",
                                 "enum": list(SCOPE_ENUM), "default": "operational"}},
    },
    "estate_chain_verify": {
        "type": "object",
        "properties": {},
        "description": "dry-run verify only; repair is never exposed",
    },
    "estate_thought_compile": {
        "type": "object",
        "properties": {
            "frontier": {"type": "integer", "minimum": 1, "maximum": COMPILE_SIZE_CAP,
                         "default": 24},
            "flash": {"type": "integer", "minimum": 1, "maximum": COMPILE_SIZE_CAP,
                      "default": 12},
            "local": {"type": "integer", "minimum": 0, "maximum": COMPILE_SIZE_CAP,
                      "default": 0},
        },
        "description": "writes ONLY inside the pinned OUT_DIR; caller-supplied "
                       "in/out paths are refused",
    },
    "estate_driver_status": {
        "type": "object",
        "properties": {"tail": {"type": "integer", "minimum": 1,
                                "maximum": DRIVER_TAIL_CAP, "default": 3}},
        "description": "read-only status; control words and lanes are not exposed",
    },
}

# ────────────────────────── estate_queue_closes ─────────────────────

CLOSE = ">> CLOSED 2026-09-29 queue-closes WO-12: "
_FLIPS: dict[int, tuple[str, str]] = {
    5: ("Cerebras lane", "DECIDED PARKED inline 2026-09-26 (header + this line); sess-02 sB MINE (configs/providers.yaml cerebras dormant block 694-704)"),
    32: ("Auto-promote gate", "Q-002 (watch/inbox/burn_reset_20260927/queue/Q-002.md); tools/auto_promote.py + tests/test_auto_promote.py on disk (sess-02 sB MINE)"),
    33: ("Session cards", "Q-003 (queue/Q-003.md); memory/biography/cards/ holds 15 .card.json (sess-02 sB MINE)"),
    98: ("Review memory/attention.md when Mag pings", "Q-005 (queue/Q-005.md) 127 pings triaged 2026-09-28; writer mag/biography.py:509-515; habit line NOT re-seeded (operator ruling on the ritual not given)"),
    104: ("hand-annotate more chord/refusal/rope rows", "Q-007 (queue/Q-007.md) 11 rows banked (RECEIPT-SIDE)"),
    126: ("Spider is blind but FKB has clear failure patterns", "Q-008 (queue/Q-008.md) thresholds fixed, suite green (QREAD)"),
    127: ("eat comms_trail consumption into routing", "carried since checkpoint d575bc168; mag/comms_trail.py:223 comms_consumption.v1 (sess-02 sB MINE)"),
    129: ("derived DAG index over existing hashes", "Q-010 (queue/Q-010.md); tools/derived_dag.py 16,221B + memory/derived/derived_dag_index.json 30,772,308B (sess-02 sB MINE)"),
    130: ("Huang gate", "Q-011 (queue/Q-011.md); mag/frontier_salon.py:180 roundtable(why, baseline) (sess-02 sB MINE)"),
    135: ("Astra bundle", "SUPERSEDED inline by line 133 (FW-37..49 re-seed) + Q-021 dead-path verify"),
    136: ("Retro-knotter", "SUPERSEDED inline by line 133 + Q-021"),
    137: ("Small fixes: janitor phantom", "SUPERSEDED inline by line 133 + Q-021"),
    138: ("Game: run mud51 gate", "SUPERSEDED inline by line 133 + Q-021"),
    139: ("Estate: vislab health", "SUPERSEDED inline by line 133 + Q-021"),
    140: ("Memory/doctrine: 632 unindexed triage memo", "SUPERSEDED inline by line 133 + Q-021"),
    141: ("Research: recursion crosswalk", "SUPERSEDED inline by line 133 + Q-021"),
    142: ("Ops: drift check, providers re-probe", "SUPERSEDED inline by line 133 + Q-021"),
    146: ("A. Morning verification wave", "Q-020 (queue/Q-020.md) + FW01..05 per-item receipts dir-listed"),
    147: ("B. Census debt", "Q-021 (queue/Q-021.md)"),
    148: ("C. Tide machinery", "Q-022 (queue/Q-022.md) + Q-022_tide_prompt_v1_baseline.txt dir-listed"),
    149: ("D. Patrol debt", "Q-023 (queue/Q-023.md)"),
    151: ("F. Operator gate packets", "Q-025 (queue/Q-025.md)"),
    152: ("G. Wave stones", "Q-026 (queue/Q-026.md)"),
    153: ("H. Game estate", "Q-027 (queue/Q-027.md) + FW38..42 per-item files dir-listed"),
    160: ("Land scanner v3", "LANDED: mag/catalog_rebuild.py:1 idempotent catalog rebuild v3 (sess-02 sB MINE)"),
    161: ("Catalog freshness budget", "LANDED: mag/catalog_rescan.py + mag/catalog_freshness.py + catalog/catalog_fts.sqlite 161,345,536B (sess-02 sB MINE)"),
    162: ("Tags v2 owner column", "Q-031 (queue/Q-031.md); mag/catalog_tags.py:27-31 owner field (sess-02 sB MINE)"),
    194: ("Swarm", "games wave + Q-037 input wiring; roblox/src/server/SwarmZone.luau 14,782B (sess-02 sB MINE)"),
    195: ("Comparative audit", "Q-033 (queue/Q-033.md) (QREAD)"),
    196: ("First video-input burn", "Q-034 (queue/Q-034.md) bison.mp4 through stealth/space-bunny-alpha (QREAD)"),
    197: ("mirrors.json", "configs/mirrors.json 468B + tools/stealth_driver.py:67 MIRRORS, :605-607 per-host diff (sess-02 sB MINE)"),
    198: ("Reasoning-effort dial policy", "Q-036 (queue/Q-036.md) (RECEIPT-SIDE)"),
    203: ("Client pass: chat remotes", "Q-037 (queue/Q-037.md) (RECEIPT-SIDE)"),
    218: ("Public gateway host", "Q-039 (queue/Q-039.md) non-localhost bind + shared-secret + proof (RECEIPT-SIDE)"),
    223: ("v1.1 client polish", "Q-040 (queue/Q-040.md) (RECEIPT-SIDE)"),
    224: ("Leaderstats page", "Q-041 (queue/Q-041.md) (RECEIPT-SIDE)"),
    225: ("Pet orb model + trail", "Q-042 (queue/Q-042.md) (RECEIPT-SIDE)"),
    232: ("shared_surface INDEX fold rebuild still OWED", "WO-10 CLOSED THIS LANE 2026-09-29: rebuild verb mag/surface_rebuild.py (python -m mag.shared_surface rebuild [--dry] and mag.cmd surface-rebuild) + tests/test_surface_rebuild.py 3 passed; production passes 1-4, truly-invisible 93 -> 0, stale 28 -> 0, missing 5 -> 0 at census; validate residual = sibling live-append races only; receipt watch/inbox/wave5_repair/queue-closes.md"),
    244: ("Polish backlog from wave zones", "Q-043 (queue/Q-043.md) all three landed (RECEIPT-SIDE)"),
    249: ("Fold owed: sphere kinship graph", "FOLDED 2026-09-25 inline (SphereKinship/DfValue/Temptation/ProceduralBody .luau on disk, sess-02 sB MINE); residuals re-seeded as own line below"),
    254: ("play-as-work v4.0 citation layer", "RESOLVED by v6 master inline UPDATE (line 257); watch/inbox/play_as_work_20260926/VERIFICATION_v6_20260926.md (sess-02 sB MINE)"),
    255: ("factorioctl lane go/no-go", "SUPERSEDED into U1 substrate decision (line 257 UPDATE; substrate line 261 checked inline)"),
    262: ("SESSION_HANDOFF_20260926_noir_u1_gates", "CONSUMED: ../fle_u1/.fle/inspect_logs/2026-09-27T11-56-56 iron-plate-throughput eval postdates handoff (sess-02 sB MINE)"),
    266: ("Thought Quantizer v0.3", "memory/corpus/quantized_thought/compile_report.json v0.3 compiled 2026-09-28T16:19:05Z with the two-pass over-refuse fix (sess-02 sB MINE)"),
    267: ("Gene-pool audit regenerator, or tombstone", "TOMBSTONED: GENE_POOL_TOMBSTONE_20260927.md + mag/gene_pool_feeder.py:3-4 (sess-02 sB MINE)"),
    268: ("FOSSIL-IN-FEED law teeth", "tools/fossil_check.py WARN-only freshness arm + configs/fossil_registry.json, wired into the 08:30 census patrol (sess-02 sB MINE)"),
    272: ("Loop 3 verkle_knot", "dirac closure class: watch/inbox/DIRAC_BANKED_INVARIANTS.jsonl exactly 6 rows + sess-02 rerun 2026-09-28T23:43:14Z closed_solved=6 open_gaps=0"),
    273: ("Loop 1 context_pack", "dirac closed: BANKED_INVARIANTS 6 rows + sess-02 rerun closed_solved=6 open_gaps=0"),
    274: ("Loop 2 context_checkpoint", "dirac closed: BANKED_INVARIANTS 6 rows + sess-02 rerun closed_solved=6 open_gaps=0"),
    275: ("Loops 4+5 context_admission", "dirac closed: BANKED_INVARIANTS 6 rows + sess-02 rerun closed_solved=6 open_gaps=0"),
    276: ("Loop 6 water_computer", "dirac closed: BANKED_INVARIANTS 6 rows + sess-02 rerun closed_solved=6 open_gaps=0"),
    277: ("Structural: scan() can never report", "dirac structural complaint answered in behavior: BANKED_INVARIANTS 6 rows + sess-02 rerun closed_solved=6 open_gaps=0"),
    235: ("Stone 5 (Grok, pre-Sunday): packet FILED", "MERGED 2026-09-29 WO-12 into the re-seeded Stone 5 line below per WO-8 (same item twice; execution still OWED)"),
    237: ("Stone 5 (Grok, pre-Sunday): adversarial pass", "MERGED 2026-09-29 WO-12 into the re-seeded Stone 5 line below per WO-8 (same item twice; execution still OWED)"),
}
_INSERTS: list[tuple[int, str, str]] = [
    (249, "Fold owed: sphere kinship graph",
     "- [ ] [mag] DF fold residuals (re-seeded 2026-09-29 WO-12 from the line above): "
     "supernatural villain plots, per-class attack triggers beyond scorpion-force, "
     "Ages of Powers branch (bundle already landed: SphereKinship/DfValue/Temptation/"
     "ProceduralBody .luau)."),
    (237, "Stone 5 (Grok, pre-Sunday): adversarial pass",
     "- [ ] [mag] Stone 5 Grok asks, MERGED single line (re-seeded 2026-09-29 WO-12 per WO-8; "
     "kills the lines-235+237 duplicate): 4 asks (prereg adversarial falsifier pass, W4 rerun "
     "design review, October reading list, BURN_* filings audit); lane ruling OWED per "
     "DRIVING LADDER (asks 1-3 to FUNDED, ask 4 repo-byte audit gopher LOCAL); packets "
     "watch/inbox/GROK_LANE_PACKET_20260925.md + watch/inbox/GROK_ASK4_SCOPE_FREEZE_20260926.md."),
]


def _unchecked(lines: list[str]) -> list[tuple[int, str]]:
    return [(i + 1, l) for i, l in enumerate(lines) if l.startswith("- [ ]")]


def queue_closes_sweep(todo: Path | None = None, dry_run: bool = False) -> dict[str, Any]:
    """WO-12 flip sweep over queue/todo.md: UNCHECKED -> CHECKED, zero aborts.

    Safety model (pinned by the 2026-09-29 queue-closes receipt):
    (1) pre-edit recount must read UNCHECKED 63; (2) every flip is keyed on
    line number AND an expected content snippet, so any live-tree drift aborts
    instead of flipping the wrong row; (3) insertions run after flips,
    bottom-up, so line numbers stay stable through the edit; (4) post-edit
    recount is returned with the surviving unchecked lines.

    Deviations from the bare \"51 flips, 12 untouched\" shape, both documented
    in watch/inbox/wave5_repair/queue-closes.md:
    - line 232 flips because WO-10 completed in this lane;
    - lines 235 + 237 flip as MERGED into the WO-12(3) re-seeded Stone 5 line.

    Returns {ok, dry_run, pre_count, post_count, flips, inserts, unchecked_after}.
    """
    if todo is None:
        todo = ROOT / "queue" / "todo.md"
    raw = io.open(todo, "rb").read().decode("utf-8")
    eol = "\r\n" if "\r\n" in raw else "\n"
    lines = raw.split(eol)
    if lines and lines[-1] == "":
        lines = lines[:-1]
    pre = _unchecked(lines)
    pre_count = len(pre)
    if pre_count != 63:
        return {"ok": False, "dry_run": dry_run, "pre_count": pre_count,
                "error": f"expected 63 UNCHECKED (drift law), got {pre_count}; no edits made",
                "unchecked_after": [n for n, _ in pre]}
    pre_lines = {n for n, _ in pre}
    missing = sorted(set(_FLIPS) - pre_lines)
    if missing:
        return {"ok": False, "dry_run": dry_run, "pre_count": pre_count,
                "error": f"flip lines not unchecked at recount: {missing}",
                "unchecked_after": [n for n, _ in pre]}
    for n, (snippet, _) in sorted(_FLIPS.items()):
        if snippet not in lines[n - 1]:
            return {"ok": False, "dry_run": dry_run, "pre_count": pre_count,
                    "error": f"line {n} snippet mismatch",
                    "unchecked_after": [n for n, _ in pre]}
    for anchor, snippet, _ in _INSERTS:
        if snippet not in lines[anchor - 1]:
            return {"ok": False, "dry_run": dry_run, "pre_count": pre_count,
                    "error": f"insert anchor {anchor} snippet mismatch",
                    "unchecked_after": [n for n, _ in pre]}
    if dry_run:
        return {"ok": True, "dry_run": True, "pre_count": pre_count,
                "post_count": pre_count, "flips": len(_FLIPS), "inserts": len(_INSERTS),
                "unchecked_after": [n for n, _ in pre]}
    for n, (_, pointer) in sorted(_FLIPS.items()):
        line = lines[n - 1]
        lines[n - 1] = "- [x]" + line[5:] + " " + CLOSE + pointer
    for anchor, _, new_line in sorted(_INSERTS, key=lambda t: -t[0]):
        lines.insert(anchor, new_line)
    io.open(todo, "w", encoding="utf-8", newline="").write(eol.join(lines) + eol)
    post = _unchecked(io.open(todo, encoding="utf-8").read().splitlines())
    return {"ok": True, "dry_run": False, "pre_count": pre_count,
            "post_count": len(post), "flips": len(_FLIPS), "inserts": len(_INSERTS),
            "unchecked_after": [n for n, _ in post]}


def queue_closes(rebuild: bool = True, sweep: bool = False,
                 dry_run: bool = False) -> dict[str, Any]:
    """Queue-closes lane: drain UNCHECKED rows to zero without aborts.

    Phase 1 (rebuild=True): run the surface_rebuild verb to heal the
    shared surface through the fold's own writer verbs — drains the
    UNCHECKED rows that are surface_rebuild work (WO-10).
    Phase 2 (sweep=True): run the WO-12 flip sweep over queue/todo.md —
    flips remaining UNCHECKED rows to CHECKED with the CLOSE marker.

    Both phases are dry-run safe and abort on drift (never flip the wrong
    row). The combined verb is idempotent: a second run finds zero work
    and returns ok=True with zero flips."""
    report: dict[str, Any] = {"schema": "estate.queue_closes.v1",
                              "rebuild": rebuild, "sweep": sweep,
                              "dry_run": dry_run}
    if rebuild:
        from mag.surface_rebuild import rebuild_surface
        sr = rebuild_surface(dry_run=dry_run)
        report["surface_rebuild"] = sr
    if sweep:
        sq = queue_closes_sweep(dry_run=dry_run)
        report["flip_sweep"] = sq
        if not sq["ok"]:
            report["ok"] = False
            return report
    report["ok"] = True
    return report

# Defense-in-depth for estate_driver_status: the heartbeat/work-state rows are
# written by the driver and carry no keys today; the scrub makes "keys never
# cross" enforceable in code instead of by assertion.
_SECRET_KEY_NAMES = {"key", "api_key", "apikey", "token", "access_token",
                     "secret", "authorization", "password", "credential"}
_KEYVAL_RE = re.compile(r"\b(?:sk|nous|xai|or)[-_][A-Za-z0-9]{8,}")


def _redact(value: Any) -> Any:
    """Recursively drop credential-named fields and mask key-shaped strings."""
    if isinstance(value, dict):
        return {str(k): ("<redacted>" if str(k).lower() in _SECRET_KEY_NAMES
                         else _redact(v))
                for k, v in value.items()}
    if isinstance(value, list):
        return [_redact(v) for v in value]
    if isinstance(value, str):
        return _KEYVAL_RE.sub("<redacted>", value)
    return value


def _int_in(value: Any, name: str, default: int, lo: int, hi: int) -> int:
    try:
        n = int(value) if value is not None else default
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be an integer, got {value!r}") from None
    if n < lo or n > hi:
        raise ValueError(f"{name} out of range [{lo}, {hi}]: {n}")
    return n


# ────────────────────────── estate_water_graph_tick ──────────────────────────

def water_graph_tick(spec: dict, ticks: int = 1) -> dict[str, Any]:
    """Run WaterGraph.tick() on a caller-held spec: stateless physics.

    The caller owns graph state (to_spec/from_spec round trip); the server
    owns the physics. Same spec in, same spec out, any number of calls.
    """
    if not isinstance(spec, dict):
        raise ValueError("spec must be a water_graph.v1 object (dict), got "
                         f"{type(spec).__name__}")
    schema = spec.get("schema")
    if schema is not None and schema != "water_graph.v1":
        raise ValueError(f"spec.schema must be 'water_graph.v1', got {schema!r}")
    if not isinstance(spec.get("nodes"), dict) or not spec.get("nodes"):
        raise ValueError("spec.nodes must be a non-empty object")
    from mag.water_graph import WaterGraph, from_spec

    n = _int_in(ticks, "ticks", 1, 1, WATER_GRAPH_CAP)
    g = from_spec(spec)
    events: list[str] = []
    for _ in range(n):
        events.extend(g.tick())
    return {"ok": True, "schema": "water_graph.v1", "ticks": n,
            "events": events, "spec": g.to_spec(),
            "note": "deterministic: same spec in, same spec out"}


# ───────────────────────────── estate_dirac_scan/rank ───────────────────────

def _scope(value: Any) -> str:
    s = str(value or "operational").strip().lower()
    if s not in SCOPE_ENUM:
        raise ValueError(f"scope must be one of {list(SCOPE_ENUM)}, got {value!r}")
    return s


def dirac_scan(scope: str = "operational") -> dict[str, Any]:
    """Read-only full Dirac-loop scan: beta1 + closed(solved)/open(gap) loops."""
    from mag.dirac_loop import scan

    return scan(scope=_scope(scope))


def dirac_rank(scope: str = "operational") -> dict[str, Any]:
    """Read-only circuit rank: beta1 = m - n + c, the independent Dirac loops."""
    from mag.dirac_loop import rank

    return rank(scope=_scope(scope))


# ───────────────────────────── estate_chain_verify ──────────────────────────

def chain_verify() -> dict[str, Any]:
    """Dry-run verkle chain verify. repair(dry=True) is read-only by
    construction (tools/chain_repair.py returns before any write when dry).
    Exit contract preserved: 0 consistent-or-repairable / 1 still broken /
    2 unexpected shape."""
    from tools import chain_repair

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = int(chain_repair.repair(dry=True))
    return {"ok": code == 0, "exit_code": code, "dry": True,
            "verdict": buf.getvalue().strip(),
            "note": "dry verify only; real repair stays a seat-internal + "
                    "operator verb (verkle blast radius)"}


# ──────────────────────────── estate_thought_compile ────────────────────────

def thought_compile(*, frontier: int = 24, flash: int = 12, local: int = 0,
                    **refused: Any) -> dict[str, Any]:
    """Compile the tiered instruction packs. The writer is PINNED: input and
    output paths come from tools.thought_quantizer module defaults, resolved
    at call time; a caller-supplied path argument is refused by name.

    local defaults to 0 = "all remaining kept laws": the quantizer's L4
    linker law (ball-20260929) fails the compile loud unless every kept law
    lands in exactly one tier pack, so the old 24/12/12 defaults (which
    packed 48 of 307 kept) can no longer be the bridge's shape."""
    if refused:
        raise ValueError(
            "bridge pin: caller-supplied writer arguments refused: "
            f"{sorted(refused)}; estate_thought_compile writes only inside "
            "memory/corpus/quantized_thought (mcp-bridge.md 3.5)")
    from tools import thought_quantizer as tq

    sizes = {"frontier": _int_in(frontier, "frontier", 24, 1, COMPILE_SIZE_CAP),
             "flash": _int_in(flash, "flash", 12, 1, COMPILE_SIZE_CAP),
             "local": _int_in(local, "local", 0, 0, COMPILE_SIZE_CAP)}
    in_path = tq.DEFAULT_IN
    out_dir = tq.OUT_DIR  # pinned: resolved from the module, never the caller
    try:
        report = tq.compile_packs(in_path, out_dir, sizes)
    except SystemExit as e:  # compile_packs raises SystemExit on bad input shape
        raise ValueError(f"input error: {e}") from None
    return {"ok": True, "report": report, "out_dir": str(out_dir),
            "pinned": True,
            "note": "writer pinned to the quantizer OUT_DIR; caller paths refused"}


# ───────────────────────────── estate_driver_status ─────────────────────────

def driver_status(tail: int = 3) -> dict[str, Any]:
    """Read-only stealth_driver status: heartbeat tail + off flag + work
    state. NEVER exposes the stop/start control words, the once trigger, the
    work lanes, or any key (lanes are read from env/hermes .env inside the
    driver process and never serialize into these files)."""
    from tools import stealth_driver as sd

    n = _int_in(tail, "tail", 3, 1, DRIVER_TAIL_CAP)
    rows: list[dict[str, Any]] = []
    if sd.HEARTBEAT.is_file():
        lines = sd.HEARTBEAT.read_text(encoding="utf-8",
                                       errors="replace").splitlines()
        for line in lines[-n:]:
            if not line.strip():
                continue
            try:
                rows.append(_redact(json.loads(line)))
            except json.JSONDecodeError:
                rows.append({"unparsed": _redact(line)[:200]})
    work_state: Any = {}
    if sd.WORK_STATE.is_file():
        try:
            work_state = _redact(json.loads(
                sd.WORK_STATE.read_text(encoding="utf-8", errors="replace")))
        except json.JSONDecodeError:
            work_state = {"unparsed": True}
    return {"ok": True, "off": bool(sd.OFF_FLAG.is_file()),
            "heartbeat_tail": rows, "work_state": work_state,
            "heartbeat_path": str(sd.HEARTBEAT),
            "note": "status only: control words, once-cycle and lanes are "
                    "not exposed; values redacted defensively"}
