"""ox_scout — the ADAPTIVE miner built from the megaburn's own lessons (2026-08-23).

The thousand-ask grid (ox_megaburn3) taught us three things, and this is the process that
acts on them instead of repeating them:

1. BREADTH-NOT-DEPTH: a flat core x scope x context grid spreads thin and burns budget on
   re-deriving doctrine. FIX: gate each result with the novelty index, then DRILL depth-chains
   on the cells that actually yielded something real.

2. CONSENSUS-ILLUSION: the 8 contexts mostly re-skin one mechanism -> correlated redundancy,
   not N independent voices. FIX: instead of re-skinning a core on 8 surfaces, ask the same
   core the 4 depth-questions that probe DIFFERENT things (hardest edge, minimal impl,
   independent-implementation acceptance, adversarial red-team).

3. FOLLOW THE SURPRISE: the grid fires blindly with no feedback. FIX: score results, feed the
   score back, and let high-yield cells get the next round of budget.

Schema: ox_scout.v1
Run:  python -m mag.ox_scout                # one adaptive round (discover + drill + fold)
      python -m mag.ox_scout --summary       # banked depth-asks + high-yield cells
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:  # noqa: BLE001
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

from mag.ox_megaburn3 import CORES, SCOPES, CONTEXTS  # noqa: E402
from mag.ox_novelty_index import _noise_reason, _is_novel_core  # noqa: E402

SCHEMA = "ox_scout.v1"
OUT_DIR = ROOT / "handoff"
LEDGER = ROOT / "memory" / "runs" / "ox_scout_ledger.jsonl"

# 4 DEPTH-CHAIN questions per high-yield (core, scope). Each probes a DIFFERENT thing, so we get
# independent signal instead of 8 re-skins of the same mechanism.
DEPTH_ASKS: list[tuple[str, str]] = [
    ("hardest_edge", "Go deeper on the hardest edge of this: {core}. Name the SINGLE most dangerous "
                     "failure mode and the deterministic guard that makes it structurally impossible "
                     "— not policy, structure."),
    ("minimal_impl", "Give the minimal standalone implementation of {core} in pure stdlib Python "
                     "(~20-40 lines, runnable), with a self-test that proves it behaves byte-identically "
                     "from a fixed start. Concrete code, no prose."),
    ("independent_accept", "Give the acceptance test that TWO independent implementations of {core} must "
                           "pass to prove byte-identical roots from the same start state. Exact assertions, "
                           "not vibes."),
    ("adversarial", "Red-team {core} ADVERSARIALLY: assume the implementer is lazy and the verifier is "
                    "hostile. Name the one bypass most likely to actually ship, and the guard that closes it."),
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm(s: str) -> str:
    return s.strip().lower()


def high_yield_cells() -> list[dict]:
    """Cells (core x scope) that the novelty index tagged novel? — these are the ones worth drilling."""
    from mag.ox_novelty_index import build as _idx_build
    _idx_build()  # ensure the index is fresh
    from mag import ox_novelty_index
    rows = [json.loads(l) for l in ox_novelty_index.INDEX.read_text(encoding="utf-8").splitlines()
            if l.strip() and json.loads(l).get("tag") == "novel?"]
    seen: dict[tuple[str, str], int] = {}
    for r in rows:
        seen[(r["core"], r["scope"])] = seen.get((r["core"], r["scope"]), 0) + 1
    return [{"core": c, "scope": s, "variants": v} for (c, s), v in seen.items()]


def drill_asks(core: str) -> list[tuple[str, str]]:
    """Depth-chain asks for one high-yield core. These are the deep probes, not re-skins."""
    out: list[tuple[str, str]] = []
    for tag, tpl in DEPTH_ASKS:
        prompt = tpl.format(core=core)
        h = hashlib.sha256(_norm(prompt).encode("utf-8")).hexdigest()[:12]
        out.append((f"scout-{h[:10]}-{tag}", prompt))
    return out


def _done_names() -> set[str]:
    done: set[str] = set()
    for p in OUT_DIR.glob("OX_SCOUT_*.json"):
        try:
            d = json.loads(p.read_text(encoding="utf-8", errors="replace"))
            if d.get("ok"):
                done.add(p.stem.removeprefix("OX_SCOUT_"))
        except Exception:  # noqa: BLE001
            pass
    return done


def _bank(name: str, res: dict[str, Any], core: str, kind: str) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / f"OX_SCOUT_{name}.json").write_text(
        json.dumps({"schema": SCHEMA, "name": name, "core": core, "kind": kind,
                    "ts": _now(), "ok": bool(res.get("ok")), "cost": res.get("cost", 0.0),
                    "content": res.get("content") or "", "reasoning": res.get("reasoning") or "",
                    "error": res.get("error", "")}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"name": name, "core": core, "kind": kind, "ts": _now(),
                            "ok": bool(res.get("ok")), "content_chars": len(res.get("content") or "")},
                           ensure_ascii=False) + "\n")


def _fire(seat, name: str, prompt: str, max_tokens: int, timeout: int) -> dict[str, Any]:
    try:
        return seat.chat(
            "You are the adaptive scout. This is a DEPTH drill on a mechanism we already found "
            "valuable. Go one level deeper than the first pass — exact, grounded, runnable, no fluff.",
            prompt, max_tokens=max_tokens, timeout=timeout, tier="T2")
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"}


def run(*, max_tokens: int = 8000, timeout: int = 480, drill: int = 2) -> dict[str, Any]:
    """One adaptive round: pick the top high-yield cells, drill depth-chains on them, fold."""
    from mag import ox_seat
    done = _done_names()
    cells = high_yield_cells()
    # prefer the highest-yield (most variants -> most evidence) cells not yet drilled
    cells_sorted = sorted(cells, key=lambda c: -c["variants"])
    targets = [c for c in cells_sorted if not any(d.startswith("scout-") and d.endswith("-hardest_edge")
                                                   and c["core"] in d for d in done)][:drill]
    fired: list[dict] = []
    new_ok = 0
    for t in targets:
        core = t["core"]
        for name, prompt in drill_asks(core):
            if name in done:
                continue
            res = _fire(ox_seat, name, prompt, max_tokens, timeout)
            _bank(name, res, core, name.rsplit("-", 1)[-1])
            if res.get("ok") and (res.get("content") or "").strip():
                new_ok += 1
            fired.append({"name": name, "core": core[:40], "ok": bool(res.get("ok")),
                          "content_chars": len(res.get("content") or "")})
    return {"ok": True, "schema": SCHEMA, "drill_targets": len(targets),
            "fired": len(fired), "new_ok": new_ok, "fired_detail": fired,
            "high_yield_cells": len(cells), "done_total": len(_done_names())}


def summary() -> dict[str, Any]:
    rows = [json.loads(l) for l in LEDGER.read_text(encoding="utf-8", errors="replace").splitlines()
            if l.strip()] if LEDGER.exists() else []
    by_kind: dict[str, int] = {}
    for r in rows:
        by_kind[r.get("kind")] = by_kind.get(r.get("kind"), 0) + 1
    return {"ok": True, "schema": SCHEMA, "total_depth_asks": len(rows), "by_kind": by_kind,
            "banked_files": len(_done_names())}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", nargs="?", default="run", choices=["run", "summary", "cells"])
    ap.add_argument("--drill", type=int, default=2)
    a = ap.parse_args()
    if a.cmd == "summary":
        print(json.dumps(summary(), indent=2, ensure_ascii=False))
    elif a.cmd == "cells":
        for c in sorted(high_yield_cells(), key=lambda x: -x["variants"]):
            print(f"{c['variants']:3d}  {c['core'][:70]}")
    else:
        print(json.dumps(run(drill=a.drill), indent=2, ensure_ascii=False, default=str))
