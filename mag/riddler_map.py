"""Campaign map layer over mag.riddler — villains-guild payloads ↔ codec.

The codec is law. mag.riddler exposes compile_surrogate, fingerprint_randomize,
validate_surrogate, save_surrogate, load_private_map (plus PrivateGraph /
SurrogateStory / ValidationReport). It does not send, decode, or aggregate.

This module re-exports those primitives and binds campaign room payloads onto
them. Schema riddler_campaign_map.v1 wraps codec faces riddler_surrogate.v1.
No new crypto. No new protocol.
"""

from __future__ import annotations

from typing import Any

from mag.riddler import (
    PrivateGraph,
    SurrogateStory,
    ValidationReport,
    compile_surrogate,
    fingerprint_randomize,
    load_private_map,
    save_surrogate,
    validate_surrogate,
)

SCHEMA = "riddler_campaign_map.v1"
CODEC_SCHEMA = "riddler_surrogate.v1"
CODEC_MODULE = "mag.riddler"
CODEC_COMPILE = "compile_surrogate"

# Public functions actually on mag.riddler. Send/decode/aggregate are not here.
CODEC_PRIMITIVES = (
    "compile_surrogate",
    "fingerprint_randomize",
    "validate_surrogate",
    "save_surrogate",
    "load_private_map",
)
CODEC_TYPES = (
    "PrivateGraph",
    "SurrogateStory",
    "ValidationReport",
)

# Room → verification skill. Bound from campaigns/villains_guild/module.json
# rooms_detail_note + docs/ref/GAME_VILLAIN_GUILD_DESIGN.md room table.
GUILD_SKILL_BIND = {
    "guildhall_of_gracious_crimes": "parse_contracts",
    "hall_of_fine_print": "cross_reference_documents",
    "registry_of_regrets": "check_sources",
    "counting_house_of_minor_miracles": "verify_arithmetic",
    "overthrow_floor": "build_consensus",
}

# Recorded in campaigns/villains_guild/daylight/riddler_map.json (map_seed / room_seeds).
GUILD_MAP_SEED = 20260827
GUILD_ROOM_SEEDS = {
    "guildhall_of_gracious_crimes": 202608271,
    "hall_of_fine_print": 202608272,
    "registry_of_regrets": 202608273,
    "counting_house_of_minor_miracles": 202608274,
    "overthrow_floor": 202608275,
}

# id, name, order — campaigns/villains_guild/module.json rooms list.
GUILD_ROOMS = (
    ("guildhall_of_gracious_crimes", "I — The Guildhall of Gracious Crimes", 1),
    ("hall_of_fine_print", "II — The Hall of Fine Print", 2),
    ("registry_of_regrets", "III — The Registry of Regrets", 3),
    ("counting_house_of_minor_miracles", "IV — The Counting House of Minor Miracles", 4),
    ("overthrow_floor", "V — The Overthrow Floor", 5),
)
_GUILD_ROOM_META = {rid: (name, order) for rid, name, order in GUILD_ROOMS}

__all__ = [
    "SCHEMA",
    "CODEC_SCHEMA",
    "CODEC_MODULE",
    "CODEC_COMPILE",
    "CODEC_PRIMITIVES",
    "CODEC_TYPES",
    "GUILD_SKILL_BIND",
    "GUILD_MAP_SEED",
    "GUILD_ROOM_SEEDS",
    "GUILD_ROOMS",
    "PrivateGraph",
    "SurrogateStory",
    "ValidationReport",
    "compile_surrogate",
    "fingerprint_randomize",
    "validate_surrogate",
    "save_surrogate",
    "load_private_map",
    "graph_from_payload",
    "compile_payload",
    "public_face",
    "private_face",
    "validation_face",
    "bind_room",
    "bind_campaign",
    "bind_guild",
]


def graph_from_payload(payload: PrivateGraph | dict[str, Any]) -> PrivateGraph:
    """Lift a campaign payload into mag.riddler.PrivateGraph. No extra fields."""
    if isinstance(payload, PrivateGraph):
        return payload
    raw = payload.get("graph", payload)
    if isinstance(raw, PrivateGraph):
        return raw
    if not isinstance(raw, dict):
        raw = payload
    return PrivateGraph(
        actors=list(raw.get("actors") or []),
        resources=list(raw.get("resources") or []),
        dependencies=list(raw.get("dependencies") or []),
        constraints=list(raw.get("constraints") or []),
        conflicts=list(raw.get("conflicts") or []),
        goal=str(raw.get("goal") or payload.get("territory_goal") or ""),
        domain_hint=str(raw.get("domain_hint") or ""),
    )


def _room_id_of(payload: dict[str, Any]) -> str:
    return str(payload.get("room_id") or payload.get("id") or "")


def _seed_of(payload: PrivateGraph | dict[str, Any], seed: int | None) -> int | None:
    if seed is not None:
        return seed
    if not isinstance(payload, dict):
        return None
    for key in ("seed", "fingerprint_seed"):
        if payload.get(key) is not None:
            return int(payload[key])
    rid = _room_id_of(payload)
    if rid in GUILD_ROOM_SEEDS:
        return GUILD_ROOM_SEEDS[rid]
    return None


