"""reasoning_intake — B-CHAIN-1: seal unsealed REASONING-chain artifacts into W0.

Parses a hand-saved window trajectory export (the traj.txt paste format:
numbered turns + "Reasoning" / "Assistant" / "Tool call" / "Tool result" /
"Output" / "User" / "System" sections) into discrete turns and seals each
content-bearing turn as ONE schema-v2 TrajectoryStep row — through
mag.bash_local's writer, so the schema gate, caps, and hash chain all apply.

Row mapping (schema v2 — the why field makes it v2):
  input       = tool command (from the Tool call JSON) else User prompt,
                head-capped INPUT_CAP (4096)
  output      = Assistant text, head-capped 4096
  tool_result = {"output_head": Tool result/Output text head-capped 2048,
                 "tool": tool name, "call_id": hex id, "exit_code": None,
                 "source": "reasoning_intake"}
  why         = the turn's Reasoning block, head-capped 1024 (WHY_CAP) -> v2
  reasoning   = "" (the v1 field; the thought lives in `why` on v2 rows)
  timing      = {"source_ts", "duration_s", "tokens_in", "tokens_out", "turn"}
                (ts field = seal time; source time kept in timing — honest
                provenance: sealed-when != said-when)

Parser is TOLERANT by design (house lesson W2: preload truncation, capped
blocks): sections are delimited by numbered-turn markers ("95" + "Main
session") and exact section-header lines; unknown/garbage lines are skipped
AND COUNTED. The parse report states turns found, lines skipped, and parse
coverage % — an honest instrument, never a silent one.

CLI:
  python -m mag.reasoning_intake parse <export.txt> [--session-id X] [--dry-run]
  python -m mag.reasoning_intake verify-export <export.txt>   # report only
  python -m mag.reasoning_intake help

Read-only on the source export; appends only to the W0 tape via the writer.
$0-local. Card: watch/MYCELIAL_REPUBLIC_DISSECTION_20260907.md (B-CHAIN-1).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from mag import bash_local as w0

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATE = datetime.now().strftime("%Y%m%d")

INPUT_CAP = 4096    # tool command / user prompt head, chars
OUTPUT_CAP = 4096   # assistant text head, chars
TOOL_CAP = 2048     # tool output head, chars

# Exact section-header lines seen in the specimen (compared case-insensitively).
SECTION_HEADERS = {
    "reasoning": "reasoning",
    "assistant": "assistant",
    "tool call": "tool_call",
    "input": "input_hdr",
    "output": "output",
    "tool result": "tool_result",
    "user": "user",
    "system": "system",
}
# Meta-ish lines consumed but never treated as content (at section starts and
# in turn headers): durations, middots, timestamps, Collapse, IN/OUT tokens.
RE_META = [
    re.compile(r"^·$"),
    re.compile(r"^·\s*.+$"),
    re.compile(r"^[\d.,]+s$"),
    re.compile(r"^IN\s[\d,]+$", re.IGNORECASE),
    re.compile(r"^\d{1,2}/\d{1,2}/\d{4},\s*\d{1,2}:\d{2}:\d{2}\s*(AM|PM)?$", re.IGNORECASE),
    re.compile(r"^\d{1,2}:\d{2}:\d{2}\s*(AM|PM)$", re.IGNORECASE),
    re.compile(r"^Collapse$", re.IGNORECASE),
]
RE_TURN_NUM = re.compile(r"^\d{1,6}$")
RE_SESSION_LINE = re.compile(r"session", re.IGNORECASE)
RE_CALL_ID = re.compile(r"^[0-9a-f]{16,64}$")
RE_TOOL_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,24}$")
TOOL_NAMES_KNOWN = {"bash", "edit", "read", "write", "taskstop", "task", "glob",
                    "grep", "skill", "webfetch", "websearch", "todowrite",
                    "askuserquestion", "respondtocoordinator"}


def _is_meta(line: str) -> bool:
    return any(rx.match(line) for rx in RE_META)


def _is_section_header(line: str) -> str | None:
    return SECTION_HEADERS.get(line.strip().lower())


def _split_turns(lines: list[str]) -> tuple[list[list[str]], int]:
    """Split into turn blocks at '<int>\\n<...session...>' markers.

    Returns (turn_blocks, skipped_preamble_lines). Lines before the first
    marker are preamble: non-empty ones count as skipped.
    """
    starts: list[int] = []
    for i, ln in enumerate(lines):
        if RE_TURN_NUM.match(ln.strip()) and i + 1 < len(lines) \
                and RE_SESSION_LINE.search(lines[i + 1]):
            starts.append(i)
    skipped = sum(1 for ln in lines[:starts[0]] if ln.strip()) if starts \
        else sum(1 for ln in lines if ln.strip())
    blocks = [lines[starts[i]:starts[i + 1]] for i in range(len(starts) - 1)]
    if starts:
        blocks.append(lines[starts[-1]:])
    return blocks, skipped


def _strip_tool_preamble(content: list[str]) -> tuple[str, str, list[str]]:
    """Peel a leading tool-name line + hex call-id line off a section body."""
    tool, call_id = "", ""
    rest = list(content)
    if rest and RE_TOOL_NAME.match(rest[0].strip()) \
            and rest[0].strip().lower() in TOOL_NAMES_KNOWN:
        tool = rest.pop(0).strip()
    if rest and RE_CALL_ID.match(rest[0].strip()):
        call_id = rest.pop(0).strip()
    return tool, call_id, rest


def _parse_turn(block: list[str]) -> tuple[dict[str, Any], int]:
    """Parse one turn block -> (turn dict, skipped_garbage_lines)."""
    turn: dict[str, Any] = {
        "number": None, "tokens_in": None, "tokens_out": None,
        "duration_s": None, "source_ts": None, "sections": {}, "garbage": [],
    }
    i = 0
    # marker + session line
    if block and RE_TURN_NUM.match(block[0].strip()):
        try:
            turn["number"] = int(block[0].strip())
        except ValueError:
            pass
        i = 1
    # header region until first section header
    while i < len(block):
        ln = block[i].strip()
        if _is_section_header(ln):
            break
        m = re.match(r"^IN\s([\d,]+)$", ln, re.IGNORECASE)
        if m:
            turn["tokens_in"] = int(m.group(1).replace(",", ""))
        else:
            m = re.match(r"^·\s*OUT\s([\d,]+)$", ln, re.IGNORECASE)
            if m:
                turn["tokens_out"] = int(m.group(1).replace(",", ""))
            else:
                m = re.match(r"^·\s*([\d.,]+)s$", ln)
                if m:
                    turn["duration_s"] = float(m.group(1).replace(",", ""))
                elif RE_TURN_NUM.match(ln):
                    pass  # the marker itself
                elif ln and not RE_SESSION_LINE.search(ln) and not _is_meta(ln) \
                        and not re.match(r"^\d{1,2}:\d{2}:\d{2}", ln):
                    turn["garbage"].append(ln)
        i += 1
    # sections
    cur_key: str | None = None
    cur_meta_done = False
    cur: list[str] = []
    order: list[str] = []

    def _close() -> None:
        nonlocal cur
        if cur_key is not None:
            if cur_key in turn["sections"]:
                turn["sections"][cur_key].append("\n".join(cur).strip())
            else:
                turn["sections"][cur_key] = ["\n".join(cur).strip()]
                order.append(cur_key)
        cur = []

    while i < len(block):
        raw = block[i]
        ln = raw.strip()
        hdr = _is_section_header(ln)
        if hdr:
            _close()
            cur_key = hdr
            cur_meta_done = False
        elif cur_key is None:
            if ln:
                turn["garbage"].append(ln)
        else:
            if not cur_meta_done:
                if _is_meta(ln) and not cur:
                    m_ts = re.match(r"^(\d{1,2}/\d{1,2}/\d{4},\s*\d{1,2}:\d{2}:"
                                    r"\d{2}\s*(AM|PM)?)$", ln, re.IGNORECASE)
                    if m_ts:
                        if not turn["source_ts"]:
                            turn["source_ts"] = ln  # section meta timestamp
                    else:
                        m_in = re.match(r"^IN\s([\d,]+)$", ln, re.IGNORECASE)
                        if m_in:
                            if turn["tokens_in"] is None:
                                turn["tokens_in"] = int(m_in.group(1).replace(",", ""))
                        else:
                            m_out = re.match(r"^·\s*OUT\s([\d,]+)$", ln, re.IGNORECASE)
                            if m_out:
                                if turn["tokens_out"] is None:
                                    turn["tokens_out"] = int(m_out.group(1).replace(",", ""))
                            else:
                                m_dur = re.match(r"^·?\s*([\d.,]+)s$", ln)
                                if m_dur and turn["duration_s"] is None:
                                    turn["duration_s"] = float(
                                        m_dur.group(1).replace(",", ""))
                else:
                    cur_meta_done = True
                    if ln:
                        cur.append(raw)
            else:
                if ln:
                    cur.append(raw)
        i += 1
    _close()

    # garbage count = header-region junk (content-region lines are, tolerantly,
    # content — they are capped, never crash the parser)
    skipped = len(turn["garbage"])

    def sect(key: str) -> str:
        parts = turn["sections"].get(key, [])
        return "\n".join(p for p in parts if p).strip()

    reasoning = sect("reasoning")
    assistant = sect("assistant")
    user = sect("user")
    tool_out = "\n---\n".join(
        p for p in turn["sections"].get("tool_result", []) + turn["sections"].get("output", [])
        if p
    ).strip()

    # tool command: first parseable JSON with a "command" key in any tool_call
    # or nested "Input" body (the export puts the JSON under either header)
    tool_name, call_id, command = "", "", ""
    for body in (turn["sections"].get("tool_call", [])
                 + turn["sections"].get("input_hdr", [])):
        t2, c2, rest = _strip_tool_preamble(
            [l for l in body.splitlines() if l.strip()])
        tool_name = tool_name or t2
        call_id = call_id or c2
        raw_txt = "\n".join(rest).strip()
        obj = None
        try:
            # raw_decode: first JSON object wins; trailing export notes
            # ("Too many records...") after the closing brace are tolerated
            obj, _ = json.JSONDecoder().raw_decode(raw_txt)
        except (json.JSONDecodeError, ValueError):
            obj = None
        if isinstance(obj, dict) and "command" in obj:
            command = str(obj.get("command", ""))
            if not tool_name:
                tool_name = "Bash"
            break
        if not command:
            command = raw_txt  # honest fallback: keep the raw head

    # tool result: peel name+id if present
    tr_tool, tr_call, tr_rest = _strip_tool_preamble(
        [l for l in tool_out.splitlines() if l.strip()]) if tool_out else ("", "", [])
    tool_name = tool_name or tr_tool
    call_id = call_id or tr_call
    tool_out_text = "\n".join(tr_rest).strip()

    turn["fields"] = {
        "reasoning": reasoning,
        "assistant": assistant,
        "user": user,
        "command": command,
        "tool_out": tool_out_text,
        "tool_name": tool_name,
        "call_id": call_id,
    }
    return turn, skipped


def parse_export(path: Path) -> dict[str, Any]:
    """Parse an export file into turns + an honest parse report."""
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    blocks, skipped = _split_turns(lines)
    turns: list[dict[str, Any]] = []
    for b in blocks:
        t, s = _parse_turn(b)
        turns.append(t)
        skipped += s
    nonempty = sum(1 for ln in lines if ln.strip())
    empty_turns = 0
    sealable: list[dict[str, Any]] = []
    for t in turns:
        f = t["fields"]
        if not (f["reasoning"] or f["assistant"] or f["user"]
                or f["command"] or f["tool_out"]):
            empty_turns += 1
            continue
        sealable.append(t)
    section_hits: dict[str, int] = {}
    for t in turns:
        for k, v in t["sections"].items():
            if any(p.strip() for p in v):
                section_hits[k] = section_hits.get(k, 0) + 1
    coverage = 100.0 * (nonempty - skipped) / nonempty if nonempty else 0.0
    return {
        "file": str(path),
        "total_lines": len(lines),
        "nonempty_lines": nonempty,
        "skipped_lines": skipped,
        "coverage_pct": round(coverage, 1),
        "turns_found": len(turns),
        "empty_turns": empty_turns,
        "turns_sealable": len(sealable),
        "section_hits": section_hits,
        "turns": turns,
    }


def _report(rep: dict[str, Any], sealed: list[dict[str, Any]] | None = None) -> str:
    out = [
        f"PARSE REPORT {rep['file']}",
        f"  turns found:    {rep['turns_found']}",
        f"  turns sealable: {rep['turns_sealable']} (empty: {rep['empty_turns']})",
        f"  lines: {rep['nonempty_lines']} non-empty / {rep['total_lines']} total;"
        f" skipped (unparseable): {rep['skipped_lines']}",
        f"  parse coverage: {rep['coverage_pct']}%",
        f"  section hits (turns containing >=1 non-empty section): "
        + ", ".join(f"{k}={n}" for k, n in sorted(rep["section_hits"].items())),
    ]
    if sealed is not None:
        out.append(f"  SEALED: {len(sealed)} row(s) -> {w0.TAPE.name}")
        for r in sealed:
            out.append(f"    step {r['step_hash']} turn {r['timing'].get('turn')} "
                       f"session {r['session_id']} (schema v{r['schema_version']},"
                       f" why {'yes' if 'why' in r else 'no'},"
                       f" {len(r.get('why', ''))}B why, "
                       f"{len(r['output'])}B output, "
                       f"{len(r['tool_result'].get('output_head', ''))}B tool_result)")
    return "\n".join(out)


def seal(rep: dict[str, Any], session_id: str) -> list[dict[str, Any]]:
    """Seal every content-bearing turn as one schema-v2 row via the W0 writer."""
    rows = w0._rows()
    sealed: list[dict[str, Any]] = []
    prev = w0._last_hash_for_session(rows, session_id)
    for t in rep["turns"]:
        f = t["fields"]
        if not (f["reasoning"] or f["assistant"] or f["user"]
                or f["command"] or f["tool_out"]):
            continue
        input_txt = f["command"] or f["user"] or ""
        why_txt = f["reasoning"] or "(no Reasoning block captured)"
        row = w0.build_row(
            session_id=session_id,
            input_cmd=input_txt[:INPUT_CAP],
            output=f["assistant"][:OUTPUT_CAP],
            tool_result={
                "output_head": f["tool_out"][:TOOL_CAP],
                "tool": f["tool_name"],
                "call_id": f["call_id"],
                "exit_code": None,
                "source": "reasoning_intake",
            },
            reasoning="",
            timing={
                "source_ts": t.get("source_ts"),
                "duration_s": t["duration_s"],
                "tokens_in": t["tokens_in"],
                "tokens_out": t["tokens_out"],
                "turn": t["number"],
            },
            prev_step_hash=prev,
            why=why_txt,
        )
        # honest provenance: the section timestamp if we captured one
        w0.append_row(row)
        prev = row["step_hash"]
        sealed.append(row)
    return sealed


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    ap = argparse.ArgumentParser(prog="mag.reasoning_intake", add_help=False)
    ap.add_argument("verb", choices=["parse", "verify-export", "help"])
    ap.add_argument("export", nargs="?", default=None)
    ap.add_argument("--session-id", default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.verb == "help" or not args.export:
        print(__doc__.strip())
        sys.exit(0 if args.verb == "help" else 2)
    path = Path(args.export)
    if not path.is_file():
        print(f"FAIL export not found: {path}", file=sys.stderr)
        sys.exit(1)
    rep = parse_export(path)
    if rep["turns_found"] == 0:
        print(_report(rep))
        print("FAIL: zero turns parsed — is this a window export?",
              file=sys.stderr)
        sys.exit(1)
    if args.verb == "verify-export" or args.dry_run:
        print(_report(rep))
        print("(dry — nothing sealed)")
        return
    session_id = args.session_id or f"intake-{path.stem}-{DEFAULT_DATE}"
    sealed = seal(rep, session_id)
    print(_report(rep, sealed))
    ok, msg = w0.verify()
    print(("TAPE " + ("PASS " if ok else "FAIL ") + msg))


if __name__ == "__main__":
    main()
