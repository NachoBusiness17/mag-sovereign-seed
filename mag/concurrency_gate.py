"""concurrency_gate — cross-process per-model in-flight limits (2026-08-25).

Grounding: z.ai rate limits are CONCURRENCY (in-flight requests), not RPM. The table
(operator-pasted from z.ai/manage-apikey/rate-limits, 2026-08-25):
  GLM-4.7-Flash: 1, GLM-4.7: 2, GLM-5.3: 1, GLM-5-Turbo: 1, GLM-4.6: 3,
  GLM-4.5: 10, GLM-5.1: 10, GLM-5.2: 10, GLM-4.5-Flash: 2, GLM-4.5-Air: 5, ...

The 1305 "service overloaded" wall is us exceeding a model's in-flight cap — thousands
QUEUED, single-digit (often ONE) in-flight. This module enforces the cap ACROSS PROCESSES
(the drain, the autonomous driver, and direct probes are separate processes, so a
threading semaphore cannot hold): a lease-file slot per in-flight token, stale-steal
after LEASE_SECS so a crashed holder can't deadlock the lane.

Usage:
    from mag import concurrency_gate as cg
    with cg.hold("glm-4.7-flash", timeout=120):   # blocks until a slot frees or timeout
        ... one in-flight call ...
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Iterator

ROOT = Path(r"c:\Users\foste\Documents\projects\local_sovereign_agent")

# The documented concurrency caps (in-flight requests per model). Source: operator pasted
# from z.ai/manage-apikey/rate-limits, 2026-08-25. Only the models we actually ride.
MODEL_CONCURRENCY: dict[str, int] = {
    "glm-4.7-flash": 1,
    "glm-4.7": 2,
    "glm-5.3": 1,
    "glm-5-turbo": 1,
    "glm-4.6": 3,
    "glm-4.5": 10,
    "glm-5.1": 10,
    "glm-5.2": 10,
    "glm-4.5-flash": 2,
    "glm-4.5-air": 5,
    "glm-4.6v-flashx": 3,
    "glm-5": 2,
    "glm-4-plus": 20,
    "glm-4-32b-0414-128k": 15,
    "search-prime": 5,
    "web-reader": 5,
    # deepseek-penny lane (openclaw conservation 2026-09-02): conservative local
    # cap, NOT a verified vendor number — no deepseek per-key table receipted.
    # 3 covers the 3-wide dogfood play without claiming more. (F2, 2026-09-04)
    "deepseek-v4-flash": 3,
    # coding-plan Max seat probe lane (2026-09-05, operator GO): "max-flash-5x"
    # is OUR name for the concurrency probe lane on the Max coding-plan seat.
    # g1 width 5 CLEAN (3.75x), g2 width 8 CLEAN (4.45x, peak 7); SHADOW WORK
    # fanout escalates to width 50 = the salon's ceiling experiment, real work.
    # 50 is the measured test width, NOT a vendor cap.
    "max-flash-5x": 50,
}

LEASE_SECS = 120          # a held slot this old is considered dead -> steal it
POLL_SECS = 0.5           # wait between slot polls
DEFAULT_TIMEOUT = 120     # max seconds to wait for a slot

_LOCK_DIR = ROOT / "memory" / "runs" / "concurrency"
LOCK_OWNER = os.path.basename(sys.argv[0] or "?")


def _slot_paths(model: str, *, lane: str = "") -> list[Path]:
    """Leases are per (lane, model) — coding-plan Max and funded Lite are
    different API keys. Sharing one glm-4.7-flash slot across keys made Lite
    wait 180s while Max hung on raw /paas/v4."""
    _LOCK_DIR.mkdir(parents=True, exist_ok=True)
    n = int(MODEL_CONCURRENCY.get(model, 1))
    prefix = f"{lane}.{model}" if lane else model
    return [_LOCK_DIR / f"{prefix}.{i}.lease" for i in range(max(1, n))]


def _lease_ok(path: Path) -> bool:
    """True if the slot is currently held by a LIVE lease."""
    try:
        d = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:  # noqa: BLE001
        return False
    ts = float(d.get("ts") or 0)
    return (time.time() - ts) < LEASE_SECS


def acquire(model: str, *, timeout: int = DEFAULT_TIMEOUT, owner: str = "", lane: str = "") -> str | None:
    """Block until a slot for this model is free (or timeout). Returns a token to release."""
    slots = _slot_paths(model, lane=lane)
    owner = owner or LOCK_OWNER
    deadline = time.time() + timeout
    while time.time() < deadline:
        for i, path in enumerate(slots):
            if not _lease_ok(path):
                try:
                    path.write_text(json.dumps({
                        "model": model, "lane": lane, "slot": i, "ts": time.time(),
                        "owner": owner, "pid": os.getpid(),
                    }), encoding="utf-8")
                    prefix = f"{lane}.{model}" if lane else model
                    return f"{prefix}.{i}"
                except Exception:  # noqa: BLE001
                    continue
        time.sleep(POLL_SECS)
    return None


def release(token: str) -> bool:
    """Release a held slot token (e.g. 'glm-4.7-flash.0')."""
    try:
        model, i = str(token).rsplit(".", 1)
        path = _LOCK_DIR / f"{model}.{int(i)}.lease"
        if path.is_file():
            path.unlink(missing_ok=True)
        return True
    except Exception:  # noqa: BLE001
        return False


def status() -> dict[str, Any]:
    """Who holds what, right now (the live in-flight map)."""
    _LOCK_DIR.mkdir(parents=True, exist_ok=True)
    held: dict[str, list[dict[str, Any]]] = {}
    for p in sorted(_LOCK_DIR.glob("*.lease")):
        try:
            d = json.loads(p.read_text(encoding="utf-8", errors="replace"))
        except Exception:  # noqa: BLE001
            continue
        m = d.get("model") or p.stem.split(".")[0]
        held.setdefault(m, []).append({
            "owner": d.get("owner"), "pid": d.get("pid"),
            "age_s": round(time.time() - float(d.get("ts") or 0), 1),
        })
    return {"ok": True, "schema": "concurrency_gate.v1", "held": held,
            "n_locked_models": len(held)}


def hold(model: str, *, timeout: int = DEFAULT_TIMEOUT, owner: str = "", lane: str = "") -> Iterator[None]:
    """Context manager: acquire a slot for the model's in-flight cap, release on exit."""
    import contextlib

    @contextlib.contextmanager
    def _ctx():
        token = acquire(model, timeout=timeout, owner=owner, lane=lane)
        if token is None:
            raise TimeoutError(f"no {model} slot free within {timeout}s")
        try:
            yield
        finally:
            release(token)

    return _ctx()
