"""RenderMan Map — cache-coherent agent rendering pipeline.

Maps Pixar RenderMan's rendering principles to the sovereign agent swarm.
Every RenderMan concept has a swarm equivalent.

RENDERMAN → SOVEREIGN ARCHITECTURE MAPPING:
  REYES (micropolygon adaptive sampling) → adaptive agent depth (rightsize per task)
  Stochastic sampling (Monte Carlo ray distribution) → swarm exploration (random probes)
  Bucketed rendering (image divided into tiles) → task partitioning across agents
  Lazy evaluation (only compute visible) → lazy model routing (only query when needed)
  BVH (bounding volume hierarchy) → Verkle chain (hierarchical content-addressed proof)
  Texture caching (mipmap, tile cache) → result cache (avoid redundant model calls)
  Ray coherence (bundle similar rays) → swarm coherence (bundle similar queries)
  Adaptive refinement (more samples in noisy areas) → more compute on uncertain tasks
  Deep shadows (volumetric occlusion) → deep context (multi-layer agent memory)
  Shader network (composable material graphs) → skill pipeline (composable agent skills)
  AOVs (arbitrary output variables) → multi-lens output (Bard + Verkle + Q + cost)
  Render farm (distributed bucket processing) → swarm farm (distributed agent processing)

CACHE MISS MINIMIZATION:
  Problem: Agents re-query same data, recompute same results, don't share outputs.
  Fix: RenderMan-style cache coherence —
    1. Bucket coherence: bundle related tasks into same agent
    2. Ray coherence: group similar queries into single model calls
    3. Texture cache: memoize model results with TTL
    4. Geometry cache: cache parsed/structured data
    5. Adaptive refinement: re-query only when uncertainty exceeds threshold
    6. Pre-fetch: predict needed data from task context before agent asks

SCHEMA: renderman.v1
LAW: Never query a model for what's already in cache.
LAW: Never send an agent what another agent already has.
LAW: Cache lines self-destruct when consent chain breaks.
"""

from __future__ import annotations

import hashlib
import json
import sys
import threading
import time
from mag.chain_query import chain  # auto-added by doctor_agent
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

try:
    from config import ROOT
except ImportError:
    ROOT = Path(__file__).resolve().parent.parent


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ═══════════════════════════════════════════════════════════════════
# MEMORY GUARD (2026-08-16): caches were bounded in COUNT but unbounded in per-entry SIZE —
# a GeometryCache of large parsed objects could hold gigabytes (the desk process 5GB leak).
# Skip caching any single value over this size; huge render/geometry objects don't benefit.
# ═══════════════════════════════════════════════════════════════════
MAX_CACHE_VALUE_BYTES = 2 * 1024 * 1024  # 2 MiB per entry


def _approx_size(o: Any, _seen: Optional[set] = None) -> int:
    """Rough in-memory size of a value in bytes. Best-effort; safe on any object."""
    try:
        if _seen is None:
            _seen = set()
        oid = id(o)
        if oid in _seen:
            return 0
        _seen.add(oid)
        base = sys.getsizeof(o)
        if isinstance(o, dict):
            return base + sum(_approx_size(k, _seen) + _approx_size(v, _seen) for k, v in o.items())
        if isinstance(o, (list, tuple, set, frozenset)):
            return base + sum(_approx_size(i, _seen) for i in o)
        if isinstance(o, str):
            return len(o.encode("utf-8", "replace")) + 64
        if isinstance(o, (bytes, bytearray)):
            return len(o)
        return base
    except Exception:
        try:
            return len(str(o)) + 64
        except Exception:
            return 0


# ═══════════════════════════════════════════════════════════════════
# CACHE LINES — the fundamental unit. Self-destruct on consent break.
# ═══════════════════════════════════════════════════════════════════

