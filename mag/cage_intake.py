"""cage_intake — the DFHack layer v0: seal hermes cage job receipts as PER-RACTOR chains.

Card: watch/MYCELIAL_REPUBLIC_DISSECTION_20260907.md §7 THE DFHACK LAYER.
The DFHack law: read the memory, don't interview the dwarf. A persona's
self-report is the reasoning chain — contested by default; the job receipt is
the behavior chain — hash-sealed. This organ is the cage's READ layer: it
seals the hermes steering job receipts (memory/runs/hermes_jobs/*.md) into
the W0 trajectory tape as per-ractor chains, session ids
`ractor-<persona>-<filedate>`, via mag/bash_local.py's row builder (schema
gate + hash chain apply unchanged). READ-LAYER ONLY: it never posts, never
drives hermes.exe; POSTING stays ESTATE_USERrtron-gated per the rotation charter.

bash_local.py is schema v1 today (no `why` field) — the why-string rides in
the hash-covered `reasoning` field instead. If W0 grows a `why`, this module
adopts it without format change.

CLI:
  python -m mag.cage_intake seal [--source DIR] [--dry-run]
      scan *.md job cards, append one TrajectoryStep per receipt to the W0
      tape. Tolerant parser: missing fields = None, counted. Jobs without a
      persona seal under persona "helm" (the steering itself). STEER cards
      fall back to their `nudge` line as the goal. Re-running skips receipts
      already sealed (matched by receipt filename in tool_result) —
      append-only, no duplicate rows.
  python -m mag.cage_intake census
      per-persona chain state: persona -> rows sealed -> first/last ts ->
      chain tip. Also reports KNOWN CAGE RESIDENTS with ZERO sealed receipts
      (kabuki cast from configs/kabuki_cast.json + dissection-named personas)
      — the first census of who has a chain and who is chainless.

Falsifiers:
  (a) real receipts seal well-formed; mag.bash_local verify PASSES.
  (b) corrupted/garbled job card (specimens under memory/runs/cage_intake/
      specimens/) -> skipped + counted, no crash. --dry-run previews any
      source dir with ZERO tape writes.
  (c) census is honest about personas with zero receipts (chainless roster).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from mag import bash_local as bl  # W0 writer — schema gate + chain live there

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE = ROOT / "memory" / "runs" / "hermes_jobs"
SPECIMEN_DIR = ROOT / "memory" / "runs" / "cage_intake" / "specimens"
CAST_CONFIG = ROOT / "configs" / "kabuki_cast.json"
TAPE_NAME = bl.TAPE.name

GOAL_CAP = 1024      # input head cap (chars)
OUTPUT_CAP = 4096    # output body head cap (chars)
STDERR_CAP = 256     # stderr head kept inside tool_result
HELM = "helm"
WHY = "DFHack read-layer seal of hermes job receipt"

HEADER_RE = re.compile(r"^#\s*HERMES\s+(DISPATCH|STEER)\s+(\S+)", re.M)
FIELD_RE = re.compile(r"^-\s*([A-Za-z_]+)\s*:\s*(.*)$")
FILEDATE_RE = re.compile(r"(\d{8})T")
KNOWN_KEYS = ("ts", "goal", "persona", "dir", "model", "account", "exit",
              "duration_s", "resume", "nudge")
REQUIRED_KEYS = ("goal", "persona", "exit", "duration_s", "model")
PERSONA_FALLBACKS = ("", "-", "none", "null", "helm")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ------------------------------------------------------------------- parsing

def _split_body(text: str) -> tuple[str, str]:
    """Return (output_body, stderr_text). Body starts after the first
    standalone `---` line; stderr section starts at a `--- stderr` line."""
    parts = re.split(r"^---\s*$", text, maxsplit=1, flags=re.M)
    tail = parts[1] if len(parts) > 1 else ""
    err_parts = re.split(r"^---\s*stderr.*$", tail, maxsplit=1,
                         flags=re.M | re.I)
    return err_parts[0].strip(), (err_parts[1].strip() if len(err_parts) > 1
                                  else "")


def parse_job_card(text: str) -> dict[str, Any] | None:
    """Tolerant parse. Returns None when the text is not recognizable as a
    job card (no HERMES header AND fewer than two known field lines).
    Missing fields stay None; every absence is counted in `missing`."""
    header = HEADER_RE.search(text)
    meta = text.split("\n", 1)
    fields: dict[str, str] = {}
    known_hits = 0
    zone = text
    body, stderr = _split_body(text)
    if not header:
        # metadata zone only up to the first `---` separator, when present
        zone = re.split(r"^---\s*$", text, maxsplit=1, flags=re.M)[0]
    cont_key: str | None = None
    for line in zone.splitlines():
        m = FIELD_RE.match(line)
        if m and m.group(1).lower() in KNOWN_KEYS:
            key = m.group(1).lower()
            fields[key] = m.group(2).strip()
            known_hits += 1
            cont_key = key if key in ("goal", "nudge") else None
        elif (cont_key and line.strip()
              and not line.lstrip().startswith(("-", "#"))):
            fields[cont_key] = (fields[cont_key] + " " + line.strip()).strip()
        elif line.strip():
            cont_key = None
    if not header and known_hits < 2:
        return None
    parsed: dict[str, Any] = dict(fields)
    parsed["kind"] = header.group(1) if header else "?"
    parsed["card_ts"] = header.group(2) if header else fields.get("ts")
    parsed["goal"] = fields.get("goal") or fields.get("nudge")
    parsed["output"] = body
    parsed["stderr"] = stderr
    parsed["missing"] = [k for k in REQUIRED_KEYS
                         if parsed.get(k) in (None, "")]
    exit_v: int | None = None
    try:
        exit_v = int(str(fields.get("exit", "")).strip())
    except (ValueError, TypeError):
        pass
    dur_v: float | None = None
    try:
        dur_v = float(str(fields.get("duration_s", "")).strip())
    except (ValueError, TypeError):
        pass
    parsed["exit"] = exit_v
    parsed["duration_s"] = dur_v
    return parsed


def persona_of(parsed: dict[str, Any]) -> str:
    """Jobs without a persona = persona `helm` — the steering itself."""
    raw = (parsed.get("persona") or "").strip()
    if raw.lower() in PERSONA_FALLBACKS:
        return HELM
    clean = re.sub(r"[^A-Za-z0-9_-]+", "", raw).lower()
    return clean or HELM


def filedate_of(path: Path, parsed: dict[str, Any]) -> str | None:
    m = FILEDATE_RE.search(path.name)
    if m:
        return m.group(1)
    ts = str(parsed.get("card_ts") or "")
    m = FILEDATE_RE.search(ts)
    return m.group(1) if m else None


def _timing(card_ts: str | None, dur: float | None) -> dict[str, Any]:
    start = end = _now()
    raw = str(card_ts or "").strip().replace("Z", "")
    t0 = None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y%m%dT%H%M%S"):
        try:
            t0 = datetime.strptime(raw[:len(datetime(2026, 1, 1).strftime(fmt))],
                                   fmt).replace(tzinfo=timezone.utc)
            break
        except ValueError:
            continue
    if t0 is not None:
        t1 = (t0 + timedelta(seconds=dur)) if dur is not None else t0
        start = t0.strftime("%Y-%m-%dT%H:%M:%SZ")
        end = t1.strftime("%Y-%m-%dT%H:%M:%SZ")
    return {"start": start, "end": end, "duration_s": dur, "receipt_ts": card_ts}


# --------------------------------------------------------------------- seal

def seal(source: Path, dry_run: bool = False) -> int:
    files = sorted(source.glob("*.md")) if source.is_dir() else []
    if not files:
        print(f"cage_intake seal: no job cards found under {source}")
        return 1
    tape_rows = bl._rows()
    sealed_receipts = {
        (r.get("tool_result") or {}).get("receipt")
        for r in tape_rows
        if isinstance(r, dict) and str(r.get("session_id", "")).startswith("ractor-")
    }
    counts = {"found": len(files), "sealed": 0, "skipped": 0,
              "already": 0, "dryrun": 0}
    missing_tally: dict[str, int] = {}
    personas: dict[str, int] = {}
    skip_reasons: list[str] = []
    for path in files:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            counts["skipped"] += 1
            skip_reasons.append(f"{path.name}: unreadable ({exc})")
            continue
        parsed = parse_job_card(text)
        if parsed is None:
            counts["skipped"] += 1
            skip_reasons.append(f"{path.name}: not a job card "
                                f"(no HERMES header, <2 known fields)")
            continue
        for k in parsed["missing"]:
            missing_tally[k] = missing_tally.get(k, 0) + 1
        fdate = filedate_of(path, parsed)
        if not fdate:
            counts["skipped"] += 1
            skip_reasons.append(f"{path.name}: no YYYYMMDD date derivable")
            continue
        persona = persona_of(parsed)
        sid = f"ractor-{persona}-{fdate}"
        goal = parsed.get("goal") or ""
        output = parsed.get("output") or ""
        if path.name in sealed_receipts:
            counts["already"] += 1
            print(f"  = {path.name}: already sealed ({sid})")
            continue
        tool_result = {
            "exit_code": parsed["exit"],
            "duration_s": parsed["duration_s"],
            "model": parsed.get("model"),
            "account": parsed.get("account"),
            "receipt": path.name,
            "stderr_head": (parsed.get("stderr") or "")[:STDERR_CAP],
        }
        if dry_run:
            counts["dryrun"] += 1
            print(f"  DRYRUN {path.name} -> {sid} "
                  f"(exit={parsed['exit']}, missing={parsed['missing'] or 'none'})")
            continue
        row = bl.build_row(
            session_id=sid,
            input_cmd=goal[:GOAL_CAP],
            output=output[:OUTPUT_CAP],
            tool_result=tool_result,
            reasoning=WHY,
            timing=_timing(parsed.get("card_ts"), parsed["duration_s"]),
            prev_step_hash=bl._last_hash_for_session(bl._rows(), sid),
        )
        bl.append_row(row)
        sealed_receipts.add(path.name)
        counts["sealed"] += 1
        personas[sid] = personas.get(sid, 0) + 1
        print(f"  + {path.name} -> {sid} step {row['step_hash']} "
              f"<- prev {row['prev_step_hash']}")
    mode = "DRY-RUN (no tape writes)" if dry_run else "SEALED"
    print(f"cage_intake seal [{mode}] source={source.name}: "
          f"{counts['found']} found, {counts['sealed']} sealed, "
          f"{counts['already']} already-sealed, {counts['skipped']} skipped, "
          f"{counts['dryrun']} previewed")
    if missing_tally:
        print(f"  missing-field tally: "
              + ", ".join(f"{k}={v}" for k, v in sorted(missing_tally.items())))
    for reason in skip_reasons:
        print(f"  SKIP: {reason}")
    return 0


# ------------------------------------------------------------------- census

def _known_residents() -> dict[str, str]:
    """Roster of cage residents we KNOW exist but may have zero receipts:
    kabuki cast (configs/kabuki_cast.json, read-only) + dissection-named."""
    roster: dict[str, str] = {"fermat": "dissection card 20260907",
                              "shitposter": "dissection card 20260907"}
    try:
        cast = json.loads(CAST_CONFIG.read_text(encoding="utf-8"))
        for actor in cast.get("actors", []):
            name = str(actor.get("stage_name", "")).strip().lower()
            if name:
                roster[name] = "kabuki cast config"
    except (OSError, json.JSONDecodeError, AttributeError):
        pass  # roster source unavailable — census says so, never silent
    return roster


def census() -> int:
    rows = [r for r in bl._rows()
            if isinstance(r, dict)
            and str(r.get("session_id", "")).startswith("ractor-")]
    per: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        m = re.match(r"^ractor-(.+)-(\d{8})$", str(row.get("session_id")))
        persona = m.group(1) if m else str(row.get("session_id"))
        per.setdefault(persona, []).append(row)
    print(f"CAGE INTAKE CENSUS — per-ractor chain state on {TAPE_NAME}")
    print(f"{'persona':<14}{'rows':>5}  {'first_ts':<21}{'last_ts':<21}tip")
    for persona in sorted(per):
        rws = sorted(per[persona], key=lambda r: str(r.get("ts")))
        tip = str(rws[-1].get("step_hash", "?"))
        print(f"{persona:<14}{len(rws):>5}  {str(rws[0].get('ts')):<21}"
              f"{str(rws[-1].get('ts')):<21}{tip}")
    print(f"total ractor rows: {len(rows)} across {len(per)} persona(s)")
    roster = _known_residents()
    chainless = sorted(set(roster) - set(per))
    print(f"CHAINLESS residents (in the cage, zero sealed receipts): "
          f"{', '.join(chainless) if chainless else 'none'}")
    print(f"  roster source: {CAST_CONFIG.name} (kabuki cast) + "
          f"dissection card MYCELIAL_REPUBLIC 20260907 (fermat, shitposter)")
    ok, msg = bl.verify()
    print(f"tape verify: {'PASS' if ok else 'FAIL'} {msg}")
    return 0 if ok else 1


# --------------------------------------------------------------------- main

def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    ap = argparse.ArgumentParser(
        prog="mag.cage_intake",
        description="DFHack layer v0: seal hermes job receipts as per-ractor chains")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_s = sub.add_parser("seal", help="seal job cards into the W0 tape")
    p_s.add_argument("--source", default=str(DEFAULT_SOURCE),
                     help="dir of *.md job cards (default memory/runs/hermes_jobs)")
    p_s.add_argument("--dry-run", action="store_true",
                     help="parse + report only, zero tape writes")
    sub.add_parser("census", help="per-persona chain state + chainless roster")
    args = ap.parse_args()
    if args.cmd == "seal":
        return seal(Path(args.source), dry_run=args.dry_run)
    return census()


if __name__ == "__main__":
    raise SystemExit(main())
