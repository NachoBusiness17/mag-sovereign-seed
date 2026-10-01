"""cite_gate — the vision pipeline's missing organ, made structural (2026-09-06).

Pipeline: READ -> FILTER -> INTERPRET -> [CITE-GATE] -> RIGHTSIZE -> JIT.
This organ sits between INTERPRET and RIGHTSIZE: it extracts the citations a
card loads its claims on and classifies each one deterministically, so that
uncited/broken evidence DEMOTES before rightsizing bands the output.

Classes (tri-state stamped per citation):
  LOCAL-VERIFIED   path exists under ROOT and is non-empty         -> supports
  EXISTS-UNRELATED LAW-064: file exists but the claim's key terms   -> unproven
                    are absent from it (true-but-unsupported)
  LOCAL-MISSING    path given but absent (or empty)                -> unproven
  URL-UNVERIFIED   http(s) citation, no network in this build      -> unproven (deterministic)
  NONE             citation-shaped token with no resolvable anchor -> unproven

LAW-064 PREMISE-SPAN (2026-09-07, seat gatekeep; perturbation P4 gap): a claim line with
a because/so/therefore/thus/hence structure OR a numeric claim gets its KEY TERMS
(subject words + the numbers) checked against the cited file's text (case-insensitive,
streamed, 1MB cap). File exists + terms present -> LOCAL-VERIFIED (SUBJECT-MATCH, full).
File exists + terms absent -> EXISTS-UNRELATED: the file is real but does not carry the
claim's subject -> the claim is UNPROVEN. Exists-without-subject is the gap P4 exploited:
existence was passing for support.

Per-card verdict: cite_rate = LOCAL-VERIFIED / total citations.
Writes a JSON row to state/cite_gate_latest.json (latest + capped history).

$0 LAW: local files only. The URL fetch door is a clearly-marked stub that
raises NotImplementedError — see fetch_url(). Network egress needs a later,
operator-gated build.

Falsifiers (watch/SELF_STEAL_VISION_PIPELINE_20260905.md + LAW-064 2026-09-07):
  rotation self-test, 4 cases (python -m mag.cite_gate selftest):
    A verified+subject-match  -> LOCAL-VERIFIED (SUBJECT-MATCH)
    B unrelated-but-existing  -> EXISTS-UNRELATED (claim UNPROVEN)
    C missing path            -> LOCAL-MISSING
    D numeric claim w/subject -> LOCAL-VERIFIED (SUBJECT-MATCH, numeric trigger)
  link-only card -> 0.0 (all UNPROVEN); originals never edited.

CLI:
  python -m mag.cite_gate check <card.md> [--json]
  python -m mag.cite_gate selftest
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_PATH = os.path.join(ROOT, "state", "cite_gate_latest.json")
HISTORY_CAP = 50
WORKER = "citegate"

# http(s) citations. Trailing sentence punctuation is stripped deterministically.
URL_RE = re.compile(r"https?://[^\s<>\"'`\]\}]+")

# Repo-anchored evidence pointers: known top-level dir + >=1 more segment.
# Optional trailing slash => directory pointer (must be non-empty to verify).
_ANCHOR = (
    r"(?:state|watch|memory|mag|corpus|docs|configs|queue|handoff|docker|salon"
    r"|example|examples|tests|tools|dashboard|\.agents|\.claude|\.zcode)"
)
PATH_RE = re.compile(_ANCHOR + r"(?:/[\w.@+\-]+)+/?")

# Citation-shaped bare filenames with no directory anchor (class NONE):
# unresolvable as written — deterministic UNPROVEN, never counted as verified.
BARE_FILE_RE = re.compile(
    r"(?<![\w./\-])[A-Za-z0-9_][\w\-]*\.(?:md|py|json|jsonl|yaml|yml|txt|html"
    r"|glsl|pdf|csv|log|toml|cfg|ini|bak)\b"
)

_TRAIL_PUNCT = ".,;:!?'\"*"

# ── LAW-064: premise-span subject-match (2026-09-07, seat gatekeep) ───────────
# A claim line carrying a because/so/therefore structure or a number must have its
# subject present in the file it cites. Deterministic: lexicon-free stoplist, plain
# substring containment, streamed read capped at 1MB. No LLM, $0.
SUBJECT_READ_CAP = 1_000_000   # max bytes read from a cited file (streamed, 64KB chunks)
_SUBJECT_CHUNK = 65536
_SUBJECT_OVERLAP = 128         # > longest plausible term; keeps boundary straddles hits
CONNECTIVE_RE = re.compile(r"\b(because|therefore|so|thus|hence)\b", re.IGNORECASE)
NUMBER_RE = re.compile(r"\b\d{2,}[\d,]*(?:\.\d+)?\b|\b\d+\.\d+\b")  # v2 does not trigger
_TERM_RE = re.compile(r"[a-z_][a-z0-9_\-]{3,}")  # >= 4 chars total
_SUBJECT_STOP = {
    "because", "therefore", "thus", "hence", "this", "that", "with", "from",
    "have", "been", "were", "will", "must", "before", "after", "first", "then",
    "than", "they", "them", "their", "there", "these", "those", "into", "over",
    "under", "when", "while", "since", "also", "only", "very", "more", "most",
    "such", "each", "every", "both", "should", "would", "could", "evidence",
    "works",
}


def is_claim_line(line: str) -> bool:
    """A claim line = connective structure (because/so/therefore/thus/hence) or numeric."""
    return bool(CONNECTIVE_RE.search(line) or NUMBER_RE.search(line))


def extract_key_terms(claim: str, cap: int = 10) -> list:
    """Key terms of a claim: the numbers + distinctive subject words. Citation-shaped
    tokens (URLs, repo paths, bare filenames) are masked so the pointer itself can
    never be its own subject. Order-preserving, capped, deterministic."""
    masked = URL_RE.sub(" ", claim)
    masked = PATH_RE.sub(" ", masked)
    masked = BARE_FILE_RE.sub(" ", masked)
    terms: list = []
    for num in NUMBER_RE.findall(masked):
        n = num.replace(",", "")
        if n not in terms:
            terms.append(n)
    for tok in _TERM_RE.findall(masked.lower()):
        if len(tok) >= 4 and tok not in _SUBJECT_STOP and tok not in terms:
            terms.append(tok)
        if len(terms) >= cap:
            break
    return terms[:cap]


def _stream_lower_text(path: str, cap: int = SUBJECT_READ_CAP) -> str:
    """Stream a file (binary, 64KB chunks, 128B overlap) up to `cap` bytes, lowercase."""
    parts: list = []
    total = 0
    tail = b""
    with open(path, "rb") as f:
        while total < cap:
            chunk = f.read(min(_SUBJECT_CHUNK, cap - total))
            if not chunk:
                break
            total += len(chunk)
            parts.append(tail + chunk)
            tail = chunk[-_SUBJECT_OVERLAP:]
    return b"".join(parts).decode("utf-8", errors="replace").lower()


def subject_match(claim: str, resolved_path: str) -> dict:
    """Does the cited file's text contain the claim's key terms?

    Threshold: >= 2 distinct terms for claims with >= 4 key terms, else >= 1.
    Returns {terms, matched, subject_matched, need}."""
    terms = extract_key_terms(claim)
    if not terms:
        return {"terms": [], "matched": [], "subject_matched": False, "need": 1,
                "note": "no key terms extracted from claim"}
    hay = _stream_lower_text(resolved_path)
    matched = [t for t in terms if t.lower() in hay]
    need = 2 if len(terms) >= 4 else 1
    return {"terms": terms, "matched": matched, "subject_matched": len(matched) >= need,
            "need": need}


def fetch_url(url: str) -> str:
    """FUTURE DOOR — real primary-source fetch for URL citations (NOT this build).

    When approved this must: GET the URL, cache the body under state/cite_gate_cache/,
    extract the load-bearing claim (arXiv id / DOI / repo+sha / release page),
    and reclassify URL-UNVERIFIED -> URL-VERIFIED with a content sha256 receipt.
    Needs operator GO for network egress; this build is $0 by law.
    """
    raise NotImplementedError(
        "cite_gate.fetch_url: URL door is a stub ($0 build); "
        "network egress requires operator GO in a later build"
    )


def _clean_url(url: str) -> str:
    url = url.rstrip(_TRAIL_PUNCT)
    if url.endswith(")") and "(" not in url:
        url = url[:-1].rstrip(_TRAIL_PUNCT)
    return url


def _resolve_path(target: str) -> str:
    t = target.replace("\\", "/").strip()
    if t.startswith("ROOT/"):
        t = t[5:]
    if os.path.isabs(t):
        return os.path.normpath(t)
    return os.path.normpath(os.path.join(ROOT, t))


def _classify_path(raw: str) -> dict:
    target = raw.rstrip(".,;:")  # strip sentence punctuation; keep raw for display
    resolved = _resolve_path(target)
    is_dir_pointer = target.endswith("/")
    if not os.path.exists(resolved):
        return {
            "kind": "path",
            "raw": raw,
            "resolved": resolved,
            "class": "LOCAL-MISSING",
            "status": "unproven",
            "note": "path absent on host",
        }
    if is_dir_pointer or os.path.isdir(resolved):
        non_empty = bool(os.listdir(resolved))
        return {
            "kind": "path",
            "raw": raw,
            "resolved": resolved,
            "class": "LOCAL-VERIFIED" if non_empty else "LOCAL-MISSING",
            "status": "supported" if non_empty else "unproven",
            "note": "directory" + ("" if non_empty else " exists but empty"),
        }
    size = os.path.getsize(resolved)
    return {
        "kind": "path",
        "raw": raw,
        "resolved": resolved,
        "class": "LOCAL-VERIFIED" if size > 0 else "LOCAL-MISSING",
        "status": "supported" if size > 0 else "unproven",
        "note": f"file, {size} bytes" if size > 0 else "file exists but empty",
    }


def extract_citations(text: str, strict: bool = False) -> list:
    """Deterministic extraction + classification. Dedupe by (kind, target).

    Default: only anchored citations (URLs + repo-anchored paths) — a bare
    filename in prose is a mention, not a load-bearing citation. --strict
    additionally captures bare filenames as class NONE (audit mode).
    """
    seen: set = set()
    mask = text

    # 1. URLs first (masked so path scan cannot double-count them).
    urls = [_clean_url(u) for u in URL_RE.findall(mask)]
    mask = URL_RE.sub(lambda m: "\x00" * len(m.group(0)), mask)

    # 2. Repo-anchored paths.
    paths = PATH_RE.findall(mask)
    mask = PATH_RE.sub(lambda m: "\x00" * len(m.group(0)), mask)

    # 3. Strict only: bare filenames in the residue -> class NONE.
    bares = BARE_FILE_RE.findall(mask) if strict else []

    out: list = []
    for u in urls:
        key = ("url", u)
        if u and key not in seen:
            seen.add(key)
            out.append({
                "kind": "url",
                "raw": u,
                "class": "URL-UNVERIFIED",
                "status": "unproven",
                "note": "no network in this build ($0 law); fetch door stubbed",
            })
    for p in paths:
        key = ("path", p.rstrip("/.,;:"))
        if key not in seen:
            seen.add(key)
            out.append(_classify_path(p))
    for b in bares:
        key = ("bare", b)
        if key not in seen:
            seen.add(key)
            out.append({
                "kind": "bare-file",
                "raw": b,
                "class": "NONE",
                "status": "unproven",
                "note": "no directory anchor; unresolvable as written",
            })
    return out


def check_card(card_path: str, strict: bool = False) -> dict:
    """Run the gate over one card. Never mutates the card. Returns the verdict row."""
    ap = card_path.replace("\\", "/")
    if not os.path.isabs(ap):
        ap = os.path.normpath(os.path.join(os.getcwd(), ap))
    if not os.path.isfile(ap):
        raise SystemExit(f"cite_gate: card not found: {ap}")
    with open(ap, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()

    citations = extract_citations(text, strict=strict)
    # LAW-064 premise-span: map each path citation to the first CLAIM line it sits on
    # (because/so/therefore structure or numeric claim). Other citations are untouched.
    claim_lines: dict = {}
    for ln in text.splitlines():
        if not is_claim_line(ln):
            continue
        for c in extract_citations(ln, strict=False):
            if c["kind"] == "path" and c["raw"] not in claim_lines:
                claim_lines[c["raw"]] = ln
    counts = {"LOCAL-VERIFIED": 0, "EXISTS-UNRELATED": 0, "LOCAL-MISSING": 0,
              "URL-UNVERIFIED": 0, "NONE": 0}
    for c in citations:
        if (c["kind"] == "path" and c["class"] == "LOCAL-VERIFIED"
                and os.path.isfile(c["resolved"]) and c["raw"] in claim_lines):
            m = subject_match(claim_lines[c["raw"]], c["resolved"])
            if not m["terms"]:
                # no extractable subject (e.g. a receipts line whose only digits live
                # inside the masked citation paths) -> nothing to check, no downgrade
                c["note"] += "; premise-span skipped (no key terms in claim line)"
            else:
                c["subject_terms"] = m["terms"]
                c["subject_matched_terms"] = m["matched"]
                c["subject_needed"] = m["need"]
                if m["subject_matched"]:
                    c["subject"] = "SUBJECT-MATCH"
                    c["note"] += "; premise-span SUBJECT-MATCH"
                else:
                    # file exists but does not carry the claim's subject -> UNPROVEN
                    c["class"] = "EXISTS-UNRELATED"
                    c["status"] = "unproven"
                    c["subject"] = "NO-SUBJECT-MATCH"
                    absent = [t for t in m["terms"] if t not in m["matched"]][:4]
                    c["note"] += (f"; premise-span NO-SUBJECT-MATCH "
                                  f"({len(m['matched'])}/{len(m['terms'])} key terms present,"
                                  f" absent: {absent}) -> claim UNPROVEN")
        counts[c["class"]] += 1
    total = len(citations)
    verified = counts["LOCAL-VERIFIED"]
    cite_rate = round(verified / total, 4) if total else None

    with open(ap, "rb") as f:
        card_sha = hashlib.sha256(f.read()).hexdigest()

    row = {
        "worker": WORKER,
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "organ": "cite_gate",
        "card": os.path.relpath(ap, ROOT).replace("\\", "/"),
        "card_sha256": card_sha[:16],
        "total_citations": total,
        "counts": counts,
        "cite_rate": cite_rate,
        "complete": cite_rate == 1.0,
        "citations": citations,
    }
    return row


def write_state(row: dict) -> None:
    """Latest row + capped append-only history, one file, deterministic."""
    history = []
    if os.path.isfile(STATE_PATH):
        try:
            with open(STATE_PATH, "r", encoding="utf-8") as f:
                prev = json.load(f)
            history = prev.get("history", [])
            if prev.get("latest"):
                history.append(prev["latest"])
        except (json.JSONDecodeError, OSError):
            history = []
    history = history[-(HISTORY_CAP - 1):]
    history.append(row)
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump({"latest": row, "history": history}, f, indent=2)


def selftest() -> int:
    """Rotation self-test, 4 cases (falsifier for LAW-064). Builds disposable fixtures
    under state/cite_gate_selftest/, gates them, prints PASS/FAIL, removes fixtures.
    Returns 0 iff all 4 cases classify right."""
    import shutil
    fx = os.path.join(ROOT, "state", "cite_gate_selftest")
    os.makedirs(fx, exist_ok=True)
    try:
        topic = os.path.join(fx, "corpus_registry.md")
        other = os.path.join(fx, "corpus_weather.md")
        with open(topic, "w", encoding="utf-8") as f:
            f.write("registry percolator merge seal snapshot save heal invariant 13678 knots\n"
                    "The invariant registry auto-heals by union merge with the newest seal "
                    "snapshot before the first save.\n")
        with open(other, "w", encoding="utf-8") as f:
            f.write("humidity barometer rainfall forecast thunderstorm umbrella\n")
        rel_topic = "state/cite_gate_selftest/corpus_registry.md"
        rel_other = "state/cite_gate_selftest/corpus_weather.md"
        claim = ("The registry heal works because the percolator must merge the newest "
                 "seal snapshot before its first save.")
        cases = [
            # (case, card body, expected class, expect subject_matched)
            ("A", f"{claim} Evidence: {rel_topic}", "LOCAL-VERIFIED", True),
            ("B", f"{claim} Evidence: {rel_other}", "EXISTS-UNRELATED", None),
            ("C", f"{claim} Evidence: state/cite_gate_selftest/absent.md",
             "LOCAL-MISSING", None),
            # numeric trigger only: no connective on the line
            ("D", f"The registry holds 13678 knots. Evidence: {rel_topic}",
             "LOCAL-VERIFIED", True),
        ]
        n_fail = 0
        for case, body, want_class, want_subj in cases:
            card = os.path.join(fx, f"card_{case}.md")
            with open(card, "w", encoding="utf-8") as f:
                f.write(body + "\n")
            row = check_card(card)
            cit = row["citations"][0] if row["citations"] else {}
            got = cit.get("class")
            subj = cit.get("subject") if case in ("A", "B", "D") else "-"
            ok = got == want_class
            if want_subj is True:
                ok = ok and cit.get("subject") == "SUBJECT-MATCH"
            if case == "B":
                ok = ok and cit.get("status") == "unproven"
            n_fail += 0 if ok else 1
            print(f"  case {case}: want={want_class}"
                  + (f"+SUBJECT-MATCH" if want_subj else "")
                  + f"  got={got}"
                  + (f"/{subj}" if subj != "-" else "")
                  + f"  {'PASS' if ok else 'FAIL'}")
        print(f"  rotation self-test: {'4/4 PASS' if n_fail == 0 else f'{n_fail} FAIL'}")
        return 0 if n_fail == 0 else 1
    finally:
        shutil.rmtree(fx, ignore_errors=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="mag.cite_gate", description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    chk = sub.add_parser("check", help="verify citations in a card (local-only, $0)")
    chk.add_argument("card", help="path to the card .md")
    chk.add_argument("--json", action="store_true", help="emit the verdict row as JSON to stdout")
    chk.add_argument("--strict", action="store_true",
                     help="audit mode: also capture bare filenames as class NONE")
    sub.add_parser("selftest", help="rotation self-test, 4 cases (LAW-064 falsifier)")
    args = ap.parse_args(argv)

    if args.cmd == "selftest":
        return selftest()
    row = check_card(args.card, strict=args.strict)
    write_state(row)

    if args.json:
        print(json.dumps(row, indent=2))
    else:
        c = row["counts"]
        print(f"CITE-GATE {row['card']}")
        print(f"  citations: {row['total_citations']}  "
              f"verified={c['LOCAL-VERIFIED']} unrelated={c['EXISTS-UNRELATED']} "
              f"missing={c['LOCAL-MISSING']} "
              f"url-unverified={c['URL-UNVERIFIED']} none={c['NONE']}")
        rate = row["cite_rate"]
        print(f"  cite_rate: {'n/a (no citations)' if rate is None else rate}"
              f"  complete={row['complete']}")
        for cit in row["citations"]:
            mark = {"LOCAL-VERIFIED": "+", "EXISTS-UNRELATED": "!", "LOCAL-MISSING": "x",
                    "URL-UNVERIFIED": "?", "NONE": "-"}[cit["class"]]
            print(f"  [{mark}] {cit['class']:<16} {cit['raw']}")
        print(f"  state row -> {os.path.relpath(STATE_PATH, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
