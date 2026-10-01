"""Unified routing — one classifier, one seat matrix, honest failures.

All entry points (coordinate, dispatch, governor autorun, REST) should call
``route()`` so the same goal always gets the same seat/provider/mode.

Schema: route.v2
"""
from __future__ import annotations

import os
from typing import Any

from mag.coordination import DEPTH_ROUTES, VALID_DEPTHS, _clip

DEPTH_JOB_MAP: dict[str, str] = {
    "scut": "scut",
    "conversation": "default",
    "simple_code": "default",
    "heavy_code": "hard_code",
    "plan": "hard_reason",
    "overview": "hard_reason",
}

_CURSOR_MARKERS = (
    "via cursor",
    "cursor ide",
    "cursor seat",
    "seat cursor",
    "--seat cursor",
    "[cursor]",
    "[composer]",
)
_HERMES_MARKERS = (
    "via hermes",
    "hermes agent",
    "use hermes",
    "with hermes",
    "seat hermes",
    "hermes seat",
    "--seat hermes",
)
_SECRET_MARKERS = ("secret", "password", ".env", "private", "data/raw", "intimate")
_RESEARCH_MARKERS = (
    "research",
    "scrape",
    "according to",
    "from the pack",
    "research pack",
    "what does the site",
    "compare sources",
)

# RIBs are BARE METAL (2026-08-15, operator): frozen deterministic specs compiled by our OWN
# close-to-compiler machinery (rib_struct / rib_bus / invariant lattice / compiler_lang). This is
# deterministic + $0 work — it must route to the cheapest local tier, NEVER up to plan/overview (Grok).
_RIB_MARKERS = (
    "rib",
    "rib_struct",
    "rib_bus",
    "rib_action",
    "bare metal",
    "baremetal",
    "own compiler",
    "compile",
    "compiler",
    "invariant",
    "frozen spec",
    "declare rib",
    "knot invariant",
)

# --- DELEGATION PROFILE (DELEG-POLICY, castle-foundation 2026-08-25) ---
# A named, model-agnostic POLICY layer above routing: controls HOW MUCH the parent agent may do
# locally and WHEN it must hand off / refuse. parent_edit_allow is a function of the PROFILE, never
# of the parent model (DELEG-POLICY-1). The reviewer/verifier role is gated by RISK, not run after
# every worker (DELEG-POLICY-2). This is the operational form of the "golden rule / ok=False
# autopilot" refusal boundary.
_DELEGATION_PROFILES: dict[str, dict[str, Any]] = {
    # minimal coordinator: at most one cheap scope/marker scan, no broad local exploration,
    # stop rather than take over after delegation failure.
    "cost-optimization": {
        "parent_edit_allow": {
            "read": True,
            "scope_scan": True,
            "logic_change": False,
            "concurrency_fix": False,
            "security_hardening": False,
            "new_tests": False,
            "api_change": False,
            "lifecycle_ownership_fix": False,
            "persistence_migration": False,
        },
        "max_local_steps": 1,
        "on_delegation_failure": "stop_and_report",
    },
    # primary orchestrator keeps architecture/task-decomposition/final-acceptance, delegates only
    # bounded work.
    "orchestrator": {
        "parent_edit_allow": {
            "read": True,
            "scope_scan": True,
            "logic_change": True,
            "concurrency_fix": False,
            "security_hardening": False,
            "new_tests": True,
            "api_change": False,
            "lifecycle_ownership_fix": False,
            "persistence_migration": False,
        },
        "max_local_steps": 3,
        "on_delegation_failure": "delegate_then_stop",
    },
    # deep delegation: parent is a thin coordinator, most work handed to workers.
    "deep-delegation": {
        "parent_edit_allow": {
            "read": True,
            "scope_scan": True,
            "logic_change": False,
            "concurrency_fix": False,
            "security_hardening": False,
            "new_tests": False,
            "api_change": False,
            "lifecycle_ownership_fix": False,
            "persistence_migration": False,
        },
        "max_local_steps": 0,
        "on_delegation_failure": "stop_and_report",
    },
}

# Risk markers that GATE the reviewer/verifier role (DELEG-POLICY-2). Reviewer is dispatched ONLY
# when one of these is present, never unconditionally after every worker.
_RISK_MARKERS = (
    "concurrency", "thread", "async", "socket", "websocket", "auth", "login",
    "payment", "billing", "data loss", "data-loss", "persistence", "migrat",
    "security", "encrypt", "secret", "password", ".env", "delete", "archive",
    "move", "rename", "migrate", "reset", "irreversible", "payment",
)