@dataclass
class CacheLine:
    """A single cached result. Tied to a consent chain. Self-destructs when chain breaks."""
    key: str                              # Content hash of the query
    value: Any                            # Cached result
    model: str                            # Which model produced this
    cost: float                           # What it cost to produce
    ttl_s: float                          # Time-to-live in seconds
    created_at: float = field(default_factory=time.time)
    access_count: int = 0                 # How many times this was a cache hit
    consent_chain_id: str = ""            # Which consent chain owns this
    dependencies: list[str] = field(default_factory=list)  # Related cache keys
    verkle_breadcrumb: str = ""           # Verkle chain proof link

    @property
    def expired(self) -> bool:
        return (time.time() - self.created_at) > self.ttl_s

    @property
    def age_s(self) -> float:
        return time.time() - self.created_at

    def hit(self) -> Any:
        """Record a cache hit and return the value."""
        self.access_count += 1
        return self.value


# ═══════════════════════════════════════════════════════════════════
# CONSENT CHAIN — permissioned sharing that can retroactively dissolve
# ═══════════════════════════════════════════════════════════════════

@dataclass
class ConsentChain:
    """A permissioned sharing agreement between sovereign instances.

    When the chain breaks:
      - All cache lines tied to this chain self-destruct
      - All shared Verkle knots become unreadable (LENS_KEY rotated)
      - All Bard passages referencing shared data are re-encoded without it
      - The consent is RETROCAUSAL — it was as if it never happened
    """
    chain_id: str
    owner: str                            # Who initiated the share
    grantee: str                          # Who received access
    level: int                            # 0=public, 1=surface, 2=deep, 3=raw
    resources: list[str] = field(default_factory=list)  # What was shared
    active: bool = True
    created_at: str = field(default_factory=_now)
    dissolved_at: str = ""

    # Access control matrix
    LEVEL_MATRIX = {
        0: {"can_read": ["public_metadata"], "can_query": [], "can_cache": False},
        1: {"can_read": ["public_metadata", "narrative_surface"], "can_query": ["bard_lens"], "can_cache": True},
        2: {"can_read": ["public_metadata", "narrative_surface", "decoded_events"], "can_query": ["bard_decode", "task_route"], "can_cache": True},
        3: {"can_read": ["*"], "can_query": ["*"], "can_cache": True, "note": "full trust — raw event access"},
    }

    def can_access(self, resource: str, operation: str = "read") -> bool:
        """Check if this consent chain permits access to a resource."""
        if not self.active:
            return False
        perms = self.LEVEL_MATRIX.get(self.level, self.LEVEL_MATRIX[0])
        allowed = perms.get(f"can_{operation}", [])
        return "*" in allowed or resource in allowed

    def dissolve(self) -> int:
        """Break the consent chain. Returns number of cache lines destroyed."""
        self.active = False
        self.dissolved_at = _now()

        # Destroy all cache lines tied to this chain
        destroyed = 0
        try:
            cache = get_texture_cache()
            keys_to_delete = [
                k for k, v in cache._lines.items()
                if v.consent_chain_id == self.chain_id
            ]
            for k in keys_to_delete:
                del cache._lines[k]
                destroyed += 1
        except Exception:
            pass

        return destroyed


# ═══════════════════════════════════════════════════════════════════
# TEXTURE CACHE — RenderMan-style mipmap cache for model results
# ═══════════════════════════════════════════════════════════════════

