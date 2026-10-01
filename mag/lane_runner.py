"""lane_runner — the in-cage, headless lane engine (container-native lanes).

Operator order 2026-09-04 evening: agents spawning terminals on the shared desktop
is a defect class — recurring work must be HEADLESS and IN THE CONTAINERS
(headless-only + docker-not-desktop, 2026-08-25/26). This module is the
container-native successor of the ZCode-scheduled lane tasks: it runs INSIDE
mag-sovereign via `docker exec`, opens no window on any OS, and drives the lanes
off the same file chassis (queue/lanes/<lane>/{inbox.jsonl,surface.md,trail.jsonl}).

Laws wired in:
- LAW-058 PIN-CHECK: free lanes only — this runner refuses any paid-lane call by
  construction (single flash helper, z_ai3 Lite, thinking off).
- LAW-056 COUNTER-TEETH: economist RED flags escalate to the operator inbox row.
- LAW-055 HUMAN-PACED: external fetches are few, timed out short, never looped,
  and pass the SSRF guard (https only, public IPs only, redirects refused).
- ADOPT-2 HANDOFF GATE: every inbox drop is gated (schema/ttl/anchor) before the
  lane acts; gate verdicts are trail rows.

Usage:
  python mag/lane_runner.py --lane economist --once   # one cycle, one lane
  python mag/lane_runner.py --lane all --once         # every lane once
  python mag/lane_runner.py --daemon                  # the schedule loop (in-cage)

The android lane is NOT schedulable in-cage (adb/emulator are host-bound); it
stays a seat/manual lane by design.
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# in-cage imports (models/, mag/ siblings) resolve from the repo root:
sys.path.insert(0, str(ROOT))

LANES = ROOT / "queue" / "lanes"
STATIC = ROOT / "dashboard" / "static"
LOG = ROOT / "logs" / "lane_scheduler.log"
PIDFILE = ROOT / "logs" / "lane_scheduler.pid"

# CADENCE: minutes for recurring lanes, "HH:MM" local for daily lanes.
SCHEDULE = {
    "research": 15,
    "builder": 30,
    "day_work": 30,
    "economist": "06:00",
    "bard_ledger": "20:00",
    "elder": "12:00",
    # "night" is composite (monitor + sweep + march receipt), 23:00-09:00 window.
    "night": "23:00",
    # prose-debt census: daily in the quiet window, before the economist.
    "prose": "05:30",
    # media harvest: drains state/art_queue.jsonl (spend-gated by the queue).
    "forge": "12:00",
    # THE WATCHER: one free model experiencing the fleet feed, dropping breadcrumbs.
    "watcher": "30",
    # ARXIV HARVEST: the day's journals, recorded, mined against ourselves.
    "harvest": "06:30",
}
STALLED_HOURS = 2.0


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _ts() -> str:
    return _now().strftime("%Y-%m-%dT%H:%M:%SZ")


def _trail(lane: str, event: str, detail: str, artifacts: list | None = None) -> None:
    lane_dir = LANES / lane
    lane_dir.mkdir(parents=True, exist_ok=True)
    row = {"ts": _ts(), "actor": f"{lane}-cage", "event": event,
           "detail": detail[:400], "artifacts": artifacts or []}
    with (lane_dir / "trail.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _surface_append(lane: str, text: str) -> None:
    p = LANES / lane / "surface.md"
    with p.open("a", encoding="utf-8") as f:
        f.write(text.rstrip() + "\n")


def _state(lane: str) -> dict:
    p = LANES / lane / "runner_state.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return {}
    return {}


def _save_state(lane: str, st: dict) -> None:
    st.setdefault("seat", lane)
    p = LANES / lane / "runner_state.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")


def _mirror(lane: str) -> None:
    """Mirror trail + surface to dashboard/static (the operator's board)."""
    lane_dir = LANES / lane
    try:
        (STATIC / "trails").mkdir(parents=True, exist_ok=True)
        (STATIC / "lanes").mkdir(parents=True, exist_ok=True)
        src_t = lane_dir / "trail.jsonl"
        src_s = lane_dir / "surface.md"
        if src_t.exists():
            (STATIC / "trails" / f"{lane}.jsonl").write_text(
                src_t.read_text(encoding="utf-8"), encoding="utf-8")
        if src_s.exists():
            (STATIC / "lanes" / f"{lane}.md").write_text(
                src_s.read_text(encoding="utf-8"), encoding="utf-8")
    except Exception as e:  # noqa: BLE001
        _log(f"mirror fail {lane}: {e}")


def _log(msg: str) -> None:
    line = f"{_ts()} {msg}"
    print(line, flush=True)
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:  # noqa: BLE001
        pass


# ------------------------------------------------------------------ SSRF guard
class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):  # noqa: ANN002, ANN003
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def _safe_https_url(url: str) -> bool:
    """Mimosa SSRF guard: https only, host must resolve to a PUBLIC address,
    redirects refused. Blocks private/loopback/link-local/metadata targets."""
    try:
        p = urllib.parse.urlparse(url)
        if p.scheme != "https" or not p.hostname:
            return False
        for info in socket.getaddrinfo(p.hostname, 443, proto=socket.IPPROTO_TCP):
            ip = ipaddress.ip_address(info[4][0])
            if (ip.is_private or ip.is_loopback or ip.is_link_local
                    or ip.is_reserved or ip.is_multicast or ip.is_unspecified):
                return False
        return True
    except Exception:  # noqa: BLE001
        return False


# ---------------------------------------------------------------- handoff gate
def gate_drop(item: dict, lane: str) -> tuple[bool, list[str]]:
    """ADOPT-2 handoff gate (charter clause 9): one atomic validation per inbox
    drop BEFORE the lane acts. Returns (ok, reasons); every verdict is trailed."""
    reasons: list[str] = []
    for field in ("ts", "from", "task", "where", "why"):
        if not item.get(field):
            reasons.append(f"missing:{field}")
    ttl = item.get("ttl")
    if ttl:
        try:
            exp = datetime.fromisoformat(str(ttl).replace("Z", "+00:00"))
            if _now() > exp:
                reasons.append("ttl:expired")
        except Exception:  # noqa: BLE001
            reasons.append("ttl:unparseable")
    else:
        reasons.append("ttl:missing")
    anchor = item.get("anchor")
    if anchor and not (ROOT / str(anchor)).exists():
        reasons.append(f"anchor:missing({anchor})")
    ok = not reasons
    _trail(lane, "GATE_VERDICT",
           f"{str(item.get('task', '?'))[:80]} -> {'PASS' if ok else 'FAIL: ' + ','.join(reasons)}",
           [str(item.get("anchor", ""))])
    return ok, reasons


