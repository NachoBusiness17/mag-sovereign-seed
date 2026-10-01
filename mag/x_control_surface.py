"""X Control Surface — Ghost browses X, reads @nachoquixotic prompts, posts results.

Architecture:
  Ghost → Grok agent (Super Grok API) → X native tools → pull prompts
  Ghost → X API v2 (OAuth 2.0) → post results, read mentions
  @nachoquixotic "Strike the Chord" → copilot inbox → autonomous agent loop

TWO PATHS (choose based on what's configured):
  PATH A — Grok Native (Super Grok license):
    Grok has built-in x_* tools. Ghost spawns a Grok agent that uses
    x_user_search, x_semantic_search, x_thread_fetch to pull @nachoquixotic
    prompts. Results route through the copilot inbox → orchestrator.

  PATH B — Direct X API (X API v2 bearer + OAuth):
    Ghost calls X API directly via fxtwitter (read) + X API v2 (read/write).
    Lower latency, no Grok spend, but needs separate X API credentials.

  PATH C — Hybrid (Grok for discovery + fxtwitter for fetch):
    Grok finds relevant @nachoquixotic posts via semantic search.
    Ghost fetches full text via fxtwitter (free, no auth needed for public).
    Ghost posts replies via X API v2 write.

CONTROL SURFACE:
  - Ghost polls its own X account for mentions/DMs → treats as commands
  - Operators tweet "@GhostSovereign deploy campaign quiet_forge" → Ghost executes
  - Ghost posts status updates: "Ran campaign: 1 room, 1 steer deployed. Leak scan clean."

Schema: x_control_surface.v1
Law: X API keys NEVER leave the machine. Prompts are ingested locally.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except ImportError:
    ROOT = Path(__file__).resolve().parent.parent

# ── Paths ─────────────────────────────────────────────────────────
X_SURFACE_DIR = ROOT / "memory" / "ghost" / "x_surface"
X_PROMPTS_DIR = X_SURFACE_DIR / "nachoquixotic_prompts"
X_MENTIONS_LOG = X_SURFACE_DIR / "mentions.jsonl"
X_POSTS_LOG = X_SURFACE_DIR / "posts.jsonl"
X_STATE = X_SURFACE_DIR / "state.json"

# ── X account config (set in .env or environment) ──
X_HANDLE = os.environ.get("GHOST_X_HANDLE", "")          # e.g. "GhostSovereign"
X_API_KEY = os.environ.get("X_API_KEY", "")               # X API v2 bearer token
X_API_SECRET = os.environ.get("X_API_SECRET", "")         # OAuth 2.0 secret
X_ACCESS_TOKEN = os.environ.get("X_ACCESS_TOKEN", "")     # OAuth 2.0 access token
X_ACCESS_SECRET = os.environ.get("X_ACCESS_SECRET", "")   # OAuth 2.0 access secret

# ── Target accounts to monitor ──
TARGET_ACCOUNTS: list[str] = [
    "NachoQuixotic",   # Strike the Chord prompts
    # Add more accounts here — Ghost will monitor all of them
]

# ── Strike the Chord prompt patterns ──
STRIKE_PATTERNS: list[str] = [
    r"strike\s+the\s+chord",
    r"chord\s+prompt",
    r"system\s+prompt\s+for",
    r"you\s+are\s+\w+\s+and\s+you",
    r"available\s+tools",
    r"render\s+components",
]

STRIKE_MIN_LENGTH = 200  # minimum chars for a prompt to be considered valid


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8", errors="replace")).hexdigest()[:12]


def _load_json(path: Path) -> dict[str, Any]:
    if path.is_file():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _append_jsonl(path: Path, entry: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _read_jsonl(path: Path, tail: int = 200) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8", errors="replace").strip().splitlines()
    if tail and len(lines) > tail:
        lines = lines[-tail:]
    rows: list[dict[str, Any]] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


# ═══════════════════════════════════════════════════════════════════
# X API v2 — DIRECT (PATH B)
# ═══════════════════════════════════════════════════════════════════

def x_api_configured() -> bool:
    """Check if X API v2 credentials are available."""
    return bool(X_API_KEY) or bool(X_ACCESS_TOKEN)


def grok_api_configured() -> bool:
    """Check if Grok API (Super Grok license) is available."""
    return bool(os.environ.get("XAI_API_KEY") or os.environ.get("GROK_API_KEY"))


def any_x_surface_configured() -> bool:
    """Check if ANY X surface path is available."""
    return x_api_configured() or grok_api_configured()


def fetch_user_timeline(
    username: str,
    max_results: int = 10,
) -> list[dict[str, Any]]:
    """Fetch recent posts from an X user via fxtwitter (free, no auth).

    Uses the same stack as mycelial-republic/x_pull.py and sovereign-mirror.
    No API key needed for public tweets.
    """
    import urllib.error
    import urllib.request

    posts: list[dict[str, Any]] = []

    # Try fxtwitter user endpoint
    try:
        url = f"https://api.fxtwitter.com/{username}/timeline"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "GhostSovereign/0.1 (+local; research)"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=25.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            tweets = data.get("tweets") or data.get("timeline") or []
            for tweet in tweets[:max_results]:
                text = (tweet.get("text") or tweet.get("raw_text") or "").strip()
                if text:
                    posts.append({
                        "id": str(tweet.get("id", "")),
                        "text": text,
                        "created_at": str(tweet.get("created_at", "")),
                        "author": username,
                        "source": "x_fxtwitter",
                        "url": f"https://x.com/{username}/status/{tweet.get('id', '')}",
                    })
    except (urllib.error.URLError, json.JSONDecodeError, OSError):
        pass

    return posts


def fetch_status(status_id: str) -> dict[str, Any] | None:
    """Fetch a single X post by status ID via fxtwitter."""
    import urllib.error
    import urllib.request

    status_id = str(status_id).strip()
    try:
        url = f"https://api.fxtwitter.com/status/{status_id}"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "GhostSovereign/0.1 (+local; research)"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=25.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            tweet = data.get("tweet") or data
            text = (tweet.get("text") or tweet.get("raw_text") or "").strip()
            if text:
                author = ""
                user = tweet.get("author") or {}
                if isinstance(user, dict):
                    author = user.get("screen_name", "")
                return {
                    "id": status_id,
                    "text": text,
                    "created_at": str(tweet.get("created_at", "")),
                    "author": author,
                    "source": "x_fxtwitter",
                    "url": f"https://x.com/i/status/{status_id}",
                }
    except (urllib.error.URLError, json.JSONDecodeError, OSError):
        pass
    return None


# ═══════════════════════════════════════════════════════════════════
# GROK NATIVE X TOOLS (PATH A)
# ═══════════════════════════════════════════════════════════════════

def grok_search_nachoquixotic() -> list[dict[str, Any]]:
    """Use Grok's native x_* tools to find @nachoquixotic's Strike the Chord prompts.

    Requires: XAI_API_KEY or GROK_API_KEY in environment (Super Grok license).
    Returns: List of posts that match strike-the-chord patterns.
    """
    if not grok_api_configured():
        return []

    # This builds a Grok agent prompt that uses Grok's built-in x_semantic_search
    # and x_user_search tools to find the prompts. The Grok agent runs via
    # the existing grok_client.py or via copilot inbox → orchestrator.

    prompt = (
        f"You have access to x_user_search, x_semantic_search, x_keyword_search, "
        f"and x_thread_fetch tools. Do the following:\n\n"
        f"1. Use x_user_search to confirm @NachoQuixotic exists (query: 'NachoQuixotic').\n"
        f"2. Use x_semantic_search with query 'strike the chord prompt system' "
        f"from user NachoQuixotic to find recent Strike the Chord posts.\n"
        f"3. Use x_keyword_search with query 'from:NachoQuixotic (\"strike the chord\" OR \"system prompt\" OR \"available tools\" OR \"you are\")' "
        f"to find technical prompt posts.\n"
        f"4. For each relevant post, use x_thread_fetch to get the full thread context.\n"
        f"5. Return a JSON array of posts with keys: id, text (first 500 chars), "
        f"created_at, url. Only include posts that appear to be AI system prompts "
        f"(containing 'you are', 'available tools', 'guidelines', etc.) and are "
        f"at least {STRIKE_MIN_LENGTH} characters.\n"
        f"6. Write the result to a file in memory/ghost/x_surface/nachoquixotic_prompts/ "
        f"with filename format: prompt-{{post_id}}.md containing the full prompt text.\n"
        f"7. Return a JSON summary of how many prompts were found and saved."
    )

    return [{
        "method": "grok_agent",
        "prompt": prompt,
        "model": "grok-4",
        "note": "Route this through copilot inbox → orchestrator → Grok agent",
    }]


# ═══════════════════════════════════════════════════════════════════
# PROMPT DETECTION & INGESTION
# ═══════════════════════════════════════════════════════════════════

def is_strike_chord_prompt(text: str) -> bool:
    """Heuristic: does this post look like a Strike the Chord AI system prompt?

    Checks for:
    - Contains multiple strike patterns (system prompt structure)
    - Minimum length (real prompts are long)
    - Contains function/tool definitions
    - Contains behavioral guidelines
    """
    if len(text) < STRIKE_MIN_LENGTH:
        return False

    matches = 0
    for pattern in STRIKE_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            matches += 1

    # Need at least 3 pattern matches for high confidence
    return matches >= 3


def extract_prompt_metadata(text: str, post_id: str = "") -> dict[str, Any]:
    """Extract metadata from a Strike the Chord prompt.

    Detects: model name, date/version, tool list, team structure.
    """
    meta: dict[str, Any] = {
        "post_id": post_id,
        "is_strike_chord": False,
        "detected_model": "",
        "detected_date": "",
        "tool_count": 0,
        "team_agents": [],
        "has_tools": False,
        "has_render_components": False,
        "char_length": len(text),
    }

    if not is_strike_chord_prompt(text):
        return meta

    meta["is_strike_chord"] = True

    # Detect model name
    model_patterns = [
        r"(?:you are|as)\s+(Grok[\s\-]?[\d\.]+(?:\s*\([^)]+\))?)",
        r"(?:you are|as)\s+(Claude[\s\-]?[\d\.]+(?:\s*\([^)]+\))?)",
        r"(?:you are|as)\s+(GPT[\s\-]?[\d\.]+(?:\s*\([^)]+\))?)",
        r"(?:you are|as)\s+(Gemini[\s\-]?[\d\.]+(?:\s*\([^)]+\))?)",
    ]
    for pat in model_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            meta["detected_model"] = m.group(1).strip()
            break

    # Detect date
    date_patterns = [
        r'(?:updated|version|release)[:\s]+([A-Z][a-z]{2}[-\s]\d{1,2}[,\s]*2025)',
        r'(?:updated|version|release)[:\s]+(\d{4}-\d{2}-\d{2})',
    ]
    for pat in date_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            meta["detected_date"] = m.group(1).strip()
            break

    # Count tools
    tool_matches = re.findall(r'\{"name":\s*"(\w+)",\s*"description"', text)
    meta["tool_count"] = len(tool_matches)
    meta["has_tools"] = meta["tool_count"] > 0

    # Detect render components
    meta["has_render_components"] = bool(re.search(r'Render\s+Components', text, re.I))

    # Detect team agents
    team_match = re.search(
        r'(?:collaborating with|team[:\s]+)([^.!?\n]{10,100})',
        text, re.IGNORECASE,
    )
    if team_match:
        names = re.findall(r'\b([A-Z][a-z]+)\b', team_match.group(1))
        meta["team_agents"] = names[:6]

    return meta


def ingest_prompts_from_posts(posts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Ingest Strike the Chord prompts from X posts into local storage.

    Saves each prompt as a .md file and returns a list of ingestion records.
    """
    ingested: list[dict[str, Any]] = []

    for post in posts:
        text = post.get("text", "")
        if not is_strike_chord_prompt(text):
            continue

        post_id = post.get("id", _hash(text))
        meta = extract_prompt_metadata(text, post_id)

        # Save prompt file
        X_PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
        prompt_file = X_PROMPTS_DIR / f"prompt-{post_id}.md"
        header = (
            f"# Strike the Chord Prompt\n"
            f"<!-- source: {post.get('url', 'x.com')} -->\n"
            f"<!-- author: {post.get('author', 'NachoQuixotic')} -->\n"
            f"<!-- created_at: {post.get('created_at', '')} -->\n"
            f"<!-- detected_model: {meta['detected_model']} -->\n"
            f"<!-- tool_count: {meta['tool_count']} -->\n"
            f"<!-- ingested_at: {_now()} -->\n\n"
        )
        prompt_file.write_text(header + text, encoding="utf-8")

        record = {
            "post_id": post_id,
            "author": post.get("author", "NachoQuixotic"),
            "url": post.get("url", ""),
            "created_at": post.get("created_at", ""),
            "ingested_at": _now(),
            "file": str(prompt_file.relative_to(ROOT)),
            "detected_model": meta["detected_model"],
            "tool_count": meta["tool_count"],
            "char_length": meta["char_length"],
        }
        ingested.append(record)

    return ingested


