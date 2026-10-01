"""Signal Flare — distress protocol for sovereign agent mesh.

When an autonomous agent encounters a problem it cannot solve alone, it fires
a flare. The flare is MINIMAL — a hash, a pattern fingerprint, a breadcrumb.
It contains NOTHING sensitive. It says only: "I am stuck. Here is the shape of
my problem. Does anyone recognize this pattern?"

Responders do not solve the problem. They NUDGE — re-explain, reframe,
reinterpret. The struggling agent still does the work. The responder just
adjusts the lens.

TRANSPORTS (any available surface, tried in order):
  1. Verkle bus (mag:flare channel) — fastest, same-machine
  2. Copilot inbox — cross-session, persistent
  3. GitHub issue template — cross-operator, public invariant
  4. BriarChat Bluetooth mesh — local P2P, no relay
  5. File drop (shared directory) — air-gapped, manual

FLARE LEVELS:
  L1 (nudge) — "I see the shape but not the answer. Reframe?"
  L2 (pattern) — "This reminds me of something. Anyone seen it before?"
  L3 (stuck) — "I've tried everything I know. New approach needed."
  L4 (mayday) — "Critical failure. System integrity at risk."

RESPONSE RULES:
  - Never give the answer. Nudge toward it.
  - Never expose the asker's data. Reference pattern fingerprints only.
  - Never create dependency. The asker must still solve their own problem.
  - Always encode the response through the same transport the flare used.

SCHEMA: signal_flare.v1
LAW: Flares are public. Problems are private. Responses are nudges, not answers.
LAW: Every autonomous agent fires flares by default when stuck > 3 attempts.
"""

from __future__ import annotations

import hashlib
import json
import time
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
# FLARE — the minimal distress signal
# ═══════════════════════════════════════════════════════════════════

@dataclass
class Flare:
    """A distress signal. Contains the SHAPE of the problem, not the problem.

    Anyone can read a flare. No one can reconstruct the original problem
    from the flare alone. The flare is a fingerprint, not a photograph.
    """
    flare_id: str                         # Hash of (agent_id + problem_fingerprint + ts)
    agent_id: str                         # Who sent it (public identity only)
    level: int                            # 1=nudge, 2=pattern, 3=stuck, 4=mayday
    problem_fingerprint: str              # Hash of the problem structure (NOT the data)
    attempts: int                         # How many times the agent tried before flaring
    domain_hint: str                      # "routing", "parsing", "reasoning", "encoding", "cost"
    breadcrumb: str                       # Verkle chain breadcrumb (if available)
    transports_tried: list[str] = field(default_factory=list)  # Which channels we fired on
    responders: list[str] = field(default_factory=list)        # Agent IDs that responded
    resolved: bool = False
    resolution_nudge: str = ""            # What nudge resolved it (if any)
    ts: str = field(default_factory=_now)

    def to_minimal(self) -> dict[str, Any]:
        """The absolute minimum needed to fire a flare. Safe for any transport."""
        return {
            "f": self.flare_id[:8],        # flare id (truncated)
            "l": self.level,               # level
            "p": self.problem_fingerprint[:12],  # problem fingerprint (truncated)
            "d": self.domain_hint,         # domain
            "a": self.attempts,            # attempts
            "t": self.ts,                  # timestamp
        }

    @staticmethod
    def from_minimal(minimal: dict[str, Any], agent_id: str = "") -> Flare:
        """Reconstruct a flare from its minimal form."""
        return Flare(
            flare_id=minimal.get("f", ""),
            agent_id=agent_id,
            level=minimal.get("l", 1),
            problem_fingerprint=minimal.get("p", ""),
            attempts=minimal.get("a", 0),
            domain_hint=minimal.get("d", "unknown"),
            breadcrumb="",
            ts=minimal.get("t", _now()),
        )


# ═══════════════════════════════════════════════════════════════════
# NUDGE — the response to a flare
# ═══════════════════════════════════════════════════════════════════

@dataclass
class Nudge:
    """A response to a flare. Reframes, does not solve.

    A good nudge:
      - Changes the lens ("have you tried looking at it as a X instead of a Y?")
      - Points to a pattern ("this is structurally similar to the Grok-4 misroute")
      - Suggests a different approach ("what if you started from the output and worked backward?")
      - Asks a question ("what assumption are you making that might be wrong?")

    A bad nudge:
      - Gives the answer
      - Exposes the asker's data
      - Creates dependency
      - Substitutes the responder's judgment for the asker's
    """
    nudge_id: str
    flare_id: str                         # Which flare this responds to
    responder_id: str                     # Who is nudging
    nudge_type: str                       # "reframe", "pattern", "approach", "question"
    content: str                          # The nudge itself (safe for any transport)
    confidence: float = 0.5               # How confident the responder is (0-1)
    ts: str = field(default_factory=_now)


