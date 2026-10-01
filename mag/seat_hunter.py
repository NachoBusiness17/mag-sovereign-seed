"""seat_hunter — the swarm of free seats finding MORE free seats (2026-08-23, self-steal).

Operator: "this is perfect shit to figure out with kubernetes and our swarm of free seats
finding more free seats. self steal please."

THE SELF-STEAL (nothing invented — every pattern was already proven in this codebase):
  * freebie_scan (mag/afk_loop) is a STATIC list of free tiers — it never looks for NEW ones.
  * grok_seat_burner SEATS is hardcoded to two homes (~/.grok, ~/.grok-sd) — the seat check
    (auth.json present = configured) is proven, but it never globs for MORE grok homes.
  * health.check_openrouter probes /api/v1/models for AUTH but never reads the model list.
  * providers.yaml openrouter.models is a fixed 3 free models.
So the only genuinely new logic here is DISCOVERY — and even that is built by composing the
proven checks above, not by inventing new transport.

WHAT IT DOES (discovery + fold, $0):
  1. grok seats: glob ~/.grok* for homes with auth.json -> a seat. Reuses grok_seat_burner's
     configured-check (auth.json present = configured + authed). NEW homes that aren't in
     SEATS get surfaced as discoverable seats.
  2. openrouter free models: GET /api/v1/models, keep only `:free` / $0-pricing models.
     NEW free models not already in providers.yaml openrouter.models get surfaced + appended,
     so the free lane self-rotates when one model hits its daily cap.
  3. fold: findings are appended to a hunt ledger (memory/runs/seat_hunt.jsonl) so real_swarm /
     the fleet can read "what free lane should we rotate to" grounded in our own bytes.

Wired into afk_cadence (the k8s 24/7 CronJob loop) as `seat_hunt` right after freebie_scan.

CLI:  python -m mag.seat_hunter hunt|status|list
"""
from __future__ import annotations

import glob
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCHEMA = "seat_hunter.v1"
LEDGER = ROOT / "memory" / "runs" / "seat_hunt.jsonl"
SNAPSHOT = ROOT / "memory" / "runs" / "seat_hunt_snapshot.json"
EXHAUST = ROOT / "memory" / "runs" / "seat_lane_exhaust.json"
OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
OPENROUTER_KEY_URL = "https://openrouter.ai/api/v1/key"
_OR_KEY_ENVS = ("OPENROUTER_API_KEY", "OR_API_KEY")
# OpenRouter free-tier limits (steal from openrouter.ai/docs/api-reference/limits, 2026-08-23):
# each FREE model lane has its own cap: RPM=20, RPD=50 (<$10 lifetime) or 1000 (>= $10). 429 on a
# :free model = that lane's daily cap -> rotate to the next free lane, don't retry the same one.
FREE_RPM = 20
FREE_RPD_NO_CREDITS = 50
FREE_RPD_HAS_CREDITS = 1000
FREE_CREDITS_THRESHOLD = 10


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


# ── 1. GROK SEAT DISCOVERY (reuses grok_seat_burner's proven auth.json check) ──────────────
def discover_grok_seats() -> dict[str, Any]:
    """Glob ~/.grok* for seats. A home with auth.json = configured (grok_seat_burner's proven
    check). Surfaces homes NOT already known to grok_seat_burner as discoverable new seats."""
    # known seats are keyed by seat name (nacho/sd) in grok_seat_burner; compare by HOME path,
    # not by the home-dir name (".grok" vs "nacho").
    known_homes = set()
    known_names = set()
    try:
        from mag.grok_seat_burner import SEATS
        for _name, cfg in SEATS.items():
            known_homes.add(str(Path(cfg["home"]).resolve()))
            known_names.add(_name)
    except Exception:
        pass
    homes = sorted(glob.glob(str(Path.home() / ".grok*")))
    seats, new = [], []
    for h in homes:
        name = Path(h).name
        auth = Path(h) / "auth.json"
        rec = {"home": h, "name": name, "configured": auth.is_file()}
        seats.append(rec)
        if auth.is_file() and str(Path(h).resolve()) not in known_homes:
            new.append(rec)
    return {"ok": True, "schema": SCHEMA, "kind": "grok", "seats": seats, "new": new,
            "note": "glob ~/.grok*; auth.json present = configured (grok_seat_burner pattern)"}


