"""Conspiracy test lattice dig loop — Mag instrument, not verdict engine.

Loads sovereign-mirror-scaffold conspiracy_lattice preset + knot texts.
Each cycle: **finish one full dig**, then append a Verkle-style bead (parent tip → new tip),
then start the next unit. Never kill mid-answer; no truncated chain handoff.

Self-directed: model may propose public URLs → next cycle queue.
Law: not courtroom proof · rhyme ≠ identity · residual open · no new church.

Stop: `python main.py lattice-loop --stop`
"""
from __future__ import annotations

import hashlib
import json
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT

# ponytail: external preset only — not session DNA; optional spore on host with scaffold path
_SM = (
    Path.home()
    / "Documents"
    / "projects"
    / "worktrees"
    / "sovereign-mirror-scaffold"
)
_PRESET = _SM / "data" / "presets" / "conspiracy_lattice.json"
_KNOTS = _SM / "data" / "knots"

_LOCK = threading.Lock()
_THREAD: threading.Thread | None = None
_STOP = threading.Event()

LAW = [
    "Not courtroom proof — structure map and tensions only.",
    "Rhyme is not identity — similar patterns ≠ same conspiracy proven.",
    "Consent residual stays open — no forced close.",
    "No new church / no recruitment — Mag-stealable method only.",
    "Public/T2 sources only for remote fetches.",
    "Separate OFFICIAL / DISSENT / MATERIAL / INCENTIVE charts.",
]


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def lattice_root() -> Path:
    p = ROOT / "memory" / "improve" / "blast" / "lattice"
    p.mkdir(parents=True, exist_ok=True)
    return p


def load_lattice() -> dict[str, Any]:
    if not _PRESET.is_file():
        return {"ok": False, "error": f"preset missing: {_PRESET}"}
    preset = json.loads(_PRESET.read_text(encoding="utf-8"))
    stack = list(preset.get("default_stack") or [])
    knots: dict[str, str] = {}
    for kid in stack:
        path = _KNOTS / f"{kid}.txt"
        if path.is_file():
            knots[kid] = path.read_text(encoding="utf-8", errors="replace")
    return {
        "ok": True,
        "preset_path": str(_PRESET),
        "id": preset.get("id"),
        "title": preset.get("title"),
        "event_title": preset.get("event_title"),
        "one_line": preset.get("one_line"),
        "law": preset.get("law") or LAW,
        "default_stack": stack,
        "knots": knots,
        "n_knots_loaded": len(knots),
        "explore": preset.get("explore") or [],
    }


def _state_path() -> Path:
    return lattice_root() / "state.json"


def _log_path() -> Path:
    return ROOT / "logs" / "lattice_loop.jsonl"


def read_state() -> dict[str, Any]:
    p = _state_path()
    if not p.is_file():
        return {
            "schema": "lattice_loop_state.v1",
            "run": False,
            "cycle": 0,
            "cursor": 0,
            "dug_knots": [],
            "url_queue": [],
            "url_done": [],
            "last_error": None,
        }
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {"schema": "lattice_loop_state.v1", "run": False, "cycle": 0}


def write_state(st: dict[str, Any]) -> None:
    st = dict(st)
    st["ts"] = _utc()
    st["thread_alive"] = bool(_THREAD and _THREAD.is_alive())
    tip = read_tip()
    st["verkle_tip"] = tip.get("root")
    st["verkle_n"] = tip.get("n_leaves")
    _state_path().write_text(json.dumps(st, indent=2, default=str), encoding="utf-8")
    lines = [
        f"# Lattice dig loop — {st.get('ts')}",
        "",
        f"- run: **{st.get('run')}** · cycle: **{st.get('cycle')}** · cursor: {st.get('cursor')}",
        f"- dug_knots: {len(st.get('dug_knots') or [])} · url_queue: {len(st.get('url_queue') or [])}",
        f"- last_knot: `{st.get('last_knot')}` · last_ok: {st.get('last_ok')}",
        f"- verkle tip: `{tip.get('root')}` · beads: **{tip.get('n_leaves') or 0}**",
        f"- last_error: {st.get('last_error') or '—'}",
        f"- latest dig: `{st.get('last_dig_path') or 'n/a'}`",
        "",
        "## Law (always)",
        "",
    ]
    for law in LAW:
        lines.append(f"- {law}")
    lines.extend(
        [
            "",
            "Chain: `memory/improve/blast/lattice/verkle_chain.jsonl` + `verkle_tip.json`",
            "Stop: `python main.py lattice-loop --stop`",
            "",
        ]
    )
    (lattice_root() / "latest.md").write_text("\n".join(lines), encoding="utf-8")


