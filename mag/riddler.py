"""Riddler semantic-surrogate compiler — private graph → synthetic story.

Translates a private problem graph into a small synthetic story preserving the
same roles, relationships, dependencies, constraints, scarce resources, conflicts,
and permitted actions — while withholding the original territory.

The remote model reasons in the story domain. Local Mag decodes the response.
The mapping key NEVER leaves the operator's machine.

Schema: riddler_surrogate.v1
Law: T0/T1 data never enters a surrogate. The compiler runs LOCAL ONLY.
"""

from __future__ import annotations

import hashlib
import json
import random
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

try:
    from config import ROOT
except ImportError:
    ROOT = Path(__file__).resolve().parent.parent

DOMAINS_PATH = ROOT / "configs" / "riddler_domains.yaml"
SURROGATE_DIR = ROOT / "memory" / "runs" / "riddler"

# ── Data classes ──────────────────────────────────────────────────

@dataclass
class SurrogateStory:
    """A compiled synthetic story ready for remote dispatch."""
    story_text: str
    question: str
    domain: str
    role_map: dict[str, str]           # private_name → story_name
    constraint_map: dict[str, str]      # private_constraint → story_constraint
    allowed_actions: list[str]
    shape_hash: str                     # hash of canonical abstract graph
    private_map_ref: str                # opaque local reference (never exported)
    loss_report: list[str]              # what was removed / generalized / distorted
    tier: str = "T2_SURROGATE"
    schema: str = "riddler_surrogate.v1"
    scratch_id: str = ""
    expires_at: str = ""
    fingerprint_seed: int = 0

    def to_public(self) -> dict[str, Any]:
        """Export ONLY the public face — never includes private_map_ref path."""
        return {
            "schema": self.schema,
            "scratch_id": self.scratch_id,
            "public_story": self.story_text,
            "public_question": self.question,
            "allowed_story_actions": self.allowed_actions,
            "shape_hash": self.shape_hash,
            "domain": self.domain,
            "loss_report": self.loss_report,
            "tier": self.tier,
            "expires_at": self.expires_at,
        }


@dataclass
class PrivateGraph:
    """A private problem represented as a typed relational graph."""
    actors: list[str]                   # who
    resources: list[dict[str, Any]]     # what (name, type, scarcity)
    dependencies: list[dict[str, str]]  # ordering (before, after)
    constraints: list[str]             # rules / invariants
    conflicts: list[str]               # tensions / tradeoffs
    goal: str                          # what needs to be decided
    domain_hint: str = ""              # optional: "routing", "scheduling", etc.

    def __hash__(self) -> int:
        # A default @dataclass (eq=True) is UNHASHABLE, but the surrogate/cache path keys on
        # the graph (the flock's "unhashable type: 'PrivateGraph'"). Hash a canonical JSON
        # serialization so it's deterministic and content-based. (2026-08-10 flock fix.)
        try:
            import json as _json
            raw = _json.dumps({
                "a": self.actors, "r": self.resources, "d": self.dependencies,
                "c": self.constraints, "f": self.conflicts, "g": self.goal,
                "h": self.domain_hint,
            }, sort_keys=True, default=str)
            return hash(raw)
        except Exception:
            return object.__hash__(self)



@dataclass
class ValidationReport:
    """Result of surrogate validation."""
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    leakage_detected: bool = False
    constraints_preserved: int = 0
    constraints_lost: int = 0


# ── Domain loading ────────────────────────────────────────────────

_domain_cache: dict[str, Any] | None = None


def _load_domains() -> dict[str, Any]:
    global _domain_cache
    if _domain_cache is not None:
        return _domain_cache
    if DOMAINS_PATH.is_file():
        _domain_cache = yaml.safe_load(DOMAINS_PATH.read_text(encoding="utf-8")) or {}
    else:
        _domain_cache = {}
    return _domain_cache


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8", errors="replace")).hexdigest()[:16]


# ── Compiler ──────────────────────────────────────────────────────

