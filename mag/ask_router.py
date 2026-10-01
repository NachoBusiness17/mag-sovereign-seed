#!/usr/bin/env python3
"""ask_router - the missing controller: outcome-ledger-driven ask routing.

Thin rib in the Mag flywheel. Composes existing organs by subprocess, never imports:
  route:  decide lane ranking for a prompt from ledger + seat_corpus + memlance
  record: drop one outcome row into the ledger (pheromone) + tie verkle
$0 by construction: this is the control plane - it makes NO model calls.
Execution stays with seat_dispatch / salon / swarm_cycle; the ledger feeds back here.
"""
import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER_DIR = ROOT / "memory" / "runs" / "ask_router"
LEDGER = LEDGER_DIR / "ledger.jsonl"
CORPUS = ROOT / "memory" / "runs" / "seat_corpus" / "latest.json"
RECEIPTS = LEDGER_DIR / "receipts.jsonl"

# $-tier fallback when seat_corpus is silent (0=free, 3=frontier). Physics, not gospel.
LANE_TIERS = {
    "groq": 0, "openrouter": 0, "nvidia": 0, "cerebras": 0, "ollama": 0,
    "deepseek": 1, "zai": 2, "openai": 3, "anthropic": 3, "xai": 3,
}
# B2-521 DORMANT GATE (2026-09-26): the tier table still priced cerebras at tier 0 (free)
# after B2-36 declared it dormant, handing the dormant lane the best cost prior in
# score_lane fallbacks (100*ok_rate - 10*tier). Dormant provider rows drop out here, the
# B2-133 law (mag/dormant.py; mag/doctor.py:607: dormant is a declared state); operator GO
# flips the flag and the rows return with no code edit. Receipt:
# watch/inbox/burn_wave_20260926/B2_521_cerebras_stragglers_20260926.md
sys.path.insert(0, str(ROOT))

from mag.dormant import dormant_ids as _dormant_provider_ids  # noqa: E402

LANE_TIERS = {lane: tier for lane, tier in LANE_TIERS.items()
              if lane not in _dormant_provider_ids()}


def _spawn(cmd, timeout=60):
    try:
        p = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, timeout=timeout,
                           encoding="utf-8", errors="replace")
        return {"cmd": " ".join(cmd), "rc": p.returncode, "ok": p.returncode == 0,
                "head": (p.stdout or "")[:400], "err": (p.stderr or "")[:200]}
    except Exception as e:
        return {"cmd": " ".join(cmd), "rc": -1, "ok": False, "head": "", "err": str(e)[:200]}


def load_ledger():
    rows = []
    if LEDGER.exists():
        for line in LEDGER.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    return rows


def lane_stats(rows):
    st = {}
    for r in rows:
        lane = r.get("lane")
        if not lane:
            continue
        s = st.setdefault(lane, {"n": 0, "ok": 0, "cost": 0.0, "lat": 0.0, "last": 0})
        s["n"] += 1
        s["ok"] += 1 if r.get("ok") else 0
        s["cost"] += float(r.get("cost_usd") or 0)
        s["lat"] += float(r.get("latency_s") or 0)
        s["last"] = max(s["last"], int(r.get("ts") or 0))
    return st


def harvest_costs(corpus):
    """Best-effort cost hints from seat_corpus; shapes vary, never guess hard."""
    out = {}
    if not isinstance(corpus, dict):
        return out
    hints = corpus.get("costs") or corpus.get("lanes") or {}
    if isinstance(hints, dict):
        for k, v in hints.items():
            if isinstance(v, (int, float)):
                out[k] = v
            elif isinstance(v, dict) and isinstance(v.get("cost_usd"), (int, float)):
                out[k] = v["cost_usd"]
    return out


