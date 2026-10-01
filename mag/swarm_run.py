"""swarm_run — autonomous swarm runner: run the k8s swarm N cycles, bridge results back, fold.

Operator (2026-08-10): "troubleshoot rightsize it until it runs 3 times and you produce
meaningful results full autonomy."

This is the deterministic autonomous loop for the cluster swarm (the execution path that holds the
API key):
  * run_cycle(n)  -> trigger a mag-swarm manual job, poll until it completes, bridge the results
                     from the PVC back to the local seat, report ok/failed.
  * run_three()   -> 3 full cycles, then FOLD the meaningful results: roshomon.compare() ->
                     attractor_tools (strongest attractors -> memlang chords -> swarm tools ->
                     self-knowledge). The frontier witnesses become durable doctrine.

Right-sizing: the swarm drains MAX_PER_PASS agents per cycle; each cycle is a fresh stateless job.
No local DeepSeek key needed (the in-cluster pod maps the secret key). Deterministic, $0 to
orchestrate (the agent calls are the intended swarm work).

Schema: swarm_run.v1 · CLI: python -m mag.swarm_run once|three
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
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

SCHEMA = "swarm_run.v1"
KUBECTL = (r"C:\Users\foste\AppData\Local\Programs\DockerDesktop\resources\bin\kubectl.exe",)
NS = "mag"
JOB = "mag-swarm-manual"
CRONJOB = "mag-swarm"
MAX_PER_CYCLE_S = 900  # 15 min ceiling per cycle (8 agents)
POLL_S = 20


def _kub(args: list[str], timeout: int = 90) -> subprocess.CompletedProcess:
    return subprocess.run([KUBECTL[0], *args], capture_output=True, text=True, timeout=timeout,
                          cwd=str(ROOT))


def _pod_name() -> str:
    r = _kub(["get", "pods", "-n", NS, "-l", "app=mag", "-o", "jsonpath={.items[0].metadata.name}"])
    return (r.stdout or "").strip() or "mag-6c5b869b96-gb897"


def _job_done() -> tuple[bool, str]:
    r = _kub(["get", "job", JOB, "-n", NS, "-o", "jsonpath={.status.conditions[?(@.type=='Complete')].status}"])
    if (r.stdout or "").strip() == "True":
        return True, "complete"
    r2 = _kub(["get", "job", JOB, "-n", NS, "-o", "jsonpath={.status.failed}"])
    if (r2.stdout or "").strip().isdigit() and int((r2.stdout or "").strip()) > 0:
        return True, "failed"
    return False, "running"


def run_cycle(cycle: int) -> dict[str, Any]:
    """One full cycle: trigger the swarm job, wait, bridge results back, report."""
    _kub(["delete", "job", JOB, "-n", NS, "--ignore-not-found"])
    cr = _kub(["create", "job", f"--from=cronjob/{CRONJOB}", JOB, "-n", NS])
    if cr.returncode != 0:
        return {"ok": False, "schema": SCHEMA, "cycle": cycle, "error": (cr.stderr or "").strip()[:200]}
    t0 = time.time()
    while time.time() - t0 < MAX_PER_CYCLE_S:
        done, status = _job_done()
        if done:
            break
        time.sleep(POLL_S)
    else:
        done, status = False, "timeout"
    # bridge results back (PVC -> local), using a relative local dest (Windows drive-colon fix)
    pod = _pod_name()
    inc = "memory/runs/swarm_worker/results_incoming"
    _kub(["cp", "-n", NS, f"{NS}/{pod}:/app/memory/runs/swarm_worker/results/.", inc], timeout=120)
    merged = 0
    inc_dir = ROOT / inc
    res_dir = ROOT / "memory" / "runs" / "swarm_worker" / "results"
    res_dir.mkdir(parents=True, exist_ok=True)
    if inc_dir.is_dir():
        for f in inc_dir.rglob("*.json"):
            try:
                import shutil
                shutil.copy(f, res_dir / f.name)
                merged += 1
            except OSError:
                pass
    # count ok results
    ok = 0
    for f in res_dir.glob("*.json"):
        try:
            if json.loads(f.read_text(encoding="utf-8")).get("ok"):
                ok += 1
            else:
                f.unlink()
        except Exception:
            pass
    return {"ok": done, "schema": SCHEMA, "cycle": cycle, "job_status": status,
            "results_merged": merged, "local_ok_results": ok}


def run_three(*, cycles: int = 3, fold: bool = True) -> dict[str, Any]:
    """Run N cycles then fold the meaningful results into doctrine (Roshomon + attractor tools)."""
    out = {"schema": SCHEMA, "cycles": []}
    for c in range(1, cycles + 1):
        r = run_cycle(c)
        out["cycles"].append(r)
        print(f"[swarm_run] cycle {c}: {r}", flush=True)
    if fold:
        try:
            from mag import roshomon as rh
            cmp = rh.compare()
            out["roshomon_core_total"] = cmp.get("roshomon_core_total")
            print(f"[swarm_run] roshomon core: {cmp.get('roshomon_core_total')}", flush=True)
        except Exception as e:
            out["roshomon_error"] = str(e)[:120]
        try:
            from mag import attractor_tools as at
            a = at.run()
            out["attractor"] = {"n": a.get("attractors"), "swarm_tools": a.get("swarm_tools"),
                                "folded": a.get("folded"), "batch": a.get("batch")}
            print(f"[swarm_run] attractor fold: {a.get('folded')} nodes", flush=True)
        except Exception as e:
            out["attractor_error"] = str(e)[:120]
    out["ok"] = True
    return out


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="swarm-run")
    ap.add_argument("cmd", nargs="?", default="once", choices=["once", "three"])
    ap.add_argument("--cycles", type=int, default=3)
    ap.add_argument("--nofold", action="store_true")
    args = ap.parse_args(argv)
    if args.cmd == "once":
        print(json.dumps(run_cycle(1), indent=2))
    else:
        print(json.dumps(run_three(cycles=args.cycles, fold=not args.nofold), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
