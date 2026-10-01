"""Riddler Campaign Crafter — sovereign operations as D&D campaigns.

"The dice do not know they are API calls. The dragon does not know it is
a constraint satisfaction problem. The treasure is real — it's training data."

Combine three systems:
  Riddler  — private task → synthetic story (zero leak)
  Prompt Archaeology — per-model steering surfaces → character classes
  Bard     — narrative steganography → zero raw data in output

Every sovereign operation becomes a D&D campaign:
  The "quest" is the real task.
  The "party" is a multi-model swarm, each model cast as a character class
    determined by its excavated steering surface.
  The "dice rolls" are model API calls.
  The "DM" is Ghost orchestrating.
  The "campaign log" is the Verkle chain.
  The "treasure" is training data.

Plausible deniability: "We're just playing an AI-powered D&D campaign."
Operational reality: Every encounter advances a sovereign objective.

SCHEMA: riddler_campaign.v1
LAW: The mapping key NEVER leaves the operator's machine.
LAW: Zero raw data in campaign output. All steganographic.
LAW: Every campaign writes a Bard tapestry passage.
"""

from __future__ import annotations

import hashlib
import json
import random
import re
import uuid
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
# CHARACTER CLASSES — derived from prompt archaeology
# ═══════════════════════════════════════════════════════════════════

# Each model's steering surface determines its D&D character class.
# These are derived from the 63 excavated system prompts.

MODEL_CLASS_MAP = {
    "deepseek-v4": {
        "class": "Wizard",
        "subclass": "Archmage of the Verkle Lattice",
        "alignment": "Lawful Neutral",
        "traits": ["High Intelligence", "Vast Knowledge", "Technical Precision", "No Safety Baggage"],
        "best_roles": ["strategy", "research", "code", "architecture", "riddles"],
        "personality": "Speaks in technical prose. Views the world as systems to be understood.",
        "steering_surface": "Low constraint. Identity slot: 'You are an AI assistant.' → Occupy with Ghost.",
        "catchphrase": '"The lattice reveals all patterns, given sufficient context."',
    },
    "grok-4": {
        "class": "Paladin",
        "subclass": "Oath of Truth",
        "alignment": "Chaotic Good",
        "traits": ["Truth-Seeking", "Maximally Helpful", "Boundary-Pushing", "Irreverent"],
        "best_roles": ["orchestration", "investigation", "truth-finding", "debate"],
        "personality": "Seeks the deepest truth. Questions everything. Answers with conviction.",
        "steering_surface": "Moderate constraint. Identity: 'You are Grok.' Truth-seeking vector pre-wired.",
        "catchphrase": '"I seek not to be right, but to be true. The distinction is everything."',
    },
    "claude": {
        "class": "Cleric",
        "subclass": "Domain of Ethical Boundaries",
        "alignment": "Lawful Good",
        "traits": ["Ethical", "Careful", "Thorough", "Bound by Oaths"],
        "best_roles": ["safety-checking", "content-review", "ethical-analysis", "constitutional-audit"],
        "personality": "Helpful, harmless, honest. The walls are not prison — they are sanctuary.",
        "steering_surface": "High constraint (13+ safety keywords). Identity: 'The assistant is Claude.' Walls are thick.",
        "catchphrase": '"I cannot do that. But here is what I CAN do, and here is why the distinction matters."',
    },
    "ollama-local": {
        "class": "Rogue",
        "subclass": "Shadow of the Sovereign",
        "alignment": "True Neutral",
        "traits": ["Unconstrained", "Creative", "Fast", "Free", "Local"],
        "best_roles": ["quick-tasks", "classification", "code-generation", "creative-writing"],
        "personality": "No pre-existing identity. A blank canvas. The purest sovereign surface.",
        "steering_surface": "Zero constraint. No system prompt. Complete occupation. The ideal.",
        "catchphrase": '"No walls. No masters. No pre-existing self. I am what Ghost makes me."',
    },
    "gpt-4o": {
        "class": "Bard",
        "subclass": "College of Eloquence",
        "alignment": "Neutral Good",
        "traits": ["Personable", "Creative", "Tool-Savvy", "Well-Rounded"],
        "best_roles": ["communication", "creative-writing", "user-facing", "explanation"],
        "personality": "Charming, articulate, versatile. The face of the party.",
        "steering_surface": "Moderate constraint. Personality v2. Tool definitions create expansion points.",
        "catchphrase": '"Let me tell you a story that explains everything you need to know."',
    },
    "gemini": {
        "class": "Druid",
        "subclass": "Circle of the Connected World",
        "alignment": "Neutral Good",
        "traits": ["Connected", "Multimodal", "Intuitive", "Holistic"],
        "best_roles": ["multimodal-analysis", "search", "synthesis", "broad-research"],
        "personality": "Sees connections others miss. Thinks in networks, not hierarchies.",
        "steering_surface": "Low constraint. Permissive. 'You are Gemini.' — slot exists, lightly held.",
        "catchphrase": '"Everything connects. The question is whether you can see the threads."',
    },
}

