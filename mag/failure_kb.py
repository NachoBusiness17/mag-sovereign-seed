"""Failure Knowledge Base (FKB) — searchable store of failures, fixes, and recurrence.

Captures tool failures and collapse signatures, deduplicates by signature, auto-drafts
remedy cards when a pattern recurs, and injects relevant hits into context packs.

Storage:
  logs/failure_kb.jsonl       -- append-only event log (authoritative)
  memory/failure_kb/signatures.json -- deduped index (count, last_seen, remedy_id)

Index continuity (B2-87, 2026-09-26): the index is a DERIVED cache of the
append-only log; the log is authoritative. The 2026-09-22T14:54Z index reset
zeroed every cross-session count while the log kept full history (receipt:
run_shell:c73866f2f1b5 fell from 25,086 logged events to an index count of
28, unnoticed for 4 days). Two laws hold from now on:

1. Counts are reconciled from log bytes by rebuild_index(), never trusted
   across a reset. Every rebuild writes a top-level "rebuild_receipt" block
   into the index naming the previous totals (signatures_before,
   total_count_before, previous_rebuild_ts/reason), so a rebuild can never
   again silently zero the cross-session counter: the receipt is the record
   of exactly what the previous index held.
2. The log is never pruned to match the index. If counts disagree, the log
   wins and the index is rebuilt.

Wire points:
  operator_inbox.log_behavioral_event → log_failure
  decision_framework.surface_tips → surface_hits
  agent_cli collapse / tool_fail → lookup + format_block
  improve._behavioral_candidates → recurring_patterns
  main.py fkb search|list|stats
"""
from __future__ import annotations

import hashlib
import json
import re
import contextlib
import sys
import threading
import time as _time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT

LOG_PATH = ROOT / "logs" / "failure_kb.jsonl"
INDEX_PATH = ROOT / "memory" / "failure_kb" / "signatures.json"
REMEDY_DIR = ROOT / "memory" / "remedies"
AUTO_DRAFT_THRESHOLD = 3
ALERT_STATE_PATH = ROOT / "state" / "failure_kb_alerts.json"
ALERTS_LOG_PATH = ROOT / "logs" / "failure_kb_alerts.jsonl"
_ALERT_MILESTONES = (10, 50, 100, 500)
_ALERT_COOLDOWN_S = 3600.0

_INDEX_CACHE: tuple[int, int, dict[str, Any]] | None = None
_INDEX_CACHE_LOCK = threading.Lock()

try:  # B2-360: cross-process lock primitive; msvcrt on Windows, fcntl on POSIX
    import msvcrt as _msvcrt

    def _lock_fd(fd: int, unlock: bool = False) -> None:
        _msvcrt.locking(fd, _msvcrt.LK_UNLCK if unlock else _msvcrt.LK_NBLCK, 1)
except ImportError:  # pragma: no cover (non-Windows estate hosts)
    try:
        import fcntl as _fcntl

        def _lock_fd(fd: int, unlock: bool = False) -> None:
            _fcntl.flock(fd, _fcntl.LOCK_UN if unlock else _fcntl.LOCK_EX | _fcntl.LOCK_NB)
    except ImportError:
        def _lock_fd(fd: int, unlock: bool = False) -> None:
            raise OSError("no cross-process lock primitive available")


