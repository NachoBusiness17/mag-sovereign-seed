"""Cursor Canvas → Mag dashboard bridge.

Reads *.canvas.tsx (or companion .canvas.data.json) from external canvas dirs,
writes memory/viewports/<slug>.json manifests, and upserts lattice nodes.
Does not execute TypeScript.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT

VIEWPORTS_DIR = ROOT / "memory" / "viewports"
LATTICE_NODES = ROOT / "memory" / "lattice" / "nodes.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canvas_sources() -> list[Path]:
    """External canvas dirs — set CANVAS_SOURCES (semicolon-separated paths)."""
    raw = os.environ.get("CANVAS_SOURCES", "").strip()
    if not raw:
        return []
    parts = [p.strip() for p in re.split(r"[;,]", raw) if p.strip()]
    return [Path(p).expanduser().resolve() for p in parts]


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _slug_from_path(path: Path) -> str:
    name = path.name
    if name.endswith(".canvas.tsx"):
        return name[: -len(".canvas.tsx")]
    if name.endswith(".canvas.data.json"):
        return name[: -len(".canvas.data.json")]
    return path.stem


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (json.JSONDecodeError, OSError):
        return None


def _strip_ts_noise(text: str) -> str:
    text = re.sub(r"\s+as\s+const\b", "", text)
    return text


def _find_const_block(src: str, name: str) -> str | None:
    m = re.search(rf"const\s+{re.escape(name)}\s*=\s*", src)
    if not m:
        return None
    i = m.end()
    while i < len(src) and src[i] in " \t\n\r":
        i += 1
    if i >= len(src) or src[i] not in "[{":
        return None
    open_ch, close_ch = src[i], {"[": "]", "{": "}"}[src[i]]
    depth = 0
    j = i
    in_str: str | None = None
    escape = False
    while j < len(src):
        ch = src[j]
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == in_str:
                in_str = None
        elif ch in ("'", '"', "`"):
            in_str = ch
        elif ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                return src[i : j + 1]
        j += 1
    return None


def _parse_string_rows(block: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for row_m in re.finditer(r"\[([^\[\]]*(?:\[[^\[\]]*\][^\[\]]*)*)\]", block):
        inner = row_m.group(1)
        cells = re.findall(r'"((?:\\.|[^"\\])*)"', inner)
        if cells:
            rows.append([c.replace('\\"', '"') for c in cells])
    return rows


def _parse_todo_items(block: str) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for obj_m in re.finditer(r"\{[^{}]+\}", block):
        chunk = _strip_ts_noise(obj_m.group(0))
        id_m = re.search(r'id:\s*"([^"]+)"', chunk)
        content_m = re.search(r'content:\s*"((?:\\.|[^"\\])*)"', chunk)
        status_m = re.search(r'status:\s*"([^"]+)"', chunk)
        if not content_m:
            continue
        items.append(
            {
                "id": id_m.group(1) if id_m else "",
                "content": content_m.group(1).replace('\\"', '"'),
                "status": status_m.group(1) if status_m else "pending",
            }
        )
    return items


def _extract_title(src: str) -> str:
    m = re.search(r"<H1>([^<]+)</H1>", src)
    if m:
        return m.group(1).strip()
    fn = re.search(r"function\s+(\w+)", src)
    if fn:
        return re.sub(r"([a-z])([A-Z])", r"\1 \2", fn.group(1)).strip()
    return "Canvas viewport"


def _extract_stats(src: str) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for m in re.finditer(
        r'<Stat\s+label="([^"]+)"\s+value="([^"]+)"', src
    ):
        items.append({"label": m.group(1), "value": m.group(2)})
    return items


def _extract_usage_stats(src: str) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for m in re.finditer(
        r'topLeftLabel="([^"]+)"', src
    ):
        label = m.group(1)
        pct_m = re.search(r"value:\s*(\d+)", src[m.end() : m.end() + 120])
        value = f"{pct_m.group(1)}%" if pct_m else "—"
        items.append({"label": label, "value": value})
    return items


def _manifest_mag_ecosystem_deep_dive(source_tsx: str) -> dict[str, Any]:
    """Full manifest for the known ecosystem canvas (parser + curated sections)."""
    repo_rows = [
        ["local_sovereign_agent", "Product home — Mag harness", ":8765 / :8000", "done"],
        ["sovereign-mirror-scaffold", "Strike desk — lattice / chord / 3D", ":8743", "done"],
        ["mag-sovereign-kit", "Public fork kit (law + skeleton)", "—", "done"],
        ["mycelial-republic", "Training soil — QLoRA / seed-mirror", "—", "partial"],
    ]
    seat_rows = [
        ["L0", "Janitor", "Ollama gemma:2b", "Route, ask, status", "yes"],
        ["L0", "Worker", "Ollama gemma4", "Short bursts", "yes"],
        ["L2", "Grok TUI", "xAI harness", "Scarce judgment", "yes"],
        ["L2", "DeepSeek agent", "DeepSeek + tools", "REPL + orchestrator", "yes"],
        ["L2", "Cursor IDE", "Composer", "Multi-file + hooks", "partial"],
        ["L2", "Hermes", "Parked", "Long autonomous", "no"],
        ["L3", "Human", "wait", "Secrets", "yes"],
    ]
    done = [
        {"id": "a", "content": "Phase A–D steering engine (streaming, steer, collapse guard)", "status": "completed"},
        {"id": "b", "content": "Launch stack — mag_launch, stop_mag, dashboard :8765", "status": "completed"},
        {"id": "c", "content": "Mirror mag_bridge — read Mag verkle on :8743", "status": "completed"},
        {"id": "d", "content": "Cursor seat — hooks, preamble, dispatch route", "status": "completed"},
        {"id": "e", "content": "12h sovereign run — 70+ pytest passed", "status": "completed"},
    ]
    todo = [
        {"id": "t1", "content": "multi-smoke PASS after lanes fix (clerk gemma:2b)", "status": "pending"},
        {"id": "t2", "content": "Manual REPL verify — !steer / !pause in terminal", "status": "pending"},
        {"id": "t3", "content": "W0.0 X archive → mycelial-republic/data/raw/", "status": "pending"},
        {"id": "t4", "content": "Wire governor.py into CLI loop (B5 seam)", "status": "pending"},
        {"id": "t5", "content": "Co-launch Mirror :8743 from Start Everything", "status": "pending"},
        {"id": "t6", "content": "Verify Cursor hooks → Verkle leaf on session end", "status": "pending"},
    ]
    gap_rows = [
        ["Governor not wired", "mag/governor.py", "agent_cli loop", "high"],
        ["Two desks manual", ":8765 Mag", ":8743 Mirror", "medium"],
        ["Republic blocked", "mycelial-republic", "W0.0 archive", "high"],
        ["Drainer opt-in", "orchestrator queue", "MAG_DRAINER=1", "medium"],
    ]
    launch_rows = [
        ["backend", "python -m backend.server", ":8000"],
        ["dashboard", "python main.py dashboard", ":8765"],
        ["scribe", "synthesis_agent.py", "commentary"],
        ["drainer", "orchestrator drain", "MAG_DRAINER=1"],
    ]
    return {
        "schema": "canvas_viewport.v1",
        "id": "mag-ecosystem-deep-dive",
        "title": "Mag / Sovereign Mirror — ecosystem map",
        "source_tsx": source_tsx,
        "synced_at": _now(),
        "sections": [
            {
                "kind": "stats",
                "title": "Ports",
                "items": [
                    {"label": "Mag dashboard", "value": ":8765"},
                    {"label": "Tool backend", "value": ":8000"},
                    {"label": "Mirror desk", "value": ":8743"},
                ],
            },
            {
                "kind": "stats",
                "title": "Progress by layer",
                "items": [
                    {"label": "Stabilize body", "value": "85%"},
                    {"label": "Seat coherence", "value": "70%"},
                    {"label": "Republic soil", "value": "25%"},
                ],
            },
            {
                "kind": "table",
                "title": "Repository puzzle pieces",
                "columns": ["Repo", "Role", "Port", "Status"],
                "rows": repo_rows,
            },
            {
                "kind": "table",
                "title": "Seat matrix",
                "columns": ["Lane", "Seat", "Provider", "Job", "Wired"],
                "rows": seat_rows,
            },
            {
                "kind": "table",
                "title": "Launch topology",
                "columns": ["Slot", "Command", "Note"],
                "rows": launch_rows,
            },
            {
                "kind": "todos",
                "title": "Done",
                "items": done,
            },
            {
                "kind": "todos",
                "title": "Open",
                "items": todo,
            },
            {
                "kind": "table",
                "title": "Integration gaps",
                "columns": ["Gap", "From", "To", "Priority"],
                "rows": gap_rows,
            },
        ],
    }


def parse_canvas_tsx(path: Path) -> dict[str, Any]:
    """Build a canvas_viewport.v1 manifest from TSX (regex-lite, no execution)."""
    slug = _slug_from_path(path)
    source_tsx = str(path.resolve()).replace("\\", "/")

    data_path = path.parent / f"{slug}.canvas.data.json"
    companion = _read_json(data_path)
    if companion and companion.get("schema") == "canvas_viewport.v1":
        companion = dict(companion)
        companion["source_tsx"] = source_tsx
        companion["synced_at"] = _now()
        if "id" not in companion:
            companion["id"] = slug
        return companion

    if slug == "mag-ecosystem-deep-dive":
        return _manifest_mag_ecosystem_deep_dive(source_tsx)

    src = path.read_text(encoding="utf-8", errors="replace")
    title = _extract_title(src)
    sections: list[dict[str, Any]] = []

    stats = _extract_stats(src)
    if stats:
        sections.append({"kind": "stats", "title": "Stats", "items": stats})
    usage = _extract_usage_stats(src)
    if usage:
        sections.append({"kind": "stats", "title": "Progress", "items": usage})

    table_map = {
        "REPO_ROWS": ("Repository puzzle pieces", ["Repo", "Role", "Port", "Status"]),
        "SEAT_ROWS": ("Seat matrix", ["Lane", "Seat", "Provider", "Job", "Wired"]),
        "GAP_ROWS": ("Integration gaps", ["Gap", "From", "To", "Priority"]),
    }
    for const_name, (tbl_title, columns) in table_map.items():
        block = _find_const_block(src, const_name)
        if not block:
            continue
        rows = _parse_string_rows(block)
        if rows:
            sections.append(
                {"kind": "table", "title": tbl_title, "columns": columns, "rows": rows}
            )

    for const_name, todo_title in (("DONE", "Done"), ("TODO", "Open")):
        block = _find_const_block(src, const_name)
        if not block:
            continue
        items = _parse_todo_items(block)
        if items:
            sections.append({"kind": "todos", "title": todo_title, "items": items})

    return {
        "schema": "canvas_viewport.v1",
        "id": slug,
        "title": title,
        "source_tsx": source_tsx,
        "synced_at": _now(),
        "sections": sections,
    }


def _discover_canvas_files() -> list[Path]:
    seen: set[str] = set()
    out: list[Path] = []
    for src_dir in _canvas_sources():
        if not src_dir.is_dir():
            continue
        for path in sorted(src_dir.glob("*.canvas.tsx")):
            slug = _slug_from_path(path)
            if slug in seen:
                continue
            seen.add(slug)
            out.append(path)
    return out


def list_viewports() -> list[dict[str, Any]]:
    """List synced viewport manifests (summary rows)."""
    if not VIEWPORTS_DIR.is_dir():
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted(VIEWPORTS_DIR.glob("*.json")):
        data = _read_json(path)
        if not data:
            continue
        rows.append(
            {
                "id": data.get("id") or path.stem,
                "title": data.get("title") or path.stem,
                "synced_at": data.get("synced_at"),
                "source_tsx": data.get("source_tsx"),
                "sections_n": len(data.get("sections") or []),
                "path": _display_path(path),
            }
        )
    return rows


def load_viewport(viewport_id: str) -> dict[str, Any]:
    """Load one manifest by id."""
    vid = viewport_id.strip()
    if not vid:
        return {"ok": False, "error": "viewport id required"}
    path = VIEWPORTS_DIR / f"{vid}.json"
    data = _read_json(path)
    if not data:
        return {"ok": False, "error": f"viewport not found: {vid}"}
    return {"ok": True, "viewport": data}


def _upsert_lattice_nodes(manifests: list[dict[str, Any]], *, dry_run: bool) -> int:
    """Append/update canvas_viewport nodes without rewriting the full lattice store."""
    if not manifests:
        return 0
    existing: list[dict[str, Any]] = []
    if LATTICE_NODES.is_file():
        for line in LATTICE_NODES.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("kind") == "canvas_viewport":
                continue
            existing.append(row)

    new_nodes: list[dict[str, Any]] = []
    for m in manifests:
        vid = str(m.get("id") or "")
        if not vid:
            continue
        new_nodes.append(
            {
                "schema": "lattice_node.v1",
                "id": f"canvas:{vid}",
                "kind": "canvas_viewport",
                "title": m.get("title") or vid,
                "viewport_id": vid,
                "viewport_path": f"memory/viewports/{vid}.json",
                "synced_at": m.get("synced_at"),
            }
        )

    if dry_run:
        return len(new_nodes)

    LATTICE_NODES.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(r, ensure_ascii=False) for r in existing + new_nodes]
    LATTICE_NODES.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return len(new_nodes)


def sync_canvases(*, dry_run: bool = False) -> dict[str, Any]:
    """Scan canvas sources and write memory/viewports/*.json manifests."""
    files = _discover_canvas_files()
    written: list[str] = []
    skipped: list[str] = []
    manifests: list[dict[str, Any]] = []

    for tsx in files:
        slug = _slug_from_path(tsx)
        try:
            manifest = parse_canvas_tsx(tsx)
        except OSError as e:
            skipped.append(f"{slug}: {e}")
            continue
        manifests.append(manifest)
        out_path = VIEWPORTS_DIR / f"{slug}.json"
        if dry_run:
            written.append(slug)
            continue
        VIEWPORTS_DIR.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        written.append(slug)

    lattice_n = _upsert_lattice_nodes(manifests, dry_run=dry_run)

    return {
        "ok": True,
        "dry_run": dry_run,
        "sources": [str(p) for p in _canvas_sources()],
        "found": len(files),
        "written": written,
        "written_n": len(written),
        "skipped": skipped,
        "lattice_nodes": lattice_n,
        "viewports_dir": _display_path(VIEWPORTS_DIR),
    }