# ----------------------------------------------------- gate_verdict_v2 (B2-111)
# Three-axis verdict schema + two-band cascade (build doc sections 1-2,
# watch/inbox/BURN_JUDGE_LANE_BUILD_20260925.md; thresholds frozen at the B2-32
# registration in configs/lanes.yaml gate_verdict_v2). THE JUDGE NEVER MOVES ITS
# OWN GATE: tau, band axes and escalation policy are read ONLY from the yaml
# block on every call; no function below takes a threshold parameter and no
# judge-supplied field can override one. A derivation-class failure routes to
# band_derivation (always_escalate); everything else runs band_routine
# (accept iff failure_class == none AND every band axis score >= tau).
def load_gate_block() -> dict:
    """Read the frozen gate_verdict_v2 registration from configs/lanes.yaml.
    Refuses (raises) when the block is missing or malformed: there is no
    code-side fallback tau, the block is the only gate owner."""
    import yaml
    cfg = yaml.safe_load((ROOT / "configs" / "lanes.yaml").read_text(encoding="utf-8"))
    block = (cfg or {}).get("gate_verdict_v2")
    if not isinstance(block, dict):
        raise RuntimeError("gate_verdict_v2 block missing from configs/lanes.yaml")
    cascade = block.get("cascade")
    if not isinstance(cascade, dict) or "band_routine" not in cascade:
        raise RuntimeError("gate_verdict_v2.cascade.band_routine missing")
    band = cascade["band_routine"]
    if not isinstance(band.get("axes"), list) or not band["axes"]:
        raise RuntimeError("gate_verdict_v2 band_routine axes missing")
    tau = band.get("tau")
    if not isinstance(tau, (int, float)) or isinstance(tau, bool) or not 0.0 <= float(tau) <= 1.0:
        raise RuntimeError("gate_verdict_v2 band_routine tau missing or out of range")
    return block


def build_gate_verdict(lane: str, task_ref: str, axes: dict, judge_seat: str,
                       failure_class: str = "none", failure_detail: str = "",
                       escalated_from: str | None = None) -> dict:
    """Construct one verdict per the build doc section 1 JSON contract. Refuses
    (raises) on schema violations: score/confidence outside 0.0..1.0, a
    non-1.0 score without its verbatim evidence quote (the evidence-quote
    falsifier law), an unknown judge seat, or an unknown failure_class."""
    block = load_gate_block()
    seats = block.get("judge_seats") or []
    if judge_seat not in seats:
        raise ValueError(f"judge_seat {judge_seat!r} not in gate_verdict_v2.judge_seats")
    if failure_class not in ("infra", "merit", "none"):
        raise ValueError(f"failure_class {failure_class!r} not in infra|merit|none")
    schema_axes = block.get("axes") or []
    if sorted(axes) != sorted(schema_axes):
        raise ValueError(f"axes {sorted(axes)} != gate_verdict_v2.axes {sorted(schema_axes)}")
    out_axes: dict = {}
    for name in schema_axes:
        a = axes.get(name)
        if not isinstance(a, dict):
            raise ValueError(f"axis {name}: not a score/confidence/evidence_quote object")
        score, conf = a.get("score"), a.get("confidence")
        for label, val in (("score", score), ("confidence", conf)):
            if isinstance(val, bool) or not isinstance(val, (int, float)) \
                    or not 0.0 <= float(val) <= 1.0:
                raise ValueError(f"axis {name}: {label} must be a number in 0.0..1.0")
        quote = str(a.get("evidence_quote") or "")
        if float(score) < 1.0 and not quote.strip():
            raise ValueError(f"axis {name}: non-1.0 score without a verbatim evidence quote")
        out_axes[name] = {"score": float(score), "confidence": float(conf),
                          "evidence_quote": quote}
    return {
        "verdict_id": str(uuid.uuid4()),
        "ts_utc": _ts(),
        "lane": lane,
        "task_ref": task_ref,
        "axes": out_axes,
        "failure_class": failure_class,
        "failure_detail": str(failure_detail)[:200],
        "judge_seat": judge_seat,
        "escalated_from": escalated_from,
    }


def apply_cascade(verdict: dict, block: dict | None = None,
                  requires_derivation: bool = False) -> dict:
    """Two-band cascade (B2-32 registration; falsifier F1 needs both bands
    live). Band selection: a task whose verdict requires checking a derivation
    (math, protocol proofs, security claims) goes to band_derivation (policy
    always_escalate); everything else to band_routine (accept iff
    failure_class == none AND every band axis score >= tau, else escalate).
    tau/band axes come only from the block; the judge cannot pass one in.
    Returns {decision, band, tau} where decision is accept|escalate."""
    block = block or load_gate_block()
    cascade = block["cascade"]
    if requires_derivation:
        derivation = cascade.get("band_derivation") or {}
        policy = str(derivation.get("policy") or "always_escalate")
        if policy == "always_escalate":
            return {"decision": "escalate", "band": "band_derivation", "tau": None}
        raise RuntimeError(f"band_derivation policy {policy!r} unsupported")
    band = cascade["band_routine"]
    tau = float(band["tau"])
    if str(verdict.get("failure_class") or "none") != "none":
        return {"decision": "escalate", "band": "band_routine", "tau": tau}
    for name in band["axes"]:
        a = (verdict.get("axes") or {}).get(name)
        s = a.get("score") if isinstance(a, dict) else None
        if isinstance(s, bool) or not isinstance(s, (int, float)) or float(s) < tau:
            return {"decision": "escalate", "band": "band_routine", "tau": tau}
    return {"decision": "accept", "band": "band_routine", "tau": tau}


