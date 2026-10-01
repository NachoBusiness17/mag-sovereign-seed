"""Mag OS v2 — live status for dashboard (ARK-shaped, Mag-native)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT

DOCS = ROOT / "docs" / "ref"
CARD = DOCS / "MAG_Card.md"
ACTIVATION = DOCS / "MAG_Activation.md"
OS_DOC = DOCS / "MAG_OS_v2.md"
VERSION = "2.0.0"
COMMITMENT = "mag-os-v2-001"


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read(path: Path, n: int = 4000) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")[:n]


def load_card_lines() -> list[str]:
    """Non-negotiables for UI chips."""
    return [
        "Residual = DNA",
        "Presented corpus (or say not attached)",
        "Pack-first remotes",
        "Seat purity on open run",
        "Process ≠ case ≠ trail",
        "Grok scarce",
    ]


def live_status() -> dict[str, Any]:
    """Aggregate smoke + compose + run + pin for provenance strip."""
    out: dict[str, Any] = {
        "schema": "mag_os_v2_status",
        "version": VERSION,
        "commitment": COMMITMENT,
        "ts": _utc(),
        "non_negotiables": load_card_lines(),
        "paths": {
            "card": str(CARD.relative_to(ROOT)) if CARD.is_file() else None,
            "activation": str(ACTIVATION.relative_to(ROOT)) if ACTIVATION.is_file() else None,
            "os_doc": str(OS_DOC.relative_to(ROOT)) if OS_DOC.is_file() else None,
            "mirror_presented": "docs/ref/MIRROR_PRESENTED.md",
        },
        "card_md": _read(CARD, 2500),
        "activation_md": _read(ACTIVATION, 3500),
    }

    # health
    try:
        from mag.health import sanity

        s = sanity()
        out["health"] = {
            "status": s.get("status"),
            "live_stale": (s.get("recording") or {}).get("live_stale"),
        }
    except Exception as e:
        out["health"] = {"status": "unknown", "error": str(e)}

    # multi-smoke
    smoke_path = ROOT / "logs" / "multi_smoke_latest.json"
    smoke: dict[str, Any] = {}
    if smoke_path.is_file():
        try:
            smoke = json.loads(smoke_path.read_text(encoding="utf-8"))
        except Exception:
            smoke = {}
    out["smoke"] = {
        "ok": bool(smoke.get("ok")),
        "verdict": smoke.get("verdict") or ("PASS" if smoke.get("ok") else "UNKNOWN"),
        "models": smoke.get("models_seen"),
    }

    # compose
    try:
        from mag.modules import compose_status

        cs = compose_status()
        rt = cs.get("runtime") or {}
        out["compose"] = {
            "ok": cs.get("ok"),
            "n_modules": cs.get("n_modules"),
            "missing": cs.get("n_missing_paths"),
            "active_run": rt.get("active_run"),
            "related_runs_n": rt.get("related_runs_n"),
        }
    except Exception as e:
        out["compose"] = {"ok": False, "error": str(e)}

    # active run
    try:
        from mag.run_trail import load_run

        run = load_run()
        if run and run.get("status") == "open":
            out["run"] = {
                "open": True,
                "run_id": run.get("run_id"),
                "seat": run.get("seat"),
                "goal": (run.get("goal") or "")[:120],
                "proactivity": run.get("proactivity"),
            }
        else:
            out["run"] = {"open": False}
    except Exception:
        out["run"] = {"open": False}

    # pin
    pin = ROOT / "memory" / "improve" / "pins" / "LATEST.json"
    if pin.is_file():
        try:
            pj = json.loads(pin.read_text(encoding="utf-8"))
            out["pin"] = {
                "commitment": pj.get("commitment"),
                "health": (pj.get("verdict") or {}).get("health"),
            }
        except Exception:
            out["pin"] = {"commitment": None}
    else:
        out["pin"] = {"commitment": None}

    # bag
    bag_ptr = ROOT / "memory" / "portable_bags" / "LATEST.txt"
    out["portable_bag"] = (
        bag_ptr.read_text(encoding="utf-8").strip() if bag_ptr.is_file() else None
    )

    # ship status heuristic
    smoke_ok = out["smoke"].get("ok")
    compose_ok = out.get("compose", {}).get("ok")
    health_up = (out.get("health") or {}).get("status") == "up"
    if smoke_ok and compose_ok and health_up:
        ship = "OK"
    elif not smoke_ok or not compose_ok:
        ship = "PROVISIONAL"
    else:
        ship = "CAVEATS"
    out["ship_status"] = ship

    # Phoenix hint
    phoenix = []
    if not smoke_ok:
        phoenix.append("multi-smoke fail — run: python main.py multi-smoke")
    if not compose_ok:
        phoenix.append("compose red — run: python main.py compose-status")
    if (out.get("health") or {}).get("status") != "up":
        phoenix.append(
            "Mag health not up — scripts\\mag_exec.ps1 doctor; "
            "docker compose restart mag (not host python main.py lab)"
        )
    out["phoenix"] = phoenix

    out["ok"] = True
    return out
