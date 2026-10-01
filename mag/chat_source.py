"""Agnostic chat sources for the biographer / Verkle leaf system.

Any seat that produces a conversation can FILE as a workday bead.
Seats today:
  - grok       → ~/.grok/sessions/.../chat_history.jsonl
  - mag_agent  → memory/agent_sessions/<id>.json  (messages[])

Weights ≠ continuity. Source is a label on the residual, not a second archive.
"""
from __future__ import annotations

import json
import re
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from config import ROOT


def _grok_home() -> Path:
    """~/.grok resolved lazily: Path.home() can raise in service/sandbox
    contexts without a resolvable HOME (same fix as config.py)."""
    try:
        return Path.home() / ".grok"
    except (RuntimeError, OSError):
        return ROOT.parent / ".grok"


GROK_HOME = _grok_home()
GROK_SESSIONS = GROK_HOME / "sessions"
AGENT_SESS_DIR = ROOT / "memory" / "agent_sessions"

# Stable bio id namespace for agent seats (amend-in-place, no collision with Grok UUIDs).
AGENT_BIO_PREFIX = "mag-agent-"

SOURCE_GROK = "grok"
SOURCE_MAG_AGENT = "mag_agent"
SOURCE_AUTO = "auto"


@dataclass
class ChatRef:
    """Resolved transcript location + seat label."""

    session_id: str  # biographer / residual / verkle id
    path: Path
    source: str
    local_id: str | None = None  # e.g. agent seat label "dashboard"
    provider: str | None = None
    model: str | None = None

    @property
    def label(self) -> str:
        if self.source == SOURCE_MAG_AGENT:
            seat = self.local_id or "agent"
            return f"Mag agent ({seat})"
        if self.source == SOURCE_GROK:
            return "Grok TUI"
        if self.source == "cursor":
            return "Cursor IDE"
        return self.source or "unknown"


def agent_bio_id(local_session_id: str) -> str:
    """Map agent seat id → biographer session_id (stable)."""
    raw = (local_session_id or "default").strip() or "default"
    if raw.startswith(AGENT_BIO_PREFIX):
        return raw
    safe = re.sub(r"[^a-zA-Z0-9._-]+", "_", raw)[:48] or "default"
    return f"{AGENT_BIO_PREFIX}{safe}"


def agent_local_id(bio_session_id: str) -> str:
    if bio_session_id.startswith(AGENT_BIO_PREFIX):
        return bio_session_id[len(AGENT_BIO_PREFIX) :]
    return bio_session_id


def agent_session_path(local_session_id: str) -> Path:
    safe = re.sub(r"[^a-zA-Z0-9._-]+", "_", (local_session_id or "default"))[:64] or "default"
    return AGENT_SESS_DIR / f"{safe}.json"


def _find_grok_chat(session_id: str, cwd: str | None = None) -> Path | None:
    if cwd:
        p = GROK_SESSIONS / urllib.parse.quote(cwd, safe="") / session_id / "chat_history.jsonl"
        if p.is_file():
            return p
    if not GROK_SESSIONS.is_dir():
        return None
    for group in GROK_SESSIONS.iterdir():
        if not group.is_dir():
            continue
        cand = group / session_id / "chat_history.jsonl"
        if cand.is_file():
            return cand
    return None


def _looks_like_uuid(sid: str) -> bool:
    s = (sid or "").strip()
    # Grok-style ids: 019fc364-364c-7f10-...
    return bool(re.match(r"^[0-9a-f]{8}-[0-9a-f]{4}-", s, re.I))


