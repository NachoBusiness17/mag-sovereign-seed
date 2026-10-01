"""local_usable.v1 — smart seats FILE layered packs; local only loads constrained slices.

Law:
  - Narrative is poor storage for small models
  - Facts ≠ interpretations ≠ controversies ≠ influence
  - Semantic retrieval obligations before generation
  - Generation never collapses layers
  - Game modules: engine truth > lore gloss
  - Dual reading: public face may be play/riddle; soil on disk always real
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT

SCHEMA = "local_usable.v1"
PACKS_DIR = ROOT / "memory" / "knowledge_packs"
VALID_KINDS = frozenset({"entity_ref", "structure", "game_module"})
VALID_LAYERS = frozenset({"fact", "interpretation", "controversy", "influence"})
EVIDENCE = frozenset({"archival", "consensus", "contested", "anecdotal", "engine", "operator"})
SOURCE_TYPES = frozenset({"primary", "secondary", "archival", "engine", "module", "operator"})

# Default semantic obligations (not keyword if-then)
DEFAULT_OBLIGATIONS: dict[str, list[str]] = {
    "historical_event": ["provenance"],
    "quotation": ["source_reference"],
    "controversial_claim": ["opposing_interpretation"],
    "psychological_theory": ["historiography"],
    "political_event": ["historical_context"],
    "game_action": ["legal_actions", "scene_state"],
    "narrate": ["scene_context", "events_from_engine"],
    "rules_ruling": ["ruleset_id", "rule_atom"],
    "world_fact": ["datasheet_id_or_engine"],
    "structure_step": ["acceptance", "non_goals"],
}

# In-fiction roles → Mag seat classes (camo face of multi-seat self-talk)
DEFAULT_WORLD_ROLES: list[dict[str, str]] = [
    {
        "world_role": "rules_clerk",
        "mag_seat": "local",
        "may": "cite legal_actions and dice outcomes",
        "must_not": "invent rooms, NPCs, or exits",
    },
    {
        "world_role": "scene_painter",
        "mag_seat": "local_narrate",
        "may": "paint scene_context only",
        "must_not": "change HP, inventory, or map",
    },
    {
        "world_role": "chronicler",
        "mag_seat": "local",
        "may": "FILE log tails and freezes",
        "must_not": "rewrite past engine events",
    },
    {
        "world_role": "module_author",
        "mag_seat": "deepseek",
        "may": "FILE local_usable packs and modules",
        "must_not": "live-DM every player turn on remote",
    },
    {
        "world_role": "contract_trail",
        "mag_seat": "kimi",
        "may": "check layer purity and obligations",
        "must_not": "become system of record",
    },
    {
        "world_role": "judge",
        "mag_seat": "grok_tui",
        "may": "benchmark, steal, unstick",
        "must_not": "multi-file scut after plan freeze",
    },
    {
        "world_role": "player",
        "mag_seat": "human",
        "may": "act and L3 consent",
        "must_not": "—",
    },
]


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug(s: str, n: int = 48) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", (s or "pack").lower()).strip("-")
    return (s or "pack")[:n]


def _h(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8", errors="replace")).hexdigest()[:16]


def pack_dir(slug: str) -> Path:
    return PACKS_DIR / _slug(slug)


def default_retrieval_policy() -> dict[str, Any]:
    return {
        "schema": "mag_retrieval_policy.v1",
        "generation_rule": "never_collapse_layers",
        "obligations": dict(DEFAULT_OBLIGATIONS),
        "local_default_sources": [
            "datasheet.json",
            "misconceptions.yaml",
            "retrieval_policy.yaml",
            "local_prompt.md",
        ],
        "never_default_to_local": ["master.md"],
        "note": "Semantic obligations — not keyword if campaigns then ethics",
    }


def build_local_prompt(
    *,
    kind: str,
    title: str,
    datasheet: dict[str, Any],
    misconceptions: list[dict[str, Any]],
    world_roles: list[dict[str, str]] | None = None,
    max_chars: int = 1800,
) -> str:
    """Build gemma-facing prompt: no master essay."""
    lines = [
        f"# Local usable slice — {title}",
        f"kind: {kind}",
        "LAW: Use only this slice. If required obligation is missing, say insufficient context.",
        "LAW: Do not invent entities, rooms, quotes, or HP not listed.",
        "",
        "## World roles (who may speak how)",
    ]
    for r in world_roles or DEFAULT_WORLD_ROLES:
        lines.append(
            f"- {r.get('world_role')}: may {r.get('may')}; must_not {r.get('must_not')}"
        )
    lines.append("")
    lines.append("## Datasheet rows (facts first)")
    rows = list(datasheet.get("rows") or [])
    # Prefer engine/fact layers first
    rows_sorted = sorted(
        rows,
        key=lambda r: (0 if r.get("layer") == "fact" else 1, str(r.get("id") or "")),
    )
    for row in rows_sorted[:40]:
        layer = row.get("layer") or "?"
        eid = row.get("id") or "?"
        claim = str(row.get("claim") or "")[:200]
        ev = row.get("evidence_level") or ""
        lines.append(f"- [{layer}/{ev}] {eid}: {claim}")
        if row.get("quote") and row.get("quote_source"):
            lines.append(f"  Q: \"{str(row['quote'])[:120]}\" ({row['quote_source']})")
    lines.append("")
    lines.append("## Misconceptions (do not repeat)")
    for m in (misconceptions or [])[:12]:
        lines.append(f"- FALSE: {str(m.get('false_claim') or '')[:120]}")
        lines.append(f"  TRUE: {str(m.get('correction') or '')[:160]}")
    text = "\n".join(lines)
    if len(text) > max_chars:
        text = text[: max_chars - 20] + "\n…[truncated]"
    return text


def validate_pack(pack: dict[str, Any]) -> list[str]:
    errs: list[str] = []
    if pack.get("schema") != SCHEMA:
        errs.append(f"schema must be {SCHEMA}")
    if pack.get("kind") not in VALID_KINDS:
        errs.append(f"kind must be one of {sorted(VALID_KINDS)}")
    if not pack.get("slug"):
        errs.append("slug required")
    ds = pack.get("datasheet") or {}
    for i, row in enumerate(ds.get("rows") or []):
        if row.get("layer") not in VALID_LAYERS:
            errs.append(f"row[{i}] bad layer")
        if row.get("quote") and not row.get("quote_source"):
            errs.append(f"row[{i}] quote without quote_source")
    return errs


def write_pack(
    *,
    slug: str,
    kind: str,
    title: str,
    entity_or_goal: str = "",
    datasheet: dict[str, Any] | None = None,
    master_md: str = "",
    provenance: dict[str, Any] | None = None,
    misconceptions: list[dict[str, Any]] | None = None,
    retrieval_policy: dict[str, Any] | None = None,
    world_roles: list[dict[str, str]] | None = None,
    prompt_variants: str = "",
    producer_chain_id: str = "",
    freeze_hash: str = "",
    extra: dict[str, Any] | None = None,
    local_token_budget: int = 1024,
) -> dict[str, Any]:
    """Write knowledge_packs/<slug>/ tree. Returns envelope + paths."""
    slug = _slug(slug)
    kind = (kind or "structure").strip()
    if kind not in VALID_KINDS:
        return {"ok": False, "error": f"bad kind {kind}"}

    datasheet = datasheet or {"schema": "mag_datasheet.v1", "rows": []}
    misconceptions = misconceptions or []
    world_roles = world_roles or list(DEFAULT_WORLD_ROLES)
    policy = retrieval_policy or default_retrieval_policy()
    provenance = provenance or {
        "schema": "mag_provenance.v1",
        "sources": [],
        "revision": 1,
        "ts": _utc(),
    }

    d = pack_dir(slug)
    d.mkdir(parents=True, exist_ok=True)

    local_prompt = build_local_prompt(
        kind=kind,
        title=title or slug,
        datasheet=datasheet,
        misconceptions=misconceptions,
        world_roles=world_roles,
        max_chars=min(2400, local_token_budget * 4),
    )

    # Write satellites
    (d / "master.md").write_text(
        master_md
        or f"# {title or slug}\n\n_Designer notes — not default local context._\n",
        encoding="utf-8",
    )
    (d / "datasheet.json").write_text(
        json.dumps(datasheet, indent=2, default=str), encoding="utf-8"
    )
    (d / "provenance.yaml").write_text(
        _simple_yaml(provenance), encoding="utf-8"
    )
    (d / "misconceptions.yaml").write_text(
        _misconceptions_yaml(misconceptions), encoding="utf-8"
    )
    (d / "retrieval_policy.yaml").write_text(
        _simple_yaml(policy), encoding="utf-8"
    )
    (d / "world_roles.json").write_text(
        json.dumps(world_roles, indent=2), encoding="utf-8"
    )
    (d / "prompt_variants.txt").write_text(
        prompt_variants or "# optional perspective overlays — facts unchanged\n",
        encoding="utf-8",
    )
    (d / "local_prompt.md").write_text(local_prompt, encoding="utf-8")

    envelope: dict[str, Any] = {
        "schema": SCHEMA,
        "slug": slug,
        "kind": kind,
        "title": title or slug,
        "entity_or_goal": entity_or_goal or title or slug,
        "ts": _utc(),
        "local_token_budget": local_token_budget,
        "generation_rule": "never_collapse_layers",
        "world_roles": world_roles,
        "retrieval_obligations": policy.get("obligations") or DEFAULT_OBLIGATIONS,
        "producer_chain_id": producer_chain_id or "",
        "freeze_hash": freeze_hash or "",
        "files": {
            "master": "master.md",
            "datasheet": "datasheet.json",
            "provenance": "provenance.yaml",
            "misconceptions": "misconceptions.yaml",
            "retrieval_policy": "retrieval_policy.yaml",
            "world_roles": "world_roles.json",
            "local_prompt": "local_prompt.md",
            "prompt_variants": "prompt_variants.txt",
        },
        "hashes": {
            "datasheet": _h(json.dumps(datasheet, sort_keys=True, default=str)),
            "local_prompt": _h(local_prompt),
        },
        "dual_reading": {
            "public_face": "play_or_riddle_activation" if kind == "game_module" else "structure_or_ref",
            "soil": "disk_engine_and_packs",
            "note": "Shape of multi-seat self-talk is enough camo; real decode always on disk",
        },
        "extra": extra or {},
    }
    errs = validate_pack({**envelope, "datasheet": datasheet})
    if errs:
        return {"ok": False, "error": "; ".join(errs), "envelope": envelope}

    (d / "pack.json").write_text(
        json.dumps(envelope, indent=2, default=str), encoding="utf-8"
    )
    rel = str(d.relative_to(ROOT)).replace("\\", "/")
    return {
        "ok": True,
        "schema": SCHEMA,
        "slug": slug,
        "path": rel,
        "pack": envelope,
        "local_prompt_chars": len(local_prompt),
    }


def load_pack(slug: str) -> dict[str, Any] | None:
    p = pack_dir(slug) / "pack.json"
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def load_local_slice(slug: str) -> dict[str, Any]:
    """What local seats should see — never master by default."""
    d = pack_dir(slug)
    if not d.is_dir():
        return {"ok": False, "error": "missing pack"}
    out: dict[str, Any] = {"ok": True, "slug": slug}
    try:
        out["pack"] = json.loads((d / "pack.json").read_text(encoding="utf-8"))
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:160]}
    try:
        out["datasheet"] = json.loads((d / "datasheet.json").read_text(encoding="utf-8"))
    except Exception:
        out["datasheet"] = {"rows": []}
    try:
        out["local_prompt"] = (d / "local_prompt.md").read_text(encoding="utf-8")
    except Exception:
        out["local_prompt"] = ""
    try:
        out["world_roles"] = json.loads((d / "world_roles.json").read_text(encoding="utf-8"))
    except Exception:
        out["world_roles"] = DEFAULT_WORLD_ROLES
    out["includes_master"] = False
    return out


def obligation_ok(
    claim_type: str,
    available: set[str] | list[str],
    *,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Semantic gate before local generation."""
    obl = (policy or default_retrieval_policy()).get("obligations") or DEFAULT_OBLIGATIONS
    need = list(obl.get(claim_type) or [])
    have = set(available or [])
    missing = [x for x in need if x not in have]
    return {
        "ok": not missing,
        "claim_type": claim_type,
        "required": need,
        "missing": missing,
        "action_if_missing": "insufficient_context",
    }


