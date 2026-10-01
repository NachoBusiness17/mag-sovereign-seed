"""prompt_lance — PYLANCE FOR THE PROMPT (deterministic prompt/context diagnostics memtools).

OPERATOR GENESIS: steering began as reading in-process state to steer slow local models
(ghost_pylance reads CODE state; ghost_memlance reads MEMORY state). The missing organ is
the same deterministic lens pointed at WHAT THE MODEL WAS ACTUALLY FED: the context window
as the codebase, the prompt as the module. A specialist seat can burn scarce remote
inference on a prompt that is quietly broken (duplicated blocks, stale dates, placeholder
leakage, self-contradiction, budget overrun); prompt_lance catches those with stdlib
heuristics, $0, before the ask is spent.

STEAL ANALYSIS:
  * SELF — the shape is ghost_pylance (diagnose / symbols / references / self_check) lifted
    from code bytes to PROMPT bytes. provenance() is trace_value flipped around: instead of
    "how did this value get set", it asks "what artifacts does this context CLAIM to draw
    from" — a verifiable inventory the caller checks against disk, never trusting the
    prompt's own say-so.
  * EXTERNAL — linter/Pylance discipline: diagnostics are deterministic, severity-ranked,
    located (line numbers), and never silently pass a broken input. Same contract here,
    no prompt DNA, no model calls, no network.

MEMTOOLS (the prompt-intelligence organs):
  diagnose(ctx)           - structural diagnostics: near-dup blocks (shingle overlap),
                            empty/near-empty sections, repeated system-reminder bodies,
                            contradiction markers (same subject, opposing polarity), stale
                            dates (older than N days), placeholder leakage (TODO / FIXME /
                            <placeholder> / YOUR_API_KEY shapes), token-budget overrun
                            (chars/4 heuristic).
  symbols(ctx)            - the section map: markdown headers, fenced-code inventory with
                            languages, valid JSON blobs.
  references(ctx, needle) - every occurrence of a needle with line + excerpt (like Pylance
                            references; case-insensitive over prompt bytes).
  provenance(ctx)         - provenance inventory: paths + hex hashes the context CLAIMS to
                            draw from; the ground-truth side the caller verifies on disk.
  self_check(ctx)         - one-line verdict: CLEAN or "N findings; worst=..." worst-first.

ctx accepts a raw str OR a list of message dicts ({role, content}); findings locate into
msg[i:role] blocks when message dicts are given. Deterministic: the same input bytes (plus
the injectable `today` used by the stale check) give byte-identical output dicts.

Schema: prompt_lance.v1 · deterministic $0 · CLI: python -m mag.prompt_lance <tool> <file|->
"""
from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCHEMA = "prompt_lance.v1"

_SEV_RANK = {"high": 3, "warn": 2, "info": 1}

# caps per check (deterministic truncation, ghost_pylance slice style)
_CAP_DUP = 20
_CAP_EMPTY = 20
_CAP_REMINDER = 10
_CAP_CONTRA = 10
_CAP_STALE = 40
_CAP_PLACEHOLDER = 30

# near-dup: word 3-gram shingles, containment of later paragraph in earlier
_DUP_SHINGLES = 3
_DUP_MIN_WORDS = 4
_DUP_CONTAINMENT = 0.8

# a section body under a header with fewer non-blank chars than this is near-empty
_EMPTY_SECTION_CHARS = 4

# stale dates: ISO year-month-day in text older than stale_days vs `today`
_DATE_RE = re.compile(r"\b(20\d{2})-(\d{2})-(\d{2})\b")

# repeated system-reminder detection: XML-style bodies + plain-style lines
_REMINDER_BODY_RE = re.compile(r"<system-reminder>(.*?)</system-reminder>", re.S | re.I)
_REMINDER_LINE_RE = re.compile(r"^\s*(?:[#>*\-]+\s*)?system-reminder\b.*$", re.I)

