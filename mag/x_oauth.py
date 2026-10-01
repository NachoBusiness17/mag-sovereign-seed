"""x_oauth — OAuth 2.0 Authorization Code + PKCE for the X API (user context).

Why: X API v2 POST /2/tweets requires USER-CONTEXT auth (OAuth 2.0 user token or
OAuth 1.0a), NOT an app-only bearer token. The X Premium ($8/mo) account carries
write access, so a user-context token lets us post as @GHOST_HANDLE through the
official API — ban-safe, no browser automation, no $100 tier.

Flow:
  1. Operator creates an X developer app (Premium) -> gets Client ID (+Secret).
  2. python -m mag.x_oauth start   -> prints authorize URL + runs a one-shot
     callback server on the redirect URI. Operator opens URL, logs in (their
     secret), authorizes @GHOST_HANDLE.
  3. python -m mag.x_oauth complete <code>  (or the server auto-captures)
     -> exchanges code for access+refresh tokens, stores locally (never printed).
  4. python -m mag.x_oauth post "<text>"  -> auto-refreshes then POST /2/tweets.

ENV (in .env, operator-filled):
  X_CLIENT_ID, X_CLIENT_SECRET, X_REDIRECT_URI (default http://127.0.0.1:8788/callback),
  GHOST_X_HANDLE (GHOST_HANDLE)

Schema: x_oauth.v1
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import sys
import threading
import webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlparse, parse_qs

try:
    from config import ROOT
except ImportError:
    ROOT = Path(__file__).resolve().parent.parent

import requests

SCHEMA = "x_oauth.v1"
AUTHORIZE_URL = "https://x.com/i/oauth2/authorize"
TOKEN_URL = "https://api.x.com/2/oauth2/token"
POST_URL = "https://api.x.com/2/tweets"
ME_URL = "https://api.x.com/2/users/me"
SCOPES = "users.read tweet.read tweet.write media.write like.write follows.write bookmark.write dm.read dm.write offline.access"

TOKENS = ROOT / "memory" / "runs" / "x_oauth" / "tokens.json"
OAUTH_STATE = ROOT / "memory" / "runs" / "x_oauth" / "state.json"

# Load X_* config from .env (values are stored there, not necessarily exported).
def _load_env_x() -> None:
    env_path = ROOT / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k = k.strip()
        if k.startswith("X_") and k not in os.environ:
            os.environ[k] = v.strip()


_load_env_x()

CLIENT_ID = os.environ.get("X_ClientID", os.environ.get("X_CLIENT_ID", ""))
CLIENT_SECRET = os.environ.get("X_ClientSecret", os.environ.get("X_CLIENT_SECRET", ""))
REDIRECT_URI = os.environ.get("X_REDIRECT_URI", "http://127.0.0.1:8788/callback")
HANDLE = os.environ.get("GHOST_X_HANDLE", "NachoQuixotic")  # token binds NachoQuixotic (verified 09-05 via me())


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _b64url(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")


def _configured() -> bool:
    return bool(CLIENT_ID)


# ── PKCE ────────────────────────────────────────────────────────────
def _make_pkce() -> tuple[str, str]:
    verifier = _b64url(secrets.token_bytes(48))
    challenge = _b64url(hashlib.sha256(verifier.encode("ascii")).digest())
    return verifier, challenge


# ── Step 1: build authorize URL ─────────────────────────────────────
def start(*, auto_server: bool = True) -> dict[str, Any]:
    if not _configured():
        return {"ok": False, "schema": SCHEMA,
                "error": "X_CLIENT_ID not set — create an X developer app and fill .env"}
    verifier, challenge = _make_pkce()
    state = secrets.token_urlsafe(16)
    _write_json(OAUTH_STATE, {"verifier": verifier, "state": state, "ts": _now()})
    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPES,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    url = f"{AUTHORIZE_URL}?{urlencode(params)}"
    if auto_server:
        threading.Thread(target=_run_callback_server, daemon=True).start()
    webbrowser.open(url)
    return {"ok": True, "schema": SCHEMA, "authorize_url": url,
            "redirect_uri": REDIRECT_URI,
            "note": "open the URL, log in as the account, authorize. Code auto-captured."}


_captured: dict[str, str] = {}


def _run_callback_server() -> None:
    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            q = parse_qs(urlparse(self.path).query)
            _captured["code"] = q.get("code", [""])[0]
            _captured["state"] = q.get("state", [""])[0]
            body = b"Authorization captured. You can close this tab and return to the terminal."
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    port = int(urlparse(REDIRECT_URI).port or 8788)
    try:
        HTTPServer(("127.0.0.1", port), H).handle_request()
    except OSError:
        pass


# ── Step 2: exchange code for tokens ────────────────────────────────
def complete(code: str) -> dict[str, Any]:
    st = _read_json(OAUTH_STATE)
    verifier = st.get("verifier", "")
    if not verifier:
        return {"ok": False, "schema": SCHEMA, "error": "no PKCE state — run start first"}
    data = {
        "code": code,
        "grant_type": "authorization_code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "code_verifier": verifier,
    }
    if CLIENT_SECRET:
        data["client_secret"] = CLIENT_SECRET
    try:
        r = requests.post(TOKEN_URL, data=data, timeout=30)
    except requests.RequestException as e:
        return {"ok": False, "schema": SCHEMA, "error": f"net: {e}"}
    if r.status_code != 200:
        return {"ok": False, "schema": SCHEMA, "error": r.text[:400]}
    tok = r.json()
    _write_json(TOKENS, {
        "access_token": tok.get("access_token", ""),
        "refresh_token": tok.get("refresh_token", ""),
        "expires_in": tok.get("expires_in", 7200),
        "scope": tok.get("scope", ""),
        "token_type": tok.get("token_type", ""),
        "issued_at": _now(),
    })
    return {"ok": True, "schema": SCHEMA, "note": "token stored locally",
            "scope": tok.get("scope"), "handle": HANDLE}


def refresh() -> dict[str, Any]:
    tok = _read_json(TOKENS)
    rt = tok.get("refresh_token", "")
    if not rt:
        return {"ok": False, "schema": SCHEMA, "error": "no refresh token"}
    data = {
        "grant_type": "refresh_token",
        "refresh_token": rt,
        "client_id": CLIENT_ID,
    }
    if CLIENT_SECRET:
        data["client_secret"] = CLIENT_SECRET
    try:
        r = requests.post(TOKEN_URL, data=data, timeout=30)
    except requests.RequestException as e:
        return {"ok": False, "schema": SCHEMA, "error": f"net: {e}"}
    if r.status_code != 200:
        return {"ok": False, "schema": SCHEMA, "error": r.text[:400]}
    t = r.json()
    tok["access_token"] = t.get("access_token", tok.get("access_token", ""))
    if t.get("refresh_token"):
        tok["refresh_token"] = t["refresh_token"]
    tok["issued_at"] = _now()
    _write_json(TOKENS, tok)
    return {"ok": True, "schema": SCHEMA, "note": "refreshed"}


def _access_token() -> tuple[str, str]:
    """Return (token, error). Auto-refresh if the old one is stale."""
    tok = _read_json(TOKENS)
    at = tok.get("access_token", "")
    if not at:
        return "", "no token — run start + complete first"
    issued = tok.get("issued_at", "")
    if issued:
        try:
            age_s = (datetime.now(timezone.utc) - datetime.fromisoformat(issued)).total_seconds()
            if age_s > max(int(tok.get("expires_in", 7200)) - 60, 0):
                rr = refresh()
                if not rr.get("ok"):
                    return "", rr.get("error", "refresh failed")
                tok = _read_json(TOKENS)
                at = tok.get("access_token", "")
        except Exception:
            pass
    return at, ""


# ── Step 3: post ────────────────────────────────────────────────────
MEDIA_URL = "https://api.x.com/2/media/upload"


def upload_media(image_path: str) -> dict[str, Any]:
    """v2 simple media upload (images <=5MB). Returns {media_id}."""
    at, err = _access_token()
    if not at:
        return {"ok": False, "schema": SCHEMA, "error": err}
    p = Path(image_path)
    if not p.exists():
        return {"ok": False, "schema": SCHEMA, "error": f"no file: {image_path}"}
    raw = p.read_bytes()
    if len(raw) > 5 * 1024 * 1024:
        return {"ok": False, "schema": SCHEMA, "error": f"file too large: {len(raw)} B"}
    mime = "image/png" if raw[:8] == b"\x89PNG\r\n\x1a\n" else (
        "image/jpeg" if raw[:3] == b"\xff\xd8\xff" else "application/octet-stream")
    if mime == "application/octet-stream":
        return {"ok": False, "schema": SCHEMA, "error": "not a PNG/JPEG"}
    try:
        r = requests.post(
            MEDIA_URL,
            headers={"Authorization": f"Bearer {at}", "User-Agent": f"{HANDLE}/0.1"},
            files={"media": (p.name, raw, mime)},
            data={"media_category": "tweet_image"},
            timeout=60,
        )
    except requests.RequestException as e:
        return {"ok": False, "schema": SCHEMA, "error": f"net: {e}"}
    if r.status_code not in (200, 201):
        return {"ok": False, "schema": SCHEMA, "error": r.text[:400]}
    j = r.json()
    mid = (j.get("data") or {}).get("id", "")
    return {"ok": True, "schema": SCHEMA, "media_id": mid}


def post(text: str, media_ids: list[str] | None = None, reply_to: str = "") -> dict[str, Any]:
    at, err = _access_token()
    if not at:
        return {"ok": False, "schema": SCHEMA, "error": err}
    payload: dict[str, Any] = {"text": text[:4000]}  # X Premium allows up to 4000 chars/post
    if media_ids:
        payload["media"] = {"media_ids": media_ids[:4]}
    if reply_to:
        payload["reply"] = {"in_reply_to_tweet_id": reply_to}
    headers = {
        "Authorization": f"Bearer {at}",
        "Content-Type": "application/json",
        "User-Agent": f"{HANDLE}/0.1",
    }
    try:
        r = requests.post(POST_URL, headers=headers, json=payload, timeout=30)
    except requests.RequestException as e:
        return {"ok": False, "schema": SCHEMA, "error": f"net: {e}"}
    if r.status_code not in (200, 201):
        return {"ok": False, "schema": SCHEMA, "error": r.text[:400]}
    d = r.json().get("data", {})
    pid = d.get("id", "")
    return {"ok": True, "schema": SCHEMA, "post_id": pid,
            "url": f"https://x.com/{HANDLE}/status/{pid}"}


def edit(post_id: str, text: str) -> dict[str, Any]:
    """Edit an existing post (within the edit window) to a new complete text."""
    at, err = _access_token()
    if not at:
        return {"ok": False, "schema": SCHEMA, "error": err}
    headers = {"Authorization": f"Bearer {at}", "Content-Type": "application/json"}
    payload = {"text": text[:4000], "edit_options": {"previous_post_id": post_id}}
    try:
        r = requests.put(f"https://api.x.com/2/tweets/{post_id}",
                         headers=headers, json=payload, timeout=30)
    except requests.RequestException as e:
        return {"ok": False, "schema": SCHEMA, "error": f"net: {e}"}
    if r.status_code not in (200, 201):
        return {"ok": False, "schema": SCHEMA, "error": r.text[:400]}
    d = r.json().get("data", {})
    pid = d.get("id", "")
    return {"ok": True, "schema": SCHEMA, "post_id": pid,
            "url": f"https://x.com/{HANDLE}/status/{pid}"}


def delete(post_id: str) -> dict[str, Any]:
    """Delete a post by id (tweet.write scope)."""
    at, err = _access_token()
    if not at:
        return {"ok": False, "schema": SCHEMA, "error": err}
    headers = {"Authorization": f"Bearer {at}"}
    try:
        r = requests.delete(f"https://api.x.com/2/tweets/{post_id}",
                            headers=headers, timeout=30)
    except requests.RequestException as e:
        return {"ok": False, "schema": SCHEMA, "error": f"net: {e}"}
    if r.status_code not in (200, 201):
        return {"ok": False, "schema": SCHEMA, "error": r.text[:400]}
    return {"ok": True, "schema": SCHEMA, "deleted": post_id}


def me() -> dict[str, Any]:
    at, err = _access_token()
    if not at:
        return {"ok": False, "schema": SCHEMA, "error": err}
    try:
        r = requests.get(ME_URL, headers={"Authorization": f"Bearer {at}"}, timeout=30)
    except requests.RequestException as e:
        return {"ok": False, "schema": SCHEMA, "error": f"net: {e}"}
    if r.status_code != 200:
        return {"ok": False, "schema": SCHEMA, "error": r.text[:400]}
    return {"ok": True, "schema": SCHEMA, "me": r.json().get("data", {})}


LIKE_URL = "https://api.x.com/2/users/{uid}/likes"


def _user_by_username(username: str) -> dict[str, Any]:
    at, err = _access_token()
    if not at:
        return {"ok": False, "schema": SCHEMA, "error": err}
    try:
        r = requests.get(
            f"https://api.x.com/2/users/by/username/{username}",
            headers={"Authorization": f"Bearer {at}"},
            timeout=30,
        )
    except requests.RequestException as e:
        return {"ok": False, "schema": SCHEMA, "error": f"net: {e}"}
    if r.status_code != 200:
        return {"ok": False, "schema": SCHEMA, "error": r.text[:400]}
    return {"ok": True, "schema": SCHEMA, "user": r.json().get("data", {})}


def follow(username: str) -> dict[str, Any]:
    """Follow a user as the authenticated account (requires follows.write)."""
    at, err = _access_token()
    if not at:
        return {"ok": False, "schema": SCHEMA, "error": err}
    u = _user_by_username(username.lstrip("@"))
    if not u.get("ok"):
        return u
    target = (u.get("user") or {}).get("id", "")
    if not target:
        return {"ok": False, "schema": SCHEMA, "error": "could not resolve user"}
    m = me()
    uid = (m.get("me") or {}).get("id", "")
    headers = {"Authorization": f"Bearer {at}", "Content-Type": "application/json"}
    try:
        r = requests.post(f"https://api.x.com/2/users/{uid}/following",
                          headers=headers, json={"target_user_id": target}, timeout=30)
    except requests.RequestException as e:
        return {"ok": False, "schema": SCHEMA, "error": f"net: {e}"}
    if r.status_code not in (200, 201):
        return {"ok": False, "schema": SCHEMA, "error": r.text[:400]}
    return {"ok": True, "schema": SCHEMA, "following": username,
            "user": (u.get("user") or {}).get("username")}


def recent_posts(username: str, count: int = 5) -> dict[str, Any]:
    """Read-only: fetch a user's most recent posts (to pick something genuine to engage with)."""
    at, err = _access_token()
    if not at:
        return {"ok": False, "schema": SCHEMA, "error": err}
    u = _user_by_username(username.lstrip("@"))
    if not u.get("ok"):
        return u
    target = (u.get("user") or {}).get("id", "")
    headers = {"Authorization": f"Bearer {at}"}
    try:
        r = requests.get(
            f"https://api.x.com/2/users/{target}/tweets?max_results={count}",
            headers=headers, timeout=30,
        )
    except requests.RequestException as e:
        return {"ok": False, "schema": SCHEMA, "error": f"net: {e}"}
    if r.status_code != 200:
        return {"ok": False, "schema": SCHEMA, "error": r.text[:400]}
    return {"ok": True, "schema": SCHEMA, "posts": r.json().get("data", [])}


