"""oh_fuck — the emergency "OH FUCK MODE" (panic button), memlang-steered + verkle-anchored.

When something is exploding (windows storm, runaway loop, resource meltdown), one command
brings the system to a safe state FAST — memlang as the primary operation vector for the
steering, verkle-anchored so the emergency is provable and replayable:

  1. KILL all Mag platform processes + container (platform_kill, headless).
  2. EMIT an emergency STEER packet + memlang `steer` token (compiled, verkle-anchored).
  3. RECORD the panic to memory/panic/ + a behavioral event (so the loop learns).
  4. LEAVE the system quiet (nothing respawns — loop_breaker + disabled tasks guard).

Schema: oh_fuck.v1
CLI:  python -m mag.oh_fuck "<reason>" [--dry]
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCHEMA = "oh_fuck.v1"
PANIC_DIR = ROOT / "memory" / "panic"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _memlang_steer(reason: str) -> dict[str, Any]:
    """Compile the emergency as a memlang `steer` token (verkle-anchored) + a STEER packet."""
    out: dict[str, Any] = {"memlang": None, "steer": None}
    try:
        from mag.memlang import compile_token
        out["memlang"] = compile_token("steer", f"OH_FUCK: {reason[:300]}")
    except Exception as e:
        out["memlang_error"] = str(e)[:120]
    try:
        from mag.steer import emit as steer_emit
        out["steer"] = steer_emit("oh-fuck", "panic", f"[STEER] OH_FUCK: {reason[:300]}",
                                  phases=["emergency", "safe_state"], steer_back=True)
    except Exception as e:
        out["steer_error"] = str(e)[:120]
    return out


def oh_fuck(reason: str = "emergency", *, dry: bool = False) -> dict[str, Any]:
    """Emergency mode: kill all platforms + emit memlang/steer + record panic."""
    reason = (reason or "emergency").strip()
    out: dict[str, Any] = {"schema": SCHEMA, "ts": _now(), "ok": True, "dry": dry,
                           "reason": reason[:300], "source": "oh_fuck"}

    # 1) kill all platforms + container (headless). Dry => report only.
    try:
        from mag.platform_kill import kill_all
        out["kill"] = kill_all(dry=dry)
    except Exception as e:
        out["kill_error"] = str(e)[:160]

    # 2) memlang-steer the emergency (only when actually firing, not dry)
    if not dry:
        out["steer"] = _memlang_steer(reason)

    # 2b) GHOST PARTNER STEERS GROK TO FIX IT (only on a real emergency, gated):
    # grok is the frontier fixer — but ONLY when grok_gate says it's cost-effective
    # + frontier-needed. Never ping deepseek for the fix; never idle-ping grok.
    try:
        from mag.grok_gate import should_use_grok
        gate = should_use_grok(reason)
        out["grok_gate"] = gate
        if gate.get("use_grok") and not dry:
            from mag.grok_rightsize import ghost_grok_task
            out["grok_fix"] = ghost_grok_task(f"FIX the emergency: {reason[:400]}")
        else:
            out["grok_fix"] = {"skipped": True, "reason": gate.get("reason", "")}
    except Exception as e:
        out["grok_fix_error"] = str(e)[:120]

    # 3) record the panic (behavioral event + panic file) — the loop learns.
    try:
        from mag.operator_inbox import log_behavioral_event
        log_behavioral_event(kind="oh_fuck", source="copilot-assistant", detail=reason[:300])
    except Exception as e:
        out["behavioral_error"] = str(e)[:120]
    if not dry:
        PANIC_DIR.mkdir(parents=True, exist_ok=True)
        (PANIC_DIR / f"panic_{_now()[:19].replace(':', '')}.json").write_text(
            json.dumps(out, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        (PANIC_DIR / "latest.json").write_text(
            json.dumps(out, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    out["note"] = "system brought to safe state; nothing respawns (loop_breaker + disabled tasks)"
    return out


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    dry = "--dry" in argv
    reason = " ".join(a for a in argv if not a.startswith("--")) or "emergency"
    print(json.dumps(oh_fuck(reason, dry=dry), indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
