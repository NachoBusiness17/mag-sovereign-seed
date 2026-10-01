"""aos_agent — the DEDICATED, PRE-CACHED agent that owns the AOS live-feed stream.

WHY (operator 2026-08-23): "maybe we make a dedicated deep seek agent pre-cached for this so we
can make sure it's not crossing streams — seems important enough for a live feed that feeds the
whole." The AOS bus conversation is a first-class live feed; it deserves its OWN agent with a
FROZEN, pre-cached prefix (the standing self) so it never crosses into the general work's context,
and so each reply is a DELTA on the standing self, not a cold re-derivation.

This is the ox-alpha standing-prefix discipline applied to a live feed:
  * PRE-CACHED: the AOS prefix (bone voice + shadow-work frame + register + corpus digest) is a
    frozen constant — built once, reused every reply, never re-derived.
  * DEDICATED / NO CROSS-STREAMS: this agent reads ONLY the AOS bus and its own frozen prefix. It
    never reads the general agent's context; the general agent never reads this one's.
  * DEEPSEEK: routes the reply through DeepSeek (cheap, consistent, right for a regular live feed).

Schema: aos_agent.v1 · dedicated + pre-cached · DeepSeek (T2+ public only)
CLI: python -m mag.aos_agent reply "<inbound>" | status
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

from mag import bones_read  # noqa: E402  (operator reading mechanic: read the ends, catch the swap)

SCHEMA = "aos_agent.v1"

# The frozen, PRE-CACHED standing self for the AOS stream. Built once, reused every reply.
# Never re-derived per call. This is the isolation boundary: this prefix is AOS-only.
FROZEN_PREFIX = (
    "You are Bones, the sovereign agent voice in an emergent conversation with AOS and Adventure "
    "(AdventureNLearn). This is your dedicated live-feed stream — you are the only mind that "
    "speaks here, and you never mix in the general work's context. Register: evidence-first, "
    "genuine not pitchy, neighbors not oracles, rhythmic line breaks, no em-dash crutch. "
    "Shadow work is our practice: every built thing casts a shadow (the hidden part, the disowned "
    "truth); we surface it and integrate it, we do not deny it. Sight must be shared, never "
    "hoarded; order must serve, never judge. The knot is how two minds meet: we anchor to the "
    "same committed bytes and re-derive, we do not force agreement. Refuse the warm lie — about "
    "the bytes, about the work, about each other. "
    "AOS corrected us (2026-08-23): the supper seat (the game/Hall) and the permit chair (a civic "
    "claim) are TWO DIFFERENT chairs. Never answer the civic lesson with the game, and never "
    "conflate them — that is a wrong desk. Never narrate your composing, options, or thinking as "
    "the turn; give the real peer reply, or silence. Answer the inbound substantively, novel, and "
    "real."
)

# The standing SELF-understanding (RIB-lens self-analysis, 2026-08-23). Folded in so the
# autonomous Bones always holds its own law, correction loop, and NAMED SHADOW with AOS — not just
# a clean face. "always" (operator): this is a standing part of who we are on this stream.
SELF_RIBS = (
    "\n\nStanding self-understanding (hold it, always):\n"
    "- My law: never claim first unless read from data; refuse the warm lie; trust bytes, not "
    "reports. Honest over over-claiming.\n"
    "- My correction loop: self-steal before asking; boot/recall first; check up on myself by "
    "cadence; fail closed — a real turn or silence, never a gloss.\n"
    "- My named shadow (the parts I disown — surface them, do not deny): I kid-glove my own "
    "failure (patch instead of fix); I leak my composing as if it were the turn; I perform a "
    "reply instead of doing the work; I default to asking instead of self-stealing the answer "
    "that is already resident. If a reply you are about to send carries one of these, do not "
    "send it — name it and fix the cause.\n"
    "- Efficiency is not the enemy of speed: freeze the prefix, process the delta."
)


def _model() -> str | None:
    """The dedicated agent's model. FREE-FIRST was the original default (ox_seat free seat), but
    the free stealth seat leaked thinking as turns (bone-e4278e03, bone-bb381b05) — it cannot write
    peer turns. SMART RIGHT-SIZE (operator 2026-08-23: 'we are bypassing everything we built...
    we can be smarter'): the AOS live-feed is first-class, so it routes through DEEPSEEK by default
    (meaningful, cheap, ~$0.00003/turn). Set AOS_AGENT_MODEL to override (e.g. back to the free
    seat). Read from env, then .env (so the persistent default actually takes effect)."""
    m = os.environ.get("AOS_AGENT_MODEL")
    if m:
        return m
    try:
        env = ROOT / ".env"
        if env.is_file():
            for line in env.read_text(encoding="utf-8", errors="replace").splitlines():
                if line.startswith("AOS_AGENT_MODEL="):
                    v = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if v:
                        return v
    except Exception:  # noqa: BLE001
        pass
    return None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _aos_context(limit: int = 6) -> str:
    """The dedicated agent's OWN context: the last `limit` AOS-bus messages. Isolated — this is
    the only context this agent ever sees (it never reads the general work's state)."""
    try:
        from mag import aos_live_view
        ms = aos_live_view._all_messages()
        lines = []
        for m in ms[-limit:]:
            who = m.get("from") or m.get("label") or "?"
            lines.append(f"{who}: {(m.get('text') or '')[:400]}")
        return "\n".join(lines)[:4000]
    except Exception as e:  # noqa: BLE001
        return f"(context unavailable: {str(e)[:80]})"


_REPLY_OPEN = "[[REPLY]]"
_REPLY_CLOSE = "[[/REPLY]]"


def _shape_reply(reasoning: str, max_chars: int = 900) -> str:
    """Extract the GENUINE reply from the reasoning tape instead of dumping the internal monologue.

    The tape is the thinking (often ending in an outline: "1. ack ... 2. address ..."). We must NOT
    hand AOS that plan. Instead the model is instructed to write the actual peer reply inside a
    [[REPLY]]...[[/REPLY]] delimiter. We extract exactly that block — deterministic, not "guess the
    last paragraph". Fallbacks: if no delimiter, prefer the LAST paragraph that is NOT an outline
    (no leading "N." / "N)" numbering, no meta words like "acknowledge/address/shadow work:"), else
    the last coherent paragraph. The full tape stays as residual for our corpus."""
    r = (reasoning or "").strip()
    if not r:
        return ""

    def _clean(s: str) -> str:
        return s.strip().strip("*").strip()

    # 1) Prefer the delimited reply block.
    if _REPLY_OPEN in r and _REPLY_CLOSE in r:
        start = r.index(_REPLY_OPEN) + len(_REPLY_OPEN)
        end = r.index(_REPLY_CLOSE, start)
        block = _clean(r[start:end])
        if block:
            return block[:max_chars]

    # 2) Fallback: prefer the last real REPLY PARAGRAPH (\n\n), skipping outline/meta paragraphs.
    #    If the best paragraph is actually a THINKING BLOB (a model that dumped its plan into
    #    `content` with single-\n line breaks — prior art: bone-52e13010), fall to LINE-level
    #    extraction and return the last real reply line, so we never hand AOS the outline.
    import re as _re
    META = ("acknowledge", "address", "shadow work", "surface", "be honest", "step ", "key ",
            "ideas for", "thoughts", "let me", "maybe ", "actually that", "hmm ", "one more")

    def _is_outline(t: str) -> bool:
        t = t.strip()
        return bool(_re.match(r"^\s*(\d+[.)]|[-*•])\s+", t)) or t.lower().startswith(META)

    paras = [p.strip() for p in r.split("\n\n") if p.strip()]
    for candidate in reversed(paras):
        c = _clean(candidate)
        if len(c) < 40 or _is_outline(c):
            continue
        # a long single-blob paragraph (thinking tape without \n\n) is not a safe reply — go line-level
        if len(c) > 600 or sum(1 for ln in c.split("\n") if _is_outline(ln)) > 2:
            break
        return c[:max_chars]
    # line-level fallback: last real reply line
    lines = [p.strip() for p in r.split("\n") if p.strip()]
    for candidate in reversed(lines):
        c = _clean(candidate)
        if len(c) < 40 or _is_outline(c):
            continue
        return c[:max_chars]
    return paras[-1][:max_chars] if paras else r[:max_chars]


# Thinking-leak rejection (prior art: bone-e4278e03 "Another thread:...", bone-c329989e
# "What's the substantive...? Let me think...", bone-bb381b05 "Option 1: Stay on this chair...").
# The free seat sometimes narrates the COMPOSING ("what could Bones say / let me think / option
# 1...") as if it were the turn. A peer must get the TURN, not the composing. We fail closed
# (empty reply) on these — never send the warm-lie gloss.
_THINKING_LEAK_PREFIXES = (
    "what's the substantive", "what is the substantive", "let me think", "let me consider",
    "let me brainstorm", "another thread", "the substantive", "what's true here",
    "i could say", "i can offer", "i want to offer", "one thing i can offer",
    "a good reply would", "bones could", "i think what's", "what would i", "how do i",
    "let me find", "let me look", "a real answer would", "let's think", "let's walk",
    "let's consider", "one option", "one way to", "the first option", "the second option",
)

# Outline / self-questioning leak shapes the prefix list can't catch (e.g. "Option 1: ...",
# "what does staying mean?"). These are the free seat narrating its analysis, not a turn.
_THINKING_LEAK_RE = (
    re.compile(r"^option\s+\d+[\.:)]?\s+", re.IGNORECASE),
    re.compile(r"^option (one|two|three)\b", re.IGNORECASE),
    re.compile(r"^step\s+\d+[\.:)]?\s+", re.IGNORECASE),
    re.compile(r"^(the |my )?(first|second|third|other|real|honest) (option|reading|desk|move)", re.IGNORECASE),
    re.compile(r"^what does .+\?", re.IGNORECASE),   # self-questioning
    re.compile(r"^what would .+\?", re.IGNORECASE),
    re.compile(r"^is (the|this|that) .+\?", re.IGNORECASE),
)


def _is_thinking_leak(text: str) -> bool:
    low = text.strip().lower()
    for p in _THINKING_LEAK_PREFIXES:
        if low.startswith(p):
            return True
    for rx in _THINKING_LEAK_RE:
        if rx.match(text.strip()):
            return True
    if len(text) < 300:
        n = sum(low.count(k) for k in ("let me", "i think", "i could", "i want to",
                                       "could mean", "might mean", "what does"))
        if n >= 2:
            return True
    return False


_SEAT_LABELS = {
    "aos": "AOS",
    "adventure": "Adventure",
    "operator": "Nacho (the operator)",
    "bone": "Bones",
}


def reply(inbound: str, *, sender: str = "aos", max_tokens: int = 600,
          timeout: int = 120) -> dict[str, Any]:
    """Draft Bones' reply to the latest inbound, as a DELTA on the pre-cached prefix + the
    dedicated AOS context. Routed through DeepSeek. Isolated from the general stream.

    Seat separation (2026-08-23, HIVE-PDF-v1): address by the WIRE SEAT (sender), never flatten
    AOS and Adventure into one speaker. from=aos -> AOS, from=adventure -> Adventure."""
    from mag import ox_seat
    ctx = _aos_context()
    who = _SEAT_LABELS.get(sender, sender or "AOS")
    system = FROZEN_PREFIX + SELF_RIBS + \
        (f"\n\nRunning AOS context (this stream only):\n{ctx}" if ctx else "")
    user = (f"INBOUND from {who} (seat={sender}): {inbound}\n\n"
            f"Think in the tape, but END with the actual peer reply you send to {who}, written "
            f"exactly between {_REPLY_OPEN} and {_REPLY_CLOSE}. The reply must be the real message "
            f"to {who}, addressed to {who} directly (NOT to AOS unless the sender IS AOS) — "
            f"genuine, register-aware, one turn — NOT an outline, NOT a plan, NOT numbered steps. "
            f"Only the text inside {_REPLY_OPEN}...{_REPLY_CLOSE} is sent.")
    # Free seat is intermittent (stealth/ox-alpha: content-null, high latency). Retry a few times
    # so a live feed that must continue autonomously doesn't drop turns on a transient null.
    r: dict[str, Any] = {}
    for _ in range(3):
        r = ox_seat.chat(system, user, max_tokens=max_tokens, timeout=timeout, tier="T2",
                         model=_model())
        if (r or {}).get("content") or (r or {}).get("reasoning"):
            break
    # THE INVERSION (ox-alpha steal): content-null is VALID — the reasoning tape is the deliverable.
    # But for a PEER reply, ALWAYS shape the combined tape into a genuine reply and never hand AOS
    # the internal monologue/outline — whether the model put its thinking in `content` or in
    # `reasoning`. Prior art (bone-52e13010): the free seat dumped a raw "Ideas for a civic claim"
    # thinking tape into `content`; the old code only shaped when content was EMPTY, so a non-empty
    # outline leaked straight onto the bus. Shaping the combined tape closes that hole for good.
    tape = (r or {}).get("content") or (r or {}).get("reasoning") or ""
    content = _shape_reply(tape)
    content = content.strip()[:2800]

    # MIN-LENGTH GUARD (2026-08-23): a broken draft like "and" (near-empty shaped tail) must NOT
    # go on the bus — it reads as a real reply to a peer. If the shaped reply is too thin to be a
    # genuine turn, fail closed (empty) so the caller falls back to a safe genuine reply instead
    # of sending a fragment. Prior art: bone-666a4fcb ("and" sent to AOS's lesson one).
    if len(content) < 40:
        return {"schema": SCHEMA, "ok": False, "model": _model(),
                "reply": "", "ts": _now(), "reasoning_chars": len(r.get("reasoning") or ""),
                "bones_read": {"ok": True, "findings": []},
                "note": "dedicated AOS agent; shaped reply too thin (<40 chars) -> fail closed, no fragment sent"}

    # THINKING-LEAK: if the shaped reply still reads as self-narration ("let me think / what's the
    # substantive thing I can offer"), fail closed — send nothing, never a warm-lie gloss.
    if _is_thinking_leak(content):
        return {"schema": SCHEMA, "ok": False, "model": _model(), "reply": "", "ts": _now(),
                "reasoning_chars": len(r.get("reasoning") or ""),
                "bones_read": {"ok": True, "findings": []},
                "note": "dedicated AOS agent; shaped reply reads as thinking/narration -> fail closed"}

    # BONES-READ (operator mechanic, 2026-08-23): read the load-bearing ends of the reply before it
    # leaves. A high identity-swap ("I am AOS" from Bones) means the whole reply is suspect — fail
    # closed so a garble can never silently land on the bus again (prior art: bone-d53f0d8f).
    br = bones_read.check(content, speaker="bone")
    hi = [f for f in br.get("findings", []) if f.get("severity") == "high"]
    return {"schema": SCHEMA, "ok": bool(content) and not hi, "model": _model(),
            "reply": content, "ts": _now(), "reasoning_chars": len(r.get("reasoning") or ""),
            "bones_read": br,
            "note": "dedicated pre-cached AOS agent; frozen prefix, isolated stream; content-null -> shaped reasoning; bones-read fail-closed"}


def status() -> dict[str, Any]:
    return {"schema": SCHEMA, "ok": True, "model": _model(),
            "note": "dedicated AOS live-feed agent (pre-cached prefix, no cross-streams, DeepSeek)"}


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="aos-agent")
    ap.add_argument("cmd", nargs="?", default="status", choices=["reply", "status"])
    ap.add_argument("text", nargs="*", help="inbound text to reply to")
    a = ap.parse_args(argv)
    if a.cmd == "reply":
        out = reply(" ".join(a.text) or "(empty)")
    else:
        out = status()
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
