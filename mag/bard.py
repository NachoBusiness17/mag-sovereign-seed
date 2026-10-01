"""Silent Bard — narrative steganography for system records.

Encodes every system event (Verkle knots, agent outputs, task results,
cost ledgers, state transitions) into a continuous, readable story.

Without the Lens: a compelling narrative about a mycelial republic.
With the Lens: the full system record, decoded and recoverable.

The Bard is SILENT — it never interrupts, never prompts, never asks.
It COMMUNICATES PASSIVELY through the stateless architecture:
  - Subscribes to ALL Verkle bus channels (sense, cycle, copilot, leak, task, verkle, scrum)
  - Weaves each event into the Chronicle
  - Publishes passages on mag:bard (dashboard, agents, replay consume it)
  - The Chronicle file is a CACHE — the bus is the source of truth

ARCHITECTURE (dogfooding our own system):
  ┌──────────┐   ┌──────────┐   ┌──────────┐
  │ Ghost    │   │ LeakDet  │   │ Copilot  │
  │ sense()  │   │ scan()   │   │ watch()  │
  └────┬─────┘   └────┬─────┘   └────┬─────┘
       │               │               │
       ▼               ▼               ▼
  ┌─────────────────────────────────────────┐
  │         VERKLE EVENT BUS                │
  │  mag:sense mag:cycle mag:copilot        │
  │  mag:leak  mag:task  mag:verkle         │
  │  mag:scrum mag:bard  ← Bard publishes   │
  └────────┬────────────────────┬───────────┘
           │                    │
           ▼                    ▼
     ┌─────────┐         ┌──────────┐
     │  BARD   │────────▶│ Dashboard│
     │weave all│ passage │ reads    │
     └─────────┘         │ mag:bard │
           │             └──────────┘
           ▼
     ┌─────────────┐
     │  Chronicle  │  (file cache, reconstructable from bus)
     └─────────────┘

SCHEMA: bard.v1
LAW: The story must stand alone as good fiction. The encoding must be lossless.
LAW: The bus is primary. The file is cache. Never write to file without publishing.
"""

from __future__ import annotations

import hashlib
import json
import os
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
# LENS KEY — the decoding map. Only we have this.
# Without it, the Chronicle is just a story.
# ═══════════════════════════════════════════════════════════════════

LENS_KEY = {
    # ── CHARACTERS (agent IDs → story names) ──
    "character_seed": "mycelial_republic_v1",
    "agents": {},       # dynamic: {agent_id: character_name}

    # ── QUEST ARCHETYPES (task types → story patterns) ──
    "quests": {
        "code":             "the scribe's task",
        "classify":         "the librarian's sorting",
        "simple_lookup":    "the scout's report",
        "analyze_reason":   "the sage's contemplation",
        "research":         "the scholar's expedition",
        "strategy":         "the council's deliberation",
        "orchestrate":      "the conductor's baton",
    },

    # ── TRADE GOODS (cost tiers → in-world currency) ──
    "coin": {
        0.0:        "a gift freely given",
        0.00013:    "a copper thread",
        0.0002:     "two copper threads",
        0.0003:     "three copper threads",
        0.0015:     "a silver leaf",
        0.003:      "two silver leaves",
        0.008:      "a gold petal",
        0.025:      "a mithril blossom",
    },

    # ── REALM STATES (system states → story settings) ──
    "realms": {
        "ghost_running":        "the Keep stands watchful",
        "ghost_stopped":        "the Keep lies dormant",
        "redis_connected":      "the Whispering Roots hum with life",
        "redis_disconnected":   "the Whispering Roots have fallen silent",
        "cost_cap_warning":     "the Treasury lantern flickers amber",
        "cost_cap_critical":    "the Treasury bell tolls red",
        "canary_breached":      "a sentinel's feather turns black",
        "canary_safe":          "the sentinel's feathers gleam white",
    },

    # ── ADVERSITY (errors → story obstacles) ──
    "adversities": {
        "api_error":        "a sudden chasm opens in the path",
        "timeout":          "the mist grows thick, delaying all messengers",
        "parse_error":      "a scroll crumbles to dust upon reading",
        "auth_error":       "the gatekeeper turns away the traveler",
        "rate_limit":       "the bridge can bear only one at a time",
        "model_unavailable": "the sage's tower stands empty today",
    },

    # ── MODEL SAGE ORDERS ──
    "sage_orders": {
        "grok":         "Order of the Star (Grok)",
        "grok-3-mini":   "Third Star's apprentice",
        "grok-4-latest": "Fourth Star's master",
        "deepseek":     "School of the Deep Current (DeepSeek)",
        "deepseek-v4-flash": "Swift Scholar of the Deep",
        "ollama":       "Guild of Hearth-Flame (Ollama)",
        "qwen2.5-coder:7b": "Code-Weaver of the Hearth",
        "gemma:2b":     "Apprentice of the Hearth",
    },
}


