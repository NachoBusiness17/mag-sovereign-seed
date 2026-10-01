"""SPAWN MANIFEST — the consumed-sources organ (GAP-1 closure, Astra chain).

Gap (astra_gap_v2_20260906 / memory_orphans.md): "the archive cannot reliably
supply its own precedents" — 92% of MEMORY.md's pointers are phantom, and a
fresh seat cannot PROVE what it did or did not read (the August brief went
unread while the fleet answered it by accident).

This organ closes the smallest version of that gap, two ways:

1. MANIFEST (consumed-sources law): every spawn/brief records what it consumed.
   `python -m mag.spawn_manifest record --sources file1,file2 --session <id>`
   appends {ts, session, sources[], note} to memory/runs/spawn_manifest.jsonl.
   Falsifier this enables ("fresh seat misses the August brief"): a fresh
   seat's manifest either CONTAINS the brief or PROVABLY never saw it.

2. ANTI-PHANTOM CHECK: verify a brief's referenced files resolve.
   `python -m mag.spawn_manifest check --brief <path>`
   extracts every file reference (slash paths + bare filenames with known
   extensions), resolves each (literal at repo root, literal relative to the
   brief, then basename walk across memory/ then the repo, heavy dirs pruned),
   and lists the PHANTOMS — references to rooms that were never built.
   Exit 0 = all resolve; exit 1 = phantoms found.

3. POINTER REPAIR (additive, MEMORY.md is SEALED — never edited):
   `python -m mag.spawn_manifest resolve` rebuilds memory/MEMORY_resolved.md,
   a resolved index: every MEMORY.md link row whose target exists (basename-
   resolved across memory/ as needed), one line per row with the RESOLVED
   path and the via-method; unresolvable rows land in the PHANTOMS (forensic)
   footer. Additive only — the sealed index is evidence, not garbage.

$0, deterministic, no network, no daemons. Append-only ledger.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / "memory" / "runs" / "spawn_manifest.jsonl"
DEFAULT_INDEX = ROOT / "memory" / "MEMORY.md"
DEFAULT_RESOLVED = ROOT / "memory" / "MEMORY_resolved.md"

GENESIS = "0" * 16

# Known file extensions a reference must end with to count as a file ref.
FILE_EXTS = {
    ".md", ".py", ".json", ".jsonl", ".csv", ".yaml", ".yml", ".txt", ".html",
    ".htm", ".js", ".ts", ".sh", ".cmd", ".ps1", ".bat", ".bak", ".log",
    ".tsv", ".ini", ".cfg", ".toml", ".db", ".png", ".svg", ".ipynb",
}

# Directories never walked during basename resolution (size/irrelevance prune).
PRUNE_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", ".zcode",
    "mine", "seals", "traces", "trash", ".ruff_cache", ".mypy_cache",
}

# Per-session state dumps under memory/ (100k+ files each): literal paths
# still resolve through them, but a BASENAME match there is noise (e.g.
# LATEST.json exists 33k times) — excluded from the basename walk only.
MEMORY_NOISE_SUBDIRS = {"ghost", "biography", "agent_state", "agent_sessions", "mail"}

# A slash-path or a bare filename with a known extension.
PATH_TOKEN_RE = re.compile(
    r"(?:[A-Za-z0-9_\-\.]+/)+[A-Za-z0-9_\-\.\*]+"
    r"|(?<![\w/\-\.])[A-Za-z0-9_\-]+\.(?:" 
    + "|".join(ext.lstrip(".") for ext in sorted(FILE_EXTS))
    + r")(?![\w/])"
)
MD_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


# ---------------------------------------------------------------- basename index
def _is_memory_noise_dir(parent: str, name: str) -> bool:
    mem_root = os.path.normcase(str(ROOT / "memory"))
    if os.path.normcase(parent) != mem_root:
        return False
    return name in MEMORY_NOISE_SUBDIRS or name.startswith("biography_backup")


def _walk_files(base: Path):
    """Yield files under base, pruning heavy/irrelevant dirs. Deterministic
    (scandir + per-dir name sort)."""
    stack: list[str] = [str(base)]
    while stack:
        d = stack.pop()
        try:
            with os.scandir(d) as it:
                entries = sorted(it, key=lambda e: e.name)
        except OSError:
            continue
        for e in entries:
            try:
                if e.is_dir(follow_symlinks=False):
                    if e.name in PRUNE_DIRS or _is_memory_noise_dir(d, e.name):
                        continue
                    stack.append(e.path)
                elif e.is_file(follow_symlinks=False):
                    yield Path(e.path)
            except OSError:
                continue


# One shared walk snapshot (name -> [relative posix paths]) — built lazily,
# O(repo) ONCE per process, then O(1) lookups per reference.
_SNAPSHOT: dict[str, list[str]] | None = None


def _snapshot() -> dict[str, list[str]]:
    """Map basename -> sorted list of repo-relative posix paths, memory/ first."""
    global _SNAPSHOT
    if _SNAPSHOT is None:
        buckets: dict[str, list[str]] = {}
        for p in _walk_files(ROOT):
            rel = p.relative_to(ROOT).as_posix()
            buckets.setdefault(p.name, []).append(rel)
        for name, rels in buckets.items():
            # memory/ matches sort first, then shortest path, then lexicographic
            rels.sort(key=lambda r: (not r.startswith("memory/"), len(r), r))
        _SNAPSHOT = buckets
    return _SNAPSHOT


def _basename_candidates(name: str) -> list[Path]:
    """All files under ROOT whose basename matches, memory/ matches first."""
    return [ROOT / rel for rel in _snapshot().get(name, [])]


def resolve_ref(ref: str, brief_dir: Path | None = None) -> tuple[Path | None, str]:
    """Resolve one file reference. Returns (path or None, via-method)."""
    ref_clean = ref.rstrip("*/").strip()
    if not ref_clean:
        return None, "empty"
    # 1. literal, relative to repo root
    cand = ROOT / ref_clean
    if cand.exists():
        return cand, "literal-root"
    # 2. literal, relative to the brief's own directory
    if brief_dir is not None:
        cand = brief_dir / ref_clean
        if cand.exists():
            return cand, "literal-briefdir"
    # 3. literal, relative to memory/ (briefs often speak memory-relative)
    cand = ROOT / "memory" / ref_clean
    if cand.exists():
        return cand, "literal-memory"
    # 4. basename walk (memory/ first, then repo)
    base = Path(ref_clean).name
    hits = _basename_candidates(base)
    if hits:
        return hits[0], "basename-memory" if hits[0].parts[1] == "memory" else "basename-repo"
    return None, "phantom"


# ---------------------------------------------------------------- commands
def cmd_record(args: argparse.Namespace) -> int:
    sources = [s.strip() for s in args.sources.split(",") if s.strip()]
    if not sources:
        raise SystemExit("record: --sources must name at least one consumed file")
    row = {
        "ts": _now(),
        "session": args.session.strip(),
        "sources": sources,
        "note": (args.note or "").strip(),
    }
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"recorded: session={row['session']} sources={len(sources)} -> {LEDGER.relative_to(ROOT)}")
    for s in sources:
        print(f"  - {s}")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    brief = Path(args.brief)
    if not brief.is_absolute():
        brief = ROOT / brief
    if not brief.exists():
        raise SystemExit(f"check: brief not found: {brief}")
    text = brief.read_text(encoding="utf-8", errors="replace")
    raw_tokens = PATH_TOKEN_RE.findall(text)

    refs: list[str] = []
    seen: set[str] = set()
    for tok in raw_tokens:
        t = tok.strip()
        if t.lower().startswith(("http://", "https://")):
            continue
        last = Path(t.rstrip("*/")).name
        has_ext = Path(last).suffix.lower() in FILE_EXTS
        is_dir_glob = t.endswith("/*") or t.endswith("*")
        if "/" in t:
            if not (has_ext or is_dir_glob):
                continue  # endpoint-ish or identifier path, not a file ref
        else:
            if not has_ext:
                continue
        if t not in seen:
            seen.add(t)
            refs.append(t)

    resolved: list[tuple[str, Path, str]] = []
    phantoms: list[str] = []
    for ref in refs:
        path, via = resolve_ref(ref, brief_dir=brief.parent)
        if path is not None:
            resolved.append((ref, path, via))
        else:
            phantoms.append(ref)

    print(f"SPAWN MANIFEST check — {brief.relative_to(ROOT)}")
    print(f"  file refs: {len(refs)}  resolved: {len(resolved)}  PHANTOMS: {len(phantoms)}")
    print("  resolved:")
    for ref, path, via in resolved:
        print(f"    + {ref} -> {path.relative_to(ROOT).as_posix()} ({via})")
    if phantoms:
        print("  PHANTOMS (referenced but resolve to no file):")
        for ref in phantoms:
            print(f"    - {ref}")
    print(f"  verdict: {'PHANTOMS PRESENT' if phantoms else 'ALL RESOLVE'}")
    return 1 if phantoms else 0


def _resolve_link_target(target: str, brief_dir: Path | None = None) -> tuple[Path | None, str]:
    return resolve_ref(target, brief_dir=brief_dir)


def cmd_resolve(args: argparse.Namespace) -> int:
    index = Path(args.index)
    if not index.is_absolute():
        index = ROOT / index
    out = Path(args.out)
    if not out.is_absolute():
        out = ROOT / out
    if not index.exists():
        raise SystemExit(f"resolve: index not found: {index}")

    lines = index.read_text(encoding="utf-8", errors="replace").splitlines()
    rows: list[dict] = []
    seen_rows: set[tuple[str, str]] = set()
    for lineno, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped.startswith("- "):
            continue
        for title, target in MD_LINK_RE.findall(line):
            if target.lower().startswith(("http://", "https://", "mailto:")):
                continue
            target = target.split("#", 1)[0]
            if not target:
                continue
            key = (title, target)
            if key in seen_rows:
                continue
            seen_rows.add(key)
            path, via = _resolve_link_target(target, brief_dir=index.parent)
            rows.append({"lineno": lineno, "title": title, "target": target,
                         "path": path, "via": via})

    resolved_rows = [r for r in rows if r["path"] is not None]
    phantom_rows = [r for r in rows if r["path"] is None]
    uniq_resolved = {r["target"] for r in resolved_rows}
    uniq_phantom = {r["target"] for r in phantom_rows}

    out_lines: list[str] = []
    out_lines.append("# MEMORY_resolved — resolved index (pointer repair, GAP-1)")
    out_lines.append("")
    out_lines.append(f"Generated: {_now()} · Source: memory/MEMORY.md (SEALED — untouched) · "
                     "Generator: `python -m mag.spawn_manifest resolve`")
    out_lines.append(f"Resolved: **{len(resolved_rows)} of {len(rows)} link rows** "
                     f"({len(uniq_resolved)} unique targets) · "
                     f"Phantoms: **{len(phantom_rows)} rows** ({len(uniq_phantom)} unique targets)")
    out_lines.append("")
    out_lines.append("Law: ADDITIVE ONLY. memory/MEMORY.md is sealed forensic evidence "
                     "(astra_gap_v2 salon verdict) — this index repairs pointers by existing "
                     "beside it, never by editing it. Resolution order: literal at repo root, "
                     "literal under memory/, then basename walk across memory/ then the repo "
                     "(heavy dirs pruned).")
    out_lines.append("")
    out_lines.append("## RESOLVED")
    out_lines.append("")
    for r in resolved_rows:
        rp = r["path"].relative_to(ROOT).as_posix()
        out_lines.append(f"- [{r['title']}]({r['target']}) → `{rp}` "
                         f"(via {r['via']}, MEMORY.md:L{r['lineno']})")
    out_lines.append("")
    out_lines.append("## PHANTOMS (forensic)")
    out_lines.append("")
    out_lines.append("Referenced but no file resolves anywhere under memory/ or the repo — "
                     "index-only rows: rooms never built, or moved without re-pointing. "
                     "Keep: this is the gap's own map, not garbage.")
    out_lines.append("")
    for r in phantom_rows:
        out_lines.append(f"- [{r['title']}]({r['target']}) — MEMORY.md:L{r['lineno']} — phantom")
    out_lines.append("")
    out_lines.append("---")
    out_lines.append(f"Run by seat `spawnman` (GAP-1 closure build, 2026-09-06). "
                     f"Re-run: `python -m mag.spawn_manifest resolve`.")
    out_lines.append("")
    out.write_text("\n".join(out_lines), encoding="utf-8")
    print(f"wrote {out.relative_to(ROOT)}: "
          f"resolved {len(resolved_rows)}/{len(rows)} rows "
          f"({len(uniq_resolved)} unique targets), "
          f"phantoms {len(phantom_rows)} rows ({len(uniq_phantom)} unique targets)")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="mag.spawn_manifest", description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_rec = sub.add_parser("record", help="append consumed sources to the spawn manifest ledger")
    p_rec.add_argument("--sources", required=True, help="comma-separated consumed files")
    p_rec.add_argument("--session", required=True, help="session/spawn id")
    p_rec.add_argument("--note", default="", help="optional note")
    p_rec.set_defaults(func=cmd_record)

    p_chk = sub.add_parser("check", help="anti-phantom check: verify a brief's referenced files exist")
    p_chk.add_argument("--brief", required=True, help="path to the brief/document to check")
    p_chk.set_defaults(func=cmd_check)

    p_res = sub.add_parser("resolve", help="rebuild memory/MEMORY_resolved.md (additive pointer repair)")
    p_res.add_argument("--index", default=str(DEFAULT_INDEX.relative_to(ROOT)))
    p_res.add_argument("--out", default=str(DEFAULT_RESOLVED.relative_to(ROOT)))
    p_res.set_defaults(func=cmd_resolve)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
