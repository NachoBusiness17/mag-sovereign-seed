"""lane_probe.py — the law: each wired lane gets one minimal ping; we record
only whether it answered, never a byte of secret material. Key VALUES are
read from .env solely to be sent as auth headers, never printed or logged.

Usage: python -m mag.lane_probe --once
Appends one JSONL row per lane to watch/lane_probe.jsonl:
  {ts, lane, ok, latency_ms, error}
"""

import argparse
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = REPO_ROOT / ".env"
OUT_PATH = REPO_ROOT / "watch" / "lane_probe.jsonl"

LANES = [
    {
        "lane": "deepseek",
        "env_key": "DEEPSEEK_API_KEY",
        "url": "https://api.deepseek.com/v1/chat/completions",
        "model": "deepseek-chat",
    },
    {
        "lane": "zai",
        "env_key": "ZAI_API_KEY",
        "url": "https://api.z.ai/api/paas/v4/chat/completions",
        "model": "glm-4.5-flash",
    },
    {
        "lane": "groq",
        "env_key": "GROQ_API_KEY",
        "url": "https://api.groq.com/openai/v1/chat/completions",
        "model": "openai/gpt-oss-20b",
    },
]

TIMEOUT_S = 20
MAX_TOKENS = 8


def load_env_key_names(env_path: Path) -> list:
    """Return the KEY NAMES defined in .env. Values are never exposed."""
    if not env_path.exists():
        raise FileNotFoundError(f"missing .env at {env_path}")
    names = []
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        names.append(line.split("=", 1)[0].strip())
    return names


def get_env_value(env_path: Path, key: str) -> str:
    """Read one key's value from .env for header use only."""
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith(key + "="):
            val = line.split("=", 1)[1].strip().strip('"').strip("'")
            if not val:
                raise ValueError(f"{key} is set but empty")
            return val
    raise KeyError(f"{key} not present in .env")


def ping_lane(lane: dict, api_key: str) -> dict:
    """One minimal OpenAI-compatible chat request. Returns result row."""
    payload = json.dumps({
        "model": lane["model"],
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": MAX_TOKENS,
    }).encode("utf-8")
    req = urllib.request.Request(
        lane["url"],
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            if resp.status != 200:
                raise RuntimeError(f"http {resp.status}")
        latency_ms = round((time.monotonic() - t0) * 1000)
        return {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "lane": lane["lane"],
            "ok": True,
            "latency_ms": latency_ms,
            "error": "",
        }
    except Exception as exc:
        latency_ms = round((time.monotonic() - t0) * 1000)
        return {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "lane": lane["lane"],
            "ok": False,
            "latency_ms": latency_ms,
            "error": f"{type(exc).__name__}: {exc}",
        }


def append_rows(rows: list, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def run_once() -> list:
    key_names = load_env_key_names(ENV_PATH)
    rows = []
    for lane in LANES:
        if lane["env_key"] not in key_names:
            rows.append({
                "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "lane": lane["lane"],
                "ok": False,
                "latency_ms": 0,
                "error": f"missing {lane['env_key']} in .env",
            })
            continue
        api_key = get_env_value(ENV_PATH, lane["env_key"])
        rows.append(ping_lane(lane, api_key))
    append_rows(rows, OUT_PATH)
    for row in rows:
        status = "OK " if row["ok"] else "FAIL"
        print(f"{status} {row['lane']} {row['latency_ms']}ms {row['error']}")
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="probe wired lanes once")
    parser.add_argument("--once", action="store_true", required=True)
    args = parser.parse_args()
    if args.once:
        run_once()


if __name__ == "__main__":
    main()
