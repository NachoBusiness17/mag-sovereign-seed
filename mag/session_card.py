"""Human-facing session cards: short paragraph + bullets of what the day was.

Filters Grok system chrome so cards describe *operator work*, not scaffolding.
"""
from __future__ import annotations

import re
from typing import Any

_NOISE_MARKERS = (
    "system-reminder",
    "<user_info>",
    "user_info>",
    "agent_skills",
    "mcp servers connected",
    "available tools",
    "available render",
    "today's date:",
    "prefer using relative paths",
    "function calls to help you solve",
    "do not mention these guidelines",
    "session is being continued from a previous conversation",
    "summary below covers the earlier portion",
    "<image_files>",
    "image_files>",
    "chat_history.jsonl",
    "re-read this dossier before inventing",
    "check scrum board if republic",
    "keep steiniger as method inspiration",
    "full transcript remains in",
    "xai-",  # api key fragments
    "sk-",
    "api_key",
)


def _is_noise(text: str) -> bool:
    if not text or len(text.strip()) < 8:
        return True
    low = text.lower()
    if any(m in low for m in _NOISE_MARKERS):
        return True
    # pure tool/system blobs
    if low.startswith("os version:") or low.startswith("shell:"):
        return True
    # long opaque tokens (keys)
    if re.search(r"\b[a-z0-9_\-]{40,}\b", low) and " " not in text.strip()[:50]:
        return True
    if re.search(r"(xai-|sk-|gsk_)[a-zA-Z0-9]{20,}", text):
        return True
    return False


def clean_operator_text(text: str) -> str:
    if not text:
        return ""
    m = re.search(r"<user_query>\s*(.*?)\s*</user_query>", text, re.I | re.S)
    if m:
        text = m.group(1)
    text = re.sub(r"</?user_query>", "", text, flags=re.I)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:400]


def real_operator_asks(dossier: dict[str, Any], *, limit: int = 12) -> list[str]:
    asks: list[str] = []
    seen: set[str] = set()

    def add(raw: str) -> None:
        t = clean_operator_text(raw)
        if _is_noise(t):
            return
        key = t.lower()[:80]
        if key in seen:
            return
        seen.add(key)
        asks.append(t)

    for sp in dossier.get("salient_points") or []:
        if isinstance(sp, dict) and sp.get("type") == "operator_ask":
            add(str(sp.get("text") or ""))
        elif isinstance(sp, str):
            add(sp)

    for op in dossier.get("operator_prompts") or []:
        if isinstance(op, dict):
            add(str(op.get("text") or ""))
        else:
            add(str(op))

    # chronological: salient often already last-N; keep order, cap
    return asks[:limit]


def build_session_card(dossier: dict[str, Any], narrative_md: str | None = None) -> dict[str, Any]:
    """Return {title, blurb, bullets, themes, one_liner}."""
    chord = dossier.get("chord") or {}
    time = dossier.get("time") or {}
    sk = dossier.get("scalar_knot") or {}
    themes = dossier.get("themes") or []
    theme_ids: list[str] = []
    for t in themes:
        if isinstance(t, dict) and t.get("id"):
            theme_ids.append(str(t["id"]))
        elif isinstance(t, str):
            theme_ids.append(t)
    theme_ids = theme_ids[:5]
    dominant = (sk.get("theme_vector") or {}).get("dominant") or (
        theme_ids[0] if theme_ids else None
    )

    asks = real_operator_asks(dossier, limit=10)
    moves = list(chord.get("disentangled_moves") or [])[:4]
    open_loops = list(dossier.get("open_loops") or [])[:3]
    impact = clean_operator_text(str(chord.get("personal_impact") or ""))
    if _is_noise(impact):
        impact = ""

    # Title: prefer human title unless it's a noise commitment hash
    raw_title = str(time.get("title") or "").strip()
    if not raw_title or raw_title.startswith("chord-") or len(raw_title) < 4:
        if asks:
            raw_title = asks[0][:72]
            if len(asks[0]) > 72:
                raw_title = raw_title.rsplit(" ", 1)[0] + "…"
        elif dominant:
            raw_title = f"Session · {dominant}"
        else:
            raw_title = "Work session"

    # Bullets: real operator asks only (no stock dossier moves)
    bullets: list[str] = []
    for a in asks[:6]:
        b = a if len(a) <= 160 else a[:157] + "…"
        bullets.append(b)

    if len(bullets) < 3:
        for m in moves:
            m = clean_operator_text(str(m))
            if _is_noise(m):
                continue
            if m and m not in bullets and len(bullets) < 6:
                bullets.append(m[:140])

    if len(bullets) < 2 and open_loops:
        for o in open_loops:
            o = clean_operator_text(str(o))
            if not _is_noise(o):
                bullets.append(o[:140])
            if len(bullets) >= 4:
                break

    if not bullets:
        bullets = [
            f"Themes: {', '.join(theme_ids)}" if theme_ids else "Session recorded",
        ]

    # Paragraph
    n_user = (dossier.get("stats") or {}).get("user_turns")
    dur = sk.get("duration_minutes")
    theme_bit = ", ".join(theme_ids[:4]) if theme_ids else "mixed work"
    if asks:
        lead = asks[0]
        if len(asks) == 1:
            mid = ""
        elif len(asks) == 2:
            mid = f" Also: {asks[1][:90]}{'…' if len(asks[1]) > 90 else ''}."
        else:
            mid = (
                f" Thread also moved through {len(asks) - 1} other asks "
                f"(e.g. “{asks[1][:50]}…”)."
            )
        blurb = (
            f"{lead}"
            f"{'' if lead.endswith(('?', '.', '!')) else '.'}"
            f"{mid} "
            f"Tags: {theme_bit}."
        )
    else:
        plain = clean_operator_text(str(chord.get("plain_english") or dossier.get("tldr") or ""))
        if plain and not _is_noise(plain) and "worked the knot around" not in plain.lower():
            blurb = plain[:420]
        else:
            blurb = f"Recorded workday tagged {theme_bit}."
        if impact:
            blurb += f" Stakes: {impact[:180]}"

    meta_bits = []
    if n_user:
        meta_bits.append(f"{n_user} operator turns")
    if dur is not None:
        try:
            meta_bits.append(f"~{int(float(dur))} min")
        except (TypeError, ValueError):
            pass
    if meta_bits:
        blurb = blurb.rstrip() + " (" + ", ".join(meta_bits) + ")."

    # one-liner for table compact view
    one_liner = asks[0][:100] if asks else blurb[:100]
    if len(one_liner) >= 100:
        one_liner = one_liner.rsplit(" ", 1)[0] + "…"

    return {
        "schema": "session_card.v1",
        "title": raw_title[:100],
        "one_liner": one_liner,
        "blurb": blurb[:600].strip(),
        "bullets": bullets[:7],
        "themes": theme_ids,
        "dominant_theme": dominant,
        "ask_count": len(asks),
    }


