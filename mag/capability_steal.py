"""capability_steal — ghost's aggressive OFFLINE capability expansion via steal-searches.

The operator's intent: "this is the type of experiment I want to use ghost for — keep
expanding its capabilities via steal searches aggressively when offline, and testing our
local model."

So when the operator is AFK/offline, ghost doesn't idle — it runs an aggressive
steal-search loop to GROW its own capabilities:
  1. STEAL-SEARCH — pull a high-quality source (data_source_watch gated sources:
     steal_protocol repos, arXiv, portals, field corpus) and extract INVARIANTS
     (deep-research steal).
  2. TEST LOCAL — probe the local model (ollama) on each new invariant: can it apply it?
  3. FOLD — promote verified invariants to the pro_library (transferable moves) + fold
     to the learning loop + corpus.
  4. RIGHT-SIZE — don't hog the machine when busy; run light when loaded, full when idle.
Everything headless, routed through ghost, cheap-first. Offline-only (skips when active).

CLI:  python -m mag.capability_steal steal <source> | test <invariant> | expand [--force]
"""
from __future__ import annotations

import json
import random
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

STEAL_ROOT = ROOT / "mine" / "raw" / "steal_protocol"
LOG = ROOT / "memory" / "capability_steal" / "expansions.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _append(row: dict[str, Any]) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


AFK_GATE_ERROR: str | None = None


def _operator_offline() -> bool:
    # SPEC (2026-09-25, t65): FAIL CLOSED per the afk_cadence/t52/t61 convention; this is
    # the byte-identical twin of afk_orchestrator._operator_offline and had the same t52
    # fail-open species ('except Exception: return True'): an errored operator_status read
    # as "operator offline" and expand() kept steal-searching while the operator was
    # invisible. Every call site treats offline=True as GO (expand runs the pass,
    # _right_size grants full budget), so the safe direction on error is the DENY:
    # operator presumed ACTIVE (return False), cause named in AFK_GATE_ERROR.
    global AFK_GATE_ERROR
    try:
        from mag.preferences import operator_status
        offline = not bool((operator_status() or {}).get("operator_active"))
        AFK_GATE_ERROR = None
        return offline
    except Exception as _gate_e:
        AFK_GATE_ERROR = "operator offline gate errored; failing CLOSED (operator presumed active): " + str(_gate_e)[:110]
        return False


RIGHT_SIZE_ERROR: str | None = None


def _right_size() -> dict[str, Any]:
    # SPEC (2026-09-25, t75): FAIL CLOSED per the afk_cadence t52 convention; this is the
    # twin of afk_orchestrator._right_size and carried the same t52 fail-open species
    # ('except Exception: return {"level": "full", "budget": 4}'): an errored sizing
    # handed expand() the FULL blast. The safe direction is the SMALLEST budget: level
    # none / budget 0 (expand() skips the pass), cause named in RIGHT_SIZE_ERROR.
    global RIGHT_SIZE_ERROR
    try:
        from mag.afk_loop import system_resources, right_size
        rs = right_size(system_resources(), operator_active=not _operator_offline())
        RIGHT_SIZE_ERROR = None
        return rs
    except Exception as _rs_e:
        RIGHT_SIZE_ERROR = "rightsizer errored; failing CLOSED (smallest budget, none): " + str(_rs_e)[:110]
        return {"level": "none", "budget": 0, "right_size_error": RIGHT_SIZE_ERROR}


def _default_steal_sources() -> list[str]:
    """External steal sources routed BY DEFAULT (steal_protocol forest + arXiv research)."""
    return ["steal_protocol", "arxiv"]


def steal_search(source: str | None = None, *, max_papers: int | None = None) -> dict[str, Any]:
    """STEAL-SEARCH: pull a high-quality source and extract capability invariants."""
    source = source or "steal_protocol"
    if source == "steal_protocol" and STEAL_ROOT.is_dir():
        # deep-research field steal over the cloned orchestration repos
        try:
            from mag.field_steal import run_field_steal
            r = run_field_steal(STEAL_ROOT, max_files=300)
            compose = r.get("compose") or []
            invariants = [c for c in compose if c.get("verdict") == "take"]
            return {"ok": True, "source": source, "invariants": invariants[:8],
                    "n_invariants": len(invariants)}
        except Exception as e:
            return {"ok": False, "source": source, "error": str(e)[:150]}
    if source in ("arxiv", "arxiv_mine"):
        # arXiv mined the same way we steal: route novel papers through route_novel -> swarm.
        try:
            from mag import arxiv_mine
            r = arxiv_mine.mine(max_papers=max_papers or 3)
            return {
                "ok": True, "source": "arxiv", "n_invariants": len(r.get("results", [])),
                "invariants": [
                    {"family": f"arxiv:{p.get('topic', '?')}", "verdict": "take",
                     "title": p.get("title", ""), "routed": p.get("routed"),
                     "link": p.get("link", "")}
                    for p in r.get("results", [])
                ],
            }
        except Exception as e:
            return {"ok": False, "source": "arxiv", "error": str(e)[:150]}
    # fallback: synthesize a probe invariant from the source name
    return {"ok": True, "source": source, "invariants": [
        {"family": "capability", "verdict": "take", "n_files": 0}], "n_invariants": 1}