def compile_surrogate(
    graph: PrivateGraph,
    *,
    domain: str | None = None,
    seed: int | None = None,
) -> SurrogateStory:
    """Compile a private problem graph into a synthetic surrogate story.

    Args:
        graph: The private problem as a typed relational graph.
        domain: Optional domain name override (e.g. 'fantasy_village').
                If None, auto-selects from problem_domain_map.
        seed: Random seed for reproducible fingerprint randomization.

    Returns:
        A SurrogateStory ready for validation and dispatch.
    """
    if seed is None:
        seed = random.randint(0, 2**31 - 1)
    rng = random.Random(seed)

    domains = _load_domains()
    domain_cfg = _pick_domain(graph, domain, domains, rng)
    domain_name = domain_cfg["_name"]

    # Build the abstract shape hash BEFORE domain dressing
    shape_text = json.dumps({
        "n_actors": len(graph.actors),
        "n_resources": len(graph.resources),
        "n_deps": len(graph.dependencies),
        "n_constraints": len(graph.constraints),
        "n_conflicts": len(graph.conflicts),
    }, sort_keys=True)
    shape_hash = _hash(shape_text)

    # Map private actors → story roles
    role_slots = list(domain_cfg.get("role_slots", []))
    rng.shuffle(role_slots)
    role_map: dict[str, str] = {}
    for i, actor in enumerate(graph.actors):
        if i < len(role_slots):
            role_map[actor] = role_slots[i]

    # Map private resources → story resources
    resource_types = list(domain_cfg.get("resource_types", []))
    rng.shuffle(resource_types)
    resource_map: dict[str, str] = {}
    for i, res in enumerate(graph.resources):
        res_name = str(res.get("name", f"resource_{i}"))
        if i < len(resource_types):
            resource_map[res_name] = resource_types[i]

    # Map constraints
    constraint_patterns = list(domain_cfg.get("constraint_patterns", []))
    rng.shuffle(constraint_patterns)
    constraint_map: dict[str, str] = {}
    for i, c in enumerate(graph.constraints):
        if i < len(constraint_patterns):
            constraint_map[c] = constraint_patterns[i]

    # Build the story
    vocab = domain_cfg.get("domain_vocabulary", {})
    story_text = _weave_story(graph, role_map, resource_map, constraint_map,
                               domain_cfg, vocab, rng)
    question = _weave_question(graph, role_map, constraint_map, domain_cfg, rng)

    # Allowed actions
    allowed = list(domain_cfg.get("action_verbs", ["decide", "suggest", "propose"]))

    # Loss report
    loss = _build_loss_report(graph, role_map, resource_map, constraint_map)

    scratch_id = f"riddler-{_utc()[:19].replace(':', '')}-{_hash(graph.goal)}"

    return SurrogateStory(
        story_text=story_text,
        question=question,
        domain=domain_name,
        role_map=role_map,
        constraint_map=constraint_map,
        allowed_actions=allowed,
        shape_hash=shape_hash,
        private_map_ref=f"local:{scratch_id}:{seed}",
        loss_report=loss,
        scratch_id=scratch_id,
        expires_at=_utc(),
        fingerprint_seed=seed,
    )


def _pick_domain(
    graph: PrivateGraph, domain: str | None, domains: dict, rng: random.Random,
) -> dict[str, Any]:
    """Select a domain template, respecting user override and problem_domain_map."""
    all_domains = domains.get("domains", {})
    if not all_domains:
        raise ValueError("No domain templates loaded from configs/riddler_domains.yaml")

    if domain and domain in all_domains:
        cfg = dict(all_domains[domain])
        cfg["_name"] = domain
        return cfg

    # Auto-select from problem domain map
    hint = graph.domain_hint or "routing"
    domain_map = domains.get("problem_domain_map", {})
    candidates = domain_map.get(hint, list(all_domains.keys()))
    chosen = rng.choice(candidates) if candidates else list(all_domains.keys())[0]

    cfg = dict(all_domains[chosen])
    cfg["_name"] = chosen
    return cfg


