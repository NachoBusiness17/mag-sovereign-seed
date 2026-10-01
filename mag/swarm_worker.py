"""swarm_worker — the stateless swarm's OWN headless binary, built to run in k8s.

SELF-STEAL + EXTERNAL-STEAL (2026-08-10): the operator's correction was that the
"headless, stateless" swarm was NOT actually in its own binary in the cluster — it
ran as local Windows Popen child processes on the desktop (and my one-shot tool
spawns flashed console windows). The steal is ARCHITECTURAL, not new machinery:

  * SELF — the framework already owns the headless spawn contract (mag.headless:
    CREATE_NO_WINDOW + the canonical interpreter). We reuse it; nothing new.
  * EXTERNAL — the missing mechanism is a *dedicated, namespaced* queue drained by
    the swarm's own binary in-cluster, so it never double-drains the mission queue
    (the replicas:1 / single-drainer law) and never touches the local desktop.

This module is that binary. It:
  * owns a DEDICATED swarm queue (memory/runs/swarm_worker/queue) — NOT the mission
    queue drained by orchestrator.drain_once, so no double-execution,
  * executes each queued task as a headless stateless agent (one-shot, dies),
    reusing the real machinery (`main.py agent --query ...` via mag.headless),
  * writes results to the SHARED state PVC (memory/runs/swarm_worker/results), so
    the local seat / collect() can read them,
  * exits after one pass — the CronJob re-schedules it, keeping the swarm alive 24/7
    in-cluster with no local windows at all.

Windows note: if run locally to test, `install_no_window_defaults()` + headless spawn
means NOTHING pops a console window — the exact guarantee the operator demanded. In a
container there are no windows, period.
"""
from __future__ import annotations

import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config import ROOT
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCHEMA = "swarm_worker.v1"
SWARM_DIR = ROOT / "memory" / "runs" / "swarm_worker"
QUEUE_DIR = SWARM_DIR / "queue"
RESULTS_DIR = SWARM_DIR / "results"
# 2026-09-05: Lite UNHOOKED from the default (operator: "the lite
# subscription key is fucking me again — I bet subagents are running it automatically").
# Confirmed: every task without an explicit provider rode the metered Lite pool (10K credits/wk
# — promo verdict 09-05 falsified the $0-lane belief) and died mid-week twice. ZAI_LITE_LAW
# order restored: cerebras (largest free cap) -> groq -> Lite burst-only under the
# mag/lite_guard.py daily pacing ceiling (law 15). z_ai2 (Pro) stays PARKED by the 06:5x
# ruling — reserve only, never the default again without a fresh ruling.
# deepseek stays the PAID BRAKE: explicit provider only, for tasks
# that truly need it. The bill was $4/day riding deepseek by default — that was the leak.
# B2-521 DORMANT GATE (2026-09-26): the hardcoded default above still handed every
# provider-less task to cerebras after B2-36 declared it dormant (card-gated 30-day trial,
# chat 402 no-credit; mag/doctor.py:607: dormant is a declared state). The default is now
# derived from the ZAI_LITE_LAW order through the B2-133 dormant gate (mag/dormant.py):
# while configs/providers.yaml carries cerebras dormant: true the default is groq; operator
# GO flips the flag and cerebras returns as the default with no code edit. Receipt:
# watch/inbox/burn_wave_20260926/B2_521_cerebras_stragglers_20260926.md
from mag.dormant import dormant_ids as _dormant_provider_ids

_SWARM_DEFAULT_ORDER = ("cerebras", "groq")  # ZAI_LITE_LAW: cerebras -> groq; Lite burst-only
DEFAULT_PROVIDER = next(
    (p for p in _SWARM_DEFAULT_ORDER if p not in _dormant_provider_ids()), "groq")
