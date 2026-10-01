"""Object-oriented temperature stacks — adjustable timings + token heat.

Stacks (cold → scarce) encode how long a job may run, how many tokens it may
burn, and which seat class is appropriate. Config: configs/temperature_stacks.yaml

Also:
  - PointerKnot — Verkle-style “where to find it” (path/url/github), not bulk dump
  - track_loop_gap — anything not built into the loop becomes a training + improve token

  mag_loop_gap.v1 row shape (spec, B2-80): every row carries the base fields
  schema/ts/ts_unix/name/detail/where/kind/dedupe/stack. Rows sourced from the
  lifecycle (track_lifecycle_into_improve) additionally carry `should` (the
  _policy_should verdict "on"/"off", mag/lifecycle.py), `should_reason` (the
  policy reason string), and `signals` (the probe inputs queue_depth,
  fleet_running, operator_active, drainer_allowed, browser_enabled) so a
  gap-vs-waste flip is auditable from the row alone; non-lifecycle rows stay
  variable-field (improve_candidate/pointer already appear conditionally).

Usage:
  from mag.temperature_stack import stack_for_goal, timeout_for_goal, file_pointer_knot
  st = stack_for_goal("implement dual-progress fix")
  timeout_for_goal(goal, tag="x")  # uses stack
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import socket
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT

CONFIG_PATH = ROOT / "configs" / "temperature_stacks.yaml"
STATE_PATH = ROOT / "state" / "temperature_stacks_latest.json"
POINTERS_DIR = ROOT / "memory" / "biography" / "pointer_knots"
POINTERS_CHAIN = ROOT / "memory" / "biography" / "pointer_chain.jsonl"
GAPS_LOG = ROOT / "memory" / "training" / "loop_gaps.jsonl"
SCHEMA = "mag_temperature_stacks.v1"


def _gaps_log() -> Path:
    """Gap log path; MAG_GAPS_LOG env override points it elsewhere (tests use tmp_path).

    Fix receipt B2-79 (2026-09-26, watch/inbox/burn_wave_20260926/B2_79_pollution_fix_20260926.md):
    cause was tests/test_temperature_stack.py calling track_loop_gap(force=True), which
    appended test_gap_unique_xyz rows to the production log through the module constant
    GAPS_LOG (17 rows, 2026-08-06 to 2026-09-26, verified on bytes at fix time); the env
    override decouples the writer from the production path without touching the rows.
    """
    env = os.environ.get("MAG_GAPS_LOG", "").strip()
    if env:
        return Path(env)
    return GAPS_LOG

_CACHE: dict[str, Any] | None = None
_CACHE_MTIME: float = 0.0


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_raw() -> dict[str, Any]:
    global _CACHE, _CACHE_MTIME
    try:
        mtime = CONFIG_PATH.stat().st_mtime if CONFIG_PATH.is_file() else 0.0
    except OSError:
        mtime = 0.0
    if _CACHE is not None and mtime == _CACHE_MTIME:
        return _CACHE
    raw: dict[str, Any] = {
        "schema": SCHEMA,
        "loops": {
            "supervisor_check_s": 5,
            "lifecycle_reconcile_every_s": 60,
            "mag_idle_interval_s": 120,
            "watch_interval_s": 5,
            "external_seat_stale_s": 300,
        },
        "stacks": {},
        "default_stack": "warm",
        "gap_tracking": {"enabled": True, "dedupe_hours": 12},
    }
    if CONFIG_PATH.is_file():
        try:
            import yaml  # type: ignore

            data = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
            if isinstance(data, dict):
                raw.update(data)
        except Exception:
            pass
    _CACHE = raw
    _CACHE_MTIME = mtime
    return raw


@dataclass
class TimingProfile:
    """Wall-clock and sampling knobs for one heat band."""

    timeout_s: int = 600
    max_tokens: int = 4096
    temperature: float = 0.2
    mag_idle_interval_s: int | None = None

    def scaled_timeout(self, *, size_hint: int = 0) -> int:
        """Grow timeout when payload/goal is large (chars or file count)."""
        base = int(self.timeout_s)
        if size_hint <= 0:
            return base
        # +30% per ~20k chars, cap 2.5x
        boost = min(1.5, 0.3 * (size_hint / 20000.0))
        return int(base * (1.0 + boost))


@dataclass
class TemperatureStack:
    """One heat band — object, not a string flag."""

    id: str
    label: str = ""
    token_class: str = "local_free"
    temperature: float = 0.2
    max_tokens: int = 4096
    timeout_s: int = 600
    seat_hint: str = "ollama"
    when: str = ""
    keywords: list[str] = field(default_factory=list)

    @property
    def timing(self) -> TimingProfile:
        return TimingProfile(
            timeout_s=self.timeout_s,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
        )

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["timing"] = asdict(self.timing)
        return d


@dataclass
class PointerKnot:
    """Where to find huge info — path, github, note — not the blob itself.

    Verkle-compatible leaf: hash of payload pointer, chain tip separate.
    """

    kind: str  # code | note | github | instruction | config | url | dir
    ref: str  # path or URL
    summary: str = ""
    tags: list[str] = field(default_factory=list)
    knot_id: str = ""
    leaf_hash: str = ""
    ts: str = ""

    def to_leaf(self) -> dict[str, Any]:
        return {
            "schema": "mag_pointer_knot.v1",
            "knot_id": self.knot_id,
            "kind": self.kind,
            "ref": self.ref,
            "summary": self.summary[:500],
            "tags": self.tags[:12],
            "leaf_hash": self.leaf_hash,
            "ts": self.ts or _now(),
            "note": "LOAD by ref — do not paste corpus into seats",
        }


class TemperatureRegistry:
    """Loads config, resolves stacks, exposes loop timings."""

    def __init__(self, raw: dict[str, Any] | None = None) -> None:
        self.raw = raw or _load_raw()
        self.stacks: dict[str, TemperatureStack] = {}
        for sid, body in (self.raw.get("stacks") or {}).items():
            if not isinstance(body, dict):
                continue
            self.stacks[str(sid)] = TemperatureStack(
                id=str(sid),
                label=str(body.get("label") or sid),
                token_class=str(body.get("token_class") or "local_free"),
                temperature=float(body.get("temperature") or 0.2),
                max_tokens=int(body.get("max_tokens") or 4096),
                timeout_s=int(body.get("timeout_s") or 600),
                seat_hint=str(body.get("seat_hint") or "ollama"),
                when=str(body.get("when") or ""),
                keywords=[str(k).lower() for k in (body.get("keywords") or [])],
            )
        self.default_id = str(self.raw.get("default_stack") or "warm")
        self.loops = dict(self.raw.get("loops") or {})
        self.gap_tracking = dict(self.raw.get("gap_tracking") or {})

    def get(self, stack_id: str) -> TemperatureStack:
        if stack_id in self.stacks:
            return self.stacks[stack_id]
        if self.default_id in self.stacks:
            return self.stacks[self.default_id]
        return TemperatureStack(id="warm")

    def resolve(self, goal: str = "", *, tag: str = "", explicit: str | None = None) -> TemperatureStack:
        if explicit and explicit in self.stacks:
            return self.stacks[explicit]
        blob = f"{goal} {tag}".lower()
        if "[improve]" in blob or (tag or "").lower().startswith("improve"):
            if "improve" in self.stacks:
                return self.stacks["improve"]
        # score keyword hits — longer keywords first
        best: TemperatureStack | None = None
        best_score = 0
        for st in self.stacks.values():
            score = 0
            for kw in st.keywords:
                if kw and kw in blob:
                    score += len(kw)
            if score > best_score:
                best_score = score
                best = st
        if best and best_score > 0:
            return best
        return self.get(self.default_id)

    def loop_s(self, key: str, default: float | int) -> float:
        try:
            return float(self.loops.get(key, default))
        except (TypeError, ValueError):
            return float(default)

    def snapshot(self) -> dict[str, Any]:
        return {
            "ok": True,
            "schema": SCHEMA,
            "ts": _now(),
            "config": str(CONFIG_PATH.relative_to(ROOT)) if CONFIG_PATH.is_file() else str(CONFIG_PATH),
            "loops": self.loops,
            "default_stack": self.default_id,
            "stacks": {k: v.to_dict() for k, v in self.stacks.items()},
            "gap_tracking": self.gap_tracking,
            "hint": "Edit configs/temperature_stacks.yaml — hot reloads on next resolve",
        }


def registry() -> TemperatureRegistry:
    return TemperatureRegistry(_load_raw())


def stack_for_goal(goal: str = "", *, tag: str = "", stack: str | None = None) -> TemperatureStack:
    return registry().resolve(goal, tag=tag, explicit=stack)


def timeout_for_goal(
    goal: str = "",
    *,
    tag: str = "",
    timeout: int | None = None,
    size_hint: int = 0,
    stack: str | None = None,
) -> int:
    """Orchestrator/agent wall timeout from temperature stack (+ size boost)."""
    if timeout is not None and timeout > 0:
        # explicit override always wins
        return int(timeout)
    st = stack_for_goal(goal, tag=tag, stack=stack)
    return st.timing.scaled_timeout(size_hint=size_hint or len(goal or ""))


def sampling_for_goal(goal: str = "", *, tag: str = "", stack: str | None = None) -> dict[str, Any]:
    st = stack_for_goal(goal, tag=tag, stack=stack)
    return {
        "stack": st.id,
        "temperature": st.temperature,
        "max_tokens": st.max_tokens,
        "timeout_s": st.timeout_s,
        "token_class": st.token_class,
        "seat_hint": st.seat_hint,
    }


def loop_timings() -> dict[str, float]:
    reg = registry()
    return {
        "supervisor_check_s": reg.loop_s("supervisor_check_s", 5),
        "lifecycle_reconcile_every_s": reg.loop_s("lifecycle_reconcile_every_s", 60),
        "mag_idle_interval_s": reg.loop_s("mag_idle_interval_s", 120),
        "watch_interval_s": reg.loop_s("watch_interval_s", 5),
        "external_seat_stale_s": reg.loop_s("external_seat_stale_s", 300),
    }


# ── Pointer knots (where, not what) ──────────────────────────────────────────


def _leaf_hash(obj: dict[str, Any]) -> str:
    raw = json.dumps(obj, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(b"ptr:" + raw).hexdigest()


def file_pointer_knot(
    ref: str,
    *,
    kind: str = "path",
    summary: str = "",
    tags: list[str] | None = None,
) -> dict[str, Any]:
    """FILE a pointer knot — huge info stays on disk/github; seats get the address."""
    ref = (ref or "").strip()
    if not ref:
        return {"ok": False, "error": "ref required"}
    kind = (kind or "path").strip().lower()
    if kind not in ("code", "note", "github", "instruction", "config", "url", "dir", "path"):
        kind = "path"
    knot_id = "pk-" + hashlib.sha256(ref.encode()).hexdigest()[:12]
    pk = PointerKnot(
        kind=kind,
        ref=ref,
        summary=summary or f"pointer to {kind}",
        tags=list(tags or [])[:12],
        knot_id=knot_id,
        ts=_now(),
    )
    leaf = pk.to_leaf()
    leaf["leaf_hash"] = _leaf_hash({k: leaf[k] for k in ("kind", "ref", "summary", "tags")})
    pk.leaf_hash = leaf["leaf_hash"]

    POINTERS_DIR.mkdir(parents=True, exist_ok=True)
    path = POINTERS_DIR / f"{knot_id}.json"
    path.write_text(json.dumps(leaf, indent=2), encoding="utf-8")
    try:
        POINTERS_CHAIN.parent.mkdir(parents=True, exist_ok=True)
        with POINTERS_CHAIN.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": leaf["ts"], "knot_id": knot_id, "leaf_hash": leaf["leaf_hash"], "ref": ref}, default=str) + "\n")
    except OSError:
        pass

    # Training token — organic self-improve corpus
    try:
        from mag.training_events import emit

        emit(
            "pointer_knot",
            join={"knot_id": knot_id},
            input_data={"kind": kind, "ref": ref[:500]},
            action={"file": str(path.relative_to(ROOT))},
            outcome={"leaf_hash": leaf["leaf_hash"][:16]},
            pattern_tags=["pointer", "verkle_style", kind],
            tier_max="T2",
        )
    except Exception:
        pass

    return {"ok": True, "knot": leaf, "path": str(path.relative_to(ROOT))}


# ── Gap tracking (not in the loop → tokenize) ────────────────────────────────


def _gap_dedupe_key(name: str, detail: str) -> str:
    return hashlib.sha256(f"{name}|{detail}".encode()).hexdigest()[:16]


def _recently_tracked(key: str, hours: float) -> bool:
    gaps_log = _gaps_log()
    if not gaps_log.is_file():
        return False
    cutoff = time.time() - hours * 3600
    try:
        for line in reversed(gaps_log.read_text(encoding="utf-8", errors="replace").splitlines()[-200:]):
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("dedupe") == key:
                ts = row.get("ts_unix") or 0
                if float(ts) >= cutoff:
                    return True
    except OSError:
        pass
    return False


def _piece_of(name: str, kind: str) -> str:
    """The piece a lifecycle row watches: 'lifecycle_gap:drainer' and
    'lifecycle_waste:drainer' share the piece 'drainer' (B2-346: the differing
    names are exactly why gap and waste rows never shared a dedupe key)."""
    prefix = ""
    if kind.startswith("lifecycle_"):
        prefix = kind + ":"
    if name.startswith(prefix):
        return name[len(prefix):].strip()
    return ""


def _prev_lifecycle_verdict(piece: str) -> dict | None:
    """Most recent prior lifecycle row for the same piece that carries a
    should verdict (bounded tail scan, same window as _recently_tracked).
    B2-346: the flip link - two consecutive opposite-verdict rows for one
    piece must be traceable from either row alone."""
    if not piece:
        return None
    gaps_log = _gaps_log()
    if not gaps_log.is_file():
        return None
    try:
        tail = gaps_log.read_text(encoding="utf-8", errors="replace").splitlines()[-200:]
    except OSError:
        return None
    for line in reversed(tail):
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if (row.get("kind") in ("lifecycle_gap", "lifecycle_waste")
                and _piece_of(str(row.get("name") or ""), str(row.get("kind"))) == piece
                and row.get("should")):
            return {"ts": row.get("ts"), "should": str(row.get("should"))[:8],
                    "row": row.get("name")}
    return None


def track_loop_gap(
    name: str,
    *,
    detail: str = "",
    where: str = "",
    kind: str = "missing_capability",
    force: bool = False,
    lifecycle: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Something not built into the loop — auto token for improve + training.

    Call from lifecycle waste/gaps, missing browser driver, dead Startup, etc.
    Deduped so it does not spam the queue.

    lifecycle: optional carry from build_lifecycle for one piece; when truthy
    the row gains should/should_reason/signals per the mag_loop_gap.v1 spec
    above. Callers with no lifecycle verdict omit it and the row stays
    variable-field.
    """
    reg = registry()
    gt = reg.gap_tracking
    if not force and not gt.get("enabled", True):
        return {"ok": True, "skipped": True, "reason": "gap_tracking disabled"}

    name = (name or "").strip() or "unnamed_gap"
    detail = (detail or "").strip()[:800]
    where = (where or "").strip()[:400]
    # B2-394 (2026-09-26): every gap row now names its observing process.
    # Cause: the 89 lifecycle_gap:ollama rows were written by SOME process
    # whose probe could not reach 127.0.0.1:11434 while an independent
    # 31s-cadence poller answered 200 at 70-90ms in the same seconds (B2-81),
    # and the row's where= is a hardcoded route label ("GET /api/v1/lifecycle",
    # the track_lifecycle_into_improve caller), not an identity, so the
    # writer was unreconstructable after the fact. The proxy mechanism
    # reproduces the signature, so proxy env vars ride along with pid/exe/
    # host, appended into the existing detail field (falsifier: a new
    # lifecycle_gap row whose detail cannot name the writing process).
    _proxy = " ".join(
        ("%s=%s" % (k, os.environ.get(k, "")))[:80]
        for k in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
                  "http_proxy", "https_proxy")
        if os.environ.get(k)
    ) or "proxies=none"
    detail = "%s [writer pid=%s exe=%s host=%s %s]" % (
        detail, os.getpid(), (sys.executable or "")[:80],
        (socket.gethostname() or "")[:60], _proxy,
    )[:1000]
    key = _gap_dedupe_key(name, detail)
    hours = float(gt.get("dedupe_hours") or 12)
    if not force and _recently_tracked(key, hours):
        return {"ok": True, "skipped": True, "reason": "deduped", "dedupe": key}

    row = {
        "schema": "mag_loop_gap.v1",
        "ts": _now(),
        "ts_unix": time.time(),
        "name": name,
        "detail": detail,
        "where": where,
        "kind": kind,
        "dedupe": key,
        "stack": "improve",
    }
    if lifecycle:
        # B2-80 fix (2026-09-26): lifecycle rows previously persisted none of
        # the _policy_should verdict (mag/lifecycle.py:445) or its probe
        # inputs, so drainer gap 17 vs waste 87 rows and 4 sub-hour verdict
        # flips were unauditable after the fact (B2-20 census,
        # watch/inbox/burn_wave_20260926/B2_20_loop_gaps_20260926.md; 18 vs 88
        # on bytes at fix time). Evidence: 313-row log, zero rows carrying
        # should/should_reason/signals pre-fix.
        row["should"] = str(lifecycle.get("should") or "")[:8]
        row["should_reason"] = str(lifecycle.get("reason") or "")[:400]
        row["signals"] = dict(lifecycle.get("signals") or {})
        # B2-346 (2026-09-26): the per-piece flip link. Piece id (name minus
        # the lifecycle_gap:/lifecycle_waste: prefix) plus the previous
        # verdict row for the same piece, so a sub-hour gap/waste flip is
        # auditable from either row alone instead of landing as two unrelated
        # dedupe keys. Falsifier precondition held on bytes: the drainer
        # flip pairs in memory/training/loop_gaps.jsonl shared no linking
        # field pre-fix.
        pid = _piece_of(row["name"], row["kind"])
        row["piece"] = pid
        prev = _prev_lifecycle_verdict(pid)
        if prev:
            row["prev_verdict"] = prev
            row["flip"] = bool(prev.get("should") and prev["should"] != row["should"])
    try:
        gaps_log = _gaps_log()
        gaps_log.parent.mkdir(parents=True, exist_ok=True)
        with gaps_log.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError:
        pass

    # Training event
    try:
        from mag.training_events import emit

        join = {"gap": name[:80]}
        # B2-345 (2026-09-26): carry the lifecycle verdict into the training
        # join so the token is attributable whenever the gap row is (B2-80
        # made the row carry should/should_reason/signals; the emit and the
        # improve candidate still named only the piece id). Bounded fields,
        # no schema change to the event shape.
        if lifecycle:
            join["should"] = str(lifecycle.get("should") or "")[:8]
            join["should_reason"] = str(lifecycle.get("reason") or "")[:200]
            join["signals"] = {
                str(k)[:40]: str(v)[:80]
                for k, v in list((lifecycle.get("signals") or {}).items())[:8]
            }
        emit(
            str(gt.get("train_pattern") or "lifecycle_gap"),
            join=join,
            input_data={"detail": detail, "where": where, "kind": kind},
            action={"track": "loop_gap"},
            outcome={"dedupe": key},
            pattern_tags=["self_improve", "gap", kind],
            tier_max="T2",
        )
    except Exception:
        pass

    # Improve candidate (organic self-improve feed)
    try:
        from mag.improve import append_candidates, ensure_dirs, load_config

        cfg = load_config()
        paths = ensure_dirs(cfg)
        cid = "gap-" + key
        claim = f"[loop gap] {name}: {detail or where or kind}"
        # B2-345 (2026-09-26): the candidate claim carries the lifecycle
        # verdict too, same attribution law as the training join above.
        if lifecycle:
            claim = "%s [should=%s reason=%s]" % (
                claim,
                str(lifecycle.get("should") or "")[:8],
                str(lifecycle.get("reason") or "")[:160],
            )
        append_candidates(
            [
                {
                    "id": cid,
                    "ts": _now(),
                    "claim": claim,
                    "url": where or f"mag://gap/{key}",
                    "source": str(gt.get("improve_source") or "mag_temperature_gap"),
                    "status": "new",
                    "kind_hint": "stack_gap",
                    "local_feasible": "yes",
                    "tags": ["loop_gap", "auto", kind],
                }
            ],
            paths,
        )
        row["improve_candidate"] = cid
    except Exception as exc:
        row["improve_error"] = str(exc)[:120]

    # Pointer if where looks like a path/url
    if where and (where.startswith("http") or "/" in where or "\\" in where):
        try:
            pk = file_pointer_knot(
                where,
                kind="github" if "github.com" in where else ("url" if where.startswith("http") else "path"),
                summary=f"gap:{name}",
                tags=["loop_gap", name[:24]],
            )
            row["pointer"] = pk.get("knot", {}).get("knot_id")
        except Exception:
            pass

    return {"ok": True, "gap": row}