# depth -> default delegation profile (the standing policy rides the same hop as the seat).
_DEPTH_PROFILE: dict[str, str] = {
    "scut": "cost-optimization",
    "conversation": "cost-optimization",
    "simple_code": "cost-optimization",
    "heavy_code": "orchestrator",
    "plan": "orchestrator",
    "overview": "orchestrator",
}


def _delegation_profile(depth: str, goal: str) -> dict[str, Any]:
    """Resolve the delegation profile for a goal. Model-agnostic: depends only on depth + goal."""
    name = _DEPTH_PROFILE.get(depth, "cost-optimization")
    prof = dict(_DELEGATION_PROFILES.get(name, _DELEGATION_PROFILES["cost-optimization"]))
    prof["name"] = name
    prof["reviewer_gated"] = _risk_present(goal)
    return prof


def _risk_present(goal: str) -> bool:
    """True when a risk marker is present -> reviewer/verifier role is gated ON (DELEG-POLICY-2)."""
    g = (goal or "").lower()
    return any(m in g for m in _RISK_MARKERS)


# --- comms_trail consumption wire (Q-009, 2026-09-28) ---
# The mycelium graph carries consumption edges (producer seat -> artifact -> consumer) and
# mag.comms_trail.consumption_signal() reduces them to per-seat {count, weight}. The 09-14
# wiring (gather_signals -> local-janitor branch) only used the BINARY cheap flip. This wire
# finishes the job the consumption_signal() spec states (mag/comms_trail.py:191-199: "The
# router consumes this to trust seats that have a PROVEN consumption record"): the per-seat
# records promote the provider lanes whose seat family has a proven comms round-trip, in
# EVERY branch that picks a provider.
# Seat-name token -> provider lane in configs/providers.yaml. Grounded in the seat titles the
# graph actually carries (verified live 2026-09-28: grok_free, cheap_swarm, aos_grok seat).
# A seat maps to at most one lane: first matching token wins, so provider-name tokens are
# listed BEFORE generic family tokens (a seat like "deepseek_swarm" must map to deepseek,
# not to the generic swarm->ollama alias).
_COMMS_SEAT_LANES: tuple[tuple[str, str], ...] = (
    ("deepseek", "deepseek"),
    ("openrouter", "openrouter"),
    ("groq", "groq"),
    ("nous", "nous"),
    ("z_ai", "z_ai"),
    ("ollama", "ollama"),
    ("grok", "xai"),
    ("cheap", "ollama"),
    ("swarm", "ollama"),
    ("local", "ollama"),
)

# Mirrors the proven floor in mag/comms_trail.py:220 (count > 0 and weight >= 0.5).
_COMMS_PROVEN_WEIGHT_FLOOR = 0.5


def _proven_comms_lanes(cc: Any) -> list[str]:
    """Provider lanes matched from proven comms-consumer seats (deduped, sorted)."""
    if not isinstance(cc, dict):
        return []
    seats = cc.get("seats")
    proven: list[str] = []
    if isinstance(seats, dict) and seats:
        for name, st in seats.items():
            if not isinstance(st, dict):
                continue
            try:
                cnt = int(st.get("count") or 0)
                w = float(st.get("weight") or 0.0)
            except (TypeError, ValueError):
                continue
            if cnt > 0 and w >= _COMMS_PROVEN_WEIGHT_FLOOR:
                proven.append(str(name))
    else:
        proven = [str(s) for s in (cc.get("proven_seats") or [])]
    lanes: set[str] = set()
    for s in proven:
        low = s.lower()
        for token, lane in _COMMS_SEAT_LANES:
            if token in low:
                lanes.add(lane)
                break
    return sorted(lanes)


def _comms_lane_boost(base_prefer: list[str], cc: Any) -> tuple[list[str], list[str]]:
    """Promote provider lanes with a proven comms-consumption record within a branch's
    prefer order. Cost-doctrine guard: the free local lane (ollama) is NEVER displaced;
    when it is present in the list, only lanes after it may reorder. Promoted lanes keep
    their relative base order; non-promoted lanes keep theirs. Returns (new_order,
    lanes_actually_promoted); empty second element means no movement (identity)."""
    base = list(base_prefer or [])
    lanes = [ln for ln in _proven_comms_lanes(cc) if ln in base]
    if not lanes:
        return base, []
    head: list[str] = []
    tail = base
    if "ollama" in base:
        i = base.index("ollama")
        head, tail = base[: i + 1], base[i + 1 :]
        lanes = [ln for ln in lanes if ln != "ollama" and ln in tail]
    if not lanes:
        return base, []
    promoted = [p for p in tail if p in lanes]
    rest = [p for p in tail if p not in lanes]
    new = head + promoted + rest
    if new == base:
        return base, []
    return new, promoted


