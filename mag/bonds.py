"""Residual bonds — first-class next-session inputs (not scrap notes).

Promoted practice c-0a6393520bfb: residual + brief + Verkle leaf feed the *next*
session. This module ingests those artifacts into memory/bonds_active.{md,json}
and context-pack attaches them automatically.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT

BONDS_MD = ROOT / "memory" / "bonds_active.md"
BONDS_JSON = ROOT / "memory" / "bonds_active.json"
BRIEFS = ROOT / "memory" / "briefs"
WORKING = ROOT / "memory" / "working.md"
FIELD = ROOT / "memory" / "improve" / "field_brief.md"
PLAYBOOK = ROOT / "memory" / "improve" / "playbook.md"


# --- conflict-scan pass (steal c-f368762f1e82 / SubtleMemory) --------------
_NEG_WORDS = {
    "no", "not", "never", "refuse", "refuses", "refused", "deny", "denies",
    "against", "without", "anti", "block", "blocks", "reject", "rejects",
    "forbid", "forbids", "stop", "stops", "avoid", "avoids", "prevent",
}
_POS_WORDS = {
    "yes", "accept", "accepts", "allow", "allows", "support", "supports",
    "approve", "approves", "keep", "keeps", "trust", "trusts", "promote",
    "promotes", "endorse", "endorses", "favor", "favors",
    "prefer", "prefers", "advocate", "advocates", "back", "backs",
    "choose", "chooses", "value", "values", "protect", "protects",
}
_STOP = {
    "the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "for",
    "with", "as", "is", "are", "was", "were", "be", "been", "it", "its",
    "this", "that", "these", "those", "we", "you", "they", "he", "she",
    "i", "me", "my", "our", "their", "from", "by", "at", "not", "no",
}
_GLUE = {
    "here", "when", "what", "which", "where", "who", "whom", "how",
    "into", "onto", "over", "under", "than", "then", "them", "there",
    "their", "some", "any", "each", "every", "both", "also", "very",
    "much", "many", "more", "most", "only", "just", "about", "after",
    "before", "between", "during", "while", "though", "although",
    "because", "since", "until", "once", "upon", "within", "will",
    "would", "could", "should", "can", "may", "might", "must",
    "without",
}


def _polarity(text: str) -> int:
    """Crude heuristic polarity: -1 negative stance, +1 positive, 0 neutral."""
    words = re.findall(r"[a-zA-Z']+", text.lower())
    neg = sum(1 for w in words if w in _NEG_WORDS)
    pos = sum(1 for w in words if w in _POS_WORDS)
    if neg and not pos:
        return -1
    if pos and not neg:
        return 1
    return 0


def _subjects(text: str) -> set[str]:
    """Key subject words (stopwords removed, >=3 chars, no glue, hyphens split)."""
    words: list[str] = []
    for tok in re.findall(r"[a-zA-Z][a-zA-Z-]{2,}", text.lower()):
        words.extend(tok.split("-"))
    return {w for w in words if w not in _STOP and w not in _GLUE and len(w) >= 3}


def _overlap(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


def scan_conflicts(
    candidate: str,
    existing: list[str],
    *,
    min_overlap: float = 0.35,
    min_words: int = 2,
) -> list[dict[str, Any]]:
    """Return conflicts between a candidate bond and existing bonds.

    Fires when both sides have >= min_words subject words, subject overlap
    >= min_overlap, and polarities are strictly opposite.
    """
    cand_subj = _subjects(candidate)
    cand_pol = _polarity(candidate)
    if len(cand_subj) < min_words:
        return []
    out: list[dict[str, Any]] = []
    for ex in existing:
        ex_subj = _subjects(ex)
        ex_pol = _polarity(ex)
        if len(ex_subj) < min_words:
            continue
        if cand_pol == 0 or ex_pol == 0 or cand_pol == ex_pol:
            continue
        ov = _overlap(cand_subj, ex_subj)
        if ov >= min_overlap:
            out.append(
                {
                    "candidate": candidate,
                    "existing": ex,
                    "overlap": round(ov, 2),
                    "candidate_polarity": cand_pol,
                    "existing_polarity": ex_pol,
                    "subjects": sorted(cand_subj & ex_subj),
                    "conflicts_with": ex[:160],
                }
            )
    return out


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clip(path: Path, n: int = 4000) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")[:n]


def _section(md: str, heading: str) -> list[str]:
    """Extract bullet lines under ## heading until next ##."""
    lines = md.splitlines()
    out: list[str] = []
    in_sec = False
    want = heading.strip().lower().lstrip("#").strip()
    for ln in lines:
        s = ln.strip()
        if s.startswith("## "):
            title = s[3:].strip().lower()
            if in_sec:
                break
            if want in title or title in want:
                in_sec = True
            continue
        if in_sec:
            if s.startswith("#"):
                break
            if s.startswith("- ") or s.startswith("* "):
                out.append(s.lstrip("-* ").strip())
            elif re.match(r"^\d+\.\s+", s):
                out.append(re.sub(r"^\d+\.\s+", "", s).strip())
    return [x for x in out if x and x != "—"]


