"""Lightweight scalar-knot anchors for session dossiers (analysis-ready).

Inspired by Steiniger EUT / scalar-knot grammar — numerical proxies for *future*
untangling analysis, not a claim of full lattice simulation.

Every dossier should carry:
  - ISO timestamps to the minute (and second when available)
  - Unix epoch seconds
  - Theme weight vector + normalized distribution
  - Tension index, residual weight, frame occupancy
  - Content hash for Verkle-style commit of the extract
"""
from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def parse_iso_minute(iso: str | None) -> dict[str, Any] | None:
    if not iso:
        return None
    s = iso.strip().replace("Z", "+00:00")
    try:
        # trim subseconds noise for display; keep full for epoch
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        dt_utc = dt.astimezone(timezone.utc)
        minute = dt_utc.replace(second=0, microsecond=0)
        return {
            "iso_full": dt_utc.isoformat().replace("+00:00", "Z"),
            "iso_minute": minute.strftime("%Y-%m-%dT%H:%M:00Z"),
            "date": minute.strftime("%Y-%m-%d"),
            "time_minute": minute.strftime("%H:%M"),
            "unix": int(dt_utc.timestamp()),
            "unix_minute": int(minute.timestamp()),
        }
    except ValueError:
        return None


def file_time_anchor(path: Path) -> dict[str, Any]:
    st = path.stat()
    # Windows mtime
    m = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc)
    c = datetime.fromtimestamp(st.st_ctime, tz=timezone.utc)
    return {
        "path": str(path),
        "mtime": parse_iso_minute(m.isoformat()),
        "ctime": parse_iso_minute(c.isoformat()),
        "size_bytes": st.st_size,
    }


def load_session_meta(session_id: str, chat_path: Path | None) -> dict[str, Any]:
    """Pull times from Grok summary.json or Mag agent session JSON when present."""
    meta: dict[str, Any] = {"session_id": session_id}
    if chat_path and chat_path.is_file():
        summary = chat_path.parent / "summary.json"
        if summary.is_file():
            try:
                data = json.loads(summary.read_text(encoding="utf-8"))
                meta["title"] = data.get("generated_title") or data.get("session_summary")
                meta["created_at"] = parse_iso_minute(data.get("created_at"))
                meta["updated_at"] = parse_iso_minute(data.get("updated_at"))
                meta["last_active_at"] = parse_iso_minute(data.get("last_active_at"))
                meta["num_messages"] = data.get("num_messages")
                meta["num_chat_messages"] = data.get("num_chat_messages")
                meta["model"] = data.get("current_model_id")
            except (json.JSONDecodeError, OSError):
                pass
        # Mag agent seat: single JSON with messages + updated
        if chat_path.suffix == ".json" and chat_path.name != "summary.json":
            try:
                data = json.loads(chat_path.read_text(encoding="utf-8"))
                if isinstance(data, dict) and isinstance(data.get("messages"), list):
                    meta["source"] = "mag_agent"
                    meta["title"] = (
                        data.get("title")
                        or f"Mag agent · {data.get('session_id') or chat_path.stem}"
                    )
                    meta["updated_at"] = parse_iso_minute(data.get("updated"))
                    meta["created_at"] = meta.get("created_at") or meta.get("updated_at")
                    meta["num_messages"] = len(data.get("messages") or [])
                    meta["num_chat_messages"] = meta["num_messages"]
                    meta["model"] = data.get("model") or data.get("provider")
                    meta["provider"] = data.get("provider")
            except (json.JSONDecodeError, OSError):
                pass
        meta["chat_file"] = file_time_anchor(chat_path)
        # If agent JSON had no updated field, use file mtime anchors
        if not meta.get("created_at") and meta.get("chat_file"):
            cf = meta["chat_file"]
            meta["created_at"] = cf.get("ctime") or cf.get("mtime")
            meta["updated_at"] = cf.get("mtime") or cf.get("ctime")
    # dossier generation clock
    now = datetime.now(timezone.utc)
    meta["dossier_generated_at"] = parse_iso_minute(now.isoformat())
    return meta


