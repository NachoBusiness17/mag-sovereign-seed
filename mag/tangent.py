"""Opt-in background tangents — deliberate scouts, not always-on.

Proof-of-concept for later: queue a public/cheap ask → janitor or Gemini →
memory/tangents/<id>.md. Does **not** run on Mag lab cycles unless you call it.

Trigger only via:
  python main.py tangent "…"
  POST /api/v1/tangent
  dashboard Chat → Tangent mode
  python main.py tangent --scan / --process   # explicit live scan
"""
from __future__ import annotations

import hashlib
import json
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT

TANGENT_DIR = ROOT / "memory" / "tangents"
QUEUE_PATH = TANGENT_DIR / "queue.jsonl"
LATEST_PATH = TANGENT_DIR / "latest.md"
STATE_PATH = TANGENT_DIR / "state.json"

# Patterns in live_from_grok / chat that mean "spawn a background scout"
_TANGENT_MARKERS = (
    r"\[tangent\]\s*(.+)",
    r"(?i)tangent:\s*(.+)",
    r"(?i)go check (?:that|this|on)\s*[:\-]?\s*(.+)",
    r"(?i)cool tangent[:\-]?\s*(.+)",
    r"(?i)mag,?\s*(?:scout|check|look into)\s*[:\-]?\s*(.+)",
    r"(?i)offload to (?:gemini|mag|janitor)[:\-]?\s*(.+)",
)

_PRIVATE = re.compile(
    r"(?i)(\.env|password|secret|private|intimate|data/raw|T0|T1 residual)",
)


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure() -> None:
    TANGENT_DIR.mkdir(parents=True, exist_ok=True)
    if not QUEUE_PATH.is_file():
        QUEUE_PATH.write_text("", encoding="utf-8")


def _tid(prompt: str) -> str:
    h = hashlib.sha256(f"{prompt}|{_utc()}".encode()).hexdigest()[:10]
    return f"t-{h}"


def _load_state() -> dict[str, Any]:
    _ensure()
    if STATE_PATH.is_file():
        try:
            return json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"seen_live_hashes": [], "last_scan": None}


def _save_state(st: dict[str, Any]) -> None:
    _ensure()
    STATE_PATH.write_text(json.dumps(st, indent=2, default=str), encoding="utf-8")


def enqueue(
    prompt: str,
    *,
    source: str = "manual",
    provider: str | None = None,
    prefer_gemini: bool = True,
    run_async: bool = False,
) -> dict[str, Any]:
    """Queue a tangent. Optionally start worker thread immediately."""
    prompt = (prompt or "").strip()
    if not prompt:
        return {"ok": False, "error": "empty prompt"}
    if _PRIVATE.search(prompt):
        return {
            "ok": False,
            "error": "private markers — local only, not queued to free remotes",
            "hint": "Use: python main.py dispatch '…'  (local seat)",
        }

    _ensure()
    tid = _tid(prompt)
    # default provider: gemini for public scouts if configured, else auto
    prov = provider
    if prov is None and prefer_gemini:
        try:
            from models.quota import provider_budget

            b = provider_budget("gemini")
            if b.get("configured") and b.get("budget_ok"):
                prov = "gemini"
        except Exception:
            prov = None

    row = {
        "id": tid,
        "prompt": prompt[:2000],
        "source": source,
        "provider": prov,
        "status": "queued",
        "created": _utc(),
        "result_path": None,
        "summary": None,
        "error": None,
    }
    with QUEUE_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")

    if run_async:
        threading.Thread(target=process_one, args=(tid,), daemon=True).start()
        row["status"] = "running_async"
    return {"ok": True, **row}


def list_tangents(limit: int = 20) -> dict[str, Any]:
    _ensure()
    rows: list[dict[str, Any]] = []
    if QUEUE_PATH.is_file():
        for line in QUEUE_PATH.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    # de-dupe by id keep last
    by_id: dict[str, dict[str, Any]] = {}
    for r in rows:
        by_id[str(r.get("id"))] = r
    ordered = list(by_id.values())
    ordered.reverse()
    latest = LATEST_PATH.read_text(encoding="utf-8")[:3000] if LATEST_PATH.is_file() else ""
    return {
        "ok": True,
        "count": len(ordered),
        "items": ordered[:limit],
        "latest_preview": latest,
        "dir": str(TANGENT_DIR),
    }


def _rewrite_queue(rows: list[dict[str, Any]]) -> None:
    with QUEUE_PATH.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")


def _all_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not QUEUE_PATH.is_file():
        return rows
    for line in QUEUE_PATH.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    return rows


