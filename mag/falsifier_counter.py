#!/usr/bin/env python3
"""falsifier_counter — measure the WATCHER's breadcrumb->action close rate.

Born 2026-09-05 (A2, weekend build pool). The stigmergy card
(watch/DEEP_SELF_STEAL_STIGMERGY_20260905.md) named the falsifier:
"breadcrumb -> action close rate over a week". Nobody measured it. This is
the measurer: a read-only pass over the breadcrumb store and the activity
stores, classifying each breadcrumb's lifecycle:

    dropped -> seen -> acted (closed) | expired

Breadcrumb store (dropped by mag/lane_runner.py cycle_watcher):
  queue/lanes/<lane>/INBOX/watcher_<stamp>.md   (+ WATCHER_CRUMB trail row)

Activity stores (where action would show):
  queue/lanes/*/trail.jsonl, state/shared_activity.jsonl,
  queue/room.jsonl, watch/room.jsonl, queue/handoff/*/CONVO.md,
  queue/lanes/*/surface.md

Classification (deterministic, no model calls, $0):
  tokens   = distinctive keywords from clue+shape+evidence (stopwords out),
             then RARITY-FILTERED: a token that appears in more than
             max(10, 0.2%) of activity rows is boilerplate (lane names,
             autorun ticks) and can never count — a keyword that matches
             everything identifies nothing.
  window   = --window-days (default 7) after the drop timestamp
  acted    = a candidate row cites the drop stamp, or matches >= N rare
             tokens (N=2 for row-timestamped sources: trails, shared
             activity, rooms; N=3 for coarse sources: CONVO/surface lines)
             -> status "closed", time-to-action recorded
  seen     = >=1 rare token match but below the acted bar
  open     = nothing matched, window not elapsed yet
  expired  = nothing matched, window elapsed

Honesty guards (each earned against real false positives on day one):
  time-travel guard — rows timestamped BEFORE the drop never count, even
    with every token present. CONVO.md gets PER-LINE timestamps parsed from
    its "[seat <ts>]" headers (unparseable lines carry the previous line's
    ts; the file mtime is the last resort).
  echo guard — trail events {WATCHER_CRUMB, SCHEDULER_UP, CYCLE} are the
    scheduler re-emitting the feed; they never count as action.
  drop-report demotion — a row that talks ABOUT the breadcrumb mechanism
    ("breadcrumb", "WATCHER_CRUMB") is the fleet discussing the watcher,
    not acting on a clue; it can raise a crumb to "seen", never "closed",
    unless it cites the exact drop stamp.

Ledger: memory/falsifier/close_rate.jsonl — append-only, typed rows
(row_type=breadcrumb_close | summary_close_rate), deduped on breadcrumb id:
a row is appended only when the id is new or its status/action changed.
Every breadcrumb row carries matched_by + matched_text so a human can audit
the machine's judgment in one line.

Usage:
  python mag/falsifier_counter.py                 # live incremental pass
  python mag/falsifier_counter.py --json          # machine-readable summary
  python mag/falsifier_counter.py --root PATH     # point at a store (tests)
  python mag/falsifier_counter.py --selftest      # synthetic proof, no live IO
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import statistics
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT_DEFAULT = Path(__file__).resolve().parent.parent

STAMP_RE = re.compile(r"watcher_(\d{8}T\d{6}Z)")
FIELD_RE = {k: re.compile(rf"^-\s*{k}:\s*(.+)$", re.M) for k in ("shape", "evidence", "clue")}
# Trail events that are the scheduler re-emitting the feed — never "action".
ECHO_EVENTS = {"WATCHER_CRUMB", "SCHEDULER_UP", "CYCLE"}
# A row talking about the breadcrumb mechanism itself: reporting drops,
# naming the falsifier. Engagement at best -> seen tier, never closed.
BC_MECHANISM_RE = re.compile(r"breadcrumb|watcher_crumb", re.I)
STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "into", "over", "also",
    "been", "each", "when", "then", "than", "them", "they", "were", "have",
    "has", "had", "not", "but", "its", "our", "are", "was", "who", "why",
    "how", "what", "which", "while", "still", "only", "same", "more", "most",
    "some", "such", "very", "must", "should", "would", "could", "before",
    "after", "between", "against", "whose", "their", "there", "these",
    "those", "about", "under", "again", "once", "here", "just", "even",
    "lead", "unproven", "verify", "acting", "watcher", "breadcrumb",
    "breadcrumbs", "clue", "shape", "evidence", "inbox", "inboxes",
}
MAX_TOKENS = 16
DF_CAP_FLOOR = 10
DF_CAP_FRAC = 0.002          # a token in >0.2% of rows is boilerplate


def parse_ts(raw: str) -> datetime | None:
    """Tolerant UTC parse: Z, +00:00, naive (assumed UTC), space separator."""
    if not raw:
        return None
    s = str(raw).strip().replace(" ", "T", 1)
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def compact_ts(dt: datetime) -> str:
    return dt.strftime("%Y%m%dT%H%M%SZ")


# ------------------------------------------------------------------ drops
def load_breadcrumbs(root: Path) -> list[dict]:
    """Discover watcher drops: INBOX/*.md files first, then WATCHER_CRUMB
    trail rows whose clue is not already covered by a file (consumed inboxes
    leave only the trail row — it is the durable record)."""
    crumbs: list[dict] = []
    seen_keys: set[tuple[str, str]] = set()
    for f in sorted(root.glob("queue/lanes/*/INBOX/watcher_*.md")):
        lane = f.parts[-3]
        m = STAMP_RE.search(f.name)
        drop_ts = parse_ts(m.group(1)) if m else None
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if drop_ts is None:
            drop_ts = parse_ts(f"{f.stem.split('_', 1)[-1]}")
        fields = {}
        for k, rx in FIELD_RE.items():
            mm = rx.search(text)
            if mm:
                fields[k] = mm.group(1).strip().strip("`").strip()
        clue = fields.get("clue", "")
        crumbs.append({
            "id": f"{lane}/{f.name}", "lane": lane, "drop_ts": drop_ts,
            "stamp": m.group(1) if m else "", "text": text,
            "clue": clue, "source": "inbox_md",
            "fields": fields,
        })
        if clue:
            seen_keys.add((lane, clue[:80]))
    # orphan trail rows (file gone / never written)
    for tf in sorted(root.glob("queue/lanes/*/trail.jsonl")):
        lane = tf.parts[-2]
        for line in _read_lines(tf):
            try:
                row = json.loads(line)
            except Exception:  # noqa: BLE001 — silent-fail per row
                continue
            if row.get("event") != "WATCHER_CRUMB":
                continue
            detail = str(row.get("detail", ""))
            if (lane, detail[:80]) in seen_keys:
                continue
            ts = parse_ts(str(row.get("ts", "")))
            crumbs.append({
                "id": f"{lane}/watcher_{compact_ts(ts) if ts else 'unknown'}",
                "lane": lane, "drop_ts": ts, "stamp": "",
                "text": detail, "clue": detail, "source": "trail_row",
                "fields": {"clue": detail},
            })
    return [c for c in crumbs if c["drop_ts"] is not None]


