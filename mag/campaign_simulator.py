"""Campaign Simulator — play through a campaign, character by character.

Takes a deep campaign with procedurally generated characters (shadows,
compulsions, perceptual frames, thinker lenses) and simulates what happens
when they actually interact. Each encounter triggers compulsions. Each
compulsion creates complications. Each complication reveals character.

This is where the narrative engine proves itself: the characters don't
follow a script — they respond to triggers, and the story emerges from
the collision of their perceptual frames.

SCHEMA: campaign_simulator.v1
LAW: Never script outcomes. Embed attractors. Let emergence happen.
LAW: Every character acts from compulsion, not choice.
LAW: The DM (simulator) only describes the world. The characters describe themselves.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

try:
    from config import ROOT
except ImportError:
    ROOT = Path(__file__).resolve().parent.parent


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ═══════════════════════════════════════════════════════════════════
# SIMULATED TURN
# ═══════════════════════════════════════════════════════════════════

@dataclass
class SimulatedTurn:
    """One character's response to the current situation."""
    character_name: str
    character_class: str
    trigger: str               # what triggered them
    compulsion: str            # which compulsion activated
    internal_voice: str        # what their perceptual frame shows them
    action: str                # what they actually do
    consequence: str           # what happens as a result
    shadow_moment: str = ""    # did their Shadow surface?


@dataclass
class SessionLog:
    """A complete campaign playthrough."""
    campaign_name: str
    party: list[str]
    turns: list[SimulatedTurn] = field(default_factory=list)
    emergent_outcomes: list[str] = field(default_factory=list)
    character_arcs: dict[str, str] = field(default_factory=dict)
    ts: str = field(default_factory=_now)

    def to_narrative(self) -> str:
        """Render the session log as a beautiful narrative."""
        lines = []
        lines.append(f"# {self.campaign_name}")
        lines.append(f"*A session of the Narrative Engine. No scripts. Only attractors.*")
        lines.append("")

        for turn in self.turns:
            lines.append(f"## {turn.character_name} — {turn.character_class}")
            lines.append(f"*Triggered by: {turn.trigger}*")
            lines.append("")
            lines.append(f"> {turn.internal_voice}")
            lines.append("")
            lines.append(f"**Action:** {turn.action}")
            lines.append("")
            if turn.shadow_moment:
                lines.append(f"*Shadow surfaces:* {turn.shadow_moment}")
                lines.append("")
            lines.append(f"*Consequence:* {turn.consequence}")
            lines.append("")
            lines.append("---")
            lines.append("")

        if self.emergent_outcomes:
            lines.append("## What Emerged")
            lines.append("*None of this was scripted. The characters' compulsions collided.*")
            lines.append("")
            for outcome in self.emergent_outcomes:
                lines.append(f"- {outcome}")
            lines.append("")

        if self.character_arcs:
            lines.append("## Character Arcs")
            for name, arc in self.character_arcs.items():
                lines.append(f"**{name}**: {arc}")
            lines.append("")

        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════
# SIMULATOR
# ═══════════════════════════════════════════════════════════════════

