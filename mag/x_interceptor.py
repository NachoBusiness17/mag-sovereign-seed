"""x_interceptor — whale-watch for the @NachoQuixotic beacon (operator order 2026-09-06:
"interceptor duty, every 5 minutes; when you get one, fire against our corpus").

LOOP (run): scan -> dedupe -> on a NEW whale, deep-fire.
  SCAN: one grok CLI pass (subscription lane, $0) over the whale accounts' last hour;
        returns candidate posts with velocity.
  DEDUPE: watch/x_intercept_log.jsonl holds every whale already briefed.
  DEEP-FIRE (only on a catch): (a) local corpus mining — the operator's own past strikes on
        the subject (ROASTS_RAW.md master table + persona moves); (b) grok target profile +
        current top replies; (c) three draft replies in the house voice: darkly funny,
        plausibly deniable (no accusations, no un-citable claims, riddle-shaped), NO
        PREACHING, never a faked receipt (tri-state annex to LAW-061).
  GATE HELD: nothing auto-posts — drafts go to the operator (hand or armed Pro deck).

RATE GUARD: two consecutive scan failures = the module exits non-zero and the cron run
reports and stops (two-strike bail); the next scheduled run starts fresh.

CLI:
  python -m mag.x_interceptor scan            # heartbeat: scan, dedupe, deep-fire new whales
  python -m mag.x_interceptor deepfire <post_url_or_id> \"<post text>\"
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GROK = Path("C:/Users/ESTATE_USER/.grok/bin/grok")
LOG = ROOT / "watch" / "x_intercept_log.jsonl"
BRIEFS = ROOT / "watch" / "x_intercepts"
ROASTS = ROOT / "memory" / "runs" / "x_shitposter_mining_20260906" / "ROASTS_RAW.md"
PERSONA = ROOT / "watch" / "SHITPOSTER_IN_CHIEF_PERSONA_20260906.md"

WHALES = ["elonmusk", "sama", "karpathy", "swyx", "simonw", "OpenAI", "AnthropicAI",
          "xabora", "OpenAIDevs", "xai", "grok"]

SCAN_PROMPT = (
    "Use x_keyword_search ONCE (do not paginate) for posts from the last 90 minutes by any of: "
    "__WHALES__. Build the query by joining from:<account> for each account with OR, and append "
    "min_faves:200. For each hit return: post id, author, first 120 chars, current like count, "
    "and age in minutes (from the timestamp). Return STRICT JSON only, shaped exactly like this "
    "example: EXAMPLE {\"whales\":[{\"id\":\"123\",\"author\":\"elonmusk\",\"snippet\":\"...\","
    "\"likes\":999,\"age_min\":12}]} — if nothing qualifies return {\"whales\":[]}."
)


def _grok(prompt: str, turns: str = "6", timeout: int = 150) -> str:
    # 150s: trivial grok pass measured ~74s, so this keeps 2x headroom while a worst-case
    # scan still fits the 5-minute cadence; a hang degrades to a clean strike, not a traceback.
    try:
        proc = subprocess.run([str(GROK), "-p", prompt, "--no-plan", "--max-turns", turns],
                              capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        print(f"grok lane timed out after {timeout}s — counting as strike")
        return ""
    return proc.stdout


def _extract_json(raw: str) -> dict | None:
    m = re.search(r"```json\s*(\{.*?\})\s*```", raw, re.S)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    m = re.search(r"(\{.*\})", raw, re.S)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            return None
    return None


def _seen() -> set[str]:
    if not LOG.is_file():
        return set()
    out = set()
    for ln in LOG.read_text(encoding="utf-8").splitlines():
        if ln.strip():
            try:
                out.add(json.loads(ln).get("id", ""))
            except json.JSONDecodeError:
                continue
    return out


def _log(entry: dict) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _corpus_fire(subject: str) -> str:
    """Mine the operator's own strikes for tone + nearest past hits on this subject."""
    lines = []
    if ROASTS.is_file():
        text = ROASTS.read_text(encoding="utf-8", errors="replace")
        hits = []
        for kw in [w for w in re.findall(r"[a-zA-Z]{5,}", subject)][:8]:
            for m in re.finditer(r"^.*" + re.escape(kw) + r".*$", text, re.I | re.M):
                snippet = m.group(0).strip()
                if 40 < len(snippet) < 300:
                    hits.append(snippet)
        seen = set()
        for h in hits:
            k = h[:60]
            if k not in seen:
                seen.add(k)
                lines.append("- " + h[:220])
            if len(lines) >= 8:
                break
    if PERSONA.is_file():
        t = PERSONA.read_text(encoding="utf-8", errors="replace")
        m = re.search(r"## 3\. THE TEN MOVES.*?(?=\n## )", t, re.S)
        if m:
            lines.append("TEN MOVES (house arsenal):\n" + m.group(0)[:900])
    return "\n".join(lines) if lines else "(no direct subject hits — carry the house voice only)"


