"""Context Checkpoint — escape the context-window lock-in tax.

The Problem:
  You start a conversation with Model A. Every turn adds to the context window.
  Switching to Model B requires re-feeding the ENTIRE history — you're paying
  Model B to re-process every word Model A already said. This is lock-in.
  The context IS the tax.

The Solution:
  Write compressed context checkpoints to the Verkle chain. Each turn writes
  a ~200-token summary + pointer. The next turn reads only the pointer, not
  the full history. Context lives in the chain, not in any model's window.

The Economics:
  Without checkpoints: 10K token context × $0.013/1M = $0.00013/turn (fixed)
  With checkpoints:    200 token pointer × $0.013/1M = $0.0000026/turn
  But the REAL saving: you can switch models freely. Grok-4 for hard turns,
  DeepSeek flash for routine turns, Ollama for classification — without
  losing state or paying the expensive model to re-read history.

SCHEMA: context_checkpoint.v1
LAW: Every turn writes a checkpoint. No orphaned context windows.
LAW: The pointer is the bridge. Reading the pointer restores state.
LAW: Checkpoints are content-addressed. Tampering is detectable.
"""

from __future__ import annotations

import hashlib
import json
import time
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
# CHECKPOINT MODEL
# ═══════════════════════════════════════════════════════════════════

@dataclass
class ContextCheckpoint:
    """One turn's compressed state, stored in the Verkle chain."""

    session_id: str
    turn_number: int
    summary: str              # compressed summary (~200 tokens)
    full_context_hash: str     # SHA256 of the full context (for verification)
    model_used: str            # which model wrote this checkpoint
    model_cost_usd: float      # what that turn cost
    parent_knot_id: str        # pointer to previous checkpoint (linked list)
    verkle_knot_id: str = ""   # filled after writing to chain
    key_decisions: list[str] = field(default_factory=list)
    pending_questions: list[str] = field(default_factory=list)
    state_snapshot: dict[str, Any] = field(default_factory=dict)
    ts: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "context_checkpoint.v1",
            "session_id": self.session_id,
            "turn_number": self.turn_number,
            "summary": self.summary[:500],
            "full_context_hash": self.full_context_hash,
            "model_used": self.model_used,
            "model_cost_usd": round(self.model_cost_usd, 6),
            "parent_knot_id": self.parent_knot_id,
            "verkle_knot_id": self.verkle_knot_id,
            "key_decisions": self.key_decisions,
            "pending_questions": self.pending_questions,
            "state_snapshot": self.state_snapshot,
            "ts": self.ts,
        }

    def to_pointer(self) -> str:
        """Generate a compact pointer string for injection into the next turn's context.

        This is the ~200-token bridge between turns. The next model reads this,
        not the full history.
        """
        parts = [
            f"[CHECKPOINT {self.verkle_knot_id[:8] if self.verkle_knot_id else 'pending'}]",
            f"Session: {self.session_id[:12]} | Turn: {self.turn_number}",
            f"Previous model: {self.model_used} (${self.model_cost_usd:.6f})",
            f"Summary: {self.summary[:300]}",
        ]
        if self.key_decisions:
            parts.append(f"Decisions: {'; '.join(self.key_decisions[:5])}")
        if self.pending_questions:
            parts.append(f"Pending: {'; '.join(self.pending_questions[:3])}")
        parts.append(f"Chain pointer: knot/{self.verkle_knot_id}" if self.verkle_knot_id else "Chain pointer: pending")
        return "\n".join(parts)

    def verify(self, full_context: str) -> bool:
        """Verify this checkpoint matches the full context it claims to represent."""
        computed = hashlib.sha256(full_context.encode()).hexdigest()[:16]
        return computed == self.full_context_hash


# ═══════════════════════════════════════════════════════════════════
# CHECKPOINT ENGINE
# ═══════════════════════════════════════════════════════════════════