# ═══════════════════════════════════════════════════════════════════
# X CONTROL SURFACE — MENTIONS AS COMMANDS
# ═══════════════════════════════════════════════════════════════════

def check_mentions() -> list[dict[str, Any]]:
    """Check Ghost's X account for mentions and DMs that contain commands.

    Returns list of parsed commands ready for copilot inbox routing.
    """
    if not X_HANDLE or not X_API_KEY:
        return []

    # Would use X API v2: GET /2/users/:id/mentions
    # For now, returns empty — needs OAuth 2.0 token with read access
    return []


def parse_x_command(text: str, author: str = "", post_id: str = "") -> dict[str, Any] | None:
    """Parse a tweet/DM as a potential command for Ghost.

    Command format: "@GhostSovereign <action> <args>"
    Supported actions: deploy, campaign, sense, status, probe, kill
    """
    # Strip @mentions of Ghost itself
    text = re.sub(rf'@{re.escape(X_HANDLE)}\s*', '', text, flags=re.I).strip()
    if not text:
        return None

    action_map = {
        "deploy": "exec",
        "campaign": "exec",
        "sense": "read",
        "status": "read",
        "probe": "exec",
        "kill": "exec",
        "scan": "read",
        "leak": "read",
        "tesuji": "exec",
        "whisper": "exec",
        "research": "exec",
    }

    words = text.lower().split()
    action = words[0] if words else ""
    mapped_action = action_map.get(action, "exec")

    command = {
        "id": f"x-cmd-{post_id or uuid.uuid4().hex[:8]}",
        "action": mapped_action,
        "goal": text,
        "provider": "grok" if grok_api_configured() else "deepseek",
        "model": "grok-4" if grok_api_configured() else "deepseek-v4-flash",
        "timeout_s": 300,
        "ts": _now(),
        "source": f"x:{author}",
    }

    return command


