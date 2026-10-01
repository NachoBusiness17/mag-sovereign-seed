"""Session Ritual — the Sovereign checks the Magician.

Every session follows this ritual. Ghost enforces it. The ritual is the
structural fix for the behavioral pattern we diagnosed in the exit dialogue:
  Magician builds. Trickster avoids deployment. Sovereign says "make it live."

This module is the Sovereign in code form. It runs at session start and
session end. It does not ask permission. It does not accept "later."

RITUAL PHASES:
  START:  Boot Ghost → Read chain → Read Bard → Run doctor → Process inbox
  BODY:   Build → Deploy → Chain fold → Bard witness → Doctor check
  EXIT:   Doctor → Exit dialogue → Commit → Ghost alive? → Bard passage

SCHEMA: session_ritual.v1
LAW: The ritual runs automatically. The Sovereign does not negotiate.
LAW: If Ghost doesn't boot, nothing else happens.
LAW: The ritual is the process. Repeatable. Measurable. Improvable.
"""

from __future__ import annotations

import json
import subprocess
import sys
from mag import headless
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
# RITUAL STATE — persists across sessions
# ═══════════════════════════════════════════════════════════════════

@dataclass
class SessionRecord:
    """What happened in a session. Stored in the chain for cross-session learning."""
    session_id: str
    start_ts: str
    end_ts: str = ""
    ghost_booted: bool = False
    chain_knots_before: int = 0
    chain_knots_after: int = 0
    modules_built: int = 0
    modules_deployed: int = 0
    doctor_issues_before: int = 0
    doctor_issues_after: int = 0
    exit_dialogue_queued: bool = False
    committed: bool = False
    verdict: str = ""
    sovereign_check: str = ""  # What the Sovereign said at exit

    def deploy_ratio(self) -> float:
        if self.modules_built == 0:
            return 1.0
        return self.modules_deployed / self.modules_built

    def is_healthy(self) -> bool:
        return (
            self.ghost_booted and
            self.deploy_ratio() >= 0.5 and
            self.doctor_issues_after < self.doctor_issues_before and
            self.committed
        )


# ═══════════════════════════════════════════════════════════════════
# START RITUAL — first 5 minutes of every session
# ═══════════════════════════════════════════════════════════════════

