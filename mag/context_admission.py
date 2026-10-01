"""Context admission and pressure receipts.

This is the small missing rib between context assembly and model dispatch.  It
does not call a model and it never decides what the user meant; it only answers
whether the next prompt fits the configured window and leaves a bounded receipt
when pressure or recovery occurs.

Schema: context_admission.v1
Law: a prompt is admitted before dispatch, not after the provider rejects it.
Law: pressure recovery is durable evidence, not a console claim.
"""
from __future__ import annotations

import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA = "context_admission.v1"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def assess(
    *,
    estimated_tokens: int,
    context_window: int,
    repack_ratio: float = 0.85,
    tool_schema_reserve: int = 2500,
    reply_reserve: int = 2500,
    reason: str = "preflight",
    provider: str = "",
    session_id: str = "",
    repacks: int = 0,
    max_repacks: int = 0,
) -> dict[str, Any]:
    """Return a deterministic admission decision without touching the network."""
    window = max(4_000, int(context_window or 0))
    ratio = min(0.90, max(0.35, float(repack_ratio or 0.85)))
    reserve = max(0, int(tool_schema_reserve)) + max(0, int(reply_reserve))
    usable = max(4_000, window - reserve)
    threshold = max(4_000, int(usable * ratio))
    est = max(0, int(estimated_tokens))
    if est > window:
        band = "black"
    elif est > threshold:
        band = "red"
    elif est > int(threshold * 0.90):
        band = "amber"
    else:
        band = "green"
    return {
        "schema": SCHEMA,
        "ts": _now(),
        "provider": provider,
        "session_id": session_id,
        "reason": reason,
        "estimated_tokens": est,
        "context_window": window,
        "usable_budget": usable,
        "threshold": threshold,
        "reserve_tokens": reserve,
        "repack_ratio": ratio,
        "band": band,
        "allowed": est <= threshold,
        "repacks": int(repacks),
        "max_repacks": int(max_repacks),
    }


def write_receipt(root: str | Path, receipt: dict[str, Any]) -> str:
    """Append a pressure/recovery receipt and return its path.

    The record intentionally contains measurements and identifiers only; no
    prompt or tool body is copied into the telemetry surface.
    """
    base = Path(root)
    path = base / "memory" / "runs" / "context_admission" / "receipts.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    clean = dict(receipt)
    clean.setdefault("schema", SCHEMA)
    clean.setdefault("ts", _now())
    fingerprint = hashlib.sha256(
        json.dumps(clean, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()[:16]
    clean["receipt_id"] = f"ctx-{fingerprint}"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(clean, ensure_ascii=False, default=str) + "\n")
    return str(path)


def safe_write_receipt(root: str | Path, receipt: dict[str, Any]) -> str | None:
    """Best-effort evidence: telemetry failure must not fail a user turn."""
    try:
        return write_receipt(root, receipt)
    except OSError:
        return None

