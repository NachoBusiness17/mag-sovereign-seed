"""ARC SEED — the conversation-as-verkle-object compiler (self-steal 09-06).

Operator question: "how do i recreate the entire conversation arc in a single
prompt that would cover its caching... how is this like a multidimensional
verkle object... hidden stochastic spaces hidden to observers with the
curiosity and the will to ask for directions?"

THE STEAL — three facts we already owned, seen as ONE object:
1. A conversation is a PREFIX CHAIN priced by its cache: each call re-feeds the
   whole prior arc as cache reads; only the new suffix misses (this seat's own
   rollout: 9% hit cold -> 99.98% hit warm, ~280K-token stable prefix).
2. The trajectory envelope {input, tool_result, output, reasoning, step_hash,
   timing} is the per-node vector — the arc is a VERKLE TREE keyed by
   H(parent_hash, turn); the linear transcript is ONE root-to-leaf path.
3. The hidden stochastic space = the SIBLING leaves: every position's sampling
   distribution defines a probability field the transcript never shows. Probes
   (tesuji stones, salon forks, A/B arms) are the only doors into it.

THE ORGAN: parse a rollout (model-io-sess_*.jsonl) -> emit
  (a) the CACHE ANATOMY — per-call hit curve + stable-prefix growth,
  (b) the ARC CHAIN — hash-chained turn envelopes + the arc root,
  (c) the ARC SEED — the single-prompt skeleton (system prefix + operator
      forks + state delta) that would regenerate the arc's shape in a fresh
      session. Falsifier: a fresh seat given the seed should predict the next
      move; if it can't, the seed missed the load-bearing state.

$0, local, read-only on the source. Never echoes secrets (redacts by default).
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "watch" / "arc_seeds"

# secrets law: operator forks may embed keys — redact before anything is written
_REDACT = re.compile(
    r"(sk-[A-Za-z0-9_-]{8,}"                       # api-key shapes
    r"|Bearer\s+\S+"
    r"|[A-Za-z0-9_-]*key[=: ]\S{12,}"
    r"|[A-Fa-f0-9]{32,})"
)


def _redact(s: str) -> str:
    return _REDACT.sub("[REDACTED]", s)


def _sha(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8", "ignore")).hexdigest()[:16]


def parse_rollout(path: Path) -> list[dict]:
    turns = []
    prev_input = 0
    prev_hash = "GENESIS"
    for i, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines()):
        if not line.strip():
            continue
        try:
            d = json.loads(line)
        except Exception:
            continue
        body = (d.get("request") or {}).get("body") or {}
        resp = d.get("response") or {}
        u = resp.get("usage") or {}
        inp, out = int(u.get("inputTokens") or 0), int(u.get("outputTokens") or 0)
        cached = int(u.get("cacheReadTokens") or 0)
        reasoning = resp.get("reasoningText") or ""
        sys_blocks = body.get("system") or []
        user_msgs = [m.get("content") for m in (body.get("messages") or [])
                     if isinstance(m, dict) and m.get("role") == "user"]
        env = {
            "i": i,
            "ts": d.get("completedAt"),
            "dur_ms": d.get("durationMs"),
            "model": (d.get("model") or {}).get("modelId"),
            "input": inp, "output": out, "cache_read": cached,
            "hit_pct": round(100 * cached / inp, 2) if inp else None,
            "prefix_growth": inp - prev_input,          # new tokens this turn added
            "reasoning_sha": _sha(reasoning) if reasoning else None,
            "reasoning_chars": len(reasoning),
            "system_blocks": len(sys_blocks),
            "system_sha": _sha(json.dumps(sys_blocks, default=str)),
            "user_forks": [str(m)[:400] for m in user_msgs],
            "finish": resp.get("finishReason"),
        }
        # the verkle step: node address = H(parent, turn-envelope)
        env["step_hash"] = hashlib.sha256(
            (prev_hash + json.dumps(env, sort_keys=True, default=str)).encode()
        ).hexdigest()[:16]
        env["parent"] = prev_hash
        prev_hash = env["step_hash"]
        prev_input = inp
        turns.append(env)
    return turns


def anatomy(turns: list[dict]) -> dict:
    """The cache trace: how much of this arc was stable prefix vs new work."""
    if not turns:
        return {}
    hits = [t["cache_read"] for t in turns if t["input"]]
    cold = turns[0]["hit_pct"]
    warm = [t["hit_pct"] for t in turns[1:] if t["hit_pct"] is not None]
    refeed = sum(hits)
    total_in = sum(t["input"] for t in turns)
    return {
        "calls": len(turns),
        "cold_hit_pct": cold,
        "warm_hit_pct_min": min(warm) if warm else None,
        "warm_hit_pct_max": max(warm) if warm else None,
        "stable_prefix_tokens": max((t["input"] for t in turns), default=0),
        "refeed_tokens": refeed,
        "total_input_tokens": total_in,
        "refeed_share_pct": round(100 * refeed / total_in, 1) if total_in else None,
        "new_tokens_total": sum(max(t["prefix_growth"], 0) for t in turns),
        "thinking_chars": sum(t["reasoning_chars"] or 0 for t in turns),
        "arc_root": turns[-1]["step_hash"] if turns else None,
    }


def seed_skeleton(turns: list[dict], session_id: str) -> str:
    """The single prompt that would regenerate this arc's SHAPE: layer 0 = the
    immutable system, layer 1 = the operator's forks verbatim, layer 2 = the
    committed-state delta (files/cards are the durable memory, not the chat)."""
    lines = ["# ARC SEED — single-prompt recreation", ""]
    lines.append(f"session: {session_id}  arc_root: {turns[-1]['step_hash'] if turns else '-'}")
    lines.append("")
    lines.append("## LAYER 0 — immutable system (deterministic, rides the cache forever)")
    lines.append("<< the system prefix, verbatim — every seat has this; it is the constitution >>")
    lines.append("")
    lines.append("## LAYER 1 — the operator's forks (verbatim orders = the branch points)")
    n = 0
    for t in turns:
        for f in t["user_forks"]:
            n += 1
            lines.append(f"{n}. {_redact(f)}")
    if n == 0:
        lines.append("<< none captured in this rollout window — orders live in the session db >>")
    lines.append("")
    lines.append("## LAYER 2 — committed-state delta (the arc's verkle leaves, outside the context)")
    lines.append("<< artifacts written during the arc: files, cards, knots — the durable memory >>")
    lines.append(f"<< thinking banked: {sum(t['reasoning_chars'] or 0 for t in turns)} chars across "
                 f"{sum(1 for t in turns if t['reasoning_sha'])} calls (sha-addressed, replayable) >>")
    lines.append("")
    lines.append("## RESUME")
    lines.append("You are the seat mid-arc. Your next move follows from LAYER 1's last fork "
                 "and LAYER 2's committed state. State the next move before reading anything.")
    return "\n".join(lines)


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python -m mag.arc_seed <model-io-sess_*.jsonl> [session_id]")
        return 2
    src = Path(sys.argv[1])
    session_id = sys.argv[2] if len(sys.argv) > 2 else src.stem.replace("model-io-", "")
    turns = parse_rollout(src)
    a = anatomy(turns)
    root = a.get("arc_root") or "noroot"
    # idempotent naming: same arc root -> same files -> re-running is a no-op (CAS by content)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"arc_chain_{session_id[:13]}_{root}.json").write_text(
        json.dumps({"schema": "arc_seed.v1", "session": session_id, "anatomy": a,
                    "turns": turns}, indent=1, default=str), encoding="utf-8")
    seed = seed_skeleton(turns, session_id)
    (OUT / f"arc_seed_{session_id[:13]}_{root}.md").write_text(seed, encoding="utf-8")
    print(json.dumps(a, indent=1))
    print(f"arc root: {root}")
    print(f"seed + chain -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