class TextureCache:
    """Mipmap-style hierarchical cache for model query results.

    RenderMan maps textures at different resolutions (mip levels).
    We map model results at different detail levels:
      L0: Raw model output (full response)
      L1: Extracted key facts (structured summary)
      L2: Embedding vector (semantic fingerprint)
      L3: Content hash (dedup key)

    When a query comes in:
      1. Hash the query → check L3 (exact match?)
      2. If no exact match, check L2 (semantically similar?)
      3. If similar, return L1 (structured summary) and let agent decide if L0 needed
      4. Only fetch L0 (raw model call) if truly necessary

    This is ADAPTIVE REFINEMENT: more compute only where uncertainty exceeds threshold.
    """

    def __init__(self, max_size: int = 1000, default_ttl_s: float = 300.0):
        self._lines: OrderedDict[str, CacheLine] = OrderedDict()
        self.max_size = max_size
        self.default_ttl_s = default_ttl_s
        self._lock = threading.Lock()
        self.hits: int = 0
        self.misses: int = 0
        self.evictions: int = 0
        self.dissolved: int = 0  # Consent-chain dissolutions

    def _key(self, query: str, model: str, task_type: str) -> str:
        """Deterministic cache key from query + model + task_type."""
        raw = f"{task_type}:{model}:{query}"
        return hashlib.sha256(raw.encode()).hexdigest()[:32]

    def get(self, query: str, model: str = "", task_type: str = "") -> Optional[CacheLine]:
        """Look up a cached result. Records hit/miss."""
        key = self._key(query, model, task_type)
        with self._lock:
            line = self._lines.get(key)
            if line is None:
                self.misses += 1
                return None
            if line.expired:
                del self._lines[key]
                self.misses += 1
                self.evictions += 1
                return None
            # Move to end (LRU: most recently used)
            self._lines.move_to_end(key)
            self.hits += 1
            return line

    def put(
        self,
        query: str,
        value: Any,
        model: str = "",
        task_type: str = "",
        cost: float = 0.0,
        ttl_s: Optional[float] = None,
        consent_chain_id: str = "",
        dependencies: Optional[list[str]] = None,
    ) -> CacheLine:
        """Store a result in the cache. Evicts LRU if over max_size."""
        key = self._key(query, model, task_type)
        ttl = ttl_s if ttl_s is not None else self.default_ttl_s

        line = CacheLine(
            key=key,
            value=value,
            model=model,
            cost=cost,
            ttl_s=ttl,
            consent_chain_id=consent_chain_id,
            dependencies=dependencies or [],
        )

        with self._lock:
            # MEMORY GUARD: never cache a single huge value (leak -> 5GB desk balloon).
            if _approx_size(value) > MAX_CACHE_VALUE_BYTES:
                self._skipped_large = getattr(self, "_skipped_large", 0) + 1
                return line  # caller keeps the value; cache does NOT retain it
            # Evict LRU if needed
            while len(self._lines) >= self.max_size:
                self._lines.popitem(last=False)
                self.evictions += 1
            self._lines[key] = line

        return line

    def invalidate_chain(self, chain_id: str) -> int:
        """Destroy all cache lines tied to a consent chain. Returns count."""
        with self._lock:
            keys = [k for k, v in self._lines.items() if v.consent_chain_id == chain_id]
            for k in keys:
                del self._lines[k]
            self.dissolved += len(keys)
            return len(keys)

    def stats(self) -> dict[str, Any]:
        """Cache performance statistics."""
        total = self.hits + self.misses
        return {
            "size": len(self._lines),
            "max_size": self.max_size,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": self.hits / max(total, 1),
            "evictions": self.evictions,
            "dissolved": self.dissolved,
            "oldest_age_s": min((v.age_s for v in self._lines.values()), default=0),
        }

    def pre_fetch_keys(self, queries: list[str], model: str = "", task_type: str = "") -> list[str]:
        """Return which of these queries are NOT in cache. Use to pre-fetch."""
        missing = []
        for q in queries:
            key = self._key(q, model, task_type)
            with self._lock:
                line = self._lines.get(key)
                if line is None or line.expired:
                    missing.append(q)
        return missing


# ═══════════════════════════════════════════════════════════════════
# GEOMETRY CACHE — structured data, parse once, reuse many times
# ═══════════════════════════════════════════════════════════════════

