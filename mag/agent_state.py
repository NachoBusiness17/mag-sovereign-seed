"""Grok/Mag agent state — versioned packs on a Verkle-style chain (not session tip).

Law:
  - Session residual tip remains sessions-only (DNA).
  - Agent state is a *recall edge*: LOAD before redesign; never invent a second DNA.
  - Each commit has content_commit + parent_commit + merkle tip over version leaves.
  - LATEST is the viewport; versions/ is history (amend = new version, not erase).

Recall:
  mag.cmd agent-state
  mag.cmd agent-state --load
  context-pack includes L0 agent_state excerpt automatically.
"""
from __future__ import annotations

import hashlib
import json
import contextlib
import functools
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT

STATE_DIR = ROOT / "memory" / "agent_state"
VERSIONS = STATE_DIR / "versions"
CHAIN = STATE_DIR / "chain.jsonl"
TIP = STATE_DIR / "tip.json"
LATEST_JSON = STATE_DIR / "LATEST.json"
LATEST_MD = STATE_DIR / "LATEST.md"

SCHEMA = "mag_agent_state.v1"


def _utc() -> datetime:
    return datetime.now(timezone.utc)


def _h(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _leaf_hash(obj: dict[str, Any]) -> str:
    raw = json.dumps(obj, sort_keys=True, default=str).encode("utf-8")
    return _h(b"agent_leaf:" + raw)


def _merkle_root(leaf_hashes: list[str]) -> str:
    if not leaf_hashes:
        return _h(b"agent_empty")
    layer = list(leaf_hashes)
    while len(layer) > 1:
        nxt: list[str] = []
        for i in range(0, len(layer), 2):
            left = layer[i]
            right = layer[i + 1] if i + 1 < len(layer) else left
            nxt.append(_h(b"agent_node:" + left.encode() + b":" + right.encode()))
        layer = nxt
    return layer[0]


def ensure_dirs() -> None:
    VERSIONS.mkdir(parents=True, exist_ok=True)
    STATE_DIR.mkdir(parents=True, exist_ok=True)


@contextlib.contextmanager
def agent_state_lock(*, timeout: float = 60.0):
    """Serialize state commits without changing the historical chain.

    The lock path is derived from ``STATE_DIR`` at call time so tests and
    isolated callers can redirect the state root safely.  A stale lock from a
    crashed writer is recoverable after fifteen minutes; normal contention
    waits briefly and never spins indefinitely.
    """
    ensure_dirs()
    lock_path = STATE_DIR / ".agent_state.lock"
    deadline = time.monotonic() + timeout
    acquired = False
    while not acquired:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            try:
                os.write(fd, f"pid={os.getpid()}\n".encode("ascii"))
            finally:
                os.close(fd)
            acquired = True
        except FileExistsError:
            try:
                if time.time() - lock_path.stat().st_mtime > 900:
                    lock_path.unlink()
                    continue
            except FileNotFoundError:
                continue
            if time.monotonic() >= deadline:
                raise TimeoutError(f"agent-state lock timeout: {lock_path}")
            time.sleep(0.05)
    try:
        yield
    finally:
        if acquired:
            try:
                lock_path.unlink()
            except FileNotFoundError:
                pass


def _state_locked(fn):
    @functools.wraps(fn)
    def wrapped(*args, **kwargs):
        with agent_state_lock():
            return fn(*args, **kwargs)

    return wrapped


def load_latest() -> dict[str, Any] | None:
    if not LATEST_JSON.is_file():
        return None
    try:
        return json.loads(LATEST_JSON.read_text(encoding="utf-8", errors="replace"))
    except (json.JSONDecodeError, OSError):
        return None


def load_version(commit_hex: str) -> dict[str, Any] | None:
    c8 = (commit_hex or "")[:8]
    if not c8 or not VERSIONS.is_dir():
        return None
    for p in VERSIONS.glob(f"*_{c8}.json"):
        try:
            return json.loads(p.read_text(encoding="utf-8", errors="replace"))
        except (json.JSONDecodeError, OSError):
            continue
    # full hex match
    for p in VERSIONS.glob("*.json"):
        try:
            o = json.loads(p.read_text(encoding="utf-8", errors="replace"))
        except (json.JSONDecodeError, OSError):
            continue
        if str((o.get("content_commit") or {}).get("hex") or "").startswith(c8):
            return o
    return None


def list_versions(*, limit: int = 20) -> list[dict[str, Any]]:
    if not CHAIN.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in CHAIN.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows[-limit:]


def _body_for_hash(state: dict[str, Any]) -> dict[str, Any]:
    """Exclude volatile tip fields from content commit."""
    # content_commit is derived from this body, so a verifier receiving a
    # persisted state must exclude the commitment itself to avoid a
    # self-referential hash mismatch.
    skip = {"tip", "chain_row", "pack_excerpt", "content_commit"}
    return {k: v for k, v in state.items() if k not in skip}


def content_commit_hex(state: dict[str, Any]) -> str:
    raw = json.dumps(_body_for_hash(state), sort_keys=True, default=str).encode("utf-8")
    return _h(b"agent_state:" + raw)


def _display_path(path: Path) -> str:
    """Repo-relative path for commit receipts, absolute when outside ROOT.

    Cause (ball3 driver-meter 2026-09-29): commit_state recorded
    fpath.relative_to(ROOT) and raised ValueError when STATE_DIR was
    monkeypatched into an out-of-repo tmp_path (the wave5 suite-burn run
    used an out-of-repo pytest basetemp:
    watch/inbox/gala_20260925/wave5-repair/lanes/suite-burn.check.txt,
    test_agent_state_commit_hash_excludes_its_own_field). These are
    display-only receipt fields; with the default STATE_DIR under ROOT the
    output is byte-identical to the old code.
    """
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def format_load_markdown(state: dict[str, Any] | None = None, *, max_chars: int = 4500) -> str:
    s = state if state is not None else load_latest()
    if not s:
        return (
            "# Agent state — none filed\n\n"
            "Run: `python main.py agent-state --commit \"bootstrap\"` after a full analysis.\n"
            "Law: LOAD this before redesigning Mag/republic loops.\n"
        )
    cc = (s.get("content_commit") or {}).get("hex") or ""
    parent = (s.get("parent_commit") or {}).get("hex") or ""
    tip = s.get("tip") or {}
    lines = [
        f"# Agent state LOAD — {s.get('label') or 'unnamed'}",
        "",
        f"**schema:** `{s.get('schema')}`  ",
        f"**commitment:** `{s.get('commitment')}`  ",
        f"**content_commit:** `{cc[:16]}…`  " if len(cc) > 16 else f"**content_commit:** `{cc}`  ",
        f"**parent:** `{parent[:16]}…`  " if parent and len(parent) > 16 else f"**parent:** `{parent or 'genesis'}`  ",
        f"**ts:** {s.get('ts')}  ",
        f"**agent_tip_root:** `{(tip.get('root') or '')[:16]}…` · n={tip.get('n_versions')}  ",
        "",
        "## One line (do not reinvent)",
        "",
        s.get("one_line") or "(none)",
        "",
        "## Anti-reinvention (hard)",
        "",
    ]
    for item in s.get("do_not_redesign") or []:
        lines.append(f"- {item}")
    lines.extend(["", "## Compose bundles (already named)", ""])
    for b in s.get("compose_bundles") or []:
        if isinstance(b, dict):
            lines.append(f"- **{b.get('id')}:** {b.get('line')}")
        else:
            lines.append(f"- {b}")
    lines.extend(["", "## Next moves (ordered)", ""])
    for i, m in enumerate(s.get("next_moves") or [], 1):
        if isinstance(m, dict):
            st = m.get("status") or "open"
            lines.append(f"{i}. [{st}] {m.get('id')}: {m.get('title')}")
        else:
            lines.append(f"{i}. {m}")
    lines.extend(["", "## Stack snapshot", ""])
    snap = s.get("stack") or {}
    for k, v in snap.items():
        lines.append(f"- **{k}:** {v}")
    lines.extend(["", "## Paths (edges — open these, don't rebuild)", ""])
    for k, v in (s.get("paths") or {}).items():
        lines.append(f"- `{k}` → {v}")
    lines.extend(
        [
            "",
            "## Leave (capture / theater)",
            "",
        ]
    )
    for item in s.get("leave") or []:
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## Recall commands",
            "",
            "```text",
            "python main.py agent-state --load",
            "python main.py agent-state --list",
            "python main.py agent-state --show <commit8>",
            "python main.py context-pack   # includes agent_state excerpt",
            "```",
            "",
            "_Grok: answer from this pack + dig leaves. Do not full redesign loops already named._",
        ]
    )
    text = "\n".join(lines)
    if len(text) > max_chars:
        text = text[: max_chars - 20] + "\n…(clipped)"
    return text


