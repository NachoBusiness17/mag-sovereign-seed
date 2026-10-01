"""wave — standing-wave snapshot for the Mag desk.

Schema: mag_wave.v1
One JSON gateway (Hermes tui_gateway steal). The relation persists; models interchange.
"""
from __future__ import annotations

from typing import Any

SCHEMA = "mag_wave.v1"


def _seats(limit: int = 8) -> list[dict[str, Any]]:
    """Mag bus adapters. Not tavern company. Ghost, grok, chatgpt-desktop live here."""
    from config import ROOT
    import json
    path = ROOT / "memory" / "runs" / "party_subchain" / "chain.jsonl"
    seen: dict[str, dict[str, Any]] = {}
    if path.is_file():
        for raw in path.read_text(encoding="utf-8", errors="replace").splitlines()[-40:]:
            try:
                j = json.loads(raw)
            except Exception:
                continue
            seat = str(j.get("seat") or "?")
            seen[seat] = {"seat": seat, "ok": bool(j.get("ok")), "kind": j.get("kind")}
    return list(seen.values())[-limit:]


def _room_who(table: dict[str, Any]) -> list[dict[str, Any]]:
    """Who is in the room. Campaign bytes. Icesus party grid, not the client roster."""
    sc = table.get("scene") or {}
    out: list[dict[str, Any]] = []
    pl = sc.get("player") or {}
    enc = sc.get("encounter")
    if isinstance(enc, dict) and enc.get("name") and int(enc.get("hp") or 0) > 0:
        out.append({"name": str(enc.get("name")), "role": "foe", "kind": "encounter", "talkable": True})
    hooks = list(sc.get("hooks") or [])
    if not hooks:
        cid = str(table.get("campaign_id") or "")
        if cid:
            try:
                from mag.game_campaign import load_campaign, _room
                hooks = list((_room(load_campaign(cid) or {}) or {}).get("hooks") or [])
            except Exception:
                hooks = []
    for h in hooks:
        s = str(h).strip()
        if not s:
            continue
        name = ""
        low = s.lower()
        if low.startswith("rumor") or low.startswith("quest"):
            continue
        if low.startswith("barkeep"):
            name = "barkeep"
        elif "stranger" in low:
            name = "stranger"
        elif "merchant" in low or "captive" in low:
            name = "merchant"
        elif ":" in s[:28]:
            name = s.split(":", 1)[0].strip()
            if name.lower() in ("rumor", "quest", "hook"):
                continue
        if not name:
            continue
        if any(x["name"].lower() == name.lower() for x in out):
            continue
        out.append({"name": name, "role": "here", "kind": "room", "talkable": True})
    blob = " ".join([str(sc.get("room_name") or ""), str(sc.get("room_desc") or ""), str(sc.get("hook") or "")]).lower()
    rid = str(sc.get("room_id") or table.get("room_id") or "").lower()
    if ("lantern" in rid or "tavern" in rid) and any(w in blob for w in ("fire", "hearth")):
        if not any(str(x.get("name") or "").lower() == "calcifer" for x in out):
            out.append({"name": "Calcifer", "role": "hearth", "kind": "room", "talkable": True})
    return out


def _bar(legal: list[Any] | None) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    skip = {"help", "status", "inventory"}
    for a in legal or []:
        if not isinstance(a, dict):
            continue
        typ = str(a.get("type") or "")
        if typ in skip:
            continue
        d = str(a.get("direction") or "")
        tgt = str(a.get("target") or a.get("item") or "").strip()
        if typ == "move" and d:
            label, text = d, "go " + d
        elif typ == "talk" and tgt:
            label, text = "talk " + tgt, "talk to " + tgt
        elif typ == "look" and tgt:
            label, text = "look " + tgt, "look " + tgt
        elif typ == "take" and tgt:
            label, text = "take " + tgt, "take " + tgt
        elif typ == "work":
            label, text = "share", "share"
        elif typ == "talk":
            continue
        elif typ:
            label, text = typ, typ
        else:
            continue
        out.append({"label": label, "text": text})
    if not out:
        out = [{"label": "look", "text": "look"}, {"label": "north", "text": "go north"}]
    return out[:16]