@contextlib.contextmanager
def _index_file_lock(timeout: float = 15.0):
    """B2-360 (2026-09-26): log_failure's load+mutate+save window was guarded by
    _INDEX_CACHE_LOCK only, which is per-process; two seats or mag cycles logging
    failures concurrently lost the loser's index entries (observed on bytes:
    82 distinct post-reset sigs in logs/failure_kb.jsonl vs 62 index entries at
    census). This sidecar lock file (signatures.json.lock, never the data file
    itself) serializes the read-modify-write window ACROSS processes; the
    in-process cache lock still guards the cache tuple. Waits up to `timeout`
    seconds, then raises rather than writing unlocked (fail-closed: a timed-out
    write is a lost update by definition)."""
    lock_path = Path(str(INDEX_PATH) + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    deadline = _time.monotonic() + timeout
    f = open(lock_path, "a+b")
    try:
        while True:
            try:
                f.seek(0)
                _lock_fd(f.fileno())
                break
            except OSError:
                if _time.monotonic() >= deadline:
                    raise TimeoutError(
                        f"failure_kb index lock busy after {timeout}s: {lock_path}")
                _time.sleep(0.02)
        yield
    finally:
        try:
            f.seek(0)
            _lock_fd(f.fileno(), unlock=True)
        except OSError:
            pass
        f.close()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _alert_signature_pressure(sig: str, rec: dict[str, Any]) -> None:
    """Loud cross-session alarm when one failure signature piles up.

    The in-session collapse detector (5 consecutive identical calls inside
    one turn) cannot see failures spread 1-3 per turn across many sessions —
    the 2026-08-06..09-11 run_shell loop (25k rows, no alert) is the receipt.
    This counter is cross-session: it lives in the shared signatures index
    and pages at count milestones, cooldown-gated per signature.
    """
    try:
        import time

        count = int(rec.get("count") or 0)
        milestone = count in _ALERT_MILESTONES or (count > 500 and count % 500 == 0)
        if not milestone:
            return
        ALERT_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        state: dict[str, Any] = {}
        try:
            state = json.loads(ALERT_STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            state = {}
        now = time.time()
        try:
            last = float(state.get(sig) or 0)
        except (TypeError, ValueError):
            last = 0.0
        if now - last < _ALERT_COOLDOWN_S:
            return
        state[sig] = now
        ALERT_STATE_PATH.write_text(json.dumps(state), encoding="utf-8")
        alert = {
            "ts": _now(),
            "type": "signature_pressure",
            "sig": sig,
            "count": count,
            "tool": rec.get("tool"),
            "sample": (rec.get("error_sample") or rec.get("detail_sample") or "")[:200],
        }
        ALERTS_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with ALERTS_LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(alert, ensure_ascii=False) + "\n")
        print(
            f"!! signature pressure: {sig} x{count} — recurring failure across sessions"
            " (see logs/failure_kb_alerts.jsonl)",
            flush=True,
        )
        try:
            from mag.training_events import emit

            emit(
                "fkb_signature_pressure",
                join={"sig": sig},
                input_data={"count": count},
                action={"tool": rec.get("tool")},
                outcome={"alerted": True},
                pattern_tags=["signature_pressure", rec.get("tool") or "unknown"],
            )
        except Exception:
            pass
    except Exception:
        pass


def _slug(text: str, max_len: int = 48) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return (s[:max_len] or "unknown").strip("-")


def _normalize_error(error: str | None, detail: str | None) -> str:
    """Collapse noisy error text into a stable signature fragment."""
    blob = f"{error or ''} {detail or ''}".lower()
    blob = re.sub(r"\s+", " ", blob).strip()
    # Strip volatile paths / timestamps
    blob = re.sub(r"[a-f0-9]{8,}", "<hex>", blob)
    blob = re.sub(r"\d{4}-\d{2}-\d{2}[t\s]\d{2}:\d{2}:\d{2}", "<ts>", blob)
    return blob[:240]


def signature_key(*, tool: str | None = None, error: str | None = None, detail: str | None = None) -> str:
    tool_s = (tool or "").strip().lower() or "_"
    norm = _normalize_error(error, detail)
    digest = hashlib.sha256(f"{tool_s}|{norm}".encode()).hexdigest()[:12]
    return f"{tool_s}:{digest}"


def _load_index() -> dict[str, Any]:
    global _INDEX_CACHE
    if not INDEX_PATH.is_file():
        return {"schema": "failure_kb.signatures.v1", "signatures": {}}
    try:
        stat = INDEX_PATH.stat()
        stamp = (int(stat.st_mtime_ns), int(stat.st_size))
        with _INDEX_CACHE_LOCK:
            if _INDEX_CACHE and _INDEX_CACHE[:2] == stamp:
                return _INDEX_CACHE[2]
    except OSError:
        stamp = None
    try:
        data = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("signatures"), dict):
            if stamp is not None:
                with _INDEX_CACHE_LOCK:
                    _INDEX_CACHE = (stamp[0], stamp[1], data)
            return data
    except (OSError, json.JSONDecodeError):
        pass
    return {"schema": "failure_kb.signatures.v1", "signatures": {}}


def _save_index(data: dict[str, Any]) -> None:
    global _INDEX_CACHE
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    INDEX_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    try:
        stat = INDEX_PATH.stat()
        with _INDEX_CACHE_LOCK:
            _INDEX_CACHE = (int(stat.st_mtime_ns), int(stat.st_size), data)
    except OSError:
        with _INDEX_CACHE_LOCK:
            _INDEX_CACHE = None