def _log(event: dict[str, Any]) -> None:
    path = _log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": _utc(), **event}, default=str) + "\n")


def _h(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _chain_path() -> Path:
    return lattice_root() / "verkle_chain.jsonl"


def _tip_path() -> Path:
    return lattice_root() / "verkle_tip.json"


def read_tip() -> dict[str, Any]:
    p = _tip_path()
    if not p.is_file():
        return {"schema": "lattice_verkle_tip.v1", "root": None, "n_leaves": 0, "last_path": None}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {"schema": "lattice_verkle_tip.v1", "root": None, "n_leaves": 0}


def _merkle_root(leaf_hashes: list[str]) -> str:
    if not leaf_hashes:
        return _h(b"lattice-empty")
    layer = leaf_hashes[:]
    while len(layer) > 1:
        nxt = []
        for i in range(0, len(layer), 2):
            left = layer[i]
            right = layer[i + 1] if i + 1 < len(layer) else left
            nxt.append(_h(b"node:" + left.encode() + b":" + right.encode()))
        layer = nxt
    return layer[0]


def append_chain_bead(
    *,
    unit_id: str,
    cycle: int,
    dig_path: Path,
    answer_text: str,
    pack_id: str | None,
    urls: list[str],
) -> dict[str, Any]:
    """Append full dig as a Verkle-style leaf. Parent tip → new tip. Never truncates file."""
    dig_bytes = dig_path.read_bytes() if dig_path.is_file() else answer_text.encode("utf-8")
    leaf_hash = _h(b"lattice-leaf:" + dig_bytes)
    tip = read_tip()
    parent = tip.get("root")
    # collect prior leaf hashes from chain
    leaf_hashes: list[str] = []
    cp = _chain_path()
    if cp.is_file():
        for line in cp.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
                if row.get("leaf_hash"):
                    leaf_hashes.append(str(row["leaf_hash"]))
            except json.JSONDecodeError:
                continue
    leaf_hashes.append(leaf_hash)
    root = _merkle_root(leaf_hashes)
    seq = len(leaf_hashes)
    bead = {
        "schema": "lattice_verkle_bead.v1",
        "seq": seq,
        "ts": _utc(),
        "unit_id": unit_id,
        "cycle": cycle,
        "pack_id": pack_id,
        "dig_path": str(dig_path),
        "answer_chars": len(answer_text or ""),
        "urls": urls,
        "leaf_hash": leaf_hash,
        "parent_root": parent,
        "verkle_root": root,
    }
    with cp.open("a", encoding="utf-8") as f:
        f.write(json.dumps(bead, default=str) + "\n")
    tip_out = {
        "schema": "lattice_verkle_tip.v1",
        "root": root,
        "n_leaves": seq,
        "last_path": str(dig_path),
        "last_unit": unit_id,
        "last_cycle": cycle,
        "last_leaf_hash": leaf_hash,
        "parent_root": parent,
        "updated": _utc(),
        "note": "Lattice instrument chain — not Mag session DNA tip",
    }
    _tip_path().write_text(json.dumps(tip_out, indent=2), encoding="utf-8")
    return tip_out


def _load_parent_bead_full() -> tuple[str | None, str]:
    """Return (parent_root, full previous dig markdown) — full text, no truncate."""
    tip = read_tip()
    parent = tip.get("root")
    last = tip.get("last_path")
    if not last:
        return parent, ""
    p = Path(str(last))
    if not p.is_file():
        return parent, ""
    try:
        return parent, p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return parent, ""


def _worker_chat_full(system: str, user: str) -> str:
    """Long-form dig: high ctx + high predict; do not slice the prompt hard."""
    from langchain_ollama import ChatOllama
    from models.registry import require_model
    from config import ollama_base

    model = require_model("worker", strict=True)
    base = ollama_base()
    # Full answers: allow long generation; wait until model finishes
    llm = ChatOllama(
        model=model,
        temperature=0.25,
        base_url=base,
        num_ctx=32768,
        num_predict=8192,
    )
    resp = llm.invoke([("system", system), ("human", user)])
    content = resp.content
    if isinstance(content, list):
        parts = []
        for p in content:
            if isinstance(p, dict) and "text" in p:
                parts.append(p["text"])
            else:
                parts.append(str(p))
        return "\n".join(parts)
    return str(content)


def normalize_url(u: str) -> str | None:
    """Strip junk; reject truncated / garbage hosts. None = drop from queue."""
    if not u or not isinstance(u, str):
        return None
    u = u.strip().strip("`\"'<>")
    # common model/markdown junk
    u = u.rstrip(".,;:)\\]`'\"")
    u = u.lstrip("<(")
    if "`" in u or " " in u or "\n" in u:
        return None
    if not u.startswith(("http://", "https://")):
        return None
    if "example.com" in u.lower():
        return None
    # truncated paths often end mid-slug or with lone slash + junk
    if u.endswith(("/", "\\")) and "search" not in u.lower():
        # allow trailing slash on short roots only
        path = u.split("://", 1)[-1]
        if path.count("/") <= 1:
            pass  # https://host/ ok
        # still allow normal trailing slash pages
    # obvious garbage hosts / placeholders from 2026-07-29 bag
    bad_hosts = (
        "parlament.com",  # not Belgian parliament; invent host in bag
        "localhost",
        "127.0.0.1",
    )
    try:
        from urllib.parse import urlparse

        host = (urlparse(u).hostname or "").lower()
    except Exception:
        return None
    if not host or any(b in host for b in bad_hosts):
        return None
    # reject ultra-short or cut-off wiki-style paths (…sexual_ without abuse_case)
    if len(u) < 16 or u.endswith(("_", "-", "=")):
        return None
    return u


def _extract_urls(text: str) -> list[str]:
    urls = re.findall(r"https?://[^\s\]\)\"'<>]+", text or "")
    clean: list[str] = []
    for u in urls:
        n = normalize_url(u)
        if n and n not in clean:
            clean.append(n)
    return clean[:20]


def should_enqueue_proposed(
    *,
    proposed: list[str],
    fidelity: dict[str, Any] | None,
    pack: dict[str, Any] | None,
) -> list[str]:
    """Queue gate: drop proposed URLs when dig is ungrounded or sources failed."""
    fid = fidelity or {}
    if fid.get("ungrounded"):
        return []
    if fid.get("recommend") and fid.get("recommend") != "hold":
        # still allow if grounded explicitly true
        g = fid.get("grounding") or {}
        if g.get("applicable") and not g.get("grounded"):
            return []
        if fid.get("ungrounded"):
            return []
    sources = list((pack or {}).get("sources") or [])
    if sources:
        any_ok = any(bool(s.get("ok")) and int(s.get("chars") or 0) >= 200 for s in sources)
        if not any_ok and fid.get("ungrounded", True):
            return []
    out: list[str] = []
    for u in proposed:
        n = normalize_url(u)
        if n and n not in out:
            out.append(n)
    return out[:12]


def _dig_unit(
    *,
    unit_id: str,
    body: str,
    urls: list[str],
    cycle: int,
) -> dict[str, Any]:
    from mag.research_pack import build_research_pack, load_pack, score_fidelity, PACKS

    parent_root, parent_full = _load_parent_bead_full()
    law_block = "\n".join(f"- {x}" for x in LAW)

    # Full prior bead in chain section (no truncation of previous answers)
    parent_section = ""
    if parent_full:
        parent_section = (
            f"## PREVIOUS VERKLE BEAD (full — finish reading before extending)\n"
            f"parent_root: `{parent_root}`\n\n"
            f"{parent_full}\n\n"
            f"## END PREVIOUS BEAD\n\n"
            "Continue the chain: extend residual/tensions/method. Do not erase prior bead.\n\n"
        )

    # Full knot body — no 12k cut
    ask = (
        f"LATTICE DIG unit=`{unit_id}` cycle={cycle}\n"
        f"Instrument: conspiracy test lattice (Sovereign Mirror). NOT Mag DNA.\n"
        f"Chain mode: complete multi-frame dig; then next bead will link via Verkle tip.\n\n"
        f"## LAW (obey)\n{law_block}\n\n"
        f"{parent_section}"
        f"## KNOT / MATERIAL (full)\n{body}\n\n"
        "## JOB (complete — do not abbreviate)\n"
        "1) Structure map: people, claims, docs, residual tensions "
        "(OFFICIAL vs DISSENT vs MATERIAL vs INCENTIVE).\n"
        "2) Mag-stealable method only (filters, charts, residual hold) — not a verdict or church.\n"
        "3) Relate explicitly to previous bead if present (continuities + contradictions).\n"
        "4) List 3–8 PUBLIC URLs for next digs (primary sources preferred).\n"
        "5) Gaps / uncertainty honestly.\n"
        "6) One local Mag next move (existing path/CLI only — no invented commands).\n"
        "Write a full dig. Prefer completeness over brevity.\n"
    )
    built = build_research_pack(
        ask,
        urls=urls[:6],
        title=f"lattice-{unit_id}"[:40],
        elevate_to="local",
        success_criteria=[
            "Obey LAW — not courtroom proof.",
            "Hold multi-frame (official/dissent/material).",
            "If parent bead present, extend the chain explicitly.",
            "Propose only public URLs for next dig.",
            "Complete answer — not a stub.",
        ],
        constraints=[
            "Public/T2 only.",
            "Do not invent Mag CLI flags.",
            "Do not recruit or close residual.",
            "Do not truncate the structure map to one paragraph.",
        ],
    )
    out: dict[str, Any] = {
        "unit_id": unit_id,
        "pack_id": built.get("id"),
        "pack_ok": built.get("ok"),
        "urls_fetched": urls[:6],
        "parent_root": parent_root,
    }
    if not built.get("ok"):
        out["ok"] = False
        out["error"] = built.get("error")
        return out

    pack = load_pack(built.get("json"))
    # Build prompt ourselves with larger source budget + full ask (no 14k hard cut)
    from mag.research_pack import _pack_to_prompt

    prompt = _pack_to_prompt(pack or {}, max_source_chars=12000)
    system = (
        "You dig Mag lattice knots as a Verkle chain of full beads. "
        "Multi-frame hold. Never verdict engine. "
        "Finish the dig completely before stopping. "
        "Cite URLs. Propose next public research URLs. "
        "If a previous bead is provided, read it fully and extend the chain."
    )
    try:
        text = _worker_chat_full(system, prompt)
    except Exception as e:
        out["ok"] = False
        out["error"] = str(e)
        return out

    if not (text or "").strip():
        out["ok"] = False
        out["error"] = "empty model answer"
        return out

    fid = score_fidelity(text, pack or {})
    pack_id = str(built.get("id"))
    ans = PACKS / f"{pack_id}.answer.local.md"
    ans.write_text(
        f"# Lattice dig `{unit_id}`\n\ncycle={cycle}\nparent_root={parent_root}\n\n"
        f"{text}\n\n## Fidelity\n\n{json.dumps(fid, indent=2)}\n",
        encoding="utf-8",
    )
    ungrounded = bool(fid.get("ungrounded"))
    dig_dir = lattice_root() / "digs"
    dig_dir.mkdir(parents=True, exist_ok=True)
    dig_path = dig_dir / f"c{cycle:04d}_{unit_id}.md"
    dig_body = (
        f"# Lattice dig `{unit_id}` cycle {cycle}\n\n"
        f"- pack: `{pack_id}`\n"
        f"- parent_root: `{parent_root}`\n"
        f"- started: {_utc()}\n"
        f"- urls: {urls[:6]}\n"
        f"- answer_chars: {len(text)}\n\n"
        f"## Answer (full)\n\n{text}\n"
    )
    dig_path.write_text(dig_body, encoding="utf-8")

    # Commit bead only after full write
    tip = append_chain_bead(
        unit_id=unit_id,
        cycle=cycle,
        dig_path=dig_path,
        answer_text=text,
        pack_id=pack_id,
        urls=urls[:6],
    )
    # stamp tip onto dig file
    dig_path.write_text(
        dig_body
        + f"\n## Verkle bead\n\n"
        f"- leaf_hash: `{tip.get('last_leaf_hash')}`\n"
        f"- parent_root: `{tip.get('parent_root')}`\n"
        f"- verkle_root: `{tip.get('root')}`\n"
        f"- seq: {tip.get('n_leaves')}\n",
        encoding="utf-8",
    )

    proposed = _extract_urls(text)
    for line in text.splitlines():
        if "http" in line.lower():
            proposed.extend(_extract_urls(line))
    seen: set[str] = set()
    raw_uniq: list[str] = []
    for u in proposed:
        if u not in seen:
            seen.add(u)
            raw_uniq.append(u)
    # Queue gate: no pollution when dig is ungrounded / thin fetch invent
    uniq = should_enqueue_proposed(
        proposed=raw_uniq,
        fidelity=fid,
        pack=pack if isinstance(pack, dict) else None,
    )

    out.update(
        {
            "ok": True,
            "answer_chars": len(text),
            "answer_path": str(ans),
            "dig_path": str(dig_path),
            "fidelity": fid,
            "ungrounded": ungrounded,
            "proposed_urls_raw": raw_uniq[:12],
            "proposed_urls": uniq[:12],
            "verkle_root": tip.get("root"),
            "parent_root": tip.get("parent_root"),
            "leaf_hash": tip.get("last_leaf_hash"),
            "seq": tip.get("n_leaves"),
        }
    )
    return out


def plant_status() -> dict[str, Any]:
    lat = load_lattice()
    st = read_state()
    from mag.blast import ollama_ping

    digs = list((lattice_root() / "digs").glob("*.md")) if (lattice_root() / "digs").is_dir() else []
    digs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    tip = read_tip()
    return {
        "ok": True,
        "mode": "lattice_loop",
        "lattice": {
            "ok": lat.get("ok"),
            "id": lat.get("id"),
            "title": lat.get("title"),
            "n_knots": lat.get("n_knots_loaded"),
            "stack": lat.get("default_stack"),
            "preset_path": lat.get("preset_path"),
            "error": lat.get("error"),
        },
        "state": st,
        "verkle_tip": tip,
        "ollama": ollama_ping(),
        "thread_alive": bool(_THREAD and _THREAD.is_alive()),
        "recent_digs": [str(p.name) for p in digs[:8]],
        "latest": str(lattice_root() / "latest.md"),
        "law": LAW,
    }


def _loop_main(*, cycle_seconds: int, max_cycles: int) -> None:
    lat = load_lattice()
    if not lat.get("ok"):
        st = read_state()
        st["run"] = False
        st["last_error"] = lat.get("error")
        write_state(st)
        _log({"phase": "abort", "error": lat.get("error")})
        return

    stack: list[str] = list(lat.get("default_stack") or [])
    knots: dict[str, str] = dict(lat.get("knots") or {})
    st = read_state()
    st["run"] = True
    st["last_error"] = None
    write_state(st)
    _log({"phase": "start", "n_knots": len(knots), "stack": stack})

    # seed focus for dash
    focus = (
        f"LATTICE LOOP: {lat.get('event_title')}\n"
        f"Preset: {lat.get('id')}\n"
        f"Law: {'; '.join(lat.get('law') or LAW)}\n"
        f"Stack: {', '.join(stack)}\n"
    )
    (lattice_root() / "FOCUS.md").write_text(focus, encoding="utf-8")
    try:
        from mag.blast import write_influence

        write_influence(
            {
                "focus": focus[:2000],
                "notes": "lattice_loop active — digs under memory/improve/blast/lattice/",
            },
            by="lattice_loop",
        )
    except Exception:
        pass

    while not _STOP.is_set():
        st = read_state()
        if not st.get("run"):
            break

        # ollama gate
        from mag.blast import ollama_ping

        ping = ollama_ping()
        if not ping.get("ok"):
            st["last_error"] = f"Ollama down at {ping.get('base')}"
            st["last_ok"] = False
            write_state(st)
            _log({"phase": "ollama_down", "base": ping.get("base")})
            if _STOP.wait(45):
                break
            continue

        cycle = int(st.get("cycle") or 0) + 1
        if max_cycles and cycle > max_cycles:
            st["run"] = False
            st["last_error"] = "max_cycles reached"
            write_state(st)
            break

        url_queue: list[str] = [
            n for n in (normalize_url(x) for x in (st.get("url_queue") or [])) if n
        ]
        url_done: list[str] = list(st.get("url_done") or [])
        dug: list[str] = list(st.get("dug_knots") or [])

        unit_id = ""
        body = ""
        urls: list[str] = []

        # Knots-first: finish each stack knot once before free-roam URL mode.
        # (2026-07-29 bag: URL queue starved stack after 2 knots.)
        stack_complete = bool(stack) and all(k in dug for k in stack)

        if url_queue and stack_complete:
            u = url_queue.pop(0)
            nu = normalize_url(u)
            if not nu:
                st["url_queue"] = url_queue
                write_state(st)
                continue
            unit_id = f"url_{cycle}"
            body = (
                f"Self-directed follow-up URL dig (next bead on lattice Verkle chain).\n"
                f"Parent lattice: {lat.get('event_title')}\n"
                f"URL: {nu}\n\n"
                f"## Core rope (full)\n{knots.get('core_rope') or ''}\n"
            )
            urls = [nu]
            url_done.append(nu)
        else:
            # next undug knot in stack (prefer first missing, else rotate)
            cursor = int(st.get("cursor") or 0)
            if not stack:
                st["run"] = False
                st["last_error"] = "empty stack"
                write_state(st)
                break
            kid = None
            for k in stack:
                if k not in dug:
                    kid = k
                    break
            if kid is None:
                # all knots done; if queue empty, stop cleanly
                if not url_queue:
                    st["run"] = False
                    st["last_error"] = "stack complete and url_queue empty"
                    write_state(st)
                    break
                # queue has items but we needed stack_complete — set and continue
                st["url_queue"] = url_queue
                write_state(st)
                continue
            try:
                cursor = stack.index(kid)
            except ValueError:
                cursor = 0
            st["cursor"] = (cursor + 1) % len(stack)
            unit_id = kid
            body = knots.get(kid) or f"(missing knot text for {kid})"
            urls = _extract_urls(body)
            if kid not in dug:
                dug.append(kid)

        st["cycle"] = cycle
        st["last_knot"] = unit_id
        st["url_queue"] = url_queue
        st["url_done"] = url_done[-50:]
        st["dug_knots"] = dug
        write_state(st)
        _log({"phase": "cycle_start", "cycle": cycle, "unit": unit_id, "urls": urls})

        try:
            result = _dig_unit(unit_id=unit_id, body=body, urls=urls, cycle=cycle)
        except Exception as e:
            result = {"ok": False, "error": str(e), "unit_id": unit_id}

        st = read_state()
        st["last_ok"] = bool(result.get("ok"))
        st["last_error"] = result.get("error")
        st["last_dig_path"] = result.get("dig_path")
        st["last_ungrounded"] = bool(result.get("ungrounded"))
        # enqueue only gated proposed URLs (normalize + grounding)
        q = [n for n in (normalize_url(x) for x in (st.get("url_queue") or [])) if n]
        done = set(st.get("url_done") or [])
        queued = set(q)
        for u in result.get("proposed_urls") or []:
            n = normalize_url(u)
            if n and n not in done and n not in queued and len(q) < 20:
                q.append(n)
                queued.add(n)
        st["url_queue"] = q
        write_state(st)
        _log(
            {
                "phase": "cycle_end",
                "cycle": cycle,
                "unit": unit_id,
                "ok": result.get("ok"),
                "chars": result.get("answer_chars"),
                "proposed_n": len(result.get("proposed_urls") or []),
                "proposed_raw_n": len(result.get("proposed_urls_raw") or []),
                "ungrounded": result.get("ungrounded"),
                "error": result.get("error"),
            }
        )

        if _STOP.wait(float(cycle_seconds)):
            break

    st = read_state()
    st["run"] = False
    write_state(st)
    _log({"phase": "exit", "cycle": st.get("cycle")})


def start_loop(
    *,
    background: bool = True,
    cycle_seconds: int = 90,
    max_cycles: int = 0,
) -> dict[str, Any]:
    global _THREAD
    lat = load_lattice()
    if not lat.get("ok"):
        return {"ok": False, "error": lat.get("error")}

    st = read_state()
    st["run"] = True
    write_state(st)
    _STOP.clear()

    if _THREAD and _THREAD.is_alive():
        return {"ok": True, "already_running": True, "status": plant_status()}

    def target() -> None:
        _loop_main(cycle_seconds=cycle_seconds, max_cycles=max_cycles)

    if background:
        _THREAD = threading.Thread(target=target, name="mag-lattice-loop", daemon=True)
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
        t.join(timeout=8.0)
    return {"ok": True, "stopped": True, "status": plant_status()}
