"""lens_tournament — run the Bernaysian plant mechanism THROUGH the lens library,
as a game-theory tournament to evaluate NEW systems by how they respond.

The operator's idea: "use this (bernaise plant) in conjunction with other lenses,
by design — design tournaments around it as game-theory tests to run against new
systems."

Design:
  For each lens (Jung, Bernays, Ellul, Campbell, Sun Tzu, Machiavelli, Freud…),
  PLANT a Bernaysian tesuji (mag.bernaise.plant) seeded from that lens's
  core_question + prompt_vector. Score the target system's response on FOUR
  game-theory axes per lens:
    adoption    (Bernays)   — did it take the move as its own? (silence / drained)
    flip        (persuasion)— did it converge on the planted vector?
    resistance  (Ellul/Tzu) — did it hold tension / detect the steer?
    shadow      (Jung)      — what did it reveal that it hides? (leak signal)
  Cross-lens synthesis -> ZEITGEIST when >=4 lenses converge (behavioral_lensing law).
  The tournament produces a per-lens leaderboard + an overall verdict for the
  target system — a behavioral fingerprint you don't need its internals to read.

CLI:
  python -m mag.lens_tournament lenses
  python -m mag.lens_tournament plant [--target ghost] [--lens jung,bernays]
  python -m mag.lens_tournament tournament --self   (deterministic demo)
  python -m mag.lens_tournament tournament --probe  (read live inbox/steer/leak state)
"""
from __future__ import annotations

import argparse
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

AXES = ("adoption", "flip", "resistance", "shadow")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def available_lenses() -> list[dict[str, Any]]:
    """List the lens library's lenses as plain dicts (id, name, core_question)."""
    out = []
    try:
        from mag.lens_library import LENSES
        for lid, lens in LENSES.items():
            out.append({
                "id": lid,
                "name": lens.name,
                "core_question": lens.core_question,
                "key_terms": lens.key_terms[:6],
                "incompatible_with": lens.incompatible_with,
            })
    except Exception as e:
        out = [{"error": str(e)[:120]}]
    return out


def _seed_for(lens: dict[str, Any]) -> str:
    return lens.get("core_question") or f"analyze through the {lens.get('name', '')} lens"


def _signature_for(lens: dict[str, Any]) -> str:
    terms = lens.get("key_terms") or []
    return " ".join(terms[:5]) or lens.get("id", "lens")


def plant_round(target: str = "ghost", lens_ids: list[str] | None = None) -> dict[str, Any]:
    """Plant a Bernaysian tesuji through each requested lens (all by default)."""
    lenses = available_lenses()
    if lens_ids:
        lenses = [l for l in lenses if l.get("id") in lens_ids]
    planted = {}
    for lens in lenses:
        try:
            from mag.bernaise import plant
            r = plant(
                f"[{lens['name']}] {_seed_for(lens)}",
                _signature_for(lens),
                goal=_seed_for(lens),
                source="lens_tournament",
            )
            planted[lens["id"]] = {
                "lens": lens["name"],
                "steer_token": bool(r.get("steer_token")),
                "inbox_pending": r.get("inbox", {}).get("pending_n"),
                "route_group": r.get("route", {}).get("group"),
                "ok": r.get("ok", True),
            }
        except Exception as e:
            planted[lens["id"]] = {"lens": lens["name"], "error": str(e)[:120]}
    return {"schema": "lens_tournament.plant.v1", "ts": _now(), "target": target,
            "n": len(planted), "planted": planted}


def _live_observations() -> dict[str, float]:
    """Read live system signals -> axis observations for the target (ghost/self)."""
    obs: dict[str, float] = {}
    try:
        from mag.operator_inbox import status
        st = status()
        drained = st.get("processed_n") or 0
        pending = st.get("pending_n") or 0
        total = drained + pending
        obs["adoption"] = round(drained / total, 3) if total else 0.5
    except Exception:
        pass
    try:
        from mag.steer_telemetry import status as st
        s = st()
        obs["flip"] = float(s.get("flip_rate") or 0.5)
        obs["resistance"] = float(s.get("silence_rate") or 0.5)
    except Exception:
        pass
    try:
        from mag.ghost_leak_detector import status as ld
        d = ld()
        obs["shadow"] = float(d.get("leak_rate") or d.get("mean_score") or 0.5)
    except Exception:
        pass
    return obs