def _lifecycle_carry(lc: dict[str, Any], piece_id: str) -> dict[str, Any]:
    """Should verdict + reason + probe inputs for one lifecycle piece (B2-80).

    Feeds the mag_loop_gap.v1 spec fields: the piece's _policy_should verdict
    and reason plus the build_lifecycle signal inputs that produced them.
    """
    piece = next(
        (p for p in (lc.get("pieces") or []) if isinstance(p, dict) and p.get("id") == piece_id),
        {},
    )
    return {
        "should": piece.get("should"),
        "reason": piece.get("reason"),
        "signals": dict(lc.get("signals") or {}),
    }


def track_lifecycle_into_improve() -> dict[str, Any]:
    """Pull lifecycle waste/gaps into training tokens (organic)."""
    tracked: list[dict[str, Any]] = []
    try:
        from mag.lifecycle import build_lifecycle

        lc = build_lifecycle()
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:160]}

    for gid in lc.get("gaps") or []:
        tracked.append(
            track_loop_gap(
                f"lifecycle_gap:{gid}",
                detail=f"should be on but actual off — piece={gid}",
                where="GET /api/v1/lifecycle",
                kind="lifecycle_gap",
                lifecycle=_lifecycle_carry(lc, gid),
            )
        )
    for wid in lc.get("waste") or []:
        tracked.append(
            track_loop_gap(
                f"lifecycle_waste:{wid}",
                detail=f"should be off but still on — piece={wid} (token/cpu waste)",
                where="GET /api/v1/lifecycle",
                kind="lifecycle_waste",
                lifecycle=_lifecycle_carry(lc, wid),
            )
        )
    # Missing browser driver when operator wants computer-use
    try:
        from mag.browser_env import status as browser_status

        bs = browser_status()
        if not bs.get("ready") and not bs.get("enabled"):
            tracked.append(
                track_loop_gap(
                    "browser_env_not_wired",
                    detail="OpenClaw/Playwright computer-use seat not enabled — allowlist only scaffold",
                    where="configs/browser_env.yaml",
                    kind="missing_seat",
                )
            )
    except Exception:
        pass

    snap = registry().snapshot()
    try:
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        STATE_PATH.write_text(
            json.dumps(
                {
                    "ts": _now(),
                    "loops": snap.get("loops"),
                    "default_stack": snap.get("default_stack"),
                    "lifecycle_posture": lc.get("posture"),
                    "tracked_n": len(tracked),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    except OSError:
        pass

    return {
        "ok": True,
        "tracked": tracked,
        "n": len(tracked),
        "posture": lc.get("posture"),
    }


def write_state_snapshot() -> Path:
    snap = registry().snapshot()
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(snap, indent=2), encoding="utf-8")
    return STATE_PATH
