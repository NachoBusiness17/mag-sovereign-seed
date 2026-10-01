"""flex_test — autonomous flex: exercise every Mag system deterministically and fold.

"use that stretch to create a test of all your other systems as an autonomous flex"
(operator, 2026-08-10). Stateless agents don't need a sprint board; they flex every
system, fold the outcome, and route the next move through ghost/queue.

Runs each registered system check via importlib (defensive: a missing fn is WARN,
an exception is FAIL, a clean call is PASS). Writes memory/runs/flex/<ts>/FLEX_REPORT.md
and folds a training_events row + skill_ledger decision (source=flex).

Schema: flex_test.v1.  CLI: python -m mag.flex_test
"""
from __future__ import annotations
import importlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent

SCHEMA = "flex_test.v1"
FLEX_DIR = ROOT / "memory" / "runs" / "flex"

# (name, module, fn, args) — defensive; missing fn -> WARN, exception -> FAIL
# ACTIVE (stateless) core only. The mycelium/republic_os/comms_trail/scrum machinery
# is RETIRED (operator 2026-08-10: "these are all redundant and retired systems") — do
# NOT flex-test or maintain it as live. The live system = ghost + queue/drainer +
# RIB/direction + verkle + research_lens + rightsize + orphan_timer + ledger/flex.
CHECKS: list[tuple[str, str, str, tuple]] = [
    ("doctor.tracking", "mag.doctor", "check_system_tracking", ()),
    ("swarm_health", "mag.swarm_health", "swarm_health", ()),
    ("ghost.sense_surfaces", "mag.ghost", "sense_surfaces", ()),
    ("memlang.status", "mag.memlang", "status", ()),
    ("memlang.roundtrip", "mag.memlang", "roundtrip", ("flex-probe",)),
    ("verkle.prove_latest", "mag.verkle_knot", "prove_latest", ()),
    ("research_lens.status", "mag.research_lens", "status", ()),
    ("rightsize_all.audit", "mag.rightsize_all", "audit", ()),
    ("orphan_timer.list_open", "mag.orphan_timer", "list_open", ()),
    ("skill_ledger.progress", "mag.skill_ledger", "progress", ()),
    ("gap_analysis", "mag.gap_analysis", "gap_analysis", ()),
    ("cost_learn.analyze", "mag.cost_learn", "analyze", ()),
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for name, mod, fn, args in CHECKS:
        try:
            m = importlib.import_module(mod)
            f = getattr(m, fn)
        except Exception as e:  # module or fn missing
            rows.append({"check": name, "status": "WARN", "detail": f"missing: {e}"[:160]})
            continue
        t0 = time.time()
        try:
            res = f(*args)
            ms = round((time.time() - t0) * 1000)
            # a returned dict with an explicit ok/error flag informs WARN/FAIL
            if isinstance(res, dict) and res.get("ok") is False:
                if "overall" in res:  # live status (up/degraded/down), not a crash
                    status = "FAIL" if res.get("overall") == "down" else "WARN"
                    rows.append({"check": name, "status": status, "ms": ms,
                                 "detail": f"overall={res.get('overall')} "
                                           f"agents_up={res.get('agents_up')}/{res.get('agents_total')}"})
                    continue
                rows.append({"check": name, "status": "FAIL", "ms": ms,
                             "detail": str(res.get("error") or res.get("reason") or "")[:160]})
                continue
            rows.append({"check": name, "status": "PASS", "ms": ms,
                         "detail": (str(res)[:120] if not isinstance(res, (list, dict)) else
                                    (f"{len(res)} keys" if isinstance(res, dict) else f"{len(res)} items"))})
        except Exception as e:
            ms = round((time.time() - t0) * 1000)
            rows.append({"check": name, "status": "FAIL", "ms": ms, "detail": str(e)[:200]})

    passed = sum(1 for r in rows if r["status"] == "PASS")
    warn = sum(1 for r in rows if r["status"] == "WARN")
    failed = sum(1 for r in rows if r["status"] == "FAIL")
    report = {
        "schema": SCHEMA, "ts": _now(), "total": len(rows),
        "passed": passed, "warn": warn, "failed": failed,
        "rows": rows,
    }

    # ---- persist report (files-as-truth) ----
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = FLEX_DIR / stamp
    run_dir.mkdir(parents=True, exist_ok=True)
    md = [f"# FLEX TEST — autonomous system flex ({stamp})",
          f"\n**schema:** `{SCHEMA}` · **result:** {passed}/{len(rows)} passed"
          f" · warn {warn} · fail {failed}",
          "\n| check | status | ms | detail |",
          "|---|---|---|---|"]
    for r in rows:
        md.append(f"| {r['check']} | {r['status']} | {r.get('ms','-')} | {r.get('detail','')[:80]} |")
    (run_dir / "FLEX_REPORT.md").write_text("\n".join(md), encoding="utf-8")
    (run_dir / "flex.json").write_text(json.dumps(report, ensure_ascii=False, default=str, indent=2), encoding="utf-8")
    report["report_md"] = str(run_dir / "FLEX_REPORT.md")
    report["report_json"] = str(run_dir / "flex.json")

    # ---- fold through ghost's learning path ----
    try:
        from mag.training_events import emit
        emit("flex_test", action={"passed": passed, "total": len(rows), "failed": failed},
             outcome={"report": str(run_dir / "flex.json")}, pattern_tags=["flex", "autonomous"])
    except Exception:
        pass
    try:
        from mag.skill_ledger import record_decision
        record_decision(goal=f"flex:autonomous:{passed}/{len(rows)}",
                        task_shape="ops", provider="local", model="flex",
                        outcome="ok" if failed == 0 else "fail",
                        detail=f"system flex {passed}/{len(rows)} pass, {failed} fail",
                        source="flex")
    except Exception:
        pass
    return report


def main(argv: list[str] | None = None) -> int:
    r = run()
    print(json.dumps({k: r.get(k) for k in ("ts", "total", "passed", "warn", "failed", "report_md")}, default=str, indent=2))
    for row in r.get("rows", []):
        print(f"  [{row['status']}] {row['check']} {row.get('ms','')}ms :: {row.get('detail','')[:60]}")
    return 0 if r.get("failed") == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
