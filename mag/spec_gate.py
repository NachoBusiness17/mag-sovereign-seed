"""Spec gate — the "wrong offset" guard (DFHack-inspired).

DFHack never writes to a memory offset without validating it against the game
version. Same law here: before a seat applies a frozen spec to a file, verify
the file still matches the frozen BASE fingerprint (sha256). If it drifted,
REFUSE to apply blind — re-freeze or escalate. Trust bytes, not reports.

Usage:
  python main.py spec-gate freeze <path> [--label x]   # snapshot the base
  python main.py spec-gate check  <path>                # does it still match?
  python main.py spec-gate gate   <path>                # block if drifted
  python main.py spec-gate verify-after <path> [--sha X] [--label L]  # POSTCONDITION: did the apply take effect?
  python main.py spec-gate list                         # frozen bases
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT

GATE_STATE = ROOT / "memory" / "working" / "spec_gate.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def fingerprint(path: str | Path) -> str | None:
    """sha256 of the file's current bytes, or None if missing/unreadable."""
    p = Path(path)
    try:
        return hashlib.sha256(p.read_bytes()).hexdigest()
    except OSError:
        return None


def _load() -> dict[str, Any]:
    if not GATE_STATE.is_file():
        return {"schema": "spec_gate.v1", "bases": {}}
    try:
        data = json.loads(GATE_STATE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {"schema": "spec_gate.v1", "bases": {}}
    except Exception:
        return {"schema": "spec_gate.v1", "bases": {}}


def _save(data: dict[str, Any]) -> None:
    GATE_STATE.parent.mkdir(parents=True, exist_ok=True)
    GATE_STATE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _norm(path: str | Path) -> str:
    return str(Path(path).resolve())


def freeze(path: str | Path, *, label: str = "") -> dict[str, Any]:
    """Snapshot the current file state as the frozen base for a spec."""
    key = _norm(path)
    sha = fingerprint(path)
    data = _load()
    rec = {
        "path": key,
        "sha": sha,
        "label": label,
        "ts": _now(),
    }
    data.setdefault("bases", {})[key] = rec
    _save(data)
    return {**rec, "ok": sha is not None}


def base_for(path: str | Path) -> dict[str, Any] | None:
    return (_load().get("bases") or {}).get(_norm(path))


def check(path: str | Path, *, expected_sha: str | None = None) -> dict[str, Any]:
    """Does the file still match the frozen base? (bytes = ground truth)."""
    key = _norm(path)
    rec = base_for(path) or {}
    expected = expected_sha or rec.get("sha")
    current = fingerprint(path)
    return {
        "ok": expected is not None and current is not None and expected == current,
        "path": key,
        "expected_sha": expected,
        "current_sha": current,
        "base_ts": rec.get("ts"),
        "base_label": rec.get("label", ""),
        "missing": current is None,
    }


def gate(path: str | Path) -> dict[str, Any]:
    """The wrong-offset refusal: BLOCK apply if the world drifted from the base."""
    c = check(path)
    if c["ok"]:
        return {"ok": True, "blocked": False, "detail": "world matches frozen base — safe to apply", **c}
    if c["expected_sha"] is None:
        return {"ok": False, "blocked": True, "detail": "no frozen base for this file — freeze it first", **c}
    return {
        "ok": False,
        "blocked": True,
        "detail": "DRIFT: file changed since base was frozen — re-freeze or escalate (do not apply blind)",
        **c,
    }


def verify_after(path: str | Path, *, expected_sha: str | None = None, label: str = "") -> dict[str, Any]:
    """POSTCONDITION verify: did the apply actually take effect?

    gate() only guards the BEFORE (file hasn't drifted from the frozen base).
    This closes the honesty gap on the AFTER: fingerprint the file's current
    bytes and report whether the apply produced the expected result.

    - If expected_sha is given: ok iff current == expected_sha (result oracle).
    - If no expected_sha: ok iff current CHANGED from the frozen base (the
      apply actually mutated the file).
    """
    key = _norm(path)
    rec = base_for(path) or {}
    base_sha = rec.get("sha")
    current = fingerprint(path)
    changed = (
        current is not None
        and base_sha is not None
        and current != base_sha
    )
    if expected_sha is not None:
        ok = current is not None and current == expected_sha
        detail = (
            "result matches expected sha - apply took effect"
            if ok
            else "MISMATCH: current bytes != expected sha - apply did not produce the expected result"
        )
    else:
        ok = changed
        detail = (
            "file CHANGED from frozen base - apply mutated the file"
            if ok
            else "file UNCHANGED from frozen base - apply did not mutate the file"
        )
    return {
        "ok": ok,
        "changed": changed,
        "expected_sha": expected_sha,
        "current_sha": current,
        "base_sha": base_sha,
        "base_ts": rec.get("ts"),
        "base_label": rec.get("label", ""),
        "label": label,
        "detail": detail,
    }


def list_bases() -> list[dict[str, Any]]:
    return sorted((_load().get("bases") or {}).values(), key=lambda r: str(r.get("path")))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="spec-gate")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_f = sub.add_parser("freeze")
    p_f.add_argument("path")
    p_f.add_argument("--label", default="")
    p_c = sub.add_parser("check")
    p_c.add_argument("path")
    p_g = sub.add_parser("gate")
    p_g.add_argument("path")
    p_v = sub.add_parser("verify-after")
    p_v.add_argument("path")
    p_v.add_argument("--sha", default=None, help="expected sha of the applied result (result oracle)")
    p_v.add_argument("--label", default="")
    sub.add_parser("list")
    args = ap.parse_args(argv)

    if args.cmd == "freeze":
        print(json.dumps(freeze(args.path, label=args.label), indent=2))
    elif args.cmd == "check":
        print(json.dumps(check(args.path), indent=2))
    elif args.cmd == "gate":
        g = gate(args.path)
        print(json.dumps(g, indent=2))
        return 0 if not g.get("blocked") else 3
    elif args.cmd == "verify-after":
        v = verify_after(args.path, expected_sha=args.sha, label=args.label)
        print(json.dumps(v, indent=2))
        return 0 if v.get("ok") else 3
    elif args.cmd == "list":
        print(json.dumps(list_bases(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
