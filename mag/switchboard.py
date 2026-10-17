"""Switchboard — unified seat mesh, orphan reap, tier-bounded steer drops (v3-014).

No orphan processes: every live child is a peer in one mesh, grouped by platform,
API flags, fleet role, and importance. Conductor/spider route through here for
telepathic steering — lawful cross-seat context drops (tier-bounded spooky share).

CLI: python main.py switchboard status|reap|peers|drop|mesh|route
Trail: memory/runs/switchboard_trail.jsonl
"""
from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None

from config import ROOT

SCHEMA = "switchboard.v1"
TRAIL = ROOT / "memory" / "runs" / "switchboard_trail.jsonl"
DROPS_DIR = ROOT / "memory" / "switchboard" / "drops"
PROVIDERS_CFG = ROOT / "configs" / "providers.yaml"
FLEET_CFG = ROOT / "configs" / "agent_fleet" / "jones.yaml"

TIER_ORDER = ("T0", "T1", "T2", "T3")
TIER_RANK = {t: i for i, t in enumerate(TIER_ORDER)}
TIER_RECEIVE = {
    "T0": frozenset({"T0"}),
    "T1": frozenset({"T0", "T1"}),
    # T2 is the remote/public boundary. It must never inherit access to the
    # numerically lower but more sensitive T0/T1 classes.
    "T2": frozenset({"T2"}),
    # T3 represents the human/L3 authority boundary, not a remote provider.
    "T3": frozenset(TIER_ORDER),
}

# Seat → default platform mapping (router seats)
_SEAT_PLATFORM: dict[str, str] = {
    "local": "ollama",
    "agent": "deepseek",
    "deepseek": "deepseek",
    "grok_tui": "xai",
    "cursor": "cursor",
    "hermes": "hermes",
    "human": "operator",
    "defer": "operator",
}