def theme_vector(themes: list[dict[str, Any]]) -> dict[str, Any]:
    """Map theme scores to a fixed-order vector for time-series analysis."""
    order = [
        "mirror_meta",
        "mag_hands",
        "scrum_plan",
        "constitution",
        "dashboard",
        "harness",
        "biography",
        "data_r0",
    ]
    scores = {t.get("id"): float(t.get("score") or 0) for t in themes}
    vec = [scores.get(k, 0.0) for k in order]
    total = sum(vec) or 1.0
    norm = [v / total for v in vec]
    # entropy of theme distribution (nats)
    ent = 0.0
    for p in norm:
        if p > 0:
            ent -= p * math.log(p)
    # concentration = 1 - normalized entropy
    max_ent = math.log(len(order)) if order else 1.0
    concentration = 1.0 - (ent / max_ent if max_ent else 0.0)
    return {
        "basis": order,
        "raw": vec,
        "normalized": [round(x, 6) for x in norm],
        "L1": total,
        "L2": math.sqrt(sum(v * v for v in vec)),
        "entropy_nats": round(ent, 6),
        "concentration": round(concentration, 6),
        "dominant": order[int(max(range(len(vec)), key=lambda i: vec[i]))] if any(vec) else None,
    }


def scalar_knot_proxy(
    *,
    themes: list[dict[str, Any]],
    tension_n: int,
    frames_active: int,
    frames_total: int,
    residual_n: int,
    collapse_n: int,
    metaphor_n: int,
    idea_n: int,
    user_n: int,
    tool_n: int,
    duration_minutes: float | None,
) -> dict[str, Any]:
    """
    Proxies aligned with laymen Steiniger ops for later untangling:

    S_core_proxy  — stability of protected-core insistence (constant for now; session-level)
    tension_index — unresolved pressure load
    residual_weight — keep-list mass
    Q_proxy       — 'charge' ~ sum of theme intensity (½ ||w||² style)
    gap_proxy     — separation between dominant and secondary theme (spectral-gap flavored)
    lambda2_proxy — crude connectivity of theme support
    """
    tv = theme_vector(themes)
    raw = tv["raw"]
    sorted_raw = sorted(raw, reverse=True)
    dominant = sorted_raw[0] if sorted_raw else 0.0
    second = sorted_raw[1] if len(sorted_raw) > 1 else 0.0
    gap = (dominant - second) / (dominant + 1e-9)

    support = sum(1 for v in raw if v > 0)
    # graph laplacian λ2 proxy: more multi-theme support → higher connectivity
    lambda2 = support / max(len(raw), 1)

    tension_index = min(
        1.0,
        0.15 * tension_n
        + 0.08 * collapse_n
        + 0.05 * (1.0 - tv["concentration"])
        + 0.02 * max(0, tool_n / 50.0),
    )
    residual_weight = min(1.0, 0.12 * residual_n + 0.05 * metaphor_n + 0.04 * idea_n)
    frame_occupancy = frames_active / max(frames_total, 1)

    # Dirichlet-like energy proxy on normalized theme vector (sum (p_i - mean)^2)
    mean = sum(tv["normalized"]) / max(len(tv["normalized"]), 1)
    energy = 0.5 * sum((p - mean) ** 2 for p in tv["normalized"])

    Q = 0.5 * sum(v * v for v in raw)

    return {
        "schema": "scalar_knot_proxy.v1",
        "note": (
            "Analysis anchors only — not a full EUT solve. "
            "Suitable for time-series untangling of sessions."
        ),
        "S_core_proxy": -8.0,  # protected core convention from Scalar Knots literature
        "beta_target": 3.0,
        "tension_index": round(tension_index, 6),
        "residual_weight": round(residual_weight, 6),
        "frame_occupancy": round(frame_occupancy, 6),
        "Q_proxy": round(Q, 6),
        "gap_proxy": round(gap, 6),
        "lambda2_proxy": round(lambda2, 6),
        "dirichlet_energy_proxy": round(energy, 6),
        "theme_vector": tv,
        "counts": {
            "tension_items": tension_n,
            "frames_active": frames_active,
            "frames_total": frames_total,
            "residual_items": residual_n,
            "collapse_items": collapse_n,
            "metaphors": metaphor_n,
            "ideas": idea_n,
            "user_prompts": user_n,
            "tool_previews": tool_n,
        },
        "duration_minutes": duration_minutes,
    }


def content_commit(payload: dict[str, Any]) -> dict[str, str]:
    """Hash of analysis payload for append-only history."""
    blob = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return {
        "algo": "sha256",
        "hex": hashlib.sha256(blob).hexdigest(),
        "blake2b_128": hashlib.blake2b(blob, digest_size=16).hexdigest(),
    }


def duration_minutes(meta: dict[str, Any]) -> float | None:
    c = (meta.get("created_at") or {}).get("unix")
    u = (meta.get("updated_at") or {}).get("unix") or (meta.get("last_active_at") or {}).get(
        "unix"
    )
    if c and u and u >= c:
        return round((u - c) / 60.0, 2)
    return None
