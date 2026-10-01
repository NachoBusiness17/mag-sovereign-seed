"""seed_registry — W6: the provenance symbiote v1 — seed registry + load-time self-scan.

Card: watch/WORLDLINE_SEED_20260907.md §3 door 2 + ladder W6: "seed registry +
self-scan before load — forged lineage refuses." The worldline seed is a
PROVENANCE-CHAINED SYMBIOTE: hash lineage (seed_hash -> slabs -> chain tips),
replication consent operator-gated. SkillSpector (NVIDIA) scans third-party
skills for injection/theft/supply-chain risk pre-install; this is the LAWFUL
MIRROR pointed at our own body — we scan OUR seeds for provenance breaks and
foreign-pointer risks before anything reconstitutes from them. $0-local, files
only, no docker/config/secrets.

COMMANDS
  register [SEED_PATH...]   run the full scan per seed, then append one
                            hash-chained registry row per seed to
                            memory/worldline/REGISTRY.jsonl. No paths = every
                            memory/worldline/*/SEED.json on disk. Rows chain via
                            prev_reg_hash (grounding_wave style), so "the
                            registry knows it" is a checkable claim. REFUSE
                            verdicts are RECORDED too (append-only provenance
                            history) but set exit 2.
  scan <SEED_PATH...>       the pre-load self-scan (SkillSpector mirror,
                            lawful). Four lenses, verdict PASS /
                            PASS-WITH-FLAGS / REFUSE, exit 0 / 2:
    PROVENANCE  seed_hash recomputed over the canonical manifest (excluding
                seed_hash) + every slab/file sha against on-disk truth. Runs
                mag.worldline_seed._verify_impl (the W1 contract) when
                importable; else an independent MIRROR checker (same shas,
                marked MIRROR). INTEGRITY breaks (manifest edited, seed_hash
                mismatch, missing slab/file, truncated tape/chain) = REFUSE.
                LIVING-FILE DRIFT (manifest intact — seed_hash recomputes —
                but a snapshot sha no longer matches disk because the body
                moved on after the death-rite emit) = REVIEW flag: snapshot
                staleness, not forgery; W1/W2 load-time law still refuses to
                reconstitute until the seed is re-minted, and the scan is
                never silent about it.
    LINEAGE     the seed's position.chain_tip.leaf_hash must EXIST in
                memory/biography/verkle_chain.jsonl, or in a prior registry
                row. A tip that exists nowhere = forged lineage = REFUSE.
    FOREIGN     every path-like string in the manifest must live INSIDE our
                body: the workspace root (C:/Users/foste/Documents/projects)
                or the memory dir worldline_seed indexes (MEMORY.md's dir).
                Anything else = FOREIGN flag = REFUSE. The symbiote only
                points at its own body.
    HYGIENE     the seed must be hashes/pointers/metadata only. Any string
                field >200 chars is REVIEW-flagged (location, length,
                head/tail snippet — never silent). Allowlisted verbatim
                blocks inside SEED.json: none in v1. The AGENTS.md verbatim
                embed is lawful in the W2 RESURRECTION_BUNDLE (that bundle IS
                the genome being reconstituted, sha-checked at load), NOT in
                the seed manifest, which stays pointers-only.
  verify                    recompute the registry's own hash chain (W0-style
                            PASS/FAIL line).

W2 INTEGRATION SEAM (deliberately UN-WIRED): mag/worldline_seed.py `load`
(the W2 resurrection loader) should call `mag.seed_registry.scan_manifest`
BEFORE reconstituting — any REFUSE = no bundle, tamper dies at the door.
W6 leaves that call site unwired and does NOT modify worldline_seed.py
(read-only for this lane; another builder owns it and may be mid-extension).

Falsifier battery (specimens live in memory/runs/seed_registry/, NEVER under
memory/worldline/ — the register default glob must stay clean):
  (i)   the real W1 seed -> PASS.
  (ii)  forged seed with a foreign path in a slab ref -> REFUSE (FOREIGN).
        Both a naive forgery (hash left stale) and a REHASHED forgery (seed_hash
        honestly recomputed, so only the foreign lens can catch it) are forged.
  (iii) a seed with a stuffed ~5KB free-text field -> PASS-WITH-FLAGS (REVIEW),
        never silent.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
WORKSPACE_ROOT = ROOT.parent                                # .../Documents/projects
WORLDLINE_DIR = ROOT / "memory" / "worldline"
REGISTRY = WORLDLINE_DIR / "REGISTRY.jsonl"
CHAIN = ROOT / "memory" / "biography" / "verkle_chain.jsonl"
SCHEMA_VERSION = 1
GENESIS = "0" * 16
HYGIENE_LIMIT = 200
SLABS = ("genome", "invariants", "organs", "record", "position")
REFUSE_CLASSES = ("PROVENANCE", "LINEAGE", "FOREIGN")

try:  # W1 contract import — read-only; W6 never modifies worldline_seed.py
    from mag import worldline_seed as w1  # type: ignore
except Exception:  # noqa: BLE001 — mid-extension/partial file: mirror takes over
    w1 = None  # type: ignore

MEMORY_DIR = (w1.MEMORY_DIR if w1 is not None else
              Path.home() / ".zcode" / "cli" / "memories" / "projects" /
              "projects-0fb5e3041b59db21" / "memory")

ABS_PATH_RE = re.compile(r"^([A-Za-z]:[\\/].*|/(?:Users|home)/.*|file://.*|\\\\.*)$")
PATH_KEY_RE = re.compile(r"(^|_)path$")
# W1 FAIL details that mean integrity break / provenance destruction rather
# than living-file drift (drift = manifest intact, snapshot shas stale).
_INTEGRITY_MARKERS = ("RECORDED", "MISSING SLAB", "file missing on disk",
                      "NOT FOUND in live file", "SHRANK", "missing path or",
                      "missing tip", "missing leaf_hash",
                      "expected worldline_seed")


# ------------------------------------------------------------------ primitives

def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False)


def _seed_hash(manifest: dict[str, Any]) -> str:
    """MIRROR of W1's seed_hash (same canonical form) — second belt."""
    core = {k: v for k, v in manifest.items() if k != "seed_hash"}
    return hashlib.sha256(_canonical(core).encode("utf-8")).hexdigest()[:16]


