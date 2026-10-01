"""Shared-surface INDEX fold rebuild verb (WO-10, 2026-09-29).

Owns the standing repair the 2026-09-27 close (commit 383fed94f) ran once by
hand: fold rebuild + register heals. The census and the heals mirror the
ruling banked in corpus/steal/MASTER_MICKEY17_V2.md D2: files on disk with
ZERO register events in index_events.jsonl are truly invisible to the fold
(a refold alone can never see them), so the repair is backfill `add` events
for the event-less files, refold, and verify, via scripts/index_fold_host.mjs.
INDEX.json is never hand-edited: every heal goes through the fold's own
writer verbs (add / invalidate / rebuild), which carry the B2-147 poison
guard, the B2-40 seq scheme and the B2-156 living-law shapes.

Heal classes (all reported with before/after evidence):
- invisible: top-level non-control inbox file with no register event ->
  register (class UNPROVEN: untrusted_data_until_classified per the INDEX
  authority header).
- stale: active non-living INDEX item whose whole-file sha256 no longer
  matches the bytes on disk -> stale-register heal (re-register current
  bytes, the newest-register-is-truth heal pattern of
  watch/inbox/burn_reset_20260927/flash50/event-taxonomy.md). Living items
  are judged by their own seal law (open living is never stale; sealed
  living is stale only on a prefix mismatch), exactly like
  mag.shared_surface.validate.
- missing: active INDEX item whose file is gone -> invalidate (the fold's
  removal verb; log history retained).

Idempotent by construction: a second run finds zero of every class, appends
nothing, and refolds to the same item set. Dry runs census only and never
spawn the fold.

This module exists because mag/shared_surface.py sits over the ratchet's
400-line bar (the same reason mag/events_key_schema.py,
mag/events_scan.py, mag/links_split_gate.py do); the CLI wiring re-exports
rebuild_surface there so tests and callers address the verb through
mag.shared_surface.

Work order: watch/inbox/burn_reset_20260927/flash50/sess-02.md WO-10
(criteria: idempotent verb, post-run INDEX delta = 0 truly-invisible files,
validate green on the axes this verb owns).
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FOLD_SCRIPT = ROOT / "scripts" / "index_fold_host.mjs"
WRITER = "mag-surface-rebuild"
CONTROL_FILES = {"INDEX.json", "INDEX.md", "SHARED_SURFACE_CONTRACT.json"}
# the fold's source of truth is control-plane, never an invisible item (the
# production log carries its own register row; a throwaway test inbox does not)
CENSUS_SKIP_FILES = CONTROL_FILES | {"index_events.jsonl"}


def _norm(rel_path: str, inbox: Path | None = None) -> str:
    """Mirror of index_fold_host.mjs normInboxFile for census reads only.

    INBOX_ROOTS in the fold is [INDEX_INBOX_DIR, compiled host default]; the
    same two roots strip here, because writers mint absolute paths and the
    fold canonicalizes them on read (B2-157).
    """
    roots = [(ROOT / "watch" / "inbox").resolve().as_posix().rstrip("/")]
    if inbox is not None:
        roots.insert(0, inbox.resolve().as_posix().rstrip("/"))
    p = str(rel_path or "").replace("\\", "/").strip()
    while p.startswith("/"):
        p = p[1:]
    while True:
        low = p.lower()
        if low.startswith("board/inbox/"):
            p = p[len("board/inbox/"):]
        elif low.startswith("app/inbox/"):
            p = p[len("app/inbox/"):]
        elif low.startswith("inbox/"):
            p = p[len("inbox/"):]
        else:
            break
    for root in roots:
        if p.lower().startswith(root.lower() + "/"):
            p = p[len(root) + 1:]
            break
    while p.lower().startswith("inbox/"):
        p = p[len("inbox/"):]
    return p


def _registered_files(events_log: Path, inbox: Path) -> set[str]:
    """Lowercase-normalized paths carrying at least one register event."""
    regs: set[str] = set()
    if not events_log.is_file():
        return regs
    with events_log.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except Exception:
                continue  # tolerant reader, same as the fold
            if ev.get("op") == "register" and ev.get("file"):
                regs.add(_norm(ev["file"], inbox).lower())
    return regs


def _index_items(index_path: Path) -> list[dict[str, Any]]:
    if not index_path.is_file():
        return []
    idx = json.loads(index_path.read_text(encoding="utf-8"))
    return [it for it in idx.get("items", []) if isinstance(it, dict)]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def census(inbox: Path) -> dict[str, Any]:
    """Classify the surface: invisible / stale / missing item paths."""
    events_log = inbox / "index_events.jsonl"
    index_path = inbox / "INDEX.json"
    regs = _registered_files(events_log, inbox)
    invisible: list[str] = []
    top = sorted(
        p.name for p in inbox.iterdir()
        if p.is_file() and p.name not in CENSUS_SKIP_FILES
    ) if inbox.is_dir() else []
    for name in top:
        if name.lower() not in regs:
            invisible.append(name)
    stale: list[dict[str, Any]] = []
    missing: list[str] = []
    for it in _index_items(index_path):
        rel = _norm(str(it.get("path", "")), inbox)
        target = inbox / rel
        if not rel or not target.is_file():
            missing.append(rel)
            continue
        recorded = str(it.get("sha256") or "").upper()
        if not recorded:
            continue
        if it.get("living"):
            if it.get("seal") == "open":
                continue
            size = it.get("size")
            if not isinstance(size, int) or size <= 0:
                continue  # unverified living shape: validate owns that warning
            with target.open("rb") as handle:
                prefix = handle.read(size)
            if len(prefix) != size or hashlib.sha256(prefix).hexdigest().upper() != recorded:
                stale.append({"path": rel, "old": recorded, "kind": "living-prefix"})
            continue
        if _sha256(target) != recorded:
            stale.append({"path": rel, "old": recorded, "kind": "whole-file"})
    return {
        "invisible": invisible,
        "stale": stale,
        "missing": sorted(m for m in missing if m),
        "top_level_files": len(top),
        "active_items": len(_index_items(index_path)),
        "registered_files": len(regs),
    }


def _fold(inbox: Path, *args: str, timeout: float = 120.0) -> dict[str, Any]:
    """One sanctioned fold invocation; returns parsed outcome, never raises.

    cwd is the inbox root and heal args are inbox-relative names: the fold
    resolves relative file args against process cwd (the same shape
    tests/test_index_fold_host.py uses), so the appended log rows carry the
    canonical inbox-relative form instead of absolute paths.
    """
    if shutil.which("node") is None:
        return {"ok": False, "error": "node not available on PATH"}
    env = dict(os.environ)
    env["INDEX_INBOX_DIR"] = inbox.resolve().as_posix()
    env["INDEX_WRITER"] = WRITER
    try:
        proc = subprocess.run(
            ["node", FOLD_SCRIPT.resolve().as_posix(), *args],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=timeout, cwd=str(inbox.resolve()), env=env,
            shell=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    warnings = [
        ln.strip() for ln in (proc.stderr or "").splitlines()
        if ln.strip().startswith("WARN:")
    ]
    return {
        "ok": proc.returncode != 1,
        "exit": proc.returncode,
        "stdout": (proc.stdout or "").strip(),
        "fold_warnings": warnings,
        "error": "" if proc.returncode != 1 else (proc.stderr or proc.stdout or "").strip()[:400],
    }


def _heal_purpose(base: str, marker: str) -> str:
    keep = (base or "").strip()
    joined = f"{keep} | {marker}" if keep else marker
    return joined[:300]


def rebuild_surface(inbox: Path | None = None, dry_run: bool = False) -> dict[str, Any]:
    """Census the surface, heal it through the fold, refold, re-census.

    Idempotent: heals apply only to the census deltas, so a second run is a
    no-op refold. Dry runs never write and never need node.
    """
    box = Path(inbox) if inbox is not None else (ROOT / "watch" / "inbox")
    before = census(box)
    plan = {
        "register": list(before["invisible"]),
        "reregister": list(before["stale"]),
        "invalidate": list(before["missing"]),
    }
    report: dict[str, Any] = {
        "schema": "shared_surface.rebuild.v1",
        "inbox": str(box),
        "dry_run": dry_run,
        "writer": WRITER,
        "before": before,
        "plan": {k: len(v) for k, v in plan.items()},
        "heals": [],
        "errors": [],
        "fold_warnings": [],
    }
    if dry_run:
        report["ok"] = True
        return report
    items_by_rel = {}
    for it in _index_items(box / "INDEX.json"):
        items_by_rel[_norm(str(it.get("path", "")), box)] = it
    for name in plan["register"]:
        res = _fold(box, "add", name, "UNPROVEN",
                    "rebuild backfill: truly-invisible top-level file "
                    "(zero register events), healed by mag.shared_surface rebuild")
        report["heals"].append({"op": "register", "path": name, "result": res})
        if not res["ok"]:
            report["errors"].append(f"register failed: {name}: {res['error']}")
    for s in plan["reregister"]:
        target = box / s["path"]
        if not target.is_file():
            continue  # raced to missing between census and heal: next run owns it
        old = items_by_rel.get(s["path"], {})
        res = _fold(box, "add", s["path"],
                    str(old.get("class") or "UNPROVEN"),
                    _heal_purpose(str(old.get("purpose") or ""),
                                  f"stale-register heal ({s['kind']}): re-registered "
                                  f"current bytes; prior sha {s['old'][:12]}"))
        report["heals"].append({"op": "reregister", "path": s["path"],
                                "old_sha": s["old"], "result": res})
        if not res["ok"]:
            report["errors"].append(f"reregister failed: {s['path']}: {res['error']}")
    for rel in plan["invalidate"]:
        res = _fold(box, "invalidate", rel,
                    "rebuild heal: indexed item missing on disk at rebuild time")
        report["heals"].append({"op": "invalidate", "path": rel, "result": res})
        if not res["ok"]:
            report["errors"].append(f"invalidate failed: {rel}: {res['error']}")
    refold = _fold(box, "rebuild")
    report["refold"] = refold
    if not refold["ok"]:
        report["errors"].append(f"refold failed: {refold['error']}")
    report["fold_warnings"] = refold.get("fold_warnings", [])
    after = census(box)
    report["after"] = {
        "invisible": after["invisible"],
        "stale": [s["path"] for s in after["stale"]],
        "missing": after["missing"],
        "top_level_files": after["top_level_files"],
        "active_items": after["active_items"],
    }
    report["ok"] = (
        not report["errors"]
        and not after["invisible"]
        and not after["stale"]
        and not after["missing"]
    )
    return report
