"""Local steward jobs — janitor clerk layer (v4).

Queued [steward] goals run scoped catalog/digest work and file one leaf each.
Not an open REPL — scheduled jobs with disk outputs.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT

STEWARD_ROOT = ROOT / "memory" / "steward"
SCOPE_DIR = STEWARD_ROOT / "scope_cards"
LAST_RUNS = STEWARD_ROOT / "last_runs.json"
TRAIL = ROOT / "memory" / "runs" / "steward_trail.jsonl"

BUILD_GLOB = "docs/ref/BUILD-*.md"
RUN_DOC = ROOT / "docs" / "ref" / "MAG_NEXT_CODING_RUN.md"

STEWARD_JOBS = frozenset({
    "steward-daily",
    "steward-scope",
    "steward-patterns",
    "steward-prompts",
})


def run_steward_daily(*, dry: bool = False) -> dict[str, Any]:
    """File exactly one bounded, local-only daily maintenance leaf."""
    day = _now()[:10]
    out_path = STEWARD_ROOT / "daily" / f"{day}.json"
    if out_path.is_file() and not dry:
        try:
            prior = json.loads(out_path.read_text(encoding="utf-8"))
            return {**prior, "ok": True, "action": "already_filed", "path": str(out_path)}
        except (OSError, json.JSONDecodeError):
            pass
    by_pattern: dict[str, int] = {}
    total = 0
    try:
        from mag.training_events import stats

        summary = stats()
        by_pattern = dict(summary.get("by_pattern") or {})
        total = int(summary.get("total") or 0)
    except Exception:
        pass
    payload = {
        "schema": "steward_daily.v1",
        "ok": True,
        "action": "preview" if dry else "filed",
        "date": day,
        "job_id": "steward-daily",
        "provider": "local-deterministic",
        "remote_calls": 0,
        "inputs": {"training_events_total": total, "patterns_seen": len(by_pattern)},
        "maintenance": {
            "top_patterns": [
                {"pattern": name, "events": count}
                for name, count in sorted(by_pattern.items(), key=lambda row: (-row[1], row[0]))[:8]
            ],
            "frozen_builds": len(find_frozen_builds()),
        },
        "outcomes": [{"kind": "daily_catalog", "leaf": f"memory/steward/daily/{day}.json", "bounded": True}],
    }
    if dry:
        return payload
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return {**payload, "path": str(out_path)}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _trail(event: str, **fields: Any) -> None:
    TRAIL.parent.mkdir(parents=True, exist_ok=True)
    row = {"ts": _now(), "event": event, **fields}
    with TRAIL.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def _load_last_runs() -> dict[str, str]:
    if not LAST_RUNS.is_file():
        return {}
    try:
        return json.loads(LAST_RUNS.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _save_last_run(job_id: str) -> None:
    STEWARD_ROOT.mkdir(parents=True, exist_ok=True)
    runs = _load_last_runs()
    runs[job_id] = _now()
    LAST_RUNS.write_text(json.dumps(runs, indent=2), encoding="utf-8")


def ran_today(job_id: str) -> bool:
    ts = _load_last_runs().get(job_id) or ""
    if not ts:
        return False
    try:
        day = datetime.fromisoformat(ts.replace("Z", "+00:00")).date()
        return day == datetime.now(timezone.utc).date()
    except ValueError:
        return False


def find_frozen_builds() -> list[dict[str, Any]]:
    """BUILD specs marked frozen under docs/ref/."""
    out: list[dict[str, Any]] = []
    for p in sorted((ROOT / "docs" / "ref").glob("BUILD-*.md")):
        text = p.read_text(encoding="utf-8", errors="replace")
        if re.search(r"(?im)^\*\*Status:\*\*\s*frozen", text) or re.search(
            r"(?im)^Status:\s*frozen", text
        ):
            slug = p.stem.replace("BUILD-", "", 1)
            out.append({
                "slug": slug,
                "path": p.relative_to(ROOT).as_posix(),
                "mtime": p.stat().st_mtime,
            })
    out.sort(key=lambda x: x["mtime"], reverse=True)
    return out


def _parse_build_sections(text: str) -> dict[str, str]:
    """Extract Goal, Scope In/Out, Verify from BUILD markdown."""
    sections: dict[str, str] = {}

    m = re.search(r"(?im)^##\s*Goal\s*\n+(.*?)(?=^##|\Z)", text, re.DOTALL)
    if m:
        sections["goal"] = m.group(1).strip()[:800]

    for row in re.finditer(r"^\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|", text, re.MULTILINE):
        key, val = row.group(1).strip().lower(), row.group(2).strip()
        if key in ("in", "out"):
            sections[key] = val[:400]

    m = re.search(r"(?im)^##\s*Verify\s*\n+(.*?)(?=^##|\Z)", text, re.DOTALL)
    if m:
        sections["verify"] = m.group(1).strip()[:600]

    m = re.search(r"(?im)^\*\*Slug:\*\*\s*`?([^`\n]+)", text)
    if m:
        sections["slug"] = m.group(1).strip()

    return sections


def _run_row_hint(slug: str) -> str:
    if not RUN_DOC.is_file():
        return ""
    text = RUN_DOC.read_text(encoding="utf-8", errors="replace")
    tokens = re.findall(r"[a-z0-9-]+", slug.lower())
    for line in text.splitlines():
        low = line.lower()
        if any(t in low for t in tokens if len(t) > 3):
            if "|" in line and ("RUN" in line or "C" in line or "Wave" in line):
                return line.strip()[:200]
    return ""


def _heuristic_scope_card(build_path: Path, sections: dict[str, str]) -> str:
    slug = sections.get("slug") or build_path.stem.replace("BUILD-", "", 1)
    rel = build_path.relative_to(ROOT).as_posix()
    run_hint = _run_row_hint(slug)
    goal_line = (sections.get("goal") or "implement frozen BUILD")[:200]
    return f"""# Scope · {slug}

