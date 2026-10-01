#!/usr/bin/env python3
"""board_directive — the board -> switchboard ADAPTER (thin rib, NOT an authority).

Correction (operator verdict + elder, 2026-08-30): the switchboard already owns
authorization. mag/switchboard.py::steer_drop (tier-bounded pigeonhole drop) and
route_intent (conductor + mesh routing) ARE the authority boundary. This module
must NOT invent a second one — it only DECODES a board post into a typed proposal
and DELEGATES to the existing switchboard by subprocess.

The real gap (verified in bytes):
  swarm_tools.blackboard_post() writes bb-NNNNN.json DIRECTLY to disk with no
  switchboard grant, tier check, or budget. The image board (/board/room.jsonl)
  has NO path to action at all today. This adapter is the first leg of making
  board -> proposal -> switchboard -> effect the enforced path.

Law: $0 by construction (no model calls). Deterministic marker decode only.
Marker rules (conservative by default):
  - rec["steer"] truthy                         -> directive
  - text starts >>steer/!steer/>>direct/!direct/>>route/!route -> directive
  - rec["seat"] in AUTHORITY_SEATS (empty = no auto-authorized seat)
  Everything else -> rejected. A roast never routes.

Typed proposal emitted (switchboard-shaped, verdict schema):
  {kind, actor, target, requested_effect, requested_capabilities,
   memory_scope, budget, ttl_seconds, provenance, parent}

Delegation (subprocess, existing organs only):
  requested_effect == "route" -> python -m mag.seat_dispatch route <goal>
  requested_effect == "steer" -> python -m mag.switchboard drop <target> <context>
  (dry flag passes through; no writes, no verkle tie — switchboard trails itself)

Usage:
  python -m mag.board_directive gate --post <json-line-or-file> [--dry]
  echo '<json-line>' | python -m mag.board_directive gate --stdin [--dry]
"""
import argparse
import json
import subprocess
import sys
import time

ROOT = None

# Operator-only. Empty = no seat auto-authorized; explicit markers still pass.
AUTHORITY_SEATS: list[str] = []

MARKER_PREFIXES = (">>steer", "!steer", ">>direct", "!direct", ">>route", "!route")


class _Directive:
    """Typed proposal — switchboard-shaped, per the verdict schema."""
    def __init__(self, *, effect, actor, target, text, reason):
        self.effect = effect          # "route" | "steer"
        self.actor = actor
        self.target = target
        self.text = text
        self.reason = reason

    def to_proposal(self):
        budget = "low" if any(w in self.text.lower() for w in ("scut", "canvas", "local", "fast")) else "high"
        return {
            "kind": "proposal",
            "actor": self.actor,
            "target": self.target or "",
            "requested_effect": "invoke_" + self.effect,
            "requested_capabilities": [],
            "memory_scope": "scratch",
            "budget": {"tier": budget, "max_usd": None, "max_calls": None},
            "ttl_seconds": 900,
            "provenance": self.reason,
            "parent": None,
        }


def _decode(rec: dict) -> _Directive | None:
    """Deterministic marker decode. Returns a typed directive or None (rejected)."""
    text = str(rec.get("text") or "").strip()
    actor = str(rec.get("seat") or rec.get("actor") or "unknown")
    if rec.get("steer"):
        return _Directive(effect="route", actor=actor, target=str(rec.get("target") or ""),
                          text=text, reason="steer-flag")
    if actor and actor in AUTHORITY_SEATS:
        return _Directive(effect="route", actor=actor, target=str(rec.get("target") or ""),
                          text=text, reason=f"authority-seat:{actor}")
    low = text.lower()
    for pfx in MARKER_PREFIXES:
        if low.startswith(pfx.lower()):
            body = text[len(pfx):].strip()
            # Prefix punctuation is framing, not part of the command name.
            # The previous rstrip-based check never removed leading `>>`/`!`,
            # so even an explicit steer marker was silently classified as a
            # route. Keep this deterministic and closed over the enum.
            command = pfx.lstrip(">!").lower()
            effect = "steer" if command == "steer" else "route"
            return _Directive(effect=effect, actor=actor, target="", text=body, reason=f"marker:{pfx}")
    return None


def _spawn(cmd, timeout=120):
    try:
        p = subprocess.run(cmd, cwd=str(ROOT) if ROOT else None, capture_output=True,
                           timeout=timeout, encoding="utf-8", errors="replace")
        return {"cmd": " ".join(cmd), "rc": p.returncode, "ok": p.returncode == 0,
                "head": (p.stdout or "")[:600], "err": (p.stderr or "")[:300]}
    except Exception as e:
        return {"cmd": " ".join(cmd), "rc": -1, "ok": False, "head": "", "err": str(e)[:300]}


def _load_post(args) -> dict | None:
    raw = ""
    if args.stdin:
        raw = sys.stdin.read()
    elif args.post:
        from pathlib import Path
        p = Path(args.post)
        raw = p.read_text(encoding="utf-8", errors="replace") if p.is_file() else args.post
    if not raw.strip():
        return None
    raw = raw.strip().splitlines()[-1] if "\n" in raw else raw.strip()
    try:
        rec = json.loads(raw)
        return rec if isinstance(rec, dict) else None
    except Exception:
        return {"text": raw, "seat": args.seat or "unknown", "raw": True}


def cmd_gate(args) -> int:
    rec = _load_post(args)
    if rec is None:
        print(json.dumps({"ok": False, "err": "no post provided"}))
        return 1
    d = _decode(rec)
    if d is None:
        print(json.dumps({"ok": True, "passed": False, "reason": "no-marker",
                          "note": "rejected by gate — a roast never routes"}))
        return 0

    proposal = d.to_proposal()
    # Delegate routing to the single seat interface. The board remains a
    # proposal surface; seat_dispatch route ranks bodies but does not launch
    # one without an explicit operator task request.
    if args.dry:
        delegated = {"ok": True, "dry": True, "skipped": "delegation to switchboard skipped"}
    elif d.effect == "steer":
        target = d.target or ""
        ctx = d.text
        delegated = _spawn([sys.executable, "-m", "mag.switchboard", "drop",
                            target or ctx[:60], ctx, "--from", d.actor])
    else:  # route
        delegated = _spawn([sys.executable, "-m", "mag.seat_dispatch", "route", d.text])

    out = {"ok": True, "passed": True, "reason": d.reason,
           "proposal": proposal,
           "delegated_to": "seat_dispatch" if d.effect == "route" else "switchboard",
           "switchboard": delegated}
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0


def main() -> int:
    global ROOT
    from pathlib import Path
    ROOT = Path(__file__).resolve().parents[1]
    ap = argparse.ArgumentParser(prog="mag.board_directive")
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("gate", help="decode one board post -> typed proposal -> delegate to switchboard")
    g.add_argument("--post", default="", help="jsonl line, or path to a file holding one")
    g.add_argument("--stdin", action="store_true", help="read the post line from stdin")
    g.add_argument("--seat", default="", help="seat label when raw text has none")
    g.add_argument("--dry", action="store_true", help="decode only; skip switchboard delegation")
    args = ap.parse_args()
    return cmd_gate(args)


if __name__ == "__main__":
    raise SystemExit(main())
