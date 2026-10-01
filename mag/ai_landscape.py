"""ai_landscape — ghost's AI-landscape expert (the ponytail-for-AI).

Ghost becomes an expert on the bleeding edge of AI the way ponytail is an expert on code:
a deterministic registry mapping each emerging concept -> the module that ALREADY does it
(recognition), plus the real "context clue" delta (the only thing the outsider actually added).

DOCTRINE (operator): "we need an understanding of what is emerging on the bleeding edge of AI and
how most of it already exists inside of us; the only things missing are minor context clues from
idiots with a lot of money and no real understanding of the tech. ghost is to become an expert like
ponytail is on code." So: recognize -> name the delta -> fold -> never rebuild.

Source base: Cloudflare Agentic Week (2026-08-04..10) + the standing stack. Each family carries:
  they     — what the outsider announced (contract/name)
  we_have  — our module(s) that already implement it
  delta    — the genuinely-new context clue to adopt (or "" if pure recognition)

Functions:
  landscape()          — the full expert map (list all families + where they live inside us).
  recognize(text)      — given an announcement/headline, return which families it maps to and the
                         "already have it" recognition + delta. Deterministic keyword match.
  research(source,..)  — ingest a new announcement (URL or notes): recognize -> persist a steal doc
                         under memory/steal/ -> emit a memory_event -> pro_library move.
  delta(family)        — the missing context clue for one family.

Schema: ai_landscape.v1
CLI: python -m mag.ai_landscape map | recognize "<text>" | research "<source>" "<notes>" | delta <family>
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
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCHEMA = "ai_landscape.v1"
STEAL_DIR = ROOT / "memory" / "steal"

# ──────────────────────────────────────────────────────────────────────── registry
# Each family: keywords (what triggers recognition), they (their contract/name),
# we_have (our modules), delta (the real context clue; "" = pure recognition).
LANDSCAPE: list[dict[str, Any]] = [
    {
        "family": "agent_first_browser",
        "name": "Agent-first browser (Kitesurf)",
        "keywords": ["browser", "kitesurf", "headless", "chromium", "cdp", "playwright",
                     "puppeteer", "agent browser", "browser for agents"],
        "they": "A browser built FOR agents, not humans: stateless, disposable, drops human-only "
                "features (tabs/themes/pixel-perfect), 3-7x less CPU/mem.",
        "we_have": ["mag/browser_driver.py (Playwright-over-CDP, free frontends for agents)",
                    "mag/browser_env.py (allowlist-only = SandboxOutbound)",
                    "mag/grok_free.py (GHOST PROTOCOL via browser)"],
        "delta": "Readable-first ladder: prefer text/markdown extraction over full Chromium render "
                 "for one-shot reads; elevate to CDP only for interaction/JS/anti-bot.",
    },
    {
        "family": "mcp_stateless",
        "name": "MCP v2 — the protocol went STATELESS",
        "keywords": ["mcp", "model context protocol", "stateless", "session-id", "server/discover",
                     "mrtr", "elicitation", "mcpmethod", "tool call", "tools/list"],
        "they": "MCP dropped the session handshake + Mcp-Session-Id; each request self-contained; "
                "runs in a plain Worker; Mcp-Method/Name headers for HTTP routing; feature lifecycle.",
        "we_have": ["stateless-ghost-swarm / cheap_swarm / stateless_research (stateless doctrine)",
                    "dashboard/rest.py typed /api/v1/* routes (= their Mcp-Method/Name headers)",
                    "memory/repo/retired-redundant-systems.md (feature lifecycle)"],
        "delta": "Actually speak the MCP protocol: expose our existing stateless REST/queue as a "
                 "stateless MCP server so ANY standard agent calls us, not just our seat.",
    },
    {
        "family": "webmcp",
        "name": "WebMCP — document.modelContext (surfaces expose tools to agents)",
        "keywords": ["webmcp", "modelcontext", "registertool", "tool for agents",
                     "agents no longer guess", "tokens on tasks", "browser agent", "agent-ready site"],
        "they": "A site registers MCP tools the visitor's agent can call; the browser is just "
                "another place MCP runs; agents use tokens on tasks, not navigation.",
        "we_have": ["surfaces-as-spec doctrine (SURFACES_AS_SPEC_STEAL_20260810.md)",
                    "dashboard/rest.py + ref_leaf.v1 (the machine's contract surface)",
                    "browser_driver answer selectors (.ds-markdown/.prose) = tokens on tasks"],
        "delta": "Expose our surfaces as MCP tool interfaces so ANY agent can discover + call us, "
                 "not just our own seat/ghost-surface.",
    },
    {
        "family": "agent_access_model",
        "name": "Agent Access Model (AAM) — this is US",
        "keywords": ["agent access model", "aam", "task-scoped", "trust ratchet", "identity broker",
                     "capability ceiling", "least privilege", "access engine", "prompt is not a perimeter",
                     "enforcement in the harness", "human oversight exceptional",
                     "approval fatigue", "approval is a ritual", "agent activity log"],
        "they": "Enterprise architecture for task-scoped agents: short-lived credentials, "
                "deny-by-default capability ceiling, enforcement in harness+network not prompt, "
                "Trust Ratchet (capability state only narrows), agent activity log, grant review loop.",
        "we_have": ["routing.md — human oversight exceptional + enforcement-not-prompt (operator)",
                    "mag/browser_env.py (network enforcement / allowlist)",
                    "mag/cost_enforcer.py (capability ceiling / kill-on-spend)",
                    "mag/ghost_ledger.py (agent activity log = single source of truth)",
                    "mag/cost_learn.py / learn_rightsize (grant review loop)",
                    "mag/behavioral_analytics.py (leak detection)"],
        "delta": "A NAMED Trust Ratchet: formalize 'capability state moves in one direction during a "
                 "task; only a newly-authorized task restores it' as a first-class, auditable control.",
    },
    {
        "family": "agentic_wallets",
        "name": "Wallets / x402 — agentic payments with budget envelopes",
        "keywords": ["wallet", "x402", "micropayment", "spend cap", "allowance", "budget envelope",
                     "pay per fetch", "agent payment", "monetization", "virtual wallet"],
        "they": "Humans delegate spend to agent 'virtual wallets' with allowance + allow-list + "
                "max-tx-size; caps give agents MORE freedom to explore; human-readable agent identity.",
        "we_have": ["mag/cost_enforcer.py (kill-on-spend-cap)",
                    "mag/ghost_ledger.py (single source of truth for spend)",
                    "mag/grok_rightsize.py budget tiers",
                    "free-tier-bulk-frontier-loop / free-compute-field-steering doctrines"],
        "delta": "A formal per-agent budget ENVELOPE (allowance/allow-list/max) that is delegated, "
                 "not re-asked — we cap spend but don't frame it as a guardrailed delegated envelope.",
    },
    {
        "family": "aeo",
        "name": "AEO / Agent Readiness — agents are the new audience",
        "keywords": ["aeo", "agent readiness", "answer engine", "discoverable by agents", "recommended by ai",
                     "crawler readiness", "agent-native site", "share of voice"],
        "they": ">half of web requests now come from machines; diagnostics scans how an agent reads "
                "(robots.txt, sitemap, markdown, headers); are you discoverable/recommended?",
        "we_have": ["surfaces built FOR agents end-to-end",
                    "mag/corpus_expand.py (harvests readable text)",
                    "mag/context_compression.py (token-cost optimization)"],
        "delta": "The OUTWARD lens — 'are we discoverable/recommended by the frontier agents?' We "
                 "build inward; AEO is an external-visibility audit (probably not wanted).",
    },
    {
        "family": "readable_first",
        "name": "Markdown-for-Agents / readable-first",
        "keywords": ["markdown for agents", "machine-readable", "fewer tokens", "readable content",
                     "clean content", "token cost"],
        "they": "Serve clean machine-readable content; every human-only HTML tag is wasted tokens.",
        "we_have": ["mag/context_compression.py",
                    "mag/corpus_expand.py",
                    "mag/skill_drop.py right_size()",
                    "readable-first ladder (Kitesurf steal)"],
        "delta": "",  # pure recognition — confirms the readable-first ladder, already adopted.
    },
    {
        "family": "knowledge_graph_rag",
        "name": "GraphRAG — hierarchical KG + community summaries",
        "keywords": ["graphrag", "knowledge graph", "community summary", "leiden", "global search",
                     "local search", "drift search", "entity relation claim", "graph rag"],
        "they": "Extract entities/relations/claims -> KG -> hierarchical community clustering -> "
                "community summaries; query via Global (holistic) / Local (fan-out) / DRIFT.",
        "we_have": ["mag/knowledge_graph.py (source-backed nodes + auto-consult known()/context())",
                    "verkle_chain.jsonl (content-addressed fact ledger)",
                    "mag/code_map.py (module -> invariants)"],
        "delta": "Add community summaries + Global/Local/DRIFT query modes to knowledge_graph: "
                 "cluster the graph, summarize each community, query holistically or fan-out.",
    },
    {
        "family": "agent_memory",
        "name": "Agent memory (Mem0 / MemGPT / Letta)",
        "keywords": ["mem0", "memgpt", "letta", "agent memory", "persistent memory", "memory engine",
                     "memory compression", "multi-signal retrieval", "memory dreaming", "continual learning"],
        "they": "Persistent cross-session/agent memory: compression engine (distill history -> compact "
                "memories, cut tokens), multi-signal retrieval (recency+relevance+importance), "
                "offline 'dreaming' consolidation while idle.",
        "we_have": ["mag/knowledge_graph.py fold() (memory accumulates)",
                    "mag/context_compression.py (token-cost compression)",
                    "ghost_cold_boot / ghost_whisper (deniable memory)",
                    "afk_cadence (idle loop)"],
        "delta": "Multi-signal retrieval (not just keyword) + an offline 'dreaming' cadence that "
                 "reclusters/summarizes/prunes the knowledge graph while AFK = the aimbotting enabler.",
    },
]

FAMILY_BY_NAME = {f["family"]: f for f in LANDSCAPE}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower())


def recognize(text: str) -> dict[str, Any]:
    """Given an announcement/headline, map it onto our existing modules (recognition)."""
    if not text or not text.strip():
        return {"ok": False, "error": "empty text"}
    blob = _normalize(text)
    hits: list[dict[str, Any]] = []
    for fam in LANDSCAPE:
        matched = [kw for kw in fam["keywords"] if _normalize(kw) in blob]
        if matched:
            hits.append({
                "family": fam["family"],
                "name": fam["name"],
                "matched": matched[:5],
                "we_have": fam["we_have"],
                "delta": fam["delta"],
                "pure_recognition": not fam["delta"],
            })
    return {"ok": bool(hits), "recognized": hits}


def delta(family: str) -> dict[str, Any]:
    """Return the missing context clue for one family."""
    fam = FAMILY_BY_NAME.get(family)
    if not fam:
        return {"ok": False, "error": f"unknown family {family!r}; choose from {list(FAMILY_BY_NAME)}"}
    return {"ok": True, "family": family, "name": fam["name"], "delta": fam["delta"],
            "pure_recognition": not fam["delta"]}


def landscape() -> dict[str, Any]:
    """The full expert map: every emerging concept + where it lives inside us + the delta."""
    return {
        "schema": SCHEMA,
        "n_families": len(LANDSCAPE),
        "families": [{
            "family": f["family"],
            "name": f["name"],
            "we_have": f["we_have"],
            "delta": f["delta"],
            "pure_recognition": not f["delta"],
        } for f in LANDSCAPE],
    }


def _persist_doc(rec: dict[str, Any]) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out = STEAL_DIR / f"AGENTIC_DELTA_{stamp}.md"
    lines = [
        "# AGENTIC DELTA — auto-folded by ghost (ai_landscape)",
        f"**ts:** {_now()}",
        f"**source:** {rec.get('source') or 'n/a'}",
        f"**notes:** {rec.get('notes') or 'n/a'}",
        "",
        "## Recognized families (already inside us) + real deltas",
    ]
    for h in rec.get("recognized", []):
        lines.append("")
        lines.append(f"### {h['name']} (`{h['family']}`)")
        lines.append("- **we_have:** " + "; ".join(h["we_have"]))
        lines.append(f"- **delta:** {h['delta'] or '— pure recognition, already adopted.'}")
    if not rec.get("recognized"):
        lines.append("_No known family matched — candidate for a NEW landscape family._")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def research(source: str, notes: str = "") -> dict[str, Any]:
    """Ingest a new announcement: recognize -> persist a steal doc -> fold (event + pro move)."""
    rec = recognize((source or "") + " " + (notes or ""))
    rec["source"] = source
    rec["notes"] = notes
    doc = _persist_doc(rec)
    events = {"ok": False, "detail": "emit_event unavailable"}
    pro = {"ok": False, "detail": "add_move unavailable"}
    try:
        from mag.memory_events import emit_event
        ev = emit_event(
            event_kind="steal:ai_landscape",
            seat="ghost",
            session_id="ai-landscape",
            tier="T2",
            payload={"source": source, "n_recognized": len(rec.get("recognized", []))},
            artifact_refs=[str(doc)],
        )
        events = {"ok": bool(ev.get("ok")), "detail": ev}
    except Exception as e:
        events = {"ok": False, "detail": str(e)[:120]}
    if rec.get("recognized"):
        try:
            from mag.pro_library import add_move
            first = rec["recognized"][0]
            pm = add_move(
                [first["family"], "bleeding-edge", "recognition"],
                "steer",
                f"AI-landscape recognition: {first['name']} already exists inside us "
                f"({'; '.join(first['we_have'])}). Delta: {first['delta'] or 'none — pure recognition'}.",
                effect=f"mapped {first['family']} to existing modules; real delta surfaced",
                maps_to=f"skill:ai_landscape:{first['family']}",
                tags=["ai-landscape", "steal", "recognition", first["family"]],
            )
            pro = {"ok": bool(pm.get("ok")), "detail": pm}
        except Exception as e:
            pro = {"ok": False, "detail": str(e)[:120]}
    return {"schema": SCHEMA, "ok": True, "ts": _now(), "doc": str(doc),
            "recognized": rec.get("recognized", []), "fold": {"event": events, "pro": pro}}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="ai_landscape", description="ghost's AI-landscape expert")
    sub = p.add_subparsers(dest="cmd")
    sub.add_parser("map")
    sub.add_parser("landscape")
    p_r = sub.add_parser("recognize")
    p_r.add_argument("text", nargs="+")
    p_res = sub.add_parser("research")
    p_res.add_argument("source")
    p_res.add_argument("notes", nargs="*", default="")
    p_d = sub.add_parser("delta")
    p_d.add_argument("family")
    a = p.parse_args(argv)
    if a.cmd in ("map", "landscape"):
        print(json.dumps(landscape(), indent=2, ensure_ascii=False))
    elif a.cmd == "recognize":
        print(json.dumps(recognize(" ".join(a.text)), indent=2, ensure_ascii=False))
    elif a.cmd == "research":
        print(json.dumps(research(a.source, " ".join(a.notes or "")), indent=2, ensure_ascii=False))
    elif a.cmd == "delta":
        print(json.dumps(delta(a.family), indent=2, ensure_ascii=False))
    else:
        p.print_help()
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