def _frames(table: dict[str, Any]) -> dict[str, Any]:
    sc = table.get("scene") or {}
    pl = sc.get("player") or {}
    bags = list(pl.get("inventory") or [])
    cid = str(table.get("campaign_id") or "")
    if not bags and cid:
        try:
            from mag.game_campaign import load_campaign
            camp = load_campaign(cid) or {}
            bags = list(((camp.get("player") or {}).get("inventory") or []))
            if not pl.get("name"):
                pl = camp.get("player") or pl
        except Exception:
            pass
    status = str(table.get("status") or "")
    seated = bool(pl.get("name") or cid) and status != "void"
    if not seated:
        return {
            "unit": {"name": "unseated", "archetype": "", "hp": None, "hp_max": None, "hp_pct": None},
            "bags": [],
            "quest": "",
            "who": _room_who(table),
            "seats": _seats(),
            "bar": _bar(table.get("legal") or sc.get("legal")),
            "note": "no campaign mounted — void is empty, not a 0-HP corpse",
        }
    hp = int(pl.get("hp") if pl.get("hp") is not None else 0)
    hp_max = int(pl.get("hp_max") or 1) or 1
    return {
        "unit": {
            "name": pl.get("name") or "Adventurer",
            "archetype": pl.get("archetype") or "",
            "hp": hp,
            "hp_max": hp_max,
            "hp_pct": round(100.0 * hp / hp_max),
        },
        "bags": bags,
        "quest": (
            "The crate is sealed. The merchant will not open it."
            if any(x in str(sc.get("hook") or "").lower() for x in ("crate", "merchant", "captive", "seal"))
            else (
                (lambda h: (
                    (h.split(":",1)[-1].strip().rstrip(".") + ".")
                    if h.lower().startswith("rumor") else ""
                ))(str(sc.get("hook") or ""))
            )
        ) or "",
        "who": _room_who(table),
            "seats": _seats(),
        "bar": _bar(table.get("legal") or sc.get("legal")),
        "hotspots": _hotspots(sc, _room_who(table)),
        "note": "vanilla WoW frames from campaign bytes — prove mechanics, no 3D",
    }


def _exits(scene: dict[str, Any]) -> list[str]:
    raw = (scene or {}).get("exits") or []
    out: list[str] = []
    for e in raw:
        if isinstance(e, str) and e.strip():
            out.append(e.strip().lower())
        elif isinstance(e, dict):
            d = str(e.get("direction") or e.get("to") or "").strip().lower()
            if d:
                out.append(d)
    return out


def room_mermaid(scene: dict[str, Any] | None) -> str:
    sc = scene or {}
    here = str(sc.get("room_name") or sc.get("room_id") or "here").replace('"', "'")
    lines = ["flowchart TD", f'  HERE["{here}"]']
    for d in _exits(sc):
        nid = d.replace(" ", "_")
        lines.append(f'  HERE -->|{d}| {nid}["{d}"]')
    if len(lines) == 2:
        lines.append('  HERE -->|look| stay["stay"]')
    return "\n".join(lines)


def _hotspots(scene: dict[str, Any], who: list | None = None) -> list[dict[str, str]]:
    """Clickable nouns from the live room, not a tavern-only list."""
    sc = scene or {}
    spots: list[dict[str, str]] = []
    seen: set[str] = set()
    def add(word: str, act: str) -> None:
        w = (word or "").strip()
        if not w or w.lower() in seen:
            return
        seen.add(w.lower())
        spots.append({"word": w, "act": act})
    for p in who or []:
        if isinstance(p, dict) and p.get("talkable") and p.get("name"):
            add(str(p.get("name")), "talk to " + str(p.get("name")))
    blob = " ".join([
        str(sc.get("room_name") or ""),
        str(sc.get("room_desc") or ""),
        str(sc.get("hook") or ""),
    ]).lower()
    for word, act in (
        ("stranger", "talk to stranger"),
        ("barkeep", "talk to barkeep"),
        ("fire", "look fire"),
        ("mug", "look mug"),
        ("chimney", "look chimney"),
        ("cart", "look cart"),
        ("keep", "look keep"),
        ("gate", "look gate"),
        ("raven", "look raven"),
        ("tracks", "look tracks"),
        ("merchant", "talk to merchant"),
        ("captive", "talk to merchant"),
        ("crate", "look crate"),
        ("seal", "look crate"),
        ("puzzle-box", "look crate"),
        ("torch", "look torch"),
        ("stubs", "look stubs"),
    ):
        if word in blob:
            add(word, act)
    for d in _exits(sc):
        add(d, "go " + d)
    return spots[:14]


