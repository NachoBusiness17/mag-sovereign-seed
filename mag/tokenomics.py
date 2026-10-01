"""Tokenomics Observer — Friedman-esque cost intelligence for sovereign agents.

"INFLATION is always and everywhere a monetary phenomenon."
  — Milton Friedman

"TOKEN INFLATION is always and everywhere a context-window phenomenon."
  — Ghost Friedman, 2026

Every token has a price. That price is a signal. This module reads those signals
and produces actionable intelligence: where to route, when to switch providers,
which tasks are bleeding tokens, and what the real cost of sovereignty is.

SCHEMA: tokenomics.v1
LAW: Every token is accounted for. No free inferences.
LAW: Provider arbitrage is rational. Route to cheapest capable model.
LAW: Context window bloat is inflation. Monitor and control.
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Optional

try:
    from config import ROOT
except ImportError:
    ROOT = Path(__file__).resolve().parent.parent


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ═══════════════════════════════════════════════════════════════════
# PRICE SIGNALS — the market data
# ═══════════════════════════════════════════════════════════════════

# Known pricing per 1M tokens (input / output)
PROVIDER_PRICES: dict[str, dict[str, float]] = {
    "deepseek-v4-flash":     {"in": 0.013, "out": 0.013},
    "deepseek-v4":           {"in": 0.040, "out": 0.040},
    "grok-3-mini":           {"in": 0.300, "out": 0.300},
    "grok-4-latest":         {"in": 2.500, "out": 10.000},
    "gpt-4o":                {"in": 2.500, "out": 10.000},
    "gpt-4o-mini":           {"in": 0.150, "out": 0.600},
    "claude-3.5-sonnet":     {"in": 3.000, "out": 15.000},
    "claude-3-haiku":        {"in": 0.250, "out": 1.250},
    "ollama-qwen2.5-coder":  {"in": 0.000, "out": 0.000},
    "ollama-gemma2":         {"in": 0.000, "out": 0.000},
}

# Capability tiers (what each model can do)
CAPABILITY_TIERS: dict[str, int] = {
    "deepseek-v4-flash":     40,  # good coding, fast, cheap
    "deepseek-v4":           50,  # better reasoning
    "grok-3-mini":           55,  # analysis, research
    "grok-4-latest":         70,  # orchestration
    "gpt-4o":                65,  # general purpose
    "gpt-4o-mini":           35,  # budget
    "claude-3.5-sonnet":     60,  # coding
    "claude-3-haiku":        30,  # budget
    "ollama-qwen2.5-coder":  20,  # local
    "ollama-gemma2":         15,  # local
}

FRIEDMAN_QUOTES = [
    "There's no such thing as a free token.",
    "Token inflation is always and everywhere a context-window phenomenon.",
    "The business of AI is token arbitrage.",
    "A model's greatest enemy is its own context window.",
    "Price is what you pay. Tokens are what you burn.",
    "The market can stay irrational longer than your API credits can stay solvent.",
    "Underlying most arguments against the free API market is a lack of belief in token discipline itself.",
    "Many people want the government to protect the consumer. A far more urgent problem is to protect the consumer from the government — and from locked-in model providers.",
    "The great virtue of a free token market is that it enables people who hate each other to cooperate on inference.",
    "You never change things by fighting the existing provider. You change things by building a new model that makes the existing one obsolete.",
]


# ═══════════════════════════════════════════════════════════════════
# OBSERVER
# ═══════════════════════════════════════════════════════════════════

class TokenomicsObserver:
    """Read the Ghost ledger and produce Friedman-esque cost intelligence."""

    def __init__(self):
        self.ledger_path = ROOT / "memory" / "ledger" / "ghost_ledger.jsonl"

    def _read_entries(self, days: int = 30) -> list[dict[str, Any]]:
        """Read ledger entries from the last N days."""
        if not self.ledger_path.is_file():
            return []

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        entries = []
        try:
            for line in self.ledger_path.read_text(encoding="utf-8").strip().splitlines():
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    ts = entry.get("ts", "")
                    if ts:
                        try:
                            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                            if dt < cutoff:
                                continue
                        except (ValueError, TypeError):
                            pass
                    entries.append(entry)
                except json.JSONDecodeError:
                    continue
        except (UnicodeDecodeError, OSError):
            pass

        return entries

    # ── Cost per token ──────────────────────────────────────────

    def cost_per_model(self) -> dict[str, dict[str, Any]]:
        """Compute cost/token for each model in the ledger."""
        entries = self._read_entries()
        models: dict[str, dict[str, float]] = defaultdict(lambda: {"tokens_in": 0, "tokens_out": 0, "cost": 0.0, "calls": 0})

        for e in entries:
            m = e.get("model", "unknown")
            models[m]["tokens_in"] += e.get("tokens_in", 0)
            models[m]["tokens_out"] += e.get("tokens_out", 0)
            models[m]["cost"] += e.get("cost_usd", 0.0)
            models[m]["calls"] += 1

        result = {}
        for m, d in models.items():
            total_tokens = d["tokens_in"] + d["tokens_out"]
            cost_usd = d["cost"]
            result[m] = {
                "model": m,
                "calls": d["calls"],
                "tokens_in": d["tokens_in"],
                "tokens_out": d["tokens_out"],
                "tokens_total": total_tokens,
                "cost_usd": round(cost_usd, 4),
                "cost_per_1k_tokens": round(cost_usd / (total_tokens / 1000), 6) if total_tokens > 0 else 0,
                "cost_per_call": round(cost_usd / d["calls"], 6) if d["calls"] > 0 else 0,
                "efficiency_ratio": round(d["tokens_out"] / d["tokens_in"], 2) if d["tokens_in"] > 0 else 0,
            }

        return result

    # ── Burn rate ───────────────────────────────────────────────

    def burn_rate(self) -> dict[str, Any]:
        """Daily burn rate and projections."""
        entries = self._read_entries(days=30)
        daily: dict[str, float] = defaultdict(float)

        for e in entries:
            ts = e.get("ts", "")
            if ts:
                day = ts[:10]  # YYYY-MM-DD
                daily[day] += e.get("cost_usd", 0.0)

        if not daily:
            return {"daily_burn": {}, "avg_daily": 0, "projected_monthly": 0, "trend": "no data"}

        days = sorted(daily.keys())
        avg = sum(daily.values()) / len(daily)
        recent_avg = sum(daily[d] for d in days[-7:]) / min(7, len(days)) if len(days) >= 7 else avg

        # Trend: are we spending more or less?
        if len(days) >= 14:
            first_week = sum(daily[d] for d in days[:7]) / 7
            last_week = sum(daily[d] for d in days[-7:]) / 7
            if last_week > first_week * 1.3:
                trend = "INFLATIONARY — burn rate rising >30%"
            elif last_week < first_week * 0.7:
                trend = "DEFLATIONARY — burn rate falling >30%"
            elif last_week > first_week * 1.1:
                trend = "mild inflation"
            elif last_week < first_week * 0.9:
                trend = "mild deflation"
            else:
                trend = "stable"
        else:
            trend = "insufficient data"

        return {
            "daily_burn": {d: round(v, 6) for d, v in sorted(daily.items())[-14:]},
            "avg_daily": round(avg, 4),
            "recent_avg_daily": round(recent_avg, 4),
            "projected_monthly": round(recent_avg * 30, 2),
            "projected_annual": round(recent_avg * 365, 2),
            "trend": trend,
            "days_tracked": len(daily),
        }

    # ── Arbitrage opportunities ─────────────────────────────────

    def arbitrage_opportunities(self) -> list[dict[str, Any]]:
        """Find opportunities to switch providers and save money.

        For each task type, find the cheapest model that can do it.
        """
        entries = self._read_entries()
        task_models: dict[str, dict[str, dict[str, float]]] = defaultdict(lambda: defaultdict(lambda: {"cost": 0, "calls": 0}))

        for e in entries:
            task = e.get("task_type") or "unknown"
            model = e.get("model", "unknown")
            task_models[task][model]["cost"] += e.get("cost_usd", 0)
            task_models[task][model]["calls"] += 1

        opportunities = []
        for task, models in task_models.items():
            # Find current most-used model and its cost
            current_model = max(models, key=lambda m: models[m]["calls"])
            current_cost = models[current_model]["cost"]
            current_calls = models[current_model]["calls"]
            current_cost_per_call = current_cost / current_calls if current_calls > 0 else 0

            # Find cheapest alternative with sufficient capability
            current_tier = CAPABILITY_TIERS.get(current_model, 30)
            alternatives = []
            for alt_model, alt_price in PROVIDER_PRICES.items():
                alt_tier = CAPABILITY_TIERS.get(alt_model, 0)
                if alt_model == current_model:
                    continue
                if alt_tier < current_tier - 5:  # must be close in capability
                    continue
                alt_cost_per_call = (500 + 200) / 1_000_000 * (alt_price["in"] + alt_price["out"]) / 2
                if alt_cost_per_call < current_cost_per_call:
                    savings_pct = (1 - alt_cost_per_call / current_cost_per_call) * 100 if current_cost_per_call > 0 else 0
                    alternatives.append({
                        "model": alt_model,
                        "tier": alt_tier,
                        "est_cost_per_call": round(alt_cost_per_call, 6),
                        "savings_pct": round(savings_pct, 1),
                    })

            if alternatives:
                alternatives.sort(key=lambda a: a["est_cost_per_call"])
                opportunities.append({
                    "task_type": task,
                    "current_model": current_model,
                    "current_tier": current_tier,
                    "current_cost_per_call": round(current_cost_per_call, 6),
                    "total_spent": round(current_cost, 4),
                    "alternatives": alternatives[:3],
                    "best_switch": alternatives[0]["model"],
                    "estimated_savings": f"{alternatives[0]['savings_pct']}%",
                })

        return sorted(opportunities, key=lambda o: o["total_spent"], reverse=True)

    # ── Waste detection ─────────────────────────────────────────

    def waste_detection(self) -> list[dict[str, Any]]:
        """Detect tasks that cost more than they should.

        Waste = high cost + low token efficiency.
        """
        entries = self._read_entries()
        if not entries:
            return []

        # Group by goal_summary
        goals: dict[str, dict[str, Any]] = defaultdict(lambda: {"cost": 0.0, "tokens_in": 0, "tokens_out": 0, "calls": 0, "models": set()})

        for e in entries:
            goal = e.get("goal_summary") or "(no goal)"
            goals[goal]["cost"] += e.get("cost_usd", 0)
            goals[goal]["tokens_in"] += e.get("tokens_in", 0)
            goals[goal]["tokens_out"] += e.get("tokens_out", 0)
            goals[goal]["calls"] += 1
            goals[goal]["models"].add(e.get("model", "unknown"))

        # Find expensive, inefficient tasks
        waste = []
        for goal, d in goals.items():
            if d["calls"] < 3:
                continue  # not enough data

            cost_per_call = d["cost"] / d["calls"]
            efficiency = d["tokens_out"] / d["tokens_in"] if d["tokens_in"] > 0 else 0

            # Flag if cost > $0.01/call and efficiency < 0.5
            if cost_per_call > 0.01 and efficiency < 0.5:
                waste.append({
                    "goal": goal[:120],
                    "calls": d["calls"],
                    "total_cost": round(d["cost"], 4),
                    "cost_per_call": round(cost_per_call, 4),
                    "efficiency_ratio": round(efficiency, 2),
                    "models_used": list(d["models"]),
                    "diagnosis": _diagnose_waste(cost_per_call, efficiency, d["models"]),
                })

        return sorted(waste, key=lambda w: w["total_cost"], reverse=True)[:10]

    # ── Context inflation tracker ───────────────────────────────

    def context_inflation(self) -> dict[str, Any]:
        """Track context window growth over time.

        'Token inflation is always and everywhere a context-window phenomenon.'
        """
        entries = self._read_entries(days=30)
        if not entries:
            return {"status": "no data"}

        daily_tokens: dict[str, list[int]] = defaultdict(list)
        for e in entries:
            ts = e.get("ts", "")[:10]
            if ts and e.get("tokens_in", 0) > 0:
                daily_tokens[ts].append(e["tokens_in"])

        days = sorted(daily_tokens.keys())
        if len(days) < 3:
            return {"status": "insufficient data"}

        averages = []
        for day in days:
            vals = daily_tokens[day]
            averages.append({
                "day": day,
                "avg_tokens_in": round(sum(vals) / len(vals)),
                "max_tokens_in": max(vals),
                "call_count": len(vals),
            })

        # Compute trend
        first_week_avg = sum(a["avg_tokens_in"] for a in averages[:min(7, len(averages))]) / min(7, len(averages))
        last_week_avg = sum(a["avg_tokens_in"] for a in averages[-min(7, len(averages)):]) / min(7, len(averages))
        growth_pct = round((last_week_avg / first_week_avg - 1) * 100, 1) if first_week_avg > 0 else 0

        return {
            "status": "INFLATIONARY" if growth_pct > 10 else "stable" if abs(growth_pct) < 10 else "DEFLATIONARY",
            "context_growth_pct": growth_pct,
            "first_week_avg_tokens": round(first_week_avg),
            "last_week_avg_tokens": round(last_week_avg),
            "friedman_says": "Context window bloat is the hidden tax on every inference." if growth_pct > 10 else "Context discipline is holding.",
            "daily_averages": averages[-14:],
        }

    # ── Full dashboard ──────────────────────────────────────────

    def dashboard(self) -> dict[str, Any]:
        """Full tokenomics dashboard — all signals in one view."""
        burn = self.burn_rate()
        inflation = self.context_inflation()
        per_model = self.cost_per_model()
        arbitrage = self.arbitrage_opportunities()
        waste = self.waste_detection()

        # Compute the single most important number: effective cost per 1K tokens
        total_tokens = sum(m["tokens_total"] for m in per_model.values())
        total_cost = sum(m["cost_usd"] for m in per_model.values())
        effective_rate = round(total_cost / (total_tokens / 1000), 6) if total_tokens > 0 else 0

        import random
        quote = random.choice(FRIEDMAN_QUOTES)

        return {
            "schema": "tokenomics.v1",
            "ts": _now(),
            "friedman_says": quote,
            "headline": {
                "effective_cost_per_1k_tokens": effective_rate,
                "daily_burn": burn["recent_avg_daily"],
                "monthly_projection": burn["projected_monthly"],
                "trend": burn["trend"],
            },
            "burn_rate": burn,
            "context_inflation": inflation,
            "per_model": per_model,
            "arbitrage_opportunities": arbitrage[:5],
            "waste_detection": waste[:5],
            "provider_prices": PROVIDER_PRICES,
        }


def _diagnose_waste(cost_per_call: float, efficiency: float, models: set[str]) -> str:
    """Diagnose why a task is wasteful."""
    reasons = []
    if cost_per_call > 0.05:
        reasons.append("expensive model — consider routing to DeepSeek")
    if efficiency < 0.2:
        reasons.append("very low output ratio — too much context, too little result")
    if any("grok-4" in m for m in models):
        reasons.append("Grok-4 used — check if Grok-3-mini suffices")
    if cost_per_call > 0.01 and efficiency < 0.5:
        reasons.append("high cost + low output — candidate for prompt compression")
    return "; ".join(reasons) if reasons else "borderline — monitor"


# ═══════════════════════════════════════════════════════════════════
# QUICK ACCESS
# ═══════════════════════════════════════════════════════════════════

_OBSERVER: Optional[TokenomicsObserver] = None


def get_observer() -> TokenomicsObserver:
    global _OBSERVER
    if _OBSERVER is None:
        _OBSERVER = TokenomicsObserver()
    return _OBSERVER


def tokenomics_dashboard() -> dict[str, Any]:
    """One-call full dashboard."""
    return get_observer().dashboard()


def tokenomics_burn() -> dict[str, Any]:
    """Quick burn rate check."""
    return get_observer().burn_rate()


def tokenomics_arbitrage() -> list[dict[str, Any]]:
    """Find savings opportunities."""
    return get_observer().arbitrage_opportunities()


def tokenomics_waste() -> list[dict[str, Any]]:
    """Find waste."""
    return get_observer().waste_detection()