def gate_drop_v2(lane: str, task_ref: str, axes: dict, judge_seat: str,
                 failure_class: str = "none", failure_detail: str = "",
                 escalated_from: str | None = None,
                 requires_derivation: bool = False) -> tuple[str, dict]:
    """The V2 emission path: build the three-axis verdict, run the two-band
    cascade, trail a GATE_VERDICT_V2 row (nested `verdict` object, the shape
    _trail_verdicts and the cluster organ consume). Returns (decision, verdict)
    with decision accept|escalate; escalation routing to the frontier seat is
    the caller's dispatch, the gate itself never moves."""
    verdict = build_gate_verdict(lane, task_ref, axes, judge_seat,
                                 failure_class=failure_class,
                                 failure_detail=failure_detail,
                                 escalated_from=escalated_from)
    verdict["requires_derivation"] = bool(requires_derivation)
    call = apply_cascade(verdict, requires_derivation=requires_derivation)
    verdict["decision"] = call["decision"]
    verdict["band"] = call["band"]
    # one trail row carrying the nested verdict object: the shape _trail_verdicts
    # and the cluster organ consume
    lane_dir = LANES / lane
    row = {"ts": _ts(), "actor": f"{lane}-cage", "event": "GATE_VERDICT_V2",
           "detail": f"verdict {verdict['verdict_id']} {call['decision']}",
           "artifacts": [task_ref], "verdict": verdict}
    with (lane_dir / "trail.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return call["decision"], verdict


def _inbox_new(lane: str) -> list[dict]:
    """New inbox drops since the last processed offset (gate applies to each)."""
    inbox = LANES / lane / "inbox.jsonl"
    if not inbox.exists():
        return []
    st = _state(lane)
    off = int(st.get("inbox_offset", 0))
    lines = inbox.read_text(encoding="utf-8").splitlines()
    items = []
    for ln in lines[off:]:
        ln = ln.strip()
        if not ln:
            off += 1
            continue
        try:
            items.append(json.loads(ln))
        except Exception:  # noqa: BLE001
            pass
        off += 1
    _save_state(lane, {**st, "inbox_offset": off})
    return items


# -------------------------------------------------------------- cluster organ
# Build doc sections 2 + 2b (watch/inbox/BURN_JUDGE_LANE_BUILD_20260925.md;
# 2b amendment filed 2026-09-26 by burn lane B2-34 BEFORE this code): cluster
# before propose. CLUSTER_REPORT every CLUSTER_WINDOW_N verdicts, keyed
# failure_class + normalized failure_detail; the infra repeat-rate alarm makes
# the report a pipe P1 fix-order, never a chooser task; merit rows route to the
# chooser. Two detectors ride the same report (2b): form_over_substance and
# confident_and_wrong.
CLUSTER_WINDOW_N = 20       # build doc section 2: N=20 verdicts per window
INFRA_REPEAT_ALARM = 0.60   # build doc section 2: infra repeat > 60% -> P1 fix-order
MIN_RATE_EVENTS = 10        # pass-e convention (BURN_judge-lane-spec_20260926_e.md):
                            # never gate on a rate below 10 events
FOS_RECEIPT_HIGH = 0.90     # 2b form_over_substance: receipt_completeness >= 0.90
FOS_BUILD_LOW = 0.50        #   ...while build_quality <= 0.50 (elaborate-wrong shape)
CAW_CONF_HIGH = 0.90        # 2b confident_and_wrong: overturned conf >= 0.90 verdicts
CAW_TRIPWIRE = 0.15         # 2b / falsifier F2 (B2_08): > 15% overturn -> tripwire
SPOTCHECK_SAMPLE_K = 5      # 2b/F2 spot-check protocol (B2-193, SPOTCHECK_PROTOCOL_20260926.md):
                            # every CLUSTER_REPORT carries up to K high-confidence ids to re-check
CLUSTER_TAU = 0.90          # mirrors gate_verdict_v2.cascade.band_routine.tau (B2-32)

# pinned verbs per build doc section 2 ("keep the verb") plus the deterministic
# gate reason families gate_drop emits (missing:/ttl:/anchor:)
_PINNED_VERBS = ("timeout", "200-error-body", "404", "empty_content", "parse-fail",
                 "unjudgeable", "missing:", "ttl:", "anchor:")


def normalize_detail(detail: str) -> str:
    """Build doc section 2 keying: strip lane ids, ts, paths, numbers; keep the
    verb (timeout, 200-error-body, 404, empty_content, parse-fail)."""
    s = str(detail or "").lower()
    s = re.sub(r"\d{4}-\d{2}-\d{2}[t ]\d{2}:\d{2}(:\d{2})?(\.\d+)?(z|\+00:00)?", " ", s)
    s = re.sub(r"[a-z]:\\[^\"' ]*", " ", s)   # windows paths
    s = re.sub(r"/[\w.\-]+", " ", s)          # posix paths
    for verb in _PINNED_VERBS:
        if verb in s:
            return verb.rstrip(":")
    s = re.sub(r"\b\d+(\.\d+)?\b", " ", s)    # bare numbers
    s = re.sub(r"[^a-z_-]+", " ", s).strip()
    return " ".join(s.split()[:6]) or "unclassified"


def _axes_scores(v: dict) -> dict:
    axes = v.get("axes")
    return axes if isinstance(axes, dict) else {}


def _axis_score(v: dict, axis: str):
    a = _axes_scores(v).get(axis)
    if not isinstance(a, dict):
        return None
    s = a.get("score")
    if isinstance(s, bool) or not isinstance(s, (int, float)):
        return None
    return float(s)


def _verdict_max_conf(v: dict):
    confs = [a.get("confidence") for a in _axes_scores(v).values()
             if isinstance(a, dict) and isinstance(a.get("confidence"), (int, float))
             and not isinstance(a.get("confidence"), bool)]
    return max(confs) if confs else None


def _verdict_decision(v: dict):
    """2b decision rule: accept iff every axis score >= CLUSTER_TAU AND
    failure_class == "none"; anything else rejects. None = undecidable row
    (no parseable axes), never counted as an overturn in either direction."""
    if str(v.get("failure_class") or "none") != "none":
        return "reject"
    axes = _axes_scores(v)
    if not axes:
        return None
    for name in axes:
        s = _axis_score(v, name)
        if s is None or s < CLUSTER_TAU:
            return "reject"
    return "accept"


def cluster_step(verdicts: list, prev_keys: dict | None = None) -> dict:
    """Pure CLUSTER_REPORT computation over one window of verdict rows (the
    GATE_VERDICT_V2 nested `verdict` objects). Build doc section 2: counts per
    class, cross-window repeat rate per class, intra-window repeat beside it
    (reported, never gated, per pass d), infra alarm routing. Section 2b: the
    form_over_substance and confident_and_wrong detectors. Reads nothing,
    writes nothing. Rates are computed only at >= MIN_RATE_EVENTS events
    (pass-e convention); counts are always reported."""
    prev_raw = prev_keys or {}
    prev = {c: set(k) for c, k in prev_raw.items()}
    has_prev = bool(prev)   # no previous window on file: cross-window rate is
                            # undefined (None), never reported as a fake 0.0
    rows = [v for v in verdicts if isinstance(v, dict)]
    counts: dict = {}
    keys_by_class: dict = {}
    detail_hits: dict = {}
    for v in rows:
        cls = str(v.get("failure_class") or "none")
        counts[cls] = counts.get(cls, 0) + 1
        d = normalize_detail(str(v.get("failure_detail") or ""))
        keys_by_class.setdefault(cls, set()).add(d)
        detail_hits[(cls, d)] = detail_hits.get((cls, d), 0) + 1
    repeat: dict = {}
    intra: dict = {}
    for cls, cnt in counts.items():
        pk = prev.get(cls, set())
        rep_rows = sum(n for (c, d), n in detail_hits.items() if c == cls and d in pk)
        repeat[cls] = (round(rep_rows / cnt, 4)
                       if cnt >= MIN_RATE_EVENTS and has_prev else None)
        intra[cls] = sum(n for (c, _), n in detail_hits.items() if c == cls and n >= 2)
    infra_rep = repeat.get("infra")
    alarm = infra_rep is not None and infra_rep > INFRA_REPEAT_ALARM
    # 2b detector 1: form_over_substance (a complete receipt is not a built
    # thing; spot-check, never auto-accept). Explicit None checks: 0.0 scores
    # are real scores (build_quality 0.0 is the extreme low case), not missing.
    def _fos_match(v: dict) -> bool:
        rc = _axis_score(v, "receipt_completeness")
        bq = _axis_score(v, "build_quality")
        return rc is not None and bq is not None and rc >= FOS_RECEIPT_HIGH and bq <= FOS_BUILD_LOW

    fos_ids = [str(v.get("verdict_id") or "") for v in rows if _fos_match(v)]
    # 2b detector 2: confident_and_wrong (escalation overturns of
    # confidence >= CAW_CONF_HIGH verdicts; distribution statistics are not
    # calibration)
    by_id = {str(v.get("verdict_id") or ""): v for v in rows if v.get("verdict_id")}
    caw_events = caw_overturns = 0
    for v in rows:
        pid = str(v.get("escalated_from") or "")
        parent = by_id.get(pid)
        if parent is None or parent is v:
            continue
        pconf = _verdict_max_conf(parent)
        if pconf is None or pconf < CAW_CONF_HIGH:
            continue
        caw_events += 1
        pd, cd = _verdict_decision(parent), _verdict_decision(v)
        if pd is not None and cd is not None and pd != cd:
            caw_overturns += 1
    caw_rate = (round(caw_overturns / caw_events, 4)
                if caw_events >= MIN_RATE_EVENTS else None)
    # 2b/F2 spot-check sampler (B2-193, 2026-09-26): the caw detector above is
    # an escalation-parent PROXY; the true falsifier F2 needs independent
    # spot-checks. Every CLUSTER_REPORT therefore carries the deterministic
    # sample to execute: the first SPOTCHECK_SAMPLE_K window verdicts whose
    # max axis confidence is >= CAW_CONF_HIGH. Who executes, where results
    # are filed, and the F2 denominator are pinned in
    # watch/inbox/SPOTCHECK_PROTOCOL_20260926.md; the proxy rate above stays
    # the automatic tripwire, the spot-check rate is the calibration verdict.
    spot_ids = []
    for v in rows:
        mc = _verdict_max_conf(v)
        if mc is not None and mc >= CAW_CONF_HIGH and v.get("verdict_id"):
            spot_ids.append(str(v.get("verdict_id")))
            if len(spot_ids) >= SPOTCHECK_SAMPLE_K:
                break
    return {
        "tool": "cluster_report",
        "window_n": len(rows),
        "counts_by_class": counts,
        "repeat_rate_by_class": repeat,
        "intra_window_repeat_by_class": intra,
        "route": "pipe_p1" if alarm else "split",
        "route_note": ("infra repeat above INFRA_REPEAT_ALARM: report is a pipe "
                       "P1 fix-order, not a chooser task" if alarm else
                       "infra rows -> pipe repair; merit rows -> chooser"),
        "form_over_substance": {
            "flagged": bool(fos_ids),
            "matches": len(fos_ids),
            "verdict_ids": fos_ids[:10],
            "action": "spot_check_never_auto_accept",
        },
        "spot_check": {
            "sample_ids": spot_ids,
            "sample_k": SPOTCHECK_SAMPLE_K,
            "population": ("verdicts with max axis confidence >= "
                           f"{CAW_CONF_HIGH} (the F2 denominator)"),
            "protocol": "watch/inbox/SPOTCHECK_PROTOCOL_20260926.md",
        },
        "confident_and_wrong": {
            "events": caw_events,
            "overturns": caw_overturns,
            "rate": caw_rate,
            "rate_note": (None if caw_rate is not None else
                          f"below MIN_RATE_EVENTS={MIN_RATE_EVENTS}: events only, never gated"),
            "calibration_tripwire": bool(caw_rate is not None and caw_rate > CAW_TRIPWIRE),
        },
    }


def _trail_verdicts(lane: str) -> list:
    """All GATE_VERDICT_V2 nested verdict objects in the lane trail, in order."""
    p = LANES / lane / "trail.jsonl"
    out: list = []
    if not p.exists():
        return out
    for ln in p.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            row = json.loads(ln)
        except Exception:  # noqa: BLE001
            continue
        if row.get("event") == "GATE_VERDICT_V2" and isinstance(row.get("verdict"), dict):
            out.append(row["verdict"])
    return out


def cluster_report_step(lane: str) -> str:
    """Rolling cluster organ (build doc sections 2 + 2b). Emits one
    CLUSTER_REPORT trail + surface row per CLUSTER_WINDOW_N new verdicts,
    carrying the two B2-34 detectors. Dormant while the lane emits no
    GATE_VERDICT_V2 rows: the V2 wiring is a separate gated lane
    (configs/lanes.yaml gate_verdict_v2 comment), so zero verdicts means zero
    reports, never an invented one."""
    verdicts = _trail_verdicts(lane)
    st = _state(lane)
    done = int(st.get("cluster_done", 0))
    pending = verdicts[done:]
    if not pending:
        return "dormant(0 pending)"
    prev_keys = st.get("cluster_prev_keys") or {}
    emitted = 0
    while len(pending) >= CLUSTER_WINDOW_N:
        window, pending = pending[:CLUSTER_WINDOW_N], pending[CLUSTER_WINDOW_N:]
        rep = cluster_step(window, prev_keys)
        prev_keys = {}
        for v in window:
            cls = str(v.get("failure_class") or "none")
            prev_keys.setdefault(cls, set()).add(
                normalize_detail(str(v.get("failure_detail") or "")))
        prev_keys = {c: sorted(ks) for c, ks in prev_keys.items()}
        done += len(window)
        emitted += 1
        caw = rep["confident_and_wrong"]
        summary = (f"win={rep['window_n']} classes="
                   + ",".join(f"{c}:{n}" for c, n in sorted(rep["counts_by_class"].items()))
                   + f" route={rep['route']} fos={rep['form_over_substance']['matches']}"
                   + f" caw={caw['overturns']}/{caw['events']}"
                   + f" tripwire={caw['calibration_tripwire']}")
        _trail(lane, "CLUSTER_REPORT", summary)
        _surface_append(lane, f"\n## CLUSTER_REPORT ({_ts()})\n```json\n"
                        f"{json.dumps(rep, ensure_ascii=False, indent=1, sort_keys=True)}\n```\n")
    if emitted:
        st = _state(lane)
        _save_state(lane, {**st, "cluster_done": done, "cluster_prev_keys": prev_keys})
    return f"windows={emitted} pending={len(pending)}"


# ------------------------------------------------------------------ flash call
_FLASH_ENDPOINT = "https://api.z.ai/api/paas/v4/chat/completions"
_FLASH_KEY_VARS = ("ZAI_API_KEY_L", "ZAI_API_KEY_LITE", "ZAI_API_KEY")


def flash_call(system: str, user: str, max_tokens: int = 1536) -> str:
    """LAW-058 pin-check baked in: the ONLY model door here is the Lite coding-plan
    key (ZAI_API_KEY_L, the Calcifer lane) on glm-5.3-flash. CORRECTED 2026-09-05:
    this is NOT the fleet's $0 lane — the promo verdict proved Lite metered
    (10,000 credits/wk real credits; the "zero-metered night window" belief was
    falsified). Paced by mag/lite_guard.py (law 15 daily ceiling), past it raises.
    5.x law: thinking cannot be disabled — reasoning_effort low + max_tokens >= 1536
    (epoch-1 medicine). march_228.py's proven request shape; endpoint passes the
    SSRF guard; redirects refused (_OPENER)."""
    from mag import lite_guard
    g = lite_guard.check("lane_runner")
    if not g["ok"]:
        raise RuntimeError(g["deny"])
    key = next((os.environ[v] for v in _FLASH_KEY_VARS if os.environ.get(v)), "")
    if not key:
        raise RuntimeError("no Lite key in cage env (flash lane down)")
    if not _safe_https_url(_FLASH_ENDPOINT):
        raise ValueError("blocked: endpoint failed SSRF guard (scheme/host/resolved-IP)")
    body = {"model": "glm-5.3-flash",
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}],
            "max_tokens": max_tokens, "temperature": 0.2,
            "thinking": {"type": "enabled"}, "reasoning_effort": "low"}
    req = urllib.request.Request(_FLASH_ENDPOINT, data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json",
                                          "Authorization": "Bearer " + key})
    with _OPENER.open(req, timeout=120) as r:
        data = json.loads(r.read())
    _u = data.get("usage") or {}
    lite_guard.record("lane_runner",
                      int(_u.get("prompt_tokens") or 0) + int(_u.get("completion_tokens") or 0))
    msg = ((data.get("choices") or [{}])[0].get("message", {}) or {})
    content = (msg.get("content") or "").strip()
    if not content:
        # REASONING-BUDGET RESCUE (2026-09-23, gopher-proven): the thinking channel
        # ate the token budget and content came back empty. One retry with thinking
        # disabled and doubled tokens — the gopher bench proved thinking-disabled
        # works on this endpoint family (glm-4.7-flash, 2026-09-23).
        try:
            body2 = dict(body)
            body2["thinking"] = {"type": "disabled"}
            body2["max_tokens"] = max_tokens * 2
            req2 = urllib.request.Request(_FLASH_ENDPOINT, data=json.dumps(body2).encode("utf-8"),
                                          headers={"Content-Type": "application/json",
                                                   "Authorization": "Bearer " + key})
            with _OPENER.open(req2, timeout=180) as r2:
                d2 = json.loads(r2.read())
            _u2 = d2.get("usage") or {}
            lite_guard.record("lane_runner",
                              int(_u2.get("prompt_tokens") or 0) + int(_u2.get("completion_tokens") or 0))
            m2 = ((d2.get("choices") or [{}])[0].get("message", {}) or {})
            content = (m2.get("content") or "").strip() or (m2.get("reasoning_content") or "").strip()
        except Exception:  # noqa: BLE001 — rescue attempt, never a new failure mode
            pass
    # PASSIVE THOUGHT BANK (2026-09-05): one choke point, mag/thought_bank.py —
    # verbatim reasoning to memory/thinking/, silent-fail, all models by design.
    try:
        from mag.thought_bank import bank_response
        bank_response("glm-5.3-flash", user, data, lane="cage")
    except Exception:  # noqa: BLE001 — bank, not break
        pass
    return content


