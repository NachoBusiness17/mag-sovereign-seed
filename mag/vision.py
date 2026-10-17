"""vision — let the agents SEE (2026-08-25).

DeepSeek vision (`deepseek-v4-flash-vision-exp`, OpenAI-compatible, documented at
api-docs.deepseek.com/guides/vision): images in USER messages only (system/assistant
images -> 400), base64-inline / external URL / Files API file_id. Formats JPEG/PNG/GIF/
WebP. Images resize to ~800x800 -> <=384 tokens each. Body limit 48 MiB, image 32 MiB.

Self-steal: rides the deepseek provider (api.deepseek.com/v1, DEEPSEEK_API_KEY), the
browser-UA lesson from providers.py (Cloudflare 1010), and the work_contract envelope.

CLI: python -m mag.vision describe <image_path> ["prompt"]
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any

ROOT = Path(r"c:\Users\ESTATE_USER\Documents\projects\local_sovereign_agent")
SCHEMA = "vision.v1"
MODEL = "deepseek-v4-flash-vision-exp"
BASE = "https://api.deepseek.com/v1"

# browser UA (the 1010 lesson, providers.py 2026-08-24): bare urllib gets Cloudflare-blocked
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")


def _key() -> str:
    if not os.environ.get("DEEPSEEK_API_KEY"):
        try:
            for line in (ROOT / ".env").read_text(encoding="utf-8", errors="replace").splitlines():
                if line.startswith("DEEPSEEK_API_KEY="):
                    os.environ["DEEPSEEK_API_KEY"] = line.split("=", 1)[1].strip()
                    break
        except Exception:  # noqa: BLE001
            pass
    k = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not k:
        try:
            for line in (ROOT / ".env").read_text(encoding="utf-8", errors="replace").splitlines():
                if line.startswith("DEEPSEEK_SWARM_API_KEY="):
                    k = line.split("=", 1)[1].strip()
                    break
        except Exception:  # noqa: BLE001
            pass
    return k


def _image_url(image: str) -> str:
    """Local path -> base64 data URL; http(s) -> passed through (<=8192 chars)."""
    if image.startswith(("http://", "https://", "data:")):
        return image
    p = Path(image)
    b64 = base64.b64encode(p.read_bytes()).decode("utf-8")
    ext = (p.suffix or ".jpg").lower().lstrip(".")
    mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
            "gif": "image/gif", "webp": "image/webp"}.get(ext, "image/jpeg")
    return f"data:{mime};base64,{b64}"


def describe(image: str, prompt: str = "What is in this image?", *, detail: str = "auto",
             max_tokens: int = 1024) -> dict[str, Any]:
    """Ask the vision model to describe/analyze an image. Image in the USER message only."""
    prompt = (prompt or "What is in this image?").strip()
    key = _key()
    if not key:
        return {"ok": False, "schema": SCHEMA, "error": "no DEEPSEEK_API_KEY"}
    url = _image_url(image)
    body = json.dumps({
        "model": MODEL,
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": url, "detail": detail}},
        ]}],
        "max_tokens": max_tokens,
    }).encode("utf-8")
    req = urllib.request.Request(f"{BASE}/chat/completions", data=body, method="POST", headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {key}",
        "User-Agent": _UA,
    })
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            data = json.loads(r.read().decode("utf-8"))
        choice = (data.get("choices") or [{}])[0]
        usage = data.get("usage") or {}
        return {"ok": True, "schema": SCHEMA, "model": MODEL,
                "text": str((choice.get("message") or {}).get("content") or "").strip(),
                "prompt_tokens": int(usage.get("prompt_tokens") or 0),
                "completion_tokens": int(usage.get("completion_tokens") or 0),
                "detail": detail}
    except urllib.error.HTTPError as e:
        return {"ok": False, "schema": SCHEMA, "error": f"HTTP {e.code}: {e.read().decode('utf-8', errors='replace')[:300]}"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "schema": SCHEMA, "error": f"{type(e).__name__}: {str(e)[:200]}"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="vision", description="deepseek vision seat")
    sub = ap.add_subparsers(dest="cmd")
    p = sub.add_parser("describe")
    p.add_argument("image")
    p.add_argument("prompt", nargs="*", default=[])
    p.add_argument("--detail", default="auto", choices=["low", "high", "original", "auto"])
    p.add_argument("--max-tokens", type=int, default=1024)
    a = ap.parse_args(argv)
    if a.cmd == "describe":
        out = describe(a.image, " ".join(a.prompt) or "What is in this image?",
                       detail=a.detail, max_tokens=a.max_tokens)
    else:
        out = {"ok": False, "error": "usage: python -m mag.vision describe <image> [prompt]"}
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