def pack_excerpt(*, max_chars: int = 900) -> str:
    """Min token excerpt for context-pack L0."""
    s = load_latest()
    if not s:
        return "(no agent_state — commit after analysis: main.py agent-state --commit)"
    cc = str((s.get("content_commit") or {}).get("hex") or "")[:12]
    tip = s.get("tip") or {}
    moves = s.get("next_moves") or []
    open_moves = [
        (m.get("id") if isinstance(m, dict) else str(m))
        for m in moves
        if not isinstance(m, dict) or m.get("status") in (None, "open", "doing")
    ][:5]
    lines = [
        f"label={s.get('label')} commit={cc} tip_n={tip.get('n_versions')}",
        f"one_line: {(s.get('one_line') or '')[:200]}",
        "do_not_redesign: " + "; ".join((s.get("do_not_redesign") or [])[:4])[:220],
        "next: " + ", ".join(str(x) for x in open_moves),
        f"paths.full_analysis={((s.get('paths') or {}).get('full_self_analysis') or '')[:80]}",
    ]
    return "\n".join(lines)[:max_chars]


@_state_locked
def commit_state(
    payload: dict[str, Any],
    *,
    label: str,
    reason: str = "",
    session_id: str | None = None,
) -> dict[str, Any]:
    """Write a new agent_state version. Never overwrites history files."""
    ensure_dirs()
    prev = load_latest()
    parent_hex = ""
    if prev:
        parent_hex = str((prev.get("content_commit") or {}).get("hex") or "")

    ts = _utc()
    ts_iso = ts.isoformat()
    ts_file = ts.strftime("%Y%m%dT%H%M%SZ")

    state: dict[str, Any] = {
        "schema": SCHEMA,
        "label": label,
        "reason": reason,
        "ts": ts_iso,
        "session_id": session_id or "",
        "parent_commit": {"hex": parent_hex} if parent_hex else {"hex": "", "genesis": True},
        "commitment": payload.get("commitment")
        or f"agent-state-{label}-{ts_file}",
        "one_line": payload.get("one_line") or "",
        "do_not_redesign": list(payload.get("do_not_redesign") or []),
        "compose_bundles": list(payload.get("compose_bundles") or []),
        "next_moves": list(payload.get("next_moves") or []),
        "stack": dict(payload.get("stack") or {}),
        "paths": dict(payload.get("paths") or {}),
        "leave": list(payload.get("leave") or []),
        "tesuji_taken": list(payload.get("tesuji_taken") or []),
        "notes": payload.get("notes") or "",
    }
    # provisional hash without tip
    c_hex = content_commit_hex(state)
    state["content_commit"] = {
        "hex": c_hex,
        "alg": "sha256",
        "prefix": "agent_state:",
    }
    c8 = c_hex[:8]
    fname = f"{ts_file}_{c8}.json"
    fpath = VERSIONS / fname

    # rebuild tip over all version leaf hashes
    leaf_hashes: list[str] = []
    if CHAIN.is_file():
        for line in CHAIN.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
                if row.get("leaf_hash"):
                    leaf_hashes.append(str(row["leaf_hash"]))
            except json.JSONDecodeError:
                continue

    leaf_for_hash = {
        "type": "agent_state_leaf",
        "schema": "agent_state_leaf.v1",
        "label": label,
        "ts": ts_iso,
        "content_commit": c_hex,
        "parent_commit": parent_hex,
        "one_line": state.get("one_line"),
        "session_id": state.get("session_id"),
    }
    lh = _leaf_hash(leaf_for_hash)
    leaf_hashes.append(lh)
    root = _merkle_root(leaf_hashes)
    tip = {
        "schema": "agent_state_tip.v1",
        "root": root,
        "n_versions": len(leaf_hashes),
        "last_filename": fname,
        "last_leaf_hash": lh,
        "last_content_commit": c_hex,
        "updated": ts_iso,
        "note": "Agent-state version tip — not session residual tip. Recall via LATEST.",
    }
    state["tip"] = tip

    fpath.write_text(json.dumps(state, indent=2, default=str) + "\n", encoding="utf-8")
    md_path = fpath.with_suffix(".md")
    md_path.write_text(format_load_markdown(state, max_chars=12000), encoding="utf-8")

    chain_row = {
        "ts": ts_iso,
        "filename": fname,
        "label": label,
        "content_commit": c_hex,
        "parent_commit": parent_hex,
        "leaf_hash": lh,
        "tip_root": root,
        "n_versions": len(leaf_hashes),
        "session_id": session_id or "",
        "reason": reason[:200],
    }
    with CHAIN.open("a", encoding="utf-8") as f:
        f.write(json.dumps(chain_row, default=str) + "\n")
    TIP.write_text(json.dumps(tip, indent=2) + "\n", encoding="utf-8")
    LATEST_JSON.write_text(json.dumps(state, indent=2, default=str) + "\n", encoding="utf-8")
    LATEST_MD.write_text(format_load_markdown(state, max_chars=12000), encoding="utf-8")

    # pin pointer for improve pins face
    pin_ptr = ROOT / "memory" / "improve" / "pins" / "AGENT_STATE_LATEST.md"
    pin_ptr.parent.mkdir(parents=True, exist_ok=True)
    pin_ptr.write_text(
        f"# Agent state pin → LOAD\n\n"
        f"**label:** {label}  \n"
        f"**commit:** `{c_hex}`  \n"
        f"**path:** `memory/agent_state/LATEST.md`  \n"
        f"**tip_root:** `{root[:24]}…`  \n"
        f"**n_versions:** {len(leaf_hashes)}  \n\n"
        f"Command: `python main.py agent-state --load`\n",
        encoding="utf-8",
    )

    return {
        "ok": True,
        "content_commit": c_hex,
        "parent_commit": parent_hex,
        "path": _display_path(fpath),
        "latest_md": _display_path(LATEST_MD),
        "tip": tip,
        "label": label,
    }


