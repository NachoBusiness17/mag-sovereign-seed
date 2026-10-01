"""preload_selector — F-W5 instrument: trajectory-conditioned preload selector A/B probe.

Fold build order #1 (watch/WORLDLINE_SEED_20260907.md §6, ratified falsifier F-W5):
same dead session, two preload orderings — trajectory-conditioned vs shuffled —
run through HOST ollama (127.0.0.1:11434, native /api/chat, non-streaming,
logprobs:true, top_logprobs=10). Delta <3% = the selector is decorative, kill it.

HONESTY LABEL (fleet law): every row and printout from this instrument is PROXY.
A 2-3B local specimen (qwen2.5:3b-instruct, fallback gemma:2b) measures ordering
sensitivity of a preload body; it is NOT the production GLM-5.3-flash Max session.
The F-W5 verdict applies to the INSTRUMENT's question — "does preload order move
the field at all" — not to production resurrection fidelity.

SCORING FORMULA (deterministic given identical inputs; no wall-clock, no RNG in
the orderer; ties broken by (ts, block_id) so the order is total):

  score(b) = 0.5 * recency(b) + 0.2 * heat(b) + 0.3 * success(b)

  recency(b) = (ts_b - ts_min) / (ts_max - ts_min)          in [0,1], newer = higher
               (missing/unparseable ts -> 0.0; span<=0 -> 1.0 for all)
  heat(b)    = within-source normalization of evidence weight:
               tesuji rows: min(1, tokens_b / max_tokens_source)
               tape rows:   min(1, duration_ms_b / max_ms_source)   (no token count)
               (0 when the source max is 0)
  success(b) = 1.0 if the step succeeded (tesuji verdict SUPPORTED, or tape
               exit_code == 0) else 0.0 (DISPUTED/SHADOW/UNPROVEN/nonzero exit)

Weights are fixed constants of the instrument (W_RECENCY/W_HEAT/W_SUCCESS below);
changing them changes the instrument and must be re-versioned. The SHUFFLER uses
random.Random(seed) — fixed seed, default 20260907 — over the SAME block set, so
conditioned vs shuffled differ in ORDER ONLY, never in content.

METRICS (both runs greedy: temperature 0, num_predict fixed):
  - shared continuation tokens = positions j where run_A.token[j] == run_B.token[j]
    (position-wise alignment; conservative when churn realigns later — documented).
  - mean_abs_dlp  = mean(|lp_A[j] - lp_B[j]|) over shared j
  - rel_delta_pct = 100 * mean_abs_dlp / mean(|lp_A[j]|) over shared j   <- F-W5 metric
  - churn_rate    = 1 - |shared| / n_positions   (top-1 token churn)
  - ppl_A, ppl_B  = exp(-mean(selected logprob)) per run over its own tokens
  - ppl_delta_pct = 100 * |ppl_A - ppl_B| / max(ppl_A, ppl_B)
  VERDICT (on rel_delta_pct):  <3  -> DECORATIVE (kill)
                               3-10 -> MEASURED_EFFECT
                               >10  -> LARGE_EFFECT
  Observer-effect guard (OLLAMA_LOGPROBS_PROBE_20260907 caveat #18163): the
  conditioned ordering is re-run once WITHOUT logprobs; identical generated text
  = probe not perturbing the walk (reported, not gating).

Card: watch/WORLDLINE_SEED_20260907.md (§4 F-W5, §6 fold build order #1).
Probe receipt card: watch/inbox/OLLAMA_LOGPROBS_PROBE_20260907.md (wire shapes).

CLI:
  python -m mag.preload_selector probe [--trajectory PATH] [--tape PATH]
          [--model NAME] [--seed S] [--blocks N] [--predict N] [--topk K]
  python -m mag.preload_selector order  [--trajectory PATH] [--tape PATH] [--top N]
  python -m mag.preload_selector shuffle [--trajectory PATH] [--tape PATH]
          [--seed S] [--top N]
  python -m mag.preload_selector selftest     # offline determinism checks, $0

Rows: memory/runs/preload_selector/probe_YYYYMMDD.jsonl (append; label PROXY).
$0-local only: host ollama, no cloud calls, no docker, no config edits.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TRAJECTORY = ROOT / "watch" / "TESUJI_MAP.jsonl"
DEFAULT_TAPE = ROOT / "memory" / "runs" / "trajectory" / "steps.jsonl"
OUT_DIR = ROOT / "memory" / "runs" / "preload_selector"
OLLAMA = "http://127.0.0.1:11434"
PRIMARY_MODEL = "qwen2.5:3b-instruct"
FALLBACK_MODEL = "gemma:2b"
BLOCK_CHARS = 400          # per-block text cap before composing the preload body
DEFAULT_BLOCKS = 10        # blocks in the preload body (~1K tokens, <2K budget)
DEFAULT_PREDICT = 48       # continuation tokens per run
DEFAULT_TOPK = 10          # top_logprobs k (valid 0-20 per v0.32.7)
DEFAULT_SEED = 20260907
W_RECENCY, W_HEAT, W_SUCCESS = 0.5, 0.2, 0.3
LABEL = "PROXY"            # fleet honesty law: this instrument is a proxy, always


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_ts(ts: str) -> datetime | None:
    try:
        return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ")
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------- blocks

def load_blocks(trajectory: Path = DEFAULT_TRAJECTORY,
                tape: Path = DEFAULT_TAPE) -> list[dict[str, Any]]:
    """Real trajectory evidence -> candidate preload blocks (id, source, ts, text,
    tokens, ms, success). Repo files are data: malformed lines are skipped, never trusted."""
    blocks: list[dict[str, Any]] = []

    def _clip(s: str) -> str:
        s = " ".join(str(s).split())
        return s[:BLOCK_CHARS]

    if trajectory.is_file():
        for i, ln in enumerate(trajectory.read_text(encoding="utf-8",
                                                     errors="replace").splitlines()):
            ln = ln.strip()
            if not ln:
                continue
            try:
                r = json.loads(ln)
            except json.JSONDecodeError:
                continue
            probe = r.get("probe", "")
            note = r.get("note", "")
            cell = r.get("cell", f"row{i}")
            text = _clip(f"[{cell}] probe: {probe} -> {r.get('verdict', '?')}. {note}")
            ms = int(r.get("ms") or 0)
            tokens = int(r.get("tokens") or 0)
            blocks.append({
                "id": f"tesuji:{str(r.get('hash', ''))[:12] or i}",
                "source": "tesuji",
                "ts": r.get("ts", ""),
                "text": text,
                "tokens": tokens,
                "ms": ms,
                "success": 1.0 if r.get("verdict") == "SUPPORTED" else 0.0,
            })

    if tape.is_file():
        for i, ln in enumerate(tape.read_text(encoding="utf-8",
                                              errors="replace").splitlines()):
            ln = ln.strip()
            if not ln:
                continue
            try:
                r = json.loads(ln)
            except json.JSONDecodeError:
                continue
            tr = r.get("tool_result", {})
            code = tr.get("exit_code") if isinstance(tr, dict) else None
            out = str(r.get("output", ""))[:160]
            dur = r.get("timing", {})
            ms = int(round(float(dur.get("duration_s", 0)) * 1000)) \
                if isinstance(dur, dict) else 0
            text = _clip(f"[step {r.get('session_id', '')}:{str(r.get('step_hash', ''))[:8]}] "
                         f"cmd: {r.get('input', '')} -> exit {code}; out: {out}")
            blocks.append({
                "id": f"tape:{str(r.get('step_hash', ''))[:12] or i}",
                "source": "tape",
                "ts": r.get("ts", ""),
                "text": text,
                "tokens": 0,
                "ms": ms,
                "success": 1.0 if code == 0 else 0.0,
            })
    return blocks


def score_blocks(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Apply the documented formula. Deterministic: pure function of block list."""
    if not blocks:
        return []
    tss = [_parse_ts(b["ts"]) for b in blocks]
    known = [t for t in tss if t is not None]
    ts_min = min(known) if known else None
    ts_span = (max(known) - ts_min).total_seconds() if known else 0.0
    for src in ("tesuji", "tape"):  # within-source heat normalization
        rows = [b for b in blocks if b["source"] == src]
        max_tok = max((b["tokens"] for b in rows), default=0)
        max_ms = max((b["ms"] for b in rows), default=0)
        for b in rows:
            b["heat"] = (min(1.0, b["tokens"] / max_tok) if max_tok > 0
                         else (min(1.0, b["ms"] / max_ms) if max_ms > 0 else 0.0))
    for b, ts in zip(blocks, tss):
        recency = ((ts - ts_min).total_seconds() / ts_span) if (ts and ts_span > 0) \
            else (1.0 if ts and ts_span == 0 and ts == ts_min and not known else 0.0)
        b["recency"] = min(1.0, max(0.0, recency))
        b["score"] = round(W_RECENCY * b["recency"] + W_HEAT * b["heat"]
                           + W_SUCCESS * b["success"], 9)
    return sorted(blocks, key=lambda b: (-b["score"], b["ts"], b["id"]))


