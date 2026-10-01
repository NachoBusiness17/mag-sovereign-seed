"""Steal First — cache-before-inference middleware for all API endpoints.

PRINCIPLE: Never infer what's already known.
  Tier 1: Local texture cache (same query + same model → instant hit)
  Tier 2: Verkle chain lookup (has this result been proven before?)
  Tier 3: Swarm cache (did a parallel agent already compute this?)
  Tier 4: Model inference (only if tiers 1-3 all miss)

This wraps EVERY model call in the system. Not just task_router — every
endpoint, every agent, every query. The middleware sits between the caller
and the model, checking all cache tiers before spending inference cost.

STEAL PATTERNS (what we cache and never re-compute):
  - NachoQuixotic invariants → compoundable steer vectors (extract once, apply forever)
  - Verkle chain segments → structured extractions (parse once, reuse)
  - Swarm results → parallel agent outputs (compute once, share)
  - Model responses → query+model→result (ask once, cache with TTL)
  - Embedding vectors → semantic fingerprints (compute once, compare cheaply)

COST MODEL:
  Tier 1 hit: $0.00000 (local hash lookup, <1ms)
  Tier 2 hit: $0.00000 (Verkle chain read, <10ms)
  Tier 3 hit: $0.00000 (swarm result read, <50ms)
  Tier 4 miss:  $0.00013-$0.025 (actual model call, 500ms-30s)

  At 80% cache hit rate on 1000 calls: $0.05 vs $3.00 (60x savings)

SCHEMA: steal_first.v1
LAW: Every model call MUST pass through steal_first.
LAW: Cache results compound. Inference costs don't.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from mag.chain_query import chain  # auto-added by doctor_agent
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

try:
    from config import ROOT
except ImportError:
    ROOT = Path(__file__).resolve().parent.parent


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ═══════════════════════════════════════════════════════════════════
# TIER 1 — Local texture cache (fastest, hash-based)
# ═══════════════════════════════════════════════════════════════════

@dataclass
class StolenResult:
    """A result we already have — no inference needed."""
    value: Any
    source: str                    # "texture_cache", "verkle_chain", "swarm_cache"
    original_cost: float           # What it cost to produce originally
    saved_cost: float              # What we saved by stealing (same as original_cost)
    age_s: float                   # How old is this result?
    access_count: int = 0          # How many times we've stolen this
    verkle_breadcrumb: str = ""    # Verkle chain proof link

    @property
    def savings_multiplier(self) -> float:
        """How many times has this result been stolen vs produced?"""
        return self.access_count  # Each access is one inference saved


class StealFirstCache:
    """Four-tier cache hierarchy. Tiers checked in order until hit."""

    def __init__(self, max_size: int = 2000, default_ttl_s: float = 600.0):
        # Tier 1: exact query+model hash → result
        self._texture: OrderedDict[str, StolenResult] = OrderedDict()
        # Tier 2: Verkle breadcrumb → result (populated by chain reader)
        self._verkle: dict[str, StolenResult] = {}
        # Tier 3: swarm result digests
        self._swarm: dict[str, StolenResult] = {}
        # Config
        self.max_size = max_size
        self.default_ttl_s = default_ttl_s
        self._lock = threading.Lock()

        # Stats
        self.tier1_hits = 0
        self.tier2_hits = 0
        self.tier3_hits = 0
        self.tier4_misses = 0
        self.total_saved_cost = 0.0

    def _key(self, query: str, model: str, task_type: str = "") -> str:
        raw = f"{task_type}:{model}:{query}"
        return hashlib.sha256(raw.encode()).hexdigest()[:32]

    # ── Tier 1: Texture cache ──

    def texture_get(self, query: str, model: str = "", task_type: str = "") -> Optional[StolenResult]:
        """Tier 1: exact hash match. Fastest. <1ms."""
        key = self._key(query, model, task_type)
        with self._lock:
            result = self._texture.get(key)
            if result is None:
                return None
            if result.age_s > self.default_ttl_s:
                del self._texture[key]
                return None
            self._texture.move_to_end(key)
            result.access_count += 1
            self.tier1_hits += 1
            self.total_saved_cost += result.saved_cost
            return result

    def texture_put(
        self, query: str, value: Any, model: str = "", task_type: str = "",
        cost: float = 0.0, ttl_s: Optional[float] = None,
    ) -> StolenResult:
        """Store a new result in Tier 1."""
        key = self._key(query, model, task_type)
        result = StolenResult(
            value=value,
            source="texture_cache",
            original_cost=cost,
            saved_cost=cost,
            age_s=0.0,
        )
        with self._lock:
            while len(self._texture) >= self.max_size:
                self._texture.popitem(last=False)
            self._texture[key] = result
        return result

    # ── Tier 2: Verkle chain ──

    def verkle_get(self, breadcrumb: str) -> Optional[StolenResult]:
        """Tier 2: Verkle chain proof lookup. <10ms."""
        with self._lock:
            result = self._verkle.get(breadcrumb)
            if result is None:
                return None
            result.access_count += 1
            self.tier2_hits += 1
            self.total_saved_cost += result.saved_cost
            return result

    def verkle_put(self, breadcrumb: str, value: Any, cost: float = 0.0) -> None:
        """Index a Verkle chain result."""
        with self._lock:
            self._verkle[breadcrumb] = StolenResult(
                value=value,
                source="verkle_chain",
                original_cost=cost,
                saved_cost=cost,
                age_s=0.0,
                verkle_breadcrumb=breadcrumb,
            )

    # ── Tier 3: Swarm cache ──

    def swarm_get(self, task_id: str) -> Optional[StolenResult]:
        """Tier 3: did a parallel swarm agent already compute this? <50ms."""
        with self._lock:
            result = self._swarm.get(task_id)
            if result is None:
                return None
            result.access_count += 1
            self.tier3_hits += 1
            self.total_saved_cost += result.saved_cost
            return result

    def swarm_put(self, task_id: str, value: Any, cost: float = 0.0) -> None:
        """Index a swarm result."""
        with self._lock:
            self._swarm[task_id] = StolenResult(
                value=value,
                source="swarm_cache",
                original_cost=cost,
                saved_cost=cost,
                age_s=0.0,
            )

    # ── Stats ──

    def stats(self) -> dict[str, Any]:
        total_queries = self.tier1_hits + self.tier2_hits + self.tier3_hits + self.tier4_misses
        return {
            "tier1_hits": self.tier1_hits,
            "tier2_hits": self.tier2_hits,
            "tier3_hits": self.tier3_hits,
            "tier4_misses": self.tier4_misses,
            "total_queries": total_queries,
            "steal_rate": (self.tier1_hits + self.tier2_hits + self.tier3_hits) / max(total_queries, 1),
            "total_saved_cost": round(self.total_saved_cost, 6),
            "texture_cache_size": len(self._texture),
            "verkle_index_size": len(self._verkle),
            "swarm_index_size": len(self._swarm),
        }


# ═══════════════════════════════════════════════════════════════════
# MIDDLEWARE — wraps every model call
# ═══════════════════════════════════════════════════════════════════

class StealFirstMiddleware:
    """Middleware that sits between every API endpoint and every model call.

    Usage (decorator pattern):
        @steal_first(task_type="analyze_reason")
        def my_endpoint(query: str) -> dict:
            ...

    Usage (explicit call):
        result = steal_first.call(
            query="analyze the Verkle chain",
            model="grok-3-mini",
            task_type="analyze_reason",
            fallback=lambda: actual_model_call(),
        )
    """

    def __init__(self):
        self.cache = StealFirstCache()

    def call(
        self,
        query: str,
        model: str = "",
        task_type: str = "",
        max_cost: float = 0.025,
        fallback: Optional[Callable[[], Any]] = None,
    ) -> tuple[Any, str]:
        """Try to steal the result. If not found, call the fallback.

        Returns (result, source) where source is one of:
          "texture_cache", "verkle_chain", "swarm_cache", "inference"
        """
        # Tier 1: exact match
        stolen = self.cache.texture_get(query, model, task_type)
        if stolen is not None:
            return stolen.value, "texture_cache"

        # Tier 2: Verkle chain (check if query relates to a known breadcrumb)
        # For now: hash the query and check if any verkle entry matches
        query_hash = hashlib.sha256(f"{task_type}:{query}".encode()).hexdigest()[:16]
        stolen = self.cache.verkle_get(query_hash)
        if stolen is not None:
            # Also promote to texture cache for next time
            self.cache.texture_put(query, stolen.value, model, task_type, stolen.saved_cost)
            return stolen.value, "verkle_chain"

        # Tier 3: Swarm cache (check if a parallel agent already answered this)
        stolen = self.cache.swarm_get(query_hash)
        if stolen is not None:
            self.cache.texture_put(query, stolen.value, model, task_type, stolen.saved_cost)
            return stolen.value, "swarm_cache"

        # Tier 4: must infer
        self.cache.tier4_misses += 1
        if fallback is None:
            return None, "no_fallback"

        result = fallback()
        # Cache the result
        cost = self._estimate_cost(model, task_type)
        self.cache.texture_put(query, result, model, task_type, cost)
        return result, "inference"

    def _estimate_cost(self, model: str, task_type: str) -> float:
        """Estimate the cost of a model call. Used for savings tracking."""
        costs = {
            "grok-4-latest": 0.025,
            "grok-3-mini": 0.003,
            "deepseek-v4-flash": 0.00013,
            "qwen2.5-coder:7b": 0.0,
            "gemma:2b": 0.0,
        }
        return costs.get(model, 0.003)

    def stats(self) -> dict[str, Any]:
        return self.cache.stats()


# ═══════════════════════════════════════════════════════════════════
# STEAL-FIRST DECORATOR — drop-in for any endpoint
# ═══════════════════════════════════════════════════════════════════

_global_middleware: Optional[StealFirstMiddleware] = None


def get_steal_first() -> StealFirstMiddleware:
    global _global_middleware
    if _global_middleware is None:
        _global_middleware = StealFirstMiddleware()
    return _global_middleware


def steal_first(task_type: str = "", model: str = ""):
    """Decorator: wrap any function with steal-first caching.

    The wrapped function becomes the Tier 4 fallback.
    The cache key is (function_name, args, kwargs, task_type, model).

    Usage:
        @steal_first(task_type="analyze_reason", model="grok-3-mini")
        def analyze_verkle_chain(query: str) -> dict:
            # This only runs on cache miss
            return actual_grok_call(query)
    """
    def decorator(func: Callable):
        def wrapper(*args, **kwargs):
            middleware = get_steal_first()

            # Build cache key from function name + args
            query_parts = [func.__name__]
            query_parts.extend(str(a)[:100] for a in args)
            query_parts.extend(f"{k}={str(v)[:100]}" for k, v in sorted(kwargs.items()))
            query = " | ".join(query_parts)

            def fallback():
                return func(*args, **kwargs)

            result, source = middleware.call(
                query=query,
                model=model,
                task_type=task_type,
                fallback=fallback,
            )

            # If stolen, log and return
            if source != "inference":
                # Could publish to mag:bard here — "stole X instead of inferring, saved $Y"
                pass

            return result

        return wrapper
    return decorator


# ═══════════════════════════════════════════════════════════════════
# PRELOAD — seed the cache with known invariants (steal from research)
# ═══════════════════════════════════════════════════════════════════

def preload_nacho_invariants() -> int:
    """If the NachoQuixotic invariant extraction has completed, preload
    the extracted steer vectors into the cache so every future agent
    call benefits from the research without re-running inference."""
    outbox = ROOT / "memory" / "copilot" / "outbox"
    merged_file = outbox / "nacho-invariants-merged.json"

    if not merged_file.is_file():
        return 0

    try:
        data = json.loads(merged_file.read_text())
    except (json.JSONDecodeError, OSError):
        return 0

    middleware = get_steal_first()
    loaded = 0

    # Cache each prioritized steer vector
    for vector in data.get("prioritized_steer_vectors", []):
        name = vector.get("invariant_name", "")
        if name:
            key = f"steer_vector:{name}"
            middleware.cache.texture_put(
                query=key,
                value=vector,
                model="research-compound",
                task_type="steer_vector",
                cost=0.025,  # Original extraction cost
                ttl_s=86400 * 30,  # Steer vectors are permanent (30 day TTL = effectively forever)
            )
            loaded += 1

    return loaded


def preload_verkle_chain_segments() -> int:
    """Preload structured extractions from the Verkle chain into the cache.
    Parse once, reuse forever."""
    chain_path = ROOT / "memory" / "biography" / "# CHAIN_QUERY_MIGRATION_NEEDED: replace with chain.tail() or chain.by_type()"
    if not chain_path.is_file():
        return 0

    middleware = get_steal_first()
    loaded = 0

    try:
        for line in chain_path.read_text().strip().splitlines()[-50:]:  # Last 50 knots
            try:
                knot = json.loads(line)
                knot_id = knot.get("knot_id") or knot.get("hash", "")
                if knot_id:
                    middleware.cache.verkle_put(
                        breadcrumb=knot_id,
                        value=knot,
                        cost=0.0,  # Already paid for
                    )
                    loaded += 1
            except json.JSONDecodeError:
                continue
    except OSError:
        pass

    return loaded


# ═══════════════════════════════════════════════════════════════════
# WIRE INTO GHOST — add steal-first endpoint
# ═══════════════════════════════════════════════════════════════════

def steal_first_endpoint() -> dict[str, Any]:
    """REST endpoint: GET /api/v1/steal — cache statistics and savings."""
    mw = get_steal_first()
    stats = mw.stats()
    return {
        "ok": True,
        "schema": "steal_first.v1",
        "principle": "Never infer what's already known.",
        "stats": stats,
        "message": _savings_message(stats),
        "ts": _now(),
    }


def _savings_message(stats: dict[str, Any]) -> str:
    steal_rate = stats["steal_rate"]
    saved = stats["total_saved_cost"]
    if steal_rate > 0.8:
        return f"Hot cache: {steal_rate:.0%} steal rate. ${saved:.4f} saved. The system is learning."
    elif steal_rate > 0.5:
        return f"Warm cache: {steal_rate:.0%} steal rate. ${saved:.4f} saved. Keep feeding the cache."
    elif steal_rate > 0.2:
        return f"Cold cache: {steal_rate:.0%} steal rate. ${saved:.4f} saved. Preload more invariants."
    else:
        return f"Freezing: {steal_rate:.0%} steal rate. ${saved:.4f} saved. Seed the cache with research."
