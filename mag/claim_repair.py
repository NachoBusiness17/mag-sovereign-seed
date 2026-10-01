#!/usr/bin/env python3
"""claim_repair — FINDING 2 fix for the claim organ (watch/
CLAIM_ORGAN_RACE_TEST_20260904.md): a CORRUPT claim file (bad JSON, missing
fields, aged tombstone residue) makes `sweep_expired` skip or choke and
`try_claim` lose-forever — the tranche is stranded until a human deletes the
file by hand. This tool scans a claims store, classifies every corrupt/stale
claim, QUARANTINES it (evidence preserved, never deleted), and re-opens the
tranche by proving it claimable again (try_claim win + immediate release)
ONLY when the tranche's work is verifiably not done.

Corruption classes handled:
  unparseable      — file is not JSON, or valid JSON that is not an object
                     (a non-object also CRASHES claim_is_active/_tomb_move_if_same
                     via .get -> the sweeper chokes, not just skips)
  missing-fields   — parses as an object but lacks required keys (pid/ts/token);
                     a missing ts makes claim_is_active judge a LIVE holder
                     stale (double-execution hazard), so live holders are LEFT
                     in place, never yanked
  expired-lease    — parses fine but stale: claimant pid dead, or lease past
                     its window. The old sweep blind-DELETED these (no
                     evidence); repair quarantines instead
  tomb-mismatch    — aged `.expired-*` tombstone residue (corrupt or
                     well-formed, token recorded for the record). FRESH
                     tombstones are never touched — the CAS split-brain fix
                     (FINDING 1) relies on them transiently

Laws baked in: dry-run by default (--apply to mutate); backup-first (the whole
claims store is copied under <repair_root>/backup-<ts>/ before any move);
quarantine-don't-delete; append-only jsonl receipts; re-issue only on verified
not-done (parked marker / THIN output / missing queue row all refuse);
idempotent (a second apply run finds nothing left to repair).

CLI:
  python -m mag.claim_repair                       # dry-run, all queues
  python -m mag.claim_repair --queue march228      # dry-run, one queue
  python -m mag.claim_repair --apply               # mutate (backs up first)

Env knobs (tests): CLAIM_REPAIR_QUEUE_DIR (where <queue>.jsonl lives),
CLAIM_REPAIR_STATE (churn state json with the parked map).
"""

import hashlib
import json
import os
import shutil
import sys
import time

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from mag import bay_organs
else:
    from . import bay_organs

REQUIRED_FIELDS = ("pid", "ts", "token")
TMP_MAX_AGE_S = 300          # mirrors sweep_expired's .tmp threshold
REPAIR_ENGINE = "claim-repair"
REISSUE_GRACE_S = 60         # re-issue proof claim; released immediately


def compact_ts():
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def iso_ts():
    return bay_organs.now_iso()


def repair_root_for(root):
    """Repair artifacts live as a sibling of the claims store (same volume by
    construction — quarantine renames never cross a filesystem boundary)."""
    return os.path.join(os.path.dirname(os.path.abspath(root or
                        bay_organs.DEFAULT_CLAIMS_ROOT)), "repair")


def queue_dir():
    """Where <queue>.jsonl work manifests live (overnight_queue.jsonl etc.)."""
    env = os.environ.get("CLAIM_REPAIR_QUEUE_DIR")
    if env:
        return env
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(repo, "watch")


def state_path():
    env = os.environ.get("CLAIM_REPAIR_STATE")
    if env:
        return env
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(repo, "watch", "churn_state.json")


# --------------------------------------------------------------------------
# classification
# --------------------------------------------------------------------------