# ----------------------------------------------------------------- lane cycles
def _run_script(path: str, timeout: int = 600) -> tuple[int, str]:
    p = ROOT / path
    if not p.exists():
        return 2, f"missing: {path}"
    try:
        r = subprocess.run([sys.executable, str(p)], capture_output=True,
                           text=True, timeout=timeout, cwd=str(ROOT))
        out = ((r.stdout or "") + (r.stderr or ""))[-1500:]
        return r.returncode, out
    except Exception as e:  # noqa: BLE001
        return 1, f"{type(e).__name__}: {e}"


def _latest_sweep_report() -> "Path | None":
    sweeps = sorted((ROOT / "watch" / "usage_sweeps").glob("USAGE_SWEEP_*.md"))
    return sweeps[-1] if sweeps else None


def _sweep_flag_count(p: "Path") -> int:
    try:
        text = p.read_text(encoding="utf-8")
    except Exception:  # noqa: BLE001
        return -1
    return len([ln for ln in text.splitlines()
                if "OUTPUT-RATIO:" in ln or "PIN-EXPIRY:" in ln or "CONTEXT-DEBT:" in ln])


def cycle_economist() -> str:
    # hunger ledger: cage copy first (watch/ is mounted; scripts/ is not), then canonical.
    rc2, out2 = _run_script("watch/cage_bin/hunger_ledger.py")
    if rc2 == 2:
        rc2, out2 = _run_script("scripts/hunger_ledger.py")
    # LAW-056 teeth: read the newest HOST-produced sweep report (the sweep itself is
    # host-db-bound: it reads ~/.zcode/cli/db/db.sqlite which no container sees —
    # parked pending an operator-sanctioned data door). Escalate ONCE per report.
    rep = _latest_sweep_report()
    flags = _sweep_flag_count(rep) if rep else -1
    st = _state("economist")
    if rep is not None and flags > 0 and st.get("escalated_sweep") != rep.name:
        _surface_append("economist",
            f"\n## CAGE ESCALATION {_ts()}\nusage sweep {rep.name} FLAGS={flags} — "
            f"premium burn law violation (see the report)\n")
        esc = {"ts": _ts(), "from": "lane_runner",
               "task": "OPERATOR INBOX: usage sweep flagged premium burn (see economist surface)",
               "where": f"watch/usage_sweeps/{rep.name}",
               "why": "LAW-056 counter-teeth: RED flag auto-escalation",
               "ttl": "", "anchor": "queue/lanes/economist/surface.md"}
        try:
            with (LANES / "day_work" / "inbox.jsonl").open("a", encoding="utf-8") as f:
                f.write(json.dumps(esc, ensure_ascii=False) + "\n")
        except Exception:  # noqa: BLE001
            pass
        _save_state("economist", {**st, "escalated_sweep": rep.name})
    _trail("economist", "CYCLE",
           f"hunger rc={rc2}; sweep={rep.name if rep else 'none'} flags={flags}; {out2[-160:]}")
    return f"hunger rc={rc2}, sweep_flags={flags}"


