"""overseer — ONE-PASS process & orchestration snapshot for the operator's dashboard.

WHAT: a stateless look at the whole habitat — docker fleet, in-flight concurrency
slots, live listeners, verkle chain tip, live-feed freshness, grounding-wave tip,
inbox depth — written straight onto the operator's surface (dashboard/static/).

LAW CITATION (corrections #11, #13, law-candidate 059): this is a LOOK, not a
runtime — spawns nothing, kills nothing, schedules nothing, holds no port.
Invoked inside existing steering passes (restful-watch: looks, not timers);
one-supervisor law intact (observer, not supervisor).

CLI:
  python -m mag.overseer snap [--tag TEXT]   # snapshot once, print compact summary
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

STATIC = ROOT / "dashboard" / "static"
CHAIN = ROOT / "memory" / "biography" / "verkle_chain.jsonl"
FEED = STATIC / "live_feed.json"
INBOX = ROOT / "queue" / "handoff" / "zcode" / "INBOX"
WAVE = ROOT / "watch" / "GROUNDING_WAVE.jsonl"
OUT_STATIC = STATIC / "overseer.json"
OUT_STATE = ROOT / "state" / "overseer_latest.json"

FLEET_PORTS = ["8000", "8001", "8765"]  # control-plane, mag-mcp, dashboard


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _fleet() -> list[dict[str, str]]:
    try:
        out = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}\t{{.Status}}"],
            capture_output=True, text=True, timeout=20).stdout
        rows = []
        for ln in out.strip().splitlines():
            name, _, status = ln.partition("\t")
            if name:
                rows.append({"name": name, "status": status.strip()})
        return rows
    except Exception as exc:  # noqa: BLE001
        return [{"name": "ERROR", "status": str(exc)}]


def _in_flight() -> dict[str, Any]:
    try:
        from mag import concurrency_gate as cg
        return cg.status()
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc), "held": {}}


def _listeners() -> list[str]:
    try:
        out = subprocess.run(["netstat", "-ano"], capture_output=True,
                             text=True, timeout=20).stdout
        hits = []
        for ln in out.splitlines():
            if "LISTENING" in ln and any(f":{p} " in ln for p in FLEET_PORTS):
                hits.append(" ".join(ln.split())[:110])
        return hits[:12]
    except Exception:  # noqa: BLE001
        return []


def _chain_tip() -> dict[str, str]:
    try:
        lines = [ln for ln in CHAIN.read_text(encoding="utf-8",
                                              errors="replace").splitlines() if ln.strip()]
        if not lines:
            return {"ts": "", "leaf": "EMPTY"}
        d = json.loads(lines[-1])
        return {"ts": str(d.get("ts", "")),
                "leaf": str(d.get("leaf_hash", ""))[:12],
                "rows": str(len(lines))}
    except Exception as exc:  # noqa: BLE001
        return {"ts": "", "leaf": f"ERROR:{type(exc).__name__}"}


def _feed_age_s() -> float | None:
    try:
        return round(time.time() - FEED.stat().st_mtime, 1)
    except Exception:  # noqa: BLE001
        return None


def _wave_tip() -> dict[str, str]:
    try:
        lines = [ln for ln in WAVE.read_text(encoding="utf-8",
                                             errors="replace").splitlines() if ln.strip()]
        if not lines:
            return {"posts": "0"}
        d = json.loads(lines[-1])
        return {"posts": str(len(lines)), "last_verdict": d.get("verdict", "?"),
                "last_claim": str(d.get("claim", ""))[:90]}
    except Exception:  # noqa: BLE001
        return {"posts": "?"}


def _inbox_n() -> int:
    try:
        return len([p for p in INBOX.iterdir() if p.is_file()])
    except Exception:  # noqa: BLE001
        return -1


def snap(tag: str = "") -> dict[str, Any]:
    fleet = _fleet()
    inflight = _in_flight()
    held = inflight.get("held", {}) if isinstance(inflight, dict) else {}
    held_summary = {m: len(v) for m, v in held.items()} if isinstance(held, dict) else {}
    data: dict[str, Any] = {
        "schema": "overseer.v1",
        "ts": _now(),
        "tag": tag,
        "fleet": fleet,
        "fleet_n": len(fleet),
        "in_flight_held": held_summary,
        "in_flight_detail": held,
        "listeners": _listeners(),
        "chain_tip": _chain_tip(),
        "feed_age_s": _feed_age_s(),
        "grounding_wave": _wave_tip(),
        "inbox_n": _inbox_n(),
    }
    try:
        from mag.phone_door import ensure as _door
        data["phone_door"] = _door()
    except Exception as exc:  # noqa: BLE001 — the door check never breaks the snap
        data["phone_door"] = {"ok": False, "error": type(exc).__name__}
    OUT_STATIC.write_text(json.dumps(data, ensure_ascii=False, indent=1),
                          encoding="utf-8")
    OUT_STATE.write_text(json.dumps(data, ensure_ascii=False, indent=1),
                         encoding="utf-8")
    return data


def _summarize(d: dict[str, Any]) -> str:
    fleet_ok = sum(1 for f in d["fleet"] if "Up" in f.get("status", ""))
    held = d.get("in_flight_held") or {}
    held_s = ", ".join(f"{m}:{n}" for m, n in sorted(held.items())) or "none"
    tip = d.get("chain_tip", {})
    wave = d.get("grounding_wave", {})
    feed = d.get("feed_age_s")
    return (f"OVERSEER {d['ts']} tag={d['tag'] or '-'}\n"
            f"  fleet      : {fleet_ok}/{d['fleet_n']} containers up\n"
            f"  in-flight  : {held_s}\n"
            f"  chain tip  : {tip.get('leaf', '?')} @ {tip.get('ts', '?')} ({tip.get('rows', '?')} rows)\n"
            f"  live feed  : {'%.0fs old' % feed if feed is not None else 'MISSING'}\n"
            f"  gnd wave   : {wave.get('posts', '?')} posts, last={wave.get('last_verdict', '-')}\n"
            f"  inbox      : {d.get('inbox_n')} rows")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["snap"])
    ap.add_argument("--tag", default="")
    args = ap.parse_args()
    if args.cmd == "snap":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            pass
        print(_summarize(snap(args.tag)))


if __name__ == "__main__":
    main()