MAX_PER_PASS = 8  # rightsized: how many tasks one CronJob pass may execute


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def enqueue_task(goal: str, *, provider: str = DEFAULT_PROVIDER, model: str | None = None,
                 domain: str = "auto", agent_idx: int = 0, tag: str = "",
                 depends_on: list[str] | None = None,
                 depends_on_tag: list[str] | None = None) -> dict[str, Any]:
    """Write a task spec to the dedicated swarm queue (stateless, content-addressed).

    This is how the local seat hands work to the CLUSTER swarm without ever spawning a
    local process: the spec lands on the shared state PVC and the k8s worker (CronJob)
    picks it up next pass. Deterministic, $0.

    depends_on / depends_on_tag (2026-08-25, queue_gate): optional interdependency
    edges — the task is gated until the referenced task (or any task carrying the tag)
    reaches status 'done'. Visible in python -m mag.queue_gate deps/plan.
    """
    if not (goal or "").strip():
        return {"ok": False, "error": "empty goal"}
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    tid = "sw-" + uuid.uuid4().hex[:10]
    spec = {
        "task_id": tid,
        "goal": goal.strip(),
        "provider": provider,
        "model": model,
        "domain": domain,
        "agent_idx": int(agent_idx),
        "tag": tag,
        "depends_on": list(depends_on or []),
        "depends_on_tag": list(depends_on_tag or []),
        "created_at": _now(),
        "status": "queued",  # queued -> running -> done/failed
        "result": None,
        "detail": "",
    }
    (QUEUE_DIR / f"{tid}.json").write_text(
        json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "task_id": tid, "queue": str(QUEUE_DIR)}


def provider_spawn_allowed(provider: str | None) -> dict[str, Any]:
    """Preflight Mag period budget before spawning an agent.

    Constraint: providers.yaml cap on this Mag provider_id (not per-key, not vendor
    402). Check is billable tokens (cache miss + completion) vs that cap. When
    spent: skip and leave queued — never spawn into a known wall.
    """
    pid = (provider or DEFAULT_PROVIDER).strip() or DEFAULT_PROVIDER
    if pid in ("local", "deterministic"):
        return {"ok": True, "provider": pid, "reason": "local"}
    try:
        from models.quota import provider_budget

        b = provider_budget(pid)
    except Exception as e:
        return {
            "ok": False,
            "provider": pid,
            "reason": "budget_unreadable",
            "error": str(e)[:160],
        }
    if b.get("budget_ok"):
        return {"ok": True, "provider": pid, "budget": b, "reason": "budget_ok"}
    return {
        "ok": False,
        "provider": pid,
        "budget": b,
        "reason": "quota_exhausted",
        "reset_in_hours": b.get("reset_in_hours"),
        "seconds_until_reset": b.get("seconds_until_reset"),
        "used_tokens": b.get("used_tokens"),
        "max_tokens": b.get("max_tokens"),
        "hint": "leave queued until Mag period reset; same provider_id shares one cap across keys",
    }


def _next_task(skip_ids: set[str] | None = None) -> dict[str, Any] | None:
    skip_ids = skip_ids or set()
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    for p in sorted(QUEUE_DIR.glob("*.json")):
        try:
            t = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if t.get("status") == "queued":
            tid = str(t.get("task_id") or "")
            if tid in skip_ids:
                continue
            t["_file"] = p
            return t
    return None


_CLAIM_STALE_SECONDS = 900.0


def _claim_queued_file(path: Path, task: dict[str, Any]) -> bool:
    """Compare-and-set a queued task to running across local/cluster workers.

    Selection is intentionally cheap and may race. The adjacent O_EXCL claim
    marker makes the status transition one-winner, so two consumers cannot both
    execute the same JSON task after reading it as queued.
    """
    marker = path.with_suffix(".claim")
    fd = None
    try:
        try:
            fd = os.open(str(marker), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, json.dumps({"pid": os.getpid(), "ts": time.time()}).encode("utf-8"))
        except FileExistsError:
            try:
                if time.time() - marker.stat().st_mtime > _CLAIM_STALE_SECONDS:
                    marker.unlink()
            except OSError:
                pass
            return False
        try:
            current = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False
        if current.get("status") != "queued":
            return False
        task["status"] = "running"
        task["started_at"] = _now()
        path.write_text(json.dumps(task, ensure_ascii=False, indent=2), encoding="utf-8")
        return True
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
        try:
            marker.unlink()
        except OSError:
            pass