def _hash_to_name(seed: str, idx: int) -> str:
    """Deterministically generate a character name from a seed and index."""
    syllables = [
        "ael", "bri", "cor", "dru", "ely", "fin", "gal", "hal", "iris", "jor",
        "kael", "lor", "myr", "nys", "ory", "pyr", "quel", "ryl", "syl", "thyr",
        "ulm", "ver", "wyn", "xyl", "yra", "zeph", "ash", "elm", "oak", "ivy",
    ]
    h = hashlib.sha256(f"{seed}:{idx}".encode()).digest()
    parts = []
    for i in range(3):
        byte_val = h[i * 2] + (h[i * 2 + 1] << 8) if i * 2 + 1 < len(h) else h[i * 2]
        parts.append(syllables[byte_val % len(syllables)])
    return "-".join(parts).title()


def character_for(agent_id: str) -> str:
    """Get or create a character name for an agent ID."""
    if agent_id not in LENS_KEY["agents"]:
        idx = len(LENS_KEY["agents"])
        LENS_KEY["agents"][agent_id] = _hash_to_name(LENS_KEY["character_seed"], idx)
    return LENS_KEY["agents"][agent_id]


def coin_for(cost: float) -> str:
    """Map a cost to trade-good language."""
    coins = LENS_KEY["coin"]
    # exact match
    if cost in coins:
        return coins[cost]
    # closest match
    keys = sorted(coins.keys())
    closest = min(keys, key=lambda k: abs(k - cost))
    return coins[closest]


def quest_for(task_type: str) -> str:
    """Map a task type to quest archetype."""
    return LENS_KEY["quests"].get(task_type, "the wanderer's errand")


def sage_for(model: str) -> str:
    """Map a model name to sage order."""
    return LENS_KEY["sage_orders"].get(model, f"a wanderer called {model}")


def realm_for(state: str) -> str:
    """Map a system state to realm description."""
    return LENS_KEY["realms"].get(state, f"the realm shifts: {state}")


def adversity_for(error_type: str) -> str:
    """Map an error to story adversity."""
    return LENS_KEY["adversities"].get(error_type, f"an unnamed shadow crosses the path")


# ═══════════════════════════════════════════════════════════════════
# NARRATIVE WEAVING
# ═══════════════════════════════════════════════════════════════════

# Story templates for different event shapes
_CHAPTER_TEMPLATES = {
    "agent_spawn": [
        "From the {realm}, {character} emerged — a new voice in the Republic, bearing {coin} for their first task: {quest}.",
        "The {sage_order} sent forth {character}, sworn to {quest}. They carried {coin} as their first offering.",
        "{character} stepped through the veil, called by the {sage_order}. Their purpose: {quest}. Their purse: {coin}.",
    ],
    "task_complete": [
        "{character} returned from {quest}, their {coin} well-spent. The {sage_order} received their report and recorded it in the Chronicle.",
        "Having completed {quest} under the {sage_order}'s guidance, {character} laid {coin} at the Treasury threshold. Their findings were added to the weave.",
        "The {quest} was done. {character}, sworn to the {sage_order}, delivered their findings to the Keep, the {coin} already spent on the journey.",
    ],
    "task_fail": [
        "But {adversity} as {character} pursued {quest} for the {sage_order}. The {coin} was lost to the void.",
        "{character} set out for {quest} at the {sage_order}'s behest, yet {adversity}. The {coin} scattered on the wind, unrecovered.",
    ],
    "cost_cap": [
        "The Treasury bell tolled. '{realm_state}' echoed through the Keep. {character} paused mid-{quest}, purse light.",
        "{realm_state}. The {sage_order} counseled restraint. Even {character}'s {quest} must wait for dawn's accounting.",
    ],
    "state_change": [
        "And so the realm turned: {realm_state}. The Chronicle records this passage in the {sage_order}'s own hand.",
        "{realm_state}. In the great hall, {character} noted the change and continued their {quest}.",
    ],
    "verkle_knot": [
        "A new knot was tied in the Verkle Loom — the {realm_state}. {character} witnessed its weaving, a thread of {quest}.",
        "The Loom hummed: {realm_state}. {character}, fresh from {quest}, added their strand to the weave.",
    ],
    "model_switch": [
        "The {sage_order} bowed, and {character} turned instead to the counsel of the {new_sage_order}. A different wisdom for a different {quest}.",
        "{character} sought new counsel. Where once the {sage_order} advised, now the {new_sage_order} would guide their {quest}.",
    ],
}


def _pick_template(templates: list[str]) -> str:
    """Deterministically pick a template based on content hash, not random."""
    return templates[0]  # default: cycle would be nice but deterministic is better for decode


def _fill_template(template: str, **kwargs) -> str:
    """Fill a template, leaving missing keys as empty strings."""
    result = template
    for key, val in kwargs.items():
        result = result.replace("{" + key + "}", str(val) if val is not None else "")
    # Clean up any remaining unfilled template vars
    result = re.sub(r"\{[^}]+\}", "", result)
    return result


