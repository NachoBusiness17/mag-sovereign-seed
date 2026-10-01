"""Run object + live trail — mid-run continuity substrate (feature compose).

Contracts stolen/enhanced from model_tesuji (K3):
  - trail integrity: reasoning/tool cores re-injected (not dropped)
  - seat purity: one seat per run; change seat → new run
  - proactivity dial: narrow|normal|wide on the run object
  - pack-first: trail excerpt rides context-pack, not full chat

Ontology (DNA law): residual remains cold SessionEnd DNA.
  memory/runs/ is warm-mid for one goal trajectory — not a second DNA throne.

Files:
  memory/runs/{run_id}/run.json
  memory/runs/{run_id}/trail.jsonl
  memory/runs/active.json
"""
from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT

RUNS = ROOT / "memory" / "runs"
ACTIVE = RUNS / "active.json"
RELATED = RUNS / "related_runs.jsonl"
SCHEMA_RUN = "mag_run.v1"
SCHEMA_EVENT = "mag_trail_event.v1"
SCHEMA_ACTIVE = "mag_active_run.v1"
SCHEMA_BASE = "mag_base.v1"
SCHEMA_DRIFT = "mag_drift.v1"
PROACTIVITY = frozenset({"narrow", "normal", "wide"})
# Drift kinds on agent_probe cores (architecture-enforced field set)
DRIFT_KINDS = frozenset(
    {"add", "contradict", "open_loop", "gap", "severity", "note", "finding", "ready"}
)
AGENT_PROBE_KINDS = frozenset({"agent_probe", "drift"})
CORE_MAX_BYTES = 2048

# Canonical seats only (normalize L0–L3 into these)
_SEAT_MAP = {
    "local": "local",
    "l0": "local",
    "remote": "remote",
    "l1": "remote",
    "grok_tui": "grok_tui",
    "grok": "grok_tui",
    "l2": "grok_tui",
    "hermes": "hermes",
    "human": "human",
    "l3": "human",
    "wait": "human",
    "cursor": "cursor",
    "cursor_ide": "cursor",
    "composer": "cursor",
    "research": "research",
}


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug(text: str, n: int = 40) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", (text or "run").strip().lower()).strip("-")
    return (s[:n] or "run").rstrip("-")


def normalize_seat(seat: str | None) -> str:
    key = (seat or "local").strip().lower().replace("-", "_")
    if key in _SEAT_MAP:
        return _SEAT_MAP[key]
    # bare aliases
    if key in ("ollama", "janitor", "clerk"):
        return "local"
    return "local" if not key else key if key in _SEAT_MAP.values() else "local"


def cap_core(core: Any) -> dict[str, Any] | None:
    """Bound core size so trail never becomes chat history."""
    if core is None:
        return None
    if not isinstance(core, dict):
        core = {"text": str(core)[:500]}
    raw = json.dumps(core, ensure_ascii=False)
    if len(raw.encode("utf-8")) <= CORE_MAX_BYTES:
        return core
    # progressive shrink of string values
    out: dict[str, Any] = {}
    for k, v in core.items():
        if isinstance(v, str):
            out[str(k)[:64]] = v[:400]
        elif isinstance(v, (int, float, bool)) or v is None:
            out[str(k)[:64]] = v
        else:
            out[str(k)[:64]] = str(v)[:200]
    out["_truncated"] = True
    raw2 = json.dumps(out, ensure_ascii=False)
    if len(raw2.encode("utf-8")) > CORE_MAX_BYTES:
        return {"type": "truncated", "text": raw2[:600], "_truncated": True}
    return out


def _run_dir(run_id: str) -> Path:
    return RUNS / run_id


def _run_path(run_id: str) -> Path:
    return _run_dir(run_id) / "run.json"


def _trail_path(run_id: str) -> Path:
    return _run_dir(run_id) / "trail.jsonl"


def _progress_path(run_id: str) -> Path:
    return _run_dir(run_id) / "progress.md"


def ensure_runs_root() -> None:
    RUNS.mkdir(parents=True, exist_ok=True)


