"""swarm_grok_watch — the deterministic WATCH over the swarm->grok harness lane (2026-08-16).

WHY (operator dogfood audit, 2026-08-16): "is the swarm actually steering grok?" The audit found
the swarm drains (24 queued / 52 done) but the grok lane FAILS: 5 of the last 6 harness
escalations returned ok=False. Root cause (grounded, read the actual result files): every failure
is `Max turns reached` — the harness prompt over-invites loading Mag framework/skills, so grok
burns its turn budget narrating process instead of answering. The swarm thinks it's steering grok;
grok never hears it. This module is the WATCH that catches that — deterministic, $0, folded into
the governor cadence (pause-first law: we watch, we pause when amiss, we correct).

The lane: refine_loop._call_frontier -> harness.grok_cli.escalate_via_harness -> queue/results/*-harness.json

Schema: swarm_grok_watch.v1 · deterministic + $0 · reuse: config.RESULTS_DIR, harness.grok_cli

2026-09-22: restored to this estate from mag-current-rebuild (the module existed there but not
here — the governor's per-tick import errored every cycle since the drift). Same content.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import RESULTS_DIR
except Exception:
    from config import ROOT as _R
    RESULTS_DIR = _R / "queue" / "results"

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCHEMA = "swarm_grok_watch.v1"

# Deterministic failure classifiers — what "amiss" looks like on the grok lane (root-cause grounded).
_DRIFT_MARKERS = ("loading mag", "loading the mag", "i'll load", "load mag", "framework first",
                  "loads the mag", "loading harness rules")
_MAXTURNS_MARKERS = ("max turns reached", "max turns", "error: max turns")
_HEDGE_MARKERS = ("i cannot", "i can't", "as an ai", "i don't have enough context")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def classify_result(r: dict[str, Any]) -> dict[str, Any]:
    """Deterministic: what kind of failure (or success) is this harness result? $0."""
    if r.get("ok"):
        return {"ok": True, "class": "ok"}
    stderr = (r.get("stderr") or "").lower()
    summary = (r.get("summary") or "").lower()
    deliverable = (r.get("deliverable") or "").lower()
    blob = " ".join([stderr, summary, deliverable])
    if any(m in stderr for m in _MAXTURNS_MARKERS):
        if any(m in blob for m in _DRIFT_MARKERS):
            return {"ok": False, "class": "maxturns_framework_drift",
                    "reason": "max turns burned loading framework instead of answering"}
        return {"ok": False, "class": "maxturns", "reason": "max turns reached (no deliverable)"}
    if any(m in blob for m in _DRIFT_MARKERS):
        return {"ok": False, "class": "framework_drift",
                "reason": "narrated framework-loading instead of answering"}
    if any(m in blob for m in _HEDGE_MARKERS):
        return {"ok": False, "class": "hedge", "reason": "hedged/refused instead of answering"}
    code = int(r.get("exit_code") or 1)
    if code != 0:
        return {"ok": False, "class": "exit_nonzero", "reason": f"exit code {code}"}
    return {"ok": False, "class": "unknown", "reason": "unclassified failure"}


def scan(*, lookback: int = 12) -> dict[str, Any]:
    """Watch the grok harness lane: read recent results, classify, report the failure rate."""
    files = sorted(RESULTS_DIR.glob("*-harness.json"),
                   key=lambda p: p.stat().st_mtime, reverse=True)[:lookback]
    rows = []
    for f in files:
        try:
            j = json.loads(f.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        cls = classify_result(j)
        rows.append({"file": f.name, "ts": (j.get("ts") or j.get("finished_at") or ""),
                     **cls, "summary": (j.get("summary") or "")[:80]})
    n = len(rows)
    fails = [r for r in rows if not r.get("ok")]
    n_fail = len(fails)
    # collapse to classes for the dominant-failure diagnosis
    classes: dict[str, int] = {}
    for r in fails:
        c = r.get("class") or "unknown"
        classes[c] = classes.get(c, 0) + 1
    dominant = max(classes.items(), key=lambda kv: kv[1])[0] if classes else ""
    rate = (n_fail / n) if n else 0.0
    # PAUSE verdict (pause-first law): high failure rate -> pause the lane + correct the prompt.
    degraded = n >= 4 and rate >= 0.5
    return {
        "ok": True, "schema": SCHEMA, "ts": _now(), "n": n, "n_fail": n_fail,
        "fail_rate": round(rate, 2), "classes": classes, "dominant_failure": dominant,
        "degraded": degraded,
        "pause": degraded,  # deterministic: watch -> pause when amiss
        "verdict": "PAUSE_LANE" if degraded else ("HEALTHY" if rate == 0 else "WATCHING"),
        "rows": rows,
    }


def _corrective_prompt(goal: str, context: str = "") -> str:
    """GENTLY CORRECT the root cause: the harness prompt over-invited framework/skill loading,
    which burned turns. The corrective prompt forbids it explicitly (same fix that works on the
    seat burner: 'Do NOT load any framework'). Returns the fixed prompt text for the harness."""
    ctx = f"\n\nContext (ground truth):\n{context[:12000]}" if context else ""
    return (
        "You are the specialist lane for Sovereign Mag. Do NOT load any framework, tool, skill, "
        "compass, or file. Do NOT narrate your process. Answer the goal DIRECTLY with substance.\n\n"
        f"## Goal\n{goal}\n{ctx}\n\n"
        "Rules: one job, substance, no process narration, no framework-loading preamble. "
        "Prefer writing concrete files under the cwd when useful. Respect private data. "
        "End with:\nSUMMARY: ...\nDELIVERABLE: ..."
    )


def run_cadence(*, lookback: int = 12, dry: bool = True) -> dict[str, Any]:
    """The WATCH cadence: scan the grok lane; if degraded, PAUSE and report the corrective fix
    (dry=True just reports — the governor applies it). Deterministic + $0."""
    s = scan(lookback=lookback)
    return {
        "ok": True, "schema": SCHEMA, "ts": _now(), "watch": s,
        "action": "PAUSE_GROK_LANE" if s.get("pause") else "CONTINUE",
        "corrective": _corrective_prompt("(goal)") if s.get("pause") else "",
        "note": "watch the swarm->grok harness lane; when failures dominate, pause and correct "
                "the prompt (root cause: framework-loading burns turns, never answers)",
        "dry": dry,
    }


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "contract": "classify_result(r)->failure class; scan()->failure rate + dominant; "
                        "run_cadence()->pause verdict + corrective; status()->this",
            "cost": "deterministic + $0 (reads result files, no model calls)",
            "reuse": "config.RESULTS_DIR, harness.grok_cli",
            "root_cause": "5/6 harness escalations fail: max turns burned loading framework "
                          "(grounded 2026-08-16) — the swarm thinks it steers grok; grok never answers"}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = (argv[0] if argv else "status").lower()
    if cmd == "scan":
        print(json.dumps(scan(), indent=2, ensure_ascii=False, default=str))
        return 0
    if cmd in ("cadence", "run"):
        print(json.dumps(run_cadence(), indent=2, ensure_ascii=False, default=str))
        return 0
    print(json.dumps(status(), indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
