"""ractor_vessels — steerable persona vessels on the deepseek lanes (v0, 2026-09-10).

Operator order: "we launched multiple deepseeks as steerable vessels — we need to do
the same here." A vessel = a PANEL ractor mask (queue/handoff/ractors/*.md) + the desk
voice laws + one steer (the task). Stateless per firing — the mask is the memory, the
steer is the moment. Strikes land on the take board under VESSEL RETURNS; raw runs
log to memory/runs/vessels/ for desk audit.

CLI:
  python -m mag.ractor_vessels fire --mask BAUDRILLARD --steer "<task>" [--label L]
  python -m mag.ractor_vessels wave --wave-file tasks.jsonl [--label L]
      tasks.jsonl rows: {"mask": "JUNG", "steer": "..."}
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

RACTORS_DIR = ROOT / "queue" / "handoff" / "ractors"
RUNS_DIR = ROOT / "memory" / "runs" / "vessels"
BOARD = ROOT / "queue" / "shitpost" / "TAKE_BOARD.md"
PROVIDER = "deepseek"

VOICE_LAWS = (
    "DESK VOICE LAWS: one strike, 15 words or fewer unless the steer says otherwise. "
    "Deadpan caption energy. Hit an archetype via inference, metaphor, or simile — "
    "never explain the joke. Subtle, plausible deniability, layered meaning. "
    "Loose punctuation, sentence case, max 2 emoji, no hashtags. "
    "Punch up only — institutions, elites, media, the owner class, never the small. "
    "Quote the target verbatim only when their words are the punchline. "
    "No invented facts: strike only what the steer gives you."
)


def _load_mask(mask: str, limit: int = 1800) -> str:
    """Load the head of a ractor mask spec — the lens, not the whole file."""
    matches = sorted(RACTORS_DIR.glob(f"*{mask.upper()}*"))
    if not matches:
        matches = sorted(RACTORS_DIR.glob(f"*{mask.capitalize()}*"))
    if not matches:
        raise SystemExit(f"no ractor mask matches '{mask}' in {RACTORS_DIR}")
    spec = matches[0].read_text(encoding="utf-8", errors="replace")
    return spec[:limit]


def fire(mask: str, steer: str, label: str = "") -> dict[str, Any]:
    """Fire one steerable vessel: mask + voice laws + steer -> strike via deepseek."""
    from models.providers import chat_provider

    lens = _load_mask(mask)
    system_prompt = (
        f"You are a shitpost desk ractor vessel wearing the {mask.upper()} lens.\n"
        f"LENS SPEC (stay inside this lens; its ideas are your ammunition):\n{lens}\n\n"
        f"{VOICE_LAWS}"
    )
    user_prompt = (
        f"STEER (the moment you are striking on):\n{steer}\n\n"
        "Return ONLY the strike text — no preamble, no quotes around it, no explanation."
    )
    t0 = time.time()
    response = chat_provider(PROVIDER, system_prompt, user_prompt, tier="T2",
                             temperature=0.9, max_tokens=200)
    latency_ms = round((time.time() - t0) * 1000)
    ok = bool(response.get("ok"))
    strike = (response.get("content") or response.get("text") or "").strip()
    out = {
        "schema": "ractor_vessel.v1",
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "mask": mask.upper(), "label": label, "ok": ok,
        "strike": strike[:600], "latency_ms": latency_ms,
        "model": response.get("model", ""), "error": response.get("error", ""),
        "steer": steer[:300],
    }
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    (RUNS_DIR / f"vessel_{mask.lower()}_{stamp}.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


def land_on_board(results: list[dict[str, Any]], label: str) -> None:
    """Append vessel strikes to the take board under a VESSEL RETURNS section."""
    lines = [f"\n### VESSEL RETURNS — {label}", ""]
    for r in results:
        if r["ok"] and r["strike"]:
            lines.append(f"**{r['mask']} (vessel, deepseek)**")
            lines.append("```")
            lines.append(r["strike"])
            lines.append("```")
            lines.append("")
    if BOARD.is_file() and len(lines) > 2:
        with BOARD.open("a", encoding="utf-8") as f:
            f.write("\n".join(lines))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="mag.ractor_vessels")
    sub = ap.add_subparsers(dest="cmd", required=True)
    f1 = sub.add_parser("fire")
    f1.add_argument("--mask", required=True)
    f1.add_argument("--steer", required=True)
    f1.add_argument("--label", default="")
    f1.add_argument("--board", action="store_true", help="land on take board")
    f2 = sub.add_parser("wave")
    f2.add_argument("--wave-file", required=True)
    f2.add_argument("--label", default="")
    f2.add_argument("--board", action="store_true")
    args = ap.parse_args(argv)

    if args.cmd == "fire":
        out = fire(args.mask, args.steer, args.label)
        print(json.dumps(out, indent=2, ensure_ascii=False))
        if args.board:
            land_on_board([out], args.label or out["ts"])
        return 0 if out["ok"] else 1

    if args.cmd == "wave":
        rows = [json.loads(l) for l in
                Path(args.wave_file).read_text(encoding="utf-8").splitlines() if l.strip()]
        results = []
        for r in rows:
            out = fire(r["mask"], r["steer"], args.label)
            results.append(out)
            print(f"{out['mask']}: {'ok' if out['ok'] else out['error']}")
        if args.board:
            land_on_board(results, args.label)
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