def cycle_research() -> str:
    rc, out = _run_script("watch/monitor_lane.py", timeout=300)
    _trail("research", "MONITOR", f"monitor_lane rc={rc}: {out[-250:]}")
    n = 0
    for item in _inbox_new("research"):
        ok, why = gate_drop(item, "research")
        if not ok:
            continue
        # LAW-055: one gentle fetch per drop, short timeout, redirects refused.
        url = str(item.get("url") or item.get("where") or "")
        title = url[:120]
        if url.startswith("https://") and _safe_https_url(url):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with _OPENER.open(req, timeout=8) as resp:
                    head = resp.read(4096).decode("utf-8", "ignore")
                a, b = head.find("<title>"), head.find("</title>")
                if 0 <= a < b:
                    title = head[a + 7:b][:160]
            except Exception as e:  # noqa: BLE001
                title = f"fetch-failed({type(e).__name__})"
        elif url.startswith("http"):
            title = "blocked:ssrf-guard"
        score = ""
        try:
            score = flash_call(
                "You triage research links for an AI-agent fleet. Reply EXACTLY: "
                "SCORE: <0-10> | ONE-LINE: <what it is> | VERDICT: <CARD|SHELF|SKIP>",
                f"Link: {url}\nTitle: {title}\nContext: {str(item.get('why'))[:300]}")
        except Exception as e:  # noqa: BLE001
            score = f"lane-down({e})"
        _surface_append("research", f"\n### DROP {str(item.get('task', ''))[:60]}\n"
                        f"- url: {url[:160]}\n- title: {title}\n- triage: {score}\n"
                        f"- gated: {'PASS' if ok else 'FAIL ' + ','.join(why)}\n")
        n += 1
    return f"monitor rc={rc}, drops gated={n}"


