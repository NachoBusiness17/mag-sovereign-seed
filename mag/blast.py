"""Blast plant: continuous improve dig + human influence dials.

Architecture:
  - Mag + dashboard stay on operator machine (DNA / Verkle local).
  - Ollama may be local or remote via OLLAMA_HOST (Vast SSH tunnel).
  - influence.json is the operator remote control (dash or CLI).
  - Never auto-promotes candidates.
"""
from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from config import CONFIGS_DIR, ROOT

CFG_PATH = CONFIGS_DIR / "blast.yaml"
_LOCK = threading.Lock()
_THREAD: threading.Thread | None = None
_STOP = threading.Event()


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_config() -> dict[str, Any]:
    if not CFG_PATH.is_file():
        return {"enabled": True, "defaults": {}, "safety": {}, "paths": {}}
    data = yaml.safe_load(CFG_PATH.read_text(encoding="utf-8")) or {}
    data.setdefault("defaults", {})
    data.setdefault("safety", {})
    data.setdefault("paths", {})
    return data


def _paths(cfg: dict[str, Any] | None = None) -> dict[str, Path]:
    cfg = cfg or load_config()
    p = cfg.get("paths") or {}
    return {
        "influence": ROOT / (p.get("influence") or "memory/improve/blast/influence.json"),
        "status": ROOT / (p.get("status") or "memory/improve/blast/status.json"),
        "log": ROOT / (p.get("log") or "logs/blast.jsonl"),
        "latest_md": ROOT / (p.get("latest_md") or "memory/improve/blast/latest.md"),
        "root": ROOT / "memory" / "improve" / "blast",
    }


def ensure_dirs(cfg: dict[str, Any] | None = None) -> dict[str, Path]:
    paths = _paths(cfg)
    paths["root"].mkdir(parents=True, exist_ok=True)
    paths["log"].parent.mkdir(parents=True, exist_ok=True)
    return paths


