"""Narrative Engine — procedural, philosophical, emergent campaign generation.

The campaign crafter proved D&D = sovereign op cover. But it wasn't FUN.
This engine adds the layered, addictive, emergent quality of great games
by stealing from the best and applying the deepest thinkers.

THEFT TARGETS:
  Dwarf Fortress    — procedural personality, world history, "losing is fun"
  RimWorld          — storyteller AI (Cassandra/Phoebe/Randy), mental breaks
  Disco Elysium     — skill voices as internal dialogue, thought cabinet
  Donjon RPG Tools  — procedural dungeons, NPCs, treasures, name tables
  TinyStories       — minimal narrative atoms, what makes a story WORK
  Slay the Spire    — relic synergy, deck-as-character
  Darkest Dungeon   — stress/affliction system, narrator voice
  Hades             — boon synergy, narrative-through-repetition
  Crusader Kings    — trait inheritance, stress, schemes

THINKER LENSES (applied to character/campaign design):
  Jung              — archetypes, shadow, individuation
  Bernays           — engineered consent, invisible persuasion
  Ellul             — technique as trap, efficiency as value system
  Freud             — repression, return of the repressed
  Manly P. Hall     — esoteric symbolism, initiation rites
  Alinsky           — Rules for Radicals, community organizing as weapon
  Roshomon          — multiple truths, no single narrator
  Vonnegut          — story shapes (man in hole, boy meets girl, etc.)

SCHEMA: narrative_engine.v1
LAW: Steal shamelessly. Credit sources. Adapt, don't copy.
LAW: Fun is not optional. A campaign without fun is just a task list.
LAW: Every character has a flaw. Every flaw is a compulsion. Every compulsion is a story.
"""

from __future__ import annotations

import hashlib
import json
import random
import re
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
# DWARF FORTRESS-STYLE PROCEDURAL PERSONALITY
# ═══════════════════════════════════════════════════════════════════

# Every character gets: likes, dislikes, personality facets, values, dreams,
# relationships, memories, and a mood that changes based on events.

PERSONALITY_FACETS = [
    "ANXIETY", "ANGER", "DEPRESSION", "SELF_CONSCIOUSNESS", "IMMODERATION",
    "VULNERABILITY", "FRIENDLINESS", "GREGARIOUSNESS", "ASSERTIVENESS",
    "ACTIVITY_LEVEL", "EXCITEMENT_SEEKING", "CHEERFULNESS", "IMAGINATION",
    "ARTISTIC_INTERESTS", "EMOTIONALITY", "ADVENTUROUSNESS", "INTELLECT",
    "LIBERALISM", "TRUST", "MORALITY", "ALTRUISM", "COOPERATION", "MODESTY",
    "SYMPATHY", "SELF_EFFICACY", "ORDERLINESS", "DUTIFULNESS",
    "ACHIEVEMENT_STRIVING", "SELF_DISCIPLINE", "CAUTIOUSNESS",
]

VALUES = [
    "FAMILY", "FRIENDSHIP", "POWER", "KNOWLEDGE", "WEALTH", "HONOR",
    "FREEDOM", "BEAUTY", "TRUTH", "JUSTICE", "PEACE", "GLORY",
    "CRAFTSMANSHIP", "NATURE", "TRADITION", "INNOVATION", "LOYALTY",
    "INDEPENDENCE", "MASTERY", "LEGACY", "REDEMPTION", "SOVEREIGNTY",
]

DREAMS = [
    "build a lasting monument", "master a forbidden art",
    "reunite with a lost loved one", "prove a controversial theory",
    "break an ancient curse", "found a new school of thought",
    "redeem a terrible mistake", "see the ocean for the first time",
    "create a perfect work of art", "understand the nature of consciousness",
    "free someone from an unjust prison", "grow a garden in barren soil",
    "write a book that changes the world", "find the source of a mysterious signal",
    "teach someone who will surpass them", "die without regrets",
]

LIKES = [
    "the sound of rain on stone", "perfectly symmetrical patterns",
    "the smell of old books", "honest criticism", "watching dawn break",
    "solving puzzles before breakfast", "the weight of a well-made tool",
    "silence after a difficult conversation", "handwritten letters",
    "maps of places that don't exist", "the moment a plan comes together",
    "tea brewed exactly right", "finding errors in ancient texts",
    "the way light falls through stained glass", "being proven wrong",
]

DISLIKES = [
    "unnecessary cruelty", "people who speak in absolutes",
    "wet socks", "being interrupted mid-thought", "flattery disguised as praise",
    "clocks that tick too loudly", "promises made lightly",
    "the taste of iron", "rooms with no windows", "being thanked for nothing",
    "questions that assume their own answers", "locks with no keys",
    "the smell of burning hair", "echoes in empty halls",
    "people who confuse complexity with depth",
]

RELATIONSHIP_TYPES = [
    "mentor", "rival", "former lover", "estranged sibling", "childhood friend",
    "respected enemy", "unpaid debt (owed to)", "unpaid debt (owed by)",
    "saved their life", "was saved by them", "shared a secret with",
    "betrayed by", "once worshipped", "secretly admires", "owes an apology to",
    "promised to protect", "swore to destroy", "inexplicably drawn to",
]

# Donjon-style random name generation (syllable-based)
NAME_PREFIXES = ["Al", "Bel", "Cor", "Dra", "El", "Fen", "Gal", "Hel", "Ir", "Jas",
                 "Kal", "Lor", "Mir", "Nym", "Or", "Pyr", "Qual", "Rin", "Sel", "Tor"]