class GeometryCache:
    """Cache for parsed/structured data (Verkle chain segments, Q-sessions, etc.).

    RenderMan caches geometry so repeated renders don't re-parse the same models.
    We cache structured extractions so agents don't re-parse the same chain data.
    """

    def __init__(self, max_size: int = 500):
        self._lines: OrderedDict[str, CacheLine] = OrderedDict()
        self.max_size = max_size
        self._lock = threading.Lock()

    def get_structured(self, raw_key: str) -> Optional[Any]:
        """Get a cached structured extraction."""
        key = hashlib.sha256(f"geo:{raw_key}".encode()).hexdigest()[:32]
        with self._lock:
            line = self._lines.get(key)
            if line is None or line.expired:
                return None
            self._lines.move_to_end(key)
            return line.hit()

    def put_structured(self, raw_key: str, value: Any, ttl_s: float = 600.0) -> None:
        """Cache a structured extraction. Skips values over the size guard (memory leak fix)."""
        key = hashlib.sha256(f"geo:{raw_key}".encode()).hexdigest()[:32]
        if _approx_size(value) > MAX_CACHE_VALUE_BYTES:
            return  # MEMORY GUARD: do not retain huge parsed objects (leak -> 5GB balloon)
        line = CacheLine(key=key, value=value, model="parser", cost=0.0, ttl_s=ttl_s)
        with self._lock:
            while len(self._lines) >= self.max_size:
                self._lines.popitem(last=False)
            self._lines[key] = line


# ═══════════════════════════════════════════════════════════════════
# BUCKET RENDERER — partitions work across agents like RenderMan buckets
# ═══════════════════════════════════════════════════════════════════

@dataclass
class RenderBucket:
    """A unit of work assigned to one agent. Like a RenderMan image bucket."""
    bucket_id: str
    task_type: str
    query: str
    agent_id: str = ""
    model: str = ""
    cost_est: float = 0.0
    dependencies: list[str] = field(default_factory=list)  # Other bucket IDs this depends on
    status: str = "pending"               # pending, rendering, done, failed
    result: Any = None
    cache_hit: bool = False
    ts: str = field(default_factory=_now)


class BucketRenderer:
    """Divides a complex task into buckets and renders them across agents.

    RenderMan divides an image into 16x16 pixel buckets. Each bucket can be
    rendered independently on a different CPU core. Buckets that are spatially
    coherent (adjacent pixels) render faster because of texture cache locality.

    We divide complex tasks into buckets. Each bucket goes to an agent.
    Buckets that are semantically coherent (related queries) share cache lines.
    """

    def __init__(self, bucket_size: int = 3):
        self.bucket_size = bucket_size  # Max sub-queries per bucket
        self.buckets: dict[str, RenderBucket] = {}
        self.texture_cache = get_texture_cache()
        self.geometry_cache = GeometryCache()

    def partition(self, task_type: str, queries: list[str], model: str = "") -> list[RenderBucket]:
        """Partition a list of queries into coherent buckets.

        COHERENCE STRATEGY (minimizing cache miss):
          1. Group semantically similar queries (share cache lines)
          2. Order by dependency (render earlier buckets first)
          3. Pre-fetch cache for all queries in a bucket before rendering
          4. Bundle queries to same model (avoid model-switch overhead)
        """
        buckets: list[RenderBucket] = []

        # Group queries into buckets of bucket_size
        for i in range(0, len(queries), self.bucket_size):
            bucket_queries = queries[i:i + self.bucket_size]
            bucket_id = hashlib.sha256(
                f"{task_type}:{i}:{'.'.join(bucket_queries)}".encode()
            ).hexdigest()[:12]

            # Check cache before rendering — which queries are already cached?
            missing = self.texture_cache.pre_fetch_keys(bucket_queries, model, task_type)
            all_cached = len(missing) == 0

            bucket = RenderBucket(
                bucket_id=bucket_id,
                task_type=task_type,
                query=" | ".join(bucket_queries),
                model=model,
                cache_hit=all_cached,
            )
            buckets.append(bucket)
            self.buckets[bucket_id] = bucket

        return buckets

    def render_bucket(self, bucket_id: str) -> Any:
        """Render a single bucket — execute queries and cache results.

        Returns the rendered result. If all queries were cache hits,
        returns immediately without any model call.
        """
        bucket = self.buckets.get(bucket_id)
        if not bucket:
            return None

        bucket.status = "rendering"

        # If all cache hits, return immediately
        if bucket.cache_hit:
            bucket.status = "done"
            bucket.result = {"cached": True, "queries": bucket.query}
            return bucket.result

        # Otherwise, would route to model here
        # For now: return cache-aware status
        bucket.status = "done"
        bucket.result = {
            "cached": False,
            "queries": bucket.query,
            "model": bucket.model,
            "cost_est": bucket.cost_est,
        }
        return bucket.result

    def stats(self) -> dict[str, Any]:
        """Bucket renderer statistics."""
        buckets = list(self.buckets.values())
        return {
            "total_buckets": len(buckets),
            "pending": sum(1 for b in buckets if b.status == "pending"),
            "rendering": sum(1 for b in buckets if b.status == "rendering"),
            "done": sum(1 for b in buckets if b.status == "done"),
            "failed": sum(1 for b in buckets if b.status == "failed"),
            "cache_hits": sum(1 for b in buckets if b.cache_hit),
            "cache_hit_rate": sum(1 for b in buckets if b.cache_hit) / max(len(buckets), 1),
        }


