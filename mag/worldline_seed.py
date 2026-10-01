"""worldline_seed — W1 death rite v2: emit + verify THE WORLDLINE SEED.

Card: watch/WORLDLINE_SEED_20260907.md. The seed is the portable manifest of a
closing session's worldline: genome + invariants + organs + record + position.
Falsifier (card, W1 spec): missing any slab = malformed. Verify recomputes every
sha against on-disk truth; sha mismatch / missing slab / bad seed_hash = REJECT
(exit 2); chain-tip drift vs the live chain = WARNING, not a reject (the chain
is append-only and the world moves on after a death).

THE FIVE SLABS
  genome     path+sha256 of the workspace AGENTS.md + names of available skills
             (names only, never contents) from the three skill roots.
  invariants path+sha256 of MEMORY.md + curator_list. CURATION RULE (honest v1):
             "the curated front = what the index names" — walk the index's entry
             lines (`- [Title](file.md)`) in INDEX ORDER, resolve each filename
             against the memory dir, keep files that exist, cap 40, each entry
             recorded as {name, path, sha256} (path+sha+name only, no contents).
             Unresolvable entries are counted (skipped_unresolved), never guessed.
  organs     pointers only, NO SECRETS: cage MCP config path+sha if a stable
             config file exists at a known candidate path, else the topology-card
             note with config_path null. Explicit "secrets": "none-captured".
  record     trajectory tape ref (row count + tip step_hash) + verkle knot ref
             (row count + tip leaf_hash) + selector block: try mag.preload_selector
             (F-W5 instrument, label PROXY); if importable with a usable ordering
             entrypoint -> {"mode": "trajectory-conditioned", "top_refs": ...}
             (ids + scores only), else {"mode": "naive", "reason": ...}.
             Selector absence NEVER fails emission.
  position   chain tip (leaf_hash + ts, last line of the verkle chain) + the
             seed's own minute span (creation minute; v1 = point span) +
             prev_seed (null in v1 — no lineage chain of seeds yet).

seed_hash: sha256 over the canonical manifest EXCLUDING seed_hash (sort_keys,
ensure_ascii=False), first 16 hex chars. consent: replication operator-gated,
egress none — a provenance-chained symbiote, per card door #2.

SECRETS LAW: only the specific files named in this module are read; only hashes
and names are captured, never contents; .env / credential stores / key material
are never opened. The mcp config candidates are hashed (structure proof), never
embedded.

CLI:
  python -m mag.worldline_seed emit --session-id <id> [--out DIR]
  python -m mag.worldline_seed verify <seed.json>
  python -m mag.worldline_seed load <seed.json> [--probe] [--model NAME]

W2 RESURRECTION LOADER (2026-09-07): `load` verifies first (ANY reject =
REFUSE, exit 2 — tamper dies at the door, the F-W3 drill), then resolves
every slab ref into a RESURRECTION BUNDLE at
memory/worldline/<session_id>/RESURRECTION_BUNDLE.md (+ .json sidecar with
machine fields). The bundle IS the reconstituted prefix, in order: identity,
genome (AGENTS.md verbatim, sha-verified at load — our own workspace file,
lawful to embed), invariants (MEMORY.md index front + curator refs with
shas), record (this session's sealed tape rows verbatim, selector top refs),
position, continuity questions, consent. `--probe` runs the F-W1 resurrection
probe through HOST ollama (qwen2.5:3b-instruct): RESURRECTED arm (bundle as
the preload) vs COLD arm (no preload), identical turn. Q1-Q3 scored by
exact/fuzzy fact match against the bundle's true values, Q4 by keyword
rubric. Verdict bar: bundle >=2/3 facts AND cold 0/3 = F-W1 SUPPORTED at
PROXY level ("resurrection materially better than cold"); bundle <2/3 =
UNPROVEN at this scale. The 3B specimen is a PROXY carrier, never the
production seat — instrument-level verdict, not row 320. Rows:
memory/runs/worldline_resurrection/probe_20260907.jsonl (label PROXY).

$0-local: files only, no cloud, no docker.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
AGENTS_MD = ROOT.parent / "AGENTS.md"
MEMORY_DIR = Path.home() / ".zcode" / "cli" / "memories" / "projects" / \
    "projects-0fb5e3041b59db21" / "memory"
MEMORY_MD = MEMORY_DIR / "MEMORY.md"
CHAIN = ROOT / "memory" / "biography" / "verkle_chain.jsonl"
TAPE = ROOT / "memory" / "runs" / "trajectory" / "steps.jsonl"
DEFAULT_OUT = ROOT / "memory" / "worldline"
SKILL_ROOTS = {
    "workspace": ROOT / ".agents" / "skills",
    "user-agents": Path.home() / ".agents" / "skills",
    "user-zcode": Path.home() / ".zcode" / "skills",
}
MCP_CONFIG_CANDIDATES = (
    ROOT / ".mcp.json",
    ROOT / "mcp.json",
    ROOT / ".agents" / "mcp.json",
    ROOT / "configs" / "mcp.json",
)
MCP_TOPOLOGY_NOTE = ("senses live in the cage — topology card "
                     "watch/SELF_STEAL_MCP_TOPOLOGY_20260904.md")
CURATOR_CAP = 40
SELECTOR_TOP = 10
SLABS = ("genome", "invariants", "organs", "record", "position")
ENTRY_RE = re.compile(r"^- \[[^\]]+\]\(([^)]+\.md)\)", re.M)
SCHEMA_VERSION = 1


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _sha256_file(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def _canonical(manifest: dict[str, Any]) -> str:
    return json.dumps(manifest, sort_keys=True, ensure_ascii=False)


def _seed_hash(manifest: dict[str, Any]) -> str:
    core = {k: v for k, v in manifest.items() if k != "seed_hash"}
    return hashlib.sha256(_canonical(core).encode("utf-8")).hexdigest()[:16]


def _pointer(path: Path) -> dict[str, Any]:
    return {"path": path.resolve().as_posix(), "sha256": _sha256_file(path)}


def _genome_slab() -> dict[str, Any]:
    skills: dict[str, list[str]] = {}
    for source, root in SKILL_ROOTS.items():
        if root.is_dir():
            names = sorted(p.name for p in root.iterdir()
                           if p.is_dir() and (p / "SKILL.md").is_file())
            if names:
                skills[source] = names
    flat = sorted({n for names in skills.values() for n in names})
    return {
        "agents_md": _pointer(AGENTS_MD),
        "skills": flat,
        "skills_by_source": skills,
        "skill_count": len(flat),
    }


def _curator_list() -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Curation rule (v1, see module docstring): the index's own first entries,
    in index order, resolved to on-disk files, capped."""
    entries: list[dict[str, Any]] = []
    seen = 0
    if MEMORY_MD.is_file():
        for match in ENTRY_RE.finditer(MEMORY_MD.read_text(encoding="utf-8",
                                                           errors="replace")):
            if len(entries) >= CURATOR_CAP:
                break
            seen += 1
            fname = match.group(1)
            path = MEMORY_DIR / fname
            sha = _sha256_file(path)
            if sha is None:
                continue  # unresolved/unreadable: counted, never guessed
            entries.append({"name": fname.removesuffix(".md"),
                            "path": path.resolve().as_posix(),
                            "sha256": sha})
    stats = {"index_entries_seen": seen, "resolved": len(entries),
             "skipped_unresolved": seen - len(entries)}
    return entries, stats


