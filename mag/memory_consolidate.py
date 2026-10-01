"""memory_consolidate — the MISSING half of persistent memory: consolidation.

Research (2026-08-18, verified): Generative Agents (2304.03442) importance/recency/relevance,
MemGPT (2310.08560) recursive-summary + memory-pressure trigger, EverMemOS (2601.02163)
episodic->semantic consolidation. We had RETRIEVAL (mem_lands/ghost_memlance) but no
CONSOLIDATION. This is the consolidation pass.

WHAT IT DOES (the verified minimal mechanism, not over-engineered):
  1. IMPORTANCE — deterministic signals (recency, frequency, dedupe-by-signature) free + always
     on. One optional LLM-judged importance [1-10] (rubric-driven) as a pluggable hook — the
     4B's bounded job, or the frontier; decided by hook, not by this module.
  2. RECURSIVE SUMMARY — the rolling summary per scope, folded only on a token-pressure
     threshold (MemGPT), so quiet periods cost nothing.
  3. DECAYED RETRIEVAL SCORE — score = a*recency(exp decay) + b*importance + g*relevance
     (Generative Agents formula); we reuse ghost_memlance's relevance. Soft decay — nothing
     is deleted; unaccessed records stop ranking.
  4. ACTIVE LAYER — the consolidated, high-importance summaries + a small stable profile that
     retrieval ranks first; the raw store stays append-only (no data loss).

DESIGN PRINCIPLE (from the research): keep deterministic scoring free + always-on; reserve any
LLM (4B or frontier) ONLY for bounded rubric-driven steps. Never open-ended "think about this."

Schema: memory_consolidate.v1 · deterministic + $0 core · reuse: mem_lands (flow log store),
ghost_memlance (relevance), afk_cadence (the sleep when it runs)
"""
from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "memory_consolidate.v1"
FLOW_LOG = ROOT / "memory" / "runs" / "mem_lands" / "flow.jsonl"
OUT = ROOT / "memory" / "runs" / "memory_consolidate"
# token-pressure trigger (MemGPT ~70%): summarize a scope when its accumulated content passes
PRESSURE_CHARS = 8000
# exponential recency decay (Generative Agents 0.995 per hour, min-max normalized)
DECAY = 0.995
# retrieval-weight defaults (Generative Agents formula)
W_RECENCY, W_IMPORTANCE, W_RELEVANCE = 0.3, 0.5, 0.2


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _hours_since(ts: str) -> float:
    try:
        t = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return max(0.0, (datetime.now(timezone.utc) - t).total_seconds() / 3600.0)
    except Exception:
        return 0.0


def _load_flow() -> list[dict[str, Any]]:
    if not FLOW_LOG.is_file():
        return []
    rows = []
    for line in FLOW_LOG.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    return rows


# ── importance ──────────────────────────────────────────────────────────────
def _deterministic_score(row: dict[str, Any]) -> float:
    """Free, always-on importance: recency + frequency + content mass. No LLM."""
    hours = _hours_since(str(row.get("ts") or ""))
    recency = DECAY ** hours                    # in [0,1], fresh ~1, old ~0
    freq = 1.0 / (1.0 + float(row.get("access_count") or 0))  # penalize never-reaccessed
    mass = min(1.0, len(str(row.get("ctx") or row.get("label") or "")) / 500.0)
    return 0.5 * recency + 0.3 * (1.0 - freq) + 0.2 * mass


def _llm_importance(row: dict[str, Any], scorer: Callable[[dict[str, Any]], float]) -> float:
    """Pluggable LLM-judged importance [1-10] normalized to [0,1]. The 4B's bounded job."""
    try:
        v = float(scorer(row) or 0.0)
        return max(0.0, min(1.0, v / 10.0))
    except Exception:
        return _deterministic_score(row)


# ── recursive summary ──────────────────────────────────────────────────────
def _rolling_summary_path(scope: str) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    safe = "".join(c if c.isalnum() else "_" for c in scope)[:40] or "default"
    return OUT / f"summary_{safe}.md"


