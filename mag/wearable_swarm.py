"""wearable_swarm — prototype: control the swarm from an AI-enhanced wearable (VR/AR), Baymax-style.

Operator (2026-08-11): "prototype swarm skills for real world control via AI enhanced wearables,
to control swarms. like baymax." + "we should build in support for [the VR headset] too, to test
these things and prototype them."

THE IDEA: the wearable (VR headset browser / AR glasses) is a companion command + awareness surface
for the swarm. The operator speaks or taps a "swarm skill" -> the wearable routes the intent through
the SAME deterministic machinery we already have (voice_trigger.dispatch -> queue -> drainer), and
renders live swarm state back to the HUD. This is the cheapest possible Baymax: a head-up control
panel that steers the cheap swarm, with no new runtime — it reuses our own stack.

Components (deterministic + $0, module functions only):
  skills()            -> the "swarm skills" catalog (control verbs the wearable exposes).
  command(text, dry)  -> route a spoken/tapped intent to a swarm action (dry=plan, or fire via
                         voice_trigger.dispatch -> queue). Deterministic routing.
  surface()           -> the wearable HUD payload: live swarm/queue/percolator/seams + skills +
                         a one-line overlay caption for the VR/AR browser to render.
  skills_rib()        -> fold each swarm skill as a RIB (rib_bus.publish_rib) so the wearable's
                         command layer is durable + mounted by workers. (fold, deterministic)

Schema: wearable_swarm.v1 · deterministic + $0 · reuse: voice_trigger, orchestrator, ghost_memlance,
percolator, rib_bus. No terminal spawns; async fire routes through the queue.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from typing import Any

try:
    from config import ROOT
except Exception:
    from pathlib import Path
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "wearable_swarm.v1"

# ── THE SWARM SKILLS CATALOG — control verbs the wearable exposes (Baymax-style) ──
# Each maps to an action our existing machinery already handles. Deterministic.
SWARM_SKILLS: dict[str, dict[str, Any]] = {
    "dispatch":   {"action": "dispatch", "desc": "send a goal to a seat / swarm (queue)",
                   "say": "send <goal>"},
    "research":   {"action": "research", "desc": "spawn a deep-research dig (queue)",
                   "say": "research <topic>"},
    "steer":      {"action": "steer", "desc": "steer the running swarm (awareness seam)",
                   "say": "steer <guidance>"},
    "strike":     {"action": "strike", "desc": "invoke strike-the-chord (clarity mode)",
                   "say": "strike the chord"},
    "focus":      {"action": "focus", "desc": "surface the swarm seams / divergences to the HUD",
                   "say": "focus seams"},
    "status":     {"action": "status", "desc": "swarm health + queue + percolator + intake to the HUD",
                   "say": "status"},
    "percolate":  {"action": "percolate", "desc": "run a raw signal through the percolator",
                   "say": "percolate <signal>"},
    "mind":       {"action": "mind", "desc": "grok what the swarm is learning (top invariants / explore)",
                   "say": "mind"},
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def skills() -> list[dict[str, Any]]:
    """The wearable's command catalog — what the operator can say/tap to control the swarm."""
    return [{"name": k, **v} for k, v in SWARM_SKILLS.items()]


def parse_command(text: str) -> list[dict[str, Any]]:
    """Map a spoken/tapped command to swarm skills (deterministic keyword parse)."""
    text = (text or "").strip().lower()
    out: list[dict[str, Any]] = []
    seen = set()
    for name, meta in SWARM_SKILLS.items():
        kw = name if name != "mind" else "mind"
        if name == "mind" and ("mind" in text or "learning" in text):
            pass
        elif name not in text:
            continue
        if meta["action"] in seen:
            continue
        seen.add(meta["action"])
        out.append({"skill": name, "action": meta["action"], "desc": meta["desc"]})
    # fall back to the generic voice_trigger parser for the standard verbs
    try:
        from mag import voice_trigger
        for t in voice_trigger.parse(text):
            if t["action"] not in seen:
                seen.add(t["action"])
                out.append({"skill": t["trigger"], "action": t["action"], "desc": t["desc"]})
    except Exception:
        pass
    return out


