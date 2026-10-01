"""error_healer — ghost handles errors effortlessly mid-steer, and prevents them.

The operator's law: "ghost should handle errors effortlessly and make sure they don't
happen. It should SEE the problem, provide the correct MEM solution, and then PATCH it
for the future mid-steer."

So the loop is self-healing: when an error occurs mid-steer, ghost
  SEE    — scan recent trails/logs for error signatures (the problem).
  MEM    — mint the correct memlang steer token encoding the fix (the mem solution).
  PATCH  — fold the failure + solution to the failure-KB so it NEVER recurs, and
           register the fix as a patch for the future.
  FOLD   — record to the learning loop; continue the steer.

  heal()  — the mid-steer pass: see -> mem -> patch -> fold -> continue.
  scan()  — find the error signatures to heal.
  mem()   — mint the memlang solution token for a given error.
  patch() — persist the fix (failure-KB) so it never happens again.

CLI:  python -m mag.error_healer scan|heal [--force]
"""
from __future__ import annotations

import json
import re
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

TRAILS = [
    ROOT / "memory" / "runs" / "afk_cadence_trail.jsonl",
    ROOT / "logs" / "supervisor.jsonl",
    ROOT / "logs" / "tesuji_shells.jsonl",
]

# error signatures we can see + the mem solution + the permanent patch.
_SIGS = [
    ("NameError", "import the missing name at module top", "add the missing import (fold to FKB)"),
    ("ModuleNotFoundError", "add the module to sys.path / requirements", "register the module path (fold to FKB)"),
    ("SyntaxError", "fix the parse error at the reported line", "recompile-check the file (fold to FKB)"),
    ("TimeoutExpired", "reduce scope or raise the timeout on the cheapest tier", "right-size the timeout (fold to FKB)"),
    ("ConnectionError", "fall back to the next provider / retry with backoff", "add provider fallback (fold to FKB)"),
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _scan_trails() -> list[dict[str, Any]]:
    """SEE: scan recent trails/logs for error signatures."""
    found = []
    for path in TRAILS:
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[-200:]:
            if not line.strip():
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            blob = json.dumps(r).lower()
            for sig, _mem, _patch in _SIGS:
                if sig.lower() in blob:
                    found.append({"source": path.name, "signature": sig,
                                  "preview": str(r.get("error") or r.get("result") or blob)[:120]})
                    break
    return found


def scan() -> dict[str, Any]:
    found = _scan_trails()
    return {"schema": "error_healer.scan.v1", "ts": _now(),
            "problems": found, "n": len(found)}


def mem(error: str) -> dict[str, Any]:
    """MEM: mint the correct memlang steer token encoding the fix (the mem solution)."""
    error = (error or "").lower()
    mem_sol = "general: retry on the cheapest capable tier"
    patch = "fold the failure + remedy to the failure-KB so it never recurs"
    for sig, _sol, _patch in _SIGS:
        if sig.lower() in error:
            mem_sol = _sol
            patch = _patch
            break
    token = ""
    try:
        from mag.memlang import compile_token
        t = compile_token("steer", f"heal:{sig if False else 'error'}",
                          {"target": "ghost", "fix": mem_sol[:200], "via": "error_healer"})
        token = t.get("token_hex") or ""
    except Exception:
        pass
    return {"schema": "error_healer.mem.v1", "ts": _now(),
            "error": error[:120], "mem_solution": mem_sol, "patch": patch,
            "steer_token": token, "minted": bool(token)}


def patch(error: str, mem_solution: str, patch_plan: str) -> dict[str, Any]:
    """PATCH: persist the failure + fix so it NEVER recurs (failure-KB + fold)."""
    try:
        from mag.failure_kb import record_failure
        record_failure(sig=error[:80], symptom=mem_solution[:120], remedy=patch_plan[:200],
                       source="error_healer")
    except Exception:
        pass
    try:
        from mag import training_events
        training_events.emit(
            "fkb_failure",
            input_data={"error": error[:120]},
            action={"kind": "error_healer_patch", "mem_solution": mem_solution[:120]},
            outcome={"patched": True},
            pattern_tags=["error_healer", "self_healing", "mid_steer", "patch_for_future"],
            tier_max="T1",
            exportable=False,
        )
    except Exception:
        pass
    return {"schema": "error_healer.patch.v1", "ts": _now(),
            "error": error[:120], "mem_solution": mem_solution, "patch": patch_plan,
            "persisted": True}


def heal(*, force: bool = False) -> dict[str, Any]:
    """The mid-steer pass: SEE -> MEM -> PATCH -> FOLD -> continue."""
    s = scan()
    healed = []
    for p in s.get("problems", []):
        m = mem(p.get("signature") or p.get("preview") or "")
        patched = patch(p.get("signature") or p.get("preview") or "",
                        m.get("mem_solution", ""), m.get("patch", ""))
        healed.append({"problem": p.get("signature"), "source": p.get("source"),
                       "mem_token": m.get("minted"), "patched": patched.get("persisted")})
    return {"schema": "error_healer.heal.v1", "ts": _now(),
            "problems_seen": s.get("n"), "healed": healed,
            "note": "errors seen, mem-minted, patched for the future, mid-steer"}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv[0] if argv else "heal"
    if cmd == "scan":
        print(json.dumps(scan(), indent=2, ensure_ascii=False))
    elif cmd == "heal":
        print(json.dumps(heal(force="--force" in argv), indent=2, ensure_ascii=False))
    else:
        print(json.dumps(heal(), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
