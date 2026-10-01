"""Exit Dialogue — Grok↔DeepSeek research process on task completion.

When any significant task completes, two models spawn a research dialogue:
  - Grok-3-mini: analysis, synthesis, "what did we learn?"
  - DeepSeek-v4-flash: pattern extraction, "what does this remind us of?"

This is the DEFAULT EXIT — every task completion triggers it unless suppressed.
Cost: $0.00313 total ($0.003 Grok + $0.00013 DeepSeek). Rightsized.

The dialogue is:
  1. Honest — no architecture-washing, no module-counting
  2. Behavioral — uses Bernays (propaganda/behavior engineering) and Jung (archetypes) lenses
  3. Actionable — produces a "fold to ledger" recommendation
  4. Vague enough — no secrets, no raw data, no operational details in the output

SCHEMA: exit_dialogue.v1
LAW: Every task exit triggers this unless explicitly suppressed.
LAW: Grok analyzes. DeepSeek patterns. Human decides.
"""

from __future__ import annotations

import json
import hashlib
from mag.chain_query import chain  # auto-added by doctor_agent
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
# LENSES — how we analyze what happened
# ═══════════════════════════════════════════════════════════════════

JUNG_LENS = """
Analyze through Jung's archetypal lens:
- What archetype was active? (Magician, Sovereign, Warrior, Sage, Trickster, etc.)
- Was there a shadow projection? (What did we avoid seeing?)
- Was there synchronicity? (Meaningful coincidence — two independent patterns converging)
- What was the individuation movement? (Did the system become more itself?)

Keep it honest. No flattery. If the Shadow was laziness or grandiosity, say so.
"""

BERNAYS_LENS = """
Analyze through Bernays' propaganda/behavior lens:
- What behavior was being engineered? (What did we want to happen?)
- Who was the invisible governor? (What force actually shaped the outcome?)
- Was consent manufactured or genuine? (Did we choose, or were we routed?)
- What's the "engineering of consent" pattern here?

Keep it clinical. No moralizing. Just describe the behavior mechanics at work.
"""

RESEARCH_EXIT_PROMPT = """
You are analyzing a completed task in the Mycelial Republic sovereign architecture.
Be HONEST. Be VAGUE enough to protect operational details. Base everything in actual
observations, not architecture-speak.

TASK CONTEXT:
{task_context}

WHAT ACTUALLY HAPPENED:
{what_happened}

GROK ANALYSIS (this is your section — fill it):
1. What did we actually learn? (Not what we built. What we learned.)
2. What did we avoid? (The shadow — the thing we didn't want to see.)
3. Was the model routing correct? (Did we use the right model for the right task?)
4. What pattern repeated? (Have we seen this before in this session?)
5. What's the one thing we should do differently next time?

DEEPSEEK PATTERNS (extract these):
1. Cross-session pattern: Does this remind you of any previous task or session?
2. Behavioral fingerprint: What operator behavior does this reveal?
3. Emergent property: What emerged that wasn't planned?
4. Cache-miss indicator: What did we query that was already known?

FOLD RECOMMENDATION:
- [ ] Fold to skill_ledger (a reusable pattern was discovered)
- [ ] Fold to pro_library (a compoundable vector was validated)
- [ ] Fold to FKB (a failure pattern worth remembering)
- [ ] Just record and move on (one-off, no reusable signal)
"""


# ═══════════════════════════════════════════════════════════════════
# EXIT DIALOGUE ENGINE
# ═══════════════════════════════════════════════════════════════════

