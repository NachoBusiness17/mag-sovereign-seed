"""fuel_feed — THE FUEL LINE: real work sources -> the free-lane channel -> fold -> percolate.

The missing wiring (operator, 2026-08-24): the loop only knew queue + cold vertices (both empty),
while the system holds REAL waiting work — the percolator's EXPLORE QUEUE (291 novel signals on
disk) — and a massive free channel (openrouter x18, nvidia, groq) that nothing fed continuously.
"Use these seats instead of looking at them." This is that feed.

  sources()   -> pending work from ALL real sources (explore queue first; queue/cold handled by
                 work_loop). Currently: memory/percolator/explore.jsonl (status=open).
  run(batch)  -> fire each pending signal through the FREE-LANE CHANNEL (ENTROPY ROUTED: hard
                 signals -> strong lanes, easy -> fast lanes, rotated for fairness), fold the
                 answer back (mark explored), percolate it (new signal -> invariant/explore).
                 Start batch=1, ramp as needed (operator: "one agent call and ramp our way up").
  status()    -> how much fuel is waiting + how much has flowed.

Free-first + $0 (the channel only hits free lanes; paid deepseek is NOT in the channel). Honest
down-reporting: a lane that fails reports down, never fabricates. Deduped by canonical.

Schema: fuel_feed.v1 · reuse: percolator (explore queue + percolate_signal), models.providers
CLI: python -m mag.fuel_feed status | run [--batch N]
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:  # noqa: BLE001
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

SCHEMA = "fuel_feed.v1"
EXPLORE_QUEUE = ROOT / "memory" / "percolator" / "explore.jsonl"
ROTATION = ROOT / "memory" / "runs" / "fuel_feed" / "rotation.json"
PROFILE = ROOT / "memory" / "runs" / "fuel_feed" / "lane_profile.jsonl"  # Stage 1: per-lane reliability ledger
BATCHES = ROOT / "memory" / "runs" / "fuel_feed" / "batches.jsonl"      # the CURVE: per-batch telemetry

# The FREE-LANE CHANNEL. ROTATED per call (2026-08-24): fixed free-first order let nvidia
# swallow every ask while the 18 OpenRouter free lanes sat idle (19 req/day). Each call starts
# at the next lane index so over N calls every lane gets a fair first shot — the free lanes
# actually get used.
FREE_LANES: list[tuple[str, str, str | None]] = [
    ("ox", "ox", None),                                            # the frontier teacher (bounded seat)
    ("nvidia", "nvidia", "deepseek-ai/deepseek-v4-flash-0731"),  # verified 3.4s, $0 credits
    ("openrouter-a1", "openrouter", "openrouter/auto"),           # funded account
    ("openrouter-a2", "openrouter", "openrouter/auto"),           # free-tier account (18 lanes)
    ("groq", "groq", None),                                       # live 2026-08-24: gpt-oss-120b, dual-key (GROQ_API_KEY + _2)
    # z_ai2/z_ai3 PULLED FROM ROTATION 2026-08-27 (operator: Pro near 100%, Lite parked at
    # 0% — coding-plan keys STOP burning on dashboards; swarm rides truly-free lanes only).
    # z_ai3 RESTORED 2026-08-27 evening on fresh operator GO: restore gate cleared (metering
    # blackout reconciled $0.14/no dark drain; epoch-1 + eyes receipts both fired). Pinned BY
    # MODEL to glm-4.5-flash — the 4.7-flash pool is congested provider-wide (key-independent
    # 1305s, measured 08-27 morning); 5.3-flash arms work rides rib_chat thinking=low instead.
    # ("z_ai2", "z_ai2", "glm-4.7-flash"),   # FUNDED API key (Pro) — reserve, restore only on operator ruling
    # z_ai3 PULLED AGAIN 2026-08-29: probe = 429 code 1310 "Weekly/Monthly Limit
    # Exhausted, reset 2026-09-02 12:52" (same wall on ZAI_API_KEY_2/3/4 — this is
    # why both accounts' 300K daily claims fail). CONSERVATION until reset: the
    # only live z.ai key (ZAI_API_KEY) is the operator's working lane — fleet
    # hands off. Restore z_ai3 after 09-02 12:52 on operator GO.
    # z_ai3 RELIT 2026-09-04 "Calcifer" (operator GO in-session): ZAI_API_KEY_Lite =
    # GLM Coding Lite V3 YEARLY package key, empirically alive — 50/50 burst +
    # sustained 27.85 rps / 99.89% on glm-5.3-flash tonight (scripts/lite_lane_probe.mjs,
    # lite_lane_sustained.mjs; watch/INTAKE_RACTOR_LEGIONS_20260903.md). Pinned BY MODEL
    # to glm-5.3-flash (billing rows show Lite carries it; 23:00-09:00 SGT night window
    # zero-metered — 32.26M-tok receipt). Tranche discipline: Lite credits 2,000/5h +
    # 10,000/wk; cache meter ~53K tok/credit. Supersedes the 08-26 "opencode-only" fence
    # note for THIS key: 09-04 billing rows + live raw-API probes receipt it.
    ("z_ai3", "z_ai3", "glm-5.3-flash"),   # Lite — RELIT 09-04 (Calcifer); PACE-GUARDED 09-05
    #   (mag/lite_guard.py daily ceiling, law 15): promo verdict 09-05 proved Lite METERED
    #   (10K/wk + 2K/5h real credits — the "zero-metered night window" belief was falsified).
    #   Automatic defaults repointed off Lite same day; explicit calls ride the guard.
    ("cerebras", "cerebras", "gpt-oss-120b"),                    # FAST lane (~3000 tok/s) 2026-08-24
]
# SWARM CACHE LANES SWAPPED TO FUNDED KEYS 2026-08-26: z_ai/z_ai4 were riding the CODING-PLAN
# keys (ZAI_API_KEY/ZAI_API_KEY_2) through the raw API — rate-limited (1305/1302) and a fence
# risk. The funded API keys (ZAI_API_KEY_Pro/Lite, lanes z_ai2/z_ai3) are proven working via
# chat_provider (real content, 97-99.9% cached, $0). Coding-plan keys are opencode-only now.
# together REMOVED 2026-08-24: its free key is deprecated (must pay); a paid lane has no place
# in the $0 channel. Together models still ride the openrouter/auto free lanes (same models,
# free carrier).
# OX (stealth/ox-alpha) WIRED BACK 2026-08-24: it was the 8-lane workhorse before the channel
# rebuild left it out. It rides the bounded ox_seat wrapper (the generic path hangs on its
# heavy reasoning). The frontier teacher is the strongest lane again.
# Z_AI WIRED 2026-08-24: glm-4.7-flash is FREE at all tiers (docs.z.ai pricing) and is the
# CACHE-MINING lane — probe: cached 5->70 on repeat (~92% hit), 30-45 token completions with
# thinking off, real content. The operator's $5 balance is now just a buffer, not a dependency.
# CEREBRAS WIRED 2026-08-24: gpt-oss-120b verified answering (~3000 tok/s — the true fast lane
# while groq's quota recovers). Must ride chat_provider (browser UA defeats Cloudflare 1010);
# raw urllib probes get 1010-blocked and misread as a bad key. DORMANT-GATED 2026-09-26
# (B2-133, below): cerebras re-enters the channel only when providers.yaml flips the flag.

# B2-133 DORMANT GATE (2026-09-26): providers.yaml owns lane liveness (mag/doctor.py:607:
# `dormant: true` is a declared state, never probed) and B2-204 already made a dormant lane
# never pickable at the quota seam (models/quota.py). The hardcoded channel gets the same
# law: a lane whose provider id is declared dormant never enters FREE_LANES. B2-36 set
# cerebras dormant (card-gated 30-day trial, chat 402 no-credit); the same gate catches
# nvidia (dormant per B2-61, 410 EOL). Operator GO flips the flag and the lane returns,
# no code edit. Receipt: watch/inbox/burn_wave_20260926/B2_133_cerebras_purge_20260926.md
from mag.dormant import dormant_ids as _dormant_provider_ids

FREE_LANES = [l for l in FREE_LANES if l[1] not in _dormant_provider_ids()]

# ENTROPY LANE ROUTING (GSTD steal #2, 2026-08-24): route each signal to lanes by its
# difficulty instead of blind round-robin. STRONG lanes (verified reasoning) carry hard,
# high-entropy signals; FAST/cheap lanes carry easy signals and get a fair probe, not the
# hard work they'd waste. Rotation within the class keeps every lane fed.
# Derived lane classes by NAME (2026-08-27): positional indexes broke when funded lanes
# left the rotation — names survive any future reserve/restore shuffle.
_L = {l[0]: l for l in FREE_LANES}
STRONG_LANES = [_L[n] for n in ("ox", "nvidia", "openrouter-a1", "openrouter-a2") if n in _L]
FAST_LANES = [_L[n] for n in ("groq", "cerebras") if n in _L]
# z_ai3 was in FREE_LANES but never in STRONG/FAST — Lite sat idle while Max hung.
CACHE_LANES = [_L[n] for n in ("z_ai3",) if n in _L]
ENTROPY_HARD = 0.5
LOSING_STREAK = 3  # consecutive failures before a lane is probed last, not trusted

# PER-LANE BUDGET (2026-08-24, verified by raw probe): openrouter/auto and nvidia route to
# reasoning models (deepseek-v4-flash-0731) that IGNORE thinking:disabled and eat small
# budgets on hard signals (600 -> empty; moderate 2000 -> content). groq returns content at
# 600. So the strong reasoning lanes carry a real budget; the fast lane stays cheap.
# openrouter-a1/a2 RAISED 600->5000 (2026-08-24): at 2200 they returned "empty content —
# reasoning model consumed the budget" (0-17% ok); at 5000 they return real content (probe:
# 247c answer). Same root cause as OX, simpler fix — they just needed room.
LANE_MAX_TOKENS = {"ox": 5000, "nvidia": 2200, "openrouter-a1": 5000, "openrouter-a2": 5000,
                    "z_ai2": 2000, "z_ai3": 2000}


def _next_start(n: int | None = None) -> int:
    """Round-robin start index for lane rotation (persisted so it survives restarts).
    n = modulus for per-class fairness (strong vs fast)."""
    try:
        i = 0
        if ROTATION.is_file():
            i = int(json.loads(ROTATION.read_text(encoding="utf-8")).get("next", 0))
        n = n or len(FREE_LANES)
        ROTATION.parent.mkdir(parents=True, exist_ok=True)
        ROTATION.write_text(json.dumps({"next": (i + 1) % len(FREE_LANES)}), encoding="utf-8")
        return i % n
    except Exception:  # noqa: BLE001
        return 0


def _signal_entropy(signal: str) -> float:
    """Deterministic 0-1 difficulty key for routing (GSTD #2): length + question/mechanism
    density + novelty markers. High = cold reasoning (strong lanes); low = any lane."""
    t = (signal or "").strip()
    if not t:
        return 0.0
    s = min(0.4, len(t) / 400.0)                    # length -> more to reason over
    low = t.lower()
    q = sum(1 for m in ("how", "why", "what if", "mechanism", "design", "architecture",
                        "tradeoff", "protocol", "invariant", "emergent", "novel")
            if m in low)
    s += min(0.4, q * 0.08)                          # question/mechanism density -> deeper reasoning
    n = sum(1 for m in ("adversarial", "hard", "unproven", "cold", "edge") if m in low)
    s += min(0.2, n * 0.04)                          # novelty/hardness markers
    return round(min(1.0, s), 2)


def _losing_streaks() -> dict[str, int]:
    """Consecutive failure count per lane from the Stage-1 profile (the trickle's truth).
    A lane with LOSING_STREAK+ straight failures is probed last, not trusted first.
    AUTH-CONFIG errors (missing API key / 401 / 403) do NOT count toward the streak
    (2026-08-24): they are a config state that gets fixed ONCE, not a runtime reliability
    signal — a lane whose key was repaired should not be permanently banished."""
    streaks: dict[str, int] = {}
    if PROFILE.is_file():
        try:
            for line in PROFILE.read_text(encoding="utf-8", errors="replace").splitlines():
                if not line.strip():
                    continue
                r = json.loads(line)
                lane = r.get("lane")
                if not lane:
                    continue
                err = (r.get("error") or "").lower()
                if "missing api key" in err or "401" in err or "403" in err:
                    continue  # auth/config error — not a reliability failure
                streaks[lane] = 0 if r.get("ok") else streaks.get(lane, 0) + 1
        except Exception:  # noqa: BLE001
            pass
    return streaks


def _route_lanes(signal: str) -> list[tuple[str, str, str | None]]:
    """ENTROPY LANE ROUTING (GSTD steal #2): order the lanes for THIS signal. Hard signals go
    to the STRONG lanes (rotated for fairness, persisted); easy signals ride the FAST lanes
    first with strong as fallback. Profile-informed: a lane on a losing streak is pushed to
    the back (probed, not trusted) until it shows a pulse."""
    entropy = _signal_entropy(signal)
    primary, fallback = (STRONG_LANES, FAST_LANES) if entropy >= ENTROPY_HARD \
        else (FAST_LANES, STRONG_LANES)
    start = _next_start(len(primary))
    lanes = primary[start:] + primary[:start] + CACHE_LANES + fallback
    streak = _losing_streaks()
    hot = [ln for ln in lanes if streak.get(ln[0], 0) >= LOSING_STREAK]
    if hot:
        lanes = [ln for ln in lanes if ln not in hot] + hot  # probe last, not first
    # CADENCE GATE (2026-08-25, utilization rung 5): lanes still inside their learned overload
    # backoff window are probed LAST, not hammered. Guarded — never breaks a call, only reorders.
    try:
        from mag import lane_cadence as _lc
        _cooled = [ln for ln in lanes if _lc.cooldown(ln[0]) > 0]
        if _cooled:
            lanes = [ln for ln in lanes if ln not in _cooled] + _cooled
    except Exception:  # noqa: BLE001
        pass
    return lanes


# PROMPT = the UNIVERSAL WORK CONTRACT (work_contract.v1, 2026-08-24) — the standing brief every
# seat independently prescribed, plus the fold format (MECHANISM/WHY/TEST). Static-first so the
# provider prefix cache mines the frozen block; only the dynamic signal rides at the end.
try:
    from mag.work_contract import BRIEF as _BRIEF
except Exception:  # noqa: BLE001 — fall back to the inline brief if the module ever breaks
    _BRIEF = ("You are a reasoning engine with no persistent memory: every session starts blank. "
              "Answer in a STRUCTURED TASK ENVELOPE: CONTEXT, ROLE, TASK, CONSTRAINTS, INPUTS, "
              "SUCCESS, OUTPUT. Flag uncertainty; kill your own ideas when they fail. Density "
              "over exhaustiveness; never accept 'done' without evidence.")

PROMPT = (_BRIEF
          + "\n\nGiven the signal, produce: THE MECHANISM (one concrete buildable mechanism), "
            "WHY IT MATTERS (one sentence), and THE TEST (one falsifiable test). Concrete, "
            "grounded, no fluff.\n\nSIGNAL: {signal}")

# QUALITY GATE (2026-08-24, GSTD steal #1 — metacognition self-score + confidence floor):
# only quality-cleared results enter the percolator/chain. Weak answers are recorded but not
# percolated (a fall filed, not pollution). Withhold <0.3, down-weight 0.3-0.7, full >=0.7.
WITHHOLD_FLOOR = 0.3
FULL_FLOOR = 0.7
_REFUSAL_HINTS = ("i cannot", "i can't", "as an ai", "i'm an ai", "i am an ai", "i apologize",
                  "i'm sorry", "cannot assist", "not able to")


def _quality_score(text: str, effect: float = 0.0) -> float:
    """Self-score an answer 0-1 (GSTD metacognition, our frame). Baudrillard-gated
    (PANEL_FOLD 20260904: health bars count EFFECT, never bytes): substance is
    SPECIFICITY (named numbers/paths/quotes — the anti-150-byte-floor), and `effect`
    is the downstream term callers add once consumption is REAL (a consumed row, a
    flipped verdict, a run). Bytes alone never pay."""
    t = (text or "").strip()
    if not t:
        return 0.0
    s = 0.0
    # substance: specificity — concrete tokens (numbers, dotted paths, quoted spans),
    # not raw length. A 400-char vibe scores less than a 120-char receipt.
    specific = len(re.findall(r"\b\d+(?:\.\d+)?\b|[A-Za-z0-9_\-]+\.[a-z]{2,4}\b|\"[^\"]{4,}\"", t))
    s += min(0.4, 0.1 * specific)
    # structure: the asked fields present
    low = t.lower()
    markers = sum(1 for m in ("mechanism", "why it matters", "the test", "test:") if m in low)
    s += min(0.4, markers * 0.13)
    # groundedness: refusal/hedge drops the score
    if any(h in low for h in _REFUSAL_HINTS):
        s = max(0.0, s - 0.4)
    # effect: real consumption (caller-supplied; bytes can never earn this)
    s += max(0.0, min(0.2, effect))
    return round(min(1.0, s), 2)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _read_explore() -> list[dict[str, Any]]:
    if not EXPLORE_QUEUE.is_file():
        return []
    out = []
    try:
        for line in EXPLORE_QUEUE.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.strip():
                try:
                    out.append(json.loads(line))
                except Exception:  # noqa: BLE001
                    pass
    except OSError:
        return []
    return out


def _write_explore(rows: list[dict[str, Any]]) -> None:
    EXPLORE_QUEUE.parent.mkdir(parents=True, exist_ok=True)
    EXPLORE_QUEUE.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + ("\n" if rows else ""),
        encoding="utf-8")


def pending() -> dict[str, Any]:
    """Pending fuel: explore-queue signals still status=open (real waiting work)."""
    rows = _read_explore()
    open_rows = [r for r in rows if str(r.get("status") or "open") == "open"]
    return {"ok": True, "schema": SCHEMA, "open": len(open_rows), "total": len(rows),
            "queue": str(EXPLORE_QUEUE.relative_to(ROOT)).replace("\\", "/"),
            "note": "explore queue = the percolator's novel signals — real work waiting for lanes"}


def clarify() -> dict[str, Any]:
    """CLARIFY, DON'T DELETE (operator 2026-08-24): a signal that recurs across enqueues is
    EMPHASIS, not noise. Group open rows by normalized signal text; for each repeated group keep
    ONE clarified row — tagged with its recurrence count + merged sources/domains so the strong
    seats answer the invariant once, deeply, with the repetition as context — and mark the rest
    `status: merged` (folded in, never deleted). The drain then fires the clarified rows, and
    recurrence becomes priority instead of wasted calls on repeats."""
    rows = _read_explore()
    if not rows:
        return {"ok": True, "schema": SCHEMA, "action": "clarified", "groups": 0,
                "merged": 0, "clarified_kept": 0, "open_before": 0, "open_after": 0,
                "note": "queue empty — nothing to clarify"}

    def _raw_signal(r: dict[str, Any]) -> str:
        """Extract the real signal text: some rows carry a JSON-encoded {\"text\": ...} wrapper."""
        s = str(r.get("signal") or "").strip()
        if s.startswith("{"):
            try:
                d = json.loads(s)
                if isinstance(d, dict) and d.get("text"):
                    return str(d["text"])
            except Exception:  # noqa: BLE001
                pass
        return s

    def norm(s: str) -> str:
        s = s.strip()
        if s.startswith("[RECURS x"):  # strip the marker we add so re-clarify can re-group
            s = s.split("]", 1)[-1].strip()
        return " ".join(s.lower().split())

    open_rows = [r for r in rows if str(r.get("status") or "open") == "open"]
    groups: dict[str, list[dict[str, Any]]] = {}
    for r in open_rows:
        groups.setdefault(norm(_raw_signal(r)), []).append(r)

    merged = 0
    clarified_kept = 0
    for g in groups.values():
        if len(g) < 2:
            continue
        keep = g[0]
        others = g[1:]
        merged_from = [str(o.get("canonical") or "") for o in others]
        sources = sorted({str(o.get("source") or "?") for o in others if o.get("source")})
        domains = sorted({str(o.get("domain") or "?") for o in others if o.get("domain")})
        keep["recurrence"] = len(g)
        keep["merged_from"] = merged_from
        keep["clarified"] = (f"[RECURS x{len(g)}" 
                             + (f" across {len(sources)} sources ({', '.join(sources[:4])})" if sources else "")
                             + (f"; domains: {', '.join(domains[:4])}" if domains else "")
                             + " — this invariant keeps coming up; answer it once, deeply.] "
                             + _raw_signal(keep))
        keep["canonical"] = f"clr-{str(keep.get('canonical') or '')[-12:]}"
        for o in others:
            o["status"] = "merged"
            o["merged_into"] = str(keep.get("canonical") or "")
        merged += len(others)
        clarified_kept += 1
    open_after = sum(1 for r in rows if str(r.get("status") or "open") == "open")
    _write_explore(rows)
    return {"ok": True, "schema": SCHEMA, "action": "clarified",
            "groups": len([g for g in groups.values() if len(g) >= 2]),
            "merged": merged, "clarified_kept": clarified_kept,
            "open_before": len(open_rows), "open_after": open_after,
            "note": "repeats folded into clarified rows (recurrence = priority); nothing deleted"}


def _profile_record(lane: str, ok: bool, ms: float, error: str) -> None:
    """STAGE 1 (slow trickle): every lane attempt records a row to the reliability ledger —
    per-lane personality (latency, success, failure mode) is the definition of done."""
    try:
        PROFILE.parent.mkdir(parents=True, exist_ok=True)
        with PROFILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"lane": lane, "ok": ok, "ms": round(ms, 1),
                                "error": (error or "")[:120], "ts": _now()}, ensure_ascii=False) + "\n")
    except Exception:  # noqa: BLE001
        pass


def profile() -> dict[str, Any]:
    """STAGE 1 gauge: the per-lane reliability profile from real trickle calls."""
    rows = []
    if PROFILE.is_file():
        try:
            rows = [json.loads(l) for l in PROFILE.read_text(encoding="utf-8", errors="replace").splitlines()
                    if l.strip()]
        except Exception:  # noqa: BLE001
            rows = []
    by_lane: dict[str, dict[str, Any]] = {}
    for r in rows:
        lane = r.get("lane", "?")
        d = by_lane.setdefault(lane, {"calls": 0, "ok": 0, "fail": 0, "ms_sum": 0.0,
                                      "ms": None, "errors": []})
        d["calls"] += 1
        d["ok"] += 1 if r.get("ok") else 0
        d["fail"] += 0 if r.get("ok") else 1
        d["ms_sum"] += float(r.get("ms") or 0)
        if r.get("error"):
            d["errors"].append(r["error"][:60])
        d["ms"] = round(d["ms_sum"] / d["calls"], 1) if d["calls"] else None
        d["errors"] = d["errors"][-3:]
    current = {ln[0] for ln in FREE_LANES}  # only live lanes count toward the Stage-1 gate
    return {"ok": True, "schema": SCHEMA, "kind": "profile", "total_calls": len(rows),
            "lanes": by_lane,
            "note": "Stage 1 trickle — per-lane reliability is the definition of done",
            "gate_to_stage2": bool(current) and all(
                (by_lane.get(l) or {}).get("calls", 0) >= 3 for l in current) if current else False}


def _free_channel(signal: str) -> dict[str, Any]:
    """Fire the signal through the FREE-LANE CHANNEL (rotating; the first lane that answers
    wins). Honest: down lanes report down, no fabrication, $0 (no paid lane in the channel).
    Every lane attempt records to the Stage-1 profile ledger (the trickle IS the learning)."""
    from models.providers import reload_providers, chat_provider
    from mag import ox_seat
    reload_providers()
    prompt = PROMPT.format(signal=(signal or "")[:800])
    last_err = "no lane attempted"
    entropy = _signal_entropy(signal)
    for label, provider, model in _route_lanes(signal):
        t0 = datetime.now(timezone.utc)
        try:
            if label == "ox":
                # OX rides its bounded seat (the generic path hangs on its heavy reasoning):
                # big budget + long timeout, one call per signal, mapped to the channel contract.
                r = ox_seat.chat(system="You are a sovereign reasoning agent. Be concrete.",
                                 user=prompt, max_tokens=LANE_MAX_TOKENS.get(label, 5000),
                                 timeout=540, tier="T2")
                # The seat's deliverable is the reasoning stream (content comes back empty,
                # finish_reason=length — it never switches to a final answer in-budget).
                # The reasoning IS the answer; use it, it is the model's actual output.
                text = (r.get("content") or "").strip() or (r.get("reasoning") or "").strip()
            else:
                kw = {"tier": "T2", "max_tokens": LANE_MAX_TOKENS.get(label, 600)}
                if model:
                    kw["model"] = model
                if label.startswith("z_ai"):
                    # glm flash: force thinking OFF (probe 2026-08-24) —
                    # otherwise it intermittently burns the whole budget reasoning (empty
                    # content). With thinking off it's a stable fast cache-mining lane.
                    kw["thinking"] = False
                    try:
                        from mag.lane_cadence import pick_free_glm
                        kw["model"] = pick_free_glm(label)
                    except Exception:  # noqa: BLE001
                        kw["model"] = kw.get("model") or "glm-4.5-flash"
                r = chat_provider(provider, system="You are a sovereign reasoning agent. Be concrete.",
                                  user=prompt, **kw)
                text = (r.get("text") or "").strip()
            ms = (datetime.now(timezone.utc) - t0).total_seconds() * 1000
            if r.get("ok") and text:
                _profile_record(label, True, ms, "")
                return {"ok": True, "lane": label, "provider": provider, "text": text,
                        "entropy": entropy}
            err = str(r.get("error") or "empty answer")[:120]
            _profile_record(label, False, ms, err)
            last_err = f"{label}: {err[:80]}"
        except Exception as e:  # noqa: BLE001
            ms = (datetime.now(timezone.utc) - t0).total_seconds() * 1000
            _profile_record(label, False, ms, str(e))
            last_err = f"{label}: {str(e)[:80]}"
    # BURST (2026-08-28): coding-plan Max/Lite hang on raw API and never reached
    # DeepSeek. One paid flash call after the $0 channel fails.
    try:
        from models.providers import burst_mill
        b = burst_mill(
            "You are a sovereign reasoning agent. Be concrete.",
            prompt,
            max_tokens=2200,
            reason=last_err,
        )
        text = (b.get("text") or "").strip()
        if b.get("ok") and text:
            _profile_record("deepseek-burst", True, 0.0, last_err)
            return {"ok": True, "lane": "deepseek-burst", "provider": "deepseek",
                    "text": text, "entropy": entropy, "burst": True,
                    "burst_reason": last_err}
        _profile_record("deepseek-burst", False, 0.0, str(b.get("error") or "")[:120])
        last_err = f"deepseek-burst: {str(b.get('error') or last_err)[:80]}"
    except Exception as e:  # noqa: BLE001
        last_err = f"deepseek-burst: {str(e)[:80]}"
    # LAW-11 CREDITS-OVER-FAILURE (operator 2026-09-25, canon 87b8cf1750883595): when the $0
    # channel AND the deepseek burst both fail, the demanded signal escalates to the paid nous
    # lane (glm-5.3-prime, 200-verified 09-25) instead of dying. Last resort by design: free
    # lanes, then flash burst, then this. Every attempt records to the same Stage-1 profile
    # ledger, so the spend is a meter, not a leak. Reasoning-model gotcha (09-25 receipt):
    # size max_tokens for the thinking burn or the content comes back empty.
    try:
        nr = chat_provider("nous", system="You are a sovereign reasoning agent. Be concrete.",
                           user=prompt, tier="T2", model="z-ai/glm-5.3-prime", max_tokens=4000)
        ntext = (nr.get("text") or "").strip()
        if nr.get("ok") and ntext:
            _profile_record("nous-rescue", True, 0.0, last_err)
            return {"ok": True, "lane": "nous-rescue", "provider": "nous", "text": ntext,
                    "entropy": entropy, "law11_rescue": True, "rescue_reason": last_err}
        _profile_record("nous-rescue", False, 0.0, str(nr.get("error") or "")[:120])
        last_err = f"nous-rescue: {str(nr.get('error') or last_err)[:80]}"
    except Exception as e:  # noqa: BLE001
        last_err = f"nous-rescue: {str(e)[:80]}"
    return {"ok": False, "lane": "none", "text": "", "entropy": entropy,
            "error": f"all free lanes down/unanswered (last: {last_err})"}


def _patch_explore(patch: dict[str, dict[str, Any]]) -> int:
    """MERGE-SAFE write-back (bug fix 2026-08-24): update rows by canonical in the CURRENT file,
    preserving any changes made since this reader's snapshot — e.g. a concurrent clarify pass.
    The old full-file rewrite clobbered merged/clarified rows when a drain overlapped a clarify."""
    rows = _read_explore()
    n = 0
    for r in rows:
        c = str(r.get("canonical") or "")
        if c in patch:
            r.update(patch[c])
            n += 1
    _write_explore(rows)
    return n


def run(*, batch: int = 1) -> dict[str, Any]:
    """Fire up to `batch` pending signals through the free-lane channel; fold the answers back
    (mark explored) and percolate each answer (new signal -> invariant / explore). Start at 1.
    Write-back is MERGE-SAFE: only the fired rows are patched by canonical, so a concurrent
    clarify never gets clobbered (2026-08-24)."""
    rows = _read_explore()
    open_rows = [r for r in rows if str(r.get("status") or "open") == "open"][:max(1, batch)]
    if not open_rows:
        return {"ok": True, "schema": SCHEMA, "action": "no_fuel", "ts": _now(),
                "fired": 0, "detail": "no open signals in the explore queue — feed is dry"}
    fired = []
    patch: dict[str, dict[str, Any]] = {}
    for row in open_rows:
        signal = str(row.get("signal") or "").strip()
        canonical = str(row.get("canonical") or "")
        if not signal:
            patch[canonical] = {"status": "done"}  # empty signal — close it honestly
            continue
        r = _free_channel(signal)
        patch[canonical] = {"status": "done", "answered_at": _now(),
                            "answer": (r.get("text") or "")[:2000],
                            "lane": r.get("lane", "")}
        # QUALITY GATE: score the answer; only quality-cleared results percolate into the
        # shared reality. Weak answers are recorded (a fall filed), never pollution.
        q = _quality_score(r.get("text") or "")
        patch[canonical]["quality"] = q
        patch[canonical]["quality_gate"] = "pass" if q >= WITHHOLD_FLOOR else "withheld"
        if r.get("ok") and r.get("text") and q >= WITHHOLD_FLOOR:
            try:
                from mag import percolator
                percolator.percolate_signal(r["text"], pattern="fuel_feed", source=f"fuel:{canonical[:12]}",
                                            domain="fuel_feed", emit_event=False)
            except Exception:  # noqa: BLE001
                pass
        # ESCALATION (2026-08-24, the organism steal): a withheld answer with REAL content is not
        # dropped — it ESCALATES cache-aware to the deeper model. Cheap loop first; the paid brain
        # is only called at the judgment boundary (the "spend frontier only at the coldest seams"
        # law). If the escalation clears the gate, it folds back as an improvement; if it fails,
        # it is filed honestly as escalated_weak — never silently dropped, never pollution.
        elif q < WITHHOLD_FLOOR and (r.get("text") or "").strip():
            try:
                from mag import session_maze
                er = session_maze.escalate_cached(signal, max_tokens=1600)
                et = (er.get("text") or "").strip()
                eq = _quality_score(et)
                patch[canonical]["escalated"] = bool(er.get("ok") and et)
                patch[canonical]["escalated_quality"] = eq
                patch[canonical]["escalation_model"] = er.get("model", "")
                if er.get("ok") and et and eq >= WITHHOLD_FLOOR:
                    patch[canonical]["answer"] = et[:2000]
                    patch[canonical]["quality"] = eq
                    patch[canonical]["quality_gate"] = "pass"
                    try:
                        from mag import percolator
                        percolator.percolate_signal(et, pattern="fuel_feed_escalated",
                                                    source=f"fuel:{canonical[:12]}",
                                                    domain="fuel_feed", emit_event=False)
                    except Exception:  # noqa: BLE001
                        pass
                else:
                    patch[canonical]["quality_gate"] = "escalated_weak"
            except Exception:  # noqa: BLE001 — escalation must never break the feed
                patch[canonical]["quality_gate"] = "escalate_error"
        fired.append({"canonical": canonical[:12], "lane": r.get("lane", "none"),
                      "ok": bool(r.get("ok")), "quality": q, "entropy": r.get("entropy"),
                      "gate": patch[canonical]["quality_gate"],
                      "answer_chars": len(r.get("text") or ""),
                      # ANSWER TEXT (2026-08-24, the k3s scribe): the scribe classifies what KIND
                      # of knowledge each batch produced — it needs the answer, not just counts.
                      # Truncated (the ledger stays lean); the full answer lives in explore.jsonl.
                      "answer": (r.get("text") or "")[:1200],
                      "error": (r.get("error") or "")[:120]})
    _patch_explore(patch)
    _record_batch(fired)
    return {"ok": True, "schema": SCHEMA, "action": "fed", "ts": _now(), "fired": len(fired),
            "detail": "fired signals through the free lanes, folded + percolated the answers",
            "results": fired}


def _record_batch(fired: list[dict[str, Any]]) -> None:
    """Persist ONE drain batch to the curve ledger (the learning loop, 2026-08-24): fired, ok-rate,
    quality avg, lane spread, failure modes. The curve is what lets us rightsize the batch upward
    with data — the trickle-to-walk ramp decided by bytes, not vibes."""
    try:
        n = len(fired)
        ok_n = sum(1 for f in fired if f.get("ok"))
        qs = [f["quality"] for f in fired if isinstance(f.get("quality"), (int, float))]
        lanes: dict[str, int] = {}
        modes: dict[str, int] = {}
        for f in fired:
            l = str(f.get("lane") or "?")
            lanes[l] = lanes.get(l, 0) + 1
            err = (f.get("error") or "").lower()
            if f.get("ok"):
                key = "ok"
            elif "quota" in err or "429" in err:
                key = "quota/429"
            elif "empty" in err:
                key = "empty"
            else:
                key = (f.get("error") or "fail")[:24]
            modes[key] = modes.get(key, 0) + 1
        BATCHES.parent.mkdir(parents=True, exist_ok=True)
        with BATCHES.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"ts": _now(), "fired": n, "ok": ok_n,
                                 "ok_rate": round(ok_n / n, 3) if n else 0.0,
                                 "quality_avg": round(sum(qs) / len(qs), 3) if qs else None,
                                 "lanes": lanes, "failure_modes": modes},
                                ensure_ascii=False) + "\n")
    except Exception:  # noqa: BLE001 — telemetry must never break the feed
        pass


