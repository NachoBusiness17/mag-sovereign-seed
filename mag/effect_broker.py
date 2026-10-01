"""effect_broker — unified effect execution layer for MAG.

Every side effect in MAG must route through this broker.  The broker is
co-located with the switchboard (reference-monitor pattern) and enforces:

    1. authority.status == AUTHORIZED
    2. effect in authority.granted_capabilities
    3. policy_engine.validate_authority() passes (TTL, budget, revocation)

Each broker produces a full receipt:
    ENQUEUED → RUNNING → COMPLETED / FAILED → RECEIPT_COMMITTED

Dispatch delegates (AH18, 2026-09-29, receipt
watch/inbox/last_mile_20260930/AH18_BROKER_STUBS.md — these two effects
were ok=True stubs while this module claimed every side effect routes
through it; both are now real-but-narrow):
    model_call  -> models.providers.chat_provider (authorize + max_cost_usd
                   pre-call gate + call + metered effect row)
    lane_spawn  -> mag.seat_dispatch.task (authorize + delegate + row)

Every dispatched effect also appends one compact meter row to
memory/runs/effect_broker/effects.jsonl (model, tokens, cost_usd,
corr_id / task_id) so cost rollups need not glob the receipt tree.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RECEIPTS_DIR = ROOT / "memory" / "runs" / "effect_broker"

# ---------------------------------------------------------------------------
# Configurable allowlists / denylist
# ---------------------------------------------------------------------------

def _list_from_env(name: str, default: list[str]) -> list[str]:
    """Parse an allow/denylist from env var `name` as a JSON list of strings.

    FIX (audit finding #6, watch/inbox/MAG_SYSTEMS_DEEP_ANALYSIS_20260930):
    the old `":".join(default).split(":")` shredded Windows drive paths
    ("C:\\repo\\board" -> ["C", "\\repo\\board"]) and shredded the IPv6
    loopback "::1" into empty strings.  An empty deny entry matches every
    url ("" in url is always True -> every network_access denied while the
    self-test still passed) and an empty allow prefix matches every path
    (str.startswith("")), so malformed or empty entries fail loud here
    instead of silently widening or collapsing the gates.  JSON is chosen
    over os.pathsep because ":"-splitting shreds "C:\\..." on Windows and
    os.pathsep (":") shreds "::1" on POSIX; JSON keeps both intact on
    every surface (Windows host, WSL, Docker).
    """
    raw = os.environ.get(name)
    if raw is None:
        values = default
    else:
        try:
            values = json.loads(raw)
        except ValueError as exc:  # name the env var, not just the JSON offset
            raise ValueError(f"{name} must be a JSON list of strings: {exc}") from exc
    if (not isinstance(values, list)
            or not all(isinstance(v, str) and v for v in values)):
        raise ValueError(
            f"{name} must be a JSON list of non-empty strings, got: {raw!r}")
    return list(values)


# fs_write: paths under these prefixes are allowed.
# Intended default list: the repo's board/, patches/, memory/, bridge/ roots.
FS_ALLOWLIST = _list_from_env("MAG_FS_ALLOWLIST", [
    str(ROOT / "board"),
    str(ROOT / "patches"),
    str(ROOT / "memory"),
    str(ROOT / "bridge"),
])

# tool_invoke: only these cwd values are allowed.
# Intended default list: the repo root plus the container-mount paths
# /mag and /board (keeps Docker/OpenClaw lanes usable).
TOOL_CWD_ALLOWLIST = _list_from_env("MAG_TOOL_CWD_ALLOWLIST", [
    str(ROOT),
    "/mag",
    "/board",
])

# network_access: deny these hosts/patterns.
# Intended default list: the loopback family 127.0.0.1, localhost,
# 0.0.0.0, and the IPv6 loopback "::1" (which must survive parsing as a
# single real entry, never as empty-string fragments).
NETWORK_DENYLIST = _list_from_env("MAG_NETWORK_DENYLIST", [
    "127.0.0.1",
    "localhost",
    "0.0.0.0",
    "::1",
])

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

EFFECTS_LOG_NAME = "effects.jsonl"

# AH18 (2026-09-29): single conservative USD ceiling for the model_call
# budget gate.  The estate has no per-model price table (models/quota.py
# meters tokens, not dollars; its only dollar figure is the DeepSeek cache
# comment at $0.14/M miss vs $0.0028/M hit), and inventing per-model prices
# would fabricate precision the config does not hold.  One blended ceiling
# over-estimates cost, which fails CLOSED on the pre-call max_cost_usd
# gate (a denied cheap call is recoverable; an authorized expensive call is
# not) and keeps the ledger row internally consistent (same rate pre and
# post).  Operator-tunable via env because the ceiling is policy, not truth.
USD_PER_MTOK = float(os.environ.get("MAG_MODEL_USD_PER_MTOK", "15.0"))


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:16]


def _hash_file(path: Path) -> str:
    if path.exists():
        return _hash_bytes(path.read_bytes())
    return ""


def _ensure_dirs():
    RECEIPTS_DIR.mkdir(parents=True, exist_ok=True)


def _append_effect_row(effect: str, row: dict) -> dict:
    """Append one metered effect row to the broker's append-only ledger.

    AH18: receipts (one JSON per event) carry the full audit trail;
    effects.jsonl is the compact per-effect meter (model, tokens, cost_usd,
    corr_id / task_id) that cost rollups can scan without globbing the
    receipt tree.  Lives under RECEIPTS_DIR so redirecting the receipts
    root in tests redirects the ledger with it.
    """
    _ensure_dirs()
    entry = {"ts": _now(), "effect": effect, **row}
    with (RECEIPTS_DIR / EFFECTS_LOG_NAME).open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def _load_policy_engine():
    """Import policy_engine if present; otherwise return None."""
    try:
        from . import policy_engine
        return policy_engine
    except Exception:
        # Keep direct-file execution usable for the small CLI/debug harness,
        # while package execution remains the canonical path.
        try:
            import policy_engine
            return policy_engine
        except Exception:
            return None


def _pre_state(effect: str, params: dict) -> dict:
    """Capture state *before* an effect runs."""
    if effect == "fs_write":
        path = Path(params.get("path", ""))
        return {"path_exists": path.exists(), "path_hash": _hash_file(path)}
    if effect == "board_write":
        bb = ROOT / "memory" / "runs" / "swarm_worker" / "blackboard"
        existing = sorted(bb.glob("bb-*.json")) if bb.exists() else []
        return {"note_count": len(existing), "last_seq": _last_seq(existing)}
    if effect == "verkle_link":
        return {"event_id": params.get("event_id")}
    if effect == "tool_invoke":
        return {"cmd_preview": " ".join(params.get("cmd", []))[:80]}
    return {}


def _last_seq(paths: list[Path]) -> int:
    if not paths:
        return 0
    try:
        return int(paths[-1].stem.split("-")[1])
    except Exception:
        return len(paths)


def _post_state(effect: str, params: dict, result: dict) -> dict:
    """Capture state *after* an effect runs."""
    if effect == "fs_write":
        path = Path(params.get("path", ""))
        return {"path_exists": path.exists(), "path_hash": _hash_file(path)}
    if effect == "board_write":
        bb = ROOT / "memory" / "runs" / "swarm_worker" / "blackboard"
        existing = sorted(bb.glob("bb-*.json")) if bb.exists() else []
        return {"note_count": len(existing), "last_seq": _last_seq(existing)}
    if effect == "verkle_link":
        return {"stdout_head": (result.get("stdout") or "")[:80]}
    return {}


def _postcondition_evidence(effect: str, params: dict, result: dict) -> dict:
    """Produce evidence that the intended state change occurred."""
    if effect == "fs_write":
        path = Path(params.get("path", ""))
        return {
            "path": str(path),
            "size_bytes": path.stat().st_size if path.exists() else 0,
            "hash": _hash_file(path),
        }
    if effect == "board_write":
        return {"seq": result.get("seq"), "path": result.get("path")}
    if effect == "verkle_link":
        return {"stdout_head": (result.get("stdout") or "")[:80],
                "rc": result.get("rc")}
    if effect == "tool_invoke":
        return {"rc": result.get("rc"), "stdout_hash": _hash_bytes((result.get("stdout") or "").encode())}
    if effect == "network_access":
        return {"status": result.get("status"), "bytes_fetched": len(result.get("body", ""))}
    if effect == "model_call":
        # AH18: real dispatch evidence — delegate ref, metered tokens/cost,
        # correlation id into effects.jsonl.  (Was {"stub": True}.)
        return {
            "delegate": result.get("delegate"),
            "model": result.get("model"),
            "total_tokens": (result.get("prompt_tokens") or 0)
                            + (result.get("completion_tokens") or 0),
            "cost_usd": result.get("cost_usd"),
            "corr_id": result.get("corr_id"),
            "effect_row_logged": result.get("effect_row_logged"),
        }
    if effect == "lane_spawn":
        # AH18: real dispatch evidence — delegate ref + spawner task_id.
        # (Was {"stub": True}.)
        return {
            "delegate": result.get("delegate"),
            "seat": result.get("seat"),
            "task_id": result.get("task_id"),
            "status": result.get("status"),
            "effect_row_logged": result.get("effect_row_logged"),
        }
    return {}


# ---------------------------------------------------------------------------
# Receipt chain
# ---------------------------------------------------------------------------

def _receipt(event_id: str, effect: str, status: str, params: dict,
             result: dict, error: str | None = None) -> dict:
    rec = {
        "schema": "effect_broker.v1",
        "event_id": event_id,
        "effect": effect,
        "status": status,
        "ts": _now(),
        "params": params,
        "result": result,
        "error": error,
    }
    return rec


def _commit_receipt(rec: dict) -> dict:
    rec["status"] = "RECEIPT_COMMITTED"
    rec["committed_ts"] = _now()
    _ensure_dirs()
    slug = f"{rec['event_id'].replace(':', '_')}_{rec['effect']}"
    # unique filename
    ts = time.strftime("%Y%m%d_%H%M%S")
    path = RECEIPTS_DIR / f"{slug}_{ts}.json"
    for i in range(100):
        if not path.exists():
            break
        path = RECEIPTS_DIR / f"{slug}_{ts}_{i}.json"
    path.write_text(json.dumps(rec, indent=2, ensure_ascii=False), encoding="utf-8")
    rec["receipt_path"] = str(path.relative_to(ROOT))
    return rec


# ---------------------------------------------------------------------------
# Authority pre-check
# ---------------------------------------------------------------------------

def _authority_ok(authority: dict, effect: str) -> tuple[bool, str]:
    # The switchboard changes a grant to EXECUTING before handing it here.
    # Reject everything else, but do not reject the intended in-flight state.
    if authority.get("status") not in {"AUTHORIZED", "EXECUTING"}:
        return False, f"status={authority.get('status')} not executable"
    caps = authority.get("granted_capabilities", [])
    if effect not in caps:
        return False, f"effect {effect} not in granted_capabilities"
    # Deep check via policy_engine if available
    pe = _load_policy_engine()
    if pe:
        verdict = pe.validate_authority(authority, effect)
        if not verdict.get("ok"):
            return False, verdict.get("reason", "policy_engine denied")
    return True, ""


# ---------------------------------------------------------------------------
# Effect implementations
# ---------------------------------------------------------------------------

def _broker_board_write(params: dict, authority: dict) -> dict:
    """Wrap switchboard.write_board_note()."""
    from . import switchboard_v2 as sb
    note = params.get("note", {})
    result = sb.write_board_note(note, authority)
    return result


def _broker_verkle_link(params: dict, authority: dict) -> dict:
    event_id = params.get("event_id", authority.get("event_id", "unknown"))
    cmd = [sys.executable, "-m", "mag.verkle_lance", "link", "--event", event_id]
    try:
        p = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=60, cwd=str(ROOT)
        )
        return {
            "ok": p.returncode == 0,
            "rc": p.returncode,
            "stdout": p.stdout,
            "stderr": p.stderr[-200:] if p.stderr else "",
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "rc": -1, "error": "timeout 60s"}
    except Exception as e:
        return {"ok": False, "rc": -1, "error": repr(e)}


def _broker_tool_invoke(params: dict, authority: dict) -> dict:
    cmd = params.get("cmd", [])
    timeout = params.get("timeout", 60)
    cwd = params.get("cwd", str(ROOT))
    # cwd lock
    cwd_real = str(Path(cwd).resolve())
    allowed = False
    for allowed_cwd in TOOL_CWD_ALLOWLIST:
        allowed_real = str(Path(allowed_cwd).resolve())
        if cwd_real.startswith(allowed_real):
            allowed = True
            break
    if not allowed:
        return {"ok": False, "error": f"cwd {cwd} not in TOOL_CWD_ALLOWLIST"}
    try:
        p = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=timeout, cwd=cwd,
        )
        return {
            "ok": p.returncode == 0,
            "rc": p.returncode,
            "stdout": p.stdout,
            "stderr": p.stderr[-200:] if p.stderr else "",
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "rc": -1, "error": f"timeout {timeout}s"}
    except Exception as e:
        return {"ok": False, "rc": -1, "error": repr(e)}


def _estimate_cost_usd(params: dict) -> float:
    """Worst-case pre-call cost: prompt chars/4 + full max_tokens completion.

    Over-estimates by design (completion rarely fills max_tokens) so the
    max_cost_usd gate fails closed; the post-call row carries the actual
    usage-based cost alongside this estimate.
    """
    prompt_tok = (len(str(params.get("system", "") or ""))
                  + len(str(params.get("user", "") or ""))) // 4
    completion_tok = int(params.get("max_tokens") or 2048)
    return (prompt_tok + completion_tok) / 1_000_000 * USD_PER_MTOK


def _broker_model_call(params: dict, authority: dict) -> dict:
    """AH18 (2026-09-29): real dispatch through the provider layer.

    Was a stub (ok=True stub=True) while the broker claimed every side
    effect routes through it — audit §3.5.  Now: authority gate (execute)
    → max_cost_usd pre-call gate → models.providers.chat_provider →
    metered effect row on effects.jsonl.  Narrow by construction: the
    broker narrows max_tokens to 2048 (the provider layer's own default
    is the 65k ceiling) and defaults tier to T2 — a brokered model_call
    is by definition an explicitly authorized remote-capable effect, and
    free_local lanes (ollama janitors) are unaffected by the tier gate.
    """
    provider = str(params.get("provider", "") or "").strip()
    if not provider:
        return {"ok": False, "error": "model_call requires provider"}
    user = str(params.get("user", "") or "")
    if not user.strip():
        return {"ok": False, "error": "model_call requires non-empty user prompt"}

    corr_id = authority.get("event_id", params.get("event_id", "anon"))
    est = _estimate_cost_usd(params)
    max_cost = params.get("max_cost_usd")
    if max_cost is not None:
        try:
            cap = float(max_cost)
        except (TypeError, ValueError):
            return {"ok": False, "error": f"max_cost_usd not a number: {max_cost!r}"}
        if est > cap:
            return {
                "ok": False,
                "error": f"budget exceeded: worst-case estimate ${est:.6f} > "
                         f"max_cost_usd ${cap:.6f} (rate ${USD_PER_MTOK}/Mtok)",
                "estimated_cost_usd": round(est, 8),
                "max_cost_usd": cap,
                "corr_id": corr_id,
            }

    from models.providers import chat_provider
    r = chat_provider(
        provider,
        str(params.get("system", "") or ""),
        user,
        model=params.get("model") or None,
        max_tokens=int(params.get("max_tokens") or 2048),
        tier=str(params.get("tier", "T2")),
        session_id=str(params.get("session_id")
                       or f"broker:{corr_id}"),
        timeout=params.get("timeout"),
        allow_peak=bool(params.get("allow_peak", False)),
    )
    if not r.get("ok"):
        return {"ok": False, "error": r.get("error", "provider call failed"),
                "provider": provider, "corr_id": corr_id,
                "delegate": "models.providers.chat_provider"}

    usage = r.get("usage") or {}
    pt = int(usage.get("prompt_tokens") or 0)
    ct = int(usage.get("completion_tokens") or 0)
    cost = (pt + ct) / 1_000_000 * USD_PER_MTOK
    _append_effect_row("model_call", {
        "corr_id": corr_id,
        "provider": provider,
        "model": r.get("model"),
        "prompt_tokens": pt,
        "completion_tokens": ct,
        "cost_usd": round(cost, 8),
        "estimated_cost_usd": round(est, 8),
    })
    out = {
        "ok": True,
        "delegate": "models.providers.chat_provider",
        "provider": provider,
        "model": r.get("model"),
        "text": r.get("text", ""),
        "usage": usage,
        "prompt_tokens": pt,
        "completion_tokens": ct,
        "cost_usd": round(cost, 8),
        "estimated_cost_usd": round(est, 8),
        "corr_id": corr_id,
        "budget_after": r.get("budget_after"),
        "effect_row_logged": True,
    }
    if max_cost is not None and cost > cap:
        # Post-hoc honesty (the pre-call gate passed but actual usage crossed
        # the cap, e.g. an unknown-model rate mismatch): the call already
        # happened, so the receipt stays COMPLETED with the overrun flagged,
        # never hidden and never misreported as a denial.
        out["budget_exceeded_post"] = True
    return out


def _broker_network_access(params: dict, authority: dict) -> dict:
    url = params.get("url", "")
    # denylist check
    for deny in NETWORK_DENYLIST:
        if deny in url:
            return {"ok": False, "error": f"url contains denied pattern: {deny}"}
    method = params.get("method", "GET").upper()
    max_bytes = params.get("max_bytes", 100_000)
    try:
        import urllib.request
        req = urllib.request.Request(url, method=method)
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read(max_bytes)
            return {
                "ok": True,
                "status": resp.status,
                "body": body.decode("utf-8", errors="replace"),
                "url": url,
            }
    except Exception as e:
        return {"ok": False, "error": repr(e)}


def _broker_fs_write(params: dict, authority: dict) -> dict:
    path = Path(params.get("path", ""))
    content = params.get("content", "")
    mode = params.get("mode", "write")  # write | append
    # allowlist check
    path_real = str(path.resolve())
    allowed = False
    for prefix in FS_ALLOWLIST:
        prefix_real = str(Path(prefix).resolve())
        if path_real.startswith(prefix_real):
            allowed = True
            break
    if not allowed:
        return {"ok": False, "error": f"path {path} not in FS_ALLOWLIST"}
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if mode == "append":
            with path.open("a", encoding="utf-8") as f:
                f.write(content)
        else:
            path.write_text(content, encoding="utf-8")
        return {"ok": True, "path": str(path), "bytes_written": len(content.encode("utf-8"))}
    except Exception as e:
        return {"ok": False, "error": repr(e)}


def _broker_lane_spawn(params: dict, authority: dict) -> dict:
    """AH18 (2026-09-29): real delegate to the estate's lane spawner.

    mag/seat_dispatch.py owns spawning (HEADLESS verified launchers +
    MAILBOX inbox writes); this broker adds the authority gate, the budget
    decrement (execute) and the metered effect row.  A HEADLESS dispatch is
    a real subprocess spawn; a MAILBOX seat lands the task in the seat
    INBOX and returns status "queued" (the operator asks the GUI seat to
    work it) — both count as dispatched.
    """
    goal = str(params.get("task") or "").strip()
    if not goal:
        return {"ok": False, "error": "lane_spawn requires non-empty task"}

    corr_id = authority.get("event_id", params.get("event_id", "anon"))
    from mag import seat_dispatch
    r = seat_dispatch.task(
        goal,
        seat=str(params.get("seat", "auto")),
        model=str(params.get("model", "") or ""),
        tag=str(params.get("tag") or f"broker-{corr_id}"),
    )
    seat = r.get("seat", params.get("seat", "auto"))
    status = str(r.get("status", "failed"))
    ok = bool(r.get("ok")) and status in ("done", "queued")
    out = {
        "ok": ok,
        "delegate": "mag.seat_dispatch.task",
        "corr_id": corr_id,
        "seat": seat,
        "status": status,
        "task_id": r.get("task_id"),
        "detail": r.get("detail", r.get("error", "")),
        "effect_row_logged": False,
    }
    if not ok:
        out["error"] = r.get("error") or f"seat_dispatch status {status}"
        return out
    _append_effect_row("lane_spawn", {
        "corr_id": corr_id,
        "seat": seat,
        "status": status,
        "task_id": r.get("task_id"),
        "goal_head": goal[:80],
    })
    out["effect_row_logged"] = True
    return out


BROKERS = {
    "board_write": _broker_board_write,
    "verkle_link": _broker_verkle_link,
    "tool_invoke": _broker_tool_invoke,
    "model_call": _broker_model_call,
    "network_access": _broker_network_access,
    "fs_write": _broker_fs_write,
    "lane_spawn": _broker_lane_spawn,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def execute(effect: str, params: dict, authority: dict) -> dict:
    """Execute an effect through the broker.  Returns a RECEIPT_COMMITTED dict.

    Receipt state machine:
        ENQUEUED → RUNNING → (COMPLETED | FAILED) → RECEIPT_COMMITTED
    """
    event_id = authority.get("event_id", params.get("event_id", f"anon-{int(time.time())}"))

    # 1. ENQUEUED
    rec = _receipt(event_id, effect, "ENQUEUED", params, {})

    # 2. Authority gate
    ok, reason = _authority_ok(authority, effect)
    if not ok:
        rec["status"] = "FAILED"
        rec["error"] = f"authority check failed: {reason}"
        return _commit_receipt(rec)

    # Validation is intentionally a non-mutating preflight.  Consume one
    # budget unit only after the authority gate passes and before the effect
    # can run; otherwise a budget existed only in prose and unlimited calls
    # slipped through the broker.
    pe = _load_policy_engine()
    # board_write has a second, policy-aware reference-monitor implementation
    # in switchboard_v2.write_board_note(); it validates and charges its own
    # budget after the broker preflight. Leave that effect to its owner so a
    # central pre-charge cannot make the owner's revalidation reject call 3.
    if pe is not None and effect != "board_write":
        budget_ok, remaining = pe.check_budget(authority, effect, decrement=True)
        rec["budget_remaining"] = remaining
        if not budget_ok:
            rec["status"] = "FAILED"
            rec["error"] = "budget exhausted"
            return _commit_receipt(rec)

    # 3. RUNNING
    rec["status"] = "RUNNING"
    rec["pre_state"] = _pre_state(effect, params)

    broker = BROKERS.get(effect)
    if broker is None:
        rec["status"] = "FAILED"
        rec["error"] = f"unknown effect: {effect}"
        return _commit_receipt(rec)

    try:
        result = broker(params, authority)
    except Exception as e:
        rec["status"] = "FAILED"
        rec["error"] = repr(e)
        rec["post_state"] = _post_state(effect, params, {})
        return _commit_receipt(rec)

    rec["result"] = result
    rec["post_state"] = _post_state(effect, params, result)

    if result.get("ok"):
        rec["status"] = "COMPLETED"
    else:
        rec["status"] = "FAILED"
        rec["error"] = result.get("error", "broker returned ok=False")

    # 4. Postcondition evidence
    rec["postcondition_evidence"] = _postcondition_evidence(effect, params, result)

    return _commit_receipt(rec)


def get_receipt(event_id: str, effect: str | None = None) -> dict | None:
    """Load the most recent receipt for an event_id / effect."""
    _ensure_dirs()
    candidates = []
    for p in RECEIPTS_DIR.glob("*.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if data.get("event_id") == event_id:
                if effect is None or data.get("effect") == effect:
                    candidates.append(data)
        except Exception:
            pass
    if not candidates:
        return None
    # newest by committed_ts
    candidates.sort(key=lambda x: x.get("committed_ts", ""), reverse=True)
    return candidates[0]


def list_receipts(limit: int = 50) -> list[dict]:
    _ensure_dirs()
    out = []
    for p in sorted(RECEIPTS_DIR.glob("*.json"), reverse=True)[:limit]:
        try:
            out.append(json.loads(p.read_text(encoding="utf-8")))
        except Exception:
            pass
    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def cmd_execute(args):
    authority = json.loads(args.authority_file.read_text(encoding="utf-8"))
    params = json.loads(args.params_file.read_text(encoding="utf-8")) if args.params_file else {}
    rec = execute(args.effect, params, authority)
    print(json.dumps(rec, indent=2, ensure_ascii=False))
    return 0 if rec["status"] == "RECEIPT_COMMITTED" and rec.get("result", {}).get("ok") else 1


def cmd_receipt(args):
    rec = get_receipt(args.event_id, args.effect)
    if rec:
        print(json.dumps(rec, indent=2, ensure_ascii=False))
        return 0
    print(json.dumps({"ok": False, "error": "receipt not found"}, indent=2))
    return 1


def cmd_status(args):
    receipts = list_receipts(args.limit)
    summary = {
        "ok": True,
        "total_receipts": len(list(RECEIPTS_DIR.glob("*.json"))),
        "recent": receipts,
        "effects": {},
    }
    for r in receipts:
        eff = r.get("effect", "unknown")
        st = r.get("status", "unknown")
        summary["effects"].setdefault(eff, {}).setdefault(st, 0)
        summary["effects"][eff][st] += 1
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


def cmd_test(args):
    """Run 5 basic self-tests."""
    results = []
    _ensure_dirs()

    # Test 1: authorized pass (fs_write to allowed path)
    auth_ok = {
        "status": "AUTHORIZED",
        "granted_capabilities": ["fs_write"],
        "event_id": "test-1",
        "budget": {"max_calls": 5},
        "ts": _now(),
        "ttl_seconds": 900,
    }
    test_path = ROOT / "memory" / "effect_broker_test_1.txt"
    rec1 = execute("fs_write", {"path": str(test_path), "content": "hello world"}, auth_ok)
    ok1 = rec1["status"] == "RECEIPT_COMMITTED" and rec1.get("result", {}).get("ok")
    results.append({"test": 1, "name": "authorized_fs_write", "pass": ok1,
                    "detail": rec1.get("postcondition_evidence", {})})
    if test_path.exists():
        test_path.unlink()

    # Test 2: unauthorized fail (wrong capability)
    auth_bad = {
        "status": "AUTHORIZED",
        "granted_capabilities": ["board_write"],
        "event_id": "test-2",
    }
    rec2 = execute("fs_write", {"path": str(test_path), "content": "x"}, auth_bad)
    ok2 = rec2["status"] == "RECEIPT_COMMITTED" and not rec2.get("result", {}).get("ok")
    results.append({"test": 2, "name": "unauthorized_fs_write", "pass": ok2,
                    "detail": rec2.get("error", "")[:60]})

    # Test 3: fs deny (path outside allowlist)
    auth_deny = {
        "status": "AUTHORIZED",
        "granted_capabilities": ["fs_write"],
        "event_id": "test-3",
    }
    rec3 = execute("fs_write", {"path": "/etc/passwd", "content": "x"}, auth_deny)
    ok3 = rec3["status"] == "RECEIPT_COMMITTED" and not rec3.get("result", {}).get("ok")
    results.append({"test": 3, "name": "fs_deny_outside_allowlist", "pass": ok3,
                    "detail": rec3.get("error", "")[:60]})

    # Test 4: network deny (localhost)
    auth_net = {
        "status": "AUTHORIZED",
        "granted_capabilities": ["network_access"],
        "event_id": "test-4",
    }
    rec4 = execute("network_access", {"url": "http://127.0.0.1:8000/secret"}, auth_net)
    ok4 = rec4["status"] == "RECEIPT_COMMITTED" and not rec4.get("result", {}).get("ok")
    results.append({"test": 4, "name": "network_deny_localhost", "pass": ok4,
                    "detail": rec4.get("error", "")[:60]})

    # Test 5: tool timeout (sleep longer than timeout)
    auth_tool = {
        "status": "AUTHORIZED",
        "granted_capabilities": ["tool_invoke"],
        "event_id": "test-5",
    }
    rec5 = execute("tool_invoke", {"cmd": ["sleep", "10"], "timeout": 1}, auth_tool)
    ok5 = rec5["status"] == "RECEIPT_COMMITTED" and not rec5.get("result", {}).get("ok")
    results.append({"test": 5, "name": "tool_timeout", "pass": ok5,
                    "detail": rec5.get("error", "")[:60]})

    all_pass = all(r["pass"] for r in results)
    print(json.dumps({
        "ok": all_pass,
        "tests": results,
        "summary": f"{sum(r['pass'] for r in results)}/{len(results)} passed",
    }, indent=2, ensure_ascii=False))
    return 0 if all_pass else 1


def main(argv=None):
    ap = argparse.ArgumentParser(prog="mag.effect_broker")
    sub = ap.add_subparsers(dest="cmd", required=True)

    e = sub.add_parser("execute", help="execute an effect with authority")
    e.add_argument("effect")
    e.add_argument("--authority-file", type=Path, required=True)
    e.add_argument("--params-file", type=Path, default=None)
    e.set_defaults(func=cmd_execute)

    r = sub.add_parser("receipt", help="get a receipt by event_id")
    r.add_argument("event_id")
    r.add_argument("--effect", default=None)
    r.set_defaults(func=cmd_receipt)

    s = sub.add_parser("status", help="list recent receipts")
    s.add_argument("--limit", type=int, default=20)
    s.set_defaults(func=cmd_status)

    t = sub.add_parser("test", help="run self-tests")
    t.set_defaults(func=cmd_test)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