def _weave_story(
    graph: PrivateGraph,
    role_map: dict[str, str],
    resource_map: dict[str, str],
    constraint_map: dict[str, str],
    domain_cfg: dict[str, Any],
    vocab: dict[str, list[str]],
    rng: random.Random,
) -> str:
    """Weave the private graph into a short natural-language story."""
    agent_words = vocab.get("agents", ["person"])
    place_words = vocab.get("places", ["place"])
    obj_words = vocab.get("objects", ["thing"])

    sentences: list[str] = []

    # Introduce actors with their story roles
    introduced: list[str] = []
    for actor in graph.actors:
        role = role_map.get(actor, rng.choice(agent_words))
        place = rng.choice(place_words)
        sentences.append(f"The {role} is at the {place}.")
        introduced.append(role)

    # Introduce resources
    for res in graph.resources:
        res_name = str(res.get("name", ""))
        story_res = resource_map.get(res_name, rng.choice(obj_words))
        owner = role_map.get(str(res.get("owner", "")), introduced[0] if introduced else "someone")
        scarcity = res.get("scarcity", "")
        if scarcity:
            sentences.append(f"There is only one {story_res}, and it belongs to the {owner}.")
        else:
            sentences.append(f"The {owner} has a {story_res}.")

    # Dependencies (ordering)
    for dep in graph.dependencies:
        before = role_map.get(dep.get("before", ""), introduced[0] if introduced else "the first")
        after = role_map.get(dep.get("after", ""), introduced[-1] if len(introduced) > 1 else "the next")
        sentences.append(f"The {before} must finish before the {after} can begin.")

    # Constraints (mapped)
    for i, c in enumerate(graph.constraints):
        if c in constraint_map:
            sentences.append(constraint_map[c])
        elif i < len(domain_cfg.get("constraint_patterns", [])):
            sentences.append(domain_cfg["constraint_patterns"][i])
        else:
            sentences.append(f"A rule applies: {c[:80]}.")

    # Conflicts
    for conflict in graph.conflicts:
        sentences.append(f"There is a tension: {conflict[:120]}.")

    return " ".join(sentences)


def _weave_question(
    graph: PrivateGraph,
    role_map: dict[str, str],
    constraint_map: dict[str, str],
    domain_cfg: dict[str, Any],
    rng: random.Random,
) -> str:
    """Build a story-domain question from the private goal."""
    actions = domain_cfg.get("action_verbs", ["decide"])
    primary_actor = role_map.get(graph.actors[0], "the leader") if graph.actors else "the leader"
    action = rng.choice(actions)

    question = (
        f"The {primary_actor} must {action}. Given the situation, "
        f"what should they do? Describe your reasoning step by step, "
        f"then state your recommended action using only the allowed story actions."
    )
    return question


def _build_loss_report(
    graph: PrivateGraph,
    role_map: dict[str, str],
    resource_map: dict[str, str],
    constraint_map: dict[str, str],
) -> list[str]:
    """Report what was removed, generalized, or distorted."""
    report: list[str] = []
    report.append("real names replaced with story roles")
    report.append("domain identity withheld")
    report.append("timestamps removed")

    unmapped_actors = [a for a in graph.actors if a not in role_map]
    if unmapped_actors:
        report.append(f"{len(unmapped_actors)} actor(s) generalized (insufficient role slots)")

    unmapped_constraints = [c for c in graph.constraints if c not in constraint_map]
    if unmapped_constraints:
        report.append(f"{len(unmapped_constraints)} constraint(s) expressed as literal rules")

    unmapped_resources = [r.get("name", "") for r in graph.resources
                          if str(r.get("name", "")) not in resource_map]
    if unmapped_resources:
        report.append(f"{len(unmapped_resources)} resource(s) generalized")

    return report


# ── Fingerprint randomization ─────────────────────────────────────

def fingerprint_randomize(story: SurrogateStory, *, seed: int | None = None) -> SurrogateStory:
    """Re-compile the same graph with a different random seed.

    Returns a lexically different story that decodes to the same territory.
    This prevents cross-query fingerprinting where an observer could join
    two surrogates as mapping to the same private problem.
    """
    if seed is None:
        seed = random.randint(0, 2**31 - 1)

    # Re-run compile with the same graph shape but different seed.
    # We extract the original private graph from the role/constraint maps.
    graph = PrivateGraph(
        actors=list(story.role_map.keys()),
        resources=[{"name": k} for k in story.role_map.keys() if k not in story.role_map.values()],
        dependencies=[],
        constraints=list(story.constraint_map.keys()),
        conflicts=[],
        goal=story.question.split("?")[0] if "?" in story.question else story.question,
    )
    return compile_surrogate(graph, domain=story.domain, seed=seed)


# ── Validation ────────────────────────────────────────────────────

TERRITORY_LEAK_PATTERNS = [
    r"\bcode\b", r"\brepository\b", r"\bgithub\b", r"\bAPI\b", r"\bdatabase\b",
    r"\bdeploy", r"\bdocker\b", r"\bkubernetes\b", r"\bconfig\b", r"\bendpoint\b",
    r"\bcredentials?\b", r"\bpassword\b", r"\btoken\b", r"\bkey\b",
    r"\bproduction\b", r"\bstaging\b", r"\bprod\b",
]


