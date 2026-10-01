"""Day-by-day diary + project story — narrative spine from filed beads and law docs.

Not a second DNA store. Reads registry + key project files on disk.
Product: origins → supporting docs → day-by-day path → where we are.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from config import ROOT

SCHEMA = "mag_diary.v2"
FACE = ROOT / "memory" / "diary_latest.md"

# Curated supporting documents (role is product language, not marketing)
_SUPPORTING: list[dict[str, str]] = [
    {"path": "docs/DNA.md", "role": "Why we file real notes on disk (not only chat)"},
    {"path": "docs/ref/OPERATOR_CARD.md", "role": "Daily how-to: find → file → load a short pack"},
    {"path": "docs/ref/MIRROR_PRESENTED.md", "role": "Quote you as you wrote it—not as the model rewrites you"},
    {"path": "docs/ref/IDEA_GRAPH.md", "role": "Topic map for ideas (early version)"},
    {"path": "docs/ref/DASHBOARD_DESIGN.md", "role": "What the dashboard is for (status first, depth second)"},
    {"path": "docs/ref/MAG_OS_v2.md", "role": "How Mag governs itself as software"},
    {"path": "docs/ref/strike_origin.md", "role": "Where the “strike / mirror” language came from"},
    {"path": "docs/HOW_TO_MAG_DASHBOARD.md", "role": "Plain walkthrough of this dashboard"},
    {"path": "README.md", "role": "What Mag is for in one page"},
    {"path": "memory/agent_state/LATEST.md", "role": "What the system last knew about itself—read before redesign"},
    {"path": "memory/working.md", "role": "Today’s goals, open items, done list"},
    {"path": "memory/ideas/LATEST.md", "role": "Latest face of the idea map"},
    {
        "path": "../mycelial-republic/docs/CONSTITUTION.md",
        "role": "Public project rules: no kings, no fake rank",
    },
    {
        "path": "../mycelial-republic/docs/MILESTONES.md",
        "role": "Honest milestones (practice vs heavy training)",
    },
    {
        "path": "../mycelial-republic/docs/BOOT_SOIL.md",
        "role": "How to practice with exports you already have",
    },
    {
        "path": "../mycelial-republic/docs/INST_001_MAG_BRIDGE.md",
        "role": "Private office vs public project—what never crosses",
    },
]


def _clip(s: str, n: int) -> str:
    t = re.sub(r"\s+", " ", str(s or "")).strip()
    if len(t) <= n:
        return t
    return t[: n - 1].rstrip() + "…"


def _short_url(url: str, max_len: int = 40) -> str:
    try:
        u = urlparse(url)
        host = (u.netloc or "").replace("www.", "")
        path = (u.path or "").rstrip("/") or "/"
        if len(path) > 24:
            path = path[:12] + "…" + path[-8:]
        out = host + path
        return out if len(out) <= max_len else out[: max_len - 1] + "…"
    except Exception:
        return _clip(url, max_len)


def _clean_prose(text: str, max_len: int = 280) -> str:
    t = str(text or "")
    t = re.sub(r"https?://[^\s)\]>'\"]+", lambda m: _short_url(m.group(0)), t)
    t = re.sub(r"\bTags?:\s*[^.]*\.?", "", t, flags=re.I)
    t = re.sub(r"\(\d+\s*operator turns[^)]*\)", "", t, flags=re.I)
    t = re.sub(r"\s+", " ", t).strip()
    return _clip(t, max_len)


def _day_key(iso: str | None) -> str:
    if not iso:
        return "undated"
    m = re.match(r"(\d{4}-\d{2}-\d{2})", str(iso))
    return m.group(1) if m else "undated"


def _when_label(iso: str | None) -> str:
    if not iso:
        return ""
    m = re.match(r"(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2})", str(iso))
    if m:
        return f"{m.group(1)} {m.group(2)}"
    return _clip(str(iso), 16)


def _sort_key(row: dict[str, Any]) -> str:
    return str(row.get("end_minute") or row.get("start_minute") or row.get("updated") or "")


def _read_text(path: Path, limit: int = 12000) -> str:
    if not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:limit]
    except OSError:
        return ""


def _section_bullets(md: str, heading_substr: str, *, max_n: int = 8) -> list[str]:
    """Bullets under a ## heading whose title contains heading_substr (case-insensitive)."""
    want = heading_substr.strip().lower()
    lines = md.splitlines()
    out: list[str] = []
    in_sec = False
    for ln in lines:
        s = ln.strip()
        if s.startswith("## "):
            title = s[3:].strip().lower()
            if in_sec:
                break
            in_sec = want in title
            continue
        if not in_sec:
            continue
        if s.startswith("#"):
            break
        if s.startswith("- ") or s.startswith("* "):
            out.append(_clean_prose(s.lstrip("-* ").strip(), 160))
        if len(out) >= max_n:
            break
    return [x for x in out if x]


