"""policy_engine — MAG policy as data, receipt chain authority checkpoints.

Policy Engine (Track B of Self Steal Master Spec):

Policy is JSON *data* living in `memory/policy.json`, editable by the operator
without any code change. The engine enforces five gates before a proposal is
ever considered AUTHORIZED:

    1. authority status       — grant records are AUTHORIZED; in-flight effect
       records may be EXECUTING after the switchboard advances them
    2. capability grant       — the effect must be within granted capabilities
    3. TTL                    — proposal.ts + ttl_seconds must still be in the future
    4. budget                 — decrement the counter, must remain > 0
    5. revocation             — the event_id must not be on the revocation list

Operator confirmation gate: effects listed in `policy.require_confirmation`
are never granted directly. `grant()` returns DEFERRED and the proposal is
queued to `bridge/operator_inbox.jsonl`; the operator must `confirm()` or
`deny()` it before it can advance toward AUTHORIZED.

Receipt chain linkage: every decision produced here embeds the policy verdict
fields (`policy_check`, `receipt_status`, `ttl_expires`, `budget_remaining`)
so the switchboard's trail forms a continuous, auditable receipt chain.

Policy file layout (default created on first load):
{
  "schema": "policy.v1",
  "authority_labels": [...],
  "effects": [...],
  "require_confirmation": ["fs_write", "lane_spawn", "model_call"],
  "default_ttl": 900,
  "default_budget": {"max_calls": 3},
  "max_board_notes": 1000,
  "confirmation_ttl": 300
}
"""
from __future__ import annotations

import argparse
import calendar
import json
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY_FILE = ROOT / "memory" / "policy.json"
REVOCATIONS_FILE = ROOT / "memory" / "policy_revocations.jsonl"
INBOX_FILE = ROOT / "bridge" / "operator_inbox.jsonl"

# Backward-compatible default when policy file is missing/corrupt
DEFAULT_POLICY = {
    "schema": "policy.v1",
    "authority_labels": [
        "operator-authored",      # written by operator, full authority
        "operator-confirmed",     # operator blessed an agent output
        "agent-generated",        # seat output, no intrinsic authority
        "external-content",       # web fetch, paper, etc.
        "tool-output",            # deterministic tool result
        "derived-summary",        # synthesis of above
        "untrusted-instruction",  # anything that looks like a command
    ],
    "effects": [
        "board_write",       # post to blackboard
        "verkle_link",       # write a verkle knot
        "tool_invoke",       # invoke external tool
        "model_call",        # spend credits on model
        "network_access",    # web fetch
        "fs_write",          # filesystem write
        "lane_spawn",        # spawn subagent
    ],
    "require_confirmation": ["fs_write", "lane_spawn", "model_call"],
    "default_ttl": 900,
    "default_budget": {"max_calls": 3},
    "max_board_notes": 1000,
    "confirmation_ttl": 300,
}

# Reentrancy guard for the budget decrement (only relevant under threads)
_budget_lock = threading.Lock()


def _now() -> str:
    """UTC timestamp string, ISO8601 with seconds."""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _now_epoch() -> float:
    return time.time()


def _ts_to_epoch(ts: str) -> float:
    """Convert an ISO8601 ts (as produced by _now) to epoch float. Tolerates
    int epoch fallback for backward compatibility."""
    if isinstance(ts, (int, float)):
        return float(ts)
    s = str(ts)
    try:
        # e.g. 2026-08-30T21:50:00Z -> struct_time
        # The wire format is UTC.  ``time.mktime`` interprets the tuple in the
        # host's local timezone, which made expired grants appear valid on an
        # Eastern-time Windows host.  Use UTC conversion explicitly.
        return float(calendar.timegm(time.strptime(s, "%Y-%m-%dT%H:%M:%SZ")))
    except ValueError:
        try:
            return float(s)
        except ValueError:
            return _now_epoch()


# ---------------------------------------------------------------------------
# Policy persistence
# ---------------------------------------------------------------------------