def resolve_chat(
    session_id: str,
    *,
    source: str | None = None,
    cwd: str | None = None,
    chat_path: Path | str | None = None,
) -> ChatRef | None:
    """Resolve a session id to a transcript file. Source-agnostic when source=auto."""
    if not session_id and not chat_path:
        return None

    if chat_path is not None:
        path = Path(chat_path)
        if not path.is_file():
            return None
        kind = _detect_path_source(path, session_id or path.stem)
        local = None
        provider = model = None
        bio_id = session_id or path.stem
        if kind == SOURCE_MAG_AGENT:
            local = agent_local_id(bio_id) if bio_id.startswith(AGENT_BIO_PREFIX) else path.stem
            bio_id = agent_bio_id(local)
            provider, model = _agent_provider_model(path)
        return ChatRef(
            session_id=bio_id,
            path=path,
            source=kind,
            local_id=local,
            provider=provider,
            model=model,
        )

    src = (source or SOURCE_AUTO).strip().lower() or SOURCE_AUTO
    sid = (session_id or "").strip()
    if not sid:
        return None

    # Explicit agent / bare seat name / mag-agent-* prefix
    if src in {SOURCE_MAG_AGENT, "agent", "mag-agent"} or sid.startswith(AGENT_BIO_PREFIX):
        local = agent_local_id(sid)
        path = agent_session_path(local)
        if path.is_file():
            provider, model = _agent_provider_model(path)
            return ChatRef(
                session_id=agent_bio_id(local),
                path=path,
                source=SOURCE_MAG_AGENT,
                local_id=local,
                provider=provider,
                model=model,
            )
        if src != SOURCE_AUTO:
            return None

    # Explicit grok or UUID-shaped → Grok home
    if src in {SOURCE_GROK, "tui"} or (src == SOURCE_AUTO and _looks_like_uuid(sid)):
        path = _find_grok_chat(sid, cwd)
        if path:
            return ChatRef(session_id=sid, path=path, source=SOURCE_GROK)
        if src != SOURCE_AUTO:
            return None

    # Auto: try agent seat name (dashboard, smoke, …)
    if src == SOURCE_AUTO:
        path = agent_session_path(sid)
        if path.is_file():
            provider, model = _agent_provider_model(path)
            return ChatRef(
                session_id=agent_bio_id(sid),
                path=path,
                source=SOURCE_MAG_AGENT,
                local_id=sid,
                provider=provider,
                model=model,
            )
        path = _find_grok_chat(sid, cwd)
        if path:
            return ChatRef(session_id=sid, path=path, source=SOURCE_GROK)

    return None


def _detect_path_source(path: Path, hint: str) -> str:
    try:
        rel = path.resolve().relative_to(AGENT_SESS_DIR.resolve())
        if rel.suffix == ".json":
            return SOURCE_MAG_AGENT
    except (ValueError, OSError):
        pass
    name = path.name.lower()
    if name.endswith(".json") and "agent" in str(path).lower():
        return SOURCE_MAG_AGENT
    if name == "chat_history.jsonl" or name.endswith(".jsonl"):
        return SOURCE_GROK
    if hint.startswith(AGENT_BIO_PREFIX):
        return SOURCE_MAG_AGENT
    return SOURCE_GROK if path.suffix == ".jsonl" else SOURCE_MAG_AGENT


def _agent_provider_model(path: Path) -> tuple[str | None, str | None]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return (
            str(data.get("provider") or "") or None,
            str(data.get("model") or "") or None,
        )
    except (json.JSONDecodeError, OSError):
        return None, None


def _preview_content(content: Any, limit: int = 800) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and "text" in item:
                parts.append(str(item["text"]))
            elif isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
            else:
                parts.append(str(item)[:200])
        text = " ".join(parts)
    elif isinstance(content, dict):
        text = json.dumps(content, default=str)
    else:
        text = str(content)
    text = re.sub(r"\s+", " ", text).strip()
    # Drop TUI wrapper noise that pollutes operator-prompt samples
    if text.startswith("<system-reminder>") or text.startswith("<user_info>"):
        # keep only if there's a user_query inside
        m = re.search(r"<user_query>\s*(.*?)\s*</user_query>", text, re.I | re.S)
        if m:
            text = m.group(1).strip()
        else:
            return ""
    if text.startswith("<image_files>"):
        m = re.search(r"<user_query>\s*(.*?)\s*</user_query>", text, re.I | re.S)
        if m:
            text = m.group(1).strip()
        else:
            text = "[image attachment]"
    return text[:limit]