def classify_file(path, grace_s=bay_organs.DEFAULT_GRACE_S, now=None):
    """Classify one claims-store file. Returns a finding dict; action field is
    one of: skip-live / leave-live-corrupt / repair / skip-fresh-tomb /
    skip-foreign. cls is None for healthy files."""
    now = now if now is not None else time.time()
    name = os.path.basename(path)
    f = {"file": name, "path": path, "cls": None, "detail": "",
         "action": "skip-foreign", "task": None, "claim": None,
         "pid_alive": None, "age_s": None, "sha256": None, "size": None}
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except OSError as e:
        f["detail"] = "unreadable: %r" % (e,)
        return f
    f["size"] = len(raw)
    f["sha256"] = hashlib.sha256(raw).hexdigest()

    if name.startswith(".tmp-"):
        try:
            age = now - os.path.getmtime(path)
        except OSError:
            return f
        f["age_s"] = round(age, 1)
        if age > TMP_MAX_AGE_S:
            f["cls"] = "tomb-mismatch"  # litter is tomb-class residue
            f["detail"] = "aged .tmp litter (%.0fs > %ds), sweep handles or repair quarantines" % (age, TMP_MAX_AGE_S)
            f["action"] = "repair"
        return f

    if name.startswith(".expired-"):
        try:
            age = now - os.path.getmtime(path)
        except OSError:
            return f
        f["age_s"] = round(age, 1)
        if age <= grace_s:
            f["action"] = "skip-fresh-tomb"
            f["detail"] = "fresh tombstone (%.0fs <= %ds grace): CAS split-brain fix relies on these transiently" % (age, grace_s)
            return f
        f["cls"] = "tomb-mismatch"
        f["action"] = "repair"
        tomb = None
        try:
            obj = json.loads(raw.decode("utf-8"))
            if isinstance(obj, dict):
                tomb = obj
        except (ValueError, UnicodeDecodeError):
            pass
        if tomb is None:
            f["detail"] = "aged tombstone, content unparseable (corrupt tomb residue)"
        else:
            f["task"] = tomb.get("task")
            f["detail"] = "aged tombstone residue (token=%r); old sweep blind-deleted this" % (tomb.get("token"),)
        return f

    if not name.endswith(".json"):
        f["detail"] = "not a claim file shape; left alone"
        return f

    f["task"] = name[:-len(".json")]
    try:
        obj = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        f["cls"] = "unparseable"
        f["detail"] = "JSON parse failed (bad/truncated/empty)"
        f["action"] = "repair"
        return f
    if not isinstance(obj, dict):
        f["cls"] = "unparseable"
        f["detail"] = "valid JSON but not an object (%s): claim_is_active/_tomb_move_if_same .get would CHOKE the sweeper" % (type(obj).__name__,)
        f["action"] = "repair"
        return f
    f["claim"] = obj
    missing = [k for k in REQUIRED_FIELDS if k not in obj]
    alive = bay_organs.pid_alive(obj.get("pid"))
    f["pid_alive"] = alive

    ts_val = obj.get("ts")
    age = None
    ts_ok = isinstance(ts_val, str)
    if ts_ok:
        try:
            age = _ts_age(ts_val, now)
        except (ValueError, OverflowError):
            ts_ok = False
    f["age_s"] = round(age, 1) if age is not None else None

    if missing:
        f["cls"] = "missing-fields"
        f["detail"] = "missing required fields: %s" % ",".join(missing)
        if alive and not ts_ok:
            # live holder, freshness unjudgeable (e.g. ts lost in a half-write):
            # yanking it would let a rival double-execute under the worker.
            f["action"] = "leave-live-corrupt"
            f["detail"] += "; LIVE holder pid=%r, lease unjudgeable -> left in place (never yank a live claim)" % (obj.get("pid"),)
        elif alive and ts_ok and age < _window(obj, grace_s):
            # actually healthy: fresh live claim that merely lacks optional keys
            f["cls"] = None
            f["action"] = "skip-live"
            f["detail"] = "fresh live claim (missing only optional fields)"
        else:
            f["action"] = "repair"
            if alive:
                f["detail"] += "; holder alive but lease proven stale -> takeover-legal, quarantine"
        return f

    # required fields present: healthy vs expired-lease
    if alive and age is not None and age < _window(obj, grace_s):
        f["cls"] = None
        f["action"] = "skip-live"
        f["detail"] = "fresh live claim"
        return f
    f["cls"] = "expired-lease"
    f["action"] = "repair"
    if not alive:
        f["detail"] = "claimant pid %r dead" % (obj.get("pid"),)
    else:
        f["detail"] = "lease expired (%.0fs >= %ds window) with live holder: takeover-legal" % (age, _window(obj, grace_s))
    return f


def _ts_age(ts_val, now):
    """Age of an ISO claim timestamp vs now, UTC-correct (mirrors
    bay_organs.claim_is_active's calendar.timegm parse)."""
    import calendar
    return now - calendar.timegm(time.strptime(ts_val, "%Y-%m-%dT%H:%M:%SZ"))


def _window(claim, default_grace_s):
    try:
        return int(claim.get("grace_s", default_grace_s))
    except (TypeError, ValueError):
        return int(default_grace_s)


