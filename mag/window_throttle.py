#!/usr/bin/env python3
"""window_throttle — one primary per work window (salon day direction 2026-09-04, item 3).

Night windows are triple-booked (sweeps + burns 2/4 + ractor panels, 23:00-09:00,
no coordinator). This organ makes "who is primary for this window" a FILE under
watch/windows/<window>.json, claimed by atomic create: two seats race, exactly
one primary. The Launch Law's same-turn builders consult this before they
multiply.

CAS discipline inherited from mag/bay_organs.py (claim organ, race-verified:
watch/CLAIM_ORGAN_RACE_TEST_20260904.md; FINDING 1 fix receipted in
watch/CAS_FIX_RECEIPT_20260904.md):
  - temp-write (same dir = same volume) + os.rename = create-only CAS. On win32
    os.rename raises FileExistsError when the target exists: that is the race
    winner's signal. (win32 is this fleet's measured host; POSIX rename
    overwrites silently and must not host this organ.)
  - stale takeover (EXPIRY PASSED — and only expiry; see the lease law below)
    is judge-then-CAS and NEVER blind: re-read the target and tomb-move ONLY if
    it still holds the EXACT claim proven stale (token match at commit time).
    Any race-away is an honest loss, no write. Kills the FINDING 1 split-brain
    class (two takers, two winners, a live claim tombed).
  - an unreadable claim file is never a lock and never stolen blind: lose
    safely (and unlike bay_organs FINDING 2, sweep removes unreadable claim
    files older than 300s, so corruption cannot wedge a window forever).
  - release is token-guarded: an expired-and-taken-over window belongs to the
    NEW primary; the old holder's late release must not fire.

LEASE LAW (measured, not assumed — the first race run of
watch/test_window_throttle_race_20260904.py FAILED with 2-3 winners per round
until this was written down): the lease is EXPIRY-ONLY. bay_organs releases a
claim when the claimant pid dies, which is right for long-lived engines holding
queue items — but a window primary is claimed by a SHORT-LIVED CLI process that
exits the moment the claim is written. Under pid-death-release, every claim is
stale within milliseconds (rivals read it, pid_alive says dead, they steal):
instant split-brain, the exact disease this organ exists to kill. So here the
claim OUTLIVES the claiming process: active = unexpired, takeover = expired,
and the pid is recorded for ATTRIBUTION (status reports pid_alive as
information only). Consequence: a vanished holder keeps its window until
expiry — set TTLs honestly; short TTLs self-heal (default 1h).

Claim file: <root>/<window>.json
  {"schema": "window_throttle.v1", "window", "holder", "purpose", "pid", "ts",
   "ttl_s", "expires_at", "token"}

The claim's OWN expires_at (fixed at claim time) is the expiry that counts;
the default TTL only covers claims made without one.

CLI (exit codes: 0 = won/ok, 3 = honest loss/refused, 2 = usage/env error):
  python -m mag.window_throttle claim   <window> --holder H --purpose P [--ttl S]
  python -m mag.window_throttle release <window> --token T
  python -m mag.window_throttle status  [<window>]
  python -m mag.window_throttle sweep

stdlib only, $0 at runtime, no LLM calls. Root override: WINDOW_THROTTLE_ROOT
(race harness passes root= explicitly and never touches the live watch/windows/).
"""

from __future__ import annotations

import calendar
import json
import os
import random
import time

SCHEMA = "window_throttle.v1"
DEFAULT_TTL_S = int(os.environ.get("WINDOW_THROTTLE_TTL_S", "3600"))
DEFAULT_ROOT = os.environ.get(
    "WINDOW_THROTTLE_ROOT",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                 "watch", "windows"))
TMP_LITTER_S = 300        # .tmp- files older than this are crash debris
TOMB_TTL_S = 3600         # .expired- tombstones older than this are swept
UNREADABLE_S = 300        # unreadable claim older than this is swept (wedge kill)

try:  # one measured win32 liveness probe, not a fork (see bay_organs.pid_alive:
    from mag.bay_organs import pid_alive  # os.kill(pid,0) is a no-op here)
except ImportError:
    import sys as _sys
    _REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _REPO not in _sys.path:
        _sys.path.insert(0, _REPO)
    from mag.bay_organs import pid_alive


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _iso_to_epoch(ts) -> int | None:
    try:
        return calendar.timegm(time.strptime(ts, "%Y-%m-%dT%H:%M:%SZ"))
    except (TypeError, ValueError, OverflowError):
        return None


def _check_window_name(window) -> str:
    """Window names are file names: reject path-likes and dotfiles."""
    if not window or not isinstance(window, str):
        raise ValueError("window name required")
    if (window.startswith(".") or "/" in window or "\\" in window
            or ":" in window):
        raise ValueError("bad window name (path-like): %r" % window)
    return window


