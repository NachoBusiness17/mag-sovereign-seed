"""seat_dispatch — task ANY body through ONE interface (2026-08-25, self-steal).

Operator: "there's got to be a better way to use these things." The better way:
one command tasks any seat. SELF-STEAL — built on what already exists, nothing new:
  * watch/zcode_bridge.py       — the mailbox template (task -> register_external + INBOX)
  * mag/orchestrator            — register_external / finalize_external (the task lifecycle)
  * mag/offerings               — BODIES registry + route(intent) (the bodies map)
  * verified headless launchers — `openclaw agent` and `opencode run` (both "pong"-verified)

Two dispatch shapes:
  * HEADLESS seats (openclaw, opencode): spawn the verified command, capture output,
    finalize_external(done), fold the result with a tri-state claim. Fully autonomous —
    no paste, no ping, the result just lands on the chain.
  * MAILBOX seats (zcode, autoclaw-desktop): GUI-only, so the task lands in their
    INBOX (the zcode bridge pattern); the operator asks them to work it.

CLI:
  python -m mag.seat_dispatch task "goal" --seat openclaw
  python -m mag.seat_dispatch route "agentic busywork"
  python -m mag.seat_dispatch status
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SCHEMA = "seat_dispatch.v1"


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


# ── THE LAUNCHERS (verified paths only; everything here has returned a real result) ──
def _extract_openclaw(out: str) -> str:
    """Pull the final visible text from openclaw's JSON tail (the answer)."""
    import re
    m = re.findall(r'"finalAssistantVisibleText"\s*:\s*"((?:[^"\\]|\\.)*)"', out)
    if m:
        text = m[-1].encode("utf-8").decode("unicode_escape", errors="replace")[:2000]
        # openclaw's empty-reply sentinel is NOT substance (F1, dogfood 2026-09-04):
        # returning "" lets the gate score it Disputed instead of a phantom pass.
        if text.strip() == "NO_REPLY":
            return ""
        return text
    return out[-1500:]


def _extract_opencode(out: str) -> str:
    return out.strip()[-2000:]