# ── 1b. GROK BILL READER (steal from ccusage's grok adapter, 2026-08-23) ────────────────────
# ccusage reads the ACTUAL Grok Build CLI session files and pulls the INVOICE cost from
# costUsdTicks (fixed-point USD, 1 tick = 1e-10 USD) on each completed turn. This is the
# authoritative bill — NOT a derived estimate — exactly our 'trust the bill' law. Our own
# grok_seat_burner SPEND_LEDGER records what WE drove; this reads what GROK actually billed.
# Data source: $GROK_HOME/sessions/<url-encoded-cwd>/<session-uuid>/updates.jsonl
# Only rows with sessionUpdate == "turn_completed" + usable usage are counted (in-progress turns
# are not reported until they complete). logs/unified.jsonl is NOT used (no per-request model id).
_COST_USD_TICKS_PER_USD = 1e10


def _grok_session_files(home: Path) -> list[tuple[Path, Path]]:
    """Walk $GROK_HOME/sessions for (updates.jsonl, summary.json) pairs (ccusage data source)."""
    sess_root = home / "sessions"
    if not sess_root.is_dir():
        return []
    out = []
    for updates in sess_root.rglob("updates.jsonl"):
        out.append((updates, updates.parent / "summary.json"))
    return out


def _grok_usage_from_line(line: dict[str, Any]) -> dict[str, Any] | None:
    """Extract a usable turn_completed usage row from a grok updates.jsonl line (ccusage shapes)."""
    try:
        params = line.get("params") or {}
        update = params.get("update") or {}
        if update.get("sessionUpdate") != "turn_completed":
            return None
        usage = update.get("usage") or {}
        if not usage:
            return None
        input_tokens = int(usage.get("inputTokens") or 0)
        output_tokens = int(usage.get("outputTokens") or 0)
        if input_tokens == 0 and output_tokens == 0:
            return None  # unusable
        cached_read = int(usage.get("cachedReadTokens") or 0)
        cache_creation = int(usage.get("cacheCreationTokens") or 0)
        reasoning = int(usage.get("reasoningTokens") or 0)
        # invoice cost: costUsdTicks / 1e10 (ccusage uses it verbatim as the bill)
        ticks = int(usage.get("costUsdTicks") or 0)
        cost = ticks / _COST_USD_TICKS_PER_USD if ticks else None
        model_usage = usage.get("modelUsage") or {}
        model = None
        if isinstance(model_usage, dict) and model_usage:
            model = next(iter(model_usage))
        session_id = str(params.get("sessionId") or "")
        return {
            "session_id": session_id,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cache_read_tokens": cached_read,
            "cache_creation_tokens": cache_creation,
            "reasoning_tokens": reasoning,
            "model": model,
            "cost": cost,
            "ts": line.get("timestamp"),
        }
    except Exception:  # noqa: BLE001
        return None


