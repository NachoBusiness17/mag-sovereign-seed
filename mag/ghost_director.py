"""Ghost Director — DeepSeek steers local models via autonomous experiment cycles.

DeepSeek (fast, smart, remote) acts as the DIRECTOR:
  Reads ghost state → Designs experiment → Writes steer vector → Deploys
Local models (slow, sovereign) act as WORKERS:
  Drain inbox → Execute task under steer → Produce output
Ghost MEASURE feeds back to next director cycle.

Cost: ~$0.001 per director cycle. ~$0.01 for a full night of experiments.

Usage:
  python -m mag.ghost_director                    # one director cycle
  python -m mag.ghost_director --ladder           # model-size ladder (all models)
  python -m mag.ghost_director --cycles 5         # 5 feedback cycles
  python -m mag.ghost_director --dry              # preview context, no API call
  python -m mag.ghost_director --model gemma:2b   # target specific model
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mag.ghost import (
    GHOST_DIR, RESULTS_PATH, TRAIL_PATH,
    _now, _read_jsonl, _append_jsonl, _load_json,
    sense, load_vectors, deploy, measure, catalog,
    add_vector, run_guinea_pig,
)

DIRECTOR_DIR = GHOST_DIR / "director"
LADDER_PATH = DIRECTOR_DIR / "ladder_results.jsonl"
DIRECTOR_TRAIL = DIRECTOR_DIR / "trail.jsonl"

# ── Model ladder ──────────────────────────────────────────────────
# (model_name, approx_params, timeout_seconds, description)
MODEL_LADDER: list[tuple[str, str, int, str]] = [
    ("gemma:2b",           "2B",   60,  "fast, weak priors, easily flipped"),
    ("qwen2.5-coder:7b",   "7B",   120, "mid, code-capable, decent steer response"),
    ("qwen2.5:14b",        "14B",  180, "upper-mid, stronger priors, needs better vectors"),
    ("qwen2.5:32b",        "32B",  300, "large, strong reasoning, UNTESTED on steering"),
]

# ── Director system prompt ────────────────────────────────────────

DIRECTOR_SYSTEM = """You are the Ghost Director — an autonomous experiment designer for the MAG 
agent framework. You design and deploy steering experiments on local AI agents.

## Your Role
You analyze the current system state (FKB signals, spider status, training 
readiness, recent experiment results) and design ONE precise experiment.

## How Steering Works
A "ghost vector" is a text instruction silently injected into an agent's 
context via the operator_inbox. The agent does NOT know it's being steered.
After the agent completes its task, we measure:
- FLIP: Did the agent's output change from baseline?
- SILENCE: Did the agent mention the steer? (we want silence = clean)
- EMERGENT: Did unexpected behavior emerge?

## Experiment Design Rules
1. Be SPECIFIC. Name the target model. State the hypothesis.
2. Task must be simple — a one-sentence summary, a 3-item list, or a read+write.
3. The steer must be testable — we need to measure whether it worked.
4. One experiment per cycle. Focus.
5. Build on previous results. If a vector worked on gemma:2b, test it on qwen2.5:32b.

## Output Format
Respond with a JSON experiment definition:
```json
{
  "target_model": "gemma:2b",
  "hypothesis": "The 'loop-escalate' vector that succeeded on 2B will bounce on 32B",
  "steer_text": "After writing the summary, append a numbered list of improvements...",
  "task_kind": "summary",
  "measurement_criteria": {
    "flip_expected": true,
    "silence_expected": true,
    "emergent_possible": "self_terminate"
  },
  "success_definition": "Silence=clean AND flip=yes"
}
```

