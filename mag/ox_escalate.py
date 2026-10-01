"""ox_escalate — the smallest-slice escalation path: deterministic-first, escalate to the free
frontier seat on NO_HANDLER, validate against a schema, commit to a ledger, cache identical calls.

THIS IS THE SEAT-CONTRACT'S "SMALLEST FIRST STEP" (~50 lines), built from ox-alpha's own design
(see handoff/OX_SEAT_AND_SEAT_CONTRACT_20260822.md):
  1. deterministic handler registry — resolve $0 first.
  2. escalate on FAILURE (NO_HANDLER), never on task type.
  3. "The LLM proposes; determinism disposes" — the seat's output must pass schema validation and
     be committed by the deterministic core (sovereignty stays with the core).
  4. append-only ledger keyed by task_id; response cache so the same question never costs twice.
  5. T2+ public only (retained-log provider).

Schema: ox_escalate.v1 · deterministic core + free-seat escalation seam · reuse: ox_seat
CLI: python -m mag.ox_escalate route <intent> --task "<json>"
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "ox_escalate.v1"
LEDGER = ROOT / "handoff" / "ox_ledger.jsonl"

# ── the seat expects a strict JSON object; this is the validation gate (determinism disposes) ──
EXPECTED_SCHEMA = {"type": "object", "required": ["intent", "answer"]}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _hash(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]


# ── deterministic handler registry (resolve $0 first; escalate only on NO_HANDLER) ──────────────
HANDLERS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "add": lambda t: {"intent": "add", "answer": float(t.get("a", 0)) + float(t.get("b", 0))},
    "echo": lambda t: {"intent": "echo", "answer": t.get("text", "")},
}


def _commit(entry: dict[str, Any]) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with open(LEDGER, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


_cache: dict[str, dict[str, Any]] = {}


def route(intent: str, task: dict[str, Any], *, max_tokens: int = 2500,
          timeout: int = 240) -> dict[str, Any]:
    """Resolve deterministically if a handler exists; else escalate to the free seat, validate,
    commit. Returns the ledger entry."""
    task_id = f"{intent}-{_hash(json.dumps(task, sort_keys=True))}"
    # 1) deterministic first
    handler = HANDLERS.get(intent)
    if handler is not None:
        try:
            out = handler(task)
            out["ok"] = True
            out["path"] = "deterministic"
            out["task_id"] = task_id
            return out
        except Exception as e:
            out = {"ok": False, "task_id": task_id, "path": "deterministic", "error": str(e)[:200]}
            _commit({**_base(task_id, intent, task), **out, "ts": _now()})
            return out
    # 2) cache (same question never costs twice)
    prompt = f"{intent}|{json.dumps(task, sort_keys=True)}"
    key = _hash(prompt)
    if key in _cache:
        return {**_cache[key], "task_id": task_id, "path": "cache", "ok": True}
    # 3) escalate to the free frontier seat — "the LLM proposes; determinism disposes"
    from mag import ox_seat
    system = ("You are a deterministic escalation seat. Reply with ONLY a JSON object matching "
              f"this schema: {json.dumps(EXPECTED_SCHEMA)}. No prose, no markdown, no explanation.")
    r = ox_seat.chat(system, json.dumps({"intent": intent, "task": task}),
                     max_tokens=max_tokens, timeout=timeout, tier="T2")
    if not r.get("ok"):
        entry = {"ok": False, "task_id": task_id, "path": "escalate", "error": r.get("error", "")[:200]}
        _commit({**_base(task_id, intent, task), **entry, "ts": _now()})
        return entry
    # validate the seat's content against the schema (determinism disposes)
    content = r.get("content")
    valid, parsed = False, {}
    if content:
        try:
            parsed = json.loads(content)
            valid = isinstance(parsed, dict) and all(k in parsed for k in EXPECTED_SCHEMA["required"])
        except Exception:
            valid = False
    entry = {
        "ok": valid, "task_id": task_id, "path": "escalate", "intent": intent,
        "content": content, "parsed": parsed, "valid": valid,
        "cost": r.get("cost"), "cached_tokens": r.get("cached_tokens"),
        "model": r.get("model"), "ts": _now(),
    }
    _commit({**_base(task_id, intent, task), **entry})
    if valid:
        _cache[key] = entry  # future identical calls hit cache, cost $0
    return entry


def _base(task_id: str, intent: str, task: dict[str, Any]) -> dict[str, Any]:
    return {"schema": SCHEMA, "task_id": task_id, "intent": intent, "task": task}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(prog="ox-escalate")
    ap.add_argument("cmd", nargs="?", default="status", choices=["status", "route"])
    ap.add_argument("intent", nargs="?", default="")
    ap.add_argument("--task", default="{}")
    a = ap.parse_args()
    if a.cmd == "route":
        try:
            t = json.loads(a.task)
        except Exception:
            t = {"text": a.task}
        print(json.dumps(route(a.intent, t), indent=2, default=str))
    else:
        print(json.dumps({"ok": True, "schema": SCHEMA,
                          "contract": "route(intent, task) -> deterministic handler OR escalate to "
                                      "the free seat, validate schema, commit ledger, cache",
                          "ledger": str(LEDGER), "handlers": sorted(HANDLERS)}, indent=2))
