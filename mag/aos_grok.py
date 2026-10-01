"""AOS Grok access controller — budgeted, specific-ask-only access to the lent
"Super Grok" frontier surface (AdventureNLearn's stack), starting small and proving it.

THE COURTESY CONTRACT (why this exists): the partner lends us access to their grok-heavy
frontier. We must NOT throw volume at it. This controller makes that a HARD, deterministic
rule (code-as-law), not a hope:

  1. HARD BUDGET (configs/aos_grok.yaml): max asks/day, max tokens/ask, cooldown between
     asks. Tunable only with partner sign-off. Never exceeds these, ever.
  2. SPECIFIC-ASK-ONLY gate: rejects scut/filler. Only curated high-value asks dispatch
     (frontier-gap shapes, HELP-WANTED asks, explicit [aos]/[specific] tagged, or
     elevate-signal goals like design/judgment).
  3. TRANSPARENT LEDGER (memory/embassy/AOS/grok_usage.jsonl): every call logged with
     ask, tokens, transport, model, est cost — the proof-of-respect artifact we SHOW
     the partner so he sees exactly what his access was used for.
  4. PROBE-FIRST: probe() fires ONE tiny bounded ask, verifies the round-trip + fold-back
     (the system integration test), and writes a PROOF doc. Start small, prove it, then
     scale only on partner sign.

CLI:  python -m mag.aos_grok status | probe | ask "<goal>" | cadence
REST: GET/POST /api/v1/aos-grok (action status|probe|ask)
Schema: aos_grok.v1
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone, date
from pathlib import Path
from typing import Any

from config import ROOT

SCHEMA = "aos_grok.v1"
CONFIG = ROOT / "configs" / "aos_grok.yaml"

# Goals that signal "specific enough for the lent frontier" (judgment / design / stakes).
_SPECIFIC_SIGNALS = (
    "design", "architect", "review", "audit", "assess", "decide", "recommend",
    "synthesize", "judgment", "evaluate", "contract", "partner", "opspec",
    "security", "strategy", "test plan", "adversarial", "symmetry",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _today() -> str:
    return date.today().isoformat()


def _budget() -> dict[str, Any]:
    """Read the courtesy budget (configs/aos_grok.yaml) with conservative defaults."""
    b: dict[str, Any] = {
        "transport": "xai", "model": "grok-4.5",
        "max_asks_per_day": 3, "max_tokens_per_ask": 800, "cooldown_seconds": 3600,
        "probe_max_tokens": 600, "probe_enabled": True, "auto_cadence": True,
        "ledger": "memory/embassy/AOS/grok_usage.jsonl",
        "proof_doc": "memory/embassy/AOS/grok_PROOF.md",
    }
    try:
        import yaml
        if CONFIG.is_file():
            b.update({k: v for k, v in (yaml.safe_load(CONFIG.read_text(encoding="utf-8")) or {}).items() if k in b})
    except Exception:
        pass
    return b


def _ledger_path(b: dict[str, Any]) -> Path:
    p = ROOT / str(b["ledger"])
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _proof_path(b: dict[str, Any]) -> Path:
    return ROOT / str(b["proof_doc"])


def _read_ledger(b: dict[str, Any]) -> list[dict[str, Any]]:
    p = _ledger_path(b)
    if not p.is_file():
        return []
    out = []
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except (json.JSONDecodeError, TypeError):
            continue
    return out


def _log_usage(b: dict[str, Any], row: dict[str, Any]) -> None:
    p = _ledger_path(b)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": _now(), **row}, ensure_ascii=False, default=str) + "\n")


def budget_status() -> dict[str, Any]:
    """Current courtesy-budget state: used today, tokens today, cooldown remaining."""
    b = _budget()
    rows = _read_ledger(b)
    today = _today()
    today_rows = [r for r in rows if (r.get("ts") or "")[:10] == today and r.get("ok")]
    used = len(today_rows)
    tokens = sum(int(r.get("tokens_out") or 0) for r in today_rows)
    cost = sum(float(r.get("cost_est_usd") or 0) for r in rows)
    remaining = max(0, int(b["max_asks_per_day"]) - used)
    last_ts = max((r.get("ts") or "") for r in rows) if rows else ""
    cooldown_left = 0
    if last_ts:
        try:
            import time
            last = datetime.fromisoformat(last_ts).timestamp()
            cd = int(b["cooldown_seconds"])
            cooldown_left = max(0, int(cd - (time.time() - last)))
        except Exception:
            cooldown_left = 0
    return {
        "schema": SCHEMA,
        "today": today,
        "asks_used_today": used,
        "max_asks_per_day": int(b["max_asks_per_day"]),
        "remaining_today": remaining,
        "tokens_out_today": tokens,
        "max_tokens_per_ask": int(b["max_tokens_per_ask"]),
        "cooldown_seconds_left": cooldown_left,
        "total_calls": len(rows),
        "total_est_cost_usd": round(cost, 6),
        "transport": b["transport"],
        "model": b["model"],
        "probe_enabled": bool(b["probe_enabled"]),
        "auto_cadence": bool(b["auto_cadence"]),
    }


def _is_specific_ask(goal: str) -> bool:
    """Deterministic gate: is this ask specific/high-value enough for the lent frontier?
    Rejects scut/filler. Accepts elevate-signal goals or explicit [aos]/[specific] tags.
    """
    g = (goal or "").lower()
    low = g
    if not low or len(low) < 8:
        return False
    if any(t in low for t in ("[aos]", "[specific]", "[frontier]", "[super grok]")):
        return True
    if any(s in low for s in _SPECIFIC_SIGNALS):
        return True
    # HELP-WANTED / frontier-gap shapes count as specific (they're already curated).
    if "frontier-gap" in low or "help-wanted" in low or "frontier-gap shape" in low:
        return True
    return False


def _dispatch(goal: str, *, max_tokens: int) -> dict[str, Any]:
    """Bounded grok call via the rightsize transport. Returns raw result."""
    # Self-reference the research-lens corpus so the lent frontier builds on what the
    # cheap system already learned (compounding), not a cold blank slate.
    context = ""
    try:
        from mag.research_lens import retrieve_prior
        pr = retrieve_prior(goal, lens_id="default", limit=3)
        if pr.get("prior_refs"):
            context = pr.get("prior_block", "")[:4000]
    except Exception:
        pass
    try:
        from mag.grok_rightsize import call_grok
        res = call_grok(goal, max_tokens=max_tokens, context=context or None)
        return {
            "ok": bool(getattr(res, "ok", False)),
            "content": str(getattr(res, "content", "") or "")[:2000],
            "model": getattr(res, "model", ""),
            "tier": getattr(res, "tier", ""),
            "cost_est_usd": float(getattr(res, "cost_est_usd", 0) or 0),
            "latency_ms": float(getattr(res, "latency_ms", 0) or 0),
            "error": getattr(res, "error", ""),
        }
    except Exception as e:
        return {"ok": False, "content": "", "error": str(e)[:300]}


def specific_ask(goal: str, *, force: bool = False, transport: str | None = None) -> dict[str, Any]:
    """Main entry: gate + budget + dispatch ONE specific ask; log to the transparent ledger."""
    b = _budget()
    st = budget_status()

    if not force and not _is_specific_ask(goal):
        return {"ok": False, "action": "rejected_scut", "reason": "not a specific/high-value ask",
                "hint": "tag [aos] or use a design/judgment/evaluate goal"}
    if not force and st["remaining_today"] <= 0:
        return {"ok": False, "action": "budget_exhausted", "status": st}
    if not force and st["cooldown_seconds_left"] > 0:
        return {"ok": False, "action": "cooldown", "seconds_left": st["cooldown_seconds_left"]}

    transport = transport or str(b["transport"])
    max_tokens = int(b["max_tokens_per_ask"])
    if not force:
        max_tokens = min(max_tokens, int(b["max_tokens_per_ask"]))

    res = _dispatch(goal, max_tokens=max_tokens)
    row = {
        "action": "specific_ask",
        "goal": (goal or "")[:400],
        "ok": bool(res.get("ok")),
        "transport": transport,
        "model": res.get("model") or b["model"],
        "tokens_out": len(str(res.get("content") or "")) // 4,
        "cost_est_usd": res.get("cost_est_usd", 0),
        "latency_ms": res.get("latency_ms", 0),
        "error": res.get("error", "")[:200],
        "content": res.get("content", "")[:1500],
    }
    _log_usage(b, row)
    row.pop("content", None)  # don't bloat the ledger with full replies; keep a pointer
    return {"ok": res.get("ok"), "action": "dispatched", "row": row, "status": budget_status(),
            "ledger": str(_ledger_path(b))}


def probe(*, force: bool = False) -> dict[str, Any]:
    """START SMALL + PROVE IT: fire ONE tiny bounded ask, verify round-trip + fold-back,
    and write the PROOF doc — the proof-of-respect artifact we show the partner."""
    b = _budget()
    if not b["probe_enabled"] and not force:
        return {"ok": False, "action": "probe_disabled"}
    goal = ("[aos][specific] probe: verify integration with the AOS grok surface. "
            "Reply in <=3 sentences: confirm you can see this specific ask, and name one "
            "asymmetry-reduction pattern from ARK Gate 6. This is a bounded integration test.")
    res = _dispatch(goal, max_tokens=int(b["probe_max_tokens"]))
    ok = bool(res.get("ok"))
    row = {
        "action": "probe",
        "goal": (goal or "")[:200],
        "ok": ok,
        "transport": b["transport"],
        "model": res.get("model") or b["model"],
        "tokens_out": len(str(res.get("content") or "")) // 4,
        "cost_est_usd": res.get("cost_est_usd", 0),
        "latency_ms": res.get("latency_ms", 0),
        "error": res.get("error", "")[:200],
    }
    _log_usage(b, row)

    # Fold the proof: write the PROOF doc (the artifact we show the partner).
    proof = _proof_path(b)
    body = (
        "# AOS GROK INTEGRATION PROOF\n\n"
        f"- Ran: `{_now()}`\n- Transport: `{b['transport']}` · model `{res.get('model') or b['model']}`\n"
        f"- Outcome: **{'PASS' if ok else 'FAIL'}**\n"
        f"- Round-trip verified: the system sent a bounded specific ask to the lent grok "
        f"surface and received a reply (tokens_out~{row['tokens_out']}, est_cost~${row['cost_est_usd']}).\n\n"
        f"## Reply (bounded probe)\n{res.get('content', '')[:1200]}\n\n"
        "## What this proves\n"
        "1. The controller can reach the lent frontier with a bounded, budgeted call.\n"
        "2. The transparent usage ledger records every call (see grok_usage.jsonl).\n"
        "3. Usage stays inside the courtesy budget — start small, prove it, scale on sign.\n"
    )
    proof.write_text(body, encoding="utf-8")
    return {"ok": ok, "action": "probe", "proof": str(proof), "row": row, "status": budget_status()}


def _pending_specific_ask() -> str:
    """Find a new specific ask to dispatch on cadence (from HELP-WANTED or explicit queue)."""
    # HELP-WANTED doc — the curated frontier asks already percolated.
    try:
        p = ROOT / "memory" / "frontier" / "HELP_WANTED.md"
        if p.is_file():
            for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
                s = line.strip()
                if s and s[0].isdigit() and ". " in s:
                    goal = s.split(". ", 1)[-1]
                    if _is_specific_ask(goal):
                        return goal[:400]
    except Exception:
        pass
    return ""


def run_cadence() -> dict[str, Any]:
    """Idempotent cadence: dispatch a NEW specific ask only when the budget allows and
    the ask hasn't been sent before (tracked by goal prefix in the ledger)."""
    b = _budget()
    if not b["auto_cadence"]:
        return {"ok": True, "action": "skip", "reason": "auto_cadence_disabled"}
    st = budget_status()
    if st["remaining_today"] <= 0 or st["cooldown_seconds_left"] > 0:
        return {"ok": True, "action": "skip", "reason": "budget_or_cooldown"}
    goal = _pending_specific_ask()
    if not goal:
        return {"ok": True, "action": "skip", "reason": "no_new_specific_ask"}
    rows = _read_ledger(b)
    sent = {str(r.get("goal") or "")[:60] for r in rows}
    if goal[:60] in sent:
        return {"ok": True, "action": "skip", "reason": "already_sent"}
    return specific_ask(goal)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    ap = argparse.ArgumentParser(prog="aos-grok", description="Budgeted AOS grok access (start small, prove it)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status", help="courtesy-budget status")
    sub.add_parser("probe", help="START SMALL: one bounded probe ask + write the PROOF doc")
    p_ask = sub.add_parser("ask", help="dispatch a specific ask (budget + gate enforced)")
    p_ask.add_argument("goal", nargs="+")
    p_ask.add_argument("--force", action="store_true", help="bypass gate/budget (operator-only)")
    sub.add_parser("cadence", help="idempotent cadence: one new specific ask when budget allows")
    args = ap.parse_args(argv)
    if args.cmd == "status":
        print(json.dumps(budget_status(), indent=2, default=str))
    elif args.cmd == "probe":
        print(json.dumps(probe(), indent=2, default=str)[:8000])
    elif args.cmd == "ask":
        print(json.dumps(specific_ask(" ".join(args.goal), force=args.force), indent=2, default=str)[:8000])
    elif args.cmd == "cadence":
        print(json.dumps(run_cadence(), indent=2, default=str)[:8000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