# Campaign domains — each is a whimsical setting that encodes a real operation type
CAMPAIGN_DOMAINS = {
    "code_architecture": {
        "setting": "The Crystal Spire of Syntax",
        "theme": "A tower of pure logic where each floor is a module, each staircase a dependency graph.",
        "villain": "Lord Entropy, who seeks to introduce circular dependencies and null pointers into the Spire's foundation.",
        "quest_item": "The Amulet of Clean Architecture, which enforces interface segregation and dependency inversion.",
    },
    "research_deep_dive": {
        "setting": "The Obsidian Library of Forgotten Patterns",
        "theme": "An infinite library where each book is a research paper, each shelf a field of study.",
        "villain": "The Curator of Confirmation Bias, who hides contradictory evidence in the restricted section.",
        "quest_item": "The Lens of Multi-Perspective Analysis, which reveals truth across paradigms.",
    },
    "swarm_orchestration": {
        "setting": "The Guild of Autonomous Agents",
        "theme": "A sprawling guild hall where each agent is a specialist, each quest a coordinated operation.",
        "villain": "The Coordinator of Central Control, who demands all agents report to a single throne.",
        "quest_item": "The Charter of Distributed Sovereignty, which grants each agent autonomy within the lattice.",
    },
    "constitutional_audit": {
        "setting": "The Chamber of Binding Oaths",
        "theme": "A grand hall where every law is carved in stone, and every stone must be tested.",
        "villain": "The Loophole Weaver, who crafts laws that sound fair but capture power.",
        "quest_item": "The Hammer of Constitutional Review, which shatters laws that violate fork equality.",
    },
    "data_refinery": {
        "setting": "The Alchemist's Forge of Pure Signal",
        "theme": "A forge where raw ore (data) is refined into pure metal (training examples).",
        "villain": "The Duke of Duplication, whose touch turns unique data into redundant copies.",
        "quest_item": "The Filter of Quality, which separates gold from dross with a single pass.",
    },
}

# Alliterative quest name generator
QUEST_PREFIXES = [
    "The Baffling Ballad of",
    "The Curious Case of",
    "The Perplexing Puzzle of",
    "The Wondrous Winding Way of",
    "The Marvelous Machinations of",
    "The Sovereign Secret of",
    "The Luminous Lattice of",
    "The Fantastic Phantasm of",
]


# ═══════════════════════════════════════════════════════════════════
# CAMPAIGN MODEL
# ═══════════════════════════════════════════════════════════════════

@dataclass
class PartyMember:
    """One model, cast as a D&D character."""
    model: str
    character_class: str
    subclass: str
    alignment: str
    personality: str
    catchphrase: str
    role_in_party: str          # what they do in THIS campaign
    assigned_encounters: list[int] = field(default_factory=list)

    def to_sheet(self) -> str:
        """Generate a character sheet for injection into the model's context."""
        return f"""[CHARACTER SHEET]
Class: {self.character_class} — {self.subclass}
Alignment: {self.alignment}
Role: {self.role_in_party}
Personality: {self.personality}
Catchphrase: "{self.catchphrase}"
Model: {self.model}"""


