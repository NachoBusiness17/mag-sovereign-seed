"""frontier_batch — dump our research findings and cross-check them against REAL frontier (Grok).

Rooted in the provenance-honesty recalibration (2026-08-10): we admitted the session's 'frontier'
work was OUR grounded synthesis, and the grok dispatch path was dead (9/9). This module makes the
honest test concrete:
  1. collect()  — pull the session's research findings (doctrine nodes from the session's sources).
  2. dump()     — write them as a batch file (the 'batch dump' to hand to a frontier model).
  3. run_grok() — attempt a REAL Grok call via the CLI harness (escalate_via_harness); label
                  provenance honestly ('frontier_model_output' only if a real call succeeded, else
                  'not_dispatched').
  4. compare()  — Grok's response vs our findings (sharpest disagreements, confirms, gaps).

Schema: frontier_batch.v1 · deterministic (collect/dump) · launch: python -m mag.frontier_batch dump|grok|compare
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

SCHEMA = "frontier_batch.v1"
OUT_DIR = ROOT / "memory" / "runs" / "frontier_batch"

# The session's research sources (what we claim to have 'found' — test these against real grok).
SESSION_SOURCES = {
    "frontier_advice", "socratic_steal", "diogenes_steal", "frontier_gadfly_and_dog",
    "provenance_honesty", "full_session_weave", "window_bus", "window_hop",
    "verkle_bus_research_project", "rightsize-tesuji", "shadow_work_session_test",
    "shadow_work_session_specific",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def collect() -> list[dict[str, Any]]:
    """Pull the session's doctrine findings from the knowledge graph."""
    try:
        from mag.knowledge_graph import GRAPH_PATH
        g = json.loads(GRAPH_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []
    findings = [n for n in g.get("nodes", [])
                if n.get("kind") == "doctrine" and n.get("source") in SESSION_SOURCES]
    return findings


def dump(*, write: bool = True) -> dict[str, Any]:
    """Write the findings as a batch markdown file (the 'batch dump')."""
    findings = collect()
    lines = ["# Frontier batch — session research findings (2026-08-10)",
             "", "Provenance: OUR grounded synthesis (fetched + local), NOT frontier-model output.",
             "Cross-check against a REAL frontier model (Grok).", "",
             f"{len(findings)} findings:", ""]
    for n in sorted(findings, key=lambda x: str(x.get("label"))):
        lines.append(f"- [{n.get('source')}] **{n.get('label')}**: {str(n.get('summary'))[:240]}")
    text = "\n".join(lines)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / "findings_batch.md"
    if write:
        path.write_text(text, encoding="utf-8")
    return {"ok": True, "schema": SCHEMA, "n_findings": len(findings),
            "path": str(path), "chars": len(text)}


def run_grok(*, timeout: int = 300) -> dict[str, Any]:
    """Attempt a REAL Grok call on the findings. Provenance is labeled honestly: only a genuine
    harness success counts as frontier_model_output; anything else is not_dispatched."""
    try:
        from harness.grok_cli import harness_available, escalate_via_harness
    except Exception as e:
        return {"ok": False, "schema": SCHEMA, "provenance": "not_dispatched",
                "error": f"harness import failed: {str(e)[:120]}"}
    if not harness_available():
        return {"ok": False, "schema": SCHEMA, "provenance": "not_dispatched",
                "error": "grok harness binary not available"}
    findings = collect()
    summary = "\n".join(f"- {n.get('label')}: {str(n.get('summary'))[:140]}" for n in findings[:30])
    goal = ("You are the independent frontier auditor. Here are a local system's research findings "
            "(claims). For each, give ONE sharp verdict: AGREE / CHALLENGE / GAP, and in one line why. "
            "Flag anything that sounds like unverified confidence or a mislabel of 'synthesis as "
            "frontier'. Be blunt (Diogenes).\n\nFINDINGS:\n" + summary[:12000])
    r = escalate_via_harness(goal=goal, timeout=timeout, output_format="plain")
    provenance = "frontier_model_output" if r.get("ok") else "not_dispatched"
    out_path = OUT_DIR / f"grok_response_{_now()[:19].replace(':','')}.md"
    if r.get("ok"):
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        out_path.write_text(str(r.get("deliverable") or ""), encoding="utf-8")
    return {"ok": bool(r.get("ok")), "schema": SCHEMA, "provenance": provenance,
            "exit_code": r.get("exit_code"), "error": r.get("error") or r.get("stderr", "")[:300],
            "path": str(out_path) if r.get("ok") else None}


def compare() -> dict[str, Any]:
    """Show the latest grok response alongside our findings (the honest cross-check)."""
    resp = sorted(OUT_DIR.glob("grok_response_*.md"))[-1] if list(OUT_DIR.glob("grok_response_*.md")) else None
    return {"ok": True, "schema": SCHEMA,
            "findings": collect(), "grok_response_path": str(resp) if resp else None,
            "note": "read the grok_response file to diff against findings_batch.md"}


def swarm_task(*, surface: str = "grok", max_wait_s: int = 180) -> dict[str, Any]:
    """Swarm-routable frontier cross-check: drive the container browser (ghost, over CDP) to ask a
    REAL frontier model (grok) to audit our findings. Honest provenance: only a captured browser
    answer counts as frontier_model_output; anything else reports the seat blocker (so the swarm
    doesn't count a failed dispatch as a real frontier call). Deterministic, $0. Any flock /
    ghost_auto agent can call this as a task."""
    try:
        import mag.browser_driver as bd
    except Exception as e:
        return {"ok": False, "schema": SCHEMA, "provenance": "not_dispatched",
                "error": f"browser_driver import failed: {str(e)[:120]}"}
    findings = collect()
    goal = ("You are the independent frontier auditor. Our local system made these research claims. "
            "For each give ONE sharp verdict: AGREE / CHALLENGE / GAP, one line why. Flag any "
            "unverified confidence or 'synthesis labeled as frontier'. Be blunt (Diogenes).\n\n"
            + "\n".join(f"- {n.get('label')}: {str(n.get('summary'))[:130]}" for n in findings[:28])[:9000])
    r = bd.ask(goal, surface=surface, max_wait_s=max_wait_s)
    if r.get("ok") and (r.get("content") or "").strip():
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        out_path = OUT_DIR / f"grok_browser_{_now()[:19].replace(':','')}.md"
        out_path.write_text(str(r.get("content")), encoding="utf-8")
        try:  # fold the REAL frontier opinion back as doctrine (honest provenance)
            from mag.knowledge_graph import fold
            fold("frontier-opinion-batch", "doctrine",
                 f"REAL frontier (grok via ghost browser) on our findings: {str(r.get('content'))[:400]}",
                 source="frontier_model_output")
        except Exception:
            pass
        return {"ok": True, "schema": SCHEMA, "provenance": "frontier_model_output",
                "surface": surface, "content": r.get("content"), "path": str(out_path)}
    return {"ok": False, "schema": SCHEMA, "provenance": "not_dispatched",
            "error": r.get("error", "no answer captured"),
            "seat_hint": "browser seat must be up (container CDP) AND grok logged in (persistent auth)"}


def main(argv: list[str] | None = None) -> int:
    import sys as _sys
    cmd = argv[0] if argv else "dump"
    if cmd == "grok":
        print(json.dumps(run_grok(), indent=2, default=str))
    elif cmd == "compare":
        print(json.dumps(compare(), indent=2, default=str))
    else:
        print(json.dumps(dump(), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(_sys.argv[1:]))