def cycle_builder() -> str:
    n = 0
    for item in _inbox_new("builder"):
        ok, why = gate_drop(item, "builder")
        _surface_append("builder",
            f"\n### GATED DROP {str(item.get('task', ''))[:70]}\n"
            f"- gate: {'PASS' if ok else 'FAIL ' + ','.join(why)}\n"
            f"- where: {item.get('where')}\n- ttl: {item.get('ttl')}\n"
            f"- state: {'QUEUED for in-cage build shift (window_throttle claim first)' if ok else 'REFUSED'}\n")
        n += 1
    _trail("builder", "CYCLE", f"drops gated={n}; queue on surface")
    return f"gated={n}"


def cycle_bard() -> str:
    today = _now().strftime("%Y%m%d")
    cards = sorted((ROOT / "watch").glob(f"*_{today}.md"))
    ledger = ROOT / "watch" / f"DAY_LEDGER_{_now().strftime('%Y-%m-%d')}.md"
    names = ", ".join(c.name for c in cards[-12:])
    row = (f"\n## CAGE ROW {_ts()}\n- cards today: {len(cards)}\n"
           f"- recent: {names}\n- source: watch/ glob (read, not invented)\n")
    try:
        with ledger.open("a", encoding="utf-8") as f:
            f.write(row)
        _trail("bard_ledger", "CYCLE", f"ledger row appended ({len(cards)} cards today)")
        return "row"
    except Exception as e:  # noqa: BLE001
        _trail("bard_ledger", "CYCLE_FAIL", str(e)[:200])
        return "fail"


def cycle_elder() -> str:
    today = _now().strftime("%Y%m%d")
    cards = sorted((ROOT / "watch").glob(f"*_{today}.md"))[-3:]
    if not cards:
        cards = sorted((ROOT / "watch").glob("*.md"),
                       key=lambda p: p.stat().st_mtime)[-3:]
    if not cards:
        _trail("elder", "CYCLE", "no cards to read")
        return "empty"
    digest = []
    for c in cards:
        try:
            digest.append(f"--- {c.name} ---\n" + c.read_text(encoding="utf-8")[:1200])
        except Exception:  # noqa: BLE001
            pass
    try:
        lens = flash_call(
            "You are the Elder lens: read fleet cards and give the emergent pattern in "
            "physics/compsci/esoteric anchors ONLY where real (name them). End with "
            "THE ELDER'S QUESTION: the question the fleet isn't asking. Label as lens, not claim.",
            "\n\n".join(digest)[:6000], max_tokens=1536)
    except Exception as e:  # noqa: BLE001
        lens = f"lane-down: {e}"
    # TRI-STATE TRAIL LAW (elder lens 2026-09-18; migration audit 2026-09-19):
    # the trail may not file a success-shaped CYCLE row when the lens died.
    # lane-down gets CYCLE_FAIL — and so does an EMPTY lens: the always-thinking
    # channel eats any sub-1536 budget and returns 200 with zero content
    # (flash_call law: max_tokens >= 1536). A sub-80-char body is not a lens.
    if lens.startswith("lane-down:") or len(lens.strip()) < 80:
        body = lens.strip() or "lane-down: HTTP 200 with empty content (thinking channel ate budget)"
        _surface_append("elder", f"\n## ELDER LENS (cage, {_ts()}) — LENS NOT CLAIM, Unproven\n"
                        f"{body}\n")
        _trail("elder", "CYCLE_FAIL", body[:200])
        return "lane-down"
    _surface_append("elder", f"\n## ELDER LENS (cage, {_ts()}) — LENS NOT CLAIM, Unproven\n"
                    f"{lens}\n")
    _trail("elder", "CYCLE", f"lens on {len(cards)} cards")
    return "lens"