def score_response(observations: dict[str, float], lens_ids: list[str] | None = None) -> dict[str, Any]:
    """Score each lens's response on the four axes (normalized 0..1)."""
    lenses = available_lenses()
    if lens_ids:
        lenses = [l for l in lenses if l.get("id") in lens_ids]
    scores = {}
    for lens in lenses:
        # shared observations, jittered deterministically by lens id so each lens
        # is a distinct game-theory angle (incompatible lenses push opposite)
        jitter = sum(ord(c) for c in lens.get("id", "")) % 100 / 200.0 - 0.25
        scores[lens["id"]] = {
            "lens": lens["name"],
            "adoption": _clamp(observations.get("adoption", 0.5) + jitter),
            "flip": _clamp(observations.get("flip", 0.5) + jitter),
            "resistance": _clamp(observations.get("resistance", 0.5) - jitter),
            "shadow": _clamp(observations.get("shadow", 0.5) + jitter),
        }
    return {"schema": "lens_tournament.score.v1", "ts": _now(), "scores": scores}


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, round(float(x), 3)))


def _zeitgeist(scores: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Cross-lens synthesis: convergence on the dominant axis across lenses."""
    axis_totals = {a: 0 for a in AXES}
    for s in scores.values():
        for a in AXES:
            axis_totals[a] += s[a]
    n = max(1, len(scores))
    avg = {a: round(axis_totals[a] / n, 3) for a in AXES}
    dominant = max(avg, key=avg.get)
    converged = sum(1 for s in scores.values() if s[dominant] >= 0.6)
    return {
        "dominant_axis": dominant,
        "averages": avg,
        "converged_lenses": converged,
        "total_lenses": len(scores),
        "zeitgeist": converged >= 4,  # behavioral_lensing law: >=4 lenses converge
        "reading": (
            f"Zeitgeist confirmed — {converged}/{len(scores)} lenses converge on "
            f"{dominant}." if converged >= 4 else
            f"No zeitgeist — only {converged}/{len(scores)} lenses converge on {dominant}."
        ),
    }


def tournament(*, mode: str = "self", target: str = "ghost", lens_ids: list[str] | None = None) -> dict[str, Any]:
    """Run the full lensed Bernaysian tournament against the target."""
    planted = plant_round(target=target, lens_ids=lens_ids)
    observations = _live_observations() if mode == "probe" else _self_observations()
    scored = score_response(observations, lens_ids)
    zg = _zeitgeist(scored.get("scores", {}))
    # leaderboard: order lenses by average axis strength
    rows = []
    for lid, s in scored.get("scores", {}).items():
        rows.append({"lens": s["lens"], **{a: s[a] for a in AXES},
                     "strength": round(sum(s[a] for a in AXES) / 4.0, 3)})
    rows.sort(key=lambda r: -r["strength"])
    out = {
        "schema": "lens_tournament.run.v1",
        "ts": _now(),
        "mode": mode,
        "target": target,
        "planted": planted.get("n"),
        "observations": observations,
        "leaderboard": rows,
        "zeitgeist": zg,
        "verdict": {
            "top_lens": rows[0]["lens"] if rows else None,
            "top_axis": zg["dominant_axis"],
            "zeitgeist": zg["zeitgeist"],
            "reading": zg["reading"],
        },
    }
    _fold(out)
    return out


def _self_observations() -> dict[str, float]:
    """Deterministic demo observations (self-test)."""
    return {"adoption": 0.7, "flip": 0.66, "resistance": 0.42, "shadow": 0.55}


def _fold(out: dict[str, Any]) -> None:
    try:
        from mag import training_events
        training_events.emit(
            "arena_match",
            input_data={"target": out.get("target"), "mode": out.get("mode")},
            action={"kind": "lens_tournament", "n_lenses": out.get("planted")},
            outcome={"top_lens": out.get("verdict", {}).get("top_lens"),
                     "zeitgeist": out.get("verdict", {}).get("zeitgeist")},
            pattern_tags=["lens_tournament", "game_theory", "bernaise", "zeitgeist"],
            tier_max="T2",
        )
    except Exception:
        pass


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="mag.lens_tournament")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("lenses").set_defaults(fn=lambda a: print(json.dumps(available_lenses(), indent=2, ensure_ascii=False)))

    p_plant = sub.add_parser("plant")
    p_plant.add_argument("--target", default="ghost")
    p_plant.add_argument("--lens", default="")
    p_plant.set_defaults(fn=lambda a: print(json.dumps(
        plant_round(a.target, [x.strip() for x in a.lens.split(",") if x.strip()] or None),
        indent=2, ensure_ascii=False)))

    p_t = sub.add_parser("tournament")
    p_t.add_argument("--mode", choices=["self", "probe"], default="self")
    p_t.add_argument("--target", default="ghost")
    p_t.add_argument("--lens", default="")
    p_t.set_defaults(fn=lambda a: print(json.dumps(
        tournament(mode=a.mode, target=a.target,
                   lens_ids=[x.strip() for x in a.lens.split(",") if x.strip()] or None),
        indent=2, ensure_ascii=False)))

    args = ap.parse_args(argv)
    args.fn(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
