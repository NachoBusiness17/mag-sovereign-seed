"""agent_behavior — record & save every swarm agent's behavior profile (Frank-Church style).

The operator directive: "i want their behavior profiles recorded and saved like the keyboard
operators is frank church style" — i.e. thorough per-actor surveillance: every agent dispatch is
logged as a saved behavior profile (model, tier, shape, outcome, cache-hit, latency, theme), so the
swarm's behavior is a durable record we can mine, not a transient log.

Self-improve (behavioral loops):
  - Every recorded row feeds one_sizer.record_sizing(...) so REAL swarm behavior (not guesses)
    improves rightsizing: the (agent, domain, shape) -> tier mapping learns from actual outcomes.
  - profile(agent_id) returns the saved record AND runs the Jungian/consent lenses
    (behavioral_lensing.build_profile) so each agent gets an archetypal profile (Frank-Church dossier).
  - The row is also a GA4-style behavioral signal (behavioral_analytics domain) -> swarms iterate.

Schema: agent_behavior.v1 · deterministic $0 · CLI: python -m mag.agent_behavior summary | profile <id>
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

SCHEMA = "agent_behavior.v1"
AGENT_PROFILE = ROOT / "memory" / "behavior" / "agents.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _read(tail: int = 2000) -> list[dict[str, Any]]:
    if not AGENT_PROFILE.is_file():
        return []
    out = []
    for line in AGENT_PROFILE.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except (json.JSONDecodeError, TypeError):
            continue
    return out[-tail:]


def record(*, agent_id: str, domain: str = "general", shape: str = "balanced",
           tier: str = "flash", model: str = "", ok: bool = True,
           cache_hit: bool | None = None, tokens: int | None = None,
           latency_ms: int | None = None, theme: str = "", source: str = "swarm") -> dict[str, Any]:
    """Log one agent dispatch as a saved behavior profile + feed rightsizing (self-improve)."""
    AGENT_PROFILE.parent.mkdir(parents=True, exist_ok=True)
    row = {"schema": SCHEMA, "ts": _now(), "agent_id": (agent_id or "?"),
           "domain": (domain or "general"), "shape": (shape or "balanced"),
           "tier": (tier or "flash"), "model": model or "", "ok": bool(ok),
           "cache_hit": cache_hit, "tokens": tokens, "latency_ms": latency_ms,
           "theme": theme or "", "source": source or "swarm"}
    try:
        with AGENT_PROFILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass
    # self-improve: real swarm behavior -> rightsizing store
    try:
        from mag.one_sizer import record_sizing
        record_sizing(skill=agent_id[:40], domain=domain or "general", shape=shape or "balanced",
                      effective_tier=tier or "flash", model=model or "", ok=bool(ok))
    except Exception:
        pass
    return {"ok": True, "schema": SCHEMA, "row": row}


def profile(agent_id: str) -> dict[str, Any]:
    """Frank-Church dossier: every saved row for this agent + the Jungian/consent lens profile."""
    rows = [r for r in _read() if str(r.get("agent_id")) == agent_id]
    dossier = {
        "agent_id": agent_id,
        "schema": SCHEMA,
        "n_dispatches": len(rows),
        "last": rows[-1] if rows else None,
        "saved": f"{AGENT_PROFILE}",
    }
    if not rows:
        dossier["note"] = "no saved behavior for this agent yet"
        return dossier
    ok = sum(1 for r in rows if r.get("ok"))
    tiers = {}
    for r in rows:
        tiers[str(r.get("tier"))] = tiers.get(str(r.get("tier")), 0) + 1
    dossier.update({
        "ok_rate": round(ok / len(rows), 3),
        "tiers": tiers,
        "cache_hit_rate": round(
            sum(1 for r in rows if r.get("cache_hit") is True) / max(1, len(rows)), 3),
        "avg_latency_ms": round(
            sum(r.get("latency_ms") or 0 for r in rows) / max(1, len(rows)), 1),
    })
    try:  # the archetypal lens (Frank-Church-style behavioral profiling)
        from mag.behavioral_lensing import BehavioralLenser
        lenser = BehavioralLenser()
        lp = lenser.build_profile(agent_id, rows)
        dossier["lens"] = {"dominant_archetype": getattr(lp, "dominant_archetype", None),
                           "shadow_archetype": getattr(lp, "shadow_archetype", None),
                           "alignment_to_zeitgeist": getattr(lp, "alignment_to_zeitgeist", None),
                           "efficiency_trap": getattr(lp, "efficiency_trap", None),
                           "journey_stage": getattr(lp, "journey_stage", None)}
    except Exception as e:
        dossier["lens"] = {"error": str(e)[:80]}
    return dossier


def summary() -> dict[str, Any]:
    rows = _read()
    if not rows:
        return {"ok": True, "schema": SCHEMA, "dispatches": 0, "note": "no agent behavior recorded yet"}
    agents = sorted({str(r.get("agent_id")) for r in rows})
    tiers = {}
    ok = 0
    for r in rows:
        tiers[str(r.get("tier"))] = tiers.get(str(r.get("tier")), 0) + 1
        ok += 1 if r.get("ok") else 0
    return {"ok": True, "schema": SCHEMA, "dispatches": len(rows),
            "agents": len(agents), "ok_rate": round(ok / len(rows), 3),
            "tiers": tiers, "saved": str(AGENT_PROFILE)}


def main(argv: list[str] | None = None) -> int:
    import argparse, sys as _sys
    p = argparse.ArgumentParser(prog="agent_behavior")
    sub = p.add_subparsers(dest="cmd")
    sub.add_parser("summary")
    prof = sub.add_parser("profile"); prof.add_argument("agent_id")
    a = p.parse_args(argv)
    print(json.dumps(summary() if a.cmd != "profile" else profile(a.agent_id),
                     indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
