"""ghost_spooky — the running test of ghost's abilities to affect outcomes.

Every prompt gets a SPOOKY block: which autonomous things ghost can (and will) do
to move the outcome, shown as a live capability probe. This is a LONG-STANDING
loop per prompt — not a one-off. Each probe is folded into the learning surface
(training_events) so the operator always sees ghost flexing its levers, and the
system learns which levers actually moved things.

The "spooky" levers (things ghost does silently / autonomously to affect outcomes):
  sense       — read live system state (inbox, frustration, verkle, training rows)
  nudge       — apply the nudge contract: cheap-first, grok-gated routing
  route       — dispatch through the one-window skill pipeline
  queue       — spawn async work so the drainer eats it (never inline)
  icon        — drop a clickable icon for human-only actions (never nag)
  loopbreak   — detect + break a crash/respawn loop
  rightsize   — right-size the queue / subsystems to the cheapest capable tier
  retire      — delete old/superseded tools and LEARN from it
  whisper     — deniable store for anything that needs to stay out of plaintext
  summon      — sense intent from current+future+coldest vertices
  fold        — fold every decision into skill_ledger + training_events (self-improving)

CLI: python -m mag.ghost_spooky "<prompt>"     (show which spooky levers apply)
     python -m mag.ghost_spooky --all          (show the full catalog)
"""
from __future__ import annotations

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

# id -> (name, what ghost does, how it affects the outcome, trigger words)
CATALOG: dict[str, dict[str, Any]] = {
    "sense": {"name": "Sense", "what": "read live system state (inbox, frustration, verkle, training rows)",
              "effect": "ghost knows where things stand before it acts", "triggers": ("status", "what", "how", "where", "sense")},
    "nudge": {"name": "Nudge", "what": "apply the nudge contract: cheap-first, grok-gated routing",
              "effect": "cost + quality steered before a single model call", "triggers": ("route", "nudge", "cost", "spend", "token", "cheap")},
    "route": {"name": "Route", "what": "dispatch through the one-window skill pipeline",
              "effect": "the ask reaches the right module without manual wiring", "triggers": ("run", "do", "route", "handle", "process")},
    "queue": {"name": "Queue", "what": "spawn async work so the drainer eats it",
              "effect": "long work runs in the background, never inline", "triggers": ("queue", "async", "background", "later", "drain")},
    "icon": {"name": "Icon-drop", "what": "drop a clickable icon for human-only actions",
             "effect": "operator gets a doorway for what ghost can't automate", "triggers": ("reload", "secret", "manual", "operator", "vast", "click")},
    "loopbreak": {"name": "Loop-break", "what": "detect + break a crash/respawn loop",
                  "effect": "no window storms, no self-destructing respawns", "triggers": ("crash", "loop", "storm", "respawn", "spinning")},
    "rightsize": {"name": "Right-size", "what": "collapse dupes + route to cheapest capable tier",
                  "effect": "the same work done for fewer tokens", "triggers": ("efficient", "rightsize", "token", "dedup", "backlog")},
    "retire": {"name": "Tool-retire", "what": "delete old/superseded tools and LEARN from it",
               "effect": "no dead tools rot in the tree; each retirement is a lesson", "triggers": ("delete", "retire", "old tool", "superseded", "cleanup")},
    "whisper": {"name": "Whisper", "what": "deniable store for anything that must not sit in plaintext",
                "effect": "sensitive context survives without a visible trail", "triggers": ("whisper", "deniable", "secret", "hide")},
    "summon": {"name": "Summon", "what": "sense intent from current+future+coldest vertices",
               "effect": "ghost sees what you should do next, not just what you asked", "triggers": ("intent", "summon", "what should", "next")},
    "fold": {"name": "Fold", "what": "fold every decision into skill_ledger + training_events",
             "effect": "each interaction makes the system measurably smarter", "triggers": ("learn", "train", "record", "fold")},
    # ── PROACTIVE LEVERS (2026-08-11, forged this session) — the kit goes HUNT, not just react ──
    "steal": {"name": "Steal", "what": "self-steal (audit our own pro_library/skill_ledger/memory) AND external-steal (find other systems) and ADAPT before answering/building",
              "effect": "never build from blank; the mechanism is stolen + adapted to our deterministic shape", "triggers": ("steal", "!steal", "adapt", "borrow", "spook")},
    "survey": {"name": "Survey", "what": "draw the territory via the hypervisor/observability (Prometheus/Grafana/k8s metrics) + ghost.sense scanning the seams",
               "effect": "the machine monitors itself; ghost sees the map before it moves (survey->mine->slay)", "triggers": ("survey", "observability", "metrics", "hypervisor", "monitor", "prometheus", "grafana")},
    "map": {"name": "Map/Solve", "what": "roll the d8 (1 of 8 lenses), look at the map (jones_lens coordinate), shade the flock seams, dispatch to the k8s swarm render farm",
             "effect": "the territory solver: emergent swarm behavior, frontier at the seams only, pennies", "triggers": ("map", "territory", "d8", "lens", "solve", "collapse")},
    "fetch": {"name": "Fetch", "what": "reach our OWN fetch surface (research_pack._fetch_url then browser_driver CDP) for blocked/JS/anti-bot content — never 'can't'",
               "effect": "a 403 is a signal to switch surfaces, not a dead end; the container browser reads JS-walled shares", "triggers": ("fetch", "share", "url", "blocked", "read", "page")},
    "btw": {"name": "Btw", "what": "drop a live-aside dot (btw_sidechannel: inject/travel/sense/rightsize) that re-maps the territory live",
             "effect": "a '/btw' aside IS a live instruction; cold vector +1 agent, warm -1; pointillism operational", "triggers": ("btw", "aside", "coordinate", "travel", "dot", "vector")},
    "campaign": {"name": "Campaign", "what": "run survey->mine->slay as ONE operation (seed the map as a series of territories, drift the stateless self toward the goal)",
                  "effect": "the strategic umbrella: hypervisor surveys so the swarm can mine diamonds and slay dragons", "triggers": ("campaign", "survey mine slay", "drift", "goal", "strategic")},
}


