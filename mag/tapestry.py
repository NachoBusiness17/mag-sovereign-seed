"""Operational tapestry pack from Mag residual DNA.

Builds a VK-class connection graph:
  tip → day beads → theme beads → ask sub-beads
with explicit 3D transforms (helix / ring / radial) compatible with
sovereign-mirror platform engine (nodes: id,x,y,z,S,label,kind).

  python main.py tapestry          # write pack + print stats
  GET /api/v1/tapestry
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT
from mag.tapestry_visual import lattice_chain_offset, visual_profile

BIO = ROOT / "memory" / "biography"
OUT = BIO / "tapestry_pack.json"
AGENT_SESS_DIR = ROOT / "memory" / "agent_sessions"
RELATED_RUNS = ROOT / "memory" / "runs" / "related_runs.jsonl"

THEME_COLORS = {
    "mag_hands": 0.2,
    "mirror_meta": -1.5,
    "biography": -0.8,
    "dashboard": 0.5,
    "data_r0": 1.0,
    "scrum_plan": 0.0,
    "constitution": -2.0,
    "harness": 0.3,
}


def _parse_minute(iso: str | None) -> float:
    if not iso:
        return 0.0
    try:
        s = str(iso).replace("Z", "+00:00")
        t = datetime.fromisoformat(s)
        return t.timestamp()
    except Exception:
        return 0.0


def _seat_slug(session_id: str) -> str:
    sid = str(session_id or "")
    for prefix in ("mag-agent-", "mag-"):
        if sid.startswith(prefix):
            return sid[len(prefix) :]
    return sid


def _load_agent_transcript(session_id: str) -> dict[str, Any] | None:
    slug = _seat_slug(session_id)
    for name in (slug, session_id):
        if not name:
            continue
        path = AGENT_SESS_DIR / f"{name}.json"
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else None
        except (json.JSONDecodeError, OSError):
            continue
    return None


def _load_related_runs() -> list[dict[str, Any]]:
    if not RELATED_RUNS.is_file():
        return []
    rows: list[dict[str, Any]] = []
    try:
        for line in RELATED_RUNS.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    except OSError:
        return []
    return rows


def _session_ids_match(a: str, b: str) -> bool:
    a, b = str(a or ""), str(b or "")
    if not a or not b:
        return False
    if a == b:
        return True
    return _seat_slug(a) == _seat_slug(b) or a.endswith(b) or b.endswith(a)


def _layman_block(
    *,
    what: str,
    where: str,
    why: str,
) -> dict[str, str]:
    return {
        "layman_what": what[:220],
        "layman_where": where[:180],
        "layman_why": why[:220],
    }


def _subsessions_from_transcript(
    session_id: str,
    parent_nid: str,
    *,
    x: float,
    y: float,
    z: float,
    ang: float,
    S: float,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Real chat turns from agent_sessions — not bullet summaries."""
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    tr = _load_agent_transcript(session_id)
    if not tr:
        return nodes, edges
    slug = _seat_slug(session_id)
    turns = [m for m in (tr.get("messages") or []) if m.get("role") == "user"][:8]
    prev_id: str | None = None
    for j, msg in enumerate(turns):
        text = str(msg.get("content") or "").strip()
        if not text:
            continue
        sub_id = f"sub:{session_id[:14]}:{j}"
        a_ang = ang + (j - (len(turns) - 1) / 2) * 0.2
        ar = 0.62 + j * 0.07
        nodes.append(
            {
                "id": sub_id,
                "label": text[:40],
                "kind": "subsession",
                "layer": "frame",
                "core": False,
                "S": S * 0.45,
                "x": x + ar * math.cos(a_ang),
                "y": y + 0.12 * j,
                "z": z + ar * math.sin(a_ang),
                "visual": visual_profile(
                    "subsession",
                    S=S * 0.45,
                    chain_index=j,
                    n_children=len(turns),
                ),
                "meta": {
                    "parent": parent_nid,
                    "session_id": session_id,
                    "text": text[:240],
                    "turn": j + 1,
                    "seat": tr.get("source") or tr.get("provider") or "agent",
                    **_layman_block(
                        what=f"Turn {j + 1}: «{text[:80]}»",
                        where=f"memory/agent_sessions/{slug}.json",
                        why="A real operator prompt in this work session — child of the day bead.",
                    ),
                },
            }
        )
        edges.append(
            {"source": parent_nid, "target": sub_id, "kind": "thread", "weight": 0.62}
        )
        if prev_id:
            edges.append(
                {"source": prev_id, "target": sub_id, "kind": "thread", "weight": 0.48}
            )
        prev_id = sub_id
    return nodes, edges