def post_to_x(text: str, *, reply_to_id: str = "") -> dict[str, Any]:
    """Post a status update to Ghost's X account.

    Uses X API v2: POST /2/tweets (OAuth 2.0 user context).
    Requires write access — the operator's X Premium account + x_oauth token.

    Deep-steal (2026-08-21): this existing X surface is the single posting entry
    point. Token comes from mag.x_oauth (user-context OAuth2 + auto-refresh), with
    fallback to a legacy X_ACCESS_TOKEN env token. POST /2/tweets needs a USER
    token, not an app-only bearer — so we never send a bare app bearer here.
    """
    from mag import x_oauth
    token, err = x_oauth._access_token()
    if not token:
        token = X_ACCESS_TOKEN
    if not token:
        return {"ok": False, "error": "no X access token — run `python -m mag.x_oauth start` to authorize"}

    # X API v2 post
    import urllib.error
    import urllib.request

    payload: dict[str, Any] = {"text": text[:280]}  # X character limit
    if reply_to_id:
        payload["reply"] = {"in_reply_to_tweet_id": reply_to_id}

    try:
        req = urllib.request.Request(
            "https://api.x.com/2/tweets",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "User-Agent": f"{X_HANDLE or 'GhostSovereign'}/0.1",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15.0) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            post_id = result.get("data", {}).get("id", "")

            _append_jsonl(X_POSTS_LOG, {
                "ts": _now(),
                "text": text[:100],
                "post_id": post_id,
                "reply_to": reply_to_id,
                "ok": True,
            })

            return {"ok": True, "post_id": post_id, "url": f"https://x.com/{X_HANDLE}/status/{post_id}"}

    except (urllib.error.URLError, json.JSONDecodeError, OSError) as e:
        _append_jsonl(X_POSTS_LOG, {
            "ts": _now(),
            "text": text[:100],
            "error": str(e)[:200],
            "ok": False,
        })
        return {"ok": False, "error": str(e)[:200]}


