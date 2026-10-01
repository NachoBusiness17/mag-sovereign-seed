"""Nervous system — agent-operation containment at a glance.

Subsystem (not doctrine): what Mag *contains* and whether the body is alive.
Law: trust glance + doctor JSON, not model memory about keys/online.
Never print secret values.

CLI: python main.py nervous [--json]
Pack: context_pack L0a via pack_excerpt().
Face: memory/nervous_system.md (+ .json)
"""
from __future__ import annotations

import json
import os
import socket
import tempfile
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT

SCHEMA = "nervous_system.v1"
FACE_MD = ROOT / "memory" / "nervous_system.md"
FACE_JSON = ROOT / "memory" / "nervous_system.json"

KEY_NAMES = [
    "OPENROUTER_API_KEY",
    "DEEPSEEK_API_KEY",
    "DEEPSEEK_OVERMIND_API_KEY",
    "GEMINI_API_KEY",
    "XAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "GROQ_API_KEY",
    "TOGETHER_API_KEY",
    "VAST_API_KEY",
    "VAST_OPENAI_API_KEY",
    "VAST_OPENAI_BASE_URL",
]


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dotenv_raw_names() -> set[str]:
    """ALL names present in .env, regardless of whether the value is empty."""
    names: set[str] = set()
    env_path = ROOT / ".env"
    if not env_path.is_file():
        return names
    for line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, _ = line.partition("=")
        k = k.strip()
        if k:
            names.add(k)
    return names


def _dotenv_key_names() -> set[str]:
    """Names in .env with non-empty values only."""
    names: set[str] = set()
    env_path = ROOT / ".env"
    if not env_path.is_file():
        return names
    for line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, val = line.partition("=")
        k = k.strip()
        val = val.strip().strip('"').strip("'")
        if k and val:
            names.add(k)
    return names


def _port_up(host: str, port: int, timeout: float = 0.4) -> bool:
    try:
        s = socket.create_connection((host, port), timeout)
        s.close()
        return True
    except Exception:
        return False


def _ollama_up(timeout: float = 0.8) -> bool:
    try:
        # Use the shared hard-bounded/cached registry probe; a direct urllib
        # call here made every glance vulnerable to host/Docker DNS stalls.
        from models.registry import ollama_tags

        return bool(ollama_tags(timeout=timeout))
    except Exception:
        return False


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _keys_snapshot() -> list[dict[str, Any]]:
    dotenv = _dotenv_key_names()
    raw = _dotenv_raw_names()
    rows: list[dict[str, Any]] = []
    for k in KEY_NAMES:
        in_dotenv = k in dotenv
        in_proc = bool(os.environ.get(k) and str(os.environ.get(k)).strip())
        if in_dotenv and in_proc:
            status = "ok"
        elif in_dotenv and not in_proc:
            status = "env-only"
        elif in_proc:
            status = "process-only"
        elif k in raw:
            # Name present in .env but the value is empty -> actionable,
            # NOT the same as "missing" (key never added at all).
            status = "empty-value"
        else:
            status = "missing"
        rows.append(
            {
                "id": k.replace("_API_KEY", "").lower(),
                "env": k,
                "in_dotenv": in_dotenv,
                "in_process": in_proc,
                "status": status,
                "usable_hint": status in ("ok", "env-only", "process-only"),
            }
        )
    return rows


def _working_open_lines(limit: int = 12) -> list[str]:
    wp = ROOT / "memory" / "working.md"
    if not wp.is_file():
        return []
    out: list[str] = []
    for line in wp.read_text(encoding="utf-8", errors="replace").splitlines():
        s = line.strip()
        if not s.startswith("-"):
            continue
        if any(k in s for k in ("W0", "IJL", "READY", "[PO]", "[open]", "open]")):
            out.append(s[:200])
        if len(out) >= limit:
            break
    return out