def _latest_session_id() -> str | None:
    latest = BRIEFS / "latest.md"
    if latest.is_file():
        text = latest.read_text(encoding="utf-8", errors="replace")
        m = re.search(r"Brief[^\n]*?([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f-]{20,})", text, re.I)
        if m:
            # may be truncated in title — prefer mtime brief file
            pass
    if not BRIEFS.is_dir():
        return None
    files = sorted(
        [p for p in BRIEFS.glob("*.md") if p.name != "latest.md"],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return files[0].stem if files else None


def _artifact_paths(session_id: str | None) -> dict[str, str | None]:
    """Locate residual / pdf / leaf paths for a session."""
    out: dict[str, str | None] = {
        "residual_json": None,
        "session_md": None,
        "session_pdf": None,
        "brief_md": None,
        "verkle_hint": None,
    }
    if not session_id:
        return out
    try:
        from mag.registry import find_derived, find_residual

        r = find_residual(session_id)
        if r:
            out["residual_json"] = str(r)
        md = find_derived(session_id, "md")
        if md:
            out["session_md"] = str(md)
        pdf = find_derived(session_id, "pdf")
        if pdf:
            out["session_pdf"] = str(pdf)
    except Exception:
        pass
    brief = BRIEFS / f"{session_id}.md"
    if brief.is_file():
        out["brief_md"] = str(brief)
    elif (BRIEFS / "latest.md").is_file():
        out["brief_md"] = str(BRIEFS / "latest.md")
    # Verkle: chain tip file if present
    for cand in (
        ROOT / "memory" / "biography" / "verkle_tip.json",
        ROOT / "memory" / "biography" / "chain_tip.json",
        ROOT / "logs" / "verkle_tip.json",
    ):
        if cand.is_file():
            out["verkle_hint"] = str(cand)
            break
    return out


def ingest_bonds(*, session_id: str | None = None, write: bool = True) -> dict[str, Any]:
    """
    Build active bonds pack from brief + working + field + residual metadata.
    Writes memory/bonds_active.md and .json when write=True.
    """
    sid = session_id or _latest_session_id()
    brief_path = BRIEFS / "latest.md"
    if sid and (BRIEFS / f"{sid}.md").is_file():
        brief_path = BRIEFS / f"{sid}.md"
    brief_md = _clip(brief_path, 8000)
    working_md = _clip(WORKING, 3000)
    field_md = _clip(FIELD, 2500)

    open_loops = _section(brief_md, "Open loops")
    residual_bonds = _section(brief_md, "Residual bonds")
    next_moves = _section(brief_md, "Next moves")
    # working.md Open
    working_open = _section(working_md, "Open")
    if not working_open:
        for ln in working_md.splitlines():
            if ln.strip().startswith("- ") and "Open" not in ln:
                # crude: lines under ## Open already handled
                pass
        # fallback scrape
        in_open = False
        for ln in working_md.splitlines():
            if ln.strip().startswith("## Open"):
                in_open = True
                continue
            if in_open and ln.strip().startswith("## "):
                break
            if in_open and ln.strip().startswith("- "):
                working_open.append(ln.strip()[2:].strip())

    # field brief top tickets
    field_tickets = []
    for ln in field_md.splitlines():
        if "`c-" in ln and ("practice" in ln.lower() or "runtime" in ln.lower() or "**`" in ln):
            field_tickets.append(ln.strip()[:200])
        m = re.search(r"`(c-[a-f0-9]+)`", ln)
        if m and ln.strip().startswith(("1.", "2.", "3.", "4.", "5.", "-")):
            field_tickets.append(ln.strip()[:200])
    field_tickets = field_tickets[:5]

    # residual dossier extras
    residual_meta: dict[str, Any] = {}
    if sid:
        try:
            from mag.registry import load_residual

            d = load_residual(sid)
            if d:
                chord = d.get("chord") or {}
                lay = d.get("steiniger_laymen") or {}
                residual_meta = {
                    "tldr": (d.get("tldr") or "")[:400],
                    "commitment": chord.get("commitment_hash"),
                    "title": ((d.get("time") or {}).get("title") or "")[:200],
                }
                for L in (chord.get("loops_audited") or [])[:6]:
                    if isinstance(L, dict):
                        plain = L.get("plain") or L.get("id")
                        if plain and plain not in open_loops:
                            open_loops.append(str(plain)[:200])
                for r in (lay.get("residual_bonds") or [])[:8]:
                    if r and str(r) not in residual_bonds:
                        residual_bonds.append(str(r)[:200])
        except Exception as e:
            residual_meta["load_error"] = str(e)

    artifacts = _artifact_paths(sid)

    # Closed runs — lattice child edges (not tip leaves). See docs/ref/run_trail_lattice.md
    related_runs: list[dict[str, Any]] = []
    try:
        from mag.run_trail import list_related_runs

        related_runs = list_related_runs(last_n=6)
    except Exception:
        related_runs = []

    # promoted practices (last triage block lines)
    practices: list[str] = []
    if PLAYBOOK.is_file():
        pb = PLAYBOOK.read_text(encoding="utf-8", errors="replace")
        for ln in pb.splitlines():
            if ln.strip().startswith("- **c-") and "practice" in ln.lower() or (
                ln.strip().startswith("- **c-") and ":" in ln
            ):
                practices.append(ln.strip()[:240])
        practices = practices[-6:]

    def _uniq(items: list[str], n: int) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for x in items:
            k = re.sub(r"\s+", " ", x.lower())[:120]
            if k in seen:
                continue
            seen.add(k)
            out.append(x)
            if len(out) >= n:
                break
        return out

    # conflict-scan pass (SubtleMemory steal): flag same-subject opposite-polarity bonds
    bond_conflicts: list[dict[str, Any]] = []
    seen_pairs: set[tuple[str, str]] = set()
    for i, b1 in enumerate(residual_bonds):
        for b2 in residual_bonds[i + 1:]:
            hits = scan_conflicts(b1, [b2])
            if hits:
                pair = tuple(sorted(hits[0]["subjects"]))
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                bond_conflicts.append(hits[0])
    bond_conflicts = bond_conflicts[:8]

    pack: dict[str, Any] = {
        "schema": "mag_bonds_active.v1",
        "ts": _utc(),
        "session_id": sid,
        "doctrine": (
            "Residual bonds are first-class next-session inputs. "
            "Re-read before new epics. Not todo theater. "
            "related_runs = closed goal trails under the day bead (not verkle tip)."
        ),
        "open_loops": _uniq(open_loops, 12),
        "residual_bonds": _uniq(residual_bonds, 12),
        "next_moves": _uniq(next_moves, 10),
        "working_open": _uniq(working_open, 10),
        "field_tickets": _uniq(field_tickets, 5),
        "related_runs": related_runs,
        "promoted_practices_tail": practices,
        "bond_conflicts": bond_conflicts,

        "artifacts": artifacts,
        "residual_meta": residual_meta,
        "sources": {
            "brief": str(brief_path) if brief_path.is_file() else None,
            "working": str(WORKING) if WORKING.is_file() else None,
            "field_brief": str(FIELD) if FIELD.is_file() else None,
            "related_runs": str(ROOT / "memory" / "runs" / "related_runs.jsonl"),
        },
    }

    md = _format_md(pack)
    if write:
        BONDS_MD.parent.mkdir(parents=True, exist_ok=True)
        BONDS_MD.write_text(md, encoding="utf-8")
        BONDS_JSON.write_text(json.dumps(pack, indent=2, default=str), encoding="utf-8")

    return {
        "ok": True,
        "session_id": sid,
        "path_md": str(BONDS_MD),
        "path_json": str(BONDS_JSON),
        "n_loops": len(pack["open_loops"]),
        "n_bonds": len(pack["residual_bonds"]),
        "n_moves": len(pack["next_moves"]),
        "n_conflicts": len(pack.get("bond_conflicts") or []),
        "artifacts": artifacts,
        "chars_md": len(md),
    }


def _format_md(pack: dict[str, Any]) -> str:
    art = pack.get("artifacts") or {}
    lines = [
        f"# Active residual bonds",
        "",
        f"_Ingested `{pack.get('ts')}` · session `{pack.get('session_id') or '?'}`_",
        "",
        pack.get("doctrine") or "",
        "",
        "## Open loops (carry forward)",
        "",
    ]
    for x in pack.get("open_loops") or []:
        lines.append(f"- {x}")
    if not pack.get("open_loops"):
        lines.append("- _(none extracted)_")
    lines.extend(["", "## Residual bonds (identity / architecture)", ""])
    for x in pack.get("residual_bonds") or []:
        lines.append(f"- {x}")
    if not pack.get("residual_bonds"):
        lines.append("- _(none extracted)_")
    lines.extend(["", "## Next moves (local first)", ""])
    for x in pack.get("next_moves") or []:
        lines.append(f"- {x}")
    if not pack.get("next_moves"):
        lines.append("- Re-read this file before inventing new epics.")
    lines.extend(["", "## Working.md still open", ""])
    for x in pack.get("working_open") or []:
        lines.append(f"- {x}")
    if not pack.get("working_open"):
        lines.append("- _(none)_")
    lines.extend(["", "## Field brief tickets", ""])
    for x in pack.get("field_tickets") or []:
        lines.append(f"- {x}")
    if not pack.get("field_tickets"):
        lines.append("- _(none)_")
    lines.extend(["", "## Artifacts (re-read these)", ""])
    for k, v in art.items():
        lines.append(f"- **{k}:** `{v or '—'}`")
    meta = pack.get("residual_meta") or {}
    if meta.get("tldr") or meta.get("commitment"):
        lines.extend(
            [
                "",
                "## Residual meta",
                "",
                f"- **title:** {meta.get('title') or '—'}",
                f"- **commitment:** `{meta.get('commitment') or '—'}`",
                f"- **tldr:** {meta.get('tldr') or '—'}",
            ]
        )
    lines.extend(
        [
            "",
            "## Related runs (closed goals — child of day bead, not tip)",
            "",
        ]
    )
    rruns = pack.get("related_runs") or []
    if not rruns:
        lines.append("- _(none — `python main.py trail start/close` when you need mid-run continuity)_")
    for r in rruns:
        if not isinstance(r, dict):
            continue
        lines.append(
            f"- **{r.get('run_id')}** seat=`{r.get('seat')}` · "
            f"{(r.get('goal') or '')[:80]} · "
            f"commit=`{(r.get('run_commit') or '')[:12]}` · "
            f"`{r.get('path') or '—'}`"
        )
    if pack.get("bond_conflicts"):
        lines.extend(["", "## Bond conflicts (scan)", ""])
        for c in pack["bond_conflicts"]:
            lines.append(f"- `{c['candidate'][:80]}`  ~~ conflicts with  ~~  `{c['existing'][:80]}`")
    lines.extend(
        [
            "",
            "## Use",
            "",
            "- Auto-attached to `python main.py context-pack`",
            "- Refresh: `python main.py bonds`",
            "- Trail: `python main.py trail start|append|close`",
            "- Grok: read this + pack only under `[priority]`",
            "",
        ]
    )
    return "\n".join(lines)


def load_bonds_text(max_chars: int = 1800) -> str:
    if not BONDS_MD.is_file():
        return ""
    return BONDS_MD.read_text(encoding="utf-8", errors="replace")[:max_chars]


def load_bonds_json() -> dict[str, Any] | None:
    if not BONDS_JSON.is_file():
        return None
    try:
        return json.loads(BONDS_JSON.read_text(encoding="utf-8"))
    except Exception:
        return None
