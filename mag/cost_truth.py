"""Canonical cost view built from the provider usage receipt stream.

This module is deliberately narrower than a billing system.  It answers:

* what the local receipt stream can calculate from token usage;
* what is known to be local/free or quota-backed;
* what cannot be priced without a provider invoice or plan telemetry.

The billable-volume counter is ``cache-miss input + output``.  When a provider
supplies a cache split, the dollar calculation also applies the joined
cache-hit rate to hit tokens.  A raw prompt token count is useful volume
telemetry, but it is not a safe substitute for the split.  All dollar figures
returned here are therefore labelled ``calculated_api_cost_usd`` rather than
``actual`` or ``invoice`` unless an invoice has been joined separately.

Schema: cost_truth.v1
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from functools import lru_cache
from typing import Any, Iterable

import yaml

from config import CONFIGS_DIR, ROOT

SCHEMA = "cost_truth.v1"
USAGE = ROOT / "logs" / "provider_usage.jsonl"
RATES = CONFIGS_DIR / "cost_rates.yaml"

_LEGACY_DEEPSEEK_ALIASES = {
    "deepseek-chat": "deepseek-v4-flash",
    "deepseek-reasoner": "deepseek-v4-pro",
}

_PROVIDER_FREE_OR_CREDIT = {"cerebras", "groq", "nvidia", "together"}
# B2-133 DORMANT GATE (2026-09-26): a provider declared dormant in configs/providers.yaml
# is not priced free-or-credit (mag/doctor.py:607: dormant is a declared state). B2-36 set
# cerebras dormant (card-gated 30-day trial, chat 402 no-credit) and B2-61 set nvidia
# dormant (410 EOL); pricing a dead lane $0 is a cost lie. Honest cost of the gate:
# historical usage rows from before dormancy re-price as `unpriced` (this module's
# first-class unknown state), since no joined rate table carries their models. Operator GO
# flips the flag and the free-or-credit pricing returns with it.
# Receipt: watch/inbox/burn_wave_20260926/B2_133_cerebras_purge_20260926.md
from mag.dormant import dormant_ids as _dormant_provider_ids

_PROVIDER_FREE_OR_CREDIT -= _dormant_provider_ids()
_SUBSCRIPTION_PROVIDER = {
    "glm_coding_lite": "z_ai",
    "zcode": "z_ai",
    "autoclaw": "z_ai",
    "openclaw": "mag_routing",
    "cursor": "cursor",
    "copilot": "copilot",
    "github_copilot": "copilot",
    "chatgpt": "openai",
    "codex": "codex",
    "grok": "xai",
}


@lru_cache(maxsize=1)
def _load_rates() -> dict[str, Any]:
    if not RATES.is_file():
        return {}
    try:
        return yaml.safe_load(RATES.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}


def _parse_ts(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def _model_key(provider: str, model: str) -> str:
    """Normalize the model names seen in provider_usage.jsonl."""
    m = (model or "").strip().lower()
    if m in _LEGACY_DEEPSEEK_ALIASES:
        return _LEGACY_DEEPSEEK_ALIASES[m]
    if m.startswith("deepseek-ai/deepseek-v4-flash"):
        return "deepseek-v4-flash"
    if m.startswith("deepseek/deepseek-v4-flash"):
        return "deepseek-v4-flash"
    if m.startswith("z-ai/"):
        return m.split("/", 1)[1]
    return m


def _is_test_row(row: dict[str, Any]) -> bool:
    provider = str(row.get("provider") or row.get("provider_id") or "").lower()
    return provider == "test_provider" or bool((row.get("meta") or {}).get("test"))


def _row_tokens(row: dict[str, Any]) -> dict[str, int | bool]:
    """Return real volume and billable tokens without trusting ``tokens`` blindly."""
    prompt = max(0, int(row.get("prompt_tokens") or 0))
    hit = max(0, int(row.get("cache_hit_tokens") or 0))
    miss_raw = row.get("cache_miss_tokens")
    miss = max(0, int(miss_raw or 0))
    completion = max(0, int(row.get("completion_tokens") or 0))

    # The writer emits a split whenever it can.  Legacy/test fixtures may
    # omit it; in that case the safe accounting fallback is all prompt input
    # treated as a miss, never silently as a hit.
    split = bool(hit or miss) or ("cache_hit_tokens" in row and "cache_miss_tokens" in row and prompt == 0)
    if not split:
        miss = prompt
    input_tokens = hit + miss if split else prompt
    return {
        "prompt_tokens": prompt,
        "cache_hit_tokens": hit if split else 0,
        "cache_miss_tokens": miss,
        "completion_tokens": completion,
        "billable_tokens": miss + completion,
        "split_observed": split,
        "input_tokens": input_tokens,
    }


def _deepseek_rates(at: datetime | None, model_cfg: dict[str, Any]) -> tuple[dict[str, float], str]:
    """Select the official DeepSeek peak/off-peak schedule for a timestamp."""
    peak = False
    if at is not None and at.weekday() < 5:
        peak = at.hour in (1, 2, 3, 6, 7, 8, 9)
    schedule = model_cfg.get("schedule") or {}
    key = "peak" if peak else "offpeak"
    selected = schedule.get(key) or schedule.get("offpeak") or {}
    return (
        {
            "cache_hit_per_m": float(selected.get("cache_hit_per_m") or 0),
            "cache_miss_per_m": float(selected.get("cache_miss_per_m") or 0),
            "output_per_m": float(selected.get("output_per_m") or 0),
        },
        key,
    )


def _lookup_rate(provider: str, model: str, at: datetime | None) -> dict[str, Any]:
    """Resolve a pricing state.  Unknown is a first-class result."""
    p = (provider or "").strip().lower()
    raw_model = (model or "").strip().lower()
    model_key = _model_key(p, raw_model)
    if p == "ollama" or p == "mlx-cluster" or p == "saelis":
        return {"state": "local", "source": "local_runtime", "model": model_key}
    if p == "openrouter" and raw_model.endswith(":free"):
        return {"state": "free_or_quota", "source": "openrouter_free_model", "model": model_key}
    if p in _PROVIDER_FREE_OR_CREDIT:
        return {"state": "free_or_quota", "source": "provider_quota_or_credit", "model": model_key}

    rates = _load_rates().get("model_rates") or {}
    cfg = rates.get(model_key)
    if isinstance(cfg, dict):
        # Z.ai coding-plan keys are not the same billing surface as the public
        # PaaS API.  Keep plan calls out of a fake API-dollar total.
        if p in {"z_ai", "z_ai4"} and cfg.get("plan_surface_unknown"):
            return {
                "state": "unpriced",
                "source": "zai_coding_plan_not_metered",
                "model": model_key,
                "reason": "coding-plan usage is not exposed in provider_usage.jsonl",
            }
        if cfg.get("free"):
            return {"state": "free_or_quota", "source": cfg.get("source") or "official_free_rate", "model": model_key}
        provider_matches = (
            cfg.get("provider") == p
            or (cfg.get("provider") == "deepseek" and p in {"deepseek", "deepseek_overmind"})
            or (cfg.get("provider") == "z_ai" and p.startswith("z_ai"))
        )
        if cfg.get("provider") and not provider_matches:
            # A model's public rate does not transfer across aggregators.
            return {
                "state": "unpriced",
                "source": "aggregator_model_rate_missing",
                "model": model_key,
                "reason": "provider-specific pass-through price not joined",
            }
        if cfg.get("schedule"):
            selected, schedule_name = _deepseek_rates(at, cfg)
        else:
            rate_cfg = cfg.get("rates") or cfg
            selected = {
                "cache_hit_per_m": float(rate_cfg.get("cache_hit_per_m") or 0),
                "cache_miss_per_m": float(rate_cfg.get("cache_miss_per_m") or 0),
                "output_per_m": float(rate_cfg.get("output_per_m") or 0),
            }
            schedule_name = "standard"
        return {
            "state": "exact_rate",
            "source": cfg.get("source") or "configured_model_rate",
            "model": model_key,
            "rates": selected,
            "schedule": schedule_name,
        }
    return {
        "state": "unpriced",
        "source": "no_joined_model_rate",
        "model": model_key,
        "reason": "provider/model is present in receipts but has no authoritative local rate",
    }


def price_tokens(
    provider: str,
    model: str,
    *,
    cache_hit_tokens: int = 0,
    cache_miss_tokens: int = 0,
    completion_tokens: int = 0,
    at: datetime | None = None,
) -> dict[str, Any]:
    """Price one receipt's billable token split, preserving its evidence state."""
    hit = max(0, int(cache_hit_tokens or 0))
    miss = max(0, int(cache_miss_tokens or 0))
    completion = max(0, int(completion_tokens or 0))
    lookup = _lookup_rate(provider, model, at)
    out: dict[str, Any] = {
        "state": lookup["state"],
        "source": lookup.get("source"),
        "model": lookup.get("model") or model,
        "schedule": lookup.get("schedule"),
        "billable_tokens": miss + completion,
        "cache_hit_tokens": hit,
        "cache_miss_tokens": miss,
        "completion_tokens": completion,
        "calculated_usd": 0.0,
    }
    if lookup["state"] == "exact_rate":
        rate = lookup["rates"]
        out["calculated_usd"] = round(
            hit * rate["cache_hit_per_m"] / 1_000_000
            + miss * rate["cache_miss_per_m"] / 1_000_000
            + completion * rate["output_per_m"] / 1_000_000,
            8,
        )
        out["rate_per_m"] = rate
    if lookup.get("reason"):
        out["reason"] = lookup["reason"]
    return out


