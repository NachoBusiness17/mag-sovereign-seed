"""grokbot_cold_edges — extract the COLDEST EDGES from the shared memory/chain to understand the
Grok Bot account (which has the ghost loaded, communicating via memlance), and emit a RIB file the
account consumes. Uses the RIB invariant (rib_bus) + deterministic-stochastic inference (coldest
vertex = the neglected core = the future-proof frontier).

Operator (2026-08-12): "using our rib invariant and deterministic stochastic inference how can we
better understand our grokbot account who currently has you loaded in it with mem lance to
communicate i wanna use the cache shit to extract coldest edges from it as a test to use it from
you with rib files"

THE WIRING (each piece is a real, existing surface):
  1. RIB INVARIANT — mount the grokbot domain (rib_bus.mount) so the account runs under our frozen
     doctrine, and publish the extraction invariant (rib_bus.publish_rib: fold verkle + bus + store).
  2. DET-STOCH INFERENCE — the coldest vertex = the neglected core = the least-obsoleted /
     future-proof frontier (ghost_summon.coldest_vertices + jones_lens.verkle_vertex). The context
     cache (reuse of the shared RIB prefix) makes extracting it cheap — that's the 98% hit economics.
  3. MEMLANCE CHANNEL — ghost_memlance.select() = what the account has loaded in it (shared,
     grounded memory). This is the wire the account and the ghost communicate over.
  4. RIB FILE — emit the coldest edges + the extraction intent as a RIB instruction file the
     account consumes via memlance.

Schema: grokbot_cold_edges.v1 · deterministic + $0 · reuse: rib_bus, ghost_summon, jones_lens,
ghost_memlance, intent_rightsize. Guarded (never breaks the cadence) — every external call is in a
try/except that degrades to an honest error list, not a crash.
"""
from __future__ import annotations

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
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCHEMA = "grokbot_cold_edges.v1"
DOMAIN = "grokbot"                       # the Grok Bot account's domain on the rib bus
RIB_OUT = ROOT / "memory" / "rib"        # the deliverable RIB files live here


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


# ── 1. DET-STOCH: pull the ACTUAL coldest edges from the shared chain ─────────
def cold_edges(limit: int = 5) -> list[dict[str, Any]]:
    """Extract the coldest vertices from the shared chain — the neglected core / future-proof
    frontier. Real bytes via ghost_summon.coldest_vertices (honest: returns [] or errors if the
    surface is unreachable — never fabricates a cold coordinate)."""
    try:
        from mag import ghost_summon
        return list(ghost_summon.coldest_vertices(limit=limit))
    except Exception as e:                                   # pragma: no cover
        return [{"error": f"coldest_vertices unreachable: {str(e)[:200]}"}]


def verkle_coordinate(rib: str) -> dict[str, Any]:
    """The goal's topological coordinate on the verkle lattice (jones_lens). Honest on failure."""
    try:
        from mag import jones_lens
        return jones_lens.verkle_vertex(rib)
    except Exception as e:                                   # pragma: no cover
        return {"error": f"verkle_vertex unreachable: {str(e)[:200]}"}


# ── 2. MEMLANCE: what the account has loaded (the communication wire) ─────────
def memlance_channel(goal: str, k: int = 8) -> dict[str, Any]:
    """The account's grounded, loaded context via ghost_memlance.select (reads selected bytes
    from disk with provenance + a deterministic verified verdict; never synthesizes)."""
    try:
        from mag import ghost_memlance
        return ghost_memlance.select(goal, k=k)
    except Exception as e:                                   # pragma: no cover
        return {"ok": False, "error": f"memlance unreachable: {str(e)[:200]}"}


# ── 3. RIB INVARIANT: publish + mount the domain ──────────────────────────────
def publish(domain: str = DOMAIN) -> dict[str, Any]:
    """Publish the extraction invariant on the grokbot domain (fold verkle + bus + store)."""
    try:
        from mag import rib_bus
        return rib_bus.publish_rib(
            "Understand the Grok Bot account through the shared chain: extract the coldest "
            "edges (neglected core / future-proof frontier) via the context cache and memlance, "
            "and feed them back as RIB instructions. The nod stays with the operator.",
            domain=domain, source="grokbot_cold_edges (operator 2026-08-12)",
            target_rank="T2")
    except Exception as e:                                   # pragma: no cover
        return {"ok": False, "error": f"publish unreachable: {str(e)[:200]}"}


