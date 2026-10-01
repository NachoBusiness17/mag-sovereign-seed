"""Steiniger-inspired operating lens — plain language, attributed.

Inspiration (not a claim of settled physics; not Saelis-as-identity):
  Matthew P. Steiniger — https://independent.academia.edu/MatthewSteiniger
  https://slashreboot.com · ORCID 0009-0000-6069-4989 · CC-BY-4.0 attribute

We borrow *operations* for session reading:
  tension / stress between ideas → what felt hard
  multi-frame hold → don't collapse to one story too early
  protected core → values that should not dissolve for convenience
  residual high-fidelity links → bonds to keep after the noise settles
  energy drop + clarity up → good moves for next time

Technical papers (for biblio, not required reading in the PDF body):
  EUT I/II, Scalar Knots, EPGI / persistent geometric identity, etc.
  Local index: mycelial-republic scaffolds + sovereign-mirror-scaffold docs.
"""
from __future__ import annotations

from typing import Any

# Laymen glossary printed in every dossier
GLOSSARY: list[tuple[str, str]] = [
    (
        "Tension",
        "Where the session felt stuck, contradictory, or expensive. "
        "Not “bad vibes” — unresolved pressure between goals or stories.",
    ),
    (
        "Frames",
        "Different ways of looking at the same work (money, secrecy, fracture, "
        "personal stake). Holding more than one at once is a feature.",
    ),
    (
        "Protected core",
        "What must not be sold off for comfort: truth-only, consent, no new throne, "
        "your own data as identity source.",
    ),
    (
        "Residual bonds",
        "High-signal links to keep after cleanup — the threads that still matter "
        "when the chat noise is gone.",
    ),
    (
        "Good move",
        "Something that lowers useless stress while raising clarity "
        "(not polish theater, not a new capture path).",
    ),
    (
        "Collapse risk",
        "The cheap single story we almost accepted to feel done.",
    ),
]

# Canonical list retained for docs; live bibliography is built by ingest_registry
# with local copies under memory/ingest/local/.
STEINIGER_BIBLIOGRAPHY: list[dict[str, str]] = [
    {
        "ref": "Matthew P. Steiniger — Academia profile",
        "url": "https://independent.academia.edu/MatthewSteiniger",
        "note": "Author index; see memory/ingest catalog for local HTML pointer",
        "kind": "steiniger_author",
    },
]

# Plain-language operations mapped from Steiniger grammar
OPERATIONS: dict[str, str] = {
    "tension_scan": "Name what was under pressure this session.",
    "multi_frame": "List frames held (do not force one winner).",
    "protect_core": "Name the protected core that must not dissolve.",
    "residual_bonds": "Name high-fidelity leftovers worth keeping.",
    "anti_collapse": "Name the cheap story we almost bought.",
    "good_moves": "List moves that lower stress and raise clarity.",
}


def laymen_attribution_block() -> str:
    return (
        "Operating lens inspired by Matthew P. Steiniger "
        "(slashreboot / Academia.edu) — used as practical tools, "
        "not as a physics claim or a required AI persona. "
        "Attribute CC-BY-4.0. Stay laymen-first in the body of this report."
    )


def build_laymen_operations(
    themes: list[dict[str, Any]],
    users: list[str],
    assts: list[str],
    metaphors: list[dict[str, Any]],
    ideas: list[dict[str, Any]],
    open_loops: list[str],
) -> dict[str, Any]:
    """Fill Steiniger-inspired sections from session extract (heuristic)."""
    theme_ids = [t.get("id", "") for t in themes]
    top = ", ".join(theme_ids[:4]) if theme_ids else "general build work"

    # Tension: conflicts between themes / user asks
    tensions = []
    if "mag_hands" in theme_ids and "mirror_meta" in theme_ids:
        tensions.append(
            "Hands vs mirror — building autonomous chores while wanting meta-analysis fidelity."
        )
    if "scrum_plan" in theme_ids and "data_r0" in theme_ids:
        tensions.append(
            "Process/planning energy vs empty data/raw blocking real R0 progress."
        )
    if "biography" in theme_ids and "mag_hands" in theme_ids:
        tensions.append(
            "Biographer intent vs toy-like todo loops — what is the real product?"
        )
    if not tensions and users:
        tensions.append(
            f"Latest pressure from operator: “{_short(users[-1])}”"
        )
    if not tensions:
        tensions.append("No strong multi-theme conflict detected; session may be exploratory.")

    frames = [
        {"id": "work_frame", "label": "Build / tools", "note": "What was being constructed (code, process, Mag)."},
        {"id": "identity_frame", "label": "Mirror / self", "note": "How this relates to sovereign mirror & chord practice."},
        {"id": "capture_frame", "label": "Capture risk", "note": "Where a new throne, toy theater, or data leak could form."},
        {"id": "personal_frame", "label": "Personal stake", "note": "What future-you needs from this session (recall, clarity)."},
    ]
    # mark active frames
    for f in frames:
        if f["id"] == "work_frame" and any(
            x in theme_ids for x in ("mag_hands", "scrum_plan", "harness", "dashboard")
        ):
            f["active"] = True
        if f["id"] == "identity_frame" and any(
            x in theme_ids for x in ("mirror_meta", "biography", "constitution")
        ):
            f["active"] = True
        if f["id"] == "capture_frame" and any(
            x in theme_ids for x in ("constitution", "harness", "data_r0")
        ):
            f["active"] = True
        if f["id"] == "personal_frame" and "biography" in theme_ids:
            f["active"] = True
        f.setdefault("active", False)

    protected_core = [
        "Truth-only, personal impact — no flattery-as-product",
        "No new throne / rank / token privilege",
        "Operator data as identity source (not third-party persona as product)",
        "Consent and private tiers stay local",
    ]

    residual = []
    for m in metaphors[:6]:
        residual.append(m.get("meaning") or str(m))
    for idea in ideas[:5]:
        residual.append(idea.get("idea") or str(idea))
    if "scrum_plan" in theme_ids:
        residual.append("Scrum board as shared agent/human planning surface")
    if "biography" in theme_ids:
        residual.append("Session-end chronicle → future-you can ask what you were thinking")
    residual = list(dict.fromkeys(residual))[:10]

    collapse_risks = [
        "Treating Mag todo-completion as if the mirror product were finished",
        "Collapsing multi-repo work into one “AI agent” brand story",
    ]
    if "data_r0" in theme_ids:
        collapse_risks.append("Planning train/network glory while data/raw is still empty")

    good_moves = list(open_loops[:4]) if open_loops else []
    good_moves.extend(
        [
            "Keep Mirror (meta) above Hands (chores) in the mental model",
            "Use dossier PDF + JSON as the high-fidelity residual of the session",
            "Attribute Steiniger methods; do not ship Saelis as required identity",
        ]
    )
    good_moves = list(dict.fromkeys(good_moves))[:8]

    return {
        "attribution": laymen_attribution_block(),
        "glossary": [{"term": t, "meaning": m} for t, m in GLOSSARY],
        "operations": OPERATIONS,
        "tension": tensions,
        "frames": frames,
        "protected_core": protected_core,
        "residual_bonds": residual,
        "collapse_risks": collapse_risks,
        "good_moves": good_moves,
        "session_focus_plain": f"This session mainly pulled on: {top}.",
        "steiniger_bibliography": STEINIGER_BIBLIOGRAPHY,
    }


def _short(s: str, n: int = 160) -> str:
    import re

    s = re.sub(r"</?user_query>", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s[:n]