def link_to_residual(session_id: str | None = None) -> dict[str, Any]:
    """Retrocausal-safe: write edges.agent_state on residual without stripping core."""
    latest = load_latest()
    if not latest:
        return {"ok": False, "error": "no agent_state"}
    sid = session_id or ""
    if not sid:
        # latest session file
        ls = ROOT / "memory" / "biography" / "latest_session.json"
        if ls.is_file():
            try:
                sid = str(json.loads(ls.read_text(encoding="utf-8")).get("session_id") or "")
            except (json.JSONDecodeError, OSError):
                sid = ""
    if not sid:
        tip_path = ROOT / "memory" / "biography" / "verkle_tip.json"
        if tip_path.is_file():
            try:
                sid = str(json.loads(tip_path.read_text(encoding="utf-8")).get("last_session_id") or "")
            except (json.JSONDecodeError, OSError):
                sid = ""
    if not sid:
        return {"ok": False, "error": "no session_id"}

    from mag.registry import load_residual, residual_path

    res = load_residual(sid)
    if not res:
        return {"ok": False, "error": f"no residual for {sid}", "session_id": sid}
    edges = res.get("edges") if isinstance(res.get("edges"), dict) else {}
    edges = dict(edges)
    edges["agent_state"] = {
        "schema": SCHEMA,
        "content_commit": (latest.get("content_commit") or {}).get("hex"),
        "label": latest.get("label"),
        "path": "memory/agent_state/LATEST.json",
        "tip_root": (latest.get("tip") or {}).get("root"),
        "linked_at": _utc().isoformat(),
    }
    # keep list of prior agent commits as edge history (cap 12)
    hist = list(edges.get("agent_state_history") or [])
    hist.append(
        {
            "content_commit": (latest.get("content_commit") or {}).get("hex"),
            "label": latest.get("label"),
            "ts": latest.get("ts"),
        }
    )
    edges["agent_state_history"] = hist[-12:]
    res["edges"] = edges
    path = residual_path(sid)
    path.write_text(json.dumps(res, indent=2, default=str) + "\n", encoding="utf-8")
    return {"ok": True, "session_id": sid, "path": str(path), "edges.agent_state": edges["agent_state"]}
