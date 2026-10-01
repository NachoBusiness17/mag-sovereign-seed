"""ox_gap — CONTINUOUS GAP ANALYSIS over the megaburn haul, with grok elevation.

Operator (2026-08-22): "do another pass for gap analysis. to better tie the ask together / research
for our next lensing and ask. or can we do gap analysis while they come in elevating to grok and
then really kicking this shit off."

So: scan the banked wave-1 outputs (handoff/OX_MEGA_*.json) AS THEY LAND, emit a gap report (what's
covered, what's weak/empty, open seams, contradictions, what's missing for the code-as-law plan),
elevate the sharpest gaps to GROK (via call_grok_free — grok through the free SuperGrok front-end,
$0, per our standing credit-protection rule) for hard synthesis, and fold the findings so the next
wave/lensing is sharper.

Schema: ox_gap.v1
Run:  python -m mag.ox_gap report            # one-shot gap report over banked outputs
      python -m mag.ox_gap elevate [--top N] # elevate the top N gaps to grok, bank to handoff/GAP_*.json
      python -m mag.ox_gap watch [--every S] # continuous: report + elevate as outputs land
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

SCHEMA = "ox_gap.v1"
OUT_DIR = ROOT / "handoff"
WAVE = OUT_DIR.glob("OX_MEGA_*.json")
GAP_DIR = OUT_DIR
# what we're planning toward (code-as-law) — used to score gaps as blocking vs nice-to-have
PLAN = ["code-as-law", "invariant lattice", "governance", "enforcement", "meta-token",
        "verkle proof", "deniable comms", "consensus", "cache economics", "semantic checkpoints",
        "sovereignty", "frontier-scout", "integration"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load(name: str) -> dict[str, Any] | None:
    p = OUT_DIR / f"OX_MEGA_{name}.json"
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def analyze() -> dict[str, Any]:
    """Gap report over every banked wave-1 output: coverage, weak/empty, open seams, contradictions."""
    names = sorted(p.stem.removeprefix("OX_MEGA_") for p in WAVE)
    if not names:
        return {"ok": True, "schema": SCHEMA, "banked": 0, "note": "no wave-1 outputs banked yet"}
    weak: list[dict[str, Any]] = []
    empty: list[str] = []
    strong: list[str] = []
    for n in names:
        d = _load(n)
        if not d:
            continue
        content = (d.get("content") or "").strip()
        reasoning = (d.get("reasoning") or "").strip()
        if not content and not reasoning:
            empty.append(n)
        elif len(content) < 1200:
            weak.append({"name": n, "content_chars": len(content),
                         "reasoning_chars": len(reasoning)})
        else:
            strong.append(n)
    # coverage vs the plan (which plan areas have at least one banked output?) — normalize
    # hyphens/underscores so 'meta-token' matches 'meta_token_definition'
    def _norm(s: str) -> str:
        return s.replace("-", "_").replace(" ", "_").lower()

    covered = sorted({next((a for a in PLAN if _norm(a) in _norm(n)), "other") for n in names})
    uncovered = [a for a in PLAN if a not in covered]
    return {
        "ok": True, "schema": SCHEMA, "ts": _now(), "banked": len(names),
        "strong": strong, "weak": weak, "empty": empty,
        "coverage": sorted(covered), "uncovered_plan_areas": uncovered,
        "open_seams": [  # the seams that gap analysis is meant to find
            "how do the wave-1 designs COMPOSE into one code-as-law system? (integration)",
            "what is the single authored invariant the whole lattice re-derives from?",
            "which enforcement is structural-impossibility vs detection vs sanction?",
            "what is the constitutional floor that even governance cannot amend?",
        ],
        "next_lensing_hint": ("gap analysis found " + str(len(weak) + len(empty)) +
                              " weak/empty of " + str(len(names)) +
                              " banked; the uncovered plan areas are " + ", ".join(uncovered) +
                              " — those are the sharpest next asks."),
    }


def _gap_prompt(report: dict[str, Any], top_n: int) -> str:
    weak = ", ".join(w["name"] for w in report["weak"][:top_n]) or "(none)"
    uncovered = ", ".join(report["uncovered_plan_areas"]) or "(none)"
    return (
        "We are building a code-as-law sovereign system from a wave of hard designs. GAP ANALYSIS:\n"
        f"- strong outputs: {', '.join(report['strong'][:20]) or 'none'}\n"
        f"- weak/thin outputs: {weak}\n"
        f"- empty outputs: {', '.join(report['empty']) or 'none'}\n"
        f"- uncovered plan areas (NOT yet designed): {uncovered}\n"
        f"- open seams: {json.dumps(report['open_seams'])}\n\n"
        "Synthesize: which gaps BLOCK the code-as-law build, what is the single authored invariant "
        "that ties the whole lattice together, and what is the sharpest next lensing/ask to close "
        "the biggest gap? Be concrete and short in reasoning; emit the full synthesis as content."
    )


def elevate(*, top_n: int = 5, max_tokens: int = 8000, timeout: int = 600) -> dict[str, Any]:
    """Elevate the sharpest gaps to GROK (free SuperGrok front-end) for hard synthesis."""
    report = analyze()
    if not report.get("banked"):
        return {"ok": True, "schema": SCHEMA, "action": "no-outputs-yet"}
    prompt = _gap_prompt(report, top_n)
    try:
        from mag import grok_rightsize
        res = grok_rightsize.call_grok_free(prompt, timeout=timeout)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "schema": SCHEMA, "action": "grok-elevate-failed",
                "error": f"{type(e).__name__}: {str(e)[:200]}"}
    out = {"schema": SCHEMA, "ts": _now(), "kind": "grok-gap-synthesis",
           "source": "elevate", "prompt": prompt,
           "answer": (res.get("content") or res.get("text") or res.get("answer") or ""),
           "reasoning": (res.get("reasoning") or ""), "cost": res.get("cost", 0.0),
           "report_snapshot": report}
    (GAP_DIR / f"GAP_{_now().replace(':', '').replace('-', '')}.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "schema": SCHEMA, "action": "grok-elevated", "report": report,
            "answer_chars": len(out["answer"]), "banked_to": f"GAP_*.json"}


def watch(*, every_s: int = 120, top_n: int = 5) -> None:
    """Continuous gap analysis: report + elevate as outputs land. Ctrl+C to stop."""
    import time
    last = 0
    print(f"[ox_gap] watch up — every {every_s}s. Ctrl+C to stop.", flush=True)
    while True:
        try:
            names = sorted(p.stem.removeprefix("OX_MEGA_") for p in WAVE)
            if len(names) != last:
                last = len(names)
                r = analyze()
                print(f"[ox_gap] banked={r['banked']} weak={len(r['weak'])} empty={len(r['empty'])} "
                      f"uncovered={r['uncovered_plan_areas']}", flush=True)
                if r["banked"] >= 3 and (r["weak"] or r["uncovered_plan_areas"]):
                    e = elevate(top_n=top_n)
                    print(f"[ox_gap] elevated -> {e.get('action')} ({e.get('answer_chars', 0)} chars)",
                          flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"[ox_gap] ERR {type(e).__name__}: {str(e)[:120]}", flush=True)
        time.sleep(max(int(every_s), 60))


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="ox-gap")
    ap.add_argument("cmd", nargs="?", default="report", choices=["report", "elevate", "watch"])
    ap.add_argument("--top", type=int, default=5)
    ap.add_argument("--every", type=int, default=120)
    a = ap.parse_args()
    if a.cmd == "elevate":
        print(json.dumps(elevate(top_n=a.top), indent=2, ensure_ascii=False, default=str))
    elif a.cmd == "watch":
        watch(every_s=a.every, top_n=a.top)
    else:
        print(json.dumps(analyze(), indent=2, ensure_ascii=False, default=str))
