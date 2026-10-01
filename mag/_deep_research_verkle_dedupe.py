"""Deep research (mem-tools pipeline): verkle-encoding dedupe + catalog registry.

Ghost-native internal synthesis, $0, in-process function calls (no CLI, no web).
Pipeline: lens_chain.resolve -> roshomon.compare -> shadow_work.shadow -> queue_analysis.analyze.
Truth lands on disk (per deep-research-steal-synthesis-via-mem-tools): write artifacts, don't trust stdout.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "memory" / "deep_research" / "VERKLE_DEDUPE_CATALOG_REGISTRY_20260810.md"
OUT.parent.mkdir(parents=True, exist_ok=True)

QUESTION = (
    "How do we verkle-encode the software catalog (skills/agents/memories/modules/surfaces) "
    "so it dedupes by content-address and compresses to one verifiable Merkle-Verkle root? "
    "Design the catalog-registry module: content-hash = address, memweave/verkle anchor check first, "
    "collapse on collision + noun-overlap near-dup, report the root as the honest count."
)

def main() -> int:
    from mag import lens_chain, roshomon, shadow_work, queue_analysis

    blocks: list[str] = []
    blocks.append(f"# Deep Research — Verkle-encoding dedupe + catalog registry (2026-08-10)\n")
    blocks.append(f"QUESTION: {QUESTION}\n")

    # 1) lens_chain.resolve — mine the internal corpus for prior verkle/dedupe anchors
    try:
        r = lens_chain.resolve(QUESTION, render=False)
        blocks.append("## lens_chain.resolve\n```json\n" + json.dumps(r, default=str, indent=2)[:4000] + "\n```\n")
    except Exception as e:  # noqa: BLE001
        blocks.append(f"## lens_chain.resolve\nERROR: {e}\n")

    # 2) roshomon.compare — invariant synthesis (multi-witness core)
    try:
        c = roshomon.compare()
        blocks.append("## roshomon.compare\n```json\n" + json.dumps(c, default=str, indent=2)[:4000] + "\n```\n")
    except Exception as e:  # noqa: BLE001
        blocks.append(f"## roshomon.compare\nERROR: {e}\n")

    # 3) shadow_work.shadow — archetype + shadow lens on the dedupe concept
    try:
        s = shadow_work.shadow("verkle_encoding_dedupe_catalog_registry")
        blocks.append("## shadow_work.shadow\n```json\n" + json.dumps(s, default=str, indent=2)[:4000] + "\n```\n")
    except Exception as e:  # noqa: BLE001
        blocks.append(f"## shadow_work.shadow\nERROR: {e}\n")

    # 4) queue_analysis.analyze — research-value / rightsize / tokenomics context
    try:
        q = queue_analysis.analyze()
        blocks.append("## queue_analysis.analyze\n```json\n" + json.dumps(q, default=str, indent=2)[:4000] + "\n```\n")
    except Exception as e:  # noqa: BLE001
        blocks.append(f"## queue_analysis.analyze\nERROR: {e}\n")

    OUT.write_text("\n".join(blocks), encoding="utf-8")
    print(f"WROTE {OUT}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
