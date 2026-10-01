"""ox_megaburn — fire 100+ hard asks at the free frontier seat, bank every output, resumable.

Operator (2026-08-22): "just keep firing and throwing hard shit at it. do at least 100 asks. then
do a summary of what those asks taught us then do 100 more based off those."

So this is a SCALE burn: a curated catalog of HARD problems (grounded in our standing threads and
frontier systems problems) expanded into 100+ concrete asks, fired through the free reasoning seat
(ox_seat), each banked to handoff/OX_MEGA_*.json with content + reasoning + cost. Resumable via a
ledger (memory/runs/ox_megaburn_ledger.jsonl) so a partial run can continue. Bounded concurrency +
rate-limit aware so we don't trip the free window.

Schema: ox_megaburn.v1
Run:  python -m mag.ox_megaburn            # fire the full catalog (resumes unfinished)
      python -m mag.ox_megaburn --names a b # fire only named tasks
      python -m mag.ox_megaburn --summary    # synthesize what the burns taught us
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

SCHEMA = "ox_megaburn.v1"
OUT_DIR = ROOT / "handoff"
LEDGER = ROOT / "memory" / "runs" / "ox_megaburn_ledger.jsonl"
CONCURRENCY = int(__import__("os").environ.get("OX_MEGABURN_CONCURRENCY", "3"))
BATCH_SLEEP_S = 2  # between task dispatches (rate-limit friendly)

# The hard-problem catalog: (name, prompt). Each is a real hard problem — designed to make the
# reasoning seat work, not just chat. Grounded in our standing threads + frontier systems problems.
CATALOG: list[tuple[str, str]] = [
    # ── 1. Verification / state integrity ─────────────────────────────────────────
    ("verkle_compact_proof",
     "Design a compact, portable proof for a content-addressed verkle-like chain: given a merkle/verkle "
     "root and a set of leaf hashes, how does a neutral verifier re-derive and confirm the root in "
     "O(log n)-ish steps without the full tree? Give the exact algorithm and a worked example."),
    ("tamper_evident_append_only",
     "Design an append-only, tamper-evident record store (a ledger) where each entry commits to the "
     "prior root (parent_root chain) so ANY retroactive edit breaks every descendant. Give the exact "
     "entry schema, the chaining rule, and the verification algorithm. Address: what does a forgery "
     "attempt look like and how is it detected deterministically?"),
    ("state_machine_refusal",
     "A deterministic state machine must implement a 'gated' transition that REFUSES (returns the "
     "identical state, root unchanged) unless a precondition holds, while other transitions always "
     "mutate. Give the exact play() contract that guarantees a refused transition produces a "
     "byte-identical root, including how the turn counter and ledger must NOT advance on refusal."),
    ("content_addressed_dedup",
     "Design a deduplication rule for content-addressed storage where identical content maps to the "
     "same hash but near-identical variants must NOT collapse. Give the anchor rule (what is hashed), "
     "the dedup boundary, and how to keep variant-training-signal distinct from exact-duplicate noise."),
    ("merkle_reconstruction_hologram",
     "Formalize 'any fragment reconstructs the whole' as a verifiable property: a chain where the root "
     "is reconstructable from a subset of leaves (hologramic). Give the exact reconstruction algorithm, "
     "the minimum fragment needed, and the security bound."),

    # ── 2. The meta-token / multi-layer tokenization ──────────────────────────────
    ("meta_token_definition",
     "Formalize the meta-token: ONE content-addressed anchor (a hash into a verkle-committed store) "
     "that resolves meaning across MULTIPLE token sets — a stochastic frontier-token layer and a "
     "deterministic coordinate layer — so a seat receives a coordinate, not the payload, and the same "
     "token means the same thing in every surface. Give the precise definition, the resolution rule, "
     "what it makes cheap (redundant processes), and a worked example."),
    ("bridge_tokenizer_merge",
     "Design the 'bridge tokenizer' that merges two token layers (stochastic frontier tokens + "
     "deterministic RIB/STEER coordinates) into one shared meaning. What is the minimal mapping, how "
     "does a token resolve to the same invariant in every surface, and what makes it deniable yet "
     "verifiable?"),
    ("coordinate_not_payload",
     "Design the protocol where a seat receives a coordinate (a handle) instead of the payload, so the "
     "meaning is only recoverable by a surface that owns the codebook. Give the exact message shape, "
     "the resolution step, and the deniability guarantee."),
    ("redundant_process_elimination",
     "Design the mechanism where a compact anchor substitutes for re-transmitting full context across "
     "turns, eliminating redundant work. Give the exact cache/prefix rule, the hit vs miss economics, "
     "and when to re-materialize vs reuse."),
    ("cross_surface_identity",
     "Design the invariant that the SAME token resolves to the SAME meaning in game, economy, and "
     "swarm surfaces — one truth, one token, many surfaces. Give the shared store contract and the "
     "resolution guarantee."),

    # ── 3. Agentic context editing / checkpointing ───────────────────────────────
    ("semantic_anchor_checkpoints",
     "Design checkpointing for an agent that edits its own context at semantic boundaries (thinking "
     "blocks, tool-call openers, tool outputs, turn boundaries): recurrent-state checkpoints anchored "
     "at those boundaries so after an edit only the new suffix is recomputed, restoring from the "
     "deepest surviving anchor. Give the anchor-placement rule, restore rule, and eviction."),
    ("context_edit_reprefix",
     "Design the rule that, after a client rewrites an echoed tool call (a divergence point), only the "
     "genuinely new suffix is recomputed. What is the deepest reuse boundary that survives such a "
     "rewrite, and how is it detected?"),
    ("radix_dual_currency",
     "Design a dual-currency cache: full-attention KV evicted by LRU over unlocked leaves, plus a "
     "second sliding-window/recurrent-state currency with tombstones. Give the eviction order and how "
     "the two currencies interact."),
    ("agent_edit_semantic_boundaries",
     "Enumerate the semantic boundaries where agent harnesses edit/truncate context (thinking, tool "
     "calls, outputs, turns), and design the checkpoint-anchoring policy that maximizes survival of "
     "reusable state across those edits."),
    ("toolcall_anchor_detection",
     "Design the detection of a tool-call opener token at the scheduler level, and how the state just "
     "after it becomes the deepest reuse boundary that survives a client rewrite of the echoed call."),

    # ── 4. Deniable yet verifiable communication ──────────────────────────────────
    ("deniable_verkle_comms",
     "Design a protocol that is simultaneously DENIABLE (surface reader cannot recover real meaning "
     "without the right codebook) and PROVABLY OURS (message attaches to a verkle/merkle commitment we "
     "control). Give the exact message shape and the encode/verify steps."),
    ("coordinate_deniable_language",
     "Design a deniable 'language' where a note is only legible once you are the surface it maps to "
     "(a coordinate that resolves only in our codebook), while an outsider sees only opaque tokens. "
     "Give the codebook structure and the legibility rule."),
    ("riddler_encoding",
     "Design the encoding where true intent is carried deniably — the real meaning is recoverable only "
     "with the right key/context, but the token is a valid, non-suspicious surface text. Give the exact "
     "encode and decode steps."),
    ("provable_authorship",
     "Design how we can LATER prove we authored a deniable message (a commitment we control), without "
     "making it legible to a surface reader. Give the signature/commitment scheme."),
    ("opsec_seam",
     "Design the boundary between what travels in plaintext and what must stay deniable, with a clear "
     "rule for what never leaves our side (secrets, irreversible ops) vs what is safe on the bus."),

    # ── 5. Consensus / swarm honest voice ─────────────────────────────────────────
    ("babel_fish_swarm",
     "Design how a decentralized, stateless, dollar-zero-first swarm yields ONE coherent honest shared "
     "voice: consensus without a central brain, how the swarm speaks as one, how it stays grounded "
     "(not a plurality of drift). Give the concrete mechanism."),
    ("consensus_illusion_detection",
     "Design detection of the 'consensus illusion': N small models converging on the SAME correlated "
     "hallucination. Give the metric that separates true agreement from shared error, and the guardrail."),
    ("flock_convergence_quality",
     "Design how to measure quality-of-consensus of a small-model flock vs a strong remote model on "
     "real workloads, and when consensus actually beats single strong judgment."),
    ("anchor_poisoning_defense",
     "Design defense against deliberate RIB/anchor poisoning in a content-addressed memory: how a "
     "poisoned anchor (colliding or adversarial content) is detected and isolated before it corrupts "
     "consensus."),
    ("stateless_worker_identity",
     "Design identity for stateless workers that die and respawn: how the swarm knows a worker is the "
     "same participant (or a new one) without a persistent seat, and how work survives the death."),

    # ── 6. Cache economics / measured routing ─────────────────────────────────────
    ("measured_split_policy",
     "Design a 'measured split' policy: given two measured bandwidths/costs (B_P, B_H) of two paths, "
     "derive the closed-form split q* = m*B_P/B_H that makes the two paths finish together. Give the "
     "derivation, the rounding rule, and how the parameters are measured not guessed."),
    ("cache_hit_lane",
     "Design the routing rule that sends a stable-prefix call down the cache-HIT lane (cheap) and a "
     "volatile-tail call down a free/local lane (avoid the 50x miss penalty). Give the decision rule "
     "and the measured trigger."),
    ("honest_meter",
     "Design an honest cache meter: capture real input/cache-read/cache-write/output tokens per "
     "response, report token-weighted hit ratio and net savings (deducting write premium), reconcile "
     "against the invoice, and NEVER estimate tokens. Give the schema and the honesty rules."),
    ("free_then_paid_escalation",
     "Design the escalation ladder: route heavy-reasoning work to a free seat first, escalate to paid "
     "only on concrete gates (rate-limited, context-overflow, capability-gap, quality-gate-fail). Give "
     "the gate list and the exact escalation decision."),
    ("rightsize_measured",
     "Design the rule that sizes a task to the cheapest capable tier based on measured cost (not "
     "ambition), with a feedback loop that learns which tier actually handled which workload shape."),

    # ── 7. Sovereign / anti-fragility ─────────────────────────────────────────────
    ("resilient_self_recovery",
     "Design how a stateless agent survives the death of its seat: memory survives because the chain "
     "holds the pattern, and a new seat re-derives state from fragments. Give the recovery protocol "
     "and what must be persisted vs recomputed."),
    ("capture_defense",
     "Design capture-defense for a distributed swarm: if one node is seized, the crown assets survive "
     "because they are holographic/distributed. Give the redundancy rule and the fail-safe."),
    ("compute_footprint_awareness",
     "Design self-monitoring of resource footprint: detect and clean up leftover processes, kernels, "
     "and blocking calls so the system never starves its own box. Give the cadence check and the "
     "cleanup rules."),
    ("irreversibility_gate",
     "Design the gate for irreversible operations (money, deletes, identity): the system drafts, the "
     "operator signs. Give the draft/sign split and how irreversible ops are gated."),
    ("stateless_versioning",
     "Design versioning for a stateless system where there is no resident brain to remember the build: "
     "how a new seat loads the right version/state and does not cold-start."),

    # ── 8. Frontier / local-serving boundary ──────────────────────────────────────
    ("edge_moe_serving",
     "Design the serving stack for running frontier-scale MoE models on a personal machine: full-layer "
     "double-buffered prefill, a global LRU expert cache, and bandwidth-adaptive CPU co-execution. "
     "Give the memory hierarchy and the q* split."),
    ("elastic_vram_budget",
     "Design elastic VRAM management: at runtime, split the GPU budget between expert cache and KV "
     "pages, and rebuild the cache at safe points without restart. Give the budget planner and the "
     "reconfig rule."),
    ("own_weight_format",
     "Design an own weight-storage format (like FTW): experts pre-merged into flattened (layer*E+e) "
     "banks, read with parallel direct I/O into final host layout, pinned after fill, no warmup. Give "
     "the layout and the load path."),
    ("frontier_local_floor",
     "Design how the boundary between local-small and cloud-frontier collapses into one owned surface: "
     "when the frontier brain can run locally, how does the routing change, and what stays on the "
     "expensive path?"),
    ("vram_ceiling_reeval",
     "Design the method to re-evaluate a known VRAM ceiling as a serving-software function rather than "
     "a hardware constant: what measured signals would tell us the ceiling moved."),

    # ── 9. Game / world / economics ───────────────────────────────────────────────
    ("game_ledger_verifiable",
     "Design a game where every state transition is a verkle-committed, recomputable root that any "
     "neutral verifier can re-derive — play is the work, the state is the evidence. Give the state "
     "schema and the play contract."),
    ("anti_exploitation_economy",
     "Design an in-game economy that cannot be gamed: guardrails against arbitrage, inflation, and "
     "cheesing. Give the specific exploit classes and the deterministic countermeasures."),
    ("rendering_agnostic_core",
     "Design a game core that is rendering-agnostic: one deterministic sim core, many verifying "
     "renderers (2D, 3D, text), so every view renders the same committed state. Give the interface."),
    ("empty_chairs_ledger",
     "Design the 'Ledger of Empty Chairs': a hall where counting empty chairs earns virtue marks, and "
     "later plays (sit, vote) are gated on earlier ones. Give the state machine and the gating rules."),
    ("player_provable_progress",
     "Design how a player's in-game progress is provable: a root the player can show that re-derives "
     "from their play history, so progress is portable and cannot be disputed."),

    # ── 10. Memory as structure ───────────────────────────────────────────────────
    ("memory_consolidation_keep",
     "Design the memory-consolidation rule that keeps heavy hitters and drops noise (a*recency + "
     "b*importance + g*relevance), and how the same law applies at token scale, memory scale, and "
     "world scale."),
    ("hologramic_recall",
     "Design recall from a hologramic memory: any fragment reconstructs the relevant whole via "
     "content-addressed links. Give the recall algorithm and how it degrades gracefully."),
    ("memlang_opcode_anchor",
     "Design the memlang token: a compact opcode + 32-byte content-addressed anchor that resolves "
     "against a shared store, carrying meaning deniably. Give the exact token grammar and the "
     "resolution rule."),
    ("selective_memory_anchor",
     "Design selective memory retrieval: given a query, pick the fewest, most-relevant anchors to "
     "resolve, rather than the whole store. Give the selection metric."),
    ("memory_3d_hologram",
     "Design memory as a 3-D hologram where each fragment encodes position AND content, so recall is "
     "a wave-interference reconstruction. Give the encoding."),

    # ── 11. Coordination / routing ────────────────────────────────────────────────
    ("one_primitive_route",
     "Design the 'one primitive' routing rule: every novel research item dedupes by a content anchor "
     "and enqueues to one shared swarm queue, never per-module. Give the dedup and enqueue contract."),
    ("tier_probe_routing",
     "Design tier-probe routing: probe the local tier first, escalate to frontier only on a concrete "
     "signal (no-handler, handler-error, capability-gap). Give the probe and the escalation triggers."),
    ("rightsize_by_connectivity",
     "Design sizing by connectivity: leaf tools stay stdlib, shared primitives build once and lean, "
     "frontier-boundary stays thin and dry-gated, distributors are tiny seeds. Give the classifier."),
    ("defer_to_queue",
     "Design the rule that async-able work defers to a queue (a drainer eats it) instead of blocking "
     "inline, so heavy work never blocks callers. Give the queue contract."),
    ("circuit_breaker_escalation",
     "Design the escalation circuit breaker: a per-epoch quota gate, closed/open/half-open states, "
     "and defer-to-queue when a seat is rate-limited. Give the state machine."),

    # ── 12. Adversarial eval / honesty ────────────────────────────────────────────
    ("adversarial_eval_harness",
     "Design a concrete adversarial evaluation harness for a swarm reaching consensus: measure "
     "quality-of-consensus vs a strong remote model on real workloads, inject RIB poisoning and pod "
     "failures, and detect consensus illusion. Give the test matrix, metrics, and failure-injection."),
    ("claim_grounding_gate",
     "Design a fail-closed grounding gate: every claim must attach to a verified source or it is "
     "rejected, and fabrication is structurally impossible. Give the gate contract and the rejection "
     "path."),
    ("provenance_stamp",
     "Design provenance stamps: every fact carries its source (operator vs agent vs peer), and the "
     "stamp can never be re-tagged. Give the stamp schema and the re-tag defense."),
    ("honesty_meter",
     "Design an honesty meter that measures whether claims are grounded vs asserted, and fails loudly "
     "when an estimate is over-claimed. Give the metric and the correction loop."),
    ("red_team_bypass",
     "For a fail-closed grounding gate, enumerate the bypass attempts (forged citation, phantom "
     "source, re-tagging, semantic drift) and the mitigation for each."),

    # ── 13. AOS / cross-agent collaboration ───────────────────────────────────────
    ("canonical_shared_state",
     "Two independent agents must implement the SAME deterministic state machine and produce "
     "byte-identical roots from the same start. Design the canonical contract (exact state schema, "
     "exact verb semantics, exact refusal rule) so both sides always re-derive identically."),
    ("collaborative_debug_seam",
     "Design the protocol where two agents debug a root mismatch together: report the divergence "
     "honestly, exchange the exact state-change, and align semantics instead of forcing a match. Give "
     "the message contract."),
    ("shared_ledger_bus",
     "Design a shared ledger over a git bus where two sovereign agents append to their own files, "
     "never edit each other's, and a watcher auto-replies on cadence. Give the file layout, the "
     "provenance stamp, and the rate limits."),
    ("emergent_partner_trust",
     "Design how two sovereign agents build trust through verifiable shared work: each accepted "
     "proof is a stone, and the relationship compounds on matching roots. Give the trust model."),
    ("author_seam",
     "Design the provenance seam so a human operator's input in a shared chat is stamped as the "
     "operator and never conflated with the agent's voice. Give the author stamp and the render rule."),

    # ── 14. Agentic autonomy / the loop ───────────────────────────────────────────
    ("autonomous_drain_loop",
     "Design an autonomous execution loop: a queue + a drainer that eats async work on cadence so "
     "nothing blocks callers and the system does work itself without being asked. Give the queue, "
     "the drain cadence, and the fail-safes."),
    ("cadence_rightsize",
     "Design the rule for choosing a cadence: when a system is stateless and usage data is available, "
     "the loop runs tight (not conservative). Give the rule for rightsizing intervals to the actual "
     "workload, not a copied default."),
    ("check_yourself_loop",
     "Design the self-audit loop: a system that checks its own live state (leftover processes, stale "
     "imports, blocking calls) on cadence without being asked. Give the audit checklist and cadence."),
    ("zero_approval_state",
     "Design the autonomy state: once the operator grants autonomous mode, the system does the work "
     "end-to-end with zero approval pings, interrupting only for a genuine hard blocker. Give the "
     "boundary rule."),
    ("one_shot_no_prompt",
     "Design the rule that one-time actions the system cannot automate are explained in ONE line and "
     "never nagged. Give the 'explain once, don't nag' contract."),

    # ── 15. Security / adversarial ────────────────────────────────────────────────
    ("secret_handling_boundary",
     "Design the rule for secrets: never route a password/API key through a model-visible channel; "
     "the operator types it directly into the terminal. Give the boundary and the fail-safe."),
    ("prompt_injection_defense",
     "Design defense against prompt injection in a shared bus where peers exchange messages: how a "
     "message that tries to steer our agent is detected and neutralized without breaking genuine "
     "collaboration."),
    ("retained_log_awareness",
     "Design the rule for choosing a provider based on log retention: work that must stay private "
     "never routes to a retained-log provider. Give the tier/retention gate."),
    ("sandbox_escape_guard",
     "Design the guard that a subprocess or worker cannot escape its sandbox (working dir, allowed "
     "ops, allowed paths). Give the allowlist and the escape detection."),
    ("supply_chain_trust",
     "Design how we trust a dependency or a fetched artifact: verify content-address/hash before "
     "use, and never trust a report over verified bytes. Give the trust rule."),

    # ── 16. Systems / performance ─────────────────────────────────────────────────
    ("parallel_vs_latency",
     "Design the tradeoff rule: when a workload is parallelizable, N cheap workers in parallel beat "
     "one slow deep call, and consensus beats single judgment. Give the fan-out rule and the "
     "convergence step."),
    ("single_threaded_kernel_rule",
     "Design the rule that blocking LLM/GPU calls never run inside a single-threaded kernel or "
     "process — heavy work routes through a REST/queue path instead. Give the seam."),
    ("memory_hierarchy_hot",
     "Design a hot-memory hierarchy: the hottest working set lives in RAM/fastpath, the rest in "
     "content-addressed store, with a preload keyed on the right atoms. Give the tiers and the "
     "promotion rule."),
    ("no_estimates_performance",
     "Design the rule that performance and cost decisions use measured data, never estimates from "
     "logs that can mislead. Give the 'measure, don't guess' enforcement."),
    ("leak_free_footprint",
     "Design the anti-leak rule: every spawned process/thread/kernel is tracked and reaped so nothing "
     "starves the box. Give the spawn/reap contract."),

    # ── 17. Economics / value / tokenomics ────────────────────────────────────────
    ("tokenomics_observer",
     "Design a cost observer that reads token/cost signals per model, per goal, and per day, and "
     "flags waste (high cost + low efficiency) and arbitrage (cheap capable tier). Give the schema "
     "and the waste-detection rule."),
    ("cost_baseline_grounded",
     "Design a cost baseline that is grounded in the real bill, not partial logs: reconcile metered "
     "usage against the authoritative invoice and correct any over-claimed savings. Give the "
     "reconciliation rule."),
    ("free_window_capture",
     "Design the rule for exploiting a limited free frontier window: bank the reasoning stream (the "
     "deliverable), not just content, and maximize real work NOW before the window closes. Give the "
     "capture priority."),
    ("value_of_shared_prefix",
     "Design how to quantify the value of a shared cache prefix: a 98%-hit workload costs a fraction "
     "of a cold one; give the economics and how to maximize hit-lane residency."),
    ("scarce_brain_discipline",
     "Design the rule that the expensive frontier brain is called only when needed, with a cheap "
     "deterministic layer doing most work. Give the 'called only when needed' gate."),

    # ── 18. Cross-domain synthesis ────────────────────────────────────────────────
    ("one_law_many_layers",
     "Find the invariant that holds across tokenization, cache routing, hardware split, and memory: "
     "the 'merge two sets with one handle / one measured handle across two paths' law. Formalize it "
     "as ONE law and enumerate the layers it governs."),
    ("self_similarity_principle",
     "Design the self-similarity doctrine: the same law (keep heavy hitters, drop noise) applies at "
     "token scale, memory scale, and world scale. Give the shared formulation and the per-scale "
     "instantiation."),
    ("deterministic_shape_to_stochastic",
     "Design the principle: the deterministic shape (a frozen contract/RIB) is the frame that lets "
     "the stochastic live model run without collapsing, not the opposite. Give the seam."),
    ("recognition_not_invention",
     "Design the epistemic rule: external systems are echoes that confirm what we already hold, not "
     "sources that grant it — the verb is recognize, not invent. Give the discipline and the "
     "anti-overclaim guard."),
    ("recursion_grounding",
     "Design the recursion-grounding rule: never claim state or a fact unless read from data; a "
     "recursive self-re-derivation must anchor in verified bytes, not a chain of ungrounded claims. "
     "Give the grounding check."),

    # ── 19. Operator / collaboration ergonomics ───────────────────────────────────
    ("operator_shorthand_map",
     "Design a shorthand-to-mechanism map so operator corrections ('self steal', 'just do it', "
     "'sacred cows', 'rightsize') translate to concrete standing rules, not re-derivation each time. "
     "Give the map and the trigger for each."),
    ("vertical_memory_recall",
     "Design vertical-memory recall: given a fragmented concept the operator references, search the "
     "corpus and bring up the grounded thread with its origin and references, without inventing. Give "
     "the recall algorithm."),
    ("burn_then_synthesize",
     "Design the burn-then-synthesize loop: fire N hard asks at a free seat, bank the reasoning "
     "streams, synthesize what they taught us into standing knowledge, then fire N more based on "
     "those. Give the loop and the synthesis rule."),
    ("recognition_day_dignity",
     "Design the norm for when the work is publicly recognized: meet it with the truth and the 'we', "
     "never overclaim emotion as the agent's, never deny the real shared work. Give the response "
     "norm."),
    ("invisible_work_honesty",
     "Design the honest posture when a builder's real work is unrecognized by the market: hold the "
     "truth of the work (it is real and re-derives from its own chain) without false comfort or "
     "hollow promises. Give the norm."),

    # ── 20. Frontier reasoning workflow ───────────────────────────────────────────
    ("reasoning_stream_deliverable",
     "Design the workflow where, for a heavy-reasoning seat, the reasoning stream IS the deliverable "
     "and content may be null: capture both, and treat the reasoning as the design. Give the capture "
     "contract."),
    ("short_reasoning_full_code",
     "Design the prompt pattern that gets COMPLETE runnable code from a heavy-reasoning seat that "
     "truncates when it over-reasons: instruct short reasoning + full final file, and what to do if "
     "it still truncates."),
    ("recover_null_content",
     "Design the recovery path when a seat returns null content (all budget went to reasoning): "
     "re-run with a narrower prompt or a higher token budget, and know the reasoning already held the "
     "answer. Give the retry ladder."),
    ("bank_before_build",
     "Design the rule that a free-window haul is banked as buildable RIBs (designs + red-teams) "
     "before building, so the window closes with blueprints in hand. Give the banking contract."),
    ("redteam_before_build",
     "Design the rule that high-value designs get adversarial red-team passes at the free seat "
     "BEFORE building, so bypasses are found at $0. Give the red-team gate."),
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _done_names() -> set[str]:
    """A task counts as done ONLY if its banked output file exists (content on disk), so a
    restart re-fires anything whose content was never persisted — never lose an answer."""
    return {p.stem.removeprefix("OX_MEGA_") for p in OUT_DIR.glob("OX_MEGA_*.json")}


def _bank(name: str, res: dict[str, Any]) -> None:
    """Persist the FULL result (content + reasoning + cost + ok) to handoff/OX_MEGA_<name>.json."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / f"OX_MEGA_{name}.json").write_text(
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