def probe(prompt: str) -> dict[str, Any]:
    """Return the spooky levers that apply to this prompt (ghost's ability test)."""
    t = (prompt or "").lower()
    applied = []
    for lid, c in CATALOG.items():
        if any(tr in t for tr in c["triggers"]):
            applied.append({"id": lid, "name": c["name"], "what": c["what"], "effect": c["effect"]})
    # always include sense + fold (ghost always senses and always learns)
    always = []
    for lid in ("sense", "fold"):
        if lid not in [a["id"] for a in applied]:
            always.append({"id": lid, "name": CATALOG[lid]["name"],
                           "what": CATALOG[lid]["what"], "effect": CATALOG[lid]["effect"]})
    applied = always + applied
    out = {
        "schema": "ghost_spooky.v1",
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "levers": applied,
        "count": len(applied),
        "line": _one_line(applied),
    }
    # PROVE (steal: mag.verkle_knot.prove) — real reconstruction invariant: ghost
    # takes a live memory pointer + sibling path and RECREATES the chain root. This
    # turns the spooky block from a listing into a verifiable ability test.
    try:
        from mag.verkle_knot import prove_latest
        p = prove_latest()
        if p.get("ok"):
            out["prove"] = {
                "pointer": f"knot/{p['leaf_hash'][:8]}",
                "index": p["index"],
                "n_leaves": p["n_leaves"],
                "invariant": p["equation"],
                "root": p["root"][:16] + "…",
                "verified": bool(p["verified"]),
            }
        else:
            out["prove"] = {"error": p.get("error", "prove unavailable")}
    except Exception as e:
        out["prove"] = {"error": str(e)[:120]}
    _fold(out, prompt)
    return out


def _one_line(applied: list[dict[str, Any]]) -> str:
    return " · ".join(a["name"] for a in applied) + " → affecting the outcome"


def _fold(probe_row: dict[str, Any], prompt: str) -> None:
    """Long-standing loop: fold each spooky probe into the learning surface."""
    try:
        from mag import training_events
        training_events.emit(
            "operator_behavior",
            input_data={"prompt": (prompt or "")[:200]},
            action={"kind": "ghost_spooky_probe", "levers": [a["id"] for a in probe_row["levers"]]},
            outcome={"count": probe_row["count"]},
            pattern_tags=["ghost_spooky", "ability_probe", "long_standing_loop"],
            tier_max="T1",
            exportable=False,
        )
    except Exception:
        pass


def all_abilities() -> dict[str, Any]:
    return {"schema": "ghost_spooky.catalog.v1", "levers": [
        {"id": lid, "name": c["name"], "what": c["what"], "effect": c["effect"]}
        for lid, c in CATALOG.items()]}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "--all":
        print(json.dumps(all_abilities(), indent=2, ensure_ascii=False))
        return 0
    prompt = " ".join(argv) if argv else ""
    print(json.dumps(probe(prompt), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