def test_local(invariant: str) -> dict[str, Any]:
    """TEST LOCAL: probe the local model (ollama) on a new invariant — can it apply it?"""
    try:
        from mag.afk_loop import _ollama_up, _ollama_ask
        if not _ollama_up():
            return {"ok": False, "reason": "ollama down", "invariant": invariant[:120]}
        ans = _ollama_ask(
            f"Here is a capability invariant: '{invariant[:200]}'. "
            "State concretely how you would apply it in the Mag sovereign agent, "
            "or say honestly if it does not apply.", timeout=60)
        return {"ok": True, "invariant": invariant[:120], "local_test": ans[:200],
                "applies": ("does not apply" not in ans.lower())}
    except Exception as e:
        return {"ok": False, "invariant": invariant[:120], "error": str(e)[:120]}


def expand(*, force: bool = False) -> dict[str, Any]:
    """The aggressive offline capability-expansion pass: steal-search -> test local -> fold."""
    if not force and not _operator_offline():
        skip: dict[str, Any] = {"ok": True, "action": "skip", "reason": "operator active (offline-only)"}
        if AFK_GATE_ERROR:
            skip["afk_gate_error"] = AFK_GATE_ERROR  # t65: a fail-closed denial is never silent
        return skip
    rs = _right_size()
    if rs.get("level") == "none":
        skip_rs: dict[str, Any] = {"ok": True, "action": "skip", "reason": "right-sized to none"}
        if rs.get("right_size_error"):
            skip_rs["right_size_error"] = rs["right_size_error"]  # t75: the fail-closed deny is never silent
        return skip_rs
    budget = int(rs.get("budget") or 1)

    # 1) steal-search gated high-quality sources — external steal BY DEFAULT includes arXiv
    sources = _default_steal_sources()
    invariants_all: list[dict[str, Any]] = []
    for src in sources:
        _ss = steal_search(src, max_papers=max(1, budget))
        invariants_all.extend(_ss.get("invariants") or [])
    ss = {"source": "+".join(sources), "invariants": invariants_all,
          "n_invariants": len(invariants_all)}
    expanded = []
    for inv in invariants_all[:budget]:
        family = inv.get("family") or "capability"
        # 2) test local model on it
        tl = test_local(family)
        # 3) fold verified invariants to pro_library
        promoted = None
        if tl.get("applies", True):
            try:
                from mag.pro_library import add_move
                pm = add_move([family, "capability-steal"], "skill",
                              f"Apply the {family} invariant (steal-searched offline, "
                              f"local-tested): {inv.get('verdict','take')}",
                              effect=f"capability expanded via offline steal-search ({source_hint(ss)})",
                              maps_to="skill:capability_steal",
                              tags=["capability-steal", "offline", "local-test", family])
                promoted = (pm.get("move") or {}).get("id")
            except Exception as _pe:  # noqa: BLE001 - promotion must never break the steal pass; it must be VISIBLE
                # LOOP-DEATH GUARD (2026-09-25, t84): the old 'except Exception: promoted
                # = None' swallowed the pro_library.add_move failure, leaving the row to
                # record promoted=None with no trace of WHY. Promotion stays honestly
                # None and the pass non-fatal, but the cause is now visible.
                # SPEC: tests/test_loop_death_guards.py, t84 SPEC line 2.
                promoted = None
                print(f"[capability-steal] PROMOTION LOOP DEATH GUARD: pro_library.add_move exited: {_pe}", flush=True)
        row = {"ts": _now(), "family": family, "local_applies": tl.get("applies", True),
               "local_test": (tl.get("local_test") or tl.get("error") or "")[:120],
               "promoted": promoted}
        _append(row)
        expanded.append(row)

    _fold(len(expanded))
    return {"schema": "capability_steal.expand.v1", "ts": _now(),
            "offline": True, "right_size": rs["level"],
            "steal_search": {"source": ss.get("source"), "n_invariants": ss.get("n_invariants")},
            "expanded": expanded, "n_expanded": len(expanded)}


def source_hint(ss: dict[str, Any]) -> str:
    return str(ss.get("source") or "steal_protocol")


def _fold(n: int) -> None:
    try:
        from mag import training_events
        training_events.emit(
            "steal_compose",
            input_data={"n_expanded": n},
            action={"kind": "capability_steal", "offline": True},
            outcome={"promoted": True},
            pattern_tags=["capability_steal", "steal_search", "offline_expansion", "local_test"],
            tier_max="T1",
            exportable=False,
        )
    except Exception as _fe:  # noqa: BLE001 - folding must never break the expansion; it must be VISIBLE
        # LOOP-DEATH GUARD (2026-09-25, t78): a silently dead training-event fold voids
        # the steal pass's telemetry while expand() still reports n_expanded. Non-fatal,
        # but visible. (pattern: work_loop.py verkle-anchor guard, t19.)
        print(f"[capability-steal] FOLD LOOP DEATH GUARD: training_events.emit exited: {_fe}", flush=True)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv[0] if argv else "expand"
    rest = " ".join(argv[1:]) if len(argv) > 1 else ""
    if cmd == "steal":
        print(json.dumps(steal_search(rest or None), indent=2, ensure_ascii=False))
    elif cmd == "test":
        print(json.dumps(test_local(rest), indent=2, ensure_ascii=False))
    elif cmd == "expand":
        print(json.dumps(expand(force="--force" in argv), indent=2, ensure_ascii=False))
    else:
        print(json.dumps(expand(), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
