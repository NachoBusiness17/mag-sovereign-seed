"""Composite foundation proof: independent-witness consensus (2026-08-25).

Three independent free lanes, ONE grounded question with a known ground truth. Measure
(a) per-lane correctness, (b) agreement across lanes. The composite's whole premise is that
independent bodies, asked the same thing, converge on the same grounded answer.

Per the autonomous mandate: iterate -> test. Fold the result to the verkle chain.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"c:\Users\foste\Documents\projects\local_sovereign_agent")
sys.path.insert(0, str(ROOT))

from mag import fuel_feed as ff  # noqa: E402

QUESTION = "What is 12 times 13? Reply with ONLY the integer, nothing else."
GROUND_TRUTH = "156"
LANES = [  # (label, provider, model, extra)
    ("z_ai", "z_ai", "glm-4.7-flash", {"thinking": False}),
    ("groq", "groq", None, {}),
    ("cerebras", "cerebras", None, {}),
]
# B2-521 DORMANT GATE (2026-09-26): the witness roster hardcoded a cerebras seat after
# B2-36 declared cerebras dormant (card-gated 30-day trial, chat 402 no-credit;
# mag/doctor.py:607: dormant is a declared state). Roster entries whose provider id is
# flagged dormant drop out here, the same gate mag/rotation_harness.LANES got in B2-133;
# operator GO flips the flag and the seat returns with no code edit. Receipt:
# watch/inbox/burn_wave_20260926/B2_521_cerebras_stragglers_20260926.md
from mag.dormant import dormant_ids as _dormant_provider_ids  # noqa: E402

LANES = [ln for ln in LANES if ln[1] not in _dormant_provider_ids()]


def ask(label: str, provider: str, model: str | None, extra: dict) -> dict:
    from models.providers import reload_providers, chat_provider
    reload_providers()
    kw = {"tier": "T2", "max_tokens": 64}
    if model:
        kw["model"] = model
    kw.update(extra)
    t0 = datetime.now(timezone.utc)
    try:
        r = chat_provider(provider, system="You are a reasoning engine. Be exact and minimal.",
                          user=QUESTION, **kw)
        text = (r.get("text") or "").strip()
        ok = bool(r.get("ok") and text)
        return {"lane": label, "ok": ok, "text": text,
                "error": (r.get("error") or "")[:100] if not ok else "",
                "ms": int((datetime.now(timezone.utc) - t0).total_seconds() * 1000)}
    except Exception as e:  # noqa: BLE001
        return {"lane": label, "ok": False, "text": "", "error": str(e)[:100],
                "ms": int((datetime.now(timezone.utc) - t0).total_seconds() * 1000)}


def extract_int(text: str) -> str | None:
    import re
    m = re.search(r"-?\d+", text or "")
    return m.group(0) if m else None


def main() -> int:
    answers = [ask(*ln) for ln in LANES]
    for a in answers:
        a["answer"] = extract_int(a["text"])
    correct = [a for a in answers if a["ok"] and a["answer"] == GROUND_TRUTH]
    agreement = len({a["answer"] for a in answers if a["ok"] and a["answer"]})
    n_ok = sum(1 for a in answers if a["ok"])

    result = {
        "ok": True,
        "schema": "consensus_witness.v1",
        "question": QUESTION,
        "ground_truth": GROUND_TRUTH,
        "lanes": answers,
        "summary": {
            "lanes_answered": n_ok,
            "correct": len(correct),
            "distinct_answers": agreement,
            "consensus": "CONVERGED" if (n_ok == len(LANES) and agreement == 1) else
                         ("MAJORITY" if agreement == 1 else "DIVERGED"),
        },
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    print(json.dumps(result, indent=2))
    # persist the full result (logs/ is the honest-byte home for telemetry)
    logs = ROOT / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    with (logs / "consensus_witness.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(result, default=str) + "\n")
    # fold via work_register (verkle knot + shared manifest)
    try:
        from mag.work_register import record
        s = result["summary"]
        kn = record("test", "consensus-witness",
                    path="logs/consensus_witness.jsonl",
                    note=f"{s['consensus']} {s['lanes_answered']}/{len(LANES)} lanes, {s['correct']} correct, "
                         f"{s['distinct_answers']} distinct answers on 12*13")
        print(f"\nFOLDED via work_register (verkle: {kn.get('verkle')})")
    except Exception as e:  # noqa: BLE001
        print(f"\nfold skipped: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
