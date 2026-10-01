"""DM voice formatting — passage card for table; narrator-only for TTS.

Schema: mag_game_dm_voice.v1
Law: speak/speak_text = Narrator section only. answer/narrate = full card.
"""
from __future__ import annotations

import re
from typing import Any

SCHEMA = "mag_game_dm_voice.v1"

# Tavern brawl environment palette (engine-owned; not invented rooms)
_BRAWL_ENV = {
    "calm_open": (
        "Lamp-light argues with damp. Broth and wet wool. Tables sticky enough "
        "to hold a rumor still."
    ),
    "heat_rising": (
        "Voices stack. A chair scrapes like a drawn line. Ale trembles in mugs "
        "that have not yet chosen a side."
    ),
    "mid_brawl": (
        "Noise becomes weather. Spilled ale maps the floor. Someone's laugh "
        "arrives late and wrong. Smoke from the hearth tastes of temper."
    ),
    "absurd": (
        "The room tilts toward farce. Physics stays honest; dignity does not. "
        "Even the fire seems to lean in for gossip."
    ),
    "aftermath": (
        "Heat drains. Counting of chairs begins. The lantern still hangs; "
        "the night has new furniture of memory."
    ),
}


def extract_narrator(passage: str) -> str:
    """Narrator section only — DM voice for TTS."""
    t = passage or ""
    m = re.search(
        r"##\s*Narrator\s*\n+(.+?)(?=\n##\s|\n###\s|\Z)",
        t,
        re.I | re.S,
    )
    if m:
        body = m.group(1).strip()
        body = re.sub(r"\n{3,}", "\n\n", body)
        return body[:700]
    # fallback: first non-heading paragraph that isn't soft leads
    lines = []
    for ln in t.splitlines():
        if re.match(r"^#+\s", ln):
            continue
        if re.match(r"^[-*]\s", ln):
            continue
        if ln.strip():
            lines.append(ln.strip())
    return " ".join(lines)[:500] if lines else "The room waits."


def _env_for_brawl(
    *,
    status: str,
    absurd: bool,
    round_n: int,
    room_env: str = "",
) -> str:
    if absurd:
        base = _BRAWL_ENV["absurd"]
    elif status in ("complete", "defeat", "fled"):
        base = _BRAWL_ENV["aftermath"]
    elif round_n <= 1 and status in ("awaiting_player", "auto_running"):
        base = _BRAWL_ENV["heat_rising"]
    else:
        base = _BRAWL_ENV["mid_brawl"]
    if room_env:
        return f"{room_env.rstrip('. ')}. {base}"
    return base


def _interior_from_events(events: list[str], *, open_story: bool = False) -> str:
    if open_story:
        return (
            "The Guttered Lantern's common room: low beams, sticky tables, "
            "a fire that argues with the damp. An adventuring party returns "
            "empty-handed — the mark gone — and heat finds a stranger's stool."
        )
    # pick vivid mechanical lines, strip roll noise for interior image
    vivid = []
    for e in events or []:
        s = str(e).strip()
        if not s or s.startswith("—") or s.startswith("["):
            continue
        if s.startswith("INITIATIVE") or s.startswith("ROSTER") or s.startswith("  ["):
            continue
        if "FAILED HUNT" in s:
            vivid.append("Empty hands. Full blame. The failed hunt sits at the bar like a fourth guest.")
            continue
        # soften dice lines into image
        if " hits " in s and " for " in s:
            name = s.split(" hits ")[0]
            rest = s.split(" hits ", 1)[1]
            target = rest.split(" with ")[0] if " with " in rest else rest.split(" (")[0]
            vivid.append(f"{name} connects with {target} — wood, bone, or pride.")
        elif "miss" in s.lower():
            vivid.append("A swing spends itself on air and ale-smell.")
        elif "grapples" in s.lower() or "grapple" in s.lower():
            vivid.append("Bodies lock; the floor becomes a temporary treaty.")
        elif "ABSURD" in s:
            vivid.append("The plot hiccups. Farce steals a turn.")
        elif "drops" in s.lower():
            vivid.append("Someone joins the floor's collection.")
        else:
            if len(s) < 120 and not re.search(r"\d+ vs AC", s):
                vivid.append(s)
    if not vivid:
        return "Chairs, elbows, and unfinished sentences fill the lantern light."
    # dedupe preserve order
    out = []
    for v in vivid:
        if v not in out:
            out.append(v)
    return " ".join(out[:5])


