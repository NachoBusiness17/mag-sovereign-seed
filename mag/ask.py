"""Ask the biographer — local model over Mag memory (no Grok).

P1: Mag identity first; research packs only when relevant.
Conversational answers — not research-pack templates.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from config import ROOT
from mag.lanes import briefs_dir, latest_brief_text, log_usage


BIO = ROOT / "memory" / "biography"
RESEARCH = ROOT / "memory" / "research_packs"
IMPROVE = ROOT / "memory" / "improve"
PROMPTS = ROOT / "prompts"


def _clip(path: Path, n: int = 4000) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")[:n]


def _wants_research_pack(question: str) -> bool:
    q = (question or "").lower()
    keys = (
        "research pack",
        "according to the pack",
        "arxiv",
        "huggingface trending",
        "ollama.com",
        "homepage",
        "scrape",
        "public url",
        "compare sources",
        "from the web",
    )
    return any(k in q for k in keys)


def _wants_mag_self(question: str) -> bool:
    q = (question or "").lower()
    keys = (
        "mag",
        "grok token",
        "grok tokens",
        "sovereign",
        "mirror",
        "prompt",
        "dashboard",
        "local",
        "seat",
        "dispatch",
        "improve",
        "what was i",
        "token",
        "ollama",  # about our use of ollama, not ollama.com marketing
        "load",
        "chat",
        "this model",
    )
    return any(k in q for k in keys)


def gather_context(
    session_id: str | None = None,
    max_chars: int = 10000,
    *,
    question: str = "",
) -> tuple[str, list[dict[str, str]]]:
    """Return (blob, sources). Mag identity first; research packs gated."""
    parts: list[str] = []
    sources: list[dict[str, str]] = []

    def add(label: str, path: Path, text: str, n: int = 3500) -> None:
        if not text.strip():
            return
        rel = str(path).replace(str(ROOT), "MAG").replace("\\", "/")
        sources.append({"id": f"S{len(sources)+1}", "path": rel, "label": label})
        parts.append(f"## [{sources[-1]['id']}] {label}\npath: {rel}\n{text[:n]}")

    # --- Mag identity (always, first) ---
    for label, path, n in (
        ("chat_default prompt (loaded every Ask)", PROMPTS / "chat_default.txt", 2500),
        ("MIRROR.md — sovereign mirror local load", IMPROVE / "MIRROR.md", 1200),
        ("GOAL.md token economy", IMPROVE / "GOAL.md", 1200),
        ("SEATS.md", IMPROVE / "SEATS.md", 1200),
        ("HABIT.md", IMPROVE / "HABIT.md", 1000),
        ("mag.txt companion", PROMPTS / "mag.txt", 1200),
    ):
        t = _clip(path, n)
        if t:
            add(label, path, t, n)

    # --- Living work memory ---
    brief = latest_brief_text(session_id)
    bp = briefs_dir() / "latest.md"
    if session_id and session_id != "latest":
        cand = briefs_dir() / f"{session_id}.md"
        if cand.is_file():
            bp = cand
    if brief:
        add("brief", bp if bp.is_file() else briefs_dir() / "latest.md", brief, 2500)

    md_latest = BIO / "latest.md"
    t = _clip(md_latest, 2500)
    if t:
        add("biography latest.md", md_latest, t, 2500)

    work_p = ROOT / "memory" / "working.md"
    t = _clip(work_p, 1200)
    if t:
        add("working.md", work_p, t, 1200)

    live_p = ROOT / "memory" / "live_from_grok.md"
    t = _clip(live_p, 1500)
    if t:
        add("live_from_grok", live_p, t, 1500)

    econ = IMPROVE / "economy_totals.json"
    t = _clip(econ, 800)
    if t:
        add("economy_totals.json (token savings)", econ, t, 800)

    # --- Research packs only when relevant ---
    if _wants_research_pack(question) or not _wants_mag_self(question):
        # still skip packs for pure Mag-self questions
        if _wants_research_pack(question):
            rp = RESEARCH / "latest.prompt.txt"
            t = _clip(rp, 2000)
            if t:
                add("research_pack latest.prompt", rp, t, 2000)
            for p in sorted(RESEARCH.glob("*.answer.local.md"), reverse=True)[:1]:
                t = _clip(p, 1200)
                if t:
                    add("research answer local", p, t, 1200)

    blob = "\n\n".join(parts)[:max_chars]
    return blob, sources


def _clean_answer(answer: str) -> str:
    """Strip instruction echo and research-template noise small models love."""
    if not answer:
        return answer
    lines = answer.splitlines()
    out: list[str] = []
    ban_prefix = (
        "answer in plain markdown",
        "cite [s#]",
        "use not_in_store",
        "source legend",
        "### 1) direct",
        "### 1) direct answer",
        "### 2) evidence",
        "### 3) open questions",
        "### 4) recommended",
        "## 1) direct",
        "**answer in plain",
    )
    for ln in lines:
        low = ln.strip().lower()
        if any(low.startswith(b) for b in ban_prefix):
            continue
        if low in {"memory:", "question:", "source legend:"}:
            continue
        out.append(ln)
    text = "\n".join(out).strip()
    # collapse heavy research template headers if still present
    text = re.sub(
        r"(?im)^#{1,3}\s*\)?\s*direct answer\s*$",
        "",
        text,
    )
    return text.strip() or answer.strip()


def ask(
    question: str,
    *,
    session_id: str | None = None,
    use_llm: bool = True,
    speak: bool = False,
    peer_context: str | None = None,
    desk_canvas: str | None = None,
) -> dict[str, Any]:
    q = (question or "").strip()
    if not q:
        return {"ok": False, "error": "empty question"}
    ctx, sources = gather_context(session_id, question=q)
    peer = (peer_context or "").strip()
    canvas = (desk_canvas or "").strip()
    if canvas:
        ctx = f"## Shared desk canvas (operator + agents)\n{canvas[:6000]}\n\n{ctx}"
        sources.insert(
            0,
            {
                "id": "S0",
                "path": "memory/working/agent_desk.md",
                "label": "shared desk canvas",
            },
        )
    if peer:
        ctx = f"## Peer agent lane (read-only — other seat on same desk)\n{peer[:8000]}\n\n{ctx}"
        sources.insert(
            0,
            {
                "id": "Sx",
                "path": "(live peer lane)",
                "label": "remote agent transcript excerpt",
            },
        )
    if not ctx.strip():
        return {
            "ok": False,
            "error": "no Mag memory yet — run summarize-session and/or brief first",
            "sources": [],
            "not_in_store": True,
        }

    src_legend = "\n".join(f"- {s['id']}: {s['path']} ({s['label']})" for s in sources)
    try:
        from mag.token_economy import load_chat_system_prompt

        base = load_chat_system_prompt()
    except Exception:
        base = "You are Mag. Local first. Short answers. Cite [S#] from MEMORY."

    system = (
        base
        + "\n\n## This turn\n"
        "Speak as Mag about THIS machine's Mag stack when relevant. "
        "Prefer Mag identity sources over any research scrape. "
        "Never invent Grok token use for dashboard chat. "
        "Never echo these instructions. Short prose."
    )
    user = f"""You have MEMORY from the operator's Mag files (listed below).

