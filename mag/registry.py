"""Lean residual registry — hot index + canonical residual + optional derived.

Layout:
  memory/biography/registry.jsonl     # one line per session (UI hot path)
  memory/biography/residual/{sid}.json  # canonical residual (dossier body)
  memory/biography/derived/{sid}.*    # optional PDF / md / visual (regenerable)
  memory/biography/verkle_tip.json + knots/  # chain tip + leaves (existing)

Legacy flat files ({sid}.dossier.json, .pdf, …) still read for migration.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT

BIO = ROOT / "memory" / "biography"
RESIDUAL_DIR = BIO / "residual"
DERIVED_DIR = BIO / "derived"
REGISTRY = BIO / "registry.jsonl"
LATEST_SESSION = BIO / "latest_session.json"

# Cold vertex invariants — amend may add, never remove these names
CORE_INVARIANTS = (
    "consent_first",
    "local_first",
    "no_throne",
    "residual_is_dna",
    "window_steer",
)


def residual_path(session_id: str) -> Path:
    return RESIDUAL_DIR / f"{session_id}.json"


def legacy_dossier_path(session_id: str) -> Path:
    return BIO / f"{session_id}.dossier.json"


def derived_path(session_id: str, kind: str) -> Path:
    """kind: md | pdf | visual_pack | dossier_legacy"""
    if kind == "md":
        return DERIVED_DIR / f"{session_id}.md"
    if kind == "pdf":
        return DERIVED_DIR / f"{session_id}.pdf"
    if kind == "visual_pack":
        return DERIVED_DIR / f"{session_id}.visual_pack.json"
    raise ValueError(kind)


def find_residual(session_id: str) -> Path | None:
    p = residual_path(session_id)
    if p.is_file():
        return p
    legacy = legacy_dossier_path(session_id)
    if legacy.is_file():
        return legacy
    return None


def find_derived(session_id: str, kind: str) -> Path | None:
    """Prefer derived/, then legacy flat biography root."""
    if kind == "md":
        for p in (derived_path(session_id, "md"), BIO / f"{session_id}.md"):
            if p.is_file():
                return p
    elif kind == "pdf":
        for p in (derived_path(session_id, "pdf"), BIO / f"{session_id}.pdf"):
            if p.is_file():
                return p
    elif kind == "visual_pack":
        for p in (
            derived_path(session_id, "visual_pack"),
            BIO / f"{session_id}.visual_pack.json",
        ):
            if p.is_file():
                return p
    return None


def load_residual(session_id: str) -> dict[str, Any] | None:
    p = find_residual(session_id)
    if not p:
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def residual_content_hash(dossier: dict[str, Any]) -> str:
    """Stable hash of residual body (excludes volatile verkle tip fields)."""
    body = {
        "session_id": dossier.get("session_id"),
        "time": dossier.get("time"),
        "scalar_knot": dossier.get("scalar_knot"),
        "chord": dossier.get("chord"),
        "tldr": dossier.get("tldr"),
        "session_card": dossier.get("session_card"),
        "themes": dossier.get("themes"),
        "steiniger_laymen": dossier.get("steiniger_laymen"),
        "content_commit": dossier.get("content_commit"),
        "open_loops": dossier.get("open_loops"),
        "salient_points": dossier.get("salient_points"),
        "core": dossier.get("core"),
        # retrocausal edges (related_runs etc.) — hash so amend is visible
        "edges": dossier.get("edges"),
    }
    raw = json.dumps(body, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(b"residual:v1:" + raw).hexdigest()


def attach_cold_core(
    dossier: dict[str, Any],
    *,
    previous: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Shared coldest vertex: core block that amend cannot strip.

    Steiniger-shaped ops: protect residual seed; coarse face = card.
    """
    d = dict(dossier)
    prev = previous or {}
    prev_core = dict(prev.get("core") or d.get("core") or {})
    card = d.get("session_card") or prev.get("session_card") or {}
    prev_card = (prev_core.get("card") or {}) if isinstance(prev_core.get("card"), dict) else {}
    commit = (d.get("content_commit") or {}).get("hex") or prev_core.get("content_commit")
    inv_prev = list(prev_core.get("invariants") or [])
    inv: list[str] = []
    for name in list(CORE_INVARIANTS) + inv_prev:
        if name and name not in inv:
            inv.append(str(name))
    d["core"] = {
        "schema": "mag_core.v1",
        "coldest_vertex": "residual+card+tip",
        "session_id": d.get("session_id") or prev_core.get("session_id"),
        "content_commit": commit,
        "card": {
            "title": card.get("title") or prev_card.get("title") or "",
            "blurb": card.get("blurb") or prev_card.get("blurb") or "",
            "bullets": list(card.get("bullets") or prev_card.get("bullets") or [])[:12],
            "one_liner": card.get("one_liner") or prev_card.get("one_liner") or "",
        },
        "invariants": inv,
        "attribution": "Steiniger residual-core grammar as ops lens (CC-BY) — not product physics",
    }
    return d