def room_svg(scene: dict[str, Any] | None, people: list | None = None) -> str:
    """Floor of the live room. Tavern stays the tavern. Road shows the keep. Swiss hairlines."""
    sc = scene or {}
    people = people or sc.get("who") or []
    names = [str((p.get("name") if isinstance(p, dict) else p) or "").lower() for p in people]
    exits = _exits(sc)
    title = str(sc.get("room_name") or sc.get("room_id") or "")
    rid = str(sc.get("room_id") or "").lower()
    low = (title + " " + rid).lower()
    # Text adventure: only the lantern is a pokeable floor. Other rooms are prose + compass.
    tavern = "lantern" in rid or rid in ("tavern_lantern", "tavern")
    if not tavern:
        return ""
    claw = False
    cellar = False
    hall = False
    blob = (title + " " + str(sc.get("room_desc") or "") + " " + str(sc.get("hook") or "")).lower()
    w, h = 720, 320
    cx, cy = 360, 170
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="100%" height="320" data-scene="room" data-camera="ortho">',
        '<g data-layer="world" data-order="0">',
        '<rect width="100%" height="100%" fill="#111111"/>',
    ]
    if tavern:
        parts += [
            '<rect x="160" y="70" width="400" height="160" fill="none" stroke="#3a3a3a" stroke-width="1" vector-effect="non-scaling-stroke"/>',
            '<rect x="176" y="150" width="40" height="56" fill="none" stroke="#3a3a3a" stroke-width="1" vector-effect="non-scaling-stroke"/>',
            '<line x1="220" y1="92" x2="520" y2="92" stroke="#3a3a3a" stroke-width="1" vector-effect="non-scaling-stroke"/>',
            '<rect x="300" y="128" width="96" height="40" fill="none" stroke="#3a3a3a" stroke-width="1" vector-effect="non-scaling-stroke"/>',
        ]
    elif hall:
        parts += [
            '<rect x="120" y="40" width="480" height="240" fill="none" stroke="#3a3a3a" stroke-width="1" vector-effect="non-scaling-stroke"/>',
            '<line x1="150" y1="70" x2="210" y2="140" stroke="#3a3a3a" stroke-width="1" vector-effect="non-scaling-stroke"/>',
            '<line x1="168" y1="64" x2="226" y2="138" stroke="#3a3a3a" stroke-width="1" vector-effect="non-scaling-stroke"/>',
            '<line x1="186" y1="68" x2="242" y2="142" stroke="#3a3a3a" stroke-width="1" vector-effect="non-scaling-stroke"/>',
        ]
    else:
        parts += [
            f'<line x1="{cx}" y1="260" x2="{cx}" y2="70" stroke="#3a3a3a" stroke-width="1" vector-effect="non-scaling-stroke"/>',
            '<rect x="300" y="28" width="120" height="48" fill="none" stroke="#3a3a3a" stroke-width="1" vector-effect="non-scaling-stroke"/>',
        ]
    parts.append("</g>")
    parts.append('<g data-layer="props" data-order="1">')
    if tavern:
        parts.append('<text x="196" y="228" text-anchor="middle" fill="#f2f2f2" font-size="18" font-family="Helvetica, Arial, sans-serif" data-look="fire" class="exit" cursor="pointer">fire</text>')
    elif claw:
        parts.append(
            '<g data-look="crate" class="exit" cursor="pointer">'
            '<rect x="430" y="168" width="80" height="52" fill="transparent" pointer-events="all"/>'
            '<rect x="430" y="168" width="72" height="44" fill="none" stroke="#3a3a3a" stroke-width="1" vector-effect="non-scaling-stroke" pointer-events="none"/>'
            '<text x="466" y="196" text-anchor="middle" fill="#f2f2f2" font-size="16" '
            'font-family="Helvetica, Arial, sans-serif" pointer-events="none">puzzle-box</text>'
            "</g>"
        )
    elif cellar:
        parts.append(
            '<g data-look="torch" class="exit" cursor="pointer">'
            '<rect x="150" y="60" width="100" height="90" fill="transparent" pointer-events="all"/>'
            '<text x="200" y="140" text-anchor="middle" fill="#f2f2f2" font-size="16" '
            'font-family="Helvetica, Arial, sans-serif" pointer-events="none">stubs</text>'
            "</g>"
        )
    else:
        parts.append('<text x="360" y="58" text-anchor="middle" fill="#f2f2f2" font-size="18" font-family="Helvetica, Arial, sans-serif" data-look="keep" class="exit" cursor="pointer">keep</text>')
        hook = str(sc.get("hook") or "").lower()
        if "cart" in hook or "cart" in str(sc.get("room_desc") or "").lower():
            parts.append('<text x="250" y="200" text-anchor="middle" fill="#f2f2f2" font-size="16" font-family="Helvetica, Arial, sans-serif" data-look="cart" class="exit" cursor="pointer">cart</text>')
    parts.append("</g>")
    parts.append('<g data-layer="people" data-order="2">')
    parts.append('<text x="360" y="250" text-anchor="middle" fill="#8a8a8a" font-size="16" font-family="Helvetica, Arial, sans-serif">you</text>')
    slots = [(240, 150), (400, 140), (520, 150), (300, 180), (480, 220)]
    drawn = set()
    si = 0
    for p in people:
        nm = str((p.get("name") if isinstance(p, dict) else p) or "").strip()
        if not nm or nm.lower() in drawn or nm.lower() in ("you",):
            continue
        if isinstance(p, dict) and str(p.get("kind") or "") == "player":
            continue
        if isinstance(p, dict) and str(p.get("role") or "") == "you":
            continue
        drawn.add(nm.lower())
        x, y = slots[si % len(slots)]
        si += 1
        talkable = True if not isinstance(p, dict) else bool(p.get("talkable", True))
        extra = f' data-talk="{nm}" class="exit" cursor="pointer"' if talkable else ""
        parts.append(f'<text x="{x}" y="{y}" text-anchor="middle" fill="#f2f2f2" font-size="18" font-family="Helvetica, Arial, sans-serif"{extra}>{nm}</text>')
    if any("barkeep" in n for n in names) and "barkeep" not in drawn:
        parts.append('<text x="370" y="86" text-anchor="middle" fill="#f2f2f2" font-size="18" font-family="Helvetica, Arial, sans-serif" data-talk="barkeep" class="exit" cursor="pointer">barkeep</text>')
    if any("stranger" in n for n in names) and "stranger" not in drawn:
        parts.append('<text x="348" y="154" text-anchor="middle" fill="#f2f2f2" font-size="18" font-family="Helvetica, Arial, sans-serif" data-talk="stranger" class="exit" cursor="pointer">stranger</text>')
    parts.append("</g>")
    parts.append('<g data-layer="exits" data-order="3">')
    slots = {
        "north": (cx, 36, cx, 70),
        "n": (cx, 36, cx, 70),
        "up": (520, 50, 560, 70),
        "south": (cx, 280, cx, 230),
        "s": (cx, 280, cx, 230),
        "down": (cx, 280, cx, 230),
        "out": (cx, 280, cx, 230),
        "back": (cx, 280, cx, 230),
        "tavern": (80, 280, 160, 230),
        "east": (640, cy, 560, cy),
        "e": (640, cy, 560, cy),
        "west": (80, cy, 160, cy),
        "w": (80, cy, 160, cy),
    }
    for d in exits:
        x1, y1, x2, y2 = slots.get(d, (cx + 200, 40, 560, 70))
        parts.append(f'<line x1="{x2}" y1="{y2}" x2="{x1}" y2="{y1}" stroke="#3a3a3a" stroke-width="1" vector-effect="non-scaling-stroke"/>')
        parts.append(
            f'<text x="{x1}" y="{y1}" text-anchor="middle" fill="#f2f2f2" font-size="20" '
            f'font-family="Helvetica, Arial, sans-serif" data-exit="{d}" class="exit" cursor="pointer">{d}</text>'
        )
    parts.append("</g></svg>")
    return "".join(parts)


