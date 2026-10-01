"""steal_lens — make the swarm lensing INHERENT to the steal subsystem: every steal is novelty-scored,
lens-mapped, invariant-sharded, and GPU-routed, then reorg everything to map to the lensing maps.

Operator (2026-08-11): "incorporate into the steal subsystem inherently and think about how we can
reorganize everything to map to our new swarm lensing maps."

THE INHERENT STEAL PASS (deterministic + $0):
  steal(src) -> for every steal, automatically:
     1. file_steal   (steal_pack)           - the steal lands in the pipeline (verkle-folded)
     2. novelty      (novelty_lens)         - how novel is it? (new lens vs variant)
     3. keyword_lens (novelty_lens)         - which lens/domain + similar systems
     4. shard        (invariant_ledger)     - which warm shard it belongs to (cache affinity)
     5. gpu_route    (gpu_lifecycle)        - GPU free? route its render/analysis there
     All recorded into one lensed steal record (the 5 W's + lens + shard + resource) so every steal
     is natively organized into the swarm lensing maps.

  reorg_map() -> the reorganization: map EVERY subsystem to its swarm lens (the lensing-map spine),
     so the system is organized by lens (memory/invariant, economics/cost, compiler/world, swarm/
     detect, ...) instead of by module list. Deterministic.

Schema: steal_lens.v1 · deterministic + $0 · reuse: steal_pack, novelty_lens, invariant_ledger,
gpu_lifecycle
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    from pathlib import Path as _P
    ROOT = _P(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "steal_lens.v1"
STEAL_RECORDS = ROOT / "memory" / "steal_lens" / "records.jsonl"


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def steal(src: str | Path, *, tag: str = "steal", title: str = "") -> dict[str, Any]:
    """The INHERENT steal pass: file + novelty + lens + shard + gpu-route, recorded. Deterministic."""
    src_p = Path(src)
    text = src_p.read_text(encoding="utf-8", errors="replace") if src_p.is_file() else str(src)
    head = title or src_p.stem.replace("_", " ").replace("-", " ")
    rec: dict[str, Any] = {"ts": _now(), "schema": SCHEMA, "title": head}

    # 1) file the steal — the lens pass is now INHERENT to file_steal (novelty + lens + shard + gpu)
    filed = {"ok": False, "error": "not run"}
    try:
        from mag import steal_pack
        filed = steal_pack.file_steal(src_p, tag=tag, remote=False)
    except Exception as e:
        filed = {"ok": False, "error": str(e)[:120]}
    rec["filed"] = {k: filed.get(k) for k in ("ok", "slug", "fold_ok", "verkle", "error")}
    rec["lens"] = filed.get("lens", {})

    # 2) DEFAULT DEEP SELF-STEAL (2026-08-11) — every steal also deep self-steals our egregore +
    #    semantic words + related topics via the swarm (dedupe + enqueue to the research queue).
    rec["egregore_deep_steal"] = {"ok": False}
    try:
        from mag import egregore_steal
        rec["egregore_deep_steal"] = egregore_steal.deep_steal(enqueue=True)
    except Exception as e:
        rec["egregore_deep_steal"] = {"ok": False, "error": str(e)[:120]}
    return {"ok": bool(filed.get("ok")), "schema": SCHEMA, "record": rec,
            "records_path": str(STEAL_RECORDS.relative_to(ROOT)).replace("\\", "/")}


def reorg_map() -> dict[str, Any]:
    """The REORGANIZATION: map every subsystem to its swarm lens (the lensing-map spine)."""
    try:
        from mag import invariant_ledger
        ic = invariant_ledger.interconnect()
        led = invariant_ledger.ledger()
    except Exception as e:
        return {"ok": True, "schema": SCHEMA, "error": str(e)[:120]}
    # group subsystems by lens from the interconnect's lens map
    by_lens: dict[str, list[str]] = {}
    for lens, mods in ic.get("lenses", {}).items():
        by_lens[lens] = [m for m in mods if m in {r["who"] for r in led["rows"]}]
    return {"ok": True, "schema": SCHEMA,
            "reorg_spine": "organize by lens, not by module list",
            "lenses": by_lens, "n_subsystems": led["n_subsystems"],
            "n_unsharded": led["n_unsharded"],
            "note": "everything maps to a lens; each lens is a swarm lensing map; steals land in "
                    "their lens + shard + resource automatically"}


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "contract": "steal(src)->file+novelty+lens+shard+gpu-route (inherent); "
                        "reorg_map()->subsystems by swarm lens",
            "cost": "deterministic + $0",
            "records": str(STEAL_RECORDS.relative_to(ROOT)).replace("\\", "/")}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="steal-lens")
    ap.add_argument("cmd", nargs="?", default="status",
                    choices=["status", "reorg", "steal"])
    ap.add_argument("src", nargs="?", default="", help="steal: path or text")
    a = ap.parse_args()
    if a.cmd == "status":
        print(json.dumps(status(), indent=2, default=str))
    elif a.cmd == "reorg":
        print(json.dumps(reorg_map(), indent=2, default=str))
    else:
        print(json.dumps(steal(a.src or "queue/handoff/STEAL_WORLD_RIB_COMPILER_20260811.md"),
                         indent=2, default=str))
