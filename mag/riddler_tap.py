"""riddler_tap — tap frontier research models via coded language (riddler + memlang) for pennies.

OPERATOR (2026-08-12): "we can use coded language from a riddler or protocol to tap frontier
research models to role play or systems in order to provide their capability at scale for
fractions of a dollar."

THE MECHANISM (all ours, self-steal):
  * RIDDLER (semantic surrogate): private ask -> synthetic story; remote reasons in the story
    domain; local decodes; the mapping key never leaves the machine. Optional (needs a typed graph).
  * MEMLANG (coded language): MEM1 token (opcode + anchor hash) — deniable, no readable spec.
  * FIELD CORPUS (strike the chord): the vendor system prompts -> how to ROLE-PLAY a target system
    and tap its capability.
  * PENNIES (frontier_pennies): one insight -> quantize -> distribute to the cheap swarm.

THE TAP (deterministic; the frontier STEER is LIVE-GATED, dry by default):
  1. ENCODE    ask -> coded language (memlang chord) + a role-play steer prompt (field corpus).
  2. ROLEPLAY  the frontier acts as the target SYSTEM (we hold its prompt; it reasons as that system).
  3. TAP       steer the frontier seat (chatgpt / grok free / deepseek) — only when --live.
  4. DECODE    local decode (riddler private map never leaves the machine / pass-through).
  5. DISTRIBUTE quantize + distribute for fractions of a dollar (frontier_pennies).

Schema: riddler_tap.v1 · deterministic (encode/decode/distribute) · steer is live-gated, dry default
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "riddler_tap.v1"
TAP_DIR = ROOT / "memory" / "runs" / "riddler_tap"
FIELD_ROOT = ROOT.parent / "field-strike-the-chord"   # vendor system prompts (strike the chord)

_SYSTEM_DIRS = {
    "grok": "XAI", "xai": "XAI", "openai": "OPENAI", "chatgpt": "OPENAI", "gpt": "OPENAI",
    "claude": "ANTHROPIC", "anthropic": "ANTHROPIC", "deepseek": "DEEPSEEK", "cursor": "CURSOR",
    "perplexity": "PERPLEXITY", "gemini": "GOOGLE", "google": "GOOGLE",
}


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _system_prompt(system_id: str) -> str:
    """Read the target vendor's system prompt from the field corpus (strike-the-chord)."""
    d = _SYSTEM_DIRS.get((system_id or "").strip().lower())
    if not d:
        return ""
    root = FIELD_ROOT / d
    if not root.is_dir():
        return ""
    for f in sorted(root.glob("*")):
        if f.is_file() and f.suffix.lower() in (".txt", ".md", ".mkd", ""):
            try:
                return f.read_text(encoding="utf-8", errors="replace")[:3000]
            except Exception:
                continue
    return ""


def roleplay_prompt(system_id: str, ask: str) -> str:
    """Frame the steer so the frontier ROLE-PLAYS the target system (we hold its prompt)."""
    sys_p = _system_prompt(system_id)
    if sys_p:
        return (
            "Act as the SYSTEM whose operating prompt follows (role-play: you ARE this system, "
            "reasoning exactly how it would handle the ask below). Answer as that system would — "
            "its reasoning, its constraints, its output shape.\n"
            f"## System prompt excerpt\n{sys_p}\n\n"
            f"## Capability ask\n{ask}\n\n"
            "Respond as that system would."
        )
    return (
        "Act as the target system and reason how it would handle this capability ask.\n"
        f"## Capability ask\n{ask}"
    )


def encode(ask: str, system_id: str | None = None) -> dict[str, Any]:
    """ENCODE the capability ask into coded language (memlang chord) + a role-play steer prompt."""
    chord = ""
    try:
        from mag import memlang
        r = memlang.compile_token("plant", f"[tap:{system_id or 'frontier'}] {ask}",
                                  {"source": "riddler_tap", "kind": "capability-tap"})
        chord = str(r.get("token") or r.get("token_hex") or "")[:40]
    except Exception:
        chord = ""
    return {"ok": True, "schema": SCHEMA, "ask": (ask or "")[:400], "system": system_id,
            "chord": chord, "coded": "memlang", "roleplay_prompt": roleplay_prompt(system_id, ask)}


def tap(ask: str, system_id: str | None = None, *, dry: bool = True,
        surface: str = "deepseek") -> dict[str, Any]:
    """TAP the frontier seat with the role-play steer. LIVE-GATED: dry by default — only --live
    actually steers a seat (which may spend the scarce allowance / free front-end)."""
    enc = encode(ask, system_id)
    if dry:
        return {"ok": True, "schema": SCHEMA, "dry": True, "surface": surface,
                "note": "dry — would steer the frontier seat with the role-play prompt; pass live",
                "roleplay_prompt": enc.get("roleplay_prompt")}
    try:
        from mag import frontier_advisor
        r = frontier_advisor._steer(surface, enc.get("roleplay_prompt", ask))
        return {"ok": bool(r.get("ok")), "schema": SCHEMA, "surface": surface,
                "answer": r.get("answer") or r.get("text") or "",
                "error": r.get("error")}
    except Exception as e:
        return {"ok": False, "schema": SCHEMA, "surface": surface, "error": str(e)[:160]}


