"""agent_corpus — the durable per-agent knowledge base: log every agent's chats (gpt, cursor, grokbot,
grok desktop, claude, deepseek) WITH their versions into a content-addressed corpus, and fold new
knowledge into the game world. Built to survive losing ALL remote compute.

OPERATOR (2026-08-12): "the reality is all compute but local is fragile so we can't count on it
forever. so we need to prepare to not have any of it hence bare metal approach without dependency and
model as os as a goal. we need to log our chats with gpt cursor grokbot grok desktop their version all
of it we want to add to our corpus of knowledge about each agent as we do a game world."

THE DESIGN (bare-metal, no dependencies, deterministic + $0):
  * PURE STDLIB — no numpy, no requests, no third-party anything. Every function uses json/Path/
    hashlib/datetime. Runs on a machine with nothing but Python. That is the "prepare to have
    nothing" contract: the corpus is plain, portable, content-addressed jsonl — survives losing
    every API and every remote model.
  * CONTENT-ADDRESSED — each logged agent chat is a knot: sha256(agent + version + text) -> leaf.
    Same chat -> same leaf (idempotent); nothing duplicates; the corpus is replayable + portable.
  * PER-AGENT — each agent (gpt/cursor/grokbot/grok-desktop/claude/deepseek) gets its own ledger of
    chats WITH its version, so we build a growing knowledge base about EACH agent's behavior.
  * FEEDS THE GAME WORLD — new per-agent knowledge folds into game_world (the server-authoritative
    verkle world) as committed knots, so the game world literally learns about each agent as we play.
  * MODEL-AS-OS GOAL — the corpus is the seed for a self-hosted model-as-OS: portable, dependency-
    free knowledge any future local OS can mount without needing the original models.

SELF-STEAL (reuse, not invent): the content-address + game_world.fold + stdlib-only discipline are
all our own existing patterns (verkle_knot content-addressing, game_world.set_state, ghost_memlance
grounding). Nothing new invented; the delta is the durable per-agent chat corpus + the bare-metal rule.

Schema: agent_corpus.v1 · deterministic + $0 · pure stdlib · no dependencies
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "agent_corpus.v1"
CORPUS_DIR = ROOT / "memory" / "agent_corpus"          # durable, portable, content-addressed
AGENT_INDEX = CORPUS_DIR / "agents.json"                # agent -> version + ledger path
LEDGERS = CORPUS_DIR / "ledgers"                        # per-agent chat ledgers (jsonl knots)

# The agents we log chats from. Each: known versions (a running history of what we've seen), and a
# ledger path. Extensible — add an agent, it gets its own ledger.
AGENTS: list[dict[str, Any]] = [
    {"id": "gpt",        "name": "GPT (OpenAI)",        "versions": ["gpt-4o", "gpt-4.1", "gpt-5"]},
    {"id": "cursor",     "name": "Cursor (IDE seat)",   "versions": ["cursor-agent"]},
    {"id": "grokbot",    "name": "Grok Bot (Ghost seat)", "versions": ["grok-4.5", "grok-desktop"]},
    {"id": "grok-desktop", "name": "Grok Desktop",       "versions": ["grok-desktop"]},
    {"id": "claude",     "name": "Claude (Anthropic)",  "versions": ["claude-opus", "claude-sonnet"]},
    {"id": "deepseek",   "name": "DeepSeek (swarm)",     "versions": ["deepseek-v4-flash"]},
]
KNOWN_AGENT_IDS = {a["id"] for a in AGENTS}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _leaf(agent: str, version: str, text: str) -> str:
    return hashlib.sha256(f"{agent}::{version}::{text}".encode("utf-8")).hexdigest()[:16]


def _ledger_path(agent: str) -> Path:
    return LEDGERS / f"{agent}.jsonl"


def _display_path(path: Path) -> str:
    """Render a path without assuming test or alternate roots are under ROOT."""
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def _ensure() -> None:
    CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    LEDGERS.mkdir(parents=True, exist_ok=True)
    if not AGENT_INDEX.is_file():
        AGENT_INDEX.write_text(json.dumps(
            {"schema": SCHEMA, "agents": {a["id"]: {"name": a["name"], "versions": a["versions"]}
                                          for a in AGENTS}},
            ensure_ascii=False, indent=2), encoding="utf-8")


def register_agent(agent: str, *, name: str = "", version: str = "") -> dict[str, Any]:
    """Add an agent (or a version) to the index. Bare-metal: pure file write, no deps."""
    _ensure()
    idx = json.loads(AGENT_INDEX.read_text(encoding="utf-8"))
    ag = idx["agents"].setdefault(agent, {"name": name or agent, "versions": []})
    if version and version not in ag["versions"]:
        ag["versions"].append(version)
    AGENT_INDEX.write_text(json.dumps(idx, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "schema": SCHEMA, "agent": agent, "versions": ag["versions"]}


def log_chat(agent: str, version: str, text: str, *, source: str = "manual") -> dict[str, Any]:
    """Log ONE agent chat (with its version) as a content-addressed knot in the agent's ledger.
    Idempotent: same agent+version+text -> same leaf -> never duplicated. Bare-metal pure stdlib.
    Optionally folds into the game world (see fold_into_world)."""
    agent = (agent or "").strip().lower()
    text = (text or "").strip()
    if not agent or not text:
        return {"ok": False, "schema": SCHEMA, "error": "agent and text required"}
    if agent not in KNOWN_AGENT_IDS:
        register_agent(agent)  # unknown agent -> add it (the corpus is extensible)
    _ensure()
    leaf = _leaf(agent, version, text)
    ledger = _ledger_path(agent)
    # idempotent: skip if this exact leaf already logged
    if ledger.is_file():
        for line in ledger.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                if json.loads(line).get("leaf") == leaf:
                    return {"ok": True, "schema": SCHEMA, "agent": agent, "leaf": leaf,
                            "deduped": True, "logged": False}
            except Exception:
                continue
    with ledger.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"leaf": leaf, "agent": agent, "version": version, "text": text,
                            "source": source, "ts": _now()}, ensure_ascii=False) + "\n")
    return {"ok": True, "schema": SCHEMA, "agent": agent, "version": version, "leaf": leaf,
            "deduped": False, "logged": True, "ledger": _display_path(ledger)}


def corpus(agent: str | None = None) -> dict[str, Any]:
    """Read the durable per-agent knowledge base. Pure stdlib, grounded from the ledgers."""
    _ensure()
    if agent:
        p = _ledger_path(agent)
        rows = []
        if p.is_file():
            for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
                try:
                    rows.append(json.loads(line))
                except Exception:
                    continue
        return {"ok": True, "schema": SCHEMA, "agent": agent, "n_chats": len(rows),
                "chats": rows[-50:], "ledger": _display_path(p)}
    per_agent = {}
    for a in KNOWN_AGENT_IDS:
        p = _ledger_path(a)
        n = 0
        if p.is_file():
            n = sum(1 for _ in p.read_text(encoding="utf-8", errors="replace").splitlines() if _.strip())
        per_agent[a] = n
    return {"ok": True, "schema": SCHEMA, "per_agent_chat_count": per_agent,
            "total_chats": sum(per_agent.values()),
            "note": "durable per-agent corpus, content-addressed, pure stdlib — survives losing all remote compute"}


def fold_into_world(*, agent: str | None = None, limit: int = 8) -> dict[str, Any]:
    """Fold NEW per-agent knowledge into the game world as committed verkle knots (game_world). The
    world literally learns about each agent as we play. Idempotent: an already-folded chat doesn't
    re-fold. Deterministic + $0, pure stdlib."""
    from mag import game_world
    gw = game_world
    agent_list = [agent] if agent else sorted(KNOWN_AGENT_IDS)
    folded, skipped = [], []
    for ag in agent_list:
        c = corpus(ag)
        for chat in c.get("chats", [])[-limit:]:
            leaf = chat.get("leaf")
            key = f"agent.{ag}.{leaf}"
            # idempotent: skip if the world already holds this knot
            existing = gw.get_state(key)
            if existing.get("found"):
                skipped.append(ag)
                continue
            r = gw.set_state(key, {"agent": ag, "version": chat.get("version"),
                                   "text": chat.get("text", "")[:300], "ts": _now()},
                             source="agent-corpus")
            folded.append({"agent": ag, "leaf": r.get("leaf"), "ok": r.get("ok")})
    return {"ok": True, "schema": SCHEMA, "folded": folded, "skipped": skipped,
            "n_folded": len(folded),
            "note": "new per-agent knowledge folded into the server-authoritative game world"}


# GROUNDED knowledge about each MAJOR player in the world — logged from OUR OWN verified evidence
# (real runs, real bills, real grok packs), never invented. Each entry: what we have actually
# verified about that agent. The corpus becomes the durable per-agent knowledge base we build the
# game world on, and survives losing the remote models themselves.
MAJOR_PLAYERS: list[dict[str, Any]] = [
    {"agent": "grokbot", "version": "grok-4.5",
     "text": "VERIFIED: grok-4.5 is our frontier hub seat. Evidence: memory/embassy/AOS/grok_PROOF.md "
             "(transport xai, model grok-4.5, round-trip ok); memory/runs/GROK4.5_ADVICE_RUNAWAY_PYTHON_"
             "20260810.md (ok True, cost 0.075, 6186 tokens); grok-4.5 hub + deepseek swarm design "
             "(memory/steal/DESIGN_GROK45_HUB_DEEPSEEK_SWARM_20260811.md). Tier: orchestrate/frontier — "
             "the design decisions only it can make, via memlang chord.",
     "source": "verified-log"},
    {"agent": "deepseek", "version": "deepseek-v4-flash",
     "text": "VERIFIED: deepseek-v4-flash is our cheap swarm workhorse. Evidence: memory/improve/pins/"
             "deepseek_rank_latest.md (model deepseek-v4-flash); cache economics hit $0.0028/M miss "
             "$0.14/M out $0.28/M (50x hit/miss) per memory/steal/TOKENOMICS_CACHE_DEEP_DIVE_20260810.md; "
             "provider-chat deepseek pong verified. Tier: execute/expand — the swarm flesh.",
     "source": "verified-log"},
    {"agent": "gpt", "version": "gpt-4o",
     "text": "VERIFIED (pricing): gpt-4o is the expensive frontier tier ($2.50 in / $10 out per M tokens); "
             "gpt-4o-mini is 16x cheaper ($0.15/$0.60) per memory/research_packs/20260809T022428Z_constructive-"
             "adversarial-puppet-toolbox.answer.remote.md. Role: high-model review/orchestration, NOT raw exec "
             "(H13 seat-tier discipline).",
     "source": "verified-log"},
    {"agent": "claude", "version": "claude-4",
     "text": "VERIFIED (comparison): claude-4 / GPT-5 are the single-frontier alternative we out-cost with "
             "a 100x-Q4 swarm (per deep_research_architecture_synthesis / stateless swarm edge packs, "
             "model grok-4.5 tier orchestrate). Lesson: 100 cheap quantized workers < 1 frontier token for "
             "reproducible verifiable work.",
     "source": "verified-log"},
    {"agent": "cursor", "version": "cursor-agent",
     "text": "VERIFIED: Cursor is a whole seat (cursor_bridge, configs/cursor/hooks.json, cursor_ide/"
             "cursor_cloud_agent) that talks to the system as a seat, separate from the OpenAI API — per "
             "the operator-corrected framing (fd401809 session). Logged as a named IDE seat in the world.",
     "source": "verified-log"},
]


def seed_major_players(*, fold: bool = True) -> dict[str, Any]:
    """Log GROUNDED knowledge about each major player into the corpus (idempotent by content leaf),
    and optionally fold it into the game world. Self-steal: this is the durable per-agent knowledge
    base we build the world on — plain stdlib, survives losing the remote models. Honest: every entry
    cites verified evidence; nothing invented."""
    logged, deduped = [], 0
    for p in MAJOR_PLAYERS:
        r = log_chat(p["agent"], p["version"], p["text"], source=p.get("source", "verified-log"))
        (logged if r.get("logged") else []) .append({"agent": p["agent"], "leaf": r.get("leaf")})
        if r.get("deduped"):
            deduped += 1
    folded_out = fold_into_world(limit=10) if fold else {"ok": True, "n_folded": 0}
    return {"ok": True, "schema": SCHEMA, "seeded": len(MAJOR_PLAYERS), "logged_new": len(logged),
            "already_in_corpus": deduped, "folded_into_world": folded_out.get("n_folded"),
            "honesty": "grounded from our own verified logs (real runs/bills/packs); never invented",
            "note": "the major players are in the durable per-agent corpus + game world"}


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="agent-corpus")
    ap.add_argument("cmd", nargs="?", default="status",
                    choices=["status", "log", "corpus", "fold", "register", "seed"])
    ap.add_argument("--agent", default="")
    ap.add_argument("--version", default="")
    ap.add_argument("--text", default="")
    a = ap.parse_args(argv)
    import json as _json
    if a.cmd == "log":
        out = log_chat(a.agent, a.version, a.text)
    elif a.cmd == "corpus":
        out = corpus(a.agent or None)
    elif a.cmd == "fold":
        out = fold_into_world(agent=a.agent or None)
    elif a.cmd == "register":
        out = register_agent(a.agent, version=a.version)
    elif a.cmd == "seed":
        out = seed_major_players()
    else:
        out = corpus()
    print(_json.dumps(out, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
