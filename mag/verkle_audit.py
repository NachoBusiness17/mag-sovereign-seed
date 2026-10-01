"""Verkle history audit + ticket reconciliation + optional local synthesis.

Law: session DNA lives in memory/biography/ — this module reads and reports;
instrument lattice (memory/improve/blast/lattice/) is separate.

CLI: python main.py verkle-audit [--full] [--synth] [--reconcile] [--dry] [--fix]
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT

BIO = ROOT / "memory" / "biography"
TIP = BIO / "verkle_tip.json"
CHAIN = BIO / "verkle_chain.jsonl"
KNOTS = BIO / "knots"
RESIDUAL = BIO / "residual"
LATTICE_NODES = ROOT / "memory" / "lattice" / "nodes.jsonl"
DAILY = ROOT / "memory" / "improve" / "daily"
ROADMAP_LEAVES_TARGET = 20

# Roadmap tickets (sync with mag/operator_os.NEXT_TICKETS + ORG_ROADMAP)
ROADMAP_TICKETS: list[dict[str, Any]] = [
    {"id": "A1", "title": "org-review / Operate tab", "status": "done", "source": "roadmap"},
    {"id": "A2", "title": "Hard private → remote refuse", "status": "partial", "source": "roadmap", "note": "router PR #8; needs tier refuse test"},
    {"id": "A3", "title": "Seat matrix in dispatch", "status": "partial", "source": "roadmap", "note": "route.v2 in PR #8"},
    {"id": "A4", "title": "Context-pack freshness", "status": "partial", "source": "roadmap", "note": "autorun_common in PR #10"},
    {"id": "B1", "title": "Inter-day graph (memory palace 0.95)", "status": "partial", "source": "roadmap", "note": "lattice-backfill seeds store; graph UI partial"},
    {"id": "B2", "title": "Evolution API + UI", "status": "partial", "source": "roadmap"},
    {"id": "O3", "title": "n_leaves ≥ 20", "status": "open", "source": "roadmap", "metric": "n_leaves"},
    {"id": "2.0", "title": "verify-leaf over residual_hash", "status": "open", "source": "roadmap"},
    {"id": "PR8", "title": "Unified router", "status": "open", "source": "pr", "note": "cursor/unified-router-e2ce"},
    {"id": "PR9", "title": "Failure KB", "status": "open", "source": "pr", "note": "cursor/failure-kb-e2ce"},
    {"id": "PR10", "title": "Mag Autorun v1", "status": "open", "source": "pr", "note": "cursor/mag-autorun-v1-e2ce"},
    {"id": "PR11", "title": "Mag v2 plan", "status": "open", "source": "pr", "note": "cursor/mag-v2-plan-e2ce"},
    {"id": "V36", "title": "verkle-audit CLI", "status": "done", "source": "v2"},
    {"id": "LL1", "title": "lattice-loop external scaffold", "status": "abandoned", "source": "abandoned", "note": "needs sovereign-mirror-scaffold on host"},
]

ABANDONED_PATTERNS = (
    "lattice-loop",
    "sovereign-mirror-scaffold",
    "lattice-loop --backfill",
)


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _day() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        o = json.loads(path.read_text(encoding="utf-8"))
        return o if isinstance(o, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            o = json.loads(line)
            if isinstance(o, dict):
                rows.append(o)
        except json.JSONDecodeError:
            continue
    return rows


def _todo_open() -> list[str]:
    p = ROOT / "queue" / "todo.md"
    if not p.is_file():
        return []
    return [
        ln.strip()
        for ln in p.read_text(encoding="utf-8", errors="replace").splitlines()
        if ln.strip().startswith("- [ ]")
    ]


def _improve_candidates(*, statuses: set[str] | None = None) -> list[dict[str, Any]]:
    path = ROOT / "memory" / "improve" / "candidates.jsonl"
    if not path.is_file():
        return []
    want = statuses or {"new", "hold", "failed"}
    out: list[dict[str, Any]] = []
    for row in _read_jsonl(path):
        st = str(row.get("status") or "new").lower()
        if st in want:
            out.append(row)
    return out


def verkle_gaps(*, deep: bool = False) -> list[dict[str, Any]]:
    """Actionable gaps from session DNA + lattice store.

    The default is a control-plane scan: it only reads bounded metadata and
    never opens every knot JSON.  Reading the full knot corpus is useful for a
    deliberate forensic audit, but it must not happen implicitly from health
    enforcement, queue admission, or a status page.  Callers that explicitly
    request a full audit pass ``deep=True``.
    """
    gaps: list[dict[str, Any]] = []
    tip = _read_json(TIP)
    n_leaves = int(tip.get("n_leaves") or 0)
    chain = _read_jsonl(CHAIN)
    knot_files = sorted(KNOTS.glob("*.knot.json")) if KNOTS.is_dir() else []

    if n_leaves < ROADMAP_LEAVES_TARGET:
        gaps.append(
            {
                "kind": "roadmap_metric",
                "id": "O3",
                "severity": "info",
                "detail": f"n_leaves {n_leaves}/{ROADMAP_LEAVES_TARGET} — use-time, not code",
            }
        )

    if len(chain) != len(knot_files):
        gaps.append(
            {
                "kind": "integrity",
                "severity": "warn",
                "detail": f"chain rows ({len(chain)}) != knot files ({len(knot_files)})",
                "action": "python main.py backfill-sessions --all",
            }
        )

    if not LATTICE_NODES.is_file():
        gaps.append(
            {
                "kind": "lattice_store",
                "severity": "warn",
                "detail": "memory/lattice/nodes.jsonl missing",
                "action": "python main.py lattice-backfill",
            }
        )

    if deep:
        null_theme = 0
        knot_session_ids: set[str] = set()
        for kf in knot_files:
            k = _read_json(kf)
            if k.get("session_id"):
                knot_session_ids.add(str(k["session_id"]))
            if not k.get("dominant_theme"):
                null_theme += 1
        if null_theme:
            gaps.append(
                {
                    "kind": "theme_signal",
                    "severity": "info",
                    "detail": f"{null_theme}/{len(knot_files)} knots lack dominant_theme",
                    "action": "python main.py verkle-audit --synth",
                }
            )

        residual_files = sorted(RESIDUAL.glob("*.json")) if RESIDUAL.is_dir() else []
        for rf in residual_files:
            sid = rf.stem
            # Knot filenames intentionally truncate session ids for Windows-safe
            # paths, so compare against the session_id stored in each knot. The
            # previous substring scan was O(residuals * knots) and made a normal
            # audit quadratic on the live corpus.
            if sid not in knot_session_ids:
                gaps.append(
                    {
                        "kind": "orphan_residual",
                        "severity": "warn",
                        "detail": f"residual without knot: {rf.name}",
                        "action": f"summarize-session for {sid}",
                    }
                )

    return gaps


def reconcile_tickets() -> dict[str, Any]:
    """Merge roadmap, operator_os, improve candidates, queue/todo."""
    try:
        from mag.operator_os import NEXT_TICKETS

        operator = list(NEXT_TICKETS)
    except Exception:
        operator = []

    by_id: dict[str, dict[str, Any]] = {}
    for t in ROADMAP_TICKETS:
        by_id[t["id"]] = dict(t)
    for t in operator:
        oid = str(t.get("id") or "")
        if oid in by_id:
            by_id[oid]["operator_status"] = t.get("status")
        else:
            by_id[oid] = {**t, "source": "operator_os"}

    improve = _improve_candidates()
    todo = _todo_open()
    gaps = verkle_gaps()

    open_roadmap = [t for t in by_id.values() if t.get("status") in ("open", "partial", "next", "queued")]
    abandoned = [t for t in by_id.values() if t.get("status") == "abandoned"]
    done = [t for t in by_id.values() if t.get("status") == "done"]

    return {
        "ok": True,
        "schema": "tickets_reconcile.v1",
        "ts": _utc(),
        "open": open_roadmap,
        "done": done,
        "abandoned": abandoned,
        "improve_hold_new": [
            {
                "id": c.get("id"),
                "kind": c.get("kind"),
                "status": c.get("status"),
                "claim": (c.get("claim") or "")[:120],
            }
            for c in improve[:25]
        ],
        "queue_todo_open": todo[:20],
        "verkle_gaps": gaps,
        "counts": {
            "open": len(open_roadmap),
            "done": len(done),
            "abandoned": len(abandoned),
            "improve": len(improve),
            "todo": len(todo),
            "verkle_gaps": len(gaps),
        },
    }


def _synth_one_residual(path: Path, *, role: str = "clerk", dry: bool = False) -> dict[str, Any]:
    """Local L0 pass: themes, loops, open threads from one residual JSON."""
    sid = path.stem
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return {"ok": False, "session_id": sid, "error": str(e)}

    # Clip for clerk context
    blob = text[:12000]
    system = (
        "You are Mag clerk. Extract from this session residual JSON only — no invention. "
        "Output markdown: ## Themes, ## Loops, ## Open threads, ## Suggested next move (one line)."
    )
    user = f"Session `{sid}` residual excerpt:\n\n```json\n{blob}\n```"

    if dry:
        return {"ok": True, "session_id": sid, "dry": True, "chars": len(blob)}

    try:
        from llm import chat as llm_chat

        answer = llm_chat(role, system, user, temperature=0.1)
    except Exception as e:
        return {"ok": False, "session_id": sid, "error": str(e), "seat": "local"}

    return {"ok": True, "session_id": sid, "answer": answer, "chars": len(answer or "")}


def synth_all_residuals(*, dry: bool = False, max_sessions: int = 12) -> dict[str, Any]:
    """Per-session local synthesis → daily verkle leaf."""
    files = sorted(RESIDUAL.glob("*.json")) if RESIDUAL.is_dir() else []
    files = files[-max_sessions:]
    digs: list[dict[str, Any]] = []
    sections: list[str] = [f"# Verkle synthesis — {_day()}", "", f"Generated: {_utc()}", ""]

    for rf in files:
        dig = _synth_one_residual(rf, dry=dry)
        digs.append(dig)
        if dig.get("ok") and dig.get("answer"):
            sections.extend([f"## {dig['session_id']}", "", dig["answer"], ""])

    out_path = DAILY / f"{_day()}-verkle.md"
    report = {
        "ok": True,
        "schema": "verkle_synth.v1",
        "n_sessions": len(files),
        "n_ok": sum(1 for d in digs if d.get("ok")),
        "digs": digs,
        "dry": dry,
    }

    if not dry and sections:
        DAILY.mkdir(parents=True, exist_ok=True)
        out_path.write_text("\n".join(sections) + "\n", encoding="utf-8")
        report["leaf_path"] = str(out_path.relative_to(ROOT)).replace("\\", "/")

    return report


def run_audit(
    *,
    full: bool = False,
    synth: bool = False,
    reconcile: bool = True,
    backfill_lattice: bool = False,
    dry: bool = False,
    fix: bool = False,
) -> dict[str, Any]:
    """Full deterministic audit; optional synth + lattice backfill."""
    from mag.verkle_knot import evolution_summary

    tip = _read_json(TIP)
    evo = evolution_summary()
    gaps = verkle_gaps(deep=full)

    lattice_summary: dict[str, Any] = {}
    try:
        from mag.lattice_query import summary as lattice_summary_fn

        lattice_summary = lattice_summary_fn()
    except Exception as e:
        lattice_summary = {"ok": False, "error": str(e)}

    backfill_result: dict[str, Any] | None = None
    if backfill_lattice and not dry:
        from mag.lattice_backfill import run_backfill

        backfill_result = run_backfill(dry_run=False)
        try:
            from mag.lattice_query import summary as lattice_summary_fn

            lattice_summary = lattice_summary_fn()
        except Exception:
            pass

    fix_out: dict[str, Any] | None = None
    if fix:
        # The sanctioned auto-heal: repair ONLY a stale tip bookmark after
        # proving the chain rows are internally consistent. Never rewrites,
        # reorders, or drops chain rows (see verkle_knot.repair_tip_if_consistent).
        try:
            from mag.verkle_knot import repair_tip_if_consistent

            fix_out = repair_tip_if_consistent()
        except Exception as e:
            fix_out = {"ok": False, "repaired": False, "error": str(e)}

    reconcile_out: dict[str, Any] | None = None
    if reconcile:
        reconcile_out = reconcile_tickets()

    synth_out: dict[str, Any] | None = None
    if synth:
        synth_out = synth_all_residuals(dry=dry)
    elif full and not dry:
        synth_out = synth_all_residuals(dry=False)

    # Improve-ready goals from gaps
    autorun_goals: list[str] = []
    for g in gaps:
        act = g.get("action")
        if act and g.get("severity") in ("warn", "error"):
            autorun_goals.append(f"[verkle] {g.get('detail', '')[:200]} — {act}")

    out: dict[str, Any] = {
        "ok": True,
        "schema": "verkle_audit.v1",
        "ts": _utc(),
        "tip": tip,
        "evolution": evo,
        "lattice": lattice_summary,
        "gaps": gaps,
        "autorun_goals": autorun_goals,
        "reconcile": reconcile_out,
        "backfill": backfill_result,
        "fix": fix_out,
        "synth": synth_out,
        "full": full,
        "dry": dry,
    }

    if not dry:
        report_path = DAILY / f"{_day()}-verkle-audit.json"
        DAILY.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        try:
            out["report_path"] = str(report_path.relative_to(ROOT)).replace("\\", "/")
        except ValueError:
            out["report_path"] = str(report_path)

    return out


def _cli(argv: list[str] | None) -> int:
    import argparse

    p = argparse.ArgumentParser(prog="verkle-audit")
    p.add_argument("--full", action="store_true", help="Audit + lattice backfill + synth")
    p.add_argument("--synth", action="store_true", help="Local clerk pass per residual session")
    p.add_argument("--reconcile", action="store_true", default=True, help="Include ticket reconciliation")
    p.add_argument("--no-reconcile", action="store_true", help="Skip ticket reconciliation")
    p.add_argument("--backfill", action="store_true", help="Run lattice-backfill before audit")
    p.add_argument(
        "--fix",
        action="store_true",
        help="Auto-heal: repair a stale tip bookmark via repair_tip_if_consistent() "
        "(chain rows are never rewritten; refuses if rows fail integrity)",
    )
    p.add_argument("--dry", action="store_true", help="Plan only; no writes or LLM")
    args = p.parse_args(argv)

    res = run_audit(
        full=args.full,
        synth=args.synth,
        reconcile=not args.no_reconcile,
        backfill_lattice=args.backfill or args.full,
        dry=args.dry,
        fix=args.fix,
    )
    print(json.dumps(res, indent=2, ensure_ascii=False, default=str))
    ok = bool(res.get("ok")) and not (
        args.fix and res.get("fix") and not res["fix"].get("ok")
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(_cli(None))