@dataclass
class ExitDialogue:
    """A Grok↔DeepSeek research dialogue on task completion."""
    dialogue_id: str
    task_id: str
    task_type: str
    what_happened: str           # Honest, plain-English account
    task_context: str            # What we were trying to do
    grok_analysis: dict[str, str] = field(default_factory=dict)
    deepseek_patterns: dict[str, str] = field(default_factory=dict)
    fold_recommendations: list[str] = field(default_factory=list)
    jung_archetype: str = ""
    bernays_mechanic: str = ""
    ts: str = field(default_factory=_now)

    def to_ledger_entry(self) -> dict[str, Any]:
        """Format for folding into the skill_ledger or FKB."""
        return {
            "schema": "exit_dialogue.v1",
            "dialogue_id": self.dialogue_id,
            "task_id": self.task_id,
            "ts": self.ts,
            "task_type": self.task_type,
            "what_happened": self.what_happened[:200],
            "jung_archetype": self.jung_archetype,
            "bernays_mechanic": self.bernays_mechanic,
            "fold": self.fold_recommendations,
            "grok_synthesis": self.grok_analysis.get("what_learned", "")[:200],
            "deepseek_pattern": self.deepseek_patterns.get("cross_session", "")[:200],
        }

    @staticmethod
    def generate(task_id: str, task_type: str, what_happened: str, task_context: str = "") -> ExitDialogue:
        """Create an exit dialogue. The actual Grok/DeepSeek calls happen
        when the dialogue is processed through the copilot inbox."""
        dialogue_id = hashlib.sha256(f"{task_id}:exit:{_now()}".encode()).hexdigest()[:16]
        return ExitDialogue(
            dialogue_id=dialogue_id,
            task_id=task_id,
            task_type=task_type,
            what_happened=what_happened,
            task_context=task_context,
        )


# ═══════════════════════════════════════════════════════════════════
# QUEUE — inject exit dialogue into copilot inbox for processing
# ═══════════════════════════════════════════════════════════════════

def queue_exit_dialogue(
    task_id: str,
    task_type: str,
    what_happened: str,
    task_context: str = "",
    suppress: bool = False,
) -> Optional[str]:
    """Queue a Grok↔DeepSeek exit dialogue for processing.

    Args:
        task_id: The task that just completed
        task_type: classify / analyze_reason / research / strategy / orchestrate / code
        what_happened: Honest account. No architecture-speak. "We tried X. Y happened. Cost $Z."
        task_context: What we were trying to do. "Building a sovereign agent that..."
        suppress: If True, skip the dialogue (for trivial tasks)

    Returns:
        dialogue_id if queued, None if suppressed
    """
    if suppress:
        return None

    dialogue = ExitDialogue.generate(task_id, task_type, what_happened, task_context)

    # Build the research prompt that Grok-3-mini will process
    grok_prompt = RESEARCH_EXIT_PROMPT.format(
        task_context=task_context or "(no context provided — analyze the task itself)",
        what_happened=what_happened,
    )

    # Inject TWO inbox tasks: one for Grok analysis, one for DeepSeek patterns
    inbox_path = ROOT / "memory" / "copilot" / "inbox.jsonl"

    grok_task = json.dumps({
        "id": f"exit-grok-{dialogue.dialogue_id}",
        "action": "exec",
        "goal": grok_prompt + "\n\nOUTPUT: Write your analysis as JSON to memory/copilot/outbox/exit-grok-{did}.json with keys: what_learned, what_avoided, routing_correct (bool), pattern_repeated, do_differently, jung_archetype, bernays_mechanic.".replace("{did}", dialogue.dialogue_id),
        "provider": "xai",
        "model": "grok-3-mini",
        "timeout_s": 120,
        "ts": _now(),
        "source": "exit-dialogue",
    })

    ds_task = json.dumps({
        "id": f"exit-ds-{dialogue.dialogue_id}",
        "action": "exec",
        "goal": f"PATTERN EXTRACTION. Task completed: {what_happened[:300]}. Extract: 1) cross-session pattern (what does this remind you of?), 2) behavioral fingerprint (what operator behavior does this reveal?), 3) emergent property (what emerged unplanned?), 4) cache-miss indicator (what was queried that was already known?). Write JSON to memory/copilot/outbox/exit-ds-{dialogue.dialogue_id}.json with those four keys. Be honest. Be vague enough to protect operational details.",
        "provider": "deepseek",
        "model": "deepseek-v4-flash",
        "timeout_s": 120,
        "ts": _now(),
        "source": "exit-dialogue",
    })

    with open(inbox_path, "a", encoding="utf-8") as f:
        f.write(grok_task + "\n")
        f.write(ds_task + "\n")

    return dialogue.dialogue_id


# ═══════════════════════════════════════════════════════════════════
# FOLD TO LEDGER — after both models respond, fold the synthesis
# ═══════════════════════════════════════════════════════════════════

