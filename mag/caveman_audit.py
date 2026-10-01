"""Caveman audit — doc density scan (Mag v2/v3).

Complements ponytail_audit (code). Scans markdown for filler, bloat, hedge.
Law: security/irreversible sections exempt from aggressive trimming hints.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from config import ROOT

SCHEMA = "caveman_audit.v1"

SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__", "memory", "logs", "derived"}

DEFAULT_PATHS = (
    "docs/ref",
    "docs",
    "queue",
    "HANDOFF_MAG_AGENT_TODOS.md",
    "AGENTS.md",
    "LOAD.md",
)

FILLER_PATTERNS = [
    (r"\bit'?s important to note\b", "filler"),
    (r"\bin order to\b", "filler"),
    (r"\bgoing forward\b", "filler"),
    (r"\bat the end of the day\b", "filler"),
    (r"\bleverage\b", "marketing"),
    (r"\butilize\b", "marketing"),
    (r"\bdelve\b", "marketing"),
    (r"\brobust\b", "marketing"),
    (r"\bcomprehensive\b", "marketing"),
    (r"\bessentially\b", "hedge"),
    (r"\bperhaps\b", "hedge"),
    (r"\bmight want to consider\b", "hedge"),
]

EXEMPT_MARKERS = ("G3", "irreversible", "secret", "T0", "T1", "password", "tier law")


def _rel(p: Path) -> str:
    try:
        return str(p.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(p)


def _iter_md(paths: list[str] | None) -> list[Path]:
    if paths:
        out: list[Path] = []
        for raw in paths:
            p = ROOT / raw
            if p.is_file() and p.suffix.lower() in (".md", ".txt"):
                out.append(p)
            elif p.is_dir():
                for f in p.rglob("*.md"):
                    if set(f.parts) & SKIP_DIRS:
                        continue
                    out.append(f)
        return sorted(set(out))
    out = []
    for raw in DEFAULT_PATHS:
        p = ROOT / raw
        if p.is_file():
            out.append(p)
        elif p.is_dir():
            for f in p.rglob("*.md"):
                if set(f.parts) & SKIP_DIRS:
                    continue
                out.append(f)
    return sorted(set(out))


def _line_exempt(line: str) -> bool:
    low = line.lower()
    return any(m.lower() in low for m in EXEMPT_MARKERS)


def _scan_file(path: Path) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return findings
    rel = _rel(path)
    for i, line in enumerate(lines, 1):
        if _line_exempt(line):
            continue
        if len(line) > 220:
            findings.append({
                "tag": "long_line",
                "what": f"line {i}: {len(line)} chars",
                "replacement": "split or caveman trim",
                "path": f"{rel}:{i}",
                "severity": "low",
            })
        for pat, kind in FILLER_PATTERNS:
            if re.search(pat, line, re.I):
                findings.append({
                    "tag": kind,
                    "what": f"line {i}: `{pat}`",
                    "replacement": "delete or shorten",
                    "path": f"{rel}:{i}",
                    "severity": "low",
                })
    return findings


def run_audit(*, paths: list[str] | None = None) -> dict[str, Any]:
    files = _iter_md(paths)
    findings: list[dict[str, Any]] = []
    for fp in files:
        findings.extend(_scan_file(fp))
    sev_order = {"high": 0, "medium": 1, "low": 2}
    findings.sort(key=lambda f: (sev_order.get(f.get("severity", "low"), 9), f.get("path", "")))
    dense = len(findings) == 0
    return {
        "ok": True,
        "schema": SCHEMA,
        "dense": dense,
        "summary": "Dense already. Ship." if dense else f"{len(findings)} caveman finding(s).",
        "files_scanned": len(files),
        "findings": findings[:80],
        "caveman": "https://github.com/JuliusBrussee/caveman",
    }


def format_report(res: dict[str, Any]) -> str:
    if res.get("dense"):
        return str(res.get("summary"))
    lines = [str(res.get("summary")), ""]
    for f in res.get("findings") or []:
        lines.append(f"{f.get('tag')}: {f.get('what')}. {f.get('replacement')} [{f.get('path')}]")
    lines.append(f"\nScanned {res.get('files_scanned', 0)} files.")
    return "\n".join(lines)
