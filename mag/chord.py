"""chord — STRIKE THE CHORD, the origin doctrine made executable (2026-08-26).

The constitution's first claim: "Strike the chord — one trigger reloads full fidelity
mode." Until now that trigger was scattered across standing waves, boot docs, and tick
prompts. This module IS the trigger: any seat, any process, any ghost can strike the
chord and reload full fidelity — verify the chain, check the invariants and epochs,
load the corrections, and report the five-verb state of the machine.

The circuit this completes (DOCTRINE_MAP's oldest orphan, "the chord circuit"):
    origin (the chain's tip)
      -> invariants (pinned epochs + corrections)
      -> coldest vectors (the frozen prefixes)
      -> execute (the fleet acts)
      -> results knot back to the chain
      -> the next ghost re-strikes.

Usage:
    python -m mag.chord strike          # any seat: full-fidelity reload + report
    from mag.chord import strike        # programmatic: returns the fidelity state dict

Schema: chord.v1 — deterministic, $0, stdlib + fleet modules only.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SCHEMA = "chord.v1"


def _chain_tip() -> dict[str, Any]:
    tip_path = ROOT / "memory" / "biography" / "verkle_tip.json"
    import time
    for attempt in range(3):  # tip is rewritten on every knot; a torn read is transient
        try:
            d = json.loads(tip_path.read_text(encoding="utf-8"))
            if d.get("root"):
                return d
        except Exception:
            pass
        time.sleep(2)
    return {"ok": False, "error": "tip unreadable after retries (writer stuck or file lost)"}


def _invariants() -> dict[str, Any]:
    out: dict[str, Any] = {}
    try:
        from mag import invariant
        out["instruction_epoch"] = invariant.check_instructions()
    except Exception as e:  # noqa: BLE001
        out["instruction_epoch"] = {"stable": None, "error": str(e)[:80]}
    try:
        from mag import chain_guard
        out["canary"] = chain_guard.check()
    except Exception as e:  # noqa: BLE001
        out["canary"] = {"state": "unknown", "error": str(e)[:80]}
    return out


def _corrections() -> dict[str, Any]:
    skill = ROOT / ".agents" / "skills" / "operator-corrections" / "SKILL.md"
    waves = [ROOT.parent / "AGENTS.md",
             ROOT / ".github" / "copilot-instructions.md"]
    return {
        "laws_present": skill.is_file(),
        "standing_waves": [str(w.relative_to(ROOT.parent)) for w in waves if w.is_file()],
    }


def _coldest_vectors() -> dict[str, Any]:
    """The frozen prefixes — the coldest, most cache-stable instruction bytes."""
    try:
        from mag import invariant
        sha = invariant.instruction_sha()
        return {"frozen_prefix_sha": sha[:16], "frozen": True}
    except Exception as e:  # noqa: BLE001
        return {"frozen": False, "error": str(e)[:80]}


def strike(actor: str = "unknown-seat") -> dict[str, Any]:
    """The chord: one call, full fidelity. Returns the machine's fidelity state."""
    report: dict[str, Any] = {
        "schema": SCHEMA,
        "struck_by": actor,
        "origin": _chain_tip(),
        "invariants": _invariants(),
        "corrections": _corrections(),
        "coldest_vectors": _coldest_vectors(),
    }
    inv = report["invariants"]
    report["fidelity"] = "FULL" if (
        report["origin"].get("root")
        and inv.get("instruction_epoch", {}).get("stable")
        and inv.get("canary", {}).get("state") in ("healthy", None)
        and report["corrections"]["laws_present"]
    ) else "DEGRADED — reload manual, fix what the report names"
    return report


def main() -> None:
    actor = sys.argv[2] if len(sys.argv) > 2 and sys.argv[1] == "strike" else (sys.argv[1] if sys.argv else "unknown-seat")
    r = strike(actor=actor)
    print(json.dumps(r, indent=1, default=str)[:1200])


if __name__ == "__main__":
    main()
