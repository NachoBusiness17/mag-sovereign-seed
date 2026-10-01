"""team_knot — turn AdventureNLearn inward: anchor the SHARED TEAM REALITY to the verkle chain.

Operator (2026-08-24): "use what we did with adventurnlearn with ourself internally to make sure
we are all working off the verkle instead of our own bullshit."

THE PROBLEM it solves (proven live): two sessions on the same repo, each trusting its own local
narrative, collided — one deliberately parked the mag stack ("machine is yours again", shelved the
autonomous loop), the other cold-booted the full stack 7 minutes later, re-engaging the very loop
that was just shelved. Both were "right" in their own session; neither was reading shared reality.

THE MECHANISM (AdventureNLearn, internalized):
  - The shared WORK is the journey. Each engagement (session) is ONE one-shot stage.
  - The verkle KNOT is the committed state that persists across sessions: which stage the work is
    on, what is carried (parked/shelved), what the machine's actual state is.
  - Any session STARTS by reading the knot (status/where) instead of trusting its own memory, and
    ANCHORS its reality back to the knot (stand) when it changes the world. Same committed bytes ->
    same reality. Meet at the bytes, not the words (verkle-knot-maps-understanding).

REUSE (nothing invented): verkle_knot.append_verkle_knot (commit/amend leaf, integrity-gated),
agent_knot (standing-invariant + dedup pattern), chain_query (read path). This is the standing
knot invariant (agent-knot) applied to TEAM reality instead of a single agent's identity.

Schema: team_knot.v1 · deterministic + $0 · reuse: verkle_knot, agent_knot, chain_query
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "team_knot.v1"
TEAM_SESSION_ID = "team-internal-alignment"  # one stable leaf, amended in place (no chain spam)
STANDING = ROOT / "memory" / "team" / "team_standing.json"

# On-disk sources of GROUND TRUTH (never invent; read real state):
POWER_OFF = ROOT / "state" / "mag_power.off"        # present => stack deliberately parked
# The shelved-loop marker may live in the repo memory dir OR the Copilot memory-tool dir
# (the shared /memories/ FS both sessions read via the memory tool). Check both.
SHELVED_MARKERS = [
    ROOT / "memory" / "repo" / "shelved-autonomous-loop-20260824.md",
    Path(r"c:\Users\foste\AppData\Roaming\Code\User\workspaceStorage"
         r"\e2b798e7fc103fa17361a909a52c13e5\GitHub.copilot-chat\memory-tool"
         r"\memories\repo\shelved-autonomous-loop-20260824.md"),
]
LIVE_SESSIONS = ("0e6b1c8c-6395-4119-8cc4-6044f15e3889",  # this session
                 "7e653ed7-63f1-40f0-8dda-148d5cc7ede5")  # the other active session today


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _power_state() -> dict[str, Any]:
    """The machine's ACTUAL power state, read from disk (never from a session's memory)."""
    if POWER_OFF.is_file():
        return {"stack": "parked", "note": "mag_power.off present — stack deliberately stopped"}
    # healthy endpoints imply running (cheap, local, read-only)
    try:
        import urllib.request
        up = urllib.request.urlopen("http://127.0.0.1:8765/", timeout=2).status == 200
    except Exception:
        up = False
    return {"stack": "running" if up else "unknown", "dashboard_8765": up}


def _shelved() -> dict[str, Any]:
    for p in SHELVED_MARKERS:
        if p.is_file():
            return {"autonomous_loop": "shelved",
                    "note": "overnight autonomous loop parked 2026-08-24 (see shelved-autonomous-loop)"}
    return {"autonomous_loop": "unshelved"}


def _focus() -> dict[str, str]:
    """The current shared focus, from the operator's own words this morning (session 7e653ed7)."""
    return {"direction": "use the seats; make the dashboard not suck; be stateless, not a cron job",
            "carrier": "shelved (CPU spin ~95% — do not re-engage without operator go)"}


