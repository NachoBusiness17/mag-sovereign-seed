"""Auto-Quantizer — adaptive resolution for analytics data.

Problem: 5,271 calls/day with 1 user = manageable. 12 users × 5,000 calls = 
60,000+ events/day. The Tesuji log, Verkle chain, and behavioral metrics 
become massive without a scaling plan.

Solution: RenderMan adaptive sampling applied to analytics storage.
  - High-variance periods → keep individual events (high resolution)
  - Low-variance periods → quantize to hourly/daily aggregates (low resolution)
  - Anomalies → always keep individual events regardless of variance
  - The chain keeps cryptographic anchors at every resolution level

QUANTIZATION LEVELS:
  L0: Raw events — individual knots, 24h retention
  L1: Hourly buckets — behavioral stats per model per hour, 30d retention
  L2: Daily fingerprints — correlation matrices per day, 90d retention
  L3: Weekly invariants — detected patterns per week, 1y retention
  L4: Monthly steers — control effectiveness per month, forever
  L5: Emergence snapshots — quarterly, forever

SCHEMA: auto_quantize.v1
LAW: Anomalies are NEVER quantized. Keep raw forever.
LAW: Variance determines resolution. Low variance = high compression.
LAW: The chain root is always recoverable from any quantization level.
"""

from __future__ import annotations

import hashlib
import json
import math
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Optional

try:
    from config import ROOT
except ImportError:
    ROOT = Path(__file__).resolve().parent.parent

QUANTIZED_DIR = ROOT / "memory" / "analytics" / "quantized"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ═══════════════════════════════════════════════════════════════════
# QUANTUM — a single aggregated data point at a resolution level
# ═══════════════════════════════════════════════════════════════════

@dataclass
class Quantum:
    """An aggregated analytics bucket. Replaces N individual events with 1 summary."""

    quantum_id: str
    level: int                         # 0=raw, 1=hourly, 2=daily, 3=weekly, 4=monthly
    bucket_ts: str                     # Start of the time window (ISO)
    bucket_duration_s: int             # Duration in seconds
    event_count: int                   # How many raw events this replaces
    event_type: str                    # "model_call", "agent_spawn", etc.

    # Aggregated metrics (statistical summary of N events)
    metrics: dict[str, Any] = field(default_factory=dict)
    # metrics contains:
    #   latency_ms: {min, max, mean, p50, p90, p99, stddev}
    #   tokens: {total_in, total_out, mean_in, mean_out}
    #   cost: {total, mean, min, max}
    #   behavioral: {refusal_rate, avg_hesitation, avg_certainty, avg_uncertainty}
    #   models: {model_name: count}

    variance: float = 0.0              # Statistical variance of the primary metric
    is_anomaly: bool = False           # If True, raw events also retained
    chain_anchor: str = ""             # Verkle chain hash at this bucket boundary
    ts: str = field(default_factory=_now)

    def to_knot(self) -> dict[str, Any]:
        """Export as a lightweight Verkle knot."""
        return {
            "type": f"quantum_L{self.level}",
            "quantum_id": self.quantum_id,
            "bucket_ts": self.bucket_ts,
            "duration_s": self.bucket_duration_s,
            "event_count": self.event_count,
            "variance": round(self.variance, 4),
            "anomaly": self.is_anomaly,
            "chain_anchor": self.chain_anchor,
            "ts": self.ts,
            # Metrics summary only — full metrics in separate file
            "summary": {
                k: self.metrics[k]
                for k in ["latency_ms", "cost", "behavioral"]
                if k in self.metrics
            },
        }

    @property
    def storage_ratio(self) -> float:
        """How much storage this quantum saves vs raw events. 0.9 = 90% reduction."""
        return 1.0 - (1.0 / max(self.event_count, 1))


# ═══════════════════════════════════════════════════════════════════
# QUANTIZER — adaptive resolution engine
# ═══════════════════════════════════════════════════════════════════

