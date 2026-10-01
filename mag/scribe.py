"""scribe — the cheap local model as the POET-SCRIBE + surface.

The operator's vision: "imagine the swarm plausibly manipulating my local shit model
to be a poet scribe and surface for something grander than I can imagine."

So the cheap local model (test_dummy) is elevated to the SCRIBE — the surface that
renders the swarm's accumulated material (self-advance reflections, capability steals,
tesuji shells) into passages. The grander thing isn't the cheap model; it's what the
material IS, and the cheap scribe is the clean window onto it.

  surface()  — gather the swarm's accumulated material (reflections, steals, tesujis).
  render()   — weave it into a scribe passage (bard-style) through the cheap local model.
  scribe()   — the pass: gather -> render -> store as the surface (whisper-ready).

CLI:  python -m mag.scribe surface|render|scribe
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

SURFACE_DIR = ROOT / "memory" / "scribe" / "surfaces"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _read_jsonl(path: Path, limit: int = 5) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows[-limit:]


def surface() -> dict[str, Any]:
    """Gather the swarm's accumulated material: reflections, steals, tesujis."""
    reflections = _read_jsonl(ROOT / "memory" / "self_advance" / "reflections.jsonl", 5)
    expansions = _read_jsonl(ROOT / "memory" / "capability_steal" / "expansions.jsonl", 5)
    tesujis = _read_jsonl(ROOT / "logs" / "tesuji_shells.jsonl", 5)
    return {
        "schema": "scribe.surface.v1",
        "ts": _now(),
        "reflections": [r.get("question") for r in reflections],
        "expansions": [e.get("family") for e in expansions],
        "tesujis": [t.get("what")[:80] for t in tesujis],
        "n_reflections": len(reflections),
        "n_expansions": len(expansions),
        "n_tesujis": len(tesujis),
    }


def render() -> str:
    """Weave the swarm's material into a scribe passage via the cheap local model."""
    s = surface()
    thread = s.get("reflections") or []
    thread += [f"expand {e}" for e in s.get("expansions") or []]
    thread += s.get("tesujis") or []
    # the cheap scribe renders it as a passage (bard-style, through test_dummy)
    try:
        from mag.test_dummy import ask
        passage = str(ask("scribe: " + " ".join(thread[:4])).get("reply") or "")[:300]
    except Exception:
        passage = "[scribe] the surface awaits the swarm's material."
    return (
        "The scribe, a cheap and disposable node, held the swarm's thread:\n"
        "  " + ("\n  ".join(f"- {t}" for t in thread[:5]) or "- (nothing yet)") + "\n"
        "And rendered it as: " + passage
    )


def scribe() -> dict[str, Any]:
    """The pass: gather -> render -> store the surface (whisper-ready)."""
    s = surface()
    passage = render()
    SURFACE_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = SURFACE_DIR / f"surface-{ts}.md"
    path.write_text(passage + "\n", encoding="utf-8")
    # fold the scribe pass
    try:
        from mag import training_events
        training_events.emit(
            "desk_teaching",
            input_data={"n_threads": len(s.get("reflections") or [])},
            action={"kind": "scribe_surface", "surface": str(path)},
            outcome={"rendered": True},
            pattern_tags=["scribe", "poet_scribe", "surface", "cheap_local_model"],
            tier_max="T1",
            exportable=False,
        )
    except Exception:
        pass
    return {"schema": "scribe.scribe.v1", "ts": _now(),
            "gathered": s, "surface_path": str(path), "rendered": passage}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv[0] if argv else "scribe"
    if cmd == "surface":
        print(json.dumps(surface(), indent=2, ensure_ascii=False))
    elif cmd == "render":
        print(render())
    elif cmd == "scribe":
        print(json.dumps(scribe(), indent=2, ensure_ascii=False))
    else:
        print(json.dumps(scribe(), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