def _runs_for_session(
    session_id: str,
    parent_nid: str,
    related: list[dict[str, Any]],
    *,
    x: float,
    y: float,
    z: float,
    ang: float,
    S: float,
    start_idx: int = 0,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    matched = [
        r
        for r in related
        if _session_ids_match(str(r.get("session_id") or ""), session_id)
    ][:6]
    for j, run in enumerate(matched):
        goal = str(run.get("goal") or run.get("run_id") or "run")[:40]
        rid = f"run:{run.get('run_id', j)}"[:48]
        a_ang = ang + math.pi * 0.5 + j * 0.25
        ar = 0.85 + j * 0.05
        nodes.append(
            {
                "id": rid,
                "label": goal,
                "kind": "run",
                "layer": "frame",
                "core": False,
                "S": S * 0.35,
                "x": x + ar * math.cos(a_ang),
                "y": y - 0.2 - j * 0.08,
                "z": z + ar * math.sin(a_ang),
                "visual": visual_profile(
                    "run",
                    S=S * 0.35,
                    chain_index=j,
                    n_children=int(run.get("n_tool_calls") or 0),
                ),
                "meta": {
                    "parent": parent_nid,
                    "session_id": session_id,
                    "run_id": run.get("run_id"),
                    "seat": run.get("seat"),
                    "status": run.get("status"),
                    "n_tool_calls": run.get("n_tool_calls"),
                    "path": str(run.get("path") or "")[-80:],
                    **_layman_block(
                        what=f"Background run: {goal}",
                        where=str(run.get("trail_path") or run.get("path") or "memory/runs/")[-100:],
                        why="A Mag orchestrator trail tied to this session — tools + events on disk.",
                    ),
                },
            }
        )
        edges.append(
            {"source": parent_nid, "target": rid, "kind": "run", "weight": 0.5}
        )
    return nodes, edges


def _orc_worker_nodes(
    orc_reg: dict[str, Any],
    parent_nid: str,
    *,
    x: float,
    y: float,
    z: float,
    ang: float,
    S: float,
    idx: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Orchestrator smoke/worker sessions attach as run beads, not separate days."""
    sid = str(orc_reg.get("session_id") or "")
    goal = str(orc_reg.get("one_liner") or orc_reg.get("title") or sid)[:44]
    rid = f"orc:{sid[-12:]}"
    a_ang = ang - 0.35 - (idx % 4) * 0.15
    ar = 0.72 + (idx % 3) * 0.06
    node = {
        "id": rid,
        "label": goal[:36],
        "kind": "run",
        "layer": "frame",
        "core": False,
        "S": S * 0.4,
        "x": x + ar * math.cos(a_ang),
        "y": y + 0.08 * idx,
        "z": z + ar * math.sin(a_ang),
        "visual": visual_profile("run", S=S * 0.4, chain_index=idx),
        "meta": {
            "parent": parent_nid,
            "session_id": sid,
            "worker": True,
            "text": str(orc_reg.get("blurb") or "")[:200],
            **_layman_block(
                what=f"Worker task: {goal}",
                where=f"memory/biography/residual/{sid}.json",
                why="Orchestrator worker filed as a sub-bead — not its own day on the helix.",
            ),
        },
    }
    edge = {"source": parent_nid, "target": rid, "kind": "run", "weight": 0.55}
    return [node], [edge]


def _lattice_node(
    reg: dict[str, Any],
    day_nid: str,
    *,
    x: float,
    y: float,
    z: float,
    prev_lattice: str | None,
    chain_index: int = 0,
    Q_proxy: float | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Portable Verkle knot artifact anchored beneath its source workday."""
    sid = str(reg.get("session_id") or "")
    if not (reg.get("leaf_hash") or reg.get("verkle_filename") or reg.get("leaf_filename")):
        return [], []
    lx, ly, lz = lattice_chain_offset(chain_index, x=x, y=y, z=z)
    leaf_seed = str(reg.get("leaf_hash") or reg.get("verkle_filename") or sid)
    tens = reg.get("tension_index")
    try:
        tens_f = float(tens) if tens is not None else None
    except (TypeError, ValueError):
        tens_f = None
    visual = visual_profile(
        "lattice",
        tension_index=tens_f,
        S=-4.5,
        Q_proxy=Q_proxy,
        chain_index=chain_index,
        seed=leaf_seed,
    )
    lid = f"lattice:{sid[:16]}"
    node = {
        "id": lid,
        "label": "Verkle knot artifact",
        "kind": "lattice",
        "layer": "lattice",
        "core": False,
        "S": -4.5,
        "x": lx,
        "y": ly,
        "z": lz,
        "visual": visual,
        "meta": {
            "parent": day_nid,
            "session_id": sid,
            "leaf_hash": (reg.get("leaf_hash") or "")[:16],
            "verkle_root": (reg.get("verkle_root") or "")[:16],
            "leaf_file": reg.get("verkle_filename") or reg.get("leaf_filename"),
            "ghost": True,
            **_layman_block(
                what="Portable evidence packet that can be handed to an agent",
                where=f"memory/biography/knots/{reg.get('verkle_filename') or reg.get('leaf_filename') or '?'}",
                why="Packages a filed workday, source path, and commitments so an agent can inherit evidence without the whole conversation.",
            ),
        },
    }
    edges = [
        {"source": day_nid, "target": lid, "kind": "lattice", "weight": 0.35},
    ]
    if prev_lattice:
        edges.append(
            {"source": prev_lattice, "target": lid, "kind": "lattice_chain", "weight": 0.28}
        )
    return [node], edges


def build_tapestry_pack() -> dict[str, Any]:
    from mag.registry import list_registry, load_residual

    rows = list_registry(limit=500)
    # sort oldest → newest for helix
    rows = sorted(
        rows,
        key=lambda r: _parse_minute(r.get("end_minute") or r.get("start_minute")),
    )
    primary_rows = [
        r
        for r in rows
        if not str(r.get("session_id") or "").startswith("mag-agent-orc-")
    ]
    orc_rows = [
        r for r in rows if str(r.get("session_id") or "").startswith("mag-agent-orc-")
    ]
    related = _load_related_runs()
    timeline_by_sid: dict[str, dict[str, Any]] = {}
    tl_path = BIO / "knot_timeline.jsonl"
    if tl_path.is_file():
        try:
            for line in tl_path.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                sid_tl = str(row.get("session_id") or "")
                if sid_tl:
                    timeline_by_sid[sid_tl] = row
        except OSError:
            pass
    n = max(len(primary_rows), 1)
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    by_theme: dict[str, list[str]] = {}
    day_positions: dict[str, tuple[float, float, float, float, float]] = {}
    n_subsessions = 0
    n_runs = 0
    n_lattice = 0

    tip = BIO / "verkle_tip.json"
    tip_data = {}
    if tip.is_file():
        try:
            tip_data = json.loads(tip.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            tip_data = {}

    # --- root tip node (substrate) ---
    nodes.append(
        {
            "id": "tip",
            "label": "chain tip",
            "kind": "root",
            "layer": "substrate",
            "core": True,
            "S": -8.0,
            "x": 0.0,
            "y": 0.0,
            "z": 0.0,
            "visual": visual_profile("root", S=-8.0),
            "meta": {
                "n_leaves": tip_data.get("n_leaves"),
                "root": (tip_data.get("root") or "")[:16],
                **_layman_block(
                    what="Latest hash on Mag's filed memory chain",
                    where="memory/biography/verkle_tip.json",
                    why="Current commitment for filed day records — audit it against the leaf files to detect drift or gaps.",
                ),
            },
        }
    )

    # --- day beads on a rising helix (time = angle + height) ---
    helix_r = 3.0
    helix_h = 8.0
    prev_lattice: str | None = None
    lattice_chain_idx = 0
    for i, reg in enumerate(primary_rows):
        sid = reg.get("session_id") or f"s{i}"
        nid = f"day:{sid}"
        t = i / max(n, 1)
        ang = t * math.tau * 1.6
        y = (t - 0.5) * helix_h
        x = helix_r * math.cos(ang)
        z = helix_r * math.sin(ang)
        tens = float(reg.get("tension_index") or 0.5)
        S = -2.0 + 4.0 * min(1.0, max(0.0, tens))
        tl_row = timeline_by_sid.get(sid) or {}
        Q_proxy = tl_row.get("Q_proxy")
        try:
            Q_proxy_f = float(Q_proxy) if Q_proxy is not None else None
        except (TypeError, ValueError):
            Q_proxy_f = None
        dur = tl_row.get("duration_minutes")
        try:
            dur_f = float(dur) if dur is not None else None
        except (TypeError, ValueError):
            dur_f = None
        title = reg.get("title") or sid[:12]
        residual = load_residual(sid) or {}
        card = residual.get("session_card") or residual.get("card") or {}
        blurb = (
            reg.get("blurb")
            or reg.get("one_liner")
            or residual.get("one_liner")
            or card.get("one_liner")
            or (residual.get("chord") or {}).get("one_line")
            or ""
        )
        bullets = list(
            reg.get("bullets")
            or card.get("bullets")
            or residual.get("bullets")
            or []
        )[:6]
        theme = reg.get("dominant_theme")
        nodes.append(
            {
                "id": nid,
                "label": title[:48],
                "kind": "session",
                "layer": "object",
                "core": False,
                "S": S,
                "x": x,
                "y": y,
                "z": z,
                "visual": visual_profile(
                    "session",
                    tension_index=tens,
                    S=S,
                    Q_proxy=Q_proxy_f,
                    duration_min=dur_f,
                ),
                "meta": {
                    "session_id": sid,
                    "blurb": str(blurb)[:240],
                    "bullets": [str(b)[:160] for b in bullets],
                    "theme": theme,
                    "residual_hash": (reg.get("residual_hash") or "")[:16],
                    "end_minute": reg.get("end_minute") or reg.get("start_minute"),
                    **_layman_block(
                        what=str(reg.get("one_liner") or blurb)[:120] or title,
                        where=f"memory/biography/residual/{sid}.json",
                        why=(
                            f"Filed work session — theme «{theme}»"
                            if theme
                            else "Filed work session on your local Mag disk."
                        ),
                    ),
                },
            }
        )
        day_positions[sid] = (x, y, z, ang, S)
        edges.append(
            {
                "source": "tip",
                "target": nid,
                "kind": "hierarchy",
                "weight": 0.35 + 0.4 * tens,
            }
        )
        if i > 0:
            prev_sid = primary_rows[i - 1].get("session_id")
            edges.append(
                {
                    "source": f"day:{prev_sid}",
                    "target": nid,
                    "kind": "history",
                    "weight": 0.85,
                }
            )

        themes = list(reg.get("themes") or [])
        if reg.get("dominant_theme") and reg["dominant_theme"] not in themes:
            themes.insert(0, reg["dominant_theme"])
        for th in themes[:6]:
            if not th:
                continue
            by_theme.setdefault(str(th), []).append(nid)

        # Real subsessions from agent transcript; fallback to bullet summaries
        sub_n, sub_e = _subsessions_from_transcript(
            sid, nid, x=x, y=y, z=z, ang=ang, S=S
        )
        nodes.extend(sub_n)
        edges.extend(sub_e)
        n_subsessions += len(sub_n)
        if not sub_n:
            asks = bullets[:4]
            for j, ask in enumerate(asks):
                aid = f"ask:{sid[:8]}:{j}"
                a_ang = ang + (j - 1.5) * 0.22
                ar = 0.55 + j * 0.08
                nodes.append(
                    {
                        "id": aid,
                        "label": str(ask)[:36],
                        "kind": "turn",
                        "layer": "frame",
                        "core": False,
                        "S": S * 0.5,
                        "x": x + ar * math.cos(a_ang),
                        "y": y + 0.15 * j,
                        "z": z + ar * math.sin(a_ang),
                        "visual": visual_profile("turn", tension_index=tens, S=S * 0.5),
                        "meta": {
                            "parent": nid,
                            "text": str(ask)[:160],
                            **_layman_block(
                                what=str(ask)[:100],
                                where=f"memory/biography/residual/{sid}.json (summary bullet)",
                                why="Summary bullet when no live transcript file exists.",
                            ),
                        },
                    }
                )
                edges.append(
                    {"source": nid, "target": aid, "kind": "affinity", "weight": 0.55}
                )

        run_n, run_e = _runs_for_session(
            sid, nid, related, x=x, y=y, z=z, ang=ang, S=S
        )
        nodes.extend(run_n)
        edges.extend(run_e)
        n_runs += len(run_n)

        lat_n, lat_e = _lattice_node(
            reg,
            nid,
            x=x,
            y=y,
            z=z,
            prev_lattice=prev_lattice,
            chain_index=lattice_chain_idx,
            Q_proxy=Q_proxy_f,
        )
        nodes.extend(lat_n)
        edges.extend(lat_e)
        n_lattice += len(lat_n)
        if lat_n:
            prev_lattice = lat_n[0]["id"]
            lattice_chain_idx += 1

    # Orchestrator workers → sub-beads on nearest primary session (not separate days)
    for oi, orc in enumerate(orc_rows):
        ot = _parse_minute(orc.get("end_minute") or orc.get("start_minute"))
        best: dict[str, Any] | None = None
        best_d = float("inf")
        for pr in primary_rows:
            pt = _parse_minute(pr.get("end_minute") or pr.get("start_minute"))
            d = abs(ot - pt)
            if d < best_d:
                best_d = d
                best = pr
        if not best or best_d > 7200:
            continue
        psid = str(best.get("session_id") or "")
        pos = day_positions.get(psid)
        if not pos:
            continue
        x, y, z, ang, S = pos
        on, oe = _orc_worker_nodes(
            orc, f"day:{psid}", x=x, y=y, z=z, ang=ang, S=S, idx=oi
        )
        nodes.extend(on)
        edges.extend(oe)
        n_runs += len(on)

    # theme beads on outer ring (self-similar cluster centers)
    theme_ids = sorted(by_theme.keys())
    tn = max(len(theme_ids), 1)
    theme_r = 5.5
    for ti, th in enumerate(theme_ids):
        ang = (ti / tn) * math.tau
        tid = f"theme:{th}"
        S = THEME_COLORS.get(th, -0.2)
        nodes.append(
            {
                "id": tid,
                "label": th,
                "kind": "theme",
                "layer": "substrate",
                "core": th in ("mirror_meta", "constitution"),
                "S": S,
                "x": theme_r * math.cos(ang),
                "y": -2.2,
                "z": theme_r * math.sin(ang),
                "visual": visual_profile(
                    "theme",
                    S=S,
                    n_children=len(by_theme[th]),
                    core=th in ("mirror_meta", "constitution"),
                ),
                "meta": {"n_days": len(by_theme[th])},
            }
        )
        for day_id in by_theme[th]:
            edges.append(
                {
                    "source": tid,
                    "target": day_id,
                    "kind": "spatial",
                    "weight": 0.4,
                }
            )

    # framework docs as outer shell beads (project DNA fidelity)
    doc_shell = [
        ("doc:DNA", "DNA", "docs/DNA.md"),
        ("doc:ZEITGEIST", "Zeitgeist", "docs/ZEITGEIST.md"),
        ("doc:FRACTAL", "Fractal beads", "docs/FRACTAL_BEADS.md"),
        ("doc:ROADMAP", "Roadmap", "docs/ORG_ROADMAP.md"),
    ]
    for di, (did, label, path) in enumerate(doc_shell):
        ang = (di / max(len(doc_shell), 1)) * math.tau + 0.4
        nodes.append(
            {
                "id": did,
                "label": label,
                "kind": "doc",
                "layer": "object",
                "core": True,
                "S": -3.5,
                "x": 7.0 * math.cos(ang),
                "y": 2.5,
                "z": 7.0 * math.sin(ang),
                "visual": visual_profile("doc", S=-3.5),
                "meta": {"path": path},
            }
        )
        edges.append(
            {"source": "tip", "target": did, "kind": "residual", "weight": 0.5}
        )

    pack = {
        "schema": "mag_tapestry_pack.v3",
        "engine": "mirror-compatible",
        "note": (
            "Mag residual DNA as explorable graph: day helix, real subsession trees "
            "from agent_sessions, orchestrator runs as sub-beads, Verkle lattice knots "
            "with Steiniger temperature visual grammar (ops metaphor)."
        ),
        "ts": datetime.now(timezone.utc).isoformat(),
        "transforms": {
            "days": "helix radius=3 height=8 — primary sessions only (orc workers attach as runs)",
            "subsessions": "radial children from memory/agent_sessions/*.json user turns",
            "lattice": "torus-knot chain under days — hash-seeded (p,q), micro-helix",
            "visual": "steiniger_temp → shape/scale; tension_index from residual",
            "themes": "ring radius=5.5 y=-2.2",
            "docs": "outer shell radius=7 y=2.5",
        },
        "connections": {"nodes": nodes, "edges": edges},
        "stats": {
            "n_nodes": len(nodes),
            "n_edges": len(edges),
            "n_days": len(primary_rows),
            "n_orc_attached": len(orc_rows),
            "n_subsessions": n_subsessions,
            "n_runs": n_runs,
            "n_lattice": n_lattice,
            "n_themes": len(theme_ids),
            "n_docs": len(doc_shell),
        },
        "english": {
            "headline": "Workdays as beads — subsessions as children",
            "blurb": (
                f"{len(primary_rows)} day beads on a time helix. "
                f"{n_subsessions} live transcript turns, {n_runs} run/worker sub-beads, "
                f"{n_lattice} Verkle lattice anchors. Hover any ball for what / where / why."
            ),
            "legend": {
                "session": "One filed workday — click to pin context",
                "subsession": "Real operator turn from agent transcript",
                "run": "Orchestrator trail or worker task",
                "lattice": "Verkle proof bead (toggle visibility)",
                "turn": "Summary bullet when transcript missing",
                "theme": "Shared topic cluster",
            },
        },
    }
    return pack


def write_tapestry_pack(path: Path | None = None) -> dict[str, Any]:
    pack = build_tapestry_pack()
    out = path or OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(pack, indent=2, default=str), encoding="utf-8")
    pack["path"] = str(out)
    return pack