**BUILD:** `{rel}`  
**Status:** frozen (scope card for dumb agents)  
**Generated:** {_now()[:19]}Z

## In scope
{sections.get("in") or goal_line}

## Out of scope
{sections.get("out") or "Anything not listed in BUILD scope table"}

## Verify
{sections.get("verify") or "pytest + commands in BUILD Verify section"}

## RUN context
{run_hint or "(see MAG_NEXT_CODING_RUN.md)"}

## Dumb-agent goal
```text
[build] {goal_line[:180]}
```

## Risk
- Do not expand beyond BUILD acceptance
- One branch · one RUN · file outcomes before chat ends
"""


def _llm_polish_scope(heuristic: str, build_excerpt: str) -> str | None:
    try:
        from llm import chat

        system = (
            "You compress frozen BUILD specs into scope cards for builder agents. "
            "Keep under 600 words. Plain markdown. No chat. Preserve verify commands."
        )
        user = f"BUILD excerpt:\n{build_excerpt[:2500]}\n\nDraft:\n{heuristic[:2000]}\n\nPolish the scope card."
        out = chat("worker", system, user, temperature=0.1).strip()
        if out and len(out) > 100:
            return out
    except Exception:
        pass
    return None


def run_steward_scope(
    *,
    slug: str | None = None,
    dry: bool = False,
    use_llm: bool = True,
) -> dict[str, Any]:
    """Digest frozen BUILD → scope card leaf for DeepSeek queue."""
    builds = find_frozen_builds()
    if not builds:
        return {"ok": True, "action": "noop", "reason": "no frozen BUILD specs"}

    pick = builds[0]
    if slug:
        for b in builds:
            if b["slug"] == slug or slug in b["path"]:
                pick = b
                break

    build_path = ROOT / pick["path"]
    text = build_path.read_text(encoding="utf-8", errors="replace")
    sections = _parse_build_sections(text)
    card_slug = sections.get("slug") or pick["slug"]
    heuristic = _heuristic_scope_card(build_path, sections)

    body = heuristic
    if use_llm and not dry:
        polished = _llm_polish_scope(heuristic, text[:4000])
        if polished:
            body = polished

    out_path = SCOPE_DIR / f"{card_slug}.md"
    result: dict[str, Any] = {
        "schema": "steward_scope.v1",
        "ok": True,
        "dry": dry,
        "job": "steward-scope",
        "slug": card_slug,
        "build_path": pick["path"],
        "scope_path": out_path.relative_to(ROOT).as_posix(),
        "chars": len(body),
    }

    if dry:
        result["preview"] = body[:500]
        return result

    SCOPE_DIR.mkdir(parents=True, exist_ok=True)
    out_path.write_text(body, encoding="utf-8")
    _save_last_run("steward-scope")
    _trail("steward_scope", slug=card_slug, path=str(out_path))

    try:
        from mag.training_events import emit

        emit(
            "route_decision",
            join={"build_slug": card_slug},
            input_data={"build_path": pick["path"]},
            action={"job": "steward-scope", "scope_path": result["scope_path"]},
            outcome={"chars": len(body), "filed": True},
            pattern_tags=["steward_scope"],
        )
    except Exception:
        pass

    # Queue follow-up build goal if none pending (optional nudge)
    try:
        from mag.governor_autorun import queue_has_goal

        dumb = f"[build] implement scope card {card_slug} per {pick['path']}"
        if not queue_has_goal(dumb):
            result["suggested_queue_goal"] = dumb
    except Exception:
        pass

    result["path"] = str(out_path)
    return result


def run_steward_patterns(*, dry: bool = False) -> dict[str, Any]:
    """Cluster recent training events into a daily patterns digest."""
    out_path = STEWARD_ROOT / "daily" / f"{_now()[:10]}-patterns.md"
    lines = [f"# Steward patterns · {_now()[:10]}", ""]

    try:
        from mag.training_events import stats

        s = stats()
        by_pat = s.get("by_pattern") or {}
        if by_pat:
            lines.append("## Training events (by pattern)")
            for k, v in sorted(by_pat.items(), key=lambda x: -x[1])[:12]:
                lines.append(f"- **{k}**: {v}")
        else:
            lines.append("_No training events yet._")
    except Exception as exc:
        lines.append(f"_stats error: {exc}_")

        try:
            from mag.loop_audit import run_audit

            la = run_audit(tail=500)
            findings = la.get("findings") or []
            if findings:
                lines.extend(["", "## Loop-audit signals"])
                for sig in findings[:8]:
                    lines.append(f"- {sig.get('kind')}: {sig.get('message', '')[:120]}")
        except Exception:
            pass

    body = "\n".join(lines)
    result = {"ok": True, "dry": dry, "job": "steward-patterns", "chars": len(body)}

    if dry:
        result["preview"] = body[:400]
        return result

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(body, encoding="utf-8")
    _save_last_run("steward-patterns")
    _trail("steward_patterns", path=str(out_path))
    result["path"] = str(out_path)
    return result


def run_job(job_id: str, *, dry: bool = False, **kwargs: Any) -> dict[str, Any]:
    job_id = (job_id or "").strip().lower()
    if job_id not in STEWARD_JOBS:
        return {"ok": False, "error": f"unknown steward job: {job_id}"}
    if job_id == "steward-scope":
        return run_steward_scope(dry=dry, **kwargs)
    if job_id == "steward-daily":
        return run_steward_daily(dry=dry)
    if job_id == "steward-patterns":
        return run_steward_patterns(dry=dry)
    return {"ok": False, "error": "not implemented", "job": job_id}


def parse_steward_goal(goal: str) -> str | None:
    """Extract job id from `[steward] steward-scope — …` goal."""
    g = (goal or "").strip()
    if not g.lower().startswith("[steward]"):
        return None
    rest = g[len("[steward]") :].strip()
    for job in sorted(STEWARD_JOBS, key=len, reverse=True):
        if rest.lower().startswith(job):
            return job
    m = re.match(r"^([a-z0-9-]+)", rest.lower())
    return m.group(1) if m else None


def fill_steward_queue(*, max_jobs: int = 2) -> list[dict[str, Any]]:
    """Seed orchestrator with steward jobs not yet run today."""
    from mag.governor_autorun import enqueue_routed, queue_has_goal

    queued: list[dict[str, Any]] = []
    candidates: list[tuple[str, str]] = []

    builds = find_frozen_builds()
    for b in builds:
        slug = b["slug"]
        scope_path = SCOPE_DIR / f"{slug}.md"
        if not scope_path.is_file() and not ran_today("steward-scope"):
            candidates.append(
                (
                    "steward-scope",
                    f"[steward] steward-scope — digest frozen BUILD {slug}",
                )
            )
            break

    daily_path = STEWARD_ROOT / "daily" / f"{_now()[:10]}.json"
    if not daily_path.is_file():
        candidates.append(
            ("steward-daily", "[steward] steward-daily — bounded local maintenance leaf")
        )

    for job_id, goal in candidates[:max_jobs]:
        if queue_has_goal(goal):
            continue
        rec = enqueue_routed(goal, tag=f"steward-{job_id}", depth="scut")
        rec["steward_job"] = job_id
        queued.append(rec)
    return queued


def execute_steward_goal(goal: str, *, dry: bool = False) -> dict[str, Any]:
    """Run steward job from queue goal text."""
    job_id = parse_steward_goal(goal)
    if not job_id:
        return {"ok": False, "error": "not a steward goal", "goal": goal[:120]}
    return run_job(job_id, dry=dry)