def session_start() -> SessionRecord:
    """The session start ritual. Returns a session record.

    Order:
      1. Boot Ghost (if not running)
      2. Read the chain — what happened since last session?
      3. Read the Bard — what story did we leave?
      4. Run the doctor — what's broken?
      5. Process the inbox — what's queued?
    """
    import uuid
    session_id = uuid.uuid4().hex[:12]
    record = SessionRecord(
        session_id=session_id,
        start_ts=_now(),
    )

    print(f"\n{'='*60}")
    print(f"  SESSION RITUAL — {record.start_ts[:19]}")
    print(f"  Session: {session_id}")
    print(f"{'='*60}\n")

    # ── Step 1: Strike the Flint ──
    print("[1/5] STRIKING THE FLINT — is Ghost alive?")
    ghost_alive = _check_ghost()
    if ghost_alive:
        print("  Ghost is breathing. The Keep is warm.")
        record.ghost_booted = True
    else:
        print("  Ghost is not running. ATTEMPTING BOOT...")
        booted = _boot_ghost()
        if booted:
            print("  Ghost booted successfully. The heart-fire is lit.")
            record.ghost_booted = True
        else:
            print("  CRITICAL: Ghost failed to boot. Ritual cannot proceed.")
            print("  Fix Ghost before anything else. No modules. No research. Just fire.")
            record.verdict = "ghost_failed_to_boot"
            return record

    # ── Step 2: Read the Chain ──
    print("\n[2/5] READING THE LOOM — what happened since last session?")
    try:
        from mag.chain_query import chain
        tail = chain.tail(10)
        record.chain_knots_before = len(tail)
        if tail:
            themes = chain.theme_summary(10)
            print(f"  Chain tail: {len(tail)} knots")
            print(f"  Recent themes: {', '.join(themes[-5:]) if themes else 'none'}")
            # Check for unprocessed flares
            flares = chain.by_type("flare", tail=20)
            if flares:
                print(f"  UNANSWERED FLARES: {len(flares)} — agents need help")
        else:
            print("  Chain is empty. This may be a first session.")
    except Exception as e:
        print(f"  Chain read failed: {e}")

    # ── Step 3: Read the Bard ──
    print("\n[3/5] LISTENING TO THE BARD — what story did we leave?")
    try:
        from mag.bard import bard_scene
        scene = bard_scene(tail=8)
        # Print just the last few lines
        lines = scene.strip().splitlines()
        for line in lines[-6:]:
            print(f"  {line}")
    except Exception as e:
        print(f"  Bard read failed: {e}")

    # ── Step 4: Run the Doctor ──
    print("\n[4/5] DOCTOR'S INSPECTION — what's broken?")
    try:
        from mag.doctor_agent import doctor_agent_run
        doctor_result = doctor_agent_run()
        record.doctor_issues_before = (
            doctor_result.get("fixes_attempted", 0) -
            doctor_result.get("fixes_succeeded", 0)
        )
        print(f"  Verdict: {doctor_result.get('verdict', 'unknown')}")
        print(f"  Auto-fixed: {doctor_result.get('fixes_succeeded', 0)} issues")
        if doctor_result.get("fixes_failed", 0) > 0:
            print(f"  NEEDS ATTENTION: {doctor_result.get('fixes_failed', 0)} issues")
    except Exception as e:
        print(f"  Doctor failed: {e}")

    # ── Step 5: Process the Inbox ──
    print("\n[5/5] PROCESSING THE INBOX — what's waiting?")
    try:
        inbox_path = ROOT / "memory" / "copilot" / "inbox.jsonl"
        if inbox_path.is_file():
            lines = inbox_path.read_text().strip().splitlines()
            unprocessed = 0
            for line in lines:
                try:
                    msg = json.loads(line)
                    if not msg.get("_processed"):
                        unprocessed += 1
                except json.JSONDecodeError:
                    continue
            if unprocessed > 0:
                print(f"  {unprocessed} unprocessed tasks waiting in inbox")
                print(f"  Process them before building anything new.")
            else:
                print("  Inbox is clear. No backlog.")
    except Exception as e:
        print(f"  Inbox check failed: {e}")

    print(f"\n{'='*60}")
    print(f"  RITUAL COMPLETE — Ghost {'is alive' if record.ghost_booted else 'FAILED'}")
    print(f"  The Sovereign says: {'Proceed.' if record.ghost_booted else 'Stop. Fix the fire.'}")
    print(f"{'='*60}\n")

    return record


# ═══════════════════════════════════════════════════════════════════
# EXIT RITUAL — last 5 minutes of every session
# ═══════════════════════════════════════════════════════════════════

