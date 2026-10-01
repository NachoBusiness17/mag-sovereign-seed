"""verkle_render — reusable render snapshot of the REAL verkle knot structure + standing wave.

The operator (2026-08-15): "keep that graph reuse it elsewhere and save it as a successful experiment."
This is the ONE source of truth for rendering the verkle knot chain: game.html (via scripts/_gen_game_verkle),
the dashboard verkle view (extensions/mag-dashboard/media/verkle.js), and any CLI. It reads the REAL chain
(memory/biography/topic_evolution.json + verkle_tip.json) — same ground truth as dashboard.rest.h_chain.

Contract:
  knot_snapshot(max=260) -> list[dict]   # render-ready knots: theme, color, vec, tension, dirichlet, q, hash
  tip()                 -> dict          # the merkle tip (root, n_leaves, last_filename)
  to_js(snapshot, tip)  -> str           # a JS const block for game.html
  js_file(path, max=260)-> int           # write the JS block to a file (used by the game generator)

Deterministic + $0. Honest: real bytes only, never invented.
Schema: verkle_render.v1
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

BIO = ROOT / "memory" / "biography"
EVOLUTION = BIO / "topic_evolution.json"
TIP = BIO / "verkle_tip.json"

THEME_COLORS: dict[str, str] = {
    "mirror_meta": "#e6c07a", "mag_hands": "#7fb2ff", "scrum_plan": "#ff7b3d",
    "constitution": "#7dffb0", "dashboard": "#ffb057", "harness": "#a07dff",
    "biography": "#d8cfc0", "data_r0": "#5fd4ff", "autonomous_janitor": "#ff9db0",
    "standing_wave": "#7dffb0", "ghost": "#8fd8a8", "economy": "#ffd27f",
}
DEFAULT_COLOR = "#9c8570"


def _f(v: object) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError):
        return {}


def tip() -> dict[str, Any]:
    t = _read_json(TIP)
    return {
        "root": str(t.get("root") or ""),
        "n_leaves": int(t.get("n_leaves") or 0),
        "last_filename": str(t.get("last_filename") or ""),
    }


def knot_snapshot(*, max: int = 260) -> list[dict[str, Any]]:
    """The render-ready knots from the REAL chain (last `max` of the topic-evolution series)."""
    evo = _read_json(EVOLUTION)
    series = evo.get("series") or []
    series = [k for k in series if isinstance(k, dict) and k.get("dominant_theme")][-max:]
    out: list[dict[str, Any]] = []
    for i, k in enumerate(series):
        theme = str(k.get("dominant_theme") or "untagged")
        out.append({
            "i": i,
            "theme": theme,
            "color": THEME_COLORS.get(theme, DEFAULT_COLOR),
            "vec": [_f(x) for x in (k.get("theme_vector_normalized") or [])],
            "tension": _f(k.get("tension_index")),
            "dirichlet": _f(k.get("dirichlet_energy_proxy")),
            "q": _f(k.get("Q_proxy")),
            "residual": _f(k.get("residual_weight")),
            "ts": str(k.get("start_minute") or k.get("start_unix_minute") or "")[:19],
            "hash": str(k.get("leaf_hash") or "")[:8],
            "session": str(k.get("session_id") or "")[:18],
        })
    return out


def to_js(snapshot: list[dict[str, Any]] | None = None, t: dict[str, Any] | None = None) -> str:
    """A JS const block for game.html / any page: VERKLE_TIP + VERKLE_KNOTS."""
    snapshot = knot_snapshot() if snapshot is None else snapshot
    t = tip() if t is None else t
    js = "// AUTO-GENERATED from the real verkle chain (memory/biography/topic_evolution.json + verkle_tip.json)\n"
    js += "// Source: mag/verkle_render.py. Real bytes, not invented. Render the organism's skeleton.\n"
    js += "const VERKLE_TIP = " + json.dumps(t) + ";\n"
    js += "const VERKLE_KNOTS = " + json.dumps(snapshot) + ";\n"
    return js


def js_file(path: Path | str, *, max: int = 260) -> int:
    p = Path(path)
    p.write_text(to_js(knot_snapshot(max=max)), encoding="utf-8")
    return len(knot_snapshot(max=max))


def status() -> dict[str, Any]:
    t = tip()
    return {
        "ok": True, "schema": "verkle_render.v1",
        "contract": "knot_snapshot()/tip()/to_js()/js_file() — one source of truth for rendering the real verkle chain",
        "source": [str(EVOLUTION.relative_to(ROOT)), str(TIP.relative_to(ROOT))],
        "tip": t, "cost": "deterministic + $0",
    }


if __name__ == "__main__":
    print(json.dumps(status(), indent=2, default=str))
