#!/usr/bin/env python
"""canon_gate.py — canon admission gate (LESSIG BUILD, 2026-09-04).

Sec-VIII of the Light-Operator Foundation, compiled for prose: every canon
document carries machine-readable ground wires — a named null-space, a
falsifier (with expected failure), and a falsifier-receipt from an actual
held-out run. CANDIDATE is the sanctioned holding state; documents without
ground wires do not promote past it. The operator is the promotion authority;
this gate is the draw code that refuses the promotion.

Usage:
    python mag/canon_gate.py            # gate pass over docs/ref/canon/*.md
    python mag/canon_gate.py --stamp    # write skeleton headers where missing
Stdlib only.
"""
import argparse
import io
import re
import sys
from pathlib import Path

REQUIRED = ["null-space", "falsifier", "falsifier-receipt"]
PROMOTION_STATES = {"promoted", "doctrine"}
UNSATISFIED = {"", "unnamed", "none", "todo", "tbd"}

HEADER_BLOCK = """<!--
canon-gate:
status: CANDIDATE
null-space: UNNAMED
falsifier: UNNAMED
falsifier-receipt: NONE
-->
"""


def parse_header(text):
    """Extract key: value pairs from a YAML frontmatter block or the first
    HTML comment block near the top of the document. Returns dict (may be empty)."""
    lines = text.splitlines()
    # YAML-ish frontmatter: file starts with ---
    if lines and lines[0].strip() == "---":
        for line in lines[1:]:
            if line.strip() == "---":
                break
            m = re.match(r"^\s*([A-Za-z][\w-]*)\s*:\s*(.*?)\s*$", line)
            if m:
                yield m.group(1).lower(), m.group(2)
        return
    # First HTML comment block within the head of the file
    head = "\n".join(lines[:60])
    m = re.search(r"<!--\s*(.*?)-->", head, re.S)
    if not m:
        return
    for line in m.group(1).splitlines():
        lm = re.match(r"^\s*([A-Za-z][\w-]*)\s*:\s*(.*?)\s*$", line)
        if lm:
            yield lm.group(1).lower(), lm.group(2)


def check_doc(path):
    """Return (status, missing_fields, warnings)."""
    text = path.read_text(encoding="utf-8", errors="replace")
    fields = dict(parse_header(text))
    status = fields.get("status", "").strip().lower()
    if not status:
        status = "(no-status)"
    missing = []
    for f in REQUIRED:
        val = fields.get(f, "").strip()
        low = val.lower()
        if not val or low.startswith(tuple(s for s in UNSATISFIED if s)):
            missing.append(f)
    return status, missing, fields


def stamp_doc(path):
    """Prepend/extend a skeleton canon-gate header on a doc missing fields.
    Returns True if the file was modified."""
    text = path.read_text(encoding="utf-8", errors="replace")
    fields = dict(parse_header(text))
    need = [f for f in ["status"] + REQUIRED if not fields.get(f, "").strip()]
    if not need:
        return False
    if "<!--" in text.split("\n", 1)[0] or text.lstrip().startswith("<!--"):
        # header block exists but incomplete: rebuild it complete (idempotent skeleton)
        m = re.search(r"<!--\s*(.*?)-->", text, re.S)
        block = m.group(0)
        body = dict(parse_header(text))
        body.update({k: v for k, v in
                     [("status", "CANDIDATE"), ("null-space", "UNNAMED"),
                      ("falsifier", "UNNAMED"), ("falsifier-receipt", "NONE")]
                     if k in need})
        lines = ["<!--", "canon-gate:"] + [f"{k}: {body[k]}" for k in ["status"] + REQUIRED] + ["-->"]
        text = text.replace(block, "\n".join(lines), 1)
    else:
        text = HEADER_BLOCK + text
    path.write_text(text, encoding="utf-8")
    return True


def main():
    ap = argparse.ArgumentParser(description="canon admission gate")
    ap.add_argument("--canon-dir", default="docs/ref/canon")
    ap.add_argument("--stamp", action="store_true",
                    help="write skeleton headers into docs missing fields")
    args = ap.parse_args()
    root = Path(__file__).resolve().parent.parent
    cdir = root / args.canon_dir
    docs = sorted(cdir.glob("*.md"))
    if not docs:
        print(f"canon_gate: no .md docs under {cdir}")
        return 2
    refused = []
    if args.stamp:
        for d in docs:
            if stamp_doc(d):
                print(f"STAMPED  {d.name}")
            else:
                print(f"OK       {d.name} (header complete)")
        return 0
    print(f"canon_gate: gating {len(docs)} docs in {cdir}")
    for d in docs:
        status, missing, fields = check_doc(d)
        if missing:
            if status in PROMOTION_STATES:
                refused.append((d, status, missing))
                print(f"REFUSED  {d.name}  status={status}  missing: {', '.join(missing)}")
            else:
                print(f"WARN     {d.name}  status={status}  missing: {', '.join(missing)}")
        else:
            print(f"PASS     {d.name}  status={status}  ground wires wired")
    if refused:
        print(f"\nREFUSED: {len(refused)} document(s) tried to promote without ground wires:")
        for d, status, missing in refused:
            print(f"  {d.name} ({status}): missing {', '.join(missing)}")
        return 1
    print("\nGate pass: no ungrounded promotions. (CANDIDATE holding states warned, not refused.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
