"""Backfill instrument Verkle chain + seed queryable lattice store.

Law: touches only memory/improve/blast/lattice/ (instrument) and memory/lattice/
(store). NEVER memory/biography/ session DNA.
"""
from __future__ import annotations

import ast
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT

from mag.lattice_loop import _h, _merkle_root, lattice_root

_DIG_NAME = re.compile(r"^c(\d+)_(.+)\.md$", re.I)
_HEADER = re.compile(r"^-\s+(\w+):\s*(.+)$")
_THEME_WORDS = {
    "mirror_meta": ("mirror", "meta", "chord"),
    "mag_hands": ("mag", "hands", "cli", "operator"),
    "scrum_plan": ("scrum", "plan", "ticket", "epic"),
    "constitution": ("constitution", "law", "rail"),
    "dashboard": ("dashboard", "desk", "viewport"),
    "harness": ("harness", "seat", "grok"),
    "biography": ("biography", "residual", "dossier", "verkle"),
    "data_r0": ("data", "tier", "raw", "soil"),
}

KNOTS_DIR = ROOT / "memory" / "biography" / "knots"
LATTICE_STORE = ROOT / "memory" / "lattice"
BONDS_JSON = ROOT / "memory" / "bonds_active.json"


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "\n".join(json.dumps(r, ensure_ascii=False) for r in rows)
    if body:
        body += "\n"
    path.write_text(body, encoding="utf-8")


def parse_dig_meta(path: Path) -> dict[str, Any]:
    """Parse unit_id, cycle, pack, urls from dig markdown."""
    m = _DIG_NAME.match(path.name)
    cycle = int(m.group(1)) if m else 0
    unit_id = m.group(2) if m else path.stem
    text = path.read_text(encoding="utf-8", errors="replace")
    meta: dict[str, Any] = {
        "unit_id": unit_id,
        "cycle": cycle,
        "dig_path": str(path),
        "pack_id": None,
        "urls": [],
        "started": None,
        "answer_chars": 0,
    }
    hm = re.search(r"# Lattice dig `([^`]+)`(?: cycle (\d+))?", text)
    if hm:
        meta["unit_id"] = hm.group(1)
        if hm.group(2):
            meta["cycle"] = int(hm.group(2))
    for line in text.splitlines()[:24]:
        hm2 = _HEADER.match(line.strip())
        if not hm2:
            continue
        key, val = hm2.group(1), hm2.group(2).strip()
        if key == "pack":
            pm = re.search(r"`([^`]+)`", val)
            meta["pack_id"] = pm.group(1) if pm else val.strip("`")
        elif key == "urls":
            try:
                meta["urls"] = list(ast.literal_eval(val))
            except Exception:
                meta["urls"] = re.findall(r"https?://[^\s\]\)\"']+", val)
        elif key == "started":
            meta["started"] = val
        elif key == "answer_chars":
            try:
                meta["answer_chars"] = int(val)
            except ValueError:
                pass
    if not meta["answer_chars"]:
        ans = re.split(r"## Answer", text, maxsplit=1)
        meta["answer_chars"] = len(ans[1]) if len(ans) > 1 else len(text)
    if meta["started"]:
        meta["date"] = meta["started"][:10]
    else:
        meta["date"] = None
    return meta


def list_dig_files() -> list[Path]:
    digs_dir = lattice_root() / "digs"
    if not digs_dir.is_dir():
        return []
    digs = [p for p in digs_dir.glob("*.md") if p.is_file()]
    digs.sort(key=lambda p: (parse_dig_meta(p)["cycle"], p.name))
    return digs