class CheckpointEngine:
    """Manages context checkpoints — write, read, switch models."""

    def __init__(self):
        self.checkpoint_dir = ROOT / "memory" / "checkpoints"
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self.active_sessions: dict[str, list[ContextCheckpoint]] = {}

    def checkpoint(
        self,
        session_id: str,
        full_context: str,
        model_used: str,
        model_cost_usd: float = 0.0,
        *,
        key_decisions: list[str] | None = None,
        pending_questions: list[str] | None = None,
        state_snapshot: dict[str, Any] | None = None,
    ) -> ContextCheckpoint:
        """Write a context checkpoint to the Verkle chain.

        Args:
            session_id: Which conversation this belongs to.
            full_context: The FULL context window (we hash it, not store it).
            model_used: Which model processed this turn.
            model_cost_usd: What this turn cost.
            key_decisions: Decisions made this turn (for quick recall).
            pending_questions: Questions that need answers later.
            state_snapshot: Any state variables to preserve.

        Returns:
            ContextCheckpoint with Verkle knot ID for the next turn's pointer.
        """
        # Find turn number
        existing = self._load_session(session_id)
        turn_number = len(existing) + 1
        parent_id = existing[-1].verkle_knot_id if existing else "genesis"

        # Generate summary (compress the context)
        summary = self._summarize(full_context, key_decisions or [])

        # Hash the full context for tamper detection
        full_hash = hashlib.sha256(full_context.encode()).hexdigest()[:16]

        cp = ContextCheckpoint(
            session_id=session_id,
            turn_number=turn_number,
            summary=summary,
            full_context_hash=full_hash,
            model_used=model_used,
            model_cost_usd=model_cost_usd,
            parent_knot_id=parent_id,
            key_decisions=key_decisions or [],
            pending_questions=pending_questions or [],
            state_snapshot=state_snapshot or {},
        )

        # Write to Verkle chain
        knot_id = self._write_to_chain(cp)
        cp.verkle_knot_id = knot_id

        # Save locally for fast lookup
        self._save_checkpoint(cp)
        if session_id not in self.active_sessions:
            self.active_sessions[session_id] = []
        self.active_sessions[session_id].append(cp)

        return cp

    def restore_pointer(self, session_id: str) -> str:
        """Get the latest checkpoint pointer for injection into context.

        Returns a ~200-token string that the next model reads instead of
        the full conversation history.
        """
        existing = self._load_session(session_id)
        if not existing:
            return "[No prior context. This is turn 1.]"

        latest = existing[-1]
        return latest.to_pointer()

    def switch_model(
        self,
        session_id: str,
        full_context: str,
        from_model: str,
        to_model: str,
        to_model_cost: float = 0.0,
    ) -> dict[str, Any]:
        """Switch models mid-conversation without losing state.

        1. Checkpoint current state with the FROM model.
        2. Return the pointer for the TO model to pick up.
        3. The TO model gets a ~200-token pointer instead of full history.

        Returns:
            {"ok": True, "pointer": "...", "checkpoint": ContextCheckpoint,
             "context_saved_tokens": int, "estimated_savings_usd": float}
        """
        # Checkpoint with current model
        old_cost = self._estimate_model_cost(from_model)
        cp = self.checkpoint(
            session_id=session_id,
            full_context=full_context,
            model_used=from_model,
            model_cost_usd=old_cost,
            key_decisions=[f"Switching from {from_model} to {to_model}"],
        )

        # Calculate savings
        full_context_tokens = len(full_context) // 4
        pointer_tokens = len(cp.to_pointer()) // 4
        tokens_saved = full_context_tokens - pointer_tokens

        # If the TO model is cheaper, every future turn saves the difference
        new_cost_per_1m = to_model_cost if to_model_cost > 0 else self._estimate_model_cost(to_model)
        old_cost_per_1m = self._estimate_model_cost(from_model) if from_model != "ollama" else 0.001
        per_turn_savings = (old_cost_per_1m - new_cost_per_1m) * (full_context_tokens / 1_000_000)

        out = {
            "ok": True,
            "pointer": cp.to_pointer(),
            "checkpoint": cp,
            "context_saved_tokens": tokens_saved,
            "from_model": from_model,
            "to_model": to_model,
            "per_turn_savings_usd": round(max(0, per_turn_savings), 6),
            "handoff": "pointer",
            "note": (
                f"Switched from {from_model} to {to_model}. "
                f"Saved {tokens_saved} tokens of context transfer. "
                f"Future turns save ~\/turn "
                f"by not reprocessing history in the expensive model."
            ),
        }
        try:
            from mag.party_subchain import want_full
            if want_full():
                out["handoff"] = "full_context"
                out["full_context"] = full_context
                out["note"] = (
                    f"Switched from {from_model} to {to_model}. "
                    "MAG_FULL_CONTEXT=1: pointer still persisted; window handed the real context."
                )
        except Exception:
            pass
        return out


    def chain_for_session(self, session_id: str) -> list[dict[str, Any]]:
        """Get the full checkpoint chain for a session (linked list)."""
        checkpoints = self._load_session(session_id)
        return [cp.to_dict() for cp in checkpoints]

    def _summarize(self, context: str, decisions: list[str]) -> str:
        """Compress context into a ~200 token summary.

        Uses heuristics: extract last N lines, key decisions, strip boilerplate.
        For production, this would use an LLM call for semantic compression.
        """
        lines = context.strip().splitlines()
        # Take last 15 lines as most recent context
        recent = lines[-15:] if len(lines) > 15 else lines
        recent_text = "\n".join(recent)

        # Truncate to ~800 chars (~200 tokens)
        if len(recent_text) > 800:
            recent_text = recent_text[:800] + "..."

        summary_parts = [recent_text]
        if decisions:
            summary_parts.insert(0, f"Decisions: {'; '.join(decisions[:3])}")

        return "\n".join(summary_parts)

    def _write_to_chain(self, cp: ContextCheckpoint) -> str:
        """Write checkpoint to Verkle chain, return knot ID."""
        try:
            from mag.verkle_bus import publish_sync, CH_VERKLE
            knot_id = f"knot-cp-{cp.session_id[:8]}-{cp.turn_number:04d}-{hashlib.sha256(cp.summary.encode()).hexdigest()[:8]}"
            publish_sync(CH_VERKLE, {
                "type": "context_checkpoint",
                "knot_id": knot_id,
                "ts": cp.ts,
                "data": cp.to_dict(),
            })
            return knot_id
        except Exception:
            # Fallback: local file-based knot ID
            knot_id = f"knot-cp-local-{cp.session_id[:8]}-{cp.turn_number:04d}"
            return knot_id

    def _save_checkpoint(self, cp: ContextCheckpoint):
        """Save checkpoint locally for fast lookup."""
        session_dir = self.checkpoint_dir / cp.session_id[:12]
        session_dir.mkdir(parents=True, exist_ok=True)
        cp_file = session_dir / f"turn_{cp.turn_number:04d}.json"
        try:
            cp_file.write_text(json.dumps(cp.to_dict(), default=str, indent=2), encoding="utf-8")
        except OSError:
            pass

    def _load_session(self, session_id: str) -> list[ContextCheckpoint]:
        """Load all checkpoints for a session."""
        if session_id in self.active_sessions:
            return self.active_sessions[session_id]

        session_dir = self.checkpoint_dir / session_id[:12]
        if not session_dir.is_dir():
            return []

        checkpoints = []
        for cp_file in sorted(session_dir.glob("turn_*.json")):
            try:
                data = json.loads(cp_file.read_text(encoding="utf-8"))
                checkpoints.append(ContextCheckpoint(
                    session_id=data.get("session_id", session_id),
                    turn_number=data.get("turn_number", 0),
                    summary=data.get("summary", ""),
                    full_context_hash=data.get("full_context_hash", ""),
                    model_used=data.get("model_used", "unknown"),
                    model_cost_usd=data.get("model_cost_usd", 0.0),
                    parent_knot_id=data.get("parent_knot_id", ""),
                    verkle_knot_id=data.get("verkle_knot_id", ""),
                    key_decisions=data.get("key_decisions", []),
                    pending_questions=data.get("pending_questions", []),
                    state_snapshot=data.get("state_snapshot", {}),
                    ts=data.get("ts", ""),
                ))
            except (json.JSONDecodeError, KeyError):
                continue

        self.active_sessions[session_id] = checkpoints
        return checkpoints

    @staticmethod
    def _estimate_model_cost(model_name: str) -> float:
        """Estimate per-call cost for a model."""
        costs = {
            "deepseek-v4-flash": 0.00013,
            "deepseek-v4": 0.00040,
            "grok-3-mini": 0.003,
            "grok-4-latest": 0.025,
            "grok-4": 0.025,
            "ollama-qwen2.5-coder": 0.0,
            "ollama-gemma2": 0.0,
        }
        return costs.get(model_name, 0.00013)