def curve(*, window: int = 10) -> dict[str, Any]:
    """THE IMPROVEMENT CURVE (2026-08-24): from the batch ledger — rolling ok-rate, quality avg,
    lane spread, and a data-driven next-batch-size suggestion. Ramp only when ok-rate holds >= 0.9
    across lanes; hold when it doesn't. The trickle -> standing -> walk -> run ramp, by bytes."""
    rows: list[dict[str, Any]] = []
    if BATCHES.is_file():
        for line in BATCHES.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except Exception:  # noqa: BLE001
                    pass
    if not rows:
        return {"ok": True, "schema": SCHEMA, "action": "curve", "batches": 0,
                "note": "no batches recorded yet — run() now persists each batch"}
    recent = rows[-window:]
    n = sum(r.get("fired") or 0 for r in recent)
    ok = sum(r.get("ok") or 0 for r in recent)
    ok_rate = round(ok / n, 3) if n else 0.0
    qs = [r["quality_avg"] for r in recent if r.get("quality_avg") is not None]
    quality_avg = round(sum(qs) / len(qs), 3) if qs else None
    lanes: dict[str, int] = {}
    for r in recent:
        for l, c in (r.get("lanes") or {}).items():
            lanes[l] = lanes.get(l, 0) + int(c)
    last = int(rows[-1].get("fired") or 1)
    suggested = last
    if ok_rate >= 0.9 and len(rows) >= 3:
        suggested = min(64, max(1, last * 2))
    return {"ok": True, "schema": SCHEMA, "action": "curve", "batches": len(rows),
            "window": len(recent), "fired": n, "ok": ok, "ok_rate": ok_rate,
            "quality_avg": quality_avg, "lanes": lanes, "last_batch": last,
            "suggested_batch": suggested,
            "note": ("ramp" if suggested > last else "hold") +
                    " — ramp only when ok-rate holds >=0.9 across lanes (bytes, not vibes)"}


def status() -> dict[str, Any]:
    p = pending()
    return {"ok": True, "schema": SCHEMA, "open": p.get("open"), "total": p.get("total"),
            "lanes": [l[0] for l in FREE_LANES],
            "note": "the fuel feed: explore queue -> free lanes (free-first, $0) -> fold -> percolate"}


def main(argv: list[str] | None = None) -> int:
    import argparse
    p = argparse.ArgumentParser(prog="fuel_feed", description="feed real work through the free lanes")
    p.add_argument("cmd", nargs="?", default="status",
                   choices=["status", "run", "profile", "curve", "clarify"])
    p.add_argument("--batch", type=int, default=1)
    a = p.parse_args(argv)
    if a.cmd == "run":
        print(json.dumps(run(batch=a.batch), indent=2, default=str))
    elif a.cmd == "profile":
        print(json.dumps(profile(), indent=2, default=str))
    elif a.cmd == "curve":
        print(json.dumps(curve(), indent=2, default=str))
    elif a.cmd == "clarify":
        print(json.dumps(clarify(), indent=2, default=str))
    else:
        print(json.dumps(status(), indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