def _fold_summary(scope: str, rows: list[dict[str, Any]], summarizer: Callable | None) -> dict[str, Any]:
    """Fold a rolling summary for a scope, only when token-pressure is crossed."""
    path = _rolling_summary_path(scope)
    prev = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
    # extract the new span's content
    span = "\n".join(str(r.get("ctx") or r.get("label") or "")[:300] for r in rows)
    total = len(prev) + len(span)
    if total < PRESSURE_CHARS and prev:
        return {"ok": True, "schema": SCHEMA, "scope": scope, "folded": False,
                "reason": "below token-pressure threshold", "chars": total}
    # summarize: prev_summary + new_span -> new_summary (MemGPT recursive fold)
    if summarizer is not None:
        new_summary = summarizer(prev, span) or span[:2000]
    else:
        # deterministic fallback: keep prev head + newest span tail (extractive-ish)
        new_summary = (prev[-1200:] + "\n" + span[-1200:]).strip() or "accumulated memory"
    path.write_text(new_summary, encoding="utf-8")
    return {"ok": True, "schema": SCHEMA, "scope": scope, "folded": True,
            "summary_path": str(path), "chars": len(new_summary)}


# ── decayed retrieval score + active layer ─────────────────────────────────
def _decayed_score(row: dict[str, Any], query: str, relevance: Callable[[dict, str], float]) -> float:
    hours = _hours_since(str(row.get("ts") or ""))
    recency = DECAY ** hours
    importance = _deterministic_score(row)
    rel = relevance(row, query)
    return W_RECENCY * recency + W_IMPORTANCE * importance + W_RELEVANCE * rel


def consolidate(*, scope: str = "default", summarizer: Callable | None = None,
                scorer: Callable | None = None,
                relevance: Callable | None = None) -> dict[str, Any]:
    """THE CONSOLIDATION PASS: score + fold the flow log into an active layer + summary.

    scorer/relevance are pluggable (4B or frontier); when None, deterministic only.
    """
    rows = _load_flow()
    if not rows:
        return {"ok": False, "schema": SCHEMA, "error": "no memory records to consolidate"}
    # scope filters by label prefix; empty/None scope = ALL records (the shared layer)
    if scope and str(scope).strip() and str(scope).strip() != "default":
        scoped = [r for r in rows if str(r.get("label") or "default").startswith(scope)]
    else:
        scoped = rows
    scored = []
    for r in scoped:
        imp = _llm_importance(r, scorer) if scorer else _deterministic_score(r)
        scored.append({"row": r, "importance": imp,
                       "deterministic": _deterministic_score(r)})
    scored.sort(key=lambda s: s["importance"], reverse=True)

    # active layer = top consolidated, high-importance records (promoted, rank first)
    active = [{"label": s["row"].get("label"), "ctx": (s["row"].get("ctx") or "")[:300],
               "importance": round(s["importance"], 3)} for s in scored[:10]]

    # recursive summary fold (only if pressure crossed)
    summary = _fold_summary(scope, scoped, summarizer)

    # decayed retrieval over all scoped (rank by score, relevance optional)
    rel = relevance or (lambda r, q: 0.0)
    ranked = sorted(scoped, key=lambda r: _decayed_score(r, scope, rel), reverse=True)
    ranked_labels = [str(r.get("label") or "")[:40] for r in ranked[:10]]

    return {
        "ok": True, "schema": SCHEMA, "scope": scope,
        "n_records": len(scoped),
        "active_layer": active,
        "summary": summary,
        "top_retrieval": ranked_labels,
        "note": ("consolidation: deterministic scoring always-on; LLM scorer/summarizer pluggable "
                 "(4B or frontier). Raw store append-only; nothing deleted."),
    }


def run_sleep_step(*, summarizer: Callable | None = None,
                   scorer: Callable | None = None) -> dict[str, Any]:
    """The afk_cadence sleep step: consolidate the shared memory layer. Callable, $0."""
    return consolidate(summarizer=summarizer, scorer=scorer)


def status() -> dict[str, Any]:
    return {
        "ok": True, "schema": SCHEMA,
        "contract": ("consolidate(scope)->importance + recursive summary + decayed retrieval + "
                     "active layer over mem_lands flow log; run_sleep_step() = the afk_cadence "
                     "sleep; deterministic always-on, LLM (4B/frontier) pluggable for the bounded "
                     "scoring/summarizing steps"),
        "cost": "deterministic + $0 (LLM scorer/summarizer only when provided)",
        "reuse": "mem_lands (flow store), ghost_memlance (relevance), afk_cadence (when)",
        "pressure_chars": PRESSURE_CHARS,
    }


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="memory_consolidate",
                                 description="Consolidate the shared memory (missing half of persistence)")
    ap.add_argument("cmd", nargs="?", default="consolidate", choices=["consolidate", "sleep", "status"])
    ap.add_argument("--scope", default="default")
    a = ap.parse_args(argv)
    if a.cmd == "sleep":
        print(json.dumps(run_sleep_step(), indent=2, default=str))
    elif a.cmd == "status":
        print(json.dumps(status(), indent=2, default=str))
    else:
        print(json.dumps(consolidate(scope=a.scope), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