# --------------------------------------------------------------- activity
def _convo_ts(header: str, year_hint: int) -> tuple[datetime | None, bool]:
    """Parse a CONVO bracket header like 'zcode 2026-08-26T16:32:13Z' or
    'zcode 09-05 ~02:5xZ'. Returns (UTC dt, dirty_minute). A dirty minute
    ('5x' — the ones digit unknown) means the true time lies in [M0, M9]:
    dt is the interval START and dirty=True. Callers matching a window must
    use ts_hi = dt + 9min and only count when the whole interval qualifies —
    an uncertain line is never smuggled across the drop boundary."""
    m = re.search(r"(\d{4}-\d{2}-\d{2})T(\d{1,2}):(\d{2})(?::(\d{2}))?", header)
    if m:
        try:
            return (datetime(int(m.group(1)[:4]), int(m.group(1)[5:7]), int(m.group(1)[8:10]),
                             int(m.group(2)), int(m.group(3)), int(m.group(4) or 0),
                             tzinfo=timezone.utc), False)
        except ValueError:
            return None, False
    m = re.search(r"(?:(\d{4})-)?(\d{2})-(\d{2})", header)
    if m:
        year = int(m.group(1)) if m.group(1) else year_hint
        month, day = int(m.group(2)), int(m.group(3))
        try:
            dt = datetime(year, month, day, tzinfo=timezone.utc)
        except ValueError:
            return None, False
        tail = header[m.end():m.end() + 8]
        tm = re.search(r"[ T~]*?(\d{1,2}):(\d{0,2})x?", tail)
        dirty = False
        if tm:
            hh = int(tm.group(1))
            raw_mm = tm.group(2) or ""
            if len(raw_mm) == 2:
                mm = int(raw_mm)                       # clean minute
            else:
                mm = int(raw_mm or "0") * 10           # "5x" -> interval starts :50
                dirty = True
            try:
                dt = dt.replace(hour=min(hh, 23), minute=min(mm, 59))
            except ValueError:
                dirty = False
        # month/day in the future of the year-hint means the previous year
        if dt > datetime.now(timezone.utc) + timedelta(days=1):
            try:
                dt = dt.replace(year=year - 1)
            except ValueError:
                pass
        return dt, dirty
    return None, False


