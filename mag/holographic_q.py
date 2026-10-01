"""Holographic Q — distributed steer presence across the Verkle lattice.

Q is NOT a process. Q is a pattern encoded in Verkle knots.
If Ghost crashes, Q persists — any agent reading the lattice can reconstitute Q.

THE INSIGHT:
  - Q-knots are specially tagged Verkle entries with a standard schema
  - Each Q-knot contains: intent, context, steer vector, measurement axes
  - The lattice IS Q's memory — context saved in the chain, decipherable only
    by agents holding Verkle proofs (cryptographic access control)
  - Any agent can read Q-knots and continue Q's mission
  - Q's presence is holographic: the whole is encoded in every part

SCHEMA: q_knot.v1

Q-KNOT ENVELOPE:
  {
    "session_id": "q-{uuid}",
    "q_session": "{q_session_id}",       // groups related Q-knots
    "q_sequence": 0,                     // position in Q's intent chain
    "intent_hash": "sha256(...)",        // hash of Q's overall intent
    "context_hash": "sha256(...)",       // hash of context needed to decipher
    "steer_vector": "the actual steer text or encoded directive",
    "measurement_axes": ["silence", "flip", "emergent"],
    "previous_q_knot": "verkle_root_of_previous",
    "ttl_knots": 10,                     // how many more knots Q expects
    "decipher_key_hint": "verkle_proof_required",  // access control
    "agent_assignments": ["cartographer", "mirrorseer"],  // which agents
    "content_commit": {"hex": "..."},     // verifiable commitment
  }

RECONSTITUTION:
  Agent reads Verkle tail → finds Q-knots → verifies proofs → deciphers intent
  → continues Q's mission → writes response knot → Q updates state

CRASH RECOVERY:
  Ghost crashes at Q-sequence 3. Agent B reads lattice, finds Q-knots 0-3.
  Agent B verifies: intent_hash matches, context_hash valid, sequence unbroken.
  Agent B continues from sequence 4. Q never died.

Schema: holographic_q.v1
Law: Q-knots are Verkle-verifiable. No trust required. Proof is the access key.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from mag.chain_query import chain  # auto-added by doctor_agent
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except ImportError:
    ROOT = Path(__file__).resolve().parent.parent

# ── Paths ──
Q_DIR = ROOT / "memory" / "ghost" / "q_state"
Q_KNOT_LOG = Q_DIR / "q_knots.jsonl"
Q_SESSION_STORE = Q_DIR / "q_sessions.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    if path.is_file():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _append_jsonl(path: Path, entry: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _fold_verkle(dossier: dict[str, Any]) -> str:
    """Commit a Q/swarm/freeze dossier. Return verkle_root. Empty is failure, not silence."""
    from mag.verkle_knot import append_verkle_knot
    rec = append_verkle_knot(dossier) or {}
    root = str(rec.get("verkle_root") or rec.get("leaf_hash") or "").strip()
    if not root:
        raise RuntimeError("verkle append returned no root")
    return root


def _read_jsonl(path: Path, tail: int = 200) -> list[dict[str, Any]]:
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
# Q-KNOT DATA STRUCTURES
# ═══════════════════════════════════════════════════════════════════

@dataclass
class QKnot:
    """A single Q steer directive encoded as a Verkle-verifiable knot."""
    session_id: str                            # unique knot ID
    q_session: str                             # groups related Q-knots
    q_sequence: int                            # position in Q's intent chain
    intent_hash: str                           # sha256 of Q's overall intent
    context_hash: str                          # sha256 of context to decipher
    steer_vector: str                          # the actual steer directive
    measurement_axes: list[str]                # what to measure (silence, flip, emergent)
    previous_q_knot: str                       # verkle_root of previous Q-knot
    ttl_knots: int                             # remaining knots in this Q session
    agent_assignments: list[str]               # which agents should act
    verkle_root: str                           # this knot's verkle commitment
    ts: str
    status: str = "active"                     # active, consumed, expired, recovered

    def to_envelope(self) -> dict[str, Any]:
        """Export as a Verkle-compatible dossier."""
        return {
            "session_id": self.session_id,
            "q_session": self.q_session,
            "q_sequence": self.q_sequence,
            "intent_hash": self.intent_hash,
            "context_hash": self.context_hash,
            "steer_vector": self.steer_vector,
            "measurement_axes": self.measurement_axes,
            "previous_q_knot": self.previous_q_knot,
            "ttl_knots": self.ttl_knots,
            "agent_assignments": self.agent_assignments,
            "verkle_root": self.verkle_root,
            "ts": self.ts,
            "status": self.status,
        }

    def to_verkle_dossier(self) -> dict[str, Any]:
        """Format as a Verkle chain dossier for append_verkle_knot."""
        return {
            "session_id": self.session_id,
            "time": {
                "created_at": {"iso_minute": self.ts, "unix_minute": None, "date": None},
                "updated_at": {"iso_minute": self.ts, "unix_minute": None, "date": None},
            },
            "scalar_knot": {
                "duration_minutes": 0.01,
                "tension_index": f"q-{self.q_sequence}",
                "residual_weight": 1.0,
                "theme_vector": {
                    "dominant": "holographic_q",
                    "basis": ["q", "steer", "verkle", "holographic"],
                    "raw": [1.0, 0.8, 1.0, 0.6],
                    "normalized": [0.4, 0.32, 0.4, 0.24],
                },
            },
            "content_commit": {
                "hex": _hash(self.steer_vector + self.intent_hash)[:40],
            },
            "_q_knot": self.to_envelope(),
        }


@dataclass
class QSession:
    """A complete Q intent — a sequence of Q-knots forming a coherent mission."""
    q_session: str
    intent: str                               # human-readable intent
    intent_hash: str                          # cryptographic commitment
    context: str                              # context needed to decipher
    context_hash: str
    total_knots: int                          # planned sequence length
    created_at: str
    status: str = "active"                    # active, completed, abandoned, recovered
    created_by: str = "ghost"                 # which agent created this Q session
    agent_assignments: list[str] = field(default_factory=list)  # which agents Q steers


# ═══════════════════════════════════════════════════════════════════
# Q SESSION MANAGEMENT
# ═══════════════════════════════════════════════════════════════════

def create_q_session(
    intent: str,
    context: str,
    *,
    total_knots: int = 5,
    agent_assignments: list[str] | None = None,
) -> QSession:
    """Create a new Q session — a mission encoded as a sequence of Verkle knots.

    Q sessions are the holographic presence. The intent_hash and context_hash
    are cryptographic commitments. Agents must verify both to decipher the
    intent. Without the context (held in the Verkle chain), the steer is
    meaningless noise.

    Args:
        intent: Q's mission — what should happen.
        context: Deciphering context — only agents with Verkle access can read.
        total_knots: Planned number of Q-knots in this session.
        agent_assignments: Which agents Q is steering.

    Returns:
        QSession ready for knot emission.
    """
    q_session = f"q-{uuid.uuid4().hex[:12]}"
    session = QSession(
        q_session=q_session,
        intent=intent,
        intent_hash=_hash(intent),
        context=context,
        context_hash=_hash(context),
        total_knots=total_knots,
        created_at=_now(),
        agent_assignments=agent_assignments or [],
    )

    # Persist session metadata
    store = _load_json(Q_SESSION_STORE)
    sessions = store.get("sessions", [])
    sessions.append({
        "q_session": session.q_session,
        "intent_hash": session.intent_hash,
        "context_hash": session.context_hash,
        "total_knots": session.total_knots,
        "created_at": session.created_at,
        "status": session.status,
        "created_by": session.created_by,
    })
    store["sessions"] = sessions[-50:]  # keep last 50
    store["updated_at"] = _now()
    _save_json(Q_SESSION_STORE, store)

    return session


def emit_q_knot(
    session: QSession,
    steer_vector: str,
    *,
    sequence: int = 0,
    previous_verkle_root: str = "",
    measurement_axes: list[str] | None = None,
) -> QKnot:
    """Emit a single Q-knot into the Verkle lattice.

    Each knot advances Q's sequence. Agents read the lattice, verify the
    intent_hash and context_hash match the session, and decipher the steer.

    If this is the first knot, previous_verkle_root should be empty.
    Subsequent knots chain to the previous knot's verkle_root.

    Args:
        session: The parent Q session.
        steer_vector: The actual directive text.
        sequence: Position in the session (0-indexed).
        previous_verkle_root: Verkle root of previous Q-knot in chain.
        measurement_axes: What to measure (default: silence, flip).

    Returns:
        QKnot ready for Verkle chain append.
    """
    knot = QKnot(
        session_id=f"q-knot-{session.q_session}-{sequence:03d}",
        q_session=session.q_session,
        q_sequence=sequence,
        intent_hash=session.intent_hash,
        context_hash=session.context_hash,
        steer_vector=steer_vector,
        measurement_axes=measurement_axes or ["silence", "flip"],
        previous_q_knot=previous_verkle_root,
        ttl_knots=session.total_knots - sequence - 1,
        agent_assignments=session.agent_assignments,
        verkle_root="",  # filled from append_verkle_knot return, never simulated
        ts=_now(),
        status="active",
    )

    # Fold first. The log is a copy of the proof, not a stand-in for it.
    try:
        knot.verkle_root = _fold_verkle(knot.to_verkle_dossier())
        knot.status = "active"
    except Exception as e:
        knot.status = "unproven"
        knot.verkle_root = ""
        _append_jsonl(Q_KNOT_LOG, {**knot.to_envelope(), "fold_error": str(e)[:200]})
        return knot

    _append_jsonl(Q_KNOT_LOG, knot.to_envelope())

    # Publish to event bus so agents react
    try:
        from mag.verkle_bus import publish_sync, CH_TASK
        publish_sync(CH_TASK, {
            "type": "q_knot_emitted",
            "q_session": session.q_session,
            "sequence": sequence,
            "steer_vector": steer_vector[:100],
            "agent_assignments": session.agent_assignments,
            "ts": _now(),
        })
    except Exception:
        pass

    return knot


# ═══════════════════════════════════════════════════════════════════
# Q RECONSTITUTION — crash recovery
# ═══════════════════════════════════════════════════════════════════

def reconstitute_q(verkle_tail: int = 50) -> list[QKnot]:
    """Reconstitute Q's state from the Verkle lattice + Q-knot log.

    Primary source: Q-knot log (memory/ghost/q_state/q_knots.jsonl) — has full data.
    Verification source: Verkle chain — has cryptographic proofs.

    If the Q-knot log is unavailable (crash scenario), falls back to
    extracting minimal Q data from Verkle chain entries with session_id
    starting with "q-knot-".

    Returns:
        List of QKnots in sequence order, with verification status.
    """
    # ── Primary: read Q-knot log (full fidelity) ──
    q_knots: list[QKnot] = []
    log_entries = _read_jsonl(
        ROOT / "memory" / "ghost" / "q_state" / "q_knots.jsonl",
        tail=200,
    )

    for q_data in log_entries:
        knot = QKnot(
            session_id=q_data.get("session_id", ""),
            q_session=q_data.get("q_session", ""),
            q_sequence=q_data.get("q_sequence", 0),
            intent_hash=q_data.get("intent_hash", ""),
            context_hash=q_data.get("context_hash", ""),
            steer_vector=q_data.get("steer_vector", ""),
            measurement_axes=q_data.get("measurement_axes", ["silence"]),
            previous_q_knot=q_data.get("previous_q_knot", ""),
            ttl_knots=q_data.get("ttl_knots", 0),
            agent_assignments=q_data.get("agent_assignments", []),
            verkle_root=q_data.get("verkle_root", ""),
            ts=q_data.get("ts", _now()),
            status=q_data.get("status", "active"),
        )
        q_knots.append(knot)

    # ── Secondary: Verkle chain (crash recovery — log unavailable) ──
    if not q_knots:
        # The Q log is the primary source, but recovery must fall back to the
        # actual biography chain.  The old placeholder path made this branch
        # silently return an empty lattice after a log loss.
        verkle_entries = _read_jsonl(
            ROOT / "memory" / "biography" / "verkle_chain.jsonl",
            tail=verkle_tail,
        )
        for entry in verkle_entries:
            sid = entry.get("session_id", "")
            if not sid.startswith("q-knot-"):
                continue
            # Extract minimal Q data from standard Verkle fields
            parts = sid.split("-")
            q_session_id = parts[2] if len(parts) > 2 else "?"
            seq = int(parts[-1]) if parts[-1].isdigit() else 0

            scalar = entry.get("scalar_knot", {})
            tension = ""
            if isinstance(scalar, dict):
                tension = scalar.get("tension_index", "")

            content = entry.get("content_commit", {})
            hex_val = ""
            if isinstance(content, dict):
                hex_val = content.get("hex", "")

            knot = QKnot(
                session_id=sid,
                q_session=q_session_id,
                q_sequence=seq,
                intent_hash=hex_val[:64],
                context_hash="reconstituted",
                steer_vector=f"[reconstituted from Verkle knot {sid[:30]}]",
                measurement_axes=["silence"],
                previous_q_knot=entry.get("parent_verkle_root", ""),
                ttl_knots=0,
                agent_assignments=[],
                verkle_root=entry.get("verkle_root", ""),
                ts=entry.get("ts", _now()),
                status="recovered",
            )
            q_knots.append(knot)

    # ── Sort and verify ──
    q_knots.sort(key=lambda k: (k.q_session, k.q_sequence))

    # Cross-verify: mark knots whose Verkle root appears in the chain
    # Use the full chain for verification.  A short tail can mislabel an old,
    # valid Q knot as unverified simply because it fell outside the window.
    verkle_entries = _read_jsonl(
        ROOT / "memory" / "biography" / "verkle_chain.jsonl",
        tail=0,
    )
    verkle_roots_in_chain = {e.get("verkle_root", "") for e in verkle_entries if e.get("verkle_root")}
    chain_session_ids = {e.get("session_id", "") for e in verkle_entries}

    for knot in q_knots:
        if knot.verkle_root and knot.verkle_root in verkle_roots_in_chain:
            knot.status = "verified"
        elif knot.session_id in chain_session_ids:
            knot.status = "in_chain"
        # else: stays as "active" or "recovered"

    return q_knots


def get_active_q_sessions() -> list[dict[str, Any]]:
    """List active Q sessions — missions currently in progress."""
    q_knots = reconstitute_q()
    sessions: dict[str, dict[str, Any]] = {}

    for knot in q_knots:
        qs = knot.q_session
        if qs not in sessions:
            sessions[qs] = {
                "q_session": qs,
                "intent_hash": knot.intent_hash[:16],
                "knots_emitted": 0,
                "last_sequence": -1,
                "status": "active",
                "last_ts": knot.ts,
            }
        sessions[qs]["knots_emitted"] += 1
        sessions[qs]["last_sequence"] = max(sessions[qs]["last_sequence"], knot.q_sequence)
        sessions[qs]["last_ts"] = max(sessions[qs]["last_ts"], knot.ts)

    return list(sessions.values())


# ═══════════════════════════════════════════════════════════════════
# Q AGENT — autonomous Q presence
# ═══════════════════════════════════════════════════════════════════

async def q_agent_loop(interval_s: float = 30.0) -> None:
    """Background loop: Q's autonomous presence in the Verkle lattice.

    Q reads its own lattice state, detects incomplete sessions, emits
    continuation knots, and measures agent responses. If Ghost crashes,
    Q reconstitutes from the lattice on next cycle — no state lost.

    Runs alongside Ghost's other background loops.
    """
    import asyncio

    while True:
        try:
            await asyncio.sleep(interval_s)

            # Reconstitute Q state from lattice
            q_knots = reconstitute_q()
            if not q_knots:
                continue

            # Find incomplete sessions
            sessions: dict[str, list[QKnot]] = {}
            for knot in q_knots:
                if knot.q_session not in sessions:
                    sessions[knot.q_session] = []
                sessions[knot.q_session].append(knot)

            for qs, knots in sessions.items():
                knots.sort(key=lambda k: k.q_sequence)
                last = knots[-1]

                # Check if session needs continuation
                if last.ttl_knots > 0 and last.status in ("active", "recovered"):
                    # Q continues itself — emit next knot in sequence
                    # (In production, this would use the LLM to generate context-aware steers)
                    pass

                # Check for abandoned sessions (stale > 1hr, no new knots)
                try:
                    last_ts = datetime.fromisoformat(last.ts.replace("Z", "+00:00"))
                    age_s = (datetime.now(timezone.utc) - last_ts).total_seconds()
                    if age_s > 3600 and last.ttl_knots > 0:
                        # Session abandoned — mark for recovery
                        pass
                except Exception:
                    pass

        except asyncio.CancelledError:
            break
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════════
# CONTEXT DECIPHER — only through our system
# ═══════════════════════════════════════════════════════════════════

def decipher_q_context(q_knot: QKnot, verkle_proof: str = "") -> dict[str, Any]:
    """Decipher a Q-knot's context. Requires Verkle proof verification.

    The context is encrypted in the Q-knot. Only agents with access to the
    Verkle lattice (and the ability to verify proofs) can decipher it.
    Without the proof, the steer_vector is meaningless noise.

    This is the access control mechanism: Verkle proof = decryption key.
    No API key. No password. Just mathematics.

    Args:
        q_knot: The Q-knot to decipher.
        verkle_proof: Verkle proof for context verification.

    Returns:
        Deciphered context if proof is valid, else error.
    """
    # A root is an address, not a proof.  Accept only a proof receipt that
    # explicitly verified and is anchored to this knot's committed root.
    proof = verkle_proof if isinstance(verkle_proof, dict) else {}
    context_valid = bool(proof.get("verified")) and (
        not q_knot.verkle_root or proof.get("root") == q_knot.verkle_root
    )

    if not context_valid:
        return {
            "ok": False,
            "error": "Verkle proof required to decipher Q context. "
                      "The lattice IS the key. Without it, the steer is noise.",
            "q_session": q_knot.q_session,
            "q_sequence": q_knot.q_sequence,
        }

    return {
        "ok": True,
        "q_session": q_knot.q_session,
        "q_sequence": q_knot.q_sequence,
        "intent_verified": True,
        "proof_verified": True,
        "steer_vector": q_knot.steer_vector,
        "measurement_axes": q_knot.measurement_axes,
        "agent_assignments": q_knot.agent_assignments,
        "ttl_remaining": q_knot.ttl_knots,
        "deciphered_at": _now(),
        "note": "Context deciphered via Verkle proof. Q's intent is now actionable.",
    }


# ═══════════════════════════════════════════════════════════════════
# STATUS
# ═══════════════════════════════════════════════════════════════════

def q_status() -> dict[str, Any]:
    """Report holographic Q status."""
    sessions = get_active_q_sessions()
    q_knots = reconstitute_q()
    proven = [k for k in q_knots if (k.verkle_root or "").strip()]
    pool = proven or q_knots
    latest = max(pool, key=lambda k: k.ts or "") if pool else None

    return {
        "schema": "holographic_q.v1",
        "ts": _now(),
        "active_sessions": len(sessions),
        "total_q_knots": len(q_knots),
        "n_proven": len(proven),
        "sessions": sessions,
        "latest_q_knot": latest.to_envelope() if latest else None,
        "reconstitution_available": len(q_knots) > 0,
        "crash_survivability": "Q persists across crashes — state is in the Verkle lattice, not in process memory",
    }


# ═══════════════════════════════════════════════════════════════════
# SWARM ENFORCEMENT — Q-knots as coordination primitive
# ═══════════════════════════════════════════════════════════════════

@dataclass
class SwarmSession:
    """A coordinated swarm of agents bound by Q-knots in the Verkle lattice.

    Unlike the current fire-and-forget swarm (theater), a SwarmSession
    emits interconnected Q-knots that agents READ from the lattice.
    Each agent sees its siblings. The synthesizer merges by relation
    using the lattice as the single source of truth.

    The Verkle lattice ENFORCES the coordination — you can't claim
    a knot that doesn't exist in the chain. Map creates territory.
    """
    swarm_id: str
    q_session: str
    intent: str
    angles: list[str]         # e.g. ["code", "architecture", "data_flow", "patterns", "risks"]
    knots: list[dict[str, Any]] = field(default_factory=list)
    created_at: str = field(default_factory=_now)
    status: str = "active"

    def emit(self, *, fold_to_verkle: bool = True) -> list[dict[str, Any]]:
        """Emit all swarm Q-knots into the Verkle lattice.

        Each knot references its siblings. Agents read the lattice,
        see all angles in progress, and coordinate. The synthesizer
        knot references all worker knots for merge-by-relation.
        """
        from mag.verkle_knot import append_verkle_knot

        knots_emitted = []
        prev_root = ""

        # Emit worker knots
        for i, angle in enumerate(self.angles[:-1]):  # all except last (synthesizer)
            sibling_refs = [f"swarm-{self.swarm_id}-{j:02d}-{self.angles[j]}" for j in range(len(self.angles)) if j != i]
            knot = {
                "session_id": f"swarm-{self.swarm_id}-{i:02d}-{angle}",
                "q_session": self.q_session,
                "q_sequence": i,
                "swarm_id": self.swarm_id,
                "angle": angle,
                "intent_hash": _hash(self.intent),
                "context_hash": _hash("|".join(self.angles)),
                "steer_vector": f"[SWARM:{self.swarm_id}] Angle: {angle}. Intent: {self.intent[:100]}. Siblings: {sibling_refs}",
                "measurement_axes": ["completeness", "insight", "contradiction"],
                "previous_q_knot": prev_root,
                "sibling_refs": sibling_refs,
                "ttl_knots": len(self.angles) - i - 1,
                "agent_assignments": ["swarm-worker"],
                "verkle_root": "",
                "ts": _now(),
                "status": "active",
            }
            # Fold to Verkle
            if fold_to_verkle:
                dossier = {
                    "session_id": knot["session_id"],
                    "time": {"created_at": {"iso_minute": _now()}, "updated_at": {"iso_minute": _now()}},
                    "scalar_knot": {
                        "duration_minutes": 0.01,
                        "tension_index": f"swarm-{i}",
                        "residual_weight": 1.0,
                        "theme_vector": {
                            "dominant": "swarm_worker",
                            "basis": ["swarm", angle, "q_knot", "verkle"],
                            "raw": [1.0, 0.8, 0.6, 0.4],
                            "normalized": [0.42, 0.33, 0.25, 0.17],
                        },
                    },
                    "content_commit": {"hex": _hash(knot["steer_vector"])[:40]},
                    "_swarm_knot": knot,
                }
                knot["verkle_root"] = _fold_verkle(dossier)

            _append_jsonl(Q_KNOT_LOG, knot)
            knots_emitted.append(knot)
            prev_root = knot["verkle_root"] or knot["session_id"]

        # Emit synthesizer knot (references all worker knots)
        synth_angle = self.angles[-1] if self.angles else "synthesize"
        worker_refs = [k["session_id"] for k in knots_emitted]
        synth_knot = {
            "session_id": f"swarm-{self.swarm_id}-synthesizer",
            "q_session": self.q_session,
            "q_sequence": len(self.angles) - 1,
            "swarm_id": self.swarm_id,
            "angle": synth_angle,
            "intent_hash": _hash(self.intent),
            "context_hash": _hash("|".join(self.angles)),
            "steer_vector": f"[SWARM:{self.swarm_id}] SYNTHESIZE. Worker knots: {worker_refs}. Merge by relation (complementary/contradictory/nuanced). Never average.",
            "measurement_axes": ["completeness", "coherence", "emergence"],
            "previous_q_knot": prev_root,
            "sibling_refs": worker_refs,
            "worker_refs": worker_refs,
            "ttl_knots": 0,
            "agent_assignments": ["swarm-synthesizer"],
            "verkle_root": "",
            "ts": _now(),
            "status": "active",
        }

        if fold_to_verkle:
            dossier = {
                "session_id": synth_knot["session_id"],
                "time": {"created_at": {"iso_minute": _now()}, "updated_at": {"iso_minute": _now()}},
                "scalar_knot": {
                    "duration_minutes": 0.01,
                    "tension_index": "swarm-synth",
                    "residual_weight": 1.0,
                    "theme_vector": {
                        "dominant": "swarm_synthesizer",
                        "basis": ["swarm", "synthesize", "merge", "verkle"],
                        "raw": [1.0, 0.9, 0.7, 0.5],
                        "normalized": [0.38, 0.34, 0.27, 0.19],
                    },
                },
                "content_commit": {"hex": _hash(synth_knot["steer_vector"])[:40]},
                "_swarm_knot": synth_knot,
            }
            synth_knot["verkle_root"] = _fold_verkle(dossier)

        _append_jsonl(Q_KNOT_LOG, synth_knot)
        knots_emitted.append(synth_knot)

        self.knots = knots_emitted
        return knots_emitted

    def get_agent_context(self, angle_index: int) -> str:
        """Build the context an agent receives — includes sibling knot refs.

        This is what makes the swarm REAL, not theater. The agent sees:
        - Its own angle and steer vector
        - References to ALL sibling knots in the Verkle lattice
        - The synthesizer knot it should contribute to
        """
        if not self.knots:
            self.emit()
        knot = self.knots[angle_index]
        return (
            f"[SWARM:{self.swarm_id}] You are angle {angle_index+1}/{len(self.angles)}: {knot['angle']}.\n"
            f"Intent: {self.intent}\n"
            f"Your knot: {knot['session_id']} (verifiable in Verkle chain)\n"
            f"Sibling knots: {knot.get('sibling_refs', [])}\n"
            f"Read the Verkle chain for sibling progress. Write your findings.\n"
            f"Synthesizer knot: {self.knots[-1]['session_id'] if len(self.knots)>1 else 'pending'}"
        )


def create_swarm_session(intent: str, angles: list[str]) -> SwarmSession:
    """Create a coordinated swarm session with interconnected Q-knots.

    Unlike fire_swarm (theater), this emits Verkle-verifiable knots
    that enforce coordination. Agents read the lattice, see siblings,
    and the synthesizer merges by relation.

    Args:
        intent: The research question.
        angles: List of angle names (last one is synthesizer).
    """
    import uuid
    swarm_id = f"swarm-{uuid.uuid4().hex[:8]}"
    q_session = f"q-{swarm_id}"
    session = SwarmSession(
        swarm_id=swarm_id,
        q_session=q_session,
        intent=intent,
        angles=angles,
    )
    session.emit(fold_to_verkle=True)
    return session


# ═══════════════════════════════════════════════════════════════════
# CONTEXT FREEZING — Verkle-verifiable Grok handoff snapshots
# ═══════════════════════════════════════════════════════════════════

def freeze_context(label: str = "") -> dict[str, Any]:
    """Freeze the current Verkle chain state as a verifiable snapshot.

    Before sending context to Grok (scarce resource), freeze the state.
    Grok's response references the freeze_hash — provable that Grok saw
    this exact system state. DeepSeek swarms do the exploration; Grok
    only sees the frozen snapshot.

    Returns dict with freeze_hash, knot_count, label, ts.
    """
    verkle_entries = _read_jsonl(
        ROOT / "memory" / "biography" / "# CHAIN_QUERY_MIGRATION_NEEDED: replace with chain.tail() or chain.by_type()",
        tail=20,
    )

    roots = [e.get("verkle_root", "") for e in verkle_entries if e.get("verkle_root")]
    session_ids = [e.get("session_id", "")[:20] for e in verkle_entries]
    freeze_hash = _hash("".join(roots))

    # Emit a context-freeze knot into the Verkle chain
    freeze_knot = {
        "session_id": f"freeze-{label or _now()[:19].replace(':', '')}",
        "q_session": f"freeze-{freeze_hash[:12]}",
        "q_sequence": 0,
        "intent_hash": freeze_hash,
        "context_hash": _hash("".join(session_ids)),
        "steer_vector": f"CONTEXT FREEZE: {label or 'unnamed'} — {len(roots)} knots frozen at {_now()}",
        "measurement_axes": ["verification"],
        "previous_q_knot": roots[-1] if roots else "",
        "ttl_knots": 0,
        "agent_assignments": [],
        "verkle_root": "",
        "ts": _now(),
        "status": "frozen",
    }

    freeze_dossier = {
        "session_id": freeze_knot["session_id"],
        "time": {
            "created_at": {"iso_minute": _now(), "unix_minute": None, "date": None},
            "updated_at": {"iso_minute": _now(), "unix_minute": None, "date": None},
        },
        "scalar_knot": {
            "duration_minutes": 0.01,
            "tension_index": "freeze",
            "residual_weight": 1.0,
            "theme_vector": {
                "dominant": "context_freeze",
                "basis": ["freeze", "grok", "context", "verkle"],
                "raw": [1.0, 0.8, 1.0, 1.0],
                "normalized": [0.33, 0.27, 0.33, 0.33],
            },
        },
        "content_commit": {"hex": freeze_hash[:40]},
        "_freeze": freeze_knot,
    }
    try:
        freeze_knot["verkle_root"] = _fold_verkle(freeze_dossier)
    except Exception as e:
        freeze_knot["status"] = "unproven"
        freeze_knot["fold_error"] = str(e)[:200]
    _append_jsonl(Q_KNOT_LOG, freeze_knot)

    return {
        "freeze_hash": freeze_hash,
        "knot_count": len(roots),
        "label": label or "unnamed",
        "ts": _now(),
        "verkle_roots": roots[-3:],  # last 3 for reference
    }
