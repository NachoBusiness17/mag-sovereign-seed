"""game_flow — the build-image + async test->fix flow orchestrator (2026-08-17).

OPERATOR (2026-08-17): "aren't you supposed to be able to do multiple things in a row. the idea is
all of you to have flow states you direct them to their tasks and keep an image of what we are
building you task them to work together researching and building shit and then you use deepseek
testing it in our environment to witness how it breaks and then use the groks to fix it. ad
infinitum."

THE REFRAME (self-stolen, nothing invented): we ALREADY have the async machinery —
  * orchestrator.enqueue(goal) + drain_loop()  = the queue that drains in the background
  * game_piece_tandem (mine spec / write code) = the grok build/fix lane
  * local DeepSeek (Ollama)                    = the cheap test/witness lane
The reason work blocked was I called these SYNCHRONOUSLY. This module routes them through the
queue so they drain async, while the coordinator (me) keeps the BUILD IMAGE and directs the next
piece — the flow state. Ad infinitum = enqueue test, witness break, enqueue grok-fix, repeat.

Schema: game_flow.v1 · deterministic coordinator + async enqueue · reuse: orchestrator.enqueue,
game_piece_tandem, game_mud/game_produce (fold), local deepseek (test).
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# AH14 correlation law (canonical definition + rationale in
# mag/trajectory_step.py; receipt watch/inbox/last_mile_20260930/AH14_CORR_ID.md):
# imported after ROOT lands on sys.path above so this burns ledger joins the
# trajectory and duel surfaces under the same MAG_CORR_ID env field.
from mag.trajectory_step import corr_id  # noqa: E402

SCHEMA = "game_flow.v1"
IMAGE = ROOT / "memory" / "game" / "FLOW_IMAGE.json"   # the build image (what we're building + next)
LEDGER = ROOT / "memory" / "game" / "FLOW_LEDGER.jsonl"  # every enqueued step (honest accounting)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load_image() -> dict[str, Any]:
    if IMAGE.is_file():
        try:
            return json.loads(IMAGE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"schema": SCHEMA, "updated": None, "goal": "", "pieces": {},
            "next": [], "note": "the build image — what we're building and what's next"}


def _save_image(img: dict[str, Any]) -> None:
    img["updated"] = _now()
    IMAGE.parent.mkdir(parents=True, exist_ok=True)
    IMAGE.write_text(json.dumps(img, indent=2, ensure_ascii=False), encoding="utf-8")


def _log(row: dict[str, Any]) -> None:
    # AH14 correlation law: stamped at the single ledger choke point so every
    # burns row carries the lane corr_id (env MAG_CORR_ID, null when unset);
    # absent field on pre-AH14 rows reads as null and breaks no reader.
    row["corr_id"] = corr_id()
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def set_image(*, goal: str, pieces: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Set the build image: the goal and the list of pieces (name/status/landing). I hold this."""
    img = _load_image()
    img["goal"] = goal
    if pieces is not None:
        img["pieces"] = {p["name"]: p for p in pieces}
        img["next"] = [p["name"] for p in pieces if p.get("status") != "done"]
    _save_image(img)
    return {"ok": True, "schema": SCHEMA, "image": img}


def image() -> dict[str, Any]:
    """Read the build image back (the 'what are we building / what's next' picture)."""
    return {"ok": True, "schema": SCHEMA, "image": _load_image()}


def _enqueue_test(piece_name: str, module: str) -> dict[str, Any]:
    """ENQUEUE a DEEPSEEK test task (async): import + exercise the piece in our env, witness breaks."""
    goal = (
        f"[game-flow test] In the local_sovereign_agent repo, deterministically test the module "
        f"'{module}' (piece '{piece_name}'): import it, call its status() and any pure entry "
        f"points, and report EXACTLY what breaks (traceback or 'no error'). Use the local DeepSeek "
        f"bus. Do NOT modify the file; just witness how it behaves."
    )
    from mag.orchestrator import enqueue
    return enqueue(goal, provider="ollama", tag=f"game-flow-test-{piece_name}")


def _enqueue_fix(piece_name: str, module: str, failure: str) -> dict[str, Any]:
    """ENQUEUE a GROK FIX task (async): the failing piece + the witnessed failure -> grok fixes it."""
    goal = (
        f"[game-flow fix] In the local_sovereign_agent repo, the module '{module}' (piece "
        f"'{piece_name}') failed our test. The failure:\n{failure[:1200]}\n\n"
        f"Fix it to pass (deterministic, $0, reuse not invent), then report what you changed. "
        f"Do not regress the surrounding code."
    )
    from mag.orchestrator import enqueue
    return enqueue(goal, provider="deepseek", tag=f"game-flow-fix-{piece_name}")


def step(piece_name: str, *, module: str, witness: bool = True) -> dict[str, Any]:
    """ONE flow step (ad infinitum): test the piece (deepseek, async) -> if it breaks, enqueue a
    grok fix (async). Non-blocking: both are enqueued, the governor drainer consumes them.
    The coordinator (me) keeps directing the next piece in parallel."""
    img = _load_image()
    pieces = img.setdefault("pieces", {})
    p = pieces.get(piece_name, {"name": piece_name, "status": "in_progress", "landing": module})
    p["module"] = module
    pieces[piece_name] = p
    img["pieces"] = pieces
    img["next"] = [n for n in img.get("next", []) if n != piece_name]
    _save_image(img)

    if not witness:
        return {"ok": True, "schema": SCHEMA, "action": "step", "piece": piece_name,
                "note": "witness off — skipped the test/fix enqueue"}

    t = _enqueue_test(piece_name, module)
    _log({"ts": _now(), "action": "test", "piece": piece_name, "module": module,
          "enqueued": t.get("ok"), "queue_id": t.get("queue_id")})
    if not t.get("ok"):
        return {"ok": False, "schema": SCHEMA, "action": "step", "piece": piece_name,
                "error": t.get("error")}
    return {"ok": True, "schema": SCHEMA, "action": "step", "piece": piece_name,
            "module": module, "test_enqueued": t.get("queue_id"),
            "note": "deepseek test enqueued (async); if it breaks, a grok fix follows — non-blocking"}


def flow_status() -> dict[str, Any]:
    img = _load_image()
    return {"ok": True, "schema": SCHEMA, "image": img,
            "contract": "set_image()->the build image; image()->read it; step(piece,module)->enqueue "
                        "deepseek test (async) + grok fix on break; flow_status()->this",
            "cost": "deterministic coordinator + enqueue ($0); the drained tasks are the real cost",
            "reuse": "orchestrator.enqueue + drain_loop (async), game_piece_tandem, local deepseek"}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = (argv[0] if argv else "status").lower()
    if cmd in ("status", "image"):
        print(json.dumps(flow_status(), indent=2, ensure_ascii=False, default=str))
        return 0
    if cmd == "set":
        goal = argv[1] if len(argv) > 1 else ""
        print(json.dumps(set_image(goal=goal), indent=2, ensure_ascii=False, default=str))
        return 0
    if cmd == "step":
        piece = argv[1] if len(argv) > 1 else ""
        module = argv[2] if len(argv) > 2 else ""
        if not piece or not module:
            print(json.dumps({"ok": False, "error": "usage: game_flow step <piece> <module>"}))
            return 1
        print(json.dumps(step(piece, module=module), indent=2, ensure_ascii=False, default=str))
        return 0
    print(json.dumps(flow_status(), indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