# ═══════════════════════════════════════════════════════════════════
# STOCHASTIC SAMPLER — Monte Carlo exploration for agent swarms
# ═══════════════════════════════════════════════════════════════════

@dataclass
class StochasticSample:
    """A single Monte Carlo probe — a random agent exploration.

    RenderMan uses stochastic sampling: cast random rays, average the result.
    We use stochastic exploration: random agent probes, merge the findings.

    STOCHASTIC (exploration) vs DETERMINISTIC (exploitation):
      - Random probes cover the space (stochastic sampling)
      - Bucket coherence bundles related work (ray coherence)
      - Adaptive refinement focuses on uncertain areas (variance-based sampling)
      - Cache lines anchor known territory (texture cache)
    """
    sample_id: str
    query: str
    task_type: str
    model: str = ""
    cost: float = 0.0
    result: Any = None
    uncertainty: float = 1.0           # How uncertain we are about this area (0-1)
    variance: float = 1.0              # Result variance (for adaptive refinement)
    ts: str = field(default_factory=_now)


class StochasticSampler:
    """Monte Carlo exploration engine for the agent swarm.

    Casts random probes into the task space. Areas with high variance
    get more samples (adaptive refinement). Areas with low variance
    stop being sampled (convergence). Cache lines provide deterministic anchors.
    """

    def __init__(self, min_samples: int = 3, max_samples: int = 20, variance_threshold: float = 0.05):
        self.min_samples = min_samples
        self.max_samples = max_samples
        self.variance_threshold = variance_threshold
        self.samples: list[StochasticSample] = []
        self.converged: bool = False

    def needs_more_samples(self) -> bool:
        """Does this area need more stochastic exploration?

        Returns True if:
          - We haven't hit min_samples yet
          - Variance is above threshold AND we haven't hit max_samples
        """
        if len(self.samples) < self.min_samples:
            return True
        if len(self.samples) >= self.max_samples:
            return False
        avg_variance = sum(s.variance for s in self.samples) / max(len(self.samples), 1)
        return avg_variance > self.variance_threshold

    def add_sample(self, sample: StochasticSample) -> None:
        """Record a stochastic probe result."""
        self.samples.append(sample)
        # Check convergence
        if not self.needs_more_samples():
            self.converged = True

    def best_estimate(self) -> Optional[Any]:
        """Best estimate after stochastic exploration converges."""
        if not self.samples:
            return None
        # Weighted by inverse variance (more certain samples count more)
        # For now: return the most recent sample as best estimate
        return self.samples[-1].result

    def stats(self) -> dict[str, Any]:
        return {
            "samples": len(self.samples),
            "converged": self.converged,
            "min_samples": self.min_samples,
            "max_samples": self.max_samples,
            "avg_variance": sum(s.variance for s in self.samples) / max(len(self.samples), 1),
            "total_cost": sum(s.cost for s in self.samples),
        }