def backfill_instrument_chain(*, dry_run: bool = False) -> dict[str, Any]:
    """Rebuild instrument verkle_chain.jsonl + verkle_tip from dig markdown."""
    digs = list_dig_files()
    if not digs:
        return {"ok": False, "error": "no dig files under memory/improve/blast/lattice/digs/"}

    beads: list[dict[str, Any]] = []
    leaf_hashes: list[str] = []
    parent: str | None = None

    for dig_path in digs:
        meta = parse_dig_meta(dig_path)
        dig_bytes = dig_path.read_bytes()
        leaf_hash = _h(b"lattice-leaf:" + dig_bytes)
        leaf_hashes.append(leaf_hash)
        root = _merkle_root(leaf_hashes)
        seq = len(leaf_hashes)
        bead = {
            "schema": "lattice_verkle_bead.v1",
            "seq": seq,
            "ts": meta.get("started") or _utc(),
            "unit_id": meta["unit_id"],
            "cycle": meta["cycle"],
            "pack_id": meta.get("pack_id"),
            "dig_path": str(dig_path),
            "answer_chars": meta.get("answer_chars") or 0,
            "urls": meta.get("urls") or [],
            "leaf_hash": leaf_hash,
            "parent_root": parent,
            "verkle_root": root,
            "backfill": True,
        }
        beads.append(bead)
        parent = root

    out = {
        "ok": True,
        "n_beads": len(beads),
        "n_digs": len(digs),
        "verkle_root": parent,
        "chain_path": str(_chain_path()),
        "tip_path": str(_tip_path()),
        "dry_run": dry_run,
    }
    if dry_run:
        return out

    _write_jsonl(_chain_path(), beads)
    last = beads[-1]
    tip = {
        "schema": "lattice_verkle_tip.v1",
        "root": last["verkle_root"],
        "n_leaves": last["seq"],
        "last_path": last["dig_path"],
        "last_unit": last["unit_id"],
        "last_cycle": last["cycle"],
        "last_leaf_hash": last["leaf_hash"],
        "parent_root": last["parent_root"],
        "updated": _utc(),
        "note": "Lattice instrument chain — not Mag session DNA tip",
        "backfill": True,
    }
    _tip_path().write_text(json.dumps(tip, indent=2), encoding="utf-8")
    return out


def _chain_path() -> Path:
    return lattice_root() / "verkle_chain.jsonl"


def _tip_path() -> Path:
    return lattice_root() / "verkle_tip.json"


def _knot_nodes() -> list[dict[str, Any]]:
    if not KNOTS_DIR.is_dir():
        return []
    nodes: list[dict[str, Any]] = []
    for path in sorted(KNOTS_DIR.glob("*.knot.json")):
        if path.name.startswith("by-session_"):
            continue
        knot = _read_json(path)
        if not knot:
            continue
        sid = str(knot.get("session_id") or "")
        stem = path.stem.replace(".knot", "")
        nodes.append(
            {
                "schema": "lattice_node.v1",
                "id": f"knot:{stem}",
                "kind": "session_knot",
                "session_id": sid,
                "date": knot.get("date"),
                "start_minute": knot.get("start_minute"),
                "end_minute": knot.get("end_minute"),
                "dominant_theme": knot.get("dominant_theme"),
                "tension_index": knot.get("tension_index"),
                "dossier_commit": (knot.get("dossier_commit") or "")[:16] or None,
                "path": str(path.relative_to(ROOT)).replace("\\", "/"),
            }
        )
    nodes.sort(key=lambda n: str(n.get("start_minute") or ""))
    return nodes


def _dig_nodes() -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    for path in list_dig_files():
        meta = parse_dig_meta(path)
        nodes.append(
            {
                "schema": "lattice_node.v1",
                "id": f"dig:c{meta['cycle']:04d}_{meta['unit_id']}",
                "kind": "instrument_dig",
                "unit_id": meta["unit_id"],
                "cycle": meta["cycle"],
                "date": meta.get("date"),
                "pack_id": meta.get("pack_id"),
                "urls": meta.get("urls") or [],
                "answer_chars": meta.get("answer_chars") or 0,
                "path": str(path.relative_to(ROOT)).replace("\\", "/"),
            }
        )
    return nodes


def _rel_store_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _bond_nodes(bonds: dict[str, Any]) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    texts = list(bonds.get("residual_bonds") or [])
    if not texts:
        texts = list(bonds.get("open_loops") or [])
    for i, text in enumerate(texts):
        if not isinstance(text, str) or not text.strip():
            continue
        slug = re.sub(r"[^a-z0-9]+", "-", text.lower())[:48].strip("-") or f"bond-{i}"
        nodes.append(
            {
                "schema": "lattice_node.v1",
                "id": f"bond:{slug}",
                "kind": "residual_bond",
                "text": text.strip()[:240],
                "session_id": bonds.get("session_id"),
            }
        )
    return nodes


def _dig_body_lower(path_rel: str) -> str:
    p = ROOT / path_rel.replace("/", "\\") if "\\" not in path_rel else ROOT / path_rel
    if not p.is_file():
        p = ROOT / path_rel
    if not p.is_file():
        return ""
    return p.read_text(encoding="utf-8", errors="replace").lower()


