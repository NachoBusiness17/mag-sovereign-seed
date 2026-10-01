"""Agent Compass — the sovereign steering anchor (DeepSeek share zfm168h68wh5fnt6hi).

When the operator types something ambiguous ("continue", "go", "steer ..."), or the
collapse detector spots a loop, the CLI injects a Compass preamble: Constitution
(moral law) + Blueprint (active plan) + Last state (bead) + Case law (decision log)
+ Differential state (git diff) + Mandate (autonomous 4-step protocol).

The model is fed rigid rules (system) + immutable facts (compass) + the operator's
steering word — so it cannot default to wheel-spinning. Case law: past !steer
decisions are precedent unless explicitly overridden.

Data tier: T2 local. Never reads .env. Diff is scoped to memory/ and filtered.
"""
from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT

DECISIONS_LOG = ROOT / "memory" / "decisions_log.jsonl"
def decisions_log_path() -> Path:
    """B2-403 (2026-09-26): the decisions sink is redirectable.

    Tests exercising the real run_turn/drain machinery appended case-law
    rows into PRODUCTION memory/decisions_log.jsonl (measured:
    test_t1_steering +3/run, test_repack_integration +104/run) and could
    consume real pending operator guidance mid-test. Setting
    MAG_DECISIONS_LOG redirects every record_decision write; production
    default is unchanged when the env is absent.
    """
    env = os.environ.get("MAG_DECISIONS_LOG")
    return Path(env) if env else DECISIONS_LOG
BLUEPRINT = ROOT / "memory" / "plans" / "sovereign-steering-engine-plan-2026-08-03.md"
ANCHOR = ROOT / "memory" / "plans" / "ANCHOR.md"
LAST_STATE = ROOT / "memory" / "agent_state" / "LATEST.md"
CONSTITUTION = ROOT.parent / "mycelial-republic" / "docs" / "CONSTITUTION.md"
CONSTITUTION_FALLBACK = ROOT / "CONSTITUTION.md"

# Short / ambiguous inputs that should never go to the model raw — they trigger the compass.
_AMBIGUOUS = {
    "continue", "go", "next", "again", "and", "yes", "y", "steer",
    "continue.", "go.", "next.", "keep going", "keep going.", "keep", "more",
}

MANDATE = """\
[MANDATE — AUTONOMOUS DECISION]
Based on the Constitution, the Blueprint, the Last State and the Case Law above,
make the sovereign next decision now:
1. Assess whether the active Blueprint step is complete (read the Blueprint, do not guess).
2. If not complete, identify the next blocked step in the Blueprint.
3. Execute step 1 of that next step immediately — call real tools, no permission asks.
4. If no step is blocked, pick the highest-priority task that aligns with the
   Constitution and the recent decision precedents, and execute it.
State which precedent / blueprint item dictates your choice before the first tool call.
"""

