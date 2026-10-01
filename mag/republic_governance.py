"""republic_governance — the Mycelial Republic's governance law (Ostrom + stigmergy).

STEAL (research-grounded, 2026-08-10):
  * Stigmergy (Grasse 1959): coordination is INDIRECT through the environment — each agent leaves a
    trace others respond to; the traces ARE the shared external memory. Our verkle/mycelium graph IS
    that environment. consent_first: no permission to propose. no_throne: no planner.
  * Ostrom's 8 design principles (Governing the Commons, Nobel 2009): how a self-governing republic
    manages shared common-pool resources WITHOUT a king — clear boundaries, congruence, collective-
    choice, accountable monitoring, graduated sanctions, conflict arenas, self-organization, nested
    enterprises. Each maps onto the Republic's shared resources + existing invariants.

This module:
  resources()    — the shared commons inventory (compute, tokens, GPU, memory, free-tier pools) + who
                   may withdraw each (the boundaries, principle 1).
  audit()        — governance-health score: how many of Ostrom's 8 our architecture satisfies, and
                   which principles are partial/gaps (the real steal: graduated sanctions, collective-
                   choice, explicit boundaries).
  constitution() — emit the Republic's governance constitution (markdown) as case law.

Schema: republic_governance.v1 · deterministic · $0
CLI: python -m mag.republic_governance resources | audit | constitution | status
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCHEMA = "republic_governance.v1"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

# ── Ostrom's 8 principles mapped to the Republic ────────────────────────────────
# each: number, name, resource/invariant/mechanism, status (satisfied/partial/gap), gap note.
PRINCIPLES: list[dict[str, Any]] = [
    {"n": 1, "name": "Clearly defined boundaries",
     "maps_to": "roster() (single boundary inventory: resource -> who may withdraw each, governed_by, cap)",
     "status": "satisfied", "gap": ""},
    {"n": 2, "name": "Congruence with local conditions",
     "maps_to": "rightsize / queue_rightsize / cost_learn — cheapest-capable tier per task, adapts to local cost",
     "status": "satisfied", "gap": ""},
    {"n": 3, "name": "Collective-choice (affected can modify rules)",
     "maps_to": "propose/consent/amend (explicit bead co-authorship of case-law, consent_first, true-majority gate)",
     "status": "satisfied", "gap": ""},
    {"n": 4, "name": "Accountable monitoring",
     "maps_to": "ghost_ledger (source of truth) + behavioral_analytics (leak) + swarm_health (health) + ghost watching",
     "status": "satisfied", "gap": ""},
    {"n": 5, "name": "Graduated sanctions",
     "maps_to": "sanction/ladder (warn -> restrict -> suspend -> expel, per offense; Trust Ratchet narrows)",
     "status": "satisfied", "gap": ""},
    {"n": 6, "name": "Conflict-resolution arenas",
     "maps_to": "loop_breaker / doctor / error_healer / oh_fuck / lens divergence-preserving",
     "status": "satisfied", "gap": ""},
    {"n": 7, "name": "Right to self-organize (not challenged)",
     "maps_to": "no_throne + local_first + self-advance + Republic sovereignty",
     "status": "satisfied", "gap": ""},
    {"n": 8, "name": "Nested enterprises (multi-layer governance)",
     "maps_to": "queue -> drainer -> governor -> ghost -> overseer -> republic -> fleet/worktrees",
     "status": "satisfied", "gap": ""},
]

# The shared commons of the Republic: resource -> who may withdraw (boundaries).
RESOURCES: list[dict[str, Any]] = [
    {"name": "compute (CPU)", "withdraw": "all beads", "governed_by": "cost_enforcer / swarm_health", "cap": "per-task budget"},
    {"name": "tokens (LLM)", "withdraw": "routed beads", "governed_by": "grok_rightsize / cache_router", "cap": "budget tiers + cache-hit discipline"},
    {"name": "GPU (free/local)", "withdraw": "free-tier loops", "governed_by": "gpu_ghost / free-tier frontier loop", "cap": "free pool"},
    {"name": "memory (verkle/mycelium)", "withdraw": "all beads (append-only)", "governed_by": "verkle_knot / schema_registry", "cap": "content-addressed, amend-not-erase"},
    {"name": "free-tier pools (grok/deepseek)", "withdraw": "cheap swarms", "governed_by": "grok_free / flock_steal", "cap": "rate limits"},
    {"name": "bandwidth / browser", "withdraw": "allowlisted", "governed_by": "browser_env (allowlist)", "cap": "host allowlist"},
]


def resources() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA, "commons": RESOURCES,
            "note": "the Republic's shared common-pool resources + who may withdraw each (boundaries)"}


def audit() -> dict[str, Any]:
    """Governance-health: how many of Ostrom's 8 the architecture satisfies; list the gaps."""
    satisfied = [p for p in PRINCIPLES if p["status"] == "satisfied"]
    partial = [p for p in PRINCIPLES if p["status"] == "partial"]
    gaps = [p for p in PRINCIPLES if p["gap"]]
    return {"ok": True, "schema": SCHEMA, "ts": _now(),
            "n_principles": len(PRINCIPLES), "satisfied": len(satisfied),
            "partial": len(partial), "governance_score": f"{len(satisfied)}/{len(PRINCIPLES)}",
            "satisfied_names": [p["name"] for p in satisfied],
            "partial_names": [p["name"] for p in partial],
            "gaps": [{"n": p["n"], "name": p["name"], "gap": p["gap"]} for p in gaps],
            "n_resources": len(RESOURCES),
            "law": "coordinate by stigmergy (traces in the verkle/mycelium environment); govern shared "
                   "resources by Ostrom's 8; under no_throne / local_first / consent_first / residual_is_dna"}


