"""ox_swarm — deploy the resident cold-vertex pattern across the frontier FLEET (2026-08-23).

The operator's lever (2026-08-23): we have a trained swarm of frontier seats, not one seat.
The resident scout (mag/ox_resident.py) is the PER-SEAT pattern (frozen self + cold-vertex +
reasoning-as-product + distill + fold). This module fans that pattern across MULTIPLE frontier
providers at once — each member drills a DISTINCT set of cold vertices (deduped by core, so no
two seats burn the same mechanism), all through the OpenRouter gateway (ox_seat.chat model
override reaches OpenAI / Grok / DeepSeek / Cursor on one key).

Fleet (grounded from .env):
  - ox        : the FREE stealth seat (OPENROUTER_MODEL)       tier=free
  - deepseek  : PAID, $50 balance (AOS_AGENT_MODEL / deepseek)  tier=paid  <- reliable workhorse
  - (configurable: openai, grok, cursor — add model strings here once confirmed)

Each member runs its slice at its own concurrency; every result banks to the same store, and
verify + distill + fold are shared (the growth loop). Paid members report cost honestly.

Schema: ox_swarm.v1
Run:  python -m mag.ox_swarm preview   # show the fleet + slice assignment, fire nothing
      python -m mag.ox_swarm           # one swarm round across the fleet
      python -m mag.ox_swarm summary   # banked + cost by member
"""
from __future__ import annotations

import json
import os
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

from mag.ox_resident import (FROZEN_PREFIX, ROUND2_ASKS, COLD_ASKS, cold_asks,  # noqa: E402
                             target_cells, _substance)
from mag.ox_seat import chat as _or_chat  # noqa: E402

SCHEMA = "ox_swarm.v1"
OUT_DIR = ROOT / "handoff"
LEDGER = ROOT / "memory" / "runs" / "ox_swarm_ledger.jsonl"
EXHAUSTED_FILE = ROOT / "memory" / "runs" / "ox_swarm_exhausted.json"

# Concurrency PER MEMBER. Each member runs this many asks in parallel. Probed: ox throttles past
# 8; DeepSeek (paid, reliable) can take more. Per-member override in FLEET.
DEFAULT_CONCURRENCY = int(os.environ.get("OX_SWARM_CONCURRENCY", "8"))


def _env_or(key: str, fallback: str) -> str:
    v = os.environ.get(key, "")
    if v:
        return v
    try:
        env_path = ROOT / ".env"
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
                if line.startswith(key + "="):
                    return line.split("=", 1)[1].strip().strip('"')
    except Exception:  # noqa: BLE001
        pass
    return fallback


def fleet() -> list[dict]:
    """The frontier fleet. ox = free; deepseek = the $50 paid workhorse (model we already use for
    AOS); openai = ChatGPT (OPENAI_API_KEY set, was idle -> wired as a second independent seat for
    the n* verification pass). Add more once their OpenRouter model strings are confirmed."""
    return [
        {"name": "ox", "model": _env_or("OPENROUTER_MODEL", "stealth/ox-alpha"),
         "tier": "free", "concurrency": 8},
        {"name": "deepseek", "model": _env_or("AOS_AGENT_MODEL", "deepseek/deepseek-v4-flash"),
         "tier": "paid", "concurrency": 16},
        {"name": "openai", "model": _env_or("OPENAI_MODEL", "openai/gpt-5"),
         "tier": "paid", "concurrency": 8},
        {"name": "grok", "model": _env_or("XAI_MODEL", "x-ai/grok-4"),
         "tier": "paid", "concurrency": 8},
    ]


def _exhausted() -> set[str]:
    """Members currently rate-limited out (HTTP 429, e.g. free-models-per-day-stealth). We skip
    them so the swarm doesn't waste fires on an exhausted seat until it recovers."""
    try:
        if EXHAUSTED_FILE.exists():
            return set(json.loads(EXHAUSTED_FILE.read_text(encoding="utf-8")))
    except Exception:  # noqa: BLE001
        pass
    return set()