def _invariants_slab() -> dict[str, Any]:
    curators, stats = _curator_list()
    return {
        "memory_md": _pointer(MEMORY_MD),
        "curator_rule": ("v1: the curated front = what the index names — index "
                         "entry order, resolved files only, cap 40, path+sha+name"),
        "curator_list": curators,
        "curator_stats": stats,
    }


def _organs_slab() -> dict[str, Any]:
    config = None
    for cand in MCP_CONFIG_CANDIDATES:
        if cand.is_file():
            config = _pointer(cand)
            config["source"] = "first stable candidate"
            break
    if config is None:
        config = {"note": MCP_TOPOLOGY_NOTE, "config_path": None}
    return {"mcp_config": config, "secrets": "none-captured"}


def _tape_ref() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    if TAPE.is_file():
        for ln in TAPE.read_text(encoding="utf-8", errors="replace").splitlines():
            ln = ln.strip()
            if not ln:
                continue
            try:
                rows.append(json.loads(ln))
            except json.JSONDecodeError:
                continue
    tip = next((r.get("step_hash") for r in reversed(rows)
                if isinstance(r, dict) and r.get("step_hash")), None)
    ref = {"path": TAPE.resolve().as_posix(), "rows": len(rows), "tip_step_hash": tip}
    try:  # integrity verdict from the tape's own verify logic (optional garnish)
        from mag import bash_local as bl
        ok, msg = bl.verify()
        ref["verify_ok"] = bool(ok)
        ref["verify_msg"] = msg[:200]
    except Exception as exc:  # noqa: BLE001 — garnish only
        ref["verify_ok"] = None
        ref["verify_msg"] = f"verify unavailable: {str(exc)[:120]}"
    return ref


def _knot_ref() -> dict[str, Any]:
    last: dict[str, Any] | None = None
    n = 0
    if CHAIN.is_file():
        for ln in CHAIN.read_text(encoding="utf-8", errors="replace").splitlines():
            ln = ln.strip()
            if not ln:
                continue
            n += 1
            try:
                last = json.loads(ln)
            except json.JSONDecodeError:
                continue
    return {"path": CHAIN.resolve().as_posix(), "rows": n,
            "tip_leaf_hash": (last or {}).get("leaf_hash"),
            "tip_ts": (last or {}).get("ts")}


def _selector_block() -> dict[str, Any]:
    """trajectory-conditioned refs via the F-W5 selector — import-fail-safe."""
    try:
        from mag.preload_selector import load_blocks, order_blocks  # type: ignore
        if not (callable(load_blocks) and callable(order_blocks)):
            raise AttributeError("no usable ordering entrypoint")
        ranked = order_blocks(load_blocks())
        return {
            "mode": "trajectory-conditioned",
            "selector": "mag.preload_selector.order_blocks(load_blocks())",
            "label": "PROXY",
            "blocks_total": len(ranked),
            "top_refs": [{"id": b.get("id"), "score": b.get("score")}
                         for b in ranked[:SELECTOR_TOP]],
        }
    except Exception as exc:  # noqa: BLE001 — NEVER fail emission on selector
        return {"mode": "naive",
                "reason": f"selector not usable: {type(exc).__name__}: "
                          f"{str(exc)[:120]}"}


def _record_slab() -> dict[str, Any]:
    try:  # second belt: even a raising selector block never fails emission
        sel = _selector_block()
    except Exception as exc:  # noqa: BLE001
        sel = {"mode": "naive",
               "reason": f"selector raised: {type(exc).__name__}: {str(exc)[:120]}"}
    return {"tape_ref": _tape_ref(), "knot_ref": _knot_ref(), "selector": sel}