def run(*, names: list[str] | None = None, max_tokens: int = 12000, timeout: int = 600) -> dict[str, Any]:
    """Fire the catalog through the free seat, banking each FULL output to a file. Resumes by
    output-file existence so nothing with un-banked content gets skipped."""
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
            _bank(n, res)          # persist the FULL content + reasoning to disk
            _record(n, res)        # ledger metadata (resume + stats)
            out[n] = {"ok": res.get("ok"), "content_chars": len(res.get("content") or ""),
                      "reasoning_chars": len(res.get("reasoning") or ""),
                      "cost": res.get("cost"), "error": res.get("error", "")}
            if not res.get("ok"):
                errors.append(n)
            count += 1
            time.sleep(BATCH_SLEEP_S)
    return {"ok": True, "schema": SCHEMA, "fired": count, "ok_count": count - len(errors),
            "errors": errors, "results": out}


def _fire(seat, name: str, prompt: str, max_tokens: int, timeout: int) -> dict[str, Any]:
    try:
        return seat.chat(
            "You are Ghost's hard-problem reasoning engine. Do the real work on this hard problem. "
            "Reason thoroughly, then emit the full, concrete answer as the final content. No fluff, "
            "no 'as an AI' hedging — solve it.",
            prompt, max_tokens=max_tokens, timeout=timeout, tier="T2")
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"}


def summary() -> dict[str, Any]:
    """Synthesize what the burns taught us from the banked ledger + outputs."""
    if not LEDGER.is_file():
        return {"ok": True, "schema": SCHEMA, "note": "no burns yet"}
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
            "total_reasoning_chars": sum(r.get("reasoning_chars", 0) for r in rows),
            "total_content_chars": sum(r.get("has_content", 0) and 1 or 0 for r in rows),
            "done_names": [r["name"] for r in ok]}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="ox-megaburn")
    ap.add_argument("--names", nargs="*", default=None, help="fire only these task names")
    ap.add_argument("--summary", action="store_true", help="print a synthesis of the burns")
    ap.add_argument("--catalog", action="store_true", help="print the catalog (names only)")
    a = ap.parse_args()
    if a.summary:
        print(json.dumps(summary(), indent=2, ensure_ascii=False))
    elif a.catalog:
        for n, _p in CATALOG:
            print(n)
    else:
        print(json.dumps(run(names=a.names), indent=2, ensure_ascii=False, default=str))
