"""clawbot — the swarms' COMMUNICATION + ORGANIZATION CLAW: a RIB spec that gives the swarm a
delivery claw — it hands artifacts (images, large reports) out of vmem, mirrored to the operator's
DESKTOP folders so the operator can SEE what the swarms do.

Operator (2026-08-12): "can we give the swarms like a clawbot for communication organization rib
spec? in vmem we can mirror to c and then i can see shit they do that i ask you for pictures of or
large reports we have desktop folders."

THE DESIGN (the claw):
  1. CLAW-SPEC — the RIB: the swarm's communication + organization contract. The swarm writes its
     artifact (image/report) into its result dir; the clawbot's `deliver()` MIRRORS it out of vmem
     (memory/) to the operator's desktop folder. The operator SEES the swarm's work.
  2. DELIVER  — copy an artifact (image/report) from the workspace/vmem to a desktop delivery
     folder, organized by kind (pictures/ -> Desktop/clawbot/pictures, reports/ ->
     Desktop/clawbot/reports). Deterministic + $0 (a file copy).
  3. WATCH    — scan the swarm results / artifact dirs for images + large reports and deliver them,
     so anything the operator asked to see lands on the desktop automatically.

Schema: clawbot.v1 · deterministic + $0 (file copies) · the communication/organization RIB for the
swarm-to-operator surface.
"""
from __future__ import annotations

import json
import shutil
import sys
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

SCHEMA = "clawbot.v1"
# The operator's desktop folders (the visible surface the claw mirrors to).
DESKTOP = Path.home() / "Desktop"
DELIVERY_ROOT = DESKTOP / "clawbot"
PICTURES_DIR = DELIVERY_ROOT / "pictures"
REPORTS_DIR = DELIVERY_ROOT / "reports"

IMG_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
REPORT_EXT = {".md", ".txt", ".json", ".jsonl", ".html", ".log", ".pdf"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def claw_spec() -> dict[str, Any]:
    """The CLAW-SPEC RIB: the swarm's communication + organization contract. Deterministic + $0."""
    return {"ok": True, "schema": SCHEMA,
            "rib": "clawbot-communication-organizer (the claw): the swarm writes its artifact "
                   "(image/report) to its result dir; the clawbot DELIVERS it out of vmem to the "
                   "operator's desktop folder (pictures/ or reports/) so the operator SEES the "
                   "swarm's work. Deterministic + $0 (a file copy). Organize by kind, never "
                   "untangle later.",
            "delivery_root": str(DELIVERY_ROOT),
            "pictures_dir": str(PICTURES_DIR),
            "reports_dir": str(REPORTS_DIR),
            "contract": "deliver(path)->mirror an artifact to the desktop; watch()->auto-deliver "
                        "images + large reports from the swarm's results so anything asked for "
                        "lands on the desktop"}


def _kind(path: Path) -> str:
    return "pictures" if path.suffix.lower() in IMG_EXT else "reports"


def deliver(path: str | Path, *, kind: str | None = None) -> dict[str, Any]:
    """MIRROR an artifact out of vmem (the workspace) to the operator's desktop folder — the
    operator SEES the swarm's work. Deterministic + $0 (a file copy)."""
    src = Path(path)
    if not src.is_file():
        return {"ok": False, "schema": SCHEMA, "error": f"artifact not found: {src}"}
    k = kind or _kind(src)
    d = PICTURES_DIR if k == "pictures" else REPORTS_DIR
    d.mkdir(parents=True, exist_ok=True)
    dst = d / src.name
    try:
        shutil.copy2(src, dst)
    except Exception as e:
        return {"ok": False, "schema": SCHEMA, "error": str(e)[:120]}
    return {"ok": True, "schema": SCHEMA, "tool": "clawbot", "kind": k,
            "delivered": str(dst), "source": str(src),
            "note": f"clawbot delivered the {k} artifact to your desktop — you can see it now"}


def watch(*, max_deliver: int = 25) -> dict[str, Any]:
    """AUTO-DELIVER: scan the swarm results + artifact dirs for images and large reports, and
    mirror them to the desktop so the operator SEES what the swarms did. Deterministic + $0."""
    delivered: list[str] = []
    candidates: list[Path] = []
    # the swarm results dir + the vmem artifact dirs
    for d in (ROOT / "memory" / "runs" / "swarm_worker" / "results",
              ROOT / "memory" / "artifacts",
              ROOT / "memory" / "corpus"):
        if d.is_dir():
            for p in d.rglob("*"):
                if p.is_file() and (p.suffix.lower() in IMG_EXT or p.suffix.lower() in REPORT_EXT):
                    candidates.append(p)
    for p in candidates[:max_deliver]:
        r = deliver(p)
        if r.get("ok"):
            delivered.append(r["delivered"])
    return {"ok": True, "schema": SCHEMA, "tool": "clawbot", "n_delivered": len(delivered),
            "delivered": delivered[:20],
            "delivery_root": str(DELIVERY_ROOT),
            "note": "clawbot auto-delivered images + reports from the swarm to your desktop — "
                    "anything you asked to see now lands where you can see it"}


def deliver_drift(*, max_targets: int = 25) -> dict[str, Any]:
    """TIE-IN (2026-08-13, operator 'could this be tied into our underutilized clawbot idea'):
    the clawbot DELIVERS the swarm's DRIFT-TARGETS to the operator's desktop — a visible 'drift
    inbox' of findings agents flagged as useful-to-the-whole for later inspection, so the targeting
    drift isn't lost and the operator can see where the swarm wants to aim next. Deterministic + $0."""
    targets = []
    try:
        from mag import swarm_tools
        targets = (swarm_tools.drift_targets(limit=max_targets) or {}).get("targets", [])
    except Exception as e:
        return {"ok": False, "schema": SCHEMA, "tool": "clawbot",
                "error": f"drift_targets unavailable: {str(e)[:120]}"}
    if not targets:
        return {"ok": True, "schema": SCHEMA, "tool": "clawbot", "n_drift": 0,
                "note": "no drift-targets yet — nothing flagged for later inspection"}
    # write a drift-inbox report to the desktop (visible to the operator)
    REPORT_DIR = DELIVERY_ROOT / "reports"
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    lines = ["# Drift-Targets — the swarm's flagged-for-later-inspection", "",
             "Findings agents on other tasks marked as useful to the whole. Target drifts toward these:", ""]
    for t in targets:
        lines.append(f"- {t.get('scent', '')[:200]}  [{t.get('at','')}]")
    out = REPORT_DIR / "drift_inbox.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    return {"ok": True, "schema": SCHEMA, "tool": "clawbot", "n_drift": len(targets),
            "delivered": str(out),
            "note": "clawbot delivered the drift-targets to your desktop — the swarm's "
                    "flagged-for-later-inspection, visible where you can aim"}