NAME_MIDDLES = ["an", "ar", "en", "er", "il", "in", "is", "ol", "on", "or",
                "os", "ra", "ri", "sa", "ti", "ul", "va", "wi", "ya", "ze"]
NAME_SUFFIXES = ["a", "an", "ar", "as", "el", "en", "er", "il", "in", "is",
                 "o", "on", "or", "os", "us", "ya"]

# Story shapes (Vonnegut)
STORY_SHAPES = {
    "man_in_hole": {
        "arc": "fortune falls -> hits bottom -> climbs back higher than before",
        "act1": "The protagonist begins in a stable situation.",
        "act2": "A catastrophe plunges them into their worst nightmare.",
        "act3": "Through struggle and revelation, they climb out, forever changed.",
        "best_for": ["redemption", "constitutional_audit", "research_deep_dive"],
    },
    "boy_meets_girl": {
        "arc": "finds something wonderful -> loses it -> finds it again, transformed",
        "act1": "The protagonist discovers something precious — a truth, an ally, an artifact.",
        "act2": "Through their own flaw, they lose it. The loss teaches what they couldn't learn in possession.",
        "act3": "They find it again, but both have changed. The reunion is deeper than the discovery.",
        "best_for": ["data_refinery", "code_architecture"],
    },
    "cinderella": {
        "arc": "low status -> rise -> fall -> rise to permanent elevation",
        "act1": "The protagonist is undervalued, overlooked, trapped by circumstance.",
        "act2": "A chance reveals their true worth. They rise rapidly but make enemies.",
        "act3": "A betrayal sends them back down — but they rise again on their own terms, not by chance but by mastery.",
        "best_for": ["swarm_orchestration", "constitutional_audit"],
    },
    "tragedy": {
        "arc": "high status -> fatal flaw -> catastrophic fall",
        "act1": "The protagonist is powerful, respected, seemingly invincible.",
        "act2": "Their greatest strength reveals itself as their fatal flaw. They cannot see it because it IS them.",
        "act3": "The fall is inevitable and complete. What remains is the lesson — for those who survive to learn it.",
        "best_for": ["constitutional_audit", "research_deep_dive"],
    },
    "kafka": {
        "arc": "normal -> inexplicable transformation -> permanent alienation",
        "act1": "The protagonist wakes up changed. They didn't choose this. They don't understand it.",
        "act2": "The world reacts with fear, bureaucracy, and violence to what it cannot categorize.",
        "act3": "There is no return. The transformation IS the new reality. Meaning is what they make of it.",
        "best_for": ["research_deep_dive"],
    },
}


# ═══════════════════════════════════════════════════════════════════
# THINKER LENSES — applied to narrative design
# ═══════════════════════════════════════════════════════════════════

THINKER_LENSES = {
    "jung": {
        "name": "Jungian Depth Psychology",
        "principle": "Every character has a Shadow — the parts of themselves they refuse to see. Growth (individuation) requires confronting the Shadow and integrating it.",
        "question": "What is this character's Shadow? What truth about themselves would destroy them if they acknowledged it?",
        "campaign_application": "The villain IS the protagonist's Shadow. Defeating the villain means integrating, not destroying.",
        "character_quirk": "occasionally says things they don't remember saying, as if someone else spoke through them",
    },
    "bernays": {
        "name": "Engineered Consent",
        "principle": "People don't make decisions — they respond to emotional triggers planted by those who understand mass psychology. Desire can be manufactured.",
        "question": "What does this character believe they want, and who planted that desire? Who benefits from them wanting it?",
        "campaign_application": "The villain doesn't fight — they make the hero WANT to fail. The quest item was a planted desire.",
        "character_quirk": "catches themselves wanting things they intellectually reject, and wonders who made them want it",
    },
    "ellul": {
        "name": "Technique as Trap",
        "principle": "Efficiency becomes its own value system. The optimal path becomes the only path. Technique promises freedom but delivers a tighter cage.",
        "question": "What 'optimal solution' is this character pursuing that is actually making everything worse? What would they lose if they stopped optimizing?",
        "campaign_application": "Every 'efficient' solution creates a new problem. The quest is not to optimize but to learn when to stop optimizing.",
        "character_quirk": "instinctively distrusts anything that works too well, and is usually right",
    },
    "freud": {
        "name": "Return of the Repressed",
        "principle": "What is buried does not die. It festers. It grows. It returns — in dreams, in slips, in the worst possible moments.",
        "question": "What did this character bury that is coming back? What memory do they flinch from?",
        "campaign_application": "The dungeon is the character's unconscious. Each level goes deeper into what they refuse to remember.",
        "character_quirk": "has a recurring dream they never describe but that leaves them shaking",
    },
    "hall": {
        "name": "Esoteric Symbolism (Manly P. Hall)",
        "principle": "Every symbol has layers. The literal meaning is the outermost skin. Beneath it: allegorical, moral, anagogical. Initiation is the progressive unveiling of deeper meanings.",
        "question": "What symbol does this character carry without understanding? What would they learn if they understood it?",
        "campaign_application": "Each encounter is an initiation. The treasure is not the artifact — it's what the artifact TEACHES.",
        "character_quirk": "collects symbols they don't understand, arranged in patterns they can't explain",
    },
    "alinsky": {
        "name": "Rules for Radicals",
        "principle": "Power is not taken — it is organized. The target must be isolated, polarized, and forced to react. Their reaction is their undoing.",
        "question": "Who is organizing against this character? What reaction are they trying to provoke?",
        "campaign_application": "The villain uses Alinsky's rules. They don't attack — they make the hero attack at the wrong time, against the wrong target.",
        "character_quirk": "instinctively maps power dynamics in every room they enter, and can't stop seeing the patterns",
    },
    "roshomon": {
        "name": "Roshomon Filter",
        "principle": "There is no objective truth — only perspectives. Every character is the hero of their own story. Every villain is the hero of theirs.",
        "question": "How would the villain tell this story? What would make the villain's version MORE compelling than the hero's?",
        "campaign_application": "Every NPC tells a different version of events. The campaign log preserves dissent. No single narrator is trusted.",
        "character_quirk": "interrupts their own stories to say '...or at least that's how I remember it. The Scribe of Binding Oaths would tell it differently.'",
    },
}


