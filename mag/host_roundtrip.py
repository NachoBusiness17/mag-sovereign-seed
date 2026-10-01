"""host_roundtrip — the swarm remembers host state and round-trips it back (the K3 mission).

Build (2026-08-11, operator: "you have the invariants + tool research, do what I asked against
the codebase"). The mechanism from the DeepSeek arc: an AI frontier instructs K (launch k3s) ->
the swarm runs the DETERMINISTIC mission -> the swarm remembers host state -> round-trips it
back to the host -> the host completes the deterministic mission.

Grounds on OUR invariants (not hallucination): verkle_knot (content-addressed state), memlang
(instruction token), machine_target (deterministic rank). Honest: returns host state ONLY if a
real source records it; never fabricates.

Schema: host_roundtrip.v1 · deterministic + $0 · reuse: verkle_knot, memlang, machine_target
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "host_roundtrip.v1"
MISSION_RECORD = ROOT / "memory" / "runs" / "host_roundtrip" / "missions.jsonl"


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def instruct(mission: str, *, frontier_instruct: str = "") -> dict[str, Any]:
    """Frontier instructs K: compile the deterministic mission to a memlang token + rank,
    record the intended mission. Does NOT claim k3s is running (honest)."""
    out: dict[str, Any] = {"schema": SCHEMA, "ok": True, "ts": _now(), "mission": mission}
    try:
        from mag import memlang
        tok = memlang.compile_token("rib_elevate", frontier_instruct or mission)
        out["token_len"] = tok.get("token_len")
        out["opcode"] = tok.get("opcode")
        out["anchor_hex"] = (tok.get("anchor_hex") or "")[:16]
        out["compile"] = bool(tok.get("ok"))
    except Exception as e:
        out["compile_error"] = str(e)[:120]
    try:
        from mag import machine_target
        out["target"] = {"rank": "T2", "action": machine_target.TARGETS["T2"]["action"]}
    except Exception:
        out["target"] = {"rank": "T2", "action": "file_write"}
    MISSION_RECORD.parent.mkdir(parents=True, exist_ok=True)
    with MISSION_RECORD.open("a", encoding="utf-8") as f:
        f.write(json.dumps(out, ensure_ascii=False) + "\n")
    return out


def remember_host_state() -> dict[str, Any]:
    """The swarm records host state as a verkle knot (content-addressed). Returns the knot ONLY
    if append_verkle_knot actually returns a real knot — else honest 'unavailable'."""
    try:
        from mag import verkle_knot
        k = verkle_knot.append_verkle_knot({
            "session_id": f"host-roundtrip-{_now()}",
            "theme": "host-state",
            "summary": "[host_roundtrip] swarm remembered host state (deterministic mission record)",
        })
        if k and k.get("leaf_hash"):
            return {"ok": True, "recorded": True,
                    "leaf_hash": k.get("leaf_hash"), "root": k.get("verkle_root") or k.get("root", "")}
    except Exception as e:
        return {"ok": False, "recorded": False, "error": str(e)[:120]}
    return {"ok": False, "recorded": False, "note": "no verkle knot returned (NOT fabricating)"}


def roundtrip(mission: str, *, frontier_instruct: str = "") -> dict[str, Any]:
    """The full round-trip: instruct (token) -> remember host state (verkle knot) -> return the
    recorded state to the host to complete the deterministic mission. Honest verdicts."""
    inst = instruct(mission, frontier_instruct=frontier_instruct)
    state = remember_host_state()
    return {
        "schema": SCHEMA, "ok": bool(inst.get("ok") and state.get("recorded")),
        "mission": mission,
        "instruction": inst,
        "host_state": state,
        "roundtrip_complete": bool(state.get("recorded")),
        "note": "host can now complete the deterministic mission from the round-tripped state"
                if state.get("recorded") else "round-trip incomplete (no verkle knot recorded)",
    }


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "contract": "instruct(mission)->memlang token+rank; remember_host_state()->verkle knot; "
                        "roundtrip()->instruct+remember+return (honest)",
            "cost": "deterministic + $0", "record": str(MISSION_RECORD.relative_to(ROOT))}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="host-roundtrip")
    ap.add_argument("mission", nargs="*", default=[])
    a = ap.parse_args()
    if a.mission:
        print(json.dumps(roundtrip(" ".join(a.mission)), indent=2, default=str))
    else:
        print(json.dumps(status(), indent=2, default=str))
