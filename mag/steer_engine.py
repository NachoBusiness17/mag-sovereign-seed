"""steer_engine — the UNIFIED sovereign steering engine (moonshot: one protocol steers every seat,
every worker, and ourselves).

OPERATOR (2026-08-12): "research deeply and improve it and moonshot it" — exploit what we learned
steering grokbot (the controlled-seat best practice: steering-loaded spec + directives + acceptance
+ report) everywhere. Today steering is SCATTERED and STATIC: frontier_steer._STEER (mined
invariants), grok_bot._DIRECTIVES (seat), rib_bus domain RIBs, operator_directives.md. Each site
injects its own block; none learn.

THE ENGINE (the moonshot seed — one protocol):
  1. compile(domain)  — merge ALL steering sources into ONE canonical, deduped steer block:
                        frontier invariants (mined) + operator directives + domain RIBs +
                        grokbot seat directives. Deterministic, $0.
  2. spec(task, domain, acceptance) — the CONTROLLED-SEAT SPEC (Grok's best practice) applied to
                        ANY task: steering + directives + acceptance + report contract. One shape
                        for every seat and worker, not just grok-bot.
  3. inject_for(task, domain) — the UNIFIED injection (improves frontier_steer.inject +
                        rib_bus.inject_for): one canonical steer block + the acceptance contract,
                        so every dispatched task carries the same disciplined steering.
  4. fold()/telemetry — record what steering was injected + its outcome, so the LOOP learns what
                        steering works (telemetry-fed, not static). Feeds behavioral_lensing +
                        steer_telemetry + the standing wave.

MOONSHOT: one self-steering sovereign layer — every seat, every worker, and the loop itself carry
the same compiled steering, and the loop tunes that steering from outcomes each cycle. The system
steers itself the way we learned to steer grokbot.

Schema: steer_engine.v1 · deterministic + $0 · reuse: frontier_steer, rib_bus, operator_directives,
grok_bot, steer_telemetry
"""
from __future__ import annotations

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

SCHEMA = "steer_engine.v1"
TELEMETRY = ROOT / "memory" / "steer_engine" / "telemetry.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sources(domain: str) -> list[tuple[str, str]]:
    """Gather steering from ALL sources: (label, steer_line). Deterministic + $0, honest."""
    out: list[tuple[str, str]] = []
    # 1. frontier invariants (mined from leaked prompts)
    try:
        from mag import frontier_steer
        for s in frontier_steer.preamble():
            out.append(("frontier", s))
    except Exception:
        pass
    # 2. operator directives (the autonomy contract)
    try:
        p = ROOT / "memory" / "operator_directives.md"
        if p.is_file():
            for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if line and not line.startswith(("#", "-", ">", " ")):
                    out.append(("operator", line[:200]))
    except Exception:
        pass
    # 3. domain RIBs (mounted via rib_bus)
    try:
        from mag import rib_bus
        m = rib_bus.mount(domain)
        for s in m.get("ribs", []):
            out.append((f"rib:{domain}", s))
    except Exception:
        pass
    # 4. grokbot seat directives (the controlled-seat best practice)
    try:
        from mag import grok_bot
        for d in grok_bot._DIRECTIVES:
            out.append(("grokbot", d))
    except Exception:
        pass
    return out


def compile_steer(domain: str = "general") -> dict[str, Any]:
    """Merge ALL steering sources into ONE canonical, deduped steer block. Deterministic + $0."""
    merged: dict[str, str] = {}
    order: list[str] = []
    for label, line in _sources(domain):
        line = (line or "").strip()
        if not line or line in merged:
            continue
        merged[line] = label
        order.append(line)
    return {"ok": True, "schema": SCHEMA, "domain": domain, "n_steer": len(order),
            "sources": sorted({merged[l] for l in order}),
            "steer": [f"[{merged[l]}] {l}" for l in order]}


def spec(*, task: str, domain: str = "general",
         acceptance: list[str] | None = None) -> dict[str, Any]:
    """The CONTROLLED-SEAT SPEC (Grok's best practice) applied to ANY task: the compiled steering
    + a hard acceptance contract + a report-back shape. One discipline for every seat/worker."""
    c = compile_steer(domain)
    acc = acceptance or ["The task's goal is met, verified by a real probe (not asserted)."]
    task_id = f"se-{datetime.now(timezone.utc).strftime('%H%M%S')}-{len(task) % 1000}"
    return {"ok": True, "schema": SCHEMA, "id": task_id, "task": task, "domain": domain,
            "steer": c["steer"], "acceptance": acc,
            "report": "return a concise result + the evidence path; never claim done unverified.",
            "contract": "STEER (compiled) -> TASK -> ACCEPTANCE -> REPORT"}


def inject_for(task: str, domain: str = "general",
               acceptance: list[str] | None = None) -> str:
    """The UNIFIED injection (improves frontier_steer.inject + rib_bus.inject_for): one canonical
    steer block + the acceptance contract, so every dispatched task carries the same discipline."""
    c = compile_steer(domain)
    head = "\n".join(f"- {s}" for s in c["steer"])
    acc = "\n".join(f"- {a}" for a in (acceptance or ["verify by a real probe before claiming done"]))
    return (f"STEER (steer_engine compiled: {c['n_steer']} from {', '.join(c['sources'])}):\n"
            f"{head}\n\nTASK: {task}\n\nACCEPTANCE:\n{acc}\n"
            "REPORT: return a concise result + evidence path; never claim done unverified.")


def fold(*, task: str = "", outcome: str = "unknown", domain: str = "general") -> dict[str, Any]:
    """Record what steering was injected + its outcome, so the LOOP learns (telemetry-fed, not
    static). Append-only; feeds behavioral_lensing / steer_telemetry."""
    row = {"schema": SCHEMA, "ts": _now(), "domain": domain, "task": (task or "")[:200],
           "outcome": (outcome or "")[:120], "n_steer": len(compile_steer(domain)["steer"])}
    try:
        TELEMETRY.parent.mkdir(parents=True, exist_ok=True)
        with TELEMETRY.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    except OSError:
        pass
    return {"ok": True, "schema": SCHEMA, "folded": row}


def status() -> dict[str, Any]:
    n = 0
    if TELEMETRY.is_file():
        n = sum(1 for _ in TELEMETRY.read_text(encoding="utf-8", errors="replace").splitlines() if _.strip())
    return {"ok": True, "schema": SCHEMA,
            "contract": "compile_steer(domain)->one canonical block from ALL sources; "
                        "spec/inject_for->controlled-seat discipline on any task; fold()->the loop "
                        "learns steering from outcomes",
            "cost": "deterministic + $0",
            "sources": ["frontier (mined invariants)", "operator_directives.md", "rib_bus RIBs",
                        "grokbot seat directives"],
            "telemetry_rows": n, "telemetry": str(TELEMETRY.relative_to(ROOT)).replace("\\", "/")}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="steer-engine")
    ap.add_argument("cmd", nargs="?", default="status", choices=["status", "compile", "spec", "inject"])
    ap.add_argument("--domain", default="general")
    ap.add_argument("--task", default="reflect on the republic")
    a = ap.parse_args()
    if a.cmd == "compile":
        print(json.dumps(compile_steer(a.domain), ensure_ascii=False, indent=2, default=str))
    elif a.cmd == "spec":
        print(json.dumps(spec(task=a.task, domain=a.domain), ensure_ascii=False, indent=2, default=str))
    elif a.cmd == "inject":
        print(inject_for(a.task, a.domain))
    else:
        print(json.dumps(status(), ensure_ascii=False, indent=2, default=str))