def score_lane(lane, s, corpus_cost):
    """Transparent math: reliability first, then cost, then freshness."""
    ok_rate = (s["ok"] / s["n"]) if (s and s["n"]) else 0.5  # unseen lane = neutral prior
    tier = corpus_cost.get(lane, LANE_TIERS.get(lane, 2))
    last = s["last"] if s else 0
    freshness = 1.0 / (1.0 + max(0, time.time() - last) / 86400.0)
    score = 100.0 * ok_rate - 10.0 * tier + 5.0 * freshness
    why = f"ok_rate={ok_rate:.2f} tier={tier} fresh={freshness:.2f}"
    if s and s["n"]:
        why += f" n={s['n']} avg_cost=${s['cost'] / s['n']:.4f} avg_lat={s['lat'] / s['n']:.1f}s"
    return round(score, 2), why


def route(prompt: str, *, dry: bool = False, k: int = 4, lanes: str = "") -> dict:
    """Rank lanes through the real router and leave a bounded receipt.

    ``dry`` is the cadence-safe mode: it performs local ledger/corpus math and
    deliberately skips memlance and Verkle subprocesses.  The route itself is
    still a successful control-plane operation when it produces a cascade;
    optional evidence is reported separately in the receipt.
    """
    slug = time.strftime("%Y%m%d-%H%M%S")
    prompt = str(prompt).strip()
    rec = {"kind": "route", "ts": int(time.time()), "slug": slug, "dry": dry,
           "prompt_head": prompt[:160]}

    # 1) grounded memory: what the swarm already knows about this goal
    if dry:
        mem = {"ok": False, "err": "dry: skipped"}
    else:
        mem = _spawn([sys.executable, "-m", "mag.ghost_memlance",
                      "select", "--goal", prompt, "--k", str(k)])
    rec["memlance"] = {"ok": bool(mem.get("ok")), "head": mem.get("head", "")[:200]}

    # 2) corpus contracts + cost hints
    corpus = {}
    try:
        corpus = json.loads(CORPUS.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        pass
    corpus_cost = harvest_costs(corpus)

    # 3) ledger outcomes -> lane rank (THE feedback loop)
    rows = load_ledger()
    st = lane_stats(rows)
    if lanes:
        lanes = [l.strip() for l in lanes.split(",") if l.strip()]
    else:
        lanes = sorted(set(list(st.keys()) + list(LANE_TIERS.keys())))
    rank = []
    for lane in lanes:
        sc, why = score_lane(lane, st.get(lane), corpus_cost)
        rank.append({"lane": lane, "score": sc, "why": why})
    rank.sort(key=lambda x: -x["score"])
    rec["ledger_rows"] = len(rows)
    rec["lane_rank"] = rank
    rec["decision"] = {
        "cascade": [r["lane"] for r in rank],
        "frontier_judgment_lanes": [r["lane"] for r in rank
                                    if corpus_cost.get(r["lane"], LANE_TIERS.get(r["lane"], 2)) >= 2][:2],
    }

    # 4) verkle tie: receipt to the chain tip (tamper-evident history)
    if dry:
        tie = {"ok": False, "rc": 0, "head": "dry: skipped"}
    else:
        tie = _spawn([sys.executable, "-m", "mag.verkle_lance", "link",
                      "--event", f"ask_router:{slug}"])
    rec["verkle"] = {"ok": bool(tie.get("ok")), "rc": tie.get("rc"), "head": tie.get("head", "")[:200]}

    rec["ok"] = bool(rank)
    LEDGER_DIR.mkdir(parents=True, exist_ok=True)
    route_path = LEDGER_DIR / f"{slug}-route.json"
    route_path.write_text(
        json.dumps(rec, indent=2, ensure_ascii=False), encoding="utf-8")
    receipt = {
        "schema": "ask_router.receipt.v1",
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "ok": bool(rank),
        "dry": dry,
        "ledger_rows": len(rows),
        "cascade_len": len(rank),
        "route_path": str(route_path.relative_to(ROOT)).replace("\\", "/"),
        "optional_memlance_ok": bool(mem.get("ok")),
        "optional_verkle_ok": bool(tie.get("ok")),
        "caller": "mag.ask_router.route",
    }
    with RECEIPTS.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(receipt, ensure_ascii=False, sort_keys=True) + "\n")
    rec["receipt_path"] = str(RECEIPTS.relative_to(ROOT)).replace("\\", "/")
    return rec


