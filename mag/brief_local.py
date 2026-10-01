"""Local brief from session dossier/md — cheap cycles, preserve Grok usage."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT
from mag.lanes import briefs_dir, log_usage


BIO = ROOT / "memory" / "biography"


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def resolve_session_id(session_id: str | None = None) -> str | None:
    if session_id and session_id != "latest":
        return session_id
    try:
        from mag.registry import get_latest_session_id, list_registry

        sid = get_latest_session_id()
        if sid:
            return sid
        rows = list_registry(limit=1)
        if rows:
            return str(rows[0].get("session_id") or "") or None
    except Exception:
        pass
    d = _read_json(BIO / "latest.dossier.json")
    if d and d.get("session_id"):
        return str(d["session_id"])
    residual = BIO / "residual"
    if residual.is_dir():
        files = sorted(residual.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        if files:
            return files[0].stem
    return None


def collect_source(session_id: str) -> dict[str, Any]:
    d = None
    try:
        from mag.registry import find_derived, load_residual

        d = load_residual(session_id)
        md_p = find_derived(session_id, "md")
        md = md_p.read_text(encoding="utf-8", errors="replace") if md_p else ""
    except Exception:
        md = ""
    if not d:
        d = _read_json(BIO / f"{session_id}.dossier.json") or _read_json(
            BIO / "latest.dossier.json"
        )
    if not md:
        md_path = BIO / f"{session_id}.md"
        md = md_path.read_text(encoding="utf-8", errors="replace") if md_path.is_file() else ""
    if not md and (BIO / "latest.md").is_file():
        md = (BIO / "latest.md").read_text(encoding="utf-8", errors="replace")
    return {"session_id": session_id, "dossier": d or {}, "narrative_md": md}


def _heuristic_brief(src: dict[str, Any]) -> str:
    d = src.get("dossier") or {}
    sid = src.get("session_id") or "?"
    time = d.get("time") or {}
    chord = d.get("chord") or {}
    sk = d.get("scalar_knot") or {}
    lay = d.get("steiniger_laymen") or {}
    title = time.get("title") or chord.get("plain_english") or sid
    themes = (sk.get("theme_vector") or {}).get("dominant") or "—"
    moves = chord.get("disentangled_moves") or lay.get("good_moves") or []
    loops = chord.get("loops_audited") or []
    residual = lay.get("residual_bonds") or []
    tension = lay.get("tension") or [chord.get("rope")]
    lines = [
        f"# Brief · {sid[:13]}…",
        "",
        f"- **title:** {title}",
        f"- **when:** {(time.get('created_at') or {}).get('iso_minute')} → {(time.get('updated_at') or {}).get('iso_minute')}",
        f"- **dominant theme:** {themes}",
        f"- **tension_index:** {sk.get('tension_index')}",
        f"- **commitment:** {chord.get('commitment_hash') or '—'}",
        f"- **recommended_lane:** L0 (local) unless tagged [priority]/[grok]",
        "",
        "## What was turned",
        chord.get("plain_english") or d.get("tldr") or (src.get("narrative_md") or "")[:600] or "—",
        "",
        "## Personal impact",
        chord.get("personal_impact") or "—",
        "",
        "## Rope / tension",
        "\n".join(f"- {t}" for t in (tension if isinstance(tension, list) else [tension]) if t) or "—",
        "",
        "## Open loops",
        "\n".join(
            f"- {L.get('id') if isinstance(L, dict) else L}: "
            f"{L.get('plain') if isinstance(L, dict) else ''}"
            for L in loops[:8]
        )
        or "—",
        "",
        "## Residual bonds",
        "\n".join(f"- {r}" for r in residual[:8]) or "—",
        "",
        "## Next moves (local first)",
        "\n".join(f"- {m}" for m in moves[:8]) or "- Re-read this brief before new epics.",
        "",
        "## Escalate to Grok only if",
        "- Hard architecture / multi-file design you cannot settle locally",
        "- Explicit `[priority]` or `[grok]` on the todo",
        "- Daily L2 budget remains",
        "",
        f"_Generated {datetime.now(timezone.utc).isoformat()} · lane L0 · not a full mirror_",
    ]
    return "\n".join(lines)


def _llm_polish(heuristic: str, src: dict[str, Any]) -> str:
    try:
        from llm import chat
    except Exception:
        return heuristic
    system = (
        "You are Mag biographer clerk (local). Compress the session into a short operator brief. "
        "Preserve facts. Prefer local next steps. Only recommend Grok escalate if truly hard. "
        "Plain markdown. No flattery. No new throne."
    )
    user = f"""Source brief (heuristic) and raw extract. Rewrite cleaner, keep structure.

HEURISTIC:
{heuristic[:3500]}

NARRATIVE (clip):
{(src.get('narrative_md') or '')[:2000]}
"""
    try:
        out = chat("worker", system, user, temperature=0.15)
        if out and len(out.strip()) > 80:
            return out.strip()
    except Exception:
        pass
    return heuristic


def write_brief(
    session_id: str | None = None,
    *,
    use_llm: bool = True,
    write_visual: bool = False,
) -> dict[str, Any]:
    # P0-1 warm-face law (2026-09-26): a FROZEN as-of banner on latest.md is
    # deliberate residual. Do not overwrite it with a session-bio fossil that
    # wears today's Generated stamp (the lie Elder named). Force requires
    # operator unfreeze (delete/edit the FROZEN header) first.
    latest_probe = briefs_dir() / "latest.md"
    if latest_probe.is_file():
        head = latest_probe.read_text(encoding="utf-8", errors="replace")[:240]
        if head.lstrip("\ufeff").startswith("# FROZEN"):
            return {
                "ok": False,
                "error": "latest.md is FROZEN; refuse overwrite (P0-1 warm-face)",
                "latest": str(latest_probe),
                "frozen": True,
            }
    sid = resolve_session_id(session_id)
    if not sid:
        return {"ok": False, "error": "no session dossier found"}
    src = collect_source(sid)
    if not src.get("dossier") and not src.get("narrative_md"):
        return {"ok": False, "error": f"empty sources for {sid}", "session_id": sid}

    text = _heuristic_brief(src)
    used_llm = False
    if use_llm:
        polished = _llm_polish(text, src)
        if polished != text:
            used_llm = True
            text = polished

    bdir = briefs_dir()
    out_path = bdir / f"{sid}.md"
    latest = bdir / "latest.md"
    out_path.write_text(text, encoding="utf-8")
    latest.write_text(text, encoding="utf-8")
    meta = {
        "session_id": sid,
        "path": str(out_path),
        "latest": str(latest),
        "used_llm": used_llm,
        "chars": len(text),
    }
    log_usage(
        lane="L0",
        action="brief",
        detail=f"session={sid[:13]} llm={used_llm}",
        ok=True,
        meta=meta,
    )
    # Residual bonds: refresh first-class next-session pack
    bonds_meta: dict[str, Any] = {}
    try:
        from mag.bonds import ingest_bonds

        bonds_meta = ingest_bonds(session_id=sid, write=True)
    except Exception as e:
        bonds_meta = {"ok": False, "error": str(e)}
    # Visual is export-layer only (default off)
    vis_meta: dict[str, Any] = {"ok": True, "skipped": True, "reason": "export_on_demand"}
    if write_visual:
        try:
            from mag.visual_pack import write_visual_pack

            vis_meta = write_visual_pack(sid)
        except Exception as e:
            vis_meta = {"ok": False, "error": str(e)}
    return {"ok": True, **meta, "preview": text[:500], "visual": vis_meta, "bonds": bonds_meta}
