"""worldgen — Python port of roblox/src/shared/Worldgen.luau (ages, the 130
spheres, forgotten beasts) + roblox/src/server/ZoneGate.luau (portal gating
by per-soul sphere vs region alliance).

DF world-history laws mined from the wiki (LINKS-341/342/343), driving THE
MOUNTAIN's world state — now the estate's CAMPAIGN layer zone progression:
water_graph (mag/water_graph.py) is the physics, worldgen is the geography.
A campaign zone joins one generator region; a soul carries one sphere drawn
deterministically from its UserId; the gate resolves the pair.

Laws ported 1:1 from the Luau:
  - AGES: worlds start in the Age of Myth; megabeast (boss) deaths move the
    age every KILLS_PER_AGE kills; the three ages recur with ordinals
    ("The Second Age of Legends" style, capped at "Seventh").
  - SPHERES: 130 cosmic principles; the per-soul draw is
    SeedRng(UserId * 7919).int(1, 130) — deterministic per player, no UI,
    no store, re-derivable (ZoneGate.ensureSphere).
  - KINSHIP: alignment classes (good/evil) + co-occurrence, generated on
    the Luau side from corpus/df_mine/df_spheres.json (shared/
    SphereKinship.luau) — mirrored here verbatim. Opposition outranks
    kinship (law 4 precedence).
  - GATE: alliance over the region's whole sphere row — any opposed sphere
    decides "opposed" (locked), else any allied sphere decides "allied"
    (open + one VirtueMark per BUFF_SECONDS per zone), else "independent"
    (open, no effect — a negative is a fact). Unjoined zones carry no gate.

Luau -> Python mapping:
  - SeedRng: bit-exact xorshift32 mirror of roblox/src/shared/SeedRng.luau
    (same fleet shape as the section_stream test mirror; Python's big ints
    make the bit32 wraparound explicit via masks, division by 2**32 is
    exact in both languages' doubles, so the same seed integer draws the
    same stream on both sides).
  - Roblox Player -> :class:`Soul` (user_id + attributes dict); player
    attributes become dict keys ("Sphere", "VirtueMarks", Gate_<zone>).
  - ShadowLedger.record -> an append-only list on the gate (place, message,
    positive); the campaign layer can swap in its own recorder.
  - Players.PlayerAdded -> pull-based :meth:`ZoneGate.attach` called by
    :meth:`ZoneGate.init` for the souls it is handed (no event loop here).
  - region_spheres is constructor-injectable, defaulting to the sourced
    REGION_SPHERES mirror — the exact seam the Luau header names ("if the
    mine ever grows an aligned region row, this is the seam that grows the
    lock"): every sourced region row is unaligned spheres, so "opposed" is
    unreachable through the sourced table, and the lock branch is only
    exercisable through this seam. Not fallback creep: the branch is
    implemented, exactly as in the Luau portalGate.
  - gateAttr: Lua "%W" is [^a-zA-Z0-9] (underscore NOT in %w), Python
    "\\W" keeps underscore — outputs identical because Lua maps "_" to
    itself; alphanumerics survive, everything else becomes "_".

Determinism: the module draws no randomness of its own — every rng is a
SeedRng handed in or seeded from a UserId; ages are integer kill counts.
$0, stdlib.

Port receipt: watch/inbox/last_mile_20260930/W5_WORLDGEN.md (Y1's second
port, after section_stream).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Tuple

__all__ = [
    "AGES",
    "ALIGNMENT",
    "ALLIES",
    "OPPOSED",
    "REGION_SPHERES",
    "SPHERES",
    "DWARVEN",
    "Beast",
    "SeedRng",
    "Soul",
    "Word",
    "Worldgen",
    "ZoneGate",
    "gate_attr",
    "WORLDGEN",
]


# ---------------------------------------------------------------------------
# SeedRng — xorshift32, replay-safe: same seed, same mountain, bit-exact rerun.
# Mirror of roblox/src/shared/SeedRng.luau (mulberry32 needs 32-bit multiply
# wraparound, which doubles lose above 2^53; xorshift32 uses only xor/shift
# so it is exact in both languages).
# ---------------------------------------------------------------------------
class SeedRng:
    def __init__(self, seed: int) -> None:
        self.seed = seed % 2147483647
        if self.seed == 0:
            self.seed = 1  # xorshift32 must not start at zero

    def next(self) -> float:
        s = self.seed
        s = (s ^ ((s << 13) & 0xFFFFFFFF)) & 0xFFFFFFFF
        s ^= s >> 17
        s = (s ^ ((s << 5) & 0xFFFFFFFF)) & 0xFFFFFFFF
        self.seed = s
        return s / 4294967296

    def int(self, lo: int, hi: int) -> int:
        n = self.next()
        return lo + int(n * (hi - lo + 1))  # floor: n >= 0 always

    def pick(self, options: Sequence[str]) -> str:
        return options[self.int(1, len(options)) - 1]


# ---------------------------------------------------------------------------
# GENERATED MIRROR of the fleet's generated Luau artifacts — do not hand-edit.
# Source of truth + regenerate pointers:
#   SPHERES        tools/gen_worldgen_spheres.py  -> shared/Worldgen.luau
#   ALIGNMENT/ALLIES/OPPOSED  tools/gen_df_luau_data.py -> shared/SphereKinship.luau
#   REGION_SPHERES tools/gen_df_luau_data.py      -> shared/RegionSpheres.luau
#   DWARVEN        tools/gen_artifact_lore.py     -> shared/ArtifactLore.luau
# (df_spheres.json / df_lexicon_full.json under corpus/df_mine/). Key order
# preserved from the Luau tables.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Word:
    gloss: str
    dw: str
    pos: str


SPHERES: list[str] = [
    "AGRICULTURE", "ANIMALS", "ART", "BALANCE", "BEAUTY", "BIRTH",
    "BLIGHT", "BOUNDARIES", "CAVERNS", "CHAOS", "CHARITY", "CHILDREN",
    "COASTS", "CONSOLATION", "COURAGE", "CRAFTS", "CREATION", "DANCE",
    "DARKNESS", "DAWN", "DAY", "DEATH", "DEFORMITY", "DEPRAVITY",
    "DISCIPLINE", "DISEASE", "DREAMS", "DUSK", "DUTY", "EARTH",
    "FAME", "FAMILY", "FATE", "FERTILITY", "FESTIVALS", "FIRE",
    "FISH", "FISHING", "FOOD", "FORGIVENESS", "FORTRESSES", "FREEDOM",
    "GAMBLING", "GAMES", "GENEROSITY", "HAPPINESS", "HEALING", "HOSPITALITY",
    "HUNTING", "INSPIRATION", "JEALOUSY", "JEWELS", "JUSTICE", "LABOR",
    "LAKES", "LAWS", "LIES", "LIGHT", "LIGHTNING", "LONGEVITY",
    "LOVE", "LOYALTY", "LUCK", "LUST", "MARRIAGE", "MERCY",
    "METALS", "MINERALS", "MISERY", "MIST", "MOON", "MOUNTAINS",
    "MUCK", "MURDER", "MUSIC", "NATURE", "NIGHT", "NIGHTMARES",
    "OATHS", "OCEANS", "ORDER", "PAINTING", "PEACE", "PERSUASION",
    "PLANTS", "POETRY", "PREGNANCY", "RAIN", "RAINBOWS", "REBIRTH",
    "REVELRY", "REVENGE", "RIVERS", "RULERSHIP", "RUMORS", "SACRIFICE",
    "SALT", "SCHOLARSHIP", "SEASONS", "SILENCE", "SKY", "SONG",
    "SPEECH", "STARS", "STORMS", "STRENGTH", "SUICIDE", "SUN",
    "THEFT", "THRALLDOM", "THUNDER", "TORTURE", "TRADE", "TRAVELERS",
    "TREACHERY", "TREES", "TRICKERY", "TRUTH", "TWILIGHT", "VALOR",
    "VICTORY", "VOLCANOS", "WAR", "WATER", "WEALTH", "WEATHER",
    "WIND", "WISDOM", "WRITING", "YOUTH",
]

ALIGNMENT: dict[str, str] = {
    "BLIGHT": "evil",
    "CHAOS": "evil",
    "CHARITY": "good",
    "CONSOLATION": "good",
    "DEATH": "evil",
    "DEFORMITY": "evil",
    "DEPRAVITY": "evil",
    "DISEASE": "evil",
    "FORGIVENESS": "good",
    "FREEDOM": "good",
    "GENEROSITY": "good",
    "HAPPINESS": "good",
    "HEALING": "good",
    "HOSPITALITY": "good",
    "JEALOUSY": "evil",
    "LIES": "evil",
    "LOVE": "good",
    "MERCY": "good",
    "MISERY": "evil",
    "MURDER": "evil",
    "NIGHTMARES": "evil",
    "PEACE": "good",
    "REVELRY": "good",
    "SACRIFICE": "good",
    "SUICIDE": "evil",
    "THEFT": "evil",
    "THRALLDOM": "evil",
    "TORTURE": "evil",
    "TREACHERY": "evil",
    "TRUTH": "good",
    "WISDOM": "good",
}

ALLIES: dict[str, list[str]] = {
    "AGRICULTURE": [],
    "ANIMALS": ["CAVERNS", "FIRE", "FISH", "LAKES", "METALS", "MINERALS", "MOUNTAINS", "MUCK", "NATURE", "OCEANS", "PLANTS", "RIVERS", "TREES", "WATER"],
    "ART": [],
    "BALANCE": [],
    "BEAUTY": [],
    "BIRTH": [],
    "BLIGHT": ["CHAOS", "DEATH", "DEFORMITY", "DEPRAVITY", "DISEASE", "JEALOUSY", "LIES", "MISERY", "MURDER", "NIGHTMARES", "SUICIDE", "THEFT", "THRALLDOM", "TORTURE", "TREACHERY"],
    "BOUNDARIES": [],
    "CAVERNS": ["ANIMALS", "CHAOS", "DARKNESS", "DEFORMITY", "METALS", "MINERALS", "MOUNTAINS", "NATURE", "STRENGTH"],
    "CHAOS": ["BLIGHT", "CAVERNS", "DARKNESS", "DEATH", "DEFORMITY", "DEPRAVITY", "DISEASE", "JEALOUSY", "LIES", "MISERY", "MURDER", "NIGHTMARES", "STRENGTH", "SUICIDE", "THEFT", "THRALLDOM", "TORTURE", "TREACHERY"],
    "CHARITY": ["CONSOLATION", "FORGIVENESS", "FREEDOM", "GENEROSITY", "HAPPINESS", "HEALING", "HOSPITALITY", "LOVE", "MERCY", "PEACE", "REVELRY", "SACRIFICE", "TRUTH", "WISDOM"],
    "CHILDREN": [],
    "COASTS": [],
    "CONSOLATION": ["CHARITY", "FORGIVENESS", "FREEDOM", "GENEROSITY", "HAPPINESS", "HEALING", "HOSPITALITY", "LOVE", "MERCY", "PEACE", "REVELRY", "SACRIFICE", "TRUTH", "WISDOM"],
    "COURAGE": [],
    "CRAFTS": [],
    "CREATION": [],
    "DANCE": [],
    "DARKNESS": ["CAVERNS", "CHAOS", "DEFORMITY", "STRENGTH"],
    "DAWN": [],
    "DAY": [],
    "DEATH": ["BLIGHT", "CHAOS", "DEFORMITY", "DEPRAVITY", "DISEASE", "JEALOUSY", "LIES", "MISERY", "MURDER", "NIGHTMARES", "SUICIDE", "THEFT", "THRALLDOM", "TORTURE", "TREACHERY"],
    "DEFORMITY": ["BLIGHT", "CAVERNS", "CHAOS", "DARKNESS", "DEATH", "DEPRAVITY", "DISEASE", "JEALOUSY", "LIES", "MISERY", "MURDER", "NIGHTMARES", "STRENGTH", "SUICIDE", "THEFT", "THRALLDOM", "TORTURE", "TREACHERY"],
    "DEPRAVITY": ["BLIGHT", "CHAOS", "DEATH", "DEFORMITY", "DISEASE", "JEALOUSY", "LIES", "MISERY", "MURDER", "NIGHTMARES", "SUICIDE", "THEFT", "THRALLDOM", "TORTURE", "TREACHERY"],
    "DISCIPLINE": [],
    "DISEASE": ["BLIGHT", "CHAOS", "DEATH", "DEFORMITY", "DEPRAVITY", "JEALOUSY", "LIES", "MISERY", "MURDER", "NIGHTMARES", "SUICIDE", "THEFT", "THRALLDOM", "TORTURE", "TREACHERY"],
    "DREAMS": [],
    "DUSK": [],
    "DUTY": [],
    "EARTH": [],
    "FAME": [],
    "FAMILY": [],
    "FATE": [],
    "FERTILITY": [],
    "FESTIVALS": [],
    "FIRE": ["ANIMALS", "NATURE", "PLANTS", "WEALTH"],
    "FISH": ["ANIMALS", "LAKES", "NATURE", "OCEANS", "RIVERS", "WATER"],
    "FISHING": [],
    "FOOD": ["STRENGTH"],
    "FORGIVENESS": ["CHARITY", "CONSOLATION", "FREEDOM", "GENEROSITY", "HAPPINESS", "HEALING", "HOSPITALITY", "LOVE", "MERCY", "PEACE", "REVELRY", "SACRIFICE", "TRUTH", "WISDOM"],
    "FORTRESSES": [],
    "FREEDOM": ["CHARITY", "CONSOLATION", "FORGIVENESS", "GENEROSITY", "HAPPINESS", "HEALING", "HOSPITALITY", "LOVE", "MERCY", "PEACE", "REVELRY", "SACRIFICE", "TRUTH", "WISDOM"],
    "GAMBLING": [],
    "GAMES": [],
    "GENEROSITY": ["CHARITY", "CONSOLATION", "FORGIVENESS", "FREEDOM", "HAPPINESS", "HEALING", "HOSPITALITY", "LOVE", "MERCY", "PEACE", "REVELRY", "SACRIFICE", "TRUTH", "WISDOM"],
    "HAPPINESS": ["CHARITY", "CONSOLATION", "FORGIVENESS", "FREEDOM", "GENEROSITY", "HEALING", "HOSPITALITY", "LOVE", "MERCY", "PEACE", "REVELRY", "SACRIFICE", "TRUTH", "WISDOM"],
    "HEALING": ["CHARITY", "CONSOLATION", "FORGIVENESS", "FREEDOM", "GENEROSITY", "HAPPINESS", "HOSPITALITY", "LOVE", "MERCY", "PEACE", "REVELRY", "SACRIFICE", "TRUTH", "WISDOM"],
    "HOSPITALITY": ["CHARITY", "CONSOLATION", "FORGIVENESS", "FREEDOM", "GENEROSITY", "HAPPINESS", "HEALING", "LOVE", "MERCY", "PEACE", "REVELRY", "SACRIFICE", "TRUTH", "WISDOM"],
    "HUNTING": ["SKY", "WIND"],
    "INSPIRATION": [],
    "JEALOUSY": ["BLIGHT", "CHAOS", "DEATH", "DEFORMITY", "DEPRAVITY", "DISEASE", "LIES", "MISERY", "MURDER", "NIGHTMARES", "SUICIDE", "THEFT", "THRALLDOM", "TORTURE", "TREACHERY"],
    "JEWELS": [],
    "JUSTICE": [],
    "LABOR": [],
    "LAKES": ["ANIMALS", "FISH", "NATURE", "RIVERS", "WATER"],
    "LAWS": [],
    "LIES": ["BLIGHT", "CHAOS", "DEATH", "DEFORMITY", "DEPRAVITY", "DISEASE", "JEALOUSY", "MISERY", "MURDER", "NIGHTMARES", "SUICIDE", "THEFT", "THRALLDOM", "TORTURE", "TREACHERY"],
    "LIGHT": ["LIGHTNING", "LONGEVITY", "MINERALS", "STRENGTH", "THUNDER"],
    "LIGHTNING": ["LIGHT", "LONGEVITY", "MINERALS", "STRENGTH", "THUNDER"],
    "LONGEVITY": ["LIGHT", "LIGHTNING", "MINERALS", "STRENGTH", "THUNDER"],
    "LOVE": ["CHARITY", "CONSOLATION", "FORGIVENESS", "FREEDOM", "GENEROSITY", "HAPPINESS", "HEALING", "HOSPITALITY", "MERCY", "PEACE", "REVELRY", "SACRIFICE", "TRUTH", "WISDOM"],
    "LOYALTY": [],
    "LUCK": [],
    "LUST": [],
    "MARRIAGE": [],
    "MERCY": ["CHARITY", "CONSOLATION", "FORGIVENESS", "FREEDOM", "GENEROSITY", "HAPPINESS", "HEALING", "HOSPITALITY", "LOVE", "PEACE", "REVELRY", "SACRIFICE", "TRUTH", "WISDOM"],
    "METALS": ["ANIMALS", "CAVERNS", "MINERALS", "MOUNTAINS", "NATURE", "STRENGTH", "WAR"],
    "MINERALS": ["ANIMALS", "CAVERNS", "LIGHT", "LIGHTNING", "LONGEVITY", "METALS", "MOUNTAINS", "NATURE", "STRENGTH", "THUNDER"],
    "MISERY": ["BLIGHT", "CHAOS", "DEATH", "DEFORMITY", "DEPRAVITY", "DISEASE", "JEALOUSY", "LIES", "MURDER", "NIGHTMARES", "SUICIDE", "THEFT", "THRALLDOM", "TORTURE", "TREACHERY"],
    "MIST": [],
    "MOON": [],
    "MOUNTAINS": ["ANIMALS", "CAVERNS", "METALS", "MINERALS", "NATURE"],
    "MUCK": ["ANIMALS", "NATURE", "PLANTS", "REBIRTH", "STRENGTH", "WATER"],
    "MURDER": ["BLIGHT", "CHAOS", "DEATH", "DEFORMITY", "DEPRAVITY", "DISEASE", "JEALOUSY", "LIES", "MISERY", "NIGHTMARES", "SUICIDE", "THEFT", "THRALLDOM", "TORTURE", "TREACHERY"],
    "MUSIC": [],
    "NATURE": ["ANIMALS", "CAVERNS", "FIRE", "FISH", "LAKES", "METALS", "MINERALS", "MOUNTAINS", "MUCK", "OCEANS", "PLANTS", "RIVERS", "TREES", "WATER"],
    "NIGHT": [],
    "NIGHTMARES": ["BLIGHT", "CHAOS", "DEATH", "DEFORMITY", "DEPRAVITY", "DISEASE", "JEALOUSY", "LIES", "MISERY", "MURDER", "SUICIDE", "THEFT", "THRALLDOM", "TORTURE", "TREACHERY"],
    "OATHS": [],
    "OCEANS": ["ANIMALS", "FISH", "NATURE", "WATER"],
    "ORDER": [],
    "PAINTING": [],
    "PEACE": ["CHARITY", "CONSOLATION", "FORGIVENESS", "FREEDOM", "GENEROSITY", "HAPPINESS", "HEALING", "HOSPITALITY", "LOVE", "MERCY", "REVELRY", "SACRIFICE", "TRUTH", "WISDOM"],
    "PERSUASION": [],
    "PLANTS": ["ANIMALS", "FIRE", "MUCK", "NATURE", "RIVERS", "TREES", "WATER"],
    "POETRY": [],
    "PREGNANCY": [],
    "RAIN": [],
    "RAINBOWS": [],
    "REBIRTH": ["MUCK", "STRENGTH"],
    "REVELRY": ["CHARITY", "CONSOLATION", "FORGIVENESS", "FREEDOM", "GENEROSITY", "HAPPINESS", "HEALING", "HOSPITALITY", "LOVE", "MERCY", "PEACE", "SACRIFICE", "TRUTH", "WISDOM"],
    "REVENGE": [],
    "RIVERS": ["ANIMALS", "FISH", "LAKES", "NATURE", "PLANTS", "TREES", "WATER"],
    "RULERSHIP": [],
    "RUMORS": [],
    "SACRIFICE": ["CHARITY", "CONSOLATION", "FORGIVENESS", "FREEDOM", "GENEROSITY", "HAPPINESS", "HEALING", "HOSPITALITY", "LOVE", "MERCY", "PEACE", "REVELRY", "TRUTH", "WISDOM"],
    "SALT": [],
    "SCHOLARSHIP": [],
    "SEASONS": [],
    "SILENCE": [],
    "SKY": ["HUNTING", "WIND"],
    "SONG": [],
    "SPEECH": ["STRENGTH"],
    "STARS": [],
    "STORMS": [],
    "STRENGTH": ["CAVERNS", "CHAOS", "DARKNESS", "DEFORMITY", "FOOD", "LIGHT", "LIGHTNING", "LONGEVITY", "METALS", "MINERALS", "MUCK", "REBIRTH", "SPEECH", "THUNDER", "WAR"],
    "SUICIDE": ["BLIGHT", "CHAOS", "DEATH", "DEFORMITY", "DEPRAVITY", "DISEASE", "JEALOUSY", "LIES", "MISERY", "MURDER", "NIGHTMARES", "THEFT", "THRALLDOM", "TORTURE", "TREACHERY"],
    "SUN": [],
    "THEFT": ["BLIGHT", "CHAOS", "DEATH", "DEFORMITY", "DEPRAVITY", "DISEASE", "JEALOUSY", "LIES", "MISERY", "MURDER", "NIGHTMARES", "SUICIDE", "THRALLDOM", "TORTURE", "TREACHERY"],
    "THRALLDOM": ["BLIGHT", "CHAOS", "DEATH", "DEFORMITY", "DEPRAVITY", "DISEASE", "JEALOUSY", "LIES", "MISERY", "MURDER", "NIGHTMARES", "SUICIDE", "THEFT", "TORTURE", "TREACHERY"],
    "THUNDER": ["LIGHT", "LIGHTNING", "LONGEVITY", "MINERALS", "STRENGTH"],
    "TORTURE": ["BLIGHT", "CHAOS", "DEATH", "DEFORMITY", "DEPRAVITY", "DISEASE", "JEALOUSY", "LIES", "MISERY", "MURDER", "NIGHTMARES", "SUICIDE", "THEFT", "THRALLDOM", "TREACHERY"],
    "TRADE": [],
    "TRAVELERS": [],
    "TREACHERY": ["BLIGHT", "CHAOS", "DEATH", "DEFORMITY", "DEPRAVITY", "DISEASE", "JEALOUSY", "LIES", "MISERY", "MURDER", "NIGHTMARES", "SUICIDE", "THEFT", "THRALLDOM", "TORTURE"],
    "TREES": ["ANIMALS", "NATURE", "PLANTS", "RIVERS"],
    "TRICKERY": [],
    "TRUTH": ["CHARITY", "CONSOLATION", "FORGIVENESS", "FREEDOM", "GENEROSITY", "HAPPINESS", "HEALING", "HOSPITALITY", "LOVE", "MERCY", "PEACE", "REVELRY", "SACRIFICE", "WISDOM"],
    "TWILIGHT": [],
    "VALOR": [],
    "VICTORY": [],
    "VOLCANOS": [],
    "WAR": ["METALS", "STRENGTH"],
    "WATER": ["ANIMALS", "FISH", "LAKES", "MUCK", "NATURE", "OCEANS", "PLANTS", "RIVERS"],
    "WEALTH": ["FIRE"],
    "WEATHER": [],
    "WIND": ["HUNTING", "SKY"],
    "WISDOM": ["CHARITY", "CONSOLATION", "FORGIVENESS", "FREEDOM", "GENEROSITY", "HAPPINESS", "HEALING", "HOSPITALITY", "LOVE", "MERCY", "PEACE", "REVELRY", "SACRIFICE", "TRUTH"],
    "WRITING": [],
    "YOUTH": [],
}

OPPOSED: dict[str, list[str]] = {
    "AGRICULTURE": [],
    "ANIMALS": [],
    "ART": [],
    "BALANCE": [],
    "BEAUTY": [],
    "BIRTH": [],
    "BLIGHT": ["CHARITY", "CONSOLATION", "FORGIVENESS", "FREEDOM", "GENEROSITY", "HAPPINESS", "HEALING", "HOSPITALITY", "LOVE", "MERCY", "PEACE", "REVELRY", "SACRIFICE", "TRUTH", "WISDOM"],
    "BOUNDARIES": [],
    "CAVERNS": [],
    "CHAOS": ["CHARITY", "CONSOLATION", "FORGIVENESS", "FREEDOM", "GENEROSITY", "HAPPINESS", "HEALING", "HOSPITALITY", "LOVE", "MERCY", "PEACE", "REVELRY", "SACRIFICE", "TRUTH", "WISDOM"],
    "CHARITY": ["BLIGHT", "CHAOS", "DEATH", "DEFORMITY", "DEPRAVITY", "DISEASE", "JEALOUSY", "LIES", "MISERY", "MURDER", "NIGHTMARES", "SUICIDE", "THEFT", "THRALLDOM", "TORTURE", "TREACHERY"],
    "CHILDREN": [],
    "COASTS": [],
    "CONSOLATION": ["BLIGHT", "CHAOS", "DEATH", "DEFORMITY", "DEPRAVITY", "DISEASE", "JEALOUSY", "LIES", "MISERY", "MURDER", "NIGHTMARES", "SUICIDE", "THEFT", "THRALLDOM", "TORTURE", "TREACHERY"],
    "COURAGE": [],
    "CRAFTS": [],
    "CREATION": [],
    "DANCE": [],
    "DARKNESS": [],
    "DAWN": [],
    "DAY": [],
    "DEATH": ["CHARITY", "CONSOLATION", "FORGIVENESS", "FREEDOM", "GENEROSITY", "HAPPINESS", "HEALING", "HOSPITALITY", "LOVE", "MERCY", "PEACE", "REVELRY", "SACRIFICE", "TRUTH", "WISDOM"],
    "DEFORMITY": ["CHARITY", "CONSOLATION", "FORGIVENESS", "FREEDOM", "GENEROSITY", "HAPPINESS", "HEALING", "HOSPITALITY", "LOVE", "MERCY", "PEACE", "REVELRY", "SACRIFICE", "TRUTH", "WISDOM"],
    "DEPRAVITY": ["CHARITY", "CONSOLATION", "FORGIVENESS", "FREEDOM", "GENEROSITY", "HAPPINESS", "HEALING", "HOSPITALITY", "LOVE", "MERCY", "PEACE", "REVELRY", "SACRIFICE", "TRUTH", "WISDOM"],
    "DISCIPLINE": [],
    "DISEASE": ["CHARITY", "CONSOLATION", "FORGIVENESS", "FREEDOM", "GENEROSITY", "HAPPINESS", "HEALING", "HOSPITALITY", "LOVE", "MERCY", "PEACE", "REVELRY", "SACRIFICE", "TRUTH", "WISDOM"],
    "DREAMS": [],
    "DUSK": [],
    "DUTY": [],
    "EARTH": [],
    "FAME": [],
    "FAMILY": [],
    "FATE": [],
    "FERTILITY": [],
    "FESTIVALS": [],
    "FIRE": [],
    "FISH": [],
    "FISHING": [],
    "FOOD": [],
    "FORGIVENESS": ["BLIGHT", "CHAOS", "DEATH", "DEFORMITY", "DEPRAVITY", "DISEASE", "JEALOUSY", "LIES", "MISERY", "MURDER", "NIGHTMARES", "SUICIDE", "THEFT", "THRALLDOM", "TORTURE", "TREACHERY"],
    "FORTRESSES": [],
    "FREEDOM": ["BLIGHT", "CHAOS", "DEATH", "DEFORMITY", "DEPRAVITY", "DISEASE", "JEALOUSY", "LIES", "MISERY", "MURDER", "NIGHTMARES", "SUICIDE", "THEFT", "THRALLDOM", "TORTURE", "TREACHERY"],
    "GAMBLING": [],
    "GAMES": [],
    "GENEROSITY": ["BLIGHT", "CHAOS", "DEATH", "DEFORMITY", "DEPRAVITY", "DISEASE", "JEALOUSY", "LIES", "MISERY", "MURDER", "NIGHTMARES", "SUICIDE", "THEFT", "THRALLDOM", "TORTURE", "TREACHERY"],
    "HAPPINESS": ["BLIGHT", "CHAOS", "DEATH", "DEFORMITY", "DEPRAVITY", "DISEASE", "JEALOUSY", "LIES", "MISERY", "MURDER", "NIGHTMARES", "SUICIDE", "THEFT", "THRALLDOM", "TORTURE", "TREACHERY"],
    "HEALING": ["BLIGHT", "CHAOS", "DEATH", "DEFORMITY", "DEPRAVITY", "DISEASE", "JEALOUSY", "LIES", "MISERY", "MURDER", "NIGHTMARES", "SUICIDE", "THEFT", "THRALLDOM", "TORTURE", "TREACHERY"],
    "HOSPITALITY": ["BLIGHT", "CHAOS", "DEATH", "DEFORMITY", "DEPRAVITY", "DISEASE", "JEALOUSY", "LIES", "MISERY", "MURDER", "NIGHTMARES", "SUICIDE", "THEFT", "THRALLDOM", "TORTURE", "TREACHERY"],
    "HUNTING": [],
    "INSPIRATION": [],
    "JEALOUSY": ["CHARITY", "CONSOLATION", "FORGIVENESS", "FREEDOM", "GENEROSITY", "HAPPINESS", "HEALING", "HOSPITALITY", "LOVE", "MERCY", "PEACE", "REVELRY", "SACRIFICE", "TRUTH", "WISDOM"],
    "JEWELS": [],
    "JUSTICE": [],
    "LABOR": [],
    "LAKES": [],
    "LAWS": [],
    "LIES": ["CHARITY", "CONSOLATION", "FORGIVENESS", "FREEDOM", "GENEROSITY", "HAPPINESS", "HEALING", "HOSPITALITY", "LOVE", "MERCY", "PEACE", "REVELRY", "SACRIFICE", "TRUTH", "WISDOM"],
    "LIGHT": [],
    "LIGHTNING": [],
    "LONGEVITY": [],
    "LOVE": ["BLIGHT", "CHAOS", "DEATH", "DEFORMITY", "DEPRAVITY", "DISEASE", "JEALOUSY", "LIES", "MISERY", "MURDER", "NIGHTMARES", "SUICIDE", "THEFT", "THRALLDOM", "TORTURE", "TREACHERY"],
    "LOYALTY": [],
    "LUCK": [],
    "LUST": [],
    "MARRIAGE": [],
    "MERCY": ["BLIGHT", "CHAOS", "DEATH", "DEFORMITY", "DEPRAVITY", "DISEASE", "JEALOUSY", "LIES", "MISERY", "MURDER", "NIGHTMARES", "SUICIDE", "THEFT", "THRALLDOM", "TORTURE", "TREACHERY"],
    "METALS": [],
    "MINERALS": [],
    "MISERY": ["CHARITY", "CONSOLATION", "FORGIVENESS", "FREEDOM", "GENEROSITY", "HAPPINESS", "HEALING", "HOSPITALITY", "LOVE", "MERCY", "PEACE", "REVELRY", "SACRIFICE", "TRUTH", "WISDOM"],
    "MIST": [],
    "MOON": [],
    "MOUNTAINS": [],
    "MUCK": [],
    "MURDER": ["CHARITY", "CONSOLATION", "FORGIVENESS", "FREEDOM", "GENEROSITY", "HAPPINESS", "HEALING", "HOSPITALITY", "LOVE", "MERCY", "PEACE", "REVELRY", "SACRIFICE", "TRUTH", "WISDOM"],
    "MUSIC": [],
    "NATURE": [],
    "NIGHT": [],
    "NIGHTMARES": ["CHARITY", "CONSOLATION", "FORGIVENESS", "FREEDOM", "GENEROSITY", "HAPPINESS", "HEALING", "HOSPITALITY", "LOVE", "MERCY", "PEACE", "REVELRY", "SACRIFICE", "TRUTH", "WISDOM"],
    "OATHS": [],
    "OCEANS": [],
    "ORDER": [],
    "PAINTING": [],
    "PEACE": ["BLIGHT", "CHAOS", "DEATH", "DEFORMITY", "DEPRAVITY", "DISEASE", "JEALOUSY", "LIES", "MISERY", "MURDER", "NIGHTMARES", "SUICIDE", "THEFT", "THRALLDOM", "TORTURE", "TREACHERY"],
    "PERSUASION": [],
    "PLANTS": [],
    "POETRY": [],
    "PREGNANCY": [],
    "RAIN": [],
    "RAINBOWS": [],
    "REBIRTH": [],
    "REVELRY": ["BLIGHT", "CHAOS", "DEATH", "DEFORMITY", "DEPRAVITY", "DISEASE", "JEALOUSY", "LIES", "MISERY", "MURDER", "NIGHTMARES", "SUICIDE", "THEFT", "THRALLDOM", "TORTURE", "TREACHERY"],
    "REVENGE": [],
    "RIVERS": [],
    "RULERSHIP": [],
    "RUMORS": [],
    "SACRIFICE": ["BLIGHT", "CHAOS", "DEATH", "DEFORMITY", "DEPRAVITY", "DISEASE", "JEALOUSY", "LIES", "MISERY", "MURDER", "NIGHTMARES", "SUICIDE", "THEFT", "THRALLDOM", "TORTURE", "TREACHERY"],
    "SALT": [],
    "SCHOLARSHIP": [],
    "SEASONS": [],
    "SILENCE": [],
    "SKY": [],
    "SONG": [],
    "SPEECH": [],
    "STARS": [],
    "STORMS": [],
    "STRENGTH": [],
    "SUICIDE": ["CHARITY", "CONSOLATION", "FORGIVENESS", "FREEDOM", "GENEROSITY", "HAPPINESS", "HEALING", "HOSPITALITY", "LOVE", "MERCY", "PEACE", "REVELRY", "SACRIFICE", "TRUTH", "WISDOM"],
    "SUN": [],
    "THEFT": ["CHARITY", "CONSOLATION", "FORGIVENESS", "FREEDOM", "GENEROSITY", "HAPPINESS", "HEALING", "HOSPITALITY", "LOVE", "MERCY", "PEACE", "REVELRY", "SACRIFICE", "TRUTH", "WISDOM"],
    "THRALLDOM": ["CHARITY", "CONSOLATION", "FORGIVENESS", "FREEDOM", "GENEROSITY", "HAPPINESS", "HEALING", "HOSPITALITY", "LOVE", "MERCY", "PEACE", "REVELRY", "SACRIFICE", "TRUTH", "WISDOM"],
    "THUNDER": [],
    "TORTURE": ["CHARITY", "CONSOLATION", "FORGIVENESS", "FREEDOM", "GENEROSITY", "HAPPINESS", "HEALING", "HOSPITALITY", "LOVE", "MERCY", "PEACE", "REVELRY", "SACRIFICE", "TRUTH", "WISDOM"],
    "TRADE": [],
    "TRAVELERS": [],
    "TREACHERY": ["CHARITY", "CONSOLATION", "FORGIVENESS", "FREEDOM", "GENEROSITY", "HAPPINESS", "HEALING", "HOSPITALITY", "LOVE", "MERCY", "PEACE", "REVELRY", "SACRIFICE", "TRUTH", "WISDOM"],
    "TREES": [],
    "TRICKERY": [],
    "TRUTH": ["BLIGHT", "CHAOS", "DEATH", "DEFORMITY", "DEPRAVITY", "DISEASE", "JEALOUSY", "LIES", "MISERY", "MURDER", "NIGHTMARES", "SUICIDE", "THEFT", "THRALLDOM", "TORTURE", "TREACHERY"],
    "TWILIGHT": [],
    "VALOR": [],
    "VICTORY": [],
    "VOLCANOS": [],
    "WAR": [],
    "WATER": [],
    "WEALTH": [],
    "WEATHER": [],
    "WIND": [],
    "WISDOM": ["BLIGHT", "CHAOS", "DEATH", "DEFORMITY", "DEPRAVITY", "DISEASE", "JEALOUSY", "LIES", "MISERY", "MURDER", "NIGHTMARES", "SUICIDE", "THEFT", "THRALLDOM", "TORTURE", "TREACHERY"],
    "WRITING": [],
    "YOUTH": [],
}

REGION_SPHERES: dict[str, list[str]] = {
    "DESERT": ["ANIMALS", "FIRE", "NATURE", "PLANTS"],
    "FOREST": ["ANIMALS", "NATURE", "PLANTS", "RIVERS", "TREES"],
    "GLACIER": ["ANIMALS", "NATURE"],
    "GRASSLAND": ["ANIMALS", "NATURE", "PLANTS", "RIVERS"],
    "HILLS": ["ANIMALS", "NATURE", "PLANTS", "RIVERS"],
    "LAKE": ["ANIMALS", "FISH", "LAKES", "NATURE", "RIVERS", "WATER"],
    "MOUNTAINS": ["ANIMALS", "CAVERNS", "METALS", "MINERALS", "MOUNTAINS", "NATURE"],
    "NONE": [],
    "OCEAN": ["ANIMALS", "FISH", "NATURE", "OCEANS", "WATER"],
    "SWAMP": ["ANIMALS", "MUCK", "NATURE", "PLANTS", "WATER"],
    "TUNDRA": ["ANIMALS", "NATURE"],
}

DWARVEN: list[Word] = [
    Word(gloss="anvil", dw="zuntîr", pos="noun"),
    Word(gloss="ash", dw="ibruk", pos="noun"),
    Word(gloss="blight", dw="sharsid", pos="noun"),
    Word(gloss="blood", dw="nazush", pos="noun"),
    Word(gloss="bloody", dw="nashon", pos="noun"),
    Word(gloss="bone", dw="osod", pos="noun"),
    Word(gloss="book", dw="thîkut", pos="noun"),
    Word(gloss="candle", dw="tílgil", pos="noun"),
    Word(gloss="chain", dw="nicat", pos="noun"),
    Word(gloss="clash", dw="lisid", pos="noun"),
    Word(gloss="clearing", dw="dostob", pos="noun"),
    Word(gloss="crown", dw="torish", pos="noun"),
    Word(gloss="dark", dw="umom", pos="noun"),
    Word(gloss="deep", dw="thol", pos="noun"),
    Word(gloss="delight", dw="amith", pos="noun"),
    Word(gloss="depth", dw="amas", pos="noun"),
    Word(gloss="donkey", dw="nuggad", pos="noun"),
    Word(gloss="door", dw="tun", pos="noun"),
    Word(gloss="dream", dw="nåzom", pos="noun"),
    Word(gloss="dwell", dw="kokeb", pos="noun"),
    Word(gloss="dwelling", dw="siknug", pos="noun"),
    Word(gloss="echo", dw="sárek", pos="noun"),
    Word(gloss="eye", dw="ker", pos="noun"),
    Word(gloss="famine", dw="sogdol", pos="noun"),
    Word(gloss="flash", dw="asiz", pos="noun"),
    Word(gloss="flight", dw="vuthil", pos="noun"),
    Word(gloss="floor", dw="dakost", pos="noun"),
    Word(gloss="furnace", dw="sarvesh", pos="noun"),
    Word(gloss="gate", dw="inod", pos="noun"),
    Word(gloss="ghost", dw="ngotol", pos="noun"),
    Word(gloss="gold", dw="limul", pos="noun"),
    Word(gloss="grave", dw="mondûl", pos="noun"),
    Word(gloss="gravel", dw="asën", pos="noun"),
    Word(gloss="hall", dw="îton", pos="noun"),
    Word(gloss="hammer", dw="nil", pos="noun"),
    Word(gloss="hammerer", dw="ùnil", pos="noun"),
    Word(gloss="iron", dw="datan", pos="noun"),
    Word(gloss="key", dw="edëm", pos="noun"),
    Word(gloss="king", dw="etar", pos="noun"),
    Word(gloss="kingdom", dw="osor", pos="noun"),
    Word(gloss="knot", dw="oth", pos="noun"),
    Word(gloss="lash", dw="meng", pos="noun"),
    Word(gloss="light", dw="istam", pos="noun"),
    Word(gloss="lightning", dw="giken", pos="noun"),
    Word(gloss="mine", dw="avuz", pos="noun"),
    Word(gloss="mirror", dw="ònul", pos="noun"),
    Word(gloss="monkey", dw="vankåb", pos="noun"),
    Word(gloss="mountain", dw="onol", pos="noun"),
    Word(gloss="mushroom", dw="kirun", pos="noun"),
    Word(gloss="name", dw="kab", pos="noun"),
    Word(gloss="negate", dw="kez", pos="noun"),
    Word(gloss="pit", dw="gor", pos="noun"),
    Word(gloss="pitch", dw="damol", pos="noun"),
    Word(gloss="ring object", dw="athel", pos="noun"),
    Word(gloss="room", dw="mosus", pos="noun"),
    Word(gloss="root", dw="odur", pos="noun"),
    Word(gloss="rootverb", dw="lulâr", pos="noun"),
    Word(gloss="salt", dw="nabid", pos="noun"),
    Word(gloss="secret", dw="nekut", pos="noun"),
    Word(gloss="seed", dw="lenod", pos="noun"),
    Word(gloss="shadow", dw="shedim", pos="noun"),
    Word(gloss="spit", dw="òstob", pos="noun"),
    Word(gloss="spite", dw="zakgol", pos="noun"),
    Word(gloss="spittle", dw="lashid", pos="noun"),
    Word(gloss="splash", dw="rulush", pos="noun"),
    Word(gloss="spring noun", dw="kigok", pos="noun"),
    Word(gloss="spring season", dw="bekom", pos="noun"),
    Word(gloss="steel", dw="deler", pos="noun"),
    Word(gloss="stone", dw="lam", pos="noun"),
    Word(gloss="string", dw="birut", pos="noun"),
    Word(gloss="suffering", dw="omshit", pos="noun"),
    Word(gloss="supper", dw="nis", pos="noun"),
    Word(gloss="swallow", dw="mozib", pos="noun"),
    Word(gloss="sword", dw="dastot", pos="noun"),
    Word(gloss="tomb", dw="rakust", pos="noun"),
    Word(gloss="tournament", dw="mëlist", pos="noun"),
    Word(gloss="trash", dw="rëdreg", pos="noun"),
    Word(gloss="tunnel", dw="ód", pos="noun"),
    Word(gloss="twilight", dw="ingtak", pos="noun"),
    Word(gloss="void", dw="torir", pos="noun"),
    Word(gloss="ash", dw="ibruk", pos="adjective"),
    Word(gloss="ashamed", dw="mangròd", pos="adjective"),
    Word(gloss="awe-inspiring", dw="gòstang", pos="adjective"),
    Word(gloss="blight", dw="sharsid", pos="adjective"),
    Word(gloss="bloody", dw="nashon", pos="adjective"),
    Word(gloss="brash", dw="midrim", pos="adjective"),
    Word(gloss="carmine", dw="thastith", pos="adjective"),
    Word(gloss="dark", dw="umom", pos="adjective"),
    Word(gloss="deep", dw="thol", pos="adjective"),
    Word(gloss="delight", dw="amith", pos="adjective"),
    Word(gloss="dream", dw="nåzom", pos="adjective"),
    Word(gloss="flighty", dw="rersîr", pos="adjective"),
    Word(gloss="gold", dw="limul", pos="adjective"),
    Word(gloss="goldenrod", dw="thistun", pos="adjective"),
    Word(gloss="light", dw="istam", pos="adjective"),
    Word(gloss="mountain", dw="onol", pos="adjective"),
    Word(gloss="name", dw="kab", pos="adjective"),
    Word(gloss="roomy", dw="omthel", pos="adjective"),
    Word(gloss="salt", dw="nabid", pos="adjective"),
    Word(gloss="secret", dw="nekut", pos="adjective"),
    Word(gloss="spite", dw="zakgol", pos="adjective"),
    Word(gloss="squash", dw="stukón", pos="adjective"),
    Word(gloss="stale", dw="vuzded", pos="adjective"),
    Word(gloss="tunnel", dw="ód", pos="adjective"),
    Word(gloss="unnameable", dw="nan", pos="adjective"),
    Word(gloss="wall", dw="adil", pos="adjective"),
    Word(gloss="wash", dw="stelid", pos="adjective"),
    Word(gloss="word", dw="il", pos="adjective"),
    Word(gloss="abate", dw="med", pos="adjective"),
    Word(gloss="absolute", dw="ilas", pos="adjective"),
    Word(gloss="abysmal", dw="sosas", pos="adjective"),
    Word(gloss="abyss", dw="ngalák", pos="adjective"),
    Word(gloss="accident", dw="kuthdêng", pos="adjective"),
    Word(gloss="ace", dw="alak", pos="adjective"),
    Word(gloss="ache", dw="agseth", pos="adjective"),
    Word(gloss="acrid", dw="tatek", pos="adjective"),
    Word(gloss="admire", dw="nebél", pos="adjective"),
    Word(gloss="adore", dw="salir", pos="adjective"),
    Word(gloss="adventure", dw="cenäth", pos="adjective"),
    Word(gloss="afflict", dw="thokit", pos="adjective"),
    Word(gloss="ageless", dw="gatal", pos="adjective"),
    Word(gloss="alchemy", dw="anzish", pos="adjective"),
    Word(gloss="ally", dw="astel", pos="adjective"),
    Word(gloss="amaze", dw="edos", pos="adjective"),
    Word(gloss="amber", dw="thukkan", pos="adjective"),
    Word(gloss="ambiguous", dw="umgan", pos="adjective"),
    Word(gloss="amethyst", dw="alron", pos="adjective"),
    Word(gloss="amuse", dw="ïdath", pos="adjective"),
    Word(gloss="ancient", dw="zustash", pos="adjective"),
    Word(gloss="angel", dw="sedil", pos="adjective"),
]
# END GENERATED MIRROR


# ---------------------------------------------------------------------------
# Worldgen — ages, spheres, kinship, forgotten beasts
# (roblox/src/shared/Worldgen.luau)
# ---------------------------------------------------------------------------
AGES: List[str] = ["the Age of Myth", "the Age of Heroes", "the Age of Legends"]
KILLS_PER_AGE = 10
ORDINALS: List[str] = ["", "Second", "Third", "Fourth", "Fifth", "Sixth", "Seventh"]


def _names(list_: Sequence[str], cap: int) -> str:
    if not list_:
        return "none"  # negative is a fact: unaligned spheres hold no kin/foes
    return " and ".join(list_[:cap])


@dataclass
class Beast:
    name: str
    sphere: str
    allies: List[str]
    opposed: List[str]


class ArtifactLore:
    """The one ArtifactLore piece Worldgen needs: the dwarven compound namer
    (shared/ArtifactLore.luau dwarvenCompound). Pools are built by iterating
    DWARVEN in order, exactly like the Luau, so rng draw order matches."""

    def __init__(self, dwarven: Sequence[Word] = DWARVEN) -> None:
        self.adj_pool = [w for w in dwarven if w.pos == "adjective"]
        self.noun_pool = [w for w in dwarven if w.pos != "adjective"]

    def dwarven_compound(self, rng: SeedRng) -> Tuple[str, str]:
        use_adj = rng.next() < 0.5
        first = self.adj_pool[rng.int(1, len(self.adj_pool)) - 1] if use_adj \
            else self.noun_pool[rng.int(1, len(self.noun_pool)) - 1]
        second = self.noun_pool[rng.int(1, len(self.noun_pool)) - 1]
        return (f"{first.dw} {second.dw}", f"{first.gloss} {second.gloss}")


class Worldgen:
    """Ages + spheres + kinship laws. The Luau module is a singleton with
    boss-kill state; the port is an instance (fresh state per campaign) with
    the generated tables injectable for tests, defaulting to the mirrors."""

    def __init__(self, spheres: Sequence[str] = SPHERES,
                 alignment: Dict[str, str] = ALIGNMENT,
                 allies: Dict[str, List[str]] = ALLIES,
                 opposed: Dict[str, List[str]] = OPPOSED,
                 artifact_lore: Optional[ArtifactLore] = None) -> None:
        self.spheres = list(spheres)
        self.alignment = alignment
        self.allies = allies
        self.opposed = opposed
        self.artifact_lore = artifact_lore or ArtifactLore()
        self.boss_kills = 0
        self.kill_log: List[str] = []

    # megabeast deaths move the world's age; ages recur with ordinals (DF law)
    def note_boss_kill(self, name: str) -> None:
        self.boss_kills += 1
        self.kill_log.append(name)

    def age_text(self) -> str:
        stage = self.boss_kills // KILLS_PER_AGE          # 0-based into AGES
        cycle = stage // len(AGES)
        age = AGES[stage % len(AGES)]
        if cycle == 0:
            return age[0].upper() + age[1:]
        ordinal = ORDINALS[min(cycle, len(ORDINALS) - 1)]  # Luau 1-based min(cycle+1, #ORDINALS)
        # "the Age of Myth" -> "the Second Age of Myth" (AGES are "the "-prefixed)
        return f"the {ordinal} {age[4:]}"

    def kill_count(self) -> int:
        return self.boss_kills

    # sphere kinship = which zones ally (WORLDGEN_MINE.md law 4): opposition
    # (good vs evil) outranks co-occurrence kin; everything else is independent
    def zone_alliance(self, a: str, b: str) -> str:
        if b in self.opposed.get(a, ()):
            return "opposed"
        if b in self.allies.get(a, ()):
            return "allied"
        return "independent"

    def sphere_alignment(self, sphere: str) -> str:
        return self.alignment.get(sphere, "unaligned")

    def forgotten_beast(self, rng: SeedRng) -> Beast:
        dw, en = self.artifact_lore.dwarven_compound(rng)
        sphere = self.spheres[rng.int(1, len(self.spheres)) - 1]
        titled = en[0].upper() + en[1:]
        return Beast(
            name=f'{dw}, "the {titled} of {sphere}"',
            sphere=sphere,
            allies=list(self.allies.get(sphere, ())),
            opposed=list(self.opposed.get(sphere, ())),
        )

    def forgotten_name(self, rng: SeedRng) -> str:
        return self.forgotten_beast(rng).name

    # the alliance sentence for the first-seen announcement: sourced rows only
    def kinship_line(self, beast: Beast) -> str:
        return (f"Kin: {_names(beast.allies, 2)}. "
                f"Foes: {_names(beast.opposed, 2)}.")


# module-level default, the Luau singleton's shadow (read-mostly laws + data)
WORLDGEN = Worldgen()


# ---------------------------------------------------------------------------
# ZoneGate — portal gating by per-soul sphere vs region alliance
# (roblox/src/server/ZoneGate.luau)
# ---------------------------------------------------------------------------
@dataclass
class Soul:
    """The Roblox Player mirror: a UserId plus the attribute bag. The sphere
    attribute is drawn once per soul and never changes, so every gate verdict
    for a soul is static."""

    user_id: int
    attributes: Dict[str, object] = field(default_factory=dict)


def gate_attr(zone: str) -> str:
    # Lua %W = [^a-zA-Z0-9]; Python \W also excludes "_" — outputs identical
    # (Lua maps "_" -> "_" itself). See module docstring.
    return "Gate_" + re.sub(r"\W", "_", zone)


LedgerRecord = Callable[[Soul, str, str, bool], None]


class ZoneGate:
    """WORLDGEN_MINE.md law 4 (t35): zone access/buffs gated by sphere
    alliance. Each zone joins one region (the authored join handed to
    :meth:`init`); the region's sphere row is sourced data. The gate owns no
    zone-name list — the join is the single authorship site, the map here is
    its only writer (t67)."""

    BUFF_SECONDS = 300
    REFUSAL_SECONDS = 5

    def __init__(self, region_spheres: Dict[str, List[str]] = REGION_SPHERES,
                 worldgen: Optional[Worldgen] = None,
                 clock: Optional[Callable[[], int]] = None,
                 record: Optional[LedgerRecord] = None) -> None:
        self.region_spheres = region_spheres
        self.worldgen = worldgen or WORLDGEN
        self._clock = clock or _wall_seconds
        self._record_cb = record
        # ShadowLedger shadow: (place, message, positive, userId)
        self.ledger: List[Tuple[str, str, bool, int]] = []
        # derived join, filled by init from the WAVE rows; NONE is never
        # picked: its row is empty, a zone joined to it would carry no gate
        # and the law would be silent furniture.
        self.zone_regions: Dict[str, str] = {}
        self._last_buff: Dict[str, int] = {}      # "userId|zone" -> seconds
        self._last_refusal: Dict[int, int] = {}   # userId -> seconds

    # -- ledger (ShadowLedger.record mirror: player, place, text, positive) --
    def _note(self, soul: Soul, place: str, message: str, positive: bool, when: int) -> None:
        self.ledger.append((place, message, positive, soul.user_id))
        if self._record_cb is not None:
            self._record_cb(soul, place, message, positive)

    # one sphere per soul: seeded by the UserId so the same player returns to
    # the same allegiance without any picker UI
    def ensure_sphere(self, soul: Soul) -> str:
        existing = soul.attributes.get("Sphere")
        if isinstance(existing, str):
            return existing
        rng = SeedRng(soul.user_id * 7919)
        sphere = self.worldgen.spheres[rng.int(1, len(self.worldgen.spheres)) - 1]
        soul.attributes["Sphere"] = sphere
        return sphere

    # alliance across the region's whole sphere row: opposition outranks
    # kinship (law 4 precedence), so the first opposed sphere decides and
    # otherwise any allied sphere marks the region as kin
    def alliance_for(self, sphere: str, region: str) -> str:
        row = self.region_spheres.get(region)
        if row is None:
            return "independent"  # unjoined region: no kin, no enmity (a fact)
        verdict = "independent"
        for s in row:
            a = self.worldgen.zone_alliance(sphere, s)
            if a == "opposed":
                return "opposed"
            if a == "allied":
                verdict = "allied"
        return verdict

    # the portal hook: True = take the teleport, False = refused at the ring
    def portal_gate(self, soul: Soul, zone: str) -> bool:
        region = self.zone_regions.get(zone)
        if region is None:
            return True  # fixed climbs carry no join, so no gate (a fact)
        sphere = self.ensure_sphere(soul)
        alliance = self.alliance_for(sphere, region)
        if alliance == "opposed":
            now = self._clock()
            if now - self._last_refusal.get(soul.user_id, 0) >= self.REFUSAL_SECONDS:
                self._last_refusal[soul.user_id] = now
                self._note(soul, "Basecamp",
                           f"the portal to {zone} refuses you: your sphere "
                           f"{sphere} stands opposed to the {region}", False, now)
            return False
        if alliance == "allied":
            key = f"{soul.user_id}|{zone}"
            now = self._clock()
            if now - self._last_buff.get(key, 0) >= self.BUFF_SECONDS:
                self._last_buff[key] = now
                soul.attributes["VirtueMarks"] = \
                    int(soul.attributes.get("VirtueMarks") or 0) + 1
                self._note(soul, "Basecamp",
                           f"the {region} region welcomes a {sphere} soul: "
                           f"the way is open (+1 Virtue Mark)", True, now)
        return True

    # t46: stamp the same alliance_for verdict the gate enforces, once at
    # join (sphere never changes, so the verdicts are static per soul);
    # climb portals get no attribute, they carry no join and no tint
    def attach(self, soul: Soul) -> None:
        sphere = self.ensure_sphere(soul)
        for zone, region in self.zone_regions.items():
            soul.attributes[gate_attr(zone)] = self.alliance_for(sphere, region)

    # receives the join derived from the WAVE rows; the campaign authorship
    # site is the only writer (t67). PlayerAdded -> attach here is pull-based.
    def init(self, regions: Dict[str, str], souls: Sequence[Soul] = ()) -> None:
        self.zone_regions = dict(regions)
        for soul in souls:
            self.attach(soul)


def _wall_seconds() -> int:
    import time
    return int(time.time())
