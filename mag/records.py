"""Records office — pack completeness, backfill, KPI for residual constitution.

Mag 0.91: every closed day should be a full institutional record.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT
from mag.biography import pack_status, summarize_session

BIO = ROOT / "memory" / "biography"
KPI_PATH = BIO / "kpi.json"
KPI_LOG = ROOT / "logs" / "kpi.jsonl"


def _grok_sessions_dir() -> Path:
    """Lazy ~/.grok resolution (Path.home() can raise in sandbox/service contexts)."""
    try:
        return Path.home() / ".grok" / "sessions"
    except (RuntimeError, OSError):
        return ROOT.parent / ".grok" / "sessions"


GROK_SESSIONS = _grok_sessions_dir()
SKIP_STEMS = {
    "latest",
    "index",
    "kpi",
    "topic_evolution",
    "verkle_tip",
    "verkle_chain",
    "knot_timeline",
    "README",
}


def _is_session_id(stem: str) -> bool:
    if not stem or stem in SKIP_STEMS:
        return False
    if stem.startswith("latest") or stem.startswith("verkle"):
        return False
    # grok-style ids often uuid-like
    if len(stem) < 8:
        return False
    return True


def list_known_session_ids() -> list[str]:
    """Union of biography artifacts + Grok session dirs on disk."""
    found: set[str] = set()
    if BIO.is_dir():
        for pat, strip in (
            ("*.md", ".md"),
            ("*.dossier.json", ".dossier.json"),
            ("*.visual_pack.json", ".visual_pack.json"),
            ("*.pdf", ".pdf"),
        ):
            for p in BIO.glob(pat):
                stem = p.name
                if strip == ".md":
                    stem = p.stem
                else:
                    stem = p.name[: -len(strip)] if p.name.endswith(strip) else p.stem
                if _is_session_id(stem):
                    found.add(stem)

    if GROK_SESSIONS.is_dir():
        for group in GROK_SESSIONS.iterdir():
            if not group.is_dir():
                continue
            for sid_dir in group.iterdir():
                if not sid_dir.is_dir():
                    continue
                chat = sid_dir / "chat_history.jsonl"
                if chat.is_file() and _is_session_id(sid_dir.name):
                    found.add(sid_dir.name)

    return sorted(found)


def pack_report(session_id: str | None = None) -> dict[str, Any]:
    """One sid or all known sessions (lean complete rules)."""
    if session_id and session_id not in ("", "all", "*"):
        st = pack_status(session_id)
        return {"ok": True, "mode": "one", "session": st, "complete": st.get("complete")}

    # Prefer registry ids + residual scan
    sids = set(list_known_session_ids())
    registry_map: dict[str, dict[str, Any]] = {}
    try:
        from mag.registry import RESIDUAL_DIR, _load_registry_map, list_registry

        # One registry read per report. Calling pack_status() for every session
        # used to reload this whole ledger for each row (O(n²) self-audit).
        registry_map = _load_registry_map()

        for r in list_registry(limit=500):
            if r.get("session_id"):
                sids.add(str(r["session_id"]))
        if RESIDUAL_DIR.is_dir():
            for p in RESIDUAL_DIR.glob("*.json"):
                sids.add(p.stem)
    except Exception:
        pass

    rows = [pack_status(sid, registry_map=registry_map) for sid in sorted(sids)]
    complete = [r for r in rows if r.get("complete")]
    incomplete = [r for r in rows if not r.get("complete")]
    n_leaves = 0
    tip_path = BIO / "verkle_tip.json"
    if tip_path.is_file():
        try:
            n_leaves = int(json.loads(tip_path.read_text(encoding="utf-8")).get("n_leaves") or 0)
        except (json.JSONDecodeError, OSError, TypeError, ValueError):
            n_leaves = 0
    return {
        "ok": True,
        "mode": "all",
        "schema": "lean_pack_report.v1",
        "n_sessions": len(rows),
        "n_complete": len(complete),
        "n_incomplete": len(incomplete),
        "complete_pct": round(100.0 * len(complete) / max(len(rows), 1), 1),
        "n_leaves": n_leaves,
        "complete_means": "residual + card + content_commit + chain_leaf (pdf/visual optional)",
        "incomplete": [
            {"session_id": r.get("session_id"), "missing": r.get("missing")}
            for r in incomplete
        ],
        "sessions": rows,
    }


def write_kpi(*, source: str = "manual") -> dict[str, Any]:
    """Memory health KPI — org metric without poetry."""
    rep = pack_report()
    tip: dict[str, Any] = {}
    if (BIO / "verkle_tip.json").is_file():
        try:
            tip = json.loads((BIO / "verkle_tip.json").read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            tip = {}
    kpi = {
        "schema": "mag_records_kpi.v1",
        "ts": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "n_sessions": rep.get("n_sessions"),
        "n_complete": rep.get("n_complete"),
        "n_incomplete": rep.get("n_incomplete"),
        "complete_pct": rep.get("complete_pct"),
        "n_leaves": tip.get("n_leaves") or rep.get("n_leaves") or 0,
        "tip_root": (tip.get("root") or "")[:16] or None,
        "incomplete_ids": [
            x.get("session_id") for x in (rep.get("incomplete") or []) if x.get("session_id")
        ],
        "note": "Lean complete = residual+card+commit+leaf; pdf/visual derived",
        "complete_means": "residual + card + content_commit + chain_leaf",
    }
    BIO.mkdir(parents=True, exist_ok=True)
    KPI_PATH.write_text(json.dumps(kpi, indent=2), encoding="utf-8")
    KPI_LOG.parent.mkdir(parents=True, exist_ok=True)
    with KPI_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(kpi, default=str) + "\n")
    return kpi


def backfill_sessions(
    *,
    use_llm: bool = False,
    dry_run: bool = False,
    only_incomplete: bool = True,
) -> dict[str, Any]:
    """Fill missing dossier/pdf/visual/leaf for known sessions."""
    rep = pack_report()
    targets: list[str]
    if only_incomplete:
        targets = [
            x["session_id"]
            for x in (rep.get("incomplete") or [])
            if x.get("session_id")
        ]
    else:
        targets = list_known_session_ids()

    results: list[dict[str, Any]] = []
    for sid in targets:
        before = pack_status(sid)
        if dry_run:
            results.append(
                {
                    "session_id": sid,
                    "dry_run": True,
                    "missing": before.get("missing"),
                }
            )
            continue
        try:
            out = summarize_session(
                sid,
                use_llm=use_llm,
                force=True,
                pdf=True,
                amend=True,
            )
            after = pack_status(sid)
            results.append(
                {
                    "session_id": sid,
                    "ok": bool(after.get("complete") or out.get("ok")),
                    "complete": after.get("complete"),
                    "missing_before": before.get("missing"),
                    "missing_after": after.get("missing"),
                    "mode": out.get("mode"),
                }
            )
        except Exception as e:
            results.append({"session_id": sid, "ok": False, "error": str(e)[:300]})

    kpi = write_kpi(source="backfill")
    filled = sum(1 for r in results if r.get("complete"))
    return {
        "ok": all(r.get("ok", r.get("dry_run")) for r in results) if results else True,
        "n_targets": len(targets),
        "n_complete_after": filled if not dry_run else None,
        "results": results,
        "kpi": kpi,
    }


def format_pack_report_text(rep: dict[str, Any] | None = None) -> str:
    r = rep or pack_report()
    if r.get("mode") == "one":
        s = r.get("session") or {}
        return (
            f"session {s.get('session_id')}\n"
            f"complete={s.get('complete')} missing={s.get('missing')}\n"
            f"residual={s.get('has_residual')} card={s.get('has_card')} "
            f"commit={s.get('has_commit')} leaf={s.get('has_leaf')}\n"
            f"derived(optional): md={s.get('has_md')} pdf={s.get('has_pdf')} "
            f"visual={s.get('has_visual')}"
        )
    lines = [
        "# Records office (lean residual + registry)",
        f"sessions={r.get('n_sessions')} complete={r.get('n_complete')} "
        f"incomplete={r.get('n_incomplete')} ({r.get('complete_pct')}%)",
        f"n_leaves={r.get('n_leaves')}",
        "complete = residual + card + content_commit + chain_leaf",
        "(pdf / visual / md = derived, optional)",
    ]
    inc = r.get("incomplete") or []
    if inc:
        lines.append("holes:")
        for x in inc:
            lines.append(f"  - {x.get('session_id')}: missing {x.get('missing')}")
    else:
        lines.append("holes: none")
    return "\n".join(lines)