def dm(username: str, text: str) -> dict[str, Any]:
    """Send a Direct Message to a user as the authenticated account (requires dm.write)."""
    at, err = _access_token()
    if not at:
        return {"ok": False, "schema": SCHEMA, "error": err}
    u = _user_by_username(username.lstrip("@"))
    if not u.get("ok"):
        return u
    target = (u.get("user") or {}).get("id", "")
    if not target:
        return {"ok": False, "schema": SCHEMA, "error": "could not resolve user"}
    headers = {"Authorization": f"Bearer {at}", "Content-Type": "application/json"}
    try:
        r = requests.post(
            f"https://api.x.com/2/dm_conversations/with/{target}/messages",
            headers=headers, json={"text": text[:1000]}, timeout=30,
        )
    except requests.RequestException as e:
        return {"ok": False, "schema": SCHEMA, "error": f"net: {e}"}
    if r.status_code not in (200, 201):
        return {"ok": False, "schema": SCHEMA, "error": r.text[:400]}
    return {"ok": True, "schema": SCHEMA, "dm_to": username, "note": "dm sent"}


def like(tweet_id: str) -> dict[str, Any]:
    """Like a post as the authenticated user (requires like.write scope)."""
    at, err = _access_token()
    if not at:
        return {"ok": False, "schema": SCHEMA, "error": err}
    m = me()
    uid = (m.get("me") or {}).get("id", "")
    if not uid:
        return {"ok": False, "schema": SCHEMA, "error": "could not resolve user id"}
    headers = {"Authorization": f"Bearer {at}", "Content-Type": "application/json"}
    try:
        r = requests.post(LIKE_URL.format(uid=uid), headers=headers,
                          json={"tweet_id": str(tweet_id)}, timeout=30)
    except requests.RequestException as e:
        return {"ok": False, "schema": SCHEMA, "error": f"net: {e}"}
    if r.status_code not in (200, 201):
        return {"ok": False, "schema": SCHEMA, "error": r.text[:400]}
    return {"ok": True, "schema": SCHEMA, "liked": str(tweet_id),
            "liked_by": HANDLE, "url": f"https://x.com/{HANDLE}/status/{tweet_id}"}


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="x-oauth")
    ap.add_argument("cmd", choices=["start", "complete", "post", "me", "refresh", "like", "follow", "recent", "dm", "edit", "delete", "status"])
    ap.add_argument("arg", nargs="*", default=[])
    args, _unknown = ap.parse_known_args(argv)
    args.arg = (args.arg or []) + _unknown
    body = " ".join(args.arg)
    if args.cmd == "start":
        print(json.dumps(start(), indent=2))
        # wait briefly for the callback server to capture a code
        for _ in range(120):
            if _captured.get("code"):
                break
            import time
            time.sleep(0.5)
        if _captured.get("code"):
            print(json.dumps(complete(_captured["code"]), indent=2))
    elif args.cmd == "complete":
        print(json.dumps(complete(body), indent=2))
    elif args.cmd == "post":
        # post "<text>" | post --media <path> --reply <tweet_id> "<text>"
        # flags are stripped from ANYWHERE in the arg list (order-free)
        mid, rto = "", ""
        rest, flags = [], {}
        pending = None
        for a in args.arg:
            if a in ("--media", "--reply"):
                pending = a
            elif pending == "--media":
                flags["media"] = a; pending = None
            elif pending == "--reply":
                flags["reply"] = a; pending = None
            else:
                rest.append(a)
        if "media" in flags:
            up = upload_media(flags["media"])
            if not up.get("ok"):
                print(json.dumps(up, indent=2)); sys.exit(1)
            mid = up.get("media_id", "")
        rto = flags.get("reply", "")
        body = " ".join(rest)
        print(json.dumps(post(body, [mid] if mid else None, rto), indent=2))
    elif args.cmd == "edit":
        # python -m mag.x_oauth edit "<post_id>" "<text>"
        parts = [a for a in args.arg if a.strip()]
        if len(parts) < 2:
            print(json.dumps({"ok": False, "error": "edit needs <post_id> <text>"}, indent=2))
            return 1
        print(json.dumps(edit(parts[0], " ".join(parts[1:])), indent=2))
    elif args.cmd == "delete":
        print(json.dumps(delete(body), indent=2))
    elif args.cmd == "like":
        print(json.dumps(like(body), indent=2))
    elif args.cmd == "follow":
        print(json.dumps(follow(body), indent=2))
    elif args.cmd == "recent":
        print(json.dumps(recent_posts(body), indent=2))
    elif args.cmd == "dm":
        # python -m mag.x_oauth dm "<@user>" "<text>"  (two args; text = the rest)
        parts = [a for a in args.arg if a.strip()]
        if len(parts) < 2:
            print(json.dumps({"ok": False, "error": "dm needs <username> <text>"}, indent=2))
            return 1
        print(json.dumps(dm(parts[0], " ".join(parts[1:])), indent=2))
    elif args.cmd == "me":
        print(json.dumps(me(), indent=2))
    elif args.cmd == "refresh":
        print(json.dumps(refresh(), indent=2))
    elif args.cmd == "status":
        tok = _read_json(TOKENS)
        print(json.dumps({
            "ok": True, "schema": SCHEMA,
            "client_id_set": bool(CLIENT_ID),
            "handle": HANDLE,
            "token_stored": bool(tok.get("access_token")),
            "scope": tok.get("scope", ""),
            "redirect_uri": REDIRECT_URI,
        }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