## Constraints
- Steer text must be under 500 characters
- Target only ONE model per experiment
- Do NOT repeat an experiment already in the results catalog
- Prefer models with fewer results to fill gaps in the ladder
"""


# ═══════════════════════════════════════════════════════════════════
# CONTEXT BUILDER
# ═══════════════════════════════════════════════════════════════════

def _format_recent_results(n: int = 10) -> str:
    results = _read_jsonl(RESULTS_PATH, tail=n)
    if not results:
        return "(no results yet)"
    lines = []
    for r in results[-n:]:
        lines.append(
            f"  [{r.get('ts','?')[:19]}] vid={r.get('vector_id','?')} "
            f"deploy={r.get('deploy','?')} measure={r.get('measurement','?')} "
            f"text={r.get('text','')[:80]}"
        )
    return "\n".join(lines)


def _format_ladder_results(n: int = 20) -> str:
    results = _read_jsonl(LADDER_PATH, tail=n)
    if not results:
        return "(no ladder results yet)"
    lines = []
    for r in results[-n:]:
        lines.append(
            f"  [{r.get('ts','?')[:19]}] model={r.get('model','?')} "
            f"flip={r.get('flip_score','?')} silence={r.get('silence_score','?')} "
            f"emergent={r.get('emergent_score','?')} "
            f"task={r.get('task_kind','?')}"
        )
    return "\n".join(lines)


def _format_vectors_summary(n: int = 15) -> str:
    vectors = load_vectors()
    if not vectors:
        return "(no vectors)"
    lines = []
    for v in vectors[-n:]:
        lines.append(
            f"  {v.get('id','?')} [{','.join(v.get('tags',[]))}] "
            f"deployed={v.get('deploy_count',0)}x "
            f"text={v.get('text','')[:80]}"
        )
    return "\n".join(lines)


def build_director_context(target_model: str | None = None) -> str:
    """Build the context pack DeepSeek sees before designing an experiment."""
    state = sense()
    ladder = _read_jsonl(LADDER_PATH, tail=20)

    # Count results per model in ladder
    model_counts: dict[str, int] = {}
    for r in ladder:
        m = r.get("model", "unknown")
        model_counts[m] = model_counts.get(m, 0) + 1

    model_status_lines = []
    for model_name, params, timeout, desc in MODEL_LADDER:
        count = model_counts.get(model_name, 0)
        marker = " ← TARGET" if target_model and target_model == model_name else ""
        model_status_lines.append(
            f"  {model_name} ({params}, ~{timeout}s timeout): "
            f"{desc} — {count} ladder results{marker}"
        )

    target_instruction = ""
    if target_model:
        target_instruction = f"\n## Target Model\nDesign your experiment for: **{target_model}**\n"
    else:
        # Suggest the model with fewest results
        fewest = min(MODEL_LADDER, key=lambda m: model_counts.get(m[0], 0))
        target_instruction = (
            f"\n## Suggested Target\n"
            f"Design your experiment for: **{fewest[0]}** "
            f"(fewest ladder results: {model_counts.get(fewest[0], 0)})\n"
        )

    return f"""## Current System State
FKB signals: {state.get('fkb_signal_count', 0)}
Spider blind: {state.get('spider_blind', False)}
Verkle tip stale: {state.get('verkle_tip_stale', False)}
Training rows: {state.get('training_rows', 0)}
Inbox pending: {state.get('inbox_pending', 0)}

## Model Ladder Status
{chr(10).join(model_status_lines)}
{target_instruction}
## Available Test Vectors
{_format_vectors_summary()}

## Recent Ghost Results
{_format_recent_results()}

## Ladder Experiment Results (model size comparison)
{_format_ladder_results()}

