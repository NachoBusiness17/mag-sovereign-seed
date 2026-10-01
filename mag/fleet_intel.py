"""fleet_intel — THE DOGFOOD SURFACE: aggregate the fleet's own organs into one intel page.

Operator order (2026-09-06): "we have blackboards, atlas, card catalog — all of these
incredibly complex analyses and we surface none of it usefully."

This organ reads the fleet's own instruments (deterministic, $0, read-only) and emits
dashboard/static/intel.json + dashboard/static/intel.html — the intelligence, surfaced:
  chain tip + seal        — memory/biography/verkle_tip.json, state/seal_latest.json
  blackboard decisions    — mag.swarm_tools.blackboard_read (36 pinned)
  card catalog            — watch/DISPOSITIONS.json + watch/INTAKE_*.md
  corpus shelves          — memory/corpus/ractors/corpus_index.json
  grounding wave          — watch/GROUNDING_WAVE.jsonl
  tesuji shells           — watch/tesuji_shells.jsonl
  burn state              — memory/burn/steer_log.jsonl (last entry)
  pin audit               — watch/receipts/pin_audit_latest.txt
  panels + salons         — queue/handoff/ractors/PANEL_FOLD_*.md, memory/runs/salons/
  register                — memory/ghost/intake/register.jsonl (work knots)

Usage: python mag/fleet_intel.py   (idempotent; writes intel.json + intel.html, wires nav)
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

OUT_JSON = ROOT / "dashboard" / "static" / "intel.json"
NAV = ROOT / "dashboard" / "static" / "nav.js"


def _tail_jsonl(path: Path, n: int = 5):
    if not path.is_file():
        return []
    rows = []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    for line in reversed(lines):
        if len(rows) >= n:
            break
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            rows.append({"raw": line[:200]})
    return rows


def _count(path: Path) -> int:
    if not path.is_file():
        return 0
    try:
        return sum(1 for line in path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip())
    except OSError:
        return 0


def build_intel() -> dict:
    intel: dict = {"schema": "fleet_intel.v1",
                   "generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                   "sections": {}}

    # chain + seal
    tip = {}
    tp = ROOT / "memory" / "biography" / "verkle_tip.json"
    if tp.is_file():
        try:
            tip = json.loads(tp.read_text(encoding="utf-8"))
        except Exception:
            tip = {"error": "unreadable"}
    seal = {}
    sp = ROOT / "state" / "seal_latest.json"
    if sp.is_file():
        try:
            seal = json.loads(sp.read_text(encoding="utf-8"))
        except Exception:
            seal = {"error": "unreadable"}
    intel["sections"]["chain"] = {
        "root": str(tip.get("root", "?"))[:16],
        "n_leaves": tip.get("n_leaves", "?"),
        "seal_verified": seal.get("verified", None),
        "seal_ts": seal.get("ts", seal.get("sealed_at", "?")),
    }

    # blackboard (the egregore's shared mind)
    try:
        sys.path.insert(0, str(ROOT))
        from mag.swarm_tools import blackboard_read
        bb = blackboard_read(limit=6)
        intel["sections"]["blackboard"] = {
            "n_pinned": bb.get("n_pinned", 0),
            "pinned": [
                {"kind": r.get("kind"), "owner": r.get("owner"), "text": str(r.get("text", ""))[:180]}
                for r in (bb.get("pinned") or [])[:6]
            ],
        }
    except Exception as e:
        intel["sections"]["blackboard"] = {"error": str(e)[:120]}

    # card catalog (dispositions + intake cards)
    disp = {}
    dp = ROOT / "watch" / "DISPOSITIONS.json"
    if dp.is_file():
        try:
            disp = json.loads(dp.read_text(encoding="utf-8"))
        except Exception:
            disp = {}
    cards = disp.get("cards", {})
    latest_cards = sorted(cards.items(), key=lambda kv: kv[0], reverse=True)[:8]
    intake_cards = sorted((ROOT / "watch").glob("INTAKE_*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    intel["sections"]["cards"] = {
        "dispositioned": len(cards),
        "intake_cards_on_disk": len(intake_cards),
        "latest": [{"card": k, "verdict": v[:160]} for k, v in latest_cards],
    }

    # corpus shelves
    ci = ROOT / "memory" / "corpus" / "ractors" / "corpus_index.json"
    if ci.is_file():
        try:
            cix = json.loads(ci.read_text(encoding="utf-8"))
            intel["sections"]["corpus"] = {"totals": cix.get("totals", {}),
                                           "shelves": {k: v.get("texts") for k, v in cix.get("shelves", {}).items()}}
        except Exception:
            intel["sections"]["corpus"] = {"error": "unreadable"}

    # grounding wave + tesuji shells + burn
    gw = _tail_jsonl(ROOT / "watch" / "GROUNDING_WAVE.jsonl", 3)
    intel["sections"]["grounding_wave"] = {"rows": _count(ROOT / "watch" / "GROUNDING_WAVE.jsonl"), "tail": gw}
    intel["sections"]["tesuji"] = {"rows": _count(ROOT / "watch" / "tesuji_shells.jsonl"),
                                   "tail": _tail_jsonl(ROOT / "watch" / "tesuji_shells.jsonl", 3)}
    burn_tail = _tail_jsonl(ROOT / "memory" / "burn" / "steer_log.jsonl", 1)
    if burn_tail:
        tel = burn_tail[0].get("telemetry", {})
        intel["sections"]["burn"] = {"ts": burn_tail[0].get("ts"), "total_mtok": tel.get("total_mtok")}
    intel["sections"]["pin_audit"] = {
        "brief": (ROOT / "watch" / "receipts" / "pin_audit_latest.txt").read_text(encoding="utf-8", errors="replace")[:600]
        if (ROOT / "watch" / "receipts" / "pin_audit_latest.txt").is_file() else ""
    }

    # panels + salons + register
    panels = sorted((ROOT / "queue" / "handoff" / "ractors").glob("PANEL_FOLD_*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    intel["sections"]["panels"] = [p.name for p in panels[:5]]
    salons = sorted((ROOT / "memory" / "runs" / "salons").glob("*/SALON_ARTIFACT.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    intel["sections"]["salons"] = [p.parent.name for p in salons[:6]]
    intel["sections"]["register_rows"] = _count(ROOT / "memory" / "ghost" / "intake" / "register.jsonl")
    intel["sections"]["atlas_receipts"] = _count(ROOT / "memory" / "runs" / "atlas" / "receipts.jsonl")
    return intel






def render_brief_into_page() -> int:
    from mag.render_brief import render_brief_into_page as _r
    return _r()

def main() -> int:
    intel = build_intel()
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    src_brief = ROOT / "watch" / "HUMAN_BRIEF_20260906.md"
    if src_brief.is_file():
        (ROOT / "dashboard" / "static" / "HUMAN_BRIEF_20260906.md").write_text(src_brief.read_text(encoding="utf-8"), encoding="utf-8")
    OUT_JSON.write_text(json.dumps(intel, indent=1, ensure_ascii=False), encoding="utf-8")
    render_brief_into_page()
    # wire nav (idempotent)
    try:
        nav = NAV.read_text(encoding="utf-8")
        if "/static/intel.html" not in nav:
            nav = nav.replace('["/static/mesh_gallery.html", "Mesh Gallery"],',
                              '["/static/mesh_gallery.html", "Mesh Gallery"],\n    ["/static/intel.html", "Intel"],')
            NAV.write_text(nav, encoding="utf-8")
    except OSError:
        pass
    n = intel["sections"]
    print(f"intel: chain n={n['chain'].get('n_leaves')} seal={n['chain'].get('seal_verified')} "
          f"blackboard_pinned={n['blackboard'].get('n_pinned', '?')} cards={n['cards'].get('dispositioned')} "
          f"-> {OUT_JSON.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