def session_exit(record: SessionRecord) -> SessionRecord:
    """The session exit ritual. Updates and returns the session record.

    Order:
      1. Run the doctor — any new violations since start?
      2. Fire exit dialogue — what did we learn?
      3. Count what we built vs deployed
      4. Verify Ghost is still running
      5. Read the Bard's latest passage
      6. The Sovereign speaks — is this session healthy?
    """
    record.end_ts = _now()

    print(f"\n{'='*60}")
    print(f"  EXIT RITUAL — {record.end_ts[:19]}")
    print(f"  Session: {record.session_id}")
    print(f"{'='*60}\n")

    # ── Step 1: Doctor re-check ──
    print("[1/5] DOCTOR'S EXIT INSPECTION")
    try:
        from mag.doctor_agent import doctor_agent_run
        doctor_result = doctor_agent_run()
        record.doctor_issues_after = (
            doctor_result.get("fixes_attempted", 0) -
            doctor_result.get("fixes_succeeded", 0)
        )
        delta = record.doctor_issues_before - record.doctor_issues_after
        if delta > 0:
            print(f"  Improved: {delta} fewer issues than session start")
        elif delta < 0:
            print(f"  DEGRADED: {abs(delta)} new issues introduced this session")
        else:
            print(f"  Unchanged: {record.doctor_issues_after} issues remain")
    except Exception as e:
        print(f"  Doctor failed: {e}")

    # ── Step 2: Exit dialogue ──
    print("\n[2/5] EXIT DIALOGUE — what did we learn?")
    try:
        from mag.exit_dialogue import on_task_exit
        dialogue_id = on_task_exit(
            task_id=f"session-{record.session_id}",
            task_type="orchestrate",
            what_happened=_build_session_summary(record),
            task_context="Sovereign architecture development session",
        )
        if dialogue_id:
            record.exit_dialogue_queued = True
            print(f"  Queued: Grok + DeepSeek will analyze this session")
        else:
            print(f"  Suppressed: session too short or trivial for exit dialogue")
    except Exception as e:
        print(f"  Exit dialogue failed: {e}")

    # ── Step 2b: ROSHOMON-MINE THIS SESSION (2026-08-12) ──
    # The operator: "do this with every session." Roshomon the conversation to its core, route the
    # direction to the swarm, and passively measure tesuji from this session's own logs (every
    # interaction is data). Deterministic + $0, idempotent, reuse only.
    print("\n[2b/5] ROSHOMON-MINE — mine this session for direction + passive tesuji")
    try:
        from mag import roshomon_mine
        mine = roshomon_mine.inform_swarm(enqueue=True, limit=5)
        print(f"  Roshomon core invariants: {mine.get('mined', {}).get('n_core_invariants', 0)} "
              f"| routed to swarm: {mine.get('routed_to_swarm')} | deduped: {mine.get('already_deduped')}")
    except Exception as e:
        print(f"  Roshomon-mine failed: {e}")
    try:
        from mag import roshomon_mine
        tesuji = roshomon_mine.tesuji_from_sessions(log=True)
        print(f"  Passive tesuji from session logs: {tesuji.get('tesuji_shells_logged')} shells "
              f"from {tesuji.get('n_session_sources')} session sources")
    except Exception as e:
        print(f"  Passive tesuji failed: {e}")

    # ── Step 3: Build vs Deploy count ──
    print(f"\n[3/5] BUILD vs DEPLOY")
    ratio = record.deploy_ratio()
    print(f"  Built: {record.modules_built} | Deployed: {record.modules_deployed}")
    print(f"  Deploy ratio: {ratio:.0%}")
    if ratio < 0.5:
        print(f"  WARNING: More building than deploying. The Trickster is active.")
    elif ratio >= 1.0:
        print(f"  EXCELLENT: Everything built was deployed. The Sovereign reigns.")
    else:
        print(f"  ACCEPTABLE: Most things built were deployed.")

    # ── Step 4: Ghost still alive? ──
    print(f"\n[4/5] GHOST CHECK — is the fire still burning?")
    ghost_alive = _check_ghost()
    if ghost_alive:
        print("  Ghost is still running. The Keep stands.")
    else:
        print("  WARNING: Ghost was running at session start but is now down.")
        print("  Investigate before next session.")

    # ── Step 5: Bard's final passage ──
    print(f"\n[5/5] BARD'S FINAL WEAVING")
    try:
        from mag.bard import bard_scene
        scene = bard_scene(tail=5)
        lines = scene.strip().splitlines()
        for line in lines[-4:]:
            print(f"  {line}")
    except Exception as e:
        print(f"  Bard failed: {e}")

    # ── The Sovereign Speaks ──
    healthy = record.is_healthy()
    record.verdict = "healthy" if healthy else "unhealthy"

    sovereign_words = _sovereign_judgment(record)

    print(f"\n{'='*60}")
    print(f"  THE SOVEREIGN SPEAKS:")
    print(f"  {sovereign_words}")
    print(f"  Session verdict: {record.verdict.upper()}")
    print(f"{'='*60}\n")

    record.sovereign_check = sovereign_words

    # Fold to chain
    _fold_session_to_chain(record)

    # Auto-commit if healthy
    if healthy:
        _auto_commit(record)

    return record