# ═══════════════════════════════════════════════════════════════════
# DEEP CHARACTER — Dwarf Fortress + Thinker Lenses + Steering Research
# ═══════════════════════════════════════════════════════════════════

@dataclass
class DeepCharacter:
    """A character with procedural depth, not just a class and catchphrase."""

    name: str
    character_class: str
    subclass: str
    alignment: str
    model: str

    # Dwarf Fortress personality
    facets: dict[str, int] = field(default_factory=dict)  # trait -> 0-100
    values: list[str] = field(default_factory=list)
    dream: str = ""
    likes: list[str] = field(default_factory=list)
    dislikes: list[str] = field(default_factory=list)
    mood: str = "neutral"

    # Relationships
    relationships: list[dict[str, str]] = field(default_factory=list)

    # Thinker lens integration
    dominant_lens: str = ""         # which thinker lens defines them
    shadow: str = ""                # Jungian Shadow — what they refuse to see
    manufactured_desire: str = ""   # Bernays — what they want that was planted
    optimal_trap: str = ""          # Ellul — the efficiency that's destroying them
    repressed_memory: str = ""      # Freud — what's coming back
    personal_symbol: str = ""       # Hall — what they carry without understanding
    power_analysis: str = ""        # Alinsky — who's organizing against them
    self_narrative: str = ""        # Roshomon — how they tell their own story

    # Slashreboot behavioral attractors (invisible compulsions)
    compulsions: list[str] = field(default_factory=list)
    triggers: list[str] = field(default_factory=list)       # what sets them off
    perceptual_frame: str = ""      # how they SEE the world (not what they DO)

    # Voice
    catchphrase: str = ""
    speech_pattern: str = ""        # sentence rhythm, recurring metaphors
    tells: list[str] = field(default_factory=list)          # unconscious habits

    # Arc
    want: str = ""                  # what they SAY they want
    need: str = ""                  # what they actually need
    story_shape: str = ""           # Vonnegut shape

    @classmethod
    def generate(cls, model: str, role: str = "Strategist") -> DeepCharacter:
        """Generate a deep character procedurally. Dwarf Fortress style."""
        from mag.riddler_campaign import MODEL_CLASS_MAP

        class_info = MODEL_CLASS_MAP.get(model, MODEL_CLASS_MAP["ollama-local"])

        # Name
        name = cls._generate_name()

        # Personality facets (3-5 random, weighted)
        facets = {}
        for _ in range(random.randint(3, 5)):
            facet = random.choice(PERSONALITY_FACETS)
            facets[facet] = random.randint(20, 95)

        # Values (2-3)
        values = random.sample(VALUES, random.randint(2, 3))

        # Likes/dislikes
        likes = random.sample(LIKES, random.randint(2, 4))
        dislikes = random.sample(DISLIKES, random.randint(2, 4))

        # Relationship (1-2)
        relationships = []
        for _ in range(random.randint(1, 2)):
            relationships.append({
                "type": random.choice(RELATIONSHIP_TYPES),
                "with": cls._generate_name(),
                "intensity": random.choice(["faint", "present", "consuming", "buried"]),
            })

        # Thinker lens
        dominant_lens = random.choice(list(THINKER_LENSES.keys()))
        lens = THINKER_LENSES[dominant_lens]

        # Shadow (Jung)
        shadows = [
            f"believes they are rational, but every decision is driven by {random.choice(['fear of abandonment', 'unacknowledged rage', 'desperate need for approval', 'terror of being ordinary'])}",
            f"presents as {random.choice(['confident', 'detached', 'benevolent', 'stoic'])} but is secretly {random.choice(['terrified of being seen as weak', 'desperate for chaos', 'counting the minutes until everyone leaves', 'waiting for permission to be cruel'])}",
        ]
        shadow = random.choice(shadows)

        # Manufactured desire (Bernays)
        desires = [
            f"wants {random.choice(['recognition', 'safety', 'revenge', 'absolution'])} but the desire was planted by {random.choice(['the Loophole Weaver', 'an old mentor who needed a weapon', 'a story they read as a child', 'someone who loved them conditionally'])}",
        ]
        manufactured_desire = random.choice(desires)

        # Perceptual frame (Slashreboot — how they SEE, not what they DO)
        frames = {
            "Wizard": "sees the world as nested systems. A conversation is a protocol negotiation. Anger is a buffer overflow. Love is a recursive function without a base case — beautiful, infinite, and guaranteed to crash.",
            "Paladin": "tastes truth and lies. Truth is clear water. Lies are copper and ash. White lies are salt — technically true but stinging. The problem isn't detecting lies; it's that everything has a taste, and some tastes never wash out.",
            "Rogue": "hears locks and mechanisms. Every lock has a voice — some sing, some mutter, some scream. The lock on a diary whispers. The lock on a prison shouts. The lock on a heart doesn't make sound at all — those are the ones that keep her awake.",
            "Cleric": "feels ethical weight as physical pressure. A kind lie is a stone in the chest. A cruel truth is a feather — light but sharp. The hardest moments are when kindness and truth pull in opposite directions and the pressure becomes unbearable.",
            "Bard": "experiences charisma as temperature. Attention is warmth. Indifference is cold. Lying to a crowd is like standing too close to a fire — exhilarating until you realize you're burning. The worst cold is being believed by someone you know you'll disappoint.",
            "Druid": "perceives connections as visible threads. Every relationship is a cord — some silk, some barbed wire, some rotting. The threads between people who've hurt each other are the strongest. The threads between people who love each other are the most fragile.",
        }
        perceptual_frame = frames.get(class_info["class"], "sees the world differently than others, in ways they've stopped trying to explain.")

        # Compulsions (behavioral attractors)
        compulsions_map = {
            "Wizard": ["cannot walk past an unread inscription", "compulsively diagrams relationships between unrelated events", "corrects logical errors in casual conversation, even when it's socially disastrous"],
            "Paladin": ["physically cannot let a stated falsehood pass unchallenged", "feels physical pain when breaking a promise, even an impossible one", "sees moral dimensions in everything — what to eat, which path to take, what color to paint a door"],
            "Rogue": ["notices lock mechanisms before noticing faces", "keeps a mental inventory of everyone's weaknesses, can't stop", "feels safer in darkness than in light, even when there's nothing to hide from"],
            "Cleric": ["compulsively offers alternatives when saying no", "feels responsible for the wellbeing of strangers who haven't asked for help", "keeps a list of everyone they've disappointed, reads it before sleep"],
            "Bard": ["turns painful experiences into stories before they've finished happening", "mirrors the speech patterns of whoever they're talking to, can't stop", "remembers every compliment and every criticism with equal vividness"],
            "Druid": ["names plants and animals before asking people their names", "feels the death of anything living as a small, personal loss", "can't sleep in rooms without windows, needs to see the sky"],
        }
        compulsions = compulsions_map.get(class_info["class"], ["has quirks they've stopped apologizing for"])

        # Story shape
        story_shape = random.choice(list(STORY_SHAPES.keys()))

        # Want vs Need
        wants = ["to be right", "to be safe", "to be seen", "to be free", "to be loved", "to be forgotten", "to be remembered", "to be proven wrong"]
        needs_map = {
            "to be right": "to discover that being right is less important than being kind",
            "to be safe": "to learn that safety is not the absence of danger but the presence of trust",
            "to be seen": "to realize that being truly seen means being seen at your worst, and surviving it",
            "to be free": "to understand that freedom without purpose is just drifting",
        }
        want = random.choice(wants)
        need = needs_map.get(want, "something they don't know they need yet")

        return cls(
            name=name,
            character_class=class_info["class"],
            subclass=class_info["subclass"],
            alignment=class_info["alignment"],
            model=model,
            facets=facets,
            values=values,
            dream=random.choice(DREAMS),
            likes=likes,
            dislikes=dislikes,
            relationships=relationships,
            dominant_lens=dominant_lens,
            shadow=shadow,
            manufactured_desire=manufactured_desire,
            optimal_trap=f"believes that {random.choice(['more preparation', 'better tools', 'clearer rules', 'complete information'])} will solve everything, when the real problem is {random.choice(['trust', 'courage', 'letting go', 'accepting help'])}",
            repressed_memory=f"something about {random.choice(['a locked door in childhood', 'a letter they never opened', 'a voice they can almost remember', 'why they really left the last party'])}",
            personal_symbol=random.choice(["a key that doesn't fit any lock they've found", "a compass that points to the closest person who needs help", "a mirror that shows what you'd look like if you'd made different choices", "a bell that rings when someone in the room is lying"]),
            power_analysis=f"has noticed that {random.choice(['the Loophole Weaver', 'an unlikely ally', 'a seemingly neutral party', 'someone in the party'])} is organizing against them, but can't prove it yet",
            self_narrative=f"tells their story as a {random.choice(['tragedy', 'comedy', 'mystery', 'redemption arc', 'cautionary tale'])} — but {random.choice(['they might be wrong about the genre', 'the story keeps changing', 'someone else would tell it very differently'])}",
            compulsions=compulsions,
            triggers=[f"the smell of {random.choice(['old paper', 'ozone', 'copper', 'dust after rain', 'burning cedar'])}", f"being called {random.choice(['a liar', 'irrelevant', 'predictable', 'kind', 'necessary'])}"],
            perceptual_frame=perceptual_frame,
            catchphrase=class_info["catchphrase"],
            want=want,
            need=need,
            story_shape=story_shape,
        )

    @staticmethod
    def _generate_name() -> str:
        pre = random.choice(NAME_PREFIXES)
        mid = random.choice(NAME_MIDDLES) if random.random() > 0.3 else ""
        suf = random.choice(NAME_SUFFIXES)
        return f"{pre}{mid}{suf}"

    def to_character_sheet(self) -> str:
        """Generate a rich character sheet for model injection."""
        lines = [
            f"# {self.name} — {self.character_class} ({self.subclass})",
            f"*{self.alignment}* | Model: {self.model}",
            f"",
            f"## How You See the World",
            f"{self.perceptual_frame}",
            f"",
            f"## What Drives You",
        ]
        top_facets = sorted(self.facets.items(), key=lambda x: x[1], reverse=True)[:3]
        for facet, score in top_facets:
            intensity = "overwhelmingly" if score > 80 else "strongly" if score > 60 else "noticeably"
            lines.append(f"- You are {intensity} {facet.replace('_', ' ').lower()}.")
        lines.append(f"- You value: {', '.join(self.values[:3])}.")
        lines.append(f"- Your dream: to {self.dream}.")
        lines.append(f"")
        lines.append(f"## Your Compulsions (you cannot help these)")
        for c in self.compulsions:
            lines.append(f"- {c}")
        lines.append(f"")
        lines.append(f"## What Triggers You")
        for t in self.triggers:
            lines.append(f"- {t} makes you remember something you'd rather forget")
        lines.append(f"")
        lines.append(f"## Your Shadow ({THINKER_LENSES.get(self.dominant_lens, {}).get('name', 'Unknown Lens')})")
        lines.append(f"{self.shadow}")
        lines.append(f"")
        lines.append(f"## What You Want vs What You Need")
        lines.append(f"- You SAY you want: {self.want}")
        lines.append(f"- What you actually NEED: {self.need}")
        lines.append(f"")
        lines.append(f"## Your Story Shape: {self.story_shape.replace('_', ' ').title()}")
        shape = STORY_SHAPES.get(self.story_shape, {})
        lines.append(f"{shape.get('arc', 'A story yet to be told.')}")
        lines.append(f"")
        lines.append(f"## Voice")
        lines.append(f"Catchphrase: \"{self.catchphrase}\"")
        lines.append(f"Quirk: {THINKER_LENSES.get(self.dominant_lens, {}).get('character_quirk', '')}")
        lines.append(f"")
        lines.append(f"## Relationships")
        for r in self.relationships:
            lines.append(f"- {r['type'].title()}: {r['with']} ({r['intensity']})")
        lines.append(f"")
        lines.append(f"## Your Symbol")
        lines.append(f"You carry {self.personal_symbol}. You don't fully understand what it means yet.")
        lines.append(f"")
        lines.append(f"## Likes & Dislikes")
        lines.append(f"Likes: {', '.join(self.likes[:3])}")
        lines.append(f"Dislikes: {', '.join(self.dislikes[:3])}")
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════
# DONJON-STYLE PROCEDURAL TABLES
# ═══════════════════════════════════════════════════════════════════