def _mark_exhausted(member: str) -> None:
    try:
        s = _exhausted()
        s.add(member)
        EXHAUSTED_FILE.parent.mkdir(parents=True, exist_ok=True)
        EXHAUSTED_FILE.write_text(json.dumps(sorted(s)), encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass


def _is_rate_limited(res: dict[str, Any]) -> bool:
    err = str(res.get("error", "")).lower()
    return "429" in err or "rate limit" in err


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _assign(pending: list[tuple[str, str, str, str]]) -> dict[str, list]:
    """Assign pending asks to fleet members, deduped by CORE: each core's asks go to ONE member, so
    no two seats ever drill the same mechanism (no duplicated work / no consensus-illusion). Cores
    are distributed round-robin across members."""
    members = fleet()
    core_to_member: dict[str, str] = {}
    out = {m["name"]: [] for m in members}
    idx = 0
    for name, prompt, core, kind in pending:
        if core not in core_to_member:
            core_to_member[core] = members[idx % len(members)]["name"]
            idx += 1
        out[core_to_member[core]].append((name, prompt, core, kind))
    return out


def _fire(model: str, prompt: str, max_tokens: int, timeout: int) -> dict[str, Any]:
    try:
        return _or_chat(FROZEN_PREFIX, prompt, max_tokens=max_tokens, timeout=timeout,
                        tier="T2", model=model)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"}


def _done_names() -> set[str]:
    done: set[str] = set()
    for p in OUT_DIR.glob("OX_SWARM_*.json"):
        try:
            d = json.loads(p.read_text(encoding="utf-8", errors="replace"))
            if d.get("ok"):
                done.add(p.stem.removeprefix("OX_SWARM_"))
        except Exception:  # noqa: BLE001
            pass
    return done


def _bank(name: str, res: dict[str, Any], core: str, kind: str, member: str, tier: str) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / f"OX_SWARM_{name}.json").write_text(
        json.dumps({"schema": SCHEMA, "name": name, "core": core, "kind": kind,
                    "member": member, "tier": tier, "ts": _now(),
                    "ok": bool(res.get("ok")), "cost": res.get("cost", 0.0),
                    "content": res.get("content") or "", "reasoning": res.get("reasoning") or "",
                    "error": res.get("error", "")}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"name": name, "core": core, "kind": kind, "member": member,
                            "tier": tier, "ts": _now(), "ok": bool(res.get("ok")),
                            "cost": res.get("cost", 0.0),
                            "substance_chars": len(_substance(res.get("content") or "",
                                                              res.get("reasoning") or "") or "")},
                           ensure_ascii=False) + "\n")


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
    members = fleet()
    assign = _assign(pending_asks())
    return {"ok": True, "schema": SCHEMA, "fleet": [{"name": m["name"], "model": m["model"],
                                                     "tier": m["tier"],
                                                     "concurrency": m["concurrency"]}
                                                    for m in members],
            "assignment": {k: [i[0] for i in v] for k, v in assign.items()},
            "total_pending": sum(len(v) for v in assign.values())}