# ═══════════════════════════════════════════════════════════════════
# MAIN SURFACE CYCLE — called by Ghost's autonomous loop
# ═══════════════════════════════════════════════════════════════════

def x_surface_cycle() -> dict[str, Any]:
    """Run one cycle of the X control surface.

    1. Pull @nachoquixotic timeline for new Strike the Chord prompts
    2. Ingest any new prompts into local storage
    3. Check Ghost's X account for command mentions
    4. Route commands to copilot inbox
    5. Return cycle report

    Returns dict with cycle results.
    """
    if not any_x_surface_configured():
        return {
            "ok": False,
            "error": "No X surface configured. Set XAI_API_KEY (Super Grok) or X_API_KEY + X_ACCESS_TOKEN.",
            "ts": _now(),
        }

    report: dict[str, Any] = {
        "ts": _now(),
        "surface": "x",
        "paths_available": {
            "grok_native": grok_api_configured(),
            "x_api_direct": x_api_configured(),
        },
        "prompts_found": 0,
        "prompts_ingested": 0,
        "commands_found": 0,
        "commands_routed": 0,
        "posts_made": 0,
    }

    # ── Step 1: Pull @nachoquixotic prompts ──
    prompts_found: list[dict[str, Any]] = []

    # PATH B: Direct fxtwitter fetch (free, works now)
    for account in TARGET_ACCOUNTS:
        posts = fetch_user_timeline(account, max_results=10)
        for post in posts:
            if is_strike_chord_prompt(post.get("text", "")):
                prompts_found.append(post)

    # PATH A: Grok native search (if Super Grok is configured)
    if grok_api_configured() and not prompts_found:
        grok_instructions = grok_search_nachoquixotic()
        if grok_instructions:
            # Route through copilot inbox for async Grok agent execution
            inbox_path = ROOT / "memory" / "copilot" / "inbox.jsonl"
            _append_jsonl(inbox_path, {
                "id": f"x-grok-nacho-{uuid.uuid4().hex[:6]}",
                "action": "exec",
                "goal": grok_instructions[0]["prompt"],
                "provider": "grok",
                "model": "grok-4",
                "timeout_s": 300,
                "ts": _now(),
                "source": "x-surface-nachoquixotic",
            })

    report["prompts_found"] = len(prompts_found)

    # ── Step 2: Ingest prompts ──
    if prompts_found:
        ingested = ingest_prompts_from_posts(prompts_found)
        report["prompts_ingested"] = len(ingested)

        # Route each ingested prompt to the copilot inbox as a research task
        for record in ingested:
            inbox_path = ROOT / "memory" / "copilot" / "inbox.jsonl"
            _append_jsonl(inbox_path, {
                "id": f"x-prompt-{record['post_id'][:12]}",
                "action": "exec",
                "goal": (
                    f"Analyze the Strike the Chord prompt at {record['file']}. "
                    f"It was posted by @{record['author']} and describes a "
                    f"{record['detected_model']} agent with {record['tool_count']} tools. "
                    f"Write a one-paragraph assessment: what is this prompt designed to do? "
                    f"What kind of agent behavior does it encode? What can Ghost learn "
                    f"from its structure? Write to memory/copilot/outbox/x-prompt-{record['post_id'][:12]}.json"
                ),
                "provider": "deepseek",
                "model": "deepseek-v4-flash",
                "timeout_s": 120,
                "ts": _now(),
                "source": "x-surface-nachoquixotic-ingest",
            })

    # ── Step 3: Check mentions (if X account is configured) ──
    if X_HANDLE and X_API_KEY:
        mentions = check_mentions()
        report["commands_found"] = len(mentions)
        for mention in mentions:
            cmd = parse_x_command(
                mention.get("text", ""),
                mention.get("author", ""),
                mention.get("id", ""),
            )
            if cmd:
                inbox_path = ROOT / "memory" / "copilot" / "inbox.jsonl"
                _append_jsonl(inbox_path, cmd)
                report["commands_routed"] += 1

    # ── Step 4: Save state ──
    _save_json(X_STATE, {
        "last_cycle": report["ts"],
        "total_prompts_ingested": report["prompts_ingested"],
        "target_accounts": TARGET_ACCOUNTS,
        "x_handle": X_HANDLE or "(not configured)",
        "paths": report["paths_available"],
    })

    return report