def _theme_link(knot: dict[str, Any], dig: dict[str, Any], body: str) -> bool:
    theme = knot.get("dominant_theme")
    if not isinstance(theme, str) or not theme:
        return False
    phrase = theme.replace("_", " ")
    if phrase in body or theme in body:
        return True
    tokens = _THEME_WORDS.get(theme, ())
    if not tokens:
        return False
    hits = sum(1 for t in tokens if len(t) >= 4 and t in body)
    return hits >= 2


def seed_lattice_store(*, dry_run: bool = False) -> dict[str, Any]:
    """Write memory/lattice/nodes.jsonl + edges.jsonl from knots, digs, bonds."""
    bonds = _read_json(BONDS_JSON)
    knot_nodes = _knot_nodes()
    dig_nodes = _dig_nodes()
    bond_nodes = _bond_nodes(bonds)
    nodes = knot_nodes + dig_nodes + bond_nodes

    edges: list[dict[str, Any]] = []
    by_id = {n["id"]: n for n in nodes}

    # day → day bonds (chronological session knots)
    prev_knot: dict[str, Any] | None = None
    for kn in knot_nodes:
        if prev_knot:
            edges.append(
                {
                    "schema": "lattice_edge.v1",
                    "id": f"edge:day:{prev_knot['id']}->{kn['id']}",
                    "kind": "day_bond",
                    "source": prev_knot["id"],
                    "target": kn["id"],
                    "weight": 0.5,
                }
            )
        prev_knot = kn

    # instrument dig chain
    prev_dig: dict[str, Any] | None = None
    for dn in dig_nodes:
        if prev_dig:
            edges.append(
                {
                    "schema": "lattice_edge.v1",
                    "id": f"edge:verkle:{prev_dig['id']}->{dn['id']}",
                    "kind": "instrument_chain",
                    "source": prev_dig["id"],
                    "target": dn["id"],
                    "weight": 0.6,
                }
            )
        prev_dig = dn

    # session → dig via date + theme
    for dn in dig_nodes:
        dig_date = dn.get("date")
        dig_path = dn.get("path") or ""
        body = _dig_body_lower(dig_path) if dig_path else ""
        for kn in knot_nodes:
            linked = False
            if dig_date and kn.get("date") == dig_date:
                linked = True
            if not linked:
                linked = _theme_link(kn, dn, body)
            if linked:
                edges.append(
                    {
                        "schema": "lattice_edge.v1",
                        "id": f"edge:session_dig:{kn['id']}->{dn['id']}",
                        "kind": "session_dig",
                        "source": kn["id"],
                        "target": dn["id"],
                        "weight": 0.35,
                        "via": "date" if dig_date and kn.get("date") == dig_date else "theme",
                    }
                )

    # residual bonds → latest session knot
    latest_knot = knot_nodes[-1] if knot_nodes else None
    if latest_knot:
        for bn in bond_nodes:
            edges.append(
                {
                    "schema": "lattice_edge.v1",
                    "id": f"edge:bond:{latest_knot['id']}->{bn['id']}",
                    "kind": "residual_bond",
                    "source": latest_knot["id"],
                    "target": bn["id"],
                    "weight": 0.4,
                }
            )

    out = {
        "ok": True,
        "n_nodes": len(nodes),
        "n_edges": len(edges),
        "knot_nodes": len(knot_nodes),
        "dig_nodes": len(dig_nodes),
        "bond_nodes": len(bond_nodes),
        "nodes_path": str(LATTICE_STORE / "nodes.jsonl"),
        "edges_path": str(LATTICE_STORE / "edges.jsonl"),
        "dry_run": dry_run,
    }
    if dry_run:
        return out

    _write_jsonl(LATTICE_STORE / "nodes.jsonl", nodes)
    _write_jsonl(LATTICE_STORE / "edges.jsonl", edges)
    return out


def run_backfill(*, dry_run: bool = False) -> dict[str, Any]:
    """Backfill instrument chain then seed lattice store."""
    chain = backfill_instrument_chain(dry_run=dry_run)
    store = seed_lattice_store(dry_run=dry_run)
    return {
        "ok": chain.get("ok") and store.get("ok"),
        "chain": chain,
        "store": store,
    }