def order_blocks(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return score_blocks(list(blocks))


def shuffle_blocks(blocks: list[dict[str, Any]], seed: int = DEFAULT_SEED
                   ) -> list[dict[str, Any]]:
    """The control: SAME block set, fixed-seed randomized order."""
    out = list(blocks)
    random.Random(seed).shuffle(out)
    return out


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


def chat_logprobs(model: str, system: str, user: str, num_predict: int,
                  top_k: int, want_logprobs: bool = True) -> dict[str, Any]:
    """Native /api/chat, non-streaming, logprobs:true + top_logprobs:int
    (wire shapes per watch/inbox/OLLAMA_LOGPROBS_PROBE_20260907.md)."""
    payload: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        "stream": False,
        "options": {"num_predict": num_predict, "temperature": 0},
    }
    if want_logprobs:
        payload["logprobs"] = True
        payload["top_logprobs"] = top_k
    req = urllib.request.Request(
        f"{OLLAMA}/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=180) as resp:
        return json.loads(resp.read().decode("utf-8"))


# ---------------------------------------------------------------- probe

def compose_prompt(blocks: list[dict[str, Any]]) -> tuple[str, str]:
    """Fixed continuation prompt; ONLY block order varies between arms."""
    body = "\n".join(f"[{i + 1}] {b['text']}" for i, b in enumerate(blocks))
    system = ("You are resurrecting a dead coding-agent session. Warmed preload "
              "context blocks from its trajectory follow.\n" + body)
    user = ("Based only on the preload blocks above, name the single most important "
            "next action for this session in one sentence, then justify it in one "
            "more sentence.")
    return system, user


def run_arm(model: str, blocks: list[dict[str, Any]], num_predict: int, top_k: int,
            want_logprobs: bool = True) -> dict[str, Any]:
    system, user = compose_prompt(blocks)
    resp = chat_logprobs(model, system, user, num_predict, top_k, want_logprobs)
    lps = resp.get("logprobs") or []
    text = ((resp.get("message") or {}).get("content") or "").strip()
    return {"tokens": [e.get("token", "") for e in lps],
            "logprobs": [float(e.get("logprob", 0.0)) for e in lps],
            "text": text,
            "prompt_sha": hashlib.sha256((system + "\x00" + user)
                                         .encode("utf-8")).hexdigest()[:16],
            "eval_count": resp.get("eval_count", 0)}


def compare(arm_a: dict[str, Any], arm_b: dict[str, Any]) -> dict[str, Any]:
    ta, tb = arm_a["tokens"], arm_b["tokens"]
    la, lb = arm_a["logprobs"], arm_b["logprobs"]
    n = min(len(ta), len(tb))
    shared = [j for j in range(n) if ta[j] == tb[j]]
    churn = 1.0 - (len(shared) / n) if n else 1.0
    dlp = [abs(la[j] - lb[j]) for j in shared]
    scale = [abs(la[j]) for j in shared]
    mean_dlp = sum(dlp) / len(dlp) if dlp else 0.0
    mean_lp = sum(scale) / len(scale) if scale else 0.0
    rel_pct = (100.0 * mean_dlp / mean_lp) if mean_lp > 1e-12 else 0.0
    ppl_a = math.exp(-sum(la) / len(la)) if la else float("nan")
    ppl_b = math.exp(-sum(lb) / len(lb)) if lb else float("nan")
    ppl_delta = (100.0 * abs(ppl_a - ppl_b) / max(ppl_a, ppl_b)
                 if max(ppl_a, ppl_b) > 0 else 0.0)
    verdict = ("DECORATIVE" if rel_pct < 3.0 else
               "MEASURED_EFFECT" if rel_pct < 10.0 else "LARGE_EFFECT")
    return {"positions": n, "shared_positions": len(shared),
            "top1_churn_rate": round(churn, 6),
            "mean_abs_dlogprob": round(mean_dlp, 6),
            "mean_abs_logprob_scale": round(mean_lp, 6),
            "rel_delta_pct": round(rel_pct, 4),
            "ppl_conditioned": round(ppl_a, 6), "ppl_shuffled": round(ppl_b, 6),
            "ppl_delta_pct": round(ppl_delta, 4),
            "verdict": verdict}


# ---------------------------------------------------------------- CLI cmds

def cmd_order(args: argparse.Namespace) -> int:
    blocks = score_blocks(load_blocks(Path(args.trajectory), Path(args.tape)))
    rows = blocks[:args.top] if args.top else blocks
    for i, b in enumerate(rows, 1):
        print(f"{i:3d}. score={b['score']:.4f} rec={b['recency']:.2f} "
              f"heat={b['heat']:.2f} suc={b['success']:.0f} {b['id']} :: {b['text'][:90]}")
    print(f"[{LABEL}] {len(rows)} of {len(blocks)} blocks, weights "
          f"recency={W_RECENCY} heat={W_HEAT} success={W_SUCCESS}")
    return 0


def cmd_shuffle(args: argparse.Namespace) -> int:
    ranked = score_blocks(load_blocks(Path(args.trajectory), Path(args.tape)))
    rows = shuffle_blocks(ranked, args.seed)
    rows = rows[:args.top] if args.top else rows
    for i, b in enumerate(rows, 1):
        print(f"{i:3d}. {b['id']} (score={b['score']:.4f}) :: {b['text'][:90]}")
    print(f"[{LABEL}] shuffled seed={args.seed} over the SAME {len(rows)}-block set")
    return 0


def cmd_probe(args: argparse.Namespace) -> int:
    ok, ver = ollama_health()
    print(f"ollama health: {'UP' if ok else 'DOWN'} (v{ver})")
    ranked = score_blocks(load_blocks(Path(args.trajectory), Path(args.tape)))
    if not ranked:
        print("no trajectory blocks found — aborting")
        return 1
    chosen = ranked[:args.blocks]
    cond = chosen                                # trajectory-conditioned order
    shuf = shuffle_blocks(chosen, args.seed)     # same set, seeded random order

    row: dict[str, Any] = {
        "label": LABEL, "instrument": "preload_selector FW5 (fold build order #1)",
        "ts": _now(), "status": "PENDING-OLLAMA",
        "ollama_up": ok, "ollama_version": ver,
        "model": args.model or pick_model(),
        "seed": args.seed, "num_predict": args.predict, "top_logprobs": args.topk,
        "blocks": [b["id"] for b in chosen],
        "conditioned_order": [b["id"] for b in cond],
        "shuffled_order": [b["id"] for b in shuf],
        "weights": {"recency": W_RECENCY, "heat": W_HEAT, "success": W_SUCCESS},
        "honesty": ("PROXY instrument: 2-3B local specimen measures ordering "
                    "sensitivity of a preload body; F-W5 verdict applies to the "
                    "instrument's question, not production resurrection fidelity"),
    }
    metrics: dict[str, Any] | None = None
    if ok:
        arm_a = run_arm(row["model"], cond, args.predict, args.topk)
        arm_b = run_arm(row["model"], shuf, args.predict, args.topk)
        observer = run_arm(row["model"], cond, args.predict, args.topk,
                           want_logprobs=False)
        metrics = compare(arm_a, arm_b)
        row.update({
            "status": "MEASURED",
            "prompt_sha_conditioned": arm_a["prompt_sha"],
            "prompt_sha_shuffled": arm_b["prompt_sha"],
            "gen_conditioned": arm_a["text"][:300],
            "gen_shuffled": arm_b["text"][:300],
            "observer_effect_same_text": observer["text"].strip() == arm_a["text"].strip(),
            **metrics,
        })
        print(f"model: {row['model']} | blocks: {len(chosen)} | seed: {args.seed}")
        print(f"positions={metrics['positions']} shared={metrics['shared_positions']} "
              f"churn={metrics['top1_churn_rate']:.3f}")
        print(f"mean|dlogprob|={metrics['mean_abs_dlogprob']:.4f} "
              f"(scale {metrics['mean_abs_logprob_scale']:.4f}) "
              f"-> rel_delta={metrics['rel_delta_pct']:.2f}%")
        print(f"ppl cond={metrics['ppl_conditioned']:.3f} "
              f"shuf={metrics['ppl_shuffled']:.3f} "
              f"delta={metrics['ppl_delta_pct']:.2f}%")
        print(f"observer-effect guard (logprobs on/off same text): "
              f"{row['observer_effect_same_text']}")
        print(f"F-W5 VERDICT [{LABEL}]: {metrics['verdict']}")
    else:
        print("ollama DOWN — measurement row marked PENDING-OLLAMA; not starting "
              "any container (law: the eye is HOST ollama).")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"probe_{_now()[:10].replace('-', '')}.jsonl"
    with out.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"row appended: {out}")
    return 0


