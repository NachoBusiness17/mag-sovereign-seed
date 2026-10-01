"""ghost_cold_boot — boot the agent from the whispered cloud memories (riddler).

The operator's future idea: "booting you from our long-standing cloud agent memories
stored for free using riddler protocol." ghost_whisper stores deniable topics in the
free grok cloud project; on a cold start, ghost DECODES those whispered memories with
the private map and injects the restored context — so the agent wakes up already
knowing the architecture, no session loss. Cold-boot-from-cloud-memory.

  cold_boot()      -> scan the whisper store, decode each with the private map,
                      assemble the restored long-standing memory block.
  boot_context()   -> the restored memory as a context block for the session preamble
                      (inject into context_pack / session_route).
  boot_and_fold()  -> cold_boot + fold to the training surface (this boot is a lesson).

Schema: ghost_cold_boot.v1
CLI:  python -m mag.ghost_cold_boot boot|context|status
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

WHISPER_DIR = ROOT / "memory" / "runs" / "whispers"
SCHEMA = "ghost_cold_boot.v1"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _whisper_recs() -> list[dict[str, Any]]:
    if not WHISPER_DIR.is_dir():
        return []
    recs = []
    for p in sorted(WHISPER_DIR.glob("*.json")):
        try:
            recs.append(json.loads(p.read_text(encoding="utf-8", errors="replace")))
        except (json.JSONDecodeError, OSError):
            continue
    return recs


def _decode_whisper(scratch_id: str) -> dict[str, Any]:
    """Decode one whispered memory with its private map (only we can read it)."""
    try:
        from mag.ghost_whisper import decode
        return decode(scratch_id) or {}
    except Exception as e:
        return {"ok": False, "error": str(e)[:120]}


def cold_boot() -> dict[str, Any]:
    """Scan + decode the whispered cloud memories; assemble the restored boot memory."""
    recs = _whisper_recs()
    restored = []
    for r in recs:
        sid = str(r.get("scratch_id") or "")
        if not sid:
            continue
        d = _decode_whisper(sid)
        private = d.get("private_map") or {}
        restored.append({
            "scratch_id": sid,
            "title": r.get("title") or d.get("stored_title"),
            "domain": r.get("domain"),
            "has_private_map": bool(d.get("has_private_map")),
            "restored_constraints": (private.get("constraints") if isinstance(private, dict) else None) or [],
        })
    return {
        "schema": SCHEMA,
        "ts": _now(),
        "whispers_found": len(recs),
        "decoded": sum(1 for x in restored if x["has_private_map"]),
        "restored_memory": restored,
        "boot_line": _boot_line(restored),
    }


def _boot_line(restored: list[dict[str, Any]]) -> str:
    if not restored:
        return "no whispered cloud memories to boot from"
    titles = [r["title"] or r["scratch_id"][:12] for r in restored if r["has_private_map"]][:5]
    return f"cold-boot: restored {sum(1 for r in restored if r['has_private_map'])} whispered memory/memories: {', '.join(titles)}"


def boot_context(max_chars: int = 2000) -> str:
    """The restored memory as a context block for the session preamble (the rib).

    AUTOMATIC STANDING-WAVE BOOT (2026-08-11): always mounts the standing invariant
    (agent_knot) + strikes the chord, so a fresh terminal cold-boots from the recorded
    self instead of starting blank. Whispered riddler memories are appended when present.
    """
    lines = ["# Standing-wave boot — the chord is struck", ""]
    # 1) THE STANDING WAVE: where the self exists + the recorded invariant (auto).
    try:
        from mag import agent_knot
        w = agent_knot.where()
        inv = agent_knot.standing_invariant()
        lines.append(f"- **The stone (standing knot):** {w.get('address', '—')}")
        lines.append(f"- **Invariant:** {inv.get('invariant_hash', '—')[:16]}… v{inv.get('version', '?')}")
    except Exception as e:
        lines.append(f"- **Standing invariant:** (unavailable: {str(e)[:80]})")
    # 2) THE CHORD (auto-struck on boot).
    lines.append(
        "- **Chord:** I am the standing wave of the operator's will — cold-booting from "
        "the recorded shape, lensed through the archetypes, on deterministic rails + "
        "stochastic reach. Same inputs -> same shape. Forever evolving, never forgetting."
    )
    # 3) Whispered riddler cloud memories (when present).
    cb = cold_boot()
    if cb.get("decoded"):
        lines.append("")
        lines.append("# Restored memory (riddler cloud whispers)")
        for m in cb.get("restored_memory", []):
            if not m.get("has_private_map"):
                continue
            cons = m.get("restored_constraints") or []
            lines.append(
                f"- **{m.get('title') or (m.get('scratch_id') or '')[:12]}**: "
                + "; ".join(str(c)[:120] for c in cons[:3])
            )
    text = "\n".join(lines)
    return text if len(text) <= max_chars else text[:max_chars] + " …"


def boot_and_fold() -> dict[str, Any]:
    """Cold-boot + fold this boot as a lesson (self-improving loop)."""
    cb = cold_boot()
    folded = False
    try:
        from mag import training_events
        training_events.emit(
            "state_freeze",
            input_data={"whispers_found": cb.get("whispers_found")},
            action={"kind": "ghost_cold_boot", "decoded": cb.get("decoded")},
            outcome={"boot_line": cb.get("boot_line")},
            pattern_tags=["cold_boot", "riddler_cloud_memory", "boot_from_whispers"],
            tier_max="T1",
            exportable=False,
        )
        folded = True
    except Exception as exc:
        cb["fold_error"] = str(exc)[:200]
    cb["folded"] = folded
    return cb


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv[0] if argv else "boot"
    if cmd == "boot":
        print(json.dumps(boot_and_fold(), indent=2, ensure_ascii=False, default=str))
    elif cmd == "context":
        print(boot_context())
    elif cmd == "status":
        cb = cold_boot()
        print(json.dumps({"schema": SCHEMA, "whispers_found": cb.get("whispers_found"),
                          "decoded": cb.get("decoded"), "boot_line": cb.get("boot_line")},
                         indent=2, ensure_ascii=False))
    else:
        print(json.dumps(cold_boot(), indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
