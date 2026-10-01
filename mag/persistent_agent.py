"""Persistent Agent Actors — long-running conversations as Verkle-backed memory states.

Instead of one-shot spawn-and-die subprocesses, persistent agents maintain
their own conversation history and reference quantized memory states from
the Verkle lattice. They coordinate through Q-knots and survive crashes
via holographic reconstitution.

ARCHITECTURE:
  Each agent is a long-running asyncio task with:
    - agent_id: unique identity (cartographer, forgesmith, mirrorseer, scribe)
    - memory_state: QuantizedMemory reference (compressed Verkle state)
    - conversation_log: append-only JSONL of all turns
    - q_subscription: listens for Q-knots assigned to this agent
    - action_loop: sense → think → act → measure → fold → repeat

JABBERWOCKY DND:
  The DnD campaign IS the testbed. Each party member is a PersistentAgent.
  Rooms are quantization checkpoints. Between rooms, the state quantizer
  compresses the party's actions into a summary knot. Next room loads from
  the summary. The campaign is a state machine; the agents are the state.

GROK AS PRIVATE COPY:
  If Grok is available, persistent agents use Grok as their reasoning layer.
  The quantized memory state is injected as context. Grok sees the compressed
  system state, not the raw Verkle chain. This is the "private copy" — Grok
  gets a dense summary, never the raw data.

Schema: persistent_agent.v1
"""

from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

try:
    from config import ROOT
except ImportError:
    ROOT = Path(__file__).resolve().parent.parent

