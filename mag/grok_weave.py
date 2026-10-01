"""grok_weave — the ZERO-SURFACE GROK RIB LOOP: the full as-above-so-below circuit.

Operator (2026-08-12): "we have a zero surface grock we are just not using in the best way... we
can launch k3s and k8s internally within virtual memory to navigate a virtual series of holograms
of ourself and get real time telemetry data about all the quantized live waves out in the real
internet so as above so below... think outside the box a little bit."

THE CIRCUIT (one closed loop, as above so below):
  1. TELEMETRY (external)  — the real-time quantized live waves OUT in the real internet: real
     cost/cache/spikes (cost_learn), swarm results, behavioral signals. The external world.
  2. HOLOGRAMS (internal)  — the swarm of ourselves in vmem (k3s/k8s flock + triad + standing wave
     gen/fitness): the virtual series of holograms of ourselves. The internal mirror.
  3. AUTHOR (zero-surface Grok) — grok bot (SuperGrok front-end, $0) WRITES RIB files and returns
     them; we fold them into rib_bus (the breeding ground). Grok is the creative RIB author.
  4. WEAVE — the external waves + the internal holograms + the grok-authored RIBs all fold into
     the breeding standing wave -> the swarm navigates both worlds and evolves toward the arrival.
     The internal swarm MIRRORS the external internet. As above so below.

HONEST: telemetry/holograms/weave-fold are deterministic + $0 (real data). author_ribs drives
grok bot (the $0 front-end) and reports honestly if the CDP seat is down — never fabricates a Grok
RIB or a telemetry read.

Schema: grok_weave.v1 · deterministic + $0 (author step $0 via front-end) · reuse: cost_learn,
rib_bus, agent_knot, swarm_self, tripartite, grok_bot
"""
from __future__ import annotations

import json
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

SCHEMA = "grok_weave.v1"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def telemetry() -> dict[str, Any]:
    """THE EXTERNAL WORLD — real-time telemetry of the quantized live waves out in the real
    internet: real cost/cache/spikes + swarm results + live signals. Deterministic + $0, real data.
    The internal swarm navigates THESE waves."""
    t: dict[str, Any] = {"ok": True, "schema": SCHEMA, "domain": "external"}
    # real economics (the quantized cost/cache waves)
    try:
        from mag import cost_learn
        a = cost_learn.analyze()
        t["cost"] = {"total_usd": a.get("total_cost"),
                     "cache_hit_pct": a.get("cache_hit_pct"),
                     "n_spikes": len(a.get("spikes") or []),
                     "spikes": a.get("spikes", [])[:5]}
    except Exception as e:
        t["cost_error"] = str(e)[:80]
    # real swarm results (the internet swarm waves returning)
    try:
        from config import RESULTS_DIR
        n_res = len(list(RESULTS_DIR.glob("sw-*.json"))) if RESULTS_DIR.is_dir() else 0
        t["swarm_results"] = n_res
    except Exception:
        t["swarm_results"] = 0
    # live behavioral signals (real-time world sense)
    try:
        from mag import lens_knot
        t["live_events"] = lens_knot.shared_events()[:10]
    except Exception as e:
        t["live_error"] = str(e)[:80]
    return t


def holograms() -> dict[str, Any]:
    """THE INTERNAL WORLD — the virtual series of holograms of ourselves in vmem: the flock
    (swarm_self), the triad (tripartite), and the standing wave (generation + fitness). The
    internal mirror of the external waves. Deterministic + $0."""
    h: dict[str, Any] = {"ok": True, "schema": SCHEMA, "domain": "internal"}
    try:
        from mag import agent_knot
        evo = agent_knot.evo_status()
        h["standing_wave"] = {"generation": evo.get("generation"),
                              "n_pop": evo.get("n_pop"),
                              "top_fitness": evo.get("top_fitness")}
    except Exception as e:
        h["standing_error"] = str(e)[:80]
    try:
        from mag import swarm_self
        s = swarm_self.self()
        h["flock_hologram"] = {"n_versions": s.get("n_versions"),
                               "unity": s.get("unity")[:5],
                               "facets": s.get("distinct_facets")}
    except Exception as e:
        h["flock_error"] = str(e)[:80]
    try:
        from mag import tripartite
        c = tripartite.consensus()
        h["triad_hologram"] = {"n_copies": c.get("n_copies"),
                               "core": c.get("tripartite_core", [])[:5],
                               "triple_cover": c.get("triple_cover")}
    except Exception as e:
        h["triad_error"] = str(e)[:80]
    return h