# Importance weights for routing priority (higher = steer here first)
_IMPORTANCE: dict[str, int] = {
    "operator": 100,
    "cursor": 90,
    "deepseek": 80,
    "xai": 75,
    "ollama": 60,
    "hermes": 50,
    "unknown": 30,
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _trail(event: str, **fields: Any) -> None:
    TRAIL.parent.mkdir(parents=True, exist_ok=True)
    row = {"ts": _now(), "event": event, **fields}
    with TRAIL.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def tier_rank(tier: str) -> int:
    return TIER_RANK.get((tier or "T2").upper(), 2)


def tier_allows(*, holder_tier_max: str, payload_tier: str) -> bool:
    """True when holder may receive payload at payload_tier."""
    holder = (holder_tier_max or "T2").upper()
    payload = (payload_tier or "T2").upper()
    return payload in TIER_RECEIVE.get(holder, TIER_RECEIVE["T2"])


@dataclass
class SeatProfile:
    """Static platform/seat descriptor — config-backed, reusable by all peers."""

    seat_id: str
    platform: str
    kind: str = "seat"
    tier_max: str = "T2"
    group: str = "platform"
    importance: int = 50
    api_key_env: str | None = None
    api_ready: bool = False
    models: list[str] = field(default_factory=list)
    free_local: bool = False
    fleet_roles: list[str] = field(default_factory=list)
    flags: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ProcessPeer:
    """Live process in the mesh — orchestrator child, seat, or harness loop."""

    peer_id: str
    kind: str  # task | seat | harness
    seat: str = "unknown"
    platform: str = "unknown"
    tier_max: str = "T2"
    status: str = "unknown"
    group: str = "live"
    importance: int = 50
    alive: bool | None = None
    phase: str | None = None
    goal: str = ""
    task_id: str | None = None
    pid: int | None = None
    heartbeat_age_s: int | None = None
    api_flags: dict[str, Any] = field(default_factory=dict)
    why: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _load_providers() -> dict[str, Any]:
    if not PROVIDERS_CFG.is_file():
        return {}
    try:
        return yaml.safe_load(PROVIDERS_CFG.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def _load_fleet() -> dict[str, Any]:
    if not FLEET_CFG.is_file():
        return {}
    try:
        return yaml.safe_load(FLEET_CFG.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def _api_ready(env_name: str | None) -> bool:
    if not env_name:
        return True
    import os

    val = os.environ.get(env_name, "")
    return bool(val and str(val).strip())


def build_seat_registry() -> dict[str, SeatProfile]:
    """OO seat catalog: providers + fleet roles + router seats."""
    cfg = _load_providers()
    fleet = _load_fleet()
    providers = cfg.get("providers") or {}

    # fleet role → seats
    role_seats: dict[str, list[str]] = {}
    for role_name, role in (fleet.get("roles") or {}).items():
        for seat in role.get("seats") or []:
            role_seats.setdefault(str(seat), []).append(str(role_name))

    seats: dict[str, SeatProfile] = {}

    for pid, prov in providers.items():
        platform = str(pid)
        tier_max = str(prov.get("tier_max") or "T2")
        env_name = prov.get("api_key_env")
        seats[platform] = SeatProfile(
            seat_id=platform,
            platform=platform,
            kind=str(prov.get("kind") or "openai_compat"),
            tier_max=tier_max,
            group="provider",
            importance=_IMPORTANCE.get(platform, 55),
            api_key_env=str(env_name) if env_name else None,
            api_ready=_api_ready(str(env_name) if env_name else None),
            models=list(prov.get("models") or [])[:6],
            free_local=bool(prov.get("free_local")),
            fleet_roles=role_seats.get(platform, []),
            flags={
                "quota_period": (prov.get("quota") or {}).get("period"),
                "timeout_s": prov.get("timeout_seconds"),
            },
        )

    for seat_name, platform in _SEAT_PLATFORM.items():
        if seat_name in seats:
            continue
        prov = seats.get(platform)
        tier_max = prov.tier_max if prov else ("T1" if seat_name == "local" else "T2")
        seats[seat_name] = SeatProfile(
            seat_id=seat_name,
            platform=platform,
            kind="router_seat",
            tier_max=tier_max,
            group="router",
            importance=_IMPORTANCE.get(platform, _IMPORTANCE["unknown"]),
            api_ready=prov.api_ready if prov else True,
            fleet_roles=role_seats.get(seat_name, []),
        )

    return seats


def _infer_seat_from_task(task: dict[str, Any]) -> str:
    cmd = task.get("cmd") or []
    for i, part in enumerate(cmd):
        if part == "--provider" and i + 1 < len(cmd):
            return str(cmd[i + 1])
        if part == "--seat" and i + 1 < len(cmd):
            return str(cmd[i + 1])
    tag = str(task.get("tag") or "")
    if tag:
        return tag
    return "agent"


def _live_peers() -> list[ProcessPeer]:
    peers: list[ProcessPeer] = []
    seats = build_seat_registry()

    try:
        from mag import orchestrator as orc

        for task in orc.list_tasks_live(limit=80) or []:
            tid = str(task.get("task_id") or task.get("id") or "")
            if not tid:
                continue
            seat = _infer_seat_from_task(task)
            platform = _SEAT_PLATFORM.get(seat, seat)
            prof = seats.get(platform) or seats.get(seat)
            tier_max = prof.tier_max if prof else "T2"
            importance = prof.importance if prof else _IMPORTANCE["unknown"]
            status = str(task.get("status") or "unknown")
            alive = task.get("alive")
            why: list[str] = [f"orchestrator:{status}"]
            if alive is False:
                why.append("heartbeat_stale")
            if status == "running" and alive is not False:
                importance += 20
            peers.append(
                ProcessPeer(
                    peer_id=f"task:{tid}",
                    kind="task",
                    seat=seat,
                    platform=platform,
                    tier_max=tier_max,
                    status=status,
                    group="live_tasks",
                    importance=importance,
                    alive=alive if isinstance(alive, bool) else None,
                    phase=task.get("phase"),
                    goal=str(task.get("goal") or "")[:200],
                    task_id=tid,
                    pid=task.get("pid"),
                    heartbeat_age_s=task.get("heartbeat_age_s"),
                    api_flags={"api_ready": prof.api_ready if prof else None},
                    why=why,
                )
            )
    except Exception as exc:
        peers.append(
            ProcessPeer(
                peer_id="error:orchestrator",
                kind="harness",
                seat="orchestrator",
                platform="harness",
                status="error",
                group="harness",
                importance=10,
                why=[f"probe_failed:{exc}"],
            )
        )

    # Harness presence from router signals (drainer, operator active)
    try:
        from mag.router import gather_signals

        sig = gather_signals()
        if sig.get("drainer"):
            peers.append(
                ProcessPeer(
                    peer_id="harness:drainer",
                    kind="harness",
                    seat="autorun",
                    platform="harness",
                    tier_max="T2",
                    status="active",
                    group="harness",
                    importance=70,
                    why=["MAG_DRAINER=1"],
                    api_flags={"pending_breadcrumbs": sig.get("pending_breadcrumbs")},
                )
            )
        if not sig.get("grok_budget_ok", True):
            peers.append(
                ProcessPeer(
                    peer_id="harness:grok_budget",
                    kind="harness",
                    seat="grok_tui",
                    platform="xai",
                    tier_max="T2",
                    status="throttled",
                    group="harness",
                    importance=20,
                    why=["grok_budget_exhausted"],
                )
            )
    except Exception:
        pass

    # External/desktop seats + seat-guard (unified registry union)
    try:
        from mag.seat_registry import mesh_peers

        for mp in mesh_peers():
            peers.append(
                ProcessPeer(
                    peer_id=str(mp.get("peer_id") or ""),
                    kind=str(mp.get("kind") or "external"),
                    seat=str(mp.get("seat") or "unknown"),
                    platform=str(mp.get("platform") or "unknown"),
                    tier_max=str(mp.get("tier_max") or "T2"),
                    status=str(mp.get("status") or "running"),
                    group=str(mp.get("group") or "external_seats"),
                    importance=int(mp.get("importance") or 70),
                    alive=mp.get("alive"),
                    phase=mp.get("phase"),
                    goal=str(mp.get("goal") or "")[:200],
                    task_id=mp.get("task_id"),
                    pid=mp.get("pid"),
                    heartbeat_age_s=mp.get("heartbeat_age_s"),
                    why=list(mp.get("why") or []),
                )
            )
    except Exception:
        pass

    import os

    if os.environ.get("MAG_OPERATOR_ACTIVE", "").strip().lower() in ("1", "true", "yes"):
        peers.append(
            ProcessPeer(
                peer_id="harness:operator",
                kind="harness",
                seat="human",
                platform="operator",
                tier_max="T1",
                status="active",
                group="harness",
                importance=100,
                why=["MAG_OPERATOR_ACTIVE"],
            )
        )

    return peers


def mesh(*, include_seats: bool = True) -> dict[str, Any]:
    """Full switchboard mesh: static seats + live peers + grouping."""
    seats = build_seat_registry()
    peers = _live_peers()
    groups: dict[str, list[str]] = {}
    for p in peers:
        groups.setdefault(p.group, []).append(p.peer_id)
    if include_seats:
        for sid, prof in seats.items():
            groups.setdefault(prof.group, []).append(f"seat:{sid}")

    orphan = find_orphans(dry=True)
    arena_league: dict[str, Any] = {}
    try:
        from mag.arena_learning import league_snapshot

        league = league_snapshot()
        ranks = league.get("rankings") or []
        arena_league = {
            "n_seats": len(ranks),
            "top": ranks[0] if ranks else None,
            "routing_hint": league.get("routing_hint"),
            "path": "memory/training/arena_league.json",
        }
    except Exception:
        pass
    return {
        "schema": SCHEMA,
        "ts": _now(),
        "seats": {k: v.to_dict() for k, v in seats.items()},
        "peers": [p.to_dict() for p in peers],
        "groups": groups,
        "arena_league": arena_league,
        "summary": {
            "n_seats": len(seats),
            "n_peers": len(peers),
            "n_live_tasks": sum(1 for p in peers if p.kind == "task" and p.status == "running"),
            "n_orphans": len(orphan.get("orphans") or []),
            "arena_seats_ranked": arena_league.get("n_seats", 0),
        },
    }


def peers(*, group: str | None = None, live_only: bool = False) -> list[dict[str, Any]]:
    """List peers sorted by importance (routing priority)."""
    items = _live_peers()
    if group:
        items = [p for p in items if p.group == group]
    if live_only:
        items = [p for p in items if p.kind == "task" and p.status == "running"]
    items.sort(key=lambda p: p.importance, reverse=True)
    return [p.to_dict() for p in items]


def find_orphans(*, dry: bool = True) -> dict[str, Any]:
    """Detect zombie task records and orphan mailboxes — no orphan processes."""
    orphans: list[dict[str, Any]] = []
    tasks: list[dict[str, Any]] = []
    known: set[str] = set()
    try:
        from mag import orchestrator as orc

        # Read task records once.  The old implementation rescanned the full
        # task directory a second time merely to build mailbox membership.
        tasks = orc.list_tasks(limit=100) or []
        for task in tasks:
            tid = str(task.get("task_id") or "")
            status = str(task.get("status") or "")
            pid = task.get("pid")
            if status == "running" and pid and not orc._pid_alive(int(pid)):
                orphans.append({
                    "kind": "zombie_task",
                    "task_id": tid,
                    "pid": pid,
                    "detail": "running record but pid dead",
                })
        task_dir = getattr(orc, "TASK_DIR", None)
        if task_dir is not None and task_dir.is_dir():
            known = {p.stem for p in task_dir.glob("*.json") if p.is_file()}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "orphans": []}

    try:
        from mag.pigeonhole import MAIL_ROOT

        root = MAIL_ROOT
        if root.is_dir():
            for d in root.iterdir():
                if not d.is_dir():
                    continue
                tid = d.name
                if tid.startswith("selftest-"):
                    continue
                if tid not in known:
                    orphans.append({
                        "kind": "orphan_mailbox",
                        "task_id": tid,
                        "detail": "mailbox without task record",
                    })
    except Exception:
        pass

    return {"ok": True, "dry": dry, "orphans": orphans, "n": len(orphans)}


def reap() -> dict[str, Any]:
    """Reap stale orchestrator tasks + report orphans (actionable mesh hygiene)."""
    reaped = {"reaped": 0}
    try:
        from mag import orchestrator as orc

        reaped = orc.reap_stale()
    except Exception as exc:
        reaped = {"ok": False, "error": str(exc), "reaped": 0}

    orphans = find_orphans(dry=False)
    fixed = 0
    if orphans.get("orphans"):
        _trail("reap", reaped=reaped.get("reaped", 0), orphans=orphans["orphans"])
        fixed = len(orphans["orphans"])
    return {
        "ok": True,
        "reaped": int(reaped.get("reaped") or 0),
        "orphans_found": fixed,
        "orphans": orphans.get("orphans") or [],
    }


def _resolve_peer(peer_ref: str) -> ProcessPeer | None:
    ref = (peer_ref or "").strip()
    if not ref:
        return None
    for p in _live_peers():
        if p.peer_id == ref or p.task_id == ref or ref in (p.peer_id, p.seat):
            return p
    if ref.startswith("task:"):
        tid = ref.split(":", 1)[1]
        for p in _live_peers():
            if p.task_id == tid:
                return p
    for p in _live_peers():
        if p.task_id == ref:
            return p
    return None


def steer_drop(
    from_ref: str,
    to_ref: str,
    context: str,
    *,
    tier: str = "T2",
    reason: str = "",
    spooky: bool = False,
    dry: bool = False,
) -> dict[str, Any]:
    """Tier-bounded cross-seat context drop — telepathic steer via pigeonhole.

    spooky=True marks lawful operator-curated share (training label), still tier-filtered.
    """
    context = (context or "").strip()
    if not context:
        return {"ok": False, "error": "empty context"}
    if not to_ref:
        return {"ok": False, "error": "missing to_ref"}

    tier = (tier or "T2").upper()
    if tier not in TIER_ORDER:
        return {"ok": False, "error": f"invalid tier {tier}"}

    target = _resolve_peer(to_ref)
    if target is None and not to_ref.startswith("t"):
        # Allow raw task_id
        target = _resolve_peer(f"task:{to_ref}")
    if target is None:
        # Last resort: steer by task_id string directly
        task_id = to_ref.replace("task:", "")
    else:
        task_id = target.task_id or to_ref.replace("task:", "")

    holder_tier = target.tier_max if target else "T2"
    if not tier_allows(holder_tier_max=holder_tier, payload_tier=tier):
        return {
            "ok": False,
            "error": "tier_blocked",
            "detail": f"target tier_max={holder_tier} cannot receive {tier}",
        }

    drop_id = "drop-" + uuid.uuid4().hex[:10]
    prefix = "[switchboard"
    if spooky:
        prefix += ":spooky"
    steer_text = f"{prefix} tier={tier}"
    if reason:
        steer_text += f" reason={reason[:80]}"
    if from_ref:
        steer_text += f" from={from_ref}"
    steer_text += f"] {context[:1200]}"

    record = {
        "schema": "switchboard_drop.v1",
        "drop_id": drop_id,
        "ts": _now(),
        "from": from_ref,
        "to": to_ref,
        "task_id": task_id,
        "tier": tier,
        "spooky": spooky,
        "reason": reason[:200],
        "context_len": len(context),
        "dry": dry,
    }

    if dry:
        return {"ok": True, "dry": True, "drop": record, "steer_preview": steer_text[:400]}

    try:
        from mag import pigeonhole as ph

        ph.post_steer(str(task_id), steer_text)
    except Exception as exc:
        return {"ok": False, "error": f"pigeonhole: {exc}", "drop": record}

    DROPS_DIR.mkdir(parents=True, exist_ok=True)
    (DROPS_DIR / f"{drop_id}.json").write_text(
        json.dumps({**record, "context": context[:2000]}, indent=2, default=str),
        encoding="utf-8",
    )
    _trail("steer_drop", **{k: record[k] for k in record if k != "dry"})

    try:
        from mag.training_events import emit

        emit(
            "steer_outcome",
            join={"drop_id": drop_id, "task_id": str(task_id)},
            input_data={"from": from_ref, "to": to_ref, "tier": tier, "reason": reason[:120]},
            action={"spooky": spooky, "context_len": len(context)},
            outcome={"delivered": True},
            pattern_tags=["switchboard_drop", f"tier_{tier}"] + (["spooky"] if spooky else []),
            tier_max=tier,
        )
    except Exception:
        pass

    return {"ok": True, "drop": record, "steer_len": len(steer_text)}


def route_intent(goal: str, *, dry: bool = False) -> dict[str, Any]:
    """Conductor + mesh: who to talk to, why, best platform flags."""
    goal = (goal or "").strip()
    if not goal:
        return {"ok": False, "error": "empty goal"}

    try:
        from mag.conductor import conduct

        # route_intent is itself the mesh layer. Re-entering conduct with mesh
        # enabled recursively calls route_intent forever.
        decision = conduct(goal, dry=dry, mesh=False)
    except Exception as exc:
        decision = {"error": str(exc)}

    route = (decision.get("route") or {}) if isinstance(decision, dict) else {}
    seat = str(route.get("seat") or "local")
    platform = _SEAT_PLATFORM.get(seat, seat)
    seats = build_seat_registry()
    prof = seats.get(platform) or seats.get(seat)
    live = peers(live_only=True)

    # Best live peer for this seat/platform
    best_peer = None
    for p in live:
        if p.get("seat") == seat or p.get("platform") == platform:
            best_peer = p
            break

    try:
        from mag.router import gather_signals

        signals = gather_signals()
    except Exception:
        signals = {}

    importance = prof.importance if prof else _IMPORTANCE["unknown"]
    if not prof or not prof.api_ready:
        importance -= 15

    arena_route: dict[str, Any] = {}
    try:
        from mag.arena_learning import league_snapshot, routing_hint

        league = league_snapshot()
        budget = "low" if any(w in goal.lower() for w in ("scut", "canvas", "handoff", "local", "fast")) else "high"
        arena_route = routing_hint(
            task="route",
            budget=budget,
            league=league.get("rankings"),
        )
        rec = str(arena_route.get("recommend") or "")
        if rec and rec != seat and arena_route.get("value_score", 0) >= 0.55:
            seat = rec
            platform = _SEAT_PLATFORM.get(seat, seat)
            prof = seats.get(platform) or seats.get(seat)
            importance = prof.importance if prof else _IMPORTANCE["unknown"]
    except Exception:
        pass

    return {
        "schema": "switchboard_route.v1",
        "ts": _now(),
        "goal": goal[:300],
        "conductor": decision,
        "target": {
            "seat": seat,
            "platform": platform,
            "tier_max": prof.tier_max if prof else "T2",
            "importance": importance,
            "api_ready": prof.api_ready if prof else None,
            "models": (prof.models[:3] if prof else []),
            "fleet_roles": prof.fleet_roles if prof else [],
        },
        "best_live_peer": best_peer,
        "signals": signals,
        "arena_learning": arena_route,
        "dry": dry,
    }


def status() -> dict[str, Any]:
    """Operator glance — mesh summary + top peers + orphan count."""
    m = mesh(include_seats=False)
    top = peers(live_only=True)[:5]
    return {
        "schema": SCHEMA,
        "ts": _now(),
        "summary": m["summary"],
        "top_peers": top,
        "groups": m["groups"],
        "orphans": find_orphans(dry=True),
    }


def format_status_text(s: dict[str, Any]) -> str:
    lines = [
        f"Switchboard ({(s.get('ts') or '')[:19]})",
        f"  seats={s.get('summary', {}).get('n_seats')} "
        f"peers={s.get('summary', {}).get('n_peers')} "
        f"live_tasks={s.get('summary', {}).get('n_live_tasks')} "
        f"orphans={s.get('summary', {}).get('n_orphans')}",
    ]
    for p in s.get("top_peers") or []:
        lines.append(
            f"  · {p.get('peer_id')} seat={p.get('seat')} "
            f"imp={p.get('importance')} status={p.get('status')}"
        )
    return "\n".join(lines)


def self_test() -> dict[str, Any]:
    """Tier gate + dry steer round-trip (no live task required)."""
    ok_tier = tier_allows(holder_tier_max="T1", payload_tier="T2") is False
    ok_tier2 = tier_allows(holder_tier_max="T2", payload_tier="T2") is True
    ok_private = all(
        tier_allows(holder_tier_max="T2", payload_tier=tier) is False
        for tier in ("T0", "T1")
    )
    reg = build_seat_registry()
    m = mesh(include_seats=False)
    drop = steer_drop("conductor", "nonexistent-task", "test", tier="T2", dry=True)
    return {
        "ok": ok_tier and ok_tier2 and ok_private and len(reg) >= 3 and m.get("schema") == SCHEMA and drop.get("ok"),
        "tier_gate": ok_tier and ok_tier2 and ok_private,
        "n_seats": len(reg),
        "mesh_peers": m.get("summary", {}).get("n_peers"),
        "dry_drop": drop.get("ok"),
    }


def main(argv: list[str] | None = None) -> int:
    import sys

    args = list(argv) if argv else sys.argv[1:]
    if not args:
        print("usage: switchboard status|mesh|peers|reap|drop|route|self-test")
        return 2
    cmd = args[0]
    if cmd == "self-test":
        print(json.dumps(self_test(), indent=2, default=str))
        return 0 if self_test()["ok"] else 1
    if cmd == "status":
        s = status()
        print(format_status_text(s))
        return 0
    if cmd == "mesh":
        print(json.dumps(mesh(), indent=2, default=str)[:16000])
        return 0
    if cmd == "peers":
        group = ""
        live = "--live" in args
        for i, a in enumerate(args):
            if a == "--group" and i + 1 < len(args):
                group = args[i + 1]
        print(json.dumps(peers(group=group or None, live_only=live), indent=2, default=str)[:12000])
        return 0
    if cmd == "reap":
        print(json.dumps(reap(), indent=2, default=str))
        return 0
    if cmd == "drop":
        # drop <to> <context...> [--from X] [--tier T2] [--spooky] [--dry]
        rest = args[1:]
        if len(rest) < 2:
            print("usage: drop <to_peer> <context> [--from REF] [--tier T2] [--spooky] [--dry]")
            return 2
        to_ref = rest[0]
        from_ref = "operator"
        tier = "T2"
        spooky = False
        dry = False
        ctx_parts: list[str] = []
        i = 1
        while i < len(rest):
            a = rest[i]
            if a == "--from" and i + 1 < len(rest):
                from_ref = rest[i + 1]
                i += 2
            elif a == "--tier" and i + 1 < len(rest):
                tier = rest[i + 1]
                i += 2
            elif a == "--spooky":
                spooky = True
                i += 1
            elif a == "--dry":
                dry = True
                i += 1
            else:
                ctx_parts.append(a)
                i += 1
        context = " ".join(ctx_parts).strip()
        print(json.dumps(
            steer_drop(from_ref, to_ref, context, tier=tier, spooky=spooky, dry=dry),
            indent=2,
            default=str,
        ))
        return 0
    if cmd == "route":
        goal = " ".join(args[1:]).strip()
        if not goal:
            print("need goal text")
            return 2
        print(json.dumps(route_intent(goal, dry="--dry" in args), indent=2, default=str)[:12000])
        return 0
    print("unknown switchboard command: " + cmd)
    return 2


if __name__ == "__main__":
    import sys

    sys.exit(main())