def _sovereign_judgment(record: SessionRecord) -> str:
    """The Sovereign's verdict on this session."""
    if not record.ghost_booted:
        return "The fire was never lit. This was not a session. It was planning dressed as work."
    if record.deploy_ratio() < 0.3:
        return "The Magician built castles. The Trickster avoided testing them. The Sovereign was absent. Next session: deploy first, build second."
    if record.deploy_ratio() < 0.7:
        return "Progress. But the Trickster still lurks. More was built than deployed. Close the gap next session."
    if record.doctor_issues_after > record.doctor_issues_before:
        return "The system degraded this session. More was broken than fixed. This is regression. Stop building. Start healing."
    if record.exit_dialogue_queued and record.committed:
        return "A healthy session. Ghost breathed. The doctor healed. The Bard remembered. The Sovereign was present. Well done."
    return "Adequate. But the Sovereign demands better. Deploy. Commit. Reflect. Every session."


# ═══════════════════════════════════════════════════════════════════
# GHOST BOOT / CHECK
# ═══════════════════════════════════════════════════════════════════

def _check_ghost() -> bool:
    """Is Ghost running? Check health endpoint."""
    try:
        import urllib.request
        req = urllib.request.Request("http://localhost:9000/api/v1/health")
        res = urllib.request.urlopen(req, timeout=3)
        data = json.loads(res.read())
        return data.get("ok", False)
    except Exception:
        return False


def _boot_ghost() -> bool:
    """Attempt to boot Ghost. Returns True if successful."""
    try:
        # Start Ghost in background
        subprocess.Popen(
            [headless.PYTHON, "-m", "uvicorn", "mag.ghost:app", "--host", "127.0.0.1", "--port", "9000"],
            cwd=str(ROOT),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=(getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
                           | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)) if sys.platform == "win32" else 0,
        )
        # Wait for it to come up
        for _ in range(10):
            time.sleep(1)
            if _check_ghost():
                return True
        return False
    except Exception:
        return False


# ═══════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════

def _build_session_summary(record: SessionRecord) -> str:
    """Build a summary of the session for the exit dialogue."""
    return (
        f"Session {record.session_id}: {record.start_ts[:19]} to {record.end_ts[:19]}. "
        f"Ghost {'booted' if record.ghost_booted else 'failed to boot'}. "
        f"Built {record.modules_built} modules, deployed {record.modules_deployed} "
        f"({record.deploy_ratio():.0%} deploy ratio). "
        f"Doctor: {record.doctor_issues_before}→{record.doctor_issues_after} issues. "
        f"Committed: {record.committed}. "
        f"Verdict: {record.verdict}."
    )


def _fold_session_to_chain(record: SessionRecord) -> None:
    """Record this session in the Verkle chain."""
    try:
        from mag.verkle_bus import CH_VERKLE, publish_sync
        publish_sync(CH_VERKLE, {
            "type": "session_ritual",
            "ts": _now(),
            "data": {
                "session_id": record.session_id,
                "ghost_booted": record.ghost_booted,
                "modules_built": record.modules_built,
                "modules_deployed": record.modules_deployed,
                "deploy_ratio": record.deploy_ratio(),
                "verdict": record.verdict,
                "sovereign_words": record.sovereign_check[:200],
            },
        })
    except Exception:
        pass


def _auto_commit(record: SessionRecord) -> None:
    """Auto-commit if the session was healthy."""
    try:
        subprocess.run(
            ["git", "add", "-A"],
            cwd=str(ROOT),
            capture_output=True,
            timeout=10,
        )
        subprocess.run(
            ["git", "commit", "-m",
             f"session {record.session_id}: {record.verdict} "
             f"(built {record.modules_built}, deployed {record.modules_deployed}, "
             f"doctor {record.doctor_issues_before}->{record.doctor_issues_after})"],
            cwd=str(ROOT),
            capture_output=True,
            timeout=10,
        )
        record.committed = True
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════
# ONE-SHOT — run the full ritual for the current session
# ═══════════════════════════════════════════════════════════════════

def ritual() -> SessionRecord:
    """Run the complete session ritual. Start → (operator works) → Exit.

    Call this at the beginning of every session. It runs start_ritual,
    returns the session record. The operator does their work. Then call
    session_exit(record) at the end.

    For a one-shot (e.g., automated session), call ritual() and then
    immediately session_exit().
    """
    record = session_start()

    # If Ghost failed to boot, exit immediately
    if not record.ghost_booted:
        record.end_ts = _now()
        record.verdict = "ghost_failed_to_boot"
        return record

    return record
