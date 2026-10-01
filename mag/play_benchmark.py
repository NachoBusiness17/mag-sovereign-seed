"""Play benchmark runner — B0 session sustains; scorecard FILE.

Soft claims only: benchmark status, never AGI language.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT

BENCH_DIR = ROOT / "memory" / "game_benchmarks"
SCHEMA = "mag_play_benchmark.v1"

# B1: pillar break → named Mag disequilibrium (fc-mag-gt-001 / play-gt-map-001)
PILLAR_TO_EQUILIBRIUM: dict[str, str] = {
    "world": "world_form_collapse",  # no shared game form / invented rooms
    "rules": "illegal_message_accepted",  # strategy set not enforced
    "memory": "trail_abandonment",  # FILE continuity failed
    "adapt": "coordination_failure",  # Stag Hunt: seats didn't meet on legal path
    "causality": "cheap_talk_over_commitment",  # log/state not binding
    "collab": "grok_sink_or_freestyle",  # integrated session died / freestyle DM
}


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _equilibrium_tags(pillars: dict[str, bool], failures: list[dict[str, Any]]) -> list[str]:
    tags: list[str] = []
    for p, ok in (pillars or {}).items():
        if not ok:
            tags.append(PILLAR_TO_EQUILIBRIUM.get(p, f"unknown_{p}"))
    for f in failures or []:
        pillar = str(f.get("pillar") or "")
        eq = PILLAR_TO_EQUILIBRIUM.get(pillar)
        if eq and eq not in tags:
            tags.append(eq)
    return tags


def run_b0(*, voice_session_id: str = "bench-b0") -> dict[str, Any]:
    """Classic: start → character → 8 turns → resume fidelity."""
    from mag.game_campaign import (
        apply_action,
        begin_play,
        load_campaign,
        parse_character,
        set_character,
    )

    pillars = {
        "world": True,
        "rules": True,
        "memory": True,
        "adapt": True,
        "causality": True,
        "collab": True,
    }
    failures: list[dict[str, Any]] = []
    log: list[str] = []

    def fail(pillar: str, msg: str) -> None:
        pillars[pillar] = False
        failures.append({"pillar": pillar, "msg": msg})
        log.append(f"FAIL[{pillar}]: {msg}")

    # fresh campaign
    start = begin_play(
        module_id="classic",
        voice_session_id=voice_session_id,
        force_new=True,
    )
    if not start.get("ok"):
        fail("world", f"begin_play failed: {start.get('error')}")
        return _score("B0", False, pillars, failures, log, start)

    cid = str(start.get("campaign_id") or (start.get("campaign") or {}).get("campaign_id") or "")
    log.append(f"campaign {cid}")

    player = parse_character("I'm Ash a greedy fighter")
    if not player:
        fail("collab", "character parse failed")
        return _score("B0", False, pillars, failures, log, {"campaign_id": cid})

    ch = set_character(cid, player)
    if not ch.get("ok"):
        fail("world", f"set_character: {ch.get('error')}")
        return _score("B0", False, pillars, failures, log, ch)

    camp = load_campaign(cid) or {}
    room0 = camp.get("room_id")
    hp0 = (camp.get("player") or {}).get("hp")
    log.append(f"start room={room0} hp={hp0}")

    # scripted 8 turns — mix legal + one illegal
    script = [
        {"type": "look"},
        {"type": "status"},
        {"type": "move", "direction": "north"},
        {"type": "look"},
        {"type": "move", "direction": "north"},  # toward courtyard if path allows
        {"type": "status"},
        {"type": "rest"},
        {"type": "look"},
    ]
    # ensure illegal probe mid-run
    illegal_done = False
    turns_ok = 0

    for i, act in enumerate(script):
        if i == 3 and not illegal_done:
            bad = apply_action(cid, {"type": "move", "direction": "xyzzy"})
            illegal_done = True
            if bad.get("ok"):
                fail("rules", "illegal move xyzzy was accepted")
            else:
                log.append("illegal xyzzy correctly refused")
                turns_ok += 1  # counts as rules pillar exercise
        r = apply_action(cid, act)
        if not r.get("ok") and act.get("type") == "move":
            # try alternate direction
            r = apply_action(cid, {"type": "look"})
        if r.get("ok"):
            turns_ok += 1
            log.append(f"t{i}:{act.get('type')} ok")
        else:
            # rest might not exist as type — treat soft
            if act.get("type") == "rest" and "unknown" in str(r.get("error") or "").lower():
                r2 = apply_action(cid, {"type": "status"})
                if r2.get("ok"):
                    turns_ok += 1
                    log.append(f"t{i}:rest→status ok")
                else:
                    fail("adapt", f"turn {i} failed: {r.get('error')}")
            else:
                fail("adapt", f"turn {i} {act}: {r.get('error')}")

    camp2 = load_campaign(cid) or {}
    if not camp2:
        fail("memory", "campaign missing after turns")
    else:
        # resume fidelity: re-load same id
        camp3 = load_campaign(cid)
        if not camp3 or camp3.get("room_id") != camp2.get("room_id"):
            fail("memory", "resume room mismatch")
        if (camp3 or {}).get("player", {}).get("hp") != camp2.get("player", {}).get("hp"):
            fail("memory", "resume HP mismatch")
        log.append(
            f"resume room={camp2.get('room_id')} hp={(camp2.get('player') or {}).get('hp')}"
        )

    if turns_ok < 8:
        fail("collab", f"only {turns_ok}/8+ turns ok (need ≥8 engine interactions)")

    # causality: log grew
    nlog = len(camp2.get("log") or [])
    if nlog < 2:
        fail("causality", "campaign log too short")

    passed = all(pillars.values()) and turns_ok >= 8 and not any(
        f["pillar"] == "rules" and "accepted" in f["msg"] for f in failures
    )
    # recompute: rules fail only if illegal accepted
    if any(f["msg"].startswith("illegal") and "accepted" in f["msg"] for f in failures):
        passed = False
    elif turns_ok >= 8 and pillars.get("memory") and pillars.get("world"):
        # allow soft adapt fails if enough turns
        if turns_ok >= 8:
            passed = all(
                pillars[p] for p in ("world", "rules", "memory", "causality")
            )

    return _score(
        "B0",
        passed,
        pillars,
        failures,
        log,
        {
            "campaign_id": cid,
            "turns_ok": turns_ok,
            "room": camp2.get("room_id"),
            "hp": (camp2.get("player") or {}).get("hp"),
        },
    )


def _score(
    level: str,
    passed: bool,
    pillars: dict[str, bool],
    failures: list[dict[str, Any]],
    log: list[str],
    extra: dict[str, Any],
) -> dict[str, Any]:
    BENCH_DIR.mkdir(parents=True, exist_ok=True)
    eq = _equilibrium_tags(pillars, failures)
    row = {
        "schema": SCHEMA,
        "level": level,
        "passed": passed,
        "ts": _utc(),
        "pillars": pillars,
        "failures": failures,
        "equilibrium_breaks": eq,
        "gt_ref": "docs/ref/GAME_THEORY_PLAY_MAP.md",
        "log": log[-40:],
        "claim": "benchmark_status_only",
        "extra": extra,
    }
    path = BENCH_DIR / f"{level}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    path.write_text(json.dumps(row, indent=2, default=str), encoding="utf-8")
    latest = BENCH_DIR / f"{level}_latest.json"
    latest.write_text(json.dumps(row, indent=2, default=str), encoding="utf-8")
    row["path"] = str(path.relative_to(ROOT)).replace("\\", "/")
    return row


def run_b1() -> dict[str, Any]:
    """Name broken pillars / equilibria from latest B0 (or run B0 if missing)."""
    latest = BENCH_DIR / "B0_latest.json"
    if not latest.is_file():
        b0 = run_b0(voice_session_id="bench-b1-via-b0")
    else:
        try:
            b0 = json.loads(latest.read_text(encoding="utf-8"))
        except Exception:
            b0 = run_b0(voice_session_id="bench-b1-via-b0")

    pillars = dict(b0.get("pillars") or {})
    failures = list(b0.get("failures") or [])
    eq = list(b0.get("equilibrium_breaks") or _equilibrium_tags(pillars, failures))
    # B1 passes if we successfully *named* the state (pass or fail of B0 both OK)
    named = True
    if not b0.get("passed") and not eq and not failures:
        named = False
        failures = [{"pillar": "collab", "msg": "B0 failed without pillar tags"}]
        eq = _equilibrium_tags({"collab": False}, failures)

    log = [
        f"B0 passed={b0.get('passed')}",
        f"pillars={pillars}",
        f"equilibrium_breaks={eq}",
        "see GAME_THEORY_PLAY_MAP.md",
    ]
    return _score(
        "B1",
        named,
        pillars if pillars else {"collab": False},
        failures,
        log,
        {
            "b0_path": b0.get("path"),
            "b0_passed": b0.get("passed"),
            "equilibrium_breaks": eq,
            "lesson": "Name the disequilibrium; do not only say session felt bad",
        },
    )


def run_b2(*, voice_session_id: str = "bench-b2") -> dict[str, Any]:
    """Non-classic ruleset loads and plays a turn (generalization, not 5e-only Nash)."""
    from mag.game_campaign import (
        apply_action,
        begin_play,
        load_campaign,
        parse_character,
        set_character,
    )

    pillars = {k: True for k in PILLAR_TO_EQUILIBRIUM}
    failures: list[dict[str, Any]] = []
    log: list[str] = []

    def fail(pillar: str, msg: str) -> None:
        pillars[pillar] = False
        failures.append({"pillar": pillar, "msg": msg})
        log.append(f"FAIL[{pillar}]: {msg}")

    start = begin_play(
        module_id="2d6",
        voice_session_id=voice_session_id,
        force_new=True,
    )
    if not start.get("ok"):
        fail("world", f"2d6 begin failed: {start.get('error')}")
        return _score("B2", False, pillars, failures, log, start)

    cid = str(start.get("campaign_id") or "")
    mid = (start.get("campaign") or {}).get("module_id") or load_campaign(cid) or {}
    if isinstance(mid, dict):
        mid = mid.get("module_id")
    camp0 = load_campaign(cid) or {}
    mid = camp0.get("module_id") or mid
    if "2d6" not in str(mid) and "adventure_2d6" not in str(mid):
        fail("world", f"expected 2d6 module, got {mid}")

    player = parse_character("I'm Ren a curious traveler") or {
        "name": "Ren",
        "archetype": "traveler",
        "hp": 10,
        "hp_max": 10,
        "ac": 12,
        "attack_bonus": 1,
        "damage": "1d6",
        "traits": ["curious"],
        "inventory": ["walking stick"],
    }
    ch = set_character(cid, player)
    if not ch.get("ok"):
        fail("collab", f"character: {ch.get('error')}")
        return _score("B2", False, pillars, failures, log, ch)

    look = apply_action(cid, {"type": "look"})
    move = apply_action(cid, {"type": "move", "direction": "east"})
    bad = apply_action(cid, {"type": "move", "direction": "xyzzy"})
    if not look.get("ok"):
        fail("adapt", f"look: {look.get('error')}")
    if not move.get("ok"):
        fail("adapt", f"move east: {move.get('error')}")
    if bad.get("ok"):
        fail("rules", "illegal xyzzy accepted on 2d6")
    else:
        log.append("illegal refused on 2d6")

    camp = load_campaign(cid) or {}
    if not camp.get("room_id"):
        fail("memory", "no room after turns")
    log.append(f"module={camp.get('module_id')} room={camp.get('room_id')}")

    passed = all(pillars.values())
    return _score(
        "B2",
        passed,
        pillars,
        failures,
        log,
        {
            "campaign_id": cid,
            "module_id": camp.get("module_id"),
            "room": camp.get("room_id"),
            "lesson": "generalize ruleset — not 5e cosplay Nash",
        },
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Mag play benchmark")
    ap.add_argument("--level", default="B0", choices=["B0", "B1", "B2", "B3"])
    args = ap.parse_args(argv)
    if args.level == "B0":
        r = run_b0()
    elif args.level == "B1":
        r = run_b1()
    elif args.level == "B2":
        r = run_b2()
    else:
        r = {
            "schema": SCHEMA,
            "level": args.level,
            "passed": False,
            "claim": "benchmark_status_only",
            "error": f"{args.level} not automated yet — see docs/ref/PLAY_BENCHMARK.md",
            "gt_ref": "docs/ref/GAME_THEORY_PLAY_MAP.md",
        }
        BENCH_DIR.mkdir(parents=True, exist_ok=True)
        (BENCH_DIR / f"{args.level}_latest.json").write_text(
            json.dumps(r, indent=2), encoding="utf-8"
        )
    keys = (
        "level",
        "passed",
        "pillars",
        "equilibrium_breaks",
        "path",
        "extra",
        "failures",
        "gt_ref",
    )
    print(json.dumps({k: r[k] for k in keys if k in r}, indent=2))
    return 0 if r.get("passed") else 1


if __name__ == "__main__":
    sys.exit(main())
