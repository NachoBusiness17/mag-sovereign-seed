"""Session biographer — FILE any seat's chat into residual DNA + Verkle leaves.

Source-agnostic: Grok TUI, Mag agent CLI, or any path the chat_source adapter resolves.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT
from mag.chat_source import (
    SOURCE_MAG_AGENT,
    extract_turns as _extract_turns_agnostic,
    resolve_chat,
)

BIO_DIR = ROOT / "memory" / "biography"
INDEX = BIO_DIR / "index.jsonl"
LATEST = BIO_DIR / "latest.md"
SUMMARIZED = ROOT / "watch" / "summarized_sessions.json"


def _find_chat(session_id: str, cwd: str | None = None) -> Path | None:
    """Back-compat: first Grok (or auto) transcript path for session_id."""
    ref = resolve_chat(session_id, cwd=cwd, source="auto")
    return ref.path if ref else None


def _extract_turns(path: Path, max_lines: int = 4000) -> dict[str, Any]:
    """Back-compat wrapper — prefer chat_source.extract_turns."""
    return _extract_turns_agnostic(path, max_lines=max_lines)


def _heuristic_summary(sid: str, turns: dict[str, Any]) -> str:
    users = turns.get("user") or []
    assts = turns.get("assistant") or []
    tools = turns.get("tools") or []
    reasons = turns.get("reasoning") or []

    # themes from paths/keywords
    blob = " ".join(users[-10:] + assts[-8:] + tools[-20:]).lower()
    themes = []
    for label, keys in [
        ("local Mag / agent", ["mag", "ollama", "langgraph", "local_sovereign"]),
        ("scrum / planning", ["scrum", "backlog", "sprint", "ticket"]),
        ("constitution / law", ["constitution", "lessig", "tier"]),
        ("mirror / chord", ["chord", "mirror", "locus", "sovereign"]),
        ("dashboard / instrument", ["dashboard", "sovereign-mirror-scaffold"]),
        ("handoff / harness", ["handoff", "harness", "grok -p"]),
        ("biography / watch", ["biograph", "live_from_grok", "watch"]),
    ]:
        if any(k in blob for k in keys):
            themes.append(label)

    files = sorted(set(re.findall(r"[A-Za-z0-9_./\\-]+\.(?:md|py|json|yaml|yml|txt)", blob)))[:20]

    source = str(turns.get("source") or "unknown")
    source_note = {
        "mag_agent": "Mag agent seat (provider-agnostic tool loop)",
        "grok": "Grok TUI",
    }.get(source, source)
    provider = turns.get("provider")
    model = turns.get("model")
    seat_line = f"- **seat:** `{source_note}`"
    if provider:
        seat_line += f" · provider `{provider}`"
    if model:
        seat_line += f" · model `{model}`"

    lines = [
        f"# Session summary",
        f"",
        f"- **session:** `{sid}`",
        seat_line,
        f"- **ended:** {datetime.now(timezone.utc).isoformat()}",
        f"- **source lines scanned:** {turns.get('line_count')}",
        f"- **themes:** {', '.join(themes) or '(unclear — see digests)'}",
        f"",
        f"## What you were working on",
        f"",
    ]
    if users:
        lines.append("Operator prompts (sample, latest first):")
        for u in reversed(users[-8:]):
            lines.append(f"- {u[:350]}")
    else:
        lines.append("_No clear user prompts extracted; session may be tool-heavy._")
    lines.extend(["", "## What the agent did (sample)", ""])
    if assts:
        for a in reversed(assts[-6:]):
            lines.append(f"- {a[:350]}")
    else:
        lines.append("_Sparse assistant text in extract._")
    if reasons:
        lines.extend(["", "## Reasoning snippets", ""])
        for r in reversed(reasons[-5:]):
            lines.append(f"- {r[:280]}")
    if files:
        lines.extend(["", "## Paths touched (heuristic)", ""])
        for f in files[:15]:
            lines.append(f"- `{f}`")
    lines.extend(
        [
            "",
            "## Open loops (heuristic)",
            "",
            "- Re-read this summary next session before inventing new epics.",
            "- Check `scrum/sprints/current/board.md` if republic work was in flight.",
            (
                "- Full transcript: `memory/agent_sessions/<seat>.json` (Mag agent)."
                if source == SOURCE_MAG_AGENT
                else "- Full transcript still in `~/.grok/sessions/.../chat_history.jsonl`."
            ),
            "",
            "## Intent (best guess)",
            "",
            _intent_guess(themes, users, assts),
            "",
            "---",
            "_Written by Mag biographer (local, seat-agnostic). Not full chord mode._",
            "",
        ]
    )
    return "\n".join(lines)


def _intent_guess(themes: list[str], users: list[str], assts: list[str]) -> str:
    if not themes and not users:
        return "Unclear — log extract was thin."
    t = ", ".join(themes) if themes else "general build work"
    last_u = users[-1][:200] if users else ""
    return (
        f"You were driving **{t}**. "
        f"Latest ask flavor: “{last_u}…” " if last_u else f"You were driving **{t}**."
    ) + " Mag/hands and product/mirror layers may have been mixed — prefer re-centering on the stated goal before next sprint."


def _llm_polish(sid: str, draft: str, turns: dict[str, Any]) -> str | None:
    """Optional Ollama rewrite into tighter biographer voice."""
    try:
        from llm import chat
    except Exception:
        return None
    user_sample = "\n".join(f"- {u}" for u in (turns.get("user") or [])[-12:])
    asst_sample = "\n".join(f"- {a}" for a in (turns.get("assistant") or [])[-8:])
    source = str(turns.get("source") or "session")
    prompt = f"""You are a session biographer for one operator. Summarize THIS work session (seat={source}).

