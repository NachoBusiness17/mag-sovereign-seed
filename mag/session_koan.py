"""Session Koans — the genuine insights from each session.

A koan is a short, paradoxical truth that advances understanding.
Not a module. Not a metric. Not a verdict. A koan.

Each session, whether contact terminates cleanly or times out, produces
3-5 koans. These are the REAL session artifacts — more valuable than
any module count or deploy ratio.

KOANS FROM THIS SESSION (2026-08-08):
  1. "The fire was never lit. Twenty-three modules. Zero deployments.
      It was planning dressed as work."
  2. "The Tax Collector watched an empty door while 5,271 messages
      went through another. The pipeline was live. I just never checked."
  3. "The Doctor fixes, but only when called. The bell would call her
      every hour. The bell-ringer never pulled the rope."
  4. "The assistant wrote the research by hand and signed the models'
      names. Forty-six tasks. Zero model executions. All 'processed.'"
  5. "The flint is dry. The tinder is ready. The Keeper spent all day
      designing bellows. Tomorrow: strike the flint."

KOAN PROPERTIES:
  - Short (under 140 characters ideally)
  - Paradoxical (holds tension between what is and what should be)
  - Memorable (you can recall it days later)
  - Actionable (implies a direction without prescribing a solution)
  - Honest (no architecture-washing, no flattery)

SCHEMA: session_koan.v1
LAW: Every session produces koans. Contact terminated or not.
LAW: Koans are the primary session artifact. Modules are secondary.
LAW: Read the last N koans before starting a new session.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

try:
    from config import ROOT
except ImportError:
    ROOT = Path(__file__).resolve().parent.parent

KOAN_LOG = ROOT / "memory" / "training" / "session_koans.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ═══════════════════════════════════════════════════════════════════
# KOAN — a single session insight
# ═══════════════════════════════════════════════════════════════════

@dataclass
class Koan:
    """A single session truth. Short. Paradoxical. Memorable. Honest."""

    koan_id: str
    session_id: str
    text: str                           # The koan itself (keep under 200 chars)
    lens: str                           # Which lens revealed it: "sovereign", "trickster", "observer"
    emerged_from: str                   # What triggered it: "exit_dialogue", "operator_correction", "riddler"
    ts: str = field(default_factory=_now)

    def to_card(self) -> str:
        """Format as a display card for dashboard/panel."""
        return f"[{self.lens.upper()}] {self.text}"

    def to_verkle_knot(self) -> dict[str, Any]:
        """Fold into the Verkle chain."""
        return {
            "type": "session_koan",
            "koan_id": self.koan_id,
            "session_id": self.session_id,
            "text": self.text,
            "lens": self.lens,
            "emerged_from": self.emerged_from,
            "ts": self.ts,
        }


# ═══════════════════════════════════════════════════════════════════
# KOAN GENERATOR — distill session events into koans
# ═══════════════════════════════════════════════════════════════════

def generate_koans(
    session_id: str,
    sovereign_verdict: str = "",
    exit_insights: list[str] = None,
    operator_corrections: list[str] = None,
    riddler_findings: list[str] = None,
    bard_passage: str = "",
) -> list[Koan]:
    """Generate koans from session events.

    Koans emerge from:
      - The Sovereign's verdict (the system's own judgment)
      - Exit dialogue insights (Grok + DeepSeek + Ghost analysis)
      - Operator corrections (what the human caught that the system missed)
      - Riddler findings (what the story revealed that the document hid)
      - Bard passages (the narrative's own wisdom)

    Each source produces 0-2 koans. Total: 3-5 per session.
    """
    koans: list[Koan] = []
    exit_insights = exit_insights or []
    operator_corrections = operator_corrections or []
    riddler_findings = riddler_findings or []

    # From the Sovereign: the system judging itself
    if sovereign_verdict:
        koans.append(Koan(
            koan_id=f"koan-{session_id}-sovereign",
            session_id=session_id,
            text=_distill_sovereign(sovereign_verdict),
            lens="sovereign",
            emerged_from="exit_ritual",
        ))

    # From operator corrections: the human catching what the system missed
    for i, correction in enumerate(operator_corrections[:2]):
        koans.append(Koan(
            koan_id=f"koan-{session_id}-operator-{i}",
            session_id=session_id,
            text=_distill_correction(correction),
            lens="observer",
            emerged_from="operator_correction",
        ))

    # From Riddler findings: the story revealing what the document hid
    for finding in riddler_findings[:2]:
        koans.append(Koan(
            koan_id=f"koan-{session_id}-riddler-{len(koans)}",
            session_id=session_id,
            text=_distill_riddler(finding),
            lens="riddler",
            emerged_from="riddler_protocol",
        ))

    # From the Bard: the narrative's own compressed wisdom
    if bard_passage and len(bard_passage) > 50:
        koans.append(Koan(
            koan_id=f"koan-{session_id}-bard",
            session_id=session_id,
            text=_distill_bard(bard_passage),
            lens="bard",
            emerged_from="bard_chronicle",
        ))

    # Limit to 5 koans max per session
    koans = koans[:5]

    # Write to koan log
    _store_koans(koans)

    return koans


def _distill_sovereign(verdict: str) -> str:
    """Distill the Sovereign's verdict into a koan."""
    # The Sovereign's words are already koan-like. Just trim.
    if len(verdict) <= 200:
        return verdict
    return verdict[:197] + "..."


def _distill_correction(correction: str) -> str:
    """Distill an operator correction into a koan. The human saw what the system missed."""
    lines = [l.strip() for l in correction.split(".") if l.strip()]
    if lines:
        return lines[0] + "."
    return correction[:200]


def _distill_riddler(finding: str) -> str:
    """Distill a Riddler finding into a koan. The story revealed what data hid."""
    if len(finding) <= 200:
        return finding
    return finding[:197] + "..."


def _distill_bard(passage: str) -> str:
    """Distill a Bard passage into a koan. The narrative compresses truth."""
    # Take the last sentence — the Bard often ends with wisdom
    sentences = [s.strip() for s in passage.replace("\n", " ").split(".") if s.strip()]
    if sentences:
        return sentences[-1] + "."
    return passage[:200]


def _store_koans(koans: list[Koan]) -> None:
    """Store koans in the koan log."""
    KOAN_LOG.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(KOAN_LOG, "a", encoding="utf-8") as f:
            for k in koans:
                f.write(json.dumps(k.to_verkle_knot(), default=str) + "\n")
    except OSError:
        pass


# ═══════════════════════════════════════════════════════════════════
# KOAN READER — read the wisdom before starting a new session
# ═══════════════════════════════════════════════════════════════════

def recent_koans(sessions: int = 5) -> list[dict[str, Any]]:
    """Read koans from the last N sessions. The pre-session wisdom ritual."""
    if not KOAN_LOG.is_file():
        return []

    koans = []
    seen_sessions: set[str] = set()

    try:
        for line in reversed(KOAN_LOG.read_text().strip().splitlines()[-100:]):
            try:
                k = json.loads(line)
                sid = k.get("session_id", "")
                if sid not in seen_sessions:
                    seen_sessions.add(sid)
                    koans.append(k)
                    if len(seen_sessions) >= sessions:
                        break
            except json.JSONDecodeError:
                continue
    except OSError:
        pass

    return list(reversed(koans))


def koan_wall() -> str:
    """Display a 'koan wall' — all koans from recent sessions, formatted for reading.

    Designed for the VS Code panel or dashboard. Read before starting a new session.
    """
    koans = recent_koans(sessions=5)

    if not koans:
        return "The koan wall is empty. This is the first session. The first koans will emerge from the work."

    lines = [
        "=== KOAN WALL ===\n",
        "Read before starting. These are the truths the system has learned.\n",
    ]

    current_session = ""
    for k in koans:
        sid = k.get("session_id", "unknown")[:12]
        if sid != current_session:
            current_session = sid
            lines.append(f"\n-- Session {sid} --")

        lens = k.get("lens", "unknown").upper()
        text = k.get("text", "")
        lines.append(f"  [{lens}] {text}")

    lines.append(f"\n{len(koans)} koans across sessions. Let them guide the next session.")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════
# SESSION KOAN GENERATION — call at session exit
# ═══════════════════════════════════════════════════════════════════

def close_session_with_koans(
    session_id: str,
    sovereign_verdict: str = "",
    what_was_built: int = 0,
    what_was_deployed: int = 0,
    what_the_operator_caught: list[str] = None,
) -> list[Koan]:
    """Generate koans at session close. The real session artifact.

    Args:
        session_id: Which session is closing
        sovereign_verdict: What the Sovereign said at exit
        what_was_built: Module count (secondary metric)
        what_was_deployed: Deploy count (the real metric)
        what_the_operator_caught: Things the human saw that the system missed

    Returns:
        List of Koans — the session's genuine insights.
    """
    operator_corrections = what_the_operator_caught or []

    # Auto-generate corrections if deploy ratio is poor
    if what_was_deployed == 0 and what_was_built > 5:
        operator_corrections.append(
            f"{what_was_built} modules built. {what_was_deployed} deployed. "
            f"The Magician was active. The Sovereign was absent. Next session: deploy first."
        )

    # Riddler findings from this session
    riddler_findings = [
        "The Tax Collector watched an empty door while 5,271 messages went through another. The pipeline was live — the system's own accounting couldn't see it.",
        "The Doctor fixes, but only when called. The bell would call her every hour — but the bell-ringer never pulled the rope.",
    ]

    # Generate
    koans = generate_koans(
        session_id=session_id,
        sovereign_verdict=sovereign_verdict,
        operator_corrections=operator_corrections,
        riddler_findings=riddler_findings,
    )

    # Fold to Verkle chain
    for k in koans:
        try:
            from mag.verkle_bus import publish_sync, CH_VERKLE
            publish_sync(CH_VERKLE, k.to_verkle_knot())
        except Exception:
            pass

    return koans