def _convo_rows(path: Path) -> list[dict]:
    """One activity row per CONVO line, timestamped per-line from bracket
    headers; lines without a header inherit the previous line's ts (the
    files are chronological); the file mtime is the last resort."""
    rows: list[dict] = []
    try:
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    except OSError:
        return rows
    year_hint = mtime.year
    carry = None
    for line in _read_lines(path):
        ts = carry
        ts_hi = ts
        m = re.match(r"^\[\s*([^\]]{1,80})\]", line)
        if m:
            parsed, dirty = _convo_ts(m.group(1), year_hint)
            if parsed:
                ts = parsed
                ts_hi = parsed + timedelta(minutes=9) if dirty else parsed
        if ts is None:
            ts = ts_hi = mtime
        carry = ts
        rows.append({"ts": ts, "ts_hi": ts_hi, "event": "convo", "text": line,
                     "where": path.parts[-2], "source": f"convo:{path.parts[-2]}",
                     "echo": False})
    return rows


def load_activity(root: Path) -> list[dict]:
    """Collect activity rows: {ts, event, text, where, source, echo}.
    Per-row silent-fail; unreadable stores are skipped."""
    rows: list[dict] = []
    # lane trails (authoritative lane action log)
    for tf in sorted(root.glob("queue/lanes/*/trail.jsonl")):
        lane = tf.parts[-2]
        for line in _read_lines(tf):
            try:
                r = json.loads(line)
            except Exception:  # noqa: BLE001
                continue
            ev = str(r.get("event", ""))
            rows.append({
                "ts": parse_ts(str(r.get("ts", ""))),
                "event": ev,
                "text": str(r.get("detail", "")) + " " +
                        " ".join(str(a) for a in (r.get("artifacts") or [])),
                "where": lane, "source": f"trail:{lane}",
                "echo": ev in ECHO_EVENTS,
            })
    # shared activity
    for line in _read_lines(root / "state" / "shared_activity.jsonl"):
        try:
            r = json.loads(line)
        except Exception:  # noqa: BLE001
            continue
        rows.append({
            "ts": parse_ts(str(r.get("ts", ""))),
            "event": str(r.get("status", "")),
            "text": str(r.get("goal", "")) + " " + str(r.get("detail", "")),
            "where": str(r.get("seat", r.get("actor", ""))),
            "source": "shared_activity", "echo": False,
        })
    # rooms
    for rp in (root / "queue" / "room.jsonl", root / "watch" / "room.jsonl"):
        for line in _read_lines(rp):
            try:
                r = json.loads(line)
            except Exception:  # noqa: BLE001
                continue
            rows.append({
                "ts": parse_ts(str(r.get("ts", ""))),
                "event": str(r.get("event", r.get("thread", "room"))),
                "text": str(r.get("text", "")) + " " + str(r.get("actor", "")),
                "where": str(r.get("seat", r.get("actor", "room"))),
                "source": f"room:{rp.parent.name}", "echo": False,
            })
    # seat rooms (per-line ts) + lane surfaces (mtime, coarse)
    for cf in sorted(root.glob("queue/handoff/*/CONVO.md")):
        rows.extend(_convo_rows(cf))
    for sf in sorted(root.glob("queue/lanes/*/surface.md")):
        text = _read_all(sf)
        if text:
            rows.append({
                "ts": _mtime_utc(sf), "event": "surface",
                "text": text, "where": sf.parts[-2],
                "source": f"surface:{sf.parts[-2]}", "echo": False,
            })
    return [r for r in rows if r["ts"] is not None]


