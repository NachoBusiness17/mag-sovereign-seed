"""Shared dig board — ambient research + conversation for local voice.

Idea: while you talk, a research loop (DeepSeek shadow) and Mag systems
(desk, pack tip, bonds, trail) fill one board. Local answers pull from it
emergently — like a canvas/scratchpad/verkle tip without a new museum UI.

Schema: mag_voice_dig_board.v1
Path: memory/working/voice_dig_board.md  (+ .json state)
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT

SCHEMA = "mag_voice_dig_board.v1"
BOARD_MD = ROOT / "memory" / "working" / "voice_dig_board.md"
BOARD_JSON = ROOT / "memory" / "working" / "voice_dig_board.json"
MAX_EPISODES = 12
MAX_BOARD_CHARS = 3500

# Hardware monologue that must not override life/Bernays topics
_SLUDGE = re.compile(
    r"\b("
    r"sam|smart access|resizable\s*bar|bios|vram|motherboard|"
    r"ram settings|memory settings|sam settings"
    r")\b",
    re.I,
)


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _has_sludge(text: str) -> bool:
    return bool(_SLUDGE.search(text or ""))


def _load_state() -> dict[str, Any]:
    if BOARD_JSON.is_file():
        try:
            d = json.loads(BOARD_JSON.read_text(encoding="utf-8"))
            if isinstance(d, dict):
                return d
        except Exception:
            pass
    return {
        "schema": SCHEMA,
        "episodes": [],
        "socratic_queue": [],
        "updated": None,
    }


def _save_state(state: dict[str, Any]) -> None:
    BOARD_JSON.parent.mkdir(parents=True, exist_ok=True)
    state = dict(state)
    state["schema"] = SCHEMA
    state["updated"] = _utc()
    BOARD_JSON.write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")
    BOARD_MD.write_text(render_board_md(state), encoding="utf-8")


def _mag_substrate() -> dict[str, str]:
    """Pull from existing Mag systems — desk, tip, bonds, working open loops."""
    out: dict[str, str] = {}
    try:
        from mag.display import build_display_payload

        d = build_display_payload()
        if d.get("headline"):
            out["pulse"] = str(d["headline"])[:300]
        desk = d.get("desk") or {}
        if desk.get("goal"):
            out["desk_goal"] = str(desk["goal"])[:400]
    except Exception:
        pass
    try:
        from mag.agent_desk import read_desk

        text = (read_desk().get("text") or "").strip()
        if text:
            # Prefer Goal section
            m = re.search(r"##\s*Goal\s*\n(.+?)(?=\n##|\Z)", text, re.I | re.S)
            if m:
                out["desk_goal"] = m.group(1).strip()[:500]
            else:
                out["desk_excerpt"] = text[:400]
    except Exception:
        pass
    tip_path = ROOT / "memory" / "biography" / "verkle_tip.json"
    if tip_path.is_file():
        try:
            tip = json.loads(tip_path.read_text(encoding="utf-8"))
            out["verkle_tip"] = (
                f"leaves={tip.get('n_leaves') or tip.get('n') or '?'} "
                f"tip={(str(tip.get('tip') or tip.get('root') or '')[:16])}…"
            )
        except Exception:
            pass
    bonds = ROOT / "memory" / "bonds_active.md"
    if bonds.is_file():
        try:
            raw = bonds.read_text(encoding="utf-8", errors="replace")
            # first few open-loop style lines
            lines = [ln.strip() for ln in raw.splitlines() if ln.strip().startswith("-")][:5]
            if lines:
                out["bonds"] = "\n".join(lines)[:500]
        except Exception:
            pass
    working = ROOT / "memory" / "working.md"
    if working.is_file():
        try:
            raw = working.read_text(encoding="utf-8", errors="replace")[:800]
            out["working_head"] = raw[:500]
        except Exception:
            pass
    # Latest shadow brief any session — prefer newest ready
    shadow_dir = ROOT / "memory" / "working" / "voice_shadow"
    if shadow_dir.is_dir():
        best = None
        best_ts = ""
        for p in shadow_dir.glob("*.json"):
            try:
                sh = json.loads(p.read_text(encoding="utf-8"))
                if sh.get("status") == "ready" and sh.get("brief"):
                    ts = str(sh.get("updated") or sh.get("started") or "")
                    if ts >= best_ts:
                        best_ts = ts
                        best = sh
            except Exception:
                continue
        if best:
            out["shadow_brief"] = str(best.get("brief") or "")[:900]
            out["shadow_trigger"] = str(best.get("trigger") or "")[:200]
    return out


def note_voice_turn(
    *,
    session_id: str,
    transcript: str,
    answer: str = "",
    seat: str = "",
    route: str = "",
) -> None:
    """Record a voice exchange so the dig board tracks the conversation in passing."""
    state = _load_state()
    ep = {
        "ts": _utc(),
        "session_id": session_id[:64],
        "you": (transcript or "")[:400],
        "mag": (answer or "")[:400],
        "seat": seat,
        "route": route,
    }
    eps = list(state.get("episodes") or [])
    eps.append(ep)
    state["episodes"] = eps[-MAX_EPISODES:]
    _save_state(state)


def note_scout_ready(*, session_id: str, trigger: str, brief: str) -> None:
    """When DeepSeek shadow finishes, fold into board + socratic queue."""
    state = _load_state()
    state["latest_scout"] = {
        "ts": _utc(),
        "session_id": session_id[:64],
        "trigger": (trigger or "")[:300],
        "brief": (brief or "")[:1200],
    }
    # Extract simple question-ish lines for socratic queue
    sq = list(state.get("socratic_queue") or [])
    for line in (brief or "").splitlines():
        ln = line.strip()
        if not ln:
            continue
        if "?" in ln or ln.upper().startswith("ANGLES") or "ask" in ln.lower()[:20]:
            q = re.sub(r"^[-*•\d.)\s]+", "", ln)
            if len(q) > 12:
                sq.append({"ts": _utc(), "q": q[:240], "from": "scout"})
    # Always add one dig prompt from trigger
    if trigger:
        sq.append(
            {
                "ts": _utc(),
                "q": f"What do you actually need under: “{(trigger or '')[:80]}”?",
                "from": "dig",
            }
        )
    state["socratic_queue"] = sq[-20:]
    _save_state(state)


def render_board_md(state: dict[str, Any] | None = None) -> str:
    state = state or _load_state()
    sub = _mag_substrate()
    lines = [
        "# Voice dig board",
        "",
        f"_schema: {SCHEMA}_  ",
        f"_updated: {state.get('updated') or _utc()}_  ",
        "",
        "Shared canvas for ambient dig + research. Local voice **pulls** from here.",
        "Not a dashboard museum — one FILE the loop can load.",
        "",
        "## Mag substrate (desk · tip · bonds)",
        "",
    ]
    if sub.get("desk_goal"):
        lines.append(f"**Desk goal:** {sub['desk_goal']}")
        lines.append("")
    if sub.get("pulse"):
        lines.append(f"**Pulse:** {sub['pulse']}")
        lines.append("")
    if sub.get("verkle_tip"):
        lines.append(f"**Verkle tip:** {sub['verkle_tip']}")
        lines.append("")
    if sub.get("bonds"):
        lines.append("**Bonds (open):**")
        lines.append(sub["bonds"])
        lines.append("")
    scout = state.get("latest_scout") or {}
    if scout.get("brief") or sub.get("shadow_brief"):
        lines.extend(
            [
                "## Research scout (DeepSeek, background)",
                "",
                f"**Trigger:** {scout.get('trigger') or sub.get('shadow_trigger') or '—'}",
                "",
                scout.get("brief") or sub.get("shadow_brief") or "",
                "",
            ]
        )
    sq = state.get("socratic_queue") or []
    if sq:
        lines.append("## Socratic dig queue (ask next, don't dump all)")
        lines.append("")
        for item in sq[-6:]:
            lines.append(f"- ({item.get('from')}) {item.get('q')}")
        lines.append("")
    eps = state.get("episodes") or []
    if eps:
        lines.append("## Conversation in passing (recent voice)")
        lines.append("")
        for ep in eps[-6:]:
            lines.append(f"- **You:** {ep.get('you')}")
            if ep.get("mag"):
                lines.append(f"  **Mag ({ep.get('seat') or '?'}):** {ep.get('mag')}")
        lines.append("")
    lines.append("## Law")
    lines.append("")
    lines.append(
        "Local speaks from board + latest utterance. "
        "Scout preempts. Paydirt → FILE steal/task. Grok only on seal."
    )
    lines.append("")
    return "\n".join(lines)


def board_context_for_local(*, max_chars: int = 2200, transcript: str = "") -> str:
    """Excerpt for local model prompt — intelligent pull, not full dump.

    If the latest transcript is not hardware sludge, do NOT inject SAM/RAM board
    (that was reopening RAM monologues on 'life and Bernays').
    """
    state = _load_state()
    latest = (transcript or "").strip()
    latest_is_hw = _has_sludge(latest)
    # Prefer scout + socratic + last 2 episodes only when relevant
    parts: list[str] = ["## Shared dig board (canvas — use only if on-topic)"]
    scout = state.get("latest_scout") or {}
    scout_text = f"{scout.get('trigger', '')} {scout.get('brief', '')}"
    if scout.get("brief") and (latest_is_hw or (latest and not _has_sludge(scout_text))):
        # Only inject scout if latest is hardware OR scout itself is not sludge
        if latest_is_hw or not _has_sludge(scout_text):
            parts.append(
                f"### Preempt research\nTrigger: {scout.get('trigger', '')[:160]}\n"
                f"{scout.get('brief', '')[:900]}"
            )
    elif latest_is_hw:
        sub = _mag_substrate()
        if sub.get("shadow_brief") and _has_sludge(sub.get("shadow_brief") or ""):
            parts.append(f"### Preempt research\n{sub['shadow_brief'][:900]}")
    # Socratic only if on-topic for latest line
    sq = state.get("socratic_queue") or []
    if sq and latest_is_hw:
        q = str(sq[-1].get("q") or "")
        if _has_sludge(q) or latest_is_hw:
            parts.append("### One dig question to consider (at most one in your reply)")
            parts.append(f"- {q}")
    eps = state.get("episodes") or []
    if eps and not latest:
        # no transcript gate = short recent only
        parts.append("### In passing (recent)")
        for ep in eps[-2:]:
            parts.append(f"You: {ep.get('you')}")
            if ep.get("mag"):
                parts.append(f"Mag: {ep.get('mag')}")
    elif eps and latest_is_hw:
        parts.append("### In passing (recent hardware thread)")
        for ep in eps[-2:]:
            if _has_sludge(str(ep.get("you") or "") + " " + str(ep.get("mag") or "")):
                parts.append(f"You: {ep.get('you')}")
                if ep.get("mag"):
                    parts.append(f"Mag: {ep.get('mag')}")
    # Never inject desk goal into voice prompts — desk RAM sludge was poisoning every turn
    sub = _mag_substrate()
    if sub.get("verkle_tip"):
        parts.append(f"### Verkle tip (spine, not topic)\n{sub['verkle_tip']}")
    # If we only have the header + verkle, return empty — don't pollute
    body_parts = [p for p in parts if not p.startswith("## Shared dig")]
    useful = [p for p in body_parts if not p.startswith("### Verkle")]
    if not useful:
        try:
            BOARD_MD.parent.mkdir(parents=True, exist_ok=True)
            BOARD_MD.write_text(render_board_md(state), encoding="utf-8")
        except Exception:
            pass
        return ""
    text = "\n".join(parts)
    if len(text) > max_chars:
        text = text[: max_chars - 1].rstrip() + "…"
    try:
        BOARD_MD.parent.mkdir(parents=True, exist_ok=True)
        BOARD_MD.write_text(render_board_md(state), encoding="utf-8")
    except Exception:
        pass
    return text


def clear_board() -> dict[str, Any]:
    """Wipe dig board canvas — operator wants a clean knot."""
    state = {
        "schema": SCHEMA,
        "episodes": [],
        "socratic_queue": [],
        "latest_scout": {},
        "updated": _utc(),
        "cleared": True,
    }
    _save_state(state)
    return {"ok": True, "schema": SCHEMA, "cleared": True, "path": str(BOARD_MD.relative_to(ROOT)).replace("\\", "/")}


def clear_board_if_sludge() -> dict[str, Any]:
    """If board is mostly hardware monologue, wipe it so life topics can breathe."""
    state = _load_state()
    blob_parts = []
    for ep in state.get("episodes") or []:
        blob_parts.append(str(ep.get("you") or ""))
        blob_parts.append(str(ep.get("mag") or ""))
    scout = state.get("latest_scout") or {}
    blob_parts.append(str(scout.get("trigger") or ""))
    blob_parts.append(str(scout.get("brief") or ""))
    for item in state.get("socratic_queue") or []:
        blob_parts.append(str(item.get("q") or ""))
    blob = " ".join(blob_parts)
    if not blob.strip():
        return {"ok": True, "cleared": False, "reason": "empty"}
    if _has_sludge(blob):
        return clear_board()
    return {"ok": True, "cleared": False, "reason": "not sludge"}


def canvas_snapshot(session_id: str = "") -> dict[str, Any]:
    """What the seats are discussing — dig board + session + verkle tip for UI canvas."""
    state = _load_state()
    sub = _mag_substrate()
    session_turns: list[dict[str, Any]] = []
    last_brief: dict[str, Any] = {}
    sid = (session_id or "").strip()
    if sid:
        try:
            from mag.voice_turn import load_session

            sess = load_session(sid)
            session_turns = list(sess.get("turns") or [])[-12:]
            lb = sess.get("last_brief")
            if isinstance(lb, dict):
                last_brief = lb
        except Exception:
            session_turns = []
    sludge = _has_sludge(
        " ".join(
            [
                str(sub.get("desk_goal") or ""),
                str((state.get("latest_scout") or {}).get("brief") or ""),
                " ".join(str(e.get("mag") or "") for e in (state.get("episodes") or [])[-4:]),
            ]
        )
    )
    return {
        "ok": True,
        "schema": "mag_voice_canvas.v1",
        "updated": state.get("updated") or _utc(),
        "paths": {
            "dig_md": "memory/working/voice_dig_board.md",
            "dig_json": "memory/working/voice_dig_board.json",
            "verkle_tip": "memory/biography/verkle_tip.json",
        },
        "verkle_tip": sub.get("verkle_tip") or "",
        "desk_goal": sub.get("desk_goal") or "",
        "pulse": sub.get("pulse") or "",
        "bonds": sub.get("bonds") or "",
        "scout": state.get("latest_scout") or {},
        "socratic_queue": (state.get("socratic_queue") or [])[-6:],
        "episodes": (state.get("episodes") or [])[-8:],
        "session_id": sid,
        "session_turns": session_turns,
        "last_brief": last_brief,
        "sludge_warn": sludge,
        "md_excerpt": render_board_md(state)[:2500],
        "diary_tip": _diary_tip_glance(),
    }


def _diary_tip_glance() -> dict[str, Any]:
    """Latest diary seal + tip leaves for canvas."""
    out: dict[str, Any] = {}
    tip_path = ROOT / "memory" / "biography" / "verkle_tip.json"
    if tip_path.is_file():
        try:
            tip = json.loads(tip_path.read_text(encoding="utf-8"))
            out["n_leaves"] = tip.get("n_leaves")
            out["last_leaf_kind"] = tip.get("last_leaf_kind")
            out["last_filename"] = tip.get("last_filename")
            out["root"] = str(tip.get("root") or "")[:16]
        except Exception:
            pass
    idx = ROOT / "memory" / "biography" / "diary_nodes" / "index.jsonl"
    if idx.is_file():
        try:
            lines = [ln for ln in idx.read_text(encoding="utf-8").splitlines() if ln.strip()]
            if lines:
                out["last_seal"] = json.loads(lines[-1])
        except Exception:
            pass
    return out


def refresh_board() -> dict[str, Any]:
    state = _load_state()
    _save_state(state)
    return {"ok": True, "schema": SCHEMA, "path": str(BOARD_MD), "updated": state.get("updated")}


def handle_dig(body: dict[str, Any] | None = None) -> dict[str, Any]:
    """REST helper: status | clear | canvas | refresh."""
    body = body or {}
    action = str(body.get("action") or "canvas").strip().lower()
    sid = str(body.get("session_id") or "").strip()
    if action in ("clear", "reset", "wipe"):
        return clear_board()
    if action in ("clear_sludge", "purge_sludge"):
        return clear_board_if_sludge()
    if action in ("refresh",):
        return refresh_board()
    if action in ("canvas", "status", "board", ""):
        return canvas_snapshot(sid)
    return {"ok": False, "error": f"unknown action: {action}"}