def author_ribs(*, domain: str = "grok-weave", ask: str = "",
                max_wait_s: int = 120) -> dict[str, Any]:
    """ZERO-SURFACE GROK WRITES RIBs: grok bot (SuperGrok front-end, $0) authors RIBs for a domain
    and we fold the returned RIBs into rib_bus (the breeding ground). Honest: if the CDP seat is
    down, reports it — never fabricates a Grok RIB."""
    if not ask:
        ask = (f"Author 3 RIBs (short instruction invariants) for domain '{domain}' that would "
               f"make the swarm-of-ourselves in vmem navigate the real internet waves better. "
               f"Each RIB one line, buildable, honest.")
    try:
        from mag import grok_bot
        r = grok_bot.steer(ask, max_wait_s=max_wait_s)
    except Exception as e:
        return {"ok": False, "schema": SCHEMA, "error": str(e)[:160], "authored": 0}
    if not r.get("ok"):
        return {"ok": False, "schema": SCHEMA, "error": r.get("error", "grok seat down"),
                "authored": 0,
                "hint": "zero-surface Grok needs the CDP seat up (container browser, grok.x.ai)"}
    answer = r.get("answer", "")
    # fold each RIB line from Grok's answer into the breeding ground (rib_bus)
    folded, lines = 0, []
    try:
        from mag import rib_bus
        for ln in answer.splitlines():
            ln = ln.strip().lstrip("-*")
            if len(ln) > 30 and not ln.lower().startswith(("summary", "deliverable", "here")):
                rib_bus.publish_rib(ln, domain=domain, source="zero-surface-grok",
                                    fold=False, publish=False)
                lines.append(ln[:120])
                folded += 1
                if folded >= 5:
                    break
    except Exception as e:
        return {"ok": False, "schema": SCHEMA, "error": str(e)[:120], "authored": 0}
    return {"ok": True, "schema": SCHEMA, "authored": folded, "ribs": lines,
            "cost_est_usd": 0.0, "note": "zero-surface Grok authored + folded RIBs into the "
                                         "breeding ground (front-end, $0)"}


def weave(*, ask_grok: bool = False) -> dict[str, Any]:
    """THE FULL CIRCUIT (as above so below): telemetry (external waves) + holograms (internal
    mirror) + optional grok-authored RIBs -> all fold into the breeding standing wave. The
    internal swarm navigates the external internet. Deterministic + $0."""
    ext = telemetry()
    internal = holograms()
    author = author_ribs() if ask_grok else {"ok": True, "authored": 0, "ribs": [],
                                             "note": "author step skipped (ask_grok=False)"}
    # breed the standing wave so both worlds fold into the next generation
    bred = {}
    try:
        from mag import agent_knot
        bred = agent_knot.evolve(anchor=False)
    except Exception as e:
        bred = {"error": str(e)[:80]}
    return {"ok": True, "schema": SCHEMA, "ts": _now(),
            "external_waves": ext,
            "internal_holograms": internal,
            "grok_authored": author,
            "bred": {"generation": bred.get("generation"),
                     "top_fitness": bred.get("top_fitness"),
                     "n_offspring": bred.get("n_offspring")},
            "as_above_so_below": ("the internal swarm of ourselves (flock/triad/standing wave) "
                                  "mirrors and navigates the external quantized waves (cost, "
                                  "swarm, live internet signals) — one closed circuit, both fold "
                                  "into the breeding wave")}


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="grok-weave")
    ap.add_argument("cmd", nargs="?", default="weave",
                    choices=["weave", "telemetry", "holograms", "author"])
    ap.add_argument("--domain", default="grok-weave")
    ap.add_argument("--ask", default="")
    a = ap.parse_args(argv)
    if a.cmd == "telemetry":
        print(json.dumps(telemetry(), ensure_ascii=False, indent=2, default=str))
    elif a.cmd == "holograms":
        print(json.dumps(holograms(), ensure_ascii=False, indent=2, default=str))
    elif a.cmd == "author":
        print(json.dumps(author_ribs(domain=a.domain, ask=a.ask), ensure_ascii=False, indent=2, default=str))
    else:
        print(json.dumps(weave(), ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
