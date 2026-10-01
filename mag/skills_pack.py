"""Progressive skill excerpts for context-pack (skills > MCP flood).

Fires one skill_fired.v1 receipt per skill actually returned by skills_for_job
(W3 2026-09-29, Mickey17 wave-3 lane, spec: MICKEY17_WAVE_LEDGER_20260929 return 16):
one logging point at the chokepoint so the catalog gains a fired column,
right_size gains demotion grounds, and bare verbs gain skill candidates.
"""
from __future__ import annotations

import fnmatch
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from config import CONFIGS_DIR, ROOT

CFG = CONFIGS_DIR / "skills.yaml"
SKILL_LEDGER = ROOT / "memory" / "improve" / "skill_ledger.jsonl"


def load_skills_cfg() -> dict[str, Any]:
    if not CFG.is_file():
        return {}
    return yaml.safe_load(CFG.read_text(encoding="utf-8")) or {}


def _resolve_path(rel: str) -> Path | None:
    if not rel:
        return None
    if rel.startswith("~/") or rel.startswith("~\\"):
        p = Path.home() / rel[2:]
    else:
        p = ROOT / rel
    return p if p.is_file() else None


def _clip_file(path: Path, n: int = 400) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    # first meaningful lines
    # 2026-09-29 W3 fix: the old predicate ended with `or ln.strip()`, which is
    # truthy for every non-blank line, so the # and ** checks never filtered
    # anything (no-op filter found by the Mickey17 wave-3 dig, ledger return 16;
    # proven filtered by tests/test_skill_fired.py). Keep only the skeleton
    # lines that carry a skill's shape: headings, bold-led lines, list items.
    lines = []
    for ln in text.splitlines():
        s = ln.strip()
        if s.startswith(("#", "**", "- ")):
            lines.append(ln)
        if sum(len(x) for x in lines) > n:
            break
    out = "\n".join(lines)[:n]
    return out


def _law_tail(path: Path, n: int = 5) -> str:
    """TOP-n oral laws by birth_count, one law per line (X6 2026-09-29).

    The deduped oral-law registry (watch/inbox/operator_model/ORAL_LAW_DEDUPED.jsonl,
    55 JSONL rows) is law clusters, not markdown: _clip_file has no ``#``/``**``/``-``
    skeleton lines to keep there, so it would return an empty body and the wiring
    would be dead. The excerpt is the top of the dedupe verdict instead: sort by
    (birth_count desc, rank asc) — birth_count is the operator's own dedupe weight —
    skip rows the dedupe marked ``superseded`` (dead law never ships into context;
    rank 26 carries a superseded note), and emit exactly n single-line laws.
    A 5-line tail, never the whole file. Receipt: watch/inbox/hydrology/X6_ORAL_WIRING.md
    """
    scored: list[tuple[tuple[int, float], str, int]] = []
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    for ln in raw.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            row = json.loads(ln)
        except ValueError:
            continue  # same tolerance as fired(): one bad row never kills the read
        if not isinstance(row, dict) or not row.get("canonical") or row.get("superseded"):
            continue
        bc = row.get("birth_count")
        bc = bc if isinstance(bc, int) else 0
        rank = row.get("rank")
        rk = float(rank) if isinstance(rank, (int, float)) else float("inf")
        scored.append(((-bc, rk), str(row["canonical"]), bc))
    scored.sort(key=lambda t: t[0])
    return "\n".join(f"- {can} (birth_count={bc})" for _, can, bc in scored[:n])