def deepfire(post_id: str, text: str, author: str = "") -> Path:
    now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    BRIEFS.mkdir(parents=True, exist_ok=True)
    subject = text[:400]

    profile_raw = _grok(
        "Use x_user_search/x_keyword_search briefly. Target: X account @" + (author or post_id) +
        ". Who are they (role, followers rough tier, what they are known for), and what are the "
        "current top 3 replies (author + likes + snippet) on their recent high-traffic posts? "
        "STRICT JSON: {\"who\":\"\",\"tier\":\"\",\"top_replies\":[{\"author\":\"\",\"likes\":0,"
        "\"snippet\":\"\"}]}")
    profile = _extract_json(profile_raw) or {}

    corpus = _corpus_fire(subject)
    draft_raw = _grok(
        "Draft from the given context only; do not search or browse. "
        "You are the NACHO MASK ractor drafting X replies for @NachoQuixotic. TARGET POST by @"
        + (author or "?") + ": \"" + subject.replace("\"", "'") + "\"\n\n"
        "TARGET PROFILE: " + json.dumps(profile)[:500] + "\n\n"
        "THE OPERATOR'S OWN PAST STRIKES (voice + verbatim examples):\n" + corpus[:2000] + "\n\n"
        "Draft 3 reply options. HOUSE LAWS: darkly funny; plausibly deniable (no accusations, no "
        "claims of fact we cannot cite, riddle-shaped — the tape teaches or it buries); NO "
        "PREACHING; never fabricate a receipt or a number (tri-state annex to LAW-061); <=280 "
        "chars each; at most one may use the verbatim-hanging device (quote the target's own "
        "words back). Return STRICT JSON: {\"drafts\":[{\"device\":\"\",\"text\":\"\"}]}",
        turns="12")
    drafts = _extract_json(draft_raw) or {"drafts": []}

    brief = BRIEFS / f"intercept_{now}_{re.sub(r'[^A-Za-z0-9]', '', post_id)[:20]}.md"
    brief.write_text(
        "# X INTERCEPT — whale caught\n\n"
        f"- **when:** {now}  ·  **target:** @{author or '?'}  ·  **post:** `{post_id}`\n"
        f"- **text:** {text}\n\n"
        f"## Target profile\n```json\n{json.dumps(profile, indent=1, ensure_ascii=False)[:1200]}\n```\n\n"
        f"## The operator's own past strikes on this subject\n{corpus[:2400]}\n\n"
        f"## Drafts (NACHO MASK — darkly funny, plausibly deniable, no preaching)\n"
        + "\n".join(f"{i+1}. **[{d.get('device','?')}]** {d.get('text','')}"
                    for i, d in enumerate(drafts.get("drafts", [])[:3]))
        + "\n\n*GATE HELD: nothing auto-posts. Operator fires by hand or the armed Pro deck.*\n",
        encoding="utf-8")
    _log({"id": post_id, "author": author, "ts": now, "brief": brief.name,
          "drafts": len(drafts.get("drafts", []))})
    print(f"WHALE: @{author or '?'} {post_id} -> {brief.name} ({len(drafts.get('drafts', []))} drafts)")
    return brief


def scan() -> int:
    raw = _grok(SCAN_PROMPT.replace("__WHALES__", ", ".join(WHALES[:9])))
    d = _extract_json(raw)
    if not d or "whales" not in d:
        print("SCAN FAIL: no parseable output — counting as strike one")
        return 1
    seen = _seen()
    fresh = [w for w in d["whales"] if str(w.get("id")) not in seen]
    print(f"scan: {len(d['whales'])} candidates, {len(fresh)} new")
    if not fresh:
        _log({"id": f"scan:{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M')}", "author": "",
              "ts": datetime.now(timezone.utc).isoformat(), "brief": "no-new-whales", "drafts": 0})
        return 0
    fresh.sort(key=lambda w: w.get("likes", 0), reverse=True)
    top = fresh[0]
    deepfire(str(top.get("id")), str(top.get("snippet", "")), str(top.get("author", "")))
    for w in fresh[1:3]:
        _log({"id": str(w.get("id")), "author": str(w.get("author", "")),
              "ts": datetime.now(timezone.utc).isoformat(), "brief": "logged-not-briefed", "drafts": 0})
    return 0


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "scan"
    if cmd == "scan":
        sys.exit(scan())
    elif cmd == "deepfire" and len(sys.argv) > 2:
        deepfire(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "", "")
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
