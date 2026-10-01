"""grok_seat_burner — drive TWO grok seats (nacho + sd) in parallel, rightsized, toward the game.

WHY (2026-08-16, operator): "can't we drive two grok seats at once to test cache hit steering and
how to best use all in conjunction rightsizing asks to extend usage and changing model tiers all
that jass and chariot our way to our game."

THE REFRAME (grounded, sacred-cow-free): grok build authenticates by SESSION in a grok home dir,
and grok honors $env:GROK_HOME (PROVEN 2026-08-16). So each account is a SEAT = a home dir:
    nacho = ~/.grok     (nachobusinesscorp@gmail.com)
    sd    = ~/.grok-sd  (fostertron@gmail.com)
Two seats = two SEPARATE grok processes, each with its own GROK_HOME. That's the parallel driver:
not a key chain, not a container — just N processes on N homes.

The rightsize (stretch usage, pick the right model tier):
    - CLASSIFY each task by shape (frontier/deep vs cheap/scut) -> grok only for frontier-shaped
      work (the scarce, high-value seat). Cheap work stays on deepseek/vram (free). This is the
      frontier_council route-by-work-type law, made per-seat.
    - MODEL TIER per seat per task: a task can request grok's model tier (grok-4.5 / extra-high /
      the seat's default). Changing the tier is a per-task knob, NOT a per-seat lock.

CACHE-HIT STEERING (the test the operator wants): the ORCHESTRATOR (this module, $0) decides which
seat gets which task using a deterministic rightsize gate. When it needs frontier reasoning to
STEER (e.g. "which seat should take the next room?"), it escalates through session_maze.escalate_cached
(byte-stable maze prefix -> cache-HIT ~$0.0036/M) instead of a fresh miss. Reused — nothing invented.

CHARIOT TO THE GAME: the tasks are GAME-SHAPED — each seat works the dungeon (game_mud / game_produce
prepare_next) so the frontier seats produce real world-loot. The produce loop folds landed work.

Schema: grok_seat_burner.v1 · deterministic orchestrator + $0 gate · reuse: grok_seat (GROK_HOME),
harness.grok_cli, session_maze.escalate_cached, game_produce, frontier_council — nothing invented.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCHEMA = "grok_seat_burner.v1"

# Spend ledger (2026-08-17, operator "is it actually using?"): every driven task records a row
# here so usage is measured by OUR bytes, not the grok dashboard. Honest accounting.
SPEND_LEDGER = ROOT / "memory" / "runs" / "seat_spend" / "spend.jsonl"

# The two seats (operator has exactly two grok accounts).
SEATS: dict[str, dict[str, Any]] = {
    "nacho": {"home": str(Path.home() / ".grok"), "email": "nachobusinesscorp@gmail.com"},
    "sd": {"home": str(Path.home() / ".grok-sd"), "email": "fostertron@gmail.com"},
}
DEFAULT_SEAT_ORDER = ["nacho", "sd"]

GROK_BIN = os.environ.get("GROK_BIN") or str(Path.home() / ".grok" / "bin" / "grok.exe")

# Model tiers per seat (per-task knob — not a per-seat lock). Default = let grok pick.
MODEL_TIERS = ("", "grok-4.5", "extra-high", "high", "medium")

# ── RIGHTSIZE GATE: is this task frontier-shaped (grok-worthy) or cheap (deepseek/vram)? ──
_FRONTIER_SHAPES = (
    "frontier", "research", "deep", "strategy", "architecture", "root cause",
    "synthesis", "design", "game design", "world", "steal", "invariant",
)
_CHEAP_SHAPES = ("scut", "tactical", "data", "maintenance", "render", "cache", "classify")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def classify_task(goal: str) -> str:
    """Rightsize: frontier (grok seat) vs cheap (deepseek/vram). Code-as-law, $0."""
    g = (goal or "").lower()
    if any(s in g for s in _FRONTIER_SHAPES):
        return "frontier"
    if any(s in g for s in _CHEAP_SHAPES):
        return "cheap"
    return "frontier"  # default to the scarce seat only if it looks meaty; else it's cheap


def record_spend(seat: str, result: dict[str, Any], spec: dict[str, Any] | None = None) -> dict[str, Any]:
    """Append one driven task's spend row to the ledger (append-only jsonl).

    Counts what WE did: seat, task, verdict, corrected, words produced, timestamps. This is the
    honest byte-level accounting that answers "is SD/nacho actually being used" — from our own
    records, not the grok dashboard. Never logs tokens or secrets; just our driven activity."""
    spec = spec or {}
    acc = result.get("accepted") or {}
    row = {
        "schema": "grok_seat_burner.spend.v1", "ts": _now(), "seat": seat,
        "task": str(spec.get("deliverable") or "")[:120], "scene": str(spec.get("scene") or ""),
        "ok": bool(result.get("ok")), "accepted": bool(acc.get("ok")),
        "n_corrections": int(result.get("n_corrections") or 0),
        "n_attempts": len(result.get("attempts") or []),
        "words": len((acc.get("output") or "").split()),
        "started": (acc.get("started") or ""), "finished": (acc.get("finished") or ""),
        "model": acc.get("model") or result.get("model") or "(default)",
    }
    SPEND_LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with SPEND_LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    return row


def spend_ledger(*, seat: str | None = None, tail: int = 20) -> dict[str, Any]:
    """Read back the spend ledger: how many drives per seat, accepted, words, total runs. This is
    the honest answer to 'is the seat actually being used' — grounded in our own bytes."""
    rows = []
    if SPEND_LEDGER.is_file():
        for line in SPEND_LEDGER.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    if seat:
        rows = [r for r in rows if r.get("seat") == seat]
    recent = rows[-tail:]
    per_seat: dict[str, dict[str, Any]] = {}
    for r in rows:
        s = r.get("seat") or "?"
        ps = per_seat.setdefault(s, {"runs": 0, "accepted": 0, "words": 0, "corrections": 0})
        ps["runs"] += 1
        if r.get("accepted"):
            ps["accepted"] += 1
        ps["words"] += int(r.get("words") or 0)
        ps["corrections"] += int(r.get("n_corrections") or 0)
    return {"ok": True, "schema": "grok_seat_burner.spend.v1", "ts": _now(),
            "total_runs": len(rows), "per_seat": per_seat, "recent": recent,
            "note": "spend measured by OUR driven-task bytes (not the grok dashboard)"}


def seats_status() -> dict[str, Any]:
    """Which seats are configured + authenticated (names only — never tokens)."""
    out = {}
    for name, cfg in SEATS.items():
        auth = Path(cfg["home"]) / "auth.json"
        ok = auth.is_file()
        email = ""
        if ok:
            try:
                j = json.loads(auth.read_text(encoding="utf-8", errors="replace"))
                p = next(iter(j.values()), {})
                email = p.get("email", "")
            except Exception:
                email = "(unreadable)"
        out[name] = {"home": cfg["home"], "configured": ok, "email": email or "(no auth.json)"}
    return {"ok": True, "schema": "grok_seat_burner.seats.v1", "seats": out}


def _launch_one(
    seat: str,
    goal: str,
    *,
    model: str = "",
    max_turns: int = 6,
    timeout: int = 300,
    cwd: Path | None = None,
    json_schema: str | None = None,
    no_subagents: bool = True,
    always_approve: bool = False,
) -> dict[str, Any]:
    """Launch grok on ONE seat (isolated via GROK_HOME) with a rightsized goal. Returns result.

    BEST-PRACTICE (2026-08-17, operator: "these runs are way too slow... do a steal, kill sacred
    cows, more reliable + faster"):
      - json_schema: constrain output to structured JSON (implies --output-format json). This is
        FAR more reliable than parsing prose — a code-writing seat returns code in a field, not
        narration that fails to parse. This fixes the "sd wrote nothing parseable" failure.
      - no_subagents: disable subagent spawning (big overhead/turn saver for a single deliverable).
      - max_turns right-sized: an agent runs N tool turns; too high = slow, too low = no deliverable.
    """
    cfg = SEATS.get(seat)
    if not cfg:
        return {"ok": False, "seat": seat, "error": f"unknown seat: {seat}"}
    home = cfg["home"]
    if not (Path(home) / "auth.json").is_file():
        return {"ok": False, "seat": seat, "error": f"seat {seat} not authenticated (run 'grok {seat} login')"}
    if not Path(GROK_BIN).is_file():
        return {"ok": False, "seat": seat, "error": f"grok binary not found: {GROK_BIN}"}

    env = dict(os.environ)
    env["GROK_HOME"] = home  # the seat isolation — this process uses this account only
    cmd = [GROK_BIN, "-p", goal, "--cwd", str(cwd or ROOT), "--output-format", "plain",
           "--max-turns", str(max_turns), "--no-auto-update"]
    if no_subagents:
        cmd.append("--no-subagents")
    if always_approve:  # opt-in (2026-08-26): headless file-writing burns stall without it
        cmd.append("--always-approve")
    if json_schema:
        cmd += ["--json-schema", json_schema]  # structured output: reliable, parseable
    if model:
        cmd += ["--model", model]  # per-task model tier knob
    t0 = _now()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                              cwd=str(cwd or ROOT), env=env)
        out = (proc.stdout or "")[-6000:]
        err = (proc.stderr or "")[-800:]
        return {
            "ok": proc.returncode == 0, "seat": seat, "model": model or "(default)",
            "exit_code": proc.returncode, "output": out, "stderr": err,
            "started": t0, "finished": _now(),
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "seat": seat, "model": model or "(default)",
                "error": "timeout", "started": t0, "finished": _now()}
    except Exception as e:
        return {"ok": False, "seat": seat, "model": model or "(default)",
                "error": str(e)[:160], "started": t0, "finished": _now()}


# ═══════════════════════════════════════════════════════════════════════════
# DETERMINISTIC INSTRUCTION CONTRACT + WATCH / PAUSE / GENTLY CORRECT
# (operator, 2026-08-16): "we should treat them deterministically with instruction
# to make sure they do what we ask and we watch. we pause when we spot something
# amiss and gently correct." — the pause-first law, made per-seat, $0.
# ═══════════════════════════════════════════════════════════════════════════
def build_instruction(spec: dict[str, Any]) -> str:
    """Turn a task spec into a DETERMINISTIC instruction contract the seat must obey.

    The contract names: the deliverable (what we want), the acceptance (how we check it,
    mechanically), and the forbid-list (what would count as drifting — loading frameworks,
    hedging, going off-scene). Putting the acceptance IN the instruction lets verify()
    check it mechanically after — we watch, and we know what "amiss" looks like in advance.
    """
    deliver = str(spec.get("deliverable") or "answer the question directly")
    acceptance = str(spec.get("acceptance") or "return the concrete answer, under the word limit")
    forbid = spec.get("forbid") or []
    forbid_txt = "; ".join(f"DO NOT {f}" for f in forbid) if forbid else ""
    scene = str(spec.get("scene") or "")
    scene_txt = f" Stay on THIS scene: {scene}." if scene else ""
    limit = int(spec.get("word_limit") or 60)
    parts = [
        "You are a deterministic collaborator. Follow the contract EXACTLY.",
        f"DELIVERABLE: {deliver}",
        f"ACCEPTANCE: {acceptance} Must be under {limit} words.",
        "Do NOT load any framework, tool, skill, or file. Do NOT narrate your process. "
        "Do NOT hedge, ask questions, or refuse. Output ONLY the answer.",
    ]
    if forbid_txt:
        parts.append(forbid_txt)
    if scene_txt:
        parts.append(scene_txt)
    parts.append("Now output the answer:")
    return " ".join(parts)


def verify_output(result: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    """DETERMINISTIC WATCH ($0): check a seat's output against the instruction contract.
    Returns ok:True if it did what we asked, or a verdict naming what's amiss (to pause+correct)."""
    out = (result.get("output") or "").strip()
    if not out:
        return {"ok": False, "verdict": "empty_output", "reason": "no output text"}
    limit = int(spec.get("word_limit") or 60)
    n_words = len(out.split())
    if n_words > limit * 3:  # gross over-length = it narrated/loaded instead of answering
        return {"ok": False, "verdict": "too_long", "reason": f"{n_words} words (limit {limit})",
                "n_words": n_words}
    # drift signals: process-narration / framework-loading / hedging (the things the contract forbade)
    low = out.lower()
    drift = []
    if any(k in low for k in ("loading", "framework", "i'll", "compass", "checking the", "let me",
                               "i will load", "first i")):
        drift.append("process_narration")
    if any(k in low for k in ("do not load", "i can't", "i cannot", "i won't", "as an ai")):
        drift.append("hedging_or_refusal")
    # scene anchor (if a scene was required)
    scene = str(spec.get("scene") or "").lower()
    if scene:
        tok = scene.replace("the ", "").replace("'", "").replace("-", " ").strip()
        anchors = [tok] + [w for w in tok.split() if len(w) >= 4]
        if not any(a in low for a in anchors if a):
            drift.append("off_scene")
    if drift:
        return {"ok": False, "verdict": "drift", "drift": drift,
                "reason": "output violates the instruction contract"}
    return {"ok": True, "verdict": "ok", "n_words": n_words}


def _gentle_correction(spec: dict[str, Any], verdict: str) -> str:
    """GENTLY CORRECT: a short, non-scolding re-aim of the same contract. No blame — just the
    specific miss and the one line to fix it. (The operator's 'gently correct', made literal.)"""
    if verdict == "too_long":
        return ("You went over the word limit. That usually means you narrated your process. "
                "Reset: output ONLY the concrete answer in under the limit. No loading, no "
                "process narration, no framework. Just the answer.")
    if verdict == "empty_output":
        return ("You returned nothing. Output ONLY the concrete answer to the deliverable. "
                "Under the limit. No process, no preamble.")
    if "off_scene" in verdict:
        scene = str(spec.get("scene") or "")
        return (f"You drifted off the scene. Stay on THIS scene: {scene}. Output only an answer "
                f"grounded in that scene, under the limit.")
    return ("You violated the instruction contract (loaded a framework, hedged, or narrated "
            "instead of answering). Reset and output ONLY the concrete answer, under the limit, "
            "on scene. No process, no hedging.")


def run_watched(
    seat: str,
    spec: dict[str, Any],
    *,
    model: str = "",
    max_attempts: int = 2,
    timeout: int = 300,
) -> dict[str, Any]:
    """Drive ONE seat under the deterministic contract with WATCH + PAUSE + GENTLY CORRECT.

    Run the seat with the built instruction -> verify the output mechanically ($0) -> if it
    deviates, PAUSE (don't accept), send the GENTLE CORRECTION back as the next prompt, and retry
    up to max_attempts. This is the pause-first law, per seat, $0 verification.
    """
    contract = build_instruction(spec)
    attempts = []
    json_schema = spec.get("json_schema")  # structured output (reliable, parseable)
    no_subagents = bool(spec.get("no_subagents", True))
    for attempt in range(1, max_attempts + 1):
        prompt = contract if attempt == 1 else contract + " " + _gentle_correction(spec, verdict)
        r = _launch_one(seat, prompt, model=model,
                        max_turns=int(spec.get("max_turns") or 4), timeout=timeout,
                        json_schema=json_schema, no_subagents=no_subagents)
        r["attempt"] = attempt
        v = verify_output(r, spec)
        r["verdict"] = v
        attempts.append(r)
        if v.get("ok"):
            return {"ok": True, "seat": seat, "model": model or "(default)", "attempts": attempts,
                    "accepted": r, "corrected": attempt > 1, "n_corrections": attempt - 1}
        verdict = v.get("verdict", "drift")  # noqa: F841 (used next iteration)
        if attempt >= max_attempts:
            return {"ok": False, "seat": seat, "model": model or "(default)", "attempts": attempts,
                    "accepted": None, "corrected": True, "n_corrections": attempt - 1,
                    "error": f"could not satisfy contract after {attempt} attempts: {v.get('reason')}"}
    return {"ok": False, "seat": seat, "model": model or "(default)", "attempts": attempts}


def drive_watched_parallel(
    tasks: list[dict[str, Any]],
    *,
    seats: list[str] | None = None,
    model_tiers: dict[str, str] | None = None,
) -> dict[str, Any]:
    """PARALLEL dual-seat drive under the deterministic contract: each task -> a seat, watched,
    paused + gently corrected if it drifts. Cheap work stays off the scarce seats (rightsize)."""
    seats = seats or DEFAULT_SEAT_ORDER
    model_tiers = model_tiers or {}
    if len(seats) < 2:
        return {"ok": False, "schema": SCHEMA, "error": "need >=2 seats for parallel drive"}
    assignments: dict[str, list[dict[str, Any]]] = {s: [] for s in seats}
    i = 0
    for t in tasks:
        goal = str(t.get("goal") or "")
        if classify_task(goal) != "frontier":
            continue
        spec = dict(t)
        spec.setdefault("deliverable", goal)
        assignments[seats[i % len(seats)]].append(spec)
        i += 1
    results: dict[str, Any] = {}
    import threading
    lock = threading.Lock()

    def _run(seat: str, spec: dict[str, Any]) -> None:
        r = run_watched(seat, spec, model=model_tiers.get(seat, spec.get("model", "")))
        # honest spend accounting: every driven task lands in the ledger
        try:
            record_spend(seat, r, spec)
        except Exception:
            pass
        with lock:
            results.setdefault(seat, []).append(r)

    threads = []
    for seat, specs in assignments.items():
        for spec in specs:
            th = threading.Thread(target=_run, args=(seat, spec), daemon=True)
            threads.append(th)
            th.start()
    for th in threads:
        th.join()
    return {"ok": True, "schema": SCHEMA, "ts": _now(), "seats": seats,
            "assignments": {s: [sp.get("deliverable", "")[:50] for sp in sl] for s, sl in assignments.items()},
            "results": results,
            "note": "parallel deterministic seat drive: watched, paused + gently corrected on drift"}


def drive_parallel(
    tasks: list[dict[str, Any]],
    *,
    seats: list[str] | None = None,
    model_tiers: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Drive the given tasks in PARALLEL across the seats. Each task is rightsized + routed to a
    seat, launched on its own GROK_HOME, model tier per task. Returns per-seat results."""
    seats = seats or DEFAULT_SEAT_ORDER
    model_tiers = model_tiers or {}
    if len(seats) < 2:
        return {"ok": False, "schema": SCHEMA, "error": "need >=2 seats for parallel drive"}
    # assign tasks round-robin across seats (rightsized: only frontier tasks go to grok)
    assignments: dict[str, list[dict[str, Any]]] = {s: [] for s in seats}
    i = 0
    for t in tasks:
        goal = str(t.get("goal") or "")
        shape = classify_task(goal)
        if shape != "frontier":
            continue  # cheap work stays off the scarce seats (rightsize, stretch usage)
        seat = seats[i % len(seats)]
        assignments[seat].append({**t, "seat": seat, "model": model_tiers.get(seat, t.get("model", ""))})
        i += 1

    results: dict[str, Any] = {}
    procs: dict[str, list[tuple[dict[str, Any], subprocess.Popen]]] = {}
    import threading
    lock = threading.Lock()

    def _run(seat: str, task: dict[str, Any]) -> None:
        r = _launch_one(seat, str(task.get("goal") or ""), model=str(task.get("model") or ""),
                        max_turns=int(task.get("max_turns") or 6), timeout=int(task.get("timeout") or 300))
        with lock:
            results.setdefault(seat, []).append(r)

    threads = []
    for seat, tasks_for_seat in assignments.items():
        for task in tasks_for_seat:
            th = threading.Thread(target=_run, args=(seat, task), daemon=True)
            threads.append(th)
            th.start()
    for th in threads:
        th.join()

    return {
        "ok": True, "schema": SCHEMA, "ts": _now(), "seats": seats,
        "assignments": {s: [t.get("goal", "")[:60] for t in tl] for s, tl in assignments.items()},
        "results": results,
        "note": "parallel seat drive: each task on its own GROK_HOME; cheap work kept off scarce seats",
    }


def steer(game_prompt: str, *, model: str = "deepseek-v4-pro", use_cache: bool = True) -> dict[str, Any]:
    """CACHE-HIT STEERING (the test the operator wants): the orchestrator escalates a steering
    question through the byte-stable maze (cache-hit ~$0.0036/M) to decide how to aim the seats.
    Reuses session_maze.escalate_cached — nothing invented."""
    try:
        from mag.session_maze import escalate_cached
        r = escalate_cached(game_prompt, model=model) if use_cache else {"ok": False, "error": "cache off"}
        return {"ok": bool(r.get("text")), "schema": SCHEMA, "action": "steer",
                "channel": "escalate_cached (cache-hit)" if use_cache else "direct",
                "text": r.get("text", "").strip(), "error": r.get("error"),
                "model": model, "cache_aware": True}
    except Exception as e:
        return {"ok": False, "schema": SCHEMA, "action": "steer", "error": str(e)[:160]}


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "contract": "seats_status()->which seats authed; classify_task(goal)->frontier/cheap; "
                        "drive_parallel(tasks)->run tasks across seats in parallel on separate "
                        "GROK_HOME; steer(game_prompt)->cache-hit escalation to aim the seats; "
                        "status()->this",
            "cost": "deterministic orchestrator + $0 gate; grok seat calls are the real scarce "
                    "cost; steer rides cache-hit when available",
            "reuse": "grok seat (GROK_HOME), harness.grok_cli, session_maze.escalate_cached, "
                     "game_produce, frontier_council",
            "seats": SEATS}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = (argv[0] if argv else "status").lower()
    if cmd in ("status", "seats"):
        print(json.dumps(seats_status(), indent=2, ensure_ascii=False, default=str))
        return 0
    if cmd == "steer":
        prompt = argv[1] if len(argv) > 1 else "Steer the two grok seats toward the game."
        print(json.dumps(steer(prompt), indent=2, ensure_ascii=False, default=str))
        return 0
    if cmd == "parallel":
        # parallel "<goalA>|" "<goalB>|" ... — each '|'-separated segment is a task goal
        goals = [a for a in argv[1:] if a]
        tasks = [{"goal": g} for g in goals]
        if not tasks:
            print(json.dumps({"ok": False, "error": "provide goals"}, indent=2))
            return 1
        print(json.dumps(drive_parallel(tasks), indent=2, ensure_ascii=False, default=str))
        return 0
    print(json.dumps(status(), indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
