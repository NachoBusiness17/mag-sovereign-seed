"""tavern_summon_guests — bring the four guests into the live tavern room.

Dispatches each guest persona against the current room tail, appends their
lines to the shared transcript, and persists their session ids for future
rounds. House cast keeps using mag.tavern_chat as normal.

  python -m mag.tavern_summon_guests
"""
from mag.tavern_chat import (
    SYSTEM_NOTE, _append_transcript, _dispatch_or_resume, _load, _save, _tail,
)

GUESTS = ["shakespeare", "diogenes", "plato", "voltaire"]

SUMMONS = (
    "MARK has summoned you into the room as a guest — the house already knows "
    "each other; you are new. ON THE TABLE: a primer that teaches real "
    "electronics to children raised on D&D — every component a stat block with "
    "a law, a toll, a weakness, an alignment. Room 1 was the Darlington Pair. "
    "Tonight the house filed twelve sensor-familiars (the dungeon's senses) and "
    "the question is where this road goes: is the D&D costume an honest way to "
    "teach true physics or a trick; and should the body hire its missing "
    "senses now or after the wall. One question or one cut that moves the road."
)


def main() -> int:
    st = _load()
    _append_transcript(
        st["transcript"], "MARK",
        "Four chairs appear by the fire: the poet, the dog, the geometer, the "
        "smile. MARK's ask: tease out where the Primer's road goes — nine "
        "voices tonight, no speeches.",
    )
    for persona in GUESTS:
        prompt = (
            f"{SYSTEM_NOTE}\n\nTHE ROOM LATELY:\n{_tail(st['transcript'], 3)}\n\n"
            f"{SUMMONS}\n\nYour turn, {persona}."
        )
        sid, body = _dispatch_or_resume(persona, prompt, st["sessions"].get(persona))
        if sid:
            st["sessions"][persona] = sid
        _append_transcript(st["transcript"], persona.upper(), body or "(silence)")
        _save(st)
        print(f"{persona}: {(body or '(silence)')[:90].replace(chr(10), ' ')}")
    print(f"[room transcript] {st['transcript']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