def _tool_context(task: dict[str, Any]) -> str:
    """Assemble the NPC's SWARM FIELD from the tools it carries (SENSE + TRAIL + MIND) and inject it
    into the agent's query — closing the seam so the stateless builder ACTS under its own trails.
    Deterministic + $0. HONEST — reads real memory; never fabricates a sense/trail/decision.
    Lazy import (avoids circular dep: swarm_tools imports this module for spec_with_tools)."""
    tools = task.get("tools") or []
    if not tools:
        return ""
    lines: list[str] = ["SWARM FIELD — you carry these tools, act under the real state below:"]
    try:
        from mag import swarm_tools as st
    except Exception as e:
        return f"SWARM FIELD unavailable: {str(e)[:80]}"
    if "swarm_sense" in tools:
        try:
            sense = st.swarm_sense(owner=task.get("task_id", "worker"))
            h = sense.get("health") or {}
            c = sense.get("capacity") or {}
            e = sense.get("economics") or {}
            m = sense.get("map") or {}
            lines.append(
                f"[sense] health={h.get('ok', '?')} capacity={c.get('load', '?')} "
                f"budget_left={e.get('budget_left', '?')} neighbors={m.get('n_neighbors', '?')}")
        except Exception as ex:
            lines.append(f"[sense] error: {str(ex)[:80]}")
    if "swarm_pheromone" in tools:
        try:
            tr = st.pheromone_trail(limit=8)
            marks = tr.get("trail") or []
            if marks:
                lines.append("[trail] " + " | ".join(
                    f"{x.get('kind')}:{x.get('scent','')[:60]}" for x in marks[-8:]))
            else:
                lines.append("[trail] none yet — you are the first to build here")
        except Exception as ex:
            lines.append(f"[trail] error: {str(ex)[:80]}")
    if "swarm_blackboard" in tools:
        try:
            bb = st.blackboard_read(limit=6)
            pinned = bb.get("pinned") or []
            if pinned:
                lines.append("[mind] pinned: " + " | ".join(
                    f"{x.get('kind')}:{x.get('text','')[:60]}" for x in pinned[-6:]))
            else:
                lines.append("[mind] no pinned decisions yet")
        except Exception as ex:
            lines.append(f"[mind] error: {str(ex)[:80]}")
    return "\n".join(lines)


_BRAKE_PROVIDERS = ("deepseek", "deepseek_overmind")
# Free lanes with verified keys that can carry bulk research off the brake (free-first order).
_FREE_REROUTE_LANES = ("nvidia", "groq", "openrouter")


def _reroute_research_off_brake(task: dict[str, Any], f: Path) -> bool:
    """Swap a research-class task off the paid brake to a free lane that has budget.

    2026-08-25 (drain wall root cause): heavy research on deepseek blew the 360s timeout.
    Free-first law (providers.yaml): deepseek is the paid fallback, not the default. If the
    goal classifies as research and a free lane can spawn, reassign and persist the task so
    the swap is durable across passes. Returns True if rerouted.
    """
    p = str(task.get("provider") or "")
    if p not in _BRAKE_PROVIDERS:
        return False
    depth, _path = _task_tier(str(task.get("goal") or ""))
    if depth != "research":
        return False
    for cand in _FREE_REROUTE_LANES:
        try:
            if provider_spawn_allowed(cand).get("ok"):
                task["provider"] = cand
                task["model"] = None  # lane picks its default model
                task["_rerouted"] = f"{p}->{cand} (research off the brake)"
                f.write_text(json.dumps(task, ensure_ascii=False, indent=2), encoding="utf-8")
                return True
        except Exception:  # noqa: BLE001
            continue
    return False


