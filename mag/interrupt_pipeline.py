"""interrupt_pipeline — what happens when the operator INTERRUPTS: park it, value it,
steer the useful, re-route the rest, assemble a coherent batch.

Operator (2026-08-10): "when i interrupt it goes to our interuppt queue our ghost sees what you
are working on determines its value steers what is useful and not a cache hit and rerouts the
other request that massages it and assembles something coherent like 3 steal loops and an
invariant scan or something"

THE PIPELINE (the ghost handles every interrupt, never just drops it):
  1. INTERRUPT   -> the operator's new instruction lands while work is in progress.
  2. PIN CURRENT -> the in-progress work is parked (steer_router.pin) so it can resume, never lost.
  3. VALUE       -> ghost determines the new instruction's value: is it NOVEL (not a cache hit)?
                    novelty = does our corpus already cover it (knowledge_graph.known / novelty)?
                    cache_hit -> low value, drop/steer away. novel -> high value, keep.
  4. STEER       -> route the useful instruction: enqueue (async) or run-now (steer_router.steer).
  5. RE-ROUTE    -> the OTHER parked requests (the interrupt stack + pins) get massaged into a
                    coherent batch.
  6. ASSEMBLE    -> compose the batch: e.g. 3 steal loops + an invariant scan -> expressed as a
                    RIB scene and dispatched through OUR swarm (session_rib style).

Honesty: value is determined by NOVELTY (real coverage check), not self-congratulation. A
cache-hit (we already know it) is NOT re-run. provenance is explicit.

Schema: interrupt_pipeline.v1 · CLI: python -m mag.interrupt_pipeline interrupt "<new>" \
        [--current "<in-progress>"] [--dry] | batch | stack | status
"""
from __future__ import annotations

import argparse
import json
import re
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

