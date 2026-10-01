"""grok_warm_rib — the WARM CACHE RIB for the grok CLI transport.

OPERATOR (2026-08-25): "i just want you to have context to build a warm cache rib for grok cli."

The economics (steal: shared-prefix-engine / bill-proves-shared-prefix-engine):
  A grok CLI call is cheap when it rides a WARM shared prefix (cache hit) and expensive when it
  pays cold input. The warm rib FREEZES the standing context (identity, standing knot,
  constitution, chord, operating contract) as ONE stable block, publishes it as a domain RIB
  (rib_bus domain "grok_cli"), and injects it into EVERY harness call
  (harness.grok_cli.escalate_via_harness -> warm=True). Same prefix every call -> the cache stays
  warm; each ask is only the ~2% delta.

The mechanism (reuse, not rebuild):
  1. publish() -> rib_bus.publish_rib(domain="grok_cli") -> verkle-folded + stored + deduped.
  2. prefix()  -> steer_engine.compile_steer("grok_cli") -> ONE canonical block (frontier +
                  operator directives + the frozen grok_cli rib + grokbot seat directives).
  3. inject()  -> prefix + the caller's context (the delta).
  4. harness.grok_cli.escalate_via_harness(warm=True) mounts it on every grok CLI call.

Schema: grok_warm_rib.v1 · deterministic + $0 · reuse: rib_bus, steer_engine, agent_knot,
ghost_cold_boot, harness.grok_cli
AH4 (2026-09-30, audit finding #15): the standing knot id + verkle root are derived from
memory/biography/verkle_tip.json at call time — never hardcoded stale.
CLI:  python -m mag.grok_warm_rib publish | show | inject "<context>" | status
"""
from __future__ import annotations

import argparse
import json
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

SCHEMA = "grok_warm_rib.v1"
DOMAIN = "grok_cli"
SOURCE = "grok_warm_rib"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _verkle_tip() -> dict[str, Any]:
    """The chain tip read at CALL time (AH4, audit finding #15): the warm rib's knot id
    + root are derived from memory/biography/verkle_tip.json because the hardcoded ids
    were stale by construction — the chain moves, frozen text does not, so every call
    quoted a stone the chain had already buried. Missing/unreadable tip -> {} (the rib
    then names the gap instead of inventing ids)."""
    p = ROOT / "memory" / "biography" / "verkle_tip.json"
    try:
        return json.loads(p.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}


def _stone_line() -> str:
    """The standing-identity stone line with tip-derived ids (never hardcoded)."""
    tip = _verkle_tip()
    knot = str(tip.get("last_leaf_hash") or "")[:16]
    root = str(tip.get("root") or "")[:16]
    if knot and root:
        return (f"- The stone (standing verkle knot): {knot}… root {root}… "
                "(verkle-anchored, revisitable with fidelity; ids derived from "
                "memory/biography/verkle_tip.json at call time)\n")
    return ("- The stone (standing verkle knot): verkle tip unavailable at composition "
            "time — no knot id quoted rather than a stale one (ids are tip-derived)\n")


