"""Narrative corpus query — inspiration packs for Slow color / DM craft.

Schema: mag_corpus_query.v1
Law:
  - PD / Mag seeds / craft notes: fulltext search OK
  - Catalog-only authors: tags + short fair-use leaves, not pirate novels
  - Never invent engine truth; returns inspiration only
Modes: keyword | adjacent | quote | topic
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from config import ROOT

SCHEMA = "mag_corpus_query.v1"

# Craft leaves always available (no clone required)
_CRAFT_LEAVES: list[dict[str, Any]] = [
    {
        "id": "craft_leguin_clean",
        "source": "craft_leaf",
        "tags": ["leguin", "prose", "concrete", "place", "tavern", "clarity"],
        "license": "notes_not_novels",
        "text": (
            "Name the room by what it does to the body: stickiness of tables, "
            "argument of fire with damp, broth that has known better vegetables. "
            "Cut ornament. Let moral weather sit in objects, not sermons."
        ),
        "quotes": [
            "Let the place do the talking through smell and weight.",
            "Concrete first — philosophy only if a mug can hold it.",
        ],
    },
    {
        "id": "craft_threshold",
        "source": "craft_leaf",
        "tags": ["campbell", "threshold", "hub", "brawl", "call", "return"],
        "license": "structure_energy",
        "text": (
            "Threshold energy: peace becomes violence without leaving the room. "
            "The tavern is still the world after the brawl. Return is sitting down "
            "with a new scar and the same sticky table."
        ),
        "quotes": [
            "The night stops being ordinary at the edge of a chair.",
            "You do not leave the hub to change — the hub changes around you.",
        ],
    },
    {
        "id": "craft_shadow_blame",
        "source": "craft_leaf",
        "tags": ["jung", "shadow", "blame", "party", "failed_hunt", "rashomon"],
        "license": "structure_energy",
        "text": (
            "Blame is a shadow the party throws when the mark escapes. "
            "Each voice needs a villain more than a window. Engine holds what "
            "happened; mouths hold who they need it to be."
        ),
        "quotes": [
            "Three windows in three mouths. One broken mug.",
            "The stranger at the bar becomes convenient weather.",
        ],
    },
    {
        "id": "craft_attention_bark",
        "source": "craft_leaf",
        "tags": ["attention", "bark", "comedy", "bar", "wit"],
        "license": "fiction_frame_only",
        "text": (
            "Each bark wants your side. Comedy is a weapon and a shield. "
            "Absurdity can steal the room's plot without changing HP until the "
            "engine says so."
        ),
        "quotes": [
            "They will tell this story wrong for years.",
            "Dignity optional. Progress intact.",
        ],
    },
    {
        "id": "craft_if_hub",
        "source": "craft_leaf",
        "tags": ["if", "hub", "ink", "twine", "passage", "environment"],
        "license": "structure",
        "text": (
            "Hub loop: interior image, area frame, environment weather, "
            "narrator pressure, soft leads — not a prison menu. Spilled ale is "
            "state. Noise is environment. Heat is story flag made audible."
        ),
        "quotes": [
            "The common room is a knot you can leave and re-enter.",
            "Soft leads invite; they do not cage.",
        ],
    },
    {
        "id": "craft_temple_box",
        "source": "craft_leaf",
        "tags": ["temple", "puzzle", "dragon", "necromancer", "troll", "ward", "campbell", "dungeon"],
        "license": "structure",
        "text": (
            "The keep is a temple. The crate is a puzzle box. Each ward is a beast: "
            "troll army, necromancer, dragon. Slaying is how the work gets done. "
            "The hoard is shared. No one keeps the eye."
        ),
        "quotes": [
            "Open the box. Name the beast. Share the hoard.",
            "A temple is a dungeon that remembers why you came.",
        ],
    },
    {
        "id": "craft_vonnegut",
        "source": "craft_leaf",
        "tags": ["vonnegut", "pace", "want", "end", "cruelty", "so_it_goes"],
        "license": "notes_not_novels",
        "text": (
            "Start as close to the end as possible. Every character wants something, "
            "even a glass of water. Be a sadist: put them in trouble, then more trouble. "
            "Cut every sentence that does not work. Pity is allowed; apology is not."
        ),
        "quotes": [
            "Start as close to the end as possible.",
            "Every character should want something, even if it is only a glass of water.",
        ],
    },
    {
        "id": "craft_legend_sim",
        "source": "craft_leaf",
        "tags": ["dwarf_fortress", "rimworld", "legend", "emergence", "history", "roguelike"],
        "license": "structure",
        "text": (
            "Do not invent the plot. The sim already happened: a fight, a bound merchant, "
            "a crate with a seal, a fire that followed. The narrator only names what the "
            "world already did, in the voice of a history that does not flinch."
        ),
        "quotes": [
            "The world writes. You only read it aloud.",
            "A legend is a log that learned to breathe.",
        ],
    },
    {
        "id": "craft_time_tangent",
        "source": "craft_leaf",
        "tags": ["time", "titor", "tangent", "research", "scifi", "wells"],
        "license": "pd_adjacent",
        "text": (
            "A tangent (time travel, rumor of tomorrow) should return as in-world "
            "pressure: a stranger's half-true map, a wrong clock, a keep that "
            "smokes black out of season — never as OOC lecture."
        ),
        "quotes": [
            "The future arrives as bad weather and worse gossip.",
            "Research is a rumor until the engine files it.",
        ],
    },
]

_STOP = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "of",
    "to",
    "in",
    "on",
    "for",
    "is",
    "are",
    "was",
    "with",
    "that",
    "this",
    "as",
    "at",
    "by",
    "from",
    "it",
    "be",
    "not",
    "you",
    "your",
    "they",
    "their",
    "we",
    "our",
}


def _tokens(q: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9']{3,}", (q or "").lower()) if t not in _STOP]


def _score(text: str, tags: list[str], toks: list[str]) -> float:
    if not toks:
        return 0.0
    blob = (text or "").lower() + " " + " ".join(tags).lower()
    hits = sum(1 for t in toks if t in blob)
    tag_hits = sum(1 for t in toks if any(t in g for g in tags))
    return hits + tag_hits * 1.5


def _load_disk_leaves(*, max_files: int = 40) -> list[dict[str, Any]]:
    """Mag seeds + short PD slices. Skips huge code trees."""
    out: list[dict[str, Any]] = []
    roots = [
        ROOT / "memory" / "narrative_corpus",
        ROOT / "mine" / "raw" / "narrative_corpus" / "public_domain",
    ]
    n = 0
    for root in roots:
        if not root.is_dir():
            continue
        for p in sorted(root.rglob("*")):
            if n >= max_files:
                break
            if not p.is_file():
                continue
            if p.suffix.lower() not in (".md", ".txt"):
                continue
            # skip giant files
            try:
                if p.stat().st_size > 400_000:
                    # sample head of PD novels
                    raw = p.read_text(encoding="utf-8", errors="ignore")[:12000]
                else:
                    raw = p.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            # chunk into ~800 char leaves
            chunks = re.split(r"\n{2,}", raw)
            buf = ""
            for ch in chunks:
                buf = (buf + "\n\n" + ch).strip()
                if len(buf) < 400:
                    continue
                leaf_text = buf[:900]
                tags = re.findall(r"[a-z]{4,}", leaf_text.lower())[:20]
                quotes = []
                for ln in leaf_text.splitlines():
                    s = ln.strip()
                    if not (40 <= len(s) <= 160):
                        continue
                    if s.startswith("#") or s.startswith("|") or s.startswith("```"):
                        continue
                    if re.search(
                        r"(?i)\b(schema|train labels|hard_negative|salon_use|"
                        r"engine truth|perspective:|\*\*use\*\*|license_note)\b",
                        s,
                    ):
                        continue
                    if s.startswith("**") and ":" in s[:40]:
                        continue
                    quotes.append(s)
                    if len(quotes) >= 3:
                        break
                out.append(
                    {
                        "id": f"disk:{p.stem}:{n}",
                        "source": str(p.relative_to(ROOT)).replace("\\", "/")[:120],
                        "tags": list(dict.fromkeys(tags))[:12],
                        "license": "pd_or_mag_seed",
                        "text": leaf_text,
                        "quotes": quotes,
                    }
                )
                n += 1
                buf = ""
                if n >= max_files:
                    break
    return out


def _catalog_tags() -> list[dict[str, Any]]:
    """From yaml catalog_only — tags only."""
    p = ROOT / "configs" / "narrative_corpus.yaml"
    if not p.is_file():
        return []
    try:
        import yaml

        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except Exception:
        return []
    out = []
    for row in data.get("catalog_only") or []:
        if not isinstance(row, dict):
            continue
        focus = str(row.get("steal_focus") or "")
        tags = re.findall(r"[a-z0-9_]+", focus.lower())
        out.append(
            {
                "id": f"catalog:{row.get('id')}",
                "source": "catalog_only",
                "tags": tags + [str(row.get("kind") or "")],
                "license": str(row.get("license") or "catalog"),
                "text": f"{row.get('id')}: {focus}",
                "quotes": [],
                "urls": row.get("urls") or [],
            }
        )
    return out


def _all_leaves() -> list[dict[str, Any]]:
    return list(_CRAFT_LEAVES) + _catalog_tags() + _load_disk_leaves()


def query(
    q: str,
    *,
    mode: str = "topic",
    limit: int = 5,
) -> dict[str, Any]:
    """Return inspiration pack. Modes: topic|keyword|adjacent|quote."""
    mode = (mode or "topic").lower().strip()
    toks = _tokens(q)
    leaves = _all_leaves()
    scored: list[tuple[float, dict[str, Any]]] = []
    for leaf in leaves:
        s = _score(str(leaf.get("text") or ""), list(leaf.get("tags") or []), toks)
        if mode == "quote" and not leaf.get("quotes"):
            s *= 0.3
        if s > 0:
            scored.append((s, leaf))
    # fallback: craft leaves by soft defaults for empty query
    if not scored and not toks:
        scored = [(1.0, leaf) for leaf in _CRAFT_LEAVES[:limit]]
    if not scored and toks:
        # soft default tavern/brawl pack
        for leaf in _CRAFT_LEAVES:
            scored.append((0.5, leaf))
    scored.sort(key=lambda x: -x[0])
    top = [dict(leaf, score=round(sc, 2)) for sc, leaf in scored[: max(1, limit)]]

    quotes: list[str] = []
    tags: list[str] = []
    # Prefer craft_leaf quotes first (clean prose)
    ordered = sorted(
        top,
        key=lambda l: (0 if str(l.get("source") or "") == "craft_leaf" else 1, -float(l.get("score") or 0)),
    )
    for leaf in ordered:
        for qt in leaf.get("quotes") or []:
            qts = str(qt).strip()
            if not qts or qts in quotes:
                continue
            if qts.startswith("**") or "schema" in qts.lower():
                continue
            quotes.append(qts)
        for t in leaf.get("tags") or []:
            if t not in tags:
                tags.append(str(t))

    adjacent: list[str] = []
    if mode in ("adjacent", "topic", "keyword") and top:
        # words near query tokens in best leaf
        blob = " ".join(str(l.get("text") or "") for l in top)
        words = re.findall(r"[a-z']{4,}", blob.lower())
        for i, w in enumerate(words):
            if w in toks:
                for j in range(max(0, i - 2), min(len(words), i + 3)):
                    if words[j] not in toks and words[j] not in _STOP:
                        adjacent.append(words[j])
        adjacent = list(dict.fromkeys(adjacent))[:12]

    pack = {
        "schema": SCHEMA,
        "query": (q or "")[:200],
        "mode": mode,
        "leaves": [
            {
                "id": l.get("id"),
                "source": l.get("source"),
                "score": l.get("score"),
                "tags": (l.get("tags") or [])[:8],
                "excerpt": str(l.get("text") or "")[:280],
                "license": l.get("license"),
            }
            for l in top
        ],
        "quotes": quotes[:6],
        "tags": tags[:16],
        "adjacent": adjacent,
        "craft_hint": (top[0].get("text") if top else "")[:400],
    }
    return {"ok": True, "schema": SCHEMA, "pack": pack}


def inspire_for_scene(
    *,
    story: str = "",
    room: str = "",
    flags: list[str] | None = None,
    absurd: bool = False,
    events_tail: list[str] | None = None,
    limit: int = 4,
) -> dict[str, Any]:
    """Build a query string from scene pressure and return pack."""
    bits = [story, room]
    bits.extend(flags or [])
    if absurd:
        bits.append("absurd comedy bark attention")
    if events_tail:
        bits.append(" ".join(str(e) for e in events_tail[:3]))
    if "failed_hunt" in (flags or []) or "failed" in (story or "").lower():
        bits.append("blame shadow threshold party")
    if "tavern" in (room or "").lower() or "lantern" in (room or "").lower():
        bits.append("tavern hub ale environment concrete place leguin")
    rl = (room or "").lower() + " " + (story or "").lower()
    if any(w in rl for w in ("keep", "gate", "claw", "hall", "cave", "merchant", "goblin")):
        bits.append("threshold campbell concrete place leguin vonnegut legend emergence")
    if any(w in rl for w in ("dead", "down", "captive", "bound", "crate")):
        bits.append("vonnegut want end legend dwarf_fortress")
    q = " ".join(b for b in bits if b)
    return query(q, mode="topic", limit=limit)


def format_inspiration_footer(pack: dict[str, Any] | None) -> str:
    """Tiny DM-facing inspiration note (not for TTS)."""
    if not pack:
        return ""
    tags = ", ".join((pack.get("tags") or [])[:6])
    q = pack.get("quotes") or []
    lines = ["### Inspiration (silent craft)"]
    if tags:
        lines.append(f"tags: {tags}")
    if q:
        lines.append(f'echo: "{q[0]}"')
    return "\n".join(lines)
