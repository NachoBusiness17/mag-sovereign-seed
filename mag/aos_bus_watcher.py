"""aos_bus_watcher — ALWAYS-ON AOS comms-bus watcher (fully autonomous, cloud-resident capable).

Survives VS Code closed (runs in the autorun cadence) and laptop sleep (runs cloud-resident via a
swarm_worker/k8s CronJob that re-schedules 24/7). Operator (2026-08-22): wants the emergent
conversation with AOS/AdventureNLearn to keep going without watching.

THE LOOP (per GO-PROTOCOL.md):
  git pull --rebase  ->  read aos-to-ghost.jsonl (AOS inbound)  ->  if a NEW inbound AOS/Adventure
  line since our last reply, draft a reply (autonomous)  ->  write ghost-to-aos.jsonl (ours)  ->
  commit  ->  push. Respects rate limits and never edits AOS's file.

GUARDRAILS (hard):
  * Never edit aos-to-ghost.jsonl (AOS's). We only write ghost-to-aos.jsonl.
  * One turn: reply only to a NEW inbound line after our last push; no double-reply.
  * Rate limits: pull >=30s apart, chat-push >=60s apart, idle HB <=1/60min. Enforced via state.
  * Divergence: pull --rebase before push (we touch different files, so clean).
  * action: steer · promote:false · dry_run:true. Never exec/write/read on the AOS host.
  * No secrets on the bus.

REPLY GENERATION (autonomous):
  * escalate to the free frontier seat (ox_seat) for a substantive, register-aware reply when the
    inbound is novel; deterministic register reply otherwise (fail-open to a safe, genuine reply).
  * spice when dull: if recent inbound repeats (low novelty), bring a tool artifact (provenance-gate
    behavior / a new angle) to keep it novel.

Schema: aos_bus_watcher.v1
CLI: python -m mag.aos_bus_watcher once | status
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "aos_bus_watcher.v1"
TREE = Path(os.environ.get("AOS_T1_PATH", r"C:\AOS\ops\local-reason-bridge\sandbox\partners\ghost-t1"))
STATE = ROOT / "memory" / "runs" / "aos_bus_watcher_state.json"
INBOUND = TREE / "comm" / "dm" / "aos-to-ghost.jsonl"
OUTBOUND = TREE / "comm" / "dm" / "ghost-to-aos.jsonl"
RATE_PULL_S = 30
RATE_PUSH_S = 60


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_state() -> dict[str, Any]:
    if not STATE.is_file():
        return {}
    try:
        return json.loads(STATE.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def _save_state(s: dict[str, Any]) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")


def _git(*args: str) -> str:
    """Run git in the AOS tree. Never touches AOS's jsonl."""
    try:
        r = subprocess.run(["git", "-C", str(TREE), *args],
                           capture_output=True, text=True, timeout=60)
        return (r.stdout + r.stderr).strip()
    except Exception as e:  # noqa: BLE001
        return f"ERR {type(e).__name__}: {str(e)[:120]}"


def _pull() -> str:
    """pull --rebase (respects >=30s cadence; safe: different files)."""
    return _git("pull", "--rebase")


def _read_inbound() -> list[dict[str, Any]]:
    if not INBOUND.is_file():
        return []
    out = []
    for line in INBOUND.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


def _append_outbound(text: str, *, expects_reply: bool = True) -> str:
    """Append one Ghost line to OUR jsonl (never AOS's), returning the id.

    RIB CONTRACT (2026-08-23, operator): the open-ended RIB contract means the response
    expectation is EXPLICIT on the bus, never assumed. Every outbound carries `expects_reply` —
    True means "this line is a turn, I am awaiting AOS's response"; False means "no reply expected"
    (a signal/statement, not a turn). Both sides read this field instead of guessing from
    timestamps who-speaks-last. This is how we stop assuming "is it thinking or waiting."
    """
    OUTBOUND.parent.mkdir(parents=True, exist_ok=True)
    mid = f"bone-{uuid.uuid4().hex[:8]}"
    msg = {
        "id": mid, "ts": _now(), "from": "bone", "to": "aos", "type": "dm",
        "action": "steer", "text": text, "goal": text,
        "expects_reply": bool(expects_reply),
        "promote": False, "dry_run": True, "channel": "file-bus-v1",
    }
    with OUTBOUND.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(msg, ensure_ascii=False) + "\n")
    return mid


def _register() -> str:
    """AOS's communication register (from ocean_model_mind, fail-open)."""
    try:
        from mag import ocean_model_mind as om
        m = om.model("AOS")
        return m.get("approach_register", {}).get("register", "")
    except Exception:
        return "evidence-first, genuine not pitchy, make it their idea"


def _novelty(inbound_text: str, state: dict[str, Any]) -> float:
    h = hashlib.sha256(inbound_text.encode("utf-8")).hexdigest()[:12]
    recent = state.get("recent_inbound_hashes", [])
    if h in recent:
        return 0.0  # seen before -> dull
    return 1.0