# ── Paths ──
AGENT_DIR = ROOT / "memory" / "ghost" / "persistent_agents"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _append_jsonl(path: Path, entry: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _read_jsonl(path: Path, tail: int = 50) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8", errors="replace").strip().splitlines()
    if tail and len(lines) > tail:
        lines = lines[-tail:]
    rows: list[dict[str, Any]] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


# ═══════════════════════════════════════════════════════════════════
# PERSISTENT AGENT
# ═══════════════════════════════════════════════════════════════════

@dataclass
class AgentTurn:
    """A single turn in a persistent agent's conversation."""
    turn_id: str
    agent_id: str
    sequence: int
    role: str                        # "sense", "think", "act", "measure"
    input_state: dict[str, Any]      # what the agent saw
    action: str                      # what the agent did
    output: str                      # what resulted
    memory_ref: str                  # quantized memory state hash referenced
    q_knots_seen: list[str]          # Q-knot IDs observed this turn
    ts: str
    verkle_root: str = ""            # folded to Verkle after turn


@dataclass
class PersistentAgent:
    """A long-running agent actor with its own conversation history.

    Survives crashes via holographic reconstitution — conversation log
    is periodically folded to Verkle knots. On restart, reads its own
    history from the lattice and continues.
    """
    agent_id: str
    role: str                        # cartographer, forgesmith, mirrorseer, scribe
    model: str                       # qwen2.5-coder:7b, deepseek-v4-flash, grok-3
    provider: str                    # ollama, deepseek, grok
    agent_dir: Path = field(init=False)
    conversation_log: Path = field(init=False)
    state_file: Path = field(init=False)
    turns: list[AgentTurn] = field(default_factory=list)
    sequence: int = 0
    memory_state: Any = None         # QuantizedMemory reference
    status: str = "idle"

    def __post_init__(self):
        self.agent_dir = AGENT_DIR / self.agent_id
        self.agent_dir.mkdir(parents=True, exist_ok=True)
        self.conversation_log = self.agent_dir / "conversation.jsonl"
        self.state_file = self.agent_dir / "state.json"

    def load_state(self) -> None:
        """Load agent state from disk (survives restarts)."""
        if self.state_file.is_file():
            try:
                state = json.loads(self.state_file.read_text(encoding="utf-8"))
                self.sequence = state.get("sequence", 0)
                self.status = state.get("status", "idle")
            except (json.JSONDecodeError, OSError):
                pass

        # Load recent turns
        self.turns = []
        for entry in _read_jsonl(self.conversation_log, tail=20):
            try:
                self.turns.append(AgentTurn(
                    turn_id=entry.get("turn_id", ""),
                    agent_id=entry.get("agent_id", self.agent_id),
                    sequence=entry.get("sequence", 0),
                    role=entry.get("role", "?"),
                    input_state=entry.get("input_state", {}),
                    action=entry.get("action", ""),
                    output=entry.get("output", ""),
                    memory_ref=entry.get("memory_ref", ""),
                    q_knots_seen=entry.get("q_knots_seen", []),
                    ts=entry.get("ts", ""),
                    verkle_root=entry.get("verkle_root", ""),
                ))
            except Exception:
                continue

    def save_state(self) -> None:
        """Persist agent state."""
        self.state_file.write_text(json.dumps({
            "agent_id": self.agent_id,
            "role": self.role,
            "sequence": self.sequence,
            "status": self.status,
            "turns": len(self.turns),
            "updated_at": _now(),
        }, indent=2, ensure_ascii=False), encoding="utf-8")

    def record_turn(self, role: str, input_state: dict[str, Any],
                    action: str, output: str, memory_ref: str = "",
                    q_knots_seen: list[str] | None = None) -> AgentTurn:
        """Record a turn in the agent's conversation history."""
        self.sequence += 1
        turn = AgentTurn(
            turn_id=f"{self.agent_id}-turn-{self.sequence:04d}",
            agent_id=self.agent_id,
            sequence=self.sequence,
            role=role,
            input_state=input_state,
            action=action,
            output=output,
            memory_ref=memory_ref,
            q_knots_seen=q_knots_seen or [],
            ts=_now(),
        )
        self.turns.append(turn)

        # Log to conversation file
        _append_jsonl(self.conversation_log, {
            "turn_id": turn.turn_id,
            "agent_id": turn.agent_id,
            "sequence": turn.sequence,
            "role": turn.role,
            "action": turn.action[:200],
            "output": turn.output[:500],
            "memory_ref": turn.memory_ref,
            "q_knots_seen": turn.q_knots_seen,
            "ts": turn.ts,
        })

        # Fold to Verkle (best-effort)
        try:
            from mag.verkle_knot import append_verkle_knot
            append_verkle_knot({
                "session_id": turn.turn_id,
                "time": {
                    "created_at": {"iso_minute": turn.ts, "unix_minute": None, "date": None},
                    "updated_at": {"iso_minute": turn.ts, "unix_minute": None, "date": None},
                },
                "scalar_knot": {
                    "duration_minutes": 0.01,
                    "tension_index": f"agent-{self.agent_id}",
                    "residual_weight": 0.5,
                    "theme_vector": {
                        "dominant": f"agent_{self.role}",
                        "basis": ["agent", self.role, "turn", "conversation"],
                        "raw": [1.0, 0.8, 0.5, 0.3],
                        "normalized": [0.45, 0.36, 0.23, 0.14],
                    },
                },
                "content_commit": {"hex": turn.turn_id},
                "_agent_turn": {
                    "agent_id": self.agent_id,
                    "role": self.role,
                    "sequence": self.sequence,
                    "action": turn.action[:100],
                },
            })
        except Exception:
            pass

        self.save_state()
        return turn

    def get_context_for_llm(self) -> str:
        """Build a context block for injection into LLM prompts.

        Includes: role, recent turns, quantized memory state, Q-knots seen.
        """
        lines = [
            f"[AGENT: {self.agent_id} | ROLE: {self.role}]",
            f"Turns completed: {self.sequence}",
        ]

        if self.memory_state:
            try:
                lines.append(self.memory_state.to_agent_context())
            except Exception:
                pass

        if self.turns:
            lines.append(f"\nRecent turns ({min(5, len(self.turns))}):")
            for turn in self.turns[-5:]:
                lines.append(f"  [{turn.role}] {turn.action[:80]} → {turn.output[:80]}")

        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "role": self.role,
            "model": self.model,
            "provider": self.provider,
            "sequence": self.sequence,
            "turns": len(self.turns),
            "status": self.status,
        }


# ═══════════════════════════════════════════════════════════════════
# AGENT FACTORY — DnD party + research swarm
# ═══════════════════════════════════════════════════════════════════

def create_dnd_party() -> dict[str, PersistentAgent]:
    """Create the standard 4-agent DnD party as persistent agents.

    These agents survive across campaign rooms. Their conversation logs
    are the party's shared memory. Between rooms, the state quantizer
    compresses their actions into a summary knot.
    """
    return {
        "cartographer": PersistentAgent(
            agent_id="cartographer",
            role="planner",
            model="qwen2.5-coder:7b",
            provider="ollama",
        ),
        "forgesmith": PersistentAgent(
            agent_id="forgesmith",
            role="crafter",
            model="gemma:2b",
            provider="ollama",
        ),
        "mirrorseer": PersistentAgent(
            agent_id="mirrorseer",
            role="reflector",
            model="qwen2.5-coder:7b",
            provider="ollama",
        ),
        "scribe": PersistentAgent(
            agent_id="scribe",
            role="recorder",
            model="qwen2.5-coder:7b",
            provider="ollama",
        ),
    }