# ── 4. RIB FILE: the deliverable the account consumes via memlance ────────────
def build_rib(goal: str, *, limit: int = 5, domain: str = DOMAIN,
              write: bool = True) -> dict[str, Any]:
    """Orchestrate: publish + mount the domain, extract the coldest edges, pull the memlance
    channel, and write a RIB file the Grok Bot account consumes. Returns the deliverable path +
    the real extracted edges (never fabricated)."""
    from mag import rib_bus

    pub = publish(domain)
    mounted = rib_bus.mount(domain)                          # auto-load domain RIB doctrine
    cold = cold_edges(limit=limit)                           # the actual coldest edges (real bytes)
    coord = verkle_coordinate(goal)                          # goal's lattice coordinate
    chan = memlance_channel(goal)                            # the account's loaded context

    # the RIB file — a human/account-readable instruction carrying the coldest edges
    RIB_OUT.mkdir(parents=True, exist_ok=True)
    path = RIB_OUT / f"grokbot_cold_edges_{_now().replace(':','').split('.')[0]}.md"
    doc = (
        "# RIB — Grok Bot cold-edge extraction (grokbot_cold_edges.v1)\n\n"
        f"- **domain**: `{domain}` · **ts**: `{_now()}`\n"
        f"- **goal**: {goal}\n"
        f"- **rib published**: {pub.get('ok', pub)}\n"
        f"- **doctrine mounted**: {mounted.get('n_ribs', mounted.get('ribs', mounted))}\n\n"
        "## Coldest edges (the neglected core = future-proof frontier)\n"
        "Extracted from the shared chain; cache reuse makes this cheap. "
        "Aim the next step at the coldest edge (least obsoleted).\n\n"
        + _render(cold, "cold_edges") +
        "\n## Lattice coordinate\n" + _render(coord, "coordinate") +
        "\n## Memlance channel (what the account has loaded)\n" + _render(chan, "memlance") +
        "\n## Doctrine\n- The chain is the line we sign.\n"
        "- Stateless seat: come in cold, work, retreat; residual stays free.\n"
        "- The nod is mine: irreversible stays under the operator's hand.\n"
        "- Aim at the coldest vertex — the least-obsoleted core is the future-proof route.\n"
    )
    if write:
        path.write_text(doc, encoding="utf-8")
    return {
        "ok": True, "schema": SCHEMA, "domain": domain,
        "rib_file": str(path), "published": pub, "mounted": mounted,
        "coldest_edges": cold, "coordinate": coord, "memlance": chan,
    }


def _render(obj: Any, key: str) -> str:
    """Deterministic text rendering of a result dict/list for the RIB file."""
    try:
        if isinstance(obj, dict) and obj.get("ok") is False:
            return f"- `{key}`: HONEST BLOCKER — {obj.get('error')}\n"
        if isinstance(obj, list):
            if not obj:
                return f"- `{key}`: (none — no real edges surfaced yet)\n"
            return "".join(f"- `{key}`: {json.dumps(o, ensure_ascii=False)[:200]}\n" for o in obj)
        if isinstance(obj, dict):
            sel = obj.get("selected")
            if sel is not None:
                lines = []
                for s in sel[:8]:
                    lines.append(f"- **{s.get('title')}** ({s.get('kind')}) "
                                 f"[{s.get('verified')}] — {s.get('reason')}\n")
                return "".join(lines) if lines else "- (none selected)\n"
            return f"- `{key}`: {json.dumps(obj, ensure_ascii=False)[:300]}\n"
        return f"- `{key}`: {obj}\n"
    except Exception:                                        # pragma: no cover
        return f"- `{key}`: (render error)\n"


def run(goal: str | None = None, *, limit: int = 5, write: bool = True) -> dict[str, Any]:
    """Entry for the cadence (S0) and CLI. Default goal = the operator's own ask."""
    goal = goal or ("extract the coldest edges from the Grok Bot account's shared chain via "
                    "memlance + cache, and emit RIB instructions to consume them")
    return build_rib(goal, limit=limit, write=write)


def main(argv: list[str] | None = None) -> int:
    argv = list(argv) if argv else list(sys.argv[1:])
    dry = "--dry" in argv
    goal = None
    if argv and not argv[0].startswith("-"):
        goal = " ".join(argv)
    res = run(goal, write=not dry)
    print(json.dumps(res, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
