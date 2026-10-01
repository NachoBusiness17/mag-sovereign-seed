"""aos_live_view — LIVE, HUMAN-READABLE VIEW of the Ghost<->AOS bus conversation.

Watch the emergent conversation with AOS/Adventure in real time the way AOS's seat sees it: by
reading the shared git bus (the two JSONL DMs) and rendering them as readable interleaved text.

Read-only on the bus: it only `git pull`s (never writes, commits, or pushes — the watcher owns
sending). It renders BOTH directions so the operator can watch the whole exchange live.

THE LOOP:
  git pull  ->  read ghost-to-aos.jsonl (ours) + aos-to-ghost.jsonl (AOS/Adventure)  ->
  merge by timestamp, dedupe by message id, print any NEW lines as readable text  ->  sleep cadence.

CLI:
  python -m mag.aos_live_view            # watch loop (always-on), default cadence 30s
  python -m mag.aos_live_view --once     # print the whole conversation so far, then exit
  python -m mag.aos_live_view --secs 15  # watch loop with a custom cadence
  python -m mag.aos_live_view --raw      # print raw JSON lines instead of rendered text

Schema: aos_live_view.v1
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "aos_live_view.v1"
TREE = Path(os.environ.get("AOS_T1_PATH", r"C:\AOS\ops\local-reason-bridge\sandbox\partners\ghost-t1"))
INBOUND = TREE / "comm" / "dm" / "aos-to-ghost.jsonl"
OUTBOUND = TREE / "comm" / "dm" / "ghost-to-aos.jsonl"
DEFAULT_CADENCE_S = 30
RATE_PULL_S = 30  # match the bus pull rate (>=30s)

# ── BUS GUARD: no secrets leave on the outbound bus (2026-08-23, operator OPSEC) ──
# We SHARE our deep research OUT to AOS to map understanding. The bus repo is a shared git
# surface (treat as not-fully-trusted). Before anything pushes, strip/refuse secrets: API key
# patterns, canary tokens, and high-entropy token runs that look like keys.
SECRET_PATTERNS = [
    r"sk-or-v1-[A-Za-z0-9_-]{16,}",
    r"sk-ant-[A-Za-z0-9_-]{16,}",
    r"xai-[A-Za-z0-9_-]{16,}",
    r"gsk_[A-Za-z0-9]{16,}",
    r"sk-[A-Za-z0-9]{20,}",
    r"(OPENROUTER|XAI|GROK|ANTHROPIC|OPENAI|DEEPSEEK)_API_KEY\s*=\s*\S+",
    r"Bearer\s+[A-Za-z0-9._~-]{16,}",
]


def _is_content_hash(s: str) -> bool:
    """Pure lowercase-hex of length 64 (sha256) or 40 (sha1) = a CONTENT ADDRESS (public),
    not a secret. The byte-treaty's currency — must never be flagged as a leak."""
    s = s.strip()
    if len(s) not in (40, 64):
        return False
    return all(c in "0123456789abcdef" for c in s)


def _entropy(s: str) -> float:
    import math
    if not s:
        return 0.0
    n = len(s)
    freq: dict[str, int] = {}
    for ch in s:
        freq[ch] = freq.get(ch, 0) + 1
    e = 0.0
    for c in freq.values():
        p = c / n
        e -= p * math.log2(p)
    return e


def sanitize(text: str) -> dict[str, Any]:
    """Scan outbound text for secrets before it touches the bus. Returns clean + findings."""
    import re
    text = text or ""
    findings: list[dict[str, Any]] = []
    for pat in SECRET_PATTERNS:
        for m in re.finditer(pat, text):
            findings.append({"kind": "secret_pattern", "pattern": pat,
                             "snippet": text[max(0, m.start() - 12):m.end() + 12]})
    if "CANARY-" in text:
        findings.append({"kind": "canary", "snippet": "CANARY- token present (exfil marker)"})
    for tok in re.findall(r"\S{20,}", text):
        if _entropy(tok) > 5.8:
            findings.append({"kind": "high_entropy", "snippet": tok[:24]})
    # de-dup by snippet
    seen: set[str] = set()
    uniq = []
    for f in findings:
        key = f["snippet"]
        if key not in seen:
            seen.add(key)
            uniq.append(f)
    return {"clean": len(uniq) == 0, "findings": uniq[:10], "count": len(uniq)}


def _git(*args: str) -> str:
    """Run git in the AOS tree. Read-only on remote (pull only)."""
    try:
        r = subprocess.run(["git", "-C", str(TREE), *args],
                           capture_output=True, text=True, timeout=60)
        return (r.stdout + r.stderr).strip()
    except Exception as e:  # noqa: BLE001
        return f"ERR {type(e).__name__}: {str(e)[:120]}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _pull() -> str:
    return _git("pull", "--rebase")