def cmd_route(args):
    rec = route(" ".join(args.prompt), dry=args.dry, k=args.k, lanes=args.lanes)
    print(json.dumps(rec, indent=2, ensure_ascii=False))
    return 0


def cmd_record(args):
    slug = time.strftime("%Y%m%d-%H%M%S")
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except Exception as e:
        print(json.dumps({"ok": False, "err": f"bad json: {e}"}))
        return 1
    row = {"kind": "outcome", "ts": int(time.time()), "slug": slug,
           "lane": payload.get("lane"), "ok": bool(payload.get("ok")),
           "cost_usd": float(payload.get("cost_usd") or 0),
           "latency_s": float(payload.get("latency_s") or 0),
           "task_head": (payload.get("task") or "")[:160]}
    LEDGER_DIR.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    tie = _spawn([sys.executable, "-m", "mag.verkle_lance", "link",
                  "--event", f"ask_router:record:{slug}:{row['lane']}"])
    print(json.dumps({"ok": True, "row": row, "verkle": {"ok": bool(tie.get("ok"))}},
                     indent=2, ensure_ascii=False))
    return 0


def cmd_record(args):
    """Read one outcome from stdin and delegate to the single writer."""
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except Exception as exc:
        print(json.dumps({"ok": False, "err": f"bad json: {exc}"}))
        return 1
    result = record_outcome(
        lane=payload.get("lane") or "unknown",
        ok=bool(payload.get("ok")),
        cost_usd=float(payload.get("cost_usd") or 0),
        latency_s=float(payload.get("latency_s") or 0),
        task=payload.get("task") or "",
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("ok") else 1


def record_outcome(lane: str, ok: bool, cost_usd: float = 0.0,
                   latency_s: float = 0.0, task: str = "") -> dict:
    """Append one outcome row to the routing ledger + verkle tie.

    Single-writer helper for lane callers (api_gateway /room/spawn, future
    cage passthroughs). Same row schema as cmd_record; never raises —
    outcome memory must never break the lane it is measuring.
    """
    slug = time.strftime("%Y%m%d-%H%M%S")
    row = {"kind": "outcome", "ts": int(time.time()), "slug": slug,
           "lane": lane, "ok": bool(ok),
           "cost_usd": float(cost_usd or 0),
           "latency_s": float(latency_s or 0),
           "task_head": (task or "")[:160]}
    try:
        LEDGER_DIR.mkdir(parents=True, exist_ok=True)
        with LEDGER.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        tie = _spawn([sys.executable, "-m", "mag.verkle_lance", "link",
                      "--event", f"ask_router:record:{slug}:{lane}"])
        return {"ok": True, "row": row, "verkle": {"ok": bool(tie.get("ok"))}}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "err": str(e)[:200], "row": row}


def main():
    ap = argparse.ArgumentParser(prog="mag.ask_router")
    ap.add_argument("prompt", nargs="*", help="the ask to size/route")
    ap.add_argument("--dry", action="store_true",
                    help="no subprocess calls at all: pure local ledger math ($0 pipe test)")
    ap.add_argument("--k", type=int, default=4, help="memlance hits to consult")
    ap.add_argument("--lanes", default="", help="CSV lane override")
    ap.add_argument("--record", action="store_true",
                    help="read outcome JSON on stdin -> ledger + verkle tie")
    args = ap.parse_args()
    if args.record:
        sys.exit(cmd_record(args))
    if not " ".join(args.prompt).strip():
        print(json.dumps({"ok": False, "err": "need a prompt"}))
        sys.exit(1)
    sys.exit(cmd_route(args))


if __name__ == "__main__":
    main()
