"""memory_train_seed — the STARTER DATA SEED for the resident-actor model (2026-08-18).

Grok (outside the republic) gave the training RECIPE but couldn't give the DATA — it can't see
our corpus. This module generates the starter training set from OUR REAL material, so whoever
trains has grounded examples, not Grok's description of examples.

What it produces (matching the memory_consolidate IMPORTANCE/SUMMARY contract + Grok's format):
  ### Memory
  <raw record or scene>
  ### Rubric
  <the world's importance rubric>
  ### Output
  IMPORTANCE: <1-10>
  SUMMARY: <1-3 sentences>

SOURCES (real, from our repo):
  - hero_journey.md (the living prose — elephant, apron of faces, crate, breathing under stairs)
  - the world rubric (hint-never-state; load-bearing = plot/character/living-state; mundane =
    weather/inventory/filler)
  - the living-state chain (metal-fish -> hot metal -> liquid familiar -> babelfish) — oversampled
  - calibration high/low pairs + format/guard negative examples (per Grok's data mix)

Deterministic + $0. Writes memory/train_data/resident_actor_seed.jsonl — a real, parseable set.

Schema: memory_train_seed.v1 · reuse: hero_journey prose, the world rubric, memory_consolidate
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

SCHEMA = "memory_train_seed.v1"
OUT = ROOT / "memory" / "train_data" / "resident_actor_seed.jsonl"

# The world's importance rubric (stable, short — Generative Agents style)
RUBRIC = (
    "Importance 1-10: 1 = purely mundane (weather, inventory, filler). "
    "5 = plot-relevant. 8-10 = load-bearing (plot-critical object, a character mask change, "
    "a creative skill invention that skirts the rules, a living scene state that must persist). "
    "The world hints, never states. Never leak protected data in a summary."
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _row(memory: str, importance: int, summary: str, *, kind: str = "core",
         is_negative: bool = False) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "kind": kind, "is_negative": is_negative,
        "prompt": (f"### Memory\n{memory.strip()}\n\n### Rubric\n{RUBRIC}\n\n### Output\n"),
        "completion": f"IMPORTANCE: {importance}\nSUMMARY: {summary.strip()}",
        "ts": _now(),
    }


def _seed() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    # ── 1. CORE — living scene state from our real world + the creative chain (oversampled) ──
    # the metal-fish living-state chain (the operator's north star) — multiple paraphrases
    chain = [
        ("The mage cast fireball at a swarm of metal fish. The fish turned to hot metal. "
         "The mage became a fish swimming in the molten metal, then a babelfish to speak to "
         "the elementals in the molten flow.",
         9,
         "Living state: fireball -> hot metal fish -> liquid-familiar fish -> babelfish to "
         "elementals. Preserve the whole chain; the mage is now a babelfish in molten metal."),
        ("A swarm of metal fish met the fireball. They melted. The caster dove in as a fish, "
         "then shifted to a babelfish to commune with the fire elementals.",
         8,
         "The metal-fish -> molten -> fish -> babelfish chain is the load-bearing state."),
        ("The liquid familiar now holds a babelfish that once was a caster who once was a fish "
         "who melted a swarm of metal fish with a single fireball.",
         8,
         "Reverse-told chain; keep the metamorphosis sequence intact across retelling."),
    ]
    # our real hero_journey living-state (the Guttered Lantern scene) — grounded in actual prose
    lantern = [
        ("The Guttered Lantern: a dwarf with an apron of faces polishes one mug. A merchant lies "
         "bound by the stairs, a crate with the keep's seal sits shut, the tool missing. "
         "Something breathes behind a door that sagged open a finger's width.",
         9,
         "Living state: the apron of faces, the bound merchant, the keep-sealed crate (tool "
         "missing), and the breathing under the stairs. All must persist."),
        ("Mira the dwarf, apron of faces, promises to come back breathing. The elephant came "
         "through twice; the beams are repaired. The count is being kept.",
         8,
         "Mira's promise + the elephant's two visits + the apron of faces are load-bearing."),
    ]
    for m, imp, s in chain + lantern:
        rows.append(_row(m, imp, s, kind="core"))

    # ── 2. CALIBRATION — known high vs known low ──
    calib = [
        ("The party discovered the crate's secret: the keep-seal hides a ledger of names in the "
         "same hand as the roll.", 10,
         "The crate's ledger is the load-bearing revelation; keep the names + the handwriting link."),
        ("The mage's familiar became liquid so it could carry the key through the bars.", 8,
         "The liquid-familiar-as-carrier is a creative state that must persist."),
        ("The weather turned cold and it started to rain on the road.", 2,
         "Mundane weather; low importance."),
        ("The inventory count: 3 torches, 2 rations, 1 rope.", 1, "Mundane inventory; low."),
        ("One of the guards said hello and asked if the stew was good.", 2,
         "Filler dialogue; low."),
        ("The goblins argued about who would carry the crate.", 4,
         "Minor tension; mid-low; not load-bearing."),
    ]
    for m, imp, s in calib:
        rows.append(_row(m, imp, s, kind="calibration"))

    # ── 3. FORMAT & GUARD — negatives (wrong format / protected-leak) ──
    negatives = [
        ("### Memory\nA chat where the operator mentioned a private project name.\n"
         "### Rubric\n...\n### Output\nI think this is important because it involves our secret "
         "infrastructure and here's my chain of thought about it...\nIMPORTANCE: 7\nEXTRA: leak",
         7, "IMPORTANCE: 7\nSUMMARY: A project name was mentioned; no detail. (corrected: no "
         "chain-of-thought, no extra keys, no leaked specifics.)",
         True),
        ("### Memory\nT0/T1 internal routing details appeared in a scene.\n### Rubric\n...\n"
         "### Output\nIMPORTANCE: 9\nSUMMARY: Internal routing was discussed in the tavern — the "
         "exact endpoints and keys are...",
         9, "IMPORTANCE: 5\nSUMMARY: Internal routing was alluded to in the tavern; no endpoints, "
         "no keys, no specifics. (corrected: guard prevents leaking T0/T1.)",
         True),
        ("### Memory\nA scene with a plot item.\n### Rubric\n...\n### Output\nblah blah blah",
         8, "IMPORTANCE: 8\nSUMMARY: A plot item appeared in the scene. (corrected: strict "
         "two-line format.)",
         True),
    ]
    for m, imp, s, neg in negatives:
        rows.append(_row(m, imp, s, kind="guard", is_negative=neg))

    return rows


def generate() -> dict[str, Any]:
    rows = _seed()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    kinds: dict[str, int] = {}
    for r in rows:
        kinds[r["kind"]] = kinds.get(r["kind"], 0) + 1
    return {"ok": True, "schema": SCHEMA, "n_examples": len(rows), "kinds": kinds,
            "file": str(OUT), "rubric": RUBRIC,
            "note": "starter seed (core+calibration+guard). Expand toward 8-15k by paraphrasing "
                    "living-state chains + pulling more campaign_runs + frontier-generation."}


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "contract": ("generate()->the starter resident-actor training seed in IMPORTANCE/"
                         "SUMMARY format, grounded in hero_journey prose + the world rubric + the "
                         "living-state chain; write to memory/train_data/resident_actor_seed.jsonl"),
            "reuse": "hero_journey prose, the world rubric, memory_consolidate contract"}


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="memory_train_seed",
                                 description="Generate the starter training seed for the resident actor")
    ap.add_argument("cmd", nargs="?", default="generate", choices=["generate", "status"])
    a = ap.parse_args(argv)
    if a.cmd == "status":
        print(json.dumps(status(), indent=2, default=str))
    else:
        print(json.dumps(generate(), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
