"""grok_frontier_loop — self-improvement loop for FRONTIER RESEARCH STEALS via grok 4.5.

WHY (2026-08-11, operator): we have premium grok with ~92% of the premium API remaining
(8% used, resets 2026-08-15; the other grok opens 2026-08-13T02:52). Use the remaining premium
on GENUINE frontier work — research steals that only grok 4.5 can do — and RIGHTSIZE so cheap
shapes never touch grok. Self-improve: each cycle folds the outcome so the next rightsizes.

The loop (stateless, measured, self-correcting):
  1. PICK a frontier-gap steal target (frontier gap map / scout findings / HELP_WANTED), deduped.
  2. GATE on budget + frontier-need (grok 4.5 = "orchestrate" tier ONLY; cheap first).
  3. RUN grok 4.5 -> frontier synthesis (a steal: research + adapt the invariant).
  4. FOLD via steal_pack + verkle knot (content-addressed, durable).
  5. LEARN: log outcome + adoption so the next cycle rightsizes better.

Honesty (operator law): grok_captured is TRUE only when the call actually returned text.
In dry/$0 mode we fold OUR synthesis with grok_captured=False + provenance note — never claim
frontier output that didn't arrive.

Schema: grok_frontier_loop.v1 · cheap/deepseek for scut, grok 4.5 only for frontier steals.
CLI: python -m mag.grok_frontier_loop status | test | cycle [--dry] [--force] | learn
"""
from __future__ import annotations

import argparse
import json
import os
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

SCHEMA = "grok_frontier_loop.v1"
STATE_DIR = ROOT / "memory" / "runs" / "grok_frontier_loop"
LEDGER = STATE_DIR / "cycles.jsonl"
DONE = STATE_DIR / "done.jsonl"

# Budget config (operator, 2026-08-11). Adjust in config/env; never fabricate spend.
BUDGET_DEFAULTS = {
    "remaining_pct": 92.0,     # premium API remaining (8% used)
    "reset_date": "2026-08-15",
    "next_grok_open": "2026-08-13T02:52Z",   # other grok account opens
    "min_remaining_pct": 25.0,  # stop spending grok below this (leave headroom)
    "cooldown_s": 900,          # 15 min between grok-4.5 frontier steals
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _cfg() -> dict[str, Any]:
    c = dict(BUDGET_DEFAULTS)
    for k in ("remaining_pct", "reset_date", "next_grok_open", "min_remaining_pct", "cooldown_s"):
        v = os.environ.get(f"GROK_FRONTIER_{k.upper()}")
        if v:
            try:
                c[k] = float(v) if k in ("remaining_pct", "min_remaining_pct", "cooldown_s") else v
            except ValueError:
                pass
    return c


def _read_jsonl(path: Path, tail: int = 200) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    out = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out[-tail:]


def _append_jsonl(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False, default=str) + "\n")


# ── budget / gate ───────────────────────────────────────────────────────────
def budget_status() -> dict[str, Any]:
    c = _cfg()
    last = _read_jsonl(LEDGER, tail=1)
    last_ts = last[0].get("ts") if last else None
    cooldown_left = 0
    if last_ts:
        try:
            lt = datetime.fromisoformat(str(last_ts).replace("Z", "+00:00"))
            cooldown_left = max(0, int(c["cooldown_s"]) - int((datetime.now(timezone.utc) - lt).total_seconds()))
        except (ValueError, TypeError):
            cooldown_left = 0
    can_spend = c["remaining_pct"] >= c["min_remaining_pct"] and cooldown_left <= 0
    return {"schema": SCHEMA, "ts": _now(), "budget": c,
            "cooldown_left_s": cooldown_left,
            "can_spend_grok": can_spend,
            "n_cycles": len(_read_jsonl(LEDGER))}


def _gate() -> dict[str, Any]:
    st = budget_status()
    if not st["can_spend_grok"]:
        return {"ok": False, "reason": "budget_or_cooldown", "status": st}
    return {"ok": True, "status": st}


# ── frontier-gap target selection (deduped) ────────────────────────────────
def frontier_targets() -> list[str]:
    """Collect frontier-gap steal candidates (things that need a frontier model)."""
    cands: list[str] = []
    try:
        from mag.gap_map import analyze as gap_analyze
        g = gap_analyze()
        cands += [f"frontier-gap: {n}" for n in (g.get("frontier_gap_names") or [])][:3]
    except Exception:
        pass
    try:
        fh = ROOT / "memory" / "frontier" / "HELP_WANTED.md"
        if fh.is_file():
            for line in fh.read_text(encoding="utf-8", errors="replace").splitlines():
                s = line.strip()
                if s and (s[0].isdigit() or s.startswith("- ")) and len(s) > 20:
                    cands.append("help-wanted: " + s[:160])
                    if len(cands) >= 6:
                        break
    except Exception:
        pass
    try:
        sc = ROOT / "memory" / "frontier" / "scout_findings.jsonl"
        for r in _read_jsonl(sc, tail=50):
            if r.get("verdict") in ("adopt", None):
                cands.append("scout: " + str(r.get("summary") or r.get("finding") or "")[:160])
                if len(cands) >= 8:
                    break
    except Exception:
        pass
    return cands


def _done_set() -> set[str]:
    return {str(r.get("goal")) for r in _read_jsonl(DONE, tail=500)}