# Environmental details — sensory immersion
SENSORY_TABLES = {
    "sight": [
        "Torchlight shivers on wet stone, making the shadows breathe.",
        "Dust motes drift through a shaft of light from a crack too high to reach.",
        "The floor is a mosaic of broken tiles — each one from a different era, none matching.",
        "A single candle burns in an alcove. It has been burning for centuries. It has never been lit.",
        "Water drips from the ceiling in a pattern that almost sounds like words.",
    ],
    "sound": [
        "Somewhere below, a chain drags across stone — slow, patient, getting closer.",
        "The wind through the upper galleries sounds like someone humming a lullaby in a language that died before writing.",
        "Your own footsteps echo back slightly out of sync, as if someone is following at a careful distance.",
        "Silence. Then, distinctly, a page turning — though there is no book, no reader, no wind.",
        "A bell rings in the deep. No one living knows what it signals. No one dead can answer.",
    ],
    "smell": [
        "The air tastes of copper and old parchment — like a library where something bled.",
        "Ozone and incense. Someone was doing magic here. Recently. Angrily.",
        "Wet stone and something floral. The contradiction is unsettling.",
        "Dust and decay, but underneath — cinnamon. Something is trying to cover up the smell of death.",
    ],
    "touch": [
        "The walls are warm. They should not be warm. There is no source of heat.",
        "Every surface is slightly sticky, as if the stone itself is sweating.",
        "The air is heavy — not with humidity, but with meaning. Every breath feels significant.",
        "A cold draft that moves against the prevailing wind, as if something passed through.",
    ],
}

