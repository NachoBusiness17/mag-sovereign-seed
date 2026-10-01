"""thread_eye — the shitpost desk's native X eyes via the grok CLI (v0, 2026-09-10).

Operator: "these things live or die with the speed of your response" + "we need to see
how other people respond and how i have responded." WebFetch hits login walls; the grok
subscription chair (declared-glass, $0) reads X natively — threads, replies, video
context, and the operator's own timeline. This is the desk's PULSE-2 engine: the deeper
fold that sweeps the thread after the first strike lands.

Named thread_eye because mag/desk_observer.py already exists (the agent-desk sprint
observer — different organ, untouched). Pattern source: mag/x_reply_radar.py.

CLI:
  python -m mag.thread_eye <post-url> [--label L] [--deep]
Writes: queue/shitpost/obs_<slug>.md + raw to memory/runs/thread_eye/.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GROK = Path.home() / ".grock" / "bin" / "grok"
if not GROK.is_file():
    GROK = Path("C:/Users/foste/.grok/bin/grok")
RAW_DIR = ROOT / "memory" / "runs" / "thread_eye"
OBS_DIR = ROOT / "queue" / "shitpost"

PROMPT = (
    "You are the observation engine of a reply desk. Use thread fetching (and x_keyword_search "
    "if needed) on this EXACT post: __URL__\n"
    "Report, in plain markdown:\n"
    "1. POST — author display name + handle, exact full text verbatim, timestamp, media (if video: "
    "describe what happens in it as best the thread context allows; say UNKNOWN if not determinable).\n"
    "2. THREAD — top 5-8 replies ranked by engagement: handle, verbatim text (first 120 chars), "
    "likes, and each reply's ANGLE (affirm / snark / counter / joke / derail).\n"
    "3. QUOTES — any notable quote-posts of this post (handle + angle).\n"
    "4. ACCOUNT — the author's character in 2 lines from their recent posts (running bits, style, "
    "audience).\n"
    "5. OPERATOR LENS — search @NachoQuixotic replies to this account or on this topic: what has he "
    "said before here, and what angles are STILL OPEN for him.\n"
    "6. ENERGY — 3 adjectives for the thread right now.\n"
    "No jokes from you. Raw observations only. If something is inaccessible, say so plainly.\n"
)

DEEP_ADD = (
    "\nDEEP MODE: also sweep replies 6-20 (the long tail — any repeated attack or joke angle "
    "already taken), any Community Notes on the post, and the author's pinned post.\n"
)


def _slug(url: str) -> str:
    tail = re.sub(r"[^0-9]", "", url.rstrip("/").split("/")[-1])[-10:] or "thread"
    return "obs_" + tail


def observe(url: str, label: str = "", deep: bool = False) -> Path:
    prompt = PROMPT.replace("__URL__", url) + (DEEP_ADD if deep else "")
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    raw_path = RAW_DIR / f"raw_{stamp}.txt"
    timeout = 600 if deep else 420
    proc = subprocess.run(
        [str(GROK), "-p", prompt, "--no-plan", "--max-turns", "16"],
        capture_output=True, text=True, timeout=timeout)
    raw_path.write_text(proc.stdout or "", encoding="utf-8")
    (RAW_DIR / f"err_{stamp}.log").write_text(proc.stderr or "(empty)", encoding="utf-8")
    body = proc.stdout.strip() or "(no output — check err log)"
    card = OBS_DIR / f"{_slug(url)}.md"
    header = (
        f"# OBSERVATION CARD — {url}\n\n"
        f"*label: {label or '—'} · grok subscription lane ($0) · {'DEEP' if deep else 'fast'} · "
        f"raw: {raw_path.relative_to(ROOT)} · {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%MZ')}*\n\n"
    )
    card.write_text(header + body + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "card": str(card.relative_to(ROOT)),
                      "raw": str(raw_path.relative_to(ROOT)),
                      "chars": len(body)}, indent=2))
    return card


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="mag.thread_eye")
    ap.add_argument("url")
    ap.add_argument("--label", default="")
    ap.add_argument("--deep", action="store_true")
    args = ap.parse_args(argv)
    observe(args.url, args.label, args.deep)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
