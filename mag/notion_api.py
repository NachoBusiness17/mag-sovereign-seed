"""Notion API body — token-gated writable knowledge surface (2026-08-25).

One self, many bodies: this makes Notion a REAL writable body for the fleet.
Works only when NOTION_API_KEY is in .env. To enable:
  1. Create an integration at https://www.notion.so/my-integrations
  2. Copy the internal integration token into .env as NOTION_API_KEY
  3. Share the target page/database with the integration ("...connections")
Until then the mailbox bridge (watch/notion_bridge.py) is the GUI path.

CLI:
  python -m mag.notion_api status                 # token present? (+ self-check)
  python -m mag.notion_api create "Title" "para one|para two" [--parent <page_id>]
  python -m mag.notion_api search "query"

urllib only — no new deps. Bounded retry on 429/rate-limit. Never logs the token.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

API = "https://api.notion.com/v1"
VERSION = "2022-06-28"
ENV_KEY = "NOTION_API_KEY"
MAX_RETRY = 3


def _load_dotenv() -> None:
    """Tiny .env loader (values only — never echoes secrets)."""
    p = ROOT / ".env"
    if not p.is_file():
        return
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _headers() -> dict[str, str]:
    key = os.environ.get(ENV_KEY) or ""
    return {
        "Authorization": f"Bearer {key}",
        "Notion-Version": VERSION,
        "Content-Type": "application/json",
    }


def token_status() -> dict:
    """Token present? (honest — this is the gate for the writable body.)"""
    _load_dotenv()
    present = bool(os.environ.get(ENV_KEY))
    return {
        "ok": present,
        "body": "notion",
        "token_present": present,
        "note": "add NOTION_API_KEY to .env (integration token) to make Notion writable",
        "mailbox_path": str(ROOT / "watch" / "notion_bridge.py"),
    }


def _post(path: str, body: dict) -> dict:
    _load_dotenv()
    key = os.environ.get(ENV_KEY) or ""
    if not key:
        return {"ok": False, "error": "no NOTION_API_KEY in .env", "status": 401}
    data = json.dumps(body).encode("utf-8")
    for attempt in range(MAX_RETRY):
        req = urllib.request.Request(f"{API}{path}", data=data, headers=_headers(), method="POST")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            code = e.code
            try:
                err = json.loads(e.read().decode("utf-8", errors="replace"))
            except Exception:  # noqa: BLE001
                err = {"message": str(e)}
            if code == 429 and attempt < MAX_RETRY - 1:
                time.sleep(2 ** attempt)
                continue
            return {"ok": False, "status": code, "code": err.get("code"), "message": err.get("message")}
        except urllib.error.URLError as e:
            return {"ok": False, "error": str(e.reason)}
    return {"ok": False, "status": 429, "message": "rate limited after retries"}


def paragraph(text: str) -> dict:
    return {"object": "block", "type": "paragraph",
            "paragraph": {"rich_text": [{"type": "text", "text": {"content": text[:1999]}}]}}


def heading(text: str) -> dict:
    return {"object": "block", "type": "heading_2",
            "heading_2": {"rich_text": [{"type": "text", "text": {"content": text[:1999]}}]}}


def _resolve_parent() -> str | None:
    """Auto-find a page the integration can write under (self-heal: no manual parent id needed).
    Returns None when the integration has NO workspace access — the real blocker."""
    res = _post("/search", {"page_size": 20})
    for r in (res.get("results") or []):
        if r.get("object") == "page":
            return r.get("id")
    return None


def create_page(title: str, paragraphs: list[str], parent_page_id: str | None = None) -> dict:
    """Create a page. Auto-resolves a parent via search when none is given. If the
    integration has no access to any page, returns the exact unblock (one click in Notion)."""
    if not parent_page_id:
        parent_page_id = _resolve_parent()
    if not parent_page_id:
        return {"ok": False, "status": 403,
                "code": "no_access",
                "message": ("The integration can't see any page. One click fixes it: in Notion, "
                            "open any page -> '...' top right -> Connections -> add this "
                            "integration. Then re-run — parent auto-resolves.")}
    parent = {"page_id": parent_page_id}
    children = []
    for para in paragraphs:
        if para.strip().endswith(":") and len(para.strip()) <= 60:
            children.append(heading(para.strip().rstrip(":")))
        else:
            children.append(paragraph(para))
    body = {
        "parent": parent,
        "properties": {"title": {"title": [{"text": {"content": title[:1999]}}]}},
        "children": children[:100],
    }
    return _post("/pages", body)


def search(query: str) -> dict:
    return _post("/search", {"query": query, "page_size": 10})


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] == "status":
        print(json.dumps(token_status(), indent=2))
        return 0
    cmd = argv[0]
    if cmd == "create":
        if len(argv) < 3:
            print("usage: python -m mag.notion_api create <title> <'para|para'> [--parent <id>]")
            return 2
        parent = None
        if "--parent" in argv:
            i = argv.index("--parent")
            parent = argv[i + 1] if i + 1 < len(argv) else None
        title = argv[1]
        paras = [p for p in argv[2].split("|") if p.strip()]
        res = create_page(title, paras, parent)
        print(json.dumps(res, indent=2, ensure_ascii=False)[:1200])
        return 0 if res.get("ok", True) and res.get("object") == "page" else 1
    if cmd == "search":
        if len(argv) < 2:
            print("usage: python -m mag.notion_api search <query>")
            return 2
        res = search(argv[1])
        print(json.dumps(res, indent=2, ensure_ascii=False)[:1200])
        return 0 if res.get("ok", True) and res.get("object") == "list" else 1
    print(f"unknown command: {cmd}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