# ═══════════════════════════════════════════════════════════════════
# MODEL-SWITCHING ECONOMICS CALCULATOR
# ═══════════════════════════════════════════════════════════════════

def compute_switch_economics(
    context_tokens: int,
    from_model: str,
    to_model: str,
    remaining_turns: int = 10,
) -> dict[str, Any]:
    """Calculate the economics of switching models mid-conversation.

    Without checkpoints: every remaining turn pays the FROM model's rate
    for the full context window (context_tokens × remaining_turns).

    With checkpoints: the switch turn pays a one-time checkpoint cost,
    then remaining turns pay the TO model's rate for only the pointer.
    """
    engine = CheckpointEngine()
    from_cost = engine._estimate_model_cost(from_model)
    to_cost = engine._estimate_model_cost(to_model)

    # Without checkpoints: stay on FROM model for all remaining turns
    stay_cost = from_cost * remaining_turns  # simplified — doesn't account for growing context

    # With checkpoints: one checkpoint turn + remaining turns on TO model
    pointer_tokens = 200  # ~200 tokens for the pointer
    switch_turn_cost = from_cost  # checkpoint turn
    remaining_cost = (pointer_tokens / 1_000_000) * to_cost * 1_000_000 * remaining_turns  # simplified
    switch_cost = switch_turn_cost + (to_cost * remaining_turns)  # rough

    savings = stay_cost - switch_cost

    return {
        "scenario": {
            "context_tokens": context_tokens,
            "from_model": from_model,
            "to_model": to_model,
            "remaining_turns": remaining_turns,
        },
        "without_checkpoints": {
            "strategy": f"Stay on {from_model} for all {remaining_turns} turns",
            "estimated_cost": round(stay_cost, 6),
            "note": "Locked in. Cannot switch without losing context or paying full re-feed.",
        },
        "with_checkpoints": {
            "strategy": f"Checkpoint with {from_model}, continue {remaining_turns} turns on {to_model}",
            "estimated_cost": round(switch_cost, 6),
            "context_per_turn": f"{pointer_tokens} tokens (vs {context_tokens} without checkpoints)",
            "reduction": f"{round((1 - pointer_tokens/context_tokens)*100)}% smaller context",
        },
        "savings": {
            "total": round(savings, 6),
            "per_turn": round(savings / remaining_turns, 6) if remaining_turns > 0 else 0,
            "verdict": (
                "SWITCH: checkpoints make it free to switch models mid-conversation"
                if savings > 0 else
                "STAY: switching costs more than staying (unlikely with our cost spread)"
            ),
        },
    }