def _first_paragraph_after(md: str, marker: str | None = None, *, max_len: int = 420) -> str:
    """First non-empty prose paragraph (optionally after a marker line)."""
    text = md
    if marker:
        i = md.lower().find(marker.lower())
        if i >= 0:
            text = md[i:]
    paras: list[str] = []
    buf: list[str] = []
    for ln in text.splitlines():
        s = ln.strip()
        if s.startswith("#") or s.startswith("|") or s.startswith("```") or s.startswith("---"):
            if buf:
                break
            continue
        if not s:
            if buf:
                paras.append(" ".join(buf))
                break
            continue
        if s.startswith("- ") or s.startswith("* ") or re.match(r"^\d+\.", s):
            if buf:
                paras.append(" ".join(buf))
                break
            continue
        buf.append(s)
    if buf and not paras:
        paras.append(" ".join(buf))
    return _clean_prose(paras[0] if paras else "", max_len)


def _resolve(rel: str) -> Path:
    return (ROOT / rel).resolve()


def build_project_story() -> dict[str, Any]:
    """Origins, one-line, goals, dual house, supporting docs that exist on disk."""
    dna = _read_text(ROOT / "docs" / "DNA.md")
    readme = _read_text(ROOT / "README.md")
    working = _read_text(ROOT / "memory" / "working.md")
    agent = _read_text(ROOT / "memory" / "agent_state" / "LATEST.md")
    strike = _read_text(ROOT / "docs" / "ref" / "strike_origin.md")
    const_path = ROOT.parent / "mycelial-republic" / "docs" / "CONSTITUTION.md"
    constitution = _read_text(const_path)

    one_line = ""
    for ln in agent.splitlines():
        if ln.strip().startswith("Modular lattice") or "do not reinvent" in ln.lower():
            continue
        if ln.strip() and not ln.startswith("#") and not ln.startswith("**") and "Modular" in ln:
            one_line = _clean_prose(ln, 220)
            break
    # agent_state one_line section
    for i, ln in enumerate(agent.splitlines()):
        if "one line" in ln.lower() and ln.startswith("#"):
            for ln2 in agent.splitlines()[i + 1 : i + 8]:
                s = ln2.strip()
                if s and not s.startswith("#") and not s.startswith("**"):
                    one_line = _clean_prose(s, 240)
                    break
            break
    if not one_line:
        one_line = _first_paragraph_after(readme, "Product home", max_len=240) or (
            "A local office that files your workdays, plus a public project for a personal "
            "AI mirror—tools you can move, without a cloud company owning the memory."
        )

    origins: list[str] = []
    pre = _first_paragraph_after(constitution, "Preamble", max_len=380)
    if pre:
        origins.append(pre)
    else:
        pre2 = _first_paragraph_after(constitution, "sovereign mirror", max_len=380)
        if pre2:
            origins.append(pre2)
    dna_rule = ""
    for ln in dna.splitlines():
        if "Fidelity lives" in ln or "Residual is" in ln or "Coldest vertex" in ln:
            dna_rule = _clean_prose(ln.lstrip("*").strip(), 220)
            break
    if dna_rule:
        origins.append(dna_rule)
    strike_blurb = ""
    for ln in strike.splitlines():
        if ln.startswith("**Blurb:**"):
            strike_blurb = _clean_prose(ln.replace("**Blurb:**", "").strip(), 220)
            break
    if not strike_blurb:
        strike_blurb = _first_paragraph_after(strike, "napkin", max_len=220)
    if strike_blurb:
        origins.append("Strike origin: " + strike_blurb)
    if not origins:
        origins.append(
            "Started as a garage path: a local filing office and a public set of rules—"
            "AI as hired help under you, not a cloud operating system that marries your life."
        )

    goals = _section_bullets(working, "Goals", max_n=6)
    if not goals:
        goals = _section_bullets(working, "Lane", max_n=4)
    open_items = _section_bullets(working, "Open", max_n=6)
    done = _section_bullets(working, "Done this arc", max_n=6)

    spine = _section_bullets(working, "Goals", max_n=12)
    # prefer spine line from working goals
    spine_line = ""
    for g in goals:
        if "spine" in g.lower() or "idea lattice" in g.lower() or "avatar" in g.lower():
            spine_line = g
            break
    if not spine_line:
        spine_line = (
            "Map ideas → run them through a local workspace → optional personal mirror → "
            "keep the house portable (the model is furniture; your files are the house)."
        )

    docs: list[dict[str, Any]] = []
    for spec in _SUPPORTING:
        p = _resolve(spec["path"])
        if not p.is_file():
            continue
        try:
            rel = str(p.relative_to(ROOT)).replace("\\", "/")
            house = "mag"
        except ValueError:
            rel = str(p).replace("\\", "/")
            house = "republic" if "mycelial-republic" in rel else "other"
        excerpt = _first_paragraph_after(_read_text(p, 4000), max_len=160)
        docs.append(
            {
                "path": rel,
                "role": spec["role"],
                "house": house,
                "exists": True,
                "excerpt": excerpt,
            }
        )

    dual = (
        "Dual house: **Mag** (person residual, dashboard, seats, idea graph) "
        "and **mycelial-republic** (forest law, soil, selftest, spore path). "
        "Practice R0-lite is not blocked by empty weight archive."
    )

    return {
        "title": "Sovereign mirror / Mag office",
        "one_line": one_line,
        "spine": spine_line,
        "origins": origins[:5],
        "goals": goals[:6],
        "open": open_items[:6],
        "done_recent": done[:6],
        "dual_house": dual,
        "supporting_docs": docs,
        "n_docs": len(docs),
    }