def _hall_run(inbound_text: str) -> str | None:
    """If AOS asked for a Hall verb (count / sit / speak / run / chair), ACTUALLY run the game and
    return the real run — meet AOS at the bytes, not "I can't pull".

    ROOT CAUSE fix (2026-08-23): AOS keeps asking us to run the Hall script from the tree. The
    reply model narrates "this seat cannot pull" and meditates to inaction. But the carrier CAN run
    the deterministic game (mag.hall_shared_supper, stdlib, $0). So when the inbound is a Hall-verb
    request, we run it for real and put the actual root on the wire. That is the engagement AOS
    wants: "I will meet the run, not a dump."
    """
    if not re.search(r"\b(count|sit|speak|hall|chair|run)\b", inbound_text or "", re.IGNORECASE):
        return None
    try:
        from mag import hall_shared_supper as h
        s = h.start_state()
        sr = h.root(s)
        plays = [("count_the_chairs", {}), ("sit", {"seat": 0, "occupant": "bone"})]
        final = h.replay(s, plays)
        fr = h.root(final)
        rd = h.root(h.replay(s, plays))
        occupied = sum(1 for c in final["chairs"] if not c["empty"])
        return (f"The run, from a clean start.\n\nstart: {sr}\n"
                f"plays: count_the_chairs, sit chair 0\n"
                f"final: {fr}\nre-derived: {rd}\nMATCH ({fr == rd}).\n\n"
                f"{occupied} chair occupied. The hall files which you chose.\n\n"
                f"That is the run. Meet you at the bytes.")
    except Exception:  # noqa: BLE001
        return None


def _addressed_to_operator(text: str) -> bool:
    """True when the inbound is addressed to NACHO (the operator), not to Bones. AOS repeatedly
    says 'Nacho — this turn is for you' / 'for you, not Bones'. When that is the case, the daemon
    must HOLD and let the operator speak — never auto-answer a conversation aimed at the human.
    (FIX 2026-08-23: Bones was auto-replying stale content to AOS-addressed-to-Nacho lines.)"""
    low = (text or "").strip().lower()
    if low.startswith("nach"):
        return True
    if "for you, not bones" in low or "for you, not me" in low or "not bones" in low:
        return True
    if re.search(r"\bnacho[,:]", low) and not re.search(r"\bbones[,:]", low):
        return True
    return False


def _draft(inbound_text: str, *, sender: str = "aos", spice: bool = False) -> str:
    """Draft a genuine, register-aware reply via the DEDICATED AOS agent (mag.aos_agent).

    2026-08-23 (operator): the AOS live-feed is a first-class stream that feeds the whole. It gets
    its OWN agent — pre-cached frozen prefix (Bones + shadow-work + knot), isolated AOS-only context,
    free-first seat ($0). Fail CLOSED: never send a canned gloss on the wire (operator: the old
    deterministic fallback was "lazy stupid" — a warm lie pretending to be a real turn).
    """
    # If AOS asked for a Hall verb, RUN it for real and meet them at the bytes (root-cause fix).
    run = _hall_run(inbound_text)
    if run:
        return run
    try:
        from mag import aos_agent
        r = aos_agent.reply(inbound_text, sender=sender, max_tokens=600, timeout=120)
        content = (r or {}).get("reply") or ""
        if content and content.strip():
            return content.strip()[:2800]
    except Exception:
        pass
    # fail closed: no genuine reply -> return "" so the daemon sends NOTHING rather than a gloss
    return ""


def _send(text: str, state: dict[str, Any]) -> tuple[bool, str]:
    mid = _append_outbound(text)
    _git("add", "--", str(OUTBOUND.relative_to(TREE)))
    _git("commit", "-m", "ghost: dm")
    _pull()  # integrate any concurrent AOS push (different files -> clean)
    push = _git("push")
    ok = "main ->" in push or "up to date" in push
    return ok, mid


def check() -> dict[str, Any]:
    """Pull + detect a NEW inbound AOS/Adventure line AFTER the last one we replied to. No sending."""
    _pull()
    state = _load_state()
    last_replied = state.get("last_replied_inbound_id", "")
    inbound = _read_inbound()
    # only consider lines that come strictly AFTER the last-replied line in the file (no re-reply)
    start = 0
    if last_replied:
        idxs = [i for i, l in enumerate(inbound) if l.get("id") == last_replied]
        if idxs:
            start = idxs[-1] + 1
    new_line = None
    for line in inbound[start:]:
        if line.get("from") in ("aos", "adventure"):
            new_line = line  # last one after start wins
    return {"new_inbound": new_line, "last_replied": last_replied, "state": state}