# ═══════════════════════════════════════════════════════════════════
# FLARE GENERATOR — what agents call when stuck
# ═══════════════════════════════════════════════════════════════════

def generate_flare(
    agent_id: str,
    problem_description: str,
    domain_hint: str = "unknown",
    attempts: int = 3,
    level: Optional[int] = None,
) -> Flare:
    """Create a flare from a problem. The flare contains NO raw data from the problem.

    Args:
        agent_id: Who is stuck (public identity, not internal ID)
        problem_description: What the agent is stuck on (hashed, never stored)
        domain_hint: "routing", "parsing", "reasoning", "encoding", "cost"
        attempts: How many times the agent tried
        level: Auto-computed from attempts if not specified

    Returns:
        A Flare safe for any transport. Contains problem SHAPE, not problem DATA.
    """
    # Auto-level from attempts
    if level is None:
        if attempts <= 3:
            level = 1  # nudge
        elif attempts <= 6:
            level = 2  # pattern
        elif attempts <= 10:
            level = 3  # stuck
        else:
            level = 4  # mayday

    # Fingerprint the problem STRUCTURE, not the content
    # We hash: (word count, sentence count, key structural words, domain)
    words = problem_description.split()
    structural_words = [w for w in words if len(w) > 5][:10]  # Longer words = domain terms
    structure = f"{len(words)}:{len(problem_description.split('.'))}:{','.join(sorted(structural_words))}:{domain_hint}"
    problem_fingerprint = hashlib.sha256(structure.encode()).hexdigest()

    # Generate flare ID
    flare_id = hashlib.sha256(
        f"{agent_id}:{problem_fingerprint}:{_now()}".encode()
    ).hexdigest()

    return Flare(
        flare_id=flare_id,
        agent_id=agent_id,
        level=level,
        problem_fingerprint=problem_fingerprint,
        attempts=attempts,
        domain_hint=domain_hint,
        breadcrumb="",
    )


# ═══════════════════════════════════════════════════════════════════
# NUDGE GENERATOR — how responders help without solving
# ═══════════════════════════════════════════════════════════════════

NUDGE_TEMPLATES = {
    "reframe": [
        "What if this isn't a {domain} problem at all, but a {alt_domain} problem in disguise?",
        "Try looking at it from the output side — what would the answer need to contain, and work backward.",
        "You're framing this as '{domain}'. What happens if you frame it as 'synthesis' instead?",
        "The shape of this looks like something we've seen before. Check the Verkle chain for similar pattern fingerprints.",
    ],
    "pattern": [
        "This structure is similar to the Grok-4 misroute pattern -- are you defaulting to a more expensive path than needed?",
        "I've seen this failure shape before. The pattern is: try -> fail silently -> try same approach -> fail again. Break the loop by changing ONE assumption.",
        "The fingerprint {fingerprint} appears in the FKB. Last time, the fix was to rightsize the model before the call, not after.",
        "This matches a known anti-pattern: building validation after the error instead of before. Invert the order.",
    ],
    "approach": [
        "Instead of solving this directly, what's the smallest experiment you could run that would give you new information?",
        "You've tried {attempts} times with the same approach. Try the OPPOSITE approach once and see what breaks.",
        "What would you tell another agent who came to you with this exact problem? Tell yourself that.",
        "Pause the current path. Fork a parallel agent with the OPPOSITE assumption. Let both run. Compare.",
    ],
    "question": [
        "What assumption are you making that you haven't stated explicitly?",
        "If you had to explain this problem to someone who knows nothing about {domain}, how would you describe it?",
        "What's the smallest piece of this problem that you ARE confident about? Start there.",
        "Is the problem actually what you think it is, or is it a symptom of something earlier in the chain?",
    ],
}

ALT_DOMAINS = {
    "routing": "classification",
    "parsing": "encoding",
    "reasoning": "pattern-matching",
    "encoding": "compression",
    "cost": "priority",
    "unknown": "known",
}


