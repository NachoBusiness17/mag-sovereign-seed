"""percolator — raw signal in; noise/theater stripped; repeatables compiled to invariants;
novel signal explored + folded. Applied EVERYWHERE (training-signal detection, X-tabs, intake).

Operator (2026-08-11): "raw signal invariant stripped of noise and theater. anything that can be
repeated is compiled into invariants anything novel explored and folded" + "for training signal
detection and false positives do this everywhere" + "put the noise in a noise file".

THE PIPELINE (deterministic, $0 — no LLM, module functions only):
  percolate(text) ->
    split into sentences
    classify each: SIGNAL vs THEATER vs NOISE (lexicon scoring, no hallucination)
    noise/theater sentences -> NOISE FILE (memory/ghost/noise/<domain>.jsonl)
    clean signal -> canonical fingerprint (hash of the signal sentences)
    if that canonical has been seen before  -> REPEAT  -> compile to INVARIANT (fold via fact_bus +
      invariant registry, dedupe by content hash). Recurrence = stable truth worth compiling.
    if it is NOVEL (first time)            -> NOVEL   -> log to the EXPLORE queue (deep research /
      steal / synthesis / frontier assistance) so it gets explored and folded.
  inaccessible / blocked input            -> INTAKE REGISTER (memory/ghost/intake/register.jsonl)
      status 'open', to look into later (inference/steering assistance when deep in training).
  false positives (a detected training signal that is actually noise) -> filtered + counted, so the
      lexicon/registry learns and the FP rate drops. Honesty: a false positive is logged, never
      carried forward as truth.

COUNT LAWS (Z15, 2026-09-29, S15 diagnosis — the top invariant read 232,214 self-reinforcements
= 79.8% of all events; configs/mates.yaml: "the percolator's memorization is an exploit played
by the loop on itself"; receipt watch/inbox/hydrology/Z15_PERCOLATOR_FIX.md):
  1. HALF-LIFE DECAY — count halves every half_life_days without reinforcement (applied at
     increment time + by maintenance(); config configs/percolator.json, default 30 days).
  2. HEAL-MERGE TAKES MAX, NOT SUM — idempotent: healing N times from the same seal never
     inflates a count (SUM re-added the sealed count on every heal event = triple-counting).
  3. SELF-EMISSION CAP — an invariant reinforced by the same source within the same cycle
     (UTC day) counts ONCE per cycle, not once per repetition. The exploit: pro_library.fire
     logs a "[steer] …" behavioral event per fire, operator_inbox percolates every behavioral
     event, so each fire re-incremented the very invariant that told seats to fire it.

Schema: percolator.v1 · deterministic + $0 · deps: stdlib only (config file is JSON, not yaml)
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

SCHEMA = "percolator.v1"
NOISE_DIR = ROOT / "memory" / "ghost" / "noise"
INTAKE_DIR = ROOT / "memory" / "ghost" / "intake"
INVARIANT_REGISTRY = ROOT / "memory" / "percolator" / "invariants.json"
SEALS_DIR = ROOT / "memory" / "seals"
EXPLORE_QUEUE = ROOT / "memory" / "percolator" / "explore.jsonl"

# ── count laws config (Z15, 2026-09-29) ───────────────────────────────────────
# JSON (not yaml) on purpose: this module's contract is stdlib-only. The file is
# OPTIONAL — every key has an in-code default, so a missing/corrupt file degrades
# to the documented defaults, never to a crash.
PERCOLATOR_CFG = ROOT / "configs" / "percolator.json"
_CFG_DEFAULTS: dict[str, Any] = {
    "half_life_days": 30.0,       # law 1: count halves every 30 days without reinforcement
    "cycle": "utc-day",           # law 3 cycle clock: one UTC day = one cycle
    "self_emission_cap": True,    # law 3: same source, same cycle counts once
}
_cfg_cache: dict[str, Any] = {"mtime": None, "data": dict(_CFG_DEFAULTS)}


def _cfg() -> dict[str, Any]:
    """Load count-law config (mtime-cached; defaults on any read/parse failure)."""
    try:
        m = PERCOLATOR_CFG.stat().st_mtime
        if _cfg_cache["mtime"] != m:
            data = json.loads(PERCOLATOR_CFG.read_text(encoding="utf-8"))
            merged = dict(_CFG_DEFAULTS)
            if isinstance(data, dict):
                for k, v in _CFG_DEFAULTS.items():
                    if k in data and data[k] is not None:
                        merged[k] = data[k]
            _cfg_cache.update(mtime=m, data=merged)
        return dict(_cfg_cache["data"])
    except Exception:
        return dict(_CFG_DEFAULTS)

# ── signal lexicon (deterministic scoring, no hallucination) ──────────────────
SIGNAL_HINTS = (
    "system prompt", "you are", "available tools", "guidelines", "tools:",
    "invariant", "architecture", "swarm", "flock", "rib", "procedure", "mechanism",
    "we built", "we made", "how to", "the map precedes", "intended paths", "consensus",
    "agent", "steer", "fold", "verkle", "training signal", "false positive", "noise",
    # moderation-field register (wrongthink invariant map, 2026-09-10): a flag receipt is
    # the platform's sensor firing — refusals/filters/blocks are repeatable field signal.
    "refusal", "content filter", "moderation", "flagged", "shadow cell", "denial",
    "temp block", "reach limit", "unsafe content", "boundary is data",
)
THEATER_HINTS = (
    "thrilled", "excited", "excitedly", "announcement", "breaking", "🚀", "🔥",
    "huge", "massive", "historic", "game-changer", "revolutionary", "unprecedented",
    "amazing", "incredible", "so excited", "to the moon", "check this out",
    "steal_pack", "rib_bus_", "session_id",
)
NOISE_HINTS = (
    "reposted", "retweet", "thread", "follow me", "follow @", "like and share",
    "subscribed", "verified", "sponsored", "advertisement", "sign up", "subscribe",
    "giveaway", "win a", "click the link", "dm me", "replies", "reply to",
)
MIN_SIGNAL_LEN = 3  # a 'sentence' shorter than this is not signal

_SENT_RE = re.compile(r"[^.!?\n]+[.!?]?")
_TOKEN_RE = re.compile(r"[a-z0-9_]+")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_ts(ts: Any) -> datetime | None:
    """Parse an ISO timestamp from the registry (naive treated as UTC; bad -> None)."""
    if not isinstance(ts, str) or not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _cycle_key(now: datetime | None = None) -> str:
    """Law 3 cycle clock: one UTC day = one cycle (config 'cycle': 'utc-day')."""
    return (now or datetime.now(timezone.utc)).date().isoformat()


def _decay_count(count: int, elapsed_days: float, *, half_life_days: float | None = None) -> int:
    """Law 1 (Z15, 2026-09-29): count halves every half_life_days without reinforcement.

    Elapsed time is quantized to WHOLE cycles (UTC days — the law's clock, law 3): decay
    lands per-cycle, so two observations minutes apart decay nothing and two landed a day
    apart decay exactly one day's worth. floor at 1 — an observed invariant never decays to
    0 by time alone (only the false-positive path removes truth claims).
    Pure function; tests hit this directly.
    """
    if half_life_days is None:
        half_life_days = float(_cfg()["half_life_days"])
    whole_cycles = float(int(elapsed_days))  # sub-cycle remainder never decays
    if whole_cycles <= 0 or half_life_days <= 0:
        return int(count)
    return max(1, int(count * (0.5 ** (whole_cycles / half_life_days))))


def _canonical_hex(signal_sentences: list[str]) -> str:
    norm = " ".join(s.strip().lower() for s in signal_sentences if s.strip())
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()[:16] if norm else ""


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENT_RE.findall(text or "") if s.strip()]


def _classify(sentence: str) -> dict[str, Any]:
    low = sentence.lower()
    toks = set(_TOKEN_RE.findall(low))
    signal = sum(1 for h in SIGNAL_HINTS if h in low)
    theater = sum(1 for h in THEATER_HINTS if h in low)
    noise = sum(1 for h in NOISE_HINTS if h in low)
    kind = "signal"
    if noise > 0 and noise >= signal:
        kind = "noise"
    elif theater > 0 and theater >= signal:
        kind = "theater"
    return {"sentence": sentence, "signal": signal, "theater": theater,
            "noise": noise, "kind": kind}


def partition(text: str, *, source: str = "") -> dict[str, Any]:
    """Split raw text into signal / theater / noise sentence classes. Deterministic + $0."""
    signal_s, theater_s, noise_s = [], [], []
    for s in _sentences(text):
        c = _classify(s)
        if len(_TOKEN_RE.findall(c["sentence"].lower())) < MIN_SIGNAL_LEN:
            noise_s.append(c)
            continue
        {"signal": signal_s, "theater": theater_s, "noise": noise_s}[c["kind"]].append(c)
    return {"source": source, "signal": signal_s, "theater": theater_s, "noise": noise_s,
            "n_signal": len(signal_s), "n_theater": len(theater_s), "n_noise": len(noise_s)}


def _append_jsonl(path: Path, entry: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _read_jsonl(path: Path, tail: int = 200) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    out = []
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[-tail:]:
            if line.strip():
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return []
    return out


def _newest_seal_registry() -> Path | None:
    """Newest seal snapshot of the invariant registry, or None (seal dir names are UTC-sortable)."""
    try:
        cands = sorted(SEALS_DIR.glob("*/memory/percolator/invariants.json"))
        return cands[-1] if cands else None
    except OSError:
        return None


def _load_registry() -> dict[str, Any]:
    reg = None
    try:
        if INVARIANT_REGISTRY.is_file():
            reg = json.loads(INVARIANT_REGISTRY.read_text(encoding="utf-8"))
    except Exception:
        reg = None
    seal_path = _newest_seal_registry()
    if seal_path is not None:
        try:
            seal = json.loads(seal_path.read_text(encoding="utf-8"))
        except Exception:
            seal = None
        if isinstance(seal, dict):
            seal_gens = seal.get("invariants") or {}
            live_gens = (reg.get("invariants") or {}) if isinstance(reg, dict) else {}
            # GAP-2 (2026-09-06, seat sealcheck; Astra gap v2 ANSWER.md "recovery presented as
            # conservation"): the heal trigger is a PER-GENERATION ID DIFF against the newest
            # seal — ANY sealed generation missing from live heals. The old >50%-by-count gate
            # could not detect partial loss: deleting ONE sealed generation left a silently
            # "healthy" load. The count gate is kept only as a redundant fast-path pre-check
            # (the ID diff subsumes it); it is never the sole trigger.
            missing = [k for k in seal_gens if k not in live_gens]
            shrank = len(live_gens) * 2 < len(seal_gens)
            if reg is None or missing or shrank:
                try:  # AUTO-HEAL (registry-wipe amnesia 2026-09-06 + partial loss 2026-09-06):
                    # merge newest seal — never start empty, never silently stay partial.
                    merged = dict(seal_gens)
                    if INVARIANT_REGISTRY.is_file():
                        try:
                            live = json.loads(INVARIANT_REGISTRY.read_text(encoding="utf-8"))
                            for k, v in (live.get("invariants") or {}).items():
                                if k in merged:
                                    # Z15 (2026-09-29, S15 diagnosis "heal-merge SUMS counts
                                    # (triple-counting)"): shared count merges take MAX, not SUM.
                                    # MAX is IDEMPOTENT — healing N times from the same seal
                                    # yields the same count every time; SUM re-added the sealed
                                    # count on every heal event (heal.log 2026-09-06..09-26:
                                    # repeated 57/72/109/216-gen heals riding the same seal),
                                    # which is one of the two pumps behind the 232,214 top count.
                                    merged[k]["count"] = max(merged[k].get("count", 0),
                                                              v.get("count", 0))
                                    if (v.get("last_seen") or "") > (merged[k].get("last_seen") or ""):
                                        # carry the cap ledger (law 3) from the fresher side
                                        merged[k]["last_seen"] = v.get("last_seen")
                                        merged[k]["decay_as_of"] = v.get("decay_as_of")
                                        if isinstance(v.get("cycle_hits"), dict):
                                            merged[k]["cycle_hits"] = v.get("cycle_hits")
                                    else:
                                        merged[k]["last_seen"] = max(merged[k].get("last_seen") or "",
                                                                     v.get("last_seen") or "")
                                else:
                                    merged[k] = v
                            seal["false_positives"] = max(seal.get("false_positives", 0),
                                                          live.get("false_positives", 0))
                        except Exception:
                            pass
                    reg = {"invariants": merged, "false_positives": seal.get("false_positives", 0)}
                    _append_jsonl(INVARIANT_REGISTRY.parent / "heal.log",
                                  {"ts": _now(),
                                   "heal": f"auto-healed {len(merged)} generations from {seal_path.parents[2]}"})
                except Exception:
                    reg = None
    if reg is None:
        reg = {"invariants": {}, "false_positives": 0}
    reg.setdefault("invariants", {})
    reg.setdefault("false_positives", 0)
    return reg


def _save_registry(reg: dict[str, Any]) -> None:
    INVARIANT_REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    tmp = INVARIANT_REGISTRY.with_name(f"{INVARIANT_REGISTRY.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(reg, ensure_ascii=False, indent=2), encoding="utf-8")
    try:  # LAW-065 DEMO (2026-09-07, seat gatekeep): receipt the destructive replace.
        # Warn-only era — the receipt is appended, the save is never blocked. Sole demo
        # call site; fleet-wide requirement is operator law, not this build's call.
        from mag.destructive_receipt import record as _receipt
        _receipt(str(INVARIANT_REGISTRY), actor="percolator",
                 reason="atomic registry save (temp+os.replace) — LAW-065 demo call site")
    except Exception:
        pass  # the instrument must never break the writer
    os.replace(tmp, INVARIANT_REGISTRY)  # atomic: empty-file-from-crash is now impossible


def append_noise(items: list[dict[str, Any]], *, domain: str = "general") -> dict[str, Any]:
    """Write the stripped noise/theater to a per-domain noise file (jsonl)."""
    path = NOISE_DIR / f"{domain}.jsonl"
    for it in items:
        _append_jsonl(path, {"ts": _now(), "kind": it["kind"], "sentence": it["sentence"]})
    return {"ok": True, "schema": SCHEMA, "path": str(path.relative_to(ROOT)).replace("\\", "/"),
            "n": len(items)}


def noise_log(domain: str = "general", *, tail: int = 200) -> dict[str, Any]:
    path = NOISE_DIR / f"{domain}.jsonl"
    rows = _read_jsonl(path, tail)
    return {"ok": True, "schema": SCHEMA, "domain": domain, "n": len(rows), "rows": rows}


def intake_register(target: str, *, reason_blocked: str, why_useful: str,
                    source: str = "x-tabs", domain: str = "general") -> dict[str, Any]:
    """When input is INACCESSIBLE, log it to the intake register for later (inference/steering)."""
    rec = {"id": hashlib.sha256(f"{target}\x1f{_now()}".encode("utf-8")).hexdigest()[:16],
           "ts": _now(), "target": target, "source": source, "domain": domain,
           "reason_blocked": reason_blocked, "why_useful": why_useful, "status": "open"}
    _append_jsonl(INTAKE_DIR / "register.jsonl", rec)
    return {"ok": True, "schema": SCHEMA, "intake": rec,
            "path": str((INTAKE_DIR / "register.jsonl").relative_to(ROOT)).replace("\\", "/")}


def open_intake(*, tail: int = 200) -> dict[str, Any]:
    rows = [r for r in _read_jsonl(INTAKE_DIR / "register.jsonl", tail) if r.get("status") == "open"]
    return {"ok": True, "schema": SCHEMA, "n_open": len(rows), "rows": rows}


def false_positive(signal_sentence: str, *, reason: str = "detected signal is actually noise",
                   domain: str = "general") -> dict[str, Any]:
    """Filter a FALSE POSITIVE training signal: log it (never carried as truth) + count it."""
    reg = _load_registry()
    reg["false_positives"] = reg.get("false_positives", 0) + 1
    _save_registry(reg)
    _append_jsonl(NOISE_DIR / f"{domain}.fp.jsonl",
                  {"ts": _now(), "sentence": signal_sentence, "reason": reason})
    return {"ok": True, "schema": SCHEMA, "false_positives_total": reg["false_positives"],
            "path": str((NOISE_DIR / f"{domain}.fp.jsonl").relative_to(ROOT)).replace("\\", "/")}


def _compile_invariant(signal_sentences: list[str], canonical: str, *, domain: str,
                       source: str = "") -> dict[str, Any]:
    reg = _load_registry()
    now_dt = datetime.now(timezone.utc)
    now = now_dt.isoformat().replace("+00:00", "Z")
    cycle = _cycle_key(now_dt)
    src = (source or "")[:60]
    inv = reg["invariants"].get(canonical)
    if inv:
        hits = inv.get("cycle_hits") if isinstance(inv.get("cycle_hits"), dict) else {}
        capped = bool(_cfg()["self_emission_cap"]) and hits.get(src) == cycle
        if capped:
            # law 3 (Z15, 2026-09-29): same source, same cycle = ONE count per cycle, not one
            # per repetition. The observation still refreshes last_seen/decay_as_of (the
            # invariant is demonstrably still alive — decay measures ABSENCE), it just cannot
            # pump its own count inside a single cycle.
            pass
        else:
            # law 1 (Z15): decay the stored count over the interval since the last observation
            # baseline (decay_as_of, falling back to last_seen for pre-Z15 rows), THEN +1 for
            # this reinforcement. Long absence floors at 1 then re-counts from there.
            baseline = _parse_ts(inv.get("decay_as_of")) or _parse_ts(inv.get("last_seen"))
            if baseline is not None:
                elapsed_days = (now_dt - baseline).total_seconds() / 86400.0
                inv["count"] = _decay_count(int(inv.get("count", 1)), elapsed_days) + 1
            else:
                inv["count"] = int(inv.get("count", 0)) + 1
        inv["last_seen"] = now
        inv["decay_as_of"] = now
        # per-source cycle ledger, pruned to the current cycle (bounded: one entry per source
        # that hit THIS cycle — an A/B/A alternation within a day still counts each source once)
        inv["cycle_hits"] = {s: c for s, c in hits.items() if c == cycle}
        inv["cycle_hits"][src] = cycle
        _save_registry(reg)
        return {"status": "repeat", "invariant": inv["text"], "count": inv["count"],
                "canonical": canonical, "compiled": True, "capped": capped}
    text = " ".join(s.strip() for s in signal_sentences if s.strip())
    reg["invariants"][canonical] = {"text": text, "count": 1, "first_seen": now,
                                    "domain": domain, "last_seen": now, "decay_as_of": now,
                                    "cycle_hits": {src: cycle}}
    _save_registry(reg)
    try:
        from mag import fact_bus
        # fold=False (2026-08-16, sacred-cow fix): a percolator SIGNAL does not need a full
        # verkle session-knot append (append_verkle_knot -> _rewrite_chain uses
        # incremental O(n log n) prefix roots over the whole chain).
        # The fact still lands in the fact STORE + the invariant registry (real data); only the
        # expensive session-knot verkle rewrite is skipped. The spine (verkle_knot) is untouched.
        fb = fact_bus.publish_fact(text[:400], who="percolator", what="compiled_invariant",
                                   when=_now(), domain=domain, fold=False)
    except Exception:
        fb = {}
    return {"status": "novel", "invariant": text, "count": 1, "canonical": canonical,
            "compiled": True, "fact_bus": fb}


def percolate(text: str, *, source: str = "", domain: str = "general",
              fold: bool = True) -> dict[str, Any]:
    """The full percolator. Raw signal -> noise file + invariants (repeat) / explore (novel)."""
    p = partition(text, source=source)
    # 1) strip noise + theater to the noise file
    stripped = p["theater"] + p["noise"]
    noise_res = append_noise(stripped, domain=domain) if stripped else {"ok": True, "n": 0}
    # 2) the clean signal
    signal_sentences = [s["sentence"] for s in p["signal"]]
    canonical = _canonical_hex(signal_sentences)
    if not signal_sentences:
        return {"ok": True, "schema": SCHEMA, "source": source, "verdict": "no_signal",
                "noise": noise_res, "n_signal": 0, "n_stripped": len(stripped)}
    # 3) repeat (compile to invariant) vs novel (explore + fold)
    res = _compile_invariant(signal_sentences, canonical, domain=domain, source=source)
    if res["status"] == "novel":
        _append_jsonl(EXPLORE_QUEUE, {"ts": _now(), "source": source, "domain": domain,
                                      "signal": res["invariant"][:600], "canonical": canonical,
                                      "status": "open"})
    return {"ok": True, "schema": SCHEMA, "source": source, "domain": domain,
            "verdict": res["status"], "n_signal": len(signal_sentences),
            "n_stripped": len(stripped), "canonical": canonical, "signal": res["invariant"],
            "count": res["count"], "capped": res.get("capped", False), "noise": noise_res,
            "explore": res["status"] == "novel",
            "explore_queue": str(EXPLORE_QUEUE.relative_to(ROOT)).replace("\\", "/")}


def percolate_signal(text: str, *, pattern: str = "route_decision", source: str = "",
                     domain: str = "general", emit_event: bool = True) -> dict[str, Any]:
    """APPLY THE PERCOLATOR EVERYWHERE (training-signal detection + false positives).

    Drop-in for any loop that ingests free-text signal (operator messages, behavioral signals,
    research findings). It: (1) strips noise/theater to the noise file, (2) filters false
    positives (a detected signal that is actually noise -> noise .fp file + counted, NEVER carried
    as truth), (3) compiles repeatable signal into an invariant, (4) queues novel signal for
    exploration, and (5) optionally emits a training event (mag.training_events.emit) so the
    signal is captured in the training feed. Deterministic + $0, safe to call from any loop.
    """
    p = percolate(text, source=source or pattern, domain=domain)
    verdict = p.get("verdict", "no_signal")
    fp = False
    if verdict == "no_signal" and text and len(text.strip()) >= MIN_SIGNAL_LEN:
        # text with no detected signal in a signal-bearing path = likely false positive
        fp_res = false_positive(text[:200], reason="no_signal_in_signal_path", domain=domain)
        fp = True
        p["false_positive"] = fp_res
    evt = {}
    if emit_event:
        try:
            from mag import training_events
            evt = training_events.emit(
                pattern if pattern in training_events.VALID_PATTERNS else "route_decision",
                input_data={"source": source or pattern, "text": text[:500]},
                outcome={"verdict": verdict, "stripped": p.get("n_stripped", 0),
                         "signal": p.get("n_signal", 0), "false_positive": fp},
                pattern_tags=["percolator"])
        except Exception as e:
            evt = {"error": str(e)[:120]}
    p["false_positive"] = fp
    p["training_event"] = evt
    return p


def _top_rows(invs: dict[str, Any], n: int = 5) -> list[dict[str, Any]]:
    return [{"canonical": k, "count": v.get("count", 0), "text": (v.get("text") or "")[:60]}
            for k, v in sorted(invs.items(), key=lambda kv: -int(kv[1].get("count", 0)))[:n]]


def maintenance(*, dry: bool = True) -> dict[str, Any]:
    """Z15 backfill (2026-09-29): enforce the three count laws on STORED counts.

    Laws 1+3 apply prospectively in _compile_invariant; this pass repairs the historical
    damage already sitting in invariants.json (the 232,214 exploit count among them):

      cap   count <- min(count, distinct cycles observed): without per-hit source history
            the strongest PROVABLE bound on a cycle-deduped count is the number of UTC days
            in [first_seen, last_seen] (inclusive). Conservative: an invariant legitimately
            reinforced by several DISTINCT sources in one day can exceed it — accepted, the
            alternative is keeping a provably self-inflated number.
      decay count <- half-life decay from the observation baseline (decay_as_of, falling back
            to last_seen) to now; floor 1. decay_as_of is stamped on apply so a rerun decays
            only the fresh interval, never compounds.

    dry=True reports only (no disk write, deliberately NOT via _load_registry so a pending
    auto-heal can never surprise-write during a dry run). dry=False backs up the registry
    next to it (invariants.json.bak-z15-<date>) before the atomic replace.
    """
    try:
        original_raw = INVARIANT_REGISTRY.read_text(encoding="utf-8")
        reg = json.loads(original_raw)
    except Exception as e:
        return {"ok": False, "error": f"cannot read registry: {e}", "dry": dry}
    if not isinstance(reg, dict):
        reg = {"invariants": {}}
    invs = reg.setdefault("invariants", {})
    now_dt = datetime.now(timezone.utc)
    now = now_dt.isoformat().replace("+00:00", "Z")
    cap_on = bool(_cfg()["self_emission_cap"])
    top_before = _top_rows(invs)
    changed = 0
    total_before = sum(int(v.get("count", 0)) for v in invs.values())
    for inv in invs.values():
        old = int(inv.get("count", 1))
        count = old
        fs, ls = _parse_ts(inv.get("first_seen")), _parse_ts(inv.get("last_seen"))
        if cap_on and fs is not None and ls is not None:
            observed_days = max(1, (ls.date() - fs.date()).days + 1)
            count = min(count, observed_days)
        baseline = _parse_ts(inv.get("decay_as_of")) or ls
        if baseline is not None:
            count = _decay_count(count, (now_dt - baseline).total_seconds() / 86400.0)
        count = max(1, count)
        if count != old:
            inv["count"] = count
            changed += 1
        inv["decay_as_of"] = now
    backup = None
    if not dry:
        backup = INVARIANT_REGISTRY.with_name(f"{INVARIANT_REGISTRY.name}.bak-z15-{now_dt:%Y%m%d}")
        try:
            backup.write_text(original_raw, encoding="utf-8")  # PRE-EDIT bytes, not the result
        except Exception:
            backup = None  # the atomic save still proceeds; the pre-edit file stays on disk
        _save_registry(reg)
    return {"ok": True, "dry": dry, "n_invariants": len(invs), "n_changed": changed,
            "total_count_before": total_before,
            "total_count_after": sum(int(v.get("count", 0)) for v in invs.values()),
            "top_before": top_before, "top_after": _top_rows(invs), "backup": backup,
            "half_life_days": _cfg()["half_life_days"], "ts": now}


def status() -> dict[str, Any]:
    reg = _load_registry()
    return {"ok": True, "schema": SCHEMA,
            "contract": "percolate(text) -> noise file + invariant(repeat) / explore(novel); "
                        "percolate_signal(text) for training-signal detection + false positives",
            "n_invariants": len(reg.get("invariants") or {}),
            "false_positives": reg.get("false_positives", 0),
            "count_laws": {"half_life_days": _cfg()["half_life_days"],
                           "cycle": _cfg()["cycle"],
                           "self_emission_cap": _cfg()["self_emission_cap"]},
            "noise_dir": str(NOISE_DIR.relative_to(ROOT)).replace("\\", "/"),
            "intake": str((INTAKE_DIR / "register.jsonl").relative_to(ROOT)).replace("\\", "/"),
            "cost": "deterministic + $0 (stdlib only)"}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="percolator")
    ap.add_argument("text", nargs="?", help="raw signal to percolate")
    ap.add_argument("--source", default="manual")
    ap.add_argument("--domain", default="general")
    ap.add_argument("--noise-log", action="store_true")
    ap.add_argument("--intake", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--maintenance", action="store_true",
                    help="Z15 backfill: self-emission cap + half-life decay on stored counts")
    ap.add_argument("--dry", action="store_true", help="with --maintenance: report only, no write")
    ap.add_argument("--apply", action="store_true", help="with --maintenance: write the repair")
    a = ap.parse_args()
    if a.status:
        print(json.dumps(status(), indent=2, default=str))
    elif a.maintenance:
        if a.dry and a.apply:
            ap.error("--dry and --apply are mutually exclusive")
        print(json.dumps(maintenance(dry=not a.apply), indent=2, default=str))
    elif a.noise_log:
        print(json.dumps(noise_log(a.domain), indent=2, default=str))
    elif a.intake:
        print(json.dumps(open_intake(), indent=2, default=str))
    elif a.text:
        print(json.dumps(percolate(a.text, source=a.source, domain=a.domain), indent=2, default=str))
