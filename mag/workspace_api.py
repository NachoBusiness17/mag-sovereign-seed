"""Safe workspace file access for Sovereign Shell (editor under Mag ROOT)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from config import ROOT

TEXT_SUFFIXES = {
    ".md", ".txt", ".json", ".jsonl", ".yaml", ".yml", ".py", ".js", ".css",
    ".html", ".cmd", ".ps1", ".sh", ".toml", ".mdc", ".rhai",
}
SKIP_DIRS = {".git", ".venv", "__pycache__", "node_modules", ".cursor"}


def _safe_rel(rel: str) -> Path | None:
    r = (rel or "").replace("\\", "/").strip().lstrip("/")
    if not r or ".." in r.split("/"):
        return None
    path = (ROOT / r).resolve()
    try:
        path.relative_to(ROOT.resolve())
    except ValueError:
        return None
    return path


def list_tree(rel: str = "", *, max_depth: int = 2, max_entries: int = 400) -> dict[str, Any]:
    base = _safe_rel(rel) if rel else ROOT.resolve()
    if base is None:
        return {"ok": False, "error": "bad path"}
    if not base.is_dir():
        return {"ok": False, "error": "not a directory"}
    entries: list[dict[str, Any]] = []

    def walk(d: Path, depth: int) -> None:
        if len(entries) >= max_entries or depth > max_depth:
            return
        try:
            children = sorted(d.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except OSError:
            return
        for p in children:
            if len(entries) >= max_entries:
                break
            if p.name.startswith(".") and p.name not in {".cursor"}:
                continue
            if p.is_dir() and p.name in SKIP_DIRS:
                continue
            try:
                rel_p = str(p.relative_to(ROOT.resolve())).replace("\\", "/")
            except ValueError:
                continue
            entries.append({
                "name": p.name,
                "path": rel_p,
                "type": "dir" if p.is_dir() else "file",
            })
            if p.is_dir() and depth < max_depth:
                walk(p, depth + 1)

    walk(base, 0)
    root_rel = "" if base == ROOT.resolve() else str(base.relative_to(ROOT.resolve())).replace("\\", "/")
    return {"ok": True, "root": root_rel, "entries": entries}


def read_file(rel: str, *, max_bytes: int = 500_000) -> dict[str, Any]:
    path = _safe_rel(rel)
    if path is None:
        return {"ok": False, "error": "bad path"}
    if not path.is_file():
        return {"ok": False, "error": "not found", "path": rel}
    if path.suffix.lower() not in TEXT_SUFFIXES and path.suffix:
        return {"ok": False, "error": "binary or unsupported type"}
    try:
        raw = path.read_bytes()
    except OSError as e:
        return {"ok": False, "error": str(e)[:200]}
    if len(raw) > max_bytes:
        return {"ok": False, "error": f"file too large ({len(raw)} bytes)"}
    text = raw.decode("utf-8", errors="replace")
    return {
        "ok": True,
        "path": rel.replace("\\", "/").lstrip("/"),
        "text": text,
        "sha256": None,
    }


def write_file(rel: str, text: str) -> dict[str, Any]:
    path = _safe_rel(rel)
    if path is None:
        return {"ok": False, "error": "bad path"}
    if path.suffix.lower() not in TEXT_SUFFIXES and path.suffix:
        return {"ok": False, "error": "unsupported type for shell save"}
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text or "", encoding="utf-8")
    except OSError as e:
        return {"ok": False, "error": str(e)[:200]}
    return {"ok": True, "path": str(path.relative_to(ROOT.resolve())).replace("\\", "/"), "bytes": len(text or "")}