def _tool_call_preview(tc: Any) -> str:
    if not isinstance(tc, dict):
        return str(tc)[:200]
    fn = tc.get("function") if isinstance(tc.get("function"), dict) else {}
    name = fn.get("name") or tc.get("name") or tc.get("tool_name") or "tool"
    args = fn.get("arguments") or tc.get("arguments") or tc.get("input") or ""
    if isinstance(args, (dict, list)):
        args = json.dumps(args, default=str)
    return f"{name}: {str(args)[:300]}"


def extract_turns_from_messages(
    messages: list[Any],
    *,
    source: str = SOURCE_MAG_AGENT,
    max_items: int = 4000,
) -> dict[str, Any]:
    """Normalize OpenAI-style message list → biographer turns."""
    user_bits: list[str] = []
    asst_bits: list[str] = []
    tools: list[str] = []
    reasoning: list[str] = []
    n = 0
    for m in messages[-max_items:]:
        if not isinstance(m, dict):
            continue
        n += 1
        role = str(m.get("role") or m.get("type") or "").lower()
        preview = _preview_content(m.get("content"))
        if role in {"system"}:
            continue  # pack/law — not operator workday content
        if role in {"user", "human"}:
            if preview:
                user_bits.append(preview)
            continue
        if role in {"assistant", "model", "message"}:
            if preview:
                asst_bits.append(preview)
            for tc in m.get("tool_calls") or []:
                tools.append(_tool_call_preview(tc)[:400])
            continue
        if "tool" in role:
            name = m.get("name") or m.get("tool_name") or ""
            bit = f"{name}: {preview}" if name else preview
            if bit:
                tools.append(bit[:400])
            continue
        if "reason" in role:
            if preview:
                reasoning.append(preview[:400])
    return {
        "line_count": n,
        "user": user_bits[-40:],
        "assistant": asst_bits[-40:],
        "tools": tools[-60:],
        "reasoning": reasoning[-30:],
        "source": source,
    }


def extract_turns_from_jsonl(path: Path, *, max_lines: int = 4000) -> dict[str, Any]:
    """Grok (and any jsonl) chat_history lines → biographer turns."""
    user_bits: list[str] = []
    asst_bits: list[str] = []
    tools: list[str] = []
    reasoning: list[str] = []
    n = 0
    data = path.read_bytes()
    text = data.decode("utf-8", errors="replace")
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if len(lines) > max_lines:
        lines = lines[-max_lines:]
    for ln in lines:
        n += 1
        try:
            obj = json.loads(ln)
        except json.JSONDecodeError:
            continue
        t = str(obj.get("type") or obj.get("role") or "")
        preview = _preview_content(obj.get("content"))
        if not preview and "summary" in obj:
            s = obj["summary"]
            if isinstance(s, list):
                preview = " ".join(
                    str(x.get("text", x) if isinstance(x, dict) else x) for x in s
                )
            else:
                preview = str(s)
            preview = re.sub(r"\s+", " ", preview).strip()[:800]
        if not preview and not obj.get("tool_calls"):
            continue
        tl = t.lower()
        if t in {"user", "human"} or "user" in tl:
            if preview:
                user_bits.append(preview)
        elif t in {"assistant"} or t == "message":
            if preview:
                asst_bits.append(preview)
            for tc in obj.get("tool_calls") or []:
                tools.append(_tool_call_preview(tc)[:400])
        elif "tool" in tl:
            if preview:
                tools.append(preview[:400])
        elif "reason" in tl:
            if preview:
                reasoning.append(preview[:400])
    return {
        "line_count": n,
        "user": user_bits[-40:],
        "assistant": asst_bits[-40:],
        "tools": tools[-60:],
        "reasoning": reasoning[-30:],
        "source": SOURCE_GROK,
    }


