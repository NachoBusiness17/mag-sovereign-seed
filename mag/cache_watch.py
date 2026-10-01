"""cache_watch — the $0 standing cache monitor (mine-the-cache, guard the 97%).

Operator ask (2026-08-25): "the important thing is the cache in the other window
and trying to play nice and mine it at our 97%." Translation: sustain the prefix-
cache mining (~97% lifetime hit on deepseek, 99%+ on glm flash) WITHOUT spending
model quota to watch it. This module is that watcher — pure, deterministic, ~2
cheap glm-flash calls per run (free tier), no GLM-5.3, no LLM judgment:

  probe   -> mag.glm_flash twice, byte-identical (the A/B mining check)
  audit   -> mag.prefix_prover.cmd_audit (drift vs novelty attribution)
  ledger  -> mag.cache_map.recent_hit_ratio (economics, split rows)

ALARM RULES (appended to memory/runs/cache_watch.jsonl with "alarm" set):
  probe ratio < 0.90          -> mining broken on the flash lane (provider or
                                 frozen-self edited — check FROZEN_SELF bytes)
  audit attribution DRIFT     -> a feeding prefix changed; fix builder, not budget
  ledger ratio < 0.90         -> the deepseek lane is bleeding (was 97%+ lifetime)
Cadence: rides the governor's janitor slot (MAG_CACHE_WATCH_EVERY ticks, default
same as janitor). Pure: never mutates anything but its own report.

CLI:  python -m mag.cache_watch            # run once, print report
      python -m mag.cache_watch --history  # last 5 reports
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

REPORT = ROOT / "memory" / "runs" / "cache_watch.jsonl"
SCHEMA = "cache_watch.v1"

PROBE_FLOOR = 0.90
LEDGER_FLOOR = 0.90
DEADMAN_FLOOR_MIN = 45


def _now_dt() -> datetime:
    return datetime.now(timezone.utc)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def run() -> dict[str, Any]:
    row: dict[str, Any] = {"schema": SCHEMA, "ts": _now(), "alarms": []}

    # 1. probe: two byte-identical flash calls; call2 ratio = mining truth
    try:
        from mag.glm_flash import cached_chat

        task = "Reply with exactly: CACHE-PROBE-ACK"
        r1 = cached_chat(task)
        r2 = cached_chat(task)
        ratio = (r2["cached_tokens"] / r2["prompt_tokens"]) if r2.get("prompt_tokens") else 0.0
        row["probe"] = {"ok": bool(r1.get("ok") and r2.get("ok")),
                        "ratio": round(ratio, 4),
                        "cached": r2.get("cached_tokens"), "prompt": r2.get("prompt_tokens")}
        if row["probe"]["ok"] and ratio < PROBE_FLOOR:
            row["alarms"].append(f"mining broken: probe ratio {ratio:.2%} < {PROBE_FLOOR:.0%}")
        if not row["probe"]["ok"]:
            err = f"{r2.get('error') or r1.get('error') or ''}"
            if "429" in err or "1302" in err or "1305" in err:
                # concurrency/rate contention (glm_flash gate says 1302/1305 are
                # concurrency codes) — the lane is BUSY, not broken. Not an alarm.
                row["probe"]["busy"] = True
                row["probe"]["note"] = "lane busy (429/1302/1305) — probe skipped, not broken"
            else:
                row["alarms"].append(f"probe failed: {err}")
    except Exception as e:  # noqa: BLE001 — monitor must never crash the loop
        row["probe"] = {"ok": False, "error": str(e)[:160]}

    # 2. audit: drift vs novelty (uses invariant pins + usage ledger)
    try:
        from mag.prefix_prover import cmd_audit

        a = cmd_audit(hours=24)
        drift = [l for l in a.get("lanes", []) if str(l.get("attribution", "")).startswith("DRIFT")]
        row["audit"] = {"missing_lanes": a.get("verdict", {}).get("missing_lanes", 0),
                        "drift_lanes": [l["lane"] for l in drift]}
        if drift:
            row["alarms"].append(f"prefix drift on lanes: {', '.join(l['lane'] for l in drift)}")
    except Exception as e:  # noqa: BLE001
        row["audit"] = {"error": str(e)[:160]}

    # 3. ledger: real economics from split rows
    try:
        from mag.cache_map import recent_hit_ratio

        hr = recent_hit_ratio()
        row["ledger"] = {"hit_ratio": hr}
        if hr and hr < LEDGER_FLOOR:
            row["alarms"].append(f"ledger hit ratio {hr:.2%} below {LEDGER_FLOOR:.0%} floor")
    except Exception as e:  # noqa: BLE001
        row["ledger"] = {"error": str(e)[:160]}

    # 4. dead-man: usage ledger must be fresh, or the meter is blind
    #    (Aug 26 19:49 -> Aug 27 06:5x blackout went unnoticed ~12h — never again)
    try:
        ledger = ROOT / "logs" / "provider_usage.jsonl"
        age_min = (_now_dt() - datetime.fromtimestamp(ledger.stat().st_mtime, timezone.utc)).total_seconds() / 60
        row["ledger_freshness"] = {"age_minutes": round(age_min, 1)}
        if age_min > DEADMAN_FLOOR_MIN:
            row["alarms"].append(f"meter dead-man: provider_usage.jsonl silent {age_min:.0f}min > {DEADMAN_FLOOR_MIN}min")
    except Exception as e:  # noqa: BLE001
        row["ledger_freshness"] = {"error": str(e)[:160]}

    row["healthy"] = not row["alarms"]
    with REPORT.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def history(n: int = 5) -> list[dict]:
    if not REPORT.is_file():
        return []
    lines = REPORT.read_text(encoding="utf-8", errors="replace").splitlines()
    out = []
    for line in lines[-n:]:
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    ap = argparse.ArgumentParser(prog="cache-watch", description="$0 cache-mining monitor")
    ap.add_argument("--history", action="store_true", help="print last reports instead of running")
    args = ap.parse_args(argv)
    if args.history:
        print(json.dumps(history(), indent=2, ensure_ascii=False))
        return 0
    row = run()
    print(json.dumps(row, indent=2, ensure_ascii=False))
    return 0 if row["healthy"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