def attach_card_to_dossier(dossier: dict[str, Any], narrative_md: str | None = None) -> dict[str, Any]:
    card = build_session_card(dossier, narrative_md)
    dossier["session_card"] = card
    # improve human title in time block for list_sessions
    if dossier.get("time") is None:
        dossier["time"] = {}
    if isinstance(dossier["time"], dict) and card.get("title"):
        old = str(dossier["time"].get("title") or "")
        if not old or old.startswith("chord-") or "worked the knot" in old.lower():
            dossier["time"]["title"] = card["title"]
    if card.get("blurb"):
        dossier["tldr"] = card["blurb"][:500]
    return dossier


def recompute_card_file(dossier_path: Any) -> dict[str, Any]:
    """Rewrite dossier JSON with refreshed session_card. path-like."""
    from pathlib import Path
    import json

    p = Path(dossier_path)
    d = json.loads(p.read_text(encoding="utf-8"))
    sid = d.get("session_id") or p.name.replace(".dossier.json", "")
    md = p.parent / f"{sid}.md"
    narrative = md.read_text(encoding="utf-8", errors="replace") if md.is_file() else None
    attach_card_to_dossier(d, narrative)
    p.write_text(json.dumps(d, indent=2, default=str), encoding="utf-8")
    latest = p.parent / "latest.dossier.json"
    if latest.is_file():
        try:
            ld = json.loads(latest.read_text(encoding="utf-8"))
            if ld.get("session_id") == sid:
                latest.write_text(json.dumps(d, indent=2, default=str), encoding="utf-8")
        except (json.JSONDecodeError, OSError):
            pass
    return d.get("session_card") or {}


def recompute_all_cards() -> dict[str, Any]:
    from pathlib import Path
    from config import ROOT

    bio = ROOT / "memory" / "biography"
    paths = list(bio.glob("*.dossier.json"))
    residual = bio / "residual"
    if residual.is_dir():
        paths.extend(residual.glob("*.json"))
    cards = []
    seen: set[str] = set()
    for p in sorted(paths):
        if p.name.startswith("latest"):
            continue
        sid = p.stem if p.parent.name == "residual" else p.name.replace(
            ".dossier.json", ""
        )
        if sid in seen:
            continue
        seen.add(sid)
        try:
            card = recompute_card_file(p)
            # re-publish residual + registry when residual module present
            try:
                from mag.registry import load_residual, publish_residual

                d = load_residual(sid)
                if d:
                    publish_residual(sid, d, write_md=False)
            except Exception:
                pass
            cards.append({"session_id": sid, **card})
        except Exception as e:
            cards.append({"session_id": sid, "error": str(e)[:120]})
    return {"ok": True, "n": len(cards), "cards": cards}