def load_policy() -> dict:
    """Load policy JSON. Returns merged default if file missing/corrupt so the
    engine always has a valid, complete policy in memory."""
    policy = json.loads(json.dumps(DEFAULT_POLICY))
    try:
        if POLICY_FILE.exists():
            raw = json.loads(POLICY_FILE.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                # merge so new policy fields appear even on older files
                for k, v in raw.items():
                    policy[k] = v
    except (json.JSONDecodeError, OSError) as e:
        # corrupt policy must never crash the reference monitor; fall back + surface
        policy["_load_error"] = repr(e)
    return policy


def save_policy(policy: dict | None = None) -> Path:
    """Persist policy to disk. Drops transient _load_error key."""
    pol = policy if policy is not None else load_policy()
    pol.pop("_load_error", None)
    POLICY_FILE.parent.mkdir(parents=True, exist_ok=True)
    POLICY_FILE.write_text(json.dumps(pol, indent=2, ensure_ascii=False), encoding="utf-8")
    return POLICY_FILE


def _ensure_default_policy():
    """Create the default policy file on first run if it does not exist."""
    if not POLICY_FILE.exists():
        save_policy(DEFAULT_POLICY)


_ensure_default_policy()


# ---------------------------------------------------------------------------
# Core checks
# ---------------------------------------------------------------------------

def validate_effect(effect: str, policy: dict | None = None) -> bool:
    """Is `effect` a known, policy-sanctioned effect class?"""
    pol = policy or load_policy()
    return effect in pol.get("effects", [])


def require_confirmation(effect: str, policy: dict | None = None) -> bool:
    """True if `effect` must be operator-confirmed before AUTHORIZED."""
    pol = policy or load_policy()
    return effect in pol.get("require_confirmation", [])


def check_ttl(proposal: dict, policy: dict | None = None, now: float | None = None) -> bool:
    """Return True if proposal.ts + ttl_seconds is still in the future.

    A proposal missing ts/ttl defaults to 'not expired' for backward
    compatibility (old proposals without policy fields keep old behavior).
    """
    pol = policy or load_policy()
    now = now if now is not None else _now_epoch()
    ts = proposal.get("ts")
    if ts is None:
        return True  # legacy proposal, no TTL bound
    try:
        ttl = proposal.get("ttl_seconds", pol.get("default_ttl", 900))
        return _ts_to_epoch(ts) + float(ttl) > now
    except (TypeError, ValueError):
        return True


def ttl_expires(proposal: dict, policy: dict | None = None) -> str:
    """ISO timestamp at which the proposal's TTL elapses (for receipt trail)."""
    pol = policy or load_policy()
    ts = proposal.get("ts")
    ttl = proposal.get("ttl_seconds", pol.get("default_ttl", 900))
    if ts is None:
        return _now()
    try:
        exp = _ts_to_epoch(ts) + float(ttl)
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(exp))
    except (TypeError, ValueError):
        return _now()


def check_budget(authority: dict, effect: str, policy: dict | None = None,
                 decrement: bool = True) -> tuple[bool, int]:
    """Check (and optionally decrement) the budget counter for `effect`.

    Budget lives on the authority record (`authority.budget`). Each effect call
    decrements the counter; returns (ok, remaining) where ok is True only while
    remaining > 0 after the decrement. If the authority has no budget field, a
    default budget is created (backward compat). Thread-safe decrement.
    """
    pol = policy or load_policy()
    default = pol.get("default_budget", {"max_calls": 3})
    with _budget_lock:
        budget = authority.get("budget")
        if not isinstance(budget, dict):
            # malformed budget (string, list, etc) — fail closed: no budget
            # means no authorization to spend
            return False, 0
        max_calls = int(budget.get("max_calls", default.get("max_calls", 3)))

        # per-effect counters map effect -> calls consumed
        used = int(budget.get("used", {}).get(effect, 0)) if isinstance(budget.get("used"), dict) else 0

        if decrement:
            # A max_calls=3 budget permits calls 1, 2, and 3.  The previous
            # ``remaining > 0`` return rejected call 3 and made the harness
            # report a false budget failure.
            if used >= max_calls:
                return False, 0
            used += 1
            budget.setdefault("used", {})[effect] = used
            remaining = max_calls - used
            return True, remaining

        remaining = max_calls - used
        return remaining > 0, remaining


