"""Virtual desk research loop — DeepSeek cycles on Mag workstation brief.

Each cycle answers one P0/P1 question from docs/ref/RESEARCH_MAG_VIRTUAL_DESK.txt,
appends to memory/research_packs/mag_virtual_desk/REPORT.txt, and may queue public
URLs for follow-up digs.

Stop: python main.py virtual-desk-loop --stop
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from config import ROOT

_LOCK = threading.Lock()
_THREAD: threading.Thread | None = None
_STOP = threading.Event()

CFG_PATH = ROOT / "configs" / "virtual_desk.yaml"
PACK_ROOT = ROOT / "memory" / "research_packs" / "mag_virtual_desk"

QUESTIONS: list[dict[str, str]] = [
    {
        "id": "Q1",
        "priority": "P0",
        "title": "Isolation model",
        "prompt": (
            "How do production agent systems separate operator input from agent input "
            "without a literal second human? Cover job queues, mailboxes, session files, "
            "sandbox stdin=DEVNULL, and computer-use APIs that do not hook the host keyboard. "
            "Map findings to mag/orchestrator.py and governor_autorun.py."
        ),
    },
    {
        "id": "Q2",
        "priority": "P0",
        "title": "Supervision pattern",
        "prompt": (
            "What is the industry-standard parent-survives / child-dies supervision shape? "
            "Cover timeout, heartbeat, stall detection, retry policy, parallel workers. "
            "Map to Mag orchestrator spawn/kill/reap."
        ),
    },
    {
        "id": "Q3",
        "priority": "P0",
        "title": "Observable autonomy",
        "prompt": (
            "How do systems show what the agent did overnight without chat history? "
            "Cover dashboards, run cards, structured artifacts, morning briefs, traces "
            "readable by a layman. Map to autorun_status and Office card."
        ),
    },
    {
        "id": "Q4",
        "priority": "P0",
        "title": "Container and GUI",
        "prompt": (
            "Minimal pattern for headless browser or desktop inside Docker only (not host Chrome). "
            "Cover xvfb, Playwright in container, noVNC, CDP over localhost, seccomp/cap_drop. "
            "Name exact images/bases where possible."
        ),
    },
    {
        "id": "Q5",
        "priority": "P0",
        "title": "Windows operator ritual",
        "prompt": (
            "Practical two-desk UX on Windows 11: Virtual Desktops, window placement, "
            "Task Scheduler for MagAutorun, firewall/localhost binding. Step-by-step, not conceptual."
        ),
    },
    {
        "id": "Q6",
        "priority": "P1",
        "title": "Computer use / desktop automation",
        "prompt": (
            "Anthropic computer use, OpenAI Operator/CUA, Google Mariner, OpenClaw, Bytebot — "
            "what is load-bearing vs demo? Cost, reliability, cage requirements."
        ),
    },
    {
        "id": "Q7",
        "priority": "P1",
        "title": "Evaluator in a cage",
        "prompt": (
            "Planner/generator/evaluator loops where evaluator uses Playwright MCP inside sandbox. "
            "Cite Anthropic harness and OpenAI eval patterns."
        ),
    },
    {
        "id": "Q8",
        "priority": "P1",
        "title": "Parallel desk economics",
        "prompt": (
            "When to spawn N orchestrator children vs one long agent — token cost, context bleed, "
            "failure blast radius."
        ),
    },
    {
        "id": "Q9",
        "priority": "P1",
        "title": "Pause steer continue",
        "prompt": (
            "Live operator intervention without killing worker: mailbox, RPC, file-based knot. "
            "Find 3 analogues to Mag pigeonhole steer/pause/continue."
        ),
    },
    {
        "id": "Q10",
        "priority": "P1",
        "title": "Security anti-patterns",
        "prompt": (
            "Docker socket mount, host root bind, agent uses real Chrome profile, RDP into host — "
            "flag each with severity and Mag relevance."
        ),
    },
]


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_config() -> dict[str, Any]:
    if CFG_PATH.is_file():
        try:
            raw = yaml.safe_load(CFG_PATH.read_text(encoding="utf-8")) or {}
            if isinstance(raw, dict):
                return raw
        except Exception:
            pass
    return {
        "provider": "deepseek",
        "model": "",
        "tier": "T2",
        "max_tokens": 4096,
        "temperature": 0.2,
        "cycle_seconds": 120,
        "max_cycles": 0,
    }


def _state_path() -> Path:
    return PACK_ROOT / "state.json"


def _log_path() -> Path:
    return ROOT / "logs" / "virtual_desk_loop.jsonl"


def _report_path(cfg: dict[str, Any] | None = None) -> Path:
    cfg = cfg or load_config()
    rel = str(cfg.get("report_path") or "memory/research_packs/mag_virtual_desk/REPORT.txt")
    return ROOT / rel


def _cycles_dir() -> Path:
    p = PACK_ROOT / "cycles"
    p.mkdir(parents=True, exist_ok=True)
    return p


def read_state() -> dict[str, Any]:
    p = _state_path()
    if not p.is_file():
        return {
            "schema": "virtual_desk_loop_state.v1",
            "run": False,
            "cycle": 0,
            "done_questions": [],
            "url_queue": [],
            "url_done": [],
            "last_unit": None,
            "last_error": None,
            "last_ok": None,
        }
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {"schema": "virtual_desk_loop_state.v1", "run": False, "cycle": 0}


def write_state(st: dict[str, Any]) -> None:
    st = dict(st)
    st["ts"] = _utc()
    st["thread_alive"] = bool(_THREAD and _THREAD.is_alive())
    PACK_ROOT.mkdir(parents=True, exist_ok=True)
    _state_path().write_text(json.dumps(st, indent=2, default=str), encoding="utf-8")
    report = _report_path()
    done_n = len(st.get("done_questions") or [])
    q_total = len(QUESTIONS)
    url_q = len(st.get("url_queue") or [])
    lines = [
        f"# Virtual desk loop — {st.get('ts')}",
        "",
        f"- run: {st.get('run')} · cycle: {st.get('cycle')} · questions done: {done_n}/{q_total}",
        f"- url_queue: {url_q} · last_unit: {st.get('last_unit') or 'n/a'}",
        f"- last_ok: {st.get('last_ok')} · last_error: {st.get('last_error') or 'none'}",
        f"- report: {report}",
        "",
        "Stop: python main.py virtual-desk-loop --stop",
        "",
    ]
    (PACK_ROOT / "latest.md").write_text("\n".join(lines), encoding="utf-8")


def _log(event: dict[str, Any]) -> None:
    path = _log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": _utc(), **event}, default=str) + "\n")


def load_brief() -> str:
    cfg = load_config()
    for rel in cfg.get("brief_paths") or []:
        p = ROOT / str(rel)
        if p.is_file():
            return p.read_text(encoding="utf-8", errors="replace")
    raise FileNotFoundError("RESEARCH_MAG_VIRTUAL_DESK.txt not found")


def _extract_urls(text: str) -> list[str]:
    from mag.lattice_loop import normalize_url

    found = re.findall(r"https?://[^\s\)\]\"\'<>]+", text or "")
    out: list[str] = []
    seen: set[str] = set()
    for u in found:
        n = normalize_url(u)
        if n and n not in seen:
            seen.add(n)
            out.append(n)
    return out


def _prior_report_excerpt(max_chars: int = 12000) -> str:
    p = _report_path()
    if not p.is_file():
        return "(no prior report sections yet)"
    text = p.read_text(encoding="utf-8", errors="replace")
    if len(text) <= max_chars:
        return text
    return "...[truncated head omitted]...\n" + text[-max_chars:]


def _next_unit(st: dict[str, Any]) -> dict[str, Any] | None:
    done = set(st.get("done_questions") or [])
    for q in QUESTIONS:
        if q["id"] not in done:
            return {"kind": "question", **q}
    url_queue = [u for u in (st.get("url_queue") or []) if u]
    url_done = set(st.get("url_done") or [])
    for u in url_queue:
        if u not in url_done:
            return {"kind": "url", "id": f"url_{len(url_done)+1}", "url": u, "priority": "P1"}
    return None


def _deepseek_chat(
    system: str,
    user: str,
    *,
    provider: str,
    model: str | None,
    tier: str,
    max_tokens: int,
    temperature: float,
) -> dict[str, Any]:
    from models.providers import chat_provider

    kw: dict[str, Any] = {
        "tier": tier,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if model:
        kw["model"] = model
    return chat_provider(provider, system, user, **kw)


def _answer_unit(
    unit: dict[str, Any],
    *,
    cycle: int,
    brief: str,
    cfg: dict[str, Any],
) -> dict[str, Any]:
    provider = str(os.environ.get("MAG_VIRTUAL_DESK_PROVIDER") or cfg.get("provider") or "deepseek")
    model = (os.environ.get("MAG_VIRTUAL_DESK_MODEL") or cfg.get("model") or "").strip() or None
    tier = str(cfg.get("tier") or "T2")
    max_tokens = int(cfg.get("max_tokens") or 4096)
    temperature = float(cfg.get("temperature") or 0.2)

    system = (
        "You are a research agent for Mag Resource Harness virtual desk v2.1. "
        "Local-first, container cage, one orchestrator. Steal production patterns only. "
        "Cite URLs with access dates. Flag vaporware. Plain ASCII in answers (no markdown tables). "
        "End with: Mag mapping (module/file), Steal score 1-5, Best references (urls)."
    )

    prior = _prior_report_excerpt()
    if unit.get("kind") == "url":
        url = str(unit.get("url") or "")
        user = (
            f"VIRTUAL DESK URL DIG cycle={cycle}\n\n"
            f"## Research brief (context)\n{brief[:14000]}\n\n"
            f"## Prior report sections\n{prior}\n\n"
            f"## URL to analyze\n{url}\n\n"
            "Fetch mentally from public knowledge; if uncertain say so. "
            "How does this source inform Mag virtual desk? "
            "Propose 0-3 additional public URLs only if grounded."
        )
        unit_id = str(unit.get("id") or "url")
        title = f"URL dig {url[:80]}"
    else:
        unit_id = str(unit.get("id") or "Q?")
        title = str(unit.get("title") or unit_id)
        prompt = str(unit.get("prompt") or "")
        user = (
            f"VIRTUAL DESK RESEARCH cycle={cycle} unit={unit_id} priority={unit.get('priority')}\n\n"
            f"## Research brief (full)\n{brief[:16000]}\n\n"
            f"## Prior report sections\n{prior}\n\n"
            f"## Question {unit_id}: {title}\n{prompt}\n\n"
            "Answer thoroughly. Include 2+ independent sources where possible. "
            "List 0-5 public URLs for follow-up at the end under PROPOSED_URLS:"
        )

    res = _deepseek_chat(
        system,
        user,
        provider=provider,
        model=model,
        tier=tier,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    out: dict[str, Any] = {
        "unit_id": unit_id,
        "title": title,
        "provider": provider,
        "ok": bool(res.get("ok")),
        "error": res.get("error"),
    }
    if not res.get("ok"):
        return out

    text = (res.get("text") or "").strip()
    if not text:
        out["ok"] = False
        out["error"] = "empty model answer"
        return out

    out["answer_chars"] = len(text)
    out["model"] = res.get("model")

    # Write cycle file
    cdir = _cycles_dir()
    cycle_path = cdir / f"c{cycle:04d}_{unit_id}.txt"
    cycle_body = (
        f"Virtual desk cycle {cycle}\n"
        f"unit={unit_id}\n"
        f"title={title}\n"
        f"provider={provider}\n"
        f"model={out.get('model')}\n"
        f"ts={_utc()}\n\n"
        f"{text}\n"
    )
    cycle_path.write_text(cycle_body, encoding="utf-8")
    out["cycle_path"] = str(cycle_path)

    # Append to report
    report = _report_path(cfg)
    report.parent.mkdir(parents=True, exist_ok=True)
    block = (
        f"\n\n{'='*72}\n"
        f"SECTION {unit_id} — {title}\n"
        f"cycle={cycle} ts={_utc()} provider={provider}\n"
        f"{'='*72}\n\n"
        f"{text}\n"
    )
    if report.is_file():
        report.write_text(report.read_text(encoding="utf-8") + block, encoding="utf-8")
    else:
        header = (
            "Mag Virtual Desk — Research Report\n"
            f"Commitment: research-mag-virtual-desk-001-r1\n"
            f"Started: {_utc()}\n"
            f"Provider: {provider}\n"
        )
        report.write_text(header + block, encoding="utf-8")
    out["report_path"] = str(report)

    proposed = _extract_urls(text)
    out["proposed_urls"] = proposed[:8]
    return out


def run_once(*, dry: bool = False) -> dict[str, Any]:
    cfg = load_config()
    try:
        brief = load_brief()
    except FileNotFoundError as e:
        return {"ok": False, "error": str(e)}

    st = read_state()
    unit = _next_unit(st)
    if not unit:
        return {"ok": True, "done": True, "hint": "all questions and url queue complete"}

    cycle = int(st.get("cycle") or 0) + 1
    if dry:
        return {
            "ok": True,
            "dry": True,
            "cycle": cycle,
            "unit": unit,
            "hint": "would call DeepSeek",
        }

    result = _answer_unit(unit, cycle=cycle, brief=brief, cfg=cfg)
    st = read_state()
    st["cycle"] = cycle
    st["last_unit"] = unit.get("id")
    st["last_ok"] = bool(result.get("ok"))
    st["last_error"] = result.get("error")

    if result.get("ok") and unit.get("kind") == "question":
        done = list(st.get("done_questions") or [])
        uid = str(unit.get("id"))
        if uid not in done:
            done.append(uid)
        st["done_questions"] = done
    elif result.get("ok") and unit.get("kind") == "url":
        url_done = list(st.get("url_done") or [])
        u = str(unit.get("url") or "")
        if u and u not in url_done:
            url_done.append(u)
        st["url_done"] = url_done[-80:]

    if result.get("ok"):
        q = list(st.get("url_queue") or [])
        done_urls = set(st.get("url_done") or [])
        queued = set(q)
        for u in result.get("proposed_urls") or []:
            if u not in done_urls and u not in queued and len(q) < 30:
                q.append(u)
                queued.add(u)
        st["url_queue"] = q

    write_state(st)
    _log({"phase": "once", "cycle": cycle, "unit": unit.get("id"), "ok": result.get("ok")})
    return {"ok": bool(result.get("ok")), "cycle": cycle, "unit": unit, "result": result}


def plant_status() -> dict[str, Any]:
    cfg = load_config()
    st = read_state()
    brief_ok = any((ROOT / str(p)).is_file() for p in (cfg.get("brief_paths") or []))
    cycles = sorted(_cycles_dir().glob("c*.txt")) if _cycles_dir().is_dir() else []
    cycles.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return {
        "ok": True,
        "mode": "virtual_desk_loop",
        "brief_ok": brief_ok,
        "provider": os.environ.get("MAG_VIRTUAL_DESK_PROVIDER") or cfg.get("provider"),
        "state": st,
        "questions_total": len(QUESTIONS),
        "questions_done": len(st.get("done_questions") or []),
        "url_queue": len(st.get("url_queue") or []),
        "report_path": str(_report_path(cfg)),
        "thread_alive": bool(_THREAD and _THREAD.is_alive()),
        "recent_cycles": [p.name for p in cycles[:8]],
        "latest": str(PACK_ROOT / "latest.md"),
    }


def _loop_main(*, cycle_seconds: int, max_cycles: int) -> None:
    cfg = load_config()
    try:
        load_brief()
    except FileNotFoundError as e:
        st = read_state()
        st["run"] = False
        st["last_error"] = str(e)
        write_state(st)
        _log({"phase": "abort", "error": str(e)})
        return

    st = read_state()
    st["run"] = True
    st["last_error"] = None
    write_state(st)
    _log({"phase": "start", "provider": cfg.get("provider")})

    while not _STOP.is_set():
        st = read_state()
        if not st.get("run"):
            break

        cycle = int(st.get("cycle") or 0) + 1
        if max_cycles and cycle > max_cycles:
            st["run"] = False
            st["last_error"] = "max_cycles reached"
            write_state(st)
            break

        if _next_unit(st) is None:
            st["run"] = False
            st["last_error"] = "all units complete"
            write_state(st)
            _log({"phase": "complete", "cycle": cycle - 1})
            break

        _log({"phase": "cycle_start", "cycle": cycle})
        res = run_once(dry=False)
        if not res.get("ok") and not res.get("done"):
            st = read_state()
            st["last_error"] = (
                (res.get("result") or {}).get("error")
                or res.get("error")
                or "cycle failed"
            )
            st["last_ok"] = False
            write_state(st)
            _log({"phase": "cycle_fail", "cycle": cycle, "error": st["last_error"]})

        if _STOP.wait(float(cycle_seconds)):
            break

    st = read_state()
    st["run"] = False
    write_state(st)
    _log({"phase": "exit", "cycle": st.get("cycle")})


def start_loop(
    *,
    background: bool = True,
    cycle_seconds: int | None = None,
    max_cycles: int | None = None,
) -> dict[str, Any]:
    global _THREAD
    cfg = load_config()
    cs = int(cycle_seconds if cycle_seconds is not None else cfg.get("cycle_seconds") or 120)
    mc = int(max_cycles if max_cycles is not None else cfg.get("max_cycles") or 0)

    st = read_state()
    st["run"] = True
    write_state(st)
    _STOP.clear()

    if _THREAD and _THREAD.is_alive():
        return {"ok": True, "already_running": True, "status": plant_status()}

    def target() -> None:
        _loop_main(cycle_seconds=cs, max_cycles=mc)

    if background:
        _THREAD = threading.Thread(target=target, name="mag-virtual-desk-loop", daemon=True)
        _THREAD.start()
        time.sleep(0.4)
        return {"ok": True, "started": True, "background": True, "status": plant_status()}

    target()
    return {"ok": True, "started": True, "background": False, "status": plant_status()}


def stop_loop() -> dict[str, Any]:
    st = read_state()
    st["run"] = False
    write_state(st)
    _STOP.set()
    t = _THREAD
    if t and t.is_alive():
        t.join(timeout=10.0)
    return {"ok": True, "stopped": True, "status": plant_status()}


def _share_id_from_url(url: str) -> str | None:
    m = re.search(r"chat\.deepseek\.com/share/([a-zA-Z0-9_-]+)", url or "")
    return m.group(1) if m else None


def _detect_done_questions(text: str) -> list[str]:
    """Best-effort: mark Q1-Q10 done if headings appear in imported export."""
    done: list[str] = []
    upper = (text or "").upper()
    for q in QUESTIONS:
        qid = q["id"]
        title = q["title"].upper()
        if re.search(rf"\b{re.escape(qid)}\b", upper) and (
            title in upper or "SECTION " + qid in upper
        ):
            done.append(qid)
    return done


def import_export(
    path: str | Path,
    *,
    source_url: str = "",
    replace: bool = False,
) -> dict[str, Any]:
    """Import a DeepSeek web export (paste/save as .txt) into REPORT.txt."""
    src = Path(path)
    if not src.is_file():
        return {"ok": False, "error": f"file not found: {src}"}

    raw = src.read_text(encoding="utf-8", errors="replace").strip()
    if not raw:
        return {"ok": False, "error": "empty file"}

    cfg = load_config()
    report = _report_path(cfg)
    report.parent.mkdir(parents=True, exist_ok=True)
    imports_dir = PACK_ROOT / "imports"
    imports_dir.mkdir(parents=True, exist_ok=True)

    share_id = _share_id_from_url(source_url) or src.stem
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archive = imports_dir / f"deepseek_share_{share_id}_{stamp}.txt"
    archive.write_text(raw, encoding="utf-8")

    header = (
        "Mag Virtual Desk - Research Report (imported)\n"
        f"Imported: {_utc()}\n"
        f"Source file: {src}\n"
    )
    if source_url:
        header += f"Source URL: {source_url}\n"
    header += f"Archive: {archive}\n\n"

    if replace or not report.is_file():
        report.write_text(header + raw + "\n", encoding="utf-8")
    else:
        block = (
            f"\n\n{'='*72}\n"
            f"IMPORT {stamp}\n"
            f"source={src}\n"
            f"url={source_url or 'n/a'}\n"
            f"{'='*72}\n\n"
            f"{raw}\n"
        )
        report.write_text(report.read_text(encoding="utf-8") + block, encoding="utf-8")

    done = _detect_done_questions(raw)
    st = read_state()
    merged = list(st.get("done_questions") or [])
    for qid in done:
        if qid not in merged:
            merged.append(qid)
    st["done_questions"] = merged
    st["last_ok"] = True
    st["last_error"] = None
    st["last_unit"] = f"import:{share_id}"
    if source_url:
        st["last_import_url"] = source_url
    write_state(st)
    _log({"phase": "import", "path": str(src), "url": source_url, "done": done})

    return {
        "ok": True,
        "report_path": str(report),
        "archive_path": str(archive),
        "chars": len(raw),
        "detected_done_questions": done,
        "hint": "Feed REPORT.txt to implementer or run virtual-desk-loop --once for next gap",
    }
