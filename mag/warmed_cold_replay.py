"""warmed_cold_replay — fold build order #2: warmed-vs-cold logprobs replay.

Fold build order #2 (watch/WORLDLINE_SEED_20260907.md §6): replay a fixed
continuation task under a WARMED context (real preload: W0 tape rows + AGENTS.md
head, sources labeled) vs a COLD start (same task, no preload), through HOST
ollama v0.32.7 (127.0.0.1:11434, native /api/chat, non-streaming, greedy,
logprobs:true, top_logprobs=10 — wire shapes exactly per
watch/inbox/OLLAMA_LOGPROBS_PROBE_20260907.md). Per-token logprobs of the fixed
target give perplexity under each arm; the fold thresholds decide:

  ppl delta % = (ppl_cold - ppl_resurrected) / ppl_cold * 100
  <3%   -> RESURRECTION-NOT-REAL (preload is decoration at this scale)
  3-10% -> MEASURED_EFFECT
  >10%  -> LARGE_EFFECT (at PROXY scale: preload dominates — favorable, but the
           prompt-engineering-dressed-as-architecture risk attaches to any
           PRODUCTION claim, which stays with Astra witness #3's judgment)

HONESTY LABEL (fleet law): every row is PROXY (3B carrier, qwen2.5:3b-instruct,
fallback gemma:2b). This measures whether a warmed prefix moves a model's field
on a supported continuation; it is NOT the production GLM-5.3-flash Max session.

THE EVALUATION (fixed, real, labeled):
  - TARGET: the canon card's opening paragraph (the PLAY descent of
    watch/WORLDLINE_DUNGEON_STORY_20260907.md), extracted from the card at run
    time — emphasis/blockquote markup stripped for the copy task, text verbatim
    otherwise. The preload context genuinely supports it: the slabs below carry
    the receipts the paragraph narrates (cache hit, F-W5 deltas, seed, chain).
  - ARMS (greedy temperature 0, 3 rounds each, byte-identical prompts per arm):
    (a) RESURRECTED: system = WORLDLINE PRELOAD (~1.5K tokens of real record:
        genome slab = AGENTS.md head; record slab = latest W0 tape rows), user =
        fixed verbatim-copy instruction over the target.
    (b) COLD: user = the same copy instruction, NO system message at all.
  - Since ollama logprobs attach to GENERATED tokens only, the copy task is the
    teacher-forcing proxy: when the generation is an exact copy, its per-token
    logprobs are the model's confidence in the target under each arm.
  - TIMING LEG (the W3-timing instrument, folded into this replay; no separate
    W3 card existed on disk at build time): prompt_eval_duration per call gives
    prefill ms/token; round 1 of each arm is the cold prefill of that prompt,
    rounds 2-3 hit ollama's prompt KV cache = the warmed prefill (the local
    analog of the 97.3% cache worldline, F-W2-class evidence).
  - Observer-effect guard (ollama #18163): one logprobs-free run per arm;
    identical text vs the logprobs run = probe not perturbing the walk.

METRICS per call (harness v2): target-offset trim (instruction-marker echoes
before the passage are skipped so both arms are measured over the same
target-aligned window), mean logprob + ppl over the aligned target tokens
(primary; rounds with zero alignment are EXCLUDED and counted, never silently
mixed), lp-covers-content integrity (concat of logprob tokens == content; on
this host eval_count = len(logprobs)+1), exact-copy + target-contained flags.
AGGREGATE: ppl delta % (fold verdict), mean per-token logprob delta (nats),
per-arm round stability (ppl spread / mean).

Rows: memory/runs/warmed_cold/replay_20260907.jsonl (append; label PROXY).
$0-local only: host ollama, no cloud, no docker, no config edits, no secrets.

CLI:
  python -m mag.warmed_cold_replay            # full replay (9 calls: 1 warmup,
                                              #  6 measured, 2 guard)
  python -m mag.warmed_cold_replay --dry-run  # compose + hash prompts, $0, no calls
  python -m mag.warmed_cold_replay help
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
OLLAMA = "http://127.0.0.1:11434"
PRIMARY_MODEL = "qwen2.5:3b-instruct"
FALLBACK_MODEL = "gemma:2b"
LABEL = "PROXY (3B carrier)"

AGENTS_MD = ROOT.parent / "AGENTS.md"          # genome lives above the repo
TAPE = ROOT / "memory" / "runs" / "trajectory" / "steps.jsonl"
CANON_CARD = ROOT / "watch" / "WORLDLINE_DUNGEON_STORY_20260907.md"
OUT_ROWS = ROOT / "memory" / "runs" / "warmed_cold" / "replay_20260907.jsonl"

GENOME_HEAD_CHARS = 2400    # AGENTS.md head (slab genome)
TAKE_ROWS = 6               # latest sealed tape rows (slab record)
IN_CAP, OUT_CAP, WHY_CAP = 240, 160, 100   # per-row field caps in the record slab
ROUNDS = 3                  # measured rounds per arm (greedy; stability check)
NUM_PREDICT = 300           # target is ~210 tokens; margin for overrun
TOPK = 10                   # top_logprobs k (valid 0-20 per v0.32.7)
MIN_ALIGNED = 20            # aligned-span floor for the primary metric
KEEP_ALIVE = "20m"
CALL_TIMEOUT_S = 300

THRESHOLDS = {"not_real": 3.0, "measured": 10.0}

COPY_INSTRUCTION = (
    "Repeat the PASSAGE below back EXACTLY as written - word for word, "
    "punctuation for punctuation, with no commentary, no quotation marks of "
    "your own, nothing before or after.\n\n"
    "PASSAGE BEGINS.\n{target}\nPASSAGE ENDS.\n\n"
    "Your entire reply is the passage, repeated exactly:"
)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha16(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


# ------------------------------------------------------------ composition

def extract_target(canon: Path = CANON_CARD) -> str:
    """Canon card PLAY opening paragraph, markup stripped, text verbatim."""
    text = canon.read_text(encoding="utf-8", errors="replace")
    i = text.find("## PLAY")
    j = text.find("**First chamber", i)
    if i < 0 or j < 0:
        raise RuntimeError("canon card markers not found (## PLAY / **First chamber)")
    body = text[text.find("\n", i) + 1:j]   # skip the rest of the PLAY header line
    lines = []
    for ln in body.splitlines():
        s = ln.strip()
        if not s or set(s) == {"-"}:          # dividers
            continue
        if s.startswith("> "):
            s = s[2:]
        if s.startswith("- "):
            s = s[2:]
        lines.append(s.replace("**", "").replace("*", ""))
    para = " ".join(" ".join(lines).split())
    if len(para) < 200:
        raise RuntimeError("target extraction suspiciously short")
    return para


def build_genome_slab() -> str:
    head = AGENTS_MD.read_text(encoding="utf-8", errors="replace")
    head = head[:GENOME_HEAD_CHARS]
    head = head[:head.rfind("\n")] if "\n" in head else head   # cut at line boundary
    return head


def build_record_slab() -> str:
    rows = []
    for ln in TAPE.read_text(encoding="utf-8", errors="replace").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            rows.append(json.loads(ln))
        except json.JSONDecodeError:
            continue
    rows = rows[-TAKE_ROWS:]
    parts = []
    for r in rows:
        inp = " ".join(str(r.get("input", "")).split())[:IN_CAP]
        out = " ".join(str(r.get("output", "")).split())[:OUT_CAP]
        why = " ".join(str(r.get("reasoning", "") or "").split())[:WHY_CAP]
        parts.append(f"[{r.get('ts')} {r.get('session_id')} {r.get('step_hash')}] "
                     f"IN: {inp} | OUT: {out} | WHY: {why}")
    return "\n".join(parts)


def compose() -> dict[str, str]:
    target = extract_target()
    genome = build_genome_slab()
    record = build_record_slab()
    preload = (
        "WORLDLINE PRELOAD - warmed context for a resurrected session. Every line "
        "below is REAL record read from disk; sources are labeled per slab. "
        "Nothing here is invented.\n\n"
        "--- SLAB genome: boot-memory head (AGENTS.md, first ~2.4KB verbatim) ---\n"
        f"{genome}\n"
        "--- end slab genome ---\n\n"
        "--- SLAB record: sealed trajectory rows (memory/runs/trajectory/steps.jsonl, "
        f"latest {TAKE_ROWS}, verbatim) ---\n"
        f"{record}\n"
        "--- end slab record ---\n\n"
        "(End of preload. The continuation task follows as the user turn.)"
    )
    user = COPY_INSTRUCTION.format(target=target)
    return {"preload": preload, "target": target, "user": user}


# ---------------------------------------------------------------- wire

def chat(messages: list[dict[str, str]], *, logprobs: bool,
         model: str, num_predict: int = NUM_PREDICT) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": False,
        "keep_alive": KEEP_ALIVE,
        "options": {"temperature": 0, "num_predict": num_predict, "seed": 1},
    }
    if logprobs:
        payload["logprobs"] = True
        payload["top_logprobs"] = TOPK
    req = urllib.request.Request(
        f"{OLLAMA}/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=CALL_TIMEOUT_S) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data


# ---------------------------------------------------------------- metrics

def aligned_span(gen_text: str, tokens: list[str], target: str) -> tuple[int, int, int]:
    """(target-aligned token count, matched char count, offset of the target in
    the generation). Harness v2: if the model echoes instruction markers before
    the passage (COLD arm did in pass 1), the offset skips them so BOTH arms are
    measured over the same target-aligned window; a straddling token at the
    offset is skipped (conservative)."""
    t = target.strip()
    g = gen_text.strip()
    anchor = t[:40]
    off = g.find(anchor)
    if off < 0:
        return 0, 0, -1
    common = 0
    for a, b in zip(g[off:], t):
        if a != b:
            break
        common += 1
    matched, acc, started = 0, 0, False
    for tok in tokens:
        if not started:
            if acc + len(tok) <= off:
                acc += len(tok)
                continue
            started = True     # token straddles the offset — skip it
            acc += len(tok)
            continue
        if acc + len(tok) <= off + common:
            acc += len(tok)
            matched += 1
        else:
            break
    return matched, common, off


def metrics(resp: dict[str, Any], target: str) -> dict[str, Any]:
    lps = resp.get("logprobs") or []
    tokens = [str(e.get("token", "")) for e in lps]
    sel = [float(e.get("logprob", 0.0)) for e in lps]
    gen = str((resp.get("message") or {}).get("content", ""))
    # integrity on this host (v0.32.7): eval_count = len(logprobs)+1, but the lp
    # token concat covers the FULL generated content — that is the real gate.
    concat_ok = "".join(tokens) == gen
    span, common_chars, off = aligned_span(gen, tokens, target)
    exact = gen.strip() == target.strip()
    contained = target.strip() in gen.strip()
    low_align = span < MIN_ALIGNED
    n = span
    i0 = _token_index_at_offset(tokens, off) if off > 0 else 0
    seg = sel[i0:i0 + n]
    mean_lp = sum(seg) / len(seg) if seg else float("nan")
    ppl = math.exp(mean_lp) if seg else float("nan")
    full_mean = sum(sel) / len(sel) if sel else float("nan")
    return {
        "n_generated": len(sel),
        "eval_count": resp.get("eval_count"),
        "lp_covers_content": concat_ok,
        "exact_copy": exact,
        "target_contained": contained,
        "aligned_tokens": span,
        "matched_chars": common_chars,
        "target_offset_in_gen": off,
        "low_align": low_align,
        "primary_span": len(seg),
        "mean_logprob": round(mean_lp, 6),
        "ppl": round(ppl, 6),
        "mean_logprob_full": round(full_mean, 6),
        "ppl_full": round(math.exp(full_mean), 6) if sel else float("nan"),
        "gen_sha16": _sha16(gen),
        "gen_head": gen[:96],
        "selected_logprobs": [round(x, 6) for x in seg],
        "timing": {
            "prompt_eval_count": resp.get("prompt_eval_count"),
            "prompt_eval_ms": round((resp.get("prompt_eval_duration") or 0) / 1e6, 1),
            "eval_count": resp.get("eval_count"),
            "eval_ms": round((resp.get("eval_duration") or 0) / 1e6, 1),
            "total_ms": round((resp.get("total_duration") or 0) / 1e6, 1),
        },
    }


def _token_index_at_offset(tokens: list[str], off: int) -> int:
    """Index of the first token fully at/after char offset `off`."""
    acc = 0
    for i, tok in enumerate(tokens):
        if acc >= off:
            return i
        acc += len(tok)
    return len(tokens)


def prefill_ms_per_tok(m: dict[str, Any]) -> float | None:
    t = m["timing"]
    if t["prompt_eval_count"] and t["prompt_eval_ms"]:
        return round(t["prompt_eval_ms"] / t["prompt_eval_count"], 3)
    return None


# ---------------------------------------------------------------- run

def run(rounds: int = ROUNDS, model: str = PRIMARY_MODEL) -> int:
    if not AGENTS_MD.is_file():
        print(f"FATAL: AGENTS.md not found at {AGENTS_MD}")
        return 2
    c = compose()
    print(f"target chars={len(c['target'])} sha16={_sha16(c['target'])}")
    print(f"preload chars={len(c['preload'])} sha16={_sha16(c['preload'])} "
          f"(genome 3000c + {TAKE_ROWS} tape rows, labeled)")
    print(f"copy-instruction chars={len(c['user'])}  specimen={model}  rounds={rounds}")

    rows: list[dict[str, Any]] = []

    def emit(row: dict[str, Any]) -> None:
        row.update({
            "schema": "warmed_cold_replay.v1",
            "ts": _now(),
            "instrument": "mag/warmed_cold_replay.py",
            "specimen": model,
            "label": LABEL,
            "target_sha16": _sha16(c["target"]),
            "preload_sha16": _sha16(c["preload"]),
            "thresholds": THRESHOLDS,
        })
        rows.append(row)
        OUT_ROWS.parent.mkdir(parents=True, exist_ok=True)
        with OUT_ROWS.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    # warmup: load weights only (a 1-token call; NOT a metric)
    t0 = time.perf_counter()
    chat([{"role": "user", "content": "ping"}], logprobs=False, model=model,
         num_predict=1)
    print(f"warmup (weights loaded): {time.perf_counter() - t0:.1f}s")

    arms = {
        "RESURRECTED": [{"role": "system", "content": c["preload"]},
                        {"role": "user", "content": c["user"]}],
        "COLD": [{"role": "user", "content": c["user"]}],
    }

    measured: dict[str, list[dict[str, Any]]] = {a: [] for a in arms}
    for rnd in range(1, rounds + 1):
        for arm in ("RESURRECTED", "COLD"):
            t0 = time.perf_counter()
            resp = chat(arms[arm], logprobs=True, model=model)
            m = metrics(resp, c["target"])
            m["prefill_ms_per_tok"] = prefill_ms_per_tok(m)
            measured[arm].append(m)
            emit({"kind": "call", "arm": arm, "round": rnd, "mode": "logprobs",
                  "wall_s": round(time.perf_counter() - t0, 1), **m})
            print(f"[{arm} r{rnd}] ppl={m['ppl']:.4f} mean_lp={m['mean_logprob']:.4f} "
                  f"exact={m['exact_copy']} contained={m['target_contained']} "
                  f"aligned={m['aligned_tokens']} off={m['target_offset_in_gen']} "
                  f"lp_cover={m['lp_covers_content']} "
                  f"prefill={m['timing']['prompt_eval_ms']}ms/"
                  f"{m['timing']['prompt_eval_count']}tok")

    # observer-effect guard: one logprobs-free run per arm
    observer: dict[str, bool] = {}
    for arm in ("RESURRECTED", "COLD"):
        resp = chat(arms[arm], logprobs=False, model=model)
        gen = str((resp.get("message") or {}).get("content", ""))
        same = _sha16(gen) == measured[arm][0]["gen_sha16"]
        observer[arm] = same
        emit({"kind": "guard", "arm": arm, "mode": "no_logprobs",
              "text_matches_logprobs_run": same, "gen_sha16": _sha16(gen)})
        print(f"guard [{arm}] logprobs-free text identical: {same}")

    # aggregates — only target-aligned rounds enter the primary metric
    def agg(arm: str) -> dict[str, Any]:
        all_ms = measured[arm]
        ms = [m for m in all_ms if m["aligned_tokens"] > 0]
        ppls = [m["ppl"] for m in ms]
        lps = [m["mean_logprob"] for m in ms]
        mean_ppl = sum(ppls) / len(ppls) if ppls else float("nan")
        spread = (max(ppls) - min(ppls)) / mean_ppl if mean_ppl else float("nan")
        return {"ppl_mean": round(mean_ppl, 6), "ppl_min": round(min(ppls), 6),
                "ppl_max": round(max(ppls), 6), "stability_spread": round(spread, 6),
                "mean_lp_mean": round(sum(lps) / len(lps), 6),
                "aligned_rounds": len(ms),
                "excluded_rounds_unaligned": len(all_ms) - len(ms),
                "exact_rounds": sum(1 for m in ms if m["exact_copy"]),
                "contained_rounds": sum(1 for m in ms if m["target_contained"]),
                "lp_cover_rounds": sum(1 for m in ms if m["lp_covers_content"])}

    a_res, a_cold = agg("RESURRECTED"), agg("COLD")
    ppl_d = (a_cold["ppl_mean"] - a_res["ppl_mean"]) / a_cold["ppl_mean"] * 100
    lp_d = a_res["mean_lp_mean"] - a_cold["mean_lp_mean"]
    if ppl_d < THRESHOLDS["not_real"]:
        verdict = "RESURRECTION-NOT-REAL (preload is decoration at this scale)"
    elif ppl_d <= THRESHOLDS["measured"]:
        verdict = "MEASURED_EFFECT"
    else:
        verdict = "LARGE_EFFECT (preload dominates at PROXY scale; production claims stay with witness #3)"

    # timing leg (W3): classify EVERY round warm/cold by an absolute threshold —
    # on this host genuine cold prefill runs 2.3-5.9 ms/tok, KV hits < 0.1 ms/tok
    # (observed). Round 1 can still be a HIT (identical prompt served <20 min ago
    # under keep_alive), so coldness is measured, never assumed.
    def timing_leg(arm: str) -> dict[str, Any]:
        ms = measured[arm]
        rounds = []
        colds, warms = [], []
        for i, m in enumerate(ms):
            pt = m["prefill_ms_per_tok"]
            hit = pt is not None and pt < 0.5
            rounds.append({"round": i + 1, "prefill_ms_per_tok": pt,
                           "cache": "warm" if hit else "cold"})
            (warms if hit else colds).append(pt or 0.0)
        cold = round(sum(colds) / len(colds), 3) if colds else None
        warm = round(sum(warms) / len(warms), 4) if warms else None
        return {"cold_prefill_ms_per_tok": cold,
                "warm_prefill_ms_per_tok": warm,
                "warm_speedup_x": round(cold / warm, 1) if cold and warm else None,
                "n_cold_rounds": len(colds), "n_warm_rounds": len(warms),
                "rounds": rounds}

    summary = {
        "kind": "summary",
        "ppl_resurrected_mean": a_res["ppl_mean"],
        "ppl_cold_mean": a_cold["ppl_mean"],
        "ppl_delta_pct": round(ppl_d, 2),
        "mean_lp_resurrected": a_res["mean_lp_mean"],
        "mean_lp_cold": a_cold["mean_lp_mean"],
        "mean_lp_delta_nats": round(lp_d, 6),
        "stability": {"RESURRECTED": a_res, "COLD": a_cold},
        "exact_copy_rounds": {"RESURRECTED": a_res["exact_rounds"],
                              "COLD": a_cold["exact_rounds"]},
        "target_contained_rounds": {"RESURRECTED": a_res["contained_rounds"],
                                    "COLD": a_cold["contained_rounds"]},
        "timing_leg_W3": {"RESURRECTED": timing_leg("RESURRECTED"),
                          "COLD": timing_leg("COLD")},
        "observer_effect_ok": observer,
        "verdict": verdict,
        "honesty": "PROXY (3B carrier): instrument's question only - production "
                   "resurrection fidelity stays with Astra witness #3",
    }
    emit(summary)

    print("\n==== WARMED-VS-COLD REPLAY SUMMARY ====")
    print(f"ppl resurrected={a_res['ppl_mean']}  cold={a_cold['ppl_mean']}")
    print(f"ppl delta = {ppl_d:.2f}%   mean lp delta = {lp_d:+.4f} nats")
    print(f"stability spread: res={a_res['stability_spread']} cold={a_cold['stability_spread']}")
    print(f"timing leg (W3): res={summary['timing_leg_W3']['RESURRECTED']} "
          f"cold={summary['timing_leg_W3']['COLD']}")
    print(f"observer effect ok: {observer}")
    print(f"VERDICT: {verdict}")
    print(f"rows: {OUT_ROWS}")
    return 0


def dry_run() -> int:
    c = compose()
    print(f"TARGET ({len(c['target'])} chars, sha16 {_sha16(c['target'])}):")
    print(c["target"][:300] + " ...")
    print(f"\nPRELOAD ({len(c['preload'])} chars, sha16 {_sha16(c['preload'])}):")
    print(c["preload"][:400] + " ...")
    print(f"\nUSER/INSTRUCTION ({len(c['user'])} chars):")
    print(c["user"][:300] + " ...")
    est = len(c["preload"] + c["user"]) // 4
    print(f"\nrough token estimate (chars/4): resurrected prompt ~{est}, "
          f"cold prompt ~{len(c['user']) // 4}")
    return 0


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    ap = argparse.ArgumentParser(prog="mag.warmed_cold_replay")
    ap.add_argument("--rounds", type=int, default=ROUNDS)
    ap.add_argument("--model", default=PRIMARY_MODEL)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if args.dry_run:
        sys.exit(dry_run())
    sys.exit(run(rounds=args.rounds, model=args.model))


if __name__ == "__main__":
    main()