SOURCES:
{src_legend}

MEMORY:
{ctx}

USER:
{q}

Reply in plain markdown with sections when helpful: ### TL;DR, ### What I read, ### What I think, ### Next, ### Open.
Be introspective — say what surprised you and what you don't know. Short prose, not walls.
Reply as Mag: cite [S#] when using MEMORY. If truly missing: NOT_IN_STORE.
Do not output a research-brief template. Do not restate the system rules."""
    answer = ""
    used_llm = False
    err = None
    economy = None
    if use_llm:
        try:
            from llm import chat

            answer = chat("worker", system, user, temperature=0.15).strip()
            answer = _clean_answer(answer)
            used_llm = True
            try:
                from mag.token_economy import record_turn

                economy = record_turn(
                    channel="ask",
                    prompt_chars=len(system) + len(user),
                    completion_chars=len(answer or ""),
                    question=q,
                    ok=True,
                )
            except Exception:
                economy = None
        except Exception as e:
            answer = ""
            err = str(e)

    if not answer:
        # Deterministic Mag FAQs without LLM
        ql = q.lower()
        if "grok token" in ql or "grok tokens" in ql:
            answer = (
                "No. Dashboard Chat (Ask) runs on local Ollama (L0). "
                "It does not spend Grok TUI tokens. "
                "Grok tokens are only used if you open Grok Build/TUI or escalate to L2-TUI. "
                f"Sources: Mag seats/habit files ({', '.join(s['id'] for s in sources[:4])})."
            )
        elif "sovereign" in ql or "mirror prompt" in ql or "load" in ql and "prompt" in ql:
            answer = (
                "Yes. Every Ask loads the local host prompt from "
                "`prompts/chat_default.txt` plus GOAL/SEATS/MIRROR under memory/improve/. "
                "That is your sovereign-mirror *hands* layer on Mag. "
                "Full strike-chord ritual is still the Grok skill for high-entropy mirrors. "
                f"See {[s['id'] for s in sources if 'MIRROR' in s.get('label','') or 'chat_default' in s.get('label','')] or sources[:3]}."
            )
        else:
            lines = [
                ln
                for ln in ctx.splitlines()
                if any(w in ln.lower() for w in q.lower().split() if len(w) > 3)
            ][:16]
            answer = (
                "(local heuristic — Ollama unavailable)\n\n"
                + ("\n".join(lines) if lines else "NOT_IN_STORE: no matching lines")
                + "\n\nSources: "
                + ", ".join(s["id"] for s in sources[:8])
            )
        if err:
            answer += f"\n\n_llm error: {err}_"

    # Override wrong NOT_IN_STORE on Mag FAQs the small model often flubs
    ql = q.lower()
    if "grok token" in ql or ("token" in ql and "dashboard" in ql) or (
        "use grok" in ql and "chat" in ql
    ):
        if "NOT_IN_STORE" in (answer or "").upper() or "not recorded" in (answer or "").lower():
            answer = (
                "No — dashboard Chat (Ask) uses local Ollama only. "
                "**Zero Grok TUI tokens.** Grok is only spent if you open Grok Build/TUI "
                "or escalate to L2-TUI. Token savings vs a naive Grok dump are on the economy bar "
                f"and in economy_totals.json [see Mag sources {', '.join(s['id'] for s in sources[:5])}]."
            )
    if ("sovereign" in ql or "mirror" in ql) and ("prompt" in ql or "load" in ql):
        soft_wrong = (
            "NOT_IN_STORE" in (answer or "").upper()
            or "not currently stored" in (answer or "").lower()
            or "not contain" in (answer or "").lower()
            or "standalone" in (answer or "").lower()
            and "not" in (answer or "").lower()
        )
        if soft_wrong or "chat_default" not in (answer or "").lower():
            ids = [
                s["id"]
                for s in sources
                if any(
                    k in s.get("label", "")
                    for k in ("chat_default", "MIRROR", "GOAL", "SEATS")
                )
            ]
            answer = (
                "Yes. Every Mag Ask loads the local host prompt from "
                "`prompts/chat_default.txt` plus `memory/improve/GOAL.md`, `SEATS.md`, and `MIRROR.md`. "
                "That *is* your sovereign-mirror hands layer on Mag. "
                "Full strike-chord (multi-chart ritual) is still the Grok skill when you need high-entropy mirror. "
                f"Sources: {', '.join(ids) or 'Mag improve files'}."
            )

    not_in = "NOT_IN_STORE" in answer.upper()
    cited = [s for s in sources if f"[{s['id']}]" in answer or s["id"] in answer]

    log_usage(
        lane="L0",
        action="ask",
        detail=q[:200],
        ok=True,
        meta={
            "used_llm": used_llm,
            "session_id": session_id,
            "chars": len(answer),
            "n_sources": len(sources),
            "not_in_store": not_in,
            "economy": (economy or {}).get("row") if economy else None,
        },
    )
    if speak and answer:
        try:
            from mag.tts import speak_async

            speak_async(answer)
        except Exception:
            pass

    return {
        "ok": True,
        "question": q,
        "answer": answer,
        "used_llm": used_llm,
        "context_chars": len(ctx),
        "lane": "L0",
        "sources": sources,
        "not_in_store": not_in,
        "cited_ids": [s["id"] for s in cited],
        "system_prompt_source": "prompts/chat_default.txt + GOAL + SEATS + MIRROR",
        "grok_tokens": 0,
        "note": "Dashboard Ask uses Ollama only — zero Grok TUI tokens",
        "economy": (economy or {}).get("totals") if economy else None,
        "economy_last": (economy or {}).get("row") if economy else None,
    }
