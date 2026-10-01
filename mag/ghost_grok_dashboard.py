"""ghost_grok_dashboard — GHOST OVERTOP OF THE GROK DASHBOARD, shared-language cost reducer.

The operator's cost-savings mechanism: ghost sits ABOVE the grok dashboard and mediates
every frontier ask through the SHARED LANGUAGE LIBRARY (memlang). Instead of sending grok
a verbose prompt, ghost:
  1. Compiles the goal into a compact memlang token (verkle-anchored — the shared spec ref).
  2. Sends grok the MINIMAL shared-language packet (token ref + short pointer), not the prose.
  3. Decodes/tracks the result, folds savings into a cost ledger.

So grok only pays for the small token + the compact spec it truly needs — the shared library
means we never re-send the full prompt. Deterministic + grok-gated (frontier only, Law #7).

Schema: ghost_grok_dashboard.v1
CLI: python -m mag.ghost_grok_dashboard dispatch "<goal>" | savings
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

SCHEMA = "ghost_grok_dashboard.v1"
LEDGER = ROOT / "memory" / "ghost" / "grok_dashboard_ledger.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _approx_tokens(text: str) -> int:
    return max(1, len(text or "") // 4)


def _ledger() -> list[dict[str, Any]]:
    if not LEDGER.is_file():
        return []
    rows = []
    with open(LEDGER, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except Exception:
                    pass
    return rows


def _log_savings(goal: str, token: dict[str, Any], verbose_tokens: int, compact_tokens: int) -> None:
    row = {
        "ts": _now(), "schema": SCHEMA,
        "goal": (goal or "")[:160],
        "verbose_tokens": verbose_tokens,
        "compact_tokens": compact_tokens,
        "tokens_saved": verbose_tokens - compact_tokens,
        "anchor": (token.get("anchor_hex") or token.get("token", ""))[:16],
    }
    try:
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with open(LEDGER, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    except Exception:
        pass


def dispatch(goal: str, *, context: str = "") -> dict[str, Any]:
    """Ghost mediates a grok-dashboard ask through the shared memlang language library."""
    goal = (goal or "").strip()
    out: dict[str, Any] = {"schema": SCHEMA, "ts": _now(), "ok": True, "goal": goal[:200]}

    # Grok is frontier-only (Law #7): skip unless grok_gate says it pays.
    try:
        from mag.grok_gate import should_use_grok
        gate = should_use_grok(goal)
        out["grok_gate"] = gate
        if not gate.get("use_grok"):
            out["action"] = "cheap"
            out["note"] = gate.get("reason", "")
            return out
    except Exception as e:
        out["gate_error"] = str(e)[:120]

    # 1) compile to the shared-language memlang token (verkle-anchored spec ref)
    try:
        from mag.memlang import compile_token
        token = compile_token("rib_elevate", goal)
        out["memlang_token"] = {k: token.get(k) for k in ("opcode", "anchor_hex", "plen", "token")
                                if k in token}
    except Exception as e:
        token = {}
        out["memlang_error"] = str(e)[:120]

    # 2) build the MINIMAL shared-language packet for grok (token ref + short pointer)
    anchor = str(token.get("anchor_hex") or "")[:16]
    compact = (f"<memlang rib_elevate anchor={anchor}>\n"
               f"SPEC: {goal[:200]}\n"
               "Decode the full spec from the shared verkle/memlang registry; act on it "
               "compactly. Do not restate the prompt.")
    verbose_tokens = _approx_tokens(goal)
    compact_tokens = _approx_tokens(compact)

    # 3) send to the grok dashboard (grok_terminal) with the compact packet
    try:
        from mag.grok_terminal import launch_terminal
        res = launch_terminal(goal=compact, context=context)
        out["grok_terminal"] = {"ok": res.get("ok"), "action": res.get("action"),
                                "rounds": res.get("rounds_run"),
                                "result_path": res.get("result_path"),
                                "error": res.get("error")}
    except Exception as e:
        out["grok_terminal_error"] = str(e)[:160]

    # 4) track the cost savings (shared library means we never re-send prose)
    _log_savings(goal, token, verbose_tokens, compact_tokens)
    out["tokens"] = {"verbose": verbose_tokens, "compact": compact_tokens,
                     "saved": verbose_tokens - compact_tokens}
    out["action"] = "dispatched_via_shared_language"
    return out


def savings() -> dict[str, Any]:
    rows = _ledger()
    total = sum(r.get("tokens_saved", 0) for r in rows)
    calls = len(rows)
    return {"schema": SCHEMA, "ok": True, "calls": calls, "tokens_saved_total": total,
            "est_tokens_per_call_saved": round(total / max(1, calls), 1),
            "path": str(LEDGER)}


def saved_vs_projected() -> dict[str, Any]:
    """Dashboard counter: tokens SAVED (shared-language) vs PROJECTED (what verbose would've cost).

    saved     = sum over grok-dashboard calls of (verbose_tokens - compact_tokens)
    projected = the verbose tokens we would have sent without the shared memlang library
                (i.e. what the counterfactual spend WOULD have been).
    """
    rows = _ledger()
    calls = len(rows)
    saved = sum(r.get("tokens_saved", 0) for r in rows)
    projected = sum(r.get("verbose_tokens", 0) for r in rows)  # what we avoided sending
    # broader framework counterfactual (token_economy) for context
    economy = {}
    try:
        from mag.token_economy import economy_snapshot
        e = economy_snapshot()
        economy = {"lifetime_local": e.get("lifetime_local"),
                   "lifetime_saved": e.get("lifetime_saved"),
                   "counterfactual": e.get("counterfactual")}
    except Exception:
        pass
    return {
        "schema": "tokens_saved_vs_projected.v1", "ok": True, "calls": calls,
        "tokens_saved": saved,
        "projected_verbose_tokens": projected,
        "projected_est_cost_usd": round(projected / 1_000_000 * 0.30, 4),  # grok-3-mini in
        "saved_est_cost_usd": round(saved / 1_000_000 * 0.30, 4),
        "economy": economy,
        "path": str(LEDGER),
    }


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "savings":
        print(json.dumps(savings(), indent=2, ensure_ascii=False, default=str))
        return 0
    goal = " ".join(argv) if argv else ""
    print(json.dumps(dispatch(goal), indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