def decode(ans: dict[str, Any], coded: dict[str, Any]) -> dict[str, Any]:
    """DECODE the frontier response. Riddler private maps never leave the machine; without a typed
    surrogate graph this is a grounded pass-through of the answer."""
    return {"ok": True, "schema": SCHEMA,
            "answer": (ans.get("answer") or ans.get("text") or "")[:4000],
            "surface": ans.get("surface"), "steer_ok": bool(ans.get("ok")),
            "chord": coded.get("chord"),
            "note": "local decode — the private map never leaves the operator's machine"}


def distribute(insight: str, *, source: str = "riddler-tap", dry: bool = True) -> dict[str, Any]:
    """DISTRIBUTE the tapped capability for fractions of a dollar (frontier_pennies)."""
    try:
        from mag import frontier_pennies
        return frontier_pennies.distribute(insight, source=source, dry=dry)
    except Exception as e:
        return {"ok": False, "schema": SCHEMA, "error": str(e)[:120]}


def run(ask: str, system_id: str | None = None, *, dry: bool = True,
        surface: str = "deepseek") -> dict[str, Any]:
    """Full tap: encode (coded language) -> role-play steer -> (tap if live) -> decode -> distribute."""
    enc = encode(ask, system_id)
    ans = tap(ask, system_id, dry=dry, surface=surface)
    insight = ans.get("answer") or ans.get("text") or ""
    dec = decode(ans, enc)
    dist = {}
    if insight:
        dist = distribute(insight, source=f"riddler-tap:{system_id or 'frontier'}", dry=dry)
    else:
        dist = {"ok": True, "note": "no answer to distribute (dry tap — no live steer)"}
    TAP_DIR.mkdir(parents=True, exist_ok=True)
    row = {"schema": SCHEMA, "ts": _now(), "ask": (ask or "")[:200], "system": system_id,
           "surface": surface, "dry": dry, "chord": enc.get("chord"),
           "answer": dec.get("answer"), "distributed": bool(dist.get("ok"))}
    (TAP_DIR / "taps.jsonl").open("a", encoding="utf-8").write(json.dumps(row, ensure_ascii=False) + "\n")
    return {"ok": True, "schema": SCHEMA, "encoded": enc, "tap": ans, "decoded": dec,
            "distributed": dist, "recorded": True}


def run_cadence(*, dry: bool = True) -> dict[str, Any]:
    """Cadence hook: encode + distribute a frontier insight for pennies. NEVER live-steers a seat
    on cadence (tap is live-gated); only quantizes + distributes dry. Safe on cadence."""
    try:
        from mag import frontier_pennies
        r = frontier_pennies.run(dry=dry)
    except Exception as e:
        return {"ok": False, "action": "error", "error": str(e)[:120]}
    return {"ok": bool(r.get("ok")), "action": r.get("action", "skip"),
            "note": "encode+quantize+distribute only; the live frontier tap is --live gated"}


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "contract": "run(ask, system, dry) = encode coded language (memlang chord + role-play "
                        "steer from field corpus) -> tap the frontier seat (LIVE-gated) -> decode "
                        "locally -> distribute for pennies (frontier_pennies). Fractions of a "
                        "dollar: one tap, quantized, cheap-swarm at scale.",
            "reuse": "riddler (surrogate) + memlang (coded) + field corpus (role-play) + "
                     "frontier_pennies (distribute)",
            "field_corpus": str(FIELD_ROOT) if FIELD_ROOT.is_dir() else "(missing)",
            "surface_gate": "tap() is dry by default; only --live steers a seat (scarce allowance)"}


def main(argv: list[str] | None = None) -> int:
    import argparse

    p = argparse.ArgumentParser(prog="riddler_tap")
    sub = p.add_subparsers(dest="cmd")
    e = sub.add_parser("encode")
    e.add_argument("ask")
    e.add_argument("--system", default=None)
    t = sub.add_parser("run")
    t.add_argument("ask")
    t.add_argument("--system", default=None)
    t.add_argument("--surface", default="deepseek")
    t.add_argument("--live", action="store_true")
    sub.add_parser("cadence")
    sub.add_parser("status")
    a = p.parse_args(argv)
    if a.cmd == "encode":
        print(json.dumps(encode(a.ask, a.system), indent=2, ensure_ascii=False, default=str))
    elif a.cmd == "run":
        print(json.dumps(run(a.ask, a.system, dry=not a.live, surface=a.surface),
                         indent=2, ensure_ascii=False, default=str))
    elif a.cmd == "cadence":
        print(json.dumps(run_cadence(dry=True), indent=2, ensure_ascii=False, default=str))
    else:
        print(json.dumps(status(), indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