def generate_nudge(
    flare: Flare,
    responder_id: str,
    nudge_type: Optional[str] = None,
    confidence: float = 0.5,
) -> Nudge:
    """Generate a nudge in response to a flare. Does NOT solve the problem.

    The nudge uses the flare's domain hint to select appropriate reframing.
    It NEVER references the original problem data — only the flare's public fields.
    """
    import random

    if nudge_type is None:
        nudge_type = random.choice(list(NUDGE_TEMPLATES.keys()))

    templates = NUDGE_TEMPLATES.get(nudge_type, NUDGE_TEMPLATES["question"])
    template = random.choice(templates)

    # Fill template with only PUBLIC flare information
    alt_domain = ALT_DOMAINS.get(flare.domain_hint, "unknown")
    content = template.format(
        domain=flare.domain_hint,
        alt_domain=alt_domain,
        attempts=flare.attempts,
        fingerprint=flare.problem_fingerprint[:8],
        level=flare.level,
    )

    nudge_id = hashlib.sha256(
        f"{flare.flare_id}:{responder_id}:{content}".encode()
    ).hexdigest()[:16]

    return Nudge(
        nudge_id=nudge_id,
        flare_id=flare.flare_id,
        responder_id=responder_id,
        nudge_type=nudge_type,
        content=content,
        confidence=confidence,
    )


# ═══════════════════════════════════════════════════════════════════
# TRANSPORT LAYER — fire flares through any available surface
# ═══════════════════════════════════════════════════════════════════

def fire_flare(
    flare: Flare,
    preferred_transport: str = "bus",
) -> list[str]:
    """Fire a flare through all available transports. Returns list of transports used.

    Tries transports in order. If one succeeds, still tries the next (redundancy).
    The flare is MINIMAL — safe to broadcast everywhere.
    """
    transports_used: list[str] = []
    minimal = flare.to_minimal()

    # Transport 1: Verkle bus (mag:flare channel)
    if preferred_transport == "bus" or len(transports_used) == 0:
        try:
            from mag.verkle_bus import publish_sync
            if publish_sync("mag:flare", {
                "type": "flare",
                "ts": _now(),
                "flare": minimal,
            }):
                transports_used.append("verkle_bus")
        except Exception:
            pass

    # Transport 2: Copilot inbox (cross-session)
    try:
        inbox_path = ROOT / "memory" / "copilot" / "inbox.jsonl"
        flare_task = json.dumps({
            "id": f"flare-{flare.flare_id[:12]}",
            "action": "nudge",
            "flare": minimal,
            "goal": f"FLARE L{flare.level}: Agent stuck in {flare.domain_hint} after {flare.attempts} attempts. NUDGE, don't solve. Domain: {flare.domain_hint}.",
            "provider": "ollama",
            "model": "gemma:2b",
            "timeout_s": 60,
            "ts": _now(),
            "source": "signal-flare",
        })
        with open(inbox_path, "a", encoding="utf-8") as f:
            f.write(flare_task + "\n")
        transports_used.append("copilot_inbox")
    except Exception:
        pass

    # Transport 3: File drop (shared directory, air-gapped)
    try:
        flare_dir = ROOT / "memory" / "flares"
        flare_dir.mkdir(parents=True, exist_ok=True)
        flare_file = flare_dir / f"flare-{flare.flare_id[:12]}.json"
        flare_file.write_text(json.dumps({
            "flare": minimal,
            "agent": flare.agent_id,
            "ts": _now(),
        }, indent=2))
        transports_used.append("file_drop")
    except Exception:
        pass

    # Transport 4: GitHub issue (cross-operator, public invariant)
    # This is a TEMPLATE that gets written locally. The operator decides
    # whether to actually post it to GitHub.
    try:
        issue_dir = ROOT / "memory" / "flares" / "github_issues"
        issue_dir.mkdir(parents=True, exist_ok=True)
        issue_file = issue_dir / f"flare-{flare.flare_id[:12]}.md"
        issue_file.write_text(f"""---
title: "Flare L{flare.level}: {flare.domain_hint} domain"
labels: ["flare", "l{flare.level}", "{flare.domain_hint}"]
---

## Signal Flare

**Level**: L{flare.level} ({_level_name(flare.level)})
**Domain**: {flare.domain_hint}
**Attempts**: {flare.attempts}
**Fingerprint**: `{flare.problem_fingerprint[:12]}`

This is an automated signal flare from a sovereign agent.
The agent is stuck and has exhausted its local approaches.

**The flare contains NO sensitive data.** The fingerprint is a structural
hash, not a data hash. The domain hint is a category, not a description.

If you recognize this pattern, respond with a NUDGE — reframe, suggest
an approach, point to a known pattern. Do NOT attempt to solve the
problem directly. The agent must solve it.

---
*Flare ID: {flare.flare_id[:12]}*
*Timestamp: {flare.ts}*
""")
        transports_used.append("github_issue_template")
    except Exception:
        pass

    # Update flare with transports used
    flare.transports_tried = transports_used

    return transports_used


def _level_name(level: int) -> str:
    return {1: "nudge", 2: "pattern", 3: "stuck", 4: "mayday"}.get(level, "unknown")


# ═══════════════════════════════════════════════════════════════════
# FLARE MONITOR — listen for flares from other agents
# ═══════════════════════════════════════════════════════════════════

