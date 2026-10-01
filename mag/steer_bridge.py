"""Steer bridge — operator/assistant memory → agent steering channel.

Bridges external guidance (Copilot assistant, operator notes, drop files) into
the framework's interference layer (`operator_inbox` breadcrumbs), which the
agent drains at every checkpoint via `_absorb_operator_inbox`.

CLI (via `main.py steer-agent`):
  main.py steer-agent "guidance text"        # commit one steering note
  main.py steer-agent --sync                 # push new lines from the drop file
  main.py steer-agent --sync --file my.md    # custom drop file
  main.py steer-agent --status               # show inbox state

Drop-file convention (queue/steer_agent.md):
  Every non-empty, non-heading line is one steering note. `--sync` pushes only
  notes not yet seen (idempotent) so re-running never duplicates breadcrumbs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT

DEFAULT_DROP = ROOT / "queue" / "steer_agent.md"
SEEN_STATE = ROOT / "memory" / "working" / "steer_bridge_seen.json"
DEFAULT_SOURCE = "copilot-assistant"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_seen() -> set[str]:
    if not SEEN_STATE.is_file():
        return set()
    try:
        data = json.loads(SEEN_STATE.read_text(encoding="utf-8"))
        return set(data.get("seen") or [])
    except Exception:
        return set()


def _save_seen(seen: set[str]) -> None:
    SEEN_STATE.parent.mkdir(parents=True, exist_ok=True)
    SEEN_STATE.write_text(
        json.dumps(
            {"schema": "steer_bridge_seen.v1", "seen": sorted(seen), "updated": _now()},
            indent=2,
        ),
        encoding="utf-8",
    )


def steer(text: str, *, source: str = DEFAULT_SOURCE) -> dict[str, Any]:
    """Commit one guidance note to the agent steering channel."""
    from mag.operator_inbox import commit_guidance

    return commit_guidance(text, source=source)


def _drop_lines(path: Path) -> list[str]:
    """Non-empty, non-heading/comment lines from the drop file (markers stripped)."""
    if not path.is_file():
        return []
    out: list[str] = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith(("#", ">", "---", "```")):
            continue
        line = line.lstrip("-*0123456789. ").strip()
        if line:
            out.append(line)
    return out


def sync_guidance_file(
    path: Path | str | None = None,
    *,
    source: str = DEFAULT_SOURCE,
) -> dict[str, Any]:
    """Push new lines from the drop file into the inbox (idempotent by sha256)."""
    drop = Path(path) if path else DEFAULT_DROP
    seen = _load_seen()
    committed: list[dict[str, Any]] = []
    skipped: list[str] = []
    for line in _drop_lines(drop):
        h = hashlib.sha256(line.encode("utf-8")).hexdigest()
        if h in seen:
            skipped.append(line[:60])
            continue
        r = steer(line, source=source)
        if r.get("ok"):
            seen.add(h)
            committed.append({"id": (r.get("item") or {}).get("id"), "text": line[:80]})
        else:
            skipped.append(f"commit-error: {line[:60]}")
    _save_seen(seen)
    return {
        "ok": True,
        "schema": "steer_bridge_sync.v1",
        "drop_file": str(drop),
        "committed_n": len(committed),
        "skipped_n": len(skipped),
        "committed": committed[:20],
        "skipped": skipped[:10],
    }


def status() -> dict[str, Any]:
    from mag.operator_inbox import status as inbox_status

    return inbox_status()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="steer-agent",
        description="Steer the agent via operator_inbox breadcrumbs (drained at checkpoint).",
    )
    ap.add_argument("text", nargs="*", help="One-shot guidance text (or use --sync)")
    ap.add_argument("--sync", action="store_true", help="Push new lines from the drop file")
    ap.add_argument("--file", default=str(DEFAULT_DROP), help="Drop file path for --sync")
    ap.add_argument("--source", default=DEFAULT_SOURCE, help="Source tag (default copilot-assistant)")
    ap.add_argument("--status", action="store_true", help="Show inbox state")
    args = ap.parse_args(argv)

    if args.status:
        print(json.dumps(status(), indent=2, default=str)[:4000])
        return 0
    if args.sync:
        res = sync_guidance_file(args.file, source=args.source)
        print(json.dumps(res, indent=2, default=str)[:4000])
        return 0 if res.get("ok") else 1
    text = " ".join(args.text or []).strip()
    if not text:
        print('usage: main.py steer-agent "guidance" | --sync | --status', file=sys.stderr)
        return 2
    r = steer(text, source=args.source)
    print(json.dumps(r, indent=2, default=str)[:4000])
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
