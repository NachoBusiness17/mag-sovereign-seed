"""Chain Query — canonical read surface for the Verkle chain.

EVERY module that asks "what do we know?" goes through this module.
The Verkle chain is the default. Files, live queries, and function calls
are FALLBACKS — only used when the chain doesn't have the answer.

This is not a new data store. It's a QUERY DISCIPLINE baked into the
import graph. Import chain_query. Ask the chain first. Always.

QUERY PRIMITIVES:
  chain.tail(n)          — last N knots
  chain.by_type(t)       — all knots of event type t
  chain.by_theme(theme)  — knots matching a theme vector
  chain.since(ts)        — knots since timestamp
  chain.breadcrumb(bc)   — resolve a breadcrumb hash
  chain.exists(pattern)  — does this pattern appear in the chain?
  chain.knot(knot_id)    — get a specific knot by ID

SCHEMA: chain_query.v1
LAW: Every "what do we know?" call hits the chain first.
LAW: No module reads the chain file directly. All go through here.
LAW: If the chain doesn't have it, fall back — but LOG the fallback.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

try:
    from config import ROOT
except ImportError:
    ROOT = Path(__file__).resolve().parent.parent


CHAIN_PATH = ROOT / "memory" / "biography" / "verkle_chain.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ═══════════════════════════════════════════════════════════════════
# CORE — the chain is an append-only JSONL. Read it. Query it.
# ═══════════════════════════════════════════════════════════════════

class ChainQuery:
    """Canonical read surface for the Verkle chain.

    All modules import this. All "what do we know?" questions route here.
    The chain is the default. Everything else is fallback.
    """

    def __init__(self):
        self._fallback_count: int = 0
        self._query_count: int = 0

    # ── Read primitives ──

    def _read(self, tail: Optional[int] = None) -> list[dict[str, Any]]:
        """Read the chain file. Internal — modules call query methods, not this."""
        if not CHAIN_PATH.is_file():
            return []
        try:
            lines = CHAIN_PATH.read_text(encoding="utf-8", errors="replace").strip().splitlines()
            if tail and len(lines) > tail:
                lines = lines[-tail:]
            knots: list[dict[str, Any]] = []
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                try:
                    knots.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
            return knots
        except OSError:
            return []

    def _log_query(self, method: str, result_count: int) -> None:
        self._query_count += 1

    def _log_fallback(self, method: str, reason: str) -> None:
        self._fallback_count += 1

    # ── Query primitives ──

    def tail(self, n: int = 20) -> list[dict[str, Any]]:
        """Last N knots in the chain. Default entry point for 'what's happening?'"""
        knots = self._read(tail=n)
        self._log_query("tail", len(knots))
        return knots

    def root(self) -> Optional[dict[str, Any]]:
        """The most recent knot — the Verkle root. Cryptographic anchor."""
        knots = self._read(tail=1)
        self._log_query("root", len(knots))
        return knots[0] if knots else None

    def by_type(self, event_type: str, tail: int = 100) -> list[dict[str, Any]]:
        """All knots of a given event type (e.g. 'sense_cycle', 'task_complete')."""
        knots = self._read(tail=tail)
        result = [k for k in knots if k.get("type") == event_type]
        self._log_query("by_type", len(result))
        if not result:
            self._log_fallback("by_type", f"no knots of type '{event_type}' in tail {tail}")
        return result

    def by_theme(self, theme_pattern: str, tail: int = 200) -> list[dict[str, Any]]:
        """Knots whose theme vector matches a pattern. Case-insensitive substring.

        Searches: dominant_theme, theme_vector.dominant, scalar_knot.theme_vector.dominant
        """
        knots = self._read(tail=tail)
        pattern = theme_pattern.lower()
        result = []
        for k in knots:
            # Multiple possible field paths for theme
            dominant = (
                k.get("dominant_theme", "") or
                k.get("theme_vector", {}).get("dominant", "") or
                k.get("scalar_knot", {}).get("theme_vector", {}).get("dominant", "")
            )
            # Also search full JSON for the pattern
            full_text = json.dumps(k).lower()
            if pattern in dominant.lower() or pattern in full_text:
                result.append(k)
        self._log_query("by_theme", len(result))
        if not result:
            self._log_fallback("by_theme", f"no theme match for '{theme_pattern}' in tail {tail}")
        return result

    def since(self, ts: str, tail: int = 500) -> list[dict[str, Any]]:
        """Knots since a given ISO timestamp."""
        knots = self._read(tail=tail)
        result = [k for k in knots if k.get("ts", "") >= ts]
        self._log_query("since", len(result))
        return result

    def breadcrumb(self, breadcrumb: str, tail: int = 500) -> Optional[dict[str, Any]]:
        """Resolve a breadcrumb hash to its original knot."""
        knots = self._read(tail=tail)
        for k in reversed(knots):  # Newest first
            knot_text = json.dumps(k)
            if breadcrumb in knot_text:
                self._log_query("breadcrumb", 1)
                return k
        self._log_fallback("breadcrumb", f"'{breadcrumb}' not found in tail {tail}")
        return None

    def exists(self, pattern: str, tail: int = 500) -> bool:
        """Does a pattern (substring or regex) appear in the chain?"""
        knots = self._read(tail=tail)
        for k in knots:
            knot_text = json.dumps(k)
            if pattern in knot_text:
                self._log_query("exists", 1)
                return True
            try:
                if re.search(pattern, knot_text, re.IGNORECASE):
                    self._log_query("exists", 1)
                    return True
            except re.error:
                pass
        self._log_fallback("exists", f"pattern '{pattern}' not found")
        return False

    def knot(self, knot_id: str, tail: int = 500) -> Optional[dict[str, Any]]:
        """Get a specific knot by its ID or hash."""
        knots = self._read(tail=tail)
        for k in knots:
            if (k.get("knot_id") == knot_id or
                k.get("hash") == knot_id or
                k.get("id") == knot_id):
                self._log_query("knot", 1)
                return k
        self._log_fallback("knot", f"'{knot_id}' not found")
        return None

    def latest_by(self, event_type: str, tail: int = 100) -> Optional[dict[str, Any]]:
        """Most recent knot of a given type."""
        knots = self.by_type(event_type, tail=tail)
        result = knots[-1] if knots else None
        if not result:
            self._log_fallback("latest_by", f"no '{event_type}' knot found")
        return result

    # ── Aggregation queries ──

    def count_by(self, event_type: str, tail: int = 500) -> int:
        """How many knots of a given type?"""
        return len(self.by_type(event_type, tail=tail))

    def theme_summary(self, tail: int = 50) -> list[str]:
        """List of dominant themes from the last N knots."""
        knots = self._read(tail=tail)
        themes = []
        for k in knots:
            theme = (
                k.get("dominant_theme") or
                k.get("theme_vector", {}).get("dominant") or
                k.get("scalar_knot", {}).get("theme_vector", {}).get("dominant")
            )
            if theme:
                themes.append(theme)
        return themes

    def cost_window(self, window_s: int = 3600) -> float:
        """Total cost in the last N seconds from chain knots."""
        from datetime import timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(seconds=window_s)).isoformat()
        knots = self.since(cutoff)
        total = 0.0
        for k in knots:
            total += k.get("cost", 0.0) or k.get("data", {}).get("cost", 0.0) or 0.0
        return total

    # ── Stats ──

    def stats(self) -> dict[str, Any]:
        """Query discipline statistics — how often are we falling back?"""
        return {
            "queries": self._query_count,
            "fallbacks": self._fallback_count,
            "fallback_rate": self._fallback_count / max(self._query_count, 1),
            "chain_discipline": "healthy" if self._fallback_count < self._query_count * 0.1 else "degraded",
            "ts": _now(),
        }