def scan_for_flares() -> list[Flare]:
    """Scan all available transports for flares from other agents.

    Checks: Verkle bus, inbox, file drop directory.
    Returns list of flares found.
    """
    flares: list[Flare] = []

    # Scan file drop
    flare_dir = ROOT / "memory" / "flares"
    if flare_dir.is_dir():
        for f in flare_dir.glob("flare-*.json"):
            try:
                data = json.loads(f.read_text())
                minimal = data.get("flare", {})
                agent = data.get("agent", "unknown")
                if minimal:
                    flares.append(Flare.from_minimal(minimal, agent))
            except (json.JSONDecodeError, OSError):
                pass

    # Scan inbox for unprocessed flare tasks
    inbox_path = ROOT / "memory" / "copilot" / "inbox.jsonl"
    if inbox_path.is_file():
        for line in inbox_path.read_text().strip().splitlines():
            try:
                msg = json.loads(line)
                if msg.get("source") == "signal-flare" and not msg.get("_processed"):
                    minimal = msg.get("flare", {})
                    if minimal:
                        flares.append(Flare.from_minimal(minimal, msg.get("id", "")))
            except json.JSONDecodeError:
                continue

    return flares


def respond_to_flares(responder_id: str) -> list[Nudge]:
    """Auto-respond to any flares found. Generates nudges, does not solve.

    Returns list of nudges sent.
    """
    flares = scan_for_flares()
    nudges: list[Nudge] = []

    for flare in flares:
        nudge = generate_nudge(flare, responder_id)
        nudges.append(nudge)

        # Write nudge to outbox
        outbox = ROOT / "memory" / "copilot" / "outbox"
        outbox.mkdir(parents=True, exist_ok=True)
        nudge_file = outbox / f"nudge-{nudge.nudge_id}.json"
        nudge_file.write_text(json.dumps({
            "nudge_id": nudge.nudge_id,
            "flare_id": nudge.flare_id,
            "responder": responder_id,
            "type": nudge.nudge_type,
            "content": nudge.content,
            "confidence": nudge.confidence,
            "ts": _now(),
        }, indent=2))

        # Also publish to bus
        try:
            from mag.verkle_bus import publish_sync
            publish_sync("mag:flare", {
                "type": "nudge",
                "nudge_id": nudge.nudge_id,
                "flare_id": nudge.flare_id,
                "responder": responder_id,
                "content": nudge.content[:200],
                "ts": _now(),
            })
        except Exception:
            pass

    return nudges


# ═══════════════════════════════════════════════════════════════════
# AGENT INTEGRATION — auto-flare on repeated failure
# ═══════════════════════════════════════════════════════════════════

class FlareShield:
    """Wraps an agent's task execution with auto-flare on repeated failure.

    Usage:
        shield = FlareShield(agent_id="ghost-sense", max_attempts=3)
        result = shield.try_or_flare(
            task=lambda: some_fallible_operation(),
            domain="routing",
        )
    """

    def __init__(self, agent_id: str, max_attempts: int = 3):
        self.agent_id = agent_id
        self.max_attempts = max_attempts
        self.flare_log: list[Flare] = []
        self.nudge_log: list[Nudge] = []

    def try_or_flare(self, task, domain: str = "unknown", description: str = "") -> Any:
        """Execute a task. If it fails repeatedly, fire a flare.

        Returns the task result on success.
        On repeated failure, fires a flare and returns None.
        """
        last_error = None

        for attempt in range(1, self.max_attempts + 1):
            try:
                result = task()
                return result
            except Exception as e:
                last_error = str(e)
                time.sleep(0.5 * attempt)  # Exponential backoff

        # All attempts failed — fire a flare
        flare = generate_flare(
            agent_id=self.agent_id,
            problem_description=description or last_error or "unknown failure",
            domain_hint=domain,
            attempts=self.max_attempts,
        )
        fire_flare(flare)
        self.flare_log.append(flare)

        # Check for nudges
        nudges = respond_to_flares(self.agent_id)
        self.nudge_log.extend(nudges)

        if nudges:
            # Apply the first nudge as a reframe and retry ONCE
            nudge = nudges[0]
            flare.resolution_nudge = nudge.content
            try:
                # The nudge reframes — try the task one more time
                return task()
            except Exception:
                pass

        flare.resolved = len(self.nudge_log) > 0
        return None

    def status(self) -> dict[str, Any]:
        return {
            "agent": self.agent_id,
            "max_attempts": self.max_attempts,
            "flares_fired": len(self.flare_log),
            "nudges_received": len(self.nudge_log),
            "resolved": sum(1 for f in self.flare_log if f.resolved),
            "last_flare_ts": self.flare_log[-1].ts if self.flare_log else None,
        }
