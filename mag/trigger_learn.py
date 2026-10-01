"""trigger_learn — automatically LEARN when to trigger each lens / dashboard surface from user
signals, then publish the decision to the shared cast surface so the dashboard reacts by itself.

Operator (2026-08-11): "we also need to know when to trigger all of these based off user signals
automatically learned. within the shared surface."

THE LEARNED TRIGGER LOOP (deterministic + $0):
  user signal (behavioral event, training row, percolator novel/fp, steer, inbox) ->
  mapped to a lens + a surface (flock/world/emerge/steal-lens/...)
  -> confidence rises with repetition (learned, not hardcoded) ->
  decide() returns active triggers for the SHARED surface, so the dashboard fires the view.

Signal -> lens/surface mapping is LEARNED: we keep a count per (signal_kind -> lens); the more a
signal kind co-occurs with a lens being useful, the higher its weight. Deterministic, no LLM.

Schema: trigger_learn.v1 · deterministic + $0 · reuse: operator_inbox, percolator, novelty_lens,
invariant_ledger, cast/rib_bus
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "trigger_learn.v1"
MAP_PATH = ROOT / "memory" / "trigger_learn" / "map.json"
EVENTS_PATH = ROOT / "memory" / "behavioral_events.jsonl"
TRAINING_PATH = ROOT / "memory" / "pile" / "training_rows.jsonl"
STEER_PATH = ROOT / "memory" / "steer_telemetry.jsonl"
INBOX_PATH = ROOT / "memory" / "operator_inbox.json"
LOG_PATH = ROOT / "memory" / "trigger_learn" / "decisions.jsonl"

# Seed: which signal kinds imply which lens/surface (prior, then LEARNED upward from repetition).
SEED: dict[str, list[str]] = {
    "collapse":        ["emerge", "world"],
    "degenerate":      ["emerge", "world"],
    "tool_fail":       ["world", "emerge"],
    "seat_crash":      ["emerge", "flock"],
    "training":        ["steal-lens", "world"],
    "novel":           ["steal-lens", "world"],
    "false_positive":  ["steal-lens", "emerge"],
    "steer_accepted":  ["flock", "world"],
    "steer_override":  ["world", "emerge"],
    "cost_spike":      ["emerge", "world"],
    "usage_spike":     ["emerge"],
    "inbox_pending":   ["world"],
    "gap":             ["steal-lens", "world"],
    "probe":           ["world", "emerge"],
    "gpu_free":        ["flock", "world"],
    "correction_recurrence": ["world", "emerge"],  # 2026-08-12: recurrence_gate surfaces re-corrections
    "billing_gate":    ["emerge", "world"],        # 2026-08-12: bill drift is a gate, not a footnote
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load_map() -> dict[str, Any]:
    if MAP_PATH.is_file():
        try:
            return json.loads(MAP_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"weights": {k: {"count": 0, "lenses": v} for k, v in SEED.items()},
            "total_signals": 0}


def _save_map(m: dict[str, Any]) -> None:
    MAP_PATH.parent.mkdir(parents=True, exist_ok=True)
    MAP_PATH.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_jsonl(p: Path, tail: int = 200) -> list[dict[str, Any]]:
    if not p.is_file():
        return []
    out = []
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines()[-tail:]:
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


def _count_signals() -> dict[str, int]:
    """Count each signal kind from the live surfaces (behavioral events, training, steers, inbox,
    percolator novel/fp, cost/usage spikes)."""
    counts: dict[str, int] = defaultdict(int)
    for ev in _read_jsonl(EVENTS_PATH, tail=500):
        k = ev.get("kind")
        if k:
            counts[k] += 1
    for r in _read_jsonl(TRAINING_PATH, tail=300):
        counts.setdefault("training", 0)
        counts["training"] += 1
    for s in _read_jsonl(STEER_PATH, tail=200):
        st = s.get("status")
        if st == "accepted":
            counts["steer_accepted"] += 1
        elif st == "overridden":
            counts["steer_override"] += 1
    try:
        percolator_dir = ROOT / "memory" / "percolator"
        if (percolator_dir / "explore.jsonl").is_file():
            counts["novel"] += sum(1 for _ in (percolator_dir / "explore.jsonl").read_text(
                encoding="utf-8", errors="replace").splitlines() if _.strip())
        for fp in percolator_dir.glob("*.fp.jsonl"):
            counts["false_positive"] += sum(1 for _ in fp.read_text(
                encoding="utf-8", errors="replace").splitlines() if _.strip())
    except Exception:
        pass
    try:
        from mag import usage_monitor
        counts["usage_spike"] += len(usage_monitor.watch(_read_jsonl(
            ROOT / "logs" / "provider_usage.jsonl", tail=500), window=6).get("spikes", []))
    except Exception:
        pass
    # inbox pending counts as a pull-signal to the world lens
    try:
        inbox = json.loads(INBOX_PATH.read_text(encoding="utf-8")) if INBOX_PATH.is_file() else {}
        pending = sum(1 for i in inbox.get("committed", []) if i.get("status") == "pending")
        if pending:
            counts["inbox_pending"] += pending
    except Exception:
        pass
    # gpu-free from gpu_lifecycle (when GPU is idle we should render)
    try:
        from mag import gpu_lifecycle
        if gpu_lifecycle.resources().get("free_for_render"):
            counts["gpu_free"] += 1
    except Exception:
        pass
    return dict(counts)


def learn() -> dict[str, Any]:
    """Fold live signal counts into the learned map: each signal occurrence strengthens the lenses
    it maps to. Deterministic — no LLM."""
    m = _load_map()
    sigs = _count_signals()
    for kind, n in sigs.items():
        if kind not in m["weights"]:
            m["weights"][kind] = {"count": 0, "lenses": SEED.get(kind, [])}
        m["weights"][kind]["count"] += n
    m["total_signals"] = m.get("total_signals", 0) + sum(sigs.values())
    _save_map(m)
    return {"ok": True, "schema": SCHEMA, "signals": sigs,
            "total_signals": m["total_signals"], "weights": m["weights"]}


def decide() -> dict[str, Any]:
    """The SHARED-SURFACE trigger decision: which lenses/surfaces to fire NOW, with confidence and
    the signal evidence behind each. Confidence = learned weight (count) normalized; also report the
    top signal kind driving each trigger.

    OUTLIER FIX (2026-08-11): only emit REAL lenses (the ones signals actually map to with weight>0).
    The prior loop's `lens_w[kind][1] = kind` created phantom weight-0 lenses (e.g. "training",
    "novel") that polluted the shared cast surface. Dropped.
    """
    m = _load_map()
    sigs = _count_signals()
    # lens -> [weight, evidence[]]  — only lenses that receive signal weight
    lens_w: dict[str, list] = defaultdict(lambda: [0.0, []])
    for kind, n in sigs.items():
        if n <= 0:
            continue
        entry = m["weights"].get(kind, {"count": 0, "lenses": SEED.get(kind, [])})
        for lens in entry.get("lenses", []):
            lens_w[lens][0] += n
            lens_w[lens][1].append(f"{kind}x{n}")
    if not lens_w:
        return {"ok": True, "schema": SCHEMA, "ts": _now(), "triggers": [], "active": [],
                "surface": "shared-cast", "total_signals": m["total_signals"]}
    # pick top signal per lens (the highest-count evidence)
    triggers = []
    for lens, w in lens_w.items():
        ev = w[1]
        top = max(ev, key=lambda e: int(e.split("x")[-1])) if ev else ""
        triggers.append({"lens": lens, "weight": w[0], "confidence": 0.0,
                         "top_signal": top, "evidence": ev[:6]})
    total = sum(t["weight"] for t in triggers) or 1
    for t in triggers:
        t["confidence"] = round(t["weight"] / total, 3)
    triggers.sort(key=lambda t: t["weight"], reverse=True)
    active = [t for t in triggers if t["weight"] > 0]
    return {"ok": True, "schema": SCHEMA, "ts": _now(), "triggers": triggers[:12],
            "active": active[:6], "surface": "shared-cast", "total_signals": m["total_signals"]}


def publish() -> dict[str, Any]:
    """Run learn + decide and write the decision to the shared cast surface (rib_bus) so the
    dashboard consumes it. Deterministic, idempotent."""
    learn()
    d = decide()
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": _now(), "triggers": d.get("triggers", [])},
                               ensure_ascii=False) + "\n")
    except Exception:
        pass
    try:
        from mag import rib_bus
        rib_bus.publish_rib(json.dumps(d), domain="trigger", source="trigger_learn")
    except Exception:
        pass
    return d


def status() -> dict[str, Any]:
    m = _load_map()
    return {"ok": True, "schema": SCHEMA, "map": MAP_PATH.relative_to(ROOT).as_posix(),
            "total_signals": m.get("total_signals", 0),
            "learned": f"signals folded into lens weights; publish() -> shared cast surface"}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="trigger-learn")
    ap.add_argument("cmd", nargs="?", default="decide",
                    choices=["decide", "learn", "publish", "status"])
    a = ap.parse_args()
    if a.cmd == "decide":
        print(json.dumps(decide(), indent=2, default=str))
    elif a.cmd == "learn":
        print(json.dumps(learn(), indent=2, default=str))
    elif a.cmd == "publish":
        print(json.dumps(publish(), indent=2, default=str))
    else:
        print(json.dumps(status(), indent=2, default=str))