def _state_merge(states: set[str]) -> str:
    if not states:
        return "no_usage"
    if len(states) == 1:
        return next(iter(states))
    return "mixed"


def aggregate_rows(rows: Iterable[dict[str, Any]], *, fallback_model: str = "") -> dict[str, Any]:
    """Aggregate a bounded row set.  Pure apart from loading the rate catalog."""
    totals: dict[str, Any] = {
        "calls": 0,
        "ok_calls": 0,
        "failed_calls": 0,
        "input_tokens": 0,
        "prompt_tokens": 0,
        "cache_hit_tokens": 0,
        "cache_miss_tokens": 0,
        "completion_tokens": 0,
        "billable_tokens": 0,
        "split_rows": 0,
        "token_rows": 0,
        "accounted_calls": 0,
        "priced_calls": 0,
        "free_or_quota_calls": 0,
        "unpriced_calls": 0,
        "unpriced_billable_tokens": 0,
        "calculated_api_cost_usd": 0.0,
    }
    by_provider: dict[str, dict[str, Any]] = {}
    by_model: dict[str, dict[str, Any]] = {}
    for row in rows:
        if _is_test_row(row):
            continue
        provider = str(row.get("provider") or row.get("provider_id") or "unknown")
        model = str(row.get("model") or fallback_model or "unknown")
        parts = _row_tokens(row)
        calls = max(1, int(row.get("calls") or 1))
        billable = int(parts["billable_tokens"])
        has_tokens = bool(int(parts["input_tokens"]) or int(parts["completion_tokens"]))
        if not has_tokens and calls <= 0:
            continue
        at = _parse_ts(row.get("ts"))
        priced = price_tokens(
            provider,
            model,
            cache_hit_tokens=int(parts["cache_hit_tokens"]),
            cache_miss_tokens=int(parts["cache_miss_tokens"]),
            completion_tokens=int(parts["completion_tokens"]),
            at=at,
        )
        state = str(priced.get("state") or "unpriced")
        totals["calls"] += calls
        totals["ok_calls"] += calls if bool(row.get("ok", True)) else 0
        totals["failed_calls"] += 0 if bool(row.get("ok", True)) else calls
        totals["input_tokens"] += int(parts["input_tokens"])
        totals["prompt_tokens"] += int(parts["prompt_tokens"])
        totals["cache_hit_tokens"] += int(parts["cache_hit_tokens"])
        totals["cache_miss_tokens"] += int(parts["cache_miss_tokens"])
        totals["completion_tokens"] += int(parts["completion_tokens"])
        totals["billable_tokens"] += billable
        totals["token_rows"] += 1 if has_tokens else 0
        totals["split_rows"] += 1 if bool(parts["split_observed"]) and has_tokens else 0
        if state in {"exact_rate", "local", "free_or_quota"}:
            totals["accounted_calls"] += calls
        if state == "exact_rate":
            totals["priced_calls"] += calls
        if state in {"local", "free_or_quota"}:
            totals["free_or_quota_calls"] += calls
        if state == "unpriced":
            totals["unpriced_calls"] += calls
            totals["unpriced_billable_tokens"] += billable
        totals["calculated_api_cost_usd"] += float(priced.get("calculated_usd") or 0)

        for bucket, key in ((by_provider, provider), (by_model, f"{provider}/{model}")):
            item = bucket.setdefault(
                key,
                {
                    "provider": provider,
                    "model": model if bucket is by_model else None,
                    "calls": 0,
                    "ok_calls": 0,
                    "failed_calls": 0,
                    "input_tokens": 0,
                    "cache_hit_tokens": 0,
                    "cache_miss_tokens": 0,
                    "completion_tokens": 0,
                    "billable_tokens": 0,
                    "calculated_api_cost_usd": 0.0,
                    "states": set(),
                    "accounted_calls": 0,
                    "priced_calls": 0,
                    "unpriced_calls": 0,
                },
            )
            item["calls"] += calls
            item["ok_calls"] += calls if bool(row.get("ok", True)) else 0
            item["failed_calls"] += 0 if bool(row.get("ok", True)) else calls
            item["input_tokens"] += int(parts["input_tokens"])
            item["cache_hit_tokens"] += int(parts["cache_hit_tokens"])
            item["cache_miss_tokens"] += int(parts["cache_miss_tokens"])
            item["completion_tokens"] += int(parts["completion_tokens"])
            item["billable_tokens"] += billable
            item["calculated_api_cost_usd"] += float(priced.get("calculated_usd") or 0)
            item["states"].add(state)
            if state in {"exact_rate", "local", "free_or_quota"}:
                item["accounted_calls"] += calls
            if state == "exact_rate":
                item["priced_calls"] += calls
            if state == "unpriced":
                item["unpriced_calls"] += calls

    def clean(item: dict[str, Any], *, provider_bucket: bool = False) -> dict[str, Any]:
        item = dict(item)
        states = item.pop("states", set())
        item["cost_state"] = _state_merge(states)
        item["calculated_api_cost_usd"] = round(float(item.get("calculated_api_cost_usd") or 0), 6)
        billable = int(item.get("billable_tokens") or 0)
        input_tokens = int(item.get("cache_hit_tokens") or 0) + int(item.get("cache_miss_tokens") or 0)
        item["cache_hit_ratio"] = round(
            int(item.get("cache_hit_tokens") or 0) / max(1, input_tokens), 4
        ) if input_tokens else None
        if provider_bucket:
            item["provider"] = next(iter([item.get("provider")]))
            item.pop("model", None)
        return item

    totals["calculated_api_cost_usd"] = round(float(totals["calculated_api_cost_usd"]), 6)
    totals["cache_hit_ratio"] = round(
        totals["cache_hit_tokens"] / max(1, totals["cache_hit_tokens"] + totals["cache_miss_tokens"]),
        4,
    ) if totals["input_tokens"] else None
    totals["split_coverage"] = round(totals["split_rows"] / max(1, totals["token_rows"]), 4)
    totals["pricing_coverage"] = round(
        (totals["billable_tokens"] - totals["unpriced_billable_tokens"])
        / max(1, totals["billable_tokens"]),
        4,
    ) if totals["billable_tokens"] else 1.0
    return {
        **totals,
        "by_provider": [clean(v, provider_bucket=True) for v in sorted(by_provider.values(), key=lambda x: -x["calls"])],
        "by_model": [clean(v) for v in sorted(by_model.values(), key=lambda x: -x["calls"])],
    }