def process_one(tid: str | None = None) -> dict[str, Any]:
    """Run oldest queued (or specific id) through Mag dispatch."""
    rows = _all_rows()
    target: dict[str, Any] | None = None
    idx = -1
    for i, r in enumerate(rows):
        if tid and r.get("id") == tid and r.get("status") in ("queued", "running_async", "error"):
            target, idx = r, i
            break
        if not tid and r.get("status") == "queued":
            target, idx = r, i
            break
    if not target:
        return {"ok": True, "action": "idle", "hint": "no queued tangents"}

    target["status"] = "running"
    target["started"] = _utc()
    rows[idx] = target
    _rewrite_queue(rows)

    prompt = str(target.get("prompt") or "")
    provider = target.get("provider")
    goal = (
        f"Background Mag tangent (public/cheap). Be concrete. "
        f"No secrets. Goal: {prompt}"
    )
    try:
        from mag.dispatch import dispatch as mag_dispatch

        res = mag_dispatch(
            goal,
            execute=True,
            force_provider=str(provider) if provider else None,
            force_seat=None,
        )
    except Exception as e:
        res = {"ok": False, "error": str(e)}

    # Build markdown report
    answer = ""
    if isinstance(res, dict):
        r = res.get("result")
        if isinstance(r, dict):
            answer = str(r.get("answer") or r.get("deliverable") or r.get("summary") or "")[:8000]
        if not answer:
            answer = str(res.get("hint") or res.get("error") or "")[:2000]
        if not answer and res.get("context_pack_excerpt"):
            answer = "(deferred to grok_tui — not a background tangent result)\n" + str(
                res.get("context_pack_excerpt")
            )[:1500]

    body = "\n".join(
        [
            f"# Tangent {target.get('id')}",
            "",
            f"- created: `{target.get('created')}`",
            f"- finished: `{_utc()}`",
            f"- source: `{target.get('source')}`",
            f"- provider: `{provider or 'auto'}`",
            f"- seat: `{res.get('seat') if isinstance(res, dict) else '?'}`",
            f"- ok: **{bool(isinstance(res, dict) and res.get('ok'))}**",
            "",
            "## Ask",
            "",
            prompt,
            "",
            "## Result",
            "",
            answer or "_(empty)_",
            "",
            "## Raw (trimmed)",
            "",
            "```json",
            json.dumps(
                {k: res.get(k) for k in ("ok", "seat", "provider", "job", "hint", "error") if isinstance(res, dict)},
                indent=2,
                default=str,
            )[:3000],
            "```",
            "",
            "_Grok: open only if worth elevating — do not re-run the scout here._",
            "",
        ]
    )
    out_path = TANGENT_DIR / f"{target['id']}.md"
    out_path.write_text(body, encoding="utf-8")
    LATEST_PATH.write_text(body, encoding="utf-8")

    ok = bool(isinstance(res, dict) and res.get("ok"))
    target["status"] = "done" if ok else "error"
    target["finished"] = _utc()
    target["result_path"] = str(out_path)
    target["summary"] = (answer or "")[:400]
    target["error"] = None if ok else str((res or {}).get("error") if isinstance(res, dict) else "fail")
    rows[idx] = target
    _rewrite_queue(rows)

    _ping_attention(target, out_path)
    return {"ok": ok, "id": target["id"], "path": str(out_path), "summary": target["summary"]}


def process_queue(max_n: int = 1) -> dict[str, Any]:
    done = []
    for _ in range(max_n):
        r = process_one()
        if r.get("action") == "idle":
            break
        done.append(r)
    return {"ok": True, "processed": done, "n": len(done)}


def _ping_attention(row: dict[str, Any], path: Path) -> None:
    try:
        att = ROOT / "memory" / "attention.md"
        prev = att.read_text(encoding="utf-8") if att.is_file() else "# Mag attention\n\n"
        block = (
            f"\n---\n\n### Tangent {row.get('id')} — {_utc()}\n\n"
            f"- **ask:** {str(row.get('prompt') or '')[:200]}\n"
            f"- **status:** {row.get('status')}\n"
            f"- **file:** `{path}`\n"
            f"- **summary:** {str(row.get('summary') or '')[:300]}\n"
            f"- Open latest: `memory/tangents/latest.md` or elevate to Grok with pack only.\n"
        )
        att.write_text(block + "\n" + prev[:12000], encoding="utf-8")
    except Exception:
        pass


def scan_live_for_tangents(*, auto_run: bool = True) -> dict[str, Any]:
    """Pull TANGENT markers from live_from_grok.md into the queue."""
    live = ROOT / "memory" / "live_from_grok.md"
    if not live.is_file():
        return {"ok": True, "enqueued": [], "hint": "no live_from_grok"}
    text = live.read_text(encoding="utf-8", errors="replace")
    st = _load_state()
    seen = set(st.get("seen_live_hashes") or [])
    found: list[str] = []
    for pat in _TANGENT_MARKERS:
        for m in re.finditer(pat, text):
            prompt = (m.group(1) or "").strip()
            # strip trailing markdown junk
            prompt = re.split(r"\n|</|`", prompt)[0].strip()[:500]
            if len(prompt) < 12:
                continue
            h = hashlib.sha256(prompt.encode()).hexdigest()[:16]
            if h in seen:
                continue
            seen.add(h)
            found.append(prompt)

    enqueued = []
    for p in found[:5]:
        r = enqueue(p, source="live_from_grok", prefer_gemini=True, run_async=False)
        if r.get("ok"):
            enqueued.append(r.get("id"))

    st["seen_live_hashes"] = list(seen)[-200:]
    st["last_scan"] = _utc()
    _save_state(st)

    ran = []
    if auto_run and enqueued:
        ran = process_queue(max_n=min(2, len(enqueued))).get("processed") or []

    return {"ok": True, "enqueued": enqueued, "processed": ran}


def cycle_hook() -> dict[str, Any]:
    """Not used by lab by default. Call explicitly if you re-enable later."""
    scan = scan_live_for_tangents(auto_run=False)
    proc = process_queue(max_n=1)
    return {"ok": True, "scan": scan, "process": proc, "note": "opt-in only"}