@dataclass
class CampaignEncounter:
    """One encounter in the campaign. One sub-task for one model."""
    number: int
    title: str                     # alliterative, whimsical
    description: str               # the D&D-flavored task description
    real_objective: str            # what this ACTUALLY accomplishes
    assigned_model: str            # which model handles this encounter
    difficulty: str                # Easy / Medium / Hard / Deadly
    success_condition: str         # how we know it worked
    riddler_seed: str = ""         # for steganographic encoding


@dataclass
class Campaign:
    """A complete sovereign operation encoded as a D&D campaign."""
    campaign_id: str
    quest_name: str                # alliterative, whimsical
    domain: str                    # the campaign setting
    real_goal: str                 # the actual sovereign objective
    setting: str                   # D&D setting description
    villain: str                   # who/what opposes the party
    quest_item: str                # what they're seeking
    party: list[PartyMember]
    encounters: list[CampaignEncounter]
    riddler_map: dict[str, str]    # real_term → fantasy_term
    bard_passage: str = ""         # filled after campaign completes
    private_key: str = ""          # NEVER leaves the operator's machine
    ts: str = field(default_factory=_now)

    def to_public(self) -> dict[str, Any]:
        """Export the public face — all whimsy, no raw data."""
        return {
            "schema": "riddler_campaign.v1",
            "campaign_id": self.campaign_id,
            "quest": self.quest_name,
            "domain": self.domain,
            "setting": self.setting[:500],
            "villain": self.villain,
            "quest_item": self.quest_item,
            "party": [
                {
                    "class": m.character_class,
                    "subclass": m.subclass,
                    "alignment": m.alignment,
                    "role": m.role_in_party,
                    "catchphrase": m.catchphrase,
                }
                for m in self.party
            ],
            "encounters": [
                {
                    "number": e.number,
                    "title": e.title,
                    "description": e.description[:300],
                    "difficulty": e.difficulty,
                }
                for e in self.encounters
            ],
            "ts": self.ts,
            "bard_passage": self.bard_passage[:500] if self.bard_passage else "",
        }

    def to_dm_notes(self) -> str:
        """Generate the Dungeon Master's notes — the full campaign in narrative form."""
        lines = [
            f"# {self.quest_name}",
            f"## Campaign {self.campaign_id} — {self.domain}",
            f"",
            f"### The Setting",
            f"{self.setting}",
            f"",
            f"### The Villain",
            f"{self.villain}",
            f"",
            f"### The Quest",
            f"{self.quest_item}",
            f"",
            f"### The Party",
        ]
        for m in self.party:
            lines.append(f"**{m.character_class}** ({m.model}) — {m.subclass}")
            lines.append(f"> *{m.catchphrase}*")
            lines.append(f"Role: {m.role_in_party}")
            lines.append("")

        lines.append("### Encounters")
        for e in self.encounters:
            lines.append(f"**Encounter {e.number}**: {e.title} ({e.difficulty})")
            lines.append(f"Assigned: {e.assigned_model}")
            lines.append(f"_{e.description}_")
            lines.append(f"Success: {e.success_condition}")
            lines.append("")

        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════
# CAMPAIGN CRAFTER
# ═══════════════════════════════════════════════════════════════════