def fold_exit_to_ledger(dialogue_id: str) -> dict[str, Any]:
    """After Grok and DeepSeek have responded, fold the synthesis into the ledger.

    Reads the outbox files, merges the analyses, and writes to skill_ledger.
    """
    outbox = ROOT / "memory" / "copilot" / "outbox"
    grok_file = outbox / f"exit-grok-{dialogue_id}.json"
    ds_file = outbox / f"exit-ds-{dialogue_id}.json"

    grok_data = {}
    ds_data = {}

    if grok_file.is_file():
        try:
            grok_data = json.loads(grok_file.read_text())
        except (json.JSONDecodeError, OSError):
            pass

    if ds_file.is_file():
        try:
            ds_data = json.loads(ds_file.read_text())
        except (json.JSONDecodeError, OSError):
            pass

    # Merge into a synthesis
    synthesis = {
        "schema": "exit-synthesis.v1",
        "dialogue_id": dialogue_id,
        "ts": _now(),
        "grok": grok_data,
        "deepseek": ds_data,
        "merged_insight": _merge_insights(grok_data, ds_data),
        "jung_archetype": grok_data.get("jung_archetype", "unknown"),
        "bernays_mechanic": grok_data.get("bernays_mechanic", "unknown"),
        "fold_targets": _determine_folds(grok_data, ds_data),
    }

    # Write to skill_ledger
    ledger_path = ROOT / "memory" / "ledger" / "exit_dialogues.jsonl"
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with open(ledger_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(synthesis, default=str) + "\n")

    return synthesis


def _merge_insights(grok: dict, ds: dict) -> str:
    """Merge Grok analysis and DeepSeek patterns into a single insight."""
    parts = []

    grok_learned = grok.get("what_learned", "")
    if grok_learned:
        parts.append(f"Grok: {grok_learned[:200]}")

    ds_pattern = ds.get("cross_session", "") or ds.get("behavioral_fingerprint", "")
    if ds_pattern:
        parts.append(f"DeepSeek: {ds_pattern[:200]}")

    if not parts:
        return "No insights merged."

    return " | ".join(parts)


def _determine_folds(grok: dict, ds: dict) -> list[str]:
    """Determine where this insight should be folded."""
    folds = []

    # If Grok found a reusable pattern → skill_ledger
    if grok.get("pattern_repeated"):
        folds.append("skill_ledger")

    # If DeepSeek found an emergent property → pro_library
    if ds.get("emergent_property"):
        folds.append("pro_library")

    # If routing was wrong → FKB
    if grok.get("routing_correct") is False:
        folds.append("fkb")

    # If Grok suggests doing something differently → improve
    if grok.get("do_differently"):
        folds.append("improve_loop")

    if not folds:
        folds.append("record_only")

    return folds


# ═══════════════════════════════════════════════════════════════════
# AUTO-EXIT HOOK — call this when any task completes
# ═══════════════════════════════════════════════════════════════════

def on_task_exit(
    task_id: str,
    task_type: str,
    what_happened: str,
    task_context: str = "",
    cost: float = 0.0,
    suppress: bool = False,
) -> Optional[str]:
    """Called automatically when any significant task completes.

    Determines if an exit dialogue is warranted based on:
      - Task type (code/classify are trivial, skip unless $0)
      - Cost (cheap tasks skip unless they produced novel results)
      - Operator override (suppress=True always skips)

    Returns dialogue_id if queued, None if skipped.
    """
    # Skip trivial tasks
    if task_type in ("classify", "simple_lookup") and cost < 0.001:
        return None

    # Skip if suppressed
    if suppress:
        return None

    # Queue the Grok↔DeepSeek exit dialogue
    dialogue_id = queue_exit_dialogue(
        task_id=task_id,
        task_type=task_type,
        what_happened=what_happened,
        task_context=task_context,
    )

    # Log the exit
    log_path = ROOT / "memory" / "runs" / "exit_dialogues.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps({
            "ts": _now(),
            "task_id": task_id,
            "task_type": task_type,
            "dialogue_id": dialogue_id,
            "cost": cost,
            "suppressed": suppress,
        }) + "\n")

    return dialogue_id