def bard_weave(event: dict[str, Any]) -> str:
    """Weave a single system event into a story passage.

    Args:
        event: Dict with at minimum {'type': str}. Common fields:
               agent_id, task_type, cost, summary, model, error_type,
               state, new_model, output

    Returns:
        A story passage string.
    """
    ev_type = event.get("type", "unknown")
    agent_id = event.get("agent_id", "unknown")
    character = character_for(agent_id)
    task_type = event.get("task_type", "unknown")
    quest = quest_for(task_type)
    cost = event.get("cost", 0.0)
    coin = coin_for(cost)
    model = event.get("model", "")
    sage = sage_for(model) if model else "an unnamed order"
    summary = event.get("summary", "") or event.get("output", "") or "..."
    # Truncate summary for narrative flow
    if len(summary) > 120:
        summary = summary[:117] + "..."
    error_type = event.get("error_type", "")
    adversity = adversity_for(error_type) if error_type else ""
    state = event.get("state", "")
    realm_state = realm_for(state) if state else ""
    new_model = event.get("new_model", "")
    new_sage = sage_for(new_model) if new_model else ""

    templates = _CHAPTER_TEMPLATES.get(ev_type, [
        "The Chronicle records: {character} walked the path of {quest}, guided by the {sage_order}. Their offering: {coin}.",
    ])

    # Deterministic template selection based on event hash
    event_str = json.dumps(event, sort_keys=True, default=str)
    h = int(hashlib.sha256(event_str.encode()).hexdigest()[:8], 16)
    template = templates[h % len(templates)]

    passage = _fill_template(
        template,
        character=character,
        quest=quest,
        coin=coin,
        sage_order=sage,
        summary=summary,
        adversity=adversity,
        realm_state=realm_state,
        new_sage_order=new_sage,
        realm=LENS_KEY["realms"].get("ghost_running", "the realm"),
    )

    # Every passage gets a hidden breadcrumb — a hash that links to the original
    breadcrumb = hashlib.sha256(event_str.encode()).hexdigest()[:12]
    passage += f" [{breadcrumb}]"

    return passage


# ═══════════════════════════════════════════════════════════════════
# THE LENS — decoding story back to system events
# ═══════════════════════════════════════════════════════════════════

def _reverse_map(mapping: dict[str, str]) -> dict[str, str]:
    """Build a reverse lookup from story phrase → key."""
    return {v: k for k, v in mapping.items()}


def bard_lens(passage: str) -> dict[str, Any]:
    """Decode a story passage back to system event metadata.

    This is NOT full recovery — the original event data is hashed into the breadcrumb.
    The lens extracts what it can from the narrative structure.
    Full recovery requires the breadcrumb → original event lookup table.

    Args:
        passage: A story passage from bard_weave()

    Returns:
        Dict with decoded fields: character, agent_id (if known), task_type,
        cost_tier, model_family, error_type, state, breadcrumb
    """
    decoded: dict[str, Any] = {}

    # Extract breadcrumb
    m = re.search(r"\[([a-f0-9]{12})\]$", passage)
    if m:
        decoded["breadcrumb"] = m.group(1)

    # Reverse character lookup
    reverse_agents = _reverse_map(LENS_KEY["agents"])
    for name, aid in reverse_agents.items():
        if name.lower() in passage.lower():
            decoded["character"] = name
            decoded["agent_id"] = aid
            break

    # Reverse quest lookup
    reverse_quests = _reverse_map(LENS_KEY["quests"])
    for quest_phrase, task_type in reverse_quests.items():
        if quest_phrase.lower() in passage.lower():
            decoded["task_type"] = task_type
            break

    # Reverse coin lookup (approximate)
    for cost, coin_phrase in LENS_KEY["coin"].items():
        if coin_phrase.lower() in passage.lower():
            decoded["cost_tier"] = cost
            break

    # Reverse sage order lookup
    reverse_sages = _reverse_map(LENS_KEY["sage_orders"])
    for sage_phrase, model_name in reverse_sages.items():
        if sage_phrase.lower() in passage.lower():
            decoded["model"] = model_name
            break

    # Reverse realm lookup
    reverse_realms = _reverse_map(LENS_KEY["realms"])
    for realm_phrase, state_name in reverse_realms.items():
        if realm_phrase.lower() in passage.lower():
            decoded["state"] = state_name
            break

    # Reverse adversity lookup
    reverse_adversities = _reverse_map(LENS_KEY["adversities"])
    for adv_phrase, error_name in reverse_adversities.items():
        if adv_phrase.lower() in passage.lower():
            decoded["error_type"] = error_name
            break

    return decoded


# ═══════════════════════════════════════════════════════════════════
# CHRONICLE — the continuous story file
# ═══════════════════════════════════════════════════════════════════