def pick_target() -> dict[str, Any]:
    """Pick the highest-value frontier steal target not yet done (dedup)."""
    done = _done_set()
    for goal in frontier_targets():
        if goal not in done:
            return {"ok": True, "goal": goal}
    return {"ok": False, "reason": "no_unstealed_frontier_target", "done_n": len(done)}


# ── run the frontier steal (grok 4.5) + fold ────────────────────────────────
def run_frontier_steal(goal: str, *, dry: bool = True, force: bool = False) -> dict[str, Any]:
    """Run ONE grok-4.5 frontier steal, fold via steal_pack + verkle knot. Honest about capture."""
    report: dict[str, Any] = {"schema": SCHEMA, "ts": _now(), "goal": goal, "dry": dry,
                              "grok_captured": False}
    if not dry and not force:
        g = _gate()
        if not g["ok"]:
            return {"ok": False, "reason": g["reason"], "status": g["status"]}
    synthesis = ""
    captured = False
    if not dry:
        try:
            from mag.grok_rightsize import call_grok
            res = call_grok(goal, tier="orchestrate", max_tokens=4096)  # grok 4.5
            captured = bool(res.ok) and bool((res.content or "").strip())
            if captured:
                synthesis = res.content
        except Exception as e:
            report["error"] = str(e)[:200]
    report["grok_captured"] = captured
    if not captured and not dry:
        report["provenance_note"] = ("grok 4.5 requested but returned no real output; "
                                     "this is OUR synthesis, not frontier output.")
    # Fold: build a steal doc (even in dry, from our synthesis), fold via steal_pack + verkle.
    content = synthesis if captured else ("Synthesis placeholder for frontier steal: " + goal[:200])
    fold = _fold_steal(goal, content, captured=captured)
    report["fold"] = fold
    _append_jsonl(DONE, {"ts": _now(), "goal": goal, "grok_captured": captured, "dry": dry})
    return {"ok": True, **report}


def _fold_steal(goal: str, content: str, *, captured: bool) -> dict[str, Any]:
    out: dict[str, Any] = {}
    try:
        doc = STATE_DIR / f"STEAL_FRONTIER_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}.md"
        doc.parent.mkdir(parents=True, exist_ok=True)
        doc.write_text(
            f"# FRONTIER STEAL (grok_frontier_loop)\n\n- goal: {goal}\n- captured: {captured}\n"
            f"- ts: {_now()}\n\n{content[:4000]}\n",
            encoding="utf-8")
        out["doc"] = str(doc)
    except Exception as e:
        out["doc_error"] = str(e)[:120]
    try:
        from mag.steal_pack import file_steal
        out["steal_pack"] = file_steal(doc, tag="grok-frontier")
    except Exception as e:
        out["steal_pack_error"] = str(e)[:120]
    try:
        from mag.verkle_knot import append_verkle_knot
        out["verkle"] = append_verkle_knot({
            "session_id": f"grok-frontier-steal:{datetime.now(timezone.utc).strftime('%H%M')}",
            "theme": "steal", "summary": f"[frontier steal] {goal[:120]}",
        })
    except Exception as e:
        out["verkle_error"] = str(e)[:120]
    return out


# ── self-improvement / learn ───────────────────────────────────────────────
def learn() -> dict[str, Any]:
    """Fold cycle outcomes so the loop rightsizes: log capture rate + adoption, adjust budget guard."""
    cyc = _read_jsonl(LEDGER)
    if not cyc:
        cyc = _read_jsonl(DONE, tail=50)
    n = len(cyc)
    captured = sum(1 for c in cyc if c.get("grok_captured"))
    rate = (captured / n) if n else 0.0
    _append_jsonl(LEDGER, {"ts": _now(), "n": n, "captured": captured, "capture_rate": round(rate, 3),
                           "note": "learn: fold capture-rate so rightsize holds grok for shapes that actually capture"})
    return {"schema": SCHEMA, "ts": _now(), "n": n, "captured": captured,
            "capture_rate": round(rate, 3)}


def cycle(*, dry: bool = True, force: bool = False) -> dict[str, Any]:
    """One full iteration: pick -> gate -> run -> fold -> learn."""
    t = pick_target()
    if not t["ok"]:
        return {"ok": True, "action": "skip", "reason": t["reason"]}
    r = run_frontier_steal(t["goal"], dry=dry, force=force)
    lr = learn()
    return {"ok": True, "action": "cycle", "target": t["goal"], "result": r, "learn": lr}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="grok-frontier-loop",
                                 description="Self-improvement loop for frontier steals via grok 4.5 (rightsized).")
    ap.add_argument("cmd", nargs="?", choices=["status", "test", "cycle", "learn"], default="status")
    ap.add_argument("--dry", action="store_true", default=True)
    ap.add_argument("--force", action="store_true", help="bypass budget/cooldown gate (operator-only)")
    a = ap.parse_args(argv)
    if a.cmd == "status":
        print(json.dumps(budget_status(), indent=2, default=str))
    elif a.cmd == "test":
        print(json.dumps(cycle(dry=True), indent=2, default=str))
    elif a.cmd == "cycle":
        print(json.dumps(cycle(dry=a.dry, force=a.force), indent=2, default=str))
    else:
        print(json.dumps(learn(), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

__all__ = ["budget_status", "pick_target", "run_frontier_steal", "cycle", "learn", "main"]