def _read_lines(p: Path) -> list[str]:
    try:
        return [l for l in p.read_text(encoding="utf-8", errors="replace").splitlines() if l.strip()]
    except OSError:
        return []


def _read_all(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _mtime_utc(p: Path) -> datetime:
    return datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)


# ------------------------------------------------------------ classification
def extract_tokens(crumbs: dict) -> list[str]:
    text = " ".join(str(crumbs.get(k, "")) for k in ("clue", "shape", "evidence"))
    toks: list[str] = []
    for t in re.split(r"[^a-z0-9]+", text.lower()):
        if len(t) >= 4 and t not in STOPWORDS and t not in toks:
            toks.append(t)
        if len(toks) >= MAX_TOKENS:
            break
    return toks


def rare_tokens(crumbs: list[dict], activity: list[dict]) -> set[str]:
    """Tokens that are actually diagnostic: a token appearing in more than
    max(10, 0.2%) of activity rows is machinery boilerplate (lane names in
    autorun ticks, generic logs) and is discarded for matching."""
    toks: list[str] = []
    for c in crumbs:
        for t in extract_tokens(c["fields"]):
            if t not in toks:
                toks.append(t)
    cap = max(DF_CAP_FLOOR, int(DF_CAP_FRAC * len(activity)))
    texts = [r["text"].lower() for r in activity]
    rare: set[str] = set()
    for t in toks:
        df = sum(1 for tx in texts if t in tx)
        if df <= cap:
            rare.add(t)
    return rare


def classify(bc: dict, activity: list[dict], rare: set[str],
             window_days: float, now: datetime) -> dict:
    """Lifecycle for one breadcrumb against candidate activity rows."""
    tokens = extract_tokens(bc["fields"])
    w_end = bc["drop_ts"] + timedelta(days=window_days)
    first_seen = first_acted = None
    for r in activity:
        if r["echo"] and r["source"].startswith("trail:"):
            continue                     # machinery heartbeat, never action
        lo, hi = r["ts"], r.get("ts_hi") or r["ts"]
        # time-travel guard + window: a dirty-timestamped row ("02:5x") only
        # counts when its WHOLE uncertainty interval [lo, hi] is in-window
        if not (bc["drop_ts"] < lo and hi <= w_end):
            continue
        text = r["text"].lower()
        hits = sum(1 for t in tokens if t in rare and t in text)
        id_ref = bool(bc["stamp"]) and bc["stamp"] in text
        about_mechanism = bool(BC_MECHANISM_RE.search(r["text"]))
        coarse = r["source"].startswith(("convo:", "surface:"))
        need = 3 if coarse else 2
        if not about_mechanism and (id_ref or hits >= need) and first_acted is None:
            first_acted = r              # drop-report lines can never close
        if hits >= 1 and first_seen is None:
            first_seen = r
    if first_acted is not None:
        status, act = "closed", first_acted
    elif first_seen is not None:
        status, act = "seen", first_seen
    elif now <= w_end:
        status, act = "open", None
    else:
        status, act = "expired", None
    return {
        "id": bc["id"], "lane": bc["lane"], "drop_ts": bc["drop_ts"],
        "status": status, "tokens": tokens,
        "action_ts": act["ts"] if act else None,
        "time_to_action_min": round((act["ts"] - bc["drop_ts"]).total_seconds() / 60, 1) if act else None,
        "matched_by": act["source"] + ":" + act["event"] if act else None,
        "matched_text": act["text"][:200].replace("\n", " ") if act else None,
        "window_days": window_days,
    }


