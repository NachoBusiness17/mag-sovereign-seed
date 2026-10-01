"""art_forge — queue-driven media harvest lane (python port of scripts/art_forge.mjs).

Born 2026-09-05: the mjs forge died of the usual disease — hardcoded posters,
hand-run, no owner. This one consumes a QUEUE, never invents spend:

  state/art_queue.jsonl   rows: {"id": "slug", "prompt": "...", "prefer": "grok"|"cogview"}
  state/art_queue.done.jsonl   processed rows (delete-as-append)

Dual lane: grok-2-image (x.ai) primary, cogview-4 (z.ai) fallback — same two
literal https doors as the mjs, keys from env or .env (never echoed). Max 3
per cycle (spend throttle). Writes dashboard/static/art/<id>.png, appends
forge_log.json, refreshes the gallery index only if it carries the
``<!-- forge-index -->`` marker (hand-curated doors are never clobbered).

Standalone:  python -m mag.art_forge
Lane call:   forge_once(root, limit=3) -> dict
"""

from __future__ import annotations

import base64
import datetime
import json
import os
import urllib.request
from pathlib import Path
from typing import Any

GROK_URL = "https://api.x.ai/v1/images/generations"
COGVIEW_URL = "https://api.z.ai/api/paas/v4/images/generations"
# literal doors only — the response URL may only be fetched if https and not a
# redirect (SSRF boundary kept identical in spirit to scripts/art_forge.mjs).


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ARG002
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def _env_or_dotenv(root: Path, name: str) -> str | None:
    v = os.environ.get(name)
    if v:
        return v
    try:
        for line in (root / ".env").read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if s.startswith(name + "="):
                return s.split("=", 1)[1].strip()
    except OSError:
        pass
    return None


def _post_json(url: str, payload: dict, key: str, timeout: int = 180) -> dict:
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    with _OPENER.open(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", errors="replace"))


def _fetch_bytes(url: str, timeout: int = 120) -> bytes:
    if not url.startswith("https://"):
        raise ValueError("non-https image url refused")
    with _OPENER.open(url, timeout=timeout) as r:
        return r.read()


def _gen_grok(prompt: str, key: str) -> bytes:
    d = _post_json(GROK_URL, {"model": "grok-2-image-1212", "prompt": prompt, "n": 1}, key)
    item = (d.get("data") or [{}])[0]
    if item.get("b64_json"):
        return base64.b64decode(item["b64_json"])
    if item.get("url"):
        return _fetch_bytes(item["url"])
    raise RuntimeError("grok: no image in response")


def _gen_cogview(prompt: str, key: str) -> bytes:
    d = _post_json(COGVIEW_URL, {"model": "cogview-4-250304", "prompt": prompt}, key)
    item = (d.get("data") or [{}])[0]
    if item.get("b64_json"):
        return base64.b64decode(item["b64_json"])
    if item.get("url"):
        return _fetch_bytes(item["url"])
    raise RuntimeError("cogview: no image in response")


def _refresh_index(artdir: Path) -> bool:
    idx = artdir / "index.html"
    if not idx.exists() or "<!-- forge-index -->" not in idx.read_text(encoding="utf-8", errors="replace"):
        return False
    pngs = sorted(p.name for p in artdir.glob("*.png"))
    listing = "\n".join(
        f'<figure><img src="{n}" loading="lazy"><figcaption>{n[:-4]}</figcaption></figure>'
        for n in pngs)
    text = idx.read_text(encoding="utf-8", errors="replace")
    idx.write_text(re.sub(r"<!-- forge-index -->.*?<!-- /forge-index -->",
                          f"<!-- forge-index -->{listing}<!-- /forge-index -->",
                          text, flags=re.S), encoding="utf-8")
    return True


def forge_once(root: Path | str, limit: int = 3) -> dict[str, Any]:
    root = Path(root)
    qpath = root / "state" / "art_queue.jsonl"
    donepath = root / "state" / "art_queue.done.jsonl"
    if not qpath.exists():
        return {"ok": True, "forged": 0, "note": "queue empty"}
    rows = [json.loads(l) for l in qpath.read_text(encoding="utf-8").splitlines() if l.strip()]
    todo, rest = rows[:limit], rows[limit:]
    if not todo:
        return {"ok": True, "forged": 0, "note": "queue empty"}

    xai = _env_or_dotenv(root, "XAI_API_KEY")
    zai = _env_or_dotenv(root, "ZAI_API_KEY")
    artdir = root / "dashboard" / "static" / "art"
    artdir.mkdir(parents=True, exist_ok=True)
    logpath = artdir / "forge_log.json"
    log = json.loads(logpath.read_text(encoding="utf-8")) if logpath.exists() else {}
    if not isinstance(log, dict):
        log = {}  # dict keyed by poster id (mjs-era shape), never a list

    done, errors = [], []
    for row in todo:
        rid, prompt = str(row.get("id") or "").strip(), str(row.get("prompt") or "").strip()
        if not rid or not prompt:
            errors.append({"id": rid or "?", "error": "missing id/prompt"})
            continue
        png, lane_used = None, None
        for lane_name, key, fn in (("grok", xai, _gen_grok), ("cogview", zai, _gen_cogview)):
            if not key:
                continue
            try:
                png, lane_used = fn(prompt, key), lane_name
                break
            except Exception as e:  # noqa: BLE001 — fall through to next lane
                errors.append({"id": rid, "lane": lane_name, "error": str(e)[:120]})
        if png is None:
            continue
        (artdir / f"{rid}.png").write_bytes(png)
        log[rid] = {"ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "lane": lane_used, "bytes": len(png)}
        done.append(rid)

    logpath.write_text(json.dumps(dict(list(log.items())[-200:]), indent=1), encoding="utf-8")
    if done:
        seen = set(done)
        remaining = rest + [r for r in todo if str(r.get("id")) not in seen]
        with qpath.open("w", encoding="utf-8") as f:
            for r in remaining:
                f.write(json.dumps(r) + "\n")
        with donepath.open("a", encoding="utf-8") as f:
            for rid in done:
                f.write(json.dumps({"id": rid, "ts": datetime.datetime.now(
                    datetime.timezone.utc).isoformat()}) + "\n")
        _refresh_index(artdir)
    return {"ok": True, "forged": len(done), "ids": done, "errors": errors,
            "left_in_queue": len(rest)}


if __name__ == "__main__":
    import sys
    r = forge_once(Path(__file__).resolve().parent.parent,
                   limit=int(sys.argv[1]) if len(sys.argv) > 1 else 3)
    print(json.dumps(r))
