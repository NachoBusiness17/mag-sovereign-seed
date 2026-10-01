"""breakthrough_loop — fold every bug-fix / breakthrough through ghost, CHEAP.

The operator's tesuji: "whenever we make a bug fix or major breakthrough, run it
through the ghost as the everything improver does, to (1) improve the testing
process and (2) take the lessons on model behavior to our puppeteering protocol
for research purposes." And: "can we do the same thing with ghost's tools more
efficiently — mem pointers, time, etc."

THE EFFICIENT DESIGN (no heavy model pass per fix):
  * CAPTURE  — each fix/breakthrough becomes a compact record, verkle/mem-POINTER
               anchored (the anchor is the mem pointer; we never re-send prose).
  * FOLD $0  — deterministic, no LLM: (a) a TESTING lesson folds into the testing
               process (improve_loop + skill_ledger + training_events), and (b) a
               MODEL-BEHAVIOR lesson folds into the puppeteering protocol's lesson
               log (tools/pupeteer_gauntlet research reads it).
  * CADENCE  — on TIME (governor cadence) aggregate accumulated pointers; only if
               a cluster crosses threshold do we note a pending synthesis for the
               cheapest capable tier (Law #7 cheap-first — never grok by default).

So the review loop costs ~$0 and runs instantly; the model only ever sees a compact
pointer, and only when there's enough signal to synthesize.

Schema: breakthrough_loop.v1 · store: memory/runs/breakthrough/*.json + pointers index
CLI:  python -m mag.breakthrough_loop capture "<title>" --kind bugfix --gap "..." --behavior "..."
      python -m mag.breakthrough_loop cadence | status
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT

RUNS = ROOT / "memory" / "runs" / "breakthrough"
POINTERS = RUNS / "pointers.jsonl"
PUPPET_LESSONS = ROOT / "memory" / "runs" / "pupeteer" / "lessons.jsonl"
SCHEMA = "breakthrough_loop.v1"

_KINDS = {"bugfix", "breakthrough", "regression", "lesson"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _key(text: str) -> str:
    return hashlib.sha256((text or "").strip().lower().encode()).hexdigest()[:16]


def capture(
    *,
    title: str = "",
    kind: str = "bugfix",
    root_cause: str = "",
    testing_gap: str = "",
    model_behavior: str = "",
    files: list[str] | None = None,
) -> dict[str, Any]:
    """Capture a fix/breakthrough as a compact record + mem pointer. $0, no LLM."""
    title = (title or "").strip()
    if not title:
        return {"ok": False, "error": "title required"}
    kind = (kind or "bugfix").strip().lower()
    if kind not in _KINDS:
        kind = "bugfix"
    key = _key(title)
    pointer = hashlib.sha256(json.dumps({
        "title": title, "kind": kind, "root_cause": root_cause,
        "testing_gap": testing_gap, "model_behavior": model_behavior,
        "files": files or [],
    }, sort_keys=True, default=str).encode()).hexdigest()[:16]

    rec = {
        "schema": SCHEMA, "ts": _now(), "key": key, "pointer": pointer,
        "title": title[:200], "kind": kind,
        "root_cause": (root_cause or "")[:400],
        "testing_gap": (testing_gap or "")[:400],
        "model_behavior": (model_behavior or "")[:400],
        "files": (files or [])[:10],
    }

    # mem pointer -> verkle anchor (the pointer IS the anchor; prose stays local)
    vk: dict[str, Any] = {}
    try:
        from mag import verkle_knot
        vk = verkle_knot.append_verkle_knot({
            "session_id": f"breakthrough:{key}",
            "dominant_theme": f"breakthrough-{kind}",
            "chord_commitment": pointer,
            "dossier_commit": pointer,
            "summary": f"{kind}: {title[:80]} (pointer {pointer[:12]})",
            "purpose": "breakthrough_mem_pointer",
        })
    except Exception as e:
        vk = {"ok": False, "error": str(e)[:120]}

    # store the full record locally (the pointer resolves here)
    RUNS.mkdir(parents=True, exist_ok=True)
    (RUNS / f"{key}.json").write_text(json.dumps(rec, indent=2, ensure_ascii=False), encoding="utf-8")
    with POINTERS.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"key": key, "pointer": pointer, "ts": _now(), "kind": kind}, ensure_ascii=False) + "\n")

    # ---- fold: (a) TESTING lesson (cheap, deterministic) ----
    testing = _fold_testing(rec)
    # ---- fold: (b) MODEL-BEHAVIOR lesson -> puppeteering protocol ----
    puppet = _fold_puppet(rec)

    return {
        "schema": SCHEMA, "ok": True, "id": key, "pointer": pointer,
        "kind": kind, "title": title[:200],
        "verkle_root": vk.get("verkle_root"), "verkle_ok": bool(vk.get("ok")),
        "testing_lesson": testing, "puppet_lesson": puppet,
        "note": "captured at $0 (deterministic fold + mem pointer); model synthesis only on cadence if clustered",
    }


def _fold_testing(rec: dict[str, Any]) -> dict[str, Any]:
    """Derive + fold a testing-process lesson. Deterministic, $0."""
    gap = (rec.get("testing_gap") or "").strip()
    lesson = ""
    if gap:
        # simplest reliable signal: name the area to test so a test gets written
        lesson = f"test: {gap[:200]}"
    # always: fixes/breakthroughs should land with a test (the meta-lesson)
    if not lesson:
        lesson = "test: capture this fix as a regression test (every fix = a test)"
    folded_test = False
    try:
        from mag import training_events
        training_events.emit(
            "testing_improvement",
            input_data={"title": rec["title"], "kind": rec["kind"], "gap": gap[:200]},
            action={"kind": "breakthrough_loop_testing", "lesson": lesson[:200]},
            outcome={"folded": True},
            pattern_tags=["breakthrough_loop", "testing_process", "regression_test"],
            tier_max="T1", exportable=False,
        )
        folded_test = True
    except Exception:
        pass
    try:
        from mag import skill_ledger
        skill_ledger.record_decision(
            goal=f"[improve-testing] {rec['title'][:120]}",
            outcome=lesson[:200],
            context=f"kind={rec['kind']}",
        )
    except Exception:
        pass
    return {"lesson": lesson, "folded": folded_test}


def _fold_puppet(rec: dict[str, Any]) -> dict[str, Any]:
    """Fold the model-behavior lesson into the puppeteering protocol lesson log."""
    behavior = (rec.get("model_behavior") or "").strip()
    if not behavior:
        return {"lesson": "", "folded": False, "note": "no model_behavior provided"}
    PUPPET_LESSONS.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "ts": _now(), "source": "breakthrough_loop", "kind": rec["kind"],
        "title": rec["title"][:160], "pointer": rec["pointer"],
        "model_behavior": behavior[:400],
        "research_hint": "read this into a pupeteer sweep / classify interaction",
    }
    with PUPPET_LESSONS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return {"lesson": behavior[:400], "folded": True,
            "path": str(PUPPET_LESSONS), "count": _puppet_count()}


def _puppet_count() -> int:
    if not PUPPET_LESSONS.is_file():
        return 0
    return sum(1 for l in PUPPET_LESSONS.read_text(encoding="utf-8", errors="replace").splitlines() if l.strip())


def status() -> dict[str, Any]:
    """Count captured pointers + puppet lessons. $0."""
    n = 0
    if POINTERS.is_file():
        n = sum(1 for l in POINTERS.read_text(encoding="utf-8", errors="replace").splitlines() if l.strip())
    by_kind: dict[str, int] = {}
    if POINTERS.is_file():
        for l in POINTERS.read_text(encoding="utf-8", errors="replace").splitlines():
            if not l.strip():
                continue
            try:
                k = json.loads(l).get("kind", "bugfix")
                by_kind[k] = by_kind.get(k, 0) + 1
            except Exception:
                pass
    return {"schema": SCHEMA, "ok": True, "captured": n, "by_kind": by_kind,
            "puppet_lessons": _puppet_count(), "pointer_index": str(POINTERS)}


def run_cadence(*, threshold: int = 3) -> dict[str, Any]:
    """On TIME: aggregate pointers; note a pending synthesis only if a cluster
    crosses threshold (cheap-first, never grok by default). $0."""
    st = status()
    captured = st.get("captured", 0)
    clusters = {k: v for k, v in (st.get("by_kind") or {}).items() if v >= threshold}
    pending = []
    for kind, count in clusters.items():
        pending.append({"kind": kind, "count": count,
                        "action": f"synthesize {count} {kind}(s) via cheapest capable tier (research pack)"})
    return {
        "schema": SCHEMA, "ok": True, "ts": _now(), "captured": captured,
        "clusters_over_threshold": clusters, "pending_synthesis": pending,
        "escalate": bool(pending),
        "note": "cheap aggregate; escalate only on cluster threshold (Law #7)",
    }


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv[0] if argv else "status"
    rest = " ".join(argv[1:]).strip()
    if cmd == "capture":
        out = capture(title=rest)
    elif cmd == "cadence":
        out = run_cadence()
    else:
        out = status()
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