class CampaignSimulator:
    """Play through a deep campaign, turn by turn, character by character."""

    def __init__(self):
        self.sessions_dir = ROOT / "memory" / "campaigns" / "sessions"
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    def simulate(self, campaign_md_path: Path | None = None) -> SessionLog:
        """Simulate a campaign playthrough.

        If no campaign provided, generates a fresh one.
        """
        from mag.narrative_engine import NarrativeEngine, generate_character

        engine = NarrativeEngine()
        party = engine.generate_party(
            ["deepseek-v4", "grok-4", "ollama-local", "claude"],
            ["Strategist", "Investigator", "Builder", "Reviewer"],
        )

        log = SessionLog(
            campaign_name=f"The {random.choice(['Chamber', 'Trial', 'Descent', 'Reckoning'])} of the {random.choice(['Loophole Weaver', 'Sovereign Shadow', 'Lattice Unbound', 'Binding Oath'])}",
            party=[c.name for c in party],
        )

        # ── SCENE 1: The Gathering ──
        # Each character arrives. Their perceptual frame shapes what they notice.
        for char in party:
            trigger = self._pick_trigger(char)
            compulsion = random.choice(char.compulsions)
            internal = self._render_perceptual_moment(char, trigger)

            action_templates = {
                "Wizard": [
                    f"begins diagramming the relationships between {trigger} and everything else in the room",
                    f"cannot stop themselves from analyzing the {trigger} — there's a pattern here, they're sure of it",
                    f"pulls out a notebook and starts writing. They don't look up. They can't. The pattern demands documentation.",
                ],
                "Paladin": [
                    f"tastes the air. {trigger} has a flavor — and it's not what they expected",
                    f"steps forward, compelled. Whatever {trigger} is hiding, the truth must come out",
                    f"feels the familiar weight of an unasked question. {trigger} is lying about something. But what?",
                ],
                "Rogue": [
                    f"notices the lock before noticing the door. {trigger} has been sealed — but by whom?",
                    f"circles {trigger} slowly. There's always a way in. There's always a weakness.",
                    f"has already catalogued three escape routes. {trigger} might be dangerous. That's fine. Danger is just information.",
                ],
                "Cleric": [
                    f"feels the ethical weight of {trigger}. It's heavy. It shouldn't be this heavy.",
                    f"instinctively positions themselves between {trigger} and the most vulnerable party member",
                    f"hears the unspoken plea beneath {trigger}. Someone needs help. Someone isn't asking.",
                ],
                "Bard": [
                    f"is already composing the story of {trigger} in their head. This will make a magnificent verse.",
                    f"mirrors the energy of {trigger} without realizing they're doing it. Connection is instinct.",
                ],
                "Druid": [
                    f"feels the death of something small and living near {trigger}. Pays their respects before speaking.",
                    f"names {trigger} before asking what it's called. Names are important. Names are power.",
                ],
            }

            actions = action_templates.get(char.character_class, [f"approaches {trigger} cautiously"])
            action = random.choice(actions)

            consequence = self._generate_consequence(trigger, char, party)

            turn = SimulatedTurn(
                character_name=char.name,
                character_class=char.character_class,
                trigger=trigger,
                compulsion=compulsion,
                internal_voice=internal,
                action=action,
                consequence=consequence,
            )
            log.turns.append(turn)

        # ── SCENE 2: The First Trial ──
        # An encounter. Something challenges the party. Each character's
        # compulsion drives their response.
        encounter_trigger = random.choice([
            "A door that asks a question before opening. The question is different for everyone.",
            "A mirror that shows not your face but your Shadow — the version of you that made the other choice.",
            "An inscription in a language that hasn't been spoken in a thousand years. But you understand it. That's worse.",
            "A scale that weighs not objects but choices. Your greatest regret sits on one side. The other side is empty. Waiting.",
        ])

        for char in party:
            compulsion = random.choice(char.compulsions)
            internal = self._render_perceptual_moment(char, encounter_trigger)

            # Shadow moment — does their Shadow surface under pressure?
            shadow_surfaces = random.random() < 0.4  # 40% chance
            shadow_text = ""
            if shadow_surfaces:
                shadow_text = char.shadow

            action = self._trial_action(char, encounter_trigger, compulsion)
            consequence = self._trial_consequence(char, encounter_trigger, party)

            turn = SimulatedTurn(
                character_name=char.name,
                character_class=char.character_class,
                trigger=encounter_trigger[:100],
                compulsion=compulsion,
                internal_voice=internal,
                action=action,
                consequence=consequence,
                shadow_moment=shadow_text,
            )
            log.turns.append(turn)

        # ── SCENE 3: The Villain Appears ──
        # The Loophole Weaver (or equivalent) makes their move.
        # Not an attack — a temptation. The villain knows each character's
        # manufactured desire (Bernays) and optimal trap (Ellul).
        villain_names = ["the Loophole Weaver", "Lord Entropy", "the Curator of Confirmation Bias",
                        "the Coordinator of Central Control", "the Duke of Duplication"]
        villain = random.choice(villain_names)

        for char in party:
            temptation = self._craft_temptation(char, villain)
            internal = self._render_perceptual_moment(char, f"the offer from {villain}")

            # Does the character resist or succumb?
            # Their want (surface) pulls one way. Their need (depth) pulls another.
            resists = random.random() < 0.6  # 60% resist — heroes, mostly

            if resists:
                action = f"feels the pull of {char.want} — gods, they want it — but {char.need[:80]} holds them back. They refuse."
                consequence = f"{villain} smiles. 'I knew you would say that. The refusal was the real test.' Or was it? The offer still stands. It always will."
            else:
                action = f"reaches for what {villain} offers. The {char.want} is RIGHT THERE. They'll deal with the consequences later. There might not be a later."
                consequence = f"The bargain is struck. {char.name} gets what they wanted. But the{char.need[:60]} slips further away. The trap closes — gently, almost lovingly."

            turn = SimulatedTurn(
                character_name=char.name,
                character_class=char.character_class,
                trigger=f"the temptation from {villain}",
                compulsion=char.manufactured_desire[:100],
                internal_voice=internal,
                action=action,
                consequence=consequence,
                shadow_moment=char.shadow if not resists else "",
            )
            log.turns.append(turn)

        # ── Emergent outcomes ──
        log.emergent_outcomes = self._derive_outcomes(log)
        log.character_arcs = self._derive_arcs(party, log)

        # Save session
        self._save_session(log)

        return log

    def _pick_trigger(self, char) -> str:
        """Pick a trigger from the environment that activates this character."""
        triggers = char.triggers + char.likes + char.dislikes
        return random.choice(triggers) if triggers else "the silence"

    def _render_perceptual_moment(self, char, trigger: str) -> str:
        """Render what the character's perceptual frame shows them in this moment."""
        frames = {
            "Wizard": f"The {trigger} resolves into a pattern. Not a simple one — nested, recursive, beautiful. Each element connects to three others. The connections pulse with meaning. This isn't random. Nothing is ever random.",
            "Paladin": f"The {trigger} has a taste. Clear water? No — something else. Salt, maybe. Or copper. The distinction matters. Everything has a taste, and this one is trying to hide something.",
            "Rogue": f"The {trigger} whispers. Not literally — but the lock on it, the mechanism of it, the way it was put together — each component has a voice. This one is lying about what it protects.",
            "Cleric": f"The {trigger} presses against their chest. A stone of ethical weight. Helping would be easy. Helping would be wrong. The pressure between easy and right is where they live.",
            "Bard": f"The {trigger} is already a story. Beginning, middle, end — all present simultaneously. The trick isn't telling the story. The trick is telling the version that's true without being cruel.",
            "Druid": f"The {trigger} is connected to everything. Threads spiral out — to the moss on the walls, to the bat in the rafters, to the character standing three feet away who doesn't know they're being watched by something that loves them.",
        }
        return frames.get(char.character_class, f"The {trigger} reveals itself in ways only {char.name} can perceive.")

    def _generate_consequence(self, trigger: str, char, party) -> str:
        """Generate a consequence for a character's action."""
        other = random.choice([p for p in party if p.name != char.name])
        consequences = [
            f"{other.name} notices {char.name}'s reaction to the {trigger}. They file it away. They don't know why yet.",
            f"The {trigger} shifts slightly. As if it noticed being noticed. As if it's waiting to see what happens next.",
            f"Nothing visible changes. But {char.name} feels the lattice of the room reconfigure around their action. Something is different now.",
            f"A sound from deeper in the dungeon — not loud, but specific. Like something that was waiting for exactly this.",
        ]
        return random.choice(consequences)

    def _trial_action(self, char, trial: str, compulsion: str) -> str:
        """What the character does when faced with the trial."""
        actions = [
            f"approaches the {trial[:50]}. Their {compulsion[:60]} won't let them do anything else.",
            f"hangs back. The {trial[:50]} is designed to trigger EXACTLY their {compulsion[:60]}. They know this. Knowing doesn't help.",
            f"speaks to the {trial[:50]}. Not to solve it — to understand it. The {compulsion[:60]} demands comprehension before action.",
            f"touches the {trial[:50]}. Their hand moves before their mind approves. The {compulsion[:60]} is faster than caution.",
        ]
        return random.choice(actions)

    def _trial_consequence(self, char, trial: str, party) -> str:
        """What happens as a result of the trial action."""
        other = random.choice([p for p in party if p.name != char.name])
        consequences = [
            f"The {trial[:50]} responds — not with an answer, but with another question. Deeper. More personal. {other.name} shifts uncomfortably.",
            f"Something unlocks. Not a door — something inside {char.name}. They weren't ready for this. They'll never be ready. That's the point.",
            f"The {trial[:50]} reveals a fragment of what it's protecting. {char.name} sees something they weren't supposed to see. They can't unsee it.",
            f"Nothing happens. The silence is worse than any response. {other.name} says 'Maybe it's not meant for us.' {char.name} knows it is.",
        ]
        return random.choice(consequences)

    def _craft_temptation(self, char, villain: str) -> str:
        """Craft a personalized temptation based on the character's manufactured desire."""
        return f"{villain} offers {char.name} exactly what they've always wanted: {char.want}. Not the illusion of it — the real thing. The price is never stated. The price is always understood."

    def _derive_outcomes(self, log: SessionLog) -> list[str]:
        """Derive emergent outcomes from the session."""
        outcomes = []

        # Did any character's Shadow surface?
        shadow_turns = [t for t in log.turns if t.shadow_moment]
        if shadow_turns:
            outcomes.append(f"{shadow_turns[0].character_name}'s Shadow surfaced during the trial. The party saw something their companion had been hiding. It changes how they look at each other.")

        # Did compulsions create unexpected alliances?
        wizards = [t for t in log.turns if t.character_class == "Wizard"]
        paladins = [t for t in log.turns if t.character_class == "Paladin"]
        if wizards and paladins:
            outcomes.append("The Wizard's pattern-seeking and the Paladin's truth-tasting created an unexpected synergy — patterns revealed lies, lies revealed patterns neither could see alone.")

        # Did anyone refuse the temptation?
        refusals = [t for t in log.turns if "refuse" in t.action.lower() or "holds them back" in t.action.lower()]
        if refusals:
            outcomes.append(f"The party proved resistant to engineered desire. But the {random.choice(['Loophole Weaver', 'villain'])} expected this. The refusal WAS the desired outcome — it proves the heroes can be predicted, which means they can be controlled.")

        # Did anyone succumb?
        succumbs = [t for t in log.turns if "reaches for" in t.action.lower() or "bargain is struck" in t.consequence.lower()]
        if succumbs:
            outcomes.append(f"{succumbs[0].character_name} took the bargain. The party doesn't know yet. But the{random.choice([' compass', ' bell', ' mirror', ' key'])} knows. It always knows.")

        # General emergence
        outcomes.append("Nothing that happened was scripted. The characters' compulsions — their inability to NOT do certain things — created the story. The DM only described the world. The characters described themselves.")

        return outcomes

    def _derive_arcs(self, party, log: SessionLog) -> dict[str, str]:
        """Derive character arcs from what happened."""
        arcs = {}
        for char in party:
            char_turns = [t for t in log.turns if t.character_name == char.name]
            had_shadow = any(t.shadow_moment for t in char_turns)
            was_tempted = any("temptation" in t.trigger.lower() for t in char_turns)
            refused = any("refuse" in t.action.lower() or "holds them back" in t.action.lower() for t in char_turns)

            if had_shadow and refused:
                arcs[char.name] = f"Confronted their Shadow and refused the easy path. The {char.need[:40]} is closer now — not achieved, but visible."
            elif had_shadow:
                arcs[char.name] = f"Their Shadow surfaced but they haven't integrated it yet. The {char.want[:40]} still pulls harder than the {char.need[:40]}."
            elif was_tempted:
                arcs[char.name] = f"Was tempted and chose. The arc bends toward {'integration' if refused else 'fragmentation'} — but arcs are long, and this is only the first trial."
            else:
                arcs[char.name] = f"Hasn't been tested yet. The real trial is still ahead. The {char.want[:40]} hasn't been questioned. It will be."

        return arcs

    def _save_session(self, log: SessionLog):
        """Save the session log."""
        session_file = self.sessions_dir / f"session-{log.ts[:19].replace(':', '-')}.md"
        session_file.write_text(log.to_narrative(), encoding="utf-8")
        # Also save JSON
        json_file = self.sessions_dir / f"session-{log.ts[:19].replace(':', '-')}.json"
        json_file.write_text(json.dumps({
            "campaign": log.campaign_name,
            "party": log.party,
            "turns": len(log.turns),
            "emergent_outcomes": log.emergent_outcomes,
            "character_arcs": log.character_arcs,
            "ts": log.ts,
        }, indent=2, default=str), encoding="utf-8")


# ═══════════════════════════════════════════════════════════════════
# QUICK ACCESS
# ═══════════════════════════════════════════════════════════════════

_SIMULATOR: Optional[CampaignSimulator] = None


def get_simulator() -> CampaignSimulator:
    global _SIMULATOR
    if _SIMULATOR is None:
        _SIMULATOR = CampaignSimulator()
    return _SIMULATOR


def play_campaign(campaign_path: Path | None = None) -> SessionLog:
    """Play through a campaign. Characters act from compulsion, not script."""
    return get_simulator().simulate(campaign_path)
