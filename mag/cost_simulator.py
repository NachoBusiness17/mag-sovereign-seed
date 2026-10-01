"""Swarm cost simulator — estimate token spend before dispatching a wave.

Uses configs/cost_rates.yaml (operator-editable). Not billing truth — planning guardrail.

CLI: python main.py cost-sim wave "epic name" [--build] [--improve N]
     python main.py cost-sim goal "…" [--dry]
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from config import CONFIGS_DIR, ROOT

RATES_PATH = CONFIGS_DIR / "cost_rates.yaml"
SCHEMA = "cost_sim.v1"


def _load_rates() -> dict[str, Any]:
    if not RATES_PATH.is_file():
        return {"seats": {}, "pack_modes": {}, "swarm_defaults": {}}
    return yaml.safe_load(RATES_PATH.read_text(encoding="utf-8")) or {}


def _seat_cost(seat: str, tokens_in: int, tokens_out: int, *, rates: dict[str, Any]) -> dict[str, Any]:
    seats = rates.get("seats") or {}
    cfg = seats.get(seat) or seats.get("deepseek") or {}
    inp = float(cfg.get("input_per_m") or 0)
    out = float(cfg.get("output_per_m") or 0)
    fixed = float(cfg.get("fixed_per_call") or 0)
    usd = fixed + (tokens_in / 1_000_000) * inp + (tokens_out / 1_000_000) * out
    return {
        "seat": seat,
        "label": cfg.get("label") or seat,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "usd_est": round(usd, 4),
    }


def estimate_goal(
    goal: str,
    *,
    seat: str | None = None,
    pack_mode: str | None = None,
    dry: bool = False,
) -> dict[str, Any]:
    """Estimate one routed goal via conductor phase + pack mode."""
    goal = (goal or "").strip()
    rates = _load_rates()
    packs = rates.get("pack_modes") or {}

    route_seat = seat or "deepseek"
    mode = pack_mode or "route"
    phase = "execute"

    if not dry:
        try:
            from mag.conductor import conduct

            dec = conduct(goal, dry=False)
            route = dec.get("route") or {}
            route_seat = str(route.get("seat") or route.get("provider") or route_seat)
            phase = str(dec.get("phase") or phase)
            g = goal.lower()
            if "[priority]" in g or phase == "plan":
                mode = "plan"
                route_seat = "grok"
            elif "[build]" in g or phase == "build":
                mode = "build"
                route_seat = "deepseek"
            elif "audit" in g or phase == "audit":
                mode = "audit"
                route_seat = "cursor"
            elif "[improve]" in g:
                mode = "janitor"
        except Exception as exc:
            return {"ok": False, "error": str(exc), "goal": goal[:200]}

    pack = packs.get(mode) or packs.get("route") or {"tokens_in": 2000, "tokens_out": 1000}
    seat_key = route_seat
    if seat_key in ("local", "agent"):
        seat_key = "ollama"
    if seat_key in ("deepseek", "deepseek_overmind"):
        seat_key = "deepseek"
    if seat_key in ("xai", "grok_tui"):
        seat_key = "grok"
    if seat_key == "cursor":
        seat_key = "cursor"

    line = _seat_cost(seat_key, int(pack.get("tokens_in") or 0), int(pack.get("tokens_out") or 0), rates=rates)
    routing = _seat_cost("mag_routing", 0, 0, rates=rates)

    return {
        "ok": True,
        "schema": SCHEMA,
        "goal": goal[:300],
        "phase": phase,
        "pack_mode": mode,
        "seat": seat_key,
        "line": line,
        "routing_usd": routing["usd_est"],
        "total_usd_est": round(line["usd_est"] + routing["usd_est"], 4),
        "dry": dry,
        "hint": "Edit configs/cost_rates.yaml — simulation only",
    }


def estimate_wave(
    name: str,
    *,
    improve_n: int = 2,
    build_waves: int = 3,
    audits: int = 1,
    plan: bool = True,
) -> dict[str, Any]:
    """Estimate a full v3 epic wave (phone plan → Cursor BUILD → DeepSeek build → audit)."""
    rates = _load_rates()
    defaults = rates.get("swarm_defaults") or {}
    improve_n = improve_n or int(defaults.get("improve_per_cycle") or 2)
    build_waves = build_waves or int(defaults.get("build_waves_per_epic") or 3)
    audits = audits or int(defaults.get("audit_per_epic") or 1)

    lines: list[dict[str, Any]] = []

    if plan:
        lines.append(_seat_cost("grok", 4000, 2000, rates=rates))  # phone/Grok plan sketch
        lines.append(_seat_cost("cursor", 8000, 4000, rates=rates))  # Cursor writes BUILD

    for _ in range(improve_n):
        p = rates.get("pack_modes", {}).get("janitor", {})
        lines.append(_seat_cost("ollama", int(p.get("tokens_in") or 800), int(p.get("tokens_out") or 400), rates=rates))

    for _ in range(build_waves):
        p = rates.get("pack_modes", {}).get("build", {})
        lines.append(_seat_cost("deepseek", int(p.get("tokens_in") or 6000), int(p.get("tokens_out") or 4000), rates=rates))

    for _ in range(audits):
        p = rates.get("pack_modes", {}).get("audit", {})
        lines.append(_seat_cost("cursor", int(p.get("tokens_in") or 8000), int(p.get("tokens_out") or 2000), rates=rates))

    lines.append(_seat_cost("mag_routing", 0, 0, rates=rates))

    total = round(sum(x["usd_est"] for x in lines), 4)
    tokens_in = sum(x["tokens_in"] for x in lines)
    tokens_out = sum(x["tokens_out"] for x in lines)

    return {
        "ok": True,
        "schema": SCHEMA,
        "wave": name,
        "lines": lines,
        "summary": {
            "usd_est": total,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "n_jobs": len(lines),
        },
        "economics_target": "Grok+Cursor plan ~15-25% · DeepSeek build ~50-70% · Ollama ~0",
        "hint": "Run mag.cmd cost-sim goal \"…\" before dispatch; tune configs/cost_rates.yaml",
    }


def format_wave_text(w: dict[str, Any]) -> str:
    lines = [f"Wave: {w.get('wave')} — est ${w.get('summary', {}).get('usd_est', '?')} USD"]
    for ln in w.get("lines") or []:
        lines.append(f"  · {ln.get('label')}: ${ln.get('usd_est')} ({ln.get('tokens_in')}+{ln.get('tokens_out')} tok)")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    import argparse
    import sys

    ap = argparse.ArgumentParser(prog="cost-sim", description="Swarm cost simulator")
    sub = ap.add_subparsers(dest="cmd")
    pg = sub.add_parser("goal", help="Estimate one goal")
    pg.add_argument("goal")
    pg.add_argument("--seat", default="")
    pg.add_argument("--pack", default="")
    pg.add_argument("--dry", action="store_true")
    pg.add_argument("--json", action="store_true")

    pw = sub.add_parser("wave", help="Estimate full epic wave")
    pw.add_argument("name")
    pw.add_argument("--improve", type=int, default=2)
    pw.add_argument("--build", type=int, default=3)
    pw.add_argument("--audit", type=int, default=1)
    pw.add_argument("--no-plan", action="store_true")
    pw.add_argument("--json", action="store_true")

    args = ap.parse_args(argv)
    if args.cmd == "goal":
        res = estimate_goal(args.goal, seat=args.seat or None, pack_mode=args.pack or None, dry=args.dry)
    elif args.cmd == "wave":
        res = estimate_wave(args.name, improve_n=args.improve, build_waves=args.build, audits=args.audit, plan=not args.no_plan)
    else:
        ap.print_help()
        return 2

    if getattr(args, "json", False):
        print(json.dumps(res, indent=2, default=str))
    elif args.cmd == "wave":
        print(format_wave_text(res))
    else:
        print(json.dumps(res, indent=2, default=str))
    return 0 if res.get("ok") else 1


if __name__ == "__main__":
    import sys

    sys.exit(main())