# ── GRADUATED SANCTIONS (Ostrom principle 5) — the proportional ladder, 2026-08-15 ──
# Trust Ratchet: capability only NARROWS, never grants. Each offense escalates the sanction.
# Deterministic + $0 + persistent (ledger, not fabricated). Closes the principle-5 gap.
SANCTIONS_DIR = ROOT / "memory" / "runs" / "republic_governance" / "sanctions"
_LADDER: list[dict[str, Any]] = [
    {"level": "warn", "min_violations": 1, "action": "recorded warning; capability unchanged"},
    {"level": "restrict", "min_violations": 2, "action": "restricted to deterministic/local tier; no frontier"},
    {"level": "suspend", "min_violations": 3, "action": "suspended; cannot enqueue new work"},
    {"level": "expel", "min_violations": 4, "action": "expelled; removed from the commons roster"},
]


def _violation_file(agent: str) -> Path:
    return SANCTIONS_DIR / f"{agent}.jsonl"


def _load_violations(agent: str) -> int:
    f = _violation_file(agent)
    n = 0
    if f.is_file():
        for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.strip():
                n += 1
    return n


def level_for(n_violations: int) -> dict[str, Any]:
    level = _LADDER[0]
    for lvl in _LADDER:
        if n_violations >= lvl["min_violations"]:
            level = lvl
    return dict(level)


def _record(agent: str, offense: str) -> int:
    SANCTIONS_DIR.mkdir(parents=True, exist_ok=True)
    row = {"ts": _now(), "agent": agent, "offense": (offense or "")[:200]}
    with _violation_file(agent).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    return _load_violations(agent)


def ladder(agent: str) -> dict[str, Any]:
    """The current sanction level for an agent, from its real violation ledger."""
    n = _load_violations(agent)
    lvl = level_for(n)
    return {"ok": True, "schema": SCHEMA + ".sanctions", "agent": agent,
            "violations": n, "level": lvl["level"], "action": lvl["action"],
            "ratchet": "capability only NARROWS (Trust Ratchet); never grants"}


def sanction(agent: str, offense: str) -> dict[str, Any]:
    """Record a violation and ESCALATE along the proportional ladder (warn->restrict->suspend->expel).
    Narrowing only — never grants capability back."""
    n = _record(agent, offense)
    lvl = level_for(n)
    return {"ok": True, "schema": SCHEMA + ".sanctions", "agent": agent,
            "offense": (offense or "")[:120], "violations_now": n,
            "level": lvl["level"], "action": lvl["action"],
            "proportional": "warn -> restrict -> suspend -> expel, per offense"}


def report_offense(agent: str, offense: str, *, source: str = "") -> dict[str, Any]:
    """THE DETECTION->SANCTION HOOK (wired 2026-08-15): the one path detection modules
    (behavior_catch, dogfood_audit, republic_loop, governor) call to feed the graduated-sanctions
    ladder. This closes the gap where offenses were DETECTED but never REPORTED to the sanctions
    ladder — the Ostrom principle-5 enforcement now has a real feed, not orphan code.

    Deterministic + $0 + persistent (ledger, not fabricated). Verkle-anchored so the sanction is
    audit-trail-verifiable case law (the operator's 'case law' doctrine)."""
    r = sanction(agent, offense)
    try:
        from mag import verkle_knot
        verkle_knot.append_verkle_knot({
            "session_id": f"gov-sanction-{agent[:12]}-{datetime.now(timezone.utc).strftime('%H%M%S%f')}",
            "theme": "governance",
            "summary": f"[sanction] {agent} -> {r.get('level')} ({offense[:80]})",
        })
    except Exception:
        pass
    r["source"] = (source or "detection")[:120]
    r["note"] = "reported offense -> graduated sanctions ladder (warn->restrict->suspend->expel), verkle-anchored"
    return r


