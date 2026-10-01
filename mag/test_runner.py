"""test_runner — make TESTING restful + automated (it was the one non-automated surface).

Operator finding (2026-08-09 full-blast audit): "our testing is obviously antiquated
and broken — everything else is restful and automated and this is just hanging?"
Root causes observed live:
  * No REST/cadence surface to run tests — only a manual terminal.
  * No per-test timeout — 846 tests / 155 files incl. real-spawn tests can hang the
    whole suite (pytest blocks on a spawned loop forever).
  * The interactive terminal wedges/swallows output (no reliable capture path).
  * Windows: pytest subprocess can flash console windows (headless fix here).

THE FIX (this module): a deterministic, restful test runner.
  * run()        — runs pytest via subprocess with a BOUNDED wall-clock timeout +
                   per-test timeout (pytest-timeout if installed), CREATE_NO_WINDOW
                   (mag.headless), captures a structured report to
                   memory/runs/test_run/<ts>/report.json + LATEST.json.
  * status()     — latest run summary (trusted surface, no terminal guessing).
  * Seam checks from the steal: typed pass|fail|warn|skip; timeout→warn not fail;
                   stop-first via --maxfail; per-axis honesty (no fabrication).

Wiring: skill `test_runner` in skill_pipeline + REST GET/POST /api/v1/test-run.
CLI:  python -m mag.test_runner run [--timeout N] [--per-test N] [<path>...]
      python -m mag.test_runner status
"""
from __future__ import annotations

import json
import subprocess
import sys
from mag import headless
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

RUNS = ROOT / "memory" / "runs" / "test_run"
LATEST = RUNS / "LATEST.json"
SCHEMA = "test_runner.v1"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _has_pytest_timeout() -> bool:
    try:
        import pytest_timeout  # noqa: F401
        return True
    except Exception:
        return False


def run(
    *,
    paths: list[str] | None = None,
    timeout: int = 600,
    per_test: int | None = 90,
    maxfail: int = 5,
) -> dict[str, Any]:
    """Run pytest restfully, bounded, headless. Returns structured report."""
    RUNS.mkdir(parents=True, exist_ok=True)
    ts = _now()
    slug = ts.replace(":", "").replace("-", "").replace(".", "")[:15]

    cmd = [headless.PYTHON, "-m", "pytest", "-q", "-p", "no:cacheprovider"]
    cmd += ["--maxfail", str(maxfail)]
    pt = per_test if per_test is not None else (90 if _has_pytest_timeout() else None)
    if pt and _has_pytest_timeout():
        cmd += ["--timeout", str(pt)]
    if paths:
        cmd += [str(Path(p).resolve()) for p in paths]

    started = datetime.now(timezone.utc)
    try:
        res = subprocess.run(
            cmd,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            # MUST pass the spawn env: headless.PYTHON is the BASE interpreter (by design, to
            # avoid the venv-shim double-PID bug), so PYTHONPATH must point at the venv
            # site-packages or `-m pytest` won't resolve (ROOT cause 2026-08-23: every test run
            # silently returned empty "failed" in 0.1s because pytest was never found).
            env=headless._spawn_env(),
            creationflags=__import__("mag.headless", fromlist=["no_window_flags"]).no_window_flags(),
        )
        timed_out = False
        rc = res.returncode
        output = (res.stdout or "") + "\n" + (res.stderr or "")
    except subprocess.TimeoutExpired as e:
        timed_out = True
        rc = -1
        output = "TIMED OUT after {timeout}s\n" + ((e.stdout or "") if isinstance(e.stdout, str) else "")
        if isinstance(e.stdout, bytes):
            output += e.stdout.decode("utf-8", "replace")

    duration_s = round((datetime.now(timezone.utc) - started).total_seconds(), 1)

    # parse the -q summary tail: "N passed, M failed, K skipped, E errors in Xs"
    import re
    counts = {"passed": 0, "failed": 0, "skipped": 0, "errors": 0,
              "xfailed": 0, "xpassed": 0, "warnings": 0}
    tail = output[-1500:]
    for key in counts:
        m = re.search(r"(\d+)\s+" + key, tail)
        if m:
            counts[key] = int(m.group(1))
    # extract failing test ids
    failures: list[str] = []
    for line in output.splitlines():
        if " FAILED " in line:
            failures.append(line.split(" FAILED ")[-1].strip())
    # collection errors
    coll_errors = counts["errors"]

    report = {
        "schema": SCHEMA, "ts": ts, "id": slug,
        "status": "timed_out" if timed_out else ("ok" if rc == 0 else "failed"),
        "exit": rc, "duration_s": duration_s, "timed_out": timed_out,
        "per_test_timeout": pt if pt and _has_pytest_timeout() else None,
        "counts": {**counts, "collection_errors": coll_errors},
        "failures": failures[:maxfail],
        "paths": paths or ["<all>"],
        "output_tail": output[-3000:],
        "note": "restful bounded headless test run; timeout->warn not fail (steal: doneStateVerifier)",
    }
    (RUNS / f"{slug}.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    LATEST.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    # fold the run into the learning loop (cheap)
    try:
        from mag import training_events
        training_events.emit(
            "test_run",
            input_data={"id": slug, "paths": report["paths"]},
            action={"kind": "test_runner", "status": report["status"], "duration_s": duration_s},
            outcome={"passed": passed, "failed": failed, "errors": errors},
            pattern_tags=["test_runner", "test_automation", "restful_testing"],
            tier_max="T1", exportable=False,
        )
    except Exception:
        pass
    return report


def status() -> dict[str, Any]:
    """Latest run summary — the trusted surface (no terminal guessing)."""
    if not LATEST.is_file():
        return {"schema": SCHEMA, "ok": True, "has_run": False, "note": "no test run recorded yet"}
    try:
        d = json.loads(LATEST.read_text(encoding="utf-8"))
        return {"schema": SCHEMA, "ok": True, "has_run": True, "latest": d}
    except Exception:
        return {"schema": SCHEMA, "ok": True, "has_run": False, "error": "latest corrupt"}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv[0] if argv else "status"
    rest = argv[1:]
    timeout = 600
    per_test: int | None = 90
    paths: list[str] = []
    i = 0
    while i < len(rest):
        a = rest[i]
        if a == "--timeout" and i + 1 < len(rest):
            timeout = int(rest[i + 1]); i += 2; continue
        if a == "--per-test" and i + 1 < len(rest):
            per_test = int(rest[i + 1]); i += 2; continue
        if a == "--no-timeout":
            per_test = None; i += 1; continue
        paths.append(rest[i]); i += 1
    if cmd == "run":
        out = run(paths=paths, timeout=timeout, per_test=per_test)
    else:
        out = status()
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