# ------------------------------------------------------------------ ledger
def ledger_append(ledger: Path, results: list[dict], summary: dict) -> int:
    """Append-only, dedup on breadcrumb id: write a row only when the id is
    new or its (status, action_ts) changed. Returns rows written."""
    def _key(status: str, action_ts) -> tuple[str, str]:
        # normalized exactly as written to the ledger (seconds precision)
        return (status, action_ts.isoformat(timespec="seconds") if action_ts else "")

    prior: dict[str, tuple[str, str]] = {}
    if ledger.exists():
        for line in _read_lines(ledger):
            try:
                r = json.loads(line)
            except Exception:  # noqa: BLE001
                continue
            if r.get("row_type") == "breadcrumb_close":
                prior[r["id"]] = (r.get("status", ""), r.get("action_ts") or "")
    written = 0
    ledger.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with ledger.open("a", encoding="utf-8") as f:
        for res in results:
            key = _key(res["status"], res["action_ts"])
            if res["id"] in prior and prior[res["id"]] == key:
                continue                      # dedup: unchanged lifecycle
            row = {"row_type": "breadcrumb_close", "schema": "falsifier.close.v1",
                   "recorded_at": now, "window_days": res["window_days"],
                   "id": res["id"], "lane": res["lane"],
                   "drop_ts": res["drop_ts"].isoformat(timespec="seconds"),
                   "status": res["status"], "matched_by": res["matched_by"],
                   "matched_text": res["matched_text"],
                   "action_ts": res["action_ts"].isoformat(timespec="seconds") if res["action_ts"] else None,
                   "time_to_action_min": res["time_to_action_min"],
                   "tokens": res["tokens"]}
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            written += 1
        f.write(json.dumps({"row_type": "summary_close_rate",
                            "schema": "falsifier.summary.v1",
                            "recorded_at": now, **summary},
                           ensure_ascii=False) + "\n")
        written += 1
    return written


def summarize(results: list[dict], window_days: float, now: datetime) -> dict:
    week_start = now - timedelta(days=window_days)
    week = [r for r in results if r["drop_ts"] >= week_start]
    closed = [r for r in week if r["status"] == "closed"]
    counts = {"total": len(week), "closed": len(closed),
              "seen": sum(1 for r in week if r["status"] == "seen"),
              "open": sum(1 for r in week if r["status"] == "open"),
              "expired": sum(1 for r in week if r["status"] == "expired")}
    settled = counts["total"] - counts["open"]
    per_lane: dict[str, dict] = {}
    for r in week:
        d = per_lane.setdefault(r["lane"], {"total": 0, "closed": 0})
        d["total"] += 1
        d["closed"] += 1 if r["status"] == "closed" else 0
    tta = [r["time_to_action_min"] for r in closed if r["time_to_action_min"] is not None]
    return {
        "week_start": week_start.isoformat(timespec="seconds"),
        "week_end": now.isoformat(timespec="seconds"),
        "window_days": window_days, **counts,
        "close_rate_week": round(counts["closed"] / counts["total"], 4) if counts["total"] else None,
        "close_rate_settled": round(counts["closed"] / settled, 4) if settled else None,
        "median_tta_min": round(statistics.median(tta), 1) if tta else None,
        "per_lane": per_lane,
    }


# ------------------------------------------------------------------- passes
def run_pass(root: Path, ledger: Path, window_days: float) -> tuple[dict, list[dict]]:
    now = datetime.now(timezone.utc)
    crumbs = load_breadcrumbs(root)
    activity = load_activity(root)
    rare = rare_tokens(crumbs, activity)
    results = [classify(c, activity, rare, window_days, now) for c in crumbs]
    summary = summarize(results, window_days, now)
    summary["store"] = {"breadcrumbs": len(crumbs), "activity_rows": len(activity),
                        "rare_tokens": len(rare), "root": str(root)}
    written = ledger_append(ledger, results, summary)
    summary["ledger"] = {"path": str(ledger), "rows_written": written}
    return summary, results