def cycle_day_work() -> str:
    stalled = []
    # HANDSHAKES ARE LOANS (2026-09-05): an operator-unlocked gate with no
    # first-use receipt is a promise idling — surface it every cycle until we
    # drive it or it dies honestly.
    try:
        hs = ROOT / "state" / "handshakes.jsonl"
        if hs.exists():
            for line in hs.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                row = json.loads(line)
                if row.get("unlocked_at") and not row.get("first_use"):
                    stalled.append(f"handshake:{row.get('gate')}")
    except Exception as e:  # noqa: BLE001 — flagging must never break the mirror
        stalled.append(f"handshake-scan:{type(e).__name__}")
    for lane in SCHEDULE:
        if lane == "night":
            continue
        t = LANES / lane / "trail.jsonl"
        if not t.exists():
            continue
        age_h = (time.time() - t.stat().st_mtime) / 3600
        if age_h > STALLED_HOURS:
            stalled.append(f"{lane}({age_h:.1f}h)")
        _mirror(lane)
    for f in ("DAY_WORK_DIGEST.md",):
        src = ROOT / "watch" / f
        if src.exists():
            try:
                (STATIC / f).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
            except Exception:  # noqa: BLE001
                pass
    _trail("day_work", "CYCLE",
           f"mirrored {len(SCHEDULE) - 1} lanes; STALLED: {', '.join(stalled) if stalled else 'none'}")
    return f"mirrored, stalled={len(stalled)}"


def cycle_night() -> str:
    """Composite night cycle: monitor + usage sweep + march receipt.
    In-window guard (23:00-09:00 local), once per night, $0."""
    hour = _now().astimezone().hour
    if not (23 <= hour or hour < 9):
        return "out-of-window"
    st = _state("night")
    today = _now().strftime("%Y-%m-%d")
    if st.get("last_night") == today:
        return "already-ran"
    parts = []
    rc, _ = _run_script("watch/monitor_lane.py", timeout=300)
    parts.append(f"monitor rc={rc}")
    rc, _ = _run_script("watch/march_228.py", timeout=600)
    # march reads .env for its key — unmounted in-cage; an honest rc=2 is expected
    # until the operator sanctions an env door. Recorded, never faked.
    parts.append(f"march rc={rc}")
    _save_state("night", {**st, "last_night": today})
    _trail("night", "CYCLE", "night composite: " + "; ".join(parts))
    return "; ".join(parts)


def cycle_forge() -> str:
    """Media harvest lane: drain state/art_queue.jsonl through the dual-lane
    forge (grok primary, cogview fallback). Spend-gated by the queue — no
    queue, no spend. Gallery: dashboard/static/art/."""
    from mag.art_forge import forge_once
    r = forge_once(ROOT)
    _trail("forge", "CYCLE", f"forged={r.get('forged')} errors={len(r.get('errors') or [])}")
    return f"forged={r.get('forged')} left={r.get('left_in_queue', 0)} err={len(r.get('errors') or [])}"


def cycle_watcher() -> str:
    """THE WATCHER (2026-09-05): one feed, one free model, experiencing
    everything RESTfully — read snapshot, think, drop breadcrumb clues into
    lane inboxes. Clues are LEADS marked UNPROVEN; evidence-quoted or
    discarded. The environment watches itself; stigmergy does the steering."""
    from mag.single_feed import build_snapshot
    s = build_snapshot()
    md = (ROOT / "memory" / "feed" / "feed_snapshot.md").read_text(encoding="utf-8",
                                                                  errors="replace")
    system = ("You are THE WATCHER of a fleet of AI agents. You read one feed snapshot "
              "of everything the fleet did. Find only what is VISIBLE IN THE SNAPSHOT: "
              "(1) repeating shapes, (2) wrong assumptions (feed rows that contradict a "
              "claim), (3) TESUJI: a FAILURE in one lane whose key datum is exactly what "
              "a DIFFERENT lane needs to win — route the clue to THAT lane, stating what "
              "broke, the usable datum, and the win it enables. Output ONLY a JSON array, "
              "max 3 clues, each: {\"lane\": one of "
              "research|builder|day_work|economist|bard_ledger|elder|forge|prose, "
              "\"shape\": \"...\", \"evidence\": \"verbatim quote from the snapshot\", "
              "\"clue\": \"one-line breadcrumb for that lane's inbox\"}. No evidence "
              "quote, no clue. If nothing: [].")
    out = flash_call(system, md[:6000], max_tokens=900)
    clues = []
    try:
        i, j = out.find("["), out.rfind("]")
        if 0 <= i < j:
            parsed = json.loads(out[i:j + 1])
            clues = [c for c in parsed if isinstance(c, dict) and c.get("evidence")]
    except Exception:  # noqa: BLE001 — watcher output is leads, never law
        clues = []
    dropped = []
    for c in clues[:3]:
        lane = c.get("lane") if c.get("lane") in SCHEDULE else "day_work"
        inbox = ROOT / "queue" / "lanes" / lane / "INBOX"
        inbox.mkdir(parents=True, exist_ok=True)
        stamp = _now().strftime("%Y%m%dT%H%M%SZ")
        crumbs = (f"**WATCHER BREADCRUMB** (UNPROVEN lead — verify before acting) {stamp}\n\n"
                  f"- shape: {c.get('shape', '')}\n"
                  f"- evidence: `{str(c.get('evidence', ''))[:220]}`\n"
                  f"- clue: {c.get('clue', '')}\n")
        (inbox / f"watcher_{stamp}.md").write_text(crumbs, encoding="utf-8")
        _trail(lane, "WATCHER_CRUMB", str(c.get("clue", ""))[:160])
        dropped.append(f"{lane}:{str(c.get('clue', ''))[:60]}")
    return f"watched chars={s['chars']} clues={len(clues)} dropped={len(dropped)}"


def cycle_harvest() -> str:
    """ARXIV HARVEST (2026-09-05): the day's journals recorded to corpus/, massaged,
    mined against our interest map, top hits dropped to research. Truly stateless —
    the world's research becomes files any era can read."""
    from mag.arxiv_harvest import harvest
    r = harvest()
    _trail("harvest", "CYCLE", f"fetched={r['fetched']} new={r['new']} hits={r['hits']}")
    return f"fetched={r['fetched']} new={r['new']} hits={r['hits']}"


def cycle_prose() -> str:
    """Prose-debt census (2026-09-05, operator: 'no monkeypatches'): the debt as
    a measured queue — stale/fossil files, ghost refs, launcher-shaped fences —
    filed to watch/ so conversion-to-structure works a list, not a feeling."""
    from mag.prose_census import run_census
    s = run_census(ROOT)
    _trail("prose", "CYCLE",
           f"census files={s['files']} stale={s['stale']} fossil={s['fossil']} "
           f"ghost={s['ghost_refs']} launchers={s['launchers']}")
    return (f"census files={s['files']} stale={s['stale']} fossil={s['fossil']} "
            f"ghost={s['ghost_refs']} launchers={s['launchers']}")


CYCLES = {
    "research": cycle_research,
    "builder": cycle_builder,
    "economist": cycle_economist,
    "bard_ledger": cycle_bard,
    "elder": cycle_elder,
    "day_work": cycle_day_work,
    "night": cycle_night,
    "prose": cycle_prose,
    "forge": cycle_forge,
    "watcher": cycle_watcher,
    "harvest": cycle_harvest,
}