def gather_signals() -> dict[str, Any]:
    """Runtime probes used for routing (no network unless bridge env set)."""
    out: dict[str, Any] = {
        "drainer": os.environ.get("MAG_DRAINER", "").strip().lower() in ("1", "true", "yes"),
        "pending_breadcrumbs": 0,
        "grok_budget_ok": True,
        "home_reachable": True,
    }
    try:
        from mag.operator_inbox import status as inbox_status

        out["pending_breadcrumbs"] = int(inbox_status().get("pending_n") or 0)
    except Exception:
        pass
    try:
        from mag.lanes import grok_escalations_today, load_lanes

        lanes = load_lanes()
        max_d = int((lanes.get("grok_budget") or {}).get("max_escalations_per_day") or 8)
        used = grok_escalations_today()
        out["grok_escalations_today"] = used
        out["grok_budget_max"] = max_d
        out["grok_budget_ok"] = used < max_d
    except Exception:
        pass
    if os.environ.get("MAG_PUBLIC_URL", "").strip():
        try:
            from watch.cursor_bridge import probe_hq

            out["home_reachable"] = bool(probe_hq().get("reachable"))
        except Exception:
            out["home_reachable"] = False
    # comms_trail \u2014 the shared-private-language confidence signal (grok spec \u2192 cheap tier
    # round-trip). Cheap to read (local file globs, no API). The router uses it to decide how much
    # cheap-tier work to trust: confirmed>0 & pending==0 \u2192 the cheap tier speaks the language
    # (route cheap with confidence); confirmed==0 \u2192 unproven (be conservative); pending-heavy
    # \u2192 round-trips in flight (don't over-commit cheap).
    try:
        from mag.comms_trail import status as ct_status

        ct = ct_status()
        confirmed = int(ct.get("confirmed") or 0)
        pending = int(ct.get("pending") or 0)
        out["comms_trail"] = {
            "surfaces": int(ct.get("surfaces") or 0),
            "confirmed": confirmed,
            "pending": pending,
        }
        if confirmed > 0 and pending == 0:
            out["cheap_tier_confidence"] = "high"
        elif confirmed == 0 and pending == 0:
            out["cheap_tier_confidence"] = "unproven"
        elif confirmed > 0:
            out["cheap_tier_confidence"] = "in_flight"
        else:
            out["cheap_tier_confidence"] = "unproven"
    except Exception:
        out["comms_trail"] = {"surfaces": 0, "confirmed": 0, "pending": 0}
        out["cheap_tier_confidence"] = "unproven"
    # comms_trail CONSUMPTION \u2014 the actual mycelium consumption edges (producer -> artifact ->
    # consumer). Richer than the aggregate confirmed/pending count: it names WHICH seats have a
    # proven consumption record. The router trusts a seat with proven consumption edges for that
    # kind of work (a seat that has actually produced/consumed artifacts in the graph).
    try:
        from mag.comms_trail import consumption_signal

        cs = consumption_signal()
        out["comms_consumption"] = {
            "total_consumption_edges": int(cs.get("total_consumption_edges") or 0),
            "seats": cs.get("seats") or {},
            "proven_seats": cs.get("proven_seats") or [],
        }
    except Exception:
        out["comms_consumption"] = {"total_consumption_edges": 0, "seats": {}, "proven_seats": []}
    return out


def _detect_markers(goal: str) -> dict[str, bool]:
    g = (goal or "").lower()
    return {
        "cursor": any(m in g for m in _CURSOR_MARKERS),
        "hermes": any(m in g for m in _HERMES_MARKERS),
        "secret": any(m in g for m in _SECRET_MARKERS),
        "research": any(m in g for m in _RESEARCH_MARKERS),
        "rib": any(m in g for m in _RIB_MARKERS),
        "priority": any(m in g for m in ("[priority]", "[l2]", "[grok]")),
    }


