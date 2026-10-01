"""Operator preferences persisted for the supervisor (drainer toggle, etc.)."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from config import ROOT

PREF_PATH = ROOT / "state" / "mag_preferences.json"


def load_prefs() -> dict:
    if not PREF_PATH.is_file():
        return {}
    try:
        data = json.loads(PREF_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def save_prefs(prefs: dict) -> None:
    PREF_PATH.parent.mkdir(parents=True, exist_ok=True)
    PREF_PATH.write_text(json.dumps(prefs, indent=2, default=str), encoding="utf-8")


def drainer_enabled() -> bool:
    env = os.environ.get("MAG_DRAINER", "").strip().lower()
    if env in ("1", "true", "yes"):
        return True
    if env in ("0", "false", "no"):
        return False
    return bool(load_prefs().get("drainer"))


def operator_active() -> bool:
    """True when operator is in an interactive seat (Composer/Cursor) — pause autorun."""
    env = os.environ.get("MAG_OPERATOR_ACTIVE", "").strip().lower()
    if env in ("1", "true", "yes"):
        return True
    if env in ("0", "false", "no"):
        return False
    return bool(load_prefs().get("operator_active"))


def set_operator_active(enabled: bool) -> dict:
    prefs = load_prefs()
    prefs["operator_active"] = bool(enabled)
    prefs["updated_at"] = datetime.now(timezone.utc).isoformat()
    save_prefs(prefs)
    return prefs


def operator_status() -> dict:
    env = os.environ.get("MAG_OPERATOR_ACTIVE", "").strip().lower()
    pref = bool(load_prefs().get("operator_active"))
    locked = env in ("1", "true", "yes", "0", "false", "no")
    return {
        "operator_active": operator_active(),
        "pref": pref,
        "env": env or None,
        "env_locked": locked,
        "hint": (
            "MAG_OPERATOR_ACTIVE=1 pauses drainer while you work in Composer/Cursor"
            if locked
            else "Set in dashboard or MAG_OPERATOR_ACTIVE=1 when coding in IDE"
        ),
    }


def autorun_allowed() -> bool:
    """Drainer may tick only when enabled and operator is not actively coding."""
    if os.environ.get("MAG_DRAINER_FORCE", "").strip().lower() in ("1", "true", "yes"):
        return drainer_enabled()
    return drainer_enabled() and not operator_active()


def set_drainer(enabled: bool) -> dict:
    prefs = load_prefs()
    # Env lock: when MAG_DRAINER is explicitly set on, it owns the drainer state.
    # Ignore off-writes (e.g. lifecycle reconcile) so the container env can't be
    # silently overridden by a pref write that drainer_enabled() would ignore anyway.
    env = os.environ.get("MAG_DRAINER", "").strip().lower()
    if not enabled and env in ("1", "true", "yes"):
        return prefs
    prefs["drainer"] = bool(enabled)
    prefs["updated_at"] = datetime.now(timezone.utc).isoformat()
    save_prefs(prefs)
    return prefs


def drainer_status() -> dict:
    env = os.environ.get("MAG_DRAINER", "").strip().lower()
    pref = bool(load_prefs().get("drainer"))
    locked = env in ("1", "true", "yes", "0", "false", "no")
    op = operator_status()
    return {
        "enabled": drainer_enabled(),
        "autorun_allowed": autorun_allowed(),
        "pref": pref,
        "env": env or None,
        "env_locked": locked,
        "operator_active": op.get("operator_active"),
        "hint": (
            "MAG_DRAINER env overrides dashboard toggle"
            if locked
            else "Supervisor picks this up within ~5s"
        ),
    }


def inject_behavioral_pack() -> bool:
    """Include behavioral themes + compass framework in context-pack (default on)."""
    if os.environ.get("MAG_NO_BEHAVIORAL_PACK", "").strip().lower() in ("1", "true", "yes"):
        return False
    return load_prefs().get("inject_behavioral_pack", True) is not False


def set_inject_behavioral_pack(enabled: bool) -> dict:
    prefs = load_prefs()
    prefs["inject_behavioral_pack"] = bool(enabled)
    prefs["updated_at"] = datetime.now(timezone.utc).isoformat()
    save_prefs(prefs)
    return prefs


def autonomy_status() -> dict:
    prefs = load_prefs()
    return {
        "inject_behavioral_pack": inject_behavioral_pack(),
        "drainer": drainer_enabled(),
        "autorun_allowed": autorun_allowed(),
        "operator_active": operator_active(),
        "compass_autonomous_continue": True,
        "note": (
            "Ambiguous input (continue/go) is wrapped by compass — agent decides from blueprint + case law, "
            "not raw prompt. Toggle inject_behavioral_pack to teach recurring errors in every LOAD."
        ),
    }
