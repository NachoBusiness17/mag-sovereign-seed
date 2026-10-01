"""Idea graph v0 — topic-shaped continuity on disk (not seat economics).

Schema: idea_graph.v0
Store: memory/ideas/nodes.jsonl + edges.jsonl
Law: files are truth; not a second session DNA; no secrets.
"""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT, WORKING_MD

SCHEMA = "idea_graph.v0"
IDEAS_DIR = ROOT / "memory" / "ideas"
NODES_PATH = IDEAS_DIR / "nodes.jsonl"
EDGES_PATH = IDEAS_DIR / "edges.jsonl"
LATEST_MD = IDEAS_DIR / "LATEST.md"

NODE_TYPES = frozenset(
    {"topic", "claim", "project", "open_loop", "evidence", "entity", "avatar"}
)
EDGE_TYPES = frozenset(
    {
        "supports",
        "depends",
        "contradicts",
        "same_thread",
        "evidence_for",
        "related",
        "acted_on",
        "produced",
    }
)
STATUSES = frozenset({"open", "held", "done", "parked"})


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str = "n") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def ensure_dirs() -> None:
    IDEAS_DIR.mkdir(parents=True, exist_ok=True)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    out: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            o = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(o, dict):
            out.append(o)
    return out


def _append_jsonl(path: Path, obj: dict[str, Any]) -> None:
    ensure_dirs()
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    """Atomic-ish rewrite (temp + replace) for status/title edits."""
    ensure_dirs()
    tmp = path.with_suffix(path.suffix + ".tmp")
    body = "\n".join(json.dumps(r, ensure_ascii=False) for r in rows)
    if body:
        body += "\n"
    tmp.write_text(body, encoding="utf-8")
    tmp.replace(path)


def load_nodes() -> list[dict[str, Any]]:
    return _read_jsonl(NODES_PATH)


def load_edges() -> list[dict[str, Any]]:
    return _read_jsonl(EDGES_PATH)


def get_node(node_id: str) -> dict[str, Any] | None:
    nid = (node_id or "").strip()
    if not nid:
        return None
    for n in load_nodes():
        if str(n.get("id") or "") == nid:
            return n
        # prefix match if unique enough
        if str(n.get("id") or "").startswith(nid) and len(nid) >= 6:
            return n
    return None


