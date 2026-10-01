"""catalog -- the estate's one-catalog navigation layer.

The law (operator, 2026-09-16): everything should be ONE directory, split apart
into groups via CATALOGING, not via a million recreated folder schemes. The
physical location is history; the catalog is the map. Groups are VIEWS over the
catalog, never folders you have to hike through.

Design:
  store/          the forward store: new artifacts land here (date-prefixed)
  catalog.jsonl   append-only rows: one per known file
  relations.jsonl append-only rows: one per relationship between files

Each catalog row:
  {id, path, sha12, bytes, mtime, zone, ext, title}

  id      = sha256(path)[:12]  (stable while the path is stable)
  zone    = intake | doctrine | runs | basecamp | campaigns | code | registry |
            personal | external | vault  (derived from path; the VIEW key)

Commands:
  python -m mag.catalog scan [--roots a,b] [--max N]   index files into catalog
  python -m mag.catalog find --q TERM [--zone Z] [--since 2026-09-15]
  python -m mag.catalog show <id>
  python -m mag.catalog stats

Deterministic, read-only over the files, $0.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CATALOG = os.path.join(ROOT, "catalog", "catalog.jsonl")

ZONES = [
    ("watch/inbox", "intake"),
    ("watch/astra_hold0", "astra"),
    ("watch", "watch"),
    ("basecamp", "basecamp"),
    ("campaigns", "campaigns"),
    ("docs", "doctrine"),
    ("memory/runs", "runs"),
    ("memory", "memory"),
    ("mag", "code"),
    ("tests", "code"),
    ("scripts", "code"),
    ("configs", "code"),
    ("dashboard/static/games", "games"),
    ("dashboard", "dashboard"),
    ("research", "research"),
    ("queue", "queue"),
    ("registry", "registry"),
]

EXCLUDE = {".git", ".venv", "node_modules", "__pycache__", ".mimosa",
           "catalog", "data", "logs"}


def zone_of(path: str) -> str:
    p = path.replace("\\", "/").lower()
    for prefix, zone in ZONES:
        if p.startswith(prefix.lower()):
            return zone
    return "vault"


def title_of(path: str) -> str:
    name = os.path.basename(path)
    base, ext = os.path.splitext(name)
    if ext.lower() in (".md", ".txt"):
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    line = line.strip()
                    if line.startswith("#"):
                        return line.lstrip("# ").strip()[:110]
                    if line:
                        return line[:110]
        except OSError:
            pass
    return base


def iter_files(roots: list[str], cap_per_root: int = 20000):
    seen = 0
    for root in roots:
        rp = os.path.join(ROOT, root) if not os.path.isabs(root) else root
        if not os.path.isdir(rp):
            continue
        for dp, dns, fns in os.walk(rp):
            dns[:] = [d for d in dns if d not in EXCLUDE and not d.startswith(".")]
            for fn in fns:
                full = os.path.join(dp, fn)
                if seen >= cap_per_root:
                    return
                if os.path.isfile(full) and not os.path.islink(full):
                    seen += 1
                    yield full


def cmd_scan(roots: list[str], cap: int) -> dict:
    rows = 0
    with open(CATALOG, "a", encoding="utf-8", newline="\n") as cat:
        for full in iter_files(roots, cap):
            rel = os.path.relpath(full, ROOT)
            try:
                st = os.stat(full)
            except OSError:
                continue
            h = hashlib.sha256(rel.encode("utf-8", "replace")).hexdigest()[:12]
            row = {"id": h, "path": rel.replace("\\", "/"),
                   "bytes": st.st_size,
                   "mtime": datetime.datetime.fromtimestamp(
                       st.st_mtime, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                   "zone": zone_of(rel), "ext": os.path.splitext(rel)[1].lower(),
                   "title": title_of(full)}
            cat.write(json.dumps(row, ensure_ascii=False) + "\n")
            rows += 1
    return {"scanned": rows, "catalog": CATALOG}


def load_rows() -> list[dict]:
    if not os.path.isfile(CATALOG):
        return []
    rows = []
    for ln in open(CATALOG, encoding="utf-8", errors="replace"):
        ln = ln.strip()
        if not ln:
            continue
        try:
            rows.append(json.loads(ln))
        except Exception:
            continue
    # dedupe: latest row per (path) wins
    best = {}
    for r in rows:
        best[r["path"]] = r
    return list(best.values())


def cmd_find(q: str | None, zone: str | None, since: str | None) -> None:
    rows = load_rows()
    for r in sorted(rows, key=lambda r: r["mtime"], reverse=True):
        if zone and r["zone"] != zone:
            continue
        if since and r["mtime"] < since:
            continue
        if q and q.lower() not in (r["path"] + " " + r["title"]).lower():
            continue
        print(f"{r['id']}  {r['mtime'][:10]}  {r['zone']:10s}  {r['path']}")


def cmd_stats() -> None:
    rows = load_rows()
    zones: dict[str, int] = {}
    for r in rows:
        zones[r["zone"]] = zones.get(r["zone"], 0) + 1
    print("catalog rows:", len(rows))
    for z, n in sorted(zones.items(), key=lambda kv: -kv[1]):
        print(f"  {z:12s} {n}")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="catalog")
    ap.add_argument("cmd", choices=["scan", "find", "show", "stats"])
    ap.add_argument("--roots", default="watch/inbox,basecamp,docs,memory/runs,campaigns,registry")
    ap.add_argument("--max", type=int, default=40000)
    ap.add_argument("--q")
    ap.add_argument("--zone")
    ap.add_argument("--since")
    ap.add_argument("target", nargs="?")
    a = ap.parse_args(argv)
    if a.cmd == "scan":
        print(json.dumps(cmd_scan(a.roots.split(","), a.max)))
    elif a.cmd == "find":
        cmd_find(a.q, a.zone, a.since)
    elif a.cmd == "show":
        for r in load_rows():
            if r["id"].startswith(a.target):
                print(json.dumps(r, ensure_ascii=False, indent=1))
    else:
        cmd_stats()
    return 0


if __name__ == "__main__":
    main(sys.argv[1:])