# ═══════════════════════════════════════════════════════════════════
# STATUS — what's configured, what's not
# ═══════════════════════════════════════════════════════════════════

def x_surface_status() -> dict[str, Any]:
    """Report on X control surface configuration status."""
    return {
        "schema": "x_control_surface.v1",
        "ts": _now(),
        "configured": any_x_surface_configured(),
        "paths": {
            "grok_native": {
                "available": grok_api_configured(),
                "requires": "XAI_API_KEY or GROK_API_KEY env var (Super Grok license)",
                "capabilities": ["x_user_search", "x_semantic_search", "x_keyword_search",
                                 "x_thread_fetch", "browse_page"],
                "cost": "~$0.01–0.05 per search (Grok API pricing)",
            },
            "x_api_direct": {
                "available": x_api_configured(),
                "requires": "X_API_KEY (bearer) + X_ACCESS_TOKEN (OAuth 2.0)",
                "capabilities": ["read timeline", "read mentions", "post tweets", "reply"],
                "cost": "$0 (X API v2 free tier: 1,500 posts/month)",
            },
            "fxtwitter_fallback": {
                "available": True,
                "requires": "nothing (free, no auth)",
                "capabilities": ["read public tweets by ID", "read public timelines"],
                "cost": "$0",
            },
        },
        "target_accounts": TARGET_ACCOUNTS,
        "ghost_x_handle": X_HANDLE or "(not set — set GHOST_X_HANDLE env var)",
        "prompts_ingested": len(list(X_PROMPTS_DIR.glob("*.md"))) if X_PROMPTS_DIR.is_dir() else 0,
    }