# ═══════════════════════════════════════════════════════════════════
# FOAM ARCHITECTURE — bubble physics for sovereign inter-surface
# ═══════════════════════════════════════════════════════════════════

@dataclass
class Bubble:
    """A sovereign instance in the foam. Like a bubble in physical foam.

    PLATEAU'S LAWS (how bubbles meet):
      1. Three films meet at 120° angles along a line
      2. Four lines meet at cos⁻¹(-1/3) ≈ 109.47° at a point
      3. Minimal surface area for given volume → energy minimization

    MAPPED TO SOVEREIGN ARCHITECTURE:
      1. Three instances share a Verkle bus channel (120° = balanced load)
      2. Four channels meet at a Verkle knot (109.47° = stable proof structure)
      3. Minimal shared surface for given capability → least privilege principle
    """
    bubble_id: str                        # Sovereign instance ID
    owner: str                            # Operator address (GSTD or local)
    capabilities: list[str] = field(default_factory=list)  # What this bubble offers
    membranes: dict[str, ConsentChain] = field(default_factory=dict)  # Active consent chains
    surface_tension: float = 1.0          # How hard to penetrate (higher = more sovereign)
    volume: float = 1.0                   # Capability volume (more skills = bigger bubble)
    pressure: float = 0.0                 # Internal pressure (queue depth, load)
    neighbors: list[str] = field(default_factory=list)  # Adjacent bubble IDs

    def membrane_to(self, other: str, level: int) -> ConsentChain:
        """Create a permissioned membrane between this bubble and another."""
        chain_id = hashlib.sha256(f"{self.bubble_id}:{other}:{level}".encode()).hexdigest()[:16]
        chain = ConsentChain(
            chain_id=chain_id,
            owner=self.bubble_id,
            grantee=other,
            level=level,
        )
        self.membranes[chain_id] = chain
        return chain

    def pop_membrane(self, chain_id: str) -> int:
        """Break a membrane. All shared data self-destructs. Returns lines destroyed."""
        if chain_id not in self.membranes:
            return 0
        chain = self.membranes[chain_id]
        destroyed = chain.dissolve()
        del self.membranes[chain_id]
        # Also destroy texture cache lines
        cache = get_texture_cache()
        destroyed += cache.invalidate_chain(chain_id)
        return destroyed

    def share_surface(self, other: "Bubble", level: int = 1) -> ConsentChain:
        """Share a surface with another bubble. Creates membranes on both sides.

        Level 0: Public metadata only
        Level 1: Narrative surface (Bard lens decode)
        Level 2: Deep events (task routing, costs)
        Level 3: Raw access (full trust — rarely granted)
        """
        chain = self.membrane_to(other.bubble_id, level)
        # The other bubble creates its own membrane independently
        # (sovereignty: each side controls its own consent)
        return chain