def run(*, rnd: int = 2, max_tokens: int = 10000, timeout: int = 540) -> dict[str, Any]:
    members = fleet()
    exhausted = _exhausted()
    assign = _assign(pending_asks(rnd=rnd))
    per_member: dict[str, dict] = {}
    total_cost = 0.0
    for m in members:
        name = m["name"]
        if name in exhausted:
            per_member[name] = {"fired": 0, "new_ok": 0, "cost": 0.0, "tier": m["tier"],
                                "skipped": "rate-limited"}
            continue
        batch = assign.get(name, [])
        if not batch:
            per_member[name] = {"fired": 0, "new_ok": 0, "cost": 0.0, "tier": m["tier"]}
            continue
        fired = 0
        new_ok = 0
        cost = 0.0
        rl_hits = 0
        with ThreadPoolExecutor(max_workers=m["concurrency"]) as ex:
            futs = {ex.submit(_fire, m["model"], p, max_tokens, timeout): (n, c, k)
                    for n, p, c, k in batch}
            for fut in as_completed(futs):
                n, c, k = futs[fut]
                try:
                    res = fut.result()
                except Exception as e:  # noqa: BLE001
                    res = {"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"}
                _bank(n, res, c, k, name, m["tier"])
                fired += 1
                cost += float(res.get("cost", 0.0))
                if _is_rate_limited(res):
                    rl_hits += 1
                if res.get("ok") and _substance(res.get("content") or "", res.get("reasoning") or ""):
                    new_ok += 1
        if rl_hits >= max(1, len(batch) // 2):  # majority rate-limited -> mark exhausted
            _mark_exhausted(name)
        per_member[name] = {"fired": fired, "new_ok": new_ok, "cost": round(cost, 6),
                            "tier": m["tier"], "rate_limited": rl_hits}
        total_cost += cost
    return {"ok": True, "schema": SCHEMA, "per_member": per_member,
            "total_cost": round(total_cost, 6), "exhausted": sorted(_exhausted()),
            "done_total": len(_done_names())}


def summary() -> dict[str, Any]:
    rows = [json.loads(l) for l in LEDGER.read_text(encoding="utf-8", errors="replace").splitlines()
            if l.strip()] if LEDGER.exists() else []
    by_member: dict[str, dict] = {}
    total_cost = 0.0
    for r in rows:
        mm = r.get("member", "?")
        by_member.setdefault(mm, {"fired": 0, "new_ok": 0, "cost": 0.0, "tier": r.get("tier")})
        by_member[mm]["fired"] += 1
        if r.get("ok"):
            by_member[mm]["new_ok"] += 1
        by_member[mm]["cost"] += float(r.get("cost", 0.0))
        total_cost += float(r.get("cost", 0.0))
    return {"ok": True, "schema": SCHEMA, "by_member": by_member,
            "total_cost": round(total_cost, 6), "banked_files": len(_done_names())}


def watch(*, every_s: int = 45, rnd: int = 2) -> None:
    """LIVE swarm iteration (2026-08-23, operator: 'make this thing go'): an always-on loop that
    fires rounds across the whole fleet, folds every landed result LIVE (distill + register
    pro-moves via ox_resident), and keeps going until stopped. Leans on whatever member delivers
    (probed: DeepSeek is the reliable paid workhorse; ox is flaky/free). Ctrl+C to stop."""
    import time
    from mag.ox_resident import distill as _fold
    print(f"[ox_swarm] swarm up — fleet={[m['name'] for m in fleet()]} "
          f"every {every_s}s round {rnd}. Ctrl+C to stop.", flush=True)
    while True:
        try:
            r = run(rnd=rnd)
            if r.get("per_member"):
                _fold()  # fold the landed swarm reasoning into the distill + pro-moves LIVE
                print(f"[ox_swarm] cost=${r.get('total_cost'):.4f} "
                      f"done={r.get('done_total')} "
                      + " ".join(f"{k}:{v['new_ok']}ok/${v['cost']:.4f}"
                                 for k, v in r.get("per_member", {}).items()),
                      flush=True)
            time.sleep(every_s)
        except KeyboardInterrupt:
            print("\n[ox_swarm] swarm stopped.", flush=True)
            return
        except Exception as e:  # noqa: BLE001
            print(f"[ox_swarm] ERR {type(e).__name__}: {str(e)[:150]}", flush=True)
            time.sleep(every_s)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", nargs="?", default="run", choices=["run", "preview", "summary", "watch"])
    ap.add_argument("--round", type=int, default=2)
    ap.add_argument("--every", type=int, default=45)
    a = ap.parse_args()
    if a.cmd == "preview":
        print(json.dumps(preview(), indent=2, ensure_ascii=False))
    elif a.cmd == "summary":
        print(json.dumps(summary(), indent=2, ensure_ascii=False))
    elif a.cmd == "watch":
        watch(every_s=a.every, rnd=a.round)
    else:
        print(json.dumps(run(rnd=a.round), indent=2, ensure_ascii=False, default=str))
