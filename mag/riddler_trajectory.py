"""riddler_trajectory — the public RIB of the private session (the riddler protocol).

Operator's want (2026-09-08): session history that acts as the TRAJECTORY of what the
model worked on — without secrets or theft-enabling detail. Reference other
conversations without dropping a beat; token-enhance by design; map huge context to
the internal flash caching.

The mechanism (RenderMan RIB archival, per the compaction doc):
  - every step keeps its step_hash, timestamp, and ACTION SHAPE (what kind of move)
  - refs (file paths, entities, hashes) are KEPT — they are the decode keys and the
    KV-cache sharing surface (two sessions touching the same entity produce matching
    refs -> the flash cache hits across conversations)
  - content (input/output bodies, secrets) is REDACTED to stand-ins — the private
    chain holds the substance; the public feed holds the shape
  - a thief gets the silhouette of the work; only the private chain decodes it

CLI:
  python -m mag.riddler_trajectory emit [--out PATH] [--limit N]
  python -m mag.riddler_trajectory show [--last N]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TAPE = ROOT / "memory" / "runs" / "trajectory" / "steps.jsonl"
OUT_JSONL = ROOT / "watch" / "riddler" / "feed.jsonl"
OUT_MD = ROOT / "watch" / "riddler" / "feed.md"

# secrets never echoed: scrub anything key-shaped before it touches the feed
SECRET_PATTERNS = [
    re.compile(r"(sk-[A-Za-z0-9]{16,})"),
    re.compile(r"([A-Za-z0-9_]*(?:KEY|TOKEN|SECRET|PASSWORD)[A-Za-z0-9_]*\s*=\s*\S+)", re.I),
]


def scrub(text: str) -> str:
    for pat in SECRET_PATTERNS:
        text = pat.sub("[REDACTED]", text)
    return text


def action_shape(step: dict) -> str:
    """The shape of the move, not the substance: what kind of work, on what surface."""
    sid = str(step.get("session_id", ""))
    session = sid.split("-2026")[0] if "-2026" in sid else sid[:24]
    shape_bits = []
    try:
        inp = json.loads(step.get("input") or "{}")
        if isinstance(inp, dict):
            for k in ("kind", "shape", "lane", "salon", "scene"):
                if inp.get(k):
                    shape_bits.append(f"{k}={inp[k]}")
    except (ValueError, TypeError):
        pass
    reasoning = str(step.get("reasoning") or "")[:70]
    out_len = len(str(step.get("output") or ""))
    shape = f"{session}: {' · '.join(shape_bits) if shape_bits else 'step'}"
    if reasoning:
        shape += f" · {reasoning}"
    shape += f" · out {out_len}ch"
    return scrub(shape)


def refs_of(step: dict) -> list[str]:
    """The decode keys: hashes, salons, lanes. Pointers, not content."""
    refs = []
    try:
        inp = json.loads(step.get("input") or "{}")
        if isinstance(inp, dict):
            for k in ("brief_sha", "salon", "lane"):
                if inp.get(k):
                    refs.append(f"{k}={inp[k]}")
    except (ValueError, TypeError):
        pass
    if step.get("step_hash"):
        refs.append(f"hash={step['step_hash']}")
    return refs[:5]


def emit(limit: int, out_jsonl: Path, out_md: Path) -> int:
    rows = []
    if TAPE.is_file():
        for ln in TAPE.read_text(encoding="utf-8").splitlines():
            if ln.strip():
                try:
                    rows.append(json.loads(ln))
                except json.JSONDecodeError:
                    pass
    rows = rows[-limit:] if limit else rows
    out_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with out_jsonl.open("w", encoding="utf-8") as f:
        for r in rows:
            shape = scrub(action_shape(r))
            refs = refs_of(r)
            body = scrub(json.dumps(r, default=str))
            pub = {
                "step_hash": r.get("step_hash"),
                "ts": r.get("ts"),
                "session": hashlib.sha256(str(r.get("session_id")).encode()).hexdigest()[:8],
                "shape": shape,
                "refs": refs,
                "content_class": "REDACTED-BY-REFERENCE (decodes against the private chain)",
            }
            _ = body  # body never leaves; kept for the private chain only
            f.write(json.dumps(pub, ensure_ascii=False) + "\n")
    # the readable feed
    with out_md.open("w", encoding="utf-8") as f:
        f.write("# RIDDLER FEED — the public trajectory\n\n")
        f.write("_shape and refs public · substance redacted-by-reference · the private chain decodes_\n\n")
        for ln in out_jsonl.read_text(encoding="utf-8").splitlines():
            r = json.loads(ln)
            f.write(f"- `{r['step_hash']}` {r['ts']} — {r['shape']}\n")
    print(f"riddler feed: {len(rows)} steps -> {out_md.name}")
    return 0


def show(last: int) -> int:
    if not OUT_JSONL.is_file():
        print("feed empty — run emit first")
        return 1
    lines = OUT_JSONL.read_text(encoding="utf-8").splitlines()
    for ln in lines[-last:]:
        r = json.loads(ln)
        print(f"`{r['step_hash']}` {r['ts']}\n  {r['shape']}\n  refs: {r['refs']}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(prog="mag.riddler_trajectory")
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("emit")
    e.add_argument("--out")
    e.add_argument("--limit", type=int, default=0)
    sh = sub.add_parser("show")
    sh.add_argument("--last", type=int, default=10)
    args = ap.parse_args()
    if args.cmd == "emit":
        return emit(args.limit, OUT_JSONL, OUT_MD)
    if args.cmd == "show":
        return show(args.last)
    return 1


if __name__ == "__main__":
    sys.exit(main())