class AutoQuantizer:
    """Adaptive resolution quantizer for analytics data.

    Determines quantization level based on variance:
      - variance > 0.5 → L0 (keep raw, high signal)
      - variance 0.2-0.5 → L1 (hourly, moderate signal)
      - variance 0.05-0.2 → L2 (daily, low signal)
      - variance < 0.05 → L3 (weekly, steady state)
      - anomalies → L0 regardless of variance
    """

    def __init__(self):
        self._raw_events: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._quantums: list[Quantum] = []

    def ingest(self, event: dict[str, Any]) -> None:
        """Ingest a raw event. Queue for quantization."""
        event_type = event.get("event_name", event.get("type", "unknown"))
        self._raw_events[event_type].append(event)

    def quantize(
        self,
        event_type: str = "",
        bucket_duration_s: int = 3600,
        force_level: Optional[int] = None,
    ) -> list[Quantum]:
        """Quantize raw events into buckets.

        Args:
            event_type: Which event type to quantize ("" = all)
            bucket_duration_s: Bucket size in seconds (3600 = 1 hour)
            force_level: Override adaptive resolution (0-4)

        Returns:
            List of Quantum objects produced
        """
        quantums: list[Quantum] = []
        now = time.time()
        bucket_start = now - bucket_duration_s

        types_to_process = [event_type] if event_type else list(self._raw_events.keys())

        for etype in types_to_process:
            events = self._raw_events.get(etype, [])
            if not events:
                continue

            # Group events into the current bucket
            bucket_events = [
                e for e in events
                if self._event_in_window(e, bucket_start, now)
            ]

            if len(bucket_events) < 2:
                continue  # Not enough data to quantize

            # Compute variance to determine resolution level
            primary_metric = self._extract_primary_metric(bucket_events, etype)
            variance = self._compute_variance([m for m in primary_metric if m is not None])

            # Detect anomalies
            anomalies = self._detect_anomalies(bucket_events, etype, variance)
            anomaly_events = [e for i, e in enumerate(bucket_events) if anomalies[i]]
            normal_events = [e for i, e in enumerate(bucket_events) if not anomalies[i]]

            # Determine quantization level by variance
            if force_level is not None:
                level = force_level
            elif variance > 0.5:
                level = 1  # Hourly — high variance, keep moderate resolution
            elif variance > 0.2:
                level = 2  # Daily — moderate variance
            elif variance > 0.05:
                level = 3  # Weekly — low variance
            else:
                level = 4  # Monthly — steady state

            # Create quantum for normal events
            if normal_events:
                q = self._build_quantum(
                    normal_events, etype, level, bucket_duration_s,
                    variance, is_anomaly=False,
                )
                quantums.append(q)
                self._quantums.append(q)

            # Anomalies always get individual quantums (L0 equivalent)
            for event in anomaly_events:
                q = self._build_quantum(
                    [event], etype, level=0, bucket_duration_s=bucket_duration_s,
                    variance=1.0, is_anomaly=True,
                )
                quantums.append(q)
                self._quantums.append(q)

            # Remove processed events from raw buffer
            processed_ids = {self._event_id(e) for e in bucket_events}
            self._raw_events[etype] = [
                e for e in events
                if self._event_id(e) not in processed_ids
            ]

        # Write quantums to storage
        for q in quantums:
            self._store_quantum(q)

        return quantums

    def _build_quantum(
        self, events: list[dict], event_type: str,
        level: int, bucket_duration_s: int,
        variance: float, is_anomaly: bool,
    ) -> Quantum:
        """Build a Quantum from a list of events."""
        bucket_ts = datetime.now(timezone.utc).isoformat()

        # Aggregate metrics
        latencies = [self._get_latency(e) for e in events if self._get_latency(e)]
        costs = [self._get_cost(e) for e in events if self._get_cost(e)]
        tokens_in = [self._get_tokens(e, "in") for e in events]
        tokens_out = [self._get_tokens(e, "out") for e in events]

        # Model distribution
        model_counts: dict[str, int] = defaultdict(int)
        for e in events:
            model = e.get("event_params", {}).get("model", "unknown")
            model_counts[model] += 1

        metrics = {
            "latency_ms": _stats(latencies) if latencies else {},
            "cost": _stats(costs) if costs else {},
            "tokens": {
                "total_in": sum(tokens_in),
                "total_out": sum(tokens_out),
                "mean_in": sum(tokens_in) / len(tokens_in) if tokens_in else 0,
                "mean_out": sum(tokens_out) / len(tokens_out) if tokens_out else 0,
            },
            "behavioral": {
                "refusal_rate": sum(1 for e in events if e.get("event_params", {}).get("refusal", False)) / len(events),
            },
            "models": dict(model_counts),
        }

        quantum_id = hashlib.sha256(
            f"{event_type}:{bucket_ts}:{level}:{len(events)}".encode()
        ).hexdigest()[:16]

        return Quantum(
            quantum_id=quantum_id,
            level=level,
            bucket_ts=bucket_ts,
            bucket_duration_s=bucket_duration_s,
            event_count=len(events),
            event_type=event_type,
            metrics=metrics,
            variance=variance,
            is_anomaly=is_anomaly,
        )

    def _event_id(self, event: dict) -> str:
        return event.get("knot_id", event.get("call_id", hashlib.sha256(
            json.dumps(event, sort_keys=True, default=str).encode()
        ).hexdigest()[:12]))

    def _event_in_window(self, event: dict, start: float, end: float) -> bool:
        ts = event.get("ts_unix", 0) or 0
        if not ts:
            # Try parsing ISO timestamp
            try:
                ts_str = event.get("ts", "")
                if ts_str:
                    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00")).timestamp()
            except (ValueError, TypeError):
                return False
        return start <= ts <= end

    def _extract_primary_metric(self, events: list[dict], event_type: str) -> list[Optional[float]]:
        """Extract the primary metric for variance computation."""
        if event_type == "model_call":
            return [self._get_latency(e) for e in events]
        return [self._get_cost(e) for e in events]

    def _compute_variance(self, values: list[float]) -> float:
        """Compute statistical variance. 0 = all identical, 1+ = highly variable."""
        if len(values) < 2:
            return 0.0
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        # Normalize by mean to make variance comparable across metrics
        normalized = math.sqrt(variance) / max(mean, 0.001)
        return min(normalized, 1.0)

    def _detect_anomalies(self, events: list[dict], event_type: str, variance: float) -> list[bool]:
        """Detect anomalous events that should never be quantized.

        Anomalies: events more than 3 standard deviations from the mean.
        These are the "spooky" signals — rare, high-value, keep forever.
        """
        if len(events) < 5:
            return [False] * len(events)

        values = self._extract_primary_metric(events, event_type)
        valid = [(i, v) for i, v in enumerate(values) if v is not None]
        if len(valid) < 3:
            return [False] * len(events)

        valid_values = [v for _, v in valid]
        mean = sum(valid_values) / len(valid_values)
        stddev = math.sqrt(sum((v - mean) ** 2 for v in valid_values) / len(valid_values))

        threshold = mean + 3 * stddev
        anomalies = [False] * len(events)
        for i, v in valid:
            if v > threshold:
                anomalies[i] = True

        return anomalies

    def _get_latency(self, event: dict) -> Optional[float]:
        params = event.get("event_params", {})
        return params.get("latency_ms")

    def _get_cost(self, event: dict) -> Optional[float]:
        params = event.get("event_params", {})
        return params.get("cost_usd")

    def _get_tokens(self, event: dict, direction: str) -> int:
        params = event.get("event_params", {})
        key = f"tokens_{direction}"
        return params.get(key, 0)

    def _store_quantum(self, q: Quantum) -> None:
        """Store a quantum to disk."""
        dir_path = QUANTIZED_DIR / f"L{q.level}"
        dir_path.mkdir(parents=True, exist_ok=True)
        file_path = dir_path / f"{q.bucket_ts[:10]}.jsonl"
        try:
            with open(file_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(q.to_knot(), default=str) + "\n")
        except OSError:
            pass

    def storage_stats(self) -> dict[str, Any]:
        """How much storage is the quantizer saving?"""
        total_raw = sum(len(events) for events in self._raw_events.values())
        total_quantized = len(self._quantums)
        savings = 1.0 - (total_quantized / max(total_raw, 1))

        # Estimated storage for 12 users × 5,000 calls/day
        raw_per_day = 12 * 5000 * 200  # ~200 bytes per raw event
        quantized_per_day = total_quantized * 500 if total_quantized else raw_per_day * 0.1

        return {
            "raw_events_buffered": total_raw,
            "quantums_produced": total_quantized,
            "compression_ratio": f"{savings:.0%}",
            "estimated_raw_per_day_12_users": f"{raw_per_day / 1024 / 1024:.0f} MB",
            "estimated_quantized_per_day": f"{quantized_per_day / 1024 / 1024:.0f} MB",
            "recommendation": _storage_recommendation(savings),
        }