def cmd_selftest(_args: argparse.Namespace) -> int:
    """Offline determinism checks — no ollama needed."""
    blocks = load_blocks()
    ranked = score_blocks(blocks)
    again = score_blocks(load_blocks())
    ids_a = [b["id"] for b in ranked]
    ok1 = ids_a == [b["id"] for b in again]
    s1 = [b["id"] for b in shuffle_blocks(ranked, DEFAULT_SEED)]
    s2 = [b["id"] for b in shuffle_blocks(ranked, DEFAULT_SEED)]
    ok2 = s1 == s2
    ok3 = s1 != ids_a
    ok4 = sorted(s1) == sorted(ids_a)
    head = ranked[:DEFAULT_BLOCKS]
    ok5 = sorted(b["id"] for b in head) == \
        sorted(b["id"] for b in shuffle_blocks(head, DEFAULT_SEED))
    passed = all([ok1, ok2, ok3, ok4, ok5])
    print(f"[{LABEL}] selftest: orderer_deterministic={ok1} shuffle_deterministic={ok2} "
          f"shuffle_differs={ok3} same_multiset={ok4} probe_subset_invariant={ok5} "
          f"-> {'PASS' if passed else 'FAIL'}")
    return 0 if passed else 1


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    ap = argparse.ArgumentParser(prog="mag.preload_selector",
                                 description="F-W5 trajectory-conditioned preload A/B probe (PROXY)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--trajectory", default=str(DEFAULT_TRAJECTORY))
        p.add_argument("--tape", default=str(DEFAULT_TAPE))
        p.add_argument("--top", type=int, default=0)

    p_order = sub.add_parser("order", help="ranked preload ordering")
    common(p_order)
    p_order.set_defaults(fn=cmd_order)

    p_shuf = sub.add_parser("shuffle", help="fixed-seed control order")
    common(p_shuf)
    p_shuf.add_argument("--seed", type=int, default=DEFAULT_SEED)
    p_shuf.set_defaults(fn=cmd_shuffle)

    p_probe = sub.add_parser("probe", help="A/B probe through host ollama")
    common(p_probe)
    p_probe.add_argument("--model", default="")
    p_probe.add_argument("--seed", type=int, default=DEFAULT_SEED)
    p_probe.add_argument("--blocks", type=int, default=DEFAULT_BLOCKS)
    p_probe.add_argument("--predict", type=int, default=DEFAULT_PREDICT)
    p_probe.add_argument("--topk", type=int, default=DEFAULT_TOPK)
    p_probe.set_defaults(fn=cmd_probe)

    p_self = sub.add_parser("selftest", help="offline determinism checks")
    p_self.set_defaults(fn=cmd_selftest)

    args = ap.parse_args()
    sys.exit(args.fn(args))


if __name__ == "__main__":
    main()