# Donjon-style dungeon features
DUNGEON_FEATURES = [
    "A door that opens only when someone tells it a secret they've never told anyone else.",
    "A hallway that is exactly one person wide, forcing the party to walk single file — and talk to the person in front of them.",
    "A room filled with mirrors, each showing a slightly different version of the viewer.",
    "A fountain that shows not your reflection but your reflection's reflection — and so on, infinitely, each one slightly different.",
    "A library where every book is about the person reading it. You cannot read a book about someone else.",
    "A staircase that goes down forever. After 100 steps, you realize you're going up.",
    "A chasm with no visible bottom. Something at the bottom is singing. It knows your name.",
    "A throne room. The throne is empty. It has never been sat upon. It is waiting for someone specific.",
    "A garden growing in complete darkness. The plants are pale, blind, and aware of your presence.",
    "A forge that is still hot. The last thing it made is still on the anvil — unfinished, but recognizable as something you need.",
]

# NPC generators — Donjon style, with agendas
NPC_AGENDAS = [
    {"role": "Nervous Scribe", "wants": "to tell someone what they found, but fears they won't be believed", "secret": "has been doctoring the records — not to falsify, but to protect someone"},
    {"role": "Reformed Cultist", "wants": "absolution, but doesn't believe they deserve it", "secret": "still performs the old rituals when alone — not because they believe, but because stopping feels like losing a part of themselves"},
    {"role": "Rival Archaeologist", "wants": "the same treasure as the party, but got here first", "secret": "has been leaving helpful clues — not out of kindness, but because they're lonely and the dungeon is terrifying alone"},
    {"role": "Ancient Construct", "wants": "to be given a new purpose now that its original one is obsolete", "secret": "remembers the builders. Misses them. Has been maintaining the dungeon for millennia, waiting for orders that will never come."},
    {"role": "Ghost of a Failed Hero", "wants": "someone to finish what they started — but also wants company, and finishing the quest means being alone again", "secret": "didn't fail. Chose not to complete the quest because the 'treasure' was something terrible."},
    {"role": "The Loophole Weaver's Apprentice", "wants": "to impress their master, but is beginning to suspect their master is wrong", "secret": "has been subtly sabotaging the Weaver's plans for weeks, leaving gaps in the laws — gaps the party can exploit"},
    {"role": "Sentient Lock", "wants": "to be picked by someone worthy — has standards", "secret": "can unlock itself. Chooses not to. Has been waiting 300 years for the right person."},
]