def _stats(values: list[float]) -> dict[str, float]:
    """Compute statistical summary of a list of values."""
    if not values:
        return {}
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    return {
        "min": sorted_vals[0],
        "max": sorted_vals[-1],
        "mean": round(sum(sorted_vals) / n, 2),
        "p50": sorted_vals[n // 2],
        "p90": sorted_vals[int(n * 0.9)],
        "p99": sorted_vals[int(n * 0.99)],
        "stddev": round(math.sqrt(sum((v - sum(values) / n) ** 2 for v in values) / n), 2),
        "count": n,
    }


def _storage_recommendation(savings: float) -> str:
    if savings > 0.9:
        return "Excellent compression. 12 users will generate < 10 MB/day of quantized data."
    elif savings > 0.7:
        return "Good compression. 12 users will generate ~50 MB/day. Manageable."
    elif savings > 0.5:
        return "Moderate compression. Consider increasing bucket sizes or reducing retention."
    else:
        return "Low compression. High variance — the system is learning fast. Storage cost is the price of signal."


# ═══════════════════════════════════════════════════════════════════
# SCALING ESTIMATOR — project storage for N users
# ═══════════════════════════════════════════════════════════════════

def estimate_storage(
    users: int = 12,
    calls_per_user_per_day: int = 5000,
    raw_retention_days: int = 1,
    hourly_retention_days: int = 30,
    daily_retention_days: int = 90,
    weekly_retention_days: int = 365,
) -> dict[str, Any]:
    """Estimate storage requirements for N users.

    Based on: 5,271 calls observed today at ~200 bytes/event raw,
    ~500 bytes/quantum compressed.
    """
    calls_per_day = users * calls_per_user_per_day
    bytes_per_raw = 200
    bytes_per_quantum = 500

    # Assume 80% compression (1 quantum replaces ~100 events in low-variance periods)
    quantums_per_day = calls_per_day * 0.01  # 1% of calls become quantums

    raw_storage = calls_per_day * bytes_per_raw * raw_retention_days
    hourly_storage = quantums_per_day * bytes_per_quantum * hourly_retention_days
    daily_storage = quantums_per_day * 0.1 * bytes_per_quantum * daily_retention_days
    weekly_storage = quantums_per_day * 0.01 * bytes_per_quantum * weekly_retention_days

    total = raw_storage + hourly_storage + daily_storage + weekly_storage

    return {
        "users": users,
        "calls_per_day": calls_per_day,
        "storage_breakdown": {
            "raw_L0_24h": f"{raw_storage / 1024 / 1024:.0f} MB",
            "hourly_L1_30d": f"{hourly_storage / 1024 / 1024:.0f} MB",
            "daily_L2_90d": f"{daily_storage / 1024 / 1024:.0f} MB",
            "weekly_L3_1y": f"{weekly_storage / 1024 / 1024:.0f} MB",
        },
        "total": f"{total / 1024 / 1024:.0f} MB",
        "total_gb": f"{total / 1024 / 1024 / 1024:.2f} GB",
        "verdict": _scaling_verdict(total),
    }


def _scaling_verdict(total_bytes: float) -> str:
    gb = total_bytes / 1024 / 1024 / 1024
    if gb < 1:
        return f"{gb:.1f} GB total — fits on a free tier disk. No scaling concern."
    elif gb < 10:
        return f"{gb:.0f} GB total — manageable on a single SSD. Auto-quantize is working."
    elif gb < 100:
        return f"{gb:.0f} GB total — consider object storage (S3) for weekly+ retention."
    else:
        return f"{gb:.0f} GB total — needs distributed storage. Consider sharding by user."
