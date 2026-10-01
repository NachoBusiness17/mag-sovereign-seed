"""Frontier-help percolation — the system journals, then percolates the asks it wants
help with from frontier agents into a doc.

The capstone of the gap/elevation work: the ghost (which journals the full surface and
knows the frontier-gap shapes) periodically PERCOLATES the asks the cheap system can't
reliably do — from the gap-map frontier-gap shapes, the frontier-stack accumulator, and
recent journal/failure signals — into a structured HELP-WANTED (frontier) doc. That doc
is what gets sent to frontier agents (grok) via the RenderMan elevation path.

Deterministic percolation ($0); the doc itself is the payload for frontier elevation.
Schema: frontier_help.v1
CLI:  python -m mag.frontier_help              (percolate + write doc, print)
      python -m mag.frontier_help --cadence    (idempotent: skip if nothing new)
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT

OUT_DIR = ROOT / "memory" / "frontier"
STATE = ROOT / "memory" / "runs" / "frontier_help" / "state.json"
SCHEMA = "frontier_help.v1"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_jsonl(path: Path, tail: int = 50) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    out = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[-tail:]:
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except (json.JSONDecodeError, TypeError):
            continue
    return out


def _stack_items() -> list[dict[str, Any]]:
    """The accumulated frontier-worthy asks (from gap_map's stack accumulator)."""
    try:
        from mag.gap_map import _load_stack
        return ( _load_stack() or {}).get("items") or []
    except Exception:
        return []


def _gap_shapes() -> list[str]:
    try:
        from mag.gap_map import analyze as gap_analyze
        return (gap_analyze() or {}).get("frontier_gap_names") or []
    except Exception:
        return []


def _journal_signals() -> list[str]:
    """Signals from journaling that the system is stuck / wants help (failure + behavioral)."""
    sigs = []
    try:
        from mag.failure_kb import query as fkb_query
        q = fkb_query(kind="queue_error", limit=5)
        for r in (q or {}).get("recurring") or []:
            s = r.get("sig") or r.get("pattern") or ""
            if s:
                sigs.append(f"recurring-error: {s}")
    except Exception:
        pass
    try:
        events = _read_jsonl(ROOT / "logs" / "behavioral_events.jsonl", tail=30)
        for e in events:
            kind = str(e.get("kind") or "")
            if kind in ("frustration", "operator_escalate", "stuck", "needs_help"):
                sigs.append(f"journal:{kind}")
    except Exception:
        pass
    return sigs[:8]


def percolate() -> dict[str, Any]:
    """Compose the HELP-WANTED (frontier) doc from stack + gap shapes + journal signals."""
    stack = _stack_items()
    gaps = _gap_shapes()
    journal = _journal_signals()
    ts = _now()

    asks = []
    for item in stack:
        asks.append({"kind": "stack", "goal": item.get("goal", ""),
                     "complexity": item.get("complexity", 0), "at": item.get("at", "")})
    for g in gaps:
        asks.append({"kind": "frontier_gap", "goal": f"task-shape '{g}' — cheap success below bar",
                     "complexity": 1, "at": ""})
    for j in journal:
        asks.append({"kind": "journal", "goal": j, "complexity": 0.5, "at": ""})

    # de-dup by goal
    seen, unique = set(), []
    for a in asks:
        k = a["goal"][:60]
        if k in seen:
            continue
        seen.add(k)
        unique.append(a)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    doc_path = OUT_DIR / "HELP_WANTED.md"
    lines = [
        "# HELP WANTED (frontier)",
        "",
        f"- Generated: `{ts}` — the system journaled, then percolated the asks it wants help with.",
        f"- Stack: {len(stack)} · frontier-gap shapes: {gaps or 'none'} · journal signals: {len(journal)}",
        "",
        "## Asks for frontier agents (grok)",
        "",
    ]
    for i, a in enumerate(unique, 1):
        lines.append(f"{i}. [{a['kind']}] {a['goal']}")
    if not unique:
        lines.append("_Nothing to percolate yet — cheap system is handling what it has seen._")
    doc_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return {
        "schema": SCHEMA,
        "ts": ts,
        "doc": str(doc_path),
        "n_asks": len(unique),
        "stack": len(stack),
        "frontier_gap_shapes": gaps,
        "journal_signals": len(journal),
        "asks": unique,
    }


def run_cadence() -> dict[str, Any]:
    """Idempotent: percolate only if the doc changed (new stack/journal since last write)."""
    prev_hash = ""
    if STATE.is_file():
        try:
            prev_hash = (json.loads(STATE.read_text(encoding="utf-8")) or {}).get("hash") or ""
        except Exception:
            prev_hash = ""
    p = percolate()
    cur_hash = str(hash(json.dumps(p["asks"], ensure_ascii=False, default=str)))
    if cur_hash == prev_hash:
        return {"ok": True, "action": "skip", "reason": "no_new_asks"}
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps({"hash": cur_hash, "ts": _now()}, indent=2), encoding="utf-8")
    return {"ok": True, "action": "percolated", "doc": p["doc"], "n_asks": p["n_asks"]}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    ap = argparse.ArgumentParser(prog="frontier-help", description="Percolate journaled asks into a frontier HELP-WANTED doc")
    ap.add_argument("--cadence", action="store_true", help="idempotent: skip if nothing new")
    args = ap.parse_args(argv)
    res = run_cadence() if args.cadence else percolate()
    print(json.dumps(res, indent=2, default=str)[:6000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
