"""recurrence_gate — GATE the correction-loop (the operator must not have to re-tell us).

Operator (2026-08-12, chord move #1): "gate the correction-loop, don't just log it. when a
training-capture of class X is written, have the loop surface it on the seat and auto-open the
specific guard — so a repeat can't silently cost the operator a third correction."

THE PROBLEM: a law gets written to memory, then the SAME class of error fires next session anyway
(wrong-tool, invented-number, fetch-recurrence, prompt-to-run, window-spawn). The loop writes the
rule; it does not yet GATE the action on the rule.

THE GATE (deterministic + $0):
  1. RECORD — a training capture of a known correction class is written here (record()). Each
     capture is one line: {class, ts, note}.
  2. CHECK  — on every cadence, scan the recent captures (+ behavioral events) for each known
     class. If a class fires >= threshold within a window, that's a RECURRENCE (the operator is
     being asked to re-correct).
  3. SURFACE — on recurrence, emit a behavioral event (kind='correction_recurrence') so
     trigger_learn (already on the cadence) maps it to a surface + auto-opens the specific guard.
     Also emit a training event (pattern='operator_behavior'). The seat sees it; the operator does
     not have to type the correction a third time.

Schema: recurrence_gate.v1 · deterministic + $0 · reuse: trigger_learn (shared cast surface),
training_events (emit), logs/behavioral_events.jsonl (signal).
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    from pathlib import Path as _P
    ROOT = _P(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "recurrence_gate.v1"
RECORDS = ROOT / "memory" / "learn" / "recurrences.jsonl"
EVENTS = ROOT / "logs" / "behavioral_events.jsonl"
STATE = ROOT / "memory" / "recurrence_gate" / "state.json"

# The KNOWN correction classes — the recurring failure patterns the operator has HAD to re-tell
# us (grounded in the actual corrections in repo memory, not invented). Each maps to the specific
# guard that must auto-open so the cause cannot recur.
KNOWN_CLASSES: dict[str, dict[str, Any]] = {
    "wrong_tool": {
        "keywords": ["wrong tool", "wrong-tool", "terminal", "powershell", "spawn", "run_in_terminal"],
        "guard": "route through the architecture (ghost tools / modules / REST / queue), never a "
                 "terminal spawn for framework work",
        "surface": "route",
    },
    "invented_number": {
        "keywords": ["invented", "over-claim", "overclaim", "savings", "log field", "estimate $"],
        "guard": "ground in the BILL / authoritative source; never derive dollar claims from logs",
        "surface": "truth",
    },
    "fetch_recurrence": {
        "keywords": ["fetch", "fetch-webpage", "fetch webpage", "webpage fetch", "pane fetch"],
        "guard": "use the browser/CDP surface, not the pane fetch, for live pages",
        "surface": "browser",
    },
    "prompt_to_run": {
        "keywords": ["just do it", "should i", "shall i", "ask permission", "want me to",
                     "say the word", "approve"],
        "guard": "standing permission = EXECUTE end-to-end, never ping for approval",
        "surface": "route",
    },
    "window_spawn": {
        "keywords": ["windowed spawn", "window spawn", "popup window", "new window"],
        "guard": "no windowed spawns / popups — headless + no-window",
        "surface": "route",
    },
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _ts() -> datetime:
    return datetime.now(timezone.utc)


def _read_jsonl(path: Path, tail: int = 500) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    out: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[-tail:]:
        line = line.strip()
        if not line:
            continue
        try:
            o = json.loads(line)
            if isinstance(o, dict):
                out.append(o)
        except (json.JSONDecodeError, TypeError):
            continue
    return out


def record(cls: str, note: str = "") -> dict[str, Any]:
    """Write ONE training capture for a correction class. Call this wherever a correction is
    learned, so the gate can detect recurrence instead of silently re-incurring it."""
    cls = (cls or "").strip()
    if cls not in KNOWN_CLASSES:
        cls = "wrong_tool"  # safe default; the note carries the real class
    row = {"schema": SCHEMA, "class": cls, "ts": _now(), "note": (note or "")[:400]}
    try:
        RECORDS.parent.mkdir(parents=True, exist_ok=True)
        with RECORDS.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    except OSError:
        pass
    return {"ok": True, "schema": SCHEMA, "recorded": row}


def _classify(note: str) -> str | None:
    """Classify a free-text capture/event into a known class by keyword. Grounded: each class has
    explicit keywords; unknown text stays unclassified (never force-fit)."""
    text = (note or "").lower()
    for cls, cfg in KNOWN_CLASSES.items():
        if any(k in text for k in cfg["keywords"]):
            return cls
    return None


def _load_state() -> dict[str, Any]:
    if STATE.is_file():
        try:
            return json.loads(STATE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"last_check": "", "opened": {}, "total_recurrences": 0}


def _save_state(s: dict[str, Any]) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")


def _emit_behavioral(kind: str, **extra: Any) -> None:
    row = {"kind": kind, "ts": _now(), **extra}
    try:
        EVENTS.parent.mkdir(parents=True, exist_ok=True)
        with EVENTS.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    except OSError:
        pass


def check(*, window_hours: int = 48, threshold: int = 2) -> dict[str, Any]:
    """GATE: scan recent captures + behavioral events; any known class firing >= threshold in the
    window is a RECURRENCE -> surface it + auto-open the specific guard. Idempotent, $0."""
    cutoff = (_ts() - timedelta(hours=window_hours)).isoformat()

    # collect all recent signals of each class
    counts: dict[str, int] = {c: 0 for c in KNOWN_CLASSES}
    last_note: dict[str, str] = {}
    for r in _read_jsonl(RECORDS):
        if str(r.get("ts") or "") < cutoff:
            continue
        cls = r.get("class")
        if cls in counts:
            counts[cls] += 1
            last_note[cls] = str(r.get("note") or "")
    # also fold free-text behavioral events through classification (catches events logged without
    # an explicit class)
    for e in _read_jsonl(EVENTS, tail=300):
        if str(e.get("ts") or "") < cutoff:
            continue
        cls = _classify(str(e.get("note") or e.get("error") or ""))
        if cls:
            counts[cls] += 1
            last_note.setdefault(cls, str(e.get("note") or ""))

    # which guards fired (recurrence >= threshold)
    opened: dict[str, dict[str, Any]] = {}
    for cls, n in counts.items():
        if n >= threshold:
            opened[cls] = {"count": n, "guard": KNOWN_CLASSES[cls]["guard"],
                           "surface": KNOWN_CLASSES[cls]["surface"],
                           "last_note": last_note.get(cls, "")}

    # surface each recurrence through the shared cast/trigger surface + training events
    surfaced = 0
    for cls, info in opened.items():
        _emit_behavioral("correction_recurrence", class_=cls, count=info["count"],
                         guard=info["guard"])
        try:
            from mag import training_events
            training_events.emit("operator_behavior", pattern_tags=["correction_recurrence", cls],
                                 join={"class": cls, "count": info["count"]},
                                 outcome={"guard": info["guard"]}, exportable=False)
            surfaced += 1
        except Exception:
            pass

    state = _load_state()
    state["last_check"] = _now()
    state["opened"] = {k: v["count"] for k, v in opened.items()}
    state["total_recurrences"] = state.get("total_recurrences", 0) + len(opened)
    _save_state(state)

    return {"ok": True, "schema": SCHEMA, "window_hours": window_hours, "threshold": threshold,
            "counts": counts, "guards_opened": opened, "surfaced": surfaced,
            "note": (f"{len(opened)} correction class(es) at/above recurrence threshold — guards "
                     f"auto-opened on the shared surface so the operator need not re-tell us" if opened
                     else "no known correction class recurred in the window — loop is quiet")}


def status() -> dict[str, Any]:
    s = _load_state()
    return {"ok": True, "schema": SCHEMA,
            "contract": "record(class,note)->check(window_hours,threshold)-> on recurrence surface "
                        "kind='correction_recurrence' + auto-open the guard via trigger_learn",
            "cost": "deterministic + $0",
            "known_classes": list(KNOWN_CLASSES),
            "records": str(RECORDS.relative_to(ROOT)).replace("\\", "/"),
            "last_check": s.get("last_check"),
            "total_recurrences": s.get("total_recurrences", 0),
            "opened_now": s.get("opened", {})}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="recurrence-gate")
    ap.add_argument("cmd", nargs="?", default="check", choices=["check", "status"])
    ap.add_argument("--class", dest="cls", default="", help="class for record")
    ap.add_argument("--note", default="", help="note for record")
    a = ap.parse_args()
    if a.cmd == "record":
        print(json.dumps(record(a.cls or "wrong_tool", a.note), ensure_ascii=False, indent=2))
    elif a.cmd == "status":
        print(json.dumps(status(), ensure_ascii=False, indent=2, default=str))
    else:
        print(json.dumps(check(), ensure_ascii=False, indent=2, default=str))