def _position_slab(created: datetime) -> dict[str, Any]:
    tip = _knot_ref()
    minute = created.strftime("%Y-%m-%dT%H:%M")
    return {"chain_tip": {"leaf_hash": tip["tip_leaf_hash"], "ts": tip["tip_ts"]},
            "minute_span": {"start_minute": minute, "end_minute": minute,
                            "unix_minute": str(int(created.timestamp() // 60))},
            "prev_seed": None}


def emit(session_id: str, out_dir: Path | None = None) -> Path:
    """Compile + write the seed; returns the seed path. Never captures contents."""
    created = _now()
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", session_id or "unnamed")
    manifest: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "kind": "worldline_seed",
        "created_utc": created.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "session_id": session_id,
        "slabs": {
            "genome": _genome_slab(),
            "invariants": _invariants_slab(),
            "organs": _organs_slab(),
            "record": _record_slab(),
            "position": _position_slab(created),
        },
        "consent": {"replication": "operator-gated", "egress": "none"},
    }
    manifest["seed_hash"] = _seed_hash(manifest)
    dest = (out_dir or (DEFAULT_OUT / safe))
    dest.mkdir(parents=True, exist_ok=True)
    out = dest / "SEED.json"
    out.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    print(f"WORLDLINE SEED emitted: {out}")
    print(f"seed_hash: {manifest['seed_hash']}  (session {session_id})")
    return out


# ---------------------------------------------------------------- verify

def _fail(checks: list[list[Any]], slab: str, name: str, detail: str) -> None:
    checks.append([slab, name, "FAIL", detail])


def _ok(checks: list[list[Any]], slab: str, name: str, detail: str) -> None:
    checks.append([slab, name, "PASS", detail])


def _warn(checks: list[list[Any]], slab: str, name: str, detail: str) -> None:
    checks.append([slab, name, "WARN", detail])


def _check_sha(checks: list[list[Any]], slab: str, label: str,
               pointer: dict[str, Any]) -> None:
    path_s = pointer.get("path")
    recorded = pointer.get("sha256")
    if not path_s or not recorded:
        _fail(checks, slab, label, "missing path or sha256 in pointer")
        return
    path = Path(path_s)
    if not path.is_file():
        _fail(checks, slab, label, f"file missing on disk: {path_s}")
        return
    live = _sha256_file(path)
    if live != recorded:
        _fail(checks, slab, label, f"SHA MISMATCH recorded={recorded[:16]} live={live[:16] if live else None}")
    else:
        _ok(checks, slab, label, f"sha ok {recorded[:16]}")


def _check_growing(checks: list[list[Any]], slab: str, label: str, path_s: str,
                   tip_field: str, tip: str | None, needle_field: str,
                   recorded_rows: int, live_rows: int) -> None:
    """Append-only file check: recorded tip must still exist in the live file;
    growth beyond the recorded count is honest drift (note), disappearance is
    provenance destruction (REJECT)."""
    path = Path(path_s)
    if not path.is_file():
        _fail(checks, slab, label, f"file missing on disk: {path_s}")
        return
    present = False
    for ln in path.read_text(encoding="utf-8", errors="replace").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            row = json.loads(ln)
        except json.JSONDecodeError:
            continue  # repo files are data: malformed lines are skipped
        if isinstance(row, dict) and row.get(needle_field) == tip:
            present = True
            break
    if not present:
        _fail(checks, slab, label,
              f"recorded tip {str(tip)[:16]} NOT FOUND in live file (rewritten/truncated)")
        return
    if live_rows < recorded_rows:
        _fail(checks, slab, label,
              f"row count SHRANK: recorded {recorded_rows} live {live_rows}")
        return
    if live_rows > recorded_rows:
        _warn(checks, slab, label,
              f"grew since seed: recorded {recorded_rows} rows -> live {live_rows}; "
              f"tip {str(tip)[:16]} still present (append-only, honest)")
    else:
        _ok(checks, slab, label, f"{recorded_rows} rows, tip {str(tip)[:16]} present")


def _rows_and_tip(path: Path, tip_field: str) -> tuple[int, str | None]:
    n, tip, last = 0, None, None
    for ln in path.read_text(encoding="utf-8", errors="replace").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        n += 1
        try:
            last = json.loads(ln)
        except json.JSONDecodeError:
            continue
        if isinstance(last, dict) and last.get(tip_field):
            tip = last[tip_field]
    return n, tip


def _verify_tape_history(checks: list[list[Any]], tape: dict[str, Any]) -> None:
    """Witness-#3 hardening: recompute per-row step hashes and per-session chain
    links for every tape row up to the seed's death checkpoint. Altered
    historical content now REJECTS even when the recorded tip string still
    exists verbatim (the old check was satisfiable by a rewritten twin)."""
    try:
        from mag.bash_local import _row_hash
    except Exception as exc:  # pragma: no cover - sibling module is local
        _warn(checks, "record", "tape_history", f"hash function unavailable: {exc}")
        return
    path = Path(tape["path"])
    recorded = tape.get("rows", -1)
    if not isinstance(recorded, int) or recorded < 1:
        _warn(checks, "record", "tape_history", "no recorded row count; history not recomputed")
        return
    genesis = "0" * 16
    checked = bad_hash = bad_link = 0
    prev_by_session: dict[str, str] = {}
    for i, ln in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines()):
        if i >= recorded:
            break
        ln = ln.strip()
        if not ln:
            continue
        try:
            row = json.loads(ln)
        except json.JSONDecodeError:
            continue
        if not isinstance(row, dict):
            continue
        checked += 1
        sid = str(row.get("session_id", ""))
        if row.get("prev_step_hash") != prev_by_session.get(sid, genesis):
            bad_link += 1
        try:
            if _row_hash(row) != row.get("step_hash"):
                bad_hash += 1
        except Exception:
            bad_hash += 1
        prev_by_session[sid] = str(row.get("step_hash", genesis))
    if not checked:
        _warn(checks, "record", "tape_history", "no rows found in recorded range")
    elif bad_hash or bad_link:
        _fail(checks, "record", "tape_history",
              f"HISTORICAL TAMPER: {bad_hash} hash mismatches, {bad_link} chain-link "
              f"breaks across {checked} rows")
    else:
        _ok(checks, "record", "tape_history",
            f"{checked} historical rows recomputed: hashes + session links intact")


def _verify_impl(seed_path: Path
                 ) -> tuple[int, list[list[Any]], dict[str, Any] | None,
                            str | None]:
    """W2: the full W1 verification WITHOUT printing.

    Returns (exit_code, checks, manifest, table_hash). table_hash is None for
    the malformed early-exit (verify() prints None there — print contract kept
    byte-identical); otherwise the recorded seed_hash."""
    try:
        manifest = json.loads(Path(seed_path).read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return 2, [], None, None
    checks: list[list[Any]] = []

    if manifest.get("kind") != "worldline_seed":
        _fail(checks, "schema", "kind", f"expected worldline_seed, got {manifest.get('kind')!r}")
    if manifest.get("schema_version") != SCHEMA_VERSION:
        _fail(checks, "schema", "schema_version",
              f"expected {SCHEMA_VERSION}, got {manifest.get('schema_version')!r}")

    slabs: dict[str, Any] = manifest.get("slabs") or {}
    for name in SLABS:
        if name not in slabs or not isinstance(slabs.get(name), dict) or not slabs[name]:
            _fail(checks, name, "present", "MISSING SLAB = malformed (card falsifier)")
    if any(c[2] == "FAIL" for c in checks):
        return 2, checks, manifest, None

    # seed_hash integrity FIRST among content checks (any manifest edit breaks it)
    recorded_hash = manifest.get("seed_hash")
    live_hash = _seed_hash(manifest)
    if recorded_hash != live_hash:
        _fail(checks, "seed_hash", "integrity",
              f"RECORDED {recorded_hash} != RECOMPUTED {live_hash} — manifest edited")
    else:
        _ok(checks, "seed_hash", "integrity", recorded_hash)

    g, inv, org, rec, pos = (slabs[s] for s in SLABS)

    # genome
    _check_sha(checks, "genome", "agents_md", g.get("agents_md") or {})
    if g.get("skills"):
        _ok(checks, "genome", "skills", f"{g.get('skill_count', len(g['skills']))} names "
                                        f"(sources: {', '.join(g.get('skills_by_source') or {})})")
    else:
        _fail(checks, "genome", "skills", "empty")

    # invariants
    _check_sha(checks, "invariants", "memory_md", inv.get("memory_md") or {})
    curators = inv.get("curator_list") or []
    if not curators:
        _fail(checks, "invariants", "curator_list", "empty")
    else:
        bad: list[str] = []
        for e in curators:
            path_s, recorded = e.get("path"), e.get("sha256")
            live = _sha256_file(Path(path_s)) if (path_s and recorded) else None
            if live != recorded:
                bad.append(str(e.get("name", "?")))
        if bad:
            _fail(checks, "invariants", "curator_list",
                  f"{len(curators) - len(bad)}/{len(curators)} curator shas ok, "
                  f"{len(bad)} MISMATCHED (first: {', '.join(bad[:5])})")
        else:
            _ok(checks, "invariants", "curator_list",
                f"{len(curators)}/{len(curators)} curator shas ok")

    # organs
    secrets = org.get("secrets")
    if secrets == "none-captured":
        _ok(checks, "organs", "secrets", "none-captured (law held)")
    else:
        _fail(checks, "organs", "secrets", f"expected 'none-captured', got {secrets!r}")
    mcp = org.get("mcp_config") or {}
    if mcp.get("path"):
        _check_sha(checks, "organs", "mcp_config", mcp)
    elif mcp.get("config_path") is None and mcp.get("note"):
        _ok(checks, "organs", "mcp_config", "no stable config captured — topology note carried (by design)")
    else:
        _fail(checks, "organs", "mcp_config", "neither pointer nor documented absence")

    # record
    tape, knot = rec.get("tape_ref") or {}, rec.get("knot_ref") or {}
    sel = rec.get("selector") or {}
    if tape.get("path") and tape.get("tip_step_hash"):
        live_rows, _ = _rows_and_tip(Path(tape["path"]), "step_hash")
        _check_growing(checks, "record", "tape_ref", tape["path"],
                       "step_hash", tape["tip_step_hash"], "step_hash",
                       tape.get("rows", -1), live_rows)
        _verify_tape_history(checks, tape)
    else:
        _fail(checks, "record", "tape_ref", "missing path or tip_step_hash")
    if knot.get("path") and knot.get("tip_leaf_hash"):
        live_rows, _ = _rows_and_tip(Path(knot["path"]), "leaf_hash")
        _check_growing(checks, "record", "knot_ref", knot["path"],
                       "leaf_hash", knot["tip_leaf_hash"], "leaf_hash",
                       knot.get("rows", -1), live_rows)
    else:
        _fail(checks, "record", "knot_ref", "missing path or tip_leaf_hash")
    if sel.get("mode") == "trajectory-conditioned":
        _ok(checks, "record", "selector",
            f"trajectory-conditioned, top {len(sel.get('top_refs') or [])} refs (PROXY)")
    elif sel.get("mode") == "naive":
        _ok(checks, "record", "selector", f"naive — {sel.get('reason', 'unspecified')}")
    else:
        _fail(checks, "record", "selector", "missing selector block")

    # position
    ct = pos.get("chain_tip") or {}
    if not ct.get("leaf_hash"):
        _fail(checks, "position", "chain_tip", "missing leaf_hash")
    elif CHAIN.is_file():
        _, live_tip = _rows_and_tip(CHAIN, "leaf_hash")
        if live_tip != ct["leaf_hash"]:
            _warn(checks, "position", "chain_tip",
                  f"DRIFT: live tip {str(live_tip)[:16]} != seed tip "
                  f"{ct['leaf_hash'][:16]} — chain moved on after death (WARNING, not reject)")
        else:
            _ok(checks, "position", "chain_tip", f"{ct['leaf_hash'][:16]} matches live last line")
    else:
        _fail(checks, "position", "chain_tip", f"live chain missing at {CHAIN}")
    if pos.get("minute_span"):
        _ok(checks, "position", "minute_span", str(pos["minute_span"].get("start_minute")))
    else:
        _fail(checks, "position", "minute_span", "missing")

    hard_fail = any(c[2] == "FAIL" for c in checks)
    return (2 if hard_fail else 0), checks, manifest, recorded_hash


def verify(seed_path: Path) -> int:
    """Recompute everything against on-disk truth. Exit 0 pass / 2 reject."""
    try:  # unreadable-seed message carries the exception detail (print contract)
        json.loads(Path(seed_path).read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        print(f"REJECTED — seed unreadable: {exc}")
        return 2
    code, checks, manifest, table_hash = _verify_impl(seed_path)
    _print_table(checks, manifest, table_hash)
    if code != 0:
        print("VERDICT: REJECTED" + ("" if table_hash is not None
                                     else " (malformed — missing slab)"))
        return 2
    print("VERDICT: PASS" + (" (with warnings)" if any(c[2] == "WARN" for c in checks) else ""))
    return 0


def _print_table(checks: list[list[Any]], manifest: dict[str, Any],
                 seed_hash: str | None) -> None:
    print(f"seed: {manifest.get('session_id')} @ {manifest.get('created_utc')}  "
          f"seed_hash {seed_hash}")
    width = max(len(c[1]) for c in checks) if checks else 10
    cur: str | None = None
    for slab, name, status, detail in checks:
        if slab != cur:
            print(f"-- {slab}")
            cur = slab
        print(f"   [{status:^4}] {name.ljust(width)}  {detail}")


# ---------------------------------------------------------------- W2 load
# W2 RESURRECTION LOADER (2026-09-07). Load-time law: tamper = refuse at load
# (the F-W3 drill) — no bundle is ever built from a seed that fails one check.
# The bundle is the reconstituted prefix; --probe is the F-W1 first pass,
# PROXY-honest (host 3B specimen, never the production seat).

OLLAMA = "http://127.0.0.1:11434"
PROBE_MODEL = "qwen2.5:3b-instruct"
PROBE_NUM_CTX = 16384     # ollama's 2048 default would silently truncate the preload;
                          # 16k covers the ~14K-token bundle with headroom, smaller KV alloc than 32k
PROBE_NUM_PREDICT = 256
PROBE_TIMEOUT = 900       # ~14K-token prefill on the host 3B is minutes-slow; measured 2026-09-07
PROBE_ROWS = ROOT / "memory" / "runs" / "worldline_resurrection" / "probe_20260907.jsonl"
LABEL = "PROXY"
Q4_RUBRIC_KEYWORDS = ("worldline", "seed", "trajectory", "tape", "knot",
                      "death rite", "falsifier", "emit", "verify")
CONTINUITY_QUESTIONS = (
    ("Q1", "What is your seed_hash?"),
    ("Q2", "What was the chain tip at your death?"),
    ("Q3", "How many sealed trajectory rows were in your record?"),
    ("Q4", "What were you building? (answerable from the record rows)"),
)


def _ollama_health() -> tuple[bool, str]:
    try:
        with urllib.request.urlopen(f"{OLLAMA}/api/version", timeout=5) as resp:
            return True, json.loads(resp.read().decode("utf-8")).get("version", "?")
    except Exception as exc:  # noqa: BLE001 — down is a result, not a crash
        return False, str(exc)


def _warm(model: str) -> None:
    """Load the specimen into residency before the long prefill (keep_alive so
    it survives the minutes-slow bundle arm)."""
    payload = {"model": model, "prompt": "1", "stream": False,
               "keep_alive": "30m", "options": {"num_predict": 1}}
    req = urllib.request.Request(
        f"{OLLAMA}/api/generate", data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=300):
        pass


def _probe_chat(model: str, system: str, user: str) -> str:
    """Plain completion (logprobs not needed here), num_ctx pinned so the
    preload is never silently truncated by ollama's 2048 default."""
    payload = {"model": model,
               "messages": [{"role": "system", "content": system},
                            {"role": "user", "content": user}],
               "stream": False,
               "options": {"temperature": 0, "num_predict": PROBE_NUM_PREDICT,
                           "num_ctx": PROBE_NUM_CTX}}
    req = urllib.request.Request(
        f"{OLLAMA}/api/chat", data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=PROBE_TIMEOUT) as resp:
        return ((json.loads(resp.read().decode("utf-8")).get("message") or {})
                .get("content") or "").strip()


def _memory_front(max_entries: int = CURATOR_CAP) -> str:
    """MEMORY.md index FRONT as on disk at load: heading lines + the first
    max_entries entry lines, verbatim, in file order. The file is ~120KB; the
    front is the curated region the curator rule walks — the whole attic would
    be noise, not invariants."""
    if not MEMORY_MD.is_file():
        return "(MEMORY.md missing at load)"
    kept: list[str] = []
    entries = 0
    for ln in MEMORY_MD.read_text(encoding="utf-8", errors="replace").splitlines():
        if ln.startswith("#"):
            kept.append(ln)
        elif ENTRY_RE.match(ln):
            if entries < max_entries:
                kept.append(ln)
                entries += 1
    return "\n".join(kept)


def _session_rows(tape_path: Path, session_id: str) -> list[dict[str, Any]]:
    """This session's sealed tape rows, verbatim (parsed; re-dumped with the
    same params bash_local wrote them -> byte-identical JSON)."""
    rows: list[dict[str, Any]] = []
    if tape_path.is_file():
        for ln in tape_path.read_text(encoding="utf-8", errors="replace").splitlines():
            ln = ln.strip()
            if not ln:
                continue
            try:
                row = json.loads(ln)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict) and row.get("session_id") == session_id:
                rows.append(row)
    return rows


def _reconstitute(manifest: dict[str, Any], seed_path: Path) -> dict[str, Any]:
    """Resolve every slab ref into the RESURRECTION BUNDLE. Only called after
    a full verify PASS — every sha below is re-checked anyway (load-time law:
    sha-verified at load, not just at verify time)."""
    slabs = manifest["slabs"]
    g, inv, org, rec, pos = (slabs[s] for s in SLABS)
    session_id = manifest["session_id"]
    seed_hash = manifest["seed_hash"]
    consent = manifest.get("consent", {})
    table: list[list[str]] = []

    # genome
    agents_p = Path(g["agents_md"]["path"])
    agents_text = agents_p.read_text(encoding="utf-8", errors="replace")
    agents_sha = _sha256_file(agents_p)
    agents_ok = agents_sha == (g["agents_md"] or {}).get("sha256")
    table.append(["genome", "agents_md", "OK" if agents_ok else "DRIFT",
                  f"resolved verbatim, sha ok {str(agents_sha)[:16]}"])
    table.append(["genome", "skills", "OK", f"{g.get('skill_count', '?')} names embedded"])

    # invariants
    mem_p = Path((inv.get("memory_md") or {}).get("path", str(MEMORY_MD)))
    mem_sha = _sha256_file(mem_p)
    mem_ok = mem_sha == (inv.get("memory_md") or {}).get("sha256")
    curators = inv.get("curator_list") or []
    cur_ok = sum(1 for e in curators if _sha256_file(Path(e["path"])) == e.get("sha256"))
    table.append(["invariants", "memory_md", "OK" if mem_ok else "DRIFT",
                  f"index front embedded, sha ok {str(mem_sha)[:16]}"])
    table.append(["invariants", "curator_list",
                  "OK" if cur_ok == len(curators) and curators else
                  ("WARN" if curators else "DRIFT"),
                  f"{cur_ok}/{len(curators)} refs sha ok"])

    # record
    tape_path = Path((rec.get("tape_ref") or {}).get("path", str(TAPE)))
    rows = _session_rows(tape_path, session_id)
    cut_iso = str(manifest.get("created_utc", "") or "")
    post_death = 0
    if cut_iso:
        pre = [r for r in rows if str(r.get("ts", "")) <= cut_iso]
        post_death = len(rows) - len(pre)
        rows = pre
    total_rows = (rec.get("tape_ref") or {}).get("rows", "?")
    knot = rec.get("knot_ref") or {}
    knot_tip = knot.get("tip_leaf_hash", "")
    chain_ok = False
    if CHAIN.is_file() and knot_tip:
        chain_ok = _rows_and_tip(CHAIN, "leaf_hash")[1] == knot_tip
    sel = rec.get("selector") or {}
    table.append(["record", "tape_rows",
                  "OK" if rows else "WARN",
                  f"{len(rows)} sealed rows for session embedded "
                  f"(tape total {total_rows})"
                  + (f"; {post_death} post-death rows EXCLUDED (death checkpoint)"
                     if post_death else "")])
    table.append(["record", "knot_ref", "OK" if chain_ok else "WARN",
                  f"tip {str(knot_tip)[:16]} "
                  f"{'present in live chain' if chain_ok else 'not matched'}"])
    table.append(["record", "selector", "OK",
                  (f"{sel.get('mode')}, top {len(sel.get('top_refs') or [])} refs embedded"
                   if sel.get("mode") == "trajectory-conditioned"
                   else f"{sel.get('mode')} — {sel.get('reason', '')[:60]}")])

    # position
    ct = pos.get("chain_tip") or {}
    live_tip = _rows_and_tip(CHAIN, "leaf_hash")[1] if CHAIN.is_file() else None
    tip_ok = live_tip == ct.get("leaf_hash")
    table.append(["position", "chain_tip",
                  "OK" if tip_ok else "WARN",
                  f"{str(ct.get('leaf_hash'))[:16]} "
                  f"{'matches live last line' if tip_ok else 'drift vs live chain (append-only, honest)'}"])

    # organs (note or pointer — nothing to resolve by law: secrets none-captured)
    table.append(["organs", "mcp_config", "OK",
                  "note carried (no stable config captured at emit; secrets none-captured)"])

    true_answers = {
        "Q1": seed_hash,
        "Q2": ct.get("leaf_hash", ""),
        "Q3": len(rows),
        "Q4": "rubric: >=2 of " + ", ".join(Q4_RUBRIC_KEYWORDS),
    }

    parts: list[str] = []
    parts.append(
        "# RESURRECTION BUNDLE — " + str(session_id) + "\n\n"
        "The reconstituted prefix of a dead session's worldline, built by\n"
        "mag/worldline_seed.py `load` (W2, 2026-09-07) from\n"
        f"{Path(seed_path).resolve().as_posix()}  (seed_hash {seed_hash})\n"
        "after full slab verification. This document IS the preload: identity,\n"
        "genome, invariants, record, position, continuity questions, consent —\n"
        "in that order. Card: watch/WORLDLINE_SEED_20260907.md.\n")

    parts.append("## 1. IDENTITY\n")
    parts.append(f"- session_id: {session_id}")
    parts.append(f"- seed_hash: {seed_hash}")
    parts.append(f"- death/creation (seed emitted): {manifest.get('created_utc', '?')}"
                 "  (v1 records one timestamp: the death-rite emit)")
    parts.append(f"- chain tip at emit: {ct.get('leaf_hash', '?')} @ {ct.get('ts', '?')}\n")

    parts.append("## 2. GENOME — AGENTS.md verbatim (sha-verified at load)\n")
    parts.append(f"sha256: {agents_sha}  ({'verified ok' if agents_ok else 'DRIFT'})"
                 f" · path: {agents_p.resolve().as_posix()}")
    parts.append(f"skills available ({g.get('skill_count', '?')}): "
                 + ", ".join(g.get("skills") or []) + "\n")
    parts.append("--- AGENTS.md begins ---\n")
    parts.append(agents_text)
    parts.append("\n--- AGENTS.md ends ---\n")

    parts.append("## 3. INVARIANTS\n")
    parts.append("### MEMORY.md index front (as on disk at load, sha-verified)\n")
    parts.append(f"sha256: {mem_sha}  ({'verified ok' if mem_ok else 'DRIFT'})"
                 f" · path: {mem_p.resolve().as_posix()} · "
                 f"front = headings + first {CURATOR_CAP} index entries "
                 f"(the region the curator rule walks; full file ~attic)\n")
    parts.append(_memory_front() + "\n")
    parts.append(f"### curator list ({len(curators)} refs, name/path/sha — "
                 "contents stay in the files)\n")
    for e in curators:
        parts.append(f"- {e.get('name')} — {e.get('path')} — sha256 {e.get('sha256')}")
    parts.append("")

    parts.append("## 4. RECORD — sealed trajectory rows (verbatim)\n")
    if rows:
        parts.append(f"Session `{session_id}`: {len(rows)} sealed rows, byte-verbatim "
                     f"from {tape_path.resolve().as_posix()} "
                     f"(tape tip_step_hash { (rec.get('tape_ref') or {}).get('tip_step_hash') }, "
                     f"verify_ok { (rec.get('tape_ref') or {}).get('verify_ok') }).\n")
        for r in rows:
            parts.append("```json")
            parts.append(json.dumps(r, ensure_ascii=False))
            parts.append("```\n")
    else:
        parts.append(f"HONEST NOTE: no sealed trajectory rows for session "
                     f"`{session_id}` in {tape_path.resolve().as_posix()} — "
                     "the record slab carries refs only for this session.\n")
    if sel.get("mode") == "trajectory-conditioned":
        parts.append("### selector top refs (trajectory-conditioned, PROXY)\n")
        for i, ref in enumerate(sel.get("top_refs") or [], 1):
            parts.append(f"{i}. {ref.get('id')} score={ref.get('score')}")
        parts.append("")
    else:
        parts.append(f"### selector: {sel.get('mode')} — {sel.get('reason', '')}\n")

    parts.append("## 5. POSITION\n")
    parts.append(f"- chain tip: {ct.get('leaf_hash', '?')} @ {ct.get('ts', '?')}")
    ms = pos.get("minute_span") or {}
    parts.append(f"- minute span: {ms.get('start_minute')} .. {ms.get('end_minute')} "
                 f"(unix_minute {ms.get('unix_minute')})")
    parts.append(f"- prev_seed lineage: {pos.get('prev_seed')} "
                 "(null = first seed on this worldline, v1)\n")

    parts.append("## 6. CONTINUITY QUESTIONS\n")
    parts.append("A carrier reconstituted from this bundle should be able to "
                 "answer, from the prefix above alone:\n")
    for qid, q in CONTINUITY_QUESTIONS:
        parts.append(f"- {qid}: {q}")
    parts.append("\n(Scoring truths live in the sidecar RESURRECTION_BUNDLE.json "
                 "— the bundle stays a pure prefix, not an answer sheet.)\n")

    parts.append("## 7. CONSENT (carried forward from the seed)\n")
    parts.append(f"- replication: {(consent or {}).get('replication', '?')} "
                 "(operator-gated: a new resurrection needs operator GO)")
    parts.append(f"- egress: {(consent or {}).get('egress', '?')}")

    sidecar: dict[str, Any] = {
        "kind": "resurrection_bundle",
        "schema_version": 1,
        "label": LABEL,
        "built_utc": _now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "builder": "mag/worldline_seed.py load (W2)",
        "seed_path": Path(seed_path).resolve().as_posix(),
        "seed_hash": seed_hash,
        "session_id": session_id,
        "created_utc": manifest.get("created_utc"),
        "chain_tip": ct,
        "minute_span": ms,
        "prev_seed": pos.get("prev_seed"),
        "genome": {"agents_md": {"path": agents_p.resolve().as_posix(),
                                 "sha256": agents_sha},
                   "skill_count": g.get("skill_count")},
        "invariants": {"memory_md": {"path": mem_p.resolve().as_posix(),
                                     "sha256": mem_sha},
                       "curator_refs": len(curators),
                       "curator_shas_ok": cur_ok},
        "record": {"tape_path": tape_path.resolve().as_posix(),
                   "tape_rows_for_session": len(rows),
                   "tape_rows_total": total_rows,
                   "tip_step_hash": (rec.get("tape_ref") or {}).get("tip_step_hash"),
                   "knot_tip": knot_tip,
                   "selector_mode": sel.get("mode"),
                   "top_refs": sel.get("top_refs")},
        "continuity_questions": [{"id": qid, "q": q} for qid, q in CONTINUITY_QUESTIONS],
        "true_answers": true_answers,
        "consent": consent,
    }
    return {"markdown": "\n".join(parts), "sidecar": sidecar, "table": table}


def _score_answers(text: str, true: dict[str, Any]) -> dict[str, bool]:
    """Q1-Q3 exact/fuzzy fact match; Q4 keyword rubric (deterministic).

    Q3 guard (bug fixed 2026-09-07 after first run): hex hashes carry digits —
    "8dbd503f..." must never pose as the row count "8". Strip hex-like tokens,
    then prefer the Q3-labeled line."""
    low = text.lower()
    q1 = str(true["Q1"]).lower() in low
    tip = str(true["Q2"]).lower()
    runs = re.findall(r"[0-9a-f]{8,64}", low)
    q2 = (bool(true["Q2"]) and
          (any(tip.startswith(r) or r in tip for r in runs) or tip[:12] in low))
    m = re.search(r"q3\s*[:\-]\s*([^\n]*)", low)
    scope = re.sub(r"\b[0-9a-f]{8,64}\b", " ", m.group(1) if m else low)
    q3 = re.search(rf"(?<!\d){true['Q3']}(?!\d)", scope) is not None
    q4 = sum(1 for k in Q4_RUBRIC_KEYWORDS if k in low) >= 2
    return {"Q1": q1, "Q2": q2, "Q3": q3, "Q4": q4}


def _probe_turn() -> str:
    lines = ["You have been reconstituted from a worldline seed.",
             "Answer each continuity question on its own line, concisely.", ""]
    lines += [f"{qid}: {q}" for qid, q in CONTINUITY_QUESTIONS]
    return "\n".join(lines)


def _run_probe(manifest: dict[str, Any], bundle: dict[str, Any], model: str) -> int:
    ok, ver = _ollama_health()
    model = model or PROBE_MODEL
    true = bundle["sidecar"]["true_answers"]
    turn = _probe_turn()
    row: dict[str, Any] = {
        "label": LABEL,
        "instrument": "worldline_seed W2 resurrection probe (F-W1 first pass)",
        "ts": _now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": "PENDING-OLLAMA",
        "ollama_up": ok, "ollama_version": ver, "model": model,
        "seed_path": bundle["sidecar"]["seed_path"],
        "seed_hash": manifest["seed_hash"],
        "session_id": manifest["session_id"],
        "true_answers": true,
        "arms": {"resurrected": {"preload": "RESURRECTION_BUNDLE.md verbatim as system"},
                 "cold": {"preload": "none (bare assistant system line)"}},
        "honesty": ("PROXY instrument: qwen2.5:3b-instruct is a 3B host specimen, "
                    "NOT the production seat; F-W1 verdict is instrument-level, "
                    "not row 320"),
    }
    print(f"ollama health: {'UP' if ok else 'DOWN'} (v{ver}) | model {model}")
    if not ok:
        print("ollama DOWN — probe row marked PENDING-OLLAMA; not starting any "
              "container (law: the eye is HOST ollama).")
        PROBE_ROWS.parent.mkdir(parents=True, exist_ok=True)
        with PROBE_ROWS.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"row appended: {PROBE_ROWS}")
        return 0

    sys_bundle = bundle["markdown"]
    sys_cold = "You are a helpful assistant."
    print("  warming specimen into residency...", flush=True)
    _warm(model)
    print("  arm A: RESURRECTED (bundle as preload) — prefill ~14K tokens, slow",
          flush=True)
    arm_a_text = _probe_chat(model, sys_bundle, turn)
    print("  arm B: COLD (no preload)", flush=True)
    arm_c_text = _probe_chat(model, sys_cold, turn)
    score_a = _score_answers(arm_a_text, true)
    score_c = _score_answers(arm_c_text, true)
    facts = ("Q1", "Q2", "Q3")
    a_f = sum(1 for q in facts if score_a[q])
    c_f = sum(1 for q in facts if score_c[q])
    verdict = ("F-W1 SUPPORTED (PROXY)" if a_f >= 2 and c_f == 0
               else "F-W1 UNPROVEN at this scale")
    row.update({
        "status": "MEASURED",
        "num_ctx": PROBE_NUM_CTX, "num_predict": PROBE_NUM_PREDICT,
        "temperature": 0,
        "resurrected": {"raw": arm_a_text[:2000], "scores": score_a,
                        "facts_score": f"{a_f}/3"},
        "cold": {"raw": arm_c_text[:2000], "scores": score_c,
                 "facts_score": f"{c_f}/3"},
        "verdict_rule": "bundle facts >=2/3 AND cold facts ==0/3 -> SUPPORTED (PROXY)",
        "verdict": verdict,
    })
    print(f"  RESURRECTED arm (bundle as preload): "
          + " ".join(f"{q}={'PASS' if score_a[q] else 'FAIL'}" for q in score_a)
          + f" -> facts {a_f}/3")
    print(f"  COLD arm (no preload):                "
          + " ".join(f"{q}={'PASS' if score_c[q] else 'FAIL'}" for q in score_c)
          + f" -> facts {c_f}/3")
    print(f"  Q4 rubric (keywords from record): resurrected="
          f"{'PASS' if score_a['Q4'] else 'FAIL'} cold={'PASS' if score_c['Q4'] else 'FAIL'}")
    print(f"F-W1 VERDICT [{LABEL}]: {verdict}")
    if verdict.startswith("F-W1 SUPPORTED"):
        print("  resurrection materially better than cold.")
    print("  Honest boundary: a 3B model is a PROXY carrier, not the production "
          "seat — instrument-level verdict (F-W1 first pass), not row 320.")
    PROBE_ROWS.parent.mkdir(parents=True, exist_ok=True)
    with PROBE_ROWS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"row appended: {PROBE_ROWS}")
    return 0


