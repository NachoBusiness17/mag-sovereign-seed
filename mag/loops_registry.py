"""Nested self-improve loop registry — v3-004 manifest.

One read-only manifest listing every Mag loop, its trail path, promote gate, and
status. Alpha honesty: documents what exists vs research.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT

LOOPS: list[dict[str, Any]] = [
    {
        "id": "improve",
        "layer": "harness",
        "loop": "scout → eval → promote (human)",
        "trail": "memory/improve/candidates.jsonl",
        "promote_gate": True,
        "status": "shipped",
        "cli": "main.py improve",
    },
    {
        "id": "autorun",
        "layer": "harness",
        "loop": "fill → route → execute",
        "trail": "memory/runs/governor_autorun_trail.jsonl",
        "promote_gate": False,
        "status": "shipped",
        "cli": "main.py autorun",
    },
    {
        "id": "fkb",
        "layer": "warm_mid",
        "loop": "fail → remedy → score",
        "trail": "logs/failure_kb.jsonl",
        "promote_gate": False,
        "status": "shipped",
        "cli": "main.py fkb",
    },
    {
        "id": "loop_audit",
        "layer": "meta",
        "loop": "trail mine → findings → operator recs",
        "trail": "memory/runs/governor_autorun_trail.jsonl",
        "promote_gate": False,
        "status": "shipped",
        "cli": "main.py loop-audit",
    },
    {
        "id": "verkle",
        "layer": "cold",
        "loop": "audit → gaps → enqueue",
        "trail": "memory/improve/daily/*-verkle-audit.json",
        "promote_gate": False,
        "status": "shipped",
        "cli": "main.py verkle-audit",
    },
    {
        "id": "resonance",
        "layer": "viewport",
        "loop": "soil ↔ frontier → pack L0e",
        "trail": "memory/resonance/findings.jsonl",
        "promote_gate": False,
        "status": "research",
        "cli": "main.py resonance",
    },
    {
        "id": "spider",
        "layer": "meta",
        "loop": "watch → steer → trail",
        "trail": "memory/runs/spider_trail.jsonl",
        "promote_gate": False,
        "status": "research",
        "cli": "main.py spider",
    },
    {
        "id": "conductor",
        "layer": "harness",
        "loop": "route → outcome → train labels",
        "trail": "memory/runs/conductor_trail.jsonl",
        "promote_gate": True,
        "status": "research",
        "cli": "main.py conductor",
    },
    {
        "id": "grove",
        "layer": "warm_mid",
        "loop": "FILE events → poem nodes",
        "trail": "memory/grove/index.jsonl",
        "promote_gate": True,
        "status": "research",
        "cli": "main.py grove-build",
    },
    {
        "id": "factory",
        "layer": "harness",
        "loop": "plan → freeze → build → audit",
        "trail": "memory/runs/build_audit/",
        "promote_gate": True,
        "status": "pilot",
        "cli": "docs/ref/MAG_BUILD_PIPELINE.md",
    },
    {
        "id": "training_events",
        "layer": "cold_edge",
        "loop": "emit → export → republic train",
        "trail": "memory/training/events.jsonl",
        "promote_gate": True,
        "status": "research",
        "cli": "main.py training-events",
    },
    {
        "id": "switchboard",
        "layer": "meta",
        "loop": "mesh → route → steer_drop → reap",
        "trail": "memory/runs/switchboard_trail.jsonl",
        "promote_gate": False,
        "status": "research",
        "cli": "main.py switchboard",
    },
    {
        "id": "releases",
        "layer": "doctrine",
        "loop": "notes → gate → release_milestone",
        "trail": "memory/improve/releases/gates.jsonl",
        "promote_gate": True,
        "status": "shipped",
        "cli": "main.py release",
    },
    {
        "id": "steward",
        "layer": "harness",
        "loop": "scope → digest → one leaf",
        "trail": "memory/steward/",
        "promote_gate": False,
        "status": "pilot",
        "cli": "main.py steward",
    },
    {
        "id": "ilap",
        "layer": "doctrine",
        "loop": "propose → research → aim → eval → freeze → build",
        "trail": "memory/improve/evals/features/",
        "promote_gate": True,
        "status": "pilot",
        "cli": "docs/ref/MAG_ILAP_PROTOCOL.md",
    },
    {
        "id": "research_dive",
        "layer": "viewport",
        "loop": "scout sources → steal compose → one leaf",
        "trail": "memory/research_packs/",
        "promote_gate": True,
        "status": "shipped",
        "cli": "main.py improve / research-pack / field-steal",
    },
    {
        "id": "ghost-session",
        "layer": "harness",
        "loop": "sense_session → match_context → deploy_contextual → measure_goal_effect → catalog",
        "trail": "memory/runs/ghost/",
        "promote_gate": False,
        "status": "pilot",
        "cli": "python -m mag.ghost --session",
        "desc": "Ghost steering with session-state awareness: reads CURRENT.md, briefs, agent_state, coding_session_loop to deploy contextually-relevant steer vectors."
    },
    {
        "id": "framework_map",
        "layer": "meta",
        "loop": "scan → group by function → render → persist",
        "trail": "memory/graph/framework_map.json",
        "promote_gate": False,
        "status": "shipped",
        "cli": "python -m mag.framework_map",
        "desc": "Authoritative functional grouping of the whole framework (Steer/Decide/State/Learn/Run/Ops/Agents/Launch/Routes/Providers) with curated descriptions + examples. Served via GET /api/v1/framework/map; kept fresh by the MAG_MAP_EVERY cadence in governor_autorun."
    },
]


def _trail_exists(path: str) -> bool:
    p = ROOT / path
    if p.is_file():
        return True
    if "*" in path:
        parent = ROOT / path.split("*")[0].rstrip("/")
        return parent.is_dir() and any(parent.iterdir())
    return p.is_dir() and any(p.iterdir()) if path.endswith("/") else False


def build_registry() -> dict[str, Any]:
    loops = []
    for row in LOOPS:
        trail = row.get("trail") or ""
        loops.append({
            **row,
            "trail_on_disk": _trail_exists(trail) if trail else False,
        })
    shipped = sum(1 for r in loops if r.get("status") == "shipped")
    research = sum(1 for r in loops if r.get("status") == "research")
    return {
        "schema": "mag_loops_registry.v1",
        "ts": datetime.now(timezone.utc).isoformat(),
        "loops": loops,
        "summary": {
            "total": len(loops),
            "shipped": shipped,
            "research": research,
            "pilot": sum(1 for r in loops if r.get("status") == "pilot"),
        },
        "law": "Nested loops file to residual; none owns the throne.",
    }


def format_registry_text(reg: dict[str, Any] | None = None) -> str:
    r = reg or build_registry()
    lines = [
        f"# Mag loops registry ({r.get('ts', '')[:19]})",
        "",
        f"Shipped: {r['summary']['shipped']} · Research: {r['summary']['research']} · Pilot: {r['summary']['pilot']}",
        "",
        "| Loop | Status | Trail | Promote gate |",
        "|------|--------|-------|--------------|",
    ]
    for row in r.get("loops") or []:
        tick = "✓" if row.get("trail_on_disk") else "·"
        gate = "L3" if row.get("promote_gate") else "—"
        lines.append(
            f"| {row['id']} | {row.get('status')} | {tick} {row.get('trail', '')[:40]} | {gate} |"
        )
    lines.append("")
    lines.append(r.get("law") or "")
    return "\n".join(lines)