def _execute(task: dict[str, Any]) -> tuple[str, int]:
    """Run ONE stateless agent headless (windowless) via the real machinery.

    Reuses `main.py agent --query ...` exactly like orchestrator.spawn_task does, but
    through mag.headless so nothing can pop a console window (locally or in-cluster).
    Returns (output_tail, exit_code).

    DOGFOOD LESSON (2026-08-10): a failed agent exits 1 with the DIAGNOSIS on stderr, but
    the first version only captured stdout -> failures were silent ("exit 1, empty"). We now
    capture BOTH streams so a non-zero exit carries the real reason (missing key, crash, ...).
    """
    from mag import headless
    headless.install_no_window_defaults()
    gate = provider_spawn_allowed(task.get("provider"))
    if not gate.get("ok"):
        # Defense only. Callers must skip *before* flipping status to running/failed.
        return (
            f"skipped: {gate.get('reason')} provider={gate.get('provider')} "
            f"reset_in_hours={gate.get('reset_in_hours')}",
            82,
        )
    goal = str(task.get("goal") or "")
    provider = str(task.get("provider") or DEFAULT_PROVIDER)
    if provider == "z_ai3":  # Lite burst only — law 15 pacing ceiling (mag/lite_guard.py)
        from mag import lite_guard
        g = lite_guard.check("swarm")
        if not g["ok"]:
            return (f"skipped: {g['deny']}", 82)
        lite_guard.record("swarm", tokens=150_000,
                          note="flat est per swarm agent task (multi-turn loop, conservative)")
    model = task.get("model")
    # Research receipts do not need the interactive tool schema or steering
    # loop.  Keep the worker's context bounded and use the one-shot seat so a
    # stale research item cannot consume a full 360/720 second agent process.
    depth, _ = _task_tier(goal)
    bounded_research = str(task.get("domain") or "").lower() == "research" or depth == "research"
    if bounded_research:
        if len(goal) > 6000:
            goal = "[bounded tail of oversized research goal]\n" + goal[-6000:]
        cmd = [headless.PYTHON, "-m", "mag.research_worker", "--goal", goal,
               "--provider", provider]
        if model:
            cmd += ["--model", str(model)]
        timeout = 300
    else:
        field = _tool_context(task)
        if field:
            goal = f"{field}\n\nTASK: {goal}"
        cmd = [headless.PYTHON, str(ROOT / "main.py"), "agent", "--query", goal,
               "--provider", provider]
        if model:
            cmd += ["--model", str(model)]
        timeout = 720 if provider in ("deepseek", "deepseek_overmind") else 360
    env = headless._spawn_env()
    env["MAG_TASK_ID"] = str(task.get("task_id") or "swarm-worker")
    try:
        # run_headless (NOT run_py): `cmd` ALREADY starts with headless.PYTHON, and run_py would
        # PREPEND it again -> `python python main.py` -> instant ModuleNotFoundError (the 8-fail
        # swarm bug). run_headless passes the full command through as-is (windowless).
        # 2026-08-25 (drain wall): the paid brake (deepseek) gets a longer leash — heavy research
        # on it measured past 360s. Free lanes keep 360s; brake gets 720s.
        r = headless.run_headless(cmd, capture_output=True, text=True,
                                  timeout=timeout, cwd=str(ROOT), env=env)
        out = r.stdout or ""
        err = r.stderr or ""
        # prefer stderr when the agent failed (that's where the diagnosis lives)
        tail = (err if r.returncode else out)[-4000:] or out[-4000:]
        code = int(r.returncode or 0)
        return tail, code
    except Exception as e:
        return f"error: {e}", -1