def classify_depth(goal: str, *, depth: str | None = None) -> dict[str, Any]:
    """Unified depth classifier (replaces parallel keyword lists)."""
    if depth and depth in VALID_DEPTHS:
        route = dict(DEPTH_ROUTES[depth])
        return {
            "ok": True,
            "schema": "depth_class.v1",
            "depth": depth,
            "goal": _clip(goal, 300),
            "forced": True,
            **route,
        }

    markers = _detect_markers(goal)
    g = (goal or "").lower()
    n = len(goal or "")

    if markers["secret"]:
        depth = "scut"
    elif markers["rib"]:
        # RIBs are bare metal — compiled by our own close-to-compiler machinery, deterministic + $0.
        # Never route RIB work up to plan/overview (Grok TUI, frontier $); keep it local L0.
        depth = "scut"
    elif markers["research"]:
        depth = "simple_code"
    elif any(
        k in g
        for k in (
            "big picture",
            "interlink",
            "ecosystem map",
            "how does",
            "relate to",
            "overview",
            "two houses",
            "republic chain",
            "architecture map",
            "full stack",
        )
    ):
        depth = "overview"
    elif any(
        k in g
        for k in (
            "plan ",
            "design ",
            "tradeoff",
            "strategy",
            "roadmap",
            "architecture for",
            "how should we",
            "code planning",
            "critique plan",
            "analyze deeply",
        )
    ):
        depth = "plan"
    # Life / ideas dig — not code. Before scut/simple_code so Bernays ≠ simple_code.
    elif any(
        k in g
        for k in (
            "talk about",
            "talk to you about",
            "want to talk",
            "about life",
            "propaganda",
            "philosophy",
            "berna",
            "edward bernays",
            "who benefits",
            "what do you think about",
            "tell me about",
            "curious about",
            "meaning of",
            "ideas about",
        )
    ) or (
        n >= 20
        and not any(
            k in g
            for k in (
                "implement",
                "refactor",
                "pytest",
                "deploy",
                "pull request",
                "bios",
                "sam settings",
                "fix lint",
            )
        )
        and any(
            k in g
            for k in (
                "life",
                "people",
                "society",
                "culture",
                "history",
                "politics",
                "media",
                "power",
                "freedom",
                "attention",
            )
        )
    ):
        depth = "conversation"
    elif any(
        k in g
        for k in (
            "doctor",
            "health",
            "multi-smoke",
            "status",
            "what was i",
            "brief",
            "bonds",
            "list ",
            "show ",
            "ls ",
            "recall",
            "open loop",
            "biograph",
            "quota",
            "providers",
            "hear me",
            "can you hear",
            "hello",
            "good morning",
            "good night",
            "thank you",
            "thanks",
        )
    ) or (n < 80 and "?" in g) or (n < 36 and any(k in g for k in ("hey", "hi ", "hi,", "yo "))):
        depth = "scut"
    elif any(
        k in g
        for k in (
            "rename",
            "typo",
            "one line",
            "single file",
            "add import",
            "fix lint",
            "small fix",
        )
    ) or (n < 120 and any(k in g for k in ("fix ", "patch ", "tweak "))):
        depth = "simple_code"
    elif any(
        k in g
        for k in (
            "implement",
            "refactor",
            "multi-file",
            "orchestrat",
            "write tests",
            "migrate",
            "build feature",
            "heavy",
            "tool loop",
        )
    ) or n > 350:
        depth = "heavy_code"
    elif any(k in g for k in ("implement", "refactor", "add ", "create ", "update ")):
        depth = "simple_code" if n < 200 else "heavy_code"
    elif any(k in g for k in ("summarize", "translate", "draft", "public", "readme")):
        depth = "simple_code"
    else:
        depth = "simple_code" if n < 180 else "plan"

    route = dict(DEPTH_ROUTES[depth])
    return {
        "ok": True,
        "schema": "depth_class.v1",
        "depth": depth,
        "goal": _clip(goal, 300),
        "forced": False,
        **route,
    }


def _tier_for_depth(depth: str, *, secret: bool) -> str:
    if secret:
        return "T1"
    if depth in ("overview", "plan", "heavy_code"):
        return "T2"
    if depth == "scut":
        return "T2"
    return "T2"


def _match_skills(goal: str, depth: str, job: str) -> list[str]:
    skills: list[str] = []
    try:
        from mag.skills_pack import load_skills_cfg

        cfg = load_skills_cfg()
        job_map = cfg.get("job_to_skills") or {}
        skills.extend(list(job_map.get(job) or job_map.get("default") or []))
    except Exception:
        pass
    try:
        from ijl_core import skill_excerpt_for_goal

        if skill_excerpt_for_goal(goal, max_chars=40).strip():
            skills.append("ijl:matched")
    except Exception:
        pass
    if depth in ("heavy_code", "simple_code") and "patch-verify" not in skills:
        g = (goal or "").lower()
        if any(k in g for k in ("fix", "patch", "refactor", "implement")):
            skills.append("patch-verify")
    return skills


