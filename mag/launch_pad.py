"""Republic launch pad — framework entry for fresh installs (no personal beads yet).

Mag is the private office; Mycelial Republic is the public forkable practice.
This module describes what ships vs what grows at runtime so Office can act as
a launch point for everyone, not an empty error state.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from config import ROOT, republic_constitution


def _on_disk(rel: str) -> bool:
    return (ROOT / rel.replace("\\", "/")).is_file()


def _republic_root() -> Path:
    env = __import__("os").environ.get("MAG_REPUBLIC_ROOT", "").strip()
    if env:
        return Path(env)
    return ROOT.parent / "mycelial-republic"


def build_launch_pad(*, n_sessions: int = 0, ship: str = "OK") -> dict[str, Any]:
    """Payload for Office when framework is ready but personal soil may be empty."""
    republic = _republic_root()
    constitution = republic_constitution()
    framework = [
        {"id": "directives", "path": "memory/operator_directives.md", "label": "Autonomy contract", "ok": _on_disk("memory/operator_directives.md")},
        {"id": "activation", "path": "memory/handoff/ACTIVATION.md", "label": "Any-seat activation card", "ok": _on_disk("memory/handoff/ACTIVATION.md")},
        {"id": "seats", "path": "memory/improve/SEATS.md", "label": "Seat matrix (L0–L3)", "ok": _on_disk("memory/improve/SEATS.md")},
        {"id": "habit", "path": "memory/improve/HABIT.md", "label": "Operator habit loop", "ok": _on_disk("memory/improve/HABIT.md")},
        {"id": "mirror", "path": "memory/improve/MIRROR.md", "label": "Mirror doctrine", "ok": _on_disk("memory/improve/MIRROR.md")},
        {"id": "locus", "path": "memory/locus.md", "label": "Locus (static identity rules)", "ok": _on_disk("memory/locus.md")},
    ]
    framework_ready = all(x["ok"] for x in framework)
    personal_empty = n_sessions <= 0 or ship == "PROVISIONAL"

    rep_docs = [
        ("constitution", republic / "docs" / "CONSTITUTION.md"),
        ("mag_bridge", republic / "docs" / "INST_001_MAG_BRIDGE.md"),
        ("boot_soil", republic / "docs" / "BOOT_SOIL.md"),
    ]
    rep_status = [
        {"id": k, "path": str(p), "ok": p.is_file()}
        for k, p in rep_docs
    ]

    core_ops = [
        {
            "id": "story",
            "label": "Read the framework story (two houses)",
            "kind": "tab",
            "target": "story",
        },
        {
            "id": "context-pack",
            "label": "Build context pack for any seat",
            "kind": "cmd",
            "cmd": "scripts\\mag_exec.ps1 context-pack",
            "cmd_unix": "docker compose exec mag python main.py context-pack",
        },
        {
            "id": "multi-smoke",
            "label": "Run provider smoke (honest health)",
            "kind": "cmd",
            "cmd": "scripts\\mag_exec.ps1 multi-smoke",
            "cmd_unix": "docker compose exec mag python main.py multi-smoke",
        },
        {
            "id": "chat",
            "label": "Chat from filed memory (empty until you file)",
            "kind": "tab",
            "target": "chat",
        },
        {
            "id": "cursor-bridge",
            "label": "Cursor bridge health (host → localhost:8765)",
            "kind": "cmd",
            "cmd": "python watch\\cursor_bridge.py health",
        },
    ]

    onboarding = [
        "Framework ships in the repo — operator directives, seats, activation, Story tab.",
        "Personal day beads are empty until you work and file (residual / summarize-session).",
        "Clone Mycelial Republic beside Mag for the public practice path.",
        "Mag stays private soil; republic stays public — see INST_001_MAG_BRIDGE.",
    ]

    if not republic.is_dir():
        onboarding.append(
            f"Expected republic sibling at {republic} — clone when ready for public practice."
        )

    return {
        "schema": "mag_launch_pad.v1",
        "show": personal_empty or not framework_ready,
        "framework_ready": framework_ready,
        "personal_beads_empty": personal_empty,
        "n_sessions": n_sessions,
        "headline": (
            "Launch point — framework loaded, your beads start empty"
            if personal_empty and framework_ready
            else "Framework incomplete — check seed files"
            if not framework_ready
            else "Office ready"
        ),
        "subtitle": (
            "Mag is everyone's private office. Mycelial Republic is the public fork "
            "after the coding-agent framework is proven. No personal history is required "
            "to start — only to fill Days/Diary with your work."
        ),
        "framework": framework,
        "republic": {
            "detected": republic.is_dir(),
            "root": str(republic),
            "constitution_on_disk": constitution.is_file(),
            "docs": rep_status,
        },
        "core_ops": core_ops,
        "onboarding": onboarding,
        "docs": {
            "container": "docs/CONTAINER.md",
            "story_api": "/api/v1/story",
            "republic_launch": "memory/boot/REPUBLIC_LAUNCH.md",
        },
    }