def _sha256_file(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def _norm(p: str) -> str:
    path = Path(p)
    if not path.is_absolute():
        path = ROOT / path
    try:
        resolved = path.resolve()
    except OSError:
        resolved = path.absolute()
    return resolved.as_posix().lower().rstrip("/")


def _allowlist() -> list[str]:
    return [_norm(str(WORKSPACE_ROOT)), _norm(str(MEMORY_DIR))]


def _is_inside_body(path_s: str, allow: list[str]) -> bool:
    n = _norm(path_s)
    return any(n == a or n.startswith(a + "/") for a in allow)


def _walk_strings(node: Any, prefix: str = ""):
    if isinstance(node, dict):
        for k, v in node.items():
            yield from _walk_strings(v, f"{prefix}.{k}" if prefix else str(k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _walk_strings(v, f"{prefix}[{i}]")
    elif isinstance(node, str):
        yield prefix, node


def _walk_dicts(node: Any, prefix: str = ""):
    if isinstance(node, dict):
        yield prefix, node
        for k, v in node.items():
            yield from _walk_dicts(v, f"{prefix}.{k}" if prefix else str(k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _walk_dicts(v, f"{prefix}[{i}]")


def _flag(cls: str, at: str, detail: str) -> dict[str, str]:
    return {"cls": cls, "at": at, "detail": detail[:200]}


# ------------------------------------------------------------------- the lenses

def _mirror_provenance(manifest: dict[str, Any]) -> list[dict[str, str]]:
    """Independent sha checker used only when mag.worldline_seed is not
    importable. Same checks W1 makes, marked MIRROR."""
    flags: list[dict[str, str]] = []
    if manifest.get("kind") != "worldline_seed":
        flags.append(_flag("PROVENANCE", "kind",
                           f"expected worldline_seed, got {manifest.get('kind')!r} (MIRROR)"))
    if manifest.get("schema_version") != SCHEMA_VERSION:
        flags.append(_flag("PROVENANCE", "schema_version",
                           f"expected {SCHEMA_VERSION}, got {manifest.get('schema_version')!r} (MIRROR)"))
    slabs = manifest.get("slabs") or {}
    for name in SLABS:
        if not isinstance(slabs.get(name), dict) or not slabs[name]:
            flags.append(_flag("PROVENANCE", f"slabs.{name}",
                               "MISSING SLAB = malformed (MIRROR)"))
    if any(f["at"].startswith("slabs.") for f in flags):
        return flags
    if manifest.get("seed_hash") != _seed_hash(manifest):
        flags.append(_flag("PROVENANCE", "seed_hash",
                           f"RECORDED {manifest.get('seed_hash')} != RECOMPUTED "
                           f"{_seed_hash(manifest)} — manifest edited (MIRROR)"))
    for loc, node in _walk_dicts(manifest):
        if isinstance(node.get("path"), str) and isinstance(node.get("sha256"), str):
            live = _sha256_file(Path(node["path"]))
            if live != node.get("sha256"):
                if manifest.get("seed_hash") == _seed_hash(manifest) \
                        and Path(node["path"]).is_file():
                    flags.append(_flag(
                        "REVIEW", loc,
                        f"living-file drift since emit (manifest intact): sha mismatch "
                        f"recorded={str(node.get('sha256'))[:16]} live={str(live)[:16]} "
                        f"(MIRROR)"))
                else:
                    flags.append(_flag("PROVENANCE", loc,
                                       f"sha mismatch recorded={str(node.get('sha256'))[:16]} "
                                       f"live={str(live)[:16]} (MIRROR)"))
    return flags


def _lens_provenance(seed_path: Path, manifest: dict[str, Any] | None
                     ) -> tuple[list[dict[str, str]], str, dict[str, int]]:
    stats = {"prov_checks": 0, "prov_warns": 0, "prov_fails": 0, "prov_drift": 0}
    if manifest is None:
        return [_flag("PROVENANCE", "file", f"seed unreadable as JSON: {seed_path.name}")], \
            "none (unreadable)", stats
    mirror_ok = manifest.get("seed_hash") == _seed_hash(manifest)
    mirror_hash = "OK" if mirror_ok else "MISMATCH"

    def classify(detail: str, at: str) -> dict[str, str]:
        if mirror_ok and not any(m in detail for m in _INTEGRITY_MARKERS):
            stats["prov_drift"] += 1
            return _flag("REVIEW", at,
                         f"living-file drift since emit (manifest intact, seed_hash "
                         f"recomputes — staleness, not forgery; W1 load law still "
                         f"refuses until re-mint): {detail}")
        return _flag("PROVENANCE", at, detail)

    if w1 is not None:
        try:
            _code, checks, _m, _h = w1._verify_impl(seed_path)
            stats["prov_checks"] = len(checks)
            stats["prov_warns"] = sum(1 for c in checks if c[2] == "WARN")
            fails = [c for c in checks if c[2] == "FAIL"]
            flags = [classify(str(c[3]), f"{c[0]}.{c[1]}") for c in fails]
            stats["prov_fails"] = len(fails) - stats["prov_drift"]
            source = (f"mag.worldline_seed._verify_impl (W1 contract), "
                      f"seed_hash mirror recompute {mirror_hash}")
            return flags, source, stats
        except Exception as exc:  # noqa: BLE001 — W1 mid-extension: mirror takes over
            source = f"W1 import raised {type(exc).__name__}: MIRROR; seed_hash mirror {mirror_hash}"
    else:
        source = f"MIRROR (w1 not importable); seed_hash mirror recompute {mirror_hash}"
    return _mirror_provenance(manifest), source, stats


def _lens_lineage(manifest: dict[str, Any]) -> tuple[list[dict[str, str]], str]:
    tip = (((manifest.get("slabs") or {}).get("position") or {})
           .get("chain_tip") or {})
    leaf = tip.get("leaf_hash")
    if not leaf:
        return [_flag("LINEAGE", "position.chain_tip",
                      "missing leaf_hash — the seed claims no lineage at all")], ""
    if CHAIN.is_file():
        for i, ln in enumerate(
                CHAIN.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            ln = ln.strip()
            if not ln:
                continue
            try:
                row = json.loads(ln)
            except json.JSONDecodeError:
                continue  # repo files are data: malformed lines are skipped
            if isinstance(row, dict) and row.get("leaf_hash") == leaf:
                return [], f"tip {str(leaf)[:16]} found in verkle chain line {i}"
    for row in _registry_rows():
        if row.get("chain_tip") == leaf:
            return [], (f"tip {str(leaf)[:16]} known to registry row "
                        f"{str(row.get('reg_hash'))[:16]}")
    return [_flag("LINEAGE", "position.chain_tip",
                  f"tip {str(leaf)[:16]} exists NOWHERE (chain + registry) — "
                  f"forged lineage")], str(leaf)


def _lens_foreign(manifest: dict[str, Any]) -> tuple[list[dict[str, str]], int]:
    """Every path-keyed value and every absolute-path-looking string must be
    inside the body: workspace root or the memory dir. Relative non-path
    strings (notes naming watch/... cards) are workspace-relative by
    convention and are not foreign pointers."""
    allow = _allowlist()
    flags: list[dict[str, str]] = []
    scanned = 0
    for loc, s in _walk_strings(manifest):
        key = loc.rsplit(".", 1)[-1].split("[", 1)[0]
        keyed = bool(PATH_KEY_RE.search(key)) and bool(s.strip())
        looks_abs = bool(ABS_PATH_RE.match(s))
        if not (keyed or looks_abs):
            continue
        scanned += 1
        if not _is_inside_body(s, allow):
            flags.append(_flag("FOREIGN", loc, f"path outside the body: {s}"))
    return flags, scanned


def _lens_hygiene(manifest: dict[str, Any]) -> tuple[list[dict[str, str]], int]:
    flags: list[dict[str, str]] = []
    scanned = 0
    for loc, s in _walk_strings(manifest):
        scanned += 1
        if len(s) > HYGIENE_LIMIT:
            flags.append(_flag(
                "REVIEW", loc,
                f"string field {len(s)} chars (> {HYGIENE_LIMIT}) — seed must be "
                f"hashes/pointers/metadata only; head={s[:80]!r} tail={s[-40:]!r}"))
    return flags, scanned


# ------------------------------------------------------------------ registry io

def _registry_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if REGISTRY.is_file():
        for ln in REGISTRY.read_text(encoding="utf-8", errors="replace").splitlines():
            ln = ln.strip()
            if not ln:
                continue
            try:
                row = json.loads(ln)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                rows.append(row)
    return rows


def _registry_row_hash(row: dict[str, Any]) -> str:
    core = {k: v for k, v in row.items() if k != "reg_hash"}
    return hashlib.sha256(_canonical(core).encode("utf-8")).hexdigest()[:16]


# ------------------------------------------------------------------- scan core

def scan_manifest(seed_path: Path) -> dict[str, Any]:
    """The four-lens pre-load scan. Machine-readable, writes nothing —
    this is the W2 seam: worldline_seed.load should call this before
    reconstituting and refuse on verdict REFUSE (integration un-wired)."""
    seed_path = Path(seed_path)
    manifest: dict[str, Any] | None = None
    try:
        loaded = json.loads(seed_path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            manifest = loaded
    except Exception:  # noqa: BLE001 — unreadable is a provenance flag, not a crash
        manifest = None

    prov_flags, prov_source, prov_stats = _lens_provenance(seed_path, manifest)
    flags = list(prov_flags)
    lineage_note, foreign_n, hygiene_n = "", 0, 0
    foreign_flags: list[dict[str, str]] = []
    hygiene_flags: list[dict[str, str]] = []
    if manifest is not None:
        lin_flags, lineage_note = _lens_lineage(manifest)
        flags += lin_flags
        foreign_flags, foreign_n = _lens_foreign(manifest)
        flags += foreign_flags
        hygiene_flags, hygiene_n = _lens_hygiene(manifest)
        flags += hygiene_flags

    verdict = "REFUSE" if any(f["cls"] in REFUSE_CLASSES for f in flags) else (
        "PASS-WITH-FLAGS" if flags else "PASS")
    slabs = (manifest or {}).get("slabs") or {}
    slab_shas = {name: hashlib.sha256(
        _canonical(slabs[name]).encode("utf-8")).hexdigest()[:16]
        for name in SLABS if isinstance(slabs.get(name), dict)}
    return {
        "ts": _now(),
        "seed_path": seed_path.resolve().as_posix(),
        "session_id": (manifest or {}).get("session_id", "?"),
        "seed_hash": (manifest or {}).get("seed_hash", "?"),
        "chain_tip": (((slabs.get("position") or {}).get("chain_tip") or {})
                      .get("leaf_hash", "")),
        "verdict": verdict,
        "flags": flags,
        "slab_shas": slab_shas,
        "lens": {"provenance_source": prov_source, **prov_stats,
                 "lineage_note": lineage_note,
                 "foreign_refs_scanned": foreign_n,
                 "foreign_flagged": len(foreign_flags),
                 "string_fields_scanned": hygiene_n,
                 "hygiene_flagged": len(hygiene_flags)},
    }


def print_card(card: dict[str, Any]) -> None:
    print(f"SCAN CARD — {card['seed_path']}")
    print(f"  session {card['session_id']} · seed_hash {card['seed_hash']} · "
          f"chain_tip {str(card['chain_tip'])[:16] or '-'}")
    lens = card["lens"]
    print(f"  [PROVENANCE] {lens['prov_fails']} integrity FAIL / "
          f"{lens['prov_drift']} living-drift / {lens['prov_warns']} WARN "
          f"of {lens['prov_checks']} checks — {lens['provenance_source']}")
    print(f"  [LINEAGE]    {lens['lineage_note'] or 'no lineage claim'}")
    print(f"  [FOREIGN]    {lens['foreign_refs_scanned']} path refs scanned, "
          f"{lens['foreign_flagged']} outside body "
          f"(allow: workspace root + memory dir)")
    print(f"  [HYGIENE]    {lens['string_fields_scanned']} string fields scanned, "
          f"{lens['hygiene_flagged']} over {HYGIENE_LIMIT} chars")
    for f in card["flags"]:
        print(f"  FLAG[{f['cls']}] {f['at']}: {f['detail']}")
    print(f"  verdict: {card['verdict']}")


def cmd_scan(paths: list[Path]) -> int:
    if not paths:
        print("usage: python -m mag.seed_registry scan <SEED.json> [...]")
        return 1
    code = 0
    for p in paths:
        card = scan_manifest(p)
        print_card(card)
        if card["verdict"] == "REFUSE":
            code = 2
    return code


def cmd_register(paths: list[Path]) -> int:
    if not paths:
        paths = sorted(WORLDLINE_DIR.glob("*/SEED.json"))
    if not paths:
        print(f"no seeds found under {WORLDLINE_DIR.as_posix()}/*/SEED.json")
        return 1
    rows = _registry_rows()
    prev = rows[-1].get("reg_hash", GENESIS) if rows else GENESIS
    code = 0
    new = 0
    for p in paths:
        card = scan_manifest(p)
        print_card(card)
        row: dict[str, Any] = {
            "kind": "seed_registry_row",
            "schema_version": SCHEMA_VERSION,
            "ts": card["ts"],
            "seed_path": card["seed_path"],
            "session_id": card["session_id"],
            "seed_hash": card["seed_hash"],
            "chain_tip": card["chain_tip"],
            "verdict": card["verdict"],
            "flags": card["flags"],
            "reasons": [f["detail"] for f in card["flags"]] or ["all four lenses green"],
            "slab_shas": card["slab_shas"],
            "lens": card["lens"],
            "prev_reg_hash": prev,
        }
        row["reg_hash"] = _registry_row_hash(row)
        REGISTRY.parent.mkdir(parents=True, exist_ok=True)
        with REGISTRY.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"  registered -> REGISTRY.jsonl reg_hash {row['reg_hash']} "
              f"(prev {row['prev_reg_hash']})")
        prev = row["reg_hash"]
        new += 1
        if card["verdict"] == "REFUSE":
            code = 2
    rows = _registry_rows()
    print(f"registry: {new} new row(s), {len(rows)} total, tip "
          f"{str(rows[-1].get('reg_hash'))[:16] if rows else GENESIS}")
    return code


def cmd_verify_registry() -> int:
    rows = _registry_rows()
    if not rows:
        print(f"FAIL registry empty or absent: {REGISTRY}")
        return 1
    prev = GENESIS
    bad: list[str] = []
    for i, row in enumerate(rows, 1):
        if row.get("prev_reg_hash") != prev:
            bad.append(f"row {i}: prev_reg_hash {str(row.get('prev_reg_hash'))[:16]} "
                       f"!= {str(prev)[:16]} (chain broken)")
        if _registry_row_hash(row) != row.get("reg_hash"):
            bad.append(f"row {i}: reg_hash mismatch (row edited in place)")
        prev = row.get("reg_hash", prev)
    tip = str(rows[-1].get("reg_hash"))
    msg = f"{len(rows)} rows, tip={tip} on {REGISTRY.name}"
    if bad:
        print("FAIL " + msg + " | " + "; ".join(bad[:8]))
        return 1
    counts: dict[str, int] = {}
    for row in rows:
        counts[row.get("verdict", "?")] = counts.get(row.get("verdict", "?"), 0) + 1
    print("PASS " + msg + " | chain intact | verdicts: "
          + ", ".join(f"{k}={v}" for k, v in counts.items()))
    return 0


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    ap = argparse.ArgumentParser(
        prog="mag.seed_registry",
        description="W6 provenance symbiote: seed registry + load-time self-scan")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_r = sub.add_parser("register", help="scan + append hash-chained registry rows")
    p_r.add_argument("seeds", nargs="*", help="SEED.json paths (default: memory/worldline/*/SEED.json)")
    p_s = sub.add_parser("scan", help="pre-load self-scan (SkillSpector mirror, lawful)")
    p_s.add_argument("seeds", nargs="+", help="SEED.json paths")
    sub.add_parser("verify", help="recompute the registry's own hash chain")
    args = ap.parse_args()
    if args.cmd == "scan":
        return cmd_scan([Path(s) for s in args.seeds])
    if args.cmd == "register":
        return cmd_register([Path(s) for s in args.seeds])
    return cmd_verify_registry()


if __name__ == "__main__":
    raise SystemExit(main())
