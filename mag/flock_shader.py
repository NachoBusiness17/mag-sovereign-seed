"""flock_shader — the swarm-as-shader language: MMO-scale for ~nothing.

Operator (2026-08-11): "if we can figure out this language we can have mmo scale for nothing and
have you running in the seams gathering more data than i can imagine."

THE LANGUAGE: agent = a PIXEL, field = the TEXTURE, k8s swarm = the GPU, ghost = the RENDERER.
A ShaderToy shader is a PURE FUNCTION (uniforms -> pixel color); the GPU renders a million pixels
for ~nothing because they run in lockstep on the same function. Our swarm becomes the same: a cheap,
stateless, data-parallel agent function evaluated across the whole flock, with the expensive
frontier reserved for the SEAMS (where agents disagree). This is the rightsized render-farm: render
cheap everywhere, shade the seams.

THE SHADER CONTRACT (an agent is exactly this):
    shade(seed, uniforms) -> state
    - PURE: same (seed, uniforms) -> same state (stateless + deterministic doctrine).
    - seed   : this agent's identity/context (position, role, task slice).
    - uniforms: the shared field (phi, steer, iTime, iMouse, budget) = the texture all pixels read.
    - state  : this agent's next state (position / action / answer), content-addressed.

THE RENDERER (ghost, running in the seams):
    render(agents, uniforms) -> states        (data-parallel, cheap-per-pixel)
    seams(states) -> [divergences]            (where agents disagree = spend frontier)
    inject(uniforms, seams) -> uniforms       (steer the next frame at the seams)

Schema: flock_shader.v1 · deterministic + $0 reference · the expensive shading is gated to seams.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field as dc_field
from typing import Any, Callable

SCHEMA = "flock_shader.v1"


# ── The shared field = the TEXTURE / UNIFORMS ────────────────────────────────────
@dataclass
class Uniforms:
    """The field all agent-pixels read (analogous to a shader's uniforms + channels).

    phi      : scalar field (distance-to-goal + invariant penalties) evaluated at a point.
    steer    : the frontier/operator steer block (injected as iMouse attractors).
    iTime    : evolution clock (frame index) — the flock lives, not just static.
    iMouse   : an explicit steer attractor (a target point / direction to bias toward).
    budget   : how much EXPENSIVE (frontier) shading this frame is allowed (0 = cheap-only).
    channels : list of extra input textures (evidence/retrieval/verifier outputs).
    """
    phi: Callable[[tuple[float, ...]], float] = lambda p: 0.0
    steer: list[str] = dc_field(default_factory=list)
    iTime: int = 0
    iMouse: tuple[float, float] | None = None
    budget: float = 0.0
    channels: list[Any] = dc_field(default_factory=list)


@dataclass
class AgentSeed:
    """This agent-pixel's identity (a point in the flock, like a fragment coordinate)."""
    id: int
    pos: tuple[float, ...]
    role: str = "probe"
    task: str = ""


# ── THE SHADER: a pure, data-parallel agent function ────────────────────────────
def shade(seed: AgentSeed, uniforms: Uniforms) -> dict[str, Any]:
    """The reference per-agent PURE function: (seed, uniforms) -> state.

    Deterministic + $0. Steers this pixel by -grad(phi) toward the goal + a small steering bias
    (iMouse), with a deterministic jitter seeded by the pixel id (so distinct pixels diversify,
    like flock separation). This is the 'cheap-per-pixel' render — no LLM, just math/hash.
    """
    p = seed.pos
    # -grad(phi): step opposite the field gradient (deterministic finite-difference).
    eps = 0.01
    grad = []
    for i in range(len(p)):
        ph = [*p]
        ph[i] += eps
        grad.append((uniforms.phi(tuple(ph)) - uniforms.phi(p)) / eps)
    force = tuple(-g for g in grad)
    # deterministic diversity per pixel (flock separation without central state)
    h = int(hashlib.sha256(f"{seed.id}:{uniforms.iTime}".encode("utf-8")).hexdigest(), 16)
    jitter = tuple(((h >> (8 * i)) % 200 - 100) / 1000.0 for i in range(len(p)))
    step_vec = tuple(force[i] * 0.1 + (jitter[i] if i < len(jitter) else 0.0)
                     for i in range(len(p)))
    # steer attractor (iMouse): pull toward it weakly
    if uniforms.iMouse is not None:
        target = uniforms.iMouse
        if len(target) == len(p):
            step_vec = tuple(step_vec[i] + 0.02 * (target[i] - p[i]) for i in range(len(p)))
    return {
        "seed": seed.id,
        "role": seed.role,
        "state": step_vec,           # this pixel's next state (vector)
        "content_hash": hashlib.sha256(
            f"{seed.id}:{uniforms.iTime}:{step_vec}".encode("utf-8")).hexdigest()[:16],
    }


def render(agents: list[AgentSeed], uniforms: Uniforms) -> list[dict[str, Any]]:
    """Render the flock: evaluate the SAME pure function across all agent-pixels, data-parallel.

    MMO-scale-for-nothing comes from this being a cheap, lockstep eval per pixel — the GPU/k8s
    runs them in parallel; ghost reads the aggregate register afterward.
    """
    return [shade(a, uniforms) for a in agents]


# ── THE SEAMS: where agents disagree = where to spend frontier ───────────────────
def seams(states: list[dict[str, Any]], *, tau: float = 0.05) -> list[dict[str, Any]]:
    """Detect the seams: agent-pixels whose state disagrees with the flock consensus.

    Disagreement = a GAP (uncertainty) = the ONLY place we spend expensive frontier shading.
    Cheap everywhere else. This is uncertainty-directed adaptive dicing (Reyes).
    """
    if not states:
        return []
    # consensus = component-wise mean of state vectors
    dim = len(states[0]["state"])
    mean = [sum(s["state"][i] for s in states) / len(states) for i in range(dim)]
    out = []
    for s in states:
        dev = sum((s["state"][i] - mean[i]) ** 2 for i in range(dim)) ** 0.5
        if dev > tau:
            out.append({"seed": s["seed"], "role": s["role"], "deviation": round(dev, 4)})
    out.sort(key=lambda x: -x["deviation"])
    return out


def rightsize_spend(seam_list: list[dict[str, Any]], *, budget: float) -> dict[str, Any]:
    """Right-size frontier spend: only the worst seams get expensive shading, capped by budget.

    Returns the seams that qualify + how much of the budget they consume (frontier = the seams).
    """
    budget = max(0.0, budget)
    qualified = []
    used = 0.0
    for s in seam_list:
        cost = min(1.0, s["deviation"])  # 1 frontier unit per seam, scaled by deviation
        if used + cost <= budget:
            qualified.append(s)
            used += cost
    return {"qualified": qualified, "used": round(used, 4), "budget": budget,
            "n_seams": len(seam_list), "n_shaded": len(qualified)}


def inject(uniforms: Uniforms, seam_list: list[dict[str, Any]], *, t: int) -> Uniforms:
    """Steer the next frame at the seams (ghost running in the seams): advance iTime and bias
    iMouse toward the worst seam so the flock converges there. Returns a new Uniforms.
    """
    u = Uniforms(phi=uniforms.phi, steer=list(uniforms.steer), iTime=t,
                 iMouse=uniforms.iMouse, budget=uniforms.budget, channels=list(uniforms.channels))
    if seam_list:
        # bias the attractor toward the highest-deviation seam's seed pos (approx: use its id)
        u.iMouse = (float(seam_list[0]["seed"]) * 0.01, float(seam_list[0]["seed"]) * 0.01)
    return u


# ── EVIDENCE LIGHTING (ShaderToy XsK3RR steal) — grounded synthesis ─────────────
# The shader is a LIGHT BUFFER: lights are DATA in a texture (origin, color, shadowmap) that every
# pixel reads; each pixel's color = surface * MixLights (sum of color * inverse-square falloff *
# shadow). Mapped to us (rib-renderman: light = evidence/grounding):
#   each Light = an evidence source (tool/doc/verifier/witness), stored in the shared register
#   inverse-square falloff = RELEVANCE DECAY (far evidence illuminates little)
#   shadow            = OCCLUSION BY CONTRADICTION (a blocked/contradicted source doesn't illuminate)
#   NUM_LIGHTS=6      = RIGHTSIZED (bounded evidence set, not a flood)
#   col *= MixLights  = grounded synthesis (agent answer = proposal x evidence-illumination)

@dataclass
class Light:
    """One evidence/grounding source (analogous to a light in the buffer)."""
    origin: tuple[float, ...]          # its position in the evidence space (relevance anchor)
    color: tuple[float, float, float] = (1.0, 1.0, 1.0)  # its contribution (type/sign)
    shadow: float = 1.0                # 1 = unoccluded/trusted, 0 = fully contradicted


def _dist(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    return sum((a[i] - b[i]) ** 2 for i in range(min(len(a), len(b)))) ** 0.5


def illuminate(pos: tuple[float, ...], lights: list[Light], *,
               ambient: tuple[float, float, float] = (0.1, 0.1, 0.1),
               max_lights: int = 6) -> tuple[float, float, float]:
    """Evidence-lighting: sum light contributions with inverse-square falloff + shadow.

    b = ambient + Σ color * (0.01 / (dist^2 + 0.01)) * shadow, over a RIGHTSIZED bounded set.
    Pure, deterministic, $0 — the 'grounded synthesis' pass. dist = relevance distance.
    """
    b = list(ambient)
    for l in (lights or [])[:max_lights]:
        dist = _dist(pos, l.origin)
        if dist < 1e-6:
            dist = 1e-6
        atten = 0.01 / (dist * dist + 0.01)   # inverse-square-ish, bounded
        contrib = atten * max(0.0, min(1.0, l.shadow))
        for i in range(3):
            b[i] += l.color[i] * contrib
    return (b[0], b[1], b[2])


def shadow_by_occlusion(l: Light, others: list[Light], *, tau: float = 0.3) -> float:
    """Occlusion by contradiction: a light is shadowed when a COUNTER source sits near it.

    Counter-ness = 1 - color-vector cosine similarity (opposite colors = contradiction). Returns
    shadow in [0,1]: 1 unoccluded, lower when a contradicting source overlaps its region. This is
    the divergence/gap detector applied to evidence: contradicted evidence doesn't illuminate.
    Deterministic + $0.
    """
    occ = 0.0
    for o in others:
        if o is l:
            continue
        if _dist(l.origin, o.origin) >= tau:
            continue
        n1 = sum(c * c for c in l.color) ** 0.5
        n2 = sum(c * c for c in o.color) ** 0.5
        if n1 < 1e-9 or n2 < 1e-9:
            continue
        sim = sum(l.color[i] * o.color[i] for i in range(3)) / (n1 * n2)
        occ = max(occ, 1.0 - sim)
    return max(0.0, 1.0 - occ)


def shade_illuminated(seed: AgentSeed, uniforms: Uniforms, lights: list[Light]) -> dict[str, Any]:
    """Grounded synthesis: the agent-pixel's proposal, MODULATED by evidence illumination.

    out = shade(seed, uniforms) x illuminate(pos, lights)  — the 'col *= MixLights' pass.
    The agent's state (surface) is evidence-lighted: close trusted evidence lifts it, contradicted
    evidence (shadowed) does not. Pure, deterministic, $0.
    """
    base = shade(seed, uniforms)
    lit = illuminate(seed.pos, lights)
    scaled = tuple(base["state"][i] * lit[0] for i in range(len(base["state"])))
    return {"seed": seed.id, "role": seed.role, "state": scaled,
            "light": lit, "content_hash": base["content_hash"]}


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "contract": "shade(seed, uniforms) -> state (pure, data-parallel)",
            "renderer": "render() data-parallel; seams() finds divergence; inject() steers",
            "rightsize": "cheap-per-pixel; frontier ONLY at seams, capped by Uniforms.budget",
            "lighting": "illuminate() = evidence-lighting (color x relevance falloff x shadow); "
                        "shadow_by_occlusion() = contradicted evidence is occluded",
            "note": "deterministic + $0 reference; the expensive shading is gated to seams"}


# ── THE RENDER FARM: shade only the seams, through the k8s swarm ─────────────────
def launch(agents: list[AgentSeed], uniforms: Uniforms, *, dry: bool = True,
           seam_budget: float | None = None) -> dict[str, Any]:
    """Route the SHADED SEAMS to the k8s swarm render farm (cheap first), per rightsize.

    The cheap-per-pixel flock itself is deterministic ($0, no dispatch). ONLY the SEAMS get
    shaded: render() -> seams() -> rightsize_spend() -> dispatch the qualified seam pixels to the
    swarm worker queue (drained in-cluster). dry=True = plan ($0, no dispatch).
    """
    states = render(agents, uniforms)
    seam_list = seams(states)
    budget = uniforms.budget if seam_budget is None else seam_budget
    rz = rightsize_spend(seam_list, budget=budget)
    out: dict[str, Any] = {"ok": True, "schema": SCHEMA, "dry": dry,
                           "n_agents": len(agents), "n_seams": len(seam_list),
                           "n_shaded": len(rz["qualified"]), "shaded": rz["qualified"]}
    if dry:
        out["tasks"] = [{"seed": s["seed"], "ok": True, "task_id": None}
                        for s in rz["qualified"]]
        return out
    from mag import swarm_worker as sw
    tasks = []
    for s in rz["qualified"]:
        goal = (f"[flock-shader seam seed {s['seed']}] Shade this diverging agent-pixel "
                f"(deviation {s['deviation']}): resolve the divergence against the flock field. "
                f"Return the corrected state + the invariant it exposes. Honest provenance.")
        try:
            r = sw.enqueue_task(goal, provider="deepseek", model="deepseek-chat",
                                domain="flock-seam", agent_idx=int(s["seed"]),
                                tag="flock-shader")
            tasks.append({"seed": s["seed"], "ok": bool(r.get("ok")),
                          "task_id": r.get("task_id")})
        except Exception as e:
            tasks.append({"seed": s["seed"], "ok": False, "error": str(e)[:80]})
    out["tasks"] = tasks
    out["n_dispatched"] = sum(1 for t in tasks if t.get("ok"))
    return out


def fold_gaps(seam_list: list[dict[str, Any]], *, domain: str = "flock_seams",
              budget: float | None = None) -> dict[str, Any]:
    """Fold seam divergences into the gap experiment as ESCALATION probes (shade the seams).

    A flock seam is a WITHIN-flock divergence that needs shading (frontier/LLM spend) — so each
    seam records as an ESCALATE decision, budget-gated by its deviation (cost = min(1, deviation)).
    Seams that exceed the budget are honestly reported as unescaped (never silently skipped).
    Deterministic + $0.
    """
    b = budget if budget is not None else max(1.0, len(seam_list))
    used = 0.0
    entries = []
    for s in seam_list:
        dev = float(s.get("deviation", 0.0))
        cost = min(1.0, dev)
        probe = f"{domain}:{s['seed']}"
        if used + cost > b:
            entries.append({"probe": probe, "divergence_score": round(dev, 4),
                            "decision": {"decision": "frontier_budget_exhausted", "escalate": False,
                                         "action": "report_unescaped_gap"}})
            continue
        used += cost
        entries.append({"probe": probe, "divergence_score": round(dev, 4),
                        "decision": {"decision": "escalate", "escalate": True,
                                     "action": "shade_seam",
                                     "reason": f"flock seam deviation {round(dev, 4)} needs shading"}})
    return {"ok": True, "schema": "flock_gap_fold.v1", "n_seams": len(seam_list),
            "n_escalated": sum(1 for e in entries if e["decision"]["escalate"]),
            "budget": b, "used": round(used, 4), "entries": entries}


if __name__ == "__main__":
    import json, argparse
    ap = argparse.ArgumentParser(prog="flock-shader")
    ap.add_argument("cmd", nargs="?", default="status", choices=["status", "launch", "fold-gaps"])
    ap.add_argument("--dry", action="store_true", default=True)
    a = ap.parse_args()
    if a.cmd == "launch":
        # demo: a small flock with a goal field, dispatch seams to the swarm (dry by default)
        from mag.flock_shader import (Uniforms, AgentSeed, launch)
        phi = lambda p: (p[0] ** 2 + p[1] ** 2) ** 0.5
        ag = [AgentSeed(id=i, pos=(float(i % 3 - 1), float(i % 2))) for i in range(6)]
        u = Uniforms(phi=phi, iTime=0, budget=2.0)
        print(json.dumps(launch(ag, u, dry=a.dry), indent=2, default=str))
    elif a.cmd == "fold-gaps":
        print(json.dumps(fold_gaps([{"seed": 1, "deviation": 0.9}]), indent=2, default=str))
    else:
        print(json.dumps(status(), indent=2, default=str))