def scan(root=None, queues=None, grace_s=bay_organs.DEFAULT_GRACE_S, now=None):
    """Scan the claims store. queues=None -> every queue dir found. Returns
    (findings, queues_scanned). Active claims and fresh tombstones come back
    with cls None / skip actions — the repair loop never touches them."""
    root = root or bay_organs.DEFAULT_CLAIMS_ROOT
    now = now if now is not None else time.time()
    findings = []
    found = []
    if not os.path.isdir(root):
        return findings, found
    for entry in sorted(os.listdir(root)):
        d = os.path.join(root, entry)
        if not os.path.isdir(d):
            continue
        if queues and entry not in queues:
            continue
        found.append(entry)
        for name in sorted(os.listdir(d)):
            p = os.path.join(d, name)
            if not os.path.isfile(p):
                continue
            fnd = classify_file(p, grace_s=grace_s, now=now)
            fnd["queue"] = entry
            findings.append(fnd)
    return findings, found


# --------------------------------------------------------------------------
# work-state verification (never double-execute)
# --------------------------------------------------------------------------

def work_state(queue, task):
    """Is the tranche's work verifiably not done? Checks the work's OWN
    markers, in order: the churn state's parked map (permanent), then the
    queue manifest row's output file (substantive bytes = done, THIN head =
    parked-thin, absent = not-done). Returns one of:
    parked / parked-thin / done / not-done / unverifiable.
    Only 'not-done' authorizes a re-issue."""
    task = str(task)
    try:
        with open(state_path(), "r", encoding="utf-8") as fh:
            st = json.load(fh)
        if isinstance(st, dict) and st.get("parked", {}).get(task):
            return "parked"
    except (OSError, ValueError):
        pass
    qfile = os.path.join(queue_dir(), "%s.jsonl" % queue)
    row = None
    try:
        with open(qfile, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if isinstance(r, dict) and str(r.get("id")) == task:
                    row = r
                    break
    except OSError:
        return "unverifiable"
    if not isinstance(row, dict):
        return "unverifiable"
    out = row.get("output")
    if not out:
        return "unverifiable"
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    op = out if os.path.isabs(out) else os.path.join(repo, out)
    if not os.path.isfile(op):
        return "not-done"
    try:
        with open(op, "r", encoding="utf-8", errors="replace") as fh:
            head = fh.read(512)
    except OSError:
        return "unverifiable"
    if "THIN:" in head:
        return "parked-thin"
    if head.strip():
        return "done"
    return "not-done"


REISSUE_ELIGIBLE = ("unparseable", "missing-fields", "expired-lease")


# --------------------------------------------------------------------------
# repair
# --------------------------------------------------------------------------

def _quarantine_path(repair_root, queue, name, stamp):
    q = os.path.join(repair_root, "quarantine")
    os.makedirs(q, exist_ok=True)
    safe_q = "".join(c if c.isalnum() or c in "-_" else "_" for c in queue)
    return os.path.join(q, "%s-%s-%s" % (stamp, safe_q, name))


def _append_receipt(receipt_path, row):
    os.makedirs(os.path.dirname(os.path.abspath(receipt_path)), exist_ok=True)
    with open(receipt_path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def repair(root=None, apply=False, queues=None,
           grace_s=bay_organs.DEFAULT_GRACE_S, receipt_path=None,
           repair_root=None, now=None):
    """Scan + (on apply) quarantine + re-issue. Dry-run is the default:
    apply=False reports and writes would-* receipt rows, touches nothing.
    Returns the run summary dict."""
    root = root or bay_organs.DEFAULT_CLAIMS_ROOT
    repair_root = repair_root or repair_root_for(root)
    receipt_path = receipt_path or os.path.join(repair_root,
                                                "claim_repair_receipts.jsonl")
    now = now if now is not None else time.time()
    stamp = compact_ts()
    run_id = "claim-repair-%s-%d-%d" % (stamp, os.getpid(), time.time_ns())
    mode = "apply" if apply else "dry-run"

    findings, queues_scanned = scan(root, queues=queues, grace_s=grace_s, now=now)
    todo = [f for f in findings if f.get("action") == "repair"]
    summary = {"ts": iso_ts(), "run_id": run_id, "mode": mode,
               "kind": "summary", "root": root, "queues": queues_scanned,
               "scanned": len(findings), "to_repair": len(todo),
               "quarantined": 0, "reissued": 0, "reissue_refused": 0,
               "by_class": {}, "backup": None}

    backup_dir = None
    if apply and todo:
        # BACKUP-FIRST: copy the whole claims store before any surgery.
        backup_dir = os.path.join(repair_root, "backup-%s" % stamp)
        os.makedirs(backup_dir, exist_ok=True)
        if os.path.isdir(root):
            shutil.copytree(root, os.path.join(backup_dir, "claims"),
                            dirs_exist_ok=True)
        summary["backup"] = backup_dir

    for fnd in todo:
        summary["by_class"][fnd["cls"]] = summary["by_class"].get(fnd["cls"], 0) + 1
        row = {"ts": iso_ts(), "run_id": run_id, "mode": mode, "kind": "item",
               "queue": fnd["queue"], "file": fnd["file"], "task": fnd["task"],
               "cls": fnd["cls"], "detail": fnd["detail"],
               "sha256": fnd["sha256"], "size": fnd["size"],
               "age_s": fnd["age_s"], "pid_alive": fnd["pid_alive"],
               "action": None, "quarantine_path": None,
               "work_state": None, "reissued": False, "reissue_note": None}

        # tomb-mismatch residue: quarantine only, no work-state check needed
        # (the tranche's claim is already gone; nothing to re-issue).
        consider_reissue = fnd["cls"] in REISSUE_ELIGIBLE and fnd["task"]
        wstate = work_state(fnd["queue"], fnd["task"]) if consider_reissue else None
        row["work_state"] = wstate
        do_reissue = bool(consider_reissue and wstate == "not-done")

        if apply:
            qpath = _quarantine_path(repair_root, fnd["queue"], fnd["file"], stamp)
            try:
                os.rename(fnd["path"], qpath)  # same volume: atomic move-aside
            except OSError:
                shutil.move(fnd["path"], qpath)
            row["action"] = "quarantined"
            row["quarantine_path"] = qpath
            summary["quarantined"] += 1
            if do_reissue:
                claim = bay_organs.try_claim(
                    fnd["queue"], fnd["task"], engine=REPAIR_ENGINE,
                    slot="repair", grace_s=REISSUE_GRACE_S, root=root)
                if claim:
                    bay_organs.release_claim(fnd["queue"], fnd["task"],
                                             claim["token"], root=root)
                    row["reissued"] = True
                    row["reissue_note"] = ("tranche re-opened: try_claim won "
                                           "then released (item free for the fleet)")
                    summary["reissued"] += 1
                else:
                    row["reissue_note"] = ("raced: a live claim now holds the item; "
                                           "tranche is owned, not stranded")
                    summary["reissue_refused"] += 1
            elif consider_reissue:
                row["reissue_note"] = "re-issue refused: work_state=%s (never double-execute)" % wstate
                summary["reissue_refused"] += 1
        else:
            row["action"] = "would-quarantine"
            if do_reissue:
                row["reissued"] = None  # decided only on apply
                row["reissue_note"] = "would re-issue (work_state=not-done)"
            elif consider_reissue:
                row["reissue_note"] = "would NOT re-issue (work_state=%s)" % wstate
        _append_receipt(receipt_path, row)

    summary["receipt"] = receipt_path
    _append_receipt(receipt_path, summary)
    return summary


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(
        prog="mag.claim_repair",
        description="FINDING 2 fix: classify + quarantine + re-issue corrupt "
                    "claim-organ tranches. Dry-run by default.")
    ap.add_argument("--root", default=None, help="claims store root "
                    "(default CHURN_CLAIMS_ROOT or watch/bay/claims)")
    ap.add_argument("--queue", action="append", default=None,
                    help="restrict to this queue dir (repeatable)")
    ap.add_argument("--apply", action="store_true",
                    help="actually quarantine + re-issue (default: dry-run)")
    ap.add_argument("--grace", type=int, default=bay_organs.DEFAULT_GRACE_S,
                    help="grace window seconds for lease expiry (default %d)"
                         % bay_organs.DEFAULT_GRACE_S)
    ap.add_argument("--receipt", default=None, help="receipt jsonl path")
    args = ap.parse_args(argv)

    root = args.root or os.environ.get("CHURN_CLAIMS_ROOT") \
        or bay_organs.DEFAULT_CLAIMS_ROOT
    s = repair(root=root, apply=args.apply, queues=args.queue,
               grace_s=args.grace, receipt_path=args.receipt)
    print("CLAIM-REPAIR %s root=%s" % (s["mode"].upper(), s["root"]))
    print("  queues=%s scanned=%d to_repair=%d" %
          (",".join(s["queues"]) or "-", s["scanned"], s["to_repair"]))
    for cls, n in sorted(s["by_class"].items()):
        print("  %s: %d" % (cls, n))
    if args.apply:
        print("  quarantined=%d reissued=%d refused=%d backup=%s"
              % (s["quarantined"], s["reissued"], s["reissue_refused"],
                 s["backup"] or "-"))
    else:
        print("  DRY-RUN: nothing moved. Re-run with --apply to quarantine "
              "+ re-issue (backs up the store first).")
    print("  receipt: %s" % s["receipt"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
