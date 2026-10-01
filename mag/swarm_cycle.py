"""swarm_cycle.py — one composite flywheel turn over existing Mag organs.

Composes existing organs by subprocess, with the final blackboard effect
crossing the switchboard/effect-broker boundary:
  1. ghost_memlance select     -> grounded states for the goal (bytes, never synthesized)
  2. frontier_salon roundtable -> the swarm cross-examines (witnesses see each other)
  3. water_computer glass      -> one keep/convert beat (wait is a season)
  4. verkle_lance link         -> anchor the cycle to the chain tip
  5. surface_render all        -> mesh/lattice artifact (vram_lattice included)
  6. party_subchain verify     -> mount receipt (read-only; writes stay inside organs)
  7. blackboard note           -> durable evidence dropped in the swarm_worker store

ONE supervisor law: this is a composite organ, not a scheduler. Trigger from
governor / fuel_feed / by hand. No daemon, no cron, no new cage.

Conservation roster: pass --participants or let the salon use its seat_corpus
default. Until 2026-09-02 12:52Z: deepseek + free lanes + local ollama seat.

Run:
  python -m mag.swarm_cycle "GOAL" --dry          # structural first light, $0
  python -m mag.swarm_cycle "GOAL" --rounds 2     # live round
  python -m mag.swarm_cycle "GOAL" --participants deepseek,groq,ollama

Record: memory/runs/swarm_cycle/<ts>-<slug>.json  (full step JSONs inside)
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "memory" / "runs" / "swarm_cycle"
BB = ROOT / "memory" / "runs" / "swarm_worker" / "blackboard"


def _slug(s: str, n: int = 40) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    return s[:n] or "cycle"


def _run(args: list[str], timeout: int) -> dict:
    try:
        p = subprocess.run(
            [sys.executable, "-m"] + args,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            input="",
        )
        out = p.stdout or ""
        try:
            data = json.loads(out)
        except Exception:
            data = None
        return {
            "cmd": " ".join(args),
            "rc": p.returncode,
            "ok": p.returncode == 0,
            "json": data,
            "head": out[:800] if data is None else "",
            "err": (p.stderr or "")[-400:],
        }
    except subprocess.TimeoutExpired:
        return {"cmd": " ".join(args), "ok": False, "err": f"timeout {timeout}s"}
    except Exception as e:  # pragma: no cover
        return {"cmd": " ".join(args), "ok": False, "err": repr(e)}


def _blackboard_note(rec: dict, ev: str) -> dict:
    """Ghost-waker: post a durable-evidence note in swarm_tools.v1 format.

    Matches the live reader contract (bb-00057.json): files bb-NNNNN.json,
    schema swarm_tools.v1, seq = 1 + highest existing, with a retry on seq
    collision. Exhaust, not a gate — a failed write never fails the cycle.
    """
    try:
        step_ok = {
            k: bool(s.get("ok", False)) if isinstance(s, dict) else False
            for k, s in rec["steps"].items()
        }
        summary = (
            f"swarm_cycle {rec['ts']}: goal='{rec['goal']}' ok={rec['ok']} "
            + ",".join(f"{k}:{'ok' if v else 'FAIL'}" for k, v in step_ok.items())
        )
        note = {
            "schema": "swarm_tools.v1",
            "tool": "swarm_blackboard",
            "ts": rec["ts"],
            "owner": "swarm_cycle",
            "kind": "finding",
            "pinned": False,
            "text": summary,
            "event": ev,
            "dry": rec["dry"],
            "step_ok": step_ok,
        }

        # The old implementation wrote bb-NNNNN.json directly. That made the
        # flywheel look live while bypassing the authority mesh. Use the
        # existing proposal/grant path, then the unified effect broker.
        from . import effect_broker, switchboard_v2
        proposal = switchboard_v2.propose(
            event_id=ev,
            requested_effect="board_write",
            capabilities=["board_write"],
            memory_scope="swarm_worker",
            budget={"max_calls": 3},
            ttl_seconds=900,
            content=summary,
            source="swarm_cycle",
            authority_label="agent-generated",
            require_confirmation=False,
        )
        authority = switchboard_v2.grant(proposal)
        if authority.get("status") != "AUTHORIZED":
            return {"ok": False, "err": "switchboard denied blackboard note",
                    "authority": authority}
        executing = switchboard_v2.mark_executing(
            authority, {"effect": "board_write", "dry": rec["dry"]}
        )
        receipt = effect_broker.execute("board_write", {"note": note}, executing)
        result = receipt.get("result", {}) or {}
        if receipt.get("status") == "RECEIPT_COMMITTED" and result.get("ok"):
            terminal = switchboard_v2.complete(
                executing,
                {"broker_receipt": receipt.get("receipt_path"),
                 "path": result.get("path"), "seq": result.get("seq")},
            )
        else:
            terminal = switchboard_v2.fail(
                executing,
                receipt.get("error") or result.get("err") or "board_write failed",
                {"broker_receipt": receipt.get("receipt_path"),
                 "result": result},
            )
        committed = switchboard_v2.commit_receipt(terminal, receipt)
        return {
            "ok": bool(committed.get("ok") and result.get("ok")),
            "path": result.get("path"),
            "seq": result.get("seq"),
            "receipt": receipt.get("receipt_path"),
            "authority_status": (committed.get("decision") or {}).get("status"),
            "switchboard_receipt": committed.get("decision"),
        }
    except Exception as e:  # pragma: no cover
        return {"ok": False, "err": repr(e)}


def cycle(goal: str, rounds: int, participants: str | None, dry: bool,
          why: str = "", baseline_surface: str = "", baseline_answer: str = "") -> tuple[dict, Path]:
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    rec: dict = {"ts": ts, "goal": goal, "dry": dry, "steps": {}}

    rec["steps"]["select"] = _run(
        ["mag.ghost_memlance", "select", "--goal", goal, "--k", "8"], 120
    )

    if dry:
        rec["steps"]["salon"] = {"skipped": "dry"}
    else:
        args = ["mag.frontier_salon", "roundtable", goal, "--rounds", str(rounds)]
        if participants:
            args += ["--participants", participants]
        # Q-011 huang gate passthrough: the roundtable refuses to escalate without a stated why
        # plus a single-seat baseline, so the cycle carries them when the operator supplies any.
        if why:
            args += ["--why", why]
        if baseline_surface:
            args += ["--baseline-surface", baseline_surface]
        if baseline_answer:
            args += ["--baseline-answer", baseline_answer]
        rec["steps"]["salon"] = _run(args, 1800)

    rec["steps"]["water"] = _run(["mag.water_computer", "glass"], 60)

    ev = f"swarm_cycle:{_slug(goal)}:{ts}"
    rec["steps"]["chain"] = _run(["mag.verkle_lance", "link", "--event", ev], 60)

    rec["steps"]["render"] = _run(["mag.surface_render", "all"], 120)
    rec["steps"]["subchain"] = _run(["mag.party_subchain", "verify"], 60)

    rec["ok"] = all(
        s.get("ok", False)
        for k, s in rec["steps"].items()
        if not (dry and k == "salon")
    )

    rec["steps"]["blackboard"] = _blackboard_note(rec, ev)

    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{ts.replace(':', '')}-{_slug(goal)}.json"
    path.write_text(
        json.dumps(rec, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    return rec, path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="swarm-cycle")
    ap.add_argument("goal")
    ap.add_argument("--rounds", type=int, default=2)
    ap.add_argument("--participants", default=None)
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--why", default="", help="huang gate: why the escalation is justified")
    ap.add_argument("--baseline-surface", default="",
                    help="huang gate: seat consulted first as the single-seat baseline")
    ap.add_argument("--baseline-answer", default="", help="huang gate: what the baseline seat said")
    a = ap.parse_args(argv)
    rec, path = cycle(a.goal, a.rounds, a.participants, a.dry,
                      why=a.why, baseline_surface=a.baseline_surface,
                      baseline_answer=a.baseline_answer)
    slim = {
        k: (s.get("ok") if isinstance(s, dict) else s)
        for k, s in rec["steps"].items()
    }
    print(json.dumps({"ok": rec["ok"], "record": str(path), "steps": slim}, indent=2))
    return 0 if rec["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