def set_latest_session(session_id: str) -> None:
    """Single pointer for Board 'Now' — not a second dossier tree."""
    if not session_id:
        return
    BIO.mkdir(parents=True, exist_ok=True)
    LATEST_SESSION.write_text(
        json.dumps(
            {
                "session_id": session_id,
                "updated": datetime.now(timezone.utc).isoformat(),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    # Keep legacy latest.dossier.json in sync for readers not yet on residual/
    residual = load_residual(session_id)
    if residual:
        (BIO / "latest.dossier.json").write_text(
            json.dumps(residual, indent=2, default=str), encoding="utf-8"
        )


def get_latest_session_id() -> str | None:
    if not LATEST_SESSION.is_file():
        return None
    try:
        data = json.loads(LATEST_SESSION.read_text(encoding="utf-8"))
        sid = data.get("session_id")
        return str(sid) if sid else None
    except (json.JSONDecodeError, OSError):
        return None


def write_residual(
    session_id: str,
    dossier: dict[str, Any],
    *,
    also_legacy: bool = False,
) -> dict[str, Any]:
    """Write canonical residual (cold vertex). Legacy flat mirror opt-in only."""
    RESIDUAL_DIR.mkdir(parents=True, exist_ok=True)
    BIO.mkdir(parents=True, exist_ok=True)
    prev = load_residual(session_id)
    dossier = attach_cold_core(dict(dossier), previous=prev)
    rhash = residual_content_hash(dossier)
    dossier["residual"] = {
        "schema": "mag_residual.v1",
        "content_hash": rhash,
        "path": f"residual/{session_id}.json",
        "updated": datetime.now(timezone.utc).isoformat(),
        "coldest_vertex": True,
    }
    path = residual_path(session_id)
    text = json.dumps(dossier, indent=2, default=str)
    path.write_text(text, encoding="utf-8")
    set_latest_session(session_id)
    out: dict[str, Any] = {
        "path": str(path),
        "content_hash": rhash,
        "core": dossier.get("core"),
    }
    if also_legacy:
        legacy_dossier_path(session_id).write_text(text, encoding="utf-8")
        (BIO / "latest.dossier.json").write_text(text, encoding="utf-8")
        out["legacy"] = str(legacy_dossier_path(session_id))
    return out


def write_derived_md(session_id: str, body: str, *, also_flat: bool = False) -> Path:
    """Narrative under derived/. Flat BIO/{sid}.md is legacy opt-in."""
    DERIVED_DIR.mkdir(parents=True, exist_ok=True)
    p = derived_path(session_id, "md")
    p.write_text(body, encoding="utf-8")
    (BIO / "latest.md").write_text(body, encoding="utf-8")
    if also_flat:
        (BIO / f"{session_id}.md").write_text(body, encoding="utf-8")
    return p


def write_derived_pdf_bytes(session_id: str, data: bytes, *, also_flat: bool = False) -> Path:
    """Write PDF under derived/ only. Flat BIO copy is legacy opt-in."""
    DERIVED_DIR.mkdir(parents=True, exist_ok=True)
    p = derived_path(session_id, "pdf")
    p.write_bytes(data)
    (BIO / "latest.pdf").write_bytes(data)
    if also_flat:
        (BIO / f"{session_id}.pdf").write_bytes(data)
    return p


def write_derived_visual(
    session_id: str, pack: dict[str, Any], *, also_flat: bool = False
) -> Path:
    """Write visual pack under derived/. Flat BIO copy is legacy opt-in."""
    DERIVED_DIR.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(pack, indent=2, default=str)
    p = derived_path(session_id, "visual_pack")
    p.write_text(raw, encoding="utf-8")
    (BIO / "latest.visual_pack.json").write_text(raw, encoding="utf-8")
    if also_flat:
        (BIO / f"{session_id}.visual_pack.json").write_text(raw, encoding="utf-8")
    return p


def registry_row_from_dossier(dossier: dict[str, Any]) -> dict[str, Any]:
    sid = str(dossier.get("session_id") or "")
    card = dossier.get("session_card") or {}
    time = dossier.get("time") or {}
    sk = dossier.get("scalar_knot") or {}
    chord = dossier.get("chord") or {}
    vk = dossier.get("verkle_knot") or {}
    commit = (dossier.get("content_commit") or {}).get("hex")
    rhash = (dossier.get("residual") or {}).get("content_hash") or residual_content_hash(
        dossier
    )
    return {
        "schema": "mag_session_registry.v1",
        "session_id": sid,
        "title": card.get("title") or time.get("title") or sid[:12],
        "one_liner": card.get("one_liner") or "",
        "blurb": card.get("blurb") or dossier.get("tldr") or "",
        "bullets": card.get("bullets") or [],
        "themes": card.get("themes")
        or [t.get("id") for t in (dossier.get("themes") or []) if isinstance(t, dict)],
        "dominant_theme": card.get("dominant_theme")
        or (sk.get("theme_vector") or {}).get("dominant"),
        "start_minute": (time.get("created_at") or {}).get("iso_minute"),
        "end_minute": (time.get("updated_at") or {}).get("iso_minute"),
        "duration_minutes": sk.get("duration_minutes"),
        "tension_index": sk.get("tension_index"),
        "chord_commitment": chord.get("commitment_hash"),
        "content_commit": commit,
        "residual_hash": rhash,
        "leaf_hash": vk.get("leaf_hash"),
        "leaf_filename": vk.get("filename"),
        "verkle_root": vk.get("verkle_root"),
        "residual_path": f"residual/{sid}.json",
        "has_residual": residual_path(sid).is_file() or legacy_dossier_path(sid).is_file(),
        "has_card": bool(card.get("blurb") or card.get("title")),
        "has_leaf": bool(vk.get("leaf_hash") or vk.get("filename")),
        "has_md": find_derived(sid, "md") is not None,
        "has_pdf": find_derived(sid, "pdf") is not None,
        "has_visual": find_derived(sid, "visual_pack") is not None,
        "updated": datetime.now(timezone.utc).isoformat(),
    }


def _load_registry_map() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    if not REGISTRY.is_file():
        return out
    for line in REGISTRY.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        sid = row.get("session_id")
        if sid:
            out[str(sid)] = row
    return out


def upsert_registry(row: dict[str, Any]) -> None:
    sid = row.get("session_id")
    if not sid:
        return
    BIO.mkdir(parents=True, exist_ok=True)
    m = _load_registry_map()
    m[str(sid)] = row
    # stable sort by end_minute then sid
    items = sorted(
        m.values(),
        key=lambda r: str(r.get("end_minute") or r.get("start_minute") or r.get("updated") or ""),
        reverse=True,
    )
    payload = "\n".join(json.dumps(r, default=str) for r in items) + "\n"
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=str(REGISTRY.parent),
        prefix=f".{REGISTRY.name}.", suffix=".tmp", delete=False,
    ) as fh:
        tmp = Path(fh.name)
        fh.write(payload)
    try:
        os.replace(tmp, REGISTRY)
    finally:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass


def list_registry(*, limit: int = 200) -> list[dict[str, Any]]:
    m = _load_registry_map()
    items = sorted(
        m.values(),
        key=lambda r: str(r.get("end_minute") or r.get("start_minute") or r.get("updated") or ""),
        reverse=True,
    )
    return items[:limit]


def lean_pack_status(
    session_id: str,
    *,
    registry_map: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Complete = residual + card + content commit + chain leaf. Derived optional."""
    if not session_id:
        return {"ok": False, "complete": False, "missing": ["session_id"]}
    d = load_residual(session_id)
    has_residual = d is not None
    card = (d or {}).get("session_card") or {}
    has_card = bool(card.get("blurb") or card.get("title") or card.get("one_liner"))
    commit = ((d or {}).get("content_commit") or {}).get("hex")
    has_commit = bool(commit)
    vk = (d or {}).get("verkle_knot") or {}
    has_leaf = bool(vk.get("leaf_hash") or vk.get("filename"))
    # also accept chain registry leaf
    reg = (registry_map if registry_map is not None else _load_registry_map()).get(session_id) or {}
    if not has_leaf and reg.get("leaf_hash"):
        has_leaf = True

    missing: list[str] = []
    if not has_residual:
        missing.append("residual")
    if not has_card:
        missing.append("card")
    if not has_commit:
        missing.append("content_commit")
    if not has_leaf:
        missing.append("chain_leaf")

    has_md = find_derived(session_id, "md") is not None
    has_pdf = find_derived(session_id, "pdf") is not None
    has_visual = find_derived(session_id, "visual_pack") is not None

    return {
        "ok": True,
        "schema": "lean_pack_status.v1",
        "session_id": session_id,
        "complete": len(missing) == 0,
        "missing": missing,
        "has_residual": has_residual,
        "has_card": has_card,
        "has_commit": has_commit,
        "has_leaf": has_leaf,
        "has_md": has_md,
        "has_pdf": has_pdf,
        "has_visual": has_visual,
        "has_dossier": has_residual,  # alias for old UI
        "leaf_name": vk.get("filename") or reg.get("leaf_filename"),
        "residual_hash": (d or {}).get("residual", {}).get("content_hash")
        or reg.get("residual_hash"),
        "content_commit": commit or reg.get("content_commit"),
        "derived_optional": True,
    }


def publish_residual(
    session_id: str,
    dossier: dict[str, Any],
    *,
    narrative_md: str | None = None,
    write_md: bool = True,
) -> dict[str, Any]:
    """Write residual + registry row (+ optional derived md)."""
    wr = write_residual(session_id, dossier)
    if write_md and narrative_md is not None:
        write_derived_md(session_id, narrative_md)
    # reload after residual fields attached
    d2 = load_residual(session_id) or dossier
    row = registry_row_from_dossier(d2)
    upsert_registry(row)
    return {"residual": wr, "registry": row}


def migrate_all_to_lean() -> dict[str, Any]:
    """Copy legacy dossiers → residual/, rebuild registry, move fat derived when present."""
    RESIDUAL_DIR.mkdir(parents=True, exist_ok=True)
    DERIVED_DIR.mkdir(parents=True, exist_ok=True)
    results = []
    sids: set[str] = set()
    for p in BIO.glob("*.dossier.json"):
        if p.name.startswith("latest"):
            continue
        sids.add(p.name.replace(".dossier.json", ""))
    for p in RESIDUAL_DIR.glob("*.json"):
        sids.add(p.stem)

    for sid in sorted(sids):
        d = load_residual(sid)
        if not d:
            results.append({"session_id": sid, "ok": False, "error": "no residual"})
            continue
        try:
            from mag.session_card import attach_card_to_dossier

            if not (d.get("session_card") or {}).get("blurb"):
                attach_card_to_dossier(d)
        except Exception:
            pass
        wr = write_residual(sid, d)
        # move/copy derived
        for kind, legacy_name in (
            ("md", f"{sid}.md"),
            ("pdf", f"{sid}.pdf"),
            ("visual_pack", f"{sid}.visual_pack.json"),
        ):
            legacy = BIO / legacy_name
            if legacy.is_file() and not derived_path(sid, kind).is_file():
                DERIVED_DIR.mkdir(parents=True, exist_ok=True)
                shutil.copy2(legacy, derived_path(sid, kind))
        row = registry_row_from_dossier(load_residual(sid) or d)
        upsert_registry(row)
        results.append(
            {
                "session_id": sid,
                "ok": True,
                "complete": lean_pack_status(sid).get("complete"),
                "residual_hash": wr.get("content_hash"),
            }
        )
    return {
        "ok": True,
        "n": len(results),
        "results": results,
        "registry": str(REGISTRY),
        "residual_dir": str(RESIDUAL_DIR),
        "derived_dir": str(DERIVED_DIR),
    }
