#!/usr/bin/env python3
"""RACE HARNESS — the Leg-1 march gate (binding, not aspirational).

SHERPA_ROUTE v2 Leg 1 receipt (d) / ECONOMIST_AUDIT guard (d): NO engine
relaunch until this harness passes. Guard (b): the park fix ships with a live
test that forces one park and greps exactly ONE line — a comment is not
evidence.

What it proves, at the bytes:
  TEST 1 RACE       — two concurrent claimant processes race one queue item,
                      20 repetitions. Exactly one winner per rep, zero
                      double-claims, claim file content matches the winner.
  TEST 2 GRACE      — a fresh claim is invisible to a second claimant; after
                      grace expiry the item is stealable (claimed-but-unfinished
                      requeue); a dead claimant's pid releases immediately.
  TEST 3 PARK LIVE  — spawns `overnight_churn.py --park-test` (real park code
                      path, scratch sinks, no LLM, main loop never entered) and
                      greps the scratch log: exactly ONE "parked as THIN" line.

Scratch roots only: the live bay (watch/bay/claims, bay/locks, bay/state) is
never touched. Exit code 0 = gate open.

Run: python mag/race_harness.py
"""

import glob
import multiprocessing
import os
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from mag import bay_organs  # noqa: E402

REPS = 20
RESULTS = []


def report(name, ok, detail):
    RESULTS.append((name, ok, detail))
    print("[%s] %-10s %s" % ("PASS" if ok else "FAIL", name, detail))


def _racer(root, queue, task_id, engine, barrier, qout, grace_s, hold):
    """One claimant process. Barrier-synced so the two racers truly race.
    A WINNER holds its claim until `hold` is set — like a real engine mid-
    dispatch. (Measured: a claimant that exits right after claiming looks
    exactly like a crashed claimer, and the design CORRECTLY releases its
    food — the first harness draft measured that takeover, not the race.)"""
    try:
        barrier.wait(timeout=30)
        claim = bay_organs.try_claim(queue, task_id, engine=engine, slot=engine,
                                     grace_s=grace_s, root=root)
        qout.put({"pid": os.getpid(), "engine": engine,
                  "won": claim is not None,
                  "token": claim["token"] if claim else None})
        if claim is not None:
            hold.wait(timeout=30)  # stay a live claimant while the race resolves
    except Exception as e:  # BrokenBarrierError or organ failure: report honestly
        try:
            qout.put({"pid": os.getpid(), "engine": engine, "won": False,
                      "error": repr(e)})
        except Exception:
            pass


def test_race():
    root = tempfile.mkdtemp(prefix="race_harness_")
    queue = "race_queue"
    double_claims = 0
    zero_winner = 0
    for rep in range(REPS):
        task_id = "race-item-%02d" % rep
        barrier = multiprocessing.Barrier(2)
        qout = multiprocessing.Queue()
        hold = multiprocessing.Event()
        racers = [multiprocessing.Process(target=_racer,
                                          args=(root, queue, task_id, "racer-%d" % (i + 1),
                                                barrier, qout, 300, hold))
                  for i in range(2)]
        for r in racers:
            r.start()
        got = [qout.get(timeout=60) for _ in range(2)]
        hold.set()  # release the winner's claim hold
        for r in racers:
            r.join(timeout=30)
        wins = [g for g in got if g.get("won")]
        if len(wins) == 0:
            zero_winner += 1
        if len(wins) > 1:
            double_claims += 1
        # byte-level cross-check: exactly ONE claim file, no temp litter,
        # and the file's pid/engine match the reported winner.
        files = glob.glob(os.path.join(bay_organs.claim_dir(queue, root), "%s.json" % task_id))
        tmps = glob.glob(os.path.join(bay_organs.claim_dir(queue, root), ".tmp-*"))
        if len(wins) == 1:
            if len(files) != 1 or tmps:
                double_claims += 1  # file-state disagrees with the CAS verdict
                continue
            fc = bay_organs._read_claim(files[0])
            if not fc or fc.get("engine") != wins[0]["engine"] or fc.get("pid") != wins[0]["pid"]:
                double_claims += 1
    report("RACE", double_claims == 0 and zero_winner == 0,
           "%d reps x 2 claimants on one item: double-claims=%d zero-winner=%d" % (
               REPS, double_claims, zero_winner))


