"""Looking-eye snapshot — model trajectory + RIB bus + traj tape.

Primer face is /chan. This is the hood the overview board paints.
Deterministic, $0, existing ledgers only. No second Mag.

CLI: python -m mag.hood
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
USAGE = ROOT / "logs" / "provider_usage.jsonl"
TRAJ = ROOT / "watch" / "openclaw_traj.jsonl"
RIB_DIR = ROOT / "memory" / "rib_bus"
SCHEMA = "hood.v1"


def _now_day() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _tail_jsonl(path: Path, n: int = 80) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    out: list[dict[str, Any]] = []
    for line in lines[-n:]:
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(rec, dict):
            out.append(rec)
    return out


def _models(day: str) -> dict[str, Any]:
    rows = _tail_jsonl(USAGE, 400)
    today = [r for r in rows if str(r.get("ts") or "").startswith(day)]
    use = today or rows[-80:]
    lanes: dict[str, dict[str, Any]] = {}
    path: list[dict[str, Any]] = []
    for r in use:
        lane = f"{r.get('provider') or '?'}:{r.get('model') or '?'}"
        L = lanes.setdefault(lane, {"calls": 0, "ok": 0, "fail": 0,
                                    "cache_hit": 0, "cache_miss": 0})
        L["calls"] += 1
        if r.get("ok"):
            L["ok"] += 1
        else:
            L["fail"] += 1
        L["cache_hit"] += int(r.get("cache_hit_tokens") or 0)
        L["cache_miss"] += int(r.get("cache_miss_tokens") or 0)
        path.append({
            "ts": r.get("ts"),
            "lane": lane,
            "ok": bool(r.get("ok")),
            "hit": int(r.get("cache_hit_tokens") or 0),
            "miss": int(r.get("cache_miss_tokens") or 0),
            "out": int(r.get("completion_tokens") or 0),
            "ms": r.get("latency_ms"),
        })
    ranked = sorted(lanes.items(), key=lambda kv: kv[1]["calls"], reverse=True)
    return {
        "day": day,
        "n": len(use),
        "lanes": [{"lane": k, **v} for k, v in ranked[:12]],
        "path": path[-24:],
    }


def _ribs() -> dict[str, Any]:
    domains: list[dict[str, Any]] = []
    if RIB_DIR.is_dir():
        for f in sorted(RIB_DIR.glob("*.json")):
            try:
                store = json.loads(f.read_text(encoding="utf-8", errors="replace"))
            except (OSError, json.JSONDecodeError):
                continue
            ribs = store.get("ribs") or {}
            if not isinstance(ribs, dict):
                continue
            last = ""
            snippet = ""
            for rec in ribs.values():
                if not isinstance(rec, dict):
                    continue
                ts = str(rec.get("ts") or "")
                if ts >= last:
                    last = ts
                    snippet = str(rec.get("invariant") or "")[:160]
            domains.append({
                "domain": store.get("domain") or f.stem,
                "n": len(ribs),
                "updated": store.get("updated") or last,
                "snippet": snippet,
            })
    domains.sort(key=lambda d: str(d.get("updated") or ""), reverse=True)
    return {"n_domains": len(domains), "domains": domains[:18]}


def _traj() -> dict[str, Any]:
    rows = _tail_jsonl(TRAJ, 24)
    return {"n": len(rows), "tail": rows[-12:]}


def _chan() -> dict[str, Any]:
    try:
        from mag.chan import catalog
        cat = catalog(all_threads=True)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)[:160]}
    threads = cat.get("threads") or []
    return {
        "ok": True,
        "n_threads": cat.get("count"),
        "threads": [
            {"slug": t.get("slug"), "replies": t.get("replies"),
             "bumped": t.get("bumped"), "primer": t.get("primer")}
            for t in threads[:10]
        ],
    }


def snapshot() -> dict[str, Any]:
    day = _now_day()
    return {
        "ok": True,
        "schema": SCHEMA,
        "day": day,
        "models": _models(day),
        "ribs": _ribs(),
        "traj": _traj(),
        "chan": _chan(),
    }


def main() -> int:
    print(json.dumps(snapshot(), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
