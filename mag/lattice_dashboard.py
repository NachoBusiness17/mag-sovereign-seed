"""Verkle lattice history + planning summary for dashboard.

Viewport only — not a second DNA store. Reads tip/chain/evolution/timeline + working + agent_state.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT

BIO = ROOT / "memory" / "biography"
THEME_BASIS_DEFAULT = [
    "mirror_meta",
    "mag_hands",
    "scrum_plan",
    "constitution",
    "dashboard",
    "harness",
    "biography",
    "data_r0",
]


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _read_jsonl(path: Path, limit: int = 500) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    except Exception:
        return []
    if len(rows) > limit:
        return rows[-limit:]
    return rows


def _parse_working_open() -> list[dict[str, str]]:
    wp = ROOT / "memory" / "working.md"
    if not wp.is_file():
        return []
    items: list[dict[str, str]] = []
    in_open = False
    for line in wp.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.strip().startswith("## Open"):
            in_open = True
            continue
        if in_open and line.startswith("## "):
            break
        if not in_open:
            continue
        s = line.strip()
        if not s.startswith("-"):
            continue
        status = "open"
        m = re.search(r"\[([^\]]+)\]", s)
        if m:
            status = m.group(1).strip().lower()
        items.append({"text": s.lstrip("- ").strip()[:240], "status": status})
    return items[:20]


def _agent_next() -> list[dict[str, str]]:
    lat = _read_json(ROOT / "memory" / "agent_state" / "LATEST.json")
    if not lat:
        # fall back to md is weaker — try versions tip payload
        return []
    out: list[dict[str, str]] = []
    for m in lat.get("next_moves") or []:
        if isinstance(m, dict):
            out.append(
                {
                    "id": str(m.get("id") or ""),
                    "title": str(m.get("title") or m.get("id") or ""),
                    "status": str(m.get("status") or "open"),
                }
            )
    return out


def _theme_name(basis: list[str], vec: list[float] | None) -> str:
    if not vec or not basis:
        return "—"
    try:
        i = max(range(len(vec)), key=lambda j: float(vec[j]) if j < len(vec) else 0.0)
        return basis[i] if i < len(basis) else "—"
    except Exception:
        return "—"


def build_lattice_summary() -> dict[str, Any]:
    tip = _read_json(BIO / "verkle_tip.json")
    chain = _read_jsonl(BIO / "verkle_chain.jsonl")
    evo = _read_json(BIO / "topic_evolution.json")
    timeline = _read_jsonl(BIO / "knot_timeline.jsonl")
    basis = list(evo.get("theme_basis") or THEME_BASIS_DEFAULT)

    series = sorted(
        list(evo.get("series") or []),
        key=lambda r: r.get("start_minute") or "",
    )
    # normalize series rows for UI
    history: list[dict[str, Any]] = []
    for row in series:
        tv = row.get("theme_vector")
        # series may store theme_vector_normalized
        if not tv:
            tv = row.get("theme_vector_normalized")
        # timeline join by session_id
        sid = row.get("session_id") or ""
        tl = next((t for t in timeline if t.get("session_id") == sid), None)
        if tl and not tv:
            tv = tl.get("theme_vector")
        dominant = row.get("dominant_theme") or _theme_name(basis, tv)
        tension = row.get("tension_index")
        if tension is None and tl:
            tension = tl.get("tension_index")
        history.append(
            {
                "session_id": sid,
                "start_minute": row.get("start_minute") or (tl or {}).get("start_minute"),
                "end_minute": row.get("end_minute") or (tl or {}).get("end_minute"),
                "dominant_theme": dominant,
                "tension_index": tension,
                "duration_minutes": (tl or {}).get("duration_minutes")
                or row.get("duration_minutes"),
                "filename": row.get("filename") or row.get("last_filename"),
                "theme_vector": tv,
                "Q_proxy": (tl or {}).get("Q_proxy") or row.get("Q_proxy"),
                "amended": (tl or {}).get("amended"),
            }
        )

    # theme histogram
    hist: dict[str, int] = {b: 0 for b in basis}
    for h in history:
        d = h.get("dominant_theme") or "—"
        if d in hist:
            hist[d] += 1
        else:
            hist[d] = hist.get(d, 0) + 1

    # tension sparkline
    tensions = [
        float(h["tension_index"])
        for h in history
        if h.get("tension_index") is not None
    ]

    # chain tail enriched
    chain_tail = []
    for row in chain[-16:]:
        chain_tail.append(
            {
                "filename": row.get("filename") or row.get("leaf"),
                "session_id": row.get("session_id"),
                "verkle_root": (row.get("verkle_root") or "")[:16] or None,
                "ts": row.get("ts") or row.get("updated_minute") or row.get("start_minute"),
            }
        )

    open_work = _parse_working_open()
    agent_next = _agent_next()

    # plan face: open agent moves + working open
    plan = {
        "working_open": open_work,
        "agent_next": agent_next,
        "suggested_focus": None,
    }
    # prefer READY then open IJL/soil
    for item in open_work:
        st = item.get("status") or ""
        if "ready" in st:
            plan["suggested_focus"] = item.get("text")
            break
    if not plan["suggested_focus"]:
        for item in open_work:
            t = (item.get("text") or "").lower()
            if "ijl" in t or "annotate" in t or "soil" in t:
                plan["suggested_focus"] = item.get("text")
                break
    if not plan["suggested_focus"] and agent_next:
        open_a = [a for a in agent_next if a.get("status") == "open"]
        if open_a:
            plan["suggested_focus"] = open_a[0].get("title") or open_a[0].get("id")

    root = tip.get("root") or evo.get("verkle_root") or ""
    out: dict[str, Any] = {
        "ok": True,
        "schema": "lattice_dashboard.v1",
        "ts": datetime.now(timezone.utc).isoformat(),
        "tip": {
            "root": root,
            "root_short": root[:16] if root else None,
            "n_leaves": tip.get("n_leaves") or evo.get("n_leaves") or len(history),
            "last_filename": tip.get("last_filename"),
            "last_session_id": tip.get("last_session_id"),
            "updated_minute": tip.get("updated_minute"),
            "alive": bool(root and (tip.get("n_leaves") or 0) > 0),
        },
        "theme_basis": basis,
        "theme_histogram": hist,
        "history": history,
        "history_n": len(history),
        "tensions": tensions,
        "tension_latest": tensions[-1] if tensions else None,
        "tension_avg": (sum(tensions) / len(tensions)) if tensions else None,
        "chain_tail": chain_tail,
        "chain_n": len(chain),
        "plan": plan,
        "paths": {
            "tip": "memory/biography/verkle_tip.json",
            "chain": "memory/biography/verkle_chain.jsonl",
            "evolution": "memory/biography/topic_evolution.json",
            "timeline": "memory/biography/knot_timeline.jsonl",
            "working": "memory/working.md",
            "agent_state": "memory/agent_state/LATEST.md",
        },
        "plain": {
            "one_line": (
                f"Chain alive with {tip.get('n_leaves') or len(history)} leaves; "
                f"latest theme={(history[-1].get('dominant_theme') if history else '—')}; "
                f"focus={plan.get('suggested_focus') or 'none extracted'}"
            ),
            "help": (
                "Tip = is the session chain live. History = theme/tension over days. "
                "Plan = working.md open + agent_state next (not a second todo throne)."
            ),
        },
    }
    try:
        from mag.lattice_query import graph_viewport

        out["graph"] = graph_viewport(sample_n=8)
    except Exception:
        out["graph"] = {"store_exists": False}
    return out