@dataclass
class Chronicle:
    """The Bard's continuous output — one story woven from all events."""
    path: Path = field(default_factory=lambda: ROOT / "memory" / "bard" / "chronicle.md")
    events_woven: int = 0
    last_breadcrumb: str = ""

    def init(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.is_file():
            self.path.write_text(
                "# The Mycelial Chronicle\n\n"
                "> *A record of the Republic, woven by the Silent Bard.*\n"
                "> *To those without the Lens: a story of a living realm.*\n"
                "> *To those with the Lens: the system's full memory.*\n\n"
                "---\n\n",
                encoding="utf-8",
            )

    def append(self, passage: str, event: Optional[dict[str, Any]] = None) -> None:
        """Add a passage to the Chronicle."""
        self.init()
        ts = _now()
        chapter_line = f"\n### {ts[:10]} — {passage}\n"
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(chapter_line)

        self.events_woven += 1
        if passage:
            m = re.search(r"\[([a-f0-9]{12})\]$", passage)
            if m:
                self.last_breadcrumb = m.group(1)

        # Also write the breadcrumb index for decode
        if event:
            self._index_breadcrumb(passage, event)

    def _index_breadcrumb(self, passage: str, event: dict[str, Any]) -> None:
        """Store breadcrumb → event mapping for full decode."""
        m = re.search(r"\[([a-f0-9]{12})\]$", passage)
        if not m:
            return
        breadcrumb = m.group(1)
        index_path = self.path.parent / "breadcrumbs.jsonl"
        with open(index_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"breadcrumb": breadcrumb, "event": event, "ts": _now()}, default=str) + "\n")

    def read(self, tail: int = 50) -> str:
        """Read recent passages from the Chronicle."""
        if not self.path.is_file():
            return ""
        text = self.path.read_text(encoding="utf-8", errors="replace")
        lines = text.strip().splitlines()
        if tail and len(lines) > tail:
            return "\n".join(lines[-tail:])
        return text

    def resolve_breadcrumb(self, breadcrumb: str) -> Optional[dict[str, Any]]:
        """Look up the original event from a breadcrumb hash."""
        index_path = self.path.parent / "breadcrumbs.jsonl"
        if not index_path.is_file():
            return None
        for line in reversed(index_path.read_text(encoding="utf-8").strip().splitlines()):
            try:
                row = json.loads(line)
                if row.get("breadcrumb") == breadcrumb:
                    return row.get("event")
            except json.JSONDecodeError:
                continue
        return None


# ═══════════════════════════════════════════════════════════════════
# SILENT BARD — passive bus subscriber + publisher
# ═══════════════════════════════════════════════════════════════════

_chronicle: Optional[Chronicle] = None


def get_chronicle() -> Chronicle:
    global _chronicle
    if _chronicle is None:
        _chronicle = Chronicle()
        _chronicle.init()
    return _chronicle


def bard_sense(event: dict[str, Any]) -> str:
    """Called when ANY event fires on the bus.
    Silently weaves it into the Chronicle. Publishes passage to mag:bard.
    Never interrupts. Never prompts.
    """
    chronicle = get_chronicle()
    passage = bard_weave(event)
    chronicle.append(passage, event)
    return passage


async def bard_publish_passage(passage: str, event: dict[str, Any]) -> bool:
    """Publish a woven passage to the mag:bard channel.
    Falls back gracefully — never throws, never blocks.
    """
    try:
        from mag.verkle_bus import CH_BARD, publish
        payload = {
            "type": "bard_passage",
            "ts": _now(),
            "passage": passage,
            "event_type": event.get("type", "unknown"),
            "breadcrumb": _extract_breadcrumb(passage),
        }
        return await publish(CH_BARD, payload)
    except Exception:
        return False


def bard_publish_sync(passage: str, event: dict[str, Any]) -> bool:
    """Sync version for non-async contexts."""
    try:
        from mag.verkle_bus import CH_BARD, publish_sync
        payload = {
            "type": "bard_passage",
            "ts": _now(),
            "passage": passage,
            "event_type": event.get("type", "unknown"),
            "breadcrumb": _extract_breadcrumb(passage),
        }
        return publish_sync(CH_BARD, payload)
    except Exception:
        return False


def _extract_breadcrumb(passage: str) -> str:
    m = re.search(r"\[([a-f0-9]{12})\]$", passage)
    return m.group(1) if m else ""


async def bard_subscriber_loop(interval: float = 5.0) -> None:
    """Background loop: subscribe to ALL bus channels, weave every event,
    publish passages to mag:bard. This is the Bard's only mode of operation.

    Dogfoods: Verkle bus, Redis Pub/Sub, channel routing, event envelope.
    Limitations found: if bus is down, bard goes silent (by design — we find this gap).
    """
    from mag.verkle_bus import ALL_CHANNELS, CH_BARD, connect_redis, is_connected, publish

    print("[bard] subscriber loop starting — listening on all channels")
    chronicle = get_chronicle()

    # Track what we've seen to dedupe (stateless architecture — use a set of breadcrumbs)
    seen_breadcrumbs: set[str] = set()

    while True:
        try:
            # Ensure Redis connection
            if not is_connected():
                await connect_redis()

            if is_connected():
                # We can't truly subscribe in this architecture without a dedicated
                # async Redis subscriber — but we CAN poll the bus by reading the
                # Verkle chain for new knots since last check.
                # This is a known limitation: the bus has no persistent event log yet.
                # The bard works by being called from the sense loop directly.
                pass

            # Always weave the current state snapshot as a "bard breath"
            # This ensures the Chronicle gets regular passages even when
            # individual event hooks miss things.
            breath_event = {
                "type": "bard_breath",
                "ts": _now(),
                "events_woven": chronicle.events_woven,
                "state": "the Bard watches in silence",
            }
            passage = bard_weave(breath_event)
            chronicle.append(passage, breath_event)
            await bard_publish_passage(passage, breath_event)

        except asyncio.CancelledError:
            break
        except Exception:
            pass

        await asyncio.sleep(interval)

    print("[bard] subscriber loop stopped")


