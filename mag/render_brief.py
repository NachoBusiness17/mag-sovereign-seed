"""render_brief — inline the newest HUMAN_BRIEF into intel.html (called by fleet_intel).

Kept as its own module so the HTML/regex logic lives in a literally-authored file,
not through layers of shell escaping (the 2026-09-05 map-precedes lesson, applied
to our own tooling: meet the bytes, not the meta-bytes).
"""
from __future__ import annotations

import html as _html
import re as _re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "dashboard" / "static" / "intel.html"
NL = chr(10)


def render_brief_into_page() -> int:
    briefs = sorted((ROOT / "watch").glob("HUMAN_BRIEF_*.md"),
                    key=lambda q: q.stat().st_mtime, reverse=True)
    if not briefs or not PAGE.is_file():
        return 0
    page_text = PAGE.read_text(encoding="utf-8")
    if "<!--BRIEF-START-->" not in page_text:
        return 0
    brief = briefs[0].read_text(encoding="utf-8", errors="replace")
    out = []
    for l in brief.splitlines():
        e = _html.escape(l, quote=False)
        if e.startswith("# "):
            out.append("<h1>" + e[2:] + "</h1>")
        elif e.startswith("## "):
            out.append("<h2>" + e[3:] + "</h2>")
        elif e.startswith("- "):
            out.append('<div class="line">' + e[2:] + "</div>")
        elif _re.match(r"^[0-9]\. ", e):
            out.append('<div class="gate">' + e + "</div>")
        elif e.strip():
            out.append("<div>" + e + "</div>")
    (ROOT / "dashboard" / "static" / briefs[0].name).write_text(brief, encoding="utf-8")
    block = "<!--BRIEF-START-->" + NL + NL.join(out) + NL + "<!--BRIEF-END-->"
    new_page = _re.sub(r"<!--BRIEF-START-->.*?<!--BRIEF-END-->",
                       block.replace("\\", "\\\\"), page_text, flags=_re.S)
    PAGE.write_text(new_page, encoding="utf-8")
    return len(out)