def patch_node(
    node_id: str,
    *,
    status: str | None = None,
    title: str | None = None,
    body: str | None = None,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    """Update fields on a node (files are truth). Rewrites nodes.jsonl."""
    cur = get_node(node_id)
    if not cur:
        raise KeyError(f"not found: {node_id}")
    rid = str(cur["id"])
    if status is not None:
        st = status.strip().lower()
        if st not in STATUSES:
            raise ValueError(f"bad status {status!r}; want one of {sorted(STATUSES)}")
        cur["status"] = st
    if title is not None:
        t = title.strip()
        if not t:
            raise ValueError("title cannot be empty")
        cur["title"] = t[:300]
    if body is not None:
        cur["body"] = body[:4000]
    if tags is not None:
        cur["tags"] = list(tags)[:20]
    cur["updated_ts"] = _utc()
    rows = load_nodes()
    out: list[dict[str, Any]] = []
    replaced = False
    for n in rows:
        if str(n.get("id") or "") == rid:
            out.append(cur)
            replaced = True
        else:
            out.append(n)
    if not replaced:
        out.append(cur)
    _write_jsonl(NODES_PATH, out)
    write_latest_face()
    return cur


def list_nodes(
    *,
    status: str | None = None,
    ntype: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    rows = load_nodes()
    if status:
        rows = [r for r in rows if str(r.get("status") or "") == status]
    if ntype:
        rows = [r for r in rows if str(r.get("type") or "") == ntype]
    # newest first if ts present
    rows = sorted(rows, key=lambda r: str(r.get("ts") or ""), reverse=True)
    return rows[: max(1, limit)]


def add_node(
    *,
    title: str,
    ntype: str = "topic",
    status: str = "open",
    body: str = "",
    refs: list[str] | None = None,
    tags: list[str] | None = None,
    source: str = "human",
    node_id: str | None = None,
) -> dict[str, Any]:
    ntype = (ntype or "topic").strip().lower()
    status = (status or "open").strip().lower()
    if ntype not in NODE_TYPES:
        raise ValueError(f"bad node type {ntype!r}; want one of {sorted(NODE_TYPES)}")
    if status not in STATUSES:
        raise ValueError(f"bad status {status!r}; want one of {sorted(STATUSES)}")
    title = (title or "").strip()
    if not title:
        raise ValueError("title required")
    node = {
        "schema": SCHEMA,
        "id": node_id or _new_id("n"),
        "type": ntype,
        "title": title[:300],
        "status": status,
        "body": (body or "")[:4000],
        "refs": list(refs or [])[:20],
        "tags": list(tags or [])[:20],
        "source": source,
        "ts": _utc(),
    }
    _append_jsonl(NODES_PATH, node)
    return node


def link(
    src: str,
    dst: str,
    *,
    etype: str = "related",
    note: str = "",
    ref: str = "",
) -> dict[str, Any]:
    etype = (etype or "related").strip().lower()
    if etype not in EDGE_TYPES:
        raise ValueError(f"bad edge type {etype!r}; want one of {sorted(EDGE_TYPES)}")
    sn = get_node(src)
    dn = get_node(dst)
    if not sn:
        raise ValueError(f"src not found: {src}")
    if not dn:
        raise ValueError(f"dst not found: {dst}")
    edge = {
        "schema": SCHEMA,
        "id": _new_id("e"),
        "src": sn["id"],
        "dst": dn["id"],
        "type": etype,
        "note": (note or "")[:500],
        "ref": (ref or "")[:500],
        "ts": _utc(),
    }
    _append_jsonl(EDGES_PATH, edge)
    return edge


def neighborhood(node_id: str, *, depth: int = 1) -> dict[str, Any]:
    root = get_node(node_id)
    if not root:
        return {"ok": False, "error": f"not found: {node_id}"}
    rid = str(root["id"])
    edges = load_edges()
    nodes_by_id = {str(n.get("id")): n for n in load_nodes()}
    seen: set[str] = {rid}
    frontier: set[str] = {rid}
    linked_edges: list[dict[str, Any]] = []
    edge_ids: set[str] = set()
    for _ in range(max(1, int(depth))):
        nxt: set[str] = set()
        for e in edges:
            s, d = str(e.get("src") or ""), str(e.get("dst") or "")
            if s not in frontier and d not in frontier:
                continue
            eid = str(e.get("id") or id(e))
            if eid not in edge_ids:
                edge_ids.add(eid)
                linked_edges.append(e)
            if s and s not in seen:
                nxt.add(s)
            if d and d not in seen:
                nxt.add(d)
        seen |= nxt
        frontier = nxt
        if not frontier:
            break
    nodes = [nodes_by_id[i] for i in seen if i in nodes_by_id]
    return {
        "ok": True,
        "root": root,
        "nodes": nodes,
        "edges": linked_edges,
        "n_nodes": len(nodes),
        "n_edges": len(linked_edges),
    }


def pack_node(node_id: str, *, max_chars: int = 2500) -> str:
    """LOAD pack slice for one node + 1-hop neighborhood."""
    nb = neighborhood(node_id, depth=1)
    if not nb.get("ok"):
        return f"(idea pack: {nb.get('error')})"
    root = nb["root"]
    lines = [
        f"# Idea pack · {root.get('id')}",
        f"**schema:** {SCHEMA}",
        f"**type:** {root.get('type')} · **status:** {root.get('status')}",
        f"**title:** {root.get('title')}",
        "",
        "## Body",
        (root.get("body") or "(empty)")[:800],
        "",
        "## Refs",
    ]
    refs = root.get("refs") or []
    if refs:
        for r in refs[:12]:
            lines.append(f"- {r}")
    else:
        lines.append("- (none)")
    lines.extend(["", "## Neighborhood edges"])
    for e in (nb.get("edges") or [])[:20]:
        lines.append(
            f"- {e.get('type')}: {e.get('src')} → {e.get('dst')}"
            + (f" ({e.get('note')})" if e.get("note") else "")
        )
    if not nb.get("edges"):
        lines.append("- (none)")
    lines.extend(["", "## Neighbor nodes"])
    for n in nb.get("nodes") or []:
        if n.get("id") == root.get("id"):
            continue
        lines.append(
            f"- [{n.get('type')}|{n.get('status')}] {n.get('id')}: {n.get('title')}"
        )
    text = "\n".join(lines)
    return text[:max_chars]


def write_latest_face() -> Path:
    ensure_dirs()
    nodes = list_nodes(limit=40)
    edges = load_edges()
    lines = [
        f"# Idea graph face",
        "",
        f"**schema:** {SCHEMA}",
        f"**nodes:** {len(load_nodes())} · **edges:** {len(edges)}",
        f"**updated:** {_utc()}",
        "",
        "## Open (latest)",
        "",
    ]
    opens = [n for n in nodes if n.get("status") == "open"][:15]
    if not opens:
        lines.append("- (no open nodes)")
    for n in opens:
        lines.append(f"- `{n.get('id')}` [{n.get('type')}] {n.get('title')}")
    lines.extend(["", "## CLI", "", "```text", "python main.py ideas list", "python main.py ideas pack <id>", "```", ""])
    LATEST_MD.write_text("\n".join(lines), encoding="utf-8")
    return LATEST_MD


def _slug_title(title: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", title.strip().lower()).strip("-")
    return s[:40] or "node"


def _existing_titles() -> set[str]:
    return {str(n.get("title") or "").strip().lower() for n in load_nodes()}


def seed_from_working_and_agent_state() -> dict[str, Any]:
    """Seed open_loops from working.md Open + evidence nodes from agent_state paths."""
    ensure_dirs()
    created_nodes: list[dict[str, Any]] = []
    created_edges: list[dict[str, Any]] = []
    titles = _existing_titles()

    # root project node
    root_title = "Sovereign workspace spine"
    root = None
    for n in load_nodes():
        if n.get("title") == root_title:
            root = n
            break
    if not root:
        root = add_node(
            title=root_title,
            ntype="project",
            status="open",
            body="Idea lattice + dashboard + proxy avatars + portable house (L1–L4).",
            tags=["spine", "mag"],
            source="seed",
            node_id="n_spine_workspace",
        )
        created_nodes.append(root)
        titles.add(root_title.lower())

    # working.md Open bullets
    if WORKING_MD.is_file():
        text = WORKING_MD.read_text(encoding="utf-8", errors="replace")
        in_open = False
        for ln in text.splitlines():
            s = ln.strip()
            if s.startswith("## "):
                in_open = s[3:].strip().lower() == "open"
                continue
            if not in_open:
                continue
            if s.startswith("#"):
                break
            if s.startswith("- "):
                title = s[2:].strip()
                # strip markdown bold markers for stable title
                title_clean = re.sub(r"\*\*", "", title)[:200]
                if not title_clean or title_clean.lower() in titles:
                    continue
                node = add_node(
                    title=title_clean,
                    ntype="open_loop",
                    status="open",
                    body=f"Seeded from memory/working.md Open.\n\n{title}",
                    refs=["memory/working.md"],
                    tags=["working", "seed"],
                    source="seed",
                )
                created_nodes.append(node)
                titles.add(title_clean.lower())
                try:
                    e = link(node["id"], root["id"], etype="depends", note="roadmap open → spine")
                    created_edges.append(e)
                except ValueError:
                    pass

    # agent_state path edges as evidence
    as_path = ROOT / "memory" / "agent_state" / "LATEST.md"
    if as_path.is_file():
        text = as_path.read_text(encoding="utf-8", errors="replace")
        in_paths = False
        for ln in text.splitlines():
            s = ln.strip()
            if s.startswith("## "):
                in_paths = "paths" in s.lower()
                continue
            if not in_paths:
                continue
            if s.startswith("#"):
                break
            if s.startswith("- ") and "→" in s:
                left, _, right = s[2:].partition("→")
                key = left.strip().strip("`")
                path = right.strip().split()[0] if right.strip() else ""
                title = f"path:{key}"
                if title.lower() in titles:
                    continue
                node = add_node(
                    title=title[:200],
                    ntype="evidence",
                    status="held",
                    body=f"Agent-state path edge: {key}",
                    refs=[path] if path else [str(as_path.relative_to(ROOT))],
                    tags=["agent_state", "seed"],
                    source="seed",
                )
                created_nodes.append(node)
                titles.add(title.lower())
                try:
                    e = link(
                        node["id"],
                        root["id"],
                        etype="evidence_for",
                        note="agent_state path",
                        ref=path,
                    )
                    created_edges.append(e)
                except ValueError:
                    pass

    # skill beads as evidence
    skills = ROOT / "memory" / "improve" / "pins" / "skills"
    if skills.is_dir():
        for p in sorted(skills.glob("*.md"))[:12]:
            title = f"skill:{p.stem}"[:200]
            if title.lower() in titles:
                continue
            rel = str(p.relative_to(ROOT))
            node = add_node(
                title=title,
                ntype="evidence",
                status="held",
                body="IJL skill bead",
                refs=[rel],
                tags=["skill", "ijl", "seed"],
                source="seed",
            )
            created_nodes.append(node)
            titles.add(title.lower())
            try:
                e = link(node["id"], root["id"], etype="evidence_for", note="skill bead", ref=rel)
                created_edges.append(e)
            except ValueError:
                pass

    face = write_latest_face()
    return {
        "ok": True,
        "schema": SCHEMA,
        "created_nodes": len(created_nodes),
        "created_edges": len(created_edges),
        "total_nodes": len(load_nodes()),
        "total_edges": len(load_edges()),
        "root_id": root["id"],
        "face": str(face.relative_to(ROOT)),
        "new_ids": [n["id"] for n in created_nodes[:20]],
    }


def format_list(nodes: list[dict[str, Any]]) -> str:
    if not nodes:
        return "(no nodes)"
    lines = []
    for n in nodes:
        lines.append(
            f"{n.get('id')}\t[{n.get('type')}|{n.get('status')}]\t{n.get('title')}"
        )
    return "\n".join(lines)


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def summary() -> dict[str, Any]:
    nodes = load_nodes()
    edges = load_edges()
    by_type: dict[str, int] = {}
    by_status: dict[str, int] = {}
    for n in nodes:
        t = str(n.get("type") or "?")
        s = str(n.get("status") or "?")
        by_type[t] = by_type.get(t, 0) + 1
        by_status[s] = by_status.get(s, 0) + 1
    return {
        "ok": True,
        "schema": SCHEMA,
        "n_nodes": len(nodes),
        "n_edges": len(edges),
        "by_type": by_type,
        "by_status": by_status,
        "paths": {
            "nodes": _rel(NODES_PATH),
            "edges": _rel(EDGES_PATH),
            "face": _rel(LATEST_MD) if LATEST_MD.is_file() else None,
        },
    }