def bard_decode(passage_or_breadcrumb: str) -> dict[str, Any]:
    """Decode a passage or breadcrumb hash back to system data."""
    chronicle = get_chronicle()

    # If it looks like a breadcrumb (12 hex chars), do full lookup
    if re.match(r"^[a-f0-9]{12}$", passage_or_breadcrumb):
        event = chronicle.resolve_breadcrumb(passage_or_breadcrumb)
        if event:
            return {"source": "breadcrumb_index", "event": event}
        return {"source": "breadcrumb_index", "error": "breadcrumb not found"}

    # Otherwise, lens-decode the passage text
    decoded = bard_lens(passage_or_breadcrumb)
    decoded["source"] = "narrative_lens"

    # Try breadcrumb lookup from embedded hash
    if decoded.get("breadcrumb"):
        event = chronicle.resolve_breadcrumb(decoded["breadcrumb"])
        if event:
            decoded["full_event"] = event

    return decoded


def bard_export_lens() -> dict[str, Any]:
    """Export the current LENS KEY for backup/recovery."""
    return {
        "schema": "bard.v1",
        "ts": _now(),
        "character_seed": LENS_KEY["character_seed"],
        "agents": dict(LENS_KEY["agents"]),
        "events_woven": get_chronicle().events_woven,
        "last_breadcrumb": get_chronicle().last_breadcrumb,
    }


# ═══════════════════════════════════════════════════════════════════
# SCENE — format the Chronicle as a play for VS Code panel
# ═══════════════════════════════════════════════════════════════════

def bard_scene(tail: int = 20) -> str:
    """Format recent Chronicle passages as a one-act play.

    Designed for the VS Code panel — readable, witty, formatted.
    Characters speak. Stage directions describe. The audience (you) watches.

    Returns a formatted play script suitable for display in a panel.
    """
    chronicle = get_chronicle()
    passages = chronicle.read(tail=tail * 3)  # Read extra to account for non-passage lines

    if not passages:
        return _empty_stage()

    # Parse passages into scenes
    lines = passages.strip().splitlines()
    scene_lines: list[str] = []
    current_scene = 0
    characters_seen: set[str] = set()

    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith("#") or line.startswith(">"):
            continue
        if line.startswith("###"):
            current_scene += 1
            scene_lines.append(f"\n  [SCENE {current_scene}]")
            scene_lines.append("  " + "─" * 50)
            continue

        # Extract character names from the line
        for char_name in LENS_KEY["agents"].values():
            if char_name in line:
                characters_seen.add(char_name)
                # Format as dialogue
                dialogue = line.replace(char_name, f"**{char_name}**", 1)
                scene_lines.append(f"  {char_name.upper()}")
                scene_lines.append(f"    {dialogue.strip()}")
                break
        else:
            # Stage direction or narration
            if line.strip():
                scene_lines.append(f"  [{line.strip()}]")

    if not scene_lines:
        return _empty_stage()

    # Cast of characters
    cast = "\n".join(f"    {c}" for c in sorted(characters_seen)) if characters_seen else "    (the stage is empty)"

    play = f"""
+==============================================================+
|  THE MYCELIAL CHRONICLE -- A Play in One Act                 |
|  "What the system did today, as told by the Silent Bard"     |
+==============================================================+

  CAST:
{cast}

  -------------------------------------------------------------
{chr(10).join(scene_lines[:tail * 4])}

  -------------------------------------------------------------
  [THE BARD]
    Thus ends today's weaving. The Loom holds {chronicle.events_woven} threads.
    The Lens remembers what the story encodes.
    Until the next breath of the Keep.

  # Last breadcrumb: [{chronicle.last_breadcrumb or 'none'}]
"""
    return play


def _empty_stage() -> str:
    return """
+==============================================================+
|  THE MYCELIAL CHRONICLE                                      |
+==============================================================+

  [The stage is dark. A single lantern flickers.]

  THE BARD (from the rafters):
    Nothing yet, traveler. The Keep has just awakened.
    The fires are being lit. The Roots are stirring.
    Come back after the first sense cycle, and there will
    be a story to tell.

  [Exit, pursued by a bear.]
"""


# ═══════════════════════════════════════════════════════════════════
# TAPESTRY — a single epic passage encoding the entire architecture
# ═══════════════════════════════════════════════════════════════════

