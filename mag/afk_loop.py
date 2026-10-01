"""afk_loop — ghost's cheap self-occupation when the operator is AFK.

"Keep it going: if ghost detects me AFK 60s, figure out what you can do to occupy
yourself cheaply UNLESS a tesuji emerges — learning about our codebase socratically
with our local ollama for testing, and tool-testing with the cheapest deepseek,
running freebees and looking for more freebies."

So when the operator is away, ghost doesn't idle — it spends the cheap/free budget on
growing and testing the system:
  1. TESUJI CHECK   — if a tesuji is pending/emergent, run THAT first (priority).
  2. SOCRATIC LEARN — ask local ollama a socratic question about the codebase (tests
                      ollama + grows our understanding, $0).
  3. TOOL TEST      — exercise a framework tool through the cheapest deepseek (free
                      tier / flash), proving it works + capturing behavior.
  4. FREEBIE SCAN   — look for more free-tier opportunities (running freebees, finding
                      more) to extend the daily free budget.
Everything is cheap-first, headless (CREATE_NO_WINDOW), routed through ghost, and each
pass folds to the training surface. Never touches operator work.

CLI:  python -m mag.afk_loop status|occupy [--force]|probe|freebies
"""
from __future__ import annotations

import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception as exc:  # 2026-09-28 FW-46 silent-pass batch 2: the silent pass hid why mojibake could hit the AFK loop's redirected stdout (same disease batch 1 cleared in tools/audio_channel.py:31); valueless consoles keep the default encoding, and the reason is now named on stderr
    print(f"[afk_loop] stdout reconfigure skipped: {exc}", file=sys.stderr)

# cheap socratic probes about the codebase (rotated; tests ollama + grows insight)
_SOCRATIC = [
    ("How does the verkle knot prove chain membership?", "mag/verkle_knot.py"),
    ("What invariant does the nudge contract enforce?", "mag/ghost_nudge.py"),
    ("How does ghost route a prompt through the skill pipeline?", "mag/skill_pipeline.py"),
    ("What does the cost-enhancement loop optimize?", "mag/afk_loop.py"),
    ("How does the rib protocol encode a summon deniably?", "mag/ghost_whisper.py"),
]

