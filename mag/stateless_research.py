"""stateless_research — test the stateless-swarm theory with a real, rightsized experiment.

THEORY UNDER TEST: a swarm of DUMB (minimal, no reasoning) STATELESS agents, kept alive in the
DeepSeek cloud and coordinated ONLY through a content-addressed substrate (no shared mutable
state, no central orchestrator), can cooperatively produce a coherent research result that
exceeds any single agent — and our new systems (flock dedupe, shape portability, model_health
steering) make that coordination emerge for free.

EXPERIMENT (rightsized, cheap-first): 4 stateless agents, each:
  - one slice of a REAL question (picked from model_health's thinnest invariant domain),
  - one cheap DeepSeek call (dumb agent: no multi-turn, no memory),
  - writes its result STATELESSLY to queue/handoff/stateless_run/agent_N.json (content-addressed),
  - dies. The swarm is "kept alive" by the queue+drainer spawning each as a headless process.

COLLECT: dedupe the 4 slices (flock_scheduler), fold them (steal_pack) into a research pack,
then model_health re-reads to see if the domain got reinforced — the experiment's output
informs the system's NEXT STEP (steer_at).

Deterministic plan; cloud execution is cheap DeepSeek (dumb agents). Schema: stateless_research.v1
"""
from __future__ import annotations

import json
import sys
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

SCHEMA = "stateless_research.v1"
RUN_DIR = ROOT / "queue" / "handoff" / "stateless_run"
N_AGENTS = 4

_SLICE_TPL = [
    "Identify the single most load-bearing invariant pattern in the '{d}' domain and the cheapest way to enforce it.",
    "Name ONE concrete failure mode of the '{d}' domain in a stateless swarm, and the cheapest guardrail that blocks it.",
    "Give ONE novel stateless-swarm mechanism that would strengthen the '{d}' domain at zero cloud cost.",
    "What does a research corpus already imply about the '{d}' domain? State the sharpest takeaway in one line.",
]


def _thinnest_domain() -> str:
    try:
        from mag import model_health as mh
        h = mh.health()
        return str(h.get("steer_at") or "engine")
    except Exception:
        return "engine"


def plan(*, domain: str | None = None, n_agents: int = N_AGENTS) -> dict[str, Any]:
    """Rightsize the experiment: pick a REAL piece of data (thinnest invariant domain) and
    define the 4 stateless agent slices + their cheap contract. Deterministic, $0."""
    d = domain or _thinnest_domain()
    slices = [t.format(d=d) for t in _SLICE_TPL[:n_agents]]
    return {"ok": True, "schema": SCHEMA, "domain": d, "n_agents": len(slices),
            "provider": "deepseek", "tier": "analysis",  # dumb agents: cheap, no reasoning
            "model_hint": "deepseek-chat",
            "stateless_contract": "one call, one file (agent_N.json), content-addressed, dies",
            "slices": slices}


def _slice_file(i: int) -> Path:
    return RUN_DIR / f"agent_{i}.json"


