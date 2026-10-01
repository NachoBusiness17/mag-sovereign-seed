"""Passive warning monitor — warnings are monitored + handled via OUR system.

Scans the framework's own logs for warning/error lines, dedupes by signature,
and reports NEW warnings into the failure KB (the RESTful doctor). From there
each warning gets a remedy card, clusters into recurring_patterns, emits
training events, and surfaces in the Control Room — all passively, on governor
cadence, without the operator having to notice or hand-run anything.

Seam:  failure_kb.log_failure(kind="warning", ...)  -> FKB index + remedy + training
Store: memory/warnings/seen.json  (signatures already reported; idempotent)

CLI:   python -m mag.warning_monitor run|status [--dry]
REST:  GET /api/v1/warnings            (status)
       POST /api/v1/warnings {action:run[, dry]}   (passive sweep)
Cadence: governor_autorun MAG_WARN_EVERY (default 120 ticks)
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

LOG_DIR = ROOT / "logs"
SEEN_PATH = ROOT / "memory" / "warnings" / "seen.json"

# Warning-ish line patterns. Deliberately broad; the signature-dedup + length
# floor keeps false positives from re-reporting (we only report each sig once).
_WARN_RE = re.compile(
    r"(?i)\b(error|exception|traceback|warning|warn|failed|timeout|stalled|crash)\b"
)

# Only textual process logs (NOT .jsonl telemetry, which would be all noise).
_SCAN_GLOBS = ("orchestrator/*.out.log", "*.log")


def _now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def _load_seen(seen_path: Path) -> set[str]:
    if not seen_path.is_file():
        return set()
    try:
        data = json.loads(seen_path.read_text(encoding="utf-8", errors="replace"))
        return set(data.get("seen", []) or [])
    except (json.JSONDecodeError, OSError):
        return set()


def _save_seen(seen: set[str], seen_path: Path) -> None:
    seen_path.parent.mkdir(parents=True, exist_ok=True)
    seen_path.write_text(json.dumps({"seen": sorted(seen)}, indent=2), encoding="utf-8")


def _normalize(line: str) -> str:
    return " ".join(line.split()).strip()


def _signature(rel: str, line: str) -> str:
    return hashlib.sha1(f"{rel}::{_normalize(line)[:200]}".encode("utf-8")).hexdigest()[:24]


def extract_warnings(*, log_dir: Path = LOG_DIR, tail: int = 400) -> list[dict[str, str]]:
    """Scan textual process logs and pull warning/error lines.

    Returns [{file, line, sig}] — deduped by signature within this pass.
    """
    out: list[dict[str, str]] = []
    seen_sig: set[str] = set()
    if not log_dir.is_dir():
        return out
    files: list[Path] = []
    for glob in _SCAN_GLOBS:
        files.extend(sorted(log_dir.glob(glob)))
    for f in files:
        try:
            rel = f.relative_to(log_dir).as_posix()
            text = f.read_text(encoding="utf-8", errors="replace")
            lines = text.splitlines()[-tail:]
        except OSError:
            continue
        for line in lines:
            ln = _normalize(line)
            if len(ln) < 15:
                continue
            if not _WARN_RE.search(ln):
                continue
            sig = _signature(rel, ln)
            if sig in seen_sig:
                continue
            seen_sig.add(sig)
            out.append({"file": rel, "line": ln, "sig": sig})
    return out


def run(
    *,
    dry: bool = False,
    limit: int = 20,
    log_dir: Path = LOG_DIR,
    seen_path: Path = SEEN_PATH,
    report: Callable[[dict[str, str]], Any] | None = None,
) -> dict[str, Any]:
    """Passive sweep: report new warning signatures into the failure KB.

    Idempotent — each signature is reported at most once (recorded in seen_path).
    """
    from mag import failure_kb

    def _default_report(w: dict[str, str]) -> Any:
        return failure_kb.log_failure(
            kind="warning",
            detail=w["line"][:500],
            tool=w["file"],
            error=w["line"][:300],
            phase="passive-monitor",
        )

    reporter = report or _default_report
    seen = _load_seen(seen_path)
    found = extract_warnings(log_dir=log_dir)
    new_sigs: list[dict[str, str]] = []
    for w in found:
        if w["sig"] in seen:
            continue
        new_sigs.append(w)
        if len(new_sigs) >= limit:
            break

    reported = []
    for w in new_sigs:
        if not dry:
            try:
                res = reporter(w)
                reported.append(
                    {"sig": w["sig"], "file": w["file"], "sig_ok": bool(res.get("ok", True))}
                )
            except Exception as e:
                reported.append({"sig": w["sig"], "file": w["file"], "error": str(e)[:120]})
            seen.add(w["sig"])
    if not dry:
        _save_seen(seen, seen_path)

    return {
        "ok": True,
        "schema": "warning_monitor.v1",
        "ts": _now(),
        "dry": dry,
        "scanned": len(found),
        "reported": reported,
        "reported_n": len(reported),
        "seen_n": len(seen),
        "log_dir": str(log_dir),
        "seen_path": str(seen_path),
    }


def recent_warnings(*, limit: int = 20) -> list[dict[str, Any]]:
    from mag import failure_kb

    rows = failure_kb._read_log(tail=500)
    return [r for r in rows if r.get("kind") == "warning"][-limit:]


def status() -> dict[str, Any]:
    seen = _load_seen(SEEN_PATH)
    rec = recent_warnings(limit=20)
    return {
        "ok": True,
        "schema": "warning_monitor.status.v1",
        "ts": _now(),
        "reported_total": len(seen),
        "recent_n": len(rec),
        "recent": [
            {"ts": r.get("ts", ""), "tool": r.get("tool"), "sig": r.get("sig", ""),
             "detail": (r.get("detail") or "")[:140]}
            for r in rec
        ],
        "seen_path": str(SEEN_PATH),
    }


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = (argv[0] if argv else "status").lower()
    dry = "--dry" in argv or "-n" in argv
    if cmd == "run":
        res = run(dry=dry)
        print(json.dumps(res, indent=2, ensure_ascii=False))
        return 0
    print(json.dumps(status(), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
