"""Production-shell tripwire for test-isolation log redirects (B2-358, 2026-09-26).

Two seams let one environment variable move a production log while every
writer keeps reporting ok:

- MAG_SEAT_CRASH_LOG moves the seat-crash sink (mag.agent_cli._log_seat_crash);
  production default ROOT/logs/seat_crashes.log. Seam landed by B2-86 so tests
  could stop appending INJECTED- traceback blocks to the production log.
- MAG_GAPS_LOG moves the loop-gap log (mag.temperature_stack._gaps_log);
  production default memory/training/loop_gaps.jsonl. Seam landed by B2-79 for
  the same reason on the gap writer.

The disease (B2-358): the export that isolated a test run leaks into a plain
production shell (PowerShell $env: line, bash export, CI residue) and silently
redirects the production crash or gap record. Falsifier being repaired:
MAG_SEAT_CRASH_LOG set in a plain shell, one real seat crash, and no surface
naming where the trace went. This module is the named surface: doctor
(mag.doctor.check_env_sanity) and shared-surface validate
(python -m mag.shared_surface validate) both call env_redirect_warnings() and
warn with the redirect target whenever either variable is set outside a test
run. Spec receipt: watch/inbox/burn_wave_20260926/B2_358_env_tripwire_20260926.md.

Operator response when the ENV-REDIRECT warning fires:
1. Find the leak: inspect the shell that ran the command
   (PowerShell: $env:MAG_SEAT_CRASH_LOG / $env:MAG_GAPS_LOG;
   bash: echo "$MAG_SEAT_CRASH_LOG") and the profile files that feed it;
   remove the export line at the source.
2. Clear the current shell: Remove-Item Env:MAG_SEAT_CRASH_LOG or
   unset MAG_SEAT_CRASH_LOG (same shape for MAG_GAPS_LOG).
3. Triage the named target file: real crash or gap rows written while the
   variable was set are folded back into the production log by append (never
   erase); pure test debris (INJECTED- blocks, unit-test gap rows) may be
   archived or deleted.
4. Re-run the surface (mag.cmd doctor surfaces it via check_env_sanity, or
   .venv/Scripts/python.exe -m mag.shared_surface validate) and confirm the
   warning is gone, production paths restored.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Mapping

# The two test-isolation seams (B2-86 crash sink, B2-79 gap log) and what each
# moves when set. One table so the next seam lands here, not in a third check.
REDIRECT_VARS: dict[str, str] = {
    "MAG_SEAT_CRASH_LOG": (
        "seat crash tracebacks (writer mag.agent_cli._log_seat_crash; "
        "production default logs/seat_crashes.log)"
    ),
    "MAG_GAPS_LOG": (
        "loop gap rows (writer mag.temperature_stack._gaps_log; production "
        "default memory/training/loop_gaps.jsonl)"
    ),
}

OPERATOR_RESPONSE = (
    "remove the export at its source (shell profile or session), unset it in "
    "the current shell, triage the named target (fold real crash/gap rows "
    "back into the production log by append, never erase; archive or delete "
    "pure test debris), then re-run this surface and confirm the warning is gone"
)


def env_redirect_status(env: Mapping[str, str] | None = None) -> list[dict[str, Any]]:
    """One record per SET redirect variable, test run or not.

    Each record names the variable, the redirect target, whether that target
    file already exists, what the variable moves, whether the invoking process
    looks like a pytest run (PYTEST_CURRENT_TEST set; informational context
    for the reader, not a suppression key), and the operator response. Empty
    list means the production paths are live.
    """
    env_map = os.environ if env is None else env
    records: list[dict[str, Any]] = []
    for name, moves in REDIRECT_VARS.items():
        value = (env_map.get(name) or "").strip()
        if not value:
            continue
        try:
            target_exists: bool | None = Path(value).exists()
        except OSError:
            target_exists = None
        records.append({
            "var": name,
            "target": value,
            "target_exists": target_exists,
            "moves": moves,
            "in_test_run": bool((env_map.get("PYTEST_CURRENT_TEST") or "").strip()),
            "operator_response": OPERATOR_RESPONSE,
        })
    return records


def env_redirect_warnings(env: Mapping[str, str] | None = None) -> list[str]:
    """Warning lines for every SET redirect variable (B2-358).

    Every line names the variable and the redirect target, so a leaked export
    can never send a crash or a gap somewhere no surface names. The warning
    fires unconditionally on a set variable: these surfaces are operator
    commands, not test steps, so a variable set at invocation time is a leak
    to name even if the invoking process happens to be a test runner (the
    PYTEST_CURRENT_TEST marker flips per phase and cannot serve as the
    suppression key; a spurious warning costs nothing, a silent redirect
    costs the estate its crash and gap record).
    """
    env_map = os.environ if env is None else env
    return [
        (
            f"ENV-REDIRECT: {rec['var']} is set outside a test run; "
            f"{rec['moves']} now go to {rec['target']}. "
            f"Operator response: {OPERATOR_RESPONSE}"
        )
        for rec in env_redirect_status(env_map)
    ]