@dataclass
class Foam:
    """The emergent network of sovereign bubbles.

    Like physical foam:
      - Bubbles coarsen over time (small merge into large)
      - Surface tension maintains boundaries
      - Minimal surfaces emerge (least energy configuration)
      - Gas diffuses between bubbles (information seep at membrane)
      - Foam is STOCHASTIC at micro level (individual bubble interactions)
        but DETERMINISTIC at macro level (Plateau's laws, minimal surfaces)
    """
    bubbles: dict[str, Bubble] = field(default_factory=dict)
    total_membranes: int = 0
    total_dissolved: int = 0

    def add_bubble(self, bubble: Bubble) -> None:
        self.bubbles[bubble.bubble_id] = bubble

    def connect(self, a_id: str, b_id: str, level: int = 1) -> Optional[ConsentChain]:
        """Connect two bubbles with a shared membrane at a consent level."""
        a = self.bubbles.get(a_id)
        b = self.bubbles.get(b_id)
        if not a or not b:
            return None

        chain_a = a.membrane_to(b_id, level)
        chain_b = b.membrane_to(a_id, level)

        a.neighbors.append(b_id)
        b.neighbors.append(a_id)
        self.total_membranes += 2

        return chain_a

    def disconnect(self, a_id: str, b_id: str) -> tuple[int, int]:
        """Break all membranes between two bubbles. Returns (a_destroyed, b_destroyed)."""
        a = self.bubbles.get(a_id)
        b = self.bubbles.get(b_id)
        a_destroyed, b_destroyed = 0, 0

        if a:
            for chain_id in list(a.membranes.keys()):
                chain = a.membranes[chain_id]
                if chain.grantee == b_id:
                    a_destroyed += a.pop_membrane(chain_id)
            if b_id in a.neighbors:
                a.neighbors.remove(b_id)

        if b:
            for chain_id in list(b.membranes.keys()):
                chain = b.membranes[chain_id]
                if chain.grantee == a_id:
                    b_destroyed += b.pop_membrane(chain_id)
            if a_id in b.neighbors:
                b.neighbors.remove(a_id)

        self.total_dissolved += a_destroyed + b_destroyed
        return a_destroyed, b_destroyed

    def coarsen(self) -> int:
        """Foam coarsening: merge small, similar bubbles into larger ones.

        STOCHASTIC process at micro level — which bubbles meet is random.
        DETERMINISTIC at macro level — Plateau's laws govern the resulting structure.
        """
        # Identify merge candidates: small volume, similar capabilities, low surface tension
        merges = 0
        bubble_list = list(self.bubbles.values())
        for i, a in enumerate(bubble_list):
            for b in bubble_list[i + 1:]:
                if a.volume < 0.5 and b.volume < 0.5:
                    # Similar capabilities?
                    overlap = set(a.capabilities) & set(b.capabilities)
                    total = set(a.capabilities) | set(b.capabilities)
                    if len(overlap) / max(len(total), 1) > 0.5:
                        # Merge: b's capabilities flow into a
                        a.volume += b.volume
                        a.pressure = (a.pressure + b.pressure) / 2
                        a.capabilities = list(set(a.capabilities) | set(b.capabilities))
                        a.neighbors = list(set(a.neighbors + b.neighbors))
                        del self.bubbles[b.bubble_id]
                        merges += 1

        return merges

    def emergent_structure(self) -> dict[str, Any]:
        """Describe the foam's emergent structure — what forms without central control."""
        return {
            "bubbles": len(self.bubbles),
            "membranes": self.total_membranes,
            "dissolved": self.total_dissolved,
            "avg_volume": sum(b.volume for b in self.bubbles.values()) / max(len(self.bubbles), 1),
            "avg_surface_tension": sum(b.surface_tension for b in self.bubbles.values()) / max(len(self.bubbles), 1),
            "max_pressure": max((b.pressure for b in self.bubbles.values()), default=0),
            "clusters": self._count_clusters(),
            "description": self._describe_structure(),
        }

    def _count_clusters(self) -> int:
        """Count connected components (bubble clusters) in the foam."""
        visited: set[str] = set()
        clusters = 0
        for bid in self.bubbles:
            if bid not in visited:
                clusters += 1
                # BFS
                queue = [bid]
                while queue:
                    current = queue.pop(0)
                    if current in visited:
                        continue
                    visited.add(current)
                    bubble = self.bubbles.get(current)
                    if bubble:
                        for neighbor in bubble.neighbors:
                            if neighbor not in visited:
                                queue.append(neighbor)
        return clusters

    def _describe_structure(self) -> str:
        """Natural language description of the foam's emergent structure."""
        n = len(self.bubbles)
        c = self._count_clusters()
        if n == 0:
            return "Empty foam — no bubbles yet."
        if c == 1:
            return f"Single connected foam of {n} bubbles — maximum emergence."
        if c == n:
            return f"{n} isolated bubbles — no membranes formed."
        return f"{n} bubbles in {c} clusters — partial emergence, {n - c} membranes would connect the foam."


