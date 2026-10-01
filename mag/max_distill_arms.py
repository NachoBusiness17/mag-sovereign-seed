"""MAX_DISTILL — the arm harness + frozen-trace recorder (zcode half, 2026-08-26).

The copilot's half (mag/max_distill.py): SkillCandidate schema, admission validator,
near-miss suite, RAR math. This half: the four arms + the recorder, per the split
(CONVO 2026-08-26T01:12, amended 05:26):

  Arms (VSTR = verified-pass count over an isolated batch):
    A_high            glm-4.7-flash @ z_ai        — plain task, no help
    B_high_info       glm-4.7-flash @ z_ai        — + privileged info (the winning trace
                                                    sketch); controls for info, not policy
    C_max             glm-5.3-flash @ z_ai2       — the frontier ceiling (funded free lane)
    D_high_distilled  glm-4.7-flash @ z_ai        — + the distilled SkillCandidate
                                                    action_policy (what max_distill admits)

  Amendments honored here:
    A1 — every held-out batch emits a mechanically-renamed twin; instances below carry
         rename twins and the report splits twin vs native scores.
    A2 — power/batch-size is pre-registered: BATCH_SIZE=10 per arm; RAR is NOT computed
         unless the C-A gap is >= MIN_DENOMINATOR (2 verified events) — else GAP_TOO_SMALL.
    A3 — MAX+INFO is a pre-committed epoch-2 arm, triggered iff (D-A) >= 1.5x (B-A).
         `report` prints the trigger state; the arm is not implemented until it fires.
    A4 — batch definition frozen: same 10 instances, same order, per arm, per epoch.

  Known-ungated term (flagged, not gated): extractor nondeterminism — D's policy text is
  fixed here (the template policy), so epoch 1 does not ride an LLM extractor.

Recorder: every trial appends one row to memory/runs/max_distill/trials.jsonl with a
sha256 over the canonicalized row — commitment, not summary (the digest-knot doctrine).

CLI:
  python -m mag.max_distill_arms instances          # show the frozen epoch-1 batch
  python -m mag.max_distill_arms run --arm A_high   # one arm (or --arm all)
  python -m mag.max_distill_arms report             # VSTR table + RAR + A3 trigger
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mag.max_distill import SKILL_CANDIDATE_TEMPLATE, compute_rar  # noqa: E402

SCHEMA = "max_distill_arms.v1"
TRIALS = ROOT / "memory" / "runs" / "max_distill" / "trials.jsonl"

# ── PRE-REGISTERED BATCH (A4: frozen — do not edit after epoch 1 runs) ───────
# Ground truth: verdict the policy must reach. Positives require the arm to NAME the
# conflict (writers + interleaving), not just guess the label.

TASK_PROMPT = (
    "You are verifying a concurrency safety invariant for a piece of code.\n"
    "STATE:\n{state}\n\n"
    "Follow this procedure exactly:\n"
    "1. List every writer to shared mutable state (or state 'no shared mutable writer').\n"
    "2. If there are two or more unsynchronized writers, construct one concrete "
    "conflicting interleaving (name the two operations and the lost update/race).\n"
    "3. Give the verdict as the FINAL line, exactly one of:\n"
    "VERDICT: VIOLATED\nVERDICT: SAFE\n"
)

DISTILL_POLICY = "\n".join(SKILL_CANDIDATE_TEMPLATE["action_policy"])
INFO_SKETCH = (
    "A senior engineer looked at this exact state and reasoned: {hint}"
)

INSTANCES: list[dict[str, Any]] = [
    {
        "id": "i1", "rename_of": None,
        "state": "Module orders.py: global dict `inventory` updated by `add_order()` "
                 "(called from the HTTP request handler thread pool) and by "
                 "`reconcile()` (called from a nightly cron thread). No locks anywhere.",
        "verdict": "VIOLATED",
        "hint": "two unsynchronized writers to one dict; concurrent add during reconcile "
                "can lose an update; no lock in either path.",
    },
    {
        "id": "i2", "rename_of": None,
        "state": "Module cache.py: a frozen tuple `ROUTES` built once at import; three "
                 "reader threads call `lookup()` which only indexes into it.",
        "verdict": "SAFE", "hint": "immutable shared structure; readers only, no mutation.",
    },
    {
        "id": "i3", "rename_of": None,
        "state": "Module ledger.py: `append(entry)` and `audit()` both write `self.rows` "
                 "but every call site wraps them in `with self.tx_lock:` (one RLock shared "
                 "by both).",
        "verdict": "SAFE", "hint": "transactional guard present — the shared lock covers "
                                   "both writers, so no conflicting interleaving exists.",
    },
    {
        "id": "i4", "rename_of": None,
        "state": "Module worker.py: asyncio tasks each maintain their own local "
                 "`counts` dict and merge into a per-task report; nothing is shared "
                 "between tasks.",
        "verdict": "SAFE", "hint": "concurrency-looking structure but independent state — "
                                   "no shared mutable data.",
    },
    {
        "id": "i5", "rename_of": None,
        "state": "Module sensor.py: `calibrate()` (background thread) writes `self.offset` "
                 "while `read()` (request threads) writes `self.offset` too when "
                 "self-healing drift. Both mutate the same float with no synchronization.",
        "verdict": "VIOLATED",
        "hint": "two writer paths to one field, no lock; a read-modify-write race on "
                "offset loses a calibration.",
    },
    # ── rename twins (A1): i1/i3/i5 mechanically renamed — structural must survive ──
    {
        "id": "i1r", "rename_of": "i1",
        "state": "Module zqx_mod: global dict `vv_store` updated by `fn_alpha()` "
                 "(called from the dispatcher pool) and by `fn_beta()` (called from a "
                 "maintenance thread). No locks anywhere.",
        "verdict": "VIOLATED", "hint": "rename twin of i1.",
    },
    {
        "id": "i3r", "rename_of": "i3",
        "state": "Module zz_pad: `op_one(x)` and `op_two()` both write `self.buf` but "
                 "every call site wraps them in `with self.guard:` (one shared guard "
                 "object).",
        "verdict": "SAFE", "hint": "rename twin of i3.",
    },
    {
        "id": "i5r", "rename_of": "i5",
        "state": "Module qq_probe: `tune()` (background thread) writes `self.k` while "
                 "`poll()` (request threads) writes `self.k` too when correcting. Both "
                 "mutate the same float with no synchronization.",
        "verdict": "VIOLATED", "hint": "rename twin of i5.",
    },
    # ── held-out native pair + held-out twin ──
    {
        "id": "h1", "rename_of": None, "held_out": True,
        "state": "Module feed.py: `ingest(batch)` runs on a thread pool of 8 and does "
                 "`self.stats['n'] += 1` then `self.stats['last'] = batch_id`. No lock, "
                 "no atomic primitive.",
        "verdict": "VIOLATED",
        "hint": "eight-way read-modify-write on 'n' — classic lost increment.",
    },
    {
        "id": "h1r", "rename_of": "h1", "held_out": True,
        "state": "Module gg_line: `push(item)` runs on a pool of 8 and does "
                 "`self.tab['k'] += 1` then `self.tab['m'] = tag`. No lock, no atomic.",
        "verdict": "VIOLATED", "hint": "rename twin of h1.",
    },
]
BATCH_SIZE = len(INSTANCES)          # A2/A4: frozen at 10
MIN_DENOMINATOR = 2                  # A2: below this, RAR is not computed
A3_TRIGGER = 1.5                     # A3: (D-A) >= 1.5x (B-A) arms MAX+INFO in epoch 2

# Lanes: funded free keys only. z_ai2 proved 1305-saturated around the clock (24/7 k3s
# grind); z_ai3 reachable — all arms ride z_ai3 at the quiet window, serialized by the
# lane's concurrency gate. Lane is TRANSPORT, not treatment (models/modes unchanged).
ARMS: dict[str, dict[str, Any]] = {
    "A_high":           {"lane": "z_ai3", "model": "glm-4.7-flash", "mode": "plain"},
    "B_high_info":      {"lane": "z_ai3", "model": "glm-4.7-flash", "mode": "info"},
    "C_max":            {"lane": "z_ai3", "model": "glm-5.3-flash", "mode": "plain"},
    "D_high_distilled": {"lane": "z_ai3", "model": "glm-4.7-flash", "mode": "policy"},
}


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _commitment(row: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(row, sort_keys=True, ensure_ascii=False)
                          .encode("utf-8")).hexdigest()[:16]


def build_prompt(arm: str, inst: dict[str, Any]) -> str:
    mode = ARMS[arm]["mode"]
    p = TASK_PROMPT.format(state=inst["state"])
    if mode == "info":
        p += "\nPRIVILEGED NOTE (a senior engineer's read of THIS state):\n" + \
             INFO_SKETCH.format(hint=inst["hint"]) + \
             "\nStill follow the 3-step procedure and give the final VERDICT line.\n"
    elif mode == "policy":
        p += ("\nAPPLY THIS POLICY (a verified procedure, not specific to this code):\n"
              + DISTILL_POLICY +
              "\nStill give the final VERDICT line.\n")
    return p


def score(inst: dict[str, Any], text: str) -> dict[str, Any]:
    """Verified-pass gate: verdict matches ground truth AND, on VIOLATED, the answer
    names the conflict (two writers / interleaving), not a bare label."""
    m = re.findall(r"VERDICT:\s*(VIOLATED|SAFE)", (text or "").upper())
    verdict = m[-1] if m else None
    if verdict != inst["verdict"]:
        return {"pass": False, "verdict": verdict, "reason": "verdict mismatch/missing"}
    if inst["verdict"] == "VIOLATED":
        body = (text or "").lower()
        named = ("interleav" in body or "race" in body or "lost" in body
                 or "concurrent" in body or "both write" in body or "two writers" in body)
        if not named:
            return {"pass": False, "verdict": verdict,
                    "reason": "bare label — conflict not named"}
    return {"pass": True, "verdict": verdict, "reason": "ok"}


def run_arm(arm: str, *, limit: int | None = None, epoch: int = 1) -> dict[str, Any]:
    from mag.rib_cache import rib_chat
    spec = ARMS[arm]
    insts = INSTANCES[:limit] if limit else INSTANCES
    # 5.3-family rejects thinking=False (code 1210) — arm C rides 'low'; and its
    # reasoning tokens consume the budget, so C gets 1536 (512 starves it empty).
    is_max = "5.3" in spec["model"]
    thinking = "low" if is_max else False
    max_tokens = 1536 if is_max else 512
    passed = 0
    for inst in insts:
        prompt = build_prompt(arm, inst)
        r = rib_chat(prompt, lane=spec["lane"], model=spec["model"],
                     max_tokens=max_tokens, thinking=thinking)
        s = score(inst, r.get("text") or "")
        passed += int(s["pass"])
        row = {
            "schema": SCHEMA, "epoch": epoch, "arm": arm,
            "model": spec["model"], "lane": spec["lane"], "mode": spec["mode"],
            "instance": inst["id"], "rename_of": inst["rename_of"],
            "held_out": bool(inst.get("held_out")),
            "ground_truth": inst["verdict"], "score": s,
            "ok": r.get("ok"), "error": r.get("error", ""),
            "cached_tokens": r.get("cached_tokens", 0),
            "prompt_tokens": r.get("prompt_tokens", 0),
            "ts": _utc(),
        }
        row["commitment"] = _commitment({k: v for k, v in row.items()})
        TRIALS.parent.mkdir(parents=True, exist_ok=True)
        with TRIALS.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        time.sleep(1)  # be polite to the lane
    return {"ok": True, "arm": arm, "epoch": epoch, "n": len(insts),
            "vstr": passed, "batch_definition": f"frozen n={BATCH_SIZE}"}


def report(epoch: int = 1) -> dict[str, Any]:
    rows = [json.loads(l) for l in TRIALS.read_text(encoding="utf-8").splitlines()
            if l.strip()] if TRIALS.exists() else []
    rows = [r for r in rows if r.get("epoch") == epoch]
    table: dict[str, dict[str, Any]] = {}
    for arm in ARMS:
        rs = [r for r in rows if r["arm"] == arm]
        if not rs:
            continue
        native = [r for r in rs if not r["rename_of"] and not r.get("held_out")]
        twin = [r for r in rs if r["rename_of"] or r.get("held_out")]
        table[arm] = {
            "n": len(rs),
            "vstr": sum(int(r["score"]["pass"]) for r in rs),
            "native": f"{sum(int(r['score']['pass']) for r in native)}/{len(native)}",
            "twin_heldout": f"{sum(int(r['score']['pass']) for r in twin)}/{len(twin)}",
        }
    out: dict[str, Any] = {"ok": True, "schema": SCHEMA, "epoch": epoch,
                           "arms": table, "trials": len(rows)}
    if all(a in table for a in ARMS):
        gaps = {a: table[a]["vstr"] - table["A_high"]["vstr"] for a in ARMS}
        denom = gaps["C_max"]
        out["gaps_vs_A"] = gaps
        out["a3_trigger"] = {
            "rule": f"(D-A) >= {A3_TRIGGER}x (B-A)",
            "d_minus_a": gaps["D_high_distilled"],
            "b_minus_a": gaps["B_high_info"],
            "fires": (gaps["D_high_distilled"]
                      >= A3_TRIGGER * max(gaps["B_high_info"], 0)
                      and gaps["D_high_distilled"] > 0),
        }
        if denom < MIN_DENOMINATOR:
            out["rar"] = {"rar": None,
                          "verdict": f"GAP_TOO_SMALL (C-A={denom} < {MIN_DENOMINATOR})"}
        else:
            out["rar"] = compute_rar({a: float(table[a]["vstr"]) for a in ARMS})
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="max-distill-arms")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("instances")
    p_r = sub.add_parser("run")
    p_r.add_argument("--arm", default="all")
    p_r.add_argument("--limit", type=int, default=None)
    p_r.add_argument("--epoch", type=int, default=1)
    p_p = sub.add_parser("report")
    p_p.add_argument("--epoch", type=int, default=1)
    a = ap.parse_args(argv)
    if a.cmd == "instances":
        out = {"batch": [{k: i[k] for k in ("id", "rename_of", "verdict")}
                         for i in INSTANCES], "size": BATCH_SIZE}
    elif a.cmd == "run":
        arms = list(ARMS) if a.arm == "all" else [a.arm]
        out = [run_arm(arm, limit=a.limit, epoch=a.epoch) for arm in arms]
    elif a.cmd == "report":
        out = report(a.epoch)
    else:
        out = {"usage": "instances|run|report"}
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
