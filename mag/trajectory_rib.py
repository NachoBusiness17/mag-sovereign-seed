"""Compile bounded trajectory spans into a portable, derived RIB.

This is the v0 compiler pass from ``TRAJECTORY_RIB_COMPILER_SPEC.md``.  It is
deliberately deterministic and conservative: legacy/unbounded tape rows are
inventory, not accepted training material.  The source tape is never edited.

The output is a projection under ``memory/runs/trajectory_rib``.  It points
back to the existing person -> session -> run -> trail topology; it does not
create a second memory chain or advance a Verkle tip.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mag.read_archive import _body_hash

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "trajectory_rib.v1"
SPAN_SCHEMA = "trajectory_span.v1"
SECRET_PATTERNS = (
    re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]{16,}"),
    re.compile(r"(?i)((?:api[_-]?key|token|secret|password)\s*[:=]\s*)[^\s,;]+"),
    re.compile(r"\b(?:sk|ghp|gho|hf|gsk)_[A-Za-z0-9_-]{12,}\b"),
)
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+|\n+")


def _resolve_tape(raw: str | Path) -> Path:
    path = Path(raw)
    return path if path.is_absolute() else ROOT / path


def _redact(value: Any) -> Any:
    if isinstance(value, str):
        out = value
        for pattern in SECRET_PATTERNS:
            out = pattern.sub(lambda m: (m.group(1) if m.lastindex else "") + "[REDACTED]", out)
        return out
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, dict):
        return {str(k): _redact(v) for k, v in value.items()}
    return value


def _valid_bounds(row: dict[str, Any], line_no: int, start_byte: int, end_byte: int) -> bool:
    meta = row.get("metadata")
    if not isinstance(meta, dict) or meta.get("schema") != SPAN_SCHEMA:
        return False
    return (
        meta.get("lineRange") == [line_no, line_no]
        and isinstance(meta.get("byteRange"), list)
        and len(meta["byteRange"]) == 2
        and meta["byteRange"] == [start_byte, end_byte]
        and isinstance(meta.get("bodySha256"), str)
        and len(meta["bodySha256"]) == 64
        and meta["bodySha256"] == _body_hash(row)
    )


def _anchors(row: dict[str, Any]) -> list[str]:
    """Cheap, explainable anchor pass; semantic/counterfactual scoring is later."""
    text = str(row.get("text") or row.get("summary") or "")
    pieces = [p.strip() for p in SENTENCE_RE.split(text) if p.strip()]
    anchors: list[str] = []
    for piece in pieces:
        if len(piece) < 8:
            continue
        normalized = re.sub(r"\s+", " ", piece)[:240]
        if normalized not in anchors:
            anchors.append(normalized)
        if len(anchors) == 8:
            break
    return anchors


def _canonical(row: dict[str, Any], *, line_no: int, tape: Path, bounded: bool) -> dict[str, Any]:
    meta = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    acceptance = row.get("acceptance_commands", row.get("acceptance", []))
    if not isinstance(acceptance, list):
        acceptance = []
    status = str(row.get("status") or "observed")
    if not acceptance and status in {"verified", "passed", "complete"}:
        status = "staged"
    return {
        "schema": SCHEMA,
        "kind": "trajectory_span",
        "spanId": str(meta.get("spanId") or f"legacy-{line_no}"),
        "source": {
            "path": str(tape.relative_to(ROOT)).replace("\\", "/") if tape.is_relative_to(ROOT) else str(tape),
            "line": line_no,
            "lineRange": meta.get("lineRange") if bounded else [line_no, line_no],
            "byteRange": meta.get("byteRange") if bounded else None,
            "bodySha256": meta.get("bodySha256") if bounded else None,
            "bounded": bounded,
        },
        "session": str(row.get("session") or row.get("thread") or ""),
        "run": str(row.get("run_id") or row.get("run") or ""),
        "event": str(row.get("event") or row.get("type") or ""),
        "status": status,
        "actor": str(row.get("seat") or row.get("actor_id") or "claw"),
        "pathsTouched": list(meta.get("pathsTouched") or row.get("pathsTouched") or []),
        "tokenCount": int(meta.get("tokenCount") or row.get("tokensAfter") or 0),
        "anchors": _redact(_anchors(row)),
        "acceptance": {"commands": _redact(acceptance), "status": "present" if acceptance else "unproven"},
        "text": _redact(str(row.get("text") or row.get("summary") or ""))[:2000],
    }


def compile_tape(
    tape: str | Path = "watch/openclaw_traj.jsonl",
    output: str | Path = "memory/runs/trajectory_rib/compiled.jsonl",
    *,
    include_legacy: bool = False,
) -> dict[str, Any]:
    """Compile only byte- and line-verified spans; write a derived report."""
    source = _resolve_tape(tape)
    destination = Path(output)
    if not destination.is_absolute():
        destination = ROOT / destination
    raw = source.read_bytes() if source.is_file() else b""
    lines = raw.splitlines(keepends=True)
    compiled: list[dict[str, Any]] = []
    rejected_unbounded = 0
    rejected_malformed = 0
    offset = 0
    for line_no, physical in enumerate(lines, start=1):
        end = offset + len(physical)
        try:
            row = json.loads(physical.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            rejected_malformed += 1
            offset = end
            continue
        if not isinstance(row, dict):
            rejected_malformed += 1
            offset = end
            continue
        bounded = _valid_bounds(row, line_no, offset, end)
        if not bounded and not include_legacy:
            rejected_unbounded += 1
            offset = end
            continue
        compiled.append(_canonical(row, line_no=line_no, tape=source, bounded=bounded))
        offset = end

    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = "".join(json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n" for item in compiled)
    temp = destination.with_suffix(destination.suffix + ".tmp")
    temp.write_text(payload, encoding="utf-8")
    temp.replace(destination)
    report = {
        "ok": True,
        "schema": SCHEMA,
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source": str(source),
        "sourceSha256": "sha256:" + hashlib.sha256(raw).hexdigest(),
        "sourceLines": len(lines),
        "compiled": len(compiled),
        "rejected_unbounded": rejected_unbounded,
        "rejected_malformed": rejected_malformed,
        "includeLegacy": include_legacy,
        "metricGate": "not_run",
        "verification": "staged; acceptance commands required",
        "output": str(destination),
    }
    report_path = destination.with_suffix(destination.suffix + ".meta.json")
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    report["report"] = str(report_path)
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="trajectory-rib")
    ap.add_argument("--tape", default="watch/openclaw_traj.jsonl")
    ap.add_argument("--output", default="memory/runs/trajectory_rib/compiled.jsonl")
    ap.add_argument("--include-legacy", action="store_true", help="inventory legacy rows as explicitly unbounded")
    args = ap.parse_args(argv)
    print(json.dumps(compile_tape(args.tape, args.output, include_legacy=args.include_legacy), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