# contradiction markers: small opposing-polarity keyword lists (checked per line; the
# negative list wins so "is not" is not also counted as positive "is")
_NEG_MARKERS = (
    "is not", "isn't", "are not", "aren't", "was not", "weren't", "must not",
    "cannot", "can't", "can not", "will not", "won't", "should not", "shouldn't",
    "shall not", "never", "neither", "nor", "disabled", "forbidden", "unsupported",
    "false",
)
_POS_MARKERS = (
    "always", "is", "are", "was", "must", "can", "will", "shall", "should",
    "enabled", "required", "supported", "true", "does",
)
_NEG_RE = re.compile(r"\b(?:%s)\b" % "|".join(re.escape(m) for m in _NEG_MARKERS))
_POS_RE = re.compile(r"\b(?:%s)\b" % "|".join(re.escape(m) for m in _POS_MARKERS))
_SUBJECT_RE = re.compile(r"^\s*(?:[#>*\-+]+|\d+[.)])*\s*([A-Za-z][A-Za-z0-9_\-]*)")
_SUBJECT_STOP = frozenset({
    "the", "a", "an", "this", "that", "these", "those", "it", "its", "we", "you",
    "they", "he", "she", "if", "and", "but", "or", "so", "to", "in", "on", "for",
    "of", "is", "are", "was", "were", "not", "no", "yes", "always", "never",
    "when", "then", "do", "does", "did", "with", "by", "as", "at", "be", "been",
    "has", "have", "had", "there", "here", "what", "which", "who", "how", "why",
    "all", "any", "some", "each", "every",
})

# placeholder leakage shapes (case-insensitive unless noted)
_PLACEHOLDER_RES = (
    (re.compile(r"\bTODO\b"), "TODO marker"),
    (re.compile(r"\bFIXME\b"), "FIXME marker"),
    (re.compile(r"\bXXX\b"), "XXX marker"),
    (re.compile(r"<placeholder>", re.I), "<placeholder> tag"),
    (re.compile(r"\bYOUR_API_KEY\b"), "API-key placeholder"),
    (re.compile(r"<your[_a-z0-9\-]*>", re.I), "<your_*> placeholder tag"),
    (re.compile(r"\b[A-Z_]*PLACEHOLDER[A-Z_]*\b"), "PLACEHOLDER token"),
)

# provenance: paths + hex-hash shapes the context claims to draw from
_UNIX_PATH_RE = re.compile(r"(?<![\w./\-])[A-Za-z0-9_.\-]+(?:/[A-Za-z0-9_.\-]+)+(?![\w./\-])")
_WIN_PATH_RE = re.compile(r"\b[A-Za-z]:\\(?:[^\s\\/:*?\"<>|]+\\)*[^\s\\/:*?\"<>|]+")
_HEX_RE = re.compile(r"(?<![0-9A-Fa-f])[0-9A-Fa-f]{7,64}(?![0-9A-Fa-f])")
_URL_RE = re.compile(r"[A-Za-z][A-Za-z0-9+.\-]*://\S+")
_PATH_ROOTS = (
    "mag/", "docs/", "tests/", "tools/", "scripts/", "configs/", "watch/",
    "memory/", "queue/", "corpus/", "state/", "harness/", "router/", "backend/",
    "githooks/", ".agents/", ".venv/",
)


def _normalize(ctx: Any) -> tuple[str, list[dict[str, Any]]]:
    """Normalize ctx (str or message dicts) to text + block map (1-based line ranges)."""
    if isinstance(ctx, str):
        return ctx.replace("\r\n", "\n").replace("\r", "\n"), []
    if isinstance(ctx, dict):
        ctx = [ctx]
    blocks: list[dict[str, Any]] = []
    parts: list[str] = []
    line_no = 0
    for i, m in enumerate(ctx or []):
        role = str(m.get("role", "unknown")) if isinstance(m, dict) else "unknown"
        content = m.get("content", "") if isinstance(m, dict) else m
        if not isinstance(content, str):
            content = json.dumps(content, sort_keys=True, default=str)
        content = content.replace("\r\n", "\n").replace("\r", "\n")
        if parts:
            parts.append("")
            line_no += 1
        start0 = line_no
        parts.append(content)
        n_lines = content.count("\n") + 1
        line_no = start0 + n_lines
        blocks.append({"index": i, "role": role, "start": start0 + 1, "end": line_no})
    return "\n".join(parts), blocks


