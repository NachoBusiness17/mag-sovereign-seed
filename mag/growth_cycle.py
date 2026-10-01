"""Explicit three-body growth cycle — model + harness + behavioral memory.

Pipeline: probe → behavioral synth → scout/candidates → improve cycle →
training episode → human report + trail.

CLI: python main.py growth-cycle run|status
Steer: memory/improve/growth/steer.yaml (optional)
Autopilot: MAG_GROWTH_CYCLE=1 or steer.yaml auto: true
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from config import ROOT

SCHEMA = "growth_cycle.v1"
GROWTH_DIR = ROOT / "memory" / "improve" / "growth"
STEER_PATH = GROWTH_DIR / "steer.yaml"
TRAIL = GROWTH_DIR / "growth_trail.jsonl"
REGISTRY = ROOT / "memory" / "improve" / "model_registry.jsonl"

DEFAULT_STEER: dict[str, Any] = {
    "pause": False,
    "max_improve": 2,
    "frontier": True,
    "auto": False,
    "notes": "",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def load_steer() -> dict[str, Any]:
    """Read operator steering overrides; missing file → sensible defaults."""
    steer = dict(DEFAULT_STEER)
    if not STEER_PATH.is_file():
        return steer
    try:
        data = yaml.safe_load(STEER_PATH.read_text(encoding="utf-8")) or {}
        if isinstance(data, dict):
            steer.update(data)
    except Exception:
        pass
    return steer


def growth_cycle_enabled() -> bool:
    """True when env or steer.yaml requests automatic growth cycles."""
    if os.environ.get("MAG_GROWTH_CYCLE", "").strip().lower() in ("1", "true", "yes"):
        return True
    return bool(load_steer().get("auto"))


def _trail(event: str, **fields: Any) -> None:
    GROWTH_DIR.mkdir(parents=True, exist_ok=True)
    row = {"ts": _now(), "event": event, **fields}
    with TRAIL.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def _append_model_registry(probe: dict[str, Any]) -> dict[str, Any]:
    """Append one probe row to model_registry.jsonl."""
    l0 = probe.get("L0") or {}
    l1 = probe.get("L1") or {}
    l2 = probe.get("L2") or {}
    row = {
        "ts": _now(),
        "L0_ok": bool(l0.get("ok")),
        "L1_ok": bool(l1.get("ok")),
        "L1_configured": bool(l1.get("configured")),
        "L1_model": str(l1.get("model") or os.environ.get("OPENROUTER_MODEL") or "openrouter/auto"),
        "L2_ok": bool(l2.get("ok")),
        "verdict": str(probe.get("verdict") or "")[:200],
    }
    try:
        REGISTRY.parent.mkdir(parents=True, exist_ok=True)
        with REGISTRY.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    except OSError as exc:
        row["registry_error"] = str(exc)[:120]
    return row


def _write_model_snapshot(probe: dict[str, Any], day: str) -> str:
    GROWTH_DIR.mkdir(parents=True, exist_ok=True)
    path = GROWTH_DIR / f"{day}-model-snapshot.json"
    payload = {"schema": "model_snapshot.v1", "ts": _now(), "day": day, **probe}
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return _rel(path)


def _behavioral_mining_summary(day: str) -> dict[str, Any]:
    """Lightweight candidate mining when scout/drain paused or dry."""
    try:
        from mag.improve import _behavioral_candidates

        rows = _behavioral_candidates(day)
        return {
            "ok": True,
            "mode": "mining_summary",
            "candidates_n": len(rows),
            "sample": [r.get("claim", "")[:80] for r in rows[:5]],
        }
    except Exception as exc:
        return {"ok": False, "mode": "mining_summary", "error": str(exc)[:200]}


def _write_growth_report(
    *,
    day: str,
    steer: dict[str, Any],
    steps: dict[str, Any],
    ok: bool,
) -> str:
    """Human-readable markdown an operator can scan in ~60s."""
    GROWTH_DIR.mkdir(parents=True, exist_ok=True)
    path = GROWTH_DIR / f"{day}-growth.md"

    probe = steps.get("probe") or {}
    l0 = (probe.get("L0") or {}).get("ok")
    l1 = probe.get("L1") or {}
    l2 = (probe.get("L2") or {}).get("ok")
    behavioral = steps.get("behavioral") or {}
    improve = steps.get("improve") or {}
    scout = steps.get("scout") or {}

    lines = [
        f"# Growth cycle — {day}",
        "",
        f"_ts: {steps.get('ts', _now())}_",
        "",
        "## Steering",
        f"- pause: {steer.get('pause')} · max_improve: {steer.get('max_improve')} · frontier: {steer.get('frontier')}",
    ]
    if steer.get("notes"):
        lines.append(f"- notes: {steer.get('notes')}")
    lines.extend(["", "## Model (frontier)"])
    if probe.get("skipped"):
        lines.append("- frontier disabled — L1 probe skipped")
    else:
        l1_status = "ok" if l1.get("ok") else ("skipped" if l1.get("skipped") else "fail")
        lines.append(
            f"- L0: {'ok' if l0 else 'fail'} · L1: {l1.get('model', '?')} {l1_status} · L2: {'ok' if l2 else 'fail'}"
        )
        if probe.get("snapshot"):
            lines.append(f"- snapshot: `{probe.get('snapshot')}`")

    lines.extend(["", "## Behavioral"])
    if behavioral.get("ok"):
        lines.append(
            f"- leaf: `{behavioral.get('path', '?')}` · themes: {behavioral.get('themes_n', '?')}"
        )
    else:
        lines.append(f"- error: {behavioral.get('error', 'unknown')[:120]}")

    tesuji = steps.get("tesuji_shell") or {}
    if tesuji.get("ok"):
        lines.append(
            f"- tesuji shells: `{tesuji.get('path', '?')}` · wins: {tesuji.get('wins_n', '?')}"
        )
    elif tesuji.get("error"):
        lines.append(f"- tesuji shells error: {str(tesuji.get('error'))[:120]}")

    lines.extend(["", "## Improve"])
    if scout.get("ok"):
        lines.append(
            f"- scout: +{scout.get('candidates_added', 0)} candidates ({scout.get('mode', 'scout')})"
        )
    elif scout.get("mode") == "mining_summary":
        lines.append(f"- mining: {scout.get('candidates_n', 0)} behavioral candidates (scout paused/dry)")
    elif scout.get("skipped"):
        lines.append(f"- scout: skipped ({scout.get('reason', 'paused')})")
    else:
        lines.append(f"- scout error: {str(scout.get('error', scout.get('scout_error', '?')))[:120]}")

    fill = (improve.get("fill") or {}) if isinstance(improve, dict) else {}
    if isinstance(improve, dict) and improve.get("ok") is not False:
        lines.append(
            f"- cycle: improve_queued={fill.get('improve', 0)} handoff={fill.get('handoff', 0)}"
        )
        if improve.get("drain"):
            lines.append(f"- drain: {improve.get('drain', {}).get('action', 'ran')}")
        elif improve.get("drain_skipped"):
            lines.append("- drain: skipped (pause/dry/no-drain)")
    else:
        lines.append(f"- cycle error: {str(improve.get('fill_error') or improve.get('error', '?'))[:120]}")

    episode = steps.get("episode") or {}
    lines.extend(["", "## Verdict"])
    verdict = "ok" if ok else "partial"
    lines.append(f"{verdict} — three_body_episode `{episode.get('event_id', 'n/a')}`")
    if steps.get("errors"):
        lines.append("")
        lines.append("## Errors (non-fatal)")
        for err in steps["errors"]:
            lines.append(f"- {err}")

    body = "\n".join(lines) + "\n"
    path.write_text(body, encoding="utf-8")
    return _rel(path)


def run_growth_cycle(
    *,
    dry: bool = False,
    drain_one: bool | None = None,
    source: str = "growth-cycle",
) -> dict[str, Any]:
    """Run the explicit three-body growth pipeline."""
    day = _today()
    steer = load_steer()
    paused = bool(steer.get("pause"))
    frontier = bool(steer.get("frontier", True))
    max_improve = int(steer.get("max_improve") or 2)
    do_drain = drain_one if drain_one is not None else (not paused and not dry)

    report: dict[str, Any] = {
        "schema": SCHEMA,
        "ts": _now(),
        "day": day,
        "source": source,
        "dry": dry,
        "steer": {k: steer.get(k) for k in ("pause", "max_improve", "frontier", "auto", "notes")},
        "ok": True,
        "steps": {},
        "errors": [],
    }
    steps = report["steps"]
    steps["ts"] = report["ts"]

    # Step A — probe lanes + model snapshot + registry
    probe_result: dict[str, Any] = {"skipped": not frontier, "ok": True}
    if frontier and not dry:
        try:
            from models.probe import probe_all

            probe_result = probe_all(include_l1_chat=True)
            probe_result["registry"] = _append_model_registry(probe_result)
            probe_result["snapshot"] = _write_model_snapshot(probe_result, day)
        except Exception as exc:
            probe_result = {"ok": False, "error": str(exc)[:200]}
            report["errors"].append(f"probe: {exc}")
            report["ok"] = False
    elif frontier and dry:
        probe_result = {"ok": True, "dry": True, "verdict": "dry-run — probe skipped"}
    else:
        probe_result["reason"] = "frontier disabled in steer.yaml"
    steps["probe"] = probe_result

    # Step B — behavioral synth
    behavioral: dict[str, Any] = {}
    try:
        from mag.behavioral_synth import synthesize_behavioral_leaf

        behavioral = synthesize_behavioral_leaf(day)
    except Exception as exc:
        behavioral = {"ok": False, "error": str(exc)[:200]}
        report["errors"].append(f"behavioral: {exc}")
    steps["behavioral"] = behavioral

    tesuji: dict[str, Any] = {}
    try:
        from mag.tesuji_shell import synthesize_tesuji_shell_leaf

        tesuji = synthesize_tesuji_shell_leaf(day)
    except Exception as exc:
        tesuji = {"ok": False, "error": str(exc)[:200]}
        report["errors"].append(f"tesuji_shell: {exc}")
    steps["tesuji_shell"] = tesuji

    # Step C — scout or mining summary
    scout_result: dict[str, Any] = {}
    if paused or dry:
        scout_result = _behavioral_mining_summary(day)
        scout_result["skipped"] = paused
        scout_result["reason"] = "pause" if paused else "dry"
    else:
        try:
            from mag.improve import scout as improve_scout

            scout_result = improve_scout(dry=False)
            scout_result["mode"] = "scout"
        except Exception as exc:
            scout_result = {"ok": False, "error": str(exc)[:200], "mode": "scout"}
            report["errors"].append(f"scout: {exc}")
    steps["scout"] = scout_result

    # Step D — improve cycle (no nested scout)
    improve_result: dict[str, Any] = {}
    if dry:
        improve_result = {"ok": True, "dry": True, "drain_skipped": True}
    else:
        try:
            from mag.improve_loop import run_improve_cycle

            improve_result = run_improve_cycle(
                source=source,
                max_improve=max_improve,
                drain_one=bool(do_drain),
                scout=False,
            )
            if not do_drain:
                improve_result["drain_skipped"] = True
        except Exception as exc:
            improve_result = {"ok": False, "error": str(exc)[:200]}
            report["errors"].append(f"improve_cycle: {exc}")
            report["ok"] = False
    steps["improve"] = improve_result

    # Step E — three_body_episode training event
    episode: dict[str, Any] = {}
    try:
        from mag.training_events import emit

        join = {
            "model": f"L0:{bool((probe_result.get('L0') or {}).get('ok'))} L1:{(probe_result.get('L1') or {}).get('model', 'n/a')}",
            "harness": f"improve={((improve_result.get('fill') or {}).get('improve') if isinstance(improve_result, dict) else 0)}",
            "behavioral": f"themes={behavioral.get('themes_n', 0)} path={behavioral.get('path', '')}",
        }
        episode = emit(
            "three_body_episode",
            join=join,
            input_data={
                "day": day,
                "steer_pause": paused,
                "steer_frontier": frontier,
                "probe_ok": probe_result.get("ok"),
            },
            action={
                "dry": dry,
                "drain_one": do_drain,
                "max_improve": max_improve,
                "scout_mode": scout_result.get("mode"),
            },
            outcome={
                "behavioral_themes": behavioral.get("themes_n"),
                "candidates_added": scout_result.get("candidates_added", scout_result.get("candidates_n")),
                "improve_queued": (improve_result.get("fill") or {}).get("improve") if isinstance(improve_result, dict) else 0,
                "cycle_ok": improve_result.get("ok") if isinstance(improve_result, dict) else None,
            },
            pattern_tags=["growth_cycle", f"source_{source}"],
        )
    except Exception as exc:
        episode = {"ok": False, "error": str(exc)[:200]}
        report["errors"].append(f"episode: {exc}")
    steps["episode"] = episode
    report["errors"] = report["errors"]  # mirror for report writer
    steps["errors"] = report["errors"]

    # Step F — human report + trail
    report_path = _write_growth_report(
        day=day,
        steer=steer,
        steps=steps,
        ok=report["ok"] and not report["errors"],
    )
    report["report_path"] = report_path
    _trail(
        "cycle",
        day=day,
        ok=report["ok"],
        dry=dry,
        paused=paused,
        report_path=report_path,
        probe_ok=probe_result.get("ok"),
        behavioral_themes=behavioral.get("themes_n"),
        episode_id=episode.get("event_id"),
        errors_n=len(report["errors"]),
    )
    return report


def growth_cycle_status() -> dict[str, Any]:
    """Last trail entry, steer.yaml, latest growth markdown path."""
    steer = load_steer()
    last_trail: dict[str, Any] | None = None
    if TRAIL.is_file():
        try:
            lines = [ln for ln in TRAIL.read_text(encoding="utf-8").splitlines() if ln.strip()]
            if lines:
                last_trail = json.loads(lines[-1])
        except Exception:
            pass

    latest_md: str | None = None
    if GROWTH_DIR.is_dir():
        mds = sorted(GROWTH_DIR.glob("*-growth.md"), reverse=True)
        if mds:
            latest_md = _rel(mds[0])

    return {
        "schema": SCHEMA,
        "ts": _now(),
        "steer_path": _rel(STEER_PATH),
        "steer_exists": STEER_PATH.is_file(),
        "steer": steer,
        "enabled": growth_cycle_enabled(),
        "last_trail": last_trail,
        "latest_report": latest_md,
        "trail_path": _rel(TRAIL),
        "registry_path": _rel(REGISTRY),
    }


def maybe_run_growth_cycle(**kwargs: Any) -> dict[str, Any] | None:
    """Autopilot hook — no-op unless MAG_GROWTH_CYCLE=1 or steer auto."""
    if not growth_cycle_enabled():
        return None
    return run_growth_cycle(source="autopilot", **kwargs)


def main(argv: list[str] | None = None) -> int:
    import argparse
    import sys

    ap = argparse.ArgumentParser(prog="growth-cycle")
    sub = ap.add_subparsers(dest="cmd")

    pr = sub.add_parser("run", help="Run one three-body growth cycle")
    pr.add_argument("--dry", action="store_true", help="Skip probe/scout/drain side effects")
    pr.add_argument("--no-drain", action="store_true", help="Force skip orchestrator drain")
    pr.add_argument("--json", action="store_true")

    sub.add_parser("status", help="Last trail + steer + latest report")

    args = ap.parse_args(argv)
    if args.cmd == "run":
        res = run_growth_cycle(
            dry=bool(args.dry),
            drain_one=False if args.no_drain else None,
        )
        print(json.dumps(res, indent=2, default=str))
        return 0 if res.get("ok") else 1
    if args.cmd == "status":
        print(json.dumps(growth_cycle_status(), indent=2, default=str))
        return 0
    ap.print_help()
    return 2


if __name__ == "__main__":
    import sys

    sys.exit(main())