def _read_usage() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    invalid = 0
    if USAGE.is_file():
        try:
            for line in USAGE.read_text(encoding="utf-8", errors="replace").splitlines():
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except (json.JSONDecodeError, TypeError):
                    invalid += 1
                    continue
                if isinstance(row, dict):
                    rows.append(row)
        except OSError:
            pass
    times = [_parse_ts(r.get("ts")) for r in rows]
    valid_times = [t for t in times if t is not None]
    return rows, {
        "rows_read": len(rows),
        "invalid_rows": invalid,
        "test_rows_excluded": sum(1 for r in rows if _is_test_row(r)),
        "earliest_ts": min(valid_times).isoformat() if valid_times else None,
        "latest_ts": max(valid_times).isoformat() if valid_times else None,
        "source": str(USAGE.relative_to(ROOT)).replace("\\", "/"),
        "source_bytes": USAGE.stat().st_size if USAGE.is_file() else 0,
    }


def _window(rows: list[dict[str, Any]], *, start: datetime | None = None, end: datetime | None = None) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        ts = _parse_ts(row.get("ts"))
        if start is not None and (ts is None or ts < start):
            continue
        if end is not None and (ts is None or ts >= end):
            continue
        out.append(row)
    return out


def _commitments(usage: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Expose declared fixed surfaces without folding guesses into API spend."""
    try:
        from mag.subscriptions import SUBSCRIPTIONS
    except Exception:
        return []
    out = []
    for row in SUBSCRIPTIONS:
        sid = str(row.get("id") or "")
        provider = _SUBSCRIPTION_PROVIDER.get(sid, sid)
        calls = int((usage.get(provider) or {}).get("calls") or 0)
        quantity = max(1, int(row.get("quantity") or 1))
        unit_monthly = row.get("monthly_usd")
        floor_unit = row.get("published_floor_usd")
        try:
            monthly_usd = round(float(unit_monthly) * quantity, 2) if unit_monthly is not None else None
        except (TypeError, ValueError):
            monthly_usd = None
        try:
            floor_monthly_usd = round(float(floor_unit) * quantity, 2) if floor_unit is not None else None
        except (TypeError, ValueError):
            floor_monthly_usd = None
        candidates = row.get("plan_options") if isinstance(row.get("plan_options"), dict) else {}
        candidate_totals = {}
        for plan, amount in candidates.items():
            try:
                candidate_totals[str(plan)] = round(float(amount) * quantity, 2)
            except (TypeError, ValueError):
                continue
        out.append(
            {
                "id": sid,
                "name": row.get("name") or sid,
                "type": row.get("type") or "unknown",
                "declared_monthly_cost": row.get("cost_mo") or "unknown",
                "quantity": quantity,
                "monthly_cost_usd": monthly_usd,
                "published_floor_monthly_usd": floor_monthly_usd,
                "price_status": row.get("price_status") or ("declared" if monthly_usd is not None else "unknown"),
                "billing_period": row.get("billing_period") or "monthly",
                "plan_options_monthly_usd": candidate_totals,
                "source_url": row.get("source_url"),
                "recurring": bool(row.get("recurring")),
                "verdict": row.get("verdict") or "review",
                "metered_provider": provider,
                "metered_calls_all_time": calls,
                "included_in_api_total": False,
                "basis": "operator_declared_or_unknown",
            }
        )
    return out


def _recurring_summary(commitments: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize recurring seats without turning plan floors into fake invoices."""
    recurring = [row for row in commitments if row.get("recurring")]
    confirmed = round(sum(float(row["monthly_cost_usd"]) for row in recurring if row.get("monthly_cost_usd") is not None), 2)
    unconfirmed_floor = round(sum(float(row["published_floor_monthly_usd"]) for row in recurring
                                  if row.get("monthly_cost_usd") is None and row.get("published_floor_monthly_usd") is not None), 2)
    minimum = round(confirmed + unconfirmed_floor, 2)
    unknown = [row["id"] for row in recurring if row.get("monthly_cost_usd") is None]
    return {
        "currency": "USD",
        "confirmed_monthly_usd": confirmed,
        "unconfirmed_published_floor_monthly_usd": unconfirmed_floor,
        "published_floor_monthly_usd": minimum,
        "minimum_monthly_usd": minimum,
        "needs_confirmation_count": len(unknown),
        "needs_confirmation_ids": unknown,
        "items": recurring,
        "invoice_joined": False,
        "basis": "operator_declared_amounts_plus_official_published_floors; verify against invoices",
    }


def snapshot(*, now: datetime | None = None) -> dict[str, Any]:
    """Return the dashboard-ready cost truth snapshot."""
    now = now or datetime.now(timezone.utc)
    try:
        from mag.off_hours import queue_status as _compute_schedule
        compute_schedule = _compute_schedule()
    except Exception as exc:
        compute_schedule = {"schema": "off_hours.v1", "ok": False, "error": str(exc)[:160]}
    try:
        from mag.vast_cost import snapshot as _vast_snapshot
        vast = _vast_snapshot(now=now)
    except Exception as exc:
        vast = {"schema": "vast_cost.v1", "reachable": False, "error": str(exc)[:160]}
    rows, quality = _read_usage()
    all_rows = [r for r in rows if not _is_test_row(r)]
    providers = {}
    for r in all_rows:
        p = str(r.get("provider") or r.get("provider_id") or "unknown")
        item = providers.setdefault(p, {"calls": 0})
        item["calls"] += max(1, int(r.get("calls") or 1))

    windows = {
        "today": (now.replace(hour=0, minute=0, second=0, microsecond=0), now + timedelta(seconds=1)),
        "last_7_days": (now - timedelta(days=7), now + timedelta(seconds=1)),
        "last_30_days": (now - timedelta(days=30), now + timedelta(seconds=1)),
        "all_logged": (None, None),
    }
    period_out = {}
    for name, (start, end) in windows.items():
        agg = aggregate_rows(_window(rows, start=start, end=end))
        period_out[name] = agg

    quality["rows_included"] = len(all_rows)
    quality["unpriced_rows_all_logged"] = sum(
        1 for row in all_rows if int(_row_tokens(row)["billable_tokens"]) > 0
        and _lookup_rate(str(row.get("provider") or ""), str(row.get("model") or ""), _parse_ts(row.get("ts"))).get("state") == "unpriced"
    )
    all_period = period_out["all_logged"]
    commitments = _commitments(providers)
    recurring = _recurring_summary(commitments)
    return {
        "ok": True,
        "schema": SCHEMA,
        "as_of": now.isoformat(),
        "accounting": {
            "currency": "USD",
            "calculated_api_cost_usd": "receipt token counts × joined model/list rate",
            "billable_input_rule": "cache-miss input + completion output",
            "invoice_joined": False,
            "subscription_costs_included": False,
            "vast_charges_separate": True,
            "recurring_commitments_tracked": True,
            "local_energy_included": False,
        },
        "periods": period_out,
        "providers": all_period["by_provider"],
        "models": all_period["by_model"],
        "quality": quality,
        "commitments": commitments,
        "recurring": recurring,
        "compute_schedule": compute_schedule,
        "vast": vast,
        "outcome_linkage": {
            "status": "partial",
            "note": "Provider receipts are not yet joined consistently to verified outcomes; cost per verified outcome is withheld rather than fabricated.",
        },
        "pricing_sources": sorted(
            {
                str((cfg or {}).get("source"))
                for cfg in ((_load_rates().get("model_rates") or {}).values())
                if isinstance(cfg, dict) and cfg.get("source")
            }
        ),
        "notes": [
            "Calculated API cost is not an invoice and excludes plan usage not visible to Mag.",
            "Local Ollama is $0 API cost here; electricity and hardware depreciation are not measured.",
            "Unpriced rows remain visible with their billable token volume so missing instrumentation cannot masquerade as free.",
        ],
    }


if __name__ == "__main__":
    print(json.dumps(snapshot(), indent=2, ensure_ascii=False, default=str))
