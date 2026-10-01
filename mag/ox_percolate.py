"""ox_percolate — the SEAM: map the ox artifact domain onto the percolator (2026-08-24).

Deep steal finding (operator): ox_novelty_index IS a percolator — it tags every banked artifact
`novel?` / `consolidated` / `noise`, which is EXACTLY the percolator's explore / invariant /
noise classification, but implemented as a separate module for the artifact domain. Two learning
pipelines (ox artifacts -> distill -> pro_library, and text signal -> invariant -> meta -> the
one) that never shared bytes. This module is the seam that connects them.

The map (respecting the novelty index's tags, reusing the percolator's stores):
  novel?       -> percolate() -> NOVEL -> explore queue (memory/percolator/explore.jsonl)
  consolidated -> percolate() -> REPEAT -> compiled invariant (memory/percolator/invariants.json)
  noise        -> percolate() -> noise file (memory/ghost/noise/ox_artifact.jsonl)
  distill      -> percolate the OX_RESIDENT distill substance -> invariant (the drilled 'one')

Then meta_percolate folds the ox invariants into the single root — the loop LEARNS, it doesn't
just bank files. Deterministic + $0, deduped (mapped ledger + percolator canonical hash).

Schema: ox_percolate.v1 · reuse: percolator, ox_novelty_index (INDEX), ox_resident, ox_megaburn3
CLI: python -m mag.ox_percolate sync | distill | status
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:  # noqa: BLE001
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

SCHEMA = "ox_percolate.v1"
DOMAIN = "ox_artifact"
HANDOFF = ROOT / "handoff"
NOVELTY_INDEX = HANDOFF / "OX_NOVELTY_INDEX.jsonl"
STATE = ROOT / "memory" / "runs" / "ox_percolate" / "mapped.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _mapped_names() -> set[str]:
    if not STATE.is_file():
        return set()
    out = set()
    try:
        for line in STATE.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.strip():
                try:
                    out.add(json.loads(line).get("name", ""))
                except Exception:  # noqa: BLE001
                    pass
    except OSError:
        pass
    return out


def _mark(name: str, tag: str, verdict: str) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    with STATE.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"name": name, "tag": tag, "verdict": verdict, "ts": _now()},
                           ensure_ascii=False) + "\n")


def _artifact_text(name: str) -> str:
    """The artifact's substance (content + reasoning) from the banked file. Empty if missing."""
    for prefix in ("OX_MEGA3_", "OX_RESIDENT_"):
        p = HANDOFF / f"{prefix}{name}.json"
        if p.is_file():
            try:
                d = json.loads(p.read_text(encoding="utf-8", errors="replace"))
            except Exception:  # noqa: BLE001
                continue
            return "\n".join(x for x in ((d.get("content") or ""), (d.get("reasoning") or "")) if x)
    return ""


def sync() -> dict[str, Any]:
    """MAP the novelty-indexed artifacts into the percolator, once each (deduped by name).
    novel?->explore, consolidated->invariant, noise->noise — the same spine, one store."""
    from mag import percolator
    mapped = _mapped_names()
    rows = []
    if NOVELTY_INDEX.is_file():
        try:
            rows = [json.loads(l) for l in NOVELTY_INDEX.read_text(encoding="utf-8",
                                                                    errors="replace").splitlines()
                    if l.strip()]
        except Exception:  # noqa: BLE001
            rows = []
    counts = {"novel": 0, "consolidated": 0, "noise": 0, "percolated": 0}
    for row in rows:
        name = str(row.get("name") or "")
        if not name or name in mapped:
            continue
        tag = str(row.get("tag") or "noise").lower()
        text = _artifact_text(name)
        if not text.strip():
            _mark(name, tag, "empty")
            continue
        try:
            r = percolator.percolate(text, source=f"ox:{name}", domain=DOMAIN)
            verdict = r.get("verdict", "no_signal")
            counts["percolated"] += 1
            if tag.startswith("novel"):
                counts["novel"] += 1
            elif tag == "consolidated":
                counts["consolidated"] += 1
            else:
                counts["noise"] += 1
            _mark(name, tag, verdict)
        except Exception:  # noqa: BLE001
            _mark(name, tag, "error")
    inv = 0
    try:
        inv = len((percolator._load_registry() or {}).get("invariants") or {})
    except Exception:  # noqa: BLE001
        pass
    return {"ok": True, "schema": SCHEMA, "action": "sync", "ts": _now(), **counts,
            "index_rows": len(rows), "invariants_total": inv,
            "detail": f"mapped {counts['percolated']} artifacts into the percolator "
                      f"(novel->explore, consolidated->invariant, noise->noise)"}


def distill() -> dict[str, Any]:
    """PERCOLATE the drilled 'one': the OX_RESIDENT distill substance (and banked resident
    artifacts) -> invariant registry, so what the drill learned becomes standing knowledge that
    meta_percolate can fold into the root."""
    from mag import percolator
    texts = []
    dist = HANDOFF / "OX_RESIDENT_DISTILL.md"
    if dist.is_file():
        texts.append(("distill", dist.read_text(encoding="utf-8", errors="replace")))
    for p in sorted(HANDOFF.glob("OX_RESIDENT_*.json"))[-40:]:
        try:
            d = json.loads(p.read_text(encoding="utf-8", errors="replace"))
        except Exception:  # noqa: BLE001
            continue
        texts.append((p.stem, "\n".join(x for x in ((d.get("content") or ""),
                                                    (d.get("reasoning") or "")) if x)))
    done = 0
    for src, text in texts:
        if not text.strip():
            continue
        try:
            percolator.percolate_signal(text, pattern="cold_vertex", source=src, domain=DOMAIN,
                                        emit_event=False)
            done += 1
        except Exception:  # noqa: BLE001
            pass
    inv = 0
    try:
        inv = len((percolator._load_registry() or {}).get("invariants") or {})
    except Exception:  # noqa: BLE001
        pass
    return {"ok": True, "schema": SCHEMA, "action": "distill", "ts": _now(),
            "percolated": done, "invariants_total": inv,
            "detail": f"percolated {done} drilled/distilled sources into invariants "
                      f"(the drilled 'one' now feeds the standing wave)"}


def status() -> dict[str, Any]:
    from mag import percolator
    reg = {}
    try:
        reg = percolator._load_registry() or {}
    except Exception:  # noqa: BLE001
        pass
    return {"ok": True, "schema": SCHEMA, "mapped": len(_mapped_names()),
            "invariants_total": len(reg.get("invariants") or {}),
            "note": "the ox artifact domain maps onto the percolator — one learning pipeline"}


def main(argv: list[str] | None = None) -> int:
    import argparse
    p = argparse.ArgumentParser(prog="ox_percolate", description="map the ox domain onto the percolator")
    p.add_argument("cmd", nargs="?", default="status", choices=["sync", "distill", "status"])
    a = p.parse_args(argv)
    if a.cmd == "sync":
        print(json.dumps(sync(), indent=2, default=str))
    elif a.cmd == "distill":
        print(json.dumps(distill(), indent=2, default=str))
    else:
        print(json.dumps(status(), indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