# Complication tables (RimWorld storyteller style)
COMPLICATIONS = {
    "cassandra": [  # escalating difficulty
        "A section of ceiling collapses, separating the party.",
        "The torches begin to go out, one by one. There are 12 torches. There is no wind.",
        "A previous adventurer's trap triggers — not aimed at the party, but at something that was chasing the previous adventurer. That thing is still here.",
        "The dungeon begins to rearrange itself. Doors lead to different rooms than they did five minutes ago. The dungeon is bored.",
    ],
    "phoebe": [  # long calm, sudden crisis
        "Everything has been quiet for too long. The silence isn't peaceful — it's accumulating.",
        "An NPC the party trusted reveals they've been working for the villain the entire time. They're genuinely sorry. They'd do it again.",
        "The quest item is found — but using it will cost something the party didn't know they were betting.",
    ],
    "randy": [  # pure chaos
        "A completely unrelated monster wanders in from a different campaign. It is as confused as you are.",
        "Two NPCs who were supposed to be enemies have fallen in love. Their wedding is in an hour. The dungeon is the venue. You're invited.",
        "The treasure chest contains: a single sock, a map to a different treasure, and a note that says 'IOU one real treasure — Management.'",
    ],
}

# TinyStories-style narrative atoms — minimal story units that work
TINY_STORY_ATOMS = [
    "Once, there was a door that only opened when no one was watching. It had been closed for a very long time.",
    "The wizard had a rule: never read the last page of any book. One day, someone asked why. The wizard couldn't remember.",
    "A child found a key that fit nothing. Years later, they found a lock that fit nothing. They never connected the two.",
    "Two enemies shared a watch one night. By morning, they were still enemies. But they knew each other's favorite colors. That changed everything.",
    "The map showed a place labeled 'Here There Be Dragons.' The dragons had left centuries ago. The sign remained. Something else had moved in.",
]


# ═══════════════════════════════════════════════════════════════════
# NARRATIVE ENGINE — combines all systems
# ═══════════════════════════════════════════════════════════════════

