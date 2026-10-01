"""Copilot Bridge — connect VS Code Copilot conversations to the Ghost stack.

The problem: everything we built today runs inside Ghost on :9000. But THIS
conversation is happening through VS Code Copilot, not Ghost. The modules are
wired to REST endpoints that Copilot never calls.

The bridge: periodically sync Copilot conversation state into Ghost's Verkle
chain, constitutional filter, ledger, and checkpoint system. Now the stack
we built actually sees and tracks the conversation we're having.

SCHEMA: copilot_bridge.v1
LAW: Never intercept or modify Copilot's actual API calls. Read-only sync.
LAW: Sync is best-effort. If the transcript file isn't available, skip.
LAW: Every sync writes a checkpoint, runs constitutional heuristics, updates ledger.
"""

from __future__ import annotations

import json
import os
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
# TRANSCRIPT READER
# ═══════════════════════════════════════════════════════════════════

def find_transcript_path() -> Optional[Path]:
    """Find the current Copilot conversation transcript file.

    VS Code stores transcripts in the workspace storage under
    GitHub.copilot-chat/transcripts/ as JSONL files.
    """
    # Check environment variable set by VS Code
    env_path = os.environ.get("VSCODE_TARGET_SESSION_LOG", "")
    if env_path:
        p = Path(env_path)
        if p.is_file():
            return p

    # Search workspace storage
    code_user = os.environ.get("APPDATA", "")
    if code_user:
        base = Path(code_user) / "Code" / "User" / "workspaceStorage"
        if base.is_dir():
            for ws_dir in base.iterdir():
                transcript_dir = ws_dir / "GitHub.copilot-chat" / "transcripts"
                if transcript_dir.is_dir():
                    # Get the most recent transcript
                    files = sorted(transcript_dir.glob("*.jsonl"), key=lambda f: f.stat().st_mtime, reverse=True)
                    if files:
                        return files[0]

    # Check project-local transcripts
    local = ROOT / "memory" / "copilot" / "transcripts"
    if local.is_dir():
        files = sorted(local.glob("*.jsonl"), key=lambda f: f.stat().st_mtime, reverse=True)
        if files:
            return files[0]

    return None


@dataclass
class CopilotTurn:
    """One turn in a Copilot conversation."""
    role: str           # "user" or "assistant"
    content: str
    turn_number: int
    ts: str = ""
    estimated_tokens: int = 0
    estimated_cost_usd: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "content_len": len(self.content),
            "turn": self.turn_number,
            "est_tokens": self.estimated_tokens,
            "est_cost_usd": round(self.estimated_cost_usd, 6),
        }


def parse_transcript(transcript_path: Path, max_turns: int = 50) -> list[CopilotTurn]:
    """Parse a Copilot transcript JSONL file into turns.

    Copilot transcript format (JSONL): each line is a JSON event with type:
      - user.message:     {data: {content: "text", attachments: []}}
      - assistant.message: {data: {messageId, content: "text", reasoningText: "..."}}
      - assistant.turn_start / assistant.turn_end: turn boundaries
      - tool.execution_start / tool.execution_complete: tool calls
    """
    turns = []
    try:
        lines = transcript_path.read_text(encoding="utf-8").strip().splitlines()
    except (UnicodeDecodeError, OSError):
        return turns

    # Buffer for assistant reasoning + content
    current_assistant_content = ""
    current_user_content = ""
    turn_num = 0

    for line in lines[-max_turns * 10:]:  # events per turn vary, so read more lines
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue

        event_type = entry.get("type", "")
        data = entry.get("data", {})
        ts = entry.get("timestamp", "")

        if event_type == "user.message":
            content = data.get("content", "")
            if content.strip():
                turn_num += 1
                turns.append(CopilotTurn(
                    role="user",
                    content=content[:5000],
                    turn_number=turn_num,
                    ts=ts,
                    estimated_tokens=len(content) // 4,
                    estimated_cost_usd=_estimate_turn_cost("user", len(content)),
                ))

        elif event_type == "assistant.message":
            msg_content = data.get("content", "")
            reasoning = data.get("reasoningText", "")
            combined = f"{reasoning}\n\n{msg_content}" if reasoning else msg_content
            if combined.strip():
                turn_num += 1
                turns.append(CopilotTurn(
                    role="assistant",
                    content=combined[:8000],
                    turn_number=turn_num,
                    ts=ts,
                    estimated_tokens=len(combined) // 4,
                    estimated_cost_usd=_estimate_turn_cost("assistant", len(combined)),
                ))

    return turns[-max_turns:] if len(turns) > max_turns else turns


def _estimate_turn_cost(role: str, content_len: int) -> float:
    """Estimate the API cost of one turn.

    Assumes the current model pricing. Conservative estimate.
    """
    tokens = content_len // 4
    # User turns: input tokens (cheaper). Assistant turns: output tokens (more expensive).
    # Using DeepSeek-v4-flash pricing as baseline: $0.013/1M tokens
    rate = 0.013 / 1_000_000
    return tokens * rate


# ═══════════════════════════════════════════════════════════════════
# BRIDGE ENGINE
# ═══════════════════════════════════════════════════════════════════

@dataclass
class BridgeResult:
    """Result of one bridge sync operation."""
    turns_synced: int
    checkpoints_written: int
    constitutional_flags: int
    ledger_entries: int
    total_estimated_cost: float
    session_id: str
    ts: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "turns_synced": self.turns_synced,
            "checkpoints_written": self.checkpoints_written,
            "constitutional_flags": self.constitutional_flags,
            "ledger_entries": self.ledger_entries,
            "total_estimated_cost": round(self.total_estimated_cost, 6),
            "session_id": self.session_id,
            "ts": self.ts,
        }