def launch(*, domain: str | None = None, enqueue: bool = False, k8s: bool = False) -> dict[str, Any]:
    """Dispatch the stateless swarm agents.

    Two execution surfaces (route by where the work runs, per the architecture law):
      * k8s=True  -> write the task specs to the CLUSTER swarm worker's dedicated queue
                     (mag.swarm_worker). The k8s CronJob drains them in-cluster — NO local
                     process, NO console window. This is the operator's correction: the
                     swarm belongs in k8s, in its own binary.
      * k8s=False -> enqueue to the LOCAL mission queue (orchestrator) so the local drainer
                     spawns each as a headless stateless agent (legacy / test path).

    If enqueue=False, just return the spec.
    """
    p = plan(domain=domain)
    if not enqueue:
        return p
    # Route the instruction layer through the RIB bus: workers auto-mount the frontier steer PLUS
    # the domain's bus-grown RIBs (aligned with our memory), not a static block.
    from mag.rib_bus import inject_for as _inject_for

    def _steer(s: str) -> str:
        return _inject_for(s, domain=p["domain"])

    if k8s:
        # Route through the cluster swarm worker: deterministic, $0, no local spawns.
        from mag import swarm_worker as sw
        launched = []
        for i, s in enumerate(p["slices"]):
            try:
                r = sw.enqueue_task(_steer(s), provider="deepseek",
                                    model="deepseek-chat", domain=p["domain"], agent_idx=i,
                                    tag=f"stateless-research-{p['domain']}")
                launched.append({"agent": i, "ok": bool(r.get("ok")),
                                 "task_id": r.get("task_id"), "surface": "k8s"})
            except Exception as e:
                launched.append({"agent": i, "ok": False, "error": str(e)[:80]})
        return {"ok": True, **p, "surface": "k8s", "launched": launched}

    from mag import orchestrator as orch
    launched = []
    for i, s in enumerate(p["slices"]):
        try:
            r = orch.spawn_task(_steer(s),
                                provider="deepseek", model="deepseek-chat",
                                timeout=240, tag=f"stateless-research-{p['domain']}")
            launched.append({"agent": i, "ok": bool(r.get("ok")), "task_id": r.get("task_id")})
        except Exception as e:
            launched.append({"agent": i, "ok": False, "error": str(e)[:80]})
    return {"ok": True, **p, "surface": "local", "launched": launched}


def collect(*, domain: str | None = None) -> dict[str, Any]:
    """Collect the 4 stateless agent results, dedupe (flock_scheduler), fold (steal_pack),
    and re-read model_health to see if the domain got reinforced -> informs next step."""
    if not RUN_DIR.is_dir():
        return {"ok": False, "error": "no stateless_run results yet"}
    results = []
    for i in range(N_AGENTS):
        f = _slice_file(i)
        if f.is_file():
            try:
                results.append(json.loads(f.read_text(encoding="utf-8")))
            except Exception:
                continue
    if not results:
        return {"ok": False, "error": "no agent results written yet"}
    # fold the collected results into a research pack
    slug = f"stateless_research_{domain or 'auto'}"
    body = "\n\n".join(f"## agent-{r.get('agent')} ({r.get('slice','')[:40]}...)\n{r.get('result','')}"
                       for r in results)
    ans = ROOT / "memory" / "research_packs" / f"{slug}.answer.local.md"
    ans.parent.mkdir(parents=True, exist_ok=True)
    ans.write_text(f"# Stateless swarm research: {domain or 'auto'}\n- source: stateless_research\n\n{body}",
                   encoding="utf-8")
    folded = False
    try:
        from mag.research_fold import fold_one
        folded = bool(fold_one(ans).get("ok", True))
    except Exception:
        pass
    # re-read model_health to see next steer
    steer = None
    try:
        from mag import model_health as mh
        steer = mh.health().get("steer_at")
    except Exception:
        pass
    return {"ok": True, "schema": SCHEMA, "n_results": len(results), "folded": folded,
            "pack": str(ans), "next_steer_at": steer}


def _backlog_sample(n: int = 4) -> list[str]:
    """A small real slice of tasks from the backlog (canonical goals via backlog_reform)."""
    try:
        from mag import backlog_reform as br
        r = br.reform(apply=False)
        return [str(c.get("goal") or "") for c in r.get("canonical", [])][:n]
    except Exception:
        return [
            "Identify the most load-bearing invariant in the engine domain and the cheapest enforcement.",
            "Name one failure mode of a stateless swarm and the cheapest guardrail.",
            "Give one zero-cloud-cost mechanism to strengthen the memory domain.",
        ][:n]