# ----------------------------------------------------------------- selftest
def _write(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def _crumb_md(stamp: str, shape: str, evidence: str, clue: str, extra: str = "") -> str:
    return (f"**WATCHER BREADCRUMB** (UNPROVEN lead — verify before acting) {stamp}\n\n"
            f"- shape: {shape}\n- evidence: `{evidence}`\n- clue: {clue}\n" + extra)


def selftest() -> int:
    """Synthetic store, known answers, mismatch cases, dedup + upgrade proof."""
    now = datetime.now(timezone.utc)
    ok = True

    def check(name: str, cond: bool, detail: str = "") -> None:
        nonlocal ok
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
        ok = ok and cond

    tmp = Path(tempfile.mkdtemp(prefix="falsifier_selftest_"))
    try:
        # --- bc1: acted via id citation (0 token overlap needed) ------------
        s1 = compact_ts(now - timedelta(days=1, hours=3))
        _write(tmp / f"queue/lanes/builder/INBOX/watcher_{s1}.md",
               _crumb_md(s1, "seal drift", "grader recipe mismatch sha256",
                         "grader seal recipe drifted from canonical projection"))
        _write(tmp / "queue/lanes/builder/trail.jsonl",
               json.dumps({"ts": (now - timedelta(days=1, hours=1)).isoformat(),
                           "actor": "builder-cage", "event": "BUILD",
                           "detail": f"rebuilt seal verifier per watcher_{s1}; recipe pinned",
                           "artifacts": []}) + "\n")
        # --- bc2: acted via >=2 rare-token overlap, no id citation ----------
        s2 = compact_ts(now - timedelta(days=1, hours=2))
        _write(tmp / f"queue/lanes/research/INBOX/watcher_{s2}.md",
               _crumb_md(s2, "missing verifier", "hunger_ledger rc=2 script missing",
                         "restore scripts/hunger_ledger.py and re-run ledger verification"))
        _write(tmp / "queue/lanes/research/trail.jsonl",
               json.dumps({"ts": (now - timedelta(days=1, hours=1, minutes=15)).isoformat(),
                           "actor": "research-cage", "event": "FIX",
                           "detail": "restored scripts/hunger_ledger.py; ledger verification re-ran clean",
                           "artifacts": []}) + "\n")
        # --- bc3: seen only (exactly one rare-token echo, no id) ------------
        s3 = compact_ts(now - timedelta(days=1, hours=6))
        _write(tmp / f"queue/lanes/day_work/INBOX/watcher_{s3}.md",
               _crumb_md(s3, "cadence drift", "scheduler heartbeat timing skew",
                         "watch cadence drifted from the 30m heartbeat contract"))
        _write(tmp / "queue/lanes/day_work/trail.jsonl",
               json.dumps({"ts": (now - timedelta(days=1)).isoformat(),
                           "actor": "day_work-cage", "event": "NOTE",
                           "detail": "heartbeat reviewed, no change yet",  # exactly ONE token
                           "artifacts": []}) + "\n")
        # --- bc5: acted via a CONVO line (per-line ts, coarse bar of 3) -----
        s5 = compact_ts(now - timedelta(days=1, hours=8))
        _write(tmp / f"queue/lanes/elder/INBOX/watcher_{s5}.md",
               _crumb_md(s5, "fuel gauge gap", "restock meter unbacked",
                         "wire the fuelgauge restock meter before key requests"))
        pre = (now - timedelta(days=1, hours=20)).strftime("%Y-%m-%dT%H:%M:%SZ")
        post = (now - timedelta(days=1, hours=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
        _write(tmp / "queue/handoff/zcode/CONVO.md",
               f"[zcode {pre}] fuelgauge restock meter brainstorm, wire it someday\n"
               f"[zcode {post}] wired the fuelgauge restock meter and keyed the request\n")
        # --- bc6: drop-report lines + pre-drop echo must NOT close ----------
        #      (this is the exact false-positive class the live v0 hit)
        s6 = compact_ts(now - timedelta(days=1, hours=10))
        _write(tmp / f"queue/lanes/forge/INBOX/watcher_{s6}.md",
               _crumb_md(s6, "poster debt", "art queue backlog starving forge",
                         "drain the art queue backlog before new posters"))
        post6 = (now - timedelta(days=1, hours=9)).strftime("%Y-%m-%dT%H:%M:%SZ")
        _write(tmp / "queue/handoff/builder/CONVO.md",
               f"[builder {post6}] dropped 3 breadcrumbs incl. art queue backlog starving "
               f"forge — falsifier: close rate over a week\n")
        # --- bc7: dirty-minute intervals ------------------------------------
        # drop at H:55; a "~H:5x" line ([H:50,H:59]) STRADDLES the drop and
        # must never count; a "~(H+1):0x" line ([(H+1):00,(H+1):09]) counts.
        d7 = (now - timedelta(days=1)).replace(minute=55, second=0, microsecond=0)
        s7 = compact_ts(d7)
        h = d7.hour
        dd = d7.strftime("%m-%d")
        _write(tmp / f"queue/lanes/harvest/INBOX/watcher_{s7}.md",
               _crumb_md(s7, "stale harvest", "tide chart widget ships stale data",
                         "tide chart widget refreshed before stale data ships"))
        _write(tmp / "queue/handoff/forge/CONVO.md",
               f"[forge {dd} ~{h:02d}:5xZ] tide chart widget ships stale data, noted\n"
               f"[forge {dd} ~{(h + 1) % 24:02d}:0xZ] tide chart widget refreshed, stale data fixed\n")

        summary, results = run_pass(tmp, tmp / "memory/falsifier/close_rate.jsonl", 7.0)
        by_id = {r["id"].split("/", 1)[1]: r for r in results}
        check("6 breadcrumbs discovered (bc4 not yet dropped)",
              summary["total"] == 6, f"got {summary['total']}")
        check("bc1 closed via id citation",
              by_id.get(f"watcher_{s1}.md", {}).get("status") == "closed"
              and by_id.get(f"watcher_{s1}.md", {}).get("matched_by", "").startswith("trail:builder"))
        check("bc2 closed via tokens",
              by_id.get(f"watcher_{s2}.md", {}).get("status") == "closed")
        check("bc3 seen only (1 token)",
              by_id.get(f"watcher_{s3}.md", {}).get("status") == "seen")
        check("bc5 closed via post-drop CONVO line",
              by_id.get(f"watcher_{s5}.md", {}).get("status") == "closed"
              and by_id.get(f"watcher_{s5}.md", {}).get("matched_by", "").startswith("convo:zcode"),
              str(by_id.get(f"watcher_{s5}.md", {}).get("matched_by")))
        check("bc6 NOT closed by drop-report line (demoted to seen)",
              by_id.get(f"watcher_{s6}.md", {}).get("status") == "seen",
              str(by_id.get(f"watcher_{s6}.md", {}).get("status")))
        r7 = by_id.get(f"watcher_{s7}.md", {})
        check("bc7 closed via post-drop interval line only (straddler excluded: tta=5.0, "
              "a counted straddler would predate the drop)",
              r7.get("status") == "closed" and r7.get("time_to_action_min") == 5.0,
              f"status={r7.get('status')} tta={r7.get('time_to_action_min')}")
        # settled = 6 (no open), closed = 4 -> 66.7%
        check("close_rate_settled == 4/6 == 0.6667",
              summary["close_rate_settled"] == 0.6667, f"got {summary['close_rate_settled']}")
        med = summary["median_tta_min"]
        check("median tta == median(120, 45, 60, 5) == 52.5", med == 52.5, f"got {med}")

        # --- bc4: mismatch — counter must DISAGREE with input ---------------
        # maximal keyword overlap, but every match is pre-drop (time travel),
        # an echo event, or beyond the window; the crumb CLAIMS acted.
        s4 = compact_ts(now - timedelta(days=8))
        _write(tmp / f"queue/lanes/elder/INBOX/watcher_{s4}.md",
               _crumb_md(s4, "STATUS: ACTED (claimed)", "orphan chain knot duplicate",
                         "duplicate orphan knot left in verkle chain registry",
                         extra="\n- claimed_status: ACTED\n"))
        _write(tmp / "queue/lanes/elder/trail.jsonl",
               json.dumps({"ts": (now - timedelta(days=8, hours=5)).isoformat(),
                           "actor": "elder-cage", "event": "FIX",
                           "detail": "duplicate orphan knot in verkle chain registry removed",  # pre-drop
                           "artifacts": []}) + "\n" +
               json.dumps({"ts": (now - timedelta(days=8)).isoformat().replace("+00:00", "Z"),
                           "actor": "elder-cage", "event": "CYCLE",
                           "detail": "verkle chain registry orphan knot sweep",  # echo event
                           "artifacts": []}) + "\n" +
               json.dumps({"ts": (now - timedelta(days=8) + timedelta(days=9)).isoformat(),
                           "actor": "elder-cage", "event": "FIX",
                           "detail": "verkle chain registry orphan knot re-sweep",  # beyond window
                           "artifacts": []}) + "\n")
        summary2, results2 = run_pass(tmp, tmp / "memory/falsifier/close_rate.jsonl", 7.0)
        r4 = [r for r in results2 if r["id"].endswith(f"watcher_{s4}.md")][0]
        check("mismatch bc4: counter says expired despite claimed ACTED + 3 keyword rows",
              r4["status"] == "expired", f"got {r4['status']}")
        # weekly bucket = trailing 7d: the 8-day-old bc4 is excluded from the
        # week but present in the all-time classification
        check("window discipline: weekly total stays 6 (8-day-old bc4 excluded)",
              summary2["total"] == 6, f"got {summary2['total']}")
        alltime = {"closed": 0, "seen": 0, "expired": 0, "open": 0}
        for r in results2:
            alltime[r["status"]] += 1
        check("all-time lifecycle counts: 4 closed, 2 seen, 1 expired",
              alltime == {"closed": 4, "seen": 2, "expired": 1, "open": 0},
              f"got {alltime}")

        # --- ledger: append-only, dedup, upgrade -----------------------------
        bc_rows = [l for l in _read_lines(tmp / "memory/falsifier/close_rate.jsonl")
                   if '"breadcrumb_close"' in l]
        check("ledger dedup: exactly 7 breadcrumb rows after 3 passes", len(bc_rows) == 7,
              f"got {len(bc_rows)}")
        # upgrade bc3 to acted, rerun -> one new breadcrumb row, status closed
        with (tmp / "queue/lanes/day_work/trail.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": (now - timedelta(hours=12)).isoformat(),
                                "actor": "day_work-cage", "event": "FIX",
                                "detail": "heartbeat cadence pinned back to 30m contract; drift closed",
                                "artifacts": []}) + "\n")
        summary3, results3 = run_pass(tmp, tmp / "memory/falsifier/close_rate.jsonl", 7.0)
        r3 = [r for r in results3 if r["id"].endswith(f"watcher_{s3}.md")][0]
        bc_rows2 = [l for l in _read_lines(tmp / "memory/falsifier/close_rate.jsonl")
                    if '"breadcrumb_close"' in l]
        check("upgrade: bc3 seen -> closed on rerun", r3["status"] == "closed")
        check("append-only: 8 breadcrumb rows after upgrade", len(bc_rows2) == 8,
              f"got {len(bc_rows2)}")
        check("close_rate_settled upgraded to 5/6 == 0.8333",
              summary3["close_rate_settled"] == 0.8333)
        print(f"\n  SELFTEST {'PASS' if ok else 'FAIL'} ({tmp})")
        return 0 if ok else 1
    finally:
        if ok:
            shutil.rmtree(tmp, ignore_errors=True)


# --------------------------------------------------------------------- main
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Watcher breadcrumb close-rate counter (read-only pass)")
    ap.add_argument("--root", default=str(ROOT_DEFAULT), help="store root (default: repo)")
    ap.add_argument("--ledger", default=None, help="ledger path (default: <root>/memory/falsifier/close_rate.jsonl)")
    ap.add_argument("--window-days", type=float, default=7.0)
    ap.add_argument("--json", action="store_true", help="print summary JSON")
    ap.add_argument("--selftest", action="store_true", help="synthetic proof against a temp store")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()

    root = Path(args.root).resolve()
    ledger = Path(args.ledger) if args.ledger else root / "memory" / "falsifier" / "close_rate.jsonl"
    summary, results = run_pass(root, ledger, args.window_days)
    if args.json:
        print(json.dumps({"summary": summary, "results": [
            {k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in r.items()}
            for r in results]}, ensure_ascii=False, indent=1, default=str))
    else:
        s = summary["store"]
        print(f"falsifier-counter: crumbs={summary['total']} activity_rows={s['activity_rows']} rare_tokens={s['rare_tokens']}")
        print(f"  closed={summary['closed']} seen={summary['seen']} open={summary['open']} expired={summary['expired']}")
        rate_w = summary["close_rate_week"]
        rate_s = summary["close_rate_settled"]
        print(f"  close_rate(week)={rate_w if rate_w is not None else 'n/a'} "
              f"close_rate(settled)={rate_s if rate_s is not None else 'n/a'} "
              f"median_tta_min={summary['median_tta_min'] if summary['median_tta_min'] is not None else 'n/a'}")
        for lane, d in sorted(summary["per_lane"].items()):
            print(f"  lane {lane}: {d['closed']}/{d['total']} closed")
        print(f"  ledger: {summary['ledger']['path']} (+{summary['ledger']['rows_written']} rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
