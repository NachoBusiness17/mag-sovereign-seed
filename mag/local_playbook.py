"""Local playbooks — frontier-authored rules of the game for L0 execution.

Chess worked when Local had: rules + history + legal moves + one output shape.
Playbooks generalize that to desk, code scout, archivist, routing.

Schema: local_playbooks.v1
Artifacts: memory/training/local_playbooks/*.json (teacher-authored overrides)
Config: configs/local_playbooks.yaml
"""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from config import ROOT

CFG = ROOT / "configs" / "local_playbooks.yaml"
ARTIFACT_DIR = ROOT / "memory" / "training" / "local_playbooks"
TRAIL = ROOT / "memory" / "runs" / "local_playbook_trail.jsonl"
SCHEMA = "local_playbooks.v1"


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _trail(event: str, **fields: Any) -> None:
    TRAIL.parent.mkdir(parents=True, exist_ok=True)
    row = {"ts": _utc(), "event": event, **fields}
    with TRAIL.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def _load_cfg() -> dict[str, Any]:
    if not CFG.is_file():
        return {"playbooks": {}, "defaults": {}}
    try:
        return yaml.safe_load(CFG.read_text(encoding="utf-8")) or {"playbooks": {}}
    except Exception:
        return {"playbooks": {}, "defaults": {}}


def list_playbooks() -> dict[str, Any]:
    cfg = _load_cfg()
    items = []
    for pid, meta in (cfg.get("playbooks") or {}).items():
        if isinstance(meta, dict):
            items.append({"id": pid, **meta})
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    for p in sorted(ARTIFACT_DIR.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True)[:20]:
        try:
            row = json.loads(p.read_text(encoding="utf-8"))
            row["source"] = "teacher"
            items.append(row)
        except (OSError, json.JSONDecodeError):
            continue
    return {"ok": True, "schema": SCHEMA, "playbooks": items, "defaults": cfg.get("defaults") or {}}


def get_playbook(playbook_id: str) -> dict[str, Any]:
    """Resolve playbook — teacher artifact overrides static config."""
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    for p in ARTIFACT_DIR.glob("*.json"):
        try:
            row = json.loads(p.read_text(encoding="utf-8"))
            if row.get("id") == playbook_id or row.get("playbook_id") == playbook_id:
                return {"id": playbook_id, "source": "teacher", **row}
        except (OSError, json.JSONDecodeError):
            continue
    cfg = _load_cfg()
    meta = (cfg.get("playbooks") or {}).get(playbook_id) or {}
    if not isinstance(meta, dict):
        meta = {}
    return {"id": playbook_id, "source": "config", **meta}


def default_for_surface(surface: str) -> str:
    cfg = _load_cfg()
    defaults = cfg.get("defaults") or {}
    return str(defaults.get(surface) or "desk_canvas_commit")


def _format_context(playbook: dict[str, Any], ctx: dict[str, Any]) -> str:
    keys = playbook.get("context_keys") or []
    blocks: list[str] = []
    for key in keys:
        val = ctx.get(key)
        if val is None or val == "" or val == []:
            continue
        if isinstance(val, (list, tuple)):
            text = ", ".join(str(x) for x in val[:40])
        elif isinstance(val, dict):
            text = json.dumps(val, ensure_ascii=False)[:1200]
        else:
            text = str(val)[:2000]
        blocks.append(f"### {key}\n{text}")
    return "\n\n".join(blocks)


def build_local_prompt(
    *,
    playbook_id: str,
    ctx: dict[str, Any],
    base: str = "",
) -> str:
    """Assemble L0 prompt: rules + bounded context + output contract."""
    pb = get_playbook(playbook_id)
    rules = (pb.get("rules") or "").strip()
    out = pb.get("output") or {}
    context_block = _format_context(pb, ctx)
    parts = [
        f"## Playbook · {pb.get('label') or playbook_id}",
        f"Role: {pb.get('role') or 'agent'} · Domain: {pb.get('domain') or 'general'}",
        "",
        "### Rules",
        rules or "(no rules)",
    ]
    if context_block:
        parts.extend(["", "## Context (look here only)", context_block])
    if out:
        parts.extend(
            [
                "",
                "### Output contract",
                f"Kind: {out.get('kind') or '?'} · Format: {out.get('format') or '?'}",
                "One response only. Stay inside the contract.",
            ]
        )
    if base.strip():
        parts.extend(["", "## Task", base.strip()])
    return "\n".join(parts)