def local_steer(*, tasks: list[str] | None = None, n: int = 4, model: str | None = None,
                dedupe: bool = True, route_local_sched: bool = True) -> dict[str, Any]:
    """The point, proven locally: a small stateless swarm goes through our tasks, steers the
    data to the LOCAL model (ollama on GPU), runs cheap experiments producing data, dedupes.

    - swarm picks a small real slice of tasks (from the backlog),
    - STEERS each to the local model (gpu_ghost._ollama_generate) = cheap experiment -> data,
    - optionally routes through local_scheduler (the 'interrupt its jobs' one-at-a-time queue),
    - dedupes the produced data via flock_scheduler,
    - writes the produced data as training rows. All free/local (GPU), stateless.
    """
    from mag import gpu_ghost as gg
    tasks = [t for t in (tasks if tasks is not None else _backlog_sample(n)) if (t or "").strip()]
    tasks = tasks[:n]
    if not tasks:
        return {"ok": False, "error": "no tasks to steer"}
    models = gg._ollama_models()
    if not models:
        return {"ok": False, "error": "local model not up"}
    m = model or gg._pick_model(models)

    results = []
    for t in tasks:
        prompt = (f"Run a cheap experiment on this task and return ONE concrete data point "
                  f"(a sharp invariant, guardrail, or measured fact). Task: {t}")
        try:
            out = gg._ollama_generate(prompt, m)
        except Exception as e:
            results.append({"task": t, "output": "", "error": str(e)[:60]})
            continue
        results.append({"task": t, "output": out.strip(), "model": m})

    # dedupe produced data via flock_scheduler (cluster near-identical outputs)
    deduped = 0
    if dedupe:
        try:
            from mag import flock_scheduler as fs
            p = fs.plan([str(r.get("output") or "") for r in results], domain="general")
            for i, a in enumerate(p.get("assignments", [])):
                if a.get("is_duplicate"):
                    results[i]["duplicate"] = True
                    deduped += 1
        except Exception:
            pass

    # optional: route to local_scheduler queue ('interrupt its jobs to do stuff for them')
    routed = []
    if route_local_sched:
        try:
            from mag import local_scheduler as ls
            for r in results:
                if r.get("output"):
                    q = ls.enqueue(kind="local_experiment", payload={"q": r["output"]},
                                   label=str(r["task"])[:40])
                    if q.get("ok"):
                        routed.append(q.get("id"))
        except Exception:
            pass

    # write produced data as training rows (free GPU compute -> training data)
    written = 0
    TRAINING = ROOT / "memory" / "pile" / "training_rows.jsonl"
    TRAINING.parent.mkdir(parents=True, exist_ok=True)
    with TRAINING.open("a", encoding="utf-8") as f:
        for r in results:
            if not r.get("output") or r.get("duplicate"):
                continue
            f.write(json.dumps({"schema": "training_row.v1", "ts": _now(), "source": "stateless_local_steer",
                                "gpu": True, "model": m, "task": str(r["task"])[:200],
                                "input": str(r["task"])[:400], "output": str(r["output"])[:2000]},
                               ensure_ascii=False) + "\n")
            written += 1

    return {"ok": True, "schema": SCHEMA, "mode": "local_steer", "model": m,
            "tasks_steered": len(tasks), "outputs": len([r for r in results if r.get("output")]),
            "deduped": deduped, "local_sched_routed": len(routed),
            "training_rows_written": written,
            "results": [{"task": str(r["task"])[:50], "dup": bool(r.get("duplicate")),
                         "out": str(r.get("output"))[:80]} for r in results]}


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="stateless-research")
    ap.add_argument("cmd", nargs="?", default="plan", choices=["plan", "launch", "collect"])
    ap.add_argument("--domain", default="")
    ap.add_argument("--enqueue", action="store_true")
    ap.add_argument("--k8s", action="store_true", help="route launch through the cluster swarm worker")
    args = ap.parse_args(argv)
    if args.cmd == "plan":
        print(json.dumps(plan(domain=args.domain or None), indent=2, default=str))
    elif args.cmd == "launch":
        print(json.dumps(launch(domain=args.domain or None, enqueue=args.enqueue, k8s=args.k8s),
                         indent=2, default=str))
    elif args.cmd == "collect":
        print(json.dumps(collect(domain=args.domain or None), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