def write_face(glance: dict[str, Any]) -> Path:
    """Write human md + machine json."""
    body = glance.get("body") or {}
    tip = glance.get("session_tip") or {}
    atip = glance.get("agent_tip") or {}
    keys = glance.get("keys") or []
    lines = [
        "# Nervous system — at a glance",
        f"_ts: {glance.get('ts')}_",
        f"_ok: body={glance.get('ok')} integral={glance.get('integral_ok')}_",
        "_law: Trust this + doctor JSON, not model memory. Never print key values._",
        "",
        "## Body",
        f"- dashboard :8765: **{'UP' if body.get('dashboard_8765') else 'DOWN'}**",
        f"- ollama :11434: **{'UP' if body.get('ollama_11434') else 'DOWN'}**",
        f"- multi_smoke: **{'PASS' if body.get('multi_smoke_ok') else 'FAIL/unknown'}** "
        f"{body.get('multi_smoke_models')}",
        f"- health.status: `{body.get('health_status')}` live_stale={body.get('live_stale')}",
        "",
        "## Verkle containment",
        f"- session tip: `{(tip.get('root_short') or '')}…` leaves={tip.get('n_leaves')} "
        f"last={tip.get('last_filename')}",
        f"- agent tip: `{(atip.get('root_short') or '')}…` n={atip.get('n_versions')} "
        f"commit={atip.get('commit8')}",
        "",
        "## Keys (presence only)",
        "| provider | .env | process | status |",
        "|----------|------|---------|--------|",
    ]
    for row in keys:
        if not isinstance(row, dict):
            continue
        lines.append(
            f"| {row.get('id')} | {'yes' if row.get('in_dotenv') else 'no'} | "
            f"{'yes' if row.get('in_process') else 'no'} | {row.get('status')} |"
        )
    lines.extend(["", glance.get("note") or "", "", "## Open loops (working.md)", ""])
    for loop in glance.get("open_loops") or []:
        lines.append(f"- {loop}")
    if not glance.get("open_loops"):
        lines.append("- _(none extracted)_")
    dt = glance.get("desk_trust") or {}
    if dt:
        lines.extend(
            [
                "",
                "## Desk trust (baseline)",
                f"- tier: **{dt.get('tier', '?')}** · slow→fast: **{dt.get('slow_to_fast', '?')}**",
                f"- model: `{dt.get('baseline_score', '?')}` · ui_smoke: `{dt.get('ui_smoke_score', '?')}`",
                f"- combined: `{dt.get('combined_score', dt.get('baseline_score', '?'))}` · updated: {dt.get('updated', '?')}",
                "- probe: `python scripts/desk_baseline_probe.py`",
            ]
        )
    al = glance.get("arena_learning") or {}
    if al:
        hint = al.get("routing_hint") or {}
        lines.extend(
            [
                "",
                "## Arena learning (switchboard probes)",
                f"- active game: **{al.get('active_game')}** · seats ranked: **{al.get('n_seats_ranked', 0)}**",
                f"- top seat: **{al.get('top_seat') or '?'}** · value: `{al.get('top_value')}`",
                f"- routing hint: **{hint.get('recommend') or '?'}** — {hint.get('reason') or ''}",
                f"- league: `{al.get('path')}` · probe: `python main.py arena league`",
            ]
        )
    lines.extend(
        [
            "",
            "## Reconnect",
            "```",
            "mag.cmd doctor",
            "docker compose restart mag",
            "mag.cmd nervous",
            "mag.cmd context-pack",
            "```",
            "",
        ]
    )
    FACE_MD.parent.mkdir(parents=True, exist_ok=True)
    FACE_MD.write_text("\n".join(lines), encoding="utf-8")
    # Keep cached reads coherent while a heartbeat refreshes the face.
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=str(FACE_JSON.parent),
        prefix=f".{FACE_JSON.name}.", suffix=".tmp", delete=False,
    ) as fh:
        tmp = Path(fh.name)
        json.dump(glance, fh, indent=2, default=str)
    try:
        os.replace(tmp, FACE_JSON)
    finally:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
    glance["path_md"] = str(FACE_MD)
    glance["path_json"] = str(FACE_JSON)
    return FACE_MD


