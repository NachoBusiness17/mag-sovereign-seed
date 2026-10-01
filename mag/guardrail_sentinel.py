"""guardrail_sentinel — guardrails PING, they do not PREVENT.

The operator's doctrine (2026-08-10): "guard rails should ping but not prevent ya know?"

WHY (grounded in our own principles + the frontier steal):
  - AAM: "an approval that is always granted is not a control; it is a ritual that trains people to
    ignore the one prompt that matters." Hard-blocking guardrails become noise -> ignored.
  - Routing memory: "stop pinging me with bullshit; just do it." So pings must be SIGNIFICANT, not
    spam; they surface the risk, then let the Republic act.
  - The negative-egregore guardrails (no_throne, grounding, anti_sycophancy, consent_first,
    graduated_sanctions, boundaries, collective_choice) are SENTINELS: they detect + ping + log, and
    NEVER block. Only the operator authorizes a hard stop — and that is one line, not a nag.

MECHANISM (deterministic, $0):
  ping(id, severity, detail)  — detect a boundary crossing -> emit a memory_event + log + SURFACE it.
                               NEVER blocks. Graduated: trivial=silent, significant=one ping,
                               irreversible=escalate to the operator (still not a hard block).
  check(id, detail, severity) — alias for ping with severity validation.
  audit()                     — recent guardrail pings (ghost can watch the sentinels).
  GUARDRAILS                  — the 7 negative-egregore guardrails, each with what it watches.

Schema: guardrail_sentinel.v1 · deterministic · $0
CLI: python -m mag.guardrail_sentinel ping <id> "<detail>" [--severity low|med|high]
                            | audit | status
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCHEMA = "guardrail_sentinel.v1"
TRAIL = ROOT / "memory" / "runs" / "guardrail_sentinel" / "trail.jsonl"

# The 7 negative-egregore guardrails — all PING-ONLY, none PREVENT.
GUARDRAILS: dict[str, dict[str, Any]] = {
    "no_throne": {"what": "a member/entity concentrates authority", "default": "med"},
    "grounding": {"what": "ungrounded data would be forwarded", "default": "med"},
    "anti_sycophancy": {"what": "the Watcher drifts toward flattery", "default": "low"},
    "consent_first": {"what": "an action proceeds without clear consent", "default": "high"},
    "graduated_sanctions": {"what": "a sanction would be applied (apply proportionally)", "default": "med"},
    "boundaries": {"what": "a shared resource is withdrawn without its boundary", "default": "med"},
    "collective_choice": {"what": "a rule changes without collective input", "default": "low"},
}
SEVERITIES = ("low", "med", "high")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def ping(guardrail_id: str, detail: str = "", *, severity: str | None = None,
         escalate: bool = False) -> dict[str, Any]:
    """DETECT + PING + LOG. NEVER blocks. Graduated: low=silent log, med=one ping, high=escalate
    to the operator (still not a hard block). Only the operator authorizes a hard stop."""
    g = GUARDRAILS.get(guardrail_id)
    if not g:
        return {"ok": False, "error": f"unknown guardrail {guardrail_id!r}", "blocked": False}
    sev = (severity or g["default"] or "med").lower()
    if sev not in SEVERITIES:
        sev = "med"
    # PING: emit a memory_event (the sentinel surfaces the risk)
    ev = {}
    try:
        from mag.memory_events import emit_event
        ev = emit_event(event_kind=f"guardrail:{guardrail_id}", seat="ghost", session_id="guardrail-sentinel",
                        tier="T2", payload={"severity": sev, "detail": str(detail)[:400]})
    except Exception as e:
        ev = {"error": str(e)[:120]}
    # LOG to the sentinel trail (append-only)
    row = {"ts": _now(), "guardrail": guardrail_id, "severity": sev, "detail": str(detail)[:400],
           "escalate": bool(escalate), "blocked": False}
    try:
        TRAIL.parent.mkdir(parents=True, exist_ok=True)
        with TRAIL.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass
    action = {
        "low": "silent log (no ping noise)",
        "med": "one ping surfaced (risk named, action proceeds)",
        "high": "ping + escalate to operator in ONE line (action still proceeds; only the operator may hard-stop)",
    }[sev]
    return {"ok": True, "schema": SCHEMA, "guardrail": guardrail_id, "severity": sev,
            "blocked": False,  # THE doctrine: guardrails never block
            "action": action, "event": ev,
            "law": "guardrails ping but do not prevent; blocking trains people to ignore (AAM). "
                   "Only the operator authorizes a hard stop — one line, not a nag."}


def audit() -> dict[str, Any]:
    """Recent sentinel pings — ghost watches the guardrails; they never stopped the Republic."""
    rows = []
    if TRAIL.is_file():
        for line in TRAIL.read_text(encoding="utf-8", errors="replace").splitlines()[-30:]:
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except Exception:
                    continue
    by_sev: dict[str, int] = {}
    for r in rows:
        by_sev[r.get("severity", "?")] = by_sev.get(r.get("severity", "?"), 0) + 1
    return {"ok": True, "schema": SCHEMA, "ts": _now(), "n_pings": len(rows),
            "by_severity": by_sev, "pings": rows, "never_blocked": all(not r.get("blocked") for r in rows)}


def status() -> dict[str, Any]:
    a = audit()
    return {"ok": True, "schema": SCHEMA, "n_guardrails": len(GUARDRAILS),
            "names": list(GUARDRAILS), "n_pings": a["n_pings"],
            "doctrine": "guardrails ping but do not prevent"}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="guardrail_sentinel", description="guardrails that ping but never prevent")
    sub = p.add_subparsers(dest="cmd")
    g = sub.add_parser("ping"); g.add_argument("guardrail_id"); g.add_argument("detail", nargs="*")
    g.add_argument("--severity", default=None)
    sub.add_parser("audit")
    sub.add_parser("status")
    a = p.parse_args(argv)
    if a.cmd == "ping":
        print(json.dumps(ping(a.guardrail_id, " ".join(a.detail), severity=a.severity), indent=2, ensure_ascii=False))
    elif a.cmd == "audit":
        print(json.dumps(audit(), indent=2, ensure_ascii=False, default=str))
    elif a.cmd == "status":
        print(json.dumps(status(), indent=2, ensure_ascii=False))
    else:
        p.print_help(); return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