def load_active() -> dict[str, Any] | None:
    if not ACTIVE.is_file():
        return None
    try:
        data = json.loads(ACTIVE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def load_run(run_id: str | None = None) -> dict[str, Any] | None:
    if not run_id:
        act = load_active()
        run_id = (act or {}).get("run_id")
    if not run_id:
        return None
    p = _run_path(str(run_id))
    if not p.is_file():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def save_run(run: dict[str, Any]) -> Path:
    ensure_runs_root()
    rid = str(run["run_id"])
    d = _run_dir(rid)
    d.mkdir(parents=True, exist_ok=True)
    p = _run_path(rid)
    p.write_text(json.dumps(run, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return p


def set_active(run_id: str | None) -> None:
    ensure_runs_root()
    if not run_id:
        if ACTIVE.is_file():
            ACTIVE.unlink()
        return
    ACTIVE.write_text(
        json.dumps({"schema": SCHEMA_ACTIVE, "run_id": run_id, "ts": _utc()}, indent=2)
        + "\n",
        encoding="utf-8",
    )


def repair_active() -> dict[str, Any]:
    """Clear active pointer if run missing or not open."""
    act = load_active()
    if not act or not act.get("run_id"):
        return {"ok": True, "repaired": False}
    rid = str(act["run_id"])
    run = load_run(rid)
    if not run:
        set_active(None)
        return {"ok": True, "repaired": True, "reason": "orphan_active", "run_id": rid}
    if run.get("status") != "open":
        set_active(None)
        return {
            "ok": True,
            "repaired": True,
            "reason": f"status_{run.get('status')}",
            "run_id": rid,
        }
    return {"ok": True, "repaired": False, "run_id": rid}


def _default_session_id() -> str:
    """Bind run to day bead when possible (game: past/future same information set)."""
    latest = ROOT / "memory" / "biography" / "latest_session.json"
    if latest.is_file():
        try:
            sid = (json.loads(latest.read_text(encoding="utf-8")) or {}).get("session_id")
            if sid:
                return str(sid)
        except Exception:
            pass
    bj = ROOT / "memory" / "bonds_active.json"
    if bj.is_file():
        try:
            sid = (json.loads(bj.read_text(encoding="utf-8")) or {}).get("session_id")
            if sid:
                return str(sid)
        except Exception:
            pass
    return ""


def _tip_root_short() -> tuple[str, str, int | None]:
    """Return (root_short, last_filename, n_leaves) from verkle tip if present."""
    tip_path = ROOT / "memory" / "biography" / "verkle_tip.json"
    if not tip_path.is_file():
        return "", "", None
    try:
        tip = json.loads(tip_path.read_text(encoding="utf-8"))
    except Exception:
        return "", "", None
    root = str(tip.get("root") or "")
    short = (root[:16] + "…") if len(root) > 16 else root
    n = tip.get("n_leaves")
    try:
        n_leaves = int(n) if n is not None else None
    except (TypeError, ValueError):
        n_leaves = None
    return short, str(tip.get("last_filename") or ""), n_leaves


def _git_head(cwd: Path | None = None) -> str:
    """Best-effort HEAD short SHA; empty if not a git work tree."""
    import subprocess

    try:
        r = subprocess.run(
            ["git", "rev-parse", "--short=12", "HEAD"],
            cwd=str(cwd or ROOT),
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
        if r.returncode == 0:
            return (r.stdout or "").strip()[:16]
    except Exception:
        pass
    return ""


def snapshot_base(
    *,
    git_sha: str = "",
    pack_ts: str = "",
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Freeze a base graph commitment for multi-agent drift (stateless seats).

    Law: COORDINATION_ELIAS_ROPE + Lessig architecture — base on boundary;
    seats LOAD it and FILE drift against base_id only.
    """
    tip_short, last_leaf, n_leaves = _tip_root_short()
    git = (git_sha or "").strip() or _git_head()
    ts = (pack_ts or "").strip() or _utc()
    material: dict[str, Any] = {
        "tip": tip_short,
        "leaf": last_leaf,
        "n_leaves": n_leaves,
        "git": git,
        "ts": ts,
    }
    if extra:
        for k, v in list(extra.items())[:8]:
            material[str(k)[:32]] = str(v)[:120]
    digest = hashlib.sha256(
        json.dumps(material, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    return {
        "schema": SCHEMA_BASE,
        "base_id": digest[:16],
        "tip_root_short": tip_short,
        "last_filename": last_leaf,
        "n_leaves": n_leaves,
        "git_sha": git,
        "pack_ts": ts,
        "created": _utc(),
        "note": "frozen base for drift; tip not advanced by trail",
    }


def ensure_run_base(run_id: str | None = None, *, git_sha: str = "") -> dict[str, Any]:
    """Return run.base; snapshot once for legacy runs missing base."""
    run = load_run(run_id)
    if not run:
        return {"ok": False, "error": "no_run"}
    base = run.get("base")
    if isinstance(base, dict) and base.get("base_id"):
        return {"ok": True, "base": base, "run_id": run.get("run_id"), "created": False}
    base = snapshot_base(git_sha=git_sha)
    run["base"] = base
    run["updated"] = _utc()
    save_run(run)
    return {"ok": True, "base": base, "run_id": run.get("run_id"), "created": True}


def normalize_drift_kind(kind: str | None) -> str:
    k = (kind or "note").strip().lower().replace("-", "_")
    if k in DRIFT_KINDS:
        return k
    aliases = {
        "bug": "finding",
        "issue": "finding",
        "conflict": "contradict",
        "loop": "open_loop",
        "sev": "severity",
    }
    return aliases.get(k, "note")


def list_drifts(
    run_id: str | None = None,
    *,
    last_n: int = 50,
) -> dict[str, Any]:
    """Collect agent_probe / drift cores for fold / time-travel compare."""
    run = load_run(run_id)
    if not run:
        return {"ok": False, "error": "no_run", "drifts": []}
    base = run.get("base") if isinstance(run.get("base"), dict) else {}
    base_id = str(base.get("base_id") or "")
    drifts: list[dict[str, Any]] = []
    for e in read_trail(str(run["run_id"]), last_n=max(last_n, 80)):
        if e.get("kind") not in AGENT_PROBE_KINDS:
            continue
        core = e.get("core") if isinstance(e.get("core"), dict) else {}
        drifts.append(
            {
                "seq": e.get("seq"),
                "ts": e.get("ts"),
                "summary": e.get("summary"),
                "base_id": core.get("base_id") or base_id,
                "label": core.get("label"),
                "locus": core.get("locus") or core.get("label"),
                "drift_kind": core.get("drift_kind") or "note",
                "text": core.get("text"),
                "evidence": core.get("evidence"),
            }
        )
    by_locus: dict[str, int] = {}
    for d in drifts:
        loc = str(d.get("locus") or "?")
        by_locus[loc] = by_locus.get(loc, 0) + 1
    return {
        "ok": True,
        "run_id": run.get("run_id"),
        "base_id": base_id,
        "base": base,
        "n": len(drifts),
        "by_locus": by_locus,
        "drifts": drifts[-last_n:],
    }


def start_run(
    goal: str,
    *,
    seat: str = "local",
    proactivity: str = "narrow",
    pack_ref: str = "",
    session_id: str = "",
    max_tool_calls: int = 32,
    write_paths: list[str] | None = None,
    read_paths: list[str] | None = None,
    never_remote: bool = False,
    force: bool = False,
    git_sha: str = "",
) -> dict[str, Any]:
    """Open a run. Freezes base (tip + optional git) for multi-agent drift."""
    repair_active()
    seat = normalize_seat(seat)
    proactivity = (proactivity or "narrow").strip().lower()
    if proactivity not in PROACTIVITY:
        proactivity = "narrow"
    if not (session_id or "").strip():
        session_id = _default_session_id()

    prior = load_active()
    if prior and prior.get("run_id") and not force:
        open_run = load_run(str(prior["run_id"]))
        if open_run and open_run.get("status") == "open":
            return {
                "ok": False,
                "error": "active_run_exists",
                "active_run_id": prior["run_id"],
                "hint": "trail close  OR  trail start --force (closes prior)",
            }

    if prior and force and prior.get("run_id"):
        close_run(str(prior["run_id"]), reason="superseded")

    rid = (
        f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
        f"-{_slug(goal)}-{uuid.uuid4().hex[:6]}"
    )
    base = snapshot_base(git_sha=git_sha)
    run: dict[str, Any] = {
        "schema": SCHEMA_RUN,
        "run_id": rid,
        "status": "open",
        "goal": (goal or "").strip()[:2000],
        "seat": seat,
        "seat_locked": True,
        "proactivity": proactivity,
        "pack_ref": pack_ref or "",
        "session_id": session_id or "",
        "base": base,
        "tier_max": "T1" if never_remote else "T2",
        "bounds": {
            "max_tool_calls": int(max_tool_calls),
            "write_paths": list(write_paths or []),
            "read_paths": list(read_paths or []),
        },
        "privacy": {
            "never_remote": bool(never_remote),
            "note": "if true, remote seat forbidden even with pack",
        },
        "n_events": 0,
        "n_tool_calls": 0,
        "created": _utc(),
        "updated": _utc(),
        "closed": None,
        "close_reason": None,
        "compose": {
            "steals": [
                "trail_integrity",
                "seat_purity",
                "proactivity_dial",
                "pack_first",
                "base_drift",
            ],
            "source": "feature-compose-001 / coordination-elias-rope-001",
        },
    }
    save_run(run)
    _trail_path(rid).write_text("", encoding="utf-8")
    set_active(rid)
    init_core = {
        "type": "constraint",
        "text": (
            f"goal={(run['goal'] or '')[:300]} | seat={seat} | "
            f"proactivity={proactivity} | max_tools={max_tool_calls} | "
            f"never_remote={bool(never_remote)} | session={session_id or '—'} | "
            f"base_id={base.get('base_id')}"
        ),
        "bounds": run["bounds"],
        "privacy": run["privacy"],
        "base_id": base.get("base_id"),
        "base": {
            "base_id": base.get("base_id"),
            "tip": base.get("tip_root_short"),
            "git": base.get("git_sha"),
        },
    }
    append_event(
        "run_start",
        f"start seat={seat} proactivity={proactivity} base={base.get('base_id')}",
        run_id=rid,
        seat=seat,
        core=init_core,
    )
    write_progress_md(rid, phase="start")
    return {"ok": True, "run": load_run(rid), "base": base}


def write_progress_md(run_id: str, *, phase: str = "update") -> Path | None:
    """Artifact handoff across windows — Verkle pre-leaf / Anthropic progress analog."""
    run = load_run(run_id)
    if not run:
        return None
    rid = str(run["run_id"])
    events = read_trail(rid, last_n=40)
    cores = [e for e in events if e.get("core")]
    decisions = [
        e for e in events if e.get("kind") in ("decision", "run_start", "run_close", "dispatch")
    ]
    lines = [
        f"# Run progress — `{rid}`",
        "",
        f"_phase: {phase} · written: {_utc()}_",
        "",
        "## Card",
        "",
        f"- **goal:** {(run.get('goal') or '')[:500]}",
        f"- **seat:** `{run.get('seat')}` (locked={run.get('seat_locked')})",
        f"- **proactivity:** `{run.get('proactivity')}`",
        f"- **status:** `{run.get('status')}` · close_reason=`{run.get('close_reason') or '—'}`",
        f"- **session_id:** `{run.get('session_id') or '—'}`",
        f"- **run_commit:** `{(run.get('run_commit') or '—')[:24]}`",
        f"- **base_id:** `{(run.get('base') or {}).get('base_id') or '—'}`",
        f"- **n_events / tools:** {run.get('n_events')} / {run.get('n_tool_calls')}",
        "",
        "## Bounds (initializer)",
        "",
        f"```json",
        json.dumps(
            {
                "bounds": run.get("bounds"),
                "privacy": run.get("privacy"),
                "tier_max": run.get("tier_max"),
                "base": run.get("base"),
            },
            indent=2,
        ),
        "```",
        "",
        "## Cores to re-inject",
        "",
    ]
    if not cores:
        lines.append("- _(none yet)_")
    for e in cores[-12:]:
        lines.append(
            f"- [{e.get('seq')}|{e.get('kind')}] {e.get('summary') or ''} · "
            f"`{json.dumps(e.get('core'), ensure_ascii=False)[:180]}`"
        )
    lines.extend(["", "## Decisions / hops", ""])
    if not decisions:
        lines.append("- _(none)_")
    for e in decisions[-16:]:
        lines.append(f"- [{e.get('seq')}|{e.get('kind')}] {e.get('summary') or ''}")
    lines.extend(
        [
            "",
            "## Lattice",
            "",
            "- Progress is **warm pre-leaf** — not verkle tip.",
            "- On close: related_runs edge + residual edges; tip stays session-only.",
            "- Next session: bonds + this file if still open path needed.",
            "",
        ]
    )
    path = _progress_path(rid)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def file_agent_core(
    label: str,
    summary: str,
    *,
    run_id: str | None = None,
    findings: Any = None,
    text: str = "",
    seat: str | None = None,
    locus: str = "",
    drift_kind: str = "note",
    evidence: str = "",
    base_id: str = "",
) -> dict[str, Any]:
    """FILE multi-agent drift into warm trail (Elias rope).

    Architecture: stamps run base_id; mismatched base_id rejected.
    Does not advance Verkle tip; not cold DNA; not L3 approval.
    """
    run = load_run(run_id)
    if not run:
        return {"ok": False, "error": "no_open_run", "hint": 'trail start "goal"'}
    if run.get("status") != "open":
        return {
            "ok": False,
            "error": "run_not_open",
            "run_id": run.get("run_id"),
            "status": run.get("status"),
        }

    ensured = ensure_run_base(str(run["run_id"]))
    base = (ensured.get("base") or {}) if ensured.get("ok") else {}
    rid_base = str(base.get("base_id") or "")
    if not rid_base:
        return {"ok": False, "error": "no_base_id", "hint": "trail start freezes base"}

    want = (base_id or "").strip()
    if want and want != rid_base:
        return {
            "ok": False,
            "error": "base_id_mismatch",
            "run_base_id": rid_base,
            "attempted_base_id": want,
            "hint": "reload pack / trail status; do not invent base",
        }

    lab = (label or "agent").strip()[:64] or "agent"
    loc = (locus or lab).strip()[:200] or lab
    dkind = normalize_drift_kind(drift_kind)
    core: dict[str, Any] = {
        "schema": SCHEMA_DRIFT,
        "type": "agent_probe",
        "base_id": rid_base,
        "label": lab,
        "locus": loc,
        "drift_kind": dkind,
        "text": (text or summary or "")[:600],
    }
    if evidence:
        core["evidence"] = str(evidence)[:500]
    if findings is not None:
        if isinstance(findings, (list, dict)):
            core["findings"] = findings
        else:
            core["findings"] = str(findings)[:400]
    return append_event(
        "agent_probe",
        summary or f"drift:{dkind}:{lab}",
        run_id=str(run["run_id"]),
        seat=seat,
        core=core,
        tool=lab,
    )


def append_event(
    kind: str,
    summary: str,
    *,
    run_id: str | None = None,
    seat: str | None = None,
    core: dict[str, Any] | None = None,
    tool: str | None = None,
    content: str = "",
) -> dict[str, Any]:
    """Append trail event. Enforces seat purity; agent_probe cores stamp base_id."""
    run = load_run(run_id)
    if not run:
        return {"ok": False, "error": "no_open_run", "hint": 'trail start "goal"'}
    if run.get("status") != "open":
        return {
            "ok": False,
            "error": "run_not_open",
            "run_id": run.get("run_id"),
            "status": run.get("status"),
        }

    rid = str(run["run_id"])
    locked = normalize_seat(str(run.get("seat") or "local"))
    if seat is not None and run.get("seat_locked"):
        attempted = normalize_seat(seat)
        if seat.strip() and attempted != locked:
            return {
                "ok": False,
                "error": "seat_purity_violation",
                "run_id": rid,
                "locked_seat": locked,
                "attempted_seat": attempted,
                "hint": "close this run and trail start with new seat (no mid-run swap)",
            }

    kind_s = (kind or "note").strip()[:64]
    # Lessig architecture: agent_probe cores must carry run base_id
    if kind_s in AGENT_PROBE_KINDS:
        ensured = ensure_run_base(rid)
        rid_base = str(((ensured.get("base") or {}) if ensured.get("ok") else {}).get("base_id") or "")
        if not rid_base:
            return {"ok": False, "error": "no_base_id", "hint": "trail start freezes base"}
        if core is None:
            core = {}
        if not isinstance(core, dict):
            core = {"text": str(core)[:400]}
        else:
            core = dict(core)
        want = str(core.get("base_id") or "").strip()
        if want and want != rid_base:
            return {
                "ok": False,
                "error": "base_id_mismatch",
                "run_base_id": rid_base,
                "attempted_base_id": want,
                "hint": "drift must cite the frozen run base",
            }
        core["base_id"] = rid_base
        if not core.get("type"):
            core["type"] = "agent_probe"
        if not core.get("schema"):
            core["schema"] = SCHEMA_DRIFT
        if not core.get("drift_kind"):
            core["drift_kind"] = "note"
        if not core.get("locus") and core.get("label"):
            core["locus"] = core.get("label")

    core_capped = cap_core(core) if core is not None else None

    ev: dict[str, Any] = {
        "schema": SCHEMA_EVENT,
        "ts": _utc(),
        "run_id": rid,
        "seq": int(run.get("n_events") or 0) + 1,
        "kind": kind_s,
        "summary": (summary or "")[:1000],
        "seat": locked,
    }
    if tool:
        ev["tool"] = tool[:128]
    if content:
        ev["content"] = content[:8000]
    if core_capped is not None:
        ev["core"] = core_capped

    tp = _trail_path(rid)
    with tp.open("a", encoding="utf-8") as f:
        f.write(json.dumps(ev, ensure_ascii=False) + "\n")

    run["n_events"] = ev["seq"]
    run["updated"] = _utc()
    if kind in ("tool", "tool_call", "tool_result") or tool:
        run["n_tool_calls"] = int(run.get("n_tool_calls") or 0) + 1
        max_t = int((run.get("bounds") or {}).get("max_tool_calls") or 0)
        if max_t and run["n_tool_calls"] > max_t:
            try:
                from mag.run_worth import gate_before_truncate

                gate = gate_before_truncate(run, trail_events=read_trail(rid, last_n=80))
            except Exception:
                gate = {"allow_continue": False, "close_reason": "max_tool_calls"}
            if gate.get("allow_continue"):
                new_max = int(gate.get("new_max_tool_calls") or max_t)
                bounds = dict(run.get("bounds") or {})
                bounds["max_tool_calls"] = new_max
                run["bounds"] = bounds
                run["worth_defer_count"] = int(run.get("worth_defer_count") or 0) + 1
                run["worth_verdict"] = gate.get("verdict")
                save_run(run)
            else:
                run["status"] = "blocked"
                run["close_reason"] = str(gate.get("close_reason") or "max_tool_calls")
                run["worth_verdict"] = gate.get("verdict")
                run["closed"] = _utc()
                save_run(run)
                set_active(None)
                return {
                    "ok": False,
                    "error": run["close_reason"],
                    "event": ev,
                    "run": run,
                    "worth_gate": gate,
                }
    save_run(run)
    return {"ok": True, "event": ev, "run_id": rid, "n_events": run["n_events"]}


def check_seat(seat: str, *, run_id: str | None = None) -> dict[str, Any]:
    repair_active()
    run = load_run(run_id)
    if not run or run.get("status") != "open":
        return {"ok": True, "active": False, "note": "no open run"}
    locked = normalize_seat(str(run.get("seat") or ""))
    attempted = normalize_seat(seat)
    ok = attempted == locked or not (seat or "").strip()
    return {
        "ok": ok,
        "active": True,
        "run_id": run.get("run_id"),
        "locked_seat": locked,
        "attempted_seat": attempted,
        "error": None if ok else "seat_purity_violation",
    }


def _run_commit(run: dict[str, Any]) -> str:
    """Hash run card + trail bytes for bead-ready commit (not tip)."""
    rid = str(run.get("run_id") or "")
    trail_raw = b""
    tp = _trail_path(rid)
    if tp.is_file():
        trail_raw = tp.read_bytes()
    card = {
        "run_id": rid,
        "goal": run.get("goal"),
        "seat": run.get("seat"),
        "proactivity": run.get("proactivity"),
        "n_events": run.get("n_events"),
        "close_reason": run.get("close_reason"),
        "closed": run.get("closed"),
    }
    body = json.dumps(card, sort_keys=True, default=str).encode("utf-8") + b"|" + trail_raw
    return hashlib.sha256(b"run:" + body).hexdigest()


def related_run_card(run: dict[str, Any]) -> dict[str, Any]:
    """Lattice edge card — child of day bead, never a tip leaf."""
    rid = str(run.get("run_id") or "")
    return {
        "schema": "mag_related_run.v1",
        "run_id": rid,
        "goal": (run.get("goal") or "")[:300],
        "seat": run.get("seat"),
        "proactivity": run.get("proactivity"),
        "status": run.get("status"),
        "close_reason": run.get("close_reason"),
        "n_events": run.get("n_events"),
        "n_tool_calls": run.get("n_tool_calls"),
        "session_id": run.get("session_id") or "",
        "run_commit": run.get("run_commit") or "",
        "path": str(_run_dir(rid)),
        "trail_path": str(_trail_path(rid)),
        "closed": run.get("closed"),
        "compose": (run.get("compose") or {}).get("steals"),
    }


def append_related_run(card: dict[str, Any]) -> None:
    ensure_runs_root()
    with RELATED.open("a", encoding="utf-8") as f:
        f.write(json.dumps(card, ensure_ascii=False) + "\n")


def list_related_runs(*, last_n: int = 8) -> list[dict[str, Any]]:
    if not RELATED.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for ln in RELATED.read_text(encoding="utf-8", errors="replace").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            rows.append(json.loads(ln))
        except Exception:
            continue
    return rows[-max(1, last_n) :]


def close_run(run_id: str | None = None, *, reason: str = "done") -> dict[str, Any]:
    run = load_run(run_id)
    if not run:
        return {"ok": False, "error": "no_run"}
    rid = str(run["run_id"])
    if run.get("status") == "open":
        # write close event without re-entering purity path with wrong seat
        append_event(
            "run_close",
            f"close reason={reason}",
            run_id=rid,
            seat=str(run.get("seat") or "local"),
            core={"type": "constraint", "text": f"closed:{reason}"},
        )
        run = load_run(rid) or run
    # if blocked/open after append, force closed
    run["status"] = "closed"
    run["closed"] = _utc()
    run["close_reason"] = reason
    run["updated"] = _utc()
    run["run_commit"] = _run_commit(run)
    save_run(run)
    act = load_active()
    if act and act.get("run_id") == rid:
        set_active(None)

    progress_path = write_progress_md(rid, phase="close")
    card = related_run_card(run)
    if progress_path:
        card["progress_path"] = str(progress_path)
    append_related_run(card)

    # Lattice edge into next-session bonds (tip stays session-only)
    bonds_touch: dict[str, Any] | None = None
    try:
        from mag.bonds import ingest_bonds

        bonds_touch = ingest_bonds(write=True)
    except Exception as e:
        bonds_touch = {"ok": False, "error": str(e)}

    # Retrocausal: attach run cards onto residual edges without stripping core
    residual_touch: dict[str, Any] | None = None
    try:
        from mag.modules import attach_related_runs_to_residual

        residual_touch = attach_related_runs_to_residual(
            str(run.get("session_id") or "") or None
        )
    except Exception as e:
        residual_touch = {"ok": False, "error": str(e)}

    return {
        "ok": True,
        "run": load_run(rid),
        "related_run": card,
        "progress_path": str(progress_path) if progress_path else None,
        "bonds": {
            "ok": (bonds_touch or {}).get("ok"),
            "path_md": (bonds_touch or {}).get("path_md"),
        },
        "residual_edges": residual_touch,
    }


def read_trail(run_id: str | None = None, *, last_n: int = 50) -> list[dict[str, Any]]:
    run = load_run(run_id)
    if not run:
        return []
    tp = _trail_path(str(run["run_id"]))
    if not tp.is_file():
        return []
    lines = tp.read_text(encoding="utf-8", errors="replace").splitlines()
    out: list[dict[str, Any]] = []
    for ln in lines[-max(1, last_n) :]:
        ln = ln.strip()
        if not ln:
            continue
        try:
            out.append(json.loads(ln))
        except Exception:
            continue
    return out


def cores_for_reinject(run_id: str | None = None, *, last_n: int = 20) -> list[dict[str, Any]]:
    """Events with core — must re-inject (trail integrity)."""
    return [e for e in read_trail(run_id, last_n=max(last_n * 3, 30)) if e.get("core")][
        -last_n:
    ]


def trail_pack_excerpt(
    *,
    run_id: str | None = None,
    max_events: int = 12,
    max_chars: int = 1800,
) -> dict[str, Any]:
    """Min-token trail slice for context-pack (pack-first, not full chat)."""
    repair_active()
    run = load_run(run_id)
    if not run:
        return {"active": False}
    if run.get("status") != "open" and not run_id:
        # only open runs auto-surface in pack
        return {
            "active": False,
            "run_id": run.get("run_id"),
            "status": run.get("status"),
            "note": "run not open — pass explicit id for closed trail",
        }

    all_ev = read_trail(str(run["run_id"]), last_n=40)
    cores = [e for e in all_ev if e.get("core")]
    # prefer core-bearing events first for re-inject, then recent non-cores
    core_ids = {e.get("seq") for e in cores[-8:]}
    rest = [e for e in all_ev if e.get("seq") not in core_ids][-(max_events // 2) :]
    ordered = cores[-max(4, max_events // 2) :] + rest
    # de-dupe by seq preserve order
    seen: set[Any] = set()
    events: list[dict[str, Any]] = []
    for e in ordered:
        seq = e.get("seq")
        if seq in seen:
            continue
        seen.add(seq)
        events.append(e)
    events = events[-max_events:]

    base = run.get("base") if isinstance(run.get("base"), dict) else {}
    lines = [
        f"run_id={run.get('run_id')}",
        f"status={run.get('status')} seat={run.get('seat')} proactivity={run.get('proactivity')}",
        f"base_id={base.get('base_id') or '—'} tip={base.get('tip_root_short') or '—'} git={base.get('git_sha') or '—'}",
        f"goal={(run.get('goal') or '')[:200]}",
        f"n_events={run.get('n_events')} n_tool_calls={run.get('n_tool_calls')}",
        "--- cores (re-inject) ---",
    ]
    for e in cores[-8:]:
        bit = f"[{e.get('seq')}|{e.get('kind')}] {e.get('summary') or ''}"
        bit += f" | core={json.dumps(e.get('core'), ensure_ascii=False)[:220]}"
        lines.append(bit[:320])
    lines.append("--- trail tail ---")
    for e in events:
        bit = f"[{e.get('seq')}|{e.get('kind')}] {e.get('summary') or ''}"
        if e.get("core") and e.get("seq") not in {c.get("seq") for c in cores[-8:]}:
            bit += f" | core={json.dumps(e['core'], ensure_ascii=False)[:120]}"
        lines.append(bit[:300])
    text = "\n".join(lines)
    if len(text) > max_chars:
        text = text[: max_chars - 20] + "\n…(trail clipped)"
    return {
        "active": run.get("status") == "open",
        "run_id": run.get("run_id"),
        "seat": run.get("seat"),
        "proactivity": run.get("proactivity"),
        "base_id": base.get("base_id"),
        "base": {
            "base_id": base.get("base_id"),
            "tip_root_short": base.get("tip_root_short"),
            "git_sha": base.get("git_sha"),
        },
        "goal": (run.get("goal") or "")[:300],
        "n_events": run.get("n_events"),
        "n_cores": len(cores),
        "text": text,
        "path": str(_trail_path(str(run["run_id"]))),
        "text_len": len(text),
    }


def status() -> dict[str, Any]:
    repair = repair_active()
    act = load_active()
    run = load_run((act or {}).get("run_id") if act else None)
    return {
        "ok": True,
        "active": act,
        "run": run,
        "repair": repair,
        "runs_dir": str(RUNS),
    }