def route(
    goal: str,
    *,
    depth: str | None = None,
    force_seat: str | None = None,
    force_provider: str | None = None,
    signals: dict[str, Any] | None = None,
    delegation_profile: str | None = None,
) -> dict[str, Any]:
    """Single routing decision for a goal.

    ``delegation_profile`` optionally overrides the depth-derived profile (cost-optimization /
    orchestrator / deep-delegation). The resolved profile's ``parent_edit_allow`` is a function of
    the profile, NOT the parent model (DELEG-POLICY-1); ``reviewer_gated`` is risk-driven
    (DELEG-POLICY-2).
    """
    from models.quota import pick_provider, provider_budget

    goal = (goal or "").strip()
    if not goal:
        return {"ok": False, "schema": "route.v2", "error": "empty goal"}

    sig = signals if signals is not None else gather_signals()
    markers = _detect_markers(goal)
    classified = classify_depth(goal, depth=depth)
    d = str(classified.get("depth") or "simple_code")
    job = DEPTH_JOB_MAP.get(d, "default")
    tier = _tier_for_depth(d, secret=markers["secret"])
    why: list[str] = [f"depth={d}"]

    # delegation profile: named policy layer (DELEG-POLICY). Model-agnostic by construction.
    prof = _delegation_profile(d, goal)
    if delegation_profile and delegation_profile in _DELEGATION_PROFILES:
        prof = dict(_DELEGATION_PROFILES[delegation_profile])
        prof["name"] = delegation_profile
        prof["reviewer_gated"] = _risk_present(goal)
        why.append(f"delegation_profile={delegation_profile}")
    else:
        why.append(f"delegation_profile={prof['name']}")
    if prof["reviewer_gated"]:
        why.append("reviewer=risk_gated")

    force_seat = force_seat.strip().lower() if force_seat else None
    force_provider = force_provider.strip().lower() if force_provider else None

    # --- explicit seats (markers win) ---
    if force_seat:
        seat = force_seat
        why.append(f"force_seat={seat}")
    elif markers["hermes"]:
        seat = "hermes"
        why.append("marker=hermes")
    elif markers["cursor"]:
        seat = "cursor"
        why.append("marker=cursor")
    elif d in ("overview", "plan"):
        seat = "grok_tui"
        why.append("planning=pack_only")
    elif d in ("scut", "simple_code"):
        seat = "local"
        why.append("janitor=local")
    elif d == "heavy_code":
        seat = "deepseek"
        why.append("execution=heavy")
    else:
        seat = str(classified.get("seat") or "local")

    mode = str(classified.get("mode") or "dispatch")
    launch = bool(classified.get("launch", True))
    provider: str | None = None
    pick: dict[str, Any] = {"ok": False, "skipped": True}
    rental = False
    executable = False
    ok = True
    error: str | None = None
    hint = str(classified.get("token_hint") or "")

    if force_provider:
        provider = force_provider
        why.append(f"force_provider={provider}")
        if provider == "ollama":
            seat = "local"
        elif provider in ("groq", "openrouter", "deepseek", "deepseek_overmind", "anthropic", "vast"):
            seat = "remote"
        else:
            why.append("force_provider=unknown")

    if force_seat and force_provider:
        if force_seat == "local" and provider != "ollama":
            why.append("force_seat_ignored_for_nonlocal_provider")
        if force_seat == "remote" and provider == "ollama":
            why.append("force_provider_ignored_for_remote_seat")
    if d in ("overview", "plan"):
        if not markers["priority"] and not sig.get("grok_budget_ok", True):
            ok = False
            error = "grok_budget_exhausted"
            hint = "Grok daily budget exhausted — wait or raise lanes.yaml max_escalations_per_day"
            why.append("grok_budget=blocked")
        else:
            launch = False
            mode = "plan"
            executable = False
            hint = classified.get("token_hint") or "File pack for Grok TUI — do not auto-run"
            why.append("launch=false")
        return _route_payload(
            goal, d, job, tier, seat, provider, mode, launch, executable, ok, error, hint,
            why, pick, classified, sig, markers, skills=_match_skills(goal, d, job),
            delegation_profile=prof,
        )

    # --- defer seats ---
    if seat in ("cursor", "hermes", "grok_tui"):
        launch = False
        executable = False
        if seat == "cursor":
            mode = "defer_cursor"
            hint = "Use Cursor IDE or cursor_bridge steer when home is reachable"
        elif seat == "hermes":
            mode = "defer_hermes"
            hint = "Hermes is parked — explicit opt-in only"
        return _route_payload(
            goal, d, job, tier, seat, provider, mode, launch, executable, ok, error, hint,
            why, pick, classified, sig, markers, skills=_match_skills(goal, d, job),
            delegation_profile=prof,
        )

    # --- local janitor ---
    if seat == "local" or (not force_seat and d in ("scut", "simple_code")):
        seat = "local"
        # comms_trail consumption: the shared-private-language confidence signal decides how much
        # cheap-tier work to trust. high \u2192 the cheap tier has proven it speaks grok's language
        # (confirmed round-trips, none pending) \u2192 prefer the cheapest local provider (ollama).
        # unproven/in_flight \u2192 be conservative \u2192 prefer the heavier deepseek tier so a
        # misread spec doesn't silently land wrong.
        ctc = str(sig.get("cheap_tier_confidence") or "unproven")
        # comms_trail CONSUMPTION: a seat with a PROVEN consumption record (actual mycelium
        # consumption edges) is trusted for that kind of work. If the cheap tier (cheap_swarm /
        # ollama) has proven consumption, that reinforces the high-confidence cheap route.
        _cc = sig.get("comms_consumption")
        proven = _cc.get("proven_seats", []) if isinstance(_cc, dict) else []
        cheap_proven = any("cheap" in s or "ollama" in s or "local" in s for s in proven)
        if ctc == "high" or (ctc in ("in_flight", "unproven") and cheap_proven):
            prefer = ["ollama", "deepseek", "deepseek_overmind", "groq", "openrouter"]
            why.append("comms_trail=high\u2192cheap" if ctc == "high" else "comms_consumption=cheap_proven")
        else:
            prefer = ["deepseek", "deepseek_overmind", "ollama", "groq", "openrouter"]
            why.append(f"comms_trail={ctc}\u2192conservative")
        # Q-009 wire: the granular per-seat proven record promotes specific lanes in the
        # tail (the binary flip above stays the tier decision; this only reorders lanes
        # within it, never ahead of ollama).
        prefer, _ct_boost = _comms_lane_boost(prefer, sig.get("comms_consumption"))
        if _ct_boost:
            why.append("comms_lane_boost=" + ",".join(_ct_boost))
        pick = pick_provider(job=job if job != "default" else "scut", tier=tier, prefer=prefer)
        if pick.get("ok"):
            if not force_provider:
                provider = str(pick.get("provider") or "ollama")
            else:
                provider = force_provider
            if provider != "ollama":
                seat = "remote"
                why.append(f"pick={provider}")
            else:
                provider = "ollama"
                why.append("provider=ollama")
        else:
            provider = "ollama"
            why.append("fallback=ollama")
        mode = "dispatch"
        launch = True
        executable = True
        return _route_payload(
            goal, d, job, tier, seat, provider, mode, launch, executable, ok, error, hint,
            why, pick, classified, sig, markers, skills=_match_skills(goal, d, job),
            delegation_profile=prof,
        )

    # --- heavy execution ---
    if d == "heavy_code" or seat == "deepseek":
        vast = provider_budget("vast")
        prefer: list[str] | None = None
        if vast.get("configured") and vast.get("budget_ok"):
            prefer = ["vast", "deepseek", "deepseek_overmind", "anthropic"]
            rental = True
            why.append("rental=vast")
        else:
            prefer = ["deepseek", "deepseek_overmind", "anthropic", "vast"]
        # Q-009 wire: proven comms-consumer lanes get preferential order within the
        # branch's allowed lanes (no lane is added, ollama is absent here by design).
        prefer, _ct_boost = _comms_lane_boost(prefer, sig.get("comms_consumption"))
        if _ct_boost:
            why.append("comms_lane_boost=" + ",".join(_ct_boost))

        pick = pick_provider(job="hard_code", tier=tier, prefer=prefer)
        if pick.get("ok"):
            provider = str(pick.get("provider"))
            seat = "local" if provider == "ollama" else "remote"
            mode = "queue" if sig.get("drainer") else "delegate"
            launch = True
            executable = True
            why.append(f"pick={provider}")
            if sig.get("drainer"):
                why.append("drainer=queue")
        else:
            ok = False
            error = "no_execution_provider"
            launch = False
            executable = False
            provider = "deepseek"
            mode = "delegate"
            hint = (
                pick.get("hint")
                or "Set DEEPSEEK_API_KEY (or vast/openrouter) — heavy work cannot run"
            )
            why.append("pick=failed")
            if markers["cursor"]:
                seat = "cursor"
                ok = True
                error = None
                launch = False
                executable = False
                mode = "defer_cursor"
                hint = "No API execution provider — use Cursor seat on git clone"
                why.append("fallback=cursor_defer")

        return _route_payload(
            goal, d, job, tier, seat, provider, mode, launch, executable, ok, error, hint,
            why, pick, classified, sig, markers, skills=_match_skills(goal, d, job),
            delegation_profile=prof,
            rental=rental,
        )

    # --- remote summarize / default ---
    # Q-009 wire: read the configured routing order, promote proven comms-consumer lanes
    # within it, then hand the boosted order to pick_provider. An empty boosted order
    # (config unread) falls back to prefer=None, which is the exact pre-wire path.
    try:
        from models.providers import load_providers

        _cfgp = load_providers()
        _base_order = list(
            (_cfgp.get("routing") or {}).get(job)
            or (_cfgp.get("defaults") or {}).get("prefer_order")
            or []
        )
    except Exception:
        _base_order = []
    _base_order, _ct_boost = _comms_lane_boost(_base_order, sig.get("comms_consumption"))
    if _ct_boost:
        why.append("comms_lane_boost=" + ",".join(_ct_boost))
    pick = pick_provider(job=job, tier=tier, prefer=_base_order or None)
    if pick.get("ok"):
        provider = str(pick.get("provider"))
        seat = "remote"
        mode = "dispatch"
        launch = True
        executable = True
    else:
        provider = "ollama"
        seat = "local"
        mode = "dispatch"
        launch = True
        executable = True
        why.append("fallback=ollama")

    return _route_payload(
        goal, d, job, tier, seat, provider, mode, launch, executable, ok, error, hint,
        why, pick, classified, sig, markers, skills=_match_skills(goal, d, job),
            delegation_profile=prof,
    )


