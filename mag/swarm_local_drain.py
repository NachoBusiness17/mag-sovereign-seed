"""swarm_local_drain — THE FIX for the dead-end architecture path. A LOCAL drainer for the swarm
queue, because the k8s CronJob that was its ONLY drainer has never run on this Windows host.

OPERATOR (2026-08-13): "anything found blocking key infrastructure that you assume to work but does
not... these loops need to be intelligent and evolve. you have so much data on me interrupting you
that has to be worth something and is training data. everything is training data. especially key
infrastructure blocks."

ROOT CAUSE (grounded, deep investigation 2026-08-13): the swarm queue (memory/runs/swarm_worker/queue)
is FILLED locally but DRAINED ONLY by the k8s mag-swarm CronJob — which has NEVER run on this Windows
host (Docker/K8s not installed; no kubectl/kind execution record anywhere; docker became unreachable
08-09). So every "enqueue to the swarm" wrote a file nobody executes -> 734-task all-"queued" backlog,
zero drain since 08-10. THE RECURRING "wrong tool / route through the swarm" CORRECTION IS THE SYMPTOM
OF THIS: the sanctioned execution path enqueues-but-never-executes on this host, so work piles up or I
fall back to terminal/one-shots. The interruptions were training data that named the infra block.

THE FIX (self-steal, correct internal mechanism): invoke the SAME rightsized swarm_worker drain logic
LOCALLY on the governor cadence — no k8s needed. Reconcile any available key for reporting, but do
not make a DeepSeek key a global prerequisite: local/free lanes must still drain when DeepSeek is
unavailable. This turns enqueue -> execute without forcing every task through the paid brake.

SECONDARY KEY MISMATCH (still reported): providers.yaml reads DEEPSEEK_SWARM_API_KEY; local .env sets
only DEEPSEEK_API_KEY. key_reconcile() can alias the present key for DeepSeek tasks, but it does not
block local/free work when that key is absent.

Schema: swarm_local_drain.v1 · deterministic coordinator + bounded swarm work · reuse: swarm_worker
"""
from __future__ import annotations

import json
import os
import sys
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

SCHEMA = "swarm_local_drain.v1"
OUT = ROOT / "memory" / "runs" / "swarm_local_drain"

# The provider config reads this env var for deepseek (per providers.yaml, 2026-08-10).
PROVIDER_KEY_ENV = "DEEPSEEK_SWARM_API_KEY"
# The key the local .env actually sets.
LOCAL_KEY_ENV = "DEEPSEEK_API_KEY"

# Bounded by default: how many swarm tasks the LOCAL drainer may run per beat. Never a runaway —
# the cluster was never here, so the local drain is the fallback and must stay controlled.
DEFAULT_PER_BEAT = 2
# Daily cap: how many total swarm tasks the local drainer may run in a day (budget guard).
DEFAULT_DAILY_CAP = 20


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def key_reconcile() -> dict[str, Any]:
    """Reconcile the key env: the provider reads PROVIDER_KEY_ENV, but the local .env sets
    LOCAL_KEY_ENV. Load .env + read the key straight from the file (the saelis_seat proven pattern)
    and point the provider's env var at the available one (in-process) so deepseek resolves.
    Logs the KEY NAME only, never the value. Honest about what resolves.
    SELF-STEAL (2026-08-16): this was a weaker reinvention of mag/saelis_seat.py's resolution —
    it only aliased from PROCESS env, so if .env wasn't loaded the key was absent and it returned
    False (queue never drained, 0 drain-ledger files). Reuse the proven pattern: load .env, read
    from file, then alias."""
    # 1) load .env into process env (the loop's kernel may not have it)
    try:
        from dotenv import load_dotenv
        load_dotenv(str(ROOT / ".env"))
    except Exception:
        pass
    # 2) if the provider key is still absent, read the local key straight from the .env FILE
    if not os.environ.get(PROVIDER_KEY_ENV):
        try:
            env_file = ROOT / ".env"
            if env_file.is_file():
                import re as _re
                _m = _re.search(r"^\s*" + LOCAL_KEY_ENV + r"\s*=\s*(.+?)\s*$",
                                env_file.read_text(encoding="utf-8", errors="replace"),
                                _re.MULTILINE)
                if _m:
                    os.environ[PROVIDER_KEY_ENV] = _m.group(1).strip().strip('"').strip("'")
        except Exception:
            pass
    # 3) alias process-env local key into the provider var if present
    if not os.environ.get(PROVIDER_KEY_ENV) and os.environ.get(LOCAL_KEY_ENV):
        os.environ[PROVIDER_KEY_ENV] = os.environ[LOCAL_KEY_ENV]
    resolved = bool(os.environ.get(PROVIDER_KEY_ENV))
    return {"ok": True, "schema": SCHEMA, "action": "loaded-dotenv-and-aliased",
            "resolved_provider_key": resolved,
            "note": f"provider reads {PROVIDER_KEY_ENV}; resolved={resolved} (key VALUE never logged)"}