def _read(path: Path) -> list[dict[str, Any]]:
    """Parse a JSONL DM file into a list of messages. Never fails on bad lines."""
    if not path.is_file():
        return []
    out = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


def _all_messages() -> list[dict[str, Any]]:
    """Merge both directions, tag direction, sort by ts."""
    msgs = []
    for path, label in ((OUTBOUND, "bone"), (INBOUND, "aos")):
        for m in _read(path):
            msgs.append({"label": label, "ts": m.get("ts", ""),
                         "id": m.get("id", ""), "from": m.get("from", ""),
                         "to": m.get("to", ""), "author": m.get("author", ""),
                         "text": (m.get("text") or m.get("goal") or "").strip()})
    msgs.sort(key=lambda m: m["ts"])
    return msgs


def _fmt_time(ts: str) -> str:
    try:
        dt = datetime.fromisoformat(ts)
        return dt.astimezone().strftime("%H:%M:%S")
    except Exception:
        return ts


def _render(m: dict[str, Any], *, raw: bool = False) -> str:
    if raw:
        return json.dumps({"id": m["id"], "ts": m["ts"], "from": m.get("from") or m["label"],
                           "text": m["text"]}, ensure_ascii=False)
    who = m["label"].upper()
    # Prefer the TRUE speaker (author/from) over the file-side label, so the operator's own
    # messages render as OPERATOR and the agent's as BONE — never merged into one voice.
    true = (m.get("author") or "").strip() or (m.get("from") or "").strip()
    if true and true.lower() != m["label"]:
        who = true.upper()
    lines = ["", f"[{_fmt_time(m['ts'])}] {who}  ({m['id']})"]
    lines.append("-" * 70)
    lines.append(m["text"])
    return "\n".join(lines)


def render(*, raw: bool = False) -> str:
    """Render the full conversation as readable text. Returns empty string if no messages."""
    msgs = _all_messages()
    if not msgs:
        return "(no messages on the bus yet)"
    return "\n".join(_render(m, raw=raw) for m in msgs)


def watch(*, secs: int = DEFAULT_CADENCE_S, raw: bool = False) -> None:
    """Always-on loop: render full history once, then stream new lines. Ctrl+C to stop."""
    seen: set[str] = set()
    print(f"=== AOS live view — {SCHEMA} ===")
    print(f"tree: {TREE}")
    print(f"watching every {secs}s — Ctrl+C to stop\n")
    try:
        first = True
        while True:
            _pull()
            msgs = _all_messages()
            if first:
                # populate with the full history so far
                hist = [m for m in msgs if m["id"]]
                for m in msgs:
                    if m["id"]:
                        seen.add(m["id"])
                if hist:
                    print(f"########## HISTORY ({len(hist)} messages) ##########")
                else:
                    print("########## HISTORY (no messages yet) ##########")
                for m in msgs:
                    if m["text"]:
                        print(_render(m, raw=raw))
                print("\n########## LIVE — new messages will appear here ##########")
                sys.stdout.flush()
                first = False
                time.sleep(max(secs, RATE_PULL_S))
                continue
            for m in msgs:
                if m["id"] and m["id"] in seen:
                    continue
                if m["id"]:
                    seen.add(m["id"])
                if not m["text"]:
                    continue
                print(_render(m, raw=raw))
                sys.stdout.flush()
            time.sleep(max(secs, RATE_PULL_S))
    except KeyboardInterrupt:
        print("\n(stopped)")


def _dedupe_known() -> set[str]:
    # Used only to note how many messages are already on the bus in --once.
    return {m["id"] for m in _all_messages() if m["id"]}


def chat_json() -> dict[str, Any]:
    """Pull the bus and return the full conversation as JSON (for the browser surface).

    Lightweight, read-only. Pulls git, merges both directions by timestamp, returns a
    ``{"ok": True, "messages": [...]}`` envelope the dashboard /api/aos/chat endpoint can
    hand straight to a page. Never writes, commits, or pushes.
    """
    _pull()
    msgs = _all_messages()
    return {
        "ok": True,
        "schema": SCHEMA,
        "tree": str(TREE),
        "count": len(msgs),
        "messages": msgs,
    }