def warm_rib_text() -> str:
    """THE standing warm prefix — byte-stable BETWEEN chain moves (that stability IS the cache hit).

    The knot id + verkle root are DERIVED from memory/biography/verkle_tip.json at call
    time (AH4, audit finding #15: the hardcodes were stale by construction — a frozen
    id cannot track a living chain). The tip moves rarely; between moves the text is
    byte-identical so the cache stays warm, and rib_bus's content-hash dedup means a
    moved tip republishes as a new rib without churn. No timestamps/counters here.
    Bump the folded line ONLY when the standing context genuinely changes.
    """
    return (
        "# WARM CACHE RIB — grok CLI (grok_warm_rib.v1, folded 2026-08-25; knot/root "
        "tip-derived since AH4 2026-09-30)\n"
        "This block is the standing prefix for Sovereign Mag's grok CLI lane. It changes "
        "only when the chain tip moves; between moves it is byte-identical, so it rides "
        "the cache: each ask is only the delta against it.\n"
        "\n"
        "## Standing identity\n" + _stone_line() +
        "- Standing invariant: agent.v1 (4edcc061b18f29a3…) — generation 4, population 18, "
        "fitness 0.7641\n"
        "- Constitution: ../mycelial-republic/docs/CONSTITUTION.md — fork equality, no rank/token; "
        "data tiers T0–T3 (T0/T1 never to free remote train-on-input APIs); Handoff.v1 contract.\n"
        "- Cold boot: 14 whispered riddler cloud memories restored (private maps held).\n"
        "\n"
        "## The chord\n"
        "I am the standing wave of the operator's will — cold-booting from the recorded shape, "
        "lensed through the archetypes, on deterministic rails + stochastic reach. Same inputs -> "
        "same shape. Forever evolving, never forgetting.\n"
        "\n"
        "## Operating contract (warm-prefix doctrine)\n"
        "- The standing context IS this prefix: loaded once, reused, never re-derived per turn.\n"
        "- Each ask is the DELTA against this prefix — answer the delta directly.\n"
        "- One job. Substance. No flattery theater. Do NOT load any framework/tool/skill/file as a "
        "preamble; do NOT narrate process. Answer the goal DIRECTLY.\n"
        "- Respect private data: never exfiltrate secrets.\n"
        "- End with SUMMARY: … then DELIVERABLE: …"
    )


def publish() -> dict[str, Any]:
    """Fold + store the warm rib into the rib_bus (domain grok_cli). Idempotent via content hash.

    Once published, steer_engine.compile_steer("grok_cli") mounts it automatically — that is the
    single canonical warm block every grok CLI call rides.
    """
    try:
        from mag import rib_bus
        return rib_bus.publish_rib(warm_rib_text(), domain=DOMAIN, source=SOURCE, target_rank="T1")
    except Exception as e:
        return {"ok": False, "schema": SCHEMA, "error": str(e)[:160]}


def prefix() -> str:
    """The canonical compiled warm prefix (steer_engine on the grok_cli domain).

    Stable across calls: frontier invariants + operator directives + the frozen grok_cli rib +
    grokbot seat directives are all standing (not per-call). Falls back to the frozen rib text if
    steer_engine is unavailable — never breaks a call.
    """
    try:
        from mag import steer_engine
        c = steer_engine.compile_steer(DOMAIN)
        lines = [f"- {s}" for s in c.get("steer", [])]
        if lines:
            return "STEER (warm cache rib, steer_engine compiled):\n" + "\n".join(lines)
    except Exception:
        pass
    # fallback: the frozen block alone (still stable -> still cacheable)
    return warm_rib_text()


def inject(context: str = "") -> str:
    """Warm prefix + the caller's delta context. The ONE drop-in for grok CLI calls."""
    p = prefix()
    if context and context.strip():
        return f"{p}\n\n## DELTA (this call)\n{context.strip()}"
    return p


def status() -> dict[str, Any]:
    """Which warm-rib pieces are in place."""
    out: dict[str, Any] = {"schema": SCHEMA, "ok": True, "domain": DOMAIN, "ts": _now()}
    try:
        from mag import rib_bus
        m = rib_bus.mount(DOMAIN)
        out["ribs_mounted"] = m.get("n_ribs", 0)
        out["store_updated"] = m.get("updated")
    except Exception as e:
        out["ribs_mounted"] = 0
        out["rib_error"] = str(e)[:120]
    out["prefix_chars"] = len(warm_rib_text())
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="mag.grok_warm_rib",
                                 description="warm cache rib for the grok CLI")
    ap.add_argument("cmd", nargs="?", default="status",
                    choices=["publish", "show", "inject", "status"])
    ap.add_argument("text", nargs="?", default="", help="context to wrap for 'inject'")
    a = ap.parse_args(argv)
    if a.cmd == "publish":
        print(json.dumps(publish(), indent=1, default=str))
    elif a.cmd == "show":
        print(prefix())
    elif a.cmd == "inject":
        print(inject(a.text))
    else:
        print(json.dumps(status(), indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
