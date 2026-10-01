"""Read-only Vast.ai cost and instance receipts.

Vast has two different truths: charge records (what was billed) and current
instances (what may still be accruing). This module fetches both with a
read-only API key, caches normalized receipts locally, and never creates,
starts, stops, or destroys an instance.

Schema: vast_cost.v1
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from config import ROOT

SCHEMA = "vast_cost.v1"
CHARGES_URL = "https://console.vast.ai/api/v0/charges/"
INSTANCES_URL = "https://console.vast.ai/api/v1/instances/"
USER_URL = "https://console.vast.ai/api/v0/users/current/"
CHARGES_LEDGER = ROOT / "memory" / "cost" / "vast_charges.jsonl"
INSTANCES_CACHE = ROOT / "memory" / "cost" / "vast_instances.json"
MAX_PAGES = 20


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _key() -> str:
    try:
        from mag.vast_launcher import _load_vast_key
        return _load_vast_key()
    except Exception:
        return ""


def _get(url: str, key: str) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        headers={"Authorization": "Bearer " + key, "Accept": "application/json"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as response:
            data = json.loads(response.read().decode("utf-8", errors="replace"))
        return data if isinstance(data, dict) else {"results": data}
    except urllib.error.HTTPError as exc:
        return {"ok": False, "error": f"HTTP {exc.code}", "status_code": exc.code}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": type(exc).__name__ + ": " + str(exc)[:180]}


def _epoch(value: Any) -> float | None:
    try:
        number = float(value)
        return number if number > 0 else None
    except (TypeError, ValueError):
        return None


def _charge_key(row: dict[str, Any]) -> str:
    return "|".join(str(row.get(k) or "") for k in ("type", "source", "start", "end", "amount"))


def _normalize_charge(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "source": str(row.get("source") or ""),
        "type": str(row.get("type") or "unknown"),
        "start": _epoch(row.get("start")),
        "end": _epoch(row.get("end")),
        "amount_usd": round(float(row.get("amount") or 0), 8),
        "description": str(row.get("description") or "")[:300],
        "metadata": row.get("metadata") if isinstance(row.get("metadata"), dict) else {},
        "items": row.get("items") if isinstance(row.get("items"), list) else [],
        "fetched_at": _iso(_now()),
    }


def _save_instances(raw: list[dict[str, Any]], fetched_at: str) -> None:
    safe: list[dict[str, Any]] = []
    for row in raw:
        # Do not persist network addresses, tokens, or arbitrary environment fields.
        safe.append({
            "id": row.get("id"),
            "actual_status": row.get("actual_status"),
            "intended_status": row.get("intended_status"),
            "cur_state": row.get("cur_state"),
            "label": str(row.get("label") or "")[:200],
            "gpu_name": row.get("gpu_name"),
            "num_gpus": row.get("num_gpus"),
            "dph_base": row.get("dph_base"),
            "dph_total": row.get("dph_total"),
            "storage_total_cost": row.get("storage_total_cost"),
            "storage_cost": row.get("storage_cost"),
            "start_date": row.get("start_date"),
            "end_date": row.get("end_date"),
            "duration": row.get("duration"),
            "credit_balance": row.get("credit_balance"),
            "credit_discount": row.get("credit_discount"),
        })
    INSTANCES_CACHE.parent.mkdir(parents=True, exist_ok=True)
    INSTANCES_CACHE.write_text(json.dumps({
        "schema": SCHEMA, "fetched_at": fetched_at, "instances": safe,
    }, ensure_ascii=False, indent=2), encoding="utf-8")


def sync(*, days: int = 30, include_instances: bool = True) -> dict[str, Any]:
    """Pull charges/instances using billing_read + instance_read only."""
    key = _key()
    if not key:
        return {
            "ok": False, "schema": SCHEMA, "reachable": False,
            "error": "no VASTAI_API_KEY / VAST_API_KEY in env or .env",
            "note": "Set a scoped Vast key with billing_read and instance_read; no spend action is performed.",
        }
    now = _now()
    since = now - timedelta(days=max(1, min(int(days), 3650)))
    filters = {
        "day": {"gte": int(since.timestamp()), "lte": int(now.timestamp())},
        "type": {"in": ["instance", "volume", "serverless"]},
    }
    params: dict[str, Any] = {
        "select_filters": json.dumps(filters, separators=(",", ":")),
        "format": "table", "latest_first": "true", "limit": "100",
    }
    charges: list[dict[str, Any]] = []
    errors: list[str] = []
    for _ in range(MAX_PAGES):
        url = CHARGES_URL + "?" + urllib.parse.urlencode(params)
        page = _get(url, key)
        if page.get("ok") is False:
            errors.append("charges: " + str(page.get("error") or "unavailable"))
            break
        raw = page.get("results") if isinstance(page.get("results"), list) else []
        charges.extend(_normalize_charge(x) for x in raw if isinstance(x, dict))
        token = page.get("next_token")
        if not token:
            break
        params["after_token"] = str(token)

    existing: set[str] = set()
    if CHARGES_LEDGER.is_file():
        for line in CHARGES_LEDGER.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                row = json.loads(line)
                existing.add(_charge_key(row))
            except (json.JSONDecodeError, TypeError):
                continue
    appended = 0
    if charges:
        CHARGES_LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with CHARGES_LEDGER.open("a", encoding="utf-8") as fh:
            for row in charges:
                key_row = _charge_key(row)
                if key_row in existing:
                    continue
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
                existing.add(key_row)
                appended += 1

    instances: list[dict[str, Any]] = []
    if include_instances:
        page = _get(INSTANCES_URL + "?limit=25", key)
        if page.get("ok") is False:
            errors.append("instances: " + str(page.get("error") or "unavailable"))
        else:
            instances = [x for x in (page.get("instances") or []) if isinstance(x, dict)]
            _save_instances(instances, _iso(now))
    user = _get(USER_URL, key)
    balance = None
    if user.get("ok") is not False:
        account = user.get("user") if isinstance(user.get("user"), dict) else user
        balance = account.get("balance", account.get("credit")) if isinstance(account, dict) else None
    return {
        "ok": not errors,
        "schema": SCHEMA,
        "reachable": True,
        "fetched_at": _iso(now),
        "days": days,
        "charges_fetched": len(charges),
        "charges_appended": appended,
        "instances_fetched": len(instances),
        "balance": balance,
        "errors": errors,
        "ledger": str(CHARGES_LEDGER.relative_to(ROOT)).replace("\\", "/"),
        "instances_cache": str(INSTANCES_CACHE.relative_to(ROOT)).replace("\\", "/"),
        "note": "Read-only Vast billing/instance sync; no instance lifecycle action.",
    }


def _load_charges() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not CHARGES_LEDGER.is_file():
        return rows
    for line in CHARGES_LEDGER.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            row = json.loads(line)
            if isinstance(row, dict):
                rows.append(row)
        except json.JSONDecodeError:
            continue
    return rows


def _load_instances() -> dict[str, Any]:
    if not INSTANCES_CACHE.is_file():
        return {"fetched_at": None, "instances": []}
    try:
        row = json.loads(INSTANCES_CACHE.read_text(encoding="utf-8"))
        return row if isinstance(row, dict) else {"fetched_at": None, "instances": []}
    except (OSError, json.JSONDecodeError):
        return {"fetched_at": None, "instances": []}


def _leaves(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in items:
        children = item.get("items") if isinstance(item.get("items"), list) else []
        if children:
            out.extend(_leaves([x for x in children if isinstance(x, dict)]))
        else:
            out.append(item)
    return out


def _overlap_amount(row: dict[str, Any], start: float | None, end: float | None) -> float:
    amount = float(row.get("amount_usd") or row.get("amount") or 0)
    if start is None or end is None:
        return amount
    r_start = _epoch(row.get("start"))
    r_end = _epoch(row.get("end")) or r_start
    if r_start is None or r_end is None or r_end <= r_start:
        return amount if r_start is not None and start <= r_start < end else 0.0
    overlap = max(0.0, min(r_end, end) - max(r_start, start))
    return amount * overlap / (r_end - r_start) if overlap else 0.0


def _period(rows: list[dict[str, Any]], *, start: float | None, end: float | None) -> dict[str, Any]:
    total = gpu = storage = bandwidth = 0.0
    hours = 0.0
    by_instance: dict[str, float] = {}
    for row in rows:
        amount = _overlap_amount(row, start, end)
        if amount <= 0:
            continue
        total += amount
        source = str(row.get("source") or "unknown")
        by_instance[source] = round(by_instance.get(source, 0.0) + amount, 6)
        leaves = _leaves(row.get("items") or [])
        if not leaves:
            if row.get("type") == "instance":
                gpu += amount
            continue
        for item in leaves:
            # Vast has emitted both amount and amount_usd in different charge
            # shapes. Prefer the child amount, never fall back to the parent
            # total when a child simply uses the alternate field name.
            child_amount = item.get("amount_usd")
            if child_amount is None:
                child_amount = item.get("amount")
            item_amount = _overlap_amount({**row, "amount_usd": child_amount}, start, end)
            kind = str(item.get("type") or "").lower()
            if kind in {"gpu", "compute"}:
                gpu += item_amount
            elif kind in {"storage", "disk", "volume"}:
                storage += item_amount
            elif kind in {"bandwidth", "bwu", "bwd", "network"}:
                bandwidth += item_amount
            match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s+hours?", str(item.get("description") or ""), re.I)
            if match and kind in {"gpu", "compute"}:
                hours += float(match.group(1))
    return {
        "actual_charges_usd": round(total, 6),
        "gpu_charges_usd": round(gpu, 6),
        "storage_charges_usd": round(storage, 6),
        "bandwidth_charges_usd": round(bandwidth, 6),
        "gpu_hours": round(hours, 4),
        "by_instance": [{"source": k, "amount_usd": v} for k, v in sorted(by_instance.items(), key=lambda x: -x[1])],
    }


def snapshot(*, now: datetime | None = None) -> dict[str, Any]:
    now = now or _now()
    rows = _load_charges()
    # Keep "today" a calendar day rather than a rolling 24-hour window. This
    # makes the Vast meter agree with the main cost-truth dashboard.
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    windows = {"today": midnight, "last_7_days": now - timedelta(days=7), "last_30_days": now - timedelta(days=30), "all_logged": None}
    periods = {}
    for name, start in windows.items():
        periods[name] = _period(rows, start=start.timestamp() if start else None, end=now.timestamp() if start else None)
    cache = _load_instances()
    instances = cache.get("instances") if isinstance(cache.get("instances"), list) else []
    active = [x for x in instances if str(x.get("actual_status") or "").lower() in {"running", "frozen", "loading"}]
    hourly = sum(float(x.get("dph_total") or 0) for x in active)
    return {
        "schema": SCHEMA,
        "source": "vast_readonly_charge_cache",
        "synced_at": cache.get("fetched_at"),
        "charges_logged": len(rows),
        "periods": periods,
        "instances": {
            "cached": len(instances),
            "active_cached": len(active),
            "estimated_active_hourly_usd": round(hourly, 6),
            "rows": active[:20],
        },
        "reachable": bool(rows or cache.get("fetched_at")),
        "invoice_joined": False,
        "note": "Actual Vast charge receipts are shown from the read-only sync cache; current dph is an exposure estimate, not a posted charge.",
        "sources": [CHARGES_URL, INSTANCES_URL],
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(prog="vast-cost")
    parser.add_argument("cmd", nargs="?", default="status", choices=["status", "sync"])
    parser.add_argument("--days", type=int, default=30)
    args = parser.parse_args()
    result = sync(days=args.days) if args.cmd == "sync" else snapshot()
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