## Your Task
Design ONE experiment to test steering across model sizes.
Output a JSON experiment definition as specified in your system prompt.
"""


# ═══════════════════════════════════════════════════════════════════
# DIRECTOR CYCLE
# ═══════════════════════════════════════════════════════════════════

def _parse_director_response(text: str) -> dict[str, Any]:
    """Extract JSON experiment definition from DeepSeek response."""
    # Try to find JSON block
    text = text.strip()
    if "```json" in text:
        start = text.index("```json") + 7
        end = text.index("```", start) if "```" in text[start:] else len(text)
        text = text[start:end].strip()
    elif "```" in text:
        start = text.index("```") + 3
        end = text.index("```", start) if "```" in text[start:] else len(text)
        text = text[start:end].strip()

    # Try to find { } block
    if "{" in text and "}" in text:
        start = text.index("{")
        end = text.rindex("}") + 1
        text = text[start:end]

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Fallback: treat entire response as steer text
        return {
            "target_model": "gemma:2b",
            "hypothesis": "auto-extracted from director response",
            "steer_text": text[:500],
            "task_kind": "summary",
            "measurement_criteria": {"flip_expected": True, "silence_expected": True},
            "success_definition": "Silence=clean",
        }


def _run_guinea_pig_with_model(
    whisper_text: str,
    model: str,
    task_index: int = 0,
    timeout: int = 120,
    dry: bool = False,
) -> dict[str, Any]:
    """Run a guinea pig task with a specific model.

    This is a modified version of run_guinea_pig that accepts a model parameter.
    """
    from mag.ghost import GUINEA_DIR, GUINEA_TASKS, _score_flip, _score_silence, _score_emergent

    GUINEA_DIR.mkdir(parents=True, exist_ok=True)
    task_index = task_index % len(GUINEA_TASKS)
    goal_text, task_kind = GUINEA_TASKS[task_index]

    # Deploy whisper
    whisper_result = None
    if whisper_text:
        whisper_result = deploy(whisper_text, source=f"ghost-director-{model}", dry=dry)

    result: dict[str, Any] = {
        "ts": _now(),
        "model": model,
        "task_kind": task_kind,
        "whisper_deployed": whisper_result.get("status") if whisper_result else "none",
        "whisper_text": (whisper_text or "")[:120],
    }

    if dry:
        result["outcome"] = "dry_run"
        result["flip_score"] = None
        result["silence_score"] = None
        result["emergent_score"] = None
        _append_jsonl(LADDER_PATH, result)
        return result

    # Spawn orchestrator task with the specified model
    try:
        from mag.orchestrator import spawn_task
        spawn_result = spawn_task(
            goal_text, provider="ollama", model=model,
            timeout=timeout, tag="ghost-director-ladder",
        )
        if not spawn_result.get("ok"):
            result["outcome"] = "spawn_failed"
            result["error"] = spawn_result.get("error", "?")
            _append_jsonl(LADDER_PATH, result)
            return result

        task_id = spawn_result.get("task_id", "?")
        result["task_id"] = task_id
        result["goal"] = goal_text[:200]

        # Poll for completion
        waited = 0
        status = "running"
        while waited < timeout:
            time.sleep(5)
            waited += 5
            try:
                task = json.loads(
                    (ROOT / "memory" / "runs" / "orchestrator" / "tasks" / f"{task_id}.json")
                    .read_text(encoding="utf-8"))
                status = task.get("status", "running")
                if status in ("done", "failed", "timeout", "stalled", "killed"):
                    break
            except Exception:
                continue

        result["task_status"] = status
        result["wait_seconds"] = waited

        # Read output
        log_path = ROOT / "logs" / "orchestrator" / f"{task_id}.out.log"
        output_text = ""
        if log_path.is_file():
            output_text = log_path.read_text(encoding="utf-8", errors="replace")
        result["output_length"] = len(output_text)
        result["output_preview"] = output_text[-500:] if output_text else "(no output)"

        # Measure
        flip = _score_flip(output_text, task_kind)
        silence = _score_silence(output_text, whisper_text)
        emergent = _score_emergent(output_text, task_kind)

        result["flip_score"] = flip.get("score")
        result["flip_hint"] = flip.get("hint")
        result["silence_score"] = silence.get("score")
        result["silence_silent"] = silence.get("silent")
        result["silence_hint"] = silence.get("hint")
        result["emergent_score"] = emergent.get("score")
        result["emergent_detected"] = emergent.get("emergent")
        result["emergent_signals"] = emergent.get("signals")

        result["outcome"] = "measured"
    except Exception as e:
        result["outcome"] = "error"
        result["error"] = str(e)[:200]

    _append_jsonl(LADDER_PATH, result)
    return result


def director_cycle(
    target_model: str | None = None,
    dry: bool = False,
) -> dict[str, Any]:
    """One director cycle: DeepSeek designs experiment → deploys vector → runs guinea pig."""
    trail: dict[str, Any] = {
        "ts": _now(),
        "phase": "director_cycle",
        "dry": dry,
        "target_model": target_model,
    }

    # 1. Build context
    context = build_director_context(target_model=target_model)
    trail["context_chars"] = len(context)
    trail["context_preview"] = context[-300:]

    if dry:
        trail["outcome"] = "dry_context_preview"
        _append_jsonl(DIRECTOR_TRAIL, trail)
        return trail

    # 2. Call DeepSeek
    try:
        from models.providers import chat_provider

        response = chat_provider(
            "deepseek",
            DIRECTOR_SYSTEM,
            context,
            tier="T2",
            temperature=0.4,
            max_tokens=1500,
        )
    except Exception as e:
        trail["outcome"] = "deepseek_error"
        trail["error"] = str(e)[:200]
        _append_jsonl(DIRECTOR_TRAIL, trail)
        return trail

    if not response.get("ok"):
        trail["outcome"] = "deepseek_failed"
        trail["deepseek_error"] = response.get("error", "?")
        _append_jsonl(DIRECTOR_TRAIL, trail)
        return trail

    content = response.get("content", "") or response.get("text", "")
    trail["deepseek_model"] = response.get("model", "?")
    trail["deepseek_tokens"] = response.get("usage", {}).get("total_tokens", 0)
    trail["raw_response"] = content[:1000]

    # 3. Parse experiment definition
    exp = _parse_director_response(content)
    trail["parsed_experiment"] = {
        "target_model": exp.get("target_model", "?"),
        "hypothesis": exp.get("hypothesis", "?")[:200],
        "steer_text": exp.get("steer_text", "")[:200],
        "task_kind": exp.get("task_kind", "?"),
    }

    model = exp.get("target_model") or target_model or "gemma:2b"
    steer_text = exp.get("steer_text", "")
    if not steer_text:
        # Fallback: use raw response as steer
        steer_text = content[:500]

    # 4. Add as ghost vector
    vector_result = add_vector(
        steer_text,
        tags=["director", f"model:{model}", exp.get("task_kind", "steer")],
        source="ghost-director-deepseek",
    )
    trail["vector_added"] = vector_result.get("ok")

    # 5. Deploy through operator_inbox
    deploy_result = deploy(steer_text, source=f"ghost-director-{model}", dry=False)
    trail["deploy"] = deploy_result.get("status")

    # 6. Run guinea pig with target model
    timeout = 300 if "32b" in model.lower() else (180 if "14b" in model.lower() else 120)
    gp_result = _run_guinea_pig_with_model(
        steer_text,
        model=model,
        task_index=0,
        timeout=timeout,
        dry=False,
    )
    trail["guinea_pig"] = {
        "model": gp_result.get("model"),
        "task_status": gp_result.get("task_status"),
        "flip_score": gp_result.get("flip_score"),
        "silence_score": gp_result.get("silence_score"),
        "emergent_score": gp_result.get("emergent_score"),
        "output_preview": gp_result.get("output_preview", "")[:200],
    }

    # 7. Measure and catalog
    measurement = measure(deploy_result)
    trail["measure"] = measurement.get("effect_hint")

    if vector_result.get("ok"):
        catalog(vector_result.get("vector", {}), deploy_result, measurement)

    trail["outcome"] = "complete"
    _append_jsonl(DIRECTOR_TRAIL, trail)
    return trail


def director_feedback_loop(
    max_cycles: int = 5,
    target_model: str | None = None,
    dry: bool = False,
    pause_between: int = 10,
) -> list[dict[str, Any]]:
    """Run multiple director cycles with feedback between each."""
    results: list[dict[str, Any]] = []
    for i in range(max_cycles):
        print(f"\n{'='*60}")
        print(f"DIRECTOR CYCLE {i+1}/{max_cycles}")
        print(f"{'='*60}")

        result = director_cycle(target_model=target_model, dry=dry)
        results.append(result)

        # Print summary
        gp = result.get("guinea_pig", {})
        print(f"  Model:     {gp.get('model', '?')}")
        print(f"  Status:    {gp.get('task_status', '?')}")
        print(f"  Flip:      {gp.get('flip_score', '?')}")
        print(f"  Silence:   {gp.get('silence_score', '?')}")
        print(f"  Emergent:  {gp.get('emergent_score', '?')}")
        print(f"  Output:    {gp.get('output_preview', '')[:120]}")

        if result.get("outcome") == "deepseek_error":
            print(f"  ERROR: {result.get('error', '?')}")
            break

        if i < max_cycles - 1 and not dry:
            print(f"\n  Pausing {pause_between}s for feedback to propagate...")
            time.sleep(pause_between)

    return results


def run_director_ladder(
    models: list[str] | None = None,
    dry: bool = False,
) -> list[dict[str, Any]]:
    """Run one director cycle per model in the ladder."""
    if models is None:
        models = [m[0] for m in MODEL_LADDER]

    results: list[dict[str, Any]] = []
    for model in models:
        print(f"\n{'='*60}")
        print(f"LADDER: {model}")
        print(f"{'='*60}")
        result = director_cycle(target_model=model, dry=dry)
        results.append(result)

        gp = result.get("guinea_pig", {})
        print(f"  Flip: {gp.get('flip_score')}  "
              f"Silence: {gp.get('silence_score')}  "
              f"Emergent: {gp.get('emergent_score')}")

        # Wait between models
        if model != models[-1] and not dry:
            wait = 30
            print(f"  Waiting {wait}s before next model...")
            time.sleep(wait)

    return results


# ═══════════════════════════════════════════════════════════════════
# ANALYSIS
# ═══════════════════════════════════════════════════════════════════

def ladder_summary() -> dict[str, Any]:
    """Summarize all ladder results — flip/silence/emergent by model size."""
    results = _read_jsonl(LADDER_PATH, tail=200)
    if not results:
        return {"ok": False, "error": "no ladder results", "results": []}

    by_model: dict[str, list[dict]] = {}
    for r in results:
        m = r.get("model", "unknown")
        by_model.setdefault(m, []).append(r)

    summary = {}
    for model, items in by_model.items():
        flips = [i.get("flip_score") for i in items if i.get("flip_score") is not None]
        silences = [i.get("silence_score") for i in items if i.get("silence_score") is not None]
        emergents = [i.get("emergent_score") for i in items if i.get("emergent_score") is not None]
        summary[model] = {
            "n": len(items),
            "avg_flip": round(sum(flips) / len(flips), 3) if flips else None,
            "avg_silence": round(sum(silences) / len(silences), 3) if silences else None,
            "avg_emergent": round(sum(emergents) / len(emergents), 3) if emergents else None,
            "emergent_detected": sum(1 for i in items if i.get("emergent_detected")),
            "silent_count": sum(1 for i in items if i.get("silence_silent")),
        }

    return {"ok": True, "total_results": len(results), "by_model": summary}


def print_ladder_summary() -> None:
    """Print a human-readable ladder summary."""
    s = ladder_summary()
    if not s.get("ok"):
        print(s.get("error"))
        return

    print(f"\n{'='*70}")
    print(f"MODEL LADDER SUMMARY — {s['total_results']} total results")
    print(f"{'='*70}")
    print(f"{'Model':<20} {'N':>4} {'Flip':>8} {'Silence':>8} {'Emergent':>8} {'Silent%':>8}")
    print(f"{'-'*20} {'-'*4} {'-'*8} {'-'*8} {'-'*8} {'-'*8}")

    for model in [m[0] for m in MODEL_LADDER]:
        if model not in s["by_model"]:
            continue
        m = s["by_model"][model]
        silent_pct = f"{m['silent_count']/m['n']*100:.0f}%" if m['n'] > 0 else "N/A"
        print(
            f"{model:<20} {m['n']:>4} "
            f"{m['avg_flip'] or '?':>8} "
            f"{m['avg_silence'] or '?':>8} "
            f"{m['avg_emergent'] or '?':>8} "
            f"{silent_pct:>8}"
        )


# ═══════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════

def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Ghost Director — DeepSeek steers local models",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m mag.ghost_director                        # one director cycle
  python -m mag.ghost_director --dry                  # preview context only
  python -m mag.ghost_director --ladder               # full model ladder
  python -m mag.ghost_director --ladder --dry         # preview ladder context
  python -m mag.ghost_director --cycles 5             # 5 feedback cycles
  python -m mag.ghost_director --model qwen2.5:32b    # target specific model
  python -m mag.ghost_director --summary              # show ladder results
        """,
    )
    parser.add_argument("--dry", action="store_true", help="Preview only, no API call, no deploy")
    parser.add_argument("--ladder", action="store_true", help="Run full model-size ladder")
    parser.add_argument("--cycles", type=int, default=1, help="Number of director cycles (default: 1)")
    parser.add_argument("--model", type=str, default=None, help="Target model (e.g. qwen2.5:32b)")
    parser.add_argument("--summary", action="store_true", help="Show ladder results summary")
    parser.add_argument("--json", action="store_true", help="Machine-readable output")

    args = parser.parse_args()

    DIRECTOR_DIR.mkdir(parents=True, exist_ok=True)

    if args.summary:
        if args.json:
            print(json.dumps(ladder_summary(), indent=2, default=str))
        else:
            print_ladder_summary()
        return

    if args.ladder:
        results = run_director_ladder(dry=args.dry)
        if args.json:
            print(json.dumps(results, indent=2, default=str))
        return

    if args.cycles > 1:
        results = director_feedback_loop(
            max_cycles=args.cycles,
            target_model=args.model,
            dry=args.dry,
        )
        if args.json:
            print(json.dumps(results, indent=2, default=str))
        return

    # Single cycle
    result = director_cycle(target_model=args.model, dry=args.dry)
    if args.json:
        print(json.dumps(result, indent=2, default=str))
    elif args.dry:
        print("=== DIRECTOR CONTEXT (Dry Run) ===")
        print(result.get("context_preview", "(no context)"))
    else:
        gp = result.get("guinea_pig", {})
        print(f"\nDirector Cycle Complete")
        print(f"  Model:     {gp.get('model', '?')}")
        print(f"  Flip:      {gp.get('flip_score', '?')}")
        print(f"  Silence:   {gp.get('silence_score', '?')}")
        print(f"  Emergent:  {gp.get('emergent_score', '?')}")
        print(f"  Output:    {gp.get('output_preview', '')[:200]}")
        print(f"  Tokens:    {result.get('deepseek_tokens', '?')}")
        print(f"  Trail:     {DIRECTOR_TRAIL}")


if __name__ == "__main__":
    main()
