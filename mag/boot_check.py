"""boot_check — ONE-PASS fresh-window boot probe. Clean boot is a command, not a hope.

WHAT: every fresh zcode window boots with AGENTS.md + MEMORY.md; a window that
boots fat boots degraded. This organ gives the 60-second habitat look BEFORE any
work starts: chain tip, docker fleet, inbox depth, room tail, fresh watch cards,
MEMORY.md budget health, orphan-sweep pointer, and the one-line next action.

LAW CITATION (corrections #11, #13): a LOOK, not a runtime — spawns nothing,
kills nothing, schedules nothing, holds no port. $0, files-only, stdlib-only,
no network. Docker probe degrades gracefully when docker is missing.

CLI:
  python -m mag.boot_check          # one-screen boot report
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHAIN = ROOT / "memory" / "biography" / "verkle_chain.jsonl"
INBOX = ROOT / "queue" / "handoff" / "zcode" / "INBOX"
ROOM = ROOT / "watch" / "room.jsonl"
WATCH = ROOT / "watch"
ORPHAN_LEDGER = ROOT / "memory" / "runs" / "batch5_20260906" / "ORPHAN_LEDGER_20260906.md"

# MEMORY.md: harness index budget = one-line entries < 200 chars.
_MEM_CANDIDATES = [
    Path("C:/Users/foste/.zcode/cli/memories/projects/projects-0fb5e3041b59db21/memory/MEMORY.md"),
]


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _memory_md() -> Path | None:
    for p in _MEM_CANDIDATES:
        if p.exists():
            return p
    return None


def _chain_tip() -> dict[str, str]:
    try:
        lines = [ln for ln in CHAIN.read_text(encoding="utf-8",
                                              errors="replace").splitlines() if ln.strip()]
        if not lines:
            return {"tip": "EMPTY"}
        d = json.loads(lines[-1])
        return {"index": str(d.get("index", "?")),
                "root": str(d.get("verkle_root", "?"))[:12],
                "ts": str(d.get("ts", "?"))[:19], "rows": str(len(lines))}
    except Exception as exc:  # noqa: BLE001
        return {"tip": f"ERROR:{type(exc).__name__}"}


def _fleet() -> dict[str, int]:
    try:
        out = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}\t{{.Status}}"],
            capture_output=True, text=True, timeout=5).stdout
        rows = [ln for ln in out.strip().splitlines() if ln.strip()]
        unhealthy = sum(1 for ln in rows if "unhealthy" in ln.lower())
        return {"count": len(rows), "unhealthy": unhealthy}
    except Exception:  # noqa: BLE001 — docker missing/timeout: degrade, never block boot
        return {"count": -1, "unhealthy": -1}


def _inbox_n() -> int:
    try:
        return len([p for p in INBOX.iterdir() if p.is_file()])
    except Exception:  # noqa: BLE001
        return -1


def _room_tail() -> list[dict[str, str]]:
    try:
        lines = [ln for ln in ROOM.read_text(encoding="utf-8",
                                             errors="replace").splitlines() if ln.strip()]
        out = []
        for ln in lines[-2:]:
            try:
                d = json.loads(ln)
                msg = d.get("msg")
                if not msg:
                    msg = " ".join(f"{k}={d[k]}" for k in sorted(d)
                                   if k not in ("ts",))[:80]
                out.append({"ts": str(d.get("ts", "?"))[:19], "head": str(msg)[:80]})
            except json.JSONDecodeError:
                out.append({"ts": "?", "head": ln[:80]})
        return out
    except Exception:  # noqa: BLE001
        return []


def _watch_fresh() -> dict[str, object]:
    cutoff = time.time() - 24 * 3600
    try:
        fresh = sorted((p for p in WATCH.glob("*.md") if p.stat().st_mtime > cutoff),
                       key=lambda p: p.stat().st_mtime, reverse=True)
        return {"count": len(fresh), "newest": [p.name for p in fresh[:3]]}
    except Exception:  # noqa: BLE001
        return {"count": -1, "newest": []}


def _memory_health() -> dict[str, object]:
    p = _memory_md()
    if p is None:
        return {"status": "MEMORY.md NOT FOUND"}
    try:
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        over = sum(1 for ln in lines if len(ln) > 200)
        return {"lines": len(lines), "bytes": p.stat().st_size,
                "over200": over, "budget": "entry<200ch", "verdict":
                "FAT" if over else "OK"}
    except Exception as exc:  # noqa: BLE001
        return {"status": f"ERROR:{type(exc).__name__}"}


def snap() -> dict[str, object]:
    data: dict[str, object] = {
        "schema": "boot_check.v1",
        "ts": _now(),
        "chain_tip": _chain_tip(),
        "fleet": _fleet(),
        "inbox_n": _inbox_n(),
        "room_tail": _room_tail(),
        "watch_fresh_24h": _watch_fresh(),
        "memory": _memory_health(),
        "orphan_ledger": str(ORPHAN_LEDGER) if ORPHAN_LEDGER.exists() else None,
    }
    return data


def _summarize(d: dict[str, object]) -> str:
    tip = d["chain_tip"]
    fleet = d["fleet"]
    mem = d["memory"]
    lines: list[str] = [f"BOOT_CHECK {d['ts']}"]
    if "tip" in tip:
        lines.append(f"  chain      : {tip['tip']}")
    else:
        lines.append(f"  chain      : index {tip.get('index')} root {tip.get('root')} @ {tip.get('ts')} ({tip.get('rows')} rows)")
    if fleet["count"] < 0:
        lines.append("  fleet      : docker unavailable (degraded, non-blocking)")
    else:
        u = fleet["unhealthy"]
        lines.append(f"  fleet      : {fleet['count']} containers, {u if u >= 0 else '?'} unhealthy")
    lines.append(f"  inbox      : {d['inbox_n']} files")
    tail = d["room_tail"]
    if tail:
        for row in tail:
            lines.append(f"  room       : {row['ts']} {row['head']}")
    else:
        lines.append("  room       : no tail (room.jsonl missing/empty)")
    wf = d["watch_fresh_24h"]
    names = ", ".join(wf["newest"]) if wf["newest"] else "-"
    lines.append(f"  watch 24h  : {wf['count']} cards | newest: {names}")
    if "status" in mem:
        lines.append(f"  memory.md  : {mem['status']}")
    else:
        lines.append(f"  memory.md  : {mem['lines']} lines / {mem['bytes']}B / {mem['over200']} over-200ch "
                     f"(budget entry<200ch) => {mem['verdict']}")
    lines.append(f"  orphans    : {d['orphan_ledger'] or 'no batch5 orphan ledger yet'}")
    lines.append("  NEXT       : GO menu: OPERATOR_DRIVE.md | batch board: memory/runs/batch5_20260906/")
    return "\n".join(lines)


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    print(_summarize(snap()))


if __name__ == "__main__":
    main()
