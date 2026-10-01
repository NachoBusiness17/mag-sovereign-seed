"""cache_identity — W3 instrument: the cache-identity probe (falsifier F-W2).

Card: watch/WORLDLINE_SEED_20260907.md §4 F-W2 — "byte-identical seed → ≥95% hit;
one-byte genome drift → measurable hit-rate collapse." Insight under test: ollama
caches prompt prefixes internally (llama.cpp longest-common-prefix KV reuse), so a
byte-identical prefix should RE-LIGHT (near-zero prefill) while a one-byte drift
forces a re-prefill of everything after the drift byte. The re-light measured with
a stopwatch.

ARMS (per round; 3 rounds, medians reported):
  COLD          unique genome marker in the header (seeded per round) -> previous
                cache diverges at the marker -> ~full prefill.
  WARM-IDENT    the EXACT same request sent again back-to-back -> prefix cache hit.
  DRIFT-TAIL    one byte changed at --drift-tail-frac (default 0.95) of the body,
                length preserved -> documents per-token LCP reuse semantics
                (secondary honesty arm: "where the bytes are").
  DRIFT-HEAD    one byte changed at --drift-head-frac (default 0.10) of the body —
                the production genome position (system-prompt region) -> F-W2
                collapse arm.
Round order cold -> warm -> tail -> head keeps the single KV slot clean: warm sees
cold's sequence (identical), tail sees warm's (diverges at 95%), head sees tail's
(diverges at 10%), next round's cold diverges at the marker.

METRICS (per arm: wall_ms stopwatch AND ollama-reported prompt_eval_ms — the
runner's internal prefill stopwatch; medians over rounds):
  speedup_prefill     = med(cold prefill) / med(warm prefill)     <- F-W2 gate
  hit_ratio_est       = 1 - med(warm prefill) / med(cold prefill)
  collapse_ratio      = med(head prefill)  / med(cold prefill)    (~1 = collapsed)
  drift_vs_warm       = med(head prefill)  / med(warm prefill)
  tail_retention      = 1 - med(tail prefill) / med(cold prefill) ("where the
                        bytes are": a byte at 95% should keep most of the benefit)
VERDICT (tri-state): SUPPORTED iff speedup_prefill >= 2.0 AND hit_ratio_est >= 0.95
AND 0.7 <= collapse_ratio <= 1.5 AND drift_vs_warm >= 2.0. Warm slower than 1.5x /
hit < 0.5 -> DISPUTED. Everything between, or any measurement failure -> UNPROVEN.

HONESTY LABEL (fleet law): every row and printout is PROXY.
  - Local qwen2.5:3b-instruct timing on a shared host, NOT the production
    GLM-5.3-flash Max 1M-token meter (the c1/c2 context-anatomy screenshots with
    cache hit 97.3/96.7% remain the manual production datapoints).
  - Ollama's cache semantics are implementation details: this measures PREFILL
    TIMING, not token-exact hit counts. prompt_eval_count reports total prompt
    tokens even on hits; prompt_eval_duration is the recompute signal.
  - Host wall clock carries multi-second scheduler/pagecache noise (observed in
    calibration 09-07: an identical resend logged 18.3s wall with 16ms prefill),
    so the verdict gates on ollama's prefill stopwatch; wall is corroboration and
    unaccounted_ms = wall - prefill - eval is recorded per request.
  - Body text is REAL repo text (AGENTS.md head + W0 tape digests) used as prefill
    load — honestly labeled PROXY corpus, not a production genome.

$0-local only: host ollama (127.0.0.1:11434), no cloud calls, no docker, no
config edits, read-only on all artifacts except its own jsonl rows.

CLI:
  python -m mag.cache_identity probe [--model qwen2.5:3b-instruct]
          [--prefix-tokens 1600] [--rounds 3] [--seed 20260907] [--predict 48]
          [--drift-head-frac 0.10] [--drift-tail-frac 0.95] [--kind probe]
  python -m mag.cache_identity check    # offline determinism + drift integrity

Rows: memory/runs/cache_identity/probe_YYYYMMDD.jsonl (append; label PROXY).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "memory" / "runs" / "cache_identity"
AGENTS_MD = ROOT / "AGENTS.md"
TAPE = ROOT / "memory" / "runs" / "trajectory" / "steps.jsonl"
OLLAMA = "http://127.0.0.1:11434"
PRIMARY_MODEL = "qwen2.5:3b-instruct"
FALLBACK_MODEL = "gemma:2b"
LABEL = "PROXY"                 # fleet honesty law: this instrument is a proxy, always
FALSIFIER = "F-W2"
CHARS_PER_TOKEN = 4.0           # conservative estimate for qwen-ish BPE on English
DEFAULT_PREFIX_TOKENS = 1600
DEFAULT_ROUNDS = 3
DEFAULT_SEED = 20260907
DEFAULT_PREDICT = 48
DEFAULT_HEAD_FRAC = 0.10        # genome-region drift (production system-prompt position)
DEFAULT_TAIL_FRAC = 0.95        # tail drift (documents LCP per-token reuse)
SENTINEL = "The watch ends when the chain says it ends."
KEEP_ALIVE = "10m"
# F-W2 verdict gates (documented constants; changing them re-versions the instrument)
GATE_SPEEDUP = 2.0
GATE_HIT = 0.95
GATE_COLLAPSE_LO, GATE_COLLAPSE_HI = 0.7, 1.5
GATE_DRIFT_VS_WARM = 2.0
DISPUTE_SPEEDUP_MAX, DISPUTE_HIT_MAX = 1.5, 0.5


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------- prefix body

def load_body_text(target_chars: int) -> str:
    """Real repo text as prefill load, honestly labeled. Deterministic: pure
    function of the repo files at fixed truncation. ASCII-normalized so the
    one-byte drift is provably exactly one byte."""
    chunks: list[str] = ["[label: PROXY prefill corpus — real repo text, NOT a "
                         "production genome; the production meter datapoints remain "
                         "the c1/c2 context-anatomy screenshots]"]
    if AGENTS_MD.is_file():
        head = AGENTS_MD.read_text(encoding="utf-8", errors="replace")
        chunks.append("[source: AGENTS.md head — real standing instructions]\n" + head)
    if TAPE.is_file():
        lines = TAPE.read_text(encoding="utf-8", errors="replace").splitlines()
        digests = []
        for i, ln in enumerate(lines[:64]):
            digests.append(f"[source: W0 trajectory tape row {i + 1}] {ln[:220]}")
        chunks.append("[source: memory/runs/trajectory/steps.jsonl digests — real "
                      "sealed steps]\n" + "\n".join(digests))
    pool = "\n".join(chunks)
    # ASCII-normalize (1 char == 1 byte) and squash whitespace runs
    pool = "".join(c if 32 <= ord(c) < 127 else " " for c in pool)
    pool = " ".join(pool.split())
    if not pool:
        pool = "the fleet runs on files not process memory "
    out = []
    n = 0
    i = 0
    while n < target_chars:
        piece = pool[i % len(pool):] or pool
        out.append(piece[: max(1, target_chars - n)] if n == 0 else piece)
        n += len(out[-1])
        i += len(pool)
    body = "".join(out)[:target_chars]
    return body


def compose_prefix(marker: str, body: str) -> str:
    """Header (carries the genome marker) + body + fixed sentinel sentence.
    Deterministic: pure function of inputs."""
    header = ("CACHE IDENTITY PROBE (W3, falsifier F-W2, PROXY instrument). "
              f"Genome marker: {marker}. The context below is real repo text used "
              "as prefill load, honestly labeled. Read it as warmed state.\n\n")
    return header + body + "\n\n" + SENTINEL


def drift_byte(prefix: str, frac: float) -> tuple[str, int]:
    """Flip ONE byte at frac of the BODY region (after the header line, before the
    sentinel), preserving length. Deterministic. Returns (drifted, index)."""
    header_end = prefix.find("\n\n")
    start = header_end + 2 if header_end != -1 else 0
    body_end = prefix.rfind("\n\n" + SENTINEL)
    end = body_end if body_end != -1 else len(prefix)
    span = max(1, end - start)
    idx = start + min(span - 1, max(0, int(span * frac)))
    orig = prefix[idx]
    new = "x" if orig != "x" else "q"
    return prefix[:idx] + new + prefix[idx + 1:], idx


def prompt_sha(system: str, user: str) -> str:
    return hashlib.sha256((system + "\x00" + user).encode("utf-8")).hexdigest()[:16]


def marker_for(seed: int, round_no: int) -> str:
    return hashlib.sha256(f"{seed}:{round_no}".encode("utf-8")).hexdigest()[:16]


def median(values: list[float]) -> float:
    return statistics.median(values) if values else 0.0


# ---------------------------------------------------------------- ollama

def ollama_health() -> tuple[bool, str]:
    try:
        with urllib.request.urlopen(f"{OLLAMA}/api/version", timeout=5) as resp:
            return True, json.loads(resp.read().decode("utf-8")).get("version", "?")
    except Exception as exc:  # noqa: BLE001 — down is a result, not a crash
        return False, str(exc)


def pick_model() -> str:
    try:
        with urllib.request.urlopen(f"{OLLAMA}/api/tags", timeout=5) as resp:
            names = {m.get("name", "") for m in
                     json.loads(resp.read().decode("utf-8")).get("models", [])}
    except Exception:  # noqa: BLE001
        return FALLBACK_MODEL
    if PRIMARY_MODEL in names:
        return PRIMARY_MODEL
    if FALLBACK_MODEL in names:
        return FALLBACK_MODEL
    return next(iter(sorted(names)), PRIMARY_MODEL)


def chat_prefill(model: str, system: str, user: str, num_predict: int
                 ) -> dict[str, Any]:
    """One non-streaming /api/chat request, timed with a stopwatch on the outside
    and read off ollama's internal prefill stopwatch on the inside."""
    payload: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        "stream": False,
        "keep_alive": KEEP_ALIVE,
        "options": {"num_predict": num_predict, "temperature": 0},
    }
    req = urllib.request.Request(
        f"{OLLAMA}/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=600) as resp:
        d = json.loads(resp.read().decode("utf-8"))
    wall_ms = round((time.perf_counter() - t0) * 1000.0, 3)
    prefill_ms = round(float(d.get("prompt_eval_duration") or 0) / 1e6, 3)
    eval_ms = round(float(d.get("eval_duration") or 0) / 1e6, 3)
    load_ms = round(float(d.get("load_duration") or 0) / 1e6, 3)
    return {
        "wall_ms": wall_ms,
        "ollama_prefill_ms": prefill_ms,
        "ollama_eval_ms": eval_ms,
        "ollama_load_ms": load_ms,
        "prompt_eval_count": d.get("prompt_eval_count", 0),
        "eval_count": d.get("eval_count", 0),
        "unaccounted_ms": round(wall_ms - prefill_ms - eval_ms, 3),
        "gen_head": ((d.get("message") or {}).get("content") or "").strip()[:120],
    }


# ---------------------------------------------------------------- metrics

def compute_metrics(med: dict[str, float]) -> dict[str, Any]:
    """Ratios from medians. Prefill stopwatch is the F-W2 gate; wall corroborates."""
    def ratio(a: float, b: float) -> float:
        return round(a / b, 6) if b > 1e-9 else 0.0
    speedup_prefill = ratio(med["cold_prefill_ms"], med["warm_prefill_ms"])
    speedup_wall = ratio(med["cold_wall_ms"], med["warm_wall_ms"])
    hit_prefill = round(1.0 - ratio(med["warm_prefill_ms"], med["cold_prefill_ms"]), 6) \
        if med["cold_prefill_ms"] > 1e-9 else 0.0
    hit_wall = round(1.0 - ratio(med["warm_wall_ms"], med["cold_wall_ms"]), 6) \
        if med["cold_wall_ms"] > 1e-9 else 0.0
    collapse = ratio(med["drift_head_prefill_ms"], med["cold_prefill_ms"])
    drift_vs_warm = ratio(med["drift_head_prefill_ms"], med["warm_prefill_ms"])
    tail_retention = round(1.0 - ratio(med["drift_tail_prefill_ms"], med["cold_prefill_ms"]),
                           6) if med["cold_prefill_ms"] > 1e-9 else 0.0
    return {"speedup_prefill": speedup_prefill, "speedup_wall": speedup_wall,
            "hit_ratio_est_prefill": hit_prefill, "hit_ratio_est_wall": hit_wall,
            "collapse_ratio_prefill": collapse,
            "drift_vs_warm_prefill": drift_vs_warm,
            "tail_retention_prefill": tail_retention}


def verdict_tri_state(metrics: dict[str, Any]) -> dict[str, str]:
    """F-W2 tri-state on the documented gates."""
    sp = metrics["speedup_prefill"]
    hit = metrics["hit_ratio_est_prefill"]
    col = metrics["collapse_ratio_prefill"]
    dvw = metrics["drift_vs_warm_prefill"]
    if (sp >= GATE_SPEEDUP and hit >= GATE_HIT
            and GATE_COLLAPSE_LO <= col <= GATE_COLLAPSE_HI
            and dvw >= GATE_DRIFT_VS_WARM):
        return {"tri_state": "SUPPORTED", "f_w2": "PASS",
                "detail": (f"identical warm re-lights ({sp:.1f}x prefill speedup, "
                           f"hit-est {hit:.3f} >= 0.95) and one-byte genome-region "
                           f"drift collapses to ~cold (collapse {col:.2f}); "
                           "byte-identity matters most where the bytes are fewest "
                           "— MEASURED (PROXY)")}
    if sp < DISPUTE_SPEEDUP_MAX and hit < DISPUTE_HIT_MAX:
        return {"tri_state": "DISPUTED", "f_w2": "FAIL",
                "detail": (f"no warm re-light observed (speedup {sp:.2f}x, hit-est "
                           f"{hit:.3f}) at this resolution — cache-identity claim "
                           "contradicted on this ollama build/host")}
    return {"tri_state": "UNPROVEN", "f_w2": "INCONCLUSIVE",
            "detail": (f"between gates (speedup {sp:.2f}x, hit {hit:.3f}, collapse "
                       f"{col:.2f}, drift-vs-warm {dvw:.2f}) — standing wave "
                       "directionally real but F-W2 bar unmet at this resolution")}


# ---------------------------------------------------------------- probe

ARM_ORDER = ("cold", "warm", "drift_tail", "drift_head")
USER_PROMPT = "Repeat the last sentence of the context verbatim."


def cmd_probe(args: argparse.Namespace) -> int:
    ok, ver = ollama_health()
    model = args.model or pick_model()
    # Per-run nonce seed by default: a FIXED seed re-uses the previous run's EXACT
    # strings, and ollama's lingering KV slots then serve stale sequences back as
    # hits (measured 09-07: run 2's drift_head matched run 1's cached drift_head ->
    # 14ms "hit", inverting the drift arms — cross-run byte-identity re-lights the
    # cache, which is the thesis itself masquerading as contamination). Pin --seed
    # to reproduce a run byte-for-byte.
    seed = args.seed if args.seed is not None else int(time.time())
    target_chars = int(args.prefix_tokens * CHARS_PER_TOKEN)
    body = load_body_text(target_chars)
    print(f"ollama health: {'UP' if ok else 'DOWN'} (v{ver}) | model: {model} | "
          f"body {len(body)} chars (~{args.prefix_tokens} tokens, PROXY corpus: "
          "AGENTS.md head + W0 tape digests)")
    if not ok:
        print("ollama DOWN — landing instrument state only; measurement marked "
              "PENDING-OLLAMA (never starting containers; host ollama is the eye).")

    row: dict[str, Any] = {
        "label": LABEL, "instrument": "cache_identity W3",
        "falsifier": FALSIFIER, "ts": _now(), "run_kind": args.kind,
        "status": "PENDING-OLLAMA" if not ok else "MEASURED",
        "ollama_up": ok, "ollama_version": ver, "model": model,
        "prefix_tokens_target": args.prefix_tokens, "body_chars": len(body),
        "body_sha16": hashlib.sha256(body.encode("utf-8")).hexdigest()[:16],
        "body_sources": ["AGENTS.md head", "memory/runs/trajectory/steps.jsonl digests"],
        "body_note": "real repo text as prefill load — PROXY corpus, not a production genome",
        "sentinel": SENTINEL, "user_prompt": USER_PROMPT,
        "seed": seed, "seed_nonce": args.seed is None,
        "rounds": args.rounds, "num_predict": args.predict,
        "drift_head_frac": args.drift_head_frac, "drift_tail_frac": args.drift_tail_frac,
        "gates": {"speedup": GATE_SPEEDUP, "hit": GATE_HIT,
                  "collapse": [GATE_COLLAPSE_LO, GATE_COLLAPSE_HI],
                  "drift_vs_warm": GATE_DRIFT_VS_WARM},
        "honesty": ("PROXY: local 3B prefill timing on a shared host, not the "
                    "production 1M-token meter (c1/c2 screenshots remain the manual "
                    "datapoints). Ollama cache semantics are implementation details — "
                    "this measures prefill timing, not token-exact hit counts; "
                    "prompt_eval_count reports total prompt tokens even on hits."),
        "rounds_data": [], "load_events": 0,
    }

    if ok:
        # model warm (load once, outside all timed arms)
        chat_prefill(model, "warmup only. " + SENTINEL, USER_PROMPT, 8)

        user = USER_PROMPT
        for r in range(1, args.rounds + 1):
            marker = marker_for(args.seed, r)
            base = compose_prefix(marker, body)
            tail_sys, tail_idx = drift_byte(base, args.drift_tail_frac)
            head_sys, head_idx = drift_byte(base, args.drift_head_frac)
            assert prompt_sha(base, user) == prompt_sha(base, user)
            assert tail_sys != base and head_sys != base
            assert len(tail_sys) == len(base) == len(head_sys)

            arms: dict[str, Any] = {}
            for arm, sys_text, frac in (
                    ("cold", base, None), ("warm", base, None),
                    ("drift_tail", tail_sys, args.drift_tail_frac),
                    ("drift_head", head_sys, args.drift_head_frac)):
                t = chat_prefill(model, sys_text, user, args.predict)
                t["prompt_sha16"] = prompt_sha(sys_text, user)
                t["drift_frac"] = frac
                arms[arm] = t
                if t["ollama_load_ms"] > 0:
                    row["load_events"] += 1
            row["rounds_data"].append({
                "round": r, "marker": marker,
                "drift_tail_index": tail_idx, "drift_head_index": head_idx,
                "arms": arms})
            print(f"round {r}: cold wall={arms['cold']['wall_ms']:.0f}ms "
                  f"prefill={arms['cold']['ollama_prefill_ms']:.0f}ms | "
                  f"warm wall={arms['warm']['wall_ms']:.0f}ms "
                  f"prefill={arms['warm']['ollama_prefill_ms']:.1f}ms | "
                  f"drift_tail prefill={arms['drift_tail']['ollama_prefill_ms']:.0f}ms | "
                  f"drift_head prefill={arms['drift_head']['ollama_prefill_ms']:.0f}ms")

        med = {
            "cold_wall_ms": median([rd["arms"]["cold"]["wall_ms"] for rd in row["rounds_data"]]),
            "warm_wall_ms": median([rd["arms"]["warm"]["wall_ms"] for rd in row["rounds_data"]]),
            "drift_tail_wall_ms": median([rd["arms"]["drift_tail"]["wall_ms"] for rd in row["rounds_data"]]),
            "drift_head_wall_ms": median([rd["arms"]["drift_head"]["wall_ms"] for rd in row["rounds_data"]]),
            "cold_prefill_ms": median([rd["arms"]["cold"]["ollama_prefill_ms"] for rd in row["rounds_data"]]),
            "warm_prefill_ms": median([rd["arms"]["warm"]["ollama_prefill_ms"] for rd in row["rounds_data"]]),
            "drift_tail_prefill_ms": median([rd["arms"]["drift_tail"]["ollama_prefill_ms"] for rd in row["rounds_data"]]),
            "drift_head_prefill_ms": median([rd["arms"]["drift_head"]["ollama_prefill_ms"] for rd in row["rounds_data"]]),
        }
        metrics = compute_metrics(med)
        verdict = verdict_tri_state(metrics)
        row["medians_ms"] = {k: round(v, 3) for k, v in med.items()}
        row["metrics"] = metrics
        row["verdict"] = verdict
        row["status"] = "MEASURED"

        print(f"\nmedians (ms): cold prefill {med['cold_prefill_ms']:.0f} / "
              f"warm {med['warm_prefill_ms']:.1f} / drift_tail "
              f"{med['drift_tail_prefill_ms']:.0f} / drift_head "
              f"{med['drift_head_prefill_ms']:.0f}")
        print(f"  wall medians: cold {med['cold_wall_ms']:.0f} / warm "
              f"{med['warm_wall_ms']:.0f} (shared-host wall is noisy; prefill is the gate)")
        print(f"speedup_prefill={metrics['speedup_prefill']:.1f}x  "
              f"hit_ratio_est={metrics['hit_ratio_est_prefill']:.3f}  "
              f"collapse={metrics['collapse_ratio_prefill']:.2f}  "
              f"drift_vs_warm={metrics['drift_vs_warm_prefill']:.1f}x  "
              f"tail_retention={metrics['tail_retention_prefill']:.3f}")
        print(f"F-W2 VERDICT [{LABEL}]: {verdict['tri_state']} ({verdict['f_w2']}) "
              f"— {verdict['detail']}")
    else:
        row["verdict"] = {"tri_state": "UNPROVEN", "f_w2": "PENDING-OLLAMA",
                          "detail": "ollama down; instrument landed, measurement pending"}

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"probe_{_now()[:10].replace('-', '')}.jsonl"
    with out.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"row appended: {out}")
    return 0


