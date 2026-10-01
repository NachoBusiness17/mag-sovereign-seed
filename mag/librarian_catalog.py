"""librarian_catalog — the record of the record (2026-09-23, operator: "we have no
real record and a million files"). Sibling organ to librarian.py (v1, the bibliography
auditor): that one audits citations; THIS one catalogs the holdings. Deterministic,
$0, no LLM.

Tiers (the LIBRARIAN rib's law):
  CURATED shelves get catalog rows: file count, bytes, extension histogram,
  oldest/newest mtime, and any README first line as the shelf's own description.
  BULK layers get counts and size buckets only — gravel is counted, not cataloged.
  CANON gets MANIFEST.sha256 verification — the real-record test: if the canon's
  own hash manifest drifts, the report says so first.

Ledgers (append-only):
  state/library/catalog.jsonl        one row per shelf per run
  state/library/catalog_runs.jsonl   one row per run
  CORPUS_CATALOG.md                  the human record, rewritten each run

CLI: python -m mag.librarian_catalog --once | --verify | --status
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CATALOG_JSONL = ROOT / "state" / "library" / "catalog.jsonl"
RUNS_JSONL = ROOT / "state" / "library" / "catalog_runs.jsonl"
CATALOG_MD = ROOT / "CORPUS_CATALOG.md"
CANON = ROOT / "corpus" / "canon"

CURATED = [
    ("canon", ROOT / "corpus" / "canon"),
    ("ractor_ribs", ROOT / "corpus" / "ractor_ribs"),
    ("tartaria_lives", ROOT / "corpus" / "tartaria_lives"),
    ("telegram", ROOT / "corpus" / "telegram"),
    ("oral_history", ROOT / "corpus" / "oral_history"),
    ("game_estate", ROOT / "corpus" / "game_estate"),
    ("frontier_thinking", ROOT / "corpus" / "frontier_thinking"),
    ("library", ROOT / "corpus" / "library"),
    ("watch_inbox", ROOT / "watch" / "inbox"),
    ("docs_ref", ROOT / "docs" / "ref"),
    ("handoff", ROOT / "handoff"),
]
BULK = [
    ("attic", ROOT / "attic"),
    ("logs", ROOT / "logs"),
    ("state", ROOT / "state"),
    ("mag", ROOT / "mag"),
]

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def shelf_row(name: str, path: Path, max_files: int = 200_000) -> dict:
    files = 0
    total = 0
    exts: dict[str, int] = {}
    oldest = None
    newest = None
    if path.is_dir():
        stop = False
        for dirpath, _dirnames, filenames in os.walk(path):
            for fn in filenames:
                files += 1
                if files > max_files:
                    stop = True
                    break
                fp = Path(dirpath) / fn
                try:
                    st = fp.stat()
                    total += st.st_size
                    mt = st.st_mtime
                    oldest = mt if oldest is None else min(oldest, mt)
                    newest = mt if newest is None else max(newest, mt)
                except OSError:
                    continue
                ext = fp.suffix.lower()[:12] or "(none)"
                exts[ext] = exts.get(ext, 0) + 1
            if stop:
                break
    desc = ""
    for cand in (path / "README.md", path / "readme.md"):
        if cand.is_file():
            try:
                desc = cand.read_text(encoding="utf-8", errors="replace").splitlines()[0][:140]
            except Exception:
                pass
            break

    def iso(mt):
        return datetime.fromtimestamp(mt, tz=timezone.utc).date().isoformat() if mt else None

    return {"shelf": name, "path": str(path), "files": files, "bytes": total,
            "top_exts": sorted(exts.items(), key=lambda kv: -kv[1])[:6],
            "oldest": iso(oldest), "newest": iso(newest), "desc": desc, "ts": _now()}


def bulk_row(name: str, path: Path) -> dict:
    files = 0
    total = 0
    if path.is_dir():
        for dirpath, _dn, fns in os.walk(path):
            files += len(fns)
            for fn in fns:
                try:
                    total += (Path(dirpath) / fn).stat().st_size
                except OSError:
                    pass
    return {"shelf": name, "files": files, "bytes": total, "ts": _now()}


def verify_canon() -> dict:
    mf = CANON / "MANIFEST.sha256"
    if not mf.is_file():
        return {"ok": False, "why": "no MANIFEST.sha256 in canon"}
    lines = mf.read_text(encoding="utf-8", errors="replace").splitlines()
    checked = 0
    missing = 0
    drifted = 0
    for line in lines:
        if not line.strip():
            continue
        parts = line.split(None, 1)
        if len(parts) != 2:
            continue
        want, rel = parts[0], parts[1].strip().lstrip("*")
        if len(want) != 64 or any(c not in "0123456789abcdef" for c in want.lower()):
            continue  # seal headers and comment lines are not hash rows
        fp = CANON / rel
        h = hashlib.sha256(fp.read_bytes()).hexdigest()
        checked += 1
        if h != want:
            drifted += 1
    return {"ok": missing == 0 and drifted == 0, "manifest_rows": len(lines),
            "checked": checked, "missing": missing, "drifted": drifted}


def run_once() -> dict:
    curated = [shelf_row(n, p) for n, p in CURATED]
    bulk = [bulk_row(n, p) for n, p in BULK]
    canon = verify_canon()
    run = {"ts": _now(), "canon_verify": canon, "curated_shelves": len(curated),
           "total_files_curated": sum(r["files"] for r in curated),
           "total_bytes_curated": sum(r["bytes"] for r in curated)}
    CATALOG_JSONL.parent.mkdir(parents=True, exist_ok=True)
    for layer in (curated, bulk):
        with CATALOG_JSONL.open("a", encoding="utf-8") as f:
            for r in layer:
                f.write(json.dumps(r) + "\n")
    RUNS_JSONL.parent.mkdir(parents=True, exist_ok=True)
    with RUNS_JSONL.open("a", encoding="utf-8") as f:
        f.write(json.dumps(run) + "\n")

    lines = [
        "# CORPUS CATALOG — the record of the record",
        "",
        "Run " + _now(),
        "",
        "**CANON MANIFEST: " + ("VERIFIED (" + str(canon["checked"]) + " hashes match)" if canon.get("ok")
         else "DRIFT — checked " + str(canon.get("checked", 0)) + ", missing " + str(canon.get("missing", 0))
              + ", drifted " + str(canon.get("drifted", 0)) + " — resolve before trusting the shelves") + "**",
        "",
        "## Curated shelves",
        "",
        "| shelf | files | MB | oldest | newest | top types |",
        "|---|---|---|---|---|---|",
    ]
    for r in curated:
        lines.append("| " + r["shelf"] + " | " + str(r["files"]) + " | "
                     + str(round(r["bytes"] / 1e6, 1)) + " | " + str(r["oldest"]) + " | "
                     + str(r["newest"]) + " | " + ", ".join(e for e, _ in r["top_exts"]) + " |")
    lines += ["", "## Bulk layers (counts only)", "", "| layer | files | GB |", "|---|---|---|"]
    for r in bulk:
        lines.append("| " + r["shelf"] + " | " + str(r["files"]) + " | " + str(round(r["bytes"] / 1e9, 2)) + " |")
    lines += ["", "*Append-only ledgers: state/library/catalog.jsonl · catalog_runs.jsonl. "
              "The Librarian records; it never cleans.*", ""]
    CATALOG_MD.write_text("\n".join(lines), encoding="utf-8")
    return run


def status() -> dict:
    runs = RUNS_JSONL.read_text(encoding="utf-8", errors="replace").splitlines() if RUNS_JSONL.is_file() else []
    last = json.loads(runs[-1]) if runs else None
    return {"runs": len(runs), "last": last, "catalog_md": CATALOG_MD.is_file()}


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--status" in args:
        print(json.dumps(status(), indent=1))
    elif "--verify" in args:
        print(json.dumps(verify_canon(), indent=1))
    else:
        print(json.dumps(run_once(), indent=1))