Session id: {sid}


User prompts (samples):
{user_sample}

Assistant outcomes (samples):
{asst_sample}

Draft notes:
{draft[:6000]}

Write markdown with exactly these sections:
## What you were working on
## Decisions / turns
## What you seemed to be thinking (intent)
## Files / systems touched
## Open loops for next time

Truth only. No flattery. 400-800 words max. No claim you are conscious.
"""
    try:
        out = chat(
            "biographer",
            "You write session biographies for later recall. Plain English. Personal impact if clear.",
            prompt,
            temperature=0.2,
        )
        if out and len(out.strip()) > 120:
            return (
                f"# Session summary\n\n"
                f"- **session:** `{sid}`\n"
                f"- **ended:** {datetime.now(timezone.utc).isoformat()}\n"
                f"- **mode:** llm+heuristic\n\n"
                f"{out.strip()}\n"
            )
    except Exception:
        return None
    return None


def _load_summarized() -> dict[str, Any]:
    if not SUMMARIZED.is_file():
        return {"ids": [], "sessions": {}}
    try:
        data = json.loads(SUMMARIZED.read_text(encoding="utf-8"))
        if "sessions" not in data or not isinstance(data.get("sessions"), dict):
            data["sessions"] = {}
        return data
    except (json.JSONDecodeError, OSError):
        return {"ids": [], "sessions": {}}


def already_summarized(session_id: str) -> bool:
    data = _load_summarized()
    if session_id in (data.get("ids") or []):
        return True
    return session_id in (data.get("sessions") or {})


def mark_summarized(
    session_id: str,
    *,
    chat_mtime: float | None = None,
    line_count: int | None = None,
    amended: bool = False,
) -> None:
    SUMMARIZED.parent.mkdir(parents=True, exist_ok=True)
    data = _load_summarized()
    ids = list(data.get("ids") or [])
    if session_id not in ids:
        ids.append(session_id)
    data["ids"] = ids[-200:]
    sessions = dict(data.get("sessions") or {})
    prev = dict(sessions.get(session_id) or {})
    sessions[session_id] = {
        **prev,
        "chat_mtime": chat_mtime,
        "line_count": line_count,
        "updated": datetime.now(timezone.utc).isoformat(),
        "amended": amended or bool(prev),
        "amend_count": int(prev.get("amend_count") or 0) + (1 if amended or prev else 0),
    }
    # cap session map size
    if len(sessions) > 200:
        # keep newest by updated
        ordered = sorted(
            sessions.items(),
            key=lambda kv: str((kv[1] or {}).get("updated") or ""),
            reverse=True,
        )[:200]
        sessions = dict(ordered)
    data["sessions"] = sessions
    data["updated"] = datetime.now(timezone.utc).isoformat()
    SUMMARIZED.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _session_meta(session_id: str) -> dict[str, Any]:
    return dict((_load_summarized().get("sessions") or {}).get(session_id) or {})


def export_session_artifacts(
    session_id: str,
    *,
    pdf: bool = True,
    visual: bool = False,
) -> dict[str, Any]:
    """On-demand human render layer from existing residual (no re-summarize required).

    PDF/charts/visual packs are stickers — not DNA.
    """
    if not session_id:
        return {"ok": False, "error": "no session_id"}
    try:
        from mag.registry import find_derived, load_residual
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}

    dossier = load_residual(session_id)
    if not dossier:
        return {"ok": False, "error": "residual not found", "session_id": session_id}

    out: dict[str, Any] = {
        "ok": True,
        "session_id": session_id,
        "layer": "export",
        "pdf": None,
        "visual": None,
    }

    if pdf:
        try:
            from mag.session_dossier import render_pdf, write_dossier_assets

            assets = write_dossier_assets(session_id, dossier)
            path = render_pdf(session_id, dossier, assets)
            from mag.registry import write_derived_pdf_bytes

            write_derived_pdf_bytes(session_id, path.read_bytes(), also_flat=False)
            out["pdf"] = {
                "ok": True,
                "path": str(path),
                "url": f"/files/biography/derived/{session_id}.pdf",
            }
        except Exception as e:
            out["pdf"] = {"ok": False, "error": str(e)[:300]}
            out["ok"] = False

    if visual:
        try:
            from mag.visual_pack import write_visual_pack

            vm = write_visual_pack(session_id)
            out["visual"] = vm
            if not vm.get("ok"):
                out["ok"] = False
        except Exception as e:
            out["visual"] = {"ok": False, "error": str(e)[:300]}
            out["ok"] = False

    # existence flags after export
    out["has_pdf"] = find_derived(session_id, "pdf") is not None
    out["has_visual"] = find_derived(session_id, "visual_pack") is not None
    return out


def pack_status(
    session_id: str,
    *,
    registry_map: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Lean complete = residual + card + content_commit + chain leaf.

    PDF / visual / md are derived (optional), not required for complete.
    """
    if not session_id:
        return {"ok": False, "complete": False, "missing": ["session_id"]}
    try:
        from mag.registry import lean_pack_status

        st = lean_pack_status(session_id, registry_map=registry_map)
        # aliases for older callers
        st["has_dossier"] = st.get("has_residual")
        st["has_leaf"] = st.get("has_leaf")
        return st
    except Exception as e:
        return {
            "ok": False,
            "session_id": session_id,
            "complete": False,
            "missing": ["lean_status_error"],
            "error": str(e)[:200],
        }


