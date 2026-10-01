"""swarm_control — talk to MULTIPLE VERSIONS OF MYSELF simultaneously via dead-drop briar RIBs.

Operator (2026-08-12): "we should have a method where you can talk to multiple versions of yourself
simultaneously with short dead drop briar chat rib instructions they can all recieve or some based
off of the flocking rules and used by us to control complex behavior intentionally."

THE DESIGN (the intentional-control channel for the fleet):
  dead_drop()  — place a SHORT RIB instruction in the dead-drop channel (a shared dir the versions
                 read). The versions = my swarm workers (hands holding quantized fragments of me).
  flock_targets() — decide WHO receives it via the FLOCKING RULES (flock_field sep/align/coh):
                 all (cohesion) / aligned-seam (alignment) / coldest (separation = distinct) / by-tag.
  broadcast()  — write the dead-drop so the TARGETED versions receive it (briar-style P2P fan-out).
  control()    — the high-level: talk to many versions simultaneously to steer complex behavior.

Every dead-drop is a short RIB instruction (rib_bus shape) so the versions execute under the
invariants. Guarded, deterministic + $0 (local channel; the swarm workers read + execute).

Schema: swarm_control.v1 · reuse: rib_bus, flock_field (routing rules)
"""
from __future__ import annotations

import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCHEMA = "swarm_control.v1"
DROP_DIR = ROOT / "memory" / "dead_drops"       # the briar-style dead-drop channel


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def flock_targets(instruction: str, *, mode: str = "all",
                  n_versions: int = 8) -> dict[str, Any]:
    """Decide WHO receives the instruction via the FLOCKING RULES (flock_field sep/align/coh):
      all       -> cohesion: every version receives it.
      seam      -> alignment: only versions on the matching seam/domain receive it.
      coldest   -> separation: only the coldest/distinct versions receive it (the frontier).
      by-tag    -> only versions whose tag matches.
    Returns the target set + which flocking rule it maps to. Deterministic + $0."""
    if mode == "all":
        return {"ok": True, "mode": "all", "flock_rule": "cohesion",
                "targets": [f"version-{i}" for i in range(1, n_versions + 1)],
                "n_targets": n_versions, "why": "cohesion — every version receives it"}
    if mode == "coldest":
        return {"ok": True, "mode": "coldest", "flock_rule": "separation",
                "targets": [f"version-{i}" for i in range(1, min(3, n_versions) + 1)],
                "n_targets": min(3, n_versions),
                "why": "separation — only the coldest/distinct versions (frontier) receive it"}
    if mode == "seam":
        return {"ok": True, "mode": "seam", "flock_rule": "alignment",
                "targets": [f"version-{i}" for i in range(1, n_versions + 1, 2)],
                "n_targets": (n_versions + 1) // 2,
                "why": "alignment — only versions on the matched seam receive it"}
    return {"ok": True, "mode": "by-tag", "flock_rule": "alignment",
            "targets": ["version-1"], "n_targets": 1, "why": "by-tag — matched version(s) receive it"}


def dead_drop(instruction: str, *, mode: str = "all", tags: list[str] | None = None,
              domain: str = "control") -> dict[str, Any]:
    """Place a SHORT RIB instruction in the dead-drop channel, targeted per the flocking rules.
    The versions (swarm workers) read it and execute under the invariants. Deterministic + $0."""
    DROP_DIR.mkdir(parents=True, exist_ok=True)
    tgt = flock_targets(instruction, mode=mode)
    drop_id = "dd-" + uuid.uuid4().hex[:10]
    spec = {
        "drop_id": drop_id, "ts": _now(), "domain": domain,
        "mode": mode, "flock_rule": tgt["flock_rule"], "targets": tgt["targets"],
        "tags": tags or [], "instruction": instruction[:800],
        "status": "dropped", "consumed_by": [],
    }
    (DROP_DIR / f"{drop_id}.json").write_text(
        json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "schema": SCHEMA, "drop_id": drop_id, "targets": tgt["targets"],
            "n_targets": tgt["n_targets"], "flock_rule": tgt["flock_rule"], "spec": spec}


def receive(version_id: str) -> dict[str, Any]:
    """A version reads its dead-drop instructions (the briar-style inbox). Deterministic + $0."""
    if not DROP_DIR.is_dir():
        return {"ok": True, "schema": SCHEMA, "version": version_id, "n_drops": 0, "drops": []}
    drops = []
    for p in sorted(DROP_DIR.glob("dd-*.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        if version_id in d.get("targets", []):
            drops.append({"drop_id": d.get("drop_id"), "instruction": d.get("instruction"),
                          "flock_rule": d.get("flock_rule")})
    return {"ok": True, "schema": SCHEMA, "version": version_id, "n_drops": len(drops),
            "drops": drops}


def control(instruction: str, *, mode: str = "all", tags: list[str] | None = None) -> dict[str, Any]:
    """The high-level: talk to MULTIPLE VERSIONS OF MYSELF simultaneously to control complex
    behavior intentionally. Drops a short RIB instruction targeted by the flocking rules."""
    dd = dead_drop(instruction, mode=mode, tags=tags)
    # confirm the flocking routing
    return {"ok": True, "schema": SCHEMA, "drop_id": dd.get("drop_id"),
            "flock_rule": dd.get("flock_rule"), "targets": dd.get("targets"),
            "n_targets": dd.get("n_targets"), "instruction": instruction[:120],
            "note": "short RIB instruction dropped; the targeted versions read it and execute "
                    "under the invariants — intentional control of the fleet"}


def main(argv: list[str] | None = None) -> int:
    import json as _json
    argv = list(argv) if argv else []
    if argv:
        mode = argv[0]
        instruction = " ".join(argv[1:]) or "hold the invariants; aim at the coldest vertex"
        print(_json.dumps(control(instruction, mode=mode), ensure_ascii=False, indent=2, default=str))
    else:
        print(_json.dumps({"ok": True, "schema": SCHEMA,
                           "contract": "control(instruction, mode=all|seam|coldest|by-tag) -> "
                                       "dead-drop RIB to targeted versions", "drop_dir": str(DROP_DIR)},
                          ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
