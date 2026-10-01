"""Resonance — corpus lens (v3-008 research).

Crosswalk soil sources and surface top echo cards into context-pack L0e.
Notice-only: no promote gate. T0/T1 never exported.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT

FINDINGS_PATH = ROOT / "memory" / "resonance" / "findings.jsonl"
INDEX_META = ROOT / "memory" / "resonance" / "index_meta.json"

_SOURCE_DIRS = (
    ROOT / "memory" / "remedies",
    ROOT / "memory" / "improve",
    ROOT / "queue",
)
_FORBIDDEN_PREFIXES = ("memory/briefs/", "data/raw/", "secrets/")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]{3,}", (text or "").lower())}


def _safe_path(path: Path) -> str:
    try:
        rel = path.relative_to(ROOT).as_posix()
    except ValueError:
        return ""
    if any(rel.startswith(p) for p in _FORBIDDEN_PREFIXES):
        return ""
    return rel


def _collect_sources(*, limit_per_kind: int = 40) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for p in sorted((ROOT / "memory" / "remedies").glob("*.md"))[:limit_per_kind]:
        body = p.read_text(encoding="utf-8", errors="replace")[:2000]
        rows.append({
            "kind": "remedy",
            "path": _safe_path(p),
            "title": p.stem.replace("-", " "),
            "excerpt": body[:280],
            "tokens": _tokens(body),
        })

    cand = ROOT / "memory" / "improve" / "candidates.jsonl"
    if cand.is_file():
        for line in cand.read_text(encoding="utf-8", errors="replace").splitlines()[:limit_per_kind]:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            body = f"{row.get('title', '')} {row.get('summary', '')} {row.get('rationale', '')}"
            rows.append({
                "kind": "improve_candidate",
                "path": "memory/improve/candidates.jsonl",
                "title": str(row.get("title") or row.get("id") or "candidate")[:80],
                "excerpt": body[:280],
                "tokens": _tokens(body),
            })

    todo = ROOT / "queue" / "todo.md"
    if todo.is_file():
        for ln in todo.read_text(encoding="utf-8", errors="replace").splitlines():
            if ln.strip().startswith("- [ ]"):
                rows.append({
                    "kind": "todo_open",
                    "path": "queue/todo.md",
                    "title": ln.strip()[:80],
                    "excerpt": ln.strip(),
                    "tokens": _tokens(ln),
                })

    decisions = ROOT / "memory" / "decisions_log.jsonl"
    if decisions.is_file():
        for line in decisions.read_text(encoding="utf-8", errors="replace").splitlines()[-limit_per_kind:]:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            body = f"{row.get('context', '')} {row.get('steer_input', '')} {row.get('outcome', '')}"
            rows.append({
                "kind": "decision",
                "path": "memory/decisions_log.jsonl",
                "title": str(row.get("context") or "steer case")[:80],
                "excerpt": body[:280],
                "tokens": _tokens(body),
            })

    try:
        from mag.failure_kb import recurring_patterns

        for pat in (recurring_patterns(limit=8) or [])[:8]:
            sig = str(pat.get("signature") or pat.get("key") or "")
            rows.append({
                "kind": "fkb_pattern",
                "path": "memory/failure_kb/signatures.json",
                "title": sig[:80],
                "excerpt": str(pat.get("last_error") or pat.get("detail") or sig)[:280],
                "tokens": _tokens(sig + str(pat.get("last_error") or "")),
            })
    except Exception:
        pass

    return [r for r in rows if r.get("path")]


def score_echoes(goal: str, *, limit: int = 12) -> list[dict[str, Any]]:
    goal_tokens = _tokens(goal)
    if not goal_tokens:
        goal_tokens = _tokens("mag autorun improve")
    scored: list[tuple[float, dict[str, Any]]] = []
    for src in _collect_sources():
        overlap = len(goal_tokens & src.get("tokens", set()))
        if overlap == 0 and src.get("kind") != "fkb_pattern":
            continue
        bonus = {"remedy": 0.5, "fkb_pattern": 0.8, "decision": 0.3}.get(src.get("kind", ""), 0.0)
        score = overlap + bonus
        if score > 0:
            scored.append((score, {**src, "score": round(score, 2)}))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [row for _, row in scored[:limit]]


def top_cards(goal: str = "", *, n: int = 3) -> list[dict[str, Any]]:
    echoes = score_echoes(goal, limit=n)
    cards = []
    for e in echoes:
        cards.append({
            "kind": e.get("kind"),
            "title": e.get("title"),
            "excerpt": (e.get("excerpt") or "")[:200],
            "path": e.get("path"),
            "score": e.get("score"),
        })
    return cards


def tick(goal: str = "", *, dry: bool = False) -> dict[str, Any]:
    cards = top_cards(goal, n=5)
    finding = {
        "schema": "resonance_finding.v1",
        "ts": _now(),
        "goal": (goal or "")[:200],
        "cards": cards,
        "dry": dry,
    }
    if dry:
        return {"ok": True, "finding": finding, "written": False}
    FINDINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with FINDINGS_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(finding, ensure_ascii=False) + "\n")
    INDEX_META.parent.mkdir(parents=True, exist_ok=True)
    INDEX_META.write_text(
        json.dumps({"schema": "resonance_index_meta.v1", "last_tick": _now(), "n_cards": len(cards)}, indent=2)
        + "\n",
        encoding="utf-8",
    )
    return {"ok": True, "finding": finding, "written": True, "path": str(FINDINGS_PATH)}


def format_l0e(cards: list[dict[str, Any]] | None = None, *, goal: str = "") -> str:
    c = cards if cards is not None else top_cards(goal, n=3)
    if not c:
        return ""
    lines = ["### L0e Resonance (soil echoes — notice only, no promote)"]
    for card in c:
        lines.append(
            f"- [{card.get('kind')}] {card.get('title')} (score={card.get('score')}) "
            f"→ {card.get('path')}"
        )
        ex = (card.get("excerpt") or "").strip().replace("\n", " ")
        if ex:
            lines.append(f"  {ex[:160]}{'…' if len(ex) > 160 else ''}")
    return "\n".join(lines)