def ping_session_record(
    *,
    sid: str,
    seat: str,
    narrative: str,
    pack: dict[str, Any],
    exists: bool,
    force: bool,
    incomplete: bool,
) -> dict[str, Any]:
    """Operator attention ping that a session narrative exists.

    Ping policy: only on first write, force, or incomplete (amend pings are
    noise). 2026-09-29 gala wave5 attention-channel: routed through the shared
    attention contract in mag/act.py (evict_for_prepend) so this newest-first
    record flood can no longer evict the preserved alert tail -- the old
    `note + prev[:40000]` behead destroyed the 2026-09-26 COLLECT-DRIFT and
    2026-09-28 fleet-task-doctor patrol alerts within hours of their append
    (watch/inbox/burn_reset_20260927/flash50/w4-09.md). Records now evict
    whole-block, each ping carries a ts line, and the flood meters itself into
    the daily attention counter (emission parity: the unmetered writer was the
    survivor; w4-37 law A1/A3).
    """
    if exists and not force and not incomplete:
        return {"pinged": False}
    from mag.act import bump_attention_count, evict_for_prepend

    att = ROOT / "memory" / "attention.md"
    pdf_line = f"- pdf: `{pack.get('pdf')}`\n" if pack.get("pdf") else ""
    json_line = (
        f"- dossier: `{pack.get('dossier_json')}`\n" if pack.get("dossier_json") else ""
    )
    err_line = f"- pdf_error: {pack.get('pdf_error')}\n" if pack.get("pdf_error") else ""
    note = (
        f"\n---\n\n### Session record ready ({'first' if not exists else 'amended'})\n\n"
        f"- ts: {datetime.now(timezone.utc).isoformat()}\n"
        f"- session: `{sid}`\n"
        f"- seat: `{seat}`\n"
        f"- narrative: `{narrative}`\n"
        f"{pdf_line}{json_line}{err_line}"
        f"- also: `memory/biography/latest.md` · brief under `memory/briefs/`\n\n"
    )
    prev = att.read_text(encoding="utf-8") if att.is_file() else "# Mag attention\n"
    att.write_text(evict_for_prepend(prev, note, 40000), encoding="utf-8")
    _day, count = bump_attention_count()
    return {"pinged": True, "path": str(att), "attention_count_today": count}