def command(text: str, *, dry: bool = True, source: str = "wearable") -> dict[str, Any]:
    """Route a wearable command to the swarm. dry=True returns the plan ($0); dry=False fires it
    through voice_trigger.dispatch -> queue (drainer eats it). Deterministic routing."""
    text = (text or "").strip()
    cmds = parse_command(text)
    if not cmds:
        return {"ok": False, "schema": SCHEMA, "source": source, "text": text,
                "matched": [], "note": "no swarm skill matched"}
    actions = [c["action"] for c in cmds]
    if "focus" in actions or "status" in actions or "mind" in actions or "percolate" in actions:
        # awareness skills never fire async; they return the HUD immediately
        surf = surface()
        return {"ok": True, "schema": SCHEMA, "source": source, "text": text,
                "matched": cmds, "handled": "surface", "dry": True, **surf}
    if dry:
        return {"ok": True, "schema": SCHEMA, "source": source, "text": text,
                "matched": cmds, "dry": True,
                "note": "would route through voice_trigger.dispatch -> queue (drainer eats it)"}
    try:
        from mag import voice_trigger
        fired = voice_trigger.dispatch(text, source=source)
        return {"ok": True, "schema": SCHEMA, "source": source, "text": text,
                "matched": cmds, "dry": False, "fired": fired.get("fired")}
    except Exception as e:
        return {"ok": False, "schema": SCHEMA, "source": source, "text": text,
                "matched": cmds, "dry": False, "error": str(e)[:200]}


def surface(*, detail: bool = True) -> dict[str, Any]:
    """The wearable HUD payload — what the VR/AR overlay renders. Deterministic + $0."""
    hud: dict[str, Any] = {"schema": SCHEMA, "ts": _now()}
    try:
        from mag import ghost
        s = ghost.sense()
        hud["swarm"] = {
            "inbox_pending": s.get("inbox_pending", 0),
            "copilot_pending": s.get("copilot_inbox_pending", 0),
            "training_rows": s.get("training_rows", 0),
            "frustration_total": s.get("frustration_total", 0),
            "percolator": s.get("percolator", {}),
        }
    except Exception:
        hud["swarm"] = {"ok": False}
    try:
        from mag import queue
        q = queue.status() if hasattr(queue, "status") else {}
        hud["queue"] = {"depth": (q or {}).get("depth", (q or {}).get("pending", 0))}
    except Exception:
        hud["queue"] = {"depth": None}
    try:
        from mag import percolator
        reg = percolator._load_registry()
        hud["percolator"] = {"n_invariants": len(reg.get("invariants") or {}),
                             "false_positives": reg.get("false_positives", 0),
                             "explore": len(percolator._read_jsonl(percolator.EXPLORE_QUEUE, 1_000_000)),
                             "intake_open": percolator.open_intake()["n_open"]}
    except Exception:
        hud["percolator"] = {"ok": False}
    hud["skills"] = skills()
    top = sorted(SWARM_SKILLS.items(), key=lambda kv: kv[0])[:3]
    hud["caption"] = ("Wearable swarm HUD — say/tap a swarm skill. "
                      "Skills: " + ", ".join(k for k, _ in top) + ", …")
    return hud


def skills_rib(*, fold: bool = True) -> dict[str, Any]:
    """Fold each swarm skill as a RIB (durable instruction layer the workers mount). $0."""
    if not fold:
        return {"ok": True, "schema": SCHEMA, "n": len(SWARM_SKILLS), "folded": False}
    out = {"ok": True, "schema": SCHEMA, "folded": [], "n": len(SWARM_SKILLS)}
    try:
        from mag import rib_bus
        for name, meta in SWARM_SKILLS.items():
            out["folded"].append(rib_bus.publish_rib(
                f"Wearable swarm skill '{name}': {meta['desc']}. Say: {meta['say']}.",
                domain="wearable-swarm", source="wearable_swarm", target_rank="T2",
                fold=True, publish=True))
    except Exception as e:
        out["error"] = str(e)[:200]
    return out


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "contract": "command(text, dry) -> route to swarm; surface() -> VR/AR HUD; "
                        "skills() -> catalog; skills_rib() -> fold as RIBs",
            "n_skills": len(SWARM_SKILLS), "cost": "deterministic + $0",
            "surface": "reuses ghost.sense / percolator / queue — no new runtime"}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="wearable-swarm")
    ap.add_argument("cmd", nargs="?", default="surface",
                    choices=["surface", "skills", "status", "rib", "command"])
    ap.add_argument("--text", default="", help="command text")
    ap.add_argument("--dry", action="store_true", help="command: dry run (plan only)")
    a = ap.parse_args()
    if a.cmd == "surface":
        print(json.dumps(surface(), indent=2, default=str))
    elif a.cmd == "skills":
        print(json.dumps(skills(), indent=2, default=str))
    elif a.cmd == "rib":
        print(json.dumps(skills_rib(), indent=2, default=str))
    elif a.cmd == "status":
        print(json.dumps(status(), indent=2, default=str))
    else:
        print(json.dumps(command(a.text, dry=a.dry, source="cli"), indent=2, default=str))
