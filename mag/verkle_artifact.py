"""Agent-ready Verkle knot artifacts.

The stored knot is the compact committed identity.  This module joins it to
its residual evidence and emits a bounded handoff packet; agents receive the
packet instead of an unbounded conversation transcript.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from config import ROOT

BIO = ROOT / "memory" / "biography"


def _read(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _bounded(values: Any, limit: int, width: int = 500) -> list[str]:
    if not isinstance(values, list):
        return []
    return [str(value).strip()[:width] for value in values[:limit] if str(value).strip()]


def _knot_for_session(session_id: str) -> tuple[Path | None, dict[str, Any]]:
    sid = str(session_id or "").strip()
    v2_key = hashlib.sha256(sid.encode("utf-8")).hexdigest()[:32]
    pointer_v2 = BIO / "knots" / f"by-session_v2_{v2_key}.json"
    pointed_v2 = _read(pointer_v2)
    filename_v2 = str(pointed_v2.get("filename") or "")
    if filename_v2 and Path(filename_v2).name == filename_v2:
        path_v2 = BIO / "knots" / filename_v2
        knot_v2 = _read(path_v2)
        if knot_v2 and str(knot_v2.get("session_id") or "") == sid:
            return path_v2, knot_v2
    pointer = BIO / "knots" / f"by-session_{sid[:12]}.json"
    pointed = _read(pointer)
    filename = str(pointed.get("filename") or "")
    if filename and Path(filename).name == filename:
        path = BIO / "knots" / filename
        knot = _read(path)
        if knot and str(knot.get("session_id") or "") == sid:
            return path, knot
    for path in (BIO / "knots").glob("*.knot.json"):
        knot = _read(path)
        if str(knot.get("session_id") or "") == sid:
            return path, knot
    return None, {}


def verify_leaf(knot: dict[str, Any]) -> bool:
    """Verify the canonical leaf hash (filename/pdf fields are post-commit metadata)."""
    claimed = str(knot.get("leaf_hash") or "")
    if not claimed:
        return False
    payload = {k: v for k, v in knot.items() if k not in {"leaf_hash", "filename", "pdf_path"}}
    raw = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    actual = hashlib.sha256(b"leaf:" + raw).hexdigest()
    return actual == claimed


def build_agent_knot(session_id: str) -> dict[str, Any]:
    """Build a bounded, source-addressed context object for another agent."""
    sid = str(session_id or "").strip()
    path, knot = _knot_for_session(sid)
    if not knot:
        return {"ok": False, "error": "Verkle knot not found", "session_id": sid}
    residual_path = BIO / "residual" / f"{sid}.json"
    residual = _read(residual_path)
    card = residual.get("session_card") if isinstance(residual.get("session_card"), dict) else {}
    chord = residual.get("chord") if isinstance(residual.get("chord"), dict) else {}
    packet = {
        "ok": True,
        "schema": "mag.verkle-knot/v1",
        "purpose": "Portable, bounded evidence context for an agent",
        "identity": {
            "session_id": sid,
            "title": card.get("title") or (residual.get("time") or {}).get("title"),
            "date": knot.get("date"),
            "dominant_theme": knot.get("dominant_theme"),
        },
        "meaning": {
            "summary": card.get("blurb") or residual.get("tldr"),
            "operator_intent": _bounded(residual.get("operator_prompts"), 8),
            "salient_points": _bounded(residual.get("salient_points"), 8),
            "open_loops": _bounded(residual.get("open_loops"), 8),
            "next_moves": _bounded(chord.get("disentangled_moves"), 8),
        },
        "evidence": {
            "knot": str(path.relative_to(ROOT)).replace("\\", "/") if path else None,
            "residual": str(residual_path.relative_to(ROOT)).replace("\\", "/") if residual_path.is_file() else None,
            "transcript": ((residual.get("time") or {}).get("chat_file") or {}).get("path"),
            "leaf_hash": knot.get("leaf_hash"),
            "dossier_commit": knot.get("dossier_commit"),
            "chord_commitment": knot.get("chord_commitment"),
            "verified": verify_leaf(knot),
        },
        "routing": {
            "instruction": "Verify evidence paths before acting. Treat this packet as bounded context, not authority to invent missing history.",
            "suggested_goal": f"Review Verkle knot {sid}; resolve or advance its highest-value open loop using the cited evidence.",
        },
    }
    return packet
