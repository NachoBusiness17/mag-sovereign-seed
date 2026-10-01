"""DECISION HOOK — the PDB pattern (B2, consumption_salon_20260905).

Every card may carry a machine-readable decision line:
    Decision: launch <what> | retest <slug> | archive <slug> | none
The board shows only UNACTIONED decisions — the operator's minutes are the
fleet's scarcest organ (deepseek-pro: consumer-specific packaging; his one hot
habit gets the finished-intel treatment).

Usage:
    python -m mag.decision_hook sweep            # rebuild json + html board
    python -m mag.decision_hook done <slug>      # mark a card's decision acted

State: state/decisions_done.jsonl (one slug per line, file-native actuation).
Outputs: dashboard/static/decisions.json + decisions.html (link in nav.js).
Stdlib only, ASCII.
"""
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WATCH = ROOT / "watch"
DONE = ROOT / "state" / "decisions_done.jsonl"
OUT_JSON = ROOT / "dashboard" / "static" / "decisions.json"
OUT_HTML = ROOT / "dashboard" / "static" / "decisions.html"
DEC_RE = re.compile(r"(?im)^\s*Decision:\s*(.+?)\s*$")
NONE_RE = re.compile(r"^\s*none\s*$", re.I)
HTML = """<!doctype html><html><head><meta charset="utf-8"><title>DECISIONS</title>
<style>body{background:#0a0a0a;color:#d8d8dc;font-family:ui-monospace,Consolas,monospace;
padding:20px;max-width:980px;margin:0 auto}h1{font-size:.9rem;color:#e8b64a;letter-spacing:.14em}
.d{background:#111114;border:1px solid #232328;border-radius:10px;padding:12px 16px;margin:10px 0}
.d .slug{color:#7cf5ff}.d .what{color:#d8d8dc}.d .age{color:#8a8a92;font-size:.72rem}
.done{color:#7fd18a;font-size:.72rem}</style></head><body>
<h1>DECISIONS — unactioned first (the PDB)</h1><div id="l">loading...</div>
<script>fetch('/static/decisions.json').then(r=>r.json()).then(d=>{
document.getElementById('l').innerHTML=d.decisions.map(x=>
`<div class="d"><span class="slug">${x.slug}</span> — <span class="what">${x.decision}</span>
<br><span class="age">${x.date||'----'} &middot; ${x.title}</span>${x.done?'<br><span class="done">ACTIONED</span>':''}</div>`).join('')
||'nothing awaiting a decision';});</script></body></html>"""


def _done() -> set[str]:
    if not DONE.is_file():
        return set()
    return {l.strip() for l in DONE.read_text(encoding="utf-8").splitlines() if l.strip()}


def sweep() -> dict:
    done = _done()
    items = []
    for p in sorted(WATCH.glob("*.md")):
        text = p.read_text(encoding="utf-8", errors="ignore")
        m = DEC_RE.search(text)
        if not m or NONE_RE.match(m.group(1)):
            continue
        d = re.search(r"_(20\d{6})", p.stem)
        items.append({
            "slug": p.stem,
            "decision": m.group(1)[:160],
            "date": f"{d.group(1)[:4]}-{d.group(1)[4:6]}-{d.group(1)[6:]}" if d else "",
            "title": next((l.lstrip('# ').strip()[:80] for l in text.splitlines()
                           if l.startswith('# ')), p.stem),
            "done": p.stem in done,
        })
    items.sort(key=lambda x: (x["done"], x["date"]), reverse=False)
    data = {"built": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "open": sum(1 for i in items if not i["done"]), "decisions": items}
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(data, ensure_ascii=True, indent=1), encoding="utf-8")
    OUT_HTML.write_text(HTML, encoding="utf-8")
    return data


def mark_done(slug: str) -> str:
    DONE.parent.mkdir(parents=True, exist_ok=True)
    with DONE.open("a", encoding="utf-8") as f:
        f.write(slug + "\n")
    sweep()
    return slug


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "done":
        print("actioned:", mark_done(sys.argv[2]))
    else:
        d = sweep()
        print(f"decision_hook: {len(d['decisions'])} decisions, "
              f"{d['open']} unactioned -> {OUT_HTML.name}")