def extract_turns(path: Path, *, source: str | None = None, max_lines: int = 4000) -> dict[str, Any]:
    """Extract turns from any supported transcript path."""
    kind = source or _detect_path_source(path, path.stem)
    if kind == SOURCE_MAG_AGENT or (path.suffix == ".json" and path.name != "chat_history.jsonl"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            return {
                "line_count": 0,
                "user": [],
                "assistant": [],
                "tools": [],
                "reasoning": [],
                "source": SOURCE_MAG_AGENT,
                "error": str(e)[:200],
            }
        msgs = data.get("messages") if isinstance(data, dict) else None
        if not isinstance(msgs, list):
            msgs = data if isinstance(data, list) else []
        turns = extract_turns_from_messages(msgs, source=SOURCE_MAG_AGENT, max_items=max_lines)
        if isinstance(data, dict):
            turns["provider"] = data.get("provider")
            turns["model"] = data.get("model")
            turns["local_session_id"] = data.get("session_id")
            turns["updated"] = data.get("updated")
        return turns
    turns = extract_turns_from_jsonl(path, max_lines=max_lines)
    turns["source"] = SOURCE_GROK
    return turns


def list_agent_session_ids() -> list[str]:
    if not AGENT_SESS_DIR.is_dir():
        return []
    out: list[str] = []
    for p in sorted(AGENT_SESS_DIR.glob("*.json")):
        if p.name.startswith("_"):
            continue
        out.append(p.stem)
    return out


def file_agent_session(
    local_session_id: str = "dashboard",
    *,
    use_llm: bool = False,
    force: bool = False,
    amend: bool = True,
    pdf: bool = False,
    visual: bool = False,
) -> dict[str, Any]:
    """FILE one Mag agent seat into residual DNA + Verkle leaf (workday)."""
    from mag.biography import summarize_session

    local = (local_session_id or "dashboard").strip() or "dashboard"
    path = agent_session_path(local)
    if not path.is_file():
        return {
            "ok": False,
            "error": f"agent session not found: {path}",
            "local_session_id": local,
            "bio_session_id": agent_bio_id(local),
        }
    # Skip empty / system-only seats
    turns = extract_turns(path, source=SOURCE_MAG_AGENT)
    if not (turns.get("user") or turns.get("assistant") or turns.get("tools")):
        return {
            "ok": True,
            "skipped": True,
            "reason": "empty_agent_session",
            "local_session_id": local,
            "bio_session_id": agent_bio_id(local),
        }
    res = summarize_session(
        agent_bio_id(local),
        chat_path=path,
        source=SOURCE_MAG_AGENT,
        use_llm=use_llm,
        force=force,
        amend=amend,
        pdf=pdf,
        visual=visual,
    )
    res["local_session_id"] = local
    res["source"] = SOURCE_MAG_AGENT
    res["bio_session_id"] = agent_bio_id(local)
    # AH19 (audit finding #10, 2026-09-30): surface the CHAIN write model so
    # callers can see which shape the fold took — v1 amend-in-place (whole
    # verkle_chain.jsonl rewrite per save) or v2 append-leaves (one new row;
    # session_seq is the save counter). ``amend=True`` keeps its residual-pack
    # meaning (per-session JSON rewrite, small): only the CHAIN write changes
    # shape under configs chain_mode=v2. Spec: AH19_AMEND_PERF.md.
    verkle = res.get("verkle") if isinstance(res.get("verkle"), dict) else None
    if verkle and verkle.get("chain_mode"):
        res["chain_mode"] = verkle["chain_mode"]
        if verkle.get("session_seq") is not None:
            res["session_seq"] = verkle["session_seq"]
    return res


def file_dirty_agent_sessions(
    *,
    use_llm: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    """Amend all agent seats that have real turns (daemon / catch-up)."""
    results: list[dict[str, Any]] = []
    for local in list_agent_session_ids():
        try:
            r = file_agent_session(local, use_llm=use_llm, force=force, amend=True)
            if not r.get("skipped") or r.get("reason") != "empty_agent_session":
                results.append(
                    {
                        "local": local,
                        "ok": r.get("ok"),
                        "skipped": r.get("skipped"),
                        "bio": r.get("bio_session_id") or r.get("session_id"),
                        "complete": r.get("complete"),
                    }
                )
        except Exception as e:
            results.append({"local": local, "ok": False, "error": str(e)[:200]})
    return {"ok": True, "n": len(results), "results": results}