_HANDOFF_MARKERS = (
    "handoff", "hand off", "continue", "resume", "pick up", "as discussed",
    "as we discussed", "deep-handoff", "carry on", "carry over", "following up",
    "following on", "take over", "where we left off", "the run we started",
)


def _context_plan(
    goal: str, depth: str, job: str, tier: str, mode: str, provider: str | None,
) -> dict[str, Any]:
    """Decide the ASK'S REPRESENTATION: handoff vs fresh, and which model shape to call.

    The router today picks a DESTINATION (tier/seat/provider) but not the ask's
    representation. This fills that gap so we think about WHAT MODEL we're calling and
    WHAT CONTEXT rides in the prompt (the 'spend on the spec, not the tier' doctrine):
      - is_handoff   : does the receiving model need the session MAZE / frozen RIB to
                       CONTINUE (map-is-the-territory), vs a fresh context pack?
      - context_plan : 'handoff_maze' | 'fresh_context_pack' (what to attach).
      - model_shape  : cheap/heavy/reasoning/balanced — choose the model by TASK SHAPE,
                       not the provider's default_model.
      - model_hint   : which actual model to call for that shape.
    """
    g = (goal or "").lower()
    is_handoff = any(m in g for m in _HANDOFF_MARKERS) or mode in ("deep-handoff", "handoff")
    if depth in ("plan", "overview"):
        model_shape = "reasoning"
    elif depth == "heavy_code":
        model_shape = "heavy"
    elif depth in ("scut", "simple_code"):
        model_shape = "cheap"
    else:
        model_shape = "balanced"
    context_plan = "handoff_maze" if is_handoff else "fresh_context_pack"
    hint_map = {
        "cheap": "cheapest flash/edge model of the provider — exec scores 1.00 on all tiers (tier_probe)",
        "balanced": "default balanced model of the provider",
        "heavy": "pro/heavy model of the provider (hard_code)",
        "reasoning": "reasoning-capable model (grok TUI / deepseek pro) — plan/reason, do not auto-run",
    }
    return {
        "is_handoff": is_handoff,
        "context_plan": context_plan,
        "model_shape": model_shape,
        "model_hint": hint_map[model_shape],
    }


