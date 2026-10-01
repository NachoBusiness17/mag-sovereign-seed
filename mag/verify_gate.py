"""verify_gate — continuous verify gate (Prow-lite), lean.

The doctrine (Ben-The-Elder lane / KIND / Prow): don't trust the report, reproduce the
reality, every cycle. We already hold the core — `mag.test_runner` is a bounded, restful,
headless pytest runner with a structured report. This module is a THIN gate over it: run
the suite on the cadence, emit an honest typed verdict (green | red | timeout), surface
failures, fold to the learning loop.

DELIBERATE SCOPE CUT (2026-08-23, sacred-cow audit): no known-good "baseline" pinning, no
drift-math ceremony. That is Prow ceremony for many-contributor trees; we are a single
sovereign operator who sees red and fixes it. Load-bearing only: run + verdict + failures
+ fold. If we ever grow a real multi-contributor tree, the baseline can return.

Contract: schema `verify_gate.v1`. Verdict is typed and honest — never fabricate green.
"""
from __future__ import annotations

import ast
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCHEMA = "verify_gate.v1"

# RIGHTSIZED cadence default (2026-08-23, rib-debugged): the FULL suite exceeds 600s; the first
# "core" picks hung or cascaded into the LIVE architecture (test_law -> law.enforce(apply=True)
# -> ghost_cycle(dry=False) — a unit test that fires the production loop; test_routing_smoke /
# test_headless hit the network). The genuinely PURE fast core is these two: verkle state chain
# audit + the invariant lattice — 11 tests, ~80s, green. Network/live-loop tests belong on --full.
CORE_SMOKE = [
    "tests/test_verkle_audit.py",
    "tests/test_invariant.py",
]

# MEMOIZED GATE (operator 2026-08-23: "a sixty second test could be hashable... could we quant it?").
# Content-address the covered source; if the bytes haven't moved since the last green, reuse it.
# = the 'cache the expensive brain / coldest vertex' doctrine applied to tests: spend the big
# compute only when a covered module actually changes. HONESTY: cached green is LABELED cached,
# never mislabeled fresh, and re-runs the instant any covered mag/config module changes.
DIR = ROOT / "memory" / "runs" / "verify_gate"
CACHE = DIR / "CACHE.json"


def _load_cache() -> dict[str, Any]:
    if CACHE.is_file():
        try:
            return json.loads(CACHE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_cache(c: dict[str, Any]) -> None:
    DIR.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(c, indent=2, ensure_ascii=False), encoding="utf-8")


def _coverage_digest(test_path: Path) -> str:
    """sha256 over the test file + every mag/config module it transitively imports
    (plus pytest.ini/conftest). If these bytes are unchanged, the prior verdict is
    still valid. Bounded depth; hermetic-pure core only."""
    h = hashlib.sha256()
    seen: set[str] = set()

    def add(p: Path) -> None:
        if p.is_file():
            h.update(p.read_bytes())

    def scan(path: Path, depth: int = 0) -> None:
        if depth > 8 or str(path) in seen:
            return
        seen.add(str(path))
        add(path)
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            return
        for node in ast.walk(tree):
            mods: list[str] = []
            if isinstance(node, ast.ImportFrom) and node.module:
                mods.append(node.module)
            elif isinstance(node, ast.Import):
                mods += [a.name for a in node.names]
            for n in mods:
                parts = n.split(".")
                if parts[0] in ("mag", "config"):
                    cand = (ROOT / parts[0] / Path(*parts[1:]).with_suffix(".py")
                            if len(parts) > 1 else ROOT / parts[0] / "__init__.py")
                    if cand.is_file():
                        scan(cand, depth + 1)

    scan(test_path)
    for cfg in ("pytest.ini", "conftest.py"):
        p = ROOT / cfg
        if p.is_file():
            add(p)
    return h.hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _verdict(rep: dict[str, Any]) -> str:
    counts = rep.get("counts") or {}
    if rep.get("timed_out"):
        return "timeout"
    if rep.get("status") == "ok" and counts.get("failed", 0) == 0 \
            and counts.get("errors", 0) == 0:
        return "green"
    return "red"


