"""real_swarm — route the cold-vertex growth loop through the REAL provider layer (2026-08-23).

NO SACRED COWS / USE THE REAL WAY (operator): we already had a mature multi-provider layer —
models/providers.py + configs/providers.yaml (23 providers, quota-tracked, key failover) — and I
had invented a hand-rolled ox_swarm instead of using it. This module uses the REAL machinery:
  - models.providers.chat_provider()  routes + quota-tracks + does key failover
  - the real fleet: deepseek (disable_thinking = 10-15x cheaper, already in config), openai
    (ChatGPT, was idle), xai (2 grok seats with failover — XAI_API_KEY + XAI_API_KEY_2), openrouter.
  - the growth-loop PATTERN is kept (frozen-prefix cold-vertex, reasoning-as-product, distill/fold)
    but the ROUTING is the real layer, not a parallel wheel.

Schema: real_swarm.v1
Run:  python -m mag.real_swarm preview    # show the real fleet + assignment, fire nothing
      python -m mag.real_swarm            # one round across the real fleet
      python -m mag.real_swarm summary
"""
from __future__ import annotations

import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:  # noqa: BLE001
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

from mag.ox_resident import FROZEN_PREFIX, ROUND2_ASKS, COLD_ASKS, cold_asks, target_cells, _substance  # noqa: E402
from models.providers import chat_provider, provider_keys, get_provider  # noqa: E402

SCHEMA = "real_swarm.v1"
OUT_DIR = ROOT / "handoff"
LEDGER = ROOT / "memory" / "runs" / "real_swarm_ledger.jsonl"
CONCURRENCY = 8

# The REAL fleet — provider ids from configs/providers.yaml.
# GROUNDED 2026-08-23: xai (grok) and openai (ChatGPT) API keys are UNFUNDED (HTTP 403/429
# 'no credits') — the paid API path fails for them. Their reliable free route is the DESKTOP
# Electron apps over CDP (mag/electron_seat, free, no billing). So the funded/mixed API fleet is:
REAL_FLEET: list[dict] = [
    {"provider": "deepseek", "name": "deepseek", "tier": "paid"},    # funded ($50)
    {"provider": "openrouter", "name": "openrouter", "tier": "mixed"},  # free models, throttled
    # xai / openai: UNFUNDED via API -> use electron_seat desktop apps instead (operator launches
    # with --remote-debugging-port=9333/9334). Add here only once the accounts have credits.
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _monotonic() -> float:
    import time
    return time.monotonic()


def live_fleet() -> list[dict]:
    """Only members whose provider has at least one usable key."""
    out = []
    for m in REAL_FLEET:
        keys = provider_keys(get_provider(m["provider"]) or {})
        if keys:
            out.append({**m, "keys": len(keys),
                        "model": (get_provider(m["provider"]) or {}).get("default_model")})
    return out


def _assign(pending: list[tuple[str, str, str, str]]) -> dict[str, list]:
    """Assign asks to fleet members, deduped by CORE (each core's asks go to ONE member — no two
    seats drill the same mechanism). Cores round-robin across the live fleet."""
    members = live_fleet()
    core_to_member: dict[str, str] = {}
    out = {m["provider"]: [] for m in members}
    idx = 0
    for name, prompt, core, kind in pending:
        if core not in core_to_member:
            core_to_member[core] = members[idx % len(members)]["provider"]
            idx += 1
        out[core_to_member[core]].append((name, prompt, core, kind))
    return out


def _done_names() -> set[str]:
    done: set[str] = set()
    for p in OUT_DIR.glob("OX_RS_*.json"):
        try:
            d = json.loads(p.read_text(encoding="utf-8", errors="replace"))
            if d.get("ok"):
                done.add(p.stem.removeprefix("OX_RS_"))
        except Exception:  # noqa: BLE001
            pass
    return done


def _bank(name: str, res: dict[str, Any], core: str, kind: str, provider: str, tier: str) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / f"OX_RS_{name}.json").write_text(
        json.dumps({"schema": SCHEMA, "name": name, "core": core, "kind": kind,
                    "provider": provider, "tier": tier, "ts": _now(),
                    "ok": bool(res.get("ok")), "cost": res.get("cost", 0.0),
                    "content": res.get("content") or "", "reasoning": res.get("reasoning") or "",
                    "error": res.get("error", "")}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"name": name, "core": core, "kind": kind, "provider": provider,
                            "tier": tier, "ts": _now(), "ok": bool(res.get("ok")),
                            "cost": res.get("cost", 0.0),
                            "substance_chars": len(_substance(res.get("content") or "",
                                                              res.get("reasoning") or "") or "")},
                           ensure_ascii=False) + "\n")


def _fire(provider: str, prompt: str) -> dict[str, Any]:
    """Route through the REAL provider layer (quota-tracked, key failover, disable_thinking
    handled by config). Cold-vertex bulk: thinking off = cheap direct content.

    OpenRouter free-lane rotation (steal from openrouter limits + litellm fallback chain): each
    :free model has its own RPD cap, so we rotate across the ACTIVE free lanes (skip 429-exhausted
    ones) and mark a lane exhausted when it 429s — the swarm keeps finding working free seats."""
    try:
        model = None
        if provider == "openrouter":
            from mag.seat_hunter import next_lane
            model = next_lane().get("lane")
        res = chat_provider(provider, FROZEN_PREFIX, prompt, max_tokens=8000,
                            tier="T2", thinking=False, model=model)
        # a 429 on a free lane = that lane's daily cap -> mark it exhausted so rotation skips it
        if provider == "openrouter" and model and ("429" in str(res.get("error", ""))):
            from mag.seat_hunter import mark_lane_exhausted
            mark_lane_exhausted(model)
        return res
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"}


