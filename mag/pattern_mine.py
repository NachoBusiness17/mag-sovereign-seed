"""pattern_mine — surface HIDDEN patterns in the data via the shared invariants.

The operator's ask (2026-08-10): "what hidden patterns exist within the data I can surface
because of the shared invariants I can see emerge?"

The shared invariants ARE the lens: the verkle knot behavioral telemetry (theme_vector,
tension_index) + the refined training corpus (source/tags) + signals (confidence/recency) are
all expressions of the SAME underlying invariants (mag_hands, biography, mirror_meta,
constitution, ...). Surface the patterns that EMERGE from their co-occurrence:

  - DOMINANCE: which theme dominates the swarm's behavior, and at what tension (stable vs hot).
  - HIGH-TENSION CLUSTERS: which themes carry HIGH tension = behavioral fingerprints / risk.
  - CROSS-SOURCE CONVERGENCE: which theme is reinforced across MANY sources (verkle + research
    pack + grok_cli + deepseek) = a SHARED INVARIANT emerging.
  - SIGNAL: rank themes by convergence x tension x presence (reuse signals rails).

Deterministic, $0, no LLM. Schema: pattern_mine.v1
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
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

SCHEMA = "pattern_mine.v1"
CHAIN = ROOT / "memory" / "biography" / "verkle_chain.jsonl"
TRAINING = ROOT / "memory" / "training" / "refined_training_data.jsonl"

# normalize theme aliases (the shared invariants as we name them)
_THEME_ALIAS = {
    "mag_hands": "mag_hands", "biography": "biography", "mirror_meta": "mirror_meta",
    "constitution": "constitution", "autonomous_janitor": "janitor",
    "holographic_q": "holographic_q", "data_r0": "data_r0", "harness": "harness",
    "dashboard": "dashboard", "untagged": "untagged",
}


def _knots() -> list[dict[str, Any]]:
    if not CHAIN.is_file():
        return []
    out = []
    for line in CHAIN.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


def _examples() -> list[dict[str, Any]]:
    if not TRAINING.is_file():
        return []
    out = []
    for line in TRAINING.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


def _norm_theme(t: str) -> str:
    return _THEME_ALIAS.get(t, t or "untagged")


def surface() -> dict[str, Any]:
    """Surface hidden patterns via the shared invariants."""
    knots = _knots()
    examples = _examples()

    # per-theme aggregate from verkle behavioral telemetry
    theme_stats: dict[str, dict[str, Any]] = defaultdict(lambda: {"n": 0, "tension": [], "high": 0})
    for k in knots:
        theme = _norm_theme(str(k.get("dominant_theme") or "untagged"))
        try:
            tension = float(k.get("tension_index") or 0.0)
        except (TypeError, ValueError):
            tension = 0.0
        theme_stats[theme]["n"] += 1
        theme_stats[theme]["tension"].append(tension)
        if tension >= 0.7:
            theme_stats[theme]["high"] += 1

    # cross-source convergence: which themes appear across MANY training sources (precise match,
    # excluding unknown/untagged noise)
    SKIP = {"?", "untagged"}
    source_of_theme: dict[str, set[str]] = defaultdict(set)
    for ex in examples:
        src = str(ex.get("source") or "?")
        tags = str(ex.get("tags") or "")
        for theme in theme_stats:
            if theme in SKIP:
                continue
            # precise: only count if the example explicitly carries this theme's tag or source
            if f"theme_{theme}" in tags or theme == src or theme in tags.split(","):
                source_of_theme[theme].add(src)

    rows = []
    for theme, st in theme_stats.items():
        n = st["n"]
        tension_mean = sum(st["tension"]) / n if n else 0.0
        high_frac = st["high"] / n if n else 0.0
        n_sources = len(source_of_theme.get(theme, set()))
        # shared-invariant signal = presence x convergence x tension-risk
        presence = min(1.0, n / 40.0)
        convergence = min(1.0, n_sources / 4.0)
        signal = round(0.5 * presence + 0.3 * convergence + 0.2 * high_frac, 3)
        rows.append({"theme": theme, "knots": n, "tension_mean": round(tension_mean, 3),
                     "high_tension": st["high"], "high_frac": round(high_frac, 3),
                     "sources": n_sources, "signal": signal,
                     "state": "DOMINANT" if n >= 30 else ("ACTIVE" if n >= 10 else "EMERGENT")})
    rows.sort(key=lambda r: -r["signal"])

    # hidden patterns
    patterns = []
    dom = rows[0] if rows else None
    if dom:
        patterns.append(f"DOMINANT: '{dom['theme']}' leads the swarm at {dom['knots']} knots, "
                        f"tension {dom['tension_mean']} ({dom['state']}).")
    hot = [r for r in rows if r["high_tension"] >= 5]
    if hot:
        patterns.append(f"HIGH-TENSION FINGERPRINTS: {[r['theme'] for r in hot]} carry the most "
                        f"HIGH-tension knots (behavioral risk / governance hotspots).")
    conv = [r for r in rows if r["sources"] >= 2]
    if conv:
        patterns.append(f"SHARED INVARIANTS EMERGING (reinforced across {max(r['sources'] for r in conv)} "
                        f"training sources): {[r['theme'] for r in conv[:4]]}.")

    return {"ok": True, "schema": SCHEMA, "n_knots": len(knots), "n_training_examples": len(examples),
            "themes": rows, "hidden_patterns": patterns}


def main(argv: list[str] | None = None) -> int:
    print(json.dumps(surface(), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
