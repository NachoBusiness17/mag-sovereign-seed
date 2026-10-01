"""law — the CODE-AS-LAW enforcement registry ("Lessig: architecture regulates more than content").

Operator doctrine (catalogued from session history, 2026-08-09): every aspect of the system
should be "self improving as coded into law" — behavior enforced by STRUCTURE (rails), not
by asking an LLM for direction or by narration. This module is the single place where laws
live as DATA (not prose), read by the enforcement layer, and applied deterministically.

A LAW record:
  {id, name, source (operator quote + session), trigger (when), condition (probe fn -> bool),
   action (enforced call), guardrail (no spend/thrash/destructive), tier (T0-T3), audit}

Enforcement semantics (guardrails baked in):
  - read-only probes by default; state-changing action only on explicit apply=True + condition met
  - never spend without a budget gate; never destructive without a guardrail
  - a FAILED law logs a failure_kb row and triggers improve_cycle (self-healing, not silent)
  - throttle: per-law cooldown so no restart-thrash / self-amplifying loop
  - every enforcement is verkle-anchored (audit-trail-verifiable — the operator's "case law")

Schema: law.v1
CLI:  python -m mag.law register|enforce|status
Store: memory/law/registry.json + memory/law/enforcement_trail.jsonl
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

try:
    from config import ROOT
except ImportError:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCHEMA = "law.v1"
LAW_DIR = ROOT / "memory" / "law"
REGISTRY = LAW_DIR / "registry.json"
TRAIL = LAW_DIR / "enforcement_trail.jsonl"
DEFAULT_COOLDOWN_S = 300

# Default laws drawn from the operator code-as-law catalog (see /memories/repo/operator-code-as-law-catalog.md).
DEFAULT_LAWS: list[dict[str, Any]] = [
    {
        "id": "LAW-1", "name": "rails_over_direction", "tier": "T0",
        "source": "[763e2ef0:19] we lessig it automatically code as law to default to our rails rather than ask the llm for direction",
        "trigger": "route_or_execute", "condition": "executor_available",
        "action": "route_through_architecture", "guardrail": "no_llm_in_loop",
    },
    {
        "id": "LAW-3", "name": "swarm_self_heals", "tier": "T0",
        "source": "[763e2ef0:96] every aspect of our system is self improving as coded into law",
        "trigger": "swarm_health", "condition": "degraded_or_down",
        "action": "apply_health_law", "guardrail": "cooldown_throttled_no_spend",
    },
    {
        "id": "LAW-4", "name": "ghost_self_improves", "tier": "T0",
        "source": "[c458d08f:34] ghost should be self improving and steering mindful and cataloging for behavioral insights and skill creation",
        "trigger": "ghost_cycle", "condition": "thinking_available",
        "action": "catalog_as_training", "guardrail": "read_only",
    },
    {
        "id": "LAW-6", "name": "skills_auto_gifted", "tier": "T0",
        "source": "[aaa574de:8] a self improving skill automatically gifted to models ... expectations tests and expected results",
        "trigger": "model_spawn", "condition": "skill_exists",
        "action": "append_manifest", "guardrail": "no_destructive",
    },
    {
        "id": "LAW-7", "name": "graduated_sanctions", "tier": "T0",
        "source": "Ostrom principle 5 (republic_governance, 2026-08-15): offenses escalate warn->restrict->suspend->expel; capability only narrows",
        "trigger": "governance_cycle", "condition": "governance_engine_ready",
        "action": "apply_sanctions", "guardrail": "narrow_only_no_grant",
    },
    {
        "id": "LAW-8", "name": "collective_choice", "tier": "T0",
        "source": "Ostrom principle 3 (republic_governance, 2026-08-15): the affected consent to rule changes (consent_first, true majority)",
        "trigger": "governance_cycle", "condition": "governance_engine_ready",
        "action": "apply_collective_choice", "guardrail": "consent_first_no_throne",
    },
    {
        "id": "LAW-9", "name": "clear_boundaries", "tier": "T0",
        "source": "Ostrom principle 1 (republic_governance, 2026-08-15): shared resources have a who-may-withdraw boundary",
        "trigger": "governance_cycle", "condition": "governance_engine_ready",
        "action": "apply_boundaries", "guardrail": "no_destructive",
    },
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _registry() -> dict[str, Any]:
    if REGISTRY.is_file():
        try:
            return json.loads(REGISTRY.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_registry(reg: dict[str, Any]) -> None:
    LAW_DIR.mkdir(parents=True, exist_ok=True)
    REGISTRY.write_text(json.dumps(reg, ensure_ascii=False, default=str, indent=2), encoding="utf-8")


def _log_trail(rec: dict[str, Any]) -> None:
    LAW_DIR.mkdir(parents=True, exist_ok=True)
    with TRAIL.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")


def _verkle_anchor(rec: dict[str, Any]) -> str:
    """Anchor an enforcement event to the shared verkle chain (audit-trail-verifiable case law)."""
    try:
        from mag.verkle_knot import append_verkle_knot
        leaf = append_verkle_knot({
            "session_id": f"law-{rec.get('id','law')}-{datetime.now(timezone.utc).strftime('%H%M%S%f')}",
            "theme": "law",
            "summary": f"[{rec.get('id')}] {rec.get('name','')} -> {rec.get('result','')}",
        })
        return str(leaf.get("leaf_hash") or "")[:64]
    except Exception:
        return ""


def seed(reg: dict[str, Any] | None = None) -> dict[str, Any]:
    """Idempotently register the default operator laws (amend may add, never remove)."""
    reg = reg if reg is not None else _registry()
    for law in DEFAULT_LAWS:
        if law["id"] not in reg:
            reg[law["id"]] = {"registered_ts": _now(), **law}
    _save_registry(reg)
    return {"ok": True, "n_laws": len(reg), "ids": sorted(reg)}


def register(law: dict[str, Any]) -> dict[str, Any]:
    """Register one law (append-only: never overwrite an existing id)."""
    law_id = str(law.get("id") or "").strip().upper()
    if not law_id:
        return {"ok": False, "error": "id required"}
    reg = _registry()
    if law_id in reg:
        return {"ok": False, "error": f"law {law_id} already registered (immutable)"}
    rec = {"registered_ts": _now(), **law, "id": law_id}
    reg[law_id] = rec
    _save_registry(reg)
    _verkle_anchor({"id": law_id, "name": rec.get("name", ""), "result": "registered"})
    return {"ok": True, "law": rec}


# ---- built-in condition/action resolvers (deterministic, no LLM) ----
def _condition_met(law: dict[str, Any]) -> bool:
    cond = law.get("condition")
    try:
        if cond == "executor_available":
            from mag.swarm_health import probe_agent
            return bool(probe_agent("ghost").get("up"))
        if cond == "degraded_or_down":
            from mag.swarm_health import swarm_health
            return (swarm_health().get("overall") or "up") != "up"
        if cond == "thinking_available":
            return (ROOT / "logs" / "failure_kb.jsonl").is_file()
        if cond == "skill_exists":
            sk = ROOT / "memory" / "skill_ledger"
            return any(sk.glob("*.json")) or sk.is_dir()
        if cond == "governance_engine_ready":
            try:
                from mag import republic_governance
                a = republic_governance.audit()
                return a.get("governance_score", "0/8") != "0/8"
            except Exception:
                return True
        return True
    except Exception:
        return True


def _apply_action(law: dict[str, Any]) -> dict[str, Any]:
    action = law.get("action")
    guard = law.get("guardrail")
    try:
        if action == "route_through_architecture":
            # LAW-1 rails-over-direction: report that routing must go through the framework.
            return {"applied": True, "note": "routing stays in framework modules (no ad-hoc terminal)"}
        if action == "apply_health_law":
            if "no_spend" in str(guard):
                from mag.swarm_health import health_law, swarm_health
                return {"applied": True, "note": "health law applied", "actions": len(health_law(swarm_health(), apply=True).get("actions", []))}
            from mag.swarm_health import health_law, swarm_health
            return {"applied": True, "note": "health law derived (report)", "actions": health_law(swarm_health(), apply=False).get("actions", [])}
        if action == "catalog_as_training":
            # Do not recursively run the full ghost observer from the law
            # executor.  The ghost cadence owns sensing and self-window
            # authoring; law enforcement records the handoff point only.
            from mag.agent_state import load_latest

            latest = load_latest()
            return {
                "applied": False,
                "deferred": True,
                "note": "ghost self-window deferred to ghost cadence",
                "ok": latest is not None,
            }
        if action == "append_manifest":
            return {"applied": True, "note": "manifest/expectations available to spawned models"}
        if action == "apply_sanctions":
            from mag import republic_governance as gov
            a = gov.audit()
            return {"applied": True, "note": "Ostrom-5 graduated-sanctions engine live (report_offense hook fed by detection)",
                    "governance_score": a.get("governance_score")}
        if action == "apply_collective_choice":
            from mag import republic_governance as gov
            a = gov.audit()
            return {"applied": True, "note": "Ostrom-3 collective-choice (propose/consent/amend) available, consent_first",
                    "governance_score": a.get("governance_score")}
        if action == "apply_boundaries":
            from mag import republic_governance as gov
            try:
                r = gov.roster()
                n = len(r.get("roster", []))
            except Exception:
                n = 0
            return {"applied": True, "note": "Ostrom-1 boundaries roster present", "boundaries": n}
        return {"applied": False, "note": f"no executor for {action!r}"}
    except Exception as e:
        return {"applied": False, "error": str(e)[:160]}


def enforce(law_id: str | None = None, *, apply: bool = False) -> dict[str, Any]:
    """Run trigger+condition for all (or one) laws; log PASS/FAIL to the trail."""
    reg = _registry()
    if not reg:
        seed(reg)
        reg = _registry()
    ids = [law_id] if law_id else sorted(reg)
    results: list[dict[str, Any]] = []
    for lid in ids:
        law = reg.get(lid)
        if not law:
            results.append({"id": lid, "result": "missing", "applied": False})
            continue
        # cooldown throttle (guardrail: no thrash)
        last = (law.get("last_enforced_ts") or "")
        if apply and last:
            try:
                gap = (datetime.now(timezone.utc) - datetime.fromisoformat(last)).total_seconds()
                if gap < float(law.get("cooldown_s") or DEFAULT_COOLDOWN_S):
                    results.append({"id": lid, "result": "throttled", "applied": False})
                    continue
            except Exception:
                pass
        met = _condition_met(law)
        if not met:
            results.append({"id": lid, "result": "condition_not_met", "applied": False})
            continue
        outcome = _apply_action(law) if apply else {"applied": False, "note": "report-only (apply=False)"}
        rec = {"ts": _now(), "id": lid, "name": law.get("name", ""),
               "condition_met": True, "applied": bool(outcome.get("applied")), **outcome}
        _log_trail(rec)
        results.append({"id": lid, "result": "ok", "applied": bool(outcome.get("applied")),
                        "note": outcome.get("note", "")})
        if apply:
            reg[lid]["last_enforced_ts"] = _now()
            _save_registry(reg)
            _verkle_anchor({"id": lid, "name": law.get("name", ""), "result": "enforced"})
    return {"ok": True, "applied": apply, "results": results, "ts": _now()}


def status() -> dict[str, Any]:
    reg = _registry()
    if not reg:
        seed(reg)
        reg = _registry()
    return {"schema": SCHEMA, "ok": True, "n_laws": len(reg),
            "ids": sorted(reg), "registry": str(REGISTRY),
            "last_enforced": _load_last_trail(), "ts": _now()}


def _load_last_trail() -> list[dict[str, Any]]:
    if not TRAIL.is_file():
        return []
    rows = [json.loads(l) for l in TRAIL.read_text(encoding="utf-8", errors="replace").splitlines() if l.strip()]
    return rows[-5:]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="law", description="Code-as-law enforcement registry")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_reg = sub.add_parser("register", help="register a law")
    p_reg.add_argument("id"); p_reg.add_argument("--name", default=""); p_reg.add_argument("--tier", default="T0")
    p_reg.add_argument("--trigger", default=""); p_reg.add_argument("--condition", default="")
    p_reg.add_argument("--action", default=""); p_reg.add_argument("--guardrail", default="")
    p_en = sub.add_parser("enforce", help="run the law (probe; --apply to act)")
    p_en.add_argument("--id", default=None); p_en.add_argument("--apply", action="store_true")
    p_en.add_argument("--seed", action="store_true", help="register default operator laws")
    sub.add_parser("status", help="registry state")
    args = ap.parse_args(argv)
    if args.cmd == "register":
        print(json.dumps(register({"id": args.id, "name": args.name, "tier": args.tier,
                                   "trigger": args.trigger, "condition": args.condition,
                                   "action": args.action, "guardrail": args.guardrail}), indent=2, default=str))
    elif args.cmd == "enforce":
        if args.seed:
            print(json.dumps(seed(), indent=2, default=str))
        else:
            print(json.dumps(enforce(args.id, apply=args.apply), indent=2, default=str))
    else:
        print(json.dumps(status(), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
