"""batch_scribe — k3s META-ANALYSIS over big-batch drain results (2026-08-24).

The operator's question: "in these big batches shouldn't we have some sort of meta analysis by
the k3's?" — YES. The cluster already runs mag-swarm + mag-warnings CronJobs over the shared
state PVC. This is the third one: a SCRIBE that reads every completed detached drain
(batch_drain.collect()) and CLASSIFIES the produced answers — what KIND of knowledge each batch
created, quality trends, lane health, drift — then folds a meta-analysis report + labeled rows.

The proven classify pattern (tools/classify_corpus): LOCAL model bulk-classifies every item
($0, private, gemma4:latest proven at classification), a cheap deepseek-v4-flash sample audits
for drift. Same here, pointed at the BATCH RESULTS instead of a static corpus.

  scribe()    -> the pass: read collected drains -> classify each answer -> per-batch summary
                 -> meta-report -> skill_ledger labeled rows.
  report()    -> read the latest scribe report (what the k3s scribe found).
  classify(text) -> one item -> (label, confidence) via local gemma4.

Schema: batch_scribe.v1 · runs in-cluster (CronJob) over the shared PVC · deterministic + $0
CLI: python -m mag.batch_scribe scribe | report | classify "text"
"""
from __future__ import annotations

import argparse
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

SCHEMA = "batch_scribe.v1"
REPORTS = ROOT / "memory" / "runs" / "fuel_feed" / "scribe"

# What KIND of knowledge each answer produced (the fold taxonomy — same family as the
# percolator's invariant/explore and the ox_resident drill kinds).
LABELS = ["mechanism", "guard", "fold", "invariant", "edge_case", "weak"]
# A weak answer = refused/hedged/empty (q < floor) — the scribe flags it, the drain escalated it.

LOCAL_MODEL = "gemma4:latest"      # proven at classification, fast, free (classify_corpus)
AUDIT_MODEL = "deepseek-v4-flash"  # cheap control on the sample


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _call(provider: str, model: str, system: str, user: str, *, max_tokens: int) -> str:
    from models.providers import chat_provider
    tier = "T2" if provider == "deepseek" else "T1"
    res = chat_provider(provider, system, user, model=model, temperature=0.0,
                        max_tokens=max_tokens, tier=tier)
    return str(res.get("text") or "").strip()


def classify(text: str) -> tuple[str, float]:
    """One answer -> (label, confidence). Local gemma4 ($0). Label from the fold taxonomy."""
    if not (text or "").strip():
        return "weak", 0.0
    system = (f"Classify this reasoning answer into EXACTLY one of: {', '.join(LABELS)}. "
              "A 'mechanism' is a buildable mechanism; 'guard' is a structural guard; 'fold' is "
              "a synthesis/decision; 'invariant' is a standing law; 'edge_case' is a failure-mode "
              "analysis; 'weak' is refusal/hedge/empty. Reply with only the label word.")
    out = _call("ollama", LOCAL_MODEL, system, text[:1200], max_tokens=16)
    low = out.lower().strip(" .:[]\"'")
    for lbl in LABELS:
        if lbl in low:
            return lbl, 1.0 if out else 0.0
    return LABELS[0], 0.0


def _audit(answers: list[tuple[str, str]], n: int = 5) -> tuple[int, int]:
    """Sample-audit with deepseek-v4-flash: how many of the sample agree with the local label."""
    mismatches = 0
    for text, local_label in answers[:n]:
        try:
            system = (f"Classify into EXACTLY one of: {', '.join(LABELS)}. "
                      "Reply with only the label word.")
            out = _call("deepseek", AUDIT_MODEL, system, text[:800], max_tokens=16)
            low = out.lower().strip(" .:[]\"'")
            audit_label = next((l for l in LABELS if l in low), LABELS[0])
            if audit_label != local_label:
                mismatches += 1
        except Exception:  # noqa: BLE001
            pass
    return len(answers[:n]), mismatches