def grok_bill(*, home: str | Path | None = None) -> dict[str, Any]:
    """Read the REAL grok invoice from the session files (ccusage steal). Returns per-session
    usage + total cost + token counts. home defaults to ~/.grok, or glob all configured homes."""
    if home is not None:
        homes = [Path(home)]
    else:
        homes = [Path(h) for h in glob.glob(str(Path.home() / ".grok*"))
                 if (Path(h) / "auth.json").is_file()]
    per_home: dict[str, Any] = {}
    total_cost, total_tokens, n_turns = 0.0, 0, 0
    for h in homes:
        entries = []
        for updates, _summary in _grok_session_files(h):
            try:
                for line in updates.read_text(encoding="utf-8", errors="replace").splitlines():
                    line = line.strip()
                    if not line or '"turn_completed"' not in line:
                        continue
                    try:
                        rec = json.loads(line)
                    except Exception:  # noqa: BLE001
                        continue
                    u = _grok_usage_from_line(rec)
                    if u:
                        entries.append(u)
            except Exception:  # noqa: BLE001
                continue
        cost = sum(float(e["cost"] or 0) for e in entries)
        toks = sum(int(e["input_tokens"] or 0) + int(e["output_tokens"] or 0) for e in entries)
        total_cost += cost
        total_tokens += toks
        n_turns += len(entries)
        per_home[str(h)] = {"turns": len(entries), "cost": round(cost, 6),
                            "tokens": toks, "n_sessions": len({e["session_id"] for e in entries})}
    return {"ok": True, "schema": SCHEMA, "kind": "grok_bill",
            "per_home": per_home, "n_homes": len(homes),
            "total_cost_usd": round(total_cost, 6), "total_tokens": total_tokens,
            "total_turns": n_turns,
            "note": "read the REAL grok invoice from session updates.jsonl (ccusage steal); "
                    "costUsdTicks/1e10 = the actual bill, not a derived estimate"}


# ── 1c. CODEX BILL READER (steal from ccusage's codex adapter, 2026-08-23) ──────────────────
# Codex session JSONL under ~/.codex/sessions (and archived_sessions). Each `event_msg` line with
# payload.type == "token_count" carries total_token_usage (input/cached/cache_write/output/
# reasoning/total). Unlike grok, Codex does NOT record an invoice cost per turn — so we surface
# the TOKEN USAGE as the grounded fact (matches ccusage's honesty gate: tokens real, cost is a
# LiteLLM pricing ESTIMATE, not the bill).
_CODEX_HOME = Path.home() / ".codex"


def _codex_session_files() -> list[Path]:
    """Discover Codex session jsonl under ~/.codex (sessions/ + archived_sessions/)."""
    out = []
    roots = []
    for sub in ("sessions", "archived_sessions"):
        p = _CODEX_HOME / sub
        if p.is_dir():
            roots.append(p)
    if not roots and _CODEX_HOME.is_dir():
        roots.append(_CODEX_HOME)
    for root in roots:
        out.extend(root.rglob("*.jsonl"))
    return sorted(set(out))


def _codex_usage_from_line(line: dict[str, Any]) -> dict[str, Any] | None:
    """Extract a token_count usage row from a codex session line (ccusage shapes)."""
    try:
        if line.get("type") != "event_msg":
            return None
        payload = line.get("payload") or {}
        if payload.get("type") != "token_count":
            return None
        info = payload.get("info") or {}
        tu = info.get("total_token_usage") or {}
        input_tokens = int(tu.get("input_tokens") or 0)
        output_tokens = int(tu.get("output_tokens") or 0)
        if input_tokens == 0 and output_tokens == 0:
            return None
        cached_input = int(tu.get("cached_input_tokens") or 0)
        cache_write = int(tu.get("cache_write_input_tokens") or 0)
        reasoning = int(tu.get("reasoning_output_tokens") or 0)
        total = int(tu.get("total_tokens") or (input_tokens + output_tokens))
        return {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cache_read_tokens": cached_input,
            "cache_creation_tokens": cache_write,
            "reasoning_tokens": reasoning,
            "total_tokens": total,
            "ts": line.get("timestamp"),
        }
    except Exception:  # noqa: BLE001
        return None


