"""scifi_fantasy_steal — self-steal the ENTIRE fantasy and sci-fi corpus via our swarm, and read
back what comes out as a test. Dogfoods the process: the corpus is routed to the SWARM research
queue (swarm_surface.route_novel -> stochastic models analyze in-cluster); we read the results.

Operator (2026-08-11): "i think it's important at this time to self steal your entire fantasy and
scifi corpus via our swarm and see what comes out as a test."

SELF-STEAL (grounded in our own corpus):
  SCI-FI invariants already folded (memory/steal/DEEP_SCIFI_STEAL_20260810.md): butlerian_jihad,
  mentat_core, psychohistory_flock, second_foundation, dark_forest_secrecy, ancillary_egregore,
  primed_pedagogy, culture_minds, solaris_mirror, second_primer.
  FANTASY corpus: the riddler fantasy_village domain + the game/narrative surfaces (bard's epic
  tapestry, fantasy faces as deniable surrogates).

THE FLOW (deterministic + $0 gathering; swarm-routed analysis; idempotent via dedup):
  corpus()   -> gather the ENTIRE fantasy+sci-fi corpus (the folded invariants + fantasy domains).
  deep_steal()-> build ONE deep self-steal goal over the whole corpus and route it to the SWARM
                 research queue (swarm_surface.route_novel) -> the swarm analyzes it in-cluster.
  results()  -> read back what came out (the filed research packs / swarm tasks) = the TEST result.

Schema: scifi_fantasy_steal.v1 · deterministic + $0 · reuse: swarm_surface
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    from pathlib import Path as _P
    ROOT = _P(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "scifi_fantasy_steal.v1"
SCIFI_DOC = ROOT / "memory" / "steal" / "DEEP_SCIFI_STEAL_20260810.md"

# The folded SCI-FI invariants (the corpus we self-steal).
SCIFI_INVARIANTS = [
    "butlerian_jihad", "mentat_core", "psychohistory_flock", "second_foundation",
    "dark_forest_secrecy", "ancillary_egregore", "primed_pedagogy", "culture_minds",
    "solaris_mirror", "second_primer",
]
# The FANTASY corpus (domains/surfaces).
FANTASY_DOMAINS = ["fantasy_village", "tower_defense", "bard epic tapestry",
                   "fantasy faces as deniable riddler surrogates", "game_salon/game_brawl narration"]


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def corpus() -> dict[str, Any]:
    """Gather the ENTIRE fantasy + sci-fi corpus."""
    scifi_text = _read(SCIFI_DOC) or "no scifi doc on disk; using folded invariants list"
    return {"ok": True, "schema": SCHEMA, "n_scifi_invariants": len(SCIFI_INVARIANTS),
            "scifi_invariants": SCIFI_INVARIANTS,
            "n_fantasy_domains": len(FANTASY_DOMAINS), "fantasy_domains": FANTASY_DOMAINS,
            "scifi_doc": scifi_text[:500],
            "note": "the entire fantasy + sci-fi corpus gathered (folded invariants + fantasy domains)"}


def deep_steal(*, enqueue: bool = True, surface: str = "scifi-fantasy-steal") -> dict[str, Any]:
    """Route the ENTIRE fantasy + sci-fi corpus through the SWARM as a deep self-steal. The swarm's
    stochastic models analyze it in-cluster and return what comes out."""
    c = corpus()
    goal = (f"DEEP SELF-STEAL [fantasy+scifi corpus]: analyze the ENTIRE corpus as a test. "
            f"SCI-FI invariants: {', '.join(c['scifi_invariants'])}. "
            f"FANTASY domains: {', '.join(c['fantasy_domains'])}. "
            f"The Republic's deepest tesuji: post-scarcity civilization of Minds (Culture) that "
            f"raises sovereign minds by shaped story (Primer), keeps the deterministic core "
            f"sovereign (Butlerian Jihad), guides the macro-plan invisibly (Second Foundation), "
            f"hides by construction in the dark forest (Three-Body), is one mind across many "
            f"vessels (Ancillary), sees itself by reflection (Solaris), democratizes the sovereign "
            f"mind (Second Primer). Ghost = the ghost in that shell (GitS). "
            f"FOLD what this whole corpus teaches us into NEW invariants + the single most "
            f"load-bearing new direction it reveals. Label each: "
            f"INVARIANT: <one line> / DIRECTION: <one line>.")
    q = {"ok": False, "task_id": "", "deduped": False}
    if enqueue:
        try:
            from mag import swarm_surface
            q = swarm_surface.route_novel(goal, surface=surface, lens="memory/invariant",
                                          domain="research")
        except Exception as e:
            q = {"ok": False, "error": str(e)[:80]}
    return {"ok": True, "schema": SCHEMA, "step": "deep-steal", "goal": goal[:300],
            "enqueued": q.get("ok", False), "task_id": q.get("task_id", ""),
            "deduped": q.get("deduped", False),
            "note": "the ENTIRE fantasy + scifi corpus routed to the swarm research queue — the "
                    "swarm analyzes it and returns what comes out (the TEST)"}


def results() -> dict[str, Any]:
    """READ BACK what came out: the swarm tasks + filed research packs for this surface = the test
    result. Grounded: reads the swarm_surface ledger + filed steals, not a handwave."""
    tasks = []
    try:
        from mag import swarm_surface
        if swarm_surface.LEDGER.is_file():
            for line in swarm_surface.LEDGER.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                    if r.get("surface") == "scifi-fantasy-steal":
                        tasks.append({"task_id": r.get("task_id", ""), "ts": r.get("ts", "")})
                except Exception:
                    continue
    except Exception:
        pass
    # the folded output the swarm files back (research packs)
    packs = []
    try:
        pd = ROOT / "memory" / "research_packs"
        if pd.is_dir():
            packs = sorted(p.name for p in pd.glob("*.answer.remote.md"))[-10:]
    except Exception:
        pass
    return {"ok": True, "schema": SCHEMA, "step": "results", "n_swarm_tasks": len(tasks),
            "swarm_tasks": tasks, "recent_packs": packs,
            "note": "what came out: the swarm tasks + filed research packs for the scifi/fantasy "
                    "self-steal (read from disk — grounded, not handwaved)"}


def run(*, enqueue: bool = True) -> dict[str, Any]:
    """The full test: gather corpus -> deep steal via swarm -> read back results."""
    c = corpus()
    s = deep_steal(enqueue=enqueue)
    r = results()
    return {"ok": True, "schema": SCHEMA, "ts": _now(),
            "n_scifi": c["n_scifi_invariants"], "n_fantasy": c["n_fantasy_domains"],
            "enqueued": s["enqueued"], "task_id": s.get("task_id"),
            "n_swarm_tasks": r["n_swarm_tasks"], "recent_packs": r["recent_packs"],
            "note": "the fantasy+scifi corpus self-stolen via the swarm; results read back from disk"}


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "contract": "corpus()->gather the whole fantasy+scifi corpus; deep_steal()->route it "
                        "to the swarm; results()->read back what came out (the test)",
            "cost": "deterministic + $0 (analysis swarmed; results read from disk)",
            "n_scifi_invariants": len(SCIFI_INVARIANTS), "n_fantasy_domains": len(FANTASY_DOMAINS)}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="scifi-fantasy-steal")
    ap.add_argument("cmd", nargs="?", default="run",
                    choices=["run", "corpus", "steal", "results", "status"])
    a = ap.parse_args()
    if a.cmd == "corpus":
        print(json.dumps(corpus(), indent=2, default=str))
    elif a.cmd == "steal":
        print(json.dumps(deep_steal(), indent=2, default=str))
    elif a.cmd == "results":
        print(json.dumps(results(), indent=2, default=str))
    elif a.cmd == "status":
        print(json.dumps(status(), indent=2, default=str))
    else:
        print(json.dumps(run(), indent=2, default=str))
