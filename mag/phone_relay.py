"""phone_relay — approvals from the operator's phone, through the Mag DM.

Law (2026-09-24, operator GO): no estate gate may hold work hostage to the
operator's physical location. Pending approvals travel to his phone over the
private Mag DM lane; his reply is the decision. Fail-closed everywhere:

  - timeout = DENY (never approve by silence)
  - replies count only from DISCORD_ALLOWED_USERS in the DM (never a shared channel)
  - pinned host: api.discord.com over https, redirects refused (SSRF law)
  - kill switch: PHONE_RELAY=off env or PHONE_RELAY_OFF=1 => immediate deny
  - rate cap: max 12 asks/hour
  - every ask and reply is appended to watch/inbox/phone_relay_log.jsonl
  - the token is never logged or printed (last 4 only)

CLI:
  python mag/phone_relay.py ask "promote X?" [--timeout 600]   exit 0 approve / 1 deny
  python mag/phone_relay.py test                               post + read-back, no decision
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / "watch" / "inbox" / "phone_relay_log.jsonl"

HERMES_ENV = Path(os.environ.get("LOCALAPPDATA", "")) / "hermes" / ".env"
STATE = ROOT / "state" / "phone_relay_channel.json"  # cached DM channel id
# api.discord.com went NODATA (no A/AAAA/HTTPS records at Cloudflare authority)
# on 09-24; discord.com is the documented alternative REST base and resolves fine.
API_HOST = "discord.com"
APPROVE_WORDS = {"y", "yes", "approve", "1", "👍", "✅"}
DENY_WORDS = {"n", "no", "deny", "2", "👎", "❌"}


def _decide(words: str) -> str | None:
    """Exact-token decision (found by the seed sweep 09-25: substring 'y' approved
    the literal reply 'deny'). approve/deny both present or neither = keep waiting;
    ambiguity = deny."""
    tokens = {w.strip('.,!?;:"\'') for w in words.split()}
    a, d = bool(tokens & APPROVE_WORDS), bool(tokens & DENY_WORDS)
    if a and d:
        return "deny"
    if a:
        return "approve"
    if d:
        return "deny"
    return None
MAX_ASKS_PER_HOUR = 12

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

sys.path.insert(0, str(ROOT))


def _token() -> str:
    """Read DISCORD_BOT_TOKEN from the hermes env file. Never log the value."""
    if not HERMES_ENV.is_file():
        raise RuntimeError(f"hermes env not found: {HERMES_ENV}")
    for line in HERMES_ENV.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("DISCORD_BOT_TOKEN="):
            val = line.split("=", 1)[1].strip().strip('"')
            if val:
                return val
    raise RuntimeError("DISCORD_BOT_TOKEN not present in hermes env")


def _allowed_users() -> set[str]:
    """Human user ids that may decide. From hermes env, so it stays in one place.
    Missing env file = nobody may decide (fail closed, readable)."""
    if not HERMES_ENV.is_file():
        return set()
    for line in HERMES_ENV.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("DISCORD_ALLOWED_USERS="):
            return {u.strip() for u in line.split("=", 1)[1].split(",") if u.strip()}
    return set()


def _api(method: str, path: str, body: dict | None = None, timeout: int = 15) -> dict:
    """The one outbound door: pinned host, https, no redirects, bot auth."""
    tok = _token()
    url = f"https://{API_HOST}/api/v10{path}"
    if urllib.parse.urlsplit(url).hostname != API_HOST:
        raise RuntimeError("SSRF guard: pinned host violated")
    req = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body else None,
                                 headers={"Authorization": f"Bot {tok}", "Content-Type": "application/json",
                                          "User-Agent": "DiscordBot (https://nacho.business, 1.0) phone_relay/1.0"})

    class _Refuse(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
            raise RuntimeError("SSRF guard: redirect refused")

    opener = urllib.request.build_opener(_Refuse)
    with opener.open(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace") or "{}")


def _log(row: dict) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    row["ts"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _rate_ok() -> bool:
    if not LOG.is_file():
        return True
    hour_ago = time.time() - 3600
    n = 0
    for line in LOG.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            if json.loads(line).get("ts", "") and _ts_epoch(line) > hour_ago:
                n += 1
        except Exception:
            continue
    return n < MAX_ASKS_PER_HOUR


def _ts_epoch(line: str) -> float:
    import datetime
    ts = json.loads(line).get("ts", "")
    return datetime.datetime.fromisoformat(ts).timestamp() if ts else 0.0


def _off() -> bool:
    return os.environ.get("PHONE_RELAY", "").lower() == "off" or os.environ.get("PHONE_RELAY_OFF") == "1"


def _dm_channel() -> str:
    """The private DM with the operator. Cached; self-heals by re-opening the
    DM with each allowed user when the cached id goes stale (10003 Unknown
    Channel). Never a shared guild channel — approvals are one-human only."""
    if STATE.is_file():
        cached = STATE.read_text(encoding="utf-8").strip()
        if cached:
            try:
                _api("GET", f"/channels/{cached}")
                return cached
            except Exception:
                pass
    for uid in sorted(_allowed_users()):
        try:
            ch = _api("POST", "/users/@me/channels", {"recipient_id": uid})
            cid = str(ch.get("id", ""))
            if cid:
                STATE.parent.mkdir(parents=True, exist_ok=True)
                STATE.write_text(cid, encoding="utf-8")
                return cid
        except Exception:
            continue
    raise RuntimeError("could not open a DM channel with any allowed user")


def ask(prompt: str, timeout_s: int = 600, source: str = "") -> dict:
    """Post an approval card to the DM, wait for the operator's reply. Fail closed."""
    if _off():
        _log({"kind": "ask", "decision": "deny", "why": "kill-switch", "prompt": prompt[:200]})
        return {"ok": False, "decision": "deny", "why": "PHONE_RELAY kill switch is on"}
    if not _rate_ok():
        _log({"kind": "ask", "decision": "deny", "why": "rate-cap", "prompt": prompt[:200]})
        return {"ok": False, "decision": "deny", "why": f"rate cap {MAX_ASKS_PER_HOUR}/hour"}

    card = (f"🛂 **ESTATE APPROVAL NEEDED**\n{prompt}\n"
            f"Reply **APPROVE** or **DENY** (👍/👎 works). "
            f"Timeout {timeout_s // 60} min = DENY.\n"
            f"_{source or 'estate'} · {time.strftime('%H:%M:%S')}_")
    msg = _api("POST", f"/channels/{_dm_channel()}/messages", {"content": card})
    msg_id = msg.get("id", "?")
    _log({"kind": "ask", "msg_id": msg_id, "prompt": prompt[:200], "timeout_s": timeout_s})

    users = _allowed_users()
    deadline = time.time() + timeout_s
    seen: set[str] = set()
    while time.time() < deadline:
        time.sleep(5)
        # Decisions arrive two ways: a reply message, or a reaction ON the card
        # (the natural phone gesture — the 09-24 live-fire test sat unanswered
        # in exactly the state a reaction would have resolved).
        try:
            card_now = _api("GET", f"/channels/{_dm_channel()}/messages/{msg_id}")
            for r in card_now.get("reactions", []) or []:
                name = r.get("emoji", {}).get("name", "")
                if name in APPROVE_WORDS or name in DENY_WORDS:
                    decision = "approve" if name in APPROVE_WORDS else "deny"  # emoji are single tokens
                    _log({"kind": "reply", "msg_id": msg_id, "decision": decision, "via": "reaction"})
                    stamp = "✅ approved (reaction) — executing." if decision == "approve" else "⛔ denied — standing down."
                    _api("POST", f"/channels/{_dm_channel()}/messages", {"content": stamp})
                    return {"ok": True, "decision": decision, "via": "reaction"}
        except Exception:
            pass
        rows = _api("GET", f"/channels/{_dm_channel()}/messages?limit=20&after={msg_id}")
        for m in rows if isinstance(rows, list) else []:
            mid, author = str(m.get("id", "")), m.get("author", {})
            if mid in seen or author.get("bot") or str(author.get("id", "")) not in users:
                continue
            seen.add(mid)
            words = (m.get("content", "") or "").strip().lower()
            decision = _decide(words)
            if decision:
                _log({"kind": "reply", "msg_id": mid, "decision": decision, "reply": words[:100]})
                stamp = (f"✅ approved — executing. (`{words[:40]}`)" if decision == "approve"
                         else "⛔ denied — standing down.")
                _api("POST", f"/channels/{_dm_channel()}/messages", {"content": stamp})
                return {"ok": True, "decision": decision, "reply": words}
    _log({"kind": "reply", "decision": "deny", "why": "timeout"})
    _api("POST", f"/channels/{_dm_channel()}/messages", {"content": "⌛ timed out — **DENY** by law (fail closed)."})
    return {"ok": False, "decision": "deny", "why": "timeout (fail closed)"}