def codex_bill() -> dict[str, Any]:
    """Read the Codex session files (ccusage steal). Tokens are the grounded fact (Codex records
    them per token_count event); cost is NOT recorded per turn, so it's left out rather than
    estimated — that's the honest gate. Returns per-session totals."""
    files = _codex_session_files()
    total_tokens = 0
    n_events = 0
    sessions: dict[str, dict[str, Any]] = {}
    for f in files:
        n_file = 0
        toks = 0
        try:
            for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if '"token_count"' not in line:
                    continue
                try:
                    rec = json.loads(line)
                except Exception:  # noqa: BLE001
                    continue
                u = _codex_usage_from_line(rec)
                if not u:
                    continue
                n_file += 1
                toks = max(toks, int(u["total_tokens"]))  # cumulative per file -> last is total
            if n_file:
                sessions.setdefault(str(f.parent), {"files": 0, "turns": 0, "tokens": 0})
                s = sessions[str(f.parent)]
                s["files"] += 1
                s["turns"] += n_file
                s["tokens"] += toks
                total_tokens += toks
                n_events += n_file
        except Exception:  # noqa: BLE001
            continue
    return {"ok": True, "schema": SCHEMA, "kind": "codex_bill",
            "n_files": len(files), "n_token_events": n_events,
            "total_tokens": total_tokens, "n_sessions": len(sessions),
            "note": "read Codex session jsonl (ccusage steal). TOKENS are the grounded fact; "
                    "Codex records no per-turn invoice cost, so cost is NOT estimated here "
                    "(honest gate — no fabrication from transcript length)"}


# ── 1d. DEEPSEEK BILL (the real balance endpoint — 'trust the bill' law) ────────────────────
# DeepSeek exposes a balance endpoint: GET https://api.deepseek.com/user/balance (Bearer key)
# returns balance_infos[] with total_balance / granted_balance / topped_up_balance /
# currency. That's the AUTHORITATIVE remaining credit for the funded DeepSeek seat — the real
# bill, not our derived quota ledger. Verified endpoint per existing handoff (OX_BURN).
DEEPSEEK_BALANCE_URL = "https://api.deepseek.com/user/balance"


def _deepseek_key() -> str:
    try:
        from models.env_load import load_dotenv
        load_dotenv()
    except Exception:  # noqa: BLE001
        pass
    from models.providers import get_provider
    pcfg = get_provider("deepseek") or {}
    for e in (pcfg.get("api_key_envs") or [pcfg.get("api_key_env")] or []):
        v = os.environ.get(str(e))
        if v:
            return v
    return ""


def deepseek_bill() -> dict[str, Any]:
    """Read the REAL DeepSeek balance (the authoritative bill for the funded seat). total_balance
    is what remains on the account — grounded in the provider's own number, not our ledger."""
    key = _deepseek_key()
    if not key:
        return {"ok": False, "schema": SCHEMA, "kind": "deepseek_bill",
                "error": "no DEEPSEEK_API_KEY"}
    try:
        req = urllib.request.Request(DEEPSEEK_BALANCE_URL,
                                     headers={"Authorization": f"Bearer {key}"}, method="GET")
        with urllib.request.urlopen(req, timeout=12) as r:
            data = json.loads(r.read().decode("utf-8", errors="replace"))
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "schema": SCHEMA, "kind": "deepseek_bill",
                "error": f"{type(e).__name__}: {str(e)[:200]}"}
    infos = data.get("balance_infos") or []
    total = sum(float(i.get("total_balance") or 0) for i in infos)
    granted = sum(float(i.get("granted_balance") or 0) for i in infos)
    topped = sum(float(i.get("topped_up_balance") or 0) for i in infos)
    currency = (infos[0].get("currency") if infos else "USD")
    return {"ok": True, "schema": SCHEMA, "kind": "deepseek_bill",
            "total_balance": total, "granted_balance": granted,
            "topped_up_balance": topped, "currency": currency,
            "n_accounts": len(infos),
            "note": "GET /user/balance — the REAL remaining credit on the funded DeepSeek seat "
                    "(authoritative, from the provider's own number, not our quota ledger)"}


# ── 1e. DEEPSEEK BILLING EXPORT INGEST (the real invoice, folded) ──────────────────────────
# The operator exports the DeepSeek platform billing as two CSVs (cost + amount). These are the
# AUTHORITATIVE invoice rows (per-day per-model USD cost, and per-day per-key per-token-type
# amounts at their real prices). This ingests those exports so the real DeepSeek bill lives in
# the repo (memory/runs/seat_spend/deepseek/) and surfaces through seat_hunter — the same
# 'trust the bill' law as grok_bill, but from the provider's billing export instead of session
# files.
DEEPSEEK_BILL_DIR = ROOT / "memory" / "runs" / "seat_spend" / "deepseek"
DEEPSEEK_BILL_LEDGER = ROOT / "memory" / "runs" / "seat_spend" / "deepseek_bill.jsonl"


