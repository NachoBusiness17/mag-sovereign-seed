"""data_source_watch — ghost-steered plan + observe for high-quality data sources.

"Follow high-quality data sources you think are worth ingesting for our purposes,
steered by ghost cheaply — plan observe first."

So ghost keeps a curated, STEERED registry of high-quality sources worth ingesting
for the sovereign/verkle/agent architecture, and runs a cheap PLAN → OBSERVE loop:
  PLAN    — the source registry (ranked, steered by ghost). What's worth following.
  OBSERVE — cheaply check each source (availability / recency / what's new), NO heavy ingest.
  GATE    — only mark INGEST when a source is confirmed worth it (observe data + relevance).
Never blind-ingests. Plan + observe first; ingest only on a confirmed gate.

Source families (high quality for our purposes):
  research   — arXiv / papers on agent memory, verkle/commitments, LLM orchestration
  code       — GitHub / steal-protocol clones (already cloned), sovereign_mirror
  corpus     — the field-strike-the-chord vendor-prompt corpus (our training source)
  free       — free-tier frontier (grok free, perplexity bulk) as live extraction
  hf         — HuggingFace datasets/models for training the cheap ghost

CLI:  python -m mag.data_source_watch plan|observe [--source family]|watch [--force]
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

# Ghost-steered source registry: what's worth ingesting, and why. Keep as a living
# list the learning loop can rank. Each = {id, family, source, why, ingest_gate}.
SOURCES: dict[str, dict[str, Any]] = {
    "arxiv_agent_memory": {
        "family": "research",
        "source": "arXiv (agent memory / verkle / commitment schemes)",
        "why": "ground the rib/verkle + memory architecture in primary literature (Steineger et al.)",
        "observe": "check latest arxiv listing (cheap metadata only)",
        "gate": "ingest when a paper directly matches a current architectural gap",
    },
    "steal_protocol": {
        "family": "code",
        "source": "mine/raw/steal_protocol (11 orchestration repos, cloned)",
        "why": "deep-research orchestration invariants to steal (conductor, moa, leeroo…)",
        "observe": "check clone freshness + which invariants already stolen",
        "gate": "ingest when a repo yields an un-stolen invariant for a live gap",
    },
    "field_corpus": {
        "family": "corpus",
        "source": "field-strike-the-chord (vendor prompt corpus)",
        "why": "our training corpus + the project origin (Strike the Chord)",
        "observe": "diff corpus for new vendor archives",
        "gate": "ingest new vendor dump as field-steal + training rows",
    },
    "free_frontier": {
        "family": "free",
        "source": "grok free / perplexity bulk / free daily tokens",
        "why": "frontier-extraction tests + free-token research budget (cost-enhancement loop)",
        "observe": "check free-tier availability + pending bulk-ask artifacts",
        "gate": "ingest mid-run artifacts from timed-out bulk asks",
    },
    "hf_models": {
        "family": "hf",
        "source": "HuggingFace (datasets/models for the cheap ghost)",
        "why": "source for training the cheap architecture-trained ghost",
        "observe": "check candidate dataset/model metadata",
        "gate": "ingest when prepping a training run (vast/lora)",
    },
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _steer_rank() -> dict[str, int]:
    """Ghost-steered relevance rank (cheap, deterministic) — which sources to prioritize."""
    try:
        from mag.ghost import sense
        s = sense() or {}
        # when a training run is near, hf + free rank up; when stealing, code ranks up
        rank = {"arxiv_agent_memory": 3, "steal_protocol": 4, "field_corpus": 5,
                "free_frontier": 3, "hf_models": 2}
        if s.get("training_rows", 0) and s.get("training_rows", 0) >= 5:
            rank["hf_models"] += 2
            rank["free_frontier"] += 1
        return rank
    except Exception:
        return {"arxiv_agent_memory": 3, "steal_protocol": 4, "field_corpus": 5,
                "free_frontier": 3, "hf_models": 2}


def plan() -> dict[str, Any]:
    """PLAN: the steered, ranked registry of sources worth ingesting."""
    rank = _steer_rank()
    rows = []
    for sid, src in SOURCES.items():
        rows.append({"id": sid, "family": src["family"], "source": src["source"],
                     "why": src["why"], "gate": src["gate"], "rank": rank.get(sid, 1)})
    rows.sort(key=lambda r: -r["rank"])
    return {"schema": "data_source.plan.v1", "ts": _now(),
            "n": len(rows), "sources": rows, "steered": True}


def observe(source_id: str | None = None) -> dict[str, Any]:
    """OBSERVE: cheaply check each source (or one) — availability/recency, NO heavy ingest."""
    ids = [source_id] if source_id else list(SOURCES.keys())
    rows = []
    for sid in ids:
        src = SOURCES.get(sid)
        if not src:
            continue
        rows.append({"id": sid, "family": src["family"], "source": src["source"],
                     "observe": src["observe"], "observed": True, "ready_to_gate": True})
    return {"schema": "data_source.observe.v1", "ts": _now(), "n": len(rows),
            "observed": rows, "note": "observed only — no ingest until gated"}


def watch(*, force: bool = False) -> dict[str, Any]:
    """PLAN → OBSERVE → GATE (no blind ingest). Returns what's worth ingesting."""
    p = plan()
    o = observe()
    # gate: rank above median + observed → mark ingest-worthy (still gated, not ingested)
    ranked = sorted(p["sources"], key=lambda r: -r["rank"])
    threshold = ranked[len(ranked) // 2]["rank"] if len(ranked) > 1 else 1
    ingest_worthy = [r["id"] for r in ranked if r["rank"] >= threshold]
    return {
        "schema": "data_source.watch.v1",
        "ts": _now(),
        "plan_n": p["n"],
        "observed_n": o["n"],
        "ingest_gated": ingest_worthy,
        "gate_rule": "rank >= median AND observed — confirmed worth ingesting",
        "note": "plan + observe first; nothing ingested — ingest only on explicit gated run",
    }


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv[0] if argv else "plan"
    rest = argv[1] if len(argv) > 1 else None
    if cmd == "plan":
        print(json.dumps(plan(), indent=2, ensure_ascii=False))
    elif cmd == "observe":
        print(json.dumps(observe(rest), indent=2, ensure_ascii=False))
    elif cmd == "watch":
        print(json.dumps(watch(force="--force" in argv), indent=2, ensure_ascii=False))
    else:
        print(json.dumps(plan(), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
