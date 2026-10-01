"""Browser / computer-use seat — allowlisted surfaces only.

Place for OpenClaw (or Playwright-isolated profile) so Mag can hit the web
the way ChatGPT computer-use does — but only pre-approved hosts/windows.
Residual stays local; this module is the gate, not a free browser.

  enabled: false until a seat binary is installed and operator flips the flag.
  configs/browser_env.yaml — hosts + window title patterns.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from config import ROOT

CONFIG_PATH = ROOT / "configs" / "browser_env.yaml"
SCHEMA = "mag_browser_env.v1"


def _default_cfg() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "enabled": False,
        "mode": "allowlist",
        "driver": "none",  # none | openclaw | playwright
        "hosts": [
            "chat.openai.com",
            "chatgpt.com",
            "claude.ai",
            "grok.x.ai",
            "x.com",
            "github.com",
            "localhost",
            "127.0.0.1",
        ],
        "windows": [
            {"title_contains": "ChatGPT"},
            {"title_contains": "Claude"},
            {"title_contains": "Grok"},
            {"title_contains": "GitHub"},
        ],
        "notes": (
            "OpenClaw or a Mag-managed Playwright profile = computer-use seat. "
            "Only allowlisted hosts/windows. Flip enabled when driver is ready."
        ),
    }


def load_config() -> dict[str, Any]:
    cfg = _default_cfg()
    if not CONFIG_PATH.is_file():
        return cfg
    try:
        text = CONFIG_PATH.read_text(encoding="utf-8")
    except OSError:
        return cfg
    # Minimal YAML-ish (key: value / lists) without requiring PyYAML for gate
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(text) or {}
        if isinstance(data, dict):
            cfg.update(data)
            return cfg
    except Exception:
        pass
    return cfg


def host_from_url(url: str) -> str:
    u = (url or "").strip()
    if not u:
        return ""
    if "://" not in u:
        u = "https://" + u
    try:
        return (urlparse(u).hostname or "").lower()
    except Exception:
        return ""


def is_host_allowed(url_or_host: str, cfg: dict[str, Any] | None = None) -> bool:
    cfg = cfg or load_config()
    if not cfg.get("enabled"):
        return False
    host = host_from_url(url_or_host) or (url_or_host or "").lower().strip()
    if not host:
        return False
    allowed = [str(h).lower().strip() for h in (cfg.get("hosts") or []) if h]
    for a in allowed:
        if host == a or host.endswith("." + a):
            return True
    return False


def is_window_allowed(title: str, cfg: dict[str, Any] | None = None) -> bool:
    cfg = cfg or load_config()
    if not cfg.get("enabled"):
        return False
    t = (title or "").strip()
    if not t:
        return False
    for rule in cfg.get("windows") or []:
        if not isinstance(rule, dict):
            continue
        needle = str(rule.get("title_contains") or "").strip()
        if needle and needle.lower() in t.lower():
            return True
        pat = str(rule.get("title_regex") or "").strip()
        if pat:
            try:
                if re.search(pat, t, re.I):
                    return True
            except re.error:
                continue
    return False


def status() -> dict[str, Any]:
    cfg = load_config()
    driver = str(cfg.get("driver") or "none").lower()
    openclaw_hint = ROOT.parent / "openclaw"
    return {
        "schema": SCHEMA,
        "ok": True,
        "enabled": bool(cfg.get("enabled")),
        "mode": cfg.get("mode") or "allowlist",
        "driver": driver,
        "hosts": list(cfg.get("hosts") or [])[:24],
        "windows": list(cfg.get("windows") or [])[:12],
        "config_path": str(CONFIG_PATH.relative_to(ROOT)) if CONFIG_PATH.is_file() else str(CONFIG_PATH),
        "openclaw_repo_nearby": openclaw_hint.is_dir(),
        "ready": bool(cfg.get("enabled")) and driver in ("openclaw", "playwright"),
        "notes": cfg.get("notes") or "",
        "hint": (
            "Browser seat off — edit configs/browser_env.yaml (enabled + driver) "
            "when OpenClaw/Playwright is installed."
            if not cfg.get("enabled")
            else f"Browser seat mode={cfg.get('mode')} driver={driver}"
        ),
    }


def ensure_config_file() -> Path:
    """Write default allowlist if missing (idempotent)."""
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not CONFIG_PATH.is_file():
        # Prefer real YAML for operator edit
        body = """# Mag browser / computer-use seat (OpenClaw or Playwright later)
# Only pre-approved hosts and window titles. Residual stays local.
schema: mag_browser_env.v1
enabled: false
mode: allowlist
driver: none   # none | openclaw | playwright
hosts:
  - chat.openai.com
  - chatgpt.com
  - claude.ai
  - grok.x.ai
  - x.com
  - github.com
  - localhost
  - 127.0.0.1
windows:
  - title_contains: ChatGPT
  - title_contains: Claude
  - title_contains: Grok
  - title_contains: GitHub
notes: >
  Flip enabled when a driver is installed. Mag routes goals; this seat
  only opens allowlisted web surfaces (ChatGPT-style computer use, gated).
"""
        CONFIG_PATH.write_text(body, encoding="utf-8")
    return CONFIG_PATH