def unorphan_stale(*, ttl_minutes: int = 30) -> dict[str, Any]:
    """SELF-HEAL (2026-08-25): reset tasks stuck in 'running' past a TTL back to 'queued'.

    The failure mode this fixes: a consumer dies mid-task (or hangs past any sane timeout)
    and the task file is left 'running' forever — _next_task skips non-queued tasks, so an
    orphan blocks nothing alphabetically but permanently loses the task AND inflates the
    running count (the double-consumer confusion). Longest known single-call timeout is ox
    at 540s (9 min); a 30-min TTL is safely past any legitimate run.
    """
    from datetime import datetime, timezone
    from pathlib import Path
    from mag import swarm_worker as sw
    qdir = Path(sw.QUEUE_DIR)
    now = datetime.now(timezone.utc)
    reset = []
    for p in sorted(qdir.glob("sw-*.json")):
        try:
            t = json.loads(p.read_text(encoding="utf-8", errors="replace"))
        except Exception:  # noqa: BLE001
            continue
        if t.get("status") != "running":
            continue
        # age from started_at (when this consumer began the run); fall back to created_at
        mark = str(t.get("started_at") or t.get("created_at") or "")
        try:
            started = datetime.fromisoformat(mark.replace("Z", "+00:00"))
        except Exception:  # noqa: BLE001
            continue
        age_min = (now - started).total_seconds() / 60
        if age_min >= ttl_minutes:
            t["status"] = "queued"
            t["_unorphaned"] = f"reset from stale running ({int(age_min)}m old)"
            p.write_text(json.dumps(t, ensure_ascii=False, indent=2), encoding="utf-8")
            reset.append(str(t.get("task_id")))
    return {"ok": True, "schema": SCHEMA, "action": "unorphan_stale",
            "ttl_minutes": ttl_minutes, "reset": reset}


def drain_pass(*, limit: int = DEFAULT_PER_BEAT) -> dict[str, Any]:
    """Run the EXISTING swarm_worker.run_once() LOCALLY (bounded), with the key reconciled, so the
    queue actually drains on this host. Self-steal: the drain logic already exists; we just invoke
    it here because the k8s CronJob (its only other caller) never runs on Windows.

    Runs the stale-running sweep FIRST (self-heal) so orphans don't clog the pass.
    """
    try:
        unorphan_stale()
    except Exception:  # noqa: BLE001
        pass
    kr = key_reconcile()
    try:
        from mag import swarm_worker
        # Rightsized drain is bounded internally and sends deterministic/local
        # work to the cheap path before asking any remote provider.
        ran = swarm_worker.run_rightsized_once(max_per_pass=max(1, int(limit)))
    except Exception as e:
        return {"ok": False, "schema": SCHEMA, "error": str(e)[:160], "key_reconcile": kr}
    done = int((ran or {}).get("done") or 0)
    failed = int((ran or {}).get("failed") or 0)
    return {"ok": True, "schema": SCHEMA, "ts": _now(), "ran": ran,
            "done": done, "failed": failed, "key_reconcile": kr,
            "note": "local swarm drain: same swarm_worker rightsized mechanism, invoked locally because "
                    "the k8s CronJob drainer never runs on Windows"}