def pending_asks(rnd: int = 2) -> list[tuple[str, str, str, str]]:
    asks = ROUND2_ASKS if rnd == 2 else COLD_ASKS
    done = _done_names()
    out: list[tuple[str, str, str, str]] = []
    for t in target_cells():
        core = t["core"]
        for name, prompt in cold_asks(core, asks):
            if name in done:
                continue
            out.append((name, prompt, core, name.rsplit("-", 1)[-1]))
    return out


def preview() -> dict[str, Any]:
    fleet = live_fleet()
    assign = _assign(pending_asks())
    return {"ok": True, "schema": SCHEMA,
            "fleet": [{"provider": m["provider"], "name": m["name"], "model": m.get("model"),
                       "keys": m["keys"], "tier": m["tier"]} for m in fleet],
            "assignment": {k: [i[0] for i in v] for k, v in assign.items()},
            "total_pending": sum(len(v) for v in assign.values())}


def run(*, rnd: int = 2, provider: str | None = None) -> dict[str, Any]:
    fleet = [m for m in live_fleet() if provider is None or m["provider"] == provider]
    assign = _assign(pending_asks(rnd=rnd))
    per: dict[str, dict] = {}
    total_cost = 0.0
    # CADENCE-LEARN (2026-08-23, operator "don't hog 100% cpu... keep it at 90%... iterate and
    # learn cadence and parallel launches"): throttle per-provider concurrency to the CPU ceiling
    # and adapt the learned worker cap from real round timing. Self-steal: cadence_learn.
    try:
        from mag import cadence_learn
        workers = cadence_learn.throttled_workers()
    except Exception:  # noqa: BLE001
        workers = CONCURRENCY
    start_t = _monotonic()
    for m in fleet:
        pid = m["provider"]
        batch = assign.get(pid, [])
        if not batch:
            per[pid] = {"fired": 0, "new_ok": 0, "cost": 0.0, "name": m["name"]}
            continue
        fired, new_ok, cost = 0, 0, 0.0
        with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
            futs = {ex.submit(_fire, pid, p): (n, c, k) for n, p, c, k in batch}
            for fut in as_completed(futs):
                n, c, k = futs[fut]
                try:
                    res = fut.result()
                except Exception as e:  # noqa: BLE001
                    res = {"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"}
                _bank(n, res, c, k, pid, m["tier"])
                fired += 1
                cost += float(res.get("cost", 0.0))
                if res.get("ok") and _substance(res.get("content") or "", res.get("reasoning") or ""):
                    new_ok += 1
        per[pid] = {"fired": fired, "new_ok": new_ok, "cost": round(cost, 6), "name": m["name"]}
        total_cost += cost
    # fold the cadence-learning round (real timing + success + CPU) so the loop learns
    try:
        from mag import cadence_learn
        cadence_learn.learn({"workers": workers, "ok": any(v.get("new_ok", 0) for v in per.values()),
                             "cpu_pct": cadence_learn._cpu_pct(),
                             "round_s": round(_monotonic() - start_t, 2)})
    except Exception:  # noqa: BLE001
        pass
    return {"ok": True, "schema": SCHEMA, "per_provider": per, "workers": workers,
            "total_cost": round(total_cost, 6), "done_total": len(_done_names())}


def summary() -> dict[str, Any]:
    rows = [json.loads(l) for l in LEDGER.read_text(encoding="utf-8", errors="replace").splitlines()
            if l.strip()] if LEDGER.exists() else []
    by_prov: dict[str, dict] = {}
    total = 0.0
    for r in rows:
        p = r.get("provider", "?")
        by_prov.setdefault(p, {"fired": 0, "new_ok": 0, "cost": 0.0})
        by_prov[p]["fired"] += 1
        if r.get("ok"):
            by_prov[p]["new_ok"] += 1
        by_prov[p]["cost"] += float(r.get("cost", 0.0))
        total += float(r.get("cost", 0.0))
    return {"ok": True, "schema": SCHEMA, "by_provider": by_prov,
            "total_cost": round(total, 6), "banked_files": len(_done_names())}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", nargs="?", default="run", choices=["run", "preview", "summary"])
    ap.add_argument("--round", type=int, default=2)
    ap.add_argument("--provider", type=str, default=None,
                    help="scope to one provider (e.g. 'openrouter' to test the free lanes)")
    a = ap.parse_args()
    if a.cmd == "preview":
        print(json.dumps(preview(), indent=2, ensure_ascii=False))
    elif a.cmd == "summary":
        print(json.dumps(summary(), indent=2, ensure_ascii=False))
    else:
        print(json.dumps(run(rnd=a.round, provider=a.provider),
                         indent=2, ensure_ascii=False, default=str))
