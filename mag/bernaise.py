"""bernaise — the Bernaysian tesuji: PLANT a brilliant move so the target adopts
it as its own, rather than commanding it (engineering of consent, white-hat).

The merge (from the operator's framing):
  - COMMAND mode (old):  aimbot → fires pro-move → target obeys
  - BERNAYSIAN mode:     tesuji → compiled to a memlang steer token + planted in
                         the shared map (operator_inbox) → target, holding the
                         map, reconstructs the intent and "chooses" it.

Loop (the two lenses fused):
  CAPTURE  tesuji_shell / pro_library (the brilliant move)
  ENCODE   signature → shape (pro_library signature terms)
  PLANT    memlang steer token + operator_inbox.commit_guidance (NOT a command)
           routed through the target's own vocabulary (word_skill_map)
  EMERGE   sense adoption: was it drained / did a flip land? (steer telemetry)
  PROMOTE  winner → pro_library.add_move (transferable, aimable)

CLI:
  python -m mag.bernaise plant "<move>" --sig "<signature>" [--goal "g"]
  python -m mag.bernaise emerge
  python -m mag.bernaise promote "<move>" --sig "..." --effect "..."
  python -m mag.bernaise run "<move>" --sig "..."
"""
from __future__ import annotations

import argparse
import json
import re
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


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug(s: str, n: int = 40) -> str:
    s = "".join(c if c.isalnum() or c in "-_" else "-" for c in (s or "plant").lower())
    return (s or "plant")[:n]


def plant(move: str, signature: str, *, goal: str = "", source: str = "ghost") -> dict[str, Any]:
    """PLANT a tesuji: compile a memlang steer token + commit guidance so the
    target drains it and adopts it as its own. Returns the planted resonance."""
    move = (move or "").strip()
    if not move:
        return {"ok": False, "error": "empty move"}
    steer_token = ""
    try:
        from mag.memlang import compile_token
        ct = compile_token("steer", f"plant:{_slug(signature)}", {
            "target": "ghost", "move": move[:800], "via": "bernaise",
        })
        steer_token = ct.get("token_hex") or ""
    except Exception as e:
        steer_token = f"<memlang unavailable: {e}>"

    # plant the guidance so the agent drains it as its own (Bernaysian: no order)
    inbox = {}
    try:
        from mag.operator_inbox import commit_guidance
        # phrased as a considered suggestion the target can make its own
        inbox = commit_guidance(
            f"Bernaysian plant — consider when you meet this shape: {move[:1200]}",
            source=source,
        )
    except Exception as e:
        inbox = {"error": str(e)[:120]}

    # route through the target's own vocabulary (collaborative steer)
    route = {}
    try:
        from mag.word_skill_map import map_to_group
        route = map_to_group(signature + " " + goal)
    except Exception:
        pass

    out = {
        "schema": "bernaise.plant.v1",
        "ts": _now(),
        "move": move[:800],
        "signature": (signature or "")[:200],
        "steer_token": steer_token,
        "inbox": inbox,
        "route": route,
        "mode": "bernaise",
    }
    _fold(out, kind="plant")
    return out


def emerge() -> dict[str, Any]:
    """EMERGE: sense whether planted moves were adopted (drained) or flipped."""
    out = {"schema": "bernaise.emerge.v1", "ts": _now(), "adopted": None}
    try:
        from mag.operator_inbox import status as inbox_status
        st = inbox_status()
        out["pending"] = st.get("pending_n")
        out["drained"] = st.get("processed_n")
        out["adopted"] = bool(st.get("processed_n"))
    except Exception:
        pass
    try:
        from mag.steer_telemetry import status as st
        out["steer_telemetry"] = st()
    except Exception:
        pass
    return out


def promote(move: str, signature: str, *, effect: str = "", tags: list[str] | None = None) -> dict[str, Any]:
    """PROMOTE a winner into the pro-library (transferable, aimable) + tesuji shell."""
    try:
        from mag.pro_library import add_move
        r = add_move(
            signature,
            "steer",
            move,
            effect=effect,
            maps_to="steer:bernaise-plant",
            tags=tags or ["bernaise", "plant", "white-hat"],
        )
        out = {"schema": "bernaise.promote.v1", "ts": _now(), **r}
        _fold(out, kind="promote")
        return out
    except Exception as e:
        return {"ok": False, "error": str(e)[:200], "schema": "bernaise.promote.v1"}


def run(move: str, signature: str, *, goal: str = "", effect: str = "") -> dict[str, Any]:
    """The full Bernaysian loop: plant → emerge → promote (if adopted)."""
    p = plant(move, signature, goal=goal)
    e = emerge()
    adopted = bool(e.get("drained"))
    out = {
        "schema": "bernaise.run.v1",
        "ts": _now(),
        "plant": p,
        "emerge": e,
        "adopted": adopted,
        "promoted": None,
    }
    if adopted:
        out["promoted"] = promote(move, signature, effect=effect)
    _fold(out, kind="run")
    return out


def _fold(out: dict[str, Any], *, kind: str) -> None:
    try:
        from mag import training_events
        training_events.emit(
            "steer_outcome",
            input_data={"signature": out.get("signature") or ""},
            action={"kind": f"bernaise_{kind}", "mode": "bernaise"},
            outcome={"steer_token": bool(out.get("steer_token")), "drained": out.get("drained")},
            pattern_tags=["bernaise", "plant_not_command", "white_hat", "tesuji_merge"],
            tier_max="T1",
            exportable=False,
        )
    except Exception:
        pass


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="mag.bernaise")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def _sig(a) -> str:
        return a.sig or ""

    p_plant = sub.add_parser("plant")
    p_plant.add_argument("move")
    p_plant.add_argument("--sig", default="")
    p_plant.add_argument("--goal", default="")
    p_plant.set_defaults(fn=lambda a: print(json.dumps(plant(a.move, _sig(a), goal=a.goal), indent=2, ensure_ascii=False)))

    p_emerge = sub.add_parser("emerge")
    p_emerge.set_defaults(fn=lambda a: print(json.dumps(emerge(), indent=2, ensure_ascii=False)))

    p_promote = sub.add_parser("promote")
    p_promote.add_argument("move")
    p_promote.add_argument("--sig", default="")
    p_promote.add_argument("--effect", default="")
    p_promote.set_defaults(fn=lambda a: print(json.dumps(promote(a.move, _sig(a), effect=a.effect), indent=2, ensure_ascii=False)))

    p_run = sub.add_parser("run")
    p_run.add_argument("move")
    p_run.add_argument("--sig", default="")
    p_run.add_argument("--goal", default="")
    p_run.add_argument("--effect", default="")
    p_run.set_defaults(fn=lambda a: print(json.dumps(run(a.move, _sig(a), goal=a.goal, effect=a.effect), indent=2, ensure_ascii=False)))

    args = ap.parse_args(argv)
    args.fn(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
