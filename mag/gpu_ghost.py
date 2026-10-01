"""gpu_ghost — the ghost's GPU-aware arm: partition the backlog into FREE-LOCAL-GPU vs CLOUD.

Creative reframe of the 87-task backlog (2026-08-09): not all of it belongs in the cloud queue.
The machine has a local GPU (AMD ROCm / NVIDIA), the ghost already reads its telemetry, and
local_scheduler runs ONE local-GPU job at a time via local ollama models (free, no API spend).
So instead of draining 87 serially to cloud, the GPU GHOST:

  1. READS the GPU (rocm-smi/nvidia) — is it free, how hot, how loaded?
  2. DEDUPES + right-tiers the backlog via flock_scheduler/one_sizer (the new alloc stack).
  3. PARTITIONS canonical tasks: LOCAL-GPU-eligible (cheap, local-capable) vs CLOUD-required.
  4. When the GPU is free (vram/util low), dispatches the local batch to local_scheduler.enqueue
     (free local execution); cloud tasks keep their right-tier in the orchestrator queue.

Deterministic + $0. Schema: gpu_ghost.v1
"""
from __future__ import annotations

import json
import shutil
import subprocess
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

SCHEMA = "gpu_ghost.v1"


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

# Cloud-only markers: these explicitly need a frontier/cloud model, never local GPU.
_CLOUD_MARK = ("grok", "frontier", "deep research", "deep-research", "deepseek", "openai",
               "claude", "distill", "pre-scope", "elevation", "escalation", "billing")


def _nvidia_smi() -> str | None:
    """Resolve nvidia-smi even when it's NOT on PATH (Task Manager sees the GPU, but the CLI tool
    may only live in its install dir). Checks PATH first, then the standard Windows install paths.
    Operator (2026-08-12): 'gpu is reachable via performance tab in task manager' — the hardware is
    there; the blindness was a PATH issue, not hardware absence."""
    import shutil
    cand = shutil.which("nvidia-smi")
    if cand:
        return cand
    for p in (
        r"C:\Windows\System32\nvidia-smi.exe",
        r"C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe",
        r"C:\Program Files\NVIDIA Corporation\nvidia-smi.exe",
    ):
        if Path(p).is_file():
            return p
    return None


def _amd_windows() -> dict[str, Any]:
    """Probe an AMD GPU on WINDOWS via WMI/CIM + the GPU performance counter. rocm-smi is a
    Linux/ROCm tool (absent on Windows) and nvidia-smi is the wrong vendor for an AMD card — so
    this is the correct Windows-AMD path. Resolves the card NAME + total VRAM (AdapterRAM) +
    utilization (perf counter). Operator (2026-08-12): 'it's amd' — the blindness was the wrong
    probe, not missing hardware."""
    out: dict[str, Any] = {}
    ps = (
        r"$v = Get-CimInstance Win32_VideoController | Where-Object { $_.Name -match 'AMD|Radeon|RX' }"
        r" | Select-Object -First 1; "
        r"if ($v) { "
        r"$c = Get-Counter '\GPU Engine(*)\Utilization Percentage' -ErrorAction SilentlyContinue | "
        r"Select-Object -ExpandProperty CounterSamples | Measure-Object -Property CookedValue -Average; "
        r"[PSCustomObject]@{ name=$v.Name; vram=$v.AdapterRAM; "
        r"util=if($c -and $c.Average -ne $null){[math]::Round($c.Average,1)}else{0} } "
        r"| ConvertTo-Json -Compress }"
    )
    try:
        # B2-85 2026-09-26: bare "powershell" is not on PATH in every launch
        # context (sig run_shell:e566037def80 "[Errno 2] ... powershell",
        # 7,964 FKB rows since 2026-09-19). Resolve the full path; System32
        # fallback when PATH lookup misses (pattern mag/process_reaper.py).
        ps_exe = shutil.which("powershell") or shutil.which("powershell.exe")
        if not ps_exe and sys.platform == "win32":
            ps_exe = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
        if not ps_exe:
            return out
        r = subprocess.run([ps_exe, "-NoProfile", "-Command", ps],
                           capture_output=True, text=True, timeout=12)
        if r.returncode == 0 and r.stdout.strip():
            d = json.loads(r.stdout.strip())
            if d.get("name"):
                out = {"name": d.get("name", ""), "vram_bytes": int(d.get("vram") or 0),
                       "util_pct": float(d.get("util") or 0), "source": "amd-cim"}
    except Exception:
        pass
    return out


