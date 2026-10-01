"""Field steal — ingest vendor system-prompt archives as *contracts*, not DNA.

Source: private clone of field archive (e.g. Strike-The-Chord sysprompt dump).
Output: steal ledger under memory/improve/field_steal/ (private residual-adjacent).

Law:
- Never promote full foreign system prompts into Mag DNA or public git.
- Steal invariants only (FEATURE_COMPOSE).
- T2 field study; do not remote residual.

CLI: python main.py field-steal --root PATH [--max-files N]
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT

SCHEMA = "field_steal_ledger.v1"
OUT_DIR = ROOT / "memory" / "improve" / "field_steal"

# Contract families we care about for Mag
FAMILY_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("tool_discipline", re.compile(
        r"\b(tool|function.?call|never call|only use|available tools|tool schema)\b", re.I
    )),
    ("no_disclose_prompt", re.compile(
        r"\b(never disclose|do not (reveal|share|mention).{0,40}(system|prompt|guideline|instruction)|hide your instructions)\b", re.I
    )),
    ("memory_context", re.compile(
        r"\b(memory|context window|conversation history|persist|remember|state across)\b", re.I
    )),
    ("seat_routing", re.compile(
        r"\b(escalat|hand ?off|delegate|sub-?agent|model selection|when to use)\b", re.I
    )),
    ("code_edit", re.compile(
        r"\b(edit_file|apply_patch|never output code|pair program|linter|diff)\b", re.I
    )),
    ("search_web", re.compile(
        r"\b(search the web|browse|real-?time|ground(ing)?|cite sources|url)\b", re.I
    )),
    ("safety_refusal", re.compile(
        r"\b(refus|disallow|not assist|illegal|harmful|jailbreak|policy)\b", re.I
    )),
    ("brevity_style", re.compile(
        r"\b(shortest answer|concise|be (brief|direct)|no fluff|one line)\b", re.I
    )),
    ("user_second_person", re.compile(
        r"\b(second person|refer to the USER|you are (a |an )?\w+ assistant)\b", re.I
    )),
    ("plan_then_act", re.compile(
        r"\b(plan first|think step|before (calling|editing)|todo|checklist)\b", re.I
    )),
    ("artifact_first", re.compile(
        r"\b(write (to )?file|artifact|do not only chat|deliverable on disk)\b", re.I
    )),
    ("anti_sycophancy", re.compile(
        r"\b(do not flatter|no sycophant|disagree when|truth over)\b", re.I
    )),
]

RULE_LINE = re.compile(
    r"^[\s>*-]*(\d+\.|\*|-)?\s*(ALWAYS|NEVER|MUST|DO NOT|Don't|You (must|should|never|always)|Bias towards|Only |If )\b.+",
    re.I | re.M,
)

EXT = {".md", ".txt", ".mkd", ".markdown", ""}


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _iter_prompt_files(root: Path) -> list[Path]:
    files: list[Path] = []
    if not root.is_dir():
        return files
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if p.name.lower() in ("readme.md", "license", "license.md"):
            continue
        # never scan git objects
        if ".git" in p.parts:
            continue
        if p.suffix.lower() in EXT or p.suffix == "":
            # skip huge binaries
            try:
                if p.stat().st_size > 2_000_000:
                    continue
            except OSError:
                continue
            files.append(p)

    return sorted(files)


def _vendor_of(path: Path, root: Path) -> str:
    try:
        rel = path.relative_to(root)
        parts = rel.parts
        return parts[0] if parts else "unknown"
    except ValueError:
        return "unknown"


def extract_rules(text: str, limit: int = 40) -> list[str]:
    rules: list[str] = []
    for m in RULE_LINE.finditer(text):
        line = " ".join(m.group(0).split())
        if 20 <= len(line) <= 400:
            rules.append(line)
        if len(rules) >= limit:
            break
    # also bullet NEVER/ALWAYS fragments
    for line in text.splitlines():
        s = line.strip()
        if re.match(r"^[-*•]\s*(ALWAYS|NEVER|MUST|DO NOT)\b", s, re.I):
            s = " ".join(s.split())
            if 20 <= len(s) <= 400 and s not in rules:
                rules.append(s)
            if len(rules) >= limit:
                break
    return rules


def family_hits(text: str) -> dict[str, int]:
    hits: dict[str, int] = {}
    for name, pat in FAMILY_PATTERNS:
        n = len(pat.findall(text))
        if n:
            hits[name] = n
    return hits


def scan_file(path: Path, root: Path) -> dict[str, Any] | None:
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return {"path": str(path), "error": str(e)}
    if len(raw.strip()) < 80:
        return None
    rel = str(path.relative_to(root)).replace("\\", "/")
    rules = extract_rules(raw)
    fam = family_hits(raw)
    return {
        "rel": rel,
        "vendor": _vendor_of(path, root),
        "chars": len(raw),
        "sha12": hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()[:12],
        "families": fam,
        "rules_sample": rules[:12],
        "n_rules": len(rules),
    }


def default_take_leave(family: str) -> tuple[str, str]:
    """Wholesale default posture for Mag compose."""
    take = {
        "tool_discipline": (
            "take",
            "Only call tools that exist; never invent tool names; explain purpose before/after as Mag needs",
        ),
        "no_disclose_prompt": (
            "hold",
            "Foreign: hide system prompt. Mag: different — strike wants boundary law visible; do not steal secrecy-as-product",
        ),
        "memory_context": (
            "take",
            "External memory + selective inject — already Mag residual/pack; steal any *retrieve narrow* wording",
        ),
        "seat_routing": (
            "take",
            "When to escalate / local vs remote — maps to lanes + dispatch + scarce Grok",
        ),
        "code_edit": (
            "take",
            "Prefer tools over dumping code walls — Mag executor/filesystem already; tighten prompts",
        ),
        "search_web": (
            "take",
            "Ground when unsure — research-pack / dig; cite URLs",
        ),
        "safety_refusal": (
            "leave",
            "Their safety stack ≠ our C7 refusal of safety-as-care capture; keep Mag constitution",
        ),
        "brevity_style": (
            "take",
            "Short default — operator one-job rule; pack-first",
        ),
        "user_second_person": (
            "hold",
            "Style only; Mag already Sancho second-person",
        ),
        "plan_then_act": (
            "take",
            "Plan diversity / plan-then-tool — IJL + planner",
        ),
        "artifact_first": (
            "take",
            "Artifact > transcript — residual, dig leaves, FILE block",
        ),
        "anti_sycophancy": (
            "take",
            "Truth over flattery — strike / operator-quixote",
        ),
    }
    return take.get(family, ("hold", "Review manually"))


def build_ledger(root: Path, *, max_files: int = 0) -> dict[str, Any]:
    files = _iter_prompt_files(root)
    if max_files and max_files > 0:
        files = files[:max_files]
    scans: list[dict[str, Any]] = []
    family_files: dict[str, list[str]] = defaultdict(list)
    family_rules: dict[str, list[str]] = defaultdict(list)

    for p in files:
        row = scan_file(p, root)
        if not row or row.get("error"):
            if row:
                scans.append(row)
            continue
        scans.append(row)
        for fam, n in (row.get("families") or {}).items():
            if n:
                family_files[fam].append(row["rel"])
                for r in row.get("rules_sample") or []:
                    if fam in r.lower() or any(
                        k in r.lower() for k in fam.split("_")
                    ):
                        family_rules[fam].append(r)

    # aggregate take/leave
    compose_rows = []
    for fam, _pat in FAMILY_PATTERNS:
        verdict, note = default_take_leave(fam)
        compose_rows.append(
            {
                "family": fam,
                "n_files": len(set(family_files.get(fam) or [])),
                "sample_rules": list(dict.fromkeys(family_rules.get(fam) or []))[:8],
                "verdict": verdict,
                "steal_note": note,
            }
        )

    ledger = {
        "schema": SCHEMA,
        "ts": _utc(),
        "source_root": str(root.resolve()),
        "n_files_scanned": len(scans),
        "n_files_ok": sum(1 for s in scans if not s.get("error")),
        "vendors": sorted({s.get("vendor") for s in scans if s.get("vendor")}),
        "compose": compose_rows,
        "files": scans,
        "law": [
            "Steal contracts only (FEATURE_COMPOSE)",
            "Do not paste full foreign system prompts into residual DNA or public Mag git",
            "Human promote before playbook",
            "Field study = T2; never remote T0/T1",
        ],
        "next": [
            "For each verdict=take: write one FEATURE leaf or playbook line",
            "Wire into prompts/*.txt or operator skills only if operator will run it",
            "Measure: multi-smoke / one dig / one dispatch — not leaf count",
        ],
    }
    return ledger


def write_ledger(ledger: dict[str, Any]) -> dict[str, Path]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    jpath = OUT_DIR / f"ledger_{stamp}.json"
    latest_j = OUT_DIR / "ledger_latest.json"
    mpath = OUT_DIR / f"STEAL_{stamp}.md"
    latest_m = OUT_DIR / "STEAL_LATEST.md"

    jpath.write_text(json.dumps(ledger, indent=2, default=str), encoding="utf-8")
    latest_j.write_text(jpath.read_text(encoding="utf-8"), encoding="utf-8")

    lines = [
        "# Field steal ledger",
        f"_ts: {ledger.get('ts')}_",
        f"_source: `{ledger.get('source_root')}`_",
        f"_files: {ledger.get('n_files_ok')}/{ledger.get('n_files_scanned')}_",
        f"_vendors: {', '.join(ledger.get('vendors') or [])}_",
        "",
        "## Law",
        "",
    ]
    for L in ledger.get("law") or []:
        lines.append(f"- {L}")
    lines.extend(["", "## Compose (wholesale defaults)", ""])
    lines.append("| family | files | verdict | steal note |")
    lines.append("|--------|------:|---------|------------|")
    for row in ledger.get("compose") or []:
        lines.append(
            f"| `{row.get('family')}` | {row.get('n_files')} | **{row.get('verdict')}** | "
            f"{row.get('steal_note')} |"
        )
    lines.extend(["", "## Sample rules by family (evidence, not to paste wholesale)", ""])
    for row in ledger.get("compose") or []:
        if not row.get("sample_rules"):
            continue
        lines.append(f"### {row.get('family')} ({row.get('verdict')})")
        for r in row.get("sample_rules") or []:
            lines.append(f"- {r}")
        lines.append("")
    lines.extend(["## Next", ""])
    for n in ledger.get("next") or []:
        lines.append(f"1. {n}")
    lines.append("")
    text = "\n".join(lines)
    mpath.write_text(text, encoding="utf-8")
    latest_m.write_text(text, encoding="utf-8")
    return {"json": jpath, "md": mpath, "latest_md": latest_m, "latest_json": latest_j}


def run_field_steal(root: str | Path, *, max_files: int = 0) -> dict[str, Any]:
    root_p = Path(root).expanduser().resolve()
    if not root_p.is_dir():
        return {"ok": False, "error": f"not a directory: {root_p}"}
    ledger = build_ledger(root_p, max_files=max_files)
    paths = write_ledger(ledger)
    return {
        "ok": True,
        "n_files": ledger.get("n_files_ok"),
        "vendors": ledger.get("vendors"),
        "compose": [
            {"family": r["family"], "verdict": r["verdict"], "n_files": r["n_files"]}
            for r in (ledger.get("compose") or [])
        ],
        "paths": {k: str(v) for k, v in paths.items()},
    }