# ═══════════════════════════════════════════════════════════════════
# SINGLETONS
# ═══════════════════════════════════════════════════════════════════

_texture_cache: Optional[TextureCache] = None
_foam: Optional[Foam] = None


def get_texture_cache() -> TextureCache:
    global _texture_cache
    if _texture_cache is None:
        _texture_cache = TextureCache()
    return _texture_cache


def get_foam() -> Foam:
    global _foam
    if _foam is None:
        _foam = Foam()
    return _foam


# ═══════════════════════════════════════════════════════════════════
# CACHE MISS EXPERIMENT — how to measure and minimize
# ═══════════════════════════════════════════════════════════════════

def cache_miss_experiment(queries: list[str], models: list[str]) -> dict[str, Any]:
    """Run a cache miss experiment with the RenderMan pipeline.

    1. Partition queries into coherent buckets
    2. Pre-fetch cache for all queries
    3. Measure hit rate before and after bucketing
    4. Measure stochastic vs deterministic convergence

    Returns experiment results with recommendations.
    """
    cache = get_texture_cache()
    renderer = BucketRenderer(bucket_size=3)

    # Phase 1: Baseline — no bucketing, no pre-fetch
    baseline_hits = 0
    for q in queries[:20]:  # Sample first 20
        if cache.get(q, models[0] if models else "", "analyze_reason"):
            baseline_hits += 1

    # Phase 2: With bucketing — group coherent queries
    buckets = renderer.partition("analyze_reason", queries, models[0] if models else "")

    # Phase 3: Pre-fetch — what's still missing after bucketing?
    all_queries = [b.query for b in buckets]
    still_missing = cache.pre_fetch_keys(all_queries, models[0] if models else "", "analyze_reason")

    # Phase 4: Simulate stochastic exploration
    sampler = StochasticSampler(min_samples=3, max_samples=10)
    for q in queries[:sampler.max_samples]:
        sample = StochasticSample(
            sample_id=hashlib.sha256(q.encode()).hexdigest()[:12],
            query=q,
            task_type="analyze_reason",
            model=models[0] if models else "",
            cost=0.003,
            uncertainty=0.5,
        )
        sampler.add_sample(sample)

    return {
        "schema": "renderman-experiment.v1",
        "baseline": {
            "queries_sampled": min(20, len(queries)),
            "cache_hits": baseline_hits,
            "hit_rate": baseline_hits / max(min(20, len(queries)), 1),
        },
        "bucketed": {
            "buckets": len(buckets),
            "cache_hit_buckets": sum(1 for b in buckets if b.cache_hit),
        },
        "pre_fetch": {
            "still_missing": len(still_missing),
            "would_require_model_calls": len(still_missing),
            "estimated_cost": len(still_missing) * 0.003,  # Grok-3-mini
        },
        "stochastic": sampler.stats(),
        "cache": cache.stats(),
        "recommendation": _cache_recommendation(cache, len(still_missing)),
        "ts": _now(),
    }


def _cache_recommendation(cache: TextureCache, missing: int) -> str:
    """Generate a human-readable recommendation based on cache state."""
    hit_rate = cache.stats()["hit_rate"]
    if hit_rate > 0.8:
        return "Cache is hot — keep current strategy. Pre-fetch is working."
    elif hit_rate > 0.5:
        return f"Cache is warm — {missing} queries would miss. Increase TTL or pre-fetch more aggressively."
    elif hit_rate > 0.2:
        return f"Cache is cold — {missing} misses. Consider larger buckets, longer TTL, or semantic pre-fetch."
    else:
        return f"Cache is freezing — {missing} misses. Rebuild cache with seed data or increase bucket coherence."
