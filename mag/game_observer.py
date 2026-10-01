"""game_observer — the two-surface live-correction loop, automated on the game.

SELF-STEAL (2026-08-15, deep): everything here REUSES the existing observer/healer
machinery — it does NOT rebuild it.
  - runner:   mag.campaign_runs (records live play to memory/game/campaign_runs/*.jsonl)
  - observer: the desk_observer pattern (tail the live log, score rule-based Agent-as-Judge,
              inject a steer BEFORE the next turn wakes)
  - healer:   mag.error_healer / failure_kb (SEE -> MEM -> PATCH -> FOLD so it never recurs)

Operator (2026-08-15): "the point of all of this is to have the deterministic shape to the
stochastic" + "grok watched you play and fixed the shit in real time" — the core improvement
loop is ONE surface running (stochastic) while ANOTHER watches the live run and corrects it in
real time. This module automates that second surface against the game's live play log, using the
KNOWN failure signatures the overnight transcript proved:
  1. action_failed        (ok=False -> unknown action / engine miss)
  2. empty_narration      (ok=True but no narration -> deepseek starvation / fallback)
  3. placeholder_narration(ok=True but placeholder -> fallback wrote junk)
  4. reprint              (iterated=True -> the loop spun the same beat)

Schema: game_observer.v1 · deterministic · $0 (no model calls) · read-only on game state
"""
from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

SCHEMA = "game_observer.v1"
RUNS_DIR = ROOT / "memory" / "game" / "campaign_runs"
STEER_FILE = ROOT / "memory" / "game" / "game_observer_steer.json"
TRAIL = ROOT / "memory" / "runs" / "game_observer_trail.jsonl"

# placeholder markers that mean the writer fell back instead of writing.
_PLACEHOLDER = re.compile(r"(lorem|\[fallback\]|\[placeholder\]|TODO\b|not implemented|error:|^ERROR)", re.I)
# reprint threshold (matches campaign_runs' own near-duplicate detector).
REPEAT_THRESHOLD = 0.85

_SIGS: list[tuple[str, Callable[[dict[str, Any]], bool], str, str]] = [
    ("action_failed", lambda r: r.get("ok") is False,
     "action failed / unknown action",
     "route the runner through handle_game action='act' with legal actions from the current room"),
    ("empty_narration", lambda r: bool(r.get("ok")) and not str(r.get("narration") or "").strip(),
     "ok but no narration — deepseek starvation or fallback returned nothing",
     "raise the creative token budget so reasoning + the beat both fit; never ship empty"),
    ("placeholder_narration", lambda r: bool(r.get("ok")) and bool(_PLACEHOLDER.search(str(r.get("narration") or ""))),
     "fallback placeholder leaked into the beat",
     "force the writer to fail loudly instead of emitting placeholders"),
    ("reprint", lambda r: bool(r.get("iterated")),
     "near-repeat of the previous beat — the loop spun in place",
     "the beat must advance state (new room/flag/object); reprint = nothing changed"),
]


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _trail(event: str, **fields: Any) -> None:
    try:
        TRAIL.parent.mkdir(parents=True, exist_ok=True)
        with TRAIL.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"ts": _utc(), "event": event, "schema": SCHEMA, **fields}, default=str) + "\n")
    except Exception:
        pass


def read_runs(tail_sessions: int = 0) -> list[dict[str, Any]]:
    """Read every play-log row (all campaign_runs jsonl), optionally last N sessions."""
    rows: list[dict[str, Any]] = []
    files = sorted(RUNS_DIR.glob("*.jsonl"))
    if tail_sessions > 0:
        files = files[-tail_sessions:]
    for p in files:
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def detect(row: dict[str, Any]) -> list[str]:
    """Score ONE turn against the known failure signatures. Returns the failing kinds."""
    hits = []
    for kind, cond, _desc, _remedy in _SIGS:
        try:
            if cond(row):
                hits.append(kind)
        except Exception:
            continue
    return hits


def watch(*, tail_sessions: int = 0) -> dict[str, Any]:
    """SEE: scan the live play log for the known failure signatures."""
    rows = read_runs(tail_sessions=tail_sessions)
    counts: Counter = Counter()
    problems: list[dict[str, Any]] = []
    for r in rows:
        hits = detect(r)
        if not hits:
            continue
        for h in hits:
            counts[h] += 1
        problems.append({"ts": r.get("ts"), "turn": r.get("turn"),
                         "action": str(r.get("action") or "")[:40],
                         "kinds": hits,
                         "narration": str(r.get("narration") or "")[:120],
                         "room_id": r.get("room_id")})
    return {"schema": SCHEMA + ".watch", "ts": _utc(),
            "rows_seen": len(rows), "problem_rows": len(problems),
            "counts": dict(counts), "problems": problems[-40:]}


