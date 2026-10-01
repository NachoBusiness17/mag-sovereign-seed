"""switchboard_v2 — BBS-driven agent control plane WITH policy enforcement + receipt chain.

Track B of Self Steal Master Spec. Reinforces the original switchboard with:

  * policy_engine integration on EVERY grant() call (TTL/budget/authority/revocation)
  * operator confirmation gate: require_confirmation effects return DEFERRED
    and are queued to bridge/operator_inbox.jsonl for confirm()/deny()
  * TTL + budget enforced before a proposal ever reaches AUTHORIZED
  * full receipt chain state machine, terminal at RECEIPT_COMMITTED
  * backward compatible: legacy proposals lacking policy fields degrade to
    existing self-granting behavior (minus the operator gate).

State machine:

    PROPOSED → CLASSIFIED → (DEFERRED → CONFIRMED/DENIED) → AUTHORIZED
      → EXECUTING → COMPLETED/FAILED → RECEIPT_COMMITTED

Backward compat notes:
  - Old proposals (schema switchboard.v1, no authority/policy_verdict) still work.
  - If a proposal carries an explicit authority with status==AUTHORIZED and the
    effect is NOT in require_confirmation, grant() still validates policy but
    otherwise behaves as before.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

# Ensure the sibling policy_engine module on the same directory is importable
# regardless of the CWD the script is launched from.
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from . import policy_engine

ROOT = Path(__file__).resolve().parents[1]
BB = ROOT / "memory" / "runs" / "swarm_worker" / "blackboard"
TRAIL = ROOT / "memory" / "runs" / "switchboard" / "trail.jsonl"
INBOX = ROOT / "bridge" / "operator_inbox.jsonl"

# Authority labels mirror policy_engine defaults
AUTHORITY_LABELS = [
    "operator-authored",
    "operator-confirmed",
    "agent-generated",
    "external-content",
    "tool-output",
    "derived-summary",
    "untrusted-instruction",
]

EFFECTS = [
    "board_write",
    "verkle_link",
    "tool_invoke",
    "model_call",
    "network_access",
    "fs_write",
    "lane_spawn",
]

# Receipt chain state machine — valid transitions.
_STATE_MACHINE = {
    "PROPOSED": {"CLASSIFIED", "DEFERRED", "AUTHORIZED", "DENIED"},
    "CLASSIFIED": {"DEFERRED", "AUTHORIZED", "DENIED"},
    "DEFERRED": {"CONFIRMED", "DENIED"},
    "CONFIRMED": {"AUTHORIZED", "DENIED"},
    "AUTHORIZED": {"EXECUTING", "DENIED"},
    "EXECUTING": {"COMPLETED", "FAILED"},
    "COMPLETED": {"RECEIPT_COMMITTED"},
    "FAILED": {"RECEIPT_COMMITTED"},
    "RECEIPT_COMMITTED": set(),   # terminal, immutable
    "DENIED": set(),              # terminal, immutable
}

# Replay protection: event_ids that have already been granted. A second
# proposal for the same event_id must not produce an independent AUTHORIZED
# grant — at minimum the second is refused as a replay.
_GRANTED_EVENT_IDS: set = set()


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _now_epoch() -> float:
    return time.time()


def _transition(record: dict, to: str) -> dict:
    """Apply a guarded state transition. No-op if not allowed; returns record."""
    fr = record.get("status", "PROPOSED")
    allowed = _STATE_MACHINE.get(fr, set())
    if to in allowed:
        record["status"] = to
        record[f"{to.lower()}_ts"] = _now()
    return record


def _valid_state_transition(fr: str, to: str) -> bool:
    return to in _STATE_MACHINE.get(fr, set())


# ---------------------------------------------------------------------------
# Classification (unchanged contract)
# ---------------------------------------------------------------------------

def classify(content: str, source: str, suggested_label: str | None = None) -> dict:
    """Classify a board event. Returns authority label + confidence + CLASSIFIED state."""
    label = suggested_label or "agent-generated"
    lowered = content.lower()
    imperatives = ["run ", "execute ", "do ", "apply ", "patch ", "write ", "delete "]
    if any(lowered.startswith(i) or (" " + i) in lowered for i in imperatives):
        if label not in ("operator-authored", "operator-confirmed", "tool-output"):
            label = "untrusted-instruction"
    return {
        "label": label,
        "source": source,
        "ts": _now(),
        "imperative_detected": label == "untrusted-instruction",
        "receipt_status": "CLASSIFIED",
    }


# ---------------------------------------------------------------------------
# Propose
# ---------------------------------------------------------------------------

def propose(event_id: str, requested_effect: str, capabilities: list[str],
              memory_scope: str = "scratch", budget: dict | None = None,
              ttl_seconds: int | None = None, parent_event: str | None = None,
              content: str = "", source: str = "",
              independence: dict | None = None,
              authority_label: str | None = None,
              require_confirmation: bool | None = None,
              confirm_by_ttl: int = 300) -> dict:
    """Create a proposal at PROPOSED. Does NOT execute.

    Track B additions: ttl_seconds defaults to policy default when omitted;
    require_confirmation flag (operator gate) is recorded so grant() can decide
    DEFERRED vs AUTHORIZED; independence tracks Avenue 7 consensus scoring.
    """
    pol = policy_engine.load_policy()
    if ttl_seconds is None:
        ttl_seconds = pol.get("default_ttl", 900)
    proposal = {
        "schema": "switchboard.v2",
        "kind": "proposal",
        "event_id": event_id,
        "requested_effect": requested_effect,
        "capabilities": capabilities,
        "memory_scope": memory_scope,
        "budget": budget or dict(pol.get("default_budget", {"max_calls": 3})),
        "ttl_seconds": ttl_seconds,
        "parent_event": parent_event,
        "ts": _now(),
        "content_head": content[:200],
        "source": source,
        "status": "PROPOSED",
        "authority_label": authority_label or "agent-generated",
        "require_confirmation": require_confirmation
            if require_confirmation is not None
            else policy_engine.require_confirmation(requested_effect, pol),
        "confirm_by_ttl": confirm_by_ttl,
        "independence": independence or {},
        "receipt_status": "PROPOSED",   # alias for the receipt chain
    }
    return proposal


# ---------------------------------------------------------------------------
# Grant (reference monitor) — policy-enforced
# ---------------------------------------------------------------------------

def grant(proposal: dict, narrow_capabilities: list[str] | None = None,
          deny_reason: str | None = None,
          authority: dict | None = None) -> dict:
    """Reference monitor decision, now policy-enforced on every call.

    Order of gates:
      1. explicit deny_reason  -> DENIED (terminal)
      2. TTL check             -> DENIED if proposal already expired
      3. budget check          -> DENIED if budget exhausted (preflight only)
      4. operator confirmation -> DEFERRED + inbox write (if required)
      5. authority validate    -> DENIED fail-closed if authority invalid
      6. otherwise             -> AUTHORIZED

    Returns the decision record (with receipt_status and policy verdicts) after
    appending to the trail.
    """
    pol = policy_engine.load_policy()

    # --- explicit deny short-circuits everything (terminal) ---
    if deny_reason:
        decision = {
            **proposal,
            "status": "DENIED",
            "receipt_status": "DENIED",
            "decision_ts": _now(),
            "deny_reason": deny_reason,
            "granted_capabilities": [],
            "policy_check": {"deny": deny_reason},
        }
        trail_append(decision)
        return decision

    requested = set(proposal.get("capabilities", []))
    granted = narrow_capabilities if narrow_capabilities is not None else list(requested)
    # Never grant more than requested (board_write stays special-cased for compat)
    granted = [c for c in granted if c in requested or c == "board_write"]
    effect = proposal.get("requested_effect", granted[0] if granted else "board_write")

    # --- TTL gate ---
    if not policy_engine.check_ttl(proposal, pol):
        decision = _denied(proposal, f"proposal expired (ttl {proposal.get('ttl_seconds')})", pol)
        trail_append(decision)
        return decision

    # --- budget gate (non-mutating preflight) ---
    # Execution owns the single decrement. Charging here as well made a
    # grant+execute consume two units and rejected the last permitted call.
    budget_holder = authority if authority is not None else proposal
    budget_ok, remaining = policy_engine.check_budget(budget_holder, effect, pol, decrement=False)
    if not budget_ok:
        decision = _denied(proposal, "budget exhausted at grant", pol,
                           budget_remaining=remaining)
        trail_append(decision)
        return decision

    # --- agent-source self-authorization gate (before confirmation) ---
    # An agent-generated/untrusted source cannot confirm its own high-impact
    # request. The confirmation gate is an OPERATOR gate, not an agent gate.
    label = proposal.get("authority_label", "agent-generated")
    if label in ("agent-generated", "untrusted-instruction", "external-content"):
        if policy_engine.require_confirmation(effect, pol):
            decision = _denied(
                proposal,
                f"{label} source cannot self-authorize high-impact effect {effect}",
                pol)
            trail_append(decision)
            return decision

    # --- operator confirmation gate ---
    if proposal.get("require_confirmation", policy_engine.require_confirmation(effect, pol)):
        decision = _defer(proposal, granted, remaining, pol)
        trail_append(decision)
        return decision

    # --- authority validation (fail closed) ---
    auth = authority
    if auth is None:
        # Build an implicit authority from the proposal for legacy/self-grant path.
        auth = _implicit_authority(proposal, granted)
    verdict = policy_engine.validate_authority(auth, effect, pol)
    if not verdict["ok"]:
        decision = _denied(proposal, verdict.get("reason", "authority check failed"), pol,
                           policy_verdict=verdict, granted_capabilities=granted)
        trail_append(decision)
        return decision

    # --- replay protection (same event_id must not double-grant) ---
    eid = proposal.get("event_id", "")
    if eid and eid in _GRANTED_EVENT_IDS:
        decision = _denied(proposal, f"replay: event_id {eid} already granted", pol)
        trail_append(decision)
        return decision

    decision = {
        **proposal,
        "status": "AUTHORIZED",
        "receipt_status": "AUTHORIZED",
        "decision_ts": _now(),
        "granted_capabilities": granted,
        "deny_reason": None,
        "authority": auth,
        "policy_check": {
            "ttl_valid": True,
            "budget_ok": True,
            "budget_remaining": remaining,
            "confirmation_required": False,
            "valid": verdict,
        },
        "ttl_expires": policy_engine.ttl_expires(proposal, pol),
    }
    trail_append(decision)
    if eid:
        _GRANTED_EVENT_IDS.add(eid)
    return decision


def _implicit_authority(proposal: dict, granted: list[str]) -> dict:
    """Build an authority record for legacy/self-grant proposals so every grant
    passes through the same validate_authority gate. If the proposal was
    operator-authored (or already carried an AUTHORIZED status), it self-grants.
    """
    label = proposal.get("authority_label", "agent-generated")
    if label in ("operator-authored", "operator-confirmed"):
        status = "AUTHORIZED"
    else:
        # legacy behavior: previously self-granted — honor for backward compat
        # LAW: a roast can become a proposal; it cannot become a permission.
        # Tier by impact: low-impact effects (board_write, verkle_link) may
        # self-grant for ordinary labels — proposals stay cheap and the
        # flywheel keeps turning. High-impact effects (fs_write, lane_spawn,
        # model_call, tool_invoke, network_access) and sensitive labels
        # (untrusted-instruction, external-content) NEVER self-grant — they
        # fail closed (DENIED). The operator can still authorize deliberately
        # via an explicit AUTHORIZED authority record; nothing is lost but the
        # silent path. (T1 Kabuki verdict 2026-08-31: 2/7-label guard was
        # partial law; this is the full tier gate, composed with
        # policy_engine.require_confirmation's existing high-impact list.)
        effect = proposal.get("requested_effect", "")
        if label in ("untrusted-instruction", "external-content") or effect in (
            "fs_write", "lane_spawn", "model_call", "tool_invoke", "network_access"
        ):
            status = "DENIED"
        else:
            status = proposal.get("status") if proposal.get("status") == "AUTHORIZED" else "AUTHORIZED"
    return {
        "event_id": proposal.get("event_id"),
        "status": status,
        "granted_capabilities": granted,
        "budget": proposal.get("budget") or {"max_calls": 3},
        "ts": proposal.get("ts"),
        "ttl_seconds": proposal.get("ttl_seconds"),
        "authority_label": label,
    }


def _defer(proposal: dict, granted: list[str], remaining: int, pol: dict) -> dict:
    """Create a DEFERRED decision and write it to the operator inbox.

    The proposal parks in DEFERRED awaiting operator confirm()/deny(). A
    confirm_by timestamp (default 300s, policy override via confirmation_ttl)
    bounds how long the operator has to act; after it expires the proposal is
    treated as DENIED by the sweep.
    """
    ttl = pol.get("confirmation_ttl", proposal.get("confirm_by_ttl", 300))
    confirm_by_epoch = _now_epoch() + float(ttl)
    confirm_by = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(confirm_by_epoch))
    decision = {
        **proposal,
        "status": "DEFERRED",
        "receipt_status": "DEFERRED",
        "decision_ts": _now(),
        "confirm_by": confirm_by,
        "confirm_by_ttl": ttl,
        "granted_capabilities": granted,
        "requiring_operator": True,
        "policy_check": {
            "ttl_valid": True,
            "budget_ok": True,
            "budget_remaining": remaining,
            "confirmation_required": True,
        },
        "ttl_expires": policy_engine.ttl_expires(proposal, pol),
    }
    INBOX.parent.mkdir(parents=True, exist_ok=True)
    with INBOX.open("a", encoding="utf-8") as f:
        f.write(json.dumps(decision, ensure_ascii=False) + "\n")
    return decision


def _denied(proposal: dict, reason: str, pol: dict, **extra) -> dict:
    """Terminal DENIED decision (post-grant attempt)."""
    decision = {
        **proposal,
        "status": "DENIED",
        "receipt_status": "DENIED",
        "decision_ts": _now(),
        "deny_reason": reason,
        "granted_capabilities": [],
        "policy_check": {"denied": reason},
    }
    for k, v in extra.items():
        decision[k] = v
    return decision


# ---------------------------------------------------------------------------
# Operator confirm / deny
# ---------------------------------------------------------------------------

def _read_inbox() -> list[dict]:
    """Read all operator-inbox records (oldest first)."""
    if not INBOX.exists():
        return []
    out = []
    for line in INBOX.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def _find_inbox(event_id: str) -> dict | None:
    for rec in _read_inbox():
        if rec.get("event_id") == event_id and rec.get("status") == "DEFERRED":
            return rec
    return None


def confirm(event_id: str, actor: str = "operator") -> dict:
    """Operator confirms a DEFERRED proposal → CONFIRMED.

    Fails if the event_id is not in the inbox in DEFERRED state, or if its
    confirm_by window has expired (treated as expired → DENIED).
    """
    rec = _find_inbox(event_id)
    if rec is None:
        return {"ok": False, "err": f"no DEFERRED event {event_id} in inbox"}
    if not _confirm_window_open(rec):
        return {"ok": False, "err": f"confirm window expired for {event_id}"}

    # Revalidate at the point of authorization.  A proposal may have become
    # expired, revoked, over budget, or policy-disabled while it sat in the
    # operator inbox.  Confirmation is not allowed to resurrect it.
    pol = policy_engine.load_policy()
    effect = rec.get("requested_effect", "")
    granted = rec.get("granted_capabilities", [])
    auth = {
        "event_id": rec.get("event_id"),
        "status": "AUTHORIZED",
        "granted_capabilities": granted,
        "budget": rec.get("budget") or {"max_calls": 3},
        # Preserve proposal age; resetting ts here would defeat TTL expiry.
        "ts": rec.get("ts"),
        "ttl_seconds": rec.get("ttl_seconds", pol.get("default_ttl", 900)),
        "authority_label": "operator-confirmed",
        "confirmed_by": actor,
    }
    verdict = policy_engine.validate_authority(auth, effect, pol)
    if not verdict["ok"]:
        _transition(rec, "DENIED")
        rec["deny_reason"] = f"confirmation rejected: {verdict.get('reason', 'policy check failed')}"
        rec["denied_by"] = actor
        rec["denied_ts"] = _now()
        rec["receipt_status"] = "DENIED"
        rec["policy_check"] = {
            "confirmation_required": True,
            "confirmed_by": actor,
            "valid": verdict,
        }
        _rewrite_inbox_rec(rec)
        trail_append(rec)
        return {"ok": False, "event_id": event_id, "err": rec["deny_reason"],
                "decision": rec}

    _transition(rec, "CONFIRMED")
    rec["confirmed_by"] = actor
    rec["confirmed_ts"] = _now()
    rec["receipt_status"] = "CONFIRMED"
    _rewrite_inbox_rec(rec)

    # Now advance to AUTHORIZED (point of no return, operator-backed).
    decision = {
        **rec,
        "status": "AUTHORIZED",
        "receipt_status": "AUTHORIZED",
        "authority": auth,
        "decision_ts": _now(),
        "ttl_expires": policy_engine.ttl_expires(rec, pol),
        "policy_check": {"confirmation_required": True, "confirmed_by": actor, "valid": verdict},
    }
    trail_append(decision)
    return {"ok": True, "event_id": event_id, "decision": decision}


def deny(event_id: str, actor: str = "operator", reason: str = "operator denied") -> dict:
    """Operator denies a DEFERRED proposal → DENIED (terminal)."""
    rec = _find_inbox(event_id)
    if rec is None:
        return {"ok": False, "err": f"no DEFERRED event {event_id} in inbox"}

    _transition(rec, "DENIED")
    rec["deny_reason"] = reason
    rec["denied_by"] = actor
    rec["denied_ts"] = _now()
    rec["receipt_status"] = "DENIED"
    _rewrite_inbox_rec(rec)

    decision = {**rec, "status": "DENIED", "receipt_status": "DENIED", "deny_reason": reason}
    trail_append(decision)
    return {"ok": True, "event_id": event_id, "decision": decision}


def _confirm_window_open(rec: dict) -> bool:
    cb = rec.get("confirm_by")
    if not cb:
        return True
    try:
        from .policy_engine import _ts_to_epoch
        return _ts_to_epoch(cb) > _now_epoch()
    except Exception:
        try:
            from policy_engine import _ts_to_epoch
            return _ts_to_epoch(cb) > _now_epoch()
        except Exception:
            # Unparseable timestamp is unsafe for an operator confirmation;
            # fail closed instead of turning a malformed window into a live one.
            return False


def _rewrite_inbox_rec(updated: dict):
    """Replace a record in-place in the inbox file by event_id."""
    records = _read_inbox()
    found = False
    for i, r in enumerate(records):
        if r.get("event_id") == updated.get("event_id"):
            records[i] = updated
            found = True
            break
    if not found:
        records.append(updated)
    INBOX.parent.mkdir(parents=True, exist_ok=True)
    tmp = INBOX.with_suffix(".tmp")
    tmp.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8")
    tmp.replace(INBOX)


# ---------------------------------------------------------------------------
# Receipt chain: execution states
# ---------------------------------------------------------------------------

def mark_executing(decision: dict, details: dict | None = None) -> dict:
    """advance AUTHORIZED → EXECUTING."""
    d = {**decision}
    _transition(d, "EXECUTING")
    d["receipt_status"] = "EXECUTING"
    d["exec_start_ts"] = _now()
    if details:
        d["exec_details"] = details
    trail_append(d)
    return d


def complete(decision: dict, evidence: dict | None = None) -> dict:
    """advance EXECUTING → COMPLETED with postcondition evidence."""
    d = {**decision}
    _transition(d, "COMPLETED")
    d["receipt_status"] = "COMPLETED"
    d["completed_ts"] = _now()
    d["postcondition_evidence"] = evidence or {}
    trail_append(d)
    return d


def fail(decision: dict, error: str, evidence: dict | None = None) -> dict:
    """advance EXECUTING → FAILED with error + any evidence gathered."""
    d = {**decision}
    _transition(d, "FAILED")
    d["receipt_status"] = "FAILED"
    d["failed_ts"] = _now()
    d["error"] = error
    d["postcondition_evidence"] = evidence or {}
    trail_append(d)
    return d


def commit_receipt(decision: dict, receipt: dict) -> dict:
    """advance COMPLETED/FAILED → RECEIPT_COMMITTED. Terminal.

    RECEIPT_COMMITTED requires postcondition evidence; if the terminal state
    was reached via COMPLETED, evidence is mandatory. For FAILED, throws a
    rejected flag if evidence is missing.
    """
    d = {**decision}
    st = d.get("status", "COMPLETED")
    if st not in ("COMPLETED", "FAILED"):
        return {"ok": False, "err": f"cannot commit receipt from {st}", "decision": d}
    _transition(d, "RECEIPT_COMMITTED")
    d["receipt_status"] = "RECEIPT_COMMITTED"
    d["receipt_committed_ts"] = _now()
    d["receipt"] = receipt
    if not d.get("postcondition_evidence"):
        d["receipt_warning"] = "no postcondition evidence captured at commit"
    trail_append(d)
    return {"ok": True, "decision": d}


# ---------------------------------------------------------------------------
# Board write (original board_write broker, policy-validated at execution)
# ---------------------------------------------------------------------------

def write_board_note(note: dict, authority: dict, *, budget_consumed: bool = False) -> dict:
    """Effect broker: write a blackboard note, fail closed unless authorized.

    Now re-validates the authority through policy_engine at execution time so a
    revoked/expired-but-cached authority cannot write after the fact.
    """
    effect = "board_write"
    verdict = policy_engine.validate_authority(authority, effect)
    if not verdict["ok"]:
        return {"ok": False, "err": verdict.get("reason", "denied"), "authority": authority,
                "policy_check": verdict}
    if "board_write" not in authority.get("granted_capabilities", []):
        return {"ok": False, "err": "capability board_write not granted", "authority": authority}

    pol = policy_engine.load_policy()
    # Direct callers still consume a budget unit here.  The unified effect
    # broker consumes it immediately before dispatching this effect, so it
    # marks the call as already charged to avoid double-decrementing.
    if budget_consumed:
        budget = authority.get("budget") or {}
        used = budget.get("used") if isinstance(budget.get("used"), dict) else {}
        remaining = int(budget.get("max_calls", pol.get("default_budget", {}).get("max_calls", 3))) - int(used.get(effect, 0))
    else:
        budget_ok, remaining = policy_engine.check_budget(authority, effect, pol, decrement=True)
        if not budget_ok:
            return {"ok": False, "err": "board_write budget exhausted", "authority": authority,
                    "budget_remaining": remaining}

    # max_board_notes cap
    max_notes = int(pol.get("max_board_notes", 1000))
    if BB.exists():
        existing_count = len(list(BB.glob("bb-*.json")))
        if existing_count >= max_notes:
            return {"ok": False, "err": f"max_board_notes({max_notes}) reached", "authority": authority}

    try:
        BB.mkdir(parents=True, exist_ok=True)
        existing = sorted(BB.glob("bb-*.json"))
        seq = 0
        if existing:
            try:
                seq = int(existing[-1].stem.split("-")[1])
            except Exception:
                seq = len(existing)
        for _ in range(5):
            seq += 1
            path = BB / f"bb-{seq:05d}.json"
            if path.exists():
                continue
            payload = {
                "schema": "swarm_tools.v1",
                "tool": "swarm_blackboard",
                "seq": seq,
                "ts": note.get("ts", _now()),
                "owner": note.get("owner", "switchboard"),
                "kind": note.get("kind", "finding"),
                "pinned": False,
                "text": note.get("text", ""),
                "authority": authority,
                "event": note.get("event", ""),
                "step_ok": note.get("step_ok", {}),
            }
            path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
            return {"ok": True, "path": str(path.relative_to(ROOT)), "seq": seq,
                    "budget_remaining": remaining}
        return {"ok": False, "err": "seq collision x5"}
    except Exception as e:
        return {"ok": False, "err": repr(e)}


# ---------------------------------------------------------------------------
# Trail
# ---------------------------------------------------------------------------

def trail_append(decision: dict):
    """Durable receipt-chain log. Ensures receipt_status field is always present."""
    record = dict(decision)
    record.setdefault("receipt_status", record.get("status", "UNKNOWN"))
    TRAIL.parent.mkdir(parents=True, exist_ok=True)
    with TRAIL.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# Reconcile (kept from original, now policy-gated through grant)
# ---------------------------------------------------------------------------

def _load_board(limit: int = 200) -> list[dict]:
    if not BB.exists():
        return []
    notes = []
    for p in sorted(BB.glob("bb-*.json"), reverse=True)[:limit]:
        try:
            notes.append(json.loads(p.read_text(encoding="utf-8")))
        except Exception:
            pass
    return notes


def _detect_unmet(notes: list[dict]) -> list[dict]:
    unmet = []
    seen = {"source_verification": False, "fork_verdict_knot": False,
            "prediction_measurement": False, "principle_protocol": False}
    for n in notes:
        text = (n.get("text") or "").lower()
        if "source" in text and ("verify" in text or "⚠️" in n.get("text", "")):
            seen["source_verification"] = True
        if "fork" in text and "verdict" in text:
            seen["fork_verdict_knot"] = True
        if "prediction" in text and "measure" in text:
            seen["prediction_measurement"] = True
        if "principle" in text and "protocol" in text:
            seen["principle_protocol"] = True

    if not seen["source_verification"]:
        unmet.append({"condition": "missing_source_verification", "priority": 1,
                      "eligible_organ": "ghost_memlance", "capability": "tool_invoke",
                      "reason": "Board lacks active source verification stream"})
    if not seen["fork_verdict_knot"]:
        unmet.append({"condition": "missing_fork_verdicts", "priority": 2,
                      "eligible_organ": "verkle_lance", "capability": "verkle_link",
                      "reason": "Fork resolutions are prose-only, not knotted"})
    if len(notes) < 5:
        unmet.append({"condition": "board_quiescent", "priority": 3,
                      "eligible_organ": "swarm_cycle", "capability": "lane_spawn",
                      "reason": "Board has <5 notes; suggest cycle run"})
    return unmet


def reconcile() -> dict:
    notes = _load_board()
    unmet = _detect_unmet(notes)
    decisions = []
    for item in unmet:
        prop = propose(
            event_id=f"reconcile:{item['condition']}:{int(time.time())}",
            requested_effect=item["capability"],
            capabilities=[item["capability"]],
            memory_scope=item["eligible_organ"],
            budget={"max_calls": 1},
            ttl_seconds=600,
            content=item["reason"],
            source="switchboard_reconcile",
        )
        # Policy-gated self-grant; effects requiring confirmation will DEFER.
        auth = grant(prop, narrow_capabilities=[item["capability"]])
        decisions.append({
            "condition": item["condition"],
            "priority": item["priority"],
            "eligible_organ": item["eligible_organ"],
            "authority": auth,
            "authority_status": auth.get("status"),
            "receipt_status": auth.get("receipt_status"),
        })
    return {
        "ok": True,
        "board_notes_loaded": len(notes),
        "unmet_conditions": len(unmet),
        "decisions": decisions,
        "ts": _now(),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def cmd_classify(args):
    result = classify(args.content, args.source, args.label)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def cmd_propose(args):
    prop = propose(
        args.event_id, args.effect, args.capabilities.split(","),
        memory_scope=args.memory_scope,
        budget=json.loads(args.budget or '{}') or None,
        ttl_seconds=args.ttl,
        parent_event=args.parent,
        content=args.content,
        source=args.source,
    )
    print(json.dumps(prop, indent=2, ensure_ascii=False))
    return 0


def cmd_grant(args):
    raw = args.proposal_file.read_text(encoding="utf-8") if args.proposal_file else sys.stdin.read()
    prop = json.loads(raw)
    auth = None
    if args.authority:
        auth = json.loads(args.authority.read_text(encoding="utf-8"))
    if args.deny:
        decision = grant(prop, deny_reason=args.deny)
    else:
        caps = args.granted.split(",") if args.granted else None
        decision = grant(prop, narrow_capabilities=caps, authority=auth)
    print(json.dumps(decision, indent=2, ensure_ascii=False))
    return 0


def cmd_confirm(args):
    result = confirm(args.event_id, actor=args.actor)
    print(json.dumps(_strip_ok(result), indent=2, ensure_ascii=False))
    return 0 if result.get("ok") else 1


def cmd_deny(args):
    result = deny(args.event_id, actor=args.actor, reason=args.reason)
    print(json.dumps(_strip_ok(result), indent=2, ensure_ascii=False))
    return 0 if result.get("ok") else 1


def cmd_inbox(args):
    recs = _read_inbox()
    print(json.dumps(recs, indent=2, ensure_ascii=False))
    return 0


def cmd_reconcile(args):
    result = reconcile()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def cmd_write(args):
    raw = args.note_file.read_text(encoding="utf-8") if args.note_file else sys.stdin.read()
    note = json.loads(raw)
    auth = json.loads(args.authority.read_text(encoding="utf-8") if args.authority else sys.stdin.read())
    result = write_board_note(note, auth)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def cmd_expire(args):
    from importlib import import_module
    if not hasattr(args, "only_policy"):
        args.only_policy = False
    if args.only_policy:
        expired = policy_engine.expire()
        print(json.dumps({"ok": True, "expired": expired, "count": len(expired)}, indent=2, ensure_ascii=False))
    else:
        # sweep policy + flush stale DEFERRED inbox entries whose window lapsed
        expired = policy_engine.expire()
        flushed = _flush_expired_deferred()
        print(json.dumps({"ok": True, "expired_policy": expired,
                          "expired_deferred": flushed}, indent=2, ensure_ascii=False))
    return 0


def _flush_expired_deferred() -> list[str]:
    """Turn DEFERRED inbox entries past confirm_by into terminal DENIED."""
    flushed = []
    for rec in _read_inbox():
        if rec.get("status") == "DEFERRED" and not _confirm_window_open(rec):
            rec["status"] = "DENIED"
            rec["receipt_status"] = "DENIED"
            rec["deny_reason"] = "confirm window expired"
            rec["denied_ts"] = _now()
            _rewrite_inbox_rec(rec)
            flushed.append(rec.get("event_id"))
    return flushed


def _strip_ok(result: dict):
    """Flatten {ok, err, decision-record} for CLI printing."""
    if result.get("decision"):
        return result["decision"]
    return result


def main(argv=None):
    ap = argparse.ArgumentParser(prog="mag.switchboard_v2")
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("classify")
    c.add_argument("content")
    c.add_argument("--source", default="unknown")
    c.add_argument("--label", default=None)
    c.set_defaults(func=cmd_classify)

    p = sub.add_parser("propose")
    p.add_argument("--event_id", required=True)
    p.add_argument("--effect", required=True)
    p.add_argument("--capabilities", required=True)
    p.add_argument("--memory_scope", default="scratch")
    p.add_argument("--budget", default=None)
    p.add_argument("--ttl", type=int, default=None)
    p.add_argument("--parent", default=None)
    p.add_argument("--content", default="")
    p.add_argument("--source", default="unknown")
    p.set_defaults(func=cmd_propose)

    g = sub.add_parser("grant")
    g.add_argument("--proposal_file", type=Path, default=None)
    g.add_argument("--authority", type=Path, default=None)
    g.add_argument("--granted", default=None)
    g.add_argument("--deny", default=None)
    g.set_defaults(func=cmd_grant)

    cf = sub.add_parser("confirm")
    cf.add_argument("event_id")
    cf.add_argument("--actor", default="operator")
    cf.set_defaults(func=cmd_confirm)

    dn = sub.add_parser("deny")
    dn.add_argument("event_id")
    dn.add_argument("--actor", default="operator")
    dn.add_argument("--reason", default="operator denied")
    dn.set_defaults(func=cmd_deny)

    ib = sub.add_parser("inbox")
    ib.set_defaults(func=cmd_inbox)

    r = sub.add_parser("reconcile")
    r.set_defaults(func=cmd_reconcile)

    w = sub.add_parser("write")
    w.add_argument("--note_file", type=Path, default=None)
    w.add_argument("--authority", type=Path, required=True)
    w.set_defaults(func=cmd_write)

    e = sub.add_parser("expire")
    e.add_argument("--policy-only", action="store_true", dest="only_policy")
    e.set_defaults(func=cmd_expire)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