def gate(*, timeout: int = 180, per_test: int | None = 60,
         paths: list[str] | None = None, full: bool = False,
         use_cache: bool = True) -> dict[str, Any]:
    """Run the gate and emit an honest verdict.

    Cadence default (pure core) is MEMOIZED: hash each test's covered source; reuse the
    prior green if unchanged, run only the changed files. Cost ~0 when nothing moved.
    full=True / explicit paths / use_cache=False always run fresh.
    """
    from mag import test_runner
    targets = list(paths) if paths is not None else (None if full else CORE_SMOKE)

    if full or paths is not None or not use_cache:
        rep = test_runner.run(paths=targets, timeout=timeout, per_test=per_test)
        out = {
            "schema": SCHEMA, "verdict": _verdict(rep), "ts": _now(),
            "mode": "full" if (full or paths is not None) else "fresh",
            "run_id": rep.get("id"), "status": rep.get("status"),
            "duration_s": rep.get("duration_s"), "timed_out": rep.get("timed_out"),
            "counts": rep.get("counts") or {}, "failures": rep.get("failures") or [],
            "paths": targets or ["<all>"],
            "note": "bounded headless suite; timeout->not green (steal: doneStateVerifier); no baseline ceremony",
        }
        _fold(out)
        return out

    # ---- MEMOIZED cadence path ----
    cache = _load_cache()
    results: dict[str, Any] = {}
    for tp in targets:
        digest = _coverage_digest(ROOT / tp)
        entry = cache.get(tp)
        if entry and entry.get("hash") == digest and entry.get("verdict") == "green":
            results[tp] = {"cached": True, "verdict": "green",
                           "counts": entry.get("counts", {}), "cached_ts": entry.get("ts")}
        else:
            rep = test_runner.run(paths=[tp], timeout=timeout, per_test=per_test)
            v = _verdict(rep)
            counts = rep.get("counts") or {}
            results[tp] = {"cached": False, "verdict": v, "counts": counts,
                           "run_id": rep.get("id"), "duration_s": rep.get("duration_s")}
            cache[tp] = {"hash": digest, "verdict": v, "counts": counts, "ts": _now()}
            _save_cache(cache)

    verdicts = [r["verdict"] for r in results.values()]
    cached = sum(1 for r in results.values() if r.get("cached"))
    if all(v == "green" for v in verdicts):
        verdict = "green"
    elif "red" in verdicts:
        verdict = "red"
    else:
        verdict = "timeout"
    failed = sum(1 for v in verdicts if v != "green")
    out = {
        "schema": SCHEMA, "verdict": verdict, "ts": _now(),
        "mode": "memoized", "cached": cached, "fresh": len(verdicts) - cached,
        "skipped_fresh_run": cached == len(verdicts), "failed": failed,
        "results": results,
        "note": "memoized gate: unchanged covered-source -> prior green reused (coldest-vertex); "
                 "changed -> re-run; cached is labeled cached, never mislabeled fresh",
    }
    _fold(out)
    return out


def status() -> dict[str, Any]:
    """Last gate verdict from the latest run (trusted surface, no terminal guessing)."""
    from mag import test_runner
    try:
        st = test_runner.status()
        if st.get("has_run") and st.get("latest"):
            rep = st["latest"]
            return {"schema": SCHEMA, "verdict": _verdict(rep), "ts": _now(),
                    "run_id": rep.get("id"), "counts": rep.get("counts") or {},
                    "failures": rep.get("failures") or []}
        return {"schema": SCHEMA, "verdict": "no_run", "ts": _now(),
                "note": "no test run recorded yet"}
    except Exception as e:
        return {"schema": SCHEMA, "verdict": "error", "ts": _now(), "error": str(e)[:200]}


def _fold(d: dict[str, Any]) -> None:
    try:
        from mag import training_events
        training_events.emit(
            "verify_gate",
            input_data={"run_id": d.get("run_id")},
            action={"kind": "verify_gate", "verdict": d.get("verdict")},
            outcome={"failed": (d.get("counts") or {}).get("failed", 0)},
            pattern_tags=["verify_gate", "prow_lite", "continuous_verify", "rib_debug"],
            tier_max="T1", exportable=False,
        )
    except Exception:
        pass


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv[0] if argv else "status"
    if cmd == "gate":
        out = gate(full=("--full" in argv), use_cache=("--no-cache" not in argv))
    else:
        out = status()
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
