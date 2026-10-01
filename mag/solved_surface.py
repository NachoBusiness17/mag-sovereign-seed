"""solved_surface — automatically surface what our history already solved, from the internals.

Operator directive (2026-08-10): "this is a solved problem, our k8s need to be better about
surfacing them. look at our history via our internals you should do this automatically."

Never hand-derive what our own history already holds. This reads the INTERNALS directly and
returns the SOLVED PROBLEMS as a surfaced list, so any surface (seat, K8s annotations, REST)
can present them automatically. Schema: solved_surface.v1 · deterministic, $0.

Sources (the internals that hold the solved history):
  - memory/improve/pro_library.json  → case law (solved decisions / steer moves)
  - memory/rib/*.md                  → RIB (our complete understanding / geometric maps)
  - memory/biography/verkle_tip.json → the verkle history tip (content-addressed memory)
CLI: python -m mag.solved_surface
REST: GET /api/v1/solved
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "solved_surface.v1"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _read_json(p: Path) -> dict[str, Any]:
    try:
        return json.loads(p.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}


def _case_law() -> list[dict[str, Any]]:
    """Solved decisions from pro_library (case law)."""
    d = _read_json(ROOT / "memory" / "improve" / "pro_library.json")
    moves = d.get("moves") or []
    out = []
    for m in moves:
        out.append({
            "kind": "case_law",
            "id": m.get("id"),
            "move": (m.get("move") or "").strip(),
            "maps_to": m.get("maps_to"),
            "last_used": m.get("last_used"),
        })
    return out


def _rib() -> list[dict[str, Any]]:
    """Our geometric maps of understanding (RIB docs) — the solved understanding."""
    rib_dir = ROOT / "memory" / "rib"
    out = []
    if rib_dir.is_dir():
        for f in sorted(rib_dir.glob("*.md")):
            text = f.read_text(encoding="utf-8", errors="replace")
            m = re.search(r"^#\s*(.+)$", text, re.M)
            title = m.group(1).strip() if m else f.stem
            one_line = ""
            m2 = re.search(r"goal:?\s*(.+)", text, re.I)
            if m2:
                one_line = m2.group(1).strip()[:200]
            out.append({"kind": "rib", "id": f.stem, "title": title, "one_line": one_line})
    return out


def _verkle_tip() -> dict[str, Any]:
    """The verkle history tip — content-addressed memory of what's happened."""
    tip = _read_json(ROOT / "memory" / "biography" / "verkle_tip.json")
    return {
        "root": (tip.get("root") or "")[:16],
        "n_leaves": tip.get("n_leaves"),
        "last": tip.get("last_filename"),
    }


def solved() -> dict[str, Any]:
    """The surfaced solved problems, read automatically from the internals."""
    case_law = _case_law()
    rib = _rib()
    tip = _verkle_tip()
    return {
        "schema": SCHEMA,
        "ts": _now(),
        "ok": True,
        "verkle_tip": tip,
        "n_case_law": len(case_law),
        "n_rib": len(rib),
        "case_law": case_law,
        "rib": rib,
        "summary": (
            f"{len(case_law)} case-law decisions + {len(rib)} RIB maps "
            f"({tip.get('n_leaves')} verkle leaves) — the solved history, surfaced from the internals."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    print(json.dumps(solved(), indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