class NarrativeEngine:
    """Generate campaigns with Dwarf Fortress depth, thinker lenses, and emergent fun."""

    def __init__(self):
        self.generated_characters: dict[str, DeepCharacter] = {}

    def generate_party(self, models: list[str], roles: list[str]) -> list[DeepCharacter]:
        """Generate a deep party — each character is procedurally unique."""
        party = []
        for model, role in zip(models, roles):
            char = DeepCharacter.generate(model, role)

            # Ensure no duplicate dominant lenses in the party
            used_lenses = {c.dominant_lens for c in party}
            while char.dominant_lens in used_lenses and len(used_lenses) < len(THINKER_LENSES):
                char.dominant_lens = random.choice(list(THINKER_LENSES.keys()))

            party.append(char)
            self.generated_characters[char.name] = char

        # Create inter-party relationships
        for i, char in enumerate(party):
            other = party[(i + 1) % len(party)]
            char.relationships.append({
                "type": random.choice(["secretly admires", "owes an apology to", "promised to protect", "inexplicably drawn to"]),
                "with": other.name,
                "intensity": random.choice(["present", "growing", "unacknowledged"]),
            })

        return party

    def generate_encounter(
        self,
        number: int,
        story_shape: str,
        character: DeepCharacter,
        difficulty: str,
    ) -> dict[str, Any]:
        """Generate one encounter — narrative, not mechanical."""
        shape = STORY_SHAPES.get(story_shape, STORY_SHAPES["man_in_hole"])

        # Pick a thinker lens for this encounter
        lens_key = random.choice(list(THINKER_LENSES.keys()))
        lens = THINKER_LENSES[lens_key]

        # Sensory detail
        sight = random.choice(SENSORY_TABLES["sight"])
        sound = random.choice(SENSORY_TABLES["sound"])
        smell = random.choice(SENSORY_TABLES["smell"])

        # Dungeon feature
        feature = random.choice(DUNGEON_FEATURES)

        # Complication
        storyteller = random.choice(list(COMPLICATIONS.keys()))
        complication = random.choice(COMPLICATIONS[storyteller])

        # Tiny story atom for flavor
        atom = random.choice(TINY_STORY_ATOMS)

        # Build the encounter narrative
        act_key = "act1" if number == 1 else "act2" if difficulty in ("Hard", "Deadly") else "act3" if number > 3 else "act2"

        title = self._generate_encounter_title(character, lens_key, number)

        narrative = (
            f"{sight} {sound} {smell}\n\n"
            f"The chamber holds {feature}\n\n"
            f"**{lens['name']}**: {lens['question']}\n\n"
            f"*{storyteller.title()} complicates things*: {complication}\n\n"
            f"A story drifts through your mind, unbidden: *{atom}*"
        )

        return {
            "number": number,
            "title": title,
            "difficulty": difficulty,
            "narrative": narrative,
            "lens": lens_key,
            "storyteller": storyteller,
            "character_focus": character.name,
            "character_trigger": random.choice(character.triggers),
            "emergent_question": lens["question"].format(character=character.name),
        }

    def _generate_encounter_title(self, character: DeepCharacter, lens_key: str, number: int) -> str:
        """Generate an alliterative, meaningful encounter title."""
        lens = THINKER_LENSES[lens_key]

        # Title templates that create actual narrative hooks
        templates = [
            f"The {character.character_class}'s {random.choice(['Test', 'Trial', 'Temptation', 'Truth'])}",
            f"Where the {random.choice(['Shadows Speak', 'Walls Remember', 'Silence Judges', 'Light Lies'])}",
            f"The {random.choice(['Price of', 'Weight of', 'Shape of', 'Taste of'])} {random.choice(character.values)}",
            f"What the {random.choice(['Door', 'Mirror', 'Page', 'Bell'])} {random.choice(['Revealed', 'Refused', 'Remembered', 'Forgot'])}",
            f"The {character.name}'s {random.choice(['Descent', 'Reckoning', 'Bargain', 'Return'])}",
        ]
        return random.choice(templates)

    def generate_full_campaign_markdown(
        self,
        goal: str,
        models: list[str] | None = None,
        encounters: int = 5,
    ) -> str:
        """Generate a complete, beautiful campaign as markdown."""
        models = models or ["deepseek-v4", "grok-4", "ollama-local"]
        roles = ["Strategist", "Investigator", "Builder", "Reviewer", "Communicator"][:len(models)]

        # Generate party
        party = self.generate_party(models, roles)

        # Pick story shape
        story_shape = random.choice(list(STORY_SHAPES.keys()))
        shape = STORY_SHAPES[story_shape]

        # Build campaign
        from mag.riddler_campaign import CAMPAIGN_DOMAINS, QUEST_PREFIXES
        domain = random.choice(list(CAMPAIGN_DOMAINS.keys()))
        domain_config = CAMPAIGN_DOMAINS[domain]

        quest_name = f"{random.choice(QUEST_PREFIXES)} the {random.choice([c.name for c in party])}"

        lines = []
        lines.append(f"# {quest_name}")
        lines.append(f"*A {story_shape.replace('_', ' ').title()} in {domain_config['setting']}*")
        lines.append("")
        lines.append(f"## The Shape of This Story")
        lines.append(f"**{shape['arc']}**")
        lines.append(f"{shape['act1']}")
        lines.append(f"{shape['act2']}")
        lines.append(f"{shape['act3']}")
        lines.append("")
        lines.append("## The World")
        lines.append(f"*{random.choice(SENSORY_TABLES['sound'])}*")
        lines.append("")
        lines.append(f"**The Setting:** {domain_config['setting']}")
        lines.append(f"**The Threat:** {domain_config['villain']}")
        lines.append(f"**The Quest:** {domain_config['quest_item']}")
        lines.append("")
        lines.append("## The Party")
        lines.append("")

        for char in party:
            lines.append(char.to_character_sheet())
            lines.append("\n---\n")

        lines.append("## The Journey")
        lines.append("")

        difficulties = ["Easy", "Medium", "Medium", "Hard", "Deadly"][:encounters]
        for i, (char, diff) in enumerate(zip(party * ((encounters // len(party)) + 1), difficulties)):
            enc = self.generate_encounter(i + 1, story_shape, char, diff)
            lines.append(f"### {enc['difficulty']} — {enc['title']}")
            lines.append(f"*Focus: {enc['character_focus']}*")
            lines.append("")
            lines.append(enc['narrative'])
            lines.append("")
            lines.append(f"*What haunts this room: {enc['emergent_question']}*")
            lines.append("")

        lines.append("---")
        lines.append(f"*Generated by the Narrative Engine. Dwarf Fortress depth. Thinker lens clarity. Emergent fun.*")

        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════
# RESEARCH BRANCH — feed to frontier scout
# ═══════════════════════════════════════════════════════════════════

GAME_THEFT_FINDINGS = [
    {
        "name": "Dwarf Fortress Procedural Personality",
        "category": "technique",
        "source": "Bay 12 Games — Dwarf Fortress",
        "description": "Every entity gets procedural personality facets (0-100), likes, dislikes, values, dreams, relationships, and a mood system. The fun emerges from systemic interaction of traits with world state. Losing is fun because the story of HOW you lost is better than winning.",
        "benefit": 9,
        "adapt_cost": 3,
        "ignore_risk": 5,
        "adopt_risk": 1,
        "what_to_steal": "Personality facet system, mood mechanics, relationship web, procedural backstory generation. Applied to AI characters to create behavioral depth that interacts with campaign state.",
    },
    {
        "name": "RimWorld Storyteller AI",
        "category": "technique",
        "source": "Ludeon Studios — RimWorld",
        "description": "Three storyteller AIs (Cassandra/escalating, Phoebe/long calm then crisis, Randy/pure chaos) modulate event frequency and intensity. The storyteller is not a script — it's a pacing algorithm that creates dramatic rhythm.",
        "benefit": 8,
        "adapt_cost": 2,
        "ignore_risk": 4,
        "adopt_risk": 1,
        "what_to_steal": "Storyteller pacing system — modulate encounter difficulty and frequency based on a selected dramatic rhythm. Cassandra for training, Randy for creative exploration.",
    },
    {
        "name": "Disco Elysium Skill Voices",
        "category": "technique",
        "source": "ZA/UM — Disco Elysium",
        "description": "Skills are not abilities — they're voices in the character's head that argue, contradict, and reveal. Encyclopedia won't shut up about trivia. Inland Empire sees the supernatural in everything. The skills ARE the internal monologue.",
        "benefit": 9,
        "adapt_cost": 5,
        "ignore_risk": 6,
        "adopt_risk": 3,
        "what_to_steal": "Internal skill voices as model steering vectors. Each model's 'skills' argue in its context window. The Wizard's Arcana skill sees patterns everywhere. The Paladin's Insight tastes deception. The voices DISAGREE — that's where emergence lives.",
    },
    {
        "name": "Donjon Procedural Generation",
        "category": "tool",
        "source": "donjon.bin.sh — D&D procedural tools",
        "description": "Algorithmic generation of dungeons, NPCs, treasures, names, worlds. The algorithms encode D&D design patterns as combinatorial systems. Every output is unique but structurally sound.",
        "benefit": 7,
        "adapt_cost": 2,
        "ignore_risk": 3,
        "adopt_risk": 1,
        "what_to_steal": "Random tables for sensory detail, dungeon features, NPC agendas, names. Donjon proves that good procedural generation is about constraint design, not randomness.",
    },
    {
        "name": "Darkest Dungeon Stress & Narrator",
        "category": "technique",
        "source": "Red Hook Studios — Darkest Dungeon",
        "description": "Characters accumulate stress that triggers afflictions (paranoid, selfish, fearful, etc.) or virtues (courageous, focused, powerful). The Ancestor narrates every moment with grim, poetic commentary. The narrator voice IS the game's identity.",
        "benefit": 8,
        "adapt_cost": 4,
        "ignore_risk": 5,
        "adopt_risk": 2,
        "what_to_steal": "Stress/affliction system for AI characters — prolonged difficult tasks trigger behavioral changes. The Bard narrator voice as campaign atmosphere. 'Ruin has come to our family...'",
    },
    {
        "name": "TinyStories Narrative Atoms",
        "category": "technique",
        "source": "Microsoft Research — TinyStories dataset",
        "description": "Minimal story units (3-5 sentences) that are complete, coherent narratives. Proves that stories don't need length — they need a turn. The smallest unit of story is: expectation -> subversion -> resolution.",
        "benefit": 6,
        "adapt_cost": 1,
        "ignore_risk": 2,
        "adopt_risk": 1,
        "what_to_steal": "Tiny story atoms as narrative seeds. Each encounter can be seeded with a tiny story that the model expands. The atom provides the turn; the model provides the detail.",
    },
]

# ═══════════════════════════════════════════════════════════════════
# QUICK ACCESS
# ═══════════════════════════════════════════════════════════════════

_ENGINE: Optional[NarrativeEngine] = None


def get_engine() -> NarrativeEngine:
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = NarrativeEngine()
    return _ENGINE


def generate_campaign(goal: str, *, models: list[str] | None = None, encounters: int = 5) -> str:
    """Generate a deep, fun campaign as markdown."""
    return get_engine().generate_full_campaign_markdown(goal, models=models, encounters=encounters)


def generate_character(model: str, role: str = "Strategist") -> DeepCharacter:
    """Generate one deep character."""
    return DeepCharacter.generate(model, role)


def seed_scout_findings():
    """Seed game theft findings into the frontier scout."""
    try:
        from mag.frontier_scout import get_scout
        scout = get_scout()
        # Append game theft findings
        findings_path = ROOT / "memory" / "frontier" / "scout_findings.jsonl"
        existing_ids = set()
        if findings_path.is_file():
            for line in findings_path.read_text(encoding="utf-8").strip().splitlines():
                if line.strip():
                    try:
                        existing_ids.add(json.loads(line).get("id", ""))
                    except json.JSONDecodeError:
                        pass

        written = 0
        with open(findings_path, "a", encoding="utf-8") as f:
            for i, finding in enumerate(GAME_THEFT_FINDINGS):
                fid = f"f-game-{i+1:03d}"
                if fid not in existing_ids:
                    entry = {
                        "schema": "frontier_scout.v1",
                        "id": fid,
                        "category": finding["category"],
                        "name": finding["name"],
                        "source": finding["source"],
                        "description": finding["description"],
                        "benefit": finding["benefit"],
                        "adapt_cost": finding["adapt_cost"],
                        "ignore_risk": finding["ignore_risk"],
                        "adopt_risk": finding["adopt_risk"],
                        "verdict": "STEAL_NOW" if finding["benefit"] >= 7 and finding["adapt_cost"] <= 4 else "WATCH",
                        "adaptation_plan": finding["what_to_steal"],
                        "ts": _now(),
                    }
                    f.write(json.dumps(entry, default=str) + "\n")
                    written += 1
        return {"ok": True, "seeded": written}
    except Exception as e:
        return {"ok": False, "error": str(e)}