# ---------------------------------------------------------------- check

def cmd_check(_args: argparse.Namespace) -> int:
    """Offline determinism + drift integrity — no ollama needed."""
    ok = True

    def chk(name: str, cond: bool) -> None:
        nonlocal ok
        ok = ok and bool(cond)
        print(f"  {'PASS' if cond else 'FAIL'}  {name}")

    body = load_body_text(8000)
    chk("body ASCII-normalized", all(32 <= ord(c) < 127 for c in body))
    b2 = load_body_text(8000)
    chk("body deterministic (compose twice byte-identical)",
        hashlib.sha256(body.encode()).hexdigest() ==
        hashlib.sha256(b2.encode()).hexdigest())

    base = compose_prefix(marker_for(DEFAULT_SEED, 1), body)
    base2 = compose_prefix(marker_for(DEFAULT_SEED, 1), body)
    chk("prefix deterministic", base == base2)
    chk("sentinel is the final sentence", base.rstrip().endswith(SENTINEL))

    for frac, name in ((DEFAULT_HEAD_FRAC, "head"), (DEFAULT_TAIL_FRAC, "tail")):
        d, idx = drift_byte(base, frac)
        chk(f"drift_{name}: length preserved", len(d) == len(base))
        chk(f"drift_{name}: exactly one byte differs",
            sum(1 for a, b in zip(d, base) if a != b) == 1)
        chk(f"drift_{name}: prefix intact", d[:idx] == base[:idx])
        chk(f"drift_{name}: suffix intact", d[idx + 1:] == base[idx + 1:])
        chk(f"drift_{name}: inside body region",
            base.find("\n\n") + 2 <= idx < base.rfind("\n\n" + SENTINEL))
        d2, idx2 = drift_byte(base, frac)
        chk(f"drift_{name}: deterministic", d == d2 and idx == idx2)

    m1 = marker_for(DEFAULT_SEED, 1)
    m2 = marker_for(DEFAULT_SEED, 2)
    chk("markers differ per round", m1 != m2)
    chk("marker deterministic", m1 == marker_for(DEFAULT_SEED, 1))

    chk("median odd", median([1.0, 5.0, 3.0]) == 3.0)
    chk("median even", median([1.0, 2.0, 3.0, 4.0]) == 2.5)

    syn = {"cold_prefill_ms": 1000.0, "warm_prefill_ms": 10.0,
           "drift_tail_prefill_ms": 60.0, "drift_head_prefill_ms": 900.0,
           "cold_wall_ms": 2000.0, "warm_wall_ms": 100.0,
           "drift_tail_wall_ms": 120.0, "drift_head_wall_ms": 1800.0}
    met = compute_metrics(syn)
    chk("metrics: speedup 100x", abs(met["speedup_prefill"] - 100.0) < 1e-9)
    chk("metrics: hit 0.99", abs(met["hit_ratio_est_prefill"] - 0.99) < 1e-9)
    chk("metrics: collapse 0.9", abs(met["collapse_ratio_prefill"] - 0.9) < 1e-9)
    chk("metrics: tail_retention 0.94", abs(met["tail_retention_prefill"] - 0.94) < 1e-9)
    v_pass = verdict_tri_state(met)
    chk("verdict: synthetic strong signal -> SUPPORTED", v_pass["tri_state"] == "SUPPORTED")
    syn_bad = dict(syn, warm_prefill_ms=900.0)
    v_disp = verdict_tri_state(compute_metrics(syn_bad))
    chk("verdict: no re-light -> DISPUTED", v_disp["tri_state"] == "DISPUTED")
    syn_mid = dict(syn, warm_prefill_ms=100.0)
    chk("verdict: speedup 10x but hit 0.9 < 0.95 -> UNPROVEN",
        verdict_tri_state(compute_metrics(syn_mid))["tri_state"] == "UNPROVEN")

    print(f"[{LABEL}] cache_identity check -> {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


# ---------------------------------------------------------------- CLI

def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    ap = argparse.ArgumentParser(
        prog="mag.cache_identity",
        description="W3 cache-identity probe, falsifier F-W2 (PROXY, $0-local)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_probe = sub.add_parser("probe", help="cache re-light A/B/C probe via host ollama")
    p_probe.add_argument("--model", default="")
    p_probe.add_argument("--prefix-tokens", type=int, default=DEFAULT_PREFIX_TOKENS)
    p_probe.add_argument("--rounds", type=int, default=DEFAULT_ROUNDS)
    p_probe.add_argument("--seed", type=int, default=None,
                         help="pin the genome-marker seed (default: per-run nonce; "
                              "a fixed seed resurrects the previous run's exact "
                              "strings and their cached KV sequences)")
    p_probe.add_argument("--predict", type=int, default=DEFAULT_PREDICT)
    p_probe.add_argument("--drift-head-frac", type=float, default=DEFAULT_HEAD_FRAC)
    p_probe.add_argument("--drift-tail-frac", type=float, default=DEFAULT_TAIL_FRAC)
    p_probe.add_argument("--kind", choices=("probe", "calibration"), default="probe")
    p_probe.set_defaults(fn=cmd_probe)

    p_check = sub.add_parser("check", help="offline determinism + drift integrity")
    p_check.set_defaults(fn=cmd_check)

    args = ap.parse_args()
    sys.exit(args.fn(args))


if __name__ == "__main__":
    main()