def _csv_rows(path: Path) -> list[dict[str, Any]]:
    """Parse a CSV export into dict rows (header-driven)."""
    if not path.is_file():
        return []
    import csv
    try:
        with path.open("r", encoding="utf-8-sig", errors="replace") as f:
            return [dict(r) for r in csv.DictReader(f)]
    except Exception:  # noqa: BLE001
        return []


def _deepseek_bill_files() -> list[Path]:
    """The ingested cost/amount CSVs in the bill store (sorted by filename)."""
    if not DEEPSEEK_BILL_DIR.is_dir():
        return []
    return sorted(p for p in DEEPSEEK_BILL_DIR.glob("*.csv"))


def ingest_deepseek_bill() -> dict[str, Any]:
    """Read the ingested DeepSeek billing CSVs and fold the authoritative cost/token rows to a
    ledger + summary. Cost rows carry the real USD per day/model; amount rows carry per-key
    per-token-type amounts at their real prices. Nothing estimated."""
    rows = _deepseek_bill_files()
    cost_rows = [r for r in (_csv_rows(p) for p in rows) for r in r
                 if r.get("cost")]
    DEEPSEEK_BILL_LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with DEEPSEEK_BILL_LEDGER.open("a", encoding="utf-8") as f:
        for r in cost_rows:
            try:
                f.write(json.dumps({"schema": "deepseek.bill.v1", "ts": _now(),
                                    "start": r.get("start_time_iso", ""),
                                    "model": r.get("model", ""),
                                    "cost": float(r.get("cost") or 0),
                                    "currency": r.get("currency", "USD")}, ensure_ascii=False) + "\n")
            except Exception:  # noqa: BLE001
                continue
    total = sum(float(r.get("cost") or 0) for r in cost_rows)
    by_model: dict[str, float] = {}
    by_day: dict[str, float] = {}
    for r in cost_rows:
        m = r.get("model", "?")
        by_model[m] = by_model.get(m, 0.0) + float(r.get("cost") or 0)
        by_day.setdefault(r.get("start_time_iso", "")[:10], 0.0)
        by_day[r.get("start_time_iso", "")[:10]] += float(r.get("cost") or 0)
    # amount rows: per-key token/request tallies for context
    amount_rows = [r for p in rows for r in (_csv_rows(p) or []) if "amount" in r]
    n_requests = sum(int(r.get("amount") or 0) for r in amount_rows if r.get("type") == "request_count")
    return {"ok": True, "schema": SCHEMA, "kind": "deepseek_bill_export",
            "source": str(DEEPSEEK_BILL_DIR),
            "total_cost_usd": round(total, 6), "n_cost_rows": len(cost_rows),
            "by_model": {k: round(v, 6) for k, v in by_model.items()},
            "n_days": len(by_day),
            "requests_in_amount_export": n_requests,
            "note": "real DeepSeek platform billing export ingested (cost + amount CSVs) — "
                    "authoritative invoice, folded to " + str(DEEPSEEK_BILL_LEDGER)}


# ── 2. OPENROUTER FREE MODEL DISCOVERY (reuses health.check_openrouter's urllib probe) ──────
# MULTI-ACCOUNT KEYS (2026-08-23, operator added a second OpenRouter key): like grok's nacho+sd
# seats, each OpenRouter account key is a SEPARATE pool with its OWN account-level free quota.
# We rotate across all configured keys so no single account's daily cap gates the fleet — the
# same swap-the-seat pattern, applied to OpenRouter accounts. (NOTE: this helps the per-ACCOUNT
# cap; it does NOT raise the upstream provider shared pool that throttles a specific model.)
# Recognized key env vars, in priority order. OPENROUTER_API_KEY_2 = the sd account.
_OR_KEY_ENVS = ("OPENROUTER_API_KEY", "OPENROUTER_API_KEY_2", "OR_API_KEY", "OR_API_KEY_2")
_OR_RR = {"i": 0}  # round-robin pointer across account keys


