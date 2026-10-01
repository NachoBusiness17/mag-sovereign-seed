"""Mag Visual Pack — one reproducible geometry for many chambers.

Tesuji: freeze living-record state into a single pack that:
  · amends in place (same session_id)
  · maps internal Mag process → named chambers (connection, signature,
    residual, belt, attention, dual_orbit, spectral)
  · carries English readings for cold communication
  · needs no strike demo knots

Output:
  memory/biography/<session_id>.visual_pack.json
  memory/biography/latest.visual_pack.json
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT

BIO = ROOT / "memory" / "biography"
SCHEMA = "mag_visual_pack.v1"


def _h(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _clip(s: Any, n: int = 200) -> str:
    t = str(s or "").strip()
    return t if len(t) <= n else t[: n - 1] + "…"


def resolve_session_id(session_id: str | None = None) -> str | None:
    if session_id and session_id not in ("", "latest"):
        return session_id
    d = _read_json(BIO / "latest.dossier.json")
    if d and d.get("session_id"):
        return str(d["session_id"])
    files = sorted(
        [p for p in BIO.glob("*.dossier.json") if not p.name.startswith("latest")],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return files[0].name.replace(".dossier.json", "") if files else None


def _fourier(series: list[float], n_harmonics: int = 8) -> list[dict[str, float]]:
    m = len(series)
    if m < 2:
        return [{"k": 1, "amp": 0.5, "phase": 0.0, "amp_n": 1.0}]
    mean = sum(series) / m
    y = [v - mean for v in series]
    coeffs = []
    for k in range(1, n_harmonics + 1):
        a = b = 0.0
        for i, yi in enumerate(y):
            t = 2 * math.pi * i / m
            a += yi * math.cos(k * t)
            b += yi * math.sin(k * t)
        a = 2 * a / m
        b = 2 * b / m
        amp = math.hypot(a, b)
        phase = math.atan2(b, a)
        coeffs.append({"k": k, "amp": amp, "phase": phase, "a": a, "b": b})
    max_a = max((c["amp"] for c in coeffs), default=1.0) or 1.0
    for c in coeffs:
        c["amp_n"] = c["amp"] / max_a
    return coeffs


def _layout_circle(n: int, r: float = 1.0, phase: float = 0.0) -> list[tuple[float, float]]:
    if n <= 0:
        return []
    if n == 1:
        return [(0.0, 0.0)]
    return [
        (r * math.cos(phase + 2 * math.pi * i / n), r * math.sin(phase + 2 * math.pi * i / n))
        for i in range(n)
    ]


def _layout_spectral_2d(n: int, edges: list[tuple[int, int, float]], seed: int = 0) -> list[tuple[float, float]]:
    """Cheap force-ish layout from circle + edge pull (no numpy)."""
    if n <= 0:
        return []
    pts = list(_layout_circle(n, 2.2, seed * 0.01))
    # a few relax iterations
    for _ in range(40):
        forces = [(0.0, 0.0) for _ in range(n)]
        for i in range(n):
            for j in range(i + 1, n):
                dx = pts[i][0] - pts[j][0]
                dy = pts[i][1] - pts[j][1]
                dist = math.hypot(dx, dy) or 0.01
                # repel
                f = 0.08 / (dist * dist)
                fx, fy = f * dx / dist, f * dy / dist
                forces[i] = (forces[i][0] + fx, forces[i][1] + fy)
                forces[j] = (forces[j][0] - fx, forces[j][1] - fy)
        for i, j, w in edges:
            if i >= n or j >= n:
                continue
            dx = pts[j][0] - pts[i][0]
            dy = pts[j][1] - pts[i][1]
            dist = math.hypot(dx, dy) or 0.01
            # spring toward ideal length ~1.2
            ideal = 1.2
            f = 0.04 * w * (dist - ideal)
            fx, fy = f * dx / dist, f * dy / dist
            forces[i] = (forces[i][0] + fx, forces[i][1] + fy)
            forces[j] = (forces[j][0] - fx, forces[j][1] - fy)
        pts = [
            (pts[i][0] + forces[i][0] * 0.5, pts[i][1] + forces[i][1] * 0.5)
            for i in range(n)
        ]
    # center
    cx = sum(p[0] for p in pts) / n
    cy = sum(p[1] for p in pts) / n
    return [(p[0] - cx, p[1] - cy) for p in pts]


def _holonomy(frames: list[str], seed: str) -> dict[str, Any]:
    n = len(frames)
    if n < 2:
        return {
            "frames": frames,
            "transports": [],
            "holonomy": 1,
            "odd": False,
            "note": "Need ≥2 frames.",
        }
    transports = []
    H = 1
    for i in range(n):
        a, b = frames[i], frames[(i + 1) % n]
        raw = int(_h(a, b, seed)[:8], 16)
        # bias: high residual language → odd transport more often on last edge
        u = 1 if (raw % 2 == 0) else -1
        if i == n - 1 and "residual" in seed.lower():
            u = -1
        transports.append({"from": a, "to": b, "transport": u})
        H *= u
    return {
        "frames": frames,
        "transports": transports,
        "holonomy": H,
        "odd": H < 0,
        "note": (
            "Odd holonomy: one full spin still twisted — do not force-close."
            if H < 0
            else "Even holonomy: belts can rest after a double-pass class."
        ),
    }


def build_visual_pack(session_id: str | None = None) -> dict[str, Any]:
    """Assemble Mag → visual pack for the given (or latest) session."""
    sid = resolve_session_id(session_id)
    if not sid:
        return {"ok": False, "error": "no session dossier found", "schema": SCHEMA}

    dossier = _read_json(BIO / f"{sid}.dossier.json") or _read_json(BIO / "latest.dossier.json") or {}
    md_path = BIO / f"{sid}.md"
    md = md_path.read_text(encoding="utf-8", errors="replace") if md_path.is_file() else ""
    brief_path = ROOT / "memory" / "briefs" / f"{sid}.md"
    if not brief_path.is_file():
        brief_path = ROOT / "memory" / "briefs" / "latest.md"
    brief = brief_path.read_text(encoding="utf-8", errors="replace") if brief_path.is_file() else ""
    evo = _read_json(BIO / "topic_evolution.json") or {}
    tip = _read_json(BIO / "verkle_tip.json") or {}
    live = ""
    live_p = ROOT / "memory" / "live_from_grok.md"
    if live_p.is_file():
        live = live_p.read_text(encoding="utf-8", errors="replace")[:2000]

    time = dossier.get("time") or {}
    chord = dossier.get("chord") or {}
    sk = dossier.get("scalar_knot") or {}
    lay = dossier.get("steiniger_laymen") or {}
    themes = dossier.get("themes") or []
    verkle = dossier.get("verkle_knot") or {}
    title = time.get("title") or chord.get("plain_english") or f"Mag session {sid[:12]}"

    # --- series (time signature) ---
    series_rows = evo.get("series") or []
    # prefer full evolution; highlight this session
    points = []
    for i, row in enumerate(series_rows[-48:]):
        points.append(
            {
                "i": i,
                "session_id": row.get("session_id"),
                "t": row.get("end_unix_minute") or row.get("start_unix_minute") or i,
                "label": _clip(row.get("dominant_theme") or "?", 24),
                "S": float(row.get("tension_index") or 0.0),
                "theme": row.get("dominant_theme"),
                "active": str(row.get("session_id") or "") == sid,
                "vector": row.get("theme_vector_normalized") or [],
            }
        )
    if not points and sk.get("tension_index") is not None:
        points = [
            {
                "i": 0,
                "session_id": sid,
                "t": 0,
                "label": (sk.get("theme_vector") or {}).get("dominant") or "session",
                "S": float(sk.get("tension_index") or 0),
                "theme": (sk.get("theme_vector") or {}).get("dominant"),
                "active": True,
                "vector": (sk.get("theme_vector") or {}).get("normalized") or [],
            }
        ]
    S_series = [float(p["S"]) for p in points] or [0.5]
    fourier = _fourier(S_series)

    # --- frames / holonomy (belt) ---
    frames_src = lay.get("frames") or []
    frame_ids = []
    for f in frames_src:
        if isinstance(f, dict) and f.get("active", True):
            frame_ids.append(str(f.get("id") or f.get("label") or "frame"))
    if not frame_ids:
        frame_ids = ["work", "identity", "capture", "personal"]
    charts = chord.get("observer_charts") or []
    for c in charts:
        if isinstance(c, dict) and c.get("active"):
            fid = str(c.get("id") or c.get("label"))
            if fid not in frame_ids:
                frame_ids.append(fid)
    residual_hint = " ".join(str(x) for x in (lay.get("residual_bonds") or [])[:3])
    holonomy = _holonomy(frame_ids[:8], residual_hint or title)

    # --- connection graph nodes ---
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []

    def add_node(nid: str, label: str, role: str, plain: str = "", weight: float = 0.5, **extra: Any) -> None:
        if any(n["id"] == nid for n in nodes):
            return
        nodes.append(
            {
                "id": nid,
                "label": _clip(label, 48),
                "role": role,
                "plain": _clip(plain, 240),
                "weight": weight,
                **extra,
            }
        )

    add_node("topic", _clip(title, 60), "topic", chord.get("plain_english") or md[:200], 1.0)
    add_node(
        "rope",
        "Rope",
        "tension",
        chord.get("rope") or (lay.get("tension") or ["—"])[0] if lay.get("tension") else chord.get("rope") or "—",
        float(sk.get("tension_index") or 0.5),
    )
    edges.append({"source": "topic", "target": "rope", "kind": "tension", "weight": 0.9, "reason": "session rope"})

    for i, t in enumerate(themes[:8]):
        if not isinstance(t, dict):
            continue
        tid = f"theme:{t.get('id')}"
        add_node(tid, str(t.get("id")), "theme", f"score {t.get('score')}", min(1.0, float(t.get("score") or 0) / 200.0))
        edges.append({"source": "topic", "target": tid, "kind": "theme", "weight": 0.5 + min(0.5, float(t.get("score") or 0) / 400.0)})

    for i, r in enumerate((lay.get("residual_bonds") or [])[:10]):
        rid = f"residual:{i}"
        add_node(rid, _clip(r, 40), "residual", str(r), 0.85)
        edges.append({"source": "topic", "target": rid, "kind": "residual", "weight": 0.7, "reason": "keep after cleanup"})

    for i, m in enumerate((chord.get("disentangled_moves") or lay.get("good_moves") or [])[:8]):
        mid = f"move:{i}"
        add_node(mid, _clip(m, 40), "move", str(m), 0.6)
        edges.append({"source": "rope", "target": mid, "kind": "move", "weight": 0.55, "reason": "disentangled move"})

    for i, L in enumerate((chord.get("loops_audited") or [])[:6]):
        lid = f"loop:{L.get('id') if isinstance(L, dict) else i}"
        plain = L.get("plain") if isinstance(L, dict) else str(L)
        add_node(lid, _clip(L.get("id") if isinstance(L, dict) else L, 36), "loop", plain, 0.7)
        edges.append({"source": "rope", "target": lid, "kind": "loop", "weight": 0.65, "reason": "loop audited"})

    for i, c in enumerate(charts[:6]):
        if not isinstance(c, dict):
            continue
        cid = f"chart:{c.get('id')}"
        add_node(
            cid,
            str(c.get("label") or c.get("id")),
            "chart",
            c.get("plain") or "",
            min(1.0, float(c.get("score") or 0) / 50.0),
            score=c.get("score"),
            active=c.get("active"),
        )
        edges.append(
            {
                "source": "topic",
                "target": cid,
                "kind": "chart",
                "weight": min(1.0, 0.3 + float(c.get("score") or 0) / 80.0),
            }
        )

    # protected core
    for i, p in enumerate((lay.get("protected_core") or [])[:5]):
        pid = f"core:{i}"
        add_node(pid, _clip(p, 36), "core", str(p), 0.95)
        edges.append({"source": "topic", "target": pid, "kind": "core", "weight": 0.9})

    # layout
    id_to_i = {n["id"]: i for i, n in enumerate(nodes)}
    edge_idx = []
    for e in edges:
        a, b = id_to_i.get(e["source"]), id_to_i.get(e["target"])
        if a is not None and b is not None:
            edge_idx.append((a, b, float(e.get("weight") or 0.5)))
    coords = _layout_spectral_2d(len(nodes), edge_idx)
    for i, n in enumerate(nodes):
        if i < len(coords):
            n["x"], n["y"] = coords[i]
            n["z"] = 0.15 * math.sin(i * 0.7)  # slight depth for 3-feel

    # --- residual chamber (subset) ---
    residual_nodes = [n for n in nodes if n["role"] in ("residual", "topic", "rope", "core")]
    residual_edges = [
        e
        for e in edges
        if e.get("kind") in ("residual", "core", "tension")
        or e["source"] in {n["id"] for n in residual_nodes}
        and e["target"] in {n["id"] for n in residual_nodes}
    ]

    # --- attention matrix on charts/themes ---
    att_frames = [str(c.get("label") or c.get("id")) for c in charts if isinstance(c, dict)][:6]
    if len(att_frames) < 2:
        att_frames = [str(t.get("id")) for t in themes[:6] if isinstance(t, dict)] or frame_ids[:4]
    scores = []
    for c in charts:
        if isinstance(c, dict):
            scores.append(float(c.get("score") or 0))
    while len(scores) < len(att_frames):
        scores.append(1.0)
    scores = scores[: len(att_frames)]
    # outer product normalized → attention-like matrix
    matrix = []
    for i, si in enumerate(scores):
        row = []
        for j, sj in enumerate(scores):
            if i == j:
                row.append(1.0)
            else:
                row.append(min(1.0, (si * sj) / ((sum(scores) ** 2) / max(len(scores), 1) + 1e-6)))
        s = sum(row) or 1.0
        matrix.append([x / s for x in row])

    # --- dual orbit: hands vs mirror ---
    theme_ids = {(t.get("id") if isinstance(t, dict) else None) for t in themes}
    hands = any(x in theme_ids for x in ("mag_hands", "harness", "dashboard", "scrum_plan"))
    mirror = any(x in theme_ids for x in ("mirror_meta", "biography", "constitution", "data_r0"))
    dual = {
        "track_a": {
            "id": "hands",
            "label": "Hands / Mag",
            "active": hands or True,
            "items": [t.get("id") for t in themes if isinstance(t, dict) and t.get("id") in ("mag_hands", "harness", "dashboard", "scrum_plan")],
        },
        "track_b": {
            "id": "mirror",
            "label": "Mirror / meta",
            "active": mirror or True,
            "items": [t.get("id") for t in themes if isinstance(t, dict) and t.get("id") in ("mirror_meta", "biography", "constitution", "data_r0")],
        },
        "center": _clip(title, 40),
        "tension": float(sk.get("tension_index") or 0.5),
    }

    # --- spectral nodes (3d-ish from 2d + z) ---
    spectral_nodes = [
        {
            "id": n["id"],
            "label": n["label"],
            "role": n["role"],
            "x": n.get("x", 0),
            "y": n.get("y", 0),
            "z": n.get("z", 0),
            "S": n.get("weight", 0.5),
        }
        for n in nodes
    ]

    # --- english readings (communication layer) ---
    odd = holonomy.get("odd")
    top_theme = (sk.get("theme_vector") or {}).get("dominant") or (
        themes[0].get("id") if themes and isinstance(themes[0], dict) else "session"
    )
    residual_one = _clip(
        (lay.get("residual_bonds") or ["session living record"])[0],
        120,
    )
    move0 = _clip(
        (chord.get("disentangled_moves") or lay.get("good_moves") or ["Re-read brief before new epics"])[0],
        120,
    )
    english = {
        "headline": _clip(chord.get("plain_english") or title, 280),
        "impact": _clip(chord.get("personal_impact") or "", 280),
        "rope": _clip(chord.get("rope") or "", 200),
        "residual": residual_one,
        "move": move0,
        "commitment": chord.get("commitment_hash") or "",
        "dominant_theme": top_theme,
        "tension_index": sk.get("tension_index"),
        "lane_hint": "L0 local first · L2 only with [priority]",
    }

    readings = [
        {
            "chamber": "connection",
            "title": "Connection graph",
            "question": "What is actually connected in this session?",
            "headline": f"Topic hub · {top_theme}",
            "body": "People/themes/residuals/moves hang off the session question. Residual edges must survive polish.",
        },
        {
            "chamber": "signature",
            "title": "Fourier signature",
            "question": "What rhythm does tension leave across the living record?",
            "headline": (
                f"{len(points)} points · strongest harmonic k="
                f"{(sorted(fourier, key=lambda c: c.get('amp_n') or 0, reverse=True) or [{}])[0].get('k', 1)}"
            ),
            "body": "Epicycles of tension_index over Verkle series — fingerprint of how the work breathes, not a verdict.",
        },
        {
            "chamber": "residual",
            "title": "Hyperbolic residual",
            "question": "What must not die after cleanup?",
            "headline": residual_one,
            "body": "High-fidelity leftovers after noise. Amending the session updates these; it does not invent a new throne.",
        },
        {
            "chamber": "belt",
            "title": "Belt / twist",
            "question": "Did we fake-close after one spin through frames?",
            "headline": "ODD — still twisted" if odd else "EVEN — belts can rest",
            "body": holonomy.get("note") or "",
        },
        {
            "chamber": "attention",
            "title": "Attention · entropy",
            "question": "Where did observer mass pool?",
            "headline": " · ".join(f"{a}:{int(s)}" for a, s in zip(att_frames, scores))[:120],
            "body": "Chart/theme scores as field — personal rope often dominates; name interference instead of crowning one chart.",
        },
        {
            "chamber": "dual_orbit",
            "title": "Cube–ring dual orbit",
            "question": "Hands and mirror — still orbiting the same center?",
            "headline": f"{dual['track_a']['label']} ⟷ {dual['track_b']['label']}",
            "body": "Two tracks around one question. Capture is when one pretends to be the whole product.",
        },
        {
            "chamber": "spectral",
            "title": "Spectral manifold",
            "question": "How does the bond graph embed in space?",
            "headline": f"{len(nodes)} nodes · {len(edges)} bonds",
            "body": "Layout from affinity springs — clusters are themes of work, not authority.",
        },
    ]

    walk = [
        {"step": 1, "chamber": "connection", "say": f"Question: {_clip(title, 80)}"},
        {"step": 2, "chamber": "dual_orbit", "say": "Hold hands and mirror without crowning either."},
        {"step": 3, "chamber": "attention", "say": "Name where attention pooled."},
        {"step": 4, "chamber": "belt", "say": holonomy.get("note") or "Check twist."},
        {"step": 5, "chamber": "residual", "say": f"Keep: {residual_one}"},
        {"step": 6, "chamber": "signature", "say": "See the rhythm across sessions."},
        {"step": 7, "chamber": "connection", "say": f"Next move: {move0}"},
    ]

    commit = _h(
        sid,
        str(sk.get("tension_index")),
        str(chord.get("commitment_hash")),
        str(verkle.get("leaf_hash") or tip.get("last_leaf_hash")),
        str(len(nodes)),
        str(points[-1].get("S") if points else 0),
    )[:16]

    pack = {
        "ok": True,
        "schema": SCHEMA,
        "session_id": sid,
        "title": title,
        "commit": commit,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source": {
            "dossier": f"memory/biography/{sid}.dossier.json",
            "brief": str(brief_path.relative_to(ROOT)) if brief_path.is_file() else None,
            "verkle_leaf": verkle.get("filename"),
            "verkle_root": tip.get("root") or evo.get("verkle_root"),
            "n_leaves": tip.get("n_leaves") or evo.get("n_leaves"),
        },
        "english": english,
        "meters": {
            "tension_index": sk.get("tension_index"),
            "Q_proxy": sk.get("Q_proxy"),
            "gap_proxy": sk.get("gap_proxy"),
            "lambda2_proxy": sk.get("lambda2_proxy"),
            "duration_minutes": sk.get("duration_minutes"),
            "holonomy_odd": odd,
        },
        "chambers": {
            "connection": {"nodes": nodes, "edges": edges},
            "signature": {
                "points": points,
                "fourier": fourier,
                "source": "topic_evolution.series",
            },
            "residual": {"nodes": residual_nodes, "edges": residual_edges},
            "belt": holonomy,
            "attention": {
                "frames": att_frames,
                "matrix": matrix,
                "scores": scores,
            },
            "dual_orbit": dual,
            "spectral": {"nodes": spectral_nodes, "edges": edges},
        },
        "readings": readings,
        "walk": walk,
        "brief_excerpt": _clip(brief, 800),
        "live_excerpt": _clip(live, 400),
        "repro": {
            "note": "Same session_id + same living record → same commit when inputs unchanged.",
            "open": f"/api/visual/{sid}",
            "file": f"memory/biography/{sid}.visual_pack.json",
        },
    }
    return pack


def write_visual_pack(session_id: str | None = None) -> dict[str, Any]:
    """Build visual pack as optional derived artifact (+ flat mirror for links)."""
    pack = build_visual_pack(session_id)
    if not pack.get("ok"):
        return pack
    sid = pack["session_id"]
    BIO.mkdir(parents=True, exist_ok=True)
    try:
        from mag.registry import write_derived_visual

        path = write_derived_visual(sid, pack)
    except Exception:
        path = BIO / f"{sid}.visual_pack.json"
        latest = BIO / "latest.visual_pack.json"
        raw = json.dumps(pack, indent=2, default=str)
        path.write_text(raw, encoding="utf-8")
        latest.write_text(raw, encoding="utf-8")
    latest = BIO / "latest.visual_pack.json"
    try:
        from mag.lanes import log_usage

        log_usage(
            lane="L0",
            action="visual_pack",
            detail=f"session={sid[:13]} commit={pack.get('commit')}",
            ok=True,
            meta={
                "path": str(path),
                "commit": pack.get("commit"),
                "n_nodes": len(
                    pack.get("chambers", {}).get("connection", {}).get("nodes") or []
                ),
                "derived": True,
            },
        )
    except Exception:
        pass
    return {
        "ok": True,
        "session_id": sid,
        "path": str(path),
        "latest": str(latest),
        "commit": pack.get("commit"),
        "n_nodes": len(pack["chambers"]["connection"]["nodes"]),
        "n_edges": len(pack["chambers"]["connection"]["edges"]),
        "holonomy_odd": pack.get("meters", {}).get("holonomy_odd"),
        "derived": True,
    }