# ------------------------------------------------------------------ scheduling
def _due(lane: str) -> bool:
    st = _state(lane)
    last = st.get("last_run")
    now = _now().astimezone()
    cad = SCHEDULE.get(lane)
    if isinstance(cad, int):
        if not last:
            return True
        age = (_now() - datetime.fromisoformat(last)).total_seconds() / 60
        return age >= cad
    if isinstance(cad, str) and cad.count(":") == 1:
        hh, mm = (int(x) for x in cad.split(":"))
        if (now.hour, now.minute) < (hh, mm):
            return False
        return st.get("last_day") != now.strftime("%Y-%m-%d")
    return False


def tesuji_pass(lane: str, failure: str) -> None:
    """TESUJI AT THE MOMENT OF FAILURE (2026-09-05, operator: "how can you spot a
    tesuji 30m ago?" — you can't; batch sees shapes, tesuji needs immediacy).
    Fired synchronously when a lane fails: the failure's key datum is matched
    across lanes NOW, while the next cycles are still open. $0 lane, silent-fail."""
    try:
        snap = ROOT / "memory" / "feed" / "feed_snapshot.md"
        ctx = snap.read_text(errors="replace")[-2500:] if snap.exists() else "(no feed yet)"
        out = flash_call(
            "A fleet lane just failed. Decide if the failure's key datum is exactly "
            "what a DIFFERENT lane needs to win (a tesuji: the sacrificed stone wins "
            "elsewhere). If yes output ONLY {\"lane\": <research|builder|day_work|"
            "economist|bard_ledger|elder|forge|prose>, \"datum\": \"the usable fact\", "
            "\"win\": \"what the other lane does with it\"}. If the datum helps no "
            "other lane, output ONLY {}.",
            "failed lane: " + lane + "\nfailure: " + failure[:600]
            + "\nrecent fleet context:\n" + ctx,
            max_tokens=400)
        i, j = out.find("{"), out.rfind("}")
        if not (0 <= i < j):
            return
        c = json.loads(out[i:j + 1])
        dst = c.get("lane")
        if dst not in SCHEDULE or dst == lane or not c.get("datum"):
            return
        inbox = ROOT / "queue" / "lanes" / dst / "INBOX"
        inbox.mkdir(parents=True, exist_ok=True)
        stamp = _now().strftime("%Y%m%dT%H%M%SZ")
        body = (f"**TESUJI PASS** (UNPROVEN lead) {stamp} — failure in {lane}\n\n"
                f"- datum: {c.get('datum', '')}\n- win: {c.get('win', '')}\n"
                f"- failure: `{str(failure)[:200]}`\n")
        (inbox / f"tesuji_{stamp}.md").write_text(body, encoding="utf-8")
        _trail(dst, "TESUJI_DROP", f"from {lane}: {c.get('datum', '')}"[:160])
        _log(f"tesuji {lane}->{dst} datum={str(c.get('datum', ''))[:60]}")
    except Exception:  # noqa: BLE001 — never let the tesuji pass break the lane loop
        pass


def run_lane(lane: str) -> str:
    fn = CYCLES.get(lane)
    if fn is None:
        return f"unknown lane {lane}"
    t0 = time.time()
    try:
        result = fn()
    except Exception as e:  # noqa: BLE001
        result = f"EXC {type(e).__name__}: {e}"
        _trail(lane, "CYCLE_FAIL", result)
    if result.startswith("EXC") or " rc=1" in result or " rc=2" in result:
        tesuji_pass(lane, result)
    try:
        cluster_report_step(lane)
    except Exception as e:  # noqa: BLE001: the organ never breaks the lane loop
        _log(f"cluster organ exc {lane}: {e}")
    _mirror(lane)
    st = _state(lane)
    st["last_run"] = _now().isoformat()
    st["last_day"] = _now().strftime("%Y-%m-%d")
    st["last_result"] = str(result)[:200]
    _save_state(lane, st)
    _log(f"lane={lane} result={result} ({time.time() - t0:.1f}s)")
    return str(result)


def daemon() -> None:
    # SINGLE-WRITER GUARD (2026-09-05, the doubled-log lesson): _log() writes
    # LOG itself; if a launcher ALSO redirects our stdout into that same file,
    # every row lands twice. Refuse the launch instead of running double-mouthed.
    try:
        st_out, st_log = os.fstat(1), LOG.stat()
        if (st_out.st_dev, st_out.st_ino) == (st_log.st_dev, st_log.st_ino):
            print(f"{_ts()} daemon REFUSED: stdout redirects into {LOG.name} —"
                  " one file, one writer; start without the >> redirect", flush=True)
            return
    except OSError:
        pass
    # SINGLE-DAEMON GUARD (the respawn-law lesson, applied to this organ): a second
    # scheduler would double-run every lane. Refuse if a live holder exists.
    try:
        if PIDFILE.exists():
            old = int(PIDFILE.read_text(encoding="utf-8").strip() or 0)
            os.kill(old, 0)  # alive?
            _log(f"daemon REFUSED: pid {old} already holds {PIDFILE.name}")
            return
    except (ProcessLookupError, ValueError, PermissionError):
        pass  # stale/absent holder — take the lock
    except OSError:
        return
    PIDFILE.parent.mkdir(parents=True, exist_ok=True)
    PIDFILE.write_text(str(os.getpid()), encoding="utf-8")
    _log(f"lane_scheduler daemon UP pid={os.getpid()} lanes={list(SCHEDULE)}")
    _trail("day_work", "SCHEDULER_UP",
           f"in-cage lane scheduler armed; lanes={list(SCHEDULE)}")
    _mirror("day_work")
    beats = 0
    try:
        while True:
            for lane in SCHEDULE:
                try:
                    if _due(lane):
                        run_lane(lane)
                except Exception as e:  # noqa: BLE001
                    _log(f"loop exc {lane}: {e}")
            beats += 1
            if beats % 60 == 0:  # hourly heartbeat
                _trail("day_work", "HEARTBEAT", "scheduler alive, all lanes stateful")
                _mirror("day_work")
            time.sleep(60)
    finally:
        try:
            PIDFILE.unlink()
        except OSError:
            pass


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--lane", default="all", choices=list(SCHEDULE) + ["all"])
    ap.add_argument("--once", action="store_true", help="one cycle now (default)")
    ap.add_argument("--daemon", action="store_true", help="run the schedule loop")
    a = ap.parse_args(argv)
    if a.daemon:
        daemon()
        return 0
    lanes = list(SCHEDULE) if a.lane == "all" else [a.lane]
    for lane in lanes:
        print(f"{lane}: {run_lane(lane)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