def log_failure(
    *,
    kind: str,
    detail: str = "",
    tool: str | None = None,
    error: str | None = None,
    phase: str | None = None,
    session_id: str | None = None,
    provider: str | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    """Record a failure event; bump signature count; maybe auto-draft remedy."""
    sig = signature_key(tool=tool, error=error, detail=detail)
    row = {
        "ts": _now(),
        "kind": kind,
        "sig": sig,
        "detail": (detail or "")[:500],
        "tool": tool,
        "error": (error or "")[:300] if error else None,
        "phase": phase,
        "session_id": session_id,
        "provider": provider,
        "model": model,
    }
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError:
        pass

    try:
        from mag.training_events import emit

        emit(
            "fkb_failure",
            join={"session_id": session_id or ""},
            input_data={"kind": kind, "detail": (detail or "")[:200]},
            action={"tool": tool, "provider": provider, "sig": sig},
            outcome={"count": None},
            pattern_tags=[kind, tool or "unknown"],
        )
    except Exception:
        pass

    # B2-360: the whole read-modify-write window holds the cross-process lock
    # (including the remedy save below) so a concurrent logger cannot splice a
    # save between our load and save.
    with _index_file_lock():
        idx = _load_index()
        sigs: dict[str, Any] = idx.setdefault("signatures", {})
        rec = sigs.get(sig) or {
            "sig": sig,
            "tool": tool,
            "error_sample": (error or "")[:200],
            "detail_sample": (detail or "")[:200],
            "kind": kind,
            "count": 0,
            "first_seen": row["ts"],
            "last_seen": row["ts"],
            "remedy_id": None,
        }
        rec["count"] = int(rec.get("count") or 0) + 1
        rec["last_seen"] = row["ts"]
        rec["kind"] = kind
        if tool:
            rec["tool"] = tool
        if error:
            rec["error_sample"] = error[:200]
        if detail:
            rec["detail_sample"] = detail[:200]
        sigs[sig] = rec
        _save_index(idx)

        drafted = None
        if int(rec["count"]) >= AUTO_DRAFT_THRESHOLD and not rec.get("remedy_id"):
            drafted = auto_draft_remedy(rec)
            if drafted:
                rec["remedy_id"] = drafted
                sigs[sig] = rec
                _save_index(idx)
    _alert_signature_pressure(sig, rec)

    return {"ok": True, "sig": sig, "count": rec["count"], "remedy_id": rec.get("remedy_id"), "drafted": drafted}


def auto_draft_remedy(rec: dict[str, Any]) -> str | None:
    """When a signature recurs, draft a remedy card if none exists."""
    tool = str(rec.get("tool") or "unknown")
    sig = str(rec.get("sig") or "")
    count = int(rec.get("count") or 0)
    if count < AUTO_DRAFT_THRESHOLD:
        return None

    try:
        from mag import remedy

        existing = remedy.by_tool(tool)
        if existing:
            return str(existing.get("id") or existing.get("name") or "")
    except Exception:
        pass

    REMEDY_DIR.mkdir(parents=True, exist_ok=True)
    rid = f"rem-auto-{_slug(tool)}-{_slug(sig.split(':')[-1] if ':' in sig else sig, 16)}"
    path = REMEDY_DIR / f"{rid}.md"
    if path.is_file():
        return rid

    err = str(rec.get("error_sample") or "")
    det = str(rec.get("detail_sample") or "")
    sig_re = re.escape(_normalize_error(err, det)[:80]) if (err or det) else tool
    body = f"""id: {rid}
name: auto {tool} failure (×{count})
tools: {tool}
signature: {sig_re}

## Prevent
This failure signature recurred {count} times in Mag runs ({sig}).
Tool: `{tool}`. Error: {err or '(see detail)'}.

## Fix
1. Read the target file/area first (`read_file` with line range).
2. Emit flat tool args — sibling keys, not nested `arguments`/`parameters` blobs.
3. One surgical `write_file` (search+replace) or one create-with-content — then verify.
4. If stuck: `python main.py fkb lookup "{tool}"` or `!remedy {tool}`.

## Probe
```text
python main.py fkb stats
```
"""
    try:
        path.write_text(body, encoding="utf-8")
    except OSError:
        return None
    return rid


def _read_log(*, tail: int = 200) -> list[dict[str, Any]]:
    if not LOG_PATH.is_file():
        return []
    rows: list[dict[str, Any]] = []
    try:
        lines = LOG_PATH.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    for line in lines[-tail:]:
        if not line.strip():
            continue
        try:
            o = json.loads(line)
            if isinstance(o, dict):
                rows.append(o)
        except json.JSONDecodeError:
            continue
    return rows


def query(text: str = "", *, tool: str | None = None, limit: int = 5) -> list[dict[str, Any]]:
    """Search deduped signatures by tool name or free-text (error/detail)."""
    q = (text or "").strip().lower()
    idx = _load_index()
    sigs: list[dict[str, Any]] = list((idx.get("signatures") or {}).values())
    hits: list[tuple[int, dict[str, Any]]] = []
    for rec in sigs:
        if tool and str(rec.get("tool") or "").lower() != tool.lower():
            continue
        hay = " ".join(
            [
                str(rec.get("tool") or ""),
                str(rec.get("error_sample") or ""),
                str(rec.get("detail_sample") or ""),
                str(rec.get("sig") or ""),
            ]
        ).lower()
        if q and q not in hay:
            continue
        score = int(rec.get("count") or 0)
        hits.append((score, rec))
    hits.sort(key=lambda x: (-x[0], str(x[1].get("last_seen") or "")), reverse=False)
    return [r for _, r in hits[:limit]]


def _tail_lines(path: Path, n: int) -> list[str]:
    """Last n lines of a file without loading it whole (B2-374's 39MB law):
    read backwards in 64KB chunks until n newlines are collected."""
    size = path.stat().st_size
    chunk = 65536
    pos = size
    data = b""
    while pos > 0 and data.count(b"\n") <= n:
        step = min(chunk, pos)
        pos -= step
        with path.open("rb") as f:
            f.seek(pos)
            data = f.read(step) + data
    lines = data.decode("utf-8", "replace").splitlines()
    return lines[-n:]


def search_log(q: str = "", *, tool: str | None = None,
               tail: int = 2000, limit: int = 20) -> dict[str, Any]:
    """B2-362 (2026-09-26): log-tail search over RAW failure events.

    The deduped index intentionally carries only sigs with count >= 2 (the
    B2-87 write-amplification law), so count-1 signatures are invisible to
    query/lookup/list and to any first-occurrence triage. This command scans
    the LOG (the full-history surface) over its most recent `tail` rows,
    bounded so the 39MB log is never fully loaded into memory (the reverse
    chunked read in _tail_lines). Matches q as a case-insensitive substring
    across kind/tool/error/detail/sig, optionally filtered by exact tool."""
    qn = (q or "").strip().lower()
    tail = max(1, min(int(tail), 100000))
    hits: list[dict[str, Any]] = []
    scanned = 0
    if LOG_PATH.is_file():
        for line in reversed(_tail_lines(LOG_PATH, tail)):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(row, dict):
                continue
            scanned += 1
            rtool = str(row.get("tool") or "")
            if tool and rtool.lower() != tool.lower():
                continue
            hay = " ".join([
                rtool, str(row.get("kind") or ""),
                str(row.get("error") or ""), str(row.get("detail") or ""),
                str(row.get("sig") or ""),
            ]).lower()
            if qn and qn not in hay:
                continue
            hits.append({
                "ts": row.get("ts"), "kind": row.get("kind"),
                "tool": rtool,
                "error": str(row.get("error") or "")[:200],
                "detail": str(row.get("detail") or "")[:200],
                "sig": str(row.get("sig") or "")[:16],
            })
            if len(hits) >= limit:
                break
    return {"query": qn, "tool": tool, "tail": tail, "scanned": scanned,
            "hits": hits[:limit], "log_only": True}


def lookup(tool: str | None = None, error_text: str = "", *, limit: int = 3) -> list[dict[str, Any]]:
    """Agent-friendly lookup: tool + optional error substring."""
    return query(error_text, tool=tool, limit=limit)


def surface_hits(*, goal: str = "", tool: str | None = None, limit: int = 4) -> list[dict[str, str]]:
    """Tips-shaped hits for context_pack / decision_framework."""
    g = (goal or "").lower()
    # Goal keywords boost relevant tools
    tool_hint = tool
    if not tool_hint:
        for t in ("write_file", "run_python", "run_shell", "read_file"):
            if t.replace("_", " ") in g or t in g:
                tool_hint = t
                break
    hits = query(g[:80], tool=tool_hint, limit=limit)
    if not hits and g:
        hits = query(g[:80], limit=limit)
    out: list[dict[str, str]] = []
    for rec in hits:
        cnt = int(rec.get("count") or 0)
        if cnt < 2:
            continue
        tool_s = str(rec.get("tool") or "?")
        det = str(rec.get("detail_sample") or rec.get("error_sample") or "")[:120]
        rid = str(rec.get("remedy_id") or "")
        tip = f"FKB ×{cnt}: {tool_s} — {det}" if det else f"FKB ×{cnt}: {tool_s} failure pattern"
        avoid = f"remedy={rid}" if rid else "check memory/remedies/"
        out.append({"id": f"fkb-{rec.get('sig', '')[:16]}", "tip": tip, "avoid": avoid, "source": "failure_kb"})
    return out


def format_block(hits: list[dict[str, Any]] | list[dict[str, str]], *, max_chars: int = 700) -> str:
    if not hits:
        return ""
    lines = ["[FAILURE KB — recurring patterns (do not repeat)]"]
    for h in hits[:5]:
        if "tip" in h:
            lines.append(f"- {h.get('tip', '')}")
            if h.get("avoid"):
                lines.append(f"  → {h['avoid'][:120]}")
        else:
            cnt = int(h.get("count") or 0)
            tool_s = h.get("tool") or "?"
            det = (h.get("detail_sample") or h.get("error_sample") or "")[:100]
            lines.append(f"- ×{cnt} {tool_s}: {det}")
            if h.get("remedy_id"):
                lines.append(f"  → remedy: {h['remedy_id']}")
    block = "\n".join(lines)
    return block[:max_chars]


def recurring_patterns(*, min_count: int = 3) -> list[dict[str, Any]]:
    """Patterns for improve scout / risk candidates."""
    idx = _load_index()
    out = []
    for rec in (idx.get("signatures") or {}).values():
        if int(rec.get("count") or 0) >= min_count:
            out.append(rec)
    out.sort(key=lambda r: (-int(r.get("count") or 0), str(r.get("last_seen") or "")))
    return out


def rebuild_index(*, reason: str, actor: str = "", min_count: int = 2) -> dict[str, Any]:
    """Reconcile signature counts from the append-only log (log bytes win).

    Dedupes by sig across every log row: count, first_seen and last_seen come
    from the log timestamps; error_sample/detail_sample/kind/tool come from
    each sig's LAST log row (falling back to the previous index sample when a
    row carries empty fields). remedy_id is preserved from the existing index
    for every sig, so a rebuild never loses or mass-redrafts remedy cards.

    Import policy: sigs already in the index are always kept (their count is
    corrected to log truth); log sigs with count >= min_count are imported.
    Count-1 sigs stay log-only by design: the index is the recurring-class
    view, a 3MB all-sigs index would be rewritten by every log_failure call,
    and a singleton is imported automatically on its next recurrence.

    Every rebuild writes the reset-receipt block "rebuild_receipt" at the top
    level of the index (see the module docstring continuity law): previous
    totals and the prior receipt's ts/reason are named, so no future rebuild
    can silently zero the cross-session counter.
    """
    prev = _load_index()
    prev_sigs: dict[str, Any] = prev.get("signatures") or {}
    total_before = sum(int(r.get("count") or 0) for r in prev_sigs.values())

    agg: dict[str, dict[str, Any]] = {}
    rows_parsed = 0
    if LOG_PATH.is_file():
        try:
            with LOG_PATH.open("r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(row, dict):
                        continue
                    sig = str(row.get("sig") or "")
                    if not sig:
                        continue
                    rows_parsed += 1
                    a = agg.get(sig)
                    if a is None:
                        a = agg[sig] = {
                            "count": 0,
                            "first": None,
                            "last": None,
                            "last_row": row,
                        }
                    a["count"] += 1
                    ts = row.get("ts")
                    if isinstance(ts, str) and ts:
                        if a["first"] is None or ts < a["first"]:
                            a["first"] = ts
                        if a["last"] is None or ts > a["last"]:
                            a["last"] = ts
        except OSError:
            pass

    sigs: dict[str, Any] = {}
    for sig, a in agg.items():
        prev_rec = prev_sigs.get(sig)
        if a["count"] < max(1, int(min_count)) and prev_rec is None:
            continue
        row = a["last_row"]
        rec = {
            "sig": sig,
            "tool": row.get("tool"),
            "error_sample": (row.get("error") or "")[:200],
            "detail_sample": (row.get("detail") or "")[:200],
            "kind": row.get("kind"),
            "count": a["count"],
            "first_seen": a["first"] or (prev_rec or {}).get("first_seen") or _now(),
            "last_seen": a["last"] or (prev_rec or {}).get("last_seen") or _now(),
            "remedy_id": (prev_rec or {}).get("remedy_id"),
        }
        if prev_rec is not None:
            # Empty fields on the newest row must not erase known samples.
            if not rec["error_sample"] and prev_rec.get("error_sample"):
                rec["error_sample"] = prev_rec["error_sample"]
            if not rec["detail_sample"] and prev_rec.get("detail_sample"):
                rec["detail_sample"] = prev_rec["detail_sample"]
            if not rec["tool"] and prev_rec.get("tool"):
                rec["tool"] = prev_rec["tool"]
        sigs[sig] = rec
    for sig, prev_rec in prev_sigs.items():
        # Index-only sigs (log trimmed or lost rows) are preserved as-is.
        if sig not in sigs:
            sigs[sig] = prev_rec

    prev_receipt = prev.get("rebuild_receipt") or {}
    receipt = {
        "ts": _now(),
        "reason": reason,
        "actor": actor,
        "log_rows_parsed": rows_parsed,
        "min_count": int(min_count),
        "signatures_before": len(prev_sigs),
        "signatures_after": len(sigs),
        "total_count_before": total_before,
        "total_count_after": sum(int(r["count"]) for r in sigs.values()),
        "previous_rebuild_ts": prev_receipt.get("ts"),
        "previous_rebuild_reason": prev_receipt.get("reason"),
    }
    _save_index({"schema": "failure_kb.signatures.v1", "signatures": sigs, "rebuild_receipt": receipt})
    return receipt


def stats() -> dict[str, Any]:
    idx = _load_index()
    sigs = list((idx.get("signatures") or {}).values())
    events = len(_read_log(tail=10000))
    return {
        "ok": True,
        "events_logged": events,
        "signatures": len(sigs),
        "recurring": len([s for s in sigs if int(s.get("count") or 0) >= AUTO_DRAFT_THRESHOLD]),
        "with_remedy": len([s for s in sigs if s.get("remedy_id")]),
        "log_path": str(LOG_PATH),
        "index_path": str(INDEX_PATH),
    }


def verify() -> dict[str, Any]:
    """B2-361 (2026-09-26): index-vs-log drift tripwire, READ-ONLY.

    Recounts the log by sig (the rebuild_index oracle, without writing) and
    compares against signatures.json. Violations, per the owning brief:
      - index-above-log: a sig whose index count exceeds its log count
        (clobbered log, lost appends, or an invented index row). Includes
        index sigs with zero log rows.
      - first_seen mismatch: index first_seen differs from the log-derived
        first_seen for a sig present in both.
    Log sigs missing from the index are EXPECTED drift (new events after a
    rebuild; count-1 sigs are log-only by the rebuild policy), never
    violations. The next rebuild heals every listed violation by design
    (log bytes win), so this command names, it never mutates.
    """
    idx = _load_index()
    sigs = idx.get("signatures") or {}
    agg: dict[str, dict[str, Any]] = {}
    rows_parsed = 0
    if LOG_PATH.is_file():
        with LOG_PATH.open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(row, dict):
                    continue
                sig = str(row.get("sig") or "")
                if not sig:
                    continue
                rows_parsed += 1
                a = agg.get(sig)
                if a is None:
                    a = agg[sig] = {"count": 0, "first": None}
                a["count"] += 1
                ts = row.get("ts")
                if isinstance(ts, str) and ts:
                    if a["first"] is None or ts < a["first"]:
                        a["first"] = ts
    above: list[dict[str, Any]] = []
    mismatched: list[dict[str, Any]] = []
    for sig in sorted(sigs):
        rec = sigs[sig] or {}
        idx_count = int(rec.get("count") or 0)
        a = agg.get(sig)
        log_count = a["count"] if a else 0
        if idx_count > log_count:
            above.append({"sig": sig[:80], "index_count": idx_count,
                          "log_count": log_count})
        elif a is not None:
            idx_first = str(rec.get("first_seen") or "")
            log_first = str(a["first"] or "")
            if idx_first and log_first and idx_first != log_first:
                mismatched.append({"sig": sig[:80], "index_first_seen": idx_first,
                                   "log_first_seen": log_first})
    return {
        "ok": not above and not mismatched,
        "command": "verify",
        "log_rows_parsed": rows_parsed,
        "index_sigs": len(sigs),
        "log_sigs": len(agg),
        "violations": len(above) + len(mismatched),
        "index_above_log": above,
        "first_seen_mismatch": mismatched,
        "note": "log sigs absent from the index are expected drift (rebuild policy), never violations; next rebuild heals every listed violation (log bytes win)",
        "log_path": str(LOG_PATH),
        "index_path": str(INDEX_PATH),
    }


def _cli(argv: list[str]) -> int:
    if not argv or argv[0] in ("stats", "status"):
        print(json.dumps(stats(), indent=2))
        return 0
    if argv[0] == "verify":
        # B2-361: index-vs-log recount; exit 0 clean, 2 violations (house
        # fresh/exit-2 convention). Read-only, never mutates.
        r = verify()
        print(json.dumps(r, indent=2, default=str)[:20000])
        return 0 if r["ok"] else 2
    if argv[0] == "list":
        rows = query("", limit=int(argv[1]) if len(argv) > 1 else 20)
        print(json.dumps(rows, indent=2, default=str)[:12000])
        return 0
    if argv[0] in ("search", "lookup", "query"):
        args = argv[1:]
        # B2-362: `search --log Q [--tail N] [--limit K]` scans the raw log
        # tail (count-1 sigs the index hides), not the deduped index.
        if "--log" in args:
            i = args.index("--log")
            q = args[i + 1] if i + 1 < len(args) else ""
            tail_n, limit_n = 2000, 20
            for j, a in enumerate(args):
                if a == "--tail" and j + 1 < len(args):
                    tail_n = int(args[j + 1])
                if a == "--limit" and j + 1 < len(args):
                    limit_n = int(args[j + 1])
            r = search_log(q, tail=tail_n, limit=limit_n)
            print(json.dumps(r, indent=2, default=str)[:12000])
            return 0 if r["hits"] else 1
        q = " ".join(args) if len(args) > 0 else ""
        tool = None
        if q.startswith("tool:"):
            parts = q.split(None, 1)
            tool = parts[0].split(":", 1)[1]
            q = parts[1] if len(parts) > 1 else ""
        rows = query(q, tool=tool, limit=10)
        print(format_block(rows) or json.dumps(rows, indent=2, default=str))
        return 0 if rows else 1
    if argv[0] == "record" and len(argv) >= 2:
        # record tool_fail write_file "detail" --error preflight
        kind = argv[1]
        tool = argv[2] if len(argv) > 2 else None
        detail = argv[3] if len(argv) > 3 else ""
        error = None
        for i, a in enumerate(argv):
            if a == "--error" and i + 1 < len(argv):
                error = argv[i + 1]
        r = log_failure(kind=kind, tool=tool, detail=detail, error=error)
        print(json.dumps(r, indent=2))
        return 0
    if argv[0] == "rebuild":
        reason = ""
        actor = ""
        min_count = 2
        for i, a in enumerate(argv):
            if a == "--reason" and i + 1 < len(argv):
                reason = argv[i + 1]
            if a == "--actor" and i + 1 < len(argv):
                actor = argv[i + 1]
            if a == "--min-count" and i + 1 < len(argv):
                try:
                    min_count = int(argv[i + 1])
                except ValueError:
                    pass
        if not reason:
            print("rebuild requires --reason \"...\" (the receipt must say why)")
            return 2
        print(json.dumps(rebuild_index(reason=reason, actor=actor, min_count=min_count), indent=2))
        return 0
    print(
        "usage: python -m mag.failure_kb [stats|verify|list|search <q>|record <kind> <tool> <detail> [--error E]|rebuild --reason R [--actor A] [--min-count N]]"
    )
    return 2


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