# ═══════════════════════════════════════════════════════════════════
# SINGLETON — every module imports this
# ═══════════════════════════════════════════════════════════════════

chain = ChainQuery()


# ═══════════════════════════════════════════════════════════════════
# GHOST ENDPOINT — GET /api/v1/chain/query
# ═══════════════════════════════════════════════════════════════════

def chain_query_endpoint(query_type: str = "tail", **params) -> dict[str, Any]:
    """REST endpoint for chain queries. Exposes the chain read surface.

    GET /api/v1/chain/query?type=tail&n=20
    GET /api/v1/chain/query?type=by_theme&pattern=titor
    GET /api/v1/chain/query?type=by_type&event_type=sense_cycle
    GET /api/v1/chain/query?type=breadcrumb&breadcrumb=abc123
    GET /api/v1/chain/query?type=root
    GET /api/v1/chain/query?type=stats
    """
    try:
        if query_type == "tail":
            n = int(params.get("n", 20))
            return {"ok": True, "knots": chain.tail(n), "count": n}

        elif query_type == "root":
            root = chain.root()
            return {"ok": True, "root": root}

        elif query_type == "by_type":
            event_type = params.get("event_type", "")
            tail_n = int(params.get("tail", 100))
            knots = chain.by_type(event_type, tail=tail_n)
            return {"ok": True, "knots": knots, "count": len(knots)}

        elif query_type == "by_theme":
            pattern = params.get("pattern", "")
            tail_n = int(params.get("tail", 200))
            knots = chain.by_theme(pattern, tail=tail_n)
            return {"ok": True, "knots": knots, "count": len(knots)}

        elif query_type == "breadcrumb":
            bc = params.get("breadcrumb", "")
            knot = chain.breadcrumb(bc)
            return {"ok": True, "knot": knot, "found": knot is not None}

        elif query_type == "exists":
            pattern = params.get("pattern", "")
            return {"ok": True, "exists": chain.exists(pattern)}

        elif query_type == "theme_summary":
            n = int(params.get("n", 50))
            return {"ok": True, "themes": chain.theme_summary(tail=n)}

        elif query_type == "stats":
            return {"ok": True, **chain.stats()}

        else:
            return {"ok": False, "error": f"Unknown query type: {query_type}"}

    except Exception as e:
        return {"ok": False, "error": str(e)[:300]}
