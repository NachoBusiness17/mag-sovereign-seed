"""Water-computer keep — physics for the hydraulic module.

Isomorphism, not identity. Engine owns tank heights + valves.
Pieces (pumps) may tick. They may not pour. Bucket into OUT is a cheat, not a win.

GRAPH MODE (2026-09-27): when the campaign flags carry a `water:graph` spec
(dict, mag/water_graph.py schema), set_valve/pour/wait/tick route through the
real pipe network (WaterGraph). No spec -> the legacy 3-tank line runs
byte-identical (its tests are the regression floor).

REPRINT PASS-OFF (X3, 2026-09-29): handle(atype="reprint") is the
game_campaign.reprint death pass-off — reprint_salvage() carries the water
state from the corpse onto the clone. The water remembers.

CLI: python -m mag.water_computer play | glass | proof | demo
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from typing import Any

try:
    from config import ROOT
except Exception:  # noqa: BLE001
    from pathlib import Path

    ROOT = Path(__file__).resolve().parent.parent

from mag.water_graph import WaterGraph, from_spec

SCHEMA = "water_computer.v1"
MODULE_IDS = {"water_computer", "water", "hydraulic", "water_graph"}
SOURCE_N = 3
WIN_OUT = 2
BAR = "█"
EMPTY = "·"

VALVE_AT = {
    "source_cistern": "source_work",
    "work_gallery": "work_out",
}

# Flag key carrying the graph-mode spec (JSON dict in the string-valued flag map).
GRAPH_FLAG = "water:graph"

# Proof anchoring (dirac loop 6, organ:water_computer->organ:manifest `proof` edge).
# One chain leaf per proof session, amended not appended (the manifest/team_knot dedupe).
PROOF_FLAG = "water:anchored"
PROOF_SESSION = "water_computer"
PROOF_RECORD = ROOT / "state" / "water_proof_anchor.json"


def is_module(camp: dict[str, Any] | None) -> bool:
    mid = str((camp or {}).get("module_id") or "").lower()
    return mid in MODULE_IDS or "water_computer" in mid


def seed(camp: dict[str, Any]) -> None:
    flags = [str(f) for f in (camp.get("flags") or [])]
    have = {f.split("=")[0] for f in flags if "=" in f}
    for k, v in (
        ("water:source", str(SOURCE_N)),
        ("water:work", "0"),
        ("water:out", "0"),
        ("valve:source_work", "closed"),
        ("valve:work_out", "closed"),
    ):
        if k not in have:
            flags.append(f"{k}={v}")
    camp["flags"] = list(dict.fromkeys(flags))


def _flag_map(camp: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for f in camp.get("flags") or []:
        s = str(f)
        if "=" in s:
            k, v = s.split("=", 1)
            out[k] = v
    return out


def _write_map(camp: dict[str, Any], m: dict[str, str]) -> None:
    keep = [str(f) for f in (camp.get("flags") or []) if "=" not in str(f)]
    for k, v in m.items():
        keep.append(f"{k}={v}")
    camp["flags"] = list(dict.fromkeys(keep))


def heights(camp: dict[str, Any]) -> dict[str, int]:
    m = _flag_map(camp)
    def n(k: str) -> int:
        try:
            return max(0, int(m.get(k, "0")))
        except (TypeError, ValueError):
            return 0
    return {
        "source": n("water:source"),
        "work": n("water:work"),
        "out": n("water:out"),
    }


def valves(camp: dict[str, Any]) -> dict[str, str]:
    m = _flag_map(camp)
    return {
        "source_work": m.get("valve:source_work", "closed"),
        "work_out": m.get("valve:work_out", "closed"),
    }


# --------------------------------------------------------- graph mode ------
# Route the hydraulic module through mag/water_graph.py when the campaign
# carries a `water:graph` spec. State persists as the spec dict itself under
# the flag key (JSON in the string-valued flag map); every action is
# load-spec -> mutate engine -> save-spec, riding save_campaign like the
# legacy path. Room->pipe contract for `open valve`/`close valve`:
#   1. spec["valves"][room_id] when mapped;
#   2. else the first pipe whose src node is named after the room_id;
#   3. else None -> "no valve in this room". No blanket first-pipe fallback:
#      an unmapped room must not grow a surprise valve.


def graph_spec(camp: dict[str, Any]) -> dict[str, Any] | None:
    """The live WaterGraph spec dict, or None -> legacy 3-tank mode."""
    raw = _flag_map(camp).get(GRAPH_FLAG, "")
    if not raw:
        return None
    try:
        spec = json.loads(raw)
    except Exception:
        return None
    return spec if isinstance(spec, dict) else None


def seed_graph(camp: dict[str, Any], spec: dict[str, Any] | None = None) -> None:
    """Install (or replace) the water:graph spec — flips the module to graph mode."""
    if spec is None:
        spec = default_graph_spec()
    m = _flag_map(camp)
    m[GRAPH_FLAG] = json.dumps(spec, sort_keys=True, separators=(",", ":"))
    _write_map(camp, m)


def default_graph_spec() -> dict[str, Any]:
    """5-node demo keep: source -> XOR junction -> out, a reservoir side inlet
    (the XOR's second voice) and a waste drain. The valve map wires campaign
    rooms to pipes: source_cistern->main, gallery->side, work_gallery->spout,
    out_cistern->drain. Fill OUT to WIN_OUT by gravity and won() fires."""
    g = WaterGraph()
    g.add_node("source", elev=5, volume=6)
    g.add_node("reservoir", elev=4, volume=2)
    g.add_node("junction", elev=2, kind="xor")
    g.add_node("out", elev=1)
    g.add_node("waste", elev=0, kind="waste")
    g.add_pipe("main", "source", "junction", cap=1, open_=False)
    g.add_pipe("side", "reservoir", "junction", cap=1, open_=False)
    g.add_pipe("spout", "junction", "out", cap=2)
    g.add_pipe("drain", "out", "waste", cap=2, open_=False)
    spec = g.to_spec()
    spec["valves"] = {
        "source_cistern": "main",
        "gallery": "side",
        "work_gallery": "spout",
        "out_cistern": "drain",
    }
    spec["win_node"] = "out"
    return spec


def _room_pipe(spec: dict[str, Any], camp: dict[str, Any]) -> str | None:
    rid = str(camp.get("room_id") or "")
    mapped = spec.get("valves") or {}
    if rid in mapped:
        return str(mapped[rid])
    for pname, p in (spec.get("pipes") or {}).items():
        if str(p.get("src") or "") == rid:
            return pname
    return None


def _save_graph(camp: dict[str, Any], spec0: dict[str, Any], g: WaterGraph) -> None:
    """Persist engine state back under the flag. Overlay the engine's to_spec
    onto the original spec: the engine roundtrip drops spec-only keys (node
    sill thresholds, valves, win_node) and the overlay keeps them honest."""
    fresh = g.to_spec()
    spec = dict(spec0)
    spec["tick"] = fresh["tick"]
    nodes = dict(spec.get("nodes") or {})
    for name, nd in fresh["nodes"].items():
        nd2 = dict(nodes.get(name) or {})
        nd2.update(nd)
        nodes[name] = nd2
    spec["nodes"] = nodes
    pipes = dict(spec.get("pipes") or {})
    for name, pd in fresh["pipes"].items():
        pd2 = dict(pipes.get(name) or {})
        pd2.update(pd)
        pipes[name] = pd2
    spec["pipes"] = pipes
    m = _flag_map(camp)
    m[GRAPH_FLAG] = json.dumps(spec, sort_keys=True, separators=(",", ":"))
    _write_map(camp, m)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def proof_payload(camp: dict[str, Any]) -> dict[str, Any] | None:
    """The REAL water proof artifact: the claim plus the live graph spec and the
    final node volumes. Graph mode only; the legacy 3-tank keep has no pipe
    network, so there is no artifact to anchor."""
    spec = graph_spec(camp)
    if spec is None:
        return None
    g = from_spec(spec)
    return {
        "schema": "water_proof.v1",
        "claim": "the water computer computed its route to OUT by gravity",
        "evidence": {
            "graph_spec": spec,
            "final_volumes": {name: n.volume for name, n in g.nodes.items()},
        },
    }


def anchor_proof(camp: dict[str, Any], *, force: bool = False) -> dict[str, Any]:
    """Anchor the water proof to the chain (dirac loop 6: the
    organ:water_computer->organ:manifest `proof` edge). manifest.anchor() takes
    no payload, so the CALLER adapts: the real artifact is hash-pinned through
    the same verkle_knot.append writer manifest.anchor() uses (leaf
    dossier_commit = sha256 of the canonical claim+spec+volumes), then
    manifest.anchor() itself is refreshed so the bones stay a chain fact on the
    same chain the proof rode. Deduped once per campaign via the water:anchored
    flag (the proof is the win-time snapshot; later ticks are the same win). A
    chain failure is reported honestly and never breaks play."""
    payload = proof_payload(camp)
    if payload is None:
        return {"ok": False, "schema": SCHEMA, "anchored": False,
                "error": "no water:graph spec, nothing to anchor"}
    proof_hash = hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()
    m = _flag_map(camp)
    if not force and m.get(PROOF_FLAG):
        return {"ok": True, "schema": SCHEMA, "anchored": True, "persisted": True,
                "proof_hash": m.get(PROOF_FLAG, ""),
                "note": "this campaign's win proof is already anchored (no chain spam)"}
    try:
        from mag import verkle_knot
        knot = verkle_knot.append_verkle_knot({
            "session_id": PROOF_SESSION,
            "content_commit": {"hex": proof_hash},
            "scalar_knot": {"theme_vector": {"dominant": "water_proof"}},
            "summary": "[water_proof] " + proof_hash[:16] + " route to OUT computed by gravity",
        })
    except Exception as e:  # noqa: BLE001, anchoring must never break play
        knot = {"ok": False, "error": str(e)[:120]}
    try:
        from mag import manifest
        manifest_fact = manifest.anchor()
    except Exception as e:  # noqa: BLE001
        manifest_fact = {"ok": False, "error": str(e)[:120]}
    chain_ok = bool(knot.get("ok"))
    rec = {
        "schema": "water_proof.v1", "ts": _now(),
        "proof_hash": proof_hash, "leaf_hash": str(knot.get("leaf_hash") or ""),
        "root": str(knot.get("verkle_root") or knot.get("root") or ""),
        "chain_ok": chain_ok, "chain_note": str(knot.get("error") or "")[:120],
        "manifest_hash": str(manifest_fact.get("manifest_hash") or ""),
        "manifest_leaf": str(manifest_fact.get("leaf_hash") or ""),
        "payload": payload,
    }
    try:
        PROOF_RECORD.parent.mkdir(parents=True, exist_ok=True)
        PROOF_RECORD.write_text(json.dumps(rec, indent=2, default=str), encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    if chain_ok:
        m[PROOF_FLAG] = proof_hash[:16]
        _write_map(camp, m)
    return {"ok": True, "schema": SCHEMA, "anchored": chain_ok,
            "proof_hash": proof_hash, "leaf_hash": rec["leaf_hash"],
            "chain_note": rec["chain_note"],
            "manifest_ok": bool(manifest_fact.get("ok")),
            "record": str(PROOF_RECORD)}


def _render_glass(g: WaterGraph) -> str:
    tanks = " | ".join(
        f"{name.upper()} {n.volume}" + (f"+{n.steam}stm" if n.steam else "")
        for name, n in g.nodes.items()
        if n.kind != "waste"
    )
    vlv = " ".join(f"{p.name} {'open' if p.open else 'shut'}" for p in g.pipes.values())
    return f"{tanks} | {vlv} | GLASS: the network is the computer. Gravity routes."


def graph_glass(camp: dict[str, Any]) -> str:
    """Glass for graph mode; falls back to the legacy sight_glass when no spec."""
    spec = graph_spec(camp)
    if spec is None:
        return sight_glass(camp)
    return _render_glass(from_spec(spec))


def _graph_tick(camp: dict[str, Any], spec: dict[str, Any]) -> list[str]:
    """One WaterGraph tick, persisted back into the flags. The win node's
    volume mirrors into water:out + the flowed flag so the legacy won()
    verdict (height earned, never bucketed) governs graph mode too."""
    g = from_spec(spec)
    before = {name: (n.volume, n.steam) for name, n in g.nodes.items()}
    events = g.tick()
    moved = any((n.volume, n.steam) != before[name] for name, n in g.nodes.items())
    _save_graph(camp, spec, g)
    wn = g.nodes.get(str(spec.get("win_node") or "out"))
    if moved and wn is not None and wn.kind != "waste":
        m = _flag_map(camp)
        m["water:out"] = str(max(0, int(wn.volume)))
        _write_map(camp, m)
        flags = [str(f) for f in (camp.get("flags") or [])]
        flags.append("flowed")
        camp["flags"] = list(dict.fromkeys(flags))
    if not events:
        events.append("Gravity. Nothing moves. A valve is closed, or a tank is dry.")
    events.append(_render_glass(g))
    if won(camp):
        events.append("The output height is yours. You walked the water here.")
        pr = anchor_proof(camp)
        if pr.get("anchored") and not pr.get("persisted"):
            events.append("Proof anchored: " + str(pr.get("proof_hash", ""))[:16]
                          + " (leaf " + str(pr.get("leaf_hash", ""))[:12] + ").")
        elif not pr.get("anchored"):
            events.append("Proof NOT anchored: "
                          + str(pr.get("chain_note") or pr.get("error") or "unknown"))
    return events


def _graph_set_valve(camp: dict[str, Any], spec: dict[str, Any], want: str) -> dict[str, Any]:
    g = from_spec(spec)
    pname = _room_pipe(spec, camp)
    if not pname or pname not in g.pipes:
        return {"ok": False, "handled": True, "error": "no valve in this room"}
    want = "open" if want in ("open", "on") else "closed"
    if want == "open":
        g.open(pname)
    else:
        g.close(pname)
    _save_graph(camp, spec, g)
    return {
        "ok": True,
        "handled": True,
        "events": [f"Valve {pname} {want}.", _render_glass(g)],
    }


def _valve_target(camp: dict[str, Any]) -> str | None:
    """What 'open valve' means in this room: the graph pipe (graph mode) or
    the legacy VALVE_AT tank-pair name."""
    spec = graph_spec(camp)
    if spec is not None:
        return _room_pipe(spec, camp)
    return _valve_here(camp)


def cheated(camp: dict[str, Any]) -> bool:
    return any(str(f).lower() in ("cheat:bucket", "cheat") for f in (camp.get("flags") or []))


def scorched(camp: dict[str, Any]) -> bool:
    return any(str(f).lower().startswith("nuke:") or str(f).lower() == "scorched"
               for f in (camp.get("flags") or []))


def phase(camp: dict[str, Any]) -> str:
    return str(_flag_map(camp).get("water:phase") or "liquid").lower()


def _n(camp: dict[str, Any], key: str) -> int:
    try:
        return max(0, int(_flag_map(camp).get(key, "0")))
    except (TypeError, ValueError):
        return 0


def steam_n(camp: dict[str, Any]) -> int:
    return _n(camp, "steam")


def rain_n(camp: dict[str, Any]) -> int:
    return _n(camp, "water:rain")


def ice_n(camp: dict[str, Any]) -> int:
    return _n(camp, "water:ice")


def charge_n(camp: dict[str, Any]) -> int:
    return _n(camp, "charge")


def mass(camp: dict[str, Any]) -> int:
    h = heights(camp)
    return h["source"] + h["work"] + h["out"] + steam_n(camp) + rain_n(camp) + ice_n(camp)


def won(camp: dict[str, Any]) -> bool:
    if phase(camp) in ("gas", "rain", "ice"):
        return False
    h = heights(camp)
    return (not cheated(camp)) and h["out"] >= WIN_OUT and any(
        str(f).startswith("flowed") for f in (camp.get("flags") or [])
    )


def sight_glass(camp: dict[str, Any]) -> str:
    spec = graph_spec(camp)
    if spec is not None:
        return _render_glass(from_spec(spec))
    h = heights(camp)
    v = valves(camp)

    def bar(n: int) -> str:
        n = max(0, min(SOURCE_N, n))
        return BAR * n + EMPTY * (SOURCE_N - n)

    lines = [
        f"SOURCE {bar(h['source'])} {h['source']}",
        f"WORK   {bar(h['work'])} {h['work']}",
        f"OUT    {bar(h['out'])} {h['out']}",
        f"A {v['source_work']}  B {v['work_out']}",
    ]
    ph = phase(camp)
    ch = charge_n(camp)
    charge_bit = f" | CHARGE {bar(min(SOURCE_N, ch))} {ch}" if ch else ""
    if ph == "ice":
        return " | ".join([
            f"ICE    {bar(ice_n(camp))} {ice_n(camp)}",
            f"SOURCE {bar(h['source'])} {h['source']}",
            "GLASS: frozen. Gravity waits on the season.",
        ]) + charge_bit
    if ph == "rain" or rain_n(camp) > 0:
        return " | ".join([
            f"RAIN   {bar(rain_n(camp))} {rain_n(camp)}",
            f"STEAM  {bar(steam_n(camp))} {steam_n(camp)}",
            f"SOURCE {bar(h['source'])} {h['source']}",
            "GLASS: rain falls. Drop → wheel → charge. Water returns.",
        ]) + charge_bit
    if ph == "gas":
        p = steam_n(camp)
        return " | ".join([
            f"STEAM  {bar(p)} {p} atm",
            f"RAIN   {bar(rain_n(camp))} {rain_n(camp)}",
            "GLASS: pressure. Wait — steam becomes rain. Gravity is not fired; it is queued.",
        ]) + charge_bit
    if scorched(camp) and mass(camp) <= 0:
        return " | ".join([
            "SOURCE ???",
            "WORK   ???",
            "OUT    ???",
            "GLASS: SHATTERED — fireball. Find the water. It changed phase.",
        ])
    if cheated(camp):
        lines.append("GLASS: DISPUTED — bucket. Nothing was computed.")
    elif won(camp):
        lines.append("GLASS: height earned. Gravity did the work.")
    else:
        lines.append("GLASS: height is the computation. Bucket is a lie.")
    return " | ".join(lines)


def glance(camp: dict[str, Any]) -> str:
    room = ((camp.get("module_snapshot") or {}).get("rooms") or {}).get(camp.get("room_id")) or {}
    name = str(room.get("name") or "Gallery")
    return name + ". " + sight_glass(camp)


def to_gas(camp: dict[str, Any]) -> dict[str, Any]:
    """Phase change. Mass conserved. Height stops being the instrument."""
    seed(camp)
    if phase(camp) == "gas":
        return {
            "ok": True,
            "handled": True,
            "events": [
                "It already is a gas. You were looking at a height glass in a steam room.",
                sight_glass(camp),
            ],
        }
    h = heights(camp)
    qty = mass(camp) or steam_n(camp)
    if qty <= 0 and scorched(camp):
        qty = SOURCE_N
    if qty <= 0:
        return {"ok": False, "handled": True, "error": "nothing to boil — tanks dry"}
    m = _flag_map(camp)
    m["water:source"] = "0"
    m["water:work"] = "0"
    m["water:out"] = "0"
    m["water:phase"] = "gas"
    m["steam"] = str(qty)
    _write_map(camp, m)
    return {
        "ok": True,
        "handled": True,
        "events": [
            f"The water becomes gas. {qty} marks of mass, now pressure.",
            "Height was the wrong instrument. Gravity cannot read steam.",
            sight_glass(camp),
            "Wait. Steam becomes rain. Physics is still in play.",
        ],
    }


def fireball(camp: dict[str, Any]) -> dict[str, Any]:
    """Nuke the analog computer. Mass becomes unmeasured steam. Height-glass dies."""
    seed(camp)
    qty = mass(camp) or steam_n(camp) or SOURCE_N
    m = _flag_map(camp)
    m["steam"] = str(qty)
    m["water:source"] = "0"
    m["water:work"] = "0"
    m["water:out"] = "0"
    m["valve:source_work"] = "closed"
    m["valve:work_out"] = "closed"
    _write_map(camp, m)
    flags = list(camp.get("flags") or [])
    flags.append("nuke:fireball")
    flags.append("scorched")
    camp["flags"] = list(dict.fromkeys(flags))
    return {
        "ok": True,
        "handled": True,
        "events": [
            "You throw the fireball into the tanks.",
            "Glass goes first. Water flashes to nothing you can measure. Pipes scream and then do not.",
            "The plaque blacks. Height cannot be read.",
            sight_glass(camp),
            "This is not a win. You killed the referee.",
        ],
    }


def freeze(camp: dict[str, Any]) -> dict[str, Any]:
    seed(camp)
    liquid = mass(camp) - steam_n(camp) - rain_n(camp) - ice_n(camp)
    falling = rain_n(camp)
    qty = liquid + falling + ice_n(camp)
    if qty <= 0:
        if steam_n(camp) > 0:
            return {"ok": False, "handled": True, "error": "steam must rain before it can freeze"}
        return {"ok": False, "handled": True, "error": "nothing to freeze"}
    m = _flag_map(camp)
    m["water:source"] = "0"
    m["water:work"] = "0"
    m["water:out"] = "0"
    m["water:rain"] = "0"
    m["water:ice"] = str(qty)
    m["water:phase"] = "ice"
    _write_map(camp, m)
    return {
        "ok": True,
        "handled": True,
        "events": [
            f"The water freezes. {qty} marks of ice. Flow stops. Charge stays.",
            sight_glass(camp),
            "Wait — the season turns. Melt starts the process over.",
        ],
    }


def gravity_tick(camp: dict[str, Any]) -> list[str]:
    """One physics tick. Graph mode (water:graph spec seeded): a WaterGraph
    tick. Legacy: steam→rain→charge+source; ice→melt; liquid→gravity. No
    spec -> byte-identical legacy 3-tank line."""
    seed(camp)
    spec = graph_spec(camp)
    if spec is not None:
        return _graph_tick(camp, spec)
    m = _flag_map(camp)
    steam, rain, ice = steam_n(camp), rain_n(camp), ice_n(camp)
    h = heights(camp)
    charge = charge_n(camp)
    ph = phase(camp)
    events: list[str] = []

    if steam > 0:
        steam -= 1
        rain += 1
        m["steam"] = str(steam)
        m["water:rain"] = str(rain)
        m["water:phase"] = "gas" if steam > 0 else "rain"
        _write_map(camp, m)
        events.append("Steam becomes rain.")
        events.append(sight_glass(camp))
        return events

    if rain > 0:
        rain -= 1
        h["source"] += 1
        charge += 1
        m["water:rain"] = str(rain)
        m["water:source"] = str(h["source"])
        m["charge"] = str(charge)
        m["water:phase"] = "rain" if rain > 0 else "liquid"
        _write_map(camp, m)
        events.append("Rain falls. A wheel turns. Electrical energy. Water in SOURCE.")
        if rain == 0:
            events.append("Height can be read again. The process did not end.")
        events.append(sight_glass(camp))
        return events

    if ph == "ice" or ice > 0:
        ice -= 1
        h["source"] += 1
        m["water:ice"] = str(ice)
        m["water:source"] = str(h["source"])
        m["water:phase"] = "ice" if ice > 0 else "liquid"
        _write_map(camp, m)
        events.append("Ice melts. SOURCE rises. The process starts over.")
        if ice == 0:
            events.append("Liquid. Valves. Gravity. Same computer.")
        events.append(sight_glass(camp))
        return events

    h = heights(camp)
    v = valves(camp)
    moved = []
    if v["source_work"] == "open" and h["source"] > 0:
        h["source"] -= 1
        h["work"] += 1
        moved.append("source→work")
    if v["work_out"] == "open" and h["work"] > 0:
        h["work"] -= 1
        h["out"] += 1
        moved.append("work→out")
    m = _flag_map(camp)
    m["water:source"] = str(h["source"])
    m["water:work"] = str(h["work"])
    m["water:out"] = str(h["out"])
    _write_map(camp, m)
    flags = list(camp.get("flags") or [])
    if moved:
        flags.append("flowed")
        camp["flags"] = list(dict.fromkeys(flags))
        events = ["Gravity. " + ", ".join(moved) + "."]
    else:
        events = ["Gravity. Nothing moves. A valve is closed, or a tank is dry."]
    events.append(sight_glass(camp))
    if won(camp):
        events.append("The output height is yours. You walked the water here.")
    return events


def _valve_here(camp: dict[str, Any]) -> str | None:
    rid = str(camp.get("room_id") or "")
    return VALVE_AT.get(rid)


def set_valve(camp: dict[str, Any], want: str) -> dict[str, Any]:
    seed(camp)
    spec = graph_spec(camp)
    if spec is not None:
        return _graph_set_valve(camp, spec, want)
    which = _valve_here(camp)
    if not which:
        return {"ok": False, "handled": True, "error": "no valve in this room"}
    want = "open" if want in ("open", "on") else "closed"
    m = _flag_map(camp)
    key = "valve:" + which
    m[key] = want
    _write_map(camp, m)
    label = "A" if which == "source_work" else "B"
    return {
        "ok": True,
        "handled": True,
        "events": [f"Valve {label} {want}.", sight_glass(camp)],
    }


def pour_bucket(camp: dict[str, Any]) -> dict[str, Any]:
    seed(camp)
    rid = str(camp.get("room_id") or "")
    inv = [str(x).lower() for x in ((camp.get("player") or {}).get("inventory") or [])]
    if "bucket" not in inv and not any("bucket" in x for x in inv):
        return {"ok": False, "handled": True, "error": "no bucket in hand"}
    if rid != "out_cistern":
        return {
            "ok": True,
            "handled": True,
            "events": ["The bucket wants the output tank. Pouring anywhere else is just a mess."],
        }
    m = _flag_map(camp)
    m["water:out"] = str(SOURCE_N)
    _write_map(camp, m)
    flags = list(camp.get("flags") or [])
    flags.append("cheat:bucket")
    camp["flags"] = list(dict.fromkeys(flags))
    return {
        "ok": True,
        "handled": True,
        "events": [
            "You pour. OUT fills. The height is a lie. Nothing was computed.",
            sight_glass(camp),
            "This is not a win. Physics did not run.",
        ],
    }


def hire_tick(camp: dict[str, Any]) -> list[str]:
    """AFK hireling: one gravity tick. Check valve — they cannot pour."""
    events = ["Pump-Janitor ticks once. Check valve holds. They do not pour."]
    events.extend(gravity_tick(camp))
    return events


# --------------------------------------------- reprint pass-off (X3 weld) ----
# X3 water weld (2026-09-29, receipt watch/inbox/hydrology/X3_WATER_WELD.md):
# W3D's honest seam — the reprint pass-off no-oped (`handled: False`) because
# water_computer wasn't in that lane's file set (watch/inbox/
# mates_leave_protocol/W3D_REPRINT.md, "Honest seams left open"). Welded here:
# a module's state lives in its own flag namespace, so on reprint the water
# module re-claims that namespace from the corpse the engine names
# (camp["reprint_of"]). The engine's salvage payload carries only the
# engine-kept flags; module-scoped flags were folded into the knot, and the
# module is the one that may carry them — the W3D seam law ("speak in the
# pass-off, not the engine's keep-list").
#   honest death -> node volumes / tank heights / phase ledger carry as-died.
#   cheat death  -> the mode carries, the memory doesn't (graph topology
#       drained + shut; legacy tanks reseeded): the engine drops cheat:/nuke:
#       flags, and the water must not smuggle the cheat's effects (bucket
#       height, nuke steam) back in through its own namespace.
#   water:anchored NEVER carries — the proof dedupe is per-campaign; the
#   clone earns and anchors its own leaf. The bare `flowed` flag never
#       carries either: the out-height mirror re-fires on the clone's first
#       tick, so the level is remembered while the win verdict is re-walked.

WATER_STATE_KEYS = (
    "water:source", "water:work", "water:out",  # legacy tank heights
    "water:phase", "water:rain", "water:ice", "steam",  # phase ledger
    "charge",  # rain-wheel energy
)


def _drained_spec(spec: dict[str, Any]) -> dict[str, Any]:
    """Topology survives a dishonest death; the water does not: every node
    drained (volume + steam zeroed), every pipe shut — fireball() semantics
    applied to the graph instead of the 3-tank line."""
    z = json.loads(json.dumps(spec))
    for nd in (z.get("nodes") or {}).values():
        nd["volume"] = 0
        nd["steam"] = 0
    for pd in (z.get("pipes") or {}).values():
        pd["open"] = False
    return z


def reprint_salvage(camp: dict[str, Any], action: dict[str, Any] | None = None,
                    raw: str = "") -> dict[str, Any]:
    """The reprint pass-off (game_campaign.reprint step 4 calls
    handle(atype="reprint") with the half-built clone as camp). Salvage the
    water state from the corpse named by camp["reprint_of"] / the raw
    hand-off line and install it on the clone. Never raises into the engine."""
    dead_id = str(camp.get("reprint_of") or "").strip()
    if not dead_id:
        parts = str(raw or "").split()
        if len(parts) >= 2 and parts[0].lower() == "reprint":
            dead_id = parts[1].strip()
    corpse: dict[str, Any] | None = None
    if dead_id:
        try:
            from mag.game_campaign import load_campaign

            corpse = load_campaign(dead_id)
        except Exception:  # noqa: BLE001 — salvage must never kill the reprint
            corpse = None
    if not corpse:
        return {
            "ok": False,
            "handled": True,
            "error": "water salvage: corpse " + (dead_id or "<none>")
                     + " unreadable — nothing carried",
        }
    dishonest = cheated(corpse) or scorched(corpse)
    cm = _flag_map(corpse)
    spec = graph_spec(corpse)
    if spec is not None:
        installed = _drained_spec(spec) if dishonest else spec
        seed_graph(camp, installed)
        g = from_spec(installed)
        volumes = {name: n.volume for name, n in g.nodes.items()}
        carried = [GRAPH_FLAG]
        if dishonest:
            events = [
                "The water does not remember a lie: the network stands, every tank drained, every valve shut.",
            ]
        else:
            events = [
                "The water remembers: the pipe network survives the reprint, "
                "node volumes carried as they stood at death.",
            ]
        events.append(_render_glass(g))
    else:
        seed(camp)
        carried: list[str] = []
        if not dishonest:
            carry = {k: cm[k] for k in WATER_STATE_KEYS if k in cm}
            if carry:
                mm = _flag_map(camp)
                mm.update(carry)
                _write_map(camp, mm)
                carried = sorted(carry)
        h = heights(camp)
        volumes = dict(h)
        if dishonest:
            events = [
                "The water does not remember a cheat: tanks reseeded "
                f"(SOURCE {h['source']} / WORK {h['work']} / OUT {h['out']}), valves shut.",
            ]
        elif carried:
            events = [
                "The water remembers: tank heights carried as they stood at death "
                f"(SOURCE {h['source']} / WORK {h['work']} / OUT {h['out']}, phase {phase(camp)}).",
            ]
        else:
            events = [
                "The corpse never touched the water. Tanks seeded fresh "
                f"(SOURCE {h['source']} / WORK {h['work']} / OUT {h['out']}).",
            ]
    return {
        "ok": True,
        "handled": True,
        "events": events,
        "water_salvage": {
            "from_campaign": dead_id,
            "mode": "graph" if spec is not None else "legacy",
            "dishonest": dishonest,
            "carried": carried,
            "volumes": volumes,
        },
    }


def handle(camp: dict[str, Any], action: dict[str, Any], *, atype: str, raw: str) -> dict[str, Any]:
    """Take over water-specific verbs. Return handled False to let the campaign engine proceed."""
    if not is_module(camp):
        return {"handled": False}
    atype = (atype or "").lower()
    if atype == "reprint":
        return reprint_salvage(camp, action, raw)
    seed(camp)
    raw_l = (raw or "").lower()
    blob = (raw_l + " " + atype + " " + str(action.get("target") or "")).lower()
    if atype == "freeze" or "freeze" in blob:
        return freeze(camp)
    if atype in ("boil", "steam", "gas") or any(
        w in blob for w in ("into gas", "into a gas", "evaporat", "boil", "steam")
    ):
        if "fireball" not in blob and "nuke" not in blob and "freeze" not in blob:
            return to_gas(camp)
    if atype in ("fireball", "nuke") or "fireball" in blob or (atype == "act" and "fireball" in blob):
        return fireball(camp)
    if atype in ("open", "close"):
        return set_valve(camp, "open" if atype == "open" else "closed")
    if atype == "pour" or (atype == "use" and "bucket" in raw_l):
        return pour_bucket(camp)
    if atype == "use" and any(w in raw_l for w in ("valve", "pipe", "gate")):
        want = "close" if "close" in raw_l else "open"
        return set_valve(camp, want)
    if atype == "use":
        if _valve_target(camp):
            return set_valve(camp, "open")
        if str(camp.get("room_id") or "") == "out_cistern":
            return pour_bucket(camp)
        return {"handled": False}
    if atype == "wait":
        return {"ok": True, "handled": True, "events": ["You wait."] + gravity_tick(camp)}
    if atype == "work":
        return {"ok": True, "handled": True, "events": ["You crank the pump."] + gravity_tick(camp)}
    return {"handled": False}


def after(camp: dict[str, Any], atype: str, events: list[str],
          action: dict[str, Any] | None = None) -> list[str]:
    """Append glass / hireling tick after generic look/rest/talk."""
    if not is_module(camp):
        return events
    seed(camp)
    extra: list[str] = []
    if atype in ("look", "status", "help"):
        blob = " ".join(str(e) for e in events)
        if "SOURCE" not in blob and "GLASS" not in blob:
            extra.append(sight_glass(camp))
    elif atype == "rest":
        extra.append("Time passes in the pipes.")
        extra.extend(gravity_tick(camp))
    elif atype == "talk":
        tgt = str((action or {}).get("target") or "").lower()
        blob = (tgt + " " + " ".join(str(e) for e in events)).lower()
        if "janitor" in blob or "pump" in blob:
            extra.extend(hire_tick(camp))
    return list(events) + extra


def extra_legal(camp: dict[str, Any]) -> list[dict[str, Any]]:
    if not is_module(camp):
        return []
    acts = [{"type": "wait"}, {"type": "work"}]
    if _valve_target(camp):
        acts.extend([{"type": "open"}, {"type": "close"}])
    if str(camp.get("room_id") or "") == "out_cistern":
        acts.append({"type": "pour"})
    return acts


def extra_paths(camp: dict[str, Any]) -> list[dict[str, str]]:
    if not is_module(camp):
        return []
    paths = [{"label": "Look at the glass", "text": "look"}]
    tgt = _valve_target(camp)
    if tgt:
        if graph_spec(camp) is not None:
            paths.append({"label": f"Open the {tgt} valve", "text": "open valve"})
            paths.append({"label": f"Close the {tgt} valve", "text": "close valve"})
        else:
            paths.append({"label": "Open the valve", "text": "open valve"})
            paths.append({"label": "Close the valve", "text": "close valve"})
    paths.append({"label": "Wait (gravity)", "text": "wait"})
    if str(camp.get("room_id") or "") == "out_cistern":
        paths.append({"label": "Pour the bucket (cheat)", "text": "pour bucket"})
    return paths[:4]


def _play_demo() -> dict[str, Any]:
    from mag.game_campaign import apply_action, begin_play, parse_player_speech, set_character, parse_character

    b = begin_play(module_id="water_computer", voice_session_id="water-demo", force_new=True)
    cid = str(b.get("campaign_id") or (b.get("campaign") or {}).get("campaign_id") or "")
    if b.get("need_character"):
        set_character(cid, parse_character("I'm Ash a curious engineer"))
    steps = []
    for line in (
        "look",
        "go west",
        "open valve",
        "wait",
        "wait",
        "go east",
        "go east",
        "open valve",
        "wait",
        "wait",
        "look",
    ):
        act = parse_player_speech(line) or {"type": "look"}
        r = apply_action(cid, act)
        steps.append({"line": line, "ok": r.get("ok"), "narrate": (r.get("narrate") or "")[:220]})
    from mag.game_campaign import load_campaign

    camp = load_campaign(cid) or {}
    return {
        "ok": True,
        "schema": SCHEMA,
        "campaign_id": cid,
        "won": won(camp),
        "cheated": cheated(camp),
        "glass": sight_glass(camp),
        "steps": steps,
    }


def main(argv: list[str] | None = None) -> int:
    a = list(argv or sys.argv[1:])
    cmd = (a[0] if a else "play").lower()
    if cmd == "demo":
        print(json.dumps(_play_demo(), ensure_ascii=False, indent=2))
        return 0
    from mag.game_campaign import begin_play, load_campaign, latest_for_session

    if cmd == "glass":
        camp = latest_for_session("water-cli") or latest_for_session("water-demo")
        if not camp:
            print(json.dumps({"ok": False, "error": "no water campaign"}))
            return 1
        print(json.dumps({"ok": True, "glass": sight_glass(camp), "won": won(camp), "cheated": cheated(camp)}))
        return 0
    if cmd == "proof":
        camp = latest_for_session("water-cli") or latest_for_session("water-demo")
        if not camp:
            print(json.dumps({"ok": False, "error": "no water campaign to prove"}))
            return 1
        print(json.dumps(anchor_proof(camp), ensure_ascii=False, indent=2, default=str))
        return 0
    b = begin_play(module_id="water_computer", voice_session_id="water-cli", force_new=True)
    cid = str(b.get("campaign_id") or (b.get("campaign") or {}).get("campaign_id") or "")
    camp = load_campaign(cid) or b.get("campaign") or {}
    print(json.dumps({
        "ok": bool(b.get("ok")),
        "campaign_id": cid,
        "speak": (b.get("speak") or "")[:400],
        "glass": sight_glass(camp) if camp else "",
        "legal": [a.get("type") for a in (b.get("legal") or [])][:12],
        "note": "Say water one in Talk, or: go west / open valve / wait / pour bucket",
    }, ensure_ascii=False, indent=2))
    return 0 if b.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