def test_grace():
    root = tempfile.mkdtemp(prefix="grace_harness_")
    queue = "grace_queue"
    ok = True
    detail = []
    # 1. fresh claim = invisible to other claimants
    a = bay_organs.try_claim(queue, "g1", engine="A", slot="s", grace_s=300, root=root)
    b = bay_organs.try_claim(queue, "g1", engine="B", slot="s", grace_s=300, root=root)
    ok &= bool(a) and b is None
    detail.append("fresh-claim-invisible=%s" % (bool(a) and b is None))
    # 2. claimed-but-unfinished requeues after grace expiry
    time.sleep(0.2)
    c = bay_organs.try_claim(queue, "g2", engine="A", slot="s", grace_s=1, root=root)
    time.sleep(1.3)
    d = bay_organs.try_claim(queue, "g2", engine="B", slot="s", grace_s=300, root=root)
    ok &= bool(c) and bool(d)
    detail.append("expired-claim-takeover=%s" % (bool(c) and bool(d)))
    # 3. dead claimant's pid releases food immediately
    p = subprocess.Popen([sys.executable, "-c", "pass"])
    p.wait()
    e = bay_organs.try_claim(queue, "g3", engine="ghost", slot="s", grace_s=300, root=root)
    # forge the ghost claim with the dead pid (simulates a claimer that died)
    ghost_path = bay_organs.claim_path(queue, "g3", root)
    dead_claim = dict(e or {})
    dead_claim.update({"engine": "ghost", "pid": p.pid})
    bay_organs.atomic_write_json(ghost_path, dead_claim, overwrite=True)
    f = bay_organs.try_claim(queue, "g3", engine="B", slot="s", grace_s=300, root=root)
    ok &= bool(e) and bool(f) and f.get("engine") == "B"
    detail.append("dead-pid-releases=%s" % (bool(e) and bool(f)))
    report("GRACE", bool(ok), " ".join(detail) + " (grace default %ds, env BAY_CLAIM_GRACE_S)" % (
        bay_organs.DEFAULT_GRACE_S))


def test_park_live():
    churn = os.path.join(ROOT, "watch", "overnight_churn.py")
    r = subprocess.run([sys.executable, churn, "--park-test"],
                       capture_output=True, text=True, timeout=120, cwd=ROOT)
    log_path = None
    for line in r.stdout.splitlines():
        if line.startswith("PARKTEST-LOG "):
            log_path = line.split("PARKTEST-LOG ", 1)[1].strip()
    ok = False
    detail = "no PARKTEST-LOG in output"
    if log_path and os.path.isfile(log_path):
        lines = [l for l in open(log_path, encoding="utf-8").read().splitlines()
                 if "parked as THIN" in l]
        ok = (r.returncode == 0 and len(lines) == 1 and "PARKTEST OK" in r.stdout)
        detail = "exit=%d park-lines=%d (exactly ONE required) stdout-verdict=%s" % (
            r.returncode, len(lines),
            "OK" if "PARKTEST OK" in r.stdout else "FAIL")
    report("PARK-LIVE", ok, detail)


def main():
    print("RACE HARNESS - Leg-1 march gate (SHERPA_ROUTE v2 receipt d, ECONOMIST guard b+d)")
    print("claim organ: %s" % bay_organs.__file__)
    test_race()
    test_grace()
    test_park_live()
    failed = [n for n, ok, _ in RESULTS if not ok]
    print("-" * 72)
    print("RACE-HARNESS %s (%d/%d tests passed)%s" % (
        "PASS - GATE OPEN" if not failed else "FAIL - NO RELAUNCH",
        len(RESULTS) - len(failed), len(RESULTS),
        "" if not failed else " failed: " + ",".join(failed)))
    return 0 if not failed else 1


if __name__ == "__main__":
    multiprocessing.freeze_support()
    sys.exit(main())