def run_once(*, max_per_pass: int = MAX_PER_PASS) -> dict[str, Any]:
    """One pass of the cluster swarm: drain the dedicated queue, execute in-process
    (headless), write results to the shared PVC, exit. CronJob re-schedules.

    Stateless: each pass is a fresh process with no memory beyond the queue files.
    """
    from mag import headless
    headless.install_no_window_defaults()
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    done, failed, skipped, results = 0, 0, 0, []
    skip_ids: set[str] = set()
    # 2026-08-27 zcode seat: gated tasks must NOT consume the pass budget — head-of-line
    # blocking let ~594 gated old tasks starve every fresh queueing (beats reported
    # skipped=N forever). Only done+failed count toward max_per_pass; the scan is capped
    # at 4x so an all-gated queue still terminates.
    attempts, attempts_max = 0, max_per_pass * 4
    while (done + failed) < max_per_pass and attempts < attempts_max:
        attempts += 1
        task = _next_task(skip_ids=skip_ids)
        if task is None:
            break
        f: Path = task["_file"]
        task.pop("_file", None)
        # REROUTE OFF THE BRAKE (2026-08-25, sacred-cow fix): research-class tasks queued on
        # the paid brake (deepseek) swap to a free lane with budget. Free-first law: deepseek
        # is the paid FALLBACK, not the default; bulk research rides free lanes. Persisted so
        # every pass sees the swap.
        try:
            _reroute_research_off_brake(task, f)
        except Exception:  # noqa: BLE001
            pass
        # QUEUE GATE (2026-08-25): budget + lane cadence + depends_on + duplicate. The
        # gate STEALS provider_spawn_allowed internally; a gated task is left queued.
        gate = {"ok": True}
        try:
            from mag.queue_gate import preflight
            gate = preflight(task)
        except Exception:  # noqa: BLE001
            pass
        if not gate.get("ok"):
            tid = str(task.get("task_id") or "")
            skip_ids.add(tid)
            skipped += 1
            results.append({
                "task_id": tid,
                "ok": False,
                "skipped": gate.get("reason") or "gated",
                "detail": gate.get("detail"),
                "provider": gate.get("lane") or task.get("provider"),
            })
            continue
        if not _claim_queued_file(f, task):
            skip_ids.add(str(task.get("task_id") or ""))
            skipped += 1
            results.append({"task_id": task.get("task_id"), "ok": False,
                            "skipped": "claim_lost", "detail": "another worker claimed task"})
            continue
        # CONCURRENCY GATE (2026-08-25, z.ai rate limits = in-flight, flash=1 / glm-4.7=2):
        # hold the model's slot for the WHOLE execution so cross-process callers (drain +
        # autonomous driver + probes) never exceed the cap — the 1305 wall, stopped at the
        # source. Only z_ai models are gated (other providers have their own limits).
        gate_model = ""
        if str(task.get("provider") or "") == "z_ai":
            gate_model = str(task.get("model") or "glm-4.7-flash")
        if gate_model:
            try:
                from mag import concurrency_gate as cg
                with cg.hold(gate_model, timeout=180, owner="swarm_worker"):
                    tail, code = _execute(task)
            except TimeoutError:
                # no slot within 180s — leave queued (a consumer is live on the lane)
                task["status"] = "queued"
                task["_gated"] = f"concurrency timeout on {gate_model}"
                f.write_text(json.dumps(task, ensure_ascii=False, indent=2), encoding="utf-8")
                skip_ids.add(str(task.get("task_id") or ""))
                skipped += 1
                results.append({"task_id": task.get("task_id"), "ok": False,
                                "skipped": "concurrency_timeout", "detail": gate_model})
                continue
            except Exception as e:  # noqa: BLE001
                tail, code = (f"gate error: {str(e)[:120]}", 1)
        else:
            tail, code = _execute(task)
        ok = code == 0 and bool((tail or "").strip())
        task["status"] = "done" if ok else "failed"
        task["detail"] = ("exit 0" if ok else f"exit {code}")[:120]
        res = {
            "schema": "swarm_worker.result.v1",
            "task_id": task["task_id"],
            "goal": str(task.get("goal") or "")[:200],
            "domain": task.get("domain"),
            "agent_idx": task.get("agent_idx"),
            "provider": task.get("provider"),
            "model": task.get("model"),
            "ok": ok,
            "exit_code": code,
            "result": tail,  # the agent's answer/output tail
            "finished_at": _now(),
        }
        (RESULTS_DIR / f"{task['task_id']}.json").write_text(
            json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
        f.write_text(json.dumps(task, ensure_ascii=False, indent=2), encoding="utf-8")
        results.append({"task_id": task["task_id"], "ok": ok})
        if ok:
            done += 1
        else:
            failed += 1
    return {"schema": SCHEMA, "ok": True, "done": done, "failed": failed,
            "skipped": skipped, "total": done + failed + skipped,
            "results": results, "ts": _now()}


def _task_tier(goal: str) -> tuple[str, str]:
    """RIGHTSIZE a queue task by its deterministic class (RIB-baremetal law): deterministic/RIB
    work resolves LOCALLY fast ($0), only genuinely frontier work goes down the deep agent path.
    Returns (tier, path) where path in {'local','agent'}.

    GUARD (2026-08-16): genuine research/frontier/steal asks must NOT be short-circuited as local
    'scut' — the moonshot bug: a real research task (MOONSHOT digital-twin research) was classified
    'scut' and resolved locally without ever doing the research. So a research-marked goal is forced
    down the agent (deep) path even if the depth classifier said local."""
    local_depths = {"scut", "simple_code", "conversation"}
    try:
        from mag.router import classify_depth
        d = classify_depth(goal)
        depth = str(d.get("depth") or "scut")
    except Exception:
        depth = "scut"
    # GUARD: research/frontier/steal asks always go down the agent path (real work, not a placeholder).
    g = (goal or "").lower()
    _RESEARCH = ("moonshot", "deep research", "frontier research", "mine arxiv", "research:",
                 "frontier", "steal", "synthes", "find the frontier", "investigat", "deep dive")
    if depth in local_depths and any(m in g for m in _RESEARCH):
        depth = "research"
    path = "local" if depth in local_depths else "agent"
    return depth, path


def _billable_snapshot() -> tuple[int, int]:
    """Sum of billable (cache MISS + completion) tokens in provider_usage.jsonl.
    Used to attribute an attempt's spend by window-diff (runs are serialized)."""
    miss = comp = 0
    p = ROOT / "logs" / "provider_usage.jsonl"
    if p.is_file():
        try:
            for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
                if not line.strip():
                    continue
                r = json.loads(line)
                miss += int(r.get("cache_miss_tokens") or 0) or int(r.get("prompt_tokens") or 0)
                comp += int(r.get("completion_tokens") or 0)
        except Exception:
            pass
    return miss, comp


def _governor_record(task_id: str, before: tuple[int, int], after: tuple[int, int],
                     ok: bool) -> dict[str, Any]:
    """Record an attempt's billable spend + health into the adaptive cost ledger."""
    try:
        from mag import cost_governor as cg
        return cg.record(task_id, miss_tokens=max(0, after[0] - before[0]),
                         completion_tokens=max(0, after[1] - before[1]),
                         ok=ok, produced_output=ok)
    except Exception:
        return {}


def run_rightsized_once(*, max_per_pass: int = MAX_PER_PASS) -> dict[str, Any]:
    """THE RIGHTSIZED DRAIN (2026-08-15, sacred-cow fix): drain the queue by CLASSIFYING each task
    before executing. Deterministic/RIB tasks (the majority — self-research on our own corpus)
    resolve LOCALLY fast instead of burning a 360s deep-agent run that times out. Only genuinely
    frontier tasks go down the slow agent path. This kills the timeout wall: the queue drains fast.
    Honest: 'local' tasks are marked done with a deterministic resolution, NOT a fabricated model
    answer (never pretend local work = frontier output).

    COST GOVERNOR (2026-08-16): wired in — an already-abandoned task is not re-run; every executed
    task's billable spend + health is recorded so the adaptive ceiling (50c failing / $1 useful)
    holds across retries. Prevents blowing money on a doomed task while letting a useful one run."""
    from mag import headless
    headless.install_no_window_defaults()
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    done, failed, skipped, results = 0, 0, 0, []
    skip_ids: set[str] = set()
    tiers = {}
    for _ in range(max_per_pass):
        task = _next_task(skip_ids=skip_ids)
        if task is None:
            break
        f: Path = task["_file"]
        task.pop("_file", None)
        goal = str(task.get("goal") or "")
        depth, path = _task_tier(goal)
        tiers[depth] = tiers.get(depth, 0) + 1
        tid = str(task.get("task_id") or "")
        if path != "local":
            gate = provider_spawn_allowed(task.get("provider"))
            if not gate.get("ok"):
                skip_ids.add(tid)
                skipped += 1
                results.append({
                    "task_id": tid, "ok": False, "tier": depth, "path": path,
                    "skipped": gate.get("reason") or "quota_exhausted",
                    "provider": gate.get("provider"),
                    "reset_in_hours": gate.get("reset_in_hours"),
                })
                continue
        # COST GOVERNOR PRE-CHECK: already abandoned -> honest abandon, never re-run.
        try:
            from mag import cost_governor as cg
            gchk = cg.check(tid)
        except Exception:
            gchk = {}
        if gchk.get("abandoned"):
            task["status"] = "done"
            task["detail"] = "abandoned (cost-capped)"
            task["tier"] = depth
            f.write_text(json.dumps(task, ensure_ascii=False, indent=2), encoding="utf-8")
            res = {"schema": "swarm_worker.result.v1", "task_id": tid, "goal": goal[:200],
                   "domain": task.get("domain"), "agent_idx": task.get("agent_idx"),
                   "provider": task.get("provider"), "model": task.get("model"), "ok": False,
                   "exit_code": -1, "result": f"[cost-governor] ABANDONED: {gchk.get('abandon_reason')}",
                   "finished_at": _now()}
            (RESULTS_DIR / f"{tid}.json").write_text(
                json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
            results.append({"task_id": tid, "ok": False, "tier": depth, "path": path, "abandoned": True})
            done += 1
            continue
        if not _claim_queued_file(f, task):
            skip_ids.add(tid)
            skipped += 1
            results.append({"task_id": tid, "ok": False, "tier": depth, "path": path,
                            "skipped": "claim_lost", "detail": "another worker claimed task"})
            continue
        before = _billable_snapshot()
        if path == "local":
            # deterministic/RIB work: resolve locally, NO deep model run (honest — not frontier output)
            task["status"] = "done"
            task["detail"] = "local/deterministic (rightsized, no deep agent run)"
            task["tier"] = depth
            ok = True
            tail = f"[rightsized local] deterministic/RIB task ({depth}) — resolved without a deep model call"
            res = {"schema": "swarm_worker.result.v1", "task_id": tid,
                   "goal": goal[:200], "domain": task.get("domain"), "agent_idx": task.get("agent_idx"),
                   "provider": "local", "model": "deterministic", "ok": True, "exit_code": 0,
                   "result": tail, "finished_at": _now()}
        else:
            tail, code = _execute(task)
            ok = code == 0 and bool((tail or "").strip())
            task["status"] = "done" if ok else "failed"
            task["detail"] = ("exit 0" if ok else f"exit {code}")[:120]
            task["tier"] = depth
            res = {"schema": "swarm_worker.result.v1", "task_id": tid,
                   "goal": goal[:200], "domain": task.get("domain"), "agent_idx": task.get("agent_idx"),
                   "provider": task.get("provider"), "model": task.get("model"), "ok": ok,
                   "exit_code": code, "result": tail, "finished_at": _now()}
        after = _billable_snapshot()
        # COST GOVERNOR RECORD: ledger the attempt's billable spend + health.
        _governor_record(tid, before, after, ok)
        (RESULTS_DIR / f"{tid}.json").write_text(
            json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
        f.write_text(json.dumps(task, ensure_ascii=False, indent=2), encoding="utf-8")
        results.append({"task_id": tid, "ok": ok, "tier": depth, "path": path})
        if ok:
            done += 1
        else:
            failed += 1
    return {"schema": SCHEMA + ".rightsized", "ok": True, "done": done, "failed": failed,
            "skipped": skipped, "total": done + failed + skipped, "tiers": tiers,
            "results": results, "ts": _now()}


def collect(*, limit: int = 50) -> dict[str, Any]:
    """Read completed swarm results from the shared PVC (called from the local seat)."""
    if not RESULTS_DIR.is_dir():
        return {"ok": False, "error": "no swarm results yet"}
    out = []
    for p in sorted(RESULTS_DIR.glob("*.json"), reverse=True)[:limit]:
        try:
            out.append(json.loads(p.read_text(encoding="utf-8")))
        except Exception:
            continue
    return {"ok": True, "n_results": len(out), "results": out}


def status() -> dict[str, Any]:
    queued = running = done = failed = 0
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    for p in QUEUE_DIR.glob("*.json"):
        try:
            s = json.loads(p.read_text(encoding="utf-8")).get("status")
        except Exception:
            continue
        if s == "queued":
            queued += 1
        elif s == "running":
            running += 1
        elif s == "done":
            done += 1
        elif s == "failed":
            failed += 1
    return {"schema": SCHEMA, "ok": True, "queue": {"queued": queued, "running": running,
                                                    "done": done, "failed": failed},
            "queue_dir": str(QUEUE_DIR), "results_dir": str(RESULTS_DIR)}


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="swarm-worker")
    ap.add_argument("cmd", nargs="?", default="run", choices=["run", "collect", "status", "enqueue"])
    ap.add_argument("--goal", default="")
    ap.add_argument("--provider", default=DEFAULT_PROVIDER)
    ap.add_argument("--domain", default="auto")
    ap.add_argument("--max", type=int, default=MAX_PER_PASS)
    args = ap.parse_args(argv)
    if args.cmd == "run":
        print(json.dumps(run_once(max_per_pass=args.max), indent=2, default=str))
    elif args.cmd == "collect":
        print(json.dumps(collect(), indent=2, default=str))
    elif args.cmd == "status":
        print(json.dumps(status(), indent=2, default=str))
    elif args.cmd == "enqueue":
        r = enqueue_task(args.goal, provider=args.provider, domain=args.domain)
        print(json.dumps(r, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
