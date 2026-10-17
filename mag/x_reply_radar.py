"""x_reply_radar — daily X engagement recon for the beacon (operator: "look how other
people engage, who the top replies to major AI posts are every day").

Runs the grok CLI (subscription lane, $0) with x_keyword_search + thread fetch, parses the
strict-JSON survey, and files a watch card + dashboard/static/x_radar.json with the day's
major AI threads, top-reply leaderboard, and the reply-door read (which windows are open
for @NachoQuixotic).

DOOR LAW (X harvest doctrine): grok CLI is the declared-glass $0 subscription door; cite-verify
before amplifying anything we did not read ourselves.

CLI:
  python -m mag.x_reply_radar run                 # live recon -> card + json
  python -m mag.x_reply_radar parse <raw.json>    # re-parse an existing grok output
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GROK = Path.home() / ".grock" / "bin" / "grok"
if not GROK.is_file():
    GROK = Path("C:/Users/ESTATE_USER/.grok/bin/grok")
OUT_DIR = ROOT / "memory" / "runs" / "x_reply_radar"
CARD = ROOT / "watch" / ("X_REPLY_RADAR_" + datetime.now(timezone.utc).strftime("%Y%m%d") + ".md")
RADAR_JSON = ROOT / "dashboard" / "static" / "x_radar.json"

PROMPT = (
    "Use x_keyword_search and thread fetching to survey X engagement meta for the LAST 24 HOURS "
    "(today __TODAY__). TASKS: 1) Find the 5-8 biggest AI-community posts of the last 24h (authors "
    "like sama, karpathy, swyx, simonw, elonmusk, openai, anthropic, openaidocs, or viral AI posts "
    "with high likes). 2) For each, fetch the thread and list the TOP 3-5 REPLIES ranked by likes: "
    "reply author handle, reply text (first 100 chars), like count, timing after parent. 3) TALLY a "
    "leaderboard: accounts appearing as top repliers across MULTIPLE threads, with their style. 4) "
    "Note PATTERNS: reply format (one-liner, data flex, joke, verbatim-quote-of-the-post, "
    "contrarian take, genuine expertise), length, timing window. OUTPUT: strict JSON only, shaped "
    "exactly like this example: {\"threads\":[{\"author\":\"\",\"post_snippet\":\"\",\"likes\":0,"
    "\"top_replies\":[{\"author\":\"\",\"snippet\":\"\",\"likes\":0,\"timing\":\"\"}]}],"
    "\"leaderboard\":[{\"account\":\"\",\"appearances\":0,\"style\":\"\"}],\"patterns\":[\"\"]}"
)


def _parse(raw: str) -> dict:
    m = re.search(r"```json\s*(\{.*?\})\s*```", raw, re.S)
    if not m:
        m = re.search(r"(\{.*\"threads\".*\})", raw, re.S)
    if not m:
        raise SystemExit("no JSON block in grok output")
    return json.loads(m.group(1))


def emit(d: dict, raw_path: Path) -> None:
    raw_path = raw_path.resolve()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    lines = [f"# X REPLY RADAR — {today}", "",
             "*grok CLI recon, $0 subscription lane · raw: " + str(raw_path.relative_to(ROOT)) + "*",
             "", "## Threads + top replies", ""]
    for t in d.get("threads", []):
        lines.append(f"- **@{t.get('author')}** [{t.get('likes')} likes] {t.get('post_snippet', '')[:90]}")
        for r in t.get("top_replies", [])[:5]:
            lines.append(f"  - @{r.get('author')} [{r.get('likes')}] ({r.get('timing', '?')}) "
                         f"{r.get('snippet', '')[:80]}")
    lines += ["", "## Leaderboard (cross-thread reply aristocracy)", ""]
    for a in d.get("leaderboard", []):
        lines.append(f"- @{a.get('account')} — {a.get('appearances')} threads — {a.get('style', '')}")
    lines += ["", "## Patterns", ""]
    for p in d.get("patterns", []):
        lines.append(f"- {p}")
    CARD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    RADAR_JSON.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    print(f"card -> {CARD.name}; json -> {RADAR_JSON.name}; "
          f"{len(d.get('threads', []))} threads, {len(d.get('leaderboard', []))} leaderboard rows")


def run() -> None:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    raw_path = OUT_DIR / f"out_{today}.json"
    proc = subprocess.run(
        [str(GROK), "-p", PROMPT.replace("__TODAY__", today), "--no-plan", "--max-turns", "12"],
        capture_output=True, text=True, timeout=420)
    (OUT_DIR / f"err_{today}.log").write_text(proc.stderr or "(empty stderr)", encoding="utf-8")
    raw_path.write_text(proc.stdout, encoding="utf-8")
    emit(_parse(proc.stdout), raw_path)


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"
    if cmd == "run":
        run()
    elif cmd == "parse" and len(sys.argv) > 2:
        raw = Path(sys.argv[2]).read_text(encoding="utf-8")
        emit(_parse(raw), Path(sys.argv[2]))
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