def _where(blocks: list[dict[str, Any]], line: int) -> str:
    for b in blocks:
        if b["start"] <= line <= b["end"]:
            return f"msg[{b['index']}:{b['role']}] L{line}"
    return f"L{line}"


def _fence_lines(lines: list[str]) -> set[int]:
    """Line numbers (1-based) inside fenced code blocks (inclusive of fence markers)."""
    inside: set[int] = set()
    open_line = 0
    for i, ln in enumerate(lines, 1):
        if ln.lstrip().startswith("```"):
            if not open_line:
                open_line = i
                inside.add(i)
            else:
                inside.update(range(open_line, i + 1))
                open_line = 0
        elif open_line:
            inside.add(i)
    if open_line:  # unterminated fence runs to EOF
        inside.update(range(open_line, len(lines) + 1))
    return inside


def _line_of(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _paragraphs(lines: list[str]) -> list[tuple[int, int, str]]:
    """Non-blank line groups as (start_line, end_line, text), in document order."""
    out: list[tuple[int, int, str]] = []
    cur: list[str] = []
    start = 0
    for i, ln in enumerate(lines, 1):
        if ln.strip():
            if not cur:
                start = i
            cur.append(ln)
        elif cur:
            out.append((start, i - 1, "\n".join(cur)))
            cur = []
    if cur:
        out.append((start, len(lines), "\n".join(cur)))
    return out


def _shingles(text: str) -> frozenset:
    words = re.findall(r"[a-z0-9]+", text.lower())
    if len(words) >= _DUP_SHINGLES:
        return frozenset(tuple(words[i:i + _DUP_SHINGLES])
                         for i in range(len(words) - _DUP_SHINGLES + 1))
    norm = " ".join(words)
    return frozenset({norm}) if norm else frozenset()


def _check_dups(lines: list[str], blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Near-dup paragraph detection: word-shingle containment of a later paragraph in an
    earlier one (deterministic document-order scan, each later paragraph charged once)."""
    findings: list[dict[str, Any]] = []
    # candidate paragraphs: enough words to be meaningful; a bare single-line markdown
    # header is a section marker, not duplicated content
    paras = [p for p in _paragraphs(lines)
             if len(re.findall(r"[a-z0-9]+", p[2].lower())) >= _DUP_MIN_WORDS
             and not (p[2].lstrip().startswith("#") and "\n" not in p[2])]
    sh = [_shingles(p[2]) for p in paras]
    for j in range(len(paras)):
        if not sh[j]:
            continue
        for i in range(j):
            if not sh[i]:
                continue
            denom = len(sh[j])
            overlap = len(sh[j] & sh[i]) / denom
            if overlap >= _DUP_CONTAINMENT:
                pct = round(100 * overlap)
                findings.append({
                    "code": "PROMPT_DUP_BLOCK", "severity": "warn",
                    "line": paras[j][0],
                    "where": (f"L{paras[j][0]}-L{paras[j][1]}" if paras[j][1] > paras[j][0]
                              else f"L{paras[j][0]}"),
                    "note": (f"near-dup of L{paras[i][0]} ({pct}% shingle containment); "
                             f"duplicated context burns budget without adding signal"),
                })
                break
        if len(findings) >= _CAP_DUP:
            break
    return findings


def _check_empty_sections(lines: list[str], blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Empty / near-empty markdown sections (needs >= 2 headers so a section is a section)."""
    headers = [(i, ln.lstrip("#").strip()) for i, ln in enumerate(lines, 1)
               if re.match(r"^\s*#{1,6}\s+\S", ln)]
    if len(headers) < 2:
        return []
    findings: list[dict[str, Any]] = []
    for k, (hline, htext) in enumerate(headers):
        end = headers[k + 1][0] - 1 if k + 1 < len(headers) else len(lines)
        body_chars = sum(len(ln.strip()) for ln in lines[hline:end])
        if body_chars < _EMPTY_SECTION_CHARS:
            findings.append({
                "code": "PROMPT_EMPTY_SECTION", "severity": "info",
                "line": hline, "where": f"L{hline}",
                "note": f"section '{htext[:60]}' has no body (near-empty section)",
            })
            if len(findings) >= _CAP_EMPTY:
                break
    return findings


def _check_reminders(text: str, lines: list[str],
                     blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Repeated system-reminder content: identical reminder bodies injected more than once."""
    findings: list[dict[str, Any]] = []
    bodies: dict[str, list[int]] = {}
    for m in _REMINDER_BODY_RE.finditer(text):
        norm = re.sub(r"\s+", " ", m.group(1)).strip().lower()
        if norm:
            bodies.setdefault(norm, []).append(_line_of(text, m.start()))
    for norm, lns in sorted(bodies.items()):
        if len(lns) >= 2:
            findings.append({
                "code": "PROMPT_REPEATED_REMINDER", "severity": "warn",
                "line": lns[1], "where": _where(blocks, lns[1]),
                "note": f"system-reminder body repeated x{len(lns)} (first L{lns[0]}): "
                        f"'{norm[:80]}'",
            })
            if len(findings) >= _CAP_REMINDER:
                break
    if findings:
        return findings
    plain: dict[str, list[int]] = {}
    for i, ln in enumerate(lines, 1):
        if _REMINDER_LINE_RE.match(ln):
            plain.setdefault(ln.strip().lower(), []).append(i)
    for norm, lns in sorted(plain.items()):
        if len(lns) >= 2:
            findings.append({
                "code": "PROMPT_REPEATED_REMINDER", "severity": "warn",
                "line": lns[1], "where": _where(blocks, lns[1]),
                "note": f"system-reminder line repeated x{len(lns)} (first L{lns[0]}): "
                        f"'{norm[:80]}'",
            })
            if len(findings) >= _CAP_REMINDER:
                break
    return findings


def _check_contradictions(lines: list[str], fence: set[int],
                          blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Contradiction markers: same sentence-start subject carrying opposing polarity on
    different lines (simple deterministic floor, prose lines only, fenced code skipped)."""
    seen: dict[str, list[tuple[int, int]]] = {}
    for i, ln in enumerate(lines, 1):
        if i in fence:
            continue
        m = _SUBJECT_RE.match(ln)
        if not m:
            continue
        subj = m.group(1).lower()
        if subj in _SUBJECT_STOP:
            continue
        low = ln.lower()
        pol = -1 if _NEG_RE.search(low) else (1 if _POS_RE.search(low) else 0)
        if pol:
            seen.setdefault(subj, []).append((pol, i))
    findings: list[dict[str, Any]] = []
    for subj in sorted(seen):
        rows = seen[subj]
        pos = [r for r in rows if r[0] > 0]
        neg = [r for r in rows if r[0] < 0]
        if pos and neg:
            a, b = pos[0][1], neg[0][1]
            findings.append({
                "code": "PROMPT_CONTRADICTION", "severity": "high",
                "line": min(a, b), "where": f"{_where(blocks, a)} + {_where(blocks, b)}",
                "note": f"subject '{subj}' asserted with opposing polarity "
                        f"(affirmative L{a} vs negative L{b})",
            })
            if len(findings) >= _CAP_CONTRA:
                break
    return findings


def _check_stale(lines: list[str], blocks: list[dict[str, Any]], today: date,
                 stale_days: int) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for i, ln in enumerate(lines, 1):
        for m in _DATE_RE.finditer(ln):
            try:
                d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            except ValueError:
                continue
            age = (today - d).days
            if age > stale_days:
                findings.append({
                    "code": "PROMPT_STALE_DATE", "severity": "warn",
                    "line": i, "where": _where(blocks, i),
                    "note": f"date {m.group(0)} is {age}d old (> {stale_days}d) - stale "
                            f"marker carried into the prompt",
                })
                if len(findings) >= _CAP_STALE:
                    return findings
    return findings


def _check_placeholders(text: str, blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for rx, shape in _PLACEHOLDER_RES:
        for m in rx.finditer(text):
            ln = _line_of(text, m.start())
            findings.append({
                "code": "PROMPT_PLACEHOLDER", "severity": "high",
                "line": ln, "where": _where(blocks, ln),
                "note": f"{shape} '{m.group(0)}' leaked into the prompt",
            })
            if len(findings) >= _CAP_PLACEHOLDER:
                return findings
    return findings


def diagnose(ctx: Any, *, budget_tokens: int = 0, stale_days: int = 30,
             today: date | None = None) -> dict[str, Any]:
    """Structural diagnostics over the prompt/context under test.

    ctx: raw str or list of {role, content} message dicts.
    budget_tokens: flag a chars/4 overrun above this (0 disables the check).
    stale_days / today: a date in the text older than stale_days vs `today` is stale
    (today injectable for deterministic tests; defaults to the real today).
    """
    text, blocks = _normalize(ctx)
    lines = text.splitlines()
    fence = _fence_lines(lines)
    today = today or date.today()
    findings: list[dict[str, Any]] = []
    findings += _check_dups(lines, blocks)
    findings += _check_empty_sections(lines, blocks)
    findings += _check_reminders(text, lines, blocks)
    findings += _check_contradictions(lines, fence, blocks)
    findings += _check_stale(lines, blocks, today, stale_days)
    findings += _check_placeholders(text, blocks)
    est_tokens = (len(text) // 4) if text else 0
    if budget_tokens > 0 and est_tokens > budget_tokens:
        findings.append({
            "code": "PROMPT_BUDGET_OVERRUN", "severity": "high",
            "line": 1, "where": f"L1-L{max(1, len(lines))}",
            "note": f"est {est_tokens} tokens (chars/4) > budget {budget_tokens} - the ask "
                    f"overruns its context budget",
        })
    findings.sort(key=lambda f: (-_SEV_RANK.get(f["severity"], 0), f["code"], f["line"]))
    return {"ok": True, "schema": SCHEMA, "n_chars": len(text), "n_lines": len(lines),
            "est_tokens": est_tokens, "n_findings": len(findings), "findings": findings}


def symbols(ctx: Any) -> dict[str, Any]:
    """Section map: markdown headers, fenced-code blocks (with languages), JSON blobs."""
    text, _ = _normalize(ctx)
    lines = text.splitlines()
    headers = []
    code_blocks = []
    fence_ranges: list[tuple[int, int]] = []
    open_start = 0
    open_lang = ""
    for i, ln in enumerate(lines, 1):
        stripped = ln.lstrip()
        if stripped.startswith("```"):
            if not open_start:
                open_start = i
                tok = stripped[3:].strip().split()
                open_lang = tok[0] if tok else ""
            else:
                code_blocks.append({"start": open_start, "end": i, "lang": open_lang})
                fence_ranges.append((open_start, i))
                open_start = 0
                open_lang = ""
        m = re.match(r"^\s*(#{1,6})\s+(\S.*)$", ln)
        if m and not open_start:
            headers.append({"line": i, "level": len(m.group(1)),
                            "text": m.group(2).strip()[:120]})
    if open_start:  # unterminated fence
        code_blocks.append({"start": open_start, "end": len(lines), "lang": open_lang})
        fence_ranges.append((open_start, len(lines)))
    json_blobs = []
    for start, end, ptext in _paragraphs(lines):
        if any(fs <= start and end <= fe for fs, fe in fence_ranges):
            continue
        s = ptext.strip()
        if s[:1] in "{[":
            try:
                json.loads(s)
            except Exception:
                continue
            json_blobs.append({"line": start, "n_bytes": len(s)})
    return {"ok": True, "schema": SCHEMA, "n_lines": len(lines), "n_chars": len(text),
            "n_headers": len(headers), "headers": headers,
            "n_code_blocks": len(code_blocks), "code_blocks": code_blocks,
            "n_json_blobs": len(json_blobs), "json_blobs": json_blobs}


def references(ctx: Any, needle: str, *, limit: int = 200) -> dict[str, Any]:
    """Every occurrence of `needle` in the prompt bytes with line + excerpt (like Pylance
    references; case-insensitive, multiple hits per line counted)."""
    if not needle:
        return {"ok": False, "schema": SCHEMA, "error": "no needle given"}
    text, _ = _normalize(ctx)
    low = text.lower()
    target = needle.lower()
    hits: list[dict[str, Any]] = []
    src_lines = text.splitlines()
    start = 0
    while len(hits) < limit:
        idx = low.find(target, start)
        if idx < 0:
            break
        ln = text.count("\n", 0, idx) + 1
        excerpt = src_lines[ln - 1].strip() if ln <= len(src_lines) else ""
        hits.append({"line": ln, "col": idx - (text.rfind("\n", 0, idx) + 1),
                     "excerpt": excerpt[:200]})
        start = idx + max(1, len(target))
    return {"ok": True, "schema": SCHEMA, "needle": needle, "n_references": len(hits),
            "case_insensitive": True, "references": hits}


def provenance(ctx: Any, *, limit: int = 200) -> dict[str, Any]:
    """Provenance inventory: artifacts the context CLAIMS to draw from (paths + hex hashes).

    This is the ground-truth side: the caller verifies these against disk (trust bytes,
    not the prompt's say-so). Sorted by first appearance, deduped.
    """
    text, _ = _normalize(ctx)
    scan = _URL_RE.sub(" ", text)  # URLs are not file provenance
    paths: dict[str, int] = {}
    for rx in (_UNIX_PATH_RE, _WIN_PATH_RE):
        for m in rx.finditer(scan):
            p = m.group(0).rstrip(".")
            low = p.lower()
            if not (re.search(r"\.[A-Za-z0-9]{1,8}$", p) or low.startswith(_PATH_ROOTS)):
                continue
            paths.setdefault(p, _line_of(scan, m.start()))
    hashes: dict[str, int] = {}
    for m in _HEX_RE.finditer(scan):
        h = m.group(0)
        if any(c.isdigit() for c in h) and any(c in "abcdefABCDEF" for c in h):
            hashes.setdefault(h, _line_of(scan, m.start()))
    path_rows = [{"path": p, "first_line": l} for p, l in
                 sorted(paths.items(), key=lambda kv: (kv[1], kv[0]))][:limit]
    hash_rows = [{"hash": h, "first_line": l} for h, l in
                 sorted(hashes.items(), key=lambda kv: (kv[1], kv[0]))][:limit]
    return {"ok": True, "schema": SCHEMA, "n_paths": len(path_rows), "paths": path_rows,
            "n_hashes": len(hash_rows), "hashes": hash_rows}


def self_check(ctx: Any, **kw: Any) -> dict[str, Any]:
    """One-line verdict over a context pack: CLEAN or "N findings; worst=..." (worst-first)."""
    d = diagnose(ctx, **kw)
    findings = d["findings"]
    n = len(findings)
    if n == 0:
        return {"ok": True, "schema": SCHEMA, "est_tokens": d["est_tokens"],
                "n_findings": 0, "worst": None, "verdict": "CLEAN (0 findings)",
                "findings": []}
    w = findings[0]
    return {"ok": True, "schema": SCHEMA, "est_tokens": d["est_tokens"],
            "n_findings": n,
            "worst": {"code": w["code"], "severity": w["severity"], "where": w["where"]},
            "verdict": f"{n} findings; worst={w['severity']} {w['code']} at {w['where']}",
            "findings": findings}


def _read_target(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    return Path(path).read_text(encoding="utf-8", errors="replace")


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="prompt-lance")
    ap.add_argument("cmd", nargs="?", default="self_check",
                    choices=["diagnose", "symbols", "references", "provenance", "self_check"])
    ap.add_argument("path", nargs="?", default="-",
                    help="context file under test ('-' reads stdin)")
    ap.add_argument("needle", nargs="?", default="", help="needle for references")
    ap.add_argument("--budget", type=int, default=0, help="token budget (chars/4 heuristic)")
    ap.add_argument("--stale-days", type=int, default=30)
    args = ap.parse_args(argv)
    ctx = _read_target(args.path)
    if args.cmd == "diagnose":
        out = diagnose(ctx, budget_tokens=args.budget, stale_days=args.stale_days)
    elif args.cmd == "symbols":
        out = symbols(ctx)
    elif args.cmd == "references":
        out = references(ctx, args.needle)
    elif args.cmd == "provenance":
        out = provenance(ctx)
    else:
        out = self_check(ctx, budget_tokens=args.budget, stale_days=args.stale_days)
    print(json.dumps(out, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
