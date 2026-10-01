"""Tesuji Grove — poem skill tree builder (v3-012 research).

Scans remedies, FKB, improve artifacts and writes grove nodes on disk.
Idempotent: re-run updates index; poems are draft until operator edits.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT

GROVE_ROOT = ROOT / "memory" / "grove"
NODES_DIR = GROVE_ROOT / "nodes"
INDEX_PATH = GROVE_ROOT / "index.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _node_id(kind: str, source_path: str) -> str:
    digest = hashlib.sha256(f"{kind}|{source_path}".encode()).hexdigest()[:10]
    return f"grove-{kind}-{digest}"


def _draft_poem(title: str, kind: str) -> str:
    t = (title or "learning").strip()[:60]
    if kind == "remedy":
        return f"When {t} returns;\nfile the fix first."
    if kind == "curious_error":
        return f"Three echoes empty;\nguard stops the wheel."
    if kind == "skill":
        return f"Pack before speech —\nenvelope, not scroll."
    return f"{t};\nfiled on soil."


def _load_index_ids() -> set[str]:
    if not INDEX_PATH.is_file():
        return set()
    ids: set[str] = set()
    for line in INDEX_PATH.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
            if row.get("id"):
                ids.add(str(row["id"]))
        except json.JSONDecodeError:
            continue
    return ids


def _scan_remedies() -> list[dict[str, Any]]:
    nodes = []
    for p in sorted((ROOT / "memory" / "remedies").glob("*.md")):
        rel = p.relative_to(ROOT).as_posix()
        title = p.stem.replace("-", " ")
        kind = "remedy"
        if "empty" in title or "fail" in title or "error" in title:
            kind = "curious_error"
        nodes.append({
            "schema": "grove_node.v1",
            "id": _node_id(kind, rel),
            "kind": kind,
            "status": "learned",
            "poem": _draft_poem(title, kind),
            "title": title[:80],
            "source_path": rel,
            "parent_ids": [],
            "unlocked_at": _now(),
            "tags": ["fkb", "remedy"],
            "classifier": "grove_build",
        })
    return nodes


def _scan_skills() -> list[dict[str, Any]]:
    nodes = []
    skills_path = ROOT / "configs" / "skills.yaml"
    if not skills_path.is_file():
        return nodes
    text = skills_path.read_text(encoding="utf-8", errors="replace")
    for m in re.finditer(r"^\s*id:\s*([^\n]+)", text, re.MULTILINE):
        sid = m.group(1).strip().strip('"').strip("'")
        rel = "configs/skills.yaml"
        nodes.append({
            "schema": "grove_node.v1",
            "id": _node_id("skill", f"{rel}#{sid}"),
            "kind": "skill",
            "status": "learned",
            "poem": _draft_poem(sid, "skill"),
            "title": sid[:80],
            "source_path": rel,
            "parent_ids": [],
            "unlocked_at": _now(),
            "tags": ["skill", "promoted"],
            "classifier": "grove_build",
        })
    return nodes


def build(*, dry: bool = False) -> dict[str, Any]:
    existing = _load_index_ids()
    candidates = _scan_remedies() + _scan_skills()
    new_nodes = [n for n in candidates if n["id"] not in existing]
    written = []

    if not dry:
        NODES_DIR.mkdir(parents=True, exist_ok=True)
        GROVE_ROOT.mkdir(parents=True, exist_ok=True)
        for node in new_nodes:
            node_path = NODES_DIR / f"{node['id']}.json"
            node_path.write_text(json.dumps(node, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            with INDEX_PATH.open("a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "id": node["id"],
                    "kind": node["kind"],
                    "source_path": node["source_path"],
                    "ts": _now(),
                }, ensure_ascii=False) + "\n")
            written.append(node["id"])

    return {
        "schema": "grove_build.v1",
        "ts": _now(),
        "ok": True,
        "dry": dry,
        "candidates": len(candidates),
        "new_nodes": len(new_nodes),
        "written": written,
        "index_path": str(INDEX_PATH),
    }


def list_nodes(*, limit: int = 20) -> list[dict[str, Any]]:
    if not NODES_DIR.is_dir():
        return []
    nodes = []
    for p in sorted(NODES_DIR.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True)[:limit]:
        try:
            nodes.append(json.loads(p.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    return nodes