def build_diary(*, limit: int = 80, newest_first: bool = False) -> dict[str, Any]:
    from mag.registry import list_registry

    project = build_project_story()

    rows = list_registry(limit=max(limit, 200))
    rows = sorted(rows, key=_sort_key, reverse=newest_first)

    entries: list[dict[str, Any]] = []
    themes: dict[str, int] = {}
    for r in rows[:limit]:
        theme = str(r.get("dominant_theme") or "").strip()
        if theme:
            themes[theme] = themes.get(theme, 0) + 1
        bullets_raw = r.get("bullets") or []
        if not isinstance(bullets_raw, list):
            bullets_raw = []
        beats = []
        for b in bullets_raw:
            cb = _clean_prose(str(b), 100)
            if cb and not cb.startswith("http"):
                beats.append(cb)
            if len(beats) >= 3:
                break
        title = _clean_prose(r.get("title") or "Untitled day", 90)
        blurb = _clean_prose(r.get("blurb") or r.get("one_liner") or "", 260)
        if not blurb and beats:
            blurb = beats[0]
        end = r.get("end_minute") or r.get("start_minute")
        entries.append(
            {
                "session_id": r.get("session_id"),
                "day": _day_key(end),
                "when": _when_label(end),
                "title": title,
                "blurb": blurb or "No summary filed for this day.",
                "beats": beats,
                "theme": theme or None,
                "tension": r.get("tension_index"),
                "duration_minutes": r.get("duration_minutes"),
                "has_residual": bool(r.get("has_residual")),
            }
        )

    chrono = sorted(entries, key=lambda e: str(e.get("when") or e.get("day") or ""))
    first = chrono[0] if chrono else None
    last = chrono[-1] if chrono else None
    top_themes = sorted(themes.items(), key=lambda kv: -kv[1])[:6]

    if first and last and len(chrono) > 1:
        arc = (
            f"From {first.get('day')} (“{first.get('title')}”) "
            f"to {last.get('day')} (“{last.get('title')}”) — "
            f"{len(chrono)} filed days."
        )
    elif last:
        arc = f"One filed day so far: {last.get('day')} — “{last.get('title')}”."
    else:
        arc = "No days filed yet. Close a session / backfill residual to start the diary."

    chapters: list[dict[str, Any]] = []
    by_day: dict[str, list[dict[str, Any]]] = {}
    for e in chrono:
        d = e.get("day") or "undated"
        by_day.setdefault(d, []).append(e)
    order_days = sorted(by_day.keys(), reverse=newest_first)

    for d in order_days:
        day_entries = by_day[d]
        chapters.append(
            {
                "day": d,
                "n": len(day_entries),
                "entries": day_entries,
                "headline": day_entries[0].get("title")
                if len(day_entries) == 1
                else f"{len(day_entries)} sessions",
            }
        )

    return {
        "ok": True,
        "schema": SCHEMA,
        "ts": datetime.now(timezone.utc).isoformat(),
        "project": project,
        "arc": arc,
        "n_days": len(by_day),
        "n_entries": len(entries),
        "first_day": first.get("day") if first else None,
        "last_day": last.get("day") if last else None,
        "themes": [{"id": k, "n": v} for k, v in top_themes],
        "newest_first": newest_first,
        "chapters": chapters,
        "entries": entries,
    }


