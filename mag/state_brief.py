"""START BRIEF — the deterministic "bard report" that greets the operator on wake.

Closes the "nothing greets me after reboot" gap. Renders a CHEAP, deterministic
(no LLM) markdown greeting at `state/START_BRIEF.md` from LIVE framework state, so
on every VS Code start / wake the operator sees where we were, what's running,
what landed, and what's next — without ceremony and at $0.

This is ALSO the "measured transfer" primitive: it quantifies the data it moves
(byte size, freshness, verkle root, queue counts, landed answers) so transferring
state between sessions is a measured, verifiable act rather than a vibe.

Schema: state_brief.v1

CLI:
  python -m mag.state_brief            # write state/START_BRIEF.md
  python -m mag.state_brief --dry      # print the rendered brief, don't write
  python -m mag.state_brief --json     # print the measured payload, don't write

Wired into: watch/sancho_boot_hook.py (SessionStart) + main.py state-brief.
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
except ImportError:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

START_BRIEF = ROOT / "state" / "START_BRIEF.md"
SCHEMA = "state_brief.v1"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read(path: Path, maxlen: int = 0) -> str:
    try:
        t = path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return ""
    return t[:maxlen] if maxlen else t


def _size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def _recent_answers(n: int = 3) -> list[dict[str, Any]]:
    """Recently completed research packs (.answer.remote.md / .answer.local.md)."""
    d = ROOT / "memory" / "research_packs"
    out: list[dict[str, Any]] = []
    if not d.is_dir():
        return out
    for p in sorted(d.glob("*.answer.*.md"), key=lambda x: x.stat().st_mtime, reverse=True):
        base = p.name.split(".answer.")[0]
        ts = base[:15]
        try:
            ts = f"{ts[:4]}-{ts[4:6]}-{ts[6:8]} {ts[9:11]}:{ts[11:13]}Z"
        except Exception:
            pass
        kind = "remote" if "remote" in p.name else "local"
        first = _read(p, 160).replace("\n", " ")
        out.append({"id": base, "ts": ts, "kind": kind, "path": p.name, "snippet": first})
        if len(out) >= n:
            break
    return out


def _supervisor() -> dict[str, Any]:
    try:
        from mag.process_supervisor import status

        st = status()
        return {"running": st.get("running") or [], "loops": st.get("loops") or []}
    except Exception as e:
        return {"error": str(e)[:120]}


def gather() -> dict[str, Any]:
    """Assemble the measured state payload (deterministic, $0, no LLM)."""
    out: dict[str, Any] = {"ts": _now(), "schema": SCHEMA}

    # Reuse the live session-state brief for the core state read (one source).
    try:
        from mag.session_state_brief import gather_state

        base = gather_state()
        out["session"] = base
    except Exception as e:
        out["session_error"] = str(e)[:120]

    # Supervisor: what loops are actually alive right now.
    out["supervisor"] = _supervisor()

    # Ghost sense digest: frustration / steers / unattended flags.
    try:
        from mag.ghost import sense

        g = sense()
        out["ghost"] = {
            "inbox_pending": g.get("inbox_pending"),
            "frustration_total": g.get("frustration_total"),
            "frustration_signals": g.get("frustration_signals"),
            "unattended_autonomy_run": g.get("context", {}).get("unattended_autonomy_run"),
            "autorun_loop": g.get("context", {}).get("autorun_loop"),
        }
    except Exception as e:
        out["ghost_error"] = str(e)[:120]

    # What landed while away: completed research answers.
    out["landed_answers"] = _recent_answers(3)

    # Autonomy run summary (the "read me on return" card), if present.
    try:
        p = ROOT / "memory" / "autonomy"
        if p.is_dir():
            latest = sorted(p.glob("*.md"), key=lambda x: x.stat().st_mtime, reverse=True)
            if latest:
                out["autonomy_summary"] = latest[0].name
    except Exception:
        pass

    # MEASURE block: quantify the transfer itself (bytes, freshness, cost).
    sz = _size(START_BRIEF)
    out["measure"] = {
        "schema": "measure.v1",
        "bytes_out": sz,
        "freshness_s": None,
        "verkle_root": (base or {}).get("verkle", {}).get("root"),
        "queue_total": (base or {}).get("queue", {}).get("total"),
        "fleet_live_n": (base or {}).get("fleet_live_n"),
        "landed_answers_n": len(out["landed_answers"]),
        "cost_usd": 0.0,  # deterministic local render — no model spend
        "llm_calls": 0,
        "notes": "deterministic local render; nothing to re-ask, nothing to pay.",
    }
    # freshness = seconds since supervisor last changed / since last brief write.
    try:
        m = START_BRIEF.stat().st_mtime
        out["measure"]["freshness_s"] = int(datetime.now().timestamp() - m)
    except OSError:
        out["measure"]["freshness_s"] = None
    return out


def render(s: dict[str, Any]) -> str:
    """Deterministic greeting markdown from the measured state payload."""
    L: list[str] = []
    L.append("# START BRIEF — where we are")
    L.append("")
    L.append(f"_Schema {s.get('schema')} · {s.get('ts', '')[:19]}Z · deterministic, $0._")
    L.append("")

    base = s.get("session") or {}

    L.append("## 🟢 What's running")
    sup = s.get("supervisor") or {}
    running = sup.get("running") or []
    if running:
        L.append(f"- Loops alive: **{', '.join(running)}**")
    else:
        L.append("- ⚠️ **No framework loops alive** — nothing is draining the queue.")
        L.append("  Wake it: `main.py wake` (supervisor up + brief).")
    goal = base.get("current_goal") or "(none)"
    L.append(f"- Current goal: `{goal[:120]}`")
    L.append(f"- Current status: `{base.get('current_status') or '?'}`")
    L.append("")

    L.append("## 📦 What's queued")
    q = base.get("queue") or {}
    L.append(f"- Queue total: `{q.get('total')}` · live fleet: `{base.get('fleet_live_n', 0)}`")
    for item in (base.get("queue_active") or [])[:5]:
        L.append(f"  - `{item.get('queue_id')}` [{item.get('status')}] {item.get('goal')}")
    L.append("")

    L.append("## 🧠 What landed while you were away")
    answers = s.get("landed_answers") or []
    if answers:
        for a in answers:
            L.append(f"- **{a.get('id')}** ({a.get('kind')}, {a.get('ts')}) — {a.get('snippet')}…")
    else:
        L.append("- (no completed research answers yet)")
    if s.get("autonomy_summary"):
        L.append(f"- Autonomy run summary: `memory/autonomy/{s['autonomy_summary']}`")
    L.append("")

    L.append("## ⚙️ Health")
    gh = s.get("ghost") or {}
    L.append(f"- Inbox pending: `{gh.get('inbox_pending')}` · frustration total: `{gh.get('frustration_total')}`")
    L.append(f"- Ghost auto-run: `{gh.get('unattended_autonomy_run')}` · autorun loop: `{gh.get('autorun_loop')}`")
    sup_err = sup.get("error")
    if sup_err:
        L.append(f"- ⚠️ supervisor: {sup_err}")
    L.append("")

    L.append("## 📏 Transfer measure (this brief)")
    m = s.get("measure") or {}
    L.append(f"- Rendered bytes: `{m.get('bytes_out')}` · freshness: `{m.get('freshness_s')}s`")
    L.append(f"- Verkle root: `{m.get('verkle_root')}` · queue total: `{m.get('queue_total')}`")
    L.append(f"- Cost: **${m.get('cost_usd')}** · LLM calls: `{m.get('llm_calls')}`")
    L.append("")
    L.append("_Regenerate: `python -m mag.state_brief`. Greeting is deterministic — no model spend, no ceremony._")
    return "\n".join(L)


def write(s: dict[str, Any] | None = None) -> dict[str, Any]:
    s = s or gather()
    START_BRIEF.parent.mkdir(parents=True, exist_ok=True)
    text = render(s)
    START_BRIEF.write_text(text, encoding="utf-8")
    s["measure"]["bytes_out"] = len(text.encode("utf-8"))
    s["measure"]["freshness_s"] = 0
    return {
        "ok": True,
        "path": str(START_BRIEF),
        "schema": SCHEMA,
        "ts": s["ts"],
        "measure": s["measure"],
        "bytes": len(text.encode("utf-8")),
    }


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    ap = argparse.ArgumentParser(prog="state-brief", description="Write the START BRIEF greeting")
    ap.add_argument("--dry", action="store_true", help="Print rendered brief, don't write")
    ap.add_argument("--json", action="store_true", help="Print measured payload, don't write")
    args = ap.parse_args(argv)
    s = gather()
    if args.json:
        print(json.dumps(s, indent=2, default=str)[:8000])
        return 0
    if args.dry:
        print(render(s))
        return 0
    res = write(s)
    print(json.dumps(res, indent=2, default=str)[:2000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