def export_game_module_to_pack(module_path: str | Path | None = None) -> dict[str, Any]:
    """Bridge mag_game_module.v1 → local_usable game_module pack."""
    path = Path(module_path) if module_path else (
        ROOT / "memory" / "game_modules" / "dnd_classic_stub.v1.json"
    )
    if not path.is_file():
        return {"ok": False, "error": f"no module at {path}"}
    mod = json.loads(path.read_text(encoding="utf-8"))
    mid = str(mod.get("module_id") or path.stem)
    rows: list[dict[str, Any]] = []
    rooms = mod.get("rooms") or {}
    for rid, room in rooms.items():
        rows.append(
            {
                "id": f"room:{rid}",
                "layer": "fact",
                "claim": f"{room.get('name')}: {str(room.get('desc') or '')[:160]}",
                "evidence_level": "engine",
                "source_type": "module",
                "source_ref": mid,
                "confidence": 1.0,
                "requires": ["scene_state"],
            }
        )
        for d, dest in (room.get("exits") or {}).items():
            rows.append(
                {
                    "id": f"exit:{rid}:{d}",
                    "layer": "fact",
                    "claim": f"From {rid} {d} leads to {dest}",
                    "evidence_level": "engine",
                    "source_type": "module",
                    "source_ref": mid,
                    "confidence": 1.0,
                    "requires": ["legal_actions"],
                }
            )
        for i, hook in enumerate(room.get("hooks") or []):
            rows.append(
                {
                    "id": f"hook:{rid}:{i}",
                    "layer": "interpretation",
                    "claim": str(hook)[:200],
                    "evidence_level": "engine",
                    "source_type": "module",
                    "source_ref": mid,
                    "confidence": 0.7,
                    "requires": ["scene_context"],
                }
            )
    misconceptions = [
        {
            "false_claim": "Narrator may invent rooms or NPCs not in the module",
            "correction": "Only engine rooms/exits/encounters exist; paint scene_context only",
            "why_local_fails": "Essay DM freestyle collapses world integrity",
        },
        {
            "false_claim": "Hooks are historical facts about the real world",
            "correction": "Hooks are in-module adventure prompts (fiction layer)",
            "why_local_fails": "Layer collapse: play surface treated as soil truth",
        },
        {
            "false_claim": "Illegal moves can be narrated as success",
            "correction": "Engine refuses illegal actions; narrator must not override",
            "why_local_fails": "Rules pillar fails → collab session dies",
        },
    ]
    master = (
        f"# {mod.get('title')}\n\n"
        f"{mod.get('license_note') or ''}\n\n"
        f"System: {mod.get('system')}\n"
        f"Start: {mod.get('start_room')}\n\n"
        "Dual reading: public face = adventure module; Mag soil = engine + local_usable pack.\n"
        "Personality roles talk through this world without needing persona theater.\n"
    )
    return write_pack(
        slug=mid.replace("_", "-"),
        kind="game_module",
        title=str(mod.get("title") or mid),
        entity_or_goal=mid,
        datasheet={"schema": "mag_datasheet.v1", "module_id": mid, "rows": rows},
        master_md=master,
        provenance={
            "schema": "mag_provenance.v1",
            "sources": [
                {
                    "type": "module",
                    "path": str(path.relative_to(ROOT)).replace("\\", "/"),
                    "module_id": mid,
                }
            ],
            "revision": 1,
            "ts": _utc(),
        },
        misconceptions=misconceptions,
        extra={"module_id": mid, "system": mod.get("system"), "start_room": mod.get("start_room")},
    )