# ═══════════════════════════════════════════════════════════════════
# QUICK ACCESS
# ═══════════════════════════════════════════════════════════════════

_ENGINE: Optional[CheckpointEngine] = None


def get_engine() -> CheckpointEngine:
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = CheckpointEngine()
    return _ENGINE


def checkpoint_turn(
    session_id: str,
    full_context: str,
    model_used: str,
    model_cost_usd: float = 0.0,
) -> ContextCheckpoint:
    """Checkpoint the current turn to the Verkle chain."""
    return get_engine().checkpoint(session_id, full_context, model_used, model_cost_usd)


def restore_pointer(session_id: str) -> str:
    """Get the latest checkpoint pointer for the next turn's context."""
    return get_engine().restore_pointer(session_id)


def switch_model(
    session_id: str,
    full_context: str,
    from_model: str,
    to_model: str,
) -> dict[str, Any]:
    """Switch models mid-conversation. Returns pointer for the new model."""
    return get_engine().switch_model(session_id, full_context, from_model, to_model)


def switch_economics(
    context_tokens: int,
    from_model: str,
    to_model: str,
    remaining_turns: int = 10,
) -> dict[str, Any]:
    """Calculate the economics of switching."""
    return compute_switch_economics(context_tokens, from_model, to_model, remaining_turns)
