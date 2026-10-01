"""Sancho boot — cold-start self-analysis + optional Mag ensure.

Not Jarvis cosplay. Sensor + fix + short truth card.

  python main.py boot
  python main.py boot --ensure   # spawn lab if integral is down
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT

BOOT_JSON = ROOT / "watch" / "boot_latest.json"
BOOT_MD = ROOT / "memory" / "boot_report.md"
BOOT_LOG = ROOT / "logs" / "boot.jsonl"


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _quota_snapshot() -> dict[str, Any]:
    try:
        from models.providers import list_provider_ids
        from models.quota import provider_budget

        rows = []
        for pid in list_provider_ids()[:12]:
            try:
                b = provider_budget(pid)
            except Exception as e:
                rows.append({"id": pid, "error": str(e)[:80]})
                continue
            rows.append(
                {
                    "id": pid,
                    "configured": b.get("configured"),
                    "remaining_calls": b.get("remaining_calls"),
                    "remaining_tokens": b.get("remaining_tokens"),
                    "period": (b.get("quota") or {}).get("period")
                    if isinstance(b.get("quota"), dict)
                    else b.get("period"),
                }
            )
        return {"ok": True, "providers": rows}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


def _session_hint() -> dict[str, Any]:
    ptr = ROOT / "watch" / "active_session.json"
    out: dict[str, Any] = {"session_id": None, "cwd": None}
    if ptr.is_file():
        try:
            meta = json.loads(ptr.read_text(encoding="utf-8"))
            out["session_id"] = meta.get("session_id")
            out["cwd"] = meta.get("cwd")
        except (json.JSONDecodeError, OSError):
            pass
    sid = os.environ.get("GROK_SESSION_ID")
    if sid:
        out["session_id"] = sid
        out["from_env"] = True
    bio = ROOT / "memory" / "biography"
    out["has_latest_pdf"] = (bio / "latest.pdf").is_file()
    if out["session_id"]:
        out["session_md"] = (bio / f"{out['session_id']}.md").is_file()
        out["session_pdf"] = (bio / f"{out['session_id']}.pdf").is_file()
    return out


def format_sancho(report: dict[str, Any]) -> str:
    """Plain status card — spine, no cape."""
    s = report.get("sanity") or {}
    integral = s.get("integral") or {}
    rec = s.get("recording") or {}
    lanes = s.get("lanes") or {}
    l0 = lanes.get("L0_ollama") or {}
    action = report.get("action") or "?"
    status = (s.get("status") or "?").upper()
    lines = [
        "# Sancho boot",
        f"- **ts:** `{report.get('ts', '')}`",
        f"- **integral:** **{status}**  action=`{action}`",
        f"- **pid:** `{integral.get('pid')}` alive=`{integral.get('pid_alive')}` "
        f"port8765=`{integral.get('port_8765')}`",
        f"- **live board:** stale=`{(rec.get('live_stale'))}` "
        f"age_s=`{rec.get('live_age_seconds')}`",
        f"- **L0 ollama:** ok=`{l0.get('ok')}`",
        f"- **dashboard:** http://127.0.0.1:8765/",
    ]
    sess = report.get("session") or {}
    if sess.get("session_id"):
        lines.append(f"- **session:** `{sess['session_id']}`")
        lines.append(
            f"- **this session pack:** md=`{sess.get('session_md')}` "
            f"pdf=`{sess.get('session_pdf')}`"
        )
    miss = s.get("missing_while_down") or []
    if miss:
        lines.append("- **missing:** " + "; ".join(miss[:4]))
    need = report.get("need") or []
    if need:
        lines.append("- **need:**")
        for n in need[:6]:
            lines.append(f"  - {n}")
    else:
        lines.append("- **need:** nothing blocking — Mag is the front door")
    lines.extend(
        [
            "",
            "_Sancho: sensors + fix. Not a speech. "
            "`python main.py boot --ensure` on cold start; "
            "`python main.py doctor` for full map._",
            "",
        ]
    )
    return "\n".join(lines)


def _needs(sanity: dict[str, Any], ensure_ran: bool, ensure_ok: bool | None) -> list[str]:
    out: list[str] = []
    status = sanity.get("status")
    if status == "down":
        if ensure_ran and not ensure_ok:
            out.append(
                "lab spawn failed — cage first: docker compose restart mag "
                "(not host python main.py lab)"
            )
        elif not ensure_ran:
            out.append("integral down — run: python main.py boot --ensure")
        else:
            out.append("lab was restarted; re-check in a few seconds if still degraded")
    elif status == "degraded":
        out.append("partial — doctor if live board freezes")
    lanes = sanity.get("lanes") or {}
    if not (lanes.get("L0_ollama") or {}).get("ok"):
        out.append("Ollama not answering — local seats weak until it is")
    if not (sanity.get("integral") or {}).get("port_8765"):
        out.append("dashboard :8765 closed — lab not serving UI")
    return out


def run_boot(*, ensure: bool = False, light: bool = False) -> dict[str, Any]:
    """Self-analysis; if ensure and down, spawn lab via guard.ensure_lab."""
    from mag.health import sanity
    from mag.guard import ensure_lab

    started = _ts()
    pre = sanity()
    action = "healthy"
    ensure_result: dict[str, Any] | None = None

    status = pre.get("status")
    live_stale = (pre.get("recording") or {}).get("live_stale")
    if ensure and (status != "up" or live_stale):
        ensure_result = ensure_lab(restart=True)
        action = ensure_result.get("action") or "ensure"
    elif status != "up":
        action = "need_lab"
    elif live_stale:
        # no ensure: still try catch-up only if mag is up
        if status == "up":
            ensure_result = ensure_lab(restart=False)
            action = ensure_result.get("action") or "catch_up"
        else:
            action = "live_stale"

    post = sanity()
    session = _session_hint()
    quota = {} if light else _quota_snapshot()
    ensure_ok = None if ensure_result is None else bool(ensure_result.get("ok"))
    need = _needs(post, ensure_ran=ensure and ensure_result is not None, ensure_ok=ensure_ok)

    report: dict[str, Any] = {
        "schema": "sancho_boot.v1",
        "ts": started,
        "done_ts": _ts(),
        "action": action,
        "ensure": ensure,
        "ensure_result": ensure_result,
        "sanity": {
            "status": post.get("status"),
            "integral": post.get("integral"),
            "recording": {
                k: (post.get("recording") or {}).get(k)
                for k in (
                    "live_age_seconds",
                    "live_stale",
                    "active_session",
                    "has_latest_dossier",
                )
            },
            "lanes": post.get("lanes"),
            "missing_while_down": post.get("missing_while_down"),
            "reconnect": post.get("reconnect"),
        },
        "session": session,
        "quota": quota,
        "need": need,
        "ok": post.get("status") == "up" and not (post.get("recording") or {}).get("live_stale"),
    }
    report["text"] = format_sancho(report)

    BOOT_JSON.parent.mkdir(parents=True, exist_ok=True)
    BOOT_MD.parent.mkdir(parents=True, exist_ok=True)
    BOOT_LOG.parent.mkdir(parents=True, exist_ok=True)
    BOOT_JSON.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    BOOT_MD.write_text(report["text"], encoding="utf-8")
    with BOOT_LOG.open("a", encoding="utf-8") as f:
        slim = {
            "ts": report["ts"],
            "action": action,
            "status": post.get("status"),
            "ok": report["ok"],
            "need": need,
            "session_id": session.get("session_id"),
        }
        f.write(json.dumps(slim, default=str) + "\n")

    try:
        from mag.tripartite_boot import run_coordinated_boot

        report["tripartite"] = run_coordinated_boot(actor="boot", seat="mag")
    except Exception:
        pass

    return report