def _load_env() -> None:
    try:
        from models.env_load import load_dotenv
        load_dotenv()
    except Exception:  # noqa: BLE001
        pass


def _or_keys() -> list[str]:
    """All configured OpenRouter account keys (deduped, order preserved)."""
    _load_env()
    seen, out = set(), []
    for e in _OR_KEY_ENVS:
        v = os.environ.get(e)
        if v and v not in seen:
            seen.add(v)
            out.append(v)
    return out


def _or_key() -> str:
    """Rotate to the NEXT configured OpenRouter account key (round-robin). Each call swaps
    accounts so the fleet spreads across every key's independent account-level quota."""
    keys = _or_keys()
    if not keys:
        return ""
    _OR_RR["i"] = _OR_RR.get("i", 0) % len(keys)
    k = keys[_OR_RR["i"]]
    _OR_RR["i"] += 1
    return k


def _known_openrouter_models() -> set[str]:
    """Models already in providers.yaml openrouter.models (from the real config layer)."""
    try:
        from models.providers import _cfg_path
        import yaml
        cfg = yaml.safe_load(_cfg_path().read_text(encoding="utf-8", errors="replace")) or {}
        prov = (cfg.get("providers") or {}).get("openrouter") or {}
        return set(prov.get("models") or [])
    except Exception:
        return set()


def discover_openrouter_free() -> dict[str, Any]:
    """GET /api/v1/models, keep :free / $0 models, surface ones not already configured."""
    key = _or_key()
    if not key:
        return {"ok": False, "schema": SCHEMA, "kind": "openrouter", "error": "no OPENROUTER_API_KEY",
                "note": "set OPENROUTER_API_KEY (or OR_API_KEY) to enable free-lane discovery"}
    try:
        req = urllib.request.Request(
            OPENROUTER_MODELS_URL,
            headers={"Authorization": f"Bearer {key}"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode("utf-8", errors="replace"))
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "schema": SCHEMA, "kind": "openrouter", "error": str(e)[:200]}
    models = data.get("data") or []
    free = []
    for m in models:
        mid = str(m.get("id") or "")
        pricing = m.get("pricing") or {}
        p = float(pricing.get("prompt") or 0)
        if mid.endswith(":free") or (p == 0 and float(pricing.get("completion") or 0) == 0):
            free.append(mid)
    free = sorted(set(free))
    known = _known_openrouter_models()
    new = [m for m in free if m not in known]
    return {"ok": True, "schema": SCHEMA, "kind": "openrouter", "free": free, "new": new,
            "n_free": len(free), "n_new": len(new),
            "note": "live /api/v1/models filtered to :free/$0; new = not yet in providers.yaml"}


# ── 2b. FREE-LANE QUOTA + ROTATION (steal from openrouter limits + litellm fallback chain) ───
def _read_exhaust() -> dict[str, Any]:
    """Read the lane-exhaustion state (which free lanes are currently 429'd out)."""
    if not EXHAUST.is_file():
        return {}
    try:
        return json.loads(EXHAUST.read_text(encoding="utf-8", errors="replace")) or {}
    except Exception:
        return {}


def quota_status() -> dict[str, Any]:
    """GET /api/v1/key — live daily usage + free-tier flag (OpenRouter's own proactive check).
    Steal: track usage_daily / is_free_tier BEFORE the lane 429s, so we know which free lanes are
    near their cap instead of discovering it the hard way."""
    key = _or_key()
    if not key:
        return {"ok": False, "schema": SCHEMA, "kind": "quota", "error": "no OPENROUTER_API_KEY"}
    try:
        req = urllib.request.Request(OPENROUTER_KEY_URL,
                                     headers={"Authorization": f"Bearer {key}"}, method="GET")
        with urllib.request.urlopen(req, timeout=12) as r:
            data = (json.loads(r.read().decode("utf-8", errors="replace")) or {}).get("data") or {}
        return {"ok": True, "schema": SCHEMA, "kind": "quota",
                "limit_remaining": data.get("limit_remaining"),
                "usage_daily": data.get("usage_daily"),
                "usage_weekly": data.get("usage_weekly"),
                "is_free_tier": data.get("is_free_tier"),
                "note": "live /api/v1/key — proactive free-lane headroom"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "schema": SCHEMA, "kind": "quota", "error": str(e)[:200]}