def _answers_from_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flatten detached drain results -> per-answer rows (canonical, lane, quality, text)."""
    out: list[dict[str, Any]] = []
    for res in results or []:
        for item in (res.get("results") or []):
            text = str(item.get("answer") or item.get("text") or "").strip()
            if not text:
                continue
            out.append({"canonical": item.get("canonical", ""),
                        "lane": item.get("lane", ""),
                        "quality": item.get("quality"),
                        "gate": item.get("gate", ""),
                        "batch": res.get("batch"),
                        "answer": text[:1200]})
    return out


def scribe() -> dict[str, Any]:
    """THE SCRIBE PASS: read collected drains -> classify each answer -> per-batch summary ->
    meta-report -> skill_ledger labeled rows. Runs in-cluster over the shared PVC."""
    from mag import batch_drain

    c = batch_drain.collect()
    results = c.get("results") or []
    answers = _answers_from_results(results)
    if not answers:
        return {"ok": True, "schema": SCHEMA, "n_drains": len(results), "n_answers": 0,
                "note": "no completed detached drains yet — the scribe waits for real data"}

    labeled: list[dict[str, Any]] = []
    for a in answers:
        label, conf = classify(a["answer"])
        labeled.append({**a, "label": label, "confidence": conf})

    # per-label + per-lane + per-batch rollups (deterministic, from the labels)
    by_label: dict[str, int] = {}
    by_lane: dict[str, dict[str, Any]] = {}
    by_batch: dict[int, dict[str, Any]] = {}
    weak = 0
    for a in labeled:
        by_label[a["label"]] = by_label.get(a["label"], 0) + 1
        if a["label"] == "weak":
            weak += 1
        lane = a["lane"] or "?"
        bl = by_lane.setdefault(lane, {"n": 0, "weak": 0, "labels": {}})
        bl["n"] += 1
        if a["label"] == "weak":
            bl["weak"] += 1
        bl["labels"][a["label"]] = bl["labels"].get(a["label"], 0) + 1
        bb = by_batch.setdefault(int(a["batch"] or 0), {"n": 0, "labels": {}})
        bb["n"] += 1
        bb["labels"][a["label"]] = bb["labels"].get(a["label"], 0) + 1

    # audit a sample (cheap control, drift detection)
    n_audit, mismatches = _audit([(a["answer"], a["label"]) for a in labeled], n=5)

    # fold labeled rows to the skill ledger (the LoRA training corpus)
    from mag.skill_ledger import record_labeled_row
    folded = 0
    for a in labeled:
        try:
            record_labeled_row(text=a["answer"][:800], label=a["label"],
                               classifier=LOCAL_MODEL, confidence=a["confidence"],
                               audited_by=AUDIT_MODEL if a.get("audited") else None,
                               source="batch_scribe")
            folded += 1
        except Exception:  # noqa: BLE001
            pass

    report = {
        "schema": SCHEMA,
        "ts": _now(),
        "n_drains": len(results),
        "n_answers": len(labeled),
        "label_distribution": by_label,
        "by_batch": {str(k): v for k, v in sorted(by_batch.items())},
        "by_lane": by_lane,
        "weak_count": weak,
        "audit": {"n": n_audit, "mismatches": mismatches,
                  "drift": round(mismatches / n_audit, 2) if n_audit else None},
        "folded_to_ledger": folded,
        "note": "the k3s scribe classified the batch harvest — what kind of knowledge was made",
    }
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "latest.json").write_text(json.dumps(report, ensure_ascii=False, indent=2),
                                         encoding="utf-8")
    return report


def report() -> dict[str, Any]:
    p = REPORTS / "latest.json"
    if not p.is_file():
        return {"ok": False, "schema": SCHEMA, "error": "no scribe report yet — run scribe()"}
    return {"ok": True, "schema": SCHEMA, "report": json.loads(p.read_text(encoding="utf-8"))}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="mag.batch_scribe")
    ap.add_argument("cmd", nargs="?", default="scribe", choices=["scribe", "report"])
    ap.add_argument("text", nargs="*", default=None)
    a = ap.parse_args(argv)
    if a.cmd == "scribe":
        print(json.dumps(scribe(), indent=2, ensure_ascii=False, default=str))
    elif a.cmd == "report":
        print(json.dumps(report(), indent=2, ensure_ascii=False, default=str))
    else:
        print(json.dumps(classify(" ".join(a.text or [])), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
