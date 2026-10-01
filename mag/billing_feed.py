"""billing_feed — AUTO-FEED the real DeepSeek billing/usage to the swarm, no hand-pasting.

Operator (2026-08-11): "how can you get this data automatically i've been rewarding you with it but
you have access and stuff like it should auto feed to the swarm."

THE AUTO-FEED (deterministic + $0; pull best-effort, never fails the monitor):
  feed() -> 1. PULL the authoritative usage/billing from platform.deepseek.com via browser_driver
               (connect + inner_text; host must be allowlisted; auth is operator-owned).
            2. PARSE hourly rows (hour, model, type, amount, cost) from the page text (the CSV we
               were being pasted). Best-effort regex parse; dedup by (hour,type).
            3. APPEND to the grounded billing ledger (memory/cost/billing_feed.jsonl).
            4. FOLD spikes through the cost guard (cost_learn/flock_usage_guard) as training.
            5. RETURN what was fed — so the loop surface shows real billed numbers, not estimates.
  Wired into republic_loop as the auto-feed step (S1-cost-feed) so it runs every cadence.

Schema: billing_feed.v1 · deterministic + $0 · reuse: browser_driver, cost_learn, flock_usage_guard
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    from pathlib import Path as _P
    ROOT = _P(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "billing_feed.v1"
LEDGER = ROOT / "memory" / "cost" / "billing_feed.jsonl"
USAGE_URL = "https://platform.deepseek.com/usage"
# allowlist requirement: platform.deepseek.com must be in configs/browser_env.yaml hosts

# CSV-ish row parse: hour|model|type|price|amount  (matches the billing export we were pasted)
_ROW_RE = re.compile(
    r"(\d{2}:\d{2})-(\d{2}:\d{2})[^\n]*?(input_cache_hit_tokens|input_cache_miss_tokens|"
    r"request_count|output_tokens)[^\n]*?([0-9]+(?:\.\d+)?)\s*$", re.M)
_COST_RE = re.compile(
    r"(\d{2}:\d{2})-(\d{2}:\d{2})[^\n]*?(Paid|Free)[^\n]*?([0-9]+\.[0-9]+)\s*USD", re.M)


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse(text: str) -> list[dict[str, Any]]:
    """Parse hourly billing rows from the page text. Best-effort; dedup by (hour,type)."""
    rows: dict[str, dict[str, Any]] = {}
    for m in _ROW_RE.finditer(text or ""):
        h = f"{m.group(1)}-{m.group(2)}"
        typ, amt = m.group(3), float(m.group(4))
        rows.setdefault(f"{h}:{typ}", {"hour": h, "type": typ, "amount": amt}).update(
            {"hour": h, "type": typ, "amount": amt})
    for m in _COST_RE.finditer(text or ""):
        h = f"{m.group(1)}-{m.group(2)}"
        rows.setdefault(f"{h}:cost", {"hour": h, "type": "cost", "amount": float(m.group(4))}).update(
            {"hour": h, "type": "cost", "amount": float(m.group(4))})
    out = []
    for r in rows.values():
        r["ts"] = _now()
        out.append(r)
    return out


def _already(hour: str, typ: str) -> bool:
    if not LEDGER.is_file():
        return False
    for line in LEDGER.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
            if r.get("hour") == hour and r.get("type") == typ:
                return True
        except Exception:
            continue
    return False


def feed(*, url: str = USAGE_URL, fold: bool = True) -> dict[str, Any]:
    """AUTO-FEED the real billing to the swarm. Pull -> parse -> append (dedup) -> fold spikes."""
    # 1. PULL (best-effort via browser_driver; auth/allowlist operator-owned)
    page_text = None
    try:
        from mag import browser_driver
        c = browser_driver.connect()
        if c.get("ok") and browser_driver._host_allowed(url):
            page = c["page"]
            page.goto(url, timeout=60000)
            page.wait_for_load_state("domcontentloaded")
            try:
                page_text = page.locator("body").inner_text()
            except Exception:
                page_text = page.content()
            try:
                page.close()
                c["page"]._mag_pw.stop()
            except Exception:
                pass
    except Exception:
        page_text = None

    if not page_text:
        return {"ok": True, "schema": SCHEMA, "fed": 0, "reachable": False,
                "note": "platform not reachable / not allowlisted / auth needed; no rows fed this "
                        "cadence (monitor still alive via local feed)",
                "allowlist": "add platform.deepseek.com to configs/browser_env.yaml hosts"}

    # 2. PARSE
    rows = _parse(page_text)
    # 3. APPEND (dedup by hour+type)
    appended = 0
    for r in rows:
        if _already(r["hour"], r["type"]):
            continue
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with LEDGER.open("a", encoding="utf-8") as f:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
        appended += 1
    # 4. FOLD spikes through the cost guard
    folded = False
    if fold and appended:
        try:
            from mag import flock_usage_guard
            gr = flock_usage_guard.watch_and_guard(rows) if hasattr(flock_usage_guard, "watch_and_guard") else {}
            folded = bool(gr.get("ok"))
        except Exception:
            pass
    return {"ok": True, "schema": SCHEMA, "ts": _now(), "reachable": True,
            "parsed": len(rows), "fed": appended, "spikes_folded": folded,
            "ledger": str(LEDGER.relative_to(ROOT)).replace("\\", "/"),
            "rows": rows[:20],
            "note": "real billing auto-fed to the swarm (grounded, from the platform page)"}


# ── STANDING GATE (2026-08-12, chord move #3): the BILL is a gate, not a report ────────────
# Baseline (grounded from the operator's 2026-08-12 CSV): cache-hit 98.16%, ~$0.00231/request.
# If the live ledger drifts below the hit floor or >2x the cost/request baseline, that is a SIGNAL
# (surfaced through the shared trigger/cast surface), not a footnote.
HIT_FLOOR = 0.95          # cache-hit rate below this = the shared-stateless economics degrading
COST_PER_REQ_FACTOR = 2.0  # >2x the ledger baseline cost/request = drift worth surfacing


def gate(*, window_hours: int = 24, min_rows: int = 4) -> dict[str, Any]:
    """Assert the live ledger's economics against the standing floor. Deterministic + $0. Reads the
    authoritative billing_feed ledger (grounded), computes cache-hit + cost/request, flags drift.
    On violation -> emit behavioral signal (kind='cost_spike'/'usage_spike') so trigger_learn maps
    it to a surface. Returns {ok, gate_triggered, metrics}."""
    rows = []
    if LEDGER.is_file():
        for line in LEDGER.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    if len(rows) < min_rows:
        return {"ok": True, "schema": SCHEMA, "gate_triggered": False, "n_rows": len(rows),
                "note": f"only {len(rows)} ledger rows (< {min_rows}) — seeding, no gate yet"}

    # sum by type over the whole ledger (the ledger is the grounded bill)
    by_type: dict[str, float] = {}
    for r in rows:
        t = str(r.get("type") or "")
        try:
            by_type[t] = by_type.get(t, 0.0) + float(r.get("amount") or 0)
        except (TypeError, ValueError):
            continue
    hit = by_type.get("input_cache_hit_tokens", 0.0)
    miss = by_type.get("input_cache_miss_tokens", 0.0)
    reqs = by_type.get("request_count", 0.0)
    cost = by_type.get("cost", 0.0)
    hit_rate = hit / (hit + miss) if (hit + miss) else None
    cost_per_req = cost / reqs if reqs else None

    # cost/request baseline = the ledger's own average (honest: measured from the bill, not invented)
    baseline = _load_baseline()
    if baseline is None and cost_per_req is not None and reqs:
        baseline = cost_per_req  # seed from the ledger itself
        _save_baseline(baseline)

    violations: list[dict[str, Any]] = []
    if hit_rate is not None and hit_rate < HIT_FLOOR:
        violations.append({"metric": "cache_hit", "value": round(hit_rate, 4), "floor": HIT_FLOOR})
    if cost_per_req is not None and baseline and cost_per_req > baseline * COST_PER_REQ_FACTOR:
        violations.append({"metric": "cost_per_request", "value": round(cost_per_req, 6),
                           "baseline": round(baseline, 6),
                           "factor": round(cost_per_req / baseline, 2)})

    gate_triggered = bool(violations)
    if gate_triggered:
        _emit_signal("cost_spike" if any(v["metric"] == "cost_per_request" for v in violations)
                     else "usage_spike", violations=violations)
        try:
            from mag import training_events
            training_events.emit("operator_behavior", pattern_tags=["billing_gate"],
                                 join={"metric": violations[0]["metric"]},
                                 outcome={"violations": violations}, exportable=False)
        except Exception:
            pass

    metrics = {"cache_hit_rate": (round(hit_rate, 4) if hit_rate is not None else None),
               "cost_per_request": (round(cost_per_req, 6) if cost_per_req is not None else None),
               "baseline_cost_per_request": (round(baseline, 6) if baseline is not None else None),
               "n_requests": int(reqs), "total_cost_usd": round(cost, 6)}
    return {"ok": True, "schema": SCHEMA, "gate_triggered": gate_triggered,
            "metrics": metrics, "violations": violations,
            "note": ("bill gate FLAGGED drift -> surfaced as a signal (not a footnote)" if violations
                     else "bill within the standing floor (cache-hit >= 95%, cost/request <= 2x baseline)")}


def _baseline_path() -> Path:
    return ROOT / "memory" / "cost" / "gate_baseline.json"


def _load_baseline() -> float | None:
    p = _baseline_path()
    if p.is_file():
        try:
            return float(json.loads(p.read_text(encoding="utf-8")).get("cost_per_request"))
        except Exception:
            return None
    return None


def _save_baseline(v: float) -> None:
    p = _baseline_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"cost_per_request": v, "ts": _now()}), encoding="utf-8")


def _emit_signal(kind: str, **extra: Any) -> None:
    row = {"kind": kind, "ts": _now(), **extra}
    try:
        from pathlib import Path as _P
        events = _P(ROOT) / "logs" / "behavioral_events.jsonl"
        events.parent.mkdir(parents=True, exist_ok=True)
        with events.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    except OSError:
        pass


def status() -> dict[str, Any]:
    n = 0
    if LEDGER.is_file():
        n = sum(1 for _ in LEDGER.read_text(encoding="utf-8", errors="replace").splitlines() if _.strip())
    return {"ok": True, "schema": SCHEMA,
            "contract": "feed()->pull platform billing -> parse -> append (dedup) -> fold spikes; "
                        "auto-runs on the cadence (no hand-pasting)",
            "cost": "deterministic + $0 (browser pull best-effort)",
            "ledger": str(LEDGER.relative_to(ROOT)).replace("\\", "/"), "n_rows": n,
            "url": USAGE_URL, "allowlist_note": "platform.deepseek.com must be in browser_env.yaml hosts"}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="billing-feed")
    ap.add_argument("cmd", nargs="?", default="feed", choices=["feed", "status", "gate"])
    a = ap.parse_args()
    if a.cmd == "gate":
        print(json.dumps(gate(), indent=2, default=str))
    else:
        print(json.dumps(feed() if a.cmd == "feed" else status(), indent=2, default=str))