FRAMEWORK_BLOCK = """\
## Sovereign agent framework (governor — immutable)
- Pre-tool check: never call a tool without stating which Blueprint step it serves.
- Status signal: after every 3 consecutive tool calls, emit a 1-sentence heartbeat `[Status: <file/step>]`.
- Self-healing: on ok=False parse the error, re-evaluate against the Blueprint, try a revised approach; 3 sequential failures -> halt with `[CRITICAL: file error]`.
- Steering: `!steer <context>` is a manual override — absorb it, adjust the plan, continue from the interruption point without restarting.
- Anchor: Blueprint + Decision Log are immutable facts. Do not hallucinate their existence.
- Zero metadata: translate tool results into plain English; no raw JSON dumps, no empty strings.
- Context management: on degraded/blank state, ignore your last 5 steps; re-anchor to the last successful bead and the active Blueprint.
- Case law: treat past steer decisions as legal precedent; default to them in similar futures unless explicitly overridden.
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clip(text: str, n: int) -> str:
    text = (text or "").strip()
    return text[-n:] if len(text) > n else text


def _first(text: str, n: int) -> str:
    text = (text or "").strip()
    return text[:n] if len(text) > n else text


def _read(p: Path, *, tail: int | None = None, head: int | None = None) -> str:
    try:
        if not p.is_file():
            return ""
        t = p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""
    if tail is not None:
        t = _clip(t, tail)
    if head is not None:
        t = _first(t, head)
    return t.strip()


def constitution_text(max_chars: int = 900) -> str:
    for p in (CONSTITUTION, CONSTITUTION_FALLBACK):
        t = _read(p, head=max_chars)
        if t:
            return t
    return ("Constitution file missing — apply data tiers T0-T3; "
            "T0/T1 never leave this machine; irreversible acts need the operator's nod.")


def blueprint_text(max_chars: int = 1100) -> str:
    for p in (BLUEPRINT, ANCHOR):
        t = _read(p, head=max_chars)
        if t:
            return t
    return "(no blueprint file found)"


def last_state_text(max_chars: int = 900) -> str:
    for p in (LAST_STATE, ROOT / "memory" / "working.md"):
        t = _read(p, tail=max_chars)
        if t:
            return t
    return "(no bead file found)"


def recent_decisions(n: int = 3) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not DECISIONS_LOG.is_file():
        return out
    try:
        lines = [l for l in DECISIONS_LOG.read_text(encoding="utf-8").splitlines() if l.strip()]
    except Exception:
        return out
    for line in lines[-n:]:
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def record_decision(context: str, steer_input: str, outcome: str) -> bool:
    """Append one !steer event to the decision log (case law for future compasses)."""
    entry = {"timestamp": _now(), "context": context,
             "steer_input": steer_input, "outcome": outcome}
    try:
        log_path = decisions_log_path()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return True
    except Exception:
        return False


def differential_state(max_chars: int = 700) -> str:
    """git diff of memory/ since HEAD — only the changed lines (token-cheap focus)."""
    if not (ROOT / ".git").is_dir():
        return ""
    try:
        r = _run(["git", "-C", str(ROOT), "diff", "--stat", "--", "memory/"])
        if not r or not r[0]:
            return ""
        r2 = _run(["git", "-C", str(ROOT), "diff", "-U1", "--", "memory/"])
        diff = (r2[0] or "").strip() if r2 else ""
    except Exception:
        return ""
    if not diff:
        return ""
    # never leak secrets into the compass
    banned = ("secret", ".env", "password", "token", "api key", "credential")
    if any(b in diff.lower() for b in banned):
        return ""
    return _first(diff, max_chars)


def _run(cmd: list[str]) -> tuple[str | None, int]:
    """Shell out for git diff (graceful when git is missing)."""
    import subprocess
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=10, encoding="utf-8", errors="replace")
        return (r.stdout or "", r.returncode)
    except Exception:
        return (None, -1)


def build_compass(*, steer_text: str | None = None, reason: str = "input") -> str:
    """The context anchor injected before the operator's raw words.

    reason: 'input' (ambiguous word), 'steer' (manual override), 'loop' (auto-detected).
    """
    const = constitution_text()
    blue = blueprint_text()
    state = last_state_text()
    deci = recent_decisions(3)
    diff = differential_state()

    case_law = "\n".join(
        f"- {d.get('timestamp', '?')[:16]} steer: {_first(str(d.get('steer_input', '')), 90)}"
        for d in deci
    ) or "(no decision precedents yet — the Constitution is the only law)"

    diff_block = (
        f"\n[DIFFERENTIAL STATE]\nSince the last look, these lines changed in memory/:\n{diff}\n"
        if diff
        else ""
    )

    why = {
        "input": "The operator's input was ambiguous. Do not guess what it means — decide from the anchors below.",
        "steer": "The operator issued a manual steer. Absorb it as an override of the current plan and continue from the interruption point.",
        "loop": "A degenerate tool loop was detected. Ignore your last 3 actions; re-anchor to the Blueprint and restart from there.",
    }.get(reason, "Re-anchor to the Blueprint and act.")

    steer_note = f"\n[OPERATOR STEER]\n{steer_text}\n" if steer_text else ""

    return f"""[SYSTEM OVERRIDE: AGENT COMPASS ENGAGED]
Reason: {why}

[CONSTITUTIONAL PILLARS]
{const}

[ACTIVE BLUEPRINT]
{blue}

[LAST SUCCESSFUL STATE]
{state}

[RECENT DECISION PRECEDENTS (case law)]
{case_law}
{diff_block}
{steer_note}
{MANDATE}
"""


def should_compass(text: str) -> bool:
    """True when the raw operator input is too ambiguous to send alone."""
    low = (text or "").strip().lower().strip("! .")
    if low in _AMBIGUOUS:
        return True
    if low.startswith("steer"):
        return True
    if low in ("continue", "go"):
        return True
    return False