def _simple_yaml(obj: Any, indent: int = 0) -> str:
    """Minimal YAML-ish dump (no PyYAML required)."""
    sp = "  " * indent
    if isinstance(obj, dict):
        lines = []
        for k, v in obj.items():
            if isinstance(v, (dict, list)):
                lines.append(f"{sp}{k}:")
                lines.append(_simple_yaml(v, indent + 1))
            else:
                lines.append(f"{sp}{k}: {_yaml_scalar(v)}")
        return "\n".join(lines) + ("\n" if indent == 0 else "")
    if isinstance(obj, list):
        lines = []
        for item in obj:
            if isinstance(item, (dict, list)):
                lines.append(f"{sp}-")
                lines.append(_simple_yaml(item, indent + 1))
            else:
                lines.append(f"{sp}- {_yaml_scalar(item)}")
        return "\n".join(lines)
    return f"{sp}{_yaml_scalar(obj)}"


def _yaml_scalar(v: Any) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v).replace("\n", " ").replace('"', "'")
    if any(c in s for c in (":", "#", "{", "}", "[", "]")) or s == "":
        return f'"{s}"'
    return s


def _misconceptions_yaml(rows: list[dict[str, Any]]) -> str:
    lines = ["# misconceptions — intercept high-prob local errors", "items:"]
    for m in rows:
        lines.append(f"  - false_claim: {_yaml_scalar(m.get('false_claim'))}")
        lines.append(f"    correction: {_yaml_scalar(m.get('correction'))}")
        if m.get("why_local_fails"):
            lines.append(f"    why_local_fails: {_yaml_scalar(m.get('why_local_fails'))}")
    return "\n".join(lines) + "\n"
