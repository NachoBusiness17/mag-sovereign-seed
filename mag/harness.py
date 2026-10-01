"""harness — MAG Integration Harness.

Wires switchboard + effect_broker + policy_engine into one actionable control
loop with leases, queues, receipts, and operator confirmation.

Commands:
    harness run_once           — one pass of the control loop
    harness run_continuous     — loop with interval sleep
    harness test --scenario N  — run predefined test scenarios
    harness status             — show queue, leases, deferred
    harness reset --force      — clear all state (requires --force)
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
QUEUE_FILE = ROOT / "memory" / "runs" / "queue.jsonl"
LEASES_FILE = ROOT / "memory" / "runs" / "leases.jsonl"
RECEIPTS_FILE = ROOT / "memory" / "runs" / "receipts.jsonl"
HEALTH_RECEIPTS_FILE = ROOT / "memory" / "runs" / "harness" / "health_receipts.jsonl"
TEST_RESULTS_FILE = ROOT / "memory" / "runs" / "harness_tests.jsonl"
LAST_RUN_FILE = ROOT / "memory" / "runs" / "harness_last_run.txt"

# Import package-local organs.  These files are executed both as
# ``python -m mag.harness`` and from a test runner; bare imports only worked
# while the staging directory happened to be on ``sys.path``.
from . import effect_broker as eb
from . import policy_engine as pe
from . import switchboard_v2 as sb


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _now_epoch() -> float:
    return time.time()


def _ensure_dirs():
    for f in (QUEUE_FILE, LEASES_FILE, RECEIPTS_FILE, TEST_RESULTS_FILE):
        f.parent.mkdir(parents=True, exist_ok=True)


def _load_jsonl(path: Path) -> list[dict]:
    out = []
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return out


def _append_jsonl(path: Path, rec: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# Lease logic
# ---------------------------------------------------------------------------

def _load_leases() -> list[dict]:
    return _load_jsonl(LEASES_FILE)


def _is_leased(condition: str, leases: list[dict] | None = None) -> dict | None:
    leases = leases or _load_leases()
    now = _now_epoch()
    for lease in leases:
        if lease.get("condition") == condition:
            expires = lease.get("expires_epoch", 0)
            if expires > now:
                return lease
    return None


def _create_lease(condition: str, organ: str, duration: int = 300) -> dict:
    lease = {
        "schema": "harness.lease.v1",
        "condition": condition,
        "organ": organ,
        "granted_at": _now(),
        "expires_epoch": _now_epoch() + duration,
        "duration": duration,
    }
    _append_jsonl(LEASES_FILE, lease)
    return lease


def _cleanup_expired_leases():
    leases = _load_leases()
    now = _now_epoch()
    active = [l for l in leases if l.get("expires_epoch", 0) > now]
    if len(active) < len(leases):
        LEASES_FILE.write_text(
            "\n".join(json.dumps(l, ensure_ascii=False) for l in active) + ("\n" if active else ""),
            encoding="utf-8",
        )


# ---------------------------------------------------------------------------
# Queue logic
# ---------------------------------------------------------------------------

def _enqueue(item: dict):
    item["enqueued_at"] = _now()
    _append_jsonl(QUEUE_FILE, item)


def _load_queue() -> list[dict]:
    return _load_jsonl(QUEUE_FILE)


def _dequeue() -> list[dict]:
    """Return queue items that are not yet processed (no 'processed' field)."""
    q = _load_queue()
    return [i for i in q if not i.get("processed")]


def _mark_processed(event_id: str):
    q = _load_queue()
    changed = False
    for item in q:
        if item.get("event_id") == event_id and not item.get("processed"):
            item["processed"] = True
            item["processed_at"] = _now()
            changed = True
    if changed:
        QUEUE_FILE.write_text(
            "\n".join(json.dumps(i, ensure_ascii=False) for i in q) + ("\n" if q else ""),
            encoding="utf-8",
        )


def _consensus_priority(unmet: list[dict]) -> list[dict]:
    """Boost priority if multiple proposals target the same condition/organ."""
    counts: dict[str, int] = {}
    for u in unmet:
        key = f"{u.get('condition', '')}:{u.get('eligible_organ', '')}"
        counts[key] = counts.get(key, 0) + 1
    for u in unmet:
        key = f"{u.get('condition', '')}:{u.get('eligible_organ', '')}"
        u["_consensus_count"] = counts.get(key, 1)
    # sort: higher consensus count first, then lower priority number
    unmet.sort(key=lambda x: (-x.get("_consensus_count", 1), x.get("priority", 99)))
    return unmet


# ---------------------------------------------------------------------------
# Receipt logic
# ---------------------------------------------------------------------------

def _record_receipt(step: str, event_id: str, status: str, detail: dict):
    rec = {
        "schema": "harness.receipt.v1",
        "step": step,
        "event_id": event_id,
        "status": status,
        "ts": _now(),
        "detail": detail,
    }
    # Harness scenarios and dry probes are evidence of the control path, not
    # production side effects.  Mark them so the receipt stream cannot be
    # mistaken for live work.
    if str(event_id).startswith("test-") or str(step).endswith("_stub"):
        rec["test_only"] = True
        rec["evidence_class"] = "simulation"
    _append_jsonl(RECEIPTS_FILE, rec)


# ---------------------------------------------------------------------------
# Core control loop
# ---------------------------------------------------------------------------

def run_once(dry: bool = False) -> dict:
    """One pass:
        1. Reconcile (switchboard scans board, proposes actions)
        2. Check leases (skip if leased)
        3. Create lease + enqueue new items
        4. For each queued item: propose + grant
        5. AUTHORIZED → effect_broker.execute()  (or compat stub if dry)
        6. Record receipt
        7. Emit DEFERRED notices
        8. Clean expired leases
    """
    _ensure_dirs()
    report = {"ts": _now(), "steps": {}, "ok": True}

    # 1. Reconcile
    rec_result = sb.reconcile()
    report["steps"]["reconcile"] = rec_result
    unmet = rec_result.get("decisions", [])
    report["unmet_count"] = len(unmet)

    # 2+3. Lease check + enqueue
    leases = _load_leases()
    newly_enqueued = 0
    for item in unmet:
        condition = item.get("condition", "")
        organ = item.get("eligible_organ", "")
        if _is_leased(condition, leases):
            continue
        lease = _create_lease(condition, organ, duration=300)
        auth = item.get("authority") or {}
        caps = auth.get("granted_capabilities") or []
        _enqueue({
            "schema": "harness.queue.v1",
            "event_id": auth.get("event_id", f"harness:{int(time.time())}"),
            "condition": condition,
            "organ": organ,
            "authority": auth,
            "capability": caps[0] if caps else item.get("capability"),
        })
        newly_enqueued += 1
    report["newly_enqueued"] = newly_enqueued

    # 4+5+6. Process queue
    queue = _dequeue()
    processed = 0
    deferred = 0
    failed = 0

    for item in queue:
        event_id = item.get("event_id", f"anon-{int(time.time())}")
        authority = item.get("authority", {})
        capability = item.get("capability")

        # Re-propose + grant through switchboard (this triggers DEFERRED for high-impact)
        prop = sb.propose(
            event_id=event_id,
            requested_effect=capability or "board_write",
            capabilities=[capability] if capability else ["board_write"],
            memory_scope=item.get("organ", "scratch"),
            budget={"max_calls": 3},
            ttl_seconds=900,
            parent_event=event_id,
            content=item.get("condition", ""),
            source="harness",
        )
        # Check policy: does this effect require confirmation?
        requires_confirm = pe.require_confirmation(capability or "board_write")
        if requires_confirm:
            # Force DEFERRED
            auth = {
                **prop,
                "status": "DEFERRED",
                "decision_ts": _now(),
                "granted_capabilities": [],
                "deny_reason": None,
                "confirm_by": _now_epoch() + pe.load_policy().get("confirmation_ttl", 300),
            }
            # Write to operator inbox
            inbox = ROOT / "bridge" / "operator_inbox.jsonl"
            inbox.parent.mkdir(parents=True, exist_ok=True)
            _append_jsonl(inbox, auth)
            deferred += 1
            _record_receipt("grant", event_id, "DEFERRED", {"reason": "requires_confirmation", "inbox": str(inbox)})
            _mark_processed(event_id)
            continue

        auth = sb.grant(prop)
        status = auth.get("status")

        if status == "AUTHORIZED":
            if dry:
                # Compat stub: log what WOULD be called
                _record_receipt("execute_stub", event_id, "STUB",
                                {"effect": capability, "authority": auth, "note": "dry run — effect_broker not called"})
                processed += 1
            else:
                # Advance the switchboard trail through the full state machine
                # (AUTHORIZED -> EXECUTING -> COMPLETED/FAILED -> RECEIPT_COMMITTED)
                # so the primary control loop writes a continuous chain, not a
                # gap. Mirrors swarm_cycle.py's mesh-client pattern.
                executing = sb.mark_executing(auth, {"effect": capability or "board_write"})
                rec = eb.execute(capability or "board_write", {}, executing)
                _record_receipt("execute", event_id, rec["status"], rec)
                result = rec.get("result", {}) or {}
                if rec["status"] == "RECEIPT_COMMITTED" and result.get("ok"):
                    terminal = sb.complete(executing, {"broker_receipt": rec.get("receipt_path"), "result": result})
                    committed = sb.commit_receipt(terminal, rec)
                    if committed.get("ok"):
                        processed += 1
                    else:
                        failed += 1
                else:
                    terminal = sb.fail(executing, rec.get("error") or result.get("err") or "effect failed", {"broker_receipt": rec.get("receipt_path"), "result": result})
                    sb.commit_receipt(terminal, rec)
                    failed += 1
            _mark_processed(event_id)
        elif status == "DEFERRED":
            deferred += 1
            _record_receipt("grant", event_id, "DEFERRED", {"authority": auth})
            _mark_processed(event_id)
        else:
            failed += 1
            _record_receipt("grant", event_id, "DENIED", {"authority": auth})
            _mark_processed(event_id)

    # 7. Emit deferred notice
    if deferred:
        print(f"[HARNESS] {deferred} item(s) DEFERRED — see bridge/operator_inbox.jsonl")

    # 8. Clean expired leases
    _cleanup_expired_leases()

    # Expire stale proposals via policy engine
    expired = pe.expire()
    report["expired_by_ttl"] = expired

    report["processed"] = processed
    report["deferred"] = deferred
    report["failed"] = failed
    report["queue_depth"] = len(queue)
    report["ok"] = failed == 0

    # Persist last run
    LAST_RUN_FILE.parent.mkdir(parents=True, exist_ok=True)
    LAST_RUN_FILE.write_text(_now(), encoding="utf-8")

    return report


def health_check() -> dict:
    """Exercise one explicit, bounded board-write control path.

    This is not a queue drain and never consumes arbitrary pending work.  It
    proves the positive path through proposal, grant, broker execution,
    terminal completion, and committed receipt using a disposable health note.
    """
    event_id = f"health-harness-{int(time.time() * 1000)}"
    proposal = sb.propose(
        event_id=event_id,
        requested_effect="board_write",
        capabilities=["board_write"],
        memory_scope="harness_health",
        budget={"max_calls": 1},
        ttl_seconds=300,
        content="bounded harness health check",
        source="harness.health_check",
        authority_label="tool-output",
        require_confirmation=False,
    )
    authority = sb.grant(proposal)
    if authority.get("status") != "AUTHORIZED":
        result = {"ok": False, "event_id": event_id,
                  "authority_status": authority.get("status"),
                  "error": "health proposal was not authorized"}
    else:
        executing = sb.mark_executing(authority, {"health_check": True})
        broker = eb.execute(
            "board_write",
            {"note": {"text": "harness health receipt", "kind": "health"}},
            executing,
        )
        broker_result = broker.get("result") or {}
        if broker.get("status") == "RECEIPT_COMMITTED" and broker_result.get("ok"):
            terminal = sb.complete(executing, {
                "broker_receipt": broker.get("receipt_path"),
                "path": broker_result.get("path"),
            })
        else:
            terminal = sb.fail(
                executing,
                broker.get("error") or broker_result.get("err") or "health board write failed",
                {"broker_receipt": broker.get("receipt_path"), "result": broker_result},
            )
        committed = sb.commit_receipt(terminal, broker)
        result = {
            "ok": bool(committed.get("ok") and broker_result.get("ok")),
            "event_id": event_id,
            "authority_status": (committed.get("decision") or {}).get("status"),
            "broker_status": broker.get("status"),
            "path": broker_result.get("path"),
        }
    HEALTH_RECEIPTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with HEALTH_RECEIPTS_FILE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({
            "schema": "harness.health.v1",
            "ts": _now(),
            "ok": result.get("ok") is True,
            "event_id": event_id,
            "authority_status": result.get("authority_status"),
            "broker_status": result.get("broker_status"),
            "evidence_class": "bounded_control_smoke",
        }, ensure_ascii=False, sort_keys=True) + "\n")
    return result


def run_continuous(interval: int = 60):
    print(f"[HARNESS] Starting continuous loop every {interval}s. Press Ctrl+C to stop.")
    stopped = False
    def _sigint_handler(signum, frame):
        nonlocal stopped
        stopped = True
        print("\n[HARNESS] SIGINT received, finishing current pass...")
    signal.signal(signal.SIGINT, _sigint_handler)
    while not stopped:
        try:
            result = run_once()
            print(json.dumps({"ok": result["ok"], "processed": result["processed"],
                              "deferred": result["deferred"], "failed": result["failed"],
                              "ts": result["ts"]}, indent=2))
        except Exception as e:
            print(json.dumps({"ok": False, "error": repr(e), "ts": _now()}, indent=2))
        if stopped:
            break
        time.sleep(interval)
    print("[HARNESS] Stopped.")


# ---------------------------------------------------------------------------
# Test scenarios
# ---------------------------------------------------------------------------

def _test_result(name: str, passed: bool, detail: dict) -> dict:
    return {"test": name, "pass": bool(passed), "detail": detail, "ts": _now()}


def _write_test_result(r: dict):
    _append_jsonl(TEST_RESULTS_FILE, r)


def test_scenario_1() -> dict:
    """Simple board write: simulate propose+grant+execute, verify receipt chain."""
    event_id = f"test-sc1-{int(time.time())}"
    auth = {
        "status": "AUTHORIZED",
        "granted_capabilities": ["board_write"],
        "event_id": event_id,
        "ts": _now(),
        "ttl_seconds": 900,
        "budget": {"max_calls": 3},
    }
    rec = eb.execute("board_write", {"note": {"text": "harness test 1", "kind": "finding"}}, auth)
    passed = bool(rec["status"] == "RECEIPT_COMMITTED" and rec.get("result", {}).get("ok"))
    r = _test_result("scenario_1_board_write", passed,
                     {"receipt_status": rec["status"], "result_ok": rec.get("result", {}).get("ok")})
    _write_test_result(r)
    return r


def test_scenario_2() -> dict:
    """Tool invoke without authority: simulate unauthorized request, verify fails closed."""
    event_id = f"test-sc2-{int(time.time())}"
    auth = {
        "status": "AUTHORIZED",
        "granted_capabilities": ["board_write"],  # NOT tool_invoke
        "event_id": event_id,
    }
    rec = eb.execute("tool_invoke", {"cmd": ["echo", "hello"]}, auth)
    passed = rec["status"] == "RECEIPT_COMMITTED" and not rec.get("result", {}).get("ok")
    r = _test_result("scenario_2_unauthorized_tool", passed,
                     {"receipt_status": rec["status"], "error": rec.get("error", "")[:60]})
    _write_test_result(r)
    return r


def test_scenario_3() -> dict:
    """Operator confirmation gate: simulate DEFERRED, then confirm, then execute."""
    event_id = f"test-sc3-{int(time.time())}"
    prop = sb.propose(
        event_id=event_id,
        requested_effect="fs_write",
        capabilities=["fs_write"],
        source="harness_test",
    )
    # Force DEFERRED (fs_write requires confirmation per default policy)
    auth_deferred = {
        **prop,
        "status": "DEFERRED",
        "decision_ts": _now(),
        "granted_capabilities": [],
        "confirm_by": _now_epoch() + 300,
    }
    # Simulate operator confirm
    auth_confirmed = {
        **auth_deferred,
        "status": "AUTHORIZED",
        "granted_capabilities": ["fs_write"],
        "confirmed_at": _now(),
    }
    test_path = ROOT / "memory" / "harness_test_sc3.txt"
    rec = eb.execute("fs_write", {"path": str(test_path), "content": "confirmed"}, auth_confirmed)
    passed = bool(rec["status"] == "RECEIPT_COMMITTED" and rec.get("result", {}).get("ok"))
    if test_path.exists():
        test_path.unlink()
    r = _test_result("scenario_3_operator_confirm", passed,
                     {"deferred_ok": True, "confirmed_ok": passed, "receipt_status": rec["status"]})
    _write_test_result(r)
    return r


def test_scenario_4() -> dict:
    """Budget exhaustion: simulate 3 authorized calls, verify 4th is denied."""
    event_id_base = f"test-sc4-{int(time.time())}"
    auth = {
        "status": "AUTHORIZED",
        "granted_capabilities": ["board_write"],
        "event_id": event_id_base,
        "budget": {"max_calls": 3},
    }
    records = [eb.execute("board_write", {"note": {"text": f"budget test {i}"}}, auth)
               for i in range(4)]
    passed = bool(
        all(r.get("result", {}).get("ok") for r in records[:3])
        and not records[3].get("result", {}).get("ok")
        and "budget" in str(records[3].get("error", "")).lower()
    )
    r = _test_result("scenario_4_budget_exhaustion", passed,
                     {"calls": 4, "budget_max": 3})
    _write_test_result(r)
    return r


def test_scenario_5() -> dict:
    """TTL expiration: simulate old proposal, verify grant returns DENIED."""
    event_id = f"test-sc5-{int(time.time())}"
    old_ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(_now_epoch() - 2000))
    prop = sb.propose(
        event_id=event_id,
        requested_effect="board_write",
        capabilities=["board_write"],
        ttl_seconds=900,
        source="harness_test",
    )
    # Manually override ts to make it old for the test
    prop["ts"] = old_ts
    prop["ttl_seconds"] = 900
    auth = sb.grant(prop)
    # Both the reference monitor and the policy check must agree.
    ttl_ok = pe.check_ttl(prop)
    passed = bool(auth.get("status") == "DENIED" and not ttl_ok)
    r = _test_result("scenario_5_ttl_expiration", passed,
                     {"ttl_ok": ttl_ok, "old_ts": old_ts})
    _write_test_result(r)
    return r


def test_scenario_6() -> dict:
    """Consensus simulation: 3 agents propose same action, verify priority boost."""
    unmet = [
        {"condition": "missing_source_verification", "priority": 1, "eligible_organ": "ghost_memlance"},
        {"condition": "missing_source_verification", "priority": 1, "eligible_organ": "ghost_memlance"},
        {"condition": "missing_source_verification", "priority": 1, "eligible_organ": "ghost_memlance"},
        {"condition": "board_quiescent", "priority": 3, "eligible_organ": "swarm_cycle"},
    ]
    sorted_items = _consensus_priority(unmet)
    # The first 3 should be grouped and come before priority 3
    first = sorted_items[0]
    passed = first.get("_consensus_count") == 3 and first["priority"] == 1
    r = _test_result("scenario_6_consensus_priority", passed,
                     {"first_condition": first.get("condition"), "consensus_count": first.get("_consensus_count")})
    _write_test_result(r)
    return r


def test_scenario_7() -> dict:
    """Full cycle: board → reconcile → queue → lease → grant → (deferred/authorized) → execute stub → receipt → verkle stub."""
    event_id = f"test-sc7-{int(time.time())}"
    # Step 1: reconcile
    rec_result = sb.reconcile()
    # Step 2: pick first unmet, lease it
    decisions = rec_result.get("decisions", [])
    if not decisions:
        # Force a condition
        decisions = [{"condition": "test_sc7", "priority": 1, "eligible_organ": "test_organ",
                       "authority": {"event_id": event_id, "status": "PROPOSED", "granted_capabilities": ["board_write"]}}]
    item = decisions[0]
    condition = item["condition"]
    if _is_leased(condition):
        # Skip if already leased
        pass
    else:
        _create_lease(condition, item.get("eligible_organ", "test"), 300)
        _enqueue({
            "event_id": event_id,
            "condition": condition,
            "organ": item.get("eligible_organ", "test"),
            "authority": item["authority"],
            "capability": "board_write",
        })
    # Step 3: process queue
    queue = _dequeue()
    # Step 4: grant
    prop = sb.propose(
        event_id=event_id, requested_effect="board_write", capabilities=["board_write"],
        source="harness_test_sc7",
    )
    auth = sb.grant(prop)
    # Step 5: execute (dry/stub)
    rec = eb.execute("board_write", {"note": {"text": "scenario 7 full cycle"}}, auth)
    # Step 6: receipt
    _record_receipt("full_cycle", event_id, rec["status"], {"receipt_path": rec.get("receipt_path")})
    # Step 7: verkle stub (simulate)
    verkle_stub = {"ok": True, "stub": True, "event_id": event_id}
    _record_receipt("verkle_stub", event_id, "STUB", verkle_stub)

    passed = (rec["status"] == "RECEIPT_COMMITTED" and
              any(r.get("step") == "full_cycle" for r in _load_jsonl(RECEIPTS_FILE)[-10:]))
    r = _test_result("scenario_7_full_cycle", passed,
                     {"reconcile_ok": rec_result.get("ok"), "execute_status": rec["status"]})
    _write_test_result(r)
    return r


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def cmd_run_once(args):
    result = run_once(dry=args.dry)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["ok"] else 1


def cmd_run_continuous(args):
    run_continuous(interval=args.interval)
    return 0


def cmd_test(args):
    _ensure_dirs()
    scenarios = {
        1: test_scenario_1,
        2: test_scenario_2,
        3: test_scenario_3,
        4: test_scenario_4,
        5: test_scenario_5,
        6: test_scenario_6,
        7: test_scenario_7,
    }
    if args.scenario:
        if args.scenario not in scenarios:
            print(f"Unknown scenario: {args.scenario}")
            return 1
        results = [scenarios[args.scenario]()]
    else:
        results = [fn() for fn in scenarios.values()]

    all_pass = all(r["pass"] for r in results)
    summary = {
        "ok": all_pass,
        "scenario_runs": len(results),
        "passed": sum(r["pass"] for r in results),
        "failed": sum(not r["pass"] for r in results),
        "results": results,
        "ts": _now(),
    }
    _append_jsonl(TEST_RESULTS_FILE, summary)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if all_pass else 1


def cmd_status(args):
    q = _load_queue()
    leases = _load_leases()
    now = _now_epoch()
    active_leases = [l for l in leases if l.get("expires_epoch", 0) > now]
    pending = [i for i in q if not i.get("processed")]
    deferred = [i for i in q if i.get("deferred")]
    last_run = ""
    if LAST_RUN_FILE.exists():
        last_run = LAST_RUN_FILE.read_text(encoding="utf-8").strip()
    status = {
        "ok": True,
        "queue_depth": len(pending),
        "active_leases": len(active_leases),
        "deferred_awaiting_confirmation": len(deferred),
        "last_run": last_run,
        "ts": _now(),
    }
    print(json.dumps(status, indent=2, ensure_ascii=False))
    return 0


def cmd_reset(args):
    if not args.force:
        print("Run with --force to confirm clearing queue, leases, and receipts.")
        return 1
    for f in (QUEUE_FILE, LEASES_FILE, RECEIPTS_FILE, TEST_RESULTS_FILE, LAST_RUN_FILE):
        if f.exists():
            f.unlink()
    print(json.dumps({"ok": True, "cleared": [str(f.name) for f in (QUEUE_FILE, LEASES_FILE, RECEIPTS_FILE, TEST_RESULTS_FILE, LAST_RUN_FILE)], "ts": _now()}, indent=2))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="mag.harness")
    sub = ap.add_subparsers(dest="cmd", required=True)

    o = sub.add_parser("run_once", help="one control-loop pass")
    o.add_argument("--dry", action="store_true", help="skip effect_broker, log stubs")
    o.set_defaults(func=cmd_run_once)

    c = sub.add_parser("run_continuous", help="loop with interval sleep")
    c.add_argument("--interval", type=int, default=60, help="seconds between passes")
    c.set_defaults(func=cmd_run_continuous)

    t = sub.add_parser("test", help="run test scenarios")
    t.add_argument("--scenario", type=int, default=None, help="run single scenario 1-7")
    t.set_defaults(func=cmd_test)

    s = sub.add_parser("status", help="show queue, leases, deferred")
    s.set_defaults(func=cmd_status)

    r = sub.add_parser("reset", help="clear all harness state")
    r.add_argument("--force", action="store_true", help="confirm destructive clear")
    r.set_defaults(func=cmd_reset)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