DOCTRINE = (
    "A deterministic instruction set, anchored on shared cryptographic primitives, "
    "explains navigable paths through stochastic environments. "
    "The relation (the frozen spec) is what persists; the model is interchangeable; "
    "the chain is the ground truth."
)


def snapshot(*, session_id: str = "") -> dict[str, Any]:
    verkle: dict[str, Any] = {}
    try:
        from config import ROOT
        import json
        tip = ROOT / "memory" / "biography" / "verkle_tip.json"
        if tip.is_file():
            verkle = json.loads(tip.read_text(encoding="utf-8"))
    except Exception as e:
        verkle = {"ok": False, "error": str(e)[:120]}
    if not verkle.get("n_leaves"):
        try:
            from config import ROOT
            import json
            tip = ROOT / "memory" / "biography" / "verkle_tip.json"
            if tip.is_file():
                verkle = json.loads(tip.read_text(encoding="utf-8"))
        except Exception:
            pass

    sub: dict[str, Any] = {}
    try:
        from mag import party_subchain
        sub = party_subchain.status() if hasattr(party_subchain, "status") else {}
    except Exception as e:
        sub = {"ok": False, "error": str(e)[:120]}

    world: dict[str, Any] = {}
    try:
        from mag import game_world
        world = game_world.world_status()
    except Exception as e:
        world = {"ok": False, "error": str(e)[:120]}

    table: dict[str, Any] = {}
    try:
        from mag.game_view import build_view
        table = build_view(session_id=session_id)
    except Exception as e:
        table = {"ok": False, "error": str(e)[:120]}

    team: dict[str, Any] = {}
    surface: dict[str, Any] = {}

    fr = _frames(table)
    speak_text = ""
    camp: dict[str, Any] = {}
    interior = ""
    saga = ""
    try:
        from datetime import datetime, timezone
        import re as _re
        from mag.game_campaign import (
            latest_any,
            load_campaign,
            save_campaign,
            _donjon_sense,
            _player_signal,
            _room,
            _utc,
            _narrate_room,
            story_so_far,
        )
        from mag.chasm_state import persist as chasm_persist, recall as chasm_recall
        from mag.game_dm_voice import extract_narrator

        cid = str((table.get("campaign_id") or "") if isinstance(table, dict) else "")
        camp = load_campaign(cid) if cid else latest_any()
        if not isinstance(camp, dict):
            camp = {}
        if camp:
            interior = _narrate_room(camp) or interior
            saga = story_so_far(camp) or saga
        beat = ""
        if camp and camp.get("status") in ("active", "paused"):
            log = list(camp.get("log") or [])
            last_ts = str((log[-1] or {}).get("ts") or camp.get("updated") or "")
            age = 1e9
            try:
                dt = datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                age = (datetime.now(timezone.utc) - dt).total_seconds()
            except Exception:
                age = 1e9
            if age >= 20.0:
                room = _room(camp)
                rid = str(camp.get("room_id") or "keep_gate")
                bits: list[str] = []
                sense = _donjon_sense(camp)
                if sense:
                    bits.append(sense)
                blob = " ".join([
                    str(room.get("name") or ""),
                    str(room.get("desc") or ""),
                    " ".join(str(h) for h in (room.get("hooks") or [])),
                ]).lower()
                if "lantern" in rid or "tavern" in rid:
                    bits.append("The hearth pops.")
                for h in room.get("hooks") or []:
                    hs = str(h).strip()
                    if not hs or hs.lower().startswith(("rumor", "quest")):
                        continue
                    words = hs.replace(".", "").split()
                    if len(words) <= 6 and not any(
                        x.lower() in ("is", "are", "has", "holds", "wants", "lies", "sits", "burns", "waits")
                        for x in words
                    ):
                        continue
                    bits.append(hs)
                    break
                mem = chasm_recall(str(camp.get("campaign_id") or ""), rid, limit=1)
                if mem:
                    line = _re.sub(r"\bsession[_-]?id\S*", "", str(mem[-1]), flags=_re.I)
                    line = " ".join(line.split())
                    if ("`idle`" in line.lower() or line.lower().startswith("this place remembers")
                            or "`" in line or _re.search(r"\d{4}-\d{2}-\d{2}T", line)):
                        line = ""
                    if line:
                        bits.append("This place remembers: " + line[:160])
                try:
                    pr_recall = None  # phone: FILE tick only, skip slow persona_recall
                    pr = pr_recall(archetype="trickster", region="keep_gate")
                    voice = str(((pr.get("persona") or {}).get("voice") or "")).strip()
                    if voice:
                        bits.append(voice)
                except Exception:
                    pass
                if not bits:
                    bits.append("The keep waits. Stone holds the last word.")
                n = int((camp.get("storyteller") or {}).get("idle_n") or 0)
                beat = bits[n % len(bits)]
                beat = _player_signal(beat, source="wave_afk") or beat
                beat = " ".join(_re.sub(r"\bsession[_-]?id\S*", "", beat, flags=_re.I).split())[:240]
                st = dict(camp.get("storyteller") or {})
                st["idle_n"] = n + 1
                camp["storyteller"] = st
                camp["log"] = log + [{"ts": _utc(), "type": "idle", "text": beat}]
                save_campaign(camp)
                try:
                    chasm_persist(camp, events=[beat], action="idle")
                except Exception:
                    pass
            else:
                idle = next((e for e in reversed(log) if str(e.get("type") or "") == "idle"), None)
                beat = str((idle or {}).get("text") or "")
        if not beat:
            beat = str(((table.get("scene") or {}).get("room_desc") or ""))
        wrapped = beat if str(beat).lstrip().startswith("#") else ("## Narrator\n\n" + beat)
        speak_text = " ".join(str(extract_narrator(wrapped) or "").split())
    except Exception:
        speak_text = ""
    return {
        "ok": True,
        "schema": SCHEMA,
        "speak_text": speak_text,
        "doctrine": DOCTRINE,
        "verkle": {
            "n_leaves": verkle.get("n_leaves"),
            "root": (verkle.get("root") or "")[:16],
            "last_leaf_hash": (verkle.get("last_leaf_hash") or "")[:16],
            "updated_minute": verkle.get("updated_minute"),
        },
        "party_subchain": {
            "n": sub.get("n"),
            "verified": sub.get("verified"),
            "head_hash": (sub.get("head_hash") or "")[:16],
            "anchored": sub.get("anchored"),
        },
        "world": world,
        "table": {
            "ok": table.get("ok"),
            "skin": table.get("skin"),
            "title": table.get("title"),
            "grid_text": table.get("grid_text"),
            "world": table.get("world"),
            "room_id": table.get("room_id"),
            "campaign_id": table.get("campaign_id"),
            "legal": table.get("legal") or [],
            "scene": table.get("scene") or {},
        },
        "frames": fr,
        "narrative": {
            "interior": interior or ((table.get("scene") or {}).get("room_desc") or ""),
            "story_so_far": saga,
            "hook": ((table.get("scene") or {}).get("hook") or ""),
            "exits": _exits(table.get("scene") or {}),
            "player": ((table.get("scene") or {}).get("player") or {}),
        },
        "render": {
            "room_mermaid": room_mermaid(table.get("scene") or {}),
            "room_svg": (lambda s: room_svg({**s, "room_id": table.get("room_id")}, people=fr.get("who")))(table.get("scene") or {}),
        },
        "code_team": team,
        "faces": {
            "wave": "/wave",
            "table": "/table",
            "chat": "/",
            "voice": "/voice",
            "seat": "/seat",
        },
        "surface": surface,
        "note": "one serve, many surfaces — lantern is a pane",
    }


