"""scrum — formalized Scrum-style backlog + proof-first Socratic sprint loop + trusted surface.

The operator's doctrine: scrum organization, Socratic questioning, LOW-COST PROOF FIRST.
Every sprint item is proven on the cheapest capable tier before any spend escalates:
  proof (cheap local / flash) -> verify (deterministic check / test) -> fold to case law.
  Escalate ONLY if proof fails; grok ONLY for frontier (Law #7 grok_gate).

Board lives in memory/scrum/backlog.json (id, title, epic, role, status, proof, tier).
`surface()` = the trusted-surface snapshot the Control Room shows (no terminal guessing).

CLI: python -m mag.scrum backlog|sprint|advance|surface [--apply]
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCHEMA = "mag_scrum.v1"
BOARD = ROOT / "memory" / "scrum" / "backlog.json"
SEED = [
    {"id": "S1", "title": "Prepare Vast.ai training package from available data (lora_pipeline)",
     "epic": "Vast train", "role": "trainer", "tier": "local",
     "proof": "mag.vast_launcher.build_training_package(dry)",
     "status": "todo", "note": "package memory/training data for vast_launcher"},
    {"id": "S2", "title": "Recap recent sessions + self-steal / self-research from available data",
     "epic": "Research", "role": "researcher", "tier": "flash",
     "proof": "enqueue research-pack + steal-protocol sweep",
     "status": "todo", "note": "corpus + steal_protocol on existing data"},
    {"id": "S3", "title": "Fix container dashboard healthcheck (mag-sovereign still 'unhealthy')",
     "epic": "Ops", "role": "ops", "tier": "local",
     "proof": "verify /api/v1/health on :8765 in container",
     "status": "todo", "note": "drainer runs; healthcheck endpoint is the gap"},
    {"id": "S4", "title": "Formalize scrum board as the trusted surface (Control Room)",
     "epic": "Process", "role": "owner", "tier": "local",
     "proof": "surface() JSON -> Control Room tab",
     "status": "todo", "note": "one surface the operator trusts"},
    {"id": "S5", "title": "Wire proof-first socratic sprint loop into the skill pipeline",
     "epic": "Process", "role": "owner", "tier": "local",
     "proof": "advance() runs S1..S4 proof-first",
     "status": "todo", "note": "scrum drives skill_pipeline; each step cheap-proof then verify"},
    # COMPLETE REFACTOR EPIC (operator: steals + internal reflection -> gap analysis -> training -> end)
    {"id": "S6", "title": "Complete refactor via STEALS + internal reflection (audit all subsystems)",
     "epic": "Refactor", "role": "architect", "tier": "local",
     "proof": "internal-reflection + steal-protocol sweep -> refactor plan",
     "status": "todo", "note": "steal first, execute second; internal reflection across framework"},
    {"id": "S7", "title": "Gap analysis on missing steps (for training)",
     "epic": "Refactor", "role": "researcher", "tier": "flash",
     "proof": "gap_analysis -> missing training steps/coverage",
     "status": "todo", "note": "map gaps -> what training data/method is missing"},
    {"id": "S8", "title": "Train on Vast (Steiniger LLM research + steal protocol + available data)",
     "epic": "Vast train", "role": "trainer", "tier": "local",
     "proof": "vast_launcher.build_training_package(dry) after gap analysis",
     "status": "todo", "note": "END after this — no new work; prompt operator only when truly needed"},
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load() -> dict[str, Any]:
    if BOARD.is_file():
        try:
            d = json.loads(BOARD.read_text(encoding="utf-8"))
            # FIX (2026-08-24, "system devolved into spinning plates / real resources idle"):
            # the board file existed but with tickets=[] — never seeded, so sprint() returned null
            # and NOTHING routed to the seats while the loop spun at 100% CPU. Seed from SEED
            # whenever the board has no tickets so the fuel line is never empty.
            if not d.get("tickets"):
                d["tickets"] = [dict(t) for t in SEED]
            return d
        except Exception:
            pass
    return {"schema": SCHEMA, "created": _now(), "tickets": [dict(t) for t in SEED]}


TODO_PATH = ROOT / "queue" / "todo.md"


def sync_from_todo(*, limit: int = 10) -> dict[str, Any]:
    """SYNC REAL WORK (2026-08-24): pull OPEN (unchecked) items from queue/todo.md onto the scrum
    board as tickets, so sprint() has current work to route to the seats. This is the missing fuel
    line: todo.md (15 open items) -> board -> sprint() -> seats. Idempotent by title."""
    b = _load()
    existing = {t.get("title", "").strip() for t in b.get("tickets", [])}
    added = 0
    if TODO_PATH.is_file():
        for line in TODO_PATH.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line.startswith("- [ ]"):
                continue
            title = line[5:].strip()
            if not title or title in existing:
                continue
            b.setdefault("tickets", []).append({
                "id": f"T{len(b['tickets'])+1:02d}",
                "title": title[:160],
                "epic": "todo-sync",
                "role": "worker",
                "tier": "flash",
                "proof": "",
                "status": "todo",
                "note": "auto-synced from queue/todo.md",
            })
            existing.add(title)
            added += 1
            if added >= limit:
                break
    if added:
        _save(b)
    return {"ok": True, "schema": SCHEMA, "added": added, "board_tickets": len(b.get("tickets", []))}


def _save(board: dict[str, Any]) -> None:
    BOARD.parent.mkdir(parents=True, exist_ok=True)
    BOARD.write_text(json.dumps(board, indent=2, ensure_ascii=False), encoding="utf-8")


def backlog() -> dict[str, Any]:
    b = _load()
    by_status: dict[str, int] = {}
    for t in b.get("tickets", []):
        s = t.get("status", "todo")
        by_status[s] = by_status.get(s, 0) + 1
    return {"schema": SCHEMA, "ok": True, "tickets": b.get("tickets", []),
            "by_status": by_status, "board_path": str(BOARD)}


def sprint() -> dict[str, Any]:
    """Pick the next PROOF-FIRST item: lowest tier + todo status (cheapest capable first)."""
    b = _load()
    todo = [t for t in b.get("tickets", []) if t.get("status") == "todo"]
    if not todo:
        return {"schema": SCHEMA, "ok": True, "item": None, "note": "backlog clear"}
    todo.sort(key=lambda t: ({"local": 0, "flash": 1, "pro": 2, "grok": 3}.get(t.get("tier"), 1), t.get("id", "")))
    return {"schema": SCHEMA, "ok": True, "item": todo[0], "next": [t["id"] for t in todo[1:4]]}


def _run_proof(item: dict[str, Any]) -> dict[str, Any]:
    """Low-cost proof: call the item's proof (module.fn), cheapest tier. Never expensive.

    Handles both `module.fn` and dotted `module.submodule.fn` paths, and strips
    trailing call syntax like `(dry)` / `()` so proofs with args parse cleanly.
    """
    proof = (item.get("proof") or "").strip()
    if not proof:
        return {"ok": False, "error": "no proof defined"}
    # strip trailing call syntax: "module.fn(dry)" -> "module.fn"
    head = proof.split("(", 1)[0].strip()
    parts = head.split(".")
    if len(parts) < 2:
        return {"ok": False, "error": f"proof must be module.fn, got: {proof[:80]}"}
    mod_path, fn = ".".join(parts[:-1]), parts[-1]
    try:
        m = __import__(mod_path, fromlist=[fn])
        f = getattr(m, fn)
        res = f()
        return {"ok": True, "result": res}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


def advance(*, apply: bool = False) -> dict[str, Any]:
    """Proof-first socratic step: take the next cheapest item, run its LOW-COST proof,
    verify, and fold. Escalate ONLY on proof failure; grok ONLY frontier (grok_gate).

    Operates on the LOADED board's own ticket objects (not sprint's fresh copy) so
    done/blocked/escalated status actually persists on apply.
    """
    b = _load()
    tickets = b.get("tickets", [])
    # pick the next cheapest todo item from THIS board
    todo = [t for t in tickets if t.get("status") == "todo"]
    if not todo:
        return {"schema": SCHEMA, "ok": True, "note": "backlog clear"}
    todo.sort(key=lambda t: ({"local": 0, "flash": 1, "pro": 2, "grok": 3}.get(t.get("tier"), 1), t.get("id", "")))
    item = todo[0]

    proof = _run_proof(item)
    if proof.get("ok"):
        # proof passed -> verify (fold) -> mark done (mutates the board ticket)
        item["status"] = "done"
        item["proof_ok"] = True
        item["done_at"] = _now()
        _fold(item, ok=True)
        if apply:
            _save(b)
        return {"schema": SCHEMA, "ok": True, "item": item["id"], "proof": "passed",
                "tier": item.get("tier"), "action": "done",
                "result_preview": str(proof.get("result", ""))[:200]}

    # proof failed -> escalate tier (cheapest capable next); grok only if frontier
    item["attempts"] = int(item.get("attempts") or 0) + 1
    if int(item["attempts"]) >= 2:
        # repeated proof failure — don't block the backlog; mark blocked and move on
        item["status"] = "blocked"
        item["proof_error"] = str(proof.get("error", ""))[:200]
        _fold(item, ok=False)
        if apply:
            _save(b)
        return {"schema": SCHEMA, "ok": True, "item": item["id"], "proof": "failed",
                "tier": item.get("tier"), "action": "blocked (2 proof failures — move on)",
                "error": str(proof.get("error", ""))[:150]}
    tier_order = ["local", "flash", "pro", "grok"]
    cur = item.get("tier", "local")
    nxt_tier = tier_order[min(tier_order.index(cur) + 1, len(tier_order) - 1)] if cur in tier_order else "flash"
    if nxt_tier == "grok":
        from mag.grok_gate import should_use_grok
        if not should_use_grok(item.get("title", "")).get("use_grok"):
            nxt_tier = "pro"  # don't burn grok on non-frontier
    item["tier"] = nxt_tier
    item["proof_error"] = str(proof.get("error", ""))[:200]
    item["status"] = "escalated" if nxt_tier in ("pro", "grok") else "todo"
    _fold(item, ok=False)
    if apply:
        _save(b)
    return {"schema": SCHEMA, "ok": True, "item": item["id"], "proof": "failed",
            "tier": item.get("tier"), "action": f"escalate to {nxt_tier}",
            "error": str(proof.get("error", ""))[:150]}


def _fold(item: dict[str, Any], *, ok: bool) -> None:
    try:
        from mag.skill_ledger import record_decision
        record_decision(goal=f"scrum:{item.get('id')}:{item.get('title','')[:40]}",
                        task_shape="ops", provider="deepseek", model=item.get("tier", "?"),
                        outcome="ok" if ok else "fail",
                        detail=f"sprint item {item.get('id')} proof {'passed' if ok else 'failed'}"
                               f" at {item.get('tier')}", source="scrum")
    except Exception:
        pass


def surface() -> dict[str, Any]:
    """Trusted surface for the Control Room: board + next sprint + spend-ish counts. No guessing."""
    b = backlog()
    sp = sprint()
    return {"schema": "scrum_surface.v1", "ts": _now(), "ok": True,
            "board": b, "next": sp.get("item"),
            "note": "trusted surface — see Control Room Scrum tab; items advance proof-first."}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = (argv[0] if argv else "backlog").lower()
    do_apply = "--apply" in argv
    if cmd == "surface":
        print(json.dumps(surface(), indent=2, ensure_ascii=False, default=str))
    elif cmd == "sprint":
        print(json.dumps(sprint(), indent=2, ensure_ascii=False, default=str))
    elif cmd == "advance":
        print(json.dumps(advance(apply=do_apply), indent=2, ensure_ascii=False, default=str))
    elif cmd == "sync":
        print(json.dumps(sync_from_todo(), indent=2, ensure_ascii=False, default=str))
    else:
        print(json.dumps(backlog(), indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
