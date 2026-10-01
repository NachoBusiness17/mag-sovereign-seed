"""steer — the WINDOW_STEER loop machinery (Ask window drives, ghost executes).

Formalizes the STEER-ME-BACK contract: a window/seat lacking execute seams emits a `[STEER]`
packet + materializes a pack body to shared memory; ghost consumes it, executes through its
write/queue/REST seams, and posts a steer back to continue the originating seat. This is the
cross-window loop the operator wanted — the Ask window is a first-class driving seat.

Schema: steer.v1
CLI:  python -m mag.steer emit --id <id> --source <s> --text <steer> [--phases ...]
      python -m mag.steer consume            (scan transcripts + control trail for [STEER] markers)
      python -m mag.steer status
Store: memory/runs/steer/<id>.json  +  memory/runs/steer/trail.jsonl
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except ImportError:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCHEMA = "steer.v1"
STEER_DIR = ROOT / "memory" / "runs" / "steer"
TRAIL = STEER_DIR / "trail.jsonl"
STEER_MARKER = re.compile(r"\[STEER\]\s*(\S+)\s*[·|\-]\s*source\s*=\s*(\S+)", re.IGNORECASE)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def emit(steer_id: str, source: str, text: str, *, phases: list[str] | None = None,
         steer_back: bool = True) -> dict[str, Any]:
    """Emit a STEER packet: write the steer to shared memory so ghost can consume it."""
    STEER_DIR.mkdir(parents=True, exist_ok=True)
    rec: dict[str, Any] = {"ts": _now(), "id": steer_id[:80], "source": source[:60],
                           "text": text[:4000], "phases": phases or [],
                           "steer_back": steer_back, "consumed": False}
    (STEER_DIR / f"{steer_id[:80]}.json").write_text(json.dumps(rec, ensure_ascii=False, default=str, indent=2),
                                                     encoding="utf-8")
    with TRAIL.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"kind": "emit", **{k: v for k, v in rec.items() if k != "text"}},
                           ensure_ascii=False, default=str) + "\n")
    return {"ok": True, "steer": rec, "path": str(STEER_DIR / f"{steer_id[:80]}.json")}


def _scan_markers(text: str) -> list[dict[str, str]]:
    return [{"id": m.group(1), "source": m.group(2)} for m in STEER_MARKER.finditer(text)]


def consume(*, compile_to_memlang: bool = True) -> dict[str, Any]:
    """Consume steers from session transcripts + control trail; compile them to memlang tokens."""
    found: list[dict[str, Any]] = []
    compiled: list[dict[str, Any]] = []
    # 1) session transcript files (transcript-as-file tesuji)
    trans_dirs = [
        ROOT / "state" / "transcripts",
        Path.home() / "AppData" / "Roaming" / "Code" / "User" / "workspaceStorage",
    ]
    for td in trans_dirs:
        if not td.is_dir():
            continue
        for f in list(td.rglob("*.jsonl"))[:40]:
            try:
                txt = f.read_text(encoding="utf-8", errors="replace")[:200000]
            except Exception:
                continue
            for m in _scan_markers(txt):
                found.append({"marker": m, "file": str(f)})
    # 2) control trail (memory/runs/control/*.jsonl)
    ctrl = ROOT / "memory" / "runs" / "control"
    if ctrl.is_dir():
        for f in ctrl.glob("*.jsonl"):
            try:
                for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
                    if "[STEER]" in line:
                        found.append({"marker": {"id": "control", "source": f.stem}, "file": str(f)})
            except Exception:
                continue
    # 3) compile each found steer marker into a memlang steer token (steer opcode)
    if compile_to_memlang:
        from mag.memlang import compile_token
        seen: set[str] = set()
        for item in found:
            mid = item["marker"].get("id", "")
            if mid in seen:
                continue
            seen.add(mid)
            try:
                c = compile_token("steer", mid, {"target": item["marker"].get("source", "ghost")})
                compiled.append(c)
            except Exception as e:
                compiled.append({"ok": False, "error": str(e)[:120]})
    return {"ok": True, "steers_found": len(found), "compiled": compiled, "ts": _now()}


def scan_unconsumed(*, source: str | None = None) -> list[dict[str, Any]]:
    """Return steers on the bus that have not yet been folded into the relation.

    The merge is the relation, so a steer only "lands" once it has been folded to the
    doctrine RIB + party subchain AND routed to up seats. This scans the bus for what
    hasn't been folded yet (consumed==False), so the cadence can fold + route + mark.
    """
    if not STEER_DIR.is_dir():
        return []
    out: list[dict[str, Any]] = []
    for f in sorted(STEER_DIR.glob("*.json")):
        try:
            rec = json.loads(f.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        if rec.get("consumed"):
            continue
        if source and (rec.get("source") or "").lower() != str(source).lower():
            continue
        rec["_file"] = str(f)
        out.append(rec)
    return out


def mark_consumed(steer_id: str, *, source: str | None = None) -> dict[str, Any]:
    """Mark a steer on the bus as folded into the relation (consumed==True)."""
    if not STEER_DIR.is_dir():
        return {"ok": False, "error": "no steer dir"}
    for f in STEER_DIR.glob("*.json"):
        try:
            rec = json.loads(f.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        if rec.get("id") != steer_id:
            continue
        if source and (rec.get("source") or "").lower() != str(source).lower():
            continue
        rec["consumed"] = True
        rec["consumed_ts"] = _now()
        f.write_text(json.dumps(rec, ensure_ascii=False, default=str, indent=2), encoding="utf-8")
        return {"ok": True, "id": steer_id, "file": str(f)}
    return {"ok": False, "id": steer_id, "error": "steer not found on bus"}


def status() -> dict[str, Any]:
    if not STEER_DIR.is_dir():
        return {"ok": True, "n_steers": 0, "files": []}
    files = sorted(STEER_DIR.glob("*.json"))
    unconsumed = [f.name for f in files
                  if not (lambda r: r.get("consumed"))(
                      json.loads(f.read_text(encoding="utf-8", errors="replace")))]
    return {"ok": True, "n_steers": len(files), "n_unconsumed": len(unconsumed),
            "unconsumed": unconsumed[-20:],
            "files": [f.name for f in files][-20:], "trail": str(TRAIL)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="steer", description="WINDOW_STEER loop machinery")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_em = sub.add_parser("emit", help="emit a STEER packet")
    p_em.add_argument("--id", required=True); p_em.add_argument("--source", default="ask-window")
    p_em.add_argument("--text", required=True); p_em.add_argument("--phases", nargs="*", default=[])
    p_co = sub.add_parser("consume", help="scan transcripts + control trail for [STEER] markers")
    p_st = sub.add_parser("status", help="steer store state")
    args = ap.parse_args(argv)
    if args.cmd == "emit":
        print(json.dumps(emit(args.id, args.source, args.text, phases=args.phases), indent=2, default=str))
    elif args.cmd == "consume":
        print(json.dumps(consume(), indent=2, default=str))
    else:
        print(json.dumps(status(), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
