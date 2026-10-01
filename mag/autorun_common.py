"""Shared helpers for Mag Autorun v1 — pack refresh, FKB scoring, pause gates."""
from __future__ import annotations

from typing import Any


def autorun_pause_reason() -> str | None:
    """Return a human reason if autorun should not execute this tick."""
    try:
        from mag.operator_mode import pause_reason

        shared = pause_reason()
        if shared:
            return shared
    except Exception:
        pass
    try:
        from mag.preferences import autorun_allowed, operator_status

        if not autorun_allowed():
            st = operator_status()
            if st.get("operator_active"):
                return "operator_active (Composer/Cursor seat — drainer paused)"
            return "drainer_disabled"
    except Exception:
        pass
    return None


def refresh_context_for_goal(goal: str) -> dict[str, Any]:
    """Pack-first: refresh context pack before spawning a queued agent."""
    import json
    from pathlib import Path

    from config import ROOT

    goal = (goal or "").strip()
    try:
        from mag.context_pack import (
            build_context_pack,
            format_agent_preamble,
            format_context_pack_text,
            infer_pack_mode,
        )

        mode = infer_pack_mode(goal)
        pack = build_context_pack(mode=mode, goal=goal, fast=True)
        out_md = ROOT / "memory" / "context_pack_latest.md"
        out_md.parent.mkdir(parents=True, exist_ok=True)
        text = format_context_pack_text(pack, mode=mode)
        out_md.write_text(text, encoding="utf-8")
        (ROOT / "memory" / "context_pack_latest.json").write_text(
            json.dumps(pack, indent=2, default=str), encoding="utf-8"
        )
        if goal:
            preamble = format_agent_preamble(pack, goal=goal[:300])
            ap = ROOT / "memory" / "agent_preamble_latest.md"
            ap.write_text(preamble, encoding="utf-8")
        return {"ok": True, "md": str(out_md)}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


def fkb_score_adjustment(goal: str, *, tool: str | None = None) -> float:
    """Negative score bump when goal matches a recurring failure signature."""
    try:
        from mag.failure_kb import query

        hits = query((goal or "")[:120], tool=tool, limit=1)
        if not hits:
            return 0.0
        cnt = int(hits[0].get("count") or 0)
        if cnt >= 5:
            return -3.0
        if cnt >= 3:
            return -1.0
        if cnt >= 2:
            return -0.25
    except Exception:
        pass
    return 0.0


def fkb_block_for_goal(goal: str) -> str | None:
    """Block auto-queue when a pattern is hot unless operator tagged [mag]."""
    g = (goal or "").strip()
    if "[mag]" in g.lower() or g.lower().startswith("[improve]"):
        return None
    try:
        from mag.failure_kb import query

        hits = query(g[:120], limit=1)
        if hits and int(hits[0].get("count") or 0) >= 8:
            return (
                f"FKB block: recurring failure ×{hits[0].get('count')} "
                f"({hits[0].get('sig', '')[:24]}) — add [mag] to force or fix remedy"
            )
    except Exception:
        pass
    return None