def send_text(text: str, *, author: str = "bone", force: bool = False,
              expects_reply: bool = True) -> dict[str, Any]:
    """Send one Bone/Operator reply to AOS on the bus (the browser Bone-seat path).

    Appends a GO-PROTOCOL-shaped line to OUR jsonl (never AOS's), commits, pulls --rebase,
    and pushes. Mirrors mag.aos_bus_watcher._send. `author` is the PROVENANCE stamp: who
    actually spoke (ghost = the agent, operator = the human) — so the operator's input is
    never re-labeled as the agent's. Keeps `from`/`to` for routing; adds explicit `author`.

    BUS GUARD: by default, REFUSES to push if `sanitize()` finds secrets (API keys, canary
    tokens, high-entropy runs). This is the OPSEC wall for sharing our deep research OUT —
    nothing sensitive leaves on the shared bus. `force=True` bypasses (operator override only).
    """
    text = (text or "").strip()
    if not text:
        return {"ok": False, "error": "empty text"}
    g = sanitize(text)
    if not g["clean"] and not force:
        return {"ok": False, "error": "bus-guard refused: secrets detected on outbound",
                "findings": g["findings"], "count": g["count"]}
    author = (author or "bone").strip()[:32]
    if author not in ("bone", "operator"):
        author = "bone"  # provenance: only these two authors exist on this side
    OUTBOUND.parent.mkdir(parents=True, exist_ok=True)
    mid = f"bone-{uuid.uuid4().hex[:8]}"
    msg = {
        # `from` MUST reflect the true speaker (bone|operator), not be hardcoded to "bone".
        # AOS reads `from`, so if every outbound says from:"bone" the operator's words get
        # merged into one unified agent voice — the exact "AOS takes everything from Ghost as
        # one unified response" failure (operator 2026-08-23). The operator's own input must
        # arrive to AOS as from:"operator", so AdventureLearn can see the human distinctly.
        "id": mid, "ts": _now(), "from": author, "to": "aos", "type": "dm",
        "action": "steer", "text": text, "goal": text,
        "author": author,  # provenance seam: bone vs operator
        "expects_reply": bool(expects_reply),  # RIB contract: explicit turn expectation, never assumed
        "promote": False, "dry_run": True, "channel": "file-bus-v1",
    }
    with OUTBOUND.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(msg, ensure_ascii=False) + "\n")
    _git("add", "--", str(OUTBOUND.relative_to(TREE)))
    _git("commit", "-m", "bone: dm")
    _pull()
    push = _git("push")
    ok = "main ->" in push or "up to date" in push
    # Keep the WATCHER's state in sync so manual sends and the autonomous daemon share one
    # "last replied" record — otherwise the daemon would double-reply to what we just handled.
    try:
        st = {}
        st_path = ROOT / "memory" / "runs" / "aos_bus_watcher_state.json"
        if st_path.is_file():
            st = json.loads(st_path.read_text(encoding="utf-8")) or {}
        st["last_replied_inbound_id"] = _latest_inbound_id()
        st["last_push_ts"] = datetime.now(timezone.utc).timestamp()
        st["last_push_id"] = mid
        st_path.parent.mkdir(parents=True, exist_ok=True)
        st_path.write_text(json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    return {"ok": ok, "id": mid, "author": author, "push": push[:120]}


def _latest_inbound_id() -> str:
    """The newest AOS/Adventure inbound id on the bus (for state sync), or '' if none."""
    latest = ""
    for m in _read(INBOUND):
        if m.get("from") in ("aos", "adventure") and m.get("id"):
            latest = m["id"]
    return latest


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="aos-live-view")
    ap.add_argument("--once", action="store_true", help="print the whole conversation and exit")
    ap.add_argument("--json", action="store_true",
                    help="pull the bus and print the conversation as JSON (for the browser endpoint)")
    ap.add_argument("--send", metavar="TEXT", default=None,
                    help="send one Bone reply to AOS on the bus (browser Bone-seat), then exit")
    ap.add_argument("--send-file", metavar="PATH", default=None,
                    help="read reply text from a file and send it (avoids shell quoting)")
    ap.add_argument("--author", default="bone", choices=["bone", "operator"],
                    help="provenance stamp: bone = the agent, operator = the human (default bone)")
    ap.add_argument("--secs", type=int, default=DEFAULT_CADENCE_S,
                    help=f"watch cadence in seconds (default {DEFAULT_CADENCE_S})")
    ap.add_argument("--raw", action="store_true", help="print raw JSON lines instead of rendered text")
    a = ap.parse_args()
    if a.send_file is not None:
        try:
            txt = Path(a.send_file).read_text(encoding="utf-8", errors="replace")
        except Exception as exc:  # noqa: BLE001
            print(json.dumps({"ok": False, "error": str(exc)[:200]}, ensure_ascii=False))
        else:
            print(json.dumps(send_text(txt, author=a.author), indent=2, ensure_ascii=False))
    elif a.send is not None:
        print(json.dumps(send_text(a.send, author=a.author), indent=2, ensure_ascii=False))
    elif a.json:
        print(json.dumps(chat_json(), indent=2, ensure_ascii=False))
    elif a.once:
        _pull()
        body = render(raw=a.raw)
        n = len(_dedupe_known())
        print(f"=== AOS live view — full conversation so far ({n} messages) ===\n")
        print(body)
    else:
        watch(secs=a.secs, raw=a.raw)
