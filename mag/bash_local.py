"""bash_local — W0 of the trajectory spine: the bash-local envelope wrapper.

Every shell command wrapped through this emits ONE TrajectoryStep row (Schema v1)
to memory/runs/trajectory/steps.jsonl. The tape is an UNTRUSTED SIDECAR — the
command is the contract: envelope failures never change the command's exit code.
Rows are hash-chained per session (prev_step_hash), pattern stolen from
mag/grounding_wave.py. step_hash is the primary key: sha256 over the canonical
row content EXCLUDING step_hash, first 16 hex chars.

Card: watch/TRAJECTORY_LENS_20260905.md (build #1). Falsifier: any shell
command runs without producing an envelope row = coverage test fails.

CLI:
  python -m mag.bash_local "<command>" [--why="declared intent"] [args...]
  python -m mag.bash_local verify [--tape PATH]    # per-row validity + chain
  python -m mag.bash_local help

Env: WORLDLINE_SESSION (session_id; else generated per process),
     WORLDLINE_REASONING (optional reasoning note, default ""),
     WORLDLINE_WHY (optional declared intent; an explicit --why= flag wins).

SCHEMA v2 (B-CHAIN-1, 2026-09-07 — optional declared intent):
  A row that CARRIES a `why` field is schema_version 2; rows without stay v1.
  v2 = v1 + optional `why` string, head-capped at WHY_CAP (1024) chars.
  Hash rule: the canonical row content pre-hash gains ONE extra key `why`
  (same json.dumps(sort_keys=True) canonicalization), so for v2 rows
  step_hash = sha256(canonical(v1 fields + why))[16]; v1 rows hash exactly as
  before (v1 canonical content is unchanged, byte-identical hashes). The
  verifier accepts BOTH versions; a v1 row carrying `why` is REJECTED (its
  hash would not cover the why, so tampering would go unseen).
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
TAPE = ROOT / "memory" / "runs" / "trajectory" / "steps.jsonl"
SCHEMA_VERSION = 1
SCHEMA_VERSION_V2 = 2   # v1 + optional `why` (declared intent)
GENESIS = "0" * 16
OUTPUT_CAP = 4096   # stdout tail, chars
TOOL_CAP = 2048     # stderr tail, chars (tool_result)
WHY_CAP = 1024      # declared-intent head, chars (schema v2)
REQUIRED_FIELDS = ("schema_version", "ts", "session_id", "input", "output",
                   "tool_result", "reasoning", "timing", "prev_step_hash",
                   "step_hash")
REQUIRED_FIELDS_V2 = REQUIRED_FIELDS + ("why",)
HASH_FIELDS = tuple(f for f in REQUIRED_FIELDS if f != "step_hash")
HASH_FIELDS_V2 = tuple(f for f in REQUIRED_FIELDS_V2 if f != "step_hash")


def _hash_fields(schema_version: int) -> tuple[str, ...]:
    return HASH_FIELDS_V2 if schema_version == SCHEMA_VERSION_V2 else HASH_FIELDS


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _canonical_core(row: dict[str, Any]) -> str:
    fields = _hash_fields(row.get("schema_version", SCHEMA_VERSION))
    return json.dumps({k: row.get(k) for k in fields},
                      sort_keys=True, ensure_ascii=False)


def _row_hash(row: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_core(row).encode("utf-8")).hexdigest()[:16]


def _tail(text: str, cap: int) -> str:
    return text[-cap:] if len(text) > cap else text


def _head(text: str, cap: int) -> str:
    return text[:cap] if len(text) > cap else text


def build_row(*, session_id: str, input_cmd: str, output: str,
              tool_result: dict[str, Any], reasoning: str,
              timing: dict[str, Any], prev_step_hash: str,
              schema_version: int | None = SCHEMA_VERSION,
              ts: str | None = None,
              why: str | None = None) -> dict[str, Any]:
    """SCHEMA GATE: refuses any row without schema_version (card: mandatory).

    Passing a non-None `why` upgrades the row to schema v2 (declared intent,
    head-capped to WHY_CAP); rows without why stay v1.
    """
    if schema_version is None:
        raise ValueError("schema gate: row rejected — schema_version is mandatory")
    if why is not None:
        schema_version = SCHEMA_VERSION_V2
    row: dict[str, Any] = {
        "schema_version": schema_version,
        "ts": ts or _now(),
        "session_id": session_id,
        "input": input_cmd,
        "output": _tail(output, OUTPUT_CAP),
        "tool_result": tool_result,
        "reasoning": reasoning,
        "timing": timing,
        "prev_step_hash": prev_step_hash,
    }
    if why is not None:
        row["why"] = _head(why, WHY_CAP)
    row["step_hash"] = _row_hash(row)
    return row


def _last_hash_for_session(rows: list[dict[str, Any]], session_id: str) -> str:
    for row in reversed(rows):
        if row.get("session_id") == session_id:
            return row.get("step_hash", GENESIS)
    return GENESIS


def _rows(tape: Path = TAPE) -> list[dict[str, Any]]:
    if not tape.is_file():
        return []
    out = []
    for ln in tape.read_text(encoding="utf-8", errors="replace").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            out.append(json.loads(ln))
        except json.JSONDecodeError:
            out.append({"_unparseable": True, "_line": ln[:200]})
    return out


def append_row(row: dict[str, Any], tape: Path = TAPE) -> None:
    """Atomic-ish single-line append; the tape is a sidecar, never the contract."""
    if not isinstance(row.get("schema_version"), int):
        raise ValueError("schema gate: append rejected — schema_version missing")
    tape.parent.mkdir(parents=True, exist_ok=True)
    with tape.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())


def verify(tape: Path = TAPE) -> tuple[bool, str]:
    rows = _rows(tape)
    prev_by_session: dict[str, str] = {}
    bad: list[str] = []
    for i, row in enumerate(rows, 1):
        where = f"row {i}"
        if row.get("_unparseable"):
            bad.append(f"{where}: unparseable line")
            continue
        # schema gate (v1 and v2 both lawful; anything else refuses)
        if "schema_version" not in row:
            bad.append(f"{where}: REJECTED — no schema_version")
            continue
        if not isinstance(row["schema_version"], int):
            bad.append(f"{where}: REJECTED — schema_version not an int")
            continue
        if row["schema_version"] not in (SCHEMA_VERSION, SCHEMA_VERSION_V2):
            bad.append(f"{where}: REJECTED — unknown schema_version "
                       f"{row['schema_version']!r}")
            continue
        required = (REQUIRED_FIELDS_V2 if row["schema_version"] == SCHEMA_VERSION_V2
                    else REQUIRED_FIELDS)
        missing = [f for f in required if f not in row]
        if missing:
            bad.append(f"{where}: missing fields {','.join(missing)}")
            continue
        if row["schema_version"] == SCHEMA_VERSION and "why" in row:
            bad.append(f"{where}: REJECTED — v1 row carries `why` "
                       f"(upgrade to schema v2; v1 hash would not cover it)")
            continue
        if row["schema_version"] == SCHEMA_VERSION_V2:
            why = row["why"]
            if not isinstance(why, str):
                bad.append(f"{where}: REJECTED — v2 why not a string")
                continue
            if len(why) > WHY_CAP:
                bad.append(f"{where}: REJECTED — v2 why {len(why)} chars "
                           f"> cap {WHY_CAP}")
                continue
        if _row_hash(row) != row.get("step_hash"):
            bad.append(f"{where}: hash mismatch (row edited in place)")
            continue
        sid = row["session_id"]
        expect = prev_by_session.get(sid, GENESIS)
        if row.get("prev_step_hash") != expect:
            bad.append(f"{where}: prev_step_hash mismatch in session {sid} "
                       f"(chain broken)")
            continue
        prev_by_session[sid] = row["step_hash"]
    sessions = len({r.get("session_id") for r in rows
                    if isinstance(r, dict) and r.get("session_id")})
    tip = next((r["step_hash"] for r in reversed(rows)
                if isinstance(r, dict) and "step_hash" in r), GENESIS)
    msg = (f"{len(rows)} rows, {sessions} session(s), tip={tip} on {tape.name}")
    if bad:
        return False, msg + " | " + "; ".join(bad[:8])
    return True, msg + " | all rows valid, chains intact"


def _run(command: str, why: str | None = None) -> int:
    """Wrap one command; envelope failure never changes the exit code."""
    bash = shutil.which("bash")
    argv = [bash, "-c", command] if bash else None
    t0 = time.perf_counter()
    start = _now()
    try:
        if argv:
            proc = subprocess.run(argv, capture_output=True, text=True,
                                  errors="replace")
        else:  # no bash on PATH — degrade honestly, still wrap
            proc = subprocess.run(command, shell=True, capture_output=True,
                                  text=True, errors="replace")
        out, err, code = proc.stdout or "", proc.stderr or "", proc.returncode
    except KeyboardInterrupt:
        raise
    except Exception as exc:  # noqa: BLE001 — spawn failure is a real result
        out, err, code = "", f"spawn failed: {exc}", 127
    duration = round(time.perf_counter() - t0, 6)
    end = _now()

    real_code = code
    try:
        sid = os.environ.get("WORLDLINE_SESSION") or f"bl-{uuid.uuid4().hex[:8]}"
        rows = _rows()
        row = build_row(
            session_id=sid,
            input_cmd=command,
            output=out,
            tool_result={"stderr_tail": _tail(err, TOOL_CAP), "exit_code": code},
            reasoning=os.environ.get("WORLDLINE_REASONING", ""),
            timing={"start": start, "end": end, "duration_s": duration},
            prev_step_hash=_last_hash_for_session(rows, sid),
            why=why,
        )
        append_row(row)
        ver = f"v{row['schema_version']}"
        print(f"[bash-local] step {row['step_hash']} <- prev "
              f"{row['prev_step_hash']} (session {sid}, {ver})"
              + (" [why sealed]" if why is not None else ""), file=sys.stderr)
    except Exception as exc:  # noqa: BLE001 — sidecar never breaks the contract
        print(f"[bash-local] WARN envelope write failed ({exc}); "
              f"command result unaffected", file=sys.stderr)
    return real_code


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    argv = sys.argv[1:]
    if not argv or argv[0] in ("help", "-h", "--help"):
        print(__doc__.strip())
        sys.exit(0 if argv else 2)
    if argv[0] == "verify":
        tape = TAPE
        if "--tape" in argv:
            i = argv.index("--tape")
            tape = Path(argv[i + 1])
        ok, msg = verify(tape)
        print(("PASS " if ok else "FAIL ") + msg)
        sys.exit(0 if ok else 1)
    # declared-intent extraction: --why=FLAG wins over WORLDLINE_WHY env;
    # the flag is peeled off before the rest joins into the command.
    why = os.environ.get("WORLDLINE_WHY") or None
    cmd_argv = []
    for a in argv:
        if a.startswith("--why="):
            why = a[len("--why="):] or None
        else:
            cmd_argv.append(a)
    code = _run(" ".join(cmd_argv), why=why)
    sys.exit(code)


if __name__ == "__main__":
    main()