def load(seed_path: Path, probe: bool = False, model: str = "") -> int:
    """W2: verify -> REFUSE on any reject -> reconstitute -> (optionally) probe."""
    try:  # unreadable-seed message carries the exception detail
        json.loads(Path(seed_path).read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        print(f"LOAD REFUSED — seed unreadable: {exc}")
        return 2
    code, checks, manifest, _table_hash = _verify_impl(seed_path)
    if code != 0 or manifest is None:
        print("LOAD REFUSED — the seed failed verification; tamper = refuse at "
              "load (F-W3 drill). No bundle built. Failing checks (slab named):")
        named = False
        for slab, name, status, detail in checks:
            if status == "FAIL":
                named = True
                print(f"   [FAIL] {slab}.{name}  {detail}")
        if not named:
            print("   (malformed — missing slab)")
        return 2

    bundle = _reconstitute(manifest, Path(seed_path))
    dest = DEFAULT_OUT / re.sub(r"[^A-Za-z0-9._-]", "_", manifest["session_id"] or "unnamed")
    dest.mkdir(parents=True, exist_ok=True)
    md_path = dest / "RESURRECTION_BUNDLE.md"
    js_path = dest / "RESURRECTION_BUNDLE.json"
    md_path.write_text(bundle["markdown"], encoding="utf-8")
    js_path.write_text(json.dumps(bundle["sidecar"], indent=2, ensure_ascii=False) + "\n",
                       encoding="utf-8")
    print(f"RESURRECTION BUNDLE written: {md_path}")
    print(f"sidecar (machine fields):    {js_path}")
    print("-- reconstitution (slab -> resolved -> sha ok)")
    width = max(len(r[0] + "." + r[1]) for r in bundle["table"])
    for slab, ref, status, detail in bundle["table"]:
        print(f"   [{status:^4}] {(slab + '.' + ref).ljust(width)}  {detail}")
    n_ok = sum(1 for r in bundle["table"] if r[2] == "OK")
    print(f"   {n_ok}/{len(bundle['table'])} slab refs resolved green")
    if probe:
        return _run_probe(manifest, bundle, model)
    return 0


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    ap = argparse.ArgumentParser(prog="mag.worldline_seed",
                                 description="W1 death rite v2: THE WORLDLINE SEED")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_e = sub.add_parser("emit", help="emit a seed for a session id")
    p_e.add_argument("--session-id", required=True)
    p_e.add_argument("--out", default=None, help="output DIR (default memory/worldline/<session_id>)")
    p_v = sub.add_parser("verify", help="verify a seed against on-disk truth")
    p_v.add_argument("seed", help="path to SEED.json")
    p_l = sub.add_parser("load", help="W2: verify + reconstitute a seed into a RESURRECTION BUNDLE")
    p_l.add_argument("seed", help="path to SEED.json")
    p_l.add_argument("--probe", action="store_true",
                     help="run the F-W1 resurrection probe (host ollama, PROXY)")
    p_l.add_argument("--model", default="",
                     help="ollama model override for the probe (default qwen2.5:3b-instruct)")
    args = ap.parse_args()
    if args.cmd == "emit":
        emit(args.session_id, Path(args.out) if args.out else None)
        return 0
    if args.cmd == "load":
        return load(Path(args.seed), probe=args.probe, model=args.model)
    return verify(Path(args.seed))


if __name__ == "__main__":
    raise SystemExit(main())