def gpu_status() -> dict[str, Any]:
    """Read the local GPU (AMD ROCm -> AMD Windows/CIM -> NVIDIA fallback) — the ghost's telemetry.
    Operator (2026-08-12): the card is AMD, so the Windows-AMD path (WMI/CIM + perf counter) is
    the correct resolver, not nvidia-smi."""
    out = {"vram_used_pct": None, "temp_c": None, "util_pct": None, "source": "none", "free": None,
           "name": None, "vram_bytes": None}
    try:
        r = subprocess.run(["rocm-smi", "--showmeminfo", "vram", "--showuse", "--showtemp", "--json"],
                           capture_output=True, text=True, timeout=8)
        if r.returncode == 0 and r.stdout.strip():
            cards = json.loads(r.stdout)
            c = list(cards.values())[0] if isinstance(cards, dict) else cards[0]
            used = float(c.get("VRAM", c).get("Used", 0))
            total = float(c.get("VRAM", c).get("Total", 1))
            out.update({"vram_used_pct": round(100.0 * used / max(total, 1), 1),
                        "temp_c": float(c.get("Temperature", -1)),
                        "util_pct": float(c.get("GPU", c).get("Use", 0)), "source": "rocm-smi"})
    except Exception:
        pass
    # Windows-AMD path (the correct resolver for an AMD card on Windows)
    if out["source"] == "none":
        amd = _amd_windows()
        if amd.get("source") == "amd-cim":
            out.update({"name": amd.get("name"), "vram_bytes": amd.get("vram_bytes"),
                        "util_pct": amd.get("util_pct"), "source": "amd-cim"})
    # NVIDIA fallback (only if neither AMD path resolved)
    if out["source"] == "none":
        nv = _nvidia_smi()
        if nv:
            try:
                r = subprocess.run([nv, "--query-gpu=memory.used,memory.total,temperature.gpu,utilization.gpu",
                                    "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=6)
                if r.returncode == 0 and r.stdout.strip():
                    p = r.stdout.strip().split(",")
                    if len(p) >= 4:
                        out.update({"vram_used_pct": round(100.0 * float(p[0]) / max(float(p[1]), 1), 1),
                                    "temp_c": float(p[2]), "util_pct": float(p[3]), "source": "nvidia-smi"})
            except Exception:
                pass
    # K8S/Verkle fallback (2026-08-11, operator): the GPU lives in Kubernetes, so the host is
    # GPU-blind (rocm-smi/nvidia-smi -> source:"none"). Adapt the mem tools to read the folded
    # gpu_telemetry knot/ledger (mag.gpu_k8s) instead of a live local tool.
    if out["source"] == "none":
        try:
            from mag.gpu_k8s import status as gpu_k8s_status
            k = gpu_k8s_status()
            if k.get("source") and k["source"] != "none":
                for kk in ("vram_used_pct", "temp_c", "util_pct", "source", "free"):
                    out[kk] = k.get(kk)
        except Exception:
            pass
    # GPU is "free" for a local job when not heavily loaded (vram or util under 70%).
    if out["vram_used_pct"] is not None or out["util_pct"] is not None:
        v = out["vram_used_pct"] if out["vram_used_pct"] is not None else 0
        u = out["util_pct"] if out["util_pct"] is not None else 0
        out["free"] = bool(v < 70 and u < 70)
    return out


def partition(*, apply_local: bool = False) -> dict[str, Any]:
    """Dedupe + right-tier the backlog, then split into LOCAL-GPU vs CLOUD.

    Returns the partition. If apply_local=True, dispatches the local-eligible batch to
    local_scheduler.enqueue (free GPU execution) — gated on GPU being free.
    """
    from mag import backlog_reform as br
    reform = br.reform(apply=False)
    canonical = reform.get("canonical", [])
    gpu = gpu_status()

    local, cloud = [], []
    for c in canonical:
        goal = str(c.get("goal") or "")
        tier = str(c.get("tier") or "flash")
        learned = bool(c.get("learned_tier"))
        cloudy = any(m in goal.lower() for m in _CLOUD_MARK)
        # local-GPU-eligible: cheap tier + not cloud-marked
        if (not cloudy) and (tier in ("flash", "cheap") or not learned):
            local.append(c)
        else:
            cloud.append(c)

    dispatched = []
    if apply_local and gpu.get("free") and local:
        from mag import local_scheduler as ls
        for c in local[: ls.enqueue_limit() if hasattr(ls, "enqueue_limit") else 8]:
            try:
                r = ls.enqueue(kind="backlog", payload={"goal": str(c.get("goal") or "")},
                               label=str(c.get("queue_id") or "backlog"))
                if r.get("ok"):
                    dispatched.append({"queue_id": c.get("queue_id"), "local_task_id": r.get("id")})
            except Exception:
                continue

    return {"ok": True, "schema": SCHEMA,
            "gpu": gpu,
            "queued_total": reform.get("queued_total"),
            "unique_tasks": reform.get("unique_tasks"),
            "deduped": reform.get("deduped"),
            "tier_distribution": reform.get("tier_distribution"),
            "n_local_gpu": len(local), "n_cloud": len(cloud),
            "local_batch": [{"queue_id": c.get("queue_id"), "goal": str(c.get("goal"))[:70]} for c in local[:20]],
            "cloud_batch": [{"queue_id": c.get("queue_id"), "tier": c.get("tier"),
                             "goal": str(c.get("goal"))[:70]} for c in cloud[:20]],
            "dispatched_local": dispatched}


def _ollama_generate(prompt: str, model: str, base: str = "http://127.0.0.1:11434", timeout: int = 60) -> str:
    import urllib.request
    body = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode()
    req = urllib.request.Request(base + "/api/generate", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read().decode("utf-8"))
    return str(data.get("response") or "")


def _ollama_models(base: str = "http://127.0.0.1:11434") -> list[str]:
    import urllib.request
    try:
        with urllib.request.urlopen(base + "/api/tags", timeout=5) as r:
            return [str(m.get("name") or "") for m in json.loads(r.read().decode("utf-8")).get("models", [])]
    except Exception:
        return []


def _pick_model(models: list[str]) -> str:
    pref = ("qwen", "gemma", "llama", "nomic", "mistral", "phi")
    for p in pref:
        for m in models:
            if p in m.lower():
                return m
    return models[0] if models else ""


def _seed_prompts(n: int = 6) -> list[str]:
    return [
        "Distill one sharp invariant a stateless agent swarm must hold to stay coherent without a central orchestrator.",
        "Name one novel way a content-addressed verkle chain can make a swarm's memory portable and reconstructable anywhere.",
        "Give one concrete tesuji (proven sharp move) for cheap-first frontier routing that costs pennies.",
        "Describe one emergent behavior that appears when many stateless agents steer in a shared field.",
        "Propose one guardrail an autonomous self-training loop must never violate.",
        "Explain how declaring a structure in latent space can specify which data a swarm should collect.",
    ][:n]


def afk_train(*, model: str | None = None, n: int = 6, base: str = "http://127.0.0.1:11434",
              require_free_gpu: bool = True) -> dict[str, Any]:
    """AFK automatic inference training: when operator AFK + GPU free, run LOCAL inference on
    curated seed prompts, write training rows, fold. Free GPU compute -> free training data."""
    try:
        from mag.afk_cadence import _operator_afk
        afk = _operator_afk()
    except Exception:
        afk = True
    if not afk:
        return {"ok": False, "skipped": "operator active (not AFK)"}
    gpu = gpu_status()
    # Only block if the GPU is KNOWN busy; if telemetry is unavailable (None), don't gate —
    # ollama running locally is the real free-compute signal.
    if require_free_gpu and gpu.get("free") is False:
        return {"ok": False, "skipped": "gpu busy", "gpu": gpu}
    models = _ollama_models(base)
    if not models:
        return {"ok": False, "skipped": "ollama not up / no local models", "gpu": gpu}
    m = model or _pick_model(models)
    rows = []
    for s in _seed_prompts(n):
        try:
            out = _ollama_generate(s, m, base)
        except Exception:
            continue
        if not out.strip():
            continue
        rows.append({"schema": "training_row.v1", "ts": _now(), "source": "gpu_afk_train",
                     "gpu": True, "model": m, "input": s, "output": out.strip()[:2000]})
    TRAINING = ROOT / "memory" / "pile" / "training_rows.jsonl"
    TRAINING.parent.mkdir(parents=True, exist_ok=True)
    with TRAINING.open("a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    try:
        from mag import training_events
        training_events.emit("inference_training", input_data={"n": len(rows), "model": m},
                             action={"kind": "gpu_afk_train", "gpu": True},
                             outcome={"rows": len(rows)},
                             pattern_tags=["gpu_afk_train", "inference", "afk"],
                             tier_max="T2", exportable=False)
    except Exception:
        pass
    return {"ok": True, "model": m, "rows": len(rows), "gpu": gpu, "source": "gpu_afk_train"}


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="gpu-ghost")
    ap.add_argument("--apply-local", action="store_true", help="dispatch local-GPU batch when GPU free")
    args = ap.parse_args(argv)
    print(json.dumps(partition(apply_local=args.apply_local), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
