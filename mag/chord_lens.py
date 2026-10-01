"""Strike-the-Chord concepts for session dossiers (borrowed, operational).

Source framework (operator):
  - ~/.grok/skills/strike-chord/SKILL.md
  - strike.personal_impact / consent veto methods in sovereign-mirror-scaffold
  - public strike corpus (three quiet machines, Elias rope, marble OS)

We do NOT paste the map as costume. We run the *structure* on session extracts:
  plain English → personal impact → rope → loops → moves → commitment → self-audit
  + four observer charts (money / secrets / fracture / personal rope)
  + consent boundary + anti-throne checks
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any

# Canonical root (public strike / marble OS seed) — history tip only
STRIKE_ROOT = "e11937d605a89b022d137cceae495f5c521dbbff35cd60e23189e53172cb66b5"

OBSERVER_CHARTS = [
    {
        "id": "money_machine",
        "label": "Money machine",
        "plain": "Quiet steering of option sets / capital / who can afford the path",
        "keys": [
            "fund",
            "money",
            "capital",
            "token",
            "pay",
            "cost",
            "openrouter",
            "gpu",
            "gstd",
            "billing",
            "free tier",
        ],
    },
    {
        "id": "secrets_machine",
        "label": "Secrets machine",
        "plain": "Silence, leverage, asymmetric info, private data gates",
        "keys": [
            "secret",
            "private",
            "t0",
            "t1",
            "api key",
            "password",
            "kompromat",
            "archive",
            "data/raw",
            "exfil",
        ],
    },
    {
        "id": "fracture_machine",
        "label": "Fracture machine",
        "plain": "Narrative inversion, headline conversion, attention break",
        "keys": [
            "headline",
            "trauma",
            "split",
            "fracture",
            "perform",
            "theater",
            "hype",
            "collapse",
            "toy",
            "greenwash",
        ],
    },
    {
        "id": "personal_rope",
        "label": "Personal rope",
        "plain": "Operator’s own knots that make one story feel obvious (self-side first)",
        "keys": [
            "i was",
            "i want",
            "my ",
            "thinking",
            "mirror",
            "chord",
            "biograph",
            "intent",
            "what was i",
            "locus",
        ],
    },
]

LOOP_PATTERNS = [
    (r"plan inflation|roadmap|phase\s*\d", "plan_inflation"),
    (r"polish|theater|workshop forever|empty workshop", "polish_theater"),
    (r"single.?cause|only (because|due)|just a ", "single_cause"),
    (r"performativ|hype|flatter", "performativity"),
    (r"todo|checkbox|green", "metric_theater"),
    (r"new epic|another agent|more framework", "scope_creep"),
    (r"train|r0|spore", "glory_before_soil"),
]

LOCUS_CHECKS = [
    ("truth_only", ["flatter", "spin", "middleman"]),
    ("no_throne", ["core mirror", "canonical", "admin_tier", "mirror_rank", "token_balance"]),
    ("consent", ["i do not consent", "consent"]),
    ("self_side", ["my rope", "personal", "i want", "i was thinking"]),
]


def score_charts(blob: str) -> list[dict[str, Any]]:
    blob_l = blob.lower()
    out = []
    for c in OBSERVER_CHARTS:
        hits = [k for k in c["keys"] if k in blob_l]
        score = sum(blob_l.count(k) for k in c["keys"])
        out.append(
            {
                "id": c["id"],
                "label": c["label"],
                "plain": c["plain"],
                "score": score,
                "keys_hit": hits,
                "active": score > 0,
            }
        )
    # interference signal: multiple charts active
    active_n = sum(1 for x in out if x["active"])
    for x in out:
        x["interference_with"] = active_n - (1 if x["active"] else 0)
    return out


def detect_loops(blob: str, users: list[str]) -> list[dict[str, str]]:
    text = blob.lower() + " " + " ".join(users).lower()
    found = []
    for pat, name in LOOP_PATTERNS:
        if re.search(pat, text, re.I):
            found.append(
                {
                    "id": name,
                    "plain": _loop_plain(name),
                }
            )
    return found


def _loop_plain(name: str) -> str:
    return {
        "plan_inflation": "Planning grew faster than soil (docs/epics before data/raw).",
        "polish_theater": "Polish/workshop energy risked replacing a real move.",
        "single_cause": "Pressure to collapse into one simple story.",
        "performativity": "Performance/hype pressure instead of personal impact.",
        "metric_theater": "Todos/green checks stood in for mirror fidelity.",
        "scope_creep": "New systems proposed before finishing the open knot.",
        "glory_before_soil": "R0/train/spore talk while archive gate still open.",
    }.get(name, name)


def locus_audit(blob: str) -> list[dict[str, Any]]:
    b = blob.lower()
    checks = []
    # no_throne: fail if capture fields appear as goals
    throne_hits = [k for k in LOCUS_CHECKS[1][1] if k in b]
    checks.append(
        {
            "id": "no_throne",
            "ok": len(throne_hits) == 0,
            "note": "No rank/token/core privilege invented"
            if not throne_hits
            else f"Watch for: {', '.join(throne_hits)}",
        }
    )
    checks.append(
        {
            "id": "truth_bias",
            "ok": "flatter" not in b or "no flatter" in b or "truth" in b,
            "note": "Session language stays near truth-only / anti-flattery",
        }
    )
    checks.append(
        {
            "id": "self_side_present",
            "ok": any(k in b for k in LOCUS_CHECKS[3][1]),
            "note": "Operator personal stake / intent appears (Elias rope)",
        }
    )
    checks.append(
        {
            "id": "consent_boundary",
            "ok": True,  # informational
            "note": "'I do not consent' remains hard boundary when private tiers matter",
            "veto_language_seen": "consent" in b,
        }
    )
    return checks


def build_chord_strike(
    *,
    session_id: str,
    users: list[str],
    assts: list[str],
    tools: list[str],
    themes: list[dict[str, Any]],
    tension: list[str],
    good_moves: list[str],
    open_loops: list[str],
    dossier_commit: str | None = None,
) -> dict[str, Any]:
    """Full strike-shaped pack for one session (laymen + machine)."""
    blob = " ".join(users + assts + tools).lower()
    charts = score_charts(blob)
    loops = detect_loops(blob, users)
    locus = locus_audit(blob)

    theme_ids = [t.get("id") for t in themes[:4]]
    plain = _plain_english(theme_ids, users, assts)
    impact = _personal_impact(theme_ids, users)
    rope = _rope(tension, users, charts)
    moves = _moves(good_moves, open_loops, themes)

    # commitment slug: chord-{dominant}-{date-ish from session}
    dom = (themes[0].get("id") if themes else "session") or "session"
    slug = re.sub(r"[^a-z0-9]+", "-", dom.lower()).strip("-")[:20]
    body_for_hash = json_dumps_stable(
        {
            "plain": plain,
            "impact": impact,
            "rope": rope,
            "loops": [L["id"] for L in loops],
            "moves": moves,
            "session_id": session_id,
        }
    )
    short = hashlib.sha256(body_for_hash.encode()).hexdigest()[:10]
    commitment = f"chord-{slug}-{short}"

    self_audit = _self_audit(loops, locus, theme_ids)

    return {
        "schema": "strike_chord_session.v1",
        "struck": True,
        "activation": "session_end_biographer",
        "framework_root": STRIKE_ROOT,
        "plain_english": plain,
        "personal_impact": impact,
        "rope": rope,
        "loops_audited": loops,
        "disentangled_moves": moves,
        "commitment_hash": commitment,
        "self_audit": self_audit,
        "observer_charts": charts,
        "chart_interference": sum(1 for c in charts if c["active"]) >= 2,
        "locus_checks": locus,
        "entropy_gate": {
            "level": "high"
            if len(tension) >= 2 or any(c["score"] > 5 for c in charts)
            else "medium",
            "note": "Full chord structure used for session biography (not trivial follow-up).",
        },
        "dossier_commit_ref": dossier_commit,
        "negative_list_honored": [
            "no_saelis_as_product",
            "no_token_rank_invented",
            "no_map_regurgitation_as_insight",
        ],
    }


def json_dumps_stable(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, default=str)


def _plain_english(theme_ids: list, users: list[str], assts: list[str]) -> str:
    top = ", ".join(theme_ids) if theme_ids else "general work"
    last = ""
    if users:
        last = re.sub(r"</?user_query>", "", users[-1])
        last = re.sub(r"\s+", " ", last).strip()[:160]
    return (
        f"This session worked the knot around: {top}. "
        f"Latest operator pressure: “{last or '—'}”. "
        f"Not a finished mirror — a living record of what was actually turned."
    )


def _personal_impact(theme_ids: list, users: list[str]) -> str:
    bits = []
    if "biography" in theme_ids or "mag_hands" in theme_ids:
        bits.append(
            "Your future self’s ability to recall *what you were thinking* depends on this biographer trail."
        )
    if "scrum_plan" in theme_ids:
        bits.append("Planning energy is only useful if it unblocks soil (data/raw), not infinite board polish.")
    if "mirror_meta" in theme_ids:
        bits.append("Identity/mirror stakes: hands without meta leaves you with tools but no sovereign reading.")
    if not bits:
        bits.append(
            "Attention and option-set: what you build here either raises rope visibility or adds another foyer."
        )
    return " ".join(bits)


def _rope(tension: list[str], users: list[str], charts: list[dict]) -> str:
    if tension:
        return tension[0]
    active = [c["label"] for c in charts if c.get("active")]
    if len(active) >= 2:
        return (
            f"Interference between charts ({', '.join(active)}) — "
            "do not terminate into a single-cause story."
        )
    if users:
        u = re.sub(r"</?user_query>", "", users[-1])
        return f"Operator rope tip: {u[:200]}"
    return "Rope not named explicitly — re-open with a personal-impact question next session."


def _moves(good: list[str], loops: list[str], themes: list) -> list[str]:
    moves = []
    for g in good[:4]:
        if g and g not in moves:
            moves.append(g)
    # chord-specific minimal moves
    theme_ids = [t.get("id") for t in themes]
    if "data_r0" in theme_ids or "glory_before_soil" in str(loops):
        moves.append("Unblock W0.0 archive before train/network glory (soil first).")
    if "mag_hands" in theme_ids and "mirror_meta" in theme_ids:
        moves.append("Keep Mirror (meta/chord) above Hands (Mag chores) in the product story.")
    if "biography" in theme_ids:
        moves.append("Treat session PDF + Verkle leaf as the residual bond of the day — re-read before new epics.")
    moves.append("One disentangled next action only; refuse capture via rank/token/core.")
    # unique preserve order
    out = []
    for m in moves:
        if m not in out:
            out.append(m)
    return out[:7]


def _self_audit(loops: list, locus: list, theme_ids: list) -> str:
    risks = []
    if any(L.get("id") == "polish_theater" for L in loops):
        risks.append("polish theater")
    if any(L.get("id") == "metric_theater" for L in loops):
        risks.append("metric theater")
    if any(not c.get("ok") for c in locus if c.get("id") == "no_throne"):
        risks.append("throne language")
    if not risks:
        return "Self-audit: no obvious polish/enthrone flags in extract; still re-check personal impact."
    return f"Self-audit: watch for {', '.join(risks)} — correct before treating session as ‘done mirror’."