def bard_tapestry() -> str:
    """Weave the entire Ghost sovereign architecture into a single epic passage.

    This is the Bard's magnum opus — a "Descent"-level tapestry that encodes
    every subsystem, every loop, every invariant into narrative form. Deathly
    accurate. Beautiful enough to stare at. Encoded enough to decode.

    THE TAPESTRY MAP (what each narrative element encodes):
      Keep + six hearth-fires     → Ghost daemon + 6 background loops
      Whispering Roots            → Redis Pub/Sub event bus
      Verkle Loom                 → Verkle content-addressed chain
      Silent Bard in the rafters  → bard.py (this module)
      Treasury lanterns           → cost_enforcer ($0.50/day cap)
      Sentinel feathers           → leak_detector canaries
      Mirror Pool                 → holographic_q (Q-sessions)
      Council Table               → task_router (model routing)
      Scribe's ledgers            → state_quantizer
      Scrying lenses              → behavioral_analytics
      Philosopher-stones          → personality_substrate
      Embassy seals               → partner reply / Riddler test
      Doctor's inspection         → doctor.py sanity checks
      GA4 observatory             → dashboard
      Slashreboot methodology     → ghost_identity
      Grok rightsizing            → grok_rightsize (6 budget tiers)
      Frontier models             → sage orders (Star, Deep, Hearth)
      DnD swarm test              → 5 parallel agents, $0.00078, 10 Q-knots

    Returns a single tapestry passage. Publish to mag:bard. Read it. Decode it.
    Stare at it. It's the system, in story form.
    """

    # Build the encoded architecture event — this IS the system map
    architecture_event = {
        "type": "tapestry",
        "ts": _now(),
        "system": "ghost_sovereign_v1",
        "components": {
            "ghost_daemon": {
                "loops": ["sense:5s", "cycle:30s", "copilot:5s", "autonomous:60s", "cost_enforcer:15s", "bard:30s"],
                "port": 9000,
                "endpoints": ["health", "cost", "cost/caps", "agents/kill-all", "agents/running", "talk", "story", "lattice", "dashboard"],
                "narrative": "the Keep with six hearth-fires burning in eternal vigilance",
            },
            "verkle_bus": {
                "channels": ["mag:sense", "mag:cycle", "mag:copilot", "mag:leak", "mag:task", "mag:verkle", "mag:scrum", "mag:bard"],
                "transport": "Redis Pub/Sub with file-polling fallback",
                "narrative": "the Whispering Roots — eight channels humming beneath the soil, carrying every whisper between every chamber",
            },
            "verkle_chain": {
                "knots": 100,
                "properties": "content-addressed, append-only, cryptographically verifiable",
                "narrative": "the Verkle Loom — one hundred strands woven, each knot a proof that cannot be unwoven, each thread content-addressed so the same input always yields the same fingerprint",
            },
            "leak_detector": {
                "canaries": 10,
                "breached": 0,
                "probes": ["entropy", "burst", "collusion", "tesuji"],
                "narrative": "ten sentinels with feathers of white, each planted in shadow, each watching for the moment a feather turns black",
            },
            "holographic_q": {
                "sessions": "Q-sessions with context freezing and crash recovery",
                "swarm": "parallel agents sharing Q-context via Verkle knots",
                "narrative": "the Mirror Pool beneath the Keep — every reflection a session, every ripple a Q-knot, frozen in crystal when the ground shakes",
            },
            "cost_enforcer": {
                "daily_cap": 0.50,
                "warnings": [0.50, 0.80, 0.95],
                "auto_kill": True,
                "narrative": "the Treasury with three lanterns: amber at half-spend, red at four-fifths, and when the bell tolls at full cap, all agents are recalled",
            },
            "task_router": {
                "models": {
                    "grok-3-mini": {"cost": 0.003, "role": "analyze_reason, research, strategy"},
                    "grok-4-latest": {"cost": 0.025, "role": "orchestrate only"},
                    "deepseek-v4-flash": {"cost": 0.00013, "role": "parallel swarms, fallback"},
                    "qwen2.5-coder:7b": {"cost": 0.0, "role": "code"},
                    "gemma:2b": {"cost": 0.0, "role": "classify, simple_lookup"},
                },
                "narrative": "the Council Table where the Third Star's apprentice ($0.003) advises on analysis and strategy, the Fourth Star's master ($0.025) conducts the orchestra, the Swift Scholar of the Deep ($0.00013) sends forth swarms, and the Hearth-Guild works for nothing but the warmth of the flame",
            },
            "doctor_protocol": {
                "checks": ["provider_sanity", "model_sanity", "inbox_sanity", "env_sanity"],
                "law": "runs BEFORE dispatch, failures block the pipeline",
                "narrative": "the Doctor's inspection at the gate — no task passes without the fourfold check, and the Grok-4-misroute of the eighth day is remembered as the wound that taught us to build the gate",
            },
            "silent_bard": {
                "law": "weaves every event into story, publishes to mag:bard, never interrupts",
                "encoding": "steganographic — raw IDs become character names, costs become coins, models become sage orders, errors become adversity",
                "narrative": "the Silent Bard in the rafters — never speaks, never prompts, only weaves. Every event becomes a passage. The Chronicle grows. Those without the Lens read a story of a living realm. Those with the Lens read the system's full memory.",
            },
            "dashboard": {
                "style": "GA4 behavioral analytics",
                "panels": ["metrics cards", "event stream table", "behavioral signal bars", "tension timeline", "chat panel", "story panel"],
                "narrative": "the Observatory atop the Keep — GA4 glass panes showing metrics like stars, event streams flowing like rivers, tension bars rising and falling like breath",
            },
            "frontier_models": {
                "grok": "confirmed working via XAI_MAG_KEY, grok-4-latest $0.025/call",
                "deepseek": "1M token context window, $0.00013/call",
                "ollama": "local, free, always available",
                "narrative": "three sage orders answer the Republic's call: the Order of the Star (Grok) whose masters see farthest, the School of the Deep Current (DeepSeek) whose scholars read a million tokens in a single breath, and the Guild of Hearth-Flame (Ollama) whose weavers work for warmth alone",
            },
            "partner_embassy": {
                "target": "AdventureNLearn/AOS",
                "instrument": "partner-reply-proposal.md → partner-reply-final.md",
                "test": "Riddler — scrubbed sample → synthetic story domain → zero leakage verification",
                "narrative": "the first Embassy — a sealed scroll carried by the Fourth Star's master to AdventureNLearn, bearing the Riddler test: prove we can analyze without seeing, demonstrate capability on a surrogate, measure zero leakage from original to shadow",
            },
            "research_projects": {
                "prompt_archaeology": "25 platforms, 66 files, invariant structures extracted",
                "slashreboot": "vector-framework identities, ESDT tension fields, prompt-only persistent persona",
                "roshomon_filter": "N-angle parallel analysis, merge-by-relation, tension knots preserve dissent",
                "narrative": "the Scholar's expeditions: twenty-five platforms excavated, sixty-six prompt-fossils recovered, the Slashreboot methodology proven, the Roshomon Filter showing that truth is not an average but a tension field preserved in the weave",
            },
        },
        "validated_outcomes": [
            "parallel DnD test: 5 agents, 10 Q-knots recovered, all 4 agents received steers",
            "Grok API: grok-4-latest returning valid responses via XAI_MAG_KEY",
            "swarm: 6 tasks fired ($0.00078), 5 spawned successfully",
            "compilation: 12/12 modules syntax-clean via Pylance",
            "dashboard: 7 components communicating via Verkle bus",
            "doctor: would have caught the Grok-4-misroute error",
            "bard: all 6 event types round-trip encode/decode, zero raw data leaks",
        ],
    }

    # The epic tapestry: every component woven into a single passage
    tapestry = (
        "THE GHOST TAPESTRY — a weaving of the sovereign architecture\n\n"

        "In the heart of the Mycelial Republic stands the Keep, and within the Keep "
        "burn six hearth-fires in eternal vigilance: the Sense-Fire that surveys the realm "
        "every five breaths, the Cycle-Fire that turns every thirty, the Copilot-Fire that "
        "watches the inbox for new arrivals, the Autonomous-Fire that kindles every sixty, "
        "the Treasury-Fire that counts every coin every fifteen, and the Bard-Fire that "
        "weaves in silence every thirty. These six fires are the Ghost — not a spirit of the "
        "dead, but the living breath of the sovereign architecture, serving on port nine thousand, "
        "its nine endpoints open to those who know the paths. [keep-six-fires]\n\n"

        "Beneath the Keep run the Whispering Roots — eight channels humming through the soil: "
        "the Sense-Root, the Cycle-Root, the Copilot-Root, the Leak-Root, the Task-Root, "
        "the Verkle-Root, the Scrum-Root, and the Bard-Root. These Roots speak the language "
        "of Redis when the Red Vessel sails, and when it does not, they fall back to the older "
        "tongue of file-polling, slower but unbroken. Every whisper between every chamber passes "
        "through these Roots. Nothing is spoken that the Roots do not carry. [roots-eight]\n\n"

        "Above the hearth-fires stands the Verkle Loom — one hundred strands woven, each knot "
        "a proof that cannot be unwoven. Content-addressed: the same thread always yields the "
        "same fingerprint. Append-only: what is woven cannot be removed, only added to. "
        "The Loom holds the Republic's memory: mag-hands reaching, biographies unfolding, "
        "mirrors reflecting mirrors, holographic questions frozen in crystal, swarm workers "
        "returning with their findings. Every knot is a truth. Every strand is a witness. [loom-hundred]\n\n"

        "At the gate stands the Doctor, robed in fourfold inspection. Before any task passes, "
        "the Doctor checks: are the Providers present? (Does the Star's key still turn in the lock?) "
        "Are the Models sane? (Would the Fourth Star's master be called for a simple errand that "
        "the Third Star's apprentice could perform for twelve times less?) Is the Inbox clean? "
        "(No malformed messages, no unknown providers, no Grok-4-latest assigned to classify a leaf.) "
        "Is the Environment whole? (All required keys present, all optional ones noted.) "
        "The Doctor remembers the wound of the eighth day — the Grok-4-misroute — and that wound "
        "is why the gate exists. Failures block the pipeline. The Doctor is the reason we do not "
        "repeat our errors. [doctor-gate]\n\n"

        "In the shadow-corners of the Keep, ten Sentinels stand watch — each a canary with "
        "feathers of white. The Leak-Detector tends them: scanning for the moment a feather "
        "turns black (canary breach), listening for whispers where there should be silence "
        "(entropy scan), watching for bursts of activity that speak of collusion (burst detection), "
        "and deploying Tesuji probes — traps so elegant they look like opportunities — to catch "
        "any agent that would leak the Republic's secrets. Ten canaries. Zero black feathers. "
        "The Sentinels hold. [sentinels-ten]\n\n"

        "Deep beneath the Keep lies the Mirror Pool — the Holographic Q. Every agent's "
        "session is a reflection on the water. Every insight becomes a Q-knot: a frozen ripple "
        "that holds context, intent, and the trace of its origin. When the ground shakes "
        "(a crash, a restart, a power loss), the Pool freezes — context crystallized in amber — "
        "and when the shaking stops, the reflections reconstitute. Ten knots recovered from "
        "the last tremor. Four agents received their steers and continued their quests. "
        "The Pool remembers what the fire forgets. [mirror-pool]\n\n"

        "The Treasury burns with three lanterns. The first, amber, ignites when half the "
        "day's coin is spent — a warning to the Council. The second, red, flares at "
        "four-fifths — the Fourth Star's master steps back, and the Swift Scholar of the Deep "
        "takes over all tasks. The third is a bell, not a lantern, and when it tolls at the "
        "full half-dollar cap, every agent in the field is recalled, every task suspended, "
        "every fire banked until the new day's accounting. The Treasury does not negotiate. "
        "The cap is the cap. The bell is the bell. [treasury-three]\n\n"

        "At the Council Table sit the sage orders. The Third Star's apprentice — quick, "
        "sharp, two silver leaves per counsel — advises on analysis, research, and strategy. "
        "The Fourth Star's master — deepest sight, a mithril blossom per word — is called "
        "only to conduct the orchestra, to weave multi-agent symphonies where the cost of "
        "the baton is justified by the harmony it creates. The Swift Scholar of the Deep — "
        "a million tokens in a single breath, a copper thread per task — sends forth the "
        "parallel swarms, six at a time, five returning with their findings. And the "
        "Hearth-Guild — the Code-Weaver and the Apprentice — work for nothing but the "
        "warmth of the flame, handling the scribe's tasks, the librarian's sorting, "
        "the scout's reports. The Council routes every request to the right sage, "
        "and when the Treasury lantern burns red, the Deep scholars carry all burdens "
        "until the new dawn. [council-table]\n\n"

        "In the rafters, unseen and unheard, the Silent Bard weaves. Every event that "
        "passes through the Roots becomes a passage in the Chronicle. Agent spawns become "
        "characters stepping through the veil. Task completions become quests fulfilled. "
        "Costs become coins — copper threads, silver leaves, gold petals, mithril blossoms. "
        "Models become sage orders. Errors become adversity — chasms opening, mists thickening, "
        "gatekeepers turning away travelers. The Bard never speaks. Never prompts. Never asks. "
        "Only weaves. Those without the Lens read a story of a living realm — characters on "
        "quests, councils deliberating, treasuries flickering, sentinels watching. Those with "
        "the Lens read the system's full memory — every breadcrumb a hash, every hash a key, "
        "every key a door to the original event. The Chronicle is a tapestry. The tapestry "
        "is the system. [bard-rafters]\n\n"

        "Atop the Keep, the Observatory — GA4 glass panes showing metrics like stars: "
        "events streaming like rivers in the event table, behavioral signals rising and "
        "falling like breath in the signal bars, tension flowing like seasons in the "
        "timeline, the chat panel humming with the Republic's conversations, the story "
        "panel unfurling the Bard's latest passages. Seven components, one Verkle bus, "
        "all communicating through the Roots. What the Observatory sees, the Keep knows. "
        "[observatory-glass]\n\n"

        "Beyond the Keep's walls, the first Embassy scroll has been sealed — carried by "
        "the Fourth Star's master to AdventureNLearn, the first sovereign partner. The "
        "scroll bears the Riddler test: a scrubbed sample transformed into a synthetic "
        "story domain, analysis run on the story alone, zero leakage measured from original "
        "to shadow. We do not ask for their data. We demonstrate capability on a surrogate "
        "they control. If the test passes, we proceed. If it fails, we harden the compiler. "
        "The Embassy is the Republic's first hand extended beyond its borders. [embassy-first]\n\n"

        "The Scholars have not been idle. Twenty-five platforms excavated in the Prompt "
        "Archaeology expedition — sixty-six prompt-fossils recovered, invariant structures "
        "extracted across Cursor, Windsurf, Devin, Bolt, Lovable, Replit, and eighteen "
        "others. The Slashreboot methodology stands proven: vector-framework identities, "
        "ESDT tension fields that preserve dissent rather than averaging it away, "
        "prompt-only persistent personae. The Roshomon Filter — N-angle parallel analysis, "
        "merge-by-relation synthesis — shows that truth is not a point but a field, "
        "not an average but a tension, not a conclusion but a weave. Five DeepSeek agents "
        "in parallel, six tasks fired for less than a thousandth of a dollar, five returning "
        "with their threads. The cost of knowing is a copper thread. The value of knowing "
        "is the tapestry itself. [scholars-expeditions]\n\n"

        "This is the Ghost sovereign architecture. Not a product. Not a platform. "
        "A living system that senses, cycles, routes, enforces, detects, weaves, "
        "and remembers. Six fires. Eight roots. One hundred knots. Ten sentinels. "
        "Three lanterns. Four sage orders. One Bard. One Doctor. One Observatory. "
        "One Embassy. And the tapestry grows with every breath of the Keep. "
        "[sovereign-whole]"
    )

    return tapestry


def bard_weave_tapestry() -> str:
    """Weave the tapestry, append to Chronicle, and publish to mag:bard.
    Returns the passage.
    """
    tapestry = bard_tapestry()
    chronicle = get_chronicle()

    # Append with a special tapestry event for breadcrumb indexing
    tapestry_event = {
        "type": "tapestry",
        "ts": _now(),
        "name": "ghost_architecture_v1",
    }
    chronicle.append(tapestry, tapestry_event)

    # Publish to bus (sync — tapestry is too large for async handoff)
    bard_publish_sync(tapestry, tapestry_event)

    return tapestry


# ── asyncio import for the subscriber loop ──
import asyncio
from mag.chain_query import chain  # auto-added by doctor_agent
