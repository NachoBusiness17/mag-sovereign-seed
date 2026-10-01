"""lane_supervisor — no lane dies quietly, no lane needs a babysitter (2026-09-25,
operator: "i have to babysit the lane otherwise it errors out — this is my complaint").

Every configured lane gets a cheap probe. State machine per lane:
  UP -> (fail) FLAKING -> (3 consecutive fails) DOWN -> (pass again) RECOVERED
Failover: each lane class names its fallback chain; a DOWN lane's class is served
by the next live lane in the chain. Escalation to the operator's phone happens ONLY
when a lane is DOWN and no failover exists in its class — a decision, not a task.
Every state change appends to state/fuel/lane_health.jsonl (the receipt trail).

CLI:
  python mag/lane_supervisor.py probe     # one round, exit 0 if all healthy
  python mag/lane_supervisor.py status    # human table of lane states
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from models.env_load import load_dotenv
load_dotenv()
from mag import lite_guard  # noqa: E402
from mag.key_law import get  # noqa: E402

STATE = ROOT / "state" / "fuel" / "lane_health.jsonl"
DOWN_THRESHOLD = 3

# Lane classes: a class is served if ANY member is UP (failover chain).
# probe = a minimal real call. ping budget: 1 call, small tokens.
LANE_CLASSES: list[dict] = [
    {"class": "chat_cheap", "lanes": [
        {"name": "deepseek", "kind": "openai_chat",
         "url": "https://api.deepseek.com/chat/completions", "key_canon": "deepseek",
         "model": "deepseek-chat"},
        {"name": "groq_1", "kind": "openai_chat",
         "url": "https://api.groq.com/openai/v1/chat/completions", "key_canon": "groq_1",
         "model": "openai/gpt-oss-120b"},
        {"name": "groq_2", "kind": "openai_chat",
         "url": "https://api.groq.com/openai/v1/chat/completions", "key_canon": "groq_2",
         "model": "openai/gpt-oss-120b"},
        {"name": "together", "kind": "openai_chat",
         "url": "https://api.together.xyz/v1/chat/completions", "key_canon": "together",
         "model": "deepseek-ai/DeepSeek-V4-Flash-0731"},
    ]},
    {"class": "chat_free_wall", "lanes": [
        {"name": "openrouter_1", "kind": "openai_models",
         "url": "https://openrouter.ai/api/v1/models", "key_canon": "openrouter_1"},
        {"name": "openrouter_2", "kind": "openai_models",
         "url": "https://openrouter.ai/api/v1/models", "key_canon": "openrouter_2"},
    ]},
    {"class": "local_dialogue", "lanes": [
        {"name": "opencode_4096", "kind": "http_local",
         "url": "http://127.0.0.1:4096/global/health"},
    ]},
    {"class": "quota_meter", "lanes": [
        {"name": "zai_lite_meter", "kind": "quota_read"},
    ]},
]


def _open_local(url: str, timeout: int = 10):
    """The local door: http to loopback only, pinned by scheme+host, redirects refused.
    The local dialogue lane is local BY DESIGN; this makes that a checked fact, not a habit."""
    sp = urllib.parse.urlsplit(url)
    if sp.scheme != "http" or sp.hostname not in ("127.0.0.1", "localhost"):
        raise RuntimeError(f"local door refused non-local url: {url}")

    class _Refuse(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
            raise RuntimeError("local door: redirect refused")

    req = urllib.request.Request(url, headers={
        "Accept": "application/json", "User-Agent": "mag-estate-lane-supervisor/1.0"})
    with urllib.request.build_opener(_Refuse).open(req, timeout=timeout) as r:
        return r.status, r.read().decode("utf-8", "replace")


def _probe(lane: dict) -> tuple[bool, str]:
    kind = lane["kind"]
    try:
        if kind == "openai_chat":
            key = get(lane["key_canon"])
            if not key:
                return False, "no key"
            if not lite_guard._safe_https_url(lane["url"]):
                return False, "ssrf guard rejected url"
            body = json.dumps({"model": lane["model"], "messages": [
                {"role": "user", "content": "ping"}], "max_tokens": 5}).encode()
            req = urllib.request.Request(lane["url"], data=body, headers={
                "Authorization": f"Bearer {key}", "Content-Type": "application/json",
                "User-Agent": "mag-estate-lane-supervisor/1.0"})
            with lite_guard._OPENER.open(req, timeout=30) as r:
                out = json.loads(r.read().decode())
            content = (out.get("choices") or [{}])[0].get("message", {}).get("content", "")
            return (True, "ok") if content is not None else (False, "empty content")
        if kind == "openai_models":
            key = get(lane["key_canon"])
            if not key:
                return False, "no key"
            if not lite_guard._safe_https_url(lane["url"]):
                return False, "ssrf guard rejected url"
            req = urllib.request.Request(lane["url"], headers={
                "Authorization": f"Bearer {key}",
                "User-Agent": "mag-estate-lane-supervisor/1.0"})
            with lite_guard._OPENER.open(req, timeout=30) as r:
                out = json.loads(r.read().decode())
            n = len(out.get("data", []))
            return (True, f"catalog {n} models") if n else (False, "empty catalog")
        if kind == "http_local":
            status, _ = _open_local(lane["url"])
            return True, f"HTTP {status}"
        if kind == "quota_read":
            q = lite_guard.provider_quota(force=True)
            if q and q.get("weekly", {}).get("limit"):
                return True, f"weekly {q['weekly'].get('remaining')}/{q['weekly'].get('limit')}"
            return False, "quota read returned nothing"
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}"
    except Exception as e:  # noqa: BLE001
        return False, f"{type(e).__name__}: {str(e)[:80]}"
    return False, "unknown probe kind"


def _history() -> dict[str, dict]:
    """Per-lane consecutive-failure counters from the tail of the log."""
    streak: dict[str, dict] = {}
    if not STATE.is_file():
        return streak
    for line in STATE.read_text(encoding="utf-8", errors="replace").splitlines()[-200:]:
        try:
            row = json.loads(line)
        except Exception:
            continue
        n = row.get("name", "")
        if not n:
            continue
        st = streak.setdefault(n, {"fails": 0, "state": "UP"})
        if row.get("ok"):
            st["fails"] = 0
            st["state"] = "RECOVERED" if st["state"] in ("DOWN", "FLAKING") else "UP"
        else:
            st["fails"] += 1
            st["state"] = "DOWN" if st["fails"] >= DOWN_THRESHOLD else "FLAKING"
    return streak


def _log(row: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    row["ts"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with STATE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def probe(escalate: bool = True) -> dict:
    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
    before = _history()
    results = []
    for cls in LANE_CLASSES:
        for lane in cls["lanes"]:
            ok, why = _probe(lane)
            _log({"name": lane["name"], "class": cls["class"], "ok": ok, "why": why})
            results.append({"lane": lane["name"], "class": cls["class"],
                            "ok": ok, "why": why})
    after = _history()

    down, flaking, recovered = [], [], []
    for r in results:
        st = after.get(r["lane"], {}).get("state", "UP")
        if st == "DOWN":
            down.append(r)
        elif st == "FLAKING":
            flaking.append(r)
        if st == "RECOVERED" and before.get(r["lane"], {}).get("state") in ("DOWN", "FLAKING"):
            recovered.append(r)

    # Failover check: a class is served if any member is not DOWN.
    orphans = []
    for cls in LANE_CLASSES:
        states = [after.get(l["name"], {}).get("state", "UP") for l in cls["lanes"]]
        if all(s == "DOWN" for s in states):
            orphans.append(cls["class"])

    escalated = []
    if escalate and orphans:
        try:
            from mag import phone_relay
            for cls_name in orphans:
                out = phone_relay.ask(
                    f"LANE CLASS DOWN, no failover: {cls_name}. All lanes in the class "
                    f"failed {DOWN_THRESHOLD}+ consecutive probes. Decide when you're back.",
                    timeout_s=3600, source="lane_supervisor")
                escalated.append({"class": cls_name, **out})
        except Exception as e:  # noqa: BLE001 — escalation must never crash the probe
            escalated.append({"error": str(e)[:120]})

    summary = {"ts": now_iso, "up": sum(1 for r in results if r["ok"]),
               "total": len(results), "down": [r["lane"] for r in down],
               "flaking": [r["lane"] for r in flaking],
               "recovered": [r["lane"] for r in recovered],
               "classes_without_failover": orphans, "escalated": escalated}
    print(json.dumps(summary, indent=1))
    return summary


def status() -> str:
    streak = _history()
    lines = ["LANE SUPERVISOR STATUS", ""]
    for cls in LANE_CLASSES:
        lines.append(f"[{cls['class']}]")
        for lane in cls["lanes"]:
            st = streak.get(lane["name"], {"state": "UP", "fails": 0})
            lines.append(f"  {lane['name']:<18} {st['state']:<10} consecutive-fails={st['fails']}")
    return "\n".join(lines)


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "status":
        print(status())
    else:
        out = probe()
        healthy = out["up"] == out["total"] and not out["classes_without_failover"]
        sys.exit(0 if healthy else 1)