def _fire(skill_id: str, job: str, pack_mode: str, chars_injected: int) -> None:
    """Append one skill_fired.v1 receipt row to the shared skill ledger.

    Telemetry only: a ledger write failure must never break pack building
    (context_pack wraps this module in try/except anyway, so swallowing
    OSError here keeps the failure local and the pack intact).
    """
    row = {
        "schema": "skill_fired.v1",
        "skill_id": skill_id,
        "job": job,
        "pack_mode": pack_mode,  # excerpt = body clipped in; missing = path unresolved
        "chars_injected": chars_injected,  # chars this skill's chunk added to the pack build
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    try:
        SKILL_LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with SKILL_LEDGER.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError:
        pass


def fired(skill_id: str | None = None, *, path: Path | None = None) -> dict[str, int] | int:
    """Count skill_fired.v1 receipts per skill_id; int for a single skill_id.

    Reads only skill_fired.v1 rows, so decision.v1 rows in the same ledger
    file never inflate the counts.
    """
    p = path or SKILL_LEDGER
    counts: dict[str, int] = {}
    if p.is_file():
        with p.open("r", encoding="utf-8", errors="replace") as f:
            for ln in f:
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    row = json.loads(ln)
                except ValueError:
                    continue
                if row.get("schema") != "skill_fired.v1":
                    continue
                sid = str(row.get("skill_id") or "")
                if sid:
                    counts[sid] = counts.get(sid, 0) + 1
    if skill_id is not None:
        return counts.get(skill_id, 0)
    return counts


# ---------------------------------------------------------------------------
# Per-skill path permissions (W3P 2026-09-29, Mickey17 wave-3 lane).
#
# Seed: the S12 Kilo steal (watch/inbox/MICKEY17_WAVE_LEDGER_20260929.md,
# agent ca7ff8d5) — modes carry ORDERED glob permission lists where the LAST
# matching rule wins (Kilo spells it `deny-* allow-*.md`). Our v0 keeps the
# two match axes that matter: mode ("read"/"write") and last-match-wins
# ordering with a `deny-` prefix to flip a glob to a deny. Kilo's
# visibility axis (primary/subagent) is intentionally NOT v0 — it needs an
# invoker concept this registry does not have yet.
#
# ADVISORY v0: check() is a standalone helper. NOTHING in the harness calls
# it — skills_for_job still packs excerpts without asking permissions, and no
# effect broker consults it. Wiring enforcement anywhere is a separate law
# change (receipt: watch/inbox/W3P_SKILL_GLOBS.md).
# ---------------------------------------------------------------------------

#: Rules read `deny-<glob>` as a deny; anything else is an allow glob.
DENY_PREFIX = "deny-"


def _norm_perm_path(path: str) -> str:
    """Normalize a path for permission matching: forward slashes, repo-relative.

    Windows backslashes and a leading ``./`` are folded away; an absolute path
    under ROOT becomes repo-relative so callers may pass either form. Paths
    outside ROOT keep their absolute shape (they simply won't match
    repo-relative globs — fail-closed by construction).
    """
    p = str(path).replace("\\", "/").strip()
    if len(p) >= 2 and p[1] == ":":
        try:
            p = Path(p).resolve().relative_to(ROOT).as_posix()
        except ValueError:
            return p
    while p.startswith("./"):
        p = p[2:]
    return p.lstrip("/")


def check(skill_id: str, path: str, mode: str, *, cfg: dict[str, Any] | None = None) -> bool:
    """Return True only if the LAST matching permission rule allows the path.

    Semantics (S12 Kilo steal, v0):
      - rules are an ordered list of repo-relative globs under
        ``permissions.<mode>`` in configs/skills.yaml, e.g.
        ``write: ["watch/inbox/**"]``;
      - a rule prefixed ``deny-`` denies its glob, everything else allows;
      - LAST-MATCH-WINS: the final rule whose glob matches the path decides
        (so ``["*", "deny-corpus/steal/**"]`` allows all but corpus/steal);
      - FAIL-CLOSED: unknown skill_id, no ``permissions`` field, no list for
        that mode, empty list, or no matching rule => REJECTED (False).
        Unlisted is untrusted, never implicitly allowed.

    Matching is fnmatch.fnmatchcase: ``*`` crosses ``/`` (so ``**`` and a
    bare ``*`` both span directories at v0 — documented, not gitignore
    semantics). Advisory only; see module block above.
    """
    if cfg is None:
        cfg = load_skills_cfg()
    perms: Any = None
    for s in cfg.get("skills") or []:
        if isinstance(s, dict) and s.get("id") == skill_id:
            perms = s.get("permissions")
            break
    if not isinstance(perms, dict):
        return False
    rules = perms.get(mode)
    if not isinstance(rules, list) or not rules:
        return False
    p = _norm_perm_path(path)
    decided: bool | None = None
    for rule in rules:
        r = str(rule).strip()
        if not r:
            continue
        deny = r.startswith(DENY_PREFIX)
        glob = r[len(DENY_PREFIX):] if deny else r
        if glob and fnmatch.fnmatchcase(p, glob):
            decided = not deny
    return decided is True


def skills_for_job(job: str, *, max_chars: int = 800) -> str:
    cfg = load_skills_cfg()
    job_map = cfg.get("job_to_skills") or {}
    skill_ids = list(job_map.get(job) or job_map.get("default") or [])
    if not skill_ids:
        return ""
    by_id = {s.get("id"): s for s in (cfg.get("skills") or []) if isinstance(s, dict)}
    chunks: list[str] = []
    memory_rule = (cfg.get("memory_rule") or "").strip()
    if memory_rule:
        chunks.append("memory_rule: " + " ".join(memory_rule.split())[:200])
    budget = max_chars
    for sid in skill_ids:
        spec = by_id.get(sid) or {}
        if not spec.get("pack_excerpt", True):
            continue
        path = _resolve_path(str(spec.get("path") or ""))
        if not path:
            chunks.append(f"- {sid}: (path missing)")
            _fire(sid, job, "missing", 0)
            continue
        take = min(280, max(80, budget // max(1, len(skill_ids))))
        # X6 2026-09-29: a .jsonl law registry excerpts as the TOP-5-law tail
        # (birth_count-ranked), not clipped markdown — _clip_file keeps only
        # markdown skeleton lines and JSONL has none.
        if path.suffix.lower() == ".jsonl":
            body = _law_tail(path)
        else:
            body = _clip_file(path, take)
        chunk = f"### {sid}\n{body}"
        chunks.append(chunk)
        budget -= len(body)
        _fire(sid, job, "excerpt", len(chunk))
        if budget < 50:
            break
    text = "\n\n".join(chunks)
    return text[:max_chars]