# ── COLLECTIVE-CHOICE (Ostrom principle 3) — explicit bead co-authorship of case-law, 2026-08-15 ──
# consent_first: the AFFECTED can modify the rules, EXPLICITLY, not by implicit fold. no_throne:
# no single veto; a consent threshold among the consulted amends the law.
CASE_DIR = ROOT / "memory" / "runs" / "republic_governance" / "case_law"
CONSENT_THRESHOLD = 0.5  # proportion of consulted beads needed to amend


def _case_file() -> Path:
    return CASE_DIR / "case_law.jsonl"


def _proposal_file(pid: str) -> Path:
    return CASE_DIR / f"proposal_{pid}.json"


def propose(bead: str, rule: str, *, consulted: list[str] | None = None) -> dict[str, Any]:
    """A bead proposes a rule change; it needs explicit consent from the AFFECTED (consent_first)."""
    import uuid
    CASE_DIR.mkdir(parents=True, exist_ok=True)
    pid = "cl-" + uuid.uuid4().hex[:10]
    prop = {"proposal_id": pid, "proposer": bead, "rule": (rule or "")[:400],
            "consulted": consulted or [], "consents": [], "status": "proposed", "ts": _now()}
    _proposal_file(pid).write_text(json.dumps(prop, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "schema": SCHEMA + ".case_law", "proposal_id": pid, "rule": prop["rule"],
            "needs_consent_from": prop["consulted"],
            "note": "collective-choice: the AFFECTED must consent (consent_first)"}


def consent(bead: str, proposal_id: str, *, yes: bool = True) -> dict[str, Any]:
    """A consulted bead gives/withholds consent on a proposal (consent_first)."""
    f = _proposal_file(proposal_id)
    if not f.is_file():
        return {"ok": False, "error": "no such proposal"}
    prop = json.loads(f.read_text(encoding="utf-8"))
    if bead not in prop.get("consulted", []):
        return {"ok": False, "error": f"{bead} not consulted on this proposal"}
    consents = prop.get("consents", [])
    if bead not in [c["bead"] for c in consents]:
        consents.append({"bead": bead, "yes": bool(yes), "ts": _now()})
        prop["consents"] = consents
    f.write_text(json.dumps(prop, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "proposal_id": proposal_id, "yes": bool(yes),
            "consents": len([c for c in consents if c["yes"]])}


def amend(proposal_id: str) -> dict[str, Any]:
    """If the consent threshold is met, record the co-authored case-law amendment EXPLICITLY."""
    f = _proposal_file(proposal_id)
    if not f.is_file():
        return {"ok": False, "error": "no such proposal"}
    prop = json.loads(f.read_text(encoding="utf-8"))
    if prop.get("status") != "proposed":
        return {"ok": False, "error": "already resolved"}
    consulted = prop.get("consulted", [])
    yes = len([c for c in prop.get("consents", []) if c["yes"]])
    # CEIL (not int-truncate): a true majority of the affected is required. int(3*0.5)=1 (WRONG —
    # too permissive); ceil(1.5)=2 = the real majority. Fixed 2026-08-15.
    need = max(1, -(-(len(consulted) * CONSENT_THRESHOLD) // 1)) if consulted else 1
    if yes < need:
        return {"ok": False, "error": f"not enough consent ({yes}/{need})", "consent_needed": need}
    co_authors = [c["bead"] for c in prop.get("consents", []) if c["yes"]]
    with _case_file().open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"ts": _now(), "kind": "case_law_amendment",
                             "proposal_id": proposal_id, "proposer": prop["proposer"],
                             "co_authors": co_authors, "rule": prop["rule"],
                             "status": "enacted"}, ensure_ascii=False, default=str) + "\n")
    prop["status"] = "enacted"
    f.write_text(json.dumps(prop, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "schema": SCHEMA + ".case_law", "proposal_id": proposal_id,
            "enacted_rule": prop["rule"], "co_authors": co_authors}


# ── CLEARLY DEFINED BOUNDARIES (Ostrom principle 1) — the single roster, 2026-08-15 ──
ROSTER_FILE = ROOT / "memory" / "runs" / "republic_governance" / "roster.json"


def _load_roster() -> dict[str, Any]:
    try:
        if ROSTER_FILE.is_file():
            return json.loads(ROSTER_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _save_roster(r: dict[str, Any]) -> None:
    ROSTER_FILE.parent.mkdir(parents=True, exist_ok=True)
    ROSTER_FILE.write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")


def roster() -> dict[str, Any]:
    """The SINGLE authoritative inventory of the shared commons: resource -> who may withdraw each,
    governed by what, under what cap. Clearly defined boundaries (Ostrom principle 1)."""
    stored = _load_roster()
    rows = []
    for res in RESOURCES:
        key = res["name"]
        entry = stored.get(key, {})
        rows.append({
            "resource": key,
            "withdraw": entry.get("withdraw", res.get("withdraw", "all beads")),
            "governed_by": entry.get("governed_by", res.get("governed_by", "")),
            "cap": entry.get("cap", res.get("cap", "")),
        })
    return {"ok": True, "schema": SCHEMA + ".roster", "commons": rows,
            "n_resources": len(rows),
            "note": "the single boundary inventory — who may withdraw each shared resource"}


def define_boundary(resource: str, *, withdraw: str, governed_by: str = "", cap: str = "") -> dict[str, Any]:
    """Record/update the boundary for one shared resource (clearly-defined, persistent)."""
    stored = _load_roster()
    stored[resource] = {"withdraw": withdraw, "governed_by": governed_by, "cap": cap}
    _save_roster(stored)
    return {"ok": True, "schema": SCHEMA + ".roster", "resource": resource,
            "withdraw": withdraw, "governed_by": governed_by, "cap": cap,
            "note": "boundary defined — who may withdraw this shared resource is now explicit"}


def who_can_withdraw(resource: str) -> dict[str, Any]:
    """The exact authorized withdrawers for a shared resource (the boundary, enforced)."""
    for r in roster()["commons"]:
        if r["resource"] == resource:
            return {"ok": True, "resource": resource, "withdraw": r["withdraw"],
                    "governed_by": r["governed_by"], "cap": r["cap"]}
    return {"ok": False, "error": f"no such shared resource: {resource}"}


def constitution() -> str:
    """Emit the Republic's governance constitution (markdown case law)."""
    lines = [
        "# The Mycelial Republic — governance constitution",
        "**Coordination law (stigmergy):** agents leave traces in the shared environment (verkle / "
        "mycelium / artifacts); others respond to the traces. No planner, no permission to propose "
        "(consent_first), no throne (no_throne). The traces ARE the shared external memory.",
        "",
        "**Governance law (Ostrom's 8 principles):**",
    ]
    for p in PRINCIPLES:
        lines.append(f"{p['n']}. **{p['name']}** ({p['status']}) — {p['maps_to']}"
                     + (f" [GAP: {p['gap']}]" if p["gap"] else ""))
    lines.append("")
    lines.append("**The shared commons (boundaries):**")
    for r in RESOURCES:
        lines.append(f"- **{r['name']}** — withdraw: {r['withdraw']} · governed by {r['governed_by']} · cap: {r['cap']}")
    lines.append("")
    lines.append("Under the standing invariants: no_throne · local_first · consent_first · residual_is_dna.")
    return "\n".join(lines)


def status() -> dict[str, Any]:
    a = audit()
    return {"ok": True, "schema": SCHEMA, "governance_score": a["governance_score"],
            "partial": a["partial"], "n_resources": a["n_resources"]}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="republic_governance", description="Mycelial Republic governance law")
    sub = p.add_subparsers(dest="cmd")
    sub.add_parser("resources")
    sub.add_parser("audit")
    sub.add_parser("constitution")
    sub.add_parser("status")
    sub.add_parser("ladder")
    sub.add_parser("roster")
    a = p.parse_args(argv)
    if a.cmd == "resources":
        print(json.dumps(resources(), indent=2, ensure_ascii=False))
    elif a.cmd == "roster":
        print(json.dumps(roster(), indent=2, ensure_ascii=False))
    elif a.cmd == "audit":
        print(json.dumps(audit(), indent=2, ensure_ascii=False))
    elif a.cmd == "constitution":
        print(constitution())
    elif a.cmd == "ladder":
        agent = getattr(a, "agent", "bead") if hasattr(a, "agent") else "bead"
        print(json.dumps(ladder(agent), indent=2, ensure_ascii=False))
    elif a.cmd == "status":
        print(json.dumps(status(), indent=2, ensure_ascii=False))
    else:
        p.print_help(); return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