def _route_payload(
    goal: str,
    depth: str,
    job: str,
    tier: str,
    seat: str,
    provider: str | None,
    mode: str,
    launch: bool,
    executable: bool,
    ok: bool,
    error: str | None,
    hint: str,
    why: list[str],
    pick: dict[str, Any],
    classified: dict[str, Any],
    signals: dict[str, Any],
    markers: dict[str, bool],
    *,
    skills: list[str] | None = None,
    rental: bool = False,
    delegation_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ctx = _context_plan(goal, depth, job, tier, mode, provider)
    return {
        "ok": ok,
        "schema": "route.v2",
        "goal": _clip(goal, 300),
        "depth": depth,
        "job": job,
        "tier": tier,
        "seat": seat,
        "provider": provider,
        "model_shape": ctx["model_shape"],
        "context_plan": ctx["context_plan"],
        "is_handoff": ctx["is_handoff"],
        "model_hint": ctx["model_hint"],
        "mode": mode,
        "launch": launch,
        "executable": executable,
        "error": error,
        "hint": hint,
        "why": why,
        "pick": pick,
        "classification": classified,
        "signals": signals,
        "markers": markers,
        "skills": skills or [],
        "rental": rental,
        "delegation_profile": delegation_profile or {},
    }


def route_task(goal: str, *, depth: str | None = None) -> dict[str, Any]:
    """Governor/autorun compat — route.v1 shape backed by route.v2."""
    r = route(goal, depth=depth)
    provider = r.get("provider") or "ollama"
    depth_s = str(r.get("depth") or "simple_code")
    mult = {"scut": 1, "simple_code": 2, "heavy_code": 8, "plan": 3, "overview": 2}
    base = max(500, len(goal or "") * 4)
    return {
        "ok": r.get("ok", False),
        "schema": "route.v1",
        "goal": r.get("goal"),
        "depth": depth_s,
        "job": r.get("job"),
        "provider": provider,
        "mode": r.get("mode"),
        "launch": r.get("launch"),
        "rental": r.get("rental", False),
        "classification": r.get("classification"),
        "pick": r.get("pick"),
        "cost_estimate": {
            "tokens_est": base * mult.get(depth_s, 2),
            "depth": depth_s,
            "provider": provider,
        },
        "skills": r.get("skills") or [],
        "executable": r.get("executable"),
        "error": r.get("error"),
        "hint": r.get("hint"),
        "why": r.get("why"),
    }


def route_with_snapshot(
    goal: str,
    *,
    snapshot: dict[str, Any] | None = None,
    depth: str | None = None,
    force_seat: str | None = None,
    force_provider: str | None = None,
) -> dict[str, Any]:
    """Route with session-state awareness.

    When a frozen session snapshot is provided, the router adjusts
    seat/provider selection based on the agent's current execution context:

    - Status 'blocked' or 'escalated' → auto-escalate one tier up
    - Status 'done' → route to wait (no auto-run)
    - Goal keywords matching 'design/architect/refactor' + heavy depth →
      escalate to DeepSeek with frozen RIB
    - Scut/simple tasks → stay local ollama
    - Agent state has pending next_moves → prefer local execution
    """
    # Base routing decision
    result = route(goal, depth=depth, force_seat=force_seat, force_provider=force_provider)

    if snapshot is None:
        return result

    # Extract session context
    session_ctx = snapshot.get("layers", {}).get("session_context", {})
    if not session_ctx:
        # Try summary-level fields
        summary = snapshot.get("summary", {})
        session_ctx = {
            "current_status": summary.get("status"),
            "current_goal": summary.get("goal"),
            "_keywords": summary.get("keywords", []),
        }

    status = (session_ctx.get("current_status") or "").lower()
    keywords = session_ctx.get("_keywords", [])
    agent_state = snapshot.get("layers", {}).get("agent_state", {})
    has_pending = (agent_state.get("next_moves") or []).get("length" if isinstance(agent_state.get("next_moves"), list) else 0) > 0 if agent_state.get("next_moves") else False

    # ── Session-aware adjustments ──
    why_session: list[str] = []

    # Status-based escalation
    if "blocked" in status:
        why_session.append("session_status=blocked→escalate")
        result["tier"] = "T3"
        if result.get("provider") == "ollama":
            result["provider"] = "deepseek"
            result["seat"] = "remote"
            result["mode"] = "queue"
    elif "escalat" in status:
        why_session.append("session_status=escalated→force_remote")
        if result.get("provider") == "ollama":
            result["provider"] = "deepseek"
            result["seat"] = "remote"
    elif "done" in status or "closed" in status:
        why_session.append("session_status=done→wait")
        result["launch"] = False
        result["executable"] = False
        result["mode"] = "wait"

    # Keyword-based escalation (design/architect tasks → DeepSeek)
    heavy_kw = {"design", "architect", "refactor", "implement", "migrate", "orchestrat"}
    if any(kw in heavy_kw for kw in keywords):
        current_depth = result.get("depth", "")
        if current_depth in ("heavy_code", "plan"):
            why_session.append("keywords=heavy_design→deepseek")
            if result.get("provider") == "ollama":
                result["provider"] = "deepseek"
                result["seat"] = "remote"
                result["mode"] = "queue"

    # Pending agent_state next_moves → prefer local execution (don't escalate)
    if has_pending and result.get("provider") != "ollama":
        why_session.append("agent_has_pending→stay_local")
        # Don't override if already explicitly routed

    # Append session-aware reasoning
    if why_session:
        result["why"] = (result.get("why") or []) + why_session
        result["session_aware"] = True

    return result
