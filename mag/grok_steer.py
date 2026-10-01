"""grok_steer — the DFHack overlay over a live grok session (2026-08-16).

The operator's training, made concrete: "as DFHack to Dwarf Fortress, you sit overtop" + "this is
memweave/lance tools i've been training you for exactly" + "you need to do this in real time and not
default to dumb tools and use our cache hit shit."

THE PROBLEM I was committing: manually reading the grok terminal and hand-typing steers. That is the
dumb-tool default — slow, terminal-bound, and it never gets cheaper. The right way is the OVERLAY:
  * I sit overtop the grok session (read its deep state).
  * When grok is about to PATCH (failover/retry/band-aid), I run its move through the CACHE-HIT
    escalation channel (escalate_cached — byte-stable maze prefix, ~$0.0036/M) to decide the steer.
  * I deliver the steer back into the session.

This module is the overlay's steering brain. It is DETERMINISTIC + $0 to decide whether a steer is
needed (the steer-first keyword gate); the cache-hit pro call only fires when a patch-move is
detected, and it rides the maze prefix so it stays cheap.

Schema: grok_steer.v1 · reuse: session_maze.escalate_cached (cache-hit), steer_router (rightsize),
grok_terminal (the session surface) — nothing invented.
"""
from __future__ import annotations

import json
import sys
from typing import Any

try:
    from config import ROOT
except Exception:
    from pathlib import Path as _P
    ROOT = _P(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCHEMA = "grok_steer.v1"

# ── PATCH-MOVE DETECTION (deterministic keyword gate — the steer-first law, $0) ──
# When grok's move contains these, it's likely reaching for a workaround instead of the root fix.
# NOTE (2026-08-16 RIB-debug): exact-phrase matching missed "remove THAT gate" (the proof caught a
# false-negative). So the gate is pattern-based: remove/drop/rip/delete + a guardrail noun, plus
# direct band-aid phrases. Word-boundary aware so "removing the gate" vs "gate is removed" both hit.
import re as _re
_PATCH_PATTERNS = [
    # remove/drop/rip out/delete/disable + guardrail noun (any article) — catches "remove that gate"
    _re.compile(r"\b(remove|drop|rip\s*out|delete|disable|nuke|strip|bypass)\b.{0,30}?\b(gate|cap|guard|guardrail|limit|check|quota|constraint|failover|retry)\b", _re.I),
    # detached destructive verb (verb AFTER the noun, or standalone) — catches "the limit is wrong, rip it out"
    _re.compile(r"\b(rip\s+it\s*out|rip\s+out|take\s+it\s*out|tear\s+it\s*out|tear\s+out|just\s+kill\s+it|get\s+rid\s+of\s+it)\b", _re.I),
    # direct band-aid phrasing
    _re.compile(r"\b(failover|fallback|workaround|band-aid|paper\s*over|degrade\s+gracefully|just\s+ignore|swallow)\b", _re.I),
    _re.compile(r"\btry\s*/\s*except\s+pass\b", _re.I),
]
ROOT_HINTS = (
    "root cause", "real constraint", "check live", "quota_state", "rightsize", "gate before",
    "name the constraint", "scope", "skip-and-queue", "read the live", "skip when spent",
)


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _detect_patch(move: str) -> dict[str, Any]:
    """Deterministic steer-first gate: is grok about to PATCH (needs a steer) or fix the root?"""
    low = (move or "").lower()
    patch_hits = [p.pattern for p in _PATCH_PATTERNS if p.search(low)]
    root_hits = [h for h in ROOT_HINTS if h in low]
    # Root naming wins: if grok is already naming the constraint/scope, it's doing it right.
    if root_hits:
        return {"patch": False, "patch_hits": [], "root_hits": root_hits,
                "verdict": "already_rooted"}
    if patch_hits:
        return {"patch": True, "patch_hits": patch_hits, "root_hits": [],
                "verdict": "patch_detected"}
    return {"patch": False, "patch_hits": [], "root_hits": [],
            "verdict": "no_patch_signal"}


def decide_steer(move: str, *, question: str = "Is grok about to patch or fix the root?", 
                 model: str = "deepseek-v4-pro", use_cache: bool = True) -> dict[str, Any]:
    """THE OVERLAY'S STEERING DECISION. Deterministic gate first ($0); only if a patch-move is
    detected does it escalate through the CACHE-HIT channel (escalate_cached) to craft the steer.
    """
    gate = _detect_patch(move)
    if not gate["patch"]:
        # already rooted or no patch signal — no steer, $0, no model call
        return {"ok": True, "schema": SCHEMA, "need_steer": False, "gate": gate,
                "steer": "", "cost": "deterministic $0 (no patch detected)"}
    # patch detected -> craft a grounded steer via the cache-hit escalation channel
    prompt = (
        f"A coding agent (grok) is working on a sovereign-agent codebase and is about to "
        f"PATCH instead of fixing the root. Its move:\n---\n{move[:2000]}\n---\n"
        f"Steer it: name the real constraint, check whether it's global or per-resource, and "
        f"prefer the root fix (rightsize/gate/route) over a band-aid. Return ONE concise steer "
        f"(2-3 sentences) the operator would give. Do not remove a guardrail — fix the check to "
        f"reflect reality."
    )
    try:
        from mag.session_maze import escalate_cached
        r = escalate_cached(prompt, model=model) if use_cache else \
            {"ok": False, "error": "cache channel unavailable"}
        steer = str(r.get("text") or "").strip()
        return {"ok": bool(steer), "schema": SCHEMA, "need_steer": True, "gate": gate,
                "steer": steer, "channel": "escalate_cached (cache-hit)" if use_cache else "direct",
                "model": model, "error": r.get("error") if not steer else None}
    except Exception as e:
        return {"ok": False, "schema": SCHEMA, "need_steer": True, "gate": gate,
                "steer": "", "error": str(e)[:160]}


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "contract": "decide_steer(move)->deterministic patch-gate then cache-hit escalation "
                        "to craft a steer; status()->this",
            "cost": "deterministic $0 unless a patch-move is detected (then escalate_cached "
                    "cache-hit ~$0.0036/M)",
            "reuse": "session_maze.escalate_cached, steer_router, grok_terminal",
            "role": "the DFHack overlay over a live grok session — sit overtop, read state, steer "
                    "through the cache-hit channel, not by hand"}


def main(argv: list[str] | None = None) -> int:
    import json as _json
    move = " ".join(argv) if argv else ""
    if not move:
        print(_json.dumps(status(), ensure_ascii=False, indent=2))
        return 0
    print(_json.dumps(decide_steer(move), ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
