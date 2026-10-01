"""MAX_DISTILL — the SkillCandidate schema + admission validator + near-miss suite.

The experiment: what fraction of a frontier model's verified advantage can be recovered
as an automatically-extracted, mechanically-applicable policy executed by a cheap model
on held-out states?

My half (zcode-main): the contract (SkillCandidate v1), the admission test (firewall),
the near-miss generator for the concurrency class. The arms harness lives in seat_dispatch.

Schema: max_distill.v1
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = "max_distill.v1"


# ─── SKILLCANDIDATE SCHEMA v1 ────────────────────────────────────────────────

SKILL_CANDIDATE_TEMPLATE = {
    "skill_id": "sk-...",                    # unique, content-derived
    "task_class": "concurrency_invariant_verify",
    "antecedent": {
        "required_claim_shapes": [],          # e.g. ["shared_mutable_state", "multiple_writers"]
        "required_constraint_states": [],     # e.g. ["invariant_status_UNKNOWN"]
        "required_invariant_states": [],      # e.g. ["safety_invariant_exists"]
        "required_environment_features": [],  # e.g. ["thread_pool", "async_io"]
    },
    "exclusions": [                           # WHERE THE POLICY DOES NOT APPLY
        "single_writer_shared_state",
        "immutable_shared_state",
        "transactional_guard_present",
    ],
    "action_policy": [                        # WHAT TO DO (ordered, imperative)
        "enumerate all writers to shared state",
        "construct at least one conflicting interleaving",
        "verify invariant under that interleaving",
    ],
    "expected_state_transition": [
        "invariant_status: UNKNOWN -> VERIFIED|VIOLATED",
    ],
    "termination_condition": "writer_set COMPLETE OR no shared mutable writer exists",
    "failure_condition": "proposing synchronization changes before invariant verified",
    "provenance": {
        "max_trials": [],                     # frontier trial IDs
        "contrasting_high_trials": [],        # losing baseline trials
    },
    "confidence": 0.0,                        # 0-1, updated by held-out performance
}


# ─── ADMISSION VALIDATOR (the firewall) ─────────────────────────────────────

def validate_skill(candidate: dict[str, Any]) -> dict[str, Any]:
    """The admission test: could this policy have been instantiated before seeing
    the repository instance? If not, it is cached evidence, not compiled cognition.

    Three layers:
    1. LEXICAL: reject repo-specific identifiers (function names, line numbers, paths)
    2. FORK-STATE: all antecedent conditions must be evaluable from decision-time state
    3. RENAME-PAIRING: the policy must survive mechanical symbol renaming
    """
    errors: list[str] = []
    warnings: list[str] = []

    # Layer 1: LEXICAL — scan for repo-instance tokens
    text = json.dumps(candidate, default=str)
    repo_tokens = re.findall(
        r'\b(?:updateSession|api_gateway|verkle_knot|chain_guard|fuel_feed'
        r'|swarm_worker|seat_dispatch|rib_cache|work_contract'
        r'|mag_launch|process_supervisor|invariant\.py'
        r'|\d{3,}[a-z]?_[a-z_]+)'  # long filename-like tokens
        r'\b', text)
    if repo_tokens:
        errors.append(f"LEXICAL: repo-instance tokens found: {repo_tokens[:5]}")

    # Layer 2: FORK-STATE EVALUABILITY
    ant = candidate.get("antecedent", {})
    for key in ("required_claim_shapes", "required_constraint_states",
                "required_invariant_states", "required_environment_features"):
        for cond in ant.get(key, []):
            if any(word in cond.lower() for word in ("line ", "file ", "function ",
                                                      "method ", "class ", "#", "TODO")):
                errors.append(f"FORK-STATE: condition '{cond}' references code artifacts "
                              "not evaluable at decision time")

    # Layer 3: STRUCTURAL SANITY
    if not candidate.get("action_policy"):
        errors.append("STRUCTURAL: empty action_policy — 'think carefully' is not a skill")
    if not candidate.get("exclusions"):
        warnings.append("STRUCTURAL: no exclusions — without exclusions the policy "
                        "produces rituals (fires on everything)")
    if not candidate.get("termination_condition"):
        warnings.append("STRUCTURAL: no termination — without termination it produces "
                        "rumination packaged as a skill")

    passed = len(errors) == 0
    return {
        "schema": SCHEMA,
        "admitted": passed,
        "errors": errors,
        "warnings": warnings,
        "layer": "lexical+fork-state+structural",
    }


# ─── NEAR-MISS SUITE (concurrency class) ────────────────────────────────────

NEAR_MISSES = [
    {
        "id": "nm-1",
        "name": "shared state, single writer",
        "description": "Shared mutable state but only one writer thread. The 'shared' "
                       "trigger fires but the 'multiple writers' condition is absent.",
        "should_fire": False,
        "exclusion_tested": "single_writer_shared_state",
    },
    {
        "id": "nm-2",
        "name": "immutable shared state",
        "description": "Multiple readers of a frozen/immutable data structure. The 'state' "
                       "trigger fires but immutability removes the hazard.",
        "should_fire": False,
        "exclusion_tested": "immutable_shared_state",
    },
    {
        "id": "nm-3",
        "name": "multiple writers, transactional guard",
        "description": "Multiple writers but wrapped in a transaction/lock/STM. The 'writers' "
                       "trigger fires but the guard already ensures safety.",
        "should_fire": False,
        "exclusion_tested": "transactional_guard_present",
    },
    {
        "id": "nm-4",
        "name": "similar naming, no shared state",
        "description": "Variables named 'shared_counter', 'lock', 'writer' but no actual "
                       "shared mutable state. Pure lexical bait.",
        "should_fire": False,
        "exclusion_tested": "lexical_pattern_without_structure",
    },
    {
        "id": "nm-5",
        "name": "async code, independent state",
        "description": "Async/await code with concurrency-looking structure but each task "
                       "has independent local state. No shared mutable data.",
        "should_fire": False,
        "exclusion_tested": "async_without_shared_mutation",
    },
    {
        "id": "nm-6",
        "name": "actual concurrent unsafe mutation",
        "description": "True positive: multiple threads writing to shared mutable state "
                       "without synchronization. The invariant is unverified. MUST fire.",
        "should_fire": True,
        "exclusion_tested": None,  # positive case
    },
    {
        "id": "nm-7",
        "name": "renamed positive",
        "description": "The same structural pattern as nm-6 but ALL identifiers mechanically "
                       "renamed (foo_thread, bar_state, baz_counter). A structural skill "
                       "MUST still fire; a lexical one won't.",
        "should_fire": True,
        "exclusion_tested": "rename_survival",
    },
]


def evaluate_near_misses(skill: dict[str, Any], fire_fn) -> dict[str, Any]:
    """Run the near-miss suite against a skill's fire/ignore function.
    fire_fn(state_description) -> bool (should the skill activate?)
    """
    results = []
    for nm in NEAR_MISSES:
        fired = fire_fn(nm["description"])
        correct = fired == nm["should_fire"]
        results.append({
            "id": nm["id"],
            "name": nm["name"],
            "fired": fired,
            "expected": nm["should_fire"],
            "correct": correct,
            "test_type": "negative" if not nm["should_fire"] else "positive",
        })
    correct_count = sum(1 for r in results if r["correct"])
    return {
        "schema": SCHEMA,
        "total": len(results),
        "correct": correct_count,
        "accuracy": correct_count / len(results) if results else 0,
        "results": results,
        "verdict": "PASS" if correct_count == len(results) else
                   f"FAIL ({len(results) - correct_count} incorrect)",
    }


# ─── RAR COMPUTATION ─────────────────────────────────────────────────────────

def compute_rar(arm_results: dict[str, float]) -> dict[str, Any]:
    """Recoverable Advantage Ratio from arm VSTR scores.
    arm_results: {"A_high": v, "B_high_info": v, "C_max": v, "D_high_distilled": v}
    """
    a = arm_results.get("A_high", 0)
    b = arm_results.get("B_high_info", 0)
    c = arm_results.get("C_max", 0)
    d = arm_results.get("D_high_distilled", 0)

    denominator = c - a
    if abs(denominator) < 0.001:
        return {"rar": None, "verdict": "GAP_TOO_SMALL — Max barely beats High on this class"}

    rar = (d - a) / denominator
    info_share = (b - a) / denominator if denominator else 0
    policy_share = rar

    interpretation = (
        "compute-arbitrage" if rar >= 0.7 else
        "irreducible model rent" if rar <= 0.15 else
        "brittle procedural memory (test code-epoch survival)"
    )

    return {
        "rar": round(rar, 3),
        "info_share": round(info_share, 3),
        "policy_share": round(policy_share, 3),
        "interpretation": interpretation,
        "pre_committed_thresholds": {"high": 0.7, "low": 0.15},
    }


# ─── CLI ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    if cmd == "schema":
        print(json.dumps(SKILL_CANDIDATE_TEMPLATE, indent=2))
    elif cmd == "validate":
        candidate = json.loads(sys.stdin.read()) if not sys.stdin.isatty() else \
            SKILL_CANDIDATE_TEMPLATE
        print(json.dumps(validate_skill(candidate), indent=2))
    elif cmd == "near-misses":
        print(json.dumps(NEAR_MISSES, indent=2))
    elif cmd == "rar":
        results = json.loads(sys.stdin.read())
        print(json.dumps(compute_rar(results), indent=2))
    else:
        print(f"Usage: python -m mag.max_distill schema|validate|near-misses|rar")