def _today_drained() -> int:
    """Grounded: count today's local drain runs from the persisted ledger (budget guard)."""
    if not OUT.is_dir():
        return 0
    today = _now()[:10]
    n = 0
    for p in OUT.glob("drain-*.json"):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            if str(d.get("ts", ""))[:10] == today:
                n += int(d.get("done") or 0) + int(d.get("failed") or 0)
        except Exception:
            continue
    return n


def run_cadence(*, per_beat: int = DEFAULT_PER_BEAT, daily_cap: int = DEFAULT_DAILY_CAP,
                persist: bool = True) -> dict[str, Any]:
    """The loop's self-healing drain beat: bounded, budget-guarded, key-reconciled. Drains a small
    number of queued swarm tasks per beat locally so the sanctioned path actually executes."""
    # STANDING BACKUP (2026-08-25, sacred-cow fix): the chain is gitignored for opsec, so it needs
    # its own backup path. Once per day, under the verkle lock (the script guards same-day dupes).
    # Failure is non-fatal — the drain beats on regardless.
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "backup_chain", ROOT / "scripts" / "backup_chain.py")
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        m.backup()
    except Exception:  # noqa: BLE001
        pass
    used = _today_drained()
    remaining = max(0, int(daily_cap) - used)
    if remaining <= 0:
        return {"ok": True, "schema": SCHEMA, "skipped": "daily-cap", "daily_cap": daily_cap,
                "used_today": used}
    limit = max(1, min(int(per_beat), remaining))
    r = drain_pass(limit=limit)
    if persist and r.get("ok"):
        try:
            OUT.mkdir(parents=True, exist_ok=True)
            (OUT / f"drain-{_now().replace(':','').replace('-','')[:14]}.json").write_text(
                json.dumps(r, indent=2, default=str), encoding="utf-8")
        except Exception:
            pass
    r["used_today"] = used + (int(r.get("done") or 0) + int(r.get("failed") or 0) if r.get("ok") else 0)
    return r


def status() -> dict[str, Any]:
    return {"ok": True, "schema": SCHEMA,
            "contract": "key_reconcile()->alias the present deepseek key into the provider env (name "
                        "only, never value); drain_pass(limit)->run swarm_worker.run_once locally "
                        "(bounded, headless) after a stale-running sweep; unorphan_stale()->reset "
                        "running tasks past TTL back to queued (self-heal); run_cadence()->bounded + "
                        "daily-capped self-healing drain beat; status()->this",
            "cost": "deterministic coordinator + bounded swarm work (spawned agents are the real "
                    "deepseek spend; capped by default)",
            "reuses": ["swarm_worker"], "fixes": ["dead k8s CronJob drain", "key env mismatch",
                                                "stuck running tasks (orphans)"]}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="swarm-local-drain")
    ap.add_argument("cmd", nargs="?", default="status",
                    choices=["status", "key", "drain", "cadence", "unorphan"])
    ap.add_argument("--limit", type=int, default=DEFAULT_PER_BEAT)
    a = ap.parse_args()
    if a.cmd == "key":
        print(json.dumps(key_reconcile(), indent=2, default=str))
    elif a.cmd == "drain":
        print(json.dumps(drain_pass(limit=a.limit), indent=2, default=str))
    elif a.cmd == "cadence":
        print(json.dumps(run_cadence(per_beat=a.limit), indent=2, default=str))
    elif a.cmd == "unorphan":
        print(json.dumps(unorphan_stale(), indent=2, default=str))
    else:
        print(json.dumps(status(), indent=2, default=str))