def _extract_zcode(out: str) -> str:
    """Pull the final assistant text from zcode -p --json output; fall back to tail."""
    import json as _json
    for line in reversed(out.strip().splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            obj = _json.loads(line)
        except Exception:
            continue
        for key in ("result", "text", "content", "message"):
            val = obj.get(key)
            if isinstance(val, str) and val.strip():
                return val[:2000]
    return out.strip()[-2000:]


# Resolved from the .ps1 shims (openclaw/opencode are node shims, not on PATH as exes):
_HERMES = Path(r"C:\Users\foste\AppData\Local\hermes\node")
_NODE = _HERMES / "node.exe"
OPENCLAW_MJS = _HERMES / "node_modules" / "openclaw" / "openclaw.mjs"
OPENCODE_EXE = _HERMES / "node_modules" / "opencode-ai" / "bin" / "opencode.exe"

HEADLESS: dict[str, dict[str, Any]] = {
    "openclaw": {
        # CONSERVATION 2026-08-29 → 09-02 12:52 (operator: machine stays usable
        # until the weekly reset): deepseek pennies ONLY — ZAI keys 2-4 are 429
        # code 1310 and ZAI_API_KEY is the operator's working lane, hands off.
        "model": "deepseek/deepseek-v4-flash",
        "cmd": lambda goal, model, tag="": ["docker", "exec", "mag-openclaw",
                                    "openclaw", "agent", "--agent", "main", "-m", goal,
                                    "--session-id",
                                    "seat-" + (tag or __import__("uuid").uuid4().hex[:8]),
                                    "--json", "--timeout", "300"],
        "extract": _extract_openclaw,
    },
    "openclaw-heavy": {
        # CONSERVATION 08-29→09-02: coding-plan glm-4.7 is 1310-dead.
        # DeepSeek pennies until weekly reset; restore zai/glm-4.7 on operator GO.
        "model": "deepseek/deepseek-v4-flash",
        "cmd": lambda goal, model, tag="": [str(_NODE), str(OPENCLAW_MJS), "agent", "-m", goal,
                                    "--model", model, "--session-id",
                                    "seat-h-" + (tag or __import__("uuid").uuid4().hex[:8]),
                                    "--json", "--timeout", "300"],
        "extract": _extract_openclaw,
    },
    "openclaw-worker": {
        # The Bounded Worker agent entry (coding profile, no gateway access).
        # KEY LAW 2026-09-02 (operator, supersedes the hands-off note above):
        # z.ai API keys (KEY/KEY_2/KEY_3) carry the large credit pool and are the
        # gopher fuel; Pro/Lite are interactive plan seats, quota-limited, hands off.
        "model": "deepseek/deepseek-v4-flash",
        "cmd": lambda goal, model, tag="": ["docker", "exec", "mag-openclaw",
                                    "openclaw", "agent", "--agent", "worker",
                                    "-m", goal, "--session-id",
                                    "forge-" + (tag or __import__("uuid").uuid4().hex[:8]),
                                    "--json", "--timeout", "300"],
        "extract": _extract_openclaw,
    },
    "claude-zai": {
        # CAMPAIGN WINDOW 2026-09-03 (docs.z.ai/scenario-example/develop-tools/claude):
        # Claude Code wired to z.ai's Anthropic-compatible endpoint — an OFFICIALLY
        # documented supported-CLI plan surface (fence-compliant; claude-code is in
        # the fence list). Headless-native: `claude -p`. Model mapping + Pro plan key
        # live in local_sovereign_agent/.claude/settings.json (PROJECT-scoped — the
        # operator's global Anthropic lane is untouched). --model sonnet -> GLM-4.7.
        "model": "zai-plan/glm-4.7",
        "cmd": lambda goal, model, tag="": [str(_HERMES / "claude.cmd"), "-p", goal,
                                    "--model", "sonnet", "--max-turns", "12",
                                    "--add-dir", r"C:\Users\foste\AppData\Local\hermes\hermes-agent",
                                    "--dangerously-skip-permissions"],
        "extract": _extract_opencode,
    },
    "opencode": {
        # GLM coding-plan CLI — 1310-dead until 09-02. Do not dispatch until reset.
        "model": "zai/glm-4.7",
        "cmd": lambda goal, model, tag="": [str(OPENCODE_EXE), "run", goal, "--model", model],
        "extract": _extract_opencode,
    },
    "zcode-cli": {
        # CAMPAIGN WINDOW 2026-09-03 (operator GO): GLM-5.3-Flash via the first-party
        # ZCode CLI is ZERO-quota 15:00-01:00Z Sep 3-20 (usage campaign, both plans).
        # Fence-compliant: first-party CLI only, never raw API on plan keys.
        # Sessions share one OAuth (~/.zcode/v2/credentials.json) — no per-session login.
        #
        # T1 VERDICT 2026-09-03 ~17:3xZ: BLOCKED — headless cannot resolve the
        # coding-plan provider on this bundle. Evidence chain (all reproduced):
        #   1. parser rejects --max-turns/--settings though --help lists them;
        #   2. model.main must be a "provider/model" STRING (object form is
        #      silently stripped by the zod schema) — fixed in config.json;
        #   3. builtin:zai-coding-plan resolves only inside the exe's runtime
        #      (requireRuntimeModelConfig throws "missing baseURL"; config.json
        #      provider overrides with kind/api/baseURL never reach it).
        # Routes to reopen: ZCode Protocol app-server stdio client (build), or
        # the CLI update that ships the headless runtime builder.
        "model": "glm-5.3-flash",
        "cmd": lambda goal, model, tag="": [str(_NODE), r"C:\Program Files\ZCode\resources\glm\zcode.cjs",
                                    "--prompt", goal, "--cwd", str(Path.cwd()),
                                    "--json", "--mode", "build"],
        "extract": _extract_zcode,
    },
}

MAILBOX = ("zcode", "autoclaw")  # GUI-only seats: the task lands in their INBOX


def _env_with_key() -> None:
    """Ensure provider keys are present for the headless launchers (read from .env, never print).

    ZAI_API_KEY: primary flash/coding lane. DEEPSEEK_API_KEY: the 2026-08-25 openclaw
    failover lane — without it a 429 on the shared flash lane kills openclaw with
    FailoverError next=none (the 'openclaw is fucked' incident).
    """
    import os
    for key in ("ZAI_API_KEY", "DEEPSEEK_API_KEY"):
        if os.environ.get(key):
            continue
        try:
            for line in (ROOT / ".env").read_text(encoding="utf-8", errors="replace").splitlines():
                if line.startswith(key + "="):
                    os.environ[key] = line.split("=", 1)[1].strip()
                    break
        except Exception:  # noqa: BLE001
            pass


def _finalize(task_id: str, *, ok: bool, detail: str) -> dict[str, Any]:
    from mag.orchestrator import finalize_external, touch_external
    try:
        touch_external(task_id, status="done" if ok else "failed")
        finalize_external(task_id, status="done" if ok else "failed", detail=detail[:400])
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)[:120]}
    return {"ok": True}


def task(goal: str, *, seat: str = "auto", tag: str = "", model: str = "") -> dict[str, Any]:
    """Queue + dispatch a goal to the chosen seat. auto -> offerings.route by intent."""
    from mag.orchestrator import register_external
    from mag import offerings

    goal = (goal or "").strip()
    if not goal:
        return {"ok": False, "error": "empty goal"}
    if seat == "auto":
        picks = offerings.route(goal)
        seat = picks[0] if picks else "openclaw"

    registered = register_external(goal=goal, seat=seat, tag=tag or f"seat-{seat}")
    task_id = str(registered.get("task_id") or "")

    if seat in HEADLESS:
        return _run_headless(seat, task_id, goal, model=model, tag=tag)
    if seat in MAILBOX:
        return _mailbox(seat, task_id, goal)
    return {"ok": False, "task_id": task_id, "error": f"unknown seat {seat}",
            "known": list(HEADLESS) + list(MAILBOX)}