def default_influence(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    d = cfg.get("defaults") or {}
    return {
        "schema": "blast_influence.v1",
        "run": False,
        "paused": False,
        "focus": "",
        "notes": "",
        "dig_minutes": int(d.get("dig_minutes") or 45),
        "max_tickets": int(d.get("max_tickets") or 4),
        "cycle_seconds": int(d.get("cycle_seconds") or 300),
        "scout_every_n_cycles": int(d.get("scout_every_n_cycles") or 2),
        "max_cycles": int(d.get("max_cycles") or 0),
        "updated": _utc(),
        "updated_by": "default",
    }


def _load_influence_unlocked() -> dict[str, Any]:
    paths = ensure_dirs()
    if not paths["influence"].is_file():
        return default_influence()
    try:
        data = json.loads(paths["influence"].read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return default_influence()
        base = default_influence()
        base.update(data)
        return base
    except Exception:
        return default_influence()


def _normalize_influence(cur: dict[str, Any], *, by: str) -> dict[str, Any]:
    cur = dict(cur)
    cur["dig_minutes"] = max(5, min(int(cur.get("dig_minutes") or 45), 180))
    cur["max_tickets"] = max(1, min(int(cur.get("max_tickets") or 4), 12))
    cur["cycle_seconds"] = max(30, min(int(cur.get("cycle_seconds") or 300), 3600))
    cur["scout_every_n_cycles"] = max(1, min(int(cur.get("scout_every_n_cycles") or 2), 20))
    cur["max_cycles"] = max(0, int(cur.get("max_cycles") or 0))
    cur["run"] = bool(cur.get("run"))
    cur["paused"] = bool(cur.get("paused"))
    cur["focus"] = str(cur.get("focus") or "")[:2000]
    cur["notes"] = str(cur.get("notes") or "")[:4000]
    cur["schema"] = "blast_influence.v1"
    cur["updated"] = _utc()
    cur["updated_by"] = by
    return cur


def read_influence() -> dict[str, Any]:
    paths = ensure_dirs()
    with _LOCK:
        cur = _load_influence_unlocked()
        if not paths["influence"].is_file():
            cur = _normalize_influence(cur, by="bootstrap")
            paths["influence"].write_text(json.dumps(cur, indent=2), encoding="utf-8")
        return cur


def write_influence(patch: dict[str, Any], *, by: str = "api") -> dict[str, Any]:
    """Merge patch into influence dials. Returns full influence."""
    allowed = {
        "run",
        "paused",
        "focus",
        "notes",
        "dig_minutes",
        "max_tickets",
        "cycle_seconds",
        "scout_every_n_cycles",
        "max_cycles",
    }
    with _LOCK:
        cur = _load_influence_unlocked()
        for k, v in (patch or {}).items():
            if k in allowed:
                cur[k] = v
        cur = _normalize_influence(cur, by=by)
        paths = ensure_dirs()
        paths["influence"].write_text(json.dumps(cur, indent=2), encoding="utf-8")
        return cur


def read_status() -> dict[str, Any]:
    paths = ensure_dirs()
    if not paths["status"].is_file():
        return {"schema": "blast_status.v1", "state": "idle", "ok": True}
    try:
        return json.loads(paths["status"].read_text(encoding="utf-8"))
    except Exception as e:
        return {"schema": "blast_status.v1", "state": "error", "ok": False, "error": str(e)}


def _write_status(st: dict[str, Any]) -> None:
    paths = ensure_dirs()
    st = dict(st)
    st["schema"] = "blast_status.v1"
    st["ts"] = _utc()
    st["thread_alive"] = bool(_THREAD and _THREAD.is_alive())
    paths["status"].write_text(json.dumps(st, indent=2, default=str), encoding="utf-8")
    # human rollup
    lines = [
        f"# Mag blast status — {st.get('ts')}",
        "",
        f"- state: **{st.get('state')}**",
        f"- cycle: {st.get('cycle', 0)} · digs_ok: {st.get('digs_ok_total', 0)} · fails: {st.get('consecutive_fails', 0)}",
        f"- last_phase: {st.get('last_phase')}",
        f"- ollama: `{st.get('ollama_base')}` tags={st.get('ollama_tags_n')}",
        f"- focus: {(st.get('focus') or '')[:200] or '_none_'}",
        f"- last_error: {st.get('last_error') or '—'}",
        f"- deep_latest: `{st.get('deep_latest') or 'n/a'}`",
        "",
        "Influence: `memory/improve/blast/influence.json`",
        "Stop: dash BLAST → Stop, or `python main.py blast --stop`",
        "",
    ]
    paths["latest_md"].write_text("\n".join(lines), encoding="utf-8")


def _log(event: dict[str, Any]) -> None:
    paths = ensure_dirs()
    row = {"ts": _utc(), **event}
    with paths["log"].open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, default=str) + "\n")


def ollama_ping() -> dict[str, Any]:
    from models.registry import ollama_base_url, ollama_tags

    base = ollama_base_url()
    tags = ollama_tags(timeout=5.0)
    return {
        "ok": bool(tags),
        "base": base,
        "tags_n": len(tags),
        "tags_sample": tags[:12],
    }


def plant_status() -> dict[str, Any]:
    """Dashboard one-shot: influence + status + ollama + field brief pointer."""
    inf = read_influence()
    st = read_status()
    ping = ollama_ping()
    field = ROOT / "memory" / "improve" / "field_brief.md"
    deep = ROOT / "memory" / "improve" / "deep" / "latest.md"
    # top open candidates for promote UI
    tops: list[dict[str, Any]] = []
    try:
        from mag.improve import rank_candidates_for_brief

        ranked = rank_candidates_for_brief(top_n=8, statuses=["new", "hold"])
        for r in ranked[:8]:
            tops.append(
                {
                    "id": r.get("id"),
                    "kind": r.get("kind"),
                    "status": r.get("status"),
                    "score": r.get("_score"),
                    "claim": (r.get("claim") or "")[:140],
                }
            )
    except Exception as e:
        tops = [{"error": str(e)}]
    return {
        "ok": True,
        "influence": inf,
        "status": st,
        "ollama": ping,
        "thread_alive": bool(_THREAD and _THREAD.is_alive()),
        "field_brief": str(field) if field.is_file() else None,
        "deep_latest": str(deep) if deep.is_file() else None,
        "blast_latest": str(ensure_dirs()["latest_md"]),
        "top_candidates": tops,
        "hint": (
            "Set influence.run=true and ensure Ollama (local or OLLAMA_HOST tunnel). "
            "Chat tab = talk; BLAST tab = steer dig plant."
        ),
    }


