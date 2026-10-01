"""Ponytail ladder audit — over-engineering scan (Mag v2).

Ref: https://github.com/dietrichgebert/ponytail
Law: ladder cuts code bloat; tiers/gates/residual never cut.
"""
from __future__ import annotations

import ast
import os
import re
import stat
from pathlib import Path
from typing import Any

from config import ROOT

SCHEMA = "ponytail_audit.v1"

SKIP_DIRS = {
    ".git", ".venv", "node_modules", "__pycache__", "dist", "build",
    ".pytest_cache", "memory", "logs", "state", "derived",
}

KNOWN_DUP_CONSTS = (("DEPTH_JOB_MAP", ("mag/router.py", "mag/governor_autorun.py")),)

ABANDONED_MARKERS = (
    ("sovereign-mirror-scaffold", "mag/lattice_loop.py", "external dep — optional spore only"),
)

SHRINK_THRESHOLD_LINES = 900


def _rel(p: Path) -> str:
    try:
        return str(p.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(p)


def _reparse_dir(path: Path) -> bool:
    """True when path is a reparse point (junction/symlink dir) or unreadable.

    B2-76 junction law: a reparse directory is never descended - a mirrored tree
    is counted once, at its real path. An unreadable entry is treated the same
    (do not descend), because the audit is a scanner, not a gate on readability.
    """
    if os.name != "nt":
        return False
    try:
        st = path.stat(follow_symlinks=False)
    except OSError:
        return True
    return bool(getattr(st, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT)


def _iter_py() -> list[Path]:
    """FIX (wave5 suite-burn, 2026-09-29): the old `ROOT.rglob("*.py")` propagated
    OSError for the WHOLE audit when any path under ROOT vanished mid-walk or a
    reparse point dangled. Evidence: f-15 full-suite run 2026-09-28 -
    tests/test_ponytail_audit.py::test_run_audit_returns_schema and
    tests/test_skill_seat.py::test_ponytail_gate both died with
    "FileNotFoundError: [WinError ...]" while sibling runs' pytest tmp cleanup
    churned in-repo basetemp dirs (agents/pytest-tmp-<pid>; s2-19's own receipt
    records the twin: "PermissionError on the shared agents/pytest-tmp-21944
    during tmp rmtree, 2,403 errors"). rglob offers no per-entry tolerance, and
    it DESCENDS junctions (double-counting mirrored trees against B2-76 and
    crashing on dangling ones). os.walk with pruned SKIP_DIRS + reparse dirs and
    a no-raise onerror skips vanished/unreadable paths exactly the way
    _scan_large_files already skips vanished files (per-path `except OSError:
    continue`), so one raced path can no longer kill the audit.
    """
    out: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(ROOT, onerror=lambda _e: None):
        dp = Path(dirpath)
        rel = dp.relative_to(ROOT)
        if dp != ROOT and (set(rel.parts) & SKIP_DIRS):
            dirnames[:] = []
            continue
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not _reparse_dir(dp / d)]
        for fn in filenames:
            if not fn.endswith(".py"):
                continue
            p = dp / fn
            if _rel(p).startswith("tests/"):
                continue
            out.append(p)
    return sorted(out)


def _find_duplicate_constants() -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for name, paths in KNOWN_DUP_CONSTS:
        present = [p for p in paths if (ROOT / p).is_file()]
        defs = []
        for rel in present:
            text = (ROOT / rel).read_text(encoding="utf-8", errors="replace")
            if re.search(rf"^{name}\s*:", text, re.M):
                defs.append(rel)
        if len(defs) > 1:
            findings.append(
                {
                    "tag": "dup",
                    "what": f"{name} defined in multiple modules",
                    "replacement": "import from mag.router only",
                    "paths": defs,
                    "severity": "high",
                }
            )
        elif len(defs) == 1 and len(present) > 1:
            importers = [p for p in present if p not in defs]
            if importers:
                findings.append(
                    {
                        "tag": "dup",
                        "what": f"{name} — verify single definition",
                        "replacement": "import from mag.router",
                        "paths": present,
                        "severity": "low",
                    }
                )
    return findings


def _scan_large_files(files: list[Path]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for p in files:
        try:
            n = len(p.read_text(encoding="utf-8", errors="replace").splitlines())
        except OSError:
            continue
        if n >= SHRINK_THRESHOLD_LINES:
            out.append(
                {
                    "tag": "shrink",
                    "what": f"{n} lines",
                    "replacement": "split only when phase demands",
                    "path": _rel(p),
                    "severity": "low",
                }
            )
    return out


def _scan_yagni_wrappers(files: list[Path]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for p in files:
        if not _rel(p).startswith("mag/"):
            continue
        try:
            tree = ast.parse(p.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef) or len(node.body) != 1:
                continue
            body = node.body[0]
            if isinstance(body, ast.Return) and isinstance(body.value, ast.Call):
                if len(node.args.args) > 3:
                    continue
                out.append(
                    {
                        "tag": "yagni",
                        "what": f"wrapper `{node.name}`",
                        "replacement": "inline or delete",
                        "path": f"{_rel(p)}:{node.lineno}",
                        "severity": "low",
                    }
                )
    return out[:12]


def _scan_abandoned() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for needle, path, note in ABANDONED_MARKERS:
        fp = ROOT / path
        if fp.is_file() and needle in fp.read_text(encoding="utf-8", errors="replace"):
            out.append(
                {"tag": "delete", "what": needle, "replacement": note, "path": path, "severity": "low"}
            )
    return out


def _ladder_compliance() -> dict[str, Any]:
    required = [
        "mag/router.py", "mag/failure_kb.py", "mag/verkle_audit.py",
        "docs/ref/MAG_v2_PLAN.md", "docs/ref/lessig_1_6.md", "configs/modules.yaml",
    ]
    missing = [p for p in required if not (ROOT / p).is_file()]
    return {"ok": not missing, "missing": missing}


def _socratic_challenges(label: str, body: str) -> list[str]:
    """Socratic flow for an ungrounded doctrine — challenge to ground, never delete.
    Balanced: SOCRATES questions (Plato: define · Bernays: who benefits · Jung: what's under the
    ask) and DIOGENES punctures (parrhesia: blunt concrete truth over abstraction). End with ?"""
    t = (label or "this doctrine").strip()
    b = (body or "").strip()
    return [
        # SOCRATES — elenchus: define, evidence, who benefits, what's under it, refute it
        f"Socrates: what precisely does '{t}' assert, and what evidence would prove it?",
        f"Socrates: whose power or comfort is served by holding '{t}' without a source?",
        f"Socrates: what is the ask or fear that '{t}' protects ({b[:80]}...)?",
        f"Socrates: what would have to be true for '{t}' to be WRONG, and is that the case?",
        # DIOGENES — the Cynic cut: blunt, concrete, deflate the pretension
        f"Diogenes: show me the concrete thing '{t}' refers to, or it's a featherless biped.",
        f"Diogenes: strip the words — in one plain sentence, what does '{t}' actually DO?",
    ]


def _scan_grounding() -> list[dict[str, Any]]:
    """Frontier #6, ponytail style (Socratic flow, NOT delete): every folded doctrine's source must
    resolve to a real steal doc or known module; an ungrounded one is CHALLENGED (Socratic questions
    to ground or refute), never silently erased. Ponytail: verify don't assume. ~$0, reads graph + steal."""
    out: list[dict[str, Any]] = []
    try:
        import json as _json
        from mag.knowledge_graph import GRAPH_PATH
        steal_dir = ROOT / "memory" / "steal"
        known = {"session", "dream", "shadow_work", "shadow_work_session_test",
                 "shadow_work_session_specific", "frontier_advice", "memweave_internals"}
        docs = {p.stem.lower() for p in steal_dir.glob("*.md")} if steal_dir.is_dir() else set()
        if GRAPH_PATH.is_file():
            g = _json.loads(GRAPH_PATH.read_text(encoding="utf-8"))
            for n in g.get("nodes", []):
                src = str(n.get("source") or "").strip()
                if n.get("kind") != "doctrine":
                    continue
                label = str(n.get("label") or "?")
                body = str(n.get("summary") or "")
                q = _socratic_challenges(label, body)
                if not src:
                    out.append({"tag": "ungrounded", "what": f"doctrine '{label}' has no source",
                                "path": str(GRAPH_PATH).replace(str(ROOT), ""), "severity": "high",
                                "socratic": q,
                                "replacement": "Socratic flow: challenge to ground — do NOT delete"})
                    continue
                if src in known:
                    continue
                if any(src == d or src in d for d in docs):
                    continue
                out.append({"tag": "ungrounded",
                            "what": f"doctrine '{label}' source '{src}' matches no steal doc/module",
                            "path": str(GRAPH_PATH).replace(str(ROOT), ""), "severity": "medium",
                            "socratic": q,
                            "replacement": "Socratic flow: interrogate to find its source, or hold it as CHALLENGED — do NOT delete"})
    except Exception as e:
        out.append({"tag": "grounding", "what": f"grounding scan failed: {str(e)[:80]}",
                    "path": "mag/ponytail_audit.py", "severity": "low"})
    return out


def run_audit(*, hints: bool = False) -> dict[str, Any]:
    files = _iter_py()
    findings: list[dict[str, Any]] = []
    findings.extend(_find_duplicate_constants())
    findings.extend(_scan_abandoned())
    findings.extend(_scan_large_files(files))
    findings.extend(_scan_grounding())
    if hints:
        findings.extend(_scan_yagni_wrappers(files))

    sev_order = {"high": 0, "medium": 1, "low": 2}
    findings.sort(key=lambda f: (sev_order.get(f.get("severity", "low"), 9), f.get("tag", "")))
    lean = not any(f.get("severity") in ("high", "medium") for f in findings)

    return {
        "ok": True,
        "schema": SCHEMA,
        "lean": lean,
        "summary": "Lean already. Ship." if lean else f"{len(findings)} finding(s).",
        "files_scanned": len(files),
        "findings": findings,
        "ladder_compliance": _ladder_compliance(),
        "ponytail": "https://github.com/dietrichgebert/ponytail",
    }


def format_report(res: dict[str, Any]) -> str:
    if res.get("lean"):
        return str(res.get("summary"))
    lines = [str(res.get("summary")), ""]
    for f in res.get("findings") or []:
        path = f.get("path") or ",".join(f.get("paths") or [])
        lines.append(f"{f.get('tag')}: {f.get('what')}. {f.get('replacement')} [{path}]")
    lines.append(f"\nScanned {res.get('files_scanned', 0)} files.")
    return "\n".join(lines)