def window_path(window, root=None) -> str:
    return os.path.join(root or DEFAULT_ROOT,
                        _check_window_name(window) + ".json")


def _read_claim(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            obj = json.load(fh)
        return obj if isinstance(obj, dict) else None
    except (OSError, ValueError):
        return None


def claim_is_active(claim, now=None) -> bool:
    """Active = unexpired, by the claim's OWN expires_at (fixed at claim time).
    LEASE LAW: expiry ONLY — pid-death never releases a window (claimants are
    short-lived CLIs; see module docstring for the measured failure that made
    this law). An unreadable claim is never a lock."""
    if not claim:
        return False
    exp = _iso_to_epoch(claim.get("expires_at"))
    if exp is None:
        return False
    now = time.time() if now is None else now
    return now < exp


def _tomb_move_if_same(target, tomb, judged_token) -> bool:
    """CAS tomb-move for the stale-takeover path: only move the claim at target
    aside if it is STILL the exact claim the taker proved stale (token match at
    commit time). A mismatch means a rival's fresh claim landed after our read:
    refuse, no write, lose honestly."""
    current = _read_claim(target)
    if current is None or current.get("token") != judged_token:
        return False
    try:
        os.rename(target, tomb)
        return True
    except OSError:
        return False


def claim(window, holder, purpose, ttl_s=DEFAULT_TTL_S, root=None):
    """Atomically claim primary for one work window. Returns the claim dict on
    win, None on honest loss (window held by a fresh live claim, or no clean
    verdict in three rounds — never a blind steal). Takeover of stale claims
    (expired or dead pid) is judge-then-token-checked-CAS; every interleaving
    of two takers yields exactly one winner because the takeover commit and
    the final creation are both rename-CASes onto the one fixed target name."""
    target = window_path(window, root)
    d = os.path.dirname(os.path.abspath(target))
    os.makedirs(d, exist_ok=True)
    ttl_s = int(ttl_s)
    t0 = time.time()
    my_claim = {
        "schema": SCHEMA,
        "window": _check_window_name(window),
        "holder": str(holder),
        "purpose": str(purpose),
        "pid": os.getpid(),
        "ts": now_iso(),
        "ttl_s": ttl_s,
        "expires_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t0 + ttl_s)),
        "token": "%d-%d" % (time.time_ns(), random.randrange(1 << 30)),
    }
    tmp = os.path.join(d, ".tmp-%d-%d-%s.json" % (
        os.getpid(), time.time_ns(),
        "".join(random.choice("0123456789abcdef") for _ in range(6))))
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(my_claim, f, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    try:
        for _round in range(3):
            try:
                os.rename(tmp, target)      # CAS: win32 raises FileExistsError if held
                return my_claim
            except FileExistsError:
                pass
            except OSError:
                pass  # sharing violation mid-race: fall through to read-and-judge
            existing = None
            for _try in range(3):           # re-read against transient filter locks
                existing = _read_claim(target)
                if existing is not None:
                    break
                time.sleep(0.02)
            if existing is None:
                continue  # target gone (raced away) or unreadable: retry CAS, never steal
            if claim_is_active(existing):
                return None  # fresh live primary: we lost, cleanly
            # POSITIVE staleness proven (parseable + expired or dead pid):
            # commit takeover by token-checked tomb-move, then CAS the freed name.
            tomb = os.path.join(d, ".expired-%s-%d-%d.json" % (
                _check_window_name(window), time.time_ns(), os.getpid()))
            _tomb_move_if_same(target, tomb, existing.get("token"))
        return None  # no clean verdict in three rounds: lose safely
    finally:
        if os.path.isfile(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def release(window, token, root=None) -> bool:
    """Release OUR claim. Only removes the file if it still carries our token —
    an expired-and-taken-over window belongs to the new primary."""
    target = window_path(window, root)
    c = _read_claim(target)
    if not c or c.get("token") != token:
        return False
    try:
        os.remove(target)
        return True
    except OSError:
        return False


def status(window=None, root=None) -> dict:
    """Who is primary, per window. States: held_active (unexpired lease),
    held_stale (expired — takeover-able), free. pid_alive is INFORMATION ONLY
    (attribution); it never changes the lease (see module docstring)."""
    r = root or DEFAULT_ROOT
    now = time.time()
    if window is not None:
        names = [_check_window_name(window)]
    else:
        names = sorted(n[:-5] for n in os.listdir(r)
                       if n.endswith(".json") and not n.startswith(".")) \
            if os.path.isdir(r) else []
    out = {"root": os.path.abspath(r), "now": now_iso(), "windows": {}}
    for name in names:
        c = _read_claim(window_path(name, r))
        if c is None:
            out["windows"][name] = {"state": "free"}
            continue
        exp = _iso_to_epoch(c.get("expires_at"))
        active = claim_is_active(c, now)
        out["windows"][name] = {
            "state": "held_active" if active else "held_stale",
            "holder": c.get("holder"),
            "purpose": c.get("purpose"),
            "pid": c.get("pid"),
            "pid_alive": pid_alive(c.get("pid")),
            "ts": c.get("ts"),
            "expires_at": c.get("expires_at"),
            "seconds_left": max(0, int(exp - now)) if exp is not None else None,
        }
    return out


def sweep(root=None) -> int:
    """Garbage-collect one windows root. Removes: crash .tmp- debris, old
    .expired- tombstones, EXPIRED claims (the lease law frees them at expiry,
    whatever the pid), and unreadable claim files older than UNREADABLE_S
    (bay_organs FINDING 2 wedge, killed here). Unexpired claims are never
    touched — a vanished holder keeps its window until expiry. Returns count
    removed."""
    r = root or DEFAULT_ROOT
    if not os.path.isdir(r):
        return 0
    now = time.time()
    removed = 0
    for name in os.listdir(r):
        p = os.path.join(r, name)
        try:
            age = now - os.path.getmtime(p)
        except OSError:
            continue
        if name.startswith(".tmp-"):
            if age > TMP_LITTER_S:
                try:
                    os.remove(p)
                    removed += 1
                except OSError:
                    pass
            continue
        if name.startswith(".expired-"):
            if age > TOMB_TTL_S:
                try:
                    os.remove(p)
                    removed += 1
                except OSError:
                    pass
            continue
        if name.endswith(".json") and not name.startswith("."):
            c = _read_claim(p)
            if c is None:
                if age > UNREADABLE_S:  # unreadable + not fresh = debris, never a lock
                    try:
                        os.remove(p)
                        removed += 1
                    except OSError:
                        pass
                continue
            if not claim_is_active(c, now):
                try:
                    os.remove(p)  # expired lease (holder keeps it until expiry; then it frees)
                    removed += 1
                except OSError:
                    pass
    return removed


# ── CLI ──────────────────────────────────────────────────────────

def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(
        prog="mag.window_throttle",
        description="One primary per work window — atomic file claim under watch/windows/")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_claim = sub.add_parser("claim", help="claim primary for a window")
    p_claim.add_argument("window")
    p_claim.add_argument("--holder", required=True, help="seat/organ claiming")
    p_claim.add_argument("--purpose", required=True, help="what the window is for")
    p_claim.add_argument("--ttl", type=int, default=DEFAULT_TTL_S,
                         help="expiry seconds (default %d, env WINDOW_THROTTLE_TTL_S)" % DEFAULT_TTL_S)
    p_claim.add_argument("--root", default=None, help="override windows root")

    p_rel = sub.add_parser("release", help="release a claim (token-guarded)")
    p_rel.add_argument("window")
    p_rel.add_argument("--token", required=True)
    p_rel.add_argument("--root", default=None)

    p_st = sub.add_parser("status", help="who holds what (always exit 0)")
    p_st.add_argument("window", nargs="?", default=None)
    p_st.add_argument("--root", default=None)

    p_sw = sub.add_parser("sweep", help="remove dead claims, tombstones, debris")
    p_sw.add_argument("--root", default=None)

    args = ap.parse_args(argv)
    try:
        if args.cmd == "claim":
            c = claim(args.window, args.holder, args.purpose,
                      ttl_s=args.ttl, root=args.root)
            if c is None:
                held = status(args.window, root=args.root)["windows"].get(args.window, {})
                print(json.dumps({
                    "ok": False, "window": args.window, "lost": True,
                    "held_by": held.get("holder"), "state": held.get("state"),
                    "purpose": held.get("purpose"),
                    "expires_at": held.get("expires_at"),
                }, ensure_ascii=False))
                return 3  # honest loss
            print(json.dumps({"ok": True, "claim": c}, ensure_ascii=False))
            return 0
        if args.cmd == "release":
            ok = release(args.window, args.token, root=args.root)
            print(json.dumps({"ok": ok, "window": args.window,
                              "released": ok}, ensure_ascii=False))
            return 0 if ok else 3
        if args.cmd == "status":
            print(json.dumps(status(args.window, root=args.root),
                             indent=2, ensure_ascii=False))
            return 0
        if args.cmd == "sweep":
            n = sweep(root=args.root)
            print(json.dumps({"ok": True, "removed": n}, ensure_ascii=False))
            return 0
    except ValueError as e:  # bad window name
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