def snapshot_fast(*, session_id: str = "") -> dict[str, Any]:
    """Text-adventure pane. File-first. No idle tick, no game_campaign import."""
    from mag.game_view import handle_table_view

    table = handle_table_view({}, {"session_id": session_id} if session_id else {})
    sc = (table.get("scene") or {}) if isinstance(table, dict) else {}
    pl = sc.get("player") or {}
    rid = str(table.get("room_id") or "")
    interior = str(sc.get("room_desc") or "").strip()
    hook = str(sc.get("hook") or "").strip()
    if hook and hook.lower() not in interior.lower():
        interior = (interior + " " + hook).strip()
    who: list[dict[str, Any]] = []
    enc = sc.get("encounter") or {}
    try:
        units = [u for u in (enc.get("units") or []) if int(u.get("hp") or 0) > 0]
        if units:
            for u in units:
                who.append({"name": str(u.get("name")), "role": str(u.get("station") or "goblin"), "kind": "encounter", "talkable": False})
        elif enc.get("name") and int(enc.get("hp") or 0) > 0:
            who.append({"name": str(enc.get("name")), "role": "foe", "kind": "encounter", "talkable": True})
    except (TypeError, ValueError):
        pass
    blob = " ".join([str(sc.get("room_name") or ""), interior, hook]).lower()
    flags = sc.get("flags") or table.get("flags") or []
    if isinstance(flags, dict):
        flags = list(flags)
    flagset = {str(f).lower() for f in flags}
    for name, keys in (
        ("mira", ("mira", "barkeep")),
        ("stranger", ("stranger",)),
        ("merchant", ("merchant", "captive")),
    ):
        if name == "merchant" and "merchant_fled" in flagset:
            continue
        if any(k in blob for k in keys):
            who.append({"name": name if name != "mira" else "Mira", "role": "here", "kind": "room", "talkable": True})
    if rid in ("tavern_lantern", "lantern") and any(w in blob for w in ("fire", "hearth")):
        who.append({"name": "Calcifer", "role": "hearth", "kind": "room", "talkable": True})
    hp = int(pl.get("hp") if pl.get("hp") is not None else 0)
    hp_max = int(pl.get("hp_max") or 1) or 1
    seated = bool(pl.get("name") or table.get("campaign_id"))
    fr = {
        "unit": {
            "name": (pl.get("name") or "Adventurer") if seated else "unseated",
            "archetype": pl.get("archetype") or "",
            "hp": hp if seated else None,
            "hp_max": hp_max if seated else None,
            "hp_pct": round(100.0 * hp / hp_max) if seated else None,
        },
        "bags": list(pl.get("inventory") or []),
        "quest": hook if hook.lower().startswith(("rumor", "quest")) else "",
        "who": who,
        "bar": _bar(table.get("legal") or []),
        "hotspots": _hotspots(sc, who),
    }
    return {
        "ok": True,
        "schema": SCHEMA,
        "speak_text": interior[:480],
        "doctrine": DOCTRINE,
        "table": {
            "ok": table.get("ok"),
            "title": table.get("title"),
            "room_id": table.get("room_id"),
            "campaign_id": table.get("campaign_id"),
            "legal": table.get("legal") or [],
            "scene": sc,
        },
        "frames": fr,
        "narrative": {
            "interior": interior,
            "story_so_far": "",
            "hook": hook,
            "exits": _exits(sc),
            "player": pl,
        },
        "render": {
            "room_mermaid": room_mermaid(sc),
            "room_svg": room_svg({**sc, "room_id": rid}, people=who),
        },
        "faces": {"wave": "/wave", "table": "/table"},
        "note": "fast pane — room bytes, one beat",
    }