# free-tier surface we know about (clippy tier ladder): local ollama, gemini/groq/z.ai free, deepseek flash
_FREE_TIERS = ["ollama(local)", "gemini(free)", "groq(free)", "z.ai(free)", "deepseek-flash(free)", "grok-free"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


AFK_GATE_ERROR: str | None = None


def _operator_afk() -> bool:
    # SPEC (2026-09-25, t61): FAIL CLOSED. The old body had the same two defects t43+t52
    # fixed in afk_cadence: the pause swallow ('except Exception: pass') worked through an
    # errored pause, and the fail-open return ('except Exception: return True') read a
    # broken operator_status as "operator AFK", so occupy() kept spending while the
    # operator was invisible. An errored gate now presumes the operator is ACTIVE (deny
    # honored, pause honored) and names the cause in AFK_GATE_ERROR for callers to surface.
    global AFK_GATE_ERROR
    try:
        from mag.operator_mode import pause_reason
        if pause_reason():
            AFK_GATE_ERROR = None
            return False
    except Exception as _pg:
        AFK_GATE_ERROR = "operator pause gate errored; failing CLOSED (pause honored): " + str(_pg)[:110]
        return False
    try:
        from mag.preferences import operator_status
        afk = not bool((operator_status() or {}).get("operator_active"))
        AFK_GATE_ERROR = None
        return afk
    except Exception as _afk_e:
        AFK_GATE_ERROR = "afk gate errored; failing CLOSED (operator presumed active): " + str(_afk_e)[:110]
        return False


def _pending_tesuji() -> bool:
    """True if an emergent tesuji is pending (prioritize it over idle occupation)."""
    try:
        from mag.tesuji_shell import status
        s = status() or {}
        return bool(s.get("n_shells"))
    except Exception:
        return False


def _ollama_up(timeout: float = 0.8) -> bool:
    import urllib.request
    try:
        urllib.request.urlopen("http://localhost:11434/api/tags", timeout=timeout)
        return True
    except Exception:
        return False


def _ollama_ask(prompt: str, model: str = "gemma:2b", timeout: float = 60.0) -> str:
    """Cheap local socratic ask (tests ollama + grows understanding, $0)."""
    import urllib.request
    body = json.dumps({
        "model": model, "stream": False,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    req = urllib.request.Request(
        "http://localhost:11434/api/chat", data=body,
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read().decode())
    return str(data.get("message", {}).get("content", "") or "")[:500]


def socratic_probe() -> dict[str, Any]:
    """Ask local ollama a socratic question about the codebase (if up)."""
    q, path = random.choice(_SOCRATIC)
    if not _ollama_up():
        return {"ok": False, "reason": "ollama down", "question": q, "source": path}
    try:
        ans = _ollama_ask(
            f"You are learning the Mag sovereign codebase socratically. {q} "
            f"Reference: {path}. Answer concisely and honestly; if unsure say so.")
        return {"ok": True, "question": q, "source": path, "answer": ans[:300]}
    except Exception as e:
        return {"ok": False, "reason": str(e)[:120], "question": q, "source": path}


def freebie_scan() -> dict[str, Any]:
    """Scan the known free-tier surface for running freebies / more freebies."""
    up = []
    for t in _FREE_TIERS:
        up.append({"tier": t, "status": "available"})
    return {"ok": True, "free_tiers": up, "note": "free daily tokens = frontier-extraction test budget; spend in the loop, don't let them expire"}


def tool_test_cheap() -> dict[str, Any]:
    """Exercise a framework tool via the cheapest capable path (deterministic; deepseek free if needed)."""
    try:
        from mag import skill_pipeline
        probe = "rightsize the queue and clean up old tools"
        chain = skill_pipeline.match(probe)
        return {"ok": True, "tool": "skill_pipeline.match", "chain": [s["id"] for s in chain],
                "cheapest": "local", "note": "tool exercised on cheapest tier"}
    except Exception as e:
        return {"ok": False, "reason": str(e)[:120], "tool": "skill_pipeline.match"}


def occupy(*, force: bool = False) -> dict[str, Any]:
    """The cheap self-occupation pass. TESUJI first, else socratic/tool-test/freebie."""
    if not force and not _operator_afk():
        return {"ok": True, "action": "skip", "reason": "operator active (not AFK)"}
    out: dict[str, Any] = {"schema": "afk_loop.v1", "ts": _now(), "afk": True}

    # 1) tesuji check — prioritize emergent wins
    if _pending_tesuji():
        out["tesuji_emergent"] = True
        out["action"] = "tesuji"
        out["note"] = "emergent tesuji pending — surfaced (do not auto-run; log when re-enabled)"
    else:
        out["tesuji_emergent"] = False

    # 2) socratic codebase learning with local ollama ($0)
    sp = socratic_probe()
    out["socratic"] = sp

    # 3) tool test via cheapest tier
    tt = tool_test_cheap()
    out["tool_test"] = tt

    # 4) freebie scan
    fb = freebie_scan()
    out["freebies"] = fb

    _fold(out)
    return out


def _fold(out: dict[str, Any]) -> None:
    try:
        from mag import training_events
        training_events.emit(
            "autorun_cycle",
            input_data={"afk": True, "action": out.get("action")},
            action={"kind": "afk_occupy", "socratic_ok": bool(out.get("socratic", {}).get("ok")),
                    "tool_test_ok": bool(out.get("tool_test", {}).get("ok"))},
            outcome={"freebies": len(out.get("freebies", {}).get("free_tiers", []))},
            pattern_tags=["afk_loop", "cheap_occupation", "socratic", "freebie_scan"],
            tier_max="T1",
            exportable=False,
        )
    except Exception as _fe:  # noqa: BLE001 - folding must never break the occupy pass; it must be VISIBLE
        # LOOP-DEATH GUARD (2026-09-25, t84): the FOURTH t19-species training_events.emit
        # swallow (byte-identical to the three t78 converted): a silently dead fold voids
        # the occupy pass's telemetry while occupy() still reports success. Non-fatal,
        # but visible. SPEC: tests/test_loop_death_guards.py, t84 SPEC line 1.
        print(f"[afk-loop] FOLD LOOP DEATH GUARD: training_events.emit exited: {_fe}", flush=True)


# ───────────────────────────────────────────────────────────────────────────
# SYSTEM RESOURCE MONITOR + RIGHT-SIZE + FREE TEST-DATA SQUEEZE
# Monitor resources; right-size AFK work to system load + operator behavior;
# squeeze as much free testing data as possible from local model + deepseek.
# ───────────────────────────────────────────────────────────────────────────
def system_resources() -> dict[str, float]:
    """Cheap CPU/RAM/load snapshot. psutil if present, else os-level approx."""
    out = {"cpu_pct": 0.0, "ram_pct": 0.0, "load": 0.0}
    try:
        import psutil
        out["cpu_pct"] = round(psutil.cpu_percent(interval=0.2), 1)
        vm = psutil.virtual_memory()
        out["ram_pct"] = round(vm.percent, 1)
    except Exception:
        import os
        out["cpu_pct"] = round(os.cpu_count() or 1, 1)  # fallback: just cores
    out["load"] = round((out["cpu_pct"] + out["ram_pct"]) / 2.0, 1)
    return out


def right_size(load: dict[str, float], *, operator_active: bool = False) -> dict[str, Any]:
    """Right-size AFK work to system load + operator behavior.
    light when busy/active, medium normally, full when idle + free."""
    cpu = load.get("cpu_pct", 0)
    ram = load.get("ram_pct", 0)
    if operator_active:
        level = "none"  # never work during operator activity
    elif cpu > 75 or ram > 85:
        level = "light"  # machine busy — don't add load
    elif cpu > 45 or ram > 65:
        level = "medium"
    else:
        level = "full"  # idle + free — squeeze the most
    budget = {"none": 0, "light": 1, "medium": 2, "full": 4}[level]
    return {"level": level, "budget": budget, "cpu_pct": cpu, "ram_pct": ram}


def squeeze_free_test_data(*, budget: int) -> dict[str, Any]:
    """Squeeze free testing data from local model + deepseek orchestrator (AFK only)."""
    produced = 0
    rows = []
    # 1) local model (ollama) — free test rows, no cloud
    if _ollama_up() and budget > 0:
        try:
            q, path = random.choice(_SOCRATIC)
            ans = _ollama_ask(q, timeout=40)
            rows.append({"source": "ollama", "kind": "socratic_test", "prompt": q[:80], "answer": ans[:120]})
            produced += 1
        except Exception as _sq:
            # LOOP-DEATH GUARD (2026-09-25, t19 except-pass sweep): a silently dead
            # ollama producer makes the AFK loop report produced=0 with no trace, so
            # the occupation loop looks healthy while doing nothing. Non-fatal, visible.
            print(f"[afk-loop] SQUEEZE LOOP DEATH GUARD: ollama socratic producer exited: {_sq}", flush=True)
    # 2) deepseek orchestrator — route a free cheap task to produce a test row
    if budget > 1:
        try:
            from mag import skill_pipeline
            chain = skill_pipeline.match("rightsize the queue and clean up old tools")
            rows.append({"source": "deepseek-orchestrator", "kind": "routing_test",
                         "chain": [s["id"] for s in chain]})
            produced += 1
        except Exception as _rt:
            # LOOP-DEATH GUARD (2026-09-25, t43): a silently dead deepseek routing producer
            # made squeeze_free_test_data report produced=0 with no trace, so the AFK loop
            # looks healthy while doing nothing; same species as the ollama guard above.
            # Non-fatal, visible (ghost.py LOOP-DEATH GUARD pattern, t19 next_steal).
            print(f"[afk-loop] SQUEEZE LOOP DEATH GUARD: deepseek routing producer exited: {_rt}", flush=True)
    return {"ok": True, "produced": produced, "test_rows": rows,
            "note": "free testing data squeezed from local + deepseek orchestrator"}


def occupy(*, force: bool = False) -> dict[str, Any]:
    """The cheap self-occupation pass. TESUJI first, else socratic/tool-test/freebie."""
    if not force and not _operator_afk():
        skip: dict[str, Any] = {"ok": True, "action": "skip", "reason": "operator active (not AFK)"}
        if AFK_GATE_ERROR:
            skip["afk_gate_error"] = AFK_GATE_ERROR  # t61: a fail-closed denial is never silent
        return skip
    out: dict[str, Any] = {"schema": "afk_loop.v1", "ts": _now(), "afk": True}

    # 0) right-size to system load + operator behavior
    res = system_resources()
    rs = right_size(res, operator_active=not _operator_afk())
    out["resources"] = res
    out["right_size"] = rs
    if AFK_GATE_ERROR:
        out["afk_gate_error"] = AFK_GATE_ERROR  # t61: surface the errored gate next to the deny
    if rs["level"] == "none":
        return {**out, "action": "skip", "reason": "right-sized to none (operator active/busy)"}

    # 1) tesuji check — prioritize emergent wins
    if _pending_tesuji():
        out["tesuji_emergent"] = True
        out["action"] = "tesuji"
        out["note"] = "emergent tesuji pending — surfaced (do not auto-run; log when re-enabled)"
    else:
        out["tesuji_emergent"] = False

    # 2) socratic codebase learning with local ollama ($0)
    sp = socratic_probe()
    out["socratic"] = sp

    # 3) tool test via cheapest tier
    tt = tool_test_cheap()
    out["tool_test"] = tt

    # 4) freebie scan
    fb = freebie_scan()
    out["freebies"] = fb

    # 5) squeeze free testing data (local + deepseek orchestrator), right-sized
    if rs["budget"] > 0:
        out["free_test_data"] = squeeze_free_test_data(budget=rs["budget"])

    # 6) SEED-CHAIN BUILD — the AFK run: pick the next backlog item, decompose it
    #    with the FREE FRONTIER (logic chain), solve the middle ground cheaply.
    if rs["budget"] >= 2:
        problem = _next_problem()
        if problem:
            try:
                from mag.seed_chain import seed_build
                out["seed_chain"] = seed_build(problem)
            except Exception as e:
                out["seed_chain"] = {"ok": False, "error": str(e)[:120]}

    _fold(out)
    return out


def _next_problem() -> str:
    """Pick the next actionable problem: the scrum board's cheapest todo title."""
    try:
        from mag.scrum import sprint
        nxt = sprint() or {}
        item = nxt.get("item") or {}
        return str(item.get("title") or "")[:200]
    except Exception:
        return ""