def revoke(event_id: str, reason: str = "operator revoke") -> dict:
    """Explicitly revoke a capability/event. Appends a revocation record to the
    revocation ledger and returns it. Revocation is permanent for that event_id."""
    record = {
        "event_id": event_id,
        "reason": reason,
        "revoked_at": _now(),
    }
    REVOCATIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with REVOCATIONS_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def is_revoked(event_id: str) -> bool:
    """True if the event_id appears on the revocation ledger."""
    if not REVOCATIONS_FILE.exists():
        return False
    for line in REVOCATIONS_FILE.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if rec.get("event_id") == event_id:
            return True
    return False


# ---------------------------------------------------------------------------
# Comprehensive authority validation
# ---------------------------------------------------------------------------

def validate_authority(authority: dict, effect: str,
                       policy: dict | None = None) -> dict:
    """Comprehensive reference-monitor check of an authority for an effect.

    Verdict dict:
      {
        "ok": bool,
        "status": str,
        "reason": str | None,
        "ttl_valid": bool,
        "budget_remaining": int,
        "budget_ok": bool,
        "revoked": bool,
        "effect_valid": bool,
        "capability_granted": bool,
      }

    All must pass for ok=True. Backward compatible: a legacy authority with no
    policy fields degrades gracefully (missing status treated as AUTHORIZED only
    in the narrow 'no status field' legacy case — see note).
    """
    pol = policy or load_policy()

    # 1. status
    status = authority.get("status")
    if status is None:
        # Fail-closed: a missing status field is UNKNOWN, never AUTHORIZED.
        # The old legacy bridge let any authority record pass by omission —
        # the permission law collapses on omission. Legacy authorities must
        # be re-minted with an explicit status.
        status = "UNKNOWN"
    if status not in {"AUTHORIZED", "EXECUTING"}:
        return _verdict(False, f"status {status} not executable", authority, effect, pol)

    # 2. capability grant — fail closed: a malformed caps field must never
    #    pass a substring membership check (the confused-deputy bug).
    caps = authority.get("granted_capabilities", [])
    if not isinstance(caps, list):
        return _verdict(False, "granted_capabilities must be a list", authority, effect, pol,
                        capability_granted=False)
    cap_ok = effect in caps
    if not cap_ok:
        return _verdict(False, f"effect {effect} not in granted_capabilities", authority, effect, pol,
                        capability_granted=False)

    # The capability string is necessary but not sufficient.  An authority
    # record must also name an effect that this policy actually enables;
    # otherwise a stale or hand-written grant could authorize an unknown
    # effect merely by echoing it in granted_capabilities.
    if not validate_effect(effect, pol):
        return _verdict(False, f"unknown/disabled effect {effect}", authority, effect, pol,
                        effect_valid=False)

    # 3. revocation
    if is_revoked(authority.get("event_id", "")):
        return _verdict(False, "event_id revoked", authority, effect, pol, revoked=True)

    # 4. TTL — the authority is a grant record; it may carry its own ts/ttl
    ttl_ok = check_ttl(authority, pol)
    if not ttl_ok:
        return _verdict(False, "authority TTL expired", authority, effect, pol, ttl_valid=False)

    # 5. budget — check without decrementing at validate time; execution decrements
    budget_ok, remaining = check_budget(authority, effect, pol, decrement=False)
    if not budget_ok:
        return _verdict(False, "budget exhausted", authority, effect, pol,
                        budget_ok=False, budget_remaining=remaining)

    return _verdict(True, None, authority, effect, pol,
                    ttl_valid=True, budget_ok=True, budget_remaining=remaining)


