"""grok_tandem — grok subscription lanes as headless salon witnesses (operator law 09-05).

OPERATOR ORDER: "why can't we just have grok run in tandem as a cli you can steer
headlessly — you have two, and grokbot." Answer: we can; nobody had wired it. This module
is the wiring. Cash API stays blocked (mag/grok_route.v1); grok rides subscription:

  CHAIR 1 "grok-cli"    — the Grok Build CLI headless mode (`grok -p "<q>" --output-format
                          json --max-turns 1 --no-subagents`), subscription-backed (tier-4
                          OIDC auth), $0 cash. Steerable: --reasoning-effort, --json-schema,
                          --prompt-file, -c/--resume for multi-turn.
  CHAIR 2 "grokbot"     — the SuperGrok front-end via mag.grok_rightsize.call_grok_free
                          (browser-seat door, $0 cash) — the second tandem chair.

Both are DOWN-HONEST: failure returns ok=False, never fabricates, never falls back to cash.
The salons can lose a chair; they cannot silently spend.

CLI:  python -m mag.grok_tandem probe | ask "<question>" [--timeout 120]
API:  ask(question, timeout) -> {"ok": bool, "surface": "grok-cli"|"grokbot",
                                 "answer": str, "error": str, "tokens": int}
Schema: grok_tandem.v1
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

GROK_BIN_CANDIDATES = ("grok", str(Path.home() / ".grok" / "bin" / "grok"))
SCHEMA = "grok_tandem.v1"
LEDGER = Path(__file__).resolve().parent.parent / "memory" / "embassy" / "grok_tandem.jsonl"


def _grok_bin() -> str | None:
    import shutil
    for c in GROK_BIN_CANDIDATES:
        if shutil.which(c) or Path(c).exists():
            return c
    return None


def ask_cli(question: str, *, timeout: int = 180, effort: str = "low",
            max_turns: int = 12) -> dict:
    """CHAIR 1 — headless Grok Build CLI, single-turn, subscription-backed."""
    binpath = _grok_bin()
    if not binpath:
        return {"ok": False, "surface": "grok-cli", "answer": "",
                "error": "grok CLI not found (~/.grok/bin/grok)"}
    cmd = [binpath, "-p", question, "--output-format", "json",
           "--max-turns", str(max_turns), "--no-subagents", "--no-plan",
           "--disable-web-search",
           "--reasoning-effort", effort]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"ok": False, "surface": "grok-cli", "answer": "",
                "error": f"timeout {timeout}s"}
    if p.returncode != 0:
        return {"ok": False, "surface": "grok-cli", "answer": "",
                "error": (p.stderr or p.stdout or f"exit {p.returncode}")[:300]}
    out = (p.stdout or "").strip()
    text, tokens = out, 0
    try:
        j = json.loads(out)
        # Grok Build json: last assistant message text + usage if present
        if isinstance(j, dict):
            text = (j.get("text") or j.get("result") or j.get("content") or out)
            u = j.get("usage") or {}
            tokens = int(u.get("total_tokens") or u.get("completion_tokens") or 0)
    except Exception:
        pass
    if not text:
        return {"ok": False, "surface": "grok-cli", "answer": "",
                "error": "empty headless reply"}
    return {"ok": True, "surface": "grok-cli", "answer": str(text), "tokens": tokens}


def ask_bot(question: str, *, timeout: int = 300) -> dict:
    """CHAIR 2 — SuperGrok front-end (browser-seat door), $0 cash."""
    try:
        from mag.grok_rightsize import call_grok_free
        r = call_grok_free(question, timeout=timeout)
        ok = bool(r.get("ok", r.get("content")))
        return {"ok": ok, "surface": "grokbot", "answer": r.get("content") or "",
                "error": r.get("error", "") if not ok else ""}
    except Exception as e:
        return {"ok": False, "surface": "grokbot", "answer": "", "error": str(e)[:300]}


def ask(question: str, *, timeout: int = 180, chair: str = "grok-cli") -> dict:
    """One tandem chair. Never falls back to cash."""
    r = ask_cli(question, timeout=timeout) if chair == "grok-cli" else ask_bot(question, timeout=timeout)
    _ledger(r, question)
    return r


def tandem(question: str, *, timeout: int = 180) -> list[dict]:
    """BOTH grok chairs witness the same question (tandem). Down-honest each."""
    out = [ask_cli(question, timeout=timeout), ask_bot(question, timeout=timeout)]
    for r in out:
        _ledger(r, question)
    return out


def probe() -> dict:
    """Aliveness probe: one tiny ask per chair. $0 (subscription)."""
    res = tandem("Reply with the single word: ok", timeout=90)
    return {"schema": SCHEMA, "ts": datetime.now(timezone.utc).isoformat(),
            "chairs": [{"surface": r["surface"], "ok": r["ok"],
                        "answer": (r.get("answer") or "")[:40],
                        "error": r.get("error", "")} for r in res]}


def _ledger(r: dict, question: str) -> None:
    try:
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with LEDGER.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": datetime.now(timezone.utc).isoformat(),
                                "surface": r.get("surface"), "ok": r.get("ok"),
                                "tokens": r.get("tokens", 0),
                                "q": question[:120]}) + "\n")
    except Exception:
        pass


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="grok_tandem")
    ap.add_argument("cmd", choices=["probe", "ask"])
    ap.add_argument("question", nargs="?", default="")
    ap.add_argument("--timeout", type=int, default=180)
    a = ap.parse_args()
    if a.cmd == "probe":
        print(json.dumps(probe(), indent=1))
    else:
        print(json.dumps(ask(a.question, timeout=a.timeout), indent=1))
