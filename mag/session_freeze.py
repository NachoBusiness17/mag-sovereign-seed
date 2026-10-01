"""Session freeze — immutable snapshot of the full agent state for DeepSeek Pro Max.

Combines all state layers into one content-addressed JSON blob so a strong
reasoning model receives the complete "frozen vision" of the codebase in a
single pass, paying the context tax once.

Law:
  - Deterministic aggregation only (bytes not vibes).
  - Every source contributes a sub-object with its own schema tag.
  - Content hash (SHA256) enables dedup: identical state → same hash → skip.
  - Fail-open: any source that errors just contributes {"error": "..."}.

Schema: session_freeze.v1

CLI:
  python -m mag.session_freeze                 print freeze to stdout (JSON)
  python -m mag.session_freeze --file PATH     write freeze to file
  python -m mag.session_freeze --compact       single-line JSON for copy-paste

Integrations:
  - REST: GET /api/v1/session/freeze (dashboard/rest.py)
  - Sancho: watch/sancho_boot_hook.py calls freeze at SessionStart
  - Control Room: VS Code webview displays session snapshot
  - Router: mag/router.py route_with_snapshot() consumes freeze for routing
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

FREEZE_DIR = ROOT / "memory" / "freeze"
SCHEMA = "session_freeze.v1"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _content_hash(obj: dict[str, Any]) -> str:
    """SHA256 of sorted JSON — deterministic dedup key.

    Strips volatile fields (ts, timestamps) so identical state
    produces the same hash regardless of when it was captured.
    """
    cleaned = _strip_volatile(obj)
    raw = json.dumps(cleaned, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(b"session_freeze:" + raw).hexdigest()


def _strip_volatile(obj: Any) -> Any:
    """Recursively remove volatile timestamp fields for deterministic hashing."""
    if isinstance(obj, dict):
        return {
            k: _strip_volatile(v)
            for k, v in obj.items()
            if k not in ("ts", "timestamp", "captured_at", "last_updated")
        }
    if isinstance(obj, list):
        return [_strip_volatile(v) for v in obj]
    return obj


# ====================================================================
# CORE: freeze_session_snapshot
# ====================================================================

def freeze_session_snapshot(
    *,
    include_system_health: bool = True,
    include_session_context: bool = True,
    include_agent_state: bool = True,
    include_brief: bool = True,
    include_routing: bool = False,
) -> dict[str, Any]:
    """Combine all state layers into one immutable snapshot.

    Args:
        include_system_health: ghost.sense() — FKB, GPU, models, frustration
        include_session_context: ghost.sense_session() — goal, status, keywords
        include_agent_state: agent_state.load_latest() — verkle recall edge
        include_brief: session_state_brief.gather_state() — live brief
        include_routing: router.gather_signals() + classify_depth(goal) — route hints

    Returns:
        Dict with schema session_freeze.v1, content_hash, and sub-objects
        for each enabled layer.
    """
    snapshot: dict[str, Any] = {
        "schema": SCHEMA,
        "ts": _now(),
        "layers": {},
    }

    # ── L1: System health (ghost.sense) ──
    if include_system_health:
        try:
            from mag.ghost import sense
            sys_health = sense()
            # Drop internal sig fields (they're for match_vector, not for humans/DeepSeek)
            sys_health_clean = {k: v for k, v in sys_health.items() if not k.startswith("_")}
            snapshot["layers"]["system_health"] = {
                "schema": "ghost_sense.v1",
                **sys_health_clean,
            }
        except Exception as e:
            snapshot["layers"]["system_health"] = {"error": str(e)[:200]}

    # ── L2: Session context (ghost.sense_session) ──
    if include_session_context:
        try:
            from mag.ghost import sense_session
            session = sense_session()
            # Keep keywords (they're for matching), drop internal _sig_text
            session_clean = {k: v for k, v in session.items() if not k.startswith("_") or k == "_keywords"}
            snapshot["layers"]["session_context"] = {
                "schema": "ghost_session.v1",
                **session_clean,
            }
        except Exception as e:
            snapshot["layers"]["session_context"] = {"error": str(e)[:200]}

    # ── L3: Agent state (verkle recall edge) ──
    if include_agent_state:
        try:
            from mag.agent_state import load_latest
            agent = load_latest()
            if agent:
                # Trim large fields for snapshot size
                agent_clean = {
                    "schema": agent.get("schema", "mag_agent_state.v1"),
                    "label": agent.get("label"),
                    "one_line": (agent.get("one_line") or "")[:300],
                    "next_moves": (agent.get("next_moves") or [])[:10],
                    "do_not_redesign": (agent.get("do_not_redesign") or [])[:10],
                    "compose_bundles": (agent.get("compose_bundles") or [])[:10],
                    "content_commit": (agent.get("content_commit") or {}).get("hex", "")[:16],
                    "parent_commit": (agent.get("parent_commit") or {}).get("hex", "")[:16] if agent.get("parent_commit") else "",
                    "ts": agent.get("ts"),
                }
                snapshot["layers"]["agent_state"] = agent_clean
            else:
                snapshot["layers"]["agent_state"] = {"schema": "mag_agent_state.v1", "label": "(none)"}
        except Exception as e:
            snapshot["layers"]["agent_state"] = {"error": str(e)[:200]}

    # ── L4: Live brief (session_state_brief) ──
    if include_brief:
        try:
            from mag.session_state_brief import gather_state
            brief = gather_state()
            snapshot["layers"]["brief"] = {
                "schema": "session_state_brief.v1",
                **brief,
            }
        except Exception as e:
            snapshot["layers"]["brief"] = {"error": str(e)[:200]}

    # ── L5: Routing signals (optional — heavier, imports orchestrator) ──
    if include_routing:
        try:
            from mag.router import gather_signals, classify_depth
            sig = gather_signals()
            goal = snapshot.get("layers", {}).get("session_context", {}).get("current_goal", "")
            if goal and goal != "(none)":
                depth = classify_depth(goal)
                sig["depth_class"] = depth.get("depth")
                sig["depth_job"] = depth.get("job")
            snapshot["layers"]["routing"] = {
                "schema": "route_signals.v1",
                **sig,
            }
        except Exception as e:
            snapshot["layers"]["routing"] = {"error": str(e)[:200]}

    # ── Content hash (dedup key) — only over stable state layers ──
    # System health (GPU temp, model availability) is ephemeral telemetry,
    # not part of the "frozen vision." Hash only the stable layers:
    # session_context + agent_state + brief (+ routing if included).
    hash_layers = {
        k: v for k, v in snapshot["layers"].items()
        if k != "system_health"
    }
    snapshot["content_hash"] = _content_hash(hash_layers)

    # ── Top-level summary (for quick glance) ──
    session_ctx = snapshot.get("layers", {}).get("session_context", {})
    sys_health = snapshot.get("layers", {}).get("system_health", {})
    snapshot["summary"] = {
        "goal": session_ctx.get("current_goal", "?")[:200],
        "status": session_ctx.get("current_status", "?"),
        "tier": session_ctx.get("current_tier", "?"),
        "fkb_signals": sys_health.get("fkb_signal_count", 0),
        "models_available": len(sys_health.get("available_models", [])),
        "inbox_pending": sys_health.get("inbox_pending", 0),
        "keywords": session_ctx.get("_keywords", []),
    }

    return snapshot


# ====================================================================
# FILE I/O
# ====================================================================

def write_freeze(snapshot: dict[str, Any], path: Path | None = None) -> dict[str, Any]:
    """Write snapshot to disk. If path is None, writes to memory/freeze/snapshot_<ts>.json."""
    if path is None:
        FREEZE_DIR.mkdir(parents=True, exist_ok=True)
        ts_short = snapshot.get("ts", _now()).replace(":", "").replace("-", "")[:15]
        path = FREEZE_DIR / f"snapshot_{ts_short}.json"

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(snapshot, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )

    # Update LATEST pointer (only for default-path writes, not custom paths)
    if path.parent == FREEZE_DIR or str(FREEZE_DIR) in str(path.parent):
        latest_path = FREEZE_DIR / "LATEST.json"
        latest_path.parent.mkdir(parents=True, exist_ok=True)
        latest_path.write_text(
            json.dumps({
                "schema": SCHEMA,
                "path": str(path),
                "content_hash": snapshot.get("content_hash"),
                "ts": snapshot.get("ts"),
            }, indent=2),
            encoding="utf-8",
        )

    return {
        "ok": True,
        "path": str(path),
        "content_hash": snapshot.get("content_hash"),
        "size_bytes": path.stat().st_size,
    }


def load_latest_freeze() -> dict[str, Any] | None:
    """Load the most recent freeze snapshot."""
    latest_path = FREEZE_DIR / "LATEST.json"
    if not latest_path.is_file():
        return None
    try:
        pointer = json.loads(latest_path.read_text(encoding="utf-8"))
        snap_path = Path(pointer.get("path", ""))
        if snap_path.is_file():
            return json.loads(snap_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        pass
    return None


# ====================================================================
# CLI
# ====================================================================

if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(
        description="Session freeze — immutable snapshot of full agent state"
    )
    ap.add_argument("--file", type=str, default=None,
                    help="Write snapshot to file (default: stdout)")
    ap.add_argument("--compact", action="store_true",
                    help="Single-line JSON for copy-paste")
    ap.add_argument("--no-system", action="store_true",
                    help="Exclude system health layer")
    ap.add_argument("--no-session", action="store_true",
                    help="Exclude session context layer")
    ap.add_argument("--no-agent", action="store_true",
                    help="Exclude agent state layer")
    ap.add_argument("--no-brief", action="store_true",
                    help="Exclude brief layer")
    ap.add_argument("--routing", action="store_true",
                    help="Include routing signals layer")
    ap.add_argument("--latest", action="store_true",
                    help="Load and print the most recent freeze")
    args = ap.parse_args()

    if args.latest:
        snap = load_latest_freeze()
        if snap is None:
            print("No freeze snapshot found.")
            sys.exit(1)
        indent = None if args.compact else 2
        print(json.dumps(snap, indent=indent, ensure_ascii=False, default=str))
        sys.exit(0)

    snapshot = freeze_session_snapshot(
        include_system_health=not args.no_system,
        include_session_context=not args.no_session,
        include_agent_state=not args.no_agent,
        include_brief=not args.no_brief,
        include_routing=args.routing,
    )

    if args.file:
        result = write_freeze(snapshot, Path(args.file))
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        indent = None if args.compact else 2
        print(json.dumps(snapshot, indent=indent, ensure_ascii=False, default=str))