def _domain_of(payload: PrivateGraph | dict[str, Any], domain: str | None) -> str | None:
    if domain is not None:
        return domain
    if isinstance(payload, dict) and payload.get("domain"):
        return str(payload["domain"])
    return None


def compile_payload(
    payload: PrivateGraph | dict[str, Any],
    *,
    domain: str | None = None,
    seed: int | None = None,
) -> SurrogateStory:
    """compile_surrogate over a campaign payload."""
    graph = graph_from_payload(payload)
    return compile_surrogate(
        graph,
        domain=_domain_of(payload, domain),
        seed=_seed_of(payload, seed),
    )


def public_face(story: SurrogateStory) -> dict[str, Any]:
    """SurrogateStory.to_public — private maps stay off this face."""
    return story.to_public()


def private_face(
    story: SurrogateStory,
    graph: PrivateGraph | None = None,
) -> dict[str, Any]:
    """Local-only map. Same keys save_surrogate writes, plus the source graph."""
    data: dict[str, Any] = {
        "scratch_id": story.scratch_id,
        "role_map": dict(story.role_map),
        "constraint_map": dict(story.constraint_map),
        "private_map_ref": story.private_map_ref,
        "fingerprint_seed": story.fingerprint_seed,
        "domain": story.domain,
    }
    if graph is not None:
        data["graph"] = {
            "actors": list(graph.actors),
            "resources": list(graph.resources),
            "dependencies": list(graph.dependencies),
            "constraints": list(graph.constraints),
            "conflicts": list(graph.conflicts),
            "goal": graph.goal,
            "domain_hint": graph.domain_hint,
        }
    return data


def validation_face(report: ValidationReport) -> dict[str, Any]:
    """ValidationReport as a plain dict — codec fields only."""
    return {
        "ok": report.ok,
        "errors": list(report.errors),
        "warnings": list(report.warnings),
        "leakage_detected": report.leakage_detected,
        "constraints_preserved": report.constraints_preserved,
        "constraints_lost": report.constraints_lost,
    }


def bind_room(
    payload: dict[str, Any],
    *,
    domain: str | None = None,
    seed: int | None = None,
) -> dict[str, Any]:
    """Compile + validate one campaign room through the existing codec."""
    graph = graph_from_payload(payload)
    story = compile_payload(payload, domain=domain, seed=seed)
    report = validate_surrogate(story)
    room_id = _room_id_of(payload)
    name, order = _GUILD_ROOM_META.get(room_id, ("", None))
    block: dict[str, Any] = {
        "room_id": room_id,
        "room_name": str(payload.get("room_name") or payload.get("name") or name),
        "order": payload["order"] if "order" in payload else order,
        "territory_task": str(
            payload.get("territory_task") or GUILD_SKILL_BIND.get(room_id, "")
        ),
        "territory_goal": str(payload.get("territory_goal") or graph.goal),
        "success_encodes": str(payload.get("success_encodes") or ""),
        "failure_encodes": str(payload.get("failure_encodes") or ""),
        "fingerprint_seed": story.fingerprint_seed,
        "domain": story.domain,
        "shape_hash": story.shape_hash,
        "validation": validation_face(report),
        "surrogate": public_face(story),
        "private_map": private_face(story, graph),
        "scratch_id": story.scratch_id,
    }
    return block


def _iter_room_payloads(
    rooms: list[dict[str, Any]] | dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    if isinstance(rooms, dict):
        items: list[dict[str, Any]] = []
        for rid, payload in rooms.items():
            p = dict(payload)
            p.setdefault("room_id", rid)
            items.append(p)
        return items
    return list(rooms)


def bind_campaign(
    rooms: list[dict[str, Any]] | dict[str, dict[str, Any]],
    *,
    campaign_id: str = "villains_guild",
    map_seed: int | None = None,
) -> dict[str, Any]:
    """Bind many room payloads into a riddler_campaign_map.v1 document."""
    bound: dict[str, Any] = {}
    room_seeds: dict[str, int] = {}
    for payload in _iter_room_payloads(rooms):
        block = bind_room(payload)
        rid = block["room_id"]
        bound[rid] = block
        room_seeds[rid] = int(block["fingerprint_seed"])
    out: dict[str, Any] = {
        "schema": SCHEMA,
        "codec_schema": CODEC_SCHEMA,
        "produced_by": {
            "module": CODEC_MODULE,
            "function": CODEC_COMPILE,
            "private_graph": "mag.riddler.PrivateGraph",
            "codec_schema": CODEC_SCHEMA,
        },
        "campaign_id": campaign_id,
        "skill_bind": {
            rid: block["territory_task"]
            for rid, block in bound.items()
            if block.get("territory_task")
        },
        "room_seeds": room_seeds,
        "rooms": bound,
    }
    if map_seed is not None:
        out["map_seed"] = map_seed
    return out


def bind_guild(
    rooms: list[dict[str, Any]] | dict[str, dict[str, Any]],
    *,
    map_seed: int = GUILD_MAP_SEED,
) -> dict[str, Any]:
    """Villains-guild campaign map. Same codec path as bind_campaign."""
    return bind_campaign(rooms, campaign_id="villains_guild", map_seed=map_seed)
