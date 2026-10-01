"""Verkle Event Bus — Redis Pub/Sub ↔ Verkle knot bridge.

Every system event is both:
  1. Published to Redis (for real-time subscribers — Ghost, LeakDetector, Spider)
  2. Folded as a Verkle knot (for audit, replay, cross-container shared state)

Channels:
  mag:sense      — Ghost sense() cycle completed (FKB, spider, verkle, leak state)
  mag:cycle      — Ghost steer deployed or skipped
  mag:copilot    — Copilot task result (spawned, completed, failed)
  mag:leak       — Leak detected (canary breach, entropy, burst, collusion)
  mag:task       — New task requested (→ orchestrator picks up)
  mag:verkle     — New Verkle knot appended (→ all agents sync)
  mag:scrum      — Scrum checkpoint (ship/research/done classification)

Graceful degradation: if Redis is down, publish() is a no-op and subscribe()
falls back to file polling. No crash, no error — just quieter.

Schema: verkle_bus.v1
"""

from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator, Callable

try:
    from config import ROOT
except ImportError:
    ROOT = Path(__file__).resolve().parent.parent

# ── Channel constants ─────────────────────────────────────────────
CH_SENSE     = "mag:sense"
CH_CYCLE     = "mag:cycle"
CH_COPILOT   = "mag:copilot"
CH_LEAK      = "mag:leak"
CH_TASK      = "mag:task"
CH_VERKLE    = "mag:verkle"
CH_SCRUM     = "mag:scrum"
CH_BARD      = "mag:bard"
CH_FLARE     = "mag:flare"
CH_RIB       = "mag:rib"      # RIB/steer instruction-layer fold/publish (rib_bus)
CH_FACT      = "mag:fact"     # FACT fold/publish (fact_bus, 5-W surfacing)

ALL_CHANNELS = [CH_SENSE, CH_CYCLE, CH_COPILOT, CH_LEAK, CH_TASK, CH_VERKLE, CH_SCRUM,
                CH_BARD, CH_FLARE, CH_RIB, CH_FACT]

# ── Redis connection ──────────────────────────────────────────────

_redis = None
_redis_ok = False


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def connect_redis() -> bool:
    """Connect to Redis. Returns True if connected, False if unavailable."""
    global _redis, _redis_ok
    if _redis_ok:
        return True

    try:
        import redis.asyncio as aioredis
        host = os.environ.get("REDIS_HOST", "redis")
        port = int(os.environ.get("REDIS_PORT", "6379"))
        _redis = aioredis.Redis(host=host, port=port, socket_connect_timeout=3)
        await _redis.ping()
        _redis_ok = True
        return True
    except Exception:
        _redis = None
        _redis_ok = False
        return False


async def close_redis() -> None:
    global _redis, _redis_ok
    if _redis:
        try:
            await _redis.close()
        except Exception:
            pass
    _redis = None
    _redis_ok = False


def is_connected() -> bool:
    return _redis_ok


# ═══════════════════════════════════════════════════════════════════
# PUBLISH
# ═══════════════════════════════════════════════════════════════════

async def publish(channel: str, event: dict[str, Any]) -> bool:
    """Publish an event to Redis. No-op if Redis is down.

    Every event gets a standard envelope: {type, ts, data}.
    Returns True if published, False if skipped.
    """
    if not _redis_ok or _redis is None:
        return False

    envelope = {
        "type": event.get("type", channel.replace("mag:", "")),
        "ts": event.get("ts", _now()),
        "data": event.get("data", event),
    }

    try:
        await _redis.publish(channel, json.dumps(envelope, default=str))
        return True
    except Exception:
        return False


def publish_sync(channel: str, event: dict[str, Any]) -> bool:
    """Synchronous publish (for non-async contexts). Uses a short-lived connection."""
    try:
        import redis
        host = os.environ.get("REDIS_HOST", "redis")
        port = int(os.environ.get("REDIS_PORT", "6379"))
        r = redis.Redis(host=host, port=port, socket_connect_timeout=2)
        envelope = {
            "type": event.get("type", channel.replace("mag:", "")),
            "ts": event.get("ts", _now()),
            "data": event.get("data", event),
        }
        r.publish(channel, json.dumps(envelope, default=str))
        r.close()
        return True
    except Exception:
        return False