SCHEMA = "interrupt_pipeline.v1"
STACK_FILE = ROOT / "memory" / "runs" / "interrupt_pipeline" / "interrupt_stack.json"
BATCHES = ROOT / "memory" / "runs" / "interrupt_pipeline" / "batches.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load_stack() -> list[dict[str, Any]]:
    if not STACK_FILE.is_file():
        return []
    try:
        return json.loads(STACK_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save_stack(stack: list[dict[str, Any]]) -> None:
    STACK_FILE.parent.mkdir(parents=True, exist_ok=True)
    STACK_FILE.write_text(json.dumps(stack, ensure_ascii=False, indent=2), encoding="utf-8")


def _words(text: str) -> set[str]:
    return set(w.lower() for w in re.findall(r"[a-zA-Z][a-zA-Z0-9_]{3,}", text or ""))


# --- VALUE: is it novel (not a cache hit)? ------------------------------------------------
def value(instruction: str) -> dict[str, Any]:
    """Determine the instruction's value: NOVEL (worth doing) or CACHE_HIT (we already know it).
    Checks our knowledge graph + steal corpus for coverage. Deterministic, $0."""
    tw = _words(instruction)
    # 1) knowledge graph: does `known()` already cover this?
    known_label = ""
    try:
        from mag.knowledge_graph import known
        k = known(instruction)
        known_label = (k.get("known") or [{}])[0].get("label", "") if k.get("known") else ""
    except Exception:
        pass
    # 2) steal corpus filename overlap (we already mined this)
    try:
        from mag import lens_chain as lc
        docs = lc._steal_docs()
        max_overlap = 0
        for p, _ in docs:
            pw = _words(p.stem)
            ov = len(tw & pw) / max(1, len(pw))
            max_overlap = max(max_overlap, ov)
    except Exception:
        max_overlap = 0.0
    cache_hit = bool(known_label) or max_overlap >= 0.4
    return {"ok": True, "schema": SCHEMA, "instruction": instruction[:200],
            "novel": not cache_hit, "cache_hit": cache_hit,
            "known_node": known_label[:80] or None, "corpus_overlap": round(max_overlap, 3),
            "verdict": "novel" if not cache_hit else "cache_hit"}


# --- THE PIPELINE ------------------------------------------------------------------------
def interrupt(new_instruction: str, *, current_task: str | None = None,
              dry: bool = True) -> dict[str, Any]:
    """Handle an interrupt end to end: park current, value the new, steer it, re-route the
    parked requests, assemble a coherent batch, dispatch through our swarm."""
    out = {"ok": True, "schema": SCHEMA, "ts": _now(), "steps": []}

    # 1. PIN CURRENT — never lose the in-progress work
    pin_res = {}
    if current_task:
        try:
            from mag import steer_router as sr
            pin_res = sr.pin(current_task, reason="operator interrupt")
        except Exception as e:
            pin_res = {"error": str(e)[:120]}
        out["steps"].append({"step": "pin_current", **pin_res})

    # 2. VALUE — is the new instruction novel (not a cache hit)?
    val = value(new_instruction)
    out["steps"].append({"step": "value", "novel": val["novel"],
                         "verdict": val["verdict"], "known_node": val.get("known_node"),
                         "corpus_overlap": val.get("corpus_overlap")})

    # 3. STEER the new instruction (route: enqueue / now), unless it's a cache hit
    steer_res = {}
    if val["novel"]:
        try:
            from mag import steer_router as sr
            steer_res = sr.steer(new_instruction, current_task=current_task)
        except Exception as e:
            steer_res = {"error": str(e)[:120]}
    else:
        steer_res = {"action": "dropped_cache_hit",
                     "note": "already covered — steering away, not re-running"}
    out["steps"].append({"step": "steer", **steer_res})

    # 4. RE-ROUTE + ASSEMBLE the parked requests into a coherent batch
    batch = assemble(dry=dry)
    out["batch"] = batch
    # persist this interrupt as a stack record
    rec = {"ts": _now(), "new_instruction": new_instruction[:200],
           "current_task": current_task, "novel": val["novel"],
           "verdict": val["verdict"], "batch_id": batch.get("batch_id")}
    BATCHES.parent.mkdir(parents=True, exist_ok=True)
    BATCHES.open("a", encoding="utf-8").write(json.dumps(rec, ensure_ascii=False) + "\n")
    out["dry"] = dry
    return out


def assemble(*, dry: bool = True) -> dict[str, Any]:
    """Assemble the coherent batch from the interrupt/pin stack: e.g. 3 steal loops + an
    invariant scan, expressed as a RIB scene and dispatched through our swarm."""
    # pull the pin stack + interrupt stack as the raw threads
    threads = []
    try:
        from mag import steer_router as sr
        p = sr.pins()
        threads += [str(x.get("task")) for x in p.get("pins", [])]
    except Exception:
        pass
    stack = _load_stack()
    threads += [str(x.get("new_instruction")) for x in stack]
    # default batch if nothing parked: the standing directives
    if not threads:
        threads = [
            "steal mechanisms from other systems and adapt to our deterministic architecture",
            "honesty everywhere: no artifact claims frontier provenance without real output",
            "reuse prior deep-dive corpus as lenses to answer cheaply",
            "express work as RIB scenes and dispatch through our swarm",
        ]
    # run the batch through the session_rib stream handler -> invariant scan + swarm A/B
    from mag import session_rib as sr2
    soc = sr2.stream_of_consciousness(" ".join(threads), per_invariant=2, dry=dry)
    batch_id = f"batch_{datetime.now(timezone.utc).strftime('%H%M%S%f')}"
    return {"ok": True, "schema": SCHEMA, "batch_id": batch_id,
            "n_threads": len(threads), "n_unique_invariants": soc.get("n_unique_invariants"),
            "invariants": soc.get("invariants"),
            "ab_tasks": soc.get("ab_test", {}).get("dispatch", {}).get("n_tasks"),
            "dry": dry, "threads": threads[:6]}


def stack() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA, "n_interrupts": len(_load_stack()),
            "interrupts": _load_stack()[-10:]}


def status() -> dict[str, Any]:
    try:
        from mag import steer_router as sr
        pins = sr.pins()
    except Exception:
        pins = {"n_pins": 0}
    return {"ok": True, "schema": SCHEMA, "n_interrupts": len(_load_stack()),
            "pins": pins.get("n_pins", 0)}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Interrupt-handling pipeline (ghost values + steers + assembles)")
    ap.add_argument("cmd", nargs="?", default="status",
                    choices=["interrupt", "batch", "stack", "status"])
    ap.add_argument("arg", nargs="*", default=[])
    ap.add_argument("--current", default="")
    ap.add_argument("--dry", action="store_true", default=True)
    a = ap.parse_args()
    if a.cmd == "interrupt":
        new = " ".join(a.arg) or "operator interrupt — continue the standing work"
        print(json.dumps(interrupt(new, current_task=a.current or None, dry=a.dry),
                         ensure_ascii=False, indent=2))
    elif a.cmd == "batch":
        print(json.dumps(assemble(dry=a.dry), ensure_ascii=False, indent=2))
    elif a.cmd == "stack":
        print(json.dumps(stack(), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(status(), ensure_ascii=False, indent=2))
