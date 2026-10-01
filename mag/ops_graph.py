"""Ops knowledge graph — categorize live operational telemetry into a typed graph.

Categorizes the "crazy amount of data" the framework produces (ghost awareness,
autorun/governor, drainer/queue, behavioral events, skill ledger, verkle) into a
small, typed, visualizable knowledge graph: subsystem / provider / run / signal /
metric nodes joined by typed edges.

Store: memory/graph/nodes.jsonl + edges.jsonl   (schema: ops_graph.v1)
The store is a durable record; render() always recomputes a LIVE snapshot from
the same sources so the visualization never goes stale.

Law: files are truth; reuses the framework's own modules (no reinvention);
never routes or mutates — it only reads telemetry and categorizes.

CLI:
  python -m mag.ops_graph               # render live snapshot as a small table
  python -m mag.ops_graph --json        # machine-readable graph payload
  python -m mag.ops_graph --ingest      # also append nodes/edges to the durable store

REST (dashboard/rest.py):
  GET /api/v1/graph/ops  -> render() payload for the VS Code graph webview
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except ImportError:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCHEMA = "ops_graph.v1"
GRAPH_DIR = ROOT / "memory" / "graph"
NODES_PATH = GRAPH_DIR / "nodes.jsonl"
EDGES_PATH = GRAPH_DIR / "edges.jsonl"

# Category -> presentation (label + css color the webview maps)
CATEGORIES = {
    "run":        {"label": "Run",        "color": "#58a6ff"},
    "subsystem":  {"label": "Subsystem",  "color": "#3fb950"},
    "provider":   {"label": "Provider",   "color": "#a371f7"},
    "signal":     {"label": "Signal",     "color": "#d29922"},
    "metric":     {"label": "Metric",     "color": "#e3b341"},
    "operator":   {"label": "Operator",   "color": "#f78166"},
}

EDGE_TYPES = {
    "participates_in": "#3fb950",
    "serves":          "#a371f7",
    "about":           "#d29922",
    "tracks":          "#e3b341",
    "supervises":      "#f78166",
    "paused_by":       "#f85149",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_jsonl(path: Path, tail: int = 0) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    if tail:
        lines = lines[-tail:]
    out: list[dict[str, Any]] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            o = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(o, dict):
            out.append(o)
    return out


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8")) or {}
    except (json.JSONDecodeError, OSError):
        return {}


# ====================================================================
# COLLECT — pull raw telemetry from every live source
# ====================================================================
def collect() -> dict[str, Any]:
    data: dict[str, Any] = {"ts": _now()}

    # Ghost awareness (autonomy run, operator, VS Code session)
    try:
        from mag.ghost import sense_context
        data["context"] = sense_context()
    except Exception as e:
        data["context"] = {"error": str(e)[:120]}

    # Governor autorun trail (phase + freshness)
    try:
        trail = _read_jsonl(ROOT / "memory" / "runs" / "governor_autorun_trail.jsonl", tail=8)
        data["autorun_trail"] = trail
        last = trail[-1] if trail else {}
        data["autorun_last"] = {
            "ts": last.get("ts", ""),
            "phase": last.get("phase") or last.get("action") or "?",
            "queued_n": last.get("queued_n"),
        }
    except Exception as e:
        data["autorun_trail"] = []
        data["autorun_last"] = {"error": str(e)[:120]}

    # Ghost trail (deploys / suppressed)
    try:
        ghost = _read_jsonl(ROOT / "memory" / "runs" / "ghost" / "trail.jsonl", tail=5)
        data["ghost_trail"] = ghost
        last_g = ghost[-1] if ghost else {}
        data["ghost_last"] = {
            "ts": last_g.get("ts", ""),
            "outcome": last_g.get("outcome", "?"),
            "auto_deploy": last_g.get("auto_deploy", "?"),
            "text": (last_g.get("text_preview", "") or "")[:100],
        }
    except Exception as e:
        data["ghost_trail"] = []
        data["ghost_last"] = {"error": str(e)[:120]}

    # Drainer / operator / budget
    try:
        from mag.preferences import drainer_status, operator_status
        data["drainer"] = drainer_status()
        data["operator"] = operator_status()
    except Exception as e:
        data["drainer"] = {"error": str(e)[:120]}
        data["operator"] = {}

    # Queue
    try:
        from mag.orchestrator import queue_status
        qs = queue_status()
        data["queue"] = {
            "total": qs.get("total"),
            "counts": qs.get("counts"),
            "running_task_id": qs.get("running_task_id"),
        }
    except Exception as e:
        data["queue"] = {"error": str(e)[:120]}

    # Behavioral events
    try:
        events = _read_jsonl(ROOT / "logs" / "behavioral_events.jsonl", tail=8)
        data["behavioral_events"] = events
    except Exception:
        data["behavioral_events"] = []

    # Skill ledger
    try:
        ledger = _read_jsonl(ROOT / "memory" / "improve" / "skill_ledger.jsonl", tail=1)
        data["skill_ledger_last"] = ledger[-1] if ledger else {}
        from mag.skill_ledger import progress
        try:
            data["skill_ledger_progress"] = progress()
        except Exception:
            data["skill_ledger_progress"] = {}
    except Exception as e:
        data["skill_ledger_last"] = {}
        data["skill_ledger_progress"] = {"error": str(e)[:120]}

    # Verkle tip staleness
    try:
        from mag.ghost import sense
        s = sense()
        data["verkle_tip_stale"] = bool(s.get("verkle_tip_stale"))
        data["spider_blind"] = bool(s.get("spider_blind"))
        data["frustration_total"] = s.get("frustration_total", 0)
        data["training_rows"] = s.get("training_rows", 0)
    except Exception as e:
        data["verkle_tip_stale"] = False
        data["spider_blind"] = False
        data["frustration_total"] = 0
        data["training_rows"] = 0
        data["sense_error"] = str(e)[:120]

    # Orphan timer — undone-yet-intended intents
    try:
        from mag.orphan_timer import list_open
        data["orphans"] = list_open()
    except Exception:
        data["orphans"] = []

    # Janitor last report
    try:
        from mag.janitor import last_report
        data["janitor_last"] = last_report()
    except Exception:
        data["janitor_last"] = {}

    # Failure KB stats (doctor)
    try:
        from mag.failure_kb import stats as fkb_stats
        data["fkb"] = fkb_stats()
    except Exception:
        data["fkb"] = {}

    # Provider budgets — DeepSeek spend visibility (wise use)
    try:
        from models.quota import provider_budget
        from models.providers import list_provider_ids
        budgets: dict[str, Any] = {}
        for pid in list_provider_ids()[:8]:
            try:
                b = provider_budget(pid)
                if b.get("configured"):
                    budgets[pid] = {
                        "budget_ok": bool(b.get("budget_ok")),
                        "used_calls": b.get("used_calls"),
                        "remaining_calls": b.get("remaining_calls"),
                        "remaining_tokens": b.get("remaining_tokens"),
                    }
            except Exception:
                continue
        data["budgets"] = budgets
    except Exception:
        data["budgets"] = {}

    return data


# ====================================================================
# CATEGORIZE — build typed nodes + edges from collected telemetry
# ====================================================================
def categorize(data: dict[str, Any] | None = None) -> dict[str, Any]:
    data = data or collect()
    ctx = data.get("context", {})
    unattended = bool(ctx.get("unattended_autonomy_run"))
    op_active = bool((ctx.get("operator") or {}).get("active"))
    autorun_loop = bool(ctx.get("autorun_loop"))

    drainer = data.get("drainer", {})
    drainer_enabled = bool(drainer.get("enabled") or drainer.get("autorun_allowed"))
    queue = data.get("queue", {})
    q_counts = queue.get("counts") or {}
    ledger_prog = data.get("skill_ledger_progress") or {}

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    def N(nid: str, label: str, category: str, status: str = "live",
          meta: dict[str, Any] | None = None) -> None:
        nodes.append({
            "id": nid, "label": label, "category": category,
            "status": status, "meta": meta or {},
        })
    def E(src: str, dst: str, etype: str, label: str = "") -> None:
        edges.append({"src": src, "dst": dst, "type": etype, "label": label})

    # ── Run ──
    run_status = "unattended" if unattended else ("paused" if op_active else ("active" if autorun_loop else "idle"))
    N("run:current", "Autonomy Run", "run", run_status, {
        "autorun_loop": autorun_loop,
        "phase": (ctx.get("autorun_last_phase") or data.get("autorun_last", {}).get("phase") or "?"),
    })

    # ── Subsystems ──
    N("sub:autorun", "Autorun / Governor", "subsystem",
      "running" if autorun_loop else "idle")
    N("sub:drainer", "Drainer", "subsystem",
      "on" if drainer_enabled else "off")
    N("sub:ghost", "Ghost", "subsystem", "live", {
        "last": (data.get("ghost_last", {}) or {}).get("outcome", "?"),
        "auto_deploy": (data.get("ghost_last", {}) or {}).get("auto_deploy", "?"),
    })
    N("sub:orchestrator", "Orchestrator / Queue", "subsystem", "live", {
        "total": queue.get("total"),
        "running": q_counts.get("running", 0),
    })
    N("sub:behavioral", "Behavioral Loop", "subsystem", "live", {
        "events": len(data.get("behavioral_events", [])),
    })
    N("sub:skill_ledger", "Skill Ledger", "subsystem", "live", {
        "decisions": ledger_prog.get("decisions", ledger_prog.get("decisions_n")),
        "rows": ledger_prog.get("labeled_rows"),
    })
    N("sub:verkle", "Verkle Chain", "subsystem",
      "stale" if data.get("verkle_tip_stale") else "honest")
    N("sub:operator", "Operator", "operator",
      "active" if op_active else "away")

    # ── Automation subsystems (the self-maintaining surface) ──
    jan_last = data.get("janitor_last") or {}
    N("sub:janitor", "Janitor", "subsystem", "live", {
        "last_action": jan_last.get("action", "?"),
        "last_pruned": (jan_last.get("prune") or {}).get("n_removed", 0),
    })
    E("sub:janitor", "run:current", "participates_in")

    orphans = data.get("orphans") or []
    N("sub:orphan", "Orphan Timer", "subsystem", "live", {"open": len(orphans)})
    E("sub:orphan", "run:current", "participates_in")

    fkb = data.get("fkb") or {}
    N("sub:doctor", "Doctor (FKB)", "subsystem", "live", {
        "events": fkb.get("events_logged", fkb.get("count", 0)),
        "signatures": fkb.get("signatures", 0),
        "recurring": fkb.get("recurring", 0),
    })
    E("sub:doctor", "run:current", "participates_in")

    # ── Providers ──
    N("prov:deepseek", "DeepSeek", "provider", "primary")
    N("prov:ollama", "Ollama (local)", "provider", "local")
    N("prov:grok", "Grok", "provider", "low-budget")

    # ── Signals ──
    if unattended:
        N("sig:unattended", "Unattended autonomy run", "signal", "live",
          {"hint": "drainer draining with operator away"})
        E("sig:unattended", "run:current", "about")
    if data.get("spider_blind"):
        N("sig:spider", "Spider blind", "signal", "warn")
        E("sig:spider", "sub:behavioral", "about")
    if data.get("verkle_tip_stale"):
        N("sig:verkle", "Verkle tip stale", "signal", "warn")
        E("sig:verkle", "sub:verkle", "about")
    if data.get("frustration_total", 0) > 0:
        N("sig:frustration", f"Frustration x{data['frustration_total']}", "signal", "warn")
        E("sig:frustration", "sub:ghost", "about")
    if data.get("training_rows", 0) >= 5:
        N("sig:training", f"Training ready ({data['training_rows']})", "signal", "live")
        E("sig:training", "sub:skill_ledger", "about")

    # ── Orphans (undone-yet-intended intents) ──
    orphans = data.get("orphans") or []
    if orphans:
        n_o = len(orphans)
        N("metric:orphans", f"Orphans {n_o}", "signal" if n_o >= 3 else "metric",
          "warn" if n_o >= 3 else "live",
          {"open": n_o, "oldest": (orphans[0].get("intent") or "")[:60]})
        E("metric:orphans", "sub:ghost", "about")
        E("metric:orphans", "run:current", "about")

    # ── Metrics ──
    N("metric:queue", f"Queue {q_counts.get('done', 0)} done / {queue.get('total', 0)} total",
      "metric", "live", {"counts": q_counts})
    if data.get("training_rows"):
        N("metric:training", f"Training rows {data['training_rows']}", "metric", "live")
        E("metric:training", "sub:skill_ledger", "tracks")

    # ── Edges ──
    E("sub:autorun", "run:current", "participates_in")
    E("sub:drainer", "run:current", "participates_in")
    E("sub:ghost", "run:current", "participates_in")
    E("sub:orchestrator", "run:current", "participates_in")
    E("sub:behavioral", "run:current", "participates_in")
    E("sub:skill_ledger", "run:current", "participates_in")
    E("sub:verkle", "run:current", "participates_in")
    E("prov:deepseek", "sub:drainer", "serves")
    E("prov:ollama", "sub:ghost", "serves")
    E("prov:grok", "sub:drainer", "serves")

    # ── DeepSeek budget (wise spend) ──
    ds = (data.get("budgets") or {}).get("deepseek") or {}
    if ds:
        N("metric:deepseek_budget",
          f"DeepSeek {ds.get('remaining_tokens') or '?'} tok left",
          "metric", "on" if ds.get("budget_ok") else "warn", ds)
        E("metric:deepseek_budget", "prov:deepseek", "tracks")
    E("metric:queue", "sub:orchestrator", "tracks")
    E("sub:operator", "run:current", "paused_by" if op_active else "supervises")

    return {"schema": SCHEMA, "ts": _now(), "nodes": nodes, "edges": edges}


# ====================================================================
# PERSIST + RENDER
# ====================================================================
def persist(graph: dict[str, Any]) -> None:
    GRAPH_DIR.mkdir(parents=True, exist_ok=True)
    with NODES_PATH.open("a", encoding="utf-8") as f:
        for n in graph["nodes"]:
            f.write(json.dumps(n, ensure_ascii=False, default=str) + "\n")
    with EDGES_PATH.open("a", encoding="utf-8") as f:
        for e in graph["edges"]:
            f.write(json.dumps(e, ensure_ascii=False, default=str) + "\n")


def render(ingest: bool = False) -> dict[str, Any]:
    """Build a live visualization payload (optionally persist a durable copy)."""
    data = collect()
    graph = categorize(data)
    if ingest:
        persist(graph)
    return {
        "ok": True,
        "schema": SCHEMA,
        "ts": graph["ts"],
        "categories": CATEGORIES,
        "edge_types": EDGE_TYPES,
        "nodes": graph["nodes"],
        "edges": graph["edges"],
        "raw": {k: v for k, v in data.items() if k not in ("context", "autorun_trail", "ghost_trail", "behavioral_events")},
    }


# ====================================================================
# CLI
# ====================================================================
def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Ops knowledge graph — categorize + render live telemetry")
    ap.add_argument("--json", action="store_true", help="Machine-readable graph payload")
    ap.add_argument("--ingest", action="store_true", help="Also append nodes/edges to the durable store")
    args = ap.parse_args(argv)

    if args.json:
        print(json.dumps(render(ingest=args.ingest), indent=2, ensure_ascii=False, default=str))
        return 0

    g = render(ingest=args.ingest)
    print(f"OPS GRAPH  {g['ts']}")
    print(f"{'id':<18} {'category':<10} {'status':<12} label")
    print("-" * 80)
    for n in g["nodes"]:
        print(f"{n['id']:<18} {n['category']:<10} {n['status']:<12} {n['label']}")
    print("-" * 80)
    print(f"{len(g['nodes'])} nodes · {len(g['edges'])} edges · {len(g['categories'])} categories")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