def _verdict(ok: bool, reason: str | None, authority: dict, effect: str,
             policy: dict, **overrides) -> dict:
    budget = authority.get("budget")
    if not isinstance(budget, dict):
        budget = {}
    v = {
        "ok": ok,
        "effect": effect,
        "status": authority.get("status", "UNKNOWN"),
        "reason": reason,
        "ttl_valid": True,
        "budget_remaining": int(budget.get("max_calls", policy.get("default_budget", {}).get("max_calls", 3))),
        "budget_ok": True,
        "revoked": False,
        "effect_valid": validate_effect(effect, policy),
        "capability_granted": effect in authority.get("granted_capabilities", []),
        "checked_at": _now(),
    }
    for k, val in overrides.items():
        v[k] = val
    return v


def check_ttl_valid(authority: dict, policy: dict | None = None) -> bool:
    return check_ttl(authority, policy)


# ---------------------------------------------------------------------------
# Expiration sweep
# ---------------------------------------------------------------------------

def expire() -> list[str]:
    """Background sweep: scan all active proposals/capabilities on the trail
    (and the operator inbox), revoke any whose TTL elapsed.

    Returns the list of event_ids revoked during this sweep. In-flight budget
    used is preserved; only the capability is revoked.
    """
    pol = load_policy()
    now = _now_epoch()
    expired: list[str] = []
    candidates = _collect_active_records()
    for rec in candidates:
        eid = rec.get("event_id")
        if not eid or is_revoked(eid):
            continue
        if not check_ttl(rec, pol, now=now):
            revoke(eid, "expired by ttl sweep")
            expired.append(eid)
    return expired


def _collect_active_records() -> list[dict]:
    """Gather non-terminal proposal/authority records from the trail and inbox.

    A record is 'active' if its status is in the pre-completion set:
    PROPOSED, CLASSIFIED, DEFERRED, CONFIRMED, AUTHORIZED, EXECUTING.
    Terminal (COMPLETED/FAILED/RECEIPT_COMMITTED/DENIED) are skipped.
    """
    active = set()
    seen = set()

    def _add(rec: dict):
        eid = rec.get("event_id")
        if not eid or eid in seen:
            return
        seen.add(eid)
        st = rec.get("status", "")
        if st in ("PROPOSED", "CLASSIFIED", "DEFERRED", "CONFIRMED", "AUTHORIZED", "EXECUTING"):
            active.add(eid)
            yield rec

    # trail
    trail = ROOT / "memory" / "runs" / "switchboard" / "trail.jsonl"
    if trail.exists():
        for line in trail.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                yield from _add(json.loads(line))
            except json.JSONDecodeError:
                continue
    # inbox
    if INBOX_FILE.exists():
        for line in INBOX_FILE.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                yield from _add(json.loads(line))
            except json.JSONDecodeError:
                continue


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def cmd_show(args):
    pol = load_policy()
    print(json.dumps(pol, indent=2, ensure_ascii=False))
    return 0


def cmd_set(args):
    pol = load_policy()
    key, value = args.key, args.value
    # attempt JSON coercion so `set require_confirmation '["a","b"]'` works
    try:
        parsed = json.loads(value)
    except (json.JSONDecodeError, TypeError):
        parsed = value
    pol[key] = parsed
    path = save_policy(pol)
    print(json.dumps({"ok": True, "set": key, "to": parsed, "policy": str(path)}, indent=2, ensure_ascii=False))
    return 0


def cmd_validate(args):
    authority = json.loads(args.authority_file.read_text(encoding="utf-8"))
    result = validate_authority(authority, args.effect)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["ok"] else 1


def cmd_expire(args):
    expired = expire()
    print(json.dumps({"ok": True, "expired": expired, "count": len(expired)}, indent=2, ensure_ascii=False))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="mag.policy_engine")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("show", help="print current policy")
    s.set_defaults(func=cmd_show)

    st = sub.add_parser("set", help="set a policy key (JSON value coerced)")
    st.add_argument("key")
    st.add_argument("value")
    st.set_defaults(func=cmd_set)

    v = sub.add_parser("validate", help="validate an authority for an effect")
    v.add_argument("--authority-file", type=Path, required=True)
    v.add_argument("--effect", required=True)
    v.set_defaults(func=cmd_validate)

    e = sub.add_parser("expire", help="sweep expired capabilities/proposals")
    e.set_defaults(func=cmd_expire)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