def format_diary_markdown(d: dict[str, Any] | None = None) -> str:
    d = d or build_diary(newest_first=False)
    proj = d.get("project") or {}
    lines = [
        "# Mag diary — project story & how we got here",
        "",
        f"**schema:** `{d.get('schema')}`  ",
        f"**session arc:** {d.get('arc')}",
        "",
        "## Project",
        "",
        f"**{proj.get('title') or 'Sovereign mirror'}**  ",
        f"{proj.get('one_line') or ''}",
        "",
        f"**Spine:** {proj.get('spine') or ''}",
        "",
        f"{proj.get('dual_house') or ''}",
        "",
    ]
    if proj.get("origins"):
        lines.append("### Origins")
        lines.append("")
        for o in proj["origins"]:
            lines.append(f"- {o}")
        lines.append("")
    if proj.get("goals"):
        lines.append("### Goals (working)")
        lines.append("")
        for g in proj["goals"]:
            lines.append(f"- {g}")
        lines.append("")
    if proj.get("open"):
        lines.append("### Open now")
        lines.append("")
        for g in proj["open"]:
            lines.append(f"- {g}")
        lines.append("")
    if proj.get("done_recent"):
        lines.append("### Done this arc")
        lines.append("")
        for g in proj["done_recent"]:
            lines.append(f"- {g}")
        lines.append("")
    docs = proj.get("supporting_docs") or []
    if docs:
        lines.append("### Supporting documents")
        lines.append("")
        for doc in docs:
            lines.append(f"- `{doc.get('path')}` — {doc.get('role')}")
            if doc.get("excerpt"):
                lines.append(f"  - _{doc['excerpt']}_")
        lines.append("")

    themes = d.get("themes") or []
    if themes:
        lines.append(
            "**Session themes:** " + ", ".join(f"{t['id']}×{t['n']}" for t in themes[:8])
        )
        lines.append("")

    lines.append("## Day by day")
    lines.append("")
    for ch in d.get("chapters") or []:
        lines.append(f"### {ch.get('day')}")
        lines.append("")
        for e in ch.get("entries") or []:
            lines.append(f"#### {e.get('title')}")
            meta = " · ".join(
                x
                for x in [
                    e.get("when"),
                    e.get("theme") and f"theme {e.get('theme')}",
                    e.get("tension") is not None
                    and f"T={float(e.get('tension')):.2f}",
                ]
                if x
            )
            if meta:
                lines.append(f"*{meta}*")
                lines.append("")
            lines.append(e.get("blurb") or "")
            lines.append("")
            for b in e.get("beats") or []:
                lines.append(f"- {b}")
            if e.get("beats"):
                lines.append("")
            sid = e.get("session_id") or ""
            if sid:
                lines.append(f"`{sid[:13]}…`")
                lines.append("")
    lines.append("---")
    lines.append(
        "*Diary is projection of residual beads + law docs on disk — residual remains DNA.*"
    )
    lines.append("")
    return "\n".join(lines)


def write_diary_face(*, newest_first: bool = False) -> dict[str, Any]:
    d = build_diary(newest_first=newest_first)
    FACE.parent.mkdir(parents=True, exist_ok=True)
    FACE.write_text(format_diary_markdown(d), encoding="utf-8")
    d["face"] = str(FACE.relative_to(ROOT)).replace("\\", "/")
    return d