def mark_lane_exhausted(lane: str) -> dict[str, Any]:
    """Record a 429 on a free lane (its daily cap). It is excluded from rotation until the daily
    reset — the honest 'this lane is spent today, rotate to another' signal."""
    lane = (lane or "").strip()
    st = _read_exhaust()
    # treat as exhausted for the rest of the UTC day
    day = _now()[:10]
    st[lane] = {"exhausted_day": day, "ts": _now()}
    EXHAUST.parent.mkdir(parents=True, exist_ok=True)
    EXHAUST.write_text(json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "schema": SCHEMA, "lane": lane, "exhausted": True, "day": day}


def _active_lanes() -> list[str]:
    """Free lanes from the snapshot MINUS lanes 429-exhausted today (rotation pool)."""
    snap = free_lanes()
    lanes = [m for m in snap.get("openrouter_free", []) if str(m).endswith(":free")]
    if not lanes:  # fall back to the known config free models if no snapshot yet
        lanes = [m for m in _known_openrouter_models() if str(m).endswith(":free")]
    day = _now()[:10]
    ex = _read_exhaust()
    return [m for m in lanes if ex.get(m, {}).get("exhausted_day") != day]


_RR = {"i": 0}


def next_lane(*, exclude: str = "") -> dict[str, Any]:
    """Pick the next free lane to fire (litellm fallback-chain, adapted): rotate round-robin
    through the ACTIVE free lanes, skipping 429-exhausted ones and the one just tried. A process
    local round-robin pointer spreads parallel real_swarm threads across distinct free lanes."""
    lanes = _active_lanes()
    if not lanes:
        return {"ok": False, "schema": SCHEMA, "lane": None,
                "error": "no active free lanes — all exhausted today or none discovered (run hunt)"}
    exclude = (exclude or "").strip()
    if exclude and exclude in lanes:
        lanes = lanes[lanes.index(exclude) + 1:] + lanes[:lanes.index(exclude)]
    _RR["i"] = (_RR.get("i", 0)) % len(lanes)
    lane = lanes[_RR["i"]]
    _RR["i"] += 1
    return {"ok": True, "schema": SCHEMA, "lane": lane, "n_active": len(lanes),
            "note": "rotated to a non-exhausted free lane (litellm fallback-chain, adapted)"}


