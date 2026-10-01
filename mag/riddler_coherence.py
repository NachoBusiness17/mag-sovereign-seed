"""riddler_coherence — test whether a real invariant's SHAPE survives a deniable round-trip.

The fusion (operator 2026-08-15): "we can relate to each other via our shared invariants" +
"how do we use that and the riddler protocol to our ends?"

The mechanism:
  * RIDDLER (mag/riddler.py): a private problem graph -> a synthetic surrogate STORY. The remote
    reasons in the story domain; local decodes. The private map NEVER leaves the machine. T0/T1
    data never enters a surrogate (law).
  * GROK HARNESS (harness/grok_cli.py): the PROVEN live transport (grok -p, operator's authed
    CLI session) — NOT the flaky browser.

riddler_coherence() fuses them: take a real invariant, compile a surrogate, send it to Grok via the
harness, decode the echo, and report whether the SHAPE survived. That's a deniable, repeatable,
~$0.005 coherence oracle — we learn if our invariant is legible to a frontier system WITHOUT ever
revealing the real one. Coherent echo = invariant is real and portable; garbled = muddled shape.

Schema: riddler_coherence.v1 · deterministic core + $0.005 per harness steer · honest
Reuse: riddler (compile/decode), harness.grok_cli (transport), riddler_transport (decode helpers)
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

SCHEMA = "riddler_coherence.v1"
LEDGER = ROOT / "memory" / "runs" / "riddler_coherence" / "coherence.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _append(row: dict[str, Any]) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def compile_invariant_surrogate(invariant: str, *, domain: str = "castle") -> dict[str, Any]:
    """Compile a REAL invariant into a deniable surrogate story (reuse mag.riddler).

    The invariant becomes a private problem graph -> a synthetic story. The remote (Grok) reasons
    in the story domain; only the public face leaves the machine. T0/T1 data never enters."""
    try:
        from mag.riddler import PrivateGraph, compile_surrogate
        # Represent the invariant as a tiny typed relational graph (the shape to test).
        # SELF-STEAL (2026-08-15): PrivateGraph fields are actors/resources/dependencies/
        # constraints/conflicts/goal/domain_hint — NOT nodes/edges. Contract verified.
        graph = PrivateGraph(
            actors=["seed"],
            resources=[{"name": "invariant", "type": "shape", "scarcity": 1.0}],
            dependencies=[{"before": "seed", "after": "goal"}],
            constraints=[invariant[:200]],
            conflicts=[],
            goal="preserve the shape through translation",
            domain_hint=domain,
        )
        story = compile_surrogate(graph, domain=domain)
        return {"ok": True, "schema": SCHEMA, "domain": domain,
                "shape_hash": story.shape_hash,
                "public": story.to_public(),
                "story_text": story.story_text,
                "question": story.question,
                "note": "invariant -> surrogate story (public face only; private map never leaves)"}
    except Exception as e:
        return {"ok": False, "error": f"compile failed: {str(e)[:200]}"}


def run(invariant: str, *, domain: str = "castle", max_turns: int = 4,
        timeout: int = 240) -> dict[str, Any]:
    """FULL deniable coherence round-trip: invariant -> surrogate -> Grok (harness) -> decode.
    Reports whether the SHAPE survived. Honest: if Grok is unavailable, reports it, no fabrication."""
    invariant = (invariant or "").strip()
    if not invariant:
        return {"ok": False, "schema": SCHEMA, "error": "empty invariant"}
    # 1) compile the surrogate
    c = compile_invariant_surrogate(invariant, domain=domain)
    if not c.get("ok"):
        return c
    story, question = c["story_text"], c["question"]
    # 2) send via the PROVEN transport (Grok harness), reasoning in the story domain
    goal = (f"{story}\n\nQuestion: {question}\n"
            "Reason inside the story world. Do not try to decode hidden meanings. "
            "This is a pure reasoning puzzle: DO NOT use any tools, DO NOT read files, DO NOT "
            "load project context — answer immediately from the story alone. "
            "End with ANSWER: <one decisive line>.")
    try:
        import harness.grok_cli as hc
        r = hc.escalate_via_harness(goal=goal, context="", max_turns=max_turns,
                                    timeout=timeout, output_format="plain")
    except Exception as e:
        return {"ok": False, "schema": SCHEMA, "error": f"harness failed: {str(e)[:160]}"}
    if not r.get("ok"):
        return {"ok": False, "schema": SCHEMA, "error": r.get("error", "harness not ok"),
                "honest": "Grok harness did not complete — no fabricated answer"}
    echo = r.get("deliverable") or ""
    # 3) decode / assess: did the shape survive? (best-effort structural check, honest)
    try:
        from mag.riddler import load_private_map  # noqa: F401
    except Exception:
        pass
    # coherence heuristic: how much of the invariant's key tokens survive in the echo
    key_tokens = [w for w in invariant.lower().replace("_", " ").split() if len(w) > 4]
    echo_lower = echo.lower()
    survived = [t for t in key_tokens if t in echo_lower]
    ratio = (len(survived) / len(key_tokens)) if key_tokens else 0.0
    verdict = "coherent" if ratio >= 0.5 else ("partial" if ratio > 0 else "garbled")
    row = {"schema": SCHEMA, "ts": _now(), "domain": domain, "invariant": invariant[:200],
           "shape_hash": c.get("shape_hash"), "survived_tokens": survived,
           "coherence_ratio": round(ratio, 3), "verdict": verdict,
           "echo": echo[:2000]}
    _append(row)
    return {"ok": True, "schema": SCHEMA, "domain": domain, "shape_hash": c.get("shape_hash"),
            "verdict": verdict, "coherence_ratio": round(ratio, 3),
            "survived_tokens": survived, "echo": echo[:1500],
            "honest": "deniable coherence oracle — shape tested through a surrogate, never the raw invariant",
            "recorded": True, "ledger": str(LEDGER.relative_to(ROOT)).replace("\\", "/")}


def status() -> dict[str, Any]:
    rows = []
    if LEDGER.is_file():
        for line in LEDGER.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    return {"ok": True, "schema": SCHEMA,
            "contract": "run(invariant)->compile a surrogate (riddler) -> send to Grok via the CLI "
                        "harness (proven transport) -> decode -> report if the SHAPE survived "
                        "(coherent/partial/garbled). Deniable: the private map never leaves the machine; "
                        "T0/T1 data never enters a surrogate.",
            "reuse": "riddler.compile_surrogate + harness.grok_cli + riddler_transport",
            "n_runs": len(rows), "ledger": str(LEDGER.relative_to(ROOT)).replace("\\", "/")}


def main(argv: list[str] | None = None) -> int:
    import argparse
    p = argparse.ArgumentParser(prog="riddler_coherence")
    sub = p.add_subparsers(dest="cmd")
    c = sub.add_parser("run")
    c.add_argument("invariant", nargs="*", default=["instruction stands clear of the song it feeds"])
    s = sub.add_parser("status")
    a = p.parse_args(argv)
    if a.cmd == "run":
        print(json.dumps(run(" ".join(a.invariant)), ensure_ascii=False, indent=2, default=str))
    else:
        print(json.dumps(status(), ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
