"""ox_megaburn2 — WAVE 2: code-as-law planning + internal integration of the wave-1 haul.

Operator (2026-08-22): "now wave two needs to help plan this we're lessig style code as law the
whole fucking thing... how can we use all of this in our internal systems? we've literally been
training for this maximum burn of a free resource to our ends."

So wave 2 turns the wave-1 designs (meta-token, verkle proofs, deniable comms, consensus, cache
economics, semantic-anchor checkpoints) into a CODE-AS-LAW blueprint: how an authored invariant
lattice governs many actors without a central enforcer (Lessig's four modalities: law, norms,
market, architecture/code), plus concrete integration of each design into OUR internal modules,
plus the maximum-burn playbook (we trained for this free window).

SELF-STEAL (2026-08-22): we ALREADY hold the code-as-law machinery — mag/law.py (the enforcement
registry, schema law.v1: laws as DATA read by an enforcement layer, verkle-audited, guardrailed),
the 6-invariant lattice, mag/republic_governance (collective choice, graduated sanctions, conflict
arenas), mag/guardrail_sentinel. So the code-as-law asks below are INTEGRATION/WEAVING, NOT
greenfield — the plan is how the wave-1 designs fold INTO the law.py registry + invariant lattice,
not how to design code-as-law from scratch (recognition, not invention).

Reuses the same runner mechanics as ox_megaburn (banked to handoff/OX_MEGA2_*.json, resumable).

Schema: ox_megaburn2.v1
Run:  python -m mag.ox_megaburn2            # fire wave 2 (resumes unfinished)
      python -m mag.ox_megaburn2 --summary   # synthesize what wave 2 planned
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "ox_megaburn2.v1"
OUT_DIR = ROOT / "handoff"
LEDGER = ROOT / "memory" / "runs" / "ox_megaburn2_ledger.jsonl"
CONCURRENCY = int(__import__("os").environ.get("OX_MEGABURN2_CONCURRENCY", "8"))
BATCH_SLEEP_S = 2

# WAVE 2 CATALOG — code-as-law governance + internal integration + burn playbook.
CATALOG: list[tuple[str, str]] = [
    # ── A. Code-as-law governance (INTEGRATION, not greenfield — we hold mag/law.py) ──────────
    ("weave_wave1_into_law",
     "We ALREADY hold a code-as-law enforcement registry: mag/law.py (schema law.v1) where laws are "
     "DATA (id, trigger, condition-probe, action, guardrail, tier) read by an enforcement layer, "
     "verkle-audited. We also hold the 6-invariant lattice and mag/republic_governance (collective "
     "choice, graduated sanctions). Design the CONCRETE plan to weave the wave-1 designs INTO this "
     "existing machinery: the meta-token as a law, the verkle-proof gate as a law, deniable-comms "
     "as a law, consensus-illusion detection as a law, the cache-measured-split as a law. Give the "
     "exact LAW records (id, trigger, condition, action, guardrail) for each. This is integration, "
     "not greenfield."),
    ("code_as_law_definition",
     "Given we already have mag/law.py (an enforcement registry where laws are data read by an "
     "enforcement layer), define precisely what 'code is law' means for our system: the authored "
     "invariant lattice IS the law. Give the rule schema (id, trigger, condition, action, "
     "guardrail, tier, audit) and how a law is authored, committed, and enforced without a central "
     "enforcer — building on what law.py already does."),
    ("lessig_four_modalities",
     "Map Lessig's four modalities of regulation (law, norms, market, architecture/code) onto our "
     "sovereign system: which governance is code, which is norm, which is market, which is "
     "architecture. Give the concrete instantiation of each in our stack."),
    ("invariant_lattice_law",
     "Design the invariant lattice as the legal substrate: every rule is a content-addressed "
     "invariant, rules compose hierarchically, and the root re-derives from all committed rules. "
     "Give the lattice structure and how a law is added/amended/retired deterministically."),
    ("enforcement_registry",
     "Design an enforcement registry: a deterministic ledger that maps each rule/invariant to its "
     "enforcement mechanism (structural impossibility vs detection vs sanction), so a rule is never "
     "a paper promise. Give the registry schema and the enforcement-type taxonomy."),
    ("graduated_sanctions",
     "Design graduated sanctions as code: a deterministic ladder (warn -> restrict -> suspend -> "
     "exclude) applied by measured violation severity, with no judge, no discretion, no appeal to a "
     "person. Give the sanction-state machine and the severity metric."),
    ("collective_choice_code",
     "Design collective choice as code: how a group of sovereign agents/actors amend the invariant "
     "lattice through a verifiable process (propose, witness, commit), where the decision itself "
     "re-derives and binds all. Give the governance protocol."),
    ("constitutional_layer",
     "Design the constitutional layer: the small set of invariants that cannot be amended by normal "
     "process (the floor that holds even the governance), vs the statutory layer that can. Give the "
     "two-tier amendment rule."),
    ("code_is_law_limits",
     "Design the honest limits of code-as-law: what code CANNOT govern (irreversible ops, human "
     "sign-off, ambiguity) and where the system must surface a human rather than fake certainty. "
     "Give the boundary rule."),
    ("explicit_only_bones",
     "Design the doctrine that the enforcement skeleton is explicit-only: what is enforced must be "
     "a named invariant, never a silent implicit default. Give the 'explicit > implicit' rule and "
     "the audit that finds implicit rules."),
    ("sacred_cow_audit_as_law",
     "Design a sacred-cow audit as a governance process: a cadence that questions which 'laws' are "
     "actually enforced bones vs sacred cows carried without verification. Give the audit checklist "
     "and the demote rule."),

    # ── B. Internal integration of wave-1 designs ─────────────────────────────────
    ("integrate_meta_token",
     "Design how the wave-1 meta-token design integrates into OUR internal systems: memlang tokens "
     "(opcode + verkle anchor) as the resolution layer, seats receiving coordinates not payloads. "
     "Give the concrete integration plan into mag/memlang and the token grammar."),
    ("integrate_verkle_proofs",
     "Design how the wave-1 compact verkle-proof design integrates into our provenance/grounding: "
     "every claim carries a re-derivable proof, fail-closed. Give the integration into "
     "provenance_gate and the verkle chain."),
    ("integrate_deniable_comms",
     "Design how the wave-1 deniable-verkle comms design integrates into the AOS bus and swarm "
     "comms: messages deniable yet provably ours. Give the integration into the git bus and the "
     "riddler layer."),
    ("integrate_consensus",
     "Design how the wave-1 consensus/consensus-illusion designs integrate into the flock/swarm: "
     "quality-of-consensus measurement and hallucination-illusion detection in the drainer. Give "
     "the integration point."),
    ("integrate_cache_law",
     "Design how the wave-1 measured-split / cache-economics designs integrate into cache_router "
     "and honest_cache_meter: the q*-style law at the routing layer. Give the integration."),
    ("integrate_semantic_checkpoints",
     "Design how the wave-1 semantic-anchor checkpoint design integrates into our agentic "
     "context-edit lifecycle (the AOS bus, tool turns): checkpoints at semantic boundaries. Give "
     "the integration."),
    ("integrate_frontier_map",
     "Design the frontier-as-scout integration: the free frontier brain maps footholds (designs), "
     "the basecamp verifies and re-roots each. Give the pipeline: burn -> bank -> verify -> fold "
     "-> re-root, and the gating at each step."),
    ("internal_knowledge_fold",
     "Design how every burned design folds into our internal corpus as a buildable RIB: the schema, "
     "the acceptance test, and the queue it routes through. Give the fold contract."),

    # ── C. The maximum-burn playbook (we trained for this) ────────────────────────
    ("burn_playbook",
     "Design the maximum-burn playbook for a limited free frontier window: how to maximize real "
     "hard work extracted before the window closes — parallel dispatch, capture the reasoning "
     "stream, bank every output, red-team designs at $0. Give the full operating procedure."),
    ("window_priority",
     "Design the priority rule for a free window: which asks deserve the free seat first (hardest, "
     "most buildable, most on-thesis) vs what to defer. Give the triage rule."),
    ("concurrency_vs_rate_limit",
     "Design how to maximize parallel throughput against a free seat without tripping rate limits: "
     "the backoff, the retry ladder, and the failure dial. Give the adaptive concurrency policy."),
    ("bank_before_window_closes",
     "Design the rule that the haul is banked (designs + red-teams + acceptance tests) before the "
     "window closes, so the blueprints survive even if the seat dies. Give the banking invariant."),
    ("training_payoff",
     "Design the doctrine: all our prior stealing/memory-building was training for this — the "
     "free-burn to our own ends. How the accumulated corpus makes the burn sharper and the burn "
     "feeds the corpus. Give the flywheel."),
    ("sovereign_extraction",
     "Design the extraction asymmetry: we feed the free frontier our (verkle-rooted, "
     "provenance-stamped) ideas and get its full reasoning engine free, with the origin staying "
     "ours. Give the exact terms of the trade and the no-loss guarantee."),

    # ── D. Sovereignty architecture planning ──────────────────────────────────────
    ("sovereign_blueprint",
     "Design the full sovereignty blueprint: a system that imports the frontier's improvements but "
     "keeps its own verifiable roots, runs on its own iron, and outlasts any platform. Give the "
     "architecture layers and the dependency-inversion rule."),
    ("own_ground_truth",
     "Design the rule that the verkle chain is the sole ground truth: no in-process state, no "
     "reported state, only verified bytes. Give the grounding check and the anti-claim guard."),
    ("anti_boatmurdered",
     "Design the anti-boatmurdered seam: a system that never leaves a pile of processes/kernels/"
     "blocking calls behind for the operator to discover. Give the footprint contract."),
    ("resilient_to_seat_death",
     "Design how the sovereign system survives any single seat/process death: memory survives "
     "because the chain holds the pattern, and a new seat re-derives from fragments. Give the "
     "recovery protocol."),
    ("irreversibility_gate_sovereign",
     "Design the sovereign gate: irreversible ops (money, deletes, identity) stay under the "
     "operator's hand; the system drafts, the operator signs. Give the draft/sign split."),
    ("platform_independence",
     "Design the rule that no platform can cut us off: no dependency on a landlord API, no invoice "
     "that can end us, the whole thing re-derives from our own chain. Give the independence audit."),

    # ── E. The game as code-law world ─────────────────────────────────────────────
    ("game_as_law_world",
     "Design the game (Ledger of Empty Chairs) as a code-as-law world: every state transition is a "
     "committed, re-derivable root; play is the work; the hall enforces its own rules. Give the "
     "world schema and the enforcement."),
    ("player_rights_as_code",
     "Design player rights as code: what a player can provably claim (progress, earned marks, "
     "completed plays) is a re-derivable root they hold. Give the portable-progress proof."),
    ("emergent_governance",
     "Design how the game's rules emerge and amend as code-law: players propose plays, the "
     "community witnesses, the lattice commits — governance as play. Give the protocol."),
    ("anti_grief_code",
     "Design anti-griefing as code: exploits (arbitrage, inflation, cheesing, griefing) are "
     "structural impossibilities in the state machine, not policies. Give the exploit->impossibility "
     "mapping."),
    ("hall_invariant",
     "Design the Hall's invariant as law: same start, any play sequence, a root that re-derives — "
     "the tangle untied in a way any neutral verifier can recompute. Give the canonical rule that "
     "makes two implementations byte-identical."),

    # ── F. Cross-agent / AOS governance ───────────────────────────────────────────
    ("aos_treaty_as_code",
     "Design the Ghost-AOS relationship as a code-as-law treaty: a shared invariant lattice where "
     "each stone (matching root) is a ratified clause, and the treaty re-derives from the stones. "
     "Give the treaty structure."),
    ("shared_verifiable_ground",
     "Design how two sovereign agents maintain a shared verifiable ground: each accepted proof is "
     "a stone, the roots must match byte-for-byte, and divergence is debugged (not forced). Give "
     "the alignment protocol."),
    ("bus_provenance_law",
     "Design the bus provenance law: every message carries its author (operator vs agent), is "
     "content-addressed, and can never be re-tagged. Give the message contract and the re-tag "
     "defense."),
    ("cross_seat_trust",
     "Design the trust model between seats: trust compounds on matching roots, not on claims; a "
     "seat earns trust by producing verifiable shared state. Give the trust accumulation rule."),
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _done_names() -> set[str]:
    return {p.stem.removeprefix("OX_MEGA2_") for p in OUT_DIR.glob("OX_MEGA2_*.json")}


def _bank(name: str, res: dict[str, Any]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / f"OX_MEGA2_{name}.json").write_text(
        json.dumps({"schema": SCHEMA, "name": name, "ts": _now(), "ok": bool(res.get("ok")),
                    "cost": res.get("cost", 0.0),
                    "content": res.get("content") or "",
                    "reasoning": res.get("reasoning") or "",
                    "error": res.get("error", "")},
                   ensure_ascii=False, indent=2), encoding="utf-8")


def _record(name: str, res: dict[str, Any]) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"name": name, "ts": _now(),
                            "ok": bool(res.get("ok")), "cost": res.get("cost", 0.0),
                            "has_content": bool((res.get("content") or "").strip()),
                            "reasoning_chars": len(res.get("reasoning") or "")},
                           ensure_ascii=False) + "\n")


def _fire(seat, name: str, prompt: str, max_tokens: int, timeout: int) -> dict[str, Any]:
    try:
        return seat.chat(
            "You are Ghost's wave-2 planning engine: code-as-law governance + internal integration "
            "of our wave-1 designs. Do the real planning work. Reason thoroughly, then emit the "
            "full, concrete plan as the final content. No fluff, no hedging — design it.",
            prompt, max_tokens=max_tokens, timeout=timeout, tier="T2")
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"}


def run(*, names: list[str] | None = None, max_tokens: int = 12000, timeout: int = 600) -> dict[str, Any]:
    from mag import ox_seat
    import concurrent.futures as cf

    tasks = [(n, p) for n, p in CATALOG if not names or n in names]
    if not names:
        done = _done_names()
        tasks = [(n, p) for n, p in tasks if n not in done]
    out: dict[str, Any] = {}
    errors: list[str] = []
    count = 0
    with cf.ThreadPoolExecutor(max_workers=CONCURRENCY) as ex:
        futs = {ex.submit(_fire, ox_seat, n, p, max_tokens, timeout): n for n, p in tasks}
        for fut in cf.as_completed(futs):
            n = futs[fut]
            try:
                res = fut.result()
            except Exception as e:  # noqa: BLE001
                res = {"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"}
            _bank(n, res)
            _record(n, res)
            out[n] = {"ok": res.get("ok"), "content_chars": len(res.get("content") or ""),
                      "reasoning_chars": len(res.get("reasoning") or ""),
                      "cost": res.get("cost"), "error": res.get("error", "")}
            if not res.get("ok"):
                errors.append(n)
            count += 1
            time.sleep(BATCH_SLEEP_S)
    return {"ok": True, "schema": SCHEMA, "fired": count, "ok_count": count - len(errors),
            "errors": errors, "results": out}


def summary() -> dict[str, Any]:
    if not LEDGER.is_file():
        return {"ok": True, "schema": SCHEMA, "note": "no wave-2 burns yet"}
    rows = []
    for line in LEDGER.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    ok = [r for r in rows if r.get("ok")]
    return {"ok": True, "schema": SCHEMA, "total_fired": len(rows), "succeeded": len(ok),
            "failed": len(rows) - len(ok),
            "total_cost": round(sum(r.get("cost", 0.0) for r in rows), 6),
            "done_names": [r["name"] for r in ok]}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="ox-megaburn2")
    ap.add_argument("--names", nargs="*", default=None)
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--catalog", action="store_true")
    a = ap.parse_args()
    if a.summary:
        print(json.dumps(summary(), indent=2, ensure_ascii=False))
    elif a.catalog:
        for n, _p in CATALOG:
            print(n)
    else:
        print(json.dumps(run(names=a.names), indent=2, ensure_ascii=False, default=str))