def _narrator_from_pack(
    pack: dict[str, Any] | None,
    *,
    status: str,
    player_name: str,
    absurd: bool,
    your_turn: bool,
    events: list[str] | None = None,
) -> str:
    """Poetic DM pressure — no theory names, no HP invention."""
    quote = ""
    hint = ""
    if pack:
        qs = pack.get("quotes") or []
        if qs:
            quote = str(qs[0])
        hint = str(pack.get("craft_hint") or "")[:200]

    # core beat from state
    if status == "defeat":
        core = f"{player_name} meets the floor. The brawl continues its own opinion."
    elif status == "fled":
        core = "Cold air claims you. Behind, Mira begins the arithmetic of broken wood."
    elif status == "complete":
        core = "Heat leaves the room like a bad guest. The lantern keeps its post."
    elif absurd:
        core = (
            f"{player_name} steals the scene without asking. "
            "The room answers as one organism — then splinters into gossip."
        )
    elif your_turn:
        core = (
            f"The room holds for {player_name}. "
            "Steel is optional. A chair is a thesis. Absurdity is a legal move if you mean it."
        )
    else:
        core = "Fists write faster than apologies. The failed hunt still wants a villain."

    # weave one craft echo without citing authors / meta
    echo = ""
    clean_q = quote.strip()
    if clean_q and (
        clean_q.startswith("**")
        or "schema" in clean_q.lower()
        or "train" in clean_q.lower()
        or len(clean_q) > 140
    ):
        clean_q = ""
    if clean_q and absurd:
        echo = f" Someone will remember: {clean_q.rstrip('.')}."
    elif clean_q and your_turn:
        echo = f" {clean_q.rstrip('.')}."
    elif "blame" in hint.lower() or "shadow" in hint.lower():
        echo = " Blame looks for a body; any stranger will do."
    elif "threshold" in hint.lower() or "ordinary" in hint.lower():
        echo = " The ordinary night has cracked; it will not seal clean."

    return (core + echo).strip()


def _soft_leads(status: str, *, your_turn: bool) -> list[str]:
    if status in ("complete", "defeat", "fled"):
        return ["look around", "seal session", "leave for the road"]
    if your_turn:
        return [
            "punch / improvise / grapple",
            "do something absurd (the room reacts)",
            "flee for the door",
        ]
    return ["watch", "wait for your turn"]


def _ledger_block(
    *,
    events: list[str],
    roster_lines: str = "",
    status: str = "",
    brawl_id: str = "",
) -> str:
    """Mechanical appendix — table only, never TTS."""
    lines = ["### Ledger (engine — not spoken)"]
    if brawl_id:
        lines.append(f"brawl `{brawl_id}` · status `{status}`")
    mech = []
    for e in events or []:
        s = str(e)
        if s.startswith("—") or " vs AC " in s or s.startswith("[") or "HP " in s:
            mech.append(s)
        elif s.startswith("  [") or s.startswith("INITIATIVE"):
            mech.append(s)
    if roster_lines:
        lines.append("```")
        lines.append(roster_lines.strip())
        lines.append("```")
    if mech:
        lines.append("```")
        lines.extend(mech[-14:])
        lines.append("```")
    return "\n".join(lines)


def format_brawl_card(
    *,
    events: list[str] | None = None,
    status: str = "awaiting_player",
    player_name: str = "Adventurer",
    room_name: str = "The Guttered Lantern",
    room_area: str = "Village edge under the keep's shadow",
    room_env: str = "",
    round_n: int = 1,
    absurd: bool = False,
    open_story: bool = False,
    brawl_id: str = "",
    roster_summary: str = "",
    inspiration_pack: dict[str, Any] | None = None,
    color_line: str = "",
    pressure: str = "",
    perspectives_md: str = "",
) -> dict[str, Any]:
    """Full passage card + narrator-only speak string."""
    events = list(events or [])
    your_turn = status == "awaiting_player" or any("YOUR TURN" in str(e) for e in events)

    interior = _interior_from_events(events, open_story=open_story)
    if color_line and open_story:
        # prefer engine events; color is optional enrichment in Environment/Narrator only
        pass

    environment = _env_for_brawl(
        status=status, absurd=absurd, round_n=round_n, room_env=room_env
    )
    if pressure:
        environment = f"{environment} Pressure under the noise: {pressure.rstrip('.')}."

    narrator = _narrator_from_pack(
        inspiration_pack,
        status=status,
        player_name=player_name,
        absurd=absurd,
        your_turn=your_turn,
        events=events,
    )
    # Optional DS color as second narrator paragraph if it doesn't invent numbers badly
    if color_line and not re.search(r"\bHP\s*\d|AC\s*\d", color_line, re.I):
        # keep short
        cl = re.sub(r"\s+", " ", color_line).strip()
        if len(cl) > 40:
            narrator = f"{narrator}\n\n{cl[:420]}"

    leads = _soft_leads(status, your_turn=your_turn)
    leads_block = "\n".join(f"- {x}" for x in leads)

    parts = [
        f"## Interior\n{interior}",
        f"## Area\n{room_name} — {room_area}",
        f"## Environment\n{environment}",
        f"## Narrator\n{narrator}",
    ]
    if (perspectives_md or "").strip():
        parts.append(perspectives_md.strip())
    parts.append(f"## Soft leads\n{leads_block}")
    passage = "\n\n".join(parts)

    from mag.corpus_query import format_inspiration_footer

    foot = format_inspiration_footer(inspiration_pack)
    ledger = _ledger_block(
        events=events,
        roster_lines=roster_summary,
        status=status,
        brawl_id=brawl_id,
    )
    full = passage
    if foot:
        full = full + "\n\n" + foot
    full = full + "\n\n" + ledger

    speak = extract_narrator(passage)
    return {
        "ok": True,
        "schema": SCHEMA,
        "passage": passage,
        "narrate": full,
        "answer": full,
        "speak": speak,
        "speak_text": speak,
        "narrator": speak,
        "your_turn": your_turn,
        "environment": environment,
        "interior": interior,
        "has_perspectives": bool((perspectives_md or "").strip()),
    }
