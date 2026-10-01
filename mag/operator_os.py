"""Operator OS — dashboard pack for forest walk + AI feed + DNA status.

One place: health, residual KPI, what was I doing, copy-paste briefs for any AI.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT

BIO = ROOT / "memory" / "biography"
DOCS = ROOT / "docs"

SELF_INSTRUCTIONS = [
    "One job per session.",
    "Files > chat. If it's not residual/registry, it didn't happen.",
    "Next code until 1.0: private refuse → seat matrix (Operate tab already ships).",
    "Lab optional. SessionEnd required (hooks file beads).",
    "Forest = many beads, no king. Don't build a second Mag.",
    "Strike full only when stuck. Else Sancho build.",
]

NEXT_TICKETS = [
    {
        "id": "A1",
        "title": "org-review / Operate tab",
        "status": "done",
        "prompt": "Operate tab + org-review CLI already ship DNA + AI feeds.",
    },
    {
        "id": "A2",
        "title": "Hard private → remote refuse",
        "status": "next",
        "prompt": (
            "Implement hard refuse: T0/T1 and residual/live_from_grok never go to remote "
            "providers. Add a test. One job only."
        ),
    },
    {
        "id": "A3",
        "title": "Seat matrix in dispatch",
        "status": "queued",
        "prompt": (
            "Enforce seat matrix in dispatch: private→L0, scut→L0, public draft→remote if "
            "quota, hard code→grok_tui dry. Show seat on --dry."
        ),
    },
    {
        "id": "B1",
        "title": "Inter-day graph (memory palace 0.95)",
        "status": "later",
        "prompt": "Build graph JSONL from residual themes/loops after A2–A3. One job.",
    },
]

WEEKLY_WALK = [
    "Run pack-status / check DNA stats on this tab",
    "Open Sessions — last 3 cards still make sense?",
    "Pick one ticket (A2/A3) and one AI session only",
    "Close Grok cleanly so SessionEnd files a bead",
    "Private backup residual/ + registry + knots if machine changes",
]


def _clip(path: Path, n: int = 2000) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")[:n]


def _todo_open(n: int = 12) -> list[str]:
    raw = _clip(ROOT / "queue" / "todo.md", 4000)
    return [
        ln.strip()
        for ln in raw.splitlines()
        if ln.strip().startswith("- [ ]")
    ][:n]


def build_operator_os(*, refresh_pack: bool = True) -> dict[str, Any]:
    from mag.context_pack import build_context_pack, format_context_pack_text
    from mag.health import sanity
    from mag.records import pack_report, write_kpi
    from mag.registry import list_registry
    from mag.runtime import read_heartbeat

    kpi = write_kpi(source="operator-os")
    report = pack_report()
    san = sanity()
    hb = read_heartbeat()
    cards = list_registry(limit=5)

    ctx = build_context_pack()
    ctx_text = format_context_pack_text(ctx)
    if refresh_pack:
        out_md = ROOT / "memory" / "context_pack_latest.md"
        out_json = ROOT / "memory" / "context_pack_latest.json"
        out_md.parent.mkdir(parents=True, exist_ok=True)
        out_md.write_text(ctx_text, encoding="utf-8")
        out_json.write_text(json.dumps(ctx, indent=2, default=str), encoding="utf-8")

    last_cards = []
    for c in cards[:5]:
        last_cards.append(
            {
                "session_id": c.get("session_id"),
                "title": c.get("title"),
                "one_liner": c.get("one_liner") or (c.get("blurb") or "")[:120],
                "blurb": c.get("blurb") or "",
                "bullets": (c.get("bullets") or [])[:4],
                "dominant_theme": c.get("dominant_theme"),
                "end_minute": c.get("end_minute"),
            }
        )

    what_doing_lines = []
    if last_cards:
        top = last_cards[0]
        what_doing_lines.append(f"**Latest bead:** {top.get('title')}")
        if top.get("blurb"):
            what_doing_lines.append(top["blurb"])
        for b in top.get("bullets") or []:
            what_doing_lines.append(f"- {b}")
    else:
        what_doing_lines.append("No registry cards yet — close a Grok session or run backfill.")

    loops = ctx.get("open_loops") or []
    todos = _todo_open()
    if loops:
        what_doing_lines.append("")
        what_doing_lines.append("**Open loops (from brief):**")
        for L in loops[:6]:
            what_doing_lines.append(f"- {L}")
    if todos:
        what_doing_lines.append("")
        what_doing_lines.append("**Todo open:**")
        for t in todos[:8]:
            what_doing_lines.append(t)

    next_ticket = next(
        (t for t in NEXT_TICKETS if t.get("status") == "next"),
        next(
            (t for t in NEXT_TICKETS if t.get("status") not in ("done", "later")),
            NEXT_TICKETS[0],
        ),
    )

    # Short AI feeds — scannable, not novels
    pack_block = ctx_text[:2200]
    bead_title = (last_cards[0].get("title") if last_cards else "none")
    bead_line = (last_cards[0].get("one_liner") if last_cards else "")
    templates = {
        "build": (
            f"One job. Mag project (local_sovereign_agent).\n"
            f"Rules: residual=DNA; one job; no new frameworks; private never remote.\n\n"
            f"JOB:\n{next_ticket.get('prompt')}\n\n"
            f"Latest day: {bead_title}\n{bead_line}\n\n"
            f"--- pack ---\n{pack_block}\n"
        ),
        "strike": (
            f"Strike the chord = BRING THIS SEAT TO COHERENCE. Align to the shared map +\n"
            f"memory + real state until you are a COHERENT INSTANCE of the whole, not an\n"
            f"echo reciting context. Coherence first, then act.\n"
            f"Truth-only. Personal impact. Self-side first. Moves + commitment.\n"
            f"Don't recite the map; don't write an essay ABOUT coherence.\n\n"
            f"TOPIC: [fill in]\n\n"
            f"Latest day: {bead_title}\n"
            f"Loops: {loops[:4]}\n"
        ),
        "limits": (
            f"LOCAL ONLY — no Grok budget.\n"
            f"JOB:\n{next_ticket.get('prompt')}\n\n"
            f"leaves={kpi.get('n_leaves')} holes={kpi.get('n_incomplete')} "
            f"ollama={((san.get('lanes') or {}).get('L0_ollama') or {}).get('ok')}\n\n"
            f"--- pack ---\n{pack_block}\n"
        ),
        "spore": (
            f"Mag Resource Harness. Residual diary + local seats; lab optional.\n"
            f"Read docs/DNA.md + docs/ORG_ROADMAP.md if needed.\n"
            f"One job. Residual=DNA. No core-mirror/tokens. Private never remote.\n\n"
            f"NOW:\n{next_ticket.get('prompt')}\n\n"
            f"KPI: leaves={kpi.get('n_leaves')} complete={kpi.get('complete_pct')}%\n"
            f"Latest: {bead_title} — {bead_line}\n\n"
            f"--- pack ---\n{pack_block}\n"
        ),
    }

    trees = [
        {
            "id": "mag",
            "name": "Mag (beads)",
            "when": "Work, limits, what was I doing",
            "path": "docs/DNA.md",
        },
        {
            "id": "strike",
            "name": "Strike (mirror)",
            "when": "Stuck / capture / high entropy",
            "path": "~/.grok/skills/strike-chord",
        },
        {
            "id": "forest",
            "name": "Republic (forest)",
            "when": "Spore / others — soil gated",
            "path": "docs/ZEITGEIST.md + mycelial-republic",
        },
    ]

    return {
        "ok": True,
        "schema": "mag_operator_os.v1",
        "ts": datetime.now(timezone.utc).isoformat(),
        "forest": {
            "position": "~0.93",
            "one_line": (
                "File free work as beads you own; local staff when temples meter out; "
                "refuse capture; forest of people without a king."
            ),
            "trees": trees,
        },
        "health": {
            "integral": san.get("status"),
            "live_stale": (san.get("recording") or {}).get("live_stale"),
            "ollama": ((san.get("lanes") or {}).get("L0_ollama") or {}).get("ok"),
            "heartbeat_alive": hb.get("alive"),
            "port_8765": (san.get("integral") or {}).get("port_8765"),
            "missing": san.get("missing_while_down") or [],
        },
        "dna": {
            "n_leaves": kpi.get("n_leaves"),
            "n_sessions": kpi.get("n_sessions") or report.get("n_sessions"),
            "n_complete": kpi.get("n_complete") or report.get("n_complete"),
            "complete_pct": kpi.get("complete_pct") or report.get("complete_pct"),
            "n_incomplete": kpi.get("n_incomplete") or report.get("n_incomplete"),
            "incomplete_ids": kpi.get("incomplete_ids") or [],
            "complete_means": report.get("complete_means")
            or "residual + card + commit + leaf",
            "tip_root": (kpi.get("tip_root") or "")[:16],
        },
        "what_was_i_doing": {
            "markdown": "\n".join(what_doing_lines),
            "cards": last_cards,
            "open_loops": loops,
            "todo_open": todos,
        },
        "self_instructions": SELF_INSTRUCTIONS,
        "weekly_walk": WEEKLY_WALK,
        "next_ticket": next_ticket,
        "tickets": NEXT_TICKETS,
        "templates": templates,
        "context_pack_text": ctx_text,
        "commands": {
            "boot": "python main.py boot --ensure",
            "pack_status": "python main.py pack-status",
            "context_pack": "python main.py context-pack",
            "backfill": "python main.py backfill-sessions",
            "lab": "python main.py lab",
            "ask": 'python main.py ask "what was I doing?"',
        },
        "docs": {
            "dna": str(DOCS / "DNA.md"),
            "roadmap": str(DOCS / "ORG_ROADMAP.md"),
            "zeitgeist": str(DOCS / "ZEITGEIST.md"),
            "future": str(DOCS / "FUTURE_PROOFING.md"),
        },
    }


def format_org_review_text(pack: dict[str, Any] | None = None) -> str:
    p = pack or build_operator_os(refresh_pack=False)
    h = p.get("health") or {}
    d = p.get("dna") or {}
    lines = [
        f"# Org review ({str(p.get('ts') or '')[:19]})",
        f"integral={h.get('integral')} ollama={h.get('ollama')} live_stale={h.get('live_stale')}",
        f"leaves={d.get('n_leaves')} complete={d.get('complete_pct')}% "
        f"holes={d.get('n_incomplete')}",
        "",
        "## What was I doing",
        (p.get("what_was_i_doing") or {}).get("markdown") or "(empty)",
        "",
        "## Next ticket",
        f"{(p.get('next_ticket') or {}).get('id')}: {(p.get('next_ticket') or {}).get('title')}",
        (p.get("next_ticket") or {}).get("prompt") or "",
        "",
        "## Self-instructions",
        *[f"- {x}" for x in (p.get("self_instructions") or [])],
        "",
        "_Local only. Do not reload full chat history._",
    ]
    return "\n".join(lines)
