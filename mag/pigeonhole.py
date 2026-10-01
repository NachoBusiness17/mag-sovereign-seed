"""Pigeonhole — mycelial mailbox for scheduled sub-agents (knot as the channel).

The republic principle: agents communicate through the KNOT, not through
fragile pipes. The orchestrator spawns sub-agents with stdin=DEVNULL, so the
B1-B3 steering listener had no channel and the supervisor could only wait on a
hard timeout. This module restores the channel as a per-task mailbox:

    memory/mail/<task_id>/
        inbox.txt        supervisor -> agent   (!steer <ctx> / !pause / !continue)
        heartbeat.jsonl  agent -> supervisor   liveness beads (step, last_tool, phase)
        status.json      agent -> supervisor   latest phase (started/answered/done/
                                               collapse_stop/crashed), replaced atomically

Crash recognition becomes heartbeat staleness + status phase — live, not
timeout-based. The hard timeout stays only as a final backstop.

Concurrency: writes are small + atomic (tmp + os.replace; inbox drain uses an
exclusive lockfile). Single supervisor writer, single agent writer per file.
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT
from mag.memory_events import emit_steer_lifecycle

MAIL_ROOT = ROOT / "memory" / "mail"
HEARTBEAT_INTERVAL_S = 15  # agent writes a bead this often while a turn runs
STALL_AFTER_S = 3 * HEARTBEAT_INTERVAL_S  # no bead for this long -> suspicious
STEERING_LOG = ROOT / "logs" / "steering_events.jsonl"


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def mailbox_dir(task_id: str) -> Path:
    return MAIL_ROOT / (task_id or "unknown")


def _ensure(task_id: str) -> Path:
    d = mailbox_dir(task_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, default=str) + "\n")


def _extract_steer_id(raw_cmd: str) -> tuple[str | None, str]:
    """Parse '!steer #sid:<id># text' framing and return (sid, clean_context)."""
    cmd = (raw_cmd or "").strip()
    if not cmd.startswith("!steer"):
        return None, cmd
    ctx = cmd[6:].strip()
    marker = "#sid:"
    if not ctx.startswith(marker):
        return None, ctx
    end = ctx.find("#", len(marker))
    if end <= len(marker):
        return None, ctx
    steer_id = ctx[len(marker):end].strip()
    clean = ctx[end + 1 :].strip()
    return (steer_id or None), clean


def _steer_event(task_id: str, steer_id: str, status: str, **meta: Any) -> dict[str, Any]:
    event = {
        "schema": "overseer_steer_event.v1",
        "task_id": task_id,
        "steer_id": steer_id,
        "status": status,
        "ts": _utc(),
        **meta,
    }
    with _lock(task_id):
        _append_jsonl(_ensure(task_id) / "steer_events.jsonl", event)
    _append_jsonl(STEERING_LOG, event)
    try:
        emit_steer_lifecycle(
            task_id=task_id,
            steer_id=steer_id,
            status=status,
            phase=str(meta.get("phase") or meta.get("phase_at_apply") or ""),
            source_tier=str(meta.get("source_tier") or "T2"),
            reason=str(meta.get("reason") or ""),
        )
    except Exception:
        pass
    return event


def _lock_path(task_id: str) -> Path:
    return _ensure(task_id) / ".lock"


class _lock:
    """Cross-platform exclusive lockfile (best-effort, 10s max wait)."""

    def __init__(self, task_id: str):
        self.path = _lock_path(task_id)

    def __enter__(self) -> "_lock":
        deadline = time.time() + 10.0
        while True:
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, str(os.getpid()).encode())
                os.close(fd)
                return self
            except FileExistsError:
                if time.time() > deadline:
                    break  # stale lock: proceed (best-effort)
                time.sleep(0.05)
        return self

    def __exit__(self, *exc: Any) -> None:
        try:
            self.path.unlink()
        except OSError:
            pass


# --- supervisor -> agent ---------------------------------------------------


def post_cmd(task_id: str, cmd: str) -> None:
    """Append one command line to the task inbox (supervisor side)."""
    cmd = cmd.strip()
    if not cmd:
        return
    with _lock(task_id):
        p = _ensure(task_id) / "inbox.txt"
        with p.open("a", encoding="utf-8") as fh:
            fh.write(cmd + "\n")


def post_steer(task_id: str, context: str, *, reason: str = "", source_tier: str = "") -> str:
    """Post steer text with an ID so overseer can observe accept/apply lifecycle."""
    steer_id = "sid-" + str(int(time.time() * 1000))
    framed = "!steer #sid:%s# %s" % (steer_id, context)
    post_cmd(task_id, framed)
    _steer_event(
        task_id,
        steer_id,
        "accepted",
        reason=(reason or "")[:200],
        source_tier=(source_tier or "")[:20],
    )
    return steer_id


def ack_steer(task_id: str, steer_id: str, *, status: str = "applied", phase: str = "", error: str = "") -> dict[str, Any]:
    """Agent-side ACK when a steer command is consumed/applied."""
    return _steer_event(
        task_id,
        steer_id,
        status,
        phase_at_apply=(phase or "")[:40],
        error=(error or "")[:200],
    )


def steer_status(task_id: str, steer_id: str) -> dict[str, Any] | None:
    p = mailbox_dir(task_id) / "steer_events.jsonl"
    if not p.is_file():
        return None
    latest: dict[str, Any] | None = None
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        if row.get("steer_id") == steer_id:
            latest = row
    return latest


def steering_log(limit: int = 200) -> list[dict[str, Any]]:
    if not STEERING_LOG.is_file():
        return []
    out: list[dict[str, Any]] = []
    for line in STEERING_LOG.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out[-limit:]


# --- agent -> supervisor ---------------------------------------------------


def drain_inbox(task_id: str) -> list[str]:
    """Read + clear the inbox (agent side). Returns command lines in order."""
    d = _ensure(task_id)
    p = d / "inbox.txt"
    if not p.is_file():
        return []
    with _lock(task_id):
        if not p.is_file():
            return []
        lines = [ln.strip() for ln in p.read_text(encoding="utf-8", errors="replace").splitlines() if ln.strip()]
        p.write_text("", encoding="utf-8")
    out: list[str] = []
    for cmd in lines:
        sid, clean = _extract_steer_id(cmd)
        if sid:
            out.append("!steer [sid:%s] %s" % (sid, clean))
            _steer_event(task_id, sid, "received", phase="inbox_drain")
        else:
            out.append(cmd)
    return out


def heartbeat(task_id: str, **meta: Any) -> None:
    """Append one liveness bead (agent side)."""
    bead = {
        "kind": "heartbeat",
        "task_id": task_id,
        "ts": _utc(),
        "unix": time.time(),
        **meta,
    }
    with _lock(task_id):
        p = _ensure(task_id) / "heartbeat.jsonl"
        with p.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(bead, default=str) + "\n")


def write_status(task_id: str, **meta: Any) -> None:
    """Atomically replace status.json (agent side)."""
    st = {"task_id": task_id, "ts": _utc(), "unix": time.time(), **meta}
    d = _ensure(task_id)
    tmp = d / "status.json.tmp"
    tmp.write_text(json.dumps(st, indent=2, default=str), encoding="utf-8")
    os.replace(tmp, d / "status.json")


# --- supervisor reads ------------------------------------------------------


def read_status(task_id: str) -> dict[str, Any] | None:
    p = mailbox_dir(task_id) / "status.json"
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def heartbeats(task_id: str, limit: int = 50) -> list[dict[str, Any]]:
    p = mailbox_dir(task_id) / "heartbeat.jsonl"
    if not p.is_file():
        return []
    out: list[dict[str, Any]] = []
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out[-limit:]


def staleness_s(task_id: str) -> int | None:
    """Seconds since last heartbeat bead; None if no beads yet (unknown)."""
    p = mailbox_dir(task_id) / "heartbeat.jsonl"
    if not p.is_file() or p.stat().st_size == 0:
        return None
    try:
        mtime = p.stat().st_mtime
        return max(0, int(time.time() - mtime))
    except OSError:
        return None


def alive(task_id: str, stall_s: int = STALL_AFTER_S) -> bool | None:
    """True = fresh heartbeat, False = stale, None = unknown (no beads yet)."""
    age = staleness_s(task_id)
    if age is None:
        return None
    return age < stall_s


def self_test() -> dict[str, Any]:
    """File-level test: post/drain round trip + heartbeat + status."""
    tid = "selftest-" + str(int(time.time()))
    try:
        post_cmd(tid, "!steer hello knot")
        post_cmd(tid, "!pause")
        got = drain_inbox(tid)
        if got != ["!steer hello knot", "!pause"]:
            return {"ok": False, "error": f"inbox round trip: {got!r}"}
        heartbeat(tid, step=1, last_tool="write_file", phase="working")
        heartbeat(tid, step=2, last_tool="read_file", phase="working")
        write_status(tid, phase="done", exit_code=0)
        hb = heartbeats(tid)
        if len(hb) != 2 or hb[0]["last_tool"] != "write_file":
            return {"ok": False, "error": f"heartbeat beads: {hb!r}"}
        st = read_status(tid)
        if not st or st.get("phase") != "done" or st.get("exit_code") != 0:
            return {"ok": False, "error": f"status: {st!r}"}
        age = staleness_s(tid)
        if age is None or age > 30:
            return {"ok": False, "error": f"staleness: {age!r}"}
        if alive(tid) is not True:
            return {"ok": False, "error": "alive() should be True for a fresh bead"}
        return {"ok": True, "task_id": tid, "heartbeats": len(hb), "staleness_s": age}
    finally:
        import shutil

        shutil.rmtree(mailbox_dir(tid), ignore_errors=True)


if __name__ == "__main__":
    import json as _json

    print(_json.dumps(self_test(), indent=2, default=str))
