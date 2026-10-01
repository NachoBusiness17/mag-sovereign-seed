"""Training Data Packager — bundle sovereign data for LoRA fine-tuning.

Item 2 on the todo list: "Package training data: Verkle chain + @nachoquixotic
+ research packs."

The data already exists. This module just bundles it into a single JSONL
training file suitable for LoRA fine-tuning (Slashreboot Phase 2).

SOURCES:
  - Verkle chain (memory/biography/verkle_chain.jsonl) — system events
  - NachoQuixotic Grok prompts (memory/ghost/x_surface/) — frontier invariants
  - Research packs (memory/research_packs/) — sovereign research
  - Session koans (memory/training/session_koans.jsonl) — distilled insights
  - Ghost identity (mag/ghost_identity.py) — the identity vector itself

OUTPUT:
  - memory/training/sovereign_training_data.jsonl — one JSONL file
  - Each line: {"text": "<training example>", "source": "...", "type": "..."}

SCHEMA: training_packager.v1
LAW: Never include raw API keys, .env values, or operational secrets.
LAW: Each example is self-contained. No cross-references required.
LAW: The output is a SINGLE file. Simple. Portable. Ready for fine-tuning.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

try:
    from config import ROOT
except ImportError:
    ROOT = Path(__file__).resolve().parent.parent

OUTPUT_PATH = ROOT / "memory" / "training" / "sovereign_training_data.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ═══════════════════════════════════════════════════════════════════
# SOURCE LOADERS
# ═══════════════════════════════════════════════════════════════════

def _load_verkle_chain(tail: int = 100) -> list[dict[str, Any]]:
    """Load recent Verkle chain knots as training examples."""
    chain_path = ROOT / "memory" / "biography" / "verkle_chain.jsonl"
    if not chain_path.is_file():
        return []

    examples = []
    try:
        lines = chain_path.read_text(encoding="utf-8", errors="replace").strip().splitlines()
        for line in lines[-tail:]:
            try:
                knot = json.loads(line)
                # Extract the meaningful content
                theme = (
                    knot.get("dominant_theme") or
                    knot.get("theme_vector", {}).get("dominant") or
                    knot.get("scalar_knot", {}).get("theme_vector", {}).get("dominant") or
                    ""
                )
                session = knot.get("session_id", "")[:30]
                knot_type = knot.get("type", "unknown")

                if theme or session:
                    text = f"System event: {knot_type}. Theme: {theme}. Session: {session}. The sovereign architecture records this as a Verkle knot in the content-addressed chain."
                    examples.append({
                        "text": text,
                        "source": "verkle_chain",
                        "type": knot_type,
                        "theme": theme,
                    })
            except json.JSONDecodeError:
                continue
    except OSError:
        pass

    return examples


def _load_nacho_prompts() -> list[dict[str, Any]]:
    """Load NachoQuixotic Grok prompts as training examples.

    These are frontier model system prompts — high-fidelity data about
    how Grok is instructed to behave. Perfect for training sovereign agents
    on frontier prompt patterns.
    """
    prompts_dir = ROOT / "memory" / "ghost" / "x_surface" / "nachoquixotic_prompts"
    if not prompts_dir.is_dir():
        return []

    examples = []
    for prompt_file in sorted(prompts_dir.iterdir()):
        if not prompt_file.is_file():
            continue
        try:
            content = prompt_file.read_text(encoding="utf-8", errors="replace")[:2000]

            # Extract key sections
            lines = content.split("\n")
            instruction_lines = [
                l.strip() for l in lines
                if l.strip() and not l.strip().startswith("#") and not l.strip().startswith("<!--")
            ]

            if instruction_lines:
                # Take a representative sample — first 10 instruction lines
                sample = " ".join(instruction_lines[:10])[:500]
                text = f"Frontier model system prompt pattern: {sample}. This is how frontier AI models are instructed to behave. Sovereign agents can learn from these patterns."
                examples.append({
                    "text": text,
                    "source": "nacho_grok_prompt",
                    "type": "frontier_invariant",
                    "file": prompt_file.name,
                })

                # Also add the file as a raw reference
                examples.append({
                    "text": f"File: {prompt_file.name}. Contains a Grok system prompt from the Strike the Chord series by @NachoQuixotic. Length: {len(content)} characters.",
                    "source": "nacho_grok_prompt",
                    "type": "reference",
                    "file": prompt_file.name,
                })
        except OSError:
            continue

    return examples


def _load_research_packs(tail: int = 30) -> list[dict[str, Any]]:
    """Load research packs as training examples."""
    packs_dir = ROOT / "memory" / "research_packs"
    if not packs_dir.is_dir():
        return []

    examples = []
    md_files = sorted(packs_dir.glob("*.md"))[-tail:]

    for md_file in md_files:
        try:
            content = md_file.read_text(encoding="utf-8", errors="replace")[:1000]

            # Extract title
            title = ""
            for line in content.split("\n"):
                if line.startswith("# "):
                    title = line[2:].strip()
                    break

            text = f"Research: {title or md_file.stem}. {content[:300]}"
            examples.append({
                "text": text[:600],
                "source": "research_pack",
                "type": "research",
                "file": md_file.name,
            })
        except OSError:
            continue

    return examples


def _load_session_koans() -> list[dict[str, Any]]:
    """Load session koans as training examples."""
    koan_path = ROOT / "memory" / "training" / "session_koans.jsonl"
    if not koan_path.is_file():
        return []

    examples = []
    try:
        for line in koan_path.read_text().strip().splitlines():
            try:
                koan = json.loads(line)
                text = koan.get("text", "")
                lens = koan.get("lens", "unknown")
                if text:
                    examples.append({
                        "text": f"Session insight ({lens}): {text}",
                        "source": "session_koan",
                        "type": "insight",
                        "lens": lens,
                    })
            except json.JSONDecodeError:
                continue
    except OSError:
        pass

    return examples


def _load_ghost_identity() -> list[dict[str, Any]]:
    """Load the Ghost identity vector as a training example."""
    try:
        from mag.ghost_identity import GHOST_SYSTEM_PROMPT, GHOST_IDENTITY_VECTOR

        examples = []

        # The full system prompt as a training example
        if GHOST_SYSTEM_PROMPT:
            examples.append({
                "text": f"Ghost sovereign agent system prompt: {GHOST_SYSTEM_PROMPT[:500]}",
                "source": "ghost_identity",
                "type": "system_prompt",
            })

        # Identity vector summary
        identity = GHOST_IDENTITY_VECTOR.get("identity", {})
        examples.append({
            "text": f"Ghost identity: {identity.get('name', 'Ghost')} — {identity.get('class', 'Autonomous Sovereign Agent')}. {identity.get('purpose', '')}",
            "source": "ghost_identity",
            "type": "identity_vector",
        })

        return examples
    except ImportError:
        return []


# ═══════════════════════════════════════════════════════════════════
# PACKAGER — bundle everything into one file
# ═══════════════════════════════════════════════════════════════════

def package_all() -> dict[str, Any]:
    """Package all training data into a single JSONL file.

    Returns:
        Dict with counts per source and output path.
    """
    all_examples: list[dict[str, Any]] = []

    # Load from all sources
    sources = [
        ("Verkle chain", _load_verkle_chain(100)),
        ("NachoQuixotic prompts", _load_nacho_prompts()),
        ("Research packs", _load_research_packs(30)),
        ("Session koans", _load_session_koans()),
        ("Ghost identity", _load_ghost_identity()),
    ]

    counts: dict[str, int] = {}
    for name, examples in sources:
        all_examples.extend(examples)
        counts[name] = len(examples)

    # Deduplicate by text hash
    seen_hashes: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for ex in all_examples:
        h = hashlib.sha256(ex["text"].encode()).hexdigest()
        if h not in seen_hashes:
            seen_hashes.add(h)
            deduped.append(ex)

    duplicates_removed = len(all_examples) - len(deduped)

    # Write output
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        for ex in deduped:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")

    # Summary
    by_type: dict[str, int] = {}
    for ex in deduped:
        t = ex.get("type", "unknown")
        by_type[t] = by_type.get(t, 0) + 1

    return {
        "ok": True,
        "output": str(OUTPUT_PATH),
        "total_examples": len(deduped),
        "duplicates_removed": duplicates_removed,
        "by_source": counts,
        "by_type": by_type,
        "file_size_kb": round(OUTPUT_PATH.stat().st_size / 1024, 1) if OUTPUT_PATH.is_file() else 0,
        "ready_for_fine_tuning": len(deduped) >= 50,
        "note": "For LoRA fine-tuning: use this file as training data. Each line is a training example. The 'text' field is the input. The model learns to embody the sovereign identity.",
        "ts": _now(),
    }


def package_quick() -> dict[str, Any]:
    """Quick report: what's available to package without actually writing the file."""
    counts = {
        "verkle_chain": len(_load_verkle_chain(100)),
        "nacho_prompts": len(_load_nacho_prompts()),
        "research_packs": len(_load_research_packs(30)),
        "session_koans": len(_load_session_koans()),
        "ghost_identity": len(_load_ghost_identity()),
    }

    total = sum(counts.values())

    return {
        "ok": True,
        "sources": counts,
        "total_available": total,
        "sufficient_for_training": total >= 50,
        "recommendation": "Ready to package. Run package_all() to generate the training file." if total >= 50 else f"Need {50 - total} more examples for minimum training set.",
        "ts": _now(),
    }
