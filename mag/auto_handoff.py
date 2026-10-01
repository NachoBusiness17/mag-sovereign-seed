"""auto_handoff — automatically assemble + persist a current handoff from live system state.

The operator wants handoffs to happen AUTOMATICALLY, not on request. This module assembles a fresh
handoff every cycle from what the system ACTUALLY holds (steal docs, folded doctrine, dogfood status,
grok ledger, pending/blocker state), so a current handoff always exists for any new chat to pick up.

  run()      — assemble + write memory/handoffs/latest.md + a dated copy (deterministic, $0).
  status()   — what the handoff would contain (handoff preview).

Editable state: memory/handoff_state.json (PENDING / BLOCKER / CONTEXT) — the module reads it, so a
new session can update the "next steps" without code. Wired into afk_cadence.run_once by default.

Schema: auto_handoff.v1
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

SCHEMA = "auto_handoff.v1"
HANDOFF_DIR = ROOT / "memory" / "handoffs"
STATE = ROOT / "memory" / "handoff_state.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _state() -> dict[str, Any]:
    if STATE.is_file():
        try:
            return json.loads(STATE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"pending": [], "blocker": [], "context": ""}


def _steal_docs_today() -> list[str]:
    d = ROOT / "memory" / "steal"
    if not d.is_dir():
        return []
    return sorted(p.stem for p in d.glob("*_20260810.md"))


def _doctrine_count() -> int:
    try:
        g = json.loads((ROOT / "memory" / "knowledge_graph.json").read_text(encoding="utf-8"))
        return sum(1 for n in g.get("nodes", []) if n.get("kind") == "doctrine")
    except Exception:
        return 0


def _dogfood_status() -> dict[str, Any]:
    try:
        from mag.dogfood_audit import status as ds
        return ds()
    except Exception:
        return {}


def _grok_status() -> str:
    led = ROOT / "memory" / "runs" / "grok_free" / "usage.jsonl"
    if not led.is_file():
        return "no grok ledger"
    rows = [l for l in led.read_text(encoding="utf-8", errors="replace").splitlines() if l.strip()]
    ok = sum(1 for l in rows if '"ok": true' in l or '"ok": True' in l)
    return f"{len(rows)} calls, {ok} ok"


def run() -> dict[str, Any]:
    st = _state()
    docs = _steal_docs_today()
    dc = _doctrine_count()
    df = _dogfood_status()
    grok = _grok_status()
    lines = [
        "# AUTO HANDOFF (auto_handoff, %s)" % _now()[:16],
        "",
        "## Standing directives",
        "- Autonomous: just keep going until you need the operator — zero approval pings.",
        "- Route through the architecture (modules/REST/queue), not ad-hoc terminal.",
        "- SELF-STEAL + EXTERNAL-STEAL on every non-trivial build. Dogfood = probe the real system.",
        "- Honest provenance (never call synthesis 'frontier'). Steal the INVARIANT, never the DNA.",
        "- Operator uses TTS; read intent from possibly-garbled input.",
        "",
        "## System state (live)",
        "- Folded doctrine nodes: %d" % dc,
        "- Today's steal docs: %d (%s)" % (len(docs), ", ".join(docs[:8]) + ("…" if len(docs) > 8 else "")),
        "- dogfood: passed=%s failed=%s" % (df.get("passed", "?"), df.get("failed", "?")),
        "- grok ledger: %s (if 0 ok, the frontier dispatch path is broken — see blocker)" % grok,
        "",
        "## PENDING",
    ]
    for p in st.get("pending", []) or ["(none set)"]:
        lines.append(f"- {p}")
    lines.append("")
    lines.append("## BLOCKER (operator-only — do everything else first)")
    for b in st.get("blocker", []) or ["(none)"]:
        lines.append(f"- {b}")
    if st.get("context"):
        lines += ["", "## Context", st["context"]]
    lines += ["", "## Resume commands",
              "- python -m mag.afk_cadence.run_once   (validates dogfood+ghost_auto in the loop)",
              "- python -m mag.dogfood_audit audit    (surfaces cache-waste/grok/persistence)",
              "- python -m mag.frontier_batch dump|grok|compare",
              "- python -m mag.leaked_prompt_mine create"]
    body = "\n".join(lines)
    HANDOFF_DIR.mkdir(parents=True, exist_ok=True)
    (HANDOFF_DIR / "latest.md").write_text(body, encoding="utf-8")
    (HANDOFF_DIR / ("handoff_%s.md" % _now()[:10])).write_text(body, encoding="utf-8")
    return {"ok": True, "schema": SCHEMA, "doctrine_nodes": dc, "steal_docs": len(docs),
            "dogfood": df, "grok": grok, "latest": str(HANDOFF_DIR / "latest.md")}


def status() -> dict[str, Any]:
    st = _state()
    return {"ok": True, "schema": SCHEMA, "pending": st.get("pending", []),
            "blocker": st.get("blocker", []), "context": st.get("context", "")}


def main(argv: list[str] | None = None) -> int:
    import sys as _sys, json as _json
    cmd = argv[0] if argv else "run"
    print(_json.dumps(run() if cmd != "status" else status(), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