# ── 3. FOLD + LEDGER ────────────────────────────────────────────────────────────────────────
def _fold(rec: dict[str, Any]) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def hunt() -> dict[str, Any]:
    """Run discovery, fold findings to the ledger, return a grounded summary."""
    grok = discover_grok_seats()
    or_ = discover_openrouter_free()
    rec = {"schema": SCHEMA, "ts": _now(),
           "grok_seats": grok.get("seats", []),
           "grok_new": grok.get("new", []),
           "openrouter_free_n": or_.get("n_free", 0),
           "openrouter_new": or_.get("new", [])}
    _fold(rec)
    # persist a CURRENT snapshot the fleet (real_swarm) can rotate through without re-querying
    SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT.write_text(
        json.dumps({"schema": SCHEMA, "ts": _now(),
                    "openrouter_free": or_.get("free", []),
                    "grok_seats": grok.get("seats", [])}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    out = {"ok": True, "schema": SCHEMA, "ts": _now(), "grok": grok, "openrouter": or_,
           "note": "swarm of free seats finding more free seats; folded to " + str(LEDGER)}
    return out


def free_lanes() -> dict[str, Any]:
    """Read the last hunt snapshot back — the CURRENT free OpenRouter lanes + grok seats the
    fleet can rotate through. Read-only; never re-queries (real_swarm can call this cheaply)."""
    if not SNAPSHOT.is_file():
        return {"ok": False, "schema": SCHEMA, "error": "no snapshot yet — run hunt() first"}
    try:
        d = json.loads(SNAPSHOT.read_text(encoding="utf-8", errors="replace"))
        return {"ok": True, "schema": SCHEMA, "ts": d.get("ts"),
                "openrouter_free": d.get("openrouter_free", []),
                "grok_seats": d.get("grok_seats", [])}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "schema": SCHEMA, "error": str(e)[:200]}


def status() -> dict[str, Any]:
    """Read the hunt ledger back — what free seats/lanes have been found over time."""
    rows = []
    if LEDGER.is_file():
        for line in LEDGER.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    return {"ok": True, "schema": SCHEMA, "n_hunts": len(rows), "hunts": rows[-10:]}


def accounts() -> dict[str, Any]:
    """Show the configured OpenRouter account keys (masked) + their live quota, so the fleet can
    see how many independent account-level pools it has. Each key = one account = its own cap."""
    keys = _or_keys()
    per = []
    for i, k in enumerate(keys):
        masked = (k[:5] + "..." + k[-4:]) if len(k) > 9 else "****"
        _OR_RR["i"] = i  # point rotation at this key so quota reflects THIS account
        q = quota_status()
        per.append({"account": i + 1, "key_masked": masked, "quota": q.get("ok") and {
            "is_free_tier": q.get("is_free_tier"), "usage_daily": q.get("usage_daily"),
            "limit_remaining": q.get("limit_remaining")} or {"error": q.get("error")}})
    _OR_RR["i"] = 0
    return {"ok": True, "schema": SCHEMA, "kind": "accounts", "n_accounts": len(keys),
            "accounts": per,
            "note": "each OpenRouter account key is its own pool (own daily cap). rotation "
                    "spreads across them; this does NOT raise an upstream model's shared pool."}


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="seat-hunter")
    ap.add_argument("cmd", nargs="?", default="hunt",
                    choices=["hunt", "status", "list", "lanes", "quota", "next", "exhaust",
                             "bill", "codex", "deepseek", "ds-bill", "accounts"])
    ap.add_argument("--lane", type=str, default="", help="lane to mark exhausted (for 'exhaust')")
    ap.add_argument("--home", type=str, default="", help="grok home for 'bill'")
    a = ap.parse_args(argv)
    if a.cmd == "hunt":
        print(json.dumps(hunt(), indent=2, default=str))
    elif a.cmd == "status":
        print(json.dumps(status(), indent=2, default=str))
    elif a.cmd == "lanes":
        print(json.dumps(free_lanes(), indent=2, default=str))
    elif a.cmd == "quota":
        print(json.dumps(quota_status(), indent=2, default=str))
    elif a.cmd == "accounts":
        print(json.dumps(accounts(), indent=2, default=str))
    elif a.cmd == "next":
        print(json.dumps(next_lane(exclude=a.lane), indent=2, default=str))
    elif a.cmd == "exhaust":
        if not a.lane:
            print(json.dumps({"ok": False, "error": "--lane required"}, indent=2))
        else:
            print(json.dumps(mark_lane_exhausted(a.lane), indent=2, default=str))
    elif a.cmd == "bill":
        print(json.dumps(grok_bill(home=a.home or None), indent=2, default=str))
    elif a.cmd == "codex":
        print(json.dumps(codex_bill(), indent=2, default=str))
    elif a.cmd == "deepseek":
        print(json.dumps(deepseek_bill(), indent=2, default=str))
    elif a.cmd == "ds-bill":
        print(json.dumps(ingest_deepseek_bill(), indent=2, default=str))
    elif a.cmd == "list":
        g = discover_grok_seats()
        o = discover_openrouter_free()
        print(json.dumps({"grok_seats": g, "openrouter": o}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