def glance_cached(*, max_age_s: float = 30.0, refresh: bool = True) -> dict[str, Any]:
    """Return a cached glance if fresh (< max_age_s), else build a fresh one (writes cache).

    HOT-PATH BOUND (2026-08-16): build_glance runs a live probe suite (health.sanity,
    seat_registry live seats, multi_smoke, port probes) that takes ~4.4s. A dashboard /
    status page should NOT re-run that on every request — it made /api/v1/status hang ~8s.
    This returns the last-written face (presence data ≤ max_age_s stale, fine for a status
    read) and only re-probes when the cache has expired. ``refresh=False``
    is for hot observers that must never turn a read into a live probe; they
    receive the last face with an explicit stale marker.
    """
    import time
    try:
        if FACE_JSON.is_file():
            age_s = time.time() - os.path.getmtime(FACE_JSON)
            if age_s < max_age_s or not refresh:
                g = json.loads(FACE_JSON.read_text(encoding="utf-8"))
                g["_cached"] = True
                g["_cache_age_s"] = round(age_s, 1)
                g["_cache_stale"] = age_s >= max_age_s
                return g
    except Exception:
        pass
    if not refresh:
        return {
            "ok": False,
            "schema": SCHEMA,
            "_cached": False,
            "_cache_stale": True,
            "body": {
                "dashboard_8765": False,
                "ollama_11434": False,
                "integral_ok": False,
            },
            "note": "No nervous face receipt exists; live refresh deferred.",
        }
    g = build_glance(write=True)
    g["_cached"] = False
    return g


def build_glance(*, write: bool = True) -> dict[str, Any]:
    """Full nervous glance. Optionally write face files."""
    tip = _read_json(ROOT / "memory" / "biography" / "verkle_tip.json")
    atip = _read_json(ROOT / "memory" / "agent_state" / "tip.json")
    smoke: dict[str, Any] = {}
    try:
        from models.multi_smoke import last_smoke

        smoke = last_smoke() or {}
    except Exception as e:
        smoke = {"ok": None, "error": str(e)}

    health: dict[str, Any] = {}
    try:
        from mag.health import sanity

        s = sanity()
        health = {
            "status": s.get("status"),
            "live_stale": (s.get("recording") or {}).get("live_stale"),
            "port_8765": (s.get("integral") or {}).get("port_8765"),
            "integral_up": (s.get("integral") or {}).get("up"),
        }
    except Exception as e:
        health = {"error": str(e)}

    dash = _port_up("127.0.0.1", 8765)
    ollama = _ollama_up()
    keys = _keys_snapshot()
    open_loops = _working_open_lines()

    seats_summary: dict[str, Any] = {"registered": 0, "stale": 0, "cloud": 0}
    try:
        from mag.seat_registry import list_registered

        live = list_registered(live_only=True)
        seats_summary["registered"] = len(live)
        for s in live:
            if s.get("heartbeat_age_s") is not None and int(s.get("heartbeat_age_s") or 0) > 120:
                seats_summary["stale"] += 1
            if str(s.get("parent") or s.get("source") or "").startswith("cloud") or s.get("mode") == "cloud":
                seats_summary["cloud"] += 1
    except Exception:
        pass

    improve_loop: dict[str, Any] = {}
    try:
        trail_path = ROOT / "memory" / "runs" / "improve_loop_trail.jsonl"
        if trail_path.is_file():
            lines = trail_path.read_text(encoding="utf-8").strip().splitlines()
            if lines:
                last = json.loads(lines[-1])
                improve_loop["last_event"] = last.get("event")
                improve_loop["last_ts"] = last.get("ts")
    except Exception:
        pass

    desk_trust = _read_json(ROOT / "memory" / "working" / "agent_desk_trust_status.json")
    if desk_trust:
        desk_trust = {
            k: desk_trust[k]
            for k in (
                "tier",
                "slow_to_fast",
                "fast_to_fast",
                "baseline_score",
                "ui_smoke_score",
                "combined_score",
                "updated",
            )
            if k in desk_trust
        }

    desk_health: dict[str, Any] | None = None
    try:
        from mag.desk_dialogue import desk_health_check

        desk_health = desk_health_check(auto_heal=write)
    except Exception:
        pass

    bind_info: dict[str, Any] | None = None
    try:
        from config import bind_exposure, read_lab_bind

        pref = read_lab_bind()
        bind_info = bind_exposure(
            host="0.0.0.0" if pref.get("lan") else "127.0.0.1",
            port=8765,
        )
    except Exception:
        pass

    arena_learning: dict[str, Any] | None = None
    try:
        from mag.arena_learning import nervous_glance

        arena_learning = nervous_glance()
    except Exception:
        pass

    body_ok = bool(ollama)
    integral_ok = bool(dash and health.get("status") == "up")

    fs_roots: list[str] = []
    try:
        from config import FS_ROOTS

        fs_roots = [str(p) for p in FS_ROOTS]
    except Exception:
        pass

    glance: dict[str, Any] = {
        "schema": SCHEMA,
        "ts": _utc(),
        "ok": body_ok,
        "integral_ok": integral_ok,
        "body": {
            "dashboard_8765": dash,
            "ollama_11434": ollama,
            "multi_smoke_ok": smoke.get("ok"),
            "multi_smoke_models": smoke.get("models_seen"),
            "health_status": health.get("status"),
            "live_stale": health.get("live_stale"),
        },
        "fs_roots": fs_roots,
        "session_tip": {
            "root": tip.get("root"),
            "root_short": (tip.get("root") or "")[:16] or None,
            "n_leaves": tip.get("n_leaves"),
            "last_filename": tip.get("last_filename"),
            "last_session_id": tip.get("last_session_id"),
        },
        "agent_tip": {
            "root": atip.get("root"),
            "root_short": (atip.get("root") or "")[:16] or None,
            "n_versions": atip.get("n_versions"),
            "commit8": (atip.get("last_content_commit") or "")[:8] or None,
        },
        "keys": keys,
        "open_loops": open_loops,
        "seats": seats_summary,
        "improve_loop": improve_loop,
        "desk_trust": desk_trust or None,
        "desk_health": desk_health,
        "bind": bind_info,
        "arena_learning": arena_learning,
        "note": (
            "Keys: .env presence ≠ shell; Mag loads dotenv. "
            "status=env-only means Mag python can use if values non-empty. "
            "Probe before claim: main.py provider-chat --provider X. "
            "Dashboard down → mag.cmd doctor (venv read, no spawn). "
            "If still dead AND docker works: docker compose restart mag. "
            "Not host python main.py lab."
        ),
        "reconnect": [
            "mag.cmd doctor",
            "docker compose restart mag",
            "mag.cmd nervous",
            "mag.cmd context-pack",
        ],
        "module": "nervous_system",
        "law": "Trust this JSON + doctor; never invent keys/online from chat.",
    }
    if write:
        write_face(glance)
    return glance


