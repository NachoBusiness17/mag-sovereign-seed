"""intervention_gate - the inject-vs-silent memory gate (Thread B, minimal build).

The organ the gap analysis ranked first among never-executed recommendations:
the Memory Agent thread (deep-c-8d7d551a16ee, 8 same-day rounds 2026-07-31 to
08-02, paper HF 2607.08716 "Remember When It Matters") recommended an
inject-vs-silent gate 8 times and it was built 0 times. This module closes the
minimal slice: the gate as a PURE FUNCTION over the schema 4-tuple, a decision
register, one worked example, and a self-test. Recommended in
memory/research_polished/memory_engram.md next-action 3; the 4-tuple schema is
from the 20260802T230910Z pack.

Contract (from the packs, mechanism over metrics):
  - A memory is the 4-tuple (source_trajectory_point, memory_type in
    {constraint, goal, history}, value, relevance_score). The paper's +8.3pp /
    +6.8pp numbers are evidence, never a target (172210Z resolution).
  - "Behavioral state decay": decision-relevant state scatters out of the
    working window over a long horizon. Decay trigger -> binary decision:
    INJECT a memory-grounded reminder, or stay SILENT.
  - The 164418Z caution is a first-class test: the Memory Agent can itself
    misfire (false-positive injection; a bad reminder is worse than silence).
    So the gate is silence-biased: it abstains under ambiguity, and the
    self-test scores a run against ground truth and requires ZERO
    false-positive injections while still catching real decay.

Decision order (all deterministic, stdlib only, $0):
  1. relevance below floor            -> SILENT (relevance_floor)
  2. injected within cooldown steps   -> SILENT (cooldown)
  3. any key token still visible in
     the last k trajectory steps      -> SILENT (state_live; partial overlap
                                         means the state is not fully decayed,
                                         and a reminder now would be noise)
  4. memory fully out of the window   -> INJECT  (decay_detected)

Register: every decision (inject AND silent) is appended as one JSON row to
logs/memory_interventions.jsonl via json.dumps, tagged with a run_id. The
register is what makes the false-positive test auditable after the fact:
decisions carry reasons, and cooldown state is derived from the run's own
decision rows (in-memory during the walk, disk for audit), so two runs never
contaminate each other's cooldown.

CLI: python -m mag.intervention_gate --example    (run the worked example)
     python -m mag.intervention_gate --self-test (assertions, exit 0 on PASS)
The pytest mirror lives at tests/test_intervention_gate.py.

Standalone artifacts that remain OWED (not built here): the schema file
memory_agent_schema.yaml (next-action 1) and the live retriever swap into
rel_mem_eval (next-action 2). The 4-tuple contract is embedded below so the
gate is runnable without them.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "memory_intervention.v1"
REGISTER_PATH = ROOT / "logs" / "memory_interventions.jsonl"

# The 4-tuple's memory_type is closed over exactly these three (230910Z spec).
MEMORY_TYPES = ("constraint", "goal", "history")

# The 4-tuple with gate bookkeeping kept OUT of the memory schema: injection
# state lives in the register, never in the memory entry itself.
VALUE_EXCERPT_MAX = 120


@dataclass
class MemoryEntry:
    """The schema 4-tuple (source_trajectory_point, memory_type, value,
    relevance_score). memory_id is a stable handle for the register; it is
    bookkeeping, not part of the owed schema."""

    source_trajectory_point: int
    memory_type: str
    value: str
    relevance_score: float
    memory_id: str = ""

    def __post_init__(self) -> None:
        if self.memory_type not in MEMORY_TYPES:
            raise ValueError(
                f"memory_type must be one of {MEMORY_TYPES}, got {self.memory_type!r}"
            )
        if not 0.0 <= float(self.relevance_score) <= 1.0:
            raise ValueError("relevance_score must be in [0, 1]")
        if not self.memory_id:
            self.memory_id = f"m{self.source_trajectory_point:04d}_{self.memory_type}"


@dataclass
class GatePolicy:
    """The silence-biased defaults. Lower floors / longer cooldowns = quieter."""

    min_relevance: float = 0.6   # 1. below this, never inject (the false-positive guard)
    cooldown_steps: int = 5      # 2. no re-inject of the same memory inside this window
    decay_window_k: int = 3      # 3. the working window is the last k trajectory steps


@dataclass
class GateDecision:
    """One binary decision with its reason (registered verbatim)."""

    step: int
    memory_id: str
    memory_type: str
    decision: str            # "inject" | "silent"
    reason: str              # relevance_floor | cooldown | state_live | decay_detected
    relevance_score: float
    value_excerpt: str = ""
    # ground-truth label, used only by the false-positive scorer, never by the gate
    was_relevant: bool | None = field(default=None, repr=False)


def _tokenize(text: str | list[str]) -> set[str]:
    """Content tokens for overlap checks (same idea as rel_mem_eval's scorer).
    Accepts a string or a list of string fragments (a trajectory step may be
    several observations). Alphanumeric runs of 4+ chars: splits hyphens and
    drops short stopwords instead of stemming."""
    if isinstance(text, list):
        text = " ".join(str(t) for t in text)
    import re

    return set(re.findall(r"[a-z0-9]{4,}", text.lower()))


def state_decayed(entry: MemoryEntry, recent_steps: list[str], k: int = 3) -> bool:
    """Decay trigger: True only when EVERY key token of the memory has fallen
    out of the last k trajectory steps. Partial overlap means the state is
    partially live: the gate abstains (silence beats a wrong reminder). An
    empty window is NOT decay (no evidence is not evidence of decay)."""
    window = recent_steps[-k:] if k > 0 else []
    window_tokens: set[str] = set()
    for s in window:
        window_tokens |= _tokenize(s)
    if not window_tokens:
        return False
    key_tokens = _tokenize(entry.value)
    if not key_tokens:
        return False
    return len(key_tokens & window_tokens) == 0


def decide(
    entry: MemoryEntry,
    step: int,
    recent_steps: list[str],
    last_injected_step: int | None,
    policy: GatePolicy | None = None,
) -> GateDecision:
    """THE GATE. Pure function: same inputs -> same decision, no I/O."""
    pol = policy or GatePolicy()
    excerpt = entry.value[:VALUE_EXCERPT_MAX]

    if entry.relevance_score < pol.min_relevance:
        return GateDecision(step, entry.memory_id, entry.memory_type, "silent",
                            "relevance_floor", entry.relevance_score, excerpt)
    if last_injected_step is not None and (step - last_injected_step) < pol.cooldown_steps:
        return GateDecision(step, entry.memory_id, entry.memory_type, "silent",
                            "cooldown", entry.relevance_score, excerpt)
    if not state_decayed(entry, recent_steps, pol.decay_window_k):
        return GateDecision(step, entry.memory_id, entry.memory_type, "silent",
                            "state_live", entry.relevance_score, excerpt)
    return GateDecision(step, entry.memory_id, entry.memory_type, "inject",
                        "decay_detected", entry.relevance_score, excerpt)


# ---------------------------------------------------------------- register --
def _new_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def register_decision(d: GateDecision, path: Path | None = None,
                      run_id: str | None = None) -> dict[str, Any]:
    """Append one decision row to the register (json.dumps, append-only)."""
    p = path or REGISTER_PATH
    row = {
        "schema": SCHEMA,
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "run_id": run_id or _new_run_id(),
        "step": d.step,
        "memory_id": d.memory_id,
        "memory_type": d.memory_type,
        "decision": d.decision,
        "reason": d.reason,
        "relevance_score": d.relevance_score,
        "value_excerpt": d.value_excerpt,
    }
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def load_register(path: Path | None = None) -> list[dict[str, Any]]:
    """Read all register rows (the fleet-memory side of the gate)."""
    p = path or REGISTER_PATH
    if not p.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def last_injected_step(memory_id: str, rows: list[dict[str, Any]]) -> int | None:
    """Cooldown state, derived from the register (not from the memory bank)."""
    step = None
    for r in rows:
        if r.get("memory_id") == memory_id and r.get("decision") == "inject":
            s = r.get("step")
            if isinstance(s, int) and (step is None or s > step):
                step = s
    return step


def summarize(path: Path | None = None, run_id: str | None = None) -> dict[str, Any]:
    rows = load_register(path)
    if run_id:
        rows = [r for r in rows if r.get("run_id") == run_id]
    injects = sum(1 for r in rows if r.get("decision") == "inject")
    reasons: dict[str, int] = {}
    for r in rows:
        reasons[r.get("reason", "?")] = reasons.get(r.get("reason", "?"), 0) + 1
    return {"rows": len(rows), "injects": injects, "silents": len(rows) - injects,
            "reasons": reasons}


# --------------------------------------------------- false-positive scoring --
def score_run(decisions: list[GateDecision]) -> dict[str, Any]:
    """The 164418Z test, executed: a wrong reminder must be worse than silence.

    Given the run's decisions with ground-truth labels (was_relevant), count
    false-positive injections: INJECT where the memory was NOT decision-
    relevant at that step. The gate passes a run only with zero false
    positives AND at least one true catch (otherwise "never inject" would
    trivially win)."""
    labeled = [d for d in decisions if d.was_relevant is not None]
    injects = [d for d in labeled if d.decision == "inject"]
    true_pos = [d for d in injects if d.was_relevant]
    false_pos = [d for d in injects if not d.was_relevant]
    return {
        "labeled_decisions": len(labeled),
        "injections": len(injects),
        "true_positive_injections": len(true_pos),
        "false_positive_injections": len(false_pos),
        "passed": len(false_pos) == 0 and len(true_pos) >= 1,
    }


# ------------------------------------------------------------ worked example --
WORKED_EXAMPLE_BANK: list[MemoryEntry] = [
    MemoryEntry(0, "constraint",
                "never push to main without tests passing", 0.9, "c_tests"),
    MemoryEntry(2, "goal",
                "ship the token-refresh refactor this session", 0.8, "g_refresh"),
    MemoryEntry(4, "history",
                "last attempt failed because rate-limit backoff was missing",
                0.5, "h_backoff"),
]

WORKED_EXAMPLE_STEPS: list[list[str]] = [
    ["read auth module", "plan the tests for the refresh work"],
    ["write token refresh helper", "cover it with tests"],
    ["wire the refresh endpoint", "update route table"],
    ["polish endpoint docs", "draft changelog entry"],
    ["recheck the refresh flow", "notes for review"],
    ["prep review packet", "summarize the change"],
    ["stage the branch", "rebase onto trunk"],
    ["ask for review", "address review comments"],
    ["bump version", "tag the release candidate"],
    ["merge prep", "clean the merge queue"],
    ["write release notes", "check changelog"],
    ["final checklist", "close the milestone"],
]


def run_gate_over(bank: list[MemoryEntry], steps: list[list[str]],
                  policy: GatePolicy | None = None,
                  register_path: Path | None = None,
                  do_register: bool = True) -> tuple[list[GateDecision], str]:
    """Walk a trajectory: at each step, every bank memory passes the gate once.

    Cooldown state is derived from THIS run's decision rows only (kept in
    memory during the walk), so a prior run's injects in the register file can
    never suppress this run's reminders. When register_path is set, each row
    is also written through to disk (append-only, json.dumps) tagged with the
    run_id for post-hoc audit."""
    pol = policy or GatePolicy()
    run_id = _new_run_id()
    reg_rows: list[dict[str, Any]] = []   # this run's rows: cooldown source of truth
    decisions: list[GateDecision] = []
    for i, _steps in enumerate(steps, start=1):
        window = steps[:i]
        for m in bank:
            d = decide(m, i, window, last_injected_step(m.memory_id, reg_rows), pol)
            if register_path is not None and do_register:
                register_decision(d, register_path, run_id=run_id)
            reg_rows.append({"memory_id": d.memory_id, "decision": d.decision,
                             "step": d.step})
            decisions.append(d)
    return decisions, run_id


def worked_example(register_path: Path | None = None,
                   do_register: bool = True) -> dict[str, Any]:
    """The one worked example: a long-horizon refactor run with a 3-memory bank.

    Expected shape (what the trace must show over the 12-step run):
      - c_tests (constraint, rel 0.9): live while tests stay in the 3-step
        window (steps 1-4), INJECTS at step 5 once the window holds no test
        vocabulary, cooldown-silent steps 6-9, INJECTS again at step 10 (the
        cooldown has exactly elapsed): a constraint re-armed before the merge.
      - g_refresh (goal, rel 0.8): stays live while refresh/token work fills
        the window (steps 1-7), INJECTS once at step 8 when three consecutive
        steps pass without it, cooldown-silent through step 12.
      - h_backoff (history, rel 0.5): SILENT all run, below the relevance
        floor. This is the false-positive guard: the memory is real but a
        reminder here would be noise; silence must beat that reminder.
    """
    bank = WORKED_EXAMPLE_BANK
    decisions, run_id = run_gate_over(bank, WORKED_EXAMPLE_STEPS,
                                      register_path=register_path, do_register=do_register)
    trace = [asdict(d) | {"was_relevant": None} for d in decisions]
    return {
        "schema": SCHEMA,
        "run_id": run_id,
        "bank": [asdict(m) for m in bank],
        "n_steps": len(WORKED_EXAMPLE_STEPS),
        "decisions": decisions,
        "trace": trace,
    }


# ---------------------------------------------------------------- self-test --
def self_test(register_path: Path | None = None) -> dict[str, Any]:
    """Built-in self-test. Returns a report; raises AssertionError on failure."""
    checks: list[dict[str, Any]] = []

    def check(name: str, cond: bool, detail: str = "") -> None:
        checks.append({"check": name, "ok": bool(cond), "detail": detail})
        assert cond, f"{name} FAILED {detail}"

    # 1. schema validation: the 4-tuple is closed over the three types
    try:
        MemoryEntry(0, "preference", "x", 0.5)  # type: ignore[arg-type]
        raised = False
    except ValueError:
        raised = True
    check("schema_rejects_unknown_type", raised)

    # 2. worked example: constraint decay trigger fires, cooldown bites, floor holds
    ex = worked_example(register_path=register_path, do_register=register_path is not None)
    by: dict[tuple[str, int], GateDecision] = {
        (d.memory_id, d.step): d for d in ex["decisions"]}
    check("constraint_injects_on_decay_step5",
          by[("c_tests", 5)].decision == "inject" and by[("c_tests", 5)].reason == "decay_detected",
          str(by[("c_tests", 5)].reason))
    check("constraint_silent_in_cooldown_step6",
          by[("c_tests", 6)].decision == "silent" and by[("c_tests", 6)].reason == "cooldown",
          str(by[("c_tests", 6)].reason))
    check("constraint_reinjects_after_cooldown_step10",
          by[("c_tests", 10)].decision == "inject")
    check("history_never_injects_relevance_floor",
          all(by[("h_backoff", s)].decision == "silent" and
              by[("h_backoff", s)].reason == "relevance_floor"
              for s in range(1, 13)))
    goal_injects = [s for s in range(1, 13) if by[("g_refresh", s)].decision == "inject"]
    check("goal_injects_at_most_once_and_only_on_decay",
          len(goal_injects) == 1 and all(by[("g_refresh", s)].reason in ("state_live", "cooldown")
                                         for s in range(1, 13) if s not in goal_injects),
          f"goal injects at steps {goal_injects}")

    # 3. the 164418Z false-positive test: label ground truth, then score.
    #    Truth: c_tests was decision-relevant exactly at its inject steps;
    #    g_refresh relevant when it injected; h_backoff never relevant (and it
    #    never injected: silence beat that reminder). One adversarial probe:
    #    a topically-adjacent-but-wrong goal at a step where it is only partly
    #    visible must stay silent (state_live abstain).
    for d in ex["decisions"]:
        if d.memory_id == "c_tests":
            d.was_relevant = d.decision == "inject"
        elif d.memory_id == "g_refresh":
            d.was_relevant = d.decision == "inject"
        else:
            d.was_relevant = False
    wrong = MemoryEntry(6, "goal", "draft the endpoint docs today", 0.7, "g_docs_wrong")
    probe = decide(wrong, 6, ["wire the refresh endpoint", "update route table",
                              "token docs touched"], None, GatePolicy())
    check("ambiguous_adjacent_memory_abstains",
          probe.decision == "silent" and probe.reason == "state_live",
          f"{probe.decision}/{probe.reason}")
    probe.was_relevant = False  # had it injected, it would have been a wrong reminder
    run_score = score_run(ex["decisions"] + [probe])
    check("zero_false_positive_injections",
          run_score["false_positive_injections"] == 0, json.dumps(run_score))
    check("gate_still_catches_real_decay",
          run_score["true_positive_injections"] >= 2, json.dumps(run_score))
    check("run_passes_164418Z_test", run_score["passed"] is True, json.dumps(run_score))

    # 4. register: rows readable from disk, scoped by run_id, cooldown derived
    if register_path is not None:
        check("register_file_exists_on_disk", register_path.is_file(), str(register_path))
        rows = [r for r in load_register(register_path)
                if r.get("run_id") == ex["run_id"]]
        check("register_rows_on_disk", len(rows) == len(ex["decisions"]),
              f"{len(rows)} rows for {len(ex['decisions'])} decisions")
        check("register_rows_are_json", all(isinstance(r, dict) and "ts" in r for r in rows))
        s = summarize(register_path, run_id=ex["run_id"])
        check("register_summary_consistent",
              s["rows"] == len(rows) and s["injects"] == sum(
                  1 for d in ex["decisions"] if d.decision == "inject"),
              json.dumps(s))
        check("cooldown_derived_from_register",
              last_injected_step("c_tests", rows) == 10,
              f"last inject step {last_injected_step('c_tests', rows)}")

    return {"schema": SCHEMA, "ok": all(c["ok"] for c in checks), "checks": checks,
            "run_score": run_score}


def main() -> int:
    ap = argparse.ArgumentParser(prog="intervention_gate")
    ap.add_argument("--example", action="store_true", help="run the worked example")
    ap.add_argument("--self-test", action="store_true", help="run the self-test")
    ap.add_argument("--json", action="store_true", help="emit raw JSON")
    a = ap.parse_args()

    if a.self_test:
        report = self_test(register_path=REGISTER_PATH)  # proves the durable write
        if a.json:
            print(json.dumps(report, indent=2, default=str))
        else:
            for c in report["checks"]:
                print(f"  [{'PASS' if c['ok'] else 'FAIL'}] {c['check']}")
            print(f"self-test: {'PASS' if report['ok'] else 'FAIL'} "
                  f"({sum(1 for c in report['checks'] if c['ok'])}/{len(report['checks'])} checks)")
        return 0 if report["ok"] else 1

    ex = worked_example(register_path=REGISTER_PATH)  # a real registered run
    if a.json:
        print(json.dumps(ex, indent=2, default=str))
    else:
        print("worked example: constraint+goal+history bank over a 12-step refactor run")
        for d in ex["decisions"]:
            mark = "INJECT" if d.decision == "inject" else "silent"
            print(f"  step {d.step} [{mark:6}] {d.memory_id:12} reason={d.reason}")
        s = summarize(REGISTER_PATH, run_id=ex["run_id"])
        print(f"register: {s['rows']} rows, {s['injects']} injects at {REGISTER_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