def test() -> dict:
    """Post a card and read the channel back. Proves token, lane, poll. No decision."""
    msg = _api("POST", f"/channels/{_dm_channel()}/messages",
               {"content": f"🧪 phone_relay self-test {time.strftime('%H:%M:%S')} — lane check, no reply needed."})
    rows = _api("GET", f"/channels/{_dm_channel()}/messages?limit=3")
    got = [str(m.get("id")) for m in rows if isinstance(rows, list)][:3]
    users = sorted(_allowed_users())
    ok = str(msg.get("id")) in got
    _log({"kind": "test", "ok": ok, "msg_id": msg.get("id", "?"), "allowed_users": len(users)})
    return {"ok": ok, "posted": str(msg.get("id")), "readback": got,
            "allowed_users_count": len(users), "token_last4": _token()[-4:]}


if __name__ == "__main__":
    args = sys.argv[1:]
    try:
        if args and args[0] == "test":
            print(json.dumps(test(), indent=1))
            sys.exit(0)
        if args and args[0] == "ask":
            prompt = args[1] if len(args) > 1 else "unnamed approval?"
            timeout = 600
            if "--timeout" in args:
                timeout = int(args[args.index("--timeout") + 1])
            out = ask(prompt, timeout_s=timeout, source="cli")
            print(json.dumps(out, indent=1))
            sys.exit(0 if out.get("decision") == "approve" else 1)
    except RuntimeError as e:  # readable failure, never a traceback (seed law)
        print(json.dumps({"ok": False, "error": str(e)[:200]}, indent=1))
        sys.exit(1)
    print(__doc__)
    sys.exit(2)