def create_research_swarm() -> dict[str, PersistentAgent]:
    """Create a research swarm for prompt archaeology and architecture analysis."""
    return {
        "archaeologist": PersistentAgent(
            agent_id="archaeologist",
            role="prompt_analyst",
            model="deepseek-v4-flash",
            provider="deepseek",
        ),
        "theorist": PersistentAgent(
            agent_id="theorist",
            role="pattern_matcher",
            model="deepseek-v4-flash",
            provider="deepseek",
        ),
        "engineer": PersistentAgent(
            agent_id="engineer",
            role="builder",
            model="qwen2.5-coder:7b",
            provider="ollama",
        ),
    }


# ═══════════════════════════════════════════════════════════════════
# AGENT LOOP — the persistent execution cycle
# ═══════════════════════════════════════════════════════════════════

async def agent_conversation_loop(
    agent: PersistentAgent,
    *,
    interval_s: float = 30.0,
    max_turns: int = 100,
) -> None:
    """Run a persistent agent's conversation loop.

    Each cycle:
      1. SENSE — read quantized memory state + Q-knots
      2. THINK — decide what to do
      3. ACT — execute (or queue task via copilot inbox)
      4. MEASURE — record result
      5. FOLD — write turn to Verkle chain

    The agent survives crashes — on restart, load_state() recovers
    sequence number and recent turns from disk + Verkle chain.
    """
    agent.load_state()
    agent.status = "running"

    while agent.sequence < max_turns:
        try:
            await asyncio.sleep(interval_s)

            # SENSE: read quantized memory state
            try:
                from mag.state_quantizer import create_memory_state
                agent.memory_state = create_memory_state(
                    f"agent-{agent.agent_id}",
                    verkle_tail=30,
                )
            except Exception:
                pass

            # SENSE: read Q-knots assigned to this agent
            q_knots_seen: list[str] = []
            try:
                from mag.holographic_q import reconstitute_q
                q_knots = reconstitute_q(verkle_tail=20)
                for knot in q_knots:
                    if agent.agent_id in knot.agent_assignments or not knot.agent_assignments:
                        q_knots_seen.append(knot.session_id)
            except Exception:
                pass

            # THINK + ACT: route through copilot inbox for LLM execution
            context = agent.get_context_for_llm()
            goal = (
                f"[{agent.role}] You are the {agent.agent_id}. "
                f"Context: {context}. "
                f"Q-steers seen: {q_knots_seen[:3]}. "
                f"Take one action. Be concise. Record what you did and why."
            )

            # Queue through copilot inbox (Ghost handles execution)
            inbox_path = ROOT / "memory" / "copilot" / "inbox.jsonl"
            msg = {
                "id": f"agent-{agent.agent_id}-turn-{agent.sequence + 1:04d}",
                "action": "exec",
                "goal": goal,
                "provider": agent.provider,
                "model": agent.model,
                "timeout_s": 120,
                "ts": _now(),
                "source": f"persistent-agent-{agent.agent_id}",
            }
            _append_jsonl(inbox_path, msg)

            # Record the turn (output will be filled by Ghost's copilot_watch_loop)
            agent.record_turn(
                role="act",
                input_state={"memory_ref": agent.memory_state.summary_id if agent.memory_state else ""},
                action=goal[:200],
                output="[queued for execution]",
                memory_ref=agent.memory_state.summary_id if agent.memory_state else "",
                q_knots_seen=q_knots_seen,
            )

        except asyncio.CancelledError:
            agent.status = "cancelled"
            break
        except Exception:
            agent.status = "error"
            await asyncio.sleep(interval_s * 2)  # back off on error

    agent.status = "completed"
    agent.save_state()


# ═══════════════════════════════════════════════════════════════════
# STATUS
# ═══════════════════════════════════════════════════════════════════

def list_persistent_agents() -> list[dict[str, Any]]:
    """List all persistent agents and their status."""
    if not AGENT_DIR.is_dir():
        return []

    agents: list[dict[str, Any]] = []
    for agent_dir in AGENT_DIR.iterdir():
        if not agent_dir.is_dir():
            continue
        state_file = agent_dir / "state.json"
        if state_file.is_file():
            try:
                state = json.loads(state_file.read_text(encoding="utf-8"))
                agents.append(state)
            except (json.JSONDecodeError, OSError):
                pass

    return agents
