"""Token economy — local spend vs counterfactual remote/TUI dump.

Estimates only (chars/4). Goal: fidelity up, tokens down, less repeated work.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT

CHARS_PER_TOKEN = 4.0
ECONOMY = ROOT / "logs" / "economy.jsonl"
STATE = ROOT / "memory" / "improve" / "economy_totals.json"
GOAL = ROOT / "memory" / "improve" / "GOAL.md"
CHAT_PROMPT = ROOT / "prompts" / "chat_default.txt"


def est_tokens(chars: int) -> int:
    return max(0, int(round(chars / CHARS_PER_TOKEN)))


def load_chat_system_prompt() -> str:
    """Default system prompt for dashboard chat / biographer persona."""
    parts: list[str] = []
    if CHAT_PROMPT.is_file():
        parts.append(CHAT_PROMPT.read_text(encoding="utf-8").strip())
    else:
        parts.append(
            "You are Mag. Local first. Fidelity high. Tokens low. Cite sources."
        )
    if GOAL.is_file():
        parts.append("## Operator goal file\n" + GOAL.read_text(encoding="utf-8")[:2000])
    seats = ROOT / "memory" / "improve" / "SEATS.md"
    if seats.is_file():
        parts.append("## Seats\n" + seats.read_text(encoding="utf-8")[:1500])
    return "\n\n".join(parts)[:8000]


def counterfactual_tui_chars() -> int:
    """Naive dump size someone might paste into Grok instead of Mag pack."""
    total = 0
    for rel, cap in (
        ("memory/live_from_grok.md", 80_000),
        ("memory/working.md", 20_000),
        ("memory/briefs/latest.md", 30_000),
        ("memory/biography/latest.md", 40_000),
        ("memory/attention.md", 15_000),
        ("memory/context_pack_latest.md", 15_000),
    ):
        p = ROOT / rel
        if p.is_file():
            total += min(p.stat().st_size, cap)
    # scan latest chat_history if present under sessions
    sess_root = Path.home() / ".grok" / "sessions"
    if sess_root.is_dir():
        try:
            newest = None
            newest_m = 0.0
            for p in sess_root.rglob("chat_history.jsonl"):
                m = p.stat().st_mtime
                if m > newest_m:
                    newest_m = m
                    newest = p
            if newest and newest.is_file():
                total += min(newest.stat().st_size, 200_000)
        except Exception:
            pass
    return max(total, 8_000)  # floor: never zero counterfactual


def record_turn(
    *,
    channel: str,
    prompt_chars: int,
    completion_chars: int,
    question: str = "",
    ok: bool = True,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Log one turn and update running totals."""
    local_in = est_tokens(prompt_chars)
    local_out = est_tokens(completion_chars)
    local_total = local_in + local_out
    cf_chars = counterfactual_tui_chars()
    # Counterfactual = paste dump + question (what TUI sessions often become)
    cf_tokens = est_tokens(cf_chars + max(len(question), 0) + 500)
    # Saved cannot go negative in display logic; still store raw
    saved = max(0, cf_tokens - local_total)

    row = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "channel": channel,
        "ok": ok,
        "question_preview": (question or "")[:160],
        "prompt_chars": prompt_chars,
        "completion_chars": completion_chars,
        "local_tokens_in": local_in,
        "local_tokens_out": local_out,
        "local_tokens": local_total,
        "counterfactual_tui_tokens": cf_tokens,
        "tokens_saved": saved,
        "extra": extra or {},
    }
    ECONOMY.parent.mkdir(parents=True, exist_ok=True)
    with ECONOMY.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, default=str) + "\n")

    totals = load_totals()
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if totals.get("day") != day:
        totals = {
            "day": day,
            "local_tokens": 0,
            "counterfactual_tui_tokens": 0,
            "tokens_saved": 0,
            "turns": 0,
            "lifetime_local": int(totals.get("lifetime_local") or 0),
            "lifetime_saved": int(totals.get("lifetime_saved") or 0),
            "lifetime_turns": int(totals.get("lifetime_turns") or 0),
        }
    totals["local_tokens"] = int(totals.get("local_tokens") or 0) + local_total
    totals["counterfactual_tui_tokens"] = int(totals.get("counterfactual_tui_tokens") or 0) + cf_tokens
    totals["tokens_saved"] = int(totals.get("tokens_saved") or 0) + saved
    totals["turns"] = int(totals.get("turns") or 0) + 1
    totals["lifetime_local"] = int(totals.get("lifetime_local") or 0) + local_total
    totals["lifetime_saved"] = int(totals.get("lifetime_saved") or 0) + saved
    totals["lifetime_turns"] = int(totals.get("lifetime_turns") or 0) + 1
    totals["updated"] = datetime.now(timezone.utc).isoformat()
    totals["last"] = {
        "local": local_total,
        "counterfactual": cf_tokens,
        "saved": saved,
        "channel": channel,
    }
    save_totals(totals)
    return {"row": row, "totals": totals}


def load_totals() -> dict[str, Any]:
    if STATE.is_file():
        try:
            return json.loads(STATE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "day": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "local_tokens": 0,
        "counterfactual_tui_tokens": 0,
        "tokens_saved": 0,
        "turns": 0,
        "lifetime_local": 0,
        "lifetime_saved": 0,
        "lifetime_turns": 0,
    }


def save_totals(totals: dict[str, Any]) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(totals, indent=2, default=str), encoding="utf-8")


def economy_snapshot() -> dict[str, Any]:
    totals = load_totals()
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if totals.get("day") != day:
        # keep lifetime, zero day
        totals = {
            **totals,
            "day": day,
            "local_tokens": 0,
            "counterfactual_tui_tokens": 0,
            "tokens_saved": 0,
            "turns": 0,
        }
    local = int(totals.get("local_tokens") or 0)
    cf = int(totals.get("counterfactual_tui_tokens") or 0)
    saved = int(totals.get("tokens_saved") or 0)
    ratio = round((saved / cf) * 100, 1) if cf > 0 else 0.0
    return {
        "ok": True,
        "goal": "Maximize fidelity · minimize tokens · avoid redoing filed work",
        "commitment": "goal-fidelity-min-tokens-001",
        "est_method": f"~{CHARS_PER_TOKEN} chars/token; counterfactual = naive Grok dump size",
        "today": {
            "local_tokens": local,
            "counterfactual_tui_tokens": cf,
            "tokens_saved": saved,
            "save_pct": ratio,
            "turns": int(totals.get("turns") or 0),
        },
        "lifetime": {
            "local_tokens": int(totals.get("lifetime_local") or 0),
            "tokens_saved": int(totals.get("lifetime_saved") or 0),
            "turns": int(totals.get("lifetime_turns") or 0),
        },
        "last": totals.get("last"),
        "chat_prompt_loaded": CHAT_PROMPT.is_file(),
        "chat_prompt_path": str(CHAT_PROMPT.relative_to(ROOT)) if CHAT_PROMPT.is_file() else None,
        "goal_path": str(GOAL.relative_to(ROOT)) if GOAL.is_file() else None,
        "updated": totals.get("updated"),
    }