def score_session() -> dict[str, Any]:
    """Agent-as-Judge lite: aggregate per-session alignment score (deterministic, no LLM)."""
    from collections import defaultdict
    rows = read_runs()
    by_file: dict[str, list[dict[str, Any]]] = defaultdict(list)
    files = sorted(RUNS_DIR.glob("*.jsonl"))
    fidx = 0
    for p in files:
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                by_file[str(p)].append(json.loads(line))
            except json.JSONDecodeError:
                continue
        fidx += 1
    sessions = []
    for path, rows in by_file.items():
        if not rows:
            continue
        n = len(rows)
        ok = sum(1 for r in rows if r.get("ok"))
        fail = [detect(r) for r in rows]
        n_problem = sum(1 for f in fail if f)
        score = round(1.0 - (n_problem / max(1, n)), 3) if n else 0.0
        sessions.append({"file": Path(path).name, "turns": n, "ok": ok,
                         "problem_turns": n_problem, "score": score,
                         "top_kinds": dict(Counter(k for f in fail for k in f).most_common(3))})
    sessions.sort(key=lambda s: s["score"])
    return {"schema": SCHEMA + ".score", "ts": _utc(),
            "n_sessions": len(sessions), "sessions": sessions,
            "best": sessions[-1] if sessions else None,
            "worst": sessions[0] if sessions else None}


def steer(*, focus: str = "") -> dict[str, Any]:
    """Write a steer the next campaign_runs session reads BEFORE it wakes (desk_observer pattern)."""
    w = watch(tail_sessions=0)
    counts = w.get("counts") or {}
    # choose the single most important fix for the next session
    priority = ["action_failed", "empty_narration", "placeholder_narration", "reprint"]
    target = focus or next((k for k in priority if counts.get(k)), "")
    steer_doc = {
        "ts": _utc(), "schema": SCHEMA + ".steer",
        "target": target, "counts": counts,
        "instruction": _remedy_for(target),
    }
    try:
        STEER_FILE.parent.mkdir(parents=True, exist_ok=True)
        STEER_FILE.write_text(json.dumps(steer_doc, indent=2), encoding="utf-8")
    except Exception:
        pass
    _trail("steer", target=target)
    return steer_doc


def _remedy_for(kind: str) -> str:
    for k, _c, _d, remedy in _SIGS:
        if k == kind:
            return remedy
    return "continue the loop; no known signature to fix"


def heal(*, tail_sessions: int = 0) -> dict[str, Any]:
    """PATCH: fold every detected failure to the failure-KB so it NEVER recurs (error_healer reuse)."""
    from mag import failure_kb
    w = watch(tail_sessions=tail_sessions)
    folded = 0
    seen = set()
    for p in w.get("problems", []):
        for kind in p.get("kinds", []):
            key = (kind, p.get("action"))
            if key in seen:
                continue
            seen.add(key)
            try:
                failure_kb.record_failure(sig=f"game_observer:{kind}",
                                          symptom=str(p.get("narration") or "")[:120],
                                          remedy=_remedy_for(kind)[:200],
                                          source="game_observer")
                folded += 1
            except Exception:
                pass
    _trail("heal", folded=folded, counts=w.get("counts"))
    return {"schema": SCHEMA + ".heal", "ts": _utc(), "folded": folded, "counts": w.get("counts")}


def human() -> dict[str, Any]:
    """Plain-English reading of the live loop state (reuse human_readable spirit, no raw dict)."""
    w = watch(tail_sessions=0)
    s = score_session()
    counts = w.get("counts") or {}
    lines = []
    if w.get("rows_seen"):
        if counts:
            for k, v in counts.items():
                lines.append(f"{v} turn(s) hit '{k}': {next((d for kk,c,d,_ in _SIGS if kk==k), '')}")
        else:
            lines.append("no known failure signatures in the recent play log.")
    else:
        lines.append("no campaign play rows on disk yet — the loop is quiet.")
    if s.get("n_sessions"):
        w_ = s.get("worst") or {}
        lines.append(f"worst session: {w_.get('file')} — {w_.get('problem_turns')}/{w_.get('turns')} turns failed (score {w_.get('score')}).")
    return {"schema": SCHEMA + ".human", "ts": _utc(), "reading": " ".join(lines) or "Nothing to read yet.",
            "counts": counts}


def observe(*, tail_sessions: int = 0, heal: bool = True) -> dict[str, Any]:
    """The full pass: SEE -> score -> STEER (before next wake) -> PATCH (if heal) -> FOLD."""
    w = watch(tail_sessions=tail_sessions)
    s = score_session()
    st = steer()
    h = heal(tail_sessions=tail_sessions) if heal else {"folded": 0, "counts": w.get("counts")}
    _trail("observe", rows=w.get("rows_seen"), problems=w.get("problem_rows"),
           steer=st.get("target"), folded=h.get("folded"))
    return {"schema": SCHEMA + ".observe", "ts": _utc(),
            "watch": {k: w[k] for k in ("rows_seen", "problem_rows", "counts")},
            "steer_target": st.get("target"),
            "heal_folded": h.get("folded"),
            "worst_session": (s.get("worst") or {}).get("file")}


if __name__ == "__main__":
    import sys as _sys
    cmd = _sys.argv[1] if len(_sys.argv) > 1 else "observe"
    if cmd == "human":
        print(json.dumps(human(), indent=2, default=str))
    else:
        print(json.dumps(observe(), indent=2, default=str))