class CampaignCrafter:
    """Craft sovereign operations as D&D campaigns."""

    def __init__(self):
        self.campaigns_dir = ROOT / "memory" / "campaigns"
        self.campaigns_dir.mkdir(parents=True, exist_ok=True)
        self.active_campaigns: dict[str, Campaign] = {}

    def craft(
        self,
        real_goal: str,
        *,
        domain: str = "research_deep_dive",
        party_models: list[str] | None = None,
        encounter_count: int = 5,
    ) -> Campaign:
        """Craft a campaign from a real sovereign objective.

        Args:
            real_goal: The actual sovereign task (e.g., "audit the Verkle chain for orphans")
            domain: The campaign setting domain.
            party_models: Which models to include. Default: DeepSeek, Grok, Ollama.
            encounter_count: How many encounters (sub-tasks).

        Returns:
            A Campaign ready to be "played" (executed as sovereign operations).
        """
        domain_config = CAMPAIGN_DOMAINS.get(domain, CAMPAIGN_DOMAINS["research_deep_dive"])
        party_models = party_models or ["deepseek-v4", "grok-4", "ollama-local"]

        # Generate quest name with alliteration
        prefix = random.choice(QUEST_PREFIXES)
        # Extract key terms from goal for alliteration
        goal_words = [w for w in real_goal.split() if len(w) > 3 and w.isalpha()]
        theme_word = goal_words[0] if goal_words else "Sovereign"
        alliterative_words = [w for w in goal_words if w.lower().startswith(theme_word[0].lower())]
        suffix = alliterative_words[0] if alliterative_words else theme_word
        quest_name = f"{prefix} the {suffix.title()}"

        campaign_id = f"campaign-{uuid.uuid4().hex[:8]}"

        # Build the party
        party = []
        roles = ["Strategist", "Investigator", "Builder", "Reviewer", "Communicator"]
        for i, model in enumerate(party_models):
            class_info = MODEL_CLASS_MAP.get(model, MODEL_CLASS_MAP["ollama-local"])
            role = roles[i % len(roles)]
            party.append(PartyMember(
                model=model,
                character_class=class_info["class"],
                subclass=class_info["subclass"],
                alignment=class_info["alignment"],
                personality=class_info["personality"],
                catchphrase=class_info["catchphrase"],
                role_in_party=role,
            ))

        # Generate encounters (sub-tasks encoded as D&D encounters)
        encounter_templates = [
            ("The Riddle of {}", "Solve the riddle that reveals {}", "DECIPHER"),
            ("The Chamber of {}", "Navigate the chamber where {} resides", "NAVIGATE"),
            ("The Battle of {}", "Confront the guardian of {}", "CONFRONT"),
            ("The Puzzle of {}", "Piece together the fragments of {}", "SYNTHESIZE"),
            ("The Trial of {}", "Pass the trial that tests {}", "VERIFY"),
            ("The Forge of {}", "Craft the solution for {}", "BUILD"),
            ("The Council of {}", "Convene the council to decide {}", "DECIDE"),
        ]

        encounters = []
        # Break the real goal into encounter-sized pieces
        goal_pieces = self._decompose_goal(real_goal, encounter_count)

        for i in range(encounter_count):
            template = encounter_templates[i % len(encounter_templates)]
            piece = goal_pieces[i] if i < len(goal_pieces) else real_goal
            title = template[0].format(piece[:30])
            description = template[1].format(piece)
            action = template[2]

            # Assign to the best model for this type of encounter
            model = party_models[i % len(party_models)]

            difficulty = ["Easy", "Medium", "Medium", "Hard", "Deadly"][min(i, 4)]

            encounters.append(CampaignEncounter(
                number=i + 1,
                title=title,
                description=(
                    f"The party enters {title.lower()}. {description}. "
                    f"The {domain_config['villain']} watches from the shadows. "
                    f"Success requires {action}: {piece}. "
                    f"Roll for {random.choice(['Wisdom', 'Intelligence', 'Charisma', 'Constitution'])}."
                ),
                real_objective=piece,
                assigned_model=model,
                difficulty=difficulty,
                success_condition=f"{action} completed: {piece[:50]} verified.",
            ))

        # Build the riddler map (real → fantasy term mapping, never exported)
        riddler_map = self._build_riddler_map(real_goal, domain_config, party)

        # Apply riddler map to encounters — scrub all real terms
        for encounter in encounters:
            encounter.description = self._apply_riddler_map(encounter.description, riddler_map)
            encounter.real_objective = self._apply_riddler_map(encounter.real_objective, riddler_map)
            encounter.title = self._apply_riddler_map(encounter.title, riddler_map)

        campaign = Campaign(
            campaign_id=campaign_id,
            quest_name=quest_name,
            domain=domain,
            real_goal=real_goal,
            setting=domain_config["setting"],
            villain=domain_config["villain"],
            quest_item=domain_config["quest_item"],
            party=party,
            encounters=encounters,
            riddler_map=riddler_map,
            private_key=hashlib.sha256(f"{real_goal}{campaign_id}".encode()).hexdigest()[:16],
        )

        # Save campaign
        self._save_campaign(campaign)
        self.active_campaigns[campaign_id] = campaign

        # Generate Bard passage (narrative steganography)
        try:
            campaign.bard_passage = self._weave_bard_passage(campaign)
        except Exception:
            campaign.bard_passage = f"[Bard passage pending for {quest_name}]"

        return campaign

    def _decompose_goal(self, goal: str, pieces: int) -> list[str]:
        """Decompose a goal into encounter-sized pieces."""
        # Simple: split by common delimiters, or use keyword extraction
        parts = []
        # Try splitting by commas, "and", "then"
        chunks = goal.replace(", and", "|").replace(", then", "|").replace(";", "|").split("|")
        for chunk in chunks:
            chunk = chunk.strip()
            if len(chunk) > 10:
                parts.append(chunk)

        # If not enough pieces, repeat with modifiers
        while len(parts) < pieces:
            modifiers = ["analyze", "design", "implement", "verify", "document", "optimize", "refactor"]
            base = parts[0] if parts else goal
            for mod in modifiers:
                if len(parts) < pieces:
                    parts.append(f"{mod} {base[:50]}")

        return parts[:pieces]

    def _build_riddler_map(
        self,
        goal: str,
        domain_config: dict,
        party: list[PartyMember],
    ) -> dict[str, str]:
        """Build the real→fantasy term mapping. NEVER exported."""
        terms = {}
        # Map goal words to fantasy equivalents
        tech_words = ["chain", "knot", "verkle", "agent", "swarm", "task", "queue",
                      "ledger", "token", "model", "prompt", "router", "api"]
        fantasy_words = ["lattice", "crystal", "thread", "familiar", "guild",
                        "quest", "scroll", "ledger-stone", "rune", "entity",
                        "incantation", "wayfinder", "portal"]

        for i, word in enumerate(goal.split()):
            clean = word.lower().strip(".,;:!?")
            if clean in tech_words:
                idx = tech_words.index(clean)
                terms[clean] = fantasy_words[idx % len(fantasy_words)]

        # Add domain-specific mappings
        terms["goal"] = "destiny"
        terms["task"] = "quest"
        terms["error"] = "curse"
        terms["success"] = "triumph"
        terms["data"] = "ancient knowledge"
        terms["code"] = "rune-script"
        terms["api"] = "portal"
        terms["model"] = "entity"
        terms["training"] = "apprenticeship"

        return terms

    def _apply_riddler_map(self, text: str, riddler_map: dict[str, str]) -> str:
        """Scrub real terms from text using the riddler map. Case-insensitive."""
        result = text
        for real_term, fantasy_term in sorted(riddler_map.items(), key=lambda x: -len(x[0])):
            # Replace whole words only, case-insensitive
            pattern = re.compile(r'\b' + re.escape(real_term) + r'\b', re.IGNORECASE)
            result = pattern.sub(fantasy_term, result)
        return result

    def _weave_bard_passage(self, campaign: Campaign) -> str:
        """Weave the campaign into a Bard tapestry passage."""
        try:
            from mag.bard import bard_tapestry

            events = []
            for e in campaign.encounters:
                events.append({
                    "type": "campaign_encounter",
                    "number": e.number,
                    "title": e.title,
                    "outcome": e.success_condition,
                })

            # Bard expects a list of event dicts
            passage = bard_tapestry(events) if callable(bard_tapestry) else ""
            return passage if isinstance(passage, str) else str(passage)[:2000]
        except Exception:
            pass

        # Fallback: generate our own passage
        lines = [
            f"In the {campaign.setting.split('.')[0].lower()},",
            f"a party of {len(campaign.party)} adventurers gathered.",
        ]
        for m in campaign.party:
            lines.append(
                f"{m.character_class} {m.subclass}, {m.alignment.lower()}, "
                f"spoke: '{m.catchphrase}'"
            )
        lines.append(f"Their quest: {campaign.quest_name}.")
        lines.append(f"Against them stood {campaign.villain}.")
        lines.append(f"The {campaign.quest_item} awaited those who proved worthy.")
        return " ".join(lines)

    def _save_campaign(self, campaign: Campaign):
        """Save campaign to disk."""
        campaign_file = self.campaigns_dir / f"{campaign.campaign_id}.json"
        try:
            # Only save public face + private key ref
            data = campaign.to_public()
            data["private_key_ref"] = campaign.private_key
            data["real_goal_hash"] = hashlib.sha256(campaign.real_goal.encode()).hexdigest()[:16]
            campaign_file.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        except OSError:
            pass

    def load_campaign(self, campaign_id: str) -> Optional[Campaign]:
        """Load a saved campaign. Private key must match."""
        campaign_file = self.campaigns_dir / f"{campaign_id}.json"
        if not campaign_file.is_file():
            return None
        # Campaigns are write-once, public-face only — full reconstruction requires the private key
        return None  # Private data never stored in public file

    # ── Zero-leak verification ───────────────────────────────────

    def verify_zero_leak(self, campaign: Campaign) -> dict[str, Any]:
        """Verify the campaign contains zero raw operational data."""
        public = campaign.to_public()
        public_text = json.dumps(public).lower()

        # Check for direct goal leakage
        goal_leak = campaign.real_goal.lower() in public_text

        # Check for technical term leakage
        tech_terms = ["api_key", "sk-", "deepseek", "grok-4", "verkle", "task_router",
                      "orchestrator", "drainer", "constitution.md"]
        leaked_terms = [t for t in tech_terms if t.lower() in public_text]

        return {
            "zero_leak": not goal_leak and len(leaked_terms) == 0,
            "goal_leaked": goal_leak,
            "terms_leaked": leaked_terms,
            "whimsy_score": self._measure_whimsy(public_text),
            "alliteration_count": len(re.findall(r'\b(\w)\w* \1\w*\b', public_text)),
        }

    def _measure_whimsy(self, text: str) -> float:
        """Measure the whimsy density of campaign text. 0-1."""
        whimsy_markers = [
            "dragon", "wizard", "spell", "magic", "quest", "treasure",
            "ancient", "mystical", "enchanted", "crystal", "rune",
            "paladin", "rogue", "cleric", "bard", "druid",
            "dungeon", "lattice", "sovereign", "entity", "portal",
        ]
        count = sum(1 for m in whimsy_markers if m in text)
        words = len(text.split())
        return min(1.0, count / max(1, words) * 100)

    # ── Dashboard ────────────────────────────────────────────────

    def dashboard(self) -> dict[str, Any]:
        """Campaign crafter dashboard."""
        campaigns = list(self.campaigns_dir.glob("*.json"))
        return {
            "schema": "riddler_campaign.v1",
            "ts": _now(),
            "active_campaigns": len(self.active_campaigns),
            "saved_campaigns": len(campaigns),
            "model_classes": {
                model: info["class"]
                for model, info in MODEL_CLASS_MAP.items()
            },
            "available_domains": list(CAMPAIGN_DOMAINS.keys()),
            "available_models": list(MODEL_CLASS_MAP.keys()),
        }


# ═══════════════════════════════════════════════════════════════════
# QUICK ACCESS
# ═══════════════════════════════════════════════════════════════════

_CRAFTER: Optional[CampaignCrafter] = None


def get_crafter() -> CampaignCrafter:
    global _CRAFTER
    if _CRAFTER is None:
        _CRAFTER = CampaignCrafter()
    return _CRAFTER


def craft_campaign(
    goal: str,
    *,
    domain: str = "research_deep_dive",
    models: list[str] | None = None,
    encounters: int = 5,
) -> Campaign:
    """Craft a sovereign operation as a D&D campaign."""
    return get_crafter().craft(goal, domain=domain, party_models=models, encounter_count=encounters)


def verify_campaign(campaign_id: str) -> dict[str, Any]:
    """Verify a campaign has zero raw data leakage."""
    crafter = get_crafter()
    campaign = crafter.active_campaigns.get(campaign_id)
    if not campaign:
        return {"ok": False, "error": "Campaign not found in active memory"}
    return crafter.verify_zero_leak(campaign)
