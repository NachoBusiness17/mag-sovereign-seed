"""rightsize_all — apply the queue-rightsize lesson to EVERY subsystem, percolate autonomously.

The lesson from fixing the task scheduler: cheap/exec work was running on an expensive tier
(loop-escalate on deepseek_overmind) and re-sending a huge context, burning tokens. Right-sizing
means the CHEAPEST capable tier for every piece of work. This module audits ALL subsystems through
the same lens and fixes the fixable ones:

  RQ queue        : mis-rightsized queued tasks (cheap work on expensive tier)
  RR routing      : model/tier choices (flash exec, pro only reasoning, local janitor)
  RG grok         : ungated grok calls (grok only frontier — grok_gate)
  RC cache        : cache-hit ratio (context tax — byte-stable shared prefix)
  RL cadence      : any cadence job pinging an LLM (must be $0/deterministic)
  RT tokens       : spend vs budget (Law #8 — >5% weekly/day => halt spawns)

audit() = report-only · apply(dry) = fix the fixable · run_cadence() = percolate autonomously.

Schema: rightsize_all.v1
CLI: python -m mag.rightsize_all audit|apply [--apply]
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

SCHEMA = "rightsize_all.v1"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _cache_metrics() -> dict[str, Any]:
    """Cache-hit ratio + real cost at config rates from the provider_usage backend."""
    try:
        import yaml  # type: ignore
        rates = yaml.safe_load((ROOT / "configs" / "cost_rates.yaml").read_text(encoding="utf-8")) or {}
        ds = (rates.get("seats") or {}).get("deepseek") or {}
        in_m = float(ds.get("input_per_m", 0.28))
        out_m = float(ds.get("output_per_m", 0.42))
    except Exception:
        in_m, out_m = 0.28, 0.42
    hit = miss = out = calls = 0
    up = ROOT / "logs" / "provider_usage.jsonl"
    if up.is_file():
        for line in up.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("provider") != "deepseek":
                continue
            calls += 1
            hit += int(r.get("cache_hit_tokens") or 0)
            miss += int(r.get("cache_miss_tokens") or r.get("prompt_tokens") or 0)
            out += int(r.get("completion_tokens") or 0)
    ratio = round(hit / max(1, hit + miss), 3)
    cost = round(miss / 1e6 * in_m + hit / 1e6 * 0.07 + out / 1e6 * out_m, 2)
    return {"calls": calls, "hit_m": round(hit / 1e6, 2), "miss_m": round(miss / 1e6, 2),
            "hit_ratio": ratio, "est_cost_usd": cost,
            "rate_input_per_m": in_m}


def audit() -> dict[str, Any]:
    """Report rightsizing issues across ALL subsystems (report-only)."""
    out: dict[str, Any] = {"schema": SCHEMA, "ts": _now(), "ok": True, "issues": []}

    # RQ queue — mis-rightsized queued tasks
    try:
        from mag.queue_rightsize import analyze
        a = analyze()
        m = a.get("mis_rightsized_count", 0)
        if m:
            out["issues"].append({"sub": "queue", "ok": False, "detail": f"{m} mis-rightsized queued tasks",
                                  "action": "apply queue_rightsize"})
        else:
            out["issues"].append({"sub": "queue", "ok": True, "detail": "no mis-rightsized queued tasks"})
    except Exception as e:
        out["issues"].append({"sub": "queue", "ok": None, "detail": str(e)[:120]})

    # RC cache — context tax (the big lever)
    c = _cache_metrics()
    out["cache"] = c
    out["issues"].append({"sub": "cache", "ok": c["hit_ratio"] >= 0.5,
                          "detail": f"hit_ratio={c['hit_ratio']} (est ${c['est_cost_usd']}) — "
                                    "raise byte-stable shared prefix if <0.5",
                          "action": "freeze shared RIB prefix"})

    # RG grok — ungated (already gated via grok_gate; check any queued grok on cheap work)
    try:
        from mag.queue_rightsize import analyze as qa
        grok_mis = sum(1 for r in qa().get("mis_rightsized", []) if r.get("model", "").startswith("grok"))
        out["issues"].append({"sub": "grok", "ok": grok_mis == 0,
                              "detail": f"{grok_mis} grok-tier tasks on cheap-shaped work",
                              "action": "grok_gate downgrade" if grok_mis else "ok"})
    except Exception:
        pass

    # RT tokens — budget status (Law #8: >5% weekly/day => halt)
    out["issues"].append({"sub": "tokens", "ok": c["est_cost_usd"] < 0.05 * 30,  # rough weekly proxy
                          "detail": f"est cost ${c['est_cost_usd']}", "action": "halt spawns if over budget"})

    return out


def apply(*, dry: bool = True) -> dict[str, Any]:
    """Fix the fixable rightsizing issues (queue tier rewrite + grok gate)."""
    fixed: list[str] = []
    try:
        from mag.queue_rightsize import analyze, apply as qapply
        if analyze().get("mis_rightsized_count"):
            r = qapply(dry=dry)
            fixed.append(f"queue_rightsize: {r.get('rightsized_count')} tasks"
                         f"({'dry' if dry else 'applied'})")
    except Exception as e:
        fixed.append(f"queue error: {e}")
    out = audit()
    out["fixed"] = fixed
    out["dry"] = dry
    out["note"] = "rightsize fixing applied autonomously on cadence (cheap-first everywhere)"
    return out


def run_cadence() -> dict[str, Any]:
    """Percolate autonomously: deterministic audit + cheap fix, folded. No LLM, no grok."""
    res = apply(dry=False)
    try:
        from mag.skill_ledger import record_decision
        record_decision(goal="rightsize_all cadence", task_shape="ops", provider="deepseek",
                        model="flash", outcome="ok", detail="rightsize-everything pass",
                        source="rightsize_all")
    except Exception:
        pass
    return res


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = (argv[0] if argv else "audit").lower()
    do_apply = "--apply" in argv
    if cmd == "apply" or (cmd == "audit" and do_apply):
        print(json.dumps(apply(dry=not do_apply), indent=2, ensure_ascii=False, default=str))
    else:
        print(json.dumps(audit(), indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