def validate_output(
    playbook_id: str,
    raw: str,
    *,
    ctx: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate L0 output against playbook contract — like legal_moves for chess."""
    pb = get_playbook(playbook_id)
    out = pb.get("output") or {}
    fmt = str(out.get("format") or "")
    text = (raw or "").strip()
    ctx = ctx or {}

    if fmt == "san_chess":
        legal = ctx.get("legal_moves") or []
        from mag.desk_local_adapter import extract_move_line

        pick = extract_move_line(text) or text.split()[0] if text else ""
        ok = bool(pick) and (not legal or pick in legal or any(pick in m for m in legal))
        return {"ok": ok, "format": fmt, "parsed": pick, "legal": legal[:20]}

    if fmt == "move_line_or_one_paragraph":
        from mag.desk_local_adapter import canvas_quality, extract_move_line

        q = canvas_quality(text)
        has_move = bool(extract_move_line(text))
        ok = q in ("move", "prose") and q != "heading_only" and q != "empty"
        return {"ok": ok, "format": fmt, "quality": q, "has_move": has_move}

    if fmt in ("scout_report", "filing_block", "route_scout"):
        ok = len(text) >= 20 and "##" in text
        return {"ok": ok, "format": fmt, "lines": len(text.splitlines())}

    return {"ok": bool(text), "format": fmt or "text"}


def save_teacher_playbook(
    *,
    playbook_id: str,
    parsed: dict[str, Any],
    teacher: str = "deepseek",
    domain: str = "",
) -> dict[str, Any]:
    """Persist frontier-authored playbook override."""
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    pid = playbook_id or f"pb-{uuid.uuid4().hex[:10]}"
    artifact = {
        "schema": SCHEMA,
        "id": pid,
        "playbook_id": pid,
        "ts": _utc(),
        "source": "teacher",
        "teacher": {"seat": teacher},
        "student": {"seat": "local"},
        "domain": domain or parsed.get("domain"),
        "label": parsed.get("label") or pid,
        "role": parsed.get("role") or "agent",
        "context_keys": parsed.get("context_keys") or [],
        "rules": parsed.get("rules") or "",
        "output": parsed.get("output") or {"kind": "structured", "format": "text"},
        "exportable": True,
        "republic_tags": ["local_playbook", domain or "general"],
    }
    path = ARTIFACT_DIR / f"{pid}.json"
    path.write_text(json.dumps(artifact, indent=2, ensure_ascii=False), encoding="utf-8")
    artifact["path"] = str(path.relative_to(ROOT)).replace("\\", "/")
    _trail("playbook_filed", playbook_id=pid, domain=domain)
    try:
        from mag.training_events import emit

        emit(
            "desk_teaching",
            join={"skill_id": pid, "session_id": "local-playbook"},
            input_data={"domain": domain, "playbook_id": pid},
            action={"teacher": teacher, "artifact_path": artifact["path"]},
            outcome={"role": artifact.get("role"), "format": (artifact.get("output") or {}).get("format")},
            pattern_tags=["local_playbook", domain or "general"],
            tier_max="T2",
        )
    except Exception:
        pass
    return artifact


def _parse_teacher_playbook_response(raw: str, *, domain: str, goal: str) -> dict[str, Any]:
    text = (raw or "").strip()

    def _sec(name: str) -> str:
        m = re.search(rf"###\s*{re.escape(name)}\s*\n([\s\S]*?)(?=###\s|\Z)", text, re.I)
        return (m.group(1).strip() if m else "")[:3000]

    rules = _sec("Rules") or _sec("rules")
    ctx_raw = _sec("Context keys") or _sec("Context")
    out_raw = _sec("Output format") or _sec("Output")
    context_keys = [k.strip() for k in re.split(r"[,·\n]", ctx_raw) if k.strip()][:12]
    fmt = "structured"
    if "san" in out_raw.lower() or "chess" in domain.lower():
        fmt = "san_chess"
    elif "canvas" in out_raw.lower() or "desk" in domain.lower():
        fmt = "move_line_or_one_paragraph"
    elif "archivist" in domain.lower() or "file" in domain.lower():
        fmt = "filing_block"
    elif "code" in domain.lower() or "scout" in domain.lower():
        fmt = "scout_report"
    role = "archivist" if "archivist" in domain.lower() else (
        "coding_agent_l0" if "code" in domain.lower() else "steering_agent"
    )
    return {
        "domain": domain,
        "label": f"{domain} · taught",
        "role": role,
        "context_keys": context_keys or ["goal", "board_tail"],
        "rules": rules or text[:1500],
        "output": {"kind": "structured", "format": fmt, "max_tokens": 384},
        "goal": goal[:300],
    }


def frontier_author_playbook(
    *,
    domain: str,
    goal: str,
    playbook_id: str = "",
) -> dict[str, Any]:
    """DeepSeek authors rules of the game — proactive teach, not failure troubleshoot."""
    cfg = _load_cfg()
    tpl = str(cfg.get("teacher_prompt") or "").strip()
    prompt = tpl.format(domain=domain, goal=goal[:500]) if "{domain}" in tpl else (
        f"Author local playbook for domain={domain} goal={goal}\n"
        "### Rules\n### Context keys\n### Output format\n### Drill"
    )
    try:
        from models.providers import chat_messages

        res = chat_messages(
            "deepseek",
            [
                {
                    "role": "system",
                    "content": "You teach L0 the rules of a bounded game. No implementation — playbook only.",
                },
                {"role": "user", "content": prompt},
            ],
            tools=None,
            tier="T2",
            max_tokens=900,
        )
        if not res.get("ok"):
            return {"ok": False, "error": res.get("error") or "teacher failed"}
        raw = (res.get("text") or "").strip()
        parsed = _parse_teacher_playbook_response(raw, domain=domain, goal=goal)
        pid = (playbook_id or "").strip() or re.sub(
            r"[^a-z0-9]+", "_", domain.lower()
        ).strip("_")[:32]
        artifact = save_teacher_playbook(playbook_id=pid, parsed=parsed, domain=domain)
        return {
            "ok": True,
            "playbook": artifact,
            "prompt_preview": build_local_prompt(playbook_id=pid, ctx={"goal": goal}, base=goal),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:200]}


def augment_arena_prompt(base: str, *, state: dict[str, Any], seat: str) -> str:
    """Chess seat — playbook + strategy + legal moves context."""
    pb_id = (state.get("playbook") or {}).get("id") or default_for_surface("arena")
    history = state.get("move_history") or []
    ctx = {
        "fen": state.get("fen") or "",
        "legal_moves": state.get("legal_moves") or [],
        "move_history": [f"{m.get('san')} ({m.get('seat')})" for m in history[-12:]],
        "turn_seat": seat,
    }
    prompt = build_local_prompt(playbook_id=pb_id, ctx=ctx, base=base)
    try:
        from mag.arena_strategies import augment_move_prompt, strategy_for_game_state

        strat = strategy_for_game_state(state, seat)
        prompt = augment_move_prompt(prompt, strategy=strat)
    except Exception:
        pass
    return prompt