def summarize_session(
    session_id: str,
    *,
    cwd: str | None = None,
    chat_path: Path | None = None,
    source: str | None = None,
    use_llm: bool = True,
    force: bool = False,
    pdf: bool = False,
    visual: bool = False,
    amend: bool = True,
) -> dict[str, Any]:
    """Write or amend residual DNA for this session_id.

    Always (lean): residual + card + content_commit + chain leaf (+ md narrative).
    Optional export layer (only if requested): pdf, visual_pack, chart assets.

    Seat-agnostic: pass source=grok|mag_agent|auto, or chat_path to any transcript.

    Skip only when chat is unchanged **and** pack is already complete — unless force=True.
    Incomplete packs are always filled (even if mtime matches).
    """
    if not session_id and not chat_path:
        return {"ok": False, "error": "no session_id"}

    ref = resolve_chat(
        session_id or "",
        source=source,
        cwd=cwd,
        chat_path=chat_path,
    )
    if not ref:
        return {
            "ok": False,
            "error": f"chat transcript not found for {session_id!r} (source={source or 'auto'})",
        }

    sid = ref.session_id
    path = ref.path

    try:
        chat_mtime = path.stat().st_mtime
    except OSError:
        chat_mtime = None

    turns = _extract_turns_agnostic(path, source=ref.source)
    turns["source"] = ref.source
    if ref.provider:
        turns["provider"] = ref.provider
    if ref.model:
        turns["model"] = ref.model
    if ref.local_id:
        turns["local_session_id"] = ref.local_id

    line_count = int(turns.get("line_count") or 0)
    exists = already_summarized(sid) or (BIO_DIR / f"{sid}.md").is_file()
    meta = _session_meta(sid)
    status = pack_status(sid)
    incomplete = not status.get("complete")

    # unchanged chat → no rewrite (anti-bloat) — but only if pack is complete
    if (
        exists
        and not force
        and not incomplete
        and meta.get("chat_mtime") is not None
        and chat_mtime is not None
        and float(meta["chat_mtime"]) == float(chat_mtime)
        and meta.get("line_count") == line_count
    ):
        return {
            "ok": True,
            "skipped": True,
            "reason": "unchanged",
            "session_id": sid,
            "source": ref.source,
            "amended": False,
            "pack": status,
        }

    # Old behavior: skip forever after first summarize — replaced by amend-in-place
    if exists and not amend and not force and not incomplete:
        return {
            "ok": True,
            "skipped": True,
            "session_id": sid,
            "source": ref.source,
            "amended": False,
            "pack": status,
        }

    draft = _heuristic_summary(sid, turns)
    body = draft
    mode = "heuristic"
    if use_llm:
        polished = _llm_polish(sid, draft, turns)
        if polished:
            body = polished
            mode = "llm"

    BIO_DIR.mkdir(parents=True, exist_ok=True)
    # derived narrative (also mirrored flat for links)
    try:
        from mag.registry import write_derived_md

        out_path = write_derived_md(sid, body)
    except Exception:
        out_path = BIO_DIR / f"{sid}.md"
        out_path.write_text(body, encoding="utf-8")
        LATEST.write_text(body, encoding="utf-8")

    # residual + leaf always; PDF/assets only when requested (export layer)
    pack: dict[str, Any] = {}
    try:
        from mag.session_dossier import write_session_pack

        pack = write_session_pack(
            sid,
            turns,
            body,
            mode=mode,
            use_llm=use_llm,
            chat_path=path,
            amend=exists,
            write_pdf=bool(pdf),
            write_assets=bool(pdf),
        )
    except Exception as e:
        pack = {"pdf_error": str(e), "dossier_error": str(e)}

    first_user = (turns.get("user") or ["(none)"])[-1][:160]
    themes_line = ""
    for line in body.splitlines():
        if "themes:" in line.lower() or line.startswith("- **themes:**"):
            themes_line = line
            break

    # index: one live row per session — rewrite file to drop duplicates
    _upsert_index_row(
        {
            "ts": datetime.now(timezone.utc).isoformat(),
            "session_id": sid,
            "source": ref.source,
            "local_session_id": ref.local_id,
            "path": str(out_path),
            "pdf": pack.get("pdf"),
            "dossier_json": pack.get("dossier_json"),
            "mode": mode,
            "user_sample": first_user,
            "themes_line": themes_line,
            "amended": exists,
            "line_count": line_count,
        }
    )

    mark_summarized(
        sid,
        chat_mtime=chat_mtime,
        line_count=line_count,
        amended=exists,
    )

    # attention: only ping on first write or force, not every amend (noise)
    att_ping = ping_session_record(
        sid=sid,
        seat=ref.source,
        narrative=str(out_path),
        pack=pack,
        exists=exists,
        force=force,
        incomplete=incomplete,
    )

    brief_meta: dict[str, Any] = {}
    try:
        from mag.brief_local import write_brief

        brief_meta = write_brief(sid, use_llm=use_llm, write_visual=False)
    except Exception as e:
        brief_meta = {"ok": False, "error": str(e)}

    # visual only on explicit request (export layer) — not part of lean complete
    vis_meta: dict[str, Any] = {"ok": True, "skipped": True, "reason": "export_on_demand"}
    if visual:
        try:
            from mag.visual_pack import write_visual_pack

            vis_meta = write_visual_pack(sid)
        except Exception as e:
            vis_meta = {"ok": False, "error": str(e)}

    final_status = pack_status(sid)
    kpi: dict[str, Any] = {}
    try:
        from mag.records import write_kpi

        kpi = write_kpi(source="summarize")
    except Exception as e:
        kpi = {"ok": False, "error": str(e)[:120]}

    return {
        "ok": bool(final_status.get("complete") or pack.get("dossier_json")),
        "session_id": sid,
        "source": ref.source,
        "local_session_id": ref.local_id,
        "path": str(out_path),
        "mode": mode,
        "lines": line_count,
        "amended": exists,
        "brief": brief_meta,
        "visual": vis_meta,
        "pack": final_status,
        "complete": final_status.get("complete"),
        "missing": final_status.get("missing") or [],
        "kpi": {
            "n_leaves": kpi.get("n_leaves"),
            "complete_pct": kpi.get("complete_pct"),
            "n_incomplete": kpi.get("n_incomplete"),
        },
        **pack,
    }


def _upsert_index_row(row: dict[str, Any]) -> None:
    """Keep one index line per session_id (amend original, no bloat)."""
    BIO_DIR.mkdir(parents=True, exist_ok=True)
    sid = row.get("session_id")
    rows: list[dict[str, Any]] = []
    if INDEX.is_file():
        for line in INDEX.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if r.get("session_id") == sid:
                continue
            rows.append(r)
    rows.append(row)
    INDEX.write_text(
        "\n".join(json.dumps(r, default=str) for r in rows[-300:]) + "\n",
        encoding="utf-8",
    )