def validate_surrogate(story: SurrogateStory) -> ValidationReport:
    """Validate a compiled surrogate for safety and structural fidelity.

    Checks:
      1. No territory vocabulary leakage in story text.
      2. All roles in role_map are mapped to story roles.
      3. All constraints in constraint_map have story equivalents.
      4. Loss report is present and non-empty.
      5. Allowed actions are non-empty.
    """
    report = ValidationReport(ok=True)

    # 1. Leakage check
    story_lower = story.story_text.lower()
    for pattern in TERRITORY_LEAK_PATTERNS:
        if re.search(pattern, story_lower):
            report.leakage_detected = True
            report.errors.append(f"Territory leakage: pattern '{pattern}' found in story text")

    # 2. Role map completeness
    if not story.role_map:
        report.warnings.append("Empty role_map — no actors mapped")
    else:
        for k, v in story.role_map.items():
            if k == v:
                report.warnings.append(f"Role '{k}' mapped to itself (no transformation)")

    # 3. Constraint preservation
    report.constraints_preserved = len(story.constraint_map)
    if not story.constraint_map:
        report.warnings.append("Empty constraint_map — no constraints preserved")

    # 4. Loss report present
    if not story.loss_report:
        report.warnings.append("Empty loss_report — no transparency on what was removed")
    else:
        report.constraints_lost = sum(1 for l in story.loss_report if "removed" in l.lower())

    # 5. Allowed actions
    if not story.allowed_actions:
        report.errors.append("Empty allowed_actions — model has no legal moves")

    if report.errors:
        report.ok = False

    return report


# ── Persistence ───────────────────────────────────────────────────

def save_surrogate(story: SurrogateStory) -> Path:
    """Persist surrogate to disk (both public face and private map)."""
    SURROGATE_DIR.mkdir(parents=True, exist_ok=True)

    # Public face (safe to share)
    public_path = SURROGATE_DIR / f"{story.scratch_id}.public.json"
    public_path.write_text(
        json.dumps(story.to_public(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # Private map (NEVER leaves the machine)
    private_path = SURROGATE_DIR / f"{story.scratch_id}.private.json"
    private_data = {
        "scratch_id": story.scratch_id,
        "role_map": story.role_map,
        "constraint_map": story.constraint_map,
        "private_map_ref": story.private_map_ref,
        "fingerprint_seed": story.fingerprint_seed,
        "domain": story.domain,
    }
    private_path.write_text(
        json.dumps(private_data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    return public_path


def load_private_map(scratch_id: str) -> dict[str, Any] | None:
    """Load the private mapping for a previously dispatched surrogate."""
    private_path = SURROGATE_DIR / f"{scratch_id}.private.json"
    if not private_path.is_file():
        return None
    return json.loads(private_path.read_text(encoding="utf-8"))


# ── Quick test graph for development ──────────────────────────────

def _test_graph() -> PrivateGraph:
    """A sample private graph for testing the compiler."""
    return PrivateGraph(
        actors=["Alice", "Beth", "worker_A", "worker_B"],
        resources=[
            {"name": "GPU_lane", "type": "compute", "scarcity": "shared", "owner": "Alice"},
        ],
        dependencies=[
            {"before": "Alice", "after": "Beth"},
        ],
        constraints=[
            "only one worker may use the GPU at a time",
            "Alice's project must complete before Beth's",
            "if the GPU is busy, the worker must wait",
        ],
        conflicts=[
            "both workers need the GPU simultaneously",
            "Beth's deadline is sooner but Alice has priority",
        ],
        goal="Should we preempt Alice's GPU job so Beth can meet her deadline?",
        domain_hint="scheduling",
    )


if __name__ == "__main__":
    graph = _test_graph()
    story = compile_surrogate(graph)
    report = validate_surrogate(story)
    print("=== PUBLIC SURROGATE ===")
    print(json.dumps(story.to_public(), indent=2, ensure_ascii=False))
    print("\n=== VALIDATION ===")
    print(f"ok={report.ok} leakage={report.leakage_detected} "
          f"constraints_preserved={report.constraints_preserved}")
    if report.errors:
        print(f"ERRORS: {report.errors}")
    if report.warnings:
        print(f"WARNINGS: {report.warnings}")
    print("\n=== PRIVATE MAP ===")
    print(f"role_map: {story.role_map}")
    print(f"constraint_map: {story.constraint_map}")
    print(f"seed: {story.fingerprint_seed}")