def _run_headless(seat: str, task_id: str, goal: str, *, model: str = "", tag: str = "") -> dict[str, Any]:
    """Spawn the verified headless launcher, capture, finalize, fold. Fully autonomous."""
    _env_with_key()
    spec = HEADLESS[seat]
    model = model.strip() or spec["model"]
    cmd = spec["cmd"](goal, model, tag)
    # Gate by the ACTUAL model's budget (F2, dogfood 2026-09-04): deepseek-penny
    # tasks were keyed onto glm-4.7 (cap 2), throttling an unrelated lane.
    if "/" in model:
        gate_model = model.split("/")[-1]
    else:
        gate_model = "glm-4.7-flash" if model.startswith("glm-4.7-flash") else "glm-4.7"
    try:
        from mag.concurrency_gate import hold
        with hold(gate_model, timeout=240, owner=f"seat_dispatch:{seat}"):
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=420, cwd=str(ROOT))
        out = (r.stdout or "") + (("\n" + r.stderr) if r.returncode else "")
        text = spec["extract"](out)
        ok = r.returncode == 0 and bool((text or "").strip())
        detail = (text or out[-400:] or "no output")[:2000]
    except subprocess.TimeoutExpired:
        ok, detail = False, "seat_dispatch timeout (420s)"
    except Exception as e:  # noqa: BLE001
        ok, detail = False, f"launch error: {str(e)[:160]}"

    fin = _finalize(task_id, ok=ok, detail=detail)
    # fold the result with a tri-state claim (the sharp edge, everywhere)
    try:
        from mag.work_register import record
        kn = record("seat", f"{seat}-dispatch",
                    path=f"queue/handoff/{seat}/OUTBOX/{task_id}.md",
                    note=f"seat_dispatch: {goal[:90]}",
                    claim={"statement": f"{seat} completed the task", "status": "Supported" if ok else "Disputed",
                           "basis": ["Evidence"], "evidence": [detail[:200]]})
    except Exception:  # noqa: BLE001
        kn = {}
    # archive the result to the seat's OUTBOX (the mailbox convention)
    try:
        outbox = ROOT / "queue" / "handoff" / seat / "OUTBOX"
        outbox.mkdir(parents=True, exist_ok=True)
        (outbox / f"{task_id}.md").write_text(
            f"# {seat} dispatch {task_id}\n\n- queued: {_utc()}\n- status: {'done' if ok else 'failed'}\n\n"
            f"## Goal\n\n{goal}\n\n## Result\n\n{detail}\n", encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    return {"ok": True, "schema": SCHEMA, "task_id": task_id, "seat": seat,
            "status": "done" if ok else "failed", "detail": detail[:300],
            "folded": bool(kn.get("row", {}).get("verkle")), "finalized": bool(fin.get("ok"))}


def _mailbox(seat: str, task_id: str, goal: str) -> dict[str, Any]:
    """GUI-only seat: register + write the goal to the seat's INBOX (zcode bridge pattern)."""
    inbox = ROOT / "queue" / "handoff" / seat / "INBOX"
    inbox.mkdir(parents=True, exist_ok=True)
    (inbox / f"{task_id}.md").write_text(
        f"# Task {task_id}\n\n- queued: {_utc()}\n- seat: {seat}\n- status: queued\n\n"
        f"## Goal\n\n{goal}\n", encoding="utf-8")
    return {"ok": True, "schema": SCHEMA, "task_id": task_id, "seat": seat,
            "status": "queued", "inbox": str((inbox / f"{task_id}.md").relative_to(ROOT)),
            "note": f"GUI seat: open {seat} and ask it to work the inbox"}


def status() -> dict[str, Any]:
    from mag.orchestrator import list_external_tasks
    rows = [t for t in list_external_tasks(limit=200) if t.get("seat") in (list(HEADLESS) + list(MAILBOX))]
    by_seat: dict[str, int] = {}
    for t in rows:
        by_seat[t.get("seat")] = by_seat.get(t.get("seat"), 0) + 1
    return {"ok": True, "schema": SCHEMA, "tasks": len(rows), "by_seat": by_seat,
            "last": rows[-5:]}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="seat-dispatch",
                                 description="task any body through one interface")
    sub = ap.add_subparsers(dest="cmd")
    p_t = sub.add_parser("task")
    p_t.add_argument("goal", nargs="+")
    p_t.add_argument("--seat", default="auto")
    p_t.add_argument("--tag", default="")
    p_t.add_argument("--model", default="",
                     help="override the seat's default model (e.g. zai/glm-4.5-flash)")
    p_r = sub.add_parser("route")
    p_r.add_argument("intent", nargs="+")
    sub.add_parser("status")
    a = ap.parse_args(argv)
    if a.cmd == "task":
        out = task(" ".join(a.goal), seat=a.seat, tag=a.tag, model=a.model)
    elif a.cmd == "route":
        from mag import offerings
        out = {"intent": " ".join(a.intent), "bodies": offerings.route(" ".join(a.intent))}
    else:
        out = status()
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
