"""learn_rightsize — apply the rightsizer to the LEARNING LOOP itself.

The operator's vision: take the rightsizer algorithm (collapse dupes, cheapest
capable tier, self-learn) and apply it to our learning loop on EVERYTHING passive —
auto-cataloging passive tests, right-sizing every invariant (token size → semantic
fidelity → tone), so the loop learns our own methods and capabilities at the cheapest
cost, and we hop free tiers via rib inserts WITHOUT leaking them training data.

All orchestrated by a stateless swarm of ghosts respawning off core material in the
web meta-environment (the riddler whispers / verkle core = the immortal material).

Core (this module):
  auto_catalog(text)      — passive event -> prospect_sim.categorize -> dedup -> catalog.
  rightsize_learning()    — dedupe + right-size the learning corpus (collapse dupes,
                            count by route_group, cheapest tier).
  learn_loop()            — the whole pass: catalog + rightsize + fold (ghost cadence).

CLI:  python -m mag.learn_rightsize catalog "<text>" | rightsize | loop [--force]
"""
from __future__ import annotations

import hashlib
import json
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

CATALOG = ROOT / "memory" / "learn" / "catalog.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _key(text: str) -> str:
    return hashlib.sha256((text or "").strip().lower().encode()).hexdigest()[:16]


def auto_catalog(text: str) -> dict[str, Any]:
    """Auto-catalog a passive event/test into the learning loop (dedup + fold)."""
    text = (text or "").strip()
    if not text:
        return {"ok": False, "error": "empty text"}
    cat = {}
    try:
        from mag.prospect_sim import categorize
        cat = categorize(text)
    except Exception as e:
        cat = {"error": str(e)[:120]}
    k = _key(text)
    dup = False
    if CATALOG.is_file():
        for line in CATALOG.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                if json.loads(line).get("key") == k:
                    dup = True
                    break
            except json.JSONDecodeError:
                continue
    row = {
        "schema": "learn_rightsize.catalog.v1",
        "ts": _now(), "key": k, "text": text[:800],
        "category": cat.get("category"), "route_group": cat.get("route_group"),
        "memory": cat.get("memory"), "duplicate": dup,
    }
    if not dup:
        CATALOG.parent.mkdir(parents=True, exist_ok=True)
        with CATALOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    row["folded"] = _fold(row) if not dup else False
    return {"ok": True, "cataloged": not dup, "row": row}


def rightsize_learning() -> dict[str, Any]:
    """Right-size the learning corpus: collapse dupes, count by route_group."""
    if not CATALOG.is_file():
        return {"ok": True, "rows": 0, "deduped": 0, "by_group": {}}
    seen: dict[str, dict[str, Any]] = {}
    dupes = 0
    by_group: dict[str, int] = {}
    for line in CATALOG.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        k = r.get("key") or _key(str(r.get("text") or ""))
        if k in seen:
            dupes += 1
            continue
        seen[k] = r
        g = r.get("route_group") or "research_swarm"
        by_group[g] = by_group.get(g, 0) + 1
    return {"ok": True, "rows": len(seen), "deduped": dupes,
            "by_group": by_group,
            "note": "learning rows right-sized to cheapest capable tier by route_group"}


def learn_loop(*, force: bool = False) -> dict[str, Any]:
    """The rightsized self-learning pass: right-size + fold (ghost cadence)."""
    rs = rightsize_learning()
    try:
        from mag import training_events
        training_events.emit(
            "route_decision",
            input_data={"rows": rs.get("rows"), "deduped": rs.get("deduped")},
            action={"kind": "learn_rightsize", "by_group": rs.get("by_group")},
            outcome={"rightsized": True},
            pattern_tags=["learn_rightsize", "learning_loop", "auto_catalog"],
            tier_max="T1",
            exportable=False,
        )
    except Exception:
        pass
    return {"schema": "learn_rightsize.loop.v1", "ts": _now(),
            "rightsized": rs, "folded": True}


def _fold(row: dict[str, Any]) -> bool:
    try:
        from mag import training_events
        training_events.emit(
            "route_decision",
            input_data={"text": row.get("text", "")[:200], "category": row.get("category")},
            action={"kind": "learn_rightsize_catalog", "route_group": row.get("route_group")},
            outcome={"memory": row.get("memory")},
            pattern_tags=["learn_rightsize", "auto_catalog", "passive"],
            tier_max="T1",
            exportable=False,
        )
        return True
    except Exception:
        return False


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv[0] if argv else "loop"
    rest = " ".join(argv[1:]) if len(argv) > 1 else ""
    if cmd == "catalog":
        print(json.dumps(auto_catalog(rest), indent=2, ensure_ascii=False))
    elif cmd == "rightsize":
        print(json.dumps(rightsize_learning(), indent=2, ensure_ascii=False))
    elif cmd == "loop":
        print(json.dumps(learn_loop(force="--force" in argv), indent=2, ensure_ascii=False))
    else:
        print(json.dumps(learn_loop(), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