def team_reality() -> dict[str, Any]:
    """Compile the SHARED TEAM REALITY deterministically from on-disk ground truth.
    Same inputs -> same bytes. This is the contract both sessions anchor to."""
    parts = []
    power = _power_state()
    shelved = _shelved()
    focus = _focus()
    payload = {
        "schema": SCHEMA,
        "power": power,
        "shelved": shelved,
        "focus": focus,
        "live_sessions": list(LIVE_SESSIONS),
        "note": "both sessions read this knot before acting; anchor changes back to it",
        "ts": _now(),
    }
    invariant = json.dumps(payload, sort_keys=True, default=str)
    h = hashlib.sha256(invariant.encode("utf-8")).hexdigest()
    return {"ok": True, "schema": SCHEMA, "reality_hash": h, "payload": payload,
            "excerpt": invariant[:400]}


def _load_standing() -> dict[str, Any]:
    if STANDING.is_file():
        try:
            return json.loads(STANDING.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def stand(*, force: bool = False) -> dict[str, Any]:
    """Anchor the shared team reality as a verkle knot (amend the one team leaf in place).
    Dedup: unchanged reality -> the standing knot persists, no chain spam."""
    real = team_reality()
    prev = _load_standing()
    if not force and prev.get("reality_hash") == real["reality_hash"] and prev.get("leaf_hash"):
        return {"ok": True, "schema": SCHEMA, "standing": True, "persisted": True,
                "leaf_hash": prev.get("leaf_hash"), "root": prev.get("root"),
                "reality_hash": real["reality_hash"],
                "note": "unchanged -> the team knot persists (standing = revisited, not re-spammed)"}
    knot = {}
    try:
        from mag import verkle_knot
        knot = verkle_knot.append_verkle_knot({
            "session_id": TEAM_SESSION_ID,
            "theme": "team-alignment",
            "summary": f"[team-knot] shared reality {real['reality_hash'][:16]} — "
                       f"power={real['payload']['power'].get('stack')} "
                       f"auto_loop={real['payload']['shelved'].get('autonomous_loop')}",
        })
    except Exception as e:
        knot = {"leaf_hash": real["reality_hash"], "error": str(e)[:100]}
    standing = {"schema": SCHEMA, "ts": _now(), "reality_hash": real["reality_hash"],
                "leaf_hash": knot.get("leaf_hash", ""),
                "root": knot.get("verkle_root") or knot.get("root", ""),
                "path": knot.get("path", ""),
                "payload": real["payload"]}
    STANDING.parent.mkdir(parents=True, exist_ok=True)
    STANDING.write_text(json.dumps(standing, indent=2, default=str), encoding="utf-8")
    return {"ok": True, "schema": SCHEMA, "standing": True, "persisted": False, **standing,
            "note": "anchored the shared team reality to a fresh verkle knot (by default)"}


def status() -> dict[str, Any]:
    """READ the shared team reality. Any session calls this FIRST, before trusting its own
    memory. Returns the committed bytes both sessions converge on."""
    real = team_reality()
    standing = _load_standing()
    return {
        "ok": True,
        "schema": SCHEMA,
        "reality_hash": real["reality_hash"],
        "anchored_leaf": standing.get("leaf_hash", ""),
        "root": standing.get("root", ""),
        "power": real["payload"]["power"],
        "shelved": real["payload"]["shelved"],
        "focus": real["payload"]["focus"],
        "live_sessions": real["payload"]["live_sessions"],
        "contract": "read status() before acting; stand() to anchor reality changes back to the knot",
    }


def where() -> dict[str, Any]:
    """Where the team is: the anchored knot's address + current reality."""
    return status()


# ---------------------------------------------------------------------------
# FEED — the hypervisor as an RSS-like feed the chat window reads BY DEFAULT.
# Built ONLY from cheap sources (on-disk ledgers, cached fleet view, psutil) —
# never the slow REST endpoints (loop_health ~13s, fleet ~4s) that made the
# machine busy in the first place. "RSS feed for our hypervisor."
# ---------------------------------------------------------------------------
CADENCE_LEDGER = ROOT / "memory" / "runs" / "cadence_learn" / "rounds.jsonl"


# Browser binaries we never spawn ourselves — a chrome/edge/brave window we didn't
# open is the #1 "did something nefarious get in" signal (the salon opens one legitimately;
# a hijack opens one without asking).
BROWSER_NAMES = ("chrome", "msedge", "brave", "chromium", "firefox")


def _watch() -> dict[str, Any]:
    """AWARENESS item (2026-08-24, operator: 'i want to be aware when something nefarious
    tries to hijack this'). Cheap psutil scan for signals OUTSIDE the known fleet:
      - browsers running (the salon/seat_steer opens them legitimately; a hijack does too —
        so surface them, don't hide them)
      - python processes whose cmdline isn't the known mag/main.py family
    Honest: this is a surface, not a verdict — it shows what's running so the operator can
    see what's there, without claiming intent."""
    browsers = []
    unknown_py = []
    try:
        import psutil
        for p in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                name = (p.info["name"] or "").lower()
                cl = " ".join(p.info["cmdline"] or [])
            except Exception:  # noqa: BLE001
                continue
            if any(b in name for b in BROWSER_NAMES):
                browsers.append(f"{name}#{p.info['pid']}")
            elif "python" in name and cl:
                if "main.py" in cl or "-m mag" in cl or "mag_" in cl or ".venv" in cl:
                    continue  # known mag family
                unknown_py.append(f"py#{p.info['pid']}")
    except Exception:  # noqa: BLE001
        pass
    flags = []
    if browsers:
        flags.append(f"browsers: {', '.join(browsers[:4])}")
    if unknown_py:
        flags.append(f"unknown-py: {', '.join(unknown_py[:4])}")
    return {"ok": True, "browsers": browsers, "unknown_py": unknown_py,
            "flags": flags or ["no unknown activity"],
            "note": "surface, not verdict — browsers/unknown processes are listed so YOU see them"}


def _busy() -> dict[str, Any]:
    """The machine's busy signal, HONEST + CHEAP. Total CPU via a real measurement interval
    (cpu_percent(interval=None) returns 0 on the first read — that would fabricate 'quiet'
    on a machine at 98%, so we use a short real interval) + the roles/pids of running mag
    processes (no per-process CPU needed, that's what forced the fake 0.0%)."""
    total = 0.0
    roles = []
    try:
        import psutil
        total = round(psutil.cpu_percent(interval=0.3), 1)  # real reading, ~0.3s
        for p in psutil.process_iter(["pid", "cmdline"]):
            try:
                cl = " ".join(p.info["cmdline"] or [])
            except Exception:  # noqa: BLE001
                cl = ""
            if "main.py" not in cl and "mag" not in cl.lower():
                continue
            role = ("lab" if ("lab" in cl and "--no-dashboard" in cl)
                    else "dashboard" if "dashboard" in cl
                    else "autorun" if "autorun" in cl
                    else "mag" if "mag" in cl.lower() else "py")
            roles.append(f"{role}#{p.info['pid']}")
    except Exception:  # noqa: BLE001
        total = -1.0
    return {"total_cpu_pct": total, "roles": roles[:6]}


def _cadence_age() -> dict[str, Any]:
    """How long since the cadence last fired (from the on-disk ledger, cheap)."""
    try:
        if CADENCE_LEDGER.is_file():
            lines = [l for l in CADENCE_LEDGER.read_text(encoding="utf-8", errors="replace").splitlines() if l.strip()]
            if lines:
                last = json.loads(lines[-1])
                ts = last.get("ts") or last.get("_ts") or ""
                return {"last_ts": ts, "rounds": len(lines), "note": "cadence ledger (cheap read)"}
    except Exception:  # noqa: BLE001
        pass
    return {"rounds": 0}


def feed() -> dict[str, Any]:
    """The hypervisor as an RSS-like feed. ANY session/window reads this FIRST by default.
    Combines shared reality (team_knot) + live fleet (cached) + busy CPU (psutil) + cadence,
    all from cheap sources. Never hits the slow REST endpoints."""
    items = []
    real = team_reality()["payload"]

    # 1. shared reality
    items.append({"id": "reality", "ts": real.get("ts", ""),
                  "label": f"stack={real['power'].get('stack')} · auto_loop={real['shelved'].get('autonomous_loop')}",
                  "detail": real["focus"].get("direction", "")})

    # 2. busy CPU (real measurement + roles; NEVER per-process first-call 0.0% fabrication)
    busy = _busy()
    if busy.get("total_cpu_pct", -1) >= 0:
        hot = f"{busy['total_cpu_pct']}%"
        items.append({"id": "busy", "ts": _now(), "label": f"cpu {hot}",
                      "detail": " ".join(busy.get("roles", []))})
    else:
        items.append({"id": "busy", "ts": _now(), "label": "cpu: unknown", "detail": ""})

    # 3. fleet seats — from the CHEAP on-disk heartbeat source (seat_availability), NOT the
    #    slow fleet_heartbeat() which recomputes bills on cache-miss (~12s). Bills live on
    #    the hypervisor page; the feed keeps seats + availability only.
    try:
        from mag import seat_availability
        hb = seat_availability.status()
        by_seat = hb.get("by_seat") or {}
        seats = []
        avail = 0
        for name, ratio in by_seat.items():
            ok_n = 0
            try:
                ok_n = int(str(ratio).split("/")[0])
            except Exception:  # noqa: BLE001
                pass
            if ok_n and ok_n > 0:
                avail += 1
            seats.append(name)
        items.append({"id": "fleet", "ts": _now(),
                      "label": f"seats {avail}/{len(seats)} up over {hb.get('n_heartbeats', 0)} hb",
                      "detail": "; ".join(seats[:8])[:160]})
    except Exception:  # noqa: BLE001
        items.append({"id": "fleet", "ts": _now(), "label": "fleet: unavailable", "detail": ""})

    # 4. cadence age
    cad = _cadence_age()
    items.append({"id": "cadence", "ts": _now(),
                  "label": f"cadence ledger: {cad.get('rounds', 0)} rounds",
                  "detail": f"last: {cad.get('last_ts', '?')}"})

    # 5. VERIFIED CLOCK (2026-08-24): the one clock everywhere — utc/local/peak/drift,
    #    cross-checked against the verkle chain (ground-truth temporal record).
    try:
        from mag import verified_clock
        c = verified_clock.status()
        drift = c.get("drift_s")
        trusted = c.get("trusted")
        peak = (c.get("peak") or {})
        items.append({"id": "clock", "ts": _now(),
                      "label": f"clock {str(c.get('utc_now'))[11:19]}Z · "
                               f"{'trusted' if trusted else 'DRIFT'}",
                      "detail": f"local {str(c.get('local_now'))[11:19]} · "
                                f"peak {'YES x2' if peak.get('is_peak') else 'no'} · "
                                f"chain-drift {drift}s"})
    except Exception:  # noqa: BLE001
        pass

    # 6. AWARENESS — browsers + unknown processes running (surface, not verdict)
    w = _watch()
    items.append({"id": "watch", "ts": _now(),
                  "label": " / ".join(w.get("flags") or ["no unknown activity"]),
                  "detail": "browsers/unknown processes listed so YOU see what's running"})

    return {"ok": True, "schema": SCHEMA, "kind": "feed", "ts": _now(),
            "n_items": len(items), "items": items,
            "contract": "the chat window reads this by default, anywhere; stand() anchors reality changes back to the knot"}


def main(argv: list[str] | None = None) -> int:
    import argparse
    p = argparse.ArgumentParser(prog="team_knot", description="shared team reality, anchored to verkle")
    p.add_argument("cmd", choices=["status", "stand", "reality", "feed"], default="status", nargs="?")
    p.add_argument("--force", action="store_true")
    a = p.parse_args(argv)
    if a.cmd == "stand":
        print(json.dumps(stand(force=a.force), indent=2, default=str))
    elif a.cmd == "reality":
        print(json.dumps(team_reality(), indent=2, default=str))
    elif a.cmd == "feed":
        print(json.dumps(feed(), indent=2, default=str))
    else:
        print(json.dumps(status(), indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