def _one_cycle(cycle: int, inf: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    """Scout (optional) + deep dig. Inject operator focus into dig via influence file note."""
    from mag.improve import deep_dive, improve_once

    out: dict[str, Any] = {"cycle": cycle, "phases": {}}
    scout_every = int(inf.get("scout_every_n_cycles") or 2)
    do_scout = cycle == 1 or (cycle % scout_every == 0)

    if do_scout:
        try:
            s = improve_once(scout_only=False, dry=False)  # scout+eval+synth
            out["phases"]["scout_eval_synth"] = {
                "ok": s.get("ok"),
                "day": s.get("day"),
                "field_brief": s.get("field_brief"),
            }
        except Exception as e:
            out["phases"]["scout_eval_synth"] = {"ok": False, "error": str(e)}

    # Stash focus so dig asks can pick it up (deep_dive reads candidates; we also pass via notes)
    focus = str(inf.get("focus") or "").strip()
    if focus:
        focus_path = ensure_dirs()["root"] / "FOCUS.md"
        focus_path.write_text(
            f"# Operator blast focus\n\n{focus}\n\n_updated {_utc()}_\n",
            encoding="utf-8",
        )

    try:
        dig = deep_dive(
            minutes=int(inf.get("dig_minutes") or 45),
            max_tickets=int(inf.get("max_tickets") or 4),
            dry=False,
        )
        # If focus set, append a focus-only pack dig after tickets when dig ok or partial
        if focus and dig.get("ok") is not False:
            try:
                dig_focus = _focus_dig(focus, minutes=min(15, int(inf.get("dig_minutes") or 45)))
                dig["focus_dig"] = dig_focus
            except Exception as e:
                dig["focus_dig"] = {"ok": False, "error": str(e)}
        out["phases"]["deep"] = {
            "ok": dig.get("ok"),
            "ok_digs": dig.get("ok_digs"),
            "elapsed_min": dig.get("elapsed_min"),
            "report": dig.get("report"),
            "aborted": dig.get("aborted"),
            "error": dig.get("error"),
        }
        out["ok"] = bool(dig.get("ok"))
        out["deep"] = dig
    except Exception as e:
        out["ok"] = False
        out["phases"]["deep"] = {"ok": False, "error": str(e)}
        out["error"] = str(e)

    return out


def _focus_dig(focus: str, *, minutes: int = 15) -> dict[str, Any]:
    """One research-pack dig driven purely by operator focus text."""
    from mag.research_pack import build_research_pack, load_pack, _pack_to_prompt, score_fidelity, PACKS
    from llm import chat as llm_chat

    # Extract urls from focus if any
    import re

    urls = re.findall(r"https?://[^\s\]\)\"']+", focus)[:6]
    ask = (
        "Operator BLAST focus dig.\n"
        f"Focus:\n{focus[:3000]}\n\n"
        "Extract Mag-stealable practices (trail/residual/pack-first/promote-gate/skill beads). "
        "Refuse product worship. One concrete next Mag move."
    )
    built = build_research_pack(
        ask,
        urls=urls,
        title="blast-focus",
        elevate_to="local",
        success_criteria=[
            "Answer the operator focus directly.",
            "Cite URLs when used.",
            "Name Mag practices vs refuse.",
            "One local next move.",
        ],
    )
    if not built.get("ok"):
        return {"ok": False, "error": built.get("error")}
    pack = load_pack(built.get("json"))
    prompt = _pack_to_prompt(pack or {})
    system = "You are Mag blast digger. Local-first. Cite sources. Be concise."
    try:
        text = llm_chat("worker", system, prompt[:14000], temperature=0.2)
    except Exception as e:
        return {"ok": False, "error": str(e), "pack_id": built.get("id")}
    fid = score_fidelity(text, pack or {})
    ans = PACKS / f"{built.get('id')}.answer.local.md"
    ans.write_text(f"# Blast focus dig\n\n{text}\n\n## Fidelity\n\n{json.dumps(fid, indent=2)}\n", encoding="utf-8")
    # also under blast/
    dest = ensure_dirs()["root"] / "focus_latest.md"
    dest.write_text(f"# Blast focus dig\n\n{text}\n", encoding="utf-8")
    return {
        "ok": True,
        "pack_id": built.get("id"),
        "answer_path": str(ans),
        "focus_md": str(dest),
        "fidelity": fid,
        "chars": len(text),
        "minutes_budget": minutes,
    }


def _loop_main() -> None:
    cfg = load_config()
    safety = cfg.get("safety") or {}
    cycle = 0
    digs_ok_total = 0
    consecutive_fails = 0
    max_fails = int(safety.get("max_consecutive_fails") or 3)

    _write_status(
        {
            "state": "starting",
            "cycle": 0,
            "digs_ok_total": 0,
            "consecutive_fails": 0,
            "last_phase": "start",
            "ollama_base": ollama_ping().get("base"),
        }
    )
    _log({"phase": "start"})

    while not _STOP.is_set():
        inf = read_influence()
        if not inf.get("run"):
            _write_status(
                {
                    "state": "stopped",
                    "cycle": cycle,
                    "digs_ok_total": digs_ok_total,
                    "consecutive_fails": consecutive_fails,
                    "last_phase": "influence.run=false",
                    "focus": inf.get("focus"),
                    **{k: ollama_ping().get(k) for k in ()},
                    "ollama_base": ollama_ping().get("base"),
                    "ollama_tags_n": ollama_ping().get("tags_n"),
                }
            )
            break

        if inf.get("paused"):
            _write_status(
                {
                    "state": "paused",
                    "cycle": cycle,
                    "digs_ok_total": digs_ok_total,
                    "consecutive_fails": consecutive_fails,
                    "last_phase": "paused",
                    "focus": inf.get("focus"),
                    "ollama_base": ollama_ping().get("base"),
                    "ollama_tags_n": ollama_ping().get("tags_n"),
                }
            )
            _STOP.wait(5.0)
            continue

        ping = ollama_ping()
        if safety.get("require_ollama", True) and not ping.get("ok"):
            consecutive_fails += 1
            _write_status(
                {
                    "state": "waiting_ollama",
                    "cycle": cycle,
                    "digs_ok_total": digs_ok_total,
                    "consecutive_fails": consecutive_fails,
                    "last_phase": "ollama_down",
                    "last_error": f"Ollama not reachable at {ping.get('base')}",
                    "ollama_base": ping.get("base"),
                    "ollama_tags_n": 0,
                    "focus": inf.get("focus"),
                }
            )
            _log({"phase": "ollama_down", "base": ping.get("base")})
            if safety.get("abort_on_hard_ollama_fail", True) and consecutive_fails >= max_fails:
                write_influence({"run": False, "paused": False}, by="blast_abort_ollama")
                _write_status(
                    {
                        "state": "aborted",
                        "cycle": cycle,
                        "digs_ok_total": digs_ok_total,
                        "consecutive_fails": consecutive_fails,
                        "last_phase": "abort_ollama",
                        "last_error": f"Ollama down {consecutive_fails}x — stopped",
                        "ollama_base": ping.get("base"),
                    }
                )
                break
            _STOP.wait(30.0)
            continue

        cycle += 1
        max_cycles = int(inf.get("max_cycles") or 0)
        if max_cycles and cycle > max_cycles:
            write_influence({"run": False}, by="blast_max_cycles")
            _write_status(
                {
                    "state": "completed",
                    "cycle": cycle,
                    "digs_ok_total": digs_ok_total,
                    "last_phase": "max_cycles",
                    "ollama_base": ping.get("base"),
                    "ollama_tags_n": ping.get("tags_n"),
                    "focus": inf.get("focus"),
                }
            )
            break

        _write_status(
            {
                "state": "running",
                "cycle": cycle,
                "digs_ok_total": digs_ok_total,
                "consecutive_fails": consecutive_fails,
                "last_phase": "cycle_start",
                "ollama_base": ping.get("base"),
                "ollama_tags_n": ping.get("tags_n"),
                "focus": inf.get("focus"),
                "dig_minutes": inf.get("dig_minutes"),
                "max_tickets": inf.get("max_tickets"),
            }
        )
        _log({"phase": "cycle_start", "cycle": cycle, "focus": (inf.get("focus") or "")[:200]})

        result = _one_cycle(cycle, inf, cfg)
        if result.get("ok"):
            digs_ok_total += int((result.get("phases") or {}).get("deep", {}).get("ok_digs") or 1)
            consecutive_fails = 0
        else:
            consecutive_fails += 1

        deep_report = ((result.get("phases") or {}).get("deep") or {}).get("report")
        _write_status(
            {
                "state": "running",
                "cycle": cycle,
                "digs_ok_total": digs_ok_total,
                "consecutive_fails": consecutive_fails,
                "last_phase": "cycle_end",
                "last_ok": result.get("ok"),
                "last_error": result.get("error")
                or ((result.get("phases") or {}).get("deep") or {}).get("error"),
                "deep_latest": deep_report,
                "ollama_base": ping.get("base"),
                "ollama_tags_n": ping.get("tags_n"),
                "focus": inf.get("focus"),
            }
        )
        _log({"phase": "cycle_end", "cycle": cycle, "ok": result.get("ok"), "result": {
            k: result.get(k) for k in ("ok", "error", "phases")
        }})

        if consecutive_fails >= max_fails and safety.get("abort_on_hard_ollama_fail", True):
            write_influence({"run": False}, by="blast_abort_fails")
            _write_status(
                {
                    "state": "aborted",
                    "cycle": cycle,
                    "digs_ok_total": digs_ok_total,
                    "consecutive_fails": consecutive_fails,
                    "last_phase": "abort_fails",
                    "last_error": f"{consecutive_fails} consecutive cycle fails",
                    "ollama_base": ping.get("base"),
                }
            )
            break

        # Wait between cycles; wake early on stop
        wait_s = float(inf.get("cycle_seconds") or 300)
        _STOP.wait(wait_s)

    _log({"phase": "exit", "cycle": cycle, "digs_ok_total": digs_ok_total})
    st = read_status()
    if st.get("state") == "running":
        st["state"] = "idle"
        _write_status(st)


def start_blast(*, background: bool = True) -> dict[str, Any]:
    """Start blast loop if not already running. Sets influence.run=true."""
    global _THREAD
    cfg = load_config()
    if not cfg.get("enabled", True):
        return {"ok": False, "error": "blast disabled in configs/blast.yaml"}

    write_influence({"run": True, "paused": False}, by="start_blast")
    _STOP.clear()

    if _THREAD and _THREAD.is_alive():
        return {"ok": True, "already_running": True, "status": plant_status()}

    if background:
        _THREAD = threading.Thread(target=_loop_main, name="mag-blast", daemon=True)
        _THREAD.start()
        time.sleep(0.3)
        return {"ok": True, "started": True, "background": True, "status": plant_status()}

    # foreground (CLI --run without --bg)
    _loop_main()
    return {"ok": True, "started": True, "background": False, "status": plant_status()}


def stop_blast() -> dict[str, Any]:
    write_influence({"run": False, "paused": False}, by="stop_blast")
    _STOP.set()
    t = _THREAD
    if t and t.is_alive():
        t.join(timeout=5.0)
    _write_status(
        {
            **read_status(),
            "state": "stopped",
            "last_phase": "stop_blast",
            "ollama_base": ollama_ping().get("base"),
            "ollama_tags_n": ollama_ping().get("tags_n"),
        }
    )
    return {"ok": True, "stopped": True, "status": plant_status()}


def pause_blast(paused: bool = True) -> dict[str, Any]:
    write_influence({"paused": bool(paused), "run": True}, by="pause_blast")
    return {"ok": True, "paused": bool(paused), "status": plant_status()}