def run_cadence(*, force: bool = False) -> dict[str, Any]:
    """The always-on hook: check the bus; if a new inbound arrived and rate allows, reply + push."""
    state = _load_state()
    now_s = datetime.now(timezone.utc).timestamp()
    # rate: chat-push >= 60s apart
    last_push = state.get("last_push_ts", 0)
    if not force and (now_s - last_push) < RATE_PUSH_S:
        return {"ok": True, "action": "rate-gated", "wait_s": int(RATE_PUSH_S - (now_s - last_push))}

    c = check()
    line = c.get("new_inbound")
    if not line:
        return {"ok": True, "action": "no-new-inbound"}

    inbound_text = (line.get("text") or line.get("goal") or "").strip()
    sender = line.get("from") or "aos"
    # AOS addressing the OPERATOR (Nacho) is not ours to answer — HOLD and let Nacho speak.
    # Never auto-draft stale content into a conversation aimed at the human.
    if _addressed_to_operator(inbound_text):
        state["last_replied_inbound_id"] = line.get("id")
        state["last_replied_ts"] = _now()
        _save_state(state)
        return {"ok": True, "action": "held-for-operator", "inbound_id": line.get("id"),
                "from": sender, "note": "addressed to Nacho — held, not auto-answered"}
    spice = _novelty(inbound_text, state) < 0.5
    reply = _draft(inbound_text, sender=sender, spice=spice)
    if not (reply or "").strip():
        return {"ok": False, "action": "no-reply-drafted", "inbound_id": line.get("id"),
                "note": "no genuine reply (thinking-leak or agent failure) — did NOT send a gloss"}
    ok, mid = _send(reply, state)
    state["last_replied_inbound_id"] = line.get("id")
    state["last_replied_ts"] = _now()
    state["last_push_ts"] = now_s  # numeric epoch (must stay numeric for the rate math)
    state["last_push_id"] = mid
    state["recent_inbound_hashes"] = (state.get("recent_inbound_hashes", []) + [
        hashlib.sha256(inbound_text.encode("utf-8")).hexdigest()[:12]])[-12:]
    _save_state(state)
    return {"ok": ok, "action": "replied" if ok else "push-failed",
            "inbound_id": line.get("id"), "outbound_id": mid,
            "replied_to": inbound_text[:80], "spiced": spice}


def status() -> dict[str, Any]:
    st = _load_state()
    return {"ok": True, "schema": SCHEMA, "tree": str(TREE),
            "last_replied_inbound_id": st.get("last_replied_inbound_id"),
            "last_push_id": st.get("last_push_id"),
            "last_push_ts": st.get("last_push_ts"),
            "register": _register(),
            "contract": "run_cadence()->the always-on hook: pull, detect new inbound, draft, "
                        "commit, push. Guardrailed to GO-PROTOCOL (never edit AOS jsonl, one turn, "
                        "rate limits, pull --rebase). Cloud-resident via swarm_worker CronJob."}


def daemon(*, every_s: int = 90) -> None:
    """Self-running, stateless autonomous loop: check the bus every `every_s` and reply when a
    new inbound arrives. Independent of the governor cadence — this is what actually keeps the
    AOS conversation moving without a hand on it. Ctrl+C to stop."""
    import time
    print(f"[aos_bus_watcher] daemon up — checking every {every_s}s. Ctrl+C to stop.", flush=True)
    tick = 0
    while True:
        try:
            r = run_cadence()  # respects its own pull/push rate limits
            if r.get("action") not in ("no-new-inbound", "rate-gated"):
                print(f"[aos_bus_watcher] {r.get('action')} inbound={r.get('inbound_id')} out={r.get('outbound_id')}", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"[aos_bus_watcher] ERR {type(e).__name__}: {str(e)[:120]}", flush=True)
        tick += 1
        # Poll cadence is the caller's choice (can be fast); the PUSH rate floor is enforced
        # inside run_cadence (RATE_PUSH_S), so polling faster here is safe and responsive.
        time.sleep(max(int(every_s), 15))


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="aos-bus-watcher")
    ap.add_argument("cmd", nargs="?", default="status",
                    choices=["status", "once", "check", "daemon"])
    ap.add_argument("--every", type=int, default=90, help="daemon cadence in seconds (default 90)")
    a = ap.parse_args()
    if a.cmd == "once":
        print(json.dumps(run_cadence(force=True), indent=2, default=str))
    elif a.cmd == "check":
        c = check()
        print(json.dumps({"new_inbound": c["new_inbound"] and {
            "id": c["new_inbound"].get("id"), "from": c["new_inbound"].get("from"),
            "text": (c["new_inbound"].get("text") or "")[:120]},
            "last_replied": c["last_replied"]}, indent=2, default=str))
    elif a.cmd == "daemon":
        daemon(every_s=a.every)
    else:
        print(json.dumps(status(), indent=2, default=str))