class CopilotBridge:
    """Syncs Copilot conversation state into the Ghost stack."""

    def __init__(self):
        self.last_sync_turn = 0
        self.session_id = f"copilot-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M')}"
        self.bridge_log = ROOT / "memory" / "copilot" / "bridge_log.jsonl"
        self.bridge_log.parent.mkdir(parents=True, exist_ok=True)

    def sync(self, *, max_turns: int = 50) -> BridgeResult:
        """Sync the current Copilot conversation into Ghost.

        1. Find and parse the transcript
        2. Write context checkpoints for new turns
        3. Run constitutional heuristics on assistant responses
        4. Write estimated costs to Ghost ledger
        5. Log bridge activity

        Returns BridgeResult with counts.
        """
        transcript_path = find_transcript_path()
        if not transcript_path:
            return BridgeResult(turns_synced=0, checkpoints_written=0, constitutional_flags=0,
                              ledger_entries=0, total_estimated_cost=0.0, session_id=self.session_id)

        turns = parse_transcript(transcript_path, max_turns=max_turns)
        if not turns:
            return BridgeResult(turns_synced=0, checkpoints_written=0, constitutional_flags=0,
                              ledger_entries=0, total_estimated_cost=0.0, session_id=self.session_id)

        # Only sync new turns
        new_turns = [t for t in turns if t.turn_number > self.last_sync_turn]
        if not new_turns:
            return BridgeResult(turns_synced=0, checkpoints_written=0, constitutional_flags=0,
                              ledger_entries=0, total_estimated_cost=0.0, session_id=self.session_id)

        checkpoints = 0
        flags = 0
        ledger = 0
        total_cost = 0.0

        # Build context from all turns
        full_context = self._build_context(turns)

        for turn in new_turns:
            # Write checkpoint
            try:
                from mag.context_checkpoint import checkpoint_turn
                cp = checkpoint_turn(
                    self.session_id,
                    full_context,
                    model_used="copilot-deepseek",  # assume DeepSeek for now
                    model_cost_usd=turn.estimated_cost_usd,
                )
                checkpoints += 1
            except Exception:
                pass

            # Run constitutional heuristics on assistant responses
            if turn.role == "assistant":
                try:
                    from mag.constitutional_critique import _local_heuristics
                    violations = _local_heuristics(turn.content, "T2")
                    if violations:
                        flags += len(violations)
                except Exception:
                    pass

            # Write to ledger
            try:
                from mag.ghost_ledger import write_entry
                write_entry(
                    source="copilot_bridge",
                    model="deepseek-v4-flash",
                    tokens_in=turn.estimated_tokens if turn.role == "user" else 0,
                    tokens_out=turn.estimated_tokens if turn.role == "assistant" else 0,
                    cost_usd=turn.estimated_cost_usd,
                    task_type="copilot_conversation",
                    goal_summary=turn.content[:200],
                    via="copilot_sync",
                )
                ledger += 1
            except Exception:
                pass

            total_cost += turn.estimated_cost_usd

        self.last_sync_turn = turns[-1].turn_number if turns else self.last_sync_turn

        result = BridgeResult(
            turns_synced=len(new_turns),
            checkpoints_written=checkpoints,
            constitutional_flags=flags,
            ledger_entries=ledger,
            total_estimated_cost=total_cost,
            session_id=self.session_id,
        )

        self._log(result)
        return result

    def _build_context(self, turns: list[CopilotTurn]) -> str:
        """Build a full context string from turns."""
        lines = []
        for t in turns:
            prefix = "OPERATOR:" if t.role == "user" else "GHOST:"
            lines.append(f"{prefix} {t.content[:500]}")
        return "\n".join(lines)

    def _log(self, result: BridgeResult):
        try:
            with open(self.bridge_log, "a", encoding="utf-8") as f:
                f.write(json.dumps(result.to_dict(), default=str) + "\n")
        except OSError:
            pass

    def status(self) -> dict[str, Any]:
        """Get bridge status."""
        transcript_path = find_transcript_path()
        return {
            "ok": True,
            "session_id": self.session_id,
            "last_sync_turn": self.last_sync_turn,
            "transcript_found": transcript_path is not None,
            "transcript_path": str(transcript_path) if transcript_path else None,
            "bridge_log": str(self.bridge_log),
        }


# ═══════════════════════════════════════════════════════════════════
# AUTO-SYNC DAEMON (runs inside Ghost as a background loop)
# ═══════════════════════════════════════════════════════════════════

async def copilot_sync_loop(interval_seconds: int = 60):
    """Background loop that periodically syncs Copilot state into Ghost.

    Runs inside the Ghost daemon's background tasks.
    """
    bridge = CopilotBridge()
    while True:
        try:
            result = bridge.sync()
            if result.turns_synced > 0:
                # Publish sync event to Verkle bus
                try:
                    from mag.verkle_bus import publish_sync, CH_VERKLE
                    publish_sync(CH_VERKLE, {
                        "type": "copilot_sync",
                        "ts": _now(),
                        "data": result.to_dict(),
                    })
                except Exception:
                    pass
        except Exception:
            pass

        import asyncio
        await asyncio.sleep(interval_seconds)


# ═══════════════════════════════════════════════════════════════════
# QUICK ACCESS
# ═══════════════════════════════════════════════════════════════════

_BRIDGE: Optional[CopilotBridge] = None


def get_bridge() -> CopilotBridge:
    global _BRIDGE
    if _BRIDGE is None:
        _BRIDGE = CopilotBridge()
    return _BRIDGE


def bridge_sync() -> BridgeResult:
    """Sync Copilot → Ghost. Call this to connect the conversation."""
    return get_bridge().sync()


def bridge_status() -> dict[str, Any]:
    """Get bridge status."""
    return get_bridge().status()
