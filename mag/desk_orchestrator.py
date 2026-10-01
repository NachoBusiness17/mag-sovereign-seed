"""Desk orchestrator — gemma:2b local seat watching canvas + remote lane."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from config import ROOT
from mag.agent_desk import REMOTE_SESSION, peer_lane_excerpt, read_desk

PROMPT_PATH = ROOT / "prompts" / "desk_orchestrator.txt"


def _system() -> str:
    if PROMPT_PATH.is_file():
        return PROMPT_PATH.read_text(encoding="utf-8", errors="replace").strip()
    return "You are Mag desk orchestrator. Short markdown sections. Introspective."


def orchestrate(
    question: str,
    *,
    desk_canvas: str | None = None,
    peer_context: str | None = None,
    remote_live: str | None = None,
    include_peer_lane: bool = True,
    session_id: str = "desk-local",
) -> dict[str, Any]:
    q = (question or "").strip()
    if not q:
        return {"ok": False, "error": "question required"}

    canvas = (desk_canvas or "").strip()
    if not canvas:
        canvas = (read_desk().get("text") or "").strip()

    peer = (peer_context or "").strip()
    if not peer and include_peer_lane:
        peer = peer_lane_excerpt(REMOTE_SESSION, last_n=12)

    live = (remote_live or "").strip()
    if not live:
        try:
            from mag.agent_cli import get_live_turn

            snap = get_live_turn(REMOTE_SESSION)
            if snap.get("active"):
                live = (
                    f"ACTIVE · round {snap.get('round') or '?'} · "
                    f"phase={snap.get('phase') or '?'} · tool={snap.get('tool') or '-'} · "
                    f"{snap.get('detail') or ''} · idle {snap.get('idle_s', 0)}s"
                )
        except Exception:
            pass

    from models.registry import model_for

    model = model_for("desk_orchestrator")

    blocks = []
    if canvas:
        blocks.append(f"## Shared canvas\n{canvas[:5000]}")
    if live:
        blocks.append(f"## DeepSeek LIVE (in-memory — not stale session file)\n{live[:2000]}")
    if peer:
        blocks.append(f"## DeepSeek lane (session excerpt)\n{peer[:8000]}")
    elif not live:
        blocks.append("## DeepSeek lane\n(empty — no remote turns filed yet)")

    user = (
        "\n\n".join(blocks)
        + f"\n\n## Operator\n{q}\n\nReply with markdown sections per your instructions."
    )

    try:
        from llm import chat

        answer = chat("orchestrator", _system(), user, temperature=0.25).strip()
    except Exception as e:
        return {"ok": False, "error": str(e), "role": "orchestrator", "model": model}

    return {
        "ok": True,
        "answer": answer,
        "role": "orchestrator",
        "model": model,
        "session_id": session_id,
        "had_canvas": bool(canvas),
        "had_peer": bool(peer),
        "had_live": bool(live),
    }
