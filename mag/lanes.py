"""Resource lanes + usage log — local first, Grok budgeted."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT


def _strip_yaml_comments(text: str) -> str:
    lines = []
    for line in text.splitlines():
        if "#" in line:
            # keep quoted hashes roughly; simple strip for our config style
            in_q = False
            out = []
            for ch in line:
                if ch == '"':
                    in_q = not in_q
                if ch == "#" and not in_q:
                    break
                out.append(ch)
            line = "".join(out).rstrip()
        if line.strip():
            lines.append(line)
    return "\n".join(lines)


def load_lanes() -> dict[str, Any]:
    path = ROOT / "configs" / "lanes.yaml"
    defaults: dict[str, Any] = {
        "default_lane": "L0",
        "grok_budget": {
            "max_escalations_per_day": 8,
            "require_priority": True,
            "attach_brief": True,
        },
        "priority_markers": ["[priority]", "[grok]", "[L2]"],
        "local_markers": ["[mag]", "[assign]", "[local]", "[L0]"],
        "usage_log": "logs/usage.jsonl",
        "briefs_dir": "memory/briefs",
        "local_models": {
            "clerk": "gemma:2b",
            "worker": "gemma4:latest",
            "biographer": "gemma4:latest",
            "router": "gemma:2b",
        },
    }
    if not path.is_file():
        return defaults
    try:
        import yaml  # type: ignore

        raw = path.read_text(encoding="utf-8")
        data = yaml.safe_load(_strip_yaml_comments(raw)) or {}
        if not isinstance(data, dict):
            return defaults
        # shallow merge
        out = {**defaults, **data}
        if isinstance(data.get("grok_budget"), dict):
            out["grok_budget"] = {**defaults["grok_budget"], **data["grok_budget"]}
        return out
    except Exception:
        return defaults


def usage_log_path() -> Path:
    rel = load_lanes().get("usage_log") or "logs/usage.jsonl"
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def briefs_dir() -> Path:
    rel = load_lanes().get("briefs_dir") or "memory/briefs"
    p = ROOT / rel
    p.mkdir(parents=True, exist_ok=True)
    return p


def log_usage(
    *,
    lane: str,
    action: str,
    detail: str = "",
    ok: bool = True,
    meta: dict[str, Any] | None = None,
) -> None:
    row = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "lane": lane,
        "action": action,
        "ok": ok,
        "detail": (detail or "")[:500],
        "meta": meta or {},
    }
    path = usage_log_path()
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, default=str) + "\n")


def usage_tail(limit: int = 40) -> list[dict[str, Any]]:
    path = usage_log_path()
    if not path.is_file():
        return []
    limit = max(0, int(limit))
    if not limit:
        return []
    rows: list[dict[str, Any]] = []
    # The usage log is append-only and can grow large. Reading the whole file
    # for every router probe turned a 33 MB history into repeated parse work.
    # Read from the end, expanding only when one oversized row means the first
    # pass did not contain enough complete lines.
    try:
        size = path.stat().st_size
        chunk_size = min(size, max(64 * 1024, limit * 2048))
        raw = b""
        while True:
            start = max(0, size - chunk_size)
            with path.open("rb") as f:
                f.seek(start)
                raw = f.read()
            lines = raw.splitlines()
            if start == 0 or len(lines) > limit:
                break
            if chunk_size >= size:
                break
            chunk_size = min(size, chunk_size * 2)
        if start > 0 and lines:
            # The first line may be a partial row because the read starts in
            # the middle of the file; discard only that fragment.
            lines = lines[1:]
        text_lines = [line.decode("utf-8", errors="replace") for line in lines[-limit:]]
    except OSError:
        text_lines = []
    for line in text_lines:
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows[-limit:]


def usage_today_counts() -> dict[str, int]:
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    counts: dict[str, int] = {}
    for row in usage_tail(500):
        ts = str(row.get("ts") or "")
        if not ts.startswith(day):
            continue
        lane = str(row.get("lane") or "?")
        counts[lane] = counts.get(lane, 0) + 1
    return counts


def text_has_priority(text: str) -> bool:
    t = (text or "").lower()
    for m in load_lanes().get("priority_markers") or []:
        if str(m).lower() in t:
            return True
    return False


def goal_lane(goal: str) -> str:
    """Infer preferred lane from goal/todo text."""
    g = goal or ""
    if text_has_priority(g):
        return "L2"
    if any(k in g.lower() for k in ("wait for me", "ask human", "[human]", "[l3]")):
        return "L3"
    return str(load_lanes().get("default_lane") or "L0")


def grok_escalations_today() -> int:
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    n = 0
    for row in usage_tail(500):
        if not str(row.get("ts") or "").startswith(day):
            continue
        if row.get("lane") == "L2" and row.get("action") in {
            "escalate",
            "escalate_harness",
            "handoff",
        }:
            n += 1
    return n


def can_escalate_grok(
    *,
    goal: str = "",
    reason: str = "",
    force: bool = False,
) -> tuple[bool, str]:
    """Whether L2 Grok is allowed under budget + priority policy."""
    if force:
        return True, "force"
    pol = load_lanes()
    budget = pol.get("grok_budget") or {}
    max_d = int(budget.get("max_escalations_per_day") or 8)
    used = grok_escalations_today()
    if used >= max_d:
        return False, f"daily L2 budget exhausted ({used}/{max_d})"
    if budget.get("require_priority", True):
        blob = f"{goal}\n{reason}"
        if not text_has_priority(blob):
            return (
                False,
                "priority required — tag [priority] or [grok] (or set require_priority: false)",
            )
    return True, f"ok ({used + 1}/{max_d})"


def latest_brief_text(session_id: str | None = None) -> str:
    bdir = briefs_dir()
    if session_id:
        p = bdir / f"{session_id}.md"
        if p.is_file():
            return p.read_text(encoding="utf-8", errors="replace")
    latest = bdir / "latest.md"
    if latest.is_file():
        text = latest.read_text(encoding="utf-8", errors="replace")
        # Q1 poison fix (2026-09-27, ATLAS_SELF_STEAL GAP 1): briefs/latest.md was
        # FROZEN 2026-09-26 with an August-fossil body (operator GO); every pack was
        # injecting the fossil. Evidence: freeze banner names state/CURRENT.md as
        # truth. Serve the live truth instead of the fossil.
        if text.lstrip().startswith("# FROZEN"):
            current = ROOT / "state" / "CURRENT.md"
            if current.is_file():
                return current.read_text(encoding="utf-8", errors="replace")
        return text
    # newest by mtime
    files = sorted(bdir.glob("*.md"), key=lambda x: x.stat().st_mtime, reverse=True)
    for f in files:
        if f.name != "latest.md":
            return f.read_text(encoding="utf-8", errors="replace")
    return ""


def board_pack() -> dict[str, Any]:
    """Snapshot for Mag Board UI."""
    mem = ROOT / "memory"
    def _read(rel: str, n: int = 4000) -> str:
        p = ROOT / rel
        if not p.is_file():
            return ""
        return p.read_text(encoding="utf-8", errors="replace")[:n]

    lanes = load_lanes()
    counts = usage_today_counts()
    allowed, why = can_escalate_grok(goal="[priority] probe", force=False)
    # budget probe without priority always false if require — show raw budget
    used = grok_escalations_today()
    max_d = int((lanes.get("grok_budget") or {}).get("max_escalations_per_day") or 8)
    records_kpi: dict[str, Any] = {}
    try:
        kpi_path = ROOT / "memory" / "biography" / "kpi.json"
        if kpi_path.is_file():
            records_kpi = json.loads(kpi_path.read_text(encoding="utf-8"))
        else:
            from mag.records import write_kpi

            records_kpi = write_kpi(source="board")
    except Exception as e:
        records_kpi = {"error": str(e)[:120]}

    n_leaves = records_kpi.get("n_leaves")
    pct = records_kpi.get("complete_pct")
    n_inc = records_kpi.get("n_incomplete")
    records_line = (
        f"Records: {n_leaves if n_leaves is not None else '?'} leaves · "
        f"{pct if pct is not None else '?'}% complete"
        + (f" · {n_inc} holes" if n_inc else " · no holes")
    )

    return {
        "ok": True,
        "lanes": {
            "default": lanes.get("default_lane"),
            "local_models": lanes.get("local_models"),
            "grok_budget": lanes.get("grok_budget"),
            "priority_markers": lanes.get("priority_markers"),
        },
        "usage_today": counts,
        "grok_escalations_today": used,
        "grok_budget_max": max_d,
        "grok_budget_remaining": max(0, max_d - used),
        "live_from_grok": _read("memory/live_from_grok.md"),
        "attention": _read("memory/attention.md", 3000),
        "todo": _read("queue/todo.md", 3000),
        "mag_status": _read("state/MAG.md", 2000),
        "current": _read("state/CURRENT.md", 2000),
        "latest_brief": latest_brief_text()[:3000],
        "product_home": "http://127.0.0.1:8765/",
        "records_kpi": records_kpi,
        "records_line": records_line,
        "instrument_note": (
            "Strike desk (8743) is optional analysis only — not Mag home. "
            "Hands = Mag; Mirror = strike when entropy is high. "
            + records_line
        ),
        "runtime": _runtime_status(),
    }


def _runtime_status() -> dict[str, Any]:
    try:
        from mag.runtime import read_heartbeat

        return read_heartbeat()
    except Exception as e:
        return {"alive": False, "reason": str(e)}