def spelunker() -> dict[str, Any]:
    """The knowledge-graph SPELUNKER surface (the Tableau-like view) — ALREADY EXISTS:
    the Control Room dashboard on :8765 with lattice_query.graph_viewport() (nodes, edges,
    kinds, theme histogram) + the idea graph MAP (memory/ideas) + the verkle lattice dashboard.
    The clawbot's deliverables feed this surface so the operator can SPELUNK the graph.
    Deterministic + $0."""
    viewport = {}
    try:
        from mag import lattice_query
        viewport = lattice_query.graph_viewport(sample_n=8)
    except Exception as e:
        viewport = {"error": str(e)[:80]}
    dashboard_up = False
    try:
        import urllib.request
        with urllib.request.urlopen("http://127.0.0.1:8765", timeout=4) as r:
            dashboard_up = r.status == 200
    except Exception:
        dashboard_up = False
    return {"ok": True, "schema": SCHEMA, "tool": "clawbot-spelunker",
            "dashboard_url": "http://127.0.0.1:8765", "dashboard_up": dashboard_up,
            "graph_viewport": viewport,
            "launch": "launch_dashboard.cmd (Control Room dashboard — the Tableau-like surface)",
            "note": "the knowledge-graph spelunker EXISTS: Control Room :8765 + graph_viewport "
                    "(nodes/edges/kinds/themes). The clawbot delivers artifacts to your desktop "
                    "AND feeds this graph — you spelunk the swarm's work on :8765"}


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="clawbot")
    ap.add_argument("cmd", nargs="?", default="spec",
                    choices=["spec", "deliver", "watch", "spelunker"])
    ap.add_argument("path", nargs="?", default="")
    a = ap.parse_args(argv)
    if a.cmd == "deliver":
        print(json.dumps(deliver(a.path or str(REPORTS_DIR)), ensure_ascii=False, indent=2, default=str))
    elif a.cmd == "watch":
        print(json.dumps(watch(), ensure_ascii=False, indent=2, default=str))
    elif a.cmd == "spelunker":
        print(json.dumps(spelunker(), ensure_ascii=False, indent=2, default=str))
    else:
        print(json.dumps(claw_spec(), ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