# ═══════════════════════════════════════════════════════════════════
# SUBSCRIBE
# ═══════════════════════════════════════════════════════════════════

async def subscribe(
    channels: list[str],
    *,
    timeout: float = 30.0,
) -> AsyncIterator[dict[str, Any]]:
    """Subscribe to Redis channels. Yields parsed event dicts.

    Falls back to empty iterator if Redis is down.
    Use in async for loops:

        async for event in subscribe([CH_LEAK, CH_COPILOT]):
            if event["type"] == "leak":
                handle_leak(event["data"])

    Args:
        channels: List of channel names to subscribe to.
        timeout: Seconds to wait for a message before yielding heartbeat.

    Yields:
        Event dicts with {type, ts, data}.
    """
    if not _redis_ok or _redis is None:
        # Fallback: yield nothing, caller handles polling
        return

    try:
        pubsub = _redis.pubsub()
        await pubsub.subscribe(*channels)
        try:
            while True:
                msg = await pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=timeout,
                )
                if msg and msg.get("type") == "message":
                    try:
                        event = json.loads(msg["data"])
                        yield event
                    except json.JSONDecodeError:
                        continue
                else:
                    # Heartbeat
                    yield {"type": "heartbeat", "ts": _now(), "data": {}}
        except asyncio.CancelledError:
            pass
        finally:
            await pubsub.unsubscribe(*channels)
    except Exception:
        pass  # connection lost, caller retries


# ═══════════════════════════════════════════════════════════════════
# VERKLE KNOT BRIDGE
# ═══════════════════════════════════════════════════════════════════

async def fold_event_to_verkle(
    channel: str,
    event: dict[str, Any],
    *,
    session_id: str = "",
) -> bool:
    """Fold a Redis event into the Verkle chain as a permanent knot.

    This bridges real-time events → auditable state. Every important
    event (leak detected, task completed, steer deployed, scrum checkpoint)
    gets folded so the Verkle lattice captures the full system history.

    Returns True if folded, False if skipped.
    """
    try:
        from mag.verkle_knot import append_verkle_knot

        event_type = event.get("type", channel.replace("mag:", ""))
        dossier = {
            "session_id": session_id or f"event-{event_type}-{_now()[:19].replace(':', '')}",
            "time": {
                "created_at": {
                    "iso_minute": event.get("ts", _now()),
                    "unix_minute": None,
                    "date": None,
                },
                "updated_at": {
                    "iso_minute": _now(),
                    "unix_minute": None,
                    "date": None,
                },
            },
            "scalar_knot": {
                "duration_minutes": 0.01,
                "tension_index": event_type[:8],
                "residual_weight": 0.5,
                "theme_vector": {
                    "dominant": f"event_{event_type}",
                    "basis": ["event", "bus", "verkle", "mag"],
                    "raw": [1.0, 0.5, 0.3, 0.0],
                    "normalized": [1.0, 0.5, 0.3, 0.0],
                },
            },
            "content_commit": {
                "hex": json.dumps(event, default=str, sort_keys=True)[:40],
            },
            "_event_source": channel,
            "_event_data": event.get("data", {}),
        }
        append_verkle_knot(dossier)
        return True
    except Exception:
        return False


# ═══════════════════════════════════════════════════════════════════
# SCRUM CHECKPOINT — ship / research / done
# ═══════════════════════════════════════════════════════════════════

async def scrum_checkpoint(classification: str, items: list[dict[str, Any]]) -> bool:
    """Publish a scrum checkpoint: what to ship, research, or mark done.

    Args:
        classification: "ship", "research", or "done"
        items: List of task/item dicts being classified.

    Returns True if published.
    """
    return await publish(CH_SCRUM, {
        "type": "scrum",
        "classification": classification,
        "count": len(items),
        "items": items,
        "ts": _now(),
    })


# ═══════════════════════════════════════════════════════════════════
# STATUS
# ═══════════════════════════════════════════════════════════════════

def bus_status() -> dict[str, Any]:
    """Report event bus status."""
    return {
        "schema": "verkle_bus.v1",
        "ts": _now(),
        "redis_connected": _redis_ok,
        "redis_host": os.environ.get("REDIS_HOST", "redis"),
        "redis_port": int(os.environ.get("REDIS_PORT", "6379")),
        "channels": ALL_CHANNELS,
        "mode": "pub_sub" if _redis_ok else "polling_fallback",
    }
