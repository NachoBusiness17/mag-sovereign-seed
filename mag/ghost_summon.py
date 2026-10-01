"""ghost_summon — summon @ghost with the current session so it figures out intent.

Instead of blindly re-running old processes (stale queue tasks, old steers, superseded
next_moves), ghost reasons about what the OPERATOR actually wants by checking candidate
work against three layers:

  * CURRENT  state  — what is active right now (ghost.sense + sense_session)
  * FUTURE   state  — what is planned / next (agent_state next_moves, orphans, idea_graph
                      open_loops, roadmap gates)
  * COLDEST  VERTICES — the core / least-attended nodes that are being neglected
                      (idea_graph nodes with fewest connections + oldest touch; residual /
                      card / tip staleness; CORE_INVARIANTS)

and explicitly separates:

  * STALE_SKIP — candidates we should NOT re-run (agent_state do_not_redesign, old
                 orphan intents, terminal queue tasks, superseded moves).

Deterministic gather by default ($0, no LLM). `reason=True` optionally calls a model to
articulate the intent in the operator's words (bytes not vibes: the gather is the truth,
the model just narrates it).

Schema: ghost_summon.v1

CLI:  python -m mag.ghost_summon [context] [--reason]
REST: POST /api/v1/ghost/summon   {context, reason}
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCHEMA = "ghost_summon.v1"
STALE_ORPHAN_DAYS = 3.0
COLDEST_LIMIT = 5


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load_json(rel: str) -> dict[str, Any]:
    fp = ROOT / rel
    if not fp.is_file():
        return {}
    try:
        return json.loads(fp.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}


def _load_jsonl(rel: str, tail: int = 0) -> list[dict[str, Any]]:
    fp = ROOT / rel
    if not fp.is_file():
        return []
    rows: list[dict[str, Any]] = []
    with open(fp, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    if tail and tail > 0:
        return rows[-tail:]
    return rows


# ---------------------------------------------------------------------------
# CURRENT
# ---------------------------------------------------------------------------

def current_state() -> dict[str, Any]:
    """Active state right now: ghost.sense() + session/context aware layers."""
    out: dict[str, Any] = {"ok": False, "error": None}
    try:
        from mag.ghost import sense, sense_session
        s = sense()
        out["sense"] = {
            k: s.get(k) for k in (
                "fkb_signals", "fkb_signal_count", "spider_signals", "spider_blind",
                "verkle_tip_stale", "inbox_pending", "training_rows", "recent_steers",
                "frustration_total", "frustration_signals",
            ) if k in s
        }
        out["sense"]["leak"] = {k: s.get(k) for k in (
            "leak_canary_breaches", "leak_entropy_anomalies", "leak_burst_signals",
            "leak_collusion_patterns", "leak_summary",
        ) if k in s}
        try:
            sess = sense_session()
            out["session"] = {
                k: sess.get(k) for k in (
                    "goal", "status", "tier", "step", "agent_state_label",
                    "agent_state_next_moves", "agent_state_do_not_redesign",
                    "session_status", "keywords",
                ) if k in sess
            }
        except Exception as e:
            out["session_error"] = str(e)[:160]
        out["ok"] = True
    except Exception as e:
        out["error"] = str(e)[:200]
    return out


# ---------------------------------------------------------------------------
# FUTURE
# ---------------------------------------------------------------------------

def future_state() -> dict[str, Any]:
    """Planned / next work: agent_state next_moves, orphans, idea_graph open_loops,
    roadmap gates, queued-but-running work."""
    out: dict[str, Any] = {"next_moves": [], "do_not_redesign": [], "orphans": [],
                           "open_loops": [], "roadmap_gates": [], "queue": {}}

    # agent_state next_moves + do_not_redesign
    as_ = _load_json("memory/agent_state/LATEST.json")
    out["next_moves"] = list(as_.get("next_moves") or [])
    out["do_not_redesign"] = list(as_.get("do_not_redesign") or [])

    # orphan open intents
    for o in _load_jsonl("memory/ideas/orphans.jsonl"):
        status = str(o.get("status") or "open").lower()
        if status not in ("done", "resolved", "closed"):
            out["orphans"].append({
                "id": o.get("id"), "intent": o.get("intent"),
                "source": o.get("source"), "first_seen": o.get("first_seen"),
            })

    # idea_graph open loops
    for n in _load_jsonl("memory/ideas/nodes.jsonl"):
        if str(n.get("type", "")).lower() == "open_loop" and str(n.get("status", "")).lower() == "open":
            out["open_loops"].append({
                "id": n.get("id"), "title": n.get("title"),
                "body": (n.get("body") or "")[:140],
            })

    # roadmap gates (best-effort)
    try:
        import yaml  # type: ignore
        rp = ROOT / "configs" / "version_roadmap.yaml"
        if rp.is_file():
            rd = yaml.safe_load(rp.read_text(encoding="utf-8", errors="replace")) or {}
            gates = rd.get("gates") or rd.get("versions") or rd.get("roadmap") or {}
            out["roadmap_gates"] = list(gates)[:12]
    except Exception:
        pass

    return out


# ---------------------------------------------------------------------------
# COLDEST VERTICES
# ---------------------------------------------------------------------------

def _node_degree() -> dict[str, int]:
    deg: dict[str, int] = defaultdict(int)
    for e in _load_jsonl("memory/ideas/edges.jsonl"):
        src = e.get("src"); dst = e.get("dst")
        if src:
            deg[src] += 1
        if dst:
            deg[dst] += 1
    return deg


def coldest_vertices(limit: int = COLDEST_LIMIT) -> list[dict[str, Any]]:
    """Rank the least-attended graph nodes: open nodes with fewest connections (oldest
    first). 'Coldest vertex' = the core / open node being neglected."""
    deg = _node_degree()
    open_nodes: list[tuple[int, int, dict[str, Any]]] = []
    for i, n in enumerate(_load_jsonl("memory/ideas/nodes.jsonl")):
        if str(n.get("status", "")).lower() != "open":
            continue
        d = deg.get(n.get("id") or "", 0)
        # coldest = low degree first, then oldest (earliest in file) first
        open_nodes.append((d, i, n))
    open_nodes.sort(key=lambda t: (t[0], t[1]))
    return [{
        "id": n.get("id"), "type": n.get("type"), "title": n.get("title"),
        "degree": d, "body": (n.get("body") or "")[:120],
    } for d, _i, n in open_nodes[:limit]]


def core_invariants_status() -> dict[str, Any]:
    """Report the coldest core invariants + residual/tip staleness."""
    from mag.registry import CORE_INVARIANTS  # type: ignore
    rb = ROOT / "memory" / "biography" / "residual"
    import time as _t
    residual_age_s = None
    if rb.is_dir():
        files = sorted(rb.glob("*.json"), key=lambda p: p.stat().st_mtime)
        if files:
            residual_age_s = round(_t.time() - files[-1].stat().st_mtime)
    tip = _load_json("memory/biography/verkle_tip.json")
    return {
        "invariants": list(CORE_INVARIANTS),
        "newest_residual_age_s": residual_age_s,
        "verkle_tip_present": bool(tip),
        "verkle_tip_stale": bool(tip.get("stale")) if tip else None,
    }


# ---------------------------------------------------------------------------
# STALE SKIP — what NOT to re-run
# ---------------------------------------------------------------------------

def stale_skip() -> dict[str, Any]:
    """Candidates to STOP re-running: do_not_redesign, old orphan intents, terminal queue."""
    from datetime import datetime, timezone
    do_not = list(_load_json("memory/agent_state/LATEST.json").get("do_not_redesign") or [])

    old_orphans: list[dict[str, Any]] = []
    for o in _load_jsonl("memory/ideas/orphans.jsonl"):
        status = str(o.get("status") or "open").lower()
        if status in ("done", "resolved", "closed"):
            continue
        fs = o.get("first_seen") or ""
        try:
            age_d = (datetime.now(timezone.utc) - datetime.fromisoformat(fs.replace("Z", "+00:00"))).total_seconds() / 86400.0
        except Exception:
            age_d = 0.0
        if age_d >= STALE_ORPHAN_DAYS:
            old_orphans.append({"id": o.get("id"), "intent": o.get("intent"), "age_days": round(age_d, 1)})

    return {
        "do_not_redesign": do_not,
        "stale_orphans": old_orphans,
        "note": "These are NOT re-run by the summon. They are either explicitly deprioritized "
                "(do_not_redesign), superseded, or stale beyond the threshold.",
    }


# ---------------------------------------------------------------------------
# SUMMON
# ---------------------------------------------------------------------------

def gather(context: str = "") -> dict[str, Any]:
    """Assemble the three layers + stale_skip (deterministic, $0)."""
    return {
        "context": (context or "").strip()[:2000],
        "current": current_state(),
        "future": future_state(),
        "coldest_vertices": coldest_vertices(),
        "core_invariants": core_invariants_status(),
        "stale_skip": stale_skip(),
    }


def _intent_brief(g: dict[str, Any]) -> str:
    """Deterministic plain-English synthesis of what the operator most likely wants,
    grounded in current + future + coldest, minus stale."""
    lines: list[str] = []
    cur = g.get("current", {})
    fut = g.get("future", {})
    ctx = g.get("context", "")
    if ctx:
        lines.append(f"OPERATOR CONTEXT: {ctx}")
    lines.append("ACTIVE NOW:")
    sense = cur.get("sense", {})
    lines.append(f"  - goal: {cur.get('session', {}).get('goal', '?')}")
    lines.append(f"  - inbox pending: {sense.get('inbox_pending', 0)} · frustration total: {sense.get('frustration_total', 0)}")
    lines.append(f"  - verkle tip stale: {sense.get('verkle_tip_stale')} · leak signals: {sense.get('leak', {}).get('leak_collusion_patterns', 0)}")
    lines.append("PLANNED NEXT (future state):")
    for m in (fut.get("next_moves") or [])[:5]:
        lines.append(f"  - move: {m}")
    for o in (fut.get("orphans") or [])[:5]:
        lines.append(f"  - orphan: {o.get('intent')}")
    lines.append("COLDEST VERTICES (being neglected):")
    for v in (g.get("coldest_vertices") or []):
        lines.append(f"  - [{v.get('degree')} conn] {v.get('title')}")
    inv = g.get("core_invariants", {})
    lines.append(f"CORE INVARIANTS: {', '.join(inv.get('invariants') or [])} (residual age {inv.get('newest_residual_age_s')}s)")
    lines.append("DO NOT RE-RUN (stale / deprioritized):")
    for d in (g.get("stale_skip", {}).get("do_not_redesign") or []):
        lines.append(f"  - (deprioritized) {d}")
    for so in (g.get("stale_skip", {}).get("stale_orphans") or [])[:5]:
        lines.append(f"  - (stale {so.get('age_days')}d) {so.get('intent')}")
    return "\n".join(lines)


def summon(context: str = "", *, reason: bool = False, model: str | None = None) -> dict[str, Any]:
    """Summon ghost with the current session. Deterministic intent by default; `reason=True`
    narrates the intent via a model call (optional, not required)."""
    g = gather(context)
    brief = _intent_brief(g)
    out: dict[str, Any] = {
        "schema": SCHEMA,
        "ts": _now(),
        "ok": True,
        "deterministic": True,
        "brief": brief,
        **g,
    }
    if reason:
        try:
            from llm import chat
            narrated = chat(
                "deepseek",
                (
                    "You are Ghost, the sovereign operator's intent-advisor. From the state below, "
                    "figure out the SINGLE most likely thing the operator wants to do next, and the "
                    "top 2 runner-ups. Explicitly say which listed items are STALE and should NOT be "
                    "re-run. Ground every claim in the state. Be terse (<=12 lines)."
                ),
                brief,
                temperature=0.2,
            )
            out["intent"] = narrated
            out["deterministic"] = False
        except Exception as e:
            out["reason_error"] = str(e)[:160]
    return out


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    reason = "--reason" in argv
    model = None
    rest = [a for a in argv if not a.startswith("--")]
    if "--model" in argv:
        i = argv.index("--model")
        if i + 1 < len(argv):
            model = argv[i + 1]
    context = " ".join(rest) if rest else ""
    print(json.dumps(summon(context, reason=reason, model=model), indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