def format_glance_text(glance: dict[str, Any] | None = None) -> str:
    g = glance or build_glance(write=True)
    body = g.get("body") or {}
    tip = g.get("session_tip") or {}
    atip = g.get("agent_tip") or {}
    key_bits = []
    for row in g.get("keys") or []:
        if isinstance(row, dict):
            key_bits.append(f"{row.get('id')}={row.get('status')}")
    lines = [
        f"# Mag nervous ({(g.get('ts') or '')[:19]})",
        f"body_ok={g.get('ok')} integral_ok={g.get('integral_ok')}",
        f"dash={'UP' if body.get('dashboard_8765') else 'DOWN'} · "
        f"ollama={'UP' if body.get('ollama_11434') else 'DOWN'} · "
        f"smoke={'PASS' if body.get('multi_smoke_ok') else 'FAIL'}",
        f"session_tip={(tip.get('root_short') or '?')}… leaves={tip.get('n_leaves')}",
        f"agent_tip={(atip.get('root_short') or '?')}… commit={atip.get('commit8')}",
        f"keys: {', '.join(key_bits)}",
        f"fs_roots: {', '.join((g.get('fs_roots') or [])[:4]) or 'Mag only'}",
        f"note: {g.get('note')}",
        f"face: {g.get('path_md') or FACE_MD}",
    ]
    return "\n".join(lines) + "\n"


def pack_excerpt(glance: dict[str, Any] | None = None) -> dict[str, Any]:
    """Compact dict for context_pack L0a."""
    g = glance or build_glance(write=True)
    body = g.get("body") or {}
    key_bits = []
    for row in g.get("keys") or []:
        if isinstance(row, dict):
            key_bits.append(f"{row.get('id')}={row.get('status')}")
    return {
        "schema": SCHEMA,
        "ts": g.get("ts"),
        "ok": g.get("ok"),
        "integral_ok": g.get("integral_ok"),
        "body": body,
        "session_tip": g.get("session_tip"),
        "agent_tip": g.get("agent_tip"),
        "keys_line": ", ".join(key_bits),
        "keys": g.get("keys"),
        "open_loops": (g.get("open_loops") or [])[:6],
        "desk_trust": g.get("desk_trust"),
        "note": g.get("note"),
        "path": str(FACE_MD),
    }


def build_nervous_system_glance() -> dict[str, Any]:
    """Back-compat alias."""
    return build_glance(write=True)
